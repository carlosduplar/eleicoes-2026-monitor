"""Benchmark script to test all AI providers and models locally.

Run with: python scripts/benchmark_ai.py
Requires API keys: NVIDIA_API_KEY, OLLAMA_API_KEY, OPENROUTER_API_KEY
Optional: --iterations or -n (default 3, max 10)
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

SAMPLE_TITLE = "Lula e BNDES apresentam plano de investimentos para infraestrutura"
SAMPLE_CONTENT = """
O presidente Luiz Inacio Lula da Silva e o presidente do BNDES, Aloizio Mercadante,
anunciaram nesta segunda-feira um plano de investimentos de R$ 200 bilhoes para
infraestrutura no Brasil. O plano inclui estradas, ferrovias, portos e aeroportos.
O ministro da Fazenda, Fernando Haddad, participou da ceremonia e destacou que os
investimentos vao gerar 2 milhoes de empregos. O plano faz parte das metas do
governo para as eleicoes de 2026, quando Lula podera buscar a reelecao.
O oposicionista Jair Bolsonaro criticou o plano, chamando-o de propaganda
eleitoral antecipada. Para Bolsonaro, o governo deveria focar na reducao de
impostos em vez de gastar com infraestrutura.
"""

SAMPLE_SNIPPETS = [
    "O presidente Lula anunciou um plano de R$ 200 bilhoes para infraestrutura.",
    "O ministro Haddad disse que o plano gerara 2 milhoes de empregos.",
    "Bolsonaro criticou o plano e chamou de propaganda eleitoral.",
    "O plano inclui estradas, ferrovias, portos e aeroportos.",
]


@dataclass
class TestResult:
    provider: str
    model: str
    task: str
    success: bool
    error: str | None = None
    duration_seconds: float = 0.0
    raw_response: str | None = None
    parsed_response: dict[str, Any] | None = None
    response_preview: str | None = None


@dataclass
class BenchmarkSummary:
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    results: list[TestResult] = field(default_factory=list)
    by_provider: dict[str, dict[str, int]] = field(default_factory=dict)
    by_task: dict[str, dict[str, int]] = field(default_factory=dict)
    timings: dict[str, list[float]] = field(default_factory=dict)


def load_ai_client():
    """Import ai_client module."""
    sys.path.insert(0, str(Path(__file__).parent))
    from . import ai_client

    return (
        ai_client._provider_chain_for_task,
        ai_client.summarize_article,
        ai_client.extract_candidate_position,
        ai_client._request_completion,
    )


def get_raw_response(
    provider: dict, system: str, user: str, max_tokens: int = 500
) -> tuple[str | None, Any]:
    """Make direct API call and return raw response for inspection."""
    import openai
    import json
    import urllib.request

    api_key = os.environ.get(provider.get("key_env", ""), "").strip()
    if not api_key:
        return None, {"error": f"Missing API key for {provider.get('key_env')}"}

    if provider.get("name") == "vertex":
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{provider['model']}:generateContent?key={api_key}"
        data = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": {"maxOutputTokens": 8192}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                try:
                    content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    content = ""
                
                usage_metadata = resp_data.get("usageMetadata", {})
                usage_dict = {
                    "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                    "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                    "total_tokens": usage_metadata.get("totalTokenCount", 0),
                }
                
                full_raw = json.dumps(
                    {
                        "content": content,
                        "reasoning_content": "",
                        "model": provider["model"],
                        "usage": usage_dict,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                return full_raw, None
        except Exception as e:
            return None, {"error": str(e), "type": type(e).__name__}

    client_kwargs = {
        "api_key": api_key,
        "base_url": provider.get("base_url", "")
    }
    
    default_headers = {}
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
    kwargs = {
        "model": provider["model"],
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    if provider.get("name") == "nvidia":
        from .ai_client import _THINKING_DISABLE_EXTRA_BODY

        disable_body = _THINKING_DISABLE_EXTRA_BODY.get(provider.get("model", ""))
        if disable_body:
            kwargs["extra_body"] = disable_body
    elif provider.get("name") == "mimo":
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    try:
        response = client.chat.completions.create(**kwargs)

        raw_content = ""
        reasoning_content = ""

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                msg = choice.message
                if hasattr(msg, "content") and msg.content:
                    raw_content = msg.content
                if hasattr(msg, "reasoning_content") and msg.reasoning_content:
                    reasoning_content = msg.reasoning_content

        usage_dict = {}
        if hasattr(response, "usage") and response.usage:
            usage_obj = response.usage
            usage_dict = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                "total_tokens": getattr(usage_obj, "total_tokens", 0),
            }
            prompt_details = getattr(usage_obj, "prompt_tokens_details", None)
            if prompt_details:
                usage_dict["prompt_tokens_details"] = {
                    "cached_tokens": getattr(prompt_details, "cached_tokens", 0),
                    "audio_tokens": getattr(prompt_details, "audio_tokens", 0),
                }
            completion_details = getattr(usage_obj, "completion_tokens_details", None)
            if completion_details:
                usage_dict["completion_tokens_details"] = {
                    "reasoning_tokens": getattr(
                        completion_details, "reasoning_tokens", 0
                    ),
                    "audio_tokens": getattr(completion_details, "audio_tokens", 0),
                }

        full_raw = json.dumps(
            {
                "content": raw_content,
                "reasoning_content": reasoning_content,
                "model": response.model
                if hasattr(response, "model")
                else provider["model"],
                "usage": usage_dict,
            },
            ensure_ascii=False,
            indent=2,
        )

        return full_raw, None
    except Exception as e:
        return None, {"error": str(e), "type": type(e).__name__}


def test_summarization_task(provider: dict) -> TestResult:
    """Test summarization task."""
    system = (
        "Voce e um analista politico especializado nas eleicoes brasileiras de 2026. "
        "Responda APENAS com JSON valido, sem markdown. "
        "Sempre inclua resumos bilingues com chaves 'pt-BR' e 'en-US'."
    )
    user = f"""Titulo: {SAMPLE_TITLE}
Conteudo: {SAMPLE_CONTENT[:1500]}
Prefira redacao concisa em portugues brasileiro.

Retorne JSON:
{{
  "summaries": {{
    "pt-BR": "resumo em 2-3 frases",
    "en-US": "summary in 2-3 sentences"
  }},
  "candidates_mentioned": ["nomes exatos"],
  "topics": ["economia", "seguranca", "saude", "educacao"],
  "sentiment_per_candidate": {{"Nome": "positivo|neutro|negativo"}}
}}"""

    start = time.perf_counter()
    raw_response, error = get_raw_response(provider, system, user, max_tokens=450)
    duration = time.perf_counter() - start

    if error:
        return TestResult(
            provider=provider["name"],
            model=provider["model"],
            task="summarization",
            success=False,
            error=str(error),
            duration_seconds=round(duration, 2),
        )

    parsed = None
    preview = None
    try:
        if raw_response:
            parsed = json.loads(raw_response)
            content = parsed.get("content", "")
            preview = (
                content[:300]
                if content
                else (parsed.get("reasoning_content", "")[:300])
            )
    except:
        pass

    success = raw_response is not None and not (error)

    return TestResult(
        provider=provider["name"],
        model=provider["model"],
        task="summarization",
        success=success,
        error=str(error) if error else None,
        duration_seconds=round(duration, 2),
        raw_response=raw_response,
        parsed_response=parsed,
        response_preview=preview,
    )


def test_extraction_task(provider: dict) -> TestResult:
    """Test extraction (candidate position) task."""
    system = (
        "Voce e um analista politico. "
        "Extraia apenas posicoes verificaveis com base em evidencias textuais. "
        "Responda APENAS com JSON valido."
    )
    rendered_snippets = "\n".join(
        f"[{i + 1}] {snippet}" for i, snippet in enumerate(SAMPLE_SNIPPETS)
    )
    user = f"""Candidato: Lula
Topico: economia
Trechos:
{rendered_snippets}

Retorne JSON:
{{
  "position_pt": "posicao em portugues, ou null",
  "position_en": "position in English, or null",
  "stance": "favor|against|neutral|unclear",
  "confidence": "high|medium|low",
  "best_source_snippet_index": 1
}}"""

    start = time.perf_counter()
    raw_response, error = get_raw_response(provider, system, user, max_tokens=350)
    duration = time.perf_counter() - start

    if error:
        return TestResult(
            provider=provider["name"],
            model=provider["model"],
            task="extraction",
            success=False,
            error=str(error),
            duration_seconds=round(duration, 2),
        )

    parsed = None
    preview = None
    try:
        if raw_response:
            parsed = json.loads(raw_response)
            content = parsed.get("content", "")
            preview = (
                content[:300]
                if content
                else (parsed.get("reasoning_content", "")[:300])
            )
    except:
        pass

    return TestResult(
        provider=provider["name"],
        model=provider["model"],
        task="extraction",
        success=raw_response is not None,
        error=str(error) if error else None,
        duration_seconds=round(duration, 2),
        raw_response=raw_response,
        parsed_response=parsed,
        response_preview=preview,
    )


def test_curation_task(provider: dict) -> TestResult:
    """Test curation task (uses same provider chain as summarization)."""
    system = "Voce e um curador de noticias. Responda APENAS com JSON valido."
    user = """Categorize esta materia:
Titulo: Lula anuncia plano de infraestrutura
Conteudo: O presidente anunciou investimentos bilionarios.

Retorne JSON:
{
  "category": "politica|economia|sociedade|outro",
  "relevance": 1-10,
  "summary": "uma frase"
}"""

    start = time.perf_counter()
    raw_response, error = get_raw_response(provider, system, user, max_tokens=200)
    duration = time.perf_counter() - start

    parsed = None
    preview = None
    try:
        if raw_response:
            parsed = json.loads(raw_response)
            content = parsed.get("content", "")
            preview = (
                content[:300]
                if content
                else (parsed.get("reasoning_content", "")[:300])
            )
    except:
        pass

    return TestResult(
        provider=provider["name"],
        model=provider["model"],
        task="curation",
        success=raw_response is not None,
        error=str(error) if error else None,
        duration_seconds=round(duration, 2),
        raw_response=raw_response,
        parsed_response=parsed,
        response_preview=preview,
    )


def run_benchmark(iterations: int = 3) -> BenchmarkSummary:
    """Run all benchmarks."""
    _provider_chain, _, _, _ = load_ai_client()

    # Additional models to test (beyond what's in ai_client.py)
    extra_models = [
    ]

    tasks_config = [
        ("summarization", test_summarization_task),
        ("extraction", test_extraction_task),
        ("curation", test_curation_task),
    ]

    summary = BenchmarkSummary()

    print("=" * 70)
    print("AI PROVIDER BENCHMARK")
    print("=" * 70)
    print(f"\nIterations per test: {iterations}")
    print("\nRequired env vars: NVIDIA_API_KEY, OLLAMA_API_KEY, OPENROUTER_API_KEY")
    print()

    all_providers = _provider_chain("summarization")
    unique_providers = {}
    for p in all_providers:
        key = (p["name"], p["model"])
        if key not in unique_providers:
            unique_providers[key] = p

    # Add extra models to test
    for p in extra_models:
        key = (p["name"], p["model"])
        if key not in unique_providers:
            unique_providers[key] = p

    print(
        f"Found {len(unique_providers)} unique provider/model combinations (including extras)\n"
    )

    for task_name, test_func in tasks_config:
        print(f"\n### Task: {task_name.upper()} ###")
        print("-" * 50)

        task_providers = _provider_chain(
            task_name if task_name != "extraction" else "quiz_extract"
        )

        # Add extra models to test for this task
        task_providers = list(task_providers) + extra_models

        for provider in task_providers:
            name = provider["name"]
            model = provider["model"]
            key_env = provider.get("key_env", "")
            api_key = os.environ.get(key_env, "").strip()

            if not api_key:
                print(f"  [SKIP] {name}/{model[:35]} - Missing {key_env}")
                continue

            model_key = f"{name}/{model}"
            if iterations == 1 and any(
                r.model == model and r.task == task_name for r in summary.results
            ):
                print(f"  [SKIP] {name}/{model[:35]} - Already tested")
                continue

            print(f"\n  Testing: {name}/{model[:35]}...", end=" ", flush=True)

            for iteration in range(iterations):
                if iterations > 1:
                    print(
                        f"\n    Iteration {iteration + 1}/{iterations}...",
                        end=" ",
                        flush=True,
                    )

                try:
                    result = test_func(provider)
                except Exception as e:
                    result = TestResult(
                        provider=name,
                        model=model,
                        task=task_name,
                        success=False,
                        error=f"Exception: {type(e).__name__}: {str(e)[:100]}",
                        duration_seconds=0,
                    )

                summary.results.append(result)
                summary.total_tests += 1

                if result.success:
                    summary.passed += 1
                    print(f"PASS ({result.duration_seconds}s)")

                    if name not in summary.by_provider:
                        summary.by_provider[name] = {"pass": 0, "fail": 0}
                    summary.by_provider[name]["pass"] += 1

                    if task_name not in summary.by_task:
                        summary.by_task[task_name] = {"pass": 0, "fail": 0}
                    summary.by_task[task_name]["pass"] += 1

                    timing_key = f"{name}/{model.split('/')[-1][:15]}"
                    if timing_key not in summary.timings:
                        summary.timings[timing_key] = []
                    summary.timings[timing_key].append(result.duration_seconds)
                else:
                    summary.failed += 1
                    err_msg = result.error or "Unknown"
                    print(f"FAIL - {err_msg[:60]}")

                    if name not in summary.by_provider:
                        summary.by_provider[name] = {"pass": 0, "fail": 0}
                    summary.by_provider[name]["fail"] += 1

                    if task_name not in summary.by_task:
                        summary.by_task[task_name] = {"pass": 0, "fail": 0}
                    summary.by_task[task_name]["fail"] += 1

    return summary


def print_summary(summary: BenchmarkSummary):
    """Print benchmark summary."""
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total tests: {summary.total_tests}")
    print(f"Passed: {summary.passed}")
    print(f"Failed: {summary.failed}")
    if summary.total_tests > 0:
        print(f"Pass rate: {round(100 * summary.passed / summary.total_tests, 1)}%")

    print("\n--- By Provider ---")
    for provider, stats in sorted(summary.by_provider.items()):
        total = stats["pass"] + stats["fail"]
        rate = round(100 * stats["pass"] / max(1, total), 1)
        print(f"  {provider}: {stats['pass']}/{total} ({rate}%)")

    print("\n--- By Task ---")
    for task, stats in sorted(summary.by_task.items()):
        total = stats["pass"] + stats["fail"]
        rate = round(100 * stats["pass"] / max(1, total), 1)
        print(f"  {task}: {stats['pass']}/{total} ({rate}%)")

    print("\n--- Average Timings (successful runs) ---")
    for key, times in sorted(
        summary.timings.items(), key=lambda x: sum(x[1]) / len(x[1])
    ):
        avg = sum(times) / len(times)
        min_t = min(times)
        max_t = max(times)
        print(
            f"  {key}: avg={avg:.2f}s min={min_t:.2f}s max={max_t:.2f}s (n={len(times)})"
        )

    print("\n--- Output Quality Comparison (summarization) ---")
    summarization_results = [
        r for r in summary.results if r.task == "summarization" and r.success
    ]
    for r in summarization_results:
        preview = r.response_preview or ""
        if preview:
            preview = preview[:120].replace("\n", " ")
        print(f"  {r.provider}/{r.model.split('/')[-1][:25]}:")
        print(f"    {preview}...")


def export_results(summary: BenchmarkSummary, filepath: Path):
    """Export results to JSON."""
    results_data = []
    for r in summary.results:
        results_data.append(
            {
                "provider": r.provider,
                "model": r.model,
                "task": r.task,
                "success": r.success,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "response_preview": r.response_preview,
                "raw_response": r.raw_response,
                "parsed_response": r.parsed_response,
            }
        )

    data = {
        "summary": {
            "total": summary.total_tests,
            "passed": summary.passed,
            "failed": summary.failed,
            "pass_rate": round(100 * summary.passed / max(1, summary.total_tests), 1),
        },
        "by_provider": summary.by_provider,
        "by_task": summary.by_task,
        "timings": {
            k: {
                "avg": sum(v) / len(v),
                "min": min(v),
                "max": max(v),
                "runs": len(v),
                "times": v,
            }
            for k, v in summary.timings.items()
        },
        "results": results_data,
    }

    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nResults exported to: {filepath}")


def export_detailed_failures(summary: BenchmarkSummary, filepath: Path):
    """Export detailed failure analysis."""
    failures = [r for r in summary.results if not r.success]

    if not failures:
        print("\nNo failures to analyze.")
        return

    analysis = {
        "total_failures": len(failures),
        "by_error_type": {},
        "by_provider": {},
        "recommendations": [],
    }

    for r in failures:
        err_type = r.error or "Unknown"
        analysis["by_error_type"][err_type] = (
            analysis["by_error_type"].get(err_type, 0) + 1
        )

        provider_key = f"{r.provider}/{r.model}"
        if provider_key not in analysis["by_provider"]:
            analysis["by_provider"][provider_key] = []
        analysis["by_provider"][provider_key].append(
            {
                "task": r.task,
                "error": err_type,
            }
        )

    for provider, errors in analysis["by_provider"].items():
        error_types = set(e["error"] for e in errors)
        for et in error_types:
            count = sum(1 for e in errors if e["error"] == et)
            if "missing" in et.lower() or "not found" in et.lower():
                analysis["recommendations"].append(
                    f"{provider}: Check API key and model availability"
                )
            elif "json" in et.lower() or "parse" in et.lower():
                analysis["recommendations"].append(
                    f"{provider}: Model returns malformed JSON - may need response parsing adjustment"
                )
            elif "timeout" in et.lower():
                analysis["recommendations"].append(
                    f"{provider}: Request timed out - may need higher timeout or smaller payload"
                )

    filepath.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Failure analysis exported to: {filepath}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI Provider Benchmark")
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations per test (default: 3, max: 10)",
    )
    args = parser.parse_args()

    iterations = min(max(1, args.iterations), 10)

    summary = run_benchmark(iterations=iterations)
    print_summary(summary)

    output_path = Path(__file__).parent / "benchmark_results.json"
    export_results(summary, output_path)

    failure_path = Path(__file__).parent / "benchmark_failures.json"
    export_detailed_failures(summary, failure_path)

    if summary.failed > 0:
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        print("Review benchmark_failures.json for detailed error analysis.")
        print("Common fixes:")
        print("  - Missing API keys: Set environment variables")
        print("  - Model not found: Check model name and provider docs")
        print("  - JSON parse errors: Model may return markdown-wrapped JSON")
        print("  - Empty content: Model may use reasoning_content instead")
        return

    print("\nAll tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
