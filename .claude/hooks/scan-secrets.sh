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
# A search names a field in order to find it, so the field check skips a
# command whose first word is grep, rg or git grep, and scans every other
# command as today. A chain counts as several commands: it is split on ; & |
# ( ) ` and newlines, the searches it starts with are skipped, and everything
# from its first other command to the end is field-checked as one text. So
# "grep x f; export NCBI_API_KEY=<literal>" is still caught, a value holding a
# separator is still read whole, and a search after another command is still
# checked. The split ignores quotes: a separator inside a search's quoted
# pattern can make the rest of the pattern read as a command, which blocks
# more, never less. The token-prefix check still runs on the whole command, a
# search included. Approved item by item by the product owner on 2026-09-25
# (DECISIONS.md, "Four security-layer changes approved item by item", item 2).
# tests/ci/test_claude_hooks.py pins it.

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

# Is this command's first word grep, rg or git grep? Leading whitespace is
# ignored. Any other first word, egrep included, is not a search.
is_search() {
  local cmd=$1 rest
  cmd=${cmd#"${cmd%%[![:space:]]*}"}
  case $cmd in
    grep|rg|grep[[:space:]]*|rg[[:space:]]*) return 0 ;;
    git[[:space:]]*)
      rest=${cmd#git}
      rest=${rest#"${rest%%[![:space:]]*}"}
      case $rest in
        grep|grep[[:space:]]*) return 0 ;;
      esac
      ;;
  esac
  return 1
}

# What the field check reads: the whole command, unless the command starts
# with a search. Then the leading searches (and the empty pieces between two
# separators, as in &&) are dropped, and the text from the first other piece
# to the end is kept whole, separators included, so a literal that holds a
# separator is never cut short.
SEPARATORS=$';&|()`\n'
TRIMMED=${COMMAND#"${COMMAND%%[![:space:]]*}"}
FIELD_TEXT=$COMMAND
if is_search "${TRIMMED%%[$SEPARATORS]*}"; then
  FIELD_TEXT=
  REST=$TRIMMED
  while :; do
    PIECE=${REST%%[$SEPARATORS]*}
    case $PIECE in
      *[![:space:]]*) is_search "$PIECE" || { FIELD_TEXT=$REST; break; } ;;
    esac
    [ "$PIECE" = "$REST" ] && break
    REST=${REST:${#PIECE}+1}
  done
fi

if printf '%s' "$COMMAND" | grep -qE "$PREFIX" \
   || { [ -n "$FIELD_TEXT" ] && printf '%s' "$FIELD_TEXT" | grep -qiE "$FIELD"; }; then
  echo "BLOCKED: Command contains what looks like a secret/token. Use an environment variable instead." >&2
  exit 2
fi

exit 0
