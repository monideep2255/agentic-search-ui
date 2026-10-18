#!/usr/bin/env python3
"""Fail CI when the built web app drops its bundled libraries' license notices.

Card 60, the attribution work of 2026-09-27, in two passes.

Pass one: React, React DOM, its scheduler and MUI are MIT licensed, and MIT
requires their copyright and permission notices to travel with every copy.
`npm run build` minifies the client bundle with Oxc through Rolldown (Vite
8.1.5), and the default there strips every `@license` comment, so a local
build was found to carry zero of them in `dist/assets/index-*.js`. Every
visitor's copy of the app then shipped with no attribution at all.
`frontend/vite.config.ts` now asks Rolldown's output to keep legal comments
(`comments.legal`), which fixes React, react-dom, and the scheduler: Meta's
own build already puts an `@license React` comment in every one of their
files, and `comments.legal` is what keeps it from being stripped.

Pass two: MUI's compiled output carries no `@license` comment at all, so
`comments.legal` alone still drops MUI's notice, and the same is true of
every other MIT dependency in the bundle that never wrote itself a source
comment. `comments.legal` only preserves a comment that exists; it cannot
manufacture one. So `vite.config.ts` also gained a small build plugin that
reads each bundled package's own LICENSE file off disk and writes every one
of them into `dist/THIRD_PARTY_NOTICES.txt`. This script now checks both
halves of the fix: the source-comment survival check from pass one, and the
notices file's presence and content from pass two.

Deny-by-default, the same shape as `assert_no_db_skips.py`: the check is not
"does the bundle look clean", it is "can I find the specific evidence that
proves the notices survived". Anything else, including an empty or missing
build directory or a missing notices file, is a failure rather than a pass,
because "I could not verify X" is a fail here as everywhere else in this gate
suite.

Usage:
    python .github/scripts/assert_license_notices.py <dist-dir>

Exit codes:
    0  the built JavaScript still carries a react/react-dom source notice, AND
       dist/THIRD_PARTY_NOTICES.txt exists with a non-empty license entry for
       react, react-dom, and @mui/material, and no entry for any package carries
       the "no license file found" placeholder
    1  either half of that is missing

Depends on:
    - Nothing outside the standard library.

Reads:
    - Every `*.js` file directly inside `<dist-dir>/assets`.
    - `<dist-dir>/THIRD_PARTY_NOTICES.txt`.

Writes:
    - Nothing. Prints to stdout and stderr only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# React and react-dom both ship the same header shape across every file this
# build produces (react.production.js, scheduler.production.js,
# react-dom.production.js, react-dom-client.production.js, react-is,
# react-jsx-runtime.production.js): a comment block starting "@license React".
# That single marker is what the card itself names as proof, and it is common
# to both packages, so one pattern covers both without guessing at MUI's or
# the scheduler's own comment wording.
_MARKER = "@license React"

# The three packages the card names by name. Any one of them missing a real
# notice in THIRD_PARTY_NOTICES.txt is the exact regression this half of the
# script exists to catch.
_REQUIRED_NOTICE_PACKAGES = ("react", "react-dom", "@mui/material")

# frontend/vite.config.ts's thirdPartyNoticesPlugin writes this literal
# placeholder for a package with no license file. Seeing it for ANY package
# is a failure (card 86): MIT requires the text to travel with every copy,
# and clsx once shipped the placeholder on Linux because its file is named
# `license` in lowercase. A new dependency with no license file fails here
# instead of shipping a placeholder.
_NO_LICENSE_FOUND_PLACEHOLDER = "no license file found"

_SECTION_DELIMITER_RE = re.compile(r"^={80}$", re.MULTILINE)
_ENTRY_RE = re.compile(
    r"PACKAGE:\s*(?P<name>.+)\nVERSION:\s*(?P<version>.+)\nLICENSE:\n(?P<license>.*)",
    re.DOTALL,
)


def find_offending_or_missing(assets_dir: Path) -> tuple[list[Path], str | None]:
    """Return (js files found, error) for the given directory.

    `error` is set, and the file list may be empty, whenever the directory
    itself cannot be trusted to have been built: missing entirely, or built
    but holding no JavaScript at all. Both are failures, never a pass, since
    neither one tells us anything about whether the notices survived.
    """
    if not assets_dir.is_dir():
        return [], f"the build output directory {assets_dir} does not exist"
    js_files = sorted(assets_dir.glob("*.js"))
    if not js_files:
        return [], f"{assets_dir} holds no *.js file; the build did not run or produced nothing"
    return js_files, None


def parse_notices(text: str) -> dict[str, tuple[str, str]]:
    """Return {package name: (version, license text)} parsed from a notices file.

    A section this parser cannot make sense of is skipped rather than raised.
    That is not a silent pass: a section that fails to parse is a section
    whose package name never lands in the returned mapping, so any required
    package inside it is correctly reported as missing by the caller.
    """
    entries: dict[str, tuple[str, str]] = {}
    for raw_section in _SECTION_DELIMITER_RE.split(text):
        section = raw_section.strip()
        if not section:
            continue
        match = _ENTRY_RE.match(section)
        if not match:
            continue
        name = match.group("name").strip()
        version = match.group("version").strip()
        license_text = match.group("license").strip()
        entries[name] = (version, license_text)
    return entries


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <dist-dir>", file=sys.stderr)
        return 1

    dist_dir = Path(argv[1])
    failures: list[str] = []

    # --- Half one: the source-comment survival check (card 60, pass one). ---
    assets_dir = dist_dir / "assets"
    js_files, error = find_offending_or_missing(assets_dir)
    if error:
        failures.append(f"{error}. This script verified nothing, which is a failure.")
    else:
        carrying_notice = []
        for js_file in js_files:
            try:
                text = js_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                failures.append(f"cannot read {js_file}: {exc}")
                continue
            if _MARKER in text:
                carrying_notice.append(js_file)
        if not carrying_notice:
            failures.append(
                f"none of {len(js_files)} built JavaScript file(s) under {assets_dir} carry a "
                f"{_MARKER!r} notice. React, React DOM, and their scheduler are MIT licensed, "
                f"and MIT requires their copyright and permission notices to travel with every "
                f"copy. Check that frontend/vite.config.ts still sets "
                f"build.rolldownOptions.output.comments.legal so Rolldown stops stripping legal "
                f"comments from the minified bundle."
            )

    # --- Half two: the third-party notices file (card 60, pass two). ---
    notices_path = dist_dir / "THIRD_PARTY_NOTICES.txt"
    if not notices_path.is_file():
        failures.append(
            f"{notices_path} does not exist. MUI (and every other MIT dependency with no "
            f"source @license comment) has no notice anywhere in the build without it. Check "
            f"that frontend/vite.config.ts still registers thirdPartyNoticesPlugin()."
        )
    else:
        try:
            notices_text = notices_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failures.append(f"cannot read {notices_path}: {exc}")
        else:
            entries = parse_notices(notices_text)
            for name in _REQUIRED_NOTICE_PACKAGES:
                if name not in entries:
                    failures.append(
                        f"{notices_path} carries no entry for required package {name!r}."
                    )
                    continue
                _version, license_text = entries[name]
                if not license_text:
                    failures.append(
                        f"{notices_path}'s entry for {name!r} has no usable license text "
                        f"(found {license_text!r})."
                    )
            for name, (_version, license_text) in entries.items():
                if license_text == _NO_LICENSE_FOUND_PLACEHOLDER:
                    failures.append(
                        f"{notices_path}'s entry for {name!r} carries the "
                        f"{_NO_LICENSE_FOUND_PLACEHOLDER!r} placeholder instead of license text."
                    )

    if failures:
        print(
            f"FAIL: the built web app does not keep its libraries' license notices "
            f"({len(failures)} problem(s)):",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(
        f"ok: {len(js_files)} built JavaScript file(s) carry a {_MARKER!r} notice, and "
        f"{notices_path} carries a usable entry for every one of {_REQUIRED_NOTICE_PACKAGES}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
