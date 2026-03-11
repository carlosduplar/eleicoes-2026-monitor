# Phase 16 — Task 01 Spec (QA Final: Tests, Security, SEO, Accessibility, Final Docs)

> Planner: Opus 4.6 | Implementor: Codex | Date: 2026-03-11

---

## 1. Inputs and Mandatory References

| # | Ref | Path | Purpose |
|---|-----|------|---------|
| 1 | Architecture spec | `plans/phase-16-arch.md` | Phase objectives, deliverables, acceptance criteria |
| 2 | Agent protocol | `docs/agent-protocol.md` | RALPH loop, escalation rules, handoff files |
| 3 | TypeScript types | `docs/schemas/types.ts` | `Article`, `Sentiment`, `Quiz`, `Poll`, `Candidate`, all unions |
| 4 | Articles schema | `docs/schemas/articles.schema.json` | Required: `id`, `url`, `title`, `source`, `published_at`, `collected_at`, `status` |
| 5 | Sentiment schema | `docs/schemas/sentiment.schema.json` | Required: `updated_at`, `article_count`, `methodology_url`, `disclaimer_pt`, `disclaimer_en`, `by_topic`, `by_source` |
| 6 | Quiz schema | `docs/schemas/quiz.schema.json` | Required: `generated_at`, `ordered_topics`, `topics` |
| 7 | Polls schema | `docs/schemas/polls.schema.json` | Required: `id`, `institute`, `published_at`, `collected_at`, `type`, `results` |
| 8 | Candidates schema | `docs/schemas/candidates.schema.json` | Required: `candidates` array |
| 9 | build_data.py | `scripts/build_data.py` | Functions: `consolidate_articles`, `_deduplicate_by_id`, `_validate_articles` |
| 10 | curate.py | `scripts/curate.py` | Functions: `_read_last_run_epoch`, `main` (90-min skip logic) |
| 11 | watchdog.py | `scripts/watchdog.py` | Function: `main` (writes `data/pipeline_health.json`) |
| 12 | extract_quiz_positions.py | `scripts/extract_quiz_positions.py` | Functions: `divergence_score`, `select_quiz_topics`, `filter_snippets`, `build_options`, `load_articles` |
| 13 | ai_client.py | `scripts/ai_client.py` | Functions: `call_with_fallback`, `summarize_article`, `extract_candidate_position` |
| 14 | Existing test: test_ai_client.py | `scripts/test_ai_client.py` | Already covers: fallback chain, usage tracking, error handling — extend if gaps found |
| 15 | React components | `site/src/components/*.jsx` | 12 components to audit for a11y, XSS, i18n |
| 16 | React pages | `site/src/pages/*.jsx` | 10 pages: Home, SentimentPage, PollsPage, QuizPage, QuizResult, CandidatePage, CandidatesPage, ComparisonPage, MethodologyPage, CaseStudyPage |
| 17 | CSS | `site/src/styles.css` | Custom properties: `--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border` |
| 18 | i18n locales | `site/src/locales/{pt-BR,en-US}/common.json` | All UI strings |
| 19 | GitHub workflows | `.github/workflows/*.yml` | collect, validate, curate, deploy, watchdog, update-quiz |
| 20 | ADRs | `docs/adr/000-006*.md` | 7 ADRs for README links |
| 21 | Case study | `docs/case-study/{pt-BR,en-US}.md` | Living documentation for final update |
| 22 | CHANGELOG.md | `CHANGELOG.md` | Current state: entries for Phases 0-5 only |
| 23 | README.md | `README.md` | Current state: Phase 04 status, needs full overhaul |
| 24 | Wireframes | `docs/wireframes/WF-*.html` | Reference for visual QA of Playwright tests |
| 25 | site package.json | `site/package.json` | Scripts: dev, build, preview; NO Playwright yet |

---

## 2. Files to Create or Modify

### 2.1 Python Unit Tests (CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `scripts/test_build_data.py` | CREATE | Unit tests for dedup, 500-limit, sort order, schema validation |
| 2 | `scripts/test_curate.py` | CREATE | Unit tests for 90-min skip logic, timestamp read/write |
| 3 | `scripts/test_watchdog.py` | CREATE | Unit tests for health JSON structure output |
| 4 | `scripts/test_extract_quiz_positions.py` | CREATE | Unit tests for divergence scoring, topic selection, cluster coverage |

### 2.2 Playwright Setup and Integration Tests (CREATE)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 5 | `site/package.json` | MODIFY | Add `@playwright/test` to devDependencies, add `test:e2e` script |
| 6 | `site/playwright.config.js` | CREATE | Playwright config: baseURL from preview server, projects: chromium |
| 7 | `qa/tests/test_home.spec.js` | CREATE | Feed renders, language toggle, countdown timer |
| 8 | `qa/tests/test_sentiment.spec.js` | CREATE | Dashboard heatmap, toggle Por Tema/Por Fonte |
| 9 | `qa/tests/test_polls.spec.js` | CREATE | Chart renders, institute filter |
| 10 | `qa/tests/test_quiz.spec.js` | CREATE | Full quiz flow: answer all, result shows, share button |
| 11 | `qa/tests/test_quiz_neutrality.spec.js` | CREATE | No candidate slug or source text during question phase |
| 12 | `qa/tests/test_candidate.spec.js` | CREATE | `/candidato/lula` renders with JSON-LD |
| 13 | `qa/tests/test_comparison.spec.js` | CREATE | `/comparar/lula-vs-tarcisio` renders |
| 14 | `qa/tests/test_methodology.spec.js` | CREATE | All 5 sections present, language toggle |
| 15 | `qa/tests/test_rss.spec.js` | CREATE | `feed.xml` and `feed-en.xml` are valid XML |
| 16 | `qa/tests/test_mobile.spec.js` | CREATE | 390px: BottomNav visible, desktop Nav hidden, quiz immersive |

### 2.3 QA Reports (CREATE via skills)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 17 | `qa/phase-16-security-report.md` | CREATE | Output of `security-threat-modeler` skill |
| 18 | `qa/phase-16-seo-report.md` | CREATE | Output of `seo-audit` skill |
| 19 | `qa/phase-16-code-review.md` | CREATE | Output of `tech-lead-reviewer` skill |
| 20 | `qa/phase-16-accessibility-report.md` | CREATE | Output of `web-design-guidelines` skill |

### 2.4 Final Documentation (MODIFY)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 21 | `README.md` | MODIFY | Full overhaul: badges, screenshot, architecture, setup, secrets, candidates, ADRs, license |
| 22 | `CHANGELOG.md` | MODIFY | Add entries for Phases 06-16, add `[1.0.0]` release entry |
| 23 | `docs/case-study/pt-BR.md` | MODIFY | Final pass via `docs-maintainer` skill |
| 24 | `docs/case-study/en-US.md` | MODIFY | Final pass via `docs-maintainer` skill |

### 2.5 Sentinel Files

| # | Path | Action | Description |
|---|------|--------|-------------|
| 25 | `plans/phase-16-arch.DONE` | CREATE | Architect completion sentinel |

---

## 3. Function Signatures and Types

### 3.1 `scripts/test_build_data.py` (CREATE)

```python
"""Unit tests for scripts/build_data.py — dedup, size limit, sort order, schema validation."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any

# Helpers

def _make_article(
    url: str = "https://example.com/1",
    title: str = "Test",
    source: str = "TestSource",
    published_at: str = "2026-01-01T00:00:00Z",
    status: str = "raw",
    **overrides: Any,
) -> dict[str, Any]:
    """Create a minimal article dict conforming to articles.schema.json required fields."""
    ...

@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect build_data paths to tmp_path for isolation."""
    ...

# Tests

def test_dedup_removes_duplicate_ids(data_dir: Path) -> None:
    """Two articles with same URL produce same sha256 ID; dedup keeps only first."""
    ...

def test_dedup_preserves_unique_articles(data_dir: Path) -> None:
    """Articles with different URLs all survive dedup."""
    ...

def test_limit_500_articles(data_dir: Path) -> None:
    """consolidate_articles caps output at 500 entries."""
    ...

def test_sort_by_published_at_descending(data_dir: Path) -> None:
    """Articles sorted newest-first by published_at."""
    ...

def test_schema_validation_warns_on_missing_field(data_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Articles missing required fields produce validation warnings but do not crash."""
    ...

def test_idempotent_double_run(data_dir: Path) -> None:
    """Running consolidate_articles twice produces identical output."""
    ...
```

**Data contract:** Each test article must include all `required` fields from `articles.schema.json`: `id`, `url`, `title`, `source`, `published_at`, `collected_at`, `status`. The `id` field MUST be `sha256(url.encode())[:16]`.

### 3.2 `scripts/test_curate.py` (CREATE)

```python
"""Unit tests for scripts/curate.py — 90-minute skip logic."""
from __future__ import annotations

import time
import pytest
from pathlib import Path

@pytest.fixture
def curate_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect curate.py's data path to tmp_path."""
    ...

def test_skip_when_last_run_less_than_90_min(curate_dir: Path) -> None:
    """main() exits early if .curate_last_run is < 90 minutes old."""
    ...

def test_run_when_last_run_older_than_90_min(curate_dir: Path) -> None:
    """main() proceeds if .curate_last_run is > 90 minutes old."""
    ...

def test_run_when_no_last_run_file(curate_dir: Path) -> None:
    """main() proceeds if .curate_last_run does not exist."""
    ...

def test_last_run_file_updated_after_run(curate_dir: Path) -> None:
    """After successful run, .curate_last_run contains current epoch."""
    ...
```

**Data contract:** `curate.py` reads `data/.curate_last_run` (plain text file with epoch float). Tests must mock the epoch comparison, not sleep for 90 minutes.

### 3.3 `scripts/test_watchdog.py` (CREATE)

```python
"""Unit tests for scripts/watchdog.py — health JSON structure."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

@pytest.fixture
def watchdog_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect watchdog.py's output path to tmp_path."""
    ...

def test_health_json_has_required_keys(watchdog_dir: Path) -> None:
    """pipeline_health.json must have: checked_at, workflows, status."""
    ...

def test_health_json_checked_at_is_iso8601(watchdog_dir: Path) -> None:
    """checked_at field is valid ISO 8601 string."""
    ...

def test_health_json_is_valid_json(watchdog_dir: Path) -> None:
    """Output file is parseable JSON, not empty."""
    ...

def test_idempotent_double_run(watchdog_dir: Path) -> None:
    """Running main() twice produces valid JSON (no append corruption)."""
    ...
```

**Data contract:** `data/pipeline_health.json` must have at minimum: `checked_at` (ISO 8601), `workflows` (dict), `status` (string).

### 3.4 `scripts/test_extract_quiz_positions.py` (CREATE)

```python
"""Unit tests for scripts/extract_quiz_positions.py — divergence, topics, coverage."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any

# Import target functions
# from scripts.extract_quiz_positions import divergence_score, select_quiz_topics, ...

def _make_position(
    stance: str = "favor",
    weight: int = 2,
    confidence: str = "high",
    text_pt: str = "Texto",
    text_en: str = "Text",
) -> dict[str, Any]:
    """Create a minimal position dict."""
    ...

# --- divergence_score ---

def test_divergence_score_all_same_stance() -> None:
    """All candidates with same stance -> divergence near 0."""
    ...

def test_divergence_score_opposite_stances() -> None:
    """Candidates with opposite stances -> divergence near 1.0."""
    ...

def test_divergence_score_empty_list() -> None:
    """Empty positions list -> divergence 0."""
    ...

# --- select_quiz_topics ---

def test_select_quiz_topics_orders_by_divergence() -> None:
    """Topics with highest divergence_score appear first in ordered_topics."""
    ...

def test_select_quiz_topics_covers_multiple_clusters() -> None:
    """Selected topics span at least 3 different broad categories."""
    ...

def test_select_quiz_topics_max_15() -> None:
    """ordered_topics never exceeds 15 entries."""
    ...

# --- build_options ---

def test_build_options_no_candidate_slug_in_text(tmp_path: Path) -> None:
    """Option text_pt and text_en must NOT contain any candidate_slug value."""
    ...

def test_build_options_filters_low_confidence() -> None:
    """Positions with confidence='low' are excluded from quiz options."""
    ...

# --- Integration ---

def test_quiz_output_conforms_to_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full main() output validates against docs/schemas/quiz.schema.json."""
    ...
```

**Data contract:** Output must conform to `quiz.schema.json`. Key constraints:
- `ordered_topics`: array of `TopicId` strings (max 15)
- `topics[*].divergence_score`: float 0.0-1.0
- `topics[*].options[*].candidate_slug`: NEVER exposed in `text_pt` or `text_en`
- `topics[*].options[*].confidence`: only `"high"` or `"medium"` (low filtered out)
- `topics[*].options[*].weight`: integer -2 to 2

### 3.5 `site/playwright.config.js` (CREATE)

```javascript
// @ts-check
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../qa/tests',
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:4173',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run preview',
    port: 4173,
    reuseExistingServer: true,
    cwd: '.',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
```

**Notes:**
- `testDir` points to `../qa/tests` (relative to `site/`)
- `webServer.command` starts `vite preview` which serves the built `dist/`
- The site MUST be built before running tests: `npm run build` in `site/`
- Port 4173 is Vite preview default

### 3.6 Playwright Test Files (CREATE — all in `qa/tests/`)

All test files follow this base pattern:

```javascript
// @ts-check
import { test, expect } from '@playwright/test';

// Tests use baseURL from playwright.config.js (http://localhost:4173)
```

#### 3.6.1 `qa/tests/test_home.spec.js`

```javascript
test.describe('Home page', () => {
  test('feed renders article cards', async ({ page }) => { ... });
  test('language toggle switches to English', async ({ page }) => { ... });
  test('countdown timer is visible', async ({ page }) => { ... });
  test('source filter buttons are present', async ({ page }) => { ... });
});
```

**Assertions:** At least one `[data-testid="article-card"]` or article element visible; language toggle changes `<html lang="">` attribute; countdown shows year 2026.

#### 3.6.2 `qa/tests/test_sentiment.spec.js`

```javascript
test.describe('Sentiment Dashboard', () => {
  test('heatmap grid renders', async ({ page }) => { ... });
  test('toggle between Por Tema and Por Fonte', async ({ page }) => { ... });
  test('methodology badge is present', async ({ page }) => { ... });
});
```

**Route:** `/sentimento` (check App.jsx for exact route)

#### 3.6.3 `qa/tests/test_polls.spec.js`

```javascript
test.describe('Polls page', () => {
  test('chart renders', async ({ page }) => { ... });
  test('institute filter is present', async ({ page }) => { ... });
  test('methodology badge is present', async ({ page }) => { ... });
});
```

**Route:** `/pesquisas`

#### 3.6.4 `qa/tests/test_quiz.spec.js`

```javascript
test.describe('Quiz full flow', () => {
  test('complete quiz and see result', async ({ page }) => {
    // Navigate to /quiz
    // For each question: click an option, click next
    // Assert result page shows affinity percentages
    // Assert share button is present
    ...
  });
});
```

**Route:** `/quiz` then `/quiz/resultado`

#### 3.6.5 `qa/tests/test_quiz_neutrality.spec.js`

```javascript
import { CandidateSlug } from '../../docs/schemas/types.ts'; // reference only

const CANDIDATE_SLUGS = [
  'lula', 'flavio-bolsonaro', 'tarcisio', 'caiado', 'zema',
  'ratinho-jr', 'eduardo-leite', 'aldo-rebelo', 'renan-santos',
];

test.describe('Quiz neutrality', () => {
  test('no candidate slug visible during questions', async ({ page }) => {
    // Navigate to /quiz
    // For each visible question page:
    //   Get page text content
    //   Assert none of CANDIDATE_SLUGS appears in text
    //   Assert no source_pt or source_en text visible
    ...
  });
});
```

**Critical rule:** `candidate_slug`, `source_pt`, `source_en` MUST NOT appear in any DOM text during the question phase. Only visible after result.

#### 3.6.6 `qa/tests/test_candidate.spec.js`

```javascript
test.describe('Candidate page', () => {
  test('/candidato/lula renders profile', async ({ page }) => { ... });
  test('JSON-LD structured data present', async ({ page }) => {
    // Check for <script type="application/ld+json">
    ...
  });
  test('methodology badge is present', async ({ page }) => { ... });
});
```

**Route:** `/candidato/lula`

#### 3.6.7 `qa/tests/test_comparison.spec.js`

```javascript
test.describe('Comparison page', () => {
  test('/comparar/lula-vs-tarcisio renders both candidates', async ({ page }) => { ... });
  test('comparison data table is present', async ({ page }) => { ... });
});
```

**Route:** `/comparar/lula-vs-tarcisio`

#### 3.6.8 `qa/tests/test_methodology.spec.js`

```javascript
test.describe('Methodology page', () => {
  test('all 5 sections present', async ({ page }) => {
    // Check for: data collection, AI processing, sentiment, quiz, transparency
    ...
  });
  test('language toggle works', async ({ page }) => { ... });
});
```

**Route:** `/metodologia`

#### 3.6.9 `qa/tests/test_rss.spec.js`

```javascript
test.describe('RSS feeds', () => {
  test('feed.xml is valid XML', async ({ page, request }) => {
    const resp = await request.get('/feed.xml');
    // Assert 200, content-type includes xml, body parses as XML
    ...
  });
  test('feed-en.xml is valid XML', async ({ page, request }) => { ... });
});
```

#### 3.6.10 `qa/tests/test_mobile.spec.js`

```javascript
test.describe('Mobile layout (390px)', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('BottomNav is visible', async ({ page }) => { ... });
  test('desktop Nav is hidden', async ({ page }) => { ... });
  test('quiz is immersive (no nav)', async ({ page }) => { ... });
});
```

### 3.7 `site/package.json` (MODIFY)

Add to `devDependencies`:
```json
"@playwright/test": "^1.50.0"
```

Add to `scripts`:
```json
"test:e2e": "npx playwright test"
```

### 3.8 `README.md` (MODIFY — full overhaul)

Final structure with sections:

```markdown
# Portal Eleicoes BR 2026

<!-- Badges -->
[![Collect](https://github.com/{owner}/{repo}/actions/workflows/collect.yml/badge.svg)]()
[![Deploy](https://github.com/{owner}/{repo}/actions/workflows/deploy.yml/badge.svg)]()
[![Watchdog](https://github.com/{owner}/{repo}/actions/workflows/watchdog.yml/badge.svg)]()

> Live: https://{github-pages-url}

## What is this? / O que e isto?
(2-paragraph bilingual description)

## Screenshot
(Full-page screenshot of live homepage — light mode)

## Architecture
(Mermaid or ASCII flowchart as specified in arch spec)

## Running Locally
(npm install && npm run dev; pip install -r requirements.txt && python scripts/collect_rss.py)

## Required GitHub Secrets
| Secret | Used by | Description |
|--------|---------|-------------|
| NVIDIA_API_KEY | collect.yml | NVIDIA NIM API |
| OPENROUTER_API_KEY | collect.yml | OpenRouter API |
| ... | ... | ... |

## Pre-candidates (March 2026)
(Table of 9 candidates with party and status)

## Architecture Decision Records
- [ADR-000: Wireframes](docs/adr/000-wireframes.md)
- [ADR-001: Hosting](docs/adr/001-hosting.md)
- ... through ADR-006

## Contributing
Open a GitHub issue.

## License
MIT
```

### 3.9 `CHANGELOG.md` (MODIFY)

Must follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format. Add entries for all missing phases. Current state has entries for Phases 0-5 only. Required additions:

```markdown
## [1.0.0] - 2026-03-11

### Added
- Phase 16: QA final — full test suite, security/SEO/a11y/code review, final documentation

## [Unreleased]
(move existing content if needed)

### Added - Phase 15: Mobile Polish
...
### Added - Phase 14: ...
### Added - Phase 13: ...
### Added - Phase 12: ...
### Added - Phase 11: ...
### Added - Phase 10: ...
### Added - Phase 09: ...
### Added - Phase 08: ...
### Added - Phase 07: ...
### Added - Phase 06: ...
```

Each phase entry must include a summary of what was added/changed. The implementor must inspect git log to extract the correct descriptions for each phase.

---

## 4. Data Contract Notes

### 4.1 Python Tests — Schema Compliance

| Test File | Schema(s) Consumed | Key Validations |
|-----------|-------------------|-----------------|
| `test_build_data.py` | `articles.schema.json` | Required fields: `id`, `url`, `title`, `source`, `published_at`, `collected_at`, `status`. `id = sha256(url)[:16]`. Max 500 articles. |
| `test_curate.py` | None (tests timing logic only) | `.curate_last_run` contains epoch float |
| `test_watchdog.py` | None (no formal schema) | Output must have: `checked_at` (ISO 8601), `workflows` (object), `status` (string) |
| `test_extract_quiz_positions.py` | `quiz.schema.json` | `ordered_topics` max 15. `options[*].weight` in {-2,-1,0,1,2}. `confidence` in {"high","medium"}. No `candidate_slug` in option text. |

### 4.2 Playwright Tests — Data Expectations

All Playwright tests run against the **built static site** (`dist/`). The site reads `data/*.json` files. For tests to work:

- `data/articles.json` must exist and have at least 1 article with `status: "validated"` or `"curated"`
- `data/sentiment.json` must exist with `by_topic` and `by_source` populated
- `data/quiz.json` must exist with at least 1 topic and options
- `data/polls.json` must exist with at least 1 poll
- `data/candidates.json` must exist with the 9 candidates

If any data files are empty stubs, the Playwright tests must handle the empty/loading state gracefully (test for either data presence OR proper empty-state UI).

### 4.3 QA Reports — No Schema

The 4 QA report files (`qa/phase-16-*.md`) are free-form Markdown generated by skills. They do not need to conform to any JSON schema but must contain:
- **Security report:** findings table (Risk, Location, Severity, Status)
- **SEO report:** checklist of items audited with pass/fail
- **Code review:** findings with severity (HIGH/MEDIUM/LOW)
- **Accessibility report:** WCAG AA compliance checklist

### 4.4 README.md — No Schema

Free-form Markdown. Must include all 11 sections listed in arch spec Section 6.

### 4.5 CHANGELOG.md — Format

Must follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with categories: Added, Changed, Fixed, Removed.

---

## 5. Step-by-Step Implementation Order

### Step 1: Inspect project state and verify baseline

**Dependencies:** None
**Actions:**
1. Run `python -m pytest scripts/ -v --tb=short` to see which existing tests pass
2. Run `cd site && npm run build` to verify the site builds
3. Check `data/*.json` files have content

**Verification:** Note any pre-existing failures. These are NOT the implementor's responsibility to fix (unless related to Phase 16 deliverables).

### Step 2: Write Python unit tests

**Dependencies:** Step 1 (baseline known)
**Actions:**
1. Create `scripts/test_build_data.py` with signatures from Section 3.1
2. Create `scripts/test_curate.py` with signatures from Section 3.2
3. Create `scripts/test_watchdog.py` with signatures from Section 3.3
4. Create `scripts/test_extract_quiz_positions.py` with signatures from Section 3.4

**Key constraints:**
- All tests must use `tmp_path` and `monkeypatch` for isolation — never write to real `data/` directory
- Mock AI calls in `test_extract_quiz_positions.py` — do not make real API requests
- `test_build_data.py` must create articles with `sha256(url)[:16]` IDs
- `test_curate.py` must mock time, not sleep

**Verification:** `python -m pytest scripts/ -v --tb=short` — all new tests pass

### Step 3: Run and fix Python tests (RALPH loop)

**Dependencies:** Step 2
**Actions:**
1. Run `python -m pytest scripts/ -v --tb=short`
2. If failures: fix test code (not production code unless bug found)
3. Repeat up to 3 times per the RALPH protocol

**Verification:** Zero test failures in `scripts/test_*.py`

### Step 4: Set up Playwright

**Dependencies:** Step 1 (site builds)
**Actions:**
1. `cd site && npm install --save-dev @playwright/test`
2. Add `"test:e2e": "npx playwright test"` to `site/package.json` scripts
3. Create `site/playwright.config.js` per Section 3.5
4. Run `cd site && npx playwright install chromium` to download browser
5. Create `qa/tests/` directory

**Verification:** `cd site && npx playwright test --list` returns no errors (may show 0 tests)

### Step 5: Write Playwright integration tests

**Dependencies:** Step 4
**Actions:**
1. Create all 10 test files in `qa/tests/` per Section 3.6
2. Each test must navigate to the correct route, wait for content, and assert
3. `test_quiz_neutrality.spec.js` must check ALL 9 candidate slugs are absent from question DOM text
4. `test_mobile.spec.js` must use `{ viewport: { width: 390, height: 844 } }`
5. `test_rss.spec.js` must use Playwright `request` API, not `page.goto`

**Key constraints:**
- Tests run against the built `dist/` via `vite preview` (port 4173)
- Do NOT use `page.waitForTimeout()` — use `page.waitForSelector()` or `expect(...).toBeVisible()`
- Handle data-dependent assertions gracefully (if data file is empty, check for empty-state UI)

**Verification:** `cd site && npm run build && npx playwright test` — all 10 spec files pass

### Step 6: Run and fix Playwright tests (RALPH loop)

**Dependencies:** Steps 3, 5
**Actions:**
1. `cd site && npm run build && npx playwright test`
2. If failures: inspect error screenshots, fix test selectors or page behavior
3. If a test fails because a page component is broken, fix the component (this is a valid Phase 16 fix)
4. Repeat up to 3 times per RALPH protocol

**Verification:** Zero Playwright test failures

### Step 7: Run security review

**Dependencies:** Step 6 (all code stable)
**Actions:**
1. Invoke `security-threat-modeler` skill targeting:
   - `.github/workflows/*.yml` — no hardcoded secrets
   - `scripts/collect_parties.py` — BeautifulSoup sanitization
   - `scripts/summarize.py` — AI prompt injection risk
   - `site/src/pages/CaseStudyPage.jsx` — Markdown HTML rendering
   - All `<a target="_blank">` — `rel="noopener noreferrer"`
   - `data/*.json` — no PII
2. Save output to `qa/phase-16-security-report.md`
3. Fix all HIGH/CRITICAL findings immediately

**Verification:** `qa/phase-16-security-report.md` exists; no unresolved CRITICAL findings

### Step 8: Run SEO audit

**Dependencies:** Step 6
**Actions:**
1. Invoke `seo-audit` skill on the built site (use `vite preview` or inspect `dist/` files)
2. Check: unique `<title>` per page, `<meta description>`, JSON-LD, sitemap.xml, robots.txt, OG tags
3. Save output to `qa/phase-16-seo-report.md`
4. Fix any missing meta tags or broken structured data

**Verification:** `qa/phase-16-seo-report.md` exists; all pages have unique titles and descriptions

### Step 9: Run code review

**Dependencies:** Step 6
**Actions:**
1. Invoke `tech-lead-reviewer` skill covering all code
2. Key areas: pipeline idempotency, error handling, prop validation, dead code, race conditions, `narrative_cluster_id`
3. Save output to `qa/phase-16-code-review.md`
4. Fix all HIGH severity findings

**Verification:** `qa/phase-16-code-review.md` exists; all HIGH findings resolved

### Step 10: Run accessibility audit

**Dependencies:** Step 6
**Actions:**
1. Invoke `web-design-guidelines` skill on all page routes
2. Check: alt text, color contrast >= 4.5:1, focus indicators, button labels, nav aria-labels, BottomNav aria-labels, heatmap cell aria-labels
3. Save output to `qa/phase-16-accessibility-report.md`
4. Fix contrast or aria-label issues found

**Verification:** `qa/phase-16-accessibility-report.md` exists; WCAG AA color contrast compliant

### Step 11: Fix all HIGH/CRITICAL findings

**Dependencies:** Steps 7-10
**Actions:**
1. Collect all HIGH/CRITICAL findings from the 4 QA reports
2. Fix each one — may involve editing React components, Python scripts, or workflows
3. Re-run affected tests to confirm fixes don't break anything
4. Document MEDIUM findings fixed; LOW findings may remain as known issues

**Verification:** Re-run `python -m pytest scripts/ -v --tb=short && cd site && npm run build && npx playwright test`

### Step 12: Update README.md

**Dependencies:** Step 11 (all code finalized)
**Actions:**
1. Overhaul `README.md` per Section 3.8
2. Use actual GitHub repo owner/name for badge URLs
3. Add architecture diagram (ASCII or Mermaid) matching the pipeline flow
4. List all 9 candidates with current status
5. Link all 7 ADRs (000-006)
6. Include accurate setup instructions
7. Add secrets table with all required GitHub secrets

**Verification:** `README.md` has all 11 sections from arch spec

### Step 13: Update CHANGELOG.md

**Dependencies:** Step 11
**Actions:**
1. Inspect git log to extract descriptions for Phases 06-16
2. Add entries in Keep a Changelog format for each missing phase
3. Add `[1.0.0] - 2026-03-11` release entry at the top
4. Ensure every phase (01-16) has an entry

**Verification:** `CHANGELOG.md` has entries for all 16 phases and a `[1.0.0]` release

### Step 14: Final case study update

**Dependencies:** Step 11
**Actions:**
1. Invoke `docs-maintainer` skill to do final pass on `docs/case-study/pt-BR.md` and `docs/case-study/en-US.md`
2. Incorporate all lessons learned, final architecture decisions, and phase outcomes
3. Ensure bilingual consistency

**Verification:** Both case study files updated with Phase 16 content

### Step 15: Final build verification

**Dependencies:** Steps 12-14
**Actions:**
1. `cd site && npm run build` — must succeed with zero errors
2. `python -m pytest scripts/ -v --tb=short` — all tests pass
3. `cd site && npx playwright test` — all tests pass
4. Verify all 4 QA reports exist in `qa/`
5. Verify `README.md` and `CHANGELOG.md` are complete

**Verification:** All acceptance criteria from arch spec satisfied

---

## 6. Test and Verification Commands (PowerShell 7)

```powershell
# 1. Python unit tests
python -m pytest scripts/ -v --tb=short

# 2. Build static site
Push-Location site; npm run build; Pop-Location

# 3. Playwright E2E tests (requires build first)
Push-Location site; npx playwright test; Pop-Location

# 4. Verify QA reports exist
@(
  'qa/phase-16-security-report.md',
  'qa/phase-16-seo-report.md',
  'qa/phase-16-code-review.md',
  'qa/phase-16-accessibility-report.md'
) | ForEach-Object {
  if (Test-Path $_) { Write-Host "OK: $_" } else { Write-Error "MISSING: $_" }
}

# 5. Verify README has required sections
$readme = Get-Content README.md -Raw
@('Badge', 'Screenshot', 'What is this', 'Architecture', 'Running Locally',
  'Secrets', 'Pre-candidates', 'ADR', 'Contributing', 'License') |
  ForEach-Object {
    if ($readme -match $_) { Write-Host "OK: $_ section found" }
    else { Write-Warning "MISSING: $_ section in README.md" }
  }

# 6. Verify CHANGELOG has Phase 16 and 1.0.0 entry
$changelog = Get-Content CHANGELOG.md -Raw
if ($changelog -match '1\.0\.0') { Write-Host 'OK: 1.0.0 release entry' } else { Write-Error 'MISSING: 1.0.0 entry' }
if ($changelog -match 'Phase 16') { Write-Host 'OK: Phase 16 entry' } else { Write-Error 'MISSING: Phase 16 entry' }

# 7. Verify no CRITICAL findings unresolved in security report
if (Test-Path 'qa/phase-16-security-report.md') {
  $sec = Get-Content 'qa/phase-16-security-report.md' -Raw
  if ($sec -match 'CRITICAL.*unresolved|CRITICAL.*open') {
    Write-Error 'CRITICAL finding unresolved in security report'
  } else {
    Write-Host 'OK: No unresolved CRITICAL findings'
  }
}

# 8. Verify build produces dist/ with no errors
Push-Location site
if (Test-Path dist) { Write-Host 'OK: dist/ exists' } else { Write-Error 'MISSING: dist/' }
Pop-Location

# 9. JSON data files present
@('data/articles.json', 'data/sentiment.json', 'data/quiz.json',
  'data/polls.json', 'data/candidates.json') |
  ForEach-Object {
    if (Test-Path $_) {
      try { Get-Content $_ -Raw | ConvertFrom-Json | Out-Null; Write-Host "OK: $_ valid JSON" }
      catch { Write-Error "INVALID JSON: $_" }
    } else { Write-Warning "MISSING: $_" }
  }

# 10. Playwright installed
Push-Location site; npx playwright --version; Pop-Location
```

---

## 7. Git Commit Message

```
feat(phase-16): QA final — tests, security review, SEO audit, accessibility + final docs

Python unit tests:
- test_build_data.py: dedup, 500-limit, sort order, schema validation
- test_curate.py: 90-min skip logic
- test_watchdog.py: health JSON structure
- test_extract_quiz_positions.py: divergence scoring, topic selection

Playwright integration tests (10 spec files):
- Home feed, sentiment dashboard, polls chart, quiz full flow
- Quiz neutrality (no candidate slugs during questions)
- Candidate profile with JSON-LD, comparison page
- Methodology sections, RSS feed validation, mobile layout

QA reports:
- Security review (no hardcoded secrets, XSS mitigations)
- SEO audit (unique titles, meta descriptions, JSON-LD, sitemap)
- Code review (idempotency, error handling, dead code)
- Accessibility audit (WCAG AA contrast, aria-labels, focus)

Documentation:
- README.md: badges, architecture diagram, setup, secrets, ADRs
- CHANGELOG.md: entries for all 16 phases, 1.0.0 release
- Case study final pass (pt-BR + en-US)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## 8. Completion Sentinel

```powershell
New-Item -Path plans/phase-16-arch.DONE -ItemType File -Force
```

---

## 9. Acceptance Criteria Checklist

From `plans/phase-16-arch.md`:

- [ ] All Python unit tests pass: `python -m pytest scripts/ -v --tb=short`
- [ ] All Playwright tests pass against built site: `cd site && npx playwright test`
- [ ] `qa/phase-16-security-report.md` exists; no CRITICAL findings unresolved
- [ ] `qa/phase-16-seo-report.md` exists; all pages have unique titles and meta descriptions
- [ ] `qa/phase-16-code-review.md` exists; all HIGH findings fixed
- [ ] `qa/phase-16-accessibility-report.md` exists; color contrast WCAG AA compliant
- [ ] `README.md` has badges, screenshot, architecture diagram, and local setup instructions
- [ ] `CHANGELOG.md` has complete entries for all 16 phases with `[1.0.0]` release
- [ ] `npm run build` produces valid `dist/` with no console errors
- [ ] GitHub Pages site is live and all routes resolve without 404

---

## 10. Constraints Reminder

- All HIGH and CRITICAL findings from security/code review MUST be fixed before the push
- MEDIUM findings SHOULD be fixed; LOW findings MAY be documented as known issues in `qa/`
- Playwright tests run against the **built static site** (`dist/` via `vite preview`), NOT the dev server
- `README.md` must be accurate and useful to a developer who discovers the repo cold
- Do NOT add unnecessary dependencies beyond `@playwright/test`
- All Python tests must use `tmp_path`/`monkeypatch` for isolation — never modify real `data/` files
- All shell commands use PowerShell 7 syntax
- Invoke skills (`test-writer`, `security-threat-modeler`, `seo-audit`, `tech-lead-reviewer`, `web-design-guidelines`, `docs-maintainer`) — do not manually write QA reports
- The quiz NEVER exposes `candidate_slug` or `source_*` during the question phase
- `MethodologyBadge` must be present on all data-driven components
- `sentiment.json` must include `disclaimer_pt` and `disclaimer_en`

---

## 11. Skill Invocation Reference

The implementor must invoke these skills in the order specified in Step 7-10 and Step 14:

| Step | Skill | Target | Output |
|------|-------|--------|--------|
| 2-3 | `test-writer` | Python test files in `scripts/` | Test code + passing results |
| 5-6 | `test-writer` | Playwright test files in `qa/tests/` | Test code + passing results |
| 7 | `security-threat-modeler` | Workflows, scripts, components | `qa/phase-16-security-report.md` |
| 8 | `seo-audit` | Built site pages | `qa/phase-16-seo-report.md` |
| 9 | `tech-lead-reviewer` | All code changes since Phase 01 | `qa/phase-16-code-review.md` |
| 10 | `web-design-guidelines` | All page routes | `qa/phase-16-accessibility-report.md` |
| 14 | `docs-maintainer` | Case study files | Updated `docs/case-study/*.md` |
