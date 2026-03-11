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

Implement Vertex AI Search as a progressive enhancement:

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
