#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Bash) guard: block file deletion via rm/rmdir. Ask the user first.
# Makes the file-protection.md rule structurally enforced rather than only
# model-obeyed. jq-free, fails closed on parse failure.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
CMD=$(json_field "$INPUT" tool_input.command)
[ -z "$CMD" ] && CMD="$INPUT"

# Match rm / rm - / rmdir at command start or after a shell separator (; & | &&).
if printf '%s' "$CMD" | grep -qE '(^|[;&|][[:space:]]*)(rm|rmdir)([[:space:]]|-)'; then
  echo 'Blocked: file deletion via bash. Ask user first.' >&2
  exit 2
fi

exit 0
