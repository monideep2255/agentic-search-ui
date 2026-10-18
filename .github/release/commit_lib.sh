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
# Prints one full sha per line for the range, newest first as `git log` gives
# them, merges excluded, and the release job's own changelog commits excluded
# (see release_changelog_verdict below). An empty range means the whole
# history. Returns non-zero if git fails.
release_commit_shas() {
  local range="$1" out status line sha subject verdict
  out="$(git log ${range:+"$range"} --no-merges --format='%H%x09%s' 2>&1)"
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'git log failed for range %s (exit %s): %s\n' \
      "${range:-<whole history>}" "$status" "$out" >&2
    return 1
  fi
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    sha="${line%%$'\t'*}"
    subject="${line#*$'\t'}"
    verdict="$(release_changelog_verdict "$sha" "$subject")" || return 1
    if [ "$verdict" = "changelog" ]; then
      continue
    fi
    printf '%s\n' "$sha"
  done <<< "$out"
  return 0
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
# The release job's own changelog commit, recognised once
# ---------------------------------------------------------------------------

# WHY THE RELEASE JOB HAS TO RECOGNISE ITS OWN COMMIT. Since 2026-09-27 the job
# never pushes to `production` (release.yml's header says why). It commits the
# changelog locally, on top of the production commit it tagged, and that commit
# reaches `production` the long way round: the back-merge pull request carries
# it into `develop`, and the NEXT release pull request carries it into
# `production`. So every release after the first finds the previous release's
# changelog commit inside its own range. Counted as an ordinary commit it would
# be listed in the next release's notes, and a release whose only other
# content is merge commits would publish a patch version for nothing.
#
# The subject is written in exactly one place, here, and read in exactly one
# place, release_changelog_verdict below. Two scripts spelling it separately is
# the "two readers disagree" class this file exists to end.

# release_changelog_subject <version>
# The subject tag_and_release.sh gives the changelog commit for <version>.
release_changelog_subject() {
  printf 'docs(changelog): release %s [skip ci]' "$1"
}

_RELEASE_CHANGELOG_SUBJECT_RE='^docs\(changelog\): release v[0-9]+\.[0-9]+\.[0-9]+ \[skip ci\]$'
# The same commit after a squash merge of its back-merge pull request, which
# rewrites it under the pull request's title. The repository merges with merge
# commits, so this should not occur, but it costs one pattern to make the
# changelog survive any of GitHub's three merge buttons.
_RELEASE_BACKMERGE_SQUASH_RE='^chore: back-merge v[0-9]+\.[0-9]+\.[0-9]+ into develop( \(#[0-9]+\))?$'

# release_changelog_version <subject>
# Prints the version a subject names when it is one of the two changelog
# subjects above, and nothing for any other subject. This is the only place a
# subject is matched against them. The verdict and the finder below ask here,
# and every script that looks for a changelog commit asks the finder, so no
# two scripts can recognise the changelog commit differently (F-REL-A05, where
# the carry step matched the robot's own subject only and missed the
# squash-merged form the verdict accepted).
release_changelog_version() {
  if printf '%s' "$1" \
      | grep -Eq "${_RELEASE_CHANGELOG_SUBJECT_RE}|${_RELEASE_BACKMERGE_SQUASH_RE}"; then
    printf '%s' "$1" | sed -nE 's/^[^0-9]*(v[0-9]+\.[0-9]+\.[0-9]+).*$/\1/p'
  fi
}

# release_changelog_verdict <sha> <subject>
# Prints `changelog` when the commit is the release job's own changelog
# commit, `commit` for everything else. Returns non-zero if git fails.
#
# TWO CONDITIONS, BOTH REQUIRED. The subject alone is chosen by whoever writes
# the commit, so a subject match alone would let any commit hide from the
# release notes by borrowing it. The commit must ALSO change `CHANGELOG.md`
# and nothing else. A commit that passes both can hide nothing but changelog
# text, which is exactly what it is.
release_changelog_verdict() {
  local sha="$1" subject="$2" files status
  if [ -z "$(release_changelog_version "$subject")" ]; then
    printf 'commit'
    return 0
  fi
  files="$(git diff-tree --no-commit-id --name-only -r --root "$sha" 2>&1)"
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'git diff-tree failed for %s (exit %s): %s\n' "$sha" "$status" "$files" >&2
    return 1
  fi
  if [ "$files" = "CHANGELOG.md" ]; then
    printf 'changelog'
  else
    printf 'commit'
  fi
}

# release_find_changelog_commit <version> <ref>...
# Searches each ref in the order given for the release job's changelog commit
# for <version>, recognised exactly as the verdict above recognises it: either
# subject, naming <version>, on a commit that changes CHANGELOG.md alone.
# Prints `<sha><TAB><ref>` for the first one found, and nothing when no ref
# carries one. A ref that does not exist is skipped. Returns non-zero if git
# fails.
release_find_changelog_commit() {
  local version="$1" ref out status line sha subject verdict
  shift
  for ref in "$@"; do
    git rev-parse --verify --quiet "${ref}^{commit}" > /dev/null || continue
    out="$(git log "$ref" --no-merges --fixed-strings --grep="$version" --format='%H%x09%s' 2>&1)"
    status=$?
    if [ "$status" -ne 0 ]; then
      printf 'git log failed searching %s (exit %s): %s\n' "$ref" "$status" "$out" >&2
      return 1
    fi
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      sha="${line%%$'\t'*}"
      subject="${line#*$'\t'}"
      [ "$(release_changelog_version "$subject")" = "$version" ] || continue
      verdict="$(release_changelog_verdict "$sha" "$subject")" || return 1
      if [ "$verdict" = "changelog" ]; then
        printf '%s\t%s\n' "$sha" "$ref"
        return 0
      fi
    done <<< "$out"
  done
  return 0
}

# ---------------------------------------------------------------------------
# The release robot, and the tags it made
# ---------------------------------------------------------------------------

# The identity every commit and tag this job makes carries. It is also how a
# later run recognises a tag this job made (release_job_tag_at below), so it
# is written once, here.
RELEASE_BOT_NAME="github-actions[bot]"
RELEASE_BOT_EMAIL="41898282+github-actions[bot]@users.noreply.github.com"

release_as_bot() {
  git config user.name "$RELEASE_BOT_NAME"
  git config user.email "$RELEASE_BOT_EMAIL"
}

# release_job_tag_at <commit>
# Prints the `vX.Y.Z` tag this job made on <commit>, and nothing when there is
# none. A tag counts only when it is annotated and its tagger is the release
# robot, so a tag the owner made by hand is never one: the data engineering
# repository's first release, v1.0.0, is tagged by hand on purpose so that the
# robot releases nothing, and that must stay true. Returns non-zero if git
# fails, or if <commit> carries more than one such tag, which no run of this
# job makes.
release_job_tag_at() {
  local out status tags
  out="$(git for-each-ref --points-at "$1" \
    --format='%(refname:strip=2)%09%(objecttype)%09%(taggeremail)' refs/tags 2>&1)"
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'git for-each-ref failed reading the tags on %s (exit %s): %s\n' \
      "$1" "$status" "$out" >&2
    return 1
  fi
  tags="$(printf '%s\n' "$out" | awk -F '\t' -v email="<${RELEASE_BOT_EMAIL}>" \
    '$1 ~ /^v[0-9]+\.[0-9]+\.[0-9]+$/ && $2 == "tag" && $3 == email { print $1 }')"
  if [ "$(printf '%s' "$tags" | grep -c .)" -gt 1 ]; then
    printf '%s carries more than one release tag made by this job: %s\n' \
      "$1" "$(printf '%s' "$tags" | tr '\n' ' ')" >&2
    return 1
  fi
  printf '%s' "$tags"
}

# ---------------------------------------------------------------------------
# One release's section of CHANGELOG.md, read once
# ---------------------------------------------------------------------------

# release_changelog_section <version>
# Reads a CHANGELOG.md on stdin and prints the section for <version>: its
# `## <version> ` heading and every line after it up to, not including, the
# next `## ` heading, with trailing blank lines dropped. Prints nothing when
# the file has no section for <version>.
#
# THE NEXT `## ` HEADING ENDS THE SECTION WHATEVER IT SAYS, including a second
# heading for the same version (F-REL-J11). The notes reader this replaced
# tested for the version's heading before testing for "any heading", so a
# second `## <version>` line restarted the section instead of ending it, and a
# changelog carrying two headings for one version, for example a section the
# owner drafted by hand under the version the release then got, published
# both as one release's notes. The first heading for <version> wins.
#
# The heading is matched as `## <version> ` with its trailing space, or as the
# bare `## <version>`, so `## v0.2.0` never matches `## v0.2.01`.
release_changelog_section() {
  awk -v with_date="## $1 " -v bare="## $1" '
    found && /^## / { exit }
    !found && (index($0, with_date) == 1 || $0 == bare) { found = 1 }
    found { lines[++n] = $0 }
    END {
      while (n > 0 && lines[n] !~ /[^[:space:]]/) { n-- }
      for (i = 1; i <= n; i++) { print lines[i] }
    }
  '
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
