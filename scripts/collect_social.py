"""Optional social media collection (Twitter + YouTube) for Phase 14."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import unicodedata

import tweepy

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
CANDIDATES_FILE = DATA_DIR / "candidates.json"
ARTICLES_FILE = DATA_DIR / "articles.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
DEFAULT_SCHEMA_PATH = "../docs/schemas/articles.schema.json"

CANDIDATE_SEARCH_TERMS: dict[str, str] = {}


@dataclass
class ArticlesDocument:
    articles: list[dict[str, Any]]
    wrapped: bool
    schema_path: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_article_id(url: str) -> str:
    return sha256(url.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles_document() -> ArticlesDocument:
    if not ARTICLES_FILE.exists():
        return ArticlesDocument(articles=[], wrapped=True, schema_path=DEFAULT_SCHEMA_PATH)

    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        return ArticlesDocument(
            articles=[item for item in payload if isinstance(item, dict)],
            wrapped=False,
            schema_path=DEFAULT_SCHEMA_PATH,
        )
    if isinstance(payload, dict):
        raw_articles = payload.get("articles", [])
        if isinstance(raw_articles, list):
            schema_path = payload.get("$schema", DEFAULT_SCHEMA_PATH)
            if not isinstance(schema_path, str) or not schema_path.strip():
                schema_path = DEFAULT_SCHEMA_PATH
            return ArticlesDocument(
                articles=[item for item in raw_articles if isinstance(item, dict)],
                wrapped=True,
                schema_path=schema_path,
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
    ARTICLES_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def _append_pipeline_error(*, source: str, message: str) -> None:
    """tier='foca', script='collect_social.py'."""
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": utc_now_iso(),
            "tier": "foca",
            "script": "collect_social.py",
            "source": source,
            "message": message,
        }
    )
    payload["last_checked"] = utc_now_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_accents.lower()


def _load_candidate_names() -> dict[str, str]:
    """Load candidate slug -> display name mapping from data/candidates.json."""
    payload = _load_json(CANDIDATES_FILE)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {CANDIDATES_FILE}")
    raw_candidates = payload.get("candidates", [])
    if not isinstance(raw_candidates, list):
        raise ValueError(f"Expected 'candidates' array in {CANDIDATES_FILE}")

    names: dict[str, str] = {}
    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            continue
        slug = candidate.get("slug")
        name = candidate.get("name")
        if isinstance(slug, str) and slug.strip() and isinstance(name, str) and name.strip():
            names[slug.strip()] = name.strip()
    return names


def _infer_candidates_from_text(text: str, candidate_names: dict[str, str]) -> list[str]:
    """Match candidate names/slugs in text, return list of slugs."""
    if not text.strip():
        return []
    normalized_text = _normalize_text(text)
    matched: list[str] = []
    for slug, display_name in candidate_names.items():
        slug_variant = _normalize_text(slug.replace("-", " "))
        name_variant = _normalize_text(display_name)
        if slug_variant in normalized_text or name_variant in normalized_text:
            matched.append(slug)
    return matched


def _to_iso_utc(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return utc_now_iso()


def _collect_twitter(
    existing_ids: set[str],
    candidate_names: dict[str, str],
) -> list[dict[str, Any]]:
    """Collect recent tweets mentioning candidates + '2026 eleições'."""
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "").strip()
    if not bearer_token:
        return []

    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
    new_articles: list[dict[str, Any]] = []

    for slug, name in candidate_names.items():
        query = f"\"{name}\" 2026 eleições"
        response = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=["created_at", "author_id", "text"],
        )
        if not response or not response.data:
            continue

        for tweet in response.data:
            tweet_id = getattr(tweet, "id", None)
            tweet_text = getattr(tweet, "text", "")
            if tweet_id is None or not isinstance(tweet_text, str) or not tweet_text.strip():
                continue

            tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
            article_id = build_article_id(tweet_url)
            if article_id in existing_ids:
                continue

            candidates = _infer_candidates_from_text(tweet_text, candidate_names)
            if slug not in candidates:
                candidates.append(slug)
            title = tweet_text.strip().replace("\n", " ")[:120]

            article = {
                "id": article_id,
                "url": tweet_url,
                "title": title,
                "source": "Twitter",
                "source_category": "social",
                "published_at": _to_iso_utc(getattr(tweet, "created_at", None)),
                "collected_at": utc_now_iso(),
                "status": "raw",
                "relevance_score": None,
                "candidates_mentioned": candidates,
                "topics": [],
                "summaries": {"pt-BR": "", "en-US": ""},
                "content": tweet_text,
            }
            new_articles.append(article)
            existing_ids.add(article_id)

    return new_articles


def _collect_youtube(
    existing_ids: set[str],
    candidate_names: dict[str, str],
) -> list[dict[str, Any]]:
    """Collect recent YouTube videos mentioning candidates + 'eleições 2026'."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        return []

    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=api_key)
    new_articles: list[dict[str, Any]] = []

    for slug, name in candidate_names.items():
        query = f"\"{name}\" eleições 2026"
        response = (
            youtube.search()
            .list(
                part="snippet",
                q=query,
                type="video",
                order="date",
                maxResults=10,
            )
            .execute()
        )

        items = response.get("items", [])
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id", {})
            snippet = item.get("snippet", {})
            if not isinstance(identifier, dict) or not isinstance(snippet, dict):
                continue

            video_id = identifier.get("videoId")
            title = snippet.get("title")
            published_at = snippet.get("publishedAt")
            if not isinstance(video_id, str) or not video_id.strip():
                continue
            if not isinstance(title, str) or not title.strip():
                continue

            video_url = f"https://youtu.be/{video_id}"
            article_id = build_article_id(video_url)
            if article_id in existing_ids:
                continue

            candidates = _infer_candidates_from_text(title, candidate_names)
            if slug not in candidates:
                candidates.append(slug)

            article = {
                "id": article_id,
                "url": video_url,
                "title": title.strip(),
                "source": "YouTube",
                "source_category": "social",
                "published_at": _to_iso_utc(published_at),
                "collected_at": utc_now_iso(),
                "status": "raw",
                "relevance_score": None,
                "candidates_mentioned": candidates,
                "topics": [],
                "summaries": {"pt-BR": "", "en-US": ""},
            }
            new_articles.append(article)
            existing_ids.add(article_id)

    return new_articles


def collect_social() -> tuple[int, int]:
    """Collect social media articles and append to data/articles.json."""
    has_twitter = bool(os.environ.get("TWITTER_BEARER_TOKEN", "").strip())
    has_youtube = bool(os.environ.get("YOUTUBE_API_KEY", "").strip())
    if not has_twitter and not has_youtube:
        print("Social: 0 new articles (0 errors) - TWITTER_BEARER_TOKEN/YOUTUBE_API_KEY not set")
        return 0, 0

    document = _load_articles_document()
    existing_ids = {
        article_id
        for article in document.articles
        for article_id in [article.get("id")]
        if isinstance(article_id, str)
    }

    candidate_names = _load_candidate_names()
    CANDIDATE_SEARCH_TERMS.clear()
    CANDIDATE_SEARCH_TERMS.update(candidate_names)

    new_articles: list[dict[str, Any]] = []
    error_count = 0

    if has_twitter:
        try:
            new_articles.extend(_collect_twitter(existing_ids, candidate_names))
        except Exception as exc:
            error_count += 1
            _append_pipeline_error(source="Twitter", message=str(exc))
            logger.warning("Twitter collection failed: %s", exc)

    if has_youtube:
        try:
            new_articles.extend(_collect_youtube(existing_ids, candidate_names))
        except Exception as exc:
            error_count += 1
            _append_pipeline_error(source="YouTube", message=str(exc))
            logger.warning("YouTube collection failed: %s", exc)

    if new_articles:
        document.articles.extend(new_articles)
        _save_articles_document(document)
    elif not ARTICLES_FILE.exists():
        _save_articles_document(document)

    print(f"Social: {len(new_articles)} new articles ({error_count} errors)")
    return len(new_articles), error_count


def main() -> None:
    """Entry point: configure logging, call collect_social()."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_social()


if __name__ == "__main__":
    main()
