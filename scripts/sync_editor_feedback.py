"""Sync editor_feedback.json from currently flagged irrelevant articles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts import editor_feedback
except ImportError:  # pragma: no cover - direct script execution path
    import editor_feedback  # type: ignore[no-redef]

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
EDITOR_FEEDBACK_FILE = DATA_DIR / "editor_feedback.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_articles() -> list[dict[str, Any]]:
    if not ARTICLES_FILE.exists():
        return []

    payload = _load_json(ARTICLES_FILE)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw_articles = payload.get("articles", [])
        if isinstance(raw_articles, list):
            return [item for item in raw_articles if isinstance(item, dict)]
    raise ValueError(f"Unsupported articles structure in {ARTICLES_FILE}")


def sync_editor_feedback() -> tuple[int, int]:
    articles = _load_articles()
    feedback = editor_feedback.load_editor_feedback(EDITOR_FEEDBACK_FILE)
    added = editor_feedback.add_irrelevant_article_ids(feedback, articles)
    total = len(feedback.get("irrelevant_article_ids", []))

    if added > 0 or not EDITOR_FEEDBACK_FILE.exists():
        editor_feedback.save_editor_feedback(feedback, EDITOR_FEEDBACK_FILE)

    print(f"Editor feedback synced: {added} new irrelevant ids ({total} total)")
    return added, total


def main() -> None:
    sync_editor_feedback()


if __name__ == "__main__":
    main()

