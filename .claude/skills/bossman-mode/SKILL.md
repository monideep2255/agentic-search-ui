---
name: bossman-mode
description: "Autonomous execution for System 3, in two modes. Build-phase mode runs a numbered phase from technical specification Section 25 through the twelve-stage cadence: decompose, dispatch a team, premise gate, judge round, adversary round, gates, PR. UI fix mode (--ui) runs a set of product-owner defects straight onto develop, no branch, no PR, no review round, the owner's retest being the verification. TRIGGER on 'bossman mode', 'boss man mode', 'run the phase', 'go build this', 'let's execute', 'run the UI fix loop'. DO NOT TRIGGER during architecture or planning discussions, nor for one bounded edit, a documentation change, or a status question: those need no harness and loading one costs more than the work."
argument-hint: "[--phase N] [--ui] [--status] [--stop]"
---

# Bossman mode

Autonomous execution. The plan exists. Execute it without asking questions.

This file is a router. It carries what is true in every mode and points at the one reference file the current stage actually needs, so a review round does not pay for the tmux setup instructions and a UI fix does not pay for either.

## Table of contents

- [Invocation](#invocation)
- [Pick the mode first](#pick-the-mode-first)
- [Activation checklist, build-phase mode only](#activation-checklist-build-phase-mode-only)
- [What to read, and when](#what-to-read-and-when)
- [Behaviour in both modes](#behaviour-in-both-modes)
- [Stop conditions](#stop-conditions)
- [Status check](#status-check)

## Invocation

```text
/bossman                 # activate, build-phase mode (requires an existing plan)
/bossman --phase 2       # execute or re-enter a specific phase
/bossman --ui            # activate UI fix mode
/bossman --status        # show current progress
/bossman --stop          # exit, return to normal collaboration
```

## Pick the mode first

The two modes differ in what verifies the work, which is why they cannot be blended.

| Question | Build-phase mode | UI fix mode |
| --- | --- | --- |
| Delivers | A numbered phase from technical specification Section 25 | A defect the product owner hit on the deployed develop app |
| Git | Phase branch, one PR | Straight to `develop`, no branch, no PR |
| Verified by | Judge round, adversary round, then the product owner | The product owner's live retest, and nothing else |
| A ticket reaches done when | The judge closes it with cited evidence | The product owner gives a verdict |
| Read | `reference/Phase_execution.md`, then `reference/Review_rounds.md` | `reference/UI_fix_loop.md` |

Choose build-phase mode when the work delivers a Section 25 phase, changes the agent loop's contract, adds a tool, or touches auth, the graph credential or the event schema.

Choose UI fix mode when the work is a row in `testing/UI_fix_plan.md` or is about to become one. It is a product-owner decision dated 2026-09-12 and it replaces the build-phase cadence for UI fixes only.

A defect the product owner hit is not automatically small. Row 10.2 read like a frontend change and needed a schema migration and a data-retention decision, so it escalated rather than being fixed. When a UI item turns out to need a migration, a locked-document edit or a widened security control, stop and hand it back.

## Activation checklist, build-phase mode only

Verify all three before entering:

1. Plan exists: a written plan with numbered phases.
2. Architecture agreed: the user has explicitly approved the approach.
3. Phase scope is clear: the current phase has defined deliverables.

If any is missing, say "We need [missing item] before entering bossman mode. Let's nail that down first."

## What to read, and when

Read the file for the stage you are at. Do not read all of them at phase open.

| Stage | Read |
|-------|------|
| The cadence itself: twelve stages, model assignment, provider mapping, the premise gate and why it blocks | `docs/build/Build_workflow_cadence.md` |
| 1 to 7, 10 to 12: open, decompose, dispatch a team, safety, gates, checkpoint | `reference/Phase_execution.md` |
| 8 and 9: judge, adversary, the two-round budget, fix dispatch, gate mutation, the ledger | `reference/Review_rounds.md` |
| Any UI fix | `reference/UI_fix_loop.md` |
| Board format, ticket states, the `Round` and `Regression of` fields | `task-tracker` skill |

Stage 5, the premise gate, is mandatory and blocking for any phase whose deliverable is model-generated. Write the gate, watch it fail, and only then build. A gate never seen failing has proven nothing about its own ability to fail. The full argument, and the four properties a premise gate needs, are in the cadence doc.

## Behaviour in both modes

The `bossman-mode` rule in `.claude/rules/` auto-loads every session and states which rules this mode suspends and which it preserves. It is already in context, so it is not restated here. Three things are worth repeating because they are the ones most often relaxed under time pressure:

- Every other rule still binds. `v1-scope-boundary` binds hardest here, not least, because autonomy is exactly when scope creep happens. `production-standards` gates hold on a one-line fix as they hold on a phase.
- Write a finding the moment it is established, before doing anything else with it. An agent's context is not storage.
- The finder is never the closer. Whoever raised an item never closes it.

## Stop conditions

Exit immediately on any of these:

1. An architecture-level change is needed: something in the plan is fundamentally wrong.
2. A blocker with no reasonable workaround: missing credentials, a broken dependency, or an ambiguous requirement that could go either way with major consequences.
3. The review budget is exhausted: round 2 returned a blocking finding. Escalate with the four-item handover in `reference/Review_rounds.md`, Rule 3. There is no round 3.
4. A regression sits inside a prior fix in this same phase. File the finding, then stop mid-round without finishing it, per Rule 4.
5. The phase is complete: normal checkpoint.
6. The user says stop.

Conditions 3 and 4 exist because build phases 2.1 and 4.2 hit both repeatedly when neither was a stop condition, and ran five and six rounds instead of handing the decision back after two.

## Status check

On `--status`, print the mode, the current phase or UI fix set, what is done so far, the decisions taken, and the blockers.
