#!/usr/bin/env bash
# Derive the next semantic version from Conventional Commits since the last tag.
#
# Build phase 4.15. Reads commit subjects with `git log`, NEVER through a
# `${{ github.event... }}` interpolation. That is a security property, not a
# style choice: a commit subject is attacker-influenced text, and interpolating
# it into a shell body is the GitHub Actions script-injection sink. Here it
# arrives as data on stdin and is only ever matched against, never executed.
#
# Bump rules, from the Conventional Commits spec this repository adopted on
# 2026-07-26 (.claude/rules/git-workflow.md):
#   BREAKING CHANGE footer, or `!` before the colon  -> major
#   feat                                             -> minor
#   anything else (fix, docs, chore, refactor, test, ci, security) -> patch
set -euo pipefail

# --match is load-bearing, not a tidiness flag. A bare `git describe --tags`
# returns the nearest tag of ANY shape, and this repository already carries
# `baseline/pre-drift-fix`. Without the filter the first run computed
# `vbaseline/pre-drift-fix.1.0` and would have tagged a release under it
# (finding F-4.15-05). The pattern admits only `vN.N.N`.
previous="$(git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' 2>/dev/null || echo "")"
if [ -z "$previous" ]; then
  range=""
  prev_version="0.0.0"
  echo "no previous tag: this is the first release" >&2
else
  range="${previous}..HEAD"
  prev_version="${previous#v}"
  echo "previous tag: ${previous}" >&2
fi

IFS='.' read -r major minor patch <<< "$prev_version"
major="${major:-0}"; minor="${minor:-0}"; patch="${patch:-0}"

# Belt and braces after F-4.15-05. --match should make this unreachable, but a
# version that is not three integers must stop the release rather than be
# coerced into one: a wrong tag is published and permanent, an aborted run is
# not.
for part in "$major" "$minor" "$patch"; do
  case "$part" in
    ''|*[!0-9]*)
      echo "previous tag ${previous} does not parse as vMAJOR.MINOR.PATCH" >&2
      exit 1
      ;;
  esac
done

bump="patch"
# %s is the subject, %b the body. A BREAKING CHANGE footer lives in the body.
while IFS= read -r line; do
  case "$line" in
    *"BREAKING CHANGE:"*|*"BREAKING-CHANGE:"*) bump="major"; break ;;
  esac
done < <(git log ${range:+$range} --format='%b')

if [ "$bump" != "major" ]; then
  while IFS= read -r subject; do
    # `type(scope)!:` or `type!:` marks a breaking change in the header.
    if printf '%s' "$subject" | grep -Eq '^[a-z]+(\([^)]*\))?!:'; then
      bump="major"; break
    fi
    if printf '%s' "$subject" | grep -Eq '^feat(\([^)]*\))?:'; then
      bump="minor"
    fi
  done < <(git log ${range:+$range} --format='%s')
fi

case "$bump" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
esac

next="v${major}.${minor}.${patch}"

# A release with no commits since the last tag is a no-op, not a version bump.
if [ -n "$range" ] && [ -z "$(git log "$range" --format='%h')" ]; then
  echo "no commits since ${previous}; nothing to release" >&2
  echo "should_release=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "bump=${bump} -> ${next}" >&2
{
  echo "should_release=true"
  echo "previous_tag=${previous}"
  echo "version=${next}"
  echo "bump=${bump}"
} >> "$GITHUB_OUTPUT"
