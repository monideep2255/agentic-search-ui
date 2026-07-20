#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Edit|Write) guard: block writing hardcoded secrets into sensitive
# config files. Closes the gap where scan-secrets.sh only inspected Bash commands,
# not file contents. jq-free, targeted to config targets to avoid false positives
# on documentation that merely discusses tokens.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
FILE_PATH=$(json_field "$INPUT" tool_input.file_path)
NP="$(printf '%s' "$FILE_PATH" | tr '\\' '/')"

# Only scan sensitive config targets.
case "$NP" in
  *.mcp.json|*.env|*/settings.json|*/settings.local.json|*.mcp.local.json) ;;
  *) exit 0 ;;
esac

CONTENT=$(json_field "$INPUT" tool_input.content)
NEW=$(json_field "$INPUT" tool_input.new_string)
BLOB="$CONTENT
$NEW"

# 1) Known token prefixes.
# 2) A token-named field assigned a literal (non-${ENV}) value, in either JSON
#    style ("X_TOKEN": "MDYx...") or .env style (X_TOKEN=MDYx...). A value that
#    begins with $ or { (i.e. ${VAR}) is treated as a reference and allowed.
if printf '%s' "$BLOB" | grep -qE '(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|xox[bpras]-[a-zA-Z0-9-]+|PRIVATE KEY)' \
   || printf '%s' "$BLOB" | grep -qiE '(TOKEN|APIKEY|API_KEY|SECRET|PASSWORD|CREDENTIAL|_KEY)"?[[:space:]]*[:=][[:space:]]*"?[^$"{[:space:]][^"[:space:]]{11,}'; then
  echo 'BLOCKED: file content contains what looks like a hardcoded secret. Use ${ENV_VAR} references in config files, never literal tokens.' >&2
  exit 2
fi

exit 0
