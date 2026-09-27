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
#     was cut, and its branch was then deleted. A squash merge leaves it there
#     under the pull request's title, `chore: back-merge <previous> into
#     develop (#N)`, and it is found under that subject too
# Only a commit that commit_lib.sh recognises as the changelog commit for
# <previous>, through its one finder, is ever merged.
# Such a commit changes CHANGELOG.md and nothing else. Merging a squash-merged
# one also brings the `develop` commits beneath it into this checkout; those
# reach no tag and no notes, since both stop at RELEASE_SHA, and they are on
# `develop` already, where the back-merge pull request goes.
#
# A CONFLICT IS RESOLVED, NOT DROPPED (F-REL-J03). The merge conflicts when
# CHANGELOG.md changed near the top after the previous release, for example
# when the owner corrected an older heading on `develop`. It used to be aborted
# with one log line, and the previous section was lost in silence. It is
# resolved instead, because the right answer is known exactly: the commit
# being carried changes CHANGELOG.md and nothing else (commit_lib.sh's verdict
# requires it), and all it adds is its own section. So the file becomes this
# checkout's CHANGELOG.md, every edit in it kept, with the previous section,
# exactly as that commit wrote it, placed above the newest section here. That
# is the file a person resolving the conflict by hand would write, and newest
# first holds, since no release after the previous one has a section yet. The
# merge commit still records the carried commit as a parent, so merging the
# older back-merge pull request later changes nothing.
#
# FAIL-SOFT, AND LOUD, when nothing can be carried: the commit is on neither
# ref, the conflict reaches a file other than CHANGELOG.md, or the carried
# commit has no section to take. Then this changes nothing, prints a
# `::warning::` that GitHub shows on the run's summary, and the release goes
# out without the section. open_backmerge_pr.sh then reads the file it pushes
# and names the missing section, and how to add it, in the pull request the
# owner has to open anyway. The deploy has already happened by the time this
# runs, so blocking the release on changelog housekeeping would be the worse
# trade; losing a section without a word was the defect.
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

if ! git fetch --quiet origin; then
  echo "warning: could not fetch origin; not carrying the ${previous} changelog" >&2
  exit 0
fi

# commit_lib.sh's one finder, so this step recognises the previous changelog
# commit exactly as the notes and the version bump do, under either subject
# (F-REL-A05).
found="$(release_find_changelog_commit "$previous" \
  "refs/remotes/origin/chore/back-merge-${previous}" "refs/remotes/origin/develop")"
candidate="${found%%$'\t'*}"

# The one voice for "the previous section will be missing". A workflow command
# on stdout, so GitHub lifts it onto the run's summary page, not only the log.
not_carried() { # <why>
  echo "::warning title=CHANGELOG.md is missing ${previous}::$1 This release's" \
       "section is written without the ${previous} section. The back-merge pull" \
       "request says how to add it by hand."
}

if [ -z "$candidate" ]; then
  not_carried "No changelog commit for ${previous} is on its back-merge branch or on develop."
  exit 0
fi

if git merge-base --is-ancestor "$candidate" HEAD; then
  not_carried "This checkout already contains the ${previous} changelog commit ${candidate}, though CHANGELOG.md has no ${previous} section, so a later edit removed it."
  exit 0
fi

release_as_bot

message="chore: carry the ${previous} changelog into the next release"
echo "the ${previous} back-merge was not merged before this release;" \
     "carrying its changelog commit ${candidate}" >&2
if git merge --quiet --no-ff --no-edit -m "$message" "$candidate"; then
  echo "carried the ${previous} changelog" >&2
  exit 0
fi

# The merge conflicted. Resolve it as the header says, or leave everything as
# it was and say so.
conflicted="$(git diff --name-only --diff-filter=U)"
section="$(git show "${candidate}:CHANGELOG.md" | release_changelog_section "$previous")"
if [ "$conflicted" != "CHANGELOG.md" ] || [ -z "$section" ]; then
  git merge --abort
  not_carried "Carrying the ${previous} changelog commit ${candidate} conflicted outside CHANGELOG.md's sections."
  exit 0
fi

# This checkout's CHANGELOG.md with the section placed above its first `## `
# heading, one blank line on each side, or at the end when it has no heading.
# The section travels in the environment, so awk never parses its text as
# program or as an escape sequence.
git show HEAD:CHANGELOG.md \
  | CARRIED_SECTION="$section" awk '
      function put_section() {
        if (seen && last ~ /[^[:space:]]/) { print "" }
        print ENVIRON["CARRIED_SECTION"]
        print ""
        done = 1
      }
      !done && /^## / { put_section() }
      { print; seen = 1; last = $0 }
      END { if (!done) { put_section() } }
    ' > CHANGELOG.md
git add CHANGELOG.md
git commit --quiet -m "$message"
echo "carried the ${previous} changelog, resolving its conflict in CHANGELOG.md:" \
     "the ${previous} section now sits above this checkout's newest section" >&2
