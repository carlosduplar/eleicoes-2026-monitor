"""Article scraping pipeline for Phase 03 - fetches article body content."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"

REQUEST_TIMEOUT_SECONDS = 20000
USER_AGENT = (
    "eleicoes-2026-monitor/1.0 (+https://github.com/carlosduplar/eleicoes-2026-monitor)"
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


def extract_text_from_page(page: Any) -> str:
    selectors = [
        "article",
        "[role='main']",
        "main",
        ".post-content",
        ".article-content",
        ".entry-content",
        ".content",
        "#content",
    ]
    for selector in selectors:
        try:
            element = page.query_selector(selector)
            if element:
                text = element.inner_text()
                if text and len(text.strip()) > 100:
                    return text.strip()
        except Exception:
            continue
    try:
        body = page.query_selector("body")
        if body:
            return body.inner_text().strip()
    except Exception:
        pass
    return ""


def scrape_articles() -> tuple[int, int]:
    articles = load_articles()
    articles_need_content = [
        a for a in articles if not a.get("content") and a.get("status") == "raw"
    ]

    if not articles_need_content:
        print("No articles need content scraping")
        return 0, 0

    scraped = 0
    errors = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)

        for i, article in enumerate(articles_need_content):
            article_id = article.get("id", "?")
            url = article.get("url", "")
            if not url:
                continue

            try:
                page = context.new_page()
                page.goto(
                    url, timeout=REQUEST_TIMEOUT_SECONDS, wait_until="domcontentloaded"
                )
                content = extract_text_from_page(page)
                page.close()

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
                continue

        context.close()
        browser.close()

    if scraped > 0:
        save_articles(articles)

    print(f"Scraped {scraped} articles ({errors} errors)")
    return scraped, errors


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    scrape_articles()


if __name__ == "__main__":
    main()
