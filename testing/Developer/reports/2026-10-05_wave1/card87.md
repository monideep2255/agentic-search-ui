# Card 87: a subject plus the kind of thing wanted is answered

## Table of contents

- [The change](#the-change)
- [Live runs](#live-runs)
- [Tests](#tests)
- [Gates](#gates)
- [Not covered](#not-covered)

## The change

- A person who types `recent-onset diabetes treatment` named a subject and what they wanted, and was asked back. A bare subject is still asked back.
- File `src/system_03_search_agent/core/graph.py`, the `_ASK_BACK` criteria. The `ask_back` criterion now reads "a subject on its own, with no word saying what to find out about it". The `proceed` criterion now says a subject followed by a word naming the wanted kind of information is a request, with therapy options added to the examples. The owner approved naming therapy options on 2026-10-05.
- No test question and no disease or gene name is in the spec. The instructions line is unchanged.
- Queries 76 and 84 in the test document needed no edit: neither contradicts the owner's decision.

## Live runs

Each run calls the classifier (Jev, as `CLASSIFIER_PROVIDER=jev` does) with the real `_ASK_BACK` instructions and criteria, one call per run. P is proceed, A is ask_back.

| Wording | recent-onset diabetes treatment (want P) | GERD, BRCA1, Marfan, reflux disease (want A) | papers on statins since 2022, Any trials for GERD? (want P) |
|---|---|---|---|
| Baseline (old text) | A A A A A, wrong | 5 of 5 each, right | 5 of 5 each, right |
| Wording A: subject only vs subject plus what is wanted, old example list kept | A x5, wrong | 5 of 5 each, right | 5 of 5 each, right |
| v1: two things, a subject and a statement of what is wanted | A x3, wrong | 3 of 3 each, right | 3 of 3 each, right |
| v3: v2 without "therapy options" | A x3, wrong | 3 of 3 each, right | 3 of 3 each, right |
| v4: v3 plus "or what to do about it" | A x3, wrong | 3 of 3 each, right | 3 of 3 each, right |
| v5: examples as aspects, ending "or management" | A P A, wrong | 3 of 3 each, right | 3 of 3 each, right |
| v6: general, "a word about the subject" | A x3, wrong | 3 of 3 each, right | 3 of 3 each, right |
| v7: general, "last word is something looked up" | A x3, wrong | 3 of 3 each, right | 3 of 3 each, right |
| v2, applied: examples include "therapy options" | P x5, right | 5 of 5 each, right | 5 of 5 each, right |

- The classifier follows the example words in the criteria and does not move on a general description alone. That is why the owner allowed one therapy example.
- v2 was run 5 times on each of the seven queries: 35 of 35 correct.

## Tests

- `test_ask_back_spec_says_a_subject_plus_a_wanted_kind_is_a_request` in `tests/system_03_search_agent/core/test_graph.py`. It failed on the old spec text (run with the source change stashed) and passes on the new one.
- It pins the spec text only. It cannot say how the classifier picks.

## Gates

- Gate 2 (import order): pass.
- Gate 3 (ruff over the whole repository): pass, all checks passed.
- Gate 4 (unit suite): 6803 passed, 143 skipped, 24 deselected, 1 xfailed, in 827 s.

## Not covered

- The golden run (at least 101 of 150) and the lead's test queries on develop are the gate and were not run here.
- Live runs call the classifier directly, not the whole agent: the short-question path (three words or fewer, no memory) and the writer of the choices were not exercised.
- Four-word phrases and other languages were not tried.
- Wording was tuned against these seven queries, so a near neighbour (another subject plus a different request word) is unmeasured.
