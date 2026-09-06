"""Fail when a frontend component uses a colour the design system does not have.

Why this exists, and why it is a script rather than a rule: on 2026-09-05 the
lead wrote `.claude/rules/design-consistency.md`, then broke it three hours
later by inventing a mobile app bar while a design for it existed in
`docs/build/design/design-system/prototype/app.html`. A rule is an instruction
a model chooses to obey. This is a check that fails.

WHAT IT CHECKS, deliberately narrow so it stays worth keeping: every hex colour
literal in a frontend component must be a value that already exists in
`designTokens` in `frontend/src/theme.ts`. It does NOT demand that components
reference the token by name. Requiring that would fail 30 places on the first
run, 18 of them plain white used as contrast text on navy, and a check that
fires 30 times on day one gets switched off rather than fixed.

WHAT IT DOES NOT CHECK, stated so a reader can tell what a green run means,
per `.claude/rules/goal-contracts.md`'s requirement that a verify surface state
its own coverage:

- Whether the right token was chosen. `designTokens.risk` used as an accent
  passes here and is still wrong.
- Spacing, type sizes, radii and shadows. Only colour.
- `rgb()`, `rgba()` and `hsl()` literals. MUI's own overlays use rgba for
  translucency over navy, which no flat token can express, so requiring a
  token there would be requiring the impossible.
- CSS files. `frontend/src/index.css` is not scanned.
- Anything inside a comment. Comments are stripped before scanning, because
  the first version of this script did not strip them and produced seven
  findings of which five were prose EXPLAINING a contrast measurement, for
  example `PersonaChip.tsx` naming `#36659E` while its code correctly uses
  `designTokens.inkOnNavy`. A check that flags the people who documented
  their reasoning best is worse than no check, because it teaches everyone
  to ignore it.
- Anything outside `frontend/src`.

So a green run means "no component invented a colour", not "the design system
is being followed".

Depends on:
    - Nothing. Standard library only, matching `tracker/check_doc_drift.py`.

Reads:
    - frontend/src/theme.ts
    - frontend/src/**/*.ts, *.tsx, excluding tests

Writes:
    - Nothing. Exit code 1 on a violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "frontend" / "src" / "theme.ts"
SRC = REPO / "frontend" / "src"

HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")

# Comments first, so a hex quoted in prose about a contrast ratio is not read
# as a colour the component uses. Block comments are removed whole, then line
# comments to end of line. Neither form is nested in this codebase.
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"//[^\n]*")


def strip_comments(source: str) -> str:
    """Blank out comments while preserving line numbering.

    Newlines inside a removed block are kept so a reported line number still
    points at the right line of the original file.
    """
    def blank(match: re.Match[str]) -> str:
        return "".join(ch if ch == "\n" else " " for ch in match.group(0))

    return LINE_COMMENT.sub(blank, BLOCK_COMMENT.sub(blank, source))

# `transparent` and the two shorthand forms of white are spelled several ways
# and all resolve to a value the palette already carries.
ALWAYS_ALLOWED = {"#FFF", "#FFFF", "#FFFFFF", "#FFFFFFFF"}


def palette() -> set[str]:
    """Every hex value `designTokens` defines, upper-cased for comparison."""
    if not THEME.exists():
        raise SystemExit(f"error: {THEME} not found")
    body = THEME.read_text(encoding="utf-8")
    start = body.find("export const designTokens")
    if start == -1:
        raise SystemExit("error: designTokens not found in theme.ts")
    end = body.find("} as const;", start)
    if end == -1:
        raise SystemExit("error: could not find the end of designTokens")
    return {m.group(0).upper() for m in HEX.finditer(body[start:end])}


def scanned_files() -> list[Path]:
    out: list[Path] = []
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if path == THEME:
            continue
        if ".test." in path.name or path.name.endswith(".d.ts"):
            continue
        out.append(path)
    return out


def main() -> int:
    known = palette() | ALWAYS_ALLOWED
    if len(known) < 10:
        # A palette that parsed to almost nothing would make every file pass.
        # An arm that cannot distinguish "clean" from "I read nothing" is not
        # an arm, which is this repository's own populate-check discipline.
        raise SystemExit(f"error: palette parsed to only {len(known)} values, refusing to run")

    violations: list[tuple[Path, int, str]] = []
    for path in scanned_files():
        source = strip_comments(path.read_text(encoding="utf-8"))
        for lineno, line in enumerate(source.splitlines(), 1):
            for match in HEX.finditer(line):
                value = match.group(0).upper()
                if value not in known:
                    violations.append((path.relative_to(REPO), lineno, match.group(0)))

    if not violations:
        print(f"ok: {len(scanned_files())} files scanned against {len(known)} palette values, 0 invented colours")
        return 0

    print(f"error: {len(violations)} colour(s) not in the design system palette")
    for path, lineno, value in violations:
        print(f"  {path}:{lineno}: {value}")
    print()
    print("Every colour must already exist in designTokens (frontend/src/theme.ts).")
    print("If the design genuinely needs a new colour, add it to designTokens first,")
    print("which is the 'Ask' state in .claude/rules/design-consistency.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
