"""Sync-telemetry aggregation contract (M6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import watchdog


def _iso(reference: datetime, **delta) -> str:
    return (
        (reference - timedelta(**delta))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@pytest.fixture
def patched_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "sync_log.jsonl"
    monkeypatch.setattr(watchdog, "SYNC_LOG_FILE", log)
    return log


def test_aggregates_windows(patched_log: Path) -> None:
    now = datetime.now(timezone.utc)
    patched_log.write_text(
        "\n".join(
            [
                json_line(_iso(now, hours=2), "collect", 1, "pushed", 2, 0),
                json_line(_iso(now, hours=5), "validate", 2, "failed", 0, 3),
                json_line(_iso(now, days=30), "collect", 1, "pushed", 9, 4),
            ]
        )
        + "\n"
        + "not-json-at-all\n",
        encoding="utf-8",
    )

    summary = watchdog._summarize_sync_log(now)

    assert summary["exists"] is True
    assert summary["pushes_24h"] == 1
    assert summary["failed_attempts_24h"] == 1
    assert summary["conflicts_resolved_7d"] == 2
    assert summary["discarded_theirs_7d"] == 3
    assert summary["discarded_events_7d"] == 1


def test_discarded_outside_week_is_ignored(patched_log: Path) -> None:
    now = datetime.now(timezone.utc)
    patched_log.write_text(
        json_line(_iso(now, days=10), "curate", 1, "pushed", 5, 7) + "\n",
        encoding="utf-8",
    )

    summary = watchdog._summarize_sync_log(now)

    assert summary["discarded_theirs_7d"] == 0
    assert summary["discarded_events_7d"] == 0
    assert summary["conflicts_resolved_7d"] == 0


def test_missing_log_is_tolerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(watchdog, "SYNC_LOG_FILE", tmp_path / "absent.jsonl")
    summary = watchdog._summarize_sync_log(datetime.now(timezone.utc))
    assert summary["exists"] is False
    assert summary["pushes_24h"] == 0


def json_line(at: str, workflow: str, attempt: int, outcome: str,
              conflicts: int, discarded: int) -> str:
    import json

    return json.dumps(
        {
            "at": at,
            "workflow": workflow,
            "attempt": attempt,
            "outcome": outcome,
            "conflicts_resolved": conflicts,
            "discarded_theirs": discarded,
        }
    )
