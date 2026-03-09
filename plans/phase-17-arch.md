# Phase 17 — Vertex AI Search (Extension)

## Objective

Optional extension phase — implement semantic search over the article corpus using Google Vertex AI Search (Discovery Engine / GenAI App Builder). Replace client-side text filtering with natural language search: "posição de Tarcísio sobre privatização" returns semantically relevant articles even without exact keyword match. Only implement after Phase 16 QA passes.

## Dependencies

- **Phase 16 must be complete** (`plans/phase-16-arch.DONE` must exist)
- Google Cloud project with Vertex AI Search trial credit (773 CHF, expires 2027-03-02)
- `VERTEX_SEARCH_ENGINE_ID` and `GCP_PROJECT_ID` GitHub secrets configured
- `GOOGLE_APPLICATION_CREDENTIALS` or service account JSON configured

## Input Context

- `docs/prompt-eleicoes2026-v5.md` lines 945-964 — Vertex AI Search implementation spec
- `data/articles.json` — Article corpus to index (from Phase 06+)
- `site/src/hooks/useData.js` — Data fetching hook (from Phase 04)
- `site/src/components/NewsFeed.jsx` — Will integrate `useSearch` (from Phase 04)
- Google Cloud documentation: AI Applications → Agent Builder → Search App

## Deliverables

### 1. Google Cloud setup (manual prerequisites — document in ADR 007)

Before implementation, the operator must:
1. Go to Google Cloud Console → AI Applications → Agent Builder
2. Create a Search App: type "Generic", data store "JSON"
3. Note the `ENGINE_ID`
4. Create a Service Account with roles: `Vertex AI User` + `Discovery Engine Admin`
5. Download JSON key → store as GitHub secret `GOOGLE_APPLICATION_CREDENTIALS_JSON`
6. Store `VERTEX_SEARCH_ENGINE_ID` and `GCP_PROJECT_ID` as GitHub secrets

### 2. `scripts/index_to_vertex_search.py`

Indexes `data/articles.json` into the Vertex AI Search data store.

**Key behaviors:**
- Read `data/articles.json` (validated + curated articles)
- Use Google Cloud Discovery Engine Python client (`google-cloud-discoveryengine`)
- For each article, create a document with:
  - `id`: article ID
  - `content.raw_text`: `title + " " + summaries["pt-BR"] + " " + summaries["en-US"]`
  - `struct_data`: full article object (for retrieval)
- Use `DocumentsServiceClient.import_documents()` for batch import (not one-by-one)
- On success: print "Indexed X documents to Vertex AI Search"
- On failure: log error, do NOT crash — the portal works without Vertex
- **Idempotent:** documents are upserted by ID (existing documents are updated)

**Add to `requirements.txt`:**
```
google-cloud-discoveryengine>=0.11.0
```

### 3. `site/src/hooks/useSearch.js`

Search hook with Vertex AI Search as primary and client-side filter as fallback.

```javascript
/**
 * useSearch — semantic search with local fallback
 *
 * If VITE_VERTEX_SEARCH_URL is set, uses Vertex AI Search API.
 * Falls back to client-side filtering if Vertex is unavailable or unconfigured.
 *
 * @param {string} query - search query
 * @param {Array} articles - local article corpus (from useData)
 * @returns {{ results, loading, error, isVertexSearch }}
 */
export function useSearch(query, articles) {
  // ... implementation
}
```

**Vertex API call:**
```javascript
const VERTEX_URL = import.meta.env.VITE_VERTEX_SEARCH_URL;
// GET ${VERTEX_URL}/search?query=<encoded>&pageSize=20
```

**Local fallback:** filter `articles` by checking if `query` terms appear in `title`, `summaries.pt-BR`, or `candidates_mentioned`. Case-insensitive. Returns up to 20 results sorted by `published_at` desc.

**State management:**
- `loading`: true while Vertex request in flight
- `error`: set on network failure (triggers local fallback silently)
- `isVertexSearch`: boolean — true if result came from Vertex, false if local fallback

### 4. Update `site/src/components/NewsFeed.jsx`

Add a search bar above the `SourceFilter`:
- Input: `<input type="search" placeholder="Buscar notícias..." aria-label="Buscar notícias">`
- On input change (debounced 300ms): call `useSearch(query, articles)`
- If `query` is empty: render full article list (no search active)
- If `query` is non-empty: render `useSearch` results instead
- Show `isVertexSearch` badge: "🔍 Busca semântica" if Vertex, "🔍 Busca local" if fallback
- Loading spinner while search is in flight

### 5. `.github/workflows/collect.yml` update

Add a step after `build_data.py` to re-index Vertex AI Search when new articles are committed:
```yaml
- name: Index to Vertex AI Search
  env:
    GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GOOGLE_APPLICATION_CREDENTIALS_JSON }}
    VERTEX_SEARCH_ENGINE_ID: ${{ secrets.VERTEX_SEARCH_ENGINE_ID }}
    GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  run: python scripts/index_to_vertex_search.py || echo "[warn] Vertex indexing failed, continuing"
```

Also add to `site/.env.production`:
```
VITE_VERTEX_SEARCH_URL=https://discoveryengine.googleapis.com/v1alpha/projects/<PROJECT>/locations/global/collections/default_collection/engines/<ENGINE_ID>/servingConfigs/default_search:search
```

(This env var is not a secret — it's a public endpoint URL. The API authentication is handled server-side.)

### 6. `docs/adr/007-vertex-search.md`

Document:
- Why Vertex AI Search over client-side filtering: semantic understanding, RAG-compatible
- The local fallback strategy ensures 100% uptime without Vertex
- Discovery Engine API vs Vertex AI Search API naming (same product, two names)
- Cost model: trial credit covers ~1M queries; production cost estimate
- Setup steps (reference the manual prerequisites above)
- Decision: implement as progressive enhancement (never a hard dependency)

### 7. Unit tests — `scripts/test_index_to_vertex_search.py`

- `test_indexer_handles_missing_credentials` — exits cleanly (code 0) if no credentials, with warning
- `test_indexer_handles_missing_engine_id` — same
- `test_document_format` — article is correctly transformed to Discovery Engine document format
- `test_idempotent_upsert` — indexing the same article twice does not create duplicates (mock API)

### 8. Frontend tests — `qa/tests/test_search.spec.js`

- Verify search input is present on the homepage
- Type a query → results filter (test with local fallback by not setting Vertex URL)
- Empty query → full article list restored
- `isVertexSearch: false` shows "Busca local" badge when Vertex URL not set

## Constraints

- The portal must be 100% functional without Vertex AI Search — it's a progressive enhancement
- `useSearch` fallback to local filtering must be automatic and silent (no error shown to user)
- `VITE_VERTEX_SEARCH_URL` must NOT be committed — set via GitHub Actions environment variables for the deploy workflow
- `google-cloud-discoveryengine` is a large dependency — add to `requirements.txt` but document the size increase
- The Vertex Search API requires authentication with a service account — never expose the JSON key in the repository

## Acceptance Criteria

- [ ] `python scripts/index_to_vertex_search.py` runs and indexes articles (or exits cleanly if credentials absent)
- [ ] `useSearch` returns results using Vertex when `VITE_VERTEX_SEARCH_URL` is set
- [ ] `useSearch` falls back to local filtering when Vertex is unavailable
- [ ] Search bar appears on homepage, filters articles on input
- [ ] "Busca semântica" vs "Busca local" badge correctly indicates which engine is in use
- [ ] Removing the search query restores the full article list
- [ ] `docs/adr/007-vertex-search.md` committed
- [ ] All unit tests pass: `python -m pytest scripts/test_index_to_vertex_search.py -v`
- [ ] `npm run build` succeeds with search feature
- [ ] Portal loads and functions normally without any Vertex credentials set

## Commit & Push

After all deliverables are verified:

```
git add scripts/index_to_vertex_search.py scripts/test_index_to_vertex_search.py site/src/hooks/useSearch.js site/src/components/NewsFeed.jsx .github/workflows/collect.yml docs/adr/007-vertex-search.md requirements.txt qa/tests/test_search.spec.js
git commit -m "feat(phase-17): Vertex AI Search — semantic search with local fallback

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-17-arch.DONE`.
