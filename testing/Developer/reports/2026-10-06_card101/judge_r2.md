# Card 101 round 2 judge report

Judge, fresh context, 2026-10-06. Branch `fix/card101-check-every-rewording` at a37fe52d, reviewed against origin/develop 3d6947ff. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [Verdict](#verdict)
- [Checklist](#checklist)
- [Probes I ran](#probes-i-ran)
- [What I did not cover](#what-i-did-not-cover)

## Findings

### J2-101-01: a sentence that wraps a record title in the question's words still reaches the screen with no check
- Blocking: no (unsure; pre-existing, outside the owner's option A, but it falsifies the build's user-words claim)
- Severity: major
- Where: `src/system_03_search_agent/synthesis/grounding.py:1341-1354` (the strict path, `ground_claim`'s `b in a` direction at `:140` plus the question licence in `supporting_text` at `:1331-1335`)
- In the user's words: asking "how is it usually treated in babies?" can still produce "Acute bronchiolitis is usually treated in babies [n]", cited to the paper's title, shown without the sentence check ever reading it. The words "usually treated in babies" come from the question, not the paper.
- Evidence, my probe (`scratchpad/j2/probe_equiv.py`, offline, branch code): finding ref 13, field `title`, value "Acute bronchiolitis.", question "What causes bronchiolitis in babies, and how is it usually treated with drugs?", narrative `Acute bronchiolitis is usually treated in babies [13].` Branch first pass: shown=True, candidates=0. Develop: shown=True, candidates=0. Unchanged by this card.
- Why it matters: `build_r2.md`, "The change in the user's words", says "No sentence the app writes in its own words reaches the screen unless the sentence check has read it against its paper." That sentence is false for this shape; the owner should not be told it. The diagnosis named this path P2 and option E, and the build lists it under "Not covered", so the defect is in the claim, not in the scope.
- Suggested fix: reword the user-facing claim in `build_r2.md` (and the PR body) to "a sentence that rewords a record sentence"; open option E as its own card with a measurement first, as the diagnosis recommends.
- NOT FIXED

### J2-101-02: three comments now describe a code approval path that no longer exists
- Blocking: no
- Severity: minor
- Where:
  - `src/system_03_search_agent/core/graph.py:9670-9674`: "Below the floor it is skipped, which approves nothing: the answer is what code alone accepts, exactly as before the check existed." False since this change: before the check existed, code's word check showed a reworded sentence; below the floor now, no reworded sentence is shown.
  - `src/system_03_search_agent/core/graph.py:9695-9697`: candidates are those that "failed only the word check". Now every reworded sentence that passes the exact checks is a candidate, whatever the word check says.
  - `src/system_03_search_agent/synthesis/grounding.py:541-553`: the design block lists check 2 (every content word in the quote, the question or `_SYNTHESIS_VOCABULARY`) as one of the checks a reworded sentence passes. Nothing in the grounding pass runs it any more; it is dead in production (no caller of `synthesis_is_supported_by` or `synthesis_is_supported` outside `grounding.py`, grep over `src`).
- In the user's words: no effect on what a person sees. The next engineer reading the floor comment would believe a slow answer still shows code-approved rewordings, and might "restore" that behaviour as a fix.
- Evidence, my probe (`scratchpad/j2/probe_graph.py`, guard mode, offline): hb4's narrative through `_ground_with_sentence_check` at `budget_s=3.999`: 0 calls, "babies" not shown, narrative is the copied sentence only. The same sentence on develop's `run_grounding_pass` first pass: shown with 0 candidates (`probe_equiv.py`, "dev shown=True cand=0"). So the floor's outcome is not "exactly as before the check existed".
- Suggested fix: reword the three comments (the builder already named the two in `graph.py` in `build_r2.md`); mark check 2 in the design block as retired from acceptance by card 101.
- NOT FIXED

### J2-101-03: Researcher-length answers may now push checked sentences past the check's caps, unmeasured
- Blocking: no
- Severity: unsure
- Where: `src/system_03_search_agent/synthesis/sentence_check.py:112` (`MAX_CANDIDATES = 30`), `:413` (`MAX_PAIR_CALLS = 4`), and `build_jev_state`; fed by the larger candidate list from `grounding.py:1395-1414`
- In the user's words: on a long answer, a faithful sentence that was checked and shown yesterday could be dropped today, because the sentences code used to approve now take places in the check ahead of it. Nothing unchecked is shown; the cost is lost sentences.
- Evidence: the cap rule is fail-closed by design (sentences past it are "simply not approved"). The build measured 0 sentences pushed past the pair-call cap on 51 recorded answers, but states "Researcher depth: no live run". In my synthetic offline corpus (293 narratives, `probe_equiv.py`), the branch added 578 candidates that develop never sent, about 2 a narrative, so the list does grow. I did not measure a Researcher answer.
- Suggested fix: none to the code now; one offline replay of recorded Researcher traces through `build_pair_calls` and the item cap, counting sentences not asked, before release.
- NOT FIXED

### J2-101-04: the round 2 adversary's uncommitted scripts fail gate 03; committing them as they are would turn CI red
- Blocking: no (not on the branch; a warning for whoever commits the round's evidence)
- Severity: minor
- Where: untracked `testing/Developer/reports/2026-10-06_card101/raw/adversary_r2/budget_scan.py:4`, `pair_calls_added.py:13,16,17`, `probe_cascade.py:12,13`, `probe_paths_r2.py:10,11`
- In the user's words: none; a release-pipeline risk only.
- Evidence: `bash .github/gates/gate03_lint.sh` from the worktree: "Found 8 errors" (F401, I001, RUF100), every one in `raw/adversary_r2/`. `ruff check` over the tracked Python files only (`git ls-files -z '*.py' | xargs -0 ruff check`): "All checks passed!". So the branch itself passes gate 03; the working tree does not.
- Suggested fix: `ruff check --fix` on `raw/adversary_r2/` before it is committed.
- NOT FIXED

### J2-101-05: when the check fails on an answer whose prose was all code-approvable rewording, the person now waits for a second writer call before getting the records list
- Blocking: no
- Severity: minor (unsure it is worth acting on)
- Where: `src/system_03_search_agent/core/graph.py:9746-9752` (check failure returns the first pass) feeding `:13086-13098` (the repair fires when the model grounded nothing, `model_grounded=bool(grounding.claims)`)
- In the user's words: if the sentence check is down, an answer that yesterday showed its summary sentences now shows "Note: no written summary could be checked against the records, so the records found are listed below with their sources", and takes one more writing call (median 4.8 s measured on 2026-09-14) to get there.
- Evidence, my probe (`scratchpad/j2/test_probe_write.py`, real `write_node`, guard mode, check replaced by one that raises `SentenceCheckUnreadable`): the writer's only prose is the 72% rewording. The check was asked twice (first draft, then the repair), the rewording was not shown, the screen showed the opening line, the records list and the note above, `trust_outcome` was `ask`. With the check approving: one sentence shown, `trust_outcome` `answer`. Fail-closed is correct; the extra call is the cost. On develop the same reply would have been shown by code with no call.
- Suggested fix: none required by the owner's decision ("an answer near its time limit drops these sentences rather than show them unchecked"). If speed matters here, skip the repair when the first pass had candidates and the check raised, since the repair's rewordings would meet the same failing check.
- NOT FIXED

## Verdict

PASS. No blocking finding. No finding sits inside a defect of this round's fix: the one change (`synthesized = False` at `grounding.py:1387`, candidate condition at `:1395-1399`) behaves as the owner decided under every probe below. J2-101-01 is the one to read before telling the owner what shipped: the build's sentence "No sentence the app writes in its own words reaches the screen unless the sentence check has read it" is not true for a sentence that wraps a short record value (a title) in the question's words; that path is the diagnosis's P2, outside option A, and is unchanged.

Verified with my own probes: claims 1 to 3 of the intended change (reworded sentences go to the check; copies show with no call; nothing moved is shown when the check cannot run), the all-approved equivalence with develop, the time floor boundary, Jev partial failure, the write step's fail-closed screen, three mutations, gates 02 and 03.

Only read, not probed: follow-up turns and Researcher depth as separate paths (I found by reading that both go through the same `write_node` and the same two `_ground_with_sentence_check` calls, `graph.py:12991` and `:13136`, and that no other caller reads quoted markers, `grep extract_evidence_quotes` over `src`).

## Checklist

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | No path shows a reworded sentence without the check | Pass for every sentence that carries a quote (the path the owner's decision covers). Open for P2, J2-101-01 | `grounding.py:1387` sets `synthesized = False`; the only line that sets it True is `:1401-1402`, `key in verified_syntheses`. `verified_syntheses` is passed at exactly one place in `src`, `graph.py:9759`, after `check_reworded_sentences` returned keys. Probe: 293 synthetic narratives, 0 first-pass claims carrying an evidence quote on the branch. Guard mode: `probe_graph.py` A to C. Jev mode, item approves and a pair call times out: "babies" not shown (`probe_jev.py`). Repair: same helper at `graph.py:13136`; my `write_node` probe showed the check asked for the repair's draft too. First sentence: the item 12.16 switch rule (`grounding.py:1539-1543`) still runs on the second pass. Mixed sentences: a copied clause plus a reworded clause keeps the copied clause only until approval (`probe_equiv.py`, last row, develop and branch both cand=1). Follow-up and Researcher: read only, same path |
| 2 | Copied is still the strict test only; no copy goes to the check | Pass | `strict_ok` (`grounding.py:1341-1354`) is untouched by the diff; the candidate condition still starts `not strict_ok` (`:1396`). Probe: copied sentences with and without a quote, cand=0 on both branches (`probe_equiv.py` rows 1, 5, 8, 9). No develop candidate was lost on the branch over 293 narratives ("LOST CANDIDATE" never printed). Mutation M4 below |
| 3 | Fail-closed: failure, below the floor, cost cap | Pass | `probe_graph.py`: budget 3.999 s, 0 calls, "babies" not shown; budget 4.0 s, 1 call, shown on approval; a reply naming an item never sent, not shown; a failed call on a rewording-only answer, `grounded=False refused=True narrative=''`. Through `write_node` (`test_probe_write.py`): the screen shows the records list and "Note: no written summary could be checked against the records, so the records found are listed below with their sources", `trust_outcome` `ask`, never the rewording. Cost cap: the builder's arm, confirmed red under my mutation M2 |
| 4 | No regression; stale comments | Pass with J2-101-02 and J2-101-05 | With every candidate approved, the branch's narrative and evidence quotes equal develop's in 293 of 293 narratives (`probe_equiv.py`, "all-approved mismatches=0"). With none approved, the branch never shows a sentence develop did not (0 of 293, markers normalized). All-copy answers: identical (cand=0 both). Held-back sentences: the person sees the records list and, when no prose remains, the structured fallback note and `ask`, as for any held-back sentence before. Both `graph.py` comments the build named now misdescribe behaviour, plus one in `grounding.py`: J2-101-02 |
| 5 | Tests, and three properties broken | Pass | Baseline: `958 passed, 25 skipped, 1 xfailed in 19.83s` over `tests/system_03_search_agent/synthesis/`, `core/test_write_*.py`, `core/test_repair_listing_mode.py`, `core/test_answer_readability_premise.py`, `core/test_graph.py`. Mutations below, each red, each restored |
| 6 | Gates 02 and 03 | Pass on the branch; the working tree fails 03 on untracked files, J2-101-04 | `gate02_import_order.sh` exit 0. `gate03_lint.sh`: "Found 8 errors", all in untracked `raw/adversary_r2/`; tracked files only: "All checks passed!" |

### Mutations

| Mutation | Where | Result |
|---|---|---|
| M1, the time floor removed (`if not candidates or budget_s < _SENTENCE_CHECK_MIN_BUDGET_S` to `if not candidates`) | `graph.py:9720` | `2 failed, 638 passed`: `test_check_every_rewording.py::...[too little time]`, `test_sentence_check.py::test_the_helper_fails_closed[...1.0-False]` |
| M2, fail open: on a check exception, approve every candidate | `graph.py:9750` | `8 failed, 632 passed`: the unreadable, call failed and cost cap arms, the repair failure arm, three `test_the_helper_fails_closed` cases, `test_the_write_step_in_jev_mode_asks_no_guard_when_jev_fails` |
| M3, any approval approves every candidate (`if verified_syntheses:`) | `grounding.py:1401` | `1 failed, 656 passed`: `test_sentence_check.py::test_approval_of_a_different_sentence_accepts_nothing`. One arm only, but it reads the property itself |
| M4, a copied sentence that carries a quote is stripped | `grounding.py:1419` | `2 failed, 655 passed`: `test_a_copied_record_sentence_shows_without_a_call[with a quote]`, `test_quote_anchored_synthesis.py::test_the_same_negative_sentence_with_its_negation_survives` |

M1 ran in the shared worktree and was restored with `git checkout --` (`git status` after: no tracked change). I then saw the round 2 adversary's untracked files in the same worktree, so M2 to M4 ran in a copy of the worktree in my scratchpad, restored from saved originals and diffed clean. M1 was in the shared tree for about 5 seconds; if the adversary ran tests in that window it may have seen two red arms that are not real.

## Probes I ran

All offline, no model call, scripts in the session scratchpad (not the repository):

- `probe_equiv.py`: develop's `grounding.py` (from `origin/develop`) beside the branch's, 293 narratives over two synthetic records (the hb4 abstract and title, a drug abstract and title) and a question naming babies and treatment.
- `probe_graph.py`: `_ground_with_sentence_check`, guard mode, floor boundary, failed call, a reply naming an unsent item.
- `probe_jev.py`: Jev mode with `call_jev_batch` replaced, item approves and pairs approve, veto, or time out.
- `test_probe_write.py`: the real `write_node` with the completeness test's state, prose that is only a rewording, check failing or approving.

## What I did not cover

- Any live model call, by the brief: whether the real check approves faithful moved sentences, and how often, is the build's measurement, not mine.
- Researcher depth and follow-up turns as runs; read only (checklist row 1).
- Pair-call and item-cap pressure on real Researcher answers (J2-101-03).
- The key collision where the same sentence and quote text sit under two different records (`synthesis_key` carries no record): pre-existing, not probed.
- The deployed app, and the build's live numbers and develop comparison, which I did not re-derive.
- The build's committed `raw/check_every/` scripts were linted and scanned for local paths, not run.
