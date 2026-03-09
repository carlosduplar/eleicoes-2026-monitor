# ADR 000 — Wireframes e Sistema de Design

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)

## Contexto

O portal precisa de wireframes de referencia para 11 telas (9 desktop + 2 mobile) antes de implementar componentes React. Wireframes iniciais foram gerados no Google Stitch, depois auditados e recriados como HTML standalone para maior fidelidade ao sistema de design e correcao de divergencias sistematicas (marca, navegacao, fundos escuros, componentes ausentes).

## Decisao

Wireframes finais sao HTML standalone armazenados em `docs/wireframes/` com nomenclatura `WF-NN-descricao.html`. Cada arquivo e auto-contido (CSS inline, sem dependencias externas). Um `index.html` serve como galeria navegavel.

## Arquivos em `docs/wireframes/`

| Arquivo | WF | Tela | Rota | Viewport |
|---------|-----|------|------|----------|
| `index.html` | — | Galeria de wireframes | — | — |
| `WF-01-feed-desktop.html` | WF-01 | Feed Desktop | `/` | 1280px |
| `WF-02-03-sentiment-dashboard.html` | WF-02/03 | Sentiment Dashboard | `/sentimento` | 1280px |
| `WF-04-poll-tracker.html` | WF-04 | Poll Tracker | `/pesquisas` | 1280px |
| `WF-05-quiz-question-desktop.html` | WF-05 | Quiz Pergunta Desktop | `/quiz` | 1280px |
| `WF-06-quiz-result-desktop.html` | WF-06 | Quiz Resultado Desktop | `/quiz/resultado` | 1280px |
| `WF-07-candidate-profile-desktop.html` | WF-07 | Perfil de Candidato | `/candidato/[slug]` | 1280px |
| `WF-08-candidate-comparison.html` | WF-08 | Comparacao de Candidatos | `/comparar/[a]-vs-[b]` | 1280px |
| `WF-09-methodology.html` | WF-09 | Metodologia | `/metodologia` | 1280px |
| `WF-10-case-study.html` | WF-10 | Caso de Uso | `/sobre/caso-de-uso` | 1280px |
| `WF-11-mobile-feed.html` | WF-11 | Mobile Feed | `/` | 390px |
| `WF-12-mobile-quiz.html` | WF-12 | Mobile Quiz | `/quiz` | 390px |

## Mapeamento WF -> Componente React

| WF | Componentes React | Rota |
|----|------------------|------|
| WF-01 | `Home.jsx`, `NewsFeed.jsx`, `SourceFilter.jsx` | `/` |
| WF-02/03 | `SentimentDashboard.jsx` (views A e B) | `/sentimento` |
| WF-04 | `PollTracker.jsx`, `PollsPage.jsx` | `/pesquisas` |
| WF-05 | `QuizEngine.jsx`, `QuizPage.jsx` | `/quiz` (pergunta) |
| WF-06 | `QuizResultCard.jsx`, `QuizResult.jsx` | `/quiz/resultado?r=abc123` |
| WF-07 | `CandidatePage.jsx` | `/candidato/[slug]` |
| WF-08 | `ComparisonPage.jsx` | `/comparar/[a]-vs-[b]` |
| WF-09 | `MethodologyPage.jsx` | `/metodologia` |
| WF-10 | `CaseStudyPage.jsx` | `/sobre/caso-de-uso` |
| WF-11 | `Home.jsx` (mobile 390px) | `/` |
| WF-12 | `QuizEngine.jsx`, `QuizResultCard.jsx` (mobile) | `/quiz` |

## Referencia Stitch (historica)

As 8 telas originais foram geradas no Google Stitch (projeto ID `14035093273581397349`) e harmonizadas em sessao dedicada. Os wireframes finais substituem integralmente os artefatos Stitch. Os screen IDs Stitch estao documentados abaixo apenas para rastreabilidade:

| WF | Screen ID original | Screen ID harmonizado |
|----|-------------------|-----------------------|
| WF-01 | `d5f9a15722c54e8ab2479fea2f28b0b9` | `7a21e460ccc9473f83576bdce8e704a9` |
| WF-02/03 | `c202547a0fa6495ebebfcbac111343a9` | `c772afd493d747aa800c176312cd74c0` |
| WF-04 | `4712f18a8436431c9b02e9cc2d195adc` | `8836dfc51e94462781f9690791f90515` |
| WF-05 | — | `f5e28edfb7d144d588e078f01895961e` |
| WF-06 | — | `58223772daec4281af3107441bae9ca3` |
| WF-07 | — | `8602438c1f05428e83baebaa8337f38c` |
| WF-08 | `7765008b785c4b75a4457261ad9dbd83` | `afead3171fbf41bab4b2e33b6c6d8b6d` |
| WF-09 | `52971d8e38d54d10af02b711f48bee58` | `d61e12d4eae44159aa79593dffdf77b8` |
| WF-10 | `1133f1f3e52e450eae59d6c081332d5d` | `1894777f7a4a4d91acda6cd2a247338f` |
| WF-11 | `a61a29f7ac6049ed928365dcbc78929b` | `f89ad5266c5f439eb3ffb668debf4ee8` |
| WF-12 | `78825e70badc4832a00e213e7615e016` | `6d8304a831d644a7bdbf7e5975f828dc` |

## CSS Custom Properties (confirmadas nos wireframes)

```css
:root {
  --navy:    #1A2E4A;
  --gold:    #B8961E;
  --bg:      #F5F7FA;
  --surface: #FFFFFF;
  --muted:   #EDF2F7;
  --text:    #1A202C;
  --text2:   #4A5568;
  --border:  #E2E8F0;
  --raw:     #F6AD55;
  --valid:   #48BB78;
}
```

## Paleta de Design Tokens (para `site/src/`)

```css
:root {
  --brand-navy:     #1A2E4A;
  --brand-gold:     #B8961E;
  --brand-bg:       #F5F7FA;
  --brand-surface:  #FFFFFF;
  --brand-muted:    #EDF2F7;
  --text-primary:   #1A202C;
  --text-secondary: #4A5568;
  --status-raw:     #F6AD55;
  --status-valid:   #48BB78;
  --status-curated: #B8961E;
}
```

## Cores dos Pre-candidatos

| Candidato | Hex | Partido | Notas |
|-----------|-----|---------|-------|
| Lula | `#CC0000` | PT | |
| Flavio Bolsonaro | `#002776` | PL | |
| Tarcisio de Freitas | `#1A3A6B` | Republicanos | Se conflito visual com Flavio no heatmap, usar `#2B5EA7` |
| Ronaldo Caiado | `#FF8200` | Uniao Brasil | |
| Romeu Zema | `#FF6600` | Novo | |
| Ratinho Jr | `#0066CC` | PSD | |
| Eduardo Leite | `#4488CC` | PSD | |
| Aldo Rebelo | `#5C6BC0` | DC | |
| Renan Santos | `#26A69A` | Missao | |

## Tipografia

| Elemento | Fonte | Peso | Tamanho |
|----------|-------|------|---------|
| H1 | Georgia, serif | 700 | 36-40px |
| H2 | Inter | 600 | 24px |
| H3 card title | Inter | 600 | 18px |
| Body | Inter | 400 | 15px |
| Metadata | Inter | 400 | 12px |
| Badge/label | Inter uppercase | 500 | 11px |

## Navegacao

### Desktop (todas as telas)
```
[BR Portal Eleicoes BR 2026]  Noticias  Sentimento  Pesquisas  Candidatos  Quiz  Metodologia  [PT | EN]
```
- Item ativo: peso 600, underline ouro 2px (`#B8961E`), cor `#1A2E4A`
- Sem botao Login
- Fundo branco com `border-bottom: 1px solid #E2E8F0`

### Mobile bottom nav (WF-11, WF-12)
```
Inicio | Sentimento | Pesquisas | Quiz | Mais
```

## CountdownTimer

Faixa full-width abaixo do nav em todas as telas desktop:
- Fundo `#1A2E4A`, texto branco, Inter 400 13px
- Texto: "X dias para o 1.o turno - 4 de outubro de 2026"
- Data alvo: `2026-10-04`

## MethodologyBadge

Padrao unico em todas as telas com dados:
```
i Analise algoritmica. Nao representa pesquisa eleitoral. -> /metodologia
```
Inter 400, 11px, cor `#4A5568`, clicavel.

## Consequencias

- Wireframes HTML standalone sao a fonte de verdade visual para implementacao React
- Componentes React devem replicar a estrutura HTML/CSS dos wireframes, adaptando para JSX + react-i18next
- Os wireframes usam CSS custom properties consistentes com os design tokens do projeto
- `docs/wireframes/index.html` pode ser servido localmente para revisao visual rapida
