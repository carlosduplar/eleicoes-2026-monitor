"""Seed the candidates positions knowledge base from structured public sources.

Fetches baseline data from Wikipedia PT, Câmara dos Deputados, and Senado
Federal APIs, then uses AI synthesis to fill entries currently marked "unknown".
Idempotent: never overwrites entries already reviewed by a human editor.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import requests

from .ai_client import extract_candidate_topic_position

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
POSITIONS_FILE = ROOT_DIR / "site" / "public" / "data" / "candidates_positions.json"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"

WIKIPEDIA_API_BASE = "https://pt.wikipedia.org/w/api.php"
CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"

CANDIDATE_WIKI_TITLES: dict[str, str] = {
    "lula": "Luiz_Inácio_Lula_da_Silva",
    "flavio-bolsonaro": "Flávio_Bolsonaro",
    "tarcisio": "Tarcísio_de_Freitas",
    "caiado": "Ronaldo_Caiado",
    "zema": "Romeu_Zema",
    "ratinho-jr": "Ratinho_Junior",
    "eduardo-leite": "Eduardo_Leite_(político)",
    "aldo-rebelo": "Aldo_Rebelo",
    "renan-santos": "Renan_Santos_(político)",
}

CAMARA_DEPUTADOS_NAMES: dict[str, str] = {
    "flavio-bolsonaro": "Flávio Bolsonaro",
    "aldo-rebelo": "Aldo Rebelo",
}

CANDIDATE_FULL_NAMES: dict[str, str] = {
    "lula": "Luiz Inácio Lula da Silva",
    "flavio-bolsonaro": "Flávio Bolsonaro",
    "tarcisio": "Tarcísio de Freitas",
    "caiado": "Ronaldo Caiado",
    "zema": "Romeu Zema",
    "ratinho-jr": "Ratinho Junior",
    "eduardo-leite": "Eduardo Leite",
    "aldo-rebelo": "Aldo Rebelo",
    "renan-santos": "Renan Santos",
}

# ── Source E: Party Ideological Profiles ────────────────────────────────

PARTY_IDEOLOGICAL_PROFILES: dict[str, dict[str, str]] = {
    "lula": {
        "armas": "PT: contrário ao porte de armas pela população civil. Histórico de restrição ao acesso a armas de fogo.",
        "meio_ambiente": "PT: defesa do meio ambiente, reativação do IBAMA, Fundo Amazônia, redução do desmatamento na Amazônia.",
        "lgbtq": "PT: favorável aos direitos LGBTQ+, criminalização da homofobia, reconhecimento da identidade de gênero.",
        "aborto": "PT: debate interno; posição oficial evita liberalização ampla, mas defende descriminalização em casos específicos.",
        "previdencia": "PT: contrário à reforma da previdência aprovada em 2019. Defende correção de distorções.",
        "impostos": "PT: defende progressividade fiscal, tributação de grandes fortunas, revisão de isenções para mais ricos.",
        "midia": "PT: favorável à regulação de plataformas digitais, combate à desinformação.",
        "indigenas": "PT: favorável à demarcação de terras indígenas, contrário ao marco temporal.",
        "educacao": "PT: defesa da educação pública, universidades federais, Prouni e Fies.",
        "seguranca": "PT: prioriza políticas sociais e prevenção; crítico de abordagens puramente repressivas.",
        "corrupcao": "PT: defende independência das instituições de controle, Lava Jato controverso no contexto do partido.",
    },
    "flavio-bolsonaro": {
        "armas": "PL/alinhamento bolsonarista: favorável à flexibilização do acesso a armas de fogo e munições.",
        "meio_ambiente": "PL: crítico de restrições ambientais; defende flexibilização do licenciamento ambiental.",
        "lgbtq": "PL: postura conservadora; contrário a políticas de identidade de gênero nas escolas.",
        "aborto": "PL: contrário ao aborto em qualquer circunstância; defende vida desde a concepção.",
        "previdencia": "PL: apoiou reforma da previdência de 2019.",
        "impostos": "PL: defende redução de impostos, simplificação tributária.",
        "midia": "PL: crítico à regulação de redes sociais; defende liberdade de expressão ampla.",
        "indigenas": "PL: favorável ao marco temporal para demarcação de terras indígenas.",
        "educacao": "PL: defende escola sem partido, contrário a conteúdo ideológico nas escolas.",
        "seguranca": "PL: favorável ao endurecimento de penas, excludente de ilicitude para policiais.",
        "corrupcao": "PL: defende Lava Jato, punição de crimes de corrupção, transparência.",
    },
    "tarcisio": {
        "armas": "Republicanos/alinhamento bolsonarista: favorável à flexibilização do acesso a armas de fogo.",
        "meio_ambiente": "Republicanos: crítico do licenciamento ambiental. Defende revisão das restrições ao desmatamento.",
        "lgbtq": "Republicanos: postura conservadora em pautas identitárias.",
        "aborto": "Republicanos: contrário ao aborto; posição alinhada ao conservadorismo religioso.",
        "previdencia": "Republicanos: apoiou reforma da previdência; defende sustentabilidade fiscal.",
        "impostos": "Republicanos: defende desonerações, redução de burocracia fiscal.",
        "midia": "Republicanos: crítico à censura digital; defende liberdade de expressão.",
        "indigenas": "Republicanos: favorável ao marco temporal, defende segurança jurídica para propriedade rural.",
        "educacao": "Republicanos: defende escola sem partido, incentivo ao ensino técnico.",
        "seguranca": "Republicanos: linha dura em segurança pública, fortalecimento policial.",
        "corrupcao": "Republicanos: discurso anticorrupção, apoio ao Lava Jato.",
    },
    "caiado": {
        "armas": "União Brasil: favorável ao porte de armas; discurso alinhado ao agronegócio e à segurança rural.",
        "meio_ambiente": "União Brasil: defende o agronegócio; posição crítica a restrições ambientais excessivas.",
        "lgbtq": "União Brasil: postura conservadora; contrário a políticas de identidade de gênero.",
        "aborto": "União Brasil: contrário ao aborto; defende vida desde a concepção.",
        "previdencia": "União Brasil: apoiou reforma da previdência de 2019.",
        "impostos": "União Brasil: defende reforma tributária com simplificação e redução de carga.",
        "midia": "União Brasil: contrário à censura de redes sociais.",
        "indigenas": "União Brasil: favorável ao marco temporal; defende segurança jurídica da propriedade rural.",
        "educacao": "União Brasil: defende educação de qualidade, ensino técnico e profissional.",
        "seguranca": "União Brasil: linha dura, endurecimento de penas e fortalecimento policial.",
        "corrupcao": "União Brasil: discurso anticorrupção, transparência pública.",
    },
    "zema": {
        "armas": "Novo: defende direito individual ao porte de armas.",
        "meio_ambiente": "Novo: crítico de regulações excessivas; defende equilíbrio entre preservação e desenvolvimento econômico.",
        "lgbtq": "Novo: posição liberal em costumes; menos ativista que partidos de esquerda.",
        "aborto": "Novo: posição conservadora predominante no partido.",
        "previdencia": "Novo: apoiou reforma da previdência; defende sustentabilidade do sistema.",
        "impostos": "Novo: defende redução drástica da carga tributária e do Estado.",
        "midia": "Novo: contrário à regulação estatal de mídias; defende livre mercado.",
        "indigenas": "Novo: favorável ao marco temporal; defende propriedade privada.",
        "educacao": "Novo: defende vouchers educacionais, concorrência entre escolas, menos intervenção estatal.",
        "seguranca": "Novo: defende endurecimento de penas e menos burocracia para forças de segurança.",
        "corrupcao": "Novo: forte discurso anticorrupção, transparência e accountability.",
    },
    "ratinho-jr": {
        "armas": "PSD: posição moderada; não é ponta de lança na pauta de armas.",
        "meio_ambiente": "PSD: defende equilíbrio entre desenvolvimento e preservação ambiental.",
        "lgbtq": "PSD: posição pragmática; sem posicionamento ideológico forte.",
        "aborto": "PSD: conservador no tema; segue o mainstream evangélico/católico.",
        "previdencia": "PSD: apoiou reforma da previdência; foco em equilíbrio fiscal.",
        "impostos": "PSD: defende reforma tributária e redução de burocracia.",
        "midia": "PSD: posição moderada sobre regulação de plataformas.",
        "indigenas": "PSD: pragmático; sem posição extrema no tema.",
        "educacao": "PSD: defende educação de qualidade, investimentos em infraestrutura escolar.",
        "seguranca": "PSD: defende segurança pública robusta, valorização policial.",
        "corrupcao": "PSD: discurso anticorrupção; defende transparência na gestão pública.",
    },
    "eduardo-leite": {
        "armas": "PSDB: moderado; defende controle de armas, não liberalização ampla.",
        "meio_ambiente": "PSDB: defende políticas ambientais responsáveis e agenda climática.",
        "lgbtq": "PSDB: favorável aos direitos LGBTQ+; primeiro governador assumidamente gay do Brasil.",
        "aborto": "PSDB: posição moderada; reconhece direitos das mulheres em casos extremos.",
        "previdencia": "PSDB: apoiou reforma da previdência; foco em sustentabilidade.",
        "impostos": "PSDB: defende reforma tributária, simplificação e racionalidade fiscal.",
        "midia": "PSDB: favorável a regulação responsável de plataformas digitais.",
        "indigenas": "PSDB: posição equilibrada; defende diálogo e segurança jurídica.",
        "educacao": "PSDB: forte defensor da educação pública de qualidade; histórico reformista.",
        "seguranca": "PSDB: defende políticas integradas de segurança e prevenção.",
        "corrupcao": "PSDB: forte discurso anticorrupção; defende independência do Ministério Público.",
    },
    "aldo-rebelo": {
        "armas": "PDT/posição própria: moderado; não é defensor ativo da liberalização de armas.",
        "meio_ambiente": "PDT: posição crítica ao ambientalismo excessivo; defende soberania nacional sobre Amazônia.",
        "lgbtq": "PDT: posição moderada; defende direitos civis sem ativismo de gênero.",
        "aborto": "PDT: posição conservadora; contrário à liberalização ampla do aborto.",
        "previdencia": "PDT: contrário à reforma da previdência de 2019 na forma aprovada.",
        "impostos": "PDT: defende tributação progressiva, combate às desigualdades fiscais.",
        "midia": "PDT: favorável à regulação de plataformas para combater desinformação.",
        "indigenas": "PDT: defende soberania nacional; visão desenvolvimentista com proteção indígena.",
        "educacao": "PDT: forte defensor da educação pública, universidades e pesquisa.",
        "seguranca": "PDT: defende políticas sociais combinadas com segurança pública.",
        "corrupcao": "PDT: discurso anticorrupção; defende transparência institucional.",
    },
    "renan-santos": {
        "armas": "MBL/Novo: favorável à liberalização do porte de armas.",
        "meio_ambiente": "MBL: crítico do ambientalismo político; defende desenvolvimento econômico.",
        "lgbtq": "MBL: contrário a políticas identitárias; defende liberdade individual sem ativismo estatal.",
        "aborto": "MBL: posição conservadora; contrário ao aborto.",
        "previdencia": "MBL: favorável à reforma e privatização parcial da previdência.",
        "impostos": "MBL: defende redução radical de impostos e do Estado.",
        "midia": "MBL: fortemente contrário à regulação de plataformas; defende liberdade de expressão irrestrita.",
        "indigenas": "MBL: favorável ao marco temporal; defende propriedade privada e produção agropecuária.",
        "educacao": "MBL: defende escola sem partido, vouchers educacionais, competição.",
        "seguranca": "MBL: linha dura; defende endurecimento de penas e armamento civil.",
        "corrupcao": "MBL: forte discurso anticorrupção; origem no movimento contra o PT.",
    },
}

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "armas": ["arma", "fogo", "munição", "porte"],
    "meio_ambiente": [
        "meio ambiente",
        "floresta",
        "desmatamento",
        "licenciamento ambiental",
    ],
    "lgbtq": ["lgbtq", "homofobia", "identidade de gênero"],
    "aborto": ["aborto", "gestação", "interrupção"],
    "previdencia": ["previdência", "aposentadoria", "pensão"],
    "impostos": ["imposto", "tributário", "reforma fiscal", "ir "],
    "midia": ["plataforma", "fake news", "desinformação", "regulação de mídia"],
    "indigenas": ["indígena", "marco temporal", "demarcação"],
    "educacao": ["educação", "ensino", "escola"],
    "seguranca": ["segurança pública", "polícia", "crime", "drogas"],
    "corrupcao": ["corrupção", "improbidade", "lava jato", "anticorrupção"],
}


def _http_get_json(url: str, timeout: int = 30) -> Any:
    """Make an HTTP GET request and return parsed JSON. Returns None on failure."""
    headers = {"User-Agent": "EleicoesMonitor/1.0", "Accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
        logger.warning("HTTP GET failed for %s: %s", url, exc)
        return None


def _normalize_optional_text(value: object) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return None


# ── Source A: Wikipedia PT ──────────────────────────────────────────────


def _fetch_wikipedia_sections(wiki_title: str) -> list[dict[str, str]]:
    """Fetch relevant sections from a Wikipedia article.

    Returns a list of dicts with keys 'section_title' and 'text'.
    """
    parse_url = (
        f"{WIKIPEDIA_API_BASE}?action=parse&page={urllib.parse.quote(wiki_title)}"
        f"&prop=sections&format=json"
    )
    data = _http_get_json(parse_url)
    if not data:
        return []

    sections = data.get("parse", {}).get("sections", [])
    if not isinstance(sections, list):
        return []

    relevant_keywords = [
        "político",
        "posição",
        "governo",
        "mandato",
        "carreira",
        "política",
        "posicionamento",
        "ideologia",
        "posições",
        "biografia",
        "trajetória",
        "vida pública",
    ]

    relevant_indices: list[int] = []
    for sec in sections:
        toclevel = sec.get("toclevel", 0)
        line = sec.get("line", "").lower()
        index = sec.get("index")
        if toclevel <= 2 and any(kw in line for kw in relevant_keywords):
            if index is not None:
                relevant_indices.append(int(index))

    snippets: list[dict[str, str]] = []
    for idx in relevant_indices[:5]:  # Limit to 5 sections to avoid rate limiting
        wikitext_url = (
            f"{WIKIPEDIA_API_BASE}?action=parse&page={urllib.parse.quote(wiki_title)}"
            f"&prop=wikitext&section={idx}&format=json"
        )
        sec_data = _http_get_json(wikitext_url)
        if not sec_data:
            continue
        wikitext_obj = sec_data.get("parse", {}).get("wikitext", {})
        wikitext = wikitext_obj.get("*", "") if isinstance(wikitext_obj, dict) else ""
        if not wikitext:
            continue
        # Strip basic wikitext markup
        clean = re.sub(r"\{\{[^}]*\}\}", "", wikitext)
        clean = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", clean)
        clean = re.sub(r"<ref[^>]*>.*?</ref>", "", clean, flags=re.DOTALL)
        clean = re.sub(r"<ref[^>]*/?>", "", clean)
        clean = re.sub(r"'''?|__NOTOC__", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) > 20:
            sec_title = sec_data.get("parse", {}).get("title", "")
            actual_sec_title = ""
            for s in sections:
                if str(s.get("index")) == str(idx):
                    actual_sec_title = s.get("line", "")
                    break
            snippets.append(
                {
                    "section_title": actual_sec_title or sec_title,
                    "text": clean[:2000],
                }
            )
        time.sleep(0.3)  # Rate limiting between section fetches

    return snippets


def fetch_wikipedia_snippets(candidate_slug: str) -> list[str]:
    """Return plain-text snippets from Wikipedia for a candidate."""
    wiki_title = CANDIDATE_WIKI_TITLES.get(candidate_slug)
    if not wiki_title:
        logger.info("No Wikipedia title mapping for %s", candidate_slug)
        return []

    logger.info("Fetching Wikipedia sections for %s (%s)", candidate_slug, wiki_title)
    sections = _fetch_wikipedia_sections(wiki_title)
    return [f"{s['section_title']}: {s['text']}" for s in sections]


# ── Source B: Câmara dos Deputados ──────────────────────────────────────


def _camara_find_deputado_id(name: str) -> int | None:
    """Look up a deputy's ID by name. Tries multiple name variations."""
    # Try exact name first, then split into parts for broader search
    attempts = [name]
    parts = name.split()
    if len(parts) >= 2:
        # Try surname only for broader match
        attempts.append(parts[-1])

    for attempt_name in attempts:
        url = (
            f"{CAMARA_API_BASE}/deputados?"
            f"nome={urllib.parse.quote(attempt_name)}&ordem=ASC&ordenarPor=nome"
        )
        data = _http_get_json(url)
        if not data:
            continue
        items = data.get("dados", [])
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                dep_id = first.get("id")
                if isinstance(dep_id, int):
                    return dep_id
    return None


def _camara_fetch_votacoes(
    deputado_id: int, since: str = "2019-01-01"
) -> list[dict[str, Any]]:
    """Fetch recent voting records for a deputy."""
    url = (
        f"{CAMARA_API_BASE}/deputados/{deputado_id}/votacoes?"
        f"dataInicio={since}&itens=100"
    )
    data = _http_get_json(url)
    if not data:
        return []
    items = data.get("dados", [])
    return [item for item in items if isinstance(item, dict)]


def _camara_classify_vote(proposicao_titulo: str) -> list[str]:
    """Classify a voting proposal into topic_ids based on keywords."""
    titulo_lower = proposicao_titulo.lower()
    matched_topics: list[str] = []
    for topic_id, keywords in TOPIC_KEYWORDS.items():
        if any(kw in titulo_lower for kw in keywords):
            matched_topics.append(topic_id)
    return matched_topics


def fetch_camara_snippets(candidate_slug: str) -> dict[str, list[str]]:
    """Fetch voting record snippets from Câmara, organized by topic_id."""
    dep_name = CAMARA_DEPUTADOS_NAMES.get(candidate_slug)
    if not dep_name:
        return {}

    logger.info("Fetching Câmara data for %s (%s)", candidate_slug, dep_name)
    dep_id = _camara_find_deputado_id(dep_name)
    if dep_id is None:
        logger.warning("Câmara: deputy ID not found for %s", dep_name)
        return {}

    votacoes = _camara_fetch_votacoes(dep_id)
    topic_snippets: dict[str, list[str]] = {}

    for voto in votacoes[:50]:  # Cap at 50 most recent votes
        titulo = voto.get("titulo", "") or ""
        voto_sigla = voto.get("voto", "") or ""
        data_hora = voto.get("dataHoraVoto", "") or ""

        matched = _camara_classify_vote(titulo)
        for topic_id in matched:
            snippet = f"Votou '{voto_sigla}' em {titulo} ({data_hora[:10]})"
            topic_snippets.setdefault(topic_id, []).append(snippet)

    time.sleep(0.3)
    return topic_snippets


# ── Source C: Senado Federal ────────────────────────────────────────────


def _senado_fetch_votacoes(senador_codigo: str) -> list[dict[str, Any]]:
    """Fetch voting records for a senator.

    Handles both old and new Senado API response structures.
    """
    url = f"{SENADO_API_BASE}/senador/{senador_codigo}/votacoes"
    data = _http_get_json(url, timeout=60)
    if not data:
        return []

    # Handle nested structure: VotacaoParlamentar -> Votacoes -> Votacao
    if "VotacaoParlamentar" in data:
        vp = data["VotacaoParlamentar"]
        if isinstance(vp, dict):
            votacoes_obj = vp.get("Votacoes", {})
            if isinstance(votacoes_obj, dict):
                items = votacoes_obj.get("Votacao", [])
            elif isinstance(votacoes_obj, list):
                items = votacoes_obj
            else:
                items = []
        else:
            items = []
    elif "Votacoes" in data:
        votacoes = data["Votacoes"]
        if isinstance(votacoes, dict):
            items = votacoes.get("Votacao", [])
        elif isinstance(votacoes, list):
            items = votacoes
        else:
            items = []
    else:
        items = []

    return [item for item in items if isinstance(item, dict)]


def _senado_classify_vote(descricao: str) -> list[str]:
    """Classify a Senate voting proposal into topic_ids."""
    desc_lower = descricao.lower()
    matched_topics: list[str] = []
    for topic_id, keywords in TOPIC_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            matched_topics.append(topic_id)
    return matched_topics


def fetch_senado_snippets(candidate_slug: str) -> dict[str, list[str]]:
    """Fetch voting record snippets from Senado, organized by topic_id."""
    senador_codes: dict[str, str] = {
        "flavio-bolsonaro": "5322",  # Flávio Bolsonaro senator code
    }
    code = senador_codes.get(candidate_slug)
    if not code:
        return {}

    logger.info("Fetching Senado data for %s", candidate_slug)
    votacoes = _senado_fetch_votacoes(code)
    topic_snippets: dict[str, list[str]] = {}

    for voto in votacoes[:50]:
        descricao = ""
        if isinstance(voto, dict):
            descricao = (
                voto.get("Descricao", "")
                or voto.get("Materia", {}).get("ementa", "")
                or ""
            )
        sessao = voto.get("SessaoPlenaria", {}) or {}
        data_sessao = sessao.get("Data", "") if isinstance(sessao, dict) else ""
        voto_voto = voto.get("Voto", "") or ""

        matched = _senado_classify_vote(descricao)
        for topic_id in matched:
            snippet = (
                f"Senado: votou '{voto_voto}' em {descricao[:200]} ({data_sessao})"
            )
            topic_snippets.setdefault(topic_id, []).append(snippet)

    time.sleep(0.3)
    return topic_snippets


# ── Source E: Party Ideological Profiles ────────────────────────────────


def fetch_party_snippets(candidate_slug: str, topic_id: str) -> list[str]:
    """Return party ideological profile snippet for a candidate/topic pair.

    Returns a one-element list with the profile text, or an empty list if no
    profile is available for the given candidate or topic.
    """
    candidate_profile = PARTY_IDEOLOGICAL_PROFILES.get(candidate_slug)
    if not candidate_profile:
        return []
    snippet = candidate_profile.get(topic_id)
    if not snippet:
        return []
    return [snippet]


# ── Source F: Web Search Snippets ────────────────────────────────────────

BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_API_KEY: str | None = os.environ.get("BRAVE_SEARCH_API_KEY")


def _brave_search(query: str, max_results: int = 5) -> list[str]:
    """Call Brave Web Search API. Returns description strings, or [] on failure."""
    if BRAVE_API_KEY is None:
        logger.warning("BRAVE_SEARCH_API_KEY not set; skipping Brave web search.")
        return []

    try:
        response = requests.get(
            BRAVE_SEARCH_API_URL,
            params={
                "q": query,
                "count": max_results,
                "search_lang": "pt",
                "country": "BR",
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.warning("Brave search failed for query '%s': %s", query, exc)
        return []

    if response.status_code != 200:
        return []

    try:
        data = response.json()
        results = data["web"]["results"]
        if not isinstance(results, list):
            return []
        snippets: list[str] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            description = item.get("description")
            if isinstance(description, str) and description.strip():
                snippets.append(description.strip())
            if len(snippets) >= max_results:
                break
        time.sleep(0.5)
        return snippets
    except (KeyError, TypeError, ValueError):
        return []


def fetch_web_snippets(candidate_slug: str, topic_id: str) -> list[str]:
    """Return web search snippets for a candidate/topic pair via Brave Search.

    Returns a list of plain-text snippets (may be empty if the candidate is
    not in *CANDIDATE_FULL_NAMES* or the network is unavailable).
    """
    full_name = CANDIDATE_FULL_NAMES.get(candidate_slug)
    if not full_name:
        logger.info("No full name mapping for %s; skipping web search", candidate_slug)
        return []

    topic_keywords = TOPIC_KEYWORDS.get(topic_id, [topic_id])
    topic_label_pt = topic_keywords[0] if topic_keywords else topic_id
    query = f'"{full_name}" "{topic_label_pt}" posição site:.br'
    return _brave_search(query, max_results=5)


# ── Topic label lookup ──────────────────────────────────────────────────


def _build_topic_label_map(topics: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Build topic_id -> (topic_label_pt, topic_label_en) from existing data."""
    mapping: dict[str, tuple[str, str]] = {}
    for topic_id, topic_data in topics.items():
        if isinstance(topic_data, dict):
            pt = topic_data.get("topic_label_pt", topic_id)
            en = topic_data.get("topic_label_en", topic_id)
            mapping[topic_id] = (pt, en)
    return mapping


# ── Main seed logic ────────────────────────────────────────────────────


def seed_positions(
    *,
    dry_run: bool = False,
    candidate_filter: str | None = None,
    topic_filter: str | None = None,
    skip_web_search: bool = False,
) -> None:
    """Main entry point: seed unknown positions from public sources."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not skip_web_search and BRAVE_API_KEY is None:
        logger.warning(
            "BRAVE_SEARCH_API_KEY not set — Source F will produce no snippets. "
            "Pass --skip-web-search to suppress this warning."
        )

    payload: dict[str, Any] = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
    topics = payload.get("topics")
    if not isinstance(topics, dict):
        raise SystemExit("Invalid candidates_positions.json: missing topics object.")

    topic_label_map = _build_topic_label_map(topics)
    today = datetime.now(timezone.utc).date().isoformat()

    seeded_count = 0
    skipped_count = 0
    source_log: list[str] = []

    candidate_slugs: set[str] = set()
    if candidate_filter:
        candidate_slugs.add(candidate_filter)
    else:
        for topic_data in topics.values():
            if isinstance(topic_data, dict):
                candidates = topic_data.get("candidates", {})
                if isinstance(candidates, dict):
                    candidate_slugs.update(candidates.keys())

    # Pre-fetch Wikipedia snippets per candidate (shared across topics)
    wiki_snippets_cache: dict[str, list[str]] = {}
    for slug in candidate_slugs:
        if slug in CANDIDATE_WIKI_TITLES:
            wiki_snippets_cache[slug] = fetch_wikipedia_snippets(slug)
        time.sleep(0.3)

    # Pre-fetch Câmara/Senado voting snippets per candidate
    camara_cache: dict[str, dict[str, list[str]]] = {}
    senado_cache: dict[str, dict[str, list[str]]] = {}
    for slug in candidate_slugs:
        if slug in CAMARA_DEPUTADOS_NAMES:
            camara_cache[slug] = fetch_camara_snippets(slug)
        senado_cache[slug] = fetch_senado_snippets(slug)
        time.sleep(0.3)

    for topic_id, topic_data in topics.items():
        if not isinstance(topic_data, dict):
            continue
        if topic_filter and topic_id != topic_filter:
            continue

        topic_label_pt, topic_label_en = topic_label_map.get(
            topic_id, (topic_id, topic_id)
        )
        candidates = topic_data.get("candidates")
        if not isinstance(candidates, dict):
            continue

        slugs_to_process = (
            [candidate_filter]
            if candidate_filter and candidate_filter in candidates
            else list(candidates.keys())
        )

        for candidate_slug in slugs_to_process:
            candidate_payload = candidates.get(candidate_slug)
            if not isinstance(candidate_payload, dict):
                continue

            # Idempotent: skip entries already reviewed
            current_stance = candidate_payload.get("stance", "unknown")
            current_position_type = candidate_payload.get("position_type", "unknown")
            if current_stance != "unknown" or current_position_type != "unknown":
                skipped_count += 1
                continue

            # Collect snippets from all sources
            snippets: list[str] = []
            sources_used: list[str] = []

            # Source A: Wikipedia
            wiki_snippets = wiki_snippets_cache.get(candidate_slug, [])
            if wiki_snippets:
                snippets.extend(wiki_snippets)
                sources_used.append("wikipedia")

            # Source B: Câmara
            camara_snippets = camara_cache.get(candidate_slug, {}).get(topic_id, [])
            if camara_snippets:
                snippets.extend(camara_snippets)
                sources_used.append("camara_api")

            # Source C: Senado
            senado_snippets = senado_cache.get(candidate_slug, {}).get(topic_id, [])
            if senado_snippets:
                snippets.extend(senado_snippets)
                sources_used.append("senado_api")

            # Source E: Party ideological profile
            party_snippets = fetch_party_snippets(candidate_slug, topic_id)
            if party_snippets:
                snippets.extend(party_snippets)
                sources_used.append("party_profile")

            # Source F: Web search snippets
            if not skip_web_search:
                web_snippets = fetch_web_snippets(candidate_slug, topic_id)
                if web_snippets:
                    snippets.extend(web_snippets[:5])
                    sources_used.append("web_search")

            # If no snippets from sources A-F, we still call AI with a grounding prompt
            if not snippets:
                sources_used.append("ai_synthesis")
                snippets = []  # Pass empty to let the AI use its training knowledge

            # Source D: AI synthesis
            try:
                extracted = extract_candidate_topic_position(
                    candidate=candidate_slug,
                    topic_id=topic_id,
                    topic_label_pt=topic_label_pt,
                    snippets=snippets[:12],
                    existing_summary_pt=None,
                )
            except Exception as exc:
                logger.warning(
                    "AI extraction failed for topic=%s candidate=%s: %s",
                    topic_id,
                    candidate_slug,
                    exc,
                )
                continue

            position_type = extracted.get("position_type")
            stance = extracted.get("stance")
            if not isinstance(position_type, str) or not isinstance(stance, str):
                continue
            if position_type == "unknown" or stance == "unknown":
                logger.info(
                    "No clear position for %s/%s (AI returned unknown).",
                    candidate_slug,
                    topic_id,
                )
                continue

            summary_pt = _normalize_optional_text(extracted.get("summary_pt"))
            summary_en = _normalize_optional_text(extracted.get("summary_en"))
            key_actions_raw = extracted.get("key_actions")
            key_actions = (
                [
                    item.strip()
                    for item in key_actions_raw
                    if isinstance(item, str) and item.strip()
                ]
                if isinstance(key_actions_raw, list)
                else []
            )

            source_list = ",".join(
                dict.fromkeys(sources_used)
            )  # deduplicate, preserve order
            editor_notes = f"SEEDED:{source_list} — requires human review"

            # Build sources list for the schema
            position_sources: list[dict[str, Any]] = []
            if "wikipedia" in sources_used:
                wiki_title = CANDIDATE_WIKI_TITLES.get(candidate_slug, "")
                position_sources.append(
                    {
                        "type": "news_report",
                        "url": f"https://pt.wikipedia.org/wiki/{wiki_title}"
                        if wiki_title
                        else None,
                        "description_pt": summary_pt
                        or f"Dados da Wikipedia para {candidate_slug}",
                        "description_en": None,
                        "date": today,
                        "article_id": None,
                    }
                )
            if "camara_api" in sources_used or "senado_api" in sources_used:
                position_sources.append(
                    {
                        "type": "voting_record",
                        "url": "https://dadosabertos.camara.leg.br"
                        if "camara_api" in sources_used
                        else "https://legis.senado.leg.br/dadosabertos",
                        "description_pt": (
                            summary_pt
                            or f"Registro de votações legislativas para {candidate_slug}"
                        ),
                        "description_en": None,
                        "date": today,
                        "article_id": None,
                    }
                )

            if dry_run:
                print(
                    f"[DRY RUN] Would update {candidate_slug}/{topic_id}:\n"
                    f"  position_type={position_type}\n"
                    f"  stance={stance}\n"
                    f"  summary_pt={summary_pt}\n"
                    f"  summary_en={summary_en}\n"
                    f"  key_actions={key_actions}\n"
                    f"  sources={','.join(dict.fromkeys(sources_used))}\n"
                    f"  editor_notes={editor_notes}\n"
                )
            else:
                candidate_payload["position_type"] = position_type
                candidate_payload["stance"] = stance
                candidate_payload["summary_pt"] = summary_pt
                candidate_payload["summary_en"] = summary_en
                candidate_payload["key_actions"] = key_actions
                candidate_payload["sources"] = position_sources
                candidate_payload["last_updated"] = today
                candidate_payload["editor_notes"] = editor_notes

            seeded_count += 1
            source_log.append(f"{candidate_slug}/{topic_id} ← {source_list}")

    if not dry_run and seeded_count > 0:
        # Update top-level metadata
        payload["updated_at"] = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        editors = payload.get("editors")
        if isinstance(editors, list):
            if "seed-script" not in editors:
                editors.append("seed-script")
        else:
            payload["editors"] = ["seed-script"]

        # Validate against schema
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        jsonschema.validate(payload, schema)

        # Atomic write
        temp_file = POSITIONS_FILE.with_suffix(".json.tmp")
        temp_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_file.replace(POSITIONS_FILE)
        logger.info("Wrote updated %s", POSITIONS_FILE)

    print(f"Seeded {seeded_count} entries. Skipped {skipped_count} existing entries.")
    if source_log:
        print("Details:")
        for entry in source_log:
            print(f"  {entry}")


# ── CLI ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed candidates positions knowledge base from public sources."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without writing.",
    )
    parser.add_argument(
        "--candidate",
        type=str,
        default=None,
        help="Limit seed to a specific candidate slug.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Limit seed to a specific topic_id.",
    )
    parser.add_argument(
        "--skip-web-search",
        action="store_true",
        default=False,
        help="Skip web search step (Source F). Useful in CI without outbound HTTP.",
    )
    args = parser.parse_args()
    seed_positions(
        dry_run=args.dry_run,
        candidate_filter=args.candidate,
        topic_filter=args.topic,
        skip_web_search=args.skip_web_search,
    )


if __name__ == "__main__":
    main()
