"""Tiered article archiving for data/articles.json.

Tiers:
  - Hot (default 0-7 days): full article retained in articles.json
  - Warm (default 7-30 days): content field stripped, metadata kept
  - Cold (default 30+ days): moved to data/archives/YYYY-MM.json
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
ARCHIVES_DIR = DATA_DIR / "archives"
DEFAULT_SCHEMA_PATH = "../docs/schemas/articles.schema.json"

DEFAULT_HOT_DAYS = 7
DEFAULT_WARM_DAYS = 30
CURATED_HOT_EXTENSION = 7  # extra days of hot retention for curated articles


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso8601(value: object) -> datetime | None:
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


def _load_articles() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not ARTICLES_FILE.exists():
        return [], None
    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        return [a for a in payload if isinstance(a, dict)], None
    if isinstance(payload, dict):
        raw = payload.get("articles", [])
        articles = (
            [a for a in raw if isinstance(a, dict)] if isinstance(raw, list) else []
        )
        return articles, payload
    return [], None


def _save_articles(
    articles: list[dict[str, Any]], wrapper: dict[str, Any] | None
) -> None:
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if wrapper is not None:
        wrapper["articles"] = articles
        wrapper["total_count"] = len(articles)
        wrapper["last_updated"] = _utc_now_iso()
        payload: object = wrapper
    else:
        payload = {
            "$schema": DEFAULT_SCHEMA_PATH,
            "articles": articles,
            "last_updated": _utc_now_iso(),
            "total_count": len(articles),
        }
    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _archive_key(published_at: datetime) -> str:
    return f"{published_at.year}-{published_at.month:02d}"


def _load_archive(archive_path: Path) -> list[dict[str, Any]]:
    if not archive_path.exists():
        return []
    try:
        payload = _load_json(archive_path)
        if isinstance(payload, dict):
            raw = payload.get("articles", [])
            return (
                [a for a in raw if isinstance(a, dict)] if isinstance(raw, list) else []
            )
        if isinstance(payload, list):
            return [a for a in payload if isinstance(a, dict)]
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read archive file %s, starting fresh", archive_path)
    return []


def _save_archive(archive_path: Path, articles: list[dict[str, Any]]) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "../schemas/articles.schema.json",
        "articles": articles,
        "total_count": len(articles),
        "archived_at": _utc_now_iso(),
    }
    archive_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _strip_content(article: dict[str, Any]) -> dict[str, Any]:
    stripped = dict(article)
    stripped.pop("content", None)
    return stripped


def archive_articles(
    *,
    dry_run: bool = True,
    hot_days: int = DEFAULT_HOT_DAYS,
    warm_days: int = DEFAULT_WARM_DAYS,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    hot_cutoff = now - timedelta(days=hot_days)
    warm_cutoff = now - timedelta(days=warm_days)

    articles, wrapper = _load_articles()
    if not articles:
        return {
            "total": 0,
            "hot": 0,
            "warm": 0,
            "cold": 0,
            "content_stripped": 0,
            "archived": 0,
            "bytes_saved": 0,
        }

    hot: list[dict[str, Any]] = []
    warm: list[dict[str, Any]] = []
    cold: dict[str, list[dict[str, Any]]] = {}  # archive_key -> articles

    original_json_size = len(json.dumps(articles, ensure_ascii=False))

    for article in articles:
        published = _parse_iso8601(article.get("published_at"))
        if published is None:
            hot.append(article)
            continue

        is_curated = article.get("status") == "curated"
        effective_hot_cutoff = (
            hot_cutoff - timedelta(days=CURATED_HOT_EXTENSION)
            if is_curated
            else hot_cutoff
        )

        if published >= effective_hot_cutoff:
            hot.append(article)
        elif published >= warm_cutoff:
            warm.append(article)
        else:
            key = _archive_key(published)
            cold.setdefault(key, []).append(article)

    # Process warm: strip content
    warm_stripped = [_strip_content(a) for a in warm]

    # Process cold: merge into archive files
    cold_count = sum(len(v) for v in cold.values())

    if not dry_run:
        # Save warm articles back to main file
        all_articles = hot + warm_stripped
        _save_articles(all_articles, wrapper)

        # Archive cold articles
        for key, cold_articles in cold.items():
            archive_path = ARCHIVES_DIR / f"articles-{key}.json"
            existing = _load_archive(archive_path)
            existing_ids = {a.get("id") for a in existing}
            new_articles = [a for a in cold_articles if a.get("id") not in existing_ids]
            if new_articles:
                _save_archive(archive_path, existing + new_articles)
                logger.info(
                    "Archived %d articles to %s", len(new_articles), archive_path
                )

    final_articles = hot + warm_stripped
    final_json_size = len(json.dumps(final_articles, ensure_ascii=False))
    bytes_saved = original_json_size - final_json_size

    return {
        "total": len(articles),
        "hot": len(hot),
        "warm": len(warm),
        "cold": cold_count,
        "content_stripped": len(warm),
        "archived": cold_count,
        "bytes_saved": bytes_saved,
        "original_size_kb": original_json_size // 1024,
        "final_size_kb": final_json_size // 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiered article archiving")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without writing (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes to articles.json and archive files",
    )
    parser.add_argument(
        "--hot-days",
        type=int,
        default=DEFAULT_HOT_DAYS,
        help=f"Days to keep articles at full fidelity (default: {DEFAULT_HOT_DAYS})",
    )
    parser.add_argument(
        "--warm-days",
        type=int,
        default=DEFAULT_WARM_DAYS,
        help=f"Days to keep articles with stripped content (default: {DEFAULT_WARM_DAYS})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    dry_run = not args.execute
    summary = archive_articles(
        dry_run=dry_run,
        hot_days=args.hot_days,
        warm_days=args.warm_days,
    )

    mode = "DRY RUN" if dry_run else "EXECUTED"
    print(f"\nArchive summary ({mode}):")
    print(f"  Total articles:     {summary['total']}")
    print(f"  Hot (full):         {summary['hot']}")
    print(f"  Warm (stripped):    {summary['warm']}")
    print(f"  Cold (archived):    {summary['cold']}")
    if summary["bytes_saved"] > 0:
        print(
            f"  Size reduction:     {summary['original_size_kb']}KB -> "
            f"{summary['final_size_kb']}KB ({summary['bytes_saved'] // 1024}KB saved)"
        )
    if dry_run:
        print("\nRe-run with --execute to apply changes.")


if __name__ == "__main__":
    main()
