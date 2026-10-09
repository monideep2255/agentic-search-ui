# Card 48 build: a broad opening question asks which aspect first

Base: develop at b01dee92. Branch `fix/card48-ask-which-aspect`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card48_diagnosis.md`, option A, the owner's choice of 2026-10-09.

## Table of contents

- [What the person sees now](#what-the-person-sees-now)
- [What changed](#what-changed)
- [Tests](#tests)
- [Checks](#checks)
- [Left for review](#left-for-review)

## What the person sees now

| Opening message | Before | After |
|---|---|---|
| `Tell me about the tree of life.` | A cited list of papers beside the question | Asked which aspect is meant, when the classifier reads it as a general request |
| `How do birds fly?` | Searched | Searched: a complete question with its own aim |
| `GERD` (one to three words) | Asked back or searched by the classifier | Unchanged |
| Any follow-up inside a conversation | Never asked back | Unchanged |

## What changed

All in `src/system_03_search_agent/core/graph.py`, inside the fence.

| Part | Change |
|---|---|
| `_ASK_BACK` instructions | "a short opening message" becomes "an opening message", and names the third reading: a subject asked about so generally that the answer depends on which aspect is meant. |
| `_ASK_BACK` "ask_back" | Adds a request to be told about a subject in general, with no word naming the wanted kind of information. |
| `_ASK_BACK` "proceed" | A question with its own aim (how or why something happens, what causes it, whether two things are linked) is a request even when its subject is broad. |
| `_think` gate | An opening message (no session memory) of more than three words, and not small talk, now gets the `think.ask_back` decision. The one-to-three-word path is untouched. |
| Timing | The longer message's decision starts beside Think's own classification, so a real question waits for no extra call. The choices writer runs only after the decision picks `ask_back`, so a real question pays for no writing call. |
| Fail open | No usable pick, a failed seam, or choices that could not be written all search, as before. The decision task is cancelled in the same `finally` that cancels the classification. |

No word list and no test question in the prompt. The decision is the classifier's; code only reads its pick.

The prefix-hash check is not needed: `decide` builds its prompt with no stable prefix (`harness/decide.py`, `_build_guard_messages`), so the criterion text never enters a cached prefix.

## Tests

`tests/system_03_search_agent/core/test_bare_topic_clarification.py`. The old `test_four_words_never_reach_ask_back` asserted the gate this card removes, and is replaced by:

| Test | Proves |
|---|---|
| `test_a_longer_opening_message_picked_ask_back_is_asked_back` | An `ask_back` pick on a longer opening message shows the writer's question and choices and runs no tool |
| `test_a_longer_opening_message_picked_proceed_never_writes_choices` | A real question is searched and no writing call is made |
| `test_a_longer_opening_message_writes_choices_only_after_the_decision` | The writer starts after the decision returns |
| `test_a_longer_opening_messages_decision_runs_beside_thinks_classification` | The decision answers only once Think's classification was sent; run before it, the decision times out and the message is searched |
| `test_a_longer_opening_message_fails_open_to_a_search` (4 cases) | No pick, a failed seam, an unparseable reply and a failed writing call all search |
| `test_a_longer_follow_up_never_reaches_ask_back` | The same text with session memory never reaches the decision |
| `test_longer_small_talk_never_reaches_ask_back` | `what can you do` is never asked the decision |
| `test_the_ask_back_criteria_cover_a_general_request_and_keep_real_questions` | The criterion text names both readings |

Mutation: setting `ask_beside_classification = False` (the old gate) turned 4 tests red ("4 failed, 6 passed, 49 deselected"); restored, "10 passed, 49 deselected".

| Run | Result |
|---|---|
| `test_bare_topic_clarification.py` | 59 passed |
| `test_clarify.py` | 39 passed |
| `tests/system_03_search_agent/core` | 1489 passed, 56 skipped |
| `tests/system_03_search_agent/harness` | 448 passed |

No live model calls.

## Checks

| Check | Result |
|---|---|
| ruff on touched files | All checks passed |
| isort `--check-only` on the test file | Passed |
| isort `--check-only` on `core/graph.py` | Fails, and fails identically on develop at b01dee92 (the `contracts.events` import block, untouched here). Pre-existing, outside this card's fence. |
| `tracker/check_doc_sync.py` | ok |

## Left for review

- The held-out live measure from the ticket (ten opening texts, five subjects and five real questions, every real question still searched) needs live model calls, about 20 cents. Not run here.
- An asked-back longer message takes about 2 to 3 s more than a short one, since its choices are written after the decision. The owner's choice, the diagnosis's recommended cost.
- Every opening message of more than three words now makes one more guard-tier decision call, overlapped with Think's classification.
