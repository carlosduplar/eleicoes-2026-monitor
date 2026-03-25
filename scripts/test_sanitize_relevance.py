from __future__ import annotations

from scripts.sanitize.relevance import (
    compute_relevance_score,
    is_elections_relevant_pre_llm,
    is_relevant_post_llm,
)


def _article(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Base title",
        "source_category": "mainstream",
        "candidates_mentioned": [],
        "topics": [],
        "summaries": {"pt-BR": "", "en-US": ""},
    }
    base.update(overrides)
    return base


def test_candidate_mention_gives_high_score() -> None:
    article = _article(candidates_mentioned=["lula", "tarcisio"])
    score = compute_relevance_score(article)
    assert 0.5 <= score <= 1.0


def test_eleicoes_topic_with_brazil_context_is_relevant_post_llm() -> None:
    article = _article(
        topics=["eleicoes"],
        summaries={"pt-BR": "Eleicoes no Brasil", "en-US": "Elections in Brazil"},
    )
    is_relevant, score = is_relevant_post_llm(article)
    assert is_relevant is True
    assert score >= 0.25


def test_eleicoes_topic_without_brazil_context_is_irrelevant_post_llm() -> None:
    article = _article(topics=["eleicoes"])
    is_relevant, score = is_relevant_post_llm(article)
    assert is_relevant is False
    assert score >= 0.25


def test_international_election_without_brazil_context_is_filtered() -> None:
    article = _article(
        topics=["eleicoes", "politica_externa"],
        summaries={
            "pt-BR": "Eleicoes na Francia, extrema-direita sofre derrotas",
            "en-US": "France elections, far-right suffers defeats",
        },
    )
    is_relevant, score = is_relevant_post_llm(article)
    assert is_relevant is False


def test_pure_economics_gives_low_score() -> None:
    article = _article(
        topics=["economia"],
        summaries={"pt-BR": "Mercado e inflacao", "en-US": "Markets and inflation"},
    )
    is_relevant, score = is_relevant_post_llm(article)
    assert score < 0.30
    assert is_relevant is False


def test_international_only_is_filtered_pre_llm() -> None:
    title = "Sentimento do consumidor nos EUA cai com pressao do Fed e Nasdaq"
    content = "Dados dos Estados Unidos mostram recuo no consumer sentiment e impacto em Wall Street."
    assert is_elections_relevant_pre_llm(title=title, content=content) is False


def test_obvious_election_article_passes_pre_llm() -> None:
    title = "Lula lidera pesquisa eleitoral para 2026"
    content = (
        "Pesquisa eleitoral aponta disputa presidencial acirrada com varios candidatos."
    )
    assert is_elections_relevant_pre_llm(title=title, content=content) is True


def test_empty_article_gives_zero() -> None:
    assert compute_relevance_score(_article()) == 0.0


def test_score_is_deterministic() -> None:
    article = _article(
        candidates_mentioned=["lula"],
        topics=["corrupcao"],
        summaries={"pt-BR": "Lula em campanha para 2026", "en-US": "Campaign context"},
        source_category="politics",
    )
    first = compute_relevance_score(article)
    second = compute_relevance_score(article)
    assert first == second


def test_score_range() -> None:
    article = _article(
        candidates_mentioned=["lula", "tarcisio", "caiado"],
        topics=["eleicoes", "corrupcao", "impostos", "privatizacao"],
        source_category="party",
        summaries={"pt-BR": "eleicoes eleicao candidato voto", "en-US": "election"},
    )
    score = compute_relevance_score(article)
    assert 0.0 <= score <= 1.0
