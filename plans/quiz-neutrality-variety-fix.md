# Plan — Quiz neutrality leaks + repetitive wording fix

## Goal

Eliminate candidate-identifying leaks from quiz option texts and break template
repetition, then regenerate `site/public/data/quiz.json`. User decisions locked:
**both generator + data fixed together**, **drop weak fallback-heavy topics**,
**strict biography-clue filtering**.

Frontend (`QuizEngine.jsx`, `QuizPage.jsx`) already strips `candidate_slug` /
`sources` during questions — confirmed clean. All leaks are *inside*
`text_pt` / `text_en` themselves.

## Evidence (current `site/public/data/quiz.json`, 9 topics / 33 options)

Direct name leaks (EN only — PT/EN divergence):
- `lgbtq.opt_c` EN: "Additionally, a central point: Ronaldo 's party has a
  conservative stance…" (`candidate_slug: caiado`).
- `corrupcao.opt_b` EN: "Additionally, a central point: Flávio supported the
  establishment…" (`candidate_slug: flavio-bolsonaro`).

Third-person / meta leaks:
- `armas.opt_b` PT+EN: "E um ponto central: O político é favorável…" /
  "Additionally, a central point: The politician is in favor…".
- `seguranca.opt_a` EN-only: "…Additionally, a central point: Candidate
  prioritizes social policies…" (PT has no such clause).
- `educacao.opt_b`: "Entendo que não há informações suficientes para
  determinar uma posição clara…" (admits missing data, breaks immersion).
- `meio_ambiente.opt_c`: "…como promulgado por governos regionais" (governor clue).
- `aborto.opt_c`: "…mulheres que acidentalmente interrompem a gravidez" (nonsense).

Biography / program clues (strict mode → must go):
- `meio_ambiente.opt_a`: IBAMA, Fundo Amazônia, Ministério do Meio Ambiente.
- `educacao.opt_a`: Prouni, Fies.

Polarity inversions (scoring integrity, worse than wording):
- `lgbtq.opt_b` (flavio-bolsonaro, weight +3): text is *pro*-LGBTQ ("assegurem
  acesso equitativo…") while `source_pt` says opposition ("o normal é ser
  heterossexual").
- `seguranca.opt_c` (caiado, weight +3): text is progressive ("expansão de
  direitos") while source says hardline ("endurecimento de penas").
- Root cause: `build_topic_options()` trusts AI `weight`/`stance` over the
  mapped known-position stance.

Repetition (measured):
- Tail "com metas transparentes e revisão periódica" / "with transparent goals
  and periodic review" in ~15/33 options.
- Four stance sentences reused verbatim across topics (`impostos` 3/4,
  `midia` 3/4, `lgbtq` 3/4, `armas` 2/3 are near-identical templates).
- Only 4 PT intros / 4 EN intros; AI prompt rule 8 ("vary openings") unenforced.

Why guards missed it (`scripts/generate_quiz.py`, `scripts/ai_client.py`):
1. `BANNED_NAME_TERMS` has surnames (`caiado`, `bolsonaro`) but not first
   names (`Ronaldo`, `Flávio`); accent-sensitive substring match misses
   `Flávio` vs `flavio`.
2. `_THIRD_PERSON_LEAK_PATTERNS` misses `o político / the politician`,
   bare `Candidate <verb>`, `não há informações suficientes`,
   `como promulgado / como governador / durante seu governo`, and the
   fallback's own appendages ("E um ponto central:", "Additionally, a central
   point:").
3. `_hint_fragment_ok` gates PT and EN independently → EN-only leaks pass.
4. `_content_core` + `CORE_SIMILARITY_THRESHOLD=0.85` compares full text
   *including* hint sentences, so same-template/different-hint passes as
   "distinct".
5. AI validator is advisory-only: `_try_append_option` ignores
   `passes_all=False` unless parse error (pinned by
   `test_build_topic_options_local_first_ignores_ai_non_parse_failures`).
6. Generation prompt bans candidates/parties/events but not first names,
   offices, program names, achievements, or extra EN-only clauses.

## Steps

### 1. Harden local quality gate — `scripts/generate_quiz.py`
- Expand `BANNED_NAME_TERMS` with first names + accent variants (ronaldo,
  flávio/flavio, romeu, renan, augusto, edmilson, hertz, samara, wilson,
  clariana, rui, pablo, marçal/marcal, jair). Normalize accents (NFKD strip)
  in `_contains_banned_terms` before matching.
- Add `BANNED_BIO_TERMS` + `_contains_bio_reference()` → new `bio_reference`
  failure. Start list (word-boundary, multi-word precise): `ibama`,
  `fundo amazônia`, `ministério do meio ambiente`, `cop30`, `prouni`,
  `fies`, `escola sem partido`, `excludente de ilicitude`, `maioridade penal`,
  `pena de morte`, `amianto` (as office-history tell — or rewrite, see risk),
  `governador`, `ex-presidente`, `durante seu governo`, `quando fui`,
  `como governador`. Keep allowlist for generic vocabulary
  (`fiscalização ambiental`, `universidades federais` stay legal).
- Broaden `_THIRD_PERSON_LEAK_PATTERNS`: `\bcandidat[oa]\b` (any form),
  `\bo\s+pol[ií]tico\b`, `\bthe\s+(candidate|politician)\b`,
  `\bcandidate\s+(prioritizes|supports|is)\b`,
  `\bn[aã]o\s+h[aá]\s+informa`, `informa[cç][oõ]es?\s+suficientes`,
  `\bcomo\s+(promulgado|governador)\b`, `\bdurante\s+(seu|meu)\s+governo\b`,
  plus the appendage markers themselves (`e um ponto central`,
  `additionally,?\s+a central point`, `além disso,?\s+proponho` if removed).
- Add EN/PT consistency check: fail (`en_pt_mismatch`) when sentence counts
  differ or one side contains an appendage clause the other lacks.
- Add polarity check: fail/coerce when `sign(weight) !=
  sign(STANCE_TO_WEIGHT[mapped stance])` for non-neutral stances. Prefer
  **reject + try next fallback** (log polarity), not silent coerce.
- Add template guard: reject any option containing a verbatim
  `_STANCE_FALLBACK_*` sentence or fixed tail already used in the same topic
  (track per-topic used templates; each stance sentence max 1×/topic).

### 2. De-template the fallback — `scripts/generate_quiz.py`
- Recommended: **delete the hint-appendage mechanism**
  (`E um ponto central:…`, `Additionally, a central point:…`,
  `Além disso, proponho…`). It is the leak vector, the EN/PT divergence
  source, and a template tell. Replace with topic-specific lever-based
  fallback: per-topic 3–5 concrete levers (e.g. armas → acesso civil /
  fiscalização / campanhas; impostos → progressividade / simplificação /
  carga; educação → federal/universidades vs técnico/vouchers…). Fallback =
  intro + lever + instrument, tail rotated or dropped.
- Rotate/drop the fixed tail: 4–6 closings or none. Expand intros 4→8–10 and
  enforce per-topic intro uniqueness.
- Fix dedup: compare first-sentence core only (strip hint/appendage), lower
  `CORE_SIMILARITY_THRESHOLD` 0.85 → ~0.6–0.7 so same-stance templates still
  collide. Keep `MAX_FALLBACK_SHARE=1/3` gate (user chose drop-weak-topics).

### 3. Fix AI prompts + validator authority — `scripts/ai_client.py`
- `generate_quiz_topic_options`: extend ban to first names, offices,
  program/agency names, numbers/achievements; require ≥1 concrete instrument
  per option, distinct verb per option; require EN = translation of PT (same
  sentences, no extra clause); add negative examples (never "As governor…",
  "The candidate…", "Additionally, a central point…"); supply 8 allowed
  openings, each max 1×/topic.
- `validate_quiz_option_quality`: add checks 9–12 (first names / offices /
  programs; PT/EN parity; weight polarity vs text; generic-template
  detection).
- Make validator failures **reject** (after local pass), except
  exception/parse-error → local-only + `validation_degraded=True`. Update
  `test_build_topic_options_local_first_ignores_ai_non_parse_failures`
  accordingly.

### 4. Regenerate + triage data — `site/public/data/quiz.json`
- Run `python -m scripts.generate_quiz`; validate against
  `docs/schemas/quiz.schema.json`; run full `_local_quality_check` audit +
  tail-frequency / intro-diversity counts (all must pass).
- Hotfix floor regardless of AI availability (worst 10): rewrite `lgbtq.opt_b`
  polarity, `lgbtq.opt_c` EN, `corrupcao.opt_b` EN, `armas.opt_b`,
  `seguranca.opt_a` EN + `opt_c` polarity, `educacao.opt_b`,
  `aborto.opt_c`, `impostos`/`midia` generic trio. If providers down and only
  fallback available, **drop** weak topics via existing
  `_should_drop_topic` gate rather than ship filler (accepted: fewer topics,
  e.g. 6–7 strong, over 9 with filler).

### 5. Tests
- `scripts/test_generate_quiz.py`: add cases — first-name leaks (Ronaldo,
  Flávio with accent), bio terms (IBAMA/Prouni/COP30/governador), EN-only
  appendage, `não há informações suficientes`, polarity mismatch,
  verbatim-template reuse, intro uniqueness.
- `scripts/test_ai_client.py`: update prompt-assertion tests for new rules.
- `qa/tests/test_quiz_neutrality.spec.js`: assert rendered
  `.quiz-option-card` text contains no first/party names, program names,
  "ponto central / central point", "não há informações suficientes",
  "o político / the politician"; assert fixed tail in ≤2 options/topic.
- Run: `pytest scripts/test_generate_quiz.py scripts/test_ai_client.py`,
  generation + schema validation, Playwright quiz specs.

## Risks
- Strict bio ban over-blocks ("fiscalização" vs "IBAMA"): mitigate with
  precise multi-word terms + word boundaries + allowlist review.
- Honoring AI validator raises drop rate; all-providers-down + strict gate
  may yield zero topics → `main()` already preserves existing `quiz.json`;
  run generation in CI with retries, never ship empty.
- Polarity reject changes coverage per topic; verify affinity math in
  `site/src/utils/affinity.js` untouched (weight set {-3,-2,0,2,3} preserved).
- Accent normalization (`Flávio`→`flavio`) must apply uniformly to text and
  term lists.
- Removing hints loses the only topic-specificity fallback had; lever-based
  rewrite must land or fallbacks stay clean-but-generic.

## Open questions
- Authoritative office/program term list: curate manually (~20 terms) or
  derive from `candidates_positions.json` proper nouns automatically?
- Lever axes for all 14 `QUESTION_TEMPLATES` topics: who supplies policy
  content (3–5 levers × 14 topics)?
- Minimum acceptable topic count after dropping weak topics (floor: 6–7?).
