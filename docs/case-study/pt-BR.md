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
