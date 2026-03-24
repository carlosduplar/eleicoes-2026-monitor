"""Retroactive sanitization for data/articles.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .constants import RELEVANCE_THRESHOLD
from .dedup import apply_cluster_decisions, cluster_articles_tfidf
from .relevance import compute_relevance_signals, is_relevant_post_llm

ROOT_DIR = Path(__file__).resolve().parents[2]
ARTICLES_FILE = ROOT_DIR / "site" / "public" / "data" / "articles.json"


def _load_articles_document(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)], payload
    raise ValueError(f"Unsupported articles structure in {path}")


def _save_articles_document(
    *,
    path: Path,
    articles: list[dict[str, Any]],
    wrapper: dict[str, Any] | None,
) -> None:
    if wrapper is None:
        payload: object = articles
    else:
        wrapper["articles"] = articles
        wrapper["total_count"] = len(articles)
        payload = wrapper
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _score_bucket(score: float) -> str:
    low = int(score * 10) / 10
    high = min(1.0, low + 0.1)
    return f"{low:.1f}-{high:.1f}"


def batch_cleanup(
    *,
    dry_run: bool = False,
    borderline_llm: bool = False,
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Re-score relevance for all articles and apply duplicate decisions.

    Notes:
    - `borderline_llm` is accepted for CLI compatibility but is currently a no-op.
    - The process is deterministic and safe to run multiple times.
    """
    del borderline_llm

    source_path = ARTICLES_FILE
    destination_path = Path(output_path) if output_path else source_path
    articles, wrapper = _load_articles_document(source_path)

    already_irrelevant = 0
    newly_irrelevant_by_relevance = 0
    relevance_distribution: dict[str, int] = {}

    for article in articles:
        if article.get("status") == "irrelevant":
            already_irrelevant += 1

        is_relevant, score = is_relevant_post_llm(article)
        article["relevance_score"] = score
        article["relevance_signals"] = compute_relevance_signals(article)
        relevance_distribution[_score_bucket(score)] = (
            relevance_distribution.get(_score_bucket(score), 0) + 1
        )

        if article.get("status") == "curated":
            continue

        candidates = article.get("candidates_mentioned")
        topics = article.get("topics")
        multi_candidate = isinstance(candidates, list) and len(candidates) >= 2
        has_eleicoes_topic = isinstance(topics, list) and "eleicoes" in topics

        if not is_relevant and not multi_candidate and not has_eleicoes_topic:
            if article.get("status") != "irrelevant":
                newly_irrelevant_by_relevance += 1
            article["status"] = "irrelevant"
            article["editor_note"] = (
                f"auto-filtered: relevance_score={score:.2f} (< {RELEVANCE_THRESHOLD:.2f})"
            )

    candidate_indices = [
        idx
        for idx, article in enumerate(articles)
        if article.get("status") != "irrelevant"
    ]
    candidate_articles = [articles[idx] for idx in candidate_indices]
    local_clusters = cluster_articles_tfidf(candidate_articles)
    global_clusters = {
        cluster_id: [candidate_indices[local_idx] for local_idx in local_members]
        for cluster_id, local_members in local_clusters.items()
    }
    newly_irrelevant_by_duplicate, clusters_found = apply_cluster_decisions(
        articles, global_clusters
    )

    final_relevant_count = sum(
        1 for article in articles if article.get("status") != "irrelevant"
    )

    summary = {
        "total_articles": len(articles),
        "already_irrelevant": already_irrelevant,
        "newly_irrelevant_by_relevance": newly_irrelevant_by_relevance,
        "newly_irrelevant_by_duplicate": newly_irrelevant_by_duplicate,
        "borderline_kept_by_llm": 0,
        "borderline_removed_by_llm": 0,
        "clusters_found": clusters_found,
        "final_relevant_count": final_relevant_count,
        "relevance_score_distribution": dict(sorted(relevance_distribution.items())),
    }

    if not dry_run:
        _save_articles_document(
            path=destination_path, articles=articles, wrapper=wrapper
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Retroactive articles sanitization")
    parser.add_argument(
        "--dry-run", action="store_true", help="Compute summary without writing output"
    )
    parser.add_argument(
        "--borderline-llm",
        action="store_true",
        help="Reserved flag for future borderline triage",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write sanitized payload to an alternate file path",
    )
    args = parser.parse_args()
    summary = batch_cleanup(
        dry_run=args.dry_run,
        borderline_llm=args.borderline_llm,
        output_path=args.output,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
