#!/usr/bin/env bash
# scope: project
# depends_on: [.claude/hooks/lib/_json.sh]
# depended_by: [.claude/settings.json, tests/ci/test_claude_hooks.py]
# PreToolUse (Bash) guard: block file deletion via rm/rmdir and writes to a disk
# device, including when smuggled inside a quoted argument of an execution
# wrapper (ssh, python -c, bash -c, a pipe or here-document into a shell). Makes
# the file-protection rule structurally enforced rather than only model-obeyed.
# jq-free, fails closed on parse failure.
#
# rm and rmdir are matched as whole words, so "perform" or "platform" never
# reads as rm, and a redirect to /dev/null is dropped before any check, since
# discarding output deletes nothing. Inside an execution wrapper, an escape
# sequence that ends in a letter or digit (\n, \012, \x3b, \u000a, Ruby's \C-j)
# also ends the word, because the wrapper decodes it into a newline or a
# separator. Approved item by item by the product owner on 2026-09-25
# (DECISIONS.md, "Four security-layer changes approved item by item", item 1),
# on the condition that rm -rf stays blocked.
#
# rm and rmdir match in any letter case, since the disk is case-insensitive on
# macOS and RM, Rm or /bin/RM runs rm. The whole-word edges stay, so "ARM64",
# "RMS" and "perform" are not rm. A pipe into a shell (echo '...' | bash, curl
# ... | sh, | sudo bash) and a here-string or here-document into a shell
# (bash <<< '...', sh <<EOF) run their text as commands, so each counts as an
# execution wrapper, an output redirect such as 2>&1 before the << included.
# Approved item by item by the product owner on 2026-09-26 ("Also close the
# hook gaps"). tests/ci/test_claude_hooks.py pins every case both ways.
#
# Every check reads the command in any letter case, not only rm and rmdir: a
# runner, a wrapper, a shell or mkfs in upper or mixed case runs on that disk
# just as it does in lower case, so BASH -c, Bash -c, | BASH, SH -c, ENV rm,
# SUDO rm, | XARGS rm, MKFS.ext4 and PYTHON3 -c are read like their lower-case
# forms. The edges stay whole words, so "ARM64", "RMS", "perform", "SHASUM" and
# | SHA256SUM are neither rm nor a shell. Shell keywords (then, do), find's
# -exec and the /dev/ path now match in any case too, which only blocks more.
# Approved item by item by the product owner on 2026-09-26 (DECISIONS.md,
# "Three more guard gaps are closed", item b).
#
# Not covered, named here and not closed, because the owner approved only the
# gaps above and pattern matching cannot close these reliably:
# - Destructive text the command encodes or splits so no whole-word rm is
#   written: base64 -d | bash, printf '\x72\x6d', 'r''m'.
# - rm behind a word the guard does not know as a runner: command rm,
#   /usr/bin/env rm, LANG=C rm.
# - A pipe or a here-document into an interpreter that is not a shell, such
#   as python, perl or node.
# - A pipe whose shell is not the word right after it: the shell on the next
#   line or after | and a backslash-newline, | (bash), | { bash; },
#   | tee >(bash), | $SHELL, | busybox sh, | ssh-agent bash, | mksh.
# - An escape the guard does not read as one: PowerShell's backtick (`n)
#   right before rm inside a wrapper.
# - Deletion that never names rm or rmdir: find -delete, unlink, shred,
#   git clean, Python's os.remove.
# - A command holding a JSON lone surrogate. The JSON reader cannot print it,
#   so the guard reads the raw JSON text, where a newline is the two
#   characters \n, and an rm on its own line passes.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/_json.sh"

INPUT=$(cat)
CMD=$(json_field "$INPUT" tool_input.command)
[ -z "$CMD" ] && CMD="$INPUT"

QUOTE='["'"'"']'                          # a double or a single quote
END='([[:space:];&|)`"'"'"']|$)'           # what may follow a device name: a delimiter or the end
WORD_END='([^[:alnum:]_]|$)'              # rm ends here, so "rmtree" and "rms" are not rm
REDIRECT='[0-9]*>[>|&]?[[:space:]]*'      # >, >>, >|, >&, 2> and the like
DEVICE_WRITE="(>[>|&]?[[:space:]]*|(^|[^[:alnum:]_])of=)$QUOTE?/dev/"

# 0) Drop every redirect to /dev/null (>, >>, >|, >&, 2>, quoted or not) and
#    dd's of=/dev/null. /dev/null must end at a delimiter, so /dev/nullb0 stays
#    and is checked like any device. The delimiter is kept, so a separator right
#    after the redirect still separates. An & before the > is kept too: bash
#    reads &> as one redirect, but POSIX sh reads the & as the end of a command.
SCAN=$(printf '%s' "$CMD" | sed -E \
  -e "s#$REDIRECT$QUOTE?/dev/null$QUOTE?$END# \\1#g" \
  -e "s#of=$QUOTE?/dev/null$QUOTE?$END# \\1#g")

# Command position: the start of a line, after a shell separator or opener
# (; & | ( ) { } backtick), or after find's -exec. Then any shell keyword, and
# any runner that takes a command as its argument (sudo, env, exec, nice, nohup,
# time, timeout, xargs) with its options. Then the command word itself, which may
# be quoted, escaped with a backslash, or given as a path such as /bin/rm.
SEP='[;&|(){}`]'
LEAD="((^|$SEP)[[:space:]]*|[[:space:]]-(exec|execdir|ok|okdir)[[:space:]]+)"
KEYWORD='(then|do|else|if|elif|while|until|!)[[:space:]]+'
RUNNER='(sudo|doas|env|exec|nice|nohup|time|timeout|xargs)([[:space:]]+[^[:space:];&|]+)*[[:space:]]+'
PREFIX="($KEYWORD|$RUNNER)*"
CMDWORD="$QUOTE?"'(\\|/([[:alnum:]_.-]+/)*)?'

# rm and rmdir in any letter case: on a case-insensitive disk RM and Rm run rm.
RM='[Rr][Mm]'
RMDIR='[Rr][Mm][Dd][Ii][Rr]'

# Every grep below runs with -i: the disk is case-insensitive, so a runner,
# wrapper, shell or mkfs in any letter case runs as its lower-case form does.
#
# 1) rm / rmdir as a command word, as a whole word, in any letter case, behind
#    runners in any letter case (SUDO, ENV, XARGS). `git rm` is a git
#    subcommand, not in command position, and stays allowed as before.
if printf '%s' "$SCAN" | grep -qiE "$LEAD$PREFIX$CMDWORD($RM|$RMDIR)$QUOTE?$WORD_END"; then
  echo 'Blocked: file deletion via bash (rm/rmdir). Ask user first.' >&2
  exit 2
fi

# 2) Destructive command smuggled inside an execution wrapper's quoted argument,
#    e.g. ssh host "rm -rf /", python -c "os.system('rm -rf ~')", bash -c "...".
#    Check 1 never sees these because the rm sits inside quotes; catch them by
#    pairing a wrapper with a destructive word. rm is a whole word here too,
#    and an escape sequence ending in a letter or digit right before it ends
#    the word the way a separator would: os.system('true\nrm -rf ~'),
#    $'true\x3brm -rf x' and Ruby's "true\C-jrm -rf x" each run rm as its own
#    command once decoded. The guard cannot tell that from an escape before a
#    word that ends in rm, such as "\nperform", so it blocks both and fails
#    closed. rmdir, rmtree, dd if= and mkfs stay substring matches, as before,
#    because a whole-word rmdir would let fs.rmdirSync(...) through. Any write
#    into /dev other than /dev/null stays blocked inside a wrapper, as before.
#    The wrapper and the destructive word both match in any letter case.
#
#    A pipe into a shell and a here-string or here-document into a shell are
#    wrappers as well: the shell runs the text it reads as commands. A pipe
#    counts when the shell is the command word right after the pipe, maybe
#    behind a runner such as sudo, a quote or a path such as /bin/sh, so
#    | shasum, | shellcheck and | grep bash never count. A here-string or
#    here-document counts when a shell word (not a script such as install.sh)
#    is followed on its line by its arguments, any output redirects with their
#    targets (2>&1, >out.txt, 2> err.log, >&2, &>log) and <<. The shells are
#    bash, sh, zsh, dash, ksh, csh, tcsh and fish.
SHELLS='((ba|da|k|z|c|tc)?sh|fish)'
SHELL_END='([[:space:];&|)<>`"'"'"']|$)'   # what may follow a shell's name
PIPE_SHELL='[|]&?[[:space:]]*('"$RUNNER"')*'"$CMDWORD$SHELLS$SHELL_END"
SHELL_REDIR='[0-9]*(&>>?|>[>|&]?)[[:space:]]*[^[:space:];&|<>]+'   # 2>&1, >out, &>log
HERE_SHELL='(^|[^[:alnum:]_.-])'"$SHELLS"'([[:space:]]+[^[:space:];&|<>]+|[[:space:]]*'"$SHELL_REDIR"')*[[:space:]]*<<'
WRAPPER='(ssh[[:space:]]|python3?[[:space:]]+-c|perl[[:space:]]+-e|ruby[[:space:]]+-e|node[[:space:]]+-e|bash[[:space:]]+-c|sh[[:space:]]+-c|zsh[[:space:]]+-c|eval[[:space:]]'"|$PIPE_SHELL|$HERE_SHELL)"
ESCAPE='\\[[:alnum:]]+|\\[CM]-[[:alnum:]]'  # \n, \012, \x3b, \u000a; Ruby's \C-j
INSIDE="(^|[^[:alnum:]_]|$ESCAPE)$RM$WORD_END|$RMDIR|rmtree|dd[[:space:]]+if=|mkfs|$DEVICE_WRITE"
if printf '%s' "$SCAN" | grep -qiE "$WRAPPER" \
   && printf '%s' "$SCAN" | grep -qiE "$INSIDE"; then
  echo 'Blocked: destructive command inside an execution wrapper (ssh, python -c, bash -c, or a pipe, here-string or here-document into a shell). Ask user first.' >&2
  exit 2
fi

# 3) A write to a disk device outside a wrapper: a redirect into /dev, dd's of=
#    into /dev, or mkfs as a command word, MKFS included. /dev/null was dropped
#    in step 0, in lower case only, so /DEV/NULL is checked like a device. The
#    stream devices (stdout, stderr, tty, fd/N) are dropped too: they hold no
#    data, and outside a wrapper they were never checked before.
STREAMS='(stdout|stderr|tty|fd/[0-9]+)'
DISKSCAN=$(printf '%s' "$SCAN" | sed -E \
  -e "s#$REDIRECT$QUOTE?/dev/$STREAMS$QUOTE?$END# \\2#g" \
  -e "s#of=$QUOTE?/dev/$STREAMS$QUOTE?$END# \\2#g")
MKFS="$LEAD$PREFIX${CMDWORD}mkfs$WORD_END"
if printf '%s' "$DISKSCAN" | grep -qiE "$DEVICE_WRITE|$MKFS"; then
  echo 'Blocked: write to a disk device (a redirect into /dev, dd of=/dev/..., mkfs). To discard output, redirect to /dev/null. Ask user first.' >&2
  exit 2
fi

exit 0
