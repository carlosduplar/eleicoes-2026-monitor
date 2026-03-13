"""Article deduplication helpers for ingestion and batch clustering."""

from __future__ import annotations

import hashlib
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from .constants import (
    DEDUP_JACCARD_THRESHOLD,
    DEDUP_SIMILARITY_THRESHOLD,
    DEDUP_TIME_WINDOW_HOURS,
    SOURCE_CATEGORY_PRIORITY,
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().replace("_", " ").replace("-", " ").split())


def _parse_iso8601(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _article_timestamp(article: dict[str, Any]) -> datetime | None:
    return _parse_iso8601(article.get("published_at")) or _parse_iso8601(
        article.get("collected_at")
    )


def _find(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _union(parent: list[int], left: int, right: int) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root != right_root:
        parent[right_root] = left_root


def _make_cluster_id(article_ids: list[str]) -> str:
    digest = hashlib.sha256("".join(sorted(article_ids)).encode("utf-8")).hexdigest()[:8]
    return f"cluster_{digest}"


def _article_text_for_clustering(article: dict[str, Any]) -> str:
    title = article.get("title") if isinstance(article.get("title"), str) else ""
    summaries = article.get("summaries")
    summary_pt = summaries.get("pt-BR", "") if isinstance(summaries, dict) else ""
    content = article.get("content") if isinstance(article.get("content"), str) else ""
    content_snippet = content[:500]
    text = f"{title} {title} {summary_pt or content_snippet}"
    return _normalize_text(text)


def cluster_articles_tfidf(
    articles: list[dict[str, Any]],
    threshold: float = DEDUP_SIMILARITY_THRESHOLD,
    time_window_hours: int = DEDUP_TIME_WINDOW_HOURS,
) -> dict[str, list[int]]:
    """
    Cluster articles with TF-IDF cosine similarity over title + summary/content.
    Returns {cluster_id: [indices]} for clusters with at least 2 members.
    """
    if len(articles) < 2:
        return {}

    texts = [_article_text_for_clustering(article) for article in articles]
    if sum(1 for text in texts if text.strip()) < 2:
        return {}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            max_features=10000,
        )
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return {}

    similarity = cosine_similarity(matrix)
    parent = list(range(len(articles)))
    max_delta = timedelta(hours=time_window_hours)

    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            if float(similarity[i, j]) < threshold:
                continue

            timestamp_i = _article_timestamp(articles[i])
            timestamp_j = _article_timestamp(articles[j])
            if (
                timestamp_i is not None
                and timestamp_j is not None
                and abs(timestamp_i - timestamp_j) > max_delta
            ):
                continue
            _union(parent, i, j)

    grouped_by_root: dict[int, list[int]] = {}
    for idx in range(len(articles)):
        root = _find(parent, idx)
        grouped_by_root.setdefault(root, []).append(idx)

    clusters: dict[str, list[int]] = {}
    for members in grouped_by_root.values():
        if len(members) < 2:
            continue
        article_ids = [
            article_id
            for member in members
            for article_id in [articles[member].get("id")]
            if isinstance(article_id, str) and article_id.strip()
        ]
        if len(article_ids) < 2:
            continue
        cluster_id = _make_cluster_id(article_ids)
        clusters[cluster_id] = sorted(members)

    return {cluster_id: clusters[cluster_id] for cluster_id in sorted(clusters)}


def select_canonical(articles: list[dict[str, Any]], cluster_indices: list[int]) -> int:
    """Select canonical article index from a cluster."""

    def _sort_key(index: int) -> tuple[int, int, int, int, str]:
        article = articles[index]
        status = article.get("status")
        status_priority = 0 if status == "curated" else 1

        source_category = (
            article.get("source_category")
            if isinstance(article.get("source_category"), str)
            else ""
        )
        category_priority = SOURCE_CATEGORY_PRIORITY.get(source_category, 99)

        summaries = article.get("summaries")
        has_pt_summary = (
            1
            if isinstance(summaries, dict)
            and isinstance(summaries.get("pt-BR"), str)
            and summaries["pt-BR"].strip()
            else 0
        )

        content = article.get("content") if isinstance(article.get("content"), str) else ""
        content_length = len(content)
        collected_at = (
            article.get("collected_at")
            if isinstance(article.get("collected_at"), str)
            else "9999-12-31T23:59:59Z"
        )
        return (
            status_priority,
            category_priority,
            -has_pt_summary,
            -content_length,
            collected_at,
        )

    return min(cluster_indices, key=_sort_key)


def apply_cluster_decisions(
    articles: list[dict[str, Any]],
    clusters: dict[str, list[int]],
) -> tuple[int, int]:
    """
    Apply canonical + duplicate marks to clustered members.
    Returns (articles_marked_duplicate, clusters_processed).
    """
    marked_duplicates = 0
    clusters_processed = 0

    for cluster_id in sorted(clusters):
        member_indices = clusters[cluster_id]
        if len(member_indices) < 2:
            continue

        canonical_idx = select_canonical(articles, member_indices)
        canonical_id = articles[canonical_idx].get("id")
        canonical_id_value = canonical_id if isinstance(canonical_id, str) else None

        for idx in member_indices:
            article = articles[idx]
            article["narrative_cluster_id"] = cluster_id

            if idx == canonical_idx:
                if not isinstance(article.get("duplicate_of"), str):
                    article["duplicate_of"] = None
                continue

            # Preserve curated outputs from accidental demotion.
            if article.get("status") == "curated":
                continue

            previous_status = article.get("status")
            article["status"] = "irrelevant"
            article["editor_note"] = (
                f"duplicate of {canonical_id_value} in {cluster_id}"
                if canonical_id_value
                else f"duplicate in {cluster_id}"
            )
            article["duplicate_of"] = canonical_id_value
            if previous_status != "irrelevant":
                marked_duplicates += 1

        clusters_processed += 1

    return marked_duplicates, clusters_processed


def is_near_duplicate_fast(
    new_article: dict[str, Any],
    existing_articles: list[dict[str, Any]],
    time_window_hours: int = DEDUP_TIME_WINDOW_HOURS,
) -> str | None:
    """Fast ingestion-time near-duplicate check using title similarity."""
    new_title_raw = new_article.get("title")
    new_title = _normalize_text(new_title_raw if isinstance(new_title_raw, str) else "")
    if not new_title:
        return None

    new_id = new_article.get("id")
    new_timestamp = _article_timestamp(new_article)
    max_delta = timedelta(hours=time_window_hours)

    for existing in existing_articles:
        if existing.get("status") == "irrelevant":
            continue

        existing_title_raw = existing.get("title")
        existing_title = _normalize_text(
            existing_title_raw if isinstance(existing_title_raw, str) else ""
        )
        if not existing_title:
            continue

        existing_timestamp = _article_timestamp(existing)
        if (
            new_timestamp is not None
            and existing_timestamp is not None
            and abs(new_timestamp - existing_timestamp) > max_delta
        ):
            continue

        existing_cluster_id = existing.get("narrative_cluster_id")
        if isinstance(existing_cluster_id, str) and existing_cluster_id.strip():
            resolved_cluster_id = existing_cluster_id
        else:
            existing_id = existing.get("id")
            if isinstance(existing_id, str) and isinstance(new_id, str):
                resolved_cluster_id = _make_cluster_id([existing_id, new_id])
            else:
                resolved_cluster_id = None

        if new_title == existing_title:
            return resolved_cluster_id

        if len(new_title) > 20 and len(existing_title) > 20:
            if new_title in existing_title or existing_title in new_title:
                return resolved_cluster_id

        new_words = set(new_title.split())
        existing_words = set(existing_title.split())
        if not new_words or not existing_words:
            continue
        jaccard = len(new_words & existing_words) / len(new_words | existing_words)
        if jaccard >= DEDUP_JACCARD_THRESHOLD:
            return resolved_cluster_id

    return None
