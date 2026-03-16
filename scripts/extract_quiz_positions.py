"""Daily quiz position extraction pipeline — Phase 11."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from .ai_client import extract_candidate_position

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT_DIR / "data" / "articles.json"
QUIZ_FILE = ROOT_DIR / "data" / "quiz.json"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "quiz.schema.json"

CANDIDATES = [
    "lula",
    "flavio-bolsonaro",
    "tarcisio",
    "caiado",
    "zema",
    "ratinho-jr",
    "eduardo-leite",
    "aldo-rebelo",
    "renan-santos",
]

QUIZ_TOPICS = [
    "economia",
    "seguranca",
    "saude",
    "educacao",
    "meio_ambiente",
    "corrupcao",
    "armas",
    "privatizacao",
    "previdencia",
    "politica_ext",
    "lgbtq",
    "aborto",
    "indigenas",
    "impostos",
    "midia",
    "eleicoes",
]

STANCE_MAP = {"favor": 2, "neutral": 0, "against": -2, "unclear": None}
OPTION_LETTERS = ["opt_a", "opt_b", "opt_c", "opt_d", "opt_e", "opt_f"]
WEIGHT_TO_STANCE = {2: "favor", 0: "neutral", -2: "against"}
CONFIDENCE_ALLOWED = {"high", "medium"}

# Substrings whose presence in a position text indicates AI slop (news events,
# polling data, or template placeholder leakage) rather than a policy stance.
_QUALITY_REJECTION_SUBSTRINGS = (
    "pesquisa",
    "investigação",
    "investigacao",
    "aprovação",
    "desaprovação",
    "aprovacao",
    "desaprovacao",
    "percentual",
    "sondagem",
    "denúncia",
    "denuncia",
    "inquérito",
    "inquerito",
    "posicao em portugues",
    "position in english",
    "ou null",
)
# Prefixes that indicate the model described the article rather than the stance.
_QUALITY_REJECTION_PREFIXES = (
    "o texto apresenta",
    "o texto descreve",
    "the text presents",
    "the text describes",
)

CANDIDATE_NAME_VARIANTS = {
    "lula": [
        "lula",
        "presidente lula",
        "luiz inacio lula da silva",
        "luiz inácio lula da silva",
    ],
    "flavio-bolsonaro": [
        "flavio bolsonaro",
        "flávio bolsonaro",
        "bolsonaro",
        "eduardo bolsonaro",
    ],
    "tarcisio": ["tarcisio", "tarcísio", "tarcisio de freitas", "tarcísio de freitas"],
    "caiado": ["caiado", "ronaldo caiado"],
    "zema": ["zema", "romeu zema"],
    "ratinho-jr": ["ratinho", "ratinho jr", "ratinho-jr", "ratinho junior"],
    "eduardo-leite": ["eduardo leite", "eduardo-leite", "leite"],
    "aldo-rebelo": ["aldo rebelo", "aldo-rebelo"],
    "renan-santos": ["renan santos", "renan-santos"],
}

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
    "privatizacao": (
        "Qual deve ser o papel de privatizações na economia brasileira?",
        "What role should privatization play in Brazil's economy?",
    ),
    "previdencia": (
        "Qual direção deve orientar a política de previdência social?",
        "What direction should guide social security policy?",
    ),
    "politica_ext": (
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
    "eleicoes": (
        "Qual mudança deve ser prioridade no sistema eleitoral brasileiro?",
        "Which change should be prioritized in Brazil's electoral system?",
    ),
}

_SNIPPETS_CACHE: dict[tuple[str, str], list[str]] = {}


def _parse_iso8601(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)

    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _is_valid_position(position: dict[str, object]) -> bool:
    confidence = position.get("confidence")
    stance = position.get("stance")
    weight = STANCE_MAP.get(stance) if isinstance(stance, str) else None
    return confidence in CONFIDENCE_ALLOWED and weight is not None


def _fallback_position(
    candidate: str, topic_id: str, snippets: list[str]
) -> dict[str, object] | None:
    # Do not fabricate positions: a made-up generic stance is worse than no data.
    # Callers should skip the candidate/topic pair when this returns None.
    del candidate, topic_id, snippets
    return None


def _local_quality_check(text_pt: str, text_en: str) -> bool:
    """Return True if the position text looks like a genuine policy stance.

    Rejects: empty/null strings, template placeholders, polling/investigation
    data, meta-commentary about the source article, and texts too short or
    too long to be a policy position.
    """
    normalized_pt = text_pt.strip().lower()
    normalized_en = text_en.strip().lower()

    if not normalized_pt or normalized_pt in ("null", "none"):
        return False

    for exact in ("null", "none"):
        if normalized_pt == exact or normalized_en == exact:
            return False

    words = [w for w in re.split(r"\s+", normalized_pt) if w]
    if len(words) < 8 or len(words) > 80:
        return False

    for substring in _QUALITY_REJECTION_SUBSTRINGS:
        if substring in normalized_pt or substring in normalized_en:
            return False

    for prefix in _QUALITY_REJECTION_PREFIXES:
        if normalized_pt.startswith(prefix) or normalized_en.startswith(prefix):
            return False

    return True


def _sanitize_option_text(text: str, language: str) -> str:
    replacement = "o candidato" if language == "pt" else "the candidate"
    cleaned = text

    for slug in CANDIDATES:
        slug_with_space = slug.replace("-", " ")
        cleaned = re.sub(re.escape(slug), replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            re.escape(slug_with_space), replacement, cleaned, flags=re.IGNORECASE
        )
        for variant in CANDIDATE_NAME_VARIANTS.get(slug, []):
            cleaned = re.sub(
                rf"\b{re.escape(variant)}\b", replacement, cleaned, flags=re.IGNORECASE
            )

    cleaned = re.sub(
        rf"({re.escape(replacement)})(\s+{re.escape(replacement)})+",
        replacement,
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _load_existing_positions() -> dict[str, dict[str, dict[str, object]]]:
    if not QUIZ_FILE.exists():
        return {}

    try:
        payload = json.loads(QUIZ_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    topics = payload.get("topics")
    if not isinstance(topics, dict):
        return {}

    existing: dict[str, dict[str, dict[str, object]]] = {}
    for topic_id, topic_payload in topics.items():
        if not isinstance(topic_payload, dict):
            continue
        options = topic_payload.get("options")
        if not isinstance(options, list):
            continue

        topic_map: dict[str, dict[str, object]] = {}
        for option in options:
            if not isinstance(option, dict):
                continue
            candidate = option.get("candidate_slug")
            weight = option.get("weight")
            if not isinstance(candidate, str):
                continue
            stance = (
                WEIGHT_TO_STANCE.get(weight) if isinstance(weight, int) else "unclear"
            )
            topic_map[candidate] = {
                "position_pt": _normalize_text(option.get("text_pt")),
                "position_en": _normalize_text(option.get("text_en")),
                "stance": stance,
                "confidence": option.get("confidence")
                if option.get("confidence") in CONFIDENCE_ALLOWED
                else "medium",
                "best_source_snippet_index": None,
                "source_pt": _normalize_text(option.get("source_pt")),
                "source_en": _normalize_text(option.get("source_en")),
            }
        if topic_map:
            existing[topic_id] = topic_map
    return existing


def load_articles() -> list[dict]:
    """Load data/articles.json. Return [] on file-not-found or parse error."""
    if not ARTICLES_FILE.exists():
        return []

    try:
        payload = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not parse %s: %s", ARTICLES_FILE, exc)
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)]

    return []


def filter_snippets(articles: list[dict], candidate: str, topic: str) -> list[str]:
    """Return up to 12 most recent article snippets (title + summary pt-BR)
    where candidate is in candidates_mentioned AND topic is in topics.
    Sort by published_at descending. Each snippet: '{title}. {summaries.pt-BR}'."""
    snippets_with_date: list[tuple[datetime, str]] = []
    for article in articles:
        candidates = article.get("candidates_mentioned")
        topics = article.get("topics")
        if not isinstance(candidates, list) or not isinstance(topics, list):
            continue
        if candidate not in candidates or topic not in topics:
            continue

        title = _normalize_text(article.get("title"))
        summaries = article.get("summaries")
        summary_pt = None
        if isinstance(summaries, dict):
            summary_pt = _normalize_text(summaries.get("pt-BR"))

        if title and summary_pt:
            snippet = f"{title}. {summary_pt}"
        elif title:
            snippet = title
        elif summary_pt:
            snippet = summary_pt
        else:
            continue

        snippets_with_date.append(
            (_parse_iso8601(article.get("published_at")), snippet)
        )

    snippets_with_date.sort(key=lambda item: item[0], reverse=True)
    return [snippet for _, snippet in snippets_with_date[:12]]


def divergence_score(positions: list[dict]) -> float:
    """Compute (max_weight - min_weight) / 4.0 for positions with
    confidence in ('high','medium') and stance != 'unclear'.
    Return 0.0 if fewer than 2 valid stances."""
    valid_weights: list[int] = []
    for position in positions:
        confidence = position.get("confidence")
        stance = position.get("stance")
        weight = STANCE_MAP.get(stance) if isinstance(stance, str) else None
        if confidence in CONFIDENCE_ALLOWED and weight is not None:
            valid_weights.append(weight)

    if len(valid_weights) < 2:
        return 0.0
    return (max(valid_weights) - min(valid_weights)) / 4.0


def select_quiz_topics(
    all_positions: dict[str, dict[str, dict]],
    # outer key: topic_id, inner key: candidate_slug -> position dict
) -> list[str]:
    """Select 10-15 topics with highest divergence_score.
    Must have >= 2 options with high/medium confidence.
    Return list of topic_ids sorted by divergence descending."""
    scored_topics: list[tuple[str, float]] = []

    for topic_id in QUIZ_TOPICS:
        topic_positions = all_positions.get(topic_id, {})
        valid_positions = [
            position
            for position in topic_positions.values()
            if isinstance(position, dict) and _is_valid_position(position)
        ]
        if len(valid_positions) < 2:
            continue

        score = divergence_score(
            [
                position
                for position in topic_positions.values()
                if isinstance(position, dict)
            ]
        )
        scored_topics.append((topic_id, score))

    scored_topics.sort(key=lambda item: (-item[1], item[0]))
    selected = [topic_id for topic_id, _ in scored_topics[:15]]
    return selected


def build_question_text(topic_id: str) -> tuple[str, str]:
    """Return (question_pt, question_en) for a topic.
    Use a static template dict mapping topic_id -> bilingual question text.
    Fallback: generic 'Qual sua posicao sobre {topic}?'."""
    if topic_id in QUESTION_TEMPLATES:
        return QUESTION_TEMPLATES[topic_id]

    topic_label = topic_id.replace("_", " ")
    return (
        f"Qual sua posição sobre {topic_label}?",
        f"What is your position on {topic_label}?",
    )


def _build_source_text(
    topic_id: str, candidate: str, position: dict[str, object]
) -> tuple[str | None, str | None]:
    source_pt = _normalize_text(position.get("source_pt"))
    source_en = _normalize_text(position.get("source_en"))

    snippets = _SNIPPETS_CACHE.get((candidate, topic_id), [])
    best_index_raw = position.get("best_source_snippet_index")
    best_index = best_index_raw if isinstance(best_index_raw, int) else None
    snippet = None
    if snippets:
        if best_index is not None and 1 <= best_index <= len(snippets):
            snippet = snippets[best_index - 1]
        else:
            snippet = snippets[0]
            best_index = 1

    if snippet:
        clipped = snippet[:220]
        return (
            f"Trecho {best_index}: {clipped}",
            f"Snippet {best_index}: {clipped}",
        )

    return source_pt, source_en


def build_options(
    topic_id: str,
    positions: dict[str, dict],  # candidate_slug -> position dict
) -> list[dict]:
    """Build options array for quiz.json.
    Only include candidates with confidence in ('high','medium') and stance != 'unclear'.
    Assign id from OPTION_LETTERS sequentially.
    Each option: {id, text_pt, text_en, weight, candidate_slug, source_pt, source_en, confidence}.
    weight = STANCE_MAP[stance]. text_pt = position_pt. text_en = position_en.
    source_pt/source_en: brief attribution string from best_source_snippet_index."""
    options: list[dict] = []

    for candidate in CANDIDATES:
        position = positions.get(candidate)
        if not isinstance(position, dict):
            continue
        if not _is_valid_position(position):
            continue

        stance = position.get("stance")
        weight = STANCE_MAP.get(stance) if isinstance(stance, str) else None
        if weight is None:
            continue

        text_pt = _normalize_text(position.get("position_pt"))
        text_en = _normalize_text(position.get("position_en"))
        if not text_pt or not text_en:
            continue
        text_pt = _sanitize_option_text(text_pt, "pt")
        text_en = _sanitize_option_text(text_en, "en")

        source_pt, source_en = _build_source_text(topic_id, candidate, position)
        confidence = position.get("confidence")
        if confidence not in CONFIDENCE_ALLOWED:
            continue

        option = {
            "id": "",
            "text_pt": text_pt,
            "text_en": text_en,
            "weight": weight,
            "candidate_slug": candidate,
            "confidence": confidence,
        }
        if source_pt:
            option["source_pt"] = source_pt
        if source_en:
            option["source_en"] = source_en
        options.append(option)

    for index, option in enumerate(options[: len(OPTION_LETTERS)]):
        option["id"] = OPTION_LETTERS[index]

    return options[: len(OPTION_LETTERS)]


def _deterministic_generated_at(articles: list[dict]) -> str:
    timestamps = [_parse_iso8601(article.get("published_at")) for article in articles]
    max_timestamp = max(timestamps, default=datetime(1970, 1, 1, tzinfo=timezone.utc))
    return max_timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".json.tmp")
    temp_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_file.replace(path)


def main() -> None:
    """Orchestrator:
    1. load_articles()
    2. For each topic in QUIZ_TOPICS, for each candidate in CANDIDATES:
       - snippets = filter_snippets(articles, candidate, topic)
       - position = ai_client.extract_candidate_position(candidate, topic, snippets)
       - Store in all_positions[topic][candidate] = position
       - On AI error: log warning, continue (keep existing data if any)
    3. selected = select_quiz_topics(all_positions)
    4. Build quiz dict conforming to quiz.schema.json
    5. Validate against schema with jsonschema
    6. Write data/quiz.json (atomic write via temp file + rename)
    7. Print summary line
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    articles = load_articles()
    existing_positions = _load_existing_positions()
    all_positions: dict[str, dict[str, dict[str, object]]] = {
        topic_id: {} for topic_id in QUIZ_TOPICS
    }
    ai_errors = 0

    for topic_id in QUIZ_TOPICS:
        for candidate in CANDIDATES:
            snippets = filter_snippets(articles, candidate, topic_id)
            _SNIPPETS_CACHE[(candidate, topic_id)] = snippets

            fallback_position = existing_positions.get(topic_id, {}).get(candidate)
            try:
                position = extract_candidate_position(candidate, topic_id, snippets)
            except Exception as exc:  # noqa: BLE001 - explicitly required by spec
                ai_errors += 1
                logger.warning(
                    "AI extraction failed for topic=%s candidate=%s: %s",
                    topic_id,
                    candidate,
                    exc,
                )
                if isinstance(fallback_position, dict):
                    all_positions[topic_id][candidate] = fallback_position
                continue

            if isinstance(position, dict):
                parse_error = bool(position.get("_parse_error"))
                if parse_error and isinstance(fallback_position, dict):
                    all_positions[topic_id][candidate] = fallback_position
                elif parse_error:
                    # _fallback_position now returns None; skip the pair.
                    pass
                elif not _is_valid_position(position):
                    if isinstance(fallback_position, dict) and _is_valid_position(
                        fallback_position
                    ):
                        all_positions[topic_id][candidate] = fallback_position
                else:
                    pos_pt = str(position.get("position_pt") or "")
                    pos_en = str(position.get("position_en") or "")
                    if _local_quality_check(pos_pt, pos_en):
                        all_positions[topic_id][candidate] = position
                    elif isinstance(fallback_position, dict) and _is_valid_position(
                        fallback_position
                    ):
                        # Prefer a previously validated position over AI slop.
                        prev_pt = str(fallback_position.get("position_pt") or "")
                        prev_en = str(fallback_position.get("position_en") or "")
                        if _local_quality_check(prev_pt, prev_en):
                            all_positions[topic_id][candidate] = fallback_position
                        else:
                            logger.warning(
                                "Quality check failed for topic=%s candidate=%s; skipping.",
                                topic_id,
                                candidate,
                            )
                    else:
                        logger.warning(
                            "Quality check failed for topic=%s candidate=%s; skipping.",
                            topic_id,
                            candidate,
                        )
                continue

            if isinstance(fallback_position, dict):
                all_positions[topic_id][candidate] = fallback_position

    selected_topics = select_quiz_topics(all_positions)
    quiz_topics: dict[str, dict[str, object]] = {}
    for topic_id in selected_topics:
        topic_positions = all_positions.get(topic_id, {})
        options = build_options(topic_id, topic_positions)
        if len(options) < 2:
            continue
        question_pt, question_en = build_question_text(topic_id)
        score = divergence_score(
            [
                position
                for position in topic_positions.values()
                if isinstance(position, dict)
            ]
        )
        quiz_topics[topic_id] = {
            "divergence_score": score,
            "question_pt": question_pt,
            "question_en": question_en,
            "options": options,
        }

    ordered_topics = [
        topic_id for topic_id in selected_topics if topic_id in quiz_topics
    ]
    quiz_payload: dict[str, object] = {
        "generated_at": _deterministic_generated_at(articles),
        "ordered_topics": ordered_topics,
        "topics": quiz_topics,
    }

    try:
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        jsonschema.validate(quiz_payload, schema)
    except jsonschema.ValidationError as exc:
        logger.error("Quiz schema validation failed: %s", exc.message)
        raise SystemExit(1) from exc
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load quiz schema: %s", exc)
        raise SystemExit(1) from exc

    _write_atomic(QUIZ_FILE, quiz_payload)

    extracted_positions = sum(
        len(topic_payload["options"])
        for topic_payload in quiz_topics.values()
        if isinstance(topic_payload, dict)
        and isinstance(topic_payload.get("options"), list)
    )
    print(
        f"Quiz: {len(ordered_topics)} topics selected, "
        f"{extracted_positions} positions extracted ({ai_errors} errors)"
    )


if __name__ == "__main__":
    main()
