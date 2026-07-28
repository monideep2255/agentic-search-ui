#!/usr/bin/env bash
# scope: project
# depends_on: [.gitignore]
# depended_by: [.claude/settings.json]
#
# SessionStart hook: detect macOS Finder/Archive Utility duplicate-copy
# artifacts (e.g. "env 2.py"). These appear when a file is copied into a
# folder that already has a same-named file (Finder "Keep Both", or a zip
# extracted over an existing folder), most often from moving work out of a
# bossman-mode worktree via Finder instead of git. .gitignore keeps them out
# of git; this hook verifies each match against its non-suffixed counterpart:
#
#   - Byte-identical to the counterpart: auto-moved to Trash (reversible,
#     never rm). Safe because content equality is checked, not just the
#     filename shape.
#   - Counterpart missing, or content differs: left untouched and flagged.
#     Not a simple duplicate; needs a human decision.
#
# NOTE: unlike Claude's own Bash tool calls, a SessionStart hook's internal
# commands are not gated by block-bash-delete.sh. The move-to-Trash branch
# below is the one place in this repo's hook set that mutates the filesystem
# unattended, and it was built and reviewed on that understanding (see the
# chore/auto-clear-duplicate-copies PR). It never calls rm; it only relocates
# verified-identical files to Trash.

REPO_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REPO_NAME="$(basename "$REPO_DIR")"
TRASH_DIR="$HOME/.Trash/${REPO_NAME}-dupes-$(date +%Y-%m-%d)"

MATCHES=$(find "$REPO_DIR" \
  \( -path "$REPO_DIR/.git" -o -path "$REPO_DIR/node_modules" \
     -o -path "$REPO_DIR/venv" -o -path "$REPO_DIR/.venv" \
     -o -path "$REPO_DIR/.claude/worktrees" -o -name "__pycache__" \) -prune -o \
  -type f -print 2>/dev/null | grep -E ' [0-9]+\.[A-Za-z0-9]+$')

[ -z "$MATCHES" ] && exit 0

AUTO_MOVED=""
FLAGGED=""

while IFS= read -r path; do
  [ -z "$path" ] && continue
  dir="$(dirname "$path")"
  base="$(basename "$path")"
  counterpart_base="$(printf '%s' "$base" | sed -E 's/ [0-9]+(\.[A-Za-z0-9]+)$/\1/')"
  counterpart="$dir/$counterpart_base"
  relative="${path#"$REPO_DIR"/}"

  if [ -f "$counterpart" ] && cmp -s "$path" "$counterpart"; then
    rel_dir="$(dirname "$relative")"
    mkdir -p "$TRASH_DIR/$rel_dir"
    mv -n "$path" "$TRASH_DIR/$relative" 2>/dev/null
    AUTO_MOVED="$AUTO_MOVED
  - $relative"
  else
    FLAGGED="$FLAGGED
  - $relative"
  fi
done <<< "$MATCHES"

if [ -n "$AUTO_MOVED" ]; then
  echo "Auto-moved to Trash (byte-identical to their non-suffixed counterpart):"
  echo "$AUTO_MOVED"
  echo "  -> $TRASH_DIR"
  echo ""
fi

if [ -n "$FLAGGED" ]; then
  echo "WARNING: duplicate-copy-shaped file(s) found that could NOT be auto-verified:"
  echo "$FLAGGED"
  echo ""
  echo "Counterpart missing or content differs. Review manually before deciding."
fi

exit 0
