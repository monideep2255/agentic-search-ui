#!/usr/bin/env bash
# Commit the changelog, tag the release, push both, publish a GitHub Release.
#
# Build phase 4.15. Runs only on a push to `production`, which by the release
# flow means a release pull request was merged after CI reported on it.
#
# The changelog commit carries [skip ci] for a specific reason rather than as a
# habit: without it this workflow pushes to `production`, that push triggers
# this workflow, and the second run tags a version on top of the first. The
# marker is what makes the loop terminate.
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
