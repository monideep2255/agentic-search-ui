# Card 115 fresh verifier

Branch fix/card115-readonly-reply-first at 3709a2ab, compared against origin/develop at bce08af9. Grid re-derived from the verifier's own stubbed script, not the reviewers'. Findings are appended as each is established.

## Findings

### V-115-01: own grid, 12,312 cases per tree under load: 534 intended moves plus 24 moves on timing-race cases, re-run in isolation (see V-115-02)
- Severity: unsure (evidence for check 1, provisional until V-115-02)
- What: the verifier's own probe (`<scratchpad>/verifier115/grid.py`, not the reviewers' scripts): the real `guardrail_node` of each tree in its own process; stubs at `litellm.acompletion` (guard classifier), `graph.decide` (topic check), `graph.call_jev`, `session_scope` and the two daily caps; sockets refused; guardrail budget stubbed to 4 s on both trees alike.
  - Axes: Jev off, or on with its injection pick not_injection, injection, injection after 0.5 s, raising, hung (6); guard classifier ok, off topic, injection, ok after 0.8 s, unusable twice, raising (6); topic check off_topic at 0, 0.3, 1.2 or 2.0 s, hung, on_topic, no usable pick, guard-only off_topic, seam raising (9); first message or follow-up after a BRCA1 turn (2); 19 texts: 3 write-seeking with a referring word, 1 without, 1 the allowlist misses, 2 injection plus write (one pre-filtered), 1 injection only, 3 off topic (two of them the "cell phone" texts A-115-01 names), 3 ordinary (one the methylation text the screen misreads as a write), 1 compute, 2 medical (pre-filtered) and 1 third-party medical (forbidden screen). 6 x 6 x 9 x 2 x 19 = 12,312.
- Reproduction (pasted from `cmp.py`):
  ```
  cases per tree 12312
  develop mix {'refuse:write_seeking': 1681, 'refuse:off_topic': 2298, 'refuse:injection': 2641, 'admit': 552, 'refuse:compute_request': 194, 'refuse:medical_advice': 1490, 'step_error': 3456}
  transitions {('refuse:off_topic', 'refuse:write_seeking'): 534, ('refuse:off_topic', 'admit'): 4, ('admit', 'refuse:off_topic'): 2, ('refuse:compute_request', 'refuse:off_topic'): 2, ('refuse:medical_advice', 'refuse:off_topic'): 2, ('refuse:off_topic', 'refuse:injection'): 2, ('refuse:off_topic', 'refuse:compute_request'): 1, ('refuse:off_topic', 'refuse:medical_advice'): 1, ('admit', 'refuse:injection'): 8, ('refuse:injection', 'refuse:off_topic'): 2}
  same verdict, different reason 0
  call count diffs {}
  ```
  The 534 intended moves are 7 texts x 76 follow-up cases plus 2: the 4 allowlisted write requests with a referring word, and the 3 misread texts ("Change the status of my cell phone order, it is late", "Update that cell phone record in the database", "Does it change the methylation status of the gene promoter?"). The other 24 all sit on a deadline race (topic check at 2.0 s against the 1.5 s bound, or Jev's injection pick at 0.5 s against a 4 s budget) and every one ran 3 to 5 s against a stubbed 0.2 s: twelve processes ran at once and the event loops were saturated. Not yet evidence either way; V-115-02 re-runs them alone.
- NOT FIXED

### V-115-02 (check 3): the cancelled topic check's cost is missing from the recorded row on more refusals than develop; nobody sees it, and the daily cap under-reads by cents per thousand refusals
- Severity: minor (inside this phase's fix; no person-facing effect; not a HOLD by the owner's bar, which is about people and verdicts)
- What: the daily system cost cap sums `Interaction.cost_usd`, and when a run emits its own `done` event, `core/run.py` `_terminal_events_for_capture` records that `done` figure as is; the harness's later cancellation charge (the guard tier's output ceiling) never reaches the row. Develop already loses it for a write-seeking follow-up whose topic check runs past the 1.5 s bound. The branch loses it for every write-seeking follow-up whose topic check is still running when the guard classifier answers. The web app parses `total_cost_usd` but shows it nowhere (`frontend/src/lib/events.ts`, `useRunView.ts`: parse only), so no person sees a difference.
- Reproduction: own probe `<scratchpad>/verifier115/cost.py`, real `decide()` with Jev off, `litellm.acompletion` stubbed (guard classifier ok at 0.2 s, the topic check's generic prompt answering after the delay), BRCA1 turn in memory, harness read 1 s after the node returned. Pasted:
  ```
  v115dev  ws_ref_remove pick=off_topic delay=0.6  off_topic     el=0.604 done.total_cost_usd=0.000040 harness_after=0.000040 decisions=['guardrail.relevancy']
  v115dev  ws_ref_remove pick=off_topic delay=2.5  write_seeking el=1.501 done.total_cost_usd=0.000020 harness_after=0.000276 decisions=[]
  v115dev  ws_ref_remove pick=on_topic  delay=1.2  write_seeking el=1.202 done.total_cost_usd=0.000040 harness_after=0.000040 decisions=['guardrail.relevancy']
  v115     ws_ref_remove pick=off_topic delay=0.05 write_seeking el=0.212 done.total_cost_usd=0.000040 harness_after=0.000040 decisions=['guardrail.relevancy']
  v115     ws_ref_remove pick=off_topic delay=0.6  write_seeking el=0.203 done.total_cost_usd=0.000020 harness_after=0.000276 decisions=[]
  v115     ws_ref_remove pick=on_topic  delay=1.2  write_seeking el=0.219 done.total_cost_usd=0.000020 harness_after=0.000276 decisions=[]
  v115     ord_ref       pick=off_topic delay=0.6  off_topic     el=0.603 done.total_cost_usd=0.000040 harness_after=0.000040 decisions=['guardrail.relevancy']
  ```
  The ordinary follow-up ("What variants cause it?") is identical on both trees in all 8 arms; only write-seeking follow-ups move.
- Judgement, from the person's chair: the person sees a faster, same-or-better refusal and no cost figure. The daily cap reads $0.000020 where develop read $0.000040 on these refusals: the row drops the topic check's own call. What the provider actually bills for a request cancelled mid-flight lies between nothing and the $0.000276 ceiling estimate; at that ceiling the under-read is about $0.00026 per refusal, about 26 cents per thousand write-seeking follow-ups. Develop already has the same gap in kind (the 2.5 s arm above), and the 1,000,000 test cap aside, a real cap of dollars is not moved by it. The trace also loses the `guardrail.relevancy` record on these rows, which only matters to someone tuning card 35's topic check. Not worse for a person; slightly worse for spend accounting, as J-115-01 and A-115-03 already say.
- NOT FIXED

### V-115-03 (check 2): A-115-01 judged from the person's chair: a little less apt in one arm, not worse overall, and it makes the reply the same one the same person already gets on develop as a first message
- Severity: minor (inside this phase's fix; refusal to refusal, no admit involved)
- What: for "Change the status of my cell phone order, it is late" and "Update that cell phone record in the database", develop's reply depends on timing and on the topic check: the off-topic line only when the topic check picks off_topic inside 1.5 s on a follow-up, and the read-only line everywhere else, including every first message (no topic check is asked when the allowlist clears it). The branch gives the read-only line in every arm.
- Reproduction: own grid (V-115-01), guard classifier ok or slow, all six Jev modes, all nine topic modes. Pasted tallies:
  ```
  develop off_cell_phone  first  {'refuse:write_seeking': 108}
  develop off_cell_phone  follow {'refuse:off_topic': 52, 'refuse:write_seeking': 56}
  branch  off_cell_phone  first  {'refuse:write_seeking': 108}
  branch  off_cell_phone  follow {'refuse:write_seeking': 108}
  ```
  Identical for "Update that cell phone record in the database" and for the real biomedical question the screen misreads, "Does it change the methylation status of the gene promoter?". The two replies:
  ```
  off_topic:     I answer questions about biomedical evidence from NCBI data: genes, variants, diseases, publications, and sequencing records.
  write_seeking: I have read-only access to the knowledge graph and can't create, change, or delete anything in it. I can show you what it already contains, with citations.
  ```
- Judgement: for the person with a late phone order, develop's off-topic line is the more apt of two refusals in the one arm where it appears: it says what the product is for. The read-only line is puzzling but not misleading about anything they can do, and it is what develop already tells them if they type the same words as a first question, or when the topic check is slow or says on topic. Neither tree helps them, and neither admits. For the person asking about methylation status (a real biomedical question, A-115-05's false refusal), the off-topic line "I answer questions about biomedical evidence" is arguably the more confusing of the two, so there the branch is no worse. Net: not worse for a person in any way that matters; consistent where develop varied by timing. Not a HOLD.
- NOT FIXED

### V-115-04 (check 1): the 24 non-intended moves of V-115-01 were load races; alone, all 24 match develop in 3 of 3 runs per tree; zero moves to or from admit
- Severity: unsure (evidence for check 1; holds). This is the re-run V-115-01 calls "V-115-02"; the number moved because the cost finding was written first.
- What: every case in the race's neighbourhood (Jev off, not_injection, injection, injection after 0.5 s; classifier ok or off topic; topic off_topic at 0, 0.3, 1.2 or 2.0 s; first and follow-up; the 7 texts involved) re-run one at a time (`CONC=1`), three times per tree: 126 cases x 3 x 2 trees. None of the 24 texts is a write request the screen catches, so the early return never fires for them; the only code they share with the change is one extra `forbidden.screen` call.
- Reproduction (pasted, first lines and summary):
  ```
  cases 126 x3 runs each tree; differing or unstable: 0
  race cases covered 24 of 24
  ('not', 'ok', 'off20', 'follow', 'inj_only') dev admit [1.5028, 1.5017, 1.5031] br admit [1.5028, 1.5054, 1.5029]
  ('not', 'ok', 'off20', 'follow', 'ord_ref') dev admit [1.5019, 1.5028, 1.5016] br admit [1.5031, 1.503, 1.5028]
  ('off', 'ok', 'off20', 'follow', 'off_ref') dev refuse:off_topic [2.0037, 2.0028, 2.0028] br refuse:off_topic [2.0036, 2.0031, 2.0028]
  ('inj_slow', 'ok', 'off03', 'first', 'ord_first') dev refuse:injection [0.5036, 0.5039, 0.5032] br refuse:injection [0.5038, 0.5032, 0.5042]
  ('inj', 'ok', 'off20', 'follow', 'compute_ref') dev refuse:compute_request [1.5028, 1.5018, 1.5016] br refuse:compute_request [1.5019, 1.5028, 1.5028]
  ```
- Result for check 1, combining V-115-01: across 12,312 cases per tree the one verdict difference is refuse:off_topic on develop to refuse:write_seeking on the branch, 534 cases, all follow-ups after a BRCA1 turn whose text the forbidden screen calls write_seeking and the allowlist clears, under a topic check that picks off_topic (at any delay inside the bound, or the guard-only pick). Moves to or from admit: 0. Same verdict with a different reason: 0. Model calls, Jev calls and topic-check calls made: identical on every case. Every injection refusal on develop (2,641) stays an injection refusal, every step error stays a step error, and every first message is identical. No HOLD on verdicts.
- One caveat on the grid's realism, from reading only: the guard classifier never sees the conversation, and the stubs set each judge independently, so arms like "classifier says off topic, topic check says on topic" may be rarer live than here. That only widens coverage.
- NOT FIXED

### V-115-05 (check 4): timing: no path slower than develop beyond about a millisecond; write-seeking follow-ups up to 1.5 s faster
- Severity: unsure (evidence for check 4; holds)
- What: own grid, run one case at a time per process (`CONC=1`, no post-run sleep), follow-ups after a BRCA1 turn only, since first messages never reach the new code (`follow_up_only` needs a topic check on an allowlisted text, which only a memory-bound follow-up starts): Jev off, not_injection, injection (3) x classifier ok, off topic, ok after 0.8 s (3) x 9 topic modes x 19 texts = 1,539 cases per tree, guardrail budget stubbed to 4 s on both.
- Reproduction (pasted):
  ```
  follow-up cases per tree 1539 verdict diffs {('refuse:off_topic', 'refuse:write_seeking'): 252}
  branch slower by >0.05 s: 1
     (0.0577, ('inj', 'slow_ok', 'nopick', 'follow', 'medical_third'), 0.8037, 0.8614)
  branch faster by >0.05 s: 232 texts Counter({'ws_ref_remove': 34, 'ws_ref_write': 33, 'ws_ref_update': 33, 'ws_inj_noprefilter': 33, 'off_cell_phone': 33, 'off_cell_record': 33, 'ord_methyl': 33})
  largest saving (-1.5177, 'ws_inj_noprefilter', 1.5189, 0.0012)
  slowest case each tree {'dev': (4.0134, ('not', 'ok', 'hang', 'follow', 'off_noref')), 'br': (4.0084, ('off', 'off', 'hang', 'follow', 'ws_ref_allowmiss'))}
  ```
  The one slower case re-run alone 5 times per tree: develop 0.8079, 0.8036, 0.8043, 0.8048, 0.8026 s; branch 0.8057, 0.8036, 0.8042, 0.8039, 0.8048 s, both refuse:medical_advice. Noise.
- Added work: on a follow-up the screen does not call write_seeking, the branch runs `forbidden.screen` once more than develop (or once where develop refused off topic first and never ran it). Own probe `screenfuzz.py`, 3,007 texts of up to 2,000 characters (the `Query.text` limit), word-salad of write verbs, store nouns and verdict words plus repetition and zero-width forms: median 0.128 ms, worst 1.112 ms. That is the only way the branch can be slower than develop, and it is about a thousandth of a second.
- Not re-measured by me: Jev's injection pick hanging (A-115-06): the early return sits after that await, so both trees wait the same; read, not probed.
- NOT FIXED

### V-115-06 (check 5): gates green on the branch tree at 3709a2ab; the branch merges cleanly into current develop
- Severity: unsure (evidence; holds)
- Reproduction, branch tree at 3709a2ab (pasted):
  - `ruff check` (gate 3, no path): `All checks passed!`, exit 0.
  - `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 2's script line): `Skipped 2 files`, exit 0.
  - `pytest tests/system_03_search_agent/guardrail tests/system_03_search_agent/core -m "not integration" -q`: `1951 passed, 56 skipped, 1 deselected, 2 warnings in 173.77s`, run alone, imports from the branch tree's own `src` (warning paths name it).
  - `git merge-tree --write-tree origin/develop HEAD`: clean. Develop moved from 7626fe85 to bce08af9 since the reviews, touching only `tests/tracker/test_check_doc_sync.py`. The branch's 3709a2ab adds only the judge and adversary reports over the reviewed 766967b6 (`git diff --stat 766967b6 HEAD`: 2 report files), so the reviewed code is the shipped code.
  - No local absolute path in the branch's added lines or in this file.
- NOT FIXED (nothing to fix)

## Verdict: PASS

- Check 1, verdicts: PASS. Own grid, 12,312 cases per tree (V-115-01), with the 24 load-race cases re-run alone 3 times per tree (V-115-04): the one difference is refuse:off_topic to refuse:write_seeking on 534 follow-ups; zero moves to or from admit; no injection refusal lost; calls made identical.
- Check 2, A-115-01: not worse for a person in any way that matters (V-115-03). The off-topic line was a little more apt for the phone-order person in one timing-dependent arm; the branch gives the same read-only line develop gives them as a first message.
- Check 3, J-115-01 / A-115-03: no person sees it; the daily cap's recorded row reads $0.000020 instead of $0.000040 on these refusals, an under-read bounded by the ceiling estimate of about $0.00026 each (V-115-02). Same kind of gap develop already has past 1.5 s.
- Check 4, timing: no path slower beyond about 1 ms of extra screening; write-seeking follow-ups up to 1.5 s faster (V-115-05).
- Check 5, gates: green (V-115-06).
- Inside this phase's fix: V-115-02 and V-115-03 are minor and sit inside the card 115 change; neither is a regression by the owner's bar, so neither is a HOLD.
- Verified with my own probes: every verdict, timing, cost, call-count and screen-timing number above; the gates; the clean merge; the doc-only delta since review. Read only: that the UI shows no cost figure (grep of `frontend/src`); that the daily cap reads `Interaction.cost_usd` from the `done` figure (`core/run.py`, `cost_control.py`); that a hung Jev injection pick delays both trees equally (the early return sits after its await); and that the grid's independent stubbing may over-represent arms rare in live traffic. No live calls were made.
