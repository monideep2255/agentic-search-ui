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

Status: in-review
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

Files: `src/system_03_search_agent/synthesis/disease_names.py` (new),
`src/system_03_search_agent/synthesis/findings.py`, `src/system_03_search_agent/core/graph.py`

Evidence:

The live answer, captured after the change. Compare against the one at the top of this file:

```
BRCA1 (gene symbol: BRCA1 [1]. breast-ovarian cancer, familial, susceptibility to, 1 [2],
pancreatic cancer, susceptibility to, 4 [3], and Fanconi anemia, complementation
group S [4].

  [2] layer=layer_2_api name='breast-ovarian cancer, familial, susceptibility to, 1'
      https://www.ncbi.nlm.nih.gov/medgen/C2676676
  [3] layer=layer_2_api name='pancreatic cancer, susceptibility to, 4'
      https://www.ncbi.nlm.nih.gov/medgen/C3280442
  [4] layer=layer_2_api name='Fanconi anemia, complementation group S'
      https://www.ncbi.nlm.nih.gov/medgen/C4554406
```

Each name is cited to the MedGen record it was read from, at `layer_2_api` rather than
laundered into the Layer 1 citation that prompted the lookup.

The premise gate: `6 passed in 129.66s`, having been watched failing 5 of 6 before the
change. READ THAT NUMBER WITH F-6.2-04: arm A5 is non-deterministic and its green in that
run is a false one, so this ticket rests on A1, A2, A3 and A4 and not on A5.

Resolver measured directly, four real diseases plus three inputs that must not resolve:

```
MedGen:C0346153 -> 'Familial cancer of breast'
MedGen:C4554406 -> 'Fanconi anemia, complementation group S'
MedGen:C9999999 -> None      (MedGen does not hold it)
MeSH:D001943    -> None      (not a MedGen id; no lookup spent)
not-a-curie     -> None
cold 0.73s, warm 0.0000s, every input key present in the result
```

Regression suites: `750 passed, 68 skipped, 1 xfailed` across
`tests/system_03_search_agent/synthesis/` and `core/`. `ruff check src services tests`
clean. CI gate 2 (`isort`) run before and after the change, exit 0 both times.

TWO CALLS TOTAL rather than two per disease, verified live before the code was written:
one ESearch ORing every `[ConceptId]` clause, one ESummary over every returned UID. The
UID-to-concept mapping reads MedGen's own `conceptid` field rather than relying on result
ordering, which would have attached the wrong name to the right identifier the day NCBI
reordered.

THE FIX HAD TWO STAGES AND THE SECOND IS THE TRANSFERABLE ONE. Resolution alone produced
`familial cancer of breast (MedGen:C0346153) [2]`: readable, and still carrying four
identifiers the reader did not ask for, which arm A2 had pre-registered as the partial fix
it exists to reject. The model was NOT wrong. It had been handed
`Disease MedGen:C0346153, name: Familial cancer of breast` by `render_findings_block`, and
the system instruction tells it to state values as written and to use the identifiers it is
given. `attack-the-constraint` applied unchanged: the assembly step feeding the model is
upstream of the model, so it is the constraint. The rendered line is now
`Disease name: Familial cancer of breast`, and the identifier survives on the finding, the
citation and the chip, which is where a reader who wants to verify goes.

History:
- 2026-09-01 lead: created. The two-call resolution path verified live before scoping
- 2026-09-01 lead: `synthesis/disease_names.py` added, `apply_resolved_disease_names` and
  the `name_resolved` render branch added to `synthesis/findings.py`, wired into
  `write_node` between the findings build and the Synth call
- 2026-09-01 lead: A2 failed on the first live run, and the check was NOT relaxed to
  accommodate it. Its own docstring, written before the fix, had already named
  "names AND identifiers beside them" as the partial fix it exists to reject, so the subject
  was changed rather than the verify surface. Recorded because relaxing it would have been
  indistinguishable from progress in the summary
- 2026-09-01 lead: moved to `in-review`. The judge closes this, not the lead who wrote it

### T-6.2-03: The internal findings-accounting note is not shown to the user

Status: in-review
Refine: refined
Depends on: T-6.2-01
Spec: `UI_feedback.md` "the second defect in the same answer"

Acceptance criteria:
- [ ] No user-facing answer contains a sentence reporting how many prepared findings were reported versus withheld
- [ ] Where information was genuinely withheld, the disclosure states what a reader can act on, not an internal count
- [ ] The accounting itself is retained wherever it is used for grading or tracing, so this is a presentation change and not a loss of the signal

Files: `src/system_03_search_agent/core/graph.py`,
`tests/system_03_search_agent/core/test_write_completeness.py`,
`tests/system_03_search_agent/core/test_personalization_premise.py`

Evidence:

The note read, to a researcher on the live site:

```
Note: this answer reports 4 of the 5 findings prepared for it, and the one not reported
is absent from the citations as well as from the text above
```

It now reads:

```
Note: 3 further disease records were found for this question and are not described above
```

The three earlier fixes to this note are PRESERVED rather than undone, which is why it was
reworded rather than rewritten: it is still ONE sentence (a second would read as an uncited
claim to the coverage grader), it still states SCALE rather than inlining values (a Layer 1
value like `NM_007294.4(BRCA1):c.190T>G` is full of periods and the grader splits on them),
and it still never claims the omitted rows are in the citations, which they are not. It also
carries no semicolon, since the grounding pass treats `;` as a sentence boundary too.

TWO EXISTING TESTS PINNED THE OLD WORDING AND BOTH PINNED REAL PROPERTIES, so neither was
deleted:

- `test_write_completeness.py` guarded F-4.5-A-16, that the denominator counts findings
  PREPARED for the answer rather than rows retrieved, a defect that once understated by 25x.
  The new note prints no denominator, so the arm now asserts the same property through the
  count it does print: 3 omitted from 5 prepared, never 498 or 500. Mutation-proven by
  forcing the count to 498, which turns it red, then restoring it.
- `test_personalization_premise.py` used the note's wording as a fingerprint to prove the
  disclosure branch fired at all. Its fingerprint moved to `not described above`. That file's
  own comment warns that a fingerprint a grammar fix can invalidate is testing the wording
  rather than the control, and that warning is now recorded against the new line too, since
  it is still a phrase rather than a property.

History:
- 2026-09-01 lead: created
- 2026-09-01 lead: note rewritten from the system's side to the reader's, both dependent
  tests re-pinned against the same properties rather than dropped, mutation verified
- 2026-09-01 lead: moved to `in-review`. The judge closes this, not the lead

### T-6.2-15: A stripped mid-sentence clause must not leave a broken sentence

Status: todo
Refine: product_refine
Depends on: T-6.2-04
Spec: F-6.2-01 in the Findings section below; `synthesis/grounding.py`'s clause boundaries

Blocked on a product decision, and the decision is a genuine trade rather than a detail.
When the grounding pass strips a clause from the middle of a sentence, the surviving text
can lose its verb and its punctuation. The two honest repairs pull in opposite directions:

- Drop the whole sentence. Safe, and it means one unsupported disease out of four takes the
  other three with it, turning a partial answer into no answer.
- Keep the fragment. Preserves the surviving facts and shows a reader an ungrammatical
  sentence.

A third option, repairing the remainder into grammatical prose, is NOT on the table: it
means generating text after the grounding pass has run, which is the one thing this system's
trust position does not permit.

Acceptance criteria:
- [ ] Whichever option the product owner picks, no user-facing answer contains an unbalanced
      bracket or a sentence with no verb where a clause was stripped
- [ ] The choice is recorded in `DECISIONS.md` with the rejected option and its cost
- [ ] An arm drives a mid-sentence strip deterministically and asserts the chosen behaviour,
      rather than waiting for the run-to-run variation to produce one

Files: `src/system_03_search_agent/synthesis/grounding.py`

History:
- 2026-09-01 lead: created from F-6.2-01 once measurement showed it is a consequence of the
  omission path rather than an independent defect, and that the repair is a product trade

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

Status: in-review
Refine: refined
Depends on: none
Spec: `UI_feedback.md` complaint 2

Acceptance criteria:
- [ ] From submit to answer there is no interval longer than two seconds in which the interface shows no sign of progress
- [ ] The progress indication names the step underway rather than showing an undifferentiated spinner
- [ ] A Playwright journey captures the whole wait as a per-second filmstrip, and the filmstrip shows no blank interval

Files: `frontend/src/hooks/useElapsedSeconds.ts` (new),
`frontend/src/components/screens/RunScreen.tsx`, `frontend/src/App.tsx`,
`frontend/src/components/screens/RunScreen.progress.test.tsx` (new)

Evidence:

WHAT WAS ALREADY THERE, established by reading before changing anything: the run screen
already renders all five loop steps, marks the live one, and lands tool chips coloured by
data layer. The complaint was not that progress is unnamed. It is that NOTHING MOVES. The
live step carried a static ring, so across a five-second gap between transitions the page was
indistinguishable from one that had died.

Three changes, and the ordering of them is the reasoning:

- An elapsed counter that ticks once a second. It is the only element that is both
  always-moving and informative: a spinner would move and say nothing. It also states the 12
  to 14 second wait honestly rather than hiding it. Recomputed from `Date.now()` each tick
  rather than incremented, so a throttled background tab does not UNDERSTATE the wait in
  exactly the case where someone tabbed away and came back wanting to know how long it had
  been.
- A pulse on the live step dot, which stops when the run does. An animation still running
  after the answer landed asserts work that is not happening. `prefers-reduced-motion` gets
  the static ring back, which is why the liveness signal is ALSO text.
- A politely-announced step change for screen readers.

THE ACCESSIBILITY TRAP IS THE PART MOST LIKELY TO BE UNDONE BY A LATER READER: the counter is
`aria-hidden`. A value changing every second inside a live region would have a screen reader
announce "one second, two seconds, three seconds" for the whole run and bury the step
transitions that carry the meaning. Making it announceable would look like an accessibility
improvement and would be the opposite, so the step announcement is a separate element.

```
5 new arms passed, 240 frontend tests total (from 235)
mutation: removing the counter, the pre-fix state, turns 4 of 5 red
tsc --noEmit exit 0
playwright accessibility 10 passed, axe clean on the run and answer screens
```

One arm asserts the acceptance criterion DIRECTLY rather than by proxy: it walks 20 seconds
and measures the longest run of consecutive seconds in which the display did not change,
failing above two. The first arm would still pass if the counter ticked once every ten
seconds, which is why the second exists.

COVERAGE, since a green run here is not the whole criterion: these arms cannot see whether
the change is VISIBLE, and cannot see the pulse at all, which is CSS. T-6.2-11's journey 2
covers that.

History:
- 2026-09-01 lead: created
- 2026-09-01 lead: elapsed counter, live-step pulse and screen-reader announcement, five arms
  with the criterion asserted directly, mutation-proven against the pre-fix state, axe clean.
  Moved to `in-review`

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

Status: in-progress, 1 of 8 journeys built
Refine: refined
Depends on: T-6.2-12
Spec: `UI_feedback.md` "end-to-end workflows for browser-driven testing", the eight-journey table

Acceptance criteria:
- [ ] All eight journeys exist under `frontend/e2e/journeys/`, gated behind an environment variable like the existing diagnostics
- [ ] Each captures intermediate states, not only the end state
- [ ] Each writes a dated, named screenshot under `docs/build/design/evidence/`
- [ ] None of them asserts. A journey runs all its steps even when a step produces something wrong
- [ ] Journey 2, the per-second filmstrip of the wait, is built first

Files: `frontend/e2e/journeys/wait-filmstrip.spec.ts` (new)

Evidence so far:

Journey 2, the per-second filmstrip of the wait, built FIRST as `UI_feedback.md` directs:
the fragmentation complaint is described in prose, and a filmstrip turns it into something
anyone can look at and agree or disagree with.

It CAPTURES rather than asserts, which is the rule for this whole directory. It carries no
`expect` on the product at all: if the answer never arrives, a filmstrip of it never arriving
is the evidence wanted. Its ONE assertion is about itself, that it captured more than one
frame, because a silent zero-frame pass would read as "the wait looked fine". Each frame is
paired with a one-line state summary in `filmstrip.md`, so the strip is readable without
opening 25 images, and every read degrades to a placeholder rather than throwing, since a
missing run screen IS the observation on a failed run.

Gated behind `RUN_LIVE_JOURNEYS=1` and pointed at develop through `live-target.ts`.

Seven journeys remain: first visit to first answer, follow-up continuity, guest allowance
exhaustion, every integrations affordance, refusal and error paths, narrow viewports, and
sign up / sign out / sign in.

History:
- 2026-09-01 lead: created
- 2026-09-01 lead: journey 2 built, gated, typechecked. Seven remain

### T-6.2-12: Live browser checks target develop, not production

Status: in-review
Refine: refined
Depends on: none
Spec: `UI_feedback.md` "test against develop, not production"

Acceptance criteria:
- [ ] `frontend/e2e/live-answer-screenshot.spec.ts` takes its target from an environment variable and defaults to the develop deployment
- [ ] No spec in `frontend/e2e/` hardcodes a production URL
- [ ] The `app_env` field of the target's `/health` is captured alongside each run, so a capture states which deployment produced it

Files: `frontend/e2e/live-target.ts` (new), `frontend/e2e/live-target.spec.ts` (new),
`frontend/e2e/live-answer-screenshot.spec.ts`, `frontend/e2e/live-second-turn-diagnostic.spec.ts`

Evidence:

`live-target.ts` resolves the web and API targets from `S3_LIVE_WEB_URL` and `S3_LIVE_API_URL`,
defaulting to develop, and refuses anything that is not `https://` rather than attempting it,
since these specs spend a real guest allowance against whatever they are pointed at.

Both live diagnostics now import it, and both record `app_env` READ FROM THE API'S OWN
`/health` rather than inferred from the URL string. A URL is what someone intended to hit and
`app_env` is what answered, and those differ exactly when it matters: build phase 4.15 shipped
a develop web app that was live, answered 200, and could reach no API at all.

REWIRING THE TWO FILES THAT EXIST IS NOT THE FIX, and this is the transferable half.
`live-target.spec.ts` checks the WHOLE DIRECTORY, so the third live spec someone writes next
week cannot quietly hardcode a target. It runs offline, in the ordinary suite. Two arms: no
spec names a deployment in a string literal, and the default is develop rather than
production, asserted in that direction because defaulting to production is what produced a
whole feedback document measured against the wrong build.

Mutation-proven rather than asserted: adding a hardcoded production URL to `routing.spec.ts`
turns the first arm red naming that file, and removing it turns it green again.

```
2 passed (4.8s)          both arms
1 failed, 1 passed       with routing.spec.ts mutated
tsc --noEmit             exit 0
vitest                   235 passed
```

ONE DEFECT IN THIS TICKET'S OWN ARM, recorded rather than quietly fixed: it first used
`__dirname`, which does not exist in this ESM project. Playwright reported it as a
ReferenceError at COLLECTION time and printed `No tests found`, so the arm would have been
silently absent rather than failing. That is the same family as the unregistered pytest
marker earlier in this phase: a check that does not run reports nothing, and nothing reads as
fine.

History:
- 2026-09-01 lead: created. First, because every other browser ticket inherits the wrong target otherwise
- 2026-09-01 lead: shared target module, `app_env` capture, and a directory-wide structural
  arm; mutation verified. Moved to `in-review`

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

Status: confirmed as a MECHANISM, measured as LATENT. Needs a product decision, see below
Raised by: lead, first live premise-gate run
Severity: high when it fires, and it did not fire in 5 of 5 runs after T-6.2-02
Round: 0 (pre-build)
Ticket: T-6.2-15 (opened for it), and it is downstream of T-6.2-04

MEASURED 2026-09-01, after T-6.2-02 landed. Five consecutive live runs of the same
question, checking parenthesis balance and disease coverage:

```
run 0: parens 1/1 ok   BRCA1 (gene symbol BRCA1) [1] is associated with four disease records...
run 1: parens 0/0 ok   BRCA1 [1] is associated with four disease records in the knowledge graph...
run 2: parens 0/0 ok   BRCA1 [1] is associated with familial cancer of breast [2], breast-ovarian...
run 3: parens 0/0 ok   BRCA1 [1] is associated with four disease records in the knowledge graph...
run 4: parens 0/0 ok   BRCA1 [1] is associated with four diseases: familial cancer of breast [2]...
```

Zero reproductions in five, and every run named all four diseases. Before T-6.2-02 the
observed runs dropped one. So this finding is NOT an independent defect: it is a
CONSEQUENCE of the omission path F-6.2-03 describes, and resolving the names appears to
have made omission rarer, plausibly because a model reproduces a disease name verbatim more
reliably than it reproduces `MedGen:C0346153`. That is an inference from five runs, not a
proof, and it is stated as one.

THE MECHANISM, established by reading `synthesis/grounding.py` rather than by guessing.
A clause runs from the end of the previous marker to the marker itself, so

    BRCA1 (gene symbol: BRCA1 [1]) is associated with familial cancer of breast [2], ...

splits into a segment ending at [1] and a segment `") is associated with familial cancer of
breast "` ending at [2]. If the [2] finding is stripped, the closing parenthesis AND the
sentence's only verb go with it, and the surviving text is the fragment that was observed.
The connective tissue of a sentence lives inside its clauses, so stripping one mid-sentence
can leave the rest ungrammatical.

WHY THIS IS NOT FIXED IN THIS TICKET, and it is a product decision rather than a technical
one. The obvious repair is to drop the WHOLE SENTENCE when a mid-sentence segment is
stripped, which is honest and safe. It is also destructive in exactly the case that matters:
one unsupported disease out of four would take the other three with it, turning a partial
answer into no answer. The alternative, repairing the remainder into a grammatical sentence,
means generating prose AFTER the grounding pass has run, which is the one thing this
system's trust position does not permit.

So the choice is between an ungrammatical partial answer and a smaller complete one, and
that is the product owner's call. Recorded as T-6.2-15 with both options rather than
settled by the lead.

History:
- 2026-09-01 lead: filed from the gate's own failure output, before any fix
- 2026-09-01 lead: measured at 0 of 5 after T-6.2-02, mechanism established by reading
  `grounding.py`'s segment boundaries, reclassified from an independent defect to a
  consequence of F-6.2-03, and opened as T-6.2-15 carrying a product decision

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

### F-6.2-05: This phase's own structural arm was blind to a subdirectory

Status: closed same session, pending judge verification
Raised by: lead, minutes after writing the arm
Severity: medium
Round: 0 (pre-build)
Ticket: T-6.2-12

What happened. `live-target.spec.ts`'s docstring says it checks the WHOLE DIRECTORY, and it
used a flat `readdirSync`. `frontend/e2e/journeys/` was created minutes later in the same
session, and the arm could not see a single file in it, so a hardcoded production URL in any
journey would have passed silently, which is the exact defect the arm exists to prevent.

Caught by noticing it reported green on a directory it had never opened, rather than by any
check. SEVENTH instance in this repository of a confident sentence describing a check that is
not there, and this one was written in the same session as the sixth, while the lesson was
being quoted in a commit message.

Fixed by walking recursively, and mutation-proven from the subdirectory specifically: a
hardcoded production URL in `journeys/wait-filmstrip.spec.ts` now turns the arm red naming
that path, where before it was invisible.

The transferable form: an arm that enumerates files is only as good as its enumeration, and
the enumeration is the part nobody re-reads. When an arm's scope is stated in prose, the
scope is a claim to be tested like any other.

History:
- 2026-09-01 lead: filed and fixed in the same edit, mutation verified from inside the
  subdirectory. Left open for the judge rather than self-closed

### F-6.2-04: Arm A5 of this phase's own premise gate reports a FALSE GREEN

Status: closed by T-6.2-01's deterministic rewrite, pending judge verification
Raised by: lead, evidence capture after T-6.2-02 landed
Severity: high
Round: 0 (pre-build)
Ticket: T-6.2-01 (the gate), T-6.2-03 (the defect it fails to pin)

What happened. The full gate run after T-6.2-02 landed reported `6 passed`, including A5,
the arm asserting the internal findings-accounting note never reaches the reader. T-6.2-03,
the ticket that fixes that note, HAS NOT BEEN STARTED. A single evidence-capture run of the
same question minutes later produced:

> BRCA1 (gene symbol: BRCA1 [1]. breast-ovarian cancer, familial, susceptibility to, 1 [2],
> pancreatic cancer, susceptibility to, 4 [3], and Fanconi anemia, complementation group S
> [4]. Note: this answer reports 4 of the 5 findings prepared for it, and the one not
> reported is absent from the citations as well as from the text above

So A5 passed because that particular run happened to drop no findings, not because the
defect is fixed. This is F-6.2-03's non-determinism turning one arm of the gate into a coin
flip, and it is the more dangerous consequence of it: a green arm reads as "this class is
covered".

Why this is filed at severity high against a cosmetic underlying defect: the failure is in
the VERIFY SURFACE, not in the product. `goal-contracts.md` says a gate that cannot
distinguish the property holding from nothing having happened is not a gate, and an arm that
reports green on a live defect is that failure with an extra step. It must be made
deterministic before T-6.2-03 can be closed against it, or T-6.2-03 will be closed on
evidence that proves nothing.

The likely fix is not to retry until the note appears, which would be tuning the arm to the
defect. It is to drive the omission deterministically, so the arm asserts on what a user is
shown WHEN findings are dropped, which is the case the note exists for.

History:
- 2026-09-01 lead: filed immediately on noticing the contradiction between a green A5 and a
  live note in the very next run, before continuing
- 2026-09-01 lead: A5 rewritten. It now drives the omission DIRECTLY through
  `_build_incomplete_answer_note`, covering both the singular and plural branches, so the
  disclosure is guaranteed to exist and the arm always has something to assert. The live
  half is kept but now SKIPS explicitly when a run omits nothing, rather than passing
  silently: the gate reports `5 passed, 1 skipped`, and that skip is the arm saying out loud
  that the live path was not exercised. Mutation-proven by restoring the old wording in the
  singular branch only, which turns it red in 3.14s, before any live call. Left open for the
  judge rather than closed by the lead who wrote both the defect and the fix

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
