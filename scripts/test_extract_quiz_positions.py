"""Unit tests for scripts/extract_quiz_positions.py - divergence, topics, coverage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from scripts import extract_quiz_positions as quiz_positions


def _make_position(
    stance: str = "favor",
    weight: int = 2,
    confidence: str = "high",
    text_pt: str = "Texto",
    text_en: str = "Text",
) -> dict[str, Any]:
    """Create a minimal position dict."""
    stance_lookup = {2: "favor", 0: "neutral", -2: "against"}
    resolved_stance = stance if stance in {"favor", "neutral", "against", "unclear"} else stance_lookup.get(weight, "neutral")
    return {
        "position_pt": text_pt,
        "position_en": text_en,
        "stance": resolved_stance,
        "confidence": confidence,
        "best_source_snippet_index": 1,
    }


def _topic_positions(*positions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    topic: dict[str, dict[str, Any]] = {}
    for idx, position in enumerate(positions):
        candidate = quiz_positions.CANDIDATES[idx]
        topic[candidate] = position
    return topic


def test_divergence_score_all_same_stance() -> None:
    """All candidates with same stance should return 0.0 divergence."""
    positions = [
        _make_position(stance="favor", confidence="high"),
        _make_position(stance="favor", confidence="medium"),
        _make_position(stance="favor", confidence="high"),
    ]
    assert quiz_positions.divergence_score(positions) == 0.0


def test_divergence_score_opposite_stances() -> None:
    """Opposite stances should produce maximum divergence."""
    positions = [
        _make_position(stance="favor", confidence="high"),
        _make_position(stance="against", confidence="high"),
    ]
    assert quiz_positions.divergence_score(positions) == pytest.approx(1.0)


def test_divergence_score_empty_list() -> None:
    """Empty positions list should return 0."""
    assert quiz_positions.divergence_score([]) == 0.0


def test_select_quiz_topics_orders_by_divergence() -> None:
    """Topics with highest divergence should appear first."""
    all_positions = {
        "economia": _topic_positions(
            _make_position(stance="favor", confidence="high"),
            _make_position(stance="against", confidence="high"),
        ),
        "saude": _topic_positions(
            _make_position(stance="neutral", confidence="high"),
            _make_position(stance="against", confidence="high"),
        ),
    }

    selected = quiz_positions.select_quiz_topics(all_positions)
    assert selected[:2] == ["economia", "saude"]


def test_select_quiz_topics_covers_multiple_clusters() -> None:
    """Selected topics should span at least 3 broad categories."""
    all_positions = {
        "economia": _topic_positions(_make_position(stance="favor"), _make_position(stance="against")),
        "seguranca": _topic_positions(_make_position(stance="favor"), _make_position(stance="against")),
        "saude": _topic_positions(_make_position(stance="neutral"), _make_position(stance="against")),
        "politica_ext": _topic_positions(_make_position(stance="favor"), _make_position(stance="against")),
    }
    cluster_by_topic = {
        "economia": "economy",
        "seguranca": "security",
        "saude": "social",
        "politica_ext": "foreign",
    }

    selected = quiz_positions.select_quiz_topics(all_positions)
    covered_clusters = {cluster_by_topic[topic] for topic in selected if topic in cluster_by_topic}
    assert len(covered_clusters) >= 3


def test_select_quiz_topics_max_15() -> None:
    """ordered_topics never exceeds 15 entries."""
    all_positions = {
        topic_id: _topic_positions(
            _make_position(stance="favor", confidence="high"),
            _make_position(stance="against", confidence="high"),
        )
        for topic_id in quiz_positions.QUIZ_TOPICS
    }

    selected = quiz_positions.select_quiz_topics(all_positions)
    assert len(selected) == 15
    assert all(topic in quiz_positions.QUIZ_TOPICS for topic in selected)


def test_build_options_no_candidate_slug_in_text() -> None:
    """Option text_pt/text_en must not expose candidate_slug values."""
    positions = {
        "lula": _make_position(
            stance="favor",
            text_pt="lula defende ampliar politicas publicas",
            text_en="lula supports expanding public policies",
        ),
        "flavio-bolsonaro": _make_position(
            stance="against",
            text_pt="Flavio Bolsonaro rejeita ampliar impostos",
            text_en="Flavio Bolsonaro rejects raising taxes",
        ),
    }

    options = quiz_positions.build_options("economia", positions)
    assert options
    for option in options:
        text_pt = str(option["text_pt"]).lower()
        text_en = str(option["text_en"]).lower()
        for slug in quiz_positions.CANDIDATES:
            assert slug not in text_pt
            assert slug not in text_en
            assert slug.replace("-", " ") not in text_pt
            assert slug.replace("-", " ") not in text_en


def test_build_options_filters_low_confidence() -> None:
    """Positions with confidence='low' are excluded."""
    positions = {
        "lula": _make_position(stance="favor", confidence="low"),
        "tarcisio": _make_position(stance="against", confidence="high"),
    }

    options = quiz_positions.build_options("economia", positions)

    assert len(options) == 1
    assert options[0]["candidate_slug"] == "tarcisio"
    assert options[0]["confidence"] == "high"


def test_quiz_output_conforms_to_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full main() output validates against docs/schemas/quiz.schema.json."""
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs" / "schemas"
    articles_file = data_dir / "articles.json"
    quiz_file = data_dir / "quiz.json"
    schema_file = docs_dir / "quiz.schema.json"
    docs_dir.mkdir(parents=True, exist_ok=True)
    schema_file.write_text(Path("docs/schemas/quiz.schema.json").read_text(encoding="utf-8"), encoding="utf-8")

    articles_payload = {
        "$schema": "../docs/schemas/articles.schema.json",
        "articles": [
            {
                "id": "aaaaaaaaaaaaaaaa",
                "url": "https://example.com/a",
                "title": "Noticia",
                "source": "Fonte",
                "published_at": "2026-03-01T10:00:00Z",
                "collected_at": "2026-03-01T10:05:00Z",
                "status": "validated",
                "candidates_mentioned": ["lula"],
                "topics": ["economia"],
                "summaries": {"pt-BR": "Resumo", "en-US": "Summary"},
            }
        ],
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    articles_file.write_text(json.dumps(articles_payload, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(quiz_positions, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(quiz_positions, "QUIZ_FILE", quiz_file)
    monkeypatch.setattr(quiz_positions, "SCHEMA_FILE", schema_file)
    monkeypatch.setattr(quiz_positions, "_SNIPPETS_CACHE", {})
    monkeypatch.setattr(quiz_positions, "filter_snippets", lambda _articles, candidate, topic: [f"{candidate}:{topic}:snippet"])

    def fake_extract_candidate_position(candidate: str, topic_id: str, snippets: list[str]) -> dict[str, Any]:
        del snippets
        candidate_index = quiz_positions.CANDIDATES.index(candidate)
        stance_cycle = ["favor", "neutral", "against"]
        stance = stance_cycle[candidate_index % len(stance_cycle)]
        return {
            "position_pt": f"O governo deve ampliar as políticas de {topic_id} com metas claras e financiamento adequado.",
            "position_en": f"The government should expand {topic_id} policies with clear goals and adequate funding.",
            "stance": stance,
            "confidence": "high",
            "best_source_snippet_index": 1,
        }

    monkeypatch.setattr(quiz_positions, "extract_candidate_position", fake_extract_candidate_position)

    quiz_positions.main()

    payload = json.loads(quiz_file.read_text(encoding="utf-8"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    ordered_topics = payload.get("ordered_topics", [])
    assert isinstance(ordered_topics, list)
    assert 1 <= len(ordered_topics) <= 15

    for topic_id in ordered_topics:
        topic = payload["topics"][topic_id]
        options = topic["options"]
        assert isinstance(options, list)
        assert len(options) >= 2
        for option in options:
            assert option["confidence"] in {"high", "medium"}
            assert -2 <= option["weight"] <= 2
            for slug in quiz_positions.CANDIDATES:
                assert slug not in option["text_pt"].lower()
                assert slug not in option["text_en"].lower()


def test_local_quality_check_valid_position() -> None:
    """A well-formed policy stance passes the quality check."""
    text_pt = "O governo deve ampliar investimentos em infraestrutura e priorizar empregos formais para todos os brasileiros."
    text_en = "The government should expand infrastructure investment and prioritize formal jobs for all Brazilians."
    assert quiz_positions._local_quality_check(text_pt, text_en) is True


def test_local_quality_check_rejects_polling_data() -> None:
    """Text containing approval/polling data is rejected."""
    text_pt = "O candidato tem aprovação de 43% e desaprovação de 51% segundo pesquisa Ipsos."
    text_en = "The candidate has an approval rating of 43% according to a survey."
    assert quiz_positions._local_quality_check(text_pt, text_en) is False


def test_local_quality_check_rejects_investigation_text() -> None:
    """Text describing an investigation or scandal is rejected."""
    text_pt = "O candidato está sob investigação por desvio de verbas públicas."
    text_en = "The candidate is under investigation for misuse of public funds."
    assert quiz_positions._local_quality_check(text_pt, text_en) is False


def test_local_quality_check_rejects_null_string() -> None:
    """The literal string 'null' is rejected."""
    assert quiz_positions._local_quality_check("null", "null") is False


def test_local_quality_check_rejects_empty_string() -> None:
    """Empty strings are rejected."""
    assert quiz_positions._local_quality_check("", "") is False


def test_local_quality_check_rejects_too_short() -> None:
    """Texts with fewer than 8 words are rejected."""
    assert quiz_positions._local_quality_check("Contra impostos.", "Against taxes.") is False


def test_local_quality_check_rejects_template_placeholder() -> None:
    """Template text from the AI prompt leaking into the output is rejected."""
    text_pt = "posicao em portugues, ou null"
    text_en = "position in English, or null"
    assert quiz_positions._local_quality_check(text_pt, text_en) is False


def test_local_quality_check_rejects_article_meta_commentary() -> None:
    """Text that describes the article rather than a policy stance is rejected."""
    text_pt = "O texto apresenta diversas críticas ao candidato e menciona baixa aprovação."
    text_en = "The text presents various criticisms of the candidate and mentions low approval."
    assert quiz_positions._local_quality_check(text_pt, text_en) is False

