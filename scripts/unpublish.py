"""CLI for Editor and Editor-Chefe to unpublish irrelevant articles.

Usage:
    python -m scripts.unpublish --id b11be0191dcd7284
    python -m scripts.unpublish --id b11be0191dcd7284 --id b5bfa20bb6dc3d6b
    python -m scripts.unpublish --url "https://example.com/article"
    python -m scripts.unpublish --search "Neymar na seleção"
    python -m scripts.unpublish --list-irrelevant
    python -m scripts.unpublish --block-keyword "Lollapalooza"
    python -m scripts.unpublish --block-url-substring "/esporte/"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import editor_feedback
except ImportError:
    import editor_feedback  # type: ignore[no-redef]

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
EDITOR_FEEDBACK_FILE = DATA_DIR / "editor_feedback.json"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_articles() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not ARTICLES_FILE.exists():
        return [], {}

    payload = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("articles", []), payload
    if isinstance(payload, list):
        return payload, {}
    return [], {}


def _save_articles(articles: list[dict[str, Any]], wrapper: dict[str, Any]) -> None:
    if wrapper:
        wrapper["articles"] = articles
        wrapper["last_updated"] = utc_now_iso()
        wrapper["total_count"] = len(articles)
        payload: Any = wrapper
    else:
        payload = articles

    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _mark_article_irrelevant(article: dict[str, Any], tier: str = "editor") -> None:
    article["status"] = "irrelevant"
    article["relevance_score"] = 0.0

    history = article.get("edit_history", [])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "tier": tier,
            "at": utc_now_iso(),
            "provider": "manual",
            "action": "validated",
            "changes": ["status", "relevance_score"],
        }
    )
    article["edit_history"] = history


def unpublish_by_id(article_ids: list[str], tier: str = "editor") -> int:
    articles, wrapper = _load_articles()
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)

    id_set = {aid.strip().lower() for aid in article_ids}
    modified = 0

    for article in articles:
        aid = article.get("id", "")
        if isinstance(aid, str) and aid.strip().lower() in id_set:
            if article.get("status") != "irrelevant":
                _mark_article_irrelevant(article, tier)
                modified += 1
                title = article.get("title", "<no title>")
                print(f"  Unpublished: {aid} — {title}")

    editor_feedback.add_irrelevant_article_ids(feedback, articles)
    editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)

    if modified > 0:
        _save_articles(articles, wrapper)

    return modified


def unpublish_by_url(urls: list[str], tier: str = "editor") -> int:
    articles, wrapper = _load_articles()
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)

    url_set = {u.strip().lower() for u in urls}
    modified = 0

    for article in articles:
        article_url = article.get("url", "")
        if isinstance(article_url, str) and article_url.strip().lower() in url_set:
            if article.get("status") != "irrelevant":
                _mark_article_irrelevant(article, tier)
                modified += 1
                title = article.get("title", "<no title>")
                print(f"  Unpublished: {article.get('id', '?')} — {title}")

    editor_feedback.add_irrelevant_article_ids(feedback, articles)
    editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)

    if modified > 0:
        _save_articles(articles, wrapper)

    return modified


def search_articles(query: str) -> list[dict[str, Any]]:
    articles, _ = _load_articles()
    query_lower = query.lower()
    matches = []
    for article in articles:
        title = article.get("title", "").lower()
        content = article.get("content", "").lower()
        if query_lower in title or query_lower in content:
            matches.append(article)
    return matches


def list_irrelevant() -> list[dict[str, Any]]:
    articles, _ = _load_articles()
    return [a for a in articles if a.get("status") == "irrelevant"]


def block_keyword(keyword: str) -> None:
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)
    keywords = set(feedback.get("blocked_title_keywords", []))
    keywords.add(keyword)
    feedback["blocked_title_keywords"] = sorted(keywords)
    editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)
    print(f"  Blocked keyword: {keyword}")


def block_url_substring(substring: str) -> None:
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)
    substrings = set(feedback.get("blocked_url_substrings", []))
    substrings.add(substring.lower())
    feedback["blocked_url_substrings"] = sorted(substrings)
    editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)
    print(f"  Blocked URL substring: {substring}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unpublish irrelevant articles (Editor / Editor-Chefe tool)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--id",
        dest="ids",
        action="append",
        default=[],
        help="Article ID(s) to mark as irrelevant",
    )
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        default=[],
        help="Article URL(s) to mark as irrelevant",
    )
    parser.add_argument(
        "--search",
        type=str,
        default=None,
        help="Search articles by title/content keyword",
    )
    parser.add_argument(
        "--list-irrelevant",
        action="store_true",
        help="List all currently irrelevant articles",
    )
    parser.add_argument(
        "--block-keyword",
        dest="block_keywords",
        action="append",
        default=[],
        help="Block a title keyword (future articles matching will be filtered)",
    )
    parser.add_argument(
        "--block-url-substring",
        dest="block_url_substrings",
        action="append",
        default=[],
        help="Block a URL substring (future articles matching will be filtered)",
    )
    parser.add_argument(
        "--tier",
        type=str,
        default="editor",
        choices=["editor", "editor-chefe"],
        help="Editorial tier (default: editor)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_irrelevant:
        irrelevant = list_irrelevant()
        if not irrelevant:
            print("No irrelevant articles found.")
        else:
            print(f"Irrelevant articles ({len(irrelevant)}):")
            for article in irrelevant:
                print(f"  {article['id']} — {article.get('title', '<no title>')}")
        return

    if args.search:
        matches = search_articles(args.search)
        if not matches:
            print(f"No articles found matching '{args.search}'.")
        else:
            print(f"Found {len(matches)} article(s):")
            for article in matches:
                status = article.get("status", "?")
                print(
                    f"  [{status}] {article['id']} — {article.get('title', '<no title>')}"
                )
        return

    total_modified = 0

    for keyword in args.block_keywords:
        block_keyword(keyword)
        total_modified += 1

    for substring in args.block_url_substrings:
        block_url_substring(substring)
        total_modified += 1

    if args.ids:
        print(f"Unpublishing {len(args.ids)} article(s) as {args.tier}:")
        total_modified += unpublish_by_id(args.ids, tier=args.tier)

    if args.urls:
        print(f"Unpublishing {len(args.urls)} article(s) by URL as {args.tier}:")
        total_modified += unpublish_by_url(args.urls, tier=args.tier)

    if (
        total_modified == 0
        and not args.block_keywords
        and not args.block_url_substrings
    ):
        parser.print_help()


if __name__ == "__main__":
    main()
