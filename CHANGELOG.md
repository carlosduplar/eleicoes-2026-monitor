# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
