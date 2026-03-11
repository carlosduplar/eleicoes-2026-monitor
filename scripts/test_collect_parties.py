"""Unit tests for scripts/collect_parties.py - Phase 14."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import requests

import scripts.collect_parties as collect_parties


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_articles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("articles", [])
        if isinstance(items, list):
            return items
    raise AssertionError(f"Unexpected articles payload in {path}")


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Create isolated data files and monkeypatch collector paths."""
    data_dir = tmp_path / "data"
    sources_file = data_dir / "sources.json"
    articles_file = data_dir / "articles.json"
    pipeline_errors_file = data_dir / "pipeline_errors.json"

    _write_json(
        sources_file,
        {
            "rss": [],
            "parties": [
                {
                    "name": "PT",
                    "url": "https://pt.org.br/noticias/",
                    "candidate_slugs": ["lula"],
                    "active": True,
                    "category": "party",
                }
            ],
            "polls": [],
            "social": [],
        },
    )
    _write_json(
        articles_file,
        {
            "$schema": "../docs/schemas/articles.schema.json",
            "articles": [],
            "last_updated": "2026-03-11T00:00:00Z",
            "total_count": 0,
        },
    )
    _write_json(pipeline_errors_file, {"errors": [], "last_checked": None})

    monkeypatch.setattr(collect_parties, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(collect_parties, "DATA_DIR", data_dir)
    monkeypatch.setattr(collect_parties, "SOURCES_FILE", sources_file)
    monkeypatch.setattr(collect_parties, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(collect_parties, "PIPELINE_ERRORS_FILE", pipeline_errors_file)

    return {
        "data_dir": data_dir,
        "sources": sources_file,
        "articles": articles_file,
        "pipeline_errors": pipeline_errors_file,
    }


def test_party_article_id_is_sha256_prefix() -> None:
    """ID = sha256(url.encode('utf-8')).hexdigest()[:16]."""
    url = "https://pt.org.br/noticias/test-article"
    expected = sha256(url.encode("utf-8")).hexdigest()[:16]
    assert collect_parties.build_article_id(url) == expected


def test_party_article_has_candidate_slugs(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Article from PT site has ['lula'] in candidates_mentioned."""

    def fake_get(url: str, timeout: int, headers: dict[str, str]) -> FakeResponse:
        del url, timeout, headers
        html = "<html><body><article><a href='/noticias/test-article'>Teste PT</a></article></body></html>"
        return FakeResponse(html)

    monkeypatch.setattr(collect_parties, "_is_allowed_by_robots", lambda _: True)
    monkeypatch.setattr(collect_parties.requests, "get", fake_get)

    collect_parties.collect_articles()
    articles = _read_articles(isolated_workspace["articles"])
    assert len(articles) == 1
    assert articles[0]["candidates_mentioned"] == ["lula"]


def test_party_article_category_is_party(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """source_category must be 'party' for all party articles."""

    def fake_get(url: str, timeout: int, headers: dict[str, str]) -> FakeResponse:
        del url, timeout, headers
        html = "<html><body><article><a href='/noticias/categoria'>Categoria</a></article></body></html>"
        return FakeResponse(html)

    monkeypatch.setattr(collect_parties, "_is_allowed_by_robots", lambda _: True)
    monkeypatch.setattr(collect_parties.requests, "get", fake_get)

    collect_parties.collect_articles()
    articles = _read_articles(isolated_workspace["articles"])
    assert articles
    assert all(article.get("source_category") == "party" for article in articles)


def test_dedup_skips_existing(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Article already in data/articles.json is skipped."""
    url = "https://pt.org.br/noticias/existing"
    article_id = collect_parties.build_article_id(url)
    _write_json(
        isolated_workspace["articles"],
        {
            "$schema": "../docs/schemas/articles.schema.json",
            "articles": [
                {
                    "id": article_id,
                    "url": url,
                    "title": "Ja existe",
                    "source": "PT",
                    "source_category": "party",
                    "published_at": "2026-03-11T00:00:00Z",
                    "collected_at": "2026-03-11T00:00:00Z",
                    "status": "raw",
                    "relevance_score": None,
                    "candidates_mentioned": ["lula"],
                    "topics": [],
                    "summaries": {"pt-BR": "", "en-US": ""},
                }
            ],
            "last_updated": "2026-03-11T00:00:00Z",
            "total_count": 1,
        },
    )

    def fake_get(url_arg: str, timeout: int, headers: dict[str, str]) -> FakeResponse:
        del url_arg, timeout, headers
        html = "<html><body><article><a href='https://pt.org.br/noticias/existing'>Ja existe</a></article></body></html>"
        return FakeResponse(html)

    monkeypatch.setattr(collect_parties, "_is_allowed_by_robots", lambda _: True)
    monkeypatch.setattr(collect_parties.requests, "get", fake_get)

    new_count, _, _ = collect_parties.collect_articles()
    articles = _read_articles(isolated_workspace["articles"])
    assert new_count == 0
    assert len(articles) == 1


def test_site_failure_does_not_crash(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad URL / network error skips gracefully, logs to pipeline_errors.json."""

    def fake_get(url: str, timeout: int, headers: dict[str, str]) -> FakeResponse:
        del url, timeout, headers
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(collect_parties, "_is_allowed_by_robots", lambda _: True)
    monkeypatch.setattr(collect_parties.requests, "get", fake_get)

    new_count, source_count, error_count = collect_parties.collect_articles()
    error_payload = json.loads(isolated_workspace["pipeline_errors"].read_text(encoding="utf-8"))

    assert new_count == 0
    assert source_count == 1
    assert error_count == 1
    assert isinstance(error_payload.get("errors"), list)
    assert len(error_payload["errors"]) == 1
    assert error_payload["errors"][0]["script"] == "collect_parties.py"


def test_idempotent_double_run(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running collect_articles() twice produces same article count."""

    def fake_get(url: str, timeout: int, headers: dict[str, str]) -> FakeResponse:
        del url, timeout, headers
        html = "<html><body><article><a href='/noticias/idempotent'>Idempotente</a></article></body></html>"
        return FakeResponse(html)

    monkeypatch.setattr(collect_parties, "_is_allowed_by_robots", lambda _: True)
    monkeypatch.setattr(collect_parties.requests, "get", fake_get)

    first_new, _, _ = collect_parties.collect_articles()
    after_first = _read_articles(isolated_workspace["articles"])

    second_new, _, _ = collect_parties.collect_articles()
    after_second = _read_articles(isolated_workspace["articles"])

    ids = [article["id"] for article in after_second]
    assert first_new == 1
    assert second_new == 0
    assert len(after_first) == len(after_second) == 1
    assert len(ids) == len(set(ids))
