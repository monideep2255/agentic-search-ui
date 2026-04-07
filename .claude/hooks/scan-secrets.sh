#!/bin/bash
# scope: project
# PreToolUse hook: block Bash commands containing secret patterns.
# Adapted from personal-os-work. Adds NCBI API key pattern (32-char hex).
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE '(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|xox[bpras]-[a-zA-Z0-9-]+|PRIVATE KEY|NCBI_API_KEY=[a-f0-9]{32})'; then
  echo "BLOCKED: Command contains what looks like a secret/token. Use an environment variable instead." >&2
  exit 2
fi

exit 0
