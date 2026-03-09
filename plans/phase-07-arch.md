# Phase 07 — Sentiment Dashboard

## Objective

Implement `SentimentDashboard.jsx` — a heatmap visualization of candidate sentiment scores across topics and sources, with a toggle between "Por Tema" and "Por Fonte" views. Implement `MethodologyBadge.jsx` as a reusable component required in every data-driven dashboard. Follow WF-02/03 wireframes exactly.

## Input Context

- `docs/wireframes/WF-02-03-sentiment-dashboard.html` — Reference wireframe (open in browser before implementing)
- `docs/adr/000-wireframes.md` — Design tokens, typography, candidate colors
- `docs/schemas/sentiment.schema.json` — Sentiment data schema
- `data/sentiment.json` — Live data from Phase 06
- `site/src/hooks/useData.js` — Data fetching hook (from Phase 04)
- `site/src/locales/pt-BR/common.json` — Existing i18n strings
- `PLAN.md` — Candidate list with hex colors

## Deliverables

### 1. `site/src/components/MethodologyBadge.jsx`

Reusable badge for all data dashboards. Required on every component that displays AI-generated data.

**Spec:**
- Small info icon (`ⓘ`) + text: `t('methodology_badge')` → "Análise algorítmica. Não representa pesquisa eleitoral."
- Clicking the text or icon navigates to `/metodologia` (use react-router `Link`)
- Position: place below chart/table in the component, not overlaid
- Style: Inter 11px, color `var(--text-secondary)` (`#4A5568`), no border, subtle background `var(--brand-muted)`
- En-US: "Algorithmic analysis. Does not represent polling."

Add i18n key `"methodology_badge"` to both locale files if not already present.

### 2. `site/src/components/SentimentDashboard.jsx`

Heatmap dashboard with toggle.

**Data source:** `useData('sentiment')` → `data/sentiment.json`

**Toggle:** Two buttons — "Por Tema" / "By Topic" and "Por Fonte" / "By Source" — switch between `data.by_topic` and `data.by_source` views. Active button: `background: var(--brand-navy)`, text white. Inactive: outlined.

**Heatmap grid:**
- Rows: candidates (use `PLAN.md` candidate list — 9 candidates)
- Columns: topics (`by_topic` view) or source categories (`by_source` view)
- Cell: colored rectangle. Color scale:
  - Negative (< -0.3): `#FC8181` (red-ish)
  - Neutral (-0.3 to 0.3): `var(--brand-muted)` (light gray)
  - Positive (> 0.3): `#68D391` (green-ish)
- Cell value: show numeric score rounded to 1 decimal (e.g. `0.3`) in small text
- Missing data (candidate has no score for that topic): render as empty gray cell with `—`

**Candidate row header:**
- Small colored circle using candidate hex from design tokens
- Candidate name

**States:**
- Loading: skeleton grid (CSS animation)
- Empty: "Sem dados de sentimento disponíveis." / "No sentiment data available."
- Error: "Erro ao carregar sentimento." / "Error loading sentiment."

**MethodologyBadge:** rendered below the heatmap grid.

**Disclaimer:** render `data.disclaimer_pt` (or `data.disclaimer_en`) as a visible note below the toggle, in italics, `var(--text-secondary)`.

### 3. `site/src/pages/SentimentPage.jsx`

Page wrapper (replacing Phase 04 placeholder):
- `<Helmet>`: title "Sentimento dos Candidatos | Portal Eleições BR 2026", JSON-LD `Dataset`
- `<SentimentDashboard />`
- Route: `/sentimento`

### 4. i18n additions

**`site/src/locales/pt-BR/common.json`** — add keys:
```json
"sentiment": {
  "title": "Sentimento dos Candidatos",
  "by_topic": "Por Tema",
  "by_source": "Por Fonte",
  "loading": "Carregando sentimento...",
  "empty": "Sem dados de sentimento disponíveis.",
  "error": "Erro ao carregar sentimento.",
  "disclaimer_label": "Nota metodológica:"
}
```

**`site/src/locales/en-US/common.json`** — English equivalents.

### 5. Candidate color map `site/src/utils/candidateColors.js`

Export a static map for use in all candidate-colored components:
```javascript
export const CANDIDATE_COLORS = {
  'lula':             '#CC0000',
  'flavio-bolsonaro': '#002776',
  'tarcisio':         '#1A3A6B',
  'caiado':           '#FF8200',
  'zema':             '#FF6600',
  'ratinho-jr':       '#0066CC',
  'eduardo-leite':    '#4488CC',
  'aldo-rebelo':      '#5C6BC0',
  'renan-santos':     '#26A69A',
};
```

This utility will be reused in Phase 08, 11, 12.

## Constraints

- No Tailwind, no CSS-in-JS — plain CSS with custom properties
- `MethodologyBadge` must be exported from `components/MethodologyBadge.jsx` and imported wherever displayed
- Loading/empty/error states are mandatory for `SentimentDashboard`
- The heatmap must render correctly at 1280px desktop (WF-02/03) and degrade gracefully on mobile (horizontal scroll is acceptable for the heatmap at 390px)
- `sentiment.json` may have missing candidates or topics — component must handle sparse data without crashing
- All UI strings through `react-i18next` — zero hardcoded strings in JSX

## Acceptance Criteria

- [ ] `SentimentDashboard` renders at `/sentimento` with heatmap grid
- [ ] Toggle switches between "Por Tema" and "Por Fonte" views
- [ ] Candidate rows show colored circles matching `CANDIDATE_COLORS`
- [ ] Cells are color-coded by sentiment score
- [ ] `MethodologyBadge` renders below the heatmap and links to `/metodologia`
- [ ] `disclaimer_pt`/`disclaimer_en` from `sentiment.json` is displayed
- [ ] Loading state visible while `useData` is fetching
- [ ] Empty state renders when `sentiment.json` has no data
- [ ] Language toggle switches all text to en-US
- [ ] `npm run build` succeeds with no errors

## Commit & Push

After all deliverables are verified:

```
git add site/src/components/SentimentDashboard.jsx site/src/components/MethodologyBadge.jsx site/src/pages/SentimentPage.jsx site/src/utils/candidateColors.js site/src/locales/
git commit -m "feat(phase-07): SentimentDashboard heatmap + MethodologyBadge

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-07-arch.DONE`.
