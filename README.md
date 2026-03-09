# Portal Eleicoes BR 2026

Monitoramento em tempo real das eleicoes presidenciais brasileiras de 2026.
Real-time monitoring of Brazil's 2026 presidential elections.

---

## About

A bilingual (pt-BR / en-US) static portal that aggregates news, sentiment analysis, polling data, and a political affinity quiz for Brazil's 2026 presidential race. Built on GitHub Pages with automated AI-powered pipelines running every 10-30 minutes.

## Architecture

```
Pipeline (Python 3.12)          Frontend (React + Vite SSG)
  collect_rss.py  ──┐
  collect_polls.py ─┤           site/src/
  collect_parties.py┤             pages/       ← SSG pre-rendered
  ai_client.py ─────┤             components/  ← NewsFeed, PollTracker, Quiz...
  summarize.py ─────┤             locales/     ← pt-BR, en-US
  build_data.py ────┘             hooks/       ← useData, useQuiz
        │                              │
        ▼                              ▼
    data/*.json  ──────────►  GitHub Pages (static)
        │
    GitHub Actions (cron 10/30/90 min)
```

### Newsroom Model

| Role | Frequency | Responsibility |
|------|-----------|----------------|
| **Foca** (collector) | 10 min | RSS collection, dedup, relevance scoring |
| **Editor** (validator) | 30 min | Bilingual summaries, sentiment, topic validation |
| **Editor-chefe** (curator) | ~90 min | Prominence ranking, weekly briefing, quiz positions |

### AI Provider Chain (free-first)

1. NVIDIA NIM (free dev credits)
2. OpenRouter (free, 200 req/day)
3. Ollama Cloud (free)
4. Vertex AI / Gemini (paid, $10/mo)
5. MiMo (paid fallback)

All providers use the OpenAI Python SDK via `base_url` swap. Zero vendor lock-in.

## Features

- **News Feed**: Aggregated from 20+ RSS sources with real-time updates
- **Sentiment Dashboard**: Candidate x topic heatmap with source transparency
- **Polling Tracker**: Historical line charts from 6 major institutes
- **Political Affinity Quiz**: 15-topic progressive funnel, candidate reveal only in results
- **Candidate Profiles**: SEO-optimized pages with positions, polling, and sentiment
- **Candidate Comparison**: Side-by-side comparison with data visualizations
- **Methodology Page**: Full pipeline transparency, AI disclaimers
- **Bilingual**: Complete pt-BR and en-US support via react-i18next

## Pre-candidates Tracked (March 2026)

| Name | Party | Status |
|------|-------|--------|
| Lula | PT | Pre-candidate |
| Flavio Bolsonaro | PL | Pre-candidate |
| Tarcisio de Freitas | Republicanos | Speculated |
| Ronaldo Caiado | Uniao Brasil | Pre-candidate |
| Romeu Zema | Novo | Pre-candidate |
| Ratinho Jr | PSD | Speculated |
| Eduardo Leite | PSD | Pre-candidate |
| Aldo Rebelo | DC | Pre-candidate |
| Renan Santos | Missao | Pre-candidate |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Hosting | GitHub Pages |
| CDN | Cloudflare Free |
| CI/CD | GitHub Actions (cron) |
| Frontend | React + Vite + vite-plugin-ssg |
| i18n | react-i18next |
| SEO | react-helmet-async + JSON-LD |
| Pipeline | Python 3.12 (feedparser, BeautifulSoup, Playwright) |
| AI | Multi-provider via OpenAI SDK |

## Project Structure

```
eleicoes-2026-monitor/
  .github/workflows/     ← CI/CD pipelines
  scripts/               ← Python collection + AI processing
  data/                  ← JSON data files (auto-generated)
  site/                  ← React + Vite frontend
  docs/
    adr/                 ← Architecture Decision Records
    schemas/             ← JSON Schema + TypeScript types
    wireframes/          ← HTML standalone wireframes (WF-01 to WF-12)
    case-study/          ← Living documentation (pt-BR, en-US)
  plans/                 ← Phase specs for Codex agents
  PLAN.md                ← Master implementation plan
  CHANGELOG.md           ← Version history
  conductor.ps1          ← Multi-agent orchestrator
```

## Development

### Prerequisites

- Python 3.12+
- Node.js 20 LTS
- PowerShell 7 (for conductor.ps1)

### Setup

```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd site && npm install
```

### Running

```bash
# Orchestrate all agents
pwsh conductor.ps1

# Or run individual scripts
python scripts/collect_rss.py
python scripts/build_data.py

# Frontend dev server
cd site && npm run dev
```

## Documentation

- [PLAN.md](PLAN.md) — Master implementation plan (17 phases)
- [Architecture Decision Records](docs/adr/) — ADR 000-003+
- [Data Schemas](docs/schemas/) — JSON Schema + TypeScript types
- [Agent Protocol](docs/agent-protocol.md) — Multi-agent handoff protocol
- [Wireframes](docs/wireframes/) — HTML standalone wireframes

## Disclaimers

- Sentiment analysis is algorithmic and does not represent polling data
- Quiz results are based on verified public declarations, not endorsements
- All AI-generated content is labeled with methodology badges
- This is an academic/educational project, not affiliated with any political party

## License

MIT
