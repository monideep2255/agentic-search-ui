# Factory review loop, build

Paused on 2026-10-16 before review; the code is saved beside this file as `paused_build.patch`. See `docs/build/Factory_review_loop.md` for what remains.

The build of the Factory review loop the product owner approved item by item on 2026-10-16 (`DECISIONS.md`, "The Factory review loop is approved item by item"), on branch `chore/factory-review-loop`. Built by a builder agent on 2026-10-16, staged and not committed. Nothing is installed and no live command ran.

## Table of contents

- [What was built](#what-was-built)
- [Each approval and where the code enforces it](#each-approval-and-where-the-code-enforces-it)
- [Choices the lead should log](#choices-the-lead-should-log)
- [Tests and mutations](#tests-and-mutations)
- [Gates](#gates)
- [What could not be done](#what-could-not-be-done)

## What was built

| File | What it is |
|---|---|
| `.claude/skills/factory-loop/factory_loop.py` | The hourly orchestrator, standard library only, one action per run, `--dry-run`, an injectable command runner |
| `.claude/skills/factory-loop/SKILL.md` | The procedure the unattended review follows for one pull request, ending in one `FACTORY_LOOP_VERDICT` line |
| `.claude/skills/factory-loop/com.factory-loop.plist.template` | The hourly launch agent, with `<repo-root>` and `<user>` placeholders, logging into `~/.factory-loop/logs/` |
| `tests/tooling/test_factory_loop.py`, `tests/tooling/__init__.py` | 33 tests through a stand-in runner; the empty `__init__.py` matches `tests/ci/` |
| `docs/build/Factory_onboarding.md` | New section "How the review loop works with you"; steps 1, 7, 8 and 9, the git rule, the checks intro, "The pull request" and "When you are stuck" no longer tell Factory to push, open the pull request, tell the owner or use a worktree beside the main checkout |
| `docs/build/Factory_review_loop.md` | Marked approved with the decision row; "Install" and "How to switch it off" added |
| `.claude/README.md` | One Skills row for `factory-loop` |

## Each approval and where the code enforces it

| Approval | Where |
|---|---|
| 1. Hourly job outside the repository | The plist template: `StartInterval` 3600, `RunAtLoad` false; state, lock, logs and prompts in `~/.factory-loop/`; Factory's worktrees in `<worktree-root>/factory-<N>` |
| 2. Script under `.claude/skills/factory-loop/` | This branch, for its own pull request |
| 3. Review with an allowed-tools list, no bypass flag, merging only the reviewed pull request | `FactoryLoop.review_allowed_tools`: `gh pr merge <N> --merge --delete-branch` exactly, `gh pr review` and `gh pr comment` for `<N>` only, `git push` only for `chore/factory-done-<N>`, Edit and Write only in named files of the done worktree. `FactoryLoop.review` passes `--max-budget-usd` with what is left of $3 and no bypass flag. A missing or unknown verdict is `held` (`parse_review`); `merged` is checked against GitHub's state before clean-up |
| 4. Factory headless at `--auto medium` | `FactoryLoop.start_factory`: `droid exec --auto medium --cwd <worktree> -f <prompt file>`, flags checked against the installed command's help |
| 5. Key from the keychain at run time | `FactoryLoop.read_key`: never logged; added to a redaction list for every log line and file the script writes; put only in Factory's process environment; `_base_env` strips it from every other command, the review included |
| 6. Push `factory/...` only | `FactoryLoop.push_branch` raises `PushRefused` for any name not matching `factory/card<N>-<words>`, and never forces |
| 7. Limits | `limit_reached`: six runs or $3 a day, reset by date; one pull request handled at a time, the oldest, with a notice on more; `FIX_ROUNDS = 1`, a second failure is held with the owner's mention and the two options |

## Choices the lead should log

Each one is a choice between alternatives, for a `DECISIONS.md` row:

1. The review runs with `--restricted --strict-mcp-config --tools Bash,Read,Grep,Glob,Edit,Write,Agent`. Without it, the project's `.claude/settings.json` allows `Bash(git:*)`, `Bash(gh:*)`, Edit and Write, and those merge with `--allowedTools`, so the narrow list would mean nothing. Restricted mode ignores the user, project and local settings files (the installed command's help, version 2.1.289). Cost: the project's hooks do not run inside the review.
2. Three permissions beyond the brief's list, each needed for a step the brief requires: Edit inside the throwaway review worktree (removing one part of the fix at a time); Edit and Write on `docs/build/Factory_onboarding.md` in the done worktree (`check_doc_sync.py` rule factory-lane fails while a card in the retest list keeps its brief section); `git -C <done worktree> add` and `commit` (the done branch needs a commit to push).
3. A "run" counts only when it starts Factory or the review, the two that spend. Counting every hourly wake would stop the loop six hours into each day.
4. Findings are posted as a comment review, because GitHub refuses a request for changes on one's own pull request and the script opens Factory's pull requests from the owner's account.
5. Safety checks the script adds before spending: a `factory/` pull request from a fork or another account is ignored (the repository is public); a pull request with a path outside Factory's fence is held before any review; Factory is started at most twice on a card that never commits.
6. The done pull request is opened and left open: approval 3 merges only the reviewed Factory pull request.
7. The brief keeps the heading "Checks before you push", because `tracker/Living_documents.md` registers it; its text now says the loop pushes.

## Tests and mutations

`pytest tests/tooling -q`: 33 passed. One test or group per decision path the brief names, and a few more:

- The brief's paths: none open and the next card; a worktree ready to push; CI pending; review merged; changes requested, then Factory's fix and the push; a second failure held with the owner's mention; both limits; two open; five refused pushes; the key; four missing or unknown verdicts.
- Added: an already reviewed head; the allowed-tools list and budget; merged by the review but not on GitHub; a fix round with no commit; a new day's reset; a fork's pull request; the fence; a missing key; unreadable output; the dry run; the plist.

One property broken per group, the group run, the file restored:

| Property broken | Result |
|---|---|
| Next card skips cards not in To do | Red, 2 failed |
| A worktree with commits opens a pull request | Red, 1 failed |
| CI pending waits | Red, 1 failed |
| Merged cleans up | Red, 1 failed |
| Merge rule names this number only | Red, 1 failed |
| Fix round pushes | Red, 1 failed |
| Second failure is held | Red, 1 failed |
| Run limit | Red, 1 failed |
| Spend limit | Red, 1 failed |
| Two open: the oldest | Red, 1 failed |
| Push refuses non-factory branches | Red, 5 failed |
| The review never gets the key | Red, 1 failed |
| Only the last line is the verdict | Red, 1 failed |
| Fence holds before review | Red, 1 failed |
| Forks are ignored | Red, 1 failed |
| Dry run stops before a change | Red, 1 failed |

After restoring: 33 passed, and the file matched the staged copy.

## Gates

| Gate | Result |
|---|---|
| `ruff check` | All checks passed |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |
| `pytest tests/tooling -q` | 33 passed |
| `python3 tracker/check_doc_sync.py` | exit 0, ok |
| `python3 tracker/check_doc_drift.py --check` | exit 0, 0 structural |
| `python3 tracker/check_living_docs.py` | exit 0, 20 rows |
| `check_public_leaks.py --base origin/develop --no-fetch` | exit 0, after one test line with a home path was rewritten |

## What could not be done

- No live run: the review's flags (`--restricted`, `--tools`, `--max-budget-usd`, the `Bash(x *)` and `~/` rule forms, the exact merge rule) come from the installed help and were never exercised. The first hand run on card 100 ("How we test it first", step 1) must confirm that the Agent tool and the `phase-reviewer` agent load in restricted mode and that each allowed command is accepted.
- The design's step 3, "the schedule for card 106 only", has no switch in the script; the install section says to unload the agent after card 106 merges.
- Nothing installed: no plist loaded, no keychain entry, no commit.
