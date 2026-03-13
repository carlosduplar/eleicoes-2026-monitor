"""Tests for scripts/generate_quiz.py."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts import create_candidates_positions as builder
from scripts import generate_quiz


def test_generate_quiz_from_positions_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs" / "schemas"
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    positions_file = data_dir / "candidates_positions.json"
    quiz_file = data_dir / "quiz.json"
    schema_file = docs_dir / "quiz.schema.json"

    positions_payload = builder._build_payload(["lula", "flavio-bolsonaro", "zema"])
    economia = positions_payload["topics"]["economia"]["candidates"]
    economia["lula"].update(
        {
            "position_type": "confirmed",
            "stance": "strongly_favor",
            "summary_pt": "Defende expansão de investimento público.",
            "summary_en": "Supports expanding public investment.",
            "key_actions": ["Anunciou pacote de obras."],
            "sources": [
                {
                    "type": "news_report",
                    "url": "https://example.com/a",
                    "description_pt": "Declaração sobre investimento público.",
                    "description_en": "Statement on public investment.",
                    "date": "2026-03-10",
                    "article_id": "aaaaaaaaaaaaaaaa",
                }
            ],
        }
    )
    economia["flavio-bolsonaro"].update(
        {
            "position_type": "confirmed",
            "stance": "strongly_against",
            "summary_pt": "Defende redução do papel do Estado na economia.",
            "summary_en": "Supports reducing the state's role in the economy.",
            "key_actions": ["Defendeu corte de gastos."],
            "sources": [
                {
                    "type": "news_report",
                    "url": "https://example.com/b",
                    "description_pt": "Declaração sobre austeridade fiscal.",
                    "description_en": "Statement on fiscal austerity.",
                    "date": "2026-03-10",
                    "article_id": "bbbbbbbbbbbbbbbb",
                }
            ],
        }
    )
    economia["zema"].update(
        {
            "position_type": "inferred",
            "stance": "neutral",
            "summary_pt": "Defende equilíbrio fiscal com ajustes graduais.",
            "summary_en": "Supports fiscal balance with gradual adjustments.",
            "key_actions": [],
            "sources": [
                {
                    "type": "party_platform",
                    "url": "https://example.com/c",
                    "description_pt": "Programa partidário sobre equilíbrio fiscal.",
                    "description_en": "Party platform on fiscal balance.",
                    "date": "2026-03-09",
                    "article_id": None,
                }
            ],
        }
    )
    positions_file.write_text(
        json.dumps(positions_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    schema_file.write_text(
        Path("docs/schemas/quiz.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setattr(generate_quiz, "POSITIONS_FILE", positions_file)
    monkeypatch.setattr(generate_quiz, "QUIZ_FILE", quiz_file)
    monkeypatch.setattr(generate_quiz, "SCHEMA_FILE", schema_file)

    def fake_generate_quiz_topic_options(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "options": [
                {
                    "text_pt": "O governo deveria ampliar investimentos públicos para acelerar crescimento e emprego em setores estratégicos.",
                    "text_en": "The government should expand public investment to accelerate growth and jobs in strategic sectors.",
                    "mapped_position": 1,
                    "stance": "strongly_favor",
                    "weight": 3,
                },
                {
                    "text_pt": "O governo deveria reduzir seu tamanho na economia e priorizar responsabilidade fiscal com menos gasto público.",
                    "text_en": "The government should shrink its role in the economy and prioritize fiscal responsibility with less public spending.",
                    "mapped_position": 2,
                    "stance": "strongly_against",
                    "weight": -3,
                },
                {
                    "text_pt": "O governo deveria combinar disciplina fiscal e investimento seletivo para manter estabilidade e crescimento gradual.",
                    "text_en": "The government should combine fiscal discipline and selective investment to maintain stability and gradual growth.",
                    "mapped_position": 3,
                    "stance": "neutral",
                    "weight": 0,
                },
            ],
            "_ai_provider": "vertex",
            "_ai_model": "gemini-3.1-pro",
            "_parse_error": False,
        }

    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        fake_generate_quiz_topic_options,
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: {"passes_all": True, "failures": [], "details": ""},
    )

    generate_quiz.main()

    payload = json.loads(quiz_file.read_text(encoding="utf-8"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    assert payload["schema_version"] == "2.0.0"
    assert payload["ordered_topics"]
    first_topic = payload["topics"][payload["ordered_topics"][0]]
    assert first_topic["options"][0]["weight"] in {-3, -2, 0, 2, 3}
    assert first_topic["options"][0]["position_type"] in {"confirmed", "inferred"}
