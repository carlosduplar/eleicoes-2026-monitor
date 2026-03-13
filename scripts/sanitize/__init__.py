"""Shared sanitization helpers for relevance and deduplication."""

from .dedup import (
    apply_cluster_decisions,
    cluster_articles_tfidf,
    is_near_duplicate_fast,
    select_canonical,
)
from .relevance import (
    compute_relevance_score,
    compute_relevance_signals,
    is_elections_relevant_pre_llm,
    is_relevant_post_llm,
)

__all__ = [
    "apply_cluster_decisions",
    "cluster_articles_tfidf",
    "compute_relevance_score",
    "compute_relevance_signals",
    "is_elections_relevant_pre_llm",
    "is_near_duplicate_fast",
    "is_relevant_post_llm",
    "select_canonical",
]
