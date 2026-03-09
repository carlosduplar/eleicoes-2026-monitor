# Phase 14 — Party + Social Collection

## Objective

Implement `scripts/collect_parties.py` (BeautifulSoup scraping of 8 party sites) and `scripts/collect_social.py` (optional Twitter/YouTube collection). Integrate both into the Foca tier (`collect.yml`). Party articles become first-class citizens in `articles.json` alongside RSS articles.

## Input Context

- `docs/prompt-eleicoes2026-v5.md` lines 300-311 — `PARTY_SOURCES` list (8 parties)
- `docs/prompt-eleicoes2026-v5.md` lines 710-757 — `collect.yml` pipeline steps (social calls are optional with `|| echo`)
- `data/sources.json` — Party sources metadata (from Phase 03)
- `data/articles.json` — Target file to append party articles (from Phase 03)
- `scripts/collect_rss.py` — Reference implementation for article schema and dedup pattern (from Phase 03)
- `scripts/ai_client.py` — For relevance scoring (from Phase 02)

## Deliverables

### 1. `scripts/collect_parties.py`

BeautifulSoup-based scraper for 8 party websites.

**Party sources (from `PARTY_SOURCES`):**
| Party | URL | Candidate slugs |
|-------|-----|-----------------|
| PT | `https://pt.org.br/noticias/` | `["lula"]` |
| PL | `https://pl.org.br/noticias/` | `["flavio-bolsonaro"]` |
| Republicanos | `https://republicanos10.org.br/noticias/` | `["tarcisio"]` |
| PSD | `https://psd.org.br/noticias/` | `["ratinho-jr","eduardo-leite"]` |
| Novo | `https://novo.org.br/noticias/` | `["zema"]` |
| União Brasil | `https://uniaobrasil.org.br/noticias/` | `["caiado"]` |
| DC | `https://dc.org.br/noticias/` | `["aldo-rebelo"]` |
| Missão | `https://missao.org.br/noticias/` | `["renan-santos"]` |

**Key behaviors:**
- Read only `active: true` party sources from `data/sources.json`
- For each party site, use `requests` + `BeautifulSoup` to extract news article links and titles
- Extraction strategy: look for `<article>`, `<a>` tags with news patterns, `<h2>`/`<h3>` inside list items
- Generate article ID: `sha256(url.encode())[:16]` (same as RSS collector)
- Pre-populate `candidates_mentioned` from the party's `candidate_slugs`
- Set `source_category: "party"`, `status: "raw"`
- Skip articles already in `data/articles.json` (dedup by ID)
- Request timeout: 20 seconds per site
- Respect `robots.txt` — check `robots_txt_url` from sources.json if present
- Log failures to `data/pipeline_errors.json`, continue to next party
- Print summary: "Parties: X new articles from Y sources (Z errors)"
- **Idempotent**

**HTML extraction fallback ladder:**
1. JSON-LD `NewsArticle` in `<script type="application/ld+json">`
2. Open Graph `<meta property="og:title">` + `og:url`
3. First `<h1>` or `<h2>` + canonical `<link>` or current URL
4. Skip if none of the above yield a valid URL+title pair

### 2. `scripts/collect_social.py`

Optional Twitter/YouTube collector. Called with `|| echo "social failed, continuing"` in pipeline — failures are expected and acceptable.

**Twitter (tweepy):**
- If `TWITTER_BEARER_TOKEN` is set, search recent tweets mentioning each candidate name + "2026"
- Use Twitter API v2 `search_recent_tweets` endpoint
- Extract: tweet URL, text, author, timestamp
- Convert tweet to article format: `source: "Twitter"`, `source_category: "social"`, `candidates_mentioned` inferred from tweet content
- Rate limit aware: use `tweepy.Client` with automatic rate limiting
- Skip if bearer token not configured

**YouTube (YouTube Data API v3):**
- If `YOUTUBE_API_KEY` is set, search for videos mentioning candidates + "eleições 2026"
- Use `youtube.search().list(q=..., type="video", order="date", maxResults=10)`
- Extract: video URL (`https://youtu.be/<id>`), title, channel, published_at
- Convert to article format: `source: "YouTube"`, `source_category: "social"`

**Both social sources:** same dedup logic as RSS/party collectors.

### 3. Update `data/sources.json`

The Party sources are already seeded (Phase 03). Verify they have the full structure needed for `collect_parties.py`:
```json
{
  "parties": [
    {
      "name": "PT",
      "url": "https://pt.org.br/noticias/",
      "candidate_slugs": ["lula"],
      "active": true,
      "category": "party"
    }
  ]
}
```

Add `"social"` array to `data/sources.json`:
```json
{
  "social": [
    {"name": "Twitter", "type": "twitter", "active": true},
    {"name": "YouTube", "type": "youtube", "active": true}
  ]
}
```

### 4. Unit tests — `scripts/test_collect_parties.py`

- `test_party_article_id_is_sha256_prefix` — ID matches `sha256(url)[:16]`
- `test_party_article_has_candidate_slugs` — Article from PT site has `["lula"]` in `candidates_mentioned`
- `test_party_article_category_is_party` — `source_category == "party"`
- `test_dedup_skips_existing` — Article already in data is skipped
- `test_site_failure_does_not_crash` — Bad URL skips gracefully
- `test_idempotent_double_run` — Running twice produces same article count

### 5. Update `.github/workflows/collect.yml`

Replace the stub `|| echo "parties failed, continuing"` with the real implementation. Keep the soft-failure guard — party sites may be unreliable:
```yaml
- run: |
    python scripts/collect_rss.py
    python scripts/collect_parties.py  || echo "[warn] collect_parties failed"
    python scripts/collect_polls.py    || echo "[warn] collect_polls failed"
    python scripts/collect_social.py   || echo "[warn] collect_social failed"
```

## Constraints

- `requests` and `beautifulsoup4` are already in `requirements.txt` (Phase 01)
- `tweepy` must be added to `requirements.txt` if not already present
- Each scraper must complete within 20 seconds per site; use `requests.get(url, timeout=20)`
- Social collection is optional and must never block the pipeline — if both `TWITTER_BEARER_TOKEN` and `YOUTUBE_API_KEY` are unset, `collect_social.py` exits with code 0 and prints a warning
- Party articles enter the same validation pipeline as RSS articles (Phase 06's `summarize.py` processes them)

## Acceptance Criteria

- [ ] `python scripts/collect_parties.py` runs without crashing
- [ ] Party articles appear in `data/articles.json` with `source_category: "party"`
- [ ] Party articles have `candidates_mentioned` pre-populated from party's candidate list
- [ ] Running `collect_parties.py` twice produces no duplicates
- [ ] `python scripts/collect_social.py` exits cleanly even when API keys are absent
- [ ] `data/sources.json` includes all 8 party sources and social section
- [ ] All unit tests pass: `python -m pytest scripts/test_collect_parties.py -v`
- [ ] `collect.yml` runs end-to-end in GitHub Actions with party collection enabled

## Commit & Push

After all deliverables are verified:

```
git add scripts/collect_parties.py scripts/collect_social.py scripts/test_collect_parties.py data/sources.json requirements.txt .github/workflows/collect.yml
git commit -m "feat(phase-14): Party and social collection — BeautifulSoup party scraper + optional Twitter/YouTube

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-14-arch.DONE`.
