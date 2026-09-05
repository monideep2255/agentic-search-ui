# Thread workflows

The thread is the product's whole argument made visible: a question crosses a guardrail, gets understood, gets planned, reads real NCBI records, and gets written back with every claim tied to where it came from, or the system says it found nothing rather than guessing. Everything in this file is either that argument being kept, a place it silently breaks, or a place its own instruments describe it as broken when they are not looking at the right thing. Cite-or-refuse is the single fact a reader most needs to be able to trust, so it gets the strongest workflow here, and the two disclosure notes exist because a cited-but-partial answer that looks whole is its own kind of untrustworthy answer.

## W-thread-1: Asking a question and watching the run

The product must: while a query runs, the interface shows which of the five agent-loop steps is live, an elapsed-time counter, a chip for each tool actually dispatched, and the system's own account of what each step decided, so a multi-second wait reads as visible work rather than a spinner.

Status: BUILT. The five-step stepper renders unconditionally, `STEPS = ["Guard", "Think", "Plan", "Act", "Write"] as const` (`frontend/src/components/screens/RunScreen.tsx:52`). Elapsed counter: `data-testid="run-elapsed"` (`RunScreen.tsx:196`), driven by `useElapsedSeconds(startedAt)` and cleared to null on stop or landing (`App.tsx:906-909`). Tool chips: `data-testid={\`tool-${call.name}\`}` with `data-layer` (`RunScreen.tsx:340`). Reasoning log: `data-testid="reasoning-log"` inside `ReasoningLog`, built from `steps` (`RunScreen.tsx:369-386`, `hooks/useRunView.ts:740-768`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Submit a question from the home screen | The run screen replaces the home screen | Accessible name `Search the knowledge graph`; `App.tsx:709` sets `searchView` to `{ name: "run" }` |
| 2 | Watch the stepper while the run is in flight | Exactly one step shows `data-state="live"` at a time, in order Guard, Think, Plan, Act, Write; earlier steps show `data-state="done"` | `data-testid="step-Guard"` through `step-Write"`, `data-state` attribute (`RunScreen.tsx:243-247`) |
| 3 | Watch the elapsed counter | It counts up in whole seconds while `running` is true, and stops changing the instant the run lands or is stopped | `data-testid="run-elapsed"`; `aria-hidden="true"` is deliberate, the announcement is separate (see step 5) |
| 4 | Watch for a tool chip once Act starts | A chip appears per tool actually dispatched (in this stack, only `cypher_query` and `ncbi_efetch` are ever reachable, see D6 below), coloured by its data layer | `data-testid="tool-cypher_query"` or `"tool-ncbi_efetch"`, `data-layer` |
| 5 | For a screen-reader user, listen rather than watch | A live region announces "`{Step}` step running" once per step change, not once per second | `data-testid="run-step-announcement"`, `role="status"`, `aria-live="polite"` (`RunScreen.tsx:298-312`) |
| 6 | Open the reasoning log if steps have accumulated | Each line names its step, an elapsed offset, and a one-sentence account of what that step decided | `data-testid="work-panel"` on the answer screen's copy of the same component (`AnswerScreen.tsx:444-448`); on the run screen it renders unlabelled under the "Reasoning" heading (`RunScreen.tsx:359-386`) |

Fails if: two steps show `data-state="live"` simultaneously, the elapsed counter keeps incrementing after the run has landed, a tool chip appears for a tool that was never dispatched, or the screen-reader announcement fires every second instead of once per step transition.

Caution tied to C2 and N1: this workflow proves the stepper is honest about what is happening, not that what is happening is fast. A run that sits on "Act" for fifteen consecutive seconds with no visual change is a real, recorded, ticketless defect (F-6.2-07, N1 in the coverage checklist): the stepper will correctly show `data-state="live"` on Act the entire time, and a test asserting only "the right step is live" will pass while a user watches nothing move. A workflow for perceived responsiveness needs its own timing assertion (elapsed count crossing some ceiling with the run still unlanded), which this workflow deliberately does not add, because turning N1 into a hard pass/fail threshold on a live-model run is a product decision (what ceiling, refuse or keep waiting) nobody has made yet. Recording that gap here rather than inventing a number is the honest version of covering C2 and N1.

## W-thread-2: The answer's provenance spine, citations, sources, and trust pills

The product must: a landed answer shows one spine segment per claim coloured by the data layer that backed it, a citation chip inline on every cited sentence, a collapsible sources disclosure with a full source card per citation, a row of trust pills summarising the run's own grounding verdict, and a status strip naming the outcome and elapsed time.

Status: BUILT. Spine segment: `data-testid={\`spine-segment-${index}\`}`, `data-layer` (`AnswerScreen.tsx:500-509`). Claim text: `data-testid={\`claim-text-${index}\`}` (`AnswerScreen.tsx:513`). Citation chip: `data-testid={\`citation-${n}\`}`, `data-claim`, `data-layer` (`AnswerScreen.tsx:534-566`). Sources disclosure: `data-testid="sources-disclosure"` (`AnswerScreen.tsx:583`), count: `data-testid="sources-count"` (`AnswerScreen.tsx:624`). Trust pills: `data-testid={\`trust-${signal.kind}\`}`, kind is `good`, `risk` or `plain` (`AnswerScreen.tsx:846`). Status strip: `data-testid="answer-meta"` (`AnswerScreen.tsx:386`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Let a groundable question land | The answer screen replaces the run screen | `App.tsx:551-552`, `searchView` becomes `{ name: "answer" }` once `view.landed` |
| 2 | Read `answer-meta` | It leads with a glyph and word matching the outcome (checkmark/"Answered", question mark/hedge wording, warning/"Refused"), then the elapsed time in seconds, then the counts | `data-testid="answer-meta"`; glyph and tone come from `OUTCOME_BY_TRUST`/`OUTCOME_TONE` (`useRunView.ts:612-669`) |
| 3 | Count the spine segments against the claim sentences | One segment per claim, same count, same order, and a segment's height matches its claim's line count because they share one grid row | `spine-segment-{i}` and `claim-text-{i}` share index `i` (`AnswerScreen.tsx:461-475` comment on the grid-row pairing) |
| 4 | Click a citation chip's source open | The sources disclosure expands to show that card, with layer, source, evidence, confidence, and license fields filled | `sources-disclosure`, per-card `open` state (`AnswerScreen.tsx:583` onward) |
| 5 | Read the trust pills | At least one pill always renders once the run has landed, even if the backend sent no `trust_signal` at all, in which case it reads "Not verified" rather than nothing | `trust-risk` with label "Not verified · no grounding check was recorded" (`useRunView.ts:473-476`) |

Fails if: the spine has a different number of segments than there are claim sentences, a citation chip's `data-layer` disagrees with the source card it opens, or a landed run shows zero trust pills.

## W-thread-3: Cite or refuse, the product's central promise

The product must: every sentence the agent writes about biology either carries at least one citation to a real retrieved record, or the whole answer is a refusal naming that nothing grounded was found. There is no third state where an uncited sentence about biology is presented as fact.

Status: BUILT and enforced at two independent points, not one. Backend: the grounding pass (`src/system_03_search_agent/synthesis/grounding.py`) only emits a claim it can trace to a `SynthFinding`; `production-standards.md`'s cite-or-refuse gate names this the highest-leverage correctness control in the system. Frontend: every claim carries a `layer: Layer | null` field where `null` means uncited, and the spine renders that claim in grey specifically so an uncited claim is visible rather than hidden (`AnswerScreen.tsx`, `Claim` interface comment, lines 35-51). A claim's own screen-reader text says so explicitly: "This sentence has no source." when `citations.length === 0` (`AnswerScreen.tsx:519-527`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Ask a question the graph can answer for a resolvable gene | Every rendered claim sentence has at least one non-grey spine segment | `spine-segment-{i}`, `data-layer` not `"none"` |
| 2 | Read the hidden text behind each citation chip | It names the source's own layer and number, not the claim's first citation's layer, so a claim citing two layers announces both correctly | `AnswerScreen.tsx:519-527`, fixed for F-4.9-A-04 |
| 3 | Ask a question naming an entity that does not resolve at all (an unresolvable gene symbol) | No spine renders as a normal answer. The refusal text appears as the run's only content, `answer-meta` reads a refused outcome | `graph.py:2272`, `:2548` (the named-but-unresolvable refusal); see W-thread-8 for exactly how this renders, which is a genuinely different path from a guardrail refusal |
| 4 | Ask a question the graph returns matching data for, but where nothing survives Section 8.2's grounding pass | The system refuses rather than showing an ungrounded narrative, per `_UNGROUNDED_SYNTHESIS_REFUSAL_MESSAGE` (`graph.py`) | Same refusal rendering path as step 3 |

Fails if: any claim on the spine has non-empty text but an empty `citations` array while showing a non-grey segment, or a claim's citation points at a source index that does not exist in `sources`, or a question that should refuse instead produces a spine with grey uncited segments dressed as an "Answered" outcome.

## W-thread-4: A disease name is legible, not a MedGen CURIE (H1)

The product must: when an answer names a disease, it names it in words a reader recognises, cited back to the MedGen record the name came from, never a bare `MedGen:C0346153`-shaped identifier standing in for a name.

Status: BUILT, root-caused and fixed. The Disease `name` column in the graph holds source-vocabulary labels (`SNOMEDCT_US`, `MedGen`, `MeSH`; 3 distinct values across 25 nodes per the shared brief), so a readable name was never expressible from Layer 1 alone. The fix resolves MedGen CURIEs through Layer 2 at query time: ESearch on `[ConceptId]` then ESummary on the returned UID, two calls total regardless of how many diseases are named, mapped back by MedGen's own `conceptid` field rather than by result ordering. See `src/system_03_search_agent/synthesis/disease_names.py`.
Layer: A for the rendering contract (a mock Layer 2 response resolves the same way); B if the workflow is run against a live NCBI ESummary call to prove the resolution itself still works against the real API.
Cost: 0 for Layer A, 1 real answer for a Layer B run

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Ask a disease-anchored question that the graph resolves to a MedGen concept | The rendered claim text contains a disease name, not a string matching `MedGen:C\d+` | `claim-text-{i}` text content |
| 2 | Open the citation for that claim | The source card's record field is the same MedGen concept the name was resolved from | `citation-{n}`, `source-{n}` |
| 3 (Layer B only) | Repeat against the deployed product with a live NCBI call | The resolution still succeeds, not just against a mocked ESummary payload | Real network path to `eutils.ncbi.nlm.nih.gov` |

Fails if: any rendered claim text contains a raw CURIE-shaped token (`[A-Za-z]+:[A-Za-z0-9._]+`) in a position a disease name should occupy.

## W-thread-5: A citation URL on an untrusted host renders as a warning, not a link

The product must: a citation's record URL becomes a clickable link only when it is `https:` and its hostname is on the fixed allowlist of recognised NCBI and ClinicalTrials.gov hosts; anything else renders as plain, unlinked text with an explicit warning, never as a clickable link to an unverified destination.

Status: BUILT, `isLinkableCitationUrl` (`AnswerScreen.tsx:208-215`), checked against `ALLOWED_CITATION_HOSTS` (`AnswerScreen.tsx:198-205`: `ncbi.nlm.nih.gov`, `www.ncbi.nlm.nih.gov`, `pubmed.ncbi.nlm.nih.gov`, `pmc.ncbi.nlm.nih.gov`, `clinicaltrials.gov`, `www.clinicaltrials.gov`). Applied at render time (`AnswerScreen.tsx:782-808`): a linkable URL becomes an anchor with `target="_blank" rel="noopener noreferrer"`; anything else renders as plain text plus "Not linked: this URL is not on a recognised NCBI host." in the risk colour.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Open a source card whose `url` is a real NCBI or ClinicalTrials.gov record | The Record field renders as an `<a>` element pointing at that URL | Source card's Record row, an `a` element |
| 2 | Open a source card whose `url` is on a host not in the allowlist (or is not `https:`), constructed via a test fixture rather than a real backend response | The Record field renders as plain text plus the warning sentence, with no anchor element present | Same row, text content "Not linked: this URL is not on a recognised NCBI host." |
| 3 | Confirm the check is host-pinned, not scheme-only | A URL like `https://ncbi.nlm.nih.gov.evil.example/` fails the check, because `URL.hostname` for that string is `ncbi.nlm.nih.gov.evil.example`, not a member of the allowlist | `isLinkableCitationUrl` is exported and unit-testable directly against this exact string |

Fails if: a URL failing the allowlist check still renders as a clickable anchor, or a URL passing the check renders as plain text.

## W-thread-6: A follow-up continues the thread across two turns, then three (C3)

The product must: asking a follow-up question runs a full new search (never a reuse of the previous answer's grounding), and the finished prior turn is archived into a collapsed, still-readable entry on the same page, in order, oldest first.

Status: BUILT, T-4.16-02 and T-4.8-09. A follow-up is dispatched through the same `ask()`/`onAsk` path a fresh question uses (`FollowUp.tsx` docstring, lines 1-16: "A follow-up runs a FULL search. It is not a chat turn that reuses a previous answer"). Archiving happens in `App.tsx:695-706`, gated on `continuesThread && view.landed && searchView.name === "answer"`, so a run that was stopped or failed mid-flight is never filed away as if it had answered. Thread container: `data-testid="thread"` (`AnswerScreen.tsx:892`), one `data-testid={\`previous-turn-${index}\`}` per archived turn as a real `<details>` element (`AnswerScreen.tsx:899`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Land a first answer, then submit a follow-up via the follow-up field | The run screen reappears (a real second run, not an in-place edit), then a second answer lands | Accessible name `Ask a follow-up question`, button `Ask`; existing coverage at `frontend/e2e/journeys/followup-continuity.spec.ts` |
| 2 | Look at the page once the second answer lands | The first turn's question now appears as a collapsed `<details>` entry above the follow-up field, closed by default | `data-testid="thread"`, `previous-turn-0` |
| 3 | Open `previous-turn-0` | It shows the first turn's claim texts and a source/trust summary line, not the full spine or citation chips (a deliberate simplification for the archived view) | `AnswerScreen.tsx:947-963` |
| 4 | Ask a second follow-up | The thread now holds two entries, `previous-turn-0` then `previous-turn-1`, oldest first, newest turn always at the top of the page as the live answer | Two `previous-turn-{i}` elements, in DOM order |
| 5 | Click "New search" | The thread is cleared, not carried into the next conversation | `setThread([])` in the New-search handlers (`App.tsx:934`, `:1001`, `:1198`) |

Fails if: a follow-up reuses the prior answer's citations without an independent grounding pass, the thread ever shows the turns newest-first, or a stopped or failed run still produces a `previous-turn` entry.

## W-thread-7: The next-step offer, when it appears and when it stays honestly silent (C5)

The product must: after most answers there is nothing more to offer, and the interface says nothing rather than padding with a generic "want to know more?" prompt. When the retrieval genuinely returned more than the answer reported, one specific, honest offer appears, and accepting it continues the thread exactly like typing the same words would.

Status: BUILT, T-6.2-08, product-owner decision 2026-09-01. `_build_next_step_offer` (`graph.py`, function starting "Offer somewhere to go next, or None when there is nowhere honest") returns `None` in four cases: nothing was omitted, the answer was refused, `trust_outcome` is `refuse`, or the omitted rows carry no usable entity type. It is deliberately never model-generated text, exactly to avoid the offer claiming depth the graph does not have. Rendering: `data-testid="next-step-offer"` only when `nextStep` is non-null (`FollowUp.tsx:139-179`), accept button `data-testid="next-step-accept"` dispatches through the same `onAsk` as a typed question (`FollowUp.tsx:167`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Land a complete answer where retrieval found nothing beyond what was reported | No next-step offer renders | Absence of `next-step-offer` |
| 2 | Land an answer where findings were retrieved but not all reported (and the answer was not refused) | The offer appears as one sentence above the hint chips, naming what more exists by type, not by value | `data-testid="next-step-offer"` |
| 3 | Click "Yes, go deeper" (the accept button) | The same `onAsk` path a typed follow-up uses fires with the offer's own text, so the answer that results is archived into the thread exactly like any other follow-up | `data-testid="next-step-accept"`, `FollowUp.tsx:167`; composes with W-thread-6 |

Fails if: the offer ever appears on a refused answer, the offer's wording repeats a specific field value from an omitted finding rather than stating a type, or accepting the offer starts a fresh conversation instead of continuing the thread.

## W-thread-8: Two different refusals, rendered two different ways

The product must: a question refused by the guardrail (off-topic, medical advice, an injection attempt, a rate or cost cap) is a distinct, disclosed event from a question that reaches the graph honestly but finds nothing groundable to answer with. Both are honest refusals. The interface currently tells them apart by where the message appears, and this workflow exists specifically to pin that this is not accidental duplication.

Status: BUILT, but as two genuinely different code paths worth stating precisely rather than assuming they converge. A guardrail refusal sets `view.refusal` from a failed `guard` event's `category`, looked up in `CATEGORY_COPY` (`useRunView.ts:756-758`), and renders as a dedicated notice: `data-testid="guardrail-notice"` while the run is still visible (`RunScreen.tsx:279-281`) and `data-testid="answer-refusal"` once landed (`AnswerScreen.tsx:451`). A "no data" refusal (an unresolved entity, an ungrounded synthesis, or a truncated result with nothing citeable) never touches `view.refusal` at all: it is emitted as a plain `token` event (`graph.py:5518-5524`, `:6025` and the ungrounded-synthesis path), and because its text matches none of `useRunView.ts`'s `SYSTEM_NOTE_PREFIXES` (`useRunView.ts:56-60`), it flows through the same path as any other sentence and becomes the sole entry in `claims`, rendered as one grey, uncited spine segment carrying the refusal sentence and its NCBI cross-database fallback link as if it were prose. The only other signal a reader gets is `answer-meta` reading "⚠ Refused" from `trust_outcome`.

Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Ask an off-topic or medical-advice-seeking question | `guardrail-notice` (while running) or `answer-refusal` (once landed) shows fixed, reviewed copy naming the category; no spine, no claims | `CATEGORY_COPY[category]` (`useRunView.ts`), never the raw backend `reason` text (Section 12.6, no cost figure or free text ever reaches this notice) |
| 2 | Ask about a gene symbol that does not resolve to anything in the graph | No `guardrail-notice` or `answer-refusal` appears anywhere. Instead one grey spine segment renders, its text is the refusal sentence ending in an NCBI cross-database search link, and `answer-meta` reads a refused outcome | `spine-segment-0` with `data-layer="none"`, `claim-text-0` containing "I could not find grounded evidence for this" (`synthesis/refuse.py:27-29`) |
| 3 | Compare the two | They are visually distinct: a dedicated bordered notice box versus a claim-shaped line on the spine | Both testids present in the DOM for a fixture that forces each path |

Fails if: a "no data" refusal is ever mistaken in a test (or by a user) for an ordinary uncited claim requiring a fix, when it is functioning as designed; equally, this is flagged as a real product question worth someone deciding on purpose rather than by accident, since a refusal sentence sharing a rendering with an ordinary claim is a strange place for the product's most safety-critical message to live. Recording this distinction is this workflow's job; deciding whether the "no data" path deserves its own dedicated notice, matching the guardrail path, is a product decision this workflow does not make.

## W-thread-9: The incompleteness disclosures render, and one of the four still cannot (D1, H2)

The product must: when an answer is knowingly partial, truncated, or missing findings, the interface tells the reader so in language addressed to them, never as an uncited claim on the provenance spine and never as internal bookkeeping about "findings prepared for it".

Status: PARTLY BUILT. D1 is confirmed fixed: `App.tsx:965` now passes `systemNotes={view.systemNotes}` into `AnswerScreen`, and `AnswerScreen.tsx:454-456` renders one `data-testid={\`answer-note-${i}\`}` per note. `useRunView.ts:56-63` classifies a token's text as a system note (kept off the spine) by matching it against `SYSTEM_NOTE_PREFIXES`, currently three entries: the per-query cap prefix, "Note: this result was truncated" (the truncation note), and "Note: this answer does not address the following entities" (the unaddressed-entities note, H1/H2's sibling). H2's reword is confirmed in the backend: `_build_incomplete_answer_note` (`graph.py`, function starting "T-4.5-07, F-4.5-06 breach 2") now states "this answer reports N of the M findings prepared for it" language has been rewritten to speak to the reader rather than reporting the internal prepared-findings count as the headline (see the docstring's own before/after, `graph.py` around line 4010-4032).

But a fourth note exists and is not on the prefix list. `_build_repair_cap_note` (`graph.py:3940-3966`) returns "Note: this answer's completeness check could not run to the end because the query reached its cost limit, so the omission described above was not repaired", emitted as a token at `graph.py:6041` whenever a completeness repair itself hits the cost cap. Its text starts with "Note: this answer's completeness check", which matches none of the three `SYSTEM_NOTE_PREFIXES` strings. So this one note, alone among the four, falls through `isSystemNote` as false and is pushed into `claims` instead of `systemNotes`: it renders as an ordinary uncited grey spine segment, exactly the defect D1 fixed for the other three. This was found by reading the prefix list against the four note-builders side by side, not by running anything; it has no frontend test anywhere (`grep -rn "repair_cap" frontend/src` returns nothing) and is reachable in production whenever `omitted_findings` is non-empty and the repair call's own second Synth attempt exceeds the per-query cost cap.

Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Force a query that truncates its Layer 1 result set | A note reading "Note: this result was truncated..." renders as `answer-note-{i}`, not on the spine | `data-testid` starts with `answer-note-` |
| 2 | Force a query whose target entities are not all addressed by the answer | A note reading "Note: this answer does not address the following entities..." renders as `answer-note-{i}` | Same pattern |
| 3 | Force an answer with omitted findings that were not recovered by the repair call | A note stating the count of omitted findings (H2's reworded, reader-facing version) renders as `answer-note-{i}`, never claiming the omitted rows are "in the citations" | Same pattern; text must not contain "findings prepared for it" as its lead clause per H2 |
| 4 | Force the repair call itself to exceed the per-query cost cap while findings remain omitted | Currently: the repair-cap note renders as an extra `claim-text-{i}` with a grey `spine-segment-{i}`, not as `answer-note-{i}`. This step's evidence hook is what a fix should change it to, not what it does today | `graph.py:3940-3966` builds the text; `useRunView.ts:56-60` is missing a fourth prefix entry for it |

Fails if: any of the four note texts occupies a numbered spine segment instead of an `answer-note-{i}` slot, or `answer-note-{i}` never renders at all for a fixture that forces one of the first three notes (which is exactly what D1 was, before the `App.tsx` prop was wired).

## W-thread-10: Stopping a run mid-flight

The product must: clicking Stop aborts the run, the stepper and elapsed counter stop asserting live work immediately, and Stop cannot be clicked again on a run that already finished or was already stopped.

Status: BUILT for the abort mechanics; the interface deliberately shows no further message once stopped, which this workflow states as the observed behaviour rather than the ideal one. `onStop` sets `stopped` to true, calls the local `stop()` to abort the stream, and separately notifies the backend via `stopRun` (`App.tsx:918-928`). `activeStep` is forced to `null` once `stopped` is true (`App.tsx:906`), which makes `running` false in `RunScreen.tsx:166` (`startedAt !== null && activeStep !== null`), which in turn freezes the elapsed counter, stops the live pulse animation, and disables the Stop button itself (`stopEnabled={view.stopEnabled && !stopped}`, `App.tsx:913`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Start a run, click Stop while a step is live | The live pulse animation stops, the elapsed counter (`run-elapsed`) stops changing, and the step that was live keeps its dot but loses the pulse | `run-elapsed` value taken twice, 2 seconds apart, must be equal after Stop |
| 2 | Look at the Stop button after clicking it | It is now disabled | Role `button`, name `Stop`, `disabled` attribute true |
| 3 | Wait after stopping | No message, banner, or confirmation appears anywhere on the run screen. This is the current, observed behaviour, and it is also this repository's own recorded finding D5 ("A user-initiated Stop shows no confirmation... no message", owned by the controls area, not fixed here) | Absence of any `role="status"` text change after step 1 |

Fails if: the elapsed counter or pulse keeps animating after Stop is clicked (the exact defect T-6.2-05's docstring warns against: "an animation still running after the answer arrived would say the system is working when it is not"), or the Stop button remains clickable after a run has already landed or already been stopped once.

## W-thread-11: When a user should see a hedge instead of an answer (H3)

The product must: an answer built from exactly one independent source for a high-stakes field is never dressed up as a confident "Answered" outcome. It renders as an explicit hedge naming the actual limitation (a single source, not independently confirmed), and this is correct, spec-mandated behaviour, not a defect to be smoothed over.

Status: BUILT, and the mechanism is precise enough to state as a rule rather than an impression. `synthesis/trust.py`'s `DECISION_TABLE` (lines 406-413) is Section 8.3.3 transcribed as data: a claim's outcome is keyed on `(risk_tier, grounded, triangulation)`. The row that produces H3's exact observation, `risk_tier: "high"` and `trust_outcome: "ask"`, is `("high", True, "insufficient")`: the claim IS grounded (a real citation exists), the field is high-risk (a clinically consequential value, per `risk_tier_for`), and triangulation could not run because no second independent-origin source existed to compare against, which is different from comparing two sources and finding them to disagree (that row is `"discordant"` and produces `"flag"`, not `"ask"`). `decide()` (`trust.py:416-465`) computes this per claim; `aggregate()` (`trust.py`, Section 8.3.4's severity order, `refuse` > `ask` > `flag` > `answer`) rolls per-claim outcomes up to the run's single `trust_outcome`. On the frontend, `OUTCOME_TONE["ask"] = "warn"` (`useRunView.ts:657`) and the copy is "Single source, not independently confirmed" (`useRunView.ts:621`), a deliberate rewrite of an earlier, wrong "Needs a narrower question" wording (T-4.16-03) that blamed the reader's question for a limitation in the evidence.

Layer: A (the decision table and its wiring are deterministic and testable without a real model call; a fixture can force each `(risk_tier, grounded, triangulation)` combination directly)
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Force a claim that is grounded, high-risk, with only one independent-origin source for its field | `trust_outcome` is `ask`. `answer-meta` shows a `?` glyph in the warn colour and the text "Single source, not independently confirmed" | `answer-meta`, `outcomeTone === "warn"` |
| 2 | Force a claim that is grounded, high-risk, with two independent sources agreeing | `trust_outcome` is `answer`. Normal "✓ Answered" rendering | `answer-meta`, `outcomeTone === "good"` |
| 3 | Force a claim that is grounded, high-risk, with two independent sources disagreeing | `trust_outcome` is `flag`, still "Answered" wording but the run's trust pills should carry the discordance signal, distinct from the `ask` case | `answer-meta` text is "Answered" even though the tone-worthy event is different from step 1; verify the trust pills, not the outcome word, are what distinguish this case |
| 4 | Force a claim that is not grounded at all | `trust_outcome` is `refuse` regardless of risk tier, and triangulation is never even evaluated | `DECISION_TABLE[(tier, False, None)] == "refuse"` for both tiers |

Fails if: a single-source high-risk claim ever renders with the green "✓ Answered" glyph, or a two-source discordant claim renders identically to a single-source insufficient one (they are different rows of the table and should be visually distinguishable, even though both currently show the "Answered" word for the `flag` case per step 3).

## W-thread-12: The answer does not stream. It lands in one or two batches (N3, U3)

The product must: this workflow deliberately does NOT assert word-by-word streaming, because that is not what the system does. What it pins is the real, verified behaviour, so that a future change either preserves it knowingly or is caught the moment it silently regresses further.

Status: NOT a defect in the sense of "broken", but a real gap between appearance and mechanism, and U3 asks directly whether this is by design or an accident: it is neither, cleanly. `write_node` builds its narrative as sentence-level chunks (`_narrative_chunks`, `graph.py:5445-5469`, splitting on `re.split(r"(?<=[.;?!])\s+", ...)`, one chunk per sentence), which is a real, intentional chunking scheme. But every one of those chunks is emitted with the plain `sink.emit(...)` method (`graph.py:6030`, `_EventSink.emit`, lines 585-596), never `emit_live`, and `emit` only appends to an in-memory list; nothing reaches a client until the whole node returns. `emit_live`'s own docstring (`graph.py:602-660`) explains exactly why this matters: "an event emitted inside a node reaches a reader only when the node RETURNS", and LangGraph's `astream(stream_mode="updates")` yields one dict per COMPLETED node. So however many sentences `_narrative_chunks` produces, they all leave the server in one flush, at the moment `write_node` finishes, with no delay engineered or accidental between them. Two chunks arriving 47 microseconds apart, as recorded in the coverage checklist, is consistent with a two-sentence narrative delivered this way; a five-sentence answer would show five `token` events, still all in one flush. The "streaming" a user perceives during Guard, Think, Plan and Act is real, because those steps use `emit_live`. The answer text itself never does.

Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Let an answer land, and record the wall-clock timestamp on each `token` event as it is received by the client | Every `token` event for one answer arrives within the same tens-of-milliseconds window, not spread over the answer's true synthesis time | Timestamp deltas on consecutive `token` events, all near-zero |
| 2 | Compare the number of `token` events to the number of sentences in the rendered claim text | They match (one `_narrative_chunks` entry per sentence, per `graph.py:5459`), even though they all arrive at once | Count `claim-text-{i}` entries against event count in the raw SSE log |
| 3 | Compare this to the Guard/Think/Plan/Act steps of the same run | Those steps' events are spaced out across the run's real elapsed time, because they use `emit_live`, unlike Write's token events | `run-step-announcement` fires at distinct times; token events do not |

Fails if: a future test asserts that token events arrive spaced out over time (they do not, and should not be assumed to), or a future test asserts there is exactly one token event per answer (there can be several, one per sentence, they simply all arrive together). The gap worth someone deciding on purpose: whether `write_node`'s token emission should move to `emit_live` the way the earlier steps did, which would make the sentence-level chunking in `_narrative_chunks` actually visible as it streams in, rather than existing only as an internal shape with no externally observable effect.

## D6: the seven-tool prompt mismatch is a finding, not a workflow

D6 states the model is given all seven tool schemas (`harness/cache.py:254`) while `act_node` can only ever dispatch two, `cypher_query` (`graph.py:3157`) and `ncbi_efetch` (`graph.py:3259`). This is recorded here as a finding rather than a UI workflow, because it has no user-observable surface: nothing on any screen names which tools were offered to the model, only which tools actually ran (the `tool-{name}` chips in W-thread-1, which only ever show the two dispatchable names). A workflow needs an evidence hook a person or a script can check from the rendered page; there is no such hook for "the model was told about five tools it can never call", because that fact lives entirely in a prompt the interface never surfaces. The place this could become user-observable is if a future model, told about `pubtator_annotate` or `litvar2_lookup` in its tool list, ever tries to plan a call to one and the plan step silently drops or mishandles it: that would be a real defect with a real symptom (a plan narrative mentioning a tool that never produces a chip), but it is speculative until it is caught happening, not something to write a pass/fail workflow against today.

## Report

Workflow ids written: W-thread-1 through W-thread-12, plus the D6 finding note above.

Checklist items covered: H1 (W-thread-4), H2 (W-thread-9), H3 (W-thread-11), C2 (W-thread-1's caution, tied to N1), C3 (W-thread-6), C5 (W-thread-7), N1 (W-thread-1's caution), N3 (W-thread-12), U3 (W-thread-12), D1 (W-thread-9), D6 (marked not-a-workflow above, with reasoning).

D6 verdict: not a workflow, a finding. No rendered surface exposes which tools the model was offered versus which it can dispatch, so there is nothing on screen to assert against. Recorded as a finding with a named condition under which it would become user-observable (a plan narrative referencing an undispatchable tool).

H3 verdict: correct, spec-mandated behaviour, not a defect. The `ask` outcome is exactly `DECISION_TABLE[("high", True, "insufficient")]` in `synthesis/trust.py`, the documented row for "a high-stakes claim resting on a single independent-origin source" (Section 8.3.3, quoted in `useRunView.ts`'s own comment). W-thread-11 pins the three-way distinction (`ask` for insufficient triangulation, `flag` for discordant triangulation, `answer` for concordant) that a reader could otherwise collapse into "sometimes it hedges for no clear reason."

Contradicts the shared brief: nothing in the shared brief's feature facts turned out wrong. One addition to it: the brief's "known dead or stubbed" section does not mention `_build_repair_cap_note`'s missing prefix entry (W-thread-9, step 4), which is a genuine, currently-reachable gap found by reading the four note-builders against `SYSTEM_NOTE_PREFIXES` side by side rather than assumed from the brief. It has no test coverage anywhere in `frontend/src`.

Genuinely undefined rather than merely unbuilt: W-thread-8's two-refusal-paths distinction is the clearest case. The guardrail path gets a dedicated, bordered notice component; the "no data" path renders its refusal sentence as an ordinary uncited spine claim, because its text does not match `SYSTEM_NOTE_PREFIXES` and nothing else routes it specially. This is not a bug in the sense of contradicting a stated requirement, cite-or-refuse is honoured either way, but no design document or code comment says these two refusals should look different from each other, and they clearly do. Someone should decide on purpose whether a "no data" refusal deserves the same dedicated treatment as a guardrail refusal, rather than the current state, which is an accident of which prefix list happens to match which string. W-thread-12's streaming question is the second case: `_narrative_chunks` produces real sentence-level chunks and `emit` (not `emit_live`) throws that structure away before it ever reaches the wire, and nothing states whether that is intentional (Write's answer is meant to appear whole) or simply never finished (Write was meant to stream like every earlier step and the `emit_live` migration stopped short of it).
