---
name: learnings
description: Capture and recall build-time failures in LEARNINGS.md, what broke, what was tried and what fixed it, written before the worker continues rather than reconstructed later. Use the moment something breaks during a build, and before opening any build phase. TRIGGER on "log this", "that broke", "add to learnings", "what do we know about X" or "have we hit this before". It also runs automatically at the start of any build phase. Distinct from DECISIONS.md, which records choices between alternatives, and from task-tracker, which records what is assigned rather than what went wrong.
argument-hint: "[--log] [--recall <topic>] [--brief <phase>]"
---

# Learnings

A running log of what broke and what fixed it, with the dead ends in between. The point is not the file. The point is that it gets read before work starts, so the same wall is not hit twice.

`LEARNINGS.md` at the repo root is already specified in `requirements/Plan.md` as the input to the Step 6.2 reconciliation and a seed for Phase 7 iteration. This skill is what writes and reads it.

## Table of contents

- [Why write at the moment of failure](#why-write-at-the-moment-of-failure)
- [The one practice](#the-one-practice)
- [Entry format](#entry-format)
- [When to write](#when-to-write)
- [When to read, which matters more](#when-to-read-which-matters-more)
- [What does not belong here](#what-does-not-belong-here)
- [Three-state permissions](#three-state-permissions)

## Why write at the moment of failure

A learning reconstructed at phase end is a summary. A learning written while the error is on screen keeps what memory drops first:

- The exact message.
- The exact command.
- The two things that did not work.
- The reason the third did.

The failure mode this prevents: a phase ends, someone writes "had some trouble with the AGE connection, resolved it," and six weeks later that sentence helps nobody.

## The one practice

A failure that cost more than five minutes becomes a row in `LEARNINGS.md` before the worker continues. Not at the checkpoint, not at phase end, not when the report is written. It is stated once, here, so it is followed rather than argued (build harness review, 2026-09-25, S9):

- Every worker brief carries the line, in `.claude/skills/bossman-mode/reference/Phase_execution.md`'s agent prompt template.
- A worker whose brief forbids writing anywhere but one path writes the row's text there and says it is a learning; the lead moves it.
- `/phase-checkpoint` may still find a failure nobody wrote down and add its row. Every such row is a sign the practice slipped, not the practice itself.

Why it is written down this bluntly: across the fix loop from 2026-09-12 the decision rows per working day ran 9, 42, 28, 18, 7, 25, 8, 23 and 54, while the learnings rows ran 0, 0, 0, 0, 0, 17, 3, 13 and 7. Either nothing broke on the five busiest days, or the rows were written in batches when the checkpoint ran. This skill said the first and the record showed the second.

## Entry format

Append to the table in `LEARNINGS.md`, newest last:

| Date | Applies to | What broke | What was tried | What fixed it |
|------|-----------|------------|----------------|---------------|
| 2026-07-26 | `cypher_query`, Layer 1 | Example: query returned rows for a gene that does not exist | Widened the WHERE clause, checked the index | Untyped relationship pattern matched across edge types. Explicit edge label required, see `docs/ncbi/Tool_implementation_mechanics.md` |

The last two cells (`What was tried` and `What fixed it`) are each wrapped in a `<details>` dropdown, and every existing row follows that shape. The first three cells stay visible so the table scans for "have we hit this before"; the rest opens on demand. Match the shape when appending, or the table stops scanning.

After appending, run `python tracker/check_doc_drift.py --check`. It fails on three things:

- A row that is missing a wrapper.
- A row whose column count is wrong.
- A blank line inside the table, which ends the table when rendered and turns every row below it into loose text. That happened on 2026-08-14 and hid 273 of 311 rows while every source-level check still passed, so this is a gate rather than a suggestion.

Applies to: the tool, layer, build phase, or subsystem, so a future reader can filter. Tag generously; a missed tag is a missed recall.

When the table cell is too small for the fix: add a detailed section below the table, under a heading matching the date and topic. The table row stays as the index pointing to it.

Two things every entry needs, and the second is the one people skip:

- What fixed it, stated concretely enough to repeat.
- What did NOT fix it. The dead ends are half the value, because they are what the next person would otherwise try first.

## When to write

Write before continuing when:

- A command, tool, or test fails in a way that took more than five minutes to resolve.
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

`--brief <phase>`: print only the entries tagged to that phase and to its tools and layers. This is the form a builder should receive, not the whole file.

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
- Never continue past a failure that cost more than five minutes without its row written
- Never open a build phase without reading the entries tagged to it
- Never record only the fix and omit the dead ends that were tried first

The test: when the next agent hits this same wall, will this entry save it the hour I just spent? Or will it only say that an hour was spent?
