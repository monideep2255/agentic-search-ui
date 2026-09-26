# Build phase 8.6: Jev makes every choice

Branch: `phase/8.6-jev-everywhere`. Opened 2026-09-25 by the product owner's morning answers (`DECISIONS.md`, 2026-09-25): Jev is the classifier for every classification decision, the guard tier is its fallback only, the comparison of the two moves off the live path, and the stray "MedGen lists no clinical features for ..." sentence is fixed first.

## Table of contents

- [Goal contract](#goal-contract)
- [Budget](#budget)
- [Tickets](#tickets)
- [History](#history)
- [Findings](#findings)

## Goal contract

- Done when: every ticket meets its acceptance; CI green; one judge and one adversary round leave nothing blocking after one fix-and-verify; the golden run on develop after merge answers at least 102 of 150 and its median time to answer is at most 18.1 seconds (phase 8.1's 17.1 plus one).
- Verify: each ticket's tests and live runs; the golden run; the offline comparison script over the golden questions.
- Constraints: every rule under `.claude/rules/`; the cite-or-refuse gate stays exact and the model check fails closed; the prefilter and forbidden categories still run first and unchanged; `CLASSIFIER_PROVIDER=guard` stays the code default; no database migration; the Think, Plan and Write stable prompt prefixes stay byte-identical; nothing committed carries a local machine path (`.claude/rules/public-repository-privacy.md`).
- Blocked-stop: a ticket that needs a file outside its fence, a locked-document edit or a migration stops and is written here.

## Budget

- Wall clock: 8 hours from opening. Dispatches: 8, planned 2 builders, judge, adversary, fix, verifier, product reviewer.
- Golden floor: 102 of 150 (phase 8.2's run, kept by the product owner). Answer path: yes.
- Spend: within the product owner's cap of $8 for the day.

## Tickets

### T-8.6-01: Jev decides; DeepSeek only steps in when Jev fails

Builder K. `harness/decide.py`, `harness/jev_client.py`. Acceptance: with `CLASSIFIER_PROVIDER=jev`, decide() calls Jev alone and calls the guard tier only on a Jev failure (timeout, error, malformed reply, option outside the set), recording the reason; no concurrent comparison call on the live path; each decision's wall time is Jev's time when Jev answers.

### T-8.6-02: The model check on reworded sentences is a Jev decision, still failing closed

Builder K. `synthesis/sentence_check.py`. Acceptance: the per-answer check asks Jev one Bool per sentence in one call where the endpoint allows several questions, after the unchanged code checks (quote in the record, numbers, negation); any failure, unreadable reply or cost-cap hit accepts nothing, exactly as today.

### T-8.6-03: The Jev and DeepSeek comparison runs offline

Builder K. A new script under `testing/Developer/scripts/`. Acceptance: given golden question ids, it asks both models every decision the loop makes for each question and writes an agreement table per decision point; no live path calls it.

### T-8.6-04: The guardrail's injection verdict is a Jev decision

Builder L. `guardrail/classifier.py`, the guardrail node in `core/graph.py`. Acceptance: the verdict is decide("guardrail.injection", ["injection", "not_injection"]) after the unchanged prefilter; a failure of both models behaves exactly as today's failure path; every existing injection test still passes.

### T-8.6-05: The question class is a Jev decision

Builder L. `core/graph.py` think step. Acceptance: the query class comes from decide("think.query_class", <the existing classes>); the plan tier still extracts entities; a failure falls back to today's classification.

### T-8.6-06: A disease's clinical features are spoken of only when the question asks about them

Builder L. `core/graph.py`, `synthesis/findings.py`. Acceptance: a new decision, "think.asks_features", decides whether the question asks about a condition's features or symptoms. Only then is "MedGen lists no clinical features for <disease>" ever stated, and only then are prompt slots reserved for the features (the withdrawn F-8.1-V01 follow-up). `How many genes are associated with breast cancer?` never carries the sentence; `What phenotypic features are associated with Marfan syndrome?` names features in the prose at both depths.

### T-8.6-07: The second writing call fires only when it can change the answer

Builder L, after its own tickets. `core/graph.py`: `_code_built_lines_will_cite` compares record views by citation id while the listing it probes keeps one view per record, so the completeness-repair call to the writing model fires on nearly every question and its reply reached nothing in 4 of 5 traced questions (`testing/Developer/reports/2026-09-25_harness_review/product_harness.md`, W1 and C1). Also `write_node`'s `elapsed_ms` is read before the writing step and so leaves it out of the done event (W3). Acceptance: a three-view paper whose records the listing shows skips the repair; the repair still runs when the model grounded nothing, when a tool failed, or when a code-built sentence fails the pass; the five traced questions make one writing call each on G-012, G-013, G-021 and G-024; `done.elapsed_ms` covers the writing step.

### T-8.6-08: The writer request works for models that need reasoning, a model is priced before it is called, and every call's time is recorded

Builder K, after its own tickets. `harness/harness.py`, `contracts/events.py` (one additive field on the operator-only cost event). Acceptance: a request refused because reasoning cannot be turned off is retried once without the reasoning block and the fallback is logged (C4, W6: "Reasoning is mandatory for this endpoint and cannot be disabled"); a model with no known price fails before the call is sent, with the same actionable message (C6, W7); each model call's elapsed time is carried beside its cost (C5).

### T-8.6-09: The golden run records when the first word arrived and when it started

Builder K. `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py` and `summarize.py`. Acceptance: each saved run keeps its first token's time, which the saved files drop today; the summary adds the median time to the first word and the run's UTC start time; nothing it already reports changes.

## History

- 2026-09-25: phase opened by the lead on the product owner's yes ("Yes, same rules"); builders K and L dispatched in parallel.
- 2026-09-25: T-8.6-07 to T-8.6-09 added by the lead from the product harness review, under the product owner's delegation of the same day ("you take charge and implement the improvement"), handed to builders L and K after their own tickets rather than to new dispatches, so the phase keeps its dispatch budget and needs one golden run. Rationale: the repair call is the largest share of the wait the golden run's median measures.

## Findings

Written the moment a finding is established.
