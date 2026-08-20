"""Polling collection pipeline for Phase 08."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

import requests
from playwright.async_api import Browser, Page, async_playwright

BRIGHTDATA_ZONE = os.environ.get("BRIGHTDATA_ZONE", "web_unlocker1")
BRIGHTDATA_ENABLE_POLLS = os.environ.get("BRIGHTDATA_ENABLE_POLLS", "").strip() == "1"
POLL_FETCH_INTERVAL_MINUTES = 1440
REQUEST_TIMEOUT_SECONDS = 30

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
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
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
    "Futura Inteligencia",
    "Ipsos",
    "MDA",
    "Ideia",
}
INSTITUTE_ALIASES = {
    "data folha": "Datafolha",
    "datafolha": "Datafolha",
    "genial/quaest": "Quaest",
    "genial quaest": "Quaest",
    "atlas intel": "AtlasIntel",
    "paraná pesquisas": "Parana Pesquisas",
    "parana pesquisas": "Parana Pesquisas",
    "poder data": "PoderData",
    "real time bigdata": "Real Time Big Data",
    "real time": "Real Time Big Data",
    "futura inteligência": "Futura Inteligencia",
    "futura inteligencia": "Futura Inteligencia",
    "apex/futura": "Futura Inteligencia",
    "futura/apex": "Futura Inteligencia",
    "futura/inteligência": "Futura Inteligencia",
    "futura/inteligencia": "Futura Inteligencia",
    "ipsos-ipec": "Ipsos",
    "ipec": "Ipsos",
    "cnt/mda": "MDA",
    "mda pesquisa": "MDA",
    "meio/ideia": "Ideia",
    "ideia big data": "Ideia",
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


def _fetch_state_path() -> Path:
    return DATA_DIR / "fetch_state.json"


def _load_fetch_state() -> dict[str, str]:
    state_path = _fetch_state_path()
    if not state_path.exists():
        return {}
    try:
        payload = _load_json(state_path)
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(url): str(ts) for url, ts in payload.items() if isinstance(ts, str)}


def _save_fetch_state(state: dict[str, str]) -> None:
    state_path = _fetch_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _is_fetch_due(last_fetch_iso: str | None, interval_minutes: int) -> bool:
    if not last_fetch_iso:
        return True
    try:
        last = datetime.fromisoformat(last_fetch_iso.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - last
    return elapsed >= timedelta(minutes=interval_minutes)


def _brasilia_now() -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Sao_Paulo"))


def _is_weekend() -> bool:
    return _brasilia_now().weekday() >= 5


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


def _fetch_url_brightdata(url: str, api_key: str = "") -> str:
    """Fetch URL through Bright Data's Web Unlocker API."""
    response = requests.post(
        "https://api.brightdata.com/request",
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        },
        json={"zone": BRIGHTDATA_ZONE.strip(), "url": url, "format": "raw"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"BrightData API error: {response.status_code} - {response.text[:500]}"
        )
    try:
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(f"BrightData API error: {payload['error']}")
    except ValueError:
        pass
    return response.text


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


async def extract_poll_payload_from_html(
    html: str, source: PollSource
) -> PollItem | None:
    """Extract poll data from raw HTML (e.g., from Bright Data)."""
    from bs4 import BeautifulSoup

    institute = normalize_institute_name(source["name"])
    if institute not in INSTITUTE_ENUM:
        logger.warning("Skipping unsupported institute name: %s", institute)
        return None

    soup = BeautifulSoup(html, "lxml")
    page_text = soup.get_text()
    if not page_text:
        page_text = ""

    date_text = parse_poll_date(page_text) or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d"
    )
    published_at = f"{date_text}T00:00:00Z"
    poll_type = infer_poll_type(page_text)
    collected_at = utc_now_iso()

    results = await extract_candidates_from_jsonld_html(soup)
    if not results:
        results = await extract_candidates_from_tables_html(soup)
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

    snippet = " ".join(re.sub(r"\s+", " ", html).split())
    if snippet:
        poll["raw_html_snippet"] = snippet[:500]

    return poll


async def extract_candidates_from_jsonld_html(soup) -> list[PollResultItem]:
    """Extract candidates from JSON-LD in HTML."""
    scripts = soup.find_all("script", type="application/ld+json")
    found: dict[str, PollResultItem] = {}
    for script in scripts:
        try:
            payload = json.loads(script.string or "")
            _collect_jsonld_results(payload, found)
        except (json.JSONDecodeError, TypeError):
            continue
    return list(found.values())


async def extract_candidates_from_tables_html(soup) -> list[PollResultItem]:
    """Extract candidates from HTML tables."""
    found: dict[str, PollResultItem] = {}
    for row in soup.select("table tr"):
        text = row.get_text()
        if not text:
            continue
        compact = " ".join(text.split())
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


ARTICLES_FILE = ROOT_DIR / "site" / "public" / "data" / "articles.json"


def extract_polls_from_articles() -> list[PollItem]:
    """Extract poll data from collected articles."""
    if not ARTICLES_FILE.exists():
        return []

    try:
        payload = _load_json(ARTICLES_FILE)
    except Exception:
        return []

    articles = []
    if isinstance(payload, dict):
        articles = payload.get("articles", [])
    elif isinstance(payload, list):
        articles = payload

    INSTITUTE_PATTERNS = {
        "Datafolha": re.compile(r"\bdatafolha\b", re.IGNORECASE),
        "Quaest": re.compile(r"\bquaest\b", re.IGNORECASE),
        "AtlasIntel": re.compile(r"\batlas\s*intel\b", re.IGNORECASE),
        "Parana Pesquisas": re.compile(r"\bparana\s*pesquisas?\b", re.IGNORECASE),
        "PoderData": re.compile(r"\bpoder\s*data\b", re.IGNORECASE),
        "Real Time Big Data": re.compile(
            r"\breal\s*time\s*(big\s*)?data\b", re.IGNORECASE
        ),
        "Futura Inteligencia": re.compile(
            r"\bfutura\s*(inteligencia|inteligência)\b", re.IGNORECASE
        ),
        "Ipsos": re.compile(r"\bipsos\b", re.IGNORECASE),
        "MDA": re.compile(r"\b(cnt/?mda|mda)\b", re.IGNORECASE),
        "Ideia": re.compile(r"\b(meio/?ideia|ideia)\b", re.IGNORECASE),
    }

    PERCENTAGE_PATTERN = re.compile(
        r"(\d{1,2}(?:[\.,]\d+)?)\s*%\s+(lula|flavio|bolsonaro|tarcisio|tarcísio|caiado|zema|ratinho|eduardo|aldo|rebelos|renan|haddad|ciro)",
        re.IGNORECASE,
    )

    polls: list[PollItem] = []
    seen_polls: set[str] = set()

    for article in articles:
        if not isinstance(article, dict):
            continue

        content = (article.get("title", "") + " " + article.get("content", "")).lower()
        url = article.get("url", "")
        published = article.get("published_at", "")[:10]

        institute_name = None
        for inst, pattern in INSTITUTE_PATTERNS.items():
            if pattern.search(content):
                institute_name = inst
                break

        if not institute_name:
            continue

        matches = PERCENTAGE_PATTERN.findall(content)
        if not matches:
            continue

        results: list[PollResultItem] = []
        seen_candidates: set[str] = set()

        for pct_str, candidate in matches:
            pct = float(pct_str.replace(",", "."))
            if pct > 100 or pct == 0:
                continue
            slug = canonical_candidate_slug(candidate)
            if not slug or slug in seen_candidates:
                continue
            seen_candidates.add(slug)
            results.append(
                {
                    "candidate_slug": slug,
                    "candidate_name": _canonical_candidate_name(slug),
                    "percentage": round(pct, 1),
                }
            )

        if len(results) < 2:
            continue

        poll_id = build_poll_id(institute_name, published)
        if poll_id in seen_polls:
            continue
        seen_polls.add(poll_id)

        poll: PollItem = {
            "id": poll_id,
            "institute": institute_name,
            "published_at": f"{published}T00:00:00Z",
            "collected_at": utc_now_iso(),
            "type": "estimulada",
            "results": results,
            "source_url": url,
        }
        polls.append(poll)
        logger.info(f"Extracted poll from article: {institute_name} ({published})")

    return polls


async def collect_polls_async() -> tuple[int, int, int]:
    sources = load_active_poll_sources()
    if _is_weekend():
        logger.info("Weekend: skipping poll collection until next weekday")
        return 0, len(sources), 0

    document = load_polls_document()
    incoming: list[PollItem] = []
    errors = 0
    fetch_state = _load_fetch_state()
    state_changed = False

    brightdata_key = (
        os.environ.get("BRIGHTDATA_API_KEY", "").strip()
        if BRIGHTDATA_ENABLE_POLLS
        else ""
    )
    browser: Browser | None = None

    async with async_playwright() as playwright:
        try:
            for source in sources:
                source_url = source["url"]
                last_fetch = fetch_state.get(source_url)
                if last_fetch and not _is_fetch_due(
                    last_fetch, POLL_FETCH_INTERVAL_MINUTES
                ):
                    logger.info(
                        "Throttled: %s (%s) skipped (last fetch %s)",
                        source["name"],
                        source_url,
                        last_fetch,
                    )
                    continue
                try:
                    poll: PollItem | None = None
                    if brightdata_key:
                        try:
                            html = _fetch_url_brightdata(source_url, brightdata_key)
                            poll = await extract_poll_payload_from_html(html, source)
                        except Exception as exc:
                            logger.warning(
                                "Bright Data failed for %s: %s", source["name"], exc
                            )

                    if poll is None:
                        if browser is None:
                            browser = await playwright.chromium.launch(
                                channel="chrome", headless=True
                            )
                            logger.info("System Chrome ready as poll fallback")
                        poll = await scrape_source(browser, source, timeout_ms=30000)
                except Exception as exc:
                    errors += 1
                    append_pipeline_error(
                        institute=source["name"],
                        source_url=source_url,
                        message=str(exc),
                    )
                    continue
                if poll is not None:
                    incoming.append(poll)
                    fetch_state[source_url] = utc_now_iso()
                    state_changed = True
        finally:
            if browser is not None:
                await browser.close()

    if state_changed:
        _save_fetch_state(fetch_state)

    merged, new_count = deduplicate_by_id(document.polls, incoming)
    document.polls = merged
    if new_count > 0 or not POLLS_FILE.exists():
        save_polls_document(document)
    return new_count, len(sources), errors


def collect_polls() -> tuple[int, int, int]:
    logger.info("Starting poll collection via institute scraping...")
    return asyncio.run(collect_polls_async())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    new_count, source_count, error_count = collect_polls()
    print(
        f"Collected {new_count} new polls from {source_count} institutes ({error_count} errors)"
    )


if __name__ == "__main__":
    main()
