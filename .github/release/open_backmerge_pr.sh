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

Opened by \`.github/workflows/release.yml\`. Review and merge. If it conflicts,
resolve it on this branch; never force-push \`develop\` to make it apply."
echo "back-merge pull request opened for ${version}" >&2
