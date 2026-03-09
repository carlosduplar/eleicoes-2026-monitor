# Phase 12 — SEO / GEO

## Objective

Implement candidate profile pages (`/candidato/[slug]`), candidate comparison pages (`/comparar/[a]-vs-[b]`), and the SEO/GEO support infrastructure: `generate_seo_pages.py`, `data/candidates.json`, `sitemap.xml`, `robots.txt`, `_headers` (Cloudflare), and JSON-LD structured data. All pages are SSG pre-rendered. Create ADR 004.

## Input Context

- `docs/wireframes/WF-07-candidate-profile-desktop.html` — Candidate profile wireframe (open in browser)
- `docs/wireframes/WF-08-candidate-comparison.html` — Comparison wireframe (open in browser)
- `docs/prompt-eleicoes2026-v5.md` lines 644-705 — SEO/GEO spec (JSON-LD schemas, comparison pairs, robots.txt, _headers)
- `docs/prompt-eleicoes2026-v5.md` lines 322-334 — TSE key dates and DivulgaCand URL
- `docs/prompt-eleicoes2026-v5.md` lines 351-388 — Full `CANDIDATES` list
- `docs/schemas/candidates.schema.json` — Candidates schema (from Phase 01)
- `site/src/utils/candidateColors.js` — Candidate hex colors (from Phase 07)
- `site/src/components/MethodologyBadge.jsx` — Required on candidate pages (from Phase 07)
- `data/articles.json` — For recent articles per candidate (from Phase 06)
- `data/sentiment.json` — For per-candidate sentiment summary (from Phase 06)
- `data/polls.json` — For latest poll snapshot per candidate (from Phase 08)

## Deliverables

### 1. `data/candidates.json`

Full profiles for all 9 candidates. Seed with static data (updated manually when official registrations change after August 2026):

```json
{
  "candidates": [
    {
      "slug": "lula",
      "name": "Lula",
      "full_name": "Luiz Inácio Lula da Silva",
      "party": "PT",
      "party_site": "https://pt.org.br",
      "color": "#CC0000",
      "twitter": "LulaOficial",
      "status": "pre-candidate",
      "bio_pt": "Presidente em exercício, candidato à reeleição pelo PT.",
      "bio_en": "Incumbent president, seeking re-election for PT.",
      "photo_url": null,
      "tse_registration_url": null
    }
  ]
}
```

Include all 9 candidates from `PLANS.md`. `photo_url` and `tse_registration_url` are `null` until official registration (August 2026).

### 2. `scripts/generate_seo_pages.py`

Generates sitemap and validates candidate data. Runs in `deploy.yml` before the SSG build.

**Key behaviors:**
- Read `data/candidates.json`
- Generate `site/public/sitemap.xml` with all static routes:
  - `/` — priority `1.0`
  - `/sentimento` — priority `0.8`
  - `/pesquisas` — priority `0.8`
  - `/quiz` — priority `0.9`
  - `/metodologia` — priority `0.7`
  - `/sobre/caso-de-uso` — priority `0.6`
  - `/candidato/{slug}` for each candidate — priority `0.9`
  - `/comparar/{a}-vs-{b}` for each comparison pair — priority `0.8`
- Base URL: `https://eleicoes2026.com.br`
- `<lastmod>`: today's date
- `<changefreq>`: `daily` for candidates/home, `weekly` for comparison/methodology
- Print summary: "sitemap.xml: X URLs generated"
- **Idempotent**

**Comparison pairs (from spec):**
```python
COMPARISON_PAIRS = [
    ("lula","tarcisio"), ("lula","caiado"), ("tarcisio","caiado"),
    ("tarcisio","ratinho-jr"), ("lula","zema"), ("caiado","ratinho-jr"),
    ("lula","ratinho-jr"), ("tarcisio","zema"),
]
```

### 3. `site/public/robots.txt`

```
User-agent: *
Allow: /
Sitemap: https://eleicoes2026.com.br/sitemap.xml

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: GoogleOther
Allow: /
```

### 4. `site/public/_headers` (Cloudflare)

```
/*
  Cache-Control: public, max-age=1800, stale-while-revalidate=300
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin

/data/*.json
  Cache-Control: public, max-age=1800, stale-while-revalidate=300
  Access-Control-Allow-Origin: *

/feed*.xml
  Cache-Control: public, max-age=1800
  Content-Type: application/rss+xml; charset=utf-8

/quiz*
  Cache-Control: public, max-age=3600
```

### 5. `site/src/pages/CandidatePage.jsx`

SSG pre-rendered page at `/candidato/[slug]`. Replaces Phase 04 placeholder in `CandidatesPage.jsx`.

**Layout (WF-07):**
- Hero: candidate color banner (`background: CANDIDATE_COLORS[slug]`), full name, party, status badge
- Bio section: `bio_pt`/`bio_en`
- Sentiment summary: mini chart using `data.by_topic[slug]` from `sentiment.json` (reuse `useData`)
- Recent articles: 5 most recent from `articles.json` where `candidates_mentioned` includes the slug
- Poll snapshot: latest poll percentage from `polls.json`
- `MethodologyBadge`
- TSE link section (shown after August 2026 based on `tse_registration_url !== null`)

**`<Helmet>` and JSON-LD:**
```json
{
  "@context": "https://schema.org",
  "@type": ["Person", "ProfilePage"],
  "name": "<full_name>",
  "description": "<bio_pt or bio_en>",
  "affiliation": {"@type": "Organization", "name": "<party>"},
  "url": "https://eleicoes2026.com.br/candidato/<slug>"
}
```

**SSG route generation:** in `vite.config.js`, add candidate slugs to the routes pre-rendered at build time:
```javascript
includedRoutes: (paths, routes) => {
  const slugs = ['lula','flavio-bolsonaro','tarcisio','caiado','zema','ratinho-jr','eduardo-leite','aldo-rebelo','renan-santos'];
  return [...paths, ...slugs.map(s => `/candidato/${s}`)];
}
```

### 6. `site/src/pages/ComparisonPage.jsx`

SSG pre-rendered page at `/comparar/[a]-vs-[b]`.

**Layout (WF-08):**
- Side-by-side candidate panels with their colors
- Topics comparison table: each row = a quiz topic; columns = candidate A stance | candidate B stance
- Data source: `data/quiz.json` positions for each candidate
- FAQ-style accordion: each topic expanded to show position text and source
- `MethodologyBadge`

**`<Helmet>` and JSON-LD:**
```json
{
  "@context": "https://schema.org",
  "@type": ["FAQPage", "Article"],
  "headline": "<Name A> vs <Name B>: comparação de propostas 2026",
  "url": "https://eleicoes2026.com.br/comparar/<a>-vs-<b>"
}
```

**SSG route generation:** add the 8 comparison pairs to `includedRoutes` in `vite.config.js`.

### 7. i18n additions

**`site/src/locales/pt-BR/candidates.json`:**
```json
{
  "title": "Candidatos",
  "pre_candidate": "Pré-candidato",
  "speculated": "Cotado",
  "party_label": "Partido",
  "bio_label": "Perfil",
  "recent_news": "Notícias recentes",
  "latest_poll": "Última pesquisa",
  "tse_registration": "Registro no TSE",
  "comparison_title": "{{a}} vs {{b}}: comparação de propostas",
  "comparison_topic_header": "Tema",
  "no_position": "Posição não registrada"
}
```

**`site/src/locales/en-US/candidates.json`** — English equivalents.

### 8. `docs/adr/004-seo-geo-strategy.md`

Document:
- SSG pre-render rationale (GitHub Pages is static-only)
- GEO strategy: comparison pages target "X vs Y" natural language queries from AI assistants
- `robots.txt` explicitly permits GPTBot, ClaudeBot, PerplexityBot, GoogleOther
- JSON-LD schemas chosen per page type
- Sitemap update frequency and `generate_seo_pages.py` integration in `deploy.yml`

## Constraints

- `CandidatePage` and `ComparisonPage` must be SSG pre-rendered at build time — not client-side rendered only
- All 9 candidate pages and 8 comparison pages must appear in `sitemap.xml`
- `robots.txt` must explicitly allow AI crawlers (this is intentional for GEO)
- `_headers` file must be in `site/public/` for Cloudflare to pick it up
- `generate_seo_pages.py` is already called in `deploy.yml` (from Phase 05 stub) — replace the stub with the full implementation

## Acceptance Criteria

- [ ] `python scripts/generate_seo_pages.py` runs and writes `site/public/sitemap.xml` with all routes
- [ ] `site/public/robots.txt` exists with AI crawler allowances
- [ ] `site/public/_headers` exists with Cloudflare cache directives
- [ ] `/candidato/lula` renders with hero, bio, sentiment mini-chart, and recent articles
- [ ] `/comparar/lula-vs-tarcisio` renders side-by-side with topic comparison table
- [ ] JSON-LD structured data is present in `<head>` for both page types
- [ ] `data/candidates.json` contains all 9 candidates with required fields
- [ ] `docs/adr/004-seo-geo-strategy.md` committed
- [ ] `npm run build` pre-renders all 9 candidate pages and 8 comparison pages in `dist/`
- [ ] `dist/sitemap.xml` exists after build

## Commit & Push

After all deliverables are verified:

```
git add scripts/generate_seo_pages.py data/candidates.json site/src/pages/CandidatePage.jsx site/src/pages/ComparisonPage.jsx site/src/locales/ site/public/robots.txt site/public/_headers site/public/sitemap.xml site/vite.config.js docs/adr/004-seo-geo-strategy.md
git commit -m "feat(phase-12): SEO/GEO — candidate pages, comparison pages, sitemap, robots.txt

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-12-arch.DONE`.
