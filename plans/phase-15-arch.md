# Phase 15 — Mobile Polish

## Objective

Audit and fix all components for the 390px mobile breakpoint. Implement the bottom navigation bar (5 items) as specified in WF-11 and WF-12. Ensure all touch targets are ≥ 44px. Make the quiz immersive (full-screen question) on mobile, restoring the nav only on the result screen.

## Input Context

- `docs/wireframes/WF-11-mobile-feed.html` — Mobile feed wireframe at 390px (open in browser)
- `docs/wireframes/WF-12-mobile-quiz.html` — Mobile quiz wireframe (open in browser)
- `docs/adr/000-wireframes.md` — Typography and layout spec
- All existing React components in `site/src/components/` and `site/src/pages/`
- `site/src/components/Nav.jsx` — Desktop nav (from Phase 04)

## Deliverables

### 1. Mobile breakpoint audit

Review all components at 390px and fix layout issues. Known targets:

| Component | Expected mobile behavior |
|-----------|--------------------------|
| `Nav.jsx` | Hidden on mobile; replaced by `BottomNav` |
| `NewsFeed.jsx` | Single-column card list, full width |
| `SentimentDashboard.jsx` | Horizontal scroll for heatmap (acceptable), toggle above |
| `PollTracker.jsx` | Chart fills full width, legend below chart |
| `CandidatePage.jsx` | Single-column layout, hero banner shrinks |
| `ComparisonPage.jsx` | Stacked (not side-by-side) candidate panels |
| `QuizEngine.jsx` | Full-screen immersive mode (see below) |
| `QuizResultCard.jsx` | Nav restored, radar chart full width |
| `MethodologyPage.jsx` | Single column, no sidebar |
| `CaseStudyPage.jsx` | TOC collapsed (hamburger toggle), single column |

CSS breakpoint convention: `@media (max-width: 768px)` for tablet, `@media (max-width: 430px)` for mobile-first 390px target.

### 2. `site/src/components/BottomNav.jsx`

Mobile bottom navigation bar — replaces the desktop `Nav` on small screens.

**Layout (WF-11):**
- Fixed to viewport bottom
- 5 items: Notícias (`/`), Sentimento (`/sentimento`), Pesquisas (`/pesquisas`), Quiz (`/quiz`), Candidatos (`/candidatos`)
- Each item: icon + label below icon
- Active item: `color: var(--brand-navy)`, icon filled
- Inactive: `color: var(--text-secondary)`, icon outlined
- Background: `var(--brand-surface)` (white), `border-top: 1px solid var(--border)`
- Height: `60px`; icon size `24px`; label `10px` Inter

**Touch target compliance:** each nav item tap area is ≥ 44×44px (padding compensation if needed).

**Icons:** use inline SVG icons (no icon library dependency). Keep icons minimal: house, chart-bar, poll-bar, quiz-bubble, person-group.

**Visibility:** render only when `window.innerWidth <= 768`. Use CSS `display: none` on desktop (`@media (min-width: 769px) { display: none; }`).

### 3. Update `App.jsx`

Add `<BottomNav />` inside the app shell. It renders itself only on mobile via CSS media query — no JavaScript visibility logic needed.

Also add bottom padding to the main content area on mobile to avoid content being hidden behind `BottomNav`:
```css
@media (max-width: 768px) {
  .main-content {
    padding-bottom: 72px;
  }
}
```

### 4. Mobile quiz — immersive question mode

During the question phase (`isComplete === false`), on mobile:
- Hide `Nav` and `BottomNav` (add a CSS class `quiz-immersive` to `<body>`)
- Question card fills full viewport height minus the progress bar
- Option cards are full-width, large touch targets (min `56px` tall)
- Progress bar at top: slim (4px), `var(--brand-navy)` fill

On result screen (`isComplete === true`):
- Remove `quiz-immersive` class from `<body>`
- `BottomNav` reappears

Implementation: `QuizEngine.jsx` calls `document.body.classList.add('quiz-immersive')` on mount and `classList.remove` on unmount or completion. `QuizResult.jsx` never adds this class.

### 5. Touch target audit

Scan all interactive elements (buttons, links, filter chips, toggles) and ensure each has `min-height: 44px` and `min-width: 44px`. Common fixes needed:
- `SourceFilter.jsx` chip buttons: add `padding: 10px 16px`
- `LanguageSwitcher.jsx`: increase tap area
- `MethodologyBadge.jsx`: ensure link area is tall enough

### 6. Viewport meta and safe areas

Verify `site/index.html` has:
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

For devices with home indicator (iPhone notch/Dynamic Island), add CSS:
```css
.bottom-nav {
  padding-bottom: env(safe-area-inset-bottom);
  height: calc(60px + env(safe-area-inset-bottom));
}
```

### 7. i18n additions

**`site/src/locales/pt-BR/common.json`** — add bottom nav labels if not already present:
```json
"bottom_nav": {
  "noticias": "Notícias",
  "sentimento": "Sentimento",
  "pesquisas": "Pesquisas",
  "quiz": "Quiz",
  "candidatos": "Candidatos"
}
```

## Constraints

- No new npm dependencies for icons — use inline SVG
- CSS-only mobile hiding of desktop Nav (no JavaScript media query listeners)
- The immersive quiz mode uses `document.body.classList` — this is the only acceptable DOM manipulation outside React's render cycle in this project
- `BottomNav` must use the same `NavLink` active detection as desktop `Nav`
- Horizontal scroll is acceptable only for the `SentimentDashboard` heatmap — all other components must fit within 390px without overflow

## Acceptance Criteria

- [ ] Desktop nav hidden at 390px; `BottomNav` visible and functional
- [ ] All 5 bottom nav items navigate to correct routes
- [ ] Active route highlighted in `BottomNav`
- [ ] `NewsFeed` renders single-column at 390px
- [ ] `SentimentDashboard` renders without horizontal overflow on 390px (heatmap may scroll)
- [ ] Quiz question is full-screen immersive on mobile (nav hidden)
- [ ] Quiz result restores nav on mobile
- [ ] All touch targets ≥ 44px (verify in Chrome DevTools > Device: iPhone SE)
- [ ] `safe-area-inset-bottom` padding applied to `BottomNav`
- [ ] `npm run build` succeeds

## Commit & Push

After all deliverables are verified:

```
git add site/src/components/BottomNav.jsx site/src/App.jsx site/src/components/ site/src/pages/ site/index.html site/src/locales/
git commit -m "feat(phase-15): Mobile polish — BottomNav, 390px breakpoints, touch targets, immersive quiz

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-15-arch.DONE`.
