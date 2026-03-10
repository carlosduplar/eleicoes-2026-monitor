# Phase 09 - Task 01 Spec (RSS Feed Generation)

## Inputs and mandatory references

- Architecture input: `plans/phase-09-arch.md`
- Agent protocol: `docs/agent-protocol.md` (Tatico must provide detailed implementation spec plus edge-case tests)
- Project conventions: `.github/copilot-instructions.md`
- Contracts: `docs/schemas/articles.schema.json`, `docs/schemas/types.ts`
- Prompt spec: `docs/prompt-eleicoes2026-v5.md` lines 562-604

## 1) Files to create or modify (exact relative paths)

1. `scripts/generate_rss_feed.py` (modify existing stub)
2. `scripts/test_generate_rss_feed.py` (create)
3. `site/public/feed.xml` (generated output, not hand-edited)
4. `site/public/feed-en.xml` (generated output, not hand-edited)
5. `site/index.html` (verify only -- RSS autodiscovery `<link>` tags already present)
6. `.github/workflows/collect.yml` (modify -- remove soft-failure guard on RSS step)

No new dependencies are introduced. All imports come from Python stdlib.

## 2) Function signatures and types per file

### `scripts/generate_rss_feed.py`

```python
from __future__ import annotations

import json
from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

# --- Constants ---

SITE_URL: str  # "https://eleicoes2026.com.br"
ARTICLES_PATH: Path  # Path("data/articles.json")
OUTPUT_DIR: Path  # Path("site/public")
FEED_PT_FILENAME: str  # "feed.xml"
FEED_EN_FILENAME: str  # "feed-en.xml"
MAX_ITEMS: int  # 50
ATOM_NS: str  # "http://www.w3.org/2005/Atom"
VALID_STATUSES: frozenset[str]  # frozenset({"validated", "curated"})

# --- Channel metadata per language ---

ChannelMeta = dict[str, str]
# Keys: title, link, description, language, feed_filename

CHANNEL_PT: ChannelMeta
# {
#   "title": "Eleicoes BR 2026",
#   "link": SITE_URL,
#   "description": "Monitoramento em tempo real das eleicoes presidenciais brasileiras de 2026.",
#   "language": "pt-BR",
#   "feed_filename": FEED_PT_FILENAME,
# }

CHANNEL_EN: ChannelMeta
# {
#   "title": "Brazil Elections 2026",
#   "link": SITE_URL,
#   "description": "Real-time monitoring of the 2026 Brazilian presidential elections.",
#   "language": "en-US",
#   "feed_filename": FEED_EN_FILENAME,
# }

# --- Types (aligned with docs/schemas/types.ts Article interface) ---

from typing import Any, TypedDict, NotRequired

class ArticleSummaries(TypedDict, total=False):
    """Mirrors Article.summaries from docs/schemas/types.ts."""
    pt_BR: str  # JSON key "pt-BR"
    en_US: str  # JSON key "en-US"

class ArticleDict(TypedDict):
    """Subset of Article fields consumed by RSS generation."""
    id: str
    url: str
    title: str
    published_at: str
    status: str  # "raw" | "validated" | "curated"
    candidates_mentioned: NotRequired[list[str]]
    summaries: NotRequired[dict[str, str]]

# --- Functions ---

def load_articles(path: Path) -> list[dict[str, Any]]:
    """Read and parse data/articles.json. Return raw list of article dicts.
    Handles both bare array and $schema-wrapped shapes."""
    ...

def filter_and_sort(articles: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    """Keep only validated/curated articles, sort by published_at descending, truncate to max_items."""
    ...

def format_pub_date(iso_date: str) -> str:
    """Convert ISO 8601 date string to RFC 2822 format using email.utils.formatdate.
    Example: '2026-03-05T10:00:00Z' -> 'Thu, 05 Mar 2026 10:00:00 GMT'"""
    ...

def get_summary(article: dict[str, Any], lang_key: str) -> str:
    """Return summaries[lang_key] if present and non-empty; fallback to article['title']."""
    ...

def build_feed_xml(articles: list[dict[str, Any]], channel: ChannelMeta) -> ElementTree:
    """Build an RSS 2.0 ElementTree for the given channel language.

    Structure:
      <rss version="2.0" xmlns:atom="...">
        <channel>
          <title>...</title>
          <link>...</link>
          <description>...</description>
          <language>...</language>
          <atom:link href="SITE_URL/feed_filename" rel="self" type="application/rss+xml"/>
          <item> (one per article)
            <title>...</title>
            <link>article.url</link>
            <description>summary for language</description>
            <pubDate>RFC 2822</pubDate>
            <guid>article.id</guid>
            <category> (one per candidate_mentioned)</category>
          </item>
        </channel>
      </rss>

    Language-specific behavior:
      - pt-BR channel: description = summaries["pt-BR"] or article.title
      - en-US channel: description = summaries["en-US"] or article.title
    """
    ...

def write_feed(tree: ElementTree, output_path: Path) -> None:
    """Write XML to file with xml_declaration=True, encoding='unicode'.
    Creates parent directories if needed."""
    ...

def main() -> None:
    """Entry point:
    1. Load articles from ARTICLES_PATH
    2. Filter and sort
    3. Build pt-BR feed -> write to OUTPUT_DIR/FEED_PT_FILENAME
    4. Build en-US feed -> write to OUTPUT_DIR/FEED_EN_FILENAME
    5. Print summary: 'Generated feed.xml (N items) and feed-en.xml (N items)'
    """
    ...

if __name__ == "__main__":
    main()
```

Required behavior notes:
- Use only Python stdlib: `xml.etree.ElementTree`, `email.utils`, `datetime`, `json`, `pathlib`.
- The atom namespace must be registered with `ElementTree.register_namespace("atom", ATOM_NS)` before building the tree, so the output uses `atom:link` prefix (not `ns0:link`).
- `encoding="unicode"` in `ElementTree.write()` produces a `str`, which must be written to file as text (not bytes). Include `xml_declaration=True`.
- The `<guid>` element should have `isPermaLink="false"` since the article `id` is a hash, not a URL.
- Script must be idempotent: running twice with the same input produces byte-identical output.
- All paths are relative to the repo root (the script is invoked as `python scripts/generate_rss_feed.py` from repo root).

### `scripts/test_generate_rss_feed.py`

```python
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

# --- Fixtures ---

@pytest.fixture
def sample_articles() -> list[dict]:
    """Return a list of test articles with mixed statuses (raw, validated, curated)
    and both present/absent summaries."""
    ...

@pytest.fixture
def articles_file(tmp_path: Path, sample_articles: list[dict]) -> Path:
    """Write sample_articles to a temp articles.json and return its path."""
    ...

@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Return a temp directory for feed output."""
    ...

# --- Tests ---

def test_feed_xml_is_valid_rss(articles_file: Path, output_dir: Path) -> None:
    """Output parses as valid XML with <rss> root element and version='2.0'.
    Both feed.xml and feed-en.xml must have this structure."""
    ...

def test_feed_limited_to_50_items(tmp_path: Path, output_dir: Path) -> None:
    """Generate 60 validated articles. Both feeds must contain exactly 50 <item> elements."""
    ...

def test_feed_pt_uses_pt_summaries(articles_file: Path, output_dir: Path) -> None:
    """<description> in feed.xml uses summaries['pt-BR'] when present."""
    ...

def test_feed_en_uses_en_summaries(articles_file: Path, output_dir: Path) -> None:
    """<description> in feed-en.xml uses summaries['en-US'] when present."""
    ...

def test_feed_skips_raw_articles(articles_file: Path, output_dir: Path) -> None:
    """Articles with status='raw' must not appear as <item> elements."""
    ...

def test_feed_pubdate_is_rfc2822(articles_file: Path, output_dir: Path) -> None:
    """<pubDate> elements must parse as valid RFC 2822 dates.
    Use email.utils.parsedate_to_datetime to verify."""
    ...

def test_idempotent_double_run(articles_file: Path, output_dir: Path) -> None:
    """Running generation twice produces byte-identical feed.xml and feed-en.xml."""
    ...
```

Test implementation notes:
- Each test must monkeypatch `generate_rss_feed.ARTICLES_PATH` and `generate_rss_feed.OUTPUT_DIR` to use temp paths.
- The `sample_articles` fixture must include at least: 2 validated articles with summaries, 1 curated article with summaries, 2 raw articles, 1 validated article without summaries (to test fallback).
- For `test_feed_limited_to_50_items`, generate 60 articles programmatically with unique IDs and `status: "validated"`.
- XML parsing in tests: use `ET.parse()` or `ET.fromstring()` and XPath queries.
- Namespace-aware XPath: use `{"atom": "http://www.w3.org/2005/Atom"}` namespace map.

### `site/index.html`

No changes needed. The file already contains both RSS autodiscovery `<link>` tags:

```html
<link rel="alternate" type="application/rss+xml" title="Portal Eleicoes BR 2026 RSS (pt-BR)" href="/feed.xml" />
<link rel="alternate" type="application/rss+xml" title="Portal Eleicoes BR 2026 RSS (en-US)" href="/feed-en.xml" />
```

The implementor must verify these are present and leave them unchanged.

### `.github/workflows/collect.yml`

Modify the "AI processing" step to remove the soft-failure guard on the RSS line.

Current line:
```yaml
python scripts/generate_rss_feed.py || echo "rss feed failed, continuing"
```

Replace with:
```yaml
python scripts/generate_rss_feed.py
```

The "Commit data updates" step already handles `site/public/feed*.xml` correctly:
```yaml
git add site/public/feed*.xml 2>/dev/null || true
```
This is acceptable because the `2>/dev/null || true` handles the case where feed files don't exist yet (first run). No changes needed to the commit step.

## 3) Data contract notes (schema fields each file must satisfy)

Primary schema: `docs/schemas/articles.schema.json`
TypeScript types: `docs/schemas/types.ts` (interface `Article`)

### Fields consumed by `scripts/generate_rss_feed.py`

From each article object in `data/articles.json`:

| Field | Schema type | Required | RSS usage |
|-------|------------|----------|-----------|
| `id` | `string` pattern `^[a-f0-9]{16}$` | Yes | `<guid isPermaLink="false">` |
| `url` | `string` format `uri` | Yes | `<link>` |
| `title` | `string` minLength 1 | Yes | `<title>`, fallback `<description>` |
| `published_at` | `string` format `date-time` | Yes | `<pubDate>` (converted to RFC 2822) |
| `status` | `string` enum `raw\|validated\|curated` | Yes | Filter: only `validated` and `curated` |
| `candidates_mentioned` | `array` of `string` | No | `<category>` (one per candidate) |
| `summaries` | `object` with `pt-BR`, `en-US` keys | No | `<description>` (language-specific) |

### Schema shape of `data/articles.json`

The file may be either:
- A bare JSON array: `[ {...}, {...} ]`
- A wrapped object with `$schema` key: `{ "$schema": "...", ...articles_array... }`

The script must handle both. In practice, the current file uses the `$schema` key at top level as metadata, so `load_articles()` should check if the parsed JSON is a `list` or a `dict`. If it's a dict, extract the array from the appropriate key (inspect the actual file structure).

### RSS 2.0 output contract

Both `feed.xml` and `feed-en.xml` must conform to:
- Root element: `<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">`
- Single `<channel>` child with required subelements: `<title>`, `<link>`, `<description>`, `<language>`
- `<atom:link>` with `href`, `rel="self"`, `type="application/rss+xml"`
- Zero to 50 `<item>` elements, each with: `<title>`, `<link>`, `<description>`, `<pubDate>`, `<guid>`
- Optional `<category>` elements per item (one per candidate mentioned)

## 4) Step-by-step implementation order (dependency-aware)

1. **Read references**: architecture spec (`plans/phase-09-arch.md`), articles schema, types, and the existing `data/articles.json` structure.

2. **Inspect `data/articles.json` shape**: Determine whether it's a bare array or wrapped object, so `load_articles()` handles it correctly. (Currently it's an array with a `$schema` key as a field of each object, not a top-level wrapper.)

3. **Implement `scripts/generate_rss_feed.py`** -- replace stub:
   - a. Constants and channel metadata dicts.
   - b. `load_articles()` -- read JSON, handle shape variants.
   - c. `filter_and_sort()` -- filter by status, sort by `published_at` desc, slice to 50.
   - d. `format_pub_date()` -- ISO 8601 to RFC 2822 using `email.utils.formatdate`.
   - e. `get_summary()` -- language-aware summary with title fallback.
   - f. `build_feed_xml()` -- construct ElementTree with RSS 2.0 structure, atom namespace.
   - g. `write_feed()` -- ensure directory, write XML with declaration.
   - h. `main()` -- orchestrate, print summary.

4. **Create `site/public/` directory** if it does not exist (the script handles this via `output_path.parent.mkdir(parents=True, exist_ok=True)`).

5. **Run the script** to generate `site/public/feed.xml` and `site/public/feed-en.xml`:
   ```powershell
   python scripts/generate_rss_feed.py
   ```

6. **Write `scripts/test_generate_rss_feed.py`**:
   - a. Create fixtures: `sample_articles`, `articles_file`, `output_dir`.
   - b. Implement all 7 test functions per the architecture spec.
   - c. Each test monkeypatches paths to use temp directories.

7. **Run tests**:
   ```powershell
   python -m pytest scripts/test_generate_rss_feed.py -v
   ```

8. **Verify `site/index.html`** already has autodiscovery `<link>` tags. No modification needed.

9. **Modify `.github/workflows/collect.yml`**: remove `|| echo "rss feed failed, continuing"` from the RSS line in the "AI processing" step.

10. **Verify idempotency**: run the script twice and compare outputs.

11. **Verify `npm run build`** succeeds (feed files copied to `dist/` as static assets):
    ```powershell
    Push-Location site; npm run build; Pop-Location
    ```

12. **Create sentinel**: `New-Item -Path plans/phase-09-arch.DONE -ItemType File -Force`

13. **Commit** with message from section 6.

## 5) Exact PowerShell 7 commands to run tests and verify correctness

Run from repository root (`C:\projects\eleicoes-2026-monitor`):

```powershell
# 1. Run unit tests
python -m pytest scripts/test_generate_rss_feed.py -v

# 2. Generate feeds from real data
python scripts/generate_rss_feed.py

# 3. Verify feed files were created
if (-not (Test-Path -Path site/public/feed.xml)) { throw "site/public/feed.xml was not created." }
if (-not (Test-Path -Path site/public/feed-en.xml)) { throw "site/public/feed-en.xml was not created." }

# 4. Verify feeds are valid XML with RSS 2.0 root
python -c "
from xml.etree import ElementTree as ET
for f in ['site/public/feed.xml', 'site/public/feed-en.xml']:
    tree = ET.parse(f)
    root = tree.getroot()
    assert root.tag == 'rss', f'{f}: root is {root.tag}, expected rss'
    assert root.get('version') == '2.0', f'{f}: version is {root.get(\"version\")}, expected 2.0'
    items = root.findall('.//item')
    print(f'{f}: valid RSS 2.0 with {len(items)} items')
    assert len(items) <= 50, f'{f}: {len(items)} items exceeds 50 limit'
"

# 5. Verify no raw articles leaked into feeds
python -c "
import json
from xml.etree import ElementTree as ET
articles = json.loads(open('data/articles.json', encoding='utf-8').read())
if isinstance(articles, dict):
    articles = [v for v in articles.values() if isinstance(v, list)][0] if any(isinstance(v, list) for v in articles.values()) else articles
raw_ids = {a['id'] for a in articles if a.get('status') == 'raw'}
for f in ['site/public/feed.xml', 'site/public/feed-en.xml']:
    tree = ET.parse(f)
    guids = {g.text for g in tree.findall('.//item/guid')}
    leaked = guids & raw_ids
    assert not leaked, f'{f} contains raw articles: {leaked}'
print('No raw articles in feeds.')
"

# 6. Verify idempotency
$ptBefore = Get-Content -Path site/public/feed.xml -Raw
$enBefore = Get-Content -Path site/public/feed-en.xml -Raw
python scripts/generate_rss_feed.py
$ptAfter = Get-Content -Path site/public/feed.xml -Raw
$enAfter = Get-Content -Path site/public/feed-en.xml -Raw
if ($ptBefore -ne $ptAfter) { throw "feed.xml changed on second run (not idempotent)." }
if ($enBefore -ne $enAfter) { throw "feed-en.xml changed on second run (not idempotent)." }
Write-Host "Idempotency verified."

# 7. Verify site/index.html has RSS autodiscovery links
$html = Get-Content -Path site/index.html -Raw
if ($html -notmatch 'type="application/rss\+xml".*href="/feed\.xml"') { throw "Missing pt-BR RSS link in index.html" }
if ($html -notmatch 'type="application/rss\+xml".*href="/feed-en\.xml"') { throw "Missing en-US RSS link in index.html" }
Write-Host "RSS autodiscovery links verified in index.html."

# 8. Verify collect.yml no longer has soft-failure guard on RSS
$yml = Get-Content -Path .github/workflows/collect.yml -Raw
if ($yml -match 'generate_rss_feed\.py.*\|\|') { throw "collect.yml still has soft-failure guard on RSS step." }
Write-Host "collect.yml RSS step verified (no soft-failure guard)."

# 9. Verify npm build succeeds (static assets copied)
Push-Location site
npm run build
Pop-Location
```

## 6) Git commit message to use (Conventional Commits + trailer)

```text
feat(phase-09): RSS feeds -- feed.xml and feed-en.xml with autodiscovery

- Generate pt-BR and en-US RSS 2.0 feeds from validated/curated articles
- Limit to 50 most recent items, sorted by published_at descending
- Remove soft-failure guard from collect.yml RSS step
- Add comprehensive unit tests for feed generation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

## 7) Exact PowerShell command to create architecture completion sentinel

```powershell
New-Item -Path plans/phase-09-arch.DONE -ItemType File -Force
```

## Edge-case test scenarios (required by Tatico responsibilities)

1. **Empty articles file**: `data/articles.json` is `[]` or contains only `raw` articles. Both feeds must be generated with zero `<item>` elements and a valid `<channel>` structure.

2. **Missing summaries field**: Article has `status: "validated"` but no `summaries` key at all. `<description>` must fall back to `article["title"]`.

3. **Empty summary string**: Article has `summaries: {"pt-BR": "", "en-US": "Analysis pending"}`. Feed pt-BR `<description>` must fall back to `article["title"]`; feed en-US uses the non-empty summary.

4. **More than 50 eligible articles**: Only the 50 most recent (by `published_at`) appear in the feed.

5. **Mixed statuses**: Articles with `status: "raw"` must never appear. Articles with `status: "validated"` and `status: "curated"` both appear.

6. **pubDate edge cases**: Articles with `published_at` containing timezone offset (`+00:00`) or UTC suffix (`Z`) must both produce valid RFC 2822 dates.

7. **Idempotency**: Running the script twice with identical input produces byte-identical XML output. No timestamps or random data in the feed structure itself.

8. **Missing `candidates_mentioned`**: Article without `candidates_mentioned` key produces no `<category>` elements (not an error).

9. **articles.json shape variants**: The load function must handle both a bare JSON array and an object with a `$schema` metadata key at the article level (current format).

10. **`site/public/` directory absent**: Script creates the directory tree before writing. Must not crash on first run.

11. **Unicode in titles/summaries**: Article titles and summaries containing Portuguese characters (accents, cedilla) must be preserved correctly in the XML output.
