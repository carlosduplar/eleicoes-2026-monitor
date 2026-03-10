"""Generate pt-BR and en-US RSS 2.0 feeds from collected election articles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path
from typing import Any, NotRequired, TypedDict
from xml.etree.ElementTree import Element, ElementTree, SubElement, register_namespace

# --- Constants ---

SITE_URL: str = "https://eleicoes2026.com.br"
ARTICLES_PATH: Path = Path("data/articles.json")
OUTPUT_DIR: Path = Path("site/public")
FEED_PT_FILENAME: str = "feed.xml"
FEED_EN_FILENAME: str = "feed-en.xml"
MAX_ITEMS: int = 50
ATOM_NS: str = "http://www.w3.org/2005/Atom"
VALID_STATUSES: frozenset[str] = frozenset({"validated", "curated"})

# --- Channel metadata per language ---

ChannelMeta = dict[str, str]

CHANNEL_PT: ChannelMeta = {
    "title": "Eleicoes BR 2026",
    "link": SITE_URL,
    "description": "Monitoramento em tempo real das eleicoes presidenciais brasileiras de 2026.",
    "language": "pt-BR",
    "feed_filename": FEED_PT_FILENAME,
}

CHANNEL_EN: ChannelMeta = {
    "title": "Brazil Elections 2026",
    "link": SITE_URL,
    "description": "Real-time monitoring of the 2026 Brazilian presidential elections.",
    "language": "en-US",
    "feed_filename": FEED_EN_FILENAME,
}


class ArticleSummaries(TypedDict, total=False):
    """Mirrors Article.summaries from docs/schemas/types.ts."""

    pt_BR: str
    en_US: str


class ArticleDict(TypedDict):
    """Subset of Article fields consumed by RSS generation."""

    id: str
    url: str
    title: str
    published_at: str
    status: str
    candidates_mentioned: NotRequired[list[str]]
    summaries: NotRequired[dict[str, str]]


def _parse_iso8601(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_articles(path: Path) -> list[dict[str, Any]]:
    """Read and parse data/articles.json.

    Supports a bare array payload or object wrappers containing an articles array.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        articles = payload.get("articles")
        if isinstance(articles, list):
            return [item for item in articles if isinstance(item, dict)]

        for value in payload.values():
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise ValueError(f"Unsupported articles structure in {path}")


def filter_and_sort(articles: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    """Keep validated/curated, sort by published_at desc, and cap length."""
    eligible = [article for article in articles if article.get("status") in VALID_STATUSES]
    eligible.sort(key=lambda article: _parse_iso8601(article.get("published_at")), reverse=True)
    return eligible[:max_items]


def format_pub_date(iso_date: str) -> str:
    """Convert ISO 8601 into RFC 2822 date format."""
    parsed = _parse_iso8601(iso_date)
    return formatdate(parsed.timestamp(), usegmt=True)


def get_summary(article: dict[str, Any], lang_key: str) -> str:
    """Return summaries[lang_key] when non-empty, else fallback to title."""
    summaries = article.get("summaries")
    if isinstance(summaries, dict):
        summary_value = summaries.get(lang_key)
        if isinstance(summary_value, str):
            cleaned = summary_value.strip()
            if cleaned:
                return cleaned

    title_value = article.get("title")
    return title_value.strip() if isinstance(title_value, str) else ""


def build_feed_xml(articles: list[dict[str, Any]], channel: ChannelMeta) -> ElementTree:
    """Build RSS 2.0 XML tree with an Atom self link and language-specific descriptions."""
    register_namespace("atom", ATOM_NS)

    rss = Element("rss", {"version": "2.0"})
    channel_element = SubElement(rss, "channel")
    SubElement(channel_element, "title").text = channel["title"]
    SubElement(channel_element, "link").text = channel["link"]
    SubElement(channel_element, "description").text = channel["description"]
    SubElement(channel_element, "language").text = channel["language"]
    SubElement(
        channel_element,
        f"{{{ATOM_NS}}}link",
        {
            "href": f"{SITE_URL}/{channel['feed_filename']}",
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    lang_key = "pt-BR" if channel["language"] == "pt-BR" else "en-US"
    for article in articles:
        item = SubElement(channel_element, "item")
        SubElement(item, "title").text = article.get("title", "")
        SubElement(item, "link").text = article.get("url", "")
        SubElement(item, "description").text = get_summary(article, lang_key)
        SubElement(item, "pubDate").text = format_pub_date(str(article.get("published_at", "")))
        SubElement(item, "guid", {"isPermaLink": "false"}).text = str(article.get("id", ""))

        candidates = article.get("candidates_mentioned")
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, str) and candidate.strip():
                    SubElement(item, "category").text = candidate.strip()

    return ElementTree(rss)


def write_feed(tree: ElementTree, output_path: Path) -> None:
    """Write XML text with declaration, creating output folders when needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        tree.write(handle, encoding="unicode", xml_declaration=True)


def main() -> None:
    """Generate pt-BR and en-US RSS feed files from latest eligible articles."""
    articles = load_articles(ARTICLES_PATH)
    selected = filter_and_sort(articles, MAX_ITEMS)

    pt_tree = build_feed_xml(selected, CHANNEL_PT)
    en_tree = build_feed_xml(selected, CHANNEL_EN)

    write_feed(pt_tree, OUTPUT_DIR / FEED_PT_FILENAME)
    write_feed(en_tree, OUTPUT_DIR / FEED_EN_FILENAME)

    print(f"Generated {FEED_PT_FILENAME} ({len(selected)} items) and {FEED_EN_FILENAME} ({len(selected)} items)")


if __name__ == "__main__":
    main()
