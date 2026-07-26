---
name: task-tracker
description: Maintain the in-repo build board that tracks every task across the System 3 build phases, with acceptance criteria, status, evidence, and an append-only history per ticket. Use when opening a build phase, when a builder finishes or blocks, when the product owner asks "what is the status" or "what is left", and at every phase checkpoint. TRIGGER on "open the board", "what is in flight", "status of phase N", "add a ticket", "mark done". Distinct from phase-checkpoint, which syncs the planning documents at a requirements phase boundary: this tracks execution work during a build phase. Distinct from LEARNINGS.md, which records what broke rather than what is assigned.
argument-hint: "[--open N.M] [--status] [--close TICKET-ID]"
---

# Task tracker

The build board. A running, in-repo record of what is planned, in flight, blocked, and done, so the product owner can see state without reading a diff and the lead can resume a phase after a context reset.

Decision from Step 1.8 chose a self-maintained in-repo tracker over Linear. This skill is that tracker.

## Table of contents

- [Where the board lives](#where-the-board-lives)
- [Ticket format](#ticket-format)
- [Status states and who may set them](#status-states-and-who-may-set-them)
- [The four ledger rules](#the-four-ledger-rules)
- [Operations](#operations)
- [What a ticket must carry before work starts](#what-a-ticket-must-carry-before-work-starts)
- [Three-state permissions](#three-state-permissions)

## Where the board lives

| Path | What it holds | Kind |
|------|---------------|------|
| `tracker/BOARD.md` | The index. One row per phase: phase, branch, delivers, dependencies, group, status, flags | Source of truth |
| `tracker/phase_N.M.md` | One file per build phase, holding that phase's tickets in full | Source of truth |
| `tracker/board.html` | A standalone kanban page, openable directly in a browser with no server | Generated view |
| The published artifact | The same board hosted and shareable | Generated view |

Markdown is canonical because it is diffable, reviewable in a pull request, and writable by an agent mid-run. The two HTML views are generated from it and are never hand-edited. Editing a generated view is a defect: the next regeneration silently discards it.

Build phases and their dependencies come from `requirements/Technical_specification.md` Section 25. That section is the source of truth for what phases exist, what each delivers, and what it depends on. The board never invents a phase.

Per-phase files rather than one large board: 26 build phases in one file becomes unscannable, and a phase file can be read on its own by an agent that needs only its own phase.

## Ticket format

Each ticket in a phase file:

```markdown
### T-2.1-03: Cypher validate-then-execute pipeline

Status: in-progress
Branch: phase/2.1-cypher-tool
Depends on: T-2.1-01, T-2.1-02
Spec: Technical_specification.md Section 6.1

Acceptance criteria:
- [ ] Generated Cypher is validated before execution, never executed unvalidated
- [ ] Every query uses parameterized placeholders, no f-strings in query text
- [ ] Every relationship pattern carries an explicit edge label
- [ ] Tests cover valid input, invalid input, and null input

Breakdown:
- [x] Schema slice loader
- [x] Generation prompt with schema context
- [ ] Validator
- [ ] Repair loop

Evidence:
- (filled at close: command output, file:line, test result)

History:
- 2026-07-26 lead: created, scoped from Section 6.1
- 2026-07-26 builder-cypher: claimed
```

Ticket IDs are `T-<phase>-<NN>`, stable once assigned, never reused.

## Status states and who may set them

One writer per state. This is the rule that keeps parallel agents from corrupting each other's work.

| Status | Meaning | Who may set it |
|--------|---------|----------------|
| `todo` | Scoped, not started | Lead only |
| `in-progress` | Claimed and being worked | The builder that claimed it |
| `blocked` | Cannot proceed, reason required | The builder that hit the block |
| `in-review` | Builder done, awaiting judge | The builder that finished |
| `rejected` | Judge or adversary found a defect, reason required | Judge only |
| `done` | Judge passed with evidence | Judge only, never the builder |

The builder that did the work never marks it done. That is the maker-cannot-sign-off split from `self-eval-loop.md`, applied to the board.

## The four ledger rules

These come from the shared-ledger convention already in `bossman-mode`, made concrete here:

- Single writer per state: each status has exactly one role authorized to set it, per the table above. No status has two writers.
- Mandatory reason on judgment states: `blocked`, `rejected`, and `done` each carry a one-line reason. A bare status change with no reason is invalid.
- Append-only history: every transition appends a dated who-what-why line. History is never rewritten, only extended.
- The raiser never closes: whoever raised a ticket or filed a defect is never the one who closes it.

## Operations

Open a phase (`--open N.M`):
1. Read the phase's row in `requirements/Technical_specification.md` Section 25: what it delivers, what it depends on.
2. Verify every dependency phase is `done` on the board. If not, stop and report.
3. Read `LEARNINGS.md` for entries tagged to this phase or its tools before scoping anything.
4. Decompose the phase into tickets. Each gets acceptance criteria traced to a spec section.
5. Create `tracker/phase_N.M.md`, add the phase row to `tracker/BOARD.md`.

Status (`--status`): print the board index plus the open tickets in the current phase, grouped by status. Blocked tickets first, with their reasons.

Close a ticket (`--close`): only after the judge has produced evidence. Paste the evidence into the ticket's Evidence block, append the history line, set `done`.

Phase close: every ticket in the phase file is `done` or explicitly deferred with a reason. A phase with an open ticket is not complete, regardless of what the builders reported.

Publish (`--publish`): regenerate both HTML views from `tracker/BOARD.md`, then publish. Run it after any status change the product owner should see, and at every phase boundary.

1. Update `tracker/BOARD.md` first. It is the source; the views follow it, never the reverse.
2. Regenerate the page body, holding the phase data as a JavaScript array so the columns, filters, and counts derive from one list rather than being hand-placed.
3. Write `tracker/board.html` as a complete standalone document, with doctype, head, and a theme toggle, so it opens by double-clicking with no server and no network.
4. Publish the same body as an artifact, which is wrapped in its own document shell by the publishing step, so that copy carries no doctype of its own.
5. Republish to the same URL rather than minting a new one, so a link shared once keeps working.

Both views must come from the same generated body, so they cannot drift. Verify after regenerating: the counts in the summary strip must equal the counts in the underlying data, and the open-flag count must equal the rows in the flags table.

### What the board encodes visually

Form carries state, not just number, so what needs attention reads at a glance:

- Status is a column and a color: done, in progress, blocked, to do.
- Group is a tag: planning, prototype, v1.
- Dependencies are chips, so a phase that cannot start yet shows why.
- Gates are chips, marking a phase that must clear `eval-harness`, `dev-standards`, or Playwright before it ships.
- Product owner required is its own chip, deliberately not a flag. It is a property of the phase, not a problem to resolve, and conflating the two makes the open-flag count lie.
- Flags are unresolved problems that block their phase. This count must reconcile with the flags table.

## What a ticket must carry before work starts

A ticket dispatched without these is under-specified, and an under-specified ticket is how autonomous work drifts:

- Acceptance criteria that are checkable, not aspirational. "Returns cited results" is not checkable. "Every returned claim carries source, source_id, source_url, and layer" is.
- The spec section it traces to. A ticket with no spec anchor is either scope creep or a missing spec section, and both need the lead, not a builder.
- Its dependencies by ticket ID.
- The exact files it may create or modify, so two builders never collide.

## Three-state permissions

Allow:
- Create, update, and read board and phase files without asking
- Decompose a phase into tickets from the tech spec's Section 25 row
- Append history lines and record evidence

Ask:
- Before creating a ticket that does not trace to a spec section, since that is either scope creep or a spec gap
- Before deferring a ticket at phase close

Deny:
- Never let a builder set its own ticket to `done`
- Never set a judgment state without a reason
- Never rewrite or delete history, only append
- Never open a phase whose dependency phases are not `done`
- Never invent a build phase that Section 25 does not define

The test: can the product owner read `tracker/BOARD.md` and know exactly what is done, what is in flight, what is blocked and why, without reading a single diff?
