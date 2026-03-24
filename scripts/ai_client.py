"""AI client with multi-provider fallback and usage tracking.

Task routing follows quiz architecture requirements:
- High-quality extraction/generation tasks prefer Gemini (Vertex) first.
- Structured validation tasks prefer free NVIDIA providers first.
- Legacy summarization tasks keep free-first routing.
"""

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
USAGE_FILE = ROOT_DIR / "site" / "public" / "data" / "ai_usage.json"

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
VALID_POSITION_TYPES = {"confirmed", "inferred", "unknown"}
VALID_POSITION_STANCES = {
    "strongly_favor",
    "favor",
    "neutral",
    "against",
    "strongly_against",
    "unknown",
}
POSITION_STANCE_TO_WEIGHT = {
    "strongly_favor": 3,
    "favor": 2,
    "neutral": 0,
    "against": -2,
    "strongly_against": -3,
}

MARKDOWN_JSON_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL
)

# These NVIDIA models run in "thinking" mode by default and surface the chain-of-thought
# in `reasoning_content` while leaving `content` empty. For JSON tasks we MUST disable
# thinking so the final answer arrives in `content`.
_THINKING_DISABLE_EXTRA_BODY: dict[str, dict[str, object]] = {
    "qwen/qwen3-235b-a22b-thinking-2507": {
        "chat_template_kwargs": {"enable_thinking": False}
    },
    "qwen/qwen3.5-397b-a17b": {"chat_template_kwargs": {"enable_thinking": False}},
    "nvidia/nemotron-3-super-120b-a12b": {
        "chat_template_kwargs": {"enable_thinking": False}
    },
    "moonshotai/kimi-k2.5": {"thinking": {"type": "disabled"}},
    "minimaxai/minimax-m2.5": {"thinking": {"type": "disabled"}},
}

NVIDIA_MODELS: dict[str, str] = {
    "summarization": "nvidia/nemotron-3-super-120b-a12b",
    "sentiment": "nvidia/nemotron-3-super-120b-a12b",
    "multilingual": "nvidia/nemotron-3-super-120b-a12b",
    "quiz_extract": "minimaxai/minimax-m2.5",
}

NVIDIA_FALLBACKS: list[str] = []

OLLAMA_MODELS: list[str] = [
    "nemotron-3-super:cloud",
]


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


def _get_gemini_model(task: str) -> str:
    override = os.environ.get("GEMINI_MODEL_OVERRIDE")
    if override:
        return override
    return "gemini-3.1-flash-lite-preview"


def _get_vertex_model(task: str) -> str:
    override = os.environ.get("VERTEX_MODEL_OVERRIDE")
    if override:
        return override
    return "gemini-3-flash-preview"


def _provider_chain_for_task(task: str) -> list[ProviderConfig]:
    if task in {"positions_extract", "quiz_generate", "quiz_extract"}:
        return [
            {
                "name": "vertex",
                "base_url": "VERTEX_BASE_URL",
                "key_env": "VERTEX_API_KEY",
                "model": _get_vertex_model(task),
                "paid": True,
            },
            {
                "name": "ollama",
                "base_url": "https://ollama.com/v1",
                "key_env": "OLLAMA_API_KEY",
                "model": "kimi-k2.5:cloud",
                "paid": False,
            },
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "key_env": "NVIDIA_API_KEY",
                "model": "minimaxai/minimax-m2.5",
                "paid": False,
            },
        ]

    if task == "quiz_validate":
        return [
            {
                "name": "ollama",
                "base_url": "https://ollama.com/v1",
                "key_env": "OLLAMA_API_KEY",
                "model": "kimi-k2.5:cloud",
                "paid": False,
            },
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "key_env": "NVIDIA_API_KEY",
                "model": "minimaxai/minimax-m2.5",
                "paid": False,
            },
            {
                "name": "vertex",
                "base_url": "VERTEX_BASE_URL",
                "key_env": "VERTEX_API_KEY",
                "model": _get_vertex_model(task),
                "paid": True,
            },
        ]

    nvidia_primary = NVIDIA_MODELS.get(task, NVIDIA_MODELS["summarization"])
    nvidia_all = list(dict.fromkeys([nvidia_primary, *NVIDIA_FALLBACKS]))
    return [
        *[
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "key_env": "NVIDIA_API_KEY",
                "model": model,
                "paid": False,
            }
            for model in nvidia_all
        ],
        *[
            {
                "name": "ollama",
                "base_url": "https://ollama.com/v1",
                "key_env": "OLLAMA_API_KEY",
                "model": model,
                "paid": False,
            }
            for model in OLLAMA_MODELS
        ],
        *[
            {
                "name": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "key_env": "GEMINI_API_KEY",
                "model": _get_gemini_model(task),
                "paid": False,
            }
        ],
        {
            "name": "vertex",
            "base_url": "VERTEX_BASE_URL",
            "key_env": "VERTEX_ACCESS_TOKEN",
            "model": _get_vertex_model(task),
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
        logger.warning(
            "[AI] Usage file has invalid structure (expected object): %s", USAGE_FILE
        )
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
            if "<think>" in cleaned:
                # Strip inline <think>...</think> blocks emitted by models that embed
                # chain-of-thought in the content field (e.g. MiniMax M2.5 via SGLang
                # without a dedicated reasoning parser).
                stripped = re.sub(
                    r"<think>.*?</think>\s*", "", cleaned, flags=re.DOTALL
                ).strip()
                if stripped:
                    return stripped
                logger.warning(
                    "[AI] Provider returned only <think> content with no final answer; "
                    "checking reasoning_content"
                )
            else:
                return cleaned
        else:
            logger.warning(
                "[AI] Provider returned empty string content, checking reasoning_content"
            )

    if isinstance(content, list):
        # Handle content blocks from thinking/multimodal models.
        # Prefer items with type "text" or "output_text"; ignore "thinking" blocks.
        chunks: list[str] = []
        for item in content:
            item_type = "text"
            maybe_text: object | None = None
            if isinstance(item, dict):
                raw_item_type = item.get("type", "text")
                if isinstance(raw_item_type, str):
                    item_type = raw_item_type
                maybe_text = item.get("text")
            else:
                raw_item_type = getattr(item, "type", "text")
                if isinstance(raw_item_type, str):
                    item_type = raw_item_type
                maybe_text = getattr(item, "text", None)
            if item_type in ("text", "output_text"):
                if isinstance(maybe_text, str) and maybe_text.strip():
                    chunks.append(maybe_text.strip())
        if chunks:
            return " ".join(chunks).strip()

    content_text = getattr(content, "text", None)
    if isinstance(content_text, str):
        cleaned_content_text = content_text.strip()
        if cleaned_content_text:
            return cleaned_content_text

    # Some NVIDIA thinking models surface the final answer in reasoning_content when
    # the content field is empty. Try to extract a JSON block first; if that fails
    # we raise rather than returning raw prose that would break every JSON parser.
    reasoning = getattr(message, "reasoning_content", None)
    if isinstance(reasoning, str) and reasoning.strip():
        json_block = _extract_last_json_block(reasoning.strip())
        if json_block:
            logger.warning(
                "[AI] Extracted JSON block from reasoning_content (content was empty)"
            )
            return json_block
        logger.warning(
            "[AI] reasoning_content has no parseable JSON block; skipping provider. "
            "Tip: add this model to _THINKING_DISABLE_EXTRA_BODY to suppress thinking mode."
        )
        raise ValueError("Provider returned only prose reasoning_content with no JSON.")

    logger.warning(
        "[AI] Provider response content is not text. content=%r, reasoning=%r",
        str(content)[:200] if content else None,
        str(reasoning)[:200] if reasoning else None,
    )
    raise ValueError("Provider response content is not text.")


def _request_completion(
    provider: ProviderConfig,
    api_key: str,
    system: str,
    user: str,
    max_tokens: int,
) -> str:
    if provider.get("name") == "vertex":
        import json
        import urllib.request

        api_key = os.environ.get("VERTEX_API_KEY", "").strip()
        if not api_key:
            raise ValueError("VERTEX_API_KEY environment variable is missing.")

        grounding_enabled = os.environ.get(
            "VERTEX_GROUNDING_ENABLED", ""
        ).strip().lower() in ("1", "true", "yes")

        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{provider['model']}:generateContent"
        data = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": {"maxOutputTokens": 8192},
        }
        if grounding_enabled:
            data["tools"] = [{"googleSearch": {}}]
        req = urllib.request.Request(
            f"{url}?key={api_key}",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            resp_data = json.loads(response.read().decode("utf-8"))
            if isinstance(resp_data, list):
                resp_data = resp_data[0]
            try:
                return resp_data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise ValueError(
                    f"Unexpected Vertex response format: {resp_data}"
                ) from e

    client_kwargs: dict[str, object] = {
        "api_key": api_key,
        "base_url": provider["base_url"],
    }

    default_headers: dict[str, str] = {}
    if provider.get("name") == "openrouter":
        http_referer = os.environ.get("OPENROUTER_HTTP_REFERER", "").strip()
        app_title = os.environ.get("OPENROUTER_APP_TITLE", "").strip()
        if http_referer:
            default_headers["HTTP-Referer"] = http_referer
        if app_title:
            default_headers["X-Title"] = app_title

    if default_headers:
        client_kwargs["default_headers"] = default_headers

    client = openai.OpenAI(**client_kwargs)
    kwargs: dict[str, object] = {
        "model": provider["model"],
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # Enable Google Search Grounding for Gemini models (opt-in via env var)
    if (
        provider.get("name") == "gemini"
        and os.environ.get("GEMINI_GROUNDING_ENABLED", "").strip()
    ):
        kwargs["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "google_search",
                    "description": "Google Search Grounding",
                },
            }
        ]
    # Disable thinking mode for NVIDIA thinking models so the answer lands in
    # `content` as clean JSON rather than being buried in `reasoning_content`.
    if provider.get("name") == "nvidia":
        disable_body = _THINKING_DISABLE_EXTRA_BODY.get(provider.get("model", ""))
        if disable_body:
            kwargs["extra_body"] = disable_body
    elif provider.get("name") == "mimo":
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    try:
        response = client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
    except Exception as e:
        if provider.get("name") == "mimo":
            logger.warning(
                "[AI] MiMo request failed. API key length: %d, base_url: %s",
                len(api_key),
                provider.get("base_url", "missing"),
            )
        raise
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

        if base_url == "VERTEX_BASE_URL":
            if not os.environ.get("VERTEX_BASE_URL", "").strip():
                logger.info("[AI] %s skipped: missing VERTEX_BASE_URL in env.", name)
                continue
        elif not base_url:
            logger.info("[AI] %s skipped: missing base URL.", name)
            continue

        # Circuit breaker: skip providers that have failed too many times this run.
        if _provider_failure_counts.get(name, 0) >= _CIRCUIT_BREAKER_THRESHOLD:
            logger.info(
                "[AI] %s skipped: circuit breaker open (%d consecutive failures).",
                name,
                _provider_failure_counts[name],
            )
            continue

        daily_max_raw = provider.get("daily_max")
        if daily_max_raw is not None:
            daily_max = int(daily_max_raw)
            usage_key = f"{name}_{today}"
            if usage.get(usage_key, 0) >= daily_max:
                logger.warning(
                    "[AI] %s skipped: daily limit reached (%s).", name, daily_max
                )
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
            if name == "nvidia" and _is_not_found_error(exc):
                _provider_failure_counts[name] = _CIRCUIT_BREAKER_THRESHOLD
                logger.info(
                    "[AI] %s unavailable (404). Opening circuit breaker for this run.",
                    name,
                )
            elif _is_rate_limit_error(exc):
                _provider_failure_counts[name] = _CIRCUIT_BREAKER_THRESHOLD
                logger.info(
                    "[AI] %s rate limited (429/quota). Opening circuit breaker for this run.",
                    name,
                )
            else:
                logger.warning("[AI] %s failed: %s", name, exc)
                if name == "mimo":
                    logger.warning(
                        "[AI] MiMo API key status: %s", "set" if api_key else "missing"
                    )

    error_details = (
        "; ".join(error_messages) if error_messages else "no providers configured"
    )
    raise RuntimeError(f"All AI providers failed ({error_details}).")


def call_with_fallback(system: str, user: str, max_tokens: int = 500) -> ProviderResult:
    """Try each provider in order and return the first successful response."""
    return _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=max_tokens,
        task="summarization",
    )


def _extract_last_json_block(text: str) -> str | None:
    """Return the last parseable JSON object found in *text*, or None.

    Used as a last-resort fallback when a thinking model surfaces its chain-of-
    thought in ``reasoning_content`` (which may contain an embedded JSON answer)
    instead of returning clean JSON in ``content``.
    """
    for match in reversed(list(re.finditer(r"\{", text))):
        pos = match.start()
        depth = 0
        end = -1
        for i, ch in enumerate(text[pos:]):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = pos + i + 1
                    break
        if end == -1:
            continue
        candidate = text[pos:end]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return candidate
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _is_not_found_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "404" in message and "not found" in message


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "quota" in message


def _strip_markdown_code_fence(text: str) -> str:
    stripped = text.strip()
    match = MARKDOWN_JSON_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _parse_json_dict(text: str) -> dict[str, object]:
    maybe_json = _strip_markdown_code_fence(text)
    try:
        parsed = json.loads(maybe_json)
    except json.JSONDecodeError:
        recovered = _extract_last_json_block(maybe_json)
        if recovered is None:
            recovered = _extract_last_json_block(text)
        if recovered is None:
            raise
        parsed = json.loads(recovered)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object response.")
    return parsed


def _parse_json_list(text: str) -> list[object]:
    maybe_json = _strip_markdown_code_fence(text)
    try:
        parsed = json.loads(maybe_json)
    except json.JSONDecodeError:
        recovered = _extract_last_json_block(maybe_json)
        if recovered is None:
            recovered = _extract_last_json_block(text)
        if recovered is None:
            raise
        parsed = json.loads(recovered)
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array response.")
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


def summarize_article(
    title: str, content: str, language: str = "pt-BR"
) -> dict[str, object]:
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
            "candidates_mentioned": _to_clean_string_list(
                parsed.get("candidates_mentioned")
            ),
            "topics": _normalize_topics(parsed.get("topics")),
            "sentiment_per_candidate": _normalize_sentiment_map(
                parsed.get("sentiment_per_candidate")
            ),
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_language": preferred_language,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("[AI] summarize_article parse failure: %s", exc)
        logger.warning(
            "[AI] Raw response content: %r",
            response["content"][:500] if response.get("content") else None,
        )
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


def _normalize_optional_int(
    value: object, min_value: int, max_value: int
) -> int | None:
    if isinstance(value, int) and min_value <= value <= max_value:
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        if min_value <= parsed <= max_value:
            return parsed
    return None


def extract_candidate_position(
    candidate: str, topic_id: str, snippets: list[str]
) -> dict[str, object]:
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

    parsed: dict[str, object] | None = None
    for attempt in range(2):
        try:
            parsed = _parse_json_dict(response["content"])
            break
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            if attempt == 0:
                logger.info(
                    "[AI] extract_candidate_position parse failure on first attempt: %s. Retrying once.",
                    exc,
                )
                retry_user = (
                    f"{user}\n\n"
                    "IMPORTANTE: responda somente com um objeto JSON valido, sem markdown "
                    "e sem texto adicional."
                )
                response = _call_with_fallback_for_task(
                    system=system,
                    user=retry_user,
                    max_tokens=350,
                    task="quiz_extract",
                )
                continue
            logger.warning("[AI] extract_candidate_position parse failure: %s", exc)

    if parsed is None:
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
    confidence = (
        confidence_raw.strip().lower() if isinstance(confidence_raw, str) else "low"
    )
    if stance not in VALID_STANCES:
        stance = "unclear"
    if confidence not in VALID_CONFIDENCE:
        confidence = "low"

    position_pt = _normalize_optional_text(parsed.get("position_pt"))
    position_en = _normalize_optional_text(parsed.get("position_en"))
    best_index = _normalize_optional_int(
        parsed.get("best_source_snippet_index"), 1, len(snippets)
    )

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


def extract_candidate_topic_position(
    candidate: str,
    topic_id: str,
    topic_label_pt: str,
    snippets: list[str],
    existing_summary_pt: str | None = None,
) -> dict[str, object]:
    """Extract structured candidate position for candidates_positions.json."""
    if not snippets:
        return {
            "position_type": "unknown",
            "stance": "unknown",
            "summary_pt": None,
            "summary_en": None,
            "key_actions": [],
            "source_indices": [],
            "confidence_reasoning": "No snippets available for this candidate/topic.",
        }

    rendered_snippets = "\n".join(
        f"[{index}] {snippet}" for index, snippet in enumerate(snippets[:12], start=1)
    )
    existing_text = existing_summary_pt or "None"
    system = (
        "Você é um analista político brasileiro. "
        "Extraia posição de política pública apenas quando houver evidência textual. "
        "Responda APENAS com JSON válido."
    )
    user = f"""Candidate: {candidate}
Topic: {topic_id} ({topic_label_pt})
Existing summary_pt: {existing_text}

Article snippets ({min(len(snippets), 12)}):
{rendered_snippets}

Rules:
- Polling data is NOT a policy position.
- Scandal/investigation reports are NOT policy positions.
- If no clear position exists, return position_type=unknown and stance=unknown.

Return JSON:
{{
  "position_type": "confirmed|inferred|unknown",
  "stance": "strongly_favor|favor|neutral|against|strongly_against|unknown",
  "summary_pt": "1-2 frases em pt-BR, ou null",
  "summary_en": "1-2 sentences in en-US, or null",
  "key_actions": ["acao verificavel 1", "acao verificavel 2"],
  "source_indices": [1, 3],
  "confidence_reasoning": "justificativa curta"
}}"""
    response = _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=700,
        task="positions_extract",
    )

    parsed: dict[str, object] | None = None
    try:
        parsed = _parse_json_dict(response["content"])
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("[AI] extract_candidate_topic_position parse failure: %s", exc)

    if parsed is None:
        return {
            "position_type": "unknown",
            "stance": "unknown",
            "summary_pt": None,
            "summary_en": None,
            "key_actions": [],
            "source_indices": [],
            "confidence_reasoning": "Model output could not be parsed.",
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_parse_error": True,
        }

    raw_position_type = parsed.get("position_type")
    position_type = (
        raw_position_type.strip().lower()
        if isinstance(raw_position_type, str)
        else "unknown"
    )
    if position_type not in VALID_POSITION_TYPES:
        position_type = "unknown"

    raw_stance = parsed.get("stance")
    stance = raw_stance.strip().lower() if isinstance(raw_stance, str) else "unknown"
    if stance not in VALID_POSITION_STANCES:
        stance = "unknown"

    summary_pt = _normalize_optional_text(parsed.get("summary_pt"))
    summary_en = _normalize_optional_text(parsed.get("summary_en"))
    key_actions = _to_clean_string_list(parsed.get("key_actions"))
    confidence_reasoning = _normalize_optional_text(parsed.get("confidence_reasoning"))

    source_indices_raw = parsed.get("source_indices")
    source_indices: list[int] = []
    if isinstance(source_indices_raw, list):
        for item in source_indices_raw:
            if isinstance(item, int) and 1 <= item <= len(snippets):
                source_indices.append(item)

    if position_type == "unknown" or stance == "unknown":
        summary_pt = None
        summary_en = None
        key_actions = []
        source_indices = []

    return {
        "position_type": position_type,
        "stance": stance,
        "summary_pt": summary_pt,
        "summary_en": summary_en,
        "key_actions": key_actions,
        "source_indices": source_indices,
        "confidence_reasoning": confidence_reasoning,
        "_ai_provider": response["provider"],
        "_ai_model": response["model"],
    }


def generate_quiz_topic_options(
    topic_id: str,
    topic_label_pt: str,
    topic_label_en: str,
    question_pt: str,
    question_en: str,
    known_positions: list[dict[str, object]],
) -> dict[str, object]:
    """Generate first-person quiz options for a topic from known positions."""
    if not known_positions:
        return {"options": [], "_parse_error": False}

    position_lines: list[str] = []
    for index, position in enumerate(known_positions, start=1):
        stance = str(position.get("stance", "unknown"))
        summary = str(position.get("summary_pt", "")).strip()
        actions = position.get("key_actions")
        if isinstance(actions, list):
            action_text = "; ".join(
                str(item).strip()
                for item in actions
                if isinstance(item, str) and item.strip()
            )
        else:
            action_text = ""
        position_lines.append(
            f'Position {index}: stance={stance}, summary="{summary}", key_actions="{action_text}"'
        )

    system = (
        "Você é designer de quiz político. "
        "Crie opções em primeira pessoa, neutras e ideológicas, sem citar candidatos. "
        "Responda APENAS com JSON válido."
    )
    user = f"""Topic: {topic_id} — {topic_label_pt} / {topic_label_en}
Question pt-BR: {question_pt}
Question en-US: {question_en}

Known positions:
{chr(10).join(position_lines)}

Rules:
1) Nunca mencionar candidato, partido ou biografia.
2) Nunca descrever evento jornalístico, investigação ou pesquisa eleitoral.
3) Opções em primeira pessoa (ex.: "O governo deveria...", "Acredito que...").
4) PT-BR com diacríticos corretos.
5) Cada opção deve ser distinta e corresponder a uma posição.
6) Gere no máximo 6 opções.

Return JSON array:
[
  {{
    "text_pt": "O governo deveria...",
    "text_en": "The government should...",
    "mapped_position": 1,
    "stance": "strongly_favor|favor|neutral|against|strongly_against",
    "weight": 3|2|0|-2|-3
  }}
]"""
    response = _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=900,
        task="quiz_generate",
    )

    parsed_options: list[object] | None = None
    try:
        parsed_options = _parse_json_list(response["content"])
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("[AI] generate_quiz_topic_options parse failure: %s", exc)

    if parsed_options is None:
        return {
            "options": [],
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_parse_error": True,
        }

    options: list[dict[str, object]] = []
    for item in parsed_options:
        if not isinstance(item, dict):
            continue
        text_pt = _normalize_optional_text(item.get("text_pt"))
        text_en = _normalize_optional_text(item.get("text_en"))
        mapped_position = item.get("mapped_position")
        raw_stance = item.get("stance")
        stance = (
            raw_stance.strip().lower() if isinstance(raw_stance, str) else "neutral"
        )
        if stance not in POSITION_STANCE_TO_WEIGHT:
            stance = "neutral"
        raw_weight = item.get("weight")
        if isinstance(raw_weight, int):
            weight = raw_weight
        else:
            weight = POSITION_STANCE_TO_WEIGHT[stance]
        if weight not in {-3, -2, 0, 2, 3}:
            weight = POSITION_STANCE_TO_WEIGHT[stance]
        if not text_pt or not text_en:
            continue
        options.append(
            {
                "text_pt": text_pt,
                "text_en": text_en,
                "mapped_position": mapped_position,
                "stance": stance,
                "weight": weight,
            }
        )

    return {
        "options": options[:6],
        "_ai_provider": response["provider"],
        "_ai_model": response["model"],
        "_parse_error": False,
    }


def validate_quiz_option_quality(
    topic_id: str,
    text_pt: str,
    text_en: str,
    weight: int,
) -> dict[str, object]:
    """Validate generated quiz option quality through structured AI checks."""
    system = (
        "Você valida opções de quiz político. "
        "Responda apenas com JSON válido contendo passes_all, failures e details."
    )
    user = f"""Topic: {topic_id}
Option pt-BR: "{text_pt}"
Option en-US: "{text_en}"
Weight: {weight}

Checklist:
1. Sem nomes de candidatos/partidos
2. Sem detalhes biográficos de cargo
3. Não é descrição de evento jornalístico
4. É posição ideológica em primeira pessoa
5. Português com diacríticos adequados
6. Tamanho de 15 a 80 palavras em pt-BR
7. Tradução en-US é consistente com pt-BR
8. Direção do peso é coerente com o texto

Return JSON:
{{
  "passes_all": true|false,
  "failures": ["1", "4"],
  "details": "explicacao curta"
}}"""
    response = _call_with_fallback_for_task(
        system=system,
        user=user,
        max_tokens=250,
        task="quiz_validate",
    )
    try:
        parsed = _parse_json_dict(response["content"])
        passes_all = bool(parsed.get("passes_all"))
        failures = _to_clean_string_list(parsed.get("failures"))
        details = _normalize_optional_text(parsed.get("details")) or ""
        return {
            "passes_all": passes_all,
            "failures": failures,
            "details": details,
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
        }
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("[AI] validate_quiz_option_quality parse failure: %s", exc)
        return {
            "passes_all": False,
            "failures": ["parse_error"],
            "details": "Validator response could not be parsed.",
            "_ai_provider": response["provider"],
            "_ai_model": response["model"],
            "_parse_error": True,
        }


__all__ = [
    "NVIDIA_MODELS",
    "USAGE_FILE",
    "build_article_id",
    "call_with_fallback",
    "summarize_article",
    "extract_candidate_position",
    "extract_candidate_topic_position",
    "generate_quiz_topic_options",
    "validate_quiz_option_quality",
]
