"""Create an idempotent candidates positions knowledge base skeleton."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

ROOT_DIR = Path(__file__).resolve().parents[1]
CANDIDATES_FILE = ROOT_DIR / "data" / "candidates.json"
OUTPUT_FILE = ROOT_DIR / "data" / "candidates_positions.json"
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"

TOPICS: list[tuple[str, str, str]] = [
    ("aborto", "Aborto", "Abortion"),
    ("corrupcao", "Combate à Corrupção", "Anti-Corruption"),
    ("economia", "Economia", "Economy"),
    ("eleicoes", "Sistema Eleitoral", "Electoral System"),
    ("impostos", "Impostos", "Taxes"),
    ("midia", "Regulação de Mídia", "Media Regulation"),
    ("politica_ext", "Política Externa", "Foreign Policy"),
    ("previdencia", "Previdência", "Social Security"),
    ("saude", "Saúde", "Healthcare"),
    ("armas", "Armas", "Firearms"),
    ("educacao", "Educação", "Education"),
    ("indigenas", "Povos Indígenas", "Indigenous Peoples"),
    ("lgbtq", "Direitos LGBTQIA+", "LGBTQIA+ Rights"),
    ("meio_ambiente", "Meio Ambiente", "Environment"),
    ("seguranca", "Segurança Pública", "Public Security"),
]


def _load_candidate_slugs() -> list[str]:
    payload = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        return []
    slugs: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        if isinstance(slug, str) and slug:
            slugs.append(slug)
    return slugs


def _build_payload(candidate_slugs: list[str]) -> dict[str, object]:
    today = datetime.now(timezone.utc).date().isoformat()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    topics: dict[str, object] = {}
    for topic_id, topic_label_pt, topic_label_en in TOPICS:
        candidates: dict[str, object] = {}
        for slug in candidate_slugs:
            candidates[slug] = {
                "position_type": "unknown",
                "stance": "unknown",
                "summary_pt": None,
                "summary_en": None,
                "key_actions": [],
                "sources": [],
                "last_updated": today,
                "editor_notes": None,
            }

        topics[topic_id] = {
            "topic_id": topic_id,
            "topic_label_pt": topic_label_pt,
            "topic_label_en": topic_label_en,
            "candidates": candidates,
        }

    return {
        "schema_version": "2.0.0",
        "updated_at": generated_at,
        "editors": [],
        "topics": topics,
    }


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".json.tmp")
    temp_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_file.replace(path)


def main() -> None:
    candidate_slugs = _load_candidate_slugs()
    if not candidate_slugs:
        raise SystemExit("No candidate slugs found in data/candidates.json.")

    payload = _build_payload(candidate_slugs)
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    _write_atomic(OUTPUT_FILE, payload)
    print(
        f"Created {OUTPUT_FILE} with {len(payload['topics'])} topics and "
        f"{len(candidate_slugs)} candidates."
    )


if __name__ == "__main__":
    main()
