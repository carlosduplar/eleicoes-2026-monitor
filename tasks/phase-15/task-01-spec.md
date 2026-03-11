# Phase 15 — Task 01 Spec (Mobile Polish: BottomNav, 390px Breakpoints, Touch Targets, Immersive Quiz)

> Planner: Opus 4.6 | Implementor: Codex | Date: 2026-03-11

---

## Inputs and Mandatory References

| # | Ref | Path | Why |
|---|-----|------|-----|
| 1 | Arch spec | `plans/phase-15-arch.md` | Full Phase 15 deliverables, acceptance criteria, constraints |
| 2 | WF-11 wireframe | `docs/wireframes/WF-11-mobile-feed.html` | Mobile feed layout at 390px — bottom nav 5 items, card list, sticky header |
| 3 | WF-12 wireframe | `docs/wireframes/WF-12-mobile-quiz.html` | Mobile quiz — immersive question + result layout |
| 4 | ADR 000 | `docs/adr/000-wireframes.md` | Design tokens, typography, CSS custom properties |
| 5 | TypeScript types | `docs/schemas/types.ts` | Shared types (no schema changes for Phase 15) |
| 6 | App shell | `site/src/App.jsx` | Current `AppShell` layout: `<Nav />` + `<CountdownTimer />` + `<main>` + `<footer>` |
| 7 | Desktop Nav | `site/src/components/Nav.jsx` | `navItems` array, `NavLink` pattern, CSS class `.top-nav` |
| 8 | QuizEngine | `site/src/components/QuizEngine.jsx` | Quiz question component — needs immersive body class logic |
| 9 | QuizPage | `site/src/pages/QuizPage.jsx` | Uses `useQuiz` hook, renders `QuizEngine` or `QuizResultCard` based on `isComplete` |
| 10 | QuizResult page | `site/src/pages/QuizResult.jsx` | Shared-link result page — must never add immersive class |
| 11 | QuizResultCard | `site/src/components/QuizResultCard.jsx` | Radar chart + ranking — nav restores on result |
| 12 | SourceFilter | `site/src/components/SourceFilter.jsx` | Filter chip buttons — touch target < 44px currently |
| 13 | LanguageSwitcher | `site/src/components/LanguageSwitcher.jsx` | Lang buttons — touch target < 44px currently |
| 14 | MethodologyBadge | `site/src/components/MethodologyBadge.jsx` | Info link — touch target < 44px currently |
| 15 | Styles | `site/src/styles.css` | 1532 lines, existing `@media (max-width: 390px)` blocks at L1107 and L1523 |
| 16 | index.html | `site/index.html` | Viewport meta — missing `viewport-fit=cover` |
| 17 | pt-BR common | `site/src/locales/pt-BR/common.json` | Existing nav keys — needs `bottom_nav.*` keys |
| 18 | en-US common | `site/src/locales/en-US/common.json` | English nav — needs `bottom_nav.*` keys |
| 19 | package.json | `site/package.json` | Build/dev commands, no new dependencies allowed |

---

## 1) Files to Create or Modify

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `site/src/components/BottomNav.jsx` | **CREATE** | Mobile bottom navigation bar — 5 items with inline SVG icons, `NavLink` active detection, CSS-only visibility via media query. Fixed to viewport bottom, 60px height + safe area padding. |
| 2 | `site/src/App.jsx` | **MODIFY** | Import and render `<BottomNav />` inside `AppShell` after `<footer>`. Add `main-content` class to the `<main>` element for bottom padding targeting. |
| 3 | `site/src/pages/QuizPage.jsx` | **MODIFY** | Add `useEffect` to toggle `quiz-immersive` class on `document.body` when quiz is active (`!isComplete`) and on mobile. Remove class on completion or unmount. |
| 4 | `site/src/styles.css` | **MODIFY** | Add: (a) `.bottom-nav` styles with safe-area padding, (b) desktop `Nav` hiding at 768px, (c) `body.quiz-immersive` rules hiding nav/footer, (d) touch target minimums for all interactive elements, (e) mobile breakpoint fixes for all components listed in arch spec. |
| 5 | `site/index.html` | **MODIFY** | Update viewport meta to include `viewport-fit=cover`. |
| 6 | `site/src/locales/pt-BR/common.json` | **MODIFY** | Add `bottom_nav` object with 5 keys: `noticias`, `sentimento`, `pesquisas`, `quiz`, `candidatos`. |
| 7 | `site/src/locales/en-US/common.json` | **MODIFY** | Add `bottom_nav` object with 5 keys (English labels). |

---

## 2) Function Signatures and Types per File

### 2.1 `site/src/components/BottomNav.jsx` — CREATE

```jsx
// Imports
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

// --- Inline SVG icon components (no icon library) ---

/** House icon for Noticias/Home */
function IconHome() {
  // Returns <svg> element, 24x24, viewBox="0 0 24 24", stroke="currentColor", fill="none"
  // Minimal house outline: roof triangle + body rectangle
}

/** Bar chart icon for Sentimento */
function IconSentiment() {
  // Returns <svg> 24x24, 3 vertical bars of different heights
}

/** Poll bars icon for Pesquisas */
function IconPolls() {
  // Returns <svg> 24x24, horizontal bar chart (3 horizontal bars)
}

/** Speech bubble icon for Quiz */
function IconQuiz() {
  // Returns <svg> 24x24, rounded speech bubble with question mark
}

/** People group icon for Candidatos */
function IconCandidates() {
  // Returns <svg> 24x24, two person silhouettes
}

// --- Navigation items config ---
/** @type {Array<{ to: string, key: string, Icon: () => JSX.Element, end?: boolean }>} */
const bottomNavItems = [
  { to: '/', key: 'noticias', Icon: IconHome, end: true },
  { to: '/sentimento', key: 'sentimento', Icon: IconSentiment },
  { to: '/pesquisas', key: 'pesquisas', Icon: IconPolls },
  { to: '/quiz', key: 'quiz', Icon: IconQuiz },
  { to: '/candidatos', key: 'candidatos', Icon: IconCandidates },
];

/**
 * Mobile bottom navigation bar.
 * - Renders 5 items: icon + label.
 * - Uses NavLink for active route detection (same pattern as desktop Nav).
 * - Visibility controlled purely by CSS: hidden at min-width 769px.
 * - Each item tap area >= 44x44px.
 *
 * @returns {JSX.Element}
 */
function BottomNav() {
  const { t } = useTranslation('common');

  return (
    <nav className="bottom-nav" aria-label={t('nav.aria_label')}>
      {bottomNavItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `bottom-nav-item ${isActive ? 'bottom-nav-item--active' : ''}`
          }
        >
          <item.Icon />
          <span className="bottom-nav-label">{t(`bottom_nav.${item.key}`)}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export default BottomNav;
```

**Key constraints:**
- 5 inline SVG icons (no icon library dependency)
- Each SVG: `width="24" height="24"`, `aria-hidden="true"`
- `NavLink` with `end` prop on home route (same as desktop `Nav`)
- Translation keys from `common` namespace: `bottom_nav.noticias`, etc.
- No JavaScript-based visibility toggle — CSS only

---

### 2.2 `site/src/App.jsx` — MODIFY

Changes to `AppShell`:

```jsx
// Add import at top:
import BottomNav from './components/BottomNav';

// Modify AppShell return JSX:
function AppShell() {
  const { t } = useTranslation('common');

  return (
    <div className="app-shell">
      <Helmet>
        <title>{t('brand')}</title>
        <meta name="description" content={t('meta.description')} />
      </Helmet>
      <Nav />
      <CountdownTimer />
      {/* Add className "main-content" to main for mobile padding-bottom */}
      <main className="container app-main main-content">
        <Outlet />
      </main>
      <footer className="site-footer">
        {/* ... existing footer unchanged ... */}
      </footer>
      {/* BottomNav renders after footer; CSS positions it fixed at bottom */}
      <BottomNav />
    </div>
  );
}
```

**Exact changes:**
1. Add `import BottomNav from './components/BottomNav';` after existing imports
2. Add `main-content` to the `<main>` element's className: `"container app-main main-content"`
3. Add `<BottomNav />` as the last child of `<div className="app-shell">`, after `</footer>`

---

### 2.3 `site/src/pages/QuizPage.jsx` — MODIFY

Add `useEffect` for immersive quiz mode:

```jsx
// Add useEffect to existing import from 'react':
import { useEffect } from 'react';  // (already imports from 'react' but may not have useEffect)

// Inside QuizPage function body, after the useQuiz() call:

useEffect(() => {
  if (isComplete) {
    document.body.classList.remove('quiz-immersive');
    return;
  }
  document.body.classList.add('quiz-immersive');
  return () => {
    document.body.classList.remove('quiz-immersive');
  };
}, [isComplete]);
```

**Rules:**
- When `isComplete === false` (question phase): add `quiz-immersive` to `document.body.classList`
- When `isComplete === true` (result phase): remove `quiz-immersive`
- On unmount (navigating away): always remove `quiz-immersive`
- `QuizResult.jsx` (the shared-link result page) must NOT be modified — it never adds this class

---

### 2.4 `site/src/styles.css` — MODIFY

Append the following CSS blocks **after the existing last line (L1532)**. Do NOT modify existing rules unless explicitly noted below.

#### 2.4.1 Bottom Nav Base Styles

```css
/* --- Bottom Nav (Phase 15) --- */

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: calc(60px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--brand-surface);
  border-top: 1px solid var(--border);
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
  padding: 6px 8px;
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 10px;
  font-family: Inter, system-ui, sans-serif;
  gap: 2px;
  -webkit-tap-highlight-color: transparent;
}

.bottom-nav-item svg {
  width: 24px;
  height: 24px;
}

.bottom-nav-label {
  font-size: 10px;
  line-height: 1.2;
}

.bottom-nav-item--active {
  color: var(--brand-navy);
}

/* Hide bottom nav on desktop */
@media (min-width: 769px) {
  .bottom-nav {
    display: none;
  }
}
```

#### 2.4.2 Hide Desktop Nav on Mobile

```css
/* Hide desktop nav on mobile, show bottom nav */
@media (max-width: 768px) {
  .top-nav {
    display: none;
  }

  .main-content {
    padding-bottom: 72px;
  }
}
```

#### 2.4.3 Immersive Quiz Mode

```css
/* Immersive quiz: hide nav/footer when body has this class */
body.quiz-immersive .top-nav,
body.quiz-immersive .bottom-nav,
body.quiz-immersive .countdown-bar,
body.quiz-immersive .site-footer {
  display: none;
}

body.quiz-immersive .main-content {
  padding-bottom: 0;
}

/* On mobile: quiz fills viewport */
@media (max-width: 768px) {
  body.quiz-immersive .app-main {
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    padding-top: 0;
  }

  body.quiz-immersive .quiz-progress {
    height: 4px;
    margin-bottom: 1rem;
  }

  body.quiz-immersive .quiz-option-card {
    min-height: 56px;
    font-size: 0.95rem;
    padding: 1rem;
  }

  body.quiz-immersive .quiz-next-btn {
    min-height: 56px;
    font-size: 1rem;
    margin-top: auto;
  }
}
```

#### 2.4.4 Touch Target Audit Fixes

```css
/* Touch target compliance: all interactive elements >= 44px (Phase 15) */
@media (max-width: 768px) {
  .source-filter-button {
    min-height: 44px;
    min-width: 44px;
    padding: 10px 16px;
  }

  .lang-button {
    min-height: 44px;
    min-width: 44px;
    padding: 10px 12px;
  }

  .methodology-badge {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    padding: 8px 12px;
  }

  .quiz-option-card {
    min-height: 56px;
  }

  .quiz-next-btn {
    min-height: 48px;
  }

  .quiz-restart-btn {
    min-height: 48px;
  }

  .quiz-share-btn {
    min-height: 48px;
  }

  .sentiment-toggle {
    min-height: 44px;
    padding: 10px 16px;
  }

  .top-link {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
  }
}
```

#### 2.4.5 Component-Specific Mobile Fixes (430px and 390px)

```css
/* Mobile component layout fixes (Phase 15) */
@media (max-width: 430px) {
  /* NewsFeed: single-column, full width cards */
  .feed-card {
    grid-template-columns: 1fr;
  }

  .feed-card-content h3 {
    font-size: 1rem;
  }

  /* PollTracker: chart full width, legend below */
  .recharts-wrapper {
    width: 100% !important;
  }

  /* CandidatePage: single column, hero shrinks */
  .candidate-layout {
    grid-template-columns: 1fr;
  }

  .candidate-hero img {
    max-height: 200px;
    object-fit: cover;
  }

  /* ComparisonPage: stacked panels, not side-by-side */
  .comparison-hero-grid {
    grid-template-columns: 1fr;
  }

  .comparison-topic-columns {
    grid-template-columns: 1fr;
  }

  /* MethodologyPage: single column, no sidebar feel */
  .methodology-page {
    max-width: 100%;
    padding: 0 0.5rem;
  }

  /* CaseStudyPage: collapsed TOC */
  .case-study-layout {
    grid-template-columns: 1fr;
  }

  .case-study-toc {
    position: static;
    margin-bottom: 1rem;
  }

  /* SentimentDashboard: heatmap horizontal scroll is OK */
  .sentiment-table-container {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
}
```

#### 2.4.6 Modification to EXISTING Rule (L1107)

In the existing `@media (max-width: 390px)` block starting at line 1107, update the `.source-filter-button` rule to ensure touch target compliance:

**Current (L1113-1114):**
```css
  .source-filter-button {
    font-size: 11px;
    padding: 0.2rem 0.65rem;
  }
```

**Replace with:**
```css
  .source-filter-button {
    font-size: 11px;
    padding: 10px 12px;
    min-height: 44px;
  }
```

---

### 2.5 `site/index.html` — MODIFY

**Current (line 5):**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
```

**Replace with:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

---

### 2.6 `site/src/locales/pt-BR/common.json` — MODIFY

Add `bottom_nav` object as a new top-level key (after `"nav"` block, before `"countdown"`):

```json
"bottom_nav": {
  "noticias": "Noticias",
  "sentimento": "Sentimento",
  "pesquisas": "Pesquisas",
  "quiz": "Quiz",
  "candidatos": "Candidatos"
}
```

---

### 2.7 `site/src/locales/en-US/common.json` — MODIFY

Add `bottom_nav` object as a new top-level key (same position):

```json
"bottom_nav": {
  "noticias": "News",
  "sentimento": "Sentiment",
  "pesquisas": "Polls",
  "quiz": "Quiz",
  "candidatos": "Candidates"
}
```

---

## 3) Data Contract Notes

Phase 15 does **not** modify any `docs/schemas/*.schema.json` files. No new data contracts. All changes are purely frontend (components, CSS, i18n UI strings).

The following existing schemas remain unchanged and are not consumed by new files:
- `articles.schema.json` — consumed by `NewsFeed.jsx` (no changes to data contract)
- `quiz.schema.json` — consumed by `QuizEngine.jsx` / `QuizPage.jsx` (no changes to data contract)
- `sentiment.schema.json` — consumed by `SentimentDashboard.jsx` (no changes)
- `polls.schema.json` — consumed by `PollTracker.jsx` (no changes)
- `candidates.schema.json` — consumed by `CandidatePage.jsx`, `ComparisonPage.jsx` (no changes)

The `BottomNav.jsx` component does NOT fetch or consume any JSON data files. It only uses i18n translation keys from `common.json`.

---

## 4) Step-by-Step Implementation Order

### Step 1: Update `site/index.html` viewport meta
- Change viewport meta to include `viewport-fit=cover`
- **Dependency:** None
- **Verify:** Open file, confirm `viewport-fit=cover` is present

### Step 2: Add i18n keys to both locale files
- Add `bottom_nav` object to `site/src/locales/pt-BR/common.json`
- Add `bottom_nav` object to `site/src/locales/en-US/common.json`
- **Dependency:** None
- **Verify:** JSON files parse without errors: `node -e "JSON.parse(require('fs').readFileSync('site/src/locales/pt-BR/common.json','utf8'))"`

### Step 3: Create `site/src/components/BottomNav.jsx`
- Create component with 5 inline SVG icons, `NavLink` active detection, i18n labels
- Follow the function signatures in Section 2.1 exactly
- **Dependency:** Step 2 (i18n keys must exist)
- **Verify:** File exists, imports resolve

### Step 4: Modify `site/src/App.jsx`
- Import `BottomNav`
- Add `main-content` class to `<main>` element
- Render `<BottomNav />` as last child of `.app-shell`
- **Dependency:** Step 3 (component must exist)
- **Verify:** `npm run build` in `site/` directory

### Step 5: Modify `site/src/pages/QuizPage.jsx` for immersive mode
- Add `useEffect` to toggle `quiz-immersive` body class based on `isComplete`
- Cleanup on unmount
- **Dependency:** None (can parallelize with Steps 3-4 but builds depend on Step 4)
- **Verify:** Component renders without errors

### Step 6: Append all CSS to `site/src/styles.css`
- Append Bottom Nav base styles (Section 2.4.1)
- Append desktop nav hiding at 768px (Section 2.4.2)
- Append immersive quiz rules (Section 2.4.3)
- Append touch target fixes (Section 2.4.4)
- Append mobile component layout fixes at 430px (Section 2.4.5)
- Modify existing 390px `.source-filter-button` rule at L1113 (Section 2.4.6)
- **Dependency:** None (CSS is independent, but test after Step 4)
- **Verify:** No CSS syntax errors, `npm run build` succeeds

### Step 7: Final build verification
- Run `npm run build` from `site/` directory
- Confirm zero errors, zero warnings related to Phase 15 changes
- **Dependency:** All previous steps

---

## 5) Test and Verification Commands

All commands assume PowerShell 7 and CWD is the project root (`C:\projects\eleicoes-2026-monitor`).

### 5.1 JSON locale validation

```powershell
node -e "JSON.parse(require('fs').readFileSync('site/src/locales/pt-BR/common.json','utf8')); console.log('pt-BR OK')"
node -e "JSON.parse(require('fs').readFileSync('site/src/locales/en-US/common.json','utf8')); console.log('en-US OK')"
```

### 5.2 Verify i18n keys exist

```powershell
node -e "const j=JSON.parse(require('fs').readFileSync('site/src/locales/pt-BR/common.json','utf8')); const keys=['noticias','sentimento','pesquisas','quiz','candidatos']; keys.forEach(k=>{if(!j.bottom_nav[k])throw new Error('Missing: bottom_nav.'+k)}); console.log('All bottom_nav keys present')"
```

### 5.3 Verify BottomNav file exists and exports default

```powershell
Test-Path site/src/components/BottomNav.jsx
```

### 5.4 Verify viewport meta

```powershell
Select-String -Path site/index.html -Pattern 'viewport-fit=cover'
```

### 5.5 Verify quiz-immersive in QuizPage

```powershell
Select-String -Path site/src/pages/QuizPage.jsx -Pattern 'quiz-immersive'
```

### 5.6 Verify BottomNav imported in App.jsx

```powershell
Select-String -Path site/src/App.jsx -Pattern 'BottomNav'
```

### 5.7 Verify CSS contains bottom-nav rules

```powershell
Select-String -Path site/src/styles.css -Pattern '\.bottom-nav\b'
```

### 5.8 Verify touch target minimums in CSS

```powershell
Select-String -Path site/src/styles.css -Pattern 'min-height:\s*44px'
```

### 5.9 Full build

```powershell
Push-Location site; npm run build; Pop-Location
```

### 5.10 Verify no new dependencies added

```powershell
git diff site/package.json
# Expected: no changes to dependencies or devDependencies
```

---

## 6) Git Commit

After all deliverables pass verification:

```powershell
git add site/src/components/BottomNav.jsx site/src/App.jsx site/src/pages/QuizPage.jsx site/src/styles.css site/index.html site/src/locales/pt-BR/common.json site/src/locales/en-US/common.json
git commit -m "feat(phase-15): Mobile polish — BottomNav, 390px breakpoints, touch targets, immersive quiz

- Create BottomNav component with 5 inline SVG icons and NavLink active detection
- Hide desktop Nav on mobile (CSS-only), show BottomNav fixed at viewport bottom
- Add quiz-immersive body class for full-screen question mode on mobile
- Ensure all touch targets >= 44px (source filters, lang switcher, methodology badge)
- Add viewport-fit=cover for safe-area-inset-bottom on notch devices
- Add bottom_nav i18n keys for pt-BR and en-US
- Fix 390px/430px breakpoints for all data components

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

---

## 7) Completion Sentinel

After commit and push:

```powershell
New-Item -Path plans/phase-15-arch.DONE -ItemType File -Force
```

---

## Acceptance Criteria Checklist

From `plans/phase-15-arch.md`:

- [ ] Desktop nav hidden at 390px; `BottomNav` visible and functional
- [ ] All 5 bottom nav items navigate to correct routes (`/`, `/sentimento`, `/pesquisas`, `/quiz`, `/candidatos`)
- [ ] Active route highlighted in `BottomNav` (navy color via `--brand-navy`)
- [ ] `NewsFeed` renders single-column at 390px
- [ ] `SentimentDashboard` renders without horizontal overflow on 390px (heatmap may scroll)
- [ ] Quiz question is full-screen immersive on mobile (nav hidden via `body.quiz-immersive`)
- [ ] Quiz result restores nav on mobile (class removed on `isComplete === true` and on unmount)
- [ ] All touch targets >= 44px (source-filter-button, lang-button, methodology-badge, quiz buttons, sentiment toggles)
- [ ] `safe-area-inset-bottom` padding applied to `.bottom-nav`
- [ ] `npm run build` succeeds with zero errors

---

## Constraints Reminder

- **No new npm dependencies** — inline SVG icons only, no icon library
- **CSS-only** desktop Nav hiding — no `window.matchMedia` or JS media query listeners
- **`document.body.classList`** is the ONLY acceptable DOM manipulation outside React's render cycle (used in `QuizPage.jsx` for immersive mode)
- **`BottomNav`** must use `NavLink` from `react-router-dom` — same active detection pattern as desktop `Nav`
- **Horizontal scroll** is acceptable ONLY for the `SentimentDashboard` heatmap table — all other components must fit within 390px without horizontal overflow
