"""Unit tests for scripts/curate.py - 90-minute skip logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import curate


@pytest.fixture
def curate_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect curate.py data path to tmp_path."""
    last_run_file = tmp_path / "data" / ".curate_last_run"
    monkeypatch.setattr(curate, "LAST_RUN_FILE", last_run_file)
    return last_run_file.parent


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

