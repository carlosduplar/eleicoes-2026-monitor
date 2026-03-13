"""Editor-tier article summarization for Phase 06."""

from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

try:
    from scripts import ai_client
    from scripts.ai_client import _provider_failure_counts, _CIRCUIT_BREAKER_THRESHOLD
except ImportError:  # pragma: no cover - direct script execution path
    import ai_client  # type: ignore[no-redef]
    from ai_client import _provider_failure_counts, _CIRCUIT_BREAKER_THRESHOLD  # type: ignore[no-redef]

try:
    from scripts import editor_feedback
except ImportError:  # pragma: no cover - direct script execution path
    import editor_feedback  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

API_KEY_PATTERN = re.compile(
    r"(key|api_key|apikey|devKey)=[A-Za-z0-9_-]{20,}", re.IGNORECASE
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
EDITOR_FEEDBACK_FILE = DATA_DIR / "editor_feedback.json"

DISCLAIMER_PT = "Análise algorítmica. Não representa pesquisa de opinião."
DISCLAIMER_EN = "Algorithmic analysis. Does not represent polling data."

VALID_TOPICS = {
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
}

# High-precision election signals: if these are absent, the article is likely generic politics.
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

VALID_SENTIMENT_LABELS = {"positivo", "neutro", "negativo"}
SENTIMENT_TO_SCORE = {"positivo": 1.0, "neutro": 0.0, "negativo": -1.0}

# Phrases that indicate the scraper hit a bot-detection / error page instead of real content.
# Checked against the first 600 chars of content (case-insensitive) before any LLM call.
_BLOCKED_CONTENT_PATTERNS: frozenset[str] = frozenset(
    {
        "access denied",
        "403 forbidden",
        "404 not found",
        "please enable javascript",
        "just a moment",
        "checking your browser",
        "cloudflare",
        "ddos protection",
        "one more step",
        "verify you are human",
        "are you a robot",
        "captcha",
        "enable cookies",
        "you have been blocked",
        "security check",
        "please wait while we check",
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


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().replace("_", " ").replace("-", " ").split())


def _canonical_candidate_slug(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    if raw in CANONICAL_CANDIDATE_SLUGS:
        return raw
    alias_key = _normalize_text(raw)
    return CANDIDATE_ALIASES.get(alias_key)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles_document() -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload = _load_json(ARTICLES_FILE)
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
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if wrapper is None:
        payload: object = articles
    else:
        wrapper["articles"] = articles
        wrapper["last_updated"] = utc_now_iso()
        wrapper["total_count"] = len(articles)
        payload = wrapper
    ARTICLES_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _load_pipeline_errors() -> dict[str, Any]:
    if not PIPELINE_ERRORS_FILE.exists():
        return {"errors": [], "last_checked": None}
    try:
        payload = _load_json(PIPELINE_ERRORS_FILE)
    except json.JSONDecodeError:
        return {"errors": [], "last_checked": None}
    if not isinstance(payload, dict):
        return {"errors": [], "last_checked": None}
    if not isinstance(payload.get("errors"), list):
        payload["errors"] = []
    return payload


def _append_pipeline_error(
    *,
    script: str,
    message: str,
    article_id: str | None = None,
    provider: str | None = None,
) -> None:
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": utc_now_iso(),
            "tier": "editor",
            "script": script,
            "article_id": article_id,
            "provider": provider,
            "message": message,
        }
    )
    payload["last_checked"] = utc_now_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _to_clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def _normalize_candidate_list(values: object) -> list[str]:
    normalized: list[str] = []
    for item in _to_clean_string_list(values):
        slug = _canonical_candidate_slug(item)
        if slug and slug not in normalized:
            normalized.append(slug)
    return normalized


def _normalize_topics(values: object) -> list[str]:
    normalized: list[str] = []
    for topic in _to_clean_string_list(values):
        slug = topic.strip().lower()
        if slug in VALID_TOPICS and slug not in normalized:
            normalized.append(slug)
    return normalized


def _normalize_sentiment_per_candidate(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for candidate, sentiment in value.items():
        slug = _canonical_candidate_slug(candidate)
        if not slug or not isinstance(sentiment, str):
            continue
        cleaned_sentiment = sentiment.strip().lower()
        if cleaned_sentiment in VALID_SENTIMENT_LABELS:
            normalized[slug] = cleaned_sentiment
    return normalized


def _normalize_summaries(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"pt-BR": "", "en-US": ""}
    pt_value = value.get("pt-BR")
    en_value = value.get("en-US")
    pt = pt_value.strip() if isinstance(pt_value, str) else ""
    en = en_value.strip() if isinstance(en_value, str) else ""
    return {"pt-BR": pt, "en-US": en}


def _ensure_article_defaults(article: dict[str, Any]) -> None:
    article["summaries"] = _normalize_summaries(article.get("summaries"))
    article["sentiment_per_candidate"] = _normalize_sentiment_per_candidate(
        article.get("sentiment_per_candidate")
    )
    article["candidates_mentioned"] = _normalize_candidate_list(
        article.get("candidates_mentioned")
    )
    article["topics"] = _normalize_topics(article.get("topics"))
    article["narrative_cluster_id"] = (
        article.get("narrative_cluster_id")
        if isinstance(article.get("narrative_cluster_id"), str)
        else None
    )
    article["edit_history"] = (
        article.get("edit_history")
        if isinstance(article.get("edit_history"), list)
        else []
    )
    article["disclaimer_pt"] = DISCLAIMER_PT
    article["disclaimer_en"] = DISCLAIMER_EN
    if not isinstance(article.get("sentiment_score"), (int, float)):
        article["sentiment_score"] = 0.0
    if not isinstance(article.get("confidence_score"), (int, float)):
        article["confidence_score"] = 0.0
    if not isinstance(article.get("relevance_score"), (int, float)):
        article["relevance_score"] = 0.0


def _summaries_are_both_empty(article: dict[str, Any]) -> bool:
    summaries = _normalize_summaries(article.get("summaries"))
    return not summaries["pt-BR"] and not summaries["en-US"]


def _summaries_are_complete(article: dict[str, Any]) -> bool:
    summaries = _normalize_summaries(article.get("summaries"))
    return bool(summaries["pt-BR"]) and bool(summaries["en-US"])


def _validate_content_integrity(content: str, title: str) -> tuple[bool, str]:
    """
    Validate minimal content integrity before calling LLMs.
    Returns (is_valid, reason_if_invalid).
    Criteria:
      - Content must be non-empty and not equal to the title fallback
      - At least 120 characters or at least 15 words
      - Must contain alphabetic characters and a sentence terminator (.!?)
      - At least 80% printable characters
      - Must not look like a bot-detection / error page
    """
    if not isinstance(content, str) or not content.strip():
        return False, "empty content"
    if content.strip() == (title.strip() if isinstance(title, str) else ""):
        return False, "content equals title fallback"
    s = content.strip()
    word_count = len(s.split())
    if len(s) < 120 and word_count < 15:
        return False, f"content too short ({len(s)} chars, {word_count} words)"
    if not any(c.isalpha() for c in s):
        return False, "no alphabetic characters"
    if not any(p in s for p in (".", "!", "?")):
        return False, "no sentence terminator"
    printable_count = sum(1 for c in s if c.isprintable())
    ratio = printable_count / max(1, len(s))
    if ratio < 0.8:
        return False, f"low printable ratio {ratio:.2f}"
    # Detect bot-detection / error pages
    snippet = s[:600].lower()
    for pattern in _BLOCKED_CONTENT_PATTERNS:
        if pattern in snippet:
            return False, f"blocked/error page detected: '{pattern}'"
    return True, ""


def _keyword_hits(text: str, keywords: frozenset[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _is_elections_relevant(
    title: str,
    content: str = "",
    source_category: str = "",
) -> bool:
    """Return True when election-specific signals are strong enough."""
    if not isinstance(title, str) or not title.strip():
        return False
    normalized_title = _normalize_text(title)
    normalized_content = (
        _normalize_text(content)[:800] if isinstance(content, str) else ""
    )
    normalized_text = f"{normalized_title} {normalized_content}".strip()
    source_category_normalized = (
        source_category.strip().lower() if isinstance(source_category, str) else ""
    )

    high_signal_hits = _keyword_hits(normalized_text, ELECTIONS_HIGH_SIGNAL_KEYWORDS)
    candidate_hits = _keyword_hits(normalized_text, CANDIDATE_SIGNAL_KEYWORDS)
    context_hits = _keyword_hits(normalized_text, BRAZIL_CONTEXT_KEYWORDS)
    off_topic_hits = _keyword_hits(normalized_text, OFF_TOPIC_KEYWORDS)

    if off_topic_hits >= 2 and high_signal_hits == 0 and candidate_hits == 0:
        return False

    if high_signal_hits >= 2:
        return True

    if high_signal_hits >= 1 and (candidate_hits >= 1 or context_hits >= 1):
        return True

    if candidate_hits >= 1 and off_topic_hits < 2:
        return True

    if (
        source_category_normalized in {"party", "institutional"}
        and high_signal_hits >= 1
    ):
        return True

    return False


def _should_process(article: dict[str, Any]) -> bool:
    if article.get("status") != "raw":
        return False
    summaries = article.get("summaries")
    if not isinstance(summaries, dict):
        return True
    return _summaries_are_both_empty(article)


def _compute_sentiment_score(labels: dict[str, str]) -> float:
    if not labels:
        return 0.0
    scores = [
        SENTIMENT_TO_SCORE[label]
        for label in labels.values()
        if label in SENTIMENT_TO_SCORE
    ]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def _append_edit_history(article: dict[str, Any], provider: str) -> None:
    history = article.get("edit_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "tier": "editor",
            "at": utc_now_iso(),
            "provider": provider,
            "action": "validated",
            "changes": ["summary_pt", "summary_en"],
        }
    )
    article["edit_history"] = history


def _all_providers_unavailable() -> bool:
    """Check if all AI providers have their circuit breakers open."""
    if not _provider_failure_counts:
        return False
    return all(
        count >= _CIRCUIT_BREAKER_THRESHOLD
        for count in _provider_failure_counts.values()
    )


def summarize_articles(limit: int = 30) -> tuple[int, int, int]:
    articles, wrapper = _load_articles_document()
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)
    feedback_changed = False
    valid_articles: list[dict[str, Any]] = []

    summarized_count = 0
    error_count = 0
    skipped_done_count = 0
    processed_this_run = 0
    _circuit_breaker_logged = False
    limit_reached_logged = False
    llm_processing_enabled = not _all_providers_unavailable()

    if not llm_processing_enabled:
        logger.warning(
            "All AI providers unavailable (circuit breakers open); skipping LLM processing"
        )
        print("All AI providers unavailable; skipping LLM processing")

    for article in articles:
        _ensure_article_defaults(article)

        article_id = article.get("id") if isinstance(article.get("id"), str) else None
        title = (
            article.get("title")
            if isinstance(article.get("title"), str)
            and article.get("title", "").strip()
            else "(sem título)"
        )
        source_category = article.get("source_category")
        source_category_value = (
            source_category if isinstance(source_category, str) else ""
        )
        raw_content = article.get("content")
        content_for_relevance = raw_content if isinstance(raw_content, str) else ""

        if article.get("status") == "irrelevant":
            if editor_feedback.add_article_id_to_feedback(feedback, article):
                feedback_changed = True
            logger.info(
                "Skipping article %s already marked irrelevant: %r",
                article_id or "<missing-id>",
                title,
            )
            continue

        if not _should_process(article):
            if article.get("status") == "raw" and _summaries_are_complete(article):
                skipped_done_count += 1
            valid_articles.append(article)
            continue

        feedback_reason = editor_feedback.feedback_reason_for_article(article, feedback)
        if feedback_reason is not None:
            article["status"] = "irrelevant"
            if editor_feedback.add_article_id_to_feedback(feedback, article):
                feedback_changed = True
            logger.info(
                "Skipping article %s due to editorial feedback (%s): %r",
                article_id or "<missing-id>",
                feedback_reason,
                title,
            )
            continue

        # Relevance gate: skip articles that are clearly not elections-related.
        # Broad RSS feeds (UOL, IstoÉ, Veja, BBC) include health, tech, sports, etc.
        # Mark them "irrelevant" so future runs also skip without re-checking.
        if not _is_elections_relevant(
            title=str(title),
            content=str(content_for_relevance),
            source_category=source_category_value,
        ):
            article["status"] = "irrelevant"
            if editor_feedback.add_article_id_to_feedback(feedback, article):
                feedback_changed = True
            logger.info(
                "Skipping irrelevant article %s: %r",
                article_id or "<missing-id>",
                title,
            )
            continue

        valid_articles.append(article)

        if processed_this_run >= limit:
            if not limit_reached_logged:
                logger.info(
                    "Per-run limit of %d articles reached; deferring the rest to next run.",
                    limit,
                )
                limit_reached_logged = True
            continue

        if not llm_processing_enabled:
            continue

        content = raw_content.strip() if isinstance(raw_content, str) else ""
        if not content:
            logger.warning(
                "Article %s has no content; falling back to title for summarization.",
                article_id or "<missing-id>",
            )
            content = title

        # Validate content integrity before calling LLMs.
        is_valid, reason = _validate_content_integrity(str(content), str(title))
        if not is_valid:
            error_count += 1
            logger.warning(
                "Skipping LLM summarization for article %s: %s",
                article_id or "<missing-id>",
                reason,
            )
            _append_pipeline_error(
                script="summarize.py",
                article_id=article_id,
                provider=None,
                message=f"content validation failed: {reason}",
            )
            continue

        processed_this_run += 1

        # Single LLM call per article — the prompt already requests both pt-BR and en-US.
        if _all_providers_unavailable():
            if not _circuit_breaker_logged:
                logger.warning(
                    "All AI providers unavailable mid-run; disabling further LLM processing"
                )
                _circuit_breaker_logged = True
            llm_processing_enabled = False
            continue

        try:
            result = ai_client.summarize_article(
                title=str(title), content=str(content), language="pt-BR"
            )
        except Exception as exc:
            error_count += 1
            _append_pipeline_error(
                script="summarize.py",
                article_id=article_id,
                provider=None,
                message=str(exc),
            )
            logger.warning(
                "Summarization failed for article %s: %s",
                article_id or "<missing-id>",
                exc,
            )
            continue

        raw_summaries = result.get("summaries")
        pt_summary = (
            raw_summaries.get("pt-BR", "").strip()
            if isinstance(raw_summaries, dict)
            else ""
        )
        en_summary = (
            raw_summaries.get("en-US", "").strip()
            if isinstance(raw_summaries, dict)
            else ""
        )
        summaries = {
            "pt-BR": pt_summary or title,
            "en-US": en_summary or title,
        }

        merged_candidates = _normalize_candidate_list(
            result.get("candidates_mentioned")
        )
        merged_topics = _normalize_topics(result.get("topics"))
        merged_sentiment = _normalize_sentiment_per_candidate(
            result.get("sentiment_per_candidate")
        )

        provider = (
            result.get("_ai_provider")
            if isinstance(result.get("_ai_provider"), str)
            else "unknown"
        )
        model = (
            result.get("_ai_model")
            if isinstance(result.get("_ai_model"), str)
            else "unknown"
        )

        has_real_summaries = (
            pt_summary and pt_summary != title and en_summary and en_summary != title
        )
        had_parse_error = bool(result.get("_parse_error"))
        if has_real_summaries and not had_parse_error:
            confidence_score = 1.0
        elif had_parse_error:
            confidence_score = 0.6
        else:
            confidence_score = 0.8

        article["summaries"] = summaries
        article["candidates_mentioned"] = merged_candidates
        article["topics"] = merged_topics
        article["sentiment_per_candidate"] = merged_sentiment
        article["sentiment_score"] = _compute_sentiment_score(merged_sentiment)
        article["confidence_score"] = confidence_score
        article["_ai_provider"] = provider
        article["_ai_model"] = model
        article["ai_provider_editor"] = model

        if confidence_score < 0.6:
            article["status"] = "raw"
            article["editor_note"] = "low confidence"
        else:
            article["status"] = "validated"
            article["editor_note"] = None
            _append_edit_history(article, provider=str(provider))

        summarized_count += 1

    if feedback_changed or not EDITOR_FEEDBACK_FILE.exists():
        editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)

    _save_articles_document(valid_articles, wrapper)
    print(
        f"Summarized {summarized_count} articles ({error_count} errors, {skipped_done_count} skipped already-done)"
    )
    return summarized_count, error_count, skipped_done_count


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Editor-tier article summarization")
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=30,
        help="Maximum articles to process per run (default: 30)",
    )
    args = parser.parse_args()
    summarize_articles(limit=args.limit)


if __name__ == "__main__":
    main()
