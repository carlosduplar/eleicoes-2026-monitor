# ADR 003 — Estrategia de Internacionalizacao (i18n)

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)

## Contexto

O portal deve ser bilingue (pt-BR obrigatorio + en-US) para maximizar alcance academico e SEO internacional. Strings de UI, resumos de artigos, e conteudo editorial precisam de traducao.

## Decisao

Usar `react-i18next` com namespaces por dominio e idioma selecionavel via toggle `PT | EN`.

## Estrutura de Locales

```
site/src/locales/
  pt-BR/
    common.json       # nav, footer, labels gerais, CountdownTimer
    candidates.json   # nomes, partidos, cargos
    quiz.json         # perguntas, opcoes, labels de resultado
    methodology.json  # pagina de metodologia completa
    case-study.json   # conteudo da pagina de caso de uso
  en-US/
    common.json
    candidates.json
    quiz.json
    methodology.json
    case-study.json
```

## Regras

1. **pt-BR e default e fallback.** Se chave ausente em en-US, exibe pt-BR.
2. **Toggle `PT | EN`** no header — `PT` ativo e sublinhado por padrao. Persiste em `localStorage`.
3. **Artigos tem `summaries.pt-BR` e `summaries.en-US`** — gerados pelo pipeline de IA. Se en-US ausente, exibe pt-BR.
4. **Slugs de candidato sao invariantes** entre idiomas (`/candidato/lula` e `/candidate/lula` resolvem para a mesma pagina).
5. **URLs nao mudam com idioma.** Conteudo e trocado client-side via react-i18next. Isso simplifica cache e SEO (uma URL por pagina, `hreflang` tags apontam para a mesma URL com idioma diferente).
6. **JSON-LD e gerado no idioma ativo** (`@language: "pt-BR"` ou `"en-US"`).
7. **RSS feeds sao separados:** `/feed.xml` (pt-BR) e `/feed-en.xml` (en-US).

## Detalhes Tecnicos

### Inicializacao (i18n.js)
```javascript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

i18n.use(initReactI18next).init({
  lng: localStorage.getItem('lang') || 'pt-BR',
  fallbackLng: 'pt-BR',
  ns: ['common', 'candidates', 'quiz', 'methodology', 'case-study'],
  defaultNS: 'common',
  interpolation: { escapeValue: false },
});
```

### LanguageSwitcher.jsx
Renderiza `PT | EN` com o idioma ativo sublinhado em ouro (`#B8961E`).
Persiste selecao em `localStorage('lang')`.

### Disclaimer bilingue
`sentiment.json` e `quiz.json` incluem campos `disclaimer_pt` e `disclaimer_en`.
O frontend seleciona o campo correto via `i18n.language`.

## Consequencias

- Todas as strings de UI devem usar `t('key')` — nenhum texto hardcoded em JSX
- Pipeline de IA gera ambos idiomas por artigo; se en-US falhar, campo fica vazio (fallback para pt-BR no frontend)
- Adicionar novo idioma no futuro: criar pasta `locales/xx-XX/`, copiar estrutura, traduzir
