"""Generate sitemap.xml for all static and dynamic routes.

Reads data/candidates.json and writes site/public/sitemap.xml.
Idempotent: running twice produces identical output.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent, register_namespace

BASE_URL: str = "https://eleicoes2026.com.br"
SITEMAP_NS: str = "http://www.sitemaps.org/schemas/sitemap/0.9"

COMPARISON_PAIRS: list[tuple[str, str]] = [
    ("lula", "tarcisio"),
    ("lula", "caiado"),
    ("tarcisio", "caiado"),
    ("tarcisio", "ratinho-jr"),
    ("lula", "zema"),
    ("caiado", "ratinho-jr"),
    ("lula", "ratinho-jr"),
    ("tarcisio", "zema"),
]

STATIC_ROUTES: list[dict[str, str]] = [
    {"loc": "/", "priority": "1.0", "changefreq": "daily"},
    {"loc": "/sentimento", "priority": "0.8", "changefreq": "daily"},
    {"loc": "/pesquisas", "priority": "0.8", "changefreq": "daily"},
    {"loc": "/quiz", "priority": "0.9", "changefreq": "daily"},
    {"loc": "/metodologia", "priority": "0.7", "changefreq": "weekly"},
    {"loc": "/sobre/caso-de-uso", "priority": "0.6", "changefreq": "weekly"},
]


def load_candidates(data_dir: Path) -> list[dict]:
    """Load and return candidates list from data/candidates.json."""

    candidates_path = data_dir / "candidates.json"
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("candidates.json root must be an object.")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates.json must contain a 'candidates' array.")

    seen_slugs: set[str] = set()
    for index, entry in enumerate(candidates):
        if not isinstance(entry, dict):
            raise ValueError(f"Candidate at index {index} must be an object.")
        slug = entry.get("slug")
        if not isinstance(slug, str) or not slug:
            raise ValueError(f"Candidate at index {index} is missing a valid slug.")
        if slug in seen_slugs:
            raise ValueError(f"Duplicate candidate slug found: {slug}")
        seen_slugs.add(slug)

    return candidates


def build_sitemap(candidates: list[dict], today: str) -> Element:
    """Build XML sitemap Element tree.

    Args:
        candidates: List of candidate dicts with 'slug' key.
        today: ISO date string for <lastmod>.

    Returns:
        Root <urlset> Element.
    """

    register_namespace("", SITEMAP_NS)
    root = Element(f"{{{SITEMAP_NS}}}urlset")

    def append_url(route: str, changefreq: str, priority: str) -> None:
        url_element = SubElement(root, f"{{{SITEMAP_NS}}}url")
        SubElement(url_element, f"{{{SITEMAP_NS}}}loc").text = f"{BASE_URL}{route}"
        SubElement(url_element, f"{{{SITEMAP_NS}}}lastmod").text = today
        SubElement(url_element, f"{{{SITEMAP_NS}}}changefreq").text = changefreq
        SubElement(url_element, f"{{{SITEMAP_NS}}}priority").text = priority

    for route in STATIC_ROUTES:
        append_url(route["loc"], route["changefreq"], route["priority"])

    for candidate in candidates:
        slug = candidate.get("slug")
        if not isinstance(slug, str) or not slug:
            raise ValueError("Each candidate must contain a non-empty 'slug'.")
        append_url(f"/candidato/{slug}", "daily", "0.9")

    for slug_a, slug_b in COMPARISON_PAIRS:
        append_url(f"/comparar/{slug_a}-vs-{slug_b}", "weekly", "0.8")

    return root


def write_sitemap(root: Element, output_path: Path) -> int:
    """Write sitemap XML to file.

    Args:
        root: Root Element.
        output_path: Destination file path.

    Returns:
        Number of URLs written.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    indent(root, space="  ")
    tree = ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return len(root.findall(f"{{{SITEMAP_NS}}}url"))


def main() -> None:
    """Entry point. Reads candidates, generates sitemap, prints summary."""

    repo_root = Path(__file__).resolve().parent.parent
    candidates = load_candidates(repo_root / "data")
    today = date.today().isoformat()
    sitemap_root = build_sitemap(candidates, today)
    count = write_sitemap(sitemap_root, repo_root / "site" / "public" / "sitemap.xml")
    print(f"sitemap.xml: {count} URLs generated")


if __name__ == "__main__":
    main()
