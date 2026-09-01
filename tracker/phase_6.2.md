# Build phase 6.2: answer readability and the single UI pass

Branch: `phase/6.2-answer-readability-ui-pass`. Opened 2026-09-01.

Delivers the complete contents of `UI_feedback.md`: the answer-readability defect that makes
every disease answer unusable, and the five interface complaints a real person raised against
the live product on 2026-08-31. Depends on build phases 2.1, 3.1, 4.9 and 4.16, all merged.

THIS PHASE IS NOT IN SECTION 25, and that is a stated exception rather than a breach. See
"Why this is a phase at all" below.

## Table of contents

- [Why this is a phase at all](#why-this-is-a-phase-at-all)
- [What was measured before any ticket was written](#what-was-measured-before-any-ticket-was-written)
- [The correction to the brief](#the-correction-to-the-brief)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [Findings](#findings)
- [History](#history)

## Why this is a phase at all

`tracker/BOARD.md` carried no open phase on 2026-08-31, and `requirements/phase_6/Continuation_prompt.md`
recorded a product-owner decision that the unit of work was no longer a build phase. That
decision named its own reversal condition in the same paragraph: a genuinely phase-sized
deliverable.

This is that deliverable, and the product owner's own reasoning in `UI_feedback.md` is the
argument for it:

- Fixing these items piecemeal means some are fixed and some remain, and every partial pass
  requires re-testing the whole surface.
- This is a show piece. It needs to be right as a whole, not right in patches.

Section 25 has no row for defects a live user hits, which is the same gap build phase 4.16
was inserted to fill. Both locked documents stay unedited until the next reconciliation, per
`v1-scope-boundary`. Product-owner decision, 2026-09-01, logged in `DECISIONS.md`.

Numbering: 6.2 rather than 4.17, because 4.x is the delivery-surfaces group and this is not a
delivery surface. 6.1 is a real Section 25 phase that still exists in the specification, so
its number is not free.

## What was measured before any ticket was written

Measured 2026-09-01 against the live graph, live NCBI and the shipped source, before any
ticket was scoped. Stated as rows so a later reader can check each independently.

| Claim | State | Evidence |
|---|---|---|
| Disease nodes carry the source vocabulary in `name`, not a disease name | CONFIRMED, and already known to this codebase | `core/graph.py:3419` carries the root cause as finding F-2.1-B07, citing `docs/data-engineering/Knowledge_graph_on_server_reference.md` section M. The MedGen ETL parser is the source, and it is System 1/2's, out of this repository's scope per `file-protection.md` |
| The codebase already detects the bad values | BUILT | `_is_vocabulary_token_artifact` at `core/graph.py:3487`, a shape rule rather than a lookup table, plus a census-derived `_LEAKED_VOCABULARY_NAMES` set covering 15,466 rows the shape rule missed |
| So the CURIE fallback is deliberate, not an oversight | CONFIRMED | The detector downgrades `assertion_confidence` on a corrupted value rather than asserting it. The answer then has nothing readable left to say and names the identifier. The moat and the defect are the same mechanism, exactly as `UI_feedback.md` argues |
| `ncbi_efetch` can already resolve a MedGen concept id to a name | PARTLY, and the brief overstates it. See the correction below | `action: "search"` and `action: "summary"` both exist, `medgen` is in both db enums, and `title` is already on the `medgen` ESummary field allowlist at `tools/ncbi_eutils_actions.py:808` |
| Ground truth for the premise gate, read from live NCBI on a path touching none of the agent's machinery | ESTABLISHED | `C0346153` Familial cancer of breast; `C2676676` Breast-ovarian cancer, familial, susceptibility to, 1; `C3280442` Pancreatic cancer, susceptibility to, 4; `C4554406` Fanconi anemia, complementation group S |
| Every transport answers | READY | `python3 tracker/preflight.py`: product model 200, harness model reachable, graph 200 over the HTTPS query service |

## The correction to the brief

`UI_feedback.md` and the continuation prompt both state that `ncbi_efetch` already reaches
MedGen in the observed query, so the fix "looks closer to wiring than to building". Both told
the reader to verify that before promising it. Verified, and it is half true.

A MedGen ESummary call keyed on the concept id is REJECTED by NCBI:

```
$ curl ".../esummary.fcgi?db=medgen&id=C0346153&retmode=json"
{"error":"Invalid uid C0346153 at position= 0","result":{"uids":[]}}
```

Resolution takes two calls, not one: ESearch on `C0346153[ConceptId]` returns UID `87542`,
and ESummary on `87542` returns `title="Familial cancer of breast"`.

What survives of the original claim, and it is the load-bearing half: BOTH actions already
exist in the shipped tool, `medgen` is already an allowed db on each, and `title` is already
allowlisted. So this is still wiring rather than building. What it is not is free: it is two
extra live calls per answer on a path already taking 12 to 14 seconds, which makes caching
part of the ticket rather than a later optimization.

## Goal contract

Written before the first action, per `goal-contracts.md`.

Done when: a live run of "which diseases are associated with BRCA1" against the develop
deployment returns an answer that names diseases in words, every claim still carries a
citation, and the five interface complaints in `UI_feedback.md` are each either fixed or
closed with a stated product-owner decision.

Verify: the premise gate `tests/system_03_search_agent/core/test_answer_readability_premise.py`,
run against the live graph and live NCBI, asserting on the MEANING of the answer text against
ground truth read independently from MedGen. Plus the existing suites, `ruff`, `isort`, doc
drift, and a Playwright journey capture for each interface complaint. The verify surface is
immutable for the run: arms may be added, never weakened.

Output: the code changes on this branch, this file kept current, journey captures under
`docs/build/design/evidence/`, and one pull request.

Constraints:
- No ETL code and no write path to the graph. The upstream data defect stays System 1/2's.
- The grounding layer is not weakened to make answers read better. Cite-or-refuse holds; a
  resolved name must itself be cited to the Layer 2 record it came from.
- No new tool. The seven-tool roster is fixed and the contract is versioned.
- Two extra live calls per answer must be cached, not paid on every run.

Blocked-stop: any ticket whose resolution needs a product decision stops and reports rather
than guessing. Four tickets are already labelled `product_refine` for that reason.

Named shortcut, forbidden in advance: making the premise gate pass by asserting the answer
contains a MedGen URL, a citation count, or any other correlate of readability rather than
the disease name itself. That is the safety-by-proxy shape this repository has shipped as a
critical three times (build phases 4.3, 4.7, 4.11).

## Tickets

### T-6.2-01: Premise gate for answer readability

Status: in-review
Refine: refined
Branch: phase/6.2-answer-readability-ui-pass
Depends on: none. BLOCKS every other ticket in this phase
Spec: `docs/build/Build_workflow_cadence.md` stage 5; PRD "Citations: non-negotiable"

Acceptance criteria:
- [ ] The gate runs the real agent loop the way production runs it, with no mocked model and no mocked transport
- [ ] Ground truth is the four MedGen titles read from live NCBI, pinned in the gate file with the date and the exact query that produced them
- [ ] The gate asserts the answer text CONTAINS the disease names, and separately asserts it does NOT present a bare `MedGen:C#######` where a name belongs
- [ ] An arm covers the honest-failure direction: a disease whose name cannot be resolved is disclosed, never silently dropped and never guessed
- [ ] The gate states in its own file which question shapes it exercises and which it omits
- [ ] The gate has been SEEN FAILING before any other ticket opens, with the failing output pasted into Evidence

Files: `tests/system_03_search_agent/core/test_answer_readability_premise.py`

Evidence:

Six arms, WATCHED FAILING against the live graph, live NCBI and a real model before any
production code was touched. `RUN_PREMISE_GATE=1 python3 -m pytest
tests/system_03_search_agent/core/test_answer_readability_premise.py`:

```
5 failed, 1 passed in 186.74s (0:03:06)
```

The one pass is A6, the ground-truth pin, which is correct: it proves the four MedGen titles
this file asserts against are what MedGen says today, so the five red arms are red about the
product rather than about a stale constant.

Each failure verified to be red for its own reason rather than for a shared environmental
one, since five arms failing together is exactly the shape a single broken fixture makes:

- A1, the central arm: `the answer names 0 of the four diseases in words, needed at least 3`
- A2: reached its populate-check and stopped there, because A1's precondition does not hold
- A3: same, no resolved name exists whose provenance could be checked
- A4: `ModuleNotFoundError: No module named 'system_03_search_agent.synthesis.disease_names'`,
  which is T-6.2-02's deliverable named by the gate before it is written
- A5: `internal findings accounting reached the reader: ['3 of the 5 findings']`

The captured narrative, which is the phase's whole justification in one line:

```
BRCA1 (gene symbol BRCA1 [1], MedGen:C2676676 [2], MedGen:C3280442 [3], and
MedGen:C4554406 [4]. Note: this answer reports 4 of the 5 findings prepared for it,
and the one not reported is absent from the citations as well as from the text above
```

Two corrections the gate forced on its own first run, both recorded rather than quietly
fixed. It initially used an unregistered `premise` marker, which pytest reported as a warning
rather than an error, so the arms ran while the marker did nothing. And A6 failed its first
run against NCBI for its OWN impatience: eight E-utilities calls issued back to back tripped
the 3-requests-per-second unauthenticated pool that `.claude/rules/tool-call-budgets.md`
names, so the gate is now paced at one call per second. A gate that trips the limit it is
testing against reports on itself.

History:
- 2026-09-01 lead: created, scoped from `UI_feedback.md` after establishing ground truth live
- 2026-09-01 lead: six arms written, run live, and SEEN FAILING 5 of 6. Filed F-6.2-01,
  F-6.2-02 and F-6.2-03 from the failure output. Moved to `in-review`: stage 5 is satisfied
  and the phase's other tickets are unblocked, and per the maker-cannot-sign-off split the
  judge closes this, not the lead who wrote it

### T-6.2-02: Disease identifiers are resolved to disease names in the answer

Status: todo
Refine: refined
Depends on: T-6.2-01
Spec: `UI_feedback.md` headline finding; tech spec Section 6.2; `production-standards.md` layer authority gate

Acceptance criteria:
- [ ] An answer about BRCA1's associated diseases names each disease in words, not as `MedGen:C0346153`
- [ ] Each resolved name carries its own citation to the MedGen record the name was read from, with `layer` reporting Layer 2, never Layer 1
- [ ] A concept id that does not resolve leaves the identifier in place with a disclosure, and never invents a name
- [ ] Resolution results are cached, so a repeated question does not pay the two extra live calls again
- [ ] The resolution respects the `eutils` rate pool and build phase 6.0's per-query call ceiling
- [ ] The existing vocabulary-artifact detector is unchanged: this ticket adds a resolution path, it does not weaken the detector

Files: `src/system_03_search_agent/core/graph.py`, `src/system_03_search_agent/synthesis/`, `src/system_03_search_agent/tools/ncbi_eutils_actions.py`

History:
- 2026-09-01 lead: created. The two-call resolution path verified live before scoping

### T-6.2-03: The internal findings-accounting note is not shown to the user

Status: todo
Refine: refined
Depends on: T-6.2-01
Spec: `UI_feedback.md` "the second defect in the same answer"

Acceptance criteria:
- [ ] No user-facing answer contains a sentence reporting how many prepared findings were reported versus withheld
- [ ] Where information was genuinely withheld, the disclosure states what a reader can act on, not an internal count
- [ ] The accounting itself is retained wherever it is used for grading or tracing, so this is a presentation change and not a loss of the signal

Files: `src/system_03_search_agent/synthesis/`

History:
- 2026-09-01 lead: created

### T-6.2-04: The same question returns the same disease count on repeated runs

Status: todo
Refine: tech_refine
Depends on: T-6.2-01
Spec: `UI_feedback.md` "seen in a real browser", row 4

Acceptance criteria:
- [ ] The cause of four diseases on one run and three on another, minutes apart for the same question, is established and written down with evidence
- [ ] If the cause is a defect, it is fixed and an arm pins the fixed behaviour; if it is legitimate variation, it is documented in the phase file and closed with a reason

Files: to be determined by the investigation

History:
- 2026-09-01 lead: created. Deliberately not pre-judged as a defect

### T-6.2-05: The interface shows continuous progress during the wait

Status: todo
Refine: refined
Depends on: none
Spec: `UI_feedback.md` complaint 2

Acceptance criteria:
- [ ] From submit to answer there is no interval longer than two seconds in which the interface shows no sign of progress
- [ ] The progress indication names the step underway rather than showing an undifferentiated spinner
- [ ] A Playwright journey captures the whole wait as a per-second filmstrip, and the filmstrip shows no blank interval

Files: `frontend/src/`, `frontend/e2e/journeys/`

History:
- 2026-09-01 lead: created

### T-6.2-06: The answer is delivered progressively rather than in two chunks at the end

Status: todo
Refine: tech_refine
Depends on: T-6.2-05
Spec: `UI_feedback.md` complaint 2, the two-token measurement

Acceptance criteria:
- [ ] Whether the two-token delivery is the Write step's design or a defect is established and written down
- [ ] If it is a defect, a run of the BRCA1 question emits token events spread across the synthesis interval rather than two events microseconds apart
- [ ] The grounding layer still runs to completion before any claim is shown, so progressive delivery never shows an ungrounded claim

Files: `src/system_03_search_agent/core/graph.py`, `src/system_03_search_agent/synthesis/`

History:
- 2026-09-01 lead: created

### T-6.2-07: A follow-up question continues the thread

Status: todo
Refine: product_refine
Depends on: none
Spec: `UI_feedback.md` complaint 3

Blocked on a product decision: what a follow-up turn carries forward. The three candidates
are the prior question and answer as context, the resolved entities from the previous turn,
or the full thread. Only the product owner moves this ticket.

Acceptance criteria:
- [ ] A follow-up asking "what variants cause it" after a question about BRCA1 resolves "it" to the subject of the previous turn
- [ ] The carried context is bounded and enters the dynamic suffix, never the stable prefix, per `prompt-cache-discipline.md`
- [ ] A follow-up from a different session never inherits another session's thread

Files: `frontend/src/`, `src/system_03_search_agent/core/session_memory.py`, `src/system_03_search_agent/core/graph.py`

History:
- 2026-09-01 lead: created, labelled `product_refine` at creation

### T-6.2-08: An answer can offer an honest next step

Status: todo
Refine: product_refine
Depends on: T-6.2-07
Spec: `UI_feedback.md` complaint 5; `contracts/events.py:128` `ThinkPayload.clarifying_question`

Blocked on the same product decision plus three of its own, all named in `UI_feedback.md`:
where the suggestion comes from, whether it is one offer or several, and whether an answer
may decline to offer anything. It must be able to decline.

Acceptance criteria:
- [ ] An offer to go deeper is derived from what retrieval actually returned and had to leave out, never generated as free text about data the system does not hold
- [ ] An answer with no honest next step offers none, and this case is covered by a test
- [ ] Accepting an offer continues the thread rather than starting a fresh run

Files: `src/system_03_search_agent/core/graph.py`, `frontend/src/`

History:
- 2026-09-01 lead: created, labelled `product_refine` at creation. Ordered behind T-6.2-07 because an offer the system then forgets making is worse than no offer

### T-6.2-09: The integrations page offers only what a visitor can actually use

Status: todo
Refine: product_refine
Depends on: none
Spec: `UI_feedback.md` complaint 4

Blocked on a product decision: build the KGX HTTP endpoint, or stop advertising it. Building
it is new surface area and touches `v1-scope-boundary`, since build phase 4.4 delivered KGX
export as a command-line tool only.

Acceptance criteria:
- [ ] No control on the page acknowledges an action and does nothing
- [ ] Each named surface either carries what a visitor needs to use it, or says plainly that it is not available over the web
- [ ] The GraphQL entry states that it needs a registered account, since there is no guest path

Files: `frontend/src/`, and an API surface only if the product owner chooses to build the endpoint

History:
- 2026-09-01 lead: created, labelled `product_refine` at creation

### T-6.2-10: Design fidelity against the approved prototype is established

Status: todo
Refine: refined
Depends on: none
Spec: `UI_feedback.md` complaint 1; `docs/build/design/design-system/prototype/app.html`

Acceptance criteria:
- [ ] The live develop app and the prototype are captured side by side at 390px, 768px and 1440px
- [ ] Each difference found is classified as a regression since build phase 4.9 or as a gap that phase never covered, with evidence for the classification
- [ ] Fixes are scoped as their own tickets after that classification, not before it

Files: `frontend/e2e/journeys/`, `docs/build/design/evidence/`

History:
- 2026-09-01 lead: created. Classification comes before any fix, since a regression and an uncovered gap are different jobs

### T-6.2-11: Browser journeys capture the experience rather than assert on it

Status: todo
Refine: refined
Depends on: T-6.2-12
Spec: `UI_feedback.md` "end-to-end workflows for browser-driven testing", the eight-journey table

Acceptance criteria:
- [ ] All eight journeys exist under `frontend/e2e/journeys/`, gated behind an environment variable like the existing diagnostics
- [ ] Each captures intermediate states, not only the end state
- [ ] Each writes a dated, named screenshot under `docs/build/design/evidence/`
- [ ] None of them asserts. A journey runs all its steps even when a step produces something wrong
- [ ] Journey 2, the per-second filmstrip of the wait, is built first

Files: `frontend/e2e/journeys/`

History:
- 2026-09-01 lead: created

### T-6.2-12: Live browser checks target develop, not production

Status: todo
Refine: refined
Depends on: none
Spec: `UI_feedback.md` "test against develop, not production"

Acceptance criteria:
- [ ] `frontend/e2e/live-answer-screenshot.spec.ts` takes its target from an environment variable and defaults to the develop deployment
- [ ] No spec in `frontend/e2e/` hardcodes a production URL
- [ ] The `app_env` field of the target's `/health` is captured alongside each run, so a capture states which deployment produced it

Files: `frontend/e2e/`

History:
- 2026-09-01 lead: created. First, because every other browser ticket inherits the wrong target otherwise

### T-6.2-13: The reported cost of a run is either accurate or absent

Status: todo
Refine: tech_refine
Depends on: none
Spec: `UI_feedback.md` "the evidence, measured"; `system-design-patterns.md` pattern 4

Acceptance criteria:
- [ ] Why `total_cost_usd` reported `0.0` on a run that made two tool calls and several model calls is established and written down
- [ ] If cost accounting does not reach the guest path, it does, and an arm pins it
- [ ] No surface reports a cost figure it cannot substantiate

Files: `src/system_03_search_agent/harness/`, `src/system_03_search_agent/adapters/`

History:
- 2026-09-01 lead: created. Named because the per-user and system-wide daily caps read this figure

### T-6.2-14: The reference build comparison, owed since 2026-08-31

Status: todo
Refine: refined
Depends on: none
Spec: `UI_feedback.md` "owed: a proper comparison against the reference build"

Acceptance criteria:
- [ ] For each of KGX, MCP and the API, the comparison states what `reference/ncbi_ai_agents-ncbi-kg` put in front of a user that this build does not
- [ ] The answer is drawn from that repository's own source and interface, never from its directory listing
- [ ] Anything worth adopting is filed as its own ticket rather than built inside this one

Files: a written comparison in this phase file

History:
- 2026-09-01 lead: created. Recorded as owed rather than summarized, per `UI_feedback.md`

## Coverage: what this phase does not cover

Stated so a green phase is not read as a complete one, per `goal-contracts.md`.

- The upstream data defect. Disease `name` stays corrupted in the graph. This phase works
  around it at query time and the correct fix remains a System 1/2 re-ingest.
- Diseases only. Any other node label whose `name` carries the same ETL corruption is not
  surveyed here. `_LEAKED_VOCABULARY_NAMES` suggests the problem is Disease-specific, and
  that is an inference from a census, not a proof.
- One question shape. The premise gate anchors on gene-to-disease association. A question
  reaching Disease nodes by another route is not exercised, which is the same blind spot
  build phase 2.1's gate had and is named here rather than discovered later.
- Latency. Nothing in this phase makes the 12 to 14 second answer faster. T-6.2-05 covers
  the wait's presentation and T-6.2-02 adds two calls to it.
- Build phase 6.0's eight open judge findings and the residue of 6.1. Both stay in
  `requirements/Plan.md` Phase 7.

## Findings

All three below were established by the FIRST live run of the premise gate, before any
production code was touched. Two of them are defects `UI_feedback.md` did not name, which is
the argument for writing the gate before the fix rather than after it.

### F-6.2-01: The narrative is a broken sentence fragment, not just an unreadable one

Status: filed
Raised by: lead, first live premise-gate run
Severity: high
Round: 0 (pre-build)
Ticket: unassigned

What happened. Arm A1's captured narrative, in full:

> BRCA1 (gene symbol BRCA1 [1], MedGen:C2676676 [2], MedGen:C3280442 [3], and MedGen:C4554406 [4].

The opening parenthesis never closes, "BRCA1" is repeated inside its own parenthetical, and
the sentence has no verb. Citation [1] carries `claim_text='BRCA1 (gene symbol BRCA1'`, an
unbalanced span, so the mangling is present in the citation payload and not only in the
rendered text.

Why this matters separately from the disease-name defect: `UI_feedback.md` characterizes the
answer as correct but unreadable. It is worse than that. This is not a well-formed sentence
carrying identifiers instead of names, it is a fragment, and the likely cause is the
deterministic grounding pass stripping an unmatched clause mid-sentence and leaving the
remainder. Resolving the disease names will NOT fix it, so it needs its own owner.

History:
- 2026-09-01 lead: filed from the gate's own failure output, before any fix

### F-6.2-02: The findings-accounting note is reproducible, not intermittent

Status: filed
Raised by: lead, first live premise-gate run
Severity: medium
Round: 0 (pre-build)
Ticket: T-6.2-03

What happened. `UI_feedback.md` recorded that this note "did NOT appear this run" in the
browser and concluded it is "intermittent, not constant, and reproducing it needs a specific
path". Arm A5 reproduced it on its first attempt, and arm A1's separate run carried the same
note with different numbers:

> Note: this answer reports 3 of the 5 findings prepared for it, and the 2 not reported are
> absent from the citations as well as from the text above

> Note: this answer reports 4 of the 5 findings prepared for it, and the one not reported is
> absent from the citations as well as from the text above

So it appears whenever findings are dropped, which is every run of this question. What varies
is the count, not whether the note appears. The browser run that did not show it is the case
needing explanation, which is the opposite of what the brief assumed.

History:
- 2026-09-01 lead: filed. Corrects a characterization in `UI_feedback.md` rather than
  reporting something new

### F-6.2-03: The non-determinism reproduces inside the gate itself

Status: filed
Raised by: lead, first live premise-gate run
Severity: medium
Round: 0 (pre-build)
Ticket: T-6.2-04

What happened. Two runs of the identical question, minutes apart in one pytest session,
returned different answers: one cited four records including a Gene row at
`layer=layer_2_api`, the other cited three records, all `layer_1_graph`. The 5-finding total
was the same both times; what differed was how many survived grounding.

This is the variation `UI_feedback.md` observed between its API run and its browser run, and
it reproduces cheaply, which T-6.2-04 was scoped assuming it might not. It also means arms
A1, A2, A3 and A5 each run against a slightly different answer, so a fix must be robust to
the variation rather than tuned to one run.

History:
- 2026-09-01 lead: filed

## History

- 2026-09-01 lead: phase opened by product-owner directive. Ground truth established from
  live MedGen, the brief's `ncbi_efetch` claim verified and corrected, preflight green,
  branch cut, fourteen tickets scoped
