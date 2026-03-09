# Phase 03 — RSS Collection

## Objective

Implement the Foca tier (collector) pipeline: RSS feed collection from 20+ sources, article deduplication, and data consolidation. This is the first stage of the newsroom model.

## Input Context

- `docs/prompt-eleicoes2026-v5.md` lines 271-343 — All source definitions (RSS, parties, polls)
- `docs/prompt-eleicoes2026-v5.md` lines 1089-1236 — Pipeline hierarchy and Foca responsibilities
- `docs/schemas/articles.schema.json` — Article schema
- `docs/schemas/types.ts` — TypeScript types
- `scripts/ai_client.py` — AI client from Phase 02 (available after phase-02-arch.DONE)

## Deliverables

### 1. `data/sources.json`

Static metadata for all collection sources:

```json
{
  "rss": [
    {
      "name": "G1 Politica",
      "url": "https://g1.globo.com/rss/g1/politica/",
      "category": "mainstream",
      "language": "pt-BR",
      "active": true
    }
  ],
  "parties": [
    {
      "name": "PT",
      "url": "https://pt.org.br/noticias/",
      "candidate_slugs": ["lula"],
      "active": true
    }
  ],
  "polls": [
    {
      "name": "Datafolha",
      "url": "https://datafolha.folha.uol.com.br/eleicoes/",
      "active": true
    }
  ]
}
```

**20 RSS sources** (see spec lines 275-297):
- mainstream: G1, UOL, Folha, O Globo, Estadao, Metropoles, Gazeta do Povo
- politics: Poder360, JOTA, O Antagonista
- magazine: Veja, IstoE, CartaCapital
- international: Reuters Brasil, BBC Brasil, DW Brasil, El Pais Brasil
- institutional: Agencia Brasil, TSE, Agencia Camara, Agencia Senado

**8 party sources** (see spec lines 302-311)

**6 poll institutes** (see spec lines 336-343)

### 2. `scripts/collect_rss.py`

RSS feed collector using feedparser.

**Key behaviors:**
- Read sources from `data/sources.json` (only `active: true`)
- For each RSS source, fetch and parse feed entries
- Generate article ID: `sha256(url.encode())[:16]`
- Skip articles already in `data/articles.json` (dedup by ID)
- Set initial article fields: `id`, `url`, `title`, `source`, `published_at`, `collected_at`, `status: "raw"`, `relevance_score: null`, `candidates_mentioned: []`, `topics: []`
- Write new articles to `data/articles.json`
- Idempotent: running twice produces the same output (no duplicates)

**Error handling:**
- Individual feed failures logged but don't stop the pipeline
- Timeout per feed: 15 seconds
- Print summary: "Collected X new articles from Y sources (Z errors)"

### 3. `scripts/build_data.py`

Data consolidation script.

**Key behaviors:**
- Read `data/articles.json`
- Deduplicate by ID (in case of race conditions)
- Sort by `published_at` descending
- Limit to 500 most recent articles
- Validate each article against `docs/schemas/articles.schema.json` (warn on invalid, don't remove)
- Write consolidated `data/articles.json`
- Print summary: "Consolidated: X articles (Y removed as duplicates, Z trimmed by limit)"

### 4. Seed `data/articles.json`

Create an empty but schema-valid seed file:

```json
{
  "$schema": "../docs/schemas/articles.schema.json",
  "articles": [],
  "last_updated": "2026-03-15T00:00:00Z",
  "total_count": 0
}
```

### 5. Unit Tests — `scripts/test_collect_rss.py`

- `test_article_id_is_sha256_prefix` — ID generation matches `sha256(url)[:16]`
- `test_dedup_skips_existing_articles` — Articles already in data are not re-added
- `test_idempotent_double_run` — Running collect twice produces same article count
- `test_feed_error_does_not_crash` — Bad URL is skipped gracefully
- `test_build_data_limits_500` — More than 500 articles are trimmed to 500
- `test_build_data_sorts_by_date` — Most recent articles come first

## Constraints

- `feedparser` for RSS parsing (already in requirements.txt)
- `hashlib.sha256(url.encode()).hexdigest()[:16]` for ID generation everywhere
- No AI calls in this phase — Foca's AI processing (relevance scoring) is Phase 06
- `collected_at` uses UTC ISO 8601 format
- Articles start as `status: "raw"` with empty summaries

## Acceptance Criteria

- [ ] `data/sources.json` contains all 20 RSS + 8 party + 6 poll sources
- [ ] `collect_rss.py` runs without errors: `python scripts/collect_rss.py`
- [ ] `build_data.py` runs without errors: `python scripts/build_data.py`
- [ ] `data/articles.json` exists and is valid JSON after running both scripts
- [ ] Running `collect_rss.py` twice does not create duplicate articles
- [ ] All unit tests pass: `python -m pytest scripts/test_collect_rss.py -v`

## Sentinel

When complete, create `plans/phase-03-arch.DONE`.
