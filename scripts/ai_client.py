"""AI client with multi-provider fallback and usage tracking for Phase 02."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import TypedDict

import openai

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
USAGE_FILE = ROOT_DIR / "data" / "ai_usage.json"

OPENROUTER_DAILY_MAX = 200

# In-process circuit breaker: skip providers after this many consecutive failures per run.
_CIRCUIT_BREAKER_THRESHOLD = 3
_provider_failure_counts: dict[str, int] = {}

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
VALID_STANCES = {"favor", "against", "neutral", "unclear"}
VALID_CONFIDENCE = {"high", "medium", "low"}
HIGH_OR_MEDIUM_CONFIDENCE = {"high", "medium"}

MARKDOWN_JSON_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)

NVIDIA_MODELS: dict[str, str] = {
    "summarization": "qwen/qwen3.5-397b-a17b",
    "sentiment": "minimaxai/minimax-m2.5",
    "multilingual": "moonshotai/kimi-k2.5",
    "quiz_extract": "qwen/qwen3-235b-a22b-thinking-2507",
}


class ProviderConfig(TypedDict, total=False):
    name: str
    base_url: str
    key_env: str
    model: str
    paid: bool
    daily_max: int


class ProviderResult(TypedDict):
    content: str
    provider: str
    model: str
    paid: bool


def build_article_id(url: str) -> str:
    """Return deterministic article id based on sha256(url.encode())[:16]."""
    return sha256(url.encode("utf-8")).hexdigest()[:16]


def _today_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _provider_chain_for_task(task: str) -> list[ProviderConfig]:
    nvidia_model = NVIDIA_MODELS.get(task, NVIDIA_MODELS["summarization"])
    return [
        {
            "name": "nvidia",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "key_env": "NVIDIA_API_KEY",
            "model": nvidia_model,
            "paid": False,
        },
        {
            "name": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "key_env": "OPENROUTER_API_KEY",
            "model": "arcee-ai/trinity-large-preview:free",
            "paid": False,
            "daily_max": OPENROUTER_DAILY_MAX,
        },
        {
            "name": "ollama",
            "base_url": "https://ollama.com/v1",
            "key_env": "OLLAMA_API_KEY",
            "model": "minimax-m2.5:cloud",
            "paid": False,
        },
        {
            "name": "vertex",
            "base_url": os.environ.get("VERTEX_BASE_URL", "").strip(),
            "key_env": "VERTEX_ACCESS_TOKEN",
            "model": "google/gemini-2.5-flash-lite-001",
            "paid": True,
        },
        {
            "name": "mimo",
            "base_url": "https://api.xiaomimimo.com/v1",
            "key_env": "XIAOMI_MIMO_API_KEY",
            "model": "mimo-v2-flash",
            "paid": True,
        },
    ]


def _load_usage() -> dict[str, int]:
    try:
        raw = USAGE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        logger.warning("[AI] Could not read usage file %s: %s", USAGE_FILE, exc)
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("[AI] Usage file is invalid JSON (%s): %s", USAGE_FILE, exc)
        return {}

    if not isinstance(parsed, dict):
        logger.warning("[AI] Usage file has invalid structure (expected object): %s", USAGE_FILE)
        return {}

    usage: dict[str, int] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, int):
            usage[key] = value
    return usage


def _save_usage(usage: dict[str, int]) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(usage, indent=2, sort_keys=True), encoding="utf-8")


def _extract_content_from_response(response: object) -> str:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        raise ValueError("Provider response has no choices.")

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)

    if isinstance(content, str):
        cleaned = content.strip()
        if cleaned:
            return cleaned
        # empty string — thinking model may have put answer in reasoning_content; fall through

    if isinstance(content, list):
        # Handle content blocks from thinking/multimodal models.
        # Prefer items with type "text" or "output_text"; ignore "thinking" blocks.
        chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "text")
            if item_type in ("text", "output_text"):
                maybe_text = item.get("text")
                if isinstance(maybe_text, str) and maybe_text.strip():
                    chunks.append(maybe_text.strip())
        if chunks:
            return " ".join(chunks).strip()

    # Some NVIDIA thinking models surface the final answer in reasoning_content when
    # the content field is empty. Use it only as a last resort.
    reasoning = getattr(message, "reasoning_content", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()

    raise ValueError("Provider response content is not text.")


def _request_completion(
    provider: ProviderConfig,
    api_key: str,
    system: str,
    user: str,
    max_tokens: int,
) -> str:
    client = openai.OpenAI(api_key=api_key, base_url=provider["base_url"])
    response = client.chat.completions.create(
        model=provider["model"],
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return _extract_content_from_response(response)


def _call_with_fallback_for_task(
    system: str,
    user: str,
    max_tokens: int,
    task: str,
) -> ProviderResult:
    usage = _load_usage()
    today = _today_key()
    error_messages: list[str] = []

    for provider in _provider_chain_for_task(task):
        name = provider["name"]
        key_env = provider["key_env"]
        api_key = os.environ.get(key_env, "").strip()
        base_url = provider.get("base_url", "").strip()

        if not api_key:
            logger.info("[AI] %s skipped: missing %s.", name, key_env)
            continue
        if not base_url:
            logger.info("[AI] %s skipped: missing base URL.", name)
            continue

        # Circuit breaker: skip providers that have failed too many times this run.
        if _provider_failure_counts.get(name, 0) >= _CIRCUIT_BREAKER_THRESHOLD:
            logger.info("[AI] %s skipped: circuit breaker open (%d consecutive failures).", name, _provider_failure_counts[name])
            continue

        if name == "openrouter":
            daily_max = int(provider.get("daily_max", OPENROUTER_DAILY_MAX))
            usage_key = f"openrouter_{today}"
            if usage.get(usage_key, 0) >= daily_max:
                logger.warning("[AI] openrouter skipped: daily limit reached (%s).", daily_max)
                continue

        try:
            content = _request_completion(
                provider=provider,
                api_key=api_key,
                system=system,
                user=user,
                max_tokens=max_tokens,
            )
            # Success — reset failure counter for this provider.
            _provider_failure_counts[name] = 0
            usage_key = f"{name}_{today}"
            usage[usage_key] = usage.get(usage_key, 0) + 1
            _save_usage(usage)
            return {
                "content": content,
                "provider": name,
                "model": provider["model"],
                "paid": bool(provider["paid"]),
            }
        except Exception as exc:
            _provider_failure_counts[name] = _provider_failure_counts.get(name, 0) + 1
            error_messages.append(f"{name}: {exc}")
            logger.warning("[AI] %s failed: %s", name, exc)

    error_details = "; ".join(error_messages) if error_messages else "no providers configured"
    raise RuntimeError(f"All AI providers failed ({error_details}).")


def call_with_fallback(system: str, user: str, max_tokens: int = 500) -> ProviderResult:
    """Try each provider in order and return the first successful response."""
    return _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=max_tokens,
        task="summarization",
    )


def _strip_markdown_code_fence(text: str) -> str:
    stripped = text.strip()
    match = MARKDOWN_JSON_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _parse_json_dict(text: str) -> dict[str, object]:
    maybe_json = _strip_markdown_code_fence(text)
    parsed = json.loads(maybe_json)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object response.")
    return parsed


def _to_clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned and cleaned not in output:
                output.append(cleaned)
    return output


def _normalize_topics(value: object) -> list[str]:
    candidates = _to_clean_string_list(value)
    return [topic for topic in candidates if topic in VALID_TOPICS]


def _normalize_sentiment_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for maybe_name, maybe_label in value.items():
        if not isinstance(maybe_name, str) or not isinstance(maybe_label, str):
            continue
        name = maybe_name.strip()
        label = maybe_label.strip().lower()
        if name and label in VALID_SENTIMENT_LABELS:
            normalized[name] = label
    return normalized


def _normalize_summaries(
    summaries_value: object,
    summary_value: object,
    preferred_language: str,
    title: str,
) -> dict[str, str]:
    summaries = {"pt-BR": "", "en-US": ""}

    if isinstance(summaries_value, dict):
        pt_summary = summaries_value.get("pt-BR")
        en_summary = summaries_value.get("en-US")
        if isinstance(pt_summary, str):
            summaries["pt-BR"] = pt_summary.strip()
        if isinstance(en_summary, str):
            summaries["en-US"] = en_summary.strip()

    if isinstance(summary_value, str) and summary_value.strip():
        if preferred_language == "en-US":
            summaries["en-US"] = summaries["en-US"] or summary_value.strip()
        else:
            summaries["pt-BR"] = summaries["pt-BR"] or summary_value.strip()

    if not summaries["pt-BR"] and summaries["en-US"]:
        summaries["pt-BR"] = summaries["en-US"]
    if not summaries["en-US"] and summaries["pt-BR"]:
        summaries["en-US"] = summaries["pt-BR"]
    if not summaries["pt-BR"] and not summaries["en-US"]:
        summaries = {"pt-BR": title, "en-US": title}

    return summaries


def summarize_article(title: str, content: str, language: str = "pt-BR") -> dict[str, object]:
    """Generate bilingual summary, entities, and sentiment labels from article text."""
    preferred_language = "en-US" if language == "en-US" else "pt-BR"
    language_hint = (
        "Prefer concise English wording for the primary summary."
        if preferred_language == "en-US"
        else "Prefira redacao concisa em portugues brasileiro para o resumo principal."
    )
    truncated_content = content.strip()[:2500]

    system = (
        "Voce e um analista politico especializado nas eleicoes brasileiras de 2026. "
        "Responda APENAS com JSON valido, sem markdown. "
        "Sempre inclua resumos bilingues com chaves 'pt-BR' e 'en-US'."
    )
    user = f"""Titulo: {title}
Conteudo: {truncated_content}
{language_hint}

Retorne JSON:
{{
  "summaries": {{
    "pt-BR": "resumo em 2-3 frases",
    "en-US": "summary in 2-3 sentences"
  }},
  "candidates_mentioned": ["nomes exatos"],
  "topics": ["economia", "seguranca", "saude", "educacao", "meio_ambiente", "corrupcao", "armas", "privatizacao", "previdencia", "politica_ext", "lgbtq", "aborto", "indigenas", "impostos", "midia", "eleicoes"],
  "sentiment_per_candidate": {{"Nome": "positivo|neutro|negativo"}}
}}"""

    response = _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=450,
        task="multilingual",
    )

    try:
        parsed = _parse_json_dict(response["content"])
        summaries = _normalize_summaries(
            summaries_value=parsed.get("summaries"),
            summary_value=parsed.get("summary"),
            preferred_language=preferred_language,
            title=title,
        )
        return {
            "summary": summaries[preferred_language],
            "summaries": summaries,
            "candidates_mentioned": _to_clean_string_list(parsed.get("candidates_mentioned")),
            "topics": _normalize_topics(parsed.get("topics")),
            "sentiment_per_candidate": _normalize_sentiment_map(parsed.get("sentiment_per_candidate")),
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_language": preferred_language,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("[AI] summarize_article parse failure: %s", exc)
        fallback_summaries = {"pt-BR": title, "en-US": title}
        return {
            "summary": fallback_summaries[preferred_language],
            "summaries": fallback_summaries,
            "candidates_mentioned": [],
            "topics": [],
            "sentiment_per_candidate": {},
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_language": preferred_language,
            "_parse_error": True,
        }


def _normalize_optional_text(value: object) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return None


def _normalize_optional_int(value: object, min_value: int, max_value: int) -> int | None:
    if isinstance(value, int) and min_value <= value <= max_value:
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        if min_value <= parsed <= max_value:
            return parsed
    return None


def extract_candidate_position(candidate: str, topic_id: str, snippets: list[str]) -> dict[str, object]:
    """Extract a verifiable candidate stance from snippets, filtering low-confidence output."""
    if not snippets:
        return {
            "position_pt": None,
            "position_en": None,
            "stance": "unclear",
            "confidence": "low",
            "best_source_snippet_index": None,
        }

    rendered_snippets = "\n".join(
        f"[{index}] {snippet}" for index, snippet in enumerate(snippets[:12], start=1)
    )
    system = (
        "Voce e um analista politico. "
        "Extraia apenas posicoes verificaveis com base em evidencias textuais. "
        "Responda APENAS com JSON valido."
    )
    user = f"""Candidato: {candidate}
Topico: {topic_id}
Trechos ({min(len(snippets), 12)}):
{rendered_snippets}

Retorne JSON:
{{
  "position_pt": "posicao em portugues, ou null",
  "position_en": "position in English, or null",
  "stance": "favor|against|neutral|unclear",
  "confidence": "high|medium|low",
  "best_source_snippet_index": 1
}}"""

    response = _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=350,
        task="quiz_extract",
    )

    try:
        parsed = _parse_json_dict(response["content"])
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("[AI] extract_candidate_position parse failure: %s", exc)
        return {
            "position_pt": None,
            "position_en": None,
            "stance": "unclear",
            "confidence": "low",
            "best_source_snippet_index": None,
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_parse_error": True,
        }

    stance_raw = parsed.get("stance")
    confidence_raw = parsed.get("confidence")
    stance = stance_raw.strip().lower() if isinstance(stance_raw, str) else "unclear"
    confidence = confidence_raw.strip().lower() if isinstance(confidence_raw, str) else "low"
    if stance not in VALID_STANCES:
        stance = "unclear"
    if confidence not in VALID_CONFIDENCE:
        confidence = "low"

    position_pt = _normalize_optional_text(parsed.get("position_pt"))
    position_en = _normalize_optional_text(parsed.get("position_en"))
    best_index = _normalize_optional_int(parsed.get("best_source_snippet_index"), 1, len(snippets))

    if confidence not in HIGH_OR_MEDIUM_CONFIDENCE or stance == "unclear":
        position_pt = None
        position_en = None

    return {
        "position_pt": position_pt,
        "position_en": position_en,
        "stance": stance,
        "confidence": confidence,
        "best_source_snippet_index": best_index,
        "_ai_provider": response["provider"],
        "_ai_model": response["model"],
    }


__all__ = [
    "NVIDIA_MODELS",
    "USAGE_FILE",
    "build_article_id",
    "call_with_fallback",
    "summarize_article",
    "extract_candidate_position",
]
