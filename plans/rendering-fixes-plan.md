# Plan: Fix Rendering Errors — https://carlosduplar.github.io/eleicoes-2026-monitor/

Date: 2026-08-23
Scope: `site/` frontend only. No pipeline/backend changes.

## Goal

Eliminate client-side rendering errors on the deployed GitHub Pages site:
hydration failures (React #418/#425/#423) for returning EN users, unaccented
SEO strings in the static shell, and clarify the dead "Mercados" page.

## Investigation Summary (evidence)

Verified against live deployment (bundle `app-CBYhXlzz.js`). Local
`site/dist/index.html` differs from live HTML only by bundle hash — markup is
identical, so source-level analysis applies to production.

### Issue 1 (critical): Hydration mismatch when saved language is en-US

- `site/src/main.jsx` lines 82–93: the vite-react-ssg client callback calls
  `i18n.changeLanguage(savedLanguage)` (read from `localStorage.lang`).
- Verified in `site/node_modules/vite-react-ssg/dist/client/single-page.mjs`:
  line 43 `await fn?.(context)` executes BEFORE line 65 `hydrate(...)`.
- Result: for any visitor who previously clicked "EN", React renders the whole
  tree in English and then hydrates against Portuguese server HTML.
  - Every text node mismatches → React errors #418/#425 (and #423 when the
    mismatch breaks a boundary), console spam, flash of wrong language,
    full client re-render. This matches the symptom historically recorded in
    `WEBSITE_ISSUES_REPORT.md` §4/§5 ("URL changes but content doesn't update").
- Also affected: `applyDocumentLanguage()` mutates `<html lang>` pre-hydration
  (attribute mismatch).
- PT-only visitors are unaffected; that is why the site "looks fine" in a fresh
  browser profile.

### Issue 2 (medium): Unaccented brand/SEO strings in static shell

- `site/index.html`: `<title>Portal Eleicoes BR 2026</title>`, og:title,
  og:site_name — no accent, while runtime brand is "Portal Eleições BR 2026"
  (`site/src/locales/pt-BR/common.json` line 2).
- `site/scripts/postbuild-seo.mjs` line 5: `BRAND = 'Portal Eleicoes BR 2026'`
  plus unaccented route titles: "Quiz de Afinidade Politica",
  "Seu perfil politico", "Comparacao" (lines 67, 74, 116).
- Crawlers and no-JS users see the unaccented variants; Helmet replaces them
  only after JS boots. Inconsistent branding in SERP snippets.

### Issue 3 (user decision: wire real odds data): Mercados page is a permanent empty state

- `site/src/pages/MarketsPage.jsx` renders `t('markets.empty')`
  ("Sem dados de mercados disponíveis.") unconditionally — no data fetch at all.
- No `markets.json` exists in `site/public/data/`.
- Root cause found: `.github/workflows/collect.yml` (Collect sources step)
  already invokes `python scripts/collect_markets.py || echo "[warn] ..."` —
  but **the script does not exist** in `scripts/`. Every run swallows the
  warning, so no market data is ever produced.
- Schema already defined: `docs/schemas/types.ts` lines 250–268 (`Market`,
  `MarketsFile` → `data/markets.json` with `yes_price`/`no_price` 0–1,
  `volume`, `market_url`, `collected_at`). Shape matches Polymarket Gamma API.
- Data source verified live: Polymarket Gamma API (public, no auth) has event
  `brazil-presidential-election` (id 45915):
  `https://gamma-api.polymarket.com/events?slug=brazil-presidential-election`
  returns nested markets with `question`, `slug`, `outcomePrices`, `volume`,
  `liquidity`, `closed`, `active`.

### Issue 4 (optional / follow-up): SSG ships loading skeletons

All data-driven pages render "Carregando notícias/pesquisas/sentimento..." in
the prerendered HTML because `useData` fetches only client-side. First paint
and crawlers see placeholders. Fixing this means build-time data inlining
(vite-react-ssg `initialState`) — larger change, proposed as follow-up, not in
this fix set.

### Already fixed (no action)

Confirmed resolved since `WEBSITE_ISSUES_REPORT.md` was written:
favicon linked + 200, `useData` uses `BASE_URL`-relative paths (all data
endpoints return 200), footer links are real `<Link>`s, pt-BR locale accents
present. Double `HelmetProvider` (main.jsx + single-page.mjs) is redundant but
harmless.

## Changes

### Step 1 — Defer language restore until after hydration

Files:
- `site/src/main.jsx`

Changes:
1. Remove `i18n.changeLanguage(savedLanguage)` and `applyDocumentLanguage()`
   from the `createRoot` callback (lines 86–92). Keep i18n init at `pt-BR`.
2. Add a small post-hydration restore, e.g. inside `AppShell`
   (`site/src/App.jsx`) or a tiny `useLanguageRestore` hook mounted once:

   ```jsx
   useEffect(() => {
     const saved = normalizeLanguage(window.localStorage.getItem('lang'));
     if (saved !== i18n.language) void i18n.changeLanguage(saved);
     document.documentElement.lang = saved;
   }, []);
   ```

   Preferred placement: `useEffect` in `AppShell` (runs exactly once after
   mount, after `hydrateRoot` commits). Language flip then happens as a normal
   post-hydration update — no mismatch, brief PT flash for EN users is
   acceptable and standard for SSG i18n.
3. Keep the `languageChanged` listener for `<html lang>` sync, but register it
   inside the same effect (with cleanup), not at module scope.

### Step 2 — Accent the static shell strings

Files:
- `site/index.html` (title, description, og:title, og:site_name)
- `site/scripts/postbuild-seo.mjs` (BRAND constant and per-route title strings)

Changes:
- "Portal Eleicoes BR 2026" → "Portal Eleições BR 2026"
- "Quiz de Afinidade Politica" → "Quiz de Afinidade Política"
- "Seu perfil politico" → "Seu perfil político"
- "Comparacao" → "Comparação"
- Audit remaining literals in postbuild-seo.mjs for accents while there
  (descriptions pulled from common.json keys where possible instead of
  duplicated literals — DRY).

### Step 3 — Implement missing `collect_markets.py` + wire MarketsPage to real odds

User decision: wire real odds data (not hide nav link).

#### 3a. New file: `scripts/collect_markets.py`

Follow the existing collector pattern (`scripts/collect_polls.py`:
`ROOT_DIR`/`DATA_DIR` constants, `utc_now_iso()`, `_load_json`, atomic-ish
`json.dump(..., ensure_ascii=False)`). No new dependencies — use
`urllib.request` or the same HTTP approach collect_polls.py uses.

Behavior:
1. Fetch event + nested markets:
   `GET https://gamma-api.polymarket.com/events?slug=brazil-presidential-election`
   Event slugs kept in a module-level constant list (KISS; extendable later).
2. For each nested market where `closed == false` and `active != false`:
   - `id`: string market id
   - `slug`: market slug
   - `question`: prefer `groupItemTitle` (candidate name), fallback `question`
   - `yes_price`: `float(outcomePrices[0])` clamped to [0,1]
   - `no_price`: `float(outcomePrices[1])` clamped to [0,1]
     (`outcomePrices` arrives as array of strings)
   - `volume`: `volumeNum` if present else `float(volume or 0)`
   - `liquidity`: `liquidityNum` if present (optional field)
   - `market_url`: `https://polymarket.com/market/{slug}`
   - `collected_at`: `utc_now_iso()`
3. Write `site/public/data/markets.json` matching `MarketsFile`:
   `{ "markets": [...], "last_updated": iso, "total_count": n }`.
4. Exit 0 with empty markets list on zero results (CI warn path already
   handles failures); log a clear message when API returns nothing so the
   silent-failure mode that hid this bug cannot recur.
5. Unit test `scripts/test_collect_markets.py` mirroring
   `test_collect_polls.py` style: parse/normalize logic tested against a
   recorded Gamma API fixture (no network in tests).

#### 3b. Rewrite `site/src/pages/MarketsPage.jsx`

Mirror PollsPage/Home data patterns:
- `const { data, loading, error } = useData('markets');`
- Loading → `t('markets.loading')`; error → `t('markets.error')`;
  empty → keep existing `t('markets.empty')`.
- Render one card/row per market: question, implied probability
  (`Math.round(yes_price * 100)%`), volume formatted via
  `Intl.NumberFormat(language, { style: 'currency', currency: 'USD',
  maximumFractionDigits: 0 })`, external link (`target="_blank"`
  `rel="noopener noreferrer"`), `collected_at` shown as relative/absolute date
  rendered only after load (keeps hydration safe — no SSR/client time drift).
- Keep JSON-LD Dataset block and disclaimer paragraph.

#### 3c. i18n keys

Files: `site/src/locales/pt-BR/common.json`,
`site/src/locales/en-US/common.json` — add under `markets`:
`loading`, `error`, `yes_price` ("Probabilidade implícita" / "Implied
probability"), `volume`, `view_market`, `updated_at`. Accented pt-BR strings.

#### 3d. CI

No change needed — `.github/workflows/collect.yml` already calls the script;
it starts working once the file exists. Deploy triggers via `workflow_run`
on Collect completion (deploy.yml lines 12–15), so new `markets.json` reaches
Pages automatically. Optional hardening (separate commit): add
`markets.schema.json` under `docs/schemas/` and a check in `validate.yml`.

### Step 4 — Regression test for the hydration bug

Files:
- `qa/tests/test_home.spec.js` (extend) or new `qa/tests/test_language.spec.js`

Test:
1. `page.addInitScript` → set `localStorage.lang = 'en-US'`.
2. Load `/eleicoes-2026-monitor/`.
3. Assert: no console errors matching /Minified React error|Hydration|418|425/;
   page text contains "days to the 1st round"; nav shows EN labels.
4. Reload → same assertions (idempotent).

Run with existing config: `cd site && npx playwright test` (webServer serves
`vite preview` at `http://127.0.0.1:4173/eleicoes-2026-monitor/`; requires
`npm run build` first, and Playwright browsers installed via
`npx playwright install chromium` — not currently installed in this env).

## Risks

- Language flip timing: EN users see ~100ms of PT text before switch. Standard
  SSG tradeoff; alternative (locale-prefixed routes `/en/...`) is a bigger
  architecture change — explicitly out of scope.
- `postbuild-seo.mjs` string changes alter all static `<title>`s → harmless,
  but sitemap/RSS unaffected (they already use accented titles from feeds).
- Removing Mercados nav link changes navigation contract; keep route alive so
  old links don't 404 (GitHub Pages serves prerendered `mercados/index.html`).
  (Not applicable if Step 3 ships — nav stays.)
- `collect_markets.py` depends on an external third-party API (Polymarket).
  Failures must stay non-fatal in CI (existing `|| echo "[warn]"` pattern).
  Market prices are speculative by nature — disclaimer copy must remain
  prominent on the page.
- Rebuilding required: deployed bundle must be regenerated (`npm run build`)
  and redeployed via existing CI workflow.

## Testing Strategy

1. `python -m pytest scripts/test_collect_markets.py` — offline, fixture-based.
2. Live smoke: `python scripts/collect_markets.py` locally → inspect
   `site/public/data/markets.json` against `MarketsFile` schema.
3. `cd site && npm run build` — must succeed; inspect `dist/index.html` for
   accented titles and `dist/mercados/index.html` for prerendered content.
4. `npm run preview` + manual check with DevTools console:
   - Fresh profile PT load: zero console errors.
   - Set `localStorage.lang='en-US'`, reload: zero hydration errors, UI in EN.
   - `/mercados`: odds cards render with implied probabilities.
5. `npx playwright test` from `site/` (after `npx playwright install chromium`),
   including new language-reload regression test.
6. Post-deploy smoke: curl the four key pages + `data/markets.json`, confirm
   accented `<title>`, confirm bundle hash changed.

## Open Questions

1. Polymarket as sole odds source OK? (Betfair/PredictIt need auth or have no
   stable public API; Gamma is public and matches the existing schema.)
2. Include SSG data-inlining (Issue 4) in this pass, or defer? Recommended:
   defer — it touches every page's data flow. (User answered: defer.)
3. OK to also deduplicate SEO descriptions in postbuild-seo.mjs by importing
   locale JSON, or keep it pure-literal to avoid Node ESM/JSON import friction?
