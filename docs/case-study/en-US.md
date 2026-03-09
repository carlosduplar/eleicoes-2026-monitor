# Case Study — Portal Eleicoes BR 2026

## 2026-03-09 — Phase 03 (RSS Collection)

### Implemented deliverables
- Source registry in `data/sources.json` with `rss`, `parties`, and `polls` sections.
- RSS collector in `scripts/collect_rss.py` with:
  - active-source loading;
  - deduplication by `sha256(url.encode()).hexdigest()[:16]`;
  - initial `raw` status, required fields, and empty bilingual `summaries`;
  - per-feed failure tolerance and 15-second timeout.
- Consolidation script in `scripts/build_data.py` with ID deduplication, `published_at` sorting, 500-article limit, and warning-based schema validation.
- Test suite in `scripts/test_collect_rss.py` covering ID generation, deduplication, idempotency, feed failure handling, trimming limit, and date ordering.

### Validation run
- `python -m pytest scripts/test_collect_rss.py -v`
- `python scripts/collect_rss.py`
- `python scripts/build_data.py`
- `python -m pytest -q`

### Notes
- The consolidator logs schema warnings when `relevance_score` is `null` and keeps records, matching the phase requirement.
