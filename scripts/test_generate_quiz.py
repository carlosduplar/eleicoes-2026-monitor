"""Tests for scripts/generate_quiz.py."""

from __future__ import annotations

import json
import re
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


def test_local_quality_rejects_boilerplate() -> None:
    text_pt = (
        "O governo deveria adotar uma política pública clara e estável em que "
        "apoia reformas moderadas com metas transparentes."
    )
    text_en = (
        "The government should adopt a clear and stable public policy in which "
        "supports moderate reforms with transparent targets."
    )
    passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
    assert not passes
    assert "boilerplate" in failures


def test_main_marks_generation_quality_degraded_when_local_fallback_used(
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
            "stance": "favor",
            "summary_pt": "Defende investimento público com metas.",
            "summary_en": "Supports public investment with targets.",
            "key_actions": ["Ampliar escolas técnicas."],
            "sources": [],
        }
    )
    economia["flavio-bolsonaro"].update(
        {
            "position_type": "confirmed",
            "stance": "against",
            "summary_pt": "Defende redução de gastos e ajuste fiscal.",
            "summary_en": "Supports spending cuts and fiscal adjustment.",
            "key_actions": ["Reduzir subsídios setoriais."],
            "sources": [],
        }
    )
    economia["zema"].update(
        {
            "position_type": "inferred",
            "stance": "neutral",
            "summary_pt": "Defende equilíbrio fiscal com ajustes graduais.",
            "summary_en": "Supports fiscal balance with gradual adjustments.",
            "key_actions": ["Publicar metas trimestrais de desempenho."],
            "sources": [],
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
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: {
            "options": [
                {
                    "text_pt": "Defendo que o governo amplie investimentos públicos com metas objetivas e revisão periódica de resultados na economia.",
                    "text_en": "I support the government expanding public investment with objective targets and periodic review of economic outcomes.",
                    "mapped_position": 1,
                    "stance": "favor",
                    "weight": 2,
                },
                {
                    "text_pt": "Acredito que o governo priorize controle de gastos e regras fiscais rígidas para preservar estabilidade econômica no médio prazo.",
                    "text_en": "I believe the government should prioritize spending control and strict fiscal rules to preserve medium-term economic stability.",
                    "mapped_position": 2,
                    "stance": "against",
                    "weight": -2,
                },
                {
                    "text_pt": "Entendo que o governo combine disciplina fiscal e investimento seletivo para manter estabilidade com crescimento gradual sustentável.",
                    "text_en": "I believe the government should combine fiscal discipline and selective investment to sustain stability with gradual growth.",
                    "mapped_position": 3,
                    "stance": "neutral",
                    "weight": 0,
                },
            ],
            "_ai_provider": "vertex",
            "_ai_model": "gemini-3.1-pro",
            "_parse_error": False,
        },
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("providers down")),
    )

    generate_quiz.main()

    payload = json.loads(quiz_file.read_text(encoding="utf-8"))
    first_topic_id = payload["ordered_topics"][0]
    generation_quality = payload["topics"][first_topic_id]["generation_quality"]
    assert generation_quality["validated"] is False
    assert generation_quality["validator_model"] == "local:heuristic-fallback"


def test_fallback_option_uses_topic_summary_and_actions() -> None:
    text_pt, text_en = generate_quiz._fallback_option_text(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        candidate_slug="candidate-a",
        summary_pt="Prioriza expansão do ensino técnico e melhora da infraestrutura escolar.",
        summary_en="Prioritizes expanding technical education and improving school infrastructure.",
        key_actions=["Ampliar escolas de tempo integral."],
        stance="favor",
        variant_offset=0,
    )
    assert "educação" in text_pt.lower()
    assert "education" in text_en.lower()
    assert "ensino técnico" in text_pt.lower() or "tempo integral" in text_pt.lower()
    assert not text_pt.lower().startswith(
        "o governo deveria adotar uma política pública clara e estável em que"
    )


def test_build_topic_options_replaces_duplicate_generated_texts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    known_positions = [
        {
            "candidate_slug": "lula",
            "position_type": "confirmed",
            "stance": "favor",
            "summary_pt": "Defende expansão do investimento em escolas.",
            "summary_en": "Supports expanding investment in schools.",
            "key_actions": ["Ampliar escolas de tempo integral."],
            "sources": [],
        },
        {
            "candidate_slug": "zema",
            "position_type": "inferred",
            "stance": "favor",
            "summary_pt": "Defende gestão com metas e avaliação de desempenho.",
            "summary_en": "Supports management with targets and performance evaluation.",
            "key_actions": ["Criar indicadores públicos de aprendizagem."],
            "sources": [],
        },
    ]

    duplicate_text_pt = (
        "Defendo que o governo avance com reformas graduais na educação "
        "com metas transparentes e avaliação periódica."
    )
    duplicate_text_en = (
        "I support the government moving forward with gradual education reforms "
        "with transparent goals and periodic review."
    )

    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: {
            "options": [
                {
                    "text_pt": duplicate_text_pt,
                    "text_en": duplicate_text_en,
                    "mapped_position": 1,
                    "stance": "favor",
                    "weight": 2,
                },
                {
                    "text_pt": duplicate_text_pt,
                    "text_en": duplicate_text_en,
                    "mapped_position": 2,
                    "stance": "favor",
                    "weight": 2,
                },
            ],
            "_ai_provider": "vertex",
            "_ai_model": "gemini-3.1-pro",
            "_parse_error": False,
        },
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: {"passes_all": True, "failures": [], "details": ""},
    )

    options, _, _, _ = generate_quiz.build_topic_options(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        question_pt="Qual caminho deve orientar os investimentos em educação no país?",
        question_en="Which path should guide education investments in the country?",
        known_positions=known_positions,
    )

    assert len(options) == 2
    assert options[0]["text_pt"] != options[1]["text_pt"]
    assert options[0]["candidate_slug"] != options[1]["candidate_slug"]


def test_build_topic_options_retries_parse_error_and_keeps_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    known_positions = [
        {
            "candidate_slug": "lula",
            "position_type": "confirmed",
            "stance": "favor",
            "summary_pt": "Defende expansão do investimento em escolas.",
            "summary_en": "Supports expanding investment in schools.",
            "key_actions": ["Ampliar escolas de tempo integral."],
            "sources": [],
        }
    ]
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: {
            "options": [
                {
                    "text_pt": "Defendo que o governo amplie investimentos em educação técnica e adote metas públicas com avaliação periódica.",
                    "text_en": "I support the government expanding investment in technical education and adopting public targets with periodic evaluation.",
                    "mapped_position": 1,
                    "stance": "favor",
                    "weight": 2,
                }
            ],
            "_ai_provider": "vertex",
            "_ai_model": "gemini-3.1-pro",
            "_parse_error": False,
        },
    )
    calls = 0

    def fake_validate(**kwargs: object) -> dict[str, object]:
        del kwargs
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "passes_all": False,
                "failures": ["parse_error"],
                "details": "parse error",
                "_parse_error": True,
            }
        return {"passes_all": True, "failures": [], "details": ""}

    monkeypatch.setattr(generate_quiz, "validate_quiz_option_quality", fake_validate)

    options, _, _, validation_degraded = generate_quiz.build_topic_options(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        question_pt="Qual caminho deve orientar os investimentos em educação no país?",
        question_en="Which path should guide education investments in the country?",
        known_positions=known_positions,
    )

    assert calls == 2
    assert len(options) == 1
    assert validation_degraded is False


def test_build_topic_options_degrades_when_validator_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    known_positions = [
        {
            "candidate_slug": "lula",
            "position_type": "confirmed",
            "stance": "favor",
            "summary_pt": "Defende expansão do investimento em escolas.",
            "summary_en": "Supports expanding investment in schools.",
            "key_actions": ["Ampliar escolas de tempo integral."],
            "sources": [],
        },
        {
            "candidate_slug": "zema",
            "position_type": "inferred",
            "stance": "neutral",
            "summary_pt": "Defende gestão com metas e avaliação de desempenho.",
            "summary_en": "Supports management with targets and performance evaluation.",
            "key_actions": ["Criar indicadores públicos de aprendizagem."],
            "sources": [],
        },
    ]
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: {
            "options": [
                {
                    "text_pt": "Defendo que o governo amplie investimentos em educação técnica e adote metas públicas com avaliação periódica.",
                    "text_en": "I support the government expanding investment in technical education and adopting public targets with periodic evaluation.",
                    "mapped_position": 1,
                    "stance": "favor",
                    "weight": 2,
                },
                {
                    "text_pt": "Entendo que o governo combine metas de desempenho e apoio gradual às redes para melhorar resultados sem rupturas bruscas.",
                    "text_en": "I believe the government should combine performance targets and gradual support to school systems to improve outcomes without abrupt disruption.",
                    "mapped_position": 2,
                    "stance": "neutral",
                    "weight": 0,
                },
            ],
            "_ai_provider": "vertex",
            "_ai_model": "gemini-3.1-pro",
            "_parse_error": False,
        },
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("providers down")),
    )

    options, _, _, validation_degraded = generate_quiz.build_topic_options(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        question_pt="Qual caminho deve orientar os investimentos em educação no país?",
        question_en="Which path should guide education investments in the country?",
        known_positions=known_positions,
    )

    assert len(options) == 2
    assert validation_degraded is True


def test_local_quality_rejects_party_reference() -> None:
    cases = [
        (
            "Como membro do psdb, sou a favor da reforma tributária.",
            "As a member of the psdb, I support tax reform.",
        ),
        (
            "O partido de Ronaldo, o união brasil, é contra a censura.",
            "Ronaldo's party, união brasil, is against censorship.",
        ),
        (
            "Defendo que o governo avance. Isso inclui o mbl opõe-se a políticas.",
            "I believe the government should advance. This includes the mbl opposes policies.",
        ),
        (
            "Acredito que na pauta demidia, o governo avance. Também é essencial apoiou a reforma.",
            "I believe on media regulation the government should advance. Also it is essential supported the reform.",
        ),
    ]
    for text_pt, text_en in cases:
        passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
        assert not passes, f"Expected failure for: {text_pt[:60]}"
        assert "party_reference" in failures or "broken_continuation" in failures


def test_local_quality_rejects_broken_continuations() -> None:
    cases = [
        (
            "Defendo que o governo avance com reformas graduais. Também é essencial apoiou a reforma da previdência no congresso nacional.",
            "I defend that the government should advance with gradual reforms. Also it is essential supported the pension reform in congress.",
        ),
        (
            "Acredito que o governo tome iniciativas. Isso inclui é membro do partido que apoia a medida.",
            "I believe the government should take initiatives. This includes is a member of the party that supports the measure.",
        ),
    ]
    for text_pt, text_en in cases:
        passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
        assert not passes, f"Expected failure for: {text_pt[:60]}"
        assert "broken_continuation" in failures


def test_local_quality_accepts_clean_options() -> None:
    cases = [
        (
            "Defendo que o governo avance com reformas graduais na educação e crie metas transparentes com revisão periódica.",
            "I believe the government should advance with gradual reforms in education and create transparent targets with periodic review.",
        ),
        (
            "Entendo que o governo priorize a segurança pública com políticas firmes e baseadas em evidências.",
            "I understand that the government should prioritize public security with firm and evidence-based policies.",
        ),
    ]
    for text_pt, text_en in cases:
        passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
        assert passes, f"Expected pass for: {text_pt[:60]}, failures: {failures}"


def test_fallback_against_no_double_negative() -> None:
    for variant in range(8):
        text_pt, _ = generate_quiz._fallback_option_text(
            topic_id="meio_ambiente",
            topic_label_pt="Meio Ambiente",
            topic_label_en="Environment",
            candidate_slug="bolsonaro",
            summary_pt="",
            summary_en="",
            key_actions=[],
            stance="against",
            variant_offset=variant,
        )
        double_neg = re.search(
            r"\bevite.*\bevite\b|\bevitar.*\bevitar\b", text_pt.lower()
        )
        assert double_neg is None, (
            f"Double negative in fallback variant {variant}: {text_pt}"
        )


def test_fallback_party_hint_rejected() -> None:
    text_pt, _ = generate_quiz._fallback_option_text(
        topic_id="impostos",
        topic_label_pt="Impostos",
        topic_label_en="Taxes",
        candidate_slug="caiado",
        summary_pt="Como membro do psdb, apoia a reforma tributária.",
        summary_en="As a member of the psdb, he supports tax reform.",
        key_actions=[],
        stance="favor",
        variant_offset=0,
    )
    assert "psdb" not in text_pt.lower()
    assert "membro" not in text_pt.lower()


def test_fallback_does_not_append_raw_party_summary() -> None:
    text_pt, _ = generate_quiz._fallback_option_text(
        topic_id="lgbtq",
        topic_label_pt="Direitos LGBTQIA+",
        topic_label_en="LGBTQIA+ Rights",
        candidate_slug="caiado",
        summary_pt="O partido de Ronaldo Caiado tem postura conservadora e é contrário a políticas de identidade de gênero.",
        summary_en="Ronaldo Caiado's party has a conservative stance and is against gender identity policies.",
        key_actions=[],
        stance="against",
        variant_offset=0,
    )
    assert "partido" not in text_pt.lower()
    assert "ronaldo" not in text_pt.lower()
    assert "conservadora" not in text_pt.lower()
    assert "lgbtq" in text_pt.lower() or "identidade" in text_pt.lower()
