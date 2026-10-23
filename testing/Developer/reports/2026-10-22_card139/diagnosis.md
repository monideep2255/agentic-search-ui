# Card 139 diagnosis: notes that say the wrong thing

Card 139, filed from the 2026-10-18 browser retest, rows 47, 49 and 54 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`). Three notes under an answer state something that is not true on the page. This file gives each one's cause, the smallest true fix, and what was built.

## Table of contents

- [Summary](#summary)
- [Note 1: "listed below" under the list](#note-1-listed-below-under-the-list)
- [Note 2: "this answer shows 10" where it shows 5](#note-2-this-answer-shows-10-where-it-shows-5)
- [Note 3: entities "named in the question" that the question never named](#note-3-entities-named-in-the-question-that-the-question-never-named)

## Summary

| Note | Cause | State |
|------|-------|-------|
| 1, "listed below" | Notes always render after the listing, on every surface | Fixed: the two notes name no direction |
| 2, "shows 10" | The count is a constant, the summary cap, not a count of what is shown | Fixed: the note counts the answer's own citations of that kind |
| 3, "named in the question" | The list is every record a mention was expanded into, not the mentions | Open, waits for card 128: the fix lives in the caller, in the region card 128 owns |

## Note 1: "listed below" under the list

What the person sees: "Note: no written summary could be checked against the records, so the records found are listed below with their sources", sitting under the records it calls "below".

Cause:

- `core/graph.py` `_AnswerParts` (about line 13050): the answer's reading order is summary, then listing, then notes, and `_answer_tokens` joins them in that order. Every note is in the notes part.
- On screen, `frontend/src/hooks/useRunView.ts` collects the trailing notes into `systemNotes` and `AnswerScreen.tsx` renders them after the answer body. The command line renders tokens in arrival order. The saved answer is the same token list. So on every surface a note follows the listing.
- Two notes said "below" anyway: `_build_structured_fallback_note` (graph.py:10969) and the no-omission clause of `_build_repair_cap_note` (graph.py:10652).

Fix, built: both notes now name no direction.

- "Note: no written summary could be checked against the records, so this answer lists the records found with their sources", the same shape as the sibling notes "so this answer lists the records found" and "so this answer lists the records gathered so far".
- "..., and the records it would have added are listed in this answer as found".
- The prefix `useRunView.ts` matches ("Note: no written summary could be checked against the records") is unchanged, so the screen still shows the note.

Checked and left as they are:

- The repair-cap note's other clause, "the omission described above", is true: the incomplete-answer note that describes the omission comes before it in the same notes list.
- `synthesis/findings.py:868` and `:1640` are instructions to the writing model, not notes a person reads. Both are true: the findings follow the instruction in the prompt, and the listing follows the written summary on screen.

Tests: `tests/system_03_search_agent/core/test_write_completeness.py` pins the new wording, that neither note contains "below", and that the fallback note comes after the records in the answer.

Frontend tests: `frontend/src/answerNotesHidden.test.tsx` and `AnswerScreen.listingFirst.test.tsx` now feed the new wording. The second sends the note with no kind, so it also proves `useRunView.ts` still detects it by its unchanged prefix.

## Note 2: "this answer shows 10" where it shows 5

What the person sees, query 104: "NCBI lists N sequence records linked to PMID ...; this answer shows 10", over five sequence records, and the same for genome assemblies.

Cause:

- `core/paper_links.py` `count_note` (line 155) takes `shown` with a default of `MAX_LINKED_PER_DB`, 10, and the only caller, `core/graph.py` `_paper_link_notes` (line 10082), never passes it. So "shows 10" is the number of ids sent to ESummary, not the number shown.
- `core/graph.py` (about line 8301) then sorts each `*_summary` breadth result by record URL and cuts it to `_BREADTH_ROW_CAP`, 5, since `nuccore_summary`, `assembly_summary` and the other paper-link summaries are all in `_BREADTH_FIELDS_BY_PURPOSE`. Five rows per kind reach the answer.
- A second error follows from the same constant: when NCBI lists 6 to 10 linked records, `total <= shown` is true, so no count note shows at all, though the answer shows only 5.

Smallest true fix: count the records of that kind the answer cites. `_paper_link_notes(state)` takes only state, and the final citations exist only in the notes assembly in `write_node` (graph.py about line 15377, `citations`). So the fix is:

1. `_paper_link_notes(state, citations)`: for each target, count the citations whose `source_url` is that database's record page (`https://www.ncbi.nlm.nih.gov/{db}/...`), and pass that count as `shown`.
2. `count_note`: make `shown` required, and return None when `shown == 0` or `total <= shown`.
3. The call at graph.py:15377 passes `citations`.

Built, after the lead widened the fence (2026-10-22):

- `paper_links.summary_purpose(target)` names the kind's ESummary call; `count_note` takes `shown` with no default.
- `core/graph.py` `_paper_link_shown` counts the answer's citations, by page (`source_page_key`), whose page is one of the records that kind's ESummary call returned. `_paper_link_notes(state, citations)` passes that count, and `write_node` passes its final `citations`.
- The wording is unchanged apart from the number: "NCBI lists 1533 sequence records linked to PMID 11237011; this answer shows 5."
- Tests in `tests/system_03_search_agent/core/test_paper_links_wiring.py`: query 104's shape (1533 listed, 10 summarised, 5 cited, "shows 5"); 8 listed with 5 shown gives the note, all 8 shown gives none; and the whole Plan, Act and Write path, where the note's number equals the sequence record pages the answer cites.

A fix inside `paper_links.py` alone would be a second constant (5 in place of 10), still a claim and not a count, and wrong whenever ESummary returns fewer records or grounding drops one. Not built for that reason.

## Note 3: entities "named in the question" that the question never named

What the person sees, query 29, the CFTR-locus window: "Note: this answer does not address the following entities named in the question: CFTR-AS1, CFTR-AS2, LOC.... Ask about them individually for a complete answer." The person named a region, or CFTR, never those genes. Card 129's judge saw the same with breast cancer: one mention bound to several MedGen records, each named back as if the person had typed it.

Cause:

- `core/graph.py` `write_node` (lines 15075 to 15106) takes `target_entities` from the graph query's input: every CURIE Think and the binding produced. For a window that is every gene in the window (`window_confirmed`, about line 4413, each gene's own symbol as its "mention"). For a disease mention it is every MedGen record the mention bound (`_confirm_extracted_entities`, about line 3548).
- `_unaddressed_target_entities` (line 9994) reports each CURIE with no citation, and the label is the record's own title or symbol. So the note names records the question was expanded into, and calls them "named in the question".
- The check also fires on a one-mention question, since `len(target_entities) >= 2` counts CURIEs, not mentions.
- `_build_partial_answer_note` (line 10216) only joins the labels it is given. It cannot recover the mentions.

Smallest true fix, in the caller (lines 15075 to 15106):

1. Group `target_entities` by the mention each came from, using `resolved_entities` (`text` beside `curie`) and Think's own mention for a window or a disease binding.
2. A mention counts as addressed when any of its records is cited.
3. Fire only when two or more mentions were named and at least one is unaddressed. Name each unaddressed mention as the person typed it, or as Think extracted it.
4. `_build_partial_answer_note` keeps its sentence, now true: "this answer does not address the following entities named in the question: CFTR".

Why it is not built: steps 1 to 3 sit in lines 15075 to 15106, the region card 128 owns. The lead's call (2026-10-22): the fix waits until card 128 merges. A wording-only change was built and then reverted, since a reworded note that still names the wrong records is not worth shipping. When the fix is built, the owner's decision of 2026-10-22 lets the lead word the note plain and true: opening "Note:", one sentence, naming only what the question named, blaming no one.

Open, for when the fix is built: the window case. A window question names a region, not genes, so after the fix above a window's genes would never be named back. Three ways to word what the person sees:

| Option | What the person reads | Cost |
|--------|------------------------|------|
| A, recommended | Nothing for the window's genes. The note fires only for two or more mentions the person typed | Think's window disclosure (`coordinate_window.window_disclosure`) names the window's genes in the progress narrative, not under the answer; an uncited gene goes unremarked there |
| B | "Note: this answer cites no record for these genes in the region you asked about: CFTR-AS1, CFTR-AS2. Ask about one by name for its records." | New wording the owner has not seen; true, and names records, but as records found, not as words typed |
| C | Keep a one-line count: "Note: 3 of the 7 genes in this region have no record in this answer" | New wording; no names, so no wrong names, but less to act on |

Option A follows "A confident wrong record is worse than a missing one" and needs no new wording. Options B and C need the owner's yes on the sentence.
