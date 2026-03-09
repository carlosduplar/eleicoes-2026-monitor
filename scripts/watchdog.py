"""Watchdog stub for pipeline health output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_HEALTH_FILE = Path("data/pipeline_health.json")


def main() -> None:
    health = {
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "notes": "Watchdog stub - full implementation Phase 16.",
    }
    PIPELINE_HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_HEALTH_FILE.write_text(json.dumps(health, indent=2) + "\n", encoding="utf-8")
    print("Watchdog: pipeline_health.json written.")


if __name__ == "__main__":
    main()
