import json
from pathlib import Path
from typing import Any

import pytest

from scripts import collect_markets


def _gamma_event_payload() -> dict[str, Any]:
    return {
        "events": [
            {
                "id": "45915",
                "slug": "brazil-presidential-election",
                "markets": [
                    {
                        "id": "601818",
                        "slug": "lula-wins-2026",
                        "question": "Will Lula win the 2026 Brazilian presidential election?",
                        "groupItemTitle": "Luiz Inácio Lula da Silva",
                        "conditionId": "0xabc",
                        "outcomePrices": ["0.62", "0.38"],
                        "volume": "1234567.89",
                        "volumeNum": 1234567.89,
                        "liquidity": "89000.5",
                        "liquidityNum": 89000.5,
                        "closed": False,
                        "archived": False,
                        "active": True,
                    },
                    {
                        "id": "601819",
                        "slug": "tarcisio-wins-2026",
                        "question": "Will Tarcisio win?",
                        "groupItemTitle": "Tarcisio de Freitas",
                        "outcomePrices": '["0.0005", "0.9995"]',
                        "volumeNum": 5000,
                        "liquidityNum": 1000,
                        "closed": False,
                        "archived": False,
                    },
                    {
                        "id": "601820",
                        "slug": "resolved-market",
                        "question": "Resolved market",
                        "outcomePrices": ["1", "0"],
                        "closed": True,
                        "archived": False,
                    },
                ],
            }
        ]
    }


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    data_dir = tmp_path / "data"
    markets_file = data_dir / "markets.json"
    pipeline_errors_file = data_dir / "pipeline_errors.json"

    monkeypatch.setattr(collect_markets, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(collect_markets, "DATA_DIR", data_dir)
    monkeypatch.setattr(collect_markets, "MARKETS_FILE", markets_file)
    monkeypatch.setattr(collect_markets, "PIPELINE_ERRORS_FILE", pipeline_errors_file)

    return {
        "root": tmp_path,
        "data": data_dir,
        "markets": markets_file,
        "pipeline_errors": pipeline_errors_file,
    }


def test_parse_outcome_prices_accepts_list_and_json_string() -> None:
    assert collect_markets._parse_outcome_prices({"outcomePrices": ["0.62", "0.38"]}) == (0.62, 0.38)
    assert collect_markets._parse_outcome_prices({'outcomePrices': '["0.3", "0.7"]'}) == (0.3, 0.7)


def test_parse_outcome_prices_clamps_and_derives_no_price() -> None:
    assert collect_markets._parse_outcome_prices({"outcomePrices": ["1.4"]}) == (1.0, 0.0)
    assert collect_markets._parse_outcome_prices({}) == (0.0, 1.0)


def test_fetch_markets_maps_gamma_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collect_markets, "_fetch_json", lambda url: _gamma_event_payload())

    markets = collect_markets.fetch_markets()

    assert len(markets) == 2
    lula = markets[0]
    assert lula["id"] == "601818"
    assert lula["question"] == "Luiz Inácio Lula da Silva"
    assert lula["yes_price"] == 0.62
    assert lula["no_price"] == 0.38
    assert lula["volume"] == pytest.approx(1234567.89)
    assert lula["liquidity"] == pytest.approx(89000.5)


def test_fetch_markets_falls_back_to_clob_when_gamma_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_fetch(url: str) -> Any:
        calls.append(url)
        if url.startswith(collect_markets.GAMMA_API_BASE):
            return {"events": []}
        return {"results": [{"id": "clob1", "slug": "brazil-president-2026", "question": "Brazil president?"}]}

    monkeypatch.setattr(collect_markets, "_fetch_json", fake_fetch)

    markets = collect_markets.fetch_markets()

    assert len(calls) == 2
    assert len(markets) == 1
    assert markets[0]["id"] == "clob1"


def test_build_market_item_uses_order_book_only_without_prices() -> None:
    raw = {"id": "m1", "slug": "lula-wins", "question": "Lula?", "yes_price": 0.4, "no_price": 0.6, "volume": 10, "liquidity": 5}
    item = collect_markets.build_market_item(raw, {"bids": [["0.9"]], "asks": [["0.1"]]})
    assert item["yes_price"] == 0.4
    assert item["no_price"] == 0.6
    assert item["market_url"] == "https://polymarket.com/market/lula-wins"

    raw_zero = {"id": "m2", "slug": "zero", "question": "Zero?", "yes_price": 0, "no_price": 0, "volume": 1}
    item_zero = collect_markets.build_market_item(raw_zero, {"bids": [["0.25"]], "asks": [["0.75"]]})
    assert item_zero["yes_price"] == 0.25
    assert item_zero["no_price"] == 0.75


def test_collect_markets_persists_and_dedupes(isolated_workspace: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collect_markets, "fetch_markets", lambda: _gamma_event_payload()["events"][0]["markets"][:2])
    monkeypatch.setattr(collect_markets, "fetch_market_order_book", lambda market_id: {})

    added, checked, errors = collect_markets.collect_markets()
    assert (added, checked, errors) == (2, 2, 0)

    added_again, _, _ = collect_markets.collect_markets()
    assert added_again == 0

    saved = json.loads(isolated_workspace["markets"].read_text(encoding="utf-8"))
    assert saved["total_count"] == 2
    assert saved["$schema"].endswith("markets.schema.json")


def test_collect_markets_records_pipeline_error_on_fetch_failure(
    isolated_workspace: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> list[dict[str, Any]]:
        raise RuntimeError("gamma down and clob down")

    monkeypatch.setattr(collect_markets, "fetch_markets", boom)

    added, checked, errors = collect_markets.collect_markets()

    assert (added, checked, errors) == (0, 1, 1)
    payload = json.loads(isolated_workspace["pipeline_errors"].read_text(encoding="utf-8"))
    assert any(entry["script"] == "collect_markets.py" for entry in payload["errors"])
