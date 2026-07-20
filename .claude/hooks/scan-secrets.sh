#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Bash) hook: block commands containing secret patterns.
# jq-free. Fails closed: if the command field cannot be parsed, scans the raw
# input so a token cannot slip through on a parse failure.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
COMMAND=$(json_field "$INPUT" tool_input.command)
[ -z "$COMMAND" ] && COMMAND="$INPUT"

if printf '%s' "$COMMAND" | grep -qE '(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|xox[bpras]-[a-zA-Z0-9-]+|PRIVATE KEY)'; then
  echo "BLOCKED: Command contains what looks like a secret/token. Use an environment variable instead." >&2
  exit 2
fi

exit 0
