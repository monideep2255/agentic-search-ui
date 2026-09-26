#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh, tracker/render_board.py]
# depended_by: [.claude/skills/task-tracker/SKILL.md]
# NOT WIRED since 2026-09-26: its PostToolUse entry was removed from
# .claude/settings.json, approved item by item by the product owner on
# 2026-09-25 (DECISIONS.md, "Four security-layer changes approved item by
# item", item 4). The file stays for history and runs only by hand, with --force.
# PostToolUse (Edit|Write) sync: regenerate the kanban views whenever an agent
# edits the board markdown, so the page the product owner reads is never stale.
#
# Why this exists: the board is the team's shared point of reference. An agent
# picks up a ticket and sets it in-progress, and the view must follow without
# anyone remembering to run a command. A board that needs a manual refresh is a
# board that is quietly wrong most of the time.
#
# Contract: any Edit or Write under tracker/ that touches a .md file triggers a
# re-render of tracker/board.html and tracker/board.body.html from
# tracker/BOARD.md. The renderer is idempotent, so a false positive is harmless.
#
# KNOWN HOLE, learned the hard way on 2026-07-26: PostToolUse fires on the Edit
# and Write tools only. An edit made through Bash (sed, awk, a heredoc) bypasses
# this hook entirely and leaves the HTML stale. That exact failure hit AGENTS.md
# in this repo and is recorded in LEARNINGS.md. Two mitigations: prefer Edit for
# board files, and bossman-mode re-runs the renderer explicitly at phase close as
# a backstop rather than trusting the hook alone.
#
# This is a convenience sync, not a security gate. It always exits 0 and never
# blocks a write. Run with --force to re-render by hand.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
RENDERER="$ROOT/tracker/render_board.py"
BOARD="$ROOT/tracker/BOARD.md"

if [ "$1" = "--force" ] || [ -t 0 ]; then
  MATCHED=1
else
  MATCHED=0
  INPUT=$(cat)
  # Fast path: this hook runs on every Edit/Write in the repo, so bail out before
  # paying for a JSON parse when the payload cannot possibly be about the board.
  case "$INPUT" in
    *tracker/*) ;;
    *) exit 0 ;;
  esac
  FILE_PATH=$(json_field "$INPUT" tool_input.file_path)
  if [ -n "$FILE_PATH" ]; then
    case "$FILE_PATH" in
      */tracker/*.md) MATCHED=1 ;;
    esac
  else
    # No working python or an unparseable payload. Fall back to a raw scan. A
    # false positive is harmless because the renderer is idempotent.
    case "$INPUT" in
      *tracker/*.md*) MATCHED=1 ;;
    esac
  fi
fi

[ "$MATCHED" = "1" ] || exit 0
[ -f "$RENDERER" ] || exit 0
[ -f "$BOARD" ] || exit 0

PY=$(command -v python3 || true)
[ -n "$PY" ] || exit 0

# Capture output so a malformed board reports loudly instead of failing silently.
# The renderer exits non-zero and writes nothing when the board cannot be parsed,
# which is the correct behaviour: a stale page beats a page missing a phase.
if OUT=$("$PY" "$RENDERER" 2>&1); then
  echo "Board synced: ${OUT%%$'\n'*}" >&2
else
  echo "Board NOT synced, tracker/BOARD.md is malformed:" >&2
  echo "$OUT" >&2
fi

exit 0
