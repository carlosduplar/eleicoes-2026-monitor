# GitHub Actions Errors and Warnings Report

Generated: 2026-03-13

This document catalogs errors and warnings from recent GitHub Actions workflow runs.

---

## 1. Collect (Reporter) - `.github/workflows/collect.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 23055595387 | 2026-03-13 | success |
| 23053531829 | 2026-03-13 | success |
| 23050776086 | 2026-03-13 | success |
| 23049458637 | 2026-03-13 | success |
| 23048456286 | 2026-03-13 | success |

### Errors & Warnings Found

**Warnings in Successful Runs:**
- **AI Summarization Warnings:**
  - `WARNING: Skipping LLM summarization: no sentence terminator` (Frequent in multiple runs)
- **Vertex AI Search:**
  - `WARNING: Missing required environment variables for Vertex indexing` (Indexing skipped)
- **News Feed Consolation:**
  - `Consolidated: 500 published articles (... 74 trimmed by limit)`

---

## 2. Curate (Editor-chefe) - `.github/workflows/curate.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 23055662261 | 2026-03-13 | success |
| 23053925438 | 2026-03-13 | success |
| 23050846708 | 2026-03-13 | **failure** |
| 23048568281 | 2026-03-13 | **failure** |
| 23046529671 | 2026-03-13 | cancelled |

### Errors & Warnings Found

**Failed Runs (67, 68):**
- **Error:** `git pull --rebase` conflict.
- **Cause:** Rapidly sequential or overlapping workflow runs triggering race conditions on the data files.

---

## 3. Validate (Editor) - `.github/workflows/validate.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 23055912509 | 2026-03-13 | success |
| 23054129349 | 2026-03-13 | success |
| 23051308718 | 2026-03-13 | success |
| 23049548429 | 2026-03-13 | **failure** |
| 23047915721 | 2026-03-13 | success |

### Errors & Warnings Found

**Failed Run 83:**
- **Error:** `error: Terminal is dumb, but EDITOR unset` during rebase auto-resolution.
- **Cause:** The auto-resolution script tried to commit but lacked a defined `GIT_EDITOR`.

---

## 4. Watchdog - `.github/workflows/watchdog.yml`

### Recent Runs Status
| Run ID | Date | Status |
|--------|------|--------|
| 23039735490 | 2026-03-13 | success |
| 22990193554 | 2026-03-12 | success |

---

## Summary of Current Issues

### Critical (Active or Periodic)

1. **Git Push/Pull Race Conditions**
   - Even with concurrency groups, workflows sometimes fail during rebase if the remote state changes between the fetch and the push.
   - **Status:** Occasional failures in `Curate` and `Validate`.

2. **Rebase Commit Failure**
   - In `Validate`, the fallback mechanism for conflict resolution failed because `GIT_EDITOR` was not set.
   - **Potential Fix:** Set `GIT_EDITOR=true` in the relevant step.

### High Priority

3. **AI Provider Availability**
   - Frequent fallback usage observed. Ollama (`nemotron-3-super`) is performing well, but reliance on fallbacks indicates periodic unavailability of the primary NVIDIA endpoint.

4. **Vertex AI Indexing**
   - Indexing is currently disabled/skipped due to missing configuration.

### Low Priority

5. **Summarization Snippets**
   - Articles without clear sentence terminators are being skipped to ensure quality. This is expected behavior but reduces coverage slightly.
