# Handoff: build phase 5.0, observability

THIS PHASE IS MERGED. Build phase 5.0 merged as PR #83 on 2026-08-30 with all four CI gates green, and the branch `phase/5.0-observability` is deleted. THIS FILE IS NOW A HISTORICAL RECORD, not an instruction. Do not work "Start here" below: every step in it describes a branch that no longer exists.

If you are looking for what to do next, read `requirements/phase_6/Continuation_prompt.md`. It is the source of truth, and its next action is build phase 5.1, the 50-query golden dataset and the eval harness.

The rest of this file is kept unedited below because of what it got wrong, which is more useful than what it got right. It told the next session to finish F-5.0-28, and F-5.0-28 was already done: its fix, its two arms, its mutation case and its `fixed` status had all landed in the very commit whose message said the fix was not in. The session that wrote this file had genuinely re-probed rather than inferring from the diff, and still concluded wrongly, because it varied the KEY rather than the control. Full account: F-5.0-29 in `tracker/phase_5.0.md`, and the 2026-08-30 entry in `LEARNINGS.md`.

Written 2026-08-29 at a deliberate stopping point, corrected 2026-08-30 when the stated next action turned out to be already done, and closed 2026-08-30 at the merge.

## Start here

Four steps. None is optional and the first cannot be undone later.

1. Know which session you are in. Run `echo "${ANTHROPIC_BASE_URL:-primary provider}"`. If it prints `primary provider` you are on the subscription and every stage is available. If it prints a URL you are on the metered backend, where a session-wide subagent model silently overrides per-dispatch choices, so a judge would run on a builder's model and nothing would report it. Read "Which session to open" in the continuation prompt before doing anything else. The choice cannot be changed inside a running session.
2. Get on the branch and confirm the state matches this file:

   ```bash
   git checkout phase/5.0-observability && git pull
   git status --short          # expect clean
   source venv/bin/activate
   python3 tracker/preflight.py    # expect all three transports ok
   ```

3. Read the two sections below, "The one next action" and "What is deliberately left open". Together they are the whole remaining scope.
4. Act. Do not re-plan the phase, do not re-run the research, do not reopen the design. All of it is on disk and every round is recorded.

If `git status` is not clean, or the suite figures below do not reproduce, STOP and say so rather than building on a state this file does not describe.

## Table of contents

- [Start here](#start-here)
- [The one next action](#the-one-next-action)
- [What this phase delivers](#what-this-phase-delivers)
- [State at the cut](#state-at-the-cut)
- [What is deliberately left open](#what-is-deliberately-left-open)
- [Two decisions not to reverse](#two-decisions-not-to-reverse)
- [What this cost, and the two lessons worth carrying](#what-this-cost-and-the-two-lessons-worth-carrying)
- [Where to read more](#where-to-read-more)

## The one next action

Close the phase: gates, then `/phase-checkpoint`, then `/ship`. There is no code left to write.

F-5.0-28 IS DONE, and this section said otherwise until 2026-08-30. The fix, its two arms, its mutation case, its `fixed` status and its History entry all landed in commit `53be4cb`, whose own message says "fix not yet in". Re-measured on this branch rather than inferred from the diff: `redact_payload({"error": obj})` for an object whose `__str__` yields the `kg_reader` DSN returns `[redacted error]`, `json.dumps(result, default=str)` does not carry the secret, the observability suite is `213 passed, 1 skipped`, and mutation case 22 passes, so the arm is proven able to go red rather than merely green.

What the previous session's re-probe actually found is real and is a DIFFERENT item: a deferred-`__str__` object under an ORDINARY key still survives, `redact_payload({"note": obj})` returns the object unchanged. That is A-5.0-14, listed below under "What is deliberately left open", not the error-key branch F-5.0-28 named. One probe varying the key was read as evidence about the fix, which is this phase's own F-5.0-16 lesson arriving a second time.

Filed as F-5.0-29 in `tracker/phase_5.0.md`. The commit message is NOT amended: it is published, and `git-workflow` forbids amending a published commit, so the durable record is the tracker rather than `git log`.

Do not re-plan the phase, do not re-run the research, do not reopen the design. All of it is on disk.

## What this phase delivers

Tech spec Section 20, in full. Three records, each with one job, so no single outage blinds the whole picture:

- LangSmith per-run tracing, Section 20.1, joined to everything else on `trace_id`. Live and verified against the real service, with account PII proven absent by reading traces back OUT rather than by asserting it locally.
- PostHog behavioral analytics, Section 20.2, aggregates only. Wired, with the correct `phc_` project token in place.
- The append-only JSONL tool-call audit log, Section 20.3, one durable line per Layer 1, 2 and 3 access with its authorization.

## State at the cut

| What | Value |
|---|---|
| Observability suite | 213 passed, 1 skipped, re-measured 2026-08-30 |
| Full Python suite | 4364 passed, 171 skipped, 1 xfailed, 0 failed |
| `ruff check`, whole repository, no path | clean |
| Review rounds run | one judge, one adversary, five fix-and-verify |
| Findings filed | 29 in the phase file, plus 30 from the adversary |

Two gates are known-red and deliberately deferred. Neither is a defect:

- `check_doc_drift.py` reports 11 stale counts, the test, decision and learnings figures in `CLAUDE.md`, `AGENTS.md` and the continuation prompt. That is `/phase-checkpoint`'s job and it is held until the count stops moving.
- The board's flag list for phase 5.0 still shows the four flags filed at phase open rather than the final open set.

## What is deliberately left open

Carried forward with named owners rather than dropped quietly.

- A-5.0-24: the analytics event is `await`ed INLINE on the query path, so a slow PostHog slows a user's search. Diagnosed at `core/run.py:346` and `app.py:1851`, with the patch written out in the tracker. NOT applied because it necessarily breaks `test_analytics.py`, whose arms assert on a recording spy immediately after the await, and that file was outside the fixing agent's scope. Recommended scope: `analytics.py` plus `test_analytics.py`, with a timing arm and a mutation reverting `create_task` to a bare `await`.
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
