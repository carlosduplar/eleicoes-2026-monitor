"""Utilities for editorial feedback rules used by ingestion and publishing."""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
EDITOR_FEEDBACK_FILE = DATA_DIR / "editor_feedback.json"
DEFAULT_SCHEMA_PATH = "../docs/schemas/editor_feedback.schema.json"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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
