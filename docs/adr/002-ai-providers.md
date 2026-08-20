# ADR 002 — Provedores de IA: Cadeia de Fallback Multi-Provider

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)  
**Atualizado:** 2026-08-20 - Poolside (Laguna S 2.1) e o provider primario para todas as tarefas; Google AI Studio (Gemini), Vertex AI e Xiaomi MiMo removidos do codigo e dos workflows.

## Contexto

O pipeline precisa de modelos de linguagem para sumarizacao, analise de sentimento, e extracao de posicoes (quiz). Orcamento mensal: ~$10 (Google AI Pro). Todos os providers devem ser compativeis com OpenAI Python SDK via `base_url` swap para zero lock-in.

## Decisao

Cadeia de fallback hierarquica com Alto Raciocinio (High Reasoning) habilitado para maxima fidelidade ideologica e precisao em JSON estruturado: gratuitos primeiro, pagos como ultimo recurso.

## Cadeia de Providers por Tarefa

### Todas as tarefas (`summarization`, `sentiment`, `multilingual`, `positions_extract`, `quiz_generate`, `quiz_extract`, `quiz_validate`)

| Prioridade | Provider | base_url | Modelo | Modo Raciocínio | Referencia | Custo |
|---|---|---|---|---|---|---|
| 1 | Poolside | `https://inference.poolside.ai/v1` | `poolside/laguna-s-2.1` | Reasoning (padrão) | Terminal-Bench 2.1: **70.2** | Gratuito |
| 2 | Ollama Cloud | `https://ollama.com/v1` | `minimax-m3:cloud` | High Reasoning | AA Intel: **45.4** | Gratuito |
| 3 | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `minimaxai/minimax-m3` | High Reasoning | AA Intel: **45.4** | Gratuito (Créditos dev) |
| 4 | OpenRouter | `https://openrouter.ai/api/v1` | `openrouter/free` | Provider-dependent | — | Gratuito |

> Poolside Laguna S 2.1 nao esta indexado no Artificial Analysis (agentic index); a posicao e ancorada pelo Terminal-Bench 2.1 oficial (70.2), que e um dos componentes do indice AA.

## Hierarquia da Redacao (Newsroom)

| Papel | Frequencia | Modelo Primario | Fallbacks |
|---|---|---|---|
| Foca (coletor) | 10 min | Laguna S 2.1 (Poolside) | MiniMax-M3 (Ollama) $\rightarrow$ MiniMax-M3 (NIM) $\rightarrow$ OpenRouter/free |
| Editor (validador) | 30 min | Laguna S 2.1 (Poolside) | MiniMax-M3 (Ollama) $\rightarrow$ MiniMax-M3 (NIM) $\rightarrow$ OpenRouter/free |
| Editor-chefe (curador) | ~90 min | Laguna S 2.1 (Poolside) | MiniMax-M3 (Ollama) $\rightarrow$ MiniMax-M3 (NIM) $\rightarrow$ OpenRouter/free |

## Rastreador de Uso

`data/ai_usage.json` — incrementado a cada chamada com chave `{provider}_{YYYY-MM-DD}`.
Usado para:
- Metricas no watchdog diario

## Secrets no GitHub

| Secret | Provider | Obrigatorio |
|--------|----------|------------|
| `POOLSIDE_API_KEY` | Poolside | Sim |
| `NVIDIA_API_KEY` | NVIDIA NIM | Sim (Fase 2) |
| `OPENROUTER_API_KEY` | OpenRouter | Sim (Fase 2) |
| `OLLAMA_API_KEY` | Ollama Cloud | Sim (Fase 2) |
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

- `POOLSIDE_API_KEY`
- `NVIDIA_API_KEY`
- `OPENROUTER_API_KEY`
- `OLLAMA_API_KEY`

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
- Custo mensal maximo estimado: $0 (todos os providers da cadeia sao gratuitos)
- Transparencia: `_ai_provider` e `_ai_model` em cada artigo rastreiam qual modelo gerou o conteudo
