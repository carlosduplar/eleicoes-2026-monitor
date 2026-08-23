"""Market odds collection from Polymarket CLOB API."""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NotRequired, TypedDict

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
MARKETS_FILE = DATA_DIR / "markets.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
DEFAULT_SCHEMA_PATH = "../docs/schemas/markets.schema.json"

CLOB_BASE = "https://clob.polymarket.com"
BRAZIL_KEYWORDS = {"brazil", "brasil", "brasileiro", "brazilian"}
ELECTION_KEYWORDS = {"2026", "president", "presidential", "eleicao", "eleitoral"}
API_KEY_PATTERN = re.compile(
    r"(key|api_key|apikey|devKey)=[A-Za-z0-9_-]{20,}", re.IGNORECASE
)

logger = logging.getLogger(__name__)


class MarketItem(TypedDict):
    id: str
    slug: str
    question: str
    yes_price: float
    no_price: float
    volume: float
    market_url: str
    collected_at: str
    liquidity: NotRequired[float]


@dataclass
class MarketsDocument:
    payload: dict[str, Any] | list[MarketItem]
    markets: list[MarketItem]
    uses_wrapped_shape: bool


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_markets_document() -> MarketsDocument:
    if not MARKETS_FILE.exists():
        payload: dict[str, Any] = {
            "$schema": DEFAULT_SCHEMA_PATH,
            "markets": [],
            "last_updated": None,
            "total_count": 0,
        }
        return MarketsDocument(payload=payload, markets=[], uses_wrapped_shape=True)

    payload = _load_json(MARKETS_FILE)
    if isinstance(payload, list):
        markets = [item for item in payload if isinstance(item, dict)]
        return MarketsDocument(payload=payload, markets=markets, uses_wrapped_shape=False)

    if isinstance(payload, dict):
        markets = payload.get("markets", [])
        if isinstance(markets, list):
            safe_markets = [item for item in markets if isinstance(item, dict)]
            return MarketsDocument(
                payload=payload, markets=safe_markets, uses_wrapped_shape=True
            )

    raise ValueError(f"Unsupported markets structure in {MARKETS_FILE}")


def save_markets_document(document: MarketsDocument) -> None:
    MARKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if document.uses_wrapped_shape:
        if isinstance(document.payload, dict):
            payload = dict(document.payload)
        else:
            payload = {}
        payload["$schema"] = payload.get("$schema") or DEFAULT_SCHEMA_PATH
        payload["markets"] = document.markets
        payload["last_updated"] = utc_now_iso()
        payload["total_count"] = len(document.markets)
        serializable: object = payload
    else:
        serializable = document.markets
    MARKETS_FILE.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 eleicoes-2026-monitor/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


GAMMA_API_BASE = "https://gamma-api.polymarket.com"
EVENT_SLUGS = (
    "brazil-presidential-election",
)


def is_brazil_election_market(question: str, slug: str) -> bool:
    q_lower = question.lower()
    s_lower = slug.lower()
    text = q_lower + " " + s_lower
    has_brazil = any(kw in text for kw in BRAZIL_KEYWORDS)
    has_election = any(kw in text for kw in ELECTION_KEYWORDS)
    return has_brazil and has_election


def _parse_outcome_prices(market: dict[str, Any]) -> tuple[float, float]:
    raw_prices = market.get("outcomePrices")
    prices: list[Any] = []
    if isinstance(raw_prices, str):
        try:
            parsed = json.loads(raw_prices)
            if isinstance(parsed, list):
                prices = parsed
        except json.JSONDecodeError:
            prices = []
    elif isinstance(raw_prices, list):
        prices = raw_prices

    def clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    yes_price = clamp(float(prices[0])) if len(prices) > 0 else 0.0
    no_price = clamp(float(prices[1])) if len(prices) > 1 else clamp(1.0 - yes_price)
    return yes_price, no_price


def fetch_markets() -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []

    for event_slug in EVENT_SLUGS:
        try:
            payload = _fetch_json(f"{GAMMA_API_BASE}/events?slug={event_slug}")
        except Exception as exc:
            logger.warning("Failed to fetch Gamma event %s: %s", event_slug, exc)
            continue

        events = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(events, list) or not events:
            logger.warning("Gamma API returned no event for slug %s", event_slug)
            continue

        event_markets = events[0].get("markets") if isinstance(events[0], dict) else None
        if not isinstance(event_markets, list):
            continue

        for market in event_markets:
            if not isinstance(market, dict):
                continue
            if market.get("closed") or market.get("archived"):
                continue
            market_id = str(market.get("id") or "")
            slug = market.get("slug")
            if not market_id or not isinstance(slug, str) or not slug:
                continue

            yes_price, no_price = _parse_outcome_prices(market)
            question = market.get("groupItemTitle") or market.get("question") or slug
            try:
                volume = float(market.get("volumeNum", market.get("volume")) or 0)
                liquidity = float(market.get("liquidityNum", market.get("liquidity")) or 0)
            except (TypeError, ValueError):
                volume, liquidity = 0.0, 0.0

            collected.append(
                {
                    "id": market_id,
                    "condition_id": market.get("conditionId"),
                    "slug": slug,
                    "question": str(question).strip(),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": volume,
                    "liquidity": liquidity,
                }
            )

    logger.info("Found %d Brazil election markets from Gamma events", len(collected))
    if not collected:
        logger.warning("No markets found; falling back to CLOB keyword search")
        try:
            data = _fetch_json(f"{CLOB_BASE}/markets?limit=500&closed=false")
        except Exception as exc:
            logger.warning("Failed to fetch markets list: %s", exc)
            raise

        results = data.get("results", []) if isinstance(data, dict) else data
        collected = [
            m for m in results
            if isinstance(m, dict)
            and is_brazil_election_market(m.get("question", ""), m.get("slug", ""))
        ]
    return collected


def fetch_market_order_book(market_id: str) -> dict[str, Any]:
    try:
        return _fetch_json(f"{CLOB_BASE}/orderbook?market={market_id}")
    except Exception as exc:
        logger.warning("Failed to fetch order book for %s: %s", market_id, exc)
        return {}


def build_market_item(raw: dict[str, Any], order_book: dict[str, Any]) -> MarketItem:
    yes_price = raw.get("yes_price", 0.5)
    no_price = raw.get("no_price", 0.5)
    volume = raw.get("volume", 0)
    slug = raw.get("slug", "")
    market_id = raw.get("id", "") or raw.get("condition_id", "")

    if yes_price == 0 and no_price == 0:
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if bids:
            try:
                yes_price = float(bids[0][0])
            except (ValueError, IndexError):
                pass
        if asks:
            try:
                no_price = float(asks[0][0])
            except (ValueError, IndexError):
                pass

    return {
        "id": market_id,
        "slug": slug,
        "question": raw.get("question", ""),
        "yes_price": round(float(yes_price), 4),
        "no_price": round(float(no_price), 4),
        "volume": float(volume),
        "liquidity": round(float(raw.get("liquidity", 0)), 2),
        "market_url": f"https://polymarket.com/market/{slug}",
        "collected_at": utc_now_iso(),
    }


def _load_pipeline_errors() -> dict[str, Any]:
    if not PIPELINE_ERRORS_FILE.exists():
        return {"errors": [], "last_checked": None}
    try:
        return _load_json(PIPELINE_ERRORS_FILE)
    except json.JSONDecodeError:
        return {"errors": [], "last_checked": None}


def append_pipeline_error(*, source_name: str, source_url: str, message: str) -> None:
    sanitized = API_KEY_PATTERN.sub(r"\1=[REDACTED]", message)
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": utc_now_iso(),
            "tier": "foca",
            "script": "collect_markets.py",
            "source_name": source_name,
            "source_url": source_url,
            "message": sanitized,
        }
    )
    payload["last_checked"] = utc_now_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def collect_markets() -> tuple[int, int, int]:
    logger.info("Starting Polymarket market collection...")
    document = load_markets_document()
    incoming: list[MarketItem] = []
    errors = 0

    try:
        raw_markets = fetch_markets()
    except Exception as exc:
        append_pipeline_error(
            source_name="Polymarket",
            source_url=f"{CLOB_BASE}/markets",
            message=str(exc),
        )
        return 0, 1, 1

    for raw in raw_markets:
        market_id = raw.get("id", "") or raw.get("condition_id", "")
        slug = raw.get("slug", "")
        if not market_id:
            continue

        try:
            has_prices = bool(raw.get("yes_price")) or bool(raw.get("no_price"))
            order_book = fetch_market_order_book(market_id) if not has_prices else {}
            item = build_market_item(raw, order_book)
            incoming.append(item)
        except Exception as exc:
            errors += 1
            append_pipeline_error(
                source_name="Polymarket",
                source_url=f"{CLOB_BASE}/markets/{slug}",
                message=str(exc),
            )
            continue

    existing_ids = {m["id"] for m in document.markets if isinstance(m, dict)}
    merged = list(document.markets)
    added = 0
    for item in incoming:
        if item["id"] not in existing_ids:
            merged.append(item)
            existing_ids.add(item["id"])
            added += 1

    document.markets = merged
    save_markets_document(document)
    logger.info("Markets: %d new, %d total, %d errors", added, len(merged), errors)
    return added, len(raw_markets), errors


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    new_count, source_count, error_count = collect_markets()
    print(
        f"Collected {new_count} new markets from Polymarket ({source_count} markets checked, {error_count} errors)"
    )


if __name__ == "__main__":
    main()