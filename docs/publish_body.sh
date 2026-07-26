#!/usr/bin/env bash
# Extract the publishable body from a standalone HTML page in this repo.
#
# Why this exists: the local file is the source of truth. It is version
# controlled, it survives the session, and it is what the product owner actually
# opens. The published artifact is derived from it, never the other way round.
#
# An earlier version of this workflow had it backwards, with a scratchpad file as
# the source and the repo copy generated from it. That put the real source in a
# temporary directory that disappears when the session ends, and it meant the
# local page could silently fall behind the published one.
#
# The artifact publisher wraps its input in its own document shell, so the body
# it receives must carry no doctype, html, head, or body tags of its own. This
# script strips exactly those, plus the standalone-only theme toggle.
#
# Usage:
#   docs/publish_body.sh docs/build/Phase_6_execution_flow.html
#     -> writes docs/Phase_6_execution_flow.body.html, then publish that file.
set -euo pipefail

SRC="${1:-}"
if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "usage: $0 <standalone.html> [output-path]" >&2
  exit 2
fi

# The fragment is a transient input to the publisher, not an artifact. It goes to
# a temp path by default so the repo never carries two near-identical HTML files
# side by side, which is exactly the clutter that prompted this change.
OUT="${2:-${TMPDIR:-/tmp}/$(basename "${SRC%.html}").body.html}"

# Take everything between the standalone wrapper's <body> open and its closing
# script block. awk keeps this a single pass with no temp files.
awk '
  /<button class="theme-toggle"/ { started = 1; next }
  /^<script>$/ && started && seen_wrap_end { exit }
  /^<\/body>$/ { exit }
  started { print }
' "$SRC" > "$OUT"

# Drop the trailing theme-toggle script that only the standalone page needs, put
# the title back (it lived in the head we just stripped, and the published page
# needs it to name the browser tab), and trim leading blank lines.
python3 - "$SRC" "$OUT" <<'PY'
import re, sys
src, out = sys.argv[1], sys.argv[2]
s = open(out, encoding="utf-8").read()
s = re.sub(r'<script>\s*\(function \(\) \{\s*var root = document\.documentElement;.*?</script>\s*$',
           '', s, flags=re.S)
title = re.search(r'<title>(.*?)</title>', open(src, encoding="utf-8").read(), re.S)
s = s.lstrip("\n")
if title and "<title>" not in s:
    s = f"<title>{title.group(1)}</title>\n\n" + s
open(out, "w", encoding="utf-8").write(s.rstrip() + "\n")
PY

LINES=$(wc -l < "$OUT" | tr -d ' ')
echo "wrote $OUT ($LINES lines)"

# Guard: the publisher rejects a body carrying its own document shell.
for tag in '<!doctype' '<html' '<head>' '<body>'; do
  if grep -qi -- "$tag" "$OUT"; then
    echo "error: $OUT still contains $tag; it must be a fragment" >&2
    exit 1
  fi
done
grep -q '<title>' "$OUT" || echo "note: no <title> in the body; pass one to the publisher" >&2
echo "ok: fragment is clean, publish $OUT"
