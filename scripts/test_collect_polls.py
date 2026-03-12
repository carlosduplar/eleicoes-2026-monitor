import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from scripts import collect_polls


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_sources(path: Path, polls_sources: list[dict[str, Any]]) -> None:
    _write_json(path, {"rss": [], "parties": [], "polls": polls_sources})


def _read_polls(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        polls = payload.get("polls", [])
        if isinstance(polls, list):
            return polls
    raise AssertionError(f"Unexpected polls payload in {path}")


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    data_dir = tmp_path / "data"
    sources_file = data_dir / "sources.json"
    polls_file = data_dir / "polls.json"
    pipeline_errors_file = data_dir / "pipeline_errors.json"
    schema_file = tmp_path / "docs" / "schemas" / "polls.schema.json"
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    repo_schema = Path("docs/schemas/polls.schema.json")
    schema_file.write_text(repo_schema.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(collect_polls, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(collect_polls, "DATA_DIR", data_dir)
    monkeypatch.setattr(collect_polls, "SOURCES_FILE", sources_file)
    monkeypatch.setattr(collect_polls, "POLLS_FILE", polls_file)
    monkeypatch.setattr(collect_polls, "PIPELINE_ERRORS_FILE", pipeline_errors_file)

    return {
        "root": tmp_path,
        "data": data_dir,
        "sources": sources_file,
        "polls": polls_file,
        "pipeline_errors": pipeline_errors_file,
        "schema": schema_file,
    }


def test_poll_id_is_sha256_prefix() -> None:
    institute = "Datafolha"
    date = "2026-03-01"
    expected = hashlib.sha256(f"{institute}_{date}".encode()).hexdigest()[:16]
    assert collect_polls.build_poll_id(institute, date) == expected


def test_dedup_skips_existing_polls(isolated_workspace: dict[str, Path]) -> None:
    existing = [
        {
            "id": collect_polls.build_poll_id("Datafolha", "2026-03-01"),
            "institute": "Datafolha",
            "published_at": "2026-03-01T00:00:00Z",
            "collected_at": "2026-03-10T10:00:00Z",
            "type": "estimulada",
            "results": [{"candidate_slug": "lula", "candidate_name": "Lula", "percentage": 35.0}],
        }
    ]
    incoming = [
        {
            "id": collect_polls.build_poll_id("Datafolha", "2026-03-01"),
            "institute": "Datafolha",
            "published_at": "2026-03-01T00:00:00Z",
            "collected_at": "2026-03-10T11:00:00Z",
            "type": "estimulada",
            "results": [{"candidate_slug": "lula", "candidate_name": "Lula", "percentage": 35.0}],
        },
        {
            "id": collect_polls.build_poll_id("Quaest", "2026-03-02"),
            "institute": "Quaest",
            "published_at": "2026-03-02T00:00:00Z",
            "collected_at": "2026-03-10T11:00:00Z",
            "type": "estimulada",
            "results": [{"candidate_slug": "tarcisio", "candidate_name": "Tarcisio", "percentage": 22.0}],
        },
    ]
    merged, added = collect_polls.deduplicate_by_id(existing, incoming)
    assert added == 1
    assert len(merged) == 2


def test_idempotent_double_run(isolated_workspace: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_sources(
        isolated_workspace["sources"],
        [{"name": "Datafolha", "url": "https://example.com/datafolha", "active": True}],
    )

    class FakeBrowser:
        async def close(self) -> None:
            return None

    class FakeChromium:
        async def launch(self, headless: bool = True) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def __aenter__(self) -> "FakePlaywright":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    async def fake_scrape_source(browser: Any, source: dict[str, Any], timeout_ms: int = 30000) -> dict[str, Any]:
        return {
            "id": collect_polls.build_poll_id("Datafolha", "2026-03-01"),
            "institute": "Datafolha",
            "published_at": "2026-03-01T00:00:00Z",
            "collected_at": "2026-03-10T10:00:00Z",
            "type": "estimulada",
            "source_url": source["url"],
            "results": [{"candidate_slug": "lula", "candidate_name": "Lula", "percentage": 35.0}],
        }

    monkeypatch.setattr(collect_polls, "async_playwright", lambda: FakePlaywright())
    monkeypatch.setattr(collect_polls, "scrape_source", fake_scrape_source)

    first_run = collect_polls.collect_polls()
    before = isolated_workspace["polls"].read_text(encoding="utf-8")
    second_run = collect_polls.collect_polls()
    after = isolated_workspace["polls"].read_text(encoding="utf-8")

    assert first_run[0] == 1
    assert second_run[0] == 0
    assert before == after


def test_institute_failure_does_not_crash(isolated_workspace: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_sources(
        isolated_workspace["sources"],
        [
            {"name": "Datafolha", "url": "https://example.com/bad", "active": True},
            {"name": "Quaest", "url": "https://example.com/good", "active": True},
        ],
    )

    class FakeBrowser:
        async def close(self) -> None:
            return None

    class FakeChromium:
        async def launch(self, headless: bool = True) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def __aenter__(self) -> "FakePlaywright":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    async def fake_scrape_source(browser: Any, source: dict[str, Any], timeout_ms: int = 30000) -> dict[str, Any]:
        if "bad" in source["url"]:
            raise TimeoutError("timed out")
        return {
            "id": collect_polls.build_poll_id("Quaest", "2026-03-02"),
            "institute": "Quaest",
            "published_at": "2026-03-02T00:00:00Z",
            "collected_at": "2026-03-10T10:00:00Z",
            "type": "estimulada",
            "source_url": source["url"],
            "results": [{"candidate_slug": "tarcisio", "candidate_name": "Tarcisio", "percentage": 24.0}],
        }

    monkeypatch.setattr(collect_polls, "async_playwright", lambda: FakePlaywright())
    monkeypatch.setattr(collect_polls, "scrape_source", fake_scrape_source)

    new_count, source_count, error_count = collect_polls.collect_polls()
    error_payload = json.loads(isolated_workspace["pipeline_errors"].read_text(encoding="utf-8"))
    polls = _read_polls(isolated_workspace["polls"])

    assert new_count == 1
    assert source_count == 2
    assert error_count == 1
    assert len(polls) == 1
    assert isinstance(error_payload.get("errors"), list)
    assert len(error_payload["errors"]) == 1


def test_polls_schema_valid(isolated_workspace: dict[str, Path]) -> None:
    polls_payload = {
        "$schema": "../docs/schemas/polls.schema.json",
        "polls": [
            {
                "id": collect_polls.build_poll_id("Datafolha", "2026-03-01"),
                "institute": "Datafolha",
                "published_at": "2026-03-01T00:00:00Z",
                "collected_at": "2026-03-10T10:00:00Z",
                "type": "estimulada",
                "sample_size": 2000,
                "margin_of_error": 2.0,
                "results": [
                    {
                        "candidate_slug": "lula",
                        "candidate_name": "Lula",
                        "percentage": 35.0,
                    },
                    {
                        "candidate_slug": "tarcisio",
                        "candidate_name": "Tarcisio",
                        "percentage": 22.0,
                    },
                ],
            }
        ],
        "last_updated": "2026-03-10T10:00:00Z",
        "total_count": 1,
    }
    _write_json(isolated_workspace["polls"], polls_payload)

    schema = json.loads(isolated_workspace["schema"].read_text(encoding="utf-8"))
    saved_payload = json.loads(isolated_workspace["polls"].read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    errors = [err.message for err in validator.iter_errors(saved_payload)]
    assert not errors, errors[:5]
