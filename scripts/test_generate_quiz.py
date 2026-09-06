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
    # Fallback substance comes from per-topic instruments, never raw summaries
    # (which leak third-person phrasing), so it must be topic-specific...
    assert any(
        marker in text_pt.lower()
        for marker in (
            "universidades federais",
            "ensino técnico",
            "alfabetização",
            "tempo integral",
        )
    )
    assert any(
        marker in text_en.lower()
        for marker in (
            "education",
            "school",
            "university",
            "literacy",
            "vocational",
            "training",
        )
    )
    # ...and must not echo the summary phrasing.
    assert "infraestrutura escolar" not in text_pt.lower()
    assert not text_pt.lower().startswith(
        "o governo deveria adotar uma política pública clara e estável em que"
    )
    passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
    assert passes, f"Fallback must pass local quality: {failures}"


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

    options, _, _, _, _ = generate_quiz.build_topic_options(
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


def test_build_topic_options_parse_error_switches_to_local_only(
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
        return {
            "passes_all": False,
            "failures": ["parse_error"],
            "details": "parse error",
            "_parse_error": True,
        }

    monkeypatch.setattr(generate_quiz, "validate_quiz_option_quality", fake_validate)

    options, _, _, validation_degraded, _ = generate_quiz.build_topic_options(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        question_pt="Qual caminho deve orientar os investimentos em educação no país?",
        question_en="Which path should guide education investments in the country?",
        known_positions=known_positions,
    )

    assert calls == 1
    assert len(options) == 1
    assert validation_degraded is True


def test_build_topic_options_rejects_ai_rejected_option_uses_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit AI validator rejection drops the generated text and a
    deterministic fallback is used instead (only transport/parse problems
    degrade to local-only)."""
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
    generated_pt = (
        "Defendo que o governo amplie investimentos em educação técnica e adote "
        "metas públicas com avaliação periódica."
    )
    generated_en = (
        "I support the government expanding investment in technical education and "
        "adopting public targets with periodic evaluation."
    )
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: {
            "options": [
                {
                    "text_pt": generated_pt,
                    "text_en": generated_en,
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
    def fake_validate(**kwargs: object) -> dict[str, object]:
        if kwargs.get("text_pt") == generated_pt:
            return {"passes_all": False, "failures": ["4"], "details": "strict"}
        return {"passes_all": True, "failures": [], "details": "ok"}

    monkeypatch.setattr(generate_quiz, "validate_quiz_option_quality", fake_validate)

    options, _, _, validation_degraded, fallback_count = (
        generate_quiz.build_topic_options(
            topic_id="educacao",
            topic_label_pt="Educação",
            topic_label_en="Education",
            question_pt="Qual caminho deve orientar os investimentos em educação no país?",
            question_en="Which path should guide education investments in the country?",
            known_positions=known_positions,
        )
    )

    assert len(options) == 1
    assert options[0]["text_pt"] != generated_pt
    assert fallback_count == 1
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

    options, _, _, validation_degraded, _ = generate_quiz.build_topic_options(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        question_pt="Qual caminho deve orientar os investimentos em educação no país?",
        question_en="Which path should guide education investments in the country?",
        known_positions=known_positions,
    )

    assert len(options) == 2
    assert validation_degraded is True


def test_build_topic_options_handles_generation_provider_failure(
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
        {
            "candidate_slug": "tarcisio",
            "position_type": "inferred",
            "stance": "against",
            "summary_pt": "Defende foco em eficiência fiscal e revisão de gastos.",
            "summary_en": "Supports fiscal efficiency and expenditure review.",
            "key_actions": ["Revisar benefícios ineficientes."],
            "sources": [],
        },
    ]
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("all providers failed")),
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("validator offline")),
    )

    options, _, _, validation_degraded, _ = generate_quiz.build_topic_options(
        topic_id="educacao",
        topic_label_pt="Educação",
        topic_label_en="Education",
        question_pt="Qual caminho deve orientar os investimentos em educação no país?",
        question_en="Which path should guide education investments in the country?",
        known_positions=known_positions,
    )

    assert len(options) >= 3
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
    text_pt, text_en = generate_quiz._fallback_option_text(
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
    # Summaries are never echoed: no party, name or stance wording leaks.
    assert "partido" not in text_pt.lower()
    assert "ronaldo" not in text_pt.lower()
    assert "conservadora" not in text_pt.lower()
    assert "ronaldo" not in text_en.lower()
    assert "party" not in text_en.lower()
    # ...yet the option is still topic-specific via instruments.
    assert any(
        marker in text_pt.lower()
        for marker in ("saúde", "violência", "emprego", "psicossocial")
    )
    passes, _ = generate_quiz._local_quality_check(text_pt, text_en)
    assert passes


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (
            "Defendo que o governo mantenha estabilidade institucional e evite mudanças bruscas sem consenso em meio ambiente, com metas transparentes e revisão periódica.",
            "Acredito que o governo mantenha estabilidade institucional e evite mudanças bruscas sem consenso em meio ambiente, com metas transparentes e revisão periódica.",
        ),
        (
            "Na minha visão, o governo avance com reformas graduais e metas públicas verificáveis em impostos, com metas transparentes e revisão periódica.",
            "Defendo que o governo avance com reformas graduais e metas públicas verificáveis em impostos, com metas transparentes e revisão periódica.",
        ),
        (
            "I believe the government should maintain institutional stability and avoid abrupt changes without consensus on environment, with transparent goals and periodic review.",
            "I argue the government should maintain institutional stability and avoid abrupt changes without consensus on environment, with transparent goals and periodic review.",
        ),
    ],
)
def test_content_core_matches_intro_variants(a: str, b: str) -> None:
    """Intro-seeded fallback variants must collapse to the same content core."""
    assert generate_quiz._content_core(a) == generate_quiz._content_core(b)


def test_core_similarity_high_for_near_duplicates() -> None:
    core_a = generate_quiz._content_core(
        "Defendo que o governo avance com reformas graduais e metas em educação, "
        "com metas transparentes e revisão periódica."
    )
    core_b = generate_quiz._content_core(
        "Acredito que o governo avance com reformas graduais e metas em, "
        "com metas transparentes e revisão periódica."
    )
    assert generate_quiz._core_similarity(core_a, core_b) >= 0.85


def test_build_topic_options_same_stance_fallbacks_stay_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two same-stance candidates without differentiating hints each get a
    topic-specific instrument, so both are kept with distinct texts (no more
    near-identical "reformas graduais" templates)."""
    known_positions = [
        {
            "candidate_slug": "lula",
            "position_type": "confirmed",
            "stance": "favor",
            "summary_pt": "",
            "summary_en": "",
            "key_actions": [],
            "sources": [],
        },
        {
            "candidate_slug": "zema",
            "position_type": "inferred",
            "stance": "favor",
            "summary_pt": "",
            "summary_en": "",
            "key_actions": [],
            "sources": [],
        },
    ]
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("validator offline")),
    )

    options, _, _, validation_degraded, fallback_count = (
        generate_quiz.build_topic_options(
            topic_id="educacao",
            topic_label_pt="Educação",
            topic_label_en="Education",
            question_pt="Qual caminho deve orientar os investimentos em educação no país?",
            question_en="Which path should guide education investments in the country?",
            known_positions=known_positions,
        )
    )

    assert len(options) == 2
    assert options[0]["text_pt"] != options[1]["text_pt"]
    assert options[0]["candidate_slug"] != options[1]["candidate_slug"]
    for option in options:
        passes, failures = generate_quiz._local_quality_check(
            str(option["text_pt"]), str(option["text_en"])
        )
        assert passes, f"Fallback must pass local quality: {failures}"
    assert fallback_count == 2
    assert validation_degraded is True


@pytest.mark.parametrize(
    ("fragment", "language", "expected"),
    [
        ("Reativou o fundo amazônia e o Ibama.", "pt", False),
        ("reativar o fundo amazônia e o ibama", "pt", True),
        ("Defende um equilíbrio entre preservação e desenvolvimento.", "pt", False),
        ("Criar indicadores públicos de aprendizagem.", "pt", True),
        ("Embora o candidato tenha formação na área tributária.", "pt", False),
        ("Prioritizes expanding technical education.", "en", False),
        ("Expand technical education.", "en", True),
        ("The candidate supports the reform.", "en", False),
    ],
)
def test_hint_fragment_ok_rejects_conjugated_and_leaks(
    fragment: str, language: str, expected: bool
) -> None:
    assert generate_quiz._hint_fragment_ok(fragment, language) is expected


def test_local_quality_rejects_third_person_leak() -> None:
    text_pt = (
        "Embora o candidato tenha formação na área tributária, defendo reformas "
        "graduais com metas transparentes e revisão periódica."
    )
    text_en = (
        "Although the candidate has tax background, I support gradual reforms "
        "with transparent targets and periodic review."
    )
    passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
    assert not passes
    assert "third_person_leak" in failures


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Dados da Wikipedia para flavio-bolsonaro", None),
        ("para flavio-bolsonaro", None),
        (
            "Declaração sobre investimento público.",
            "Declaração sobre investimento público.",
        ),
        (
            "Lula defende o meio ambiente através do fortalecimento de órgãos fiscalizadores.",
            "Lula defende o meio ambiente através do fortalecimento de órgãos fiscalizadores.",
        ),
        (None, None),
    ],
)
def test_clean_source_text_drops_template_leakage(
    source: str | None, expected: str | None
) -> None:
    assert generate_quiz._clean_source_text(source) == expected


@pytest.mark.parametrize(
    ("degraded", "fallback", "total", "expected"),
    [
        (True, 6, 6, True),
        (True, 4, 6, True),
        (True, 3, 6, True),
        (True, 2, 6, False),
        (True, 0, 3, False),
        (False, 6, 6, False),
    ],
)
def test_should_drop_topic_gate(
    degraded: bool, fallback: int, total: int, expected: bool
) -> None:
    assert generate_quiz._should_drop_topic(degraded, fallback, total) is expected


def test_main_drops_degraded_fallback_heavy_topic(
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
    topics_payload = positions_payload["topics"]
    assert isinstance(topics_payload, dict)
    for topic_id in ("economia", "saude"):
        topic_payload = topics_payload[topic_id]
        assert isinstance(topic_payload, dict)
        candidates = topic_payload["candidates"]
        assert isinstance(candidates, dict)
        candidates["lula"].update(
            {
                "position_type": "confirmed",
                "stance": "favor",
                "summary_pt": "Defende investimento público com metas.",
                "summary_en": "Supports public investment with targets.",
                "key_actions": ["Ampliar escolas técnicas."],
                "sources": [],
            }
        )
        candidates["flavio-bolsonaro"].update(
            {
                "position_type": "confirmed",
                "stance": "against",
                "summary_pt": "Defende redução de gastos e ajuste fiscal.",
                "summary_en": "Supports spending cuts and fiscal adjustment.",
                "key_actions": ["Reduzir subsídios setoriais."],
                "sources": [],
            }
        )
        candidates["zema"].update(
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

    def fake_generate_quiz_topic_options(**kwargs: object) -> dict[str, object]:
        topic_id = str(kwargs["topic_id"])
        if topic_id == "economia":
            raise RuntimeError("provider down")
        return {
            "options": [
                {
                    "text_pt": f"Defendo que o governo amplie investimentos em {topic_id} com metas claras e avaliação periódica de resultados.",
                    "text_en": f"I support the government expanding investment in {topic_id} with clear targets and periodic evaluation of results.",
                    "mapped_position": 1,
                    "stance": "favor",
                    "weight": 2,
                },
                {
                    "text_pt": f"Acredito que o governo priorize controle de gastos em {topic_id} para preservar estabilidade econômica no médio prazo.",
                    "text_en": f"I believe the government should prioritize spending control in {topic_id} to preserve medium-term economic stability.",
                    "mapped_position": 2,
                    "stance": "against",
                    "weight": -2,
                },
                {
                    "text_pt": f"Entendo que o governo combine disciplina fiscal e investimento seletivo em {topic_id} para manter crescimento gradual sustentável.",
                    "text_en": f"I believe the government should combine fiscal discipline and selective investment in {topic_id} to sustain gradual growth.",
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
        generate_quiz, "generate_quiz_topic_options", fake_generate_quiz_topic_options
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("validator offline")),
    )

    generate_quiz.main()

    payload = json.loads(quiz_file.read_text(encoding="utf-8"))
    assert "economia" not in payload["ordered_topics"]
    assert "saude" in payload["ordered_topics"]


@pytest.mark.parametrize(
    ("text_pt", "text_en", "failure"),
    [
        (
            "Defendo que o governo avance com reformas graduais, pois Ronaldo tem postura conservadora e metas claras.",
            "I believe the government should advance gradual reforms with clear targets.",
            "candidate_reference",
        ),
        (
            "Acredito que o governo fortaleça a fiscalização com metas claras e avaliação periódica dos resultados.",
            "Additionally, a central point: Flávio supported the fiscal transparency program with clear targets.",
            "candidate_reference",
        ),
        (
            "Acredito que o Estado fortaleça órgãos de fiscalização ambiental, como o IBAMA, com metas claras e auditoria.",
            "I believe the State should strengthen environmental enforcement agencies with clear targets and audits.",
            "bio_reference",
        ),
        (
            "Defendo que o governo amplie o orçamento das universidades e garanta o Prouni e o Fies com metas claras.",
            "I believe the government should expand university budgets and keep Prouni and Fies with clear targets.",
            "bio_reference",
        ),
        (
            "Na minha visão, o governo avance com reformas graduais e metas públicas verificáveis em armas com avaliação.",
            "I support the government choosing to advance gradual reforms on firearms. Additionally, a central point: The politician is in favor of loosening restrictions.",
            "template_appendage",
        ),
        (
            "Entendo que não há informações suficientes para determinar uma posição clara sobre educação com metas públicas.",
            "I understand there is not enough information to determine a clear stance on education with public targets.",
            "third_person_leak",
        ),
        (
            "Defendo que o governo avance com reformas e metas claras, mas concordo em não perseguir quem acidentalmente interrompe.",
            "I believe the government should advance reforms with clear targets and not prosecute those who accidentally interrupt.",
            "broken_continuation",
        ),
        (
            "Defendo que o governo avance com reformas graduais e metas públicas com avaliação periódica dos resultados.",
            "I believe the government should advance gradual reforms with public targets. A second sentence appears only here. A third sentence appears only here too.",
            "en_pt_mismatch",
        ),
    ],
)
def test_local_quality_rejects_observed_quiz_leaks(
    text_pt: str, text_en: str, failure: str
) -> None:
    passes, failures = generate_quiz._local_quality_check(text_pt, text_en)
    assert not passes, f"Expected failure for: {text_pt[:60]}"
    assert failure in failures


def test_weight_polarity_mismatch_rejected() -> None:
    assert not generate_quiz._weight_matches_mapped_stance(3, "strongly_against")
    assert not generate_quiz._weight_matches_mapped_stance(-2, "favor")
    assert not generate_quiz._weight_matches_mapped_stance(2, "against")
    assert generate_quiz._weight_matches_mapped_stance(3, "strongly_favor")
    assert generate_quiz._weight_matches_mapped_stance(-3, "strongly_against")
    assert generate_quiz._weight_matches_mapped_stance(0, "neutral")
    assert generate_quiz._weight_matches_mapped_stance(2, "favor")


def test_build_topic_options_rejects_polarity_inversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pro-LGBTQ text mapped onto an anti-LGBTQ candidate must not be
    emitted: the inverted weight would score users toward the wrong candidate."""
    known_positions = [
        {
            "candidate_slug": "flavio-bolsonaro",
            "position_type": "confirmed",
            "stance": "strongly_against",
            "summary_pt": "Oposição a políticas de identidade de gênero.",
            "summary_en": "Opposition to gender identity policies.",
            "key_actions": [],
            "sources": [],
        }
    ]
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: {
            "options": [
                {
                    "text_pt": "Acredito que o Estado deve assegurar acesso equitativo à saúde e educação com programas de apoio.",
                    "text_en": "I believe the state should ensure equitable access to health and education with support programs.",
                    "mapped_position": 1,
                    "stance": "strongly_favor",
                    "weight": 3,
                }
            ],
            "_ai_provider": "vertex",
            "_ai_model": "gemini-3.1-pro",
            "_parse_error": False,
        },
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: {"passes_all": True, "failures": [], "details": "ok"},
    )

    options, _, _, _, fallback_count = generate_quiz.build_topic_options(
        topic_id="lgbtq",
        topic_label_pt="Direitos LGBTQIA+",
        topic_label_en="LGBTQIA+ Rights",
        question_pt="Qual deve ser a prioridade das políticas públicas para direitos LGBTQIA+?",
        question_en="What should be the priority of public policy for LGBTQIA+ rights?",
        known_positions=known_positions,
    )

    assert len(options) == 1
    assert options[0]["weight"] < 0
    assert fallback_count == 1


def test_fallback_topic_variety_no_shared_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A full-fallback topic must yield pairwise-distinct options: the variant
    loop resolves instrument collisions so no two options share a template."""
    stances = ["strongly_favor", "favor", "neutral", "against", "strongly_against"]
    known_positions = [
        {
            "candidate_slug": f"cand-{index}",
            "position_type": "confirmed",
            "stance": stance,
            "summary_pt": "",
            "summary_en": "",
            "key_actions": [],
            "sources": [],
        }
        for index, stance in enumerate(stances)
    ]
    monkeypatch.setattr(
        generate_quiz,
        "generate_quiz_topic_options",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    monkeypatch.setattr(
        generate_quiz,
        "validate_quiz_option_quality",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("validator offline")),
    )

    options, _, _, _, _ = generate_quiz.build_topic_options(
        topic_id="armas",
        topic_label_pt="Armas",
        topic_label_en="Firearms",
        question_pt="Como deve ser a política de acesso e controle de armas no Brasil?",
        question_en="How should Brazil regulate firearm access and control?",
        known_positions=known_positions,
    )

    assert len(options) == len(stances)
    cores = [
        generate_quiz._content_core(str(option["text_pt"])) for option in options
    ]
    for index, core_a in enumerate(cores):
        for core_b in cores[index + 1 :]:
            assert (
                generate_quiz._core_similarity(core_a, core_b)
                < generate_quiz.CORE_SIMILARITY_THRESHOLD
            ), f"Near-duplicate fallback cores: {core_a[:60]} / {core_b[:60]}"
