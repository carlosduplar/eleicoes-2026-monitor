# Seed Data Sources

Sources used by `scripts/seed_candidates_positions.py` to populate the baseline
knowledge base for candidate policy positions.

## Source A — Wikipedia PT REST API

| Attribute | Value |
|---|---|
| **Provider** | Wikimedia Foundation |
| **URL** | `https://pt.wikipedia.org/w/api.php` |
| **License** | CC BY-SA 3.0 / GFDL |
| **Auth required** | None |
| **Rate limit** | ~200 req/s (we use 0.3s sleep between calls) |
| **Update frequency** | Continuously edited by volunteer contributors |
| **Data provided** | Political profile sections, declared positions, career background |

## Source B — Câmara dos Deputados (Dados Abertos)

| Attribute | Value |
|---|---|
| **Provider** | Câmara dos Deputados do Brasil |
| **URL** | `https://dadosabertos.camara.leg.br/api/v2` |
| **License** | Creative Commons Atribuição 3.0 Brasil |
| **Auth required** | None |
| **Rate limit** | Public API, reasonable use expected |
| **Update frequency** | Updated daily with legislative proceedings |
| **Data provided** | Nominal votes by deputy on categorized bills |

## Source C — Senado Federal (Dados Abertos)

| Attribute | Value |
|---|---|
| **Provider** | Senado Federal do Brasil |
| **URL** | `https://legis.senado.leg.br/dadosabertos` |
| **License** | Creative Commons Atribuição 3.0 Brasil |
| **Auth required** | None |
| **Rate limit** | Public API, reasonable use expected |
| **Update frequency** | Updated daily with legislative proceedings |
| **Data provided** | Senatorial votes on bills and amendments |

## Source D — AI Synthesis (Gemini / fallback providers)

| Attribute | Value |
|---|---|
| **Provider** | Google (Gemini), with NVIDIA and MiMo fallbacks |
| **Auth required** | API key via environment variable |
| **Data provided** | Synthesized position summaries from provided snippets or training knowledge |
| **Evidence flow** | Web evidence is supplied upstream via Source F (Brave Search) and remains auditable in `sources_used` / `editor_notes` |

## Editorial Transparency

All seeded entries are marked with `editor_notes` in the format:

```
SEEDED:{source_list} — requires human review
```

Where `source_list` is a comma-separated list of source codes used (e.g.,
`wikipedia,camara_api`). This ensures that:

1. Human reviewers can trace the provenance of every seeded position.
2. The `review_candidates_positions.py` workflow requires explicit approval
   before any seeded entry is promoted to the published knowledge base.
3. Entries that were already reviewed and approved by a human editor are
   **never overwritten** by the seed script (idempotent behavior).
