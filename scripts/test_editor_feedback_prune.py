"""Retention pruning for editor_feedback.json (migration step M8).

Properties under test:
  - rule lists (keywords/url substrings/sources) survive pruning untouched
  - fresh IDs survive; IDs idle past max_age_days are pruned
  - legacy entries without timestamps get stamped, never dropped in one shot
  - pruning never grows the ID list
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from scripts import editor_feedback

SCHEMA_PATH = Path("docs/schemas/editor_feedback.schema.json")
NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _payload(
    ids: list[str],
    meta: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "$schema": editor_feedback.DEFAULT_SCHEMA_PATH,
        "updated_at": "2026-08-23T12:00:00Z",
        "irrelevant_article_ids": list(ids),
        "irrelevant_article_ids_meta": dict(meta or {}),
        "blocked_title_keywords": ["fake news"],
        "blocked_url_substrings": ["spam.example.com"],
        "blocked_sources": ["Fonte Duvidosa"],
    }


def _prune(feedback: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return editor_feedback.prune_editor_feedback(feedback, now=NOW)


def test_rules_survive_prune() -> None:
    feedback = _payload(["a" * 16])
    pruned, removed = _prune(feedback)
    assert removed == 0
    assert pruned["irrelevant_article_ids"] == ["a" * 16]
    assert pruned["blocked_title_keywords"] == ["fake news"]
    assert pruned["blocked_url_substrings"] == ["spam.example.com"]
    assert pruned["blocked_sources"] == ["fonte duvidosa"]
    assert set(pruned["irrelevant_article_ids_meta"]) == {"a" * 16}


def test_fresh_entries_survive_stale_pruned() -> None:
    stale_id, fresh_id, boundary_id = "b" * 16, "c" * 16, "d" * 16
    meta = {
        stale_id: _iso(NOW - timedelta(days=91)),
        fresh_id: _iso(NOW - timedelta(days=1)),
        boundary_id: _iso(NOW - timedelta(days=90)),
    }
    pruned, removed = _prune(_payload([stale_id, fresh_id, boundary_id], meta))
    assert removed == 1
    assert pruned["irrelevant_article_ids"] == sorted([fresh_id, boundary_id])
    assert stale_id not in pruned["irrelevant_article_ids_meta"]
    assert pruned["irrelevant_article_ids_meta"][fresh_id] == meta[fresh_id]
    assert pruned["irrelevant_article_ids_meta"][boundary_id] == meta[boundary_id]


def test_legacy_entries_stamped_not_dropped() -> None:
    ids = ["e" * 16, "f" * 16]
    pruned, removed = _prune(_payload(ids))
    assert removed == 0
    assert pruned["irrelevant_article_ids"] == ids
    stamped = pruned["irrelevant_article_ids_meta"]
    assert set(stamped) == set(ids)
    assert all(value.startswith("2026-08-23") for value in stamped.values())


def test_prune_never_grows_list() -> None:
    ids = [f"{i:x}" * 8 for i in range(10)]
    meta = {article_id: _iso(NOW - timedelta(days=200)) for article_id in ids}
    pruned, removed = _prune(_payload(ids, meta))
    assert removed == len(ids)
    assert len(pruned["irrelevant_article_ids"]) < len(ids)
    assert pruned["irrelevant_article_ids_meta"] == {}


def test_add_article_id_stamps_meta() -> None:
    feedback = editor_feedback.normalize_feedback({})
    article = {"id": "0123456789abcdef", "status": "irrelevant"}
    assert editor_feedback.add_article_id_to_feedback(feedback, article) is True
    assert feedback["irrelevant_article_ids"] == ["0123456789abcdef"]
    assert set(feedback["irrelevant_article_ids_meta"]) == {"0123456789abcdef"}
    assert editor_feedback.add_article_id_to_feedback(feedback, article) is False
    assert feedback["irrelevant_article_ids"].count("0123456789abcdef") == 1


def test_normalize_drops_orphan_and_invalid_meta() -> None:
    normalized = editor_feedback.normalize_feedback(
        {
            "irrelevant_article_ids": ["a" * 16],
            "irrelevant_article_ids_meta": {
                "a" * 16: "2026-01-01T00:00:00Z",
                "b" * 16: "2026-01-01T00:00:00Z",
                "c" * 16: "not-a-date",
            },
        }
    )
    assert normalized["irrelevant_article_ids_meta"] == {
        "a" * 16: "2026-01-01T00:00:00Z"
    }


def test_payload_after_prune_matches_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    meta = {"a" * 16: _iso(NOW - timedelta(days=120))}
    pruned, _ = _prune(_payload(["a" * 16, "9" * 16], meta))
    jsonschema.validate(pruned, schema)


def test_cli_execute_prunes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "editor_feedback.json"
    stale_id, fresh_id = "1" * 16, "2" * 16
    meta = {
        stale_id: _iso(NOW - timedelta(days=91)),
        fresh_id: _iso(NOW - timedelta(days=1)),
    }
    target.write_text(json.dumps(_payload([stale_id, fresh_id], meta)), encoding="utf-8")
    monkeypatch.setattr(editor_feedback, "EDITOR_FEEDBACK_FILE", target)
    monkeypatch.setattr(sys, "argv", ["editor_feedback.py", "--execute"])

    real_prune = editor_feedback.prune_editor_feedback

    def prune_with_fixed_clock(feedback: dict[str, Any], **kwargs: Any):
        kwargs.pop("now", None)
        return real_prune(feedback, now=NOW, **kwargs)

    monkeypatch.setattr(editor_feedback, "prune_editor_feedback", prune_with_fixed_clock)

    editor_feedback.main()

    result = json.loads(target.read_text(encoding="utf-8"))
    assert stale_id not in result["irrelevant_article_ids"]
    assert fresh_id in result["irrelevant_article_ids"]
    assert result["updated_at"] is not None


def test_cli_dry_run_leaves_file_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "editor_feedback.json"
    stale_id = "3" * 16
    payload = _payload(
        [stale_id], {stale_id: _iso(NOW - timedelta(days=91))}
    )
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(editor_feedback, "EDITOR_FEEDBACK_FILE", target)
    monkeypatch.setattr(sys, "argv", ["editor_feedback.py"])

    real_prune = editor_feedback.prune_editor_feedback

    def prune_with_fixed_clock(feedback: dict[str, Any], **kwargs: Any):
        kwargs.pop("now", None)
        return real_prune(feedback, now=NOW, **kwargs)

    monkeypatch.setattr(editor_feedback, "prune_editor_feedback", prune_with_fixed_clock)

    editor_feedback.main()

    assert json.loads(target.read_text(encoding="utf-8")) == payload
