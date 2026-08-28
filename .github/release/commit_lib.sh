#!/usr/bin/env bash
# The one Conventional Commit parser the release scripts share.
#
# Build phase 4.15. This file exists because there were TWO parsers.
# `derive_version.sh` and `write_changelog.sh` each carried their own idea of
# what a Conventional Commit is, and the two ideas disagreed, which the
# adversary round measured as three separate findings that are one defect
# wearing three faces:
#   F-4.15-A-01  a `BREAKING CHANGE:` anywhere inside a body sentence bumped
#                MAJOR, because the version reader matched a substring while
#                the spec defines a FOOTER
#   F-4.15-A-03  a real `BREAKING CHANGE:` footer bumped MAJOR while the
#                changelog's Breaking changes group matched only the `!`
#                header form, so a major release could ship with no breaking
#                section at all
#   F-4.15-A-07  the changelog silently DROPPED every commit whose type was
#                not one of eight hardcoded, while the version reader still
#                counted it toward the release
# Patching each regular expression where it stood would have left the class
# alive, since the class is "two readers disagree", not "three patterns are
# wrong". So the two readers were replaced by this one. Every question about a
# commit, is it breaking, what is its type, what is its scope, what does it
# read as, is answered here and nowhere else.
#
# Nothing here executes commit text. Subjects and bodies arrive from `git log`
# as data and are only matched against, split, or escaped.

# ---------------------------------------------------------------------------
# Reading git, with failures that stop the release
# ---------------------------------------------------------------------------

# Both scripts previously read `git log` through a process substitution, where
# `set -euo pipefail` does not reach (F-4.15-J-11). A failing `git log` there
# yields an empty stream, so the version reader fell through to its `patch`
# default and published a permanent tag from a query that never ran. Command
# substitution with an explicit status check is the fix: a failed read returns
# non-zero, and every caller exits on it.

# release_commit_shas <range>
# Prints one full sha per line for the range, oldest first, merges excluded.
# An empty range means the whole history. Returns non-zero if git fails.
release_commit_shas() {
  local range="$1" out status
  out="$(git log ${range:+"$range"} --no-merges --format='%H' 2>&1)"
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'git log failed for range %s (exit %s): %s\n' \
      "${range:-<whole history>}" "$status" "$out" >&2
    return 1
  fi
  printf '%s' "$out"
}

# release_commit_field <sha> <format>
# Prints one `git log --format` field for one commit. Returns non-zero if git
# fails, so a caller can abort rather than treat a missing body as no body.
release_commit_field() {
  local sha="$1" format="$2" out status
  out="$(git log -1 --format="$format" "$sha" 2>&1)"
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'git log failed reading %s of %s (exit %s): %s\n' \
      "$format" "$sha" "$status" "$out" >&2
    return 1
  fi
  printf '%s' "$out"
}

# ---------------------------------------------------------------------------
# What a Conventional Commit is, decided once
# ---------------------------------------------------------------------------

# The header shape from the spec this repository adopted on 2026-07-26
# (.claude/rules/git-workflow.md): `type`, an optional `(scope)`, an optional
# `!`, then a colon. Types are lowercase, which is what the rule requires, so a
# capitalised `Fix:` is deliberately NOT conventional. It is not dropped for
# that: it lands in the changelog's catch-all group, which is the point of
# F-4.15-A-07's fix.
_RELEASE_HEADER_RE='^[a-z]+(\([^)]*\))?!?:'
_RELEASE_BREAKING_HEADER_RE='^[a-z]+(\([^)]*\))?!:'

release_subject_is_conventional() {
  printf '%s' "$1" | grep -Eq "$_RELEASE_HEADER_RE"
}

release_subject_is_breaking_header() {
  printf '%s' "$1" | grep -Eq "$_RELEASE_BREAKING_HEADER_RE"
}

# A footer, not a substring. The spec puts `BREAKING CHANGE` at the START of a
# footer line, followed by `: ` or ` #`. WHAT THIS DOES NOT CATCH, stated
# rather than implied: a body that quotes a footer at the start of its own
# line, for example a revert commit pasting the reverted commit's footer
# verbatim, still reads as breaking. That is the conservative direction. It
# publishes a major version for a commit that only quotes a breaking change,
# where the previous substring match published one for a commit that merely
# mentioned the phrase mid-sentence.
release_body_has_breaking_footer() {
  printf '%s\n' "$1" | grep -Eq '^BREAKING[ -]CHANGE(:|[[:space:]]#)'
}

# release_is_breaking <subject> <body>
release_is_breaking() {
  release_subject_is_breaking_header "$1" && return 0
  release_body_has_breaking_footer "$2"
}

# release_subject_type <subject>
# Prints the lowercase type, or nothing when the subject is not conventional.
release_subject_type() {
  printf '%s' "$1" | sed -nE 's/^([a-z]+)(\([^)]*\))?!?:.*/\1/p'
}

# release_subject_scope <subject>
# Prints the scope, or nothing when there is none.
release_subject_scope() {
  printf '%s' "$1" | sed -nE 's/^[a-z]+\(([^)]*)\)!?:.*/\1/p'
}

# release_subject_description <subject>
# The subject with its type prefix stripped so the line reads as prose. A
# subject that is not conventional is returned whole rather than mangled,
# which is what lets the catch-all group render it at all.
release_subject_description() {
  if release_subject_is_conventional "$1"; then
    printf '%s' "$1" | sed -E 's/^[a-z]+(\([^)]*\))?!?: *//'
  else
    printf '%s' "$1"
  fi
}

# ---------------------------------------------------------------------------
# Rendering commit text into a public artifact
# ---------------------------------------------------------------------------

# F-4.15-A-02. A commit subject is chosen by whoever opens a pull request, and
# it is copied verbatim into CHANGELOG.md and from there into a published
# GitHub Release body, which GitHub renders as markdown. It is not a shell
# injection sink, and `release.yml`'s header comment is right about that; it is
# a CONTENT injection sink into a permanent public artifact under the project's
# own name. The measured case was
# `fix(web): [click me](https://evil.example) and <img src=x onerror=alert(1)>`
# rendering as a live clickable link.
#
# WHAT THIS NEUTRALISES:
#   - ASCII control characters are removed: everything below space except the
#     tab, so CR and ESC both go. The first version of this escape kept CR by
#     accident, and a subject carrying one rendered a bullet that overwrites
#     itself in a terminal; the range is written as one span now rather than as
#     three, since the gap is what let a character through
#   - a subject cannot terminate the bullet line, because LF cannot reach here:
#     `git log --format=%s` is the subject line alone
#   - the length is capped, so one subject cannot flood the artifact
#   - `&`, then `<` and `>`, become entities, so an HTML tag renders as text
#     rather than as markup
#   - a backslash escape is placed in front of the markdown characters that
#     build active constructs: `\`, backtick, `*`, `_`, `~`, `[` and `]`. A
#     link or image therefore renders as the literal text somebody typed
#
# WHAT THIS DOES NOT NEUTRALISE, and does not need to:
#   - `#` and `-` are left alone. Both are only active at the START of a line,
#     and rendered text never starts a line here: every line this produces
#     begins with the literal `- ` of the bullet, written by the script
#   - a bare URL. GitHub autolinks one, and a changelog that could not carry a
#     URL would be worse than one that does. The link text cannot lie about
#     where it points, which was the actual finding
#   - the ordinary meaning of the subject. This is an escape, not a filter: a
#     subject is never rejected and never silently emptied
release_render_text() {
  printf '%s' "$1" \
    | tr -d '\000-\010\013-\037\177' \
    | cut -c1-200 \
    | sed -e 's/\\/\\\\/g' \
          -e 's/&/\&amp;/g' \
          -e 's/</\&lt;/g' \
          -e 's/>/\&gt;/g' \
          -e 's/`/\\`/g' \
          -e 's/\*/\\*/g' \
          -e 's/_/\\_/g' \
          -e 's/~/\\~/g' \
          -e 's/\[/\\[/g' \
          -e 's/\]/\\]/g'
}
