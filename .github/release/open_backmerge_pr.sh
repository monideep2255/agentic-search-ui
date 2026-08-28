#!/usr/bin/env bash
# Open the back-merge pull request from `production` into `develop`.
#
# Build phase 4.15. The changelog commit and the tag land on `production`, and
# `develop` is the default branch every phase branch is cut from. Without this
# step, every future phase branch starts life missing the changelog, and the two
# lines drift a little further apart at every release.
#
# A pull request rather than a direct push, deliberately. A back-merge can
# conflict, and an automatic conflicting push to the default branch is worse
# than a pull request somebody has to look at. This is the same reasoning
# `.claude/rules/git-workflow.md` applies to everything else that reaches
# `develop`.
#
# NO CI RUNS ON THE PULL REQUEST THIS OPENS, and that is not an oversight to
# be quietly fixed by whoever reads this next. Findings F-4.15-J-10 and
# F-4.15-A-12, filed independently by a judge and an adversary. `gh pr create`
# authenticated with the workflow's built-in `GITHUB_TOKEN` does not raise
# events that start workflow runs; that is GitHub's recursion guard working as
# designed, and it is what stops this workflow from triggering itself.
#
# The gap is narrower than it sounds and the pull request body says so too: the
# content here is code that already passed CI on the release pull request, so
# nothing re-checks the MERGE rather than unreviewed code arriving.
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

git fetch origin develop production

# If develop already contains everything on production, there is nothing to
# carry back and an empty pull request would be noise. This is the common case
# when a release changed nothing but the changelog and develop was already
# ahead.
if git merge-base --is-ancestor origin/production origin/develop; then
  echo "develop already contains production; no back-merge needed" >&2
  exit 0
fi

git checkout -B "$branch" origin/production
git push -u origin "$branch"

gh pr create \
  --base develop \
  --head "$branch" \
  --title "chore: back-merge ${version} into develop" \
  --body "Automated back-merge of release ${version}.

The release commit and tag land on \`production\`. This carries them back to
\`develop\`, which is the default branch and the one every phase branch is cut
from, so the two lines do not drift.

NO CI HAS RUN ON THIS PULL REQUEST. It was opened by a workflow using the
built-in \`GITHUB_TOKEN\`, and GitHub does not start workflow runs from events
that token raises. Before merging, confirm the gates were green on the release
pull request that produced \`${version}\`, because that is the run which
actually checked this code. The content here already passed there; what is
missing is a re-check of the merge itself.

Opened by \`.github/workflows/release.yml\`. Review and merge. If it conflicts,
resolve it on this branch; never force-push \`develop\` to make it apply."
echo "back-merge pull request opened for ${version}" >&2
