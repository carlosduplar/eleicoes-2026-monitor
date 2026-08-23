# 02 - Risk Register (Phase 1)

Date: 2026-08-23. Companion: `01-current-architecture.md` (findings F1-F9 referenced below).

Each risk lists: trigger, blast radius, detection method, rollback method, test strategy. Confidence tags match the diagnosis doc.

---

## R1 - Site build broken on clean checkouts (F1, Critical, OBSERVED)

- **STATUS 2026-08-23**: remediation implemented in M0 - file staged for commit plus regression guard `tests/test_frontend_integrity.py` (proven red before staging, green after). Awaiting merge.
- **Trigger**: any fresh `git clone` / CI checkout of master; `npm run build` fails resolving `./utils/bootData` (site/src/main.jsx:15, site/src/hooks/useData.js:3 import an untracked file).
- **Blast radius**: entire Deploy Pages workflow; site freezes at last good artifact. Reader-visible outage once CDN artifact ages or a manual redeploy runs. No data loss.
- **Detection**: run `git stash -u && npm run build` locally (reproduces); or watch Deploy workflow result for HEAD; now also caught by the integrity guard test.
- **Rollback**: commit the missing file (single-file change); or revert `db6b4be1c`.
- **Test strategy**: `tests/test_frontend_integrity.py` walks every relative/aliased import under site/src and fails on unresolved or untracked targets.

## R2 - Operational state published to public web root (F2, High, OBSERVED)

- **Trigger**: every deploy (unconditional: `public/**` → `dist/**` → Pages artifact).
- **Blast radius**: public exposure of internal error logs (`pipeline_errors.json`: URLs, content snippets, provider errors), editorial blocklists (`editor_feedback.json` 4.3MB), AI usage counters, fetch state. Repo bloat: multi-MB JSON diffs on most bot commits; slow clones over time. UNKNOWN whether any external consumer depends on these URLs (treat as "assume none" only after checking access logs - not available here).
- **Detection**: `ls site/dist/data`; repo size trend; any third-party reference scan (UNKNOWN).
- **Rollback**: move files out of `site/public/` (e.g., `state/` at repo root) + update the ~13 path constants; git history keeps old copies public via Pages history - cannot fully unpublish what was already fetched.
- **Test strategy**: contract tests pinning which filenames are allowed in `site/public/data` (whitelist test); existing module tests keep passing after path constant extraction (F5 refactor is prerequisite).

## R3 - Silent data loss in bot merge/rebase resolution (F3, High)

- **Trigger**: two writers race despite lock granularity (lock is per-ref and serializes, but each workflow pulls late; long AI steps widen windows). Rebase/merge conflict on `articles.json` etc.
- **Blast radius**: freshly computed summaries/sentiment discarded by `--theirs` fallbacks (validate.yml:69, collect.yml:165); union-merge may resurrect filtered articles if base/remote semantics diverge. Self-heals partially: next Collect re-collects, next Validate re-summarizes (raw items remain). Curation promotions could be lost permanently until recomputed (deterministic from inputs - INFERRED recoverable).
- **Detection**: currently none. Add: count of conflict-resolution events per run printed to log; watchdog comparing expected-vs-actual article counts.
- **Rollback**: git history itself (bot commits are granular); `revert` the losing commit.
- **Test strategy**: characterization tests for `scripts/merge_json.py` union semantics (exists today? no dedicated test file found - gap); dry-run harness replaying a recorded conflict scenario.

## R4 - ai_client internals reached into by consumers (F4, Medium-High)

- **Trigger**: any refactor of circuit-breaker state in `ai_client.py`.
- **Blast radius**: summarize.py breaks (imports `_provider_failure_counts`, `_CIRCUIT_BREAKER_THRESHOLD` directly, summarize.py:20); hidden coupling makes provider-chain changes risky across 6 consumer modules.
- **Detection**: grep for underscore imports (trivial).
- **Rollback**: n/a (structural risk; regression caught by tests).
- **Test strategy**: scripts/test_ai_client.py exists (585 lines) - extend with a contract test asserting consumers use only public API before refactoring.

## R5 - Store path duplicated in 13 modules (+1 cwd-relative outlier) (F5, Medium)

- **Trigger**: moving/renaming store dir; running `generate_rss_feed.py` from non-root cwd (generate_rss_feed.py:15).
- **Blast radius**: missed edit = silent write to wrong location or crash; cwd bug = feed generation writes nothing where deploy expects it.
- **Detection**: grep `DATA_DIR` (68 hits today).
- **Rollback**: revert constant extraction PR (pure mechanical change).
- **Test strategy**: after extraction, full pytest suite must stay green unchanged (tests monkeypatch module attributes - extraction must preserve patchability, e.g., module-level indirection).

## R6 - Unbounded growth of editor_feedback.json / pipeline_errors.json (F6, Medium)

- **Trigger**: time. Every run loads/saves 4.3MB feedback; errors append forever (4088 now).
- **Blast radius**: linearly growing CI duration, git size, deploy size, memory in-process. Eventual workflow timeout risk (collect timeout-minutes: 25).
- **Detection**: file-size alarm (watchdog already reads health metrics - extendable).
- **Rollback**: pruning script + retention policy analogous to archive_articles.py tiers.
- **Test strategy**: property test: pruning keeps all rules/IDs referenced by live articles; snapshot test on pruned schema shape (docs/schemas/editor_feedback.schema.json exists).

## R7 - Schema validation is advisory only (OBSERVED, new entry)

- **Trigger**: malformed article passes `build_data._validate_articles` (logs warning, publishes anyway, build_data.py:167-184).
- **Blast radius**: malformed record reaches frontend rendering paths (INFERRED: defensive parsing exists in components, e.g. NewsFeed guards; severity contained but unknown fields propagate to search index).
- **Detection**: CI log warnings (currently unread routinely).
- **Rollback**: n/a.
- **Test strategy**: decision needed later (block vs metric); for now add test asserting warnings are emitted for seeded invalid fixture (locks current behavior honestly).

## R8 - Dual ownership of quiz.json (F3/F2 adjacent, OBSERVED)

- **Trigger**: curate.yml in-process `generate_quiz.main()` and update-quiz.yml both write quiz.json same day.
- **Blast radius**: benign under concurrency lock (serialized); worst case wasted AI spend + last-writer-wins content flip-flop within a day.
- **Detection**: quiz.json.bak presence suggests past incident handling (UNKNOWN provenance).
- **Rollback**: git history.
- **Test strategy**: none needed if ownership unified; note in ADR.
- **RESOLVED 2026-08-23**: owner decision keeps daily cron (redundancy valued over spend); risk formally accepted, no unification.

## R9 - Local/CI environment parity gap (F8, Low-Medium)

- **Trigger**: contributor without ubuntu+x86 (e.g., Termux/arm64) runs subset; sklearn/playwright/google-cloud uninstallable.
- **Blast radius**: weakened pre-push signal; migrations touching dedup (sklearn) or polls (playwright) validated only in CI.
- **Detection**: pytest collection warnings.
- **Rollback**: n/a.
- **Test strategy**: mark env-blocked modules explicitly in migration plans ("must validate in CI"); consider optional extras grouping in requirements later (out of scope unless approved).

## R10 - Secrets exposure surface (High-risk area, OBSERVED controls)

- **Trigger**: provider error messages containing credentials/URLs flowing into published pipeline_errors.json.
- **Blast radius**: credential leak (public site).
- **Existing control OBSERVED**: curate.py `_append_pipeline_error` regex-redacts API-key patterns (:140); INFERRED similar patterns elsewhere but NOT verified in summarize/analyze_sentiment/collectors (gap).
- **Detection**: audit grep of all `_append_pipeline_error` call sites for redaction coverage.
- **Rollback**: n/a.
- **Test strategy**: unit test feeding fake error text with key-like substrings through every writer path; assert `[REDACTED]`.

## Top ordering logic (feeds Phase 2)

R1 is an outage-class defect independent of architecture choices - candidate for immediate standalone fix upon approval. R2+R5 share one remediation seam (path constants + store split). R3/R8 need writer-ownership decisions (ADR material). R6 needs a policy decision (retention). Everything else is containment/hygiene.
