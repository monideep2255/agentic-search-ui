# Handoff: build phase 5.0, observability

Written 2026-08-29 at a deliberate stopping point. Branch `phase/5.0-observability`, 21 commits, tree clean, pushed.

This file orients someone starting cold. It is deliberately NOT the source of truth: `requirements/phase_6/Continuation_prompt.md` is, per `CLAUDE.md`, and where the two ever disagree that file wins. Everything below points into the real records rather than restating them, because two documents describing the same phase drift, and this phase has already paid five rounds for the cost of a confident sentence that stopped being true.

## Table of contents

- [The one next action](#the-one-next-action)
- [What this phase delivers](#what-this-phase-delivers)
- [State at the cut](#state-at-the-cut)
- [What is deliberately left open](#what-is-deliberately-left-open)
- [Two decisions not to reverse](#two-decisions-not-to-reverse)
- [What this cost, and the two lessons worth carrying](#what-this-cost-and-the-two-lessons-worth-carrying)
- [Where to read more](#where-to-read-more)

## The one next action

Finish F-5.0-28, then close the phase: gates, then `/phase-checkpoint`, then `/ship`.

F-5.0-28 is the only unfinished work. The "fifth family", a deferred `__str__` object that survives redaction and is materialized later by serialization, is CLOSED in `observability/audit.py` and still OPEN in `observability/tracing.py`. Close it the way `audit.py` does, as an ORDER change so the value rule sees what serialization would produce, never as another pattern. It is minor and NOT reachable at any of the four anonymizer entry points today, which is what made this a safe place to stop.

Do not re-plan the phase, do not re-run the research, do not reopen the design. All of it is on disk.

## What this phase delivers

Tech spec Section 20, in full. Three records, each with one job, so no single outage blinds the whole picture:

- LangSmith per-run tracing, Section 20.1, joined to everything else on `trace_id`. Live and verified against the real service, with account PII proven absent by reading traces back OUT rather than by asserting it locally.
- PostHog behavioral analytics, Section 20.2, aggregates only. Wired, with the correct `phc_` project token in place.
- The append-only JSONL tool-call audit log, Section 20.3, one durable line per Layer 1, 2 and 3 access with its authorization.

## State at the cut

| What | Value |
|---|---|
| Observability suite | 207 passed, 1 skipped |
| Full Python suite | 4364 passed, 171 skipped, 1 xfailed, 0 failed |
| `ruff check`, whole repository, no path | clean |
| Review rounds run | one judge, one adversary, five fix-and-verify |
| Findings filed | 28 in the phase file, plus 30 from the adversary |

Two gates are known-red and deliberately deferred. Neither is a defect:

- `check_doc_drift.py` reports 11 stale counts, the test, decision and learnings figures in `CLAUDE.md`, `AGENTS.md` and the continuation prompt. That is `/phase-checkpoint`'s job and it is held until the count stops moving.
- The board's flag list for phase 5.0 still shows the four flags filed at phase open rather than the final open set.

## What is deliberately left open

Carried forward with named owners rather than dropped quietly.

- F-5.0-24: the analytics event is `await`ed INLINE on the query path, so a slow PostHog slows a user's search. Diagnosed at `core/run.py:346` and `app.py:1851`, with the patch written out in the tracker. NOT applied because it necessarily breaks `test_analytics.py`, whose arms assert on a recording spy immediately after the await, and that file was outside the fixing agent's scope. Recommended scope: `analytics.py` plus `test_analytics.py`, with a timing arm and a mutation reverting `create_task` to a bare `await`.
- A-5.0-14: an ordinary string under an ordinary key still reaches LangSmith unredacted. Declared in `redact_payload`'s own docstring. Confirmed reachable on the wire, and confirmed that no credential reaches it today, since all producers are static literals.
- Roughly 20 minor adversary findings, all in `tracker/phase_5.0_adversary_report.md`.
- One item for the product owner, which no code change substitutes for: revoke the old `phx_` PostHog personal key. It has been removed from `.env` and its local backup deleted, and nothing depends on it.

## Two decisions not to reverse

The audit hook sits at the three TRANSPORT chokepoints, never at `act_node`. Five production call sites reach a data layer without passing through `act_node`, and a live query proved it rather than a test: the first audit line written was `think_node`'s symbol resolution. The transport is also the only place Section 20.3's required HTTP status and latency exist, since both are discarded before a tool returns. Two premise arms drive the real bypass callers by name.

The error field is BOUNDED, not scanned. Both the audit sink and the LangSmith path discard free text and keep only a classified code and an exception class name. Three rounds of scanning were each defeated by an input of the same family.

## What this cost, and the two lessons worth carrying

Five fix-and-verify rounds on one control, three Rule 4 stops, and a design reversal authorized by the product owner. Four consecutive rounds each shipped a fix that was then defeated by an input of the SAME family: something upstream consuming the credential before the check saw it. The reversal that finally worked was to stop scanning text and bound what may enter the sink instead, which is `attack-the-constraint` applied to a check: when a check keeps losing to inputs of one shape, change what it is checking rather than hardening it again.

The most transferable result is a critique of the lead's own decomposition, not of any line of code. The phase spent four rounds hardening the LOCAL audit sink's error field because exception messages carry credentials, and shipped the identical string OFF-BOX to LangSmith with no control at all. Four rounds on the best-defended field on the line. Both the judge and the adversary found it independently; neither the lead nor any fix agent did, because every round was scoped from the file the previous round had been editing rather than from where credentials actually flow.

The second, on method. The lead filed F-5.0-16 reporting nine characters that terminated a credential value. It was one defect wearing nine costumes: every probe carried the same `url=` prefix, which alone defeats the scan whatever character follows. Varying one thing teaches you about that thing only if everything else is genuinely inert. A fix agent DISPUTED that finding with evidence and was half right, and the disagreement is what surfaced the real defect, F-5.0-19. Had the agent deferred to the lead, it would have shipped.

## Where to read more

| Document | What it holds |
|---|---|
| `requirements/phase_6/Continuation_prompt.md` | THE SOURCE OF TRUTH for what to do next. Read this before acting |
| `tracker/phase_5.0.md` | Goal contract, ticket table, 28 findings, full history of every round |
| `tracker/phase_5.0_adversary_report.md` | 1120 lines, 30 findings. The exposure map, and the reason the final round was scoped correctly |
| `tracker/phase_5.0_judge_report.md` | 691 lines. The scripted verification, 23 independent source-level mutations |
| `LEARNINGS.md` | What broke and what fixed it, this phase included |
| `DECISIONS.md` | Five decisions this phase made, dated 2026-08-29 |
