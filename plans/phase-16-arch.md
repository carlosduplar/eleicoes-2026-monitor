# Phase 16 — QA Final

## Objective

Execute the full quality assurance pass across the entire project: unit + integration tests, security review, SEO audit, code review, accessibility audit, and final documentation. Finalize `README.md` with badges, screenshots, and architecture diagram. Complete `CHANGELOG.md`. This is the gate before production release.

## Input Context

- All code in `scripts/`, `site/src/`, `.github/workflows/`
- `docs/adr/` — All ADRs (000–006)
- `docs/case-study/` — Living documentation
- `PLAN.md` — Full project history
- `CHANGELOG.md` — Partial changelog from prior phases
- `README.md` — Project overview (from Phase 01)
- `qa/` directory — Output location for QA reports

## Deliverables

### 1. Test suite — `test-writer` skill

Invoke the `test-writer` skill to write and run:

**Python unit tests** (new tests not covered in prior phases):
- `scripts/test_ai_client.py` — verify fallback chain logic (mocked providers), usage tracking, error handling
- `scripts/test_build_data.py` — dedup, 500-limit, sort order
- `scripts/test_curate.py` — 90-min skip logic
- `scripts/test_watchdog.py` — health JSON structure
- `scripts/test_extract_quiz_positions.py` — divergence scoring, topic selection, cluster coverage

**Frontend integration tests** (Playwright):
- `qa/tests/test_home.spec.js` — Feed renders, language toggle, countdown timer
- `qa/tests/test_sentiment.spec.js` — Dashboard heatmap, toggle Por Tema/Por Fonte
- `qa/tests/test_polls.spec.js` — Chart renders, institute filter
- `qa/tests/test_quiz.spec.js` — Full quiz flow: answer all questions, result shows, share button
- `qa/tests/test_quiz_neutrality.spec.js` — Assert no candidate slug or source text visible during question phase
- `qa/tests/test_candidate.spec.js` — `/candidato/lula` renders with JSON-LD
- `qa/tests/test_comparison.spec.js` — `/comparar/lula-vs-tarcisio` renders
- `qa/tests/test_methodology.spec.js` — All 5 sections present, language toggle
- `qa/tests/test_rss.spec.js` — `feed.xml` and `feed-en.xml` are valid XML
- `qa/tests/test_mobile.spec.js` — 390px: BottomNav visible, desktop Nav hidden, quiz immersive

All Playwright tests must use the built static site (`npm run build && npm run preview`) as the test target — not the dev server.

**Pass criteria:** all Python pytest + Playwright tests must pass with zero failures.

### 2. Security review — `security-threat-modeler` skill

Invoke the `security-threat-modeler` skill. Target areas:

| Risk | Location | Expected finding |
|------|----------|-----------------|
| Secret exposure | `.github/workflows/` | All secrets via `${{ secrets.* }}` — verify no hardcoded keys |
| Injection | `scripts/collect_parties.py` | BeautifulSoup input is sanitized before writing to JSON |
| Injection | `scripts/summarize.py` | AI prompt injection: user-controlled article content in prompts |
| XSS | `CaseStudyPage.jsx` | Markdown rendered as HTML — ensure no `dangerouslySetInnerHTML` without sanitization |
| Open redirect | All `<a target="_blank">` | All external links have `rel="noopener noreferrer"` |
| Data integrity | `data/*.json` | Ensure no PII is collected (no user data, no session tracking) |

**Output:** `qa/phase-16-security-report.md` with findings and mitigations.

### 3. SEO audit — `seo-audit` skill

Invoke the `seo-audit` skill on the deployed GitHub Pages URL. Check:

- All `<title>` tags are unique per page
- All pages have `<meta name="description">` with relevant content
- JSON-LD structured data validates at `https://validator.schema.org/`
- `sitemap.xml` is reachable and valid
- `robots.txt` is well-formed
- Open Graph tags present on all sharable pages (quiz result, candidate pages)
- No broken internal links in `sitemap.xml`

**Output:** `qa/phase-16-seo-report.md`.

### 4. Code review — `tech-lead-reviewer` skill

Invoke the `tech-lead-reviewer` skill. Scope: all changes since Phase 01. Key areas:

- Pipeline idempotency (all scripts safe to run twice)
- Error handling (no bare `except:` without logging)
- React component prop validation (missing required props)
- Unused imports or dead code
- Race conditions in GitHub Actions (concurrent writes to `data/*.json`)
- `narrative_cluster_id` logic correctness

**Output:** `qa/phase-16-code-review.md` with findings. Fix all HIGH severity issues before pushing.

### 5. Accessibility audit — `web-design-guidelines` skill

Invoke the `web-design-guidelines` skill on all pages. Check:

- All images have `alt` text (candidate photos when added)
- Color contrast ratio ≥ 4.5:1 for body text (WCAG AA)
- Focus indicators visible on all interactive elements
- `<button>` elements have accessible labels
- `<nav>` has `aria-label`
- `BottomNav` items have `aria-label` matching their text label
- Heatmap cells have `aria-label` with candidate + topic + score for screen readers

**Output:** `qa/phase-16-accessibility-report.md`.

### 6. Final `README.md`

Update `README.md` to final state:

**Sections:**
1. **Badges** (top): GitHub Actions status for collect/deploy/watchdog, GitHub Pages live URL
2. **Screenshot:** full-page screenshot of the live homepage (light mode)
3. **What is this?** — 2-paragraph bilingual description
4. **Live site:** `https://eleicoes2026.com.br` (or GH Pages URL)
5. **Architecture diagram:** ASCII or Mermaid flowchart of the pipeline:
   ```
   RSS/Parties/Polls → collect.yml (10min) → articles.json (raw)
                     → validate.yml (30min) → articles.json (validated)
                     → curate.yml (~90min) → curated_feed.json + quiz.json
                     → deploy.yml → GitHub Pages
   ```
6. **Running locally:** `npm install && npm run dev` (frontend); `pip install -r requirements.txt && python scripts/collect_rss.py` (pipeline)
7. **Secrets:** table of required GitHub secrets
8. **Candidate list:** table of 9 candidates with status
9. **ADRs:** links to all 7 ADRs
10. **Contributing:** link to open a GitHub issue
11. **License:** MIT

### 7. Final `CHANGELOG.md`

Ensure `CHANGELOG.md` has an entry for every phase (01–16) following [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format. Add the `[1.0.0]` release entry with date.

### 8. `docs/case-study/` final update

Invoke `docs-maintainer` skill to do a final pass on both case study documents, incorporating all lessons learned, final architecture decisions, and phase outcomes.

## Constraints

- All HIGH and CRITICAL findings from security/code review must be fixed before the push
- MEDIUM findings should be fixed; LOW findings may be documented as known issues in `qa/`
- Playwright tests run against the built static site, not dev server — this catches SSG-specific issues
- `README.md` must be accurate and useful to a developer who discovers the repo cold

## Acceptance Criteria

- [ ] All Python unit tests pass: `python -m pytest scripts/ -v --tb=short`
- [ ] All Playwright tests pass against built site: `npx playwright test`
- [ ] `qa/phase-16-security-report.md` exists; no CRITICAL findings unresolved
- [ ] `qa/phase-16-seo-report.md` exists; all pages have unique titles and meta descriptions
- [ ] `qa/phase-16-code-review.md` exists; all HIGH findings fixed
- [ ] `qa/phase-16-accessibility-report.md` exists; color contrast WCAG AA compliant
- [ ] `README.md` has badges, screenshot, architecture diagram, and local setup instructions
- [ ] `CHANGELOG.md` has complete entries for all 16 phases
- [ ] `npm run build` produces valid `dist/` with no console errors
- [ ] GitHub Pages site is live and all routes resolve without 404

## Commit & Push

Fix all HIGH/CRITICAL issues from QA reports first, then:

```
git add qa/ README.md CHANGELOG.md docs/case-study/ site/ scripts/
git commit -m "feat(phase-16): QA final — tests, security review, SEO audit, accessibility + final docs

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-16-arch.DONE`.
