"""Editor-tier sentiment analysis for validated and curated articles."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
import argparse
from typing import Any

from jsonschema import Draft7Validator

BATCH_SIZE = 5

try:
    from scripts import ai_client
except ImportError:  # pragma: no cover - direct script execution path
    import ai_client  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
SENTIMENT_FILE = DATA_DIR / "sentiment.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
SENTIMENT_SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "sentiment.schema.json"

API_KEY_PATTERN = re.compile(
    r"(key|api_key|apikey|devKey)=[A-Za-z0-9_-]{20,}", re.IGNORECASE
)

DISCLAIMER_PT = "Análise algorítmica do tom das notícias coletadas. Não representa pesquisa de opinião."
DISCLAIMER_EN = (
    "Algorithmic analysis of collected news tone. Does not represent opinion polling."
)
ARTICLE_DISCLAIMER_PT = "Análise algorítmica. Não representa pesquisa de opinião."
ARTICLE_DISCLAIMER_EN = "Algorithmic analysis. Does not represent polling data."

VALID_TOPICS = {
    "economia",
    "seguranca",
    "saude",
    "educacao",
    "meio_ambiente",
    "corrupcao",
    "armas",
    "privatizacao",
    "previdencia",
    "politica_ext",
    "lgbtq",
    "aborto",
    "indigenas",
    "impostos",
    "midia",
    "eleicoes",
}
VALID_SOURCE_CATEGORIES = {
    "mainstream",
    "politics",
    "magazine",
    "international",
    "institutional",
    "party",
}
VALID_SENTIMENT_LABELS = {"positivo", "neutro", "negativo"}
LABEL_TO_SCORE = {"positivo": 1.0, "neutro": 0.0, "negativo": -1.0}

CANONICAL_CANDIDATE_SLUGS = {
    "lula",
    "flavio-bolsonaro",
    "caiado",
    "zema",
    "eduardo-leite",
    "aldo-rebelo",
    "renan-santos",
    "ratinho-jr",
    "tarcisio",
}
CANDIDATE_ALIASES = {
    "lula": "lula",
    "luiz inacio lula da silva": "lula",
    "flavio bolsonaro": "flavio-bolsonaro",
    "flavio-bolsonaro": "flavio-bolsonaro",
    "caiado": "caiado",
    "ronaldo caiado": "caiado",
    "zema": "zema",
    "romeu zema": "zema",
    "eduardo leite": "eduardo-leite",
    "eduardo-leite": "eduardo-leite",
    "aldo rebelo": "aldo-rebelo",
    "aldo-rebelo": "aldo-rebelo",
    "renan santos": "renan-santos",
    "renan-santos": "renan-santos",
    "ratinho jr": "ratinho-jr",
    "ratinho-jr": "ratinho-jr",
    "carlos massa ratinho jr": "ratinho-jr",
    "carlos massa ratinho junior": "ratinho-jr",
    "tarcisio": "tarcisio",
    "tarcisio de freitas": "tarcisio",
}


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().replace("_", " ").replace("-", " ").split())


def _canonical_candidate_slug(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    if raw in CANONICAL_CANDIDATE_SLUGS:
        return raw
    return CANDIDATE_ALIASES.get(_normalize_text(raw))


def _strip_markdown_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _score_to_label(score: float) -> str:
    if score >= 0.2:
        return "positivo"
    if score <= -0.2:
        return "negativo"
    return "neutro"


def _clamp_score(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles_document() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
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
        wrapper["last_updated"] = utc_now_iso()
        wrapper["total_count"] = len(articles)
        payload = wrapper
    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _save_sentiment(payload: dict[str, Any]) -> None:
    SENTIMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENTIMENT_FILE.write_text(
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


def _append_pipeline_error(
    *, message: str, article_id: str | None, provider: str | None
) -> None:
    sanitized = API_KEY_PATTERN.sub(r"\1=[REDACTED]", message)
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": utc_now_iso(),
            "tier": "editor",
            "script": "analyze_sentiment.py",
            "article_id": article_id,
            "provider": provider,
            "message": sanitized,
        }
    )
    payload["last_checked"] = utc_now_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _normalize_topics(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for topic in value:
        if isinstance(topic, str):
            cleaned = topic.strip().lower()
            if cleaned in VALID_TOPICS and cleaned not in normalized:
                normalized.append(cleaned)
    return normalized


def _normalize_sentiment_labels(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for candidate, label in value.items():
        slug = _canonical_candidate_slug(candidate)
        if not slug or not isinstance(label, str):
            continue
        cleaned_label = label.strip().lower()
        if cleaned_label in VALID_SENTIMENT_LABELS:
            normalized[slug] = cleaned_label
    return normalized


def _label_map_to_scores(labels: dict[str, str]) -> dict[str, float]:
    return {
        candidate: LABEL_TO_SCORE[label]
        for candidate, label in labels.items()
        if label in LABEL_TO_SCORE
    }


def _normalize_score_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float] = {}
    for candidate, score in value.items():
        slug = _canonical_candidate_slug(candidate)
        if not slug:
            continue
        if isinstance(score, (int, float)):
            normalized[slug] = round(_clamp_score(float(score)), 4)
        elif isinstance(score, str):
            try:
                normalized[slug] = round(_clamp_score(float(score.strip())), 4)
            except ValueError:
                continue
    return normalized


def _extract_scores_from_ai_response(content: str) -> dict[str, float]:
    parsed = json.loads(_strip_markdown_code_fence(content))
    if not isinstance(parsed, dict):
        return {}

    source_map: object
    if isinstance(parsed.get("scores"), dict):
        source_map = parsed.get("scores")
    elif isinstance(parsed.get("sentiment_per_candidate"), dict):
        source_map = parsed.get("sentiment_per_candidate")
    else:
        source_map = parsed

    if not isinstance(source_map, dict):
        return {}

    scores: dict[str, float] = {}
    for candidate, value in source_map.items():
        slug = _canonical_candidate_slug(candidate)
        if not slug:
            continue
        numeric_value: float | None = None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
        elif isinstance(value, str):
            try:
                numeric_value = float(value.strip())
            except ValueError:
                numeric_value = None
        if numeric_value is None:
            continue
        scores[slug] = round(_clamp_score(numeric_value), 4)
    return scores


def _extract_batch_scores(content: str, article_count: int) -> list[dict[str, float]]:
    """Extract sentiment scores for each article from batch response."""
    try:
        parsed = json.loads(_strip_markdown_code_fence(content))
    except json.JSONDecodeError:
        return [{} for _ in range(article_count)]

    if not isinstance(parsed, dict):
        return [{} for _ in range(article_count)]

    results = []
    for i in range(article_count):
        key = f"article_{i}"
        article_scores = parsed.get(key, {})
        if isinstance(article_scores, dict):
            scores = {}
            for candidate, value in article_scores.items():
                slug = _canonical_candidate_slug(candidate)
                if slug and isinstance(value, (int, float)):
                    scores[slug] = round(_clamp_score(float(value)), 4)
            results.append(scores)
        else:
            results.append({})
    return results


def _build_batch_sentiment_prompt(articles: list[dict[str, Any]]) -> tuple[str, str]:
    """Build prompt for batch sentiment analysis of multiple articles."""
    system = (
        "You are a political sentiment analyst for Brazil 2026 coverage. "
        "Analyze multiple articles and return valid JSON only, no markdown. "
        "Use canonical candidate slugs as keys and scores from -1.0 to 1.0."
    )

    articles_text = []
    for i, article in enumerate(articles):
        title = (
            article.get("title", "") if isinstance(article.get("title"), str) else ""
        )
        content = (
            article.get("content", "")
            if isinstance(article.get("content"), str)
            else ""
        )
        summary_pt = ""
        summaries = article.get("summaries")
        if isinstance(summaries, dict) and isinstance(summaries.get("pt-BR"), str):
            summary_pt = summaries["pt-BR"].strip()
        candidate_hint = article.get("candidates_mentioned")
        candidate_list = (
            ", ".join(candidate_hint) if isinstance(candidate_hint, list) else ""
        )

        text = (content or summary_pt or title)[:600]
        articles_text.append(
            f"Article {i}: {title}\nContent: {text}\nKnown candidates: {candidate_list}"
        )

    user = f"""Analyze sentiment for these {len(articles)} articles:

{chr(10).join(articles_text)}

Return JSON:
{{
  "article_0": {{"lula": 0.2, "flavio-bolsonaro": -0.1}},
  "article_1": {{"caiado": 0.3}},
  ...
}}

Rules:
- Include only candidates mentioned in each article
- Use canonical slugs only
- Clamp all values to [-1.0, 1.0]"""
    return system, user


def _build_sentiment_prompt(article: dict[str, Any]) -> tuple[str, str]:
    title = article.get("title") if isinstance(article.get("title"), str) else ""
    content = article.get("content") if isinstance(article.get("content"), str) else ""
    summary_pt = ""
    summaries = article.get("summaries")
    if isinstance(summaries, dict) and isinstance(summaries.get("pt-BR"), str):
        summary_pt = summaries["pt-BR"].strip()
    candidate_hint = article.get("candidates_mentioned")
    candidate_list = (
        ", ".join(candidate_hint) if isinstance(candidate_hint, list) else ""
    )

    system = (
        "You are a political sentiment analyst for Brazil 2026 coverage. "
        "Return valid JSON only, no markdown. "
        "Use canonical candidate slugs as keys and scores from -1.0 to 1.0."
    )
    user = f"""Title: {title}
Content: {(content or summary_pt or title)[:2500]}
Known candidates: {candidate_list}

Return JSON:
{{
  "scores": {{
    "lula": 0.2,
    "flavio-bolsonaro": -0.1
  }}
}}

Rules:
- Include only candidates mentioned in the article.
- Use canonical slugs only.
- Clamp all values to [-1.0, 1.0]."""
    return system, user


def _ensure_article_defaults(article: dict[str, Any]) -> None:
    article["disclaimer_pt"] = ARTICLE_DISCLAIMER_PT
    article["disclaimer_en"] = ARTICLE_DISCLAIMER_EN
    article["narrative_cluster_id"] = (
        article.get("narrative_cluster_id")
        if isinstance(article.get("narrative_cluster_id"), str)
        else None
    )
    article["edit_history"] = (
        article.get("edit_history")
        if isinstance(article.get("edit_history"), list)
        else []
    )
    if not isinstance(article.get("summaries"), dict):
        article["summaries"] = {"pt-BR": "", "en-US": ""}
    if not isinstance(article.get("confidence_score"), (int, float)):
        article["confidence_score"] = 0.0
    labels = _normalize_sentiment_labels(article.get("sentiment_per_candidate"))
    article["sentiment_per_candidate"] = labels
    article["_sentiment_scores"] = _normalize_score_map(
        article.get("_sentiment_scores")
    )
    if isinstance(article.get("sentiment_score"), (int, float)):
        article["sentiment_score"] = round(
            _clamp_score(float(article["sentiment_score"])), 4
        )
    else:
        article["sentiment_score"] = 0.0
    article["topics"] = _normalize_topics(article.get("topics"))


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _aggregate_average(
    accumulator: dict[str, dict[str, list[float]]],
) -> dict[str, dict[str, float]]:
    aggregated: dict[str, dict[str, float]] = {}
    for outer_key in sorted(accumulator):
        inner = accumulator[outer_key]
        aggregated[outer_key] = {
            inner_key: _average(scores) for inner_key, scores in sorted(inner.items())
        }
    return aggregated


def _resolve_article_score_map(article: dict[str, Any]) -> dict[str, float]:
    score_map = _normalize_score_map(article.get("_sentiment_scores"))
    if score_map:
        article["_sentiment_scores"] = score_map
        return score_map

    labels = _normalize_sentiment_labels(article.get("sentiment_per_candidate"))
    if not labels:
        return {}

    derived = _label_map_to_scores(labels)
    if not derived:
        return {}

    article["_sentiment_scores"] = derived
    return derived


def _accumulate_article_sentiment(
    *,
    article: dict[str, Any],
    score_map: dict[str, float],
    by_topic_acc: dict[str, dict[str, list[float]]],
    by_source_acc: dict[str, dict[str, list[float]]],
) -> None:
    if not score_map:
        return

    topics = article.get("topics") if isinstance(article.get("topics"), list) else []
    normalized_topics = [
        topic for topic in topics if isinstance(topic, str) and topic in VALID_TOPICS
    ]
    if not normalized_topics:
        normalized_topics = ["eleicoes"]

    source_category = article.get("source_category")
    normalized_source = (
        source_category
        if isinstance(source_category, str)
        and source_category in VALID_SOURCE_CATEGORIES
        else "mainstream"
    )

    for candidate, score in score_map.items():
        candidate_topic_scores = by_topic_acc.setdefault(candidate, {})
        candidate_source_scores = by_source_acc.setdefault(candidate, {})
        for topic in normalized_topics:
            candidate_topic_scores.setdefault(topic, []).append(score)
        candidate_source_scores.setdefault(normalized_source, []).append(score)


def _compute_updated_at(articles: list[dict[str, Any]]) -> str:
    timestamps: list[datetime] = []
    for article in articles:
        if article.get("status") not in {"validated", "curated"}:
            continue
        for field in ("collected_at", "published_at"):
            parsed = _parse_iso8601(article.get(field))
            if parsed:
                timestamps.append(parsed)
                break
    if not timestamps:
        return utc_now_iso()
    return max(timestamps).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_sentiment_payload(payload: dict[str, Any]) -> None:
    schema = _load_json(SENTIMENT_SCHEMA_FILE)
    if not isinstance(schema, dict):
        raise ValueError("sentiment.schema.json must be a JSON object.")
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.path) or "<root>"
        raise ValueError(
            f"Sentiment payload schema validation failed at {where}: {first.message}"
        )


def analyze_sentiment(limit: int = 30) -> dict[str, Any]:
    articles, wrapper = _load_articles_document()

    by_topic_acc: dict[str, dict[str, list[float]]] = {}
    by_source_acc: dict[str, dict[str, list[float]]] = {}

    articles_needing_sentiment = []
    for article in articles:
        _ensure_article_defaults(article)
        status = article.get("status")
        if status not in {"validated", "curated"}:
            continue

        if article.get("_sentiment_scores"):
            continue

        articles_needing_sentiment.append(article)

    processed_articles = 0
    for batch_start in range(0, len(articles_needing_sentiment), BATCH_SIZE):
        if processed_articles >= limit:
            break

        batch = articles_needing_sentiment[batch_start : batch_start + BATCH_SIZE]
        batch_size = len(batch)

        system, user = _build_batch_sentiment_prompt(batch)

        provider_name: str | None = None
        try:
            response = ai_client.call_with_fallback(
                system=system, user=user, max_tokens=800
            )
            provider_name = (
                response.get("provider")
                if isinstance(response.get("provider"), str)
                else None
            )
            batch_scores = _extract_batch_scores(
                str(response.get("content", "")), batch_size
            )
        except Exception as exc:
            for article in batch:
                article_id = (
                    article.get("id") if isinstance(article.get("id"), str) else None
                )
                _append_pipeline_error(
                    message=str(exc), article_id=article_id, provider=provider_name
                )
                logger.warning(
                    "Batch sentiment failed for articles starting with %s: %s",
                    article_id or "<missing-id>",
                    exc,
                )
            continue

        for i, article in enumerate(batch):
            score_map = batch_scores[i] if i < len(batch_scores) else {}

            if score_map:
                label_map = {
                    candidate: _score_to_label(score)
                    for candidate, score in score_map.items()
                }
                article["sentiment_per_candidate"] = label_map
                article["_sentiment_scores"] = score_map
                article["sentiment_score"] = _average(list(score_map.values()))
                if isinstance(response.get("provider"), str):
                    article["_ai_provider"] = response["provider"]
                if isinstance(response.get("model"), str):
                    article["_ai_model"] = response["model"]
            else:
                article["sentiment_score"] = 0.0

            processed_articles += 1
            if processed_articles >= limit:
                break

    analyzed_article_count = 0
    for article in articles:
        status = article.get("status")
        if status not in {"validated", "curated"}:
            continue

        score_map = _resolve_article_score_map(article)
        if not score_map:
            continue

        analyzed_article_count += 1
        _accumulate_article_sentiment(
            article=article,
            score_map=score_map,
            by_topic_acc=by_topic_acc,
            by_source_acc=by_source_acc,
        )

    by_topic = _aggregate_average(by_topic_acc)
    by_source = _aggregate_average(by_source_acc)
    unique_topics = {
        topic for candidate_topics in by_topic.values() for topic in candidate_topics
    }

    payload: dict[str, Any] = {
        "updated_at": _compute_updated_at(articles),
        "article_count": analyzed_article_count,
        "methodology_url": "/metodologia",
        "disclaimer_pt": DISCLAIMER_PT,
        "disclaimer_en": DISCLAIMER_EN,
        "by_topic": by_topic,
        "by_source": by_source,
    }

    _validate_sentiment_payload(payload)
    _save_articles_document(articles, wrapper)
    _save_sentiment(payload)
    print(
        f"Sentiment: {len(by_topic)} candidates × {len(unique_topics)} topics, {processed_articles} articles processed"
    )
    return payload


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Editor-tier sentiment analysis")
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=30,
        help="Maximum articles to process per run (default: 30)",
    )
    args = parser.parse_args()
    analyze_sentiment(limit=args.limit)


if __name__ == "__main__":
    main()
