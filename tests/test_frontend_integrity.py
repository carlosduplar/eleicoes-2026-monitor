"""Frontend integrity guard.

Every relative (./ ../) or aliased (@/) import inside site/src must resolve to an
existing file that is tracked by git. Guards against recurrence of the missing-file
defect where site/src/utils/bootData.js was imported by tracked code but never
committed, breaking clean checkouts (docs/architecture/02-risk-register.md, R1).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_SRC = REPO_ROOT / "site" / "src"
SCAN_SUFFIXES = {".js", ".jsx", ".mjs"}

FROM_RE = re.compile(r"""\bfrom\s+['"]([^'"]+)['"]""")
DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]""")
SIDE_EFFECT_RE = re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.MULTILINE)

EXTENSION_CANDIDATES = ("", ".js", ".jsx", ".json", ".css", ".svg", ".mjs", ".ts")
TRACKED_PATHS_PREFIXES = ("site/src", "docs/schemas")


def _tracked_site_files() -> set[str]:
    output = subprocess.run(
        ["git", "ls-files", *TRACKED_PATHS_PREFIXES],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line.strip() for line in output.splitlines() if line.strip()}


def _resolve_specifier(specifier: str, importer: Path) -> Path | None:
    if specifier.startswith("@/"):
        base: Path = SITE_SRC / specifier[2:]
    elif specifier.startswith("./") or specifier.startswith("../"):
        base = (importer.parent / specifier).resolve()
    else:
        return None

    if base.suffix and base.is_file():
        return base
    for suffix in EXTENSION_CANDIDATES:
        candidate = Path(str(base) + suffix) if not str(base).endswith(suffix) else base
        if candidate.is_file():
            return candidate
    for index_name in ("index.js", "index.jsx"):
        candidate = base / index_name
        if candidate.is_file():
            return candidate
    return None


def _specifiers_in(text: str) -> list[str]:
    found: list[str] = []
    for pattern in (FROM_RE, DYNAMIC_IMPORT_RE, SIDE_EFFECT_RE):
        found.extend(pattern.findall(text))
    return [specifier for specifier in found if specifier.startswith(("./", "../", "@/"))]


def test_all_frontend_imports_are_tracked() -> None:
    tracked = _tracked_site_files()
    broken: list[str] = []

    for importer in sorted(SITE_SRC.rglob("*")):
        if importer.suffix not in SCAN_SUFFIXES or not importer.is_file():
            continue
        for specifier in _specifiers_in(importer.read_text(encoding="utf-8")):
            resolved = _resolve_specifier(specifier, importer)
            if resolved is None:
                broken.append(f"{importer.relative_to(REPO_ROOT)}: cannot resolve '{specifier}'")
                continue
            rel = resolved.relative_to(REPO_ROOT).as_posix()
            if rel not in tracked:
                broken.append(
                    f"{importer.relative_to(REPO_ROOT)}: imports '{specifier}' -> "
                    f"{rel} is NOT tracked by git"
                )

    assert not broken, (
        "Frontend imports reference missing or untracked files:\n  " + "\n  ".join(broken)
    )
