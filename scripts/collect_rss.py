"""RSS feed collection pipeline for Phase 03."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import feedparser

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
ARTICLES_FILE = DATA_DIR / "articles.json"

REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "eleicoes-2026-monitor/1.0 (+https://github.com/carlosduplar/eleicoes-2026-monitor)"
DEFAULT_SCHEMA_PATH = "../docs/schemas/articles.schema.json"


@dataclass
class ArticlesDocument:
    articles: list[dict[str, Any]]
    wrapped: bool
    schema_path: str


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO 8601 format with Z suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_article_id(url: str) -> str:
    """Return deterministic article id based on sha256(url.encode())[:16]."""
    return sha256(url.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles_document() -> ArticlesDocument:
    if not ARTICLES_FILE.exists():
        return ArticlesDocument(articles=[], wrapped=True, schema_path=DEFAULT_SCHEMA_PATH)

    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        articles = [item for item in payload if isinstance(item, dict)]
        return ArticlesDocument(articles=articles, wrapped=False, schema_path=DEFAULT_SCHEMA_PATH)

    if isinstance(payload, dict):
        raw_articles = payload.get("articles", [])
        if isinstance(raw_articles, list):
            schema_path = payload.get("$schema", DEFAULT_SCHEMA_PATH)
            if not isinstance(schema_path, str) or not schema_path.strip():
                schema_path = DEFAULT_SCHEMA_PATH
            articles = [item for item in raw_articles if isinstance(item, dict)]
            return ArticlesDocument(articles=articles, wrapped=True, schema_path=schema_path)

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


def load_active_rss_sources() -> list[dict[str, str]]:
    """Read active RSS sources from data/sources.json."""
    payload = _load_json(SOURCES_FILE)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {SOURCES_FILE}")

    rss_sources = payload.get("rss", [])
    if not isinstance(rss_sources, list):
        raise ValueError(f"Expected 'rss' array in {SOURCES_FILE}")

    active_sources: list[dict[str, str]] = []
    for source in rss_sources:
        if not isinstance(source, dict) or not source.get("active", False):
            continue

        name = source.get("name")
        url = source.get("url")
        category = source.get("category")

        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(url, str) or not url.strip():
            continue

        item: dict[str, str] = {"name": name.strip(), "url": url.strip()}
        if isinstance(category, str) and category.strip():
            item["category"] = category.strip()
        active_sources.append(item)

    return active_sources


def fetch_feed_entries(feed_url: str) -> list[dict[str, Any]]:
    """Fetch and parse RSS feed entries with a per-feed timeout."""
    request = Request(feed_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw_bytes = response.read()

    parsed = feedparser.parse(raw_bytes)
    if getattr(parsed, "bozo", False):
        bozo_exception = getattr(parsed, "bozo_exception", None)
        if bozo_exception is not None:
            logger.warning("Feed parse warning for %s: %s", feed_url, bozo_exception)

    raw_entries = parsed.get("entries", [])
    if not isinstance(raw_entries, list):
        return []

    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        if hasattr(entry, "get"):
            entries.append(dict(entry))
    return entries


def _extract_entry_url(entry: dict[str, Any]) -> str | None:
    for key in ("link", "id", "url"):
        value = entry.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _extract_entry_title(entry: dict[str, Any], fallback: str) -> str:
    value = entry.get("title")
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return fallback


def _to_iso8601_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_published_at(entry: dict[str, Any], fallback_iso: str) -> str:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed_value = entry.get(key)
        if parsed_value is None:
            continue
        try:
            dt = datetime(*parsed_value[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        return _to_iso8601_utc(dt)

    for key in ("published", "updated", "created"):
        raw_value = entry.get(key)
        if not isinstance(raw_value, str):
            continue
        text_value = raw_value.strip()
        if not text_value:
            continue
        try:
            dt = parsedate_to_datetime(text_value)
        except (TypeError, ValueError, IndexError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return _to_iso8601_utc(dt)

    return fallback_iso


def collect_articles() -> tuple[int, int, int]:
    """Collect new RSS entries and append unseen articles to data/articles.json."""
    sources = load_active_rss_sources()
    document = _load_articles_document()
    existing_ids = {
        article_id
        for article in document.articles
        for article_id in [article.get("id")]
        if isinstance(article_id, str)
    }

    new_articles: list[dict[str, Any]] = []
    errors = 0

    for source in sources:
        source_name = source["name"]
        source_url = source["url"]
        source_category = source.get("category")
        try:
            entries = fetch_feed_entries(source_url)
        except Exception as exc:
            errors += 1
            logger.warning("Failed to fetch feed %s (%s): %s", source_name, source_url, exc)
            continue

        for entry in entries:
            article_url = _extract_entry_url(entry)
            if article_url is None:
                continue

            article_id = build_article_id(article_url)
            if article_id in existing_ids:
                continue

            collected_at = utc_now_iso()
            article: dict[str, Any] = {
                "id": article_id,
                "url": article_url,
                "title": _extract_entry_title(entry, article_url),
                "source": source_name,
                "published_at": _extract_published_at(entry, collected_at),
                "collected_at": collected_at,
                "status": "raw",
                "relevance_score": None,
                "candidates_mentioned": [],
                "topics": [],
                "summaries": {"pt-BR": "", "en-US": ""},
            }
            if source_category:
                article["source_category"] = source_category

            new_articles.append(article)
            existing_ids.add(article_id)

    if new_articles:
        document.articles.extend(new_articles)
        _save_articles_document(document)
    elif not ARTICLES_FILE.exists():
        _save_articles_document(document)

    print(f"Collected {len(new_articles)} new articles from {len(sources)} sources ({errors} errors)")
    return len(new_articles), len(sources), errors


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_articles()


if __name__ == "__main__":
    main()
