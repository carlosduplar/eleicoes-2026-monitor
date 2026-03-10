from __future__ import annotations

import json
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts import generate_rss_feed

NS_MAP = {"atom": "http://www.w3.org/2005/Atom"}


def _run_generation(monkeypatch: pytest.MonkeyPatch, articles_file: Path, output_dir: Path) -> None:
    monkeypatch.setattr(generate_rss_feed, "ARTICLES_PATH", articles_file)
    monkeypatch.setattr(generate_rss_feed, "OUTPUT_DIR", output_dir)
    generate_rss_feed.main()


def _items_by_guid(feed_path: Path) -> dict[str, ET.Element]:
    root = ET.parse(feed_path).getroot()
    items = root.findall("./channel/item")
    mapped: dict[str, ET.Element] = {}
    for item in items:
        guid = item.findtext("guid")
        if isinstance(guid, str):
            mapped[guid] = item
    return mapped


@pytest.fixture
def sample_articles() -> list[dict]:
    """Return test data with mixed statuses and mixed summary coverage."""
    return [
        {
            "id": "aaaaaaaaaaaaaaaa",
            "url": "https://example.com/news/a",
            "title": "Debate sobre economia em Sao Paulo",
            "published_at": "2026-03-10T10:00:00Z",
            "status": "validated",
            "candidates_mentioned": ["lula"],
            "summaries": {"pt-BR": "Resumo A PT", "en-US": "Summary A EN"},
        },
        {
            "id": "bbbbbbbbbbbbbbbb",
            "url": "https://example.com/news/b",
            "title": "Analise de propostas de seguranca",
            "published_at": "2026-03-10T10:01:00+00:00",
            "status": "validated",
            "candidates_mentioned": ["zema", "caiado"],
            "summaries": {"pt-BR": "", "en-US": "Analysis pending"},
        },
        {
            "id": "cccccccccccccccc",
            "url": "https://example.com/news/c",
            "title": "Cobertura eleitoral com acentuacao: eleições e ação",
            "published_at": "2026-03-10T10:02:00Z",
            "status": "curated",
            "candidates_mentioned": ["tarcisio"],
            "summaries": {"pt-BR": "Resumo C PT", "en-US": "Summary C EN"},
        },
        {
            "id": "dddddddddddddddd",
            "url": "https://example.com/news/d",
            "title": "Artigo nao eleitoral 1",
            "published_at": "2026-03-10T09:00:00Z",
            "status": "raw",
            "summaries": {"pt-BR": "Nao deve entrar", "en-US": "Should be skipped"},
        },
        {
            "id": "eeeeeeeeeeeeeeee",
            "url": "https://example.com/news/e",
            "title": "Artigo nao eleitoral 2",
            "published_at": "2026-03-10T08:00:00Z",
            "status": "raw",
            "summaries": {"pt-BR": "Nao deve entrar", "en-US": "Should be skipped"},
        },
        {
            "id": "ffffffffffffffff",
            "url": "https://example.com/news/f",
            "title": "Sem resumo deve usar titulo",
            "published_at": "2026-03-10T10:03:00Z",
            "status": "validated",
        },
    ]


@pytest.fixture
def articles_file(tmp_path: Path, sample_articles: list[dict]) -> Path:
    """Write sample articles to temporary wrapped articles.json."""
    path = tmp_path / "articles.json"
    payload = {"$schema": "../docs/schemas/articles.schema.json", "articles": sample_articles}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Return temporary output directory for generated feed files."""
    return tmp_path / "public"


def test_feed_xml_is_valid_rss(
    monkeypatch: pytest.MonkeyPatch,
    articles_file: Path,
    output_dir: Path,
) -> None:
    """Output parses as valid RSS 2.0 XML for both feeds."""
    _run_generation(monkeypatch, articles_file, output_dir)

    for filename in ("feed.xml", "feed-en.xml"):
        root = ET.parse(output_dir / filename).getroot()
        assert root.tag == "rss"
        assert root.get("version") == "2.0"
        assert root.find("./channel/title") is not None
        assert root.find("./channel/language") is not None
        atom_links = root.findall("./channel/atom:link", NS_MAP)
        assert len(atom_links) == 1
        assert atom_links[0].get("type") == "application/rss+xml"


def test_feed_limited_to_50_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
) -> None:
    """Generate 60 validated articles and ensure each feed has only 50 items."""
    articles_file = tmp_path / "articles.json"
    many_articles = [
        {
            "id": f"{index:016x}",
            "url": f"https://example.com/many/{index}",
            "title": f"Item {index}",
            "published_at": f"2026-03-10T10:{index % 60:02d}:00Z",
            "status": "validated",
            "summaries": {"pt-BR": f"Resumo {index}", "en-US": f"Summary {index}"},
        }
        for index in range(60)
    ]
    articles_file.write_text(json.dumps(many_articles, indent=2), encoding="utf-8")

    _run_generation(monkeypatch, articles_file, output_dir)

    for filename in ("feed.xml", "feed-en.xml"):
        root = ET.parse(output_dir / filename).getroot()
        assert len(root.findall("./channel/item")) == 50


def test_feed_pt_uses_pt_summaries(
    monkeypatch: pytest.MonkeyPatch,
    articles_file: Path,
    output_dir: Path,
) -> None:
    """feed.xml should use pt-BR summaries and title fallback."""
    _run_generation(monkeypatch, articles_file, output_dir)
    items = _items_by_guid(output_dir / "feed.xml")

    assert items["aaaaaaaaaaaaaaaa"].findtext("description") == "Resumo A PT"
    assert items["bbbbbbbbbbbbbbbb"].findtext("description") == "Analise de propostas de seguranca"
    assert items["ffffffffffffffff"].findtext("description") == "Sem resumo deve usar titulo"


def test_feed_en_uses_en_summaries(
    monkeypatch: pytest.MonkeyPatch,
    articles_file: Path,
    output_dir: Path,
) -> None:
    """feed-en.xml should use en-US summaries and title fallback."""
    _run_generation(monkeypatch, articles_file, output_dir)
    items = _items_by_guid(output_dir / "feed-en.xml")

    assert items["aaaaaaaaaaaaaaaa"].findtext("description") == "Summary A EN"
    assert items["bbbbbbbbbbbbbbbb"].findtext("description") == "Analysis pending"
    assert items["ffffffffffffffff"].findtext("description") == "Sem resumo deve usar titulo"


def test_feed_skips_raw_articles(
    monkeypatch: pytest.MonkeyPatch,
    articles_file: Path,
    output_dir: Path,
) -> None:
    """Articles marked raw should not be present in generated feeds."""
    _run_generation(monkeypatch, articles_file, output_dir)
    raw_ids = {"dddddddddddddddd", "eeeeeeeeeeeeeeee"}

    for filename in ("feed.xml", "feed-en.xml"):
        guids = set(_items_by_guid(output_dir / filename))
        assert guids.isdisjoint(raw_ids)


def test_feed_pubdate_is_rfc2822(
    monkeypatch: pytest.MonkeyPatch,
    articles_file: Path,
    output_dir: Path,
) -> None:
    """All pubDate values must be parseable RFC 2822 timestamps."""
    _run_generation(monkeypatch, articles_file, output_dir)

    for filename in ("feed.xml", "feed-en.xml"):
        root = ET.parse(output_dir / filename).getroot()
        for pub_date_node in root.findall("./channel/item/pubDate"):
            text = pub_date_node.text
            assert isinstance(text, str)
            assert parsedate_to_datetime(text) is not None


def test_idempotent_double_run(
    monkeypatch: pytest.MonkeyPatch,
    articles_file: Path,
    output_dir: Path,
) -> None:
    """Running generator twice should produce byte-identical outputs."""
    _run_generation(monkeypatch, articles_file, output_dir)
    pt_first = (output_dir / "feed.xml").read_bytes()
    en_first = (output_dir / "feed-en.xml").read_bytes()

    _run_generation(monkeypatch, articles_file, output_dir)
    pt_second = (output_dir / "feed.xml").read_bytes()
    en_second = (output_dir / "feed-en.xml").read_bytes()

    assert pt_first == pt_second
    assert en_first == en_second
