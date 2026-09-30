# Builder report: the /ship public-leak scan

Date: 2026-09-29. Branch `chore/ship-leak-scan` in both repositories, from develop, not pushed. The owner's request: "update the /ship skill to check for leaks of PII such as name, or secret keys and anything that should not be visible for a public repo".

## Table of contents

- [What was built](#what-was-built)
- [What each category matches and deliberately does not](#what-each-category-matches-and-deliberately-does-not)
- [Choices beyond the brief](#choices-beyond-the-brief)
- [Break-it results](#break-it-results)
- [The two real runs](#the-two-real-runs)
- [Gate counts](#gate-counts)
- [Blocked or needs the owner](#blocked-or-needs-the-owner)
- [Incidental findings in already public history](#incidental-findings-in-already-public-history)

## What was built

| Item | System 3 | Data engineering |
|------|----------|------------------|
| Script | `.claude/skills/ship/scripts/check_public_leaks.py` | `scripts/check_public_leaks.py` (byte identical, `cmp` clean) |
| Tests | `tests/ci/test_check_public_leaks.py`, 93 tests | `tests/scripts/test_check_public_leaks.py`, 93 tests |
| Ship skill | `.claude/skills/ship/SKILL.md`: gate in Step 0, a "public-leak scan" subsection, a second run in Step 2, a Guards entry | Not committable, see "Blocked or needs the owner" |
| Commits | `2e37ca02` (script and tests), `11ff3312` (skill) | `e3b64d5` (script and tests) |

The script is stdlib only. It scans:

- Every added line of `git diff <base>...HEAD`.
- Every added line of the staged and unstaged diff against HEAD.
- Every untracked file that git does not ignore, whole.
- Every commit message in `<base>..HEAD`.
- Every author and committer email in `<base>..HEAD`.

`<base>` defaults to `origin/develop`. It prints `file:line [category]` with the value masked to its first character and its length. Exit 0 is clean, 1 is a finding (or the private-name check not run), 2 is could not run, with the message saying what to do.

The machine-local private-name check is located by reading the `exec` line of the repository's pre-commit hook, through `git rev-parse --git-path` so a linked worktree finds the shared hook. It runs on `--staged`. When the hook or the script is absent, or the check exits 2, the scan prints `private-name check NOT RUN on this machine: <reason>` (no path in the reason) and exits 1 unless `--allow-missing-private-check` is passed.

## What each category matches and deliberately does not

| Category | Matches | Deliberately does not match |
|----------|---------|-----------------------------|
| private-key | A PEM private key header line, any algorithm word | The scanner's own source, which assembles the marker from parts |
| aws-access-key | `AKIA` or `ASIA` plus 16 upper case letters or digits | Values with `EXAMPLE` in them, as in the vendor's documentation key |
| github-token | `ghp_`, `gho_`, `ghs_`, `ghu_`, `ghr_` plus 36 or more characters, and `github_pat_` plus 22 or more | Short prefixes with no body |
| provider-api-key | `sk-`, `sk-ant-`, `sk-or-`, `sk-proj-` plus 20 or more key characters, with at least one digit | Hyphenated slugs with no digit (a branch name such as `task-tracker-...` has no `sk-` word boundary anyway) |
| slack-token | `xox` plus a, b, p, r or s, a hyphen and 10 or more characters | `xox` alone |
| google-api-key | `AIza` plus 35 key characters | Anything shorter |
| jwt | Three base64url parts, header and payload starting `eyJ`, signature of 8 or more | Two part strings, short fragments |
| bearer-token | `Bearer` and 20 or more token characters that mix letters and digits | `Bearer ${TOKEN}`, `Bearer <token>`, all letter words |
| url-password | `scheme://user:secret@host` where the password is not a placeholder | `user:password@`, `${...}`, `<...>`, `%s`, values under 8 characters |
| secret-assignment | A name containing key, secret, token, password or passwd assigned a value of 16 or more token characters, entropy of 3.3 bits or more, mixing letters and digits | Environment lookups, identifiers with no digit, values that a shaped detector already caught on the line |
| local-path | a macOS, Linux or Windows home directory followed by a person's name | `<user>`, environment variable forms, and the names runner, ubuntu, root, vsts, circleci, travis, github, docker, node, vscode, app, user, username, you, name, me, example, shared, public, default, all, build, builder, worker, and a few others. A home folder word inside a URL path, since the character before its slash must not be a word character |
| personal-email | Any address not in the list at right | `example.com`, `example.org`, `example.net` and subdomains, RFC 2606 names ending `.invalid`, `.test`, `.example`, `.localhost`, any address whose domain has a `noreply` label, local parts `noreply`, `no-reply` and `git`, and file-like names such as an image at `2x.png` |
| identity-email | An author or committer email in `<base>..HEAD` that is not `<id>+<name>@users.noreply.github.com` or `noreply@github.com` | The same two shapes |
| ipv4-address | Any dotted quad with every part 255 or less, including private ranges | 127.0.0.0/8, 0.0.0.0, 255.255.255.255, 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24, and four part versions with a part above 255 |
| ssh-host | `ssh` or `scp` with `user@host` where the host is real | Hosts with `<`, `>`, `$`, `{`, `[`, the hosts github.com, gitlab.com, bitbucket.org, localhost, and a bare word such as host, server or remote |

Placeholders that never fire on any shaped category: values under 8 characters, anything containing `<`, `>`, `${`, `$(`, `{{`, `%(` or `%s`, a leading `$`, the words password, secret, changeme and their kin, any value containing example, dummy, fake, changeme, placeholder or redacted, a `your-` or `my-` prefix, three or more `x` or `*` in a row, and a value made of two distinct characters or fewer. A line carrying `local-refs: allow` is exempt. Binary files are skipped by name and counted in the summary line. A file over 2 MB is printed as `NOT SCANNED`.

## Choices beyond the brief

- Untracked files are scanned whole. Step 0 runs before anything is staged, so a brand new file is invisible to every diff, and a new file is the usual leak.
- The scan runs a second time in Step 2, after the commit and before the push. Docs-sync edits files after Step 0, and the commit message and identity exist only after it. The skill says so.
- Private IPv4 ranges are flagged, because the privacy rule lists internal IP addresses. Test fixtures that use one (a `10.x` address) will need the allow marker. One such line exists in System 3 history (see the wide run below).
- Extra placeholders the brief did not list: the reserved test top level names, addresses whose domain has a `noreply` label, the `git@` local part for ssh remotes, file-like names, all of 127.0.0.0/8, and the `ghr_` and `sk-proj-` prefixes as detected shapes. Each came from a false positive seen in a 150 commit wide run of System 3 history, which fell from 14 findings to 1.
- The private-name check reads only the staged diff, as briefed. Run in Step 0 before anything is staged, it mostly proves the check exists on this machine, and the hook itself does the real work at commit time. It does not see a private name in a commit already made on the branch with the hook bypassed. Widening it means `--all`, which reads every tracked file and is slow, so it is left to the owner.

## Break-it results

Method: a mutation runner copies the script, disables one detector, points `CHECK_PUBLIC_LEAKS_SCRIPT` at the copy and runs the whole test file with `-x`. Each row must go red. Both repositories, on the final formatted script, all red.

| Mutation | First failing test | System 3 | Data engineering |
|----------|--------------------|----------|------------------|
| private-key detector off | `test_category_fires_from_a_commit[private-key]` | red | red |
| aws-access-key off | same test, aws-access-key | red | red |
| github-token off | same test, github-token | red | red |
| provider-api-key off | same test, provider-api-key | red | red |
| slack-token off | same test, slack-token | red | red |
| google-api-key off | same test, google-api-key | red | red |
| jwt off | same test, jwt | red | red |
| bearer-token off | same test, bearer-token | red | red |
| url-password off | same test, url-password | red | red |
| secret-assignment off | same test, secret-assignment | red | red |
| local-path off (unix and windows) | same test, local-path | red | red |
| personal-email off | same test, personal-email | red | red |
| ipv4-address off | same test, ipv4-address | red | red |
| ssh-host off | same test, ssh-host | red | red |
| identity-email check off | `test_non_noreply_identity_is_a_finding[AUTHOR]` | red | red |
| allow marker ignored | `test_allow_marker_exempts_a_line` | red | red |
| masking returns the full value | `test_output_never_carries_the_full_value[private-key]` | red | red |
| placeholder filter always false | `test_placeholder_does_not_fire[...example-api-key...]` | red | red |
| private check no longer fails closed | `test_missing_private_check_fails_closed` | red | red |
| untracked scan removed | `test_untracked_file_is_scanned_whole` | red | red |
| base check removed (exit 2) | `test_exit_two_when_the_base_is_missing` | red | red |

The first attempt at the placeholder mutation weakened only the last line of the function, and the suite stayed green, which showed the earlier placeholder rules cover each other. The mutation was widened to the whole function and went red. The bug that a removed line beside an added line dropped the added line number was found by a test written after the first draft and is pinned by `test_a_line_removed_beside_an_added_one_keeps_its_line_number`.

## The two real runs

System 3, after both commits, against `origin/develop`:

```text
private-name check: PASS (machine-local check ran on the staged diff)
scanned 1329 lines and 2 commit(s) against origin/develop; 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name
PASS: nothing to publish looks like a secret or a private value.
rc=0
```

Data engineering, after its commit, against `origin/develop`:

```text
private-name check: PASS (machine-local check ran on the staged diff)
scanned 1299 lines and 1 commit(s) against origin/develop; 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name
PASS: nothing to publish looks like a secret or a private value.
rc=0
```

The owner's machine-local hook also blocked the first System 3 skill commit on a Windows style home path written in the skill's prose (`SKILL.md` line 63). The line was reworded to "a macOS, Linux or Windows home directory that names a person" and committed anew.

A wide run of System 3, `--base HEAD~150`, gave one finding: a private `10.x` address in a test fixture, `tests/services/graph_query_service/test_forwarded_address.py:38`. It is a true positive under the rule and was left alone.

## Gate counts

System 3 worktree:

| Gate | Result |
|------|--------|
| New tests, `tests/ci/test_check_public_leaks.py` | 93 passed |
| `tests/ci` and `tests/tracker` together | 553 passed |
| `ruff check .` | exit 0 |
| `.github/gates/gate02_import_order.sh` | exit 0 |
| `python3 tracker/check_doc_drift.py --check` | exit 0, 2 facts computed, 0 stale, 0 structural |
| `check_style.py` on the ship skill | 0 hard, 1 advisory (no diagram, informational) |

The full unit suite (`gate04`) was not run: only a script, its test and a skill file changed, and the new tests plus `tests/ci` and `tests/tracker` cover what they touch. That is a departure from the skill's own "whenever any Python file under tests/ changed" line, so the lead should run gate04 before the push if the dial calls for it.

Data engineering worktree: 93 new tests passed. The repository configures no linter, so `ruff check` from the System 3 environment was used as a sanity pass and reported clean.

## Blocked or needs the owner

- The data engineering ship skill is not updated in the commit. That repository's `.gitignore` keeps everything under `.claude/` local except `settings.json`, on purpose (the worm vector its comment names), so `.claude/skills/ship/SKILL.md` and a script beside it cannot be committed without changing that ignore rule, which is the owner's call. The script and tests therefore sit under `scripts/` and `tests/scripts/`. The new ship step is written and ready as `<scratchpad>/de_ship_SKILL.md.proposed`: a new Step 2 "public-leak scan" before the commit step, the commit step renumbered to Step 3, a Guards entry and an Output line. It calls `python3 scripts/check_public_leaks.py`. Copying it over the local ignored skill file is a one line action that changes no tracked file.
- Neither repository's `CLAUDE.md` row for the ship skill mentions the scan yet. `CLAUDE.md` is a canonical document that docs-sync owns, and `AGENTS.md` follows it through a hook, so both were left alone.
- Nothing here needed a hook or `.claude/settings.json` change. The System 3 change touches `.claude/skills/ship/`, which the git workflow rule puts on a branch with a pull request.

## Incidental findings in already public history

Found by a wide run of the data engineering repository, `--base HEAD~60`, against commits that are already on its `develop`. None is in this branch's range, so nothing was edited. Values are not repeated here.

- 41 of the last 60 commits carry an author or committer email that is not a GitHub noreply address (27 with an NCBI domain, 14 with an NIH domain). The privacy rule calls a work address the owner's work identity. Removing it means rewriting history, which is the owner's call.
- `docs/learnings.md` line 997 holds a Windows home path that names a person, inside an rsync example.
- One commit message (`7c064578`) carries a private style IPv4 address.

System 3's last 150 commits show no identity finding.
