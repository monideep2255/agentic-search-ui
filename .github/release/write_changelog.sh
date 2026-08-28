#!/usr/bin/env bash
# Prepend a release section to CHANGELOG.md, grouped by Conventional Commit type.
#
# Build phase 4.15. Commit subjects arrive via `git log`, never via a
# `${{ github.event... }}` interpolation. See derive_version.sh for why that is
# a security property rather than a style choice.
#
# What a commit MEANS is decided in `.github/release/commit_lib.sh`, which is
# also where the version reader asks. Findings F-4.15-A-01, A-03 and A-07 were
# one class, two scripts disagreeing about what a Conventional Commit is, so
# the two readers became one.
#
# EVERY COMMIT IN THE RANGE APPEARS EXACTLY ONCE. The previous version tested
# each commit against five hardcoded patterns and silently dropped whatever
# matched none, so `revert`, `perf`, `build`, `style` and any capitalised or
# non-conventional subject vanished while still counting toward the version
# (F-4.15-A-07). Now every commit is classified into exactly one group, the
# last of which is a catch-all, and the script aborts unless the number of
# entries in the assembled section equals the number of commits read.
#
# The file is written newest-first, which is what `.claude/rules/writing-style.md`
# requires of a changelog: "a changelog is a dated bullet list, newest first".
#
# No temporary file is cleaned up here on purpose. This runs on an ephemeral
# GitHub Actions runner whose whole filesystem is discarded, and this
# repository's `block-bash-delete.sh` hook treats a deletion inside a script as
# something a human should approve. Leaving the scratch file costs nothing and
# keeps the script free of a delete a reviewer would have to reason about.
set -euo pipefail

# shellcheck source=.github/release/commit_lib.sh
. "$(dirname "$0")/commit_lib.sh"

version="${RELEASE_VERSION:?RELEASE_VERSION is required}"
previous="${PREVIOUS_TAG:-}"
today="$(date -u +%Y-%m-%d)"
range="${previous:+${previous}..HEAD}"

work="$(mktemp -d)"
section="${work}/section.md"

# Groups in the order a reader wants them: the breaking news first, the
# housekeeping last, and the catch-all after that so nothing can fall off the
# end. Ordering is by severity, which is what the Conventional Commits spec
# implies, not alphabetical.
# TWO CLASSES OF GROUP, and the split is the whole point of this file.
#
# `user_group_keys` get a bullet each, because a person using the product can
# perceive the difference they made. `internal_group_keys` get a COUNTED
# SUMMARY LINE and no bullets, because "tracker: refresh the computed test
# count" is true, useful to us, and noise to everyone else.
#
# WHY A COUNT AND NOT A DELETION. Finding F-4.15-A-07 was that this script
# silently DROPPED every commit whose type it did not recognise while the
# version deriver still counted it, so a release could be built from commits
# that appeared nowhere. The populate-check below exists because of it. This
# split does not reopen that: every commit still reaches the reader, either as
# a bullet or inside a stated number, and the check now proves
# bullets + counted == total rather than bullets == total. Silence is the
# defect; brevity with a number is not.
#
# Measured on the first real release, which is what prompted this: 798 commits
# produced 798 bullets and a 62,014-character GitHub Release page, of which 518
# were maintenance and other.
user_group_keys="breaking revert feat fix security"
internal_group_keys="maintenance other"
group_keys="$user_group_keys $internal_group_keys"
group_heading_breaking="Breaking changes"
group_heading_revert="Reverts"
group_heading_feat="Features"
group_heading_fix="Fixes"
group_heading_security="Security"
group_heading_maintenance="Maintenance"
group_heading_other="Other changes"

for key in $group_keys; do
  : > "${work}/group_${key}.md"
done

# Classify by what the shared parser says, in the same precedence order the
# groups are printed. A breaking commit appears under Breaking changes and
# nowhere else, so a reader never meets the same sha twice and no commit can be
# counted into two groups and out of none.
classify() { # <subject> <body>
  local subject="$1" body="$2" type
  if release_is_breaking "$subject" "$body"; then
    printf 'breaking'; return 0
  fi
  type="$(release_subject_type "$subject")"
  case "$type" in
    revert) printf 'revert' ;;
    feat) printf 'feat' ;;
    fix) printf 'fix' ;;
    security) printf 'security' ;;
    docs|refactor|test|chore|ci|build|perf|style) printf 'maintenance' ;;
    *) printf 'other' ;;
  esac
}

shas="$(release_commit_shas "$range")"
total=0
if [ -n "$shas" ]; then
  while IFS= read -r sha; do
    [ -n "$sha" ] || continue
    total=$((total + 1))
    subject="$(release_commit_field "$sha" '%s')"
    body="$(release_commit_field "$sha" '%b')"
    short="$(release_commit_field "$sha" '%h')"
    key="$(classify "$subject" "$body")"
    # Rendered, not raw. A subject is public text somebody else chose, and it
    # is about to enter a permanent artifact (F-4.15-A-02). commit_lib.sh's
    # header says exactly what the escape does and does not cover.
    text="$(release_render_text "$(release_subject_description "$subject")")"
    scope="$(release_render_text "$(release_subject_scope "$subject")")"
    if [ -n "$scope" ]; then
      echo "- ${scope}: ${text} (${short})" >> "${work}/group_${key}.md"
    else
      echo "- ${text} (${short})" >> "${work}/group_${key}.md"
    fi
  done <<< "$shas"
fi

if [ "$total" -eq 0 ]; then
  echo "no commits in range ${range:-<whole history>}; nothing to write" >&2
  exit 1
fi

{
  echo "## ${version} (${today})"
  echo
} > "$section"

for key in $user_group_keys; do
  file="${work}/group_${key}.md"
  [ -s "$file" ] || continue
  eval "heading=\"\${group_heading_${key}}\""
  # A real markdown heading, one level below the version heading above.
  # F-4.15-A-04: these used to be bare paragraph text, so a rendered GitHub
  # Release read as one heading followed by undifferentiated prose and bullets.
  echo "### ${heading}" >> "$section"
  echo >> "$section"
  cat "$file" >> "$section"
  echo >> "$section"
done

# The internal groups, as one stated line rather than as bullets. Counted here
# so the populate-check below can prove nothing went missing.
internal_total=0
internal_parts=""
for key in $internal_group_keys; do
  file="${work}/group_${key}.md"
  [ -s "$file" ] || continue
  n="$(grep -c '^- ' "$file" || true)"
  internal_total=$((internal_total + n))
  # The KEY, not the heading. "1 other changes" reads as a typo, and the
  # headings are written to title a section rather than to follow a number.
  if [ -z "$internal_parts" ]; then
    internal_parts="${n} ${key}"
  else
    internal_parts="${internal_parts}, ${n} ${key}"
  fi
done

if [ "$internal_total" -gt 0 ]; then
  # "Plus" only reads correctly when something came before it. A release with
  # no user-facing changes at all, a documentation or tooling release, is a
  # real case and the first version of this line rendered it as "Plus 2
  # internal changes" under a bare version heading, which reads as a sentence
  # missing its first half. Found by exercising the all-internal path in a
  # throwaway repository before a release needed it, rather than by shipping it.
  listed="$(grep -c '^- ' "$section" || true)"
  if [ "$listed" -gt 0 ]; then
    echo "Plus ${internal_total} internal changes not listed individually (${internal_parts}):" \
         "chores, documentation, tests, refactors and build configuration." >> "$section"
  else
    echo "No user-facing changes. ${internal_total} internal changes" \
         "(${internal_parts}): chores, documentation, tests, refactors and" \
         "build configuration." >> "$section"
  fi
  echo >> "$section"
fi

# The populate-check build phase 4.11 paid for, counted over the ASSEMBLED
# SECTION rather than over an intermediate. This is finding F-4.15-FX-02: the
# first version of this check compared commits read against lines written into
# a group file, and a mutation that deleted the catch-all key from
# `group_keys`, which is F-4.15-A-07 reintroduced exactly, left both counts
# equal while two commits never reached the section. A check that cannot tell
# the artifact from a correlate of the artifact is the safety-by-proxy shape
# this repository has already shipped as a critical three times, so this one
# reads the bytes that ship.
emitted="$(grep -c '^- ' "$section" || true)"
accounted=$((emitted + internal_total))
if [ "$accounted" -ne "$total" ]; then
  echo "read ${total} commits and the section accounts for ${accounted}" \
       "(${emitted} listed, ${internal_total} summarised);" \
       "refusing to write a confidently incomplete changelog" >&2
  exit 1
fi

if [ -n "$previous" ]; then
  echo "Full diff: \`${previous}..${version}\`" >> "$section"
fi

if [ ! -f CHANGELOG.md ]; then
  {
    echo "# Changelog"
    echo
    echo "Every release of System 3, newest first. Generated on each push to"
    echo "\`production\` by \`.github/workflows/release.yml\` from the Conventional"
    echo "Commit subjects since the previous tag. Do not hand-edit a released"
    echo "section: correct the commit history or add a new entry instead."
    echo
  } > CHANGELOG.md
fi

# ONE BLANK LINE ON EACH SIDE OF THE SECTION, produced here rather than assumed
# of the neighbours. Both seams were broken and each was found separately:
#
#   F-4.15-J-07  the head-to-section seam. The structural split copies the
#                preamble verbatim, and the checked-in CHANGELOG.md does not
#                end in a blank line, so `## v0.1.0` landed on the line
#                directly under the prose and did not render as a heading. The
#                earlier fix passed only because the copy it was tested against
#                happened to end in a blank line.
#   F-4.15-FX-01 the section-to-body seam. The blank line meant to follow the
#                `Full diff:` line was a bare `echo` with no redirect, so it
#                went to the Actions log instead of the file, and every release
#                after the first glued its last line onto the previous
#                release's `## ` heading.
#
# normalise_tail strips whatever trailing blank lines a file happens to carry
# and writes back exactly one, which is a property of the output rather than a
# hope about the input. An empty file stays empty, so a CHANGELOG.md that
# begins at its first `## ` heading does not gain a leading blank line.
normalise_tail() { # <in> <out>
  awk '
    { lines[NR] = $0 }
    END {
      last = NR
      while (last > 0 && lines[last] ~ /^[[:space:]]*$/) { last-- }
      if (last == 0) { exit }
      for (i = 1; i <= last; i++) { print lines[i] }
      print ""
    }
  ' "$1" > "$2"
}

# Split at the FIRST `## ` heading rather than at a fixed line number. The
# first version of this counted `head -n 6`, which cut the preamble one line
# short of its trailing blank and produced a version heading glued to the
# prose. A structural split cannot drift when the preamble is reworded.
split_at="$(grep -n '^## ' CHANGELOG.md | head -n 1 | cut -d: -f1 || true)"
if [ -n "$split_at" ]; then
  head -n "$((split_at - 1))" CHANGELOG.md > "${work}/head.raw.md"
  tail -n "+${split_at}" CHANGELOG.md > "${work}/body.md"
else
  cat CHANGELOG.md > "${work}/head.raw.md"
  : > "${work}/body.md"
fi
normalise_tail "${work}/head.raw.md" "${work}/head.md"
normalise_tail "$section" "${work}/section.norm.md"
cat "${work}/head.md" "${work}/section.norm.md" "${work}/body.md" > CHANGELOG.md
echo "CHANGELOG.md updated for ${version} (${total} commits)" >&2
