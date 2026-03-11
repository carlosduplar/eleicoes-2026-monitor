# ADR 005 — Quiz de Afinidade Politica

## Status
Accepted

## Context
The portal needs a tool for users to discover which candidates align with their views
without introducing confirmation bias. The quiz must work entirely client-side with
no server calls or analytics that reveal choices before the result.

## Decision
1. **Inverted framing:** Options present policy positions, not candidate names.
   candidate_slug and source_* are never rendered during the question phase.
2. **Silent progressive funnel:** Users answer questions sequentially.
   Early-exit is possible when the margin between top candidates is decisive.
3. **Confidence filtering:** Only high/medium confidence positions are included.
   Low-confidence or unclear stances are silently omitted.
4. **Source reveal on result only:** After completing all questions, the result page
   reveals which candidate each chosen option belonged to, with source citations.
5. **Stateless sharing:** Results are encoded as base64url in the ?r= query parameter.
   No server state required. Anyone with the URL sees the same result.
6. **Daily extraction:** A GitHub Actions cron job extracts positions from articles daily.
   AI failures are non-blocking: existing data is preserved for that candidate/topic.

## Consequences
- Users cannot game the quiz by seeing candidate names during questions.
- Low-confidence AI extractions are never shown, reducing misinformation risk.
- Share URLs may become stale if quiz topics change (acceptable trade-off).
- The quiz works fully offline after initial data load.
