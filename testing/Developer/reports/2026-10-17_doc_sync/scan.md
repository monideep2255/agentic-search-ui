# Leak scan: tracked symlink targets

A tracked symlink stores its target as a path in its blob (mode 120000). The scan's whole-tree pass ran the private-name check in `--all` mode, which reads the file a link points to and never the link's own text, so a link whose target named the owner's private repository stayed public for months (DECISIONS.md, 2026-10-17). The owner approved this fix the same day.

## Table of contents

- [What changed](#what-changed)
- [Tests](#tests)
- [Mutations](#mutations)
- [Live checks](#live-checks)
- [What it still cannot do](#what-it-still-cannot-do)

## What changed

- `.claude/skills/ship/scripts/check_public_leaks.py` gains an index pass: every mode 120000 entry in `git ls-files -s` has its blob read as the stored target, so a link already on the base is read too.
- The commit, staged and working-copy passes now read a symlink an outgoing commit or the working copy adds or retargets as one target, from the `new file mode 120000` line or the mode on the `index` line, instead of as a content line. The staged ones are left to the index pass.
- Each target goes through every existing rule and, as a line of the `--message` file, through the private-name check. A target that is absolute (`/`, `\`, `~` or a drive letter) also fails as `absolute-symlink`.
- A FAIL line names the link, a category and a mask, never the target. A tracked link the push does not change says "already on the base: remove it here and tell the owner".
- A relative target that leaves the repository prints `NOTE symlink <path>: ...`, the link's path only, and does not fail.
- The missing private-name check still fails the scan unless `--allow-missing-private-check` is passed. That rule is unchanged.
- `.claude/skills/ship/SKILL.md`, "The public-leak scan": one bullet under "What it reads" and one under "What it still cannot catch" state exactly this.

## Tests

`tests/ci/test_check_public_leaks.py` gains 19 cases, most run both with the link in an outgoing commit and with the link already on the base:

| Case | Expected |
|---|---|
| Absolute target, four shapes (posix root, home, drive with either slash) | Exit 1, `[absolute-symlink]`, a commit FAIL line when outgoing, "already on the base" when not |
| Home directory target | Exit 1, `[local-path]`, the name never printed |
| Target the private-name check flags (stand-in check monkeypatched, made-up term) | Exit 1, `FAIL private-name check: symlink ...`, `[owner-term]`, the term never printed |
| Relative target leaving the repository | Exit 0, a NOTE naming the link, no target text |
| Targets inside the repository | Exit 0, no FAIL, no NOTE |
| A link retargeted to an absolute path, in a commit and in the working copy | Exit 1 at that location |
| A FAIL line with a planted target | No five-character run of the target in the output |

Result: 251 passed in the file. `ruff check` (no path): all checks passed. isort as gate02 runs it: exit 0.

## Mutations

Each mutant was a copy of the script, run through `CHECK_PUBLIC_LEAKS_SCRIPT` against the 19 symlink cases. The real script was never edited, so nothing needed restoring.

| Mutation | Result |
|---|---|
| Skip symlinks in the index pass | 8 failed, every on-the-base case |
| Treat an absolute target as a NOTE | 12 failed |
| Print the raw target in the FAIL line | 12 failed |

The first run of the first mutant also failed the outgoing cases. That showed the commit pass never saw a newly added link, because the `new file mode` line was read before the mode was recorded. It was fixed, and an outgoing test now asserts a `FAIL commit ...` line, so the commit pass is proved on its own.

## Live checks

- On this branch: three tracked symlinks, two inside the repository and one to the public sibling, which gives one NOTE. The private-name check passes and the exit code is 0.
- On the commit before the cleaned guide replaced the old link, in a throwaway worktree, the new script prints `FAIL private-name check: symlink docs/Claude_security_plugin_usage.md (stored target, tracked) [owner-term] (already on the base: ...)` and exits 1. The script before this change, run the same way, printed `private-name check: PASS` and exited 0.

## What it still cannot do

- An untracked symlink's target is not read until it is staged or committed. The commit pass reads it then, before any push.
- Where a relative target that leaves the repository actually points is for a person to confirm.
- Git history still holds the old targets. Rewriting it is the owner's call.
