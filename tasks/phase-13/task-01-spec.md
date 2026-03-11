# Phase 13 — Task 01 Spec (Case Study Page: Bilingual Living Documentation)

> Planner: Opus 4.6 | Implementor: Codex | Date: 2026-03-11

---

## Inputs and Mandatory References

| # | Ref | Path | Why |
|---|-----|------|-----|
| 1 | Arch spec | `plans/phase-13-arch.md` | Full Phase 13 deliverables, acceptance criteria, constraints |
| 2 | WF-10 wireframe | `docs/wireframes/WF-10-case-study.html` | Visual layout reference — 6 numbered sections + sidebar |
| 3 | TypeScript types | `docs/schemas/types.ts` | Shared type definitions (no schema changes needed for Phase 13) |
| 4 | ADR 000 | `docs/adr/000-wireframes.md` | Design tokens, typography, CSS custom properties |
| 5 | i18n bootstrap | `site/src/main.jsx` | Current i18n namespace config (3 namespaces: common, methodology, candidates) |
| 6 | pt-BR common | `site/src/locales/pt-BR/common.json` | Existing i18n key structure, nav keys |
| 7 | en-US common | `site/src/locales/en-US/common.json` | English nav keys |
| 8 | Methodology page | `site/src/pages/MethodologyPage.jsx` | Closest pattern — long-form editorial page with Helmet + JSON-LD |
| 9 | Methodology locale | `site/src/locales/pt-BR/methodology.json` | Namespace structure pattern for dedicated page locales |
| 10 | App router | `site/src/App.jsx` | Route definitions — must add `/sobre/caso-de-uso` |
| 11 | Nav component | `site/src/components/Nav.jsx` | `navItems` array — must add case study link |
| 12 | Vite config | `site/vite.config.js` | SSG `includedRoutes` — may need to add case study route |
| 13 | Deploy workflow | `.github/workflows/deploy.yml` | Case-study copy step (line 50-53) — remove `|| true` |
| 14 | Case study pt-BR | `docs/case-study/pt-BR.md` | Existing partial content (Phases 03-05 only, ~78 lines) |
| 15 | Case study en-US | `docs/case-study/en-US.md` | Existing partial English content (Phases 03-05 only) |
| 16 | PLAN.md | `PLAN.md` | Phase history, architectural decisions, agent hierarchy, project numbers |
| 17 | ADRs 001-006 | `docs/adr/001-*.md` through `006-*.md` | Content for "Technical Decisions" section |
| 18 | package.json | `site/package.json` | Must add `marked` dependency |
| 19 | Styles | `site/src/styles.css` | CSS class naming patterns (`.methodology-*` as reference) |
| 20 | useData hook | `site/src/hooks/useData.js` | Existing data-fetch pattern (JSON only — case study uses raw fetch for .md) |

---

## 1) Files to Create or Modify

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `docs/case-study/pt-BR.md` | **REWRITE** | Full Portuguese case study with all 8 required sections (min 800 words). Replace current partial content (Phases 03-05 log) with structured narrative per arch spec. |
| 2 | `docs/case-study/en-US.md` | **REWRITE** | Full English case study — same structure, full translation (min 800 words). |
| 3 | `site/src/locales/pt-BR/case-study.json` | **CREATE** | Portuguese i18n namespace for case study UI chrome (title, subtitle, toc_label, section names, etc.) |
| 4 | `site/src/locales/en-US/case-study.json` | **CREATE** | English i18n namespace for case study UI chrome. |
| 5 | `site/src/pages/CaseStudyPage.jsx` | **CREATE** | Main page component at `/sobre/caso-de-uso` — loads markdown, renders with `marked`, sticky TOC sidebar, JSON-LD TechArticle, loading/error states. |
| 6 | `site/src/main.jsx` | **MODIFY** | Add `case-study` namespace: import locale JSONs, add to `resources` and `ns` array. |
| 7 | `site/src/App.jsx` | **MODIFY** | Import `CaseStudyPage`, add route `{ path: 'sobre/caso-de-uso', element: <CaseStudyPage /> }` to children. |
| 8 | `site/src/components/Nav.jsx` | **MODIFY** | Add case study entry to `navItems` array. |
| 9 | `site/src/locales/pt-BR/common.json` | **MODIFY** | Add `nav.caso_de_uso` key for navigation label. |
| 10 | `site/src/locales/en-US/common.json` | **MODIFY** | Add `nav.caso_de_uso` key (English). |
| 11 | `site/package.json` | **MODIFY** | Add `"marked": "^15.0.0"` to dependencies (via `npm install`). |
| 12 | `site/vite.config.js` | **MODIFY** | Add `'/sobre/caso-de-uso'` to `includedRoutes` return array for SSG pre-rendering. |
| 13 | `site/src/styles.css` | **MODIFY** | Add `.case-study-*` CSS classes for the page layout (TOC sidebar, article body, breadcrumb, section styles). |
| 14 | `.github/workflows/deploy.yml` | **MODIFY** | Remove `|| true` from the case-study copy step (line 53). |

---

## 2) Function Signatures and Types per File

### 2.1 `docs/case-study/pt-BR.md` — REWRITE

Full narrative markdown document. Required H2 sections (in this exact order):

```markdown
# Caso de Uso: Portal Eleicoes BR 2026

## Sumario executivo
[1-2 paragraphs: what was built, why, with what tools]

## Stack e arquitetura
[React + Vite + SSG, Python 3.12, GitHub Actions, GitHub Pages]
[Key ADR decisions summarized]

## Hierarquia de agentes
[Opus (Arquiteto) -> Codex (Tatico) -> MiniMax (Operacional) -> Gemini (QA)]
[RALPH loop protocol: Read -> Analyze -> List -> Plan -> Handle]
[Handoff via sentinel files: plans/phase-NN-arch.DONE]

## Pipeline de ingestao
[Foca (coletor) -> Editor (validacao) -> Editor-chefe (curadoria)]
[Publication stages: raw -> validated -> curated]
[AI fallback chain: NVIDIA NIM -> OpenRouter -> Ollama -> Vertex -> MiMo]

## Decisoes tecnicas registradas
[ADR 000: Wireframes e design tokens]
[ADR 001: GitHub Pages + Cloudflare hosting]
[ADR 002: Multi-provider AI fallback]
[ADR 003: i18n strategy (pt-BR + en-US)]
[ADR 004: SEO/GEO SSG pre-rendering]
[ADR 005: Quiz affinity system — divergence scoring]
[ADR 006: Transparency & methodology pipeline stages]

## Licoes aprendidas
[Honest assessment: vibe coding + AI agents productivity]
[Complexity of multi-agent coordination]
[What worked well, what was hard, what would be different]

## Numeros do projeto
[~16 phases, N files, N commits, pipeline frequency, source count, candidate count]

## Proximos passos
[Phase 14: Party/social collection expansion]
[Phase 15: Mobile polish]
[Phase 16: Final QA]
```

**Constraint:** Minimum 800 words. Content must be factual, derived from PLAN.md and ADRs. No invented metrics.

### 2.2 `docs/case-study/en-US.md` — REWRITE

Same structure as pt-BR.md, fully translated to English. Same 800-word minimum. Same H2 section headers (translated).

```markdown
# Case Study: Portal Eleicoes BR 2026

## Executive summary
## Stack and architecture
## Agent hierarchy
## Ingestion pipeline
## Technical decisions recorded
## Lessons learned
## Project numbers
## Next steps
```

### 2.3 `site/src/locales/pt-BR/case-study.json` — CREATE

```json
{
  "title": "Caso de Uso: Desenvolvimento com IA",
  "subtitle": "Como construimos um portal eleitoral em tempo real usando multiplos agentes de IA",
  "toc_label": "Neste artigo",
  "back_to_home": "Voltar ao portal",
  "reading_time": "{{minutes}} min de leitura",
  "last_updated": "Atualizado em {{date}}",
  "share": "Compartilhar este caso de uso",
  "loading": "Carregando caso de uso...",
  "error": "Conteudo indisponivel. Tente novamente mais tarde.",
  "breadcrumb_home": "Portal Eleicoes BR 2026",
  "breadcrumb_about": "Sobre",
  "breadcrumb_case_study": "Caso de Uso",
  "sections": {
    "executive_summary": "Sumario Executivo",
    "stack": "Stack e Arquitetura",
    "agents": "Hierarquia de Agentes",
    "pipeline": "Pipeline de Ingestao",
    "adrs": "Decisoes Tecnicas",
    "lessons": "Licoes Aprendidas",
    "numbers": "Numeros do Projeto",
    "next_steps": "Proximos Passos"
  }
}
```

### 2.4 `site/src/locales/en-US/case-study.json` — CREATE

```json
{
  "title": "Case Study: AI-Assisted Development",
  "subtitle": "How we built a real-time election portal using multiple AI agents",
  "toc_label": "In this article",
  "back_to_home": "Back to portal",
  "reading_time": "{{minutes}} min read",
  "last_updated": "Updated on {{date}}",
  "share": "Share this case study",
  "loading": "Loading case study...",
  "error": "Content unavailable. Please try again later.",
  "breadcrumb_home": "Portal Eleicoes BR 2026",
  "breadcrumb_about": "About",
  "breadcrumb_case_study": "Case Study",
  "sections": {
    "executive_summary": "Executive Summary",
    "stack": "Stack and Architecture",
    "agents": "Agent Hierarchy",
    "pipeline": "Ingestion Pipeline",
    "adrs": "Technical Decisions",
    "lessons": "Lessons Learned",
    "numbers": "Project Numbers",
    "next_steps": "Next Steps"
  }
}
```

### 2.5 `site/src/pages/CaseStudyPage.jsx` — CREATE

```jsx
// Component: CaseStudyPage
// Route: /sobre/caso-de-uso
// Pattern: follows MethodologyPage.jsx conventions

import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
// marked must be installed: npm install marked
import { marked } from 'marked';

// Helmet extraction pattern (same as MethodologyPage)
const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

/**
 * extractHeadings(markdown: string) => Array<{ id: string, text: string, level: number }>
 *
 * Parses H2 headings from raw markdown to build TOC.
 * Uses regex: /^##\s+(.+)$/gm
 * Generates slug IDs: text.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
 */

/**
 * useMarkdownContent(language: string) => { content: string | null, loading: boolean, error: Error | null }
 *
 * Custom hook (defined inside this file, not a separate file).
 * Fetches `/case-study/${language}.md` via fetch().
 * Returns raw markdown string.
 * Refetches when `language` changes (i18n language toggle).
 * Uses AbortController for cleanup on unmount/language change.
 */

/**
 * calculateReadingTime(text: string) => number
 *
 * Returns estimated reading time in minutes.
 * Formula: Math.ceil(text.split(/\s+/).length / 200)
 */

/**
 * CaseStudyPage() => JSX.Element
 *
 * Main exported component. Structure:
 *
 * <article className="case-study-page">
 *   <Helmet>
 *     <title>{t('case-study:title')} | {t('common:brand')}</title>
 *     <script type="application/ld+json">{jsonLdText}</script>
 *   </Helmet>
 *   <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdText }} />
 *
 *   <nav className="case-study-breadcrumb">
 *     <!-- Portal > Sobre > Caso de Uso -->
 *   </nav>
 *
 *   <div className="case-study-layout">
 *     <aside className="case-study-toc">
 *       <h2>{t('case-study:toc_label')}</h2>
 *       <ul>
 *         {headings.map(h => <li key={h.id}><a href={`#${h.id}`}>{h.text}</a></li>)}
 *       </ul>
 *     </aside>
 *
 *     <div className="case-study-content">
 *       <!-- LOADING STATE: skeleton paragraphs -->
 *       <!-- ERROR STATE: error message -->
 *       <!-- LOADED STATE: rendered markdown HTML via dangerouslySetInnerHTML -->
 *     </div>
 *   </div>
 * </article>
 *
 * States:
 * - loading: Show skeleton (2 skeleton blocks per section, 8 sections = ~16 skeleton lines)
 * - error: Show t('case-study:error')
 * - loaded: Render HTML from marked(markdown)
 *
 * JSON-LD:
 * {
 *   "@context": "https://schema.org",
 *   "@type": "TechArticle",
 *   "headline": t('case-study:title'),
 *   "description": t('case-study:subtitle'),
 *   "url": "https://eleicoes2026.com.br/sobre/caso-de-uso",
 *   "author": { "@type": "Organization", "name": "carlosduplar" },
 *   "inLanguage": i18n.language
 * }
 *
 * marked configuration:
 * - Configure marked to add `id` attributes to H2/H3 headings (use heading renderer override)
 * - Sanitize: marked does NOT sanitize by default; since we control the markdown source, this is acceptable
 */

export default CaseStudyPage;
```

**Internal helpers (not exported):**

| Function | Signature | Returns |
|----------|-----------|---------|
| `extractHeadings` | `(markdown: string) => Array<{id: string, text: string, level: number}>` | TOC data from H2s |
| `useMarkdownContent` | `(language: string) => {content: string\|null, loading: boolean, error: Error\|null}` | Fetched markdown |
| `calculateReadingTime` | `(text: string) => number` | Minutes (ceil) |
| `slugify` | `(text: string) => string` | URL-safe heading ID |

### 2.6 `site/src/main.jsx` — MODIFY

Changes required:

```javascript
// ADD these imports (after existing locale imports, ~line 12):
import ptCaseStudy from './locales/pt-BR/case-study.json';
import enCaseStudy from './locales/en-US/case-study.json';

// MODIFY resources object (~line 31) — add 'case-study' key to each language:
resources: {
  'pt-BR': { common: ptCommon, methodology: ptMethodology, candidates: ptCandidates, 'case-study': ptCaseStudy },
  'en-US': { common: enCommon, methodology: enMethodology, candidates: enCandidates, 'case-study': enCaseStudy },
},

// MODIFY ns array (~line 38):
ns: ['common', 'methodology', 'candidates', 'case-study'],
```

### 2.7 `site/src/App.jsx` — MODIFY

Changes required:

```javascript
// ADD import (after existing page imports, ~line 13):
import CaseStudyPage from './pages/CaseStudyPage';

// ADD route to children array (after metodologia route, ~line 40):
{ path: 'sobre/caso-de-uso', element: <CaseStudyPage /> },
```

### 2.8 `site/src/components/Nav.jsx` — MODIFY

Changes required:

```javascript
// ADD to navItems array (after metodologia entry, ~line 11):
{ to: '/sobre/caso-de-uso', key: 'caso_de_uso' },
```

### 2.9 `site/src/locales/pt-BR/common.json` — MODIFY

```json
// ADD to "nav" object:
"caso_de_uso": "Caso de Uso"
```

### 2.10 `site/src/locales/en-US/common.json` — MODIFY

```json
// ADD to "nav" object:
"caso_de_uso": "Case Study"
```

### 2.11 `site/package.json` — MODIFY (via npm install)

```bash
cd site && npm install marked@^15.0.0
```

This adds `"marked": "^15.0.0"` to the `dependencies` block.

### 2.12 `site/vite.config.js` — MODIFY

```javascript
// In includedRoutes callback, add to the return array (~line 57):
return [
  ...paths,
  ...candidateSlugs.map((slug) => `/candidato/${slug}`),
  ...comparisonPairs.map((pair) => `/comparar/${pair}`),
  '/sobre/caso-de-uso',   // <-- ADD THIS LINE
];
```

### 2.13 `site/src/styles.css` — MODIFY

Add CSS classes for the case study page. Follow the `.methodology-*` naming convention but use `.case-study-*` prefix.

```css
/* --- Case Study Page --- */

.case-study-page {
  max-width: 1100px;
  margin: 0 auto;
  padding-bottom: 2rem;
}

.case-study-breadcrumb {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
}

.case-study-breadcrumb a {
  color: var(--brand-gold);
  text-decoration: none;
}

.case-study-breadcrumb a:hover {
  text-decoration: underline;
}

.case-study-breadcrumb span {
  margin: 0 0.4rem;
}

.case-study-header {
  margin-bottom: 2rem;
}

.case-study-header h1 {
  font-size: clamp(1.5rem, 1.2rem + 0.8vw, 2rem);
  font-family: Georgia, 'Times New Roman', serif;
  margin-bottom: 0.35rem;
}

.case-study-meta {
  color: var(--text-secondary);
  font-size: 0.85rem;
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.case-study-layout {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 2rem;
  align-items: start;
}

/* Main markdown content */
.case-study-content {
  min-width: 0;
  line-height: 1.75;
  font-size: 0.95rem;
}

.case-study-content h2 {
  font-size: 1.3rem;
  font-weight: 600;
  font-family: Georgia, 'Times New Roman', serif;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.case-study-content h3 {
  font-size: 1.05rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
}

.case-study-content p {
  margin-bottom: 0.85rem;
  color: var(--text-primary);
}

.case-study-content ul,
.case-study-content ol {
  margin-bottom: 0.85rem;
  padding-left: 1.5rem;
}

.case-study-content li {
  margin-bottom: 0.3rem;
}

.case-study-content code {
  background: var(--brand-muted);
  padding: 0.15rem 0.35rem;
  border-radius: 4px;
  font-size: 0.85em;
}

.case-study-content a {
  color: var(--brand-gold);
  text-decoration: none;
}

.case-study-content a:hover {
  text-decoration: underline;
}

/* Sticky TOC sidebar */
.case-study-toc {
  position: sticky;
  top: 1.5rem;
  background: var(--brand-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
}

.case-study-toc h2 {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.case-study-toc ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.case-study-toc li {
  margin-bottom: 0.4rem;
}

.case-study-toc a {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.8rem;
  line-height: 1.4;
  display: block;
  padding: 0.15rem 0;
}

.case-study-toc a:hover,
.case-study-toc a.active {
  color: var(--brand-navy);
  font-weight: 500;
}

/* Skeleton loading state */
.case-study-skeleton {
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

.case-study-skeleton-line {
  height: 1rem;
  background: var(--brand-muted);
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.case-study-skeleton-line:nth-child(odd) {
  width: 90%;
}

.case-study-skeleton-line:nth-child(even) {
  width: 75%;
}

.case-study-skeleton-heading {
  height: 1.5rem;
  width: 50%;
  background: var(--brand-muted);
  border-radius: 4px;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Error state */
.case-study-error {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

/* Responsive: collapse TOC on mobile */
@media (max-width: 768px) {
  .case-study-layout {
    grid-template-columns: 1fr;
  }

  .case-study-toc {
    position: static;
    margin-bottom: 1.5rem;
  }
}
```

### 2.14 `.github/workflows/deploy.yml` — MODIFY

```yaml
# BEFORE (line 53):
          cp -r docs/case-study/. site/public/case-study/ || true

# AFTER:
          cp -r docs/case-study/. site/public/case-study/
```

Remove `|| true` — the case-study directory must exist by this phase.

---

## 3) Data Contract Notes

### No schema changes required

Phase 13 does not modify any `docs/schemas/*.schema.json` files. The case study is a static editorial page loading markdown files, not a data-driven component.

### Markdown file contract

Both `docs/case-study/pt-BR.md` and `en-US.md` must:
- Start with `# ` (H1 title)
- Contain exactly 8 `## ` (H2) sections matching the section keys in `case-study.json`
- Contain no raw HTML (pure markdown only)
- Be at least 800 words each
- Use only ASCII in heading text (for reliable slug generation)

### i18n namespace contract

The `case-study.json` locale files must have identical top-level key structure in both pt-BR and en-US. The `sections` object keys must align with the H2 headings in the markdown for TOC generation fallback.

### Deploy workflow contract

The `deploy.yml` must copy `docs/case-study/*.md` files into `site/public/case-study/` so that runtime `fetch('/case-study/pt-BR.md')` resolves correctly.

---

## 4) Step-by-Step Implementation Order

### Step 1: Install `marked` dependency

```powershell
cd site; npm install marked@^15.0.0; cd ..
```

Verify: `site/package.json` contains `"marked"` in dependencies and `site/node_modules/marked` exists.

### Step 2: Create i18n locale files

1. Create `site/src/locales/pt-BR/case-study.json` with all keys from section 2.3
2. Create `site/src/locales/en-US/case-study.json` with all keys from section 2.4

### Step 3: Register i18n namespace in `main.jsx`

1. Add imports for `ptCaseStudy` and `enCaseStudy`
2. Add `'case-study'` entries to `resources` object
3. Add `'case-study'` to `ns` array

### Step 4: Write case study markdown documents

1. Rewrite `docs/case-study/pt-BR.md` with all 8 required sections (content derived from PLAN.md, ADRs, and project facts)
2. Rewrite `docs/case-study/en-US.md` with equivalent English content

### Step 5: Add CSS styles

Append `.case-study-*` styles to `site/src/styles.css` per section 2.13.

### Step 6: Create `CaseStudyPage.jsx`

Implement the component per section 2.5:
1. `useMarkdownContent` hook with fetch + AbortController
2. `extractHeadings` function for TOC generation
3. `calculateReadingTime` function
4. `marked` configuration with heading ID renderer
5. Loading/error/loaded states
6. Helmet with title + JSON-LD TechArticle
7. Breadcrumb navigation
8. Two-column layout: content + TOC sidebar

### Step 7: Wire up routing

1. Modify `site/src/App.jsx` — import CaseStudyPage, add route
2. Modify `site/vite.config.js` — add `/sobre/caso-de-uso` to `includedRoutes`

### Step 8: Add navigation link

1. Modify `site/src/components/Nav.jsx` — add navItem entry
2. Modify `site/src/locales/pt-BR/common.json` — add `nav.caso_de_uso`
3. Modify `site/src/locales/en-US/common.json` — add `nav.caso_de_uso`

### Step 9: Fix deploy workflow

Remove `|| true` from the case-study copy step in `.github/workflows/deploy.yml`.

### Step 10: Verify

Run all verification commands from section 5.

---

## 5) Test and Verification Commands (PowerShell 7)

```powershell
# 1. Verify marked is installed
Test-Path site/node_modules/marked/lib/marked.cjs
# Expected: True

# 2. Verify case study markdown files exist and meet word count
$ptContent = Get-Content docs/case-study/pt-BR.md -Raw
$enContent = Get-Content docs/case-study/en-US.md -Raw
$ptWords = ($ptContent -split '\s+').Count
$enWords = ($enContent -split '\s+').Count
Write-Host "pt-BR words: $ptWords (min 800)"
Write-Host "en-US words: $enWords (min 800)"
if ($ptWords -lt 800 -or $enWords -lt 800) { throw "Case study below 800 words" }

# 3. Verify all 8 required H2 sections in pt-BR
$ptH2s = (Select-String -Path docs/case-study/pt-BR.md -Pattern '^## ' -AllMatches).Count
Write-Host "pt-BR H2 sections: $ptH2s (expected >= 8)"
if ($ptH2s -lt 8) { throw "pt-BR missing sections" }

# 4. Verify all 8 required H2 sections in en-US
$enH2s = (Select-String -Path docs/case-study/en-US.md -Pattern '^## ' -AllMatches).Count
Write-Host "en-US H2 sections: $enH2s (expected >= 8)"
if ($enH2s -lt 8) { throw "en-US missing sections" }

# 5. Verify i18n locale files exist and are valid JSON
Get-Content site/src/locales/pt-BR/case-study.json | ConvertFrom-Json | Out-Null
Get-Content site/src/locales/en-US/case-study.json | ConvertFrom-Json | Out-Null
Write-Host "Locale JSON files: valid"

# 6. Verify case-study namespace is registered in main.jsx
$mainContent = Get-Content site/src/main.jsx -Raw
if ($mainContent -notmatch "case-study") { throw "case-study namespace not in main.jsx" }
Write-Host "main.jsx: case-study namespace registered"

# 7. Verify route exists in App.jsx
$appContent = Get-Content site/src/App.jsx -Raw
if ($appContent -notmatch "sobre/caso-de-uso") { throw "Route not in App.jsx" }
if ($appContent -notmatch "CaseStudyPage") { throw "CaseStudyPage not imported in App.jsx" }
Write-Host "App.jsx: route and import present"

# 8. Verify Nav includes case study link
$navContent = Get-Content site/src/components/Nav.jsx -Raw
if ($navContent -notmatch "caso-de-uso") { throw "Nav missing case study link" }
Write-Host "Nav.jsx: case study link present"

# 9. Verify SSG includedRoutes has the case study path
$viteContent = Get-Content site/vite.config.js -Raw
if ($viteContent -notmatch "sobre/caso-de-uso") { throw "SSG missing case study route" }
Write-Host "vite.config.js: SSG route present"

# 10. Verify deploy.yml does NOT have || true on case-study copy
$deployContent = Get-Content .github/workflows/deploy.yml -Raw
if ($deployContent -match "case-study.*\|\|\s*true") { throw "deploy.yml still has || true" }
Write-Host "deploy.yml: || true removed"

# 11. Verify CaseStudyPage.jsx exists and imports marked
$cspContent = Get-Content site/src/pages/CaseStudyPage.jsx -Raw
if ($cspContent -notmatch "from 'marked'") { throw "CaseStudyPage missing marked import" }
if ($cspContent -notmatch "TechArticle") { throw "CaseStudyPage missing JSON-LD" }
if ($cspContent -notmatch "dangerouslySetInnerHTML") { throw "CaseStudyPage missing HTML rendering" }
Write-Host "CaseStudyPage.jsx: structure verified"

# 12. Build the site
cd site; npm run build; cd ..
# Expected: exit code 0, dist/ folder generated with sobre/caso-de-uso/index.html

# 13. Verify SSG output includes the case study page
Test-Path site/dist/sobre/caso-de-uso/index.html
# Expected: True

# 14. Verify JSON-LD in pre-rendered HTML
$prerendered = Get-Content site/dist/sobre/caso-de-uso/index.html -Raw
if ($prerendered -notmatch "TechArticle") { Write-Host "WARNING: JSON-LD may be client-side only" }

# 15. Verify nav link has correct common.json key
$ptCommon = Get-Content site/src/locales/pt-BR/common.json -Raw | ConvertFrom-Json
if (-not $ptCommon.nav.caso_de_uso) { throw "Missing nav.caso_de_uso in pt-BR" }
$enCommon = Get-Content site/src/locales/en-US/common.json -Raw | ConvertFrom-Json
if (-not $enCommon.nav.caso_de_uso) { throw "Missing nav.caso_de_uso in en-US" }
Write-Host "common.json: nav keys present in both locales"
```

---

## 6) Git Commit Message

```
feat(phase-13): case study page with bilingual living documentation

- Rewrite docs/case-study/pt-BR.md and en-US.md with full 8-section narrative
- Create CaseStudyPage.jsx at /sobre/caso-de-uso with marked markdown rendering
- Add case-study i18n namespace (pt-BR + en-US locale files)
- Sticky TOC sidebar from H2 headings, loading/error states
- JSON-LD TechArticle schema in page head
- Register route, SSG pre-render, nav link
- Add marked dependency to site/package.json
- Remove || true from deploy.yml case-study copy step

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## 7) Completion Sentinel

```powershell
New-Item -Path plans/phase-13-arch.DONE -ItemType File -Force
```

---

## Edge Cases and Notes

1. **Markdown XSS:** Since we control the markdown source files (committed to repo), `marked` without DOMPurify is acceptable. Do NOT add DOMPurify unless the arch spec changes to accept user-generated markdown.

2. **SSG and fetch:** During SSG pre-rendering (Node.js / server context), `fetch('/case-study/pt-BR.md')` will fail because there's no server. The component must handle this gracefully — the loading state will render in the pre-rendered HTML, and the actual markdown will load client-side via hydration. This is the expected behavior (same pattern as `useData` hook for JSON).

3. **Language toggle without page refresh:** When `i18n.language` changes, the `useMarkdownContent` hook must refetch the correct `.md` file. Use `i18n.language` as a dependency in the `useEffect`. Listen to i18n `languageChanged` event or use `useTranslation` return value.

4. **`marked` heading IDs:** Override `marked`'s renderer to add `id` attributes to H2/H3 headings. Use the `slugify` helper. This is required for TOC anchor links (`#sumario-executivo`, etc.).

5. **Existing case study content:** The current `docs/case-study/pt-BR.md` and `en-US.md` contain a phase-by-phase changelog format (Phases 03-05). The arch spec requires a complete rewrite into a narrative format with 8 specific sections. Do NOT preserve the old format — replace entirely.

6. **Reading time display:** Show reading time in the header meta area, using the `reading_time` i18n key with `{{minutes}}` interpolation.

7. **Nav overflow:** Adding a 7th nav item (`caso_de_uso`) may cause horizontal overflow on smaller desktops. The CSS should handle this — verify the nav doesn't break at 1024px width. If it overflows, consider reducing font-size or using abbreviated text. Document any visual regression for Phase 15 mobile polish.

8. **TOC on mobile:** At `max-width: 768px`, the TOC collapses from sticky sidebar to a static block above the content (not a drawer/hamburger). Per WF-10, this is the expected mobile behavior.
