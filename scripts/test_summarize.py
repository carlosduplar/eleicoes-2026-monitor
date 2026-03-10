from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts import analyze_sentiment, deduplicate_narratives, summarize


def _write_articles(path: Path, articles: list[dict[str, Any]]) -> None:
    payload = {"$schema": "../docs/schemas/articles.schema.json", "articles": articles}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_articles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["articles"] if isinstance(payload, dict) else payload


@pytest.fixture
def tmp_data_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    articles_file = tmp_path / "articles.json"
    pipeline_errors_file = tmp_path / "pipeline_errors.json"
    sentiment_file = tmp_path / "sentiment.json"

    pipeline_errors_file.write_text(json.dumps({"errors": [], "last_checked": None}, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(summarize, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(summarize, "PIPELINE_ERRORS_FILE", pipeline_errors_file)
    monkeypatch.setattr(analyze_sentiment, "ARTICLES_FILE", articles_file)
    monkeypatch.setattr(analyze_sentiment, "PIPELINE_ERRORS_FILE", pipeline_errors_file)
    monkeypatch.setattr(analyze_sentiment, "SENTIMENT_FILE", sentiment_file)
    monkeypatch.setattr(deduplicate_narratives, "ARTICLES_FILE", articles_file)

    return {
        "articles": articles_file,
        "pipeline_errors": pipeline_errors_file,
        "sentiment": sentiment_file,
    }


def test_summarize_skips_already_done(tmp_data_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_articles(
        tmp_data_paths["articles"],
        [
            {
                "id": "aaaaaaaaaaaaaaaa",
                "url": "https://example.com/a",
                "title": "Titulo",
                "source": "Fonte",
                "source_category": "mainstream",
                "published_at": "2026-03-09T12:00:00Z",
                "collected_at": "2026-03-09T12:10:00Z",
                "status": "raw",
                "summaries": {"pt-BR": "Resumo pronto", "en-US": "Ready summary"},
            }
        ],
    )

    def should_not_be_called(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("ai_client.summarize_article should not be called for already-done article")

    monkeypatch.setattr(summarize.ai_client, "summarize_article", should_not_be_called)
    summarized, errors, skipped = summarize.summarize_articles()

    assert summarized == 0
    assert errors == 0
    assert skipped == 1


def test_summarize_sets_validated_status(tmp_data_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_articles(
        tmp_data_paths["articles"],
        [
            {
                "id": "bbbbbbbbbbbbbbbb",
                "url": "https://example.com/b",
                "title": "Economia em debate",
                "source": "Fonte",
                "source_category": "mainstream",
                "published_at": "2026-03-09T13:00:00Z",
                "collected_at": "2026-03-09T13:10:00Z",
                "status": "raw",
                "summaries": {"pt-BR": "", "en-US": ""},
            }
        ],
    )

    def fake_summarize_article(title: str, content: str, language: str = "pt-BR") -> dict[str, Any]:
        assert title
        assert content
        if language == "pt-BR":
            return {
                "summaries": {"pt-BR": "Resumo PT", "en-US": "Summary EN"},
                "candidates_mentioned": ["Lula"],
                "topics": ["economia"],
                "sentiment_per_candidate": {"Lula": "positivo"},
                "_ai_provider": "nvidia",
                "_ai_model": "qwen-test",
            }
        return {
            "summaries": {"pt-BR": "Resumo PT", "en-US": "Summary EN"},
            "candidates_mentioned": ["Lula"],
            "topics": ["economia"],
            "sentiment_per_candidate": {"Lula": "positivo"},
            "_ai_provider": "nvidia",
            "_ai_model": "qwen-test",
        }

    monkeypatch.setattr(summarize.ai_client, "summarize_article", fake_summarize_article)
    summarize.summarize_articles()
    article = _read_articles(tmp_data_paths["articles"])[0]

    assert article["status"] == "validated"
    assert article["summaries"]["pt-BR"] == "Resumo PT"
    assert article["summaries"]["en-US"] == "Summary EN"
    assert article["confidence_score"] == 1.0
    assert article["edit_history"][-1]["action"] == "validated"


def test_summarize_handles_ai_failure(tmp_data_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_articles(
        tmp_data_paths["articles"],
        [
            {
                "id": "cccccccccccccccc",
                "url": "https://example.com/c",
                "title": "Falha de IA",
                "source": "Fonte",
                "source_category": "mainstream",
                "published_at": "2026-03-09T14:00:00Z",
                "collected_at": "2026-03-09T14:10:00Z",
                "status": "raw",
                "summaries": {"pt-BR": "", "en-US": ""},
            }
        ],
    )

    def fail_summarize(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(summarize.ai_client, "summarize_article", fail_summarize)
    summarized, errors, skipped = summarize.summarize_articles()

    article = _read_articles(tmp_data_paths["articles"])[0]
    log_payload = json.loads(tmp_data_paths["pipeline_errors"].read_text(encoding="utf-8"))

    assert summarized == 0
    assert errors == 1
    assert skipped == 0
    assert article["status"] == "raw"
    assert len(log_payload["errors"]) == 1
    assert "provider timeout" in log_payload["errors"][0]["message"]


def test_sentiment_has_disclaimers(tmp_data_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_articles(
        tmp_data_paths["articles"],
        [
            {
                "id": "dddddddddddddddd",
                "url": "https://example.com/d",
                "title": "Debate presidencial",
                "source": "Fonte",
                "source_category": "mainstream",
                "published_at": "2026-03-09T15:00:00Z",
                "collected_at": "2026-03-09T15:10:00Z",
                "status": "validated",
                "topics": ["economia"],
                "summaries": {"pt-BR": "Resumo", "en-US": "Summary"},
                "sentiment_per_candidate": {},
            }
        ],
    )

    monkeypatch.setattr(
        analyze_sentiment.ai_client,
        "call_with_fallback",
        lambda **_kwargs: {"content": json.dumps({"scores": {"lula": 0.4}}), "provider": "nvidia", "model": "model"},
    )

    payload = analyze_sentiment.analyze_sentiment()
    sentiment_payload = json.loads(tmp_data_paths["sentiment"].read_text(encoding="utf-8"))

    assert payload["disclaimer_pt"]
    assert payload["disclaimer_en"]
    assert sentiment_payload["disclaimer_pt"]
    assert sentiment_payload["disclaimer_en"]


def test_sentiment_is_idempotent(tmp_data_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_articles(
        tmp_data_paths["articles"],
        [
            {
                "id": "eeeeeeeeeeeeeeee",
                "url": "https://example.com/e",
                "title": "Cobertura eleitoral",
                "source": "Fonte",
                "source_category": "mainstream",
                "published_at": "2026-03-09T16:00:00Z",
                "collected_at": "2026-03-09T16:10:00Z",
                "status": "validated",
                "topics": ["economia"],
                "summaries": {"pt-BR": "Resumo", "en-US": "Summary"},
                "sentiment_per_candidate": {},
            }
        ],
    )

    monkeypatch.setattr(
        analyze_sentiment.ai_client,
        "call_with_fallback",
        lambda **_kwargs: {"content": json.dumps({"scores": {"lula": 0.2}}), "provider": "nvidia", "model": "model"},
    )

    analyze_sentiment.analyze_sentiment()
    first_output = tmp_data_paths["sentiment"].read_text(encoding="utf-8")
    analyze_sentiment.analyze_sentiment()
    second_output = tmp_data_paths["sentiment"].read_text(encoding="utf-8")

    assert first_output == second_output


def test_cosine_dedup_clusters_similar(tmp_data_paths: dict[str, Path]) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_articles(
        tmp_data_paths["articles"],
        [
            {
                "id": "ffffffffffffffff",
                "url": "https://example.com/f",
                "title": "Caiado critica proposta de impostos no debate",
                "source": "Fonte A",
                "source_category": "mainstream",
                "published_at": now,
                "collected_at": now,
                "status": "validated",
            },
            {
                "id": "1111111111111111",
                "url": "https://example.com/g",
                "title": "Caiado critica proposta de impostos no debate televisivo",
                "source": "Fonte B",
                "source_category": "politics",
                "published_at": now,
                "collected_at": now,
                "status": "validated",
            },
        ],
    )

    deduplicate_narratives.deduplicate_narratives()
    articles = _read_articles(tmp_data_paths["articles"])

    assert articles[0]["narrative_cluster_id"] is not None
    assert articles[0]["narrative_cluster_id"] == articles[1]["narrative_cluster_id"]
