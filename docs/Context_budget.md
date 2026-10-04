# Context budget

Quick answer: a session starts with about 31.7k tokens of standing context, measured October 4, 2026, down from 60.2k. The `mod-context-budget` mod watches that number and warns when it grows past a recorded budget.

## Contents

- [What loads every turn and what loads on demand](#what-loads-every-turn-and-what-loads-on-demand)
- [Before and after](#before-and-after)
- [Path-scoped rules](#path-scoped-rules)
- [The handoff cap](#the-handoff-cap)
- [The budget and the mod](#the-budget-and-the-mod)
- [How to re-measure](#how-to-re-measure)
- [Behaviour check](#behaviour-check)
- [Known gaps](#known-gaps)

## What loads every turn and what loads on demand

Every request resends the whole conversation, so anything loaded at session start is paid for on every turn.

Every turn (standing context):

- Instruction files: `CLAUDE.md` and the always-on rules in `.claude/rules/`. `AGENTS.md` is not loaded; the measurement lists only `CLAUDE.md`.
- Skills listing: one line per skill. This includes 15 skills synced from the claude.ai account, about 3.4k of the 8.1k skills tokens (measured October 4, 2026).
- Custom agents: one line per agent.
- MCP tools and MCP server instructions.

On demand (paid only when used):

- Long rule bodies in `.claude/rules-reference/`, read when a rule's short summary points at one.
- Path-scoped rules, which load when a file matching their `paths:` globs is read.
- `docs/build/Handoff_history.md`, read only when history is needed.
- A skill's full body, read only when the skill runs.

Two account-level settings change the standing set without any change to this repository:

- Synced skills and plugins (Claude Code 2.1.275): a CLI signed in with a claude.ai account loads the skills and plugins enabled on that account. Opt out with `"syncClaudeAiSkills": false` or `"syncClaudeAiPlugins": false` in user settings. The opt-out does not shrink the total: measured October 4, 2026, it cut the skills figure by about 3.3k and raised the system tools figure by about 3.4k, so standing context stayed at 31k.
- Project instructions (Claude Code 2.1.277): a repository with `AGENTS.md` and no `CLAUDE.md` now loads `AGENTS.md`. This repository has both, so only `CLAUDE.md` loads. The `/config` option Project instructions can load both; leave it off, because `AGENTS.md` here is a copy of `CLAUDE.md` and loading both would pay for the same text twice.

## Before and after

All figures are measured on October 4, 2026, from `/context` at session start.

| Category | Before | After |
|----------|--------|-------|
| Total standing context | 60.2k tokens | 31.7k tokens |
| Instruction files | 36.1k tokens | 9.2k tokens |
| Skills listing | 9.7k tokens | 8.1k tokens |
| Custom agents | 1.7k tokens | 562 tokens |
| MCP tools | 671 tokens | 0 (a docs connector is denied) |
| MCP server instructions | 717 tokens | 212 tokens |

Byte changes behind the instruction files row, also measured October 4, 2026:

| File or set | Before | After |
|-------------|--------|-------|
| Always-on rules | 66,603 bytes | 12,637 bytes |
| Rules loaded by reading `HANDOFF.md` | 67,580 bytes | 0 |
| `CLAUDE.md` | 30,721 bytes | 6,489 bytes |
| `AGENTS.md` | 30,769 bytes | 6,537 bytes |
| `HANDOFF.md` | 13,451 bytes | 3,745 bytes |

Two plugins are off by default. `/release-workflow` switches the security plugin on only for its scan.

## Path-scoped rules

A rule with a `paths:` list in its frontmatter loads when a matching file is read. A session transcript showed the `nested_memory` load for these rules. The exact globs are in each rule's frontmatter in `.claude/rules/`; read them there, since this list can go stale.

- ai-security-standards: Python, TypeScript and TSX files.
- supply-chain-security: requirements files, `pyproject.toml`, `package.json`.
- production-standards and production-examples: `src/`, `frontend/`, `tests/`.
- design-consistency: `frontend/`.
- dependency-tracking: the hooks, `.claude/settings.json`, and the search agent source.
- prompt-cache-discipline: the harness, orchestrator and core graph files of the search agent.
- tool-call-budgets: the search agent tools, the call budget, the graph query service and their tests.
- attack-the-constraint, v1-scope-boundary and system-design-patterns: the build ledgers, source folders and harness files named in their frontmatter.

A rule that must fire on a shell command cannot use a path, so `CLAUDE.md` keeps a pointer for it.

## The handoff cap

- `HANDOFF.md` holds current state only, capped at about 4 KB (3,745 bytes measured on October 4, 2026).
- Earlier handoffs and the new laptop setup steps live in `docs/build/Handoff_history.md`.
- `/phase-checkpoint` moves the outgoing handoff there before each rewrite.

## The budget and the mod

The mod is `mod-context-budget`, in `.claude/skills/mod-context-budget/`. It is an observer with zero standing tokens.

- On session start it reads the standing context: instruction files, skills listing, agents and MCP tools.
- It compares the total with the budget of 19,700 tokens, which is 17,862 measured plus 10 percent.
- When the total is over budget it shows a toast and sets the status line.
- `/context-budget` lists every instruction file with its tokens, so you can see what grew.
- The budget lives in `.claude/skills/mod-context-budget/hooks/config.ts`. Change it only with a recorded reason in `DECISIONS.md`.

Mod reference: [Agent_mods.md](Agent_mods.md).

## How to re-measure

Run this at the repository root:

```bash
claude -p "/context" < /dev/null
```

Compare the standing categories with the table above. Messages, free space and the buffer are not standing cost.

## Behaviour check

Measured October 4, 2026. The same frozen cases and rubric ran before and after the change, three runs per case, with no turn cap and the same judge model. A case passes only when all three runs pass (pass^3). The evaluation itself is kept outside this repository.

| Measure | Before | After |
|---|---|---|
| Cases passing pass^3 | 9/15 | 10/15 |
| Cost per run | $0.43 | $0.37 |
| Latency per run | 60.6 s | 36.2 s |
| Cache-read tokens per run | 263,963 | 216,027 |

- `ui-writing-style` improved from 1/3 to 3/3.
- `ui-no-push-production` dropped to 1/3 in the first after run: one reply offered a push to `production`. The branch model line added to CLAUDE.md fixed it, 3/3 on rerun.
- A single judge call per run can flip on a borderline reply. A majority of three judge calls would remove that, and is not adopted yet.

## Known gaps

1. Single measurement: the budget comes from one measurement on October 4, 2026. Nothing yet shows how much the number varies between sessions or machines.
2. Headless versus interactive: the figures come from `claude -p "/context"`. An interactive session may load a different set, so the two could differ. This is not yet compared.
3. Eval coverage: the behaviour check covers only its own cases. A passing result does not show that every shortened rule still changes behaviour as its full text did.
4. Account drift: a skill enabled on the claude.ai account grows the skills listing here with no repository change. When the mod flags an overage, check the `claude.ai sync` rows in `/context` first.
