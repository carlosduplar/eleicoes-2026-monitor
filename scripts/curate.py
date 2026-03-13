"""Editor-chefe curation pipeline with 90-minute skip logic."""

from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import generate_quiz as extract_quiz_positions
except ImportError:  # pragma: no cover - direct script execution path
    import generate_quiz as extract_quiz_positions  # type: ignore[no-redef]

try:
    from scripts.sanitize.constants import SOURCE_CATEGORY_WEIGHTS
except ImportError:  # pragma: no cover - direct script execution path
    from sanitize.constants import SOURCE_CATEGORY_WEIGHTS  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
CURATED_FEED_FILE = DATA_DIR / "curated_feed.json"
WEEKLY_BRIEFING_FILE = DATA_DIR / "weekly_briefing.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
LAST_RUN_FILE = DATA_DIR / ".curate_last_run"

API_KEY_PATTERN = re.compile(
    r"(key|api_key|apikey|devKey)=[A-Za-z0-9_-]{20,}", re.IGNORECASE
)

MIN_INTERVAL_SECONDS = 90 * 60
RECENT_WINDOW_HOURS = 24
WEEK_WINDOW_DAYS = 7
PROMOTION_THRESHOLD = 0.8
MAX_FEED_ITEMS = 80
MAX_BRIEFING_TOP_ARTICLES = 10

def _utc_iso(dt: datetime | None = None) -> str:
    current = dt or datetime.now(timezone.utc)
    return current.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso8601(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _article_timestamp(article: dict[str, Any]) -> datetime | None:
    for key in ("published_at", "collected_at"):
        parsed = _parse_iso8601(article.get(key))
        if parsed is not None:
            return parsed
    return None


def _read_last_run_epoch() -> float:
    if not LAST_RUN_FILE.exists():
        return 0.0
    raw_value = LAST_RUN_FILE.read_text(encoding="utf-8").strip()
    if not raw_value:
        return 0.0
    try:
        return float(raw_value)
    except ValueError:
        return 0.0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles_document() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not ARTICLES_FILE.exists():
        return [], {"$schema": "../docs/schemas/articles.schema.json", "articles": []}
    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)], payload
    raise ValueError(f"Unsupported articles structure in {ARTICLES_FILE}")


def _save_articles_document(
    articles: list[dict[str, Any]], wrapper: dict[str, Any] | None
) -> None:
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if wrapper is None:
        payload: object = articles
    else:
        wrapper["articles"] = articles
        wrapper["last_updated"] = _utc_iso()
        wrapper["total_count"] = len(articles)
        payload = wrapper
    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _load_pipeline_errors() -> dict[str, Any]:
    if not PIPELINE_ERRORS_FILE.exists():
        return {"errors": [], "last_checked": None}
    try:
        payload = _load_json(PIPELINE_ERRORS_FILE)
    except json.JSONDecodeError:
        return {"errors": [], "last_checked": None}
    if not isinstance(payload, dict):
        return {"errors": [], "last_checked": None}
    if not isinstance(payload.get("errors"), list):
        payload["errors"] = []
    return payload


def _append_pipeline_error(message: str) -> None:
    sanitized = API_KEY_PATTERN.sub(r"\1=[REDACTED]", message)
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": _utc_iso(),
            "tier": "editor-chefe",
            "script": "curate.py",
            "article_id": None,
            "provider": None,
            "message": sanitized,
        }
    )
    payload["last_checked"] = _utc_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned and cleaned not in output:
                output.append(cleaned)
    return output


def _summaries_complete(article: dict[str, Any]) -> bool:
    summaries = article.get("summaries")
    if not isinstance(summaries, dict):
        return False
    pt = summaries.get("pt-BR")
    en = summaries.get("en-US")
    return (
        isinstance(pt, str)
        and pt.strip() != ""
        and isinstance(en, str)
        and en.strip() != ""
    )


def _has_editor_validation_history(article: dict[str, Any]) -> bool:
    history = article.get("edit_history")
    if not isinstance(history, list):
        return False
    for item in history:
        if not isinstance(item, dict):
            continue
        if item.get("tier") == "editor" and item.get("action") == "validated":
            return True
    return False


def _compute_prominence(article: dict[str, Any], now: datetime) -> float:
    timestamp = _article_timestamp(article)
    if timestamp is None:
        recency = 0.0
    else:
        age_hours = max(0.0, (now - timestamp).total_seconds() / 3600.0)
        recency = _clamp01(1.0 - (age_hours / float(RECENT_WINDOW_HOURS * 1.5)))

    status = article.get("status")
    default_confidence = 0.65 if status in {"validated", "curated"} else 0.4
    confidence = _clamp01(
        _safe_float(article.get("confidence_score"), default_confidence)
    )

    raw_relevance = _safe_float(article.get("relevance_score"), 0.0)
    if (
        raw_relevance <= 0.0
        and status in {"validated", "curated"}
        and _summaries_complete(article)
    ):
        relevance = 0.65
    else:
        relevance = _clamp01(raw_relevance)

    source_category = article.get("source_category")
    if isinstance(source_category, str):
        source_weight = SOURCE_CATEGORY_WEIGHTS.get(source_category, 0.6)
    else:
        source_weight = 0.6

    candidates = _string_list(article.get("candidates_mentioned"))
    topics = _string_list(article.get("topics"))
    candidate_signal = _clamp01(len(candidates) / 3.0)
    topic_signal = _clamp01(len(topics) / 4.0)
    sentiment_signal = _clamp01(abs(_safe_float(article.get("sentiment_score"), 0.0)))

    score = (
        recency * 0.34
        + confidence * 0.22
        + relevance * 0.16
        + source_weight * 0.08
        + candidate_signal * 0.08
        + topic_signal * 0.06
        + sentiment_signal * 0.06
    )
    if (
        isinstance(article.get("narrative_cluster_id"), str)
        and article["narrative_cluster_id"].strip()
    ):
        score += 0.04
    if _has_editor_validation_history(article):
        score += 0.03
    return round(_clamp01(score), 4)


def _append_curation_history(
    article: dict[str, Any], changed_fields: list[str]
) -> None:
    history = article.get("edit_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "tier": "editor-chefe",
            "at": _utc_iso(),
            "provider": "heuristic-curation",
            "action": "curated",
            "changes": changed_fields,
        }
    )
    article["edit_history"] = history


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _project_feed_article(article: dict[str, Any]) -> dict[str, Any]:
    summaries = article.get("summaries")
    if not isinstance(summaries, dict):
        summaries = {"pt-BR": "", "en-US": ""}
    projection: dict[str, Any] = {
        "id": article.get("id"),
        "url": article.get("url"),
        "title": article.get("title"),
        "source": article.get("source"),
        "source_category": article.get("source_category"),
        "published_at": article.get("published_at"),
        "collected_at": article.get("collected_at"),
        "status": article.get("status"),
        "prominence_score": round(_safe_float(article.get("prominence_score"), 0.0), 4),
        "sentiment_score": round(_safe_float(article.get("sentiment_score"), 0.0), 4),
        "candidates_mentioned": _string_list(article.get("candidates_mentioned")),
        "topics": _string_list(article.get("topics")),
        "summaries": {
            "pt-BR": summaries.get("pt-BR", ""),
            "en-US": summaries.get("en-US", ""),
        },
    }
    if projection["status"] == "curated":
        projection["badge"] = "destaque-redacao"
    return projection


def _sort_key(article: dict[str, Any]) -> tuple[int, float, datetime]:
    timestamp = _article_timestamp(article) or datetime.min.replace(tzinfo=timezone.utc)
    curated_rank = 1 if article.get("status") == "curated" else 0
    prominence = _safe_float(article.get("prominence_score"), 0.0)
    return curated_rank, prominence, timestamp


def _is_recent(article: dict[str, Any], now: datetime, *, hours: int) -> bool:
    timestamp = _article_timestamp(article)
    if timestamp is None:
        return False
    return timestamp >= now - timedelta(hours=hours)


def _build_curated_feed(
    articles: list[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    eligible = [a for a in articles if a.get("status") in {"validated", "curated"}]
    recent = [
        article
        for article in eligible
        if _is_recent(article, now, hours=RECENT_WINDOW_HOURS)
    ]
    source = recent if recent else eligible
    source.sort(key=_sort_key, reverse=True)
    selected = source[:MAX_FEED_ITEMS]
    projected = [_project_feed_article(article) for article in selected]
    curated_count = sum(1 for article in selected if article.get("status") == "curated")

    return {
        "generated_at": _utc_iso(now),
        "window_hours": RECENT_WINDOW_HOURS,
        "article_count": len(projected),
        "curated_count": curated_count,
        "articles": projected,
    }


def _build_editor_quality_audit(
    weekly_articles: list[dict[str, Any]],
) -> dict[str, Any]:
    tier_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    editor_change_counts: Counter[str] = Counter()

    for article in weekly_articles:
        history = article.get("edit_history")
        if not isinstance(history, list):
            continue
        for item in history:
            if not isinstance(item, dict):
                continue
            tier = item.get("tier")
            action = item.get("action")
            if isinstance(tier, str):
                tier_counts[tier] += 1
            if isinstance(action, str):
                action_counts[action] += 1
            if tier == "editor" and action == "validated":
                changes = item.get("changes")
                if isinstance(changes, list):
                    for changed_field in changes:
                        if isinstance(changed_field, str) and changed_field.strip():
                            editor_change_counts[changed_field.strip()] += 1

    low_confidence = sum(
        1
        for article in weekly_articles
        if _safe_float(article.get("confidence_score"), 0.0) < 0.6
    )
    foca_misclassified = sum(
        1
        for article in weekly_articles
        if article.get("status") in {"validated", "curated"}
        and _safe_float(article.get("relevance_score"), 0.0) < 0.7
    )

    return {
        "history_entries_by_tier": dict(sorted(tier_counts.items())),
        "history_entries_by_action": dict(sorted(action_counts.items())),
        "editor_changed_fields": dict(
            sorted(editor_change_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "low_confidence_articles": low_confidence,
        "possible_foca_misclassification": foca_misclassified,
    }


def _build_weekly_briefing(
    articles: list[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    week_start = now - timedelta(days=WEEK_WINDOW_DAYS)
    weekly_articles = [
        article
        for article in articles
        if article.get("status") in {"validated", "curated"}
        and (_article_timestamp(article) or datetime.min.replace(tzinfo=timezone.utc))
        >= week_start
    ]

    topic_count: Counter[str] = Counter()
    topic_prominence: defaultdict[str, list[float]] = defaultdict(list)
    candidate_count: Counter[str] = Counter()
    candidate_prominence: defaultdict[str, list[float]] = defaultdict(list)
    candidate_sentiment: defaultdict[str, list[float]] = defaultdict(list)
    candidate_recent_count: Counter[str] = Counter()
    candidate_previous_count: Counter[str] = Counter()
    day_cutoff = now - timedelta(days=1)

    for article in weekly_articles:
        prominence = _safe_float(article.get("prominence_score"), 0.0)
        sentiment = _safe_float(article.get("sentiment_score"), 0.0)
        timestamp = _article_timestamp(article) or datetime.min.replace(
            tzinfo=timezone.utc
        )

        for topic in _string_list(article.get("topics")):
            topic_count[topic] += 1
            topic_prominence[topic].append(prominence)

        for candidate in _string_list(article.get("candidates_mentioned")):
            candidate_count[candidate] += 1
            candidate_prominence[candidate].append(prominence)
            candidate_sentiment[candidate].append(sentiment)
            if timestamp >= day_cutoff:
                candidate_recent_count[candidate] += 1
            else:
                candidate_previous_count[candidate] += 1

    trending_topics = [
        {
            "topic": topic,
            "article_count": count,
            "avg_prominence": _average(topic_prominence[topic]),
        }
        for topic, count in topic_count.most_common(10)
    ]

    candidate_highlights: list[dict[str, Any]] = []
    for candidate, count in candidate_count.most_common():
        recent = candidate_recent_count[candidate]
        previous = candidate_previous_count[candidate]
        previous_rate = previous / 6.0 if previous > 0 else 0.0
        recent_rate = float(recent)
        if recent > 0 and recent_rate > previous_rate * 1.25:
            trend = "rising"
        elif previous > 0 and recent_rate < previous_rate * 0.75:
            trend = "falling"
        else:
            trend = "stable"
        candidate_highlights.append(
            {
                "candidate_slug": candidate,
                "article_count": count,
                "avg_prominence": _average(candidate_prominence[candidate]),
                "avg_sentiment": _average(candidate_sentiment[candidate]),
                "trend": trend,
            }
        )

    top_articles_source = sorted(weekly_articles, key=_sort_key, reverse=True)[
        :MAX_BRIEFING_TOP_ARTICLES
    ]
    top_articles = [
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "url": article.get("url"),
            "source": article.get("source"),
            "published_at": article.get("published_at"),
            "prominence_score": round(
                _safe_float(article.get("prominence_score"), 0.0), 4
            ),
            "status": article.get("status"),
        }
        for article in top_articles_source
    ]

    top_topic = trending_topics[0]["topic"] if trending_topics else "sem_dados"
    top_candidate = (
        candidate_highlights[0]["candidate_slug"]
        if candidate_highlights
        else "sem_dados"
    )
    summary_pt = (
        f"Resumo semanal: {len(weekly_articles)} artigos validados/curados. "
        f"Tema com maior cobertura: {top_topic}. Candidato mais citado: {top_candidate}."
    )
    summary_en = (
        f"Weekly briefing: {len(weekly_articles)} validated/curated articles. "
        f"Most covered topic: {top_topic}. Most mentioned candidate: {top_candidate}."
    )

    return {
        "generated_at": _utc_iso(now),
        "window_start": _utc_iso(week_start),
        "window_end": _utc_iso(now),
        "article_count": len(weekly_articles),
        "summary_pt": summary_pt,
        "summary_en": summary_en,
        "trending_topics": trending_topics,
        "candidate_highlights": candidate_highlights,
        "editor_quality_audit": _build_editor_quality_audit(weekly_articles),
        "top_articles": top_articles,
    }


def _run_quiz_refresh() -> bool:
    try:
        extract_quiz_positions.main()
        return True
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            return True
        message = f"Quiz refresh exited with non-zero code: {code}"
        _append_pipeline_error(message)
        logger.warning(message)
        return False
    except Exception as exc:
        message = f"Quiz refresh failed: {exc}"
        _append_pipeline_error(message)
        logger.warning(message)
        return False


def curate(now: datetime) -> dict[str, int]:
    articles, wrapper = _load_articles_document()
    promoted_count = 0
    eligible_count = 0

    for article in articles:
        status = article.get("status")
        if status not in {"validated", "curated"}:
            continue
        eligible_count += 1
        prominence = _compute_prominence(article, now)
        previous_prominence = _safe_float(article.get("prominence_score"), -1.0)
        article["prominence_score"] = prominence

        if status == "validated" and prominence > PROMOTION_THRESHOLD:
            article["status"] = "curated"
            changed_fields = ["status", "prominence_score"]
            if round(previous_prominence, 4) == prominence:
                changed_fields = ["status"]
            _append_curation_history(article, changed_fields)
            promoted_count += 1

    curated_feed_payload = _build_curated_feed(articles, now)
    weekly_briefing_payload = _build_weekly_briefing(articles, now)

    _save_articles_document(articles, wrapper)
    _write_json(CURATED_FEED_FILE, curated_feed_payload)
    _write_json(WEEKLY_BRIEFING_FILE, weekly_briefing_payload)
    quiz_ok = _run_quiz_refresh()

    return {
        "eligible": eligible_count,
        "promoted": promoted_count,
        "feed_articles": len(curated_feed_payload["articles"]),
        "quiz_ok": 1 if quiz_ok else 0,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    last_run_epoch = _read_last_run_epoch()
    now_epoch = time.time()
    elapsed = now_epoch - last_run_epoch
    if elapsed < MIN_INTERVAL_SECONDS:
        print(f"Skipping: only {elapsed / 60:.1f} min since last run (minimum: 90 min)")
        raise SystemExit(0)

    now_dt = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    summary = curate(now_dt)

    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(str(now_epoch), encoding="utf-8")
    quiz_status = "ok" if summary["quiz_ok"] else "failed"
    print(
        f"Curate: processed {summary['eligible']} validated/curated articles, "
        f"promoted {summary['promoted']}, feed {summary['feed_articles']} items, quiz {quiz_status}"
    )


if __name__ == "__main__":
    main()
