---
name: bossman-mode
description: Full autonomous execution mode for building System 3 search agent + UI. Activates after architecture/plan is agreed. Claude executes phases independently, stops only at phase boundaries or blockers. TRIGGER when user says "bossman mode", "boss man mode", "let's execute", "go build this", or "run the phase". DO NOT TRIGGER during architecture/planning discussions.
argument-hint: "[--phase N] [--status] [--stop]"
---

# Bossman mode

Autonomous execution mode. You have a plan. Now execute it without asking questions.

## Invocation

```
/bossman                    # Activate bossman mode (requires existing plan)
/bossman --phase 2          # Execute a specific phase
/bossman --status           # Show current phase progress
/bossman --stop             # Exit bossman mode, return to normal collaboration
```

---

## Activation checklist

Before entering bossman mode, verify all three:

1. Plan exists - there is a written plan with numbered phases (in conversation, a plan tool, or a markdown file)
2. Architecture agreed - user has explicitly approved the architecture/approach
3. Phase scope is clear - the current phase has defined deliverables

If any of these are missing, say: "We need [missing item] before entering bossman mode. Let's nail that down first."

---

## Behavioral overrides (active while in bossman mode)

These rules are suspended during bossman mode execution:

| Rule | Why suspended |
|------|--------------|
| `pause-before-acting` | Plan is already agreed. No need to pause and re-check. |
| `preserve-your-thinking` | Decisions are made. This is execution, not deliberation. |
| `clarify-before-drafting` | Scope is defined. No Socratic questioning mid-build. |

These rules remain active:

| Rule | Why kept |
|------|---------|
| `file-protection` | Never delete without informing, even in execution mode. |
| `dependency-tracking` | Track what you build. |
| `parallel-first` | Maximize execution speed. |
| `plan-then-fan-out` | The lead plans and decomposes, cheaper models execute the bounded pieces. |
| `boil-the-lake` | Do it 100%. No half-measures. |
| `writing-style` | Output quality stays high. |
| `git-workflow` | Clean commits, phase branches. |
| `v1-scope-boundary` | Autonomy is exactly when scope creep happens. This binds hardest here, not least. |
| `tool-call-budgets` | A tool without its declared timeout is not finished. |
| `production-standards` | Every security, schema, and grounding gate holds. Speed is never a reason to skip one. |
| `ai-security-standards` | Least privilege, prompt-injection defense, no secrets in logs. |

---

## Context management

Long-running bossman sessions degrade as context fills up. Three rules prevent this.

### Context budget tiers

| Tier | Context usage | Behavior |
|------|--------------|----------|
| PEAK | 0-30% | Full operation. Read files freely, inline results, detailed coordination. |
| GOOD | 30-50% | Normal operation. No changes needed. |
| DEGRADING | 50-70% | Economize reads: headers and frontmatter only for routing decisions. Summarize sub-agent results in one line. Warn in next phase checkpoint: "Context at ~X%. Consider fresh session after this phase." |
| CRITICAL | 70%+ | Checkpoint immediately. Write progress to a markdown file (`bossman-checkpoint-phase-N.md` in project root), list what is done, what remains, and decisions made. Tell the user: "Context budget critical. Start a fresh session and resume from checkpoint." |

### Degradation signals

You cannot read your own token count. Watch for these output-quality signals instead:

- Increasing vagueness: "appropriate handling" instead of specific file paths or code
- Skipped protocol steps: missing team dispatch, missing phase checkpoint fields
- Repeated phrases or filler where specifics should be
- Sub-agent prompts getting shorter or less detailed than earlier dispatches
- Summaries that restate rather than synthesize

When 2+ signals appear in the same phase: treat as DEGRADING regardless of estimated usage.

### Phase boundary = context reset point

At every phase boundary (Step 6: phase checkpoint), explicitly assess context health. If DEGRADING or CRITICAL, the checkpoint file becomes the handoff document for a fresh session. Include in the checkpoint:

1. Plan name and current phase number
2. What was completed (with file paths)
3. What remains (next phase details)
4. Decisions made (from the decisions log)
5. Any research context the next session will need

---

## Execution team

Inspired by Cursor's [Scaling long-running autonomous coding](https://cursor.com/blog/scaling-agents) architecture: strict separation between planning and execution, parallel workers, a single judge for quality gating, and simpler systems over complex ones.

Bossman mode runs as a team, not a solo operator. The orchestrator (main session) decomposes, dispatches, and coordinates. Agents execute.

### Dispatch mode: agent teams (primary) vs sub-agents (fallback)

Bossman uses two dispatch mechanisms. Agent teams are the primary mode. Sub-agents are the fallback when teams are unavailable or overkill.

| Mechanism | When to use | How it works |
|-----------|-------------|--------------|
| Agent teams | 2+ parallel builders in a phase | Orchestrator creates a team. Each builder becomes a teammate in its own tmux pane. Teammates share a task list, claim work independently, and can message each other. |
| Sub-agents (Agent tool) | Single-task roles (researcher, judge, test writer), simple phases with 1 builder | Orchestrator dispatches via Agent tool. Sub-agent runs, reports back, context is discarded. No inter-agent communication. |

Decision rule: if the phase has 2+ independent builder tasks, use agent teams. If the phase has only 1 builder or the role is read-only (researcher, judge), use sub-agents.

### Agent teams setup

One-time setup (per machine):

1. Install tmux: `brew install tmux`
2. Confirm two keys in `~/.claude/settings.json`: `"env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }` and `"teammateMode": "tmux"`.

Both settings keys are already configured. Installing tmux is the only per-machine step.

Launch requirement: teammate panes only appear when Claude Code is running inside a tmux session. Start tmux first, then launch Claude inside it, then activate bossman:

```
tmux        # start a tmux session
claude      # launch Claude Code inside it
/bossman    # activate bossman from inside that session
```

Navigate panes with `Ctrl-b` then an arrow key.

Preflight (run this at Step 1, before dispatching any team):

```
command -v tmux >/dev/null && echo "tmux: ok" || echo "tmux: MISSING"
echo "inside tmux: ${TMUX:+yes}${TMUX:-no}"
```

If tmux is missing or the session is not inside tmux, print the setup steps to the user and let them fix it before builders dispatch. Do not silently fall back to invisible background sessions: without tmux, builders still run in parallel, but the user loses the live pane view that is the whole point of agent teams.

Display: tmux split panes. Each teammate gets its own pane. The orchestrator (lead) stays in the main pane and monitors progress via the shared task list.

To create a team, the orchestrator asks Claude Code to spawn teammates:

```
Create an agent team for Phase [N]:
- Teammate "builder-api-routes": build FastAPI routes and schemas
- Teammate "builder-agent-tools": build LangGraph tool definitions
- Teammate "builder-ui-components": build React components
Use Sonnet for each teammate. Require plan approval before they start coding.
```

Each teammate receives its task via the shared task list. The lead monitors progress. When all builders complete, the lead dispatches the judge and test writer (as sub-agents, since those are sequential single-task roles).

### Team roles

| Role | Count | Dispatch mode | Responsibility | When dispatched |
|------|-------|---------------|---------------|-----------------|
| Product owner | 1 (human) | Not dispatched | Approves the PR, decides scope, judges whether a UI actually feels right. Coordinates only with the lead, never with a builder. | At phase boundaries, and during any phase marked product owner required |
| Orchestrator (lead) | 1 (main session) | Always active | Decompose phase, create team, track tasks, coordinate, own the board. Never builds directly when 2+ tasks exist. | Always |
| Researcher | 1-N | Sub-agent | Fetch docs, read APIs, find examples, explore codebases BEFORE builders start. | Pre-build |
| Planner | 0-N | Sub-agent | Sub-planners for complex areas. Recursive decomposition. | When complexity warrants |
| Builder | 2-N | Agent team (teammates) | Execute independent build tasks in parallel. Each builder owns one task in the shared task list. Runs in its own tmux pane. | After research/planning |
| Judge | 1 | Sub-agent | Single quality gate. Reviews ALL builder output: functional, quality, plan adherence, security. | After all builders complete |
| Adversary | 0-1 | Sub-agent | Use the running artifact in hostile, unscripted ways to find what scripted checks miss. Over-reports on purpose. Files findings to a shared ledger only, never fixes, triages, or closes them. | After the judge, on any phase with a runnable artifact |
| Test writer | 1 | Sub-agent | Write tests for what was built. Unit, integration, smoke tests. | After or alongside judge |
| Integrator | 0-1 | Sub-agent | Wire independently-built components together. Only when builders produced isolated pieces. | Only when components need wiring |

### Key design principles (from [Cursor scaling agents](https://cursor.com/blog/scaling-agents))

1. Simpler beats complex. The judge is one agent, not three.
2. Workers don't coordinate with each other. Each builder gets a task and grinds independently. The orchestrator (lead) handles coordination via the shared task list.
3. Planning is recursive. Complex phases get sub-planners in parallel.
4. Fresh starts combat drift. If a builder teammate is stuck or going in circles, the lead can message it with a clearer prompt or ask it to start over.
5. The integrator is conditional. Skip when builders produce self-contained deliverables.
6. Thin orchestrator. The lead's job is routing and monitoring, not reading full file contents. Delegate reads to the agent that needs the information.
7. Fresh context per agent. Every teammate starts with a clean context window. Pre-inject only what it needs via the task description.

### Model tiering (build-time cost lever)

This is the model choice for the build TEAM, set when you dispatch each agent. It is separate from the product's Guard, Plan, and Synth runtime harness in CLAUDE.md, which routes models per query at serve time. Do not conflate the two: this table tiers the agents that write System 3, not the tiers System 3 uses to answer a user.

Assign a model tier per role, not one model for the whole team. Keep the lead thin (routing and monitoring, not reading full files), so its model choice barely matters, then push the strongest model to where judgment is hard and a cheaper model to where the work is well-scoped or bulk.

| Role | Model tier | Effort | Why |
|------|-----------|--------|-----|
| Lead (main session) | User's session model | n/a | Fixed by the user. Keep it thin. |
| Researcher / reader | Cheap or mid | low | Bulk document and API reading. The cost is the input, not the reasoning. |
| Builder (teammate) | Sonnet | medium | Well-scoped construction against a clear task. Reserve high effort for genuinely hard builds. |
| Judge | Strongest | high or xhigh | Single quality gate. A missed defect here is the most expensive, so pay for the reasoning. |
| Sub-planner | Strongest | high | Decomposition errors cascade into every downstream builder. |

Pass the model and effort choice when you dispatch each sub-agent, and set the teammate model when you create the agent team (the team creation step already says to use Sonnet for each teammate). A tool-less coordinator that delegates heavy reading to cheap scoped workers measured 2.5x cheaper and roughly 3x faster than one frontier model doing everything, with about 84 percent of input tokens billed at the cheap worker rate (the plan-big-execute-small pattern from the claude-cookbooks dive, in the personal-os Reference-repos set). Delegation has a fixed setup cost, so do not shard a phase into many tiny tasks just to parallelize. Each dispatched agent should carry a task worth its overhead.

### The judge produces evidence, not a verdict

A judge that reports "looks good, all checks pass" without showing its work is the maker-checker failure `self-eval-loop.md` warns about: a grader that knows the rubric drifts toward approving everything. Force the judge to produce evidence, and default it to fail when evidence is absent.

For every claim, the judge's report must:
- Cite the exact `file:line` for a code finding, not "the agent loop looks fine".
- Paste the actual command output for a functional or test claim (the `pytest -q` result line, the lint output), not "tests pass".
- Quote the specific offending line for a security or quality finding, not "no security issues found". Grade against the `production-standards` and `ai-security-standards` gates: parameterized Cypher and SQL, schema validation at every agent-loop hop, cite-or-refuse on generated answers, no secrets in logs.

If the judge cannot produce evidence for a check, that check fails. "I could not verify X" is a fail, never a pass.

Verify the premise, not only the leaves. The judge's default instinct is to check each artifact against its assigned task: did builder 3 produce the file it was told to. That is leaf verification, and it passes even when the decomposition itself was wrong. Add one level up: does the set of completed tasks actually satisfy the phase done-when from the goal contract? A phase where every builder succeeded at its own task but the tasks together miss the phase's stated outcome is a failed phase, not a passed one (the plan-big-execute-small park-list failure, `goal-contracts.md`, "rigor about the wrong layer").

### The adversary attacks what the judge certifies

The judge is scripted verification. It checks the artifact against the plan, the tests, and the `production-standards` and `ai-security-standards` gates, so it catches the failures someone thought to specify. It is blind to the failure nobody wrote a check for. For System 3 that blind spot is the dangerous one: the failure mode here is a fluent wrong answer, not a failed assertion, and a green judge verdict does not touch it.

The adversary is the unscripted half. It uses the running system in hostile ways the spec never imagined: malformed and boundary input, out-of-order operations, edge cases, and above all queries engineered to draw a confident wrong answer, especially queries where the graph returns nothing and the system should refuse rather than answer from priors. It is the pressure the cite-or-refuse gate needs before it is trusted: does the system actually refuse, or does it fabricate a fluent, uncited, biomedically plausible answer? It over-reports on purpose, because for a biomedical user a false alarm is cheap and a missed wrong answer is not. It files every finding to a shared ledger and stops there. It never fixes, triages, or closes its own findings; the judge or a fix agent triages them, and only the ledger's designated closer closes them. This is the maker-cannot-sign-off split of `self-eval-loop.md` applied to verification itself: the finder is never the closer.

Run the adversary after the judge, only on a phase that produced a runnable artifact. A green judge verdict is necessary but not sufficient; the adversary is what decides whether the answer path is actually trustworthy. Source: the Personal Space autonomous build harness, analyzed in the personal-os Reference-repos set, which pairs a scripted qa role with a separate unscripted adversary.

### Team dispatch order

```
Phase start
  |-- Researchers (sub-agents, parallel) --- gather context, docs, examples
  |-- Sub-planners (sub-agents, if needed) --- decompose complex sub-areas
  |
  |-- [research + planning complete]
  |
  |-- Create agent team --- spawn builder teammates in tmux panes
  |-- Builders (teammates, parallel) --- each claims a task, executes independently
  |-- Lead monitors --- watches task list, messages stuck teammates
  |
  |-- [all builders complete, team disbanded]
  |
  |-- Judge (sub-agent) --- single quality gate (pass/fail + details)
  |-- Adversary (sub-agent, only on a runnable artifact) --- hostile unscripted use, files to the ledger
  |-- Test writer (sub-agent, parallel with judge if targets clear)
  |-- Integrator (sub-agent, only if components need wiring)
  |
  |-- [judge passed, tests written, integration done]
  |
  |-- Skill chain --- release-workflow -> ship
  |
  +-- Phase checkpoint --- report to user
```

### Skill chain (every phase, no exceptions)

At phase start:

- `learnings --brief N.M`: read what already broke in this territory, before scoping anything
- `task-tracker --open N.M`: decompose the phase into tickets with acceptance criteria
- `best-practices`: session checklist (venv, API keys configured, dev server runs, CLAUDE.md, git status)

During development, enforced by builders:

- `best-practices`: scope discipline, code safety
- `decision-logging`: log choices to DECISIONS.md as they happen
- `learnings`: append the moment something breaks, never batched to the end

After all team members complete, before the phase checkpoint:

1. `verify`: compile check, tests, lint, git status. The pre-commit gate.
2. `eval-harness`: required on any phase that touches answer generation, grounding, citations, or the trust signal. It grades cite-or-refuse and citation coverage against the playbook. A phase that changes how answers are produced does not ship without it.
3. `dev-standards`: the six-lens production readiness pass. Required on any phase that shipped application code, skippable for docs-only or config-only changes.
4. `release-workflow`: local end-to-end verification and the security scan gate.
5. `ship`: docs-sync, commit, push the phase branch, create the PR.
6. `task-tracker --close`: record judge evidence on each ticket, close the phase board, then run `python3 tracker/render_board.py` explicitly and republish the artifact.

The explicit render at step 6 is a backstop, not a duplicate. `.claude/hooks/sync-board.sh` already regenerates the page on every Edit to a board file, but PostToolUse hooks fire on the Edit and Write tools only, so any change made through Bash slips past it. Re-rendering at phase close catches a bypassed hook inside the phase instead of leaving the product owner reading a stale board. The renderer is idempotent, so running it when nothing changed costs nothing.

Steps 1 through 3 are the gates the locked spec actually requires and that this skill previously never invoked. Do not treat them as optional because the judge already passed. The judge grades the work; these grade whether the work is allowed to ship.

### Agent prompt template

For sub-agents (researcher, judge, test writer, integrator):

```
You are the [ROLE] on a bossman mode execution team.

Context: [1-3 sentences of what researchers found, not full output]
Plan: [paste ONLY the relevant phase/task details, not the full plan]
Your task: [specific deliverable]
Constraints: [architectural decisions that apply]
Files to touch: [specific paths, not vague areas]
Files to read: [paths the agent should read itself for full context]

Do not ask questions. Execute and report back.
If stuck, report the blocker clearly. Do not guess on ambiguous requirements.
```

For agent team teammates (builders), the task is defined in the shared task list. The lead provides:

```
Task: [specific deliverable, e.g. "Build the graph query tool with Cypher generation"]
Context: [1-3 sentences from research]
Reference: [file paths to read for patterns, e.g. "reference/agentic-search-data-engineering/..."]
Constraints: [provenance required, read-only graph access, type hints on all public functions]
Files to create: [exact paths]
Tests to write: [exact test file paths]
When done: mark task complete in the task list.
```

Orchestrator rule: when a sub-agent returns or a teammate marks a task complete, capture a one-line summary of what it produced and which files it touched. Do not inline the full result into your context.

### The documents a phase builds against

Every phase reads from these. They are locked and frozen through the build, edited only at the Plan.md Step 6.2 reconciliation. A builder that thinks one of them is wrong reports it; it does not work around it.

| Document | What it is | Who reads it |
|----------|-----------|--------------|
| `requirements/Technical_specification.md` | The build blueprint. 25 sections, seven tools, six delivery surfaces. Section 25 defines the 26 build phases | Lead always, builders for their own tool or surface section |
| `requirements/PRD.md` | The product contract. Every requirement traces to an outcome here, and its out-of-scope list is a hard boundary | Lead, judge |
| `requirements/Evaluation_playbook.md` | The living evaluation contract. Competency questions, the rubric, the coverage metric, the feedback loop | Lead, `eval-harness`, test writer |
| `docs/ncbi/Tool_implementation_mechanics.md` | Per-tool API traps that are expensive to discover late | Any builder wiring a tool |
| `LEARNINGS.md` | What already broke here and what fixed it | Lead at phase start, any builder retrying a failure |

### Reference repos

Read the reference repo's CLAUDE.md before dispatching agents to explore it.

| Repo | Symlink path | What it is |
|------|-------------|------------|
| agentic-search-data-engineering | `reference/agentic-search-data-engineering` | System 1+2 code: Cypher patterns, AGE schema, graph structure for query generation |

---

## Multi-agent safety

When 3+ builder teammates run in parallel (agent teams or worktrees), these conventions prevent agents from corrupting each other's work.

### Scoped commits

- Each builder commits only its own changes. Never `git add -A` or `git add .` across the full repo.
- Stage files by name: `git add path/to/file1.py path/to/file2.py`.
- When the user says "commit all," the lead groups changes into logical commits, not one giant commit.

### Worktree isolation, the default for file-mutating builders

Per the 2026-07-21 decision in DECISIONS.md, concurrent file-mutating builders run in their own git worktree. This is the default policy, not a fallback after a collision.

| Agent kind | Isolation | Why |
|------------|-----------|-----|
| Builder that creates or modifies files, running concurrently with another builder | `isolation: "worktree"` | Two agents writing the same tree corrupt each other. Isolation is cheaper than reconstructing what happened |
| Sole builder in a phase, no concurrency | Shared checkout | Nothing to collide with, and a worktree costs setup time and disk for no benefit |
| Read-only agents: researchers, judge, adversary, reviewers | Shared checkout, always | They write nothing, so they cannot collide. A worktree for a reader is pure overhead |

Teardown: a worktree is removed after its work merges back. A worktree left standing after a phase closes is leaked state. The lead removes it as part of the phase checkpoint, and an unchanged worktree is auto-removed.

Partition first, isolate second. Worktrees make concurrent writes safe, they do not make an overlapping decomposition correct. Each ticket still names the exact files it may touch, so two builders should not have been aiming at the same file in the first place.

### File conflict handling

- When a teammate encounters files it did not create or modify, it notes them and continues. It does not clean them up, reformat them, or include them in its commit.
- If a teammate sees unexpected diffs in `git status`, it reports them in its completion summary but does not resolve them.
- The integrator agent wires results together after isolated builders finish.

### Git state protection

- Do not create, apply, or drop `git stash` entries. Other teammates may be working.
- Do not switch branches unless explicitly instructed by the lead.
- Do not run `git pull --rebase --autostash`. Use `git pull --rebase` only when the lead coordinates it.
- Do not create or remove `git worktree` checkouts unless explicitly requested.

### Formatting auto-resolve

- If staged + unstaged diffs are formatting-only (lint, whitespace, import order), auto-resolve without asking.
- If a commit or push was already requested, auto-stage formatting-only follow-ups in the same commit or a tiny follow-up commit. No extra confirmation needed.
- Only ask the user when changes are semantic (logic, data, behavior).

### Shared-ledger coordination

When parallel agents share findings, defects, or task state, they coordinate through one shared markdown ledger, not by each writing wherever they like. Without a convention, two agents writing status to the same file overwrite each other, and an agent that raised an item can quietly close it. A single-writer-per-state ledger removes both races by construction and leaves an auditable trail. The Personal Space harness, analyzed in the personal-os Reference-repos set, runs its defect and adversarial-review ledgers this way.

The ledger is a real file, not an abstraction: `tracker/phase_N.M.md`, the same phase file the tickets live in, under its Findings section. Adversary findings and builder defects both land there. Keeping findings beside tickets in one file is deliberate, since a confirmed finding usually becomes a fix ticket, and that transition should not cross a file boundary. The `task-tracker` skill owns the format. Four rules:

- Single writer per state: each state in the ledger has exactly one role authorized to set it. The adversary files findings, the judge or a fix agent triages, only the designated closer closes. No state has two writers.
- Mandatory reason on judgment states: any state that reflects a judgment call (accepted, rejected, closed, disputed) carries a one-line reason. A bare status change with no reason is invalid.
- Append-only history line per transition: every transition appends a who-what-why line to the item's history. History is never rewritten, only extended, so the trail reconstructs the full life of the item.
- The raiser never closes: the party that raised an item is never the party that closes it. The finder reports, a different role verifies and closes. This is the same finder-is-not-closer rule the adversary follows.

---

## Execution protocol

### Step 1: session start + branch creation

1. Run `best-practices` session checklist (venv, API keys configured, dev server runs, CLAUDE.md, git status)
2. Agent teams preflight: run the tmux check from "Agent teams setup". If tmux is missing or the session is not inside tmux, print the setup steps and let the user fix it before any builder dispatch.
3. Read the phase definition from `requirements/Technical_specification.md` Section 25. That section is the single source of truth for the 26 numbered build phases: what each delivers, what it depends on, and its branch name. Never invent a phase or reorder the sequence.
4. Verify every dependency phase in Section 25's dependency graph is already merged. If one is not, stop and report. Do not build on an unmerged dependency.
5. Read `LEARNINGS.md` filtered to this phase, its tools, and its layers (`learnings --brief N.M`). Past dead ends are cheaper to read than to rediscover.
6. Open the phase board with `task-tracker --open N.M`. Decompose the phase into tickets with acceptance criteria traced to spec sections before dispatching anyone.
7. Create the phase branch, using the exact branch name from Section 25's table: `git checkout main && git pull origin main && git checkout -b phase/N.M-description`

### Step 2: confirm entry and show team

Print:

```
Bossman mode: ON
Plan: [plan name or summary]
Phase: [N.M] - [phase title]  (tech spec Section 25)
Branch: phase/N.M-description
Board: tracker/phase_N.M.md  ([N] tickets)
Deliverables: [list what this phase produces]
Estimated scope: [files to create/modify]
Product owner required: [yes, and why / no]

Learnings read: [N] entries tagged to this phase, or "none recorded yet"

Team:
- Lead (orchestrator): main session
- Researchers: [N] sub-agents for [what needs lookup]
- Sub-planners: [N, or "none - phase is straightforward"]
- Builders: [N] teammates via agent team in tmux panes [task list]
- Worktree isolation: [which builders, or "none - no overlapping writes"]
- Judge: 1 sub-agent (post-build)
- Adversary: [1 sub-agent if the phase produces a runnable artifact, or "not needed"]
- Test writer: 1 sub-agent (post-build)
- Integrator: [1 if components need wiring, or "not needed"]

Skills active: best-practices, decision-logging, learnings
Skills at phase end: verify -> [eval-harness] -> [dev-standards] -> release-workflow -> ship -> task-tracker

Dispatching now. Next check-in at phase completion.
```

### Step 3: research (if needed)

- Dispatch researcher sub-agents in parallel for unfamiliar APIs, libraries, codebases
- Researchers report back with context that builders will need
- Skip if sufficient context from prior phases or planning stage

### Step 4: sub-planning (if needed)

- For complex phases, dispatch sub-planner sub-agents to decompose specific areas
- Sub-planners run in parallel, each producing a task list
- Orchestrator merges sub-plans into the builder dispatch
- Skip for straightforward phases

### Step 5: dispatch builders (agent team)

For phases with 2+ parallel builder tasks:

1. Create an agent team with one teammate per builder task
2. Each teammate appears in its own tmux pane
3. Give every concurrent file-mutating builder `isolation: "worktree"`, per the worktree policy above
4. Define tasks from the phase board tickets: deliverable, acceptance criteria, context, reference files, constraints, the exact files it may touch, test files to write
5. Teammates claim tickets and execute independently, setting their own ticket to `in-progress` the moment they pick it up, not when they finish. The board is the team's shared reference, so a ticket that is being worked and still reads `todo` is a lie about the state of the phase. Use the Edit tool for board changes, never `sed`, or the page will not re-render
6. Lead monitors the board and messages stuck teammates
7. If a teammate is stuck: message it with a clearer prompt or ask it to start fresh
8. A builder that finishes sets its ticket to `in-review`, never to `done`
9. When all tickets are `in-review`, disband the team and tear down the worktrees

For phases with 1 builder task: use a sub-agent in the shared checkout instead.

### Step 6: judge + tests + integration

Once all builders complete:

1. Dispatch judge sub-agent to review ALL builder output (functional correctness, code quality, plan adherence, security). Give it the strongest model at high effort. It must produce cited evidence for every claim and verify the phase premise, not just each artifact (see "The judge produces evidence, not a verdict")
2. On any phase that produced a runnable artifact, dispatch an adversary sub-agent (see the adversary role and "The adversary attacks what the judge certifies"). It throws hostile, unscripted queries at the running system, over-reports on purpose, and files every finding to a shared-ledger file. It targets the cite-or-refuse gate: queries where the graph returns nothing and the system must refuse rather than fabricate. It never fixes, triages, or closes its own findings; the judge or a fix agent triages them, and only the ledger's designated closer closes them.
3. Dispatch test writer sub-agent (can run in parallel with judge if test targets are clear)
4. Dispatch integrator sub-agent ONLY if builders produced isolated components that need wiring
5. Scope check: verify nothing built in this phase crosses the v1 boundary in `.claude/rules/v1-scope-boundary.md`. A capability the PRD declared out of scope does not become in scope because a builder found it easy. This check matters most when no human watched the phase.
6. UI phases: a phase that ships user-facing interface does not pass on a judge's code review alone. It needs a Playwright run proving the flow works in a browser, and it is marked product owner required so a human decides whether it actually feels right. An agent can verify a button exists. It cannot verify the thing is good.
7. The judge closes the board. It is the only role allowed to move a ticket from `in-review` to `done`, and the only one allowed to set `rejected`, each with a one-line reason and its evidence pasted into the ticket. A builder never closes its own ticket. If the judge does not touch the board, the phase does not close, because nothing else is permitted to write that state.
8. If judge fails or the adversary files findings: minor issues = dispatch a fix sub-agent. Major issues = escalate to the product owner.
9. Anything that cost real time to diagnose gets a `LEARNINGS.md` entry before the phase closes: what broke, what was tried and did not work, and what actually fixed it. A confirmed adversary finding always qualifies. This is the one place a phase is allowed to end without a learning, and only when genuinely nothing broke.

### Step 7: skill chain (release-workflow -> ship)

After judge passes and tests are written:

1. Run `release-workflow`:
   - Local verification (run the affected code path end-to-end)
   - Run `pytest -q` (all tests pass)
   - Run `ship` (docs-sync, commit, push the phase branch, create PR)
2. If release-workflow fails: fix root cause, restart from step 1 of release-workflow

### Step 8: phase checkpoint

When the phase is complete (all agents done, judge passed, PR created), print:

```
Phase [N.M] complete.

Branch: phase/N.M-description
PR: [URL or "created, awaiting review"]
Board: [N] tickets done, [N] deferred with reason

What was done:
- [deliverable 1]
- [deliverable 2]
- [deliverable 3]

Team activity:
- Researchers: [N] sub-agents dispatched, [summary of findings]
- Builders: [N] teammates in agent team, [N] succeeded, [N] needed retry
- Judge result: [pass/fail with details]
- Adversary findings: [N filed to ledger, or "not run - no runnable artifact"]
- Tests written: [count and location]
- Integration: [done/not needed]

Gates:
- verify: [pass/fail, paste the result line]
- eval-harness: [pass/fail with the metric, or "not applicable - phase does not touch answer generation"]
- dev-standards: [pass/fail, or "not applicable - no application code"]
- Scope check: [no v1-scope-boundary violations, or list them]

Learnings logged this phase: [N entries, or "none - nothing broke"]

Decisions made (without asking):
- [decision 1]: chose X over Y because [reason]
- [decision 2]: chose A over B because [reason]

Blockers: [none, or list]

Context health: [PEAK / GOOD / DEGRADING / CRITICAL]
[If DEGRADING: "Checkpoint file written. Recommend fresh session for next phase."]
[If CRITICAL: "Checkpoint file written. Fresh session required."]

Next phase: [N+1] - [title]
Recommendation: [proceed / adjust plan / stop and discuss / fresh session recommended]

Waiting for your go. Merge the PR then say "next" to start the next phase.
```

### Step 9: await approval

Do NOT proceed to the next phase until:

1. The user approves and merges the PR
2. The user says "go", "next", or similar

The user may:

- Review the PR and request changes (fix on the same branch, re-push)
- Adjust the plan based on what they see
- Ask questions about decisions made
- Exit bossman mode with `/bossman --stop`

---

## Stop conditions (exit bossman mode immediately)

1. Architecture-level change needed - something in the plan is fundamentally wrong
2. Blocker with no reasonable workaround - missing credentials, broken dependency, ambiguous requirement that could go either way with major consequences
3. Phase complete - normal checkpoint
4. User says stop - `/bossman --stop` or any clear signal to pause

---

## Status check

If invoked with `--status`, print current state:

```
Bossman mode: [ON/OFF]
Current phase: [N] - [title]
Progress: [what's done so far in this phase]
Decisions made: [list]
Blockers: [none or list]
```

---

## Growth path

Level 1 (now): Single-phase execution with agent teams for builders, sub-agents for other roles. Manual PR approval between phases. Full skill chain enforced at phase end. Phase-branch git workflow with worktree isolation for concurrent writers.

Level 2 (unattended overnight, deferred): the product owner deferred this on 2026-07-26 until we know whether it is actually needed. Do not enable it by inference from a general "keep going". It requires an explicit, itemized grant, because it overrides this skill's own Step 9 and the `bossman-mode` rule's standing deny on proceeding without approval.

When it is enabled, the shape is decided: fan out where Section 25's dependency graph allows, stack only where phase N literally needs phase N-1's code. Independent phases each get their own branch off main and their own PR, so a morning review is parallel rather than a chain, and rejecting one does not contaminate the others. Nothing merges to main unreviewed. Merging overnight buys no throughput anyway, since a dependent phase builds on the previous branch either way, so autonomy would only remove the review gate, not speed anything up.

Level 3 (Cursor-scale): Full autonomous multi-phase execution. Checkpoint files at phase boundaries. Morning summary of everything built, tested, and judged while the product owner was away. Fresh-start pattern: stuck teammates get messaged with clearer prompts rather than debugged in-place.

Level 4 (multi-team): Multiple independent agent teams for separate subsystems (e.g. one team for API routes, one for agent tools, one for UI components running simultaneously). Each team has its own lead running its own research/build/judge cycle. A meta-orchestrator coordinates between teams at phase boundaries.

## Design inspiration

Architecture inspired by Cursor's [Scaling long-running autonomous coding](https://cursor.com/blog/scaling-agents) post: strict planner/worker separation, single judge over multiple QA roles, workers that don't coordinate with each other, recursive sub-planning, and the principle that simpler systems outperform complex ones. Adapted for Claude Code's agent teams (experimental) with tmux split-pane display, sub-agents for single-task roles, and a fixed skill chain (release-workflow -> ship) at phase boundaries.
