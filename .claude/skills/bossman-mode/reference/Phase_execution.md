# Running a build phase

Read this at cadence stages 1 through 7 and 10 through 12: opening a phase, decomposing it, dispatching a team, and closing it. Stages 8 and 9, the judge and adversary rounds, are in `reference/Review_rounds.md` and are not repeated here.

`docs/build/Build_workflow_cadence.md` is the stage-by-stage quick reference, including the twelve-stage diagram, the model assignment table and the provider mapping. This file does not restate them. It carries what a lead needs that the cadence doc does not hold.

## Table of contents

- [Step 1: open the phase](#step-1-open-the-phase)
- [Step 2: confirm entry and show the team](#step-2-confirm-entry-and-show-the-team)
- [Step 3: research](#step-3-research)
- [Step 4: dispatch builders](#step-4-dispatch-builders)
- [Team roles and dispatch mode](#team-roles-and-dispatch-mode)
- [Agent teams setup](#agent-teams-setup)
- [Multi-agent safety](#multi-agent-safety)
- [Agent prompt template](#agent-prompt-template)
- [Step 10: gates and ship](#step-10-gates-and-ship)
- [Step 11: phase checkpoint](#step-11-phase-checkpoint)
- [Step 12: await approval](#step-12-await-approval)
- [Context management](#context-management)
- [The documents a phase builds against](#the-documents-a-phase-builds-against)

## Step 1: open the phase

1. Run `best-practices`: session checklist covering venv, API keys, dev server, CLAUDE.md, git status.
2. Agent teams preflight: run the tmux check under "Agent teams setup". If tmux is missing or the session is not inside tmux, print the setup steps and let the user fix it before any builder dispatch.
3. Transport preflight: `python3 tracker/preflight.py`. Exit 1 means a transport is down, and you do not dispatch what that transport gates. Re-run it with `--transport harness-model` immediately before any agent dispatch later in the phase, since a transport alive at phase open can die an hour in. Two results are easy to misread: a `down` result on a host outside the sandbox allowlist may be a denial rather than an outage, and a `skipped` result means nothing was verified, which is not a pass. The per-transport table and the measured dead-dispatch costs are in `docs/build/Build_workflow_cadence.md` under "Stage 4's transport preflight".
4. Read the phase definition from `requirements/Technical_specification.md` Section 25, the single source of truth for the 26 numbered build phases. Never invent a phase or reorder the sequence.
5. Verify every dependency phase in Section 25's dependency graph is already merged. If one is not, stop and report.
6. Read `LEARNINGS.md` filtered to this phase, its tools and its layers (`learnings --brief N.M`). Past dead ends are cheaper to read than to rediscover.
7. Open the phase board with `task-tracker --open N.M`. Decompose into tickets with acceptance criteria traced to spec sections before dispatching anyone.
8. Cut the phase branch using the exact name from Section 25's table: `git checkout develop && git pull origin develop && git checkout -b phase/N.M-description`.

When a probe reports `down` and it is a real outage, wait and re-probe rather than reading a dead dispatch as a defect in the work. If the task is small, do it inline: a two-file read plus a grep was measured as cheaper inline than the two dead dispatches that preceded it. "Each dispatched agent should carry a task worth its overhead" includes the failure rate, not only the setup cost.

## Step 2: confirm entry and show the team

Print a short entry block naming, one line each: the plan, the phase number and title with its Section 25 reference, the branch, the board path and ticket count, the deliverables, the estimated file scope, whether the phase is product owner required and why, how many learnings were read, the team composition by role with counts, which builders get worktree isolation, the skills active during the phase, the skills queued at phase end, and the next check-in point.

Then dispatch. Do not ask for confirmation.

## Step 3: research

Dispatch researcher sub-agents in parallel for unfamiliar APIs, libraries or codebases. They report context that builders will need. Skip this step when prior phases or the planning stage already supplied it.

## Step 4: dispatch builders

For a phase with two or more parallel builder tasks:

1. Create an agent team with one teammate per builder task, each in its own tmux pane.
2. Give every concurrent file-mutating builder `isolation: "worktree"`.
3. Define tasks from the board tickets: deliverable, acceptance criteria, context, reference files, constraints, the exact files it may touch, and the test files to write.
4. Teammates claim tickets and set their own ticket to `in-progress` the moment they pick it up, not when they finish. A ticket being worked while still reading `todo` is a lie about the state of the phase. Use the Edit tool for board changes, never `sed`, or the page will not re-render.
5. The lead monitors the board and messages stuck teammates. A stuck teammate gets a clearer prompt or a fresh start; fresh starts combat drift.
6. A builder that finishes sets its ticket to `in-review`, never to `done`.
7. When all tickets are `in-review`, disband the team and tear down the worktrees.

For a phase with one builder task, use a sub-agent in the shared checkout instead.

Workers do not coordinate with each other, but only when their work is genuinely disjoint. Two agents editing the same file are individually correct and structurally blind to each other, which is how two correct changes compose into a defect nobody reviewing either one can see. When work shares a file, it is one agent working serially, not two coordinating.

The corollary, and the reason this can read as agents working over each other: every builder READS the board's Findings section before it starts and again before it reports, even for tickets it does not own. Isolation is about write access, never about awareness. A builder that cannot see what its siblings found is not isolated, it is uninformed, and it will re-make a mistake already filed one pane over.

## Team roles and dispatch mode

| Role | Count | Dispatch mode | Responsibility | When |
|------|-------|---------------|----------------|------|
| Product owner | 1 (human) | Not dispatched | Approves the PR, decides scope, judges whether a UI actually feels right. Coordinates only with the lead | Phase boundaries, and any phase marked product owner required |
| Orchestrator (lead) | 1 (main session) | Always active | Decompose, create the team, track tickets, coordinate, own the board. Never builds directly when 2+ tasks exist | Always |
| Researcher | 1-N | Sub-agent | Fetch docs, read APIs, explore codebases before builders start | Pre-build |
| Builder | 2-N | Agent team | Execute independent build tasks in parallel, one ticket each | After research |
| Judge | 1 | Sub-agent | Single quality gate over all builder output | After all builders complete |
| Adversary | 0-1 | Sub-agent | Hostile unscripted use. Files findings to the ledger only | After the judge, on any runnable artifact |
| Test writer | 1 | Sub-agent | Tests for what was built | After or alongside the judge |

Decision rule: two or more independent builder tasks means an agent team. One builder, or a read-only role such as researcher, judge or adversary, means a sub-agent.

The tier and effort per role are in `docs/build/Build_workflow_cadence.md` under "Model assignment", and the tier-to-model mapping under "Provider mapping". Keep the lead thin, since its job is routing and monitoring rather than reading full files. Delegation has a fixed setup cost, so do not shard a phase into tiny tasks just to parallelize: each dispatched agent should carry a task worth its overhead.

## Agent teams setup

One-time per machine: install tmux (`brew install tmux`). The two settings keys, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and `teammateMode`, are already configured.

Teammate panes only appear when the CLI runs inside a tmux session, so start tmux first, launch inside it, then activate bossman. Navigate panes with `Ctrl-b` then an arrow key.

Preflight, at Step 1:

```
command -v tmux >/dev/null && echo "tmux: ok" || echo "tmux: MISSING"
echo "inside tmux: ${TMUX:+yes}${TMUX:-no}"
```

If tmux is missing or the session is not inside tmux, print the setup steps and let the user fix it before builders dispatch. Do not silently fall back to invisible background sessions: builders still run in parallel without tmux, but the user loses the live pane view that is the point of agent teams.

Which command to launch is a decision, not a default, and it cannot be changed inside a running session. The rule in one line: open a phase on the primary provider, always. Stages 3 and 5, decomposition and premise gate design, are where a bad split or a weak gate cascades into every builder dispatched afterwards. Hand the builder stages to the alternate metered backend afterwards if the budget is tight, and return to the primary for the judge onward. If the primary budget runs out mid-phase, split the phase across sessions rather than switching backend mid-run, and state each session's stop condition when you invoke it, since this skill does not stop at stage boundaries on its own. Re-enter a partially built phase with `--phase N`. This is a rescue path, not a default.

## Multi-agent safety

Worktree isolation is the default for concurrent file-mutating builders, per the 2026-07-21 decision in `DECISIONS.md`, not a fallback after a collision.

| Agent kind | Isolation |
|------------|-----------|
| Builder creating or modifying files, concurrent with another builder | `isolation: "worktree"` |
| Sole builder in a phase, no concurrency | Shared checkout |
| Read-only agents: researchers, judge, adversary, reviewers | Shared checkout, always |

Partition first, isolate second. Worktrees make concurrent writes safe; they do not make an overlapping decomposition correct. Each ticket still names the exact files it may touch. A worktree left standing after a phase closes is leaked state, so the lead removes it at the phase checkpoint.

Beyond the git hygiene `git-workflow` already carries, four conventions bind a teammate:

- Stage files by name. Never `git add -A` or `git add .` across the repository.
- A teammate that encounters files it did not create notes them and continues. It does not clean them up, reformat them, or include them in its commit.
- Do not create, apply or drop `git stash` entries, do not switch branches, and do not create or remove worktrees unless the lead instructs it. Other teammates may be working.
- Formatting-only diffs (lint, whitespace, import order) auto-resolve without asking. Semantic changes to logic, data or behaviour ask first.

## Agent prompt template

For sub-agents (researcher, judge, adversary, test writer, fix agent):

```
You are the [ROLE] on a bossman mode execution team.

Context: [1-3 sentences of what researchers found, not full output]
Plan: [ONLY the relevant phase/task details, not the full plan]
Your task: [specific deliverable]
Constraints: [architectural decisions that apply]
Files to touch: [specific paths, not vague areas]
Files to read: [paths the agent should read itself for full context]

Write findings to [ledger path] the MOMENT you establish one, before you do
anything else with it: before you verify anything, before you continue, before
you compose your report. Your context is not storage. It ends without warning,
and a finding that lives only there is lost when it does.

Do not ask questions. Execute and report back.
If stuck, report the blocker clearly. Do not guess on ambiguous requirements.
```

For teammates, the task is defined in the shared task list and carries: the deliverable, one to three sentences of context, reference file paths to read for patterns, the constraints, the exact files to create, the exact test files to write, and the instruction to mark the task complete when done.

Two rules govern context across the team:

- Fresh context per agent. Every teammate and sub-agent starts with a clean context window, and gets only what it needs pre-injected through its task description. Never pass conversation history or an earlier agent's reasoning.
- Thin orchestrator. When a sub-agent returns or a teammate marks a task complete, capture a one-line summary of what it produced and which files it touched. Do not inline the full result into your own context, and delegate reads to the agent that needs the information.

## Step 10: gates and ship

Run the phase-end chain in full, in order. These grade whether the work is allowed to ship, which is a different question from the judge's, so do not treat them as optional because the judge passed.

1. `verify`: compile check, tests, lint, git status.
2. `eval-harness`: required on any phase touching answer generation, grounding, citations or the trust signal.
3. `dev-standards`: the six-lens production readiness pass. Required on any phase that shipped application code, skippable for docs-only or config-only changes.
4. `python3 tracker/check_learnings_coverage.py N.M`: fails the phase close if any finding reached `confirmed` or `closed` with no matching `LEARNINGS.md` row. A `FAIL` means write the missing entry now and re-run, not skip it.
5. `ship`: docs-sync, commit, push the phase branch, open the PR.
6. `task-tracker --close`: record judge evidence on each ticket, close the board, then run `python3 tracker/render_board.py` explicitly and republish. The explicit render is a backstop: the sync hook fires on Edit and Write only, so a board change made through Bash slips past it.

`release-workflow` is available to invoke directly whenever its end-to-end ritual is wanted. It is not the assumed default: it measured 0 real dispatches of 6 phases through build phase 3.4 while the steps above ran and caught real defects every phase, and by this repository's own `attack-the-constraint` standard an unenforced mandate is an ownerless requirement.

If any gate fails, fix the root cause and restart from step 1 of this chain.

## Step 11: phase checkpoint

Print a checkpoint naming, one line each: the branch, the PR, the board counts including tickets deferred with a reason, the deliverables, the team activity by role, the judge result, the adversary findings count, the review rounds used of two and what round 2 changed, any regression found inside a prior fix with its `Regression of` link, the tests written, each gate's pass or fail with its result line pasted, the scope check against `v1-scope-boundary`, the learnings logged, the decisions taken without asking with the reason for each, the blockers, the context health tier, and the next phase with a recommendation.

Any entry under regressions means the phase escalated rather than closed.

## Step 12: await approval

Do not proceed to the next phase until the user approves and merges the PR and says to continue. They may instead request changes on the same branch, adjust the plan, ask about decisions taken, or exit with `--stop`.

Level 2, unattended overnight execution, is deferred by product-owner decision of 2026-07-26 until it is known to be needed. Do not enable it by inference from a general "keep going": it overrides this step and the standing deny in the `bossman-mode` rule, so it needs an explicit itemized grant.

## Context management

Long sessions degrade as context fills. You cannot read your own token count, so watch output quality instead.

| Tier | Usage | Behaviour |
|------|-------|-----------|
| PEAK | 0-30% | Full operation. Read files freely, inline results |
| GOOD | 30-50% | Normal operation |
| DEGRADING | 50-70% | Economize reads to headers and frontmatter for routing decisions. Summarize sub-agent results in one line. Warn at the next checkpoint |
| CRITICAL | 70%+ | Checkpoint immediately, write progress to a markdown file, and tell the user to start a fresh session |

Degradation signals, any two in one phase meaning DEGRADING regardless of estimated usage: increasing vagueness where file paths belong, skipped protocol steps, repeated phrases or filler, sub-agent prompts getting shorter than earlier dispatches, and summaries that restate rather than synthesize.

Every phase boundary is a context reset point. When DEGRADING or CRITICAL, the checkpoint file becomes the handoff document and carries the plan name and phase number, what was completed with file paths, what remains, the decisions made, and any research context the next session needs.

## The documents a phase builds against

Locked and frozen through the build, edited only at the Plan.md Step 6.2 reconciliation. A builder that thinks one of them is wrong reports it; it does not work around it.

| Document | What it is | Who reads it |
|----------|-----------|--------------|
| `requirements/Technical_specification.md` | The build blueprint. Section 25 defines the 26 build phases | Lead always, builders for their own section |
| `requirements/PRD.md` | The product contract. Its out-of-scope list is a hard boundary | Lead, judge |
| `requirements/Evaluation_playbook.md` | Competency questions, the rubric, the coverage metric | Lead, `eval-harness`, test writer |
| `docs/ncbi/Tool_implementation_mechanics.md` | Per-tool API traps that are expensive to discover late | Any builder wiring a tool |
| `LEARNINGS.md` | What already broke here and what fixed it | Lead at phase start, any builder retrying a failure |

System 1 and System 2 code, for Cypher patterns and AGE schema, is symlinked read-only at `reference/agentic-search-data-engineering`. Read its CLAUDE.md before dispatching agents to explore it.
