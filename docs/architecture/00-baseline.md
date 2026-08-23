# 00 - Baseline (Phase 0)

Date: 2026-08-23. HEAD: `db6b4be1c` ("perf(site): inline boot data into prerendered pages to kill skeleton flash"). Working tree clean except untracked `site/src/utils/bootData.js`.

All claims tagged OBSERVED / INFERRED / ASSUMED / UNKNOWN.

## System purpose

OBSERVED (README.md, CI workflows, site source): bilingual (pt-BR/en-US) static portal monitoring Brazil's 2026 presidential election: news, AI summaries, sentiment, polls, betting-market odds, candidate positions, quiz. Python scheduled pipeline collects from RSS/party sites/polling institutes/social/markets APIs, enriches with LLM provider chain, curates, and writes JSON into `site/public/data/`. Data is committed to git by CI bots. React SSG site reads that JSON at build time and deploys to GitHub Pages. Editorial transparency (methodology page, visible filtering rules) is a stated product surface.

INFERRED: git doubles as the database; there is no server-side store. Every "write" is a git commit by a bot workflow.

## Commands run and baseline status

Environment: Termux/linux, Python 3.13.13 (repo pins 3.12 via `.python-version`; CI uses 3.12), Node v24.15.0.

| Command | Result |
|---|---|
| `python -m pytest scripts/ tests/ -q --tb=line --ignore=scripts/test_collect_polls.py --ignore=scripts/test_index_to_vertex_search.py` | **153 passed, 2 failed** |
| failures | `scripts/test_sanitize_dedup.py::test_tfidf_clusters_and_selects_canonical`, `scripts/test_summarize.py::test_cosine_dedup_clusters_similar` - both `ModuleNotFoundError: No module named 'sklearn'` (local env gap only) |
| blocked modules (not collected) | `scripts/test_collect_polls.py` (no `playwright` wheel for Termux), `scripts/test_index_to_vertex_search.py` (no `google-cloud-discoveryengine`) |
| `node node_modules/vite-react-ssg/bin/vite-react-ssg.js build && node scripts/postbuild-seo.mjs` (in `site/`) | **success**, full prerender incl. candidate/comparison SEO pages |

Env installs performed locally (no repo changes): typing_extensions, pydantic 1.10.26 (binary-only constraint), sniffio, httpx2/httpcore2, distro, feedparser, beautifulsoup4, soupsieve, lxml 6.1.2 (source build). Not installable on Termux: scikit-learn, playwright, google-cloud-discoveryengine (no wheels).

INFERRED: the 2 local failures and 2 blocked modules are environment gaps, not code defects; CI (ubuntu, `pip install -r requirements.txt`) is expected to run them green. UNKNOWN until a recent CI log is inspected.

Note: `npm run build` fails on Termux because `node_modules/.bin/*` shebangs point to `/usr/bin/env` which does not exist there (`/data/data/com.termux/files/usr/bin/env`). Invoking bin JS via `node` directly is equivalent. Local-env quirk only.

## Repository map

```
eleicoes-2026-monitor/
├── main.py                      # dead stub: prints hello (OBSERVED)
├── pyproject.toml               # uv stub: description placeholder, deps=[openai] (OBSERVED)
├── requirements.txt             # real Python manifest: 12 deps (OBSERVED)
├── scripts/                     # pipeline: ~40 files, ~17.3k LOC (OBSERVED)
│   ├── ai_client.py             # 1564 LOC shared LLM client (provider chain, breaker, preflight)
│   ├── collect_rss.py           # 455  RSS ingestion
│   ├── collect_parties.py       # 646  party-site ingestion
│   ├── collect_polls.py         # 914  polling institutes
│   ├── collect_social.py        # 442  Twitter/YouTube
│   ├── collect_markets.py       # 351  Polymarket odds
│   ├── scrape_articles.py       # 292  Bright Data -> Playwright fallback scraping
│   ├── summarize.py             # 683  AI validation+summaries (Editor role)
│   ├── analyze_sentiment.py     # 678  AI sentiment
│   ├── curate.py                # 606  curation/prominence (Editor-chefe role)
│   ├── build_data.py            # 237  derived-data publish step
│   ├── generate_quiz.py         # 1202 quiz generation
│   ├── seed_candidates_positions.py        # 1190
│   ├── extract_positions_from_articles.py  # 287
│   ├── archive_articles.py      # 276  hot/warm/cold retention
│   ├── deduplicate_narratives.py, editor_feedback.py, sync_editor_feedback.py,
│   │   generate_rss_feed.py, generate_seo_pages.py, index_to_vertex_search.py,
│   │   merge_json.py, watchdog.py, unpublish.py, benchmark_ai.py, ...
│   ├── sanitize/                # package: constants, dedup (TF-IDF), relevance, batch_cleanup
│   └── test_*.py                # 19 colocated unit-test modules
├── tests/
│   └── test_seed_candidates_positions.py   # near-duplicate of scripts copy; differs (UNKNOWN why)
├── site/                        # frontend app
│   ├── package.json             # react 18, react-router-dom 7, i18next, recharts, marked;
│   │                            # vite 7 + vite-react-ssg 0.9.2 (+ vite-ssg 28 also present)
│   ├── src/{App,main}.jsx, pages/(11), components/(13), hooks/, locales/, utils/
│   ├── public/data/*.json       # THE data store (see below), committed to git
│   ├── public/feed*.xml
│   ├── scripts/{patch-vite-react-ssg,postbuild-seo}.mjs
│   ├── playwright.config.js + playwright-validation*.js
│   └── dist/                    # build output (gitignored)
├── docs/schemas/*.schema.json   # 11 JSON schemas + types.ts
├── docs/adr/000..007            # existing ADRs
├── .github/workflows/           # 7 workflows (below)
├── plans/, tasks/, qa/          # historical phase plans/reports (phase-01..18)
└── *.yaml (22 root files)       # playwright-cli session artifacts, tracked in git (junk)
```

## Main execution paths

OBSERVED (workflows):

| Workflow | Trigger | Script chain | Writes |
|---|---|---|---|
| Collect (Reporter) | cron `*/15 0-3,8-23 * * *` | sync_editor_feedback → collect_{rss,parties,polls,social,markets} → scrape_articles → summarize --limit 12 → analyze_sentiment --limit 12 → build_data → generate_rss_feed → archive_articles → index_to_vertex_search | `site/public/data/**`, `feed*.xml` |
| Validate (Editor) | push to `site/public/data/**` + cron `*/30` | summarize → analyze_sentiment → build_data | articles/sentiment/editor_feedback.json |
| Curate (Editor-chefe) | hourly `0 0-3,8-23` | `python -m scripts.curate` (continue-on-error) | articles, curated_feed, weekly_briefing, quiz.json, .curate_last_run, editor_feedback |
| Update Quiz Positions | daily 03:00 | `python -m scripts.generate_quiz` | quiz.json |
| Watchdog | daily 09:00 | `scripts/watchdog.py` | pipeline_health.json |
| Deploy Pages | push `site/**` or workflow_run success | generate_seo_pages → npm ci/build → upload/deploy | GitHub Pages artifact from `site/dist` |
| update-candidates-positions.yml | (not read in full yet - UNKNOWN details) | seed/extract/review positions | candidates_positions*.json |

All five data-writing workflows share concurrency group `repo-write-${{ github.ref }}` and each embeds its own copy of pull/rebase/push-retry/conflict-resolution shell logic (~25 lines duplicated x5).

Publication state machine (README + schemas): `raw -> validated -> curated`, plus `irrelevant` filtered via `editor_feedback.json` self-healing loop.

## Dependency and integration inventory

Python (requirements.txt): feedparser, beautifulsoup4, lxml, requests, playwright, openai, google-auth, tweepy, google-api-python-client, scikit-learn, jsonschema, google-cloud-discoveryengine.

Node (site/package.json): react/react-dom 18, react-router-dom 7, i18next + http-backend + react-i18next, recharts, marked, @unhead/dom, react-helmet-async; dev: vite 7, vite-react-ssg, vite-ssg, @playwright/test, picomatch. Overrides pin postcss/unhead/lodash.

External integrations OBSERVED: Bright Data Web Unlocker (primary HTML fetch), Playwright/Chrome (fallback fetch), LLM provider chain Poolside -> Ollama Cloud -> NVIDIA NIM -> OpenRouter/free (+ optional preflight TTFT selection), Twitter API v2, YouTube Data API, Google Vertex AI Search (indexing), GitHub Pages + Cloudflare CDN (per README).

Data store: `site/public/data/` - 21 entries incl. articles.json (2.5MB), editor_feedback.json (4.3MB), pipeline_errors.json (1.2MB), candidates_positions(+draft).json, polls, markets, quiz, sentiment, curated_feed, weekly_briefing, sources, tse_data, transparencia_data, donors, archives/.

Secrets referenced by workflows: BRIGHTDATA_API_KEY/ZONE, POOLSIDE/NVIDIA/OPENROUTER/OLLAMA_API_KEY, TWITTER_BEARER_TOKEN, YOUTUBE_API_KEY, GOOGLE_APPLICATION_CREDENTIALS_JSON, VERTEX_SEARCH_ENGINE_ID, GCP_PROJECT_ID.

## Baseline observations (anomalies carried into Phase 1)

1. OBSERVED: README architecture diagram says data lives in `data/*.json` at repo root; actual store is `site/public/data/`. No root `data/` dir exists.
2. OBSERVED: two competing Python manifests (`pyproject.toml` stub vs `requirements.txt`).
3. OBSERVED: `main.py` is a dead hello-world stub.
4. OBSERVED: 22 tracked playwright session YAMLs at repo root.
5. OBSERVED: `editor_feedback.json` (4.3MB) and `pipeline_errors.json` (1.2MB) are committed AND published publicly through `site/public/data/` -> Pages artifact. INFERRED operational/size concern; UNKNOWN whether any external consumer depends on them being published.
6. OBSERVED: helper duplication across collectors (`utc_now_iso`, `build_article_id`, `ArticlesDocument` load/save, `_load_pipeline_errors`/`_append_pipeline_error`, `_load_json`) repeated in collect_rss/collect_social/curate/deduplicate_narratives/etc.
7. OBSERVED: untracked `site/src/utils/bootData.js` sits beside HEAD commit claiming boot-data inlining. UNKNOWN whether it is referenced by the build (build succeeded with file present; not tested without it). Do not delete without verification.
8. OBSERVED: `tests/test_seed_candidates_positions.py` differs from `scripts/test_seed_candidates_positions.py`.
9. INFERRED: git-as-database with 5 concurrent bot writers + per-workflow conflict shell is the highest-complexity operational area.

## Unknowns and blocked observations

- UNKNOWN: recent CI run health (Collect/Validate/Curate/Deploy success rates); no logs inspected yet.
- UNKNOWN: whether anything external consumes published `pipeline_errors.json` / `editor_feedback.json` URLs.
- UNKNOWN: why both `tests/` and `scripts/` copies of seed test exist and diverged.
- UNKNOWN: contents of `update-candidates-positions.yml` (not yet read in Phase 0).
- UNKNOWN: e2e Playwright suite status (`site/playwright.config.js`) - not executed locally (browser download required).
- BLOCKED locally: sklearn/playwright/google-cloud-dependent tests cannot run on Termux; rely on CI evidence or accept subset coverage during migration steps.

## Next

Phase 1 diagnosis: end-to-end flow tracing, dependency-direction analysis, duplication clusters, risk register. No production code changes.
