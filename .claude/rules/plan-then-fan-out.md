---
paths: ["HANDOFF.md", "DECISIONS.md", "LEARNINGS.md", "testing/UI_fix_plan.md", "testing/UI_fixes_done.md", "docs/build/*", ".claude/skills/bossman-mode/*", ".claude/skills/bossman-mode/reference/*", "{tracker,requirements}/**/*"]
---
## Plan then fan out (reasoning model decomposes, cheaper models execute)

When work fans out to parallel agents, split the roles by model tier. The strongest reasoning model (Opus) owns the plan: it scouts the terrain, decomposes the work into tightly scoped, self-contained, non-overlapping tasks, and writes each task a contract. Cheaper, faster models (Sonnet 5 for substantive extraction and analysis, Haiku 4.5 for mechanical lookup and formatting) own execution: each runs one bounded task in parallel. The expensive reasoning is spent once, on the decomposition and the final synthesis. The repetitive execution is spent cheaply, in parallel.

### Only the lead fans out

This rule is addressed to the session that owns the task, the lead. A dispatched worker never applies it to its own slice: a worker does its one bounded task and never dispatches an agent, however parallel its slice looks. If a worker's task is too big for one agent, it stops and reports that to the lead, who re-splits.

Measured 2026-09-24, and the reason this section exists: the diagnosis behind `docs/build/Bossman_mode_redesign.md` dispatched 7 read-only workers, two of them read "check for parallelism first" as addressed to them and dispatched 4 and 9 workers of their own, one of those handed back empty, an eighth dispatch hit the harness's concurrent limit of 20, and the lead counted about 17 agents running at once, past this rule's own ask-first line of 8. Nothing stopped a worker from fanning out, because the rule read the same to a worker as to the lead. Product-owner decision, 2026-09-24: workers never dispatch.

Two ways to make that hold, strongest first:

- Remove the ability: dispatch reviewers and read-only workers as agent types with no Agent tool, such as `phase-reviewer` and `product-reviewer` (`system-design-patterns` pattern 8).
- Say it: every worker brief carries "Do not dispatch agents", including briefs for agent types that could.

### Check for parallelism first

Before starting any task with 2 or more parts, ask: can these run in parallel? The check takes 5 seconds:

1. Do any subtasks depend on the output of another? If yes, those must be sequential.
2. Do any subtasks share write targets (the same file)? If yes, those must be sequential.
3. Everything else: run in parallel.

Two mechanisms, chosen by shape:
- Parallel tool calls: reading multiple files, running multiple bash commands, independent searches. Use when each subtask is a single tool call.
- Parallel subagents (the Agent tool): when each subtask needs multiple steps, reads files, and produces output independently. Use when the work is non-trivial and self-contained.

Worked examples:
- User gives 3 tasks: check dependencies first, then dispatch the independent ones as parallel agents.
- Deep dive plus meeting prep: independent, run as parallel agents.
- Repo clone (step 1) plus deep dive analysis (step 2): step 2 depends on step 1, so this is sequential.
- Reading 5 files for context: no dependency between reads, parallel tool calls in one message.

Do not apply this check when the task has clear sequential dependencies (step B requires the output of step A) or when there is only one task. Sequential execution on independent tasks is wasted time: the cost of checking for parallelism is always lower than the cost of waiting.

### Why

- The value in fan-out work is the decomposition, not the execution. A good split (non-overlapping, self-contained, clear done-when) is a reasoning task. Running a bounded task against clear instructions is not.
- Cheaper execution models are faster and less likely to exhaust budget. Handing execution to top-tier reasoning agents wastes reasoning tokens on mechanical work and raises the odds of a session or rate-limit stall. This is a real, observed failure in this project: a fan-out of five reasoning-model-inherited agents died together on a session limit, and the same work re-run as scoped Sonnet tasks is both cheaper and more robust.
- It maximizes throughput: more parallel workers per unit of budget.

### The split

Reasoning model (Opus), before any fan-out:
- Scout the terrain: list the files, map the tree, probe the surface. Do not send workers blind.
- Decompose into N non-overlapping tasks, partitioned by subtree, file range, API surface, or entity, so two workers never write the same target.
- Write each worker a goal contract: done-when, inputs and scope, output path, constraints, blocked-stop (see `goal-contracts`).

Reasoning model (Opus), after the workers return:
- Synthesize the parts into the deliverable and own final judgment. Workers produce parts, the planner assembles the whole.

Worker models (Sonnet 5, or Haiku 4.5 for purely mechanical work):
- One bounded task each, in parallel, writing structured output to a named file, returning a short summary so the planner's context stays lean.

### How to apply

- Pass `model: "sonnet"` (or `"haiku"`) to the Agent tool for execution subagents. Default execution to Sonnet. Drop to Haiku only for purely mechanical work (grep-and-list, format conversion). Keep Opus for the plan and the synthesis.
- Scout before you decompose. The planner reads enough of the terrain to carve non-overlapping slices.
- Each worker task is self-contained: it names the files or scope, the output path, and the done-when. A worker should never need to coordinate with a sibling mid-run.
- Keep the worker's output off the planner's context: workers write to files, return a short summary, and the planner reads the files when assembling.
- Count dispatches. A bossman build phase gets 8 agent dispatches in total, reviewers included, and the ninth needs the product owner (DECISIONS.md, 2026-09-24). Outside a build phase, roughly 8 concurrent is the ask-first line below.

### When to apply

- Any fan-out of 2 or more independent agent tasks: mining a tree, verifying many API surfaces, reviewing many files, migrating many sites.
- Any time the "Check for parallelism first" section above points you at parallel subagents.

### When NOT to apply

- A single task with no parallelism. Just do it, or use one agent.
- Work where each step depends on the previous. That is sequential, there is nothing to fan out.
- Work where every item needs frontier reasoning (for example subtle adversarial verification). Keep those on the stronger model. Tier down only what is genuinely bounded.

### Relationship to other rules

- The "Check for parallelism first" section above decides what can run in parallel. The rest of this rule decides who plans and who executes once it does.
- `goal-contracts`: each worker task carries a contract, and the planner writes it. This is the meta-prompt-the-contract pattern applied per worker.
- `self-eval-loop`: the planner, or a separate fresh-context checker, grades the synthesized output. A worker never signs off its own part as final (maker cannot check).

### Three-state permissions

Allow:
- Decompose and dispatch parallel Sonnet or Haiku workers under an Opus-authored plan without asking.
- Choose the worker model tier per task (Sonnet default, Haiku for mechanical).

Ask:
- Before fanning out a large worker fleet (roughly 8 or more concurrent) that will consume significant budget, confirm scope first.
- Before a ninth agent dispatch in one bossman build phase, reviewers and the product reviewer included.

Deny:
- Never dispatch parallel workers without first scouting and decomposing. No blind fan-out.
- Never hand mechanical execution to the top reasoning model when a cheaper worker with a clear contract will do.
- Never let two workers write the same output target. Partition first.
- Never let a worker dispatch an agent. Only the lead fans out.

The test: before fanning out, did the reasoning model scout the terrain and write each worker a self-contained task contract that no sibling's overlaps? Does each contract forbid the worker to dispatch? Are the workers running on the cheapest model that fits the task?
