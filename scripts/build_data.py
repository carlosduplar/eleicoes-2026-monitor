"""Data consolidation for data/articles.json in Phase 03."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

try:
    from scripts import editor_feedback
except ImportError:  # pragma: no cover - direct script execution path
    import editor_feedback  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "articles.schema.json"
ARTICLES_FILE = DATA_DIR / "articles.json"
EDITOR_FEEDBACK_FILE = DATA_DIR / "editor_feedback.json"

ARTICLE_LIMIT = 500
DEFAULT_SCHEMA_PATH = "../docs/schemas/articles.schema.json"


@dataclass
class ArticlesDocument:
    articles: list[dict[str, Any]]
    wrapped: bool
    schema_path: str


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO 8601 format with Z suffix."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles_document() -> ArticlesDocument:
    if not ARTICLES_FILE.exists():
        return ArticlesDocument(
            articles=[], wrapped=True, schema_path=DEFAULT_SCHEMA_PATH
        )

    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        articles = [item for item in payload if isinstance(item, dict)]
        return ArticlesDocument(
            articles=articles, wrapped=False, schema_path=DEFAULT_SCHEMA_PATH
        )

    if isinstance(payload, dict):
        raw_articles = payload.get("articles", [])
        if isinstance(raw_articles, list):
            schema_path = payload.get("$schema", DEFAULT_SCHEMA_PATH)
            if not isinstance(schema_path, str) or not schema_path.strip():
                schema_path = DEFAULT_SCHEMA_PATH
            articles = [item for item in raw_articles if isinstance(item, dict)]
            return ArticlesDocument(
                articles=articles, wrapped=True, schema_path=schema_path
            )

    raise ValueError(f"Unsupported articles structure in {ARTICLES_FILE}")


def _save_articles_document(document: ArticlesDocument) -> None:
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if document.wrapped:
        payload: object = {
            "$schema": document.schema_path or DEFAULT_SCHEMA_PATH,
            "articles": document.articles,
            "last_updated": utc_now_iso(),
            "total_count": len(document.articles),
        }
    else:
        payload = document.articles

    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _parse_iso8601(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)

    text_value = value.strip()
    if not text_value:
        return datetime.min.replace(tzinfo=timezone.utc)

    normalized = text_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _deduplicate_by_id(
    articles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    deduplicated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    duplicates_removed = 0

    for article in articles:
        article_id = article.get("id")
        if isinstance(article_id, str):
            if article_id in seen_ids:
                duplicates_removed += 1
                continue
            seen_ids.add(article_id)
        deduplicated.append(article)

    return deduplicated, duplicates_removed


def _load_article_validator() -> Draft7Validator:
    schema = _load_json(SCHEMA_FILE)
    if not isinstance(schema, dict):
        raise ValueError(f"Expected object schema in {SCHEMA_FILE}")

    definitions = schema.get("definitions")
    if isinstance(definitions, dict):
        article_schema = definitions.get("Article")
        if isinstance(article_schema, dict):
            return Draft7Validator(article_schema)

    items = schema.get("items")
    if isinstance(items, dict) and "$ref" not in items:
        return Draft7Validator(items)

    raise ValueError("Could not resolve Article schema definition for validation.")


NUMBER_FIELDS = [
    "relevance_score",
    "sentiment_score",
    "confidence_score",
    "prominence_score",
]


def _normalize_null_numbers(article: dict[str, Any]) -> None:
    for field in NUMBER_FIELDS:
        if article.get(field) is None:
            article[field] = 0.0


def _validate_articles(articles: list[dict[str, Any]]) -> int:
    validator = _load_article_validator()
    invalid_count = 0

    for article in articles:
        _normalize_null_numbers(article)
        errors = sorted(validator.iter_errors(article), key=lambda err: list(err.path))
        if not errors:
            continue
        invalid_count += 1
        article_id = article.get("id", "<missing-id>")
        logger.warning(
            "Schema validation warning for article %s: %s",
            article_id,
            errors[0].message,
        )

    return invalid_count


def consolidate_articles() -> tuple[int, int, int]:
    """Deduplicate, sort, trim, and validate article data."""
    document = _load_articles_document()
    deduplicated, duplicates_removed = _deduplicate_by_id(document.articles)
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)
    feedback_sync_count = editor_feedback.add_irrelevant_article_ids(
        feedback, deduplicated
    )

    published_articles: list[dict[str, Any]] = []
    filtered_out_count = 0
    for article in deduplicated:
        if article.get("status") == "irrelevant":
            filtered_out_count += 1
            continue
        if editor_feedback.feedback_reason_for_article(article, feedback) is not None:
            filtered_out_count += 1
            continue
        published_articles.append(article)

    published_articles.sort(
        key=lambda article: _parse_iso8601(article.get("published_at")), reverse=True
    )

    trimmed_count = max(0, len(published_articles) - ARTICLE_LIMIT)
    if trimmed_count:
        published_articles = published_articles[:ARTICLE_LIMIT]

    _validate_articles(published_articles)

    if feedback_sync_count > 0 or not EDITOR_FEEDBACK_FILE.exists():
        editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)

    if published_articles != document.articles or not ARTICLES_FILE.exists():
        document.articles = published_articles
        _save_articles_document(document)

    print(
        f"Consolidated: {len(published_articles)} published articles "
        f"({duplicates_removed} duplicates removed, {filtered_out_count} filtered by relevance/editor feedback, {trimmed_count} trimmed by limit)"
    )
    return len(published_articles), duplicates_removed, trimmed_count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    consolidate_articles()


if __name__ == "__main__":
    main()
