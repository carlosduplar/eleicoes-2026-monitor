# Caso de Uso: Portal Eleicoes BR 2026

## Sumario executivo
O Portal Eleicoes BR 2026 foi concebido como um produto de transparencia publica: um portal bilingue (pt-BR e en-US) para monitorar noticias, sentimento, pesquisas e posicionamentos de pre-candidatos da eleicao presidencial de 2026. O objetivo nao foi criar mais uma pagina opinativa, mas sim uma infraestrutura editorial reproduzivel e auditavel, com separacao clara entre coleta de dados, processamento com IA e apresentacao para o publico. A proposta central e simples: qualquer pessoa deve conseguir ler uma materia no feed, entender em que etapa ela esta e auditar o caminho tecnico que levou aquele conteudo a aparecer.

O projeto combina frontend estatico em React + Vite com um pipeline Python orientado a dados e automacao em GitHub Actions. Em vez de depender de um unico modelo de IA, a arquitetura usa cadeia de fallback multi-provider para preservar disponibilidade e controlar custo. Em vez de esconder as limitacoes, o portal explicita metodologia, disclaimer, fontes e estado de processamento. Em vez de acoplar deploy a infraestrutura complexa, a publicacao roda em GitHub Pages com Cloudflare. O resultado e um sistema enxuto, barato, rastreavel e adaptado para evoluir em fases incrementais.

## Stack e arquitetura
Do ponto de vista tecnico, a stack foi escolhida para maximizar previsibilidade operacional. No frontend, React 18 com Vite e `vite-react-ssg` pre-renderiza as paginas principais para servir conteudo estatico em GitHub Pages, com boa indexacao para busca tradicional e assistentes de IA. A camada de UI segue wireframes em HTML standalone definidos no ADR 000, com tokens de design padronizados (`--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border`) para manter consistencia visual entre feed, dashboards, quiz, metodologia e, agora, caso de uso.

No backend de dados, Python 3.12 orquestra coleta e transformacoes. Os scripts de pipeline foram implementados com foco em idempotencia e rastreabilidade de estado. O identificador padrao `sha256(url.encode())[:16]` evita duplicacao de artigos entre execucoes, e os artefatos JSON seguem os contratos em `docs/schemas/*.schema.json` e `docs/schemas/types.ts`. Isso permite que React e Python compartilhem o mesmo modelo mental de dados, reduzindo regressao por divergencia de formato.

A arquitetura de publicacao usa tres estagios editoriais (`raw -> validated -> curated`) e privilegia disponibilidade: mesmo quando um provedor de IA falha, o pipeline nao para. O conteudo pode aparecer como `raw` com titulo e metadados enquanto etapas mais caras ou lentas continuam em background. Esse desenho evita gargalo binario do tipo "publica tudo ou publica nada" e reflete melhor a natureza de dados em tempo quase real.

## Hierarquia de agentes
O processo de entrega foi estruturado com uma hierarquia de agentes explicita, documentada no PLAN e nos arquivos de handoff. O papel de Arquiteto ficou com Opus, responsavel por consolidar estrategia, wireframes, ADRs e contratos de schema. O papel Tatico ficou com Codex, transformando arquitetura em especificacoes de tarefa e criterios de verificacao. O papel Operacional ficou com MiniMax, executando implementacoes concretas em loop disciplinado. O papel de QA ficou com Gemini, concentrado em validacao, testes de interface e relatorios.

A governanca operacional adotou o protocolo RALPH: Read, Analyze, List, Plan, Handle. Esse fluxo reduz improviso em tarefas extensas porque obriga leitura de contexto antes de alterar codigo, transforma ambiguidade em checklist, e fecha cada ciclo com validacao. No projeto, RALPH nao foi apenas um slogan; ele orientou a sequencia de fases, a escrita de specs e a forma de tratar falhas repetidas com escalacao formal.

O handoff entre camadas usa arquivos sentinela `plans/phase-NN-arch.DONE`. Esse mecanismo simples substitui integracoes complexas de orquestracao e deixa historico auditavel no proprio repositorio. Quando uma fase fecha, o sentinela comunica que arquitetura e implementacao daquela etapa estao sincronizadas e que a proxima camada pode avancar sem estado oculto. Para um projeto publico e iterativo, esse padrao se mostrou pragmatismo puro: pouco acoplamento, alta rastreabilidade.

## Pipeline de ingestao
O pipeline editorial segue a metafora de redacao com tres papeis. O Foca (coletor) roda em alta frequencia, consumindo principalmente RSS, com expansao para sites partidarios e outras fontes estruturadas. O Editor (validador) processa artigos coletados, aciona sumarizacao bilingue e prepara dados para componentes analiticos. O Editor-chefe (curadoria) opera em cadencia mais lenta, com foco em destaque, consistencia e controles de qualidade.

As etapas de publicacao sao explicitas no dado: `raw`, `validated` e `curated`. No estado `raw`, o portal privilegia velocidade e transparencia sobre acabamento: titulo, fonte e horario ja podem aparecer, com sinalizacao de que a analise ainda esta em andamento. No estado `validated`, entram sumarios em dois idiomas e metadados enriquecidos. No estado `curated`, o conteudo recebe camada adicional de priorizacao editorial automatizada. Esse funil evita bloqueios desnecessarios e entrega valor incremental para o usuario.

A cadeia de IA foi desenhada para resiliencia e custo controlado: NVIDIA NIM, OpenRouter, Ollama Cloud, Vertex AI e MiMo, nessa ordem de fallback. A regra principal e nao interromper pipeline por erro de IA. Se uma chamada falha, o sistema registra, tenta o proximo provedor e segue. Se todos falham, o artigo continua no fluxo com estado coerente, em vez de ser descartado silenciosamente. Essa postura privilegia continuidade operacional e reduz risco de indisponibilidade por dependencia unica.

## Decisoes tecnicas registradas
As ADRs 000 a 006 formam a espinha dorsal de decisao deste produto. O ADR 000 formalizou wireframes como fonte de verdade visual, com mapeamento tela-componente e tokens de design consistentes. Isso reduziu retrabalho de UI porque cada fase implementa sobre referencia concreta, nao sobre memoria subjetiva de layout.

O ADR 001 definiu hospedagem em GitHub Pages com Cloudflare, combinando custo zero, CDN e CI/CD nativo em GitHub Actions. A consequencia direta foi optar por SSG em vez de SSR. Essa restricao virou vantagem: menos complexidade de runtime, mais previsibilidade de deploy, e conteudo sempre servivel como estatico.

O ADR 002 registrou a estrategia de fallback multi-provider de IA. Em termos praticos, essa decisao tirou o projeto da dependencia de um unico fornecedor e permitiu operar com prioridade em opcoes gratuitas, preservando o budget pago para contingencia. Tambem instituiu rastreamento de uso em `data/ai_usage.json`, importante para auditoria de custo e capacidade.

O ADR 003 consolidou a estrategia de internacionalizacao com `react-i18next`, pt-BR como default e fallback, namespaces por dominio e persistencia de idioma em `localStorage`. Esse padrao permitiu ampliar cobertura bilingue sem duplicar pagina por idioma, mantendo URL unica e troca de conteudo no cliente.

O ADR 004 definiu SEO e GEO com pre-render de paginas de candidato e comparacao, `robots.txt` permissivo para crawlers de IA e JSON-LD por tipo de pagina. O portal passa a ser legivel tanto por buscadores tradicionais quanto por motores generativos, sem depender de execucao de JavaScript para revelar conteudo principal.

O ADR 005 especificou neutralidade do quiz: nenhum `candidate_slug` ou `source_*` na etapa de perguntas, revelacao de fontes apenas no resultado, e filtro de confianca para excluir extracoes fracas. O ADR 006 tornou obrigatoria a pagina de metodologia e o MethodologyBadge em componentes de dados, institucionalizando transparencia e canal de reporte de erro.

## Licoes aprendidas
A principal licao foi que produtividade com IA cresce quando o processo e explicito. "Vibe coding" sem contrato gera velocidade inicial, mas acumula debito sem controle. Neste projeto, os ganhos vieram quando prompts, ADRs, schemas e specs foram tratados como artefatos de engenharia, nao como anexos. O resultado foi uma cadencia de entrega por fases com menor retrabalho e menos surpresa em integracao.

Outra licao foi que coordenacao multi-agente tem custo cognitivo real. Handoff entre papeis exige protocolo, naming consistente e disciplina de verificacao. Sem isso, o time virtual se desalinharia rapidamente. O uso de sentinelas `.DONE`, plano central em `PLAN.md` e loops com limite de tentativas ajudou a transformar colaboracao de agentes em fluxo confiavel, em vez de cadeia opaca de mensagens.

Tambem ficou claro que transparencia nao pode ser pos-processamento. Em produtos que usam IA sobre tema sensivel como eleicao, metodologia, disclaimer e origem de dados devem nascer junto com o codigo. Quando essa camada e adiada, recuperar confianca depois custa mais caro do que implementar certo desde o inicio.

## Numeros do projeto
No recorte de publicacao desta fase, os numeros consolidados sao:

- Planejamento em 16 fases principais, com uma fase de extensao opcional (Phase 17).
- Historico de 65 commits no repositorio antes do fechamento desta entrega.
- 177 arquivos versionados no momento do levantamento tecnico para esta documentacao.
- 21 fontes RSS ativas em `data/sources.json`, alem de 8 fontes partidarias e 6 fontes de pesquisas.
- 9 candidatos modelados em `data/candidates.json`.
- Cadencia de pipeline com coletor em 10 minutos, validacao em 30 minutos e curadoria em janela aproximada de 90 minutos.
- Build estatico de referencia com 24 paginas pre-renderizadas, incluindo rotas dinamicas de candidatos e comparacoes.

Esses numeros importam menos como marketing e mais como prova de escala operacional sob restricao de custo. O projeto nao depende de infraestrutura premium para manter cobertura tecnica relevante.

## Proximos passos
Os proximos marcos seguem o roteiro ja definido no PLAN. A Phase 14 amplia coleta de partidos e social para enriquecer cobertura alem de RSS, sem quebrar idempotencia nem contratos de schema. A Phase 15 foca polimento mobile: breakpoints, navegacao inferior e ergonomia de toque para manter qualidade em 390px, alinhada aos wireframes WF-11 e WF-12.

A Phase 16 fecha o ciclo com QA final: testes automatizados, revisao de seguranca, auditoria de SEO e revisao tecnica de alto sinal. Esse fechamento e critico para transformar o portal de prototipo funcional em referencia robusta de monitoramento eleitoral aberto. Depois disso, a extensao opcional com Vertex AI Search pode ser avaliada com base em custo, utilidade de busca semantica e impacto real para usuario final.

