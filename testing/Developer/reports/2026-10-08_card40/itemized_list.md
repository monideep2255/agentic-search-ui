# Card 40: itemized hook and rule changes

You decide each of the 27 items below with its own yes or no, because a broad go-ahead is not consent for the security layer (DECISIONS.md, 2026-10-06, "Card 40").
Nothing has been changed: no hook, setting, deny rule or rule file was edited to write this list. Checked against develop at c916cfa3 on 2026-10-08.

## Table of contents

- [In one minute](#in-one-minute)
- [Hook changes](#hook-changes)
- [Settings and permission changes](#settings-and-permission-changes)
- [Deny rule change](#deny-rule-change)
- [Always-loaded rule changes](#always-loaded-rule-changes)
- [Already done, no answer needed](#already-done-no-answer-needed)

## In one minute

| Kind | Items | Lead recommends yes | Lead recommends no |
|---|---|---|---|
| Hook (the Bash guards, the session hooks, the sync hook, the push leak scan) | 20 (items 1 to 20) | 9 | 11 |
| Settings or permission (allow list, local settings) | 4 (items 21 to 24) | 4 | 0 |
| Deny rule | 1 (item 25) | 1 | 0 |
| Always-loaded rule | 2 (items 26 and 27) | 2 | 0 |
| Total | 27 | 16 | 11 |

- Yes items are small, cheap to test, and either close a gap an agent could plausibly hit or stop a harmless command being blocked.
- No items are gaps the earlier reviews named as rare or as not closable by pattern matching, or that the agent tool already asks about before running.
- Items 1 and 2 were approved on 2026-09-26 but a safety system stopped the builder writing them. Neither the lead nor another agent retries them in other words (DECISIONS.md, 2026-09-26). Your yes would need you to write or paste the pattern.
- Items 3 to 20 and 21 to 25 are from the build harness review's residual lists, the later checkers' named open gaps, or the lead's check of develop for this list. Each says which.
- The git-workflow line you asked for is item 26.

How to read an item: the lead probed the current hooks on develop with harmless test strings. Where an item says "allowed today", the probe printed allow for that string.

## Hook changes

### 1. Delete guard: flag forms of a shell or interpreter

- File: `.claude/hooks/block-bash-delete.sh`, with its tests in `tests/ci/test_claude_hooks.py`.
- Change: scan `bash -ec "..."`, `bash --norc -c "..."`, `python3.12 -c`, `python3 -I -c`, `node --eval` and `$(which rm)` like `bash -c`.
- Why: DECISIONS.md, 2026-09-26, "Two more guard gaps are closed, item by item" (you picked it), then 2026-09-26, "The two guard gaps approved earlier today ... stay open and named". Probe on develop: `bash -ec` with an rm inside is allowed today.
- Gain: the guard sees the flag forms an agent could plausibly write.
- Cost or risk: the builder was stopped by a safety system when writing it. A retry in other words is the same content, so the pattern has to come from you. More patterns raise the chance of false blocks.
- Lead's recommendation: no. Keep it a named known gap. The delete guard still catches the common forms, and the settings deny rule `Bash(rm:*)` still stops a plain delete command.
- Your answer: yes / no

### 2. Delete guard: a quoted command name

- File: `.claude/hooks/block-bash-delete.sh`, with its tests.
- Change: scan `"bash" -c "..."` and `"ssh" host "..."` like the unquoted forms.
- Why: same two 2026-09-26 rows as item 1. Probe: `"bash" -c` with an rm inside is allowed today.
- Gain: closes a shape an agent could write by accident.
- Cost or risk: same stop as item 1, so you would write the pattern. Quote handling in a text-matching hook is where false blocks come from.
- Lead's recommendation: no. Keep it a named known gap.
- Your answer: yes / no

### 3. Delete guard: the `command` and `builtin` prefix

- File: `.claude/hooks/block-bash-delete.sh`, with its tests.
- Change: add `command` and `builtin` to the runner words the guard already looks past (it does this for `sudo`, `env`, `exec`, `nice`, `nohup`, `time`, `timeout`, `xargs`).
- Why: build harness review builder H3, "Destructive commands neither version catches", and `production-examples.md`, example 5, which names `command rm`. Probe: `command rm -rf x` and `builtin command rm -rf x` are allowed today, and the settings deny rule `Bash(rm:*)` does not match them either.
- Gain: one more way past the guard is shut with a two-word edit.
- Cost or risk: very low. The word `command` is rarely used as a command prefix in this repository.
- Lead's recommendation: yes.
- Your answer: yes / no

### 4. Delete guard: an environment assignment before the command word

- File: `.claude/hooks/block-bash-delete.sh`, with its tests.
- Change: treat leading `NAME=value` words (such as `LANG=C`) as skippable before the command word, so `LANG=C rm -rf x` reads as `rm -rf x`.
- Why: `production-examples.md`, example 5, "What the hook does not see". Probe: `LANG=C rm -rf x` is allowed today, and the deny rule `Bash(rm:*)` does not match it.
- Gain: closes a shape that real scripts use.
- Cost or risk: low. An assignment is a plain word pattern.
- Lead's recommendation: yes.
- Your answer: yes / no

### 5. Delete guard: `env` given as a full path

- File: `.claude/hooks/block-bash-delete.sh`, with its tests.
- Change: read `/usr/bin/env rm -rf x` like `env rm -rf x`, which the guard already blocks.
- Why: `production-examples.md`, example 5, which names `/usr/bin/env rm`. Probe: allowed today.
- Gain: one more way past the guard is shut.
- Cost or risk: low. The command word may already be matched as a path (the guard reads `/bin/rm`); the edit is to do the same for the runner.
- Lead's recommendation: yes.
- Your answer: yes / no

### 6. Delete guard: block a forced push

- File: `.claude/hooks/block-bash-delete.sh` (or a new small hook beside it), with tests.
- Change: block `git push` carrying `--force`, `-f`, `--force-with-lease` or a `+ref`, anywhere in the command.
- Why: found while checking this list, not in the reviews. `.claude/rules/git-workflow.md` says "Never `git push --force`", but only the model obeys it. The allow rule `Bash(git:*)` lets `git push origin develop --force` run unprompted, and the probe prints allow for it. The file-protection rule's own aim is to enforce by structure what the model is told. Branch rulesets on GitHub may also stop it; the lead did not verify that.
- Gain: the one git rule marked "never" becomes structural.
- Cost or risk: a legitimate forced push (your own history rewrite) needs you to run it by hand. The hook text must read the whole command, because a prefix rule cannot see a flag at the end.
- Lead's recommendation: yes.
- Your answer: yes / no

### 7. Delete guard: stop blocking `--rm` as a flag inside a wrapper

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: inside a wrapper, `rm` that follows a hyphen (as in `docker run --rm`) is a flag, not a command word.
- Why: build harness review builder H3, "Harmless commands both versions still block". Probe: `ssh host "docker run --rm alpine echo hi"` is blocked today.
- Gain: fewer false blocks, so fewer commands moved into script files where the hooks cannot see them (build harness review, finding 6).
- Cost or risk: a command such as `ssh host "git rm --force x"` stays blocked by the word check; the edit only excuses a hyphen directly before `rm`. Low.
- Lead's recommendation: yes.
- Your answer: yes / no

### 8. Delete guard: a pipe character inside quotes just before rm

- File: `.claude/hooks/block-bash-delete.sh`.
- Change: tell a quoted `|` from a real pipe, so `grep -E "a|rm-b" f` is allowed.
- Why: builder H3, "Harmless commands both versions still block". Probe: blocked today.
- Gain: one less false block.
- Cost or risk: it needs a shell parser, which the hook does not have. A half fix could open a real gap. The workaround is easy (use two searches).
- Lead's recommendation: no.
- Your answer: yes / no

### 9. Delete guard: `find ... -delete`

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: block `find` with `-delete`.
- Why: builder H3, "Destructive commands neither version catches". Probe: allowed by the hook today.
- Gain: a deletion that never names rm is seen.
- Cost or risk: `find` is not on the allow list in `.claude/settings.json`, so the agent tool already asks you before running it. The hook would add a second block on a command you are already asked about.
- Lead's recommendation: no.
- Your answer: yes / no

### 10. Delete guard: `shred`

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: block `shred` as a command word.
- Why: builder H3, same list. Probe: allowed by the hook today.
- Gain: a deletion that never names rm is seen.
- Cost or risk: `shred` is not on the allow list, so you are already asked. Nobody in this repository has a use for it.
- Lead's recommendation: no.
- Your answer: yes / no

### 11. Delete guard: `unlink`

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: block `unlink` as a command word.
- Why: builder H3, same list. Probe: allowed by the hook today.
- Gain: a deletion that never names rm is seen.
- Cost or risk: not on the allow list, so you are already asked.
- Lead's recommendation: no.
- Your answer: yes / no

### 12. Delete guard: a disk write by `tee` or `cp`

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: block `tee` and `cp` whose target is a disk device (`/dev/sda`, `/dev/disk2`).
- Why: builder H3, "Destructive commands neither version catches". Probe: `cp img /dev/disk2` is allowed today.
- Gain: closes the last disk-write shape.
- Cost or risk: writing a disk device needs root, and `Bash(sudo:*)` is denied, so the write fails anyway on this machine. `cp` is on the allow list, which is why this is not zero.
- Lead's recommendation: no.
- Your answer: yes / no

### 13. Delete guard: a redirect before the command word

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: read `>out.txt rm -rf x` as `rm -rf x`.
- Why: builder H3, same list. Probe: allowed today.
- Gain: one more odd shape is shut.
- Cost or risk: nobody writes commands this way by accident. More patterns raise the false block count.
- Lead's recommendation: no.
- Your answer: yes / no

### 14. Delete guard: a here-document or pipe into python or node

- File: `.claude/hooks/block-bash-delete.sh`.
- Change: scan the body of `python3 - <<'EOF' ... EOF` and `cat file | python3` for deletion calls such as `shutil.rmtree`.
- Why: builder H3, "Destructive commands neither version catches", and DECISIONS.md, 2026-09-26: "pipes into python or node stay named open, since pattern matching cannot close them reliably". Probe: allowed today.
- Gain: the last common interpreter route is read.
- Cost or risk: this is how the lead and builders run real scripts, so a text match would block a lot of harmless work.
- Lead's recommendation: no.
- Your answer: yes / no

### 15. Delete guard: a wrapper outside the list, such as `osascript -e`

- File: `.claude/hooks/block-bash-delete.sh`, with tests.
- Change: add `osascript -e` and similar to the execution wrapper list.
- Why: `production-examples.md`, example 5, "What the hook does not see". Probe: allowed by the hook today.
- Gain: one more wrapper is read.
- Cost or risk: `osascript` is not on the allow list, so you are already asked.
- Lead's recommendation: no.
- Your answer: yes / no

### 16. Secret scan: `git -C dir grep` and `git --no-pager grep` count as a search

- File: `.claude/hooks/scan-secrets.sh`, with tests.
- Change: skip the field check when `git` is followed by its own options and then `grep`, as it already does for `git grep`.
- Why: builder H3, "Harmless commands both versions still block". Probe: `git -C d grep -n "api_key=settings" src/` is blocked today, while `grep -rn` on the same text is allowed.
- Gain: one less false block. The token-prefix check still runs on these commands, so a real key in a search string is still caught.
- Cost or risk: low. The change only widens which commands count as searches.
- Lead's recommendation: yes.
- Your answer: yes / no

### 17. Session hook: also scan `docs/rules/` for prompt injection

- File: `.claude/hooks/scan-context-injection.sh`.
- Change: add one loop over `docs/rules/*.md`, the way the hook already scans `.claude/rules-reference/*.md`.
- Why: build harness review builder H4, "Left open for the lead". The sandbox rule moved to `docs/rules/Sandbox_diagnosis.md` and is read on demand, but no session scan covers it.
- Gain: every file the agent is told to read as a rule gets the same injection scan.
- Cost or risk: a few lines at session start; the scan fails safe (it warns).
- Lead's recommendation: yes.
- Your answer: yes / no

### 18. Sync hook: work out the root from the script, not the project variable

- File: `.claude/hooks/sync-agents-md.sh` (line 23 reads `CLAUDE_PROJECT_DIR` first).
- Change: when the edited `CLAUDE.md` is inside a worktree, regenerate that worktree's `AGENTS.md`, not the main checkout's.
- Why: build harness review builder H1, "Facts found on the way": the hook does not sync a worktree, so a worktree's `AGENTS.md` goes stale. Builders now run in lead-made worktrees.
- Gain: `AGENTS.md` follows `CLAUDE.md` in every checkout, and no one syncs it by hand.
- Cost or risk: a PostToolUse hook that writes a file. A wrong root could write the main checkout from a worktree edit, so the change needs a test that edits a worktree and checks the main file is untouched.
- Lead's recommendation: yes.
- Your answer: yes / no

### 19. Leak scan: a personal email is a warning, not a block

- File: `.claude/skills/ship/scripts/check_public_leaks.py` (category `personal-email`), its tests in `tests/ci/test_check_public_leaks.py`, and the matching line in `.claude/skills/ship/SKILL.md`.
- Change: a `personal-email` finding prints WARN and does not stop the push. Secrets, local paths, addresses and the `identity-email` category (a non-noreply author or committer email) keep blocking.
- Why: DECISIONS.md, 2026-09-30, "Email findings were to become warnings only": your words, "if it's an email address, I don't mind that much". The permission layer refused the edit as a weakened check, so emails still block. The script on develop still lists `personal-email` as a blocking category.
- Gain: a push is no longer stopped by an address that is not a secret.
- Cost or risk: a third party's email could be published with only a warning, against `public-repository-privacy.md` ("Personal data: data about anyone"). The rule text would need one clause to match; that clause is not part of this item.
- Lead's recommendation: yes. It is your standing word, and the work identity stays blocked by the private-name check and `identity-email`.
- Your answer: yes / no

### 20. Session hook: print a line when extra branches or tags exist

- File: `.claude/hooks/session-start.sh`.
- Change: after the working tree list, print the count of local branches other than `develop`, with the names, so clutter shows at the next session start.
- Why: DECISIONS.md, 2026-10-08, "The end state ... is checked at the end of every session in both repositories": you asked to "make this a rule or somehow remember". A hook can remind; it cannot run at the end of a session.
- Gain: a stray branch is seen at once, in this repository.
- Cost or risk: many branches are legitimate right now (Factory worktrees, open pull requests), so the line would be noise on most days. It covers only this repository.
- Lead's recommendation: no. Item 26 is the rule; the reminder can wait until the noise is lower.
- Your answer: yes / no

## Settings and permission changes

### 21. Remove the System 1 module allow rule

- File: `.claude/settings.json`, `permissions.allow`.
- Change: delete `Bash(python -m system_01_data_pipelines:*)`.
- Why: `.claude/rules/file-protection.md` says this repository is System 3 only. A search of the repository finds that module named only in `.claude/settings.json`; `src/` holds `system_03_search_agent` alone. Found while checking this list.
- Gain: the allow list matches the repository, and an unknown module cannot run unprompted under that prefix.
- Cost or risk: none, because nothing runs it.
- Lead's recommendation: yes.
- Your answer: yes / no

### 22. Remove the `linkml` allow rule

- File: `.claude/settings.json`, `permissions.allow`.
- Change: delete `Bash(linkml:*)`.
- Why: the same file-protection rule. No code in the repository runs `linkml`; it appears only in notes and checker scripts as a word.
- Gain: the same as item 21.
- Cost or risk: none unless you plan to run it here.
- Lead's recommendation: yes.
- Your answer: yes / no

### 23. Narrow the `pip` allow rule to read-only commands

- File: `.claude/settings.json`, `permissions.allow`.
- Change: replace `Bash(pip:*)` with `Bash(pip list:*)`, `Bash(pip show:*)` and `Bash(pip --version)`, so `pip install` asks you first.
- Why: found while checking this list. CLAUDE.md says to read `.claude/rules/supply-chain-security.md` before any `pip install`, and its own note says a path cannot trigger that rule for a shell command. An allow rule that runs `pip install` with no question skips the only point where you could see it.
- Gain: every new package passes a human, which is what the supply-chain rule is for.
- Cost or risk: a builder installing from `requirements.txt` in a fresh worktree is asked once per run, and overnight runs stall at the prompt. `Bash(pip install -r requirements.txt)` could be allowed by itself, but that is a second change.
- Lead's recommendation: yes.
- Your answer: yes / no

### 24. Remove `Bash(pip install:*)` from the local settings file

- File: `.claude/settings.local.json` (gitignored, on your machine only).
- Change: delete the `Bash(pip install:*)` allow entry.
- Why: found while checking this list. Even with item 23 done, this local entry would still let `pip install` run unprompted on your machine. The same file also holds `Bash(brew install:*)` and `Bash(docker run:*)`, which this item leaves alone.
- Gain: item 23 holds on your machine.
- Cost or risk: the same stall as item 23. The file is not committed, so the change is yours to make.
- Lead's recommendation: yes.
- Your answer: yes / no

## Deny rule change

### 25. Deny `git clean`

- File: `.claude/settings.json`, `permissions.deny`.
- Change: add `Bash(git clean:*)`.
- Why: builder H3 lists `git clean -fdx` among the deletions the guard misses. Probe: the hook allows it, and `Bash(git:*)` in the allow list lets it run with no question, so it can delete every untracked file, including work not yet committed. A deny rule works here because the command word is the prefix.
- Gain: the one unprompted deletion left in the allow list is shut.
- Cost or risk: a legitimate clean (removing build output) needs you to run it. `git clean -n` (a dry run) would be denied too.
- Lead's recommendation: yes.
- Your answer: yes / no

## Always-loaded rule changes

### 26. Git workflow: the end state is checked at every session end, tags counting, in both repositories

- File: `.claude/rules/git-workflow.md`, in the "Steady state" paragraph.
- Change: add one sentence. Proposed text: "Check this end state at the end of every session, in both repositories (this one and the data engineering repository): locally `develop` and nothing else; on GitHub `develop`, `production` and the release tags, and nothing else. Tags count: a tag that is not a release tag is clutter."
- Why: DECISIONS.md, 2026-10-08, "The end state ... is checked at the end of every session in both repositories". The rule today names branches only. The same row says the line "waits for the owner's yes with card 40's always-loaded rule changes".
- Gain: every agent that loads the rule checks the same end state, including tags, in the same two places. Memory and the overnight skill cover the lead only.
- Cost or risk: about 60 words in an always-loaded file (the standing-context budget in `docs/Context_budget.md` has a recorded ceiling, and the lead would check the figure before and after). The long text in `.claude/rules-reference/git-workflow.md` would get the same sentence under this yes; that file is not security layer.
- Lead's recommendation: yes.
- Your answer: yes / no

### 27. Communication style: one exception for independent decisions

- File: `.claude/rules/communication-style.md`, first bullet.
- Change: after "Ask ONE question at a time. Never batch.", add "Exception: independent owner decisions may share one question-tool call, each its own question (`decision-cadence`, point 5)."
- Why: found while checking this list. Two always-loaded rules disagree. `communication-style.md` says never batch; `decision-cadence.md` point 5 says several independent decisions may share one call. Builder H2 flagged the same tension for the older daily list.
- Gain: an agent reading both stops guessing which wins, and a list like this one is not read as a breach.
- Cost or risk: it touches your communication rule. A wrong reading could let an agent batch questions that depend on each other, so the exception names "independent".
- Lead's recommendation: yes.
- Your answer: yes / no

## Already done, no answer needed

The lead checked each of these against develop. None needs a yes or no.

| What the reviews or decisions proposed | Evidence it is done |
|---|---|
| Delete guard matches rm and rmdir as whole words and drops a redirect to /dev/null (review item S2, DECISIONS 2026-09-25 item 1) | Commit 12dce317; probe: `python3 -c "print(1)" 2>/dev/null` is allowed, `rm -rf build/` is blocked |
| Secret scan skips a command led by grep, rg or git grep (S2, item 2) | Commit 12dce317; probe: `grep -rn "api_key=settings" src/` is allowed |
| Lead-only rules load only in the lead's session, one-situation rules move out (S1, item 3) | Commits f34fb61c and b38c1fd2; `.claude/README.md`, "Rules", lists eight always-loaded rules and the path globs |
| Board sync hook removed from settings (D3, item 4) | Commit adfd7dde; `.claude/settings.json` has no `sync-board.sh` entry; the script's header says it is not wired |
| Hook gaps: upper-case command word, pipe into a shell, here-string and here-document shapes, input redirect, quoted or bracketed shell before `<<<` (DECISIONS 2026-09-26 rows) | Commits ab83ce7f, 02cf4f56, 29e3e21c; header of `block-bash-delete.sh` |
| Secret scan misses a key with a hyphen after `sk-`, in Bash and in file writes | Commits 1673c4f2 and 8831d72d |
| Secret scan slows on a very long command (finding F02) | Commit aea2c52f |
| Secret scan residual: a field assignment after a grep-led chain (builder H3) | Probe: `grep -q x f; export API_KEY=<value>` is blocked today; the hook header says a chain is split into commands |
| Bossman-mode Deny entry on pushing to develop bounded by the risk dial (DECISIONS 2026-09-26, rule edit 1) | Commit 608dbb80; `.claude/rules-reference/bossman-mode.md` lines 76 to 80 |
| Seven-day close for wording and layout cards written into the loop (rule edit 2) | Commit f70620ef; `.claude/skills/bossman-mode/reference/UI_fix_loop.md` step 8 |
| `production-standards.md` no longer sends the grounding gate to the parked grader | Commit fe0bdc6a; the rule names the golden consistency run |
| `production-examples.md` example 5 says the guard does not look inside quotes | Corrected: the text now describes what the hook reads and what it does not |
| Two plugins and the docs connector switched off for this repository | `.claude/settings.json` (`enabledPlugins`, `deniedMcpServers`); DECISIONS 2026-10-04 |
| The sandbox rule moved to `docs/rules/` | Commit f34fb61c; `docs/rules/Sandbox_diagnosis.md` exists |
| Rules cut to short summaries with the full text on demand | Commit b38c1fd2; `.claude/rules-reference/` |

Left out on purpose: skill and process changes (the cadence documents, the worker brief template lines S7 to S9, the golden run's second number A3). They are not hook, settings, deny or always-loaded rule changes, so card 40's itemized yes does not cover them.
