"""Narrative deduplication for validated articles from the last 24 hours."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT_DIR = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT_DIR / "data" / "articles.json"

SIMILARITY_THRESHOLD = 0.85


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _load_articles_document() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)], payload
    raise ValueError(f"Unsupported articles structure in {ARTICLES_FILE}")


def _save_articles_document(articles: list[dict[str, Any]], wrapper: dict[str, Any] | None) -> None:
    if wrapper is None:
        payload: object = articles
    else:
        wrapper["articles"] = articles
        wrapper["last_updated"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        wrapper["total_count"] = len(articles)
        payload = wrapper
    ARTICLES_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _make_cluster_id(article_ids: list[str]) -> str:
    digest = hashlib.sha256("".join(sorted(article_ids)).encode("utf-8")).hexdigest()[:8]
    return f"cluster_{digest}"


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


def deduplicate_narratives() -> tuple[int, int]:
    articles, wrapper = _load_articles_document()
    cutoff = utc_now() - timedelta(hours=24)

    recent_indices: list[int] = []
    recent_titles: list[str] = []
    for idx, article in enumerate(articles):
        if article.get("status") != "validated":
            if not isinstance(article.get("narrative_cluster_id"), str):
                article["narrative_cluster_id"] = None
            continue
        timestamp = _parse_iso8601(article.get("published_at")) or _parse_iso8601(article.get("collected_at"))
        if not timestamp or timestamp < cutoff:
            if not isinstance(article.get("narrative_cluster_id"), str):
                article["narrative_cluster_id"] = None
            continue
        recent_indices.append(idx)
        recent_titles.append(str(article.get("title", "")).strip())
        article["narrative_cluster_id"] = None

    grouped_articles = 0
    cluster_count = 0

    if len(recent_indices) >= 2:
        vectorizer = TfidfVectorizer(lowercase=True, strip_accents="unicode", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(recent_titles)
        similarity = cosine_similarity(matrix)

        parent = list(range(len(recent_indices)))
        for i in range(len(recent_indices)):
            for j in range(i + 1, len(recent_indices)):
                if float(similarity[i, j]) > SIMILARITY_THRESHOLD:
                    _union(parent, i, j)

        groups: dict[int, list[int]] = {}
        for local_idx in range(len(recent_indices)):
            groups.setdefault(_find(parent, local_idx), []).append(local_idx)

        for local_members in groups.values():
            if len(local_members) < 2:
                continue
            article_ids: list[str] = []
            for local_idx in local_members:
                article = articles[recent_indices[local_idx]]
                article_id = article.get("id")
                if isinstance(article_id, str) and article_id:
                    article_ids.append(article_id)
            if not article_ids:
                continue
            cluster_id = _make_cluster_id(article_ids)
            for local_idx in local_members:
                articles[recent_indices[local_idx]]["narrative_cluster_id"] = cluster_id
            grouped_articles += len(local_members)
            cluster_count += 1

    _save_articles_document(articles, wrapper)
    print(f"Clusters: {grouped_articles} articles grouped into {cluster_count} clusters")
    return grouped_articles, cluster_count


def main() -> None:
    deduplicate_narratives()


if __name__ == "__main__":
    main()
