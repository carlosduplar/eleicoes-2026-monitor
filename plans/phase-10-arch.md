# Phase 10 — Methodology Page

## Objective

Implement `MethodologyPage.jsx` at `/metodologia` — the transparency page that describes the pipeline, lists AI providers, discloses limitations, and provides a link to report errors. Create bilingual locale files for the methodology content. Follow WF-09 wireframe. Create ADR 006.

## Input Context

- `docs/wireframes/WF-09-methodology.html` — Reference wireframe (open in browser before implementing)
- `docs/adr/000-wireframes.md` — Design tokens, typography
- `docs/prompt-eleicoes2026-v5.md` lines 608-641 — Methodology page content requirements (disclaimer, pipeline description, limitations, error reporting)
- `site/src/components/MethodologyBadge.jsx` — Already exists (from Phase 07) — this page is its destination
- `site/src/locales/pt-BR/common.json` — Existing i18n structure

## Deliverables

### 1. `site/src/locales/pt-BR/methodology.json`

```json
{
  "title": "Metodologia",
  "subtitle": "Como funciona o Portal Eleições BR 2026",
  "disclaimer": {
    "heading": "Declaração de Independência",
    "body": "Este portal é um projeto independente, sem filiação partidária ou financiamento eleitoral. Não há intervenção editorial de nenhuma forma: os artigos são coletados automaticamente de fontes públicas, os resumos são gerados por inteligência artificial, e as análises de sentimento são derivadas algoritmicamente. O código-fonte completo está disponível para consulta e auditoria pública em github.com/carlosduplar/eleicoes-2026-monitor."
  },
  "pipeline": {
    "heading": "Como funciona o pipeline",
    "collection": {
      "label": "Coleta",
      "body": "RSS de 20 veículos + scraping de sites partidários e institutos de pesquisa, a cada 10 minutos via GitHub Actions."
    },
    "summarization": {
      "label": "Sumarização",
      "body": "Modelos de linguagem open-source com fallback hierárquico: NVIDIA NIM (gratuito) → OpenRouter (gratuito, 200 req/dia) → Ollama Cloud (gratuito) → Vertex AI Gemini 2.5 Flash Lite (pago prioritário) → MiMo V2 Flash."
    },
    "sentiment": {
      "label": "Sentimento",
      "body": "Análise algorítmica do tom das notícias coletadas. Os scores refletem o tom das manchetes e resumos — não uma avaliação editorial ou pesquisa de opinião."
    },
    "polls": {
      "label": "Pesquisas Eleitorais",
      "body": "Dados coletados automaticamente dos sites dos institutos. Reproduzidos sem modificação editorial."
    },
    "quiz": {
      "label": "Quiz de Afinidade",
      "body": "Posições extraídas de declarações verificadas nas notícias coletadas. Fontes exibidas no resultado — nunca durante as perguntas."
    }
  },
  "limitations": {
    "heading": "Limitações conhecidas",
    "items": [
      "Modelos de IA podem cometer erros de interpretação.",
      "A cobertura de fontes pode ter viés de disponibilidade — veículos sem RSS não são incluídos.",
      "Posições de candidatos evoluem ao longo da campanha; o pipeline atualiza diariamente.",
      "Análise de sentimento não equivale a pesquisa de opinião."
    ]
  },
  "error_reporting": {
    "heading": "Reportar erros",
    "body": "Encontrou um erro? Abra uma issue no repositório público.",
    "cta": "Abrir issue no GitHub"
  },
  "repo_link": "https://github.com/carlosduplar/eleicoes-2026-monitor"
}
```

### 2. `site/src/locales/en-US/methodology.json`

English equivalents for all keys above. Key translations:
- `title`: "Methodology"
- `subtitle`: "How the Brazil Elections 2026 Portal Works"
- `disclaimer.heading`: "Independence Statement"
- `pipeline.heading`: "How the pipeline works"
- `limitations.heading`: "Known limitations"
- `error_reporting.heading`: "Report errors"
- `error_reporting.cta`: "Open issue on GitHub"

### 3. `site/src/pages/MethodologyPage.jsx`

Replaces the Phase 04 placeholder.

**Layout (WF-09):**
- Full-width editorial layout, max-width `860px`, centered
- Top: page title + subtitle (Georgia serif H1)
- Section 1: Disclaimer — visually highlighted box (background `var(--brand-muted)`, left border `4px solid var(--brand-navy)`)
- Section 2: Pipeline description — ordered list with icon per step (collection, summarization, sentiment, polls, quiz)
- Section 3: Limitations — bulleted list, each item preceded by `⚠️` icon
- Section 4: Error reporting — button linking to GitHub issues (`target="_blank"`, `rel="noopener noreferrer"`)
- Section 5: Repository link — "Código fonte: github.com/carlosduplar/eleicoes-2026-monitor"

**`<Helmet>`:**
- `<title>Metodologia | Portal Eleições BR 2026</title>`
- JSON-LD `AboutPage` + `FAQPage` schemas:
  ```json
  {
    "@context": "https://schema.org",
    "@type": ["AboutPage", "FAQPage"],
    "name": "Metodologia — Portal Eleições BR 2026",
    "description": "Como funciona o pipeline de coleta e análise do portal.",
    "url": "https://eleicoes2026.com.br/metodologia"
  }
  ```

**i18n:** load `methodology` namespace via `useTranslation('methodology')`.

### 4. `site/src/main.jsx` — register methodology namespace

Ensure `i18next` is configured to load the `methodology` namespace from `site/src/locales/{lng}/methodology.json`. Update the i18n initialization in `main.jsx` to include `ns: ['common', 'methodology']`.

### 5. `docs/adr/006-transparency-methodology.md`

```markdown
# ADR 006 — Transparency and Methodology Page

## Status
Accepted

## Context
This portal uses AI to generate summaries and sentiment scores on electoral news. Without transparency, users cannot distinguish AI analysis from editorial opinion. The GDPR-adjacent principle of explainability applies, even for public non-personal data.

## Decision
A dedicated /metodologia page is mandatory. MethodologyBadge links to it from every data-driven component. The page discloses: independence, pipeline steps, AI providers, known limitations, and an error reporting channel.

## Consequences
- Users can audit methodology and report errors
- MethodologyBadge acts as a trust signal on all dashboards
- ADR is living documentation — update when new AI providers or sources are added
```

## Constraints

- No hardcoded strings in JSX — all content via the `methodology` i18n namespace
- The disclaimer section must be visually prominent (not buried) — use the highlighted box spec above
- GitHub issues link must open in a new tab with `rel="noopener noreferrer"`
- `MethodologyBadge` on other pages links to this page — ensure the route `/metodologia` is live and renders without error

## Acceptance Criteria

- [ ] `/metodologia` renders with all 5 sections: disclaimer, pipeline, limitations, error reporting, repo link
- [ ] Language toggle switches to en-US correctly (all content translates)
- [ ] Disclaimer section is visually highlighted (not plain text)
- [ ] GitHub issues link opens in new tab
- [ ] `<Helmet>` sets correct `<title>` tag
- [ ] JSON-LD `AboutPage` + `FAQPage` schema is present in page `<head>`
- [ ] `docs/adr/006-transparency-methodology.md` is committed
- [ ] `MethodologyBadge` on `/sentimento` and `/pesquisas` links correctly to this page
- [ ] `npm run build` succeeds

## Commit & Push

After all deliverables are verified:

```
git add site/src/pages/MethodologyPage.jsx site/src/locales/pt-BR/methodology.json site/src/locales/en-US/methodology.json site/src/main.jsx docs/adr/006-transparency-methodology.md
git commit -m "feat(phase-10): Methodology page + ADR 006 + i18n methodology namespace

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-10-arch.DONE`.
