# ADR 002 — Provedores de IA: Cadeia de Fallback Multi-Provider

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)  
**Atualizado:** 2026-08-19 - Modelos atualizados com benchmarks do Artificial Analysis; GLM-5.2 primário para Quiz/Posições no NVIDIA NIM; MiniMax-M3 no Ollama e NVIDIA; Gemini 3.7 Flash no Google/Vertex; Nemotron 3 Ultra 550B no Ingestion; Kimi removido; Alto Raciocínio (High Reasoning) habilitado.

## Contexto

O pipeline precisa de modelos de linguagem para sumarizacao, analise de sentimento, e extracao de posicoes (quiz). Orcamento mensal: ~$10 (Google AI Pro). Todos os providers devem ser compativeis com OpenAI Python SDK via `base_url` swap para zero lock-in.

## Decisao

Cadeia de fallback hierarquica com Alto Raciocinio (High Reasoning) habilitado para maxima fidelidade ideologica e precisao em JSON estruturado: gratuitos primeiro, pagos como ultimo recurso.

## Cadeia de Providers por Tarefa

### Quiz, Posições e Validação (`positions_extract`, `quiz_generate`, `quiz_validate`)

| Prioridade | Provider | base_url | Modelo | Modo Raciocínio | AA Intel Index | Custo |
|---|---|---|---|---|---|---|
| 1 | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `z-ai/glm-5.2` | High Reasoning | **52.6** | Gratuito (Créditos dev) |
| 2 | Ollama Cloud | `https://ollama.com/v1` | `minimax-m3:cloud` | High Reasoning | **45.4** | Gratuito |
| 3 | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `minimaxai/minimax-m3` | High Reasoning | **45.4** | Gratuito (Créditos dev) |
| 4 | Vertex AI | env `VERTEX_BASE_URL` | `gemini-3.7-flash` | High (`thinkingBudget: 2048`) | **56.0** | $10/mês (AI Pro) |

### Ingestion, Sumarização e Sentimento (`summarization`, `sentiment`, `multilingual`)

| Prioridade | Provider | base_url | Modelo | Modo Raciocínio | AA Intel Index | Custo |
|---|---|---|---|---|---|---|
| 1 | NVIDIA NIM (primary) | `https://integrate.api.nvidia.com/v1` | `nvidia/nemotron-3-ultra-550b-a55b` | High Reasoning | **38.3** | Gratuito (Créditos dev) |
| 2 | NVIDIA NIM (fallback) | `https://integrate.api.nvidia.com/v1` | `nvidia/nemotron-3-super-120b-a12b` | High Reasoning | **25.7** | Gratuito (Créditos dev) |
| 3 | Ollama Cloud | `https://ollama.com/v1` | `nemotron-3-ultra:cloud` | High Reasoning | **38.3** | Gratuito |
| 4 | Ollama Cloud | `https://ollama.com/v1` | `minimax-m3:cloud` | High Reasoning | **45.4** | Gratuito |
| 5 | Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.7-flash` | High Reasoning | **56.0** | Gratuito (Free tier) |
| 6 | Vertex AI | env `VERTEX_BASE_URL` | `gemini-3.7-flash` | High (`thinkingBudget: 2048`) | **56.0** | $10/mês (AI Pro) |
| 7 | Xiaomi MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2.5` | Standard | **38.0** | Pago (Emergency fallback) |

## Hierarquia da Redacao (Newsroom)

| Papel | Frequencia | Modelo Primario | Fallbacks |
|---|---|---|---|
| Foca (coletor) | 10 min | Nemotron 3 Ultra 550B (NVIDIA NIM) | Nemotron 3 Super (NVIDIA NIM) $\rightarrow$ Nemotron 3 Ultra (Ollama) |
| Editor (validador) | 30 min | Nemotron 3 Ultra 550B (NVIDIA NIM) | Gemini 3.7 Flash (Google AI) $\rightarrow$ Vertex AI |
| Editor-chefe (curador) | ~90 min | GLM-5.2 (NVIDIA NIM) | MiniMax-M3 (Ollama / NIM) $\rightarrow$ Gemini 3.7 Flash |

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

## Implementation Notes

### Variaveis de ambiente obrigatorias

- `NVIDIA_API_KEY`
- `OPENROUTER_API_KEY`
- `OLLAMA_API_KEY`
- `VERTEX_ACCESS_TOKEN`
- `VERTEX_BASE_URL`
- `XIAOMI_MIMO_API_KEY`

### Arquivo de uso

- Caminho: `data/ai_usage.json`
- Formato: objeto JSON com chaves `{provider}_{YYYY-MM-DD}` e valor inteiro acumulado
- Leitura: `_load_usage()`
- Escrita: `_save_usage()` (cria diretorio pai automaticamente com `mkdir(parents=True, exist_ok=True)`)

### Como adicionar um novo provider na cadeia

1. Adicionar a configuracao no retorno de `_provider_chain_for_task()` com `name`, `base_url`, `key_env`, `model`, `paid` e limites opcionais.
2. Declarar o secret correspondente no ambiente (GitHub Actions/local) e referenciar em `key_env`.
3. Se houver limite de cota, adicionar a regra de skip em `_call_with_fallback_for_task()`.
4. Manter o cliente padrao `openai.OpenAI(api_key=key, base_url=url)` para preservar zero lock-in.

## Consequencias

- Pipeline funciona com qualquer combinacao de providers disponiveis
- Se todos falharem, artigo permanece como `status: raw` (sem resumo, mas visivel no feed)
- Custo mensal maximo estimado: $10 (Vertex AI Pro) + eventual MiMo se todos os gratuitos falharem
- Transparencia: `_ai_provider` e `_ai_model` em cada artigo rastreiam qual modelo gerou o conteudo
