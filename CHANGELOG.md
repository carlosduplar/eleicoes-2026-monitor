# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — Phase 4: Frontend MVP
- `site/` React frontend scaffold with Vite + SSG (`vite-react-ssg`) and route pre-rendering
- `site/vite.config.js` with React plugin, `@/` alias, and `/data` proxy to repository `data/`
- `site/src/locales/pt-BR/common.json` and `site/src/locales/en-US/common.json` for bilingual UI labels
- App shell in `site/src/App.jsx` + `site/src/main.jsx` with router, nav, countdown, language toggle, and placeholder routes
- Data layer `site/src/hooks/useData.js` with in-memory cache and standardized loading/error handling
- Feed UI components: `NewsFeed`, `SourceFilter`, `MethodologyBadge`, `Nav`, `CountdownTimer`, `LanguageSwitcher`
- Homepage layout `site/src/pages/Home.jsx` with WF-01-inspired 70/30 split and responsive behavior aligned to WF-11
- `site/index.html` metadata updates (viewport, description, OG tags, RSS autodiscovery links)

### Added — Phase 3: RSS Collection
- `data/sources.json` with RSS, party, and poll source metadata for the Foca collection tier
- `data/articles.json` seed document for article storage bootstrap
- `scripts/collect_rss.py` RSS collector with active-source filtering, `sha256(url)[:16]` deduplication, UTC collection timestamp, and per-feed error tolerance
- `scripts/build_data.py` consolidator with deduplication, published date ordering, 500-item cap, and schema validation warnings
- `scripts/test_collect_rss.py` unit tests for id generation, dedup behavior, idempotent double run, feed failure resilience, size limit, and sort order

### Added — Phase 1: Core Scaffold
- `PLAN.md` — Master implementation plan with 17 phases
- `README.md` — Bilingual project overview
- `CHANGELOG.md` — This file
- `.gitignore` — Standard ignores for Python + Node + IDE
- `requirements.txt` — Python 3.12 dependencies
- `conductor.ps1` — PowerShell 7 multi-agent orchestrator
- `docs/adr/000-wireframes.md` — Wireframe audit and design tokens
- `docs/adr/001-hosting.md` — GitHub Pages + Cloudflare rationale
- `docs/adr/002-ai-providers.md` — Multi-provider AI fallback chain
- `docs/adr/003-i18n-strategy.md` — Bilingual i18n strategy (react-i18next)
- `docs/schemas/articles.schema.json` — Article pipeline schema
- `docs/schemas/sentiment.schema.json` — Sentiment scores schema
- `docs/schemas/quiz.schema.json` — Quiz questions and positions schema
- `docs/schemas/polls.schema.json` — Polling data schema
- `docs/schemas/types.ts` — TypeScript type definitions for all schemas
- `docs/agent-protocol.md` — Agent roles, RALPH loops, handoff protocol
- `.github/copilot-instructions.md` — Project-specific Copilot instructions
- `plans/phase-02-arch.md` — Task spec for Codex: AI Client
- `plans/phase-03-arch.md` — Task spec for Codex: RSS Collection
- `plans/phase-04-arch.md` — Task spec for Codex: Frontend MVP
- `docs/wireframes/` — 11 HTML standalone wireframes (WF-01 to WF-12)
- Directory structure: `.github/`, `scripts/`, `data/`, `site/`, `docs/`, `plans/`, `tasks/`, `qa/`

### Phase 0: Wireframes (DONE)
- 11 wireframes created as standalone HTML files
- Design tokens finalized (navy/gold/white palette)
- Navigation standardized across all screens
- Candidate colors assigned for 9 pre-candidates
