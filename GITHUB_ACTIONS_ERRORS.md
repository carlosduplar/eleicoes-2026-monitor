# GitHub Actions Errors and Warnings Report

Generated: 2026-03-12

This document catalogs errors and warnings from the last 5 runs of each GitHub Actions workflow.

---

## 1. Collect (Foca) - `.github/workflows/collect.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 22992329527 | 2026-03-12 | in_progress |
| 22991299915 | 2026-03-12 | success |
| 22989672427 | 2026-03-12 | success |
| 22988236779 | 2026-03-12 | success |
| 22986621078 | 2026-03-12 | success |

### Errors & Warnings Found

**Failed Runs:**
- **Run 22944619927** (2026-03-11): `git pull --rebase` failed with error:
  ```
  error: cannot pull with rebase: You have unstaged changes.
  error: Please commit or stash them.
  ```
  **Cause:** The workflow attempts to pull with rebase but has unstaged changes from the checkout.

**Warnings in Successful Runs:**
- **Node.js Deprecation Warnings** (all runs):
  - `DEP0040`: The `punycode` module is deprecated
  - `DEP0169`: `url.parse()` behavior is not standardized and prone to errors (CVE-related warning)

- **Data Collection Warnings:**
  - Feed parse warning: `document declared as utf-8, but parsed as windows-1252`
  - DNS resolution failures:
    - `pl.org.br` - No address associated with hostname
    - `dc.org.br` - Name or service not known
  - HTTP errors:
    - `republicanos10.org.br` - 403 Forbidden
    - `missao.org.br` - 404 Not Found
  - `Parties: 4 new articles from 8 sources (4 errors)`
  - `Collected 0 new polls from 6 institutes (1 errors)`

- **AI Summarization Warnings:**
  - `Skipping LLM summarization: blocked/error page detected: 'access denied'`
  - `Skipping LLM summarization: no sentence terminator`

---

## 2. Curate (Editor-chefe) - `.github/workflows/curate.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 22991449569 | 2026-03-12 | **failure** |
| 22989772359 | 2026-03-12 | success |
| 22987559618 | 2026-03-12 | success |
| 22985193147 | 2026-03-12 | success |
| 22981638782 | 2026-03-12 | success |

### Errors & Warnings Found

**Failed Run 22991449569:**
```
error: failed to push some refs to 'https://github.com/carlosduplar/eleicoes-2026-monitor'
hint: Updates were rejected because the remote contains work that you do not have locally.
```
**Cause:** Race condition - another workflow pushed changes while this run was processing. The workflow needs to pull before pushing.

**Warnings in Successful Runs:**
- **Node.js Deprecation Warnings** (same as Collect)
- **NVIDIA API Failures:**
  - `WARNING: [AI] nvidia failed: 404 page not found` - The NVIDIA API endpoint is returning 404 errors
  - `INFO: [AI] nvidia skipped: circuit breaker open (3 consecutive failures)` - After 3 failures, the circuit breaker opens and skips NVIDIA

---

## 3. Validate (Editor) - `.github/workflows/validate.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 22992167770 | 2026-03-12 | in_progress |
| 22991158692 | 2026-03-12 | success |
| 22989025032 | 2026-03-12 | success |
| 22987634195 | 2026-03-12 | success |
| 22985593878 | 2026-03-12 | success |

### Errors & Warnings Found

**Failed Runs:**
- **Run 22962241174** (2026-03-11): Same push rejection error as Curate
- **Run 22959596329** (2026-03-11): Same push rejection error
- **Run 22951344448** (2026-03-11): Same push rejection error
- **Run 22950351794** (2026-03-11): Same push rejection error
- **Run 22944415958** (2026-03-11): Same push rejection error

All failed with:
```
error: failed to push some refs to 'https://github.com/carlosduplar/eleicoes-2026-monitor'
hint: Updates were rejected because the remote contains work that you do not have locally.
```

**Warnings in Successful Runs:**
- **Node.js Deprecation Warnings**
- **AI Summarization Warnings:**
  - `WARNING: Skipping LLM summarization: blocked/error page detected: 'access denied'`
  - `WARNING: Skipping LLM summarization: no sentence terminator`

---

## 4. Watchdog - `.github/workflows/watchdog.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 22990193554 | 2026-03-12 | success |
| 22940532036 | 2026-03-11 | success |

### Errors & Warnings Found

**Warnings:**
- **Node.js Deprecation Warnings**
- `Watchdog: pipeline_health.json written (warning)` - Indicates pipeline health issues

---

## 5. Update Quiz Positions - `.github/workflows/update-quiz.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 22986959823 | 2026-03-12 | success |

### Errors & Warnings Found

**Warnings:**
- **Node.js Deprecation Warnings**
- **NVIDIA API Failures:**
  - `WARNING: [AI] nvidia failed: 404 page not found`
  - `INFO: [AI] nvidia skipped: circuit breaker open (3 consecutive failures)`
- **JSON Parse Error:**
  - `WARNING: [AI] extract_candidate_position parse failure: Unterminated string starting at: line 2 column 18 (char 19)`

---

## 6. Automatic Dependency Submission - GitHub-managed

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 22962782858 | 2026-03-11 | **failure** |

### Errors & Warnings Found

**Failed Run 22962782858:**
```
HttpError: An error occurred while processing your request. Please try again later.
```
**Cause:** GitHub API error when submitting dependency snapshot. This appears to be a transient GitHub API issue.

**Warnings:**
- **Node.js 20 Actions Deprecation:**
  ```
  ##[warning]Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work as expected:
  actions/component-detection-dependency-submission-action@374343effede691df3a5ffaf36b4e7acab919590
  ```
  Actions will be forced to run with Node.js 24 starting June 2nd, 2026.

---

## Summary of Issues

### Critical (Causes Workflow Failures)

1. **Git Push Conflicts** (Collect, Curate, Validate)
   - Multiple workflows trying to push simultaneously cause race conditions
   - **Fix:** Add `git fetch origin` and `git pull --rebase origin master` before push, or implement a locking mechanism

2. **NVIDIA API 404 Errors**
   - `https://integrate.api.nvidia.com/v1/chat/completions` returns 404
   - **Fix:** Verify the NVIDIA API endpoint URL and API key configuration

### High Priority

3. **Node.js 20 Deprecation**
   - All workflows use `actions/checkout@v4` and `actions/setup-python@v5` which run on Node.js 20
   - **Fix:** Update to latest versions that support Node.js 24, or set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`

4. **Git Unstaged Changes Error** (Collect)
   - `git pull --rebase` fails due to unstaged changes
   - **Fix:** Ensure clean working directory before pull, or use `git stash`

### Medium Priority

5. **Data Collection Failures**
   - Multiple party/polling source websites unreachable (DNS/403/404 errors)
   - **Fix:** Review and update source URLs, or remove inactive sources

6. **AI Summarization Blocked Pages**
   - Some article pages return 'access denied' 
   - **Fix:** May need to adjust scraping behavior or user-agent

7. **JSON Parse Errors in Quiz**
   - `extract_candidate_position` returns malformed JSON
   - **Fix:** Improve AI prompt or add error handling

### Low Priority

8. **Node.js Deprecation Warnings**
   - `punycode` and `url.parse()` warnings
   - **Fix:** Update to newer action versions

9. **Feed Encoding Warnings**
   - RSS feeds declared as UTF-8 but parsed as windows-1252
   - **Fix:** Investigate feed encoding handling
