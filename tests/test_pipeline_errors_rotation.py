"""Rotation contract for the shared pipeline-errors store (M5)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.pipeline_errors import load_payload, rotate, save_payload


def _seed(path: Path, count: int, start_month: int = 1) -> None:
    payload = {
        "errors": [
            {"at": f"2026-{start_month + i // 100:02d}-{(i % 28) + 1:02d}T00:00:00Z", "n": i}
            for i in range(count)
        ],
        "last_checked": "2026-05-01T00:00:00Z",
    }
    save_payload(path, payload)


def test_below_threshold_is_noop(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_errors.json"
    _seed(path, 700)
    assert rotate(path) == 0
    assert len(load_payload(path)["errors"]) == 700


def test_rotates_to_keep_newest_and_archives_overflow_by_month(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_errors.json"
    _seed(path, 800)  # months 1-8, 100 entries per month

    archived = rotate(path)

    assert archived == 300
    errors = load_payload(path)["errors"]
    assert len(errors) == 500
    assert errors[0]["n"] == 300 and errors[-1]["n"] == 799

    archive_dir = tmp_path / "archives"
    files = sorted(p.name for p in archive_dir.glob("errors-*.json"))
    assert files == [
        "errors-2026-01.json",
        "errors-2026-02.json",
        "errors-2026-03.json",
    ]
    counts = [
        len(json.loads((archive_dir / name).read_text(encoding="utf-8"))["errors"])
        for name in files
    ]
    assert counts == [100, 100, 100]
    first_archived = json.loads(
        (archive_dir / "errors-2026-01.json").read_text(encoding="utf-8")
    )["errors"][0]
    assert first_archived["n"] == 0


def test_rotation_appends_to_existing_archive(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_errors.json"
    _seed(path, 800)
    rotate(path)

    payload = load_payload(path)
    payload["errors"].extend(
        [{"at": "2026-01-15T00:00:00Z", "n": 900 + i} for i in range(400)]
    )
    save_payload(path, payload)

    archived = rotate(path)

    # Rotation drops the oldest tail by list position: entries n=300..699
    # (originally archived months 2026-04..2026-06 region) move out; the
    # 400 freshly appended entries stay as the newest tail.
    assert archived == 400
    assert len(load_payload(path)["errors"]) == 500
    archive_dir = tmp_path / "archives"
    totals = sum(
        len(json.loads(p.read_text(encoding="utf-8"))["errors"])
        for p in archive_dir.glob("errors-*.json")
    )
    assert totals == 700
    january = json.loads(
        (archive_dir / "errors-2026-01.json").read_text(encoding="utf-8")
    )["errors"]
    assert len(january) == 100  # untouched second pass; appended entries were kept
    assert [e["n"] for e in load_payload(path)["errors"]][:1] == [700]


def test_entries_without_timestamp_land_in_unknown_bucket(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_errors.json"
    save_payload(
        path,
        {"errors": [{"msg": f"e{i}", "at": None} for i in range(800)], "last_checked": None},
    )

    assert rotate(path) == 300
    unknown = json.loads(
        (tmp_path / "archives" / "errors-unknown.json").read_text(encoding="utf-8")
    )
    assert len(unknown["errors"]) == 300
