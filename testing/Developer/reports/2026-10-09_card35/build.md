# Card 35 build: an off-topic follow-up with a biomedical word is checked for topic

Base: develop at b01dee92. Branch `fix/card35-offtopic-followup`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card35_diagnosis.md`. The owner's words: "An off-topic follow-up that happens to contain a word such as 'cell' or 'study' is checked for topic like any other question."

## Table of contents

- [What the person sees now](#what-the-person-sees-now)
- [What changed](#what-changed)
- [Deviation from the fence](#deviation-from-the-fence)
- [Tests](#tests)
- [Checks](#checks)
- [Left for review](#left-for-review)
- [Fix round](#fix-round)

## What the person sees now

| After a BRCA1 answer, they type | Before | After |
|---|---|---|
| `Which cell phone is it best to buy this year?` | A full paid search grounded on BRCA1 | Refused, "Outside biomedical research", when the topic decision says off topic |
| `and what about it in children?` | Answered about BRCA1 | Unchanged |
| `What variants cause it?`, with the topic decision unavailable | Answered | Unchanged: no usable pick still admits it |

## What changed

All in `src/system_03_search_agent/core/graph.py`.

| Where | Change |
|---|---|
| `guardrail_node` | The `guardrail.relevancy` decision starts when the allowlist misses OR `_is_memory_bound_follow_up(query.text, state)` is true. One condition, as the diagnosis proposed. The decision reads the previous question (`_relevancy_state`), unchanged. |
| `_guardrail_after_prefilter` | One added clause: the refusal on "no usable pick and the classifier's off-topic verdict was set aside" applies only when the allowlist missed. See the deviation below. |

The decision is the classifier's; code only reads its pick. The allowlist stays an admission shortcut for a first question, which still asks no decision.

## Deviation from the fence

The fence named `guardrail_node` only. With the one condition alone, an allowlist-admitted follow-up whose topic decision returned no usable pick, and whose guard classifier said off topic, was newly refused: `_guardrail_after_prefilter` refuses that combination, a rule written for allowlist misses (F-8.2-A01). Two existing tests turned red on it, `test_an_off_topic_verdict_on_a_pronoun_follow_up_is_set_aside_when_memory_holds_an_entity` ("What variants cause it?") and `test_with_jev_an_injection_pick_outranks_off_topic_and_memory`, and the grid below found ten cases. A broken classifier would then refuse an on-topic follow-up develop answers. The one added clause in `_guardrail_after_prefilter` keeps develop's fail-open there; only a real "off_topic" pick refuses the newly checked follow-ups.

## Tests

`tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py`:

| Test | Proves |
|---|---|
| `test_an_off_topic_follow_up_with_a_biomedical_word_is_refused` (3 texts by 2 classifier verdicts) | The allowlist admits each text (populate check), the decision is asked with the previous question, and its "off_topic" refuses |
| `test_a_first_question_the_allowlist_admits_still_asks_no_decision` | With no memory the shortcut stands and no decision is asked |
| `test_no_on_topic_follow_up_develop_admits_is_refused` (9 follow-ups by 2 classifier verdicts by 3 decision outcomes, 54 cases) | Every case gets develop's own verdict, written out in the test: admitted where develop admits, refused where develop refuses |
| `_user_content_of_the_guard_call` helper | Finds the guard call by its system message, since a follow-up now also makes the relevancy call, which reads the previous question by design |

Proofs, each pasted from the run:

| Run | Result |
|---|---|
| Develop's `graph.py` with the new tests: the grid | "54 passed": develop admits and refuses exactly what the grid says |
| Develop's `graph.py`: the refusal tests | "6 failed, 55 passed" across the three new groups: the leak is real on develop |
| Mutation: only the `guardrail_node` condition reverted | "6 failed, 115 deselected" |
| Mutation: only the `_guardrail_after_prefilter` clause reverted | "10 failed, 44 passed": the grid catches the fail-open regression |
| Restored, the file | 121 passed |
| `tests/system_03_search_agent/guardrail` | 408 passed |
| `tests/system_03_search_agent/core` | 1479 passed, 56 skipped |

No live model calls.

## Checks

| Check | Result |
|---|---|
| ruff on the two touched files | All checks passed |
| isort `--check-only` on the test file | Passed |
| isort `--check-only --diff src tests services tracker alembic .claude .github` | Clean ("Skipped 2 files"). An earlier draft of this report said isort failed on `core/graph.py`; the judge (J-35-06) could not reproduce that and it was wrong. |
| `tracker/check_doc_sync.py` | ok |

## Left for review

- Cost and wait: one guard-tier decision call on every memory-bound follow-up the allowlist admits, about $0.00008 and 1.7 to 1.9 s measured in F-8.2-A01, run beside the injection classifier, so the person waits for the slower of the two.
- A live check that the real decision calls the three off-topic follow-ups off topic and the controls on topic, five or more runs each, is not run here.
- The deviation above is the owner's or the reviewer's to accept.

## Fix round

Judge verdict MERGE, adversary PASS. One fix, in `src/system_03_search_agent/core/graph.py`.

| Finding | What changed |
|---|---|
| J-35-03 / A-35-01 | The topic decision asked only because the card reached a memory-bound follow-up the allowlist admits now has its own bound, `_FOLLOW_UP_TOPIC_CHECK_BOUND_S` = 1.5 s from when it began (Jev answered in about 0.3 s, 0.77 s at most, beside a guard classifier of 1.9 to 4.4 s). Past it the decision is cancelled and reads as no pick, so the follow-up gets develop's verdict, admitted. A decision inside the bound still refuses an off-topic follow-up. An allowlist miss keeps the full step deadline, as before. |
| J-35-06 | The isort claim in the Checks table is corrected above. |

Tests: `test_a_hung_follow_up_topic_check_adds_only_its_bound_and_keeps_develops_verdict` (2 classifier verdicts) and `test_a_follow_up_topic_check_inside_the_bound_still_refuses`. On cd0e65a8 the hung test fails (2 failed, about 15 s wait); with the fix 3 passed. Mutation: bound removed, 2 failed; restored. Guardrail directory 411 passed, ruff and isort clean.

Left as they are: J-35-02 (a follow-up Jev calls injection may show as off topic, still refused), J-35-04 (a biomedical word with no referring word skips the check), J-35-05 (guardrail step errors, not attributable to the card). Adversary A-35-02 to A-35-05 are live model variance and stay open.
