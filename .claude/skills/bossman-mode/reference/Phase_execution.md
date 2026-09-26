# Running a numbered phase

Read this at four points: opening a phase, splitting it, dispatching builders, and closing it. Two things live elsewhere and are not repeated here:

- The judge, the adversary and the fix-and-verify round: `reference/Review_rounds.md`.
- The product review and the golden consistency run: `reference/Product_review.md`.

`SKILL.md` holds what is true for every change: the dial, the team, the stages, the budgets and where everything is written. This file carries what a lead needs to run a numbered phase, whichever position the dial sits at. A card worked alone reads `reference/UI_fix_loop.md` instead.

## Table of contents

- [Step 1: pick and open the phase](#step-1-pick-and-open-the-phase)
- [Transport preflight](#transport-preflight)
- [Step 2: confirm entry and show the team](#step-2-confirm-entry-and-show-the-team)
- [Step 3: split the work and write the acceptance](#step-3-split-the-work-and-write-the-acceptance)
- [The phase ledger](#the-phase-ledger)
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
4. Transport preflight: `python3 tracker/preflight.py`, per the section below. Exit 1 means a transport is down, and you do not dispatch what that transport gates.
5. Read `LEARNINGS.md` filtered to this phase, its tools and its layers (`learnings --brief N.M`). Past dead ends are cheaper to read than to rediscover.
6. Open the phase ledger with `task-tracker --open N.M`: `tracker/phase_N.M.md`, with the sections under "The phase ledger" below. `tracker/BOARD.md` is frozen and gets no row; the phase's cards on `testing/UI_fix_plan.md` move to Build in progress.
7. Cut the phase branch and push it before any builder is dispatched: `git checkout develop && git pull origin develop && git checkout -b phase/N.M-description && git push -u origin phase/N.M-description`. Use Section 25's exact name for a Section 25 phase, and `phase/N.M-short-description` for a phase numbered after 7.1. Builders start from the pushed branch, never from develop's tip (Step 4).
8. Set the dial position from the tickets (`SKILL.md`, "Set the dial first") and write it in the ledger's Budget section. A numbered phase keeps its branch and pull request at every position; the position says whether the judge and the adversary run.
9. Start the clock. The phase has 8 hours from here to "ready for owner".
10. If the phase touches the answer path, record the golden floor now: the answered count of the latest accepted consistency run, from `reference/Product_review.md`.

When a probe reports `down` and it is a real outage, wait and re-probe rather than reading a dead dispatch as a defect in the work. If the task is small, do it inline: a two-file read plus a grep was measured as cheaper inline than the two dead dispatches that preceded it.

## Transport preflight

Added 2026-08-18, closing the priority-1 recommendation in `docs/build/Build_velocity_post_mortem.md`. What `python3 tracker/preflight.py` does:

- Probes one endpoint per transport before anything expensive is dispatched.
- Exits 1 when a transport is down.

There is one probe per transport rather than one probe. The first attempt at this check probed the product's model provider while the thing dying was agent dispatch against a different endpoint, so a green result predicted nothing.

| Transport | Gates | Dead-dispatch cost |
| --- | --- | --- |
| `product-model` | The golden run, answer-path premise gates, anything calling `harness.call_tier` | 6 to 10 minutes |
| `harness-model` | Every agent dispatch | 15 to 25 minutes |
| `graph` | Tool premise gates, live graph tests | The run, plus the misdiagnosis |

Re-run it with `--transport harness-model` immediately before any agent dispatch later in the phase, and again before a review-agent dispatch, since a transport alive at phase open can die an hour in. Two results are easy to misread:

- A `down` result on a host outside the sandbox allowlist may be a denial rather than an outage. The two are indistinguishable at that layer and the script says so instead of guessing.
- A `skipped` result means the transport was not configured, so nothing was verified, which is not the same as a pass.

## Step 2: confirm entry and show the team

Print a short entry block naming, one line each: the plan, the phase number and title, why it was picked now in the user's words, the dial position and why, the branch and its pushed head, the ledger path and ticket count, the deliverables, the file fences, the team by role with counts and tiers, the dispatch budget planned against the cap of 8, which builders get worktree isolation, whether the phase touches the answer path, the gates queued at phase end, and the next check-in point.

Then dispatch. Do not ask for confirmation.

## Step 3: split the work and write the acceptance

The lead does this, on the depth tier, because a bad split cascades into every worker.

- Split by file. Every ticket names the exact files it may touch, its file fence, and no two tickets share a file. When two pieces of work must touch one file, they are one ticket.
- Write each ticket's acceptance in the user's words: one sentence a person using the product would recognise, plus the test command that proves it. "A question about one gene never shows records for a different gene", not "wire the filter into the act result path".
- No fix without a diagnosis. A card whose cause is unknown becomes a diagnosis ticket, and only that: its acceptance is a written diagnosis, in the ledger or a dated report folder, naming the cause and the evidence. A fix ticket for it opens only after the lead has read that diagnosis. The lead may write the diagnosis itself when the cause is plain. Measured on the night of 2026-09-25: three cards the plan itself said had "no diagnosed cause yet" were dispatched as fixes, all three were reverted after review, and 4 of phase 8.1's 8 tickets put nothing on develop.
- Read `docs/build/design/README.md`'s coverage table before ticketing any screen. A surface with no design is named as a gap in the ticket, and the builder builds from the foundations and the nearest designed neighbour, per `design-consistency`. The sign-in screen shipped as raw HTML inside a designed shell because nobody read that table.
- Mark each ticket answer path or not. An answer-path ticket is one that can change what an answer says, which records it names or cites, or whether a question is answered or refused. The phase's golden run depends on this mark, and an answer-path ticket puts the phase at dial position 2 at least.
- Trace each ticket to its spec section, or to the board card the owner approved. A ticket with no anchor is scope creep or a spec gap, and both go back to the owner.

## The phase ledger

`tracker/phase_N.M.md` is the phase's one record. Its sections, in this order, so an append always lands in Findings:

- Title and opening line: the branch, when it opened, and the owner's yes that opened it.
- Table of contents.
- Goal contract: done-when, verify, output, constraints, blocked-stop, per `goal-contracts`.
- Budget: the wall clock from the opening time, the dispatch cap of 8 and the plan against it, the golden floor and whether the phase touches the answer path, the dial position, the spend cap where the owner set one, and the dispatch table below.
- Tickets: per the `task-tracker` skill's format, each with its builder, its files and its acceptance in the user's words.
- History: dated lines, appended, never rewritten. Each builder's base commit at dispatch is one of them.
- Findings: every finding as a ledger row the moment it is established (`reference/Review_rounds.md`).

The dispatch table sits in Budget. The lead appends a row when it dispatches an agent and completes the row when the agent returns, with the tokens read from the task notification:

| Role | Model | Effort | Started | Ended | Tokens |
| --- | --- | --- | --- | --- | --- |
| builder A | balance | medium | 05:12 | 06:40 | 184,000 |

The "8 of 8" is read from this table and never counted by hand. The checkpoint quotes dispatches used and tokens spent from it. It is the first record of what a phase costs to build: no billing log exists on the build side, so until 2026-09-25 the owner could be told what the product spent to the cent and nothing about the build (build harness review, finding 8).

## Step 4: dispatch builders

For a phase with two or more parallel builder tasks:

1. Push the phase branch again if anything was committed since Step 1's push, so every builder starts from the phase's real head.
2. Create an agent team with one teammate per builder task, each in its own tmux pane.
3. Give every concurrent file-mutating builder `isolation: "worktree"`. A worktree is cut from the checkout's current commit, which is develop's tip whenever the lead has not switched to the phase branch, so the brief's first step fetches and fast-forwards onto the pushed phase branch (the template below). Measured on 2026-09-25: phase 8.6's builders started at `2c6374f` while the branch stood at `13d2f2d`, harmless because that commit held only the ledger, a trap when it holds code.
4. Hand each builder exactly what "What a worker is handed" lists, and nothing else.
5. Record each builder's base commit in the ledger's History as the builder reports it, and append its row to the Budget's dispatch table.
6. Teammates claim tickets and set their own ticket to `in-progress` the moment they pick it up, not when they finish. A ticket being worked while still reading `todo` is a lie about the state of the phase.
7. The lead monitors the ledger and messages stuck teammates. A stuck teammate gets a clearer prompt or a fresh start; fresh starts combat drift. A message that changes a worker's scope binds; a worker checks any factual claim in it against the code before acting on it.
8. A builder that finishes sets its ticket to `in-review`, never to `done`.
9. When all tickets are `in-review`, disband the team and tear down the worktrees.

For a phase with one builder task, use a sub-agent in the shared checkout instead, on the phase branch.

Workers do not coordinate with each other, and they only work in parallel when their fences are disjoint. Two agents editing the same file are individually correct and structurally blind to each other, which is how two correct changes compose into a defect nobody reviewing either one can see.

Every builder reads the ledger's Findings section before it starts and again before it reports, even for tickets it does not own. Isolation is about write access, never about awareness.

## The dispatch budget

A phase gets 8 agent dispatches in total. Product-owner decision of 2026-09-24.

- Everything counts: builders, the clerk, the judge, the adversary, fix agents, the fresh verifier and the product reviewer. A resumed agent does not count again; a fresh one does.
- A typical phase spends it like this: two or three builders, one judge, one adversary, one fix agent, one fresh verifier, one product reviewer. The clerk's work is folded into the lead's session when the budget is tight.
- Plan the budget in the entry block, before the first dispatch, so the review round is never the thing that runs out.
- Count it in the ledger's dispatch table, a row per dispatch with its tokens, and read "used of 8" from there.
- The ninth dispatch needs the owner's yes. Ask with what is left, what it would cost and what happens without it.
- Workers never dispatch. The rule is written into every brief, and the preferred agent types for reviewers, `phase-reviewer` and `product-reviewer`, have no Agent tool at all, which is `system-design-patterns` pattern 8: remove the ability rather than ask for restraint. The redesign's own diagnosis reached about 17 concurrent agents because two workers fanned out on their own slice.

## What a worker is handed, and what it is not

A worker is handed:

- The ticket: one acceptance sentence in the user's words, and the test command that proves it.
- Its file fence: the exact files it may touch.
- The branch to start from, and the command that puts its worktree there.
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
- Re-enter a partially built phase with `--phase N.M`. This is a rescue path, not a default.

## Multi-agent safety

Worktree isolation is the default for concurrent file-mutating builders, per the 2026-07-21 decision in `DECISIONS.md`, not a fallback after a collision.

| Agent kind | Isolation |
| --- | --- |
| Builder creating or modifying files, concurrent with another builder | `isolation: "worktree"`, fast-forwarded onto the pushed phase branch as its first step |
| Sole builder in a phase, no concurrency | Shared checkout, on the phase branch |
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

First, in your worktree or checkout:
  git fetch origin && git merge --ff-only origin/[phase branch, or develop for a card alone]
  git rev-parse HEAD
Report that commit as your base in your first message. Do not touch git stash
and do not switch branches.

Ticket or task: [one sentence in the user's words, and the command that proves it]
Files you may touch: [the fence, exact paths; "none" for a reviewer]
Files to read: [exact paths, only what the task needs]
Learnings: [the one to three LEARNINGS.md rows naming those files]
Constraints: [architectural decisions that apply]

Do not dispatch agents. If the task needs more hands, stop and report that.

If you start a process, do not end your turn until it has exited; poll it and
read its output.

Numbers in your report are pasted from the command's output, never retyped.

If the lead sends you a message mid-run, it can change your scope; check any
factual claim in it against the code before acting on it.

A failure that cost you more than five minutes is a LEARNINGS.md row before
you continue, with what you tried and what fixed it. If your brief forbids
writing anywhere but one path, write the row's text there and say it is a
learning; the lead moves it.

Write findings to [the phase file's Findings section, or the one report path
named here] the MOMENT you establish one, before you do anything else with it:
before you verify anything, before you continue, before you compose your
report. Your context is not storage. It ends without warning, and a finding
that lives only there is lost when it does.

Do not ask questions. Execute and report back.
If stuck, report the blocker clearly. Do not guess on ambiguous requirements.
```

Four lines of that template were added on 2026-09-25 from the night's record (build harness review, S5, S7 and S9):

- The base step: worktrees were cut from develop's tip while the phase branch stood one commit ahead (observation 2).
- The process line: a bench worker twice ended its turn while its own background run was still going, so no results file was written; the lead watched the process and resumed the worker by message (observation 1).
- The numbers line: an analyst's summary said two golden runs started 27 minutes apart when its own table showed 3 hours 15 minutes (observation 7).
- The mid-run message line: a worker declined a scope change from its lead as untrusted while, in the same message, correctly catching the lead's wrong guess about a failure's cause. Both halves matter: the lead's message binds, and its claims are checked.
- The learnings line: across the fix loop the learnings rows clustered on checkpoint days, five of nine working days with none, while the skill said to write at the moment of failure.

For teammates, the task in the shared task list carries the same fields:

- The base step, the ticket and the fence.
- The files to read and the learnings rows.
- The constraints and the test files to write.
- The instruction never to dispatch, and the four worker lines above.
- The instruction to mark the task complete when done.

Two rules govern context across the team:

- Fresh context per agent. Every teammate and sub-agent starts with a clean context window and gets only what the list above names. Never pass conversation history or an earlier agent's reasoning.
- Thin orchestrator. When a sub-agent returns or a teammate marks a task complete, capture a one-line summary of what it produced and which files it touched, and complete its dispatch row. Do not inline the full result into your own context.

## Step 5: gates and ship

Run the phase-end chain in full, in order. These grade whether the work is allowed to ship, which is a different question from the judge's, so do not treat them as optional because the judge passed.

1. `verify`: compile check, tests, lint, git status.
2. `ship`: the CI gates run locally (ruff over the whole repository, isort, the unit suite when Python changed, `npm run build` when the frontend changed, the doc drift check), the docs sync, the commit, the push of the phase branch and the pull request.
3. `task-tracker --close`: record the evidence on each ticket in the ledger and leave each at `in-review`. The board is frozen, so nothing is rendered.

The chain lists only gates a ledger records as run, each with its result line pasted at the checkpoint. Four skills that used to sit in it stay available to invoke by name whenever their ritual is wanted, and none is assumed:

- `eval-harness`: its grader is parked since the evaluation track closed on 2026-08-31, and no 8.x ledger recorded a run.
- `dev-standards`: zero commit mentions since 2026-08-25 and no 8.x run.
- `python3 tracker/check_learnings_coverage.py N.M`: no 8.x run; the learnings practice is now the five-minute line in every brief.
- `release-workflow`: 0 real dispatches of 6 phases through build phase 3.4 while the steps above ran and caught real defects every phase (Step 6.2, 2026-08-10).

The first three left the chain on 2026-09-25 by the build harness review (D4): an unrun gate is an ownerless requirement by the `attack-the-constraint` standard, and the golden run after merge is the answer-path gate. If any gate fails, fix the root cause and restart from step 1 of this chain.

## Step 6: phase checkpoint

Print a checkpoint naming, one line each:

- The branch and the PR.
- The dial position, and why.
- The ledger counts, including tickets deferred with a reason.
- What a person will notice, in their words, per ticket.
- The judge result and the adversary findings count, where the position ran them.
- The review rounds used of two, what round 2 changed, and every item merging open with its named owner.
- Any regression found inside a prior fix, with its `Regression of` link.
- The instrument share: how many of the round's findings were about the phase's own tests or documents.
- Each gate's pass or fail with its result line pasted.
- The budget used: hours since phase open of 8, and dispatches used of 8 with tokens spent, both pasted from the ledger's dispatch table.
- The golden floor, if the phase touches the answer path, which the product review measures after merge.
- The scope check against `v1-scope-boundary`.
- The learnings logged, and the decisions taken without asking with the reason for each, in the user's words.
- The blockers, the context health tier, and the next phase with its user-chair reason.

Any entry under regressions means the phase escalated rather than closed.

## Step 7: merge, product review, owner retest

1. The owner reads the checkpoint and merges the PR, or requests changes on the same branch, adjusts the plan, asks about decisions taken, or exits with `--stop`.
2. Develop deploys. Confirm the deployment reports SUCCESS and the served app carries the change.
3. Dispatch the product reviewer, per `reference/Product_review.md`. It reports answered against the floor and answered well of the fixed ten. On an answer-path phase its golden run blocks: any drop in the answered count stops everything else landing on develop until the phase is fixed or reverted.
4. The owner retests on develop, with the product review as the list of what to look at first. Their verdict moves tickets to `done`, or sends defects back to builders under the same budget.

Do not open the next phase until the owner has given that verdict and says to continue.

Level 2 (unattended overnight execution) is deferred by product-owner decision of 2026-07-26 until it is known to be needed. It was granted once, for the night of 2026-09-25 only. Do not enable it by inference from a general "keep going": it overrides this step and the standing deny in the `bossman-mode` rule, so it needs an explicit itemized grant.

## Context management

Long sessions degrade as context fills. You cannot read your own token count, so watch output quality instead.

| Tier | Usage | Behaviour |
| --- | --- | --- |
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
| --- | --- | --- |
| `requirements/Technical_specification.md` | The build blueprint. Section 25 defines what each phase delivers and which dependencies are real | Lead always, builders for their own section |
| `requirements/PRD.md` | The product contract. Its out-of-scope list is a hard boundary | Lead, judge |
| `requirements/Evaluation_playbook.md` | Competency questions, the rubric, the coverage metric | Lead, and `eval-harness` when it is invoked |
| `docs/ncbi/Tool_implementation_mechanics.md` | Per-tool API traps that are expensive to discover late | Any builder wiring a tool |
| `LEARNINGS.md` | What already broke here and what fixed it | Lead at phase start; builders get only the rows naming their files |

System 1 and System 2 code, for Cypher patterns and AGE schema, is symlinked read-only at `reference/agentic-search-data-engineering`. Read its CLAUDE.md before sending a builder to it.
