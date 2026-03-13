"""Interactive review tool for candidates_positions draft updates."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema

ROOT_DIR = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT_DIR / "data" / "candidates_positions.json"
DRAFT_FILE = ROOT_DIR / "data" / "candidates_positions_draft.json"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"

COMPARE_FIELDS = [
    "position_type",
    "stance",
    "summary_pt",
    "summary_en",
    "key_actions",
    "sources",
    "editor_notes",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _entry_changed(base_entry: dict[str, object], draft_entry: dict[str, object]) -> bool:
    for field in COMPARE_FIELDS:
        if base_entry.get(field) != draft_entry.get(field):
            return True
    return False


def _render_diff(topic_id: str, candidate_slug: str, base_entry: dict[str, object], draft_entry: dict[str, object]) -> str:
    lines = [f"\n=== {topic_id} :: {candidate_slug} ==="]
    for field in COMPARE_FIELDS:
        old_value = base_entry.get(field)
        new_value = draft_entry.get(field)
        if old_value == new_value:
            continue
        lines.append(f"- {field} (base): {json.dumps(old_value, ensure_ascii=False)}")
        lines.append(f"+ {field} (draft): {json.dumps(new_value, ensure_ascii=False)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE_FILE, help="Path to base candidates_positions.json.")
    parser.add_argument("--draft", type=Path, default=DRAFT_FILE, help="Path to draft candidates_positions_draft.json.")
    parser.add_argument("--output", type=Path, default=BASE_FILE, help="Output path for approved knowledge base.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Approve all diffs without prompting.",
    )
    args = parser.parse_args()

    base_payload = _load_json(args.base)
    draft_payload = _load_json(args.draft)
    if not isinstance(base_payload, dict) or not isinstance(draft_payload, dict):
        raise SystemExit("Base and draft payloads must be JSON objects.")

    merged_payload = deepcopy(base_payload)
    base_topics = base_payload.get("topics")
    draft_topics = draft_payload.get("topics")
    merged_topics = merged_payload.get("topics")
    if not isinstance(base_topics, dict) or not isinstance(draft_topics, dict) or not isinstance(merged_topics, dict):
        raise SystemExit("Invalid topics structure in base or draft file.")

    total_diffs = 0
    approved = 0

    for topic_id, draft_topic in draft_topics.items():
        if not isinstance(draft_topic, dict):
            continue
        base_topic = base_topics.get(topic_id)
        merged_topic = merged_topics.get(topic_id)
        if not isinstance(base_topic, dict) or not isinstance(merged_topic, dict):
            continue

        draft_candidates = draft_topic.get("candidates")
        base_candidates = base_topic.get("candidates")
        merged_candidates = merged_topic.get("candidates")
        if not isinstance(draft_candidates, dict) or not isinstance(base_candidates, dict) or not isinstance(merged_candidates, dict):
            continue

        for candidate_slug, draft_entry in draft_candidates.items():
            base_entry = base_candidates.get(candidate_slug)
            merged_entry = merged_candidates.get(candidate_slug)
            if not isinstance(draft_entry, dict) or not isinstance(base_entry, dict) or not isinstance(merged_entry, dict):
                continue

            if not _entry_changed(base_entry, draft_entry):
                continue

            total_diffs += 1
            if args.yes:
                decision = "y"
            else:
                print(_render_diff(topic_id, candidate_slug, base_entry, draft_entry))
                decision = input("Approve this update? [y/N]: ").strip().lower()

            if decision in {"y", "yes"}:
                for field in COMPARE_FIELDS:
                    merged_entry[field] = draft_entry.get(field)
                approved += 1

    schema = _load_json(SCHEMA_FILE)
    jsonschema.validate(merged_payload, schema)
    _write_json(args.output, merged_payload)
    print(
        f"Review complete. Differences: {total_diffs}. Approved: {approved}. "
        f"Output: {args.output}"
    )


if __name__ == "__main__":
    main()
