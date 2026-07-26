#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PostToolUse (Edit|Write) sync: regenerate AGENTS.md from CLAUDE.md so Codex,
# Gemini, and Copilot read the same instructions Claude Code does.
#
# Why only this file: .codex is a git-tracked symlink to .claude (mode 120000),
# so the config directory cannot drift. AGENTS.md is a real copy, which makes it
# the only surface where the two can diverge.
#
# Contract: only the repo-root CLAUDE.md triggers a sync. AGENTS.md keeps its own
# tool-neutral 3-line header; everything from line 4 onward is copied verbatim.
# The write is skipped when the result would be identical, so this is idempotent.
#
# This is a convenience sync, not a security gate. It always exits 0 and never
# blocks a write. Run it with --force to backfill or re-verify by hand; relying
# on a TTY check alone would silently no-op when called from a script or CI.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
SRC="$ROOT/CLAUDE.md"
DEST="$ROOT/AGENTS.md"

# The 3 header lines that make AGENTS.md tool-neutral. Line 2 is intentionally
# blank. Everything below these lines comes from CLAUDE.md unchanged.
HEADER='# AGENTS.md

Instructions for `agentic-search-ui`. For all AI agents (Gemini, Copilot, Codex, GPT, etc.). Exact same content as CLAUDE.md.'

# Manual run: --force works everywhere, including from a script or CI where
# stdin is redirected and a TTY check would wrongly fall through to parsing.
if [ "$1" = "--force" ] || [ -t 0 ]; then
  MATCHED=1
else
  MATCHED=0
  INPUT=$(cat)
  # Fast path: this hook runs on every Edit/Write in the repo, so bail out before
  # paying for a JSON parse (which spawns python) when the payload cannot
  # possibly be about CLAUDE.md. Any edit to it names the file in the payload.
  case "$INPUT" in
    *CLAUDE.md*) ;;
    *) exit 0 ;;
  esac
  FILE_PATH=$(json_field "$INPUT" tool_input.file_path)
  if [ -n "$FILE_PATH" ]; then
    case "$FILE_PATH" in
      /*) ABS="$FILE_PATH" ;;
      *) ABS="$ROOT/$FILE_PATH" ;;
    esac
    [ "$ABS" = "$SRC" ] && MATCHED=1
  else
    # json_field returned nothing (no working python, unparseable payload). Fall
    # back to a raw scan. A false positive here is harmless: regenerating
    # AGENTS.md from CLAUDE.md is idempotent and always yields the correct state.
    case "$INPUT" in
      *CLAUDE.md*) MATCHED=1 ;;
    esac
  fi
fi

[ "$MATCHED" = "1" ] || exit 0
[ -f "$SRC" ] || exit 0

# Command substitution strips trailing newlines from both sides, so the
# comparison is fair. The write reuses the same generator.
NEW=$(printf '%s\n' "$HEADER"; tail -n +4 "$SRC")
OLD=$(cat "$DEST" 2>/dev/null)

if [ "$NEW" != "$OLD" ]; then
  { printf '%s\n' "$HEADER"; tail -n +4 "$SRC"; } >"$DEST"
  echo "Synced AGENTS.md from CLAUDE.md (body now identical from line 4)." >&2
fi

exit 0
