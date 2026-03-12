# Website Inspection Report: https://carlosduplar.github.io/eleicoes-2026-monitor/

## Summary

The website has several critical issues that prevent it from functioning properly. Below is a detailed list of all findings.

---

## 1. Missing Resources (404 Errors)

### 1.1 favicon.ico
- **Issue**: Request to `/favicon.ico` returns 404
- **Location**: Browser console shows: `[ERROR] Failed to load resource: the server responded with a status of 404 () @ https://carlosduplar.github.io/favicon.ico:0`
- **Root cause**: No `<link rel="icon">` tag in `site/index.html`, and no favicon file in the public directory

### 1.2 Data Fetch Path Issue
- **Issue**: Request to `/data/articles.json` returns 404
- **Location**: Browser console shows: `[ERROR] Failed to load resource: the server responded with a status of 404 () @ https://carlosduplar.github.io/data/articles.json:0`
- **Root cause**: The `useData` hook (`site/src/hooks/useData.js:23`) fetches from `/data/${filename}.json` instead of `/eleicoes-2026-monitor/data/${filename}.json`
- **Note**: The data IS available at the correct path (`https://carlosduplar.github.io/eleicoes-2026-monitor/data/articles.json` works when accessed directly)

---

## 2. Stub Content Displayed

Despite implementation being complete, the following sections show stub messages:

### 2.1 Latest Poll
- **Displayed text**: "The full poll widget arrives in Phase 8 with institute data." / "Componente completo chega na Fase 8 com dados de institutos."
- **Location**: Sidebar on home page

### 2.2 Affinity Quiz
- **Displayed text**: "Quiz engine and results arrive in Phase 11." / "Motor de quiz e resultado entram na Fase 11."
- **Location**: Sidebar on home page

### 2.3 Candidate Profiles
- **Displayed text**: "Full candidate profiles and comparisons arrive in Phase 12." / "Perfis completos e comparacoes entram na Fase 12."
- **Location**: Sidebar on home page

---

## 3. Portuguese Text - Missing Accents

The following translation files have improper or missing Portuguese accentuation:

### 3.1 `site/src/locales/pt-BR/common.json`
Missing accents in:
- "Eleicoes" should be "Eleicoes" (brand)
- "Navegacao" should be "Navegação"
- "Noticias" should be "Noticias"
- "disponivel" should be "disponivel"
- "ultima" should be "ultima"
- "comparacoes" should be "comparacoes"
- "indisponivel" should be "indisponivel"
- And many more throughout the file

### 3.2 `site/src/locales/pt-BR/case-study.json`
Missing accents in:
- "construimos" should be "construimos"
- "multiplos" should be "multiplos"
- "indisponivel" should be "indisponivel"
- "Eleicoes" should be "Eleicoes"
- "Conteudo" should be "Conteudo"
- "Sumario" should be "Sumario"
- "Decisoes" should be "Decisoes"
- "Licoes" should be "Licoes"
- "Numeros" should be "Numeros"
- "Proximos" should be "Proximos"

### 3.3 `site/src/locales/pt-BR/candidates.json`
Missing accents in:
- "nao" (multiple instances)
- "disponiveis" (multiple instances)
- "comparacao" (multiple instances)
- "Posicoes" should be "Posicoes"
- "Posicao" should be "Posicao"

### Note: `site/src/locales/pt-BR/methodology.json` appears to have proper accents.

---

## 4. React Console Errors

The following errors appear in the browser console:

### Error #425
- **Message**: "Minified React error #425"
- **Frequency**: Multiple occurrences (6 times)
- **URL**: `app-CikwzX5k.js:6:68`

### Error #418
- **Message**: "Minified React error #418"
- **Frequency**: Multiple occurrences (7 times)
- **URL**: `app-CikwzX5k.js:6:4926`

### Error #423
- **Message**: "Minified React error #423"
- **Frequency**: Single occurrence
- **URL**: `app-CikwzX5k.js:8:45832`

**Impact**: These errors prevent proper page rendering. Navigation links change the URL but the page content does not update - the home page content persists even when navigating to other routes (e.g., `/sentimento`, `/pesquisas`, etc.)

**Reference**: 
- #425: https://reactjs.org/docs/error-decoder.html?invariant=425
- #418: https://reactjs.org/docs/error-decoder.html?invariant=418
- #423: https://reactjs.org/docs/error-decoder.html?invariant=423

---

## 5. Menu Links Not Working Properly

### Top Navigation
- **Issue**: Clicking on navigation links (Sentimento, Pesquisas, Candidates, Quiz, Metodologia, Caso de Uso) changes the URL but does not render the correct page content
- **Observation**: When clicking "Sentimento", URL changes to `/sentimento` and the nav link shows as [active], but the page still displays the home page news feed content
- **Root cause**: Likely related to the React errors causing the routing/Outlet to fail

### Bottom Navigation
- Same behavior as top navigation - URL changes but content doesn't update

---

## 6. Footer Links Not Implemented

### Issue
- Footer navigation items are plain text `<li>` elements, not clickable links
- Located in `site/src/App.jsx` lines 91-104

**Current implementation** (not clickable):
```jsx
<ul>
  <li>{t('nav.noticias')}</li>
  <li>{t('nav.sentimento')}</li>
  <li>{t('nav.pesquisas')}</li>
  <li>{t('nav.quiz')}</li>
</ul>
```

**Expected**: Should use `<NavLink>` or `<Link>` components to make them clickable

---

## Files to Review

| File | Purpose |
|------|---------|
| `site/index.html` | Add favicon |
| `site/src/hooks/useData.js` | Fix data fetch path |
| `site/src/locales/pt-BR/common.json` | Add missing accents |
| `site/src/locales/pt-BR/case-study.json` | Add missing accents |
| `site/src/locales/pt-BR/candidates.json` | Add missing accents |
| `site/src/App.jsx` | Fix footer links |
| `site/src/main.jsx` | Review router configuration |
| `site/vite.config.js` | Verify base path configuration |

---

*Report generated: March 12, 2026*
