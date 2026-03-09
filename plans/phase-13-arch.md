# Phase 13 — Case Study Page

## Objective

Implement `CaseStudyPage.jsx` at `/sobre/caso-de-uso` — a living documentation page showcasing this project as an AI-assisted development case study. Publish bilingual case study documents (`docs/case-study/pt-BR.md` and `en-US.md`) on the live site. Follow WF-10 wireframe.

## Input Context

- `docs/wireframes/WF-10-case-study.html` — Reference wireframe (open in browser before implementing)
- `docs/adr/000-wireframes.md` — Design tokens, typography
- `docs/case-study/pt-BR.md` — Living case study document (may already have initial content from docs-maintainer skill runs)
- `docs/case-study/en-US.md` — English equivalent
- `site/src/locales/pt-BR/common.json` — Existing i18n structure
- `docs/prompt-eleicoes2026-v5.md` lines 22-24 — "Este projeto é documentado como caso de uso"
- `PLAN.md` — Full architectural decisions and phase history for content

## Deliverables

### 1. `docs/case-study/pt-BR.md`

Living narrative document. Must cover:

```markdown
# Caso de Uso: Portal Eleições BR 2026

## Sumário executivo
[1-2 paragraphs: what was built, why, with what tools]

## Stack e arquitetura
[Summarize the key architectural decisions from PLAN.md]

## Hierarquia de agentes
[Describe Opus/Codex/MiniMax/Gemini roles and RALPH loop protocol]

## Pipeline de ingestão
[Foca → Editor → Editor-chefe, publication stages model]

## Decisões técnicas registradas
[ADRs 000-006 in brief]

## Lições aprendidas
[Honest assessment: what worked, what was complex, what would be done differently]

## Números do projeto
[Approx: # of files, # of commits, # of phases, pipeline frequency]

## Próximos passos
[Phase 14-17 brief summary]
```

### 2. `docs/case-study/en-US.md`

English equivalent of the above document. Same structure, full translation.

### 3. `site/src/locales/pt-BR/case-study.json`

```json
{
  "title": "Caso de Uso: Desenvolvimento com IA",
  "subtitle": "Como construímos um portal eleitoral em tempo real usando múltiplos agentes de IA",
  "toc_label": "Neste artigo",
  "back_to_home": "← Voltar ao portal",
  "reading_time": "{{minutes}} min de leitura",
  "last_updated": "Atualizado em {{date}}",
  "share": "Compartilhar este caso de uso",
  "sections": {
    "executive_summary": "Sumário Executivo",
    "stack": "Stack e Arquitetura",
    "agents": "Hierarquia de Agentes",
    "pipeline": "Pipeline de Ingestão",
    "adrs": "Decisões Técnicas",
    "lessons": "Lições Aprendidas",
    "numbers": "Números do Projeto",
    "next_steps": "Próximos Passos"
  }
}
```

### 4. `site/src/locales/en-US/case-study.json`

English equivalents for all keys above.

### 5. `site/src/pages/CaseStudyPage.jsx`

Replaces Phase 04 placeholder.

**Layout (WF-10):** Long-form editorial article layout:
- Fixed table-of-contents sidebar (sticky on desktop, collapsed/drawer on mobile)
- Main content: full article with H2 section headers
- Top breadcrumb: "Portal Eleições BR 2026 > Sobre > Caso de Uso"
- Reading time estimate (word count / 200)

**Content loading strategy:** the case study content is in `docs/case-study/` markdown files. The `deploy.yml` already copies `docs/case-study/` to `site/public/case-study/`. Load via `fetch('/case-study/pt-BR.md')` (or `en-US.md` based on language), then render with a minimal Markdown-to-HTML renderer.

**Markdown rendering:** use `marked` (already a common Vite-compatible package) or write a minimal renderer using regex for H2, H3, paragraphs, bold, lists. Prefer `marked` — add it to `site/package.json`.

**`<Helmet>`:**
- `<title>Caso de Uso: Portal Eleições BR 2026 | Desenvolvimento com IA</title>`
- JSON-LD `TechArticle`:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    "headline": "Caso de Uso: Portal Eleições BR 2026",
    "description": "Como construímos um portal eleitoral em tempo real usando múltiplos agentes de IA",
    "url": "https://eleicoes2026.com.br/sobre/caso-de-uso",
    "author": {"@type": "Organization", "name": "carlosduplar"},
    "inLanguage": "pt-BR"
  }
  ```

**Language switch:** when user toggles to en-US, reload content from `/case-study/en-US.md`.

**States:**
- Loading: skeleton placeholder (two skeleton paragraphs per section)
- Error: "Conteúdo indisponível. Tente novamente mais tarde." / "Content unavailable."

### 6. Update `deploy.yml`

Verify the copy step `cp -r docs/case-study/ site/public/case-study/` is present in the deploy workflow (added in Phase 05). If it uses `|| true` soft-failure, remove that — the case-study directory must exist by this phase.

### 7. i18n main.jsx update

Register `case-study` namespace: update `main.jsx` to include `ns: ['common', 'methodology', 'candidates', 'quiz', 'case-study']`.

## Constraints

- No hardcoded article content in JSX — content comes from the markdown files
- `marked` must be added to `site/package.json` and installed via `npm install`
- The table-of-contents is generated automatically from H2 headings in the markdown
- Language switch must reload the correct markdown file (pt-BR vs en-US) without page refresh
- The case study documents are "living" — the docs-maintainer skill updates them after each phase; the page must always reflect the latest committed version

## Acceptance Criteria

- [ ] `docs/case-study/pt-BR.md` exists with all required sections (min 800 words)
- [ ] `docs/case-study/en-US.md` exists with all required sections (min 800 words)
- [ ] `/sobre/caso-de-uso` renders with table-of-contents sidebar and article body
- [ ] Language toggle switches between pt-BR and en-US content (different markdown files)
- [ ] Markdown headings are rendered as HTML headings (H2, H3), not raw `##` text
- [ ] JSON-LD `TechArticle` is present in page `<head>`
- [ ] Loading state shows skeleton while markdown is fetching
- [ ] `deploy.yml` copies case study files to `site/public/case-study/`
- [ ] `npm run build` succeeds with `marked` installed

## Commit & Push

After all deliverables are verified:

```
git add docs/case-study/pt-BR.md docs/case-study/en-US.md site/src/pages/CaseStudyPage.jsx site/src/locales/pt-BR/case-study.json site/src/locales/en-US/case-study.json site/src/main.jsx site/package.json
git commit -m "feat(phase-13): Case study page — living bilingual documentation at /sobre/caso-de-uso

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-13-arch.DONE`.
