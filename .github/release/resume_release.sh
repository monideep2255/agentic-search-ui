#!/usr/bin/env bash
# Pick up the changelog commit an earlier run of this release already wrote.
#
# Added 2026-09-27, finding F-REL-A04. The release job pushes its back-merge
# branch, carrying the changelog commit, BEFORE it pushes the tag, so the
# changelog is safe on `origin` before anything permanent happens. A run that
# failed after that push leaves the branch behind. Written again from scratch,
# the changelog commit would differ from the pushed one, so its push would be
# refused, and a second copy could reach `develop` as a doubled section. So,
# before the changelog is written, this looks for the changelog commit for
# this version and, when an earlier run left one, makes it this run's HEAD:
#
#   - on `chore/back-merge-<version>`: the branch is checked out as it stands
#     on `origin`, including anything the owner added to it
#   - on `develop`, when that branch was already merged: that commit is
#     checked out, and nothing will be pushed or opened for it
#
# The carry and write steps then do not run (`write_changelog=false`), and
# tag_and_release.sh and open_backmerge_pr.sh each check what already exists
# before acting. When no earlier run left a changelog, the release proceeds as
# it always did (`write_changelog=true`).
#
# The search is commit_lib.sh's one finder, the same one the carry step uses,
# so a changelog commit is recognised here exactly as everywhere else.
#
# WHAT IT NEVER DOES: push anything, or touch `production`. It reads `origin`
# and moves this checkout's HEAD, nothing more.
set -euo pipefail

# shellcheck source=.github/release/commit_lib.sh
. "$(dirname "$0")/commit_lib.sh"

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
release_sha="${RELEASE_SHA:?RELEASE_SHA is required}"
branch="chore/back-merge-${version}"

# A fetch failure stops the job here, unlike in the carry step. Nothing
# permanent has happened yet, and a run that cannot see `origin` cannot know
# whether an earlier run left a changelog to pick up.
git fetch --quiet origin

found="$(release_find_changelog_commit "$version" \
  "refs/remotes/origin/${branch}" "refs/remotes/origin/develop")"

if [ -z "$found" ]; then
  if git rev-parse --verify --quiet "refs/remotes/origin/${branch}^{commit}" > /dev/null; then
    echo "::error title=Stale back-merge branch::origin has ${branch}, but it" \
         "carries no changelog commit for ${version}. Nothing has been tagged or" \
         "published. Look at that branch on GitHub; if it holds nothing worth" \
         "keeping, delete it, then re-run this job."
    exit 1
  fi
  echo "no earlier run of ${version} left a changelog; writing it now" >&2
  echo "write_changelog=true" >> "$GITHUB_OUTPUT"
  exit 0
fi

sha="${found%%$'\t'*}"
ref="${found#*$'\t'}"

# The changelog must be for THIS production commit. The robot's own changelog
# commit sits on top of the commit it was written for, so that commit is its
# ancestor, and a changelog commit for the same version written for another
# production commit (a run that failed before tagging, then a new push to
# `production`) lists the wrong commits. A squash-merged copy on `develop` has
# lost that ancestry, and is taken on its subject and file alone.
subject="$(release_commit_field "$sha" '%s')"
if [ "$subject" = "$(release_changelog_subject "$version")" ] \
   && ! git merge-base --is-ancestor "$release_sha" "$sha"; then
  echo "::error title=Stale changelog for ${version}::the ${version} changelog" \
       "commit ${sha} on ${ref#refs/remotes/} was written for a different" \
       "production commit than ${release_sha}. Nothing has been tagged or" \
       "published. If ${ref#refs/remotes/} is the back-merge branch of a run" \
       "that failed, delete that branch on GitHub, then re-run this job."
  exit 1
fi

if [ "$ref" = "refs/remotes/origin/${branch}" ]; then
  git checkout --quiet -B "$branch" "$ref"
  echo "an earlier run of ${version} pushed ${branch} with its changelog commit" \
       "${sha}; carrying on from it rather than writing a second one" >&2
else
  git checkout --quiet --detach "$sha"
  echo "the ${version} changelog commit ${sha} is already on develop; carrying" \
       "on from it, with no back-merge branch to push" >&2
fi
echo "write_changelog=false" >> "$GITHUB_OUTPUT"
