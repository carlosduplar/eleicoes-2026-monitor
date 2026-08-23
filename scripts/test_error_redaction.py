"""Redaction coverage across every pipeline-error writer (R10 / M5a).

Each writer must scrub key-shaped substrings before persisting messages.
Modules with heavy optional dependencies are skipped when those deps are
absent locally; CI installs them and runs the full matrix.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECRET = "api_key=abcdefghijklmnopqrst"
SAFE = "api_key=[REDACTED]"


def _errors(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["errors"]


def _assert_redacted(path: Path) -> None:
    entries = _errors(path)
    assert entries, "writer produced no error entry"
    assert SECRET not in entries[-1]["message"]
    assert SAFE in entries[-1]["message"]


def test_summarize_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    from scripts import summarize

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(summarize, "PIPELINE_ERRORS_FILE", target)
    summarize._append_pipeline_error(script="summarize.py", message=f"boom {SECRET}")
    _assert_redacted(target)


def test_analyze_sentiment_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    from scripts import analyze_sentiment

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(analyze_sentiment, "PIPELINE_ERRORS_FILE", target)
    analyze_sentiment._append_pipeline_error(message=f"boom {SECRET}", article_id=None, provider=None)
    _assert_redacted(target)


def test_curate_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    from scripts import curate

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(curate, "PIPELINE_ERRORS_FILE", target)
    curate._append_pipeline_error(message=f"boom {SECRET}")
    _assert_redacted(target)


def test_collect_markets_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    from scripts import collect_markets

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(collect_markets, "PIPELINE_ERRORS_FILE", target)
    collect_markets.append_pipeline_error(source_name="s", source_url="u", message=f"boom {SECRET}")
    _assert_redacted(target)


def test_collect_parties_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    from scripts import collect_parties

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(collect_parties, "PIPELINE_ERRORS_FILE", target)
    collect_parties._append_pipeline_error(party_name="p", party_url="u", message=f"boom {SECRET}")
    _assert_redacted(target)


def test_collect_social_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    import pytest

    pytest.importorskip("tweepy")
    from scripts import collect_social

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(collect_social, "PIPELINE_ERRORS_FILE", target)
    collect_social._append_pipeline_error(source="s", message=f"boom {SECRET}")
    _assert_redacted(target)


def test_collect_polls_writer_redacts(tmp_path: Path, monkeypatch: Any) -> None:
    import pytest

    pytest.importorskip("playwright")
    from scripts import collect_polls

    target = tmp_path / "pipeline_errors.json"
    monkeypatch.setattr(collect_polls, "PIPELINE_ERRORS_FILE", target)
    collect_polls.append_pipeline_error(institute="i", source_url="u", message=f"boom {SECRET}")
    _assert_redacted(target)
