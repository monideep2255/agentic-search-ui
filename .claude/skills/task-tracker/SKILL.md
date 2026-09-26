---
name: task-tracker
description: Maintain the in-repo build record, the phase ledgers under tracker/ (tickets, acceptance criteria, status, evidence, an append-only history per ticket) beside the board of cards in testing/UI_fix_plan.md. Use when opening a numbered phase, when a builder finishes or blocks, when the product owner asks what the status is, and at every checkpoint. TRIGGER on "open the ledger", "what is in flight", "status of phase N", "add a ticket", "mark done". Distinct from phase-checkpoint (planning documents at a boundary) and from LEARNINGS.md (what broke, not what is assigned).
argument-hint: "[--open N.M] [--status] [--close TICKET-ID]"
---

# Task tracker

The build record. A running, in-repo account of what is planned, in flight, blocked, and done, so the product owner can see state without reading a diff and the lead can resume a phase after a context reset.

Decision from Step 1.8 chose a self-maintained in-repo tracker over Linear. This skill is that tracker.

## Table of contents

- [Where the record lives](#where-the-record-lives)
- [Ticket format](#ticket-format)
- [Status states and who may set them](#status-states-and-who-may-set-them)
- [Refinement labels](#refinement-labels)
- [Findings](#findings)
- [The four ledger rules](#the-four-ledger-rules)
- [Operations](#operations)
- [What a ticket must carry before work starts](#what-a-ticket-must-carry-before-work-starts)
- [Acceptance criteria wording](#acceptance-criteria-wording)
- [Three-state permissions](#three-state-permissions)

## Where the record lives

| Path | What it holds | Kind |
|------|---------------|------|
| `testing/UI_fix_plan.md` | The board for current work: To do, Build in progress, Retest, one card per change, written before it is built | Source of truth |
| `tracker/phase_N.M.md` | One file per numbered phase: goal contract, budget with the dispatch table, tickets in full, history, findings | Source of truth |
| `tracker/BOARD.md` | Frozen on 2026-09-25 as the record of build phases 1.0 through 6.2. No row is added for anything after 6.2 | Record |
| `tracker/board.html` | The rendered page of the frozen board | Generated view, a record |
| The published artifact | The same frozen board hosted | Generated view, a record |

Markdown is canonical: it is diffable and reviewable in a pull request, and an agent can write it mid-run. The two HTML views were generated from the frozen board and are never hand-edited.

Build phases through 7.1 and their dependencies come from `requirements/Technical_specification.md` Section 25, which says what each delivers and what it depends on. Phases after 7.1 are bundles of board cards the product owner approved as one phase, numbered in order from 8.1 (2026-09-25). They live as ledgers only. Nobody invents a phase.

Two boards became one on 2026-09-25 (build harness review, D3): `tracker/BOARD.md` had no row for any 8.x phase and could not hold one, since its rows come from Section 25, so it was frozen at 6.2 and `testing/UI_fix_plan.md` is the board people read. Per-phase files rather than one large board: a phase file can be read on its own by an agent that needs only its own phase.

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

Ticket IDs are `T-<phase>-<NN>`, stable once assigned, never reused. A ticket for a card whose cause is unknown is a diagnosis ticket: its acceptance is the written diagnosis, and a fix ticket opens only after the lead has read it (`.claude/skills/bossman-mode/reference/Phase_execution.md`, step 3).

## Status states and who may set them

One writer per state. This is the rule that keeps parallel agents from corrupting each other's work.

| Status | Meaning | Who may set it |
|--------|---------|----------------|
| `todo` | Scoped, not started | Lead only |
| `in-progress` | Claimed and being worked | The builder that claimed it |
| `blocked` | Cannot proceed, reason required | The builder that hit the block |
| `in-review` | Builder done, awaiting the judge where the dial runs one, then the owner's verdict | The builder that finished |
| `rejected` | Judge or adversary found a defect, reason required | Judge only |
| `done` | The judge passed with evidence where a judge ran, then the product owner's retest on develop approved it (the cadence's stage 11) | The lead records the owner's verdict; never the builder, and never on a judge pass alone |

The builder that did the work never marks it done. That is the maker-cannot-sign-off split from `self-eval-loop.md`, applied to the record.

`rejected` is transient and deliberately has no column. The judge sets it with a reason and files the defect in Findings, and the ticket returns to `in-progress` in the same move. Work flows backward on a rejection, it does not park. A ticket sitting in `rejected` at the end of a session means someone stopped halfway through the transition.

## Refinement labels

Every ticket carries exactly one refinement label from the moment it is created. Without one it gets lost in the backlog: there is no way to tell whether anyone has looked at it, so it sits in `todo` alongside tickets that are actually ready. A ticket with no refinement label is invalid, the same way a judgment state with no reason is invalid.

| Label | Meaning | Who sets it |
|-------|---------|-------------|
| `tech_refine` | Still being refined, not yet discussed in the tech refinement meeting | Lead, at ticket creation |
| `product_refine` | Needs the product owner's input before it can proceed | Lead, when a question surfaces that only the product owner can answer. Only the product owner's answer moves it forward |
| `team_refine` | Ready for the team to review | Lead, once tech refinement and any product question are resolved |
| `refined` | Passed refinement, ready to be worked | Lead, once the team's review raises no blocking feedback |

`refined` is not one of the product owner's three labels. It is added here to complete the lifecycle. Without a positive "done refining" state, a ticket that finished refinement would have to lose its label rather than advance one. That loses the trail of how it got there. Every other label describes a ticket still moving through refinement. `refined` is the one state that says refinement is over.

A ticket moves through the labels in order: `tech_refine`, then either `product_refine` if it needs product input or straight to `team_refine`, then `refined`. Each move appends a history line the same as any other ticket change.

Refinement gate: a ticket cannot move from `todo` to `in-progress` unless its refinement label is `refined`. This is the whole point of the labels, so it is a rule, not a suggestion. A builder claiming a ticket checks the label first. A ticket still carrying any other label stays in `todo` no matter how ready the work looks otherwise.

## Findings

The phase file carries a Findings section alongside its tickets. This is the shared ledger `bossman-mode` refers to, and it is where the adversary files everything it hits.

Findings sit beside tickets rather than in their own file on purpose: a confirmed finding usually becomes a fix ticket, and that transition should not cross a file boundary.

```markdown
### F-2.1-02: Refusal path returns a fluent answer on zero graph hits

Status: confirmed
Raised by: adversary
Severity: high
Round: 1
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

### Two fields the review budget needs

`bossman-mode`'s review budget caps a phase at two rounds and stops it the moment a fix regresses. Neither is enforceable unless the ledger records them, so two fields are mandatory on every finding.

`Round: N` names the review round that raised it. Round 1 is the judge and adversary pass and round 2 is the fix-and-reverify pass. There is no round 3: a blocking finding in round 2 escalates to the product owner instead. Without this field the round count has to be reconstructed by counting report files afterwards, which is how build phase 4.2 reached six rounds before anyone noticed the shape.

`Regression of: F-N.M-XX` is required whenever the finding sits inside code written to fix an earlier finding in the same phase. It is the single highest-value field in this file. Across build phases 2.1 and 4.2 (eleven review rounds between them), every round's worst defect was a regression in the previous round's fix. Nothing in the ledger said so, and each round therefore read as fresh scrutiny finding fresh problems rather than as one unresolved fix approach failing repeatedly.

A finding carrying `Regression of` is a stop condition, not a queue item: the phase escalates on the spot without finishing the round.

Both fields are set by whoever files the finding. Neither is a judgment state, so neither needs a reason line, and the `Regression of` link is a factual claim about where the code came from that the judge verifies like any other.

Every confirmed finding that cost real time to diagnose also earns a `LEARNINGS.md` entry, so the next phase does not rediscover it.

## The four ledger rules

These come from the shared-ledger convention already in `bossman-mode`, made concrete here:

- Single writer per state: each status has exactly one role authorized to set it, per the table above. No status has two writers.
- Mandatory reason on judgment states: `blocked`, `rejected`, and `done` each carry a one-line reason. A bare status change with no reason is invalid.
- Append-only history: every transition appends a dated who-what-why line. History is never rewritten, only extended.
- The raiser never closes: whoever raised a ticket or filed a defect is never the one who closes it.

## Operations

Open a phase (`--open N.M`):
1. Read what the phase delivers and what it depends on: its row in `requirements/Technical_specification.md` Section 25, or, for a phase after 7.1, the board cards the product owner approved as one phase.
2. Verify every dependency phase is done: in its ledger, or on the frozen board for a phase through 6.2. If not, stop and report.
3. Read `LEARNINGS.md` for entries tagged to this phase or its tools before scoping anything.
4. Decompose the phase into tickets. Each gets acceptance criteria traced to a spec section or an approved card. A card whose cause is unknown gets a diagnosis ticket and nothing else.
5. If the phase changes answer behaviour, its premise check is the golden consistency run after merge, which blocks (`.claude/skills/bossman-mode/reference/Product_review.md`). Where the golden questions cannot see the behaviour, the phase may add a premise gate as its FIRST ticket, blocking every other ticket, with the fixed acceptance criteria in that file's "Why the golden run is the premise check": no mocked model, meaning not shape, pinned live ground truth, the way production runs, a statement of the shapes it exercises and omits, and SEEN FAILING before any other ticket opens. Nothing outside answer behaviour gets a premise gate.
6. Create `tracker/phase_N.M.md` with the sections in `.claude/skills/bossman-mode/reference/Phase_execution.md`, "The phase ledger". The board is frozen, so no row is added to it; the phase's cards move to Build in progress on `testing/UI_fix_plan.md`.

Status (`--status`): print the open ledgers' tickets grouped by status, blocked tickets first with their reasons, then the board's Build in progress column.

Close a ticket (`--close`): record the evidence in the ticket's Evidence block (the judge's, where a judge ran) and append the history line. Leave the ticket at `in-review`; `done` is set when the lead records the owner's verdict.

Phase close: every ticket in the phase file is `done` or explicitly deferred with a reason. A phase with an open ticket is not complete, regardless of what the builders reported.

A phase premise claim cites the golden run or the premise gate, never a suite total. Build phase 2.1 closed once on "798 tests passing and 9 live-graph tests green", which was true, and the phase was then found to answer 3 of 8 real questions correctly. A count of passing tests is evidence about the tests.

### The record is the team's point of reference

Treat it the way a real team treats its board. A ticket is added when work is identified and moved to `in-progress` the moment someone picks it up. It moves on as it progresses. The record is not a report written at the end; it is the running state everyone reads to know what is happening.

That only works if updating it is cheap, which a markdown ledger and a markdown board are.

### Rendering: the frozen board's page

`tracker/render_board.py` is the only thing that ever wrote the HTML views, and it parses `tracker/BOARD.md` alone. Since the board is frozen, the renderer runs only if the frozen record is corrected, which it should not be.

```bash
python3 tracker/render_board.py           # render both views
python3 tracker/render_board.py --check   # parse and report, write nothing
```

The renderer refuses to write when the board is malformed, and exits non-zero. That is deliberate: a stale page is better than a page that silently drops a phase. It rejects:

- An unknown status.
- An unknown group.
- A duplicate phase id.
- A row with the wrong column count.
- A flag count that disagrees with the Open flags table.

The hook that ran the renderer on every Edit or Write under `tracker/` is removed from `.claude/settings.json` under the product owner's item-by-item approval of 2026-09-25 (DECISIONS.md), the board file staying as history. The hook's known hole is recorded in `LEARNINGS.md` (2026-07-26): it fired on the Edit and Write tools only, so an edit made through Bash left the page stale.

Publish (`--publish`): render, then publish `tracker/board.body.html` as the artifact, republishing to the same URL so a link shared once keeps working. Publish `board.body.html`, not `board.html`: the published page is wrapped in its own document shell, so it must not carry a doctype of its own. With the board frozen this is a republish of a record, on request only.

### What the frozen board's page encodes visually

Form carries state, not just number, so what needs attention reads at a glance:

- Status is a column and a color: done, in progress, blocked, to do.
- Group is a tag: planning, prototype, v1.
- Dependencies are chips, so a phase that cannot start yet shows why.
- Gates are chips, marking a phase that had to clear `eval-harness`, `dev-standards`, or Playwright before it shipped.
- Product owner required is its own chip, deliberately not a flag. It is a property of the phase, not a problem to resolve, and conflating the two makes the open-flag count lie.
- Flags are unresolved problems that block their phase. This count must reconcile with the flags table.

## What a ticket must carry before work starts

A ticket dispatched without these is under-specified, and an under-specified ticket is how autonomous work drifts:

- Acceptance criteria that are checkable, not aspirational, worded per Acceptance criteria wording below.
- The spec section or approved card it traces to. A ticket with no anchor is either scope creep or a missing spec section, and both need the lead, not a builder.
- Its dependencies by ticket ID.
- The exact files it may create or modify, so two builders never collide.
- A refinement label of `refined`. See Refinement labels above: the gate on `todo` to `in-progress` means work never starts on a ticket that has not cleared it.

## Acceptance criteria wording

Acceptance criteria are written as testable statements of a finished condition, never as tasks. "The button is blue" is a criterion. "Make this button blue" is a task.

The difference is not stylistic. A task tells you what someone intended to do. A criterion tells you how to decide the ticket is done. Only the second can be checked by someone who did not write it, which is the judge or the owner closing the ticket per the maker-cannot-sign-off split.

"Add a timeout to cypher_query" is satisfied by any timeout at all (five seconds or five minutes) and by code that raises an exception but leaves the underlying connection open. "cypher_query returns a timeout error after 30 seconds and does not hang" is a testable statement: run it, wait 30 seconds, check the response and check the connection. Done or not done, nothing to argue about.

| Task-shaped (bad) | Criterion-shaped (good) |
|--------------------|--------------------------|
| Add a timeout to cypher_query | cypher_query returns a timeout error after 30 seconds and does not hang |
| Make the guardrail catch prompt injection | The guardrail rejects a query containing an embedded instruction to ignore prior instructions, before the query reaches Think |
| Make sure answers have citations | Every claim in a synthesized answer carries source, source_id, source_url, and layer, or the agent returns the refusal string with no partial answer |
| Show users where an answer's information comes from | Every citation chip in the UI links to a live NCBI, PubTator3, or LitVar2 record page, not a truncated or dead URL |
| Handle rate limits in ncbi_dbsnp | ncbi_dbsnp retries once after a 429 response and returns a structured rate-limit error to the caller if the retry also fails |
| Make the Plan step choose tools correctly | For a query about a gene-disease relationship already in the graph, the Plan step selects cypher_query and does not call ncbi_efetch for the same fact |

Each right-hand column names a state that either holds or does not, with no reference to who did what. That is what makes it checkable by someone other than the builder who wrote it.

## Three-state permissions

Allow:
- Create, update, and read ledger files and the board without asking
- Decompose a phase into tickets from its Section 25 row or its approved cards
- Append history lines and record evidence

Ask:
- Before creating a ticket that does not trace to a spec section or an approved card, since that is either scope creep or a gap
- Before deferring a ticket at phase close
- Before moving a ticket out of `product_refine`, since that is the product owner's call

Deny:
- Never let a builder set its own ticket to `done`
- Never let whoever raised a finding be the one who confirms or closes it
- Never set a judgment state without a reason
- Never rewrite or delete history, only append
- Never open a phase whose dependency phases are not `done`
- Never invent a build phase: through 7.1 Section 25 defines them, and after 7.1 the product owner's approval of a set of cards does
- Never add a row to `tracker/BOARD.md`. It is frozen at build phase 6.2
- Never hand-edit `tracker/board.html` or the published artifact. They were generated from `BOARD.md`
- Never open a fix ticket for a card whose cause nobody has written down
- Never create a ticket with no refinement label
- Never move a ticket from `todo` to `in-progress` unless its refinement label is `refined`

The test: can the product owner read `testing/UI_fix_plan.md` and the open ledgers and know exactly what is done, what is in flight, what is blocked and why, without reading a single diff?
