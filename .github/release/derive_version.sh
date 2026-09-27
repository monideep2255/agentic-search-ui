#!/usr/bin/env bash
# Derive the next semantic version from Conventional Commits since the last tag.
#
# Build phase 4.15. Reads commit subjects with `git log`, NEVER through a
# `${{ github.event... }}` interpolation. That is a security property, not a
# style choice: a commit subject is attacker-influenced text, and interpolating
# it into a shell body is the GitHub Actions script-injection sink. Here it
# arrives as data on stdin and is only ever matched against, never executed.
#
# What a commit MEANS is decided in `.github/release/commit_lib.sh`, not here.
# This script used to carry its own patterns and `write_changelog.sh` carried
# different ones, which is finding F-4.15-A-03: a release could be major while
# its changelog had no breaking section. One parser, two callers. That includes
# the release job's own changelog commit, which arrives on `production` through
# `develop` one release late and is never counted (commit_lib.sh says why).
#
# WHERE THE PREVIOUS RELEASE IS FOUND. By its tag, with `git describe` from
# HEAD, which is the tip of `production` as the workflow checked it out. Since
# 2026-09-27 the tag sits on that tip, a production merge commit, rather than
# on a changelog commit pushed on top of it. `git describe` needs only that the
# tagged commit be an ancestor of HEAD, and it is: `production` moves forward
# by merges only, and a ruleset forbids a force-push that could rewrite it.
#
# THE COMMIT THIS VERSION IS FOR is written out as `release_sha`, the HEAD this
# script read. tag_and_release.sh tags exactly that commit, and
# write_changelog.sh lists exactly the commits up to it, so a later step moving
# HEAD (carry_previous_changelog.sh can) never moves the tag or the notes.
#
# Bump rules, from the Conventional Commits spec this repository adopted on
# 2026-07-26 (.claude/rules/git-workflow.md):
#   BREAKING CHANGE footer, or `!` before the colon  -> major
#   feat                                             -> minor
#   anything else (fix, docs, chore, refactor, test, ci, security) -> patch
set -euo pipefail

# shellcheck source=.github/release/commit_lib.sh
. "$(dirname "$0")/commit_lib.sh"

# A RELEASE AN EARLIER RUN STARTED IS FINISHED, NOT SKIPPED (F-REL-A04). If
# this job already tagged HEAD, an earlier run of it got at least that far and
# then failed: `gh release create` answered 502, say, or the pull request
# could not be opened. Read as "no commits since the tag", the owner's re-run
# would report success and release nothing, and the release would stay without
# its GitHub Release or its back-merge for good. So the release is picked up
# under its own version instead, with the previous tag it was derived from.
# Every later step checks what already exists before it acts, so a re-run
# makes no second tag, no second GitHub Release and no second pull request.
#
# Only a tag this job made counts (commit_lib.sh's release_job_tag_at). A tag
# the owner made by hand on HEAD still means "nothing to release", which is
# what the data engineering repository's hand-tagged first release relies on.
resume_version="$(release_job_tag_at HEAD)"
if [ -n "$resume_version" ]; then
  previous="$(git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' \
    --exclude "$resume_version" HEAD 2>/dev/null || echo "")"
  release_sha="$(git rev-parse --verify 'HEAD^{commit}')"
  echo "HEAD ${release_sha} already carries ${resume_version}, tagged by this job:" \
       "finishing that release rather than starting another" >&2
  {
    echo "should_release=true"
    echo "previous_tag=${previous}"
    echo "version=${resume_version}"
    echo "bump=resume"
    echo "release_sha=${release_sha}"
  } >> "$GITHUB_OUTPUT"
  exit 0
fi

# --match is load-bearing, not a tidiness flag. A bare `git describe --tags`
# returns the nearest tag of ANY shape, and this repository already carries
# `baseline/pre-drift-fix`. Without the filter the first run computed
# `vbaseline/pre-drift-fix.1.0` and would have tagged a release under it
# (finding F-4.15-05). The pattern admits only `vN.N.N`.
previous="$(git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' 2>/dev/null || echo "")"
if [ -z "$previous" ]; then
  range=""
  prev_version="0.0.0"
  echo "no previous tag: this is the first release" >&2
else
  range="${previous}..HEAD"
  prev_version="${previous#v}"
  echo "previous tag: ${previous}" >&2
fi

IFS='.' read -r major minor patch <<< "$prev_version"
major="${major:-0}"; minor="${minor:-0}"; patch="${patch:-0}"

# Belt and braces after F-4.15-05. --match should make this unreachable, but a
# version that is not three integers must stop the release rather than be
# coerced into one: a wrong tag is published and permanent, an aborted run is
# not.
#
# The guard used to test `*[!0-9]*` only, which finding F-4.15-A-08 defeated
# with `v1.2.08`: every character is a digit, so the guard passed, and bash
# then read `08` as octal, failed the arithmetic, and let the script exit 0
# having emitted `should_release=true` with the previous version unchanged.
# Leading zeros are therefore rejected by name. Semantic versioning forbids
# them anyway, so nothing legitimate is lost, and the whole octal question
# disappears rather than being worked around.
for part in "$major" "$minor" "$patch"; do
  case "$part" in
    ''|*[!0-9]*)
      echo "previous tag ${previous} does not parse as vMAJOR.MINOR.PATCH" >&2
      exit 1
      ;;
    0) ;;
    0*)
      echo "previous tag ${previous} has a leading zero in a version component" \
           "(${part}); semantic versioning forbids it and bash reads it as octal" >&2
      exit 1
      ;;
  esac
done

# A release with no commits since the last tag is a no-op, not a version bump.
# This runs BEFORE the scan rather than after it, so an empty range takes the
# early exit instead of being read as "no breaking commits found".
shas="$(release_commit_shas "$range")"
if [ -z "$shas" ]; then
  if [ -n "$range" ]; then
    echo "no commits since ${previous}; nothing to release" >&2
  else
    echo "no commits at all; nothing to release" >&2
  fi
  echo "should_release=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

bump="patch"
count=0
while IFS= read -r sha; do
  [ -n "$sha" ] || continue
  count=$((count + 1))
  subject="$(release_commit_field "$sha" '%s')"
  body="$(release_commit_field "$sha" '%b')"
  if release_is_breaking "$subject" "$body"; then
    bump="major"
    break
  fi
  if [ "$(release_subject_type "$subject")" = "feat" ]; then
    bump="minor"
  fi
done <<< "$shas"

# The loop must have seen something. A scan that read zero commits and reported
# `patch` is indistinguishable from a scan that read every commit and found
# nothing worth more, which is exactly the confusion F-4.15-J-11 exploited.
if [ "$count" -eq 0 ]; then
  echo "read no commits from a non-empty range; refusing to publish a version" >&2
  exit 1
fi

# Base 10 explicitly. The guard above already rejects a leading zero, so this
# cannot fire today; it is here so that a future change to the guard cannot
# quietly reintroduce octal parsing (F-4.15-A-08).
case "$bump" in
  major) major=$((10#$major + 1)); minor=0; patch=0 ;;
  minor) minor=$((10#$minor + 1)); patch=0 ;;
  patch) patch=$((10#$patch + 1)) ;;
esac

next="v${major}.${minor}.${patch}"

# A version identical to the tag it replaces means the arithmetic above did not
# happen. Publishing it would die on an already-existing tag after the
# changelog was written, which is the tail of F-4.15-A-08 and is worse than
# stopping here.
if [ -n "$previous" ] && [ "$next" = "$previous" ]; then
  echo "computed version ${next} is the previous tag; refusing to release" >&2
  exit 1
fi

release_sha="$(git rev-parse --verify 'HEAD^{commit}')"

echo "bump=${bump} -> ${next} (${count} commits) at ${release_sha}" >&2
{
  echo "should_release=true"
  echo "previous_tag=${previous}"
  echo "version=${next}"
  echo "bump=${bump}"
  echo "release_sha=${release_sha}"
} >> "$GITHUB_OUTPUT"
