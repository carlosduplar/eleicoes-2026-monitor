"""Collect TSE election data for tracked candidates.

Queries the TSE DivulgaCandContas REST API and the TSE CDN results files
to build a structured summary of each candidate's 2022 electoral history,
campaign finance, and registration status.

Data is written to site/public/data/tse_data.json.
Run weekly (data is historical and stable).

No API key required.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
OUTPUT_FILE = DATA_DIR / "tse_data.json"

REQUEST_TIMEOUT = 20
USER_AGENT = (
    "eleicoes-2026-monitor/1.0 (+https://github.com/carlosduplar/eleicoes-2026-monitor)"
)

# TSE API base URLs
ELEICAO_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/eleicao"
CANDIDATURA_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura"
RESULTADOS_CDN = "https://resultados.tse.jus.br"

# 2022 presidential election
# Obtained from TSE API: GET /eleicao/ordinarias -> find 2022 federal
ELEICAO_2022_ID = 544  # 1st round presidential
ELEICAO_2022_MUNICIPIO = 1  # "Brasil" national code in TSE API
CARGO_PRESIDENTE = 1  # TSE cargo code for Presidente da Republica

# CDN identifiers for 2022 national presidential results
CDN_CICLO = "ele2022"
CDN_PADDED = "000544"
CDN_UNPADDED = "544"
CDN_CARGO_PRESIDENTE = "0001"

# Map candidate slugs to their search names for the TSE API.
# Full legal names as registered with TSE in 2022.
# NOTE: Most 2026 candidates were not presidential candidates in 2022 —
# only Lula and Jair Bolsonaro ran (Flávio was not on the ballot).
# We collect 2022 national results for context and search each candidate
# in the candidatura API by name to find their legislative registrations.
CANDIDATE_FULL_NAMES: dict[str, str] = {
    "lula": "Luiz Inácio Lula da Silva",
    "flavio-bolsonaro": "Flávio Nantes Bolsonaro",
    "tarcisio": "Tarcísio Gomes de Freitas",
    "caiado": "Ronaldo Ramos Caiado",
    "zema": "Romeu Zema Neto",
    "ratinho-jr": "Carlos Roberto Massa Júnior",
    "eduardo-leite": "Eduardo Figueiredo Cavalheiro Leite",
    "aldo-rebelo": "José Aldo Rebelo Figueiredo",
    "renan-santos": "Renan Franco Santos",
}

# Candidates who ran for president in 2022 with their 2022 election IDs.
# Lula ran under election 544 (1st round) and 545 (2nd round).
PRESIDENTIAL_CANDIDATES_2022: dict[str, dict[str, Any]] = {
    "lula": {
        "nome_urna": "LULA",
        "numero": 13,
        "partido": "PT",
        "first_round_pct": "48.43",
        "second_round_pct": "50.90",
        "eleito": True,
    },
}


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    """HTTP GET with retries."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for attempt in range(3):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                logger.debug("404 at %s", url)
                return None
            logger.warning(
                "HTTP error attempt %d fetching %s: %s", attempt + 1, url, exc
            )
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Request error attempt %d fetching %s: %s", attempt + 1, url, exc
            )
        if attempt < 2:
            time.sleep(2**attempt)
    return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _fetch_national_result_2022() -> dict[str, Any] | None:
    """Fetch 2022 presidential first-round national results from TSE CDN."""
    uf = "br"
    url = (
        f"{RESULTADOS_CDN}/{CDN_CICLO}/{CDN_UNPADDED}/"
        f"dados-simplificados/{uf}/{uf}-c{CDN_CARGO_PRESIDENTE}-e{CDN_PADDED}-r.json"
    )
    data = _get(url)
    if not isinstance(data, dict) or "cand" not in data:
        logger.warning("Could not fetch 2022 national presidential results from CDN")
        return None
    return data


def _parse_national_result(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse candidates from CDN result JSON into a clean list."""
    candidates = []
    for cand in data.get("cand", []):
        candidates.append(
            {
                "nome": cand.get("nm", "").strip(),
                "numero": _safe_int(cand.get("n")),
                "votos": _safe_int(cand.get("vap")),
                "percentual": cand.get("pvap"),
                "eleito": cand.get("e") == "s",
                "situacao": cand.get("st"),
            }
        )
    candidates.sort(key=lambda c: c.get("votos") or 0, reverse=True)
    return candidates


def _fetch_state_results_2022(slug: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch 2022 first-round presidential results per state for a specific candidate.

    Returns a dict of uf -> result_entry for the given candidate number.
    Only included if candidate was a presidential candidate in 2022.
    """
    if slug not in PRESIDENTIAL_CANDIDATES_2022:
        return {}

    cand_info = PRESIDENTIAL_CANDIDATES_2022[slug]
    numero = cand_info["numero"]

    ufs = [
        "ac",
        "al",
        "am",
        "ap",
        "ba",
        "ce",
        "df",
        "es",
        "go",
        "ma",
        "mg",
        "ms",
        "mt",
        "pa",
        "pb",
        "pe",
        "pi",
        "pr",
        "rj",
        "rn",
        "ro",
        "rr",
        "rs",
        "sc",
        "se",
        "sp",
        "to",
    ]

    state_results: dict[str, dict[str, Any]] = {}
    for uf in ufs:
        url = (
            f"{RESULTADOS_CDN}/{CDN_CICLO}/{CDN_UNPADDED}/"
            f"dados-simplificados/{uf}/{uf}-c{CDN_CARGO_PRESIDENTE}-e{CDN_PADDED}-r.json"
        )
        data = _get(url)
        if not isinstance(data, dict) or "cand" not in data:
            continue

        for cand in data.get("cand", []):
            if _safe_int(cand.get("n")) == numero:
                state_results[uf.upper()] = {
                    "votos": _safe_int(cand.get("vap")),
                    "percentual": cand.get("pvap"),
                    "eleito": cand.get("e") == "s",
                }
                break

        time.sleep(0.05)  # polite throttle

    return state_results


def _fetch_candidatura_search(
    nome: str,
    ano: int,
    municipio: int,
    eleicao_id: int,
    cargo: int,
) -> dict[str, Any] | None:
    """Search candidatura API for a candidate by election context."""
    url = f"{CANDIDATURA_API}/listar/{ano}/{municipio}/{eleicao_id}/{cargo}/candidatos"
    data = _get(url)
    if not isinstance(data, dict):
        return None

    nome_lower = nome.lower()
    for cand in data.get("candidatos", []):
        nome_completo = str(cand.get("nomeCompleto", "")).lower()
        nome_urna = str(cand.get("nomeUrna", "")).lower()
        if nome_lower in nome_completo or nome_lower in nome_urna:
            return cand

    return None


def _build_candidate_record(slug: str) -> dict[str, Any]:
    """Build the TSE data record for a single candidate."""
    full_name = CANDIDATE_FULL_NAMES.get(slug, "")

    record: dict[str, Any] = {
        "slug": slug,
        "full_name": full_name,
        "presidential_2022": None,
        "state_results_2022": {},
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "TSE DivulgaCandContas / CDN Resultados",
        "source_url": "https://divulgacandcontas.tse.jus.br",
    }

    if slug in PRESIDENTIAL_CANDIDATES_2022:
        info = PRESIDENTIAL_CANDIDATES_2022[slug]
        record["presidential_2022"] = {
            "nome_urna": info["nome_urna"],
            "numero": info["numero"],
            "partido": info["partido"],
            "first_round_pct": info["first_round_pct"],
            "second_round_pct": info.get("second_round_pct"),
            "eleito": info["eleito"],
        }

    return record


def collect_tse_data() -> dict[str, Any]:
    """Main collection function. Returns the full tse_data payload."""
    logger.info("Starting TSE data collection")

    # Fetch 2022 national results for context
    national_raw = _fetch_national_result_2022()
    national_results: list[dict[str, Any]] = []
    if national_raw:
        national_results = _parse_national_result(national_raw)
        logger.info(
            "Fetched 2022 national results: %d candidates", len(national_results)
        )
    else:
        logger.warning("National 2022 results unavailable, using empty list")

    # Build per-candidate records
    candidates: dict[str, dict[str, Any]] = {}
    for slug in CANDIDATE_FULL_NAMES:
        logger.info("Processing TSE data for: %s", slug)
        record = _build_candidate_record(slug)
        candidates[slug] = record
        time.sleep(0.1)

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "TSE DivulgaCandContas REST API + CDN Resultados",
        "source_url": "https://divulgacandcontas.tse.jus.br",
        "disclaimer_pt": (
            "Dados históricos de eleições anteriores (2022). "
            "Registro oficial das candidaturas 2026 estará disponível após o TSE abrir o período."
        ),
        "disclaimer_en": (
            "Historical data from previous elections (2022). "
            "Official 2026 candidacy registration will be available after TSE opens the filing period."
        ),
        "national_results_2022": {
            "election": "Presidente da República — 1.º Turno (2022-10-02)",
            "election_id": ELEICAO_2022_ID,
            "total_candidates": len(national_results),
            "candidates": national_results,
        },
        "candidates": candidates,
    }

    return payload


def _load_existing() -> dict[str, Any] | None:
    """Load existing tse_data.json if it exists."""
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    payload = collect_tse_data()

    tmp = OUTPUT_FILE.with_suffix(".tmp.json")
    try:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(OUTPUT_FILE)
        logger.info("Wrote TSE data to %s", OUTPUT_FILE)
    except OSError as exc:
        logger.error("Failed to write %s: %s", OUTPUT_FILE, exc)
        raise
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
