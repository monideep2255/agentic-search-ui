# Running a build phase

Read this at four points: opening a phase, splitting it, dispatching builders, and closing it. Two things live elsewhere and are not repeated here:

- The judge, the adversary and the fix-and-verify round: `reference/Review_rounds.md`.
- The product review and the golden consistency run: `reference/Product_review.md`.

`docs/build/Build_workflow_cadence.md` is the stage-by-stage quick reference, including the flow, the model assignment table and the provider mapping. This file does not restate them. It carries what a lead needs that the cadence doc does not hold.

## Table of contents

- [Step 1: pick and open the phase](#step-1-pick-and-open-the-phase)
- [Step 2: confirm entry and show the team](#step-2-confirm-entry-and-show-the-team)
- [Step 3: split the work and write the acceptance](#step-3-split-the-work-and-write-the-acceptance)
- [Step 4: dispatch builders](#step-4-dispatch-builders)
- [The dispatch budget](#the-dispatch-budget)
- [What a worker is handed, and what it is not](#what-a-worker-is-handed-and-what-it-is-not)
- [Agent teams setup](#agent-teams-setup)
- [Multi-agent safety](#multi-agent-safety)
- [Agent prompt template](#agent-prompt-template)
- [Step 5: gates and ship](#step-5-gates-and-ship)
- [Step 6: phase checkpoint](#step-6-phase-checkpoint)
- [Step 7: merge, product review, owner retest](#step-7-merge-product-review-owner-retest)
- [Context management](#context-management)
- [The documents a phase builds against](#the-documents-a-phase-builds-against)

## Step 1: pick and open the phase

Pick the phase by what a person sees first. Product-owner decision of 2026-09-24: answer quality and speed come ahead of technical specification Section 25's order.

- The candidates are Section 25's remaining phases, the items carried into `requirements/Plan.md` Phase 7, and anything the product owner names. Never invent a phase.
- Rank them by what the person typing a question notices first, per `decide-from-the-users-chair`: a wrong or missing answer, then a slow one, then a screen that looks wrong, then everything a person never sees.
- A real dependency still binds. If a candidate needs another phase merged first, per Section 25's dependency graph, that phase goes first or the candidate waits. Report the reorder in the entry block with the user-chair reason.

Then open it:

1. Run `best-practices`: session checklist covering venv, API keys, dev server, CLAUDE.md, git status.
2. Read `HANDOFF.md`. It is the one file a fresh session reads to know what is live, what awaits the owner and the one next action. Do not rebuild state from the board, `CLAUDE.md` and `requirements/Plan.md`.
3. Agent teams preflight: run the tmux check under "Agent teams setup". If tmux is missing or the session is not inside tmux, print the setup steps and let the user fix it before any builder dispatch.
4. Transport preflight: `python3 tracker/preflight.py`. Exit 1 means a transport is down, and you do not dispatch what that transport gates. Re-run it with `--transport harness-model` immediately before any agent dispatch later in the phase, since a transport alive at phase open can die an hour in. Two results are easy to misread: a `down` result on a host outside the sandbox allowlist may be a denial rather than an outage, and a `skipped` result means nothing was verified, which is not a pass. The per-transport table is in `docs/build/Build_workflow_cadence.md` under "Transport preflight".
5. Read `LEARNINGS.md` filtered to this phase, its tools and its layers (`learnings --brief N.M`). Past dead ends are cheaper to read than to rediscover.
6. Open the phase board with `task-tracker --open N.M`.
7. Cut the phase branch using the exact name from Section 25's table: `git checkout develop && git pull origin develop && git checkout -b phase/N.M-description`.
8. Start the clock. The phase has 8 hours from here to "ready for owner".
9. If the phase touches the answer path, record the golden floor now: the answered count of the latest accepted consistency run, from `reference/Product_review.md`.

When a probe reports `down` and it is a real outage, wait and re-probe rather than reading a dead dispatch as a defect in the work. If the task is small, do it inline: a two-file read plus a grep was measured as cheaper inline than the two dead dispatches that preceded it.

## Step 2: confirm entry and show the team

Print a short entry block naming, one line each: the plan, the phase number and title, why it was picked now in the user's words, the branch, the board path and ticket count, the deliverables, the file fences, the team by role with counts and tiers, the dispatch budget planned against the cap of 8, which builders get worktree isolation, whether the phase touches the answer path, the skills queued at phase end, and the next check-in point.

Then dispatch. Do not ask for confirmation.

## Step 3: split the work and write the acceptance

The lead does this, on the depth tier, because a bad split cascades into every worker.

- Split by file. Every ticket names the exact files it may touch, its file fence, and no two tickets share a file. When two pieces of work must touch one file, they are one ticket.
- Write each ticket's acceptance in the user's words: one sentence a person using the product would recognise, plus the test command that proves it. "A question about one gene never shows records for a different gene", not "wire the filter into the act result path".
- Read `docs/build/design/README.md`'s coverage table before ticketing any screen. A surface with no design is named as a gap in the ticket, and the builder builds from the foundations and the nearest designed neighbour, per `design-consistency`. The sign-in screen shipped as raw HTML inside a designed shell because nobody read that table.
- Mark each ticket answer path or not. An answer-path ticket is one that can change what an answer says, which records it names or cites, or whether a question is answered or refused. The phase's golden run depends on this mark.
- Trace each ticket to its spec section. A ticket with no anchor is scope creep or a spec gap, and both go back to the owner.

## Step 4: dispatch builders

For a phase with two or more parallel builder tasks:

1. Create an agent team with one teammate per builder task, each in its own tmux pane.
2. Give every concurrent file-mutating builder `isolation: "worktree"`.
3. Hand each builder exactly what "What a worker is handed" lists, and nothing else.
4. Teammates claim tickets and set their own ticket to `in-progress` the moment they pick it up, not when they finish. A ticket being worked while still reading `todo` is a lie about the state of the phase. Use the Edit tool for board changes, never `sed`, or the page will not re-render.
5. The lead monitors the board and messages stuck teammates. A stuck teammate gets a clearer prompt or a fresh start; fresh starts combat drift.
6. A builder that finishes sets its ticket to `in-review`, never to `done`.
7. When all tickets are `in-review`, disband the team and tear down the worktrees.

For a phase with one builder task, use a sub-agent in the shared checkout instead.

Workers do not coordinate with each other, and they only work in parallel when their fences are disjoint. Two agents editing the same file are individually correct and structurally blind to each other, which is how two correct changes compose into a defect nobody reviewing either one can see.

Every builder reads the phase file's Findings section before it starts and again before it reports, even for tickets it does not own. Isolation is about write access, never about awareness.

## The dispatch budget

A phase gets 8 agent dispatches in total. Product-owner decision of 2026-09-24.

- Everything counts: builders, the clerk, the judge, the adversary, fix agents, the fresh verifier and the product reviewer. A resumed agent does not count again; a fresh one does.
- A typical phase spends it like this: two or three builders, one judge, one adversary, one fix agent, one fresh verifier, one product reviewer. The clerk's work is folded into the lead's session when the budget is tight.
- Plan the budget in the entry block, before the first dispatch, so the review round is never the thing that runs out.
- The ninth dispatch needs the owner's yes. Ask with what is left, what it would cost and what happens without it.
- Workers never dispatch. The rule is written into every brief, and the preferred agent types for reviewers, `phase-reviewer` and `product-reviewer`, have no Agent tool at all, which is `system-design-patterns` pattern 8: remove the ability rather than ask for restraint. The redesign's own diagnosis reached about 17 concurrent agents because two workers fanned out on their own slice.

## What a worker is handed, and what it is not

A worker is handed:

- The ticket: one acceptance sentence in the user's words, and the test command that proves it.
- Its file fence: the exact files it may touch.
- Only the files it needs to read, named.
- The one to three `LEARNINGS.md` rows that name one of those files.
- For a screen, its design card and the matching section of `prototype/app.html`.

A worker is never handed:

- The build history, the board, other phases' findings or review reports.
- The conversation or the lead's reasoning. This was already the rule for reviewers in `self-eval-loop`.
- Permission to dispatch agents.

## Agent teams setup

One-time per machine: install tmux (`brew install tmux`). The two settings keys, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and `teammateMode`, are already configured.

Teammate panes only appear when the CLI runs inside a tmux session, so start tmux first, launch inside it, then activate bossman. Navigate panes with `Ctrl-b` then an arrow key.

Preflight, at Step 1:

```bash
command -v tmux >/dev/null && echo "tmux: ok" || echo "tmux: MISSING"
echo "inside tmux: ${TMUX:+yes}${TMUX:-no}"
```

If tmux is missing or the session is not inside tmux, print the setup steps and let the user fix it before builders dispatch. Do not silently fall back to invisible background sessions: builders still run in parallel without tmux, but the user loses the live pane view that is the point of agent teams.

Which command to launch is a decision, not a default, and it cannot be changed inside a running session:

- Open a phase on the primary provider, always, because the split is where a bad decision cascades into every builder.
- Hand the builder stage to the alternate metered backend afterwards if the budget is tight, and return to the primary for the judge onward.
- If the primary budget runs out mid-phase, split the phase across sessions rather than switching backend mid-run. State each session's stop condition when you invoke it.
- Re-enter a partially built phase with `--phase N`. This is a rescue path, not a default.

## Multi-agent safety

Worktree isolation is the default for concurrent file-mutating builders, per the 2026-07-21 decision in `DECISIONS.md`, not a fallback after a collision.

| Agent kind | Isolation |
|------------|-----------|
| Builder creating or modifying files, concurrent with another builder | `isolation: "worktree"` |
| Sole builder in a phase, no concurrency | Shared checkout |
| Read-only agents: judge, adversary, verifier, product reviewer | Shared checkout, always |

Partition first, isolate second. Worktrees make concurrent writes safe; they do not make an overlapping split correct. A worktree left standing after a phase closes is leaked state, so the lead removes it at the phase checkpoint.

Beyond the git hygiene `git-workflow` already carries, four conventions bind a teammate:

- Stage files by name. Never `git add -A` or `git add .` across the repository.
- A teammate that encounters files it did not create notes them and continues. It does not clean them up, reformat them, or include them in its commit.
- Do not create, apply or drop `git stash` entries, do not switch branches, and do not create or remove worktrees unless the lead instructs it. Other teammates may be working.
- Formatting-only diffs (lint, whitespace, import order) auto-resolve without asking. Semantic changes to logic, data or behaviour ask first.

The machine's CPU is the one shared resource a fence cannot split. Two agents that both see a quiet machine and start a suite together drove the load average to 20 in the fix loop, and a suite result measured under that load is re-run before it counts.

## Agent prompt template

For sub-agents (judge, adversary, fix agent, verifier, product reviewer, clerk):

```text
You are the [ROLE] on a bossman mode execution team.

Ticket or task: [one sentence in the user's words, and the command that proves it]
Files you may touch: [the fence, exact paths; "none" for a reviewer]
Files to read: [exact paths, only what the task needs]
Learnings: [the one to three LEARNINGS.md rows naming those files]
Constraints: [architectural decisions that apply]

Do not dispatch agents. If the task needs more hands, stop and report that.

Write findings to [the phase file's Findings section, or the one report path
named here] the MOMENT you establish one, before you do anything else with it:
before you verify anything, before you continue, before you compose your
report. Your context is not storage. It ends without warning, and a finding
that lives only there is lost when it does.

Do not ask questions. Execute and report back.
If stuck, report the blocker clearly. Do not guess on ambiguous requirements.
```

For teammates, the task in the shared task list carries the same fields:

- The ticket and the fence.
- The files to read and the learnings rows.
- The constraints and the test files to write.
- The instruction never to dispatch.
- The instruction to mark the task complete when done.

Two rules govern context across the team:

- Fresh context per agent. Every teammate and sub-agent starts with a clean context window and gets only what the list above names. Never pass conversation history or an earlier agent's reasoning.
- Thin orchestrator. When a sub-agent returns or a teammate marks a task complete, capture a one-line summary of what it produced and which files it touched. Do not inline the full result into your own context.

## Step 5: gates and ship

Run the phase-end chain in full, in order. These grade whether the work is allowed to ship, which is a different question from the judge's, so do not treat them as optional because the judge passed.

1. `verify`: compile check, tests, lint, git status.
2. `eval-harness`: required on any phase touching answer generation, grounding, citations or the trust signal.
3. `dev-standards`: the six-lens production readiness pass. Required on any phase that shipped application code, skippable for docs-only or config-only changes.
4. `python3 tracker/check_learnings_coverage.py N.M`: fails the phase close if any finding reached `confirmed` or `closed` with no matching `LEARNINGS.md` row. A `FAIL` means write the missing entry now and re-run, not skip it.
5. `ship`: docs-sync, commit, push the phase branch, open the PR.
6. `task-tracker --close`: record the evidence on each ticket, leave each at `in-review`, then run `python3 tracker/render_board.py` explicitly and republish. The explicit render is a backstop: the sync hook fires on Edit and Write only, so a board change made through Bash slips past it.

`release-workflow` is available to invoke directly whenever its end-to-end ritual is wanted. It is not the assumed default: it measured 0 real dispatches of 6 phases through build phase 3.4 while the steps above ran and caught real defects every phase.

If any gate fails, fix the root cause and restart from step 1 of this chain.

## Step 6: phase checkpoint

Print a checkpoint naming, one line each:

- The branch and the PR.
- The board counts, including tickets deferred with a reason.
- What a person will notice, in their words, per ticket.
- The judge result and the adversary findings count.
- The review rounds used of two, what round 2 changed, and every item merging open with its named owner.
- Any regression found inside a prior fix, with its `Regression of` link.
- The instrument share: how many of the round's findings were about the phase's own tests or documents.
- Each gate's pass or fail with its result line pasted.
- The budget used: hours since phase open of 8, dispatches used of 8.
- The golden floor, if the phase touches the answer path, which the product review measures after merge.
- The scope check against `v1-scope-boundary`.
- The learnings logged, and the decisions taken without asking with the reason for each.
- The blockers, the context health tier, and the next phase with its user-chair reason.

Any entry under regressions means the phase escalated rather than closed.

## Step 7: merge, product review, owner retest

1. The owner reads the checkpoint and merges the PR, or requests changes on the same branch, adjusts the plan, asks about decisions taken, or exits with `--stop`.
2. Develop deploys. Confirm the deployment reports SUCCESS and the served app carries the change.
3. Dispatch the product reviewer, per `reference/Product_review.md`. On an answer-path phase its golden run blocks: any drop in the answered count stops everything else landing on develop until the phase is fixed or reverted.
4. The owner retests on develop, with the product review as the list of what to look at first. Their verdict moves tickets to `done`, or sends defects back to builders under the same budget.

Do not open the next phase until the owner has given that verdict and says to continue.

Level 2, unattended overnight execution, is deferred by product-owner decision of 2026-07-26 until it is known to be needed. Do not enable it by inference from a general "keep going": it overrides this step and the standing deny in the `bossman-mode` rule, so it needs an explicit itemized grant.

## Context management

Long sessions degrade as context fills. You cannot read your own token count, so watch output quality instead.

| Tier | Usage | Behaviour |
|------|-------|-----------|
| PEAK | 0-30% | Full operation. Read files freely, inline results |
| GOOD | 30-50% | Normal operation |
| DEGRADING | 50-70% | Economize reads to headers and frontmatter for routing decisions. Summarize sub-agent results in one line. Warn at the next checkpoint |
| CRITICAL | 70%+ | Checkpoint immediately with `/phase-checkpoint`, so `HANDOFF.md` carries the state, and tell the user to start a fresh session |

Degradation signals. Any two in one phase mean DEGRADING regardless of estimated usage:

- Increasing vagueness where file paths belong.
- Skipped protocol steps.
- Repeated phrases or filler.
- Sub-agent prompts getting shorter than earlier dispatches.
- Summaries that restate rather than synthesize.

Every phase boundary is a context reset point. `HANDOFF.md` is the handoff document, and it carries:

- What is live.
- What awaits the owner.
- The one next action.
- Where the facts live.

## The documents a phase builds against

Locked and frozen through the build, edited only at a reconciliation. A builder that thinks one of them is wrong reports it; it does not work around it.

| Document | What it is | Who reads it |
|----------|-----------|--------------|
| `requirements/Technical_specification.md` | The build blueprint. Section 25 defines what each phase delivers and which dependencies are real | Lead always, builders for their own section |
| `requirements/PRD.md` | The product contract. Its out-of-scope list is a hard boundary | Lead, judge |
| `requirements/Evaluation_playbook.md` | Competency questions, the rubric, the coverage metric | Lead, `eval-harness` |
| `docs/ncbi/Tool_implementation_mechanics.md` | Per-tool API traps that are expensive to discover late | Any builder wiring a tool |
| `LEARNINGS.md` | What already broke here and what fixed it | Lead at phase start; builders get only the rows naming their files |

System 1 and System 2 code, for Cypher patterns and AGE schema, is symlinked read-only at `reference/agentic-search-data-engineering`. Read its CLAUDE.md before sending a builder to it.
