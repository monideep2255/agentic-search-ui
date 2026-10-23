# Card 128 adversary round

One adversary round on pull request #291, branch fix/card128-note-when-summary-repeated. Findings are filed as found and never closed here.

## Findings

### A-128-01: the note fires when written sentences failed their check, and says they only repeated the records

- Severity: major (inside this card's fix)
- What: the flag at `src/system_03_search_agent/core/graph.py:14924` is `bool(restatements_dropped) and not grounding.claims`. It never reads `grounding.stripped_count`, so a reply where some sentences were stripped as ungrounded and the rest were dropped as restatements gets the note "the sentences written only repeated the records listed below". The card's own condition, and the comment at `graph.py:14921` to `:14923`, is "every sentence the writer wrote grounded". That is not what is checked.
- Reproduction: scratch probe driving the real `write_node` with the fixtures of `tests/system_03_search_agent/core/test_write_answer_quality.py` (`_state("researcher")`, `_install`), with a spy around `drop_record_restatements`.
  - Reply: the restating reply for odd ref numbers, and "This record shows a completely different value XYZ123 [n]." for even ones. Spy: `in claims 3 stripped 3 sentences 3 -> dropped 3 left 0`. Tokens: count line claim, six rows, `note 'No written summary: the sentences written only repeated the records listed below'`, trust `answer` / `low`.
  - Reply: the restating reply plus "BRCA1 variants cause breast cancer in ninety percent of carriers [1].". Spy: `in claims 6 stripped 1 -> dropped 6 left 0`. Same note, trust `answer`.
- Why it matters: half of what the writer wrote failed the check against the records, and the reader is told the opposite, that it was all correct and merely redundant. On the path where nothing written grounds, the structured fallback says "no written summary could be checked" and floors at `ask`; here a mix of failed and repeated sentences gets an untrue reason and the clean `answer` trust. The fix would need `grounding.stripped_count == 0` read before the drop (or the owner's call on what the note says in the mixed case).
- NOT FIXED

### A-128-02: when the listing cannot list a record, the note says "no written summary" next to "not covered in the summary above", and the dropped sentence's record is not listed below

- Severity: major (inside this card's fix; reached only when the listing grounds fewer records than the writer was shown, which the code calls rare)
- What: two false statements on one path.
  - `_build_incomplete_answer_note` is called with `summary_exists=not structured_fallback_used` (`graph.py:15158`), which is True on the card 128 path, so it closes "not covered in the summary above" directly under the new note saying there is no written summary. This is the exact incoherence the 2026-09-20 fix (`graph.py:10843` to `:10859`) removed for the structured fallback note.
  - `drop_record_restatements(grounding, synth_findings)` (`graph.py:14917`) drops a sentence for restating any prepared record, not any LISTED record. A sentence about a record the listing could not ground is dropped too, and the note then says it "only repeated the records listed below" when that record is not below.
- Reproduction: scratch probe, real `write_node`, restating reply, `build_structured_fallback_narrative` wrapped to leave out finding `cq-aq-3` (disease name number 3), so the listing cannot ground it. Researcher tokens: `claim 'Found 2 disease records for BRCA1: disease name number 1 [1] and disease name number 2 [2]. '`, five rows (no disease name number 3 anywhere), `note 'No written summary: the sentences written only repeated the records listed below'`, `note 'Note: one further disease record was found for this question and is not covered in the summary above'`, trust `ask`. Plain language: the same two notes, then the medical-advice note. `joined_text` (CLI and GraphQL) ends with both sentences. The web screen hides the second note (`frontend/src/components/screens/AnswerScreen.tsx:648`), so only the API, CLI, MCP and saved answer show the contradiction; the web still shows the first false claim.
- Why it matters: the writer's one sentence about disease name number 3 was correct and grounded, it was removed, and the reader is told it was redundant with a list that does not contain it. A correct fact the user would have seen at base is gone with a reason that is untrue. At base the note was absent, so the second contradiction is new with this card.
- NOT FIXED

- Correction to A-128-02, "Why it matters": the drop of the disease name number 3 sentence is not new, it happens at base too (the drop predates this card). What this card adds is the untrue reason given for it, and the two notes that contradict each other.

### A-128-03: in Plain language the note "No written summary" is followed by "This is a research summary"

- Severity: minor, unsure (two notes that read as contradicting each other; the medical-advice note is fixed text, and both wordings may be the owner's)
- What: on the card 128 path at Plain language depth, the notes list (`graph.py:15393` to `:15407`, then `graph.py:15429` to `:15430`) ends with the new note and then `_MEDICAL_ADVICE_NOTE`. The answer also opens with a code-built count sentence that reads as written prose.
- Reproduction: scratch probe, real `write_node`, `_state("plain_language")`, restating reply. Tokens: `claim 'I found 3 conditions related to BRCA1 [1][2][3]. '`, six rows, `note 'No written summary: the sentences written only repeated the records listed below'`, `note 'This is a research summary, not medical advice.'`. Saved markdown ends with the same two paragraphs back to back. With a service_down failed search the outage note sits between them, and reopening rewrites only the outage note (checked with `past_tense_outage_notes`), so the pair also survives reopening.
- Why it matters: the reader is told there is no summary, then that this is a summary, under a first sentence ("I found 3 conditions...") that looks like a written one. Not a defect in the logic; flagged so the owner sees the pair when settling the wording.
- NOT FIXED

- Correction to A-128-01: the flag is at `graph.py:14921` (comment at `:14918` to `:14920`), not `:14924`.

### A-128-04: two wrong conditions for the note pass every write suite, because the only negative case keeps three sentences

- Severity: minor (a test gap in this card's tests, distinct from J-128-06 and J-128-07)
- What: the negative test (`tests/system_03_search_agent/core/test_write_answer_quality.py:303` to `:309`) uses the relating reply, where three written sentences survive. The positive test uses a reply where exactly six are dropped. So neither the "one sentence survives" boundary nor a smaller drop count is pinned.
- Reproduction: in a scratch copy of the worktree (worktree untouched, restored and checked with `diff -q`), seven suites (`test_write_answer_quality.py`, `test_graph.py`, `test_write_completeness.py`, `test_write_answer_structure.py`, `test_write_findings_tail.py`, `test_summary_label_only_sentence.py`, `test_card_17_lead_in_order.py`):
  - Flag changed to `bool(restatements_dropped) and len(grounding.claims) < 3`: `401 passed`. Under that mutant the reply "NCBIGene:672 is associated with disease name number 1 [1]." plus restatements of the other five records gives `claim 'NCBIGene:672 is associated with disease name number 1 [1]. '` followed by `note 'No written summary: the sentences written only repeated the records listed below'`: the false note over a written sentence, and green.
  - Flag changed to `restatements_dropped >= 6 and not grounding.claims`: `401 passed`.
  - Flag changed to `not grounding.claims` (the drop count ignored): `1 failed, 400 passed` (`test_graph.py::test_happy_path_emits_the_expected_event_type_sequence`), so that one is caught, by an unrelated test.
- Why it matters: the brief's "never otherwise" has no boundary test. A later edit that shows the note over one surviving sentence ships green.
- NOT FIXED

## Probed and found holding

All with the real `write_node`, stubbed writer replies, the fixtures of `test_write_answer_quality.py`, no live model calls.

- Trust line on the card 128 path: `Based on 6 sources cited from MedGen, ClinicalTrials.gov and PubTator3`, the same at base and over the relating reply, true of the listed records. No "Confirmed by N" arose with these low-risk fixtures; the outcome staying `answer` is the owner's call and is not filed.
- Beside other notes: truncation note (before it), partial-entities note, unfinished-search note, outage note (after it), each once, no duplicates. Trust floors at `ask` where those notes floor it.
- Placement-reading client (`context.reads_placement=True`): the note carries `placement='listing'` like the other notes, and appears once.
- Follow-up turn (memory-bound plan, "What diseases is it linked to?"): same note, same trust, both depths.
- Saved answer: the note is its own markdown paragraph; `past_tense_outage_notes` on reopen rewrites only the outage note and leaves the card 128 note as written. An answer saved before this change is stored text and nothing on the reopen path recomputes notes (read, `feedback/history.py:358` and `feedback/outage_note.py`).
- Empty findings: refusal, no note.

## Not probed

- Stop mid-write and the cost cap inside the sentence check (read only: the cap and writer-failure paths set `structured_fallback_used` and never reach the new branch).
- The completeness repair replacing a relating first draft with a restating repair: with these fixtures the listing covers every record, so the repair never ran (one Synth call observed).

## Overall

FAIL against "the note appears when every written sentence grounded and was dropped as a restatement, and never otherwise". A-128-01 and A-128-02 are both inside this card's fix: the note fires when written sentences failed their check, and when a dropped sentence's record is not listed, in the second case beside a note that points at "the summary above". The worktree was left clean (`git diff HEAD` empty, only `?? frontend/node_modules`).
