"""Deterministic relevance gates and scoring."""

from __future__ import annotations

import unicodedata
from typing import Any

from .constants import (
    BRAZIL_CONTEXT_KEYWORDS,
    CANDIDATE_SIGNAL_KEYWORDS,
    ELECTIONS_HIGH_SIGNAL_KEYWORDS,
    INTERNATIONAL_ONLY_KEYWORDS,
    OFF_TOPIC_KEYWORDS,
    POLITICAL_TOPICS,
    RELEVANCE_THRESHOLD,
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().replace("_", " ").replace("-", " ").split())


def _keyword_hits(text: str, keywords: frozenset[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lower()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def is_elections_relevant_pre_llm(
    title: str,
    content: str = "",
    source_category: str = "",
) -> bool:
    """Fast keyword gate used before LLM calls."""
    if not isinstance(title, str) or not title.strip():
        return False

    normalized_title = _normalize_text(title)
    normalized_content = (
        _normalize_text(content)[:1500] if isinstance(content, str) else ""
    )
    normalized_text = f"{normalized_title} {normalized_content}".strip()
    source_category_normalized = (
        source_category.strip().lower() if isinstance(source_category, str) else ""
    )

    high_signal_hits = _keyword_hits(normalized_text, ELECTIONS_HIGH_SIGNAL_KEYWORDS)
    candidate_hits = _keyword_hits(normalized_text, CANDIDATE_SIGNAL_KEYWORDS)
    context_hits = _keyword_hits(normalized_text, BRAZIL_CONTEXT_KEYWORDS)
    off_topic_hits = _keyword_hits(normalized_text, OFF_TOPIC_KEYWORDS)
    international_hits = _keyword_hits(normalized_text, INTERNATIONAL_ONLY_KEYWORDS)

    if (
        international_hits >= 2
        and context_hits == 0
        and candidate_hits == 0
        and high_signal_hits == 0
    ):
        return False

    if off_topic_hits >= 2 and high_signal_hits == 0 and candidate_hits == 0:
        return False

    if high_signal_hits >= 2:
        return True

    if high_signal_hits >= 1 and (candidate_hits >= 1 or context_hits >= 1):
        return True

    if candidate_hits >= 1 and off_topic_hits < 2:
        return True

    if (
        source_category_normalized in {"party", "institutional"}
        and high_signal_hits >= 1
    ):
        return True

    return False


def compute_relevance_signals(article: dict[str, Any]) -> dict[str, float]:
    """Return a score breakdown used for relevance auditing."""
    candidates = _clean_string_list(article.get("candidates_mentioned"))
    topics = _clean_string_list(article.get("topics"))

    candidate_signal = 0.0
    if candidates:
        candidate_signal = 0.4 + min(0.2, len(candidates) * 0.1)

    topic_signal = 0.0
    if "eleicoes" in topics:
        topic_signal += 0.25
    political_overlap = len(set(topics) & POLITICAL_TOPICS)
    topic_signal += min(0.15, political_overlap * 0.05)

    summaries = article.get("summaries")
    summary_pt = summaries.get("pt-BR", "") if isinstance(summaries, dict) else ""
    summary_en = summaries.get("en-US", "") if isinstance(summaries, dict) else ""
    summary_text = _normalize_text(f"{summary_pt} {summary_en}")
    election_kw_hits = _keyword_hits(summary_text, ELECTIONS_HIGH_SIGNAL_KEYWORDS)
    candidate_kw_hits = _keyword_hits(summary_text, CANDIDATE_SIGNAL_KEYWORDS)
    keyword_signal = min(0.15, (election_kw_hits + candidate_kw_hits) * 0.05)

    source_signal = 0.0
    source_category = article.get("source_category")
    if isinstance(source_category, str):
        normalized_source = source_category.strip().lower()
        if normalized_source in {"party", "institutional"}:
            source_signal = 0.10
        elif normalized_source == "politics":
            source_signal = 0.05

    return {
        "candidate_signal": round(candidate_signal, 4),
        "topic_signal": round(topic_signal, 4),
        "keyword_signal": round(keyword_signal, 4),
        "source_signal": round(source_signal, 4),
    }


def compute_relevance_score(article: dict[str, Any]) -> float:
    """Compute deterministic relevance score in [0.0, 1.0]."""
    signals = compute_relevance_signals(article)
    score = sum(signals.values())
    return max(0.0, min(1.0, round(score, 4)))


def _has_brazil_context(article: dict[str, Any]) -> bool:
    """Check if article has Brazil-specific context via summary text."""
    summaries = article.get("summaries")
    if not isinstance(summaries, dict):
        return False
    summary_pt = summaries.get("pt-BR", "") or ""
    summary_en = summaries.get("en-US", "") or ""
    summary_text = _normalize_text(f"{summary_pt} {summary_en}")
    return _keyword_hits(summary_text, BRAZIL_CONTEXT_KEYWORDS) > 0


def is_relevant_post_llm(article: dict[str, Any]) -> tuple[bool, float]:
    """Post-LLM relevance decision using structured fields."""
    topics = _clean_string_list(article.get("topics"))
    candidates = _clean_string_list(article.get("candidates_mentioned"))
    score = compute_relevance_score(article)

    if candidates:
        return True, score
    if "eleicoes" in topics:
        if _has_brazil_context(article):
            return True, score
        return False, score

    return score >= RELEVANCE_THRESHOLD, score
