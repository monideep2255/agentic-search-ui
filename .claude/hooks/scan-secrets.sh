#!/bin/bash
# scope: project
# PreToolUse hook: block Bash commands containing secret patterns.
# Blocks commands containing API keys, tokens, or secrets.
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE '(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|AKIA[A-Z0-9]{16}|xox[bpras]-[a-zA-Z0-9-]+|PRIVATE KEY|(ANTHROPIC_API_KEY|OPENAI_API_KEY)=sk-[a-zA-Z0-9])'; then
  echo "BLOCKED: Command contains what looks like a secret/token. Use an environment variable instead." >&2
  exit 2
fi

exit 0
