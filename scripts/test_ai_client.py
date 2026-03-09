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


def test_fallback_first_provider_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    chain = [
        _provider("first", "FIRST_KEY", "https://first.example/v1", "model-1"),
        _provider("second", "SECOND_KEY", "https://second.example/v1", "model-2"),
    ]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("FIRST_KEY", "first-key")
    monkeypatch.setenv("SECOND_KEY", "second-key")

    called: list[str] = []

    def fake_request(provider: dict[str, object], api_key: str, system: str, user: str, max_tokens: int) -> str:
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
    chain = [_provider("nvidia", "NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1", "nvidia-model")]
    monkeypatch.setattr(ai_client, "_provider_chain_for_task", lambda _task: chain)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setattr(ai_client, "_request_completion", lambda *_args, **_kwargs: "ok")

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
            "model": "moonshotai/kimi-k2.5",
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


def test_summarize_article_parse_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_client,
        "_call_with_fallback_for_task",
        lambda **_kwargs: {
            "content": "not-json",
            "provider": "nvidia",
            "model": "moonshotai/kimi-k2.5",
            "paid": False,
        },
    )

    result = ai_client.summarize_article("Titulo", "Conteudo", language="en-US")

    assert result["_parse_error"] is True
    assert result["summaries"]["pt-BR"] == "Titulo"
    assert result["summaries"]["en-US"] == "Titulo"
    assert result["_language"] == "en-US"


def test_extract_position_low_confidence_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
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
