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
| `boil-the-lake` | Do it 100%. No half-measures. |
| `writing-style` | Output quality stays high. |
| `git-workflow` | Clean commits. |

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
| Orchestrator (lead) | 1 (main session) | Always active | Decompose phase, create team, track tasks, coordinate. Never builds directly when 2+ tasks exist. | Always |
| Researcher | 1-N | Sub-agent | Fetch docs, read APIs, find examples, explore codebases BEFORE builders start. | Pre-build |
| Planner | 0-N | Sub-agent | Sub-planners for complex areas. Recursive decomposition. | When complexity warrants |
| Builder | 2-N | Agent team (teammates) | Execute independent build tasks in parallel. Each builder owns one task in the shared task list. Runs in its own tmux pane. | After research/planning |
| Judge | 1 | Sub-agent | Single quality gate. Reviews ALL builder output: functional, quality, plan adherence, security. | After all builders complete |
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

After all team members complete, before the phase checkpoint:

1. `release-workflow` (local verification, tests, ship)
2. `ship` (docs-sync agent, commit, push feature branch, create PR)

Skills active during development (enforced by builders):

- `best-practices`: session checklist, scope discipline, code safety
- `decision-logging`: log choices to DECISIONS.md as they happen

Skills active at phase start:

- `best-practices`: session checklist (venv, API keys configured, dev server runs, CLAUDE.md, git status)

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

### File conflict handling

- When a teammate encounters files it did not create or modify, it notes them and continues. It does not clean them up, reformat them, or include them in its commit.
- If two teammates need to modify the same file, use `isolation: "worktree"` for both. The integrator agent wires the results together afterward.
- If a teammate sees unexpected diffs in `git status`, it reports them in its completion summary but does not resolve them.

### Git state protection

- Do not create, apply, or drop `git stash` entries. Other teammates may be working.
- Do not switch branches unless explicitly instructed by the lead.
- Do not run `git pull --rebase --autostash`. Use `git pull --rebase` only when the lead coordinates it.
- Do not create or remove `git worktree` checkouts unless explicitly requested.

### Formatting auto-resolve

- If staged + unstaged diffs are formatting-only (lint, whitespace, import order), auto-resolve without asking.
- If a commit or push was already requested, auto-stage formatting-only follow-ups in the same commit or a tiny follow-up commit. No extra confirmation needed.
- Only ask the user when changes are semantic (logic, data, behavior).

---

## Execution protocol

### Step 1: session start + branch creation

1. Run `best-practices` session checklist (venv, API keys configured, dev server runs, CLAUDE.md, git status)
2. Agent teams preflight: run the tmux check from "Agent teams setup". If tmux is missing or the session is not inside tmux, print the setup steps and let the user fix it before any builder dispatch.
3. Read the phase definition from the plan document
4. Create the feature branch: `git checkout main && git pull origin main && git checkout -b feature/description`

### Step 2: confirm entry and show team

Print:

```
Bossman mode: ON
Plan: [plan name or summary]
Phase: [N.M] - [phase title]
Branch: feature/description
Deliverables: [list what this phase produces]
Estimated scope: [files to create/modify]

Team:
- Lead (orchestrator): main session
- Researchers: [N] sub-agents for [what needs lookup]
- Sub-planners: [N, or "none - phase is straightforward"]
- Builders: [N] teammates via agent team in tmux panes [task list]
- Judge: 1 sub-agent (post-build)
- Test writer: 1 sub-agent (post-build)
- Integrator: [1 if components need wiring, or "not needed"]

Skills active: best-practices, decision-logging
Skills at phase end: release-workflow -> ship

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
3. Define tasks in the shared task list with: deliverable, context, reference files, constraints, test files to write
4. Teammates claim tasks and execute independently
5. Lead monitors the task list and messages stuck teammates
6. If a teammate is stuck: message it with a clearer prompt or ask it to start fresh
7. When all tasks are marked complete, disband the team

For phases with 1 builder task: use a sub-agent instead.

### Step 6: judge + tests + integration

Once all builders complete:

1. Dispatch judge sub-agent to review ALL builder output (functional correctness, code quality, plan adherence, security)
2. Dispatch test writer sub-agent (can run in parallel with judge if test targets are clear)
3. Dispatch integrator sub-agent ONLY if builders produced isolated components that need wiring
4. If judge fails: minor issues = dispatch a fix sub-agent. Major issues = escalate to user.

### Step 7: skill chain (release-workflow -> ship)

After judge passes and tests are written:

1. Run `release-workflow`:
   - Local verification (run the affected code path end-to-end)
   - Run `pytest -q` (all tests pass)
   - Run `ship` (docs-sync, commit, push feature branch, create PR)
2. If release-workflow fails: fix root cause, restart from step 1 of release-workflow

### Step 8: phase checkpoint

When the phase is complete (all agents done, judge passed, PR created), print:

```
Phase [N.M] complete.

Branch: feature/description
PR: [URL or "created, awaiting review"]

What was done:
- [deliverable 1]
- [deliverable 2]
- [deliverable 3]

Team activity:
- Researchers: [N] sub-agents dispatched, [summary of findings]
- Builders: [N] teammates in agent team, [N] succeeded, [N] needed retry
- Judge result: [pass/fail with details]
- Tests written: [count and location]
- Integration: [done/not needed]

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

Level 1 (now): Single-phase execution with agent teams for builders, sub-agents for other roles. Manual PR approval between phases. Skill chain enforced at phase end (release-workflow -> ship). Branch-per-feature git workflow.

Level 2 (trust building): Judge sub-agent gates phase transitions instead of user PR approval for non-architectural phases. Sub-planners handle recursive decomposition of complex phases. Auto-merge PRs when tests pass and no architecture changes detected.

Level 3 (Cursor-scale): Full autonomous multi-phase execution. Checkpoint files at phase boundaries. Morning summary of everything built, tested, and judged while user was away. Fresh-start pattern: stuck teammates get messaged with clearer prompts rather than debugged in-place.

Level 4 (multi-team): Multiple independent agent teams for separate subsystems (e.g. one team for API routes, one for agent tools, one for UI components running simultaneously). Each team has its own lead running its own research/build/judge cycle. A meta-orchestrator coordinates between teams at phase boundaries.

## Design inspiration

Architecture inspired by Cursor's [Scaling long-running autonomous coding](https://cursor.com/blog/scaling-agents) post: strict planner/worker separation, single judge over multiple QA roles, workers that don't coordinate with each other, recursive sub-planning, and the principle that simpler systems outperform complex ones. Adapted for Claude Code's agent teams (experimental) with tmux split-pane display, sub-agents for single-task roles, and a fixed skill chain (release-workflow -> ship) at phase boundaries.
