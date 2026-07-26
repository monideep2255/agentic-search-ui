#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Read, Bash) guard: block reading credential and private-key files.
# Closes the gap where a broad Read grant or an unscoped Bash(cat:*) allow rule
# could pull secrets (.ssh, .aws, .gnupg, .netrc, private keys) straight into the
# model's context with no scan. jq-free.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
FP=$(json_field "$INPUT" tool_input.file_path)
CMD=$(json_field "$INPUT" tool_input.command)

SENS='(/\.ssh/|/\.aws/|/\.gnupg/|/\.netrc|/\.docker/config\.json|id_rsa|id_ed25519|id_dsa|\.pem$|\.p12$|\.pfx$)'

# Read tool target.
if [ -n "$FP" ] && printf '%s' "$FP" | grep -qE "$SENS"; then
  echo 'Blocked: reading a credential or private-key file. Ask user first.' >&2
  exit 2
fi

# Bash reading a sensitive file (cat/head/tail/less/more/xxd/od/strings/base64/cp/scp).
if [ -n "$CMD" ] \
   && printf '%s' "$CMD" | grep -qE '(^|[;&|[:space:]])(cat|head|tail|less|more|xxd|od|strings|base64|cp|scp)[[:space:]]' \
   && printf '%s' "$CMD" | grep -qE "$SENS"; then
  echo 'Blocked: reading a credential or private-key file via bash. Ask user first.' >&2
  exit 2
fi

exit 0
