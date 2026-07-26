# Phase 5 continuation prompt

Phase 5 is COMPLETE (opened and closed 2026-07-26). All four steps, 5.1 to 5.4, are done. There is no remaining Phase 5 work. The next phase is Phase 6, the build. This file is kept as the Phase 5 record.

## Context to provide

Paste the following into your new chat:

---

Phases 1 through 5 of System 3 planning are complete. Phase 5 rebuilt the project's build harness so it matches the locked specifications. Read these files to get up to speed:

1. `requirements/Plan.md` - the roadmap. The status table shows Phases 1 to 5 complete and Phase 6 next.
2. `requirements/PRD.md` - the locked PRD. Every requirement traces to an outcome here.
3. `requirements/Technical_specification.md` - the locked tech spec. Section 25 is the build order, 26 numbered phases, and it is the source of truth for what gets built and in what sequence.
4. `requirements/Evaluation_playbook.md` - the living evaluation contract the eval-harness skill now implements.
5. `requirements/Strategic_memo.md` - the executive distillation.
6. `requirements/phase_5/Coverage_map.md` - 303 obligations from the three locked docs, each mapped to the rule or skill that enforces it. This is the gate list to build against.
7. `DECISIONS.md` - all decisions, 121 as of 2026-07-26.
8. `LEARNINGS.md` - what has broken so far and what fixed it. Read this before opening any build phase.

Phase 6 is the build. Step 6.1 is the prototype, which is build phases 1.0 through 2.2 in tech spec Section 25. Step 6.2 is the one reconciliation pause. Step 6.3 is v1, everything from build phase 3.0 onward.

Rules:
- The PRD, tech spec, and strategic memo are frozen. They are edited only at the Step 6.2 reconciliation.
- Log every decision to `DECISIONS.md` (append only, never modify existing rows).
- Work on `phase/N.M-description` branches, never on main. One PR per phase.
- Open every build phase with `/task-tracker --open N.M` and `/learnings --brief N.M`.
- Close every build phase with the full chain: verify, eval-harness where answer generation is touched, dev-standards where code shipped, release-workflow, ship, task-tracker.
- The product owner approves each PR before the next phase starts. Do not proceed without it.

---

## What Phase 5 produced

| Artifact | What it is |
|----------|-----------|
| `.claude/skills/bossman-mode/SKILL.md` | The build harness, rewritten. Phase branches, Section 25 as the phase source of truth, worktree isolation by default, product owner role, scope check, Playwright gate for UI, a six-skill phase-end chain |
| `.claude/skills/task-tracker/SKILL.md` | The in-repo board. Tickets with acceptance criteria, spec anchors, evidence, append-only history, and one writer per status |
| `.claude/skills/learnings/SKILL.md` | Failure capture and recall. Written at the moment of failure, read before every phase |
| `.claude/skills/eval-harness/SKILL.md` | Rewritten against the evaluation playbook. The 8-point rubric, 13-of-16 threshold, three hard-fails, coverage metric, moat test, must-pass seven, feedback loop |
| `.claude/rules/tool-call-budgets.md` | Per-tool timeouts, rate limits, queue depth, fail-fast. 13 obligations |
| `.claude/rules/v1-scope-boundary.md` | The PRD out-of-scope list and the fast-follow table as a hard boundary. Binds hardest during autonomous runs |
| `.claude/rules/prompt-cache-discipline.md` | Adapted from personal-os. Stable prefix immutability, sorted tool schemas, load-once few-shot pool |
| `docs/Tool_implementation_mechanics.md` | 19 per-tool API traps from tech spec Section 6. Facts, not policy |
| `requirements/phase_5/Coverage_map.md` | The 303-obligation gate list with owners |
| `LEARNINGS.md` | Started, with the first two entries from this session |

Also: `production-standards` and `system-design-patterns` extended, `dependency-tracking` narrowed to hooks, `release-workflow` and `dev-standards` and `best-practices` corrected, 19 stale root-document statements fixed, the PR template rewritten for System 3.

## Phase 5 steps

| Step | What it did | Status |
|------|-------------|--------|
| 5.1 | Update bossman-mode against the tech spec build order | Complete (2026-07-26) |
| 5.2 | Update or create skills, pull beneficial rules from personal-os | Complete (2026-07-26) |
| 5.3 | Update root documents | Complete (2026-07-26) |
| 5.4 | Create new reference docs | Complete (2026-07-26) |

## Decisions carried in

- The coverage map set the scope, not the candidate list. 303 obligations, 57 unowned, all routed to rules or docs. Zero of the four skills Plan.md originally floated were built, because the gaps were standing constraints (rules load automatically) and API facts (docs), not workflows.
- `dependency-tracking` narrowed to hooks only. Skills joined rules and agents in the exempt category, because CLAUDE.md's table is the real dependency record and the frontmatter field was absent from 9 of 13 skills and factually wrong where present.
- Overnight unattended execution deferred by the product owner. When enabled, the shape is fixed: fan out where Section 25's dependency graph allows, stack only where forced, one PR per phase, nothing merges to main unreviewed.
- Playwright is the UI verification gate, wired in Phase 6 after supply-chain checks, a hard gate rather than an available tool.
- `.claude/` and `.codex` re-tracked in git for the duration of v1, reversing the 2026-07-25 untracking. `settings.local.json` stays ignored as per-machine state.
- The product owner is required on build phases 1.2 and 4.5, the phases where the thing being judged is whether the interface feels right.

## Open items

- Golden fixture domain sign-off: nobody is named to verify the clinical and human-variation expected answers. Needed before build phase 5.1 ships the 50-query dataset, since retrofitting sign-off means re-reading every fixture. Three options were laid out: name a clinical genetics collaborator, narrow the clinical subset to mechanically checkable questions, or ship it marked unsigned and report it separately.
- Overnight autonomous execution: deferred until it is known whether it is needed.

## Start here

Phase 5 is complete. The harness now matches the locked specification and every gate the spec demands has an owner. Next: Phase 6, Step 6.1, the prototype, which is build phases 1.0 through 2.2 of tech spec Section 25. Open it with `/task-tracker --open 1.0` after reading `LEARNINGS.md`.
