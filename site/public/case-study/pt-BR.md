# Caso de Uso: Portal Eleições BR 2026

## Sumário executivo
O Portal Eleições BR 2026 foi concebido como um produto de transparência pública: um portal bilíngue (pt-BR e en-US) para monitorar notícias, sentimento, pesquisas e posicionamentos de pré-candidatos da eleição presidencial de 2026. O objetivo não foi criar mais uma página opinativa, mas sim uma infraestrutura editorial reproduzível e auditável, com separação clara entre coleta de dados, processamento com IA e apresentação para o público. A proposta central é simples: qualquer pessoa deve conseguir ler uma matéria no feed, entender em que etapa ela está e auditar o caminho técnico que levou aquele conteúdo a aparecer.

O projeto combina frontend estático em React + Vite com um pipeline Python orientado a dados e automação em GitHub Actions. Em vez de depender de um único modelo de IA, a arquitetura usa cadeia de fallback multi-provider para preservar disponibilidade e controlar custo. Em vez de esconder as limitações, o portal explicita metodologia, disclaimer, fontes e estado de processamento. Em vez de acoplar deploy a infraestrutura complexa, a publicação roda em GitHub Pages com Cloudflare. O resultado é um sistema enxuto, barato, rastreável e adaptado para evoluir em fases incrementais.

## Stack e arquitetura
Do ponto de vista técnico, a stack foi escolhida para maximizar previsibilidade operacional. No frontend, React 18 com Vite e `vite-react-ssg` pré-renderiza as páginas principais para servir conteúdo estático em GitHub Pages, com boa indexação para busca tradicional e assistentes de IA. A camada de UI segue wireframes em HTML standalone definidos no ADR 000, com tokens de design padronizados (`--navy`, `--gold`, `--bg`, `--surface`, `--muted`, `--text`, `--text2`, `--border`) para manter consistência visual entre feed, dashboards, quiz, metodologia e, agora, caso de uso.

No backend de dados, Python 3.12 orquestra coleta e transformações. Os scripts de pipeline foram implementados com foco em idempotência e rastreabilidade de estado. O identificador padrão `sha256(url.encode())[:16]` evita duplicação de artigos entre execuções, e os artefatos JSON seguem os contratos em `docs/schemas/*.schema.json` e `docs/schemas/types.ts`. Isso permite que React e Python compartilhem o mesmo modelo mental de dados, reduzindo regressão por divergência de formato.

A arquitetura de publicação usa três estágios editoriais (`raw -> validated -> curated`) e privilegia disponibilidade: mesmo quando um provedor de IA falha, o pipeline não para. O conteúdo pode aparecer como `raw` com título e metadados enquanto etapas mais caras ou lentas continuam em background. Esse desenho evita gargalo binário do tipo "publica tudo ou publica nada" e reflete melhor a natureza de dados em tempo quase real.

## Hierarquia de agentes
O processo de entrega foi estruturado com uma hierarquia de agentes explícita, documentada no PLAN e nos arquivos de handoff. O papel de Arquiteto ficou com Opus, responsável por consolidar estratégia, wireframes, ADRs e contratos de schema. O papel Tático ficou com Codex, transformando arquitetura em especificações de tarefa e critérios de verificação. O papel Operacional ficou com MiniMax, executando implementações concretas em loop disciplinado. O papel de QA ficou com Gemini, concentrado em validação, testes de interface e relatórios.

A governança operacional adotou o protocolo RALPH: Read, Analyze, List, Plan, Handle. Esse fluxo reduz improviso em tarefas extensas porque obriga leitura de contexto antes de alterar código, transforma ambiguidade em checklist, e fecha cada ciclo com validação. No projeto, RALPH não foi apenas um slogan; ele orientou a sequência de fases, a escrita de specs e a forma de tratar falhas repetidas com escalada formal.

O handoff entre camadas usa arquivos sentinela `plans/phase-NN-arch.DONE`. Esse mecanismo simples substitui integrações complexas de orquestração e deixa histórico auditável no próprio repositório. Quando uma fase fecha, o sentinela comunica que arquitetura e implementação daquela etapa estão sincronizadas e que a próxima camada pode avançar sem estado oculto. Para um projeto público e iterativo, esse padrão se mostrou pragmatismo puro: pouco acoplamento, alta rastreabilidade.

## Pipeline de ingestão
O pipeline editorial segue a metáfora de redação com três papéis. O Foca (coletor) roda em alta frequência, consumindo principalmente RSS, com expansão para sites partidários e outras fontes estruturadas. O Editor (validador) processa artigos coletados, aciona sumarização bilíngue e prepara dados para componentes analíticos. O Editor-chefe (curadoria) opera em cadência mais lenta, com foco em destaque, consistência e controles de qualidade.

As etapas de publicação são explícitas no dado: `raw`, `validated` e `curated`. No estado `raw`, o portal privilegia velocidade e transparência sobre acabamento: título, fonte e horário já podem aparecer, com sinalização de que a análise ainda está em andamento. No estado `validated`, entram sumários em dois idiomas e metadados enriquecidos. No estado `curated`, o conteúdo recebe camada adicional de priorização editorial automatizada. Esse funil evita bloqueios desnecessários e entrega valor incremental para o usuário.

A cadeia de IA foi desenhada para resiliência e custo controlado: NVIDIA NIM (Kimi K2.5 → MiniMax M2.5 → Nemotron 3 Super), Ollama Cloud, OpenRouter (Nemotron 3 Super), Vertex AI e MiMo, nessa ordem de fallback. A regra principal é não interromper pipeline por erro de IA. Se uma chamada falha, o sistema registra, tenta o próximo provedor e segue. Se todos falham, o artigo continua no fluxo com estado coerente, em vez de ser descartado silenciosamente. Essa postura privilegia continuidade operacional e reduz risco de indisponibilidade por dependência única.

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

## Números do projeto
No recorte de publicação desta fase, os números consolidados são:

- Planejamento em 16 fases principais, com uma fase de extensão opcional (Phase 17).
- Histórico de 65 commits no repositório antes do fechamento desta entrega.
- 177 arquivos versionados no momento do levantamento técnico para esta documentação.
- 21 fontes RSS ativas em `data/sources.json`, além de 8 fontes partidárias e 6 fontes de pesquisas.
- 9 candidatos modelados em `data/candidates.json`.
- Cadência de pipeline com coletor em 10 minutos, validação em 30 minutos e curadoria em janela aproximada de 90 minutos.
- Build estático de referência com 25 páginas pré-renderizadas, incluindo rotas dinâmicas de candidatos e comparações.
- Suíte Python com 61 testes passando (`python -m pytest scripts/ -v --tb=short`).
- Suíte Playwright com 24 testes passando contra o site buildado (`npx playwright test`).
- Quatro relatórios formais de QA gerados em `qa/phase-16-*.md` (security, SEO, code review, accessibility).

Esses números importam menos como marketing e mais como prova de escala operacional sob restrição de custo. O projeto não depende de infraestrutura premium para manter cobertura técnica relevante.

## Próximos passos
Com a Phase 16 concluída, o baseline de qualidade (testes automatizados + auditorias de segurança/SEO/acessibilidade + revisão técnica) está fechado para release `1.0.0`.

O próximo marco técnico permanece a extensão opcional da Phase 17 (Vertex AI Search), a ser avaliada por custo, utilidade de busca semântica e impacto real para usuário final. Em paralelo, o projeto deve manter operação contínua dos workflows, monitoramento de qualidade de dados e atualização editorial dos artefatos bilíngues.
