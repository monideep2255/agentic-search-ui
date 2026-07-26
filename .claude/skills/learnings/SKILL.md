---
name: learnings
description: Capture and recall build-time failures in LEARNINGS.md, what broke, what was tried, and what actually fixed it, written at the moment of failure rather than reconstructed later. Use the moment something breaks during a build, and again before opening any build phase so past mistakes are not repeated. TRIGGER on "log this", "that broke", "add to learnings", "what do we know about X", "have we hit this before", and automatically at the start of any build phase. Distinct from DECISIONS.md, which records choices between alternatives: this records failures and their fixes. Distinct from task-tracker, which records what is assigned rather than what went wrong.
argument-hint: "[--log] [--recall <topic>] [--brief <phase>]"
---

# Learnings

A running log of what broke, what was tried, and what actually fixed it. The point is not the file. The point is that it gets read before work starts, so the same wall is not hit twice.

`LEARNINGS.md` at the repo root is already specified in `requirements/Plan.md` as the input to the Step 6.2 reconciliation and a seed for Phase 7 iteration. This skill is what writes and reads it.

## Table of contents

- [Why write at the moment of failure](#why-write-at-the-moment-of-failure)
- [Entry format](#entry-format)
- [When to write](#when-to-write)
- [When to read, which matters more](#when-to-read-which-matters-more)
- [What does not belong here](#what-does-not-belong-here)
- [Three-state permissions](#three-state-permissions)

## Why write at the moment of failure

A learning reconstructed at phase end is a summary. A learning written while the error is on screen keeps the exact message, the exact command, the two things that did not work, and the reason the third did. The details that make an entry useful next time are precisely the details memory drops first.

The failure mode this prevents: a phase ends, someone writes "had some trouble with the AGE connection, resolved it," and six weeks later that sentence helps nobody.

## Entry format

Append to the table in `LEARNINGS.md`, newest last:

| Date | Applies to | What broke | What was tried | What fixed it |
|------|-----------|------------|----------------|---------------|
| 2026-07-26 | `cypher_query`, Layer 1 | Example: query returned rows for a gene that does not exist | Widened the WHERE clause, checked the index | Untyped relationship pattern matched across edge types. Explicit edge label required, see `docs/ncbi/Tool_implementation_mechanics.md` |

Applies to: the tool, layer, build phase, or subsystem, so a future reader can filter. Tag generously; a missed tag is a missed recall.

When the table cell is too small for the fix, add a detailed section below the table under a heading matching the date and topic, and keep the table row as the index pointing to it.

Two things every entry needs, and the second is the one people skip:
- What fixed it, stated concretely enough to repeat.
- What did NOT fix it. The dead ends are half the value, because they are what the next person would otherwise try first.

## When to write

Write immediately when:
- A command, tool, or test fails in a way that took more than a couple of minutes to resolve.
- An assumption in the spec or a doc turned out to be wrong in practice.
- A fix worked but the reason is not obvious from the code.
- An agent or a whole phase went in a wrong direction and had to be redone.
- A live API behaved differently from the documented contract in `requirements/phase_4/API_capability_sheet.md`.

Do not batch these to the end of a phase. That is the whole point.

## When to read, which matters more

A log nobody reads is filing, not learning. Reading is mandatory at these points:

- Before opening any build phase. The `task-tracker` open operation requires it. Filter by the phase's tools and layers.
- Before retrying anything that failed once. Check whether the dead end is already recorded.
- Before wiring any tool in the seven-tool roster, since API behavior traps accumulate here.
- At the Step 6.2 reconciliation, where this file is the captured record that updates the PRD, tech spec, and strategic memo rather than doing it from memory.

`--brief <phase>`: print only the entries tagged to that phase, its tools, and its layers. This is the form a builder should receive, not the whole file.

## What does not belong here

- A choice between alternatives with no failure involved. That is `DECISIONS.md`.
- Task status. That is `task-tracker`.
- A defect found by the adversary that is not yet triaged. That goes to the ledger first, and only lands here once it is understood and fixed.
- Anything already captured as a rule. If a learning generalizes into a standing constraint, promote it to a rule in `.claude/rules/` and leave a pointer here.

## Three-state permissions

Allow:
- Append an entry without asking, at any time, during any mode including autonomous execution
- Read and filter the file freely
- Promote a recurring learning into a rule, and leave a pointer behind

Ask:
- Before rewording an existing entry, since entries are a historical record

Deny:
- Never delete an entry
- Never batch a phase's learnings to the end instead of writing them when they happen
- Never open a build phase without reading the entries tagged to it
- Never record only the fix and omit the dead ends that were tried first

The test: when the next agent hits this same wall, will this entry save it the hour I just spent, or only tell it that an hour was spent?
