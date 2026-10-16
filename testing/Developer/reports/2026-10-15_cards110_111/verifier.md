# Cards 110 and 111: fresh verifier

Bases: branch worktree `<scratchpad>/v110` at 3cef7ae6 (fix/cards110-111-summary-opening head); develop worktree `<scratchpad>/v110dev` at cffdb8fd. Verifier has no prior context and closes nothing.

## Table of contents

- [Findings](#findings)
- [Check 1: the findings the fix round claims closed, re-derived](#check-1-the-findings-the-fix-round-claims-closed-re-derived)
- [Check 2: the standalone check's wiring](#check-2-the-standalone-checks-wiring)
- [Check 6: gates in `<scratchpad>/v110`, without the price line](#check-6-gates-in-scratchpadv110-without-the-price-line)
- [Live runs, branch against develop](#live-runs-branch-against-develop)
- [Verified by my own probes, and only read](#verified-by-my-own-probes-and-only-read)
- [Learnings](#learnings)
- [Verdict](#verdict)

## Findings

### V-110-01: No test pins which candidate a standalone answer belongs to; reading candidate 2's check for every pick stays green
- Severity: minor (the shipped code is correct; the property is unguarded)
- What: `_lead_sentence_choice` reads `check_tasks[picked - 1]`. Mutated to `check_tasks[0]` (a pick of the third or fourth sentence would lead on the SECOND sentence's check), every card 110 test stays green, because the fake Jev in `test_write_answers_sooner.py` gives every check the same answer.
- Reproduction: in `<scratchpad>/v110`, `sed -i '' 's/check_tasks\[picked - 1\]/check_tasks[0]/' src/system_03_search_agent/core/graph.py`, then `pytest tests/system_03_search_agent/core/test_write_answers_sooner.py tests/system_03_search_agent/harness/test_decide.py -q -m "not integration"`: `133 passed in 17.77s`. Restored with `git checkout -- src`.
- The shipped code itself matches correctly. My own probe (`_decide_point` faked, each check keyed to its own sentence, deliberately out of finish order) on 3cef7ae6:
  ```
  third; C3 slow SA, C2 fast NE, C4 fast NE  result=2     elapsed=0.40s pending_tasks_after=0
  third; C3 slow NE, C2 fast SA, C4 fast SA  result=None  elapsed=0.40s pending_tasks_after=0
  fourth; C4 SA at 0.9, pick at 0.5          result=3     elapsed=0.90s pending_tasks_after=0
  ```
- Why a person would care: a later edit that pairs a check with the wrong sentence would let "One is ..." or "Changes in this gene ..." open the answer again (the A-110-01 and A-110-04 shapes), and no test would say so.
- NOT FIXED

### Check 4 (holds): card 111's narrowed rule, 31 hand cases on both trees

End to end through `write_node` (fake writer, five Disease rows: [1] and [2] "Marfan syndrome", [3] and [4] "Loeys-Dietz syndrome", [5] "Ehlers-Danlos syndrome"; writer text is "NCBIGene:672 is associated with Ehlers-Danlos syndrome [5]. " plus the case). "Kept" means the sentence prints in the summary. Probe file: `<scratchpad>/vprobes/test_v111_probe.py`, run in each worktree.

| Case | Writer sentence | Depth, listing | Branch | Develop |
|---|---|---|---|---|
| c01 | Marfan syndrome [1] and Marfan syndrome [2]. | researcher, yes | left out | kept |
| c02 | Marfan syndrome [1], Marfan syndrome [2]. | researcher, yes | left out | kept |
| c03 | Loeys-Dietz syndrome [3] and Loeys-Dietz syndrome [4]. | researcher, yes | left out | kept |
| c04 | ... Marfan syndrome [2]! | researcher, yes | left out | kept |
| c05 | Loeys-Dietz ... [4]? | researcher, yes | left out | kept |
| c06 | Marfan syndrome [1] and Loeys-Dietz syndrome [3]. | researcher, yes | kept | kept |
| c07 | three distinct names [1] [3] [5] | researcher, yes | kept | kept |
| c08 | Marfan [1], Marfan [2] and Loeys-Dietz [3] | researcher, yes | kept | kept |
| c09 | Marfan syndrome [1]. | researcher, yes | stripped (both) | stripped (both) |
| c10 | Marfan syndrome [1] and Marfan syndrome [1]. | researcher, yes | stripped | stripped |
| c11 | Marfan syndrome [1][2]. | researcher, yes | stripped | stripped |
| c12 | [1] Marfan syndrome [2]. | researcher, yes | stripped | stripped |
| c13 | ... Marfan syndrome [2], both rare. | researcher, yes | left out (grounding cut it to the echo shape first) | kept as "Marfan syndrome [1] and Marfan syndrome [2]." |
| c14 | Marfan syndrome [1] resembles Marfan syndrome [2]. | researcher, yes | stripped | stripped |
| c15 | MARFAN SYNDROME [1] AND MARFAN SYNDROME [2]. | researcher, yes | stripped | stripped |
| c16 | Marfan syndrome [1] or Marfan syndrome [2]. | researcher, yes | left out | kept |
| c17 | the echo, listing ungroundable | researcher, no | kept | kept |
| c18 | the echo | plain language, yes (names shown as list_item rows) | left out | kept |
| c19 | the echo, listing ungroundable | plain language, no | kept | kept |
| c20 | the echo | clinical brief, yes | left out | kept |
| c21 | Marfan syndrome [1] and Loeys-Dietz syndrome [3]. | plain language, yes | kept | kept |

Unit level, `_label_only_positions` on the branch (develop has no such rule, so every row is kept there):

| Case | Sentence | Listing shows | Branch |
|---|---|---|---|
| u1 | Marfan syndrome [1] and Marfan syndrome [2]. | [1] to [6] | DROPPED |
| u2 | same | [1] only | kept |
| u3 | same | nothing | kept |
| u4 | What Is Marfan Syndrome? [3] and What Is Marfan Syndrome? [4] | all | DROPPED |
| u5 | What Is Marfan Syndrome [3] and What Is Marfan Syndrome [4]? | all | DROPPED |
| u6 | Marfan syndrome [1] and Marfan syndrome [5] ([5] is a description field) | all | kept |
| u7 | FBN1 [6]. (symbol, single) | all | kept |
| u8 | Marfan syndrome [1] and FBN1 [6]. | all | kept |
| u9 | What Is Marfan Syndrome? [3] (single title) | all | kept |
| u10 | the echo | a line "Found 2 records [1][2]." | DROPPED |

Reading: a cited list of distinct names (c06, c07, c08, c21, u8), a single title (c09 stripped by grounding on both trees alike, u7, u9) and a sentence citing a record the listing does not show (c17, c19, u2, u3) are never left out. The "X [a] and X [b]." shape is left out when both are listed (c01 to c05, c16, c18, c20, u1, u4, u5). Nothing in this table is worse than develop. J-111-01, A-111-01, A-111-02 and A-111-04 reproduce as closed. u10 is a note only: the rule trusts any marker in the listing's lines as "shown", which holds while the listing lines are one row per record.

### V-110-02: A second-place features sentence that develop leads is sometimes rejected by the new standalone check, so the branch opens on the count line instead
- Severity: major (unsure on rate; inside this phase's fix-round code, the `write.lead_stands_alone` check)
- What: when the pick is "second" (a pick develop already offered and led on), the branch now also needs a `stands_alone` answer for that sentence. On query 66's real features sentence ("MedGen lists these clinical features: Aortic regurgitation [3], ..."), Jev answers `needs_earlier` some of the time, and the branch then opens on "I found 5 published papers, 1 condition, ..." where develop opens on the features. Live, the check's own confidence on this sentence when it did say stands_alone was 0.32 (b66_1) and 0.24 (b66_5), so it sits near the line.
- Reproduction: develop live run d66_2 (query 66, Plain language) grounded `S1 Marfan syndrome is a multisystem connective tissue disease ... / S2 MedGen lists these clinical features: Aortic regurgitation [3], ... / S3 There is still no radical treatment ...`; develop picked `second 0.95` and opened on S2. Replaying `_lead_sentence_choice` with live Jev on that same saved grounding, 10 times per tree (`<scratchpad>/vprobes/vreplay.py d66_2 10`):
  - develop cffdb8fd: `TALLY d66_2 v110dev: {'S2: MedGen lists these clinical features: Aortic regur': 10}`
  - branch 3cef7ae6: `TALLY d66_2 v110: {'S2: MedGen lists these clinical features: Aortic regur': 9, 'COUNT LINE': 1}`, the losing run: `d66_2 run5 253ms -> COUNT LINE | checks [('MedGen lists these clinical features: Ao', 'needs_earlier'), ...]`
- Why a person would care: this is the exact query the card was written for. Develop's own win (features second, led) can now turn back into the count line on the branch. The rate is being measured below.
- NOT FIXED
- Rate, measured (`<scratchpad>/vprobes/vcheck.py 30`, the standalone check alone, live Jev, 30 times per sentence, branch):
  ```
  CHECK d66_2:1  n=30 {'stands_alone': 29, 'needs_earlier': 1} | MedGen lists these clinical features: Aortic regurgitation [3], ...
  CHECK b66_5:1  n=30 {'stands_alone': 29, 'needs_earlier': 1} | MedGen lists these clinical features: Aortic regurgitation [3], ...
  CHECK d66_1:2  n=30 {'stands_alone': 30} | MedGen lists these clinical features: Aortic regurgitation [3], ...
  CHECK d66_4:0  n=30 {'stands_alone': 30} | MedGen lists these clinical features: Aortic regurgitation [4], ...
  CHECK b66_4:0  n=30 {'stands_alone': 30} | Marfan syndrome is associated with aortic regurgitation [3], ...
  ```
  So about 1 in 30 on the features sentence (3 of 70 checks on that sentence shape across the replay and this run). When the features sentence is first no check runs, so this only touches answers where it sits second, third or fourth. Develop leads it every time it is second; the branch about 29 times in 30. Small, but it is a case where the branch is worse than develop for the person asking query 66, which the owner's bar names. Against it, the branch gains every time the features sit third or fourth (next entry).

### V-110-03: A-110-02 is not closed for the person: a paper title in third place still opens the BRCA1 answer, where develop opens on the count line
- Severity: major (inside this phase's code: card 110's third and fourth candidates plus the fix round's standalone check, which says yes to a title)
- What: the fix round closed A-110-02 by making the card 111 drop and the lead candidates agree (a dropped sentence is never offered). With card 111 narrowed, a single paper title is no longer dropped, so it is offered again, and the standalone check passes it because a title names everything it talks about. The adversary's symptom, "asked which diseases BRCA1 is linked to, the bold first line is one paper's title", reproduces unchanged.
- Reproduction: `_lead_sentence_choice` with live Jev, question "Which diseases are associated with BRCA1?", grounded sentences (my own replay, `<scratchpad>/vprobes/case_A110_02.json`): "BRCA1 is a gene that acts as a tumor suppressor [23]." / "Targeting GPX4-mediated ferroptosis protection sensitizes BRCA1-deficient cancer cells to PARP inhibitors [20]." / "Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis [14]." Five runs per tree:
  ```
  A110_02 TALLY bbrca_1 v110: {'S3: Preneoplastic stromal cells promote BRCA1-mediated': 5}
  A110_02 TALLY bbrca_1 v110dev: {'COUNT LINE': 5}
  ```
- Why a person would care: someone asking which diseases BRCA1 is linked to sees, in bold as the first line, one study's title about stromal cells, and the four diseases only after it. On develop the same writer reply opened on "I found 4 conditions related to BRCA1". How often the writer copies a title whole into Plain language prose was not measured live in my 20 runs (it did not happen in them); the adversary showed the grounding pass accepts such sentences whole.
- NOT FIXED

### V-110-04: No test pins that the pick and the check share ONE 1 s bound; giving the check a fresh full second after the pick stays green
- Severity: minor (the shipped code holds the bound; the property is unguarded)
- What: `_lead_sentence_choice` waits for the check only for what is left of `wait_s` after the pick (`left_s = max(wait_s - (time.monotonic() - started), 0.0)`). Mutated to `left_s = wait_s`, a pick that arrives at 0.95 s could wait almost another full second for its check, past F-8.7-A07's ~1 s bound, and every test stays green: `test_a_late_check_leaves_the_count_line_leading_inside_the_bound` uses an instant pick, so it cannot tell a shared bound from a fresh one.
- Reproduction: in `<scratchpad>/v110`, the mutation above, then `pytest tests/system_03_search_agent/core/test_write_answers_sooner.py tests/system_03_search_agent/core/test_summary_label_only_sentence.py tests/system_03_search_agent/harness/test_decide.py -q -m "not integration"`: `158 passed in 15.90s`. My timing probe (`<scratchpad>/vprobes/p_lead.py`, fake `_decide_point`, pick at 0.5 s, the fourth sentence's check at 1.05 s): mutated `result=3 elapsed=1.05s`; shipped code `result=None elapsed=1.00s pending_tasks_after=0 ... cancelled=[3]`. Restored from a copy, `git status` shows only my scratch price line.
- Why a person would care: the answer's opening line would wait up to about 2 s instead of 1 s on a slow classifier, and no test would catch the edit.
- NOT FIXED

### Check 5 (break it), card 111 mutation of my own: red, holds
- Mutation: `_is_label_only_sentence` asks that ANY cited marker be in the listing instead of ALL (`if not all(...)` to `if not any(...)`).
- Output: `FAILED tests/system_03_search_agent/core/test_summary_label_only_sentence.py::test_label_only_is_decided_from_structure[Marfan syndrome [1] and Marfan syndrome [2].-listed10-False]`, `1 failed, 110 passed in 6.29s`. Restored.
- Card 110 mutations of my own: both survived (V-110-01, V-110-04).

### V-110-05: "Otherwise the answer opens as develop's would" is not true for a pick of the second sentence
- Severity: minor (a wrong statement in the DECISIONS row and the commit message; the behaviour itself is V-110-02)
- What: the 2026-10-15 DECISIONS row says "A pick after the first leads only on a yes; otherwise the answer opens as develop's would", and commit 3cef7ae6 says "otherwise the answer opens on its count line as develop's does". For a pick of "second", develop leads that sentence with no check. On the branch a `needs_earlier`, a late check or a failed check opens on the count line instead. So on every check failure path for a second pick, the branch opens differently from develop.
- Reproduction: my fake-seam probe on 3cef7ae6 (`<scratchpad>/vprobes/p_lead.py`): `second; C2 SA late(1.5), others SA fast  result=None elapsed=1.00s` and `second; check no usable pick  result=None elapsed=0.05s`. Develop's `_lead_sentence_choice` asks no check, so the same pick returns the second sentence. Live: V-110-02's replay, develop 10 of 10 on the features sentence, branch 9 of 10.
- Why a person would care: the owner reads the row to judge "nothing worse than develop"; the row says the failure paths match develop, and for second picks they do not.
- NOT FIXED

### V-110-06: One branch live run of query 66 printed no answer at all (unsure, not attributed to this change)
- Severity: unsure
- What: live run b66_2 on the branch ended with no summary, cost $0.0000945, 15.1 s, and never reached the lead decision (`lead_ret: not called`, no lead records). Only the guard tier seems to have run (a full run's guard call cost $0.000148 in b66_5). I did not capture the event stream for that run (capture was added afterwards), so the cause is unknown; the next branch run with capture (b66_5) answered normally.
- Reproduction: `<scratchpad>/vprobes/live.jsonl`, the row tagged b66_2: `{'tag': 'b66_2', 'tree': 'branch', ..., 'wall_s': 15.1, 'cost': 9.448600000000002e-05, 'lead_ms': None, 'lead_ret': 'not called', 'decisions': [], 'done_lead': [], 'summary_claims': []}`.
- Why a person would care: a person would see no answer. The branch changes only the Write step and the Synth prompt's features directive, and neither ran here, so I do not attribute it to this branch; filed so it is not lost.
- NOT FIXED

## Check 1: the findings the fix round claims closed, re-derived

| Finding | My verdict | My evidence |
|---|---|---|
| J-111-01 | closed | c17 and c19 (no listing) keep the echo on both trees; u2 and u3 keep it when the listing lacks a record |
| J-111-03 | closed for the second list | `graph.py` imports `answer_layout.LABEL_FIELDS`; no `_LABEL_FIELDS_FOR_ECHO` left (grep empty). The borrowed private `_clean_claim` glue rule stays: c16 "Marfan syndrome [1] or Marfan syndrome [2]." is left out on the branch, kept on develop (harmless, says nothing) |
| A-111-01 | closed | c06, c07, c08, c21, u8 kept on the branch |
| A-111-02 | closed for the drop | u9 and u7 kept; c09 is stripped by the grounding pass on both trees alike. But the same title can now LEAD: see V-110-03 |
| A-111-04 | closed | c05, u4, u5 left out alike whether the marker sits before or after "?" |
| A-110-01 | closed | replay of "The gene, whose symbol is BRCA1 ... / Its protein ... / Changes in this gene ..." with live Jev: branch `{'COUNT LINE': 5}`, develop `{'COUNT LINE': 5}`; no live branch run opened on a "this gene" sentence (checks said `needs_earlier` 0.94 and 0.96 on such sentences in bbrca_4 and bbrca_5) |
| A-110-02 | NOT closed for the person | V-110-03: branch `{'S3: Preneoplastic stromal cells promote BRCA1-mediated': 5}`, develop `{'COUNT LINE': 5}` |
| A-110-04 | closed | "One is ..." third: branch `{'COUNT LINE': 5}`; "These include ..." fourth: branch `{'COUNT LINE': 5}`; develop the same |
| A-110-05 | closed | a 926-character candidate whose answer is at its end: `len=968 ... ectopia in state: True` |
| J-110-01 | closed | 20000 random question and candidate sizes: `bound or label broken: 0`; worst case `len=4000 parts=5 [1010, 745, 745, 746, 746]` |
| J-110-02 | closed | grep for "one or two", "3864" and `_LEAD_CANDIDATE_MAX_CHARS` returns nothing in the two files |

## Check 2: the standalone check's wiring

Fake `_decide_point` (each check keyed to its own sentence), shipped code 3cef7ae6:

```
first, checks slow 5s                      result=0     elapsed=0.05s pending_tasks_after=0 started=['pick', 1, 2, 3] cancelled=[1, 2, 3]
third; C3 slow SA, C2 fast NE, C4 fast NE  result=2     elapsed=0.40s pending_tasks_after=0
third; C3 slow NE, C2 fast SA, C4 fast SA  result=None  elapsed=0.40s pending_tasks_after=0
second; C2 SA late(1.5), others SA fast    result=None  elapsed=1.00s pending_tasks_after=0 cancelled=[1]
fourth; C4 SA at 0.9, pick at 0.5          result=3     elapsed=0.90s pending_tasks_after=0
fourth; C4 SA at 1.05, pick at 0.5         result=None  elapsed=1.00s pending_tasks_after=0 cancelled=[3]
pick late 1.5                              result=None  elapsed=1.00s pending_tasks_after=0 cancelled=['pick']
pick none record                           result=None  elapsed=0.05s
second; check no usable pick               result=None  elapsed=0.05s
neither                                    result=None  elapsed=0.05s
budget 1.6 -> wait 1.0; check 1.05         result=None  elapsed=1.00s cancelled=[1]
budget 1.4 -> not asked                    result=None  elapsed=0.00s started=[]
```

- Holds: a "first" pick never waits; out-of-order checks are matched to their own candidate; nothing passes 1.0 s; every started task is done or cancelled on return.
- Live, pick latency alone against pick with the checks running beside it (`<scratchpad>/vprobes/vlat.py 15`): two candidates median 223 ms against 212 ms, four candidates 234 ms against 242 ms, none over 1000 ms in 60 picks. The checks do not slow the pick.
- The criteria and instructions name no test question word and no pointer word list (scan of the texts for Marfan, BRCA1, disease, gene, MedGen, These, One is, Another, They: none present). The reworded criterion's "such as a list it goes on to state" describes a sentence shape, not a question; I judge it generic.
- Not holding: the failure paths for a SECOND pick do not open as develop's would (V-110-05, V-110-02); the matching and the shared bound are unpinned by tests (V-110-01, V-110-04).

## Check 6: gates in `<scratchpad>/v110`, without the price line

- `ruff check`: `All checks passed!`
- `isort --check-only`, touched files: all pass except `core/graph.py`; develop cffdb8fd's `core/graph.py` fails with the same `contracts.events ... EventResolvedEntity` lines.
- `pytest tests/system_03_search_agent/harness tests/system_03_search_agent/core tests/system_03_search_agent/synthesis -m "not integration" -q`: `2 failed, 2858 passed, 66 skipped, 1 deselected, 1 xfailed, 2 warnings in 105.36s`. The two: `test_opus_writer.py::test_the_rollback_writer_glm_5_2_is_still_priced_by_the_installed_map` and `::test_the_old_writer_is_never_priced_below_the_static_estimate`, the known glm price failures.

## Live runs, branch against develop

Setup as briefed (`run_streaming`, reads_placement=True, CLASSIFIER_PROVIDER=jev, PER_QUERY_COST_CAP_USD=0.25, SYNTH_MODEL=z-ai/glm-5.2, guard and plan deepseek/deepseek-v4-flash, Plain language), the glm price line in the scratch worktrees only, interaction capture and session memory stubbed, user database and Redis unset. Branch b66_0 was a setup run, kept and counted. "Checks" maps each standalone answer to its own sentence (my spy on `_decide_point`).

| Run | Tree | Opens on | Pick, then checks (confidence) | Lead ms | Cost USD |
|---|---|---|---|---|---|
| b66_0 | branch | features sentence | second 0.95; check on features stands_alone 0.32 | 232 | 0.0190 |
| b66_1 | branch | features sentence | first 0.96 | 205 | 0.0189 |
| b66_2 | branch | no answer (V-110-06) | not reached | none | 0.0001 |
| b66_3 | branch | features sentence | first 0.98 | 209 | 0.0193 |
| b66_4 | branch | "Marfan syndrome is associated with aortic regurgitation [3], ..." | first 1.0 | 242 | 0.0189 |
| b66_5 | branch | features sentence | second 0.95; check on features stands_alone 0.24 | 322 | 0.0195 |
| d66_0 | develop | features sentence | first 0.98 | 283 | 0.0199 |
| d66_1 | develop | count line (features third) | neither 0.97 | 381 | 0.0188 |
| d66_2 | develop | features sentence | second 0.95 | 292 | 0.0191 |
| d66_3 | develop | features sentence | first 0.98 | 202 | 0.0195 |
| d66_4 | develop | features sentence | first 0.98 | 251 | 0.0192 |
| bbrca_1 | branch | count line (no answering sentence) | neither 0.98 | 209 | 0.0201 |
| bbrca_2 | branch | count line (no answering sentence) | neither 0.99; S3 check needs_earlier 0.64 | 247 | 0.0211 |
| bbrca_3 | branch | count line (no answering sentence) | neither 0.98 | 271 | 0.0215 |
| bbrca_4 | branch | count line (pick late, answer was S1) | pick did not arrive in 1 s; S2 "Mutations in this gene ..." check needs_earlier 0.96 | 1002 | 0.0201 |
| bbrca_5 | branch | "BRCA1 is associated with four diseases: ..." | first 1.0; checks needs_earlier 0.94, 0.72 | 384 | 0.0195 |
| dbrca_1 | develop | "BRCA1 is associated with four diseases: ..." | first 1.0 | 206 | 0.0199 |
| dbrca_2 | develop | count line (pick late) | pick did not arrive in 1 s | 1002 | 0.0207 |
| dbrca_3 | develop | count line (no answering sentence) | neither 0.98 | 176 | 0.0197 |
| dbrca_4 | develop | "BRCA1 is associated with four diseases: ..." | first 1.0 | 188 | 0.0204 |
| dbrca_5 | develop | "BRCA1 is associated with familial cancer of breast [1], ..." | first 1.0 | 194 | 0.0206 |

Totals: query 66, branch 5 of 6 on a features sentence (one run gave no answer), develop 4 of 5. BRCA1, branch 1 of 5 on the answer sentence, develop 3 of 5. Live spend $0.3958 for 21 runs, plus about 600 replayed Jev decisions at about $0.00002 each (about $0.012); total about $0.41 of the $0.60.

The BRCA1 gap is the writer and one late pick, not the code: replaying every saved grounding through both trees' `_lead_sentence_choice`, 3 times each, the two trees agree on all ten (dbrca_1, dbrca_4, dbrca_5, bbrca_4, bbrca_5 open on S1 on both; bbrca_1 to bbrca_3 open on the count line on both; b66_4 and d66_4 on S1 on both). Develop's d66_1 grounding (features third) opens on the features on the branch 5 of 5 and on the count line on develop 5 of 5: card 110's gain is real. Develop's d66_2 grounding (features second) is V-110-02.

Other replays (live Jev, 5 each, BRCA1 question): a cited list behind "They include ..." in second place: develop leads it 5 of 5, branch opens on the count line 5 of 5 (an intended change, the A-110-04 shape; I judge it not worse). A plain answer sentence second: both lead it 5 of 5. A plain answer sentence third ("Diseases linked to BRCA1 include ..."): branch 5 of 5, develop count line 5 of 5.

## Verified by my own probes, and only read

- Probed: every row of check 1; the wiring in check 2 with a fake seam and with live Jev latency; 31 card 111 cases end to end and at unit level on both trees; four mutations of my own; the gates; 21 live runs and the cross replays.
- Only read: the features directive change in `synthesis/findings.py` (no probe isolates its effect; every live features sentence was one list); the guard-tier fallback for a failing check (no probe forced Jev to fail live); the DECISIONS row's reasoning.

## Learnings

- None over five minutes. Small: a hook blocks file deletion in shell commands, including report text that names the delete command, so probe outputs went to fresh file names; zsh does not split an unquoted list of paths, so the isort loop was rerun with `while read`.

## Verdict

HOLD on V-110-03, with V-110-02 beside it. Both sit inside this phase's fix-round code (the standalone check and the four-candidate pick): V-110-03 shows A-110-02, claimed closed, still opening a BRCA1 answer on a paper title where develop opens on the count line (5 of 5 against 5 of 5); V-110-02 shows develop's own query 66 win (features second) lost about one time in thirty. Everything else re-derived holds or is minor (V-110-01, V-110-04, V-110-05 minor; V-110-06 unsure and not attributed). This meets the review loop's stop condition: a finding inside a fix made during this phase, for the product owner.
