# Phase 08 - Task 01 Spec (Polling Tracker)

## Inputs and mandatory references

- Architecture input: `plans/phase-08-arch.md`
- Agent protocol: `docs/agent-protocol.md` (Tatico must provide detailed implementation spec plus edge-case tests)
- Project conventions: `.github/copilot-instructions.md`
- Wireframe: `docs/wireframes/WF-04-poll-tracker.html`
- Contracts: `docs/schemas/polls.schema.json`, `docs/schemas/types.ts`

## 1) Files to create or modify (exact relative paths)

1. `scripts/collect_polls.py` (modify existing stub)
2. `scripts/test_collect_polls.py` (create)
3. `data/polls.json` (create if missing; otherwise update)
4. `site/src/components/PollTracker.jsx` (create)
5. `site/src/pages/PollsPage.jsx` (modify existing placeholder page)
6. `site/src/locales/pt-BR/common.json` (modify)
7. `site/src/locales/en-US/common.json` (modify)

No route-file changes are required because `/pesquisas` is already wired in `site/src/App.jsx`.

## 2) Function signatures and types per file

### `scripts/collect_polls.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from playwright.async_api import Browser, Page

PollType = Literal["estimulada", "espontanea"]

class PollSource(TypedDict):
    name: str
    url: str
    active: bool

class PollResultItem(TypedDict):
    candidate_slug: str
    candidate_name: str
    percentage: float
    variation: NotRequired[float | None]

class PollItem(TypedDict):
    id: str
    institute: str
    published_at: str
    collected_at: str
    type: PollType
    results: list[PollResultItem]
    sample_size: NotRequired[int]
    margin_of_error: NotRequired[float]
    confidence_level: NotRequired[float]
    tse_registration: NotRequired[str | None]
    source_url: NotRequired[str]
    raw_html_snippet: NotRequired[str]

@dataclass
class PollsDocument:
    payload: list[PollItem] | dict[str, Any]
    polls: list[PollItem]
    uses_wrapped_shape: bool

def utc_now_iso() -> str: ...
def build_poll_id(institute: str, date_yyyy_mm_dd: str) -> str: ...
def load_active_poll_sources() -> list[PollSource]: ...
def load_polls_document() -> PollsDocument: ...
def save_polls_document(document: PollsDocument) -> None: ...
def parse_poll_date(raw_text: str) -> str | None: ...
def parse_sample_size(raw_text: str) -> int | None: ...
def parse_margin_of_error(raw_text: str) -> float | None: ...
def infer_poll_type(raw_text: str) -> PollType: ...
def normalize_institute_name(name: str) -> str: ...
def canonical_candidate_slug(raw_name: str) -> str | None: ...
def deduplicate_by_id(existing: list[PollItem], incoming: list[PollItem]) -> tuple[list[PollItem], int]: ...
def append_pipeline_error(*, institute: str, source_url: str, message: str) -> None: ...
async def extract_candidates_from_jsonld(page: Page) -> list[PollResultItem]: ...
async def extract_candidates_from_tables(page: Page) -> list[PollResultItem]: ...
async def extract_poll_payload(page: Page, source: PollSource) -> PollItem | None: ...
async def scrape_source(browser: Browser, source: PollSource, timeout_ms: int = 30000) -> PollItem | None: ...
async def collect_polls_async() -> tuple[int, int, int]: ...
def collect_polls() -> tuple[int, int, int]: ...
def main() -> None: ...
```

Required behavior notes:
- Use `playwright.async_api` only (`async_playwright`, headless Chromium, `timeout=30000`).
- Per-source failure must be isolated with `try/except`, logged to `data/pipeline_errors.json`, and processing must continue.
- Poll ID rule must be exact: `sha256(f"{institute}_{date}".encode()).hexdigest()[:16]`.

### `scripts/test_collect_polls.py`

```python
from pathlib import Path
from typing import Any

import pytest

@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]: ...

def test_poll_id_is_sha256_prefix() -> None: ...
def test_dedup_skips_existing_polls(isolated_workspace: dict[str, Path]) -> None: ...
def test_idempotent_double_run(isolated_workspace: dict[str, Path]) -> None: ...
def test_institute_failure_does_not_crash(isolated_workspace: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None: ...
def test_polls_schema_valid(isolated_workspace: dict[str, Path]) -> None: ...
```

### `data/polls.json`

No functions.

Accepted persisted shapes (implementation must support both):

```json
[
  {
    "id": "a1b2c3d4e5f60789",
    "institute": "Datafolha",
    "published_at": "2026-03-01T00:00:00Z",
    "collected_at": "2026-03-05T10:30:00Z",
    "type": "estimulada",
    "results": []
  }
]
```

or wrapped compatibility mode:

```json
{
  "$schema": "../docs/schemas/polls.schema.json",
  "polls": [],
  "last_updated": "2026-03-05T10:30:00Z",
  "total_count": 0
}
```

### `site/src/components/PollTracker.jsx`

Use JS with JSDoc types aligned with `docs/schemas/types.ts`.

```js
/**
 * @typedef {'pt-BR' | 'en-US'} AppLocale
 * @typedef {{
 *   candidate_slug: string,
 *   candidate_name: string,
 *   percentage: number,
 *   variation?: number | null
 * }} PollResult
 * @typedef {{
 *   id: string,
 *   institute: string,
 *   published_at: string,
 *   collected_at: string,
 *   type: 'estimulada' | 'espontanea',
 *   sample_size?: number,
 *   margin_of_error?: number,
 *   confidence_level?: number,
 *   tse_registration?: string | null,
 *   source_url?: string,
 *   results: PollResult[]
 * }} Poll
 * @typedef {{ dateLabel: string, dateIso: string } & Record<string, string | number>} PollChartRow
 */

function normalizePollPayload(payload) { /* Poll[] */ }
function getInstituteOptions(polls) { /* string[] */ }
function formatDateLabel(publishedAt, locale) { /* string */ }
function buildCandidateSeries(polls) { /* Array<{ slug: string, label: string, color: string }> */ }
function buildChartRows(polls, selectedInstitute, locale) { /* PollChartRow[] */ }
function PollTracker() { /* JSX.Element */ }

export default PollTracker;
```

### `site/src/pages/PollsPage.jsx`

```jsx
function PollsPage() { /* JSX.Element */ }

export default PollsPage;
```

Must include:
- `<Helmet>` title for polls page.
- JSON-LD `Dataset` script.
- `<PollTracker />` as primary page content.

### `site/src/locales/pt-BR/common.json`

No functions. Add:

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

### `site/src/locales/en-US/common.json`

No functions. Add English equivalents for all `polls.*` keys listed above.

## 3) Data contract notes (schema fields each file must satisfy)

Primary schema: `docs/schemas/polls.schema.json`

- Top-level: `type: array`
- Poll object: `definitions.Poll`
- Result object: `definitions.PollResult`

Required poll fields (`definitions.Poll.required`):
- `id` (must match `^[a-f0-9]{16}$`)
- `institute` (enum: `Datafolha`, `Quaest`, `AtlasIntel`, `Parana Pesquisas`, `PoderData`, `Real Time Big Data`)
- `published_at` (ISO date-time)
- `collected_at` (ISO date-time)
- `type` (`estimulada` or `espontanea`)
- `results` (array)

Required result fields (`definitions.PollResult.required`):
- `candidate_slug` (string)
- `candidate_name` (string)
- `percentage` (number `0..100`)

Per-file contract mapping:
- `scripts/collect_polls.py`: emits schema-valid poll/result items, enforces institute enum normalization, preserves percentage bounds.
- `scripts/test_collect_polls.py`: validates output against schema and asserts dedup/idempotency invariants.
- `data/polls.json`: stores only schema-valid poll items (direct array or wrapped `polls` list compatibility mode).
- `site/src/components/PollTracker.jsx`: consumes only schema fields (`institute`, `published_at`, `results[].candidate_slug`, `results[].candidate_name`, `results[].percentage`) and handles optional poll fields safely.
- `site/src/pages/PollsPage.jsx`: renders poll dataset metadata only; no mutation of data contract.
- `site/src/locales/pt-BR/common.json` and `site/src/locales/en-US/common.json`: no schema binding, but all poll UI strings must come from i18n keys (no hardcoded JSX text).

## 4) Step-by-step implementation order (dependency-aware)

1. Read references: architecture spec, wireframe WF-04, schema/types, and existing `useData` + `MethodologyBadge` behavior.
2. Implement typed foundation in `scripts/collect_polls.py` (TypedDicts, file paths, load/save helpers).
3. Implement source loading from `data/sources.json` (`polls[]` active entries only).
4. Implement parsing/normalization helpers (date, sample, margin, poll type, candidate slug, institute enum compatibility).
5. Implement async scraping (`playwright.async_api`) with timeout and per-source error isolation + error logging.
6. Implement extraction fallback chain (JSON-LD first, then table/text candidate extraction).
7. Implement dedup + persistence to `data/polls.json`, preserving idempotency and updating wrapped metadata when applicable.
8. Write `scripts/test_collect_polls.py` with all required tests (ID rule, dedup, idempotency, failure isolation, schema validity).
9. Create `site/src/components/PollTracker.jsx` with `useData('polls')`, loading/empty/error states, institute filter, Recharts lines, and `MethodologyBadge`.
10. Update `site/src/pages/PollsPage.jsx` to render `PollTracker` and page-level Helmet metadata (title + Dataset JSON-LD).
11. Add `polls.*` keys in both locale files.
12. Execute verification commands from section 5 and fix any failing implementation details.
13. Create `plans/phase-08-arch.DONE`.
14. Commit with message from section 6.

## 5) Exact PowerShell 7 commands to run tests and verify correctness

Run from repository root (`C:\projects\eleicoes-2026-monitor`):

```powershell
python -m pytest scripts/test_collect_polls.py -v

python scripts/collect_polls.py

if (-not (Test-Path -Path data/polls.json)) { throw "data/polls.json was not created." }

$before = Get-Content -Path data/polls.json -Raw
python scripts/collect_polls.py
$after = Get-Content -Path data/polls.json -Raw
if ($before -ne $after) { throw "collect_polls.py is not idempotent: data/polls.json changed on second run." }

python -c "import json,pathlib; from jsonschema import Draft7Validator; root=pathlib.Path('.'); schema=json.loads((root/'docs'/'schemas'/'polls.schema.json').read_text(encoding='utf-8')); payload=json.loads((root/'data'/'polls.json').read_text(encoding='utf-8')); polls = payload if isinstance(payload, list) else payload.get('polls', []); validator=Draft7Validator(schema['definitions']['Poll']); errors=[(idx, err.message) for idx,item in enumerate(polls) for err in validator.iter_errors(item)]; print(f'polls={len(polls)} errors={len(errors)}'); assert not errors, errors[:5]"

Push-Location site
npm run build
Pop-Location
```

## 6) Git commit message to use (Conventional Commits + trailer)

```text
feat(phase-08): implement polling tracker scraper and dashboard

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## 7) Exact PowerShell command to create architecture completion sentinel

```powershell
New-Item -Path plans/phase-08-arch.DONE -ItemType File -Force
```

## Edge-case test scenarios (required by Tatico responsibilities)

1. `data/polls.json` absent initially -> script creates it without crashing.
2. Duplicate institute/date pair -> same deterministic ID, no duplicate append.
3. One institute fails (timeout/parser) -> error logged to `data/pipeline_errors.json`, other institutes still processed.
4. Candidate-name variants from HTML tables still resolve to canonical slugs.
5. Optional poll fields omitted by source remain schema-valid and UI-safe.
6. Empty polls payload renders localized empty state in `PollTracker`.
7. Data-fetch failure renders localized error state in `PollTracker`.
8. Locale switch changes labels and date formatting (`DD/MM` in `pt-BR`, `MM/DD` in `en-US`).
9. Institute filter "Todas/All" aggregates all data; single institute filters series correctly.
