"""Seed the candidates positions knowledge base from structured public sources.

Fetches baseline data from Wikipedia PT, Câmara dos Deputados, and Senado
Federal APIs, then uses AI synthesis to fill entries currently marked "unknown".
Idempotent: never overwrites entries already reviewed by a human editor.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import time
import urllib.parse
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
    "armas": [
        "arma",
        "fogo",
        "munição",
        "porte",
        "desarmamento",
        "estatuto do desarmamento",
        "armamento",
    ],
    "meio_ambiente": [
        "meio ambiente",
        "floresta",
        "desmatamento",
        "licenciamento ambiental",
        "amazônia",
        "carbono",
        "clima",
        "ibama",
        "unidade de conservação",
    ],
    "lgbtq": [
        "lgbtq",
        "homofobia",
        "identidade de gênero",
        "gay",
        "transexual",
        "homoafetivo",
        "discriminação",
        "PL 5901",
        "diversidade sexual",
        "casamento igualitário",
    ],
    "aborto": [
        "aborto",
        "gestação",
        "interrupção",
        "PL 1904",
        "art. 128",
        "artigo 128",
        "gestante",
        "feto",
        "vida humana",
        "estupro",
        "anencéfalo",
    ],
    "previdencia": [
        "previdência",
        "aposentadoria",
        "pensão",
        "INSS",
        "reforma previdenciária",
        "benefício",
        "contribuição",
    ],
    "impostos": [
        "imposto",
        "tributário",
        "reforma fiscal",
        "ir ",
        "reforma tributária",
        "IVA",
        "carga tributária",
        "simplificação tributária",
    ],
    "midia": [
        "plataforma",
        "fake news",
        "desinformação",
        "regulação de mídia",
        "redes sociais",
        "censura",
        "marco civil",
        "liberdade de imprensa",
        "X",
        "Meta",
        "imprensa",
    ],
    "indigenas": [
        "indígena",
        "marco temporal",
        "demarcação",
        "FUNAI",
        "reserva",
        "território",
        "aldeia",
        "povos originários",
    ],
    "educacao": [
        "educação",
        "ensino",
        "escola",
        "universidade",
        "MEC",
        "homeschooling",
        "ensino médio",
        "ensino fundamental",
        "vestibular",
        "ENEM",
    ],
    "seguranca": [
        "segurança pública",
        "polícia",
        "crime",
        "drogas",
        "violência",
        "milícia",
        "presídio",
        "sistema prisional",
        "tráfico",
    ],
    "corrupcao": [
        "corrupção",
        "improbidade",
        "lava jato",
        "anticorrupção",
        "Lava Jato",
        "peculato",
        "lavagem de dinheiro",
        "ficha limpa",
        "transparência",
        "desvio",
    ],
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


def _fetch_wikipedia_text(wiki_title: str) -> str:
    """Fetch a Wikipedia article as plain text using the TextExtracts API.

    Returns the full article text, or an empty string on failure.
    A single HTTP request replaces the old per-section approach.
    """
    url = (
        f"{WIKIPEDIA_API_BASE}?action=query"
        f"&prop=extracts&explaintext=true&redirects=1"
        f"&titles={urllib.parse.quote(wiki_title)}"
        f"&format=json"
    )
    data = _http_get_json(url)
    if not data:
        return ""
    pages = data.get("query", {}).get("pages", {})
    if not isinstance(pages, dict):
        return ""
    page = next(iter(pages.values()), {})
    if not isinstance(page, dict):
        return ""
    return page.get("extract", "") or ""


def _extract_topic_paragraphs(text: str, topic_id: str) -> list[str]:
    """Return paragraphs from *text* that mention any keyword for *topic_id*.

    Falls back to the first 10 paragraphs if the topic has no keyword match,
    so there is always some context for the AI even for niche topics.
    """
    keywords = TOPIC_KEYWORDS.get(topic_id, [])
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) > 50]
    if not paragraphs:
        return []

    kw_lower = [kw.lower() for kw in keywords]
    matched = [p for p in paragraphs if any(kw in p.lower() for kw in kw_lower)]
    # Cap each paragraph to avoid sending huge context to the AI
    cap = 500
    return [p[:cap] for p in (matched or paragraphs[:10])[:8]]


def fetch_wikipedia_snippets(candidate_slug: str) -> str:
    """Return the full plain-text Wikipedia article for a candidate.

    Returns an empty string when no mapping exists or the fetch fails.
    """
    wiki_title = CANDIDATE_WIKI_TITLES.get(candidate_slug)
    if not wiki_title:
        logger.info("No Wikipedia title mapping for %s", candidate_slug)
        return ""

    logger.info("Fetching Wikipedia text for %s (%s)", candidate_slug, wiki_title)
    return _fetch_wikipedia_text(wiki_title)


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

    def _extract_items(votacoes_obj: object) -> list[dict[str, Any]]:
        if isinstance(votacoes_obj, dict):
            maybe_items = votacoes_obj.get("Votacao", [])
        elif isinstance(votacoes_obj, list):
            maybe_items = votacoes_obj
        else:
            maybe_items = []
        return [item for item in maybe_items if isinstance(item, dict)]

    # New structure: VotacaoParlamentar -> Parlamentar -> Votacoes -> Votacao
    # Legacy fallback: VotacaoParlamentar -> Votacoes -> Votacao
    vp = data.get("VotacaoParlamentar") if isinstance(data, dict) else None
    if isinstance(vp, dict):
        parlamentar = vp.get("Parlamentar")
        if isinstance(parlamentar, dict):
            items = _extract_items(parlamentar.get("Votacoes"))
            if items:
                return items

        items = _extract_items(vp.get("Votacoes"))
        if items:
            return items

    # Additional legacy fallback
    if isinstance(data, dict):
        items = _extract_items(data.get("Votacoes"))
        if items:
            return items

    return []


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
        "flavio-bolsonaro": "5894",  # Flávio Nantes Bolsonaro
    }
    code = senador_codes.get(candidate_slug)
    if not code:
        return {}

    logger.info("Fetching Senado data for %s", candidate_slug)
    votacoes = _senado_fetch_votacoes(code)
    topic_snippets: dict[str, list[str]] = {}

    for voto in votacoes[:300]:
        materia = voto.get("Materia", {}) if isinstance(voto, dict) else {}
        materia_ementa = ""
        if isinstance(materia, dict):
            materia_ementa = (
                _normalize_optional_text(materia.get("Ementa"))
                or _normalize_optional_text(materia.get("ementa"))
                or ""
            )

        descricao = (
            _normalize_optional_text(voto.get("DescricaoVotacao"))
            or _normalize_optional_text(voto.get("Descricao"))
            or materia_ementa
            or ""
        )

        sessao = voto.get("SessaoPlenaria", {}) or {}
        data_sessao = ""
        if isinstance(sessao, dict):
            data_sessao = (
                _normalize_optional_text(sessao.get("DataSessao"))
                or _normalize_optional_text(sessao.get("Data"))
                or ""
            )

        voto_voto = (
            _normalize_optional_text(voto.get("SiglaDescricaoVoto"))
            or _normalize_optional_text(voto.get("Voto"))
            or ""
        )

        matched = _senado_classify_vote(descricao)
        for topic_id in matched:
            snippet = (
                f"Senado: votou '{voto_voto}' em {descricao[:200]} ({data_sessao})"
            )
            bucket = topic_snippets.setdefault(topic_id, [])
            if len(bucket) < 8:
                bucket.append(snippet)

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
BRAVE_SEARCH_SITE_RESTRICTION = "site:.br"

try:
    DEFAULT_AI_WORKERS = max(1, int(os.environ.get("SEED_AI_WORKERS", "1")))
except ValueError:
    DEFAULT_AI_WORKERS = 1

MAX_AI_SNIPPETS = 12
SNIPPET_LIMITS_BY_SOURCE: dict[str, int] = {
    "camara_api": 4,
    "senado_api": 4,
    "party_profile": 2,
    "wikipedia": 4,
    "web_search": 2,
}


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
    not in *CANDIDATE_FULL_NAMES* or the network is unavailable). Queries are
    restricted to Brazilian domains via ``site:.br``.
    """
    full_name = CANDIDATE_FULL_NAMES.get(candidate_slug)
    if not full_name:
        logger.info("No full name mapping for %s; skipping web search", candidate_slug)
        return []

    topic_keywords = TOPIC_KEYWORDS.get(topic_id, [topic_id])
    topic_label_pt = topic_keywords[0] if topic_keywords else topic_id
    query = f'"{full_name}" "{topic_label_pt}" posição {BRAVE_SEARCH_SITE_RESTRICTION}'
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


def _extend_unique_snippets(
    selected: list[str],
    seen: set[str],
    candidates: list[str],
    max_items: int,
) -> int:
    """Append up to *max_items* unique snippets and return added count."""
    added = 0
    for snippet in candidates:
        cleaned = snippet.strip()
        if not cleaned or cleaned in seen:
            continue
        selected.append(cleaned)
        seen.add(cleaned)
        added += 1
        if added >= max_items or len(selected) >= MAX_AI_SNIPPETS:
            break
    return added


# ── Per-pair AI worker ─────────────────────────────────────────────────


def _seed_single(
    *,
    candidate_slug: str,
    topic_id: str,
    topic_label_pt: str,
    wiki_text: str,
    camara_snippets_for_topic: list[str],
    senado_snippets_for_topic: list[str],
    skip_web_search: bool = False,
) -> dict[str, Any] | None:
    """Run AI synthesis for one (candidate, topic) pair.

    Returns a dict with the extracted fields, or None if the AI returned unknown.
    Designed to run inside a ThreadPoolExecutor worker.
    """
    sources_used: list[str] = []
    source_snippets: dict[str, list[str]] = {}

    if wiki_text:
        wiki_snippets = _extract_topic_paragraphs(wiki_text, topic_id)
        if wiki_snippets:
            source_snippets["wikipedia"] = wiki_snippets

    if camara_snippets_for_topic:
        source_snippets["camara_api"] = camara_snippets_for_topic

    if senado_snippets_for_topic:
        source_snippets["senado_api"] = senado_snippets_for_topic

    party_snippets = fetch_party_snippets(candidate_slug, topic_id)
    if party_snippets:
        source_snippets["party_profile"] = party_snippets

    if not skip_web_search:
        web_snippets = fetch_web_snippets(candidate_slug, topic_id)
        if web_snippets:
            source_snippets["web_search"] = web_snippets

    # Prioritize high-signal sources and cap each source to avoid one source
    # crowding out all others in the first MAX_AI_SNIPPETS entries.
    snippets: list[str] = []
    seen_snippets: set[str] = set()
    source_order = (
        "camara_api",
        "senado_api",
        "party_profile",
        "wikipedia",
        "web_search",
    )
    for source_name in source_order:
        candidates = source_snippets.get(source_name, [])
        if not candidates:
            continue
        limit = SNIPPET_LIMITS_BY_SOURCE.get(source_name, MAX_AI_SNIPPETS)
        added = _extend_unique_snippets(snippets, seen_snippets, candidates, limit)
        if added > 0:
            sources_used.append(source_name)
        if len(snippets) >= MAX_AI_SNIPPETS:
            break

    # Grounding fallback: when no data-source evidence, inject a prompt that
    # instructs the AI to reason from its training knowledge about the candidate.
    if not snippets:
        snippets = [
            f"[Base de conhecimento] Descreva o posicionamento público documentado de "
            f"{candidate_slug} sobre '{topic_label_pt}', com base em declarações, "
            f"projetos de lei, votações ou ações de governo conhecidas."
        ]
        sources_used.append("ai_synthesis")

    try:
        extracted = extract_candidate_topic_position(
            candidate=candidate_slug,
            topic_id=topic_id,
            topic_label_pt=topic_label_pt,
            snippets=snippets,
            existing_summary_pt=None,
        )
    except Exception as exc:
        logger.warning(
            "AI extraction failed for topic=%s candidate=%s: %s",
            topic_id,
            candidate_slug,
            exc,
        )
        return None

    position_type = extracted.get("position_type")
    stance = extracted.get("stance")
    if not isinstance(position_type, str) or not isinstance(stance, str):
        return None
    if position_type == "unknown" or stance == "unknown":
        logger.info(
            "No clear position for %s/%s (AI returned unknown).",
            candidate_slug,
            topic_id,
        )
        return None

    return {
        "candidate_slug": candidate_slug,
        "topic_id": topic_id,
        "position_type": position_type,
        "stance": stance,
        "summary_pt": _normalize_optional_text(extracted.get("summary_pt")),
        "summary_en": _normalize_optional_text(extracted.get("summary_en")),
        "key_actions": [
            item.strip()
            for item in (extracted.get("key_actions") or [])
            if isinstance(item, str) and item.strip()
        ],
        "sources_used": list(dict.fromkeys(sources_used)),
    }


# ── Main seed logic ────────────────────────────────────────────────────


def seed_positions(
    *,
    dry_run: bool = False,
    candidate_filter: str | None = None,
    topic_filter: str | None = None,
    skip_web_search: bool = False,
    enable_camara: bool = False,
    ai_workers: int = DEFAULT_AI_WORKERS,
) -> None:
    """Main entry point: seed unknown positions from public sources."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ai_workers = max(1, ai_workers)
    if not skip_web_search and BRAVE_API_KEY is None:
        logger.warning(
            "BRAVE_SEARCH_API_KEY not set — Source F will produce no snippets. "
            "Pass --skip-web-search to suppress this warning."
        )
    if not enable_camara:
        logger.info(
            "Skipping Câmara source by default (use --enable-camara to opt in)."
        )
    else:
        logger.warning(
            "Câmara source is experimental and may return sparse data while endpoint coverage is updated."
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

    # Collect candidate slugs that need processing
    candidate_slugs: set[str] = set()
    if candidate_filter:
        candidate_slugs.add(candidate_filter)
    else:
        for topic_data in topics.values():
            if isinstance(topic_data, dict):
                candidates = topic_data.get("candidates", {})
                if isinstance(candidates, dict):
                    candidate_slugs.update(candidates.keys())

    # ── Phase 1: Parallel Wikipedia pre-fetch (1 request per candidate) ──
    wiki_text_cache: dict[str, str] = {}
    slugs_with_wiki = [s for s in candidate_slugs if s in CANDIDATE_WIKI_TITLES]

    def _fetch_wiki(slug: str) -> tuple[str, str]:
        return slug, fetch_wikipedia_snippets(slug)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for slug, text in pool.map(_fetch_wiki, slugs_with_wiki):
            wiki_text_cache[slug] = text

    # ── Phase 2: Sequential Câmara/Senado fetch (few candidates) ──────────
    camara_cache: dict[str, dict[str, list[str]]] = {}
    senado_cache: dict[str, dict[str, list[str]]] = {}
    for slug in candidate_slugs:
        if enable_camara and slug in CAMARA_DEPUTADOS_NAMES:
            camara_cache[slug] = fetch_camara_snippets(slug)
        senado_cache[slug] = fetch_senado_snippets(slug)

    # ── Phase 3: Build work items (skip already-reviewed entries) ─────────
    WorkItem = tuple[str, str, str, str, list[str], list[str]]  # type alias for clarity
    work_items: list[WorkItem] = []

    for topic_id, topic_data in topics.items():
        if not isinstance(topic_data, dict):
            continue
        if topic_filter and topic_id != topic_filter:
            continue

        topic_label_pt, _ = topic_label_map.get(topic_id, (topic_id, topic_id))
        candidates = topic_data.get("candidates")
        if not isinstance(candidates, dict):
            continue

        if candidate_filter:
            if candidate_filter not in candidates:
                continue
            slugs_to_process = [candidate_filter]
        else:
            slugs_to_process = list(candidates.keys())

        for candidate_slug in slugs_to_process:
            candidate_payload = candidates.get(candidate_slug)
            if not isinstance(candidate_payload, dict):
                continue
            current_stance = candidate_payload.get("stance", "unknown")
            current_position_type = candidate_payload.get("position_type", "unknown")
            if current_stance != "unknown" or current_position_type != "unknown":
                skipped_count += 1
                continue

            work_items.append(
                (
                    candidate_slug,
                    topic_id,
                    topic_label_pt,
                    wiki_text_cache.get(candidate_slug, ""),
                    camara_cache.get(candidate_slug, {}).get(topic_id, []),
                    senado_cache.get(candidate_slug, {}).get(topic_id, []),
                )
            )

    logger.info(
        "Seeding %d candidate/topic pairs (%d skipped as already reviewed).",
        len(work_items),
        skipped_count,
    )

    # ── Phase 4: Parallel AI synthesis ────────────────────────────────────
    def _run_seed(item: WorkItem) -> dict[str, Any] | None:
        slug, tid, label_pt, wiki_text, camara_snips, senado_snips = item
        return _seed_single(
            candidate_slug=slug,
            topic_id=tid,
            topic_label_pt=label_pt,
            wiki_text=wiki_text,
            camara_snippets_for_topic=camara_snips,
            senado_snippets_for_topic=senado_snips,
            skip_web_search=skip_web_search,
        )

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=ai_workers) as pool:
        for result in pool.map(_run_seed, work_items):
            if result is not None:
                results.append(result)

    # ── Phase 5: Apply results ─────────────────────────────────────────────
    for result in results:
        candidate_slug = result["candidate_slug"]
        topic_id = result["topic_id"]
        sources_used = result["sources_used"]
        source_list = ",".join(sources_used)
        editor_notes = f"SEEDED:{source_list} - requires human review"

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
                    "description_pt": result["summary_pt"]
                    or f"Dados da Wikipedia para {candidate_slug}",
                    "description_en": None,
                    "date": today,
                    "article_id": None,
                }
            )

        if "camara_api" in sources_used:
            position_sources.append(
                {
                    "type": "voting_record",
                    "url": "https://dadosabertos.camara.leg.br",
                    "description_pt": (
                        result["summary_pt"]
                        or f"Registro de votações legislativas para {candidate_slug}"
                    ),
                    "description_en": None,
                    "date": today,
                    "article_id": None,
                }
            )

        if "senado_api" in sources_used:
            position_sources.append(
                {
                    "type": "voting_record",
                    "url": "https://legis.senado.leg.br/dadosabertos",
                    "description_pt": (
                        result["summary_pt"]
                        or f"Registro de votações legislativas para {candidate_slug}"
                    ),
                    "description_en": None,
                    "date": today,
                    "article_id": None,
                }
            )

        if "party_profile" in sources_used:
            position_sources.append(
                {
                    "type": "party_platform",
                    "url": None,
                    "description_pt": (
                        result["summary_pt"]
                        or f"Perfil partidário para {candidate_slug}"
                    ),
                    "description_en": None,
                    "date": today,
                    "article_id": None,
                }
            )

        if "web_search" in sources_used:
            position_sources.append(
                {
                    "type": "news_report",
                    "url": None,
                    "description_pt": (
                        result["summary_pt"] or f"Pesquisa web para {candidate_slug}"
                    ),
                    "description_en": None,
                    "date": today,
                    "article_id": None,
                }
            )

        if dry_run:
            print(
                f"[DRY RUN] Would update {candidate_slug}/{topic_id}:\n"
                f"  position_type={result['position_type']}\n"
                f"  stance={result['stance']}\n"
                f"  summary_pt={result['summary_pt']}\n"
                f"  summary_en={result['summary_en']}\n"
                f"  key_actions={result['key_actions']}\n"
                f"  sources={position_sources}\n"
                f"  editor_notes={editor_notes}\n"
            )
        else:
            candidate_payload = (
                topics[topic_id].get("candidates", {}).get(candidate_slug, {})
            )
            if not isinstance(candidate_payload, dict):
                continue
            candidate_payload["position_type"] = result["position_type"]
            candidate_payload["stance"] = result["stance"]
            candidate_payload["summary_pt"] = result["summary_pt"]
            candidate_payload["summary_en"] = result["summary_en"]
            candidate_payload["key_actions"] = result["key_actions"]
            candidate_payload["sources"] = position_sources
            candidate_payload["last_updated"] = today
            candidate_payload["editor_notes"] = editor_notes

        seeded_count += 1
        source_log.append(f"{candidate_slug}/{topic_id} <- {source_list}")

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
    parser.add_argument(
        "--enable-camara",
        action="store_true",
        default=False,
        help="Enable Câmara source (disabled by default while API integration is stabilized).",
    )
    parser.add_argument(
        "--ai-workers",
        type=int,
        default=DEFAULT_AI_WORKERS,
        help="Number of parallel AI workers (default from SEED_AI_WORKERS or 1).",
    )
    args = parser.parse_args()
    seed_positions(
        dry_run=args.dry_run,
        candidate_filter=args.candidate,
        topic_filter=args.topic,
        skip_web_search=args.skip_web_search,
        enable_camara=args.enable_camara,
        ai_workers=args.ai_workers,
    )


if __name__ == "__main__":
    main()
