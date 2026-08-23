# 05 - Architecture Decision Record: Consolidation over Restructure

Status: PROPOSED (awaiting owner approval)
Date: 2026-08-23
Context docs: `00-baseline.md`, `01-current-architecture.md`, `02-risk-register.md`, `03-target-architecture.md`, `04-migration-plan.md`

## Context

A solo-human/bot-heavy repository (OBSERVED: 159 human vs 7049 bot commits) operates a bilingual election-monitoring portal where git is the database, five scheduled workflows write JSON into the web root `site/public/data/`, and a React SSG site publishes that directory verbatim. Phase 1 established the cost concentration is operational: a broken clean build at HEAD (untracked required file), internal state and multi-MB audit files served publicly, duplicated path/CI-sync logic, unbounded file growth, and lossy conflict fallbacks. No evidence indicates module-layout or infrastructure classes of problems.

## Decision drivers

1. Transparency model requires artifacts auditable in-repo (README; ADR-006) - rules out externalizing primary store.
2. Operational defects dominate observed pain (F1-F3, F5-F7).
3. Single maintainer: enforcement/governance machinery has no operator.
4. Test suite couples to module attributes via monkeypatch - structural moves carry hidden verification costs.
5. Bot-driven write concurrency already serialized by one lock; redesigning storage has no evidenced trigger yet.

## Considered options

- **A. Consolidation** (chosen): shared path module; split published vs operational state (`state/` committed, not deployed); retention for unbounded files; composite CI action for 5x-duplicated sync blocks; single-writer ownership; hygiene fixes. See 03 §2 Option A / §4.
- **B. Staged pipeline package**: adds subpackages + CLI + import-lint. Rejected for now - self-challenged in 03 §3: import-churn against monkeypatch targets, governance without governors, does not touch dominant costs, blast radius across ~40 modules/~19 test files.
- **C. Externalized store** (DB/object storage/API): rejected - violates driver 1; adds hosting/auth/backup obligations; no evidenced performance/capacity trigger.

## Decision

Adopt **Option A** with explicit upgrade thresholds (03 §6): A->B on two of {>60 modules, >=2 recurring script contributors, second programmatic consumer}; revisit C-hybrid on {sync-timeout breaches, recurring discard-counter losses, clone-size pain}. The shared seam (`scripts/store.py`) is deliberately named/placed so B's future core package absorbs it without semantic migration.

## Consequences

Positive:
- Clean builds restored (M0); public CDN surface shrinks to genuine content (M3-M5); growth bounded by retention (M8); CI sync logic single-sourced with loss counters feeding watchdog observability (M6); ownership ambiguity removed (M7).
- Every step independently revertible; no step changes externally visible site behavior except retirement of accidental URLs (state/audit JSONs).

Negative / accepted risks:
- Old public URLs for relocated state die without redirects (static hosting limit). Residual UNKNOWN: unknown third-party scrapers; accepted after zero in-repo consumers verified.
- editor_feedback.json relocation (M4) APPROVED by owner 2026-08-23 (transparency is repo-level).
- Dual quiz writers RETAINED by owner decision 2026-08-23 (M7 rejected): daily cron + hourly in-process refresh coexist under the repo-write lock; last-writer-wins and duplicate AI spend accepted.

## Validation & rollback posture

Plan-wide: every PR carries its own revert path; baseline test command fixed in 04 "Ground rules"; blocked-local paths (sklearn/playwright/google-cloud) validated by required-green CI. Stop conditions defined per step in 04.
