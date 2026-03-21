# Case Study: Portal Eleicoes BR 2026

## Executive summary
Portal Eleicoes BR 2026 was designed as a public transparency product: a bilingual portal (pt-BR and en-US) to monitor election news, sentiment trends, polling data, and candidate position signals for Brazil's 2026 presidential cycle. The goal was not to publish another opinion website, but to ship an auditable editorial infrastructure where users can see how data is collected, how AI is applied, and how each article moves through publication stages. The core promise is straightforward: people should be able to read a story, understand its processing status, and inspect the technical path that produced what they see on screen.

The implementation combines a static React + Vite frontend with a Python data pipeline and GitHub Actions automation. Instead of relying on one AI vendor, the architecture uses a multi-provider fallback chain to improve availability while keeping costs under control. Instead of hiding limitations, the product exposes methodology, disclaimers, sources, and processing state. Instead of introducing complex hosting infrastructure, deployment runs on GitHub Pages with Cloudflare in front. The result is a lightweight, low-cost, traceable system that can evolve phase by phase without losing architectural clarity.

## Stack and architecture
From a technical perspective, the stack was selected for operational predictability. On the frontend, React 18 with Vite and `vite-react-ssg` pre-renders key routes so the site can run as static content on GitHub Pages while still serving SEO and GEO goals. UI implementation follows standalone HTML wireframes defined in ADR 000, and the design token system (`--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border`) keeps visual consistency across feed, dashboards, quiz, methodology, and now the case study page.

On the data side, Python 3.12 handles ingestion and transformations. Pipeline scripts were built with idempotency and traceability as first-class constraints. The default identifier `sha256(url.encode())[:16]` prevents article duplication across runs, and output JSON follows contracts in `docs/schemas/*.schema.json` and `docs/schemas/types.ts`. This alignment keeps frontend and backend synchronized around one shared data model, which lowers regression risk caused by shape drift.

Publication architecture uses three editorial states (`raw -> validated -> curated`) and optimizes for continuity. Even when an AI provider is unavailable, the pipeline keeps moving. Content can be shown as `raw` with title and metadata while slower or more expensive processing continues asynchronously. This avoids binary all-or-nothing publishing behavior and better reflects how near-real-time election monitoring should work in practice.

## Agent hierarchy
Delivery execution was intentionally organized around an explicit agent hierarchy documented in PLAN and handoff files. Opus acted as Architect, consolidating strategy, wireframes, ADRs, and schema contracts. Codex acted as Tactical lead, transforming architecture into concrete task specs and verification criteria. MiniMax acted as Operations implementor, executing changes through disciplined loops. Gemini acted as QA, focusing on validation, interface testing, and reporting.

Governance followed the RALPH protocol: Read, Analyze, List, Plan, Handle. For long tasks, this structure reduced improvisation by forcing context review before code edits, converting ambiguity into explicit checklists, and closing each loop with verification. In this project, RALPH was not just process vocabulary; it shaped phase sequencing, spec writing, and failure handling with bounded retries and escalation rules.

Inter-agent handoff relies on sentinel files such as `plans/phase-NN-arch.DONE`. This simple mechanism replaces heavy orchestration with repository-native traceability. When a phase closes, the sentinel signals that architecture and implementation are aligned and the next layer can proceed without hidden state. For a public iterative project, the pattern proved highly practical: low coupling, clear checkpoints, and auditable history.

## Ingestion pipeline
The ingestion model follows a newsroom metaphor with three roles. Foca (collector) runs at high frequency and primarily consumes RSS, with expansion into party websites and other structured sources. Editor (validator) processes collected items, runs bilingual summarization, and prepares data for analytical components. Editor-chefe (curator) runs at a slower cadence with emphasis on prominence, consistency, and quality gates.

Publication stages are explicit in the data itself: `raw`, `validated`, and `curated`. In `raw`, the portal prioritizes speed and transparency over polish: title, source, and timestamp can already be visible while analysis is still in progress. In `validated`, bilingual summaries and richer metadata are attached. In `curated`, the story gets an additional automated prominence layer. This staged funnel avoids unnecessary blocking and delivers incremental value instead of waiting for perfect completeness.

The AI chain is built for resilience and cost control. For standard tasks: NVIDIA NIM (Nemotron 3 Super) -> Ollama Cloud (Nemotron 3 Super) -> Gemini 3.1 Flash Lite (free tier) -> Vertex AI (Gemini 3 Flash Preview, paid) -> MiMo V2 Flash. For high-quality tasks (quiz, positions): Ollama Cloud (Kimi K2.5) -> NVIDIA NIM (MiniMax M2.5) -> Vertex AI. The non-negotiable rule is that AI errors must not stop the pipeline. If a call fails, the system logs the error, tries the next provider, and continues. If all providers fail, the article still remains in a coherent state rather than being silently dropped. This approach prioritizes operational continuity and reduces single-vendor risk.

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

## Project numbers
At the publication snapshot of this phase, the measurable baseline is:

- 16 planned main phases, plus one optional extension phase (Phase 17).
- 622 commits in repository history.
- 21 active RSS sources in `data/sources.json`, plus 8 party sources and 10 polling institute sources.
- 9 candidates modeled in `data/candidates.json`.
- Pipeline cadence with collector every 10 minutes, validator every 30 minutes, and curator on an approximately 90-minute window.
- 4 article statuses: `raw`, `validated`, `curated`, `irrelevant`.
- Seed script for baseline candidate position population from institutional sources.
- AI chain split by quality tier for better task adherence.

These numbers are not marketing decoration; they demonstrate operational scope under strict cost constraints and static hosting limitations.

## Next steps
With Phase 16 complete, the `1.0.0` quality baseline is now established through automated tests and formal security/SEO/accessibility/code-review audits.

The next technical milestone remains the optional Phase 17 extension (Vertex AI Search), to be evaluated by cost, semantic retrieval usefulness, and measurable user value. In parallel, the project should maintain continuous workflow operation, data-quality monitoring, and bilingual documentation updates.

