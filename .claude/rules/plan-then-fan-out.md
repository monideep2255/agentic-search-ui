---
paths: ["tracker/phase_*.md", ".claude/skills/bossman-mode/**/*"]
---
## Plan then fan out

Only the lead fans out. A dispatched worker never dispatches an agent. A task too big for one worker goes back to the lead to re-split (owner decision, 2026-09-24).

- Check for parallelism first. Dependent steps stay sequential.
- The lead, on the strongest reasoning model, scouts the terrain, splits the work into non-overlapping tasks so no two workers write the same target, and writes each worker a goal contract that forbids it to dispatch.
- Workers run on the cheapest model that fits (Sonnet, or Haiku for mechanical work): one bounded task each, output to a named file, a short summary back.
- The lead synthesizes and owns final judgment.

Full text, with the measured incident, the limit on concurrent agents and the three-state permissions: `.claude/rules-reference/plan-then-fan-out.md`.
