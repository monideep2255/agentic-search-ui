#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json, tests/ci/test_claude_hooks.py]
# PreToolUse (Bash) hook: block commands containing secret patterns.
# jq-free. Fails closed: if the command field cannot be parsed, scans the raw
# input so a token cannot slip through on a parse failure. Catches both known
# vendor token prefixes and this repo's secret-named-field shapes (PG_PASSWORD,
# AUTH_SECRET, NCBI_API_KEY, LANGSMITH_API_KEY) assigned a literal value.
#
# A search names a field in order to find it, so for a command whose first word
# is grep, rg or git grep the field check is skipped. The token-prefix check
# still runs on every command, a search included. Approved item by item by the
# product owner on 2026-09-25 (DECISIONS.md, "Four security-layer changes
# approved item by item", item 2). tests/ci/test_claude_hooks.py pins it.

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

# Is the first word grep, rg or git grep? Leading whitespace is ignored. Any
# other first word, including egrep or a cd before the grep, is not a search.
TRIMMED=${COMMAND#"${COMMAND%%[![:space:]]*}"}
SEARCH=0
case $TRIMMED in
  grep|rg|grep[[:space:]]*|rg[[:space:]]*) SEARCH=1 ;;
  git[[:space:]]*)
    REST=${TRIMMED#git}
    REST=${REST#"${REST%%[![:space:]]*}"}
    case $REST in
      grep|grep[[:space:]]*) SEARCH=1 ;;
    esac
    ;;
esac

if printf '%s' "$COMMAND" | grep -qE "$PREFIX" \
   || { [ "$SEARCH" = 0 ] && printf '%s' "$COMMAND" | grep -qiE "$FIELD"; }; then
  echo "BLOCKED: Command contains what looks like a secret/token. Use an environment variable instead." >&2
  exit 2
fi

exit 0
