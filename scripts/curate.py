"""Curate pipeline stub with 90-minute skip logic for Phase 05."""

from __future__ import annotations

import time
from pathlib import Path

LAST_RUN_FILE = Path("data/.curate_last_run")
MIN_INTERVAL_SECONDS = 90 * 60


def _read_last_run_epoch() -> float:
    if not LAST_RUN_FILE.exists():
        return 0.0
    raw_value = LAST_RUN_FILE.read_text(encoding="utf-8").strip()
    if not raw_value:
        return 0.0
    try:
        return float(raw_value)
    except ValueError:
        return 0.0


def main() -> None:
    last_run_epoch = _read_last_run_epoch()
    now_epoch = time.time()
    elapsed = now_epoch - last_run_epoch
    if elapsed < MIN_INTERVAL_SECONDS:
        print(f"Skipping: only {elapsed / 60:.1f} min since last run (minimum: 90 min)")
        raise SystemExit(0)

    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(str(now_epoch), encoding="utf-8")
    print("Curate stub: full implementation in Phase 06.")


if __name__ == "__main__":
    main()
