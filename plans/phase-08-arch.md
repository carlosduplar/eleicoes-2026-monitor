# Phase 08 — Polling Tracker

## Objective

Implement the poll scraping pipeline (`collect_polls.py` via Playwright) and the `PollTracker.jsx` Recharts line chart showing historical polling data per candidate over time. Follow WF-04 wireframe. Add `PollsPage.jsx` as the page wrapper at `/pesquisas`.

## Input Context

- `docs/wireframes/WF-04-poll-tracker.html` — Reference wireframe (open in browser before implementing)
- `docs/adr/000-wireframes.md` — Design tokens
- `docs/prompt-eleicoes2026-v5.md` lines 336-343 — Poll institute URLs (`POLL_SOURCES`)
- `docs/schemas/polls.schema.json` — Polls data schema (from Phase 01)
- `data/sources.json` — Poll sources metadata (from Phase 03)
- `site/src/utils/candidateColors.js` — Candidate color map (from Phase 07)
- `site/src/hooks/useData.js` — Data fetching hook (from Phase 04)
- `site/src/components/MethodologyBadge.jsx` — Required on all data dashboards (from Phase 07)

## Deliverables

### 1. `scripts/collect_polls.py`

Playwright-based scraper for 6 poll institutes.

**Poll institutes (from `POLL_SOURCES`):**
- Datafolha: `https://datafolha.folha.uol.com.br/eleicoes/`
- Quaest: `https://quaest.com.br/pesquisas/`
- AtlasIntel: `https://atlasintel.com/eleicoes/`
- Paraná Pesquisas: `https://paranapesquisas.com.br/pesquisas/`
- PoderData: `https://www.poder360.com.br/poderdata/`
- Real Time Big Data: `https://www.realtimebigdata.com.br/pesquisas.html`

**Key behaviors:**
- For each active institute in `data/sources.json`, launch Playwright Chromium
- Extract poll data: date, institute name, sample size, methodology, and per-candidate percentages
- Generate poll ID: `sha256(f"{institute}_{date}".encode())[:16]`
- Deduplicate: skip polls already in `data/polls.json` by ID
- Append new polls to `data/polls.json`
- On scrape failure for a single institute: log to `data/pipeline_errors.json`, continue to next
- Use headless mode; `timeout=30000` per page
- Print summary: "Collected X new polls from Y institutes (Z errors)"
- **Idempotent:** running twice produces no duplicates

**Data extraction strategy:** since institute sites vary, implement a best-effort extractor:
- Look for structured data (JSON-LD, tables with candidate names + percentages)
- Fallback: extract any `<table>` rows containing candidate names from `CANDIDATES`
- Store raw extracted text in `raw_html_snippet` field for debugging

### 2. `data/polls.json` schema

Seed file (if not already present from Phase 01):
```json
{
  "$schema": "../docs/schemas/polls.schema.json",
  "polls": [
    {
      "id": "sha256[:16]",
      "institute": "Datafolha",
      "date": "2026-03-01",
      "sample_size": 2000,
      "methodology": "Presencial",
      "margin_of_error": "±2pp",
      "results": [
        {"candidate_slug": "lula", "percentage": 35.0},
        {"candidate_slug": "tarcisio", "percentage": 28.0}
      ],
      "source_url": "https://datafolha.folha.uol.com.br/...",
      "collected_at": "2026-03-05T10:30:00Z"
    }
  ],
  "last_updated": "2026-03-05T10:30:00Z",
  "total_count": 0
}
```

### 3. `site/src/components/PollTracker.jsx`

Recharts `LineChart` showing polling trends over time.

**Data source:** `useData('polls')` → `data/polls.json`

**Chart spec (Recharts):**
- X axis: `date` (formatted as `DD/MM` in pt-BR, `MM/DD` in en-US)
- Y axis: percentage (0–100%), labeled `%`
- One `Line` per candidate: `stroke={CANDIDATE_COLORS[slug]}`, `strokeWidth={2}`, `dot={false}` (unless < 5 data points)
- `Legend`: candidate names with their color; position bottom
- `Tooltip`: shows all candidates' values at hovered date
- `ResponsiveContainer`: width `100%`, height `400`

**Institute filter:** dropdown (or chip group) to filter by poll institute. "Todas" / "All" shows all institutes combined. Individual selections show only that institute's data.

**States:**
- Loading: "Carregando pesquisas..." / "Loading polls..."
- Empty: "Sem dados de pesquisas disponíveis." / "No poll data available."
- Error: "Erro ao carregar pesquisas." / "Error loading polls."

**MethodologyBadge:** rendered below the chart.

### 4. `site/src/pages/PollsPage.jsx`

Page wrapper (replacing Phase 04 placeholder):
- `<Helmet>`: title "Pesquisas Eleitorais | Portal Eleições BR 2026", JSON-LD `Dataset`
- `<PollTracker />`
- Route: `/pesquisas`

### 5. i18n additions

**`site/src/locales/pt-BR/common.json`** — add keys:
```json
"polls": {
  "title": "Pesquisas Eleitorais",
  "loading": "Carregando pesquisas...",
  "empty": "Sem dados de pesquisas disponíveis.",
  "error": "Erro ao carregar pesquisas.",
  "filter_all": "Todas",
  "institute_label": "Instituto",
  "percentage_label": "Intenção de voto (%)",
  "methodology_note": "Dados reproduzidos dos institutos originais sem modificação editorial."
}
```

**`site/src/locales/en-US/common.json`** — English equivalents.

### 6. Unit tests — `scripts/test_collect_polls.py`

- `test_poll_id_is_sha256_prefix` — ID format `sha256(f"{institute}_{date}")[:16]`
- `test_dedup_skips_existing_polls` — Poll already in data is not added again
- `test_idempotent_double_run` — Running twice produces same count
- `test_institute_failure_does_not_crash` — Bad URL skips gracefully, continues
- `test_polls_schema_valid` — Output conforms to `polls.schema.json`

## Constraints

- Playwright `chromium` is installed in the CI environment by `collect.yml` (Phase 05)
- Each scrape is wrapped in `try/except`; failures are logged, never re-raised
- Poll data is never modified — `methodology_note` i18n key makes this explicit in the UI
- Recharts must be already in `site/package.json` from Phase 04
- The Playwright scraper must run with `playwright.async_api` (not sync) to avoid blocking
- `collect_polls.py` is called by `collect.yml` with `|| echo "polls failed, continuing"` — this is intentional since scraping may legitimately fail

## Acceptance Criteria

- [ ] `python scripts/collect_polls.py` runs without crashing (even if no data is scraped due to site changes)
- [ ] `data/polls.json` exists and is valid JSON after running the script
- [ ] Running `collect_polls.py` twice does not create duplicate polls
- [ ] `PollTracker` renders at `/pesquisas` with Recharts line chart
- [ ] Institute filter switches the chart data
- [ ] Each candidate line uses their correct hex color from `CANDIDATE_COLORS`
- [ ] `MethodologyBadge` renders below the chart
- [ ] Language toggle switches all text to en-US
- [ ] All unit tests pass: `python -m pytest scripts/test_collect_polls.py -v`
- [ ] `npm run build` succeeds

## Commit & Push

After all deliverables are verified:

```
git add scripts/collect_polls.py scripts/test_collect_polls.py data/polls.json site/src/components/PollTracker.jsx site/src/pages/PollsPage.jsx site/src/locales/
git commit -m "feat(phase-08): Polling tracker — Playwright scraper + Recharts chart

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-08-arch.DONE`.
