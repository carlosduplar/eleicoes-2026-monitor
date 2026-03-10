"""Article scraping pipeline for Phase 03 - fetches article body content."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"

BRIGHTDATA_API_URL = "https://api.brightdata.com/request"
BRIGHTDATA_ZONE = os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1")
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (compatible; eleicoes-2026-monitor/1.0; "
    "+https://github.com/carlosduplar/eleicoes-2026-monitor)"
)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_articles() -> list[dict[str, Any]]:
    if not ARTICLES_FILE.exists():
        return []
    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        articles = payload.get("articles", [])
        return [item for item in articles if isinstance(item, dict)]
    return []


def save_articles(articles: list[dict[str, Any]]) -> None:
    if not ARTICLES_FILE.exists():
        return
    existing = _load_json(ARTICLES_FILE)
    if isinstance(existing, list):
        _save_json(ARTICLES_FILE, articles)
    elif isinstance(existing, dict):
        existing["articles"] = articles
        existing["last_updated"] = utc_now_iso()
        existing["total_count"] = len(articles)
        _save_json(ARTICLES_FILE, existing)


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    selectors = [
        "article",
        "[role='main']",
        "main",
        ".post-content",
        ".article-content",
        ".article-body",
        ".entry-content",
        ".content",
        "#content",
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator=" ", strip=True)
            if len(text) > 100:
                return text
    body = soup.find("body")
    if body:
        return body.get_text(separator=" ", strip=True)  # type: ignore[union-attr]
    return ""


def _fetch_url_brightdata(url: str, api_key: str) -> str:
    """Fetch URL via Bright Data Web Unlocker API. Returns raw HTML."""
    response = requests.post(
        BRIGHTDATA_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"zone": BRIGHTDATA_ZONE, "url": url, "format": "raw", "method": "GET", "direct": True},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def _fetch_url_plain(url: str) -> str:
    """Fallback: plain requests fetch (no bot bypass)."""
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def scrape_articles(limit: int = 100) -> tuple[int, int]:
    articles = load_articles()
    articles_need_content = [
        a for a in articles if not a.get("content") and a.get("status") == "raw"
    ]

    if not articles_need_content:
        print("No articles need content scraping")
        return 0, 0

    articles_need_content = articles_need_content[:limit]
    print(
        f"Processing max {limit} articles (of "
        f"{sum(1 for a in articles if not a.get('content') and a.get('status') == 'raw')} needing content)"
    )

    brightdata_key = os.environ.get("BRIGHTDATA_API_KEY", "").strip()
    if brightdata_key:
        logger.info("Using Bright Data Web Unlocker (zone: %s)", BRIGHTDATA_ZONE)
    else:
        logger.warning("BRIGHTDATA_API_KEY not set — falling back to plain requests (bot-blocked sites will fail)")

    scraped = 0
    errors = 0

    for i, article in enumerate(articles_need_content):
        article_id = article.get("id", "?")
        url = article.get("url", "")
        if not url:
            continue

        try:
            if brightdata_key:
                html = _fetch_url_brightdata(url, brightdata_key)
            else:
                html = _fetch_url_plain(url)

            content = _extract_text_from_html(html)

            if content and len(content) > 50:
                article["content"] = content
                scraped += 1
                print(
                    f"[{i + 1}/{len(articles_need_content)}] Scraped {article_id}: {len(content)} chars"
                )
            else:
                errors += 1
                logger.warning("No content extracted for %s", article_id)
        except Exception as exc:
            errors += 1
            logger.warning("Failed to scrape %s: %s", article_id, exc)

    if scraped > 0:
        save_articles(articles)

    print(f"Scraped {scraped} articles ({errors} errors)")
    return scraped, errors


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Article scraping pipeline")
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=100,
        help="Maximum articles to scrape (default: 100)",
    )
    args = parser.parse_args()
    scrape_articles(limit=args.limit)


if __name__ == "__main__":
    main()
