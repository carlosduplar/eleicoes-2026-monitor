# ADR 001 — Hospedagem: GitHub Pages + Cloudflare

**Status:** Aceito  
**Data:** 2026-03-06  
**Decisor:** Opus 4.6 (Arquiteto)

## Contexto

O portal precisa de hospedagem estatica gratuita com CDN, HTTPS automatico, e compatibilidade com SSG (Static Site Generation). O projeto e academico com zero orcamento de infraestrutura.

## Opcoes Consideradas

1. **GitHub Pages + Cloudflare** — site estatico, Actions para CI/CD, CDN gratuita
2. **Vercel** — bom para Next.js, mas lock-in e limites no free tier para cron jobs
3. **Netlify** — similar a Vercel, limites de build minutes
4. **Firebase Hosting** — requer setup GCP, overhead para site estatico puro

## Decisao

GitHub Pages + Cloudflare Free.

## Justificativa

- **Custo zero:** GitHub Pages gratuito para repos publicos. Cloudflare Free sem limites de bandwidth.
- **CI/CD nativo:** GitHub Actions cron (10/30/90 min) integrado sem servico externo.
- **GitHub Education:** Pro plan = Actions ilimitados para repos publicos, 40 jobs concorrentes.
- **SSG compativel:** `vite-plugin-ssg` pre-renderiza todas as paginas; deploy e um `cp dist/ gh-pages`.
- **Custom domain:** TBD via Cloudflare DNS apontando para GitHub Pages.
- **Cache HTTP:** Cloudflare cache 1800s com `stale-while-revalidate: 300` — absorve picos virais.
- **Transparencia:** repo publico = codigo-fonte auditavel, pipeline visivel, credibilidade editorial.

## Detalhes Tecnicos

### Deploy workflow (`deploy.yml`)
- Trigger: push em `main` com paths `site/**`, `data/**`, `docs/case-study/**`
- Build: `npm ci && npm run build` no diretorio `site/`
- Deploy: `actions/deploy-pages@v4` para GitHub Pages environment

### Cloudflare headers (`site/public/_headers`)
```
/*
  Cache-Control: public, max-age=1800, stale-while-revalidate=300
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY

/data/*.json
  Cache-Control: public, max-age=1800, stale-while-revalidate=300
  Access-Control-Allow-Origin: *

/feed*.xml
  Cache-Control: public, max-age=1800
  Content-Type: application/rss+xml; charset=utf-8
```

### DNS
- CNAME: TBD custom domain -> `carlosduplar.github.io`
- Cloudflare proxy: ON (orange cloud)
- SSL: Full (strict)

## Consequencias

- Site e puramente estatico — sem server-side rendering, sem API routes
- Dados atualizados via GitHub Actions commit em `data/*.json`; deploy automatico no push
- Latencia de atualizacao: ~4 min (build SSG + deploy) apos commit de dados
- Se Cloudflare ficar indisponivel, GitHub Pages serve direto (sem cache, mas funcional)
