"""Party website collection pipeline for Phase 14."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
ARTICLES_FILE = DATA_DIR / "articles.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"

REQUEST_TIMEOUT_SECONDS = 20
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
    """Return sha256(url.encode('utf-8')).hexdigest()[:16]."""
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
    """Load pipeline errors from data/pipeline_errors.json."""
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


def _append_pipeline_error(*, party_name: str, party_url: str, message: str) -> None:
    """Append error entry with tier='foca', script='collect_parties.py'."""
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": utc_now_iso(),
            "tier": "foca",
            "script": "collect_parties.py",
            "party_name": party_name,
            "party_url": party_url,
            "message": message,
        }
    )
    payload["last_checked"] = utc_now_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_active_party_sources() -> list[dict[str, Any]]:
    """Read active party sources from data/sources.json['parties']."""
    payload = _load_json(SOURCES_FILE)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {SOURCES_FILE}")

    parties = payload.get("parties", [])
    if not isinstance(parties, list):
        raise ValueError(f"Expected 'parties' array in {SOURCES_FILE}")

    active_sources: list[dict[str, Any]] = []
    for source in parties:
        if not isinstance(source, dict) or not source.get("active", False):
            continue

        name = source.get("name")
        url = source.get("url")
        category = source.get("category")
        candidate_slugs = source.get("candidate_slugs")

        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(url, str) or not url.strip():
            continue
        if not isinstance(candidate_slugs, list):
            continue

        cleaned_slugs = [slug.strip() for slug in candidate_slugs if isinstance(slug, str) and slug.strip()]
        if not cleaned_slugs:
            continue

        party: dict[str, Any] = {
            "name": name.strip(),
            "url": url.strip(),
            "candidate_slugs": cleaned_slugs,
            "category": category.strip() if isinstance(category, str) and category.strip() else "party",
        }
        robots_txt_url = source.get("robots_txt_url")
        if isinstance(robots_txt_url, str) and robots_txt_url.strip():
            party["robots_txt_url"] = robots_txt_url.strip()
        active_sources.append(party)
    return active_sources


def _is_allowed_by_robots_url(site_url: str, robots_url: str) -> bool:
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = requests.get(robots_url, timeout=5, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        parser.parse(response.text.splitlines())
        return parser.can_fetch(USER_AGENT, site_url)
    except requests.RequestException as exc:
        logger.warning("Could not fetch robots.txt (%s): %s. Continuing.", robots_url, exc)
        return True


def _is_allowed_by_robots(site_url: str) -> bool:
    """Check if our User-Agent can crawl the given URL per robots.txt."""
    parsed = urlparse(site_url)
    if not parsed.scheme or not parsed.netloc:
        return True
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    return _is_allowed_by_robots_url(site_url, robots_url)


def _normalize_title(value: str) -> str:
    return " ".join(value.split()).strip()


def _append_unique_article(
    *,
    results: list[dict[str, str]],
    seen_urls: set[str],
    base_url: str,
    raw_url: str,
    raw_title: str,
) -> None:
    clean_url = raw_url.strip()
    clean_title = _normalize_title(raw_title)
    if not clean_url or not clean_title:
        return
    resolved_url = urljoin(base_url, clean_url)
    if not resolved_url or resolved_url in seen_urls:
        return
    seen_urls.add(resolved_url)
    results.append({"url": resolved_url, "title": clean_title})


def _extract_articles_jsonld(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract articles from JSON-LD NewsArticle blocks."""
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    def walk_nodes(node: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                output.append(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(node)
        return output

    def article_type_matches(value: Any) -> bool:
        if isinstance(value, str):
            lowered = value.lower()
            return lowered in {"newsarticle", "article"}
        if isinstance(value, list):
            return any(isinstance(item, str) and item.lower() in {"newsarticle", "article"} for item in value)
        return False

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for node in walk_nodes(parsed):
            if not article_type_matches(node.get("@type")):
                continue

            raw_url = node.get("url")
            if not isinstance(raw_url, str):
                main_entity = node.get("mainEntityOfPage")
                if isinstance(main_entity, str):
                    raw_url = main_entity
                elif isinstance(main_entity, dict):
                    candidate_url = main_entity.get("@id") or main_entity.get("url")
                    if isinstance(candidate_url, str):
                        raw_url = candidate_url

            raw_title = node.get("headline")
            if not isinstance(raw_title, str):
                maybe_title = node.get("name")
                if isinstance(maybe_title, str):
                    raw_title = maybe_title

            if isinstance(raw_url, str) and isinstance(raw_title, str):
                _append_unique_article(
                    results=results,
                    seen_urls=seen_urls,
                    base_url=base_url,
                    raw_url=raw_url,
                    raw_title=raw_title,
                )

    return results


def _extract_articles_opengraph(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract article URL+title from Open Graph meta tags."""
    title_meta = soup.find("meta", attrs={"property": "og:title"})
    url_meta = soup.find("meta", attrs={"property": "og:url"})

    raw_title = title_meta.get("content") if title_meta and title_meta.has_attr("content") else None
    raw_url = url_meta.get("content") if url_meta and url_meta.has_attr("content") else None

    if not isinstance(raw_title, str) or not isinstance(raw_url, str):
        return []

    results: list[dict[str, str]] = []
    _append_unique_article(
        results=results,
        seen_urls=set(),
        base_url=base_url,
        raw_url=raw_url,
        raw_title=raw_title,
    )
    return results


def _extract_articles_html(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract article links by traversing HTML structure."""
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for article in soup.find_all("article"):
        for link in article.find_all("a", href=True):
            text = link.get_text(" ", strip=True)
            _append_unique_article(
                results=results,
                seen_urls=seen_urls,
                base_url=base_url,
                raw_url=link["href"],
                raw_title=text,
            )

    for heading in soup.find_all(["h2", "h3"]):
        link = heading.find("a", href=True)
        if link is None:
            continue
        text = link.get_text(" ", strip=True) or heading.get_text(" ", strip=True)
        _append_unique_article(
            results=results,
            seen_urls=seen_urls,
            base_url=base_url,
            raw_url=link["href"],
            raw_title=text,
        )

    news_pattern = re.compile(r"/(noticias?|news|20\d{2}/)", re.IGNORECASE)
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not isinstance(href, str) or not news_pattern.search(href):
            continue
        text = link.get_text(" ", strip=True)
        _append_unique_article(
            results=results,
            seen_urls=seen_urls,
            base_url=base_url,
            raw_url=href,
            raw_title=text,
        )

    return results


def _extract_articles_heading_fallback(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Last resort: first <h1> or <h2> + canonical link or base_url."""
    heading = soup.find(["h1", "h2"])
    if heading is None:
        return []

    title = heading.get_text(" ", strip=True)
    canonical = soup.find("link", attrs={"rel": "canonical"})
    raw_url = canonical.get("href") if canonical and canonical.has_attr("href") else base_url

    if not isinstance(raw_url, str):
        return []

    results: list[dict[str, str]] = []
    _append_unique_article(
        results=results,
        seen_urls=set(),
        base_url=base_url,
        raw_url=raw_url,
        raw_title=title,
    )
    return results


def extract_articles_from_html(html: str, base_url: str) -> list[dict[str, str]]:
    """Apply extraction fallback ladder and return unique URL+title pairs."""
    soup = BeautifulSoup(html, "lxml")
    for extractor in (
        _extract_articles_jsonld,
        _extract_articles_opengraph,
        _extract_articles_html,
        _extract_articles_heading_fallback,
    ):
        extracted = extractor(soup, base_url)
        if extracted:
            return extracted
    return []


def scrape_party_site(party: dict[str, Any]) -> list[dict[str, str]]:
    """Fetch a single party website and extract article URL+title pairs."""
    party_name = str(party.get("name", "")).strip()
    party_url = str(party.get("url", "")).strip()
    if not party_name or not party_url:
        return []

    robots_override = party.get("robots_txt_url")
    if isinstance(robots_override, str) and robots_override.strip():
        allowed = _is_allowed_by_robots_url(party_url, robots_override.strip())
    else:
        allowed = _is_allowed_by_robots(party_url)
    if not allowed:
        logger.warning("Robots.txt disallows crawling %s (%s)", party_name, party_url)
        return []

    response = requests.get(
        party_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    articles = extract_articles_from_html(response.text, party_url)
    if not articles:
        logger.warning("No articles extracted from %s (%s)", party_name, party_url)
    return articles


def collect_articles() -> tuple[int, int, int]:
    """Collect new party articles and append to data/articles.json."""
    sources = load_active_party_sources()
    document = _load_articles_document()
    existing_ids = {
        article_id
        for article in document.articles
        for article_id in [article.get("id")]
        if isinstance(article_id, str)
    }

    new_articles: list[dict[str, Any]] = []
    error_count = 0

    for party in sources:
        party_name = str(party.get("name", "")).strip()
        party_url = str(party.get("url", "")).strip()
        try:
            extracted = scrape_party_site(party)
        except Exception as exc:
            error_count += 1
            _append_pipeline_error(party_name=party_name, party_url=party_url, message=str(exc))
            logger.warning("Failed to collect from %s (%s): %s", party_name, party_url, exc)
            continue

        for entry in extracted:
            article_url = entry.get("url")
            title = entry.get("title")
            if not isinstance(article_url, str) or not isinstance(title, str):
                continue

            article_id = build_article_id(article_url)
            if article_id in existing_ids:
                continue

            now_iso = utc_now_iso()
            article = {
                "id": article_id,
                "url": article_url,
                "title": title,
                "source": party_name,
                "source_category": "party",
                "published_at": now_iso,
                "collected_at": now_iso,
                "status": "raw",
                "relevance_score": None,
                "candidates_mentioned": list(party.get("candidate_slugs", [])),
                "topics": [],
                "summaries": {"pt-BR": "", "en-US": ""},
            }
            new_articles.append(article)
            existing_ids.add(article_id)

    if new_articles:
        document.articles.extend(new_articles)
        _save_articles_document(document)
    elif not ARTICLES_FILE.exists():
        _save_articles_document(document)

    print(f"Parties: {len(new_articles)} new articles from {len(sources)} sources ({error_count} errors)")
    return len(new_articles), len(sources), error_count


def main() -> None:
    """Entry point: configure logging, call collect_articles()."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_articles()


if __name__ == "__main__":
    main()
