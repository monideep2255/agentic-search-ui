# Answer quality report, 2026-09-14

Fixer: the answer-quality sub-agent, working alone on `develop` at `537377d`, nothing committed. Findings were written the moment they were established, so the log reads in the order the work happened. Beside this file: the exact synthesis messages captured before and after (`before_*.json`, `after1_*.json`), every measurement run as one JSON line (`n_*.jsonl`, `m_*.jsonl`), the rendered `live_run_table.md`, the probes of the Synth tier's reasoning (`probe_effort_none.txt`, `probe_low_new_directive.txt`), and the scripts that produced all of it.

## Table of contents

- [Summary](#summary)
- [What the writer was given before any change](#what-the-writer-was-given-before-any-change)
- [Findings log](#findings-log)
- [The change and why](#the-change-and-why)
- [The write-step transient error](#the-write-step-transient-error)
- [Files changed](#files-changed)
- [Tests whose requirement changed](#tests-whose-requirement-changed)
- [Verify commands](#verify-commands)
- [Live-run table](#live-run-table)
- [Proposed DECISIONS.md rows](#proposed-decisionsmd-rows)
- [Left open](#left-open)
- [Full suite result](#full-suite-result)

## Summary

- Defect 1 (diseases not in the prose, trials first): fixed. Every one of 10 BRCA1 disease runs, in both modes, opens "Found 4 disease records for BRCA1: Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] and Fanconi anemia complementation group S [4]." and the model's own disease prose follows it, with trials after.
- Defect 2 (Researcher restatements, "has a source URL of"): fixed. Every GCK, CFTR, BRCA1-variants and EGFR Researcher run opens on a cited count ("Found 13 sequence variant records for GCK, of 1333 available [1]...[13]."), no prose sentence restates a listed record, and no sentence anywhere reads "has a source URL of" (measured on every run; the URL never reaches the model now).
- Defect 3 (write-step transient error, added mid-task): cause found by execution, and it is NOT output length. At reasoning effort "low" the Synth model intermittently spends its whole 4000-token ceiling on reasoning, returns `finish_reason: length` with empty or truncated content, and takes 20 to 45 seconds doing it. Reproduced locally once in 55 runs (EGFR run 3: first Synth call killed at 45.0 seconds, `write/transient`, no done event) and 2 of 6 in a direct probe. At effort "none" the same prompt finished 6 of 6 in 5.2 to 7.2 seconds with no reasoning tokens. The dial is `_TIER_REASONING["synth"]` in `harness/harness.py`, outside this fix's files, so this is a BLOCKED-STOP with the numbers below rather than a change. The length ask was shortened anyway (the coordinator's allowed fix 1), and it cut the ordinary first Synth call from 5 to 14 seconds to 2 to 5.
- Unchanged, measured on every run: one source set per question, identical between `plain_language` and `researcher`, identical to the pre-change captures (BRCA1: the same 11 ids; GCK: the same 20 ids); every claim and list row carries a marker; no raw `MedGen:C` code in answer words; the BRCA9 refusal path is untouched (its tests still pass).

## What the writer was given before any change

Captured live by wrapping `core.graph._dispatch_tier_call` and recording every Synth call's messages and reply (`capture_synth.py`). Preflight was READY.

### "Which diseases are associated with BRCA1?", `plain_language`

The findings block, verbatim, in the order `act_node` hands findings to the coordinator (Layer 2, Layer 3, Layer 1):

```
[1] gene symbol: BRCA1
[2] Literature entity name: BRCA1
[3] Clinical trial name: Germline BRCA1 and BRCA2 Mutations in Jewish Women Affected by Breast Cancer
[4] Clinical trial name: BRCA1 Haploinsufficiency and Gene Expression
[5] Clinical trial name: Study to Evaluate Treatment Customized According to RAP80 and BRCA1 in Patients With Advanced Lung Carcinoma
[6] Clinical trial name: Letrozole in Preventing Breast Cancer in Postmenopausal Women With a BRCA1 or BRCA2 Mutation
[7] Clinical trial name: Recombinant Human Chorionic Gonadotropin in Preventing Breast Cancer in Premenopausal Women With BRCA1 Mutations
[8] Disease name: Familial cancer of breast
[9] Disease name: Familial breast-ovarian cancer susceptibility 1
[10] Disease name: Pancreatic cancer susceptibility 4
[11] Disease name: Fanconi anemia complementation group S
```

Nothing in the prompt says which of the eleven answer the question, and the four diseases are last.

The model's first reply (trimmed) did open on the diseases:

> BRCA1 is a gene linked to several diseases, including a condition called Familial cancer of breast [8]. It is also associated with Familial breast-ovarian cancer susceptibility 1 [9]. Another disease tied to BRCA1 is Pancreatic cancer susceptibility 4 [10]. ...

Every one of those sentences was stripped by the grounding gate, correctly under its own rule: "gene", "several", "including", "condition", "called", "another", "tied", "further", "known" appear in no finding and not in the open part of the question. The second sentence grounds on its own but opens on "It" after a dropped predecessor, so item 9.7's pronoun rule drops it too. Paragraphs two and three were explanation and were stripped whole (F9-04). The first reply grounded zero claims.

The completeness correction then listed all eleven as omitted, `[1]` and `[2]` first, and the repair reply opened:

> BRCA1 is a gene symbol and a literature entity name [1][2]. The diseases associated with BRCA1 are Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S [8][9][10][11].

The second sentence packs four values under four trailing markers, so the clause before `[8]` must ground against finding 8 alone and fails on the other three names; the segments before `[9]`, `[10]` and `[11]` are empty. Zero claims again, so the structured fallback shipped the eleven record lines in prompt order: gene symbol, literature entity, five trials, then the diseases, plus the "could not be verified" note. That is the product owner's screenshot.

### "Variants in GCK causing MODY", `researcher`

The findings block (trimmed to the shapes that matter):

```
[1] gene symbol: GCK
[2] Literature entity name: Gck
[3] Clinical trial name: A Study of LY2599506 (Oral Agent Medication: Glucokinase Activator 1) in Type 2 Diabetes Mellitus
... [4] to [7], four more trials ...
[8] SequenceVariant ClinVar:1028584, name: NM_000162.5(GCK):c.415A>T (p.Met139Leu)
... [9] to [15], seven more named variants ...
[16] SequenceVariant ClinVar:1179956, source_url: https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956
[17] SequenceVariant ClinVar:1187444, name: NM_000162.5(GCK):c.434C>T (p.Pro145Leu)
[18] SequenceVariant ClinVar:1188508, source_url: https://www.ncbi.nlm.nih.gov/clinvar/variation/1188508
[19] SequenceVariant ClinVar:1190030, source_url: https://www.ncbi.nlm.nih.gov/clinvar/variation/1190030
[20] SequenceVariant ClinVar:1190681, source_url: https://www.ncbi.nlm.nih.gov/clinvar/variation/1190681
```

Four findings were offered with a URL as their claim value. `render_findings_block` withholds `source_url` from the prompt on purpose ("a URL in the prompt is a URL the model can copy into prose as if it were a fact it verified"), and that intent was defeated one field over: `_pick_representative_field` returned `source_url` as the representative FIELD for an intronic HGVS name, so the URL arrived as `field_value`. The model did what the prompt asked and wrote "The variant ClinVar:1179956 is listed with its source URL at https://... [16]", which is the "has a source URL of" sentence.

The model's prose was the requested shape (summary paragraph, six `##` headings, mechanistic detail) and almost all of it was stripped: every mechanistic sentence adds words no record carries. What survived the first reply were five one-record restatements of the trials ("The clinical trial named X [3]."), and the repair's survivors had the same shape. The listing then repeated the same records under "Clinical trial records found" and "Sequence variant records found". No summary paragraph survived because none can: "Glucokinase (GCK) is a key glycolytic enzyme ..." is in no finding.

The premise established from both captures: the writer was given nothing that says which findings answer the question, and the gate cannot let a model-written summary through. So the summary and the answer-first order are code-built and deterministic.

## Findings log

- AQ-01 (capture). Set 8's Layer 2, Layer 3, Layer 1 handoff order is also the PROMPT order, the FALLBACK order and the TAIL order, so when the model's prose grounds nothing the record lines open on the gene symbol and the trials. Admission to the 20-slot cap and presentation order were one thing; they are now two (`build_synth_findings(lead_call_ids=...)`).
- AQ-02 (capture). For the plain-language BRCA1 question the model's own first sentence named a disease and the gate stripped it for ordinary explanatory words. A first sentence that names a disease cannot be promised by prompt wording alone under the gate as written (F9-04), so it is built in code from the answer findings (`answer_layout.answer_summary_sentence`).
- AQ-03 (capture). The completeness correction lists omitted findings in prompt order and said nothing about keeping the answer first; the repair reply opened on the gene symbol and literature entity. The correction now says to keep the answer to the question in the first sentence.
- AQ-04 (capture). A URL reached the model as a finding's `field_value` for four GCK variants and two CFTR variants (set 9 follow-up) through `_pick_representative_field` choosing `source_url` when the artifact check flags an intronic HGVS name. Fixed in `synthesis/findings.py` by treating a URL-shaped value as degenerate, which routes the row to the existing CURIE fallback, without touching `_is_vocabulary_token_artifact`. F-2.1-B07's reason still holds for Layer 1 disease names, and the list cell still reads the HGVS name through `record_label`.
- AQ-05 (first live run after the change). My first cut of `record_label` skipped any label field the row's `vocabulary_artifact_fields` list flags, to keep "MeSH" out of a list. Measured live on GCK it listed "ClinVar:1179956" in place of "NM_000162.5(GCK):c.363+318G>A", because that list flags exactly the HGVS names the label exists to show. Reverted within the hour; `record_label` prefers a resolved title on the finding and otherwise shows the row's own name verbatim, as set 9 built it. Recorded rather than tidied away: the artifact list is not a usable label filter.
- AQ-06 (coordinator, added to scope mid-task). Write-step transient error on develop: 3 of 25 Researcher runs died at 49 to 53 seconds with `scope: step, source: write, error_class: transient` and no done event. Full account in the section below.
- AQ-07 (live, BRCA1 and BRCA2). The summary said "for BRCA1" on a two-gene question because it read `next_step_entity_label`, the first target's mention. It now names every mention Think resolved this turn ("BRCA1 and BRCA2").
- AQ-08 (live, BRCA1 and BRCA2). "Gene records found" appeared twice as a listing heading: the graph's rows carry `Gene` and `ncbi_efetch`'s carry `gene`. The listing now groups by the plain noun.
- AQ-09 (live). Two GCK runs in ten refused with the unresolved-symbol refusal ("NCBI has no record matching the name ... term=GCK") with no tool having run, one under four parallel measurement streams and one in a serial rerun with nothing else running, so it is not my load. `think_node`'s live symbol lookup for GCK returned nothing on those runs. Think-side and outside this fix's files; set 8 recorded the same question resolving nothing on 2 of 5 runs for a different reason (the model returning no entity). Left open.
- AQ-10 (live). One BRCA1-variants run in the pre-change measurement died at 50.9 seconds in the PLAN step (`source: plan`, transient), not the write step. The plan tier already runs at effort "none"; that one is a provider latency spike on the plan model and is outside this fix.

## The change and why

Order of work, as the brief asked: print the input, then the smallest deterministic change that makes the right answer the natural one, then measure.

1. Answer findings are numbered first, admission unchanged (`synthesis/findings.py`, `build_synth_findings(lead_call_ids=...)`). Which rows get through the 20-slot cap is still decided by set 8's handoff order, so the source set of a question is what it was (the same 11 ids for BRCA1, the same 20 for GCK, before and after, in both modes). Once admitted, the findings from the calls that answer the question's own shape are numbered `[1]` onward by a stable sort. The answer calls are the planned graph call (whose template `plan_node` chose from the question's shape), plus `clinicaltrials_search` when the question mentions trials (`_answer_call_ids`, `core/graph.py`). `SynthFinding` gains a local `call_id` field for this; it is not on the wire schema.
2. A per-query line in the dynamic suffix says which findings answer and which are context (`build_answer_context_directive`), directly under the findings block and above the question. The stable prefix is unchanged, proven by SHA-256 in a test. The completeness correction now also says to keep the answer in the first sentence.
3. A code-built, cited summary sentence opens every answer in both modes (`answer_layout.answer_summary_sentence`, emitted first by `_answer_tokens`). It is retrieval bookkeeping in the same class as the truncation note and the listing headings: the count of answer records the answer cites, the records' own type nouns, the subject the plan resolved, the graph's own `total_available` when the result was truncated, and up to six names inline, each a finding's value as stored beside that finding's marker. It is not run through the grounding pass, which is written for MODEL prose and would reject its own count; it is built only from values the pass already accepted (every record it names has a display slot) and it cites every record it counts, so its `marker_ids` are the citation ids of those records. It is None when no answer finding was cited, so it can never open a refusal.
4. In Researcher, a prose sentence that only restates one listed record is dropped before the list is built (`answer_layout.is_record_restatement`, `drop_record_restatements`). Deterministic: the sentence cites exactly one finding and every content token in it is already in that record's own rendering (value, field, CURIE, type, type noun), using the gate's own tokenizer. A sentence that relates the record to the question's subject ("BRCA1 is associated with Familial cancer of breast [1]") carries words from the question and is kept. Only sentences are removed, survivors are renumbered, and if the listing then grounds nothing the pre-drop prose is put back, so the change can only ever remove a duplicate. Plain language has no list, so it keeps its restatements.
5. A URL is never offered as a claim value (`_URL_VALUE` in `findings.py`, one more degenerate shape in `_citable_value_for_row`). The row takes the existing CURIE fallback, "SequenceVariant record ClinVar:1179956", the same treatment as a MeSH artifact, and the list cell still shows the HGVS name from the row. The intronic-name misfire in `_is_vocabulary_token_artifact` is untouched and is pinned as a populate-check so the guard's reason is re-measured if that ever changes.
6. The depth directives ask for what the answer keeps: Researcher about 200 words (a summary paragraph and two to four short sections, told the records are listed by the system), Plain language about 120 in three short paragraphs. Register, length and shape only, as before. Measured: first Synth calls 1.9 to 5.0 seconds for 130 to 310 words on ordinary calls, against 5 to 14 seconds for 300 to 740 words before.

What was deliberately not done: the grounding gate is unchanged in meaning (containment, never fuzzy); `_is_vocabulary_token_artifact` is unchanged; no cap, timeout, model tier or reasoning effort was changed; `act_node`'s handoff order is unchanged; the stable prefix is unchanged; the frontend is unchanged (the summary is an ordinary `claim` token with `marker_ids`, the rest is existing kinds).

## The write-step transient error

Measured, in order:

- Before the directive change (`m_*.jsonl`, 10 Researcher runs of the two develop questions): 9 completed; first Synth call 4.8 to 23.5 seconds for 300 to 740 words, repair 5.4 to 13.8 seconds; write step 12 to 31 seconds against the 45-second budget. Provider speed varied three to five fold between calls of similar length (317 words in 23.5 seconds beside 548 in 5.6). One run died at 50.9 seconds in the plan step (AQ-10).
- After the directive change (`n_*.jsonl`, 55 runs across seven questions and both depths): 52 answered, 2 refused in Think (AQ-09), and ONE died at the write step: EGFR run 3, first Synth call killed at 45.0 seconds, `write/transient`, no done event. That is the develop failure reproduced locally. Four other calls returned ZERO words after 14.9 to 36.8 seconds without failing the run (CFTR run 3, BRCA1 researcher run 1's repair, BRCA1 and BRCA2 plain run 4 twice).
- The probe (`probe_synth.py`, six direct `call_tier("synth")` calls on the captured GCK prompt, everything else identical): at the configured effort "low" on the OLD prompt, 2 of 6 calls spent 3773 and 3081 of the 4000-token ceiling on REASONING (14949 and 12174 reasoning characters), returned `finish_reason: length` with 0 and 225 words of content, and took 20.0 and 39.9 seconds; the other 4 used 95 to 545 reasoning tokens, returned 542 to 667 words, and took 7.1 to 10.2 seconds. With `_TIER_REASONING["synth"]` patched to effort "none" inside the probe process only, 6 of 6 calls finished in 5.2 to 7.2 seconds, `finish_reason: stop`, no reasoning tokens, 588 to 675 words (`probe_effort_none.txt`). On the NEW shortened prompt at effort "low", 6 of 6 finished in 2.9 to 3.9 seconds with 222 to 1106 reasoning characters (`probe_low_new_directive.txt`), yet the EGFR run above died under that same directive, so the shorter ask lowers the odds and does not remove the runaway.

So the cause is the Synth tier's reasoning runaway, not the length ask: a call that spends its token ceiling reasoning produces nothing useful and, on develop's slower route, reaches the 45-second step budget. Only the first Synth call can be fatal; the repair's timeout is swallowed as best-effort. The empty-content replies are handled (the grounding pass refuses, the structured fallback lists the records), which is why four of the five long calls did not fail the run.

BLOCKED-STOP on this item. The fix that removes the cause is `_TIER_REASONING["synth"] = {"effort": "none"}` in `harness/harness.py`, and that file is outside this fix's allowed list. Reasons it is the right fix rather than a cap change, for the product owner: the plan tier already runs at "none" on the same measured argument (its comment: effort "high" 163 seconds total, effort "none" 6.1); the Synth tier's reasoning buys prose the gate strips (F9-04); and it changes no cap, timeout, tier or model. Raising the 45-second budget or the 4000-token ceiling would make the runaway calls slower and more expensive, not rarer.

Done-when for this defect as stated (10 consecutive local runs, 0 write-step errors): the two develop questions answered 10 of 10 in Plain language and 10 of 10 in Researcher after the change (the only write-step death was on EGFR). Across all 55 runs one write-step error. Worst first Synth call 45.0 seconds (that run), worst completed first call 36.8 seconds (CFTR run 3, zero words), so the step does NOT sit well under 45 seconds at effort "low" and I am not claiming it does.

## Files changed

Backend:
- `src/system_03_search_agent/synthesis/findings.py`: `SynthFinding.call_id`; `_URL_VALUE` and the `is_url` degenerate shape; `build_synth_findings(lead_call_ids=...)` (admission first, then the stable sort, then numbering); `_marker_span` and `build_answer_context_directive`; `build_synth_messages(answer_ref_indices=...)`; the completeness correction's first-sentence rule; the `plain_language` and `researcher` directives.
- `src/system_03_search_agent/synthesis/answer_layout.py`: `record_label` prefers a resolved title; `is_record_restatement`, `drop_record_restatements`, `MAX_SUMMARY_NAMES`, `summary_label`, `answer_summary_sentence`. Imports `entity_type_noun` from `core/next_step.py`, a leaf module with no project imports.
- `src/system_03_search_agent/core/graph.py`, write side only: `_summary_subject`, `_row_for`, `_answer_call_ids`, `_TRIALS_QUESTION_WORDS`; `write_node` computes the answer call ids, passes `lead_call_ids` and `answer_ref_indices` to both Synth calls, drops restatements in Researcher before the listing (with the put-back guard), and builds the summary; `_answer_tokens` takes `summary_sentence` and groups the listing by noun.

Tests, new:
- `tests/system_03_search_agent/synthesis/test_answer_quality.py` (27 arms): the URL guard with its populate-check and mutation; lead ordering with the admitted set proven identical under a cap; the directive line, its empty cases and the byte-identical prefix; restatement detection over six shapes; the drop with renumbering, the all-dropped case, the mutation, and the hand-built result; the summary's inline, count, cited-only, mixed and single shapes; the intronic-row label; the resolved-title label; the directive word-ask regression (mutation-proven by raising the ask to 7200: red, file restored byte-identical).
- `tests/system_03_search_agent/core/test_write_answer_quality.py` (16 arms): the real `write_node` over a three-call state in set 8's handoff order with the prompt recorded; the prompt leads with the answer findings and carries the line; the mutation restoring the handoff order; the first sentence names a disease and trials follow, in both modes; both modes cite the prepared set; Researcher drops restatements and keeps a cited summary and the list, with the identity mutation putting them back; Plain language keeps them; a trials question counts trials as answer records; no URL reaches the prompt for the intronic row; the summary mutation; the two-gene subject; one heading per noun; the wiring check.

Tests changed, each a requirement change named below: `core/test_write_answer_structure.py`, `core/test_write_findings_tail.py`, `core/test_write_completeness.py`.

Not changed: `frontend/`, `_is_vocabulary_token_artifact`, `_pick_representative_field`, `grounding.py`, `harness/`, `act_node`, any cap or timeout.

## Tests whose requirement changed

- `test_write_answer_structure.py`: the fixture reply was pure restatements of the finding bodies, which a Researcher answer now drops for the list. The reply now relates each record to the question's subject ("NCBIGene:672 is associated with ..."), and the first-claim arm asserts the summary first, then the model's bolded prose.
- `test_write_findings_tail.py::test_the_note_precedes_the_tail_and_carries_no_marker`: the first token is now the summary, which cites every answer record; the arm asserts that and pins the model's own markers from token 1.
- `test_write_completeness.py::test_a_repair_that_drops_a_reported_finding_is_discarded`: the summary legitimately names "disease name number 3" before the tail note; the leak check now covers the prose region between the summary's paragraph and the note.
- One placeholder arm I wrote and then deleted (a bare `pass`) is recorded here because an arm that cannot fail is not an arm.

## Verify commands

Each on its own exit code, never piped, from the repository root.

- `python -m pytest tests/system_03_search_agent -q -p no:cacheprovider`: the result line is appended at the end of this file (the full suite ran after the live measurement so the timings above were not contended).
- Focused, green: `synthesis/` 274 existing plus the 27 new; `core/test_write_answer_quality.py` 16; `core/test_write_answer_structure.py`, `test_write_findings_tail.py`, `test_write_completeness.py`, `test_personalization_premise.py`, `test_layer_handoff.py` (except its shared-machine timing arm) all pass; the core, synthesis, contracts and eval directories: 590 passed, 48 skipped before the last test edit, then green on re-run of the edited files.
- `ruff check .`: exit 0.
- `isort --check-only src tests`: exit 0.
- `python3 tracker/check_doc_drift.py --check`: exit 1, 4 stale, 0 structural: `AGENTS.md:32` and `CLAUDE.md:32` carried a Python test count of 5002 at the time (5044 computed, the 42 added here), and the set 8 report carried 4919 twice. Not edited, per the brief; the two `.md` counts are the main agent's at checkpoint.
- `frontend/`: `npm run build` exit 0; `npx vitest run` exit 0, 41 files, 410 passed. Playwright not run: no frontend file was touched.
- `python3 tracker/preflight.py`: READY before every live batch.

## Live-run table

Script: `measure_write.py` (a sibling of `local_loop_run_depth.py` that also times every Synth call and records its reply length), no session memory, real models and graph. Words count prose plus list values with markers removed, notes and headings excluded. "Sources" is the count and a hash of the sorted cited source ids, so equal hashes are equal sets. "Markers ok" is zero unmarked claims. The first four streams ran as four parallel processes; the GCK serial rerun and everything after it ran alone.

Source sets, one per question, identical in both modes and identical to the pre-change captures where one exists:

- BRCA1 diseases (both modes, 10 runs): 11 ids, `672, @GENE_BRCA1, MedGen:C0346153, MedGen:C2676676, MedGen:C3280442, MedGen:C4554406, NCT00590109, NCT00597987, NCT00617656, NCT00673335, NCT00700778`. The pre-change capture cited exactly these 11.
- GCK MODY variants (8 answered runs of 10): 20 ids, `2645, @GENE_GCK`, thirteen ClinVar ids, five NCT ids, exactly the pre-change capture's 20.
- CFTR variants (5 runs): 20 ids. EGFR NSCLC and trials (4 answered of 5): 20 ids. BRCA1 and BRCA2 diseases (both modes, 10 runs): 20 ids. BRCA1 variants (both modes, 10 runs): 20 ids. The full id lists are at the foot of `live_run_table.md`.

| Case | Mode | Run | Outcome | First sentence | Words | Headings | List rows | Sources (hash) | Markers ok | URL sentence | Synth first s / words | Synth repair s / words | Elapsed s | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRCA1 diseases | plain_language | 1 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 163 | 0 | 0 | 11 (b3e4ad3c) | yes | no | 2.0 / 133 | 2.2 / 170 | 8.6 | none |
| BRCA1 diseases | plain_language | 2 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 166 | 0 | 0 | 11 (b3e4ad3c) | yes | no | 13.2 / 139 | 1.9 / 180 | 19.8 | none |
| BRCA1 diseases | plain_language | 3 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 138 | 0 | 0 | 11 (b3e4ad3c) | yes | no | 1.9 / 166 | 2.9 / 169 | 10.4 | none |
| BRCA1 diseases | plain_language | 4 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 136 | 0 | 0 | 11 (b3e4ad3c) | yes | no | 4.1 / 134 | 2.6 / 120 | 13.2 | none |
| BRCA1 diseases | plain_language | 5 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 133 | 0 | 0 | 11 (b3e4ad3c) | yes | no | 1.9 / 129 | 2.0 / 152 | 7.8 | none |
| BRCA1 diseases | researcher | 1 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 135 | 4 | 11 | 11 (b3e4ad3c) | yes | no | 2.3 / 210 | 26.7 / 0 | 47.4 | none |
| BRCA1 diseases | researcher | 2 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 126 | 4 | 11 | 11 (b3e4ad3c) | yes | no | 3.2 / 184 | 2.6 / 266 | 9.9 | none |
| BRCA1 diseases | researcher | 3 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 129 | 4 | 11 | 11 (b3e4ad3c) | yes | no | 2.3 / 176 | 2.0 / 178 | 8.0 | none |
| BRCA1 diseases | researcher | 4 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 141 | 4 | 11 | 11 (b3e4ad3c) | yes | no | 5.0 / 191 | 2.1 / 212 | 16.2 | none |
| BRCA1 diseases | researcher | 5 | ask | Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian canc | 135 | 4 | 11 | 11 (b3e4ad3c) | yes | no | 2.2 / 207 | 2.2 / 184 | 10.6 | none |
| GCK MODY variants | researcher | 1 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 (ede40e50) | yes | no | 2.7 / 195 | 3.2 / 220 | 13.7 | none |
| GCK MODY variants | researcher | 2 | refuse | I could not identify that gene. NCBI has no record matching the name in your question, so  | 23 | 0 | 0 | 0 (e3b0c442) | NO | no | none | none | 8.9 | none |
| GCK MODY variants | researcher | 3 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 (ede40e50) | yes | no | 9.5 / 247 | 7.3 / 211 | 24.2 | none |
| GCK MODY variants | researcher | 4 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 (ede40e50) | yes | no | 5.1 / 247 | 4.4 / 203 | 17.6 | none |
| GCK MODY variants | researcher | 5 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 (ede40e50) | yes | no | 4.1 / 284 | 22.4 / 0 | 40.4 | none |
| GCK MODY variants (serial rerun) | researcher | 1 | refuse | I could not identify that gene. NCBI has no record matching the name in your question, so  | 23 | 0 | 0 | 0 (e3b0c442) | NO | no | none | none | 5.0 | none |
| GCK MODY variants (serial rerun) | researcher | 2 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 114 | 4 | 20 | 20 (ede40e50) | yes | no | 3.5 / 234 | 3.3 / 234 | 17.2 | none |
| GCK MODY variants (serial rerun) | researcher | 3 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 (ede40e50) | yes | no | 4.1 / 221 | 2.2 / 210 | 15.4 | none |
| GCK MODY variants (serial rerun) | researcher | 4 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 (ede40e50) | yes | no | 2.7 / 172 | 4.1 / 288 | 16.2 | none |
| GCK MODY variants (serial rerun) | researcher | 5 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 114 | 4 | 20 | 20 (ede40e50) | yes | no | 3.0 / 174 | 4.1 / 219 | 24.8 | none |
| CFTR variants | researcher | 1 | answer | Found 13 sequence variant records for CFTR, of 6030 available. | 101 | 4 | 20 | 20 (5ca431b6) | yes | no | 11.7 / 233 | 9.0 / 186 | 30.2 | none |
| CFTR variants | researcher | 2 | answer | Found 13 sequence variant records for CFTR, of 6030 available. | 130 | 5 | 20 | 20 (5ca431b6) | yes | no | 13.3 / 182 | 8.5 / 182 | 30.3 | none |
| CFTR variants | researcher | 3 | ask | Found 13 sequence variant records for CFTR, of 6030 available. | 89 | 4 | 20 | 20 (5ca431b6) | yes | no | 36.8 / 0 | 8.2 / ? | 55.2 | none |
| CFTR variants | researcher | 4 | answer | Found 13 sequence variant records for CFTR, of 6030 available. | 89 | 4 | 20 | 20 (5ca431b6) | yes | no | 6.1 / 181 | 7.6 / 274 | 21.5 | none |
| CFTR variants | researcher | 5 | answer | Found 13 sequence variant records for CFTR, of 6030 available. | 113 | 5 | 20 | 20 (5ca431b6) | yes | no | 7.8 / 179 | 7.8 / 208 | 22.6 | none |
| EGFR NSCLC and trials | researcher | 1 | answer | Found 5 clinical trial records and 13 sequence variant records for EGFR, of 3961 available | 93 | 4 | 20 | 20 (375ff71b) | yes | no | 13.0 / 241 | 32.0 / ? | 54.8 | none |
| EGFR NSCLC and trials | researcher | 2 | answer | Found 5 clinical trial records and 13 sequence variant records for EGFR, of 3961 available | 147 | 4 | 20 | 20 (375ff71b) | yes | no | 14.2 / 195 | 17.3 / 325 | 41.1 | none |
| EGFR NSCLC and trials | researcher | 3 | refuse |  | 0 | 0 | 0 | 0 (e3b0c442) | yes | no | 45.0 / ? | none | 54.9 | write/transient |
| EGFR NSCLC and trials | researcher | 4 | answer | Found 5 clinical trial records and 13 sequence variant records for EGFR, of 3961 available | 103 | 5 | 20 | 20 (375ff71b) | yes | no | 10.3 / 242 | 34.7 / ? | 53.7 | none |
| EGFR NSCLC and trials | researcher | 5 | ask | Found 5 clinical trial records and 13 sequence variant records for EGFR, of 3961 available | 93 | 4 | 20 | 20 (375ff71b) | yes | no | 16.1 / 183 | 12.4 / 294 | 37.7 | none |
| BRCA1 and BRCA2 diseases | researcher | 1 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 138 | 4 | 20 | 20 (b279dd6e) | yes | no | 2.9 / 259 | 2.5 / 192 | 26.7 | none |
| BRCA1 and BRCA2 diseases | researcher | 2 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 174 | 4 | 20 | 20 (b279dd6e) | yes | no | 3.4 / 306 | 22.8 / 52 | 38.3 | none |
| BRCA1 and BRCA2 diseases | researcher | 3 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 (b279dd6e) | yes | no | 4.0 / 257 | 2.5 / 252 | 12.4 | none |
| BRCA1 and BRCA2 diseases | researcher | 4 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 262 | 5 | 20 | 20 (b279dd6e) | yes | no | 3.9 / 252 | 2.6 / 337 | 15.5 | none |
| BRCA1 and BRCA2 diseases | researcher | 5 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 157 | 4 | 20 | 20 (b279dd6e) | yes | no | 3.8 / 254 | 28.8 / 236 | 36.6 | none |
| BRCA1 and BRCA2 diseases | plain_language | 1 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 175 | 0 | 0 | 20 (b279dd6e) | yes | no | 9.6 / 229 | 2.9 / 198 | 27.6 | none |
| BRCA1 and BRCA2 diseases | plain_language | 2 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 180 | 0 | 0 | 20 (b279dd6e) | yes | no | 2.8 / 198 | 25.0 / 278 | 52.4 | none |
| BRCA1 and BRCA2 diseases | plain_language | 3 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 173 | 0 | 0 | 20 (b279dd6e) | yes | no | 1.5 / 129 | 1.6 / 180 | 7.5 | none |
| BRCA1 and BRCA2 diseases | plain_language | 4 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 173 | 0 | 0 | 20 (b279dd6e) | yes | no | 14.9 / 0 | 21.3 / 0 | 47.4 | none |
| BRCA1 and BRCA2 diseases | plain_language | 5 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 246 | 0 | 0 | 20 (b279dd6e) | yes | no | 2.1 / 199 | 30.3 / 276 | 44.3 | none |
| BRCA1 variants | researcher | 1 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 119 | 4 | 20 | 20 (0f97a498) | yes | no | 3.7 / 240 | 3.2 / 237 | 34.6 | none |
| BRCA1 variants | researcher | 2 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 159 | 4 | 20 | 20 (0f97a498) | yes | no | 19.3 / 0 | 3.6 / 254 | 43.7 | none |
| BRCA1 variants | researcher | 3 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 99 | 4 | 20 | 20 (0f97a498) | yes | no | 3.6 / 215 | 4.4 / 241 | 21.4 | none |
| BRCA1 variants | researcher | 4 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 114 | 4 | 20 | 20 (0f97a498) | yes | no | 3.4 / 199 | 3.5 / 197 | 26.8 | none |
| BRCA1 variants | researcher | 5 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 115 | 5 | 20 | 20 (0f97a498) | yes | no | 4.4 / 286 | 4.2 / 241 | 22.0 | none |
| BRCA1 variants | plain_language | 1 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 149 | 0 | 0 | 20 (0f97a498) | yes | no | 17.5 / 168 | 3.3 / 196 | 34.8 | none |
| BRCA1 variants | plain_language | 2 | ask | Found 13 sequence variant records for BRCA1, of 15310 available. | 158 | 0 | 0 | 20 (0f97a498) | yes | no | 3.4 / 173 | 2.7 / 181 | 28.5 | none |
| BRCA1 variants | plain_language | 3 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 156 | 0 | 0 | 20 (0f97a498) | yes | no | 6.1 / 214 | 4.7 / 209 | 23.7 | none |
| BRCA1 variants | plain_language | 4 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 145 | 0 | 0 | 20 (0f97a498) | yes | no | 9.6 / 177 | 9.4 / 213 | 25.2 | none |
| BRCA1 variants | plain_language | 5 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 162 | 0 | 0 | 20 (0f97a498) | yes | no | 5.9 / 191 | 2.9 / 191 | 18.8 | none |

Worst first Synth call: 45.0 s. Worst write step (first plus repair): 45.0 s.

Reading the table against the goal contract:

- Goal 1: 10 of 10 BRCA1 disease runs, both modes, open on the four disease names with their markers; the model's prose follows and names diseases (for example "BRCA1 is associated with the disease Familial cancer of breast [1]."), trials come after, and the same 11 sources are cited every run.
- Goal 2: every GCK and CFTR Researcher run that answered opens on the cited count with the truncation total, has zero restatement prose (the list carries the records), and no "source URL" sentence (measured per run as `has_source_url_sentence`). The four intronic GCK variants and the two CFTR ones now list by their HGVS names.
- Goal 3: every answered EGFR run opens "Found 5 clinical trial records and 13 sequence variant records for EGFR, of 3961 available" and lists the five trials under their own heading.
- Goal 4: markers ok on every answered run; no run had a raw `MedGen:C` code in answer words; elapsed 7.5 to 55.2 seconds (the runs over 45 are the runaway-reasoning calls of AQ-06).
- Outcomes read `ask` rather than `answer` on the disease questions because the trust gate's triangulation of a single-origin high-risk claim is unchanged (set 9, F9-18), not because anything here changed.

## Proposed DECISIONS.md rows

In the existing table shape; the main agent appends them.

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-09-14 | AMENDS THE SET 8 ORDERING DECISION: `act_node` still hands findings to the coordinator ordered Layer 2, Layer 3, Layer 1, and that order still decides ADMISSION to the 20-slot cap, but the findings from the calls that answer the question's own shape (the planned graph call, plus the trials call when the question names trials) are NUMBERED FIRST in the prompt, the structured fallback and the findings tail (`build_synth_findings(lead_call_ids=...)`), and a per-query ANSWER / CONTEXT line in the dynamic suffix says which are which | Leave set 8's order as the prompt order; reorder `act_node`'s handoff instead; filter context findings out | <details><summary>why</summary>Measured live on 2026-09-14: the BRCA1 disease prompt listed the four diseases eleventh behind the gene symbol and five trials, nothing said which answered the question, and when the model's prose failed grounding the fallback opened on the gene symbol and the trials, which is the product owner's screenshot. Reordering the handoff would change which rows the cap admits and so the source set; numbering after admission changes the prompt only, so every question keeps the source set it had (the same 11 BRCA1 ids and 20 GCK ids before and after, in both modes). The line is per query, so it lives in the dynamic suffix and the stable prefix is byte-identical, proven by SHA-256.</details> |
| 2026-09-14 | EVERY ANSWER OPENS ON A CODE-BUILT, CITED SUMMARY SENTENCE ("Found 4 disease records for BRCA1: A [1], B [2], C [3] and D [4]." or, past six records, "Found 13 sequence variant records for GCK, of 1333 available [1]...[13]."), built from the answer records the answer cites, their type nouns, the resolved mentions and the graph's own total, and NOT run through the grounding pass | Ask the model for the summary; run the sentence through the gate; cite it to one record | <details><summary>why</summary>The gate cannot let a model-written summary through (F9-04: a summary adds words no record carries), so the plain-language BRCA1 answer opened on stripped prose or on record lines. The sentence is retrieval bookkeeping in the same class as the truncation note and the listing headings, contains only values the gate already accepted, cites every record it counts, and is None when nothing answer-shaped was cited, so it can never open a refusal. Citing it to one record would be dishonest about what supports the count.</details> |
| 2026-09-14 | IN RESEARCHER, A PROSE SENTENCE THAT ONLY RESTATES ONE LISTED RECORD IS DROPPED BEFORE THE LIST IS BUILT (`answer_layout.drop_record_restatements`): the sentence cites exactly one finding and every content token is already in that record's own rendering; survivors are renumbered and the pre-drop prose is put back if the list then grounds nothing | Keep the prose as the gate left it; tell the model not to restate; drop the list instead | <details><summary>why</summary>Measured live on GCK: the only prose that survived was "The clinical trial named X [3]." five times over, and the list under it showed the same five trials. Deterministic containment over the gate's own tokenizer, never a similarity score; only removes, never writes; Plain language has no list so it keeps such sentences. The prompt also asks the model not to restate, but a prompt is a request and the drop is the control.</details> |
| 2026-09-14 | A URL-SHAPED VALUE IS NEVER OFFERED TO THE MODEL AS A FINDING'S CLAIM VALUE (`_citable_value_for_row`, one more degenerate shape routed to the CURIE fallback), and `_is_vocabulary_token_artifact` is unchanged | Fix the intronic-HGVS misfire in `_is_vocabulary_token_artifact`; strip URL sentences after the fact | <details><summary>why</summary>Four GCK and two CFTR variants reached the model as "source_url: https://..." because the artifact check flags an intronic HGVS name and the representative pick fell to the URL, defeating `render_findings_block`'s own reason for withholding URLs. A URL is where a reader verifies, never a fact a row makes, whatever field it sits under; the record's identity is the honest fallback, exactly as for a MeSH artifact, and the list cell still shows the name. Changing the artifact rule for Layer 1 values reopens F-2.1-B07 and was not needed. Stripping after the fact would strip a grounded sentence the model was told to write.</details> |
| 2026-09-14 | THE DEPTH DIRECTIVES ASK FOR WHAT THE ANSWER KEEPS: Researcher about 200 words (a summary paragraph and two to four short sections, the records listed by the system), Plain language about 120 in three short paragraphs | Keep 700 and 250; raise the Synth step budget or token ceiling | <details><summary>why</summary>Set 9 measured 160 to 230 Researcher words surviving a 700-word ask (F9-04), so most of the Synth output time bought text the gate strips; ordinary first Synth calls fell from 5 to 14 seconds to 2 to 5 after the change. It did NOT remove the write-step timeout, whose measured cause is the Synth tier's reasoning runaway at effort "low" (2 of 6 probe calls spent 3081 to 3773 of 4000 tokens reasoning, 20 to 40 seconds, empty or truncated content; 6 of 6 at effort "none" finished in 5 to 7 seconds). That dial is in `harness/harness.py` and is the product owner's decision, recorded as a blocked-stop in the 2026-09-14 answer-quality report.</details> |

## Left open

1. The write-step transient error is understood and NOT fixed: `_TIER_REASONING["synth"]` is "low" and outside this fix's files. Recommended change, measured: effort "none" (probe above). Until then, a run can still die at 45 seconds when the Synth model's reasoning runs to the ceiling; locally 1 of 55 runs, and 2 of 6 direct calls returned empty or truncated content.
2. Two GCK runs in ten refused in `think_node` with the unresolved-symbol refusal, one with nothing else running (AQ-09). The live symbol lookup for GCK intermittently returns nothing; Think-side.
3. One pre-change run died in the plan step at 50.9 seconds (AQ-10), a plan-model latency spike.
4. `testing/Product/Product_workflows.md` line 133 still describes the targets as "about 250 words (Plain language) and a full page (Researcher)"; the asks are now 120 and 200 and the answer opens on a summary sentence. Not in this fix's file list; a one-line copy change for the main agent, with the hand-test expectations for the new opening sentence.
5. `AGENTS.md` and `CLAUDE.md` test counts (5002, computed 5044) are stale by the 42 tests added here; for the checkpoint.
6. The trust outcome on the disease questions is `ask` on every run for the reason set 9 left open (F9-18); unchanged here.
7. The summary's marker run for a count-only sentence ("[1]...[13]") renders as thirteen chips in the web UI, one per record it counts. Honest, and the list below reuses the same numbers; a product-owner look at the density is worth having.
8. The GCK question's structured fallback note ("could not be verified") no longer appears on any run because the summary and list carry the answer; the `ask` floor for a fallback still applies when it fires.

## Full suite result

`python -m pytest tests/system_03_search_agent -q -p no:cacheprovider`: exit 0, 4661 passed, 176 skipped, 1 xfailed, 0 failed, 223 seconds, run alone after the live measurement.
