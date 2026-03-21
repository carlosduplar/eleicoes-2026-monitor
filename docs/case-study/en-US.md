# Case Study: Portal Eleicoes BR 2026

## Executive summary
Portal Eleicoes BR 2026 was designed as a public transparency product: a bilingual portal (pt-BR and en-US) to monitor election news, sentiment trends, polling data, and candidate position signals for Brazil's 2026 presidential cycle. The goal was not to publish another opinion website, but to ship an auditable editorial infrastructure where users can see how data is collected, how AI is applied, and how each article moves through publication stages. The core promise is straightforward: people should be able to read a story, understand its processing status, and inspect the technical path that produced what they see on screen.

The implementation combines a static React + Vite frontend with a Python data pipeline and GitHub Actions automation. Instead of relying on one AI vendor, the architecture uses a multi-provider fallback chain to improve availability while keeping costs under control. Instead of hiding limitations, the product exposes methodology, disclaimers, sources, and processing state. Instead of introducing complex hosting infrastructure, deployment runs on GitHub Pages with Cloudflare in front. The result is a lightweight, low-cost, traceable system that can evolve phase by phase without losing architectural clarity.

## Stack and architecture
From a technical perspective, the stack was selected for operational predictability. On the frontend, React 18 with Vite and `vite-react-ssg` pre-renders key routes so the site can run as static content on GitHub Pages while still serving SEO and GEO goals. UI implementation follows standalone HTML wireframes defined in ADR 000, and the design token system (`--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border`) keeps visual consistency across feed, dashboards, quiz, methodology, and now the case study page.

On the data side, Python 3.12 handles ingestion and transformations. Pipeline scripts were built with idempotency and traceability as first-class constraints. The default identifier `sha256(url.encode())[:16]` prevents article duplication across runs, and output JSON follows contracts in `docs/schemas/*.schema.json` and `docs/schemas/types.ts`. This alignment keeps frontend and backend synchronized around one shared data model, which lowers regression risk caused by shape drift.

Publication architecture uses four editorial states (`raw -> validated -> curated`, plus `irrelevant`) and optimizes for continuity. Even when an AI provider is unavailable, the pipeline keeps moving. Content can be shown as `raw` with title and metadata while slower or more expensive processing continues asynchronously. Articles detected as unrelated to elections are marked `irrelevant` and purged during summarization. This avoids binary all-or-nothing publishing behavior and better reflects how near-real-time election monitoring should work in practice.

## Agent hierarchy
Delivery execution was intentionally organized around an explicit agent hierarchy documented in PLAN and handoff files. Opus acted as Architect, consolidating strategy, wireframes, ADRs, and schema contracts. Codex acted as Tactical lead, transforming architecture into concrete task specs and verification criteria. MiniMax acted as Operations implementor, executing changes through disciplined loops. Gemini acted as QA, focusing on validation, interface testing, and reporting.

Governance followed the RALPH protocol: Read, Analyze, List, Plan, Handle. For long tasks, this structure reduced improvisation by forcing context review before code edits, converting ambiguity into explicit checklists, and closing each loop with verification. In this project, RALPH was not just process vocabulary; it shaped phase sequencing, spec writing, and failure handling with bounded retries and escalation rules.

Inter-agent handoff relies on sentinel files such as `plans/phase-NN-arch.DONE`. This simple mechanism replaces heavy orchestration with repository-native traceability. When a phase closes, the sentinel signals that architecture and implementation are aligned and the next layer can proceed without hidden state. For a public iterative project, the pattern proved highly practical: low coupling, clear checkpoints, and auditable history.

## Ingestion pipeline
The ingestion model follows a newsroom metaphor with three roles. Foca (collector) runs at high frequency and primarily consumes RSS, with expansion into party websites, polling institutes, and YouTube. Editor (validator) processes collected items, runs bilingual summarization, and prepares data for analytical components. Editor-chefe (curator) runs at a slower cadence with emphasis on prominence, consistency, and quality gates.

Publication stages are explicit in the data itself: `raw`, `validated`, `curated`, and `irrelevant`. In `raw`, the portal prioritizes speed and transparency over polish: title, source, and timestamp can already be visible while analysis is still in progress. In `validated`, bilingual summaries and richer metadata are attached. In `curated`, the story gets an additional automated prominence layer. Articles flagged as `irrelevant` are removed from the public feed via an automated editorial feedback mechanism. This staged funnel avoids unnecessary blocking and delivers incremental value instead of waiting for perfect completeness.

The AI chain is built for resilience and cost control. For standard tasks (summarization, sentiment), the chain is: NVIDIA NIM (Nemotron 3 Super) -> Ollama Cloud (Nemotron 3 Super) -> Gemini 3.1 Flash Lite (Google AI, free tier) -> Vertex AI (Gemini 3 Flash Preview, paid) -> MiMo V2 Flash. For high-quality tasks (position extraction, quiz generation/validation), the chain prioritizes stronger models: Ollama Cloud (Kimi K2.5) -> NVIDIA NIM (MiniMax M2.5) -> Vertex AI (Gemini 3 Flash Preview). A circuit breaker detects provider failures early and a per-run limit caps total AI calls to avoid runaway costs. The non-negotiable rule is that AI errors must not stop the pipeline. If a call fails, the system logs the error, tries the next provider, and continues. If all providers fail, the article still remains in a coherent state rather than being silently dropped. This approach prioritizes operational continuity and reduces single-vendor risk.

## Technical decisions recorded
ADRs 000 through 006 are the decision backbone of the portal. ADR 000 established wireframes as the visual source of truth, including component mapping and shared design tokens. That decision reduced UI rework because each phase could implement against concrete references, not subjective memory.

ADR 001 selected GitHub Pages with Cloudflare for hosting, balancing zero infrastructure cost, CDN coverage, and native CI/CD through GitHub Actions. A direct consequence was choosing SSG over SSR. This constraint became an advantage: less runtime complexity, more deterministic deployment, and static-first reliability.

ADR 002 documented multi-provider AI fallback. In practical terms, it removed dependence on a single vendor and allowed the project to prioritize free tiers while reserving paid capacity for contingency. It also formalized usage tracking in `data/ai_usage.json`, which is important for cost visibility and capacity planning.

ADR 003 standardized internationalization with `react-i18next`, pt-BR as default and fallback, domain namespaces, and language persistence in `localStorage`. This pattern enabled bilingual UX growth without duplicating routes per language, keeping a single URL while swapping content client-side.

ADR 004 defined SEO and GEO strategy through candidate/comparison pre-rendering, AI-crawler-friendly `robots.txt`, and page-type JSON-LD. The portal becomes indexable by both traditional search engines and generative engines without requiring JavaScript execution for core content.

ADR 005 specified quiz neutrality constraints: no `candidate_slug` or `source_*` in question flow, source reveal only on result, and confidence filtering to hide weak extractions. ADR 006 made `/metodologia` mandatory and required MethodologyBadge in data-driven views, institutionalizing transparency and error reporting as product behavior instead of optional documentation.

## Lessons learned
The strongest lesson is that AI-assisted productivity scales when process is explicit. Vibe coding without contracts can feel fast at the start, but it accumulates hidden debt quickly. In this project, the biggest gains came when prompts, ADRs, schemas, and task specs were treated as engineering artifacts rather than optional notes. That shift enabled phase-based delivery with less rework and fewer integration surprises.

Another lesson is that multi-agent coordination has real cognitive overhead. Handoffs require protocol, naming discipline, and verification rigor. Without those controls, agent outputs drift apart. Sentinel files, centralized planning in `PLAN.md`, and bounded retry loops converted that complexity into a manageable operating model.

A third lesson is that transparency cannot be bolted on later, especially in election-adjacent AI products. Methodology, disclaimers, and source traceability need to be part of implementation from day one. Retrofitting trust signals after launch is significantly more expensive than designing them as core requirements.

---

## Operational log: post-1.0 course corrections

This section documents what did not work as expected after the initial 1.0 delivery and what was done to correct course. Each entry is dated and categorized by subsystem. The intent is to preserve an honest record of trial-and-error for future reference and to demonstrate that the system was hardened through real production feedback, not theoretical planning alone.

### 2026-03-10 -- AI provider chain: OpenRouter removed

**What happened:** OpenRouter, originally second in the AI fallback chain, hit 100% HTTP 429 (rate-limiting) failures in production. The free tier's 200 req/day limit was exhausted within the first collection cycles, causing every summarization attempt to fall through to slower providers.

**What we did:** Removed OpenRouter from the provider chain entirely. Promoted NVIDIA NIM as the primary free-tier provider. Adjusted the chain to: NVIDIA NIM (Nemotron 3 Super) -> Ollama Cloud -> Vertex AI -> MiMo.

**Lesson:** Free-tier rate limits that look generous on paper can be burned through in minutes by an automated pipeline running every 10 minutes. The fallback chain must be tested under real load, not just validated with individual calls.

### 2026-03-10 -- Scraping strategy: Playwright replaced by Bright Data

**What happened:** Article content extraction used Playwright for headless browser scraping. In GitHub Actions, Playwright was too heavy: timeouts on complex pages, high memory usage, and unreliable results on paywalled sites.

**What we did:** Replaced Playwright with Bright Data's scraping API for primary content extraction. After multiple iterations to align the API payload with Bright Data's documentation (wrong field names, missing zone configuration), we stabilized a three-tier fallback: Bright Data API -> Playwright (local fallback) -> plain HTTP request. This took four fix commits before working reliably.

**Lesson:** Third-party scraping APIs have underdocumented payload formats. Integration requires iterative testing against the live API, not just reading docs. Having a multi-tier fallback prevented total scraping failure during the transition.

### 2026-03-10 -- Summarization pipeline: LLM call explosion

**What happened:** The summarization step was making one LLM call per article per run, with no awareness of whether the provider was healthy. When a provider was failing, the pipeline would attempt hundreds of calls before giving up, wasting time and hitting rate limits across providers.

**What we did:** Halved LLM calls by checking article status before attempting summarization. Added a circuit breaker that detects consecutive failures and short-circuits remaining calls. Added a per-run limit to cap total AI calls. Fixed a bug where the circuit breaker returned false when no providers had been tried yet.

**Lesson:** Resilience is not just about fallback order. It requires awareness of failure patterns within a single run. Circuit breakers and call budgets are essential for pipelines that process hundreds of items.

### 2026-03-10 -- RSS feeds: broken URLs in sources.json

**What happened:** Several RSS feed URLs in the initial `sources.json` were outdated or broken. Collection was running successfully but returning zero articles from affected sources, silently reducing coverage.

**What we did:** Audited all 21 RSS feeds manually, updated broken URLs, and wired `_extract_rss_body` into the article creation path (it existed in code but was never called).

**Lesson:** Data source configuration must be validated against live endpoints, not just assumed correct from documentation.

### 2026-03-11 -- CI/CD: workflow race conditions

**What happened:** With collector running every 10 minutes, validator every 30, and curator hourly, concurrent workflow runs would race on `git push`. The rebase strategy caused conflicts when two workflows modified the same JSON data files. One failure mode had `GIT_EDITOR` unset, causing the rebase commit to fail silently.

**What we did:** Replaced `git pull --rebase` with `git pull --no-rebase` and added intelligent JSON conflict resolution that merges array-based data files structurally. Added concurrency groups to prevent overlapping runs of the same workflow. Set `GIT_EDITOR=true` as fallback. This reduced failures from frequent to occasional.

**Lesson:** Automated pipelines that write to the same repository from multiple workflows need merge strategies designed for the data format, not generic git rebase. Concurrency groups help but do not eliminate all race conditions.

### 2026-03-11 -- Collect workflow: AI step timeouts

**What happened:** The collect workflow combined RSS collection, article scraping, AI summarization, and sentiment analysis in a single job. When the AI provider chain was slow, the entire job exceeded GitHub Actions' step timeout.

**What we did:** Chunked AI-dependent steps into separate workflow steps with individual timeouts. Added concurrency limits to prevent multiple collect runs from overwhelming providers simultaneously.

**Lesson:** Monolithic CI steps that depend on external API latency must be broken into independently-timed chunks.

### 2026-03-12 -- Content quality: irrelevant articles flooding the feed

**What happened:** The pipeline was ingesting articles from legitimate news sources that were completely unrelated to elections (sports results, entertainment news, weather reports). RSS feeds from general news outlets contain mixed content, and the title-based filtering was too permissive.

**What we did:** Added a fourth article status: `irrelevant`. Built an automated editorial feedback mechanism (`editor_feedback.json`) that tracks irrelevant article IDs, blocked title keywords, blocked URL patterns, and excluded sources. Modified the summarization step to purge irrelevant articles and only persist valid ones. The feedback data accumulates over time, improving filtering accuracy.

**Lesson:** RSS-based collection from general news outlets requires active content filtering, not just dedup. The editorial feedback loop was not in the original design but became essential for feed quality.

### 2026-03-12 -- AI models: thinking-mode interference

**What happened:** After updating to Kimi K2.5 and MiniMax M2.5, both models were returning chain-of-thought reasoning text inside their responses, polluting summaries with internal reasoning tokens.

**What we did:** Added `extra_body` configuration to disable thinking mode for both models. This required provider-specific parameter formats that differed from the OpenAI-compatible API standard.

**Lesson:** "OpenAI-compatible" APIs are not truly compatible. Each provider has quirks in how they handle extended parameters. Testing must cover output format, not just connectivity.

### 2026-03-12 -- AI provider chain: reordered by real-world reliability

**What happened:** After several days of production data in `ai_usage.json`, we discovered that Ollama Cloud (Nemotron 3 Super) had better availability and faster response times than NVIDIA NIM's direct endpoint. The original ordering was based on theoretical provider quality, not empirical data.

**What we did:** Promoted Ollama Cloud to primary position. Pushed NVIDIA NIM to second. Updated Vertex AI from Gemini 2.5 Flash Lite to Gemini 3 Flash Preview. Increased max output tokens for content generation tasks.

**Lesson:** Provider chain ordering should be data-driven. Instrument usage from day one and reorder based on actual success rates and latency.

### 2026-03-12 -- Frontend: navigation routing and infinite re-render

**What happened:** After the Phase 15 mobile polish changes, the navigation component entered an infinite re-render loop when switching between routes. The root cause was a state synchronization issue between the router and the language switcher.

**What we did:** Fixed the navigation routing sync to avoid circular state updates. Resolved data fetch path issues where `useData` was fetching from `/data/` instead of the GitHub Pages base path `/eleicoes-2026-monitor/data/`. Fixed stub content still displaying for already-implemented features.

**Lesson:** Static site deployment on a subpath (GitHub Pages project sites) requires consistent base path handling across all data fetching hooks, not just route configuration.

### 2026-03-12 -- Content relevance: candidate keyword filtering too strict

**What happened:** The candidate relevance filter was rejecting articles about election dynamics that did not mention specific candidate names, such as articles about "terceira via" (third way) coalitions or "segundo turno" (runoff) scenarios.

**What we did:** Relaxed the candidate relevance rule and added high-signal election keywords (`turno`, `terceira via`, `coligacao`, `chapa`) to the allowlist. Articles matching these keywords pass the relevance filter even without explicit candidate mentions.

**Lesson:** Political coverage is not always candidate-centric. Election infrastructure, coalition dynamics, and procedural topics are relevant content that a name-based filter will miss.

### 2026-03-13 -- YouTube API: quota exhaustion

**What happened:** The YouTube collection script was running one search query per candidate per collection cycle. With 9 candidates and a 10-minute cycle, this consumed the daily YouTube API quota within hours.

**What we did:** Optimized to a single combined search query using OR operators across all candidate names plus "eleicoes 2026". Added a 30-minute throttle via state file to prevent excessive API calls. Candidate association is now inferred from video title and description rather than dedicated per-candidate searches.

**Lesson:** API quota is a first-class constraint for automated collection. Design queries for minimal API calls first, then refine accuracy.

### 2026-03-13 -- Security: API keys in error logs

**What happened:** Pipeline error logs were including full API keys in error messages when provider calls failed. These logs were committed to `data/pipeline_errors.json` and visible in the public repository.

**What we did:** Added sanitization patterns to redact API keys, tokens, and credentials from all error messages before they are written to log files.

**Lesson:** Error logging in public repositories must sanitize all output by default. This should have been a day-one requirement, not a post-launch fix.

### 2026-03-13 -- Poll institutes: expanded coverage

**What happened:** The initial 6 polling institutes missed several active players in the 2026 election cycle. Users and manual checks identified Futura Inteligencia, Ipsos, MDA, and Ideia as institutes already publishing relevant data.

**What we did:** Added the four new institutes to `data/sources.json` with proper aliases, URLs, and schema configuration. Updated the poll collection scripts to handle the new sources.

**Lesson:** Source coverage must be treated as a living configuration, not a one-time setup. Regular audits against the current political landscape are necessary.

### 2026-03-21 -- AI chain: Gemini removed from high-quality tasks

**What happened:** Gemini (via Google AI) was being used as the first provider for high-quality tasks (position extraction, quiz generation and validation). Testing showed Gemini 3.1 Flash Lite did not deliver sufficient quality for these complex tasks; the JSON parse error rate was higher than Kimi K2.5 and MiniMax M2.5.

**What we did:** Reorganized the high-quality chain to Ollama Cloud (Kimi K2.5) -> NVIDIA NIM (MiniMax M2.5) -> Vertex AI (Gemini 3 Flash Preview). Gemini was kept only in the standard chain as a free-tier fallback between Ollama and Vertex. Updated the default Gemini model to `gemini-3.1-flash-lite-preview` to leverage higher free-tier limits.

**Lesson:** Structured extraction tasks (JSON) require models with better format adherence. A free model that works well for summarization may consistently fail at valid JSON generation. Model selection must be task-specific, not global.

### 2026-03-21 -- Dependabot: XSS vulnerabilities in vite-ssg and @unhead/dom

**What happened:** Dependabot opened security alerts (XSS) against `vite-ssg` and `@unhead/dom` in the frontend. Both dependencies had versions with HTML metadata injection vulnerabilities.

**What we did:** Updated `vite-ssg` and `@unhead/dom` to patched versions via `npm update`. Verified the static build remained functional and metadata injection (OG tags, JSON-LD) was still correct.

**Lesson:** Dependabot in public projects is essential. XSS alerts in SSR/SSG dependencies are particularly critical because they affect the HTML delivered to end users.

### 2026-03-21 -- CI/CD: deploy not triggering after automated workflows

**What happened:** The deploy workflow was not triggered when commits were pushed by the GitHub Actions bot (collect, validate, curate workflows). GitHub Actions intentionally does not fire workflow triggers for commits made by `github-actions[bot]` to prevent infinite loops.

**What we did:** Added a `workflow_run` trigger to `deploy.yml` that monitors successful completion of Collect, Validate, and Curate workflows. Added a concurrency group to prevent deploy pile-ups.

**Lesson:** GitHub Actions has intentional restrictions on chained triggers. For multi-workflow pipelines that write to the same repository, `workflow_run` is the correct strategy to trigger downstream workflows.

### 2026-03-21 -- Candidate position seeding

**What happened:** The candidate position knowledge base (`candidates_positions.json`) depended exclusively on the news pipeline to fill positions. For less media-covered candidates, many topics remained `unknown` indefinitely.

**What we did:** Created `scripts/seed_candidates_positions.py`, a one-shot script that populates baseline positions from structured sources: Wikipedia PT (political profile), Câmara dos Deputados (nominal votes), Senado Federal (bill votes), and AI synthesis (Gemini with grounding). The script is idempotent: it only fills entries marked `unknown` and never overwrites data already reviewed by human editors. Added a CI step that triggers seeding when the unknown ratio exceeds 50%.

**Lesson:** Candidate positions for presidential elections are largely public data already documented in institutional sources. Relying exclusively on news for this data underutilizes available information. Seeding as a baseline accelerates the portal's coverage timeline.

---

## Project numbers
At the current snapshot (2026-03-21), the measurable baseline is:

- 17 phases completed (16 main + Phase 17 Vertex AI Search extension).
- 622 commits in repository history.
- 21 active RSS sources in `data/sources.json`, plus 8 party sources and 10 polling institute sources.
- 9 candidates modeled in `data/candidates.json`.
- 6 GitHub Actions workflows: collect (10min), validate (30min), curate (hourly), deploy, update-quiz, watchdog.
- 4 article statuses: `raw`, `validated`, `curated`, `irrelevant`.
- An automated editorial feedback mechanism filtering irrelevant content.
- Circuit breaker and per-run AI call limits for pipeline resilience.
- Seed script (`seed_candidates_positions.py`) for baseline candidate position population from Wikipedia, Câmara/Senado APIs, and AI synthesis.
- AI chain split by quality tier: standard (Nemotron 3 Super -> Gemini Flash Lite -> Vertex) and high-quality (Kimi K2.5 -> MiniMax M2.5 -> Vertex).

These numbers are not marketing decoration; they demonstrate that the system was shipped, operated under real conditions, and iteratively corrected based on production feedback.

## Current status
The portal is live and operating continuously. The AI provider chain has been reordered based on empirical reliability data. Content quality has improved through the editorial feedback loop. CI/CD race conditions are managed but not fully eliminated. The system processes hundreds of articles daily across 21 RSS sources, 8 party websites, 10 polling institutes, and YouTube, with automated bilingual summarization, sentiment analysis, and quiz position extraction.

The next focus areas are monitoring long-term provider stability, expanding editorial feedback rules, and evaluating whether the Vertex AI Search integration (Phase 17) delivers measurable user value.

