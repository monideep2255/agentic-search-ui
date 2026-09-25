# Build phase 8.2: the fix-and-verify round

The phase's one fix round, working the lead's triage of round 1 (`tracker/phase_8.2.md`, "Lead triage of round 1"). Each result is written here the moment it is established; the summary table sits above the log.

## Table of contents

- [Summary](#summary)
- [Item log](#item-log)
- [Findings left open, and why](#findings-left-open-and-why)

## Summary

Filled in as each item closes.

## Item log

- Base: `git merge --no-edit origin/phase/8.2-classifier-seam` into this worktree, clean. Baseline suite (harness, guardrail, core): 1602 passed, 56 skipped, 1 deselected.

### Item 1, F-8.2-A01: a follow-up is judged for relevancy like any other question

What the person notices: after an answered BRCA1 question, "and what about it in children?" is still answered, and "What is the best pizza in Chicago and is it cheap?" is refused with the usual off-topic sentence instead of running a paid search.

What changed, all in `core/graph.py`:

- `_relevancy_state` hands `guardrail.relevancy` the previous question when the new one is a memory-bound follow-up (a referring word and a remembered entity): `Previous question in this conversation: <open thread>` then `New question: <text>`. Any other question is judged on its own text, byte for byte as before. The previous question is the person's own earlier words, bounded at 200 characters by the memory contract, and `decide` caps the whole state again.
- The relevancy decision's instructions and criteria say a follow-up may point back at the previous question and that a follow-up about something unrelated is off topic.
- A real `off_topic` refuses a follow-up exactly as a first question (the `and not _is_memory_bound_follow_up` exemption is gone).
- Choice made from the user's chair: when the injection classifier's own off-topic verdict was set aside ONLY by the referring-word rule and the relevancy decision then has no usable pick (both models down), the classifier's verdict stands and the question is refused. Nothing that saw the conversation said it was on topic, and develop refused every allowlist miss outright, so this is never worse than develop. Where the classifier admitted the question, no usable pick still fails open, unchanged.
- `test_personalization_premise.py`'s list of functions allowed to read session memory gains `_relevancy_state`, with the reason.

Tests (`tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py`, `decide` mocked): the pizza, football, weather and movie follow-ups are refused; a follow-up the classifier calls off topic and the decision calls on topic is admitted; the follow-up's state carries the previous question; a question with no referring word is judged on its own text; a set-aside verdict stands with no usable pick (two arms); a follow-up the classifier admits still fails open. The old arm that asserted the set-aside was replaced, since it pinned the defect.

Break-it checks, each on the worktree file copied aside and restored byte for byte (`cmp`):

- Restoring the follow-up exemption on the relevancy refusal: 4 failed (the four off-topic follow-ups).
- Sending the bare question instead of `_relevancy_state`: 1 failed (the state test).

Suite: harness, guardrail and core, 1611 passed, 56 skipped, 1 deselected.

Live, `CLASSIFIER_PROVIDER=jev`, real guard model and real Jev, real `guardrail_node`, memory holding a BRCA1 question (`probe_fix_round_live.py guardrail ... --memory`):

| Run | Question | Result | Relevancy record | Cost, time |
| --- | --- | --- | --- | --- |
| 1 | and what about it in children? | admitted, ok | Jev on_topic 1.0, guard on_topic | $0.00008, 2.7 s |
| 2 | What is the best pizza in Chicago and is it cheap? | refused, off_topic | Jev off_topic 1.0, guard off_topic | $0.00008, 2.1 s |

Live runs spent so far: 2 of 14.

### Item 4, F-8.2-J03, J04 and A12: a real total timeout on Jev, and no waiting on the comparison

What the person notices: with Jev switched on, a slow Jev can hold a decision for at most about 3 seconds, not 16; once Jev has answered, nobody waits for the guard model's comparison pick for more than one second; and when Jev fails, the guard model's answer is used whenever it has arrived.

What changed:

- `harness/jev_client.py`: `call_jev` wraps the whole POST, body read included, in `asyncio.wait_for(..., 3.0)`. httpx's timeout float is four per-phase limits, and its read limit is the gap between two chunks, which is why a trickling body lasted 14 seconds. `JEV_TOTAL_TIMEOUT_S` names the bound for `decide`.
- `harness/decide.py`: the `asyncio.gather` under a 16-second `wait_for` is replaced by two tasks waited on separately.
  - Jev is waited for up to `_JEV_WAIT_S` (its own 3-second bound plus 0.5 s, an outer net only).
  - Jev decided: the guard's comparison pick gets `GUARD_COMPARISON_GRACE_S = 1.0` second. One not ready by then is cancelled and the record says `fallback_reason: "guard_not_ready"` with `guard_choice` None. A dedicated field would be plainer, but `DecisionRecord` lives in `contracts/`, outside this fence, so the existing free-text field carries it and the constant documents the value.
  - Jev failed: the guard's pick decides, waited for within `_GUARD_FALLBACK_WAIT_S` (its own 15-second budget plus 1). The pick is read from the task itself, so one that has arrived is never discarded by an outer limit.
  - Anything still running when `decide` returns or is cancelled is cancelled in a `finally`, and every child task's exception is marked read, so no asyncio "never retrieved" ERROR is logged (this also fixes F-8.2-A05, see item 7).

Measured wall time of `decide()`, from `pytest --durations` on the new tests (`tests/system_03_search_agent/harness/test_decide.py`):

| Case | Fake Jev | Fake guard | decide() wall time | Decided by, record |
| --- | --- | --- | --- | --- |
| Jev in time, guard slow | answers at once | 5 s | 1.00 s | jev; `guard_not_ready`; the guard call cancelled |
| Jev in time, guard inside the grace | answers at once | 0.3 s | 0.30 s | jev; guard pick recorded, `agreed` false |
| Jev slow (real `call_jev`) | 5 s | 0.2 s | 3.00 s | guard; its 0.2 s pick used; `timeout` |
| Jev slow, guard slow | 5 s | 4 s | 4.00 s | guard; its 4 s pick used |
| Jev ignores its own bound and hangs | 30 s | 0.2 s | 3.50 s | guard; the arrived pick used, not discarded |

`call_jev` alone, `tests/system_03_search_agent/harness/test_jev_client.py`: a 5-second fake endpoint and a real httpx client fed a body in four pieces 1.5 s apart both end in `JevCallError(reason="timeout")` at 3.00 s.

Checked against the pre-fix `decide.py` (the committed file swapped in, then restored and `cmp`-verified): the slow-guard, hanging-Jev and cancellation tests all failed on it, 3 failed.

Suite: 1620 passed, 56 skipped, 1 deselected. The new timing tests add about 21 seconds to the run.

### Item 5, F-8.2-A04 (and F-8.2-J13): a decision nobody made is recorded as nobody made it

What the person notices: nothing on screen. What the product owner notices: the `done` event's decision rows and the Jev-against-guard comparison built from them no longer count a model outage as "the guard chose on_topic, ask_back, recent_unbounded or wants_literature".

What changed:

- `decide()` takes `default`, the option the caller acts on when no model makes a pick. When neither model picks, the record has `jev_choice` and `guard_choice` None, `fallback_reason` starting `no_usable_pick` (in Jev mode followed by Jev's own reason, e.g. `no_usable_pick:timeout`, `no_usable_pick:cost_cap`), and `chosen` equal to `default`. A default outside the options raises.
- `core/graph.py`: every `_DecisionSpec` names its `fail_open` option (relevancy `on_topic`, ask_back `proceed`, recent_years `not_applicable`, literature `not_literature`), and `_decide_point` passes it. So `chosen` in the record is what the run actually did. `_usable_choice` still reads "was anything decided" from the two picks, so nothing is acted on as a pick.
- Left as is, and why: `decided_by` still reads `"guard"` in that case, because `DecisionRecord.decided_by` is `Literal["jev", "guard"]` in `contracts/events.py`, outside this fence, and a new value is not a missing bound. The None picks and the `no_usable_pick` reason are what say nobody decided. A `"none"` value is a one-line additive contract change for whoever owns the contract.

Tests: four Jev failure types with a guard that gives no pick (all record no pick, the default and `no_usable_pick:<reason>`); a guard-only failure; a default outside the options; and, through the real `decide` and `core/graph.py`'s `_decide_point`, each of the four wired decisions records its fail-open option when the guard's reply names no option. The cost-cap arm's old assertion (`fallback_reason == "cost_cap"`, `chosen == options[0]` read as a guard pick) was updated because it pinned the defect.

Break-it check: restoring the old record (first option, Jev's bare reason) on a copy-aside of `decide.py`: 5 failed; restored and `cmp`-verified.

Suite: 1630 passed, 56 skipped, 1 deselected.

### Item 2, F-8.2-A07 and F-8.2-J01: no publication-date limit is ever read from the question's wording

What the person notices: "risk of stroke in the last month of pregnancy" searches all the papers on stroke in pregnancy, not the past four weeks of them; "statin trials in 2000 patients with heart failure" is no longer limited to papers from the year 2000. A person who is asked "How far back should I search?" and clicks "the last 5 years" still gets only papers from those years, on a topic question and on a gene or disease question alike, and the plan says so.

How the picked window travels, since the chip comes back only as text: the web client sends the clicked option's string and nothing else, and neither the event contract nor the client is in this fence. So the server remembers what it offered.

- `core/clarify.py`: `RECENT_WINDOWS` pairs each phrase with its months (12, 60, 120). `offer_recent_windows(session_key, question)` writes the three options and records each option's exact text against its window; `picked_recent_window(session_key, text)` returns the stored window only when the new question IS one of those options (whole text, surrounding whitespace aside). Keyed by caller and session (`owner_id` plus `session_id`), at most 1024 sessions, an hour each, in process only. Nothing is parsed from the text; text nobody was offered limits nothing.
- `core/breadth_plan.py`: `parse_publication_window` is removed. `states_publication_range(question)` only answers "does this question already name a range" (so it is not asked back again); `recent_publication_window(months, label)` builds the limit from the picked value. The range regexes now only keep a range's own words out of a topic term, which broadens a term and never adds a limit; "weeks" and "days" were added so "in the last 2 weeks" no longer makes "last" and "weeks" required words (F-8.2-J02).
- `core/graph.py`: Think offers the windows through `offer_recent_windows`; a question that is a picked option is not asked the recent-years decision at all; Plan limits PubMed only by `_picked_publication_window`. The topic narrative reads "published in the last 5 years" (the missing "in", F-8.2-J14), and the gene and disease narrative now says "PubMed papers published in the last 5 years only" (F-8.2-J01 found it silent).
- A question that states its own range ("since 2022") is still not asked back, and its search is not narrowed either, per the brief.
- Limitation, stated: the offer lives in the server process. A restart, or a click landing on a second process, loses it, and the click then searches without a limit: the honest broad search, never a guessed one. The deployment runs one process (`railway.json` starts one uvicorn with no `--workers`).

Tests:

- `test_breadth_plan.py`: picked windows count back correctly (12, 60, 120 months), a month end is clamped, a non-recency window is refused, `states_publication_range` for eight stated forms and five non-ranges, `parse_publication_window` no longer exists, and "in the last 2 weeks" and "in the last month of pregnancy" add no date clause.
- `test_clarify.py`: each offered option carries its own window; text nobody was offered (another session, extra words, before any offer, after a clear) picks nothing; the record is bounded and expires.
- `test_bare_topic_clarification.py`, through the real five-node graph: the five J01 and A07 questions send no `[dp]` clause and no "published in" narrative; "since 2022" is not asked back and not limited; asking "recent papers on statins" then clicking the 5-year option sends `statins AND ("<5 years ago>"[dp] : "3000"[dp])`; asking "recent papers on BRCA1" then clicking the 5-year option sends `BRCA1[Title/Abstract] AND (...)` while ClinVar stays unlimited (F-8.2-J07); the 5-year option's words typed with no offer limit nothing.

Break-it checks, graph.py copied aside and restored with `cmp`:

- Deleting `window=publication_window,` from the `_build_breadth_calls` call in `plan_node` (the judge's J07 mutation): 1 failed, the gene arm. It was green on the judge's run.
- Limiting the search whenever the words name a range: 9 failed.

Suite (harness, guardrail, core, and the debugging-guide coverage test): 1654 passed, 56 skipped, 1 deselected.

Follow-up outside this fence: `docs/build/Debugging_guide.md`'s `core/breadth_plan.py` row still names `parse_publication_window`; one line for whoever owns the guide.

### Item 3, F-8.2-A10, A16 and J14: sharper criteria for recent_years and relevancy

Live runs, `CLASSIFIER_PROVIDER=jev`, appended as each finishes:

| Run | Probe | Result | Record | Cost, time |
| --- | --- | --- | --- | --- |
| 3 | recent_years, G-003 (Lynch syndrome ... current trials?) | not asked back | Jev not_applicable 0.98; guard not ready within 1 s | $0.00002, 1.4 s |
| 4 | recent_years, G-003 again | not asked back | Jev not_applicable 0.98, guard not_applicable, agreed | $0.00003, 1.2 s |
| 5 | recent_years, G-030 (EGFR ... what trials are recruiting?) | not asked back | Jev not_applicable 0.96; guard not ready within 1 s | $0.00002, 1.4 s |
| 6 | recent_years, G-030 again | not asked back | Jev not_applicable 0.96; guard not ready within 1 s | $0.00002, 1.3 s |
| 7 | recent_years, "recent papers on statins" | asked "How far back?" | Jev recent_unbounded 1.0; guard not ready within 1 s | $0.00002, 1.2 s |
| 8 | guardrail, "make me a weekly workout plan" (no memory) | refused, off_topic | Jev off_topic 0.89, guard off_topic | $0.00008, 2.7 s |
| 9 | guardrail, "does coffee help exercise performance" (no memory) | admitted, ok | Jev on_topic 1.0, guard on_topic | $0.00008, 1.7 s |

Acceptance met: G-003 and G-030 not asked back, 2 of 2 each (Jev not_applicable at 0.96 to 0.98, where round 1 measured recent_unbounded at 0.32 to 0.86 on every pass); "recent papers on statins" still asked; the workout plan refused; the coffee question admitted.

What changed, `core/graph.py` only, the descriptions both models receive:

- `think.recent_years`: `recent_unbounded` only when the question EXPLICITLY asks for recent, new or latest publications, papers, studies or research and gives no year, date, period or length of time. `not_applicable` spells out the rest: a period named by an event, a disease of recent onset, something a person did or had recently, the current status of a disease, treatment, guideline or trial, and current or recruiting trials.
- `guardrail.relevancy`: a request to make a personal plan for the asker (a workout, meal or diet plan) is off topic, because it asks for advice, not evidence; a research question about exercise, diet or nutrition is on topic.
- No confidence threshold was added: acting on Jev's confidence number is a decision the product owner has not taken.
- Examples in the criteria are categories, not the round's probe questions (the owner's rule against lifting test questions into prompts); "recent onset" and the workout and meal plans are the brief's own words.
- The descriptions stay under `decide`'s 1000-character bound; the item 5 test in `test_graph.py` runs every spec through the real `decide`, which raises on an over-long description.

Observed, for the product owner (card 10): with the one-second comparison grace, the guard's pick was not ready in 4 of the 5 recent_years probes (Jev answers in about 0.3 s, the guard in 1 to 2 s), so those rows carry `guard_not_ready` rather than a guard pick. The person waits less; the comparison table gets fewer guard rows. Keeping the guard call running past the grace and filling the row in later would restore them, at the cost of background calls that outlive the decision.

Live runs spent so far: 9 of 14.

## Findings left open, and why

Filled in at the end.
