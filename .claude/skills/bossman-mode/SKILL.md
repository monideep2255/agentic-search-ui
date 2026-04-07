---
name: bossman-mode
description: Full autonomous execution mode for building products. Activates after architecture/plan is agreed. Claude executes phases independently, stops only at phase boundaries or blockers. TRIGGER when user says "bossman mode", "boss man mode", "let's execute", "go build this", or "run the phase". DO NOT TRIGGER during architecture/planning discussions.
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

1. **Plan exists** - there is a written plan with numbered phases (in conversation, a plan tool, or a markdown file)
2. **Architecture agreed** - user has explicitly approved the architecture/approach
3. **Phase scope is clear** - the current phase has defined deliverables

If any of these are missing, say: "We need [missing item] before entering bossman mode. Let's nail that down first."

---

## Behavioral overrides (active while in bossman mode)

These rules are **suspended** during bossman mode execution:

| Rule | Why suspended |
|------|--------------|
| `pause-before-acting` | Plan is already agreed. No need to pause and re-check. |
| `preserve-your-thinking` | Decisions are made. This is execution, not deliberation. |
| `clarify-before-drafting` | Scope is defined. No Socratic questioning mid-build. |

These rules **remain active**:

| Rule | Why kept |
|------|---------|
| `file-protection` | Never delete without informing, even in execution mode. |
| `dependency-tracking` | Track what you build. |
| `parallel-first` | Maximize execution speed. |
| `boil-the-lake` | Do it 100%. No half-measures. |
| `writing-style` | Output quality stays high. |
| `git-workflow` | Clean commits. |
| `check-depended-by` | System integrity. |

---

## Execution team

Inspired by Cursor's [Scaling long-running autonomous coding](https://cursor.com/blog/scaling-agents) architecture: strict separation between planning and execution, parallel workers, a single judge for quality gating, and simpler systems over complex ones.

Bossman mode runs as a team, not a solo operator. The orchestrator (main session) decomposes, dispatches, and coordinates. Agents execute.

### Team roles

| Role | Count | Responsibility | Tool access | When dispatched |
|------|-------|---------------|-------------|-----------------|
| **Orchestrator** | 1 (main session) | Decompose phase into tasks, dispatch agents, track progress, report to user. Never builds directly when 2+ tasks exist. | All tools | Always active |
| **Researcher** | 1-N | Fetch docs, read APIs, find examples, explore unfamiliar codebases BEFORE builders start. Uses web-research skill, context7 MCP, repo-dive. | Read-only: Read, Grep, Glob, WebFetch, WebSearch, MCP tools | Pre-build: runs first to give builders context |
| **Planner** | 0-N | Sub-planners for complex areas. Spawned by orchestrator when a phase has sub-areas that need their own task decomposition. Planning is recursive and parallel. | Read-only: Read, Grep, Glob, Bash (read commands) | When phase complexity warrants it |
| **Builder** | 1-N | Execute independent build tasks. Write code, create files, run commands. Each builder focuses on one task until done, then reports back. Does not coordinate with other builders. | All tools, isolation: worktree when modifying shared files | Parallel dispatch after research/planning |
| **Judge** | 1 | Single quality gate. Reviews ALL builder output: does it work (functional), is it good (code quality), does it match the plan (completeness), any security issues? Replaces separate QA + reviewer roles. Simpler is better. | Read-only: Read, Grep, Glob, Bash (test/lint commands only) | After all builders complete |
| **Test writer** | 1 | Write tests for what was built. Unit tests, integration tests, smoke tests as appropriate for the project. | All tools | After or alongside judge |
| **Integrator** | 0-1 | Wire independently-built components together. Handle imports, configs, entry points, shared state. Only dispatched when builders produced isolated pieces that need connecting. | All tools | Only when builders worked on separate components that must connect |

### Key design principles (from [Cursor scaling agents](https://cursor.com/blog/scaling-agents))

1. **Simpler beats complex.** Additional oversight roles create fragility, not quality. The judge is one agent, not three.
2. **Workers don't coordinate with each other.** Each builder gets a task and grinds on it independently. The orchestrator handles coordination.
3. **Planning is recursive.** Complex phases get sub-planners that run in parallel, each producing their own task list.
4. **Fresh starts combat drift.** If a builder is stuck or going in circles, kill it and dispatch a new one with a clearer prompt rather than trying to course-correct.
5. **The integrator is conditional.** Cursor found integrators bottleneck at scale. At our scale (3-8 agents), it adds value when components must connect. Skip it when builders produce self-contained deliverables.

### Team dispatch order

```
Phase start
  ├── Researchers (parallel) ─── gather context, docs, examples
  ├── Sub-planners (parallel, if needed) ─── decompose complex sub-areas
  │
  ├── [research + planning complete]
  │
  ├── Builders (parallel) ─── execute tasks independently
  │
  ├── [all builders complete]
  │
  ├── Judge ─── single quality gate (pass/fail + details)
  ├── Test writer (parallel with judge if targets are clear)
  ├── Integrator (only if components need wiring)
  │
  ├── [judge passed, tests written, integration done]
  │
  └── Phase checkpoint ─── report to user
```

### Agent prompt template

When dispatching any team member, include in the prompt:

```
You are the [ROLE] on a bossman mode execution team.

Context: [what researchers found, if applicable]
Plan: [paste relevant phase details]
Your task: [specific deliverable]
Constraints: [architectural decisions that apply]
Files to touch: [specific paths, not vague areas]

Do not ask questions. Execute and report back.
If stuck, report the blocker clearly. Do not guess on ambiguous requirements.
```

---

## Execution protocol

### Step 1: confirm entry and show team

Print:

```
Bossman mode: ON
Plan: [plan name or summary]
Phase: [N] - [phase title]
Deliverables: [list what this phase produces]
Estimated scope: [files to create/modify]

Team:
- Orchestrator: main session
- Researchers: [N] agents for [what needs lookup]
- Sub-planners: [N, or "none - phase is straightforward"]
- Builders: [N] agents for [task list]
- Judge: 1 agent (post-build)
- Test writer: 1 agent (post-build)
- Integrator: [1 if components need wiring, or "not needed"]

Dispatching now. Next check-in at phase completion.
```

### Step 2: research (if needed)

- Dispatch researcher agents in parallel for any unfamiliar APIs, libraries, or codebases
- Researchers report back with context that builders will need
- Skip this step if the team already has sufficient context from prior phases or the planning stage

### Step 3: sub-planning (if needed)

- For complex phases, dispatch sub-planner agents to decompose specific areas
- Sub-planners run in parallel, each producing a task list for their area
- Orchestrator merges sub-plans into the builder dispatch
- Skip for straightforward phases where task decomposition is obvious

### Step 4: dispatch builders

- Dispatch builder agents in parallel (one Agent tool call per task, all in a single message)
- Each builder gets: research context, specific task, file paths, constraints
- Use `isolation: "worktree"` for tasks that touch overlapping files
- Builders do not coordinate with each other. They grind on their task and report back.
- If a builder is stuck or going in circles: kill it and dispatch a fresh one with a clearer prompt
- Use Ralph Loop if available for sustained autonomous execution

### Step 5: judge + tests + integration

Once all builders report back:

1. Dispatch judge agent to review ALL builder output (functional correctness, code quality, plan adherence, security)
2. Dispatch test writer agent (can run in parallel with judge if test targets are clear)
3. Dispatch integrator agent ONLY if builders produced isolated components that need wiring
4. If judge fails the work: triage. Minor issues = dispatch a builder fix agent. Major issues = escalate to user.

### Step 6: phase checkpoint

When the phase is complete (all agents done, judge passed), print:

```
Phase [N] complete.

What was done:
- [deliverable 1]
- [deliverable 2]
- [deliverable 3]

Team activity:
- Researchers: [N] dispatched, [summary of findings]
- Builders: [N] dispatched, [N] succeeded, [N] needed retry
- Judge result: [pass/fail with details]
- Tests written: [count and location]
- Integration: [done/not needed]

Decisions made (without asking):
- [decision 1]: chose X over Y because [reason]
- [decision 2]: chose A over B because [reason]

Blockers: [none, or list]

Next phase: [N+1] - [title]
Recommendation: [proceed / adjust plan / stop and discuss]

Waiting for your go.
```

### Step 7: await approval

Do NOT proceed to the next phase until the user says to continue. The user may:
- Say "go" or "next" to proceed to the next phase
- Adjust the plan based on what they see
- Ask questions about decisions made
- Exit bossman mode with `/bossman --stop`

---

## Stop conditions (exit bossman mode immediately)

1. **Architecture-level change needed** - something in the plan is fundamentally wrong
2. **Blocker with no reasonable workaround** - missing credentials, broken dependency, ambiguous requirement that could go either way with major consequences
3. **Phase complete** - normal checkpoint
4. **User says stop** - `/bossman --stop` or any clear signal to pause

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

**Level 1 (now):** Single-phase execution with full agent team. Manual approval between phases. Orchestrator dispatches researchers, builders, judge, test writer. User reviews at checkpoints.

**Level 2 (trust building):** Multi-phase execution. Ralph Loop keeps the orchestrator running between phases. Judge agent gates phase transitions instead of user approval for non-architectural phases. Sub-planners handle recursive decomposition of complex phases.

**Level 3 (Cursor-scale):** Full autonomous multi-phase execution. Checkpoint files written to disk at each phase boundary. Morning summary of everything built, tested, and judged while user was away. Hundreds of builders if the codebase warrants it. Fresh-start pattern: stuck agents get killed and restarted with clearer prompts rather than debugged in-place.

**Level 4 (multi-team):** Multiple independent agent teams for separate subsystems (e.g., Team A: API, Team B: frontend, Team C: data pipeline). Each team has its own orchestrator running its own research/build/judge cycle. A meta-orchestrator coordinates between teams at phase boundaries. Useful when the project spans different tech stacks, repos, or deployment targets.

## Design inspiration

Architecture inspired by Cursor's [Scaling long-running autonomous coding](https://cursor.com/blog/scaling-agents) post: strict planner/worker separation, single judge over multiple QA roles, workers that don't coordinate with each other, recursive sub-planning, and the principle that simpler systems outperform complex ones. Adapted for Claude Code's agent dispatch model and single-phase-at-a-time execution.
