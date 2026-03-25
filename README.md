# Portal Eleicoes BR 2026

[![Collect](https://github.com/carlosduplar/eleicoes-2026-monitor/actions/workflows/collect.yml/badge.svg)](https://github.com/carlosduplar/eleicoes-2026-monitor/actions/workflows/collect.yml)
[![Deploy](https://github.com/carlosduplar/eleicoes-2026-monitor/actions/workflows/deploy.yml/badge.svg)](https://github.com/carlosduplar/eleicoes-2026-monitor/actions/workflows/deploy.yml)
[![Watchdog](https://github.com/carlosduplar/eleicoes-2026-monitor/actions/workflows/watchdog.yml/badge.svg)](https://github.com/carlosduplar/eleicoes-2026-monitor/actions/workflows/watchdog.yml)

> Live: https://carlosduplar.github.io/eleicoes-2026-monitor/

## What is this? / O que e isto?

Portal Eleicoes BR 2026 is a bilingual static portal (pt-BR and en-US) that monitors election news, sentiment, polling, and candidate positioning signals for Brazil's 2026 presidential cycle. It combines a Python ingestion pipeline, AI-assisted enrichment, and a React + Vite SSG frontend published to GitHub Pages. The product is designed as auditable editorial infrastructure: readers can inspect methodology, processing status, sources, and the technical path that produced each public artifact.

O Portal Eleições BR 2026 é um portal estático bilíngue (pt-BR e en-US) para monitorar notícias, sentimento, pesquisas e sinais de posicionamento de candidatos na eleição presidencial de 2026. O projeto combina pipeline Python de ingestão, enriquecimento com IA e frontend React + Vite SSG publicado no GitHub Pages. O produto foi concebido como infraestrutura editorial auditável: o público consegue inspecionar metodologia, status de processamento, fontes e o caminho técnico que levou cada artefato ao ar.

## Screenshot

![Homepage light mode](docs/homepage-light.png)

## Architecture

```text
Sources (21 RSS, 8 party sites, 10 polling institutes, YouTube)
                |
                v
      scripts/collect_*.py  (Foca, ~10 min)
                |
                v
       raw articles + editor feedback sync
                |
                v
   scripts/summarize.py + analyze_sentiment.py
           (Editor, ~30 min)
                |
                v
  validated articles + bilingual summaries
                |
                v
    scripts/curate.py + quiz extraction
        (Editor-chefe, ~90 min)
                |
                v
 curated articles / irrelevant purge
                |
                v
 data/*.json  -> schema validation -> git commit
                |
                v
 React + Vite + vite-plugin-ssg (site/)
                |
                v
      GitHub Pages + Cloudflare CDN
```

Publication states are explicit in the data: `raw -> validated -> curated`, plus `irrelevant` for items automatically filtered out of the public feed.

## Methodology and use case highlights / Metodologia e caso de uso

- Independent project with no party affiliation or electoral funding; methodology, limitations, and error reporting are part of the product surface.
- Newsroom-style pipeline with three automated roles: `Foca` (collection), `Editor` (validation/summarization), and `Editor-chefe` (curation/prominence).
- AI fallback chain (default tasks): NVIDIA NIM (Nemotron 3 Super) -> Ollama Cloud (Nemotron 3 Super) -> Gemini 3.1 Flash Lite (free tier) -> Vertex AI (Gemini 3 Flash Preview) -> MiMo V2 Flash.
- AI fallback chain (high-quality tasks — quiz/positions): Ollama Cloud (Kimi K2.5) -> NVIDIA NIM (MiniMax M2.5) -> Vertex AI (Gemini 3 Flash Preview).
- Circuit breaker and per-run AI call limits keep the pipeline running when providers degrade instead of failing closed.
- Editorial feedback is self-healing: blocked keywords, URLs, sources, and `irrelevant` article IDs are accumulated in `data/editor_feedback.json`.
- The public quiz only reveals sources in the result view, never during the questions.
- Public topic IDs use `politica_externa` for foreign policy. `eleicoes` remains an article-level relevance tag, not a candidate-position or quiz topic.

## Running Locally

```powershell
# from repository root
pip install -r requirements.txt

Push-Location site
npm install
npm run dev
Pop-Location
```

```powershell
# run data pipeline scripts from root
python scripts/collect_rss.py
python scripts/build_data.py
python scripts/curate.py
```

```powershell
# tests
python -m pytest scripts/ -v --tb=short
Push-Location site
npx playwright install chromium
npx playwright test
Pop-Location
```

## Editorial feedback loop (self-healing)

The ingestion pipeline now supports an editorial feedback file: `data/editor_feedback.json`.

- Mark an article as irrelevant by setting `"status": "irrelevant"` in `data/articles.json`.
- On each collect run, `scripts/sync_editor_feedback.py` stores those article IDs in `editor_feedback.json`.
- `scripts/collect_rss.py` skips URLs/IDs/sources/title patterns present in that file.
- `scripts/build_data.py` publishes only non-irrelevant articles and keeps the feedback list updated.

You can also add manual rules in `editor_feedback.json`:

- `blocked_title_keywords`
- `blocked_url_substrings`
- `blocked_sources`

This mechanism is part of the project's transparency model: irrelevant content is filtered automatically, but the filtering rules remain visible and auditable in the repository.

## Article Archiving

`data/articles.json` uses a tiered retention strategy to keep the file manageable as articles accumulate:

| Tier | Default Age | Behavior |
|------|-------------|----------|
| **Hot** | 0–7 days | Full article retained (all fields including `content`) |
| **Warm** | 7–30 days | `content` field stripped, metadata + summaries preserved |
| **Cold** | 30+ days | Moved to `data/archives/YYYY-MM.json`, removed from main file |

Curated articles (`status: "curated"`) get an extra 7 days of hot retention (14 total) since they have been manually reviewed.

```powershell
# Preview what would change (dry-run, default)
python scripts/archive_articles.py

# Apply changes
python scripts/archive_articles.py --execute

# Custom thresholds
python scripts/archive_articles.py --execute --hot-days 14 --warm-days 60
```

Archive files in `data/archives/` follow the same schema as `articles.json` and are committed alongside the main data files. The archiving step runs automatically in the `collect.yml` workflow after `build_data.py`.

## Required GitHub Secrets

| Secret | Used by | Description |
|---|---|---|
| `BRIGHTDATA_API_KEY` | `collect.yml` | Bright Data API key for fallback scraping |
| `BRIGHTDATA_ZONE` | `collect.yml` | Bright Data zone identifier |
| `NVIDIA_API_KEY` | `collect.yml`, `validate.yml`, `curate.yml`, `update-quiz.yml` | NVIDIA NIM provider |
| `OPENROUTER_API_KEY` | `collect.yml`, `validate.yml`, `curate.yml`, `update-quiz.yml` | OpenRouter provider |
| `OLLAMA_API_KEY` | `collect.yml`, `validate.yml`, `curate.yml`, `update-quiz.yml` | Ollama Cloud provider |
| `VERTEX_ACCESS_TOKEN` | `collect.yml`, `validate.yml`, `curate.yml`, `update-quiz.yml` | Vertex/Gemini access token |
| `VERTEX_BASE_URL` | `collect.yml`, `validate.yml`, `curate.yml`, `update-quiz.yml` | Vertex/Gemini endpoint base URL |
| `XIAOMI_MIMO_API_KEY` | `collect.yml`, `validate.yml`, `curate.yml` | MiMo fallback provider |
| `TWITTER_BEARER_TOKEN` | `collect.yml` | Social collection token |
| `YOUTUBE_API_KEY` | `collect.yml` | YouTube collection key |

The methodology page and case study document the current preferred AI provider order for public transparency. The table above lists the secrets still referenced by workflows in this repository, including legacy compatibility variables while provider migrations are cleaned up.

## Pre-candidates (March 2026)

| Name | Party | Status |
|---|---|---|
| Luiz Inacio Lula da Silva | PT | pre-candidate |
| Flavio Nantes Bolsonaro | PL | pre-candidate |
| Tarcisio Gomes de Freitas | Republicanos | speculated |
| Ronaldo Ramos Caiado | Uniao Brasil | pre-candidate |
| Romeu Zema Neto | Novo | pre-candidate |
| Carlos Roberto Massa Junior | PSD | speculated |
| Eduardo Figueiredo Cavalheiro Leite | PSD | pre-candidate |
| Jose Aldo Rebelo Figueiredo | DC | pre-candidate |
| Renan Franco Santos | Missao | pre-candidate |

## Architecture Decision Records

- [ADR-000: Wireframes](docs/adr/000-wireframes.md)
- [ADR-001: Hosting](docs/adr/001-hosting.md)
- [ADR-002: AI Providers](docs/adr/002-ai-providers.md)
- [ADR-003: i18n Strategy](docs/adr/003-i18n-strategy.md)
- [ADR-004: SEO and GEO Strategy](docs/adr/004-seo-geo-strategy.md)
- [ADR-005: Quiz Affinity System](docs/adr/005-quiz-affinity-system.md)
- [ADR-006: Transparency and Methodology](docs/adr/006-transparency-methodology.md)

## Learn more / Saiba mais

- [Methodology ADR](docs/adr/006-transparency-methodology.md)
- [Case study (pt-BR)](docs/case-study/pt-BR.md)
- [Case study (en-US)](docs/case-study/en-US.md)
- Live pages: [`/metodologia`](https://carlosduplar.github.io/eleicoes-2026-monitor/metodologia/) and [`/sobre/caso-de-uso`](https://carlosduplar.github.io/eleicoes-2026-monitor/sobre/caso-de-uso/)

## Contributing

Open a GitHub issue describing the bug/feature and the expected behavior before opening a pull request.

## License

MIT
