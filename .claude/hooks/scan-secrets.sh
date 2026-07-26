#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Bash) hook: block commands containing secret patterns.
# jq-free. Fails closed: if the command field cannot be parsed, scans the raw
# input so a token cannot slip through on a parse failure. Catches both known
# vendor token prefixes and this repo's secret-named-field shapes (PG_PASSWORD,
# AUTH_SECRET, NCBI_API_KEY, LANGSMITH_API_KEY) assigned a literal value.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
COMMAND=$(json_field "$INPUT" tool_input.command)
[ -z "$COMMAND" ] && COMMAND="$INPUT"

PREFIX='(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|xox[bpras]-[a-zA-Z0-9-]+|PRIVATE KEY)'
# A secret-named var assigned a literal value (export X=..., X=...). A value
# beginning with $ or { or ( or a quote-then-$ is a reference and is allowed.
FIELD='(TOKEN|APIKEY|API_KEY|SECRET|PASSWORD|CREDENTIAL|_KEY)"?[[:space:]]*=[[:space:]]*"?[^$"{()[:space:]][^"[:space:]]{7,}'

if printf '%s' "$COMMAND" | grep -qE "$PREFIX" || printf '%s' "$COMMAND" | grep -qiE "$FIELD"; then
  echo "BLOCKED: Command contains what looks like a secret/token. Use an environment variable instead." >&2
  exit 2
fi

exit 0
