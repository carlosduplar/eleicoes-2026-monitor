"""Central filesystem locations for pipeline scripts.

Single source of truth for repository paths. Modules re-export these as
module-level names so existing monkeypatch targets keep working.
"""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PUB_DATA_DIR = ROOT_DIR / "site" / "public" / "data"
STATE_DIR = ROOT_DIR / "state"
SCHEMAS_DIR = ROOT_DIR / "docs" / "schemas"
