# Phase 02 — AI Client

## Objective

Implement `scripts/ai_client.py` with multi-provider fallback chain, usage tracking, and two core functions: `summarize_article()` and `extract_candidate_position()`.

## Input Context

- `docs/adr/002-ai-providers.md` — Provider chain rationale and selection criteria
- `docs/prompt-eleicoes2026-v5.md` lines 53-175 — Full AI architecture spec
- `docs/schemas/articles.schema.json` — Article schema (summaries, sentiment, edit_history)
- `docs/schemas/types.ts` — TypeScript types for reference

## Deliverables

### 1. `scripts/ai_client.py`

Multi-provider fallback with usage tracking.

**Provider chain (in order):**

| Priority | Provider | Base URL | Model | Paid | Limits |
|----------|----------|----------|-------|------|--------|
| 1 | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `qwen/qwen3.5-397b-a17b` | No | Dev credits |
| 2 | OpenRouter | `https://openrouter.ai/api/v1` | `arcee-ai/trinity-large-preview:free` | No | 200/day, 20/min |
| 3 | Ollama Cloud | `https://ollama.com/v1` | `minimax-m2.5:cloud` | No | Hourly limits |
| 4 | Vertex AI | env `VERTEX_BASE_URL` | `google/gemini-2.5-flash-lite-001` | Yes | $10/mo |
| 5 | MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2-flash` | Yes | Pay-per-use |

**NVIDIA NIM model selection by task:**

| Task | Model |
|------|-------|
| summarization | `qwen/qwen3.5-397b-a17b` |
| sentiment | `minimaxai/minimax-m2.5` |
| multilingual | `moonshotai/kimi-k2.5` |
| quiz_extract | `qwen/qwen3-235b-a22b-thinking-2507` |

**Key API:**

```python
def call_with_fallback(system: str, user: str, max_tokens: int = 500) -> dict:
    """Try each provider in order, return first success.
    Returns: {"content": str, "provider": str, "model": str, "paid": bool}
    Raises RuntimeError if all providers fail.
    """

def summarize_article(title: str, content: str, language: str = "pt-BR") -> dict:
    """Generate summary + entities + sentiment in specified language.
    Returns parsed JSON with: summary, candidates_mentioned, topics,
    sentiment_per_candidate, _ai_provider, _language.
    On parse failure: returns fallback dict with _parse_error=True.
    """

def extract_candidate_position(candidate: str, topic_id: str, snippets: list[str]) -> dict:
    """Extract verifiable position from news snippets.
    Returns: position_pt, position_en, stance, confidence, best_source_snippet_index.
    Filters: only return high/medium confidence. low/unclear -> null positions.
    """
```

### 2. `data/ai_usage.json`

Usage tracker file. Format:

```json
{
  "nvidia_2026-03-15": 42,
  "openrouter_2026-03-15": 12,
  "vertex_2026-03-15": 3
}
```

Written by `_save_usage()`, read by `_load_usage()`. File created automatically on first call.

### 3. Unit Tests — `scripts/test_ai_client.py`

Test with mocked providers (no real API calls):

- `test_fallback_first_provider_succeeds` — First provider works, returns its result
- `test_fallback_skips_failed_provider` — First fails, second succeeds
- `test_fallback_all_fail_raises` — All providers fail, raises RuntimeError
- `test_openrouter_daily_limit_skipped` — OpenRouter at 200/day is skipped
- `test_usage_tracking_increments` — Usage file updated after successful call
- `test_summarize_article_parses_json` — Valid JSON from provider is parsed correctly
- `test_summarize_article_parse_error_fallback` — Invalid JSON returns fallback dict
- `test_extract_position_low_confidence_filtered` — low confidence returns null positions

### 4. Update `docs/adr/002-ai-providers.md`

Add "Implementation Notes" section documenting:
- Environment variables required (NVIDIA_API_KEY, OPENROUTER_API_KEY, etc.)
- Usage file location and format
- How to add a new provider to the chain

## Constraints

- All providers use `openai.OpenAI(api_key=key, base_url=url)` — no custom SDKs
- `id = sha256(url.encode())[:16]` for dedup (used by downstream scripts)
- Errors logged but never crash the pipeline
- `_save_usage()` creates parent directories automatically
- Environment variable names: `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`, `VERTEX_ACCESS_TOKEN`, `VERTEX_BASE_URL`, `XIAOMI_MIMO_API_KEY`

## Acceptance Criteria

- [ ] `ai_client.py` imports cleanly with `python -c "import scripts.ai_client"`
- [ ] All 8 unit tests pass with `python -m pytest scripts/test_ai_client.py -v`
- [ ] No hardcoded API keys anywhere
- [ ] Usage file is valid JSON after multiple calls
- [ ] `summarize_article()` returns bilingual summaries (pt-BR and en-US keys)
- [ ] `extract_candidate_position()` filters out low-confidence results

## Sentinel

When complete, create `plans/phase-02-arch.DONE`.
