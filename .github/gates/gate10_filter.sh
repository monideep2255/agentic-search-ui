#!/usr/bin/env bash
# Section 24 scopes gate 10 to UI-touching pull requests. This decides that.
#
# It FAILS CLOSED, and that direction is the whole point (F-4.14-A-07). The
# first version put `git diff` directly in an `if` condition, where `set -e` is
# suspended, so ANY git error at all took the else branch: a shallow clone, a
# force-pushed base, a garbage-collected SHA. That skipped the WCAG gate, exited
# 0, and printed "No file under frontend/ changed" on a pull request that
# changed frontend files.
#
# So every uncertain path here RUNS the gate. Running it unnecessarily costs a
# few minutes. Skipping it wrongly costs the gate.
#
# The filter is computed here rather than with `on.paths`, because `on.paths`
# would make the whole job vanish from the checks list on a backend-only pull
# request, and a required check that disappears is indistinguishable from one
# that passed.
set -uo pipefail

base="${BASE_SHA:-}"
head="${HEAD_SHA:-}"
output="${GITHUB_OUTPUT:-/dev/stdout}"

if [ -z "$base" ] || [ -z "$head" ]; then
  echo "touched=true" >> "$output"
  echo "Not a pull request, or no base SHA: running the gate."
  exit 0
fi

if ! git cat-file -e "${base}^{commit}" 2>/dev/null \
   || ! git cat-file -e "${head}^{commit}" 2>/dev/null; then
  echo "touched=true" >> "$output"
  echo "::warning title=Gate 10 filter degraded::Could not resolve the base or head commit, so the accessibility gate is running unconditionally rather than being skipped."
  exit 0
fi

if ! changed=$(git diff --name-only "$base" "$head" 2>&1); then
  echo "touched=true" >> "$output"
  echo "::warning title=Gate 10 filter degraded::git diff failed (${changed}), so the accessibility gate is running unconditionally rather than being skipped."
  exit 0
fi

if printf '%s\n' "$changed" | grep -qE '^frontend/'; then
  echo "touched=true" >> "$output"
  echo "Frontend files changed: running the accessibility gate."
else
  echo "touched=false" >> "$output"
  {
    echo "### Gate 10: not applicable"
    echo ""
    echo "No file under \`frontend/\` changed between \`${base}\` and \`${head}\`."
  } >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
fi
