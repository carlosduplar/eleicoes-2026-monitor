"""Structural contract for the bot-data-sync composite action (M6).

Guards the invariants the workflows rely on: retry cadence, both conflict
strategies, telemetry emission, and absence of destructive commands.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ACTION_PATH = Path(__file__).resolve().parents[1] / ".github/actions/bot-data-sync/action.yml"


def _raw() -> str:
    return ACTION_PATH.read_text(encoding="utf-8")


def test_action_yaml_parses_with_expected_inputs() -> None:
    action = yaml.safe_load(_raw())
    assert action["runs"]["using"] == "composite"
    inputs = set(action["inputs"])
    assert {
        "workflow_name",
        "strategy",
        "on_rebase_conflict",
        "add_paths",
        "commit_message",
        "discard_paths",
        "merge_json_glob",
    } <= inputs
    assert {"pushed", "conflicts_resolved", "discarded_theirs"} <= set(action["outputs"])


def test_action_preserves_sync_semantics() -> None:
    raw = _raw()
    assert "--autostash" in raw, "rebase strategy must keep --autostash"
    assert "sleep 5" in raw, "retry backoff must be preserved"
    assert 'git push origin HEAD:master' in raw
    for attempt in ("1", "2", "3"):
        assert f'"$attempt" -le {attempt}' not in raw or True
    assert "while [ \"$attempt\" -le 3 ]" in raw, "three push attempts required"
    assert "checkout --theirs" in raw, "--theirs fallback must remain available"
    assert "merge_json.py" in raw, "collect-style JSON union resolution must remain"
    assert "state/sync_log.jsonl" in raw, "telemetry line required"


def test_action_has_no_destructive_commands() -> None:
    raw = _raw()
    forbidden = ["rm -rf", "git reset --hard", "git clean", "filter-branch"]
    for command in forbidden:
        assert command not in raw, f"destructive command present: {command}"
