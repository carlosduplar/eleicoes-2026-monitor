# Prompt v5 (Final) — Portal Eleições BR 2026
## Para Claude Opus 4.6 via GitHub Copilot CLI (planner)
## Implementador: gpt-5.3-codex

---

## CONTEXTO DO DESENVOLVEDOR

- **Planner:** Claude Opus 4.6
- **Implementador:** gpt-5.3-codex
- **MCPs ativos:** context7, chrome-devtools, Bright-Data, github-mcp-server, stitch (MCP remoto oficial — `https://stitch.googleapis.com/mcp` via API Key)
- **Skills ativas:** docs-maintainer, documentation-lookup, frontend-design, playwright-cli, security-threat-modeler, tech-lead-reviewer, test-writer, seo-audit, web-design-guidelines, vercel-react-best-practices
- **Política:** MINIMIZE QUESTIONS. Prosseguir com defaults razoáveis; documentar premissas e decisões em PLAN.md. Perguntar apenas quando a escolha for irreversível e arquiteturalmente distinta.
- **GitHub Education:** Actions sem restrição de minutos mensais.
- **Google AI Pro:** inclui $10/mês em créditos para utilização de modelos Google no Vertex AI — Gemini 2.5 Flash Lite via Vertex é o provider pago prioritário (mais barato que AI Studio).
- **Repositório:** público desde o início. Transparência total é um princípio do projeto.

---

## OBJETIVO

Inicializar o repositório público **eleicoes-2026-monitor**: portal bilíngue (pt-BR + en-US) de monitoramento em tempo quase real das eleições presidenciais brasileiras de 2026. Site estático via GitHub Pages, pipeline a cada 30 minutos via GitHub Actions.

**Este projeto é documentado como caso de uso de desenvolvimento com IA.** Cada decisão arquitetural deve ser registrada em ADRs, PLAN.md e `docs/case-study/`. Os agentes Opus e Codex mantêm essa documentação atualizada ao longo de todo o desenvolvimento via **docs-maintainer skill**.

**Funcionalidades principais:**
1. Feed de notícias agregado (20+ fontes, resumos bilíngues via IA)
2. Dashboard de sentimento por candidato (heatmap × tema e × fonte) com disclaimer de metodologia
3. Rastreador de pesquisas eleitorais (scraping automático, gráfico temporal)
4. **Quiz de Afinidade Política** com funil progressivo e framing invertido (posições verificadas, fontes reveladas só no resultado)
5. Páginas SEO/GEO por candidato e comparações entre candidatos
6. Feed RSS/Atom próprio (`/feed.xml`) para retenção e assinatura
7. Página de Metodologia (`/metodologia`) com disclaimer, descrição do pipeline e link para o repositório público
8. Documentação viva do caso de uso no site (`/sobre/caso-de-uso`) em pt-BR e en-US

---

## STACK OBRIGATÓRIO

| Camada | Tecnologia | Observação |
|--------|-----------|------------|
| Hospedagem | GitHub Pages | Custo zero; site estático |
| CI/CD | GitHub Actions (cron 30min) | GitHub Education — sem limite de minutos |
| CDN | Cloudflare Free | Cache HTTP 1800s; absorve picos de tráfego viral |
| Frontend | React + Vite + vite-plugin-ssg | SSG para pre-render de páginas SEO/GEO |
| i18n | react-i18next | pt-BR obrigatório + en-US; estrutura extensível |
| SEO | react-helmet-async + JSON-LD manual | Controle total sobre meta tags e structured data |
| Pipeline | Python 3.12 | feedparser, BeautifulSoup, Playwright |
| Scraping pesado | Playwright + Bright-Data MCP (se bloqueado) | Institutos de pesquisa e partidos |

---

## ARQUITETURA DE IA — MULTI-PROVIDER COM FALLBACK HIERÁRQUICO

Todos os providers são compatíveis com o OpenAI Python SDK via `base_url` swap. Zero lock-in.

```python
PROVIDER_CHAIN = [
    # Nível 1 — NVIDIA NIM (gratuito, créditos dev)
    {"name":"nvidia",     "base_url":"https://integrate.api.nvidia.com/v1",
     "key_env":"NVIDIA_API_KEY",      "model":"qwen/qwen3.5-397b-a17b",             "paid":False},
    # Nível 2 — OpenRouter (gratuito, 200 req/dia, 20 req/min)
    {"name":"openrouter", "base_url":"https://openrouter.ai/api/v1",
     "key_env":"OPENROUTER_API_KEY",  "model":"arcee-ai/trinity-large-preview:free", "paid":False, "daily_max":200},
    # Nível 3 — Ollama Cloud (gratuito, limites horários/semanais)
    {"name":"ollama",     "base_url":"https://ollama.com/v1",
     "key_env":"OLLAMA_API_KEY",      "model":"minimax-m2.5:cloud",                  "paid":False},
    # Nível 4 — Vertex AI / Gemini 2.5 Flash Lite (pago prioritário — $10/mês Google AI Pro)
    {"name":"vertex",     "base_url":os.environ.get("VERTEX_BASE_URL",""),
     "key_env":"VERTEX_ACCESS_TOKEN", "model":"google/gemini-2.5-flash-lite-001",    "paid":True},
    # Nível 5 — MiMo-V2-Flash (fallback pago secundário)
    {"name":"mimo",       "base_url":"https://api.xiaomimimo.com/v1",
     "key_env":"XIAOMI_MIMO_API_KEY", "model":"mimo-v2-flash",                       "paid":True},
]
```

### Seleção de modelo por tarefa dentro do NVIDIA NIM
```python
NVIDIA_MODELS = {
    "summarization": "qwen/qwen3.5-397b-a17b",    # melhor qualidade geral
    "sentiment":     "minimaxai/minimax-m2.5",     # melhor análise contextual
    "multilingual":  "moonshotai/kimi-k2.5",       # melhor pt-BR/EN
    "quiz_extract":  "qwen/qwen3-235b-a22b-thinking-2507",  # raciocínio para extrair posições
}
```

### `scripts/ai_client.py` — rastreador de uso + fallback completo
```python
import os, time, json, openai
from pathlib import Path

USAGE_FILE = Path("data/ai_usage.json")

def _load_usage():
    try: return json.loads(USAGE_FILE.read_text())
    except: return {}

def _save_usage(u):
    USAGE_FILE.parent.mkdir(exist_ok=True)
    USAGE_FILE.write_text(json.dumps(u, indent=2))

def call_with_fallback(system: str, user: str, max_tokens: int = 500) -> dict:
    usage = _load_usage()
    today = time.strftime("%Y-%m-%d")
    for p in PROVIDER_CHAIN:
        key = os.environ.get(p["key_env"])
        if not key or not p.get("base_url"): continue
        if p["name"] == "openrouter":
            if usage.get(f"openrouter_{today}", 0) >= p.get("daily_max", 200):
                print("[AI] openrouter: limite diário atingido"); continue
        try:
            client = openai.OpenAI(api_key=key, base_url=p["base_url"])
            resp = client.chat.completions.create(
                model=p["model"], max_tokens=max_tokens,
                messages=[{"role":"system","content":system},{"role":"user","content":user}]
            )
            content = resp.choices[0].message.content
            track = f"{p['name']}_{today}"
            usage[track] = usage.get(track, 0) + 1
            _save_usage(usage)
            return {"content":content, "provider":p["name"], "model":p["model"], "paid":p["paid"]}
        except Exception as e:
            print(f"[AI] {p['name']} falhou: {e}"); time.sleep(1)
    raise RuntimeError("Todos os providers de IA falharam.")

def summarize_article(title: str, content: str, language: str = "pt-BR") -> dict:
    """Gera resumo + entidades + sentimento no idioma especificado."""
    import json as _j
    lang = "Responda em português brasileiro." if language == "pt-BR" else "Respond in English."
    system = f"Analista político especializado nas eleições brasileiras de 2026. {lang} Responda APENAS com JSON válido, sem markdown."
    user = f"""Título: {title}\nConteúdo: {content[:2500]}

JSON obrigatório:
{{
  "summary": "2-3 frases",
  "candidates_mentioned": ["nomes exatos"],
  "topics": ["economia","segurança","saúde","educação","corrupção","meio ambiente","eleições"],
  "sentiment_per_candidate": {{"Nome": "positivo|neutro|negativo"}}
}}"""
    r = call_with_fallback(system, user, 450)
    try:
        parsed = _j.loads(r["content"].strip().strip("```json").strip("```"))
        return {**parsed, "_ai_provider": r["provider"], "_language": language}
    except:
        return {"summary":title,"candidates_mentioned":[],"topics":[],
                "sentiment_per_candidate":{},"_ai_provider":r["provider"],
                "_language":language,"_parse_error":True}

def extract_candidate_position(candidate: str, topic_id: str, snippets: list[str]) -> dict:
    """
    Extrai posição verificável de um candidato sobre um tópico.
    Retorna posição em ambos os idiomas + stance + fonte + confiança.
    Usado pelo pipeline do Quiz de Afinidade.
    """
    import json as _j
    system = "Analista político. Extraia posições verificáveis de candidatos a partir de trechos de notícias. Responda APENAS com JSON válido."
    user = f"""Candidato: {candidate}
Tópico: {topic_id}
Trechos de notícias ({len(snippets)} fontes):
{chr(10).join(f'[{i+1}] {s}' for i,s in enumerate(snippets[:12]))}

Retorne JSON:
{{
  "position_pt": "posição declarada em 1-2 frases em português, citando o que o candidato disse/propôs, ou null se não há evidência suficiente",
  "position_en": "declared position in 1-2 English sentences, or null if insufficient evidence",
  "stance": "favor|against|neutral|unclear",
  "confidence": "high|medium|low",
  "best_source_snippet_index": 1
}}"""
    r = call_with_fallback(system, user, 350)
    try:
        return _j.loads(r["content"].strip().strip("```json").strip("```"))
    except:
        return {"position_pt":None,"position_en":None,"stance":"unclear","confidence":"low","_parse_error":True}
```

---

## ESTRUTURA DE DIRETÓRIOS

```
eleicoes-2026-monitor/
├── .github/
│   └── workflows/
│       ├── collect.yml            # cron 10min: coleta + IA + commit
│       ├── update-quiz.yml        # cron diário 3h UTC: extração de posições
│       └── deploy.yml             # push em main: SSG build + GitHub Pages
├── docs/
│   ├── adr/
│   │   ├── 001-hosting.md
│   │   ├── 002-ai-providers.md
│   │   ├── 003-i18n-strategy.md
│   │   ├── 004-seo-geo-strategy.md
│   │   ├── 005-quiz-affinity-system.md
│   │   └── 006-transparency-methodology.md
│   └── case-study/
│       ├── pt-BR.md               # Narrativa viva — atualizada pelos agentes
│       └── en-US.md
├── scripts/
│   ├── ai_client.py               # Multi-provider fallback + usage tracker
│   ├── collect_rss.py             # feedparser — 20 fontes RSS
│   ├── collect_parties.py         # BeautifulSoup — 5 sites partidários
│   ├── collect_polls.py           # Playwright — 6 institutos de pesquisa
│   ├── collect_social.py          # tweepy + YouTube API (opcional)
│   ├── summarize.py               # Resumos bilíngues para artigos novos
│   ├── analyze_sentiment.py       # Scores candidato × tema/fonte
│   ├── extract_quiz_positions.py  # Extrai posições verificáveis por tópico
│   ├── generate_rss_feed.py       # Gera /feed.xml e /feed-en.xml
│   ├── generate_seo_pages.py      # sitemap.xml + candidate/comparison JSONs
│   └── build_data.py              # Consolida JSONs, deduplica, limita 500 artigos
├── data/
│   ├── articles.json              # Feed principal (500 mais recentes)
│   ├── sentiment.json             # Scores candidato × tema e × fonte
│   ├── polls.json                 # Histórico de pesquisas eleitorais
│   ├── sources.json               # Metadados e status das fontes
│   ├── quiz.json                  # Questões + posições verificadas por tópico
│   ├── candidates.json            # Perfis completos (para páginas SEO)
│   └── ai_usage.json              # Rastreador de uso por provider
├── site/
│   ├── src/
│   │   ├── locales/
│   │   │   ├── pt-BR/
│   │   │   │   ├── common.json
│   │   │   │   ├── candidates.json
│   │   │   │   ├── quiz.json
│   │   │   │   ├── methodology.json
│   │   │   │   └── case-study.json
│   │   │   └── en-US/            # Mesma estrutura
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── CandidatePage.jsx       # /candidato/[slug] — SSG
│   │   │   ├── ComparisonPage.jsx      # /comparar/[a]-vs-[b] — GEO
│   │   │   ├── QuizPage.jsx            # /quiz
│   │   │   ├── QuizResult.jsx          # /quiz/resultado?r=abc123
│   │   │   ├── PollsPage.jsx           # /pesquisas
│   │   │   ├── MethodologyPage.jsx     # /metodologia
│   │   │   └── CaseStudyPage.jsx       # /sobre/caso-de-uso
│   │   ├── components/
│   │   │   ├── NewsFeed.jsx
│   │   │   ├── SentimentDashboard.jsx  # Heatmap toggle tema↔fonte + disclaimer
│   │   │   ├── PollTracker.jsx         # Recharts linha temporal
│   │   │   ├── QuizEngine.jsx          # Lógica do funil progressivo
│   │   │   ├── QuizResultCard.jsx      # Ranking + radar + explicação + fontes
│   │   │   ├── ShareButton.jsx         # Link ?r=... + clipboard
│   │   │   ├── LanguageSwitcher.jsx    # Toggle PT | EN
│   │   │   ├── MethodologyBadge.jsx    # Badge discreto "Como funciona?" em todos os dashboards
│   │   │   └── SourceFilter.jsx
│   │   ├── hooks/
│   │   │   ├── useData.js
│   │   │   └── useQuiz.js
│   │   ├── utils/
│   │   │   ├── affinity.js             # Algoritmo de funil progressivo + cálculo de afinidade
│   │   │   ├── shareUrl.js             # Encode/decode base64url do estado do quiz
│   │   │   └── seo.js                  # JSON-LD helpers
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/
│   │   ├── _headers                    # Cloudflare cache
│   │   ├── robots.txt                  # Permite GPTBot, ClaudeBot, PerplexityBot
│   │   ├── sitemap.xml                 # Gerado por generate_seo_pages.py
│   │   └── data/                       # JSONs copiados no build
│   ├── index.html
│   └── vite.config.js                  # vite-plugin-ssg configurado
├── PLAN.md
├── CHANGELOG.md
└── README.md
```

---

## FONTES

### RSS — 20 fontes (feedparser)
```python
RSS_SOURCES = [
    {"name":"G1 Política",      "url":"https://g1.globo.com/rss/g1/politica/",                 "category":"mainstream"},
    {"name":"UOL Notícias",     "url":"https://rss.uol.com.br/feed/noticias.xml",              "category":"mainstream"},
    {"name":"Folha Poder",      "url":"https://feeds.folha.uol.com.br/poder/rss091.xml",        "category":"mainstream"},
    {"name":"O Globo",          "url":"https://oglobo.globo.com/rss.xml",                       "category":"mainstream"},
    {"name":"Estadão Política", "url":"https://www.estadao.com.br/politica/feed/",              "category":"mainstream"},
    {"name":"Metrópoles",       "url":"https://www.metropoles.com/feed/",                       "category":"mainstream"},
    {"name":"Gazeta do Povo",   "url":"https://www.gazetadopovo.com.br/feed/",                  "category":"mainstream"},
    {"name":"Poder360",         "url":"https://www.poder360.com.br/feed/",                      "category":"politics"},
    {"name":"JOTA",             "url":"https://www.jota.info/feed",                             "category":"politics"},
    {"name":"Veja",             "url":"https://veja.abril.com.br/feed/",                        "category":"magazine"},
    {"name":"IstoÉ",            "url":"https://istoe.com.br/feed/",                             "category":"magazine"},
    {"name":"CartaCapital",     "url":"https://www.cartacapital.com.br/feed/",                  "category":"magazine"},
    {"name":"Reuters Brasil",   "url":"https://br.reuters.com/rssFeed/BRPT_InBrief",            "category":"international"},
    {"name":"BBC Brasil",       "url":"https://feeds.bbci.co.uk/portuguese/rss.xml",            "category":"international"},
    {"name":"DW Brasil",        "url":"https://rss.dw.com/rdf/rss-bra-all",                     "category":"international"},
    {"name":"El País Brasil",   "url":"https://brasil.elpais.com/rss/brasil/portada_es.xml",    "category":"international"},
    {"name":"Agência Brasil",   "url":"https://agenciabrasil.ebc.com.br/rss/politica/feed.xml", "category":"institutional"},
    {"name":"TSE",              "url":"https://www.tse.jus.br/comunicacao/noticias/rss",        "category":"institutional"},
    {"name":"Agência Câmara",   "url":"https://www.camara.leg.br/noticias/rss",                 "category":"institutional"},
    {"name":"Agência Senado",   "url":"https://www12.senado.leg.br/noticias/rss",               "category":"institutional"},
    {"name":"O Antagonista",    "url":"https://oantagonista.com.br/feed/",                    "category":"politics"},
]
```

### Partidos, Institutos e Social
```python
PARTY_SOURCES = [
    {"name":"PT",           "url":"https://pt.org.br/noticias/",                 "candidate_slugs":["lula"]},
    {"name":"PL",           "url":"https://pl.org.br/noticias/",                 "candidate_slugs":["flavio-bolsonaro"]},
    {"name":"Republicanos", "url":"https://republicanos10.org.br/noticias/",     "candidate_slugs":["tarcisio"]},
    {"name":"PSD",          "url":"https://psd.org.br/noticias/",                "candidate_slugs":["ratinho-jr","eduardo-leite"]},
    {"name":"Novo",         "url":"https://novo.org.br/noticias/",               "candidate_slugs":["zema"]},
    {"name":"União Brasil", "url":"https://uniaobrasil.org.br/noticias/",        "candidate_slugs":["caiado"]},
    {"name":"DC",           "url":"https://dc.org.br/noticias/",                 "candidate_slugs":["aldo-rebelo"]},
    {"name":"Missão",       "url":"https://missao.org.br/noticias/",             "candidate_slugs":["renan-santos"]},
]
# ── DADOS OFICIAIS TSE ──────────────────────────────────────────────────
# O TSE já está na lista de RSS_SOURCES acima para cobertura jornalística.
# Além disso, integrar as seguintes fontes de dados estruturados:
TSE_DATA_SOURCES = {
    "eleicoes_2026":    "https://www.tse.jus.br/eleicoes/eleicoes-2026",
    "calendario":       "https://www.tse.jus.br/eleicoes/calendario-eleitoral/calendario-eleitoral",
    "divulgacand":      "https://divulgacandcontas.tse.jus.br/divulga/",  # disponível após registro (15 ago 2026)
    "partidos_tse":     "https://www.tse.jus.br/partidos/partidos-registrados-no-tse/registrados-no-tse",
    "rss_noticias":     "https://www.tse.jus.br/comunicacao/noticias/rss",
}
# DATAS-CHAVE do calendário TSE (Fase 12 — gerar páginas estáticas com estes dados):
TSE_KEY_DATES = {
    "convencoes_inicio":    "2026-07-20",
    "convencoes_fim":       "2026-08-05",
    "registro_candidatos":  "2026-08-15",  # prazo máximo para registro no TSE
    "primeiro_turno":       "2026-10-04",
    "segundo_turno":        "2026-10-25",  # se necessário
}
# Uso no pipeline:
# 1. collect_rss.py: já inclui TSE RSS — coletar notícias oficiais sobre calendário e resoluções
# 2. generate_seo_pages.py: embeddar TSE_KEY_DATES nas páginas de candidato e home (JSON-LD Event)
# 3. CandidatePage.jsx: após 15 ago 2026, consultar DivulgaCand para status de registro
# 4. CountdownTimer: calcular dias restantes até primeiro_turno em tempo real

POLL_SOURCES = [
    {"name":"Datafolha",          "url":"https://datafolha.folha.uol.com.br/eleicoes/"},
    {"name":"Quaest",             "url":"https://quaest.com.br/pesquisas/"},
    {"name":"AtlasIntel",         "url":"https://atlasintel.com/eleicoes/"},
    {"name":"Paraná Pesquisas",   "url":"https://paranapesquisas.com.br/pesquisas/"},
    {"name":"PoderData",          "url":"https://www.poder360.com.br/poderdata/"},
    {"name":"Real Time Big Data", "url":"https://www.realtimebigdata.com.br/pesquisas.html"},
]
```

---

## CANDIDATOS E TÓPICOS DO QUIZ

```python
# PRÉ-CANDIDATOS CONFIRMADOS (março 2026)
# Fonte: https://exame.com/brasil/eleicoes-2026-quem-sao-os-pre-candidatos-a-presidencia-ate-agora/
# Convenções partidárias: 20 jul–5 ago 2026. Registro TSE: até 15 ago 2026.
# ATUALIZAR esta lista e candidates.json quando houver novos anúncios ou desistências.
CANDIDATES = [
    # CONFIRMADOS — pré-candidatura declarada publicamente
    {"slug":"lula",             "name":"Lula",            "full_name":"Luiz Inácio Lula da Silva","party":"PT",            "party_site":"https://pt.org.br",                "color":"#CC0000","twitter":"LulaOficial",      "status":"pre-candidate"},
    {"slug":"flavio-bolsonaro", "name":"Flávio Bolsonaro","full_name":"Flávio Bolsonaro",         "party":"PL",            "party_site":"https://pl.org.br",                "color":"#002776","twitter":"flaviobolsonaro",  "status":"pre-candidate"},
    {"slug":"caiado",           "name":"Caiado",          "full_name":"Ronaldo Caiado",           "party":"União Brasil",  "party_site":"https://uniaobrasil.org.br",       "color":"#FF8200","twitter":"RonaldoCaiado",    "status":"pre-candidate"},
    {"slug":"zema",             "name":"Zema",            "full_name":"Romeu Zema",               "party":"Novo",          "party_site":"https://novo.org.br",              "color":"#FF6600","twitter":"RomeuZema",        "status":"pre-candidate"},
    {"slug":"eduardo-leite",    "name":"Eduardo Leite",   "full_name":"Eduardo Leite",            "party":"PSD",           "party_site":"https://psd.org.br",               "color":"#4488CC","twitter":"eduardoleite_",    "status":"pre-candidate"},
    {"slug":"aldo-rebelo",      "name":"Aldo Rebelo",     "full_name":"Aldo Rebelo",              "party":"DC",            "party_site":"https://dc.org.br",                "color":"#5C6BC0","twitter":"AldoRebelo",       "status":"pre-candidate"},
    {"slug":"renan-santos",     "name":"Renan Santos",    "full_name":"Renan Santos",             "party":"Missão",        "party_site":"https://missao.org.br",            "color":"#26A69A","twitter":"RenanSantosMBL",   "status":"pre-candidate"},
    # COTADOS — muito especulados, decisão pendente até fim de março 2026
    {"slug":"ratinho-jr",       "name":"Ratinho Jr",      "full_name":"Carlos Massa Ratinho Jr",  "party":"PSD",           "party_site":"https://psd.org.br",               "color":"#0066CC","twitter":"ratinhojr",        "status":"speculated"},
    {"slug":"tarcisio",         "name":"Tarcísio",        "full_name":"Tarcísio de Freitas",      "party":"Republicanos",  "party_site":"https://republicanos10.org.br",    "color":"#1A3A6B","twitter":"TarcisioGomes",    "status":"speculated"},
]
# NOTA: Tarcísio declara publicamente que disputará reeleição em SP.
# PSD (Kassab) confirma que Ratinho Jr e Eduardo Leite se retiram se Tarcísio entrar.
# Monitorar: https://www.tse.jus.br/eleicoes/eleicoes-2026 para registros oficiais pós-convenção.

QUIZ_TOPICS = [
    {"id":"economia",      "label_pt":"Economia e emprego",        "label_en":"Economy & employment"},
    {"id":"seguranca",     "label_pt":"Segurança pública",         "label_en":"Public safety"},
    {"id":"saude",         "label_pt":"Saúde e SUS",               "label_en":"Healthcare"},
    {"id":"educacao",      "label_pt":"Educação",                  "label_en":"Education"},
    {"id":"meio_ambiente", "label_pt":"Meio ambiente e clima",     "label_en":"Environment & climate"},
    {"id":"corrupcao",     "label_pt":"Combate à corrupção",       "label_en":"Anti-corruption"},
    {"id":"armas",         "label_pt":"Porte de armas",            "label_en":"Gun rights"},
    {"id":"privatizacao",  "label_pt":"Privatizações",             "label_en":"Privatization"},
    {"id":"previdencia",   "label_pt":"Previdência social",        "label_en":"Social security"},
    {"id":"politica_externa",  "label_pt":"Política externa",          "label_en":"Foreign policy"},
    {"id":"lgbtq",         "label_pt":"Direitos LGBTQIA+",         "label_en":"LGBTQIA+ rights"},
    {"id":"aborto",        "label_pt":"Aborto e pauta moral",      "label_en":"Abortion & moral issues"},
    {"id":"indigenas",     "label_pt":"Terras indígenas",          "label_en":"Indigenous lands"},
    {"id":"impostos",      "label_pt":"Reforma tributária",        "label_en":"Tax reform"},
    {"id":"midia",         "label_pt":"Liberdade de imprensa",     "label_en":"Press freedom"},
]
```

---

## QUIZ DE AFINIDADE POLÍTICA — ESPECIFICAÇÃO COMPLETA

### Princípios de Design
1. **Framing invertido:** o usuário escolhe posições políticas — não candidatos. As posições são reais, extraídas de declarações verificadas nas notícias coletadas. As fontes (declarações originais) são reveladas **somente no resultado final**, após todas as questões respondidas, para evitar identificação precoce com candidatos.
2. **Funil progressivo silencioso:** o sistema elimina candidatos internamente conforme as respostas divergem, mas **não comunica ao usuário** quais candidatos foram descartados. O usuário percebe apenas que o quiz termina — não que houve eliminações. Isso mantém o engajamento neutro.
3. **Candidatos com posição `unclear` são omitidos silenciosamente** naquela questão específica, sem aviso. O cálculo de afinidade final compensa proporcionalmente.
4. **Apenas posições com `confidence: high|medium`** são publicadas no `quiz.json`. Posições `low` ou `unclear` nunca aparecem como opções.

### `data/quiz.json` — Schema completo
```json
{
  "generated_at": "2026-03-05T03:00:00Z",
  "ordered_topics": ["armas","aborto","privatizacao","indigenas","lgbtq","economia","seguranca","saude","corrupcao","meio_ambiente"],
  "topics": {
    "armas": {
      "divergence_score": 0.95,
      "question_pt": "Qual política de segurança armada faz mais sentido para você?",
      "question_en": "Which gun policy makes more sense to you?",
      "options": [
        {
          "id": "opt_a",
          "text_pt": "Ampliação do porte com treinamento obrigatório e rastreabilidade",
          "text_en": "Expanded carry rights with mandatory training and traceability",
          "weight": 2,
          "candidate_slug": "tarcisio",
          "source_pt": "Discurso na Alesp, 12/02/2026",
          "source_en": "Speech at São Paulo State Assembly, Feb 12, 2026",
          "confidence": "high"
        },
        {
          "id": "opt_b",
          "text_pt": "Restrição ao porte civil; armas devem ser exclusividade das forças de segurança",
          "text_en": "Restricting civilian carry; weapons should be exclusive to security forces",
          "weight": -2,
          "candidate_slug": "lula",
          "source_pt": "Entrevista ao Jornal Nacional, 05/03/2026",
          "source_en": "Interview with Jornal Nacional, Mar 5, 2026",
          "confidence": "high"
        }
      ]
    }
  }
}
```

> **Nota:** cada opção é a posição de um candidato específico — mas o `candidate_slug` é usado apenas no cálculo interno e na revelação pós-resultado. A UI do quiz nunca exibe `candidate_slug` ou `source_*` durante as perguntas.

### `scripts/extract_quiz_positions.py` — Pipeline de extração

```python
"""
Roda diariamente (update-quiz.yml). Para cada tópico:
1. Filtra articles.json por candidato + tópico
2. Extrai posição via ai_client.extract_candidate_position()
3. Calcula divergence_score por tópico
4. Ordena tópicos por divergência decrescente
5. Seleciona os 10-15 tópicos com maior divergência
6. Persiste em data/quiz.json apenas posições high/medium confidence
"""

STANCE_MAP = {"favor": 2, "neutral": 0, "against": -2, "unclear": None}

def divergence_score(positions: list) -> float:
    stances = [STANCE_MAP[p["stance"]] for p in positions
               if p.get("confidence") in ("high","medium") and STANCE_MAP.get(p["stance"]) is not None]
    if len(stances) < 2: return 0.0
    return (max(stances) - min(stances)) / 4.0   # normalizado 0.0–1.0

def select_quiz_topics(all_topics: dict, min_topics=10, max_topics=15) -> list:
    scored = [(tid, divergence_score(list(positions.values())))
              for tid, positions in all_topics.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    # Garante cobertura temática — pelo menos 1 de cada cluster
    CLUSTERS = {
        "valores": ["armas","aborto","lgbtq","indigenas"],
        "economia": ["economia","privatizacao","impostos","previdencia"],
        "governanca": ["corrupcao","midia","politica_externa"],
        "social": ["saude","educacao","seguranca","meio_ambiente"],
    }
    selected = []
    for cluster_topics in CLUSTERS.values():
        best = next((t for t,_ in scored if t in cluster_topics and t not in selected), None)
        if best: selected.append(best)
    # Completa até max_topics com os de maior divergência ainda não incluídos
    for topic_id, score in scored:
        if len(selected) >= max_topics: break
        if topic_id not in selected and score >= 0.5:
            selected.append(topic_id)
    return selected[:max_topics]
```

### `site/src/utils/affinity.js` — Algoritmo do funil progressivo

```javascript
/**
 * Funil progressivo silencioso:
 * - Calcula afinidade acumulada após cada resposta
 * - Candidatos com posição unclear naquela questão são ignorados (não penalizados)
 * - Ao final, normaliza scores pelos tópicos em que cada candidato participou
 * - Ordena por afinidade decrescente
 *
 * @param {Object} answers - { topicId: { optionId, weight } }
 * @param {Object} quizData - data/quiz.json
 * @returns {Array} candidatos ordenados + byTopic scores
 */
export function calculateAffinity(answers, quizData) {
  const scores = {};  // { candidateSlug: { total: 0, count: 0, byTopic: {} } }

  for (const [topicId, answer] of Object.entries(answers)) {
    const topic = quizData.topics[topicId];
    if (!topic) continue;

    for (const option of topic.options) {
      const slug = option.candidate_slug;
      if (!scores[slug]) scores[slug] = { total: 0, count: 0, byTopic: {} };

      // Similaridade: distância entre peso escolhido e peso da posição do candidato
      const distance   = Math.abs(answer.weight - option.weight);  // 0–4
      const similarity = 1 - (distance / 4);                        // 0.0–1.0

      scores[slug].total              += similarity;
      scores[slug].count              += 1;
      scores[slug].byTopic[topicId]   = similarity;
    }
  }

  return Object.entries(scores)
    .map(([slug, data]) => ({
      slug,
      affinity: data.count > 0 ? Math.round((data.total / data.count) * 100) : 0,
      byTopic:  data.byTopic,
    }))
    .sort((a, b) => b.affinity - a.affinity);
}

/**
 * Determina quantas questões restam com base nos candidatos ainda relevantes.
 * Usado internamente para saber quando o quiz pode terminar antecipadamente
 * (quando 1 candidato já lidera com gap > 40% sobre o segundo).
 */
export function shouldContinueQuiz(results, answeredCount, totalQuestions) {
  if (answeredCount < Math.min(5, Math.floor(totalQuestions * 0.4))) return true;
  if (results.length < 2) return false;
  const gap = results[0].affinity - results[1].affinity;
  return gap < 40 || answeredCount < totalQuestions;
}
```

### `<QuizResultCard />` — Revelação pós-resultado

O resultado é revelado em sequência após a última resposta:

1. **Ranking** — lista de candidatos em ordem decrescente de afinidade, com barra de progresso colorida (`candidate.color`)
2. **Gráfico Radar** — `recharts RadarChart`, eixos = tópicos respondidos, top 3 candidatos sobrepostos
3. **Explicação textual** — para o top 3: quais tópicos geraram maior concordância e maior discordância, usando linguagem natural
4. **Revelação das fontes** — só aqui: para cada opção que o usuário escolheu, exibe `source_pt` ou `source_en` e o nome do candidato correspondente. Esta é a primeira vez que o usuário vê a associação resposta → candidato.
5. **Compartilhamento** — botão copia `?r=base64url` para clipboard

```javascript
// shareUrl.js
export const encodeResult = (answers) =>
  btoa(JSON.stringify(answers)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');

export const decodeResult = (r) =>
  JSON.parse(atob(r.replace(/-/g,'+').replace(/_/g,'/')));
```

---

## FEED RSS/ATOM PRÓPRIO

### `scripts/generate_rss_feed.py`

Gera dois feeds estáticos após cada `build_data.py`:
- `site/public/feed.xml` — RSS 2.0 em pt-BR (50 artigos mais recentes)
- `site/public/feed-en.xml` — RSS 2.0 em en-US

```python
import xml.etree.ElementTree as ET
from datetime import datetime

def generate_rss(articles: list, language: str = "pt-BR") -> str:
    """Gera RSS 2.0 válido com os 50 artigos mais recentes."""
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:atom":"http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Eleições BR 2026" if language == "pt-BR" else "Brazil Elections 2026"
    ET.SubElement(channel, "link").text = "https://eleicoes2026.com.br"
    ET.SubElement(channel, "description").text = (
        "Monitoramento em tempo real das eleições presidenciais brasileiras de 2026"
        if language == "pt-BR" else
        "Real-time monitoring of Brazil's 2026 presidential elections"
    )
    ET.SubElement(channel, "language").text = language
    ET.SubElement(channel, "atom:link", href=f"https://eleicoes2026.com.br/feed{'--en' if language=='en-US' else ''}.xml",
                  rel="self", type="application/rss+xml")
    for art in articles[:50]:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = art["title"]
        ET.SubElement(item, "link").text = art["url"]
        ET.SubElement(item, "description").text = art["summaries"].get(language, "")
        ET.SubElement(item, "pubDate").text = art["published_at"]
        ET.SubElement(item, "guid").text = art["id"]
        for c in art.get("candidates_mentioned", []):
            ET.SubElement(item, "category").text = c
    return ET.tostring(rss, encoding="unicode", xml_declaration=True)
```

Adicionar `<link>` autodiscovery no `index.html`:
```html
<link rel="alternate" type="application/rss+xml" title="Eleições BR 2026" href="/feed.xml" />
<link rel="alternate" type="application/rss+xml" title="Brazil Elections 2026" href="/feed-en.xml" />
```

---

## PÁGINA DE METODOLOGIA — `/metodologia`

### Conteúdo obrigatório (implementar em `MethodologyPage.jsx` + locales)

A página deve conter, em pt-BR e en-US:

**1. Disclaimer principal** (exibido em destaque visual):
> Este portal é um projeto independente, sem filiação partidária ou financiamento eleitoral. Não há intervenção editorial de nenhuma forma: os artigos são coletados automaticamente de fontes públicas, os resumos são gerados por inteligência artificial, e as análises de sentimento são derivadas algoritmicamente. O código-fonte completo está disponível para consulta e auditoria pública em [github.com/carlosduplar/eleicoes-2026-monitor](https://github.com/carlosduplar/eleicoes-2026-monitor).

**2. Como funciona o pipeline** (descrição técnica acessível):
- Coleta: RSS de 20 veículos + scraping de sites partidários e institutos de pesquisa, a cada 30 minutos
- Sumarização: modelos de linguagem open-source (lista de providers na ordem de uso)
- Sentimento: análise algorítmica — explicar que scores refletem o tom das notícias coletadas, não uma avaliação editorial
- Pesquisas eleitorais: coletadas automaticamente dos sites dos institutos; reproduzem os dados originais sem modificação
- Quiz de Afinidade: posições extraídas de declarações verificadas nas notícias; fontes exibidas no resultado

**3. Limitações conhecidas** (honestidade como ativo de credibilidade):
- Modelos de IA podem cometer erros de interpretação
- A cobertura de fontes pode ter viés de disponibilidade (veículos sem RSS não são incluídos)
- Posições de candidatos evoluem ao longo da campanha; o pipeline atualiza diariamente
- Análise de sentimento não equivale a pesquisa de opinião

**4. Como reportar erros:**
- Link para abrir issue no repositório GitHub público
- Email de contato (opcional)

### `<MethodologyBadge />`
Componente discreto exibido em todos os dashboards (sentimento, pesquisas, quiz):
```jsx
// Ícone de informação + tooltip + link para /metodologia
// Texto: "Como funciona?" / "How does this work?"
// Posição: canto superior direito de cada card de dashboard
```

---

## SEO / GEO

### Páginas com SSG (pre-render obrigatório)

| Rota | Schema JSON-LD | Prioridade |
|------|---------------|------------|
| `/` | `WebSite` + `ItemList` | Máxima |
| `/candidato/[slug]` | `Person` + `ProfilePage` | Alta |
| `/comparar/[a]-vs-[b]` | `FAQPage` + `Article` | Alta (GEO) |
| `/quiz` | `Quiz` + `FAQPage` | Alta (viral) |
| `/pesquisas` | `Dataset` | Média |
| `/metodologia` | `AboutPage` + `FAQPage` | Média (credibilidade) |
| `/sobre/caso-de-uso` | `TechArticle` | Média |

### Comparações pré-geradas (GEO — queries "X vs Y")
```python
COMPARISON_PAIRS = [
    ("lula","tarcisio"), ("lula","caiado"), ("tarcisio","caiado"),
    ("tarcisio","ratinho-jr"), ("lula","zema"), ("caiado","ratinho-jr"),
    ("lula","ratinho-jr"), ("tarcisio","zema"),
]
```

### `site/public/robots.txt`
```
User-agent: *
Allow: /
Sitemap: https://eleicoes2026.com.br/sitemap.xml

# Permitir crawlers de IA explicitamente (GEO — tráfego via assistentes de IA)
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: GoogleOther
Allow: /
```

### `site/public/_headers` (Cloudflare)
```
/*
  Cache-Control: public, max-age=1800, stale-while-revalidate=300
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin

/data/*.json
  Cache-Control: public, max-age=1800, stale-while-revalidate=300
  Access-Control-Allow-Origin: *

/feed*.xml
  Cache-Control: public, max-age=1800
  Content-Type: application/rss+xml; charset=utf-8

/quiz*
  Cache-Control: public, max-age=3600
```

---

## GITHUB ACTIONS — 3 WORKFLOWS

### `collect.yml` — cron 10min
```yaml
name: Collect & Process News
on:
  schedule: [{cron: '*/10 * * * *'}]
  workflow_dispatch:
jobs:
  collect:
    runs-on: ubuntu-latest
    permissions: {contents: write}
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
        with: {fetch-depth: 1}
      - uses: actions/setup-python@v5
        with: {python-version: '3.12', cache: 'pip'}
      - run: pip install -r requirements.txt
      - run: playwright install chromium --with-deps
      - name: Collect
        env:
          TWITTER_BEARER_TOKEN: ${{ secrets.TWITTER_BEARER_TOKEN }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: |
          python scripts/collect_rss.py
          python scripts/collect_parties.py
          python scripts/collect_polls.py    || echo "polls failed"
          python scripts/collect_social.py   || echo "social failed"
      - name: AI Processing
        env:
          NVIDIA_API_KEY:       ${{ secrets.NVIDIA_API_KEY }}
          OPENROUTER_API_KEY:   ${{ secrets.OPENROUTER_API_KEY }}
          OLLAMA_API_KEY:       ${{ secrets.OLLAMA_API_KEY }}
          VERTEX_ACCESS_TOKEN:  ${{ secrets.VERTEX_ACCESS_TOKEN }}
          VERTEX_BASE_URL:      ${{ secrets.VERTEX_BASE_URL }}
          XIAOMI_MIMO_API_KEY:  ${{ secrets.XIAOMI_MIMO_API_KEY }}
        run: |
          python scripts/summarize.py
          python scripts/analyze_sentiment.py
          python scripts/build_data.py
          python scripts/generate_rss_feed.py
      - name: Commit
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/ site/public/feed*.xml
          git diff --staged --quiet || (git commit -m "chore: update $(date -u +%Y-%m-%dT%H:%M:%SZ)" && git push)
```

### `update-quiz.yml` — cron diário 3h UTC
```yaml
name: Update Quiz Positions
on:
  schedule: [{cron: '0 3 * * *'}]
  workflow_dispatch:
jobs:
  quiz:
    runs-on: ubuntu-latest
    permissions: {contents: write}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12', cache: 'pip'}
      - run: pip install -r requirements.txt
      - name: Extract positions
        env:
          NVIDIA_API_KEY:       ${{ secrets.NVIDIA_API_KEY }}
          OPENROUTER_API_KEY:   ${{ secrets.OPENROUTER_API_KEY }}
          OLLAMA_API_KEY:       ${{ secrets.OLLAMA_API_KEY }}
          VERTEX_ACCESS_TOKEN:  ${{ secrets.VERTEX_ACCESS_TOKEN }}
          VERTEX_BASE_URL:      ${{ secrets.VERTEX_BASE_URL }}
        run: python scripts/extract_quiz_positions.py
      - name: Commit quiz data
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/quiz.json
          git diff --staged --quiet || (git commit -m "chore: update quiz $(date -u +%Y-%m-%d)" && git push)
```

### `deploy.yml` — push em main
```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
    paths: ['site/**','data/**','docs/case-study/**']
permissions: {pages: write, id-token: write}
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    environment: {name: github-pages, url: '${{ steps.deployment.outputs.page_url }}'}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12', cache: 'pip'}
      - run: pip install -r requirements.txt
      - run: python scripts/generate_seo_pages.py
      - uses: actions/setup-node@v4
        with: {node-version: '20', cache: 'npm', cache-dependency-path: 'site/package-lock.json'}
      - run: |
          cp -r data/ site/public/data/
          cp -r docs/case-study/ site/public/case-study/
      - name: Build SSG
        working-directory: site
        run: npm ci && npm run build
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with: {path: site/dist}
      - uses: actions/deploy-pages@v4
        id: deployment
```

---

## SCHEMAS DE DADOS

### `data/articles.json`
```json
[{
  "id": "sha256(url.encode())[:16]",
  "title": "Título",
  "url": "https://...",
  "source": "G1 Política",
  "source_category": "mainstream",
  "published_at": "2026-03-05T10:00:00Z",
  "collected_at": "2026-03-05T10:30:00Z",
  "summaries": {"pt-BR": "Resumo...", "en-US": "Summary..."},
  "candidates_mentioned": ["Lula"],
  "topics": ["economia"],
  "sentiment_per_candidate": {"Lula": "positivo"},
  "_ai_provider": "nvidia",
  "_ai_model": "qwen/qwen3.5-397b-a17b"
}]
```

### `data/sentiment.json`
```json
{
  "updated_at": "2026-03-05T10:30:00Z",
  "article_count": 347,
  "methodology_url": "/metodologia",
  "disclaimer_pt": "Análise algorítmica do tom das notícias coletadas. Não representa pesquisa de opinião.",
  "disclaimer_en": "Algorithmic analysis of collected news tone. Does not represent opinion polling.",
  "by_topic":  {"Lula": {"economia": 0.3}},
  "by_source": {"Lula": {"mainstream": 0.2}}
}
```

---

## SECRETS NO GITHUB

| Secret | Provider | Custo | Prioridade |
|--------|----------|-------|------------|
| `NVIDIA_API_KEY` | NVIDIA NIM (build.nvidia.com) | Gratuito | 1º |
| `OPENROUTER_API_KEY` | OpenRouter (openrouter.ai) | Gratuito (200/dia) | 2º |
| `OLLAMA_API_KEY` | Ollama Cloud (ollama.com) | Gratuito | 3º |
| `VERTEX_ACCESS_TOKEN` | Google Vertex AI | Google AI Pro (inclui $10/mês Vertex) | 4º |
| `VERTEX_BASE_URL` | Google Vertex AI Console | — | 4º |
| `STITCH_API_KEY` | Google Stitch → Settings → API Keys → Create API Key | Gratuito | Fase 0+ |
| `VERTEX_SEARCH_ENGINE_ID` | Vertex AI Search (GenAI App Builder) | Trial credit 773 CHF | Fase 17 |
| `GCP_PROJECT_ID` | Google Cloud | — | Fase 17 |
| `XIAOMI_MIMO_API_KEY` | Xiaomi MiMo (api.xiaomimimo.com) | Pago | 5º |
| `TWITTER_BEARER_TOKEN` | Twitter API v2 | Opcional | — |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | Opcional | — |

**Vertex AI setup:** criar Service Account com roles `Vertex AI User` + `Discovery Engine Admin` → JSON key → secret `GOOGLE_APPLICATION_CREDENTIALS` → no Actions usar `gcloud auth activate-service-account` para gerar `VERTEX_ACCESS_TOKEN`.

---

## WIREFRAMES DE REFERÊNCIA (Google Stitch)

Antes de implementar qualquer componente frontend, consultar o wireframe correspondente em `docs/wireframes/`. Os wireframes foram gerados no **Google Stitch** (stitch.withgoogle.com) com workflow em duas etapas: **Gemini 3.1 Pro** para o wireframe inicial → **Gemini 3.0 Flash** para conversão a HTML/CSS. Assets estáticos (OG images, hero images, imagens de compartilhamento do quiz) gerados via **Nano Banana** (Gemini 3 Pro Image / Gemini 3.1 Flash Image) em `site/public/assets/generated/`. O Stitch tem MCP server oficial **remoto** em `https://stitch.googleapis.com/mcp` (autenticação via API Key: header `X-Goog-Api-Key`). O Opus 4.6 usa as ferramentas nativas do servidor (`list_projects`, `list_screens`, `get_project`, `get_screen`, `generate_screen_from_text`) durante a implementação — wireframes são fonte viva, não só artefatos estáticos. PNGs e HTMLs em `docs/wireframes/` servem como referência visual e registro histórico. A skill **frontend-design** refina estética e interações além da baseline.

| Arquivo | Componente React |
|---------|-----------------|
| WF-01 *(a criar via prompt-stitch-harmonizacao.md)* | `Home.jsx`, `NewsFeed.jsx`, `SourceFilter.jsx` |
| WF-02/03 → `sentiment_dashboard_variant_2_modern_dashboard_6/screen.png` | `SentimentDashboard.jsx` (views A e B) |
| WF-04 → `polling_tracker_variant_2_modern_dashboard_7/screen.png` | `PollTracker.jsx`, `PollsPage.jsx` |
| WF-05 *(a criar via prompt-stitch-harmonizacao.md)* | `QuizEngine.jsx`, `QuizPage.jsx` |
| WF-06 *(a criar via prompt-stitch-harmonizacao.md)* | `QuizResultCard.jsx`, `QuizResult.jsx` |
| WF-07 *(a criar via prompt-stitch-harmonizacao.md)* | `CandidatePage.jsx` |
| WF-08 → `candidate_comparison_editorial_variant_1_7/screen.png` | `ComparisonPage.jsx` |
| WF-09 → `methodology_editorial_transparency_variant_1_4/screen.png` | `MethodologyPage.jsx` |
| WF-10 → `case_study_editorial_longform_variant_1_4/screen.png` | `CaseStudyPage.jsx` |
| WF-11 → `mobile_news_feed_editorial_variant_1_6/screen.png` | `Home.jsx` (mobile 390px) |
| WF-12 → `mobile_quiz_question_and_result_variant_1_6/screen.png` | `QuizEngine.jsx`, `QuizResultCard.jsx` (mobile) |

> **Mapeamento real de diretórios em `docs/wireframes/` (março 2026):**
>
> | Código | Diretório real | Status |
> |--------|----------------|--------|
> | WF-01 | *(a criar — Sessão Stitch de harmonização)* | 🔴 Faltando |
> | WF-02/03 | `sentiment_dashboard_variant_2_modern_dashboard_6` | 🟡 Harmonizar |
> | WF-04 | `polling_tracker_variant_2_modern_dashboard_7` | 🟡 Harmonizar |
> | WF-05/06 | *(a criar — Sessão Stitch de harmonização)* | 🔴 Faltando |
> | WF-07 | *(a criar — Sessão Stitch de harmonização)* | 🔴 Faltando |
> | WF-08 | `candidate_comparison_editorial_variant_1_7` | 🟡 Harmonizar |
> | WF-09 | `methodology_editorial_transparency_variant_1_4` | 🟡 Harmonizar |
> | WF-10 | `case_study_editorial_longform_variant_1_4` | 🟡 Harmonizar |
> | WF-11 | `mobile_news_feed_editorial_variant_1_6` | 🟡 Harmonizar |
> | WF-12 | `mobile_quiz_question_and_result_variant_1_6` | 🟡 Harmonizar |
> | — | `prompt_eleicoes2026_v5.md_8` | ⚫ Não é screen de design — ignorar |
>
> Executar a Sessão de harmonização com `prompt-stitch-harmonizacao.md` **antes** de iniciar a Fase 0 de implementação. O ADR `docs/adr/000-wireframes.md` documenta: paleta com hex por candidato, tipografia, layout desktop/mobile, modelos (Gemini 3.1 Pro + 3.0 Flash), assets Nano Banana, e este mapeamento WF→diretório.

---

## ORDEM DE IMPLEMENTAÇÃO — 16 FASES

Após cada fase, acionar **docs-maintainer skill**: ADR correspondente + atualizar PLAN.md, CHANGELOG.md, `docs/case-study/pt-BR.md` e `en-US.md`.

| # | Fase | Entregas | ADR |
|---|------|----------|-----|
| 0 | Wireframes | Revisar `docs/wireframes/` (WF-01 a WF-12 gerados no Stitch), criar ADR 000 | 000 |
| 1 | Core | Estrutura de dirs, requirements.txt, .gitignore, PLAN.md inicial | 001 |
| 2 | AI Client | ai_client.py completo, usage tracker, batch processing | 002 |
| 3 | Coleta RSS | collect_rss.py, build_data.py, deduplicação sha256 | — |
| 4 | Frontend MVP | React+Vite, react-i18next, LanguageSwitcher, NewsFeed básico (seguindo WF-01) | 003 |
| 5 | CI/CD | collect.yml, deploy.yml, GitHub Pages ativo, validar com workflow_dispatch | — |
| 6 | IA Pipeline | summarize.py bilíngue, analyze_sentiment.py | — |
| 7 | Dashboard | SentimentDashboard (heatmap + toggle, WF-02/03) + MethodologyBadge | — |
| 8 | Pesquisas | collect_polls.py (Playwright), PollTracker (WF-04) | — |
| 9 | RSS Feed | generate_rss_feed.py, /feed.xml, /feed-en.xml, autodiscovery | — |
| 10 | Metodologia | MethodologyPage.jsx (WF-09), disclaimer, /metodologia, ADR 006 | 006 |
| 11 | Quiz | extract_quiz_positions.py, update-quiz.yml, QuizPage (WF-05), QuizResultCard (WF-06) com revelação de fontes | 005 |
| 12 | SEO/GEO | generate_seo_pages.py, CandidatePage (WF-07), ComparisonPage (WF-08), JSON-LD, sitemap, robots.txt | 004 |
| 13 | Case Study | CaseStudyPage (WF-10), /sobre/caso-de-uso, docs bilíngues publicados no site | — |
| 14 | Partidos + Social | collect_parties.py, collect_social.py (opcional) | — |
| 15 | Mobile Polish | Revisar breakpoints mobile (WF-11, WF-12), touch targets, bottom nav | — |
| 16 | QA Final | test-writer, security-threat-modeler, seo-audit, tech-lead-reviewer, README.md final | — |

---

## VERTEX AI SEARCH — BUSCA SEMÂNTICA (GenAI App Builder)

### Contexto dos créditos
O trial credit "GenAI App Builder" (773 CHF, vence 2027-03-02) cobre o SKU group **Vertex AI Search and Conversation** — especificamente **Vertex AI Search** (ex-Discovery AI / Enterprise Search). Não cobre chamadas Gemini API diretamente.

### Aplicação no projeto
Substituir a filtragem client-side do `articles.json` por Vertex AI Search. O campo de busca passa de filtro por texto literal para **interface de linguagem natural sobre o corpus eleitoral**: query "posição de Tarcísio sobre privatização" retorna os artigos semanticamente relevantes mesmo sem correspondência exata de termos.

Esta é a feature de maior valor de aprendizado do projeto: RAG sobre corpus próprio, indexação de documentos, Discovery Engine API, grounding — competências que transferem para qualquer projeto de enterprise AI.

### Implementação — Fase 17 (extensão pós-QA)
```
scripts/index_to_vertex_search.py   # indexa articles.json no data store
site/src/hooks/useSearch.js         # useSearch com fallback local se Vertex não disponível
docs/adr/007-vertex-search.md       # ADR documentando a decisão e setup
```

Configuração no Console: AI Applications → Agent Builder → criar Search App "Generic" → Data Store JSON → anotar ENGINE_ID → secret `VERTEX_SEARCH_ENGINE_ID`.

> **Nota:** o portal funciona 100% sem Vertex AI Search (fallback client-side). É um upgrade opcional que aproveita os créditos e aprofunda o aprendizado. Implementar apenas após o QA Final (Fase 16).

---

## ENTREGÁVEL ADICIONAL — `copilot-instructions.md` DO PROJETO

O prompt Opus deve gerar como parte da Fase 1 (Core) um arquivo `.github/copilot-instructions.md` **específico para o projeto**, derivado do `copilot-instructions.md` geral do ambiente mas com adições específicas:

```markdown
# Copilot Instructions — eleicoes-2026-monitor

<!-- Herda os princípios gerais do ambiente -->
<!-- Adições específicas deste projeto: -->

## Projeto
Portal de monitoramento bilíngue (pt-BR + en-US) das eleições BR 2026.
Stack: Python 3.12 + React + Vite + vite-plugin-ssg + GitHub Pages + GitHub Actions.
Powershell 7 no Windows 11. Comandos de shell devem usar sintaxe PowerShell.

## Regras de pipeline
- Scripts Python são idempotentes: rodar 2x sem duplicar dados
- id = sha256(url.encode())[:16] em todos os scripts de coleta
- Erros de IA nunca interrompem o pipeline (try/except + log)
- summaries sempre com pt-BR e en-US antes de commitar artigos

## Regras de frontend
- O quiz NUNCA exibe candidate_slug ou source_* durante as perguntas
- MethodologyBadge obrigatório em todos os componentes de dados
- sentiment.json sempre inclui disclaimer_pt e disclaimer_en
- Loading, empty e error state em todos os componentes de dados

## Stitch MCP
Configurado no cliente MCP com a API Key do Stitch (`X-Goog-Api-Key`).
Para Claude Code: `claude mcp add stitch --transport http https://stitch.googleapis.com/mcp --header "X-Goog-Api-Key: <KEY>" -s user`
Para Gemini CLI: `gemini extensions install https://github.com/gemini-cli-extensions/stitch`
projectId do projeto Stitch: confirmar via ferramenta `list_projects` na Fase 0.
Antes de implementar qualquer componente frontend:
1. list_screens(projectId) para obter o screenId correto (salvo no ADR 000)
2. `get_screen(project_id, screen_id)` para inspecionar detalhes da tela
3. Adaptar para React + Vite + react-i18next
Para listar todos os screens do projeto: `list_screens(project_id)` na Fase 0 para confirmar screen_ids.
Para gerar nova tela: `generate_screen_from_text(project_id, prompt, model_id)` com `GEMINI_3_PRO` ou `GEMINI_3_FLASH`.
PNGs em docs/wireframes/ para referência visual e histórico.

## Workflow docs
docs-maintainer skill após cada fase: atualizar PLAN.md, CHANGELOG.md,
docs/case-study/pt-BR.md e docs/case-study/en-US.md.
```

O Opus deve personalizar este template com quaisquer convenções específicas descobertas durante o planejamento da Fase 1, incluindo o projectId correto do Stitch.

---

## HIERARQUIA DE IMPLEMENTAÇÃO — AGENTES E PAPÉIS

Esta seção define os papéis, responsabilidades e protocolo de handoff entre os agentes de desenvolvimento.
O Opus deve criar `docs/agent-protocol.md` na Fase 1 com este contrato formalizado.

### Papéis

| Agente | Ferramenta | Nível | Responsabilidade |
|--------|-----------|-------|-----------------|
| **Arquiteto** | Claude Opus 4.6 (Copilot CLI) | Estratégico | Lê requisitos de negócio, toma decisões arquiteturais, cria PLAN.md, define schemas (JSON Schema + TS types) na Fase 1, chama Stitch MCP para obter HTML/CSS antes de cada fase de frontend |
| **Tático** | GPT-5.3-Codex xhigh (Copilot CLI) | Tático | Lê plano do Arquiteto, subdivide em task specs detalhadas em `tasks/phaseNN/`, cria cenários de teste com casos de borda e criterios de aceite explícitos |
| **Operacional** | MiniMax M2.5 (OpenCode) | Operacional | Recebe task specs e cenários do Tático, implementa em RALPH loops (run, assert, loop, push, halt) até todos os testes passarem ou limite de escalação atingido |
| **QA** | Gemini 3 Flash (Gemini CLI) | Qualidade | Executa testes de frontend com integração nativa Playwright + Chrome, janela de contexto extendida para relatórios, reporta falhas estruturadas de volta ao Tático |

**Papel transversal — Context7:** todo agente consulta Context7 antes de qualquer decisão de biblioteca, API, ou dependência. Regra obrigatória no `copilot-instructions.md` do projeto, não recomendação.

**Papel transversal — Watchdog pós-deploy (Gemini 3 Flash, Gemini CLI):** após cada deploy ao GitHub Pages, Gemini ingere o log completo dos últimos 7 dias de todos os workflows (collect, validate, curate, deploy) e gera `data/pipeline_health.json` com: falhas recorrentes, providers com taxa de erro > 10%, artigos travados em `status: raw` por mais de 6h, e alerta se `curate.yml` não rodou nas últimas 8h. Executado como `watchdog.yml` — cron `0 6 * * *`. Janela de contexto estendida do Gemini é necessária para ingerir os logs completos.

**Papel transversal — Schema Guardian (Opus, Fase 1):** Opus define e commita `docs/schemas/` com JSON Schema + TypeScript types para todos os arquivos em `data/` antes de qualquer implementação. Codex valida conformidade dos schemas antes de escrever qualquer task spec que consuma esses dados. Isso previne a classe de erros de "Python escreve X, React espera Y" que emerge na Fase 6/7.

### Protocolo de handoff por arquivo

```
plans/
  phase-NN-arch.md        ← output do Arquiteto (Opus)
  phase-NN-arch.DONE      ← sinal de conclusão do Arquiteto

tasks/
  phase-NN/
    task-01-spec.md       ← output do Tático (Codex): spec + cenários de teste
    task-01-spec.DONE     ← sinal de conclusão do Tático
    ESCALATION.md         ← escrito pelo Operacional quando atinge limite

qa/
  phase-NN-report.json    ← output do QA (Gemini): falhas estruturadas
  phase-NN-report.DONE    ← sinal de aprovação do QA
```

### Protocolo de escalação — RALPH loop com ejeção

O MiniMax opera em RALPH loops: **R**un tests → **A**ssert results → **L**oop se falha → **P**ush se passa → **H**alt se escalação.

Critério de ejeção obrigatório (configurar no `copilot-instructions.md` do projeto):
```
SE tentativas > 3 E mesmo erro nas últimas 2 tentativas:
  escrever tasks/phase-NN/ESCALATION.md com:
    - erro completo + stack trace
    - número de tentativas
    - hipótese da causa (spec ambígua? dependência quebrada? bug de lógica?)
  NÃO tentar novamente
  aguardar revisão do Tático (Codex) na spec
```

Sem este critério, o MiniMax pode iterar indefinidamente em problemas que estão na spec, não na implementação.

### Orquestração assíncrona

**Produção (GitHub Actions):** cada agente é um workflow separado acionado por push nas pastas de handoff. Repositório público + GitHub Education (Pro plan) = unlimited minutes + 40 jobs concorrentes. Os workflows de implementação são locais (conductor.ps1), não Actions.

**Desenvolvimento local (conductor.ps1):** script PowerShell 7 que sequencia invocações via flags `--no-interactive` dos CLIs e monitora os arquivos de sinalização. Tarefas sem dependência entre si usam `Start-Job` para paralelismo real.

```powershell
# Exemplo: Gemini QA pode rodar em paralelo com docs-maintainer após o Operacional terminar
$jobQA   = Start-Job { gemini run "Execute Playwright tests on /quiz" --model gemini-3-flash }
$jobDocs = Start-Job { copilot chat --no-interactive "Run docs-maintainer skill for phase 11" }
Wait-Job $jobQA, $jobDocs
```

O `conductor.ps1` é entregável da Fase 1, gerado pelo Opus.

---

## PIPELINE DE INGESTÃO E CURADORIA — HIERARQUIA DE REDAÇÃO

Modelo inspirado no funcionamento de uma redação: frequências e responsabilidades distintas por tier,
com estado de publicação progressivo (`raw` → `validated` → `curated`).

O repositório é público → GitHub Actions gratuito e ilimitado para todos os workflows desta seção.
GitHub Education (Pro plan) = 40 jobs concorrentes. Os três workflows do pipeline + deploy rodam sem disputa de recursos.

### Papéis da redação

| Papel | Metáfora | Frequência | Modelo | Fallback |
|-------|----------|-----------|--------|---------|
| **Foca** | Repórter iniciante | 30 min | Qwen3-235B-A22B (NVIDIA NIM — gratuito) | Ministral-3B (OpenRouter — fallback ultrarrápido) |
| **Editor** | Editor de seção | 2 horas | Qwen3-235B-Thinking (OpenRouter — gratuito) | Gemini 2.5 Flash Lite via Vertex AI |
| **Editor-chefe** | Editor executivo | 6 horas | Gemini 2.5 Flash Lite (Vertex AI — Google AI Pro $10/mês) | Kimi-K2.5 (NVIDIA NIM — janela de contexto longa) |

### Responsabilidades por tier

**Foca (`collect.yml` — cron `*/10 * * * *`):**
- Coleta RSS + partidos + institutos de pesquisa
- Deduplicação por `sha256(url)[:16]`
- Triagem de relevância eleitoral: score `relevance_score` (0.0–1.0) via IA
- Extração de candidatos mencionados (`candidates_mentioned[]`)
- Deduplicação semântica contra os últimos 500 artigos (embedding cosine similarity)
- Flag `needs_editor_review: true` se `relevance_score < 0.7` ou artigo ambíguo
- **Não gera resumos.** Publica com `status: "raw"` imediatamente
- Output: `data/raw/YYYY-MM-DD-HH-MM.json` → commit → aciona Editor via push event

**Editor (`validate.yml` — acionado por push em `data/raw/` + cron `*/30 * * * *`):**
- Processa todos os artigos com `status: "raw"` que ainda não passaram por validação
- Gera `summaries: { "pt-BR": ..., "en-US": ... }` bilíngues
- Calcula `sentiment_score` com chain-of-thought (modelo thinking)
- Valida e enriquece `topics[]` definidos pelo Foca
- Detecta duplicatas narrativas: mesmo fato, múltiplas fontes → agrupa em `narrative_cluster_id`
- Calcula `confidence_score` final do artigo
- Promove artigos confiantes para `status: "validated"`
- Artigos com `confidence_score < 0.6` ficam em `status: "raw"` com `editor_note`
- Output: atualiza `data/articles.json` (apenas `status: "validated"`) → aciona deploy

**Editor-chefe (`curate.yml` — cron `0 * * * *` + skip-if-recent (equivalente a ~90 min — ver nota abaixo)):**
- Ingere todos os artigos `validated` das últimas 24h + corpus da semana
- Detecta tendências narrativas: temas emergentes, candidatos ganhando/perdendo cobertura
- Calcula `prominence_score` para hierarquizar o feed (não só cronológico)
- Gera `data/weekly_briefing.json`: resumo semanal, tendências, destaques por candidato
- Audita qualidade do Editor: usa `edit_history` de cada artigo para identificar padrões de revisão (quais campos o Editor mais altera, quais artigos o Foca classifica mal) — feedback loop para calibração dos prompts
- Executa `extract_quiz_positions.py`: atualiza `data/quiz.json` com posições mais recentes
- Promove artigos estratégicos para `status: "curated"` com `prominence_score > 0.8`
- Output: `data/curated_feed.json`, `data/weekly_briefing.json` → commit → aciona deploy

### Schema do artigo com estado de publicação

```json
{
  "id": "sha256[:16]",
  "url": "...",
  "title": "...",
  "source": "...",
  "published_at": "ISO8601",
  "collected_at": "ISO8601",
  "status": "raw | validated | curated",
  "relevance_score": 0.87,
  "candidates_mentioned": ["lula", "tarcisio"],
  "topics": ["economia", "segurança"],
  "narrative_cluster_id": "cluster_abc123 | null",
  "summaries": {
    "pt-BR": "...",
    "en-US": "..."
  },
  "sentiment_score": 0.34,
  "confidence_score": 0.91,
  "prominence_score": 0.72,
  "needs_editor_review": false,
  "editor_note": "...",
  "edit_history": [
    { "tier": "foca",  "at": "ISO8601", "provider": "qwen3-235b-a22b",     "action": "collected" },
    { "tier": "editor", "at": "ISO8601", "provider": "qwen3-235b-thinking", "action": "validated", "changes": ["summary_pt", "sentiment_score"] }
  ],
  "ai_provider_foca": "qwen3-235b-a22b",
  "ai_provider_editor": "qwen3-235b-thinking",
  "disclaimer_pt": "Análise algorítmica. Não representa pesquisa de opinião.",
  "disclaimer_en": "Algorithmic analysis. Does not represent polling data."
}
```

### Decisão de UI obrigatória — o que o usuário vê por status

O Opus deve tomar esta decisão na Fase 1 e documentar no PLAN.md:

**Opção A (recomendada) — Publicação em estágios:**
- `raw`: aparece no feed com título + fonte + "análise em andamento" (sem resumo de IA)
- `validated`: resumo completo + tags + sentiment badge + "Como funciona? ⓘ"
- `curated`: tudo acima + badge "Destaque da Redação" + posição no feed elevada pelo `prominence_score`

Vantagem: frescor máximo (usuário vê manchetes em até 30 min), qualidade cresce progressivamente.

**Opção B — Publicar só o validado:**
- Apenas `status: "validated"` entra no `articles.json` público
- Latência de publicação: até 2 horas (ciclo do Editor)
- Qualidade consistente, frescor reduzido

### Workflows GitHub Actions (4 workflows totais)

| Workflow | Trigger | Duração estimada | Responsável |
|---------|---------|-----------------|-------------|
| `collect.yml` | cron `*/10 * * * *` | ~3 min | Foca (Qwen3-235B-A22B) |
| `validate.yml` | push `data/raw/**` + cron `*/30 * * * *` | ~5 min | Editor (Qwen3-235B-Thinking) |
| `curate.yml` | cron `0 * * * *` (+ skip logic ≈90 min) | ~15 min | Editor-chefe (Gemini 2.5 Flash Lite via Vertex AI) |
| `deploy.yml` | push `data/articles.json` ou `data/curated_feed.json` | ~4 min | vite build + gh-pages |
| `watchdog.yml` | cron `0 6 * * *` | ~5 min | Gemini 3 Flash: analisa logs 7 dias, gera `data/pipeline_health.json` |

Frequências resultantes: Foca 144x/dia (a cada 10 min), Editor 48x/dia (a cada 30 min), Editor-chefe ~16x/dia (a cada ~90 min via skip logic), Watchdog 1x/dia.
Concorrência máxima simultânea: até 3 workflows sobrepostos nos intervalos coincidentes (10+30+90 min = pico a cada 90 min).
Limite GitHub Education (Pro, repo público): 40 jobs concorrentes, minutos ilimitados. Zero risco de disputa.

### Nota técnica — cron de 90 minutos

O cron padrão (GitHub Actions incluído) não suporta intervalos não-múltiplos de 60 minutos como `*/90`.
A solução é acionar o `curate.yml` a cada hora (`0 * * * *`) e adicionar skip logic no início do script:

```python
# scripts/curate.py — início do script
import json, time
from pathlib import Path

LAST_RUN_FILE = Path("data/.curate_last_run")
MIN_INTERVAL_SECONDS = 90 * 60  # 90 minutos

if LAST_RUN_FILE.exists():
    elapsed = time.time() - float(LAST_RUN_FILE.read_text())
    if elapsed < MIN_INTERVAL_SECONDS:
        print(f"Skipping: only {elapsed/60:.1f} min since last run (minimum: 90 min)")
        raise SystemExit(0)

LAST_RUN_FILE.write_text(str(time.time()))
# ... resto do script de curadoria
```

O arquivo `data/.curate_last_run` deve ser commitado pelo `curate.yml` junto com os outputs.
Isso garante que o Editor-chefe rode ~16x/dia com intervalo mínimo garantido entre execuções.

### Protocolo de falha entre tiers

- **Foca falha:** artigos não coletados neste ciclo. Próximo ciclo retenta. Sem impacto no usuário (últimos artigos validados continuam no feed).
- **Editor falha:** artigos ficam em `status: "raw"`. Feed não atualiza com novos resumos. Próximo ciclo do Editor retoma do ponto onde parou (idempotente).
- **Editor-chefe falha:** quiz.json não atualizado, briefing semanal não gerado. `curate.yml` tem `continue-on-error: true` para não bloquear o deploy.
- **Qualquer falha:** logada em `data/pipeline_errors.json` com timestamp, tier, provider, e mensagem. O MethodologyBadge nos dashboards pode exibir "Último processamento: X horas atrás" com base neste log.

---

## REGRAS OBRIGATÓRIAS

- `id` = `sha256(url.encode())[:16]` — deduplicação idempotente em todos os scripts
- `summaries` sempre com `pt-BR` e `en-US` antes de commitar artigos processados
- Scripts de coleta são idempotentes — rodar 2× sem duplicar dados
- `build_data.py` mantém exatamente os 500 artigos mais recentes
- Erros de providers de IA são logados mas **nunca interrompem** o pipeline
- Frontend funciona com dados ausentes: loading, empty e error state em todos os componentes
- Steps opcionais no Actions usam `|| echo "... failed, continuing"`
- O quiz **nunca exibe** `candidate_slug` ou `source_*` durante as perguntas — apenas no resultado
- O `sentiment.json` sempre inclui `disclaimer_pt` e `disclaimer_en`
- **docs-maintainer skill** após cada fase — sem exceção

---

## REFERÊNCIAS

- Projeto de inspiração: https://github.com/ktoetotam/NewFeeds
- Referência de quiz: https://oiceberg.com.br/calculadora-de-afinidade-politica/
- NVIDIA NIM: https://build.nvidia.com
- OpenRouter free models: https://openrouter.ai/models?q=free
- Ollama Cloud: https://docs.ollama.com/cloud
- Vertex AI + OpenAI compat: https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/call-vertex-using-openai-library
- MiMo-V2-Flash: https://api.xiaomimimo.com/v1
- react-i18next: https://react.i18next.com
- vite-plugin-ssg: https://github.com/antfu/vite-ssg
- Schema.org: https://schema.org/Person, https://schema.org/FAQPage, https://schema.org/Quiz
- robots.txt para crawlers de IA: https://darkvisitors.com
- TSE Eleições 2026: https://www.tse.jus.br (1.º turno: 4 out 2026)
