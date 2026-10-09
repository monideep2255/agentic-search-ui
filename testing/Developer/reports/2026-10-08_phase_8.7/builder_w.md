# Builder W, phase 8.7, steps 5 and 6

Builder W's running record for build phase 8.7, steps 5 (card 2, the first sentence) and 6 (card 50, the summary sooner), merged by hand from commit 32e5945e onto today's write step.

## Table of contents

- [Base](#base)
- [Findings](#findings)
- [Deviations from the plan](#deviations-from-the-plan)
- [Open questions](#open-questions)
- [Learnings](#learnings)

## Base

- Worktree branch `feat/8.7-w`, cut from `phase/8.7-answers-sooner` at 586d715183733f94c2a2059c18222732caccbb57.

## Findings

- Step 5 lifted cleanly by hand: `harness/decide.py`, `synthesis/answer_layout.py` and the `_answer_tokens` summary block had not moved in a way that conflicts. Today's `answer_summary_sentence` has four `return` points (plain and technical, with and without the fold clause); all four go through `finish`.
- The lead decision runs only with `CLASSIFIER_PROVIDER=jev`. A deployment where the guard tier decides alone keeps today's count line leading, as the plan says.
- Mutation checks for step 5: passing `lead_index=None` turns 4 lead-sentence arms red; passing `asked_field=None` turns the honest-gap wiring arm red.

- Step 6, the seven merge points, each with an arm in `test_write_answers_sooner.py` shown red by a mutation of the code it guards:

| Point | What the code does | Mutation that turns its arm red |
|---|---|---|
| 1, the repair-keep rule | One keep block judges both the sequential repair and a second draft started beside the first, with #163's `more_on_the_same_records` | Strict superset only |
| 2, the cost limit | A cap hit at the writer call after the listing was sent sets `cap_hit` and takes #168's path and note; `_build_writer_cap_note` is gone. Before the listing is sent, a cap hit still returns `_partial_result_for_cap`, as `test_graph.py` pins | Marking it a writer failure instead |
| 3, the second draft's cap check | `_two_drafts_fit_cap` prices each draft with the new public `cost_control.estimate_next_call_cost_usd`, the cap check's own computation | The old static `estimate_call_cost_usd("synth")` |
| 4, a dropped draft's metered cost | The per-draft estimate ($0.132 on Opus) bounds a cancelled call's metering ($0.08), so a dropped draft cannot carry a question past the cap that admitted it; a property arm pins the bound, and the dropped-draft arm reads the metered cost | Not cancelling a dropped draft |
| 5, one row per record | The listing is built once, whole, by the answer's own builder before any of it leaves, and the final answer never builds it again when it was sent | Building the listing a second time in the final answer |
| 6, the early numbering | The listing's claims lead the merged claims, so its numbers cannot move; the final answer keeps the sent citation payloads and never sends one twice | Prose claims first in the merge |
| 7, nothing shown is taken back | A writer failure after the listing leaves it as the answer with `_build_writer_failed_note`, floored at "ask", no error event, and no second writer call | Refusing after the listing was sent |

- The early-sent chip text. A record cited by both the listing and the prose has, without early send, one citation whose `claim_text` joins the listing's checked words and the prose's quote (card 57). When the listing goes out early, its citation is final and is not sent again, so that chip shows the listing's words only. Re-sending a corrected citation is not safe: the MCP server appends every citation event it sees, so one record would be listed twice. The quote is always words of the same record value the listing shows, so nothing unsupported is shown, but the chip is less pointed. The lead or owner may want a contract rule for an updated citation.
- When `placement` lands in `TokenPayload`, these tests outside my fence go red, checked by switching the field on for the whole core directory (23 fail, 2 of them my own "without the field" arms, since pinned with `_contract_carries_placement` so they hold either way): `test_run_registry_stop_mid_write.py` s1 to s4 and `test_run_registry_stop_after_done.py` b (records now exist before a stop mid-write, as the owner's 2026-09-27 decision intends), `test_write_streaming_premise.py` w3 (a citation now precedes summary tokens), `test_write_answer_structure.py` three arms and `test_write_findings_tail.py` one arm (they read the answer in arrival order, where the listing now comes first). `test_breadth_wiring.py`'s two arms failed only because my probe patched `TokenPayload` in `core/graph.py` alone. This is the order change builder A's LEARNINGS row of 2026-09-27 predicted; whoever lands the field reshapes them.
- One test outside my fence goes red on this commit: `tests/system_03_search_agent/synthesis/test_check_every_rewording.py`, its two repair arms. Its fake writer picks the repair by `completeness._CORRECTION_MARKER`, and the second draft now starts beside the first carrying `COMPLETENESS REQUIREMENT`. The one-line fix, line 264: `if any(marker in joined for marker in completeness._SECOND_DRAFT_MARKERS):`. I ran it with that line (12 passed) and put the file back, since it is outside my fence.
- The live probe for step 6 must count a repair by either marker: the 2026-09-14 measurement scripts detect a repair by "COMPLETENESS CORRECTION" alone.
- The writer-failed note is typed `kind="note"`, so the web screen shows it; it is not one of `AnswerScreen.tsx`'s `HIDDEN_NOTE_PATTERNS`. `useRunView.ts`'s `SYSTEM_NOTE_PREFIXES`, kept for producers that send no `kind`, does not list it; the frontend builder may add "Note: the written summary could not be finished".

## Deviations from the plan

- Step 6: `_answer_tokens` keeps its signature and still returns one list, because `test_write_answer_structure.py`, outside my fence, calls it directly with `fallback_sentences` and `tail_sentences`. The three parts come from a new `_answer_parts`, which builds the one list exactly as before and only marks where the listing and the notes start; `_answer_tokens` joins the parts. Builder A replaced the two arguments with one `listing_sentences` and changed the return type.

- Step 5: the three lead-sentence functions and the two budget constants sit just above `_answer_tokens`, under their own card 2 banner, rather than inside builder A's single 8.7 block, so step 5 can be read and reverted alone.
- Step 5: three arms added that 32e5945e did not have: the honest gap reaching the count line from `think.asks_features` on the write path, the count line unchanged when nothing was asked for, and the closed lead options. The first fails on code that does not pass `asked_field`.

- Step 6: after a writer failure with the listing on screen, no completeness repair is asked for, as in builder A. A repair is another call to the model that just failed, and the listing is already the answer.
- Step 6: the `LEARNINGS.md` row from 32e5945e is not added. `LEARNINGS.md` is outside my fence; the lead adds it by hand, as the plan says.

## Open questions

- "Records numbered in the order the list shows them" holds fully in Plain language and for single-type answers, not for every Researcher answer. The listing's numbers now come first, in the order its sentences are grounded, which is the order Plain language shows them. The Researcher table groups rows by type and puts a mapping table's diseases first, so where types interleave in finding order (the context calls share their slots one row per round), a Researcher group can still read [11], [13], [15]. Numbering by the Researcher layout broke `test_12_9_the_firewall_depth_changes_the_display_never_the_evidence`: the firewall (item 12.9, rule 5) says the depth never changes a row's marker, and the two depths show different orders. Closing it fully needs the listing's sentences put in one order both depths show, grouped by type, which reorders the Plain language list. That is a display change for the owner or lead to decide; I did not make it.

- Option B cannot fire at a 25-cent cap with the Opus writer once `_two_drafts_fit_cap` prices both drafts at the answering model's price, as the plan's third merge point requires. `cost_control` prices one synth call on Opus at its bounding profile, 23,000 prompt and 2,000 output tokens at $4 and $20 per million, which is $0.132. Two of them are $0.264, above $0.25 before anything else on the question is counted. So on develop at 0.25 the second draft always waits for the first, as today, and the write-step gain the plan expects from option B (median 14.2 s to 11.7 s) will not show in the step 6 probe. A cancelled draft is metered at 4,000 output tokens, $0.08, which the $0.132 bound covers, so the check is not over-cautious about a dropped draft; it is the bound on a completed one. The lead's call: accept that option B is off at 25 cents, raise the cap, or price the second draft by a measured figure instead of the bound. I built it as the plan says and did not change the bound.

## Learnings

- 2026-10-08, the step 6 commit was held by `mod-public-repo-guard` with "the guard failed while checking this call", on every retry, with or without the measurement files staged and with a one-line message. Tried: a message file instead of `-m`, unstaging the lifted scripts, a dry run, retrying. The leak scanner the guard runs (`.claude/skills/ship/scripts/check_public_leaks.py --no-fetch`) passes when run by hand, in 14 seconds, while the machine's load average stood at 40 from parallel builders, so the guard most likely ran out of time rather than found anything. Retried again once the load fell to 19: still held. The scanner takes 13.5 seconds, 11.7 of them its own CPU time, so the likelier cause is the guard's own time limit against a scan that grew with step 6's 1,700 changed lines (the step 5 commit, about 650 lines, passed). Nothing fixed it; step 6 is left staged for the lead rather than committed around the guard.
