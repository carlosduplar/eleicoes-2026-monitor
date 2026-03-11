"""Index articles from data/articles.json into Google Vertex AI Search (Discovery Engine).

Environment variables (all required for indexing, graceful exit if missing):
  - GCP_PROJECT_ID: Google Cloud project ID
  - VERTEX_SEARCH_ENGINE_ID: Discovery Engine search engine ID
  - GOOGLE_APPLICATION_CREDENTIALS_JSON: Service account JSON key (string, not path)

Usage:
  python scripts/index_to_vertex_search.py
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from google.cloud import discoveryengine_v1 as discoveryengine

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "articles.json"
_REQUIRED_ENV_VARS = ("GCP_PROJECT_ID", "VERTEX_SEARCH_ENGINE_ID", "GOOGLE_APPLICATION_CREDENTIALS_JSON")


def _check_env_vars() -> tuple[str, str, str] | None:
    """Check for required environment variables.

    Returns:
        Tuple of (project_id, engine_id, credentials_json) if all present,
        None if any are missing (logs warning).
    """
    values = {name: os.getenv(name, "").strip() for name in _REQUIRED_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        logger.warning(
            "Missing required environment variables for Vertex indexing: %s. Skipping indexing.",
            ", ".join(missing),
        )
        return None
    return (
        values["GCP_PROJECT_ID"],
        values["VERTEX_SEARCH_ENGINE_ID"],
        values["GOOGLE_APPLICATION_CREDENTIALS_JSON"],
    )


def _write_credentials_file(credentials_json: str) -> str:
    """Write service account JSON to a temp file for google-auth.

    Args:
        credentials_json: Raw JSON string of the service account key.

    Returns:
        Path to the temp file (caller must clean up or let OS handle).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as handle:
        handle.write(credentials_json)
        handle.flush()
        return handle.name


def _load_articles(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load and return articles from the JSON file.

    Args:
        path: Path to articles.json.

    Returns:
        List of article dicts. Empty list on read error.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Articles file not found at %s", path)
        return []
    except (OSError, json.JSONDecodeError) as error:
        logger.error("Failed to load articles from %s: %s", path, error)
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)]

    logger.warning("Unsupported articles payload format in %s", path)
    return []


def _article_to_document(article: dict[str, Any]) -> dict[str, Any]:
    """Transform an article dict into a Discovery Engine document dict.

    The document structure:
      - id: article["id"]
      - content.raw_text: title + " " + summaries["pt-BR"] + " " + summaries["en-US"]
      - struct_data: full article object

    Args:
        article: Article dict conforming to articles.schema.json.

    Returns:
        Dict suitable for Discovery Engine import_documents().
    """
    summaries = article.get("summaries")
    summaries_map = summaries if isinstance(summaries, dict) else {}
    title = str(article.get("title") or "").strip()
    summary_pt = str(summaries_map.get("pt-BR") or "").strip()
    summary_en = str(summaries_map.get("en-US") or "").strip()
    raw_text = " ".join(part for part in (title, summary_pt, summary_en) if part)

    return {
        "id": str(article.get("id") or ""),
        "content": {"raw_text": raw_text},
        "struct_data": article,
    }


def _to_discovery_document(document: dict[str, Any]) -> discoveryengine.Document:
    content = document.get("content")
    content_map = content if isinstance(content, dict) else {}
    raw_text = str(content_map.get("raw_text") or "")
    struct_data = document.get("struct_data")
    struct_map = struct_data if isinstance(struct_data, dict) else {}

    return discoveryengine.Document(
        id=str(document.get("id") or ""),
        struct_data=struct_map,
        content=discoveryengine.Document.Content(
            raw_bytes=raw_text.encode("utf-8"),
            mime_type="text/plain",
        ),
    )


def _index_documents(
    project_id: str,
    engine_id: str,
    documents: list[dict[str, Any]],
) -> bool:
    """Batch import documents into Discovery Engine data store.

    Uses DocumentServiceClient.import_documents() for upsert.
    Documents with existing IDs are updated (idempotent).

    Args:
        project_id: GCP project ID.
        engine_id: Vertex Search engine ID.
        documents: List of document dicts from _article_to_document().

    Returns:
        True on success, False on failure.
    """
    deduped_by_id: dict[str, dict[str, Any]] = {}
    for document in documents:
        doc_id = str(document.get("id") or "").strip()
        if doc_id:
            deduped_by_id[doc_id] = document

    deduped_documents = list(deduped_by_id.values())
    if not deduped_documents:
        logger.info("No documents to index.")
        return True

    parent = discoveryengine.DocumentServiceClient.branch_path(
        project=project_id,
        location="global",
        data_store=engine_id,
        branch="default_branch",
    )

    try:
        client = discoveryengine.DocumentServiceClient()
        request = discoveryengine.ImportDocumentsRequest(
            parent=parent,
            inline_source=discoveryengine.ImportDocumentsRequest.InlineSource(
                documents=[_to_discovery_document(document) for document in deduped_documents]
            ),
            reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        )
        operation = client.import_documents(request=request)
        operation.result()
        logger.info("Indexed %s document(s) into Vertex AI Search.", len(deduped_documents))
        return True
    except Exception as error:  # pragma: no cover - covered by mocked test path
        logger.error("Vertex indexing failed: %s", error)
        return False


def main() -> None:
    """Entry point. Exits cleanly (code 0) if credentials are missing."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    env_values = _check_env_vars()
    if env_values is None:
        return

    project_id, engine_id, credentials_json = env_values

    credentials_path: str | None = None
    try:
        credentials_path = _write_credentials_file(credentials_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    except (OSError, TypeError, ValueError) as error:
        logger.error("Failed to prepare credentials file: %s", error)
        return

    try:
        articles = _load_articles(DATA_PATH)
        if not articles:
            logger.warning("No articles available for indexing at %s", DATA_PATH)
            return

        documents = [_article_to_document(article) for article in articles]
        _index_documents(project_id, engine_id, documents)
    finally:
        if credentials_path:
            try:
                Path(credentials_path).unlink(missing_ok=True)
            except OSError as error:
                logger.warning("Failed to remove temp credentials file: %s", error)


if __name__ == "__main__":
    main()
