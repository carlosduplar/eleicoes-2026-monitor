# Prompt Otimizado — Google Stitch
## Portal Eleições BR 2026
## stitch.withgoogle.com

---

## ANTES DE COMEÇAR — MODELOS E WORKFLOW

### Modelos disponíveis no Stitch (com Google AI Pro)
O Stitch ganhou integração com Gemini 3 em dezembro de 2025. Com Google AI Pro, o workflow recomendado para o projeto é em **duas etapas por tela**:

| Etapa | Modelo | Objetivo |
|-------|--------|----------|
| 1 — Wireframe inicial | **Gemini 3.1 Pro** | Melhor qualidade de raciocínio visual; interpreta prompts complexos com múltiplas restrições de layout, paleta e hierarquia |
| 2 — Conversão para HTML | **Gemini 3.0 Flash** | Geração de código HTML/CSS limpo e production-ready a partir do wireframe aprovado na etapa 1; mais rápido e eficiente para esta tarefa |

### Sobre o Stitch MCP — Integração com GitHub Copilot CLI

O Stitch tem um MCP server oficial. Com ele, o Opus 4.6 busca HTML/CSS das telas diretamente
durante a implementação — wireframes são fonte viva, não só arquivos estáticos em docs/wireframes/.

#### Pacote oficial
`@_davideast/stitch-mcp` — wrapper stdio do endpoint nativo `stitch.googleapis.com/mcp`.
O endpoint nativo requer autenticação `google_credentials` que a maioria dos clientes MCP
não suporta nativamente; o pacote resolve isso com OAuth + token refresh automático.

#### Setup em uma linha (Windows 11 PowerShell 7 — método recomendado)

```powershell
npx @_davideast/stitch-mcp init
```

O wizard `init` gerencia automaticamente: instalação do gcloud bundled, OAuth,
credenciais e geração da config MCP para o cliente.

> **Atenção no Windows 11 (não-WSL):** o CLI detecta o ambiente e imprime a URL OAuth
> no terminal com timeout de 5 segundos. Se o browser não abrir automaticamente,
> copiar a URL `https://accounts.google.com/...` e colar no browser manualmente.

#### Alternativa: API Key (mais simples, sem browser)

Stitch web → Profile → Settings → API Keys → Create Key.
Configurar no `.copilot/mcp.json`:

```json
{
  "mcpServers": {
    "stitch": {
      "command": "npx",
      "args": ["@_davideast/stitch-mcp", "proxy"],
      "env": {
        "STITCH_API_KEY": "${env:STITCH_API_KEY}"
      }
    }
  }
}
```

#### Alternativa: ADC com gcloud próprio

```powershell
gcloud auth application-default login
gcloud config set project <PROJECT_ID>
gcloud beta services mcp enable stitch.googleapis.com --project=<PROJECT_ID>
```

Config:
```json
{
  "mcpServers": {
    "stitch": {
      "command": "npx",
      "args": ["@_davideast/stitch-mcp", "proxy"],
      "env": { "STITCH_USE_SYSTEM_GCLOUD": "1" }
    }
  }
}
```

#### Ferramentas expostas pelo proxy

O proxy expõe **dois grupos** de ferramentas lado a lado:

**Grupo 1 — Ferramentas de alto nível do proxy** (combinam múltiplas chamadas API):

| Tool | Input | O que retorna | Uso no projeto |
|------|-------|---------------|---------------|
| `get_screen_code` | `screenId` | HTML/CSS da tela | Antes de implementar cada componente React |
| `get_screen_image` | `screenId` | Screenshot base64 | Visualizar tela durante planning |
| `build_site` | `{ projectId, routes: [{screenId, route}] }` | HTML de cada página mapeada a rota | Fase 12: CandidatePage + ComparisonPage de uma vez |

**Grupo 2 — Ferramentas nativas upstream do Stitch**:

| Tool | O que faz |
|------|-----------|
| `list_projects` | Lista todos os projetos do Stitch |
| `list_screens` | Lista screens de um projeto com metadados |
| `generate_screen_from_text` | Gera nova tela via Gemini 3 Pro ou Flash |

#### Comandos CLI úteis (exploração antes de usar o MCP)

```powershell
# Wizard de setup (primeira vez)
npx @_davideast/stitch-mcp init

# Navegar projetos e telas no terminal
npx @_davideast/stitch-mcp view --projects
npx @_davideast/stitch-mcp view --project <project-id> --screen <screen-id>
# Dentro do viewer: c=copiar, s=preview HTML no browser, o=abrir no Stitch, q=sair

# Preview local de todas as telas do projeto (Vite dev server)
npx @_davideast/stitch-mcp serve -p <project-id>

# Invocar qualquer ferramenta MCP direto da CLI (útil para testar antes de usar via agente)
npx @_davideast/stitch-mcp tool                          # lista todas as ferramentas
npx @_davideast/stitch-mcp tool get_screen_code -s       # mostra schema da ferramenta
npx @_davideast/stitch-mcp tool build_site -d '{
  "projectId": "SEU_PROJECT_ID",
  "routes": [
    { "screenId": "WF-07-id", "route": "/candidato" },
    { "screenId": "WF-08-id", "route": "/comparar" }
  ]
}'

# Diagnóstico
npx @_davideast/stitch-mcp doctor --verbose
```

#### Clientes MCP suportados
VS Code, Cursor, **Claude Code**, **Gemini CLI**, **Codex**, **OpenCode**

> **Nota:** o `serve` (preview Vite local) e o `site` (gera projeto Astro deployável a partir
> das telas) são comandos independentes do MCP — úteis para validar o design antes da
> implementação React, mas não fazem parte do workflow do agente via MCP.

---

## BLOCO DE CONTEXTO GLOBAL
### Colar no início de CADA nova sessão

```
Product: Portal Eleições BR 2026
Type: Bilingual (Brazilian Portuguese + English) real-time news monitoring portal
for Brazil's 2026 presidential elections. Aggregates 30+ sources — major news outlets,
party websites, polling institutes — and uses AI for summaries, sentiment analysis,
a polling tracker, and a political affinity quiz. Non-partisan, fully transparent, public source code.

Target users: Brazilian voters 25–55, politically engaged, mobile-first.
Secondary: journalists and international observers (English UI).

Design language:
- Aesthetic: Editorial political intelligence. The Economist meets a data dashboard.
  Authoritative without being cold. NOT generic SaaS, NOT standard news portal.
- Display font: Serif (Georgia or Playfair Display) for all H1/H2 — editorial authority
- Body/data font: Clean sans-serif (DM Sans) for labels, body, data
- Color palette:
    Background: #FFFFFF
    Card surface: #EDF2F7 (light gray-blue)
    Primary: #1A2E4A (deep navy)
    Accent / CTA: #C9A227 (gold)
    Body text: #1A1A2E
- Candidate colors — use EXACTLY these hex values, never substitute:
    Lula / PT:              #CC0000
    Tarcísio / PL:          #002776
    Caiado / União Brasil:  #FF8200
    Ratinho Jr / PSD:       #0066CC
    Eduardo Leite / PSD:    #4488CC
    Zema / Novo:            #FF6600
    Flávio Bolsonaro / PL:  #003399
- Every data dashboard must include a small "Como funciona? ⓘ" badge (gold text, links to /metodologia)
- Language toggle [PT | EN] always visible in header top-right
- Platform: Web desktop-first (1440px), fully responsive mobile (390px)
```

---

## SESSÕES DE GERAÇÃO — 2 TELAS POR SESSÃO

---

### SESSÃO A — WF-01 (Home) + WF-02 (Sentimento por Tema)

**[Contexto Global → depois este prompt]**

```
Screen 1 of 2 — Home: News Feed (WF-01) — desktop 1440px

Fixed header (deep navy #1A2E4A):
- Left: "Eleições BR 2026" serif logo, white
- Center: tabs — Feed | Pesquisas | Quiz | Candidatos | Metodologia
- Right: [PT | EN] toggle + "Atualizado há 8 min" in small gold text

Slim alert bar below header (gold #C9A227 background, navy text):
"📡 Assine o feed RSS · 30 fontes · Atualizado a cada 30 min"

3-column grid:

LEFT SIDEBAR (260px, card surface #EDF2F7):
Source filter panel — checkboxes grouped:
  Mainstream (G1, Folha, Estadão, UOL, O Globo)
  Política (Poder360, JOTA)
  Internacional (BBC Brasil, Reuters, DW, El País)
  Institucional (TSE, Agência Brasil, Câmara, Senado)
  Partidos (PT, PL, PSD, Novo, União Brasil)
Candidate pills below in each candidate's party color
Time filter: Última hora | 6h | 24h | Semana (radio)

CENTER (flexible, white):
Search bar at top
4 news cards:
  - Source + category badge + "há 23 min"
  - Headline (bold serif, 2 lines)
  - AI summary (2–3 lines muted sans-serif)
  - "Como funciona? ⓘ" small gold badge near summary
  - Candidate tags (colored pills: Lula #CC0000, Tarcísio #002776, etc.)
  - Topic tags (gray pills: "economia" "segurança")
  - "IA: nvidia" small badge bottom-right

RIGHT SIDEBAR (280px, #EDF2F7):
"Termômetro de Menções" — horizontal bar chart, each candidate bar in their exact color
"Últimas Pesquisas" — 2 recent polls: institute + date + top 2 candidates + %
"Quiz de Afinidade" CTA card — gold background, "Descubra seu candidato", start button

Footer: GitHub link, /metodologia, RSS feeds PT/EN, last pipeline run timestamp
```

**[Still in same session — Screen 2:]**

```
Screen 2 of 2 — Sentiment Dashboard: By Topic (WF-02) — desktop 1440px
Same header.

Title area:
H1 "Análise de Sentimento" (large serif)
Subtitle: "Como a mídia cobre cada candidato por tema"
PROMINENT callout box (gold left border, cream background):
  "Análise algorítmica · Sem intervenção editorial · Como funciona? ⓘ"
  Disclaimer italic: "Não representa pesquisa de opinião."
Toggle: [Por Tema ●] [Por Fonte ○]
"347 artigos · Atualizado há 12 min"

Heatmap grid (center of page):
Rows = 7 candidates with small colored dot in party color:
  Lula (#CC0000), Tarcísio (#002776), Caiado (#FF8200), Ratinho Jr (#0066CC),
  Eduardo Leite (#4488CC), Zema (#FF6600), Flávio Bolsonaro (#003399)
Columns = 8 topics: Economia | Segurança | Saúde | Educação | Corrupção | Meio Ambiente | Eleições | Pol. Ext.
Each cell: colored rectangle + score number (–1.0 to +1.0)
Color scale: deep red (–1) → neutral gray (0) → deep green (+1)
Show varied realistic scores for Lula row
Color legend bar below grid: "Negativo ←→ Positivo"

Right panel (280px): "Top artigos" — 3 news items for hovered cell
```

---

### SESSÃO B — WF-03 (Sentimento por Fonte) + WF-04 (Pesquisas)

**[Contexto Global → depois:]**

```
Screen 1 of 2 — Sentiment Dashboard: By Source (WF-03) — desktop 1440px
Identical structure to WF-02 with these differences only:
- Toggle: [Por Tema ○] [Por Fonte ●]
- Columns = 6 source categories: Mainstream | Política Esp. | Internacional | Institucional | Partidos | Social
- Same 7 candidate rows, same color scale
- Partidos column: high positive values for each candidate's own party — add annotation:
  "Fontes partidárias cobrem positivamente o próprio candidato (esperado)"
- Same disclaimer callout and "Como funciona? ⓘ" badge
```

```
Screen 2 of 2 — Polling Tracker (WF-04) — desktop 1440px
Same header.

H1 "Pesquisas Eleitorais" (serif)
Institute filter pills (multi-select): [Todos ●] [Datafolha] [Quaest] [AtlasIntel] [Paraná Pesquisas] [PoderData] [RTBD]

Main line chart (full width, ~380px tall):
X axis: months Jan–Oct 2026
Y axis: voting intention 0–50%
Lines in exact candidate colors:
  Lula #CC0000, Tarcísio #002776, Caiado #FF8200, Ratinho Jr #0066CC,
  Eduardo Leite #4488CC, Zema #FF6600, Flávio Bolsonaro #003399
Legend with color swatches
Dashed vertical event lines with labels
Tooltip shown: "Datafolha · 28/02/2026 · ±2pp · n=2.016"

Polls table below:
Columns: Instituto | Data | Lula | Tarcísio | Caiado | Ratinho Jr | Outros | ±Margem | Amostra
5 data rows, alternating colors, highest value per row in bold

Right sidebar (280px): trend cards per candidate — name + % current + delta ↑↓
```

---

### SESSÃO C — WF-05 (Quiz Pergunta) + WF-06 (Quiz Resultado)

**[Contexto Global → depois:]**

```
Screen 1 of 2 — Quiz: Question Screen (WF-05)
Show desktop (1440px) AND mobile (390px) side by side.

CRITICAL RULE: NO candidate names, NO source references anywhere on this screen.
User chooses political positions only. Attribution revealed after all questions answered.

Reduced header: logo + "Quiz de Afinidade Política" + [PT | EN]. No main navigation.

Progress (full-width slim bar, navy fill):
"Pergunta 3 de 12" — no indication of any candidate elimination process.

Question card (centered, max 760px):
Small uppercase topic tag (gold): "SEGURANÇA PÚBLICA"
Large serif question: "Qual política de segurança pública faz mais sentido para você?"

4 answer cards (stacked, full-width of container, min 80px tall each):
  - Letter badge A/B/C/D (navy circle, left)
  - Position text 1–2 sentences (e.g. "Ampliação do porte com treinamento obrigatório e rastreabilidade")
  - Default state: white bg, subtle border
  - Card B selected: navy bg, white text
  - NO candidate names anywhere
"Próxima pergunta →" (full width, gold, disabled until selection)
"Pular esta pergunta" ghost link (small, below)
Footnote (tiny muted): "Posições extraídas de declarações verificadas. Fontes reveladas no resultado."

Mobile 390px: same structure single column, touch targets min 64px tall, bottom-anchored button.
```

```
Screen 2 of 2 — Quiz: Result Screen (WF-06) — desktop 1440px
Show above-fold section + indication of scrollable content below.

ABOVE FOLD:
H1 "Seu perfil político" (large serif)
Subhead: "Sua afinidade com cada candidato, baseada nas suas respostas:"

Ranking list (7 candidates):
Each row: rank | candidate name + party | progress bar (candidate color, width = %) | percentage bold
Top candidate (Lula 76%) gold border + "Maior afinidade" badge
"Compartilhar resultado" — prominent gold CTA button, full width

BELOW FOLD (hint with scroll arrow):
Section "Afinidade por tema":
  Radar chart, hexagonal, axes = quiz topics
  3 overlapping colored areas for top 3 candidates (semi-transparent, party colors)
  Legend below

Section "Por que este resultado?":
  3 cards (top 3 candidates), each:
    Candidate name header in their color
    "Maior concordância:" 2 topics ✓
    "Maior divergência:" 1 topic ✗

Section "De onde vieram as posições?" (collapsed by default — gold chevron to expand):
  FIRST ATTRIBUTION REVEAL. For each question: chosen text → "Posição de [Candidato] · [Source, Date]"
  Muted gray background.

Footer: "Refazer o quiz" | link /metodologia | "Ver pesquisas eleitorais"
```

---

### SESSÃO D — WF-07 (Perfil Candidato) + WF-08 (Comparação GEO)

**[Contexto Global → depois:]**

```
Screen 1 of 2 — Candidate Profile Page (WF-07) — desktop 1440px
Example: Tarcísio de Freitas. Same header as WF-01.

Hero (full-width, #002776 PL-navy background):
"Tarcísio de Freitas" large serif white
"PL · Governador de SP · Pré-candidato 2026"
Sentiment bar: tone score + "423 artigos monitorados"

3-column grid:
LEFT (260px): "Últimas notícias sobre Tarcísio" — 5 compact items (headline + source + time ago)
CENTER (flexible):
  Mini heatmap row (Tarcísio only, 8 topics, same color scale as WF-02)
  "Posições declaradas por tema" — list with source per topic (1–2 sentences + "Fonte: ...")
RIGHT (260px):
  Mini polling trend line (his color, last 3 months)
  "Compare com:" pills — "vs Lula" | "vs Caiado" | "vs Ratinho Jr"

Footer note: "Posições extraídas automaticamente. Fontes verificadas. Ver metodologia →"
```

```
Screen 2 of 2 — Candidate Comparison Page (WF-08) — desktop 1440px
GEO-optimized page for queries like "Lula vs Tarcísio 2026". Same header.

Hero (full-width split):
Left half: #CC0000 red bg, "Lula" large serif white, "PT"
Right half: #002776 navy bg, "Tarcísio" large serif white, "PL"
Center vertical divider: "VS" in gold, dark background

Comparison grid (8 topic rows):
Economia | Segurança | Saúde | Educação | Armas | Privatizações | Meio Ambiente | Corrupção
Each row:
  Left cell (light red tint): Lula's position (1–2 sentences)
  Center: topic label + divergence dot (🔴 high / 🟡 medium / 🟢 low)
  Right cell (light navy tint): Tarcísio's position

Below grid:
Mini dual-line chart: both candidates' polling trends
3 news cards mentioning both
Gold CTA: "Faça o Quiz de Afinidade →"

Bottom (small text): "Fontes das posições disponíveis no Quiz de Afinidade"
```

---

### SESSÃO E — WF-09 (Metodologia) + WF-10 (Caso de Uso)

**[Contexto Global → depois:]**

```
Screen 1 of 2 — Methodology Page (WF-09) — desktop 1440px. Same header.

Hero (white bg, navy accent):
H1 "Como funciona o Portal Eleições BR 2026" (serif)
Subtitle: "Transparência total. Sem filiação partidária. Sem intervenção editorial."
3 trust badges: [🔓 Código aberto] [🤖 100% automatizado] [📰 Sem viés editorial]
"Ver código no GitHub →" (navy outline button)

Pipeline section (light gray bg):
Horizontal flow diagram (icons + labels):
RSS + Scraping → Deduplicação → Sumarização IA → Análise Sentimento → Publicação
Each step has 1-line description. "Atualização: a cada 30 minutos"

AI providers section (white bg):
Ordered numbered list of 5 providers with cost labels:
  1. NVIDIA NIM — gratuito
  2. OpenRouter — gratuito  
  3. Ollama Cloud — gratuito
  4. Vertex AI / Gemini 2.5 Flash Lite — pago
  5. MiMo-V2-Flash — fallback final
"Nenhuma curadoria humana dos resultados."

Warning callout (gold left border, cream bg):
"Os scores de sentimento refletem o tom das notícias coletadas.
Não equivalem a pesquisa de opinião. Modelos de IA podem cometer erros."

Sources section: grouped list of 30+ sources by category

Footer: "Encontrou um erro? Abra um issue no GitHub →"
```

```
Screen 2 of 2 — Case Study / About (WF-10) — desktop 1440px. Same header.

Hero:
H1 "Da Ideia à Concepção com IA" (serif)
Subtitle: "Como este portal foi desenvolvido usando Claude Sonnet 4.6, Claude Opus 4.6,
GPT-5.3-Codex, Google Stitch e GitHub Copilot CLI"
[PT | EN] toggle — prominent (page is fully bilingual)
"Ver no GitHub →" link
AI tool badges row: Claude Sonnet · Claude Opus · Codex · Google Stitch · Copilot CLI

Vertical timeline (main content):
Each phase = card:
  - Navy circle badge with phase number
  - Phase title (bold)
  - Date + AI tools used (small badges)
  - Bullet list: what was implemented
  - Gold left-border box: key architectural decision
Show 3 phases as example.

Right sidebar (260px):
"Stack técnico" compact list
"Ferramentas IA" icon grid
GitHub stats placeholder (stars, forks, last commit)

Aesthetic: editorial/article — generous line height, large body text, strong section headers.
Less dashboard, more longform reading experience.
```

---

### SESSÃO F — WF-11 (Mobile Home) + WF-12 (Mobile Quiz)

**[Contexto Global → depois:]**

```
Screen 1 of 2 — Mobile Home 390px (WF-11)

Fixed header (navy #1A2E4A, full width):
Left: "Eleições BR 2026" (smaller serif, white)
Right: [PT|EN] + hamburger menu
Below header: slim gold bar "Atualizado há 8 min · 30 fontes"

Horizontal scrollable tabs (below header):
Feed | Pesquisas | Quiz | Candidatos (active: gold underline)

Search bar (full width)

Filter chips (horizontal scroll, not wrapping):
[Todos ●] [Mainstream] [Política] [Internacional] [Partidos]

Candidate pills (horizontal scroll):
Short names in party colors: Lula | Tarcísio | Caiado | Ratinho | E. Leite | Zema | Flávio

News feed (full-width stacked cards, 3 visible):
Each card:
  - Source + badge + "há 23 min"
  - Headline bold serif (2 lines, readable size)
  - Summary 2 lines (muted)
  - Candidate + topic tags

Floating gold circle button bottom-right (fixed): "Quiz →"

Bottom navigation bar (fixed, full width):
5 items: Feed | Pesquisas | Quiz | Candidatos | Mais
Icons + labels. Touch targets min 44px. Active: gold underline.
No horizontal scroll on main content area.
```

```
Screen 2 of 2 — Mobile Quiz: Question + Result (WF-12)
Two 390px screens side by side.

LEFT — Quiz Question (mobile):
Slim header: progress bar + "Pergunta 4 de 12"
Topic: "ECONOMIA" (gold uppercase)
Question: "Qual política econômica faz mais sentido para você?"
4 answer cards (stacked, min 72px tall):
  Letter badge (A/B/C/D) + position text (2 lines)
  Card B selected: navy bg, white text
NO candidate names on this screen.
"Próxima →" button (full width gold)
"Pular" ghost button below

RIGHT — Quiz Result top (mobile):
"Seu perfil político" heading
Top 3 candidates ranked:
  Rank + name + colored progress bar + %
  Top candidate: gold border
"Compartilhar resultado" (full width gold)
"Ver detalhes" (full width navy outline)
Below-fold arrow: radar chart + source revelation section

Both: min 16px text, min 44px touch targets, max 2 CTAs at a time.
```

---

## FOLLOW-UP PROMPTS DE REFINAMENTO

**Corrigir cores exatas dos candidatos:**
```
Fix all candidate colors to use exactly:
Lula #CC0000, Tarcísio #002776, Caiado #FF8200, Ratinho Jr #0066CC,
Eduardo Leite #4488CC, Zema #FF6600, Flávio Bolsonaro #003399.
Replace any generic blues, reds, or other substituted values.
```

**Corrigir tipografia:**
```
Update typography: Georgia or Playfair Display serif for all H1 and H2.
DM Sans or clean sans-serif for body text and data labels.
Increase heading size for stronger hierarchy.
```

**Adicionar MethodologyBadge:**
```
Add a small "Como funciona? ⓘ" badge in gold text in the top-right corner
of every data dashboard card (sentiment, polls, quiz). This badge links to /metodologia.
```

**Adicionar empty/loading states:**
```
Add loading and empty states to all data components:
Loading: gray skeleton shimmer
Empty: icon + "Nenhum dado disponível. Pipeline atualiza a cada 30 min."
Error: warning icon + "Erro ao carregar. Tente novamente."
```

**Forçar mobile responsivo:**
```
Generate the 390px mobile version of this screen: single column layout,
convert sidebars to collapsible accordions or bottom sheets,
touch targets min 44px, no horizontal scroll, fixed bottom navigation bar.
```

**Corrigir identidade visual:**
```
Refine to match editorial political intelligence aesthetic:
#1A2E4A deep navy header, #C9A227 gold for CTAs/accents, white and #EDF2F7 surfaces.
Serif headlines, sans-serif data. Authoritative, not generic SaaS.
```

---

## EXPORTAÇÃO E INTEGRAÇÃO AO PROJETO

### Estrutura de arquivos
```
docs/wireframes/
├── WF-01-home-desktop.png + .html
├── WF-02-sentiment-by-topic.png + .html
├── WF-03-sentiment-by-source.png + .html
├── WF-04-polls-tracker.png + .html
├── WF-05-quiz-question.png + .html
├── WF-06-quiz-result.png + .html
├── WF-07-candidate-profile.png + .html
├── WF-08-candidate-comparison.png + .html
├── WF-09-methodology.png + .html
├── WF-10-case-study.png + .html
├── WF-11-mobile-home.png + .html
└── WF-12-mobile-quiz.png + .html
```

### Trecho para o prompt inicial do GitHub Copilot CLI (Opus 4.6)
```
Stitch MCP is configured in .copilot/mcp.json (package: @_davideast/stitch-mcp, proxy mode).
Use it to fetch wireframe HTML/CSS before implementing each frontend component.

Phase 0 checklist before any code:
1. npx @_davideast/stitch-mcp view --projects  →  confirm projectId of "eleicoes-2026-monitor"
2. npx @_davideast/stitch-mcp view --project <projectId>  →  list all screens and their screenIds
3. Create docs/adr/000-wireframes.md mapping each WF code to its confirmed screenId,
   plus design decisions: palette (candidate hex values), typography, layout principles.

Wireframe registry (confirm screenIds via list_screens before use):
  WF-01  → Home.jsx, NewsFeed.jsx, SourceFilter.jsx
  WF-02/03 → SentimentDashboard.jsx (views A and B)
  WF-04  → PollTracker.jsx, PollsPage.jsx
  WF-05/06 → QuizEngine.jsx, QuizPage.jsx, QuizResultCard.jsx, QuizResult.jsx
  WF-07  → CandidatePage.jsx
  WF-08  → ComparisonPage.jsx
  WF-09  → MethodologyPage.jsx
  WF-10  → CaseStudyPage.jsx
  WF-11/12 → mobile breakpoints for all above

Before implementing any frontend component:
1. list_screens(projectId) — confirm the screenId for the wireframe
2. get_screen_code(screenId) — retrieve current HTML/CSS baseline
3. Adapt HTML to React + Vite + react-i18next conventions
4. For multiple SEO/GEO pages at once: build_site with routes mapping

For local design preview before coding: npx @_davideast/stitch-mcp serve -p <projectId>
PNG references also available in docs/wireframes/ for visual context and history.
```
