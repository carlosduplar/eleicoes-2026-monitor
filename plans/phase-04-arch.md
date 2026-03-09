# Phase 04 — Frontend MVP

## Objective

Scaffold the React + Vite + vite-plugin-ssg frontend with bilingual support, app shell, routing, and the first data-driven component (NewsFeed). Follow WF-01 wireframe for layout.

## Input Context

- `docs/wireframes/WF-01-feed-desktop.html` — Feed desktop wireframe (reference layout)
- `docs/wireframes/WF-11-mobile-feed.html` — Mobile feed wireframe (responsive reference)
- `docs/adr/000-wireframes.md` — Design tokens, typography, navigation spec
- `docs/adr/003-i18n-strategy.md` — i18n strategy and locale structure
- `docs/schemas/articles.schema.json` — Article data schema
- `docs/schemas/types.ts` — TypeScript types (reference for prop types)
- `data/articles.json` — Seed data from Phase 03

## Deliverables

### 1. `site/package.json`

Initialize with:

```
react, react-dom
vite, @vitejs/plugin-react
vite-plugin-ssg (or vite-ssg)
react-router-dom
react-i18next, i18next, i18next-http-backend
react-helmet-async
recharts
```

Run `npm install` after creating package.json.

### 2. `site/vite.config.js`

Configure Vite with:
- React plugin
- vite-plugin-ssg for static site generation
- Alias `@/` to `src/`
- Dev server proxying `/data/` to repo root `data/`

### 3. Locale Files

**`site/src/locales/pt-BR/common.json`:**
```json
{
  "brand": "Portal Eleicoes BR 2026",
  "nav": {
    "noticias": "Noticias",
    "sentimento": "Sentimento",
    "pesquisas": "Pesquisas",
    "candidatos": "Candidatos",
    "quiz": "Quiz",
    "metodologia": "Metodologia"
  },
  "countdown": {
    "days_to_first_round": "{{days}} dias para o 1.o turno",
    "date": "4 de outubro de 2026"
  },
  "feed": {
    "loading": "Carregando noticias...",
    "empty": "Nenhuma noticia disponivel.",
    "error": "Erro ao carregar noticias.",
    "analysis_in_progress": "Analise em andamento",
    "validated": "Validado",
    "curated": "Destaque da Redacao",
    "updated_ago": "Atualizado ha {{minutes}} min"
  },
  "methodology_badge": "Analise algoritmica. Nao representa pesquisa eleitoral.",
  "language": { "pt": "PT", "en": "EN" }
}
```

**`site/src/locales/en-US/common.json`:** (English equivalents)

### 4. Components

**`site/src/components/Nav.jsx`:**
- Logo: "Portal Eleicoes BR 2026" (left-aligned)
- 6 nav items: Noticias, Sentimento, Pesquisas, Candidatos, Quiz, Metodologia
- Active item: font-weight 600, 2px gold underline (`#B8961E`), color `#1A2E4A`
- Language toggle `PT | EN` (right-aligned)
- Background: white with `border-bottom: 1px solid #E2E8F0`
- Uses react-router-dom `NavLink` for active state
- Uses react-i18next for labels

**`site/src/components/CountdownTimer.jsx`:**
- Full-width bar below nav
- Background: `#1A2E4A`, text: white, Inter 400 13px
- Calculates days until 2026-10-04
- Format: "📅 {{days}} dias para o 1.o turno · 4 de outubro de 2026"

**`site/src/components/LanguageSwitcher.jsx`:**
- Compact `PT | EN` toggle
- PT active by default (underlined)
- Calls `i18next.changeLanguage()`

**`site/src/components/NewsFeed.jsx`:**
- Reads from `/data/articles.json` via `useData` hook
- Three states: loading, empty, error (per wireframe)
- Card layout matching WF-01: image placeholder, title, source, time, category badge
- Status badges per article status:
  - `raw`: amber "Em apuracao" badge
  - `validated`: green checkmark badge
  - `curated`: gold "Destaque da Redacao" badge
- MethodologyBadge below data components

**`site/src/components/MethodologyBadge.jsx`:**
- Text: "Analise algoritmica. Nao representa pesquisa eleitoral."
- Links to `/metodologia`
- Inter 400, 11px, color `#4A5568`

**`site/src/components/SourceFilter.jsx`:**
- Horizontal filter chips: All, Mainstream, Politics, Magazine, International, Institutional
- Filters articles by `source.category`

### 5. Hooks

**`site/src/hooks/useData.js`:**
- Fetches JSON from `/data/{filename}.json`
- Returns `{ data, loading, error }`
- Caches in memory to avoid re-fetches

### 6. Pages

**`site/src/pages/Home.jsx`:**
- Layout: 70% main (NewsFeed) + 30% sidebar (placeholder widgets)
- Matches WF-01 wireframe layout
- SourceFilter above NewsFeed

**Placeholder pages (route only, minimal content):**
- `SentimentPage.jsx` — `/sentimento` — "Coming in Phase 7"
- `PollsPage.jsx` — `/pesquisas` — "Coming in Phase 8"
- `CandidatesPage.jsx` — `/candidatos` — "Coming in Phase 12"
- `QuizPage.jsx` — `/quiz` — "Coming in Phase 11"
- `MethodologyPage.jsx` — `/metodologia` — "Coming in Phase 10"

### 7. App Shell

**`site/src/App.jsx`:**
- `<Nav />` + `<CountdownTimer />` + `<Routes>` + Footer
- React Router with all routes defined

**`site/src/main.jsx`:**
- i18next initialization (pt-BR default, en-US fallback)
- React helmet provider
- Router wrapper

**`site/index.html`:**
- Meta tags: viewport, charset, description
- RSS autodiscovery links
- Open Graph tags (pt-BR default)

### 8. Styles

Use CSS custom properties matching the design tokens from ADR 000:

```css
:root {
  --brand-navy: #1A2E4A;
  --brand-gold: #B8961E;
  --brand-bg: #F5F7FA;
  --brand-surface: #FFFFFF;
  --brand-muted: #EDF2F7;
  --text-primary: #1A202C;
  --text-secondary: #4A5568;
  --status-raw: #F6AD55;
  --status-valid: #48BB78;
  --status-curated: #B8961E;
}
```

Typography: Georgia serif for H1, Inter for everything else. See ADR 000 for full type scale.

## Constraints

- No Tailwind, no CSS-in-JS — plain CSS with custom properties
- No TypeScript in site/ (plain JSX) — types.ts is reference only
- Follow WF-01 layout faithfully: 70/30 split, card-based feed, sidebar
- All text via i18next (no hardcoded strings except technical labels)
- Loading/empty/error states required for every data-driven component
- `npm run build` must produce valid static HTML in `site/dist/`
- `npm run dev` must serve the app on localhost with hot reload

## Acceptance Criteria

- [ ] `cd site && npm install` succeeds
- [ ] `cd site && npm run dev` starts dev server
- [ ] `cd site && npm run build` produces `dist/` with static HTML
- [ ] Homepage renders NewsFeed with articles from `data/articles.json`
- [ ] Language toggle switches between pt-BR and en-US
- [ ] CountdownTimer shows correct days until 2026-10-04
- [ ] Nav highlights active route
- [ ] All 6 routes resolve without 404
- [ ] SourceFilter filters articles by category
- [ ] Status badges render correctly for raw/validated/curated articles
- [ ] Mobile responsive (390px breakpoint per WF-11)

## Sentinel

When complete, create `plans/phase-04-arch.DONE`.
