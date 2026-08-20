import json

import pytest

from scripts import ai_client


def _provider(
    name: str,
    key_env: str,
    base_url: str,
    model: str,
    paid: bool = False,
    daily_max: int | None = None,
) -> dict[str, object]:
    provider: dict[str, object] = {
        "name": name,
        "key_env": key_env,
        "base_url": base_url,
        "model": model,
        "paid": paid,
    }
    if daily_max is not None:
        provider["daily_max"] = daily_max
    return provider


@pytest.fixture(autouse=True)
def isolate_usage_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_client, "USAGE_FILE", tmp_path / "ai_usage.json")
    ai_client._run_selected_providers.clear()
    ai_client._run_preflight_signatures.clear()
    ai_client._provider_failure_counts.clear()


def test_provider_chain_is_poolside_first_with_minimax_fallbacks() -> None:
    chain = ai_client._provider_chain_for_task("multilingual")
    provider_models = [(str(item["name"]), str(item["model"])) for item in chain]
    assert provider_models == [
        ("poolside", "poolside/laguna-s-2.1"),
        ("ollama", "minimax-m3:cloud"),
        ("nvidia", "minimaxai/minimax-m3"),
        ("openrouter", "openrouter/free"),
    ]


def test_ollama_structured_requests_disable_thinking() -> None:
    provider = _provider(
        "ollama", "OLLAMA_API_KEY", "https://ollama.example/v1", "minimax-m3:cloud"
    )
    kwargs = ai_client._chat_completion_kwargs(
        provider, "system", "user", 100
    )
    assert kwargs["extra_body"] == {"think": False}


def test_streaming_probe_measures_ttft_and_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(
        "nvidia", "NVIDIA_API_KEY", "https://nvidia.example/v1", "model-1"
    )
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    completion_calls: list[dict[str, object]] = []

    class _Delta:
        content = "{\"ok\":"
        reasoning_content = None

    class _Choice:
        delta = _Delta()

    class _Chunk:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs: object) -> list[_Chunk]:
            completion_calls.append(kwargs)
            return [_Chunk()]

    class _Client:
        chat = type("_Chat", (), {"completions": _Completions()})()

    monkeypatch.setattr(ai_client.openai, "OpenAI", lambda **_kwargs: _Client())

    result = ai_client._probe_provider(provider)

    assert result["provider"] == "nvidia"
    assert result["model"] == "model-1"
    assert float(result["ttft_ms"]) >= 0
    assert float(result["latency_ms"]) >= float(result["ttft_ms"])
    assert completion_calls[0]["stream"] is True


def test_preflight_selects_fastest_candidate_and_reuses_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chain = [
        _provider("first", "FIRST_KEY", "https://first.example/v1", "slow"),
        _provider("second", "SECOND_KEY", "https://second.example/v1", "fast"),
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("FIRST_KEY", "first-key")
    monkeypatch.setenv("SECOND_KEY", "second-key")
    monkeypatch.setenv("AI_PREFLIGHT_ENABLED", "1")
    monkeypatch.setattr(ai_client, "_load_usage", lambda: {})

    def fake_probe(provider: dict[str, object]) -> dict[str, float | str]:
        if provider["model"] == "slow":
            return {"provider": "first", "model": "slow", "ttft_ms": 100, "latency_ms": 300}
        return {"provider": "second", "model": "fast", "ttft_ms": 20, "latency_ms": 30}

    monkeypatch.setattr(ai_client, "_probe_provider", fake_probe)

    selections = ai_client.preflight_for_run(("test_task",))

    assert selections["test_task"]["model"] == "fast"
    assert ai_client._ordered_provider_chain_for_task("test_task")[0]["model"] == "fast"


def test_request_completion_openrouter_uses_optional_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(
        "openrouter",
        "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1",
        "openrouter/free",
    )
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://example.org/app")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "eleicoes-2026-monitor")

    init_calls: list[dict[str, object]] = []
    completion_calls: list[dict[str, object]] = []

    class _Message:
        content = '{"ok":true}'

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs: object) -> _Response:
            completion_calls.append(dict(kwargs))
            return _Response()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    def fake_openai_client(**kwargs: object) -> _Client:
        init_calls.append(dict(kwargs))
        return _Client()

    monkeypatch.setattr(ai_client.openai, "OpenAI", fake_openai_client)

    result = ai_client._request_completion(
        provider=provider,
        api_key="openrouter-key",
        system="system",
        user="user",
        max_tokens=123,
    )

    assert result == '{"ok":true}'
    assert init_calls[0]["default_headers"] == {
        "HTTP-Referer": "https://example.org/app",
        "X-Title": "eleicoes-2026-monitor",
    }
    assert completion_calls[0]["model"] == "openrouter/free"
    assert completion_calls[0]["max_tokens"] == 123
    assert completion_calls[0]["extra_body"] == {
        "reasoning": {"effort": "none"}
    }


def test_extract_content_from_object_content_parts() -> None:
    class _ContentPart:
        def __init__(self, part_type: str, text: str) -> None:
            self.type = part_type
            self.text = text

    class _Message:
        content = [_ContentPart("thinking", "ignore"), _ContentPart("text", "ok")]

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    assert ai_client._extract_content_from_response(_Response()) == "ok"


def test_extract_content_from_reasoning_extra_field() -> None:
    class _Message:
        content = None
        model_extra = {"reasoning": 'I will return {"ok":true}'}

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    assert ai_client._extract_content_from_response(_Response()) == '{"ok":true}'


def test_parse_json_list_from_prose_with_fenced_json() -> None:
    text = (
        "Here is the JSON requested:\n"
        "```json\n"
        '[{"text_pt":"abc","text_en":"def"}]\n'
        "```"
    )
    parsed = ai_client._parse_json_list(text)
    assert isinstance(parsed, list)
    assert parsed[0]["text_pt"] == "abc"


def test_generate_quiz_topic_options_recovers_truncated_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truncated = (
        '[{"text_pt":"Defendo que o governo fortaleça a fiscalização ambiental com metas anuais.",'
        '"text_en":"I believe the government should strengthen environmental enforcement with annual targets.",'
        '"mapped_position":1,"stance":"favor","weight":2},'
        '{"text_pt":"Acredito que'
    )
    monkeypatch.setattr(
        ai_client,
        "_call_with_fallback_for_task",
        lambda **_kwargs: {
            "content": truncated,
            "provider": "nvidia",
            "model": "z-ai/glm-5.2",
            "paid": False,
        },
    )
    known_positions = [
        {"candidate_slug": "lula", "stance": "favor", "summary_pt": "", "key_actions": []}
    ]

    result = ai_client.generate_quiz_topic_options(
        topic_id="meio_ambiente",
        topic_label_pt="Meio Ambiente",
        topic_label_en="Environment",
        question_pt="Pergunta",
        question_en="Question",
        known_positions=known_positions,
    )

    assert result["_parse_error"] is False
    assert len(result["options"]) == 1
    assert result["options"][0]["mapped_position"] == 1


def test_fallback_first_provider_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = [
        _provider("first", "FIRST_KEY", "https://first.example/v1", "model-1"),
        _provider("second", "SECOND_KEY", "https://second.example/v1", "model-2"),
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("FIRST_KEY", "first-key")
    monkeypatch.setenv("SECOND_KEY", "second-key")

    called: list[str] = []

    def fake_request(
        provider: dict[str, object],
        api_key: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        assert api_key
        assert system == "system"
        assert user == "user"
        assert max_tokens == 321
        called.append(str(provider["name"]))
        return "ok"

    monkeypatch.setattr(ai_client, "_request_completion", fake_request)
    result = ai_client.call_with_fallback("system", "user", max_tokens=321)

    assert result["provider"] == "first"
    assert result["model"] == "model-1"
    assert result["content"] == "ok"
    assert called == ["first"]


def test_fallback_skips_failed_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = [
        _provider("first", "FIRST_KEY", "https://first.example/v1", "model-1"),
        _provider("second", "SECOND_KEY", "https://second.example/v1", "model-2"),
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("FIRST_KEY", "first-key")
    monkeypatch.setenv("SECOND_KEY", "second-key")

    called: list[str] = []

    def fake_request(
        provider: dict[str, object],
        api_key: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        assert api_key
        assert system == "system"
        assert user == "user"
        assert max_tokens == 500
        called.append(str(provider["name"]))
        if provider["name"] == "first":
            raise RuntimeError("provider down")
        return "second-response"

    monkeypatch.setattr(ai_client, "_request_completion", fake_request)
    result = ai_client.call_with_fallback("system", "user")

    assert result["provider"] == "second"
    assert result["content"] == "second-response"
    assert called == ["first", "second"]


def test_fallback_all_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = [
        _provider("first", "FIRST_KEY", "https://first.example/v1", "model-1"),
        _provider("second", "SECOND_KEY", "https://second.example/v1", "model-2"),
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("FIRST_KEY", "first-key")
    monkeypatch.setenv("SECOND_KEY", "second-key")

    def always_fail(
        provider: dict[str, object],
        _api_key: str,
        _system: str,
        _user: str,
        _max_tokens: int,
    ) -> str:
        raise RuntimeError(f"{provider['name']} failed")

    monkeypatch.setattr(ai_client, "_request_completion", always_fail)
    with pytest.raises(RuntimeError, match="All AI providers failed"):
        ai_client.call_with_fallback("system", "user")


def test_openrouter_daily_limit_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = [
        _provider(
            "openrouter",
            "OPENROUTER_API_KEY",
            "https://openrouter.ai/api/v1",
            "openrouter-model",
            daily_max=200,
        ),
        _provider("second", "SECOND_KEY", "https://second.example/v1", "model-2"),
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("SECOND_KEY", "second-key")

    ai_client._save_usage({f"openrouter_{ai_client._today_key()}": 200})

    called: list[str] = []

    def fake_request(
        provider: dict[str, object],
        api_key: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        assert api_key
        assert system == "system"
        assert user == "user"
        assert max_tokens == 500
        called.append(str(provider["name"]))
        return "ok"

    monkeypatch.setattr(ai_client, "_request_completion", fake_request)
    result = ai_client.call_with_fallback("system", "user")

    assert result["provider"] == "second"
    assert called == ["second"]


def test_usage_tracking_increments(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = [
        _provider(
            "nvidia",
            "NVIDIA_API_KEY",
            "https://integrate.api.nvidia.com/v1",
            "nvidia-model",
        )
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setattr(
        ai_client, "_request_completion", lambda *_args, **_kwargs: "ok"
    )

    ai_client.call_with_fallback("system", "user")
    ai_client.call_with_fallback("system", "user")

    usage = json.loads(ai_client.USAGE_FILE.read_text(encoding="utf-8"))
    usage_key = f"nvidia_{ai_client._today_key()}"
    assert usage[usage_key] == 2


def test_summarize_article_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {
            "summaries": {"pt-BR": "Resumo curto.", "en-US": "Short summary."},
            "candidates_mentioned": ["Lula"],
            "topics": ["economia"],
            "sentiment_per_candidate": {"Lula": "positivo"},
        }
    )
    monkeypatch.setattr(
        ai_client,
        "_call_with_fallback_for_task",
        lambda **_kwargs: {
            "content": payload,
            "provider": "nvidia",
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "paid": False,
        },
    )

    result = ai_client.summarize_article("Titulo", "Conteudo", language="pt-BR")

    assert result["summary"] == "Resumo curto."
    assert result["summaries"] == {"pt-BR": "Resumo curto.", "en-US": "Short summary."}
    assert result["candidates_mentioned"] == ["Lula"]
    assert result["topics"] == ["economia"]
    assert result["sentiment_per_candidate"] == {"Lula": "positivo"}
    assert result["_ai_provider"] == "nvidia"
    assert result["_language"] == "pt-BR"


def test_summarize_article_parse_error_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_client,
        "_call_with_fallback_for_task",
        lambda **_kwargs: {
            "content": "not-json",
            "provider": "nvidia",
            "model": "nvidia/nemotron-3-ultra-550b-a55b",
            "paid": False,
        },
    )

    result = ai_client.summarize_article("Titulo", "Conteudo", language="en-US")

    assert result["_parse_error"] is True
    assert result["summaries"]["pt-BR"] == "Titulo"
    assert result["summaries"]["en-US"] == "Titulo"
    assert result["_language"] == "en-US"


def test_extract_position_low_confidence_filtered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        {
            "position_pt": "Defende a medida.",
            "position_en": "Supports the measure.",
            "stance": "favor",
            "confidence": "low",
            "best_source_snippet_index": 1,
        }
    )
    monkeypatch.setattr(
        ai_client,
        "_call_with_fallback_for_task",
        lambda **_kwargs: {
            "content": payload,
            "provider": "nvidia",
            "model": "qwen/qwen3-235b-a22b-thinking-2507",
            "paid": False,
        },
    )

    result = ai_client.extract_candidate_position(
        candidate="Lula",
        topic_id="economia",
        snippets=["Trecho 1", "Trecho 2"],
    )

    assert result["confidence"] == "low"
    assert result["position_pt"] is None
    assert result["position_en"] is None
    assert result["best_source_snippet_index"] == 1


def test_extract_candidate_topic_position_retries_on_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        {
            "content": "not-json",
            "provider": "nvidia",
            "model": "z-ai/glm-5.2",
            "paid": False,
        },
        {
            "content": json.dumps(
                {
                    "position_type": "confirmed",
                    "stance": "favor",
                    "summary_pt": "Defende a proposta em público.",
                    "summary_en": "Supports the proposal in public.",
                    "key_actions": ["Declarou apoio em entrevista."],
                    "source_indices": [1],
                    "confidence_reasoning": "Há evidência textual direta.",
                }
            ),
            "provider": "nvidia",
            "model": "z-ai/glm-5.2",
            "paid": False,
        },
    ]
    calls: list[str] = []

    def fake_call(**kwargs: object) -> dict[str, object]:
        user = kwargs.get("user")
        calls.append(str(user))
        return responses[len(calls) - 1]

    monkeypatch.setattr(ai_client, "_call_with_fallback_for_task", fake_call)

    result = ai_client.extract_candidate_topic_position(
        candidate="Lula",
        topic_id="economia",
        topic_label_pt="Economia",
        snippets=["Trecho relevante"],
    )

    assert len(calls) == 2
    assert "IMPORTANTE: responda somente" in calls[1]
    assert result["position_type"] == "confirmed"
    assert result["stance"] == "favor"
    assert result["summary_pt"] == "Defende a proposta em público."
    assert result["source_indices"] == [1]


def test_extract_candidate_topic_position_recovers_partial_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truncated = '{"position_type":"inferred","stance":"against","summary_pt":"Texto'
    calls = 0

    def fake_call(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "content": truncated,
            "provider": "nvidia",
            "model": "z-ai/glm-5.2",
            "paid": False,
        }

    monkeypatch.setattr(ai_client, "_call_with_fallback_for_task", fake_call)

    result = ai_client.extract_candidate_topic_position(
        candidate="Lula",
        topic_id="economia",
        topic_label_pt="Economia",
        snippets=["Trecho relevante"],
    )

    assert calls == 2
    assert result["position_type"] == "inferred"
    assert result["stance"] == "against"
    assert result["_partial_parse"] is True
