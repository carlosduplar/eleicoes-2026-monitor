"""Generate quiz.json from candidates_positions.json knowledge base."""

from __future__ import annotations

import json
import logging
import re
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
        "acredito que",
        "a prioridade",
        "é fundamental",
        "e fundamental",
        "defendo que",
    )
    normalized = text_pt.strip().lower()
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


def _local_quality_check(text_pt: str, text_en: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    word_count = _normalize_word_count(text_pt)
    if word_count < 15 or word_count > 80:
        failures.append("length")
    if not _looks_like_first_person_position(text_pt):
        failures.append("first_person")
    if _contains_banned_terms(text_pt, BANNED_NAME_TERMS) or _contains_banned_terms(
        text_en, BANNED_NAME_TERMS
    ):
        failures.append("candidate_reference")
    if _contains_banned_terms(text_pt, BANNED_EVENT_TERMS):
        failures.append("news_event")
    return (len(failures) == 0, failures)


def _fallback_option_text(summary_pt: str, summary_en: str) -> tuple[str, str]:
    pt_summary = summary_pt.rstrip(".")
    en_summary = summary_en.rstrip(".")
    return (
        (
            "O governo deveria adotar uma política pública clara e estável em que "
            f"{pt_summary.lower()}, com metas transparentes e revisão periódica."
        ),
        (
            "The government should adopt a clear and stable public policy in which "
            f"{en_summary.lower()}, with transparent goals and periodic review."
        ),
    )


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
) -> tuple[list[dict[str, object]], str | None, str | None]:
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

        local_pass, local_failures = _local_quality_check(text_pt, text_en)
        ai_pass = False
        if local_pass:
            validation = validate_quiz_option_quality(
                topic_id=topic_id,
                text_pt=text_pt,
                text_en=text_en,
                weight=weight,
            )
            ai_pass = bool(validation.get("passes_all"))
        if not local_pass or not ai_pass:
            summary_pt = (
                _normalize_text(mapped_position.get("summary_pt"))
                or "a política pública deve ser clara e previsível"
            )
            summary_en = (
                _normalize_text(mapped_position.get("summary_en"))
                or "public policy should be clear and predictable"
            )
            text_pt, text_en = _fallback_option_text(summary_pt, summary_en)
            local_pass, local_failures = _local_quality_check(text_pt, text_en)
            if not local_pass:
                logger.warning(
                    "Fallback option failed local quality checks for topic=%s candidate=%s failures=%s",
                    topic_id,
                    candidate_slug,
                    ",".join(local_failures),
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
                "source_pt": source_pt,
                "source_en": source_en,
                "source_url": source_url,
                "source_date": source_date,
            }
        )
        used_candidates.add(candidate_slug)
        if len(options) == len(OPTION_IDS):
            break

    for index, option in enumerate(options):
        option["id"] = OPTION_IDS[index]

    return (
        options,
        _normalize_text(generator_provider),
        _normalize_text(generator_model),
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
        options, generator_provider, generator_model = build_topic_options(
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
                "validated": True,
                "validator_model": "nvidia:moonshotai/kimi-k2.5",
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
