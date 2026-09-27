#!/usr/bin/env bash
# Tag the production commit, commit the changelog locally, publish a GitHub
# Release.
#
# Build phase 4.15, changed on 2026-09-27. Runs only on a push to
# `production`, which by the release flow means a release pull request was
# merged after CI reported on it.
#
# THIS SCRIPT NEVER PUSHES TO `production`, and neither does any other step of
# the release job. Until 2026-09-27 it committed the changelog and pushed that
# commit straight to `production`. That made the release robot a writer of the
# production branch, and the owner wants `production` to accept changes from
# the owner's account alone. GitHub refuses to exempt the Actions robot from a
# ruleset on a personal-account repository, so the robot stopped writing
# instead. What it does now:
#
#   1. Tags RELEASE_SHA, the production commit derive_version.sh read, with an
#      annotated tag, after checking that commit is on `origin/production`.
#      The tag is the only thing pushed from this script.
#   2. Commits the changelog in this checkout only. open_backmerge_pr.sh
#      carries that commit to `develop` in a pull request, and `production`
#      receives it with the next release.
#   3. Publishes the GitHub Release from the changelog section just written.
#
# WHY THIS WORKFLOW DOES NOT TRIGGER ITSELF. It fires on a push to the
# `production` branch, and nothing this job pushes is that branch: a tag does
# not match a `branches:` filter, and the back-merge branch is not
# `production`. That is structural, and it no longer rests on the token. The
# token still helps: events raised by `secrets.GITHUB_TOKEN` start no workflow
# runs, which GitHub documents.
#
# The `[skip ci]` marker stays on the changelog commit's subject. It is part of
# the subject commit_lib.sh recognises, and it keeps ci.yml's push trigger off
# the changelog commit if it ever becomes the head of a push to `develop`, for
# example through a rebase merge of the back-merge pull request. No test reads
# the marker's effect on GitHub, which is a property of GitHub's dispatcher
# rather than of this repository.
set -euo pipefail

# shellcheck source=.github/release/commit_lib.sh
. "$(dirname "$0")/commit_lib.sh"

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
release_sha="${RELEASE_SHA:?RELEASE_SHA is required}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

# The tag goes on a commit that is on `production`, checked against the remote
# rather than assumed from the checkout. A tag on a commit that is not on
# `production` would publish a release of code that never shipped.
release_sha="$(git rev-parse --verify "${release_sha}^{commit}")"
git fetch --quiet origin production
if ! git merge-base --is-ancestor "$release_sha" origin/production; then
  echo "refusing to tag ${release_sha}: it is not on origin/production" >&2
  exit 1
fi

# Annotated rather than lightweight: an annotated tag carries a tagger, a date
# and a message, and derive_version.sh's `git describe` reads it to find where
# the previous release ended. Pushed by its full ref name, so nothing but the
# tag can be pushed by this line.
git tag -a "${version}" "${release_sha}" -m "Release ${version}"
git push origin "refs/tags/${version}"

# The changelog commit, LOCAL ONLY. There is deliberately no push here: the
# commit leaves this job only on the back-merge branch open_backmerge_pr.sh
# pushes. The subject comes from commit_lib.sh, the one place that also
# recognises it when it arrives in the next release's range.
git add CHANGELOG.md
if git diff --cached --quiet; then
  echo "changelog produced no change; not committing" >&2
else
  git commit --quiet -m "$(release_changelog_subject "${version}")"
fi

# The release body is the changelog section just written, not the tag
# annotation, because the section is the part a human wrote commits toward.
# awk stops at the next `## ` heading so only this version's section is taken.
# `--verify-tag` makes gh refuse rather than create a missing tag, since gh
# would otherwise cut one from the default branch, which is `develop`.
notes="$(awk -v v="## ${version}" 'index($0,v)==1{f=1;next} f&&/^## /{exit} f' CHANGELOG.md)"
printf '%s' "$notes" | gh release create "${version}" --verify-tag --title "${version}" --notes-file -
echo "released ${version} at ${release_sha}" >&2
