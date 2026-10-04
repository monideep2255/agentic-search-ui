---
description: "Before any autonomous or multi-step run, write a goal contract (done-when, verify, output, constraints, blocked-stop). Stop on verified evidence, not on feel."
scope: portable
alwaysApply: false
paths: ["tracker/phase_*.md", ".claude/skills/bossman-mode/**/*", ".github/gates/**/*"]
---

## Goal contracts

Before any run that goes to completion without a human at each step (a bossman phase, a background agent, deep research), write the contract. The loop does not start until it exists.

1. Done when: the outcome in one testable sentence.
2. Verify: the concrete surface that proves it, immutable for the run. Add checks, never weaken them.
3. Output: the artifact and where it lands.
4. Constraints: what stays true throughout.
5. Blocked-stop: when to stop and report rather than guess.

Also binding, in full in `.claude/rules-reference/goal-contracts.md`:

- Completeness is part of done-when.
- A long run gets a meta-prompted contract.
- Never change a correct subject so a check that measures something else goes green.
- Every verify surface states what it does not cover.

The test: before I started running to completion, did I write a testable done-when and name how I would verify it?
