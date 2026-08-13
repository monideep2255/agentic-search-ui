#!/usr/bin/env python3
"""Generate the publishable prototype page from the Claude Design card.

The prototype exists once, at `design-system/prototype/app.html`, because that
is the file the Claude Design project renders and the file the product owner
edits. Publishing it as a Claude artifact needs a slightly different shape:
the artifact host supplies its own `<!doctype html>`, `<head>` and `<body>`,
so a page that brings its own would end up nested inside them.

This script does that one transform and nothing else. It exists so the two
copies can never drift: `Phase_4.8_prototype.html` is generated, never edited
by hand, and is regenerated after every pull from Claude Design.

Usage:
    python3 docs/build/design/make_prototype_artifact.py

Reads:
    docs/build/design/design-system/prototype/app.html

Writes:
    docs/build/design/Phase_4.8_prototype.html   (generated, do not hand-edit)
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "design-system" / "prototype" / "app.html"
TARGET = HERE / "Phase_4.8_prototype.html"

BANNER = (
    "<!-- GENERATED FILE. Do not edit.\n"
    "     Source: docs/build/design/design-system/prototype/app.html\n"
    "     Regenerate: python3 docs/build/design/make_prototype_artifact.py -->\n"
)


def extract(pattern: str, text: str, what: str) -> str:
    match = re.search(pattern, text, re.S | re.I)
    if match is None:
        sys.exit(f"error: could not find the {what} in {SOURCE}")
    return match.group(1)


def main() -> None:
    if not SOURCE.exists():
        sys.exit(f"error: {SOURCE} does not exist")

    source = SOURCE.read_text(encoding="utf-8")

    title = extract(r"<title>(.*?)</title>", source, "<title>")
    style = extract(r"<style>(.*?)</style>", source, "<style> block")
    body = extract(r"<body[^>]*>(.*?)</body>", source, "<body> content")

    # The body already carries the page's own <script>; nothing else to move.
    page = (
        f"{BANNER}"
        f"<title>{title}</title>\n\n"
        f"<style>{style}</style>\n"
        f"{body.strip()}\n"
    )

    TARGET.write_text(page, encoding="utf-8")

    # A nested <html> or <body> in the output is the exact failure this script
    # exists to prevent, so fail loudly rather than publish a broken page.
    for tag in ("<!doctype", "<html", "<head", "<body"):
        if tag in page.lower():
            sys.exit(f"error: generated page still contains {tag!r}")

    print(f"wrote {TARGET.relative_to(HERE.parent.parent.parent)}  ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
