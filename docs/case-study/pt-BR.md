# Caso de Uso: Portal Eleições BR 2026

## Sumário executivo
O Portal Eleições BR 2026 foi concebido como um produto de transparência pública: um portal bilíngue (pt-BR e en-US) para monitorar notícias, sentimento, pesquisas e posicionamentos de pré-candidatos da eleição presidencial de 2026. O objetivo não foi criar mais uma página opinativa, mas sim uma infraestrutura editorial reproduzível e auditável, com separação clara entre coleta de dados, processamento com IA e apresentação para o público. A proposta central é simples: qualquer pessoa deve conseguir ler uma matéria no feed, entender em que etapa ela está e auditar o caminho técnico que levou aquele conteúdo a aparecer.

O projeto combina frontend estático em React + Vite com um pipeline Python orientado a dados e automação em GitHub Actions. Em vez de depender de um único modelo de IA, a arquitetura usa cadeia de fallback multi-provider para preservar disponibilidade e controlar custo. Em vez de esconder as limitações, o portal explicita metodologia, disclaimer, fontes e estado de processamento. Em vez de acoplar deploy a infraestrutura complexa, a publicação roda em GitHub Pages com Cloudflare. O resultado é um sistema enxuto, barato, rastreável e adaptado para evoluir em fases incrementais.

## Stack e arquitetura
Do ponto de vista técnico, a stack foi escolhida para maximizar previsibilidade operacional. No frontend, React 18 com Vite e `vite-react-ssg` pré-renderiza as páginas principais para servir conteúdo estático em GitHub Pages, com boa indexação para busca tradicional e assistentes de IA. A camada de UI segue wireframes em HTML standalone definidos no ADR 000, com tokens de design padronizados (`--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border`) para manter consistência visual entre feed, dashboards, quiz, metodologia e, agora, caso de uso.

No backend de dados, Python 3.12 orquestra coleta e transformações. Os scripts de pipeline foram implementados com foco em idempotência e rastreabilidade de estado. O identificador padrão `sha256(url.encode())[:16]` evita duplicação de artigos entre execuções, e os artefatos JSON seguem os contratos em `docs/schemas/*.schema.json` e `docs/schemas/types.ts`. Isso permite que React e Python compartilhem o mesmo modelo mental de dados, reduzindo regressão por divergência de formato.

A arquitetura de publicação usa quatro estágios editoriais (`raw -> validated -> curated`, mais `irrelevant`) e privilegia disponibilidade: mesmo quando um provedor de IA falha, o pipeline não para. O conteúdo pode aparecer como `raw` com título e metadados enquanto etapas mais caras ou lentas continuam em background. Artigos detectados como não relacionados a eleições são marcados como `irrelevant` e removidos durante a sumarização. Esse desenho evita gargalo binário do tipo "publica tudo ou publica nada" e reflete melhor a natureza de dados em tempo quase real.

## Hierarquia de agentes
O processo de entrega foi estruturado com uma hierarquia de agentes explícita, documentada no PLAN e nos arquivos de handoff. O papel de Arquiteto ficou com Opus, responsável por consolidar estratégia, wireframes, ADRs e contratos de schema. O papel Tático ficou com Codex, transformando arquitetura em especificações de tarefa e critérios de verificação. O papel Operacional ficou com MiniMax, executando implementações concretas em loop disciplinado. O papel de QA ficou com Gemini, concentrado em validação, testes de interface e relatórios.

A governança operacional adotou o protocolo RALPH: Read, Analyze, List, Plan, Handle. Esse fluxo reduz improviso em tarefas extensas porque obriga leitura de contexto antes de alterar código, transforma ambiguidade em checklist, e fecha cada ciclo com validação. No projeto, RALPH não foi apenas um slogan; ele orientou a sequência de fases, a escrita de specs e a forma de tratar falhas repetidas com escalada formal.

O handoff entre camadas usa arquivos sentinela `plans/phase-NN-arch.DONE`. Esse mecanismo simples substitui integrações complexas de orquestração e deixa histórico auditável no próprio repositório. Quando uma fase fecha, o sentinela comunica que arquitetura e implementação daquela etapa estão sincronizadas e que a próxima camada pode avançar sem estado oculto. Para um projeto público e iterativo, esse padrão se mostrou pragmatismo puro: pouco acoplamento, alta rastreabilidade.

## Pipeline de ingestão
O pipeline editorial segue a metáfora de redação com três papéis. O Foca (coletor) roda em alta frequência, consumindo principalmente RSS, com expansão para sites partidários, institutos de pesquisa e YouTube. O Editor (validador) processa artigos coletados, aciona sumarização bilíngue e prepara dados para componentes analíticos. O Editor-chefe (curadoria) opera em cadência mais lenta, com foco em destaque, consistência e controles de qualidade.

As etapas de publicação são explícitas no dado: `raw`, `validated`, `curated` e `irrelevant`. No estado `raw`, o portal privilegia velocidade e transparência sobre acabamento: título, fonte e horário já podem aparecer, com sinalização de que a análise ainda está em andamento. No estado `validated`, entram sumários em dois idiomas e metadados enriquecidos. No estado `curated`, o conteúdo recebe camada adicional de priorização editorial automatizada. Artigos marcados como `irrelevant` são removidos do feed público por um mecanismo automatizado de feedback editorial. Esse funil evita bloqueios desnecessários e entrega valor incremental para o usuário.

A cadeia de IA foi redesenhada para resiliência e custo controlado com base em dados reais de produção: Ollama Cloud (Nemotron 3 Super), NVIDIA NIM (Nemotron 3 Super 120B), Ollama Cloud (MiniMax M2.5), Vertex AI (Gemini 3 Flash Preview) e MiMo V2 Flash, nessa ordem de fallback. Um circuit breaker detecta falhas cedo e um limite por execução controla o total de chamadas de IA. A regra principal é não interromper pipeline por erro de IA. Se uma chamada falha, o sistema registra, tenta o próximo provedor e segue. Se todos falham, o artigo continua no fluxo com estado coerente, em vez de ser descartado silenciosamente. Essa postura privilegia continuidade operacional e reduz risco de indisponibilidade por dependência única.

## Decisões técnicas registradas
As ADRs 000 a 006 formam a espinha dorsal de decisão deste produto. O ADR 000 formalizou wireframes como fonte de verdade visual, com mapeamento tela-componente e tokens de design consistentes. Isso reduziu retrabalho de UI porque cada fase implementa sobre referência concreta, não sobre memória subjetiva de layout.

O ADR 001 definiu hospedagem em GitHub Pages com Cloudflare, combinando custo zero, CDN e CI/CD nativo em GitHub Actions. A consequência direta foi optar por SSG em vez de SSR. Essa restrição virou vantagem: menos complexidade de runtime, mais previsibilidade de deploy, e conteúdo sempre servível como estático.

O ADR 002 registrou a estratégia de fallback multi-provider de IA. Em termos práticos, essa decisão tirou o projeto da dependência de um único fornecedor e permitiu operar com prioridade em opções gratuitas, preservando o budget pago para contingência. Também instituiu rastreamento de uso em `data/ai_usage.json`, importante para auditoria de custo e capacidade.

O ADR 003 consolidou a estratégia de internacionalização com `react-i18next`, pt-BR como default e fallback, namespaces por domínio e persistência de idioma em `localStorage`. Esse padrão permitiu ampliar cobertura bilíngue sem duplicar página por idioma, mantendo URL única e troca de conteúdo no cliente.

O ADR 004 definiu SEO e GEO com pré-render de páginas de candidato e comparação, `robots.txt` permissivo para crawlers de IA e JSON-LD por tipo de página. O portal passa a ser legível tanto por buscadores tradicionais quanto por motores generativos, sem depender de execução de JavaScript para revelar conteúdo principal.

O ADR 005 especificou neutralidade do quiz: nenhum `candidate_slug` ou `source_*` na etapa de perguntas, revelação de fontes apenas no resultado, e filtro de confiança para excluir extrações fracas. O ADR 006 tornou obrigatória a página de metodologia e o MethodologyBadge em componentes de dados, institucionalizando transparência e canal de reporte de erro.

## Lições aprendidas
A principal lição foi que produtividade com IA cresce quando o processo é explícito. "Vibe coding" sem contrato gera velocidade inicial, mas acumula débito sem controle. Neste projeto, os ganhos vieram quando prompts, ADRs, schemas e specs foram tratados como artefatos de engenharia, não como anexos. O resultado foi uma cadência de entrega por fases com menor retrabalho e menos surpresa em integração.

Outra lição foi que coordenação multiagente tem custo cognitivo real. Handoff entre papéis exige protocolo, naming consistente e disciplina de verificação. Sem isso, o time virtual se desalinharia rapidamente. O uso de sentinelas `.DONE`, plano central em `PLAN.md` e loops com limite de tentativas ajudou a transformar colaboração de agentes em fluxo confiável, em vez de cadeia opaca de mensagens.

Também ficou claro que transparência não pode ser pós-processamento. Em produtos que usam IA sobre tema sensível como eleição, metodologia, disclaimer e origem de dados devem nascer junto com o código. Quando essa camada é adiada, recuperar confiança depois custa mais caro do que implementar certo desde o início.

---

## Log operacional: correções de curso pós-1.0

Esta seção documenta o que não funcionou como esperado após a entrega inicial 1.0 e o que foi feito para corrigir o rumo. Cada entrada é datada e categorizada por subsistema. A intenção é preservar um registro honesto de tentativa e erro para referência futura e demonstrar que o sistema foi endurecido por feedback real de produção, não por planejamento teórico.

### 2026-03-10 -- Cadeia de IA: OpenRouter removido

**O que aconteceu:** O OpenRouter, originalmente segundo na cadeia de fallback de IA, atingiu 100% de falhas HTTP 429 (rate-limiting) em produção. O limite de 200 req/dia do tier gratuito foi esgotado nos primeiros ciclos de coleta, fazendo toda tentativa de sumarização cair para provedores mais lentos.

**O que fizemos:** Removemos o OpenRouter da cadeia de provedores. Promovemos NVIDIA NIM como provedor gratuito primário. Ajustamos a cadeia para: NVIDIA NIM (Nemotron 3 Super) -> Ollama Cloud -> Vertex AI -> MiMo.

**Lição:** Limites de tier gratuito que parecem generosos no papel podem ser queimados em minutos por um pipeline automatizado rodando a cada 10 minutos. A cadeia de fallback precisa ser testada sob carga real, não apenas validada com chamadas individuais.

### 2026-03-10 -- Estratégia de scraping: Playwright substituído por Bright Data

**O que aconteceu:** A extração de conteúdo de artigos usava Playwright para scraping headless. No GitHub Actions, o Playwright era pesado demais: timeouts em páginas complexas, alto consumo de memória e resultados inconsistentes em sites com paywall.

**O que fizemos:** Substituímos Playwright pela API de scraping do Bright Data para extração primária. Após múltiplas iterações para alinhar o payload da API com a documentação do Bright Data (nomes de campo errados, configuração de zona faltando), estabilizamos um fallback de três camadas: Bright Data API -> Playwright (fallback local) -> requisição HTTP simples. Foram necessários quatro commits de correção antes de funcionar de forma confiável.

**Lição:** APIs de scraping de terceiros têm formatos de payload mal documentados. A integração exige teste iterativo contra a API real, não apenas leitura de docs. Ter fallback em múltiplas camadas impediu falha total de scraping durante a transição.

### 2026-03-10 -- Pipeline de sumarização: explosão de chamadas LLM

**O que aconteceu:** O passo de sumarização fazia uma chamada LLM por artigo por execução, sem perceber se o provedor estava saudável. Quando um provedor falhava, o pipeline tentava centenas de chamadas antes de desistir, desperdiçando tempo e atingindo limites de taxa em todos os provedores.

**O que fizemos:** Reduzimos chamadas LLM pela metade verificando status do artigo antes de tentar sumarização. Adicionamos circuit breaker que detecta falhas consecutivas e interrompe chamadas restantes. Adicionamos limite por execução para controlar total de chamadas de IA. Corrigimos bug onde o circuit breaker retornava false quando nenhum provedor havia sido tentado.

**Lição:** Resiliência não é só ordem de fallback. Requer consciência de padrões de falha dentro de uma única execução. Circuit breakers e orçamento de chamadas são essenciais para pipelines que processam centenas de itens.

### 2026-03-10 -- Feeds RSS: URLs quebradas em sources.json

**O que aconteceu:** Vários URLs de feeds RSS no `sources.json` inicial estavam desatualizados ou quebrados. A coleta rodava com sucesso mas retornava zero artigos de fontes afetadas, reduzindo cobertura silenciosamente.

**O que fizemos:** Auditamos todos os 21 feeds RSS manualmente, atualizamos URLs quebradas e conectamos `_extract_rss_body` no caminho de criação de artigos (existia no código mas nunca era chamado).

**Lição:** Configuração de fontes de dados deve ser validada contra endpoints reais, não apenas assumida correta pela documentação.

### 2026-03-11 -- CI/CD: condições de corrida entre workflows

**O que aconteceu:** Com coletor rodando a cada 10 minutos, validador a cada 30 e curador a cada hora, execuções concorrentes de workflows competiam no `git push`. A estratégia de rebase causava conflitos quando dois workflows modificavam os mesmos arquivos JSON. Um modo de falha tinha `GIT_EDITOR` não configurado, fazendo o commit do rebase falhar silenciosamente.

**O que fizemos:** Substituímos `git pull --rebase` por `git pull --no-rebase` com resolução inteligente de conflitos em JSON que faz merge estrutural de arquivos baseados em array. Adicionamos grupos de concorrência para evitar execuções sobrepostas do mesmo workflow. Configuramos `GIT_EDITOR=true` como fallback. Isso reduziu falhas de frequentes para ocasionais.

**Lição:** Pipelines automatizados que escrevem no mesmo repositório a partir de múltiplos workflows precisam de estratégias de merge pensadas para o formato dos dados, não rebase genérico. Grupos de concorrência ajudam mas não eliminam todas as condições de corrida.

### 2026-03-11 -- Workflow de coleta: timeouts nos passos de IA

**O que aconteceu:** O workflow de coleta combinava coleta RSS, scraping de artigos, sumarização com IA e análise de sentimento em um único job. Quando a cadeia de provedores de IA estava lenta, o job inteiro excedia o timeout de step do GitHub Actions.

**O que fizemos:** Dividimos passos dependentes de IA em steps separados do workflow com timeouts individuais. Adicionamos limites de concorrência para evitar que múltiplas execuções de coleta sobrecarregassem provedores simultaneamente.

**Lição:** Steps monolíticos de CI que dependem de latência de API externa devem ser quebrados em chunks com timeout independente.

### 2026-03-12 -- Qualidade de conteúdo: artigos irrelevantes inundando o feed

**O que aconteceu:** O pipeline estava ingerindo artigos de fontes de notícias legítimas que não tinham relação com eleições (resultados esportivos, entretenimento, previsão do tempo). Feeds RSS de veículos generalistas contêm conteúdo misto, e a filtragem por título era permissiva demais.

**O que fizemos:** Adicionamos um quarto status de artigo: `irrelevant`. Construímos mecanismo automatizado de feedback editorial (`editor_feedback.json`) que rastreia IDs de artigos irrelevantes, palavras-chave de título bloqueadas, padrões de URL bloqueados e fontes excluídas. Modificamos o passo de sumarização para purgar artigos irrelevantes e persistir apenas os válidos. Os dados de feedback acumulam ao longo do tempo, melhorando a precisão da filtragem.

**Lição:** Coleta baseada em RSS de veículos generalistas requer filtragem ativa de conteúdo, não apenas dedup. O loop de feedback editorial não estava no design original mas se tornou essencial para qualidade do feed.

### 2026-03-12 -- Modelos de IA: interferência de modo thinking

**O que aconteceu:** Após atualizar para Kimi K2.5 e MiniMax M2.5, ambos os modelos retornavam texto de raciocínio chain-of-thought dentro das respostas, poluindo resumos com tokens de raciocínio interno.

**O que fizemos:** Adicionamos configuração `extra_body` para desabilitar modo thinking em ambos os modelos. Isso exigiu formatos de parâmetros específicos por provedor que diferiam do padrão da API compatível com OpenAI.

**Lição:** APIs "compatíveis com OpenAI" não são verdadeiramente compatíveis. Cada provedor tem peculiaridades em como lida com parâmetros estendidos. Testes devem cobrir formato de saída, não apenas conectividade.

### 2026-03-12 -- Cadeia de provedores de IA: reordenada por confiabilidade real

**O que aconteceu:** Após vários dias de dados de produção em `ai_usage.json`, descobrimos que Ollama Cloud (Nemotron 3 Super) tinha melhor disponibilidade e tempos de resposta mais rápidos que o endpoint direto da NVIDIA NIM. A ordenação original era baseada em qualidade teórica do provedor, não em dados empíricos.

**O que fizemos:** Promovemos Ollama Cloud para posição primária. Rebaixamos NVIDIA NIM para segunda posição. Atualizamos Vertex AI de Gemini 2.5 Flash Lite para Gemini 3 Flash Preview. Aumentamos max output tokens para tarefas de geração de conteúdo.

**Lição:** A ordenação da cadeia de provedores deve ser orientada por dados. Instrumentar uso desde o dia um e reordenar com base em taxas reais de sucesso e latência.

### 2026-03-12 -- Frontend: roteamento de navegação e re-render infinito

**O que aconteceu:** Após as mudanças de polish mobile da Phase 15, o componente de navegação entrou em loop infinito de re-render ao trocar entre rotas. A causa raiz foi um problema de sincronização de estado entre o router e o seletor de idioma.

**O que fizemos:** Corrigimos a sincronização de roteamento para evitar atualizações circulares de estado. Resolvemos problemas de caminho de fetch de dados onde `useData` buscava de `/data/` ao invés do base path do GitHub Pages `/eleicoes-2026-monitor/data/`. Corrigimos conteúdo stub ainda exibido para features já implementadas.

**Lição:** Deploy de site estático em subpath (project sites do GitHub Pages) exige tratamento consistente de base path em todos os hooks de fetch de dados, não apenas na configuração de rotas.

### 2026-03-12 -- Relevância de conteúdo: filtro de candidatos muito restritivo

**O que aconteceu:** O filtro de relevância de candidatos rejeitava artigos sobre dinâmica eleitoral que não mencionavam nomes específicos, como artigos sobre coalizões de "terceira via" ou cenários de "segundo turno".

**O que fizemos:** Relaxamos a regra de relevância de candidatos e adicionamos palavras-chave de alto sinal eleitoral (`turno`, `terceira via`, `coligação`, `chapa`) à lista de permissão. Artigos que correspondem a essas palavras-chave passam o filtro de relevância mesmo sem menções explícitas a candidatos.

**Lição:** Cobertura política não é sempre centrada em candidatos. Infraestrutura eleitoral, dinâmicas de coalizão e tópicos procedimentais são conteúdo relevante que um filtro baseado em nomes vai perder.

### 2026-03-13 -- YouTube API: esgotamento de cota

**O que aconteceu:** O script de coleta do YouTube fazia uma busca por candidato por ciclo de coleta. Com 9 candidatos e ciclo de 10 minutos, isso consumia a cota diária da API do YouTube em horas.

**O que fizemos:** Otimizamos para uma única busca combinada usando operadores OR entre todos os nomes de candidatos mais "eleições 2026". Adicionamos throttle de 30 minutos via arquivo de estado para evitar chamadas excessivas à API. A associação de candidatos agora é inferida do título e descrição do vídeo ao invés de buscas dedicadas por candidato.

**Lição:** Cota de API é uma restrição de primeira classe para coleta automatizada. Projetar queries para mínimo de chamadas primeiro, depois refinar precisão.

### 2026-03-13 -- Segurança: chaves de API em logs de erro

**O que aconteceu:** Logs de erro do pipeline incluíam chaves de API completas nas mensagens de erro quando chamadas a provedores falhavam. Esses logs eram commitados em `data/pipeline_errors.json` e visíveis no repositório público.

**O que fizemos:** Adicionamos padrões de sanitização para redatar chaves de API, tokens e credenciais de todas as mensagens de erro antes de serem escritas em arquivos de log.

**Lição:** Logging de erros em repositórios públicos deve sanitizar toda saída por padrão. Isso deveria ter sido requisito do dia um, não correção pós-lançamento.

### 2026-03-13 -- Institutos de pesquisa: cobertura ampliada

**O que aconteceu:** Os 6 institutos de pesquisa iniciais não incluíam vários players ativos no ciclo eleitoral de 2026. Verificações manuais identificaram Futura Inteligência, Ipsos, MDA e Ideia como institutos já publicando dados relevantes.

**O que fizemos:** Adicionamos os quatro novos institutos a `data/sources.json` com aliases, URLs e configuração de schema adequados. Atualizamos os scripts de coleta de pesquisas para lidar com as novas fontes.

**Lição:** Cobertura de fontes deve ser tratada como configuração viva, não setup único. Auditorias regulares contra o cenário político atual são necessárias.

---

## Números do projeto
No recorte atual (2026-03-13), os números consolidados são:

- 17 fases completas (16 principais + Phase 17 extensão Vertex AI Search).
- 189 commits no histórico do repositório.
- 351 arquivos versionados.
- 21 fontes RSS ativas em `data/sources.json`, além de 8 fontes partidárias e 10 institutos de pesquisa.
- 9 candidatos modelados em `data/candidates.json`.
- 6 workflows no GitHub Actions: collect (10min), validate (30min), curate (horário), deploy, update-quiz, watchdog.
- 4 status de artigo: `raw`, `validated`, `curated`, `irrelevant`.
- Mecanismo automatizado de feedback editorial filtrando conteúdo irrelevante.
- Circuit breaker e limites por execução de chamadas de IA para resiliência do pipeline.
- 109 commits de endurecimento operacional pós-1.0 desde o fechamento de QA da Phase 16.

Esses números importam menos como marketing e mais como prova de que o sistema foi publicado, operou sob condições reais e foi corrigido iterativamente com base em feedback de produção.

## Status atual
O portal está no ar e operando continuamente. A cadeia de provedores de IA foi reordenada com base em dados empíricos de confiabilidade. A qualidade de conteúdo melhorou com o loop de feedback editorial. Condições de corrida no CI/CD são gerenciadas mas não totalmente eliminadas. O sistema processa centenas de artigos diariamente de 21 fontes RSS, 8 sites partidários, 10 institutos de pesquisa e YouTube, com sumarização bilíngue automatizada, análise de sentimento e extração de posições para quiz.

Os próximos focos são monitorar estabilidade de longo prazo dos provedores, expandir regras de feedback editorial e avaliar se a integração do Vertex AI Search (Phase 17) entrega valor mensurável para o usuário.
