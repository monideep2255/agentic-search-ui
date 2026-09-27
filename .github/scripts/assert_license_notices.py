#!/usr/bin/env python3
"""Fail CI when the built web app drops its bundled libraries' license notices.

Card 60, the attribution work of 2026-09-27: React, React DOM, its scheduler
and MUI are MIT licensed, and MIT requires their copyright and permission
notices to travel with every copy. `npm run build` minifies the client bundle
with Oxc through Rolldown (Vite 8.1.5), and the default there strips every
`@license` comment, so a local build was found to carry zero of them in
`dist/assets/index-*.js`. Every visitor's copy of the app then shipped with no
attribution at all.

`frontend/vite.config.ts` now asks Rolldown's output to keep legal comments
(`comments.legal`), which is the fix. This script is the gate that proves the
fix stays applied: it fails a build the moment the notices disappear again,
whether from a future Vite or Rolldown upgrade that changes the default, or
from someone reverting the `vite.config.ts` setting to "clean up" the bundle.

Deny-by-default, the same shape as `assert_no_db_skips.py`: the check is not
"does the bundle look clean", it is "can I find the one marker that proves the
notices survived". Anything else, including an empty or missing build
directory, is a failure rather than a pass, because "I could not verify X" is
a fail here as everywhere else in this gate suite.

Usage:
    python .github/scripts/assert_license_notices.py <dist-assets-dir>

Exit codes:
    0  at least one built JavaScript file carries a react or react-dom notice
    1  no built JavaScript file does, the directory is missing, or it holds no
       JavaScript file at all

Depends on:
    - Nothing outside the standard library.

Reads:
    - Every `*.js` file directly inside the given directory (`dist/assets` in
      this repository's frontend build).

Writes:
    - Nothing. Prints to stdout and stderr only.
"""

from __future__ import annotations

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


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <dist-assets-dir>", file=sys.stderr)
        return 1

    assets_dir = Path(argv[1])
    js_files, error = find_offending_or_missing(assets_dir)
    if error:
        print(f"FAIL: {error}. This script verified nothing, which is a failure.", file=sys.stderr)
        return 1

    carrying_notice = []
    for js_file in js_files:
        try:
            text = js_file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"FAIL: cannot read {js_file}: {exc}", file=sys.stderr)
            return 1
        if _MARKER in text:
            carrying_notice.append(js_file)

    if not carrying_notice:
        print(
            f"FAIL: none of {len(js_files)} built JavaScript file(s) under {assets_dir} "
            f"carry a {_MARKER!r} notice. React, React DOM, and their scheduler are MIT "
            f"licensed, and MIT requires their copyright and permission notices to "
            f"travel with every copy. Check that frontend/vite.config.ts still sets "
            f"build.rolldownOptions.output.comments.legal (or an equivalent setting) so "
            f"Rolldown stops stripping legal comments from the minified bundle.",
            file=sys.stderr,
        )
        for js_file in js_files:
            print(f"  checked: {js_file}", file=sys.stderr)
        return 1

    print(
        f"ok: {len(carrying_notice)} of {len(js_files)} built JavaScript file(s) carry a "
        f"{_MARKER!r} notice"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
