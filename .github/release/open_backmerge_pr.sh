#!/usr/bin/env bash
# Open the back-merge pull request that carries a release's changelog into
# `develop`.
#
# Build phase 4.15, changed on 2026-09-27. The tag lands on `production`. The
# changelog commit does NOT: tag_and_release.sh made it on top of the
# production commit it tagged and pushed it as `chore/back-merge-<version>`,
# because the release job never pushes to `production`. This pull request is
# the one route that commit takes into `develop`. Once the owner merges it,
# `develop` has the changelog, and `production` receives it with the next
# release pull request.
#
# ONE PULL REQUEST PER RELEASE, on a re-run too (F-REL-A04). If a pull request
# from the branch is already open, an earlier run of this release opened it,
# and this opens no second one.
#
# IF THE OWNER HAS NOT MERGED THE PREVIOUS BACK-MERGE when the next release
# runs, carry_previous_changelog.sh has already merged the previous changelog
# commit into this checkout, so this pull request carries both, and merging it
# completes the older one too.
#
# A pull request rather than a direct push, deliberately. A back-merge can
# conflict, and an automatic conflicting push to the default branch is worse
# than a pull request somebody has to look at. `develop` also accepts changes
# from the owner's account alone, so a direct push would be refused anyway.
#
# NO CI RUNS ON THE PULL REQUEST THIS OPENS, and that is not an oversight to
# be quietly fixed by whoever reads this next. Findings F-4.15-J-10 and
# F-4.15-A-12, filed independently by a judge and an adversary. `gh pr create`
# authenticated with the workflow's built-in `GITHUB_TOKEN` does not raise
# events that start workflow runs; that is GitHub's recursion guard working as
# designed.
#
# The gap is narrower than it sounds and the pull request body says so too: the
# content here is the changelog plus code that already passed CI on the release
# pull request, so nothing re-checks the MERGE rather than unreviewed code
# arriving.
#
# Do NOT close this by switching to a personal access token or a GitHub App
# token. Both would work and both put a token with write access into the
# release path, which is a credential decision for the product owner rather
# than something to change while touching this file.
set -euo pipefail

# shellcheck source=.github/release/commit_lib.sh
. "$(dirname "$0")/commit_lib.sh"

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
previous="${PREVIOUS_TAG:-}"
branch="chore/back-merge-${version}"

git fetch --quiet origin develop

# HEAD is this job's work: the tagged production commit, the changelog commit
# on top of it, and, when one was needed, the carried previous changelog.
# tag_and_release.sh has already pushed it as the back-merge branch. If
# `develop` already contains all of it there is nothing to carry back, which
# happens only on a re-run after the back-merge was merged.
if git merge-base --is-ancestor HEAD origin/develop; then
  echo "develop already contains this release and its changelog; no back-merge needed" >&2
  exit 0
fi

# A MISSING PREVIOUS SECTION IS NAMED HERE, from the file being pushed rather
# than from anything an earlier step said (F-REL-J03). The carry step warns
# when it cannot bring the previous release's section in; this is the place
# the owner cannot miss, because they have to open this pull request anyway.
missing=""
if [ -n "$previous" ] && [ -z "$(release_changelog_section "$previous" < CHANGELOG.md)" ]; then
  missing="A CHANGELOG SECTION IS MISSING. CHANGELOG.md on this branch has no ${previous} section,
so merging it as it stands leaves that release out of the changelog. The
release job could not carry it forward, and the job's log says why. Before
merging, add it on this branch, directly below the \`## ${version}\` section.
Its heading is \`## ${previous} (<date>)\`. Its text is the notes of the
${previous} GitHub Release, or the section on the
\`chore/back-merge-${previous}\` branch if that branch still exists.

"
  echo "::warning title=CHANGELOG.md is missing ${previous}::the back-merge pull request for ${version} says how to add the ${previous} section"
fi

open="$(gh pr list --head "$branch" --base develop --state open --json number --jq length)"
if [ "$open" != "0" ]; then
  echo "a back-merge pull request from ${branch} is already open; not opening another" >&2
  exit 0
fi

gh pr create \
  --base develop \
  --head "$branch" \
  --title "chore: back-merge ${version} into develop" \
  --body "${missing}Automated back-merge of release ${version}.

The tag \`${version}\` is on \`production\`. The changelog commit for this
release is NOT: the release job never pushes to \`production\`. This pull
request carries it to \`develop\`, and \`production\` receives it with the next
release. Merge this before cutting the next release branch, so that release's
changelog is written on top of this one's. If an earlier release's back-merge
was still open when this release ran, this pull request carries that
release's changelog as well, and merging it completes the earlier one.

Merge with a merge commit. The next release recognises this changelog commit
and leaves it out of its notes.

NO CI HAS RUN ON THIS PULL REQUEST. It was opened by a workflow using the
built-in \`GITHUB_TOKEN\`, and GitHub does not start workflow runs from events
that token raises. Before merging, confirm the gates were green on the release
pull request that produced \`${version}\`, because that is the run which
actually checked this code. The content here already passed there; what is
missing is a re-check of the merge itself.

Opened by \`.github/workflows/release.yml\`. Review and merge. If it conflicts,
resolve it on this branch; never force-push \`develop\` to make it apply."
echo "back-merge pull request opened for ${version}" >&2
