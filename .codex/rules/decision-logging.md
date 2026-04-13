---
description: "Log non-trivial decisions to DECISIONS.md when choosing between alternatives that affect future work."
scope: portable
alwaysApply: true
depends_on: [DECISIONS.md]
---

## Decision logging

When a non-trivial choice is made between alternatives, log it to `DECISIONS.md` at the repo root.

**What counts as a decision:**
- Choosing one library/framework/tool over another
- Picking an architecture pattern (e.g. monorepo vs polyrepo, REST vs GraphQL)
- Settling a naming convention or file structure
- Any choice where reverting later would cost real work
- Any choice that was debated for more than 2 minutes

**What does NOT count:**
- Obvious defaults (use the project's existing language, follow existing patterns)
- One-off formatting choices
- Decisions already captured in a rule, config file, or code comment

**Format:**

```markdown
| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| YYYY-MM-DD | What we chose | What we didn't choose | The reason |
```

**Apply when:**
- During planning or architecture discussions
- When the user says "let's go with X" after comparing options
- When you recommend one approach over another and the user agrees
- After any debate that gets resolved

**Do NOT apply when:**
- The decision is already documented in a rule (promote to rule instead of logging)
- The decision is ephemeral and won't matter next session
- You're in execution mode following an existing plan - the plan already captured the decisions

**Behavior:**
- **Allow:** append to DECISIONS.md freely after a decision is made
- **Ask:** before logging something the user might consider too minor
- **Deny:** never delete or modify existing decision entries (they're a historical record)

**In software projects:** decisions accumulate fast. Log aggressively - the cost of re-debating a settled choice is always higher than the cost of one extra table row.

**In documentation projects:** decisions are rarer and usually get promoted to rules. Log the ones that fall between "too small for a rule" and "too persistent for memory."
