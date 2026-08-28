#!/usr/bin/env bash
# Prepend a release section to CHANGELOG.md, grouped by Conventional Commit type.
#
# Build phase 4.15. Commit subjects arrive via `git log`, never via a
# `${{ github.event... }}` interpolation. See derive_version.sh for why that is
# a security property rather than a style choice.
#
# The file is written newest-first, which is what `.claude/rules/writing-style.md`
# requires of a changelog: "a changelog is a dated bullet list, newest first".
#
# No temporary file is cleaned up here on purpose. This runs on an ephemeral
# GitHub Actions runner whose whole filesystem is discarded, and this
# repository's `block-bash-delete.sh` hook treats a deletion inside a script as
# something a human should approve. Leaving the scratch file costs nothing and
# keeps the script free of a delete a reviewer would have to reason about.
set -euo pipefail

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
previous="${PREVIOUS_TAG:-}"
today="$(date -u +%Y-%m-%d)"
range="${previous:+${previous}..HEAD}"

work="$(mktemp -d)"
section="${work}/section.md"
{
  echo "## ${version} (${today})"
  echo
} > "$section"

emit_group() {
  local pattern="$1" heading="$2" found=0
  while IFS= read -r line; do
    subject="${line%%|*}"
    sha="${line##*|}"
    if printf '%s' "$subject" | grep -Eq "$pattern"; then
      if [ "$found" -eq 0 ]; then
        echo "${heading}" >> "$section"
        echo >> "$section"
        found=1
      fi
      # Strip the type prefix so the line reads as prose; keep the scope, which
      # says which part of the system moved.
      text="$(printf '%s' "$subject" | sed -E 's/^[a-z]+(\([^)]*\))?!?: *//')"
      scope="$(printf '%s' "$subject" | sed -nE 's/^[a-z]+\(([^)]*)\)!?:.*/\1/p')"
      if [ -n "$scope" ]; then
        echo "- ${scope}: ${text} (${sha})" >> "$section"
      else
        echo "- ${text} (${sha})" >> "$section"
      fi
    fi
  done < <(git log ${range:+$range} --no-merges --format='%s|%h')
  if [ "$found" -eq 1 ]; then
    echo >> "$section"
  fi
  return 0
}

# Order matters: a reader wants the breaking news first and the housekeeping
# last. This is the same ordering the Conventional Commits spec implies by
# severity, not alphabetical.
emit_group '^[a-z]+(\([^)]*\))?!:' "Breaking changes"
emit_group '^feat(\([^)]*\))?:' "Features"
emit_group '^fix(\([^)]*\))?:' "Fixes"
emit_group '^security(\([^)]*\))?:' "Security"
emit_group '^(docs|refactor|test|chore|ci)(\([^)]*\))?:' "Maintenance"

if [ -n "$previous" ]; then
  echo "Full diff: \`${previous}..${version}\`" >> "$section"
  echo
fi

if [ ! -f CHANGELOG.md ]; then
  {
    echo "# Changelog"
    echo
    echo "Every release of System 3, newest first. Generated on each push to"
    echo "\`production\` by \`.github/workflows/release.yml\` from the Conventional"
    echo "Commit subjects since the previous tag. Do not hand-edit a released"
    echo "section: correct the commit history or add a new entry instead."
    echo
  } > CHANGELOG.md
fi

# Split at the FIRST `## ` heading rather than at a fixed line number. The
# first version of this counted `head -n 6`, which cut the preamble one line
# short of its trailing blank and produced a version heading glued to the
# prose. A structural split cannot drift when the preamble is reworded.
split_at="$(grep -n '^## ' CHANGELOG.md | head -n 1 | cut -d: -f1 || true)"
if [ -n "$split_at" ]; then
  head -n "$((split_at - 1))" CHANGELOG.md > "${work}/head.md"
  tail -n "+${split_at}" CHANGELOG.md > "${work}/body.md"
else
  cat CHANGELOG.md > "${work}/head.md"
  : > "${work}/body.md"
fi
cat "${work}/head.md" "$section" "${work}/body.md" > CHANGELOG.md
echo "CHANGELOG.md updated for ${version}" >&2
