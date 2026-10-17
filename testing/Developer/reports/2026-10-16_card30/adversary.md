# Card 30 step 1 adversary: unclassified variants say so

Pull request #261, branch `fix/card30-unclassified-variants-say-so`, commit `3d8988ca` on develop `78c68c1c`. One adversary round, 2026-10-16. Worktree at the pull request's head, `.env` linked; develop compared in a second detached worktree at `78c68c1c`. Probes under `<scratchpad>/card30_adv/`.

## Table of contents

- [What was attacked](#what-was-attacked)
- [Findings](#findings)
- [Live runs](#live-runs)
- [Offline probes](#offline-probes)
- [Verdict](#verdict)

## What was attacked

| Hunt | Where |
|---|---|
| A BRCA1 "pathogenic" answer still marked confirmed, or read as a pathogenic list | Live runs 1 and 2 |
| The note shown where the answer does show a classification | Live run 4 (rs334) |
| The floor on a question that never asked about classification | Live runs 5 and 6, decision probe |
| A slower answer from the new read in Write | Live timing, grace probe on both trees |
| The decision misfiring on wordings | Decision probe, 20 wordings |
| Refusal or ask back paths spending on the extra decision | Code reading of `think_node` and `write_node` |

## Findings

### A-30-01: two late decisions are now read one after the other, so Write can wait 2 s where develop waits 1 s

- Severity: minor. Not worse than develop by more than about a second, and never seen live.
- What: `_write_answer` awaits `_clinical_features_asked` and then `_classification_asked` (`src/system_03_search_agent/core/graph.py:14076` and `:14077`), each with its own `_LATE_DECISION_GRACE_S` of 1 s (`:1252`, `_read_late_decision` at `:1512`). The read sits before the listing leaves and before the writer starts, so it delays the first records too.
- Evidence: `<scratchpad>/card30_adv/grace_probe.py`, both decisions handed in still running:
  ```
  card30-adv       waited_s 2.0
  card30-adv-dev   waited_s 1.01
  ```
  Live, in 6 of 6 runs the decision had finished before Write read it (`done_on_entry: True`, wait 0 ms; see Live runs).
- Fix inside the fence if wanted: read the two decisions together (`asyncio.gather`), so the worst case stays 1 s.
- Worse than develop: only by 1 s in the case where Jev is already failing over for both decisions; no person waited for it tonight.

### A-30-02: the card 23 skip inside `_answer_parts` has no test

- Severity: minor (a test gap, no product defect).
- What: mutating one property at a time in `core/graph.py` and running the card 30 arms of `test_graph.py` and `test_write_answer_structure.py`:
  ```
  M1 floor ignores the decision          4 failed, 4 passed
  M2 _answer_parts skip removed          8 passed
  M3 Write's listing_tokens skip removed 1 failed, 7 passed
  ```
  M2 deletes `and not any(t.kind == "note" and t.text == VARIANT_TO_DISEASE_SOURCE_NOTE for t in tokens)` (`core/graph.py:13740` to `:13742`) and no test goes red. That guard is the one that matters when the code-built listing had no grounded claims (`listing_tokens` empty, `:14238`) and the variant table with card 23's line is built in the final `_answer_parts` call. File restored; `git status --short` clean.
- Worse than develop: no. With the guard intact the line is never said twice.

### A-30-03: query 22 moves from a confirmed looking answer to "ask", live, as the owner decided

- Severity: evidence (the designed change).
- What: every one of the 72 claim verdicts was `answer`, no structured fallback note, and the decision picked `asks_classification`. The answer level verdict is `ask` and the line reads "Based on 71 sources cited, not yet confirmed". With the decision's floor removed, the aggregate of 72 `answer` claims is `answer` (the M1 mutation shows the floor is the only thing that moves it in the unit arm). The owner's DECISIONS.md row of 2026-10-16 names query 22 gaining the line and "ask".

### A-30-04: the line shows on variant lists whose question never asked about classification

- Severity: unsure (the diagnosis made this the card's design, "every listing of unclassified graph variants").
- What: `What variants are in GCK?` (Plain language) and query 79 (Plain language) both carry "ClinVar's classification of these variants ... was not retrieved, so this list does not say which are pathogenic." The verdict is not floored on either: GCK stays `answer`, "Based on 68 sources cited"; query 79 is `ask` only through develop's own structured fallback floor. The line is true on both. For a person who asked only which variants exist, the word "pathogenic" is new to the page but not wrong.
- Worse than develop: no sentence or record is lost; one true line is added.

### A-30-05: the BRCA1 runs fell back to the structured listing, so tonight's live BRCA1 "ask" would have been "ask" on develop too

- Severity: evidence.
- What: both BRCA1 runs carry "Note: no written summary could be checked against the records", which floors at `ask` on develop (`core/graph.py:14867`). So the live BRCA1 runs show the line and an honest verdict but do not prove the new floor. The case the diagnosis feared (a written summary passing and "Based on 58 sources" with `answer`) did not occur in 2 runs; the unit arm `test_card30_a_classification_question_over_unclassified_variants_is_ask` covers it, and M1 shows it is load bearing.
- Also: BRCA1 at Plain language reached done at 24.9 s, over the 20 s target. Not the branch's: the classification read waited 0 ms; Write's writer and fallback took the time.

### A-30-06: the decision read 20 of 20 wordings the way a person would mean them

- Severity: evidence.
- What: `<scratchpad>/card30_adv/decide_probe.py`, one classifier call per wording through `_decide_point` with `_ASKS_CLASSIFICATION` (20 calls, all `decided_by=jev`):
  ```
  asks_classification: pathogenic, harmful, disease-causing, benign, VUS, likely pathogenic,
    "Is rs80357906 pathogenic?", "not pathogenic", "cause cancer", "dangerous mutations",
    "brca1 pathogenic variants", query 22
  not_applicable: "What variants are in GCK?", query 79 ("What diseases are caused by variants
    in the HNF1A gene?"), "What diseases is BRCA1 associated with?", query 23,
    "Papers on pathogenic bacteria in hospital water", "Which genes are linked to Marfan
    syndrome?", "Show me Salmonella isolates from 2023", "How many variants does TP53 have?"
  ```
  No miss. Query 79's "caused by" did not trip the criterion "disease causing".

### Hunts that found nothing

| Hunt | Evidence |
|---|---|
| The line contradicting a shown classification | Query 23 (rs334): the answer shows dbSNP's "not-provided, protective, likely-benign, pathogenic, other"; no card 30 line; decision `not_applicable` |
| A sentence or count line calling the BRCA1 variants pathogenic | In both BRCA1 runs the only token containing "pathogen" is the card 30 line. Count lines: "I found 40 genetic variants related to BRCA1, out of 15350 available" and "Found 40 sequence variant records for BRCA1, of 15350 available" |
| The line said twice or before the list | Each run with the line carries it once, after the last row (token index 61 after row 58, 77 after 74, 91 after 88, 76 after 69, 65 after 62) |
| A claim's own verdict moved | `aggregate([trust_outcome, "ask"])` on the answer level only (`core/graph.py:14994` to `:14995`); live claim verdicts unchanged in kind |
| Spend on refusal or ask back | The task is cancelled in `think_node`'s `finally` whenever the search does not go ahead (`core/graph.py:4202` to `:4208`) and in `write_node`'s `finally` (`:13767`), exactly as `features_task`. Small talk never starts it (test `test_card30_small_talk_is_never_asked_about_classification`) |
| What "ask" changes on screen | The web strip shows "Answered" in the warn tone when a trust line exists (`frontend/src/hooks/useRunView.ts:1197`), as for every existing floor |

## Live runs

Six runs through `core.run.run_streaming()` on the branch tree, `reads_placement=True`, session ids `card30-adv-<label>`, settings as card 115's adversary (`CLASSIFIER_PROVIDER=jev`, guard and plan models `deepseek/deepseek-v4-flash`, `PER_QUERY_COST_CAP_USD=0.25`, the writer model from the local env). Script `<scratchpad>/card30_adv/live.py`. Session memory recording failed after each run for want of a guest owner id; the answers were complete.

| Run | Question | Depth | Decision pick | Note shows | Trust outcome and line | Classification read wait | Done at | Cost |
|---|---|---|---|---|---|---|---|---|
| 1 | Which BRCA1 variants are pathogenic? | Plain language | asks_classification | Yes, once | ask, "Based on 57 sources cited, not yet confirmed" | 0 ms | 24.9 s | $0.0195 |
| 2 | Which BRCA1 variants are pathogenic? | Researcher | asks_classification | Yes, once | ask, "Based on 57 sources cited, not yet confirmed" | 0 ms | 14.0 s | $0.0112 |
| 3 | Query 22, CFTR clinically significant | Researcher | asks_classification | Yes, once | ask, "Based on 71 sources cited, not yet confirmed" | 0 ms | 19.9 s | $0.0135 |
| 4 | Query 23, rs334 | Researcher | not_applicable | No | ask (structured fallback), "Based on 1 source cited, not yet confirmed" | 0 ms | 10.8 s | $0.0049 |
| 5 | What variants are in GCK? | Plain language | not_applicable | Yes, once | answer, "Based on 68 sources cited" | 0 ms | 14.3 s | $0.0057 |
| 6 | Query 79, HNF1A diseases | Plain language | not_applicable | Yes, once | ask (structured fallback), "Based on 61 sources cited, not yet confirmed" | 0 ms | 17.6 s | $0.0095 |

Spend: $0.064 for the six runs plus about $0.002 for the 20 decision probe calls, under $0.07 of the $1 allowed.

Seen on the way, develop's own and not the branch's: query 23's count line reads "Found 1 variant record record for rs334" (card 37's ground).

## Offline probes

| Probe | Result |
|---|---|
| Card 30 tests on the branch | `32 passed` (answer layout, answer structure, bare topic) and `19 passed` (test_graph card 30 and features arms) |
| `grace_probe.py` | 2.0 s on the branch, 1.01 s on develop (A-30-01) |
| One property mutations | M1 red, M2 green (A-30-02), M3 red; file restored, tree clean |

## Verdict

Nothing on this branch shows a person anything worse than develop. The BRCA1 answer never reads as confirmed, the line shows once after the list in both depths, rs334 carries no line, and the floor hit only the two classification questions. The two minor findings are a 1 s worst case that did not occur live and a test gap.

VERDICT: PASS
