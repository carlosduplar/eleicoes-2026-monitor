# Task: Phase 02

Dispatched by conductor.ps1 at 2026-03-09T15:29:51Z
Model: gpt-5.3-codex

## Instructions

Read and implement the spec in `plans/phase-02-arch.md`.
Follow all rules in `.github/copilot-instructions.md` and `docs/agent-protocol.md`.

## Completion protocol

When ALL deliverables in the spec are implemented and committed:
1. Run any tests defined in the spec and confirm they pass.
2. Commit all changes: `git add -A && git commit -m "feat: phase 02 complete"`
3. Create the sentinel: `New-Item -Path plans/phase-02-arch.DONE -ItemType File -Force`
4. STOP — do not proceed to the next phase.

## Escalation protocol

If you encounter the same error more than 3 times in a row:
1. Write `tasks/phase-02/ESCALATION.md` with:
   - Full error + stack trace
   - Number of attempts
   - Your hypothesis (spec ambiguous? broken dependency? logic bug?)
2. Do NOT retry — stop immediately and wait for human review.

## Context files

- `PLAN.md`                           master plan
- `plans/phase-02-arch.md`       this phase spec
- `docs/agent-protocol.md`            handoff protocol
- `docs/schemas/`                     JSON schemas (do not deviate)
- `.github/copilot-instructions.md`   project-specific rules
