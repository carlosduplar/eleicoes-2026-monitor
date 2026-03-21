# ADR 002 — Provedores de IA: Cadeia de Fallback Multi-Provider

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)  
**Atualizado:** 2026-03-21 - Gemini removido de tarefas de alta qualidade; Gemini 3.1 Flash Lite como fallback gratuito na cadeia padrao; seed de candidatos adicionado

## Contexto

O pipeline precisa de modelos de linguagem para sumarizacao, analise de sentimento, e extracao de posicoes (quiz). Orcamento mensal: ~$10 (Google AI Pro). Todos os providers devem ser compativeis com OpenAI Python SDK via `base_url` swap para zero lock-in.

## Decisao

Cadeia de fallback hierarquica: gratuitos primeiro, pagos como ultimo recurso.

## Cadeia de Providers

| Prioridade | Provider | base_url | Modelo | Custo | Limite |
|-----------|----------|----------|--------|-------|--------|
| 1a | NVIDIA NIM (primary) | `https://integrate.api.nvidia.com/v1` | `moonshotai/kimi-k2.5` | Gratuito | Creditos dev |
| 1b | NVIDIA NIM (fallback 1) | `https://integrate.api.nvidia.com/v1` | `minimaxai/minimax-m2.5` | Gratuito | Creditos dev |
| 1c | NVIDIA NIM (fallback 2) | `https://integrate.api.nvidia.com/v1` | `nvidia/nemotron-3-super-120b-a12b` | Gratuito | Creditos dev |
| 2a | Ollama Cloud (primary) | `https://ollama.com/v1` | `kimi-k2.5:cloud` | Gratuito | Limites horarios |
| 2b | Ollama Cloud (fallback 1) | `https://ollama.com/v1` | `minimax-m2.5:cloud` | Gratuito | Limites horarios |
| 2c | Ollama Cloud (fallback 2) | `https://ollama.com/v1` | `nemotron-3-super:cloud` | Gratuito | Limites horarios |
| 3 | OpenRouter | `https://openrouter.ai/api/v1` | `nvidia/nemotron-3-super-120b-a12b:free` | Gratuito | 200 req/dia |
| 4 | Vertex AI | env `VERTEX_BASE_URL` | `gemini-3-flash-preview` (override via `VERTEX_MODEL_OVERRIDE`) | $10/mes (AI Pro) | Budget cap |
| 5 | MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2-flash` | Pago | Sem limite fixo |

## Selecao de Modelo por Tarefa (NVIDIA NIM)

| Tarefa | Modelo (NIM) | Modelo (Ollama) | Justificativa |
|--------|-------------|----------------|--------------|
| Sumarizacao | `nvidia/nemotron-3-super-120b-a12b` | `nemotron-3-super:cloud` | Qualidade geral, multilingue |
| Sentimento | `nvidia/nemotron-3-super-120b-a12b` | `nemotron-3-super:cloud` | Analise contextual |
| Extracao posicoes | `minimaxai/minimax-m2.5` | `kimi-k2.5:cloud` | Raciocinio para posicoes |
| Geracao quiz | `minimaxai/minimax-m2.5` | `kimi-k2.5:cloud` | Geracao de JSON estruturado |
| Validacao quiz | `minimaxai/minimax-m2.5` | `kimi-k2.5:cloud` | Validacao estruturada |

## Modelos por Provider (2026-03-21)

### NVIDIA NIM
- **Sumarizacao/Sentimento**: `nvidia/nemotron-3-super-120b-a12b`
- **Quiz/Posicoes**: `minimaxai/minimax-m2.5`

### Ollama Cloud
- **Sumarizacao/Sentimento**: `nemotron-3-super:cloud`
- **Quiz/Posicoes (primario)**: `kimi-k2.5:cloud`

### Gemini (Google AI — gratuito)
- **Fallback padrao**: `gemini-3.1-flash-lite-preview` (via `https://generativelanguage.googleapis.com/v1beta/openai/`)
- Nao usado em tarefas de alta qualidade

### Vertex AI (pago)
- **Modelo**: `gemini-3-flash-preview` (override via `VERTEX_MODEL_OVERRIDE`)
- Fallback final para todas as tarefas

### OpenRouter
- Removido da cadeia (rate-limiting 200 req/dia insuficiente para pipeline automatizado)

## Hierarquia da Redacao (Newsroom)

| Papel | Frequencia | Modelo Primario | Fallback |
|-------|-----------|----------------|---------|
| Foca (coletor) | 10 min | Nemotron 3 Super (NVIDIA NIM) | Nemotron 3 Super (Ollama Cloud) |
| Editor (validador) | 30 min | Nemotron 3 Super (NVIDIA NIM) | Gemini 3.1 Flash Lite (Google AI) |
| Editor-chefe (curador) | ~90 min | Kimi K2.5 (Ollama Cloud) | MiniMax M2.5 (NVIDIA NIM) |

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
