# Case Study — Portal Eleicoes BR 2026

## 2026-03-09 — Fase 03 (RSS Collection)

### Entregas implementadas
- Cadastro de fontes em `data/sources.json` com blocos `rss`, `parties` e `polls`.
- Coletor RSS em `scripts/collect_rss.py` com:
  - leitura de fontes ativas;
  - deduplicacao por `sha256(url.encode()).hexdigest()[:16]`;
  - status inicial `raw`, campos obrigatorios e `summaries` bilingues vazios;
  - tolerancia a falhas por feed e timeout de 15 segundos.
- Consolidacao em `scripts/build_data.py` com deduplicacao por ID, ordenacao por `published_at`, limite de 500 artigos e validacao com warnings.
- Suite de testes `scripts/test_collect_rss.py` cobrindo ID, deduplicacao, idempotencia, falha de feed, limite e ordenacao.

### Validacao executada
- `python -m pytest scripts/test_collect_rss.py -v`
- `python scripts/collect_rss.py`
- `python scripts/build_data.py`
- `python -m pytest -q`

### Observacoes
- O consolidator emite warnings de schema quando `relevance_score` e `null`, sem remover registros, conforme especificacao da fase.

## 2026-03-09 — Fase 04 (Frontend MVP)

### Entregas implementadas
- Scaffold completo em `site/` com React + Vite + SSG (`vite-react-ssg`) e rotas estaticas.
- `site/vite.config.js` com plugin React, alias `@` para `src/` e proxy `/data` para a pasta raiz `data/`.
- i18n com `react-i18next` (default/fallback `pt-BR`) e locales `pt-BR` + `en-US`.
- App shell (`Nav`, `CountdownTimer`, rotas, footer) em `site/src/App.jsx` e inicializacao em `site/src/main.jsx`.
- Hook `useData` com cache em memoria para evitar re-fetch.
- Componentes de feed: `NewsFeed`, `SourceFilter`, `LanguageSwitcher`, `MethodologyBadge`.
- Pagina `Home` com layout 70/30 alinhado ao WF-01 e responsividade para mobile (390px, WF-11).
- `site/index.html` atualizado com meta tags base, Open Graph padrao pt-BR e autodiscovery de RSS (`/feed.xml`, `/feed-en.xml`).

### Validacao executada
- `cd site && npm install`
- `cd site && npm run dev` (servidor sobe em `http://localhost:5173/`)
- `Invoke-WebRequest http://localhost:5173/data/articles.json` retorna HTTP 200 (proxy `/data` validado)
- `cd site && npm run build` (gera HTML estatico em `site/dist/` para todas as 6 rotas da fase)

## 2026-03-09 — Fase 05 (CI/CD)

### Entregas implementadas
- Workflows GitHub Actions adicionados em `.github/workflows/`:
  - `collect.yml` (Foca, cron 10 min + `workflow_dispatch`)
  - `validate.yml` (Editor, push em `data/raw/**` + cron 30 min + `workflow_dispatch`)
  - `curate.yml` (Editor-chefe, cron horario + `workflow_dispatch`, com `continue-on-error` no passo de curadoria)
  - `deploy.yml` (deploy GitHub Pages em push para `main` com filtros de path)
  - `watchdog.yml` (health check diario, 06:00 UTC + `workflow_dispatch`)
- Stubs criados para scripts ainda nao implementados nas fases seguintes:
  - `collect_parties.py`, `collect_polls.py`, `collect_social.py`
  - `summarize.py`, `analyze_sentiment.py`
  - `generate_rss_feed.py`, `generate_seo_pages.py`
- `scripts/curate.py` criado com skip logic de 90 minutos usando `data/.curate_last_run`.
- `scripts/watchdog.py` criado para gerar `data/pipeline_health.json`.
- Seeds de pipeline garantidos:
  - `data/pipeline_errors.json`
  - `data/pipeline_health.json`
  - `data/ai_usage.json` (ja existente)
  - `data/.curate_last_run`
- README atualizado com acao manual obrigatoria para Pages: `Settings > Pages > Source = GitHub Actions`.

### Validacao executada
- `python -m pytest -q` (suite Python existente)
- `python scripts/collect_rss.py`
- `python scripts/collect_parties.py`
- `python scripts/collect_polls.py`
- `python scripts/collect_social.py`
- `python scripts/summarize.py`
- `python scripts/analyze_sentiment.py`
- `python scripts/build_data.py`
- `python scripts/generate_rss_feed.py`
- `python scripts/curate.py` (1a execucao grava timestamp)
- `python scripts/curate.py` (2a execucao valida skip < 90 min)
- `python scripts/watchdog.py`
- `python scripts/generate_seo_pages.py`
