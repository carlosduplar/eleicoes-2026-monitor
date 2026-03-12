"""Unit tests for scripts/build_data.py - dedup, limit, sort, schema validation."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts import build_data


def _write_articles(path: Path, articles: list[dict[str, Any]]) -> None:
    payload = {
        "$schema": "../docs/schemas/articles.schema.json",
        "articles": articles,
        "last_updated": "2026-03-11T00:00:00Z",
        "total_count": len(articles),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_articles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        articles = payload.get("articles")
        if isinstance(articles, list):
            return articles
    if isinstance(payload, list):
        return payload
    raise AssertionError(f"Unexpected articles payload in {path}")


def _read_feedback(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_article(
    url: str = "https://example.com/1",
    title: str = "Test",
    source: str = "TestSource",
    published_at: str = "2026-01-01T00:00:00Z",
    status: str = "raw",
    **overrides: Any,
) -> dict[str, Any]:
    """Create a minimal article dict with all required schema fields."""
    article = {
        "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
        "url": url,
        "title": title,
        "source": source,
        "published_at": published_at,
        "collected_at": "2026-03-11T00:00:00Z",
        "status": status,
    }
    article.update(overrides)
    return article


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect build_data paths to tmp_path for isolation."""
    articles_file = tmp_path / "data" / "articles.json"
    feedback_file = tmp_path / "data" / "editor_feedback.json"
    schema_file = tmp_path / "docs" / "schemas" / "articles.schema.json"
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    schema_file.write_text(Path("docs/schemas/articles.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    feedback_file.write_text(
        json.dumps(
            {
                "$schema": "../docs/schemas/editor_feedback.schema.json",
                "updated_at": None,
                "irrelevant_article_ids": [],
                "blocked_title_keywords": [],
                "blocked_url_substrings": [],
                "blocked_sources": [],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(build_data, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(build_data, "SCHEMA_FILE", schema_file)
    monkeypatch.setattr(build_data, "EDITOR_FEEDBACK_FILE", feedback_file)
    return articles_file.parent


def test_dedup_removes_duplicate_ids(data_dir: Path) -> None:
    """Two articles with same URL produce same id; dedup keeps first."""
    articles_file = data_dir / "articles.json"
    duplicate_url = "https://example.com/same"
    _write_articles(
        articles_file,
        [
            _make_article(url=duplicate_url, title="First"),
            _make_article(url=duplicate_url, title="Second"),
        ],
    )

    count, duplicates_removed, trimmed = build_data.consolidate_articles()
    saved = _read_articles(articles_file)

    assert count == 1
    assert duplicates_removed == 1
    assert trimmed == 0
    assert saved[0]["title"] == "First"


def test_dedup_preserves_unique_articles(data_dir: Path) -> None:
    """Articles with different URLs all survive dedup."""
    articles_file = data_dir / "articles.json"
    _write_articles(
        articles_file,
        [
            _make_article(url="https://example.com/a"),
            _make_article(url="https://example.com/b"),
            _make_article(url="https://example.com/c"),
        ],
    )

    count, duplicates_removed, trimmed = build_data.consolidate_articles()
    saved = _read_articles(articles_file)

    assert count == 3
    assert duplicates_removed == 0
    assert trimmed == 0
    assert len(saved) == 3


def test_limit_500_articles(data_dir: Path) -> None:
    """consolidate_articles caps output at 500 entries."""
    articles_file = data_dir / "articles.json"
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    articles = [
        _make_article(
            url=f"https://example.com/{idx}",
            title=f"Article {idx}",
            published_at=(base_time + timedelta(minutes=idx)).isoformat().replace("+00:00", "Z"),
        )
        for idx in range(505)
    ]
    _write_articles(articles_file, articles)

    count, duplicates_removed, trimmed = build_data.consolidate_articles()
    saved = _read_articles(articles_file)

    assert count == 500
    assert duplicates_removed == 0
    assert trimmed == 5
    assert len(saved) == 500


def test_sort_by_published_at_descending(data_dir: Path) -> None:
    """Articles sorted newest-first by published_at."""
    articles_file = data_dir / "articles.json"
    _write_articles(
        articles_file,
        [
            _make_article(url="https://example.com/older", published_at="2026-01-01T00:00:00Z"),
            _make_article(url="https://example.com/newest", published_at="2026-01-03T00:00:00Z"),
            _make_article(url="https://example.com/middle", published_at="2026-01-02T00:00:00Z"),
        ],
    )

    build_data.consolidate_articles()
    saved = _read_articles(articles_file)

    assert [article["url"] for article in saved] == [
        "https://example.com/newest",
        "https://example.com/middle",
        "https://example.com/older",
    ]


def test_schema_validation_warns_on_missing_field(
    data_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing required fields should warn but not crash."""
    articles_file = data_dir / "articles.json"
    invalid_article = _make_article(url="https://example.com/invalid")
    invalid_article.pop("source", None)
    _write_articles(
        articles_file,
        [
            _make_article(url="https://example.com/valid"),
            invalid_article,
        ],
    )

    with caplog.at_level(logging.WARNING):
        count, duplicates_removed, trimmed = build_data.consolidate_articles()

    assert count == 2
    assert duplicates_removed == 0
    assert trimmed == 0
    assert any("Schema validation warning for article" in record.message for record in caplog.records)


def test_idempotent_double_run(data_dir: Path) -> None:
    """Running consolidate_articles twice produces identical output."""
    articles_file = data_dir / "articles.json"
    _write_articles(
        articles_file,
        [
            _make_article(url="https://example.com/a", published_at="2026-01-01T00:00:00Z"),
            _make_article(url="https://example.com/b", published_at="2026-01-02T00:00:00Z"),
        ],
    )

    build_data.consolidate_articles()
    first_output = articles_file.read_text(encoding="utf-8")
    build_data.consolidate_articles()
    second_output = articles_file.read_text(encoding="utf-8")

    assert first_output == second_output


def test_build_data_filters_irrelevant_and_syncs_feedback(data_dir: Path) -> None:
    """Irrelevant articles should be removed from published list and remembered in feedback."""
    articles_file = data_dir / "articles.json"
    feedback_file = data_dir / "editor_feedback.json"
    irrelevant_url = "https://example.com/irrelevant"
    _write_articles(
        articles_file,
        [
            _make_article(url=irrelevant_url, status="irrelevant", title="Receita de bolo"),
            _make_article(url="https://example.com/relevant", status="validated", title="Pesquisa presidencial 2026"),
        ],
    )

    count, duplicates_removed, trimmed = build_data.consolidate_articles()
    saved_articles = _read_articles(articles_file)
    feedback_payload = _read_feedback(feedback_file)

    assert count == 1
    assert duplicates_removed == 0
    assert trimmed == 0
    assert len(saved_articles) == 1
    assert saved_articles[0]["url"] == "https://example.com/relevant"
    assert hashlib.sha256(irrelevant_url.encode("utf-8")).hexdigest()[:16] in feedback_payload["irrelevant_article_ids"]

