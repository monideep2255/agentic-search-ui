---
name: parallel-first
description: Before starting any multi-part task, check if subtasks are independent and can run in parallel - using parallel tool calls or parallel subagents
scope: portable
depends_on: []
depended_by:
  - CLAUDE.md
  - AGENTS.md
  - .claude/README.md
---

## Parallel-first execution

Before starting any task with 2+ parts, ask: can these run in parallel?

**The check (takes 5 seconds):**

1. Do any subtasks depend on the output of another? If yes, those must be sequential.
2. Do any subtasks share write targets (same file)? If yes, those must be sequential.
3. Everything else: run in parallel.

**When to use parallel tool calls vs. parallel subagents:**

- Parallel tool calls: reading multiple files, running multiple bash commands, independent searches. Use when each subtask is a single tool call.
- Parallel subagents (Agent tool): when each subtask needs multiple steps, reads files, and produces output independently. Use when the work is non-trivial and self-contained.

**Examples:**

- User gives 3 tasks → check dependencies first → dispatch independent ones as parallel agents
- Deep dive + meeting prep → independent → run as parallel agents
- Repo clone (step 1) + deep dive analysis (step 2) → step 2 depends on step 1 → sequential
- Reading 5 files for context → no dependency between reads → parallel tool calls in one message

**Do NOT apply when:**
- Task has clear sequential dependencies (step B requires output of step A)
- There is only one task

**Why:** Sequential execution on independent tasks is wasted time. The cost of checking for parallelism is always lower than the cost of waiting.
