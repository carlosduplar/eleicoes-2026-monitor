import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts import build_data, collect_rss


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_sources(path: Path, rss_sources: list[dict[str, Any]]) -> None:
    _write_json(path, {"rss": rss_sources, "parties": [], "polls": []})


def _seed_articles(path: Path, articles: list[dict[str, Any]]) -> None:
    _write_json(
        path,
        {
            "$schema": "../docs/schemas/articles.schema.json",
            "articles": articles,
            "last_updated": "2026-03-15T00:00:00Z",
            "total_count": len(articles),
        },
    )


def _seed_editor_feedback(path: Path, payload: dict[str, Any] | None = None) -> None:
    default_payload: dict[str, Any] = {
        "$schema": "../docs/schemas/editor_feedback.schema.json",
        "updated_at": None,
        "irrelevant_article_ids": [],
        "blocked_title_keywords": [],
        "blocked_url_substrings": [],
        "blocked_sources": [],
    }
    if payload:
        default_payload.update(payload)
    _write_json(path, default_payload)


def _read_articles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        articles = payload.get("articles", [])
        if isinstance(articles, list):
            return articles
    raise AssertionError(f"Unexpected articles payload in {path}")


def _article(url: str, published_at: str, title: str = "Title") -> dict[str, Any]:
    return {
        "id": collect_rss.build_article_id(url),
        "url": url,
        "title": title,
        "source": "Example Source",
        "source_category": "mainstream",
        "published_at": published_at,
        "collected_at": "2026-03-15T00:00:00Z",
        "status": "raw",
        "relevance_score": None,
        "candidates_mentioned": [],
        "topics": [],
        "summaries": {"pt-BR": "", "en-US": ""},
    }


@pytest.fixture
def isolated_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    sources_path = tmp_path / "sources.json"
    articles_path = tmp_path / "articles.json"
    feedback_path = tmp_path / "editor_feedback.json"

    monkeypatch.setattr(collect_rss, "SOURCES_FILE", sources_path)
    monkeypatch.setattr(collect_rss, "ARTICLES_FILE", articles_path)
    monkeypatch.setattr(collect_rss, "EDITOR_FEEDBACK_FILE", feedback_path)
    monkeypatch.setattr(build_data, "ARTICLES_FILE", articles_path)
    monkeypatch.setattr(build_data, "EDITOR_FEEDBACK_FILE", feedback_path)

    return sources_path, articles_path, feedback_path


def test_article_id_is_sha256_prefix() -> None:
    url = "https://example.com/noticia"
    expected = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    assert collect_rss.build_article_id(url) == expected


def test_dedup_skips_existing_articles(
    isolated_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources_path, articles_path, feedback_path = isolated_files
    _seed_sources(
        sources_path,
        [{"name": "Source A", "url": "https://feed.example/a.xml", "category": "mainstream", "active": True}],
    )
    _seed_editor_feedback(feedback_path)

    existing_url = "https://news.example/item-1"
    _seed_articles(articles_path, [_article(existing_url, "2026-03-15T10:00:00Z", title="Existing")])

    monkeypatch.setattr(
        collect_rss,
        "fetch_feed_entries",
        lambda _url: [
            {
                "link": existing_url,
                "title": "Existing",
                "published": "Sat, 15 Mar 2026 10:00:00 GMT",
            },
            {
                "link": "https://news.example/item-2",
                "title": "New Item",
                "published": "Sat, 15 Mar 2026 11:00:00 GMT",
            },
        ],
    )

    new_count, source_count, error_count = collect_rss.collect_articles()

    articles = _read_articles(articles_path)
    assert new_count == 1
    assert source_count == 1
    assert error_count == 0
    assert len(articles) == 2
    assert len({article["id"] for article in articles}) == 2


def test_idempotent_double_run(
    isolated_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources_path, articles_path, feedback_path = isolated_files
    _seed_sources(
        sources_path,
        [{"name": "Source A", "url": "https://feed.example/a.xml", "category": "mainstream", "active": True}],
    )
    _seed_articles(articles_path, [])
    _seed_editor_feedback(feedback_path)

    monkeypatch.setattr(
        collect_rss,
        "fetch_feed_entries",
        lambda _url: [
            {
                "link": "https://news.example/item-1",
                "title": "First Item",
                "published": "Sat, 15 Mar 2026 10:00:00 GMT",
            }
        ],
    )

    first_run = collect_rss.collect_articles()
    second_run = collect_rss.collect_articles()

    articles = _read_articles(articles_path)
    assert first_run[0] == 1
    assert second_run[0] == 0
    assert len(articles) == 1


def test_feed_error_does_not_crash(
    isolated_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources_path, articles_path, feedback_path = isolated_files
    _seed_sources(
        sources_path,
        [
            {"name": "Bad Feed", "url": "https://feed.example/bad.xml", "category": "mainstream", "active": True},
            {"name": "Good Feed", "url": "https://feed.example/good.xml", "category": "mainstream", "active": True},
        ],
    )
    _seed_articles(articles_path, [])
    _seed_editor_feedback(feedback_path)

    def fake_fetch(url: str) -> list[dict[str, str]]:
        if "bad.xml" in url:
            raise RuntimeError("network error")
        return [
            {
                "link": "https://news.example/good-item",
                "title": "Good Item",
                "published": "Sat, 15 Mar 2026 10:00:00 GMT",
            }
        ]

    monkeypatch.setattr(collect_rss, "fetch_feed_entries", fake_fetch)
    new_count, source_count, error_count = collect_rss.collect_articles()

    articles = _read_articles(articles_path)
    assert new_count == 1
    assert source_count == 2
    assert error_count == 1
    assert len(articles) == 1


def test_build_data_limits_500(isolated_files: tuple[Path, Path, Path]) -> None:
    _sources_path, articles_path, feedback_path = isolated_files
    _seed_editor_feedback(feedback_path)
    base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    articles = [
        _article(
            url=f"https://news.example/item-{index}",
            published_at=(base_time + timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
            title=f"Item {index}",
        )
        for index in range(550)
    ]
    _seed_articles(articles_path, articles)

    final_count, duplicates_removed, trimmed_count = build_data.consolidate_articles()
    saved_articles = _read_articles(articles_path)

    assert final_count == 500
    assert duplicates_removed == 0
    assert trimmed_count == 50
    assert len(saved_articles) == 500


def test_build_data_sorts_by_date(isolated_files: tuple[Path, Path, Path]) -> None:
    _sources_path, articles_path, feedback_path = isolated_files
    _seed_editor_feedback(feedback_path)
    _seed_articles(
        articles_path,
        [
            _article("https://news.example/older", "2026-03-14T08:00:00Z", title="Older"),
            _article("https://news.example/newest", "2026-03-16T08:00:00Z", title="Newest"),
            _article("https://news.example/middle", "2026-03-15T08:00:00Z", title="Middle"),
        ],
    )

    build_data.consolidate_articles()
    saved_articles = _read_articles(articles_path)

    assert [article["url"] for article in saved_articles] == [
        "https://news.example/newest",
        "https://news.example/middle",
        "https://news.example/older",
    ]


def test_collect_skips_urls_flagged_in_editor_feedback(
    isolated_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources_path, articles_path, feedback_path = isolated_files
    _seed_sources(
        sources_path,
        [{"name": "Source A", "url": "https://feed.example/a.xml", "category": "mainstream", "active": True}],
    )
    _seed_articles(articles_path, [])

    blocked_url = "https://news.example/blocked-item"
    _seed_editor_feedback(
        feedback_path,
        payload={
            "irrelevant_article_ids": [collect_rss.build_article_id(blocked_url)],
        },
    )

    monkeypatch.setattr(
        collect_rss,
        "fetch_feed_entries",
        lambda _url: [
            {
                "link": blocked_url,
                "title": "Blocked item",
                "published": "Sat, 15 Mar 2026 10:00:00 GMT",
            },
            {
                "link": "https://news.example/allowed-item",
                "title": "Allowed item",
                "published": "Sat, 15 Mar 2026 11:00:00 GMT",
            },
        ],
    )

    new_count, source_count, error_count = collect_rss.collect_articles()
    articles = _read_articles(articles_path)

    assert new_count == 1
    assert source_count == 1
    assert error_count == 0
    assert len(articles) == 1
    assert articles[0]["url"] == "https://news.example/allowed-item"


def test_collect_marks_near_duplicate_at_ingestion(
    isolated_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources_path, articles_path, feedback_path = isolated_files
    _seed_sources(
        sources_path,
        [{"name": "Source A", "url": "https://feed.example/a.xml", "category": "mainstream", "active": True}],
    )
    _seed_editor_feedback(feedback_path)

    existing_url = "https://news.example/existing-item"
    _seed_articles(
        articles_path,
        [
            _article(
                existing_url,
                "2026-03-15T10:00:00Z",
                title="Caiado critica impostos em debate",
            )
        ],
    )

    monkeypatch.setattr(
        collect_rss,
        "fetch_feed_entries",
        lambda _url: [
            {
                "link": "https://news.example/new-item",
                "title": "Caiado critica impostos em debate televisivo",
                "published": "Sat, 15 Mar 2026 10:30:00 GMT",
            }
        ],
    )

    new_count, source_count, error_count = collect_rss.collect_articles()
    articles = _read_articles(articles_path)
    added = next(a for a in articles if a["url"] == "https://news.example/new-item")

    assert new_count == 1
    assert source_count == 1
    assert error_count == 0
    assert added["status"] == "irrelevant"
    assert isinstance(added.get("narrative_cluster_id"), str)
    assert added.get("editor_note") == "near-duplicate detected at ingestion"
