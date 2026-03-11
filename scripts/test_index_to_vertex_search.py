"""Unit tests for scripts/index_to_vertex_search.py."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts import index_to_vertex_search


def _make_article(
    url: str = "https://example.com/1",
    title: str = "Test Article",
    summaries: dict[str, str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Create a minimal article dict with auto-generated sha256 ID.

    Returns dict with required fields from articles.schema.json.
    """
    article: dict[str, Any] = {
        "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
        "url": url,
        "title": title,
        "source": "Example Source",
        "source_category": "mainstream",
        "published_at": "2026-03-11T10:00:00Z",
        "collected_at": "2026-03-11T10:05:00Z",
        "status": "raw",
        "candidates_mentioned": ["lula"],
    }
    if summaries is not None:
        article["summaries"] = summaries
    article.update(overrides)
    return article


def test_indexer_handles_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """main() exits with code 0 and logs warning when GCP credentials are absent.

    - Unset GCP_PROJECT_ID, VERTEX_SEARCH_ENGINE_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON
    - Call main()
    - Assert exit code 0 (not crash)
    - Assert warning message in stderr or log output
    """
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("VERTEX_SEARCH_ENGINE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)

    index_to_vertex_search.main()

    captured = capsys.readouterr()
    combined_output = f"{captured.out}\n{captured.err}"
    assert (
        "Missing required environment variables" in combined_output
        or "Missing required environment variables" in caplog.text
    )


def test_indexer_handles_missing_engine_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """main() exits cleanly when VERTEX_SEARCH_ENGINE_ID is missing but other vars set.

    - Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS_JSON
    - Unset VERTEX_SEARCH_ENGINE_ID
    - Call main()
    - Assert exit code 0 with warning
    """
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", '{"type":"service_account"}')
    monkeypatch.delenv("VERTEX_SEARCH_ENGINE_ID", raising=False)

    index_to_vertex_search.main()

    captured = capsys.readouterr()
    combined_output = f"{captured.out}\n{captured.err}"
    assert "VERTEX_SEARCH_ENGINE_ID" in combined_output or "VERTEX_SEARCH_ENGINE_ID" in caplog.text


def test_document_format() -> None:
    """_article_to_document() produces correct Discovery Engine document structure.

    Given an article with id, title, summaries["pt-BR"], summaries["en-US"]:
    - document["id"] == article["id"]
    - document content raw_text contains title + pt-BR summary + en-US summary
    - document struct_data is the full article object
    """
    article = _make_article(summaries={"pt-BR": "Resumo PT", "en-US": "Summary EN"})
    document = index_to_vertex_search._article_to_document(article)

    assert document["id"] == article["id"]
    assert article["title"] in document["content"]["raw_text"]
    assert "Resumo PT" in document["content"]["raw_text"]
    assert "Summary EN" in document["content"]["raw_text"]
    assert document["struct_data"] == article


def test_document_format_without_summaries() -> None:
    """_article_to_document() handles articles without summaries field.

    Given an article with no summaries key:
    - raw_text contains title only (no crash)
    """
    article = _make_article(summaries=None)
    document = index_to_vertex_search._article_to_document(article)

    assert document["content"]["raw_text"] == article["title"]


def test_idempotent_upsert() -> None:
    """Indexing the same article twice produces one document, not duplicates.

    - Mock DocumentServiceClient.import_documents()
    - Call _index_documents() with 2 identical articles (same ID)
    - Assert the mock receives deduplicated documents
    OR: Assert that the import call uses upsert semantics (same ID overwrites)
    """
    article = _make_article(summaries={"pt-BR": "Resumo", "en-US": "Summary"})
    document = index_to_vertex_search._article_to_document(article)

    with patch("scripts.index_to_vertex_search.discoveryengine.DocumentServiceClient") as mock_client_class:
        mock_client = MagicMock()
        mock_operation = MagicMock()
        mock_operation.result.return_value = None
        mock_client.import_documents.return_value = mock_operation
        mock_client_class.return_value = mock_client
        mock_client_class.branch_path.return_value = (
            "projects/test-project/locations/global/collections/default_collection/"
            "dataStores/test-engine/branches/default_branch"
        )

        success = index_to_vertex_search._index_documents(
            project_id="test-project",
            engine_id="test-engine",
            documents=[document, document],
        )

    assert success is True
    call_kwargs = mock_client.import_documents.call_args.kwargs
    request = call_kwargs["request"]
    assert len(request.inline_source.documents) == 1
    assert request.inline_source.documents[0].id == article["id"]


def test_load_articles_handles_missing_file(tmp_path: Path) -> None:
    """_load_articles() returns empty list when file does not exist."""
    missing_path = tmp_path / "does-not-exist.json"
    assert index_to_vertex_search._load_articles(missing_path) == []


def test_load_articles_handles_invalid_json(tmp_path: Path) -> None:
    """_load_articles() returns empty list on malformed JSON."""
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{invalid-json", encoding="utf-8")
    assert index_to_vertex_search._load_articles(invalid_path) == []
