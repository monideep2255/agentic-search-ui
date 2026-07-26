# Phase 5 synthesis

What the build harness now guarantees, organized by topic, ready for Phase 6. The chronological record is in `Session_July_26.md`; this is what it all means together.

Phase 5 opened and closed 2026-07-26.

## Table of contents

- [The one-sentence version](#the-one-sentence-version)
- [What Phase 5 actually was](#what-phase-5-actually-was)
- [Guarantee 1: every gate has an owner](#guarantee-1-every-gate-has-an-owner)
- [Guarantee 2: the harness reads from the spec](#guarantee-2-the-harness-reads-from-the-spec)
- [Guarantee 3: parallel work cannot corrupt itself](#guarantee-3-parallel-work-cannot-corrupt-itself)
- [Guarantee 4: state survives a context reset](#guarantee-4-state-survives-a-context-reset)
- [Guarantee 5: the product owner is in the loop by design](#guarantee-5-the-product-owner-is-in-the-loop-by-design)
- [What Phase 5 deliberately did not build](#what-phase-5-deliberately-did-not-build)
- [What Phase 6 inherits](#what-phase-6-inherits)

## The one-sentence version

The specification was locked in Phase 4, but the machinery meant to enforce it had drifted, contradicted itself, and in one place would have failed on its first run; Phase 5 measured the gap with a 303-obligation coverage map and closed it.

## What Phase 5 actually was

Not a skill-writing phase. A reconciliation between what three locked documents demand and what the tooling actually enforces.

The scoping question was reframed early, at the product owner's insistence, from "which new skills do we need" to "which obligations have no owner". That reframe is the phase's most important decision, because it produced a different and smaller answer:

| Category | Count |
|----------|-------|
| Obligations extracted from the three locked docs | 303 |
| Already owned by an existing rule or skill | 191 |
| Unowned, needing new coverage | 57 |
| New skills the 57 justified | 0 |

Every one of the 57 was a standing constraint (a rule, which loads automatically) or an API fact (a doc, which a builder reads once). None was a workflow. The two skills that were built came from a separate demand surface entirely, the team operating model, which the specification says nothing about.

The generalizable lesson: when asking whether to add tooling, measure the demand first. The instinct to build was pointing at four skills. The measurement pointed at three rules and one document.

## Guarantee 1: every gate has an owner

Before Phase 5, 57 obligations in the locked specification had nothing enforcing them. Now each is routed:

| Theme | Owner |
|-------|-------|
| Per-call timeouts, rate limits, queue depth, fail-fast | `.claude/rules/tool-call-budgets.md` |
| Prompt-cache prefix stability, sorted schemas, load-once few-shot pool | `.claude/rules/prompt-cache-discipline.md` |
| The v1 out-of-scope and fast-follow boundary | `.claude/rules/v1-scope-boundary.md` |
| Cross-layer authority, staleness, audit logging, graceful degradation | `.claude/rules/production-standards.md`, extended |
| Contract versioning, one tool per access path, model identity | `.claude/rules/system-design-patterns.md`, extended |
| Per-tool API traps | `docs/Tool_implementation_mechanics.md` |

Two ownership problems were subtler than absence.

Wiring, not absence. `verify`, `dev-standards`, and `eval-harness` all existed and were all required by the specification, and nothing in the execution chain ever invoked them. A skill nothing triggers is not coverage. All three are now in the phase-end chain.

Drift, not absence. `eval-harness` existed, was invoked, and had never heard of the evaluation playbook it was supposed to implement, missing 13 of its 17 demands. This is worse than a missing gate, because a build checklist ticks a stale gate off as done. It now carries the rubric, the threshold, the hard-fails, the coverage metric, and the feedback loop, with an explicit convention about what to inline versus reference so it cannot drift the same way twice.

## Guarantee 2: the harness reads from the spec

`bossman-mode` previously read its phase definitions from "the plan document", unnamed. It now reads tech spec Section 25, the 26 numbered build phases, and verifies dependencies are merged before opening one.

This closed a live defect with a cascade. The skill created `feature/description` branches while every rule specified `phase/N.M-description`, and `ship` only offers the MR when the branch matches `phase/*`. A real run would have made the wrong branch and then silently skipped the pull request. Both the branch names and the cascade are fixed.

## Guarantee 3: parallel work cannot corrupt itself

Worktree isolation moved from a post-collision fallback to the default for concurrent file-mutating builders, with read-only agents staying in the shared checkout and teardown at phase close.

The ordering principle matters more than the mechanism: partition first, isolate second. Worktrees make concurrent writes safe; they do not make an overlapping decomposition correct. Every ticket names the exact files it may touch, so two builders should never have been aimed at the same file.

## Guarantee 4: state survives a context reset

`task-tracker` gives the build a durable board. The insight was that `bossman-mode` already specified a complete ledger state machine in prose, single writer per state, mandatory reason on judgment states, append-only history, the raiser never closes, and had no file to write it to.

`learnings` gives the build a durable memory of its own failures. The portable part of the adopted pattern is not the table format, it is that the log is read before work starts. A log nobody opens is filing.

Both were dogfooded within the hour. The first two LEARNINGS.md entries came from real failures hit during Phase 5 itself: a sync hook that silently did not fire because an edit went through Bash rather than the Edit tool, and six agents whose writes appeared to fail because they landed in a gitignored directory.

## Guarantee 5: the product owner is in the loop by design

The operating model is now explicit in the harness rather than implied: the product owner coordinates only with the lead, approves each PR, and is marked required on the phases where the thing being judged is whether the interface feels right, currently build phases 1.2 and 4.5. Playwright becomes a hard gate on those phases, because an agent can verify a button exists and cannot verify the result is good.

The standing deny on proceeding past a phase without approval holds. Overnight unattended execution was deferred rather than designed away, and its shape is settled for when it is wanted: fan out where the dependency graph allows, stack only where forced, nothing merges to main unreviewed. The reasoning that settled it is worth keeping, since it is counterintuitive: merging overnight buys no throughput for dependent phases, because a dependent phase builds on the previous branch either way. Autonomy would remove the review gate without accelerating anything.

## What Phase 5 deliberately did not build

Recorded so a future reader does not mistake absence for oversight:

- The four skills Plan.md floated in Phase 0. The coverage map showed the gaps were rules and docs.
- Overnight autonomous execution. Deferred by the product owner pending evidence it is needed.
- Playwright installation. Scheduled for Phase 6, since no frontend exists yet, and it must clear the supply-chain checks first.
- Automated enforcement of `dependency-tracking` on skills. The mandate was narrowed instead, because a field absent from 70 percent of files and wrong where present was recording intentions rather than facts.

## What Phase 6 inherits

- A build order with 26 numbered phases, a dependency graph, and branch names, in tech spec Section 25.
- A gate list, `requirements/phase_5/Coverage_map.md`, with every obligation mapped to its owner.
- A harness that opens a phase by reading the spec and the learnings, tracks work on a board, isolates concurrent writers, runs six gates at phase end, and stops for approval.
- Two open items: the golden fixture domain sign-off owner, needed before build phase 5.1, and whether overnight runs are wanted at all.

The first action in Phase 6 is `/task-tracker --open 1.0` after reading `LEARNINGS.md`.
