#!/usr/bin/env bash
# Commit the changelog, push the back-merge branch, tag the production commit,
# publish a GitHub Release.
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
# instead. What it does now, in this order:
#
#   1. Commits the changelog in this checkout. On a re-run that picked up an
#      earlier run's changelog commit (resume_release.sh), there is nothing
#      to commit.
#   2. Pushes this checkout as `chore/back-merge-<version>`. The changelog
#      commit is then safe on `origin` before anything permanent happens.
#      open_backmerge_pr.sh opens the pull request that carries it to
#      `develop`, and `production` receives it with the next release.
#   3. Tags RELEASE_SHA, the production commit derive_version.sh read, with an
#      annotated tag, after checking that commit is on `origin/production`.
#   4. Publishes the GitHub Release from this version's changelog section.
#
# WHY THE BRANCH GOES BEFORE THE TAG (F-REL-A04). The tag is the point of no
# return: once it is on `origin`, derive_version.sh treats the release as
# started. The order used to be tag, then GitHub Release, then the branch, in
# the next script, so a 502 from `gh release create` left a tag with no
# release, and a changelog commit that existed only on the discarded runner.
# Nothing could recover it. Now every step before the tag can simply run again,
# and every step after it checks what already exists: the tag is made only if
# it is missing, and the GitHub Release is created only if `gh release view`
# cannot find it. A re-run of a failed job therefore finishes the release and
# never makes a second tag or a second release.
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
branch="chore/back-merge-${version}"

# How long to wait between attempts at the GitHub Release: the Nth retry waits
# N times this many seconds. The workflow leaves it at the default; the tests
# set it to 0.
retry_delay="${RELEASE_RETRY_DELAY_S:-5}"
case "$retry_delay" in
  ''|*[!0-9]*)
    echo "RELEASE_RETRY_DELAY_S must be a whole number of seconds, not '${retry_delay}'" >&2
    exit 1
    ;;
esac
release_attempts=5

release_as_bot

# The tag goes on a commit that is on `production`, checked against the remote
# rather than assumed from the checkout. A tag on a commit that is not on
# `production` would publish a release of code that never shipped. Checked
# first, so a refusal happens before anything is pushed.
release_sha="$(git rev-parse --verify "${release_sha}^{commit}")"
git fetch --quiet origin production
if ! git merge-base --is-ancestor "$release_sha" origin/production; then
  echo "refusing to tag ${release_sha}: it is not on origin/production" >&2
  exit 1
fi

# 1. The changelog commit, in this checkout. The subject comes from
# commit_lib.sh, the one place that also recognises it when it arrives in the
# next release's range.
git add CHANGELOG.md
if git diff --cached --quiet; then
  echo "no changelog change to commit: this checkout already holds the" \
       "${version} changelog commit an earlier run made" >&2
else
  git commit --quiet -m "$(release_changelog_subject "${version}")"
fi

# The release body is this version's changelog section, not the tag
# annotation, because the section is the part a human wrote commits toward.
# commit_lib.sh's section reader stops at the next `## ` heading, whatever it
# says, so only this version's section is taken; `tail` drops its heading,
# which the release page shows as its title. Read before anything is pushed, so
# a changelog without this version's section stops the job while nothing
# permanent has happened.
notes="$(release_changelog_section "${version}" < CHANGELOG.md | tail -n +2)"
if [ -z "$notes" ]; then
  echo "CHANGELOG.md has no ${version} section to publish; refusing to tag." \
       "Nothing has been pushed." >&2
  exit 1
fi

# 2. The back-merge branch, BEFORE the tag. Pushed by its full ref name, so
# this line can create or update `chore/back-merge-<version>` and nothing
# else. Pushing a branch an earlier run already pushed, at the same commit,
# changes nothing. Skipped when `develop` already has this commit, which
# happens only on a re-run after the back-merge was merged.
git fetch --quiet origin develop
if git merge-base --is-ancestor HEAD origin/develop; then
  echo "develop already has the ${version} changelog commit; no back-merge" \
       "branch to push" >&2
else
  git push origin "HEAD:refs/heads/${branch}"
fi

# 3. The tag, unless an earlier run made it. Annotated rather than lightweight:
# an annotated tag carries a tagger, a date and a message, derive_version.sh's
# `git describe` reads it to find where the previous release ended, and its
# tagger is how a re-run recognises a tag this job made. Pushed by its full ref
# name, so nothing but the tag can be pushed by this line.
tagged="$(git rev-parse --verify --quiet "refs/tags/${version}^{commit}" || true)"
if [ -z "$tagged" ]; then
  git tag -a "${version}" "${release_sha}" -m "Release ${version}"
  git push origin "refs/tags/${version}"
elif [ "$tagged" = "$release_sha" ]; then
  echo "${version} is already tagged on ${release_sha} by an earlier run;" \
       "not tagging again" >&2
else
  echo "refusing to release ${version}: that tag already exists on ${tagged}," \
       "not on ${release_sha}" >&2
  exit 1
fi

# 4. The GitHub Release, exactly once. Each attempt first asks whether the
# release exists, because a 502 can arrive after GitHub has in fact created
# it. `--verify-tag` makes gh refuse rather than create a missing tag, since
# gh would otherwise cut one from the default branch, which is `develop`; the
# retry is what lets it wait out GitHub's API catching up with the tag pushed
# a moment ago (F-REL-A04). Bounded: five attempts, fifty seconds of waiting at
# the default delay, and then the job fails with the branch and the tag safe,
# so a re-run finishes it.
attempt=1
while :; do
  if gh release view "${version}" > /dev/null 2>&1; then
    echo "the ${version} GitHub Release exists; not creating another" >&2
    break
  fi
  if printf '%s' "$notes" \
      | gh release create "${version}" --verify-tag --title "${version}" --notes-file -; then
    echo "released ${version} at ${release_sha}" >&2
    break
  fi
  if [ "$attempt" -ge "$release_attempts" ]; then
    echo "::error title=GitHub Release ${version} not created::gh release create" \
         "failed ${attempt} times. The ${version} tag and the ${branch} branch," \
         "with the changelog, are safe on origin. Re-run this job: it picks the" \
         "release up and creates only what is missing."
    exit 1
  fi
  wait_s=$((retry_delay * attempt))
  echo "gh release create failed (attempt ${attempt} of ${release_attempts});" \
       "trying again in ${wait_s} s" >&2
  sleep "$wait_s"
  attempt=$((attempt + 1))
done
