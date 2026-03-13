"""Polling collection pipeline for Phase 08."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from playwright.async_api import Browser, Page, async_playwright

PollType = Literal["estimulada", "espontanea"]


class PollSource(TypedDict):
    name: str
    url: str
    active: bool


class PollResultItem(TypedDict):
    candidate_slug: str
    candidate_name: str
    percentage: float
    variation: NotRequired[float | None]


class PollItem(TypedDict):
    id: str
    institute: str
    published_at: str
    collected_at: str
    type: PollType
    results: list[PollResultItem]
    sample_size: NotRequired[int]
    margin_of_error: NotRequired[float]
    confidence_level: NotRequired[float]
    tse_registration: NotRequired[str | None]
    source_url: NotRequired[str]
    raw_html_snippet: NotRequired[str]


@dataclass
class PollsDocument:
    payload: list[PollItem] | dict[str, Any]
    polls: list[PollItem]
    uses_wrapped_shape: bool


logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
POLLS_FILE = DATA_DIR / "polls.json"
PIPELINE_ERRORS_FILE = DATA_DIR / "pipeline_errors.json"
DEFAULT_SCHEMA_PATH = "../docs/schemas/polls.schema.json"

API_KEY_PATTERN = re.compile(
    r"(key|api_key|apikey|devKey)=[A-Za-z0-9_-]{20,}", re.IGNORECASE
)
INSTITUTE_ENUM = {
    "Datafolha",
    "Quaest",
    "AtlasIntel",
    "Parana Pesquisas",
    "PoderData",
    "Real Time Big Data",
}
INSTITUTE_ALIASES = {
    "data folha": "Datafolha",
    "genial/quaest": "Quaest",
    "genial quaest": "Quaest",
    "atlas intel": "AtlasIntel",
    "paraná pesquisas": "Parana Pesquisas",
    "parana pesquisas": "Parana Pesquisas",
    "poder data": "PoderData",
    "real time bigdata": "Real Time Big Data",
    "real time": "Real Time Big Data",
}
CANDIDATE_ALIASES = {
    "lula": ("lula", "Lula"),
    "luiz inacio lula da silva": ("lula", "Lula"),
    "flavio bolsonaro": ("flavio-bolsonaro", "Flavio Bolsonaro"),
    "flávio bolsonaro": ("flavio-bolsonaro", "Flavio Bolsonaro"),
    "tarcisio": ("tarcisio", "Tarcisio"),
    "tarcísio": ("tarcisio", "Tarcisio"),
    "tarcisio de freitas": ("tarcisio", "Tarcisio"),
    "tarcísio de freitas": ("tarcisio", "Tarcisio"),
    "caiado": ("caiado", "Caiado"),
    "ronaldo caiado": ("caiado", "Caiado"),
    "zema": ("zema", "Zema"),
    "romeu zema": ("zema", "Zema"),
    "ratinho jr": ("ratinho-jr", "Ratinho Jr"),
    "ratinho jr.": ("ratinho-jr", "Ratinho Jr"),
    "ratinho júnior": ("ratinho-jr", "Ratinho Jr"),
    "ratinho junior": ("ratinho-jr", "Ratinho Jr"),
    "eduardo leite": ("eduardo-leite", "Eduardo Leite"),
    "aldo rebelo": ("aldo-rebelo", "Aldo Rebelo"),
    "renan santos": ("renan-santos", "Renan Santos"),
}
DATE_PATTERN = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")
BR_DATE_PATTERN = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b")


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_poll_id(institute: str, date_yyyy_mm_dd: str) -> str:
    return sha256(f"{institute}_{date_yyyy_mm_dd}".encode()).hexdigest()[:16]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_active_poll_sources() -> list[PollSource]:
    payload = _load_json(SOURCES_FILE)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {SOURCES_FILE}")
    polls = payload.get("polls", [])
    if not isinstance(polls, list):
        raise ValueError(f"Expected 'polls' list in {SOURCES_FILE}")

    active: list[PollSource] = []
    for item in polls:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("active", False)):
            continue
        name = item.get("name")
        url = item.get("url")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(url, str) or not url.strip():
            continue
        active.append({"name": name.strip(), "url": url.strip(), "active": True})
    return active


def load_polls_document() -> PollsDocument:
    if not POLLS_FILE.exists():
        payload: dict[str, Any] = {
            "$schema": DEFAULT_SCHEMA_PATH,
            "polls": [],
            "last_updated": None,
            "total_count": 0,
        }
        return PollsDocument(payload=payload, polls=[], uses_wrapped_shape=True)

    payload = _load_json(POLLS_FILE)
    if isinstance(payload, list):
        polls = [item for item in payload if isinstance(item, dict)]
        return PollsDocument(payload=payload, polls=polls, uses_wrapped_shape=False)

    if isinstance(payload, dict):
        polls = payload.get("polls", [])
        if isinstance(polls, list):
            safe_polls = [item for item in polls if isinstance(item, dict)]
            return PollsDocument(
                payload=payload, polls=safe_polls, uses_wrapped_shape=True
            )

    raise ValueError(f"Unsupported polls structure in {POLLS_FILE}")


def save_polls_document(document: PollsDocument) -> None:
    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if document.uses_wrapped_shape:
        if isinstance(document.payload, dict):
            payload = dict(document.payload)
        else:
            payload = {}
        payload["$schema"] = payload.get("$schema") or DEFAULT_SCHEMA_PATH
        payload["polls"] = document.polls
        payload["last_updated"] = utc_now_iso()
        payload["total_count"] = len(document.polls)
        serializable: object = payload
    else:
        serializable = document.polls
    POLLS_FILE.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def parse_poll_date(raw_text: str) -> str | None:
    compact = " ".join(raw_text.split())
    m_ymd = DATE_PATTERN.search(compact)
    if m_ymd:
        year, month, day = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    m_dmy = BR_DATE_PATTERN.search(compact)
    if m_dmy:
        day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def parse_sample_size(raw_text: str) -> int | None:
    patterns = (
        r"amostra[^0-9]{0,20}([\d\.\, ]{3,})",
        r"(\d[\d\.\, ]{2,})\s*(?:entrevistas|respondentes|eleitores)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if not match:
            continue
        numeric = re.sub(r"[^\d]", "", match.group(1))
        if not numeric:
            continue
        value = int(numeric)
        if value > 0:
            return value
    return None


def parse_margin_of_error(raw_text: str) -> float | None:
    match = re.search(
        r"(?:margem de erro|erro)[^0-9]{0,20}(\d{1,2}(?:[\,\.]\d+)?)\s*(?:p\.?p\.?|%)?",
        raw_text,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    if value < 0 or value > 10:
        return None
    return value


def infer_poll_type(raw_text: str) -> PollType:
    if "espont" in raw_text.lower():
        return "espontanea"
    return "estimulada"


def normalize_institute_name(name: str) -> str:
    cleaned = " ".join(name.split()).strip()
    if cleaned in INSTITUTE_ENUM:
        return cleaned
    lowered = cleaned.lower()
    if lowered in INSTITUTE_ALIASES:
        return INSTITUTE_ALIASES[lowered]
    for key, canonical in INSTITUTE_ALIASES.items():
        if key in lowered:
            return canonical
    return cleaned


def canonical_candidate_slug(raw_name: str) -> str | None:
    lowered = re.sub(r"\s+", " ", raw_name.strip().lower())
    if lowered in CANDIDATE_ALIASES:
        return CANDIDATE_ALIASES[lowered][0]
    for key, value in CANDIDATE_ALIASES.items():
        if key in lowered:
            return value[0]
    return None


def _canonical_candidate_name(slug: str) -> str:
    for maybe_slug, candidate_name in CANDIDATE_ALIASES.values():
        if maybe_slug == slug:
            return candidate_name
    return slug.replace("-", " ").title()


def deduplicate_by_id(
    existing: list[PollItem], incoming: list[PollItem]
) -> tuple[list[PollItem], int]:
    seen = {
        item_id
        for item in existing
        for item_id in [item.get("id")]
        if isinstance(item_id, str)
    }
    merged = list(existing)
    added = 0
    for item in incoming:
        poll_id = item.get("id")
        if not isinstance(poll_id, str):
            continue
        if poll_id in seen:
            continue
        merged.append(item)
        seen.add(poll_id)
        added += 1
    return merged, added


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


def append_pipeline_error(*, institute: str, source_url: str, message: str) -> None:
    sanitized = API_KEY_PATTERN.sub(r"\1=[REDACTED]", message)
    payload = _load_pipeline_errors()
    payload["errors"].append(
        {
            "at": utc_now_iso(),
            "tier": "foca",
            "script": "collect_polls.py",
            "institute": institute,
            "source_url": source_url,
            "message": sanitized,
        }
    )
    payload["last_checked"] = utc_now_iso()
    PIPELINE_ERRORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_ERRORS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _coerce_percentage(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        match = re.search(r"(\d{1,2}(?:[\,\.]\d+)?)", value)
        if not match:
            return None
        numeric = float(match.group(1).replace(",", "."))
    else:
        return None
    if 0 <= numeric <= 100:
        return round(numeric, 2)
    return None


def _extract_result_from_mapping(
    candidate_name: Any, percentage: Any
) -> PollResultItem | None:
    if not isinstance(candidate_name, str):
        return None
    slug = canonical_candidate_slug(candidate_name)
    if not slug:
        return None
    numeric = _coerce_percentage(percentage)
    if numeric is None:
        return None
    return {
        "candidate_slug": slug,
        "candidate_name": _canonical_candidate_name(slug),
        "percentage": numeric,
    }


def _collect_jsonld_results(node: Any, output: dict[str, PollResultItem]) -> None:
    if isinstance(node, dict):
        candidate = (
            node.get("candidate") or node.get("name") or node.get("candidate_name")
        )
        percentage = (
            node.get("percentage")
            or node.get("percent")
            or node.get("value")
            or node.get("votos")
        )
        result = _extract_result_from_mapping(candidate, percentage)
        if result:
            output[result["candidate_slug"]] = result
        for value in node.values():
            _collect_jsonld_results(value, output)
    elif isinstance(node, list):
        for item in node:
            _collect_jsonld_results(item, output)


async def extract_candidates_from_jsonld(page: Page) -> list[PollResultItem]:
    scripts = await page.query_selector_all("script[type='application/ld+json']")
    found: dict[str, PollResultItem] = {}
    for script in scripts:
        text = await script.inner_text()
        if not text.strip():
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        _collect_jsonld_results(payload, found)
    return list(found.values())


async def extract_candidates_from_tables(page: Page) -> list[PollResultItem]:
    rows = await page.eval_on_selector_all(
        "table tr",
        "elements => elements.map((el) => el.innerText).filter(Boolean)",
    )
    if not isinstance(rows, list):
        return []

    found: dict[str, PollResultItem] = {}
    for row in rows:
        if not isinstance(row, str):
            continue
        compact = " ".join(row.split())
        slug = canonical_candidate_slug(compact)
        if not slug:
            continue
        percentage = _coerce_percentage(compact)
        if percentage is None:
            continue
        found[slug] = {
            "candidate_slug": slug,
            "candidate_name": _canonical_candidate_name(slug),
            "percentage": percentage,
        }
    return list(found.values())


async def extract_poll_payload(page: Page, source: PollSource) -> PollItem | None:
    institute = normalize_institute_name(source["name"])
    if institute not in INSTITUTE_ENUM:
        logger.warning("Skipping unsupported institute name: %s", institute)
        return None

    page_text = await page.evaluate(
        "() => document.body ? document.body.innerText : ''"
    )
    if not isinstance(page_text, str):
        page_text = ""

    date_text = parse_poll_date(page_text) or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d"
    )
    published_at = f"{date_text}T00:00:00Z"
    poll_type = infer_poll_type(page_text)
    collected_at = utc_now_iso()

    results = await extract_candidates_from_jsonld(page)
    if not results:
        results = await extract_candidates_from_tables(page)
    if not results:
        return None

    poll: PollItem = {
        "id": build_poll_id(institute, date_text),
        "institute": institute,
        "published_at": published_at,
        "collected_at": collected_at,
        "type": poll_type,
        "results": results,
        "source_url": source["url"],
    }

    sample_size = parse_sample_size(page_text)
    if sample_size is not None:
        poll["sample_size"] = sample_size

    margin_of_error = parse_margin_of_error(page_text)
    if margin_of_error is not None:
        poll["margin_of_error"] = margin_of_error

    confidence_match = re.search(
        r"(?:confianca|confidence)[^0-9]{0,12}(\d{2,3})\s*%", page_text, re.IGNORECASE
    )
    if confidence_match:
        confidence_level = float(confidence_match.group(1))
        if 0 <= confidence_level <= 100:
            poll["confidence_level"] = confidence_level

    tse_match = re.search(r"(BR-\d{4}/\d{4}|[A-Z]{2,4}-\d{1,5}/\d{4})", page_text)
    if tse_match:
        poll["tse_registration"] = tse_match.group(1)

    html_content = await page.content()
    snippet = " ".join(re.sub(r"\s+", " ", html_content).split())
    if snippet:
        poll["raw_html_snippet"] = snippet[:500]

    return poll


async def scrape_source(
    browser: Browser, source: PollSource, timeout_ms: int = 30000
) -> PollItem | None:
    page = await browser.new_page()
    try:
        page.set_default_timeout(timeout_ms)
        await page.goto(
            source["url"], timeout=timeout_ms, wait_until="domcontentloaded"
        )
        return await extract_poll_payload(page, source)
    finally:
        await page.close()


async def collect_polls_async() -> tuple[int, int, int]:
    sources = load_active_poll_sources()
    document = load_polls_document()
    incoming: list[PollItem] = []
    errors = 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for source in sources:
                try:
                    poll = await scrape_source(browser, source, timeout_ms=30000)
                except Exception as exc:
                    errors += 1
                    append_pipeline_error(
                        institute=source["name"],
                        source_url=source["url"],
                        message=str(exc),
                    )
                    continue
                if poll is not None:
                    incoming.append(poll)
        finally:
            await browser.close()

    merged, new_count = deduplicate_by_id(document.polls, incoming)
    document.polls = merged
    if new_count > 0 or not POLLS_FILE.exists():
        save_polls_document(document)
    return new_count, len(sources), errors


def collect_polls() -> tuple[int, int, int]:
    return asyncio.run(collect_polls_async())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    new_count, source_count, error_count = collect_polls()
    print(
        f"Collected {new_count} new polls from {source_count} institutes ({error_count} errors)"
    )


if __name__ == "__main__":
    main()
