# Phase 17 — Task 01 Spec (Vertex AI Search: Semantic Search with Local Fallback)

> Planner: Opus 4.6 | Implementor: Codex | Date: 2026-03-11

---

## 1. Inputs and Mandatory References

| # | Ref | Path | Purpose |
|---|-----|------|---------|
| 1 | Architecture spec | `plans/phase-17-arch.md` | Phase objectives, deliverables, acceptance criteria |
| 2 | Agent protocol | `docs/agent-protocol.md` | RALPH loop, escalation rules, handoff files |
| 3 | TypeScript types | `docs/schemas/types.ts` | `Article`, `ArticleStatus`, `SourceCategory`, `CandidateSlug` |
| 4 | Articles schema | `docs/schemas/articles.schema.json` | Required: `id`, `url`, `title`, `source`, `published_at`, `collected_at`, `status`; Optional: `summaries`, `candidates_mentioned` |
| 5 | Existing hook: useData | `site/src/hooks/useData.js` | Memory-cached data fetch pattern — useSearch must follow same conventions |
| 6 | Existing component: NewsFeed | `site/src/components/NewsFeed.jsx` | Target for search bar integration; uses `useData('articles')`, `normalizeArticles()`, category filter |
| 7 | Existing component: SourceFilter | `site/src/components/SourceFilter.jsx` | Search bar renders above this component in the Home page |
| 8 | i18n pt-BR | `site/src/locales/pt-BR/common.json` | Must add `search.*` keys |
| 9 | i18n en-US | `site/src/locales/en-US/common.json` | Must add `search.*` keys |
| 10 | Collect workflow | `.github/workflows/collect.yml` | Add Vertex indexing step after `build_data.py` |
| 11 | Deploy workflow | `.github/workflows/deploy.yml` | May need `VITE_VERTEX_SEARCH_URL` env var for build |
| 12 | Existing ADRs | `docs/adr/000-006*.md` | 007 is the next ADR number |
| 13 | requirements.txt | `requirements.txt` | Add `google-cloud-discoveryengine>=0.11.0` |
| 14 | Playwright test pattern | `qa/tests/test_home.spec.js` | Import path, locator conventions, `waitForLoadState` pattern |
| 15 | Playwright config | `site/playwright.config.js` | `testDir: '../qa/tests'`, baseURL, project setup |
| 16 | WF-01 wireframe | `docs/wireframes/WF-01-feed-desktop.html` | Search bar placement reference |
| 17 | site package.json | `site/package.json` | Scripts: `dev`, `build`, `preview`, `test:e2e` |

---

## 2. Files to Create or Modify

### 2.1 Python Script + Tests (CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `scripts/index_to_vertex_search.py` | CREATE | Indexes `data/articles.json` into Vertex AI Search via Discovery Engine API |
| 2 | `scripts/test_index_to_vertex_search.py` | CREATE | Unit tests: missing credentials, missing engine ID, document format, idempotent upsert |

### 2.2 React Hook (CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 3 | `site/src/hooks/useSearch.js` | CREATE | Semantic search hook with Vertex API + local fallback |

### 2.3 Frontend Components (MODIFY)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 4 | `site/src/components/NewsFeed.jsx` | MODIFY | Add search input above SourceFilter, debounced 300ms, integrate `useSearch` |

### 2.4 i18n Locales (MODIFY)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 5 | `site/src/locales/pt-BR/common.json` | MODIFY | Add `search.*` keys (placeholder, semantic badge, local badge, no results) |
| 6 | `site/src/locales/en-US/common.json` | MODIFY | Add `search.*` keys (English equivalents) |

### 2.5 CI/CD + Config (MODIFY/CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 7 | `requirements.txt` | MODIFY | Append `google-cloud-discoveryengine>=0.11.0` |
| 8 | `.github/workflows/collect.yml` | MODIFY | Add "Index to Vertex AI Search" step after AI processing |

### 2.6 Documentation (CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 9 | `docs/adr/007-vertex-search.md` | CREATE | ADR for Vertex AI Search: rationale, fallback strategy, cost model, setup steps |

### 2.7 Playwright Test (CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 10 | `qa/tests/test_search.spec.js` | CREATE | E2E: search input presence, query filtering, empty query restore, fallback badge |

### 2.8 Sentinel Files

| # | Path | Action | Description |
|---|------|--------|-------------|
| 11 | `plans/phase-17-arch.DONE` | CREATE | Architect completion sentinel |

---

## 3. Function Signatures and Types

### 3.1 `scripts/index_to_vertex_search.py` (CREATE)

```python
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
import hashlib
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "articles.json"


def _check_env_vars() -> tuple[str, str, str] | None:
    """Check for required environment variables.

    Returns:
        Tuple of (project_id, engine_id, credentials_json) if all present,
        None if any are missing (logs warning).
    """
    ...


def _write_credentials_file(credentials_json: str) -> str:
    """Write service account JSON to a temp file for google-auth.

    Args:
        credentials_json: Raw JSON string of the service account key.

    Returns:
        Path to the temp file (caller must clean up or let OS handle).
    """
    ...


def _load_articles(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load and return articles from the JSON file.

    Args:
        path: Path to articles.json.

    Returns:
        List of article dicts. Empty list on read error.
    """
    ...


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
    ...


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
    ...


def main() -> None:
    """Entry point. Exits cleanly (code 0) if credentials are missing."""
    ...


if __name__ == "__main__":
    main()
```

**Data contract:** Reads `data/articles.json` (array of `Article` objects per `articles.schema.json`). Each article MUST have at minimum: `id` (hex16), `title` (string). The `summaries` field is optional; if missing, `raw_text` uses title only.

### 3.2 `scripts/test_index_to_vertex_search.py` (CREATE)

```python
"""Unit tests for scripts/index_to_vertex_search.py."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


def _make_article(
    url: str = "https://example.com/1",
    title: str = "Test Article",
    summaries: dict[str, str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Create a minimal article dict with auto-generated sha256 ID.

    Returns dict with required fields from articles.schema.json.
    """
    ...


def test_indexer_handles_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main() exits with code 0 and logs warning when GCP credentials are absent.

    - Unset GCP_PROJECT_ID, VERTEX_SEARCH_ENGINE_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON
    - Call main()
    - Assert exit code 0 (not crash)
    - Assert warning message in stderr or log output
    """
    ...


def test_indexer_handles_missing_engine_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main() exits cleanly when VERTEX_SEARCH_ENGINE_ID is missing but other vars set.

    - Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS_JSON
    - Unset VERTEX_SEARCH_ENGINE_ID
    - Call main()
    - Assert exit code 0 with warning
    """
    ...


def test_document_format() -> None:
    """_article_to_document() produces correct Discovery Engine document structure.

    Given an article with id, title, summaries["pt-BR"], summaries["en-US"]:
    - document["id"] == article["id"]
    - document content raw_text contains title + pt-BR summary + en-US summary
    - document struct_data is the full article object
    """
    ...


def test_document_format_without_summaries() -> None:
    """_article_to_document() handles articles without summaries field.

    Given an article with no summaries key:
    - raw_text contains title only (no crash)
    """
    ...


def test_idempotent_upsert() -> None:
    """Indexing the same article twice produces one document, not duplicates.

    - Mock DocumentServiceClient.import_documents()
    - Call _index_documents() with 2 identical articles (same ID)
    - Assert the mock receives deduplicated documents
    OR: Assert that the import call uses upsert semantics (same ID overwrites)
    """
    ...


def test_load_articles_handles_missing_file(tmp_path: Path) -> None:
    """_load_articles() returns empty list when file does not exist."""
    ...


def test_load_articles_handles_invalid_json(tmp_path: Path) -> None:
    """_load_articles() returns empty list on malformed JSON."""
    ...
```

**Data contract:** Tests must mock `google.cloud.discoveryengine` — never make real API calls. Test articles must include `id` matching `sha256(url)[:16]` pattern.

### 3.3 `site/src/hooks/useSearch.js` (CREATE)

```javascript
/**
 * useSearch — semantic search with local fallback.
 *
 * If VITE_VERTEX_SEARCH_URL is set, uses Vertex AI Search API.
 * Falls back to client-side filtering if Vertex is unavailable or unconfigured.
 *
 * @param {string} query - Search query string.
 * @param {import('../../docs/schemas/types').Article[]} articles - Local article corpus from useData.
 * @returns {{ results: Article[], loading: boolean, error: Error|null, isVertexSearch: boolean }}
 */
export function useSearch(query, articles) {
  // Implementation uses useState + useEffect
  // ...
}

/**
 * Local fallback filter: case-insensitive term matching against
 * article.title, article.summaries["pt-BR"], article.summaries["en-US"],
 * and article.candidates_mentioned[].
 *
 * Returns up to 20 results sorted by published_at descending.
 *
 * @param {string} query - Search terms (space-separated).
 * @param {Article[]} articles - Full article corpus.
 * @returns {Article[]} Filtered and sorted results.
 */
function filterLocal(query, articles) {
  // ...
}

/**
 * Vertex AI Search API call.
 *
 * @param {string} query - Encoded search query.
 * @param {AbortSignal} signal - AbortController signal for cancellation.
 * @returns {Promise<Article[]>} Results from Vertex Search.
 * @throws {Error} On network failure or non-OK response.
 */
async function searchVertex(query, signal) {
  // GET ${VITE_VERTEX_SEARCH_URL}?query=<encoded>&pageSize=20
  // Parse response documents back to Article shape
  // ...
}
```

**Key behaviors:**
- `VITE_VERTEX_SEARCH_URL` read from `import.meta.env.VITE_VERTEX_SEARCH_URL`
- If env var is falsy: always use `filterLocal`, set `isVertexSearch: false`
- If env var is set: attempt `searchVertex`; on failure, silently fall back to `filterLocal`
- AbortController to cancel in-flight requests when query changes
- Empty query (`""`) returns empty `results` array (caller uses full article list)
- `loading` is `true` only during Vertex requests (local filtering is synchronous)

**Data contract:** Consumes `Article[]` from `articles.schema.json`. Reads fields: `id`, `title`, `summaries.pt-BR`, `summaries.en-US`, `candidates_mentioned`, `published_at`. Returns `Article[]` (same shape).

### 3.4 `site/src/components/NewsFeed.jsx` (MODIFY)

Changes to make:

```jsx
// ADD these imports at the top
import { useState, useMemo, useCallback } from 'react';
import { useSearch } from '@/hooks/useSearch';

// INSIDE NewsFeed component, BEFORE the return:

// 1. Add search state
const [searchQuery, setSearchQuery] = useState('');

// 2. Debounced query (300ms)
const [debouncedQuery, setDebouncedQuery] = useState('');
// useEffect for debounce: setTimeout 300ms, cleanup with clearTimeout

// 3. Call useSearch
const { results: searchResults, loading: searchLoading, isVertexSearch } = useSearch(debouncedQuery, articles);

// 4. Determine displayed articles:
//    - If debouncedQuery is non-empty: use searchResults
//    - If debouncedQuery is empty: use visibleArticles (existing category filter)
const displayedArticles = debouncedQuery
  ? searchResults
  : visibleArticles;

// 5. Add search input JSX above the article list, inside feed-stack:
// <div className="feed-search">
//   <input
//     type="search"
//     value={searchQuery}
//     onChange={(e) => setSearchQuery(e.target.value)}
//     placeholder={t('search.placeholder')}
//     aria-label={t('search.aria_label')}
//     className="feed-search-input"
//   />
//   {debouncedQuery && (
//     <span className="feed-search-badge">
//       {isVertexSearch ? t('search.semantic_badge') : t('search.local_badge')}
//     </span>
//   )}
//   {searchLoading && <span className="feed-search-spinner" aria-label={t('search.loading')} />}
// </div>

// 6. Replace visibleArticles.map(...) with displayedArticles.map(...)

// 7. Add no-results state when debouncedQuery is non-empty but results are empty
```

**Data contract:** No new data contracts. Consumes existing `articles.json` via `useData('articles')`. The `useSearch` hook returns `Article[]` matching the same schema.

**UI rules from arch spec:**
- Input renders ABOVE `SourceFilter` (inside `feed-heading` or between heading and cards)
- Placeholder text: i18n key `search.placeholder` ("Buscar noticias..." / "Search news...")
- Badge text: i18n key `search.semantic_badge` or `search.local_badge`
- Loading spinner while Vertex request in-flight
- Empty query restores full article list with category filter active

### 3.5 i18n Keys to Add

**`site/src/locales/pt-BR/common.json`** — add inside the root object:

```json
{
  "search": {
    "placeholder": "Buscar noticias...",
    "aria_label": "Buscar noticias",
    "semantic_badge": "Busca semantica",
    "local_badge": "Busca local",
    "loading": "Buscando...",
    "no_results": "Nenhum resultado encontrado para \"{{query}}\"."
  }
}
```

**`site/src/locales/en-US/common.json`** — add inside the root object:

```json
{
  "search": {
    "placeholder": "Search news...",
    "aria_label": "Search news",
    "semantic_badge": "Semantic search",
    "local_badge": "Local search",
    "loading": "Searching...",
    "no_results": "No results found for \"{{query}}\"."
  }
}
```

### 3.6 `requirements.txt` (MODIFY)

Append at end:
```
google-cloud-discoveryengine>=0.11.0
```

### 3.7 `.github/workflows/collect.yml` (MODIFY)

Add a new step **after** the "AI processing" step and **before** the "Commit data updates" step:

```yaml
      - name: Index to Vertex AI Search
        env:
          GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GOOGLE_APPLICATION_CREDENTIALS_JSON }}
          VERTEX_SEARCH_ENGINE_ID: ${{ secrets.VERTEX_SEARCH_ENGINE_ID }}
          GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
        run: python scripts/index_to_vertex_search.py || echo "[warn] Vertex indexing failed, continuing"
```

**Key constraint:** The `|| echo "[warn]..."` ensures the workflow never fails due to Vertex indexing. This is a progressive enhancement.

### 3.8 `docs/adr/007-vertex-search.md` (CREATE)

```markdown
# ADR 007 — Vertex AI Search (Semantic Search)

## Status

Accepted

## Date

2026-03-11

## Context

Client-side text filtering (`NewsFeed` + `SourceFilter`) matches only exact keywords.
Users searching "posicao de Tarcisio sobre privatizacao" find nothing if articles use
different wording. Vertex AI Search (Discovery Engine / GenAI App Builder) provides
semantic understanding and RAG-compatible retrieval.

## Decision

Implement Vertex AI Search as a **progressive enhancement**:

1. `useSearch` hook attempts Vertex API when `VITE_VERTEX_SEARCH_URL` is set
2. On failure or missing config, silently falls back to client-side filtering
3. The portal is 100% functional without Vertex AI Search

### Naming clarification

- "Discovery Engine" and "Vertex AI Search" refer to the same Google Cloud product
- API: `discoveryengine.googleapis.com`
- Console: AI Applications > Agent Builder > Search App

### Cost model

- Trial credit: 773 CHF (expires 2027-03-02)
- Covers approximately 1M search queries
- Production estimate: ~$0.01/query after trial

### Authentication

- Service account with roles: `Vertex AI User` + `Discovery Engine Admin`
- JSON key stored as GitHub secret `GOOGLE_APPLICATION_CREDENTIALS_JSON`
- `VITE_VERTEX_SEARCH_URL` is a public endpoint URL (not a secret)

## Setup Steps (Manual Prerequisites)

1. Google Cloud Console > AI Applications > Agent Builder
2. Create Search App: type "Generic", data store "JSON"
3. Note the `ENGINE_ID`
4. Create Service Account with roles above
5. Download JSON key > store as GitHub secret
6. Set `VERTEX_SEARCH_ENGINE_ID` and `GCP_PROJECT_ID` as GitHub secrets

## Consequences

- (+) Semantic search over article corpus without exact keyword matching
- (+) RAG-compatible for future LLM integration
- (+) Zero downtime: local fallback always works
- (-) `google-cloud-discoveryengine` adds ~15MB to Python dependencies
- (-) Requires manual GCP setup before Vertex features activate
- (-) Trial credit has expiration date
```

### 3.9 `qa/tests/test_search.spec.js` (CREATE)

```javascript
// @ts-check
import { expect, test } from '../../site/node_modules/@playwright/test/index.js';

test.describe('Search feature', () => {

  test('search input is present on the homepage', async ({ page }) => {
    /**
     * Navigate to /, wait for load.
     * Assert: input[type="search"] is visible.
     * Assert: input has aria-label attribute.
     */
    ...
  });

  test('typing a query filters articles (local fallback)', async ({ page }) => {
    /**
     * Navigate to /, wait for networkidle.
     * Type a known term into the search input.
     * Wait 500ms for debounce to fire.
     * Assert: feed-card count changes OR no-results message appears.
     * Assert: "Busca local" or "Local search" badge is visible
     *         (VITE_VERTEX_SEARCH_URL is not set in test env).
     */
    ...
  });

  test('empty query restores full article list', async ({ page }) => {
    /**
     * Navigate to /, wait for networkidle.
     * Note initial card count.
     * Type a query, wait for debounce.
     * Clear the search input.
     * Wait for debounce.
     * Assert: card count matches initial count (full list restored).
     * Assert: search badge is NOT visible.
     */
    ...
  });

  test('isVertexSearch false shows local badge when Vertex URL not set', async ({ page }) => {
    /**
     * Navigate to /, wait.
     * Type any query.
     * Wait for debounce.
     * Assert: badge text matches "Busca local" or "Local search" (depending on language).
     * Assert: badge does NOT say "Busca semantica" / "Semantic search".
     */
    ...
  });

  test('search input has correct placeholder text', async ({ page }) => {
    /**
     * Navigate to /.
     * Assert: search input placeholder is "Buscar noticias..." (pt-BR default).
     * Switch to EN.
     * Assert: search input placeholder is "Search news...".
     */
    ...
  });

  test('no results shows appropriate message', async ({ page }) => {
    /**
     * Navigate to /.
     * Type a nonsense query like "xyznonexistent123".
     * Wait for debounce.
     * Assert: either no feed-card elements OR a no-results message is visible.
     */
    ...
  });

});
```

**Key constraint:** All tests run without `VITE_VERTEX_SEARCH_URL` set, so they exercise the **local fallback** path exclusively. Vertex API integration is verified by the Python unit tests and manual cloud testing.

---

## 4. Data Contract Notes

### 4.1 Python Indexer — Schema Compliance

| File | Schema(s) Consumed | Key Validations |
|------|-------------------|-----------------|
| `index_to_vertex_search.py` | `articles.schema.json` | Reads: `id` (required, hex16), `title` (required), `summaries.pt-BR` (optional), `summaries.en-US` (optional), all other fields passed through in `struct_data` |
| `test_index_to_vertex_search.py` | `articles.schema.json` | Test articles must have valid `id = sha256(url)[:16]`, `title`. Summaries optional. |

### 4.2 React Hook — Data Expectations

| File | Schema(s) Consumed | Key Validations |
|------|-------------------|-----------------|
| `useSearch.js` | `articles.schema.json` (via `useData`) | Reads: `title`, `summaries.pt-BR`, `summaries.en-US`, `candidates_mentioned[]`, `published_at`. All optional except `title`. |

### 4.3 NewsFeed — No New Schema

`NewsFeed.jsx` does not consume any new data files. It uses `useSearch` which returns the same `Article[]` shape from the existing `articles.json`.

### 4.4 Discovery Engine Document Format (Internal)

The document sent to Vertex AI Search is NOT a schema in `docs/schemas/` — it's an internal API format:

```json
{
  "id": "<article.id>",
  "content": {
    "raw_text": "<title> <summaries.pt-BR> <summaries.en-US>"
  },
  "struct_data": { "...full article object..." }
}
```

This format is dictated by the `google-cloud-discoveryengine` Python client, not by our schemas.

### 4.5 Environment Variables (Not Secrets in Frontend)

| Variable | Where | Secret? | Purpose |
|----------|-------|---------|---------|
| `VITE_VERTEX_SEARCH_URL` | `site/.env.production` or deploy env | No | Public API endpoint for search |
| `GCP_PROJECT_ID` | GitHub Actions secrets | Yes | GCP project for indexing |
| `VERTEX_SEARCH_ENGINE_ID` | GitHub Actions secrets | Yes | Discovery Engine engine ID |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | GitHub Actions secrets | Yes | Service account key for indexing |

**Critical rule:** `VITE_VERTEX_SEARCH_URL` must NOT be committed to the repository. It is set as a GitHub Actions environment variable in the deploy workflow. For local development, the hook uses local fallback when the variable is absent.

---

## 5. Step-by-Step Implementation Order

### Step 1: Verify baseline and Phase 16 completion

**Dependencies:** None
**Actions:**
1. Verify `plans/phase-16-arch.DONE` exists (Phase 16 must be complete)
2. Run `python -m pytest scripts/ -v --tb=short` to see baseline test state
3. Run `Push-Location site; npm run build; Pop-Location` to verify site builds
4. Check `data/articles.json` has content (at least 1 article)

**Verification:** Site builds, existing tests pass, articles.json is non-empty.

### Step 2: Update requirements.txt

**Dependencies:** Step 1
**Actions:**
1. Append `google-cloud-discoveryengine>=0.11.0` to `requirements.txt`
2. Run `pip install -r requirements.txt` to verify the dependency resolves

**Key constraints:**
- Do NOT reorder or modify existing lines
- Append to the end of the file

**Verification:** `pip install -r requirements.txt` succeeds without errors.

### Step 3: Create `scripts/index_to_vertex_search.py`

**Dependencies:** Step 2 (dependency installed)
**Actions:**
1. Create the file with all functions from Section 3.1
2. Implement `_check_env_vars()` — return None and log warning if any of the 3 env vars missing
3. Implement `_write_credentials_file()` — write JSON string to `tempfile.NamedTemporaryFile`
4. Implement `_load_articles()` — read JSON file, return `[]` on any error
5. Implement `_article_to_document()` — build Discovery Engine document dict
6. Implement `_index_documents()` — use `DocumentServiceClient.import_documents()` with try/except
7. Implement `main()` — orchestrate: check env, load articles, transform, index, print count

**Key constraints:**
- `main()` MUST exit with code 0 even when credentials are missing (print warning, return)
- All Google Cloud API calls wrapped in try/except — log error, never crash
- `_load_articles()` uses `DATA_PATH` constant (not hardcoded string)
- Documents use article `id` as document ID (enables upsert/dedup)
- Set `GOOGLE_APPLICATION_CREDENTIALS` env var from the JSON string before creating client

**Verification:** `python scripts/index_to_vertex_search.py` — exits cleanly with warning (no credentials in dev env).

### Step 4: Create `scripts/test_index_to_vertex_search.py`

**Dependencies:** Step 3
**Actions:**
1. Create the file with all test functions from Section 3.2
2. Implement `_make_article()` helper with `hashlib.sha256(url.encode()).hexdigest()[:16]` for ID
3. Implement all 7 tests, mocking `google.cloud.discoveryengine` throughout
4. Use `monkeypatch.delenv()` to simulate missing env vars
5. Use `unittest.mock.patch` to mock the Discovery Engine client

**Key constraints:**
- NEVER make real Google Cloud API calls
- Test `_article_to_document()` directly (it's a pure function, no mocking needed)
- Test `_load_articles()` with `tmp_path` (file system isolation)
- `test_indexer_handles_missing_credentials` must assert exit code 0, not SystemExit

**Verification:** `python -m pytest scripts/test_index_to_vertex_search.py -v` — all 7 tests pass.

### Step 5: Run and fix Python tests (RALPH loop)

**Dependencies:** Step 4
**Actions:**
1. Run `python -m pytest scripts/test_index_to_vertex_search.py -v --tb=short`
2. If failures: fix test code or script code
3. Repeat up to 3 times per RALPH protocol

**Verification:** Zero test failures.

### Step 6: Add i18n search keys

**Dependencies:** Step 1 (site builds)
**Actions:**
1. Open `site/src/locales/pt-BR/common.json` and add `search` object per Section 3.5
2. Open `site/src/locales/en-US/common.json` and add `search` object per Section 3.5

**Key constraints:**
- Do NOT modify any existing keys
- Place the `search` key at root level alongside existing sections (`feed`, `home`, `nav`, etc.)
- Strings must NOT contain emojis (project rule)
- Use `{{query}}` interpolation in `no_results` for react-i18next

**Verification:** JSON files remain valid: `Get-Content site\src\locales\pt-BR\common.json | ConvertFrom-Json` (no parse error).

### Step 7: Create `site/src/hooks/useSearch.js`

**Dependencies:** Step 6 (i18n keys exist)
**Actions:**
1. Create the file with all functions from Section 3.3
2. Implement `filterLocal()` — split query into terms, case-insensitive match against `title`, `summaries["pt-BR"]`, `summaries["en-US"]`, `candidates_mentioned[]`; sort by `published_at` desc; limit 20
3. Implement `searchVertex()` — fetch from `VITE_VERTEX_SEARCH_URL` with query param, parse response
4. Implement `useSearch()` hook — useState for `results`, `loading`, `error`, `isVertexSearch`; useEffect with AbortController; if no VITE_VERTEX_SEARCH_URL, synchronous local filter

**Key constraints:**
- `import.meta.env.VITE_VERTEX_SEARCH_URL` read once (module level or useMemo)
- AbortController cancels previous Vertex request when query changes
- On Vertex fetch error: silently fall back to `filterLocal`, set `isVertexSearch: false`
- Empty query (`""` or whitespace-only): return `{ results: [], loading: false, error: null, isVertexSearch: false }`
- `filterLocal` uses `.toLowerCase()` for case-insensitive matching
- Split query by whitespace; ALL terms must match at least one field (AND logic)
- Handle articles with missing `summaries` or `candidates_mentioned` gracefully (treat as empty string / empty array)

**Verification:** `Push-Location site; npm run build; Pop-Location` succeeds (no import errors).

### Step 8: Update `site/src/components/NewsFeed.jsx`

**Dependencies:** Step 7 (useSearch exists)
**Actions:**
1. Add `useState` and `useEffect` imports (if not already present)
2. Add `import { useSearch } from '@/hooks/useSearch';`
3. Add `searchQuery` state and `debouncedQuery` state with 300ms debounce via `useEffect`
4. Call `useSearch(debouncedQuery, articles)` destructuring `results`, `loading` as `searchLoading`, `isVertexSearch`
5. Compute `displayedArticles`: if `debouncedQuery` is non-empty use `results`, else use `visibleArticles`
6. Insert search input JSX between `feed-heading` div and the article map
7. Add search badge (conditional on `debouncedQuery` being non-empty)
8. Add search loading spinner (conditional on `searchLoading`)
9. Add no-results message when `debouncedQuery` is non-empty and `displayedArticles` is empty
10. Replace `visibleArticles.map(...)` with `displayedArticles.map(...)`

**Key constraints:**
- Search input uses i18n keys: `t('search.placeholder')`, `t('search.aria_label')`
- Badge text uses i18n keys: `t('search.semantic_badge')` or `t('search.local_badge')`
- No emojis in JSX (arch spec mentions emojis but project rules forbid them — use text only)
- `MethodologyBadge` must remain at the bottom of the feed section
- `selectedCategory` filter still applies when search is not active
- When search IS active, category filter is bypassed (search results come pre-filtered)
- Debounce implementation: `useEffect` with `setTimeout` / `clearTimeout`, dependency on `searchQuery`

**Verification:** `Push-Location site; npm run build; Pop-Location` succeeds. Visually inspect in dev server.

### Step 9: Update `.github/workflows/collect.yml`

**Dependencies:** Step 3 (indexer script exists)
**Actions:**
1. Add the Vertex indexing step from Section 3.7 between "AI processing" and "Commit data updates"

**Key constraints:**
- Step must include all 3 env vars from secrets
- Must use `|| echo "[warn]..."` to prevent workflow failure
- Step order: Collect sources → Scrape → AI processing → **Index to Vertex** → Commit

**Verification:** Visually inspect YAML is valid. `python -c "import yaml; yaml.safe_load(open('.github/workflows/collect.yml'))"` (if pyyaml available).

### Step 10: Create `docs/adr/007-vertex-search.md`

**Dependencies:** None (can be done in parallel)
**Actions:**
1. Create the ADR file with content from Section 3.8
2. Ensure all 6 setup steps are documented
3. Include cost model and trial credit info

**Verification:** File exists and is valid Markdown.

### Step 11: Create `qa/tests/test_search.spec.js`

**Dependencies:** Step 8 (NewsFeed updated)
**Actions:**
1. Create the test file with all 6 tests from Section 3.9
2. Follow existing pattern: import from `../../site/node_modules/@playwright/test/index.js`
3. Use `waitForLoadState('networkidle')` before assertions
4. Wait 500ms after typing for debounce (use `page.waitForTimeout(500)` — exception to the "no waitForTimeout" rule because debounce is intentional)

**Key constraints:**
- Tests run against built site (`dist/` via `vite preview`) — NOT dev server
- `VITE_VERTEX_SEARCH_URL` is NOT set in test env — all tests exercise local fallback
- Handle empty data gracefully (if `articles.json` has no articles, test for empty-state UI)
- Language detection: check for pt-BR keys by default, EN after language switch

**Verification:** `Push-Location site; npm run build; npx playwright test qa/tests/test_search.spec.js; Pop-Location`

### Step 12: Run Playwright tests (RALPH loop)

**Dependencies:** Step 11
**Actions:**
1. `Push-Location site; npm run build; npx playwright test; Pop-Location`
2. If failures: inspect error, fix test selectors or component
3. Repeat up to 3 times per RALPH protocol

**Verification:** All Playwright tests pass (including existing Phase 16 tests and new search tests).

### Step 13: Full regression verification

**Dependencies:** Steps 5, 12
**Actions:**
1. `python -m pytest scripts/ -v --tb=short` — all Python tests pass
2. `Push-Location site; npm run build; Pop-Location` — build succeeds
3. `Push-Location site; npx playwright test; Pop-Location` — all E2E tests pass
4. `python scripts/index_to_vertex_search.py` — exits cleanly with warning (no credentials)
5. Verify portal loads normally without any Vertex credentials

**Verification:** All acceptance criteria from arch spec satisfied.

---

## 6. Test and Verification Commands (PowerShell 7)

```powershell
# 1. Python unit tests (indexer)
python -m pytest scripts/test_index_to_vertex_search.py -v --tb=short

# 2. Full Python test suite (regression)
python -m pytest scripts/ -v --tb=short

# 3. Indexer script exits cleanly without credentials
python scripts/index_to_vertex_search.py
# Expected: warning message, exit code 0
$LASTEXITCODE -eq 0  # Should be True

# 4. Build static site
Push-Location site; npm run build; Pop-Location

# 5. Playwright search tests only
Push-Location site; npx playwright test qa/tests/test_search.spec.js; Pop-Location

# 6. Full Playwright suite (regression)
Push-Location site; npx playwright test; Pop-Location

# 7. Verify i18n JSON is valid
Get-Content site\src\locales\pt-BR\common.json | ConvertFrom-Json | Out-Null
Get-Content site\src\locales\en-US\common.json | ConvertFrom-Json | Out-Null
Write-Host "OK: i18n JSON files are valid"

# 8. Verify new files exist
@(
  'scripts/index_to_vertex_search.py',
  'scripts/test_index_to_vertex_search.py',
  'site/src/hooks/useSearch.js',
  'docs/adr/007-vertex-search.md',
  'qa/tests/test_search.spec.js'
) | ForEach-Object {
  if (Test-Path $_) { Write-Host "OK: $_" } else { Write-Error "MISSING: $_" }
}

# 9. Verify requirements.txt has new dependency
if ((Get-Content requirements.txt -Raw) -match 'google-cloud-discoveryengine') {
  Write-Host 'OK: google-cloud-discoveryengine in requirements.txt'
} else {
  Write-Error 'MISSING: google-cloud-discoveryengine not in requirements.txt'
}

# 10. Verify collect.yml has Vertex indexing step
if ((Get-Content '.github\workflows\collect.yml' -Raw) -match 'index_to_vertex_search') {
  Write-Host 'OK: Vertex indexing step in collect.yml'
} else {
  Write-Error 'MISSING: Vertex indexing step not in collect.yml'
}

# 11. Verify search i18n keys exist
$ptBR = Get-Content site\src\locales\pt-BR\common.json | ConvertFrom-Json
if ($ptBR.search.placeholder) { Write-Host 'OK: pt-BR search keys' } else { Write-Error 'MISSING: pt-BR search keys' }
$enUS = Get-Content site\src\locales\en-US\common.json | ConvertFrom-Json
if ($enUS.search.placeholder) { Write-Host 'OK: en-US search keys' } else { Write-Error 'MISSING: en-US search keys' }
```

---

## 7. Git Commit Message

```
feat(phase-17): Vertex AI Search — semantic search with local fallback

Python indexer:
- scripts/index_to_vertex_search.py: batch import articles to Discovery Engine
- Graceful exit (code 0) when credentials are missing
- Idempotent upsert by article ID

React search hook + UI:
- site/src/hooks/useSearch.js: Vertex API primary, local filter fallback
- NewsFeed.jsx: search bar with 300ms debounce, search badge, loading state
- i18n: search.* keys in pt-BR and en-US

CI/CD:
- collect.yml: Vertex indexing step after AI processing (non-blocking)
- requirements.txt: google-cloud-discoveryengine>=0.11.0

Documentation:
- docs/adr/007-vertex-search.md: rationale, fallback strategy, cost model, setup

Tests:
- scripts/test_index_to_vertex_search.py: 7 unit tests (mocked API)
- qa/tests/test_search.spec.js: 6 E2E tests (local fallback path)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## 8. Completion Sentinel

```powershell
New-Item -Path plans/phase-17-arch.DONE -ItemType File -Force
```

---

## 9. Acceptance Criteria Checklist

From `plans/phase-17-arch.md`:

- [ ] `python scripts/index_to_vertex_search.py` runs and exits cleanly (code 0) when credentials absent
- [ ] `useSearch` returns results using local filtering when Vertex URL not set
- [ ] `useSearch` would use Vertex when `VITE_VERTEX_SEARCH_URL` is set (verified by code review)
- [ ] `useSearch` falls back to local filtering when Vertex is unavailable (verified by hook logic)
- [ ] Search bar appears on homepage, filters articles on input
- [ ] "Busca semantica" vs "Busca local" badge correctly indicates which engine is in use
- [ ] Removing the search query restores the full article list
- [ ] `docs/adr/007-vertex-search.md` committed
- [ ] All unit tests pass: `python -m pytest scripts/test_index_to_vertex_search.py -v`
- [ ] All Playwright tests pass: `Push-Location site; npx playwright test; Pop-Location`
- [ ] `npm run build` succeeds with search feature
- [ ] Portal loads and functions normally without any Vertex credentials set
- [ ] `google-cloud-discoveryengine>=0.11.0` in `requirements.txt`
- [ ] Vertex indexing step added to `collect.yml` (non-blocking)

---

## 10. Constraints Reminder

- **Progressive enhancement:** Portal MUST be 100% functional without Vertex AI Search
- **Silent fallback:** `useSearch` must never show an error to the user when Vertex fails — switch to local filter silently
- **No secrets in code:** `VITE_VERTEX_SEARCH_URL` must NOT be committed (set via CI env vars); `GOOGLE_APPLICATION_CREDENTIALS_JSON` is a GitHub secret only
- **No emojis:** Project rules forbid emojis in code and UI — use text labels for search badges
- **Idempotency:** `index_to_vertex_search.py` must be safe to run repeatedly (upsert by ID)
- **Error isolation:** All Google Cloud API calls wrapped in try/except — log and continue
- **Exit code 0:** `index_to_vertex_search.py` ALWAYS exits with code 0, even on failure (to not break CI)
- **Mock all API calls:** Python tests must NEVER make real Google Cloud requests
- **MethodologyBadge:** Must remain visible on NewsFeed after search integration
- **Debounce 300ms:** Search input does NOT fire on every keystroke
- **i18n only:** No hardcoded strings in JSX — all search UI text via `react-i18next`
- **AbortController:** Cancel in-flight Vertex requests when query changes (prevent stale results)
- **Max 20 results:** Both Vertex and local search return at most 20 results
- All shell commands use PowerShell 7 syntax
