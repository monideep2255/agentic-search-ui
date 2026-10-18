# Build phase 8.1: fix-and-verify round

The phase's one fix-and-verify round, run by the fix agent on 2026-09-25 against `phase/8.1-good-questions-answer` at `310f607`. The work list is the lead's triage of round 1 in `tracker/phase_8.1.md`. Each result is written here the moment it is established.

## Table of contents

- [Scope](#scope)
- [Item 1: the Think retry](#item-1-the-think-retry)
- [Item 2: thirty sources on a paper question](#item-2-thirty-sources-on-a-paper-question)
- [Item 3: the MedGen clinical features path](#item-3-the-medgen-clinical-features-path)
- [Tests and lint](#tests-and-lint)
- [Live runs](#live-runs)

## Scope

- File fence: `core/graph.py`, `synthesis/findings.py`, `tools/ncbi_eutils_actions.py`, `tools/ncbi_efetch_schemas.py`, `harness/coordinator_worker.py`, their tests, and this report.
- Untouched on purpose: `synthesis/grounding.py` and `synthesis/trust.py`. The cite-or-refuse gate stays exactly as develop has it.
- Not reintroduced: the two reverted changes, `c9b3441` (full-retrieval conflict floor) and `76a0578` (stacked citation markers).

## Item 1: the Think retry

Findings: F-8.1-J04, J05, A05.

What the person typing a question gets: nothing changes on a good run. On a run where the planning model sends a malformed reply, the second attempt still tells it exactly what was wrong, and now a reply engineered with an enormous or multi-line key name can no longer blow up the second model call or forge a line in the operator's log.

What changed, in `core/graph.py`:

- `_THINK_ERROR_TEXT_MAX_CHARS = 300`, a named constant. 300 holds every real field-level complaint (the live shape "narrative: Field required; bogus_field: Extra inputs are not permitted" is 60 characters), so only a reply whose key names are themselves oversized gets elided.
- `_bounded_one_line(text, max_chars)`: every non-printable character (newline, carriage return, control characters, U+202E, U+200B) becomes a space, whitespace collapses, and anything past the cap is cut with a note "... [N more characters elided]".
- `_think_validation_detail` now returns its summary through that bound. Its docstring no longer claims a 256-character cap it never had.
- `_think_error_text(exc)` is the one form of the error both readers take. In `think_node` it is computed once as `error_text`; the warning log and the retry prompt both use `error_text`, never `exc` raw.

Tests, in `tests/system_03_search_agent/core/test_graph.py`:

- `test_think_retry_feeds_back_the_validation_error` rewritten so it can fail. The fake model now repeats its bad reply unless the messages carry attempt 1's reply echoed as the assistant turn AND a user turn naming "bogus_field" and "narrative: Field required". The word "bogus_field" appears nowhere except in the bad reply and the feedback built from it, unlike "narrative", which the system instruction also contains (the vacuous check J05 found). It also asserts attempt 1 carries no feedback and attempt 2 carries exactly two more messages.
- `test_think_validation_detail_is_bounded_for_an_oversized_key`: the 5,000-character key and five 20,000-character keys from round 1.
- `test_think_error_text_cannot_forge_a_second_line`: newline, carriage return, escape sequence, U+202E, U+200B in a key name.
- `test_bounded_one_line_keeps_a_short_error_whole`.
- `test_think_retry_prompt_and_log_carry_only_the_bounded_error`: end to end through `think_node` with a 20,000-character key holding a newline; the retry prompt and both warning log lines are one line and bounded.

Proof the feedback test can fail (run 2026-09-25 in this worktree, then restored from a byte copy):

- Mutation 1: the line `call_messages = think_messages + [` changed to `_unused_feedback = think_messages + [`, which restores the blind resend. Result: `2 failed, 12 passed` (`test_think_retry_feeds_back_the_validation_error` at `assert _carries_feedback(think_calls[1])`, and the end-to-end bounding test). Restored: `14 passed`.
- Mutation 2: `_bounded_one_line` made to return its input unchanged. Result: `3 failed, 11 passed` (the three bounding tests). Restored: `14 passed`.

## Item 2: thirty sources on a paper question

Finding: F-8.1-A08.

What the person typing a question gets: on a question whose prompt carries long paper abstracts, the writing model now reads all 30 findings it is handed instead of stopping part-way down the list, so the owner's 30-source decision takes effect for the model's own prose too, not only for the code-built listing.

What changed:

- `synthesis/findings.py`: `MAX_FINDINGS_BLOCK_CHARS` 12,000 to 18,000, with the reason and the decision it serves in its comment.
- `MAX_FINDINGS_PER_PROMPT = 25` in the same file was checked and left alone: it is only a default argument of `build_synth_findings`, and the live caller in `write_node` passes `_MAX_FINDINGS_FOR_DISPLAY` (100) instead, so it binds nothing on the live path.
- Test comment in `test_pubmed_abstract_grounding.py` that named "12,000" now names the constant.

Tests, `tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py`:

- `test_a_thirty_finding_prompt_with_long_abstracts_reaches_the_model_whole`: the longest prompt the live path can build (the breadth plan fetches at most 5 papers per question, so 5 abstracts and one gene summary, each at the 2,000-character field cap, beside 24 short rows). A populate-check asserts 12,000 characters cuts this shape; the test then asserts all 30 markers appear in `build_synth_messages`'s user message.
- `test_block_cap_is_the_fix_round_value`.
- Mutation: the constant set back to 12,000 gives `2 failed, 7 passed`; restored, `9 passed`.

Offline reconstruction, the adversary's own synthetic shape (15 paper titles and 15 abstracts, rendered by the branch's `render_findings_block`; script `<scratchpad>/probe_block_caps.py`):

| Abstract length | Findings rendered at 12,000 | At 18,000 |
|-----------------|-----------------------------|-----------|
| 1,000 | 21 | 30 |
| 1,200 | 18 | 27 |
| 1,300 | 17 | 25 |
| 1,400 | 15 | 23 |
| 1,500 | 15 | 22 |
| 1,800 | 13 | 19 |
| 2,000 | 11 | 17 |

Stated plainly, since this is where the acceptance is tight: at 18,000 a prompt of 15 abstracts of 1,500 characters renders 22, not more than 22; it passes 22 at 1,400 characters or shorter. That shape cannot occur on the live path today, since no question fetches more than 5 PubMed abstracts. The shape that can occur, 6 values at the 2,000-character cap among 30, renders all 30 at 18,000 and 25 at 12,000 (the unit test above).

Live run 1 of 12, `What research papers discuss BRCA1?`, researcher depth, $0.0172, 31.1 s, outcome `ask`, 58 citations (log: `<scratchpad>/live1_papers.log`, script `fix_round_live_run.py` in this folder). Both Synth calls were handed 30 findings and rendered all 30, in a 1,010-character block, at 12,000 and at 18,000 alike. Every one of the 30 was a short graph `curie` row, so this question, the one builder A used as T-8.1-02's evidence, never puts an abstract in front of the model at all; its "58 sources" are the code-built listing. This confirms F-8.1-A08's point that the earlier evidence could not show the block cap either way, and it is why the proof for this item is the offline shape above rather than this run.

## Item 3: the MedGen clinical features path

Findings: F-8.1-A11, A12, J09, J10, J11, J13, J14, A03, A04, A10.

What the person asking "What phenotypic features are associated with Marfan syndrome?" should now get: the writing model's own sentences naming the features, each with a MedGen chip, and below them the disease listed by its name with every feature MedGen lists beneath it, the count stated whenever the list is cut.

### What changed, property by property

a. One citable finding per feature (F-8.1-A11). `core/graph.py` `_with_medgen_clinical_feature_rows` replaces the joined string: behind each admitted MedGen title row it adds one row per feature, `source_url` the disease's MedGen record, the feature's name first under `clinical_features` so it is the cited value. `_BREADTH_FIELDS_BY_PURPOSE["medgen_summary"]` is back to title, definition and semantic type. The grounding gate is untouched; a sentence naming one feature now contains its own finding's value.

b. The cap covers the real list (F-8.1-J09). `tools/ncbi_eutils_actions.py` `MAX_CLINICAL_FEATURES` is 100 (was 30; Marfan syndrome lists 70). The parser also returns `clinical_features_total`, every distinct feature counted, so whenever any cap cuts (this one, the 100-finding display cap or the byte ceiling) the listing heading reads "Clinical features MedGen lists for Marfan syndrome (56 of 70 shown)".

c. NCBI text is data (F-8.1-J10, J14, A03). `clean_clinical_feature_name` turns every non-printable character (newline, tab, control characters, U+202E, U+200B) into a space, collapses whitespace and cuts at 120 characters; `is_hpo_id` accepts only `HP:` plus seven ASCII digits, by `fullmatch` with `re.ASCII` (a `^...$` with `\d` would accept a trailing newline and any Unicode digit). A failing id is dropped and the name kept. `core/graph.py` applies both again on the way into a row. Repeated names are kept once.

d. "Could not read" is never "has none" (F-8.1-J11). The parser returns None for a non-string or blank blob, a DOCTYPE or ENTITY marker, or a parse error; `summary()` then sets neither key. Only a blob that parsed with no `ClinicalFeature` gives `([], 0)`, and only that record gets one row reading "MedGen lists no clinical features for" followed by the disease's own title.

e. The listing keeps the disease's name (F-8.1-A04, J13, A10). `synthesis/findings.py` removes T-8.1-06c's `_PREFERRED_LISTING_FIELDS`: clinical feature findings take no part in `one_finding_per_record`, so a MedGen record's entry is its title. `_listing_order` puts each record's features directly behind its entry in the code-built narrative. `core/graph.py` `_answer_tokens` renders them under their own heading naming the disease: at researcher depth a table ("Clinical feature", "Identifier" holding the HPO id) directly beneath the group that lists the disease; in plain language a list beneath the one "Where this answer comes from" list. The "lists none" row shows as its own line naming the disease. A new `_clinical_feature_row` looks up a feature's own row by call, URL and value, because `_row_fields_for` returns the first URL match, the title row, for every feature.

f. The features reach the researcher prompt (F-8.1-A12). `synthesis/findings.py` `reserve_prompt_slots` moves named findings inside the prompt window and renumbers densely (`ref_index` and the `citation_id` suffix together, as `drop_placeholder_condition_findings` does). It is a no-op when they already fit. `core/graph.py` calls it before the prompt slice with `_anchor_disease_prompt_reservation`: the MedGen record's title plus up to `_ANCHOR_FEATURE_PROMPT_SLOTS = 10` features. They go right after the leading run of the question's own answer rows, ahead of long context values such as abstracts, which the character-capped block would cut first.

Why 10:

- It equals `_LEAD_FINDINGS_QUOTA`, the slots the question's own graph rows are guaranteed; with 11 reserved, 19 remain, so those 10 still land in the prompt.
- It is twice the five features card 1 asks for, so a few stripped sentences cannot take the answer below five.
- It stays well under the measured record sizes (70, 57, 31), so the prompt never turns into a feature list with the graph answer squeezed out. The listing carries all of them.

The condition "the anchor is a disease with clinical features" is read off the findings, not the question's wording: clinical feature findings exist only on the `medgen_summary` call, which `breadth_plan.plan_disease_search` plans by the resolved disease's own concept id.

g. Builder C's XML hardening is kept: any DOCTYPE or ENTITY marker is rejected before `ElementTree` sees the blob (now returning None, "could not read"), and stdlib `ElementTree` resolves no external entities. No new dependency.

h. Added after live runs 3 and 4 showed researcher prose still failing (see "Runs 3 and 4" below): `synthesis/findings.py` `build_clinical_features_directive`, a dynamic-suffix line present only when feature findings are in the prompt, naming them by marker and giving the one sentence shape the exact gate accepts for them. `NO_CLINICAL_FEATURES_PREFIX` is shared with `core/graph.py` so the "lists none" finding is not mistaken for a feature.

Not changed: `tools/ncbi_efetch_schemas.py` and `harness/coordinator_worker.py` (a feature row is well inside the coordinator's per-string, list and byte bounds; the byte ceiling, if a query ever carried five records of 100 features, would cut rows and the heading's "N of M" would say so). `synthesis/grounding.py` and `synthesis/trust.py` untouched.

What a reader will also notice: every feature is its own citation, so the sources list carries one MedGen entry per feature (83 citations on the Marfan answers). The trust line counts sources by database, so it is not inflated.

### Unit tests for every property

- `tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py`: the whole 70-feature list kept, 150 capped at 100 with total 150, read-and-empty gives `[]` and 0, DOCTYPE and an HTML entity set neither key, None for non-string, blank and malformed input, billion laughs rejected, eight bad HPO ids (wrong case, letters, six and eight digits, round 1's injection payload, a 20,000-character id, Arabic-Indic digits, a leading space) dropped with the name kept, a trailing newline rejected by `is_hpo_id`, a newline, tab, U+202E and U+200B in a name collapsed to one printable line, duplicates kept once.
- `tests/system_03_search_agent/core/test_disease_breadth.py`: one row per feature behind the title with its fields; the "lists none" row names the disease; an unreadable record gets no feature row and no statement; several records interleave; a hostile list cannot forge a finding line or carry a bad id into the prompt; four natural sentences ground against their own feature findings under the unchanged gate (including three features in one sentence, three claims); a feature under another feature's marker, an invented feature, and a feature under the title's marker are all stripped.
- `tests/system_03_search_agent/synthesis/test_listing_one_row_per_record.py`: the record's entry is its title even when a feature is numbered first; the "lists none" sentence never replaces the name; the narrative lists features beneath their record; orphan features still listed; `reserve_prompt_slots` moves findings after the answer rows, ahead of an abstract, renumbers densely, loses nothing, and is a no-op when everything fits.
- `tests/system_03_search_agent/core/test_graph.py`, through `write_node` with round 1's live shape (43 graph rows, a MedGen record of 70): the first Synth prompt carries 30 findings, the title and exactly 10 feature lines, answer rows first; the researcher listing has "Marfan syndrome" as the MedGen entry, a heading "Clinical features MedGen lists for Marfan syndrome (56 of 70 shown)" and a table whose first feature row carries `HP:0000000`; the plain-language listing puts the features beneath the one list.

Mutation checks, each restored from a byte copy afterwards:

- `reserve_prompt_slots` returning its input unchanged: 3 failed (the `write_node` prompt test and two `reserve_prompt_slots` tests).
- Clinical features allowed back into `one_finding_per_record`'s collapse: 2 failed.
- A missing feature list read as an empty one (the J11 defect): 2 failed, including `test_an_unreadable_record_says_nothing_about_features`.

## Tests and lint

On the final tree, 2026-09-25:

- The brief's command, `python3 -m pytest -m "not integration" -q -p no:cacheprovider tests/system_03_search_agent/synthesis tests/system_03_search_agent/core tests/system_03_search_agent/tools tests/system_03_search_agent/harness`: `3398 passed, 142 skipped, 24 deselected, 1 xfailed, 5 warnings in 62.95s`.
- The whole unit suite as `.github/gates/gate04_unit_suite.sh` runs it (`pytest -m "not integration"`): `5382 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 143.45s`.
- `ruff check .` over the whole repository: all checks passed.
- `isort --check-only --filter-files` on every changed Python file: clean (`core/graph.py` is in `pyproject.toml`'s `extend_skip`, as on develop; ruff's I001 covers it).
- The test count went up with this round's new tests, so the tracked count in CLAUDE.md and AGENTS.md is now stale for `tracker/check_doc_drift.py`; that file is outside this round's fence and is the checkpoint's to refresh.

## Live runs

Script: `testing/Developer/reports/2026-09-25_phase_8.1/fix_round_live_run.py` (loads `.env` from the main checkout without printing any value, puts this worktree's `src` first, and asserts the imported module is the worktree's). Logs in the session scratchpad. The session-memory and interaction-capture tracebacks each log shows come from running as an anonymous local caller with no owner id; they are the same for every run and do not touch the answer.

11 of the 12 allowed runs used, $0.2198 in total.

| Run | Question | Depth | Code | Outcome | Cost | Time | Features in prose |
|-----|----------|-------|------|---------|------|------|-------------------|
| 1 | What research papers discuss BRCA1? | researcher | item 2 | ask | $0.0172 | 31.1 s | n/a |
| 2 | Marfan phenotypic features | plain language | before directive | answer | $0.0191 | 15.2 s | 10 |
| 3 | Marfan phenotypic features | researcher | before directive | answer | $0.0187 | 16.0 s | 0 |
| 4 | Marfan phenotypic features | researcher | before directive | answer | $0.0188 | 14.3 s | 0 |
| 5 | Marfan phenotypic features | researcher | final | answer | $0.0189 | 12.2 s | 11 |
| 6 | Marfan phenotypic features | researcher | final | answer | $0.0183 | 10.9 s | 11 |
| 7 | Marfan phenotypic features | researcher | final | answer | $0.0187 | 14.1 s | 8 |
| 8 | Marfan phenotypic features | plain language | final | answer | $0.0331 | 55.3 s | 11 |
| 9 | Marfan phenotypic features | plain language | final | answer | $0.0189 | 18.1 s | 11 |
| 10 | Marfan phenotypic features | plain language | final | answer | $0.0194 | 18.7 s | 11 |
| 11 | Which diseases are associated with BRCA1? | researcher | final | ask | $0.0187 | 25.8 s | n/a |

"Marfan phenotypic features" is `What phenotypic features are associated with Marfan syndrome?`. Every feature claim counted cites the disease's MedGen record (`https://www.ncbi.nlm.nih.gov/medgen/44287`), field `clinical_features`.

What a reader of these answers will notice, stated plainly:

- The prose names the first eleven features in MedGen's own order (aortic regurgitation, arachnodactyly, astigmatism, ectopia lentis, ...), not the cardinal ones: aortic root aneurysm, aortic dissection and tall stature sit further down MedGen's list, past the 10 reserved prompt slots. They are in the listing directly below, all 70 of them, and the prose says "MedGen lists these clinical features", not "the features are". Choosing which features matter most would be a ranking decision nothing in the record supports.
- The feature sentences read mechanically ("MedGen lists these clinical features: ..."), three times over in run 7. That is the one shape the unchanged exact gate accepts for these findings.

### Run 2: Marfan, plain language, before the directive

- Prompt: 30 findings handed and rendered (2,528 characters), 11 of them clinical feature lines, the MedGen title among them.
- Prose that survived the gate, word for word:
  - "I found 1 condition, 5 published papers, 1 literature index entry and 5 clinical trials related to Marfan syndrome [11][12][73]...[82]." (the code-built summary sentence)
  - "The features found in the records include aortic regurgitation [1], arachnodactyly [2], astigmatism [3], ectopia lentis [4], esotropia [5], pes planus [6], glaucoma [7], congestive heart failure [8], hypertropia [9], and micrognathia [10]."
- Sentences citing MedGen clinical features: 1, carrying 10 feature claims, every chip `medgen / clinical_features`.
- Listing: "Where this answer comes from" with "Marfan syndrome" as the MedGen entry, then "Clinical features MedGen lists for Marfan syndrome" with all 70 features beneath (no "of" in the heading, since none was cut). 82 citations.

### Runs 3 and 4: Marfan, researcher, before the directive (both fail the prose acceptance)

- Run 3: $0.0187, 16.0 s, outcome `answer`. 11 feature lines reached the prompt. Prose kept: the code-built summary and one quoted abstract sentence ("Marfan syndrome is a multisystem connective tissue disease ... [1]"). Feature sentences in prose: 0. Listing correct (MedGen entry "Marfan syndrome", 70 features beneath).
- Run 4, the same with the grounding pass instrumented: $0.0188, 14.3 s. The model DID name the features in both passes, and the unchanged gate stripped every such sentence, correctly:
  - Pass 1: "Skeletal manifestations include arachnodactyly, characterized by abnormally long fingers and toes, and pes planus, or flat feet [11][26]." Two features under stacked markers, and words no finding holds.
  - Pass 2: "Ectopia lentis is listed among the clinical features [19]." and "Micrognathia is also recorded as a clinical feature [30]." Stripped for "among", "recorded" and the singular "feature", none in the finding, the field name or the question.
- Cause: the researcher depth directive says "Do not restate the records one by one and do not write lists", so the model describes the features in its own words; at plain language depth the same prompt drew "The features found in the records include aortic regurgitation [1], arachnodactyly [2], ..." and all ten grounded.
- Change made in response (`synthesis/findings.py`, `build_clinical_features_directive`, wired into `build_synth_messages` after the plain-description line): a dynamic-suffix line, only when feature findings are in the prompt, naming them by marker and giving the one shape the gate accepts, "MedGen lists these clinical features: first name [N], second name [M] and third name [K]", with placeholder names, plus "do not describe, group or explain a feature in other words, and never gather several markers at the end". It points at content present and at how to cite it, as `build_answer_context_directive` and `build_explanatory_directive` already do; the system block, the depth directives and the gate are unchanged. Tests: the directive names `[2] to [4]` and the shape, it is absent without feature findings and absent from the system block, and the exact shape it asks for grounds 3 of 3 clauses with 0 stripped, both through hand-built findings and through the real row-to-finding pipeline, for a question naming Marfan syndrome and for one that does not.

### Run 5: Marfan, researcher, with the directive (final code), 1 of 3

- $0.0189, 12.2 s, outcome `answer`, 82 citations. 11 feature lines in the prompt.
- Prose that survived, word for word (after the code-built summary sentence):
  - "MedGen lists these clinical features: Aortic regurgitation [1], Arachnodactyly [2] and Astigmatism [3]."
  - "Additional features include Ectopia lentis [4], Esotropia [5] and Exotropia [6]."
  - "Further features are Pes planus [7], Glaucoma [8], Congestive heart failure [9], Hypertropia [10] and Micrognathia [11]."
- Sentences citing MedGen clinical features: 3, carrying 11 feature claims, every chip `medgen / clinical_features`. The model's own heading "Clinical Features from MedGen" was kept.
- What the gate still stripped, correctly: "Skeletal features include arachnodactyly, pes planus, and micrognathia [11][26][30]" (stacked markers) and the category sentences ("Ocular manifestations are prominent, ...").
- Listing: "Medgen records found" with "Marfan syndrome", then "Clinical features MedGen lists for Marfan syndrome" with all 70.

### Run 6: Marfan, researcher, final code, 2 of 3

- $0.0183, 10.9 s, outcome `answer`, 83 citations. 11 feature lines in the prompt.
- Prose (after the summary sentence): "MedGen lists these clinical features: Aortic regurgitation [1], Arachnodactyly [2], Astigmatism [3], Ectopia lentis [4], Esotropia [5], Exotropia [6], Pes planus [7], Glaucoma [8], Congestive heart failure [9], Hypertropia [10] and Micrognathia [11]." and "A comprehensive review notes that the Ghent II Nosology criteria are crucial for diagnosing Marfan syndrome and guiding identification of high-risk patients [12]."
- Sentences citing MedGen clinical features: 1, carrying 11 feature claims, all `medgen / clinical_features`. Model headings kept: "Clinical Features", "Diagnosis and Reviews".
- Listing as in run 5.

### Run 7: Marfan, researcher, final code, 3 of 3

- $0.0187, 14.1 s, outcome `answer`, 83 citations. 11 feature lines in the prompt.
- Prose (after the summary sentence):
  - "Marfan syndrome is a multisystem connective tissue disease with autosomal dominant inheritance, primarily caused by FBN1 gene mutation [1]." (a PubMed abstract)
  - "MedGen lists these clinical features: Aortic regurgitation [2] and Congestive heart failure [3]."
  - "MedGen lists these clinical features: Ectopia lentis [4], Glaucoma [5] and Astigmatism [6]."
  - "MedGen lists these clinical features: Arachnodactyly [7], Pes planus [8] and Micrognathia [9]."
- Sentences citing MedGen clinical features: 3, carrying 8 feature claims, all `medgen / clinical_features`. The model grouped them by body system; the repeated opening reads mechanically, which is the price of the one shape the exact gate accepts.
- Researcher depth result: 3 of 3 runs name at least five features in the model's own prose, each cited to MedGen (11, 11, 8).

### Run 8: Marfan, plain language, final code, 1 of 3

Run 2 was plain language before the directive existed, so the plain-language count restarts here on the final code.

- $0.0331, 55.3 s, outcome `answer`, 84 citations. 11 feature lines in the prompt. The time and cost are the highest of the set; the extra cost is consistent with the reworded-sentence model check the four quoted abstract sentences below go through, and nothing in this round's change adds a model call.
- Prose (after the summary sentence):
  - "MedGen lists these clinical features: Aortic regurgitation [1], Arachnodactyly [2], Astigmatism [3], Ectopia lentis [4], Esotropia [5], Exotropia [6], Pes planus [7], Glaucoma [8], Congestive heart failure [9], Hypertropia [10] and Micrognathia [11]."
  - "Marfan syndrome is a condition that affects connective tissue throughout the body and is passed down through families [12]." and three more sentences from two PubMed abstracts.
- Sentences citing MedGen clinical features: 1, carrying 11 feature claims, all `medgen / clinical_features`.
- Listing: "Where this answer comes from" with the "Marfan syndrome" entry, then "Clinical features MedGen lists for Marfan syndrome" with all 70.

### Run 9: Marfan, plain language, final code, 2 of 3

- $0.0189, 18.1 s, outcome `answer`, 83 citations. 11 feature lines in the prompt.
- Prose (after the summary sentence): three sentences from a PubMed abstract ("Marfan syndrome is a connective tissue disease that affects multiple parts of the body and is passed down through families [1]." and two more), then "MedGen lists these clinical features: Aortic regurgitation [2], Arachnodactyly [3], Astigmatism [4], Ectopia lentis [5], Esotropia [6], Exotropia [7], Pes planus [8], Glaucoma [9], Congestive heart failure [10], Hypertropia [11] and Micrognathia [12].", then "One titled Marfan syndrome [13], and one titled Marfan syndrome [14]." (a pre-existing plain-language restatement of two paper titles, not from this change).
- Sentences citing MedGen clinical features: 1, carrying 11 feature claims, all `medgen / clinical_features`.
- Listing as in run 8.

### Run 10: Marfan, plain language, final code, 3 of 3

- $0.0194, 18.7 s, outcome `answer`, 83 citations. 11 feature lines in the prompt.
- Prose (after the summary sentence): three sentences from a PubMed abstract ("Marfan syndrome is a connective tissue disease that can affect many parts of the body, ... [1]." and two more), then "MedGen lists these clinical features: Aortic regurgitation [2], Arachnodactyly [3], Astigmatism [4], Ectopia lentis [5], Esotropia [6], Exotropia [7], Pes planus [8], Glaucoma [9], Congestive heart failure [10], Hypertropia [11] and Micrognathia [12]."
- Sentences citing MedGen clinical features: 1, carrying 11 feature claims, all `medgen / clinical_features`.
- Plain language result: 3 of 3 runs on the final code name at least five features in the model's own prose, each cited to MedGen (11, 11, 11). Run 2, before the directive, also named 10.

### Run 11: the gene question answers as before

`Which diseases are associated with BRCA1?`, researcher depth, final code: $0.0187, 25.8 s, outcome `ask`, 23 citations, prompt 30 findings in a 3,233-character block, 0 clinical feature lines.

- Opening: "Found 4 disease records for BRCA1: Familial cancer of breast [3], Familial breast-ovarian cancer susceptibility 1 [4], Pancreatic cancer susceptibility 4 [5] and Fanconi anemia complementation group S [6]." The same four diseases in the same order as the develop-shape answer round 1 recorded (F-8.1-A14: "Found 4 disease records for BRCA1: Familial cancer of breast [2], ..."), and the same `ask` outcome that run published.
- Model prose kept: "Recent publications have explored BRCA1 deficiency as a therapeutic target, including sensitization to PARP inhibitors through ferroptosis modulation [2]."
- Listing: Disease, Gene, PubMed, ClinVar, OMIM and trial tables. No MedGen summary call is planned for a gene question, so no clinical feature row, heading or directive appears, and `reserve_prompt_slots` is a no-op.
- The Gene and OMIM tables each show their record twice ("BRCA1 | NCBIGene:672" twice). This round's listing changes touch only findings whose field is `clinical_features`, so the doubling is not from this change; recorded here for the lead rather than investigated, since it is outside this round's work list.
