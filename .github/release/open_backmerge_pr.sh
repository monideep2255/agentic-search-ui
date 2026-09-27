#!/usr/bin/env bash
# Open the back-merge pull request that carries a release's changelog into
# `develop`.
#
# Build phase 4.15, changed on 2026-09-27. The tag lands on `production`. The
# changelog commit does NOT: tag_and_release.sh made it in this checkout only,
# on top of the production commit it tagged, because the release job never
# pushes to `production`. This pull request is the one route that commit takes
# out of the job. Once the owner merges it, `develop` has the changelog, and
# `production` receives it with the next release pull request.
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

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
branch="chore/back-merge-${version}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git fetch --quiet origin develop

# HEAD is this job's local work: the tagged production commit, the changelog
# commit on top of it, and, when one was needed, the carried previous
# changelog. If `develop` already contains all of it there is nothing to carry
# back, which happens only when the changelog produced no change and `develop`
# was already ahead of `production`.
if git merge-base --is-ancestor HEAD origin/develop; then
  echo "develop already contains this release and its changelog; no back-merge needed" >&2
  exit 0
fi

# The branch is pushed by its full ref name, so this line can create or update
# `chore/back-merge-<version>` and nothing else.
git checkout --quiet -B "$branch"
git push -u origin "HEAD:refs/heads/${branch}"

gh pr create \
  --base develop \
  --head "$branch" \
  --title "chore: back-merge ${version} into develop" \
  --body "Automated back-merge of release ${version}.

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
