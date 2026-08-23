"""Utilities for editorial feedback rules used by ingestion and publishing."""

from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from scripts.store import PUB_DATA_DIR as DATA_DIR, STATE_DIR
except ImportError:  # pragma: no cover - direct script execution path
    from store import PUB_DATA_DIR as DATA_DIR, STATE_DIR
EDITOR_FEEDBACK_FILE = STATE_DIR / "editor_feedback.json"
DEFAULT_SCHEMA_PATH = "../docs/schemas/editor_feedback.schema.json"
DEFAULT_PRUNE_MAX_AGE_DAYS = 90


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_article_id(url: str) -> str:
    return sha256(url.encode("utf-8")).hexdigest()[:16]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().replace("_", " ").replace("-", " ").split())


def _normalize_string_list(
    value: object,
    *,
    normalize_text_values: bool = False,
    lowercase_values: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        return []

    output: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        if normalize_text_values:
            cleaned = _normalize_text(cleaned)
        elif lowercase_values:
            cleaned = cleaned.lower()
        if cleaned in seen:
            continue
        output.append(cleaned)
        seen.add(cleaned)
    return output


def _empty_feedback_payload() -> dict[str, Any]:
    return {
        "$schema": DEFAULT_SCHEMA_PATH,
        "updated_at": None,
        "irrelevant_article_ids": [],
        "irrelevant_article_ids_meta": {},
        "blocked_title_keywords": [],
        "blocked_url_substrings": [],
        "blocked_sources": [],
    }


def normalize_feedback(payload: object) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    normalized = _empty_feedback_payload()

    schema_path = source.get("$schema")
    if isinstance(schema_path, str) and schema_path.strip():
        normalized["$schema"] = schema_path.strip()

    updated_at = source.get("updated_at")
    if isinstance(updated_at, str) and updated_at.strip():
        normalized["updated_at"] = updated_at.strip()

    normalized["irrelevant_article_ids"] = sorted(
        _normalize_string_list(
            source.get("irrelevant_article_ids"), lowercase_values=True
        )
    )

    kept_ids = set(normalized["irrelevant_article_ids"])
    meta_source = source.get("irrelevant_article_ids_meta")
    meta: dict[str, str] = {}
    if isinstance(meta_source, dict):
        for key, value in meta_source.items():
            if (
                isinstance(key, str)
                and key in kept_ids
                and isinstance(value, str)
                and _parse_timestamp(value) is not None
            ):
                meta[key] = value.strip()
    normalized["irrelevant_article_ids_meta"] = meta

    normalized["blocked_title_keywords"] = sorted(
        _normalize_string_list(
            source.get("blocked_title_keywords"), normalize_text_values=True
        )
    )
    normalized["blocked_url_substrings"] = sorted(
        _normalize_string_list(
            source.get("blocked_url_substrings"), lowercase_values=True
        )
    )
    normalized["blocked_sources"] = sorted(
        _normalize_string_list(
            source.get("blocked_sources"), normalize_text_values=True
        )
    )

    return normalized


def load_editor_feedback(path: Path = EDITOR_FEEDBACK_FILE) -> dict[str, Any]:
    if not path.exists():
        return _empty_feedback_payload()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_feedback(payload)


def save_editor_feedback(
    payload: dict[str, Any], path: Path = EDITOR_FEEDBACK_FILE
) -> None:
    normalized = normalize_feedback(payload)
    normalized["updated_at"] = utc_now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def article_id_from_payload(article: dict[str, Any]) -> str | None:
    article_id = article.get("id")
    if isinstance(article_id, str) and article_id.strip():
        return article_id.strip().lower()

    url = article.get("url")
    if isinstance(url, str) and url.strip():
        return build_article_id(url.strip())

    return None


def add_article_id_to_feedback(
    feedback: dict[str, Any], article: dict[str, Any]
) -> bool:
    article_id = article_id_from_payload(article)
    if article_id is None:
        return False

    current_ids = set(
        _normalize_string_list(
            feedback.get("irrelevant_article_ids"), lowercase_values=True
        )
    )
    if article_id in current_ids:
        return False

    current_ids.add(article_id)
    feedback["irrelevant_article_ids"] = sorted(current_ids)
    meta = feedback.setdefault("irrelevant_article_ids_meta", {})
    if isinstance(meta, dict):
        meta[article_id] = utc_now_iso()
    return True


def add_irrelevant_article_ids(
    feedback: dict[str, Any], articles: list[dict[str, Any]]
) -> int:
    added = 0
    for article in articles:
        if article.get("status") != "irrelevant":
            continue
        if add_article_id_to_feedback(feedback, article):
            added += 1
    return added


def feedback_reason_for_article(
    article: dict[str, Any], feedback: dict[str, Any]
) -> str | None:
    article_id = article_id_from_payload(article)
    blocked_ids = set(
        _normalize_string_list(
            feedback.get("irrelevant_article_ids"), lowercase_values=True
        )
    )
    if article_id and article_id in blocked_ids:
        return "irrelevant_article_ids"

    source = article.get("source")
    source_normalized = _normalize_text(source) if isinstance(source, str) else ""
    blocked_sources = set(
        _normalize_string_list(
            feedback.get("blocked_sources"), normalize_text_values=True
        )
    )
    if source_normalized and source_normalized in blocked_sources:
        return "blocked_sources"

    raw_url = article.get("url")
    url_text = raw_url.strip().lower() if isinstance(raw_url, str) else ""
    for blocked_substring in _normalize_string_list(
        feedback.get("blocked_url_substrings"), lowercase_values=True
    ):
        if blocked_substring and blocked_substring in url_text:
            return "blocked_url_substrings"

    title = article.get("title")
    title_normalized = _normalize_text(title) if isinstance(title, str) else ""
    for keyword in _normalize_string_list(
        feedback.get("blocked_title_keywords"), normalize_text_values=True
    ):
        if keyword and keyword in title_normalized:
            return "blocked_title_keywords"

    return None


def prune_editor_feedback(
    feedback: dict[str, Any],
    *,
    max_age_days: int = DEFAULT_PRUNE_MAX_AGE_DAYS,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int]:
    """Drop article IDs whose last confirmation is older than max_age_days.

    IDs without a meta timestamp (legacy entries) are stamped with `now` so
    they age out gradually instead of disappearing in one shot. Rule lists
    (keywords/url substrings/sources) are never touched.
    """
    reference = now or datetime.now(timezone.utc)
    legacy_stamp = reference
    cutoff = reference - timedelta(days=max_age_days)

    ids = _normalize_string_list(
        feedback.get("irrelevant_article_ids"), lowercase_values=True
    )
    meta_source = feedback.get("irrelevant_article_ids_meta")
    meta: dict[str, str] = dict(meta_source) if isinstance(meta_source, dict) else {}

    kept: list[str] = []
    for article_id in ids:
        stamped_at = _parse_timestamp(meta.get(article_id))
        if stamped_at is None:
            meta[article_id] = legacy_stamp.isoformat().replace("+00:00", "Z")
            stamped_at = legacy_stamp
        if stamped_at >= cutoff:
            kept.append(article_id)
        else:
            meta.pop(article_id, None)

    pruned = dict(feedback)
    kept_set = set(kept)
    pruned["irrelevant_article_ids"] = kept
    pruned["irrelevant_article_ids_meta"] = {
        key: value for key, value in meta.items() if key in kept_set
    }
    removed = len(ids) - len(kept)
    if removed:
        logger.info("Pruned %d stale irrelevant article IDs", removed)
    return normalize_feedback(pruned), removed


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Prune stale entries from editor_feedback.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without writing (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply pruning to editor_feedback.json",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_PRUNE_MAX_AGE_DAYS,
        help=(
            "Days an unused article ID survives after its last confirmation "
            f"(default: {DEFAULT_PRUNE_MAX_AGE_DAYS})"
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not EDITOR_FEEDBACK_FILE.exists():
        print("No editor_feedback.json found; nothing to prune.")
        return

    dry_run = not args.execute
    feedback = load_editor_feedback(EDITOR_FEEDBACK_FILE)
    before = len(feedback.get("irrelevant_article_ids", []))
    rules_before = {
        key: len(feedback.get(key, []))
        for key in (
            "blocked_title_keywords",
            "blocked_url_substrings",
            "blocked_sources",
        )
    }

    pruned, removed = prune_editor_feedback(
        feedback, max_age_days=args.max_age_days
    )

    mode = "DRY RUN" if dry_run else "EXECUTED"
    print(f"\nEditor feedback prune summary ({mode}):")
    print(f"  Article IDs: {before} -> {before - removed} ({removed} pruned)")
    print(f"  Rule lists untouched: {rules_before}")
    if dry_run:
        print("\nRe-run with --execute to apply changes.")
        return

    meta_before = feedback.get("irrelevant_article_ids_meta", {})
    if removed == 0 and pruned["irrelevant_article_ids_meta"] == meta_before:
        print("  No changes to write.")
        return

    save_editor_feedback(pruned, EDITOR_FEEDBACK_FILE)


if __name__ == "__main__":
    main()
