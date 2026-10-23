# Card 128 judge round, 2026-10-22

Branch fix/card128-note-when-summary-repeated, pull request 291. Findings are appended as they are established.

## Findings

### J-128-01: the note fires after the restatements are put back, over the very sentences it says are gone

- Severity: major (inside this card's fix; how often a live run reaches it is unsure)
- What: `all_sentences_were_restatements` is computed at `src/system_03_search_agent/core/graph.py:14921`, before the "never make an answer worse" restore at `graph.py:15001` to `graph.py:15006`, which puts the dropped sentences back (`grounding = prose_before_drop`, `restatements_dropped = 0`) when the listing grounded nothing. The flag is never cleared there, so the `elif` at `graph.py:15073` still emits the note. The answer then shows the written sentences AND says "No written summary: the sentences written only repeated the records listed below", with no listing below at all.
- Reproduction: scratch probe (outside the worktree) on the restating reply of `test_write_answer_quality.py`, with `graph_module.run_grounding_pass` patched to return an empty `GroundingResult` only when `code_built_listing=True` (the listing grounds nothing). Researcher tokens observed: `claim 'Found 3 disease records for BRCA1: ...'`, then six `claim 'Disease MedGen:C1, name: disease name number 1 [1]. '` and so on (the restored written sentences), then `note 'No written summary: the sentences written only repeated the records listed below'`, `TRUST answer`. Plain language: the same six restored claims, the same note, then the medical-advice note. 2 passed (probe prints, it does not assert).
- Why it matters: the reader is told there is no written summary directly under the written sentences, and pointed at a list that is not there. A false statement about the answer, the condition the brief asked to hold "never otherwise". The fix is to compute or re-check the flag after the restore (for example `and restatements_dropped` at the `elif`, since the restore zeroes it).
- NOT FIXED
### J-128-02: the citation coverage grader counts the new note as an uncited factual claim and fails the run

- Severity: major (a live eval gate; no live run made here, the grader was called directly)
- What: every other harness note opens "Note:", which `_FRAMING_PREFIXES` in `tests/system_03_search_agent/eval/test_write_step_eval_gate.py:188` to `:191` exempts. The new note opens "No written summary:" (`graph.py:10962`), matches no framing prefix and no `_HARNESS_NOTE_MARKERS` entry, so `_citation_coverage` (`:167`) counts it as an uncited factual sentence, and `grade` (`:306` to `:308`) records "citation coverage ...: an uncited factual claim", a failed run. The builder's docstring (`graph.py:10955` to `:10959`) claims "like every other note here"; it is not, every sibling's docstring names the "Note:" opener as the shape the grader depends on (`graph.py:10976` to `:10979`).
- Reproduction: `_citation_coverage("Found 3 disease records for BRCA1: a [1], b [2] and c [3]. Disease a [1]. " + note, [{"x": 1}])` printed `0.667 False` for the new note and `1.0 True` for the structured fallback note (second column is `_looks_like_framing(note)`).
- Why it matters: a correct, fully cited answer on this path fails the write-step eval gate. The owner's wording opens "No written summary:", so either the grader learns the note or the note gains the "Note:" opener; that is the owner's call on wording, not mine.
- NOT FIXED
### J-128-03: a token with no kind carrying the new note renders as an uncited claim on the web screen

- Severity: minor (the server types this note `kind="note"` today, so only a kind-less producer is affected)
- What: `frontend/src/hooks/useRunView.ts:58` to `:85` lists the structured fallback note ("Note: no written summary could be checked against the records") in `SYSTEM_NOTE_PREFIXES`, and `:876` also catches any uncited token opening "Note:". The new note matches neither, so on the kind-less path it becomes a claim. The typed path works.
- Reproduction: scratch vitest probe (scratchpad config, nothing written to the worktree) feeding `useRunView` into `AnswerScreen`. Typed: `systemNotes= ["No written summary: the sentences written only repeated the records listed below"] claims= ["Found 1 disease record."] hidden= false onscreen= 1`. Kind-less: `systemNotes= [] claims= ["Found 1 disease record.","No written summary: the sentences written only repeated the records listed below"]`.
- Why it matters: asymmetric with the fallback note the brief says it must match; a kind-less replay would show the disclosure on the provenance spine as an uncited claim. No frontend test exercises the new text at all (`grep -rn "No written summary" frontend/src` matches only the old note's tests).
- NOT FIXED

### J-128-04: the note says "listed below" but every surface puts it after the records

- Severity: minor, unsure (the wording is the owner's, and the structured fallback note says "listed below" too)
- What: the note is emitted last, after the listing, and the screen renders it in the Notes section after the answer (`frontend/src/components/screens/AnswerScreen.tsx:2112` to `:2135`).
- Reproduction: Researcher token order from the restating reply: count line claim, three tables of `table_row`, then `note 'No written summary: the sentences written only repeated the records listed below'`. Saved answer markdown (`answer_markdown_from`) ends `... | trial title number 2 [6] | NCT00000002 |\n\nNo written summary: the sentences written only repeated the records listed below`. CLI and GraphQL text (`joined_text`) ends `... trial title number 2 [6]. \n\nNo written summary: ...`.
- Why it matters: on every surface the records are above the note, not below. Flagged for the owner, not a builder defect.
- NOT FIXED

### J-128-05: the owner's sentence ends with a period, the shipped note does not

- Severity: minor
- What: DECISIONS.md quotes "No written summary: the sentences written only repeated the records listed below." The builder returns the text without the period (`graph.py:10961` to `:10964`), justified as "like every other note here".
- Reproduction: test pin at `tests/system_03_search_agent/core/test_write_answer_quality.py:296` asserts the period-less string; observed token text `'No written summary: the sentences written only repeated the records listed below'`. The Plain language medical-advice note right after it does end in a period (`'This is a research summary, not medical advice.'`).
- Why it matters: a deliberate deviation from the owner's exact words; probably right for consistency, but it should be said to the owner rather than decided silently.
- NOT FIXED
### J-128-06: no test pins the note's absence on the restore path, so J-128-01 is invisible to the suite

- Severity: minor (the test gap behind J-128-01)
- What: adding the guard that fixes J-128-01 (`elif all_sentences_were_restatements and restatements_dropped and not structured_fallback_used:` at `graph.py:15073`) changes the restore-path output and leaves every named test green, so neither behaviour is pinned.
- Reproduction: in a scratch copy of the worktree with that one-line change, `pytest test_write_answer_quality.py test_graph.py test_write_completeness.py` printed `307 passed in 9.28s`; the restore probe under the same change printed no card 128 note (Researcher: none; Plain language: only `'This is a research summary, not medical advice.'`).
- Why it matters: the defect in J-128-01 ships green, and a later fix to it would also ship without a test.
- NOT FIXED

### J-128-07: the negative test's populate-check passes on the count line, not on a written sentence

- Severity: minor (the builder flagged this; confirmed)
- What: `tests/system_03_search_agent/core/test_write_answer_quality.py:308` checks `any(t["kind"] == "claim" for t in tokens)`. The code-built count line is itself a `kind="claim"` token, so the check holds when every written sentence was dropped.
- Reproduction: restating reply, Researcher: claim tokens observed `['Found 3 disease records for BRCA1: disease name number 1 [1]']`, only the count line, so the populate-check would pass there. With the relating reply, which the test uses, the spy on `drop_record_restatements` returned `(3, [three GroundedClaim 'NCBIGene:672 is associat...'])`: three dropped, three written sentences survived. So the test exercises the right case today, but its own check cannot tell. A check that would fail: assert a claim token whose text does not start with "Found " or "I found ", for example "NCBIGene:672 is associated with".
- Why it matters: if the relating fixture drifts into restatements, the populate-check stays green and the negative arm silently becomes the positive case.
- NOT FIXED

## Break it, run in a scratch copy of the worktree (worktree untouched)

- The new `elif` branch deleted (4 lines): `FAILED ...::test_researcher_drops_restatements_the_list_carries_and_keeps_a_cited_summary`, `1 failed, 17 passed`. Red, as required.
- Condition inverted (`elif not all_sentences_were_restatements ...`): both `test_researcher_drops_restatements...` and `test_no_restatements_note_when_a_written_sentence_survives` FAILED, `2 failed, 16 passed`. Red.
- Condition reduced to `elif not structured_fallback_used` (note always on): `test_no_restatements_note_when_a_written_sentence_survives` FAILED, `1 failed, 17 passed`. Red.
- The J-128-01 guard added: `307 passed`, no test notices (J-128-06).
- Restored: scratch file `diff -q` against the worktree file is clean; worktree `git diff HEAD --stat` printed nothing; `git status --short` printed only `?? frontend/node_modules`. No git stash used.

## Verified by my own probes

- Base against head, 22 cases (5 replies: empty, ungroundable, mixed, restating, one relating sentence; both depths; listing grounding normally and forced empty; writer failure), events compared with cost events and volatile fields removed: 18 identical. The 4 restating cases differ only by an added `paragraph_break` and the `note` token, and `trust_outcome` is `answer` at base and head. So the structured fallback path (empty, ungroundable) and the writer-failure path are byte-identical, and trust is unchanged.
- At `graph.py:14921` `grounding.claims` holds only written sentences: the spy showed `(6, [])` for the restating reply, with the count line and listing not in it.
- Delivery: screen (typed note in `systemNotes`, not hidden, on screen once), saved answer markdown, and `joined_text` (the CLI and GraphQL fold) all carry the note, by the same `notes` list as the fallback note (`graph.py:15393` to `:15407`).
- Suites: the named Python files `307 passed in 15.68s`; frontend `answerNotesHidden`, `AnswerScreen.listingFirst`, `set9AnswerStructure`: `Test Files 3 passed (3) Tests 20 passed (20)`. None of the frontend tests contains the new text.

## Read only, not probed

- The GraphQL adapter end to end (I checked `adapters/graphql/fold.py:795` to `:798` appends token payloads kind-blind and ran `joined_text`, not a GraphQL query).
- The writer-failed path with the listing already sent (`listing_sent` true): the probe state does not read placement, so it returned `refuse` at base and head alike. By reading, that path sets `structured_fallback_used` and never reaches the `elif`.

## Overall

Acceptance not met. The note fires on the intended case at both depths, trust is unchanged and every other path is identical to base. But it also fires on the restore path (J-128-01), where the written sentences are back on screen, which breaks "never otherwise". And the write-step eval gate's grader counts it as an uncited claim (J-128-02). Both sit inside this card's fix.
