# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- Phase 18: Government data integration (TSE + Portal da Transparência).
  - `scripts/collect_tse.py`: collects 2022 presidential results from TSE CDN and DivulgaCandContas REST API for all 9 tracked candidates.
  - `scripts/collect_transparencia.py`: collects PEP status and emendas parlamentares from Portal da Transparência API for all 9 candidates.
  - `site/public/data/tse_data.json`: seed file with Lula's 2022 presidential result pre-filled.
  - `site/public/data/transparencia_data.json`: seed file with empty PEP/emendas for all 9 candidates.
  - `docs/schemas/tse_data.schema.json`: JSON Schema (Draft-07) for `tse_data.json`.
  - `docs/schemas/transparencia_data.schema.json`: JSON Schema (Draft-07) for `transparencia_data.json`.
  - `site/src/components/CandidateGovData.jsx`: tabbed component (TSE | Transparência) shown on each candidate profile page.
  - `site/src/pages/FinanciamentoPage.jsx`: `/financiamento` route — sortable transparency dashboard comparing all 9 candidates' PEP status and emendas parlamentares.
  - `.github/workflows/collect_gov_data.yml`: weekly cron (Sundays 04:00 UTC) to refresh government data files.
  - `plans/phase-18-arch.md`: architecture document for this extension.
- Planning artifact for optional extension: `plans/phase-17-arch.md` (Vertex AI Search).
- `scripts/seed_candidates_positions.py`: one-shot seeder script that populates `data/candidates_positions.json` from Wikipedia PT, Câmara/Senado APIs, and AI synthesis. Idempotent — only fills entries currently marked `unknown`. CI step triggers seeding when unknown ratio exceeds 50%.
- `docs/SEED_SOURCES.md`: documents seed data sources, licensing, and editorial transparency protocol.

### Changed

- AI provider chain updated with 2026 releases based on Artificial Analysis live benchmarks:
  - Quiz & position extraction (`positions_extract`, `quiz_generate`, `quiz_extract`, `quiz_validate`): `z-ai/glm-5.2` (NVIDIA NIM) -> `minimax-m3:cloud` (Ollama) -> `minimaxai/minimax-m3` (NVIDIA NIM) -> `gemini-3.7-flash` (Vertex AI).
  - Ingestion & sentiment (`summarization`, `sentiment`, `multilingual`): `nvidia/nemotron-3-ultra-550b-a55b` (NVIDIA NIM) -> `nvidia/nemotron-3-super-120b-a12b` (NVIDIA NIM) -> `nemotron-3-ultra:cloud` (Ollama) -> `minimax-m3:cloud` (Ollama) -> `gemini-3.7-flash` (Google AI Studio) -> `gemini-3.7-flash` (Vertex AI) -> `mimo-v2.5` (Xiaomi MiMo).
  - High Reasoning enabled natively on flagship models with `thinkingBudget: 2048` and `maxOutputTokens: 4096` on Vertex AI.
  - Purged all deprecated Moonshot Kimi endpoints (`moonshotai/kimi-k2.6`, `kimi-k2.5`).
  - Expanded `max_tokens` budgets across all task callers to ensure chain-of-thought tokens never starve structured JSON outputs.
- `scripts/curate.py` now implements full Editor-chefe curation flow: prominence scoring, `validated` -> `curated` promotion, `curated_feed.json` + `weekly_briefing.json` generation, quiz refresh trigger, and 90-minute cadence gate.
- `.github/workflows/curate.yml` now stages `data/articles.json` so curation promotions persist across runs.
- `.github/workflows/collect.yml` now executes `summarize.py` and `analyze_sentiment.py` directly (without legacy stub fallbacks), matching Phase 06 behavior.
- `site/package.json`: updated `vite-ssg` and `@unhead/dom` to resolve dependabot XSS vulnerability alerts.
- Candidate-position topic taxonomy now removes `eleicoes` and renames foreign policy from `politica_ext` to `politica_externa` across scripts, schemas, and public data.

### Fixed

- `scripts/watchdog.py` no longer writes a stub payload; it now emits structured freshness/error diagnostics per pipeline output in `data/pipeline_health.json`.
- `.github/workflows/deploy.yml`: added `workflow_run` trigger so deploy runs after Collect, Validate, or Curate workflows complete (GitHub Actions does not fire workflow triggers for commits pushed by `github-actions[bot]`). Added concurrency group to prevent deploy pile-ups.
- `.github/workflows/curate.yml`: changed from `python scripts/curate.py` to `python -m scripts.curate` to resolve relative import errors in `generate_quiz.py`.

## [1.0.0] - 2026-03-11

### Added

- Phase 00: Wireframe foundation (WF-01 to WF-12), design tokens, and screen mapping.
- Phase 01: Core scaffold (`README`, `CHANGELOG`, `PLAN`, ADR bootstrap, schemas, conductor scripts).
- Phase 02: AI client abstraction with provider fallback chain and usage/error tracking.
- Phase 03: RSS collection + article consolidation with idempotent dedup (`sha256(url)[:16]`).
- Phase 04: Frontend MVP (React + Vite SSG, bilingual shell, feed baseline, methodology badges).
- Phase 05: CI/CD workflows for collect, validate, curate, deploy, and watchdog.
- Phase 06: AI pipeline hardening for summarization/sentiment with resilient fallbacks.
- Phase 07: Sentiment dashboard route and topic/source analysis UI.
- Phase 08: Polling tracker route with historical data rendering and filtering.
- Phase 09: Public RSS feed generation for curated content distribution.
- Phase 10: Methodology page with transparency notes, limitations, and reporting channel.
- Phase 11: Political affinity quiz pipeline + UX, with neutrality constraints.
- Phase 12: SEO/GEO expansion (candidate pages, comparison pages, sitemap/robots, JSON-LD).
- Phase 13: Case study page and bilingual living documentation.
- Phase 14: Party + social collection scripts integrated into ingestion workflows.
- Phase 15: Mobile polish (BottomNav, 390px adaptations, touch ergonomics for quiz/feed).
- Phase 16: Final QA closure with expanded unit tests, Playwright E2E suite, security/SEO/a11y/code-review reports, and release docs refresh.

### Changed

- `README.md` overhauled with badges, screenshot, architecture diagram, setup, secrets, ADR links, and current candidate table.
- Static SEO output now guarantees unique title/description/canonical metadata per prerendered route.
- `site/src/main.jsx` now synchronizes `html[lang]` with active i18n locale.
- Accessibility baseline improved with skip link, focus-visible styles, reduced-motion support, heading anchor offset, and screen-reader-only label utility.

### Fixed

- `scripts/watchdog.py` now emits the expected `workflows` key for health payload compatibility.
- Case study markdown rendering hardened with safer renderer rules (raw HTML stripping + URL allowlist + escaped attributes).
- External links in candidate page now use `rel="noopener noreferrer"` to prevent tabnabbing.
- Playwright methodology assertions stabilized with role-based locator strategy.

### Security

- Added explicit security review artifact: `qa/phase-16-security-report.md`.
- Resolved markdown rendering XSS risk in case study content path.
