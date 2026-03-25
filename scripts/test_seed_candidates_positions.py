from __future__ import annotations

from typing import Any

import pytest

from scripts import seed_candidates_positions


def test_senado_fetch_votacoes_supports_new_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "VotacaoParlamentar": {
            "Parlamentar": {
                "Votacoes": {
                    "Votacao": [
                        {
                            "DescricaoVotacao": "Texto",
                            "SiglaDescricaoVoto": "Sim",
                        }
                    ]
                }
            }
        }
    }

    monkeypatch.setattr(
        seed_candidates_positions, "_http_get_json", lambda *_a, **_k: payload
    )

    items = seed_candidates_positions._senado_fetch_votacoes("5894")

    assert len(items) == 1
    assert items[0]["SiglaDescricaoVoto"] == "Sim"


def test_fetch_senado_snippets_uses_current_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_votacoes: list[dict[str, Any]] = [
        {
            "DescricaoVotacao": "Projeto sobre educação básica",
            "SiglaDescricaoVoto": "Sim",
            "SessaoPlenaria": {"DataSessao": "2025-06-01"},
        }
    ]
    monkeypatch.setattr(
        seed_candidates_positions,
        "_senado_fetch_votacoes",
        lambda _codigo: fake_votacoes,
    )

    snippets = seed_candidates_positions.fetch_senado_snippets("flavio-bolsonaro")

    assert "educacao" in snippets
    assert "votou 'Sim'" in snippets["educacao"][0]
    assert "2025-06-01" in snippets["educacao"][0]


def test_seed_single_caps_and_prioritizes_snippets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_snippets: list[str] = []

    def fake_extract(**kwargs: Any) -> dict[str, Any]:
        nonlocal captured_snippets
        snippets = kwargs.get("snippets")
        if isinstance(snippets, list):
            captured_snippets = list(snippets)
        return {
            "position_type": "inferred",
            "stance": "favor",
            "summary_pt": "Resumo",
            "summary_en": "Summary",
            "key_actions": [],
        }

    monkeypatch.setattr(
        seed_candidates_positions,
        "extract_candidate_topic_position",
        fake_extract,
    )
    monkeypatch.setattr(
        seed_candidates_positions,
        "_extract_topic_paragraphs",
        lambda _text, _topic: [f"wiki{i}" for i in range(1, 9)],
    )
    monkeypatch.setattr(
        seed_candidates_positions,
        "fetch_party_snippets",
        lambda _slug, _topic: ["party1", "party2", "party3"],
    )
    monkeypatch.setattr(
        seed_candidates_positions,
        "fetch_web_snippets",
        lambda _slug, _topic: ["web1", "web2", "web3"],
    )

    result = seed_candidates_positions._seed_single(
        candidate_slug="lula",
        topic_id="educacao",
        topic_label_pt="Educação",
        wiki_text="wiki",
        camara_snippets_for_topic=["cam1", "cam2", "cam3", "cam4", "cam5"],
        senado_snippets_for_topic=["sen1", "sen2", "sen3", "sen4", "sen5"],
        skip_web_search=False,
    )

    assert result is not None
    assert captured_snippets == [
        "cam1",
        "cam2",
        "cam3",
        "cam4",
        "sen1",
        "sen2",
        "sen3",
        "sen4",
        "party1",
        "party2",
        "wiki1",
        "wiki2",
    ]
    assert result["sources_used"] == [
        "camara_api",
        "senado_api",
        "party_profile",
        "wikipedia",
    ]
