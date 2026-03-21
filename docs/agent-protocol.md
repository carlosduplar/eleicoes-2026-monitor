# Protocolo de Agentes — eleicoes-2026-monitor

## Papeis

| Agente | Ferramenta | Nivel | Responsabilidade |
|--------|-----------|-------|-----------------|
| **Arquiteto** | Claude Opus 4.6 (Copilot CLI) | Estrategico | Le requisitos de negocio, toma decisoes arquiteturais, cria PLAN.md, define schemas (JSON Schema + TS types) na Fase 1, wireframes Stitch/HTML |
| **Tatico** | GPT-5.3-Codex xhigh (Copilot CLI) | Tatico | Le plano do Arquiteto, subdivide em task specs detalhadas em `tasks/phaseNN/`, cria cenarios de teste com casos de borda |
| **Operacional** | MiniMax M2.5 (OpenCode) | Operacional | Recebe task specs do Tatico, implementa em RALPH loops ate todos os testes passarem ou limite de escalacao atingido |
| **QA** | Gemini 3 Flash (Gemini CLI) | Qualidade | Executa testes com integracao nativa Playwright + Chrome, reporta falhas estruturadas de volta ao Tatico |

## Papel transversal — Context7

Todo agente consulta Context7 antes de qualquer decisao de biblioteca, API, ou dependencia. Regra obrigatoria, nao recomendacao.

## Papel transversal — Watchdog pos-deploy

Gemini 3 Flash ingere logs dos ultimos 7 dias de todos os workflows e gera `data/pipeline_health.json`. Executado como `watchdog.yml` (cron `0 6 * * *`).

## Papel transversal — Schema Guardian

Opus define e commita `docs/schemas/` com JSON Schema + TypeScript types para todos os arquivos em `data/` antes de qualquer implementacao. Codex valida conformidade antes de escrever task specs que consumam esses dados.

## Protocolo de Handoff por Arquivo

```
plans/
  phase-NN-arch.md        <- output do Arquiteto (Opus)
  phase-NN-arch.DONE      <- sinal de conclusao do Arquiteto

tasks/
  phase-NN/
    task-01-spec.md       <- output do Tatico (Codex): spec + cenarios de teste
    task-01-spec.DONE     <- sinal de conclusao do Tatico
    ESCALATION.md         <- escrito pelo Operacional quando atinge limite

qa/
  phase-NN-report.json    <- output do QA (Gemini): falhas estruturadas
  phase-NN-report.DONE    <- sinal de aprovacao do QA
```

## Protocolo de Escalacao — RALPH loop

O Operacional (MiniMax) opera em RALPH loops: **R**un tests, **A**ssert results, **L**oop se falha, **P**ush se passa, **H**alt se escalacao.

### Criterio de ejecao

```
SE tentativas > 3 E mesmo erro nas ultimas 2 tentativas:
  escrever tasks/phase-NN/ESCALATION.md com:
    - erro completo + stack trace
    - numero de tentativas
    - hipotese da causa (spec ambigua? dependencia quebrada? bug de logica?)
  NAO tentar novamente
  aguardar revisao do Tatico (Codex) na spec
```

## Orquestracao Local — conductor.ps1

Script PowerShell 7 que sequencia invocacoes via flags `--no-interactive` dos CLIs e monitora arquivos de sinalizacao (`.DONE`). Tarefas sem dependencia usam `Start-Job` para paralelismo.

## Pipeline de Ingestao — Hierarquia de Redacao

| Papel | Metafora | Frequencia | Modelo Primario | Fallback |
|-------|----------|-----------|----------------|---------|
| **Foca** | Reporter | 10 min | Nemotron 3 Super (NVIDIA NIM) | Nemotron 3 Super (Ollama Cloud) |
| **Editor** | Editor de secao | 30 min | Nemotron 3 Super (NVIDIA NIM) | Gemini 3.1 Flash Lite (Google AI) |
| **Editor-chefe** | Editor executivo | ~90 min | Kimi K2.5 (Ollama Cloud) | MiniMax M2.5 (NVIDIA NIM) |

### Fluxo de status dos artigos

```
raw (Foca: titulo + fonte + relevance_score)
  -> validated (Editor: resumo bilingue + sentimento + confidence_score)
    -> curated (Editor-chefe: prominence_score + badge destaque)
```

### Decisao de UI — Publicacao em estagios (Opcao A)

- `raw`: aparece no feed com titulo + fonte + "analise em andamento" (sem resumo IA)
- `validated`: resumo completo + tags + sentiment badge + MethodologyBadge
- `curated`: tudo acima + badge "Destaque da Redacao" + posicao elevada no feed

### Protocolo de falha entre tiers

- **Foca falha:** artigos nao coletados neste ciclo. Proximo ciclo retenta.
- **Editor falha:** artigos ficam em `status: raw`. Feed nao atualiza com novos resumos.
- **Editor-chefe falha:** quiz.json nao atualizado, briefing semanal nao gerado.
- **Qualquer falha:** logada em `data/pipeline_errors.json`. MethodologyBadge exibe "Ultimo processamento: X horas atras".
