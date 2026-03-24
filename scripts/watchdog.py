"""Watchdog health summary for pipeline outputs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"

PIPELINE_HEALTH_FILE = DATA_DIR / "pipeline_health.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
ARTICLES_FILE = DATA_DIR / "articles.json"
SENTIMENT_FILE = DATA_DIR / "sentiment.json"
CURATED_FEED_FILE = DATA_DIR / "curated_feed.json"
WEEKLY_BRIEFING_FILE = DATA_DIR / "weekly_briefing.json"
QUIZ_FILE = DATA_DIR / "quiz.json"
POLLS_FILE = DATA_DIR / "polls.json"

WORKFLOW_TARGETS: dict[str, dict[str, Any]] = {
    "foca_collect": {
        "path": ARTICLES_FILE,
        "stale_after_minutes": 120,
        "required": True,
    },
    "editor_validate": {
        "path": SENTIMENT_FILE,
        "stale_after_minutes": 180,
        "required": True,
    },
    "editor_chefe_curate": {
        "path": CURATED_FEED_FILE,
        "stale_after_minutes": 240,
        "required": True,
    },
    "weekly_briefing": {
        "path": WEEKLY_BRIEFING_FILE,
        "stale_after_minutes": 24 * 60,
        "required": True,
    },
    "quiz_refresh": {
        "path": QUIZ_FILE,
        "stale_after_minutes": 36 * 60,
        "required": True,
    },
    "polls_collect": {
        "path": POLLS_FILE,
        "stale_after_minutes": 24 * 60,
        "required": False,
    },
}


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


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _timestamp_from_articles(payload: object) -> datetime | None:
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
    elif isinstance(payload, list):
        raw_articles = payload
    else:
        raw_articles = None

    if not isinstance(raw_articles, list):
        return None

    newest: datetime | None = None
    for item in raw_articles:
        if not isinstance(item, dict):
            continue
        parsed = _parse_iso8601(item.get("collected_at")) or _parse_iso8601(
            item.get("published_at")
        )
        if parsed is None:
            continue
        if newest is None or parsed > newest:
            newest = parsed
    return newest


def _extract_last_update(path: Path, payload: object) -> datetime | None:
    if isinstance(payload, dict):
        for field in ("checked_at", "updated_at", "generated_at", "last_updated"):
            parsed = _parse_iso8601(payload.get(field))
            if parsed is not None:
                return parsed
        parsed_articles = _timestamp_from_articles(payload)
        if parsed_articles is not None:
            return parsed_articles
    elif isinstance(payload, list):
        parsed_articles = _timestamp_from_articles(payload)
        if parsed_articles is not None:
            return parsed_articles

    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _age_minutes(now: datetime, timestamp: datetime | None) -> int | None:
    if timestamp is None:
        return None
    delta = now - timestamp
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() // 60)


def _build_workflow_entry(
    *,
    name: str,
    path: Path,
    stale_after_minutes: int,
    required: bool,
    now: datetime,
) -> dict[str, Any]:
    payload = _load_json(path)
    if not path.exists():
        return {
            "status": "missing" if required else "unknown",
            "path": str(path.relative_to(ROOT_DIR)),
            "exists": False,
            "last_update": None,
            "age_minutes": None,
            "stale_after_minutes": stale_after_minutes,
            "details": f"{name} output not found",
        }

    last_update = _extract_last_update(path, payload)
    age = _age_minutes(now, last_update)
    if payload is None:
        status = "error"
        details = f"{name} output is not valid JSON"
    elif age is None:
        status = "error"
        details = f"{name} output has no recognizable timestamp"
    elif age > stale_after_minutes:
        status = "stale"
        details = f"{name} data is older than expected freshness window"
    else:
        status = "ok"
        details = f"{name} data freshness is within expected window"

    return {
        "status": status,
        "path": str(path.relative_to(ROOT_DIR)),
        "exists": True,
        "last_update": _utc_iso(last_update) if last_update else None,
        "age_minutes": age,
        "stale_after_minutes": stale_after_minutes,
        "details": details,
    }


def _summarize_pipeline_errors(now: datetime) -> dict[str, Any]:
    payload = _load_json(PIPELINE_ERRORS_FILE)
    if not isinstance(payload, dict):
        return {
            "exists": PIPELINE_ERRORS_FILE.exists(),
            "total_errors": 0,
            "last_24h_errors": 0,
            "by_tier": {},
            "last_error_at": None,
        }

    errors = payload.get("errors")
    if not isinstance(errors, list):
        errors = []

    day_ago = now - timedelta(hours=24)
    by_tier: Counter[str] = Counter()
    last_24h = 0
    latest_error: datetime | None = None

    for error in errors:
        if not isinstance(error, dict):
            continue
        tier = error.get("tier")
        if isinstance(tier, str):
            by_tier[tier] += 1
        parsed = _parse_iso8601(error.get("at"))
        if parsed is not None and parsed >= day_ago:
            last_24h += 1
        if parsed is not None and (latest_error is None or parsed > latest_error):
            latest_error = parsed

    return {
        "exists": True,
        "total_errors": len(errors),
        "last_24h_errors": last_24h,
        "by_tier": dict(sorted(by_tier.items())),
        "last_error_at": _utc_iso(latest_error) if latest_error else None,
    }


def _summarize_relevance_health() -> dict[str, Any]:
    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
    elif isinstance(payload, list):
        raw_articles = payload
    else:
        raw_articles = None

    if not isinstance(raw_articles, list):
        return {
            "checked_articles": 0,
            "zero_relevance_count": 0,
            "sample_article_ids": [],
        }

    checked = 0
    zero_relevance_ids: list[str] = []
    for item in raw_articles:
        if not isinstance(item, dict):
            continue
        if item.get("status") not in {"validated", "curated"}:
            continue
        checked += 1
        article_id = (
            item.get("id") if isinstance(item.get("id"), str) else "<missing-id>"
        )
        relevance_score = item.get("relevance_score")
        if (
            not isinstance(relevance_score, (int, float))
            or float(relevance_score) <= 0.0
        ):
            zero_relevance_ids.append(article_id)

    return {
        "checked_articles": checked,
        "zero_relevance_count": len(zero_relevance_ids),
        "sample_article_ids": zero_relevance_ids[:20],
    }


def _overall_status(
    workflows: dict[str, dict[str, Any]],
    error_summary: dict[str, Any],
    relevance_summary: dict[str, Any],
) -> str:
    statuses = {details.get("status") for details in workflows.values()}
    if "missing" in statuses or "error" in statuses:
        return "error"
    if "stale" in statuses:
        return "warning"
    if int(relevance_summary.get("zero_relevance_count", 0)) > 0:
        return "warning"
    if int(error_summary.get("last_24h_errors", 0)) >= 25:
        return "warning"
    return "ok"


def _status_note(
    overall_status: str,
    workflows: dict[str, dict[str, Any]],
    error_summary: dict[str, Any],
    relevance_summary: dict[str, Any],
) -> str:
    stale_workflows = [
        name for name, details in workflows.items() if details.get("status") == "stale"
    ]
    missing_workflows = [
        name
        for name, details in workflows.items()
        if details.get("status") == "missing"
    ]
    recent_errors = int(error_summary.get("last_24h_errors", 0))
    zero_relevance = int(relevance_summary.get("zero_relevance_count", 0))

    if overall_status == "ok":
        return "Pipeline health is stable and all monitored outputs are fresh."
    if overall_status == "warning":
        if zero_relevance > 0:
            return f"Found {zero_relevance} validated/curated articles with zero relevance_score."
        if stale_workflows:
            return f"Stale outputs detected: {', '.join(stale_workflows)}."
        return f"Elevated error volume in the last 24h ({recent_errors})."
    if missing_workflows:
        return f"Missing required outputs: {', '.join(missing_workflows)}."
    return "One or more pipeline outputs are invalid or unavailable."


def main() -> None:
    now = datetime.now(timezone.utc)
    workflows = {
        name: _build_workflow_entry(
            name=name,
            path=details["path"],
            stale_after_minutes=details["stale_after_minutes"],
            required=details["required"],
            now=now,
        )
        for name, details in WORKFLOW_TARGETS.items()
    }
    error_summary = _summarize_pipeline_errors(now)
    relevance_summary = _summarize_relevance_health()
    status = _overall_status(workflows, error_summary, relevance_summary)

    health = {
        "checked_at": _utc_iso(now),
        "status": status,
        "workflows": workflows,
        "error_summary": error_summary,
        "relevance_health": relevance_summary,
        "notes": _status_note(status, workflows, error_summary, relevance_summary),
    }
    PIPELINE_HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_HEALTH_FILE.write_text(
        json.dumps(health, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Watchdog: pipeline_health.json written ({status}).")


if __name__ == "__main__":
    main()
