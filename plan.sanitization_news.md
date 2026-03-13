# Sanitization Plan: Portal Eleicoes BR 2026

## Problem Statement

The article pipeline has three confirmed data-quality failures:

1. **Broken `relevance_score`** — 100% of 500 articles show 0.0 because the LLM prompt in `ai_client.summarize_article()` never asks for it, and `summarize.py:_ensure_article_defaults()` defaults it to 0.0.
2. **Massive irrelevant content** — 82.2% of articles (411/500) have empty `candidates_mentioned`. The keyword-based gate `_is_elections_relevant()` in `summarize.py` catches some off-topic content but misses articles that are generically political but not election-related (e.g., STF judiciary cases, agro exports, US consumer sentiment).
3. **Cross-source duplicates** — `narrative_cluster_id` is null for 100% of articles. The `deduplicate_narratives.py` script exists but only operates on validated articles from the last 24 hours via title-only TF-IDF; it apparently hasn't clustered anything in the current dataset. At least 15 same-story duplicates were detected by simple title similarity.

**Dual mandate**: Scope A (retroactive one-time batch cleanup) and Scope B (permanent ingestion guard). Scope B is the primary deliverable.

## Root Cause Analysis

### Why `relevance_score` is always 0.0

```
collect_rss.py → sets relevance_score: None
summarize.py:_ensure_article_defaults() → coerces None to 0.0
ai_client.summarize_article() → prompt does NOT ask LLM for relevance_score
→ No code path EVER computes a real relevance_score
```

### Why irrelevant articles slip through

The existing gate `_is_elections_relevant()` in `summarize.py` (lines 446-486) checks for election keywords, candidate names, and Brazil context. However:
- It only checks the first 800 chars of normalized content
- It passes any article with >= 1 candidate keyword mention even if the article is about sports/entertainment with a passing political reference
- It does NOT check `candidates_mentioned` (which is empty at gate time since the LLM hasn't run yet)
- Articles from `party` and `institutional` sources only need 1 high-signal keyword to pass
- There is no secondary validation AFTER the LLM returns results (e.g., checking if `candidates_mentioned` came back empty)

### Why deduplication doesn't work

- `deduplicate_narratives.py` only processes articles with `status == "validated"` from the last 24 hours
- It uses title-only TF-IDF (not content)
- It is called from `curate.py` workflow, which runs hourly but has a 90-minute skip gate
- The 24-hour window means articles validated in batches across multiple collection cycles may miss each other
- The threshold (0.85) is appropriate for near-identical titles but misses paraphrased titles covering the same story

---

## 1. Relevance Filtering Strategy

### 1.1 Decision Rules (Ordered Pipeline)

#### Rule 1: Editorial Blacklist Gate [SCOPE A+B]

**Position in pipeline**: FIRST check, before any computation.

```python
# Already exists in summarize.py and collect_rss.py via editor_feedback module
if editor_feedback.feedback_reason_for_article(article, feedback):
    article["status"] = "irrelevant"
    # STOP — do not process further
```

No changes needed. This gate already works correctly.

#### Rule 2: Blocked Content Gate [SCOPE A+B]

**Position in pipeline**: SECOND check.

```python
# Already exists in summarize.py:_validate_content_integrity()
# Detects CloudFlare, CAPTCHA, 403/404, empty content
# Mark as irrelevant, not just skip
if not _validate_content_integrity(content, title):
    article["status"] = "irrelevant"
```

**Scope A difference**: For retroactive batch, also check already-validated articles whose content is blocked (some may have slipped through before this gate existed).

#### Rule 3: Keyword-Based Pre-filter (Enhanced) [SCOPE A+B]

Enhance the existing `_is_elections_relevant()` function in `summarize.py`:

```python
def _is_elections_relevant(title: str, content: str = "", source_category: str = "") -> bool:
    """Enhanced relevance gate. Returns True when election signals are present."""
    
    normalized_title = _normalize_text(title)
    # CHANGE: Use first 1500 chars instead of 800 for better signal extraction
    normalized_content = _normalize_text(content)[:1500] if content else ""
    normalized_text = f"{normalized_title} {normalized_content}".strip()
    
    # Existing keyword scoring (unchanged)
    high_signal_hits = _keyword_hits(normalized_text, ELECTIONS_HIGH_SIGNAL_KEYWORDS)
    candidate_hits = _keyword_hits(normalized_text, CANDIDATE_SIGNAL_KEYWORDS)
    context_hits = _keyword_hits(normalized_text, BRAZIL_CONTEXT_KEYWORDS)
    off_topic_hits = _keyword_hits(normalized_text, OFF_TOPIC_KEYWORDS)
    
    # Existing logic (unchanged) ...
```

**Key addition — new "always irrelevant" patterns**:

```python
# New set: international-only signals with no Brazil connection
INTERNATIONAL_ONLY_KEYWORDS: frozenset[str] = frozenset({
    "eua", "estados unidos", "trump", "biden",
    "china", "europa", "russia", "ucrania",
    "fed ", "federal reserve", "wall street", "nasdaq", "dow jones",
    "s&p 500", "consumer sentiment",
})

# ADDITIONAL RULE: If article is purely international with zero Brazil/election context
international_hits = _keyword_hits(normalized_text, INTERNATIONAL_ONLY_KEYWORDS)
if international_hits >= 2 and context_hits == 0 and candidate_hits == 0 and high_signal_hits == 0:
    return False
```

**Always-relevant topic combinations**:
- `eleicoes` in topics (any combination) → ALWAYS relevant
- Any candidate in `candidates_mentioned` → ALWAYS relevant
- `topics` includes `corrupcao` + context keyword → likely relevant (needs candidate check post-LLM)

**Always-irrelevant topic combinations**:
- Only `economia` with no candidates, no election keywords, no Brazil context → irrelevant
- Only international economic indicators → irrelevant
- Sports/entertainment with zero political signal → irrelevant (already caught by OFF_TOPIC_KEYWORDS)

#### Rule 4: Post-LLM Relevance Validation [SCOPE A+B]

**This is the critical new gate.** After `ai_client.summarize_article()` returns, check whether the LLM found any election-relevant content:

```python
def _post_llm_relevance_check(article: dict) -> tuple[bool, float]:
    """
    After LLM processing, validate that the article is genuinely election-relevant.
    Returns (is_relevant, computed_relevance_score).
    """
    candidates = article.get("candidates_mentioned", [])
    topics = article.get("topics", [])
    summaries = article.get("summaries", {})
    title = article.get("title", "")
    content = article.get("content", "")
    
    score = 0.0
    
    # Signal 1: Candidates mentioned (strongest signal)
    if candidates:
        score += 0.4 + min(0.2, len(candidates) * 0.1)  # 0.4-0.6
    
    # Signal 2: "eleicoes" in topics
    if "eleicoes" in topics:
        score += 0.25
    
    # Signal 3: Other political topics present
    political_topics = {"corrupcao", "impostos", "privatizacao", "previdencia"}
    political_overlap = len(set(topics) & political_topics)
    score += min(0.15, political_overlap * 0.05)
    
    # Signal 4: Election keywords in summaries (LLM-generated, higher quality than raw content)
    summary_text = _normalize_text(
        f"{summaries.get('pt-BR', '')} {summaries.get('en-US', '')}"
    )
    election_kw_in_summary = _keyword_hits(summary_text, ELECTIONS_HIGH_SIGNAL_KEYWORDS)
    candidate_kw_in_summary = _keyword_hits(summary_text, CANDIDATE_SIGNAL_KEYWORDS)
    score += min(0.15, (election_kw_in_summary + candidate_kw_in_summary) * 0.05)
    
    # Signal 5: Source category bonus
    source_cat = article.get("source_category", "")
    if source_cat in ("party", "institutional"):
        score += 0.10  # These sources are inherently political
    elif source_cat == "politics":
        score += 0.05
    
    # Clamp to [0.0, 1.0]
    score = min(1.0, max(0.0, round(score, 4)))
    
    # Decision threshold
    is_relevant = score >= 0.30  # Minimum: at least 1 candidate OR eleicoes topic + something
    
    return is_relevant, score
```

**Scope B implementation** (in `summarize.py`, after LLM call returns):
```python
# After LLM results are merged into article fields
is_relevant, relevance_score = _post_llm_relevance_check(article)
article["relevance_score"] = relevance_score

if not is_relevant:
    article["status"] = "irrelevant"
    article["editor_note"] = f"auto-filtered: relevance_score={relevance_score:.2f}"
    # Add to editorial feedback to prevent re-collection
    editor_feedback.add_article_id_to_feedback(feedback, article)
    continue
```

**Scope A implementation** (in batch cleanup script, runs over all existing articles):
```python
# For validated/curated articles, re-evaluate relevance using existing fields
is_relevant, relevance_score = _post_llm_relevance_check(article)
article["relevance_score"] = relevance_score

if not is_relevant and article["status"] in ("validated", "curated"):
    article["status"] = "irrelevant"
    _append_edit_history(article, action="sanitize-irrelevant", provider="batch-sanitizer")
```

#### Rule 5: LLM Borderline Triage [SCOPE A only]

For articles scoring between 0.20 and 0.35 (borderline), use a single LLM call to make a binary keep/discard decision:

```python
BORDERLINE_TRIAGE_PROMPT = """
You are evaluating whether this news article is relevant to the 2026 Brazilian 
presidential election. Consider: does it discuss candidates, electoral strategy, 
polls, party politics, legislative actions that affect the race, or policy 
positions of declared/speculated candidates?

Title: {title}
Summary: {summary_pt}
Topics: {topics}
Candidates mentioned: {candidates}

Answer ONLY with JSON: {{"relevant": true|false, "reason": "one sentence"}}
"""
```

**Rate-limit estimate**: If ~80 articles are borderline (16% of 500), at 450 tokens each, this is ~36K tokens total — well within free-tier limits for a single batch run.

### 1.2 `relevance_score` Repair [SCOPE A+B]

**Root cause fix**: The `ai_client.summarize_article()` prompt does NOT ask for `relevance_score`. Rather than depending on the LLM for this (unreliable), compute it deterministically using `_post_llm_relevance_check()` described above.

**Scope B**: `_post_llm_relevance_check()` runs on every newly summarized article in `summarize.py`. The score is computed from the LLM's structured output (candidates, topics) + keyword analysis.

**Scope A**: The batch cleanup script runs `_post_llm_relevance_check()` over all 500 existing articles. Since they already have `candidates_mentioned`, `topics`, and `summaries` populated by the LLM, the heuristic has good data to work with.

### 1.3 Status Handling for Filtered Articles

**Decision**: Mark as `"irrelevant"` and KEEP in `articles.json` (do not delete).

Rationale:
- `build_data.py:consolidate_articles()` already filters out `status == "irrelevant"` from the published output
- Keeping them prevents re-collection (the `id` check in `collect_rss.py` will skip them)
- Adding them to `editor_feedback.json:irrelevant_article_ids` provides a secondary block
- `edit_history` preserves the audit trail of why they were marked irrelevant

**However**: After `build_data.py` runs, irrelevant articles are physically excluded from the final 500-article output. This is the existing behavior and should be preserved. The net effect is that irrelevant articles are logically deleted from the published dataset but their IDs persist in `editor_feedback.json` to prevent re-ingestion.

---

## 2. Duplicate/Near-Duplicate Detection Strategy

### 2.1 Algorithm Design [SCOPE A+B]

#### Phase 1: Enhanced Title-Based Clustering (Fast)

```python
def cluster_articles(articles: list[dict]) -> dict[str, list[int]]:
    """
    Group articles by narrative similarity using TF-IDF on title + summary.
    Returns {cluster_id: [article_indices]}.
    """
    # Improvement over current deduplicate_narratives.py:
    # 1. Use title + pt-BR summary (not just title)
    # 2. Use content first 500 chars as fallback if no summary
    # 3. Lower threshold for cross-source detection (0.75 instead of 0.85)
    # 4. Add published_at proximity constraint (within 48 hours)
    
    texts = []
    for article in articles:
        title = article.get("title", "")
        summary = article.get("summaries", {}).get("pt-BR", "")
        content_snippet = (article.get("content", "") or "")[:500]
        # Weight title 2x by repeating it
        text = f"{title} {title} {summary or content_snippet}"
        texts.append(_normalize_text(text))
    
    vectorizer = TfidfVectorizer(
        lowercase=True, 
        strip_accents="unicode", 
        ngram_range=(1, 2),
        max_features=10000,
    )
    matrix = vectorizer.fit_transform(texts)
    similarity = cosine_similarity(matrix)
    
    # Union-Find clustering with time proximity constraint
    parent = list(range(len(articles)))
    
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            if similarity[i, j] < 0.75:
                continue
            # Time proximity check: must be within 48 hours
            ts_i = _parse_iso8601(articles[i].get("published_at"))
            ts_j = _parse_iso8601(articles[j].get("published_at"))
            if ts_i and ts_j and abs((ts_i - ts_j).total_seconds()) > 48 * 3600:
                continue
            _union(parent, i, j)
    
    # Build groups
    groups = {}
    for idx in range(len(articles)):
        root = _find(parent, idx)
        groups.setdefault(root, []).append(idx)
    
    # Only return groups with 2+ articles
    return {
        _make_cluster_id([articles[i]["id"] for i in members]): members
        for members in groups.values()
        if len(members) >= 2
    }
```

#### Phase 2: Canonical Representative Selection ("Keep" Heuristic)

```python
SOURCE_CATEGORY_PRIORITY = {
    "politics": 1,      # Dedicated political outlets: most context
    "mainstream": 2,     # Major newspapers: reliable
    "magazine": 3,       # Weekly magazines: depth
    "institutional": 4,  # Government sources: primary
    "international": 5,  # Foreign outlets: different perspective
    "party": 6,          # Party sites: biased
    "social": 7,         # YouTube/Twitter: least editorial
}

def select_canonical(articles: list[dict], cluster_indices: list[int]) -> int:
    """
    Select the canonical article from a cluster.
    Priority: source_category > content_length > summaries_quality > earliest_collected.
    Returns the index of the canonical article.
    """
    def sort_key(idx: int) -> tuple:
        a = articles[idx]
        cat_priority = SOURCE_CATEGORY_PRIORITY.get(a.get("source_category", ""), 99)
        content_len = len(a.get("content", "") or "")
        has_summaries = 1 if (a.get("summaries", {}).get("pt-BR", "").strip()) else 0
        collected = a.get("collected_at", "9999")  # Earlier is better
        return (cat_priority, -has_summaries, -content_len, collected)
    
    return min(cluster_indices, key=sort_key)
```

#### Phase 3: Non-Canonical Duplicate Handling

**Decision**: Mark non-canonical duplicates with `status = "irrelevant"` and set their `narrative_cluster_id` to the shared cluster ID. The canonical article also gets the `narrative_cluster_id` but keeps its status.

```python
for cluster_id, member_indices in clusters.items():
    canonical_idx = select_canonical(articles, member_indices)
    
    for idx in member_indices:
        articles[idx]["narrative_cluster_id"] = cluster_id
        
        if idx != canonical_idx:
            # Non-canonical: mark as duplicate
            articles[idx]["status"] = "irrelevant"
            articles[idx]["editor_note"] = f"duplicate of {articles[canonical_idx]['id']} in {cluster_id}"
            _append_edit_history(
                articles[idx], 
                action="sanitize-duplicate", 
                provider="batch-sanitizer",
                changes=["status", "narrative_cluster_id", "editor_note"]
            )
    
    # Canonical gets cluster ID and a prominence boost
    _append_edit_history(
        articles[canonical_idx],
        action="cluster-canonical",
        provider="batch-sanitizer", 
        changes=["narrative_cluster_id"]
    )
```

### 2.2 Edge Case: Same Story, Different Angle

The 0.75 cosine similarity threshold is calibrated to catch:
- **Near-identical** (>0.90): Wire-service syndication (Agencia Estado/Brasil distributed across UOL, IstoE, Veja). These are true duplicates → merge.
- **High similarity** (0.75-0.90): Same story, minor editorial differences. Keep canonical only.
- **Moderate similarity** (0.60-0.75): Same underlying event, genuinely different angles. These are NOT clustered — both articles are kept as independent entries.

For the Vorcaro/Banco Master example: if one outlet covers it as "corruption" and another as "electoral implications", the TF-IDF vectors will diverge below 0.75 because the vocabulary differs significantly. Both will be kept.

**Validation**: After clustering, log all clusters where max similarity is between 0.70 and 0.80 for manual spot-check. This catches the edge zone where genuine-different-angle articles might be incorrectly clustered.

### 2.3 Scope B: Ingestion-Time Deduplication

```python
# In collect_rss.py, BEFORE appending a new article:

def _is_near_duplicate(new_article: dict, existing_articles: list[dict]) -> str | None:
    """
    Check if new_article is a near-duplicate of any existing article.
    Returns the cluster_id if duplicate, None otherwise.
    Uses a lightweight comparison (no TF-IDF matrix rebuild).
    """
    new_title = _normalize_text(new_article.get("title", ""))
    new_ts = _parse_iso8601(new_article.get("published_at"))
    
    for existing in existing_articles:
        # Quick pre-filter: must be within 48 hours
        ex_ts = _parse_iso8601(existing.get("published_at"))
        if new_ts and ex_ts and abs((new_ts - ex_ts).total_seconds()) > 48 * 3600:
            continue
        
        ex_title = _normalize_text(existing.get("title", ""))
        
        # Fast check 1: exact normalized title match
        if new_title == ex_title:
            return existing.get("narrative_cluster_id") or _make_cluster_id(
                [existing["id"], new_article["id"]]
            )
        
        # Fast check 2: one title is a substring of the other (wire-service truncation)
        if len(new_title) > 20 and len(ex_title) > 20:
            if new_title in ex_title or ex_title in new_title:
                return existing.get("narrative_cluster_id") or _make_cluster_id(
                    [existing["id"], new_article["id"]]
                )
        
        # Fast check 3: Jaccard similarity on word sets (no sklearn needed)
        new_words = set(new_title.split())
        ex_words = set(ex_title.split())
        if new_words and ex_words:
            jaccard = len(new_words & ex_words) / len(new_words | ex_words)
            if jaccard >= 0.80:
                return existing.get("narrative_cluster_id") or _make_cluster_id(
                    [existing["id"], new_article["id"]]
                )
    
    return None
```

**Integration point** (in `collect_rss.py:collect_articles()`):
```python
# After building the new article dict, before appending:
cluster_match = _is_near_duplicate(article, document.articles + new_articles)
if cluster_match is not None:
    # Still collect the article (for audit), but mark as duplicate immediately
    article["status"] = "irrelevant"
    article["narrative_cluster_id"] = cluster_match
    article["editor_note"] = f"near-duplicate detected at ingestion"
```

**Key difference from Scope A**: At ingestion time, we use lightweight Jaccard similarity (no sklearn import needed in `collect_rss.py`) instead of full TF-IDF. This avoids rebuilding the TF-IDF matrix on every 10-minute collection cycle. The full TF-IDF clustering runs in the hourly curate step as a secondary pass.

---

## 3. Implementation Plan

### 3.1 Architecture Overview

Design principle: **Scope B first, Scope A reuses its logic.**

```
scripts/
  sanitize/
    __init__.py                 # Package init
    relevance.py         [A+B]  # _post_llm_relevance_check(), _is_elections_relevant() (enhanced)
    dedup.py             [A+B]  # cluster_articles(), select_canonical(), _is_near_duplicate()
    batch_cleanup.py     [A]    # CLI: one-time retroactive sanitization
    constants.py         [A+B]  # Shared keyword sets, thresholds, source priorities
```

### 3.2 Component Details

#### `scripts/sanitize/__init__.py` [SCOPE A+B]

Empty init file. Makes the sanitize module importable.

#### `scripts/sanitize/constants.py` [SCOPE A+B]

Centralizes all keyword sets and configuration constants currently scattered across `summarize.py` and `analyze_sentiment.py`:

```python
# Move from summarize.py (currently duplicated):
ELECTIONS_HIGH_SIGNAL_KEYWORDS  # 26 keywords
CANDIDATE_SIGNAL_KEYWORDS       # 10 keywords  
BRAZIL_CONTEXT_KEYWORDS         # 10 keywords
OFF_TOPIC_KEYWORDS              # 15 keywords
CANONICAL_CANDIDATE_SLUGS       # 9 slugs
CANDIDATE_ALIASES               # ~20 mappings

# New:
INTERNATIONAL_ONLY_KEYWORDS     # ~15 keywords (see section 1.1 Rule 3)

# Thresholds:
RELEVANCE_THRESHOLD = 0.30           # Minimum relevance_score to keep
BORDERLINE_LOW = 0.20                # Below this: definitely irrelevant
BORDERLINE_HIGH = 0.35               # Above this: definitely relevant
DEDUP_SIMILARITY_THRESHOLD = 0.75    # TF-IDF cosine for clustering
DEDUP_JACCARD_THRESHOLD = 0.80       # Jaccard for ingestion-time check
DEDUP_TIME_WINDOW_HOURS = 48         # Max time gap for duplicate detection

# Source category weights (move from curate.py):
SOURCE_CATEGORY_PRIORITY = { ... }
```

**Note on existing code**: `summarize.py` and `analyze_sentiment.py` currently define these keyword sets independently. After creating `constants.py`, update both files to import from `sanitize.constants` instead of duplicating. This is a safe refactor — the values are identical.

#### `scripts/sanitize/relevance.py` [SCOPE A+B]

Core relevance scoring logic:

```python
def compute_relevance_score(article: dict) -> float:
    """
    Compute relevance_score from article's structured fields.
    Call AFTER LLM summarization (when candidates_mentioned, topics, summaries are populated).
    Returns float 0.0-1.0.
    """
    # Implementation as described in section 1.1 Rule 4

def is_elections_relevant_pre_llm(title: str, content: str, source_category: str) -> bool:
    """
    Enhanced pre-LLM keyword gate. Drop-in replacement for summarize.py:_is_elections_relevant().
    """
    # Implementation as described in section 1.1 Rule 3 (enhanced version)

def is_relevant_post_llm(article: dict) -> tuple[bool, float]:
    """
    Post-LLM relevance gate. Returns (is_relevant, relevance_score).
    """
    score = compute_relevance_score(article)
    return score >= RELEVANCE_THRESHOLD, score
```

**Scope B integration** — modify `summarize.py`:
1. Replace `from summarize import _is_elections_relevant` with `from sanitize.relevance import is_elections_relevant_pre_llm`
2. After LLM results are merged into article, call `is_relevant_post_llm(article)`
3. Set `article["relevance_score"]` to the computed score
4. If not relevant, set `status = "irrelevant"`

**Scope A**: `batch_cleanup.py` imports and calls `is_relevant_post_llm()` on every article.

#### `scripts/sanitize/dedup.py` [SCOPE A+B]

Deduplication logic:

```python
def cluster_articles_tfidf(
    articles: list[dict],
    threshold: float = DEDUP_SIMILARITY_THRESHOLD,
    time_window_hours: int = DEDUP_TIME_WINDOW_HOURS,
) -> dict[str, list[int]]:
    """
    Full TF-IDF clustering using title + summary text.
    Returns {cluster_id: [article_indices]} for clusters with 2+ members.
    """
    # Implementation as described in section 2.1 Phase 1

def select_canonical(articles: list[dict], cluster_indices: list[int]) -> int:
    """Select the best representative from a narrative cluster."""
    # Implementation as described in section 2.1 Phase 2

def is_near_duplicate_fast(
    new_article: dict,
    existing_articles: list[dict],
    time_window_hours: int = DEDUP_TIME_WINDOW_HOURS,
) -> str | None:
    """
    Lightweight ingestion-time duplicate check using Jaccard similarity.
    Returns cluster_id if duplicate, None otherwise. No sklearn dependency.
    """
    # Implementation as described in section 2.3

def apply_cluster_decisions(
    articles: list[dict],
    clusters: dict[str, list[int]],
) -> tuple[int, int]:
    """
    Apply canonical/duplicate decisions to articles.
    Returns (articles_marked_duplicate, clusters_processed).
    """
    # Implementation as described in section 2.1 Phase 3
```

**Scope B integration points**:
1. `collect_rss.py`: Call `is_near_duplicate_fast()` before appending new articles
2. `deduplicate_narratives.py`: Replace existing logic with `cluster_articles_tfidf()` + `apply_cluster_decisions()` (the existing script becomes a thin wrapper)
3. Remove the 24-hour window restriction — cluster ALL validated articles (not just recent ones)

**Scope A**: `batch_cleanup.py` calls `cluster_articles_tfidf()` on the full dataset.

#### `scripts/sanitize/batch_cleanup.py` [SCOPE A only]

One-time retroactive cleanup script with CLI interface:

```python
"""
One-time retroactive sanitization of data/articles.json.

Usage:
    python -m scripts.sanitize.batch_cleanup [--dry-run] [--borderline-llm] [--output PATH]

Flags:
    --dry-run          Print summary without modifying articles.json
    --borderline-llm   Use LLM to triage borderline articles (0.20-0.35 relevance)
    --output PATH      Write cleaned data to a separate file instead of in-place
"""

def batch_cleanup(
    dry_run: bool = False,
    borderline_llm: bool = False,
    output_path: str | None = None,
) -> dict:
    """
    Main batch cleanup function. Idempotent: safe to run multiple times.
    
    Steps:
    1. Load articles.json
    2. Re-compute relevance_score for ALL articles using compute_relevance_score()
    3. Mark articles with score < RELEVANCE_THRESHOLD as irrelevant
    4. (Optional) LLM triage for borderline articles
    5. Run full TF-IDF clustering on remaining relevant articles
    6. Select canonical representatives, mark duplicates as irrelevant
    7. Append edit_history entries for all changes
    8. Save (or dry-run print summary)
    
    Returns audit summary dict.
    """
```

**Idempotency guarantees**:
- Check `edit_history` for existing `"sanitize-irrelevant"` or `"sanitize-duplicate"` actions before re-processing
- If an article was already marked irrelevant by a previous batch run, skip it
- Re-running produces identical output (deterministic relevance scoring, stable clustering)

**Output format**: Mutate `articles.json` in-place (default) OR write to a separate file with `--output`. The `--dry-run` flag prints a JSON summary:

```json
{
  "total_articles": 500,
  "already_irrelevant": 0,
  "newly_irrelevant_by_relevance": 145,
  "newly_irrelevant_by_duplicate": 12,
  "borderline_kept_by_llm": 8,
  "borderline_removed_by_llm": 5,
  "clusters_found": 15,
  "final_relevant_count": 338,
  "relevance_score_distribution": {
    "0.0-0.1": 0, "0.1-0.2": 12, "0.2-0.3": 25, ...
  }
}
```

### 3.3 Pipeline Integration Diagram

```
COLLECTION (collect_rss.py, every 10min)
  │
  ├── [existing] URL-based dedup (sha256 id check)
  ├── [existing] Editorial blacklist check
  ├── [NEW/SCOPE B] is_near_duplicate_fast() — Jaccard title check
  │     → If duplicate: collect but mark status="irrelevant" immediately
  │
  ▼
SUMMARIZATION (summarize.py, every 30min)
  │
  ├── [existing] _validate_content_integrity()
  ├── [MODIFIED/SCOPE B] is_elections_relevant_pre_llm() — enhanced keyword gate
  │     → If irrelevant: mark status="irrelevant", skip LLM
  ├── [existing] LLM call → summaries, candidates, topics, sentiment
  ├── [NEW/SCOPE B] is_relevant_post_llm() — post-LLM validation
  │     → Computes relevance_score (replaces hardcoded 0.0)
  │     → If irrelevant post-LLM: mark status="irrelevant"
  │
  ▼
DEDUPLICATION (deduplicate_narratives.py, hourly via curate)
  │
  ├── [MODIFIED/SCOPE B] cluster_articles_tfidf() — full TF-IDF on title+summary
  │     → No 24-hour restriction; process all validated articles
  ├── [NEW/SCOPE B] select_canonical() + apply_cluster_decisions()
  │     → Canonical keeps status, duplicates → status="irrelevant"
  │
  ▼
CURATION (curate.py, hourly)
  │
  ├── [existing] prominence scoring (now uses real relevance_score)
  ├── [existing] curated_feed.json generation
  │
  ▼
CONSOLIDATION (build_data.py)
  │
  ├── [existing] Filters out status="irrelevant"
  ├── [existing] Trims to 500 articles
  └── Final articles.json for frontend
```

### 3.4 Processing Complexity & Rate Limits

| Component | Complexity | LLM Calls | Estimated Time |
|-----------|-----------|-----------|----------------|
| Relevance scoring (heuristic) | O(n) per article | 0 | < 1s for 500 articles |
| Pre-LLM keyword gate | O(n * k) where k = keyword count | 0 | < 1s |
| Post-LLM validation | O(n) per article | 0 | < 1s |
| TF-IDF clustering (batch) | O(n^2) for similarity matrix | 0 | ~2-5s for 500 articles |
| Jaccard ingestion check | O(n) per new article | 0 | < 100ms per article |
| Borderline LLM triage (Scope A) | O(b) where b = borderline count | ~80 calls max | ~3-5min |

**Rate-limit concerns**: Only the optional `--borderline-llm` flag in `batch_cleanup.py` makes LLM calls. At ~80 articles * 450 tokens = ~36K tokens, this is within free-tier limits for NVIDIA/Ollama. The existing circuit breaker in `ai_client.py` handles provider failures gracefully.

**Scope B has ZERO LLM calls** for sanitization — all gates are heuristic/deterministic. The only LLM calls are the existing ones in `summarize.py` for generating summaries.

### 3.5 Output Strategy

**Scope A** (batch cleanup):
- Default: Mutate `articles.json` in-place (same as every other pipeline script)
- Optional `--output /path/to/clean.json` writes to a separate file for review before replacing
- Optional `--dry-run` prints summary only
- Produces `data/sanitization_report.json` with full audit trail

**Scope B** (ingestion guard):
- No new output files. Changes are inline within the existing pipeline flow
- Irrelevant/duplicate articles are marked in `articles.json` and filtered by `build_data.py`
- `editor_feedback.json` is updated with newly blocked article IDs

---

## 4. Quality Gates

### 4.1 Acceptance Criteria

#### Scope A (Retroactive Batch)

| Metric | Expected Range | Rationale |
|--------|---------------|-----------|
| Articles marked irrelevant (by relevance) | 20-40% of 500 (100-200) | 82.2% have empty candidates; many are genuinely political but not election-specific. Conservative estimate: ~half of empty-candidate articles are truly irrelevant. |
| Articles marked irrelevant (by duplicate) | 2-5% of 500 (10-25) | 15 duplicates detected by simple title matching; TF-IDF will catch a few more. |
| Total reduction | 25-40% (125-200 articles) | Combined irrelevant + duplicate removal. |
| `relevance_score > 0.0` | 100% of remaining articles | The all-zeros bug must be fixed for every article. |
| `narrative_cluster_id` populated | All articles in clusters (estimated 5-15% of remaining) | Clustering must actually run and persist results. |
| Zero data loss of genuinely relevant articles | Spot-check validation (see 4.2) | False-positive rate for irrelevant marking must be < 2%. |

#### Scope B (Ingestion Guard)

| Metric | Expected Behavior | How to Verify |
|--------|------------------|---------------|
| No new article enters with `relevance_score = 0.0` | Every validated article has score > 0.0 | Watchdog check: assert no validated article has relevance_score == 0.0 |
| Near-duplicates caught at ingestion | Jaccard check prevents same-story from different sources | Synthetic test: feed same article with different URL → should be caught |
| Irrelevant articles never reach `validated` status | Pre-LLM and post-LLM gates both trigger | Monitor: count of articles going raw→irrelevant vs raw→validated |
| `narrative_cluster_id` populated for story groups | Hourly clustering assigns IDs | Watchdog check: validated articles with similar titles should share cluster IDs |
| Pipeline throughput unaffected | Collection cycle stays under 25min timeout | Monitor workflow run times before/after |

### 4.2 Validation: Preventing False Positives

#### Spot-Check Methodology [SCOPE A]

After running `batch_cleanup.py --dry-run`:

1. **Sample 20 articles** from the "newly marked irrelevant" set:
   - 10 with lowest relevance_score (most confident removals)
   - 10 randomly selected
   - **Verify**: Each article is genuinely unrelated to the 2026 presidential race
   - **Acceptable false-positive rate**: < 2 out of 20 (< 10%)

2. **Sample 10 articles** from the "borderline kept" set (score 0.30-0.40):
   - **Verify**: Each article has at least a tangential connection to the election
   - If > 3 should have been removed, lower `RELEVANCE_THRESHOLD` to 0.25

3. **Sample all duplicate clusters** (estimated 5-15):
   - **Verify**: Each cluster groups genuinely same-story articles
   - **Verify**: The canonical selection picked the best representative
   - **Verify**: No cluster incorrectly merged genuinely different stories

4. **Regression check**: Confirm that ALL of these specific articles remain in the dataset:
   - Any article with `status == "curated"` (editor-chefe promoted)
   - Any article with 2+ candidates in `candidates_mentioned`
   - Any article with `"eleicoes"` in `topics`

#### Automated Validation Script [SCOPE A]

```python
def validate_sanitization(before: list[dict], after: list[dict]) -> dict:
    """
    Compare pre/post sanitization datasets. Returns validation report.
    """
    before_ids = {a["id"] for a in before}
    after_relevant = {a["id"] for a in after if a["status"] != "irrelevant"}
    removed_ids = before_ids - after_relevant
    
    # Check 1: No curated article was removed
    curated_removed = [
        a for a in before 
        if a["id"] in removed_ids and a.get("status") == "curated"
    ]
    
    # Check 2: No article with 2+ candidates was removed
    multi_candidate_removed = [
        a for a in before
        if a["id"] in removed_ids and len(a.get("candidates_mentioned", [])) >= 2
    ]
    
    # Check 3: No article with "eleicoes" topic was removed
    eleicoes_removed = [
        a for a in before
        if a["id"] in removed_ids and "eleicoes" in (a.get("topics") or [])
    ]
    
    # Check 4: All remaining articles have relevance_score > 0.0
    zero_scores = [
        a for a in after
        if a.get("status") != "irrelevant" and a.get("relevance_score", 0.0) == 0.0
    ]
    
    return {
        "total_before": len(before),
        "total_after_relevant": len(after_relevant),
        "reduction_pct": round((1 - len(after_relevant) / len(before)) * 100, 1),
        "curated_removed": len(curated_removed),  # MUST BE 0
        "multi_candidate_removed": len(multi_candidate_removed),  # MUST BE 0
        "eleicoes_topic_removed": len(eleicoes_removed),  # MUST BE 0
        "zero_relevance_scores": len(zero_scores),  # MUST BE 0
        "PASS": (
            len(curated_removed) == 0
            and len(multi_candidate_removed) == 0
            and len(eleicoes_removed) == 0
            and len(zero_scores) == 0
        ),
    }
```

### 4.3 Quality Gates by Scope

#### Ingest-Time Gates [SCOPE B]

These run on EVERY article during collection/summarization:

1. **Collection gate** (collect_rss.py): `is_near_duplicate_fast()` — blocks cross-source duplicates
2. **Pre-LLM gate** (summarize.py): `is_elections_relevant_pre_llm()` — blocks obviously irrelevant content
3. **Post-LLM gate** (summarize.py): `is_relevant_post_llm()` — blocks articles where LLM found no election connection
4. **Relevance score gate**: Every validated article MUST have `relevance_score > 0.0`

#### Post-Batch Gates [SCOPE A]

These run during the one-time cleanup:

1. **Automated validation**: `validate_sanitization()` must return `PASS = True`
2. **Spot-check**: Manual review of 20 removed + 10 borderline + all clusters
3. **Regression**: Curated articles, multi-candidate articles, and "eleicoes" articles must survive
4. **`--dry-run` review**: Run dry-run first, review summary, then run for real

---

## 5. Schema Evolution

### 5.1 No Breaking Changes Required

The existing schema supports all needed operations:
- `status: "irrelevant"` is already a valid enum value
- `narrative_cluster_id` field already exists (just null)
- `relevance_score` field already exists (just broken at 0.0)
- `edit_history` supports arbitrary tier/action/changes entries
- `editor_note` field already exists for explanatory text

### 5.2 Recommended Additive Changes

#### New field: `duplicate_of` (optional) [SCOPE A+B]

```json
{
  "duplicate_of": {
    "type": ["string", "null"],
    "description": "ID of the canonical article this is a duplicate of. Null if not a duplicate."
  }
}
```

**Rationale**: Currently, non-canonical duplicates are marked `status="irrelevant"` with the duplicate info only in `editor_note`. A structured `duplicate_of` field enables:
- Frontend could show "See also: [canonical article]" instead of just hiding duplicates
- Analytics can measure duplicate rate over time
- Re-clustering can use existing `duplicate_of` relationships

#### New field: `relevance_signals` (optional) [SCOPE A+B]

```json
{
  "relevance_signals": {
    "type": ["object", "null"],
    "description": "Breakdown of how relevance_score was computed",
    "properties": {
      "candidate_signal": { "type": "number" },
      "topic_signal": { "type": "number" },
      "keyword_signal": { "type": "number" },
      "source_signal": { "type": "number" }
    }
  }
}
```

**Rationale**: Makes `relevance_score` auditable. When a human reviews a borderline article, they can see WHY the score is what it is.

### 5.3 Fixing `relevance_score` at the Pipeline Level [SCOPE B]

**Root cause**: `collect_rss.py` sets `relevance_score: None`, and `summarize.py:_ensure_article_defaults()` coerces it to `0.0` before any real computation happens.

**Fix**:

1. **`collect_rss.py`**: Keep setting `relevance_score: None` (correct — score is unknown at collection time)

2. **`summarize.py:_ensure_article_defaults()`**: Change the default from `0.0` to `None`:
   ```python
   # BEFORE (broken):
   if not isinstance(article.get("relevance_score"), (int, float)):
       article["relevance_score"] = 0.0
   
   # AFTER (correct):
   # Do NOT default to 0.0 here — let compute_relevance_score() set it after LLM
   ```

3. **`summarize.py` (after LLM call)**: Explicitly compute and set the score:
   ```python
   from sanitize.relevance import compute_relevance_score
   article["relevance_score"] = compute_relevance_score(article)
   ```

4. **`build_data.py:_normalize_null_numbers()`**: This function coerces `None` to `0.0` for all number fields. For `relevance_score`, this is acceptable at the FINAL consolidation stage — it means "not yet scored" rather than "scored as zero". The key fix is ensuring that `summarize.py` sets a real score before `build_data.py` runs.

5. **Watchdog check** (add to `watchdog.py`): Assert that no `validated` or `curated` article has `relevance_score == 0.0`. If any do, log a pipeline health warning.

---

## 6. Prioritized Implementation Order

### Phase 1: Core Module + Scope B Guards (HIGHEST PRIORITY)

1. Create `scripts/sanitize/` package with `constants.py`, `relevance.py`, `dedup.py`
2. Integrate `is_elections_relevant_pre_llm()` into `summarize.py` (replacing existing function)
3. Integrate `compute_relevance_score()` into `summarize.py` (after LLM call)
4. Integrate `is_relevant_post_llm()` into `summarize.py` (new post-LLM gate)
5. Fix `_ensure_article_defaults()` to not coerce relevance_score to 0.0
6. Integrate `is_near_duplicate_fast()` into `collect_rss.py`
7. Update `deduplicate_narratives.py` to use `cluster_articles_tfidf()` from `dedup.py`

### Phase 2: Batch Cleanup (Scope A)

8. Implement `batch_cleanup.py` CLI
9. Run `--dry-run` and review output
10. Run spot-check validation
11. Execute cleanup and commit

### Phase 3: Monitoring & Schema

12. Add watchdog checks for `relevance_score == 0.0` on validated articles
13. Add optional schema fields (`duplicate_of`, `relevance_signals`)
14. Update TypeScript types in `docs/schemas/types.ts`

---

## 7. Definition of Done

The sanitization work is complete when ALL of the following are true:

### Tests (for Codex to implement)

#### Unit Tests

1. **`test_relevance_scoring.py`**:
   - `test_candidate_mention_gives_high_score`: Article with 2 candidates → score >= 0.50
   - `test_eleicoes_topic_gives_moderate_score`: Article with "eleicoes" topic + no candidates → score >= 0.25
   - `test_pure_economics_gives_low_score`: Article with only "economia" topic, no candidates, no election keywords → score < 0.30
   - `test_international_only_gives_zero`: Article about US consumer sentiment → score < 0.20
   - `test_empty_article_gives_zero`: Article with no topics, no candidates, no content → score == 0.0
   - `test_party_source_gets_bonus`: Party-source article with 1 election keyword → score boosted
   - `test_score_is_deterministic`: Same input → same output (idempotent)
   - `test_score_range`: Score is always in [0.0, 1.0]

2. **`test_pre_llm_gate.py`**:
   - `test_obvious_election_article_passes`: "Lula lidera pesquisa eleitoral..." → True
   - `test_obvious_offtopic_fails`: "Exportacoes do agro..." → False
   - `test_us_macro_fails`: "Sentimento do consumidor nos EUA..." → False
   - `test_stf_without_election_angle_fails`: "STF vota sobre Banco Master..." → False
   - `test_stf_with_candidate_mention_passes`: "STF e impacto na campanha de Caiado..." → True
   - `test_party_source_with_one_keyword_passes`: institutional source + "eleicao" → True
   - `test_sports_with_zero_signals_fails`: "Campeonato Brasileiro rodada 10..." → False

3. **`test_post_llm_gate.py`**:
   - `test_article_with_candidates_passes`: candidates_mentioned = ["lula"] → relevant
   - `test_article_with_eleicoes_topic_passes`: topics = ["eleicoes", "economia"] → relevant
   - `test_article_with_no_signals_fails`: empty candidates, generic topics → irrelevant
   - `test_borderline_article`: score 0.25-0.35, correctly classified

4. **`test_dedup_fast.py`**:
   - `test_exact_title_match_detected`: Same normalized title → cluster_id returned
   - `test_substring_title_match_detected`: "Exportacoes do agro" vs "Exportacoes do agro tem melhor resultado" → detected
   - `test_high_jaccard_detected`: 80%+ word overlap → detected
   - `test_different_stories_not_matched`: "Lula viaja a China" vs "Caiado propoe reforma" → None
   - `test_time_window_respected`: Same title but 72 hours apart → None (beyond 48h window)
   - `test_returns_cluster_id_format`: Returns string matching "cluster_XXXXXXXX" pattern

5. **`test_dedup_tfidf.py`**:
   - `test_identical_articles_clustered`: 3 articles with identical titles → 1 cluster
   - `test_paraphrased_titles_clustered`: Similar but not identical titles → clustered at 0.75
   - `test_different_stories_not_clustered`: Unrelated articles → separate or no clusters
   - `test_canonical_selection_prefers_politics_source`: politics > mainstream > magazine
   - `test_canonical_selection_prefers_longer_content`: Among same category, longer wins
   - `test_cluster_id_is_deterministic`: Same input → same cluster_id

6. **`test_batch_cleanup.py`**:
   - `test_idempotent`: Running twice produces identical output
   - `test_dry_run_no_mutation`: --dry-run does not modify articles.json
   - `test_curated_articles_preserved`: No curated article is marked irrelevant
   - `test_multi_candidate_articles_preserved`: Articles with 2+ candidates survive
   - `test_eleicoes_topic_articles_preserved`: Articles with "eleicoes" topic survive
   - `test_edit_history_appended`: Sanitized articles have new edit_history entries
   - `test_relevance_score_populated`: All remaining articles have score > 0.0
   - `test_narrative_cluster_id_populated`: Clustered articles have non-null cluster_id
   - `test_irrelevant_articles_have_editor_note`: Each marked article explains why

#### Integration Tests

7. **`test_pipeline_integration.py`**:
   - `test_new_irrelevant_article_blocked_at_summarize`: Feed a raw article about US macro → gets status="irrelevant" after summarize
   - `test_new_duplicate_blocked_at_collect`: Feed article with same title as existing → marked as near-duplicate
   - `test_relevance_score_nonzero_after_summarize`: Every validated article has relevance_score > 0.0
   - `test_end_to_end_pipeline_no_regression`: Run full pipeline on test fixture → validate existing tests still pass

### Acceptance Criteria Checklist

- [ ] `relevance_score` is non-zero for 100% of validated/curated articles
- [ ] `narrative_cluster_id` is populated for all articles in detected clusters
- [ ] No curated article was incorrectly marked irrelevant (automated check)
- [ ] No article with 2+ candidates was marked irrelevant (automated check)
- [ ] No article with "eleicoes" topic was marked irrelevant (automated check)
- [ ] Batch cleanup is idempotent (running twice = same result)
- [ ] Ingestion guard blocks obviously irrelevant articles before they reach validated status
- [ ] Ingestion guard detects cross-source duplicates at collection time
- [ ] Spot-check: < 10% false positive rate on irrelevant markings
- [ ] Pipeline throughput: collection workflow stays under 25min
- [ ] All existing tests continue to pass
- [ ] edit_history integrity: every automated change has a proper audit entry

### Files Changed Summary

| File | Scope | Change Type |
|------|-------|-------------|
| `scripts/sanitize/__init__.py` | A+B | NEW |
| `scripts/sanitize/constants.py` | A+B | NEW |
| `scripts/sanitize/relevance.py` | A+B | NEW |
| `scripts/sanitize/dedup.py` | A+B | NEW |
| `scripts/sanitize/batch_cleanup.py` | A | NEW |
| `scripts/summarize.py` | B | MODIFIED — import + integrate relevance gates |
| `scripts/collect_rss.py` | B | MODIFIED — import + integrate dedup gate |
| `scripts/deduplicate_narratives.py` | B | MODIFIED — delegate to sanitize.dedup |
| `scripts/watchdog.py` | B | MODIFIED — add relevance_score health check |
| `docs/schemas/articles.schema.json` | A+B | MODIFIED — add optional fields |
| `docs/schemas/types.ts` | A+B | MODIFIED — add TypeScript types |

### Open Questions / Trade-offs

1. **Should borderline LLM triage be mandatory in Scope A?** Currently proposed as opt-in (`--borderline-llm`). If the heuristic relevance scoring is accurate enough (spot-check will tell), LLM triage may be unnecessary overhead.

2. **Should duplicates be physically removed or just marked?** Current proposal: mark as `irrelevant` (soft delete). Physical removal would reduce file size but lose audit trail. Recommendation: soft delete, let `build_data.py` do the physical filtering.

3. **Should `deduplicate_narratives.py` process ALL articles or keep the time window?** Current proposal: remove the 24-hour window for Scope A batch, but keep a wider window (7 days) for Scope B to limit O(n^2) computation on every hourly run. For 500 articles, the full matrix takes ~2-5s which is acceptable.

4. **Threshold tuning**: The `RELEVANCE_THRESHOLD = 0.30` and `DEDUP_SIMILARITY_THRESHOLD = 0.75` values are initial estimates. They should be validated with the spot-check methodology and adjusted if the false-positive rate exceeds 10%.
