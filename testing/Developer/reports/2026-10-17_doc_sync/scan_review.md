# Scan review: symlink targets in the public leak scan

Fresh review, judge and adversary round for commit 67c9c40c on `chore/scan-symlink-targets`, 2026-10-17. Findings are written as they are established, ids R-SC-01 and up. The reviewer files and never fixes.

## Findings

### R-SC-01: an outgoing symlink is read twice and reported twice
- Severity: minor
- Worse than develop: no (develop reported nothing for it)
- What: a symlink added by an outgoing commit is read once by the commit pass and again by the new index pass, so every finding on it prints twice and the symlink count says 2 for one link. The checklist asks that each link be read exactly once.
- Reproduction: scratch repository, base at the first commit, then `ln -s /opt/<made-up-term>-data/notes.md link1` committed. Output: `FAIL commit 965049c5 symlink link1 (stored target) [absolute-symlink] /***(26 chars)`, `FAIL symlink link1 (stored target, tracked) [absolute-symlink] /***(26 chars)`, the same pair again for `[owner-term]`, and `scanned 1 lines, 1 file names, 2 symlink target(s)`.
- Why it matters: the count of symlink targets overstates what was read, and a reader cannot tell one bad link from two. It blocks correctly, so this is noise, not a hole.
- NOT FIXED

### R-SC-02: a relative target that climbs into a home folder passes with only a NOTE
- Severity: major
- Worse than develop: no (develop read no target at all), but it misses the acceptance line "fails on a home or person path"
- What: the home-path rule `UNIX_PATH_RE` (check_public_leaks.py:445) requires that the character before `<home>` or `<home>` is not a word character, dot or hyphen. In a relative target that climbs out, the character before `<home>` is always the dot of `..`, so the rule never fires. `target_is_absolute` is false, so the only output is the NOTE. The person's name in the target is published.
- Reproduction: scratch repository, base at the first commit, then `ln -s "../../../..<home>/Desktop/notes/x.md" lk` committed. Output: `EXIT=0` and `NOTE symlink lk: its relative target leaves the repository; a person confirms it points to a public place (not a failure)`, no FAIL. Same result for `..//..//..//..//<home>//carol//x` and `./../../../..<home>/x`. Control: `<home>/...` as the target fails `[local-path]` and `[absolute-symlink]`.
- Why it matters: a relative link from a checkout inside a home folder to a sibling folder is the most likely way a symlink names a person, and it is exactly the shape the commit 0192e9d0 class of leak takes when the private folder sits under a home directory. The private-name check catches it only when the name is on the owner's private list, so a colleague's or another user's home folder passes. The NOTE asks a person to judge it, but the scan exits 0 and /ship gates on the exit code.
- NOT FIXED

### R-SC-03: a relative target that climbs out with backslashes gets no NOTE
- Severity: minor
- Worse than develop: no
- What: `target_leaves_repository` (check_public_leaks.py:1315) uses `posixpath` only, so `..\..\..\<home>\x` is judged to stay inside the repository and prints nothing, while `ABSOLUTE_TARGET_RE` treats a leading backslash as absolute. The two helpers disagree on whether a backslash is a separator.
- Reproduction: `ln -s '..\..\..\<home>\x' lk` committed. Output: `EXIT=0`, no FAIL and no NOTE line.
- Why it matters: on a Windows checkout git resolves such a link with backslash separators, so the target leaves the repository and names a home folder, and nothing tells the person to look.
- NOT FIXED

### R-SC-04: an absolute path inside a target that does not start with one passes silently
- Severity: unsure
- Worse than develop: no
- What: the absolute test is anchored at the first character only. A target whose text carries an absolute non-home path after a prefix (`file:///srv/private/x`, a leading space ` /srv/private/x`, or a first line `docs/a` followed by a newline and `/srv/private/x`) gets no FAIL and no NOTE, because by its text it neither is absolute nor climbs out. Home paths in the same shapes are caught by `[local-path]`.
- Reproduction: `ln -s "file:///srv/private/x" lk` committed: `EXIT=0`, no FAIL, no NOTE. `ln -s " /srv/private/x" lk`: `EXIT=0`, no FAIL, no NOTE.
- Why it matters: the target text, which GitHub shows, names a place on one machine. I am unsure whether the owner counts a non-home absolute path as private; the acceptance names "an absolute target", and these are not absolute targets to the filesystem, only to a reader.
- NOT FIXED

### R-SC-05: an untracked symlink's target is never read
- Severity: minor
- Worse than develop: no (develop skipped it the same way, `scan_untracked` at check_public_leaks.py:1258)
- What: the acceptance names "every symlink the working copy adds". An untracked symlink is read for its name only; its target goes through no rule and not through the private-name check. The builder's report says so under "What it still cannot do", but the commit message and SKILL.md bullet do not.
- Reproduction: scratch repository, `ln -s /srv/untracked/zorblax u`, not staged (`?? u`). Output: `EXIT=0`, `scanned 0 lines, 1 file names, 0 symlink target(s)`, `private-name check: PASS`, no FAIL.
- Why it matters: the scan reads every other untracked file whole, as the preview of what the next commit carries. A run that passes with an untracked private link in the tree tells the person the working copy is clean when it is not. The link is caught only if the scan is run again after it is committed.
- NOT FIXED

### R-SC-06: a link the push changes is labelled "already on the base, tell the owner"
- Severity: minor (sits inside this phase's new code, `on_base_note`, check_public_leaks.py about line 1560)
- Worse than develop: no, the push is still blocked; the label is wrong
- What: `on_base_note` decides "already on the base" with `_changed_paths`, which diffs the base against the working copy, not against the index or HEAD. When the working copy puts the link back to the base's target, the index line for a link the push does change says it is already public.
- Reproduction 1: base link `l -> README.md`; commit retargets to `/srv/bad/x`; then `ln -sfn README.md l` unstaged. Output: `FAIL commit 21e7052f symlink l (stored target) [absolute-symlink] /***(10 chars)` and `FAIL symlink l (stored target, tracked) [absolute-symlink] /***(10 chars) (already on the base: remove it here and tell the owner)`.
- Reproduction 2: base link `l -> README.md`; `ln -sfn /srv/st/x l; git add l; ln -sfn README.md l` (bad target staged only). Output, the only FAIL line: `FAIL symlink l (stored target, tracked) [absolute-symlink] /***(9 chars) (already on the base: remove it here and tell the owner)`.
- Why it matters: "already on the base, tell the owner" means "this is public and needs a history rewrite". Here nothing is public yet, and the right fix is to unstage or amend. A false alarm to the owner about a public leak costs a decision they do not need to make.
- NOT FIXED

### R-SC-02 addendum: a home folder after any word character also passes
- Same root cause as R-SC-02. A target `notes<home>/x`, which stays inside the repository by its text and so prints no NOTE either, gives `EXIT=0` with no FAIL and no NOTE. The person's name is published with no line at all.

### R-SC-07: the allow marker inside a symlink target exempts the target
- Severity: minor
- Worse than develop: no
- What: `scan_line` exempts every private-value category on a unit whose text contains `local-refs: allow`, and a symlink target is a unit. A target that carries the marker is exempt from the home-path rule. The marker is meant for a line of a file a person wrote and reviewed; nobody writes it into a link target deliberately except to get past the check.
- Reproduction: `ln -s " <home>/x local-refs: allow" lk` committed: `EXIT=0`, no FAIL. Control, the same without the marker: `FAIL commit ae8c4b5c symlink lk (stored target) [local-path] /***(12 chars)`, `EXIT=1`. Whether the owner's real private-name check also honours the marker in `--message` mode I could not verify, since that script is private; my stand-in ignores markers.
- Why it matters: one way through the new pass for a target that names a person, by a text edit to the link.
- NOT FIXED

### R-SC-08: the mask prints the target's first character and its length
- Severity: unsure
- Worse than develop: no (the house mask, `mask` at check_public_leaks.py:522, does this for every finding)
- What: an `[absolute-symlink]` FAIL line prints `mask(target)`, which is the first character and the length, for example `C***(15 chars)` for a drive-letter target and `~***(8 chars)` for a home-of-user target. The acceptance says the scan never prints the target. No run of two or more characters is printed: across 15 runs (five target shapes, each in a commit, staged and in the working copy) no four-character run of the target appeared in stdout or stderr, and stderr was empty each time.
- Reproduction: `ln -s "~<user>/zorblax" lk` committed: `FAIL commit 021ebab0 symlink lk (stored target) [absolute-symlink] ~***(8 chars)` (an eight-character variant of the probe).
- Why it matters: little; filed because the acceptance wording is absolute and the first character of an absolute target is the drive letter or root form.
- NOT FIXED

- Correction to the R-SC-08 reproduction: the line `~***(8 chars)` came from the target `~<user>/x` (commit 021ebab0), not from the qwertyuiop probe, which was used only for the run-of-characters check.

### R-SC-09: no test covers a target that starts with a backslash
- Severity: minor
- Worse than develop: no
- What: removing the `\\` alternative from `ABSOLUTE_TARGET_RE` (check_public_leaks.py:482) leaves every symlink test green. The four absolute shapes tested are a POSIX root, `~/`, and a drive letter with either slash.
- Reproduction: mutant mA, a copy of the script with `ABSOLUTE_TARGET_RE = re.compile(r"^(?:/|~|[A-Za-z]:)")`, run through `CHECK_PUBLIC_LEAKS_SCRIPT` with `-k "symlink or link"`: `17 passed`. My probe on the same mutant, `ln -s '\\zqserver\share\notes.md' lk` committed: the real script prints `FAIL commit a198c9f7 symlink lk (stored target) [absolute-symlink] \***(25 chars)` and exits 1; the mutant prints `PASS: nothing to publish looks like a secret or a private value.`
- Why it matters: a UNC share path, which names a machine on a network, can lose its guard in a later edit with nothing going red.
- NOT FIXED

### R-SC-10: the new `new mode` branch in `parse_patches` is dead and untested
- Severity: unsure
- Worse than develop: no
- What: git never writes `new mode 120000` in a patch; a type change is always split into `deleted file mode` and `new file mode`, with or without `-B`. Removing the `new mode` branch (check_public_leaks.py:1056 to 1059) leaves every symlink test green.
- Reproduction: regular file `f` replaced by `ln -s /srv/x f` and staged; `git diff --cached -U0 --no-renames HEAD | grep mode` prints `deleted file mode 100644` and `new file mode 120000`, the same with `-B`. Mutant mC without the branch: `17 passed`.
- Why it matters: not a hole; dead code that reads as a guarantee. Filed so a reader does not rely on it.
- NOT FIXED

### R-SC-11: the leak this change exists for passes on a machine without the private-name check
- Severity: unsure
- Worse than develop: no
- What: the 2026-10-17 symlink's stored target climbs out of the repository and has no `<home>/` or `<home>/` segment (checked by a script that printed only booleans: `climbs out: True | contains <home>/ or <home>/ segment: False`). On the commit before the cleaned guide, the new scan blocks it only through the owner's private-name check: `FAIL private-name check: symlink docs/Claude_security_plugin_usage.md (stored target, tracked) [owner-term] (already on the base: ...)`, exit 1; the old scan exits 0. The scan's own rules give only a NOTE. So on any machine run with `--allow-missing-private-check`, the exact incident passes with exit 0.
- Reproduction: detached worktree at 4bcc5efc; new script `--no-fetch`: two NOTE lines and the private-name FAIL above, exit 1. The pre-change script on the same tree: `private-name check: PASS`, exit 0.
- Why it matters: this follows the owner's narrowed decision (a relative link out is a NOTE), so I file it as unsure. It means the fix's guarantee for this class of leak holds only on the owner's machine, which the commit message does not say.
- NOT FIXED

## Checklist evidence

Every probe below ran in a fresh scratch repository with a `base` branch, `--base base --no-fetch`, and a stand-in `verify_no_local_refs.py` named on the pre-commit hook's exec line that flags the made-up term `zorblax` (control: a commit message with the term gives `FAIL private-name check: commit 0786b5f0 message:1 [owner-term]`, exit 1).

### 1. Correctness on real git shapes

| Shape | Result |
|---|---|
| Added in a commit, absolute target with the term | Exit 1, `[absolute-symlink]` and `[owner-term]`, each twice (R-SC-01) |
| Retargeted in a commit, inside to `/srv/...` | Exit 1, `FAIL commit a89d7c2e symlink l (stored target) [absolute-symlink]` |
| Deleted, absolute on the base | Exit 0, 0 symlink targets: correct, the push removes it |
| Added then deleted in outgoing commits | Exit 1, `FAIL commit 53bb2bc9 symlink l ...`, read once |
| Renamed, absolute on the base | Exit 1, read as a new link `l2` (the scan runs `--no-renames`) |
| Symlink to regular file, as 0192e9d0 did | Exit 0, the file's text read, 0 symlink targets; the base state alone fails with "already on the base" |
| And back, file to a link naming the term | Exit 1, `[owner-term]` |
| Added only inside a merge commit, then deleted | Exit 1, `FAIL commit bb017379 symlink el ...` from the remerge diff |
| Retargeted only inside a merge commit, then restored | Exit 1, the merge commit's line |
| Added on a side branch and merged | Exit 1 |
| Target with spaces in a home path | Exit 1, `[local-path]` and `[absolute-symlink]` |
| Target with a newline, home path on line two | Exit 1, `[local-path]` |
| Target with non-UTF-8 bytes and the term | Exit 1, `[absolute-symlink]` and `[owner-term]` |
| Target with a NUL byte (git shows "Binary files differ") | Exit 1, read from the blob |
| Nested link `a/b/c/deep -> ../../../../sibling/x` | NOTE; the in-repository sibling link is quiet |
| Unstaged retarget, staged retarget, staged new link | Exit 1 each, working tree read via `os.readlink` |
| `core.symlinks=false`, link checked out as a file and edited | Exit 1, read from the diff text fallback |
| Missing blob in the index | Exit 1, `TOO LARGE symlink ghost (stored target, tracked) (could not be read)` |
| 3 MB target, home path at the end | Exit 1, read whole |
| Untracked symlink | Not read (R-SC-05) |

Read exactly once: no, an outgoing link is read twice (R-SC-01).

### 2. Evasion

Caught: `file:///<home>/...`, `C:<home>/...`, `//server/share`, `~<user>/x`, a `$HOME` path under the desktop folder, `-<home>-x`, ` <home>/x`, `\\server\share` (25 chars, `[absolute-symlink]`). Not caught: R-SC-02 (`../../../..<home>/...`, `..//`, `./../`, `notes<home>/x`), R-SC-03 (backslash climb, no NOTE), R-SC-04 (absolute non-home text after a prefix), R-SC-07 (allow marker in the target). A gitlink (mode 160000) carries no target: exit 0, 0 symlink targets, correct.

### 3. Leaks in output

Five targets (a home path with the term, a relative climb, a drive path, `~<user>`, a `/srv` path), each in a commit, staged and in the working copy: 15 runs, every one exit 1, stderr 0 bytes each, and no four-character run of the target in stdout or stderr (the detector found runs when pointed at a string that is in the output). The first character and the length are printed (R-SC-08). An internal error prints only the exception's type name (`main`, unchanged).

### 4. Regression

- Full file on 67c9c40c: `251 passed in 188.88s (0:03:08)`.
- The pre-change test file (0192e9d0, 232 tests) run against the new script through `CHECK_PUBLIC_LEAKS_SCRIPT`: `232 passed in 181.12s (0:03:01)`.
- The scan against origin/develop from the scanfix worktree, new script, with fetch: exit 0, last lines `NOTE symlink reference/agentic-search-data-engineering: its relative target leaves the repository; ...`, `private-name check: PASS (it read every line, file name, message and symlink target this scan read, in 8 commit(s) ...)`, `scanned 1047 lines, 7 file names, 3 symlink target(s) and 8 commit(s) against origin/develop (merge base 4eab6dd6); 0 finding(s) ...`, `PASS: ...`. The pre-change script on the same tree: exit 0, `scanned 1047 lines, 7 file names and 8 commit(s)`. The two outputs differ only in the NOTE line and the symlink wording; the line count is the same.
- Diff of the script: edits are confined to `INDEX_RE`, `parse_patches`, `_add_patches`, `run_scan`, `_where`, `_main`'s output and the new functions. No other function changed. No file in the repository parses the summary line whose wording changed.
- The original incident: on 4bcc5efc the new script exits 1 with the private-name FAIL; the old exits 0 (R-SC-11).

### 5. Break it

Each mutant is a copy of the script run through `CHECK_PUBLIC_LEAKS_SCRIPT` against the 17 tests `-k "symlink or link"` selects; the real script was never edited, and `git status` of the review worktree and of scanfix was empty afterwards.

| Mutation | Builder's tests | My probe |
|---|---|---|
| mB: the working-tree branch of `_add_symlink_patch` returns at once | Red: `test_a_link_retargeted_after_the_base_is_read[working-copy]` failed, 1 failed, 16 passed | not needed |
| mD: `on_base_note` always returns "" | Red: 5 failed, every on-the-base case | not needed |
| mA: `ABSOLUTE_TARGET_RE` without the backslash | Green, 17 passed (R-SC-09) | Red: real script exit 1 `[absolute-symlink]`, mutant `PASS` |
| mC: the `new mode` branch removed | Green, 17 passed; the branch is dead (R-SC-10) | not applicable |

### 6. Gates

On a detached worktree at 67c9c40c: `ruff check` with no path, `All checks passed!`, exit 0 (ruff 0.16.0). `isort --check-only --diff src tests services tracker alembic .claude .github` as gate02 runs it: `Skipped 2 files`, exit 0 (isort 9.0.0).

## Verdict

FAIL against the acceptance. The change blocks every absolute target, every target the private-name check flags, and the original incident, and it changes nothing else the scan did. It misses one acceptance line: a relative target that names a person's home folder (`../../../../<home>/<name>/...`) passes with exit 0 and a NOTE (R-SC-02). Nothing found makes anything worse than develop.

R-SC-02, R-SC-03, R-SC-06 and R-SC-10 sit inside this change's own new code, which is the fix this round reviews; under the review loop that is the stop condition and goes to the product owner.

Verified with my own probes: every row of the checklist tables above, the live scan old and new, the incident before and after, the pre-change tests on the new script, all four mutants, both gates. Only read, not run: the owner's real private-name check's handling of the allow marker (R-SC-07), and the claim that /ship always reruns the scan after committing an untracked link (R-SC-05).

## Notes for the lead

- Correction to R-SC-08: the run check looked for four-character runs. Single characters are printed by design; two- and three-character runs were not measured.
- Committing this file: the scan's own rules flag two lines of it as `[local-path]` (line 19, the "Control" sentence in R-SC-02, and line 134, the "Caught" list in the evidence), because they quote made-up home-folder targets such as `<home>/...`. They name no real person or machine. Rewrite them or mark them before the push.
- The review's scratch repositories and worktrees were outside the repository; the detached worktrees were removed with `git worktree remove`.

