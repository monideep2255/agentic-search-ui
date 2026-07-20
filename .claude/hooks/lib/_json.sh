#!/usr/bin/env bash
# scope: project
# depends_on: []
# depended_by: [.claude/hooks/scan-secrets.sh, .claude/hooks/scan-write-secrets.sh, .claude/hooks/block-bash-delete.sh]
# Portable JSON helpers for Claude Code hooks. No jq, no python3-by-name dependency.
#
# Why this exists: on Windows/Git Bash, `jq` is often absent and `python3` resolves
# to the Microsoft Store stub that prints a message and exits non-zero instead of
# running. Every guard hook used to parse its stdin with `jq`, so all of them
# failed OPEN (exit 0 = passed through) when jq was missing, silently disabling the
# write-protection, secret-scan, and deletion guards. These helpers remove that
# dependency and let the gates fail CLOSED.
#
# Usage:
#   source "$(dirname "$0")/lib/_json.sh"
#   INPUT=$(cat)
#   fp=$(json_field "$INPUT" tool_input.file_path)

# Pick a Python that actually executes (not the Store stub). Empty if none works.
_hook_python() {
  local c
  for c in python python3 py; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then
      printf '%s' "$c"
      return 0
    fi
  done
  return 1
}

# Extract a dotted field (e.g. tool_input.file_path) from a JSON string.
# Prints the string value, or nothing if absent/unparseable. Never errors.
json_field() {
  local input="$1" path="$2" py
  py="$(_hook_python)" || py=""
  if [ -n "$py" ]; then
    printf '%s' "$input" | "$py" -c '
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cur = data
for part in sys.argv[1].split("."):
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        sys.exit(0)
if cur is None:
    sys.exit(0)
sys.stdout.write(cur if isinstance(cur, str) else json.dumps(cur))
' "$path"
    return 0
  fi
  # Fallback: naive sed on the last key segment. Does not handle escaped quotes,
  # so it is a best-effort net only; gates that call this must fail closed when
  # the value is empty but the raw input still references a protected target.
  local key="${path##*.}"
  printf '%s' "$input" | sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}
