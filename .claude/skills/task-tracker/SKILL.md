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
- [Refinement labels](#refinement-labels)
- [Findings](#findings)
- [The four ledger rules](#the-four-ledger-rules)
- [Operations](#operations)
- [What a ticket must carry before work starts](#what-a-ticket-must-carry-before-work-starts)
- [Acceptance criteria wording](#acceptance-criteria-wording)
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
Refine: refined
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

`rejected` is transient and deliberately has no column. The judge sets it with a reason, files the defect in Findings, and the ticket returns to `in-progress` in the same move. Work flows backward on a rejection, it does not park. A ticket sitting in `rejected` at the end of a session means someone stopped halfway through the transition.

## Refinement labels

Every ticket carries exactly one refinement label from the moment it is created. Without one it gets lost in the backlog: there is no way to tell whether anyone has looked at it, so it sits in `todo` alongside tickets that are actually ready. A ticket with no refinement label is invalid, the same way a judgment state with no reason is invalid.

| Label | Meaning | Who sets it |
|-------|---------|-------------|
| `tech_refine` | Still being refined, not yet discussed in the tech refinement meeting | Lead, at ticket creation |
| `product_refine` | Needs the product owner's input before it can proceed | Lead, when a question surfaces that only the product owner can answer. Only the product owner's answer moves it forward |
| `team_refine` | Ready for the team to review | Lead, once tech refinement and any product question are resolved |
| `refined` | Passed refinement, ready to be worked | Lead, once the team's review raises no blocking feedback |

`refined` is not one of the product owner's three labels. It is added here to complete the lifecycle: without a positive "done refining" state, a ticket that finished refinement would have to lose its label rather than advance one, and that loses the trail of how it got there. Every other label describes a ticket still moving through refinement. `refined` is the one state that says refinement is over.

A ticket moves through the labels in order: `tech_refine`, then either `product_refine` if it needs product input or straight to `team_refine`, then `refined`. Each move appends a history line the same as any other ticket change.

Refinement gate: a ticket cannot move from `todo` to `in-progress` unless its refinement label is `refined`. This is the whole point of the labels, so it is a rule, not a suggestion. A builder claiming a ticket checks the label first. A ticket still marked `tech_refine`, `product_refine`, or `team_refine` stays in `todo` no matter how ready the work looks otherwise.

## Findings

The phase file carries a Findings section alongside its tickets. This is the shared ledger `bossman-mode` refers to, and it is where the adversary files everything it hits.

Findings sit beside tickets rather than in their own file on purpose: a confirmed finding usually becomes a fix ticket, and that transition should not cross a file boundary.

```markdown
### F-2.1-02: Refusal path returns a fluent answer on zero graph hits

Status: confirmed
Raised by: adversary
Severity: high
Ticket: T-2.1-07 (fix)

What happened: query for a gene symbol that does not exist returned a
three-sentence summary with no citations instead of the refusal string.

History:
- 2026-08-02 adversary: filed, 4 of 20 hostile queries reproduce it
- 2026-08-02 judge: confirmed, this is the cite-or-refuse gate failing
- 2026-08-03 lead: opened T-2.1-07
```

| Status | Meaning | Who may set it |
|--------|---------|----------------|
| `filed` | Raised, not yet assessed | The adversary or whoever found it |
| `confirmed` | Real, reason required | Judge only, never the raiser |
| `rejected` | Not a defect, reason required | Judge only, never the raiser |
| `closed` | Fixed and verified, reason required | The designated closer, never the raiser |

The adversary over-reports on purpose, because a false alarm is cheap and a missed wrong answer is not. A high `rejected` rate is a healthy adversary, not a broken one.

Every confirmed finding that cost real time to diagnose also earns a `LEARNINGS.md` entry, so the next phase does not rediscover it.

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

### The board is the team's point of reference

Treat it the way a real team treats its board. A ticket is added when work is identified, moved to `in-progress` the moment someone picks it up, and moved on as it progresses. The board is not a report written at the end; it is the running state everyone reads to know what is happening.

That only works if updating it is cheap and the view is never stale, which is what the rendering pipeline below guarantees.

### Rendering: nobody writes HTML by hand

`tracker/render_board.py` is the only thing that writes the HTML views. It parses `BOARD.md` and emits both. An agent updates markdown; it never touches a generated page.

```bash
python3 tracker/render_board.py           # render both views
python3 tracker/render_board.py --check   # parse and report, write nothing
```

The renderer refuses to write when the board is malformed, and exits non-zero. That is deliberate: a stale page is better than a page that silently drops a phase. It rejects an unknown status, an unknown group, a duplicate phase id, a row with the wrong column count, and a flag count that disagrees with the Open flags table.

Automatic sync: `.claude/hooks/sync-board.sh` runs the renderer on every Edit or Write to a `.md` file under `tracker/`. An agent changes a ticket's status and the page updates with no command run and nothing to remember.

The known hole, and it is real: PostToolUse hooks fire on the Edit and Write tools only. An edit made through Bash, a `sed` or a heredoc, bypasses the hook and leaves the page stale. This exact failure hit `AGENTS.md` in this repo on 2026-07-26 and is recorded in `LEARNINGS.md`. Two mitigations, use both:

- Prefer the Edit tool for board files. Never `sed` a status change.
- `bossman-mode` re-runs the renderer explicitly at phase close, so a bypassed hook is caught within the phase rather than discovered by a confused reader.

Publish (`--publish`): render, then publish `tracker/board.body.html` as the artifact.

- Cadence: the local page regenerates on every board edit, since it is a local text transform and costs nothing. The artifact republishes at phase boundaries and on request, since it is a network call and a shared link does not need per-ticket granularity.
- Republish to the same URL rather than minting a new one, so a link shared once keeps working.
- Publish `board.body.html`, not `board.html`. The published page is wrapped in its own document shell, so it must not carry a doctype of its own.

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

- Acceptance criteria that are checkable, not aspirational, worded per Acceptance criteria wording below.
- The spec section it traces to. A ticket with no spec anchor is either scope creep or a missing spec section, and both need the lead, not a builder.
- Its dependencies by ticket ID.
- The exact files it may create or modify, so two builders never collide.
- A refinement label of `refined`. See Refinement labels above: the gate on `todo` to `in-progress` means work never starts on a ticket that has not cleared it.

## Acceptance criteria wording

Acceptance criteria are written as testable statements of a finished condition, never as tasks. "The button is blue" is a criterion. "Make this button blue" is a task.

The difference is not stylistic. A task tells you what someone intended to do. A criterion tells you how to decide the ticket is done. Only the second can be checked by someone who did not write it, which is the judge closing the ticket per the maker-cannot-sign-off split. "Add a timeout to cypher_query" is satisfied by any timeout at all, five seconds or five minutes, and by code that raises an exception but leaves the underlying connection open. "cypher_query returns a timeout error after 30 seconds and does not hang" is a testable statement: run it, wait 30 seconds, check the response and check the connection, done or not done, nothing to argue about.

| Task-shaped (bad) | Criterion-shaped (good) |
|--------------------|--------------------------|
| Add a timeout to cypher_query | cypher_query returns a timeout error after 30 seconds and does not hang |
| Make the guardrail catch prompt injection | The guardrail rejects a query containing an embedded instruction to ignore prior instructions, before the query reaches Think |
| Make sure answers have citations | Every claim in a synthesized answer carries source, source_id, source_url, and layer, or the agent returns the refusal string with no partial answer |
| Show users where an answer's information comes from | Every citation chip in the UI links to a live NCBI, PubTator3, or LitVar2 record page, not a truncated or dead URL |
| Handle rate limits in ncbi_dbsnp | ncbi_dbsnp retries once after a 429 response and returns a structured rate-limit error to the caller if the retry also fails |
| Make the Plan step choose tools correctly | For a query about a gene-disease relationship already in the graph, the Plan step selects cypher_query and does not call ncbi_efetch for the same fact |

Each right-hand column names a state that either holds or does not, with no reference to who did what. That is what makes it checkable by the judge instead of only by the builder who wrote it.

## Three-state permissions

Allow:
- Create, update, and read board and phase files without asking
- Decompose a phase into tickets from the tech spec's Section 25 row
- Append history lines and record evidence

Ask:
- Before creating a ticket that does not trace to a spec section, since that is either scope creep or a spec gap
- Before deferring a ticket at phase close
- Before moving a ticket out of `product_refine`, since that is the product owner's call

Deny:
- Never let a builder set its own ticket to `done`
- Never let whoever raised a finding be the one who confirms or closes it
- Never set a judgment state without a reason
- Never rewrite or delete history, only append
- Never open a phase whose dependency phases are not `done`
- Never invent a build phase that Section 25 does not define
- Never hand-edit `tracker/board.html` or the published artifact. They are generated from `BOARD.md` and the next regeneration discards the edit
- Never create a ticket with no refinement label
- Never move a ticket from `todo` to `in-progress` unless its refinement label is `refined`

The test: can the product owner read `tracker/BOARD.md` and know exactly what is done, what is in flight, what is blocked and why, without reading a single diff?
