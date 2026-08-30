"""Public-store whitelist guard.

Locks the exact set of entries allowed in site/public/data/, the directory that
ships verbatim to GitHub Pages. Any new file appearing here must be a deliberate,
reviewed decision (docs/architecture/02-risk-register.md R2). Internal pipeline
state lives in state/ (migration steps M3-M5) and is never listed here.
"""

from __future__ import annotations

import re

from scripts.store import PUB_DATA_DIR

EXPECTED_ENTRIES = frozenset(
    {
        # published content
        "articles.json",
        "archives",
        "candidates.json",
        "candidates_positions.json",
        "candidates_positions_draft.json",
        "curated_feed.json",
        "donors.json",
        "markets.json",
        "pipeline_health.json",
        "polls.json",
        "quiz.json",
        "sentiment.json",
        "sources.json",
        "tse_data.json",
        "transparencia_data.json",
        "weekly_briefing.json",
    }
)


def test_public_data_contains_only_whitelisted_entries() -> None:
    assert PUB_DATA_DIR.is_dir(), f"{PUB_DATA_DIR} does not exist; nothing to guard"

    actual = {entry.name for entry in PUB_DATA_DIR.iterdir()}
    unexpected = sorted(actual - EXPECTED_ENTRIES)
    stale = sorted(EXPECTED_ENTRIES - actual)

    assert not unexpected, (
        "Unwhitelisted files appeared in the public store "
        f"({PUB_DATA_DIR}); they would be published to the live site:\n  "
        + "\n  ".join(unexpected)
        + "\nAdd them to EXPECTED_ENTRIES only after review."
    )
    assert not stale, (
        "Whitelist references entries no longer present; prune them:\n  "
        + "\n  ".join(stale)
    )


def test_archives_layout_is_monthly_json() -> None:
    archives = PUB_DATA_DIR / "archives"
    if not archives.is_dir():
        return
    pattern = re.compile(r"^(articles-\d{4}-\d{2}|markets-\d{4}-\d{2}-\d{2})\.json$")
    offenders = [
        entry.name
        for entry in archives.iterdir()
        if not (entry.is_file() and pattern.match(entry.name))
    ]
    assert not offenders, (
        "data/archives/ expects monthly article archives (articles-YYYY-MM.json) and daily market snapshots (markets-YYYY-MM-DD.json) only:\n  "
        + "\n  ".join(offenders)
    )
