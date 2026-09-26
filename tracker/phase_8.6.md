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

## History

- 2026-09-25: phase opened by the lead on the product owner's yes ("Yes, same rules"); builders K and L dispatched in parallel.

## Findings

Written the moment a finding is established.
