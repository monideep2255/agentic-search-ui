#!/usr/bin/env bash
# Carry the previous release's changelog commit into this release's checkout,
# when its back-merge pull request was not merged before this release.
#
# Added 2026-09-27, with the change that stopped the release job pushing to
# `production`. A release's changelog commit now reaches `production` only by
# travelling: back-merge pull request into `develop`, then the next release
# pull request into `production`. If the owner cuts the next release before
# merging the previous back-merge, `production`'s CHANGELOG.md has no section
# for the previous release. Written on top of that file, this release's section
# would leave the previous one out, and the two back-merge pull requests would
# then conflict on the same lines of CHANGELOG.md.
#
# So, before the section is written, if CHANGELOG.md has no section for the
# previous release, this finds the previous release's changelog commit and, if
# HEAD does not already contain it, merges it into this checkout. The new section is then written on top of a file that has the
# previous one, and the new back-merge pull request carries both commits, so
# merging it completes the older pull request as well.
#
# WHAT IT NEVER DOES: push anything, or touch `production`. The merge exists in
# this checkout and, from there, on the back-merge branch, which is a pull
# request the owner reviews. The tag goes on RELEASE_SHA, the production commit
# derive_version.sh read, never on this merge, and write_changelog.sh lists the
# commits up to RELEASE_SHA only, so the carried commit is not listed again.
#
# WHERE THE COMMIT CAN BE, in the order searched:
#   - on `chore/back-merge-<previous>`, while that pull request is open
#   - on `develop`, when that pull request merged after this release's branch
#     was cut, and its branch was then deleted
# Only a commit that commit_lib.sh recognises as a changelog commit, with the
# exact subject for <previous>, is ever merged. Such a commit changes
# CHANGELOG.md and nothing else.
#
# FAIL-SOFT, deliberately. If the commit is not found, or the merge conflicts,
# this says so in the log and changes nothing, and the release goes out exactly
# as it would have without this step. The deploy has already happened by the
# time this runs, so blocking the release on changelog housekeeping would be
# the worse trade.
set -euo pipefail

# shellcheck source=.github/release/commit_lib.sh
. "$(dirname "$0")/commit_lib.sh"

previous="${PREVIOUS_TAG:-}"
if [ -z "$previous" ]; then
  echo "first release: there is no previous changelog to carry" >&2
  exit 0
fi

# The common case, and the whole check when it holds: the owner merged the
# previous back-merge before cutting this release, so `production` already has
# the previous section.
if [ -f CHANGELOG.md ] \
   && [ -n "$(release_changelog_section "$previous" < CHANGELOG.md)" ]; then
  echo "CHANGELOG.md already has the ${previous} section; nothing to carry" >&2
  exit 0
fi

subject="$(release_changelog_subject "$previous")"

if ! git fetch --quiet origin; then
  echo "warning: could not fetch origin; not carrying the ${previous} changelog" >&2
  exit 0
fi

candidate=""
for ref in "refs/remotes/origin/chore/back-merge-${previous}" "refs/remotes/origin/develop"; do
  git rev-parse --verify --quiet "$ref" > /dev/null || continue
  found="$(git log "$ref" --no-merges --fixed-strings --grep="$subject" --format='%H%x09%s')"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    sha="${line%%$'\t'*}"
    [ "${line#*$'\t'}" = "$subject" ] || continue
    verdict="$(release_changelog_verdict "$sha" "$subject")"
    if [ "$verdict" = "changelog" ]; then
      candidate="$sha"
      break
    fi
  done <<< "$found"
  [ -z "$candidate" ] || break
done

if [ -z "$candidate" ]; then
  echo "warning: CHANGELOG.md has no ${previous} section, and no changelog commit" \
       "for ${previous} is on its back-merge branch or on develop. This release's" \
       "section is written without it; add the ${previous} section by hand in a" \
       "pull request to develop" >&2
  exit 0
fi

if git merge-base --is-ancestor "$candidate" HEAD; then
  echo "this checkout already contains the ${previous} changelog commit" \
       "${candidate}, though CHANGELOG.md has no ${previous} section; not carrying" >&2
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

echo "the ${previous} back-merge was not merged before this release;" \
     "carrying its changelog commit ${candidate}" >&2
if git merge --quiet --no-ff --no-edit \
     -m "chore: carry the ${previous} changelog into the next release" "$candidate"; then
  echo "carried the ${previous} changelog" >&2
else
  git merge --abort
  echo "warning: carrying the ${previous} changelog conflicted; not carrying it." \
       "This release's section is written without it; add the ${previous} section" \
       "by hand in a pull request to develop" >&2
fi
