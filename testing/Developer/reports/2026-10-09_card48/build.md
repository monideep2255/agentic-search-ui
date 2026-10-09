# Card 48 build: a broad opening question asks which aspect first

Base: develop at b01dee92. Branch `fix/card48-ask-which-aspect`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card48_diagnosis.md`, option A, the owner's choice of 2026-10-09.

## Table of contents

- [What the person sees now](#what-the-person-sees-now)
- [What changed](#what-changed)
- [Tests](#tests)
- [Checks](#checks)
- [Left for review](#left-for-review)
- [Fix round](#fix-round)

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

## Fix round

After the judge's and the adversary's first round (`judge.md`, `adversary.md`). The bar, set by the lead: no real question asked back in three live runs, broad subjects asked back on at least 90% of calls, and five structural fixes, each with a test.

### What changed

| Finding | Fix |
|---|---|
| J-48-01, J-48-07, A-48-02, A-48-03, A-48-15: real questions asked back | `_ASK_BACK` rewritten. The classifier sets aside the words that only ask to be told or taught, then asks back only when what is left is the name of one subject alone. A question asking what something is, what is known or what the research or literature says about a named subject is a request with its own aim, as is a case, a population or a pasted text. No test question and no word list in the text. |
| A-48-01: a named record asked back | `_names_a_record`: after the classifier's pick, a message holding a PMID, an rs number, a RefSeq accession, a CURIE, an NCBI accession or a chromosome window (the parsers the search already uses) is searched, on both the longer and the one-to-three-word path. |
| J-48-02, J-48-09, A-48-06, A-48-13: a clicked choice or a follow-up asked back again | `clarify.begin_turn` records every turn Think sees against its caller and session (in-process, at most 4096 sessions, one hour after the last turn). Only a conversation's first message reaches the longer message's decision. The client sends a click as plain text, so the server remembers instead. |
| J-48-06: `What can you do?` reached the decision | The gate reads small talk after the guardrail's own `prefilter.normalize`. |
| A-48-09, J-48-03: a slow decision held Think | The longer message's decision is waited for at most `_LONG_ASK_BACK_WAIT_S`, 1.0 s from its start; past it the message is searched. |
| J-48-04, A-48-14: the cancel in `finally` untested | New test; deleting the line turns it red. |
| A-48-16: query 112's promises | Rewritten to state only what was measured. |

### Live rates

`decide` with the worktree's `_ASK_BACK`, `CLASSIFIER_PROVIDER=jev`, three runs per text, every call decided by Jev with no fallback. "Asked back" is the outcome after the code's named-record check.

| Set | Texts | Calls | Classifier picked ask_back | Asked back |
|---|---|---|---|---|
| Judge's real questions (59 from the test queries document, 19 own) | 78 | 234 | 0 | 0 (0 %) |
| Adversary's real-question probes (A-48-01, 02, 03, 05, 15, the controls, three with steering text) | 40 | 120 | 9 (PMID, rs334, NM_000546.6) | 0 (0 %) |
| Broad subjects (judge's 11, with `Tell me about the tree of life.`) | 11 | 33 | 33 | 33 (100 %) |
| Held out, written after the wording was fixed: real questions | 15 | 45 | 0 | 0 |
| Held out: broad subjects | 10 | 30 | 30 | 30 (100 %) |
| One to three words: bare subjects (`GERD`, `cancer`, `tree of life` and four more) | 7 | 21 | 21 | 21 |
| One to three words: subject plus a kind (`GERD symptoms`, `What is GERD?` and four more) | 6 | 18 | 0 | 0 |
| Clicked choices (judge's 15 writer-style, 5 "How far back"), for the record: the gate no longer asks them | 20 | 60 | 0 | 0 |
| Contested, broad-shaped (`Tell me about TP53.`, three non-English, two in simple words, and nine more) | 15 | 45 | 38 | 38 |

Contested texts searched: `Everything about APOE` (3 of 3), `Give me an overview of cystic fibrosis.` (3 of 3), `Tell me about the BRCA2 gene.` (1 of 3). Decision latency over the 432 calls of the final run: median 0.27 s, 90th percentile 0.33 s, maximum 1.04 s, so about one call in 400 passes the 1.0 s bound and is searched.

Wording: six versions were measured before this one. Writing "a request to be told about a subject in general" asked back "Tell me about BRCA1 variants." and "Tell me about clinical trials for ALS."; the set-aside test with "the name of a subject alone" fixed those; `Tell me about BRCA1 mutations.` and the misspelt `tel me abuot brca1 mutatons` needed the subject-plus-its-variants-or-mutations sentence and the instruction to read misspelt words as meant. Tuning sets and bar sets overlap, which is why the held-out sets above were written afterwards and run once the wording was fixed. No writer calls were made.

Spend: OpenRouter "left" 31.6231 before, 31.4999 after, about 0.12 USD for about 2,500 decision calls.

### Tests

| Test | Proves | On 6de6dbde |
|---|---|---|
| `test_longer_small_talk_never_reaches_ask_back` (4 spellings) | `What can you do?` in any punctuation never reaches the decision | 3 of 4 red |
| `test_the_next_message_of_a_conversation_never_reaches_the_longer_decision` (3 cases) | A clicked choice, a typed reply after an ask-back, and a follow-up after a turn with no memory are never asked the decision or written choices | 3 red |
| `test_a_new_conversation_opens_with_the_longer_decision_again` | A second session's opening message is still asked | green (control) |
| `test_a_message_naming_one_exact_record_is_searched_whatever_the_pick` (4 cases) | A PMID, rs number or RefSeq accession is searched on an `ask_back` pick, on both paths | 4 red |
| `test_a_hung_longer_decision_adds_at_most_its_own_bound` | A hung decision is stopped at the bound and the message searched | red (held past the five-second guard) |
| `test_stopping_the_turn_stops_the_longer_decision` | Stopping the turn stops the decision | green; red with the `finally` cancel deleted |
| `test_the_ask_back_criteria_name_a_subject_alone_and_keep_real_questions` | The criterion text names both readings | red |

Mutations of the fixed `core/graph.py`, each in a scratch copy: the `finally` cancel deleted (1 red), the opening gate dropped (3 red), the exact small-talk check restored (3 red), the record check removed (4 red), Think's deadline in place of the bound (1 red).

| Run | Result |
|---|---|
| `test_bare_topic_clarification.py` and `test_clarify.py` | 111 passed |
| The 20 core test files that touch `_think`, `think_node` or `ask_back` | 771 passed, 34 skipped |
| `tests/system_03_search_agent/core` | 1502 passed, 56 skipped |
| `ruff check` (no path) | All checks passed |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | Passed |

### Left open

- The writing call after an `ask_back` pick is not bounded beyond its own budget (A-48-08, A-48-10); it runs only on a real `ask_back` pick, which no real question in the sets above received.
- The record of begun conversations lives in one process; a restart or more than 4096 live conversations makes the next message look like an opening one again.
- The web client keeps one session id until sign-out or a reload, so "New search" after any question is not an opening message; the same was already true whenever the earlier turn stored memory.
- With the classifier at its code default (the guard tier), a decision slower than 1.0 s is searched, so the longer path may ask back rarely there. Not measured.

