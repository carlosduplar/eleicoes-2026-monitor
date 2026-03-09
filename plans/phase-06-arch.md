# Phase 06 — AI Pipeline

## Objective

Implement the Editor tier: bilingual article summarization (`summarize.py`) and candidate-sentiment analysis (`analyze_sentiment.py`). Articles progress from `status: "raw"` to `status: "validated"`. Replace the Phase 05 stubs with full implementations. Narrative cluster deduplication via cosine similarity prevents redundant articles from different sources covering the same event.

## Input Context

- `docs/prompt-eleicoes2026-v5.md` lines 87-175 — `ai_client.py` complete implementation
- `docs/prompt-eleicoes2026-v5.md` lines 1089-1236 — Editor tier responsibilities, article schema with `edit_history`
- `docs/prompt-eleicoes2026-v5.md` lines 846-858 — `data/sentiment.json` schema
- `docs/schemas/articles.schema.json` — Article schema (from Phase 01)
- `docs/schemas/sentiment.schema.json` — Sentiment schema (from Phase 01)
- `scripts/ai_client.py` — Multi-provider fallback (from Phase 02)
- `data/articles.json` — Articles with `status: "raw"` (from Phase 03)
- `.github/workflows/collect.yml` — Pipeline context (from Phase 05)

## Deliverables

### 1. `scripts/summarize.py`

Processes all articles with `status: "raw"` that have no `summaries` yet.

**Key behaviors:**
- Read `data/articles.json`
- Filter: `status == "raw"` AND (`summaries` is missing OR both `pt-BR` and `en-US` are empty)
- For each article, call `ai_client.summarize_article(title, content, language)` for both `pt-BR` and `en-US`
- On success: set `summaries["pt-BR"]`, `summaries["en-US"]`, `_ai_provider`, `_ai_model`
- On AI failure: log to `data/pipeline_errors.json`, keep article as `raw`, continue to next
- After summaries complete, set `status: "validated"` and append to `edit_history`:
  ```json
  {"tier": "editor", "at": "<ISO8601>", "provider": "<provider>", "action": "validated", "changes": ["summary_pt", "summary_en"]}
  ```
- Write updated `data/articles.json`
- Print summary: "Summarized X articles (Y errors, Z skipped already-done)"
- **Idempotent:** articles already with both summaries are skipped

**Content extraction:** if article has no `content` field, use `title` as fallback for summarization. Log a warning.

### 2. `scripts/analyze_sentiment.py`

Builds `data/sentiment.json` from all `validated` and `curated` articles.

**Key behaviors:**
- Read all articles with `status` in `["validated", "curated"]`
- For each article with `sentiment_per_candidate` empty or missing, call `ai_client.call_with_fallback()` with a sentiment prompt to extract per-candidate scores (-1.0 to 1.0)
- Aggregate into two views:
  - `by_topic`: `{candidate_slug: {topic_id: float_avg}}`
  - `by_source`: `{candidate_slug: {source_category: float_avg}}`
- Write `data/sentiment.json` conforming to schema:
  ```json
  {
    "updated_at": "<ISO8601>",
    "article_count": 0,
    "methodology_url": "/metodologia",
    "disclaimer_pt": "Análise algorítmica do tom das notícias coletadas. Não representa pesquisa de opinião.",
    "disclaimer_en": "Algorithmic analysis of collected news tone. Does not represent opinion polling.",
    "by_topic": {},
    "by_source": {}
  }
  ```
- **Idempotent:** always rebuilds from full corpus (not incremental)
- Print summary: "Sentiment: X candidates × Y topics, Z articles processed"

### 3. `scripts/deduplicate_narratives.py`

Detects duplicate narrative clusters among newly validated articles.

**Key behaviors:**
- Load all `validated` articles from the last 24h
- Compute TF-IDF vectors for article titles (use `sklearn.feature_extraction.text.TfidfVectorizer`)
- Compute cosine similarity matrix
- Articles with cosine similarity > 0.85 assigned the same `narrative_cluster_id`
- `narrative_cluster_id` format: `cluster_<sha256(sorted_ids)[:8]>`
- Update `data/articles.json` with cluster IDs
- Print summary: "Clusters: X articles grouped into Y clusters"

Add `scikit-learn` to `requirements.txt`.

### 4. Update `scripts/summarize.py` — confidence scoring

After summarization, calculate `confidence_score` for each article:
- `1.0` if AI returned valid JSON with all required fields
- `0.8` if AI returned partial JSON (some fields missing)
- `0.6` if `_parse_error: True` in AI response (fallback to title)
- Articles with `confidence_score < 0.6` remain `status: "raw"` with `editor_note: "low confidence"`

### 5. Update `data/articles.json` schema fields

Ensure these fields are present in every article after Phase 06 processing:
- `summaries: {"pt-BR": "...", "en-US": "..."}`
- `sentiment_score: float | null`
- `confidence_score: float | null`
- `narrative_cluster_id: string | null`
- `edit_history: []`
- `disclaimer_pt: "Análise algorítmica. Não representa pesquisa de opinião."`
- `disclaimer_en: "Algorithmic analysis. Does not represent polling data."`

### 6. Replace Phase 05 stubs

Remove `|| echo "summarize failed, continuing"` stub behavior in `collect.yml` — the real scripts now handle their own errors internally and never exit with non-zero unless truly broken.

### 7. Unit tests — `scripts/test_summarize.py`

- `test_summarize_skips_already_done` — article with existing summaries is not re-processed
- `test_summarize_sets_validated_status` — article transitions to `validated` after successful summarization
- `test_summarize_handles_ai_failure` — on AI error, article stays `raw`, error logged, no crash
- `test_sentiment_has_disclaimers` — `sentiment.json` always includes `disclaimer_pt` and `disclaimer_en`
- `test_sentiment_is_idempotent` — running twice produces same output
- `test_cosine_dedup_clusters_similar` — two near-identical article titles get same `narrative_cluster_id`

## Constraints

- AI errors must NEVER raise exceptions that stop the pipeline — wrap all `ai_client` calls in `try/except`
- `data/pipeline_errors.json` must be appended (not overwritten) on each error
- All candidate name references use the canonical `slug` form from `CANDIDATES` list in the prompt
- `sentiment.json` must always include `disclaimer_pt` and `disclaimer_en` — this is a hard rule
- Do NOT use external NLP libraries other than `scikit-learn` for deduplication (already justified)

## Acceptance Criteria

- [ ] `python scripts/summarize.py` runs and produces `status: "validated"` articles in `data/articles.json`
- [ ] `python scripts/analyze_sentiment.py` runs and writes valid `data/sentiment.json` with both disclaimers
- [ ] `python scripts/deduplicate_narratives.py` runs and assigns `narrative_cluster_id` to similar articles
- [ ] Running `summarize.py` twice does not re-process already-summarized articles
- [ ] `data/pipeline_errors.json` receives entries on AI failure without crashing the pipeline
- [ ] All unit tests pass: `python -m pytest scripts/test_summarize.py -v`
- [ ] `data/sentiment.json` is valid against `docs/schemas/sentiment.schema.json`

## Commit & Push

After all deliverables are verified:

```
git add scripts/summarize.py scripts/analyze_sentiment.py scripts/deduplicate_narratives.py scripts/test_summarize.py data/sentiment.json data/pipeline_errors.json requirements.txt
git commit -m "feat(phase-06): AI pipeline — summarize, sentiment, narrative dedup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-06-arch.DONE`.
