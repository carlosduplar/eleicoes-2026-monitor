"""Collect donor data for tracked candidates from TSE campaign finance records.

Queries the TSE DivulgaCandContas REST API for campaign finance data (receitas),
then enriches corporate donors (PJ) using BrasilAPI CNPJ lookups.

Data is written to site/public/data/donors.json.
Run weekly (data is historical and stable).

No API key required for TSE. BrasilAPI is also free and open.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
OUTPUT_FILE = DATA_DIR / "donors.json"
TSE_DATA_FILE = DATA_DIR / "tse_data.json"

REQUEST_TIMEOUT = 20
USER_AGENT = (
    "eleicoes-2026-monitor/1.0 (+https://github.com/carlosduplar/eleicoes-2026-monitor)"
)

# API base URLs
TSE_PRESTADOR_API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/prestador"
BRASIL_API_CNPJ = "https://brasilapi.com.br/api/cnpj/v1"

# 2022 election configuration
ANO_ELEICAO = 2022

# TSE prestador endpoint configuration
PRESTADOR_CONSULTA = "consulta"
PRESTADOR_RECEITAS = "receitas"

# Rate limiting
TSE_RATE_LIMIT_DELAY = 2  # seconds between TSE requests
BRASILAPI_RATE_LIMIT_DELAY = 0.5  # seconds between BrasilAPI requests


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


def _clean_cnpj(cnpj: str) -> str:
    """Remove non-numeric characters from CNPJ."""
    return re.sub(r"\D", "", cnpj)


def _is_valid_cnpj(cnpj: str) -> bool:
    """Check if CNPJ has 14 digits."""
    cleaned = _clean_cnpj(cnpj)
    return len(cleaned) == 14


def _mask_cpf(cpf: str) -> str:
    """Mask CPF for privacy (show only last 2 digits)."""
    cleaned = re.sub(r"\D", "", cpf)
    if len(cleaned) == 11:
        return f"***.{cleaned[3:6]}.{cleaned[6:9]}-**"
    return cpf


def _fetch_brasilapi_cnpj(cnpj: str) -> dict[str, Any] | None:
    """Fetch company data from BrasilAPI by CNPJ.

    Returns enriched company data including:
    - razao_social (company name)
    - cnae_fiscal (economic activity code)
    - cnae_fiscal_descricao (activity description)
    - porte (company size)
    - capital_social (share capital)
    - municipio, uf (location)
    - descricao_situacao_cadastral (registration status)
    """
    cleaned_cnpj = _clean_cnpj(cnpj)
    url = f"{BRASIL_API_CNPJ}/{cleaned_cnpj}"

    data = _get(url)
    if not data:
        return None

    return {
        "cnpj": cleaned_cnpj,
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia"),
        "cnae_fiscal": data.get("cnae_fiscal"),
        "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
        "porte": data.get("porte"),
        "capital_social": _safe_float(data.get("capital_social")),
        "municipio": data.get("municipio"),
        "uf": data.get("uf"),
        "situacao_cadastral": data.get("descricao_situacao_cadastral"),
        "natureza_juridica": data.get("natureza_juridica"),
        "data_inicio_atividade": data.get("data_inicio_atividade"),
    }


def _fetch_tse_receitas(
    sq_prestador: int,
    sq_candidato: int,
) -> list[dict[str, Any]]:
    """Fetch campaign donations (receitas) from TSE API.

    Uses the prestador/consulta endpoint to get donation records.
    """
    url = (
        f"{TSE_PRESTADOR_API}/{PRESTADOR_CONSULTA}/"
        f"{ANO_ELEICAO}/{sq_prestador}/{sq_candidato}"
    )

    data = _get(url)
    if not data:
        return []

    # The response structure varies; try common paths
    receitas = []

    # Try prestador -> receitas path
    prestador = data.get("prestador", {})
    if isinstance(prestador, dict):
        receitas_list = prestador.get("receitas", [])
        if isinstance(receitas_list, list):
            receitas.extend(receitas_list)

    # Try direct receitas path
    if not receitas:
        receitas_list = data.get("receitas", [])
        if isinstance(receitas_list, list):
            receitas.extend(receitas_list)

    # Try doacoes path
    if not receitas:
        doacoes = data.get("doacoes", [])
        if isinstance(doacoes, list):
            receitas.extend(doacoes)

    return receitas


def _parse_donation_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single donation record from TSE API.

    Returns standardized donation dict with:
    - donor_type: 'PF' (individual) or 'PJ' (corporate)
    - donor_name
    - donor_document (masked CPF or CNPJ)
    - amount
    - date
    - description
    """
    if not isinstance(record, dict):
        return None

    # Extract donor info
    doador = record.get("doador", {})
    if not isinstance(doador, dict):
        doador = {}

    # Determine donor type
    tipo_doador = record.get("tipoDoador") or doador.get("tipo")
    cnpj_cpf = record.get("cnpjCpfDoador") or doador.get("cnpjCpf")

    donor_type = None
    if tipo_doador:
        if tipo_doador in ["PF", "FISICA", "Física", 1, "1"]:
            donor_type = "PF"
        elif tipo_doador in ["PJ", "JURIDICA", "Jurídica", 2, "2"]:
            donor_type = "PJ"

    # Infer from document if type not explicit
    if not donor_type and cnpj_cpf:
        cleaned = _clean_cnpj(str(cnpj_cpf))
        if len(cleaned) == 11:
            donor_type = "PF"
        elif len(cleaned) == 14:
            donor_type = "PJ"

    if not donor_type:
        donor_type = "PF"  # Default to PF

    # Extract donor name
    donor_name = (
        record.get("nomeDoador")
        or doador.get("nome")
        or record.get("doadorNome")
        or "Desconhecido"
    )

    # Mask document
    donor_document = None
    if cnpj_cpf:
        if donor_type == "PF":
            donor_document = _mask_cpf(str(cnpj_cpf))
        else:
            donor_document = _clean_cnpj(str(cnpj_cpf))

    # Extract amount
    valor = _safe_float(
        record.get("valorReceita") or record.get("valor") or record.get("vrReceita")
    )

    # Extract date
    data = record.get("dataReceita") or record.get("data") or record.get("dtReceita")

    # Extract description
    descricao = (
        record.get("descricao")
        or record.get("especieRecurso")
        or record.get("fonteRecurso")
        or "Doação"
    )

    if not valor or valor <= 0:
        return None

    return {
        "donor_type": donor_type,
        "donor_name": donor_name.strip(),
        "donor_document": donor_document,
        "amount": valor,
        "date": data,
        "description": descricao.strip(),
        "raw_data": record,  # Keep raw for debugging
    }


def _enrich_pj_donor(donation: dict[str, Any]) -> dict[str, Any]:
    """Enrich a corporate donor with BrasilAPI data."""
    if donation.get("donor_type") != "PJ":
        return donation

    cnpj = donation.get("donor_document")
    if not cnpj or not _is_valid_cnpj(cnpj):
        return donation

    logger.info("Enriching PJ donor: %s", cnpj[:8] + "...")
    company_data = _fetch_brasilapi_cnpj(cnpj)

    if company_data:
        donation["company_data"] = company_data
        time.sleep(BRASILAPI_RATE_LIMIT_DELAY)

    return donation


def _aggregate_by_sector(donations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate corporate donations by economic sector (CNAE)."""
    sector_totals: dict[str, dict[str, Any]] = {}

    for donation in donations:
        if donation.get("donor_type") != "PJ":
            continue

        company_data = donation.get("company_data", {})
        cnae_desc = company_data.get("cnae_fiscal_descricao", "Setor não identificado")
        cnae_code = company_data.get("cnae_fiscal", "0000000")

        sector_key = f"{cnae_code[:2]}"  # Use CNAE division (first 2 digits)

        if sector_key not in sector_totals:
            sector_totals[sector_key] = {
                "sector_code": sector_key,
                "sector_name": cnae_desc.split("-")[0].strip()
                if "-" in cnae_desc
                else cnae_desc,
                "total_amount": 0.0,
                "donor_count": 0,
                "donors": [],
            }

        sector_totals[sector_key]["total_amount"] += donation.get("amount", 0)
        sector_totals[sector_key]["donor_count"] += 1

        # Add donor to list (limit to avoid huge arrays)
        if len(sector_totals[sector_key]["donors"]) < 5:
            sector_totals[sector_key]["donors"].append(
                {
                    "name": donation.get("donor_name"),
                    "cnpj": donation.get("donor_document"),
                    "amount": donation.get("amount"),
                }
            )

    # Sort by total amount
    sorted_sectors = sorted(
        sector_totals.values(),
        key=lambda x: x["total_amount"],
        reverse=True,
    )

    return {
        "sectors": sorted_sectors,
        "total_sectors": len(sorted_sectors),
        "total_pj_amount": sum(s["total_amount"] for s in sorted_sectors),
    }


def _collect_candidate_donors(
    slug: str,
    sq_candidato: int | None,
    sq_prestador: int | None,
) -> dict[str, Any]:
    """Collect and process donor data for a single candidate."""
    result: dict[str, Any] = {
        "slug": slug,
        "sq_candidato": sq_candidato,
        "sq_prestador": sq_prestador,
        "donations": [],
        "summary": {
            "total_donations": 0,
            "total_amount": 0.0,
            "pf_count": 0,
            "pf_amount": 0.0,
            "pj_count": 0,
            "pj_amount": 0.0,
        },
        "sector_breakdown": None,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    if not sq_candidato or not sq_prestador:
        logger.info("No TSE IDs for %s, skipping donor collection", slug)
        result["error"] = "Missing TSE candidate/prestador IDs"
        return result

    logger.info("Fetching donors for %s (sq: %s)", slug, sq_candidato)

    # Fetch donations from TSE
    receitas = _fetch_tse_receitas(sq_prestador, sq_candidato)
    time.sleep(TSE_RATE_LIMIT_DELAY)

    if not receitas:
        logger.info("No donation data found for %s", slug)
        result["error"] = "No donation data available"
        return result

    logger.info("Found %d raw donation records for %s", len(receitas), slug)

    # Parse and enrich donations
    parsed_donations = []
    for record in receitas:
        parsed = _parse_donation_record(record)
        if parsed:
            # Enrich PJ donors with BrasilAPI
            if parsed.get("donor_type") == "PJ":
                parsed = _enrich_pj_donor(parsed)
            parsed_donations.append(parsed)

    result["donations"] = parsed_donations

    # Calculate summary
    total_amount = 0.0
    pf_count = 0
    pf_amount = 0.0
    pj_count = 0
    pj_amount = 0.0

    for donation in parsed_donations:
        amount = donation.get("amount", 0)
        total_amount += amount

        if donation.get("donor_type") == "PF":
            pf_count += 1
            pf_amount += amount
        else:
            pj_count += 1
            pj_amount += amount

    result["summary"] = {
        "total_donations": len(parsed_donations),
        "total_amount": round(total_amount, 2),
        "pf_count": pf_count,
        "pf_amount": round(pf_amount, 2),
        "pj_count": pj_count,
        "pj_amount": round(pj_amount, 2),
    }

    # Sector breakdown for PJ donors
    if pj_count > 0:
        result["sector_breakdown"] = _aggregate_by_sector(parsed_donations)

    return result


def _load_tse_data() -> dict[str, Any]:
    """Load TSE data to get candidate IDs."""
    if not TSE_DATA_FILE.exists():
        logger.error("tse_data.json not found. Run collect_tse.py first.")
        return {}

    try:
        data = json.loads(TSE_DATA_FILE.read_text(encoding="utf-8"))
        return data.get("candidates", {})
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load tse_data.json: %s", exc)
        return {}


def collect_donor_data() -> dict[str, Any]:
    """Main collection function. Returns the full donors payload."""
    logger.info("Starting donor data collection")

    # Load TSE data to get candidate IDs
    tse_candidates = _load_tse_data()
    if not tse_candidates:
        logger.error("No TSE candidate data available")
        return {
            "schema_version": "1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "TSE DivulgaCandContas + BrasilAPI",
            "source_url": "https://divulgacandcontas.tse.jus.br",
            "disclaimer_pt": "Dados de financiamento de campanha 2022.",
            "disclaimer_en": "2022 campaign finance data.",
            "candidates": {},
            "error": "No TSE candidate data available",
        }

    # Collect donor data for each candidate
    candidates_donors: dict[str, Any] = {}

    for slug, candidate_data in tse_candidates.items():
        # Skip candidates with no 2022 race
        if candidate_data.get("no_2022_race", False):
            logger.info("Skipping %s (no 2022 race)", slug)
            candidates_donors[slug] = {
                "slug": slug,
                "sq_candidato": None,
                "sq_prestador": None,
                "donations": [],
                "summary": {
                    "total_donations": 0,
                    "total_amount": 0.0,
                    "pf_count": 0,
                    "pf_amount": 0.0,
                    "pj_count": 0,
                    "pj_amount": 0.0,
                },
                "sector_breakdown": None,
                "no_2022_race": True,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
            continue

        sq_candidato = candidate_data.get("sq_candidato")
        # sq_prestador is usually the same as sq_candidato for candidates
        sq_prestador = sq_candidato

        donor_data = _collect_candidate_donors(slug, sq_candidato, sq_prestador)
        candidates_donors[slug] = donor_data

    # Calculate global aggregates
    total_donations = sum(
        c.get("summary", {}).get("total_donations", 0)
        for c in candidates_donors.values()
    )
    total_amount = sum(
        c.get("summary", {}).get("total_amount", 0) for c in candidates_donors.values()
    )

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "TSE DivulgaCandContas REST API + BrasilAPI",
        "source_url": "https://divulgacandcontas.tse.jus.br",
        "disclaimer_pt": (
            "Dados de financiamento de campanha das eleições 2022. "
            "Doações de pessoas jurídicas foram proibidas pelo STF (ADI 4650) em 2016, "
            "mas podem existir registros históricos ou doações via fundo partidário."
        ),
        "disclaimer_en": (
            "2022 campaign finance data. "
            "Corporate donations were banned by the Brazilian Supreme Court (ADI 4650) in 2016, "
            "but historical records or party fund donations may exist."
        ),
        "election_year": ANO_ELEICAO,
        "total_candidates": len(candidates_donors),
        "total_donations": total_donations,
        "total_amount": round(total_amount, 2),
        "candidates": candidates_donors,
    }

    return payload


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    payload = collect_donor_data()

    tmp = OUTPUT_FILE.with_suffix(".tmp.json")
    try:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(OUTPUT_FILE)
        logger.info("Wrote donor data to %s", OUTPUT_FILE)
    except OSError as exc:
        logger.error("Failed to write %s: %s", OUTPUT_FILE, exc)
        raise
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
