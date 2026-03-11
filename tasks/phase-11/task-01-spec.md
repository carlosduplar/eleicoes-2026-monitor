# Phase 11 — Task 01 Spec (Political Affinity Quiz: Extraction Pipeline + Full React UI)

## Inputs and mandatory references

- Architecture input: `plans/phase-11-arch.md`
- Agent protocol: `docs/agent-protocol.md` (Tatico must provide detailed implementation spec plus edge-case tests)
- Project conventions: `.github/copilot-instructions.md`
- Wireframe reference — question: `docs/wireframes/WF-05-quiz-question-desktop.html` (open in browser)
- Wireframe reference — result: `docs/wireframes/WF-06-quiz-result-desktop.html` (open in browser)
- Wireframe reference — mobile: `docs/wireframes/WF-12-mobile-quiz.html` (open in browser)
- Schema: `docs/schemas/quiz.schema.json`
- TypeScript types: `docs/schemas/types.ts` (interfaces `Quiz`, `QuizTopic`, `QuizOption`, `AffinityResult`)
- Existing AI client: `scripts/ai_client.py` — function `extract_candidate_position(candidate, topic_id, snippets)`
- Existing hook: `site/src/hooks/useData.js` — `useData(filename)` returns `{ data, loading, error }`
- Candidate colors: `site/src/utils/candidateColors.js` — `CANDIDATE_COLORS` map
- Methodology badge: `site/src/components/MethodologyBadge.jsx`
- Existing placeholder: `site/src/pages/QuizPage.jsx` (to be replaced)
- Existing router: `site/src/App.jsx` — route `/quiz` already registered
- i18n files: `site/src/locales/pt-BR/common.json`, `site/src/locales/en-US/common.json`
- Data source: `data/articles.json` — articles with `candidates_mentioned`, `topics`, `summaries`

---

## 1) Files to create or modify (exact relative paths)

| # | Path | Action | Description |
|---|------|--------|-------------|
| 1 | `scripts/extract_quiz_positions.py` | **CREATE** | Daily extraction pipeline |
| 2 | `.github/workflows/update-quiz.yml` | **CREATE** | Daily cron + workflow_dispatch |
| 3 | `site/src/utils/affinity.js` | **CREATE** | Affinity calculation + early-exit logic |
| 4 | `site/src/utils/shareUrl.js` | **CREATE** | Base64url encode/decode for result sharing |
| 5 | `site/src/hooks/useQuiz.js` | **CREATE** | Custom hook managing quiz state |
| 6 | `site/src/components/QuizEngine.jsx` | **CREATE** | Quiz question UI (WF-05, WF-12) |
| 7 | `site/src/components/QuizResultCard.jsx` | **CREATE** | Result reveal UI (WF-06, WF-12) |
| 8 | `site/src/components/ShareButton.jsx` | **CREATE** | Clipboard share button |
| 9 | `site/src/pages/QuizPage.jsx` | **MODIFY** | Replace placeholder with quiz funnel |
| 10 | `site/src/pages/QuizResult.jsx` | **CREATE** | Shared result page `/quiz/resultado` |
| 11 | `site/src/App.jsx` | **MODIFY** | Add `/quiz/resultado` route, import `QuizResult` |
| 12 | `site/src/main.jsx` | **NO CHANGE** | i18n uses `common` namespace (quiz keys go in common.json) |
| 13 | `site/src/locales/pt-BR/common.json` | **MODIFY** | Add `quiz.*` i18n keys |
| 14 | `site/src/locales/en-US/common.json` | **MODIFY** | Add `quiz.*` i18n keys |
| 15 | `site/src/styles.css` | **MODIFY** | Add quiz-specific CSS classes |
| 16 | `docs/adr/005-quiz-affinity-system.md` | **CREATE** | ADR 005 |
| 17 | `data/quiz.json` | **GENERATED** | Output of extraction pipeline |

No new npm or pip dependencies. `recharts` (^2.12.7) and `openai` are already installed.

---

## 2) Function signatures and types per file

### 2.1 `scripts/extract_quiz_positions.py`

```python
"""Daily quiz position extraction pipeline — Phase 11."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger: logging.Logger

ROOT_DIR: Path  # Path(__file__).resolve().parents[1]
ARTICLES_FILE: Path  # ROOT_DIR / "data" / "articles.json"
QUIZ_FILE: Path  # ROOT_DIR / "data" / "quiz.json"

CANDIDATES: list[str]
# Value: ["lula","flavio-bolsonaro","tarcisio","caiado","zema",
#         "ratinho-jr","eduardo-leite","aldo-rebelo","renan-santos"]

QUIZ_TOPICS: list[str]
# Value: all 16 TopicId values from docs/schemas/types.ts

STANCE_MAP: dict[str, int | None]
# {"favor": 2, "neutral": 0, "against": -2, "unclear": None}

OPTION_LETTERS: list[str]
# ["opt_a","opt_b","opt_c","opt_d","opt_e","opt_f"]

def load_articles() -> list[dict]:
    """Load data/articles.json. Return [] on file-not-found or parse error."""
    ...

def filter_snippets(articles: list[dict], candidate: str, topic: str) -> list[str]:
    """Return up to 12 most recent article snippets (title + summary pt-BR)
    where candidate is in candidates_mentioned AND topic is in topics.
    Sort by published_at descending. Each snippet: '{title}. {summaries.pt-BR}'."""
    ...

def divergence_score(positions: list[dict]) -> float:
    """Compute (max_weight - min_weight) / 4.0 for positions with
    confidence in ('high','medium') and stance != 'unclear'.
    Return 0.0 if fewer than 2 valid stances."""
    ...

def select_quiz_topics(
    all_positions: dict[str, dict[str, dict]],
    # outer key: topic_id, inner key: candidate_slug -> position dict
) -> list[str]:
    """Select 10-15 topics with highest divergence_score.
    Must have >= 2 options with high/medium confidence.
    Return list of topic_ids sorted by divergence descending."""
    ...

def build_question_text(topic_id: str) -> tuple[str, str]:
    """Return (question_pt, question_en) for a topic.
    Use a static template dict mapping topic_id -> bilingual question text.
    Fallback: generic 'Qual sua posicao sobre {topic}?'."""
    ...

def build_options(
    topic_id: str,
    positions: dict[str, dict],  # candidate_slug -> position dict
) -> list[dict]:
    """Build options array for quiz.json.
    Only include candidates with confidence in ('high','medium') and stance != 'unclear'.
    Assign id from OPTION_LETTERS sequentially.
    Each option: {id, text_pt, text_en, weight, candidate_slug, source_pt, source_en, confidence}.
    weight = STANCE_MAP[stance]. text_pt = position_pt. text_en = position_en.
    source_pt/source_en: brief attribution string from best_source_snippet_index."""
    ...

def main() -> None:
    """Orchestrator:
    1. load_articles()
    2. For each topic in QUIZ_TOPICS, for each candidate in CANDIDATES:
       - snippets = filter_snippets(articles, candidate, topic)
       - position = ai_client.extract_candidate_position(candidate, topic, snippets)
       - Store in all_positions[topic][candidate] = position
       - On AI error: log warning, continue (keep existing data if any)
    3. selected = select_quiz_topics(all_positions)
    4. Build quiz dict conforming to quiz.schema.json
    5. Validate against schema with jsonschema
    6. Write data/quiz.json (atomic write via temp file + rename)
    7. Print summary line
    """
    ...

if __name__ == "__main__":
    main()
```

**Idempotency:** Same articles + same AI responses = same quiz.json. The script overwrites the file atomically.

**Error handling:** Each `extract_candidate_position` call is wrapped in `try/except Exception`. On failure: `logger.warning(...)`, skip that candidate/topic, continue. AI errors never halt the pipeline.

**Schema validation:** After building the quiz dict, validate against `docs/schemas/quiz.schema.json` using `jsonschema.validate()`. On validation failure: log error, do NOT write file, exit with code 1.

### 2.2 `.github/workflows/update-quiz.yml`

```yaml
name: Update Quiz Positions
on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch:
jobs:
  quiz:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
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

Copy this verbatim. No modifications.

### 2.3 `site/src/utils/affinity.js`

```javascript
// JSDoc types only — no TypeScript, no 'any'

/**
 * @typedef {Object} AffinityResult
 * @property {string} slug — CandidateSlug
 * @property {number} affinity — 0-100
 * @property {Object.<string, number>} byTopic — topic_id -> similarity 0.0-1.0
 */

/**
 * Calculate affinity scores for all candidates based on user answers.
 *
 * Algorithm (from spec lines 484-538):
 * For each candidate, for each answered topic:
 *   similarity = 1 - |user_weight - candidate_weight| / 4
 * affinity = mean(similarities) * 100
 *
 * @param {Object.<string, {optionId: string, weight: number}>} answers
 *   Keys are topic IDs. Each value has the optionId chosen and its weight.
 * @param {Object} quizData — full quiz.json data
 * @returns {AffinityResult[]} sorted descending by affinity
 */
export function calculateAffinity(answers, quizData) { ... }

/**
 * Determine if early-exit is possible (margin already decisive).
 *
 * @param {AffinityResult[]} results — current sorted results
 * @param {number} answeredCount — questions answered so far
 * @param {number} totalQuestions — total questions in quiz
 * @returns {boolean} true if quiz can end early
 */
export function shouldContinueQuiz(results, answeredCount, totalQuestions) { ... }
```

**`calculateAffinity` implementation details:**
1. Collect all unique `candidate_slug` values across all topics in `quizData.topics`.
2. For each candidate, iterate over each `topicId` in `answers`:
   - Find the option in `quizData.topics[topicId].options` where `option.candidate_slug === candidate`.
   - If found: `similarity = 1 - Math.abs(answers[topicId].weight - option.weight) / 4`.
   - If not found: skip topic for this candidate.
3. `affinity = (sum of similarities / count of matched topics) * 100`. If count is 0, affinity = 0.
4. Build `byTopic` record from individual similarities.
5. Return array sorted descending by `affinity`.

**`shouldContinueQuiz` implementation details:**
- Return `false` (quiz CAN stop) when: `answeredCount >= Math.ceil(totalQuestions * 0.6)` AND gap between 1st and 2nd candidate is >= 20 points.
- Otherwise return `true` (continue).

### 2.4 `site/src/utils/shareUrl.js`

```javascript
/**
 * Encode answers object to URL-safe base64 string.
 * @param {Object} answers — {topicId: {optionId, weight}}
 * @returns {string} base64url-encoded string
 */
export function encodeResult(answers) { ... }

/**
 * Decode URL-safe base64 string back to answers object.
 * @param {string} r — base64url-encoded string
 * @returns {Object} answers — {topicId: {optionId, weight}}
 * @throws {Error} on invalid input
 */
export function decodeResult(r) { ... }
```

**Implementation:**
- `encodeResult`: `btoa(JSON.stringify(answers)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'')`
- `decodeResult`: `JSON.parse(atob(r.replace(/-/g,'+').replace(/_/g,'/')))`

### 2.5 `site/src/hooks/useQuiz.js`

```javascript
import { useState, useMemo, useCallback } from 'react';
import { useData } from './useData';
import { calculateAffinity } from '../utils/affinity';

/**
 * Custom hook managing full quiz lifecycle.
 *
 * @returns {{
 *   quizData: Object|null,
 *   loading: boolean,
 *   error: Error|null,
 *   answers: Object.<string, {optionId: string, weight: number}>,
 *   currentTopicIndex: number,
 *   isComplete: boolean,
 *   results: AffinityResult[]|null,
 *   currentTopic: Object|null,
 *   totalTopics: number,
 *   handleAnswer: (topicId: string, optionId: string, weight: number) => void,
 *   reset: () => void
 * }}
 */
export function useQuiz() { ... }
```

**State variables:**
- `quizData` — from `useData('quiz')`, returns `{ data, loading, error }`
- `answers` — `useState({})` — `{[topicId]: {optionId, weight}}`
- `currentTopicIndex` — `useState(0)`
- `isComplete` — `useState(false)`

**Derived values (useMemo):**
- `orderedTopics` — `quizData?.ordered_topics ?? []`
- `totalTopics` — `orderedTopics.length`
- `currentTopic` — `quizData?.topics?.[orderedTopics[currentTopicIndex]] ?? null`
- `results` — computed via `calculateAffinity(answers, quizData)` only when `isComplete` is true

**`handleAnswer(topicId, optionId, weight)`:**
1. Set `answers[topicId] = { optionId, weight }`
2. If `currentTopicIndex + 1 >= totalTopics`: set `isComplete = true`
3. Else: increment `currentTopicIndex`

**`reset()`:**
- Set `answers = {}`, `currentTopicIndex = 0`, `isComplete = false`

### 2.6 `site/src/components/QuizEngine.jsx`

```jsx
import { useTranslation } from 'react-i18next';

/**
 * Quiz question UI — pure presentational component.
 * Follows WF-05 (desktop) and WF-12 (mobile 390px).
 *
 * CRITICAL: NEVER render option.candidate_slug or option.source_* during questions.
 *
 * @param {{
 *   topic: QuizTopic,
 *   topicId: string,
 *   currentIndex: number,
 *   totalTopics: number,
 *   onAnswer: (topicId: string, optionId: string, weight: number) => void
 * }} props
 */
function QuizEngine({ topic, topicId, currentIndex, totalTopics, onAnswer }) { ... }
export default QuizEngine;
```

**Render structure (follow WF-05 wireframe):**
1. Progress bar: `<div className="quiz-progress">` with inner `<div>` at `width: ${(currentIndex + 1) / totalTopics * 100}%`, background `var(--brand-navy)`
2. Question counter: `t('quiz.question_of', { current: currentIndex + 1, total: totalTopics })`
3. Question text: `<h2 className="quiz-question">` rendering `topic.question_pt` or `topic.question_en` depending on `i18n.language`
4. Options list: `<div className="quiz-options">` mapping `topic.options` to clickable cards
   - Each card: `<button className="quiz-option-card">` showing `option.text_pt` or `option.text_en`
   - On click: internal state tracks `selectedOptionId`; highlights the selected card with `.quiz-option-card--selected`
   - **MUST NOT** render `option.candidate_slug`, `option.source_pt`, `option.source_en`, `option.weight`, or `option.confidence`
5. "Next" button: `<button className="quiz-next-btn" disabled={!selectedOptionId}>` with text `t('quiz.next')` (or `t('quiz.see_result')` on last question)
   - On click: call `onAnswer(topicId, selectedOptionId, selectedWeight)`, then reset `selectedOptionId` to null

**States:**
- Loading: rendered by parent (QuizPage), not by QuizEngine
- Empty: rendered by parent
- Error: rendered by parent

### 2.7 `site/src/components/QuizResultCard.jsx`

```jsx
import { useTranslation } from 'react-i18next';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts';
import { CANDIDATE_COLORS } from '../utils/candidateColors';
import MethodologyBadge from './MethodologyBadge';
import ShareButton from './ShareButton';

/**
 * Result reveal — pure presentational.
 * Follows WF-06 (desktop) and WF-12 (mobile result section).
 *
 * @param {{
 *   results: AffinityResult[],
 *   answers: Object.<string, {optionId: string, weight: number}>,
 *   quizData: Object,
 *   onRestart: () => void
 * }} props
 */
function QuizResultCard({ results, answers, quizData, onRestart }) { ... }
export default QuizResultCard;
```

**Render structure (follow WF-06 wireframe, reveal sequence from spec):**

1. **Title:** `<h2>{t('quiz.result_title')}</h2>`

2. **Ranking section:** `<div className="quiz-ranking">`
   - For each candidate in `results` (sorted by affinity descending):
     - `<div className="quiz-ranking-item">`
       - Candidate name (from a name lookup or slug display)
       - `<progress>` bar with `value={result.affinity}` `max={100}`, colored with `CANDIDATE_COLORS[result.slug]`
       - Percentage label: `${Math.round(result.affinity)}%`
       - Label: `t('quiz.affinity_label')`

3. **Radar chart:** `<div className="quiz-radar">`
   - `<ResponsiveContainer width="100%" height={350}>`
   - `<RadarChart>` with `<PolarGrid>` and `<PolarAngleAxis dataKey="topic">`
   - Data: one entry per answered topic, value = similarity score (0-1) for that topic
   - Superimpose top 3 candidates as `<Radar>` elements, each with `stroke={CANDIDATE_COLORS[slug]}` and `fill` with opacity 0.15
   - **`<MethodologyBadge />`** rendered below the radar chart

4. **Source reveal:** `<div className="quiz-sources">`
   - `<h3>{t('quiz.source_reveal_heading')}</h3>`
   - For each answered topic (use `quizData.ordered_topics` filtered by answered):
     - Show question text
     - Show user's chosen option text
     - **NOW reveal:** candidate name (`option.candidate_slug`) and source (`option.source_pt` / `option.source_en`)
     - This is the FIRST and ONLY place `candidate_slug` and `source_*` appear in quiz UI

5. **Share button:** `<ShareButton answers={answers} />`

6. **Restart:** `<button className="quiz-restart-btn" onClick={onRestart}>{t('quiz.restart')}</button>`

### 2.8 `site/src/components/ShareButton.jsx`

```jsx
import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { encodeResult } from '../utils/shareUrl';

/**
 * Share button with clipboard copy.
 *
 * @param {{ answers: Object }} props
 */
function ShareButton({ answers }) { ... }
export default ShareButton;
```

**Behavior:**
1. Compute `shareUrl = window.location.origin + '/quiz/resultado?r=' + encodeResult(answers)`
2. On click: try `navigator.clipboard.writeText(shareUrl)`
   - On success: show `t('quiz.link_copied')` for 3 seconds (via `useState` + `setTimeout`)
   - On failure (clipboard API unavailable): `window.prompt(t('quiz.share'), shareUrl)`

### 2.9 `site/src/pages/QuizPage.jsx` (MODIFY — replace placeholder)

```jsx
import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import QuizEngine from '../components/QuizEngine';
import QuizResultCard from '../components/QuizResultCard';
import { useQuiz } from '../hooks/useQuiz';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

/**
 * Route: /quiz
 * Renders QuizEngine during questions, QuizResultCard when complete.
 */
function QuizPage() { ... }
export default QuizPage;
```

**Behavior:**
1. Call `useQuiz()` to get all quiz state
2. `<Helmet>` with title `t('quiz.title') + ' | ' + t('brand')` and JSON-LD `Quiz` schema
3. If `loading`: render `<p>{t('quiz.loading')}</p>`
4. If `error`: render `<p className="error-state">{t('quiz.error')}</p>`
5. If `quizData` has no topics or `orderedTopics.length === 0`: render `<p>{t('quiz.empty')}</p>`
6. If `isComplete`: render `<QuizResultCard results={results} answers={answers} quizData={quizData} onRestart={reset} />`
7. Else: render `<QuizEngine topic={currentTopic} topicId={orderedTopics[currentTopicIndex]} currentIndex={currentTopicIndex} totalTopics={totalTopics} onAnswer={handleAnswer} />`

### 2.10 `site/src/pages/QuizResult.jsx` (CREATE)

```jsx
import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import * as ReactHelmetAsync from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { useData } from '../hooks/useData';
import { decodeResult } from '../utils/shareUrl';
import { calculateAffinity } from '../utils/affinity';
import QuizResultCard from '../components/QuizResultCard';

const Helmet = ReactHelmetAsync.Helmet || ReactHelmetAsync.default?.Helmet;

/**
 * Route: /quiz/resultado
 * Reconstructs quiz results from ?r= query param.
 */
function QuizResult() { ... }
export default QuizResult;
```

**Behavior:**
1. Read `?r=` from `useSearchParams()`
2. If no `r` param or `decodeResult(r)` throws: `navigate('/quiz', { replace: true })`
3. Load quiz data via `useData('quiz')`
4. Once loaded: `results = calculateAffinity(decodedAnswers, quizData)`
5. Render `<QuizResultCard results={results} answers={decodedAnswers} quizData={quizData} onRestart={() => navigate('/quiz')} />`
6. `<Helmet>` with appropriate title

### 2.11 `site/src/App.jsx` (MODIFY)

**Changes:**
1. Add import: `import QuizResult from './pages/QuizResult';`
2. Add route inside the children array: `{ path: 'quiz/resultado', element: <QuizResult /> }`
   - Must be placed BEFORE the `{ path: 'quiz', ... }` route to ensure proper matching.

### 2.12 `site/src/locales/pt-BR/common.json` (MODIFY)

Add `"quiz"` key at root level:

```json
"quiz": {
  "title": "Quiz de Afinidade Politica",
  "loading": "Carregando quiz...",
  "empty": "Quiz indisponivel no momento.",
  "error": "Erro ao carregar quiz.",
  "question_of": "Pergunta {{current}} de {{total}}",
  "next": "Proxima",
  "see_result": "Ver resultado",
  "result_title": "Seu perfil politico",
  "affinity_label": "Afinidade",
  "source_reveal_heading": "De onde vieram estas posicoes",
  "share": "Compartilhar resultado",
  "link_copied": "Link copiado!",
  "restart": "Refazer o quiz"
}
```

**NOTE:** Use proper Portuguese diacritics in the actual implementation: "Politica" -> "Politica", "indisponivel" -> "indisponivel", "Proxima" -> "Proxima", "posicoes" -> "posicoes". Copy exact text from `plans/phase-11-arch.md` lines 192-207.

### 2.13 `site/src/locales/en-US/common.json` (MODIFY)

Add `"quiz"` key at root level:

```json
"quiz": {
  "title": "Political Affinity Quiz",
  "loading": "Loading quiz...",
  "empty": "Quiz temporarily unavailable.",
  "error": "Error loading quiz.",
  "question_of": "Question {{current}} of {{total}}",
  "next": "Next",
  "see_result": "See result",
  "result_title": "Your political profile",
  "affinity_label": "Affinity",
  "source_reveal_heading": "Where these positions came from",
  "share": "Share result",
  "link_copied": "Link copied!",
  "restart": "Retake the quiz"
}
```

### 2.14 `site/src/styles.css` (MODIFY)

Append quiz-specific CSS classes at end of file. Required classes (follow wireframe design tokens):

```css
/* Quiz — Phase 11 */
.quiz-progress { ... }
.quiz-progress-bar { ... }     /* background: var(--brand-navy) */
.quiz-question { ... }         /* font-family: Georgia, serif */
.quiz-counter { ... }
.quiz-options { ... }
.quiz-option-card { ... }
.quiz-option-card--selected { ... }  /* border-color: var(--brand-navy) */
.quiz-next-btn { ... }
.quiz-next-btn:disabled { ... }
.quiz-ranking { ... }
.quiz-ranking-item { ... }
.quiz-radar { ... }
.quiz-sources { ... }
.quiz-source-item { ... }
.quiz-restart-btn { ... }
.quiz-share-btn { ... }
.quiz-share-btn--copied { ... }
```

Design tokens: `--brand-navy`, `--brand-gold`, `--brand-bg`, `--brand-surface`, `--text-primary`, `--text-secondary`, `--border`. All already defined in `:root`.

### 2.15 `docs/adr/005-quiz-affinity-system.md` (CREATE)

```markdown
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
```

---

## 3) Data contract notes

### `data/quiz.json` must satisfy `docs/schemas/quiz.schema.json`

| Field | Schema requirement | Producer | Consumer |
|-------|-------------------|----------|----------|
| `generated_at` | `string`, `format: date-time`, **required** | `extract_quiz_positions.py` | `QuizResultCard.jsx` (display) |
| `ordered_topics` | `array` of `string`, 1-15 items, **required** | `extract_quiz_positions.py` (sorted by divergence desc) | `useQuiz.js` (iteration order) |
| `topics` | `object`, values are `QuizTopic`, **required** | `extract_quiz_positions.py` | `useQuiz.js`, `QuizEngine.jsx`, `QuizResultCard.jsx` |
| `topics.*.divergence_score` | `number`, 0-1, **required** | `divergence_score()` | `select_quiz_topics()` (selection) |
| `topics.*.question_pt` | `string`, **required** | `build_question_text()` | `QuizEngine.jsx` (when lang=pt-BR) |
| `topics.*.question_en` | `string`, **required** | `build_question_text()` | `QuizEngine.jsx` (when lang=en-US) |
| `topics.*.options` | array of `QuizOption`, 2-6 items, **required** | `build_options()` | `QuizEngine.jsx` (render), `affinity.js` (calculate) |
| `options.*.id` | `string`, pattern `^opt_[a-z]$`, **required** | `build_options()` | `useQuiz.js` (answer tracking) |
| `options.*.text_pt` | `string`, **required** | AI extraction (`position_pt`) | `QuizEngine.jsx` (display, lang=pt-BR) |
| `options.*.text_en` | `string`, **required** | AI extraction (`position_en`) | `QuizEngine.jsx` (display, lang=en-US) |
| `options.*.weight` | `integer`, -2 to 2, **required** | `STANCE_MAP[stance]` | `affinity.js` (calculation) |
| `options.*.candidate_slug` | `string`, **required** | Pipeline | `QuizResultCard.jsx` ONLY (source reveal) |
| `options.*.source_pt` | `string` (optional in schema) | Pipeline | `QuizResultCard.jsx` ONLY (source reveal) |
| `options.*.source_en` | `string` (optional in schema) | Pipeline | `QuizResultCard.jsx` ONLY (source reveal) |
| `options.*.confidence` | `enum: ["high","medium"]`, **required** | AI extraction | Pipeline (filtering only) |

### TypeScript type alignment (`docs/schemas/types.ts`)

- `Quiz` interface: consumed by `useData('quiz')` return type
- `QuizTopic` interface: consumed by `QuizEngine` prop `topic`
- `QuizOption` interface: consumed by `QuizEngine` (render text only), `QuizResultCard` (full reveal)
- `AffinityResult` interface: consumed by `QuizResultCard` prop `results`
- `CandidateSlug` type: used for `CANDIDATE_COLORS` lookup in `QuizResultCard`
- `TopicId` type: used as keys in `answers` and `quizData.topics`

### Security invariant

`candidate_slug`, `source_pt`, `source_en` MUST NOT be:
- Rendered in any JSX during the question phase (`QuizEngine.jsx`)
- Logged to console during the question phase
- Included in any HTML attribute or `data-*` attribute during questions
- Accessible via DOM inspection during questions (do not pass these fields to QuizEngine at all; only pass `text_pt`/`text_en` and `id`/`weight`)

**Implementation approach:** In `QuizEngine.jsx`, destructure each option to extract ONLY `{ id, text_pt, text_en }` before rendering. Do NOT spread the full option object.

---

## 4) Step-by-step implementation order (dependency-aware)

### Step 1: ADR 005
- Create `docs/adr/005-quiz-affinity-system.md`
- No dependencies on any other file

### Step 2: i18n keys
- Modify `site/src/locales/pt-BR/common.json` — add `quiz.*` namespace
- Modify `site/src/locales/en-US/common.json` — add `quiz.*` namespace
- No dependencies (main.jsx already loads `common` namespace)

### Step 3: Python extraction pipeline
- Create `scripts/extract_quiz_positions.py`
- Dependencies: `scripts/ai_client.py` (existing), `data/articles.json` (existing), `docs/schemas/quiz.schema.json` (existing)
- Run: `python scripts/extract_quiz_positions.py`
- Output: `data/quiz.json`
- **Verify:** `python -c "import json,jsonschema; d=json.load(open('data/quiz.json')); s=json.load(open('docs/schemas/quiz.schema.json')); jsonschema.validate(d,s); print(f'OK: {len(d[\"ordered_topics\"])} topics')"` (in repo root)

### Step 4: GitHub Actions workflow
- Create `.github/workflows/update-quiz.yml`
- Dependencies: Step 3 (script must exist)
- Verify: YAML syntax only (no live test needed)

### Step 5: Utility — shareUrl.js
- Create `site/src/utils/shareUrl.js`
- No dependencies on other new files

### Step 6: Utility — affinity.js
- Create `site/src/utils/affinity.js`
- No dependencies on other new files

### Step 7: Hook — useQuiz.js
- Create `site/src/hooks/useQuiz.js`
- Dependencies: Step 6 (`affinity.js`), existing `useData.js`

### Step 8: Component — ShareButton.jsx
- Create `site/src/components/ShareButton.jsx`
- Dependencies: Step 5 (`shareUrl.js`), Step 2 (i18n keys)

### Step 9: Component — QuizEngine.jsx
- Create `site/src/components/QuizEngine.jsx`
- Dependencies: Step 2 (i18n keys)
- **CRITICAL:** Do NOT import or reference `candidateColors.js` or `MethodologyBadge.jsx` in this component

### Step 10: Component — QuizResultCard.jsx
- Create `site/src/components/QuizResultCard.jsx`
- Dependencies: Step 6 (`affinity.js`), Step 8 (`ShareButton.jsx`), Step 2 (i18n keys), existing `MethodologyBadge.jsx`, existing `candidateColors.js`

### Step 11: CSS additions
- Modify `site/src/styles.css` — append quiz classes
- Dependencies: Steps 9-10 (class names must match component JSX)

### Step 12: Page — QuizPage.jsx (replace placeholder)
- Modify `site/src/pages/QuizPage.jsx`
- Dependencies: Step 7 (`useQuiz.js`), Step 9 (`QuizEngine.jsx`), Step 10 (`QuizResultCard.jsx`)

### Step 13: Page — QuizResult.jsx
- Create `site/src/pages/QuizResult.jsx`
- Dependencies: Step 5 (`shareUrl.js`), Step 6 (`affinity.js`), Step 10 (`QuizResultCard.jsx`), existing `useData.js`

### Step 14: Router update
- Modify `site/src/App.jsx`
- Dependencies: Step 13 (`QuizResult.jsx`)
- Add import + route for `/quiz/resultado`

### Step 15: Build verification
- Run `npm run build` from `site/` directory
- Must succeed with zero errors

---

## 5) Test and verification commands (PowerShell 7)

```powershell
# --- Python pipeline ---

# 5.1 Run the extraction pipeline (requires API keys in env)
Set-Location C:\projects\eleicoes-2026-monitor
python scripts/extract_quiz_positions.py

# 5.2 Validate quiz.json against schema
python -c @"
import json, jsonschema, sys
quiz = json.load(open('data/quiz.json', encoding='utf-8'))
schema = json.load(open('docs/schemas/quiz.schema.json', encoding='utf-8'))
jsonschema.validate(quiz, schema)
topics = quiz.get('ordered_topics', [])
print(f'Schema valid. Topics: {len(topics)}')
assert len(topics) >= 5, f'Expected >= 5 topics, got {len(topics)}'
for tid in topics:
    opts = quiz['topics'][tid]['options']
    assert len(opts) >= 2, f'Topic {tid} has {len(opts)} options, need >= 2'
    for opt in opts:
        assert 'candidate_slug' in opt, f'Missing candidate_slug in {tid}'
        assert opt['confidence'] in ('high','medium'), f'Bad confidence in {tid}'
print('All assertions passed.')
"@

# 5.3 Verify idempotency (run twice, compare)
python scripts/extract_quiz_positions.py
$hash1 = (Get-FileHash data/quiz.json -Algorithm SHA256).Hash
python scripts/extract_quiz_positions.py
$hash2 = (Get-FileHash data/quiz.json -Algorithm SHA256).Hash
if ($hash1 -ne $hash2) { Write-Warning "Idempotency check: hashes differ (may be OK if AI responses vary)" }
else { Write-Host "Idempotency OK: identical output" }

# --- Frontend build ---

# 5.4 Build the site
Set-Location C:\projects\eleicoes-2026-monitor\site
npm run build

# 5.5 Verify quiz route was generated
if (Test-Path dist/quiz/index.html) { Write-Host "OK: /quiz route exists" }
else { Write-Error "/quiz route missing from build output" }

# 5.6 Verify quiz/resultado route was generated
if (Test-Path dist/quiz/resultado/index.html) { Write-Host "OK: /quiz/resultado route exists" }
else { Write-Error "/quiz/resultado route missing from build output" }

# 5.7 Check that candidate_slug does NOT appear in QuizEngine.jsx source
Set-Location C:\projects\eleicoes-2026-monitor
$matches = Select-String -Path site/src/components/QuizEngine.jsx -Pattern 'candidate_slug|source_pt|source_en'
if ($matches) {
    Write-Error "SECURITY: QuizEngine.jsx must NOT reference candidate_slug or source_*"
    $matches | ForEach-Object { Write-Error $_.Line }
} else {
    Write-Host "OK: QuizEngine.jsx does not reference hidden fields"
}

# 5.8 Verify MethodologyBadge is used in QuizResultCard
$badge = Select-String -Path site/src/components/QuizResultCard.jsx -Pattern 'MethodologyBadge'
if ($badge) { Write-Host "OK: MethodologyBadge present in QuizResultCard" }
else { Write-Error "MethodologyBadge missing from QuizResultCard" }

# 5.9 Verify i18n keys exist
$ptJson = Get-Content site/src/locales/pt-BR/common.json -Raw | ConvertFrom-Json
$enJson = Get-Content site/src/locales/en-US/common.json -Raw | ConvertFrom-Json
if ($ptJson.quiz -and $enJson.quiz) { Write-Host "OK: quiz i18n keys present in both locales" }
else { Write-Error "Missing quiz i18n keys" }

# 5.10 Verify ADR 005 exists
if (Test-Path docs/adr/005-quiz-affinity-system.md) { Write-Host "OK: ADR 005 exists" }
else { Write-Error "ADR 005 missing" }

# 5.11 Verify GitHub Actions workflow
if (Test-Path .github/workflows/update-quiz.yml) { Write-Host "OK: update-quiz.yml exists" }
else { Write-Error "update-quiz.yml missing" }

# 5.12 Verify workflow YAML is valid (basic check)
python -c "import yaml; yaml.safe_load(open('.github/workflows/update-quiz.yml'))" 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host "OK: YAML syntax valid" }

# 5.13 Preview site (manual verification)
# Set-Location site && npm run preview
# Open http://localhost:4173/quiz in browser
# 1. Verify progress bar renders
# 2. Verify question text renders (no candidate names visible)
# 3. Complete quiz, verify result card shows ranking + radar + sources
# 4. Verify share button copies URL
# 5. Open copied URL, verify result reconstructs
# 6. Toggle language, verify translations switch
```

---

## 6) Git commit message

```
feat(phase-11): political affinity quiz — extraction pipeline + full quiz UI

- Add scripts/extract_quiz_positions.py (daily AI position extraction)
- Add .github/workflows/update-quiz.yml (daily cron at 03:00 UTC)
- Add site/src/utils/affinity.js (calculateAffinity + shouldContinueQuiz)
- Add site/src/utils/shareUrl.js (base64url encode/decode)
- Add site/src/hooks/useQuiz.js (quiz state management hook)
- Add site/src/components/QuizEngine.jsx (question funnel, WF-05/WF-12)
- Add site/src/components/QuizResultCard.jsx (result reveal, WF-06/WF-12)
- Add site/src/components/ShareButton.jsx (clipboard share)
- Replace site/src/pages/QuizPage.jsx placeholder with full quiz
- Add site/src/pages/QuizResult.jsx (shared result page)
- Add /quiz/resultado route in App.jsx
- Add quiz i18n keys (pt-BR + en-US)
- Add quiz CSS classes in styles.css
- Add docs/adr/005-quiz-affinity-system.md
- Generate data/quiz.json

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## 7) Completion sentinel command

```powershell
New-Item -Path plans/phase-11-arch.DONE -ItemType File -Force
```

---

## Edge-case test scenarios

### Python pipeline edge cases
1. **Empty articles.json:** Script should produce quiz.json with 0 topics and `ordered_topics: []`. Schema validation will fail (minItems: 1), so script should log error and preserve existing quiz.json if present.
2. **All AI calls fail:** Every `extract_candidate_position` returns low-confidence/unclear. No topics selected. Same behavior as empty articles.
3. **Single candidate per topic:** Topic gets divergence_score 0.0 and is excluded from selection (needs >= 2 options).
4. **Duplicate stances:** Two candidates with same stance on a topic — both included as separate options with same weight.
5. **articles.json missing `summaries.pt-BR`:** `filter_snippets` should handle missing summaries gracefully (skip article or use title only).

### Frontend edge cases
1. **quiz.json fetch fails (404 or network error):** QuizPage renders error state.
2. **quiz.json has 0 topics:** QuizPage renders empty state.
3. **User reloads mid-quiz:** State resets (acceptable — no persistence requirement).
4. **Invalid `?r=` param on QuizResult:** Redirect to `/quiz`.
5. **`?r=` param with answers for topics no longer in quiz:** `calculateAffinity` should skip unknown topics gracefully.
6. **Clipboard API unavailable:** ShareButton falls back to `window.prompt()`.
7. **Language toggle mid-quiz:** Questions and options switch language without losing progress (i18n reads `topic.question_pt`/`question_en` based on current `i18n.language`).
8. **Mobile viewport (390px):** Layout must be usable per WF-12 wireframe.
