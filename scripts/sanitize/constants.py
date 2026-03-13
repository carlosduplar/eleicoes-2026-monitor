"""Shared constants for sanitization logic."""

from __future__ import annotations

from typing import Final

ELECTIONS_HIGH_SIGNAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "eleicao",
        "eleicoes",
        "eleitoral",
        "eleitor",
        "eleitores",
        "candidato",
        "candidatos",
        "candidatura",
        "campanha eleitoral",
        "intencao de voto",
        "pesquisa eleitoral",
        "pesquisa de voto",
        "debate presidencial",
        "plano de governo",
        "segundo turno",
        "primeiro turno",
        "turno",
        "terceira via",
        "presidencia",
        "presidencial",
        "pre candidato",
        "pre-candidato",
        "urna",
        "urnas",
        "votacao",
        "voto",
        "votos",
        "tse",
        "reeleicao",
        "reeleito",
        "2026",
    }
)

CANDIDATE_SIGNAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "lula",
        "bolsonaro",
        "flavio bolsonaro",
        "tarcisio",
        "caiado",
        "zema",
        "ratinho jr",
        "eduardo leite",
        "aldo rebelo",
        "renan santos",
    }
)

BRAZIL_CONTEXT_KEYWORDS: frozenset[str] = frozenset(
    {
        "brasil",
        "brasileiro",
        "brasileira",
        "brasilia",
        "palacio do planalto",
        "planalto",
        "governo federal",
        "camara dos deputados",
        "senado federal",
        "tse",
        "stf",
        "supremo",
    }
)

OFF_TOPIC_KEYWORDS: frozenset[str] = frozenset(
    {
        "futebol",
        "esporte",
        "campeonato",
        "novela",
        "entretenimento",
        "celebridade",
        "filme",
        "serie",
        "horoscopo",
        "receita",
        "culinaria",
        "bem estar",
        "saude",
        "dieta",
        "musica",
    }
)

INTERNATIONAL_ONLY_KEYWORDS: frozenset[str] = frozenset(
    {
        "eua",
        "estados unidos",
        "trump",
        "biden",
        "china",
        "europa",
        "russia",
        "ucrania",
        "fed ",
        "federal reserve",
        "wall street",
        "nasdaq",
        "dow jones",
        "s&p 500",
        "consumer sentiment",
    }
)

CANONICAL_CANDIDATE_SLUGS = {
    "lula",
    "flavio-bolsonaro",
    "caiado",
    "zema",
    "eduardo-leite",
    "aldo-rebelo",
    "renan-santos",
    "ratinho-jr",
    "tarcisio",
}

CANDIDATE_ALIASES = {
    "lula": "lula",
    "luiz inacio lula da silva": "lula",
    "flavio bolsonaro": "flavio-bolsonaro",
    "flavio-bolsonaro": "flavio-bolsonaro",
    "caiado": "caiado",
    "ronaldo caiado": "caiado",
    "zema": "zema",
    "romeu zema": "zema",
    "eduardo leite": "eduardo-leite",
    "eduardo-leite": "eduardo-leite",
    "aldo rebelo": "aldo-rebelo",
    "aldo-rebelo": "aldo-rebelo",
    "renan santos": "renan-santos",
    "renan-santos": "renan-santos",
    "ratinho jr": "ratinho-jr",
    "ratinho-jr": "ratinho-jr",
    "carlos massa ratinho jr": "ratinho-jr",
    "carlos massa ratinho junior": "ratinho-jr",
    "tarcisio": "tarcisio",
    "tarcisio de freitas": "tarcisio",
}

POLITICAL_TOPICS: frozenset[str] = frozenset(
    {"corrupcao", "impostos", "privatizacao", "previdencia"}
)

RELEVANCE_THRESHOLD: Final[float] = 0.30
BORDERLINE_LOW: Final[float] = 0.20
BORDERLINE_HIGH: Final[float] = 0.35
DEDUP_SIMILARITY_THRESHOLD: Final[float] = 0.75
DEDUP_JACCARD_THRESHOLD: Final[float] = 0.80
DEDUP_TIME_WINDOW_HOURS: Final[int] = 48

SOURCE_CATEGORY_PRIORITY = {
    "politics": 1,
    "mainstream": 2,
    "magazine": 3,
    "institutional": 4,
    "international": 5,
    "party": 6,
    "social": 7,
}

SOURCE_CATEGORY_WEIGHTS = {
    "politics": 0.95,
    "mainstream": 0.8,
    "magazine": 0.7,
    "international": 0.65,
    "institutional": 0.6,
    "party": 0.55,
    "social": 0.5,
}
