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
CANDIDATES_FILE = DATA_DIR / "candidates.json"

REQUEST_TIMEOUT = 20
USER_AGENT = (
    "eleicoes-2026-monitor/1.0 (+https://github.com/carlosduplar/eleicoes-2026-monitor)"
)

# TSE API base URLs
ELEICAO_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/eleicao"
CANDIDATURA_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/candidatura"
RESULTADOS_CDN = "https://resultados.tse.jus.br"

# 2022 election configuration
ANO_ELEICAO = 2022

# Election IDs for 2022
ELEICAO_2022_ID = 544  # 1st round presidential
ELEICAO_2022_MUNICIPIO = 1  # "Brasil" national code in TSE API
CARGO_PRESIDENTE = 1  # TSE cargo code for Presidente da Republica

# CDN identifiers for 2022 national presidential results
CDN_CICLO = "ele2022"
CDN_PADDED = "000544"
CDN_UNPADDED = "544"
CDN_CARGO_PRESIDENTE = "0001"

# TSE cargo codes
CARGO_GOVERNADOR = 3
CARGO_SENADOR = 5

# State codes for TSE API (IBGE codes)
STATE_CODES: dict[str, int] = {
    "AC": 12,
    "AL": 27,
    "AM": 13,
    "AP": 16,
    "BA": 29,
    "CE": 23,
    "DF": 53,
    "ES": 32,
    "GO": 52,
    "MA": 21,
    "MG": 31,
    "MS": 50,
    "MT": 51,
    "PA": 15,
    "PB": 25,
    "PE": 26,
    "PI": 22,
    "PR": 41,
    "RJ": 33,
    "RN": 24,
    "RO": 11,
    "RR": 14,
    "RS": 43,
    "SC": 42,
    "SE": 28,
    "SP": 35,
    "TO": 17,
}

# Map candidate slugs to their search names for the TSE API.
# Full legal names as registered with TSE in 2022.
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

# Candidate 2022 election context
# Maps candidate slug to their 2022 race details
CANDIDATE_2022_CONTEXT: dict[str, dict[str, Any]] = {
    "lula": {
        "cargo": CARGO_PRESIDENTE,
        "uf": "BR",
        "municipio": 1,
        "eleicao_id": 544,
        "nome_urna": "LULA",
        "numero": 13,
        "partido": "PT",
        "first_round_pct": "48.43",
        "second_round_pct": "50.90",
        "eleito": True,
    },
    "flavio-bolsonaro": {
        "cargo": CARGO_SENADOR,
        "uf": "RJ",
        "municipio": STATE_CODES["RJ"],  # Rio de Janeiro capital
        "eleicao_id": 546,  # State election
        "no_2022_race": False,
    },
    "tarcisio": {
        "cargo": CARGO_GOVERNADOR,
        "uf": "SP",
        "municipio": STATE_CODES["SP"],  # São Paulo capital
        "eleicao_id": 546,  # State election
        "no_2022_race": False,
    },
    "caiado": {
        "cargo": CARGO_GOVERNADOR,
        "uf": "GO",
        "municipio": STATE_CODES["GO"],  # Goiânia
        "eleicao_id": 546,  # State election
        "no_2022_race": False,
    },
    "zema": {
        "cargo": CARGO_GOVERNADOR,
        "uf": "MG",
        "municipio": STATE_CODES["MG"],  # Belo Horizonte
        "eleicao_id": 546,  # State election
        "no_2022_race": False,
    },
    "ratinho-jr": {
        "cargo": CARGO_GOVERNADOR,
        "uf": "PR",
        "municipio": STATE_CODES["PR"],  # Curitiba
        "eleicao_id": 546,  # State election
        "no_2022_race": False,
    },
    "eduardo-leite": {
        "cargo": CARGO_GOVERNADOR,
        "uf": "RS",
        "municipio": STATE_CODES["RS"],  # Porto Alegre
        "eleicao_id": 546,  # State election
        "no_2022_race": False,
    },
    "aldo-rebelo": {
        "no_2022_race": True,  # Did not run in 2022
    },
    "renan-santos": {
        "no_2022_race": True,  # Did not run in 2022
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
    context = CANDIDATE_2022_CONTEXT.get(slug, {})
    if context.get("cargo") != CARGO_PRESIDENTE:
        return {}

    numero = context.get("numero")
    if not numero:
        return {}

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


def _search_candidatura_list(
    ano: int,
    municipio: int,
    eleicao_id: int,
    cargo: int,
    nome_busca: str,
) -> dict[str, Any] | None:
    """Search candidatura list API for a candidate by name.

    Returns the matching candidate dict or None if not found.
    """
    url = f"{CANDIDATURA_API}/listar/{ano}/{municipio}/{eleicao_id}/{cargo}/candidatos"
    data = _get(url)
    if not isinstance(data, dict):
        return None

    nome_busca_lower = nome_busca.lower()
    for cand in data.get("candidatos", []):
        nome_completo = str(cand.get("nomeCompleto", "")).lower()
        nome_urna = str(cand.get("nomeUrna", "")).lower()
        if nome_busca_lower in nome_completo or nome_busca_lower in nome_urna:
            return cand

    return None


def _fetch_candidatura_detail(
    ano: int,
    uf: str,
    eleicao_id: int,
    sq_candidato: int,
) -> dict[str, Any] | None:
    """Fetch detailed candidate information from TSE API.

    Uses the candidatura/buscar endpoint to get full profile including
    photo URL, declared assets, ficha limpa status, etc.
    """
    url = f"{CANDIDATURA_API}/buscar/{ano}/{uf}/{eleicao_id}/{sq_candidato}"
    return _get(url)


def _extract_declared_assets(
    candidatura_detail: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract declared assets from candidatura detail response."""
    bens = candidatura_detail.get("bens", [])
    if not isinstance(bens, list) or not bens:
        return None

    total_value = 0.0
    asset_list = []

    for bem in bens:
        if not isinstance(bem, dict):
            continue
        descricao = bem.get("descricao", "").strip()
        valor = _safe_float(bem.get("valor"))
        tipo = bem.get("tipo", "").strip()

        if valor:
            total_value += valor
            asset_list.append(
                {
                    "description": descricao,
                    "value": valor,
                    "type": tipo,
                }
            )

    if not asset_list:
        return None

    return {
        "total_value": total_value,
        "currency": "BRL",
        "count": len(asset_list),
        "assets": asset_list[:10],  # Limit to top 10 assets
    }


def _extract_ficha_limpa_status(
    candidatura_detail: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract ficha limpa (clean record) status from candidatura detail."""
    # Check for electoral record status
    situacao_candidatura = candidatura_detail.get("situacaoCandidatura", {})
    if isinstance(situacao_candidatura, dict):
        codigo = situacao_candidatura.get("codigo")
        descricao = situacao_candidatura.get("descricao", "").strip()

        # Common codes for ficha limpa
        # 2 = Deferido (approved), 4 = Deferido com recurso
        is_clean = codigo in [2, 4] or "deferido" in descricao.lower()

        return {
            "is_clean": is_clean,
            "status_code": codigo,
            "status_description": descricao,
        }

    return None


def _build_tse_registration_url(
    ano: int,
    uf: str,
    eleicao_id: int,
    sq_candidato: int,
) -> str:
    """Build the TSE registration URL for a candidate."""
    return (
        f"https://divulgacandcontas.tse.jus.br/divulga/#/candidato/{ano}/{uf}/"
        f"{eleicao_id}/{sq_candidato}"
    )


def _check_photo_url(photo_url: str | None) -> str | None:
    """Check if photo URL is valid (returns 200)."""
    if not photo_url:
        return None

    try:
        response = requests.head(
            photo_url,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )
        if response.status_code == 200:
            return photo_url
        logger.debug("Photo URL returned %d: %s", response.status_code, photo_url)
    except requests.RequestException as exc:
        logger.debug("Photo URL check failed: %s - %s", photo_url, exc)

    return None


def _fetch_candidate_2022_data(slug: str) -> dict[str, Any]:
    """Fetch 2022 election data for a candidate from TSE API.

    Returns a dict with enriched candidate data including:
    - photo_url
    - declared_assets
    - ficha_limpa_status
    - tse_registration_url
    - sq_candidato (for donor lookup)
    """
    context = CANDIDATE_2022_CONTEXT.get(slug, {})

    # Handle candidates with no 2022 race
    if context.get("no_2022_race", False):
        return {
            "no_2022_race": True,
            "photo_url": None,
            "declared_assets": None,
            "ficha_limpa_status": None,
            "tse_registration_url": None,
            "sq_candidato": None,
        }

    cargo = context.get("cargo")
    uf = context.get("uf", "BR")
    municipio = context.get("municipio", 1)
    eleicao_id = context.get("eleicao_id", ELEICAO_2022_ID)
    full_name = CANDIDATE_FULL_NAMES.get(slug, "")

    if not cargo or not full_name:
        return {
            "no_2022_race": True,
            "photo_url": None,
            "declared_assets": None,
            "ficha_limpa_status": None,
            "tse_registration_url": None,
            "sq_candidato": None,
        }

    # Search for candidate in the list
    logger.info("Searching TSE candidatura for %s (%s)", slug, full_name)
    candidatura_list = _search_candidatura_list(
        ano=ANO_ELEICAO,
        municipio=municipio,
        eleicao_id=eleicao_id,
        cargo=cargo,
        nome_busca=full_name,
    )

    if not candidatura_list:
        logger.warning("Could not find candidatura for %s", slug)
        return {
            "no_2022_race": True,
            "photo_url": None,
            "declared_assets": None,
            "ficha_limpa_status": None,
            "tse_registration_url": None,
            "sq_candidato": None,
        }

    sq_candidato = candidatura_list.get("sqCandidato")
    if not sq_candidato:
        logger.warning("No sqCandidato found for %s", slug)
        return {
            "no_2022_race": True,
            "photo_url": None,
            "declared_assets": None,
            "ficha_limpa_status": None,
            "tse_registration_url": None,
            "sq_candidato": None,
        }

    # Fetch detailed candidatura data
    logger.info("Fetching candidatura detail for %s (sq: %s)", slug, sq_candidato)
    candidatura_detail = _fetch_candidatura_detail(
        ano=ANO_ELEICAO,
        uf=uf,
        eleicao_id=eleicao_id,
        sq_candidato=sq_candidato,
    )

    if not candidatura_detail:
        logger.warning("Could not fetch candidatura detail for %s", slug)
        return {
            "no_2022_race": False,
            "photo_url": None,
            "declared_assets": None,
            "ficha_limpa_status": None,
            "tse_registration_url": None,
            "sq_candidato": sq_candidato,
        }

    # Extract photo URL
    photo_url_raw = candidatura_detail.get("fotoUrl")
    photo_url = _check_photo_url(photo_url_raw)

    # Extract declared assets
    declared_assets = _extract_declared_assets(candidatura_detail)

    # Extract ficha limpa status
    ficha_limpa_status = _extract_ficha_limpa_status(candidatura_detail)

    # Build registration URL
    tse_registration_url = _build_tse_registration_url(
        ano=ANO_ELEICAO,
        uf=uf,
        eleicao_id=eleicao_id,
        sq_candidato=sq_candidato,
    )

    return {
        "no_2022_race": False,
        "photo_url": photo_url,
        "declared_assets": declared_assets,
        "ficha_limpa_status": ficha_limpa_status,
        "tse_registration_url": tse_registration_url,
        "sq_candidato": sq_candidato,
        "nome_urna": candidatura_detail.get("nomeUrna"),
        "numero": candidatura_detail.get("numero"),
        "partido": candidatura_detail.get("partido", {}).get("sigla"),
    }


def _build_candidate_record(slug: str) -> dict[str, Any]:
    """Build the TSE data record for a single candidate."""
    full_name = CANDIDATE_FULL_NAMES.get(slug, "")
    context = CANDIDATE_2022_CONTEXT.get(slug, {})

    record: dict[str, Any] = {
        "slug": slug,
        "full_name": full_name,
        "presidential_2022": None,
        "state_results_2022": {},
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "TSE DivulgaCandContas / CDN Resultados",
        "source_url": "https://divulgacandcontas.tse.jus.br",
    }

    # Add 2022 presidential data if applicable
    if context.get("cargo") == CARGO_PRESIDENTE:
        record["presidential_2022"] = {
            "nome_urna": context.get("nome_urna"),
            "numero": context.get("numero"),
            "partido": context.get("partido"),
            "first_round_pct": context.get("first_round_pct"),
            "second_round_pct": context.get("second_round_pct"),
            "eleito": context.get("eleito"),
        }

    # Fetch enriched TSE data
    tse_data = _fetch_candidate_2022_data(slug)

    # Add enriched fields
    record["photo_url"] = tse_data.get("photo_url")
    record["declared_assets"] = tse_data.get("declared_assets")
    record["ficha_limpa_status"] = tse_data.get("ficha_limpa_status")
    record["tse_registration_url"] = tse_data.get("tse_registration_url")
    record["sq_candidato"] = tse_data.get("sq_candidato")
    record["no_2022_race"] = tse_data.get("no_2022_race", False)

    # Fetch state results for presidential candidates
    if context.get("cargo") == CARGO_PRESIDENTE:
        record["state_results_2022"] = _fetch_state_results_2022(slug)

    return record


def _update_candidates_json(photo_updates: dict[str, str | None]) -> None:
    """Update candidates.json with photo URLs from TSE data."""
    if not CANDIDATES_FILE.exists():
        logger.warning("candidates.json not found, skipping photo sync")
        return

    try:
        data = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
        candidates = data.get("candidates", [])

        updated = False
        for candidate in candidates:
            slug = candidate.get("slug")
            if slug in photo_updates:
                photo_url = photo_updates[slug]
                if photo_url and photo_url != candidate.get("photo_url"):
                    candidate["photo_url"] = photo_url
                    candidate["tse_registration_url"] = photo_updates.get(f"{slug}_url")
                    updated = True
                    logger.info("Updated photo_url for %s", slug)

        if updated:
            # Atomic write
            tmp = CANDIDATES_FILE.with_suffix(".tmp.json")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(CANDIDATES_FILE)
            logger.info("Updated %s with photo URLs", CANDIDATES_FILE)

    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to update candidates.json: %s", exc)


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
    photo_updates: dict[str, str | None] = {}

    for slug in CANDIDATE_FULL_NAMES:
        logger.info("Processing TSE data for: %s", slug)
        record = _build_candidate_record(slug)
        candidates[slug] = record

        # Collect photo updates for candidates.json
        if record.get("photo_url"):
            photo_updates[slug] = record["photo_url"]
            photo_updates[f"{slug}_url"] = record.get("tse_registration_url")

        time.sleep(0.5)  # polite throttle between candidates

    # Update candidates.json with photo URLs
    _update_candidates_json(photo_updates)

    payload: dict[str, Any] = {
        "schema_version": "2.0.0",
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
