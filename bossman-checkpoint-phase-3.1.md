# Bossman checkpoint: build phase 3.1, ncbi_efetch

Written 2026-08-05. Branch `phase/3.1-ncbi-efetch`, not pushed, no pull request opened.

This file exists because the lead session reached its context budget mid-phase. It is the handoff. Read it with `tracker/phase_3.1.md`, which holds the tickets and the full findings ledger.

## Where the phase actually stands

| Stage | State |
|-------|-------|
| 3, decompose | Done. Thirteen tickets, three added after a research pass found gaps |
| 5, premise gate, BLOCKING | Done. Written first, watched failing at 15 of 16, failure direction verified |
| 6, 7, build | Done. All thirteen tickets built and merged to the phase branch |
| 8, judge | Done, round 1 returned FAIL. Three criticals, seven majors, four minors |
| 8b, fixes | Five findings fixed and verified. Six remain open |
| 9, adversary | Done, round 1. Fifteen findings, five critical, every one reproduced live. All OPEN |
| 8c, re-review | NOT RUN. Required: the fixer never closes its own findings |
| 10, gates | Partially run. See counts below |
| 11, ship | NOT RUN |

The phase cannot merge. A judge FAIL is not cleared by fixing; a re-review has to clear it.

## Verified numbers, each run by the lead rather than taken from a builder report

| Check | Result |
|-------|--------|
| Full Python suite | 1539 passed, 82 skipped, 1 xfailed (baseline at phase start: 1324) |
| Live premise gate | 19 passed, 1 skipped |
| `ruff check src/` | Clean |
| Doc drift | 7 stale counts, expected, synced at phase close |
| Learnings coverage | Passes, but trivially. See the caveat below |

The premise gate's one skip is case 16, the end-to-end case, which skips on graph-tunnel reachability by design.

## The one decision blocking phase close

Finding F-3.1-04, critical, still open, and it is a scope question rather than a bug.

`ncbi_efetch` is never dispatched as an answer-bearing tool. It has exactly two call sites in the whole source tree, both inside entity resolution. `act_node` dispatches only `cypher_query`. So no NCBI record ever becomes a citation, reaches the Write step, or is subject to cite-or-refuse. The tool's schema sits in the stable prompt prefix but is inert.

The phase premise reads: "A question the graph cannot answer reaches a live NCBI API, comes back as real records, and is either cited from what the API actually returned or refused." The first half of that is not met.

Two honest options, and the choice belongs to the product owner:

- Wire the Act step and the Layer 2 citation gate inside this phase. Meets the premise as written. It is real additional work: tool selection, a Layer 2 `CitationPayload`, provenance, and the trust gate.
- Carry it to a named ticket and close 3.1 as the tool plus resolution. Defensible, since Section 25 groups provenance and the two-tier trust gate across 3.0 to 3.5 rather than inside 3.1. It requires restating the phase premise, and that must be recorded as a deliberate narrowing, never a silent edit.

What is NOT acceptable is quietly rewriting the premise so the current state passes. That is the verify-surface weakening `goal-contracts` forbids.

## Why the premise gate did not catch this

Worth carrying forward, because it is a gate design lesson rather than a code defect.

The gate passes 19 of 20 while no NCBI record can reach an answer. It calls the tool directly through its `_run` helper, and its single production-path case, case 16, is also its only skippable case, because it needs the graph tunnel.

So the gate tests the component, not the system. That is build phase 2.1's blind-spot lesson in a new shape: a gate written to catch a composition defect that itself cannot see one. Any future tool phase should ensure at least one production-path case that does NOT depend on an unavailable resource.

## Open findings, none closeable by whoever fixes them

Full detail in `tracker/phase_3.1.md`. Summary:

- F-3.1-04, critical: the premise gap above.
- PubChem records ship `source_url=None`, because the schema's host pattern is narrower than `production-standards.md`'s own canonical example. Not a live violation, since no PubChem record reaches synthesis. It becomes one the moment it is wired.
- `ncbi_efetch.py`'s docstring claims the Act step wraps it in `harness.enforce_timeout`, which is false as shipped.
- `_generic_summary_fields` copies every response key for five databases, bounded only by a key count.
- The tool registry changed the stable prefix with no contract-version bump.
- Four minors: a 429 lands in the unparseable-body branch, four property-claiming comments with no enforcing test, no `start <= end` validator, and no per-value character cap in four of five extraction paths.

## Caveat on the learnings coverage gate

`python tracker/check_learnings_coverage.py 3.1` reports "nothing to cover" and passes. It only recognizes the literal statuses `confirmed` and `closed`, and this repo's convention, in build phase 3.0 and again here, writes `fixed, needs an independent closer` or `open`. So the gate passes trivially and is not evidence that learnings were written.

They were written regardless: four new LEARNINGS.md rows. But the check itself is not doing the job it was added to do, which is worth fixing before it is trusted again.

## The scope decision, taken 2026-08-05

The product owner chose to CARRY the Act-step wiring to a named 3.x ticket rather than build it inside 3.1. Section 25 groups provenance and the two-tier trust gate across 3.0 to 3.5 rather than inside 3.1, so this is a defensible narrowing.

The obligation that comes with it, and it is not optional: the phase premise must be explicitly RESTATED to what 3.1 actually delivers, recorded as a deliberate narrowing with a named owner for the carried half. Editing the premise quietly so the current state passes is the verify-surface weakening `goal-contracts` forbids, and it is the difference between a scoping decision and a cover-up.

## Running the rest on the metered backend, decided 2026-08-05

The primary provider is at 97 percent of its weekly limit, so the remaining work runs on `claude-build`. What that changes, stated precisely rather than as a blanket warning:

- Safe to hand over: fixing every open finding, verifying each against its own written reproduction, re-running the suite and the gates, syncing doc drift, and opening the pull request. The discovery work is already done, and each finding carries a file:line and a pasted reproduction, so closing one is checkable rather than a judgment call.
- Genuinely degraded: an adversarial pass over the NEW code the fix round writes. Today's evidence is why. The builders' suites were green and the judge found three criticals; the judge passed and the adversary then found five more, including a tool emitting real citations for records that do not exist. Both rounds were frontier-model reasoning finding defects that tested, green code was hiding.

So the rule for this phase: the fix round may go all the way to an open pull request. It must NOT merge. The pull request carries one known caveat, which belongs in its description: the fix round has not had an adversarial pass, and twenty-one patches across security-sensitive code is exactly where this repo's history says the next critical lives (build phase 2.1 had the same invariant defeated three separate times by its own replacement).

One short primary session clears that caveat later. Nothing is deployed and no user outside the product owner has access, so an unmerged pull request costs time-to-merge and nothing else.

## What the next session should do, in order

1. Restate the phase premise in this file's Phase premise section, with a dated note that the answer-path half is carried, and open the ticket that owns it.
2. Work the 21 open findings. Five adversary criticals come first: the fabricated ESummary citation, the lookup budget eaten by English words, the `chr1` spelling returning empty, ELink errors read as no-results, and taxon being discarded. Then the URL parameter injection, which is live-confirmed.
3. Re-run the premise gate. Note that adversary finding 2 shows gate case 14 PASSES while the behavior it pins is wrong, so that case needs rewriting, and rewriting it is strengthening rather than weakening.
4. Run an independent re-review to close the fixed findings. The fixer never closes its own.
5. Re-run the gates, sync doc drift, then `/phase-checkpoint` and `/ship`.

## Why this phase is not close to merging

Twenty-one findings are open across the two review rounds, eight of them critical. The pattern across both rounds is one thing: this tool talks to a live external API, and every critical came from the gap between what the API actually returns and what someone believed it returns. Two of the criticals were hidden by fixtures hand-written from documentation, which tested the author's belief rather than the interface.

That is the transferable lesson for build phases 3.2 to 3.5, which are four more Layer 2 and Layer 3 tools: capture fixtures from live responses, never author them from a reading of the docs.

Do not dispatch a judge and an adversary concurrently. LEARNINGS.md row 44: two frontier reviewers sharing one session limit are one failure, not two.
