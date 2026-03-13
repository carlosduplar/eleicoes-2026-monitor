"""Tests for scripts/extract_positions_from_articles.py."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts import create_candidates_positions as builder
from scripts import extract_positions_from_articles as extractor


def test_extract_positions_updates_draft_with_ai_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs" / "schemas"
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    articles_file = data_dir / "articles.json"
    positions_file = data_dir / "candidates_positions.json"
    draft_file = data_dir / "candidates_positions_draft.json"
    schema_file = docs_dir / "candidates_positions.schema.json"

    schema_file.write_text(
        Path("docs/schemas/candidates_positions.schema.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    positions_payload = builder._build_payload(["lula", "flavio-bolsonaro"])
    positions_file.write_text(
        json.dumps(positions_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    articles_payload = {
        "articles": [
            {
                "id": "aaaaaaaaaaaaaaaa",
                "url": "https://example.com/economia",
                "title": "Lula defende investimento estatal",
                "published_at": "2026-03-12T12:00:00Z",
                "candidates_mentioned": ["lula"],
                "topics": ["economia"],
                "summaries": {
                    "pt-BR": "Lula afirmou que o governo deve investir mais em infraestrutura.",
                    "en-US": "Lula said the government should invest more in infrastructure.",
                },
            }
        ]
    }
    articles_file.write_text(
        json.dumps(articles_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(extractor, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(extractor, "POSITIONS_FILE", positions_file)
    monkeypatch.setattr(extractor, "DEFAULT_DRAFT_FILE", draft_file)
    monkeypatch.setattr(extractor, "SCHEMA_FILE", schema_file)

    def fake_extract_candidate_topic_position(
        candidate: str,
        topic_id: str,
        topic_label_pt: str,
        snippets: list[str],
        existing_summary_pt: str | None = None,
    ) -> dict[str, object]:
        del topic_label_pt, existing_summary_pt
        if candidate == "lula" and topic_id == "economia" and snippets:
            return {
                "position_type": "confirmed",
                "stance": "favor",
                "summary_pt": "Defende investimento público em infraestrutura.",
                "summary_en": "Supports public investment in infrastructure.",
                "key_actions": ["Anunciou pacote de obras públicas."],
                "source_indices": [1],
            }
        return {
            "position_type": "unknown",
            "stance": "unknown",
            "summary_pt": None,
            "summary_en": None,
            "key_actions": [],
            "source_indices": [],
        }

    monkeypatch.setattr(
        extractor,
        "extract_candidate_topic_position",
        fake_extract_candidate_topic_position,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["extract_positions_from_articles.py", "--output", str(draft_file)],
    )

    extractor.main()

    payload = json.loads(draft_file.read_text(encoding="utf-8"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    lula_economia = payload["topics"]["economia"]["candidates"]["lula"]
    assert lula_economia["position_type"] == "confirmed"
    assert lula_economia["stance"] == "favor"
    assert lula_economia["summary_pt"] is not None
    assert lula_economia["sources"]
    assert "AUTO-EXTRACTED" in (lula_economia["editor_notes"] or "")
