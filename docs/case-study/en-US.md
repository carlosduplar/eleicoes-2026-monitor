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

## 2026-03-09 — Phase 04 (Frontend MVP)

### Implemented deliverables
- Full `site/` scaffold with React + Vite + SSG (`vite-react-ssg`) and pre-rendered static routes.
- `site/vite.config.js` with React plugin, `@` alias to `src/`, and `/data` proxy to repository root `data/`.
- i18n setup with `react-i18next` (`pt-BR` as default/fallback) and locale files for `pt-BR` and `en-US`.
- App shell (`Nav`, `CountdownTimer`, routes, footer) in `site/src/App.jsx` and bootstrap in `site/src/main.jsx`.
- `useData` hook with in-memory caching to prevent redundant fetches.
- Feed components: `NewsFeed`, `SourceFilter`, `LanguageSwitcher`, and `MethodologyBadge`.
- `Home` page with WF-01 70/30 layout and responsive behavior for the 390px mobile profile (WF-11).
- `site/index.html` metadata updates for viewport, OG defaults, and RSS autodiscovery (`/feed.xml`, `/feed-en.xml`).

### Validation run
- `cd site && npm install`
- `cd site && npm run dev` (server starts at `http://localhost:5173/`)
- `Invoke-WebRequest http://localhost:5173/data/articles.json` returned HTTP 200 (confirmed `/data` proxy)
- `cd site && npm run build` (generated static HTML in `site/dist/` for all 6 phase routes)

## 2026-03-09 — Phase 05 (CI/CD)

### Implemented deliverables
- GitHub Actions workflows added under `.github/workflows/`:
  - `collect.yml` (Foca tier, 10-minute cron + `workflow_dispatch`)
  - `validate.yml` (Editor tier, push on `data/raw/**` + 30-minute cron + `workflow_dispatch`)
  - `curate.yml` (Editor-chefe tier, hourly cron + `workflow_dispatch`, with `continue-on-error` on curation step)
  - `deploy.yml` (GitHub Pages deploy on push to `main` with path filters)
  - `watchdog.yml` (daily health check at 06:00 UTC + `workflow_dispatch`)
- Stubs added for scripts planned for later phases:
  - `collect_parties.py`, `collect_polls.py`, `collect_social.py`
  - `summarize.py`, `analyze_sentiment.py`
  - `generate_rss_feed.py`, `generate_seo_pages.py`
- `scripts/curate.py` added with 90-minute skip logic backed by `data/.curate_last_run`.
- `scripts/watchdog.py` added to generate `data/pipeline_health.json`.
- Pipeline seed files ensured:
  - `data/pipeline_errors.json`
  - `data/pipeline_health.json`
  - `data/ai_usage.json` (already present)
  - `data/.curate_last_run`
- README updated with the required one-time Pages operator action: `Settings > Pages > Source = GitHub Actions`.

### Validation run
- `python -m pytest -q` (existing Python suite)
- `python scripts/collect_rss.py`
- `python scripts/collect_parties.py`
- `python scripts/collect_polls.py`
- `python scripts/collect_social.py`
- `python scripts/summarize.py`
- `python scripts/analyze_sentiment.py`
- `python scripts/build_data.py`
- `python scripts/generate_rss_feed.py`
- `python scripts/curate.py` (first run writes timestamp)
- `python scripts/curate.py` (second run validates <90 minute skip)
- `python scripts/watchdog.py`
- `python scripts/generate_seo_pages.py`
