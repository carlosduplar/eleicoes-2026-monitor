# ADR 002 — Provedores de IA: Cadeia de Fallback Multi-Provider

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)

## Contexto

O pipeline precisa de modelos de linguagem para sumarizacao, analise de sentimento, e extracao de posicoes (quiz). Orcamento mensal: ~$10 (Google AI Pro). Todos os providers devem ser compativeis com OpenAI Python SDK via `base_url` swap para zero lock-in.

## Decisao

Cadeia de fallback hierarquica: gratuitos primeiro, pagos como ultimo recurso.

## Cadeia de Providers

| Prioridade | Provider | base_url | Modelo | Custo | Limite |
|-----------|----------|----------|--------|-------|--------|
| 1 | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `qwen/qwen3.5-397b-a17b` | Gratuito | Creditos dev |
| 2 | OpenRouter | `https://openrouter.ai/api/v1` | `arcee-ai/trinity-large-preview:free` | Gratuito | 200 req/dia, 20/min |
| 3 | Ollama Cloud | `https://ollama.com/v1` | `minimax-m2.5:cloud` | Gratuito | Limites horarios |
| 4 | Vertex AI | env `VERTEX_BASE_URL` | `google/gemini-2.5-flash-lite-001` | $10/mes (AI Pro) | Budget cap |
| 5 | MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2-flash` | Pago | Sem limite fixo |

## Selecao de Modelo por Tarefa (NVIDIA NIM)

| Tarefa | Modelo | Justificativa |
|--------|--------|--------------|
| Sumarizacao | `qwen/qwen3.5-397b-a17b` | Melhor qualidade geral |
| Sentimento | `minimaxai/minimax-m2.5` | Melhor analise contextual |
| Multilingue | `moonshotai/kimi-k2.5` | Melhor pt-BR/EN |
| Extracao quiz | `qwen/qwen3-235b-a22b-thinking-2507` | Raciocinio para extrair posicoes |

## Hierarquia da Redacao (Newsroom)

| Papel | Frequencia | Modelo Primario | Fallback |
|-------|-----------|----------------|---------|
| Foca (coletor) | 10 min | Qwen3-235B-A22B (NIM) | Ministral-3B (OpenRouter) |
| Editor (validador) | 30 min | Qwen3-235B-Thinking (OpenRouter) | Gemini 2.5 Flash Lite (Vertex) |
| Editor-chefe (curador) | ~90 min | Gemini 2.5 Flash Lite (Vertex) | Kimi-K2.5 (NIM) |

## Rastreador de Uso

`data/ai_usage.json` — incrementado a cada chamada com chave `{provider}_{YYYY-MM-DD}`.
Usado para:
- Verificar limite diario do OpenRouter (200 req/dia)
- Monitorar custo Vertex AI
- Metricas no watchdog diario

## Secrets no GitHub

| Secret | Provider | Obrigatorio |
|--------|----------|------------|
| `NVIDIA_API_KEY` | NVIDIA NIM | Sim (Fase 2) |
| `OPENROUTER_API_KEY` | OpenRouter | Sim (Fase 2) |
| `OLLAMA_API_KEY` | Ollama Cloud | Sim (Fase 2) |
| `VERTEX_ACCESS_TOKEN` | Google Vertex AI | Sim (Fase 6) |
| `VERTEX_BASE_URL` | Google Vertex AI | Sim (Fase 6) |
| `XIAOMI_MIMO_API_KEY` | Xiaomi MiMo | Opcional |
| `TWITTER_BEARER_TOKEN` | Twitter API v2 | Opcional (Fase 14) |
| `YOUTUBE_API_KEY` | YouTube Data v3 | Opcional (Fase 14) |

## Regras de Implementacao

1. Todos os providers usam `openai.OpenAI(api_key=key, base_url=url)` — zero lock-in
2. Erros de IA **nunca** interrompem o pipeline (`try/except` + log + proximo provider)
3. `summarize_article()` sempre retorna ambos idiomas (`pt-BR` + `en-US`)
4. `extract_candidate_position()` retorna `null` se evidencia insuficiente (nao inventa)
5. Uso rastreado em `data/ai_usage.json` para auditoria e billing

## Consequencias

- Pipeline funciona com qualquer combinacao de providers disponiveis
- Se todos falharem, artigo permanece como `status: raw` (sem resumo, mas visivel no feed)
- Custo mensal maximo estimado: $10 (Vertex AI Pro) + eventual MiMo se todos os gratuitos falharem
- Transparencia: `_ai_provider` e `_ai_model` em cada artigo rastreiam qual modelo gerou o conteudo
