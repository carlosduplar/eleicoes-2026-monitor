# Phase 12 — Task 01 Spec (SEO/GEO: Candidate Pages, Comparison Pages, Sitemap, robots.txt)

## Inputs and Mandatory References

| Ref | Path | Why |
|-----|------|-----|
| Arch spec | `plans/phase-12-arch.md` | Full deliverable list, acceptance criteria, constraints |
| WF-07 | `docs/wireframes/WF-07-candidate-profile-desktop.html` | CandidatePage layout |
| WF-08 | `docs/wireframes/WF-08-candidate-comparison.html` | ComparisonPage layout |
| TypeScript types | `docs/schemas/types.ts` | `Candidate`, `CandidateSlug`, `QuizTopic`, `QuizOption`, `Poll`, `Article`, `Sentiment` |
| Candidate colors | `site/src/utils/candidateColors.js` | `CANDIDATE_COLORS` map |
| MethodologyBadge | `site/src/components/MethodologyBadge.jsx` | Required in both new pages |
| useData hook | `site/src/hooks/useData.js` | Data fetching with memory cache |
| App router | `site/src/App.jsx` | Routes array, AppShell |
| SSG entry | `site/src/main.jsx` | `ViteReactSSG`, i18n init, namespace registration |
| Vite config | `site/vite.config.js` | `ssgOptions`, must add `includedRoutes` |
| package.json | `site/package.json` | `vite-react-ssg` is the SSG plugin |
| i18n pt-BR | `site/src/locales/pt-BR/common.json` | Existing namespace structure |
| i18n en-US | `site/src/locales/en-US/common.json` | Existing namespace structure |
| Existing placeholder | `site/src/pages/CandidatesPage.jsx` | Will be replaced by CandidatePage |
| data/articles.json | `data/articles.json` | Recent articles per candidate |
| data/sentiment.json | `data/sentiment.json` | Per-candidate sentiment summary |
| data/polls.json | `data/polls.json` | Latest poll snapshot per candidate |
| data/quiz.json | `data/quiz.json` | Topic positions per candidate (for ComparisonPage) |
| deploy workflow | `.github/workflows/deploy.yml` | Already calls `generate_seo_pages.py` (stub) |
| Prompt spec | `docs/prompt-eleicoes2026-v5.md` lines 644-705 | JSON-LD schemas, comparison pairs, robots.txt |
| PLAN.md | `PLAN.md` | Candidate list (9 candidates), design tokens |

---

## 1) Files to Create or Modify

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `data/candidates.json` | CREATE | Full profiles for all 9 candidates |
| 2 | `docs/schemas/candidates.schema.json` | CREATE | JSON Schema for candidates.json (was missing) |
| 3 | `scripts/generate_seo_pages.py` | MODIFY | Replace stub with full sitemap.xml generator |
| 4 | `site/public/robots.txt` | CREATE | AI crawler allowances |
| 5 | `site/public/_headers` | CREATE | Cloudflare cache directives |
| 6 | `site/src/pages/CandidatePage.jsx` | CREATE | Individual candidate profile page |
| 7 | `site/src/pages/ComparisonPage.jsx` | CREATE | Side-by-side candidate comparison page |
| 8 | `site/src/pages/CandidatesPage.jsx` | MODIFY | Replace placeholder with candidate list linking to individual profiles |
| 9 | `site/src/App.jsx` | MODIFY | Add routes for `/candidato/:slug` and `/comparar/:slugA-vs-:slugB` |
| 10 | `site/src/main.jsx` | MODIFY | Register `candidates` i18n namespace |
| 11 | `site/vite.config.js` | MODIFY | Add `includedRoutes` for SSG pre-rendering |
| 12 | `site/src/locales/pt-BR/candidates.json` | CREATE | Portuguese candidate/comparison strings |
| 13 | `site/src/locales/en-US/candidates.json` | CREATE | English candidate/comparison strings |
| 14 | `docs/adr/004-seo-geo-strategy.md` | CREATE | ADR documenting SEO/GEO decisions |
| 15 | `docs/schemas/types.ts` | MODIFY | Extend `Candidate` interface with new Phase 12 fields |

---

## 2) Function Signatures and Types per File

### 2.1 `docs/schemas/types.ts` — MODIFY

Add the fields required by Phase 12 to the existing `Candidate` interface (lines 158-167):

```typescript
export interface Candidate {
  slug: CandidateSlug;
  name: string;
  full_name: string;
  party: string;
  party_site: string;
  color: string; // hex
  twitter: string;
  status: 'pre-candidate' | 'speculated' | 'confirmed' | 'withdrawn';
  // --- Phase 12 additions ---
  bio_pt: string;
  bio_en: string;
  photo_url: string | null;
  tse_registration_url: string | null;
}

export interface CandidatesFile {
  candidates: Candidate[];
}
```

### 2.2 `docs/schemas/candidates.schema.json` — CREATE

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Candidates",
  "type": "object",
  "required": ["candidates"],
  "properties": {
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["slug", "name", "full_name", "party", "party_site", "color", "twitter", "status", "bio_pt", "bio_en", "photo_url", "tse_registration_url"],
        "properties": {
          "slug": { "type": "string", "enum": ["lula","flavio-bolsonaro","tarcisio","caiado","zema","ratinho-jr","eduardo-leite","aldo-rebelo","renan-santos"] },
          "name": { "type": "string" },
          "full_name": { "type": "string" },
          "party": { "type": "string" },
          "party_site": { "type": "string", "format": "uri" },
          "color": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
          "twitter": { "type": "string" },
          "status": { "type": "string", "enum": ["pre-candidate","speculated","confirmed","withdrawn"] },
          "bio_pt": { "type": "string" },
          "bio_en": { "type": "string" },
          "photo_url": { "type": ["string","null"] },
          "tse_registration_url": { "type": ["string","null"] }
        },
        "additionalProperties": false
      },
      "minItems": 9,
      "maxItems": 9
    }
  },
  "additionalProperties": false
}
```

### 2.3 `data/candidates.json` — CREATE

Must contain all 9 candidates from PLAN.md with these exact slugs, names, parties, colors, and statuses. Each entry must satisfy `docs/schemas/candidates.schema.json`.

Candidates (from PLAN.md):

| slug | name | full_name | party | color | status | twitter |
|------|------|-----------|-------|-------|--------|---------|
| lula | Lula | Luiz Inacio Lula da Silva | PT | #CC0000 | pre-candidate | LulaOficial |
| flavio-bolsonaro | Flavio Bolsonaro | Flavio Nantes Bolsonaro | PL | #002776 | pre-candidate | FlavioBolsonaro |
| tarcisio | Tarcisio de Freitas | Tarcisio Gomes de Freitas | Republicanos | #1A3A6B | speculated | taborelli_ |
| caiado | Ronaldo Caiado | Ronaldo Ramos Caiado | Uniao Brasil | #FF8200 | pre-candidate | ronaboracaiado |
| zema | Romeu Zema | Romeu Zema Neto | Novo | #FF6600 | pre-candidate | RomeuZema |
| ratinho-jr | Ratinho Jr | Carlos Roberto Massa Junior | PSD | #0066CC | speculated | rataborinhojr |
| eduardo-leite | Eduardo Leite | Eduardo Figueiredo Cavalheiro Leite | PSD | #4488CC | pre-candidate | EduardoLeite_ |
| aldo-rebelo | Aldo Rebelo | Jose Aldo Rebelo Figueiredo | DC | #5C6BC0 | pre-candidate | AldoRebelo |
| renan-santos | Renan Santos | Renan Franco Santos | Missao | #26A69A | pre-candidate | RenanSantos |

Party sites:
- PT: `https://pt.org.br`
- PL: `https://pl.org.br`
- Republicanos: `https://republicanos.org.br`
- Uniao Brasil: `https://uniaobrasil.org.br`
- Novo: `https://novo.org.br`
- PSD: `https://psd.org.br`
- DC: `https://dc.org.br`
- Missao: `https://missao.org.br`

All `photo_url` and `tse_registration_url` fields: `null`.

Bio strings: one-sentence bilingual descriptions indicating role, party, and candidacy status.

### 2.4 `scripts/generate_seo_pages.py` — MODIFY (replace stub)

```python
"""Generate sitemap.xml for all static and dynamic routes.

Reads data/candidates.json and writes site/public/sitemap.xml.
Idempotent: running twice produces identical output.
"""

from __future__ import annotations

import json
from datetime import date, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


BASE_URL: str = "https://eleicoes2026.com.br"

COMPARISON_PAIRS: list[tuple[str, str]] = [
    ("lula", "tarcisio"),
    ("lula", "caiado"),
    ("tarcisio", "caiado"),
    ("tarcisio", "ratinho-jr"),
    ("lula", "zema"),
    ("caiado", "ratinho-jr"),
    ("lula", "ratinho-jr"),
    ("tarcisio", "zema"),
]

STATIC_ROUTES: list[dict[str, str]] = [
    {"loc": "/", "priority": "1.0", "changefreq": "daily"},
    {"loc": "/sentimento", "priority": "0.8", "changefreq": "daily"},
    {"loc": "/pesquisas", "priority": "0.8", "changefreq": "daily"},
    {"loc": "/quiz", "priority": "0.9", "changefreq": "daily"},
    {"loc": "/metodologia", "priority": "0.7", "changefreq": "weekly"},
    {"loc": "/sobre/caso-de-uso", "priority": "0.6", "changefreq": "weekly"},
]


def load_candidates(data_dir: Path) -> list[dict]:
    """Load and return candidates list from data/candidates.json."""
    ...


def build_sitemap(candidates: list[dict], today: str) -> Element:
    """Build XML sitemap Element tree.

    Args:
        candidates: List of candidate dicts with 'slug' key.
        today: ISO date string for <lastmod>.

    Returns:
        Root <urlset> Element.
    """
    ...


def write_sitemap(root: Element, output_path: Path) -> int:
    """Write sitemap XML to file.

    Args:
        root: Root Element.
        output_path: Destination file path.

    Returns:
        Number of URLs written.
    """
    ...


def main() -> None:
    """Entry point. Reads candidates, generates sitemap, prints summary."""
    ...
```

**Implementation notes:**
- Namespace for sitemap: `http://www.sitemaps.org/schemas/sitemap/0.9`
- Each `<url>` has `<loc>`, `<lastmod>`, `<changefreq>`, `<priority>`
- Candidate routes: priority `0.9`, changefreq `daily`
- Comparison routes: priority `0.8`, changefreq `weekly`
- Output: `site/public/sitemap.xml`
- Print summary line: `"sitemap.xml: {count} URLs generated"`
- Use `xml.etree.ElementTree` (stdlib only, no extra deps)
- `today = date.today().isoformat()`
- Script must be idempotent

### 2.5 `site/public/robots.txt` — CREATE

Exact content as specified in `plans/phase-12-arch.md` section 3. Verbatim copy of the robots.txt block.

### 2.6 `site/public/_headers` — CREATE

Exact content as specified in `plans/phase-12-arch.md` section 4. Verbatim copy of the _headers block.

### 2.7 `site/src/pages/CandidatePage.jsx` — CREATE

```jsx
/**
 * CandidatePage — Individual candidate profile at /candidato/:slug
 *
 * Props: none (reads slug from useParams)
 * Data: useData('candidates'), useData('articles'), useData('sentiment'), useData('polls')
 * i18n: useTranslation('candidates')
 * Layout: follows WF-07 wireframe
 */

// Named export for lazy/SSG compatibility
export default function CandidatePage(): JSX.Element;
```

**Internal helpers (not exported):**

```jsx
function CandidateHero({ candidate }): JSX.Element;
// Renders: color banner, full_name, party, status badge

function CandidateBio({ candidate, lang }): JSX.Element;
// Renders: bio_pt or bio_en based on i18n.language

function CandidateSentiment({ slug, sentimentData }): JSX.Element;
// Renders: mini horizontal bar chart from sentiment.by_topic[slug]
// Uses Recharts BarChart

function CandidateArticles({ slug, articles }): JSX.Element;
// Renders: 5 most recent articles where candidates_mentioned includes slug
// Each article: title, source, published_at, link

function CandidatePollSnapshot({ slug, polls }): JSX.Element;
// Renders: latest poll percentage from most recent poll in polls array
// Find poll with most recent published_at, then find result matching slug

function CandidateTSELink({ candidate }): JSX.Element;
// Renders: TSE registration link (only if tse_registration_url !== null)
```

**JSON-LD block (in `<Helmet>`):**

```json
{
  "@context": "https://schema.org",
  "@type": ["Person", "ProfilePage"],
  "name": "{full_name}",
  "description": "{bio_pt or bio_en based on lang}",
  "affiliation": {"@type": "Organization", "name": "{party}"},
  "url": "https://eleicoes2026.com.br/candidato/{slug}"
}
```

**State handling:**
- Loading: show spinner with `t('candidates.loading')` (add this key)
- Empty/not-found: show message if slug not in candidates
- Error: show `t('candidates.error')` (add this key)
- Must include `<MethodologyBadge />`

### 2.8 `site/src/pages/ComparisonPage.jsx` — CREATE

```jsx
/**
 * ComparisonPage — Side-by-side comparison at /comparar/:pairSlug
 *
 * Props: none (reads pairSlug from useParams, parses "a-vs-b")
 * Data: useData('candidates'), useData('quiz')
 * i18n: useTranslation('candidates')
 * Layout: follows WF-08 wireframe
 */

export default function ComparisonPage(): JSX.Element;
```

**Internal helpers:**

```jsx
function parseComparisonSlugs(pairSlug: string): [string, string] | null;
// Split "lula-vs-tarcisio" on "-vs-" -> ["lula", "tarcisio"]
// Return null if invalid

function ComparisonHero({ candidateA, candidateB }): JSX.Element;
// Two panels side-by-side with candidate colors

function TopicComparisonTable({ candidateA, candidateB, quizData, lang }): JSX.Element;
// Rows: each topic from quiz.ordered_topics
// Columns: Topic Name | Candidate A stance | Candidate B stance
// Stance text from quiz.topics[topicId].options where candidate_slug matches

function TopicAccordion({ topic, candidateA, candidateB, options, lang }): JSX.Element;
// Expandable row: shows full position text + source for each candidate
```

**JSON-LD block (in `<Helmet>`):**

```json
{
  "@context": "https://schema.org",
  "@type": ["FAQPage", "Article"],
  "headline": "{Name A} vs {Name B}: comparacao de propostas 2026",
  "url": "https://eleicoes2026.com.br/comparar/{a}-vs-{b}"
}
```

**State handling:**
- Loading: spinner
- Invalid pair: "Comparacao nao encontrada" message
- Error: generic error state
- Must include `<MethodologyBadge />`

### 2.9 `site/src/pages/CandidatesPage.jsx` — MODIFY

Replace the Phase 12 placeholder with a candidate listing page that links to individual profiles:

```jsx
/**
 * CandidatesPage — Grid of all candidates at /candidatos
 *
 * Links to /candidato/:slug for each candidate.
 * Data: useData('candidates')
 * i18n: useTranslation('candidates')
 */

export default function CandidatesPage(): JSX.Element;
```

Renders a grid/list of candidate cards, each linking to `/candidato/{slug}`. Shows: name, party, color chip, status badge.

### 2.10 `site/src/App.jsx` — MODIFY

Add new imports and routes:

```jsx
// Add imports:
import CandidatePage from './pages/CandidatePage';
import ComparisonPage from './pages/ComparisonPage';

// Add to routes children array (after the existing 'candidatos' route):
{ path: 'candidato/:slug', element: <CandidatePage /> },
{ path: 'comparar/:pairSlug', element: <ComparisonPage /> },
```

Keep existing `candidatos` route as-is (it becomes the listing page).

### 2.11 `site/src/main.jsx` — MODIFY

Register the new `candidates` i18n namespace:

```jsx
// Add imports:
import ptCandidates from './locales/pt-BR/candidates.json';
import enCandidates from './locales/en-US/candidates.json';

// Modify i18n resources:
resources: {
  'pt-BR': { common: ptCommon, methodology: ptMethodology, candidates: ptCandidates },
  'en-US': { common: enCommon, methodology: enMethodology, candidates: enCandidates },
},

// Modify ns array:
ns: ['common', 'methodology', 'candidates'],
```

### 2.12 `site/vite.config.js` — MODIFY

Add `includedRoutes` callback to `ssgOptions` for SSG pre-rendering:

```javascript
ssgOptions: {
  script: 'defer',
  dirStyle: 'nested',
  formatting: 'none',
  includedRoutes: (paths) => {
    const candidateSlugs = [
      'lula', 'flavio-bolsonaro', 'tarcisio', 'caiado', 'zema',
      'ratinho-jr', 'eduardo-leite', 'aldo-rebelo', 'renan-santos',
    ];
    const comparisonPairs = [
      'lula-vs-tarcisio', 'lula-vs-caiado', 'tarcisio-vs-caiado',
      'tarcisio-vs-ratinho-jr', 'lula-vs-zema', 'caiado-vs-ratinho-jr',
      'lula-vs-ratinho-jr', 'tarcisio-vs-zema',
    ];
    return [
      ...paths,
      ...candidateSlugs.map((s) => `/candidato/${s}`),
      ...comparisonPairs.map((p) => `/comparar/${p}`),
    ];
  },
},
```

### 2.13 `site/src/locales/pt-BR/candidates.json` — CREATE

```json
{
  "title": "Candidatos",
  "loading": "Carregando dados do candidato...",
  "error": "Erro ao carregar dados do candidato.",
  "not_found": "Candidato nao encontrado.",
  "pre_candidate": "Pre-candidato",
  "speculated": "Cotado",
  "confirmed": "Confirmado",
  "withdrawn": "Desistente",
  "party_label": "Partido",
  "bio_label": "Perfil",
  "recent_news": "Noticias recentes",
  "latest_poll": "Ultima pesquisa",
  "poll_percentage": "{{percentage}}% na ultima pesquisa",
  "no_poll_data": "Sem dados de pesquisa disponiveis.",
  "sentiment_label": "Sentimento por tema",
  "no_sentiment_data": "Sem dados de sentimento disponiveis.",
  "tse_registration": "Registro no TSE",
  "tse_link_text": "Consultar registro no DivulgaCand",
  "comparison_title": "{{a}} vs {{b}}: comparacao de propostas",
  "comparison_loading": "Carregando comparacao...",
  "comparison_error": "Erro ao carregar comparacao.",
  "comparison_not_found": "Comparacao nao encontrada.",
  "comparison_topic_header": "Tema",
  "no_position": "Posicao nao registrada",
  "view_profile": "Ver perfil",
  "source_label": "Fonte"
}
```

### 2.14 `site/src/locales/en-US/candidates.json` — CREATE

```json
{
  "title": "Candidates",
  "loading": "Loading candidate data...",
  "error": "Error loading candidate data.",
  "not_found": "Candidate not found.",
  "pre_candidate": "Pre-candidate",
  "speculated": "Speculated",
  "confirmed": "Confirmed",
  "withdrawn": "Withdrawn",
  "party_label": "Party",
  "bio_label": "Profile",
  "recent_news": "Recent news",
  "latest_poll": "Latest poll",
  "poll_percentage": "{{percentage}}% in latest poll",
  "no_poll_data": "No poll data available.",
  "sentiment_label": "Sentiment by topic",
  "no_sentiment_data": "No sentiment data available.",
  "tse_registration": "TSE Registration",
  "tse_link_text": "Check registration on DivulgaCand",
  "comparison_title": "{{a}} vs {{b}}: proposal comparison",
  "comparison_loading": "Loading comparison...",
  "comparison_error": "Error loading comparison.",
  "comparison_not_found": "Comparison not found.",
  "comparison_topic_header": "Topic",
  "no_position": "Position not recorded",
  "view_profile": "View profile",
  "source_label": "Source"
}
```

### 2.15 `docs/adr/004-seo-geo-strategy.md` — CREATE

**Structure:**

```markdown
# ADR 004 — SEO/GEO Strategy

## Status: Accepted
## Date: 2026-03-11

## Context
- GitHub Pages is static-only; SSR is not available
- AI assistants (ChatGPT, Claude, Perplexity) are increasingly used for election queries
- Comparison queries ("X vs Y") are high-value for GEO (Generative Engine Optimization)

## Decision
1. SSG pre-render all candidate (/candidato/[slug]) and comparison (/comparar/[a]-vs-[b]) pages at build time using vite-react-ssg
2. robots.txt explicitly permits GPTBot, ClaudeBot, PerplexityBot, GoogleOther
3. JSON-LD structured data per page type: Person+ProfilePage for candidates, FAQPage+Article for comparisons
4. sitemap.xml generated by generate_seo_pages.py with all routes (static + dynamic)
5. Cloudflare _headers with 30min cache + stale-while-revalidate

## Consequences
- All 9 candidate + 8 comparison pages are crawlable by both search engines and AI crawlers
- Content is available without JavaScript execution
- Sitemap must be regenerated on each deploy (automated in deploy.yml)
- New candidates or comparison pairs require updating both generate_seo_pages.py and vite.config.js
```

---

## 3) Data Contract Notes

### `data/candidates.json`
- Must satisfy `docs/schemas/candidates.schema.json`
- Must have exactly 9 entries
- Each `slug` must be a valid `CandidateSlug` from `types.ts`
- Each `color` must match the corresponding entry in `site/src/utils/candidateColors.js`
- `photo_url` and `tse_registration_url` are `null` until August 2026

### `site/public/sitemap.xml`
- Must contain: 6 static routes + 9 candidate routes + 8 comparison routes = **23 URLs total**
- XML namespace: `http://www.sitemaps.org/schemas/sitemap/0.9`
- Each URL: `<loc>`, `<lastmod>`, `<changefreq>`, `<priority>`

### `CandidatePage.jsx` data dependencies
- `useData('candidates')` -> `CandidatesFile` -> find by slug
- `useData('articles')` -> filter `candidates_mentioned.includes(slug)`, sort by `published_at` desc, take 5
- `useData('sentiment')` -> `sentiment.by_topic[slug]` (may not exist for all candidates)
- `useData('polls')` -> find most recent `Poll`, then `results.find(r => r.candidate_slug === slug)`

### `ComparisonPage.jsx` data dependencies
- `useData('candidates')` -> find both candidates by slug
- `useData('quiz')` -> for each topic in `ordered_topics`, find options where `candidate_slug` matches either candidate

---

## 4) Step-by-Step Implementation Order

### Step 1: Data layer (no frontend dependency)
1. **`docs/schemas/candidates.schema.json`** — Create the JSON Schema
2. **`docs/schemas/types.ts`** — Extend `Candidate` interface with `bio_pt`, `bio_en`, `photo_url`, `tse_registration_url`; add `CandidatesFile` interface
3. **`data/candidates.json`** — Create with all 9 candidates satisfying the schema

### Step 2: Python script (depends on Step 1)
4. **`scripts/generate_seo_pages.py`** — Replace stub with full implementation; reads `data/candidates.json`, writes `site/public/sitemap.xml`
5. Verify: run the script and check output

### Step 3: Static files (no dependency)
6. **`site/public/robots.txt`** — Create verbatim from arch spec
7. **`site/public/_headers`** — Create verbatim from arch spec

### Step 4: i18n (no frontend dependency)
8. **`site/src/locales/pt-BR/candidates.json`** — Create
9. **`site/src/locales/en-US/candidates.json`** — Create
10. **`site/src/main.jsx`** — Register `candidates` namespace

### Step 5: Pages (depends on Steps 1, 4)
11. **`site/src/pages/CandidatePage.jsx`** — Create with all sub-components, Helmet, JSON-LD
12. **`site/src/pages/ComparisonPage.jsx`** — Create with comparison table, accordion, Helmet, JSON-LD
13. **`site/src/pages/CandidatesPage.jsx`** — Replace placeholder with candidate listing grid

### Step 6: Routing and SSG (depends on Step 5)
14. **`site/src/App.jsx`** — Add imports and routes for CandidatePage, ComparisonPage
15. **`site/vite.config.js`** — Add `includedRoutes` to `ssgOptions`

### Step 7: ADR (no dependency)
16. **`docs/adr/004-seo-geo-strategy.md`** — Create

### Step 8: Verification (depends on all above)
17. Run `generate_seo_pages.py` and validate sitemap
18. Run `npm run build` from `site/` and verify pre-rendered pages in `dist/`
19. Verify JSON-LD in generated HTML files

---

## 5) Test and Verification Commands (PowerShell 7)

```powershell
# --- Step 2 verification: Python script ---
python scripts/generate_seo_pages.py
# Expected output: "sitemap.xml: 23 URLs generated"

# Verify sitemap file exists and has correct URL count
$sitemap = Get-Content site/public/sitemap.xml -Raw
$urlCount = ([regex]::Matches($sitemap, '<url>')).Count
if ($urlCount -ne 23) { throw "Expected 23 URLs in sitemap, got $urlCount" }
Write-Host "PASS: sitemap.xml has $urlCount URLs"

# Verify sitemap contains a candidate route
if ($sitemap -notmatch 'candidato/lula') { throw "Missing /candidato/lula in sitemap" }
Write-Host "PASS: /candidato/lula found in sitemap"

# Verify sitemap contains a comparison route
if ($sitemap -notmatch 'comparar/lula-vs-tarcisio') { throw "Missing /comparar/lula-vs-tarcisio in sitemap" }
Write-Host "PASS: /comparar/lula-vs-tarcisio found in sitemap"

# --- Step 2 verification: Idempotency ---
python scripts/generate_seo_pages.py
$sitemap2 = Get-Content site/public/sitemap.xml -Raw
if ($sitemap -ne $sitemap2) { throw "Script is not idempotent!" }
Write-Host "PASS: generate_seo_pages.py is idempotent"

# --- Step 3 verification: Static files ---
if (-not (Test-Path site/public/robots.txt)) { throw "robots.txt missing" }
$robots = Get-Content site/public/robots.txt -Raw
if ($robots -notmatch 'GPTBot') { throw "robots.txt missing GPTBot" }
if ($robots -notmatch 'ClaudeBot') { throw "robots.txt missing ClaudeBot" }
Write-Host "PASS: robots.txt exists with AI crawler rules"

if (-not (Test-Path site/public/_headers)) { throw "_headers missing" }
$headers = Get-Content site/public/_headers -Raw
if ($headers -notmatch 'Cache-Control') { throw "_headers missing Cache-Control" }
Write-Host "PASS: _headers exists with cache directives"

# --- Step 1 verification: candidates.json ---
$candidates = Get-Content data/candidates.json | ConvertFrom-Json
if ($candidates.candidates.Count -ne 9) { throw "Expected 9 candidates, got $($candidates.candidates.Count)" }
Write-Host "PASS: candidates.json has 9 candidates"

# Verify all required fields exist on first candidate
$c = $candidates.candidates[0]
$requiredFields = @('slug','name','full_name','party','party_site','color','twitter','status','bio_pt','bio_en','photo_url','tse_registration_url')
foreach ($f in $requiredFields) {
  if (-not ($c.PSObject.Properties.Name -contains $f)) { throw "Missing field '$f' in candidate" }
}
Write-Host "PASS: All required fields present in candidates"

# --- Step 4 verification: i18n files ---
if (-not (Test-Path site/src/locales/pt-BR/candidates.json)) { throw "pt-BR candidates.json missing" }
if (-not (Test-Path site/src/locales/en-US/candidates.json)) { throw "en-US candidates.json missing" }
Write-Host "PASS: i18n candidate locale files exist"

# --- Step 7 verification: ADR ---
if (-not (Test-Path docs/adr/004-seo-geo-strategy.md)) { throw "ADR 004 missing" }
Write-Host "PASS: ADR 004 exists"

# --- Step 8 verification: Build ---
Push-Location site
npm run build
Pop-Location

# Verify candidate pages pre-rendered
$candidateSlugs = @('lula','flavio-bolsonaro','tarcisio','caiado','zema','ratinho-jr','eduardo-leite','aldo-rebelo','renan-santos')
foreach ($slug in $candidateSlugs) {
  $htmlPath = "site/dist/candidato/$slug/index.html"
  if (-not (Test-Path $htmlPath)) { throw "Missing pre-rendered page: $htmlPath" }
}
Write-Host "PASS: All 9 candidate pages pre-rendered"

# Verify comparison pages pre-rendered
$comparisonPairs = @('lula-vs-tarcisio','lula-vs-caiado','tarcisio-vs-caiado','tarcisio-vs-ratinho-jr','lula-vs-zema','caiado-vs-ratinho-jr','lula-vs-ratinho-jr','tarcisio-vs-zema')
foreach ($pair in $comparisonPairs) {
  $htmlPath = "site/dist/comparar/$pair/index.html"
  if (-not (Test-Path $htmlPath)) { throw "Missing pre-rendered page: $htmlPath" }
}
Write-Host "PASS: All 8 comparison pages pre-rendered"

# Verify JSON-LD in a candidate page
$lulaHtml = Get-Content site/dist/candidato/lula/index.html -Raw
if ($lulaHtml -notmatch 'schema\.org') { throw "Missing JSON-LD in /candidato/lula" }
if ($lulaHtml -notmatch 'ProfilePage') { throw "Missing ProfilePage type in JSON-LD" }
Write-Host "PASS: JSON-LD present in candidate pages"

# Verify JSON-LD in a comparison page
$compHtml = Get-Content site/dist/comparar/lula-vs-tarcisio/index.html -Raw
if ($compHtml -notmatch 'schema\.org') { throw "Missing JSON-LD in comparison page" }
if ($compHtml -notmatch 'FAQPage') { throw "Missing FAQPage type in JSON-LD" }
Write-Host "PASS: JSON-LD present in comparison pages"

# Verify sitemap copied to dist
if (-not (Test-Path site/dist/sitemap.xml)) { throw "sitemap.xml not in dist" }
Write-Host "PASS: sitemap.xml present in dist"

Write-Host "`nAll Phase 12 verifications PASSED."
```

---

## 6) Git Commit Message

```
feat(phase-12): SEO/GEO — candidate pages, comparison pages, sitemap, robots.txt

- Add data/candidates.json with all 9 candidates
- Add docs/schemas/candidates.schema.json
- Extend Candidate type in types.ts with bio/photo/TSE fields
- Implement generate_seo_pages.py (sitemap.xml with 23 URLs)
- Create CandidatePage.jsx with JSON-LD Person+ProfilePage
- Create ComparisonPage.jsx with JSON-LD FAQPage+Article
- Update CandidatesPage.jsx from placeholder to listing grid
- Add candidate routes and SSG pre-rendering config
- Add robots.txt with AI crawler allowances (GPTBot, ClaudeBot, PerplexityBot)
- Add _headers with Cloudflare cache directives
- Add pt-BR/en-US candidates i18n namespace
- Add ADR 004 (SEO/GEO strategy)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## 7) Completion Sentinel

After all deliverables verified and committed:

```powershell
New-Item -Path plans/phase-12-arch.DONE -ItemType File -Force
```

---

## Edge Cases and Notes

1. **SSG data fetching**: During SSG build, `useData` calls `fetch('/data/...')` which requires data files in `site/public/data/`. The `deploy.yml` workflow already copies `data/` to `site/public/data/` before build. For local builds, ensure `data/*.json` files are manually copied or the dev proxy is used.

2. **Candidate slug parsing in ComparisonPage**: The URL format is `/comparar/lula-vs-tarcisio`. Parse by splitting on `-vs-`. Handle edge case where candidate slug itself contains hyphens (e.g., `ratinho-jr`): split on the **first** occurrence of `-vs-` only. Use `pairSlug.split('-vs-')` which works because `-vs-` is not a substring of any candidate slug.

3. **Quiz data for comparisons**: Not all candidates may have positions in `quiz.json`. Show `t('candidates.no_position')` for missing entries.

4. **Sentiment data**: `sentiment.by_topic` is keyed by candidate slug. Some candidates may not have sentiment data yet. Show `t('candidates.no_sentiment_data')` for missing entries.

5. **Poll data**: Find the most recent `Poll` by `published_at`, then find the `PollResult` matching the candidate slug. May not exist for all candidates.

6. **React Router param name**: Use `:slug` for candidate, `:pairSlug` for comparison. Access via `useParams()`.

7. **Idempotency of generate_seo_pages.py**: The script always overwrites `sitemap.xml` completely. Running twice on the same day produces byte-identical output (since `<lastmod>` uses `date.today()`).

8. **Existing `candidatos` route**: Keep it as the listing page. The new `candidato/:slug` (singular) route is separate. Do NOT break the existing nav link to `/candidatos`.
