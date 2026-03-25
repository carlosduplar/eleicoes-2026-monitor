"""Tests for scripts/create_candidates_positions.py."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts import create_candidates_positions as builder


def test_create_candidates_positions_writes_valid_skeleton(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs" / "schemas"
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    candidates_file = data_dir / "candidates.json"
    output_file = data_dir / "candidates_positions.json"
    schema_file = docs_dir / "candidates_positions.schema.json"

    candidates_payload = {
        "candidates": [
            {"slug": "lula"},
            {"slug": "flavio-bolsonaro"},
            {"slug": "zema"},
        ]
    }
    candidates_file.write_text(
        json.dumps(candidates_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    schema_file.write_text(
        Path("docs/schemas/candidates_positions.schema.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(builder, "CANDIDATES_FILE", candidates_file)
    monkeypatch.setattr(builder, "OUTPUT_FILE", output_file)
    monkeypatch.setattr(builder, "SCHEMA_FILE", schema_file)

    builder.main()

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    assert payload["schema_version"] == "2.0.0"
    assert len(payload["topics"]) == 14
    for topic in payload["topics"].values():
        assert set(topic["candidates"].keys()) == {"lula", "flavio-bolsonaro", "zema"}
        for candidate in topic["candidates"].values():
            assert candidate["position_type"] == "unknown"
            assert candidate["stance"] == "unknown"
