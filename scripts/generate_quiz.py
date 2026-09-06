"""Generate quiz.json from candidates_positions.json knowledge base."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from . import ai_client
from .ai_client import generate_quiz_topic_options, validate_quiz_option_quality

logger = logging.getLogger(__name__)

try:
    from scripts.store import ROOT_DIR, PUB_DATA_DIR
except ImportError:  # pragma: no cover - direct script execution path
    from store import ROOT_DIR, PUB_DATA_DIR
POSITIONS_FILE = PUB_DATA_DIR / "candidates_positions.json"
QUIZ_FILE = PUB_DATA_DIR / "quiz.json"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "quiz.schema.json"

OPTION_IDS = ["opt_a", "opt_b", "opt_c", "opt_d", "opt_e", "opt_f"]
MIN_OPTIONS_PER_TOPIC = 3
KNOWN_POSITION_TYPES = {"confirmed", "inferred"}
STANCE_TO_WEIGHT = {
    "strongly_favor": 3,
    "favor": 2,
    "neutral": 0,
    "against": -2,
    "strongly_against": -3,
}
WEIGHT_RANGE_NORMALIZER = 6.0
BANNED_EVENT_TERMS = (
    "pesquisa",
    "investigação",
    "investigacao",
    "inquérito",
    "inquerito",
    "percentual",
    "sondagem",
    "denúncia",
    "denuncia",
)
BANNED_NAME_TERMS = (
    "lula",
    "luiz inacio",
    "luiz inácio",
    "inacio lula",
    "inácio lula",
    "bolsonaro",
    "jair",
    "flavio",
    "flávio",
    "caiado",
    "ronaldo",
    "zema",
    "romeu",
    "renan santos",
    "renan",
    "augusto cury",
    "augusto",
    "cury",
    "edmilson costa",
    "edmilson",
    "hertz dias",
    "hertz",
    "samara martins",
    "samara",
    "wilson grassi",
    "wilson",
    "clariana barao",
    "clariana",
    "barao",
    "barão",
    "zacarkim",
    "rui costa pimenta",
    "rui pimenta",
    "pimenta",
    "pablo marcal",
    "pablo",
    "marcal",
    "marçal",
)
# Office titles, program/agency proper nouns and government-history phrases
# that de-anonymize an option even without naming the candidate (strict mode).
BANNED_BIO_TERMS = (
    "ibama",
    "icmbio",
    "funai",
    "fundo amazonia",
    "fundo amazônia",
    "amazon fund",
    "ministerio do meio ambiente",
    "ministério do meio ambiente",
    "ministry of the environment",
    "cop30",
    "cop 30",
    "prouni",
    "fies",
    "escola sem partido",
    "excludente de ilicitude",
    "maioridade penal",
    "pena de morte",
    "governador",
    "governadora",
    "ex-governador",
    "presidente",
    "ex-presidente",
    "ministro",
    "ministra",
    "deputado",
    "deputada",
    "senador",
    "senadora",
    "prefeito",
    "vereadora",
    "vereador",
    "durante seu governo",
    "during his government",
    "during her government",
    "no meu governo",
    "quando fui",
    "meu mandato",
    "minha gestao como",
    "minha gestão como",
    "governo lula",
    "governo bolsonaro",
    "como membro do governo",
)
BANNED_PARTY_TERMS = (
    "pt",
    "partido dos trabalhadores",
    "pl",
    "partido liberal",
    "psol",
    "partido socialismo e liberdade",
    "pcb",
    "partido comunista brasileiro",
    "pcdob",
    "pc do b",
    "partido comunista do brasil",
    "pdt",
    "partido democrático trabalhista",
    "partido democratico trabalhista",
    "psb",
    "partido socialista brasileiro",
    "psdb",
    "partido da social democracia brasileira",
    "mdb",
    "movimento democrático brasileiro",
    "movimento democratico brasileiro",
    "pmdb",
    "psd",
    "partido social democrático",
    "partido social democratico",
    "pp",
    "progressistas",
    "partido progressista",
    "republicanos",
    "união brasil",
    "uniao brasil",
    "novo",
    "podemos",
    "solidariedade",
    "avante",
    "cidadania",
    "pv",
    "partido verde",
    "rede",
    "rede sustentabilidade",
    "agir",
    "dc",
    "democracia cristã",
    "democracia crista",
    "dem",
    "democratas",
    "patriota",
    "prd",
    "prtb",
    "pmb",
    "partido da mulher brasileira",
    "mobiliza",
    "pmn",
    "psc",
    "pros",
    "ptb",
    "pco",
    "partido da causa operária",
    "partido da causa operaria",
    "up",
    "unidade popular",
    "pstu",
    "mbl",
    "movimento brasil livre",
)
_AMBIGUOUS_PARTY_TERMS = {
    "novo",
    "podemos",
    "solidariedade",
    "avante",
    "cidadania",
    "rede",
    "agir",
    "patriota",
    "mobiliza",
}
_PARTY_CONTEXT_PATTERN = re.compile(
    r"\b(?:partido|legenda|sigla|filiad[oa]|membro|integrante|aliado|alian[aç]a|"
    r"movimento)\b",
    flags=re.IGNORECASE,
)
BANNED_OPTION_OPENINGS_PT = (
    "o governo deveria adotar uma política pública clara e estável em que",
)
BANNED_OPTION_OPENINGS_EN = (
    "the government should adopt a clear and stable public policy in which",
)

CORE_SIMILARITY_THRESHOLD = 0.6
MAX_FALLBACK_SHARE = 1.0 / 3.0

# Intro phrases stripped from option texts before deduplication so that
# same-stance fallback templates differing only by the seed-chosen intro are
# still recognized as near-duplicates.
_CORE_INTROS_PT = (
    "defendo que",
    "acredito que",
    "eu acredito que",
    "entendo que",
    "na minha visão,",
    "na minha visão",
    "na minha visao,",
    "na minha visao",
    "considero que",
    "para mim,",
    "para mim",
    "minha posição é que",
    "minha posicao e que",
    "sustento que",
    "prefiro que",
    "quero que",
    "sou favorável a que",
    "sou contra",
    "o governo",
    "o estado",
)
_CORE_INTROS_EN = (
    "i believe the government should",
    "i argue the government should",
    "in my view, the government should",
    "i support the government choosing to",
    "i maintain the government should",
    "my position is the government should",
    "i hold the government should",
    "i contend the government should",
    "i understand that the government should",
    "i consider that the government should",
    "the government should",
    "the state should",
)
_CORE_TAILS = (
    "com avaliação independente e dados públicos",
    "com metas anuais e auditoria externa",
    "com revisão periódica e relatório público",
    "com transparência orçamentária total",
    "com indicadores trimestrais públicos",
    "com prazo definido e prestação de contas",
    "com metas transparentes e revisão periódica",
    "com metas transparentes e avaliação periódica",
    "com metas objetivas e revisão periódica",
    "with independent evaluation and public data",
    "with annual targets and external audit",
    "with periodic review and public reporting",
    "with full budget transparency",
    "with public quarterly indicators",
    "with a set deadline and accountability",
    "with transparent goals and periodic review",
    "with transparent targets and periodic review",
    "with objective targets and periodic review",
)

_THIRD_PERSON_LEAK_PATTERNS = (
    r"\bo\s+candidato\b",
    r"\ba\s+candidata\b",
    r"\bcandidat[oa]s?\b",
    r"\bo\s+pol[ií]tico\b",
    r"\ba\s+pol[ií]tica\s+(?:é|e|defende|apoia|apoiam|afirma|diz|quer|pretende)\b",
    r"\bseu\s+partido\b",
    r"\bsua\s+legenda\b",
    r"\bo\s+partido\b",
    r"\bfiliad[oa]\b",
    r"\bcomo\s+membro\b",
    r"\bintegrante\b",
    r"\bn[aã]o\s+h[aá]\s+men[cç][aã]o\b",
    r"\bn[aã]o\s+h[aá]\s+informa",
    r"\binforma[cç][oõ]es?\s+suficientes\b",
    r"\bnot\s+enough\s+information\b",
    r"\bcomo\s+promulgado\b",
    r"\bcomo\s+governador\b",
    r"\bdurante\s+(seu|meu)\s+governo\b",
    r"\bquando\s+fui\b",
    r"\bpode\s+ser\s+inferid",
    r"\bprovavelmente\b",
    r"\bthe\s+candidate\b",
    r"\bthe\s+politician\b",
    r"\bcandidate\s+(prioritizes?|supports?|is|opposes?)\b",
    r"\bpolitician\s+(is|supports?|favors?|favours?)\b",
    r"\bhis\s+party\b",
    r"\bher\s+party\b",
    r"\bthe\s+party\b",
    r"\bthere\s+is\s+no\s+direct\s+mention\b",
    r"\bcan\s+be\s+inferred\b",
    r"\bprobably\b",
    r"\baccording\s+to\s+wikipedia\b",
    r"\bdados\s+da\s+wikipedia\b",
    r"\bdata\s+from\s+wikipedia\b",
)
# Template-appendage phrasing from the old fallback generator. These markers
# are banned outright: they break first-person voice, leak third-person
# summaries, and caused PT/EN divergence (appendage present in one language).
_TEMPLATE_APPENDAGE_PATTERNS = (
    r"e\s+um\s+ponto\s+central",
    r"additionally,?\s+a\s+central\s+point",
    r"al[eé]m\s+disso,?\s+proponho",
)

# Hint fragments (summary/action excerpts) that cannot compose grammatically
# into a first-person fallback sentence are dropped instead of appended raw.
_PT_HINT_REJECT_STARTS = (
    "embora",
    "que",
    "porque",
    "porem",
    "porém",
    "mas",
    "se",
    "como",
    "quando",
    "apesar",
    "ele",
    "ela",
    "eles",
    "elas",
    "seu",
    "sua",
    "seus",
    "suas",
    "eu",
    "voce",
    "você",
    "e",
    "é",
    "ha",
    "há",
    "foi",
    "tem",
    "reduz",
    "propoe",
    "propõe",
    "quer",
    "deve",
    "vai",
    "afirma",
    "garante",
)
_EN_HINT_REJECT_STARTS = (
    "although",
    "because",
    "but",
    "however",
    "if",
    "as",
    "when",
    "he",
    "she",
    "they",
    "his",
    "her",
    "their",
    "i",
    "you",
    "is",
    "are",
    "was",
    "were",
    "has",
    "had",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "should",
    "must",
)
_PT_VERB_START_REJECT = re.compile(
    r"^[a-záéíóúâêôãõç]{2,}(?:ou|eu|iu|ava|era|ei|ia|emos|amos|em|am|e|a)\b",
    re.IGNORECASE,
)
_EN_VERB_SUFFIX_REJECT = re.compile(r"^[a-z]{2,}(?:s|ed|ing)\b", re.IGNORECASE)

_JUNK_SOURCE_PATTERNS = (
    r"dados\s+da\s+wikipedia",
    r"data\s+from\s+wikipedia",
    r"^\s*(n/?a|sem\s+fontes?|source\s+not\s+found|wikipedia)\s*$",
    r"^\s*para\s+[a-z-]+\s*$",
)

QUESTION_TEMPLATES = {
    "economia": (
        "Qual deve ser a prioridade na política econômica do governo federal?",
        "What should be the federal government's top economic policy priority?",
    ),
    "seguranca": (
        "Qual estratégia deve guiar a política nacional de segurança pública?",
        "Which strategy should guide national public security policy?",
    ),
    "saude": (
        "Qual deve ser o papel do Estado no financiamento do sistema de saúde público?",
        "What should be the State's role in funding the public health system?",
    ),
    "educacao": (
        "Qual caminho deve orientar os investimentos em educação no país?",
        "Which path should guide education investments in the country?",
    ),
    "meio_ambiente": (
        "Como o Brasil deve equilibrar desenvolvimento econômico e proteção ambiental?",
        "How should Brazil balance economic development and environmental protection?",
    ),
    "corrupcao": (
        "Qual medida é mais efetiva para reduzir corrupção na administração pública?",
        "Which measure is most effective to reduce corruption in public administration?",
    ),
    "armas": (
        "Como deve ser a política de acesso e controle de armas no Brasil?",
        "How should Brazil regulate firearm access and control?",
    ),
    "previdencia": (
        "Qual direção deve orientar a política de previdência social?",
        "What direction should guide social security policy?",
    ),
    "politica_externa": (
        "Qual postura internacional o Brasil deve priorizar nos próximos anos?",
        "Which international posture should Brazil prioritize in the coming years?",
    ),
    "lgbtq": (
        "Qual deve ser a prioridade das políticas públicas para direitos LGBTQIA+?",
        "What should be the priority of public policy for LGBTQIA+ rights?",
    ),
    "aborto": (
        "Como a legislação sobre aborto deve ser tratada no Brasil?",
        "How should abortion legislation be handled in Brazil?",
    ),
    "indigenas": (
        "Qual deve ser a prioridade das políticas para povos indígenas?",
        "What should be the priority for Indigenous peoples policies?",
    ),
    "impostos": (
        "Qual abordagem tributária deve orientar a política fiscal brasileira?",
        "Which tax approach should guide Brazilian fiscal policy?",
    ),
    "midia": (
        "Qual deve ser o papel do Estado na regulação de mídia e plataformas digitais?",
        "What should be the State's role in regulating media and digital platforms?",
    ),
}


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _load_positions_payload() -> dict[str, object]:
    payload = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Invalid data/candidates_positions.json structure.")
    return payload


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".json.tmp")
    temp_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_file.replace(path)


def _load_existing_quiz_if_valid(schema: dict[str, object]) -> dict[str, object] | None:
    if not QUIZ_FILE.exists():
        return None
    try:
        existing = json.loads(QUIZ_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(existing, dict):
        return None
    try:
        jsonschema.validate(existing, schema)
    except jsonschema.ValidationError:
        return None
    return existing


def _topic_positions(topic_payload: dict[str, object]) -> list[dict[str, object]]:
    candidates = topic_payload.get("candidates")
    if not isinstance(candidates, dict):
        return []
    known: list[dict[str, object]] = []
    for candidate_slug, candidate_position in candidates.items():
        if not isinstance(candidate_position, dict):
            continue
        position_type = candidate_position.get("position_type")
        stance = candidate_position.get("stance")
        if position_type not in KNOWN_POSITION_TYPES or stance not in STANCE_TO_WEIGHT:
            continue
        known.append(
            {
                "candidate_slug": candidate_slug,
                "position_type": position_type,
                "stance": stance,
                "summary_pt": _normalize_text(candidate_position.get("summary_pt")),
                "summary_en": _normalize_text(candidate_position.get("summary_en")),
                "key_actions": candidate_position.get("key_actions")
                if isinstance(candidate_position.get("key_actions"), list)
                else [],
                "sources": candidate_position.get("sources")
                if isinstance(candidate_position.get("sources"), list)
                else [],
            }
        )
    return known


def divergence_score(positions: list[dict[str, object]]) -> float:
    weights = [
        STANCE_TO_WEIGHT[str(position["stance"])]
        for position in positions
        if position.get("stance") in STANCE_TO_WEIGHT
    ]
    if len(weights) < 2:
        return 0.0
    return (max(weights) - min(weights)) / WEIGHT_RANGE_NORMALIZER


def select_topics(positions_payload: dict[str, object]) -> list[str]:
    topics = positions_payload.get("topics")
    if not isinstance(topics, dict):
        return []
    scored: list[tuple[str, float, int]] = []
    for topic_id, topic_payload in topics.items():
        if not isinstance(topic_payload, dict):
            continue
        known = _topic_positions(topic_payload)
        if len(known) < 3:
            continue
        score = divergence_score(known)
        scored.append((topic_id, score, len(known)))
    scored.sort(key=lambda item: (-item[1], -item[2], item[0]))
    return [item[0] for item in scored[:15]]


def build_question_text(topic_id: str) -> tuple[str, str]:
    if topic_id in QUESTION_TEMPLATES:
        return QUESTION_TEMPLATES[topic_id]
    topic_label = topic_id.replace("_", " ")
    return (
        f"Qual é a sua posição sobre {topic_label}?",
        f"What is your position on {topic_label}?",
    )


def _normalize_word_count(text: str) -> int:
    return len([chunk for chunk in re.split(r"\s+", text.strip()) if chunk])


def _strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def _looks_like_first_person_position(text_pt: str) -> bool:
    starters = (
        "o governo",
        "o estado",
        "acredito que",
        "eu acredito que",
        "a prioridade",
        "é fundamental",
        "e fundamental",
        "defendo que",
        "eu defendo",
        "sou favorável",
        "sou favoravel",
        "sou contra",
        "considero que",
        "entendo que",
        "prefiro que",
        "quero que",
        "na minha visão",
        "na minha visao",
        "para mim",
        "minha posição",
        "minha posicao",
        "sustento que",
        "não apoio que",
    )
    normalized = re.sub(r"\s+", " ", text_pt.strip().lower())
    return any(normalized.startswith(prefix) for prefix in starters)


def _contains_banned_terms(text: str, banned_terms: tuple[str, ...]) -> bool:
    normalized = _strip_accents(text.lower())
    for term in banned_terms:
        folded = _strip_accents(term.lower())
        if len(folded) <= 3 and folded.isalpha():
            if re.search(rf"\b{re.escape(folded)}\b", normalized):
                return True
            continue
        if " " in folded:
            if folded in normalized:
                return True
            continue
        if re.search(rf"\b{re.escape(folded)}\b", normalized):
            return True
    return False


def _contains_party_reference(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if not normalized:
        return False
    affiliation_patterns = (
        r"\bpartido\b.*\b(partido|psdb|pt|pl|psol|mbl|republicanos|un[iã]o\s*brasil|novo|mdb|pdt|psb|pp|psd|pv|dc|dem)\b",
        r"\bcomo\s+membro\b",
        r"\bfiliad[oa]\b.*\b(partido|movimento)\b",
        r"\bintegrante\b.*\b(partido|movimento)\b",
        r"\bo\s+partido\b",
    )
    for pat in affiliation_patterns:
        if re.search(pat, normalized):
            return True
    has_context_marker = bool(_PARTY_CONTEXT_PATTERN.search(normalized))
    for term in BANNED_PARTY_TERMS:
        escaped = re.escape(term)
        if term in _AMBIGUOUS_PARTY_TERMS:
            if has_context_marker and re.search(rf"\b{escaped}\b", normalized):
                return True
            continue
        if re.search(rf"\b{escaped}\b", normalized):
            return True
    return False


def _normalize_option_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"[^\w\s]", "", normalized, flags=re.UNICODE)


def _content_core(text: str) -> str:
    """Return the option text with intro phrase and fixed tail stripped.

    Two options sharing a content core are near-duplicates even when a
    different seed-chosen intro masks an exact fingerprint match.
    """
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    changed = True
    while changed:
        changed = False
        for intro in _CORE_INTROS_PT + _CORE_INTROS_EN:
            if normalized.startswith(intro):
                normalized = normalized[len(intro) :].lstrip()
                if normalized.startswith(","):
                    normalized = normalized[1:].lstrip()
                changed = True
                break
    for tail in _CORE_TAILS:
        normalized = normalized.replace(tail, " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _core_similarity(core_a: str, core_b: str) -> float:
    tokens_a = set(re.findall(r"\w+", core_a))
    tokens_b = set(re.findall(r"\w+", core_b))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _sentence_count(text: str) -> int:
    return len([chunk for chunk in re.split(r"[.!?…]+", text) if chunk.strip()])


def _local_quality_check(text_pt: str, text_en: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    word_count = _normalize_word_count(text_pt)
    normalized_pt = re.sub(r"\s+", " ", text_pt.strip().lower())
    normalized_en = re.sub(r"\s+", " ", text_en.strip().lower())
    if word_count < 15 or word_count > 80:
        failures.append("length")
    if not _looks_like_first_person_position(text_pt):
        failures.append("first_person")
    if _contains_banned_terms(text_pt, BANNED_NAME_TERMS) or _contains_banned_terms(
        text_en, BANNED_NAME_TERMS
    ):
        failures.append("candidate_reference")
    if _contains_banned_terms(text_pt, BANNED_BIO_TERMS) or _contains_banned_terms(
        text_en, BANNED_BIO_TERMS
    ):
        failures.append("bio_reference")
    if _contains_party_reference(text_pt) or _contains_party_reference(text_en):
        failures.append("party_reference")
    if _contains_banned_terms(text_pt, BANNED_EVENT_TERMS):
        failures.append("news_event")
    if any(normalized_pt.startswith(prefix) for prefix in BANNED_OPTION_OPENINGS_PT):
        failures.append("boilerplate")
    if any(normalized_en.startswith(prefix) for prefix in BANNED_OPTION_OPENINGS_EN):
        failures.append("boilerplate")
    for leak_pattern in _THIRD_PERSON_LEAK_PATTERNS:
        if re.search(leak_pattern, normalized_pt) or re.search(
            leak_pattern, normalized_en
        ):
            failures.append("third_person_leak")
            break
    for appendage_pattern in _TEMPLATE_APPENDAGE_PATTERNS:
        if re.search(appendage_pattern, normalized_pt) or re.search(
            appendage_pattern, normalized_en
        ):
            failures.append("template_appendage")
            break
    if abs(_sentence_count(text_pt) - _sentence_count(text_en)) > 1:
        failures.append("en_pt_mismatch")
    broken_continuation_patterns = (
        r"\b(isso\s+inclui\s+[a-zéêãõ]{1,4}\s)",  # "Isso inclui é", "Isso inclui o"
        r"\b(tamb[eé]m\s+[eé]\s+essencial\s+[a-zéêãõ]{1,4}\s)",  # "Também é essencial apoiou"
        r"\b(\b[a-zéêãõ]{1,2}\b\s){3,}",  # 3+ one/two-char words in a row (glue fragments like "é a o")
        r",\s*,",  # double comma
        r"apoiou\s+a\s+reforma|defendeu\s+a\s+reforma|apoia\s+a\s+reforma|votou\s+a\s+favor\s+do\s+processo",
        r"dados\s+da\s+wikipedia",
        r"\.\s+na\s+pauta\s+de\b",  # sentence fragment like ". na pauta de"
        r"\bpolicy\s+for\b.*\bshould\s+(?:supports|advocates|prefers|defends)\b",
        r"\bi\s+believe\s+the\s+policy\s+for\b",
        r"^\s*here\s+is\s+the\s+json\s+requested\b",
        r"\bacidentalmente\b",  # nonsense qualifier ("acidentalmente interrompem")
        r"\baccidentally\s+interrupt\b",
    )
    for pat in broken_continuation_patterns:
        if re.search(pat, normalized_pt) or re.search(pat, normalized_en):
            failures.append("broken_continuation")
            break
    return (len(failures) == 0, failures)


# Stance direction verbs for the deterministic fallback. The verb carries the
# stance; the per-topic instrument carries the substance. Instruments are bare
# noun phrases (no leading article) so every verb composes grammatically.
_STANCE_VERB_PT = {
    "strongly_favor": "amplie recursos para",
    "favor": "fortaleça",
    "neutral": "avalie com critérios técnicos",
    "against": "restrinja",
    "strongly_against": "impeça novas obrigações em",
}
_STANCE_VERB_EN = {
    "strongly_favor": "expand funding for",
    "favor": "strengthen",
    "neutral": "review against technical criteria",
    "against": "limit",
    "strongly_against": "block new mandates on",
}

_FALLBACK_INTROS_PT = [
    "Defendo que",
    "Acredito que",
    "Entendo que",
    "Na minha visão,",
    "Considero que",
    "Para mim,",
    "Minha posição é que",
    "Sustento que",
]
_FALLBACK_INTROS_EN = [
    "I believe the government should",
    "I argue the government should",
    "In my view, the government should",
    "I support the government choosing to",
    "I maintain the government should",
    "My position is the government should",
    "I hold the government should",
    "I contend the government should",
]

_FALLBACK_CLOSINGS_PT = [
    "com avaliação independente e dados públicos",
    "com metas anuais e auditoria externa",
    "com revisão periódica e relatório público",
    "com transparência orçamentária total",
    "com indicadores trimestrais públicos",
    "com prazo definido e prestação de contas",
]
_FALLBACK_CLOSINGS_EN = [
    "with independent evaluation and public data",
    "with annual targets and external audit",
    "with periodic review and public reporting",
    "with full budget transparency",
    "with public quarterly indicators",
    "with a set deadline and accountability",
]

# Concrete, stance-neutral policy instruments per topic (bare noun phrases).
# The stance verb provides direction; the instrument provides substance so two
# same-topic options never share the generic "reformas graduais" template.
_TOPIC_INSTRUMENTS_PT: dict[str, list[str]] = {
    "economia": [
        "investimento em infraestrutura com seleção por retorno auditado e concessões reguladas",
        "controle de gastos com limite fiscal e revisão anual de subsídios",
        "crédito a pequenas empresas com garantia pública e juros condicionados a emprego",
        "simplificação de tributos sobre consumo com unificação e devolução a baixa renda",
    ],
    "seguranca": [
        "policiamento comunitário com câmeras corporais e metas públicas de letalidade",
        "progressão de penas condicionada a trabalho e estudo com monitoramento eletrônico",
        "inteligência contra facções com integração de bancos de dados e operações conjuntas",
        "prevenção à violência com escolas de tempo integral e iluminação em áreas críticas",
    ],
    "saude": [
        "financiamento da saúde pública com piso vinculado e ordem de espera publicada",
        "atenção básica com equipes de saúde da família e visitas domiciliares ampliadas",
        "compra centralizada de medicamentos com pregão nacional e estoque monitorado",
        "telemedicina pública com prontuário único e consultas agendadas por aplicativo",
    ],
    "educacao": [
        "orçamento de universidades federais com avaliação de desempenho e vagas ampliadas",
        "ensino técnico com vagas vinculadas a arranjos produtivos e estágio remunerado",
        "alfabetização na idade certa com material nacional e tutoria individual",
        "escolas de tempo integral com refeição, transporte e atividades culturais",
    ],
    "meio_ambiente": [
        "fiscalização do desmatamento com operações anuais, multas públicas e embargo imediato",
        "licenciamento ambiental com prazos máximos e decisões publicadas na internet",
        "recuperação de áreas degradadas com fundo auditado e metas por bioma",
        "crédito a produção de baixo carbono condicionado a compromissos verificáveis",
    ],
    "corrupcao": [
        "transparência de gastos com portal em tempo real e auditoria externa anual",
        "carreiras técnicas com concurso público e proteção legal a denunciantes",
        "licitações eletrônicas com atas públicas e disputa aberta de preços",
        "corregedorias independentes com prazos máximos de apuração e punição publicada",
    ],
    "armas": [
        "registro nacional de armas com rastreio balístico e renovação periódica",
        "fiscalização de clubes de tiro com vistorias anuais e limite de munição",
        "campanhas de entrega voluntária com indenização e destruição pública do arsenal",
        "porte restrito a categorias funcionais com avaliação psicológica periódica",
    ],
    "previdencia": [
        "idade mínima com transição por pontos e pedágio proporcional ao tempo restante",
        "alíquota progressiva com teto vinculado ao salário mínimo",
        "revisão de benefícios por incapacidade com perícia periódica e reabilitação",
        "previdência complementar pública com adesão automática e portabilidade",
    ],
    "politica_externa": [
        "acordos comerciais com cotas agrícolas e salvaguardas contra concorrência desleal",
        "cooperação ambiental com fundo internacional auditado e metas compartilhadas",
        "atuação multilateral com votos publicados e candidaturas a conselhos",
        "proteção a brasileiros no exterior com consulados de plantão e repatriação",
    ],
    "lgbtq": [
        "atendimento especializado à saúde com protocolo nacional e ambulatórios regionais",
        "combate à violência com delegacias capacitadas e estatísticas públicas",
        "inclusão no emprego com aprendizagem profissional e metas de contratação",
        "apoio psicossocial com centros de referência e linha nacional de ajuda",
    ],
    "aborto": [
        "atendimento nos casos previstos em lei com protocolo hospitalar e prazo máximo",
        "saúde materna com pré-natal universal e maternidades regionalizadas",
        "educação sexual nas escolas com material científico e formação docente",
        "apoio à gestante com licença estendida e vagas garantidas em creches",
    ],
    "indigenas": [
        "demarcação de terras com laudos antropológicos e prazo judicial definido",
        "saúde indígena com distritos sanitários e equipes permanentes",
        "educação bilíngue com material próprio e formação de professores nativos",
        "fiscalização contra garimpo ilegal com operações conjuntas e embargo",
    ],
    "impostos": [
        "progressividade com isenção até faixa salarial e alíquota maior no topo",
        "simplificação com imposto único sobre consumo e devolução a baixa renda",
        "revisão de isenções setoriais com custo-benefício publicado anualmente",
        "tributação de lucros distribuídos com tabela anual e compensação",
    ],
    "midia": [
        "transparência de algoritmos com relatórios públicos e auditoria independente",
        "moderação de conteúdo com direito de resposta e prazos de recurso",
        "fomento ao jornalismo local com fundo público e editais abertos",
        "proteção de dados pessoais com autoridade independente e multas publicadas",
    ],
}
_TOPIC_INSTRUMENTS_EN: dict[str, list[str]] = {
    "economia": [
        "public infrastructure investment screened by audited returns and regulated concessions",
        "spending control with a fiscal cap and annual subsidy review",
        "small-business credit with public guarantees tied to job creation",
        "consumption-tax simplification with unification and rebates for low earners",
    ],
    "seguranca": [
        "community policing with body cameras and public lethality targets",
        "sentence progression tied to work and study with electronic monitoring",
        "anti-gang intelligence with integrated databases and joint operations",
        "violence prevention with full-day schools and lighting in critical areas",
    ],
    "saude": [
        "public health funding with a binding floor and published waiting lists",
        "primary care with expanded family-health teams and home visits",
        "centralized drug procurement with national bidding and monitored stock",
        "public telemedicine with unified records and app-based scheduling",
    ],
    "educacao": [
        "federal university budgets tied to performance reviews and expanded seats",
        "vocational training linked to local industry with paid internships",
        "on-time literacy with national materials and individual tutoring",
        "full-day schools with meals, transport and cultural activities",
    ],
    "meio_ambiente": [
        "deforestation enforcement with annual operations, public fines and swift embargoes",
        "environmental licensing with maximum deadlines and published decisions",
        "degraded-land recovery with an audited fund and per-biome targets",
        "low-carbon credit conditioned on verifiable commitments",
    ],
    "corrupcao": [
        "spending transparency with a real-time portal and annual external audit",
        "technical civil-service careers with exams and whistleblower protection",
        "electronic procurement with public minutes and open price competition",
        "independent internal affairs with maximum inquiry deadlines and published sanctions",
    ],
    "armas": [
        "a national firearms registry with ballistic tracing and periodic renewal",
        "shooting-club oversight with annual inspections and ammo limits",
        "voluntary gun buybacks with compensation and public destruction",
        "carry permits restricted to duty categories with periodic psychological review",
    ],
    "previdencia": [
        "a minimum retirement age with points-based transition and proportional toll",
        "progressive contribution rates with a cap tied to the minimum wage",
        "disability-benefit review with periodic exams and rehabilitation",
        "public supplementary pensions with automatic enrollment and portability",
    ],
    "politica_externa": [
        "trade deals with farm quotas and safeguards against unfair competition",
        "environmental cooperation with an audited international fund and shared targets",
        "multilateral engagement with published votes and board candidacies",
        "protection of citizens abroad with on-call consulates and repatriation",
    ],
    "lgbtq": [
        "specialized health care with a national protocol and regional clinics",
        "anti-violence enforcement with trained precincts and public statistics",
        "job inclusion with apprenticeships and hiring targets",
        "psychosocial support with reference centers and a national helpline",
    ],
    "aborto": [
        "hospital care in cases allowed by law with a binding protocol and maximum wait",
        "maternal health with universal prenatal care and regional maternity units",
        "school sex education with scientific materials and teacher training",
        "support for pregnant people with extended leave and guaranteed daycare",
    ],
    "indigenas": [
        "land demarcation with anthropological reports and a set judicial deadline",
        "indigenous health with sanitary districts and permanent teams",
        "bilingual education with dedicated materials and native-teacher training",
        "enforcement against illegal mining with joint operations and embargoes",
    ],
    "impostos": [
        "progressivity with a salary-band exemption and higher top rates",
        "simplification with a single consumption tax and low-earner rebates",
        "sectoral-exemption review with annually published cost-benefit analysis",
        "taxation of distributed profits with an annual schedule and offsets",
    ],
    "midia": [
        "algorithmic transparency with public reports and independent audit",
        "content moderation with right of reply and appeal deadlines",
        "local-journalism funding with a public fund and open calls",
        "personal-data protection with an independent authority and published fines",
    ],
}
_GENERIC_INSTRUMENTS_PT = [
    "regras claras com fiscalização e metas públicas verificáveis",
    "investimento focalizado com auditoria e resultados publicados",
    "coordenação federativa com repasses condicionados a desempenho",
    "participação social com consultas públicas e conselhos deliberativos",
]
_GENERIC_INSTRUMENTS_EN = [
    "clear rules with enforcement and verifiable public targets",
    "targeted investment with audits and published results",
    "federal coordination with performance-conditioned transfers",
    "civic participation with public consultations and empowered councils",
]


def _sanitize_fallback_fragment(
    value: str, *, min_words: int = 4, max_words: int = 22
) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"\s+", " ", cleaned)
    if _contains_party_reference(cleaned):
        return None
    for term in BANNED_NAME_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "", cleaned, flags=re.IGNORECASE)
    for term in BANNED_EVENT_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;:-")
    word_count = _normalize_word_count(cleaned)
    if word_count < min_words or word_count > max_words:
        return None
    return cleaned


def _extract_summary_hint(summary: str) -> str | None:
    sentence = re.split(r"[.!?;:]", summary.strip(), maxsplit=1)[0]
    return _sanitize_fallback_fragment(sentence, min_words=5, max_words=20)


def _extract_action_hint(key_actions: list[object]) -> str | None:
    for action in key_actions:
        if not isinstance(action, str):
            continue
        cleaned = _sanitize_fallback_fragment(action, min_words=4, max_words=16)
        if cleaned:
            return cleaned
    return None


def _hint_fragment_ok(fragment: str, language: str) -> bool:
    """Return True when a summary/action fragment can compose grammatically
    into the first-person fallback sentence.

    Rejects fragments starting with a conjugated verb (e.g. "reativou",
    "defende"), conjunctions or pronouns, and any third-person leak such as
    "o candidato" / "the candidate" or party references.
    """
    first_word = fragment.split(None, 1)[0].lower() if fragment else ""
    if not first_word:
        return False
    if language == "pt":
        if first_word in _PT_HINT_REJECT_STARTS or _PT_VERB_START_REJECT.match(
            first_word
        ):
            return False
    else:
        if first_word in _EN_HINT_REJECT_STARTS or _EN_VERB_SUFFIX_REJECT.match(
            first_word
        ):
            return False
    normalized = fragment.lower()
    for pattern in _THIRD_PERSON_LEAK_PATTERNS:
        if re.search(pattern, normalized):
            return False
    return True


def _truncate_words(text: str, max_words: int = 80) -> str:
    chunks = [chunk for chunk in re.split(r"\s+", text.strip()) if chunk]
    if len(chunks) <= max_words:
        return text.strip()
    clipped = " ".join(chunks[:max_words]).rstrip(",;")
    if clipped and clipped[-1] not in ".!?":
        clipped += "."
    return clipped


def _fallback_option_text(
    *,
    topic_id: str,
    topic_label_pt: str,
    topic_label_en: str,
    candidate_slug: str,
    summary_pt: str,
    summary_en: str,
    key_actions: list[object],
    stance: str = "neutral",
    variant_offset: int = 0,
) -> tuple[str, str]:
    """Deterministic topic-specific fallback option.

    Substance comes from per-topic instruments (never from raw summaries, so
    third-person leaks such as names, parties or offices cannot pass through).
    Variety comes from rotating intro + instrument + closing; the stance verb
    carries the direction. Both languages are single sentences by
    construction, keeping PT/EN parity.
    """
    del summary_pt, summary_en, key_actions, topic_label_pt, topic_label_en
    stance_key = stance if stance in STANCE_TO_WEIGHT else "neutral"
    seed_raw = f"{topic_id}:{candidate_slug}:{stance_key}:{variant_offset}"
    seed = int(sha256(seed_raw.encode("utf-8")).hexdigest()[:8], 16)

    instruments_pt = _TOPIC_INSTRUMENTS_PT.get(topic_id, _GENERIC_INSTRUMENTS_PT)
    instruments_en = _TOPIC_INSTRUMENTS_EN.get(topic_id, _GENERIC_INSTRUMENTS_EN)
    instrument_count = min(len(instruments_pt), len(instruments_en))
    stance_order = list(STANCE_TO_WEIGHT)
    intro_index = (seed + variant_offset) % len(_FALLBACK_INTROS_PT)
    instrument_index = (
        stance_order.index(stance_key) + seed // len(_FALLBACK_INTROS_PT) + variant_offset
    ) % (instrument_count or 1)
    closing_index = (seed // 64 + variant_offset * 3) % len(_FALLBACK_CLOSINGS_PT)

    verb_pt = _STANCE_VERB_PT[stance_key]
    verb_en = _STANCE_VERB_EN[stance_key]
    text_pt = (
        f"{_FALLBACK_INTROS_PT[intro_index]} o governo {verb_pt} "
        f"{instruments_pt[instrument_index]}, "
        f"{_FALLBACK_CLOSINGS_PT[closing_index]}."
    )
    text_en = (
        f"{_FALLBACK_INTROS_EN[intro_index]} {verb_en} "
        f"{instruments_en[instrument_index]}, "
        f"{_FALLBACK_CLOSINGS_EN[closing_index]}."
    )
    text_pt = _truncate_words(text_pt, max_words=80)
    text_en = _truncate_words(text_en, max_words=80)
    return text_pt, text_en


def _weight_group(weight: int) -> str:
    if weight > 0:
        return "positive"
    if weight < 0:
        return "negative"
    return "zero"


def _weight_matches_mapped_stance(weight: int, mapped_stance: object) -> bool:
    """Reject AI weights whose polarity contradicts the known position stance.

    Catches polarity inversions such as a pro-LGBTQ text (weight +3) mapped
    onto an anti-LGBTQ candidate: the option would score users toward the
    wrong candidate.
    """
    expected = STANCE_TO_WEIGHT.get(str(mapped_stance))
    if expected is None:
        return True
    return _weight_group(weight) == _weight_group(expected)


def _best_source(
    position: dict[str, object],
) -> tuple[str | None, str | None, str | None, str | None]:
    sources = position.get("sources")
    if not isinstance(sources, list) or not sources:
        return None, None, None, None
    source = sources[0]
    if not isinstance(source, dict):
        return None, None, None, None
    source_pt = _normalize_text(source.get("description_pt"))
    source_en = _normalize_text(source.get("description_en"))
    source_url = _normalize_text(source.get("url"))
    source_date = _normalize_text(source.get("date"))
    return source_pt, source_en, source_url, source_date


def _clean_source_text(value: str | None) -> str | None:
    """Drop template-leakage placeholder sources such as "Dados da Wikipedia
    para flavio-bolsonaro". Attribution may legitimately mention the
    candidate, so only junk-filler patterns are rejected here."""
    text = _normalize_text(value)
    if text is None:
        return None
    for pattern in _JUNK_SOURCE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return None
    return text


def build_topic_options(
    topic_id: str,
    topic_label_pt: str,
    topic_label_en: str,
    question_pt: str,
    question_en: str,
    known_positions: list[dict[str, object]],
) -> tuple[list[dict[str, object]], str | None, str | None, bool, int]:
    """Build the options array for one topic.

    Returns (options, generator_provider, generator_model, validation_degraded,
    fallback_count) where fallback_count is how many options came from the
    deterministic `_fallback_option_text` template.
    """
    mapped_positions = {
        index + 1: position for index, position in enumerate(known_positions)
    }
    options: list[dict[str, object]] = []
    used_candidates: set[str] = set()
    used_text_pt: set[str] = set()
    used_text_en: set[str] = set()
    accepted_cores: list[tuple[str, str]] = []
    fallback_count = 0
    validation_degraded = False
    ai_validation_enabled = True
    generated_options: list[object] = []
    generator_provider: object = None
    generator_model: object = None
    try:
        generation = generate_quiz_topic_options(
            topic_id=topic_id,
            topic_label_pt=topic_label_pt,
            topic_label_en=topic_label_en,
            question_pt=question_pt,
            question_en=question_en,
            known_positions=known_positions,
        )
        maybe_generated = generation.get("options")
        if isinstance(maybe_generated, list):
            generated_options = maybe_generated
        generator_provider = generation.get("_ai_provider")
        generator_model = generation.get("_ai_model")
    except Exception as exc:
        logger.warning(
            "Quiz option generation unavailable for topic=%s; using deterministic synthesis only: %s",
            topic_id,
            exc,
        )
        validation_degraded = True

    def _run_optional_ai_validation(
        *,
        text_pt: str,
        text_en: str,
        weight: int,
    ) -> bool:
        """Run the AI validator; return True when the option may be accepted.

        An explicit validator rejection (`passes_all=False`) now rejects the
        option so a fallback is tried instead. Only transport problems
        (exceptions, parse errors) fall back to local-only validation and mark
        the run degraded.
        """
        nonlocal validation_degraded, ai_validation_enabled
        if not ai_validation_enabled:
            return True
        try:
            validation = validate_quiz_option_quality(
                topic_id=topic_id,
                text_pt=text_pt,
                text_en=text_en,
                weight=weight,
            )
        except Exception as exc:
            logger.warning(
                "Quiz validator became unavailable for topic=%s; switching to local-only validation: %s",
                topic_id,
                exc,
            )
            validation_degraded = True
            ai_validation_enabled = False
            return True
        if validation.get("_parse_error"):
            logger.info(
                "Validator parse failure for topic=%s; switching to local-only validation.",
                topic_id,
            )
            validation_degraded = True
            ai_validation_enabled = False
            return True
        if not validation.get("passes_all"):
            logger.info(
                "Validator rejected option for topic=%s: %s",
                topic_id,
                validation.get("failures"),
            )
            return False
        return True

    def _try_append_option(
        *,
        mapped_position: dict[str, object],
        text_pt: str,
        text_en: str,
        weight: int,
    ) -> bool:
        local_pass, _ = _local_quality_check(text_pt, text_en)
        if not local_pass:
            return False
        if not _weight_matches_mapped_stance(weight, mapped_position.get("stance")):
            logger.warning(
                "Rejecting option for topic=%s candidate=%s: weight %d contradicts stance %s",
                topic_id,
                mapped_position.get("candidate_slug"),
                weight,
                mapped_position.get("stance"),
            )
            return False

        fingerprint_pt = _normalize_option_fingerprint(text_pt)
        fingerprint_en = _normalize_option_fingerprint(text_en)
        if fingerprint_pt in used_text_pt or fingerprint_en in used_text_en:
            return False

        core_pt = _content_core(text_pt)
        core_en = _content_core(text_en)
        for existing_pt, existing_en in accepted_cores:
            if _core_similarity(core_pt, existing_pt) >= CORE_SIMILARITY_THRESHOLD:
                return False
            if _core_similarity(core_en, existing_en) >= CORE_SIMILARITY_THRESHOLD:
                return False

        if not _run_optional_ai_validation(
            text_pt=text_pt, text_en=text_en, weight=weight
        ):
            return False

        source_pt, source_en, source_url, source_date = _best_source(mapped_position)
        source_pt = _clean_source_text(source_pt)
        source_en = _clean_source_text(source_en)
        position_type = str(mapped_position["position_type"])
        confidence = "high" if position_type == "confirmed" else "medium"
        options.append(
            {
                "id": "",
                "text_pt": text_pt,
                "text_en": text_en,
                "weight": weight,
                "candidate_slug": str(mapped_position["candidate_slug"]),
                "position_type": position_type,
                "confidence": confidence,
                "source_pt": source_pt or "",
                "source_en": source_en or "",
                "source_url": source_url,
                "source_date": source_date,
            }
        )
        used_candidates.add(str(mapped_position["candidate_slug"]))
        used_text_pt.add(fingerprint_pt)
        used_text_en.add(fingerprint_en)
        accepted_cores.append((core_pt, core_en))
        return True

    for generated in generated_options:
        if not isinstance(generated, dict):
            continue
        mapped_position_raw = generated.get("mapped_position")
        if (
            isinstance(mapped_position_raw, int)
            and mapped_position_raw in mapped_positions
        ):
            mapped_position = mapped_positions[mapped_position_raw]
        else:
            mapped_position = None
            for candidate_position in known_positions:
                candidate_slug = str(candidate_position["candidate_slug"])
                if candidate_slug not in used_candidates:
                    mapped_position = candidate_position
                    break

        if mapped_position is None:
            continue
        candidate_slug = str(mapped_position["candidate_slug"])
        if candidate_slug in used_candidates:
            continue

        text_pt = _normalize_text(generated.get("text_pt"))
        text_en = _normalize_text(generated.get("text_en"))
        stance = generated.get("stance")
        if not text_pt or not text_en:
            continue
        if stance not in STANCE_TO_WEIGHT:
            stance = mapped_position["stance"]
        weight = generated.get("weight")
        if not isinstance(weight, int) or weight not in {-3, -2, 0, 2, 3}:
            weight = STANCE_TO_WEIGHT[str(stance)]

        if _try_append_option(
            mapped_position=mapped_position,
            text_pt=text_pt,
            text_en=text_en,
            weight=weight,
        ):
            if len(options) == len(OPTION_IDS):
                break
            continue

        # Fallback uses the mapped known-position stance (never the AI-claimed
        # one) so weight and direction always agree with the knowledge base.
        mapped_stance = str(mapped_position.get("stance", "neutral"))
        if mapped_stance not in STANCE_TO_WEIGHT:
            mapped_stance = "neutral"
        fallback_weight = STANCE_TO_WEIGHT[mapped_stance]
        summary_pt = _normalize_text(mapped_position.get("summary_pt")) or ""
        summary_en = _normalize_text(mapped_position.get("summary_en")) or ""
        key_actions = mapped_position.get("key_actions")
        if not isinstance(key_actions, list):
            key_actions = []
        fallback_selected = False
        for variant_offset in range(16):
            fallback_pt, fallback_en = _fallback_option_text(
                topic_id=topic_id,
                topic_label_pt=topic_label_pt,
                topic_label_en=topic_label_en,
                candidate_slug=candidate_slug,
                summary_pt=summary_pt,
                summary_en=summary_en,
                key_actions=key_actions,
                stance=mapped_stance,
                variant_offset=variant_offset,
            )
            if _try_append_option(
                mapped_position=mapped_position,
                text_pt=fallback_pt,
                text_en=fallback_en,
                weight=fallback_weight,
            ):
                fallback_selected = True
                fallback_count += 1
                break
        if not fallback_selected:
            logger.warning(
                "Fallback option failed quality or uniqueness checks for topic=%s candidate=%s",
                topic_id,
                candidate_slug,
            )
        if len(options) == len(OPTION_IDS):
            break

    # Deterministic fill preserves coverage when AI generation is sparse or malformed.
    for candidate_position in known_positions:
        if len(options) == len(OPTION_IDS):
            break
        candidate_slug = str(candidate_position["candidate_slug"])
        if candidate_slug in used_candidates:
            continue
        stance = str(candidate_position.get("stance", "neutral"))
        if stance not in STANCE_TO_WEIGHT:
            stance = "neutral"
        weight = STANCE_TO_WEIGHT[stance]
        summary_pt = _normalize_text(candidate_position.get("summary_pt")) or ""
        summary_en = _normalize_text(candidate_position.get("summary_en")) or ""
        key_actions = candidate_position.get("key_actions")
        if not isinstance(key_actions, list):
            key_actions = []
        appended = False
        for variant_offset in range(16, 40):
            fallback_pt, fallback_en = _fallback_option_text(
                topic_id=topic_id,
                topic_label_pt=topic_label_pt,
                topic_label_en=topic_label_en,
                candidate_slug=candidate_slug,
                summary_pt=summary_pt,
                summary_en=summary_en,
                key_actions=key_actions,
                stance=stance,
                variant_offset=variant_offset,
            )
            if _try_append_option(
                mapped_position=candidate_position,
                text_pt=fallback_pt,
                text_en=fallback_en,
                weight=weight,
            ):
                appended = True
                fallback_count += 1
                break
        if not appended:
            logger.warning(
                "Deterministic synthesis could not build a valid option for topic=%s candidate=%s",
                topic_id,
                candidate_slug,
            )

    for index, option in enumerate(options):
        option["id"] = OPTION_IDS[index]

    return (
        options,
        _normalize_text(generator_provider),
        _normalize_text(generator_model),
        validation_degraded,
        fallback_count,
    )


def _should_drop_topic(
    validation_degraded: bool, fallback_count: int, option_count: int
) -> bool:
    if option_count <= 0:
        return True
    return validation_degraded and fallback_count / option_count > MAX_FALLBACK_SHARE


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ai_client.preflight_for_run(("quiz_generate", "quiz_validate"))
    positions_payload = _load_positions_payload()
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    topics_payload = positions_payload.get("topics")
    if not isinstance(topics_payload, dict):
        raise SystemExit("Invalid candidates_positions.json: topics must be an object.")

    selected_topics = select_topics(positions_payload)
    quiz_topics: dict[str, dict[str, object]] = {}
    generator_model_used: str | None = None

    for topic_id in selected_topics:
        topic_payload = topics_payload.get(topic_id)
        if not isinstance(topic_payload, dict):
            continue
        topic_label_pt = (
            _normalize_text(topic_payload.get("topic_label_pt")) or topic_id
        )
        topic_label_en = (
            _normalize_text(topic_payload.get("topic_label_en")) or topic_id
        )
        known_positions = _topic_positions(topic_payload)
        if len(known_positions) < 2:
            continue

        question_pt, question_en = build_question_text(topic_id)
        (
            options,
            generator_provider,
            generator_model,
            validation_degraded,
            fallback_count,
        ) = build_topic_options(
            topic_id=topic_id,
            topic_label_pt=topic_label_pt,
            topic_label_en=topic_label_en,
            question_pt=question_pt,
            question_en=question_en,
            known_positions=known_positions,
        )
        if len(options) < MIN_OPTIONS_PER_TOPIC:
            continue
        if _should_drop_topic(validation_degraded, fallback_count, len(options)):
            logger.warning(
                "Dropping topic=%s: degraded run with %d/%d fallback options.",
                topic_id,
                fallback_count,
                len(options),
            )
            continue

        if generator_model and not generator_model_used:
            if generator_provider:
                generator_model_used = f"{generator_provider}:{generator_model}"
            else:
                generator_model_used = generator_model

        quiz_topics[topic_id] = {
            "topic_label_pt": topic_label_pt,
            "topic_label_en": topic_label_en,
            "divergence_score": divergence_score(known_positions),
            "question_pt": question_pt,
            "question_en": question_en,
            "generation_quality": {
                "validated": not validation_degraded,
                "validator_model": (
                    "local:heuristic-fallback"
                    if validation_degraded
                    else "nvidia:z-ai/glm-5.2"
                ),
                "validation_date": datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            "options": options,
        }

    ordered_topics = [
        topic_id for topic_id in selected_topics if topic_id in quiz_topics
    ]
    if not ordered_topics:
        existing = _load_existing_quiz_if_valid(schema)
        if existing is not None:
            print(
                "No eligible topics found. Keeping existing data/quiz.json unchanged."
            )
            return
        raise SystemExit(
            "No eligible topics with known positions. Curate candidates_positions.json first."
        )

    generated_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    quiz_payload: dict[str, object] = {
        "schema_version": "2.0.0",
        "generated_at": generated_at,
        "knowledge_base_version": _normalize_text(positions_payload.get("updated_at"))
        or generated_at,
        "generator_model": generator_model_used or "fallback-local",
        "ordered_topics": ordered_topics,
        "topics": quiz_topics,
    }

    jsonschema.validate(quiz_payload, schema)
    _write_atomic(QUIZ_FILE, quiz_payload)
    total_options = sum(
        len(options)
        for options in (topic.get("options") for topic in quiz_topics.values())
        if isinstance(options, list)
    )
    print(f"Quiz generated: {len(ordered_topics)} topics, {total_options} options.")


if __name__ == "__main__":
    main()
