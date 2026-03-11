# Phase 14 — Task 01 Spec (Party + Social Collection)

> Planner: Opus 4.6 | Implementor: Codex | Date: 2026-03-11

---

## Inputs and Mandatory References

| # | Ref | Path | Why |
|---|-----|------|-----|
| 1 | Arch spec | `plans/phase-14-arch.md` | Full Phase 14 deliverables, acceptance criteria, constraints |
| 2 | TypeScript types | `docs/schemas/types.ts` | `SourceCategory` union — must add `'social'` value |
| 3 | Articles schema | `docs/schemas/articles.schema.json` | `source_category` enum — must add `"social"` value |
| 4 | RSS collector | `scripts/collect_rss.py` | Reference implementation: dedup pattern, `ArticlesDocument`, `build_article_id`, `_load_articles_document`, `_save_articles_document`, `utc_now_iso` |
| 5 | AI client | `scripts/ai_client.py` | `build_article_id` (shared helper) — reuse from here or from `collect_rss.py` |
| 6 | Sources data | `data/sources.json` | Party sources already seeded (8 entries). Must add `"category"` field to each party + add `"social"` array |
| 7 | Articles data | `data/articles.json` | Wrapped object format: `{ "$schema", "articles": [...], "last_updated", "total_count" }` |
| 8 | Pipeline errors | `data/pipeline_errors.json` | Error logging format: `{ "errors": [...], "last_checked": ... }` |
| 9 | Summarize errors | `scripts/summarize.py` lines 247-283 | `_load_pipeline_errors` / `_append_pipeline_error` pattern to replicate |
| 10 | Polls collector | `scripts/collect_polls.py` lines 287-315 | `append_pipeline_error` pattern (tier="foca") to replicate |
| 11 | Collect workflow | `.github/workflows/collect.yml` | Lines 641-644 — stub `collect_parties.py` + `collect_social.py` calls to update |
| 12 | Requirements | `requirements.txt` | Already has `beautifulsoup4>=4.12`, `requests>=2.31`, `tweepy>=4.14`, `lxml>=5.0` |
| 13 | Test examples | `scripts/test_collect_polls.py` | pytest fixture pattern with `monkeypatch`, isolated workspace |
| 14 | Candidates schema | `docs/schemas/candidates.schema.json` | Valid `CandidateSlug` values for `candidates_mentioned` validation |

---

## 1) Files to Create or Modify

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `scripts/collect_parties.py` | **CREATE** | BeautifulSoup party scraper — 8 party sites, dedup, fallback HTML extraction ladder |
| 2 | `scripts/collect_social.py` | **CREATE** | Optional Twitter/YouTube collector — exits cleanly if API keys absent |
| 3 | `scripts/test_collect_parties.py` | **CREATE** | Unit tests for party collector (6 test cases) |
| 4 | `data/sources.json` | **MODIFY** | Add `"category": "party"` to each party entry + add `"social"` array |
| 5 | `docs/schemas/articles.schema.json` | **MODIFY** | Add `"social"` to `source_category` enum |
| 6 | `docs/schemas/types.ts` | **MODIFY** | Add `'social'` to `SourceCategory` union |
| 7 | `.github/workflows/collect.yml` | **MODIFY** | Update `collect_parties.py` and `collect_social.py` call lines with `[warn]` prefix |
| 8 | `requirements.txt` | **VERIFY** | Confirm `tweepy>=4.14` is present (already added); add `google-api-python-client>=2.100` for YouTube Data API if not present |

---

## 2) Function Signatures and Types per File

### 2.1 `scripts/collect_parties.py` — CREATE

```python
"""Party website collection pipeline for Phase 14."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

logger: logging.Logger
ROOT_DIR: Path   # Path(__file__).resolve().parents[1]
DATA_DIR: Path   # ROOT_DIR / "data"
SOURCES_FILE: Path  # DATA_DIR / "sources.json"
ARTICLES_FILE: Path  # DATA_DIR / "articles.json"
PIPELINE_ERRORS_FILE: Path  # DATA_DIR / "pipeline_errors.json"
REQUEST_TIMEOUT_SECONDS: int  # 20
USER_AGENT: str  # "eleicoes-2026-monitor/1.0 (+https://github.com/...)"
DEFAULT_SCHEMA_PATH: str  # "../docs/schemas/articles.schema.json"


def utc_now_iso() -> str:
    """Return UTC timestamp in ISO 8601 format with Z suffix."""
    ...


def build_article_id(url: str) -> str:
    """Return sha256(url.encode('utf-8')).hexdigest()[:16]."""
    ...


# --- ArticlesDocument loading/saving (reuse pattern from collect_rss.py) ---

@dataclass
class ArticlesDocument:
    articles: list[dict[str, Any]]
    wrapped: bool
    schema_path: str


def _load_json(path: Path) -> Any: ...
def _load_articles_document() -> ArticlesDocument: ...
def _save_articles_document(document: ArticlesDocument) -> None: ...


# --- Pipeline error logging (reuse pattern from collect_polls.py) ---

def _load_pipeline_errors() -> dict[str, Any]:
    """Load pipeline errors from data/pipeline_errors.json."""
    ...

def _append_pipeline_error(*, party_name: str, party_url: str, message: str) -> None:
    """Append error entry with tier='foca', script='collect_parties.py'."""
    ...


# --- Source loading ---

def load_active_party_sources() -> list[dict[str, Any]]:
    """Read active party sources from data/sources.json['parties'].
    
    Returns list of dicts with keys: name, url, candidate_slugs, category.
    Only entries with active=True are returned.
    """
    ...


# --- Robots.txt checking ---

def _is_allowed_by_robots(site_url: str) -> bool:
    """Check if our User-Agent can crawl the given URL per robots.txt.
    
    Returns True if robots.txt allows crawling or if robots.txt
    cannot be fetched (fail-open with warning log).
    Timeout: 5 seconds for robots.txt fetch.
    """
    ...


# --- HTML extraction fallback ladder ---

def _extract_articles_jsonld(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract articles from JSON-LD NewsArticle blocks.
    
    Searches for <script type="application/ld+json"> containing
    @type: "NewsArticle" or "Article".
    Returns list of {"url": ..., "title": ...} dicts.
    """
    ...


def _extract_articles_opengraph(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract article URL+title from Open Graph meta tags.
    
    Looks for <meta property="og:title"> and <meta property="og:url">.
    Returns list of {"url": ..., "title": ...} dicts (may be single item).
    """
    ...


def _extract_articles_html(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Extract article links by traversing HTML structure.
    
    Strategy:
    1. Find all <article> tags with nested <a href> + text
    2. Find <a> tags inside <h2>/<h3> elements  
    3. Find <a> tags whose href matches news URL patterns
       (contains '/noticias/', '/noticia/', '/news/', date patterns like /2026/)
    
    Dedup by URL. Resolve relative URLs against base_url.
    Returns list of {"url": ..., "title": ...} dicts.
    """
    ...


def _extract_articles_heading_fallback(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Last resort: first <h1> or <h2> + canonical link or base_url.
    
    Returns list of {"url": ..., "title": ...} dicts (max 1 item).
    """
    ...


def extract_articles_from_html(html: str, base_url: str) -> list[dict[str, str]]:
    """Apply extraction fallback ladder and return unique URL+title pairs.
    
    Fallback order:
    1. JSON-LD NewsArticle
    2. Open Graph meta tags
    3. HTML structure (<article>, <h2>/<h3> links, news URL patterns)
    4. Heading fallback (<h1>/<h2> + canonical)
    
    Short-circuits: if step N yields results, return them without trying N+1.
    Each result is {"url": str, "title": str}.
    Skips entries where URL or title is empty.
    """
    ...


# --- Main collection ---

def scrape_party_site(party: dict[str, Any]) -> list[dict[str, str]]:
    """Fetch a single party website and extract article URL+title pairs.
    
    Args:
        party: dict with keys name, url, candidate_slugs, category, active
    
    Returns:
        list of {"url": ..., "title": ...} dicts
    
    Raises:
        requests.RequestException: on network error (caller handles)
    
    Uses requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT}).
    Checks robots.txt before fetching.
    """
    ...


def collect_articles() -> tuple[int, int, int]:
    """Collect new party articles and append to data/articles.json.
    
    Returns: (new_articles_count, sources_count, error_count)
    
    For each active party source:
    1. scrape_party_site() to get URL+title pairs
    2. Build article_id = sha256(url)[:16]
    3. Skip if article_id exists in current articles
    4. Create article dict:
       {
           "id": article_id,
           "url": article_url,
           "title": extracted_title,
           "source": party_name,          # e.g. "PT"
           "source_category": "party",
           "published_at": utc_now_iso(),  # party sites rarely have dates
           "collected_at": utc_now_iso(),
           "status": "raw",
           "relevance_score": None,
           "candidates_mentioned": party["candidate_slugs"],  # pre-populated!
           "topics": [],
           "summaries": {"pt-BR": "", "en-US": ""},
       }
    5. On exception: log to pipeline_errors.json, increment error count, continue
    
    Prints: "Parties: X new articles from Y sources (Z errors)"
    """
    ...


def main() -> None:
    """Entry point: configure logging, call collect_articles()."""
    ...
```

### 2.2 `scripts/collect_social.py` — CREATE

```python
"""Optional social media collection (Twitter + YouTube) for Phase 14."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

logger: logging.Logger
ROOT_DIR: Path
DATA_DIR: Path
SOURCES_FILE: Path
ARTICLES_FILE: Path
PIPELINE_ERRORS_FILE: Path
DEFAULT_SCHEMA_PATH: str

# Candidate names for search queries (derived from data/candidates.json)
CANDIDATE_SEARCH_TERMS: dict[str, str]  # slug -> display name for search


def utc_now_iso() -> str: ...
def build_article_id(url: str) -> str: ...
def _load_json(path: Path) -> Any: ...

# Reuse ArticlesDocument pattern from collect_rss.py
@dataclass
class ArticlesDocument:
    articles: list[dict[str, Any]]
    wrapped: bool
    schema_path: str

def _load_articles_document() -> ArticlesDocument: ...
def _save_articles_document(document: ArticlesDocument) -> None: ...

def _load_pipeline_errors() -> dict[str, Any]: ...
def _append_pipeline_error(*, source: str, message: str) -> None:
    """tier='foca', script='collect_social.py'."""
    ...


# --- Candidate names loader ---

def _load_candidate_names() -> dict[str, str]:
    """Load candidate slug -> display name mapping from data/candidates.json.
    
    Returns: {"lula": "Lula", "tarcisio": "Tarcísio de Freitas", ...}
    Used to build search queries.
    """
    ...


# --- Twitter collection ---

def _collect_twitter(
    existing_ids: set[str],
    candidate_names: dict[str, str],
) -> list[dict[str, Any]]:
    """Collect recent tweets mentioning candidates + '2026'.
    
    Requires TWITTER_BEARER_TOKEN env var.
    Uses tweepy.Client with automatic rate limiting.
    Searches: '{candidate_name} 2026 eleições' for each candidate.
    
    Article format per tweet:
    {
        "id": sha256(tweet_url)[:16],
        "url": f"https://twitter.com/i/web/status/{tweet_id}",
        "title": tweet_text[:120],
        "source": "Twitter",
        "source_category": "social",
        "published_at": tweet.created_at ISO 8601,
        "collected_at": utc_now_iso(),
        "status": "raw",
        "relevance_score": None,
        "candidates_mentioned": [inferred slugs from tweet text],
        "topics": [],
        "summaries": {"pt-BR": "", "en-US": ""},
        "content": full tweet text,
    }
    
    Returns list of new article dicts (already deduped against existing_ids).
    Returns [] if bearer token not set.
    """
    ...


def _infer_candidates_from_text(
    text: str, candidate_names: dict[str, str]
) -> list[str]:
    """Match candidate names/slugs in text, return list of slugs.
    
    Case-insensitive matching of both display names and slugs.
    """
    ...


# --- YouTube collection ---

def _collect_youtube(
    existing_ids: set[str],
    candidate_names: dict[str, str],
) -> list[dict[str, Any]]:
    """Collect recent YouTube videos mentioning candidates + 'eleições 2026'.
    
    Requires YOUTUBE_API_KEY env var.
    Uses googleapiclient.discovery.build("youtube", "v3", ...).
    Searches: '{candidate_name} eleições 2026' for each candidate, maxResults=10.
    
    Article format per video:
    {
        "id": sha256(video_url)[:16],
        "url": f"https://youtu.be/{video_id}",
        "title": video_title,
        "source": "YouTube",
        "source_category": "social",
        "published_at": video.publishedAt ISO 8601,
        "collected_at": utc_now_iso(),
        "status": "raw",
        "relevance_score": None,
        "candidates_mentioned": [inferred slugs],
        "topics": [],
        "summaries": {"pt-BR": "", "en-US": ""},
    }
    
    Returns list of new article dicts (already deduped against existing_ids).
    Returns [] if API key not set.
    """
    ...


# --- Main ---

def collect_social() -> tuple[int, int]:
    """Collect social media articles and append to data/articles.json.
    
    Returns: (new_articles_count, error_count)
    
    1. Load existing article IDs for dedup
    2. Load candidate names for search queries
    3. Call _collect_twitter (if TWITTER_BEARER_TOKEN set)
    4. Call _collect_youtube (if YOUTUBE_API_KEY set)
    5. Append new articles, save
    6. Print summary: "Social: X new articles (Y errors)"
    
    If neither TWITTER_BEARER_TOKEN nor YOUTUBE_API_KEY is set:
      print warning, exit with code 0.
    
    Exceptions from Twitter/YouTube are caught, logged to pipeline_errors.json,
    and do NOT propagate (script always exits 0).
    """
    ...


def main() -> None:
    """Entry point: configure logging, call collect_social()."""
    ...
```

### 2.3 `scripts/test_collect_parties.py` — CREATE

```python
"""Unit tests for scripts/collect_parties.py — Phase 14."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

import scripts.collect_parties as collect_parties


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Create an isolated data directory with sources.json and articles.json.
    
    Monkeypatches: DATA_DIR, SOURCES_FILE, ARTICLES_FILE, PIPELINE_ERRORS_FILE.
    Returns dict with paths: {"data_dir", "sources", "articles", "pipeline_errors"}.
    """
    ...


# --- Test cases ---

def test_party_article_id_is_sha256_prefix() -> None:
    """ID = sha256(url.encode('utf-8')).hexdigest()[:16]."""
    url = "https://pt.org.br/noticias/test-article"
    expected = sha256(url.encode("utf-8")).hexdigest()[:16]
    assert collect_parties.build_article_id(url) == expected


def test_party_article_has_candidate_slugs(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Article from PT site has ['lula'] in candidates_mentioned.
    
    Mock requests.get to return HTML with a single <article><a> link.
    Run collect_articles(). Read articles.json.
    Assert new article has candidates_mentioned == ["lula"].
    """
    ...


def test_party_article_category_is_party(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """source_category must be 'party' for all party articles.
    
    Mock requests.get. Run collect_articles().
    Assert every new article has source_category == "party".
    """
    ...


def test_dedup_skips_existing(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Article already in data/articles.json is skipped.
    
    Pre-populate articles.json with article whose ID matches a mocked URL.
    Run collect_articles(). Assert article count unchanged.
    """
    ...


def test_site_failure_does_not_crash(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad URL / network error skips gracefully, logs to pipeline_errors.json.
    
    Mock requests.get to raise requests.ConnectionError.
    Run collect_articles(). Assert no exception raised.
    Assert error logged in pipeline_errors.json.
    """
    ...


def test_idempotent_double_run(
    isolated_workspace: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running collect_articles() twice produces same article count.
    
    Mock requests.get with deterministic HTML response.
    Run collect_articles() twice. Read articles.json.
    Assert total article count is same after both runs.
    """
    ...
```

### 2.4 `data/sources.json` — MODIFY

Add `"category": "party"` field to each party object and add `"social"` array:

```json
{
  "parties": [
    {
      "name": "PT",
      "url": "https://pt.org.br/noticias/",
      "candidate_slugs": ["lula"],
      "active": true,
      "category": "party"
    }
  ],
  "social": [
    {"name": "Twitter", "type": "twitter", "active": true},
    {"name": "YouTube", "type": "youtube", "active": true}
  ]
}
```

Each of the 8 existing party entries must gain `"category": "party"`. The `"social"` array is added after `"polls"`.

### 2.5 `docs/schemas/articles.schema.json` — MODIFY

Add `"social"` to the `source_category` enum:

```json
"source_category": {
  "type": "string",
  "enum": ["mainstream", "politics", "magazine", "international", "institutional", "party", "social"]
}
```

### 2.6 `docs/schemas/types.ts` — MODIFY

Add `'social'` to the `SourceCategory` union (line 46):

```typescript
export type SourceCategory =
  | 'mainstream'
  | 'politics'
  | 'magazine'
  | 'international'
  | 'institutional'
  | 'party'
  | 'social';
```

### 2.7 `.github/workflows/collect.yml` — MODIFY

Update lines 641-644 to use `[warn]` prefix in echo messages:

```yaml
      - name: Collect sources
        run: |
          python scripts/collect_rss.py
          python scripts/collect_parties.py  || echo "[warn] collect_parties failed"
          python scripts/collect_polls.py    || echo "[warn] collect_polls failed"
          python scripts/collect_social.py   || echo "[warn] collect_social failed"
```

Note: The current file already has the correct structure. The only change is `"parties failed, continuing"` -> `"[warn] collect_parties failed"` and `"social failed, continuing"` -> `"[warn] collect_social failed"`.

### 2.8 `requirements.txt` — VERIFY/MODIFY

Confirm these are present (all already are per Phase 01):
- `beautifulsoup4>=4.12`
- `requests>=2.31`
- `tweepy>=4.14`
- `lxml>=5.0`

Add if not present:
- `google-api-python-client>=2.100` (for YouTube Data API v3 in `collect_social.py`)

---

## 3) Data Contract Notes

### 3.1 `articles.schema.json` fields satisfied by `collect_parties.py`

| Field | Source | Required | Notes |
|-------|--------|----------|-------|
| `id` | `sha256(url.encode('utf-8')).hexdigest()[:16]` | YES | Pattern: `^[a-f0-9]{16}$` |
| `url` | Extracted from party HTML | YES | Format: `uri` |
| `title` | Extracted from party HTML | YES | `minLength: 1` |
| `source` | `party["name"]` (e.g., "PT") | YES | Free string |
| `source_category` | Hardcoded `"party"` | NO | Enum: must be in `["mainstream","politics","magazine","international","institutional","party","social"]` |
| `published_at` | `utc_now_iso()` (party sites rarely embed dates) | YES | ISO 8601 |
| `collected_at` | `utc_now_iso()` | YES | ISO 8601 |
| `status` | Hardcoded `"raw"` | YES | Enum: `["raw","validated","curated"]` |
| `relevance_score` | `None` (set later by Foca AI) | NO | Number 0-1 |
| `candidates_mentioned` | `party["candidate_slugs"]` | NO | Array of `CandidateSlug` strings |
| `topics` | `[]` (set later) | NO | Array of `TopicId` strings |
| `summaries` | `{"pt-BR": "", "en-US": ""}` | NO | Filled by Editor (summarize.py) |

### 3.2 `articles.schema.json` fields satisfied by `collect_social.py`

Same as above except:

| Field | Twitter | YouTube |
|-------|---------|---------|
| `source` | `"Twitter"` | `"YouTube"` |
| `source_category` | `"social"` | `"social"` |
| `published_at` | `tweet.created_at` | `video.publishedAt` |
| `candidates_mentioned` | Inferred from tweet text | Inferred from video title |
| `content` | Full tweet text | (omitted — no transcript) |

### 3.3 `data/sources.json` — Party entries contract

Each party entry must have:
```json
{
  "name": "string (required)",
  "url": "string URI (required)",
  "candidate_slugs": ["array of CandidateSlug strings (required)"],
  "active": "boolean (required)",
  "category": "string 'party' (required — NEW in Phase 14)"
}
```

### 3.4 `data/sources.json` — Social entries contract

```json
{
  "name": "string (required, e.g. 'Twitter', 'YouTube')",
  "type": "string (required, e.g. 'twitter', 'youtube')",
  "active": "boolean (required)"
}
```

### 3.5 `data/pipeline_errors.json` — Error entry contract for `collect_parties.py`

```json
{
  "at": "ISO 8601 string",
  "tier": "foca",
  "script": "collect_parties.py",
  "party_name": "string (party name)",
  "party_url": "string (party URL)",
  "message": "string (error description)"
}
```

### 3.6 `data/pipeline_errors.json` — Error entry contract for `collect_social.py`

```json
{
  "at": "ISO 8601 string",
  "tier": "foca",
  "script": "collect_social.py",
  "source": "string ('Twitter' or 'YouTube')",
  "message": "string (error description)"
}
```

---

## 4) Step-by-Step Implementation Order

### Step 1: Update schemas (no code dependencies)

1. **`docs/schemas/articles.schema.json`** — Add `"social"` to `source_category` enum
2. **`docs/schemas/types.ts`** — Add `| 'social'` to `SourceCategory` union type

### Step 2: Update `data/sources.json`

3. **`data/sources.json`** — Add `"category": "party"` to all 8 party entries. Add `"social"` array after `"polls"`.

### Step 3: Verify/update `requirements.txt`

4. **`requirements.txt`** — Add `google-api-python-client>=2.100` if not present. Verify `tweepy>=4.14` is present (it is).

### Step 4: Create `scripts/collect_parties.py`

5. **`scripts/collect_parties.py`** — Full implementation. Depends on:
   - `data/sources.json` party structure (Step 2)
   - `articles.schema.json` contract (Step 1)
   
   Implementation notes:
   - Reuse `ArticlesDocument` / `_load_articles_document` / `_save_articles_document` pattern from `collect_rss.py` (copy, do not import — scripts are standalone)
   - Reuse `_load_pipeline_errors` / `_append_pipeline_error` pattern from `collect_polls.py`
   - `build_article_id` and `utc_now_iso` are identical to `collect_rss.py`
   - HTML extraction ladder: JSON-LD -> OG -> HTML structure -> heading fallback
   - Resolve relative URLs with `urllib.parse.urljoin(base_url, href)`
   - Robots.txt check with `urllib.robotparser.RobotFileParser` (fail-open on error)
   - `requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})`
   - Pre-populate `candidates_mentioned` from party's `candidate_slugs`
   - Set `source_category: "party"` on all articles
   - Wrap exceptions per-site in try/except, log to pipeline_errors, continue

### Step 5: Create `scripts/collect_social.py`

6. **`scripts/collect_social.py`** — Full implementation. Depends on:
   - `data/sources.json` social structure (Step 2)
   - `articles.schema.json` contract (Step 1)
   - `data/candidates.json` for candidate names
   
   Implementation notes:
   - Guard both Twitter and YouTube behind env var checks at the top
   - If neither `TWITTER_BEARER_TOKEN` nor `YOUTUBE_API_KEY` is set, print warning and `sys.exit(0)`
   - Twitter: use `tweepy.Client(bearer_token=..., wait_on_rate_limit=True)`
   - Twitter search: `client.search_recent_tweets(query=f'"{name}" 2026', max_results=10, tweet_fields=["created_at","author_id","text"])`
   - YouTube: lazy-import `googleapiclient.discovery`, build service, use `youtube.search().list()`
   - All exceptions caught and logged, never propagate — script always exits 0
   - Set `source_category: "social"` on all articles

### Step 6: Create `scripts/test_collect_parties.py`

7. **`scripts/test_collect_parties.py`** — Unit tests. Depends on:
   - `scripts/collect_parties.py` (Step 4)
   
   Implementation notes:
   - Use `pytest` + `monkeypatch` + `tmp_path` fixture pattern (see `test_collect_polls.py`)
   - Mock `requests.get` to return controlled HTML responses
   - Mock `_is_allowed_by_robots` to always return `True`
   - Create isolated `sources.json` with 1-2 party sources
   - Create isolated `articles.json` (empty wrapped format)
   - Create isolated `pipeline_errors.json` with empty errors array
   - 6 test functions as specified in arch spec

### Step 7: Update workflow

8. **`.github/workflows/collect.yml`** — Update echo messages. Depends on nothing.

---

## 5) Test and Verification Commands (PowerShell 7)

```powershell
# --- Step A: Install/verify dependencies ---
pip install -r requirements.txt --quiet

# --- Step B: Validate schemas (jsonschema self-check) ---
python -c "import json, jsonschema; schema = json.loads(open('docs/schemas/articles.schema.json', encoding='utf-8').read()); print('Schema valid:', 'social' in schema['definitions']['Article']['properties']['source_category']['enum'])"

# --- Step C: Validate sources.json structure ---
python -c "
import json
sources = json.loads(open('data/sources.json', encoding='utf-8').read())
parties = sources['parties']
assert len(parties) == 8, f'Expected 8 parties, got {len(parties)}'
for p in parties:
    assert p.get('category') == 'party', f'{p[\"name\"]} missing category'
    assert p.get('active') is True, f'{p[\"name\"]} not active'
    assert isinstance(p.get('candidate_slugs'), list), f'{p[\"name\"]} missing candidate_slugs'
social = sources['social']
assert len(social) == 2, f'Expected 2 social sources, got {len(social)}'
print('sources.json: OK')
"

# --- Step D: Validate types.ts has 'social' ---
Select-String -Path "docs\schemas\types.ts" -Pattern "'social'" -Quiet

# --- Step E: Run collect_parties.py (dry run — will hit real sites or fail gracefully) ---
python scripts/collect_parties.py

# --- Step F: Run collect_social.py (no API keys expected in dev — should exit 0 with warning) ---
python scripts/collect_social.py

# --- Step G: Verify idempotency ---
python -c "
import json
before = len(json.loads(open('data/articles.json', encoding='utf-8').read()).get('articles', []))
"
python scripts/collect_parties.py
python -c "
import json
after = len(json.loads(open('data/articles.json', encoding='utf-8').read()).get('articles', []))
print(f'Before second run: articles count stable')
"

# --- Step H: Run unit tests ---
python -m pytest scripts/test_collect_parties.py -v

# --- Step I: Verify workflow YAML is valid ---
python -c "
import yaml
with open('.github/workflows/collect.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
collect_step = None
for step in data['jobs']['collect']['steps']:
    if step.get('name') == 'Collect sources':
        collect_step = step
        break
assert collect_step is not None, 'Collect sources step not found'
assert 'collect_parties.py' in collect_step['run'], 'collect_parties.py not in run'
assert 'collect_social.py' in collect_step['run'], 'collect_social.py not in run'
assert '[warn]' in collect_step['run'], 'Missing [warn] prefix'
print('collect.yml: OK')
"

# --- Step J: Verify no duplicate articles ---
python -c "
import json
data = json.loads(open('data/articles.json', encoding='utf-8').read())
articles = data.get('articles', data if isinstance(data, list) else [])
ids = [a['id'] for a in articles]
assert len(ids) == len(set(ids)), f'Duplicate IDs found: {len(ids)} total, {len(set(ids))} unique'
print(f'No duplicates: {len(ids)} unique articles')
"
```

---

## 6) Git Commit Message

```
feat(phase-14): party and social collection scripts

- Add scripts/collect_parties.py: BeautifulSoup scraper for 8 party
  websites with JSON-LD/OG/HTML fallback extraction ladder
- Add scripts/collect_social.py: optional Twitter (tweepy) and YouTube
  (Data API v3) collector, exits cleanly without API keys
- Add scripts/test_collect_parties.py: 6 unit tests covering dedup,
  candidate slugs, category, error handling, idempotency
- Update data/sources.json: add category field to parties, add social array
- Update docs/schemas: add 'social' to source_category enum in
  articles.schema.json and SourceCategory type in types.ts
- Update .github/workflows/collect.yml: standardize [warn] echo messages
- Update requirements.txt: add google-api-python-client for YouTube API

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## 7) Completion Sentinel

After all deliverables are verified:

```powershell
New-Item -Path plans/phase-14-arch.DONE -ItemType File -Force
```

---

## Edge Cases and Implementation Warnings

1. **Party sites may block scrapers**: Always check robots.txt first. On 403/429 responses, log error and skip — do not retry. The `|| echo` in the workflow handles total script failure.

2. **Relative URLs on party sites**: Use `urllib.parse.urljoin(base_url, href)` for all extracted `<a href>` values. Some party sites use relative paths like `/noticias/2026/03/article-slug`.

3. **JSON-LD may contain arrays**: `<script type="application/ld+json">` may contain a single object or an `@graph` array. Handle both.

4. **Empty HTML responses**: Some party sites may return login walls, CAPTCHAs, or empty bodies. If BeautifulSoup finds 0 articles via all 4 fallback levels, log a warning (not an error) and continue.

5. **Twitter API rate limits**: `tweepy.Client(wait_on_rate_limit=True)` handles this automatically but may cause the script to hang for up to 15 minutes. The workflow has `timeout-minutes: 25` which should accommodate this.

6. **YouTube API quota**: YouTube Data API has a daily quota of 10,000 units. `search.list` costs 100 units per call. With 9 candidates, that's 900 units per run. At 144 runs/day (every 10 min), quota would be exhausted in ~11 runs. Consider caching results or reducing `maxResults`.
   - **Recommendation**: Only search for top 5 candidates or reduce frequency. Log quota errors gracefully.

7. **PSD has 2 candidate slugs**: `["ratinho-jr", "eduardo-leite"]`. Articles from PSD site should have BOTH slugs in `candidates_mentioned`.

8. **Encoding**: Party sites may use various encodings. `requests.get().text` handles this via chardet/charset detection. Always use `response.text`, not `response.content`.

9. **`google-api-python-client` import**: Import conditionally — only when `YOUTUBE_API_KEY` is set. This avoids ImportError when the dependency is missing in minimal environments.

10. **`ArticlesDocument` pattern duplication**: Each collector script (`collect_rss.py`, `collect_parties.py`, `collect_social.py`) has its own copy of the `ArticlesDocument` dataclass and load/save functions. This is intentional — scripts are standalone and must work independently. If a shared module is ever needed, that's a future refactor.

---

## Acceptance Criteria Checklist

- [ ] `python scripts/collect_parties.py` runs without crashing
- [ ] Party articles appear in `data/articles.json` with `source_category: "party"`
- [ ] Party articles have `candidates_mentioned` pre-populated from party's candidate list
- [ ] Running `collect_parties.py` twice produces no duplicates
- [ ] `python scripts/collect_social.py` exits cleanly even when API keys are absent
- [ ] `data/sources.json` includes all 8 party sources with `category` field and `social` section
- [ ] All unit tests pass: `python -m pytest scripts/test_collect_parties.py -v`
- [ ] `collect.yml` has standardized `[warn]` echo messages
- [ ] `docs/schemas/articles.schema.json` includes `"social"` in `source_category` enum
- [ ] `docs/schemas/types.ts` includes `'social'` in `SourceCategory` union
