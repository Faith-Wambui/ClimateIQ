"""
scripts/update_readme.py
────────────────────────
Auto-updates the README.md "Categories Tracked" and "Sources" sections
by reading directly from config/sources.py.

Usage:
    python scripts/update_readme.py

Run this whenever you add, remove, or edit sources or categories in
config/sources.py. The README will be updated automatically in place.
"""

import sys
import os
import re
from pathlib import Path

# ── Make sure we can import from the project root ────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.sources import RSS_FEEDS, CATEGORIES, CATEGORY_DESCRIPTIONS

README_PATH = ROOT / "README.md"

# ── Markers — these must exist in your README.md ─────────────────────────────
# The script replaces everything BETWEEN these comment tags.
# Do not remove or rename them in the README.

CATEGORIES_START = "<!-- AUTO:CATEGORIES_START -->"
CATEGORIES_END   = "<!-- AUTO:CATEGORIES_END -->"

SOURCES_START    = "<!-- AUTO:SOURCES_START -->"
SOURCES_END      = "<!-- AUTO:SOURCES_END -->"


def group_sources_by_category(feeds: list, categories: dict) -> dict:
    """Group RSS_FEEDS by their category_hint, putting None-hint feeds in 'other'."""
    grouped = {key: [] for key in categories}
    grouped.setdefault("other", [])

    for feed in feeds:
        hint = feed.get("category_hint") or "other"
        if hint not in grouped:
            hint = "other"
        grouped[hint].append(feed["name"])

    return grouped


def build_categories_table(categories: dict, descriptions: dict, grouped: dict) -> str:
    """Build the markdown categories table."""
    lines = []
    lines.append("| # | Category | Sources | Example Topics |")
    lines.append("|---|---|---|---|")

    for i, (key, label) in enumerate(categories.items(), start=1):
        description = descriptions.get(key, "")
        source_names = grouped.get(key, [])

        # Show up to 3 source names, then "+N more" if there are extras
        if len(source_names) == 0:
            sources_str = "—"
        elif len(source_names) <= 3:
            sources_str = ", ".join(source_names)
        else:
            visible = ", ".join(source_names[:3])
            sources_str = f"{visible} +{len(source_names) - 3} more"

        lines.append(f"| {i} | {label} | {sources_str} | {description} |")

    return "\n".join(lines)


def build_sources_table(feeds: list, categories: dict) -> str:
    """Build the full markdown sources table."""
    lines = []
    lines.append(f"| # | Source | Category | Feed URL |")
    lines.append("|---|---|---|---|")

    for i, feed in enumerate(feeds, start=1):
        name = feed["name"]
        url = feed["url"]
        hint = feed.get("category_hint") or "other"
        category_label = categories.get(hint, "🌐  General Climate News")
        lines.append(f"| {i} | {name} | {category_label} | [RSS]({url}) |")

    # Summary line
    lines.append(f"\n> **{len(feeds)} sources** across **{len(categories)} categories** — "
                 f"edit `config/sources.py` to add more.")

    return "\n".join(lines)


def replace_section(content: str, start_marker: str, end_marker: str, new_content: str) -> str:
    """Replace everything between start_marker and end_marker with new_content."""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL
    )

    replacement = f"{start_marker}\n\n{new_content}\n\n{end_marker}"

    if not pattern.search(content):
        print(f"⚠️  Warning: Could not find markers:\n   {start_marker}\n   {end_marker}")
        print("   Add these comment tags to your README.md to enable auto-update.")
        return content

    return pattern.sub(replacement, content)


def main():
    # ── Load README ───────────────────────────────────────────────────────────
    if not README_PATH.exists():
        print(f"❌ README.md not found at {README_PATH}")
        sys.exit(1)

    original = README_PATH.read_text(encoding="utf-8")

    # ── Build new content ─────────────────────────────────────────────────────
    grouped = group_sources_by_category(RSS_FEEDS, CATEGORIES)
    categories_table = build_categories_table(CATEGORIES, CATEGORY_DESCRIPTIONS, grouped)
    sources_table    = build_sources_table(RSS_FEEDS, CATEGORIES)

    # ── Replace sections ──────────────────────────────────────────────────────
    updated = replace_section(original, CATEGORIES_START, CATEGORIES_END, categories_table)
    updated = replace_section(updated,  SOURCES_START,    SOURCES_END,    sources_table)

    # ── Write back only if something changed ──────────────────────────────────
    if updated == original:
        print("✅ README.md is already up to date — no changes made.")
        return

    README_PATH.write_text(updated, encoding="utf-8")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("✅ README.md updated successfully!")
    print(f"   📊 {len(CATEGORIES)} categories")
    print(f"   📡 {len(RSS_FEEDS)} sources")
    print()
    print("   Sections updated:")
    print(f"   • Categories Tracked  ({CATEGORIES_START})")
    print(f"   • Sources             ({SOURCES_START})")


if __name__ == "__main__":
    main()