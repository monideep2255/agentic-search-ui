#!/usr/bin/env bash
# Commit the changelog, tag the release, push both, publish a GitHub Release.
#
# Build phase 4.15. Runs only on a push to `production`, which by the release
# flow means a release pull request was merged after CI reported on it.
#
# WHY THIS WORKFLOW DOES NOT TRIGGER ITSELF, stated honestly after finding
# F-4.15-J-13, which caught the comment here naming the weaker of two
# mechanisms as the load-bearing one.
#
# The load-bearing mechanism is the TOKEN. This job pushes with
# `secrets.GITHUB_TOKEN`, and GitHub documents that events raised by that token
# do not start new workflow runs. That is what actually terminates the loop,
# and it holds whether or not the commit message says anything.
#
# The `[skip ci]` marker on the changelog commit is defence in depth, not the
# mechanism. It matters if the push is ever moved to a personal access token or
# a GitHub App token, which DO raise events, and it also keeps the ci.yml push
# trigger off a commit that changes only the changelog.
#
# WHAT IS NOT VERIFIED, said plainly rather than left to be assumed: neither
# statement above is asserted by any test in this repository. No arm reads the
# `[skip ci]` marker, so deleting it from the commit message below leaves every
# gate green, and no arm can observe the token behaviour at all, since it is a
# property of GitHub's event dispatcher rather than of this repository. The
# recursion has also never been observed, because no release has been cut yet.
# Per `.claude/rules/self-eval-loop.md` a comment asserting a correctness
# property needs a test asserting the same property; this comment therefore
# asserts no property it cannot support, and records the gap instead. Closing
# it is finding F-4.15-A-13's job, which owns the absence of any behavioural
# gate over these scripts.
set -euo pipefail

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add CHANGELOG.md
if git diff --cached --quiet; then
  echo "changelog produced no change; not committing" >&2
else
  git commit -m "docs(changelog): release ${version} [skip ci]"
  git push origin HEAD:production
fi

# Annotated rather than lightweight: an annotated tag carries a tagger, a date
# and a message, which is what `git describe` and the next run's
# derive_version.sh read to find where the previous release ended.
git tag -a "${version}" -m "Release ${version}"
git push origin "${version}"

# The release body is the changelog section just written, not the tag
# annotation, because the section is the part a human wrote commits toward.
# awk stops at the next `## ` heading so only this version's section is taken.
notes="$(awk -v v="## ${version}" 'index($0,v)==1{f=1;next} f&&/^## /{exit} f' CHANGELOG.md)"
printf '%s' "$notes" | gh release create "${version}" --title "${version}" --notes-file -
echo "released ${version}" >&2
