# PLAN.md — Portal Eleicoes BR 2026

## Problem Statement

Build a bilingual (pt-BR + en-US) near-real-time monitoring portal for Brazil's 2026 presidential elections. Static site on GitHub Pages, automated pipeline via GitHub Actions every 10-30 minutes, multi-provider AI fallback (free-first), progressive quiz, SEO/GEO pages, and full transparency via methodology page + public repo.

## Approach

Opus 4.6 plans; gpt-5.3-codex implements. 16 phases, commit after each. Wireframes (Phase 0) are complete (HTML standalone files). Implementation starts at Phase 1 (Core scaffold).

Architecture follows a "newsroom" metaphor: Foca (collector, 10min) -> Editor (validator, 30min) -> Editor-chefe (curator, ~90min). Articles progress through `raw -> validated -> curated` states. UI decision: **Option A — staged publication** (raw articles appear with title only, validated get summaries, curated get prominence badges).

## Assumptions Made

- Tarcisio hex: `#1A3A6B` (confirmed in design audit)
- Countdown target: 2026-10-04 (TSE primeiro turno)
- Node 20 LTS for frontend; Python 3.12 for pipeline
- Domain: TBD (Cloudflare DNS pointed to GitHub Pages)
- RSS feeds are the primary collection channel; Playwright for poll institutes only
- Quiz publishes only high/medium confidence positions; low/unclear silently omitted
- Git initialized in Phase 1 with first commit

## Design Tokens

```css
:root {
  --brand-navy:     #1A2E4A;
  --brand-gold:     #B8961E;
  --brand-bg:       #F5F7FA;
  --brand-surface:  #FFFFFF;
  --brand-muted:    #EDF2F7;
  --text-primary:   #1A202C;
  --text-secondary: #4A5568;
  --status-raw:     #F6AD55;
  --status-valid:   #48BB78;
  --status-curated: #B8961E;
}
```

## Candidate Colors

| Slug | Name | Party | Hex | Status |
|------|------|-------|-----|--------|
| lula | Lula | PT | #CC0000 | pre-candidate |
| flavio-bolsonaro | Flavio Bolsonaro | PL | #002776 | pre-candidate |
| tarcisio | Tarcisio de Freitas | Republicanos | #1A3A6B | speculated |
| caiado | Ronaldo Caiado | Uniao Brasil | #FF8200 | pre-candidate |
| zema | Romeu Zema | Novo | #FF6600 | pre-candidate |
| ratinho-jr | Ratinho Jr | PSD | #0066CC | speculated |
| eduardo-leite | Eduardo Leite | PSD | #4488CC | pre-candidate |
| aldo-rebelo | Aldo Rebelo | DC | #5C6BC0 | pre-candidate |
| renan-santos | Renan Santos | Missao | #26A69A | pre-candidate |

---

## Phase 0 — Wireframes (DONE)

All 11 wireframes finalized as HTML standalone files in `docs/wireframes/`. See ADR 000 for full mapping.

Files:
- `WF-01-feed-desktop.html` — Feed Desktop (`/`)
- `WF-02-03-sentiment-dashboard.html` — Sentiment Dashboard (`/sentimento`)
- `WF-04-poll-tracker.html` — Poll Tracker (`/pesquisas`)
- `WF-05-quiz-question-desktop.html` — Quiz Pergunta (`/quiz`, 1280px)
- `WF-06-quiz-result-desktop.html` — Quiz Resultado (`/quiz/resultado`, 1280px)
- `WF-07-candidate-profile-desktop.html` — Candidato Perfil (`/candidato/[slug]`, 1280px)
- `WF-08-candidate-comparison.html` — Comparacao (`/comparar/[a]-vs-[b]`)
- `WF-09-methodology.html` — Metodologia (`/metodologia`)
- `WF-10-case-study.html` — Case Study (`/sobre/caso-de-uso`)
- `WF-11-mobile-feed.html` — Mobile Feed (`/`, 390px)
- `WF-12-mobile-quiz.html` — Mobile Quiz (`/quiz`, 390px)

---

## Phase 1 — Core Scaffold

Deliverables:
- `git init` + first commit + push to `github.com/carlosduplar/eleicoes-2026-monitor`
- Directory structure per spec (`.github/`, `scripts/`, `data/`, `site/`, `docs/adr/`, `docs/case-study/`, `docs/schemas/`, `plans/`, `tasks/`, `qa/`)
- `.gitignore` (node_modules, dist, __pycache__, .env*, venv, *.pyc)
- `requirements.txt` (feedparser, beautifulsoup4, playwright, openai, lxml, tweepy, google-auth)
- `site/package.json` (react, vite, vite-ssg, react-i18next, react-helmet-async, recharts, react-router-dom)
- `PLAN.md` (this file — committed)
- `CHANGELOG.md` (initial entry)
- `README.md` (project overview, bilingual, badges)
- `.github/copilot-instructions.md` (project-specific, derived from spec)
- `docs/agent-protocol.md` (handoff protocol, RALPH loops, escalation)
- `docs/adr/000-wireframes.md` (palette, typography, layout, WF mapping)
- `docs/adr/001-hosting.md` (GitHub Pages + Cloudflare rationale)
- `docs/schemas/` — JSON Schema + TypeScript types for all `data/*.json` files
- `conductor.ps1` — PowerShell 7 orchestrator for multi-agent workflow
- Seed `data/` with empty but schema-valid JSON files
- ADR: 000, 001

## Phase 2 — AI Client (DONE)

Deliverables:
- `scripts/ai_client.py` — multi-provider fallback chain (NVIDIA NIM -> OpenRouter -> Ollama -> Vertex -> MiMo)
- Usage tracker (`data/ai_usage.json`)
- `summarize_article()` function (bilingual output)
- `extract_candidate_position()` function (for quiz pipeline)
- NVIDIA NIM model selection by task
- Unit tests for fallback logic (mocked providers)
- ADR: 002
- Status: completed and validated with pytest.

## Phase 3 — RSS Collection (DONE)

Deliverables:
- `scripts/collect_rss.py` — 20+ RSS sources, feedparser, sha256 dedup
- `scripts/build_data.py` — consolidate JSONs, dedup, limit 500 articles
- `data/sources.json` — metadata for all sources
- Idempotency: running twice produces same output
- Basic article schema validation
- Status: completed with collector/build scripts and dedicated unit tests.

## Phase 4 — Frontend MVP (DONE)

Deliverables:
- `site/` — React + Vite + vite-ssg scaffold
- `react-i18next` setup with `pt-BR/common.json` + `en-US/common.json`
- `LanguageSwitcher.jsx` — `PT | EN` toggle
- `NewsFeed.jsx` — renders articles.json, loading/empty/error states
- `SourceFilter.jsx` — filter by source category
- `CountdownTimer` — days to 1st round (2026-10-04)
- Nav component (6 items + language toggle, per harmonized wireframes)
- App shell with routing (react-router-dom)
- Follow WF-01 wireframe for layout
- ADR: 003
- Status: completed with Vite SSG scaffold, bilingual app shell, NewsFeed MVP, and validated dev/build commands.

## Phase 5 — CI/CD (DONE)

Deliverables:
- `.github/workflows/collect.yml` — cron 10min (Foca tier)
- `.github/workflows/validate.yml` — push trigger + cron 30min (Editor tier)
- `.github/workflows/curate.yml` — cron hourly with 90min skip logic (Editor-chefe)
- `.github/workflows/deploy.yml` — push on main, SSG build, GitHub Pages
- `.github/workflows/watchdog.yml` — daily 6h UTC, pipeline health
- GitHub Pages enabled via Settings
- Validate with `workflow_dispatch` manual trigger
- Status: completed with all 5 workflows, required stubs/seed files, and local validation runs.

## Phase 6 — AI Pipeline

Deliverables:
- `scripts/summarize.py` — bilingual summaries for new articles
- `scripts/analyze_sentiment.py` — candidate x topic/source scores
- `data/sentiment.json` schema with disclaimers
- Article status progression: raw -> validated
- Narrative cluster dedup (cosine similarity)

## Phase 7 — Sentiment Dashboard

Deliverables:
- `SentimentDashboard.jsx` — heatmap candidate x topic, toggle Por Tema/Por Fonte
- `MethodologyBadge.jsx` — "Como funciona?" badge, links to /metodologia
- Follow WF-02/03 wireframe (light background, harmonized)
- Candidate color chips per design tokens

## Phase 8 — Polling Tracker

Deliverables:
- `scripts/collect_polls.py` — Playwright scraping of 6 institutes
- `PollTracker.jsx` — Recharts line chart, temporal
- `PollsPage.jsx` — page wrapper
- `data/polls.json` schema
- Follow WF-04 wireframe

## Phase 9 — RSS Feed

Deliverables:
- `scripts/generate_rss_feed.py` — RSS 2.0, /feed.xml (pt-BR), /feed-en.xml (en-US)
- Autodiscovery `<link>` tags in index.html
- 50 most recent articles per feed

## Phase 10 — Methodology Page

Deliverables:
- `MethodologyPage.jsx` — disclaimer, pipeline description, limitations, error reporting
- `pt-BR/methodology.json` + `en-US/methodology.json` locales
- Follow WF-09 wireframe
- ADR: 006

## Phase 11 — Quiz

Deliverables:
- `scripts/extract_quiz_positions.py` — daily extraction, divergence scoring, topic selection
- `.github/workflows/update-quiz.yml` — cron daily 3h UTC
- `QuizEngine.jsx` — progressive funnel, no candidate reveal during questions
- `QuizResultCard.jsx` — ranking + radar chart + source reveal + share button
- `QuizPage.jsx` + `QuizResult.jsx` — page wrappers
- `utils/affinity.js` — funil progressivo algorithm
- `utils/shareUrl.js` — base64url encode/decode
- `hooks/useQuiz.js`
- `data/quiz.json` schema
- Follow WF-05 (question) + WF-06 (result) wireframes
- ADR: 005

## Phase 12 — SEO/GEO

Deliverables:
- `scripts/generate_seo_pages.py` — sitemap.xml, candidate/comparison JSONs
- `CandidatePage.jsx` — /candidato/[slug], SSG pre-render, JSON-LD Person
- `ComparisonPage.jsx` — /comparar/[a]-vs-[b], FAQPage schema
- `data/candidates.json` — full profiles for 9 candidates
- 8 pre-generated comparison pairs
- `robots.txt` allowing AI crawlers
- `_headers` Cloudflare cache config
- Follow WF-07 (candidate) + WF-08 (comparison) wireframes
- ADR: 004

## Phase 13 — Case Study

Deliverables:
- `CaseStudyPage.jsx` — /sobre/caso-de-uso
- `docs/case-study/pt-BR.md` + `en-US.md` — living documentation
- Published on site via deploy workflow
- Follow WF-10 wireframe

## Phase 14 — Party + Social Collection

Deliverables:
- `scripts/collect_parties.py` — BeautifulSoup, 8 party sites
- `scripts/collect_social.py` — tweepy + YouTube (optional)
- Integration with Foca tier pipeline

## Phase 15 — Mobile Polish

Deliverables:
- Review all breakpoints (390px mobile)
- Bottom nav (5 items) per WF-11/WF-12 wireframes
- Touch targets >= 44px
- Mobile quiz (immersive question, nav restored on result)

## Phase 16 — QA Final

Deliverables:
- `test-writer` skill: unit + integration tests
- `security-threat-modeler` skill: auth, injection, secrets review
- `seo-audit` skill: meta tags, structured data, Core Web Vitals
- `tech-lead-reviewer` skill: code review all changes
- `web-design-guidelines` skill: accessibility audit
- README.md final with badges, screenshots, architecture diagram
- CHANGELOG.md complete

## Phase 17 (Extension) — Vertex AI Search

Optional. Only after Phase 16 QA pass. Uses trial credit (773 CHF).
- `scripts/index_to_vertex_search.py`
- `hooks/useSearch.js` with local fallback
- ADR: 007

---

## Key Architectural Decisions

1. **Staged publication (Option A)**: raw articles visible immediately with title only; validated get AI summaries; curated get prominence badges
2. **Free-first AI**: NVIDIA NIM (free) -> OpenRouter (free 200/day) -> Ollama Cloud (free) -> Vertex AI ($10/mo) -> MiMo (paid)
3. **SSG over SSR**: GitHub Pages is static-only; vite-plugin-ssg pre-renders all SEO pages at build time
4. **Quiz neutrality**: candidate names never shown during questions; source reveal only in results
5. **Multi-agent orchestration**: file-based handoff (`.DONE` sentinels), RALPH loops with 3-retry escalation
