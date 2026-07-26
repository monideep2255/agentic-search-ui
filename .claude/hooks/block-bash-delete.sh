#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json]
# PreToolUse (Bash) guard: block file deletion via rm/rmdir, including when it is
# smuggled inside a quoted argument of an execution wrapper (ssh, python -c,
# bash -c). Makes the file-protection rule structurally enforced rather than only
# model-obeyed. jq-free, fails closed on parse failure.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
CMD=$(json_field "$INPUT" tool_input.command)
[ -z "$CMD" ] && CMD="$INPUT"

# 1) rm / rmdir as a command word: at command start or after a shell separator.
if printf '%s' "$CMD" | grep -qE '(^|[;&|][[:space:]]*)(rm|rmdir)([[:space:]]|-)'; then
  echo 'Blocked: file deletion via bash (rm/rmdir). Ask user first.' >&2
  exit 2
fi

# 2) Destructive command smuggled inside an execution wrapper's quoted argument,
#    e.g. ssh host "rm -rf /", python -c "os.system('rm -rf ~')", bash -c "...".
#    block-bash-delete's segment check above never sees these because the rm sits
#    inside quotes; catch them by pairing a wrapper with a destructive keyword.
if printf '%s' "$CMD" | grep -qE '(ssh[[:space:]]|python3?[[:space:]]+-c|perl[[:space:]]+-e|ruby[[:space:]]+-e|node[[:space:]]+-e|bash[[:space:]]+-c|sh[[:space:]]+-c|zsh[[:space:]]+-c|eval[[:space:]])' \
   && printf '%s' "$CMD" | grep -qE '(rm[[:space:]]|rmdir|rmtree|dd[[:space:]]+if=|mkfs|>[[:space:]]*/dev/)'; then
  echo 'Blocked: destructive command inside an execution wrapper (ssh/python -c/bash -c). Ask user first.' >&2
  exit 2
fi

exit 0
