"""Narrative deduplication for validated/curated articles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.sanitize.dedup import apply_cluster_decisions, cluster_articles_tfidf
except ImportError:  # pragma: no cover - direct script execution path
    from sanitize.dedup import (  # type: ignore[no-redef]
        apply_cluster_decisions,
        cluster_articles_tfidf,
    )

ROOT_DIR = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT_DIR / "site" / "public" / "data" / "articles.json"


def _load_articles_document() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)], payload
    raise ValueError(f"Unsupported articles structure in {ARTICLES_FILE}")


def _save_articles_document(
    articles: list[dict[str, Any]], wrapper: dict[str, Any] | None
) -> None:
    if wrapper is None:
        payload: object = articles
    else:
        wrapper["articles"] = articles
        wrapper["last_updated"] = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        wrapper["total_count"] = len(articles)
        payload = wrapper
    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def deduplicate_narratives() -> tuple[int, int]:
    articles, wrapper = _load_articles_document()

    eligible_indices: list[int] = []
    for idx, article in enumerate(articles):
        if article.get("status") in {"validated", "curated"}:
            eligible_indices.append(idx)
        elif not isinstance(article.get("narrative_cluster_id"), str):
            article["narrative_cluster_id"] = None

    eligible_articles = [articles[idx] for idx in eligible_indices]
    local_clusters = cluster_articles_tfidf(eligible_articles)
    global_clusters = {
        cluster_id: [eligible_indices[local_idx] for local_idx in local_members]
        for cluster_id, local_members in local_clusters.items()
    }

    clustered_global_indices = {
        index for members in global_clusters.values() for index in members
    }
    for idx in eligible_indices:
        if idx not in clustered_global_indices:
            articles[idx]["narrative_cluster_id"] = None
            if not isinstance(articles[idx].get("duplicate_of"), str):
                articles[idx]["duplicate_of"] = None

    grouped_articles = sum(len(members) for members in global_clusters.values())
    duplicates_marked, cluster_count = apply_cluster_decisions(
        articles, global_clusters
    )

    _save_articles_document(articles, wrapper)
    print(
        f"Clusters: {grouped_articles} articles grouped into {cluster_count} clusters "
        f"({duplicates_marked} marked as duplicate)"
    )
    return grouped_articles, cluster_count


def main() -> None:
    deduplicate_narratives()


if __name__ == "__main__":
    main()
