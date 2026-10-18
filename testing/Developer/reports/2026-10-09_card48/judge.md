# Card 48 judge report

Judge for branch fix/card48-ask-which-aspect at 6de6dbde, base develop b01dee92. Fresh context, read-only on code. Findings are appended as they are established.

## Findings

### J-48-01: Seven real opening questions from the test queries document are asked back on every run

- Severity: critical
- What: the branch's `_ASK_BACK` decision, with `CLASSIFIER_PROVIDER=jev` (the classifier develop uses), picks `ask_back` on 7 of 59 real opening questions of four or more words taken from `testing/Test_queries_and_workflows.md`, 3 of 3 runs each, 21 of 177 calls. On develop none of these reaches the decision (more than three words), so each is a new regression: the person gets "which aspect" instead of the answer the document says they should see.
- Reproduction: harness probe calling `graph._decide_point(Harness(trace_id), trace_id, graph._ASK_BACK, text)` then `graph._usable_choice(record)`, three times each, Jev decided every call (`decided_by` jev, no fallback). Picks observed:

| Query in the document | Picks, 3 runs | What the document says should happen |
|---|---|---|
| 28: `What is under chr17:43,044,295-43,125,364?` | ask_back x3 | Asked which assembly, GRCh38 or GRCh37. The long ask-back returns before the classification, so the assembly question is replaced by an aspect question |
| 31: `What is in BioProject PRJNA999999999?` | ask_back x3 | One line back: the accession was not found in NCBI |
| 42: `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?` | ask_back x3 | The single isolate's details |
| 70: `what does the literature say about metformin` | ask_back x3 | Accepted and searched |
| 81: `What is Marfan syndrome?` | ask_back x3 | Opens on what the disease is |
| 82: `What does the literature say about MTHFR C677T?` | ask_back x3 | Up to 30 sources |
| 85: `what does the literature say about MTHFR` | ask_back x3 | Answers with papers |

- Why it matters: the brief names this as the worst outcome, a real question asked back instead of answered, worse than develop. "What is X?" and "What does the literature say about X?" name the wanted kind of information (a definition, papers), which the `proceed` criterion itself lists, yet the classifier reads them as general requests. An exact accession or coordinate question is about as specific as a question gets.
- NOT FIXED

### J-48-02: Clicking an offered choice can be asked back again, a loop

- Severity: critical
- What: an asked-back turn writes no session memory (`core/run.py`, the end-of-run write returns early when the turn has no resolved entity and no citation, which an ask-back never has). So the choice the person clicks arrives as an opening message with `_session_memory(state) is None`, and since the writer's choices are full questions of four or more words, every click now reaches the `_ASK_BACK` decision. On develop a click of more than three words never did. The writer's own worked example (`core/clarify.py`, `CLARIFY_SYSTEM_INSTRUCTION`) offers "What does recent research say about insulin?", and the decision asks that shape back on every run.
- Reproduction: same probe as J-48-01, writer-style choice texts, three runs each:

| Choice text clicked | Picks, 3 runs |
|---|---|
| `What does recent research say about the tree of life?` | ask_back x3 |
| `What does recent research say about cancer?` | ask_back x3 |
| `What does recent research say about apple trees?` | ask_back x3 |
| `What does recent research say about insulin?` (the writer's worked example) | ask_back x3 |
| `What does recent research say about genetics?` | ask_back x3 |
| 10 other choice texts ("Which genes are linked to cancer?", "Are there clinical trials on cancer?", "What diseases affect apple trees?" and others) | proceed x3 each |

- Why it matters: query 112 in the test document says "Clicking a choice runs an ordinary search on it." Here the person answers our question and is asked another one, possibly the same one again. That reads as the product not listening. It also touches the existing short path: a one-to-three-word subject such as `GERD` asked back on develop offers choices that, once clicked, now reach the decision too.
- NOT FIXED

### J-48-03: A real question now waits for the slower of two decisions, not one

- Severity: minor
- What: for an opening message of four or more words, Think now waits for the `think.ask_back` decision before it reads anything else, so the wait is the slowest of the classification, `think.recent_years` and the new decision. Most of the time this adds nothing: live, the Jev decision took 0.26 s at the median and 1.57 s at worst over 291 calls, below a plan-tier classification. On a Jev failure (3.5 s wait, then the guard tier) a real question waits for that fallback where develop did not ask this decision at all. The wait is bounded by Think's budget.
- Reproduction: own pytest probe (scratch file, not in the repository) with `decide` and the Think classification stubbed to sleep, question `How do birds fly well?`, decision `proceed`:

| ask_back decision delay | Classification delay | Think wall time |
|---|---|---|
| 0.0 s | 1.0 s | 1.14 s |
| 0.5 s | 1.0 s | 1.04 s |
| 2.0 s | 0.5 s | 2.02 s |
| 3.0 s | 0.2 s | 3.04 s |
| hung (1000 s), Think budget patched to 1.5 s | stub | 1.52 s, decision cancelled, question searched |

- Why it matters: the build says "a real question waits for no extra call". That holds only while the decision is faster than the classification; on a slow classifier day it is an extra wait on every opening question of four or more words. Recorded as minor because it is bounded and the live median is small.
- NOT FIXED

### J-48-04: No test covers cancelling the new decision when the turn is stopped

- Severity: minor
- What: the line `_cancel_if_pending(long_ask_task)` in `_think`'s `finally` is the only thing that stops the new decision when the turn itself is cancelled (Stop pressed, client gone): `asyncio.wait` inside `_await_within_step` does not cancel the task it waits on. Deleting that line leaves `test_bare_topic_clarification.py` at 59 passed. The code on the branch is correct; the test suite would not notice its loss.
- Reproduction: mutation, delete `_cancel_if_pending(long_ask_task)` from `core/graph.py`, run `pytest tests/system_03_search_agent/core/test_bare_topic_clarification.py -q`: "59 passed". Own probe (decision sleeping 5 s, outer task cancelled at 0.3 s): on the branch the decision logs `ask_back_cancelled`; with the line deleted the log is empty and the decision keeps running and spending. Restored with `git checkout`.
- Why it matters: a stopped question should spend nothing more. A later refactor of this block could drop the line silently.
- NOT FIXED

### J-48-05: Mutations the author's tests do catch (for the record, not a defect)

- Severity: unsure (record only)
- What and reproduction: own mutations of `core/graph.py`, each restored with `git checkout`:

| Mutation | Result on `test_bare_topic_clarification.py` |
|---|---|
| Small-talk check removed (`ask_beside_classification = True`) | 1 failed, 58 passed |
| Long ask-back return disabled (`if False:`) | 3 failed, 56 passed |
| Decision awaited before the classification is started | 1 failed, 58 passed; own timing probe 1.59 s against 1.04 s on the branch for a 0.5 s decision and a 1.0 s classification |
| Finally cancel deleted | 59 passed (J-48-04) |

- NOT FIXED

### J-48-06: "What can you do?" with its question mark reaches the decision and is asked back

- Severity: major
- What: the new gate's small-talk exemption is `_is_small_talk`, an exact match of `text.strip().lower()` against `prefilter.CONVERSATIONAL_TEXTS`. The guardrail admits the same texts after `prefilter.normalize`, which strips punctuation. So `What can you do?` is conversational to the guardrail (admitted with no relevancy check) but not small talk to Think's gate, and as four words it now reaches the `think.ask_back` decision, which picks `ask_back` on every run. The author's test `test_longer_small_talk_never_reaches_ask_back` uses `what can you do`, the one spelling that matches, so it passes.
- Reproduction: `_is_conversational('What can you do?')` True, `_is_small_talk('What can you do?')` False, 4 words. Live decision probe, 3 runs each:

| Text | Picks |
|---|---|
| `What can you do?` | ask_back x3 |
| `Hello, what can you do?` | ask_back x3 |
| `Thank you very much!` | ask_back x3 |
| `Thanks for the help!` | ask_back x3 |
| `Who are you exactly?` | ask_back x3 |

  Whether the last four reach Think depends on the guardrail's relevancy classifier, not probed here (decide calls only). `What can you do?` reaches Think on both develop and the branch; only the branch asks the decision.
- Why it matters: the brief's check 3, "small talk never reaches the decision", fails for the most natural way to type the product question. The person asking what the product does gets "What would you like to know about ...?" with choices the writer invents for a subject that is not there. On develop it was searched (a separate, older drift between the two small-talk checks), which was not good either, but it did not ask back.
- NOT FIXED

### J-48-07: The false ask-backs are a shape, not noise: "What is known about X?" and "What does the literature say about X?"

- Severity: major (it explains J-48-01; filed separately so a fix is checked against the shape, not the seven texts)
- What: every false ask-back seen is deterministic (3 of 3) and falls into two shapes the `proceed` criterion was meant to keep: an open "what is known / what is in / what is under" question about one named thing, and "what does the literature (or recent research) say about X", which names papers, a kind of information the criterion itself lists. A definition question of four or more words ("What is Marfan syndrome?", "What is the tree of life?") also goes either way by subject, while three-word ones in the same shape proceed.
- Reproduction: live decision probe, 3 runs each, Jev deciding every call:

| Text | Picks |
|---|---|
| `What does the literature say about statins?` | ask_back x3 |
| `What is known about TP53?` | ask_back x3 |
| `What is the tree of life?` | ask_back x3 |
| `What is the BRCA1 gene?` | proceed x3 |
| `What is cystic fibrosis?` | proceed x3 |
| `What is GERD?` | proceed x3 |
| `Tell me about BRCA1 variants.` | proceed x3 |
| `Tell me about trials for melanoma.` | proceed x3 |

- Why it matters: "What is known about TP53?" from a researcher is a request for the evidence, and the product's literature path exists for exactly "what does the literature say". Asking these back costs the person a click and two to three seconds, every time, on questions develop answered.
- NOT FIXED

### J-48-08: Checks that held (record only)

- Severity: unsure (record only)
- Broad subjects: 11 of 11 asked back, 33 of 33 calls, including phrasings not in any prompt or test ("Explain the human genome to me.", "Teach me about evolution.", "I want to learn about genetics.", "Can you tell me about Alzheimer's disease?"). `How do birds fly?` proceeds 3 of 3. So the criterion is not fitted to the owner's one example.
- Follow-ups: own pytest probe, `Tell me about apple trees.` with session memory at `plain_language` and `researcher`: the decision is never asked and no writer call is made. Without memory, both depths ask back with the same question; depth plays no part in the decision.
- Prompt: the `_ASK_BACK` text names no test question and adds no word list; the examples it gives ("how or why something happens, what causes it or whether two things are linked") are kinds of aim, not phrases from the test document.
- Writer call: on a `proceed` pick no writer call is made (author's test, and a `dispatched` check in own probe).
- NOT FIXED

### J-48-09: A clicked "How far back" choice is not exempt from the new decision

- Severity: major
- What: the "How far back should I search?" ask-back also writes no session memory, so the choice the person clicks ("<their question> from the last 5 years?") arrives as an opening message of four or more words and now reaches `think.ask_back`. `think_node` already knows the text is a picked window (`recent_already_picked`) and skips `think.recent_years` for it, but the new gate does not use that, so the aspect question can replace the windowed search the person just chose.
- Reproduction: live decision probe, 3 runs each, texts in the exact shape `clarify.recent_window_choices` builds:

| Clicked choice | Picks |
|---|---|
| `What does recent research say about metformin from the last 10 years?` | ask_back x3 |
| `Recent papers on statins from the last 5 years?` | proceed x3 |
| `Recent papers on BRCA1 from the last 12 months?` | proceed x3 |
| `What is new on CRISPR from the last 5 years?` | proceed x3 |
| `Latest research on Alzheimer's disease from the last 12 months?` | proceed x3 |

- Why it matters: the person answered our question and gets a different one. Same class as J-48-02: a reply to our own ask-back is treated as a new opening message. Develop never asked a decision on these.
- NOT FIXED

## Rates

Live `think.ask_back` decision with the branch's `_ASK_BACK`, `CLASSIFIER_PROVIDER=jev`, Jev decided all 342 calls (no fallback, no missing pick). Decision latency over the first 291 calls: median 0.26 s, 90th percentile 0.31 s, max 1.57 s.

| Set | Texts | Calls | ask_back calls | Texts asked back at least once | Rate |
|---|---|---|---|---|---|
| Real opening questions, 4+ words, from `testing/Test_queries_and_workflows.md` | 59 | 177 | 21 | 7 | false ask-back 11.9 % of calls |
| Real questions, own (broad subject, own aim) | 12 | 36 | 3 | 1 | false ask-back 8.3 % |
| Real questions, own, second batch | 7 | 21 | 6 | 2 | false ask-back 28.6 % |
| All real questions together | 78 | 234 | 30 | 10 | false ask-back 12.8 % of calls, 10 of 78 texts |
| Broad subjects (3 from the brief, 8 own) | 11 | 33 | 33 | 11 | hit 100 % |
| Writer-style choices, clicked | 15 | 45 | 15 | 5 | asked back again 33 % |
| "How far back" choices, clicked | 5 | 15 | 3 | 1 | asked back again 20 % |
| Small talk, 4+ words | 5 | 15 | 15 | 5 | 100 % (J-48-06) |

Every pick was the same on all three runs of its text, so the false ask-backs are not noise: a person typing one of those ten questions is asked back every time. Develop's false ask-back rate on these 4+ word questions is 0 by construction (they never reach the decision).

Spend: OpenRouter "left" 31.6572 before, 31.6253 after, about 0.03 USD for 342 decision calls.

## Tests and checks run

| Run | Result |
|---|---|
| `test_bare_topic_clarification.py`, `test_clarify.py`, and every `tests/system_03_search_agent/core` file that mentions `_think`, `think_node` or `ask_back` (22 files) | 831 passed, 36 skipped |
| `ruff check` (no path) | All checks passed |
| isort on the test file | clean; `core/graph.py` not checked, per the brief |
| Own pytest probes (timing, cancellation, depth, writer call), scratch files outside the repository | as recorded in J-48-03, J-48-04, J-48-08 |
| Mutations of `core/graph.py`, each restored with `git checkout` | J-48-05 |

## Verdict

FIX FIRST.

The goal was "a broad subject asks which aspect; a real question still searches". The first half holds (11 of 11 broad subjects, every run). The second half does not: 10 of 78 real questions, 7 of them from the owner's own test document (queries 28, 31, 42, 70, 81, 82, 85), are asked back on every run, and replies to our own ask-backs (a clicked aspect choice, a clicked "How far back" choice) can be asked back again. That is the outcome the brief names as worse than develop.

Verified with own probes: the false ask-back and hit rates (live decide calls); the loop on clicked choices (live decide plus reading `core/run.py`'s memory write); the small-talk gap (live decide plus a direct call of both small-talk checks); timing and cancellation (own stubbed pytest probes); depth and follow-up behaviour (own stubbed pytest probe); no writer call on a real question (own probe); test-suite strength (mutations). Only read, not run: what the writer would actually offer for each broad subject (no writer calls made, per the brief's decide-only limit), the guardrail's relevancy verdict on the small-talk texts, and any full agent run.

None of these findings sits inside a fix made earlier in this card's own review loop; this is the first review round of the card. J-48-01, 02, 06, 07 and 09 all sit inside the card's one new change, the widened gate and criterion.
