from __future__ import annotations

from scripts.sanitize.dedup import (
    apply_cluster_decisions,
    cluster_articles_tfidf,
    is_near_duplicate_fast,
    select_canonical,
)


def _article(
    article_id: str,
    title: str,
    published_at: str,
    *,
    source_category: str = "mainstream",
    status: str = "validated",
    summary_pt: str = "",
    content: str = "",
) -> dict[str, object]:
    return {
        "id": article_id,
        "title": title,
        "published_at": published_at,
        "collected_at": published_at,
        "source_category": source_category,
        "status": status,
        "summaries": {"pt-BR": summary_pt, "en-US": ""},
        "content": content,
    }


def test_exact_title_match_detected() -> None:
    existing = [
        _article(
            "aaaaaaaaaaaaaaaa",
            "Caiado critica impostos em debate",
            "2026-03-15T10:00:00Z",
        )
    ]
    new_article = _article(
        "bbbbbbbbbbbbbbbb",
        "Caiado critica impostos em debate",
        "2026-03-15T11:00:00Z",
    )
    cluster_id = is_near_duplicate_fast(new_article, existing)
    assert isinstance(cluster_id, str)
    assert cluster_id.startswith("cluster_")


def test_substring_title_match_detected() -> None:
    existing = [
        _article(
            "aaaaaaaaaaaaaaaa",
            "Exportacoes do agro tem melhor resultado",
            "2026-03-15T10:00:00Z",
        )
    ]
    new_article = _article(
        "bbbbbbbbbbbbbbbb",
        "Exportacoes do agro tem melhor resultado no trimestre atual",
        "2026-03-15T10:30:00Z",
    )
    assert is_near_duplicate_fast(new_article, existing) is not None


def test_time_window_respected() -> None:
    existing = [
        _article(
            "aaaaaaaaaaaaaaaa",
            "Caiado critica impostos em debate",
            "2026-03-10T10:00:00Z",
        )
    ]
    new_article = _article(
        "bbbbbbbbbbbbbbbb",
        "Caiado critica impostos em debate",
        "2026-03-13T10:00:00Z",
    )
    assert is_near_duplicate_fast(new_article, existing) is None


def test_different_stories_not_matched() -> None:
    existing = [
        _article("aaaaaaaaaaaaaaaa", "Lula viaja a China", "2026-03-15T10:00:00Z")
    ]
    new_article = _article(
        "bbbbbbbbbbbbbbbb",
        "Caiado propoe reforma administrativa",
        "2026-03-15T10:30:00Z",
    )
    assert is_near_duplicate_fast(new_article, existing) is None


def test_tfidf_clusters_and_selects_canonical() -> None:
    articles = [
        _article(
            "aaaaaaaaaaaaaaaa",
            "Caiado critica impostos em debate",
            "2026-03-15T10:00:00Z",
            source_category="mainstream",
            summary_pt="Caiado critica impostos em debate eleitoral e apresenta argumentos.",
            content="Conteudo sobre critica de impostos no debate eleitoral nacional.",
        ),
        _article(
            "bbbbbbbbbbbbbbbb",
            "Caiado critica impostos em debate eleitoral televisivo",
            "2026-03-15T11:00:00Z",
            source_category="politics",
            summary_pt="Caiado critica impostos em debate eleitoral e detalha propostas.",
            content="Conteudo muito maior para favorecer selecao canonica." * 5,
        ),
        _article(
            "cccccccccccccccc",
            "Tarcisio apresenta proposta de seguranca",
            "2026-03-15T12:00:00Z",
            source_category="mainstream",
        ),
    ]
    clusters = cluster_articles_tfidf(articles)
    assert len(clusters) == 1
    members = next(iter(clusters.values()))
    canonical_idx = select_canonical(articles, members)
    assert canonical_idx == 1


def test_apply_cluster_decisions_marks_non_canonical_irrelevant() -> None:
    articles = [
        _article(
            "aaaaaaaaaaaaaaaa",
            "Caiado critica impostos em debate",
            "2026-03-15T10:00:00Z",
            source_category="politics",
            status="validated",
        ),
        _article(
            "bbbbbbbbbbbbbbbb",
            "Caiado critica impostos em debate televisivo",
            "2026-03-15T10:10:00Z",
            source_category="mainstream",
            status="validated",
        ),
    ]
    cluster_id = "cluster_test1234"
    marked, processed = apply_cluster_decisions(articles, {cluster_id: [0, 1]})

    assert processed == 1
    assert marked == 1
    assert articles[0]["status"] == "validated"
    assert articles[1]["status"] == "irrelevant"
    assert articles[1]["duplicate_of"] == "aaaaaaaaaaaaaaaa"
    assert articles[0]["narrative_cluster_id"] == cluster_id
    assert articles[1]["narrative_cluster_id"] == cluster_id
