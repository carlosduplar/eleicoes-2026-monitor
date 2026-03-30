# Phase 18 — Government Data Integration (TSE + Portal da Transparência)

## Goal

Surface structured Brazilian government open-data alongside existing candidate profiles and introduce a dedicated campaign-finance transparency page.

## APIs

| Source | Endpoint | Auth |
|--------|----------|------|
| TSE DivulgaCandContas | `https://divulgacandcontas.tse.jus.br/divulga/rest/v1/` | None required |
| TSE CDN Results | `https://resultados.tse.jus.br/ele2022/544/dados-simplificados/{uf}/...` | None |
| Portal da Transparência | `https://api.portaldatransparencia.gov.br/api-de-dados` | Optional `chave-api-dados` header |

No mcp-brasil dependency. Scripts call the REST APIs directly with `requests`.

## Data files

- `site/public/data/tse_data.json` — 2022 presidential results, per candidate
- `site/public/data/transparencia_data.json` — PEP status + emendas parlamentares, per candidate

Both files follow the project conventions: atomic write (tmp + replace), schema-validated JSON, `schema_version` + `updated_at` + `disclaimer_pt/en` envelope.

## Frontend additions

### `CandidateGovData` component

Tabbed card placed after `CandidateArticles` in `CandidatePage.jsx`:
- Tab 1 — TSE: 2022 presidential result (if applicable), elected badge, source link
- Tab 2 — Transparência: PEP badge with disclaimer, emendas summary table, source link

### `/financiamento` route — `FinanciamentoPage`

Sortable table comparing all 9 candidates across:
- PEP registry status
- Count of emendas parlamentares
- Total committed (empenhado)
- Total paid (pago)

Columns are sortable. Disclaimer is prominent. Sources listed at the bottom.

## Automation

`.github/workflows/collect_gov_data.yml` runs every Sunday at 04:00 UTC (`0 4 * * 0`). It:
1. Runs `collect_tse.py`
2. Runs `collect_transparencia.py` (soft-fail — keeps existing data on API error)
3. Commits updated JSON files with `[skip ci]` to avoid triggering deploy

## Decisions

- No mcp-brasil runtime dependency — read its source to understand endpoints, re-implemented in pure Python.
- Portal da Transparência API key is optional; stored in `TRANSPARENCIA_API_KEY` secret when available.
- TSE 2026 candidacy registration period has not opened; only 2022 historical data is seeded for Lula.
- PEP disclaimer is always rendered to avoid misinterpretation.
