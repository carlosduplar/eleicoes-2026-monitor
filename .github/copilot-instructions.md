# Copilot Instructions — eleicoes-2026-monitor

## Projeto

Portal de monitoramento bilingue (pt-BR + en-US) das eleicoes BR 2026.
Stack: Python 3.12 + React + Vite + vite-plugin-ssg + GitHub Pages + GitHub Actions.
PowerShell 7 no Windows 11. Comandos de shell devem usar sintaxe PowerShell.

## Wireframes de referencia

Antes de implementar qualquer componente frontend, consultar o wireframe correspondente em `docs/wireframes/`.
Os wireframes sao HTML standalone auto-contidos. Abrir no browser para visualizar.

| WF | Arquivo | Componentes React |
|----|---------|------------------|
| WF-01 | `WF-01-feed-desktop.html` | `Home.jsx`, `NewsFeed.jsx`, `SourceFilter.jsx` |
| WF-02/03 | `WF-02-03-sentiment-dashboard.html` | `SentimentDashboard.jsx` |
| WF-04 | `WF-04-poll-tracker.html` | `PollTracker.jsx`, `PollsPage.jsx` |
| WF-05 | `WF-05-quiz-question-desktop.html` | `QuizEngine.jsx`, `QuizPage.jsx` |
| WF-06 | `WF-06-quiz-result-desktop.html` | `QuizResultCard.jsx`, `QuizResult.jsx` |
| WF-07 | `WF-07-candidate-profile-desktop.html` | `CandidatePage.jsx` |
| WF-08 | `WF-08-candidate-comparison.html` | `ComparisonPage.jsx` |
| WF-09 | `WF-09-methodology.html` | `MethodologyPage.jsx` |
| WF-10 | `WF-10-case-study.html` | `CaseStudyPage.jsx` |
| WF-11 | `WF-11-mobile-feed.html` | `Home.jsx` (mobile 390px) |
| WF-12 | `WF-12-mobile-quiz.html` | `QuizEngine.jsx`, `QuizResultCard.jsx` (mobile) |

## Regras de pipeline

- Scripts Python sao idempotentes: rodar 2x sem duplicar dados
- `id = sha256(url.encode())[:16]` em todos os scripts de coleta
- Erros de IA nunca interrompem o pipeline (try/except + log)
- `summaries` sempre com `pt-BR` e `en-US` antes de commitar artigos
- Validar conformidade com `docs/schemas/*.schema.json` antes de commitar dados

## Regras de frontend

- O quiz NUNCA exibe `candidate_slug` ou `source_*` durante as perguntas
- `MethodologyBadge` obrigatorio em todos os componentes de dados
- `sentiment.json` sempre inclui `disclaimer_pt` e `disclaimer_en`
- Loading, empty e error state em todos os componentes de dados
- Strings de UI via `react-i18next` — nenhum texto hardcoded em JSX
- CSS custom properties conforme wireframes: `--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border`

## Schemas

Tipos TypeScript: `docs/schemas/types.ts`
JSON Schemas: `docs/schemas/*.schema.json`
Python e React DEVEM concordar com esses schemas. Verificar antes de implementar.

## Hierarquia de agentes

- Opus (Arquiteto): PLAN.md, ADRs, schemas, wireframes
- Codex (Tatico): task specs em `tasks/phaseNN/`, cenarios de teste
- MiniMax (Operacional): implementacao em RALPH loops
- Gemini (QA): testes Playwright, relatorios

Handoff via arquivo: `plans/phase-NN-arch.DONE` -> Codex le e cria task specs.
Escalacao: `tasks/phase-NN/ESCALATION.md` apos 3 tentativas com mesmo erro.

## Context7

Obrigatorio consultar Context7 antes de decisoes sobre bibliotecas, APIs ou dependencias.

## Workflow docs

`docs-maintainer` skill apos cada fase: atualizar PLAN.md, CHANGELOG.md, `docs/case-study/pt-BR.md` e `en-US.md`.
