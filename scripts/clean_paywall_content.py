"""One-time cleanup: clear paywall content from existing articles in data/articles.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sanitize.constants import is_paywall_content

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT_DIR / "data" / "articles.json"


def _load_articles_document(path: Path) -> tuple[list[dict], dict | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)], payload
    raise ValueError(f"Unsupported articles structure in {path}")


def clean_paywall_content(*, dry_run: bool = False) -> dict:
    """Scan articles.json and clear the content field on paywall-gated articles."""
    if not ARTICLES_FILE.exists():
        return {"cleared": 0, "scanned": 0}

    articles, wrapper = _load_articles_document(ARTICLES_FILE)
    cleared = 0

    for article in articles:
        content = article.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if is_paywall_content(content):
            article["content"] = ""
            cleared += 1
            logger.info("Cleared paywall content for %s", article.get("id", "?"))

    if not dry_run and cleared > 0:
        if wrapper is None:
            ARTICLES_FILE.write_text(
                json.dumps(articles, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        else:
            wrapper["articles"] = articles
            ARTICLES_FILE.write_text(
                json.dumps(wrapper, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    summary = {"scanned": len(articles), "cleared": cleared}
    print(f"Scanned {len(articles)} articles, cleared {cleared} paywall contents")
    return summary


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Clean paywall content from articles")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing",
    )
    args = parser.parse_args()
    clean_paywall_content(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
