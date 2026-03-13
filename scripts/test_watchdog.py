"""Unit tests for scripts/watchdog.py - health JSON structure."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts import watchdog


@pytest.fixture
def watchdog_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect watchdog.py output path to tmp_path."""
    health_file = tmp_path / "data" / "pipeline_health.json"
    monkeypatch.setattr(watchdog, "PIPELINE_HEALTH_FILE", health_file)
    return health_file.parent


def _read_health(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("pipeline_health.json should contain an object")
    return payload


def test_health_json_has_required_keys(watchdog_dir: Path) -> None:
    """pipeline_health.json must have: checked_at, workflows, status."""
    health_file = watchdog_dir / "pipeline_health.json"
    watchdog.main()
    payload = _read_health(health_file)

    assert "checked_at" in payload
    assert "workflows" in payload
    assert "status" in payload
    assert isinstance(payload["workflows"], dict)
    assert isinstance(payload["status"], str)


def test_health_json_checked_at_is_iso8601(watchdog_dir: Path) -> None:
    """checked_at field is valid ISO 8601 string."""
    health_file = watchdog_dir / "pipeline_health.json"
    watchdog.main()
    payload = _read_health(health_file)

    checked_at = payload.get("checked_at")
    assert isinstance(checked_at, str)
    parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_health_json_is_valid_json(watchdog_dir: Path) -> None:
    """Output file is parseable JSON, not empty."""
    health_file = watchdog_dir / "pipeline_health.json"
    watchdog.main()

    raw_text = health_file.read_text(encoding="utf-8").strip()
    assert raw_text
    payload = json.loads(raw_text)
    assert isinstance(payload, dict)


def test_idempotent_double_run(watchdog_dir: Path) -> None:
    """Running main() twice produces valid JSON (no append corruption)."""
    health_file = watchdog_dir / "pipeline_health.json"

    watchdog.main()
    first_payload = _read_health(health_file)
    watchdog.main()
    second_payload = _read_health(health_file)

    assert isinstance(first_payload, dict)
    assert isinstance(second_payload, dict)
    assert "workflows" in second_payload


def test_watchdog_warns_on_zero_relevance_scores(
    watchdog_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health_file = watchdog_dir / "pipeline_health.json"
    articles_file = watchdog_dir / "articles.json"
    articles_file.parent.mkdir(parents=True, exist_ok=True)
    articles_file.write_text(
        json.dumps(
            {
                "articles": [
                    {
                        "id": "aaaaaaaaaaaaaaaa",
                        "status": "validated",
                        "relevance_score": 0.0,
                        "collected_at": "2026-03-15T10:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(watchdog, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(watchdog, "WORKFLOW_TARGETS", {})

    watchdog.main()
    payload = _read_health(health_file)

    assert payload["status"] == "warning"
    relevance = payload.get("relevance_health")
    assert isinstance(relevance, dict)
    assert relevance.get("zero_relevance_count") == 1

