"""Unit tests for Sources E & F added to scripts/seed_candidates_positions.py."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from scripts import seed_candidates_positions as seed


def _fake_response(status_code: int = 200, payload: object | None = None) -> object:
    class _Response:
        def __init__(self) -> None:
            self.status_code = status_code

        def json(self) -> object:
            return payload

    return _Response()


# ── Source E: fetch_party_snippets ──────────────────────────────────────


def test_fetch_party_snippets_known_candidate_and_topic() -> None:
    """Returns a non-empty list for a known candidate/topic pair."""
    result = seed.fetch_party_snippets("tarcisio", "armas")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]  # non-empty string


def test_fetch_party_snippets_unknown_candidate_returns_empty() -> None:
    """Returns [] without raising for an unknown candidate slug."""
    result = seed.fetch_party_snippets("unknown-candidate", "armas")
    assert result == []


def test_fetch_party_snippets_unknown_topic_returns_empty() -> None:
    """Returns [] without raising for an unknown topic_id."""
    result = seed.fetch_party_snippets("lula", "unknown_topic_xyz")
    assert result == []


def test_fetch_party_snippets_all_candidates_have_profiles() -> None:
    """All nine candidates in PARTY_IDEOLOGICAL_PROFILES have an armas entry."""
    for slug in seed.CANDIDATE_WIKI_TITLES:
        result = seed.fetch_party_snippets(slug, "armas")
        assert isinstance(result, list), f"Expected list for {slug}"
        assert len(result) == 1, f"Expected 1 snippet for {slug}/armas"


def test_fetch_party_snippets_all_topics_covered_for_lula() -> None:
    """All 11 topics in TOPIC_KEYWORDS are covered for 'lula'."""
    for topic_id in seed.TOPIC_KEYWORDS:
        result = seed.fetch_party_snippets("lula", topic_id)
        assert isinstance(result, list), f"Expected list for lula/{topic_id}"
        assert len(result) == 1, f"Expected 1 snippet for lula/{topic_id}"


# ── Source F: _brave_search ─────────────────────────────────────────────


def test_brave_search_parses_descriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parses web.results[].description from a Brave Search JSON response."""
    fake_response = {
        "web": {
            "results": [
                {"description": "Snippet one about topic"},
                {"description": "Snippet two about topic"},
                {"title": "missing description"},
                {"description": ""},
            ]
        }
    }
    monkeypatch.setattr(seed, "BRAVE_API_KEY", "test-key")
    response = _fake_response(payload=fake_response)
    with patch.object(seed.requests, "get", return_value=response) as mock_get:
        with patch("time.sleep"):
            result = seed._brave_search("test query", max_results=5)
    assert mock_get.call_args.kwargs["params"]["count"] == 5
    assert result == ["Snippet one about topic", "Snippet two about topic"]


def test_brave_search_respects_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns at most max_results snippets."""
    fake_response = {
        "web": {"results": [{"description": f"Item {i}"} for i in range(10)]}
    }
    monkeypatch.setattr(seed, "BRAVE_API_KEY", "test-key")
    with patch.object(seed.requests, "get", return_value=_fake_response(payload=fake_response)):
        with patch("time.sleep"):
            result = seed._brave_search("query", max_results=3)
    assert len(result) == 3


def test_brave_search_returns_empty_without_api_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Returns [] with a warning when BRAVE_SEARCH_API_KEY is missing."""
    monkeypatch.setattr(seed, "BRAVE_API_KEY", None)
    with caplog.at_level(logging.WARNING):
        result = seed._brave_search("query")
    assert result == []
    assert "BRAVE_SEARCH_API_KEY not set" in caplog.text


def test_brave_search_returns_empty_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns [] gracefully when Brave returns a non-200 response."""
    monkeypatch.setattr(seed, "BRAVE_API_KEY", "test-key")
    with patch.object(seed.requests, "get", return_value=_fake_response(status_code=503)):
        result = seed._brave_search("query")
    assert result == []


def test_brave_search_returns_empty_on_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns [] gracefully when requests raises a RequestException."""
    monkeypatch.setattr(seed, "BRAVE_API_KEY", "test-key")
    with patch.object(seed.requests, "get", side_effect=requests.RequestException("boom")):
        result = seed._brave_search("query")
    assert result == []


# ── Source F: fetch_web_snippets ────────────────────────────────────────


def test_fetch_web_snippets_unknown_candidate_returns_empty() -> None:
    """Returns [] without raising for a candidate not in CANDIDATE_FULL_NAMES."""
    result = seed.fetch_web_snippets("unknown-candidate", "armas")
    assert result == []


def test_fetch_web_snippets_calls_web_search_with_correct_query() -> None:
    """Builds the right query and passes it to _brave_search."""
    captured_queries: list[str] = []
    captured_limits: list[int] = []

    def fake_search(query: str, max_results: int = 5) -> list[str]:
        captured_queries.append(query)
        captured_limits.append(max_results)
        return ["resultado"]

    with patch.object(seed, "_brave_search", side_effect=fake_search):
        result = seed.fetch_web_snippets("lula", "meio_ambiente")

    assert result == ["resultado"]
    assert len(captured_queries) == 1
    assert captured_limits == [5]
    query = captured_queries[0]
    assert "Luiz Inácio Lula da Silva" in query
    assert "posição" in query
    assert "site:.br" in query


def test_fetch_web_snippets_returns_list_of_strings() -> None:
    """Return value is always a list of strings."""
    fake_snippets = ["texto A", "texto B"]
    with patch.object(seed, "_brave_search", return_value=fake_snippets):
        result = seed.fetch_web_snippets("lula", "meio_ambiente")
    assert result == fake_snippets


# ── seed_positions: --skip-web-search flag ──────────────────────────────


def test_seed_positions_skip_web_search_does_not_call_fetch_web_snippets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When skip_web_search=True, fetch_web_snippets is never called."""
    # Minimal valid positions payload
    positions_payload = {
        "schema_version": "2.0.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "editors": [],
        "topics": {
            "armas": {
                "topic_label_pt": "armas",
                "topic_label_en": "guns",
                "candidates": {
                    "tarcisio": {
                        "stance": "unknown",
                        "position_type": "unknown",
                        "summary_pt": None,
                        "summary_en": None,
                        "key_actions": [],
                        "sources": [],
                        "last_updated": None,
                        "editor_notes": None,
                    }
                },
            }
        },
    }

    positions_file = tmp_path / "candidates_positions.json"
    schema_src = (
        seed.ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"
    )
    schema_dst = tmp_path / "candidates_positions.schema.json"
    positions_file.write_text(
        json.dumps(positions_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(seed, "POSITIONS_FILE", positions_file)
    monkeypatch.setattr(seed, "SCHEMA_FILE", schema_dst)

    web_search_called = []

    def fake_web_snippets(slug: str, topic_id: str) -> list[str]:
        web_search_called.append((slug, topic_id))
        return []

    monkeypatch.setattr(seed, "fetch_web_snippets", fake_web_snippets)

    # Stub out external I/O that would fail in unit tests
    monkeypatch.setattr(seed, "fetch_wikipedia_snippets", lambda slug: [])
    monkeypatch.setattr(seed, "fetch_camara_snippets", lambda slug: {})
    monkeypatch.setattr(seed, "fetch_senado_snippets", lambda slug: {})
    monkeypatch.setattr(
        seed,
        "extract_candidate_topic_position",
        lambda **kw: {
            "position_type": "unknown",
            "stance": "unknown",
            "summary_pt": None,
            "summary_en": None,
            "key_actions": [],
        },
    )

    seed.seed_positions(dry_run=True, skip_web_search=True)

    assert web_search_called == [], "fetch_web_snippets must not be called with --skip-web-search"


def test_seed_positions_warns_when_brave_key_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warns once when Source F is enabled without BRAVE_SEARCH_API_KEY."""
    positions_payload = {
        "schema_version": "2.0.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "editors": [],
        "topics": {
            "armas": {
                "topic_label_pt": "armas",
                "topic_label_en": "guns",
                "candidates": {
                    "tarcisio": {
                        "stance": "unknown",
                        "position_type": "unknown",
                        "summary_pt": None,
                        "summary_en": None,
                        "key_actions": [],
                        "sources": [],
                        "last_updated": None,
                        "editor_notes": None,
                    }
                },
            }
        },
    }

    positions_file = tmp_path / "candidates_positions.json"
    schema_src = (
        seed.ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"
    )
    schema_dst = tmp_path / "candidates_positions.schema.json"
    positions_file.write_text(
        json.dumps(positions_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(seed, "POSITIONS_FILE", positions_file)
    monkeypatch.setattr(seed, "SCHEMA_FILE", schema_dst)
    monkeypatch.setattr(seed, "BRAVE_API_KEY", None)
    monkeypatch.setattr(seed, "fetch_wikipedia_snippets", lambda slug: [])
    monkeypatch.setattr(seed, "fetch_camara_snippets", lambda slug: {})
    monkeypatch.setattr(seed, "fetch_senado_snippets", lambda slug: {})
    monkeypatch.setattr(seed, "fetch_web_snippets", lambda slug, topic_id: [])
    monkeypatch.setattr(seed, "fetch_party_snippets", lambda slug, topic_id: [])
    monkeypatch.setattr(
        seed,
        "extract_candidate_topic_position",
        lambda **kw: {
            "position_type": "unknown",
            "stance": "unknown",
            "summary_pt": None,
            "summary_en": None,
            "key_actions": [],
        },
    )

    with caplog.at_level(logging.WARNING):
        seed.seed_positions(dry_run=True, skip_web_search=False)

    assert "BRAVE_SEARCH_API_KEY not set — Source F will produce no snippets" in caplog.text


def test_seed_positions_sources_include_party_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """dry-run output for tarcisio/armas includes 'party_profile' in sources."""
    positions_payload = {
        "schema_version": "2.0.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "editors": [],
        "topics": {
            "armas": {
                "topic_label_pt": "armas",
                "topic_label_en": "guns",
                "candidates": {
                    "tarcisio": {
                        "stance": "unknown",
                        "position_type": "unknown",
                        "summary_pt": None,
                        "summary_en": None,
                        "key_actions": [],
                        "sources": [],
                        "last_updated": None,
                        "editor_notes": None,
                    }
                },
            }
        },
    }

    positions_file = tmp_path / "candidates_positions.json"
    schema_src = (
        seed.ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"
    )
    schema_dst = tmp_path / "candidates_positions.schema.json"
    positions_file.write_text(
        json.dumps(positions_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(seed, "POSITIONS_FILE", positions_file)
    monkeypatch.setattr(seed, "SCHEMA_FILE", schema_dst)
    monkeypatch.setattr(seed, "fetch_wikipedia_snippets", lambda slug: [])
    monkeypatch.setattr(seed, "fetch_camara_snippets", lambda slug: {})
    monkeypatch.setattr(seed, "fetch_senado_snippets", lambda slug: {})
    monkeypatch.setattr(seed, "fetch_web_snippets", lambda slug, topic: [])
    monkeypatch.setattr(
        seed,
        "extract_candidate_topic_position",
        lambda **kw: {
            "position_type": "favor",
            "stance": "support",
            "summary_pt": "Favorável",
            "summary_en": "In favour",
            "key_actions": [],
        },
    )

    seed.seed_positions(dry_run=True, skip_web_search=True)

    out = capsys.readouterr().out
    assert "party_profile" in out
