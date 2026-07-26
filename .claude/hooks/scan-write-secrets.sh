#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Edit|Write) guard: block writing hardcoded secrets into config and
# source files. jq-free. Config files get both the token-prefix check and the
# secret-named-field heuristic (config holds literals, so the heuristic is safe).
# Source files get only the high-confidence token-prefix check, to avoid false
# positives on legitimate expressions like api_key = self.config.api_key.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
FILE_PATH=$(json_field "$INPUT" tool_input.file_path)
NP="$(printf '%s' "$FILE_PATH" | tr '\\' '/')"

CONTENT=$(json_field "$INPUT" tool_input.content)
NEW=$(json_field "$INPUT" tool_input.new_string)
BLOB="$CONTENT
$NEW"

PREFIX='(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|xox[bpras]-[a-zA-Z0-9-]+|PRIVATE KEY)'
# A secret-named field assigned a literal (non-${ENV}) value, JSON or .env style.
# A value beginning with $ or { is a reference and is allowed.
FIELD='(TOKEN|APIKEY|API_KEY|SECRET|PASSWORD|CREDENTIAL|_KEY)"?[[:space:]]*[:=][[:space:]]*"?[^$"{[:space:]][^"[:space:]]{11,}'

case "$NP" in
  # Config targets: run both checks.
  *.mcp.json|*.mcp.local.json|*.env|*.env.*|*/.env|*/settings.json|*/settings.local.json)
    if printf '%s' "$BLOB" | grep -qE "$PREFIX" || printf '%s' "$BLOB" | grep -qiE "$FIELD"; then
      echo 'BLOCKED: file content contains what looks like a hardcoded secret. Use ${ENV_VAR} references in config files, never literal tokens.' >&2
      exit 2
    fi
    ;;
  # Source and other tracked files: high-confidence token prefixes only.
  *.py|*.ts|*.tsx|*.js|*.jsx|*.yaml|*.yml|*.toml|*.sh|*Dockerfile|*.ini|*.cfg)
    if printf '%s' "$BLOB" | grep -qE "$PREFIX"; then
      echo 'BLOCKED: file content contains what looks like a hardcoded API token. Load it from the environment instead.' >&2
      exit 2
    fi
    ;;
  *) exit 0 ;;
esac

exit 0
