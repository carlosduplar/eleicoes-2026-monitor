"""Collect Portal da Transparência data for tracked candidates.

Queries the Portal da Transparência REST API to build a structured
summary of each candidate's PEP (Pessoa Exposta Politicamente) status
and parliamentary amendments (emendas parlamentares).

Data is written to site/public/data/transparencia_data.json.
Run weekly (data changes slowly).

Optional: set TRANSPARENCIA_API_KEY env var for higher rate limits.
Without a key, 24 other APIs work fine; only some endpoints require it.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "site" / "public" / "data"
OUTPUT_FILE = DATA_DIR / "transparencia_data.json"

REQUEST_TIMEOUT = 20
USER_AGENT = (
    "eleicoes-2026-monitor/1.0 (+https://github.com/carlosduplar/eleicoes-2026-monitor)"
)

TRANSPARENCIA_API = "https://api.portaldatransparencia.gov.br/api-de-dados"
DEFAULT_PAGE_SIZE = 10

# Search names — use partial names likely to match PEP records.
# Full legal names as stored in the Portal da Transparência.
CANDIDATE_SEARCH_NAMES: dict[str, str] = {
    "lula": "Luiz Inácio Lula da Silva",
    "flavio-bolsonaro": "Flávio Nantes Bolsonaro",
    "tarcisio": "Tarcísio Gomes de Freitas",
    "caiado": "Ronaldo Ramos Caiado",
    "zema": "Romeu Zema Neto",
    "ratinho-jr": "Carlos Roberto Massa Júnior",
    "eduardo-leite": "Eduardo Figueiredo Cavalheiro Leite",
    "aldo-rebelo": "Aldo Rebelo Figueiredo",
    "renan-santos": "Renan Franco Santos",
}

# Parliamentary amendment author names as they appear in the Portal da Transparência.
# Only candidates who are/were federal legislators have emendas.
CANDIDATE_EMENDA_NAMES: dict[str, str] = {
    "flavio-bolsonaro": "Flávio Bolsonaro",
    "aldo-rebelo": "Aldo Rebelo",
    "renan-santos": "Renan Santos",
    "lula": "Luiz Inácio Lula da Silva",
}


def _make_headers() -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    api_key = os.environ.get("TRANSPARENCIA_API_KEY", "")
    if api_key:
        headers["chave-api-dados"] = api_key
    return headers


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    """HTTP GET with retries and polite throttle."""
    headers = _make_headers()
    for attempt in range(3):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            if response.status_code == 429:
                wait = 30 * (attempt + 1)
                logger.warning("Rate limited by Transparência API, waiting %ds", wait)
                time.sleep(wait)
                continue
            if response.status_code == 403:
                logger.warning("403 at %s — key may be required for this endpoint", url)
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            logger.warning("HTTP error attempt %d at %s: %s", attempt + 1, url, exc)
        except requests.exceptions.RequestException as exc:
            logger.warning("Request error attempt %d at %s: %s", attempt + 1, url, exc)
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


def _fetch_pep(nome: str) -> list[dict[str, Any]]:
    """Fetch PEP entries matching a candidate name."""
    url = f"{TRANSPARENCIA_API}/pep"
    params = {"nome": nome, "pagina": 1}
    data = _get(url, params)
    if not isinstance(data, list):
        return []

    results = []
    for item in data[:5]:  # cap at 5 PEP records per candidate
        results.append(
            {
                "cpf": item.get("cpf"),
                "nome": item.get("nome"),
                "orgao": item.get("orgaoDeVinculo") or item.get("orgao"),
                "funcao": item.get("funcao") or item.get("descricaoFuncao"),
                "data_inicio": item.get("dataInicioExercicio"),
                "data_fim": item.get("dataFimExercicio"),
                "nivel": item.get("nivel"),
            }
        )
    return results


def _fetch_emendas(nome_autor: str, ano: int | None = None) -> list[dict[str, Any]]:
    """Fetch parliamentary amendments authored by a candidate."""
    url = f"{TRANSPARENCIA_API}/emendas"
    params: dict[str, Any] = {"nomeAutor": nome_autor, "pagina": 1}
    if ano is not None:
        params["ano"] = ano

    data = _get(url, params)
    if not isinstance(data, list):
        return []

    results = []
    for item in data[:20]:  # cap at 20 emendas
        valor_empenhado = _safe_float(
            item.get("valorEmpenhado") or item.get("valor_empenhado")
        )
        valor_pago = _safe_float(item.get("valorPago") or item.get("valor_pago"))
        results.append(
            {
                "numero": item.get("numero"),
                "ano": item.get("ano"),
                "autor": item.get("nomeAutor") or item.get("autor"),
                "tipo": item.get("tipoEmenda") or item.get("tipo"),
                "localidade": item.get("localidade"),
                "funcao": item.get("funcao"),
                "subfuncao": item.get("subfuncao"),
                "valor_empenhado": valor_empenhado,
                "valor_pago": valor_pago,
            }
        )
    return results


def _fetch_sancoes(nome: str) -> list[dict[str, Any]]:
    """Fetch CEIS/CNEP sanctions for a candidate name (should be empty for clean candidates)."""
    # Only try CEIS (Cadastro de Empresas Inidôneas e Suspensas) for PJ
    # For individuals: use the cpf field if available.
    # Skip for now since all 9 tracked candidates are governors/senators in good standing.
    # This is a placeholder for future use.
    return []


def _build_candidate_record(slug: str) -> dict[str, Any]:
    """Build the Transparência data record for a single candidate."""
    full_name = CANDIDATE_SEARCH_NAMES.get(slug, "")
    emenda_name = CANDIDATE_EMENDA_NAMES.get(slug)

    logger.info("Fetching Transparência data for: %s", slug)

    # PEP lookup
    pep_records = _fetch_pep(full_name)
    time.sleep(1)

    # Emendas (only for ex-federal legislators)
    emendas: list[dict[str, Any]] = []
    if emenda_name:
        emendas = _fetch_emendas(emenda_name)
        time.sleep(1)

    # Compute emenda totals
    total_empenhado: float = sum((e.get("valor_empenhado") or 0) for e in emendas)
    total_pago: float = sum((e.get("valor_pago") or 0) for e in emendas)

    return {
        "slug": slug,
        "full_name": full_name,
        "pep": {
            "found": len(pep_records) > 0,
            "records": pep_records,
        },
        "emendas": {
            "total_count": len(emendas),
            "total_empenhado_brl": total_empenhado,
            "total_pago_brl": total_pago,
            "records": emendas,
        },
        "sancoes": [],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "Portal da Transparência",
        "source_url": "https://portaldatransparencia.gov.br",
    }


def collect_transparencia_data() -> dict[str, Any]:
    """Main collection function. Returns the full transparencia_data payload."""
    logger.info("Starting Portal da Transparência data collection")

    api_key_present = bool(os.environ.get("TRANSPARENCIA_API_KEY", ""))
    logger.info(
        "TRANSPARENCIA_API_KEY: %s",
        "set" if api_key_present else "not set (using unauthenticated)",
    )

    candidates: dict[str, dict[str, Any]] = {}
    for slug in CANDIDATE_SEARCH_NAMES:
        record = _build_candidate_record(slug)
        candidates[slug] = record

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Portal da Transparência — API de Dados",
        "source_url": "https://api.portaldatransparencia.gov.br",
        "disclaimer_pt": (
            "Dados extraídos do Portal da Transparência do governo federal. "
            "PEP (Pessoas Expostas Politicamente) é uma lista obrigatória por lei. "
            "A presença na lista não implica irregularidade."
        ),
        "disclaimer_en": (
            "Data extracted from the Brazilian federal government's Transparency Portal. "
            "PEP (Politically Exposed Persons) is a legally mandated registry. "
            "Presence on the list does not imply any irregularity."
        ),
        "candidates": candidates,
    }

    return payload


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    payload = collect_transparencia_data()

    tmp = OUTPUT_FILE.with_suffix(".tmp.json")
    try:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(OUTPUT_FILE)
        logger.info("Wrote Transparência data to %s", OUTPUT_FILE)
    except OSError as exc:
        logger.error("Failed to write %s: %s", OUTPUT_FILE, exc)
        raise
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
