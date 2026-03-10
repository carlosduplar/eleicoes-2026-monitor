"""Editor-tier article summarization for Phase 06."""

from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import ai_client
except ImportError:  # pragma: no cover - direct script execution path
    import ai_client  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"

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

VALID_SENTIMENT_LABELS = {"positivo", "neutro", "negativo"}
SENTIMENT_TO_SCORE = {"positivo": 1.0, "neutro": 0.0, "negativo": -1.0}

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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _save_articles_document(articles: list[dict[str, Any]], wrapper: dict[str, Any] | None) -> None:
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if wrapper is None:
        payload: object = articles
    else:
        wrapper["articles"] = articles
        wrapper["last_updated"] = utc_now_iso()
        wrapper["total_count"] = len(articles)
        payload = wrapper
    ARTICLES_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    PIPELINE_ERRORS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    article["sentiment_per_candidate"] = _normalize_sentiment_per_candidate(article.get("sentiment_per_candidate"))
    article["candidates_mentioned"] = _normalize_candidate_list(article.get("candidates_mentioned"))
    article["topics"] = _normalize_topics(article.get("topics"))
    article["narrative_cluster_id"] = article.get("narrative_cluster_id") if isinstance(article.get("narrative_cluster_id"), str) else None
    article["edit_history"] = article.get("edit_history") if isinstance(article.get("edit_history"), list) else []
    article["disclaimer_pt"] = DISCLAIMER_PT
    article["disclaimer_en"] = DISCLAIMER_EN
    if not isinstance(article.get("sentiment_score"), (int, float)):
        article["sentiment_score"] = 0.0
    if not isinstance(article.get("confidence_score"), (int, float)):
        article["confidence_score"] = 0.0


def _summaries_are_both_empty(article: dict[str, Any]) -> bool:
    summaries = _normalize_summaries(article.get("summaries"))
    return not summaries["pt-BR"] and not summaries["en-US"]


def _summaries_are_complete(article: dict[str, Any]) -> bool:
    summaries = _normalize_summaries(article.get("summaries"))
    return bool(summaries["pt-BR"]) and bool(summaries["en-US"])


def _should_process(article: dict[str, Any]) -> bool:
    if article.get("status") != "raw":
        return False
    summaries = article.get("summaries")
    if not isinstance(summaries, dict):
        return True
    return _summaries_are_both_empty(article)


def _extract_language_summary(result: dict[str, Any], language: str, title: str) -> str:
    summaries = _normalize_summaries(result.get("summaries"))
    summary = summaries.get(language, "").strip()
    if summary:
        return summary
    fallback = result.get("summary")
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return title


def _merge_sentiment_labels(*values: object) -> dict[str, str]:
    merged: dict[str, str] = {}
    for value in values:
        for candidate, sentiment in _normalize_sentiment_per_candidate(value).items():
            merged[candidate] = sentiment
    return merged


def _compute_sentiment_score(labels: dict[str, str]) -> float:
    if not labels:
        return 0.0
    scores = [SENTIMENT_TO_SCORE[label] for label in labels.values() if label in SENTIMENT_TO_SCORE]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def _compute_confidence_score(
    title: str,
    pt_result: dict[str, Any],
    en_result: dict[str, Any],
) -> float:
    if bool(pt_result.get("_parse_error")) or bool(en_result.get("_parse_error")):
        return 0.6

    pt_summary = _extract_language_summary(pt_result, "pt-BR", title)
    en_summary = _extract_language_summary(en_result, "en-US", title)
    required_fields = ("candidates_mentioned", "topics", "sentiment_per_candidate")
    has_required_fields = all(field in pt_result and field in en_result for field in required_fields)
    has_non_fallback_summaries = pt_summary != title and en_summary != title

    if has_required_fields and has_non_fallback_summaries:
        return 1.0
    return 0.8


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


def summarize_articles() -> tuple[int, int, int]:
    articles, wrapper = _load_articles_document()

    summarized_count = 0
    error_count = 0
    skipped_done_count = 0

    for article in articles:
        _ensure_article_defaults(article)

        if not _should_process(article):
            if article.get("status") == "raw" and _summaries_are_complete(article):
                skipped_done_count += 1
            continue

        article_id = article.get("id") if isinstance(article.get("id"), str) else None
        title = article.get("title") if isinstance(article.get("title"), str) and article.get("title", "").strip() else "(sem título)"
        raw_content = article.get("content")
        content = raw_content.strip() if isinstance(raw_content, str) else ""
        if not content:
            logger.warning("Article %s has no content; falling back to title for summarization.", article_id or "<missing-id>")
            content = title

        try:
            pt_result = ai_client.summarize_article(title=title, content=content, language="pt-BR")
            en_result = ai_client.summarize_article(title=title, content=content, language="en-US")
        except Exception as exc:
            error_count += 1
            _append_pipeline_error(
                script="summarize.py",
                article_id=article_id,
                provider=None,
                message=str(exc),
            )
            logger.warning("Summarization failed for article %s: %s", article_id or "<missing-id>", exc)
            continue

        summaries = {
            "pt-BR": _extract_language_summary(pt_result, "pt-BR", title),
            "en-US": _extract_language_summary(en_result, "en-US", title),
        }
        if not summaries["pt-BR"]:
            summaries["pt-BR"] = title
        if not summaries["en-US"]:
            summaries["en-US"] = title

        merged_candidates: list[str] = []
        for candidate in _normalize_candidate_list(pt_result.get("candidates_mentioned")) + _normalize_candidate_list(
            en_result.get("candidates_mentioned")
        ):
            if candidate not in merged_candidates:
                merged_candidates.append(candidate)

        merged_topics: list[str] = []
        for topic in _normalize_topics(pt_result.get("topics")) + _normalize_topics(en_result.get("topics")):
            if topic not in merged_topics:
                merged_topics.append(topic)

        merged_sentiment = _merge_sentiment_labels(
            pt_result.get("sentiment_per_candidate"),
            en_result.get("sentiment_per_candidate"),
        )

        provider = pt_result.get("_ai_provider") if isinstance(pt_result.get("_ai_provider"), str) else "unknown"
        model = pt_result.get("_ai_model") if isinstance(pt_result.get("_ai_model"), str) else "unknown"
        if provider == "unknown" and isinstance(en_result.get("_ai_provider"), str):
            provider = en_result["_ai_provider"]  # type: ignore[index]
        if model == "unknown" and isinstance(en_result.get("_ai_model"), str):
            model = en_result["_ai_model"]  # type: ignore[index]

        confidence_score = _compute_confidence_score(title=title, pt_result=pt_result, en_result=en_result)

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
            _append_edit_history(article, provider=provider)

        summarized_count += 1

    _save_articles_document(articles, wrapper)
    print(f"Summarized {summarized_count} articles ({error_count} errors, {skipped_done_count} skipped already-done)")
    return summarized_count, error_count, skipped_done_count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    summarize_articles()


if __name__ == "__main__":
    main()
