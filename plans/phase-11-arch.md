# Phase 11 — Quiz de Afinidade Política

## Objective

Implement the full Political Affinity Quiz: position extraction pipeline (`extract_quiz_positions.py`), daily GitHub Actions workflow (`update-quiz.yml`), and the complete React quiz UI (question funnel + result card with source reveal + share button). Follow WF-05 (question) and WF-06 (result) wireframes. Never expose `candidate_slug` or `source_*` during questions. Create ADR 005.

## Input Context

- `docs/wireframes/WF-05-quiz-question-desktop.html` — Quiz question wireframe (open in browser)
- `docs/wireframes/WF-06-quiz-result-desktop.html` — Quiz result wireframe (open in browser)
- `docs/wireframes/WF-12-mobile-quiz.html` — Mobile quiz wireframe (390px)
- `docs/prompt-eleicoes2026-v5.md` lines 392-558 — Full quiz spec (schema, extraction pipeline, affinity algorithm, result reveal, shareUrl)
- `docs/schemas/quiz.schema.json` — Quiz data schema (from Phase 01)
- `data/articles.json` — Source articles for position extraction (from Phase 06)
- `scripts/ai_client.py` — `extract_candidate_position()` function (from Phase 02)
- `site/src/utils/candidateColors.js` — Candidate hex colors (from Phase 07)
- `site/src/components/MethodologyBadge.jsx` — Required on result page (from Phase 07)

## Deliverables

### 1. `scripts/extract_quiz_positions.py`

Daily extraction pipeline — replaces nothing (new file).

**Algorithm (from spec lines 440-481):**
```python
STANCE_MAP = {"favor": 2, "neutral": 0, "against": -2, "unclear": None}

def divergence_score(positions: list) -> float:
    stances = [STANCE_MAP[p["stance"]] for p in positions
               if p.get("confidence") in ("high","medium") and STANCE_MAP.get(p["stance"]) is not None]
    if len(stances) < 2: return 0.0
    return (max(stances) - min(stances)) / 4.0
```

**Key behaviors:**
- For each topic in `QUIZ_TOPICS` and each candidate in `CANDIDATES`:
  - Filter `data/articles.json` for articles mentioning that candidate + topic
  - Collect up to 12 most recent snippets (title + summary)
  - Call `ai_client.extract_candidate_position(candidate, topic_id, snippets)`
  - Store result (only `high`/`medium` confidence)
- Compute `divergence_score` per topic
- Run `select_quiz_topics()` to select 10-15 topics with highest divergence and cluster coverage
- Generate `question_pt` and `question_en` for each selected topic (use a template or AI-generated)
- Write `data/quiz.json` conforming to schema
- On AI failure: keep existing data for that candidate/topic, log error, continue
- Print summary: "Quiz: X topics selected, Y positions extracted (Z errors)"
- **Idempotent:** running twice produces the same output (AI calls use same inputs → same outputs for high-confidence results)

**`data/quiz.json` structure (from spec lines 401-436):**
```json
{
  "generated_at": "<ISO8601>",
  "ordered_topics": ["armas","aborto","privatizacao",...],
  "topics": {
    "armas": {
      "divergence_score": 0.95,
      "question_pt": "...",
      "question_en": "...",
      "options": [
        {
          "id": "opt_a",
          "text_pt": "...",
          "text_en": "...",
          "weight": 2,
          "candidate_slug": "tarcisio",
          "source_pt": "...",
          "source_en": "...",
          "confidence": "high"
        }
      ]
    }
  }
}
```

### 2. `.github/workflows/update-quiz.yml`

Daily cron at 3h UTC + `workflow_dispatch`.

```yaml
name: Update Quiz Positions
on:
  schedule: [{cron: '0 3 * * *'}]
  workflow_dispatch:
jobs:
  quiz:
    runs-on: ubuntu-latest
    permissions: {contents: write}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12', cache: 'pip'}
      - run: pip install -r requirements.txt
      - name: Extract positions
        env:
          NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          OLLAMA_API_KEY: ${{ secrets.OLLAMA_API_KEY }}
          VERTEX_ACCESS_TOKEN: ${{ secrets.VERTEX_ACCESS_TOKEN }}
          VERTEX_BASE_URL: ${{ secrets.VERTEX_BASE_URL }}
        run: python scripts/extract_quiz_positions.py
      - name: Commit quiz data
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/quiz.json
          git diff --staged --quiet || (git commit -m "chore: update quiz $(date -u +%Y-%m-%d)" && git push)
```

### 3. `site/src/utils/affinity.js`

Full implementation from spec (lines 484-538):
- `calculateAffinity(answers, quizData)` — returns candidates sorted by affinity score
- `shouldContinueQuiz(results, answeredCount, totalQuestions)` — early-exit logic

### 4. `site/src/utils/shareUrl.js`

```javascript
export const encodeResult = (answers) =>
  btoa(JSON.stringify(answers)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');

export const decodeResult = (r) =>
  JSON.parse(atob(r.replace(/-/g,'+').replace(/_/g,'/')));
```

### 5. `site/src/hooks/useQuiz.js`

Custom hook managing quiz state:
- `quizData` — loaded from `useData('quiz')`
- `answers` — `{topicId: {optionId, weight}}`
- `currentTopicIndex` — current question index
- `isComplete` — boolean
- `results` — `calculateAffinity(answers, quizData)` (computed when `isComplete`)
- `handleAnswer(topicId, optionId, weight)` — records answer, advances to next question or completes
- `reset()` — resets all state

### 6. `site/src/components/QuizEngine.jsx`

Quiz question UI — follows WF-05 (desktop) and WF-12 (mobile).

**CRITICAL:** Never render `option.candidate_slug` or `option.source_*` during questions. These fields exist only for internal calculation.

**Layout:**
- Progress bar: `currentTopicIndex / totalTopics * 100%`, background `var(--brand-navy)`
- Question text: `topic.question_pt` or `topic.question_en`, Georgia serif H2
- Options: full-width cards, one per option. On click: highlight selected, call `handleAnswer()`
- "Próxima" / "Next" button: enabled after selection, disabled before
- No candidate names, no source citations, no percentages

**States:**
- Loading: "Carregando quiz..." / "Loading quiz..."
- Empty (no topics with sufficient divergence): "Quiz indisponível no momento." / "Quiz temporarily unavailable."
- Error: standard error state

### 7. `site/src/components/QuizResultCard.jsx`

Result reveal — follows WF-06 (desktop) and WF-12 (mobile, result section).

**Reveal sequence (from spec lines 543-558):**
1. **Ranking:** list of candidates sorted by affinity, with `<progress>` bar in `CANDIDATE_COLORS[slug]`
2. **Radar chart:** `recharts RadarChart`, axes = answered topic IDs, top 3 candidates superimposed
3. **Textual explanation:** for top 3, natural language description of highest concordance and discordance topics
4. **Source reveal:** for each answered option, show `source_pt`/`source_en` and the candidate name. **This is the first moment `candidate_slug` is visible to the user.**
5. **Share button:** copies `window.location.origin + '/quiz/resultado?r=' + encodeResult(answers)` to clipboard

**MethodologyBadge:** rendered below the radar chart.

### 8. `site/src/components/ShareButton.jsx`

- Button with clipboard icon
- On click: `navigator.clipboard.writeText(shareUrl)`
- Success state: "Link copiado!" / "Link copied!" for 3 seconds
- Fallback: `prompt()` dialog if clipboard API unavailable

### 9. `site/src/pages/QuizPage.jsx` and `site/src/pages/QuizResult.jsx`

**`QuizPage.jsx`** (replacing Phase 04 placeholder):
- Route: `/quiz`
- `<Helmet>`: title "Quiz de Afinidade Política | Portal Eleições BR 2026", JSON-LD `Quiz`
- Renders `<QuizEngine />` or `<QuizResultCard />` based on `useQuiz().isComplete`

**`QuizResult.jsx`**:
- Route: `/quiz/resultado`
- On load: read `?r=` query param, `decodeResult(r)`, reconstruct results
- Renders `<QuizResultCard />` with reconstructed answers
- Handles invalid/missing `?r=` gracefully (redirect to `/quiz`)

### 10. i18n additions

**`site/src/locales/pt-BR/common.json`** — add `quiz` namespace keys:
```json
"quiz": {
  "title": "Quiz de Afinidade Política",
  "loading": "Carregando quiz...",
  "empty": "Quiz indisponível no momento.",
  "error": "Erro ao carregar quiz.",
  "question_of": "Pergunta {{current}} de {{total}}",
  "next": "Próxima",
  "see_result": "Ver resultado",
  "result_title": "Seu perfil político",
  "affinity_label": "Afinidade",
  "source_reveal_heading": "De onde vieram estas posições",
  "share": "Compartilhar resultado",
  "link_copied": "Link copiado!",
  "restart": "Refazer o quiz"
}
```

### 11. `docs/adr/005-quiz-affinity-system.md`

Document the quiz design decisions:
- Inverted framing (positions not candidates)
- Silent progressive funnel
- `confidence: low` / `unclear` positions omitted without notice
- Source reveal only on result page
- `?r=base64url` shareability without server state

## Constraints

- `candidate_slug` and `source_*` MUST NEVER appear in JSX rendered during the question phase
- Quiz works entirely client-side: no server calls, no analytics that reveal choices before result
- `quiz.json` is the only data source — no runtime AI calls from the frontend
- `recharts` is already in `package.json`
- `useQuiz` hook encapsulates all state — `QuizEngine` and `QuizResultCard` are pure presentational components consuming hook output

## Acceptance Criteria

- [ ] `python scripts/extract_quiz_positions.py` runs and writes valid `data/quiz.json`
- [ ] `data/quiz.json` contains at least 5 topics with at least 2 options each
- [ ] Quiz renders at `/quiz` with progress bar, question text, and options
- [ ] No candidate names or sources visible during question phase
- [ ] After last question, result card renders with ranking, radar chart, source reveal, share button
- [ ] Share URL (`?r=...`) correctly reconstructs the result on `/quiz/resultado`
- [ ] Language toggle switches quiz to en-US
- [ ] `MethodologyBadge` renders on result page
- [ ] `docs/adr/005-quiz-affinity-system.md` committed
- [ ] `npm run build` succeeds

## Commit & Push

After all deliverables are verified:

```
git add scripts/extract_quiz_positions.py .github/workflows/update-quiz.yml data/quiz.json site/src/utils/affinity.js site/src/utils/shareUrl.js site/src/hooks/useQuiz.js site/src/components/QuizEngine.jsx site/src/components/QuizResultCard.jsx site/src/components/ShareButton.jsx site/src/pages/QuizPage.jsx site/src/pages/QuizResult.jsx site/src/locales/ docs/adr/005-quiz-affinity-system.md
git commit -m "feat(phase-11): Political affinity quiz — extraction pipeline + full quiz UI

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Sentinel

When complete, create `plans/phase-11-arch.DONE`.
