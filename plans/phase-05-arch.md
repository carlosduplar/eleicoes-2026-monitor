# Phase 05 — CI/CD

## Objective

Set up the full GitHub Actions pipeline: Foca (collect every 10 min), Editor (validate every 30 min), Editor-chefe (curate every ~90 min), deploy to GitHub Pages on push, and daily watchdog health check. The pipeline must be triggerable via `workflow_dispatch` for manual testing before automation begins.

## Input Context

- `docs/prompt-eleicoes2026-v5.md` lines 710-822 — Workflow YAML definitions
- `docs/prompt-eleicoes2026-v5.md` lines 1089-1236 — Pipeline hierarchy, tier responsibilities, skip logic
- `docs/agent-protocol.md` — Tier descriptions (Foca, Editor, Editor-chefe, Watchdog)
- `scripts/collect_rss.py` — Available from Phase 03
- `scripts/build_data.py` — Available from Phase 03
- `scripts/summarize.py` — Will be created in Phase 06 (stub it for now)
- `scripts/analyze_sentiment.py` — Will be created in Phase 06 (stub it for now)
- `site/` — React app from Phase 04

## Deliverables

### 1. `.github/workflows/collect.yml` — Foca tier (cron 10min)

Trigger: `schedule: [{cron: '*/10 * * * *'}]` + `workflow_dispatch`.

Steps:
- `actions/checkout@v4` with `fetch-depth: 1`
- `actions/setup-python@v5` with Python 3.12, pip cache
- `pip install -r requirements.txt`
- `playwright install chromium --with-deps`
- Collect step (with soft failures for optional sources):
  ```
  python scripts/collect_rss.py
  python scripts/collect_parties.py    || echo "parties failed, continuing"
  python scripts/collect_polls.py      || echo "polls failed, continuing"
  python scripts/collect_social.py     || echo "social failed, continuing"
  ```
- AI Processing step:
  ```
  python scripts/summarize.py          || echo "summarize failed, continuing"
  python scripts/analyze_sentiment.py  || echo "sentiment failed, continuing"
  python scripts/build_data.py
  python scripts/generate_rss_feed.py  || echo "rss feed failed, continuing"
  ```
- Commit step: stage `data/` and `site/public/feed*.xml`; skip if no changes
- Secrets: `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`, `VERTEX_ACCESS_TOKEN`, `VERTEX_BASE_URL`, `XIAOMI_MIMO_API_KEY`, `TWITTER_BEARER_TOKEN`, `YOUTUBE_API_KEY`
- `permissions: {contents: write}`
- `timeout-minutes: 25`

### 2. `.github/workflows/validate.yml` — Editor tier (push + cron 30min)

Trigger: `push` on `data/raw/**` paths + `schedule: [{cron: '*/30 * * * *'}]` + `workflow_dispatch`.

Steps:
- Checkout, Python setup, pip install
- Run `python scripts/summarize.py` (processes all `status: "raw"` articles)
- Run `python scripts/analyze_sentiment.py`
- Run `python scripts/build_data.py`
- Commit updated `data/articles.json` and `data/sentiment.json`
- Secrets: full AI provider secrets set
- `permissions: {contents: write}`
- `timeout-minutes: 30`

### 3. `.github/workflows/curate.yml` — Editor-chefe tier (cron hourly + 90min skip logic)

Trigger: `schedule: [{cron: '0 * * * *'}]` + `workflow_dispatch`.

Steps:
- Checkout, Python setup, pip install
- Run `python scripts/curate.py` (contains 90-min skip logic internally — see Implementation Notes)
- Commit `data/curated_feed.json`, `data/weekly_briefing.json`, `data/quiz.json`, `data/.curate_last_run`
- `continue-on-error: true` on curate step to avoid blocking deploy
- Secrets: full AI provider secrets set
- `permissions: {contents: write}`
- `timeout-minutes: 30`

Create stub `scripts/curate.py` with 90-min skip logic:
```python
import json, time
from pathlib import Path

LAST_RUN_FILE = Path("data/.curate_last_run")
MIN_INTERVAL_SECONDS = 90 * 60

if LAST_RUN_FILE.exists():
    elapsed = time.time() - float(LAST_RUN_FILE.read_text())
    if elapsed < MIN_INTERVAL_SECONDS:
        print(f"Skipping: only {elapsed/60:.1f} min since last run (minimum: 90 min)")
        raise SystemExit(0)

LAST_RUN_FILE.write_text(str(time.time()))
print("Curate stub: full implementation in Phase 06.")
```

### 4. `.github/workflows/deploy.yml` — GitHub Pages deploy

Trigger: `push` on `main` with paths `['site/**', 'data/**', 'docs/case-study/**']`.

```yaml
permissions: {pages: write, id-token: write}
environment: {name: github-pages, url: '${{ steps.deployment.outputs.page_url }}'}
```

Steps:
- Checkout
- Python setup + `pip install -r requirements.txt`
- `python scripts/generate_seo_pages.py || echo "seo pages failed, continuing"`
- Node 20 setup with npm cache at `site/package-lock.json`
- `cp -r data/ site/public/data/`
- `cp -r docs/case-study/ site/public/case-study/ || true`
- `cd site && npm ci && npm run build`
- `actions/configure-pages@v4`
- `actions/upload-pages-artifact@v3` with `path: site/dist`
- `actions/deploy-pages@v4`

### 5. `.github/workflows/watchdog.yml` — Daily pipeline health check

Trigger: `schedule: [{cron: '0 6 * * *'}]` + `workflow_dispatch`.

Steps:
- Checkout
- Python setup + pip install
- Run `python scripts/watchdog.py` (generates `data/pipeline_health.json`)
- Commit `data/pipeline_health.json` if changed

Create stub `scripts/watchdog.py`:
```python
import json
from datetime import datetime
from pathlib import Path

health = {
    "checked_at": datetime.utcnow().isoformat() + "Z",
    "status": "ok",
    "notes": "Watchdog stub — full implementation Phase 16."
}
Path("data/pipeline_health.json").write_text(json.dumps(health, indent=2))
print("Watchdog: pipeline_health.json written.")
```

### 6. Seed data files required by pipeline stubs

Create empty-but-valid seed files if not already present:
- `data/pipeline_errors.json` — `{"errors": [], "last_checked": null}`
- `data/pipeline_health.json` — stub health object
- `data/ai_usage.json` — `{}` (created by ai_client.py if missing, but seed it)
- `data/.curate_last_run` — empty file (or `0` so first curate run always executes)

### 7. GitHub Pages — Settings confirmation

Document in the commit message or README that the operator must:
1. Go to `Settings > Pages`
2. Set Source to `GitHub Actions`
3. Save

This cannot be automated via workflow; it requires a one-time manual action.

## Implementation Notes

- The `collect.yml` workflow uses `git diff --staged --quiet || (git commit -m ... && git push)` to skip empty commits — this is idempotent and prevents noise in the commit history.
- Python scripts that do not yet exist (Phase 06+) must be stubbed as no-ops so the workflow doesn't fail: `scripts/collect_parties.py`, `scripts/collect_social.py`, `scripts/summarize.py`, `scripts/analyze_sentiment.py`, `scripts/generate_rss_feed.py`, `scripts/generate_seo_pages.py`.
- Each stub prints a clear message: `"[stub] <script>.py not yet implemented — Phase XX"`
- The 90-min skip logic in `curate.py` uses `data/.curate_last_run` — this file must be committed by the workflow or reset will occur on every fresh checkout.
- `validate.yml` is triggered by push on `data/raw/**` but since the Foca tier may write directly to `data/articles.json` (not `data/raw/`), the cron fallback every 30 min is the primary trigger until Phase 06 separates the raw directory.
- All workflows use `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4` — pin to `@v4`/`@v5` to avoid breaking changes.

## Acceptance Criteria

- [ ] All 5 workflow files exist under `.github/workflows/`
- [ ] `workflow_dispatch` trigger works for all 5 workflows (manually triggered from GitHub Actions UI)
- [ ] `collect.yml` runs to completion without error (even if AI steps are stubs)
- [ ] `deploy.yml` produces a live GitHub Pages site at `https://carlosduplar.github.io/eleicoes-2026-monitor/`
- [ ] `watchdog.yml` writes `data/pipeline_health.json` and commits it
- [ ] `curate.yml` skip logic prevents back-to-back runs within 90 minutes
- [ ] No workflow fails due to missing scripts (all non-existent scripts are stubbed)
- [ ] `git log` shows automated commits from `action@github.com`
- [ ] `data/pipeline_errors.json` exists and is valid JSON

## Commit & Push

After all deliverables are verified:

```
git add .github/workflows/ scripts/curate.py scripts/watchdog.py data/pipeline_errors.json data/pipeline_health.json data/ai_usage.json data/.curate_last_run
git commit -m "feat(phase-05): CI/CD workflows — Foca, Editor, Editor-chefe, deploy, watchdog

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-05-arch.DONE`.
