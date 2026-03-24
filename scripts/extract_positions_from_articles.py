"""Extract candidate positions from articles into a reviewable draft knowledge base."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from .ai_client import extract_candidate_topic_position

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT_DIR / "site" / "public" / "data" / "articles.json"
POSITIONS_FILE = ROOT_DIR / "site" / "public" / "data" / "candidates_positions.json"
DEFAULT_DRAFT_FILE = (
    ROOT_DIR / "site" / "public" / "data" / "candidates_positions_draft.json"
)
SCHEMA_FILE = ROOT_DIR / "docs" / "schemas" / "candidates_positions.schema.json"


def _parse_iso8601(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    cleaned = value.strip().replace("Z", "+00:00")
    if not cleaned:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def load_articles() -> list[dict[str, object]]:
    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw_articles = payload.get("articles")
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)]
    return []


def build_evidence_snippets(
    articles: list[dict[str, object]],
    candidate_slug: str,
    topic_id: str,
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for article in articles:
        candidates = article.get("candidates_mentioned")
        topics = article.get("topics")
        if not isinstance(candidates, list) or not isinstance(topics, list):
            continue
        if candidate_slug not in candidates or topic_id not in topics:
            continue

        title = _normalize_text(article.get("title"))
        summaries = article.get("summaries")
        summary_pt = None
        if isinstance(summaries, dict):
            summary_pt = _normalize_text(summaries.get("pt-BR"))
        content = _normalize_text(article.get("content"))

        snippet = None
        if title and summary_pt:
            snippet = f"{title}. {summary_pt}"
        elif title and content:
            snippet = f"{title}. {content[:240]}"
        elif summary_pt:
            snippet = summary_pt
        elif title:
            snippet = title

        if not snippet:
            continue

        published_at = article.get("published_at")
        parsed_published = _parse_iso8601(published_at)
        evidence.append(
            {
                "snippet": snippet,
                "published_at": parsed_published,
                "article_id": _normalize_text(article.get("id")),
                "url": _normalize_text(article.get("url")),
            }
        )

    evidence.sort(key=lambda item: item["published_at"], reverse=True)
    return evidence[:12]


def _to_source_description(snippet: str) -> str:
    clipped = snippet[:260].strip()
    if len(snippet) > 260:
        clipped = f"{clipped}..."
    return clipped


def _build_sources_from_indices(
    evidence: list[dict[str, object]],
    source_indices: list[int],
) -> list[dict[str, object]]:
    if not evidence:
        return []

    normalized_indices = [
        index
        for index in source_indices
        if isinstance(index, int) and 1 <= index <= len(evidence)
    ]
    if not normalized_indices:
        normalized_indices = [1]

    sources: list[dict[str, object]] = []
    for index in normalized_indices:
        source_item = evidence[index - 1]
        snippet = str(source_item["snippet"])
        published_at = source_item["published_at"]
        date_value = None
        if isinstance(published_at, datetime) and published_at.year > 1:
            date_value = published_at.date().isoformat()
        sources.append(
            {
                "type": "news_report",
                "url": source_item.get("url"),
                "description_pt": _to_source_description(snippet),
                "description_en": None,
                "date": date_value,
                "article_id": source_item.get("article_id"),
            }
        )
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DRAFT_FILE,
        help="Output path for draft knowledge base JSON.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates directly to data/candidates_positions.json.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    articles = load_articles()
    positions_payload = _load_json(POSITIONS_FILE)
    if not isinstance(positions_payload, dict):
        raise SystemExit("Invalid candidates_positions.json structure.")

    topics = positions_payload.get("topics")
    if not isinstance(topics, dict):
        raise SystemExit("Invalid candidates_positions.json: missing topics object.")

    updated = 0
    for topic_id, topic_payload in topics.items():
        if not isinstance(topic_payload, dict):
            continue
        topic_label_pt = (
            _normalize_text(topic_payload.get("topic_label_pt")) or topic_id
        )
        candidates = topic_payload.get("candidates")
        if not isinstance(candidates, dict):
            continue

        for candidate_slug, candidate_payload in candidates.items():
            if not isinstance(candidate_payload, dict):
                continue

            evidence = build_evidence_snippets(articles, candidate_slug, topic_id)
            snippets = [str(item["snippet"]) for item in evidence]
            existing_summary_pt = _normalize_text(candidate_payload.get("summary_pt"))

            try:
                extracted = extract_candidate_topic_position(
                    candidate=candidate_slug,
                    topic_id=topic_id,
                    topic_label_pt=topic_label_pt,
                    snippets=snippets,
                    existing_summary_pt=existing_summary_pt,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Position extraction failed for topic=%s candidate=%s: %s",
                    topic_id,
                    candidate_slug,
                    exc,
                )
                continue

            position_type = extracted.get("position_type")
            stance = extracted.get("stance")
            if position_type == "unknown" or stance == "unknown":
                continue

            summary_pt = _normalize_text(extracted.get("summary_pt"))
            summary_en = _normalize_text(extracted.get("summary_en"))
            key_actions_raw = extracted.get("key_actions")
            if isinstance(key_actions_raw, list):
                key_actions = [
                    item.strip()
                    for item in key_actions_raw
                    if isinstance(item, str) and item.strip()
                ]
            else:
                key_actions = []

            source_indices_raw = extracted.get("source_indices")
            source_indices = (
                [item for item in source_indices_raw if isinstance(item, int)]
                if isinstance(source_indices_raw, list)
                else []
            )

            today = datetime.now(timezone.utc).date().isoformat()
            candidate_payload["position_type"] = position_type
            candidate_payload["stance"] = stance
            candidate_payload["summary_pt"] = summary_pt
            candidate_payload["summary_en"] = summary_en
            candidate_payload["key_actions"] = key_actions
            candidate_payload["sources"] = _build_sources_from_indices(
                evidence, source_indices
            )
            candidate_payload["last_updated"] = today
            candidate_payload["editor_notes"] = (
                "AUTO-EXTRACTED: requires human review before publishing."
            )
            updated += 1

    positions_payload["updated_at"] = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    editors = positions_payload.get("editors")
    if isinstance(editors, list):
        if "auto-extractor" not in editors:
            editors.append("auto-extractor")
    else:
        positions_payload["editors"] = ["auto-extractor"]

    schema = _load_json(SCHEMA_FILE)
    jsonschema.validate(positions_payload, schema)

    output_path = POSITIONS_FILE if args.apply else args.output
    _write_atomic(output_path, positions_payload)
    print(f"Updated {updated} candidate/topic entries. Wrote {output_path}.")


if __name__ == "__main__":
    main()
