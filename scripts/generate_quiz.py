"""Generate quiz.json from candidates_positions.json knowledge base."""

from __future__ import annotations

import json
import logging
import re
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from .ai_client import generate_quiz_topic_options, validate_quiz_option_quality

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
POSITIONS_FILE = ROOT_DIR / "site" / "public" / "data" / "candidates_positions.json"
QUIZ_FILE = ROOT_DIR / "site" / "public" / "data" / "quiz.json"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "quiz.schema.json"

OPTION_IDS = ["opt_a", "opt_b", "opt_c", "opt_d", "opt_e", "opt_f"]
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
    "bolsonaro",
    "tarcísio",
    "tarcisio",
    "caiado",
    "zema",
    "ratinho",
    "eduardo leite",
    "aldo rebelo",
    "renan santos",
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
        "não apoio que",
        "na pauta de",
    )
    normalized = re.sub(r"\s+", " ", text_pt.strip().lower())
    return any(normalized.startswith(prefix) for prefix in starters)


def _contains_banned_terms(text: str, banned_terms: tuple[str, ...]) -> bool:
    normalized = text.lower()
    for term in banned_terms:
        if len(term) <= 3 and term.isalpha():
            if re.search(rf"\b{re.escape(term)}\b", normalized):
                return True
            continue
        if term in normalized:
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
    if _contains_party_reference(text_pt) or _contains_party_reference(text_en):
        failures.append("party_reference")
    if _contains_banned_terms(text_pt, BANNED_EVENT_TERMS):
        failures.append("news_event")
    if any(normalized_pt.startswith(prefix) for prefix in BANNED_OPTION_OPENINGS_PT):
        failures.append("boilerplate")
    if any(normalized_en.startswith(prefix) for prefix in BANNED_OPTION_OPENINGS_EN):
        failures.append("boilerplate")
    broken_continuation_patterns = (
        r"\b(isso\s+inclui\s+[a-zéêãõ]{1,4}\s)",  # "Isso inclui é", "Isso inclui o"
        r"\b(tamb[eé]m\s+[eé]\s+essencial\s+[a-zéêãõ]{1,4}\s)",  # "Também é essencial apoiou"
        r"\b(\b[a-zéêãõ]{1,3}\b\s){3,}",  # 3+ single-char words in a row (glue fragments)
        r",\s*,",  # double comma
        r"apoiou\s+a\s+reforma|defendeu\s+a\s+reforma|apoia\s+a\s+reforma|votou\s+a\s+favor\s+do\s+processo",
        r"dados\s+da\s+wikipedia",
    )
    for pat in broken_continuation_patterns:
        if re.search(pat, normalized_pt) or re.search(pat, normalized_en):
            failures.append("broken_continuation")
            break
    return (len(failures) == 0, failures)


_STANCE_FALLBACK_PT = {
    "strongly_favor": "defende uma mudança progressista e ampla, priorizando direitos e expansão de políticas públicas",
    "favor": "apoia reformas moderadas com foco em modernização e melhoria gradual do cenário atual",
    "neutral": "busca um equilíbrio pragmático, avaliando prós e contras antes de avançar com reformas",
    "against": "prefere manter a estabilidade institucional, evitando mudanças radicais no cenário atual",
    "strongly_against": "defende firmemente a preservação do status quo, resistindo a propostas de liberalização",
}
_STANCE_FALLBACK_EN = {
    "strongly_favor": "advocates for broad progressive change, prioritizing rights and expansion of public policies",
    "favor": "supports moderate reforms focused on modernization and gradual improvement of the current landscape",
    "neutral": "seeks a pragmatic balance, weighing pros and cons before advancing reforms",
    "against": "prefers to maintain institutional stability, avoiding radical changes to the current landscape",
    "strongly_against": "firmly defends preserving the status quo, resisting liberalization proposals",
}


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
    pt_intros = {
        "strongly_favor": [
            "Defendo firmemente que",
            "Acredito que é prioridade que",
            "Quero que",
            "Sou favorável a que",
        ],
        "favor": [
            "Defendo que",
            "Acredito que",
            "Considero melhor que",
            "Sou favorável a que",
        ],
        "neutral": [
            "Entendo que",
            "Considero adequado que",
            "Acredito que",
            "Na minha visão, é melhor que",
        ],
        "against": [
            "Defendo que o governo mantenha cautela e avalie com rigor antes de mudar regras existentes.",
            "Sou a favor de preservar o que funciona e avançar apenas quando houver consenso amplo.",
            "Prefiro que o governo priorize estabilidade e segurança jurídica antes de promover alterações.",
            "Acredito que mudanças significativas exigem evidência sólida e debate aprofundado.",
        ],
        "strongly_against": [
            "Sou absolutamente a favor de que o governo mantenha o rumo atual e rejeite pressões por mudanças.",
            "Defendo com firmeza que o governo não modifique políticas estabelecidas sem necessidade absoluta.",
            "Acredito que qualquer alteração deve ser rejeitada se representar ruptura sem justificativa clara.",
            "Sou favorável a que o governo resista a reformas que possam desestabilizar o que já está consolidado.",
        ],
    }
    en_intros = {
        "strongly_favor": [
            "I strongly believe that",
            "I see it as a priority that",
            "I want the government to",
            "I clearly support the idea that",
        ],
        "favor": [
            "I believe that",
            "I support the idea that",
            "I consider it better that",
            "I am in favor of the government",
        ],
        "neutral": [
            "I see it as better that",
            "I believe that",
            "I consider it appropriate that",
            "In my view, it is better that",
        ],
        "against": [
            "I believe the government should proceed with caution and evaluate carefully before changing existing rules.",
            "I am in favor of preserving what works and only advancing when there is broad consensus.",
            "I prefer that the government prioritize stability and legal certainty before promoting changes.",
            "I believe significant changes require solid evidence and thorough debate.",
        ],
        "strongly_against": [
            "I am absolutely in favor of the government maintaining its current course and rejecting pressures for change.",
            "I firmly believe the government should not modify established policies without absolute necessity.",
            "I believe any alteration should be rejected if it represents a rupture without clear justification.",
            "I am in favor of the government resisting reforms that could destabilize what is already consolidated.",
        ],
    }
    stance_key = stance if stance in STANCE_TO_WEIGHT else "neutral"
    seed_raw = f"{topic_id}:{candidate_slug}:{stance_key}:{variant_offset}"
    seed = int(sha256(seed_raw.encode("utf-8")).hexdigest()[:8], 16)
    intro_index = seed % len(pt_intros[stance_key])

    topic_pt = topic_label_pt.strip().lower() or topic_id.replace("_", " ")
    topic_en = topic_label_en.strip().lower() or topic_id.replace("_", " ")
    summary_hint_pt = _extract_summary_hint(summary_pt) if summary_pt else None
    summary_hint_en = _extract_summary_hint(summary_en) if summary_en else None
    action_hint_pt = _extract_action_hint(key_actions)

    def _build_pt(intro: str, topic: str) -> str:
        sentence = f"{intro} na pauta de {topic}."
        if summary_hint_pt:
            sentence = (
                f"{intro} {topic}. {summary_hint_pt[0].upper()}{summary_hint_pt[1:]}"
            )
        if action_hint_pt and summary_hint_pt != action_hint_pt:
            sentence += f" {action_hint_pt[0].upper()}{action_hint_pt[1:]}"
        return _truncate_words(sentence, max_words=80)

    def _build_en(intro: str, topic: str) -> str:
        sentence = f"{intro} {topic}."
        if summary_hint_en:
            sentence = (
                f"{intro} {topic}. {summary_hint_en[0].upper()}{summary_hint_en[1:]}"
            )
        return _truncate_words(sentence, max_words=80)

    text_pt = _build_pt(pt_intros[stance_key][intro_index], topic_pt)
    text_en = _build_en(en_intros[stance_key][intro_index], topic_en)

    pt_desc = _STANCE_FALLBACK_PT.get(stance, _STANCE_FALLBACK_PT["neutral"])
    en_desc = _STANCE_FALLBACK_EN.get(stance, _STANCE_FALLBACK_EN["neutral"])
    if _normalize_word_count(text_pt) < 15:
        text_pt = f"Acredito que {pt_desc} na pauta de {topic_pt}, com metas transparentes e revisão periódica."
    if _normalize_word_count(text_en) < 15:
        text_en = f"I believe the policy for {topic_en} should {en_desc}, with transparent goals and periodic review."
    return text_pt, text_en


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


def build_topic_options(
    topic_id: str,
    topic_label_pt: str,
    topic_label_en: str,
    question_pt: str,
    question_en: str,
    known_positions: list[dict[str, object]],
) -> tuple[list[dict[str, object]], str | None, str | None, bool]:
    generation = generate_quiz_topic_options(
        topic_id=topic_id,
        topic_label_pt=topic_label_pt,
        topic_label_en=topic_label_en,
        question_pt=question_pt,
        question_en=question_en,
        known_positions=known_positions,
    )
    generated_options = generation.get("options")
    generator_provider = generation.get("_ai_provider")
    generator_model = generation.get("_ai_model")
    if not isinstance(generated_options, list):
        generated_options = []

    mapped_positions = {
        index + 1: position for index, position in enumerate(known_positions)
    }
    options: list[dict[str, object]] = []
    used_candidates: set[str] = set()
    used_text_pt: set[str] = set()
    used_text_en: set[str] = set()
    validation_degraded = False

    def _validate_option_with_retry(
        *,
        text_pt: str,
        text_en: str,
        weight: int,
    ) -> bool:
        nonlocal validation_degraded
        if validation_degraded:
            return True
        for attempt in range(2):
            try:
                validation = validate_quiz_option_quality(
                    topic_id=topic_id,
                    text_pt=text_pt,
                    text_en=text_en,
                    weight=weight,
                )
            except Exception as exc:
                logger.warning(
                    "Quiz validator unavailable for topic=%s; using local fallback: %s",
                    topic_id,
                    exc,
                )
                validation_degraded = True
                return True
            if validation.get("passes_all"):
                return True
            if validation.get("_parse_error"):
                if attempt == 0:
                    logger.info(
                        "Validator parse failure for topic=%s. Retrying once.",
                        topic_id,
                    )
                    continue
                logger.warning(
                    "Validator parse failures persisted for topic=%s; using local fallback.",
                    topic_id,
                )
                validation_degraded = True
                return True
            return False
        return False

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
        summary_pt = _normalize_text(mapped_position.get("summary_pt"))
        summary_en = _normalize_text(mapped_position.get("summary_en"))
        key_actions = mapped_position.get("key_actions")
        if not isinstance(key_actions, list):
            key_actions = []

        local_pass, local_failures = _local_quality_check(text_pt, text_en)
        ai_pass = False
        if local_pass:
            ai_pass = _validate_option_with_retry(
                text_pt=text_pt,
                text_en=text_en,
                weight=weight,
            )
        if not local_pass or not ai_pass:
            fallback_selected = False
            for variant_offset in range(8):
                fallback_pt, fallback_en = _fallback_option_text(
                    topic_id=topic_id,
                    topic_label_pt=topic_label_pt,
                    topic_label_en=topic_label_en,
                    candidate_slug=candidate_slug,
                    summary_pt=summary_pt,
                    summary_en=summary_en,
                    key_actions=key_actions,
                    stance=str(stance),
                    variant_offset=variant_offset,
                )
                local_pass, local_failures = _local_quality_check(
                    fallback_pt, fallback_en
                )
                if not local_pass:
                    continue
                fp_pt = _normalize_option_fingerprint(fallback_pt)
                fp_en = _normalize_option_fingerprint(fallback_en)
                if fp_pt in used_text_pt or fp_en in used_text_en:
                    continue
                if not _validate_option_with_retry(
                    text_pt=fallback_pt,
                    text_en=fallback_en,
                    weight=weight,
                ):
                    continue
                text_pt, text_en = fallback_pt, fallback_en
                fallback_selected = True
                break
            if not fallback_selected:
                logger.warning(
                    "Fallback option failed quality or uniqueness checks for topic=%s candidate=%s failures=%s",
                    topic_id,
                    candidate_slug,
                    ",".join(local_failures),
                )
                continue

        fingerprint_pt = _normalize_option_fingerprint(text_pt)
        fingerprint_en = _normalize_option_fingerprint(text_en)
        if fingerprint_pt in used_text_pt or fingerprint_en in used_text_en:
            diversified = False
            for variant_offset in range(8, 16):
                diversified_pt, diversified_en = _fallback_option_text(
                    topic_id=topic_id,
                    topic_label_pt=topic_label_pt,
                    topic_label_en=topic_label_en,
                    candidate_slug=candidate_slug,
                    summary_pt=summary_pt,
                    summary_en=summary_en,
                    key_actions=key_actions,
                    stance=str(stance),
                    variant_offset=variant_offset,
                )
                diversified_local_pass, _ = _local_quality_check(
                    diversified_pt, diversified_en
                )
                diversified_fp_pt = _normalize_option_fingerprint(diversified_pt)
                diversified_fp_en = _normalize_option_fingerprint(diversified_en)
                if (
                    diversified_local_pass
                    and diversified_fp_pt not in used_text_pt
                    and diversified_fp_en not in used_text_en
                ):
                    if not _validate_option_with_retry(
                        text_pt=diversified_pt,
                        text_en=diversified_en,
                        weight=weight,
                    ):
                        continue
                    text_pt, text_en = diversified_pt, diversified_en
                    fingerprint_pt = diversified_fp_pt
                    fingerprint_en = diversified_fp_en
                    diversified = True
                    break
            if not diversified:
                logger.info(
                    "Skipping duplicated quiz option for topic=%s candidate=%s",
                    topic_id,
                    candidate_slug,
                )
                continue

        source_pt, source_en, source_url, source_date = _best_source(mapped_position)
        position_type = str(mapped_position["position_type"])
        confidence = "high" if position_type == "confirmed" else "medium"
        options.append(
            {
                "id": "",
                "text_pt": text_pt,
                "text_en": text_en,
                "weight": weight,
                "candidate_slug": candidate_slug,
                "position_type": position_type,
                "confidence": confidence,
                "source_pt": source_pt or "",
                "source_en": source_en or "",
                "source_url": source_url,
                "source_date": source_date,
            }
        )
        used_candidates.add(candidate_slug)
        used_text_pt.add(fingerprint_pt)
        used_text_en.add(fingerprint_en)
        if len(options) == len(OPTION_IDS):
            break

    for index, option in enumerate(options):
        option["id"] = OPTION_IDS[index]

    return (
        options,
        _normalize_text(generator_provider),
        _normalize_text(generator_model),
        validation_degraded,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
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
        ) = build_topic_options(
            topic_id=topic_id,
            topic_label_pt=topic_label_pt,
            topic_label_en=topic_label_en,
            question_pt=question_pt,
            question_en=question_en,
            known_positions=known_positions,
        )
        if len(options) < 2:
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
                    else "nvidia:moonshotai/kimi-k2.5"
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
    print(
        f"Quiz generated: {len(ordered_topics)} topics, {sum(len(topic['options']) for topic in quiz_topics.values())} options."
    )


if __name__ == "__main__":
    main()
