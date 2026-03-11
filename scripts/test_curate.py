"""Unit tests for scripts/curate.py - skip logic and curation outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts import curate


def _iso_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_articles(path: Path, articles: list[dict[str, Any]]) -> None:
    payload: dict[str, Any] = {"$schema": "../docs/schemas/articles.schema.json", "articles": articles}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected object at {path}")
    return payload


def _validated_article(article_id: str, published_at: str, collected_at: str) -> dict[str, Any]:
    return {
        "id": article_id,
        "url": f"https://example.com/{article_id}",
        "title": "Debate presidencial aquece disputa",
        "source": "Fonte",
        "source_category": "politics",
        "published_at": published_at,
        "collected_at": collected_at,
        "status": "validated",
        "relevance_score": 0.8,
        "candidates_mentioned": ["lula", "tarcisio"],
        "topics": ["economia", "eleicoes"],
        "summaries": {"pt-BR": "Resumo", "en-US": "Summary"},
        "sentiment_score": 0.2,
        "confidence_score": 0.92,
        "edit_history": [{"tier": "editor", "at": published_at, "provider": "provider", "action": "validated"}],
    }


@pytest.fixture
def curate_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect curate.py data paths to tmp_path."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(curate, "DATA_DIR", data_dir)
    monkeypatch.setattr(curate, "ARTICLES_FILE", data_dir / "articles.json")
    monkeypatch.setattr(curate, "CURATED_FEED_FILE", data_dir / "curated_feed.json")
    monkeypatch.setattr(curate, "WEEKLY_BRIEFING_FILE", data_dir / "weekly_briefing.json")
    monkeypatch.setattr(curate, "PIPELINE_ERRORS_FILE", data_dir / "pipeline_errors.json")
    monkeypatch.setattr(curate, "LAST_RUN_FILE", data_dir / ".curate_last_run")
    monkeypatch.setattr(curate.extract_quiz_positions, "main", lambda: None)
    return data_dir


def test_skip_when_last_run_less_than_90_min(curate_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() exits early if .curate_last_run is < 90 minutes old."""
    last_run_file = curate_dir / ".curate_last_run"
    now_epoch = 1_000_000.0
    last_epoch = now_epoch - (curate.MIN_INTERVAL_SECONDS - 60)
    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    last_run_file.write_text(str(last_epoch), encoding="utf-8")
    monkeypatch.setattr(curate.time, "time", lambda: now_epoch)

    with pytest.raises(SystemExit) as exc_info:
        curate.main()

    assert exc_info.value.code == 0
    assert float(last_run_file.read_text(encoding="utf-8")) == last_epoch


def test_run_when_last_run_older_than_90_min(curate_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() proceeds if .curate_last_run is > 90 minutes old."""
    last_run_file = curate_dir / ".curate_last_run"
    now_epoch = 2_000_000.0
    old_epoch = now_epoch - (curate.MIN_INTERVAL_SECONDS + 60)
    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    last_run_file.write_text(str(old_epoch), encoding="utf-8")
    monkeypatch.setattr(curate.time, "time", lambda: now_epoch)

    curate.main()

    assert float(last_run_file.read_text(encoding="utf-8")) == now_epoch
    assert (curate_dir / "curated_feed.json").exists()
    assert (curate_dir / "weekly_briefing.json").exists()


def test_run_when_no_last_run_file(curate_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() proceeds if .curate_last_run does not exist."""
    last_run_file = curate_dir / ".curate_last_run"
    now_epoch = 3_000_000.0
    monkeypatch.setattr(curate.time, "time", lambda: now_epoch)

    curate.main()

    assert last_run_file.exists()
    assert float(last_run_file.read_text(encoding="utf-8")) == now_epoch


def test_last_run_file_updated_after_run(curate_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After successful run, .curate_last_run contains current epoch."""
    last_run_file = curate_dir / ".curate_last_run"
    old_epoch = 100.0
    now_epoch = old_epoch + curate.MIN_INTERVAL_SECONDS + 120.0
    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    last_run_file.write_text(str(old_epoch), encoding="utf-8")
    monkeypatch.setattr(curate.time, "time", lambda: now_epoch)

    curate.main()

    assert float(last_run_file.read_text(encoding="utf-8")) == now_epoch


def test_curate_promotes_high_prominence_article(curate_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validated article with prominence > threshold is promoted to curated."""
    now_epoch = 4_000_000.0
    published = _iso_from_epoch(now_epoch - 300.0)
    collected = _iso_from_epoch(now_epoch - 200.0)
    monkeypatch.setattr(curate.time, "time", lambda: now_epoch)

    articles = [
        _validated_article("aaaaaaaaaaaaaaaa", published, collected),
        {
            "id": "bbbbbbbbbbbbbbbb",
            "url": "https://example.com/raw",
            "title": "Artigo raw",
            "source": "Fonte",
            "published_at": published,
            "collected_at": collected,
            "status": "raw",
        },
    ]
    _write_articles(curate_dir / "articles.json", articles)

    monkeypatch.setattr(curate, "_compute_prominence", lambda article, _now: 0.91 if article["id"] == "aaaaaaaaaaaaaaaa" else 0.1)

    curate.main()

    articles_payload = _read_json(curate_dir / "articles.json")
    updated_articles = articles_payload["articles"]
    promoted_article = next(item for item in updated_articles if item["id"] == "aaaaaaaaaaaaaaaa")

    assert promoted_article["status"] == "curated"
    assert promoted_article["prominence_score"] == 0.91
    assert promoted_article["edit_history"][-1]["tier"] == "editor-chefe"
    assert promoted_article["edit_history"][-1]["action"] == "curated"

    feed_payload = _read_json(curate_dir / "curated_feed.json")
    assert feed_payload["article_count"] == 1
    assert feed_payload["articles"][0]["status"] == "curated"

    briefing_payload = _read_json(curate_dir / "weekly_briefing.json")
    assert briefing_payload["article_count"] == 1


def test_quiz_failure_is_logged_and_outputs_still_written(curate_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quiz extraction failures are logged but do not abort curation outputs."""
    now_epoch = 5_000_000.0
    published = _iso_from_epoch(now_epoch - 400.0)
    collected = _iso_from_epoch(now_epoch - 300.0)
    monkeypatch.setattr(curate.time, "time", lambda: now_epoch)
    _write_articles(curate_dir / "articles.json", [_validated_article("cccccccccccccccc", published, collected)])

    def _boom() -> None:
        raise RuntimeError("quiz refresh boom")

    monkeypatch.setattr(curate.extract_quiz_positions, "main", _boom)
    monkeypatch.setattr(curate, "_compute_prominence", lambda _article, _now: 0.7)

    curate.main()

    errors_payload = _read_json(curate_dir / "pipeline_errors.json")
    assert errors_payload["errors"]
    assert errors_payload["errors"][-1]["tier"] == "editor-chefe"
    assert errors_payload["errors"][-1]["script"] == "curate.py"
    assert "Quiz refresh failed" in errors_payload["errors"][-1]["message"]
    assert (curate_dir / "curated_feed.json").exists()
    assert (curate_dir / "weekly_briefing.json").exists()

