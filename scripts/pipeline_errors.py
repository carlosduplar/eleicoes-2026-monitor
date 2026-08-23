"""Shared pipeline-errors storage helpers.

Writers keep their own entry shapes and redaction; this module owns loading,
saving and size rotation so the error log cannot grow without bound.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KEEP_NEWEST = 500
ROTATE_THRESHOLD = 750


def empty_payload() -> dict[str, Any]:
    return {"errors": [], "last_checked": None}


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_payload()
    if not isinstance(payload, dict):
        return empty_payload()
    if not isinstance(payload.get("errors"), list):
        payload["errors"] = []
    return payload


def save_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def archive_dir_for(path: Path) -> Path:
    return path.parent / "archives"


def rotate(
    path: Path,
    *,
    keep: int = KEEP_NEWEST,
    threshold: int = ROTATE_THRESHOLD,
    archive_dir: Path | None = None,
) -> int:
    """Trim errors list to the newest `keep` once it exceeds `threshold`.

    Overflow entries are appended into per-month archive files
    (`archives/errors-YYYY-MM.json`). Returns number of archived entries.
    """
    payload = load_payload(path)
    errors = payload.get("errors")
    if not isinstance(errors, list) or len(errors) <= threshold:
        return 0

    cut = len(errors) - keep
    overflow = errors[:cut]
    payload["errors"] = errors[cut:]

    target_dir = archive_dir if archive_dir is not None else archive_dir_for(path)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in overflow:
        at = entry.get("at") if isinstance(entry, dict) else None
        month = at[:7] if isinstance(at, str) and len(at) >= 7 else "unknown"
        grouped.setdefault(month, []).append(entry)

    target_dir.mkdir(parents=True, exist_ok=True)
    for month, entries in sorted(grouped.items()):
        archive_path = target_dir / f"errors-{month}.json"
        archive_payload = load_payload(archive_path)
        archive_payload["errors"].extend(entries)
        archive_payload["last_checked"] = payload.get("last_checked")
        save_payload(archive_path, archive_payload)

    save_payload(path, payload)
    return len(overflow)
