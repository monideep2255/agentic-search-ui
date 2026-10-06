# Card 56 follow-up: build report, round 3

Builder report for `fix/card56-r3-minimal`, 2026-10-06, cut from develop at fcfc6827. Rounds 1 and 2 failed review (`judge.md`, `adversary.md`, `judge_r2.md`, `adversary_r2.md`). The product owner then chose the smallest safe fix: no retry, no organism matching, no new question asked back, no condition released. This round changes `src/system_03_search_agent/core/graph.py` only, with one new test file, `tests/system_03_search_agent/core/test_think_sra_disease_fallback.py`.

## Table of contents

- [What changed, in the user's words](#what-changed-in-the-users-words)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [Tests](#tests)
- [How develop's behaviour was established](#how-develops-behaviour-was-established)
- [Live runs](#live-runs)
- [Gates](#gates)
- [Spend](#spend)
- [Not covered](#not-covered)

## What changed, in the user's words

On a question that asks for SRA runs or genome assemblies, the app never binds a disease from a word cut out of a longer name. So "SRA runs of SARS-CoV-2" is never answered about the disease SARS. When Think's model misses the organism, the person gets develop's existing question asked back instead ("which gene, variant or condition do you mean?"). Every other question behaves exactly as on develop.

| Part | Now |
|---|---|
| 1. The disease fallback on an SRA or assembly question | When the classifier's record type is "sra" or "assembly", the disease fallback (MedGen by token, decision D3) skips a token that stands in the question only as a piece of a hyphen-joined name: a letter or digit, then a hyphen or dash, on either side of it. "SARS" in "SARS-CoV-2" is skipped, typed with an ASCII hyphen, a Unicode hyphen, a non-breaking hyphen, any other dash, or a minus sign. A whole word still binds: "MODY" in "SRA runs from MODY patients" binds as on develop. The gene-shaped fallback, the candidate list, its cap of three and every other record type are unchanged |
| 2. The parse retry's key list | The message sent after an unusable first reply now lists every key of the Think schema, `record_type` included, read from the schema itself (round 1 judge J-56-04) |
| 3. The narrative-key repair | A reply that wrote "why" for "narrative" beside a `record_type` is now repaired in place instead of refused; the known keys are read from the schema (J-56-04) |

Code, by name: `_is_name_joiner` and `_only_a_piece_of_a_joined_name` beside `_gene_shaped_fallback_candidates`; the `skip_name_pieces` check in the D3 loop of `_think`; `_THINK_RETRY_KEY_LIST` after `_ThinkClassification`; `known_keys` in `_repair_think_narrative_key`. No new question, no retry, no word list, no schema change.

## Choices for the lead to log

| Choice | Alternatives considered | Why |
|---|---|---|
| A token is skipped only when every place it stands in the question is a piece of a joined name | Skip when any one place is a piece | The brief keeps a whole word binding. "SARS and SARS-CoV-2 runs" names SARS whole once, so the person typed it as a word of its own |
| A dash is any Unicode dash punctuation (category Pd) or the minus sign U+2212 | The ASCII hyphen only; a hand-kept list of dash characters | Round 1 judge J-56-06: pasted text carries U+2010 and other dashes. The Unicode category needs no list to keep current |
| The joining character must have a letter or digit on its far side | Any neighbouring dash | "SRA runs - MODY patients" (a spaced dash) does not join MODY to anything, so MODY stays a whole word |
| The skip happens inside the D3 loop, after the cap of three | Filter the candidates before the cap, so a fourth token could take the freed slot | The brief: everything else in D3 unchanged. Letting a fourth token in would try a word develop never tried |
| Key lists read from `_ThinkClassification.model_fields` | Add "record_type" to the two hand-kept lists | One source: a future field cannot be forgotten in one list again |

## Tests

`tests/system_03_search_agent/core/test_think_sra_disease_fallback.py`, 12 tests, drives the real `think_node` with the model reply, NCBI search and summary, and the gene resolver faked. All 12 pass on the branch.

Each mutant was applied to a scratch copy of the branch outside the repository, one line at a time, by `raw/r3/mutate.py`; output in `raw/r3/mutations.txt`. The worktree was never mutated.

| Test | Property | Mutant that turns it red | On develop |
|---|---|---|---|
| `test_sra_question_with_no_entity_binds_no_medgen_record`, 4 cases: ASCII hyphen, U+2010, U+2011, en dash | The SARS-CoV-2 SRA question with an empty extraction binds no MedGen record, asks develop's question back, and still tries the whole word "SRA" | M1 the piece is never skipped (all 4); M3 only the ASCII hyphen joins a name (the 3 Unicode cases); M4 and M6 (the whole word "SRA" no longer tried) | Red: binds the three SARS records |
| `test_assembly_question_with_no_entity_binds_no_medgen_record` | The same for genome assemblies | M1; M2 skipped on SRA questions only | Red |
| `test_a_whole_word_on_an_sra_question_still_binds_as_on_develop` | "SRA runs from MODY patients", empty extraction, still binds MODY | M4 every candidate is skipped on an SRA question; M6 the whole disease fallback is skipped on an SRA question | Passes |
| `test_a_paper_question_is_unchanged_from_develop` | "papers on SARS-CoV-2", record type none, binds what develop binds (the SARS records) | M5 the skip ignores the record type | Passes |
| `test_a_follow_up_with_session_memory_is_unchanged_from_develop`, 3 cases | "What SRA runs are there for it?" after a BRCA1 turn, and "And its SRA runs?" after a Mycobacterium tuberculosis turn (empty extraction, and the organism tagged): same outcome and same MedGen lookups as develop | M4 and M6 (the 2 empty-extraction cases) | Passes |
| `test_the_parse_retry_asks_for_every_schema_key` | The retry message names all four keys and a retried SRA reply keeps "sra" | M7 the retry lists the three hand-kept keys | Red |
| `test_the_narrative_repair_counts_record_type_as_a_known_key` | A "why" reply with `record_type` is repaired; a truly unknown key still fails | M8 the repair knows the three hand-kept keys | Red |

Mutant totals: M1 5 red, M2 1, M3 3, M4 7, M5 1, M6 7, M7 1, M8 1. No mutant left every test green.

The "On develop" column: the same test file run against a scratch export of `origin/develop` (graph.py byte-identical to develop's, checked with `cmp`): 5 passed, 7 failed, exactly the 5 tests that claim develop's behaviour passing.

Neighbouring files also pass unchanged: `test_think_organisms.py`, `test_think_retry.py`, `test_think_disease_and_organism.py` (37 tests).

## How develop's behaviour was established

No second checkout was created. Two ways, both outside the repository except the evidence files:

- From the code. The change acts only inside the D3 loop, only when the record type is "sra" or "assembly", and only on a token that stands in the question solely between a letter or digit and a dash. None of the regression questions has such a token: four have no hyphen at all, "What causes type-2 diabetes?" offers no candidate ("type" is lowercase, "2" is digits only) and has record type "none", and "SRA runs from MODY patients" has no hyphen. The parse-retry fixes change only runs that need the parse retry; no live run below needed it (no "classification unusable" line in any log).
- Side by side, the round 2 adversary's `compare.py` approach: `raw/r3/compare_r3.py` runs Think with the same faked model replies and NCBI against a scratch export of `origin/develop` and against this branch, for every regression question with its live round 2 extraction and with an empty extraction under each record type (28 scenarios). Output: `raw/r3/compare_develop.jsonl` and `raw/r3/compare_branch.jsonl`. They differ in exactly 2 lines, both the SARS-CoV-2 question with an empty extraction (sra and assembly), where develop binds the three SARS records and the branch asks the question back. All 24 regression scenarios are identical.

## Live runs

Guardrail, Think and Plan only, with `raw/think_probe.py`, develop's plan model (its id is the `model` field of every row) and `CLASSIFIER_PROVIDER=jev`. No Act, no Write, nothing written. Raw output in `raw/r3/`, each `.jsonl` with its `_log.txt`.

The SARS-CoV-2 question from findings.md ("Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched."), 20 runs, all valid (no step error, no upstream error to re-run):

| Outcome | Runs | Which |
|---|---|---|
| SARS-CoV-2 tagged as an organism, SRA route on `NCBITaxon:2697049` | 9 | 2, 5, 7, 9, 10, 12, 15, 16, 20 |
| "Illumina" tagged as a gene, failed lookup, nothing planned, refused naming Illumina | 7 | 1, 3, 6, 8, 11, 17, 19 |
| Asked develop's question back ("which gene, variant or condition do you mean?") | 3 | 13 and 14 (no entity at all), 4 (SARS-CoV-2 tagged only as a disease) |
| "respiratory" tagged as a disease, bound by the model-span disease lookup | 1 | 18 |
| Bound a MedGen SARS record | 0 | |

- Runs 13, 14 and 4 are the cases this fix is for: on develop the token fallback would have cut "SARS" out of "SARS-CoV-2" and bound the three SARS records. Here nothing bound and the question was asked back.
- Run 18 bound 8 MedGen records for the model's own span "respiratory" (none of them a SARS record) and planned 8 calls on them. That is the model-span disease lookup, which this change does not touch; develop does the same for the same reply. It is a confident wrong subject of its own and is listed under "Not covered".
- The "Illumina" refusal stays, as the owner decided: 7 of 20.

Regression set, 3 runs each, all valid:

| Question | Result, 3 of 3 alike | Matches develop because |
|---|---|---|
| What diseases are linked to BRCA1? | BRCA1 tagged (once also "diseases" as a disease), `NCBIGene:672`, record type "none", 13 calls planned | A gene resolved, so the disease fallback never ran; record type "none" |
| Mycobacterium tuberculosis genome assemblies | Organism tagged, `NCBITaxon:1773`, record type "assembly", 3 calls | The organism route resolved before the disease fallback; no hyphen in the question |
| SRA runs of BRCA9 knockouts in human cells | BRCA9 tagged as a gene (twice with "human"), failed lookup, nothing planned, refused naming BRCA9 | A failed gene span keeps the disease fallback from running, as on develop |
| SRA runs of BRCA1 knockout cells | BRCA1 tagged, `NCBIGene:672`, record type "sra", 13 calls | A gene resolved; no hyphen in the question |
| What causes type-2 diabetes? | "type-2 diabetes" tagged as a disease, 8 MedGen records bound by the model-span lookup, record type "none", 8 calls | The model-span lookup is untouched; record type "none" |
| SRA runs from MODY patients | "MODY" tagged as a disease, 8 MedGen records, record type "sra", 8 calls | The model span resolved before the disease fallback; with nothing tagged, MODY is a whole word and still binds (test and offline compare) |

In all 18 runs the model tagged something that resolved or failed as a gene, so the disease fallback this change touches did not run; each result is therefore develop's by the code path, and the offline compare covers the empty-extraction case the live runs did not draw. No run needed the parse retry.

## Gates

Run in the worktree with the main checkout's virtual environment first on the path.

| Gate | Result |
|---|---|
| gate02, import order | Passes |
| gate03, lint over the whole repository | Passes, the copied review scripts and this round's `raw/r3/` scripts included. The copied round 1 and round 2 scripts needed no fix; `raw/r3/compare_r3.py` had three unused `noqa` markers, removed |
| gate04, the whole unit suite | 6939 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 5 minutes 46 seconds. The 6 Postgres tests did not fail on this run. Started when the one-minute load average fell below 8 (7.5); it climbed back to about 16 while the suite ran |

## Spend

Live runs: 38 probe runs, $0.0115 by the probe's own cost field (20 SARS-CoV-2 runs $0.0059, 18 regression runs $0.0056), under the $0.06 limit. The tests, mutants and offline compare call no model and no network.

## Not covered

- The "Illumina" refusal stays: 7 of 20 live runs tag Illumina as a gene and plan nothing. Round 2's gene-or-condition release was not kept, by the owner's decision.
- The organism retry is not built. When the model names nothing, the person is asked develop's gene question, which does not mention the organism they typed.
- A hyphen-joined disease name on an SRA question loses its piece too. "SRA runs from COVID-19 patients" with an empty extraction: develop binds the token "COVID" to MedGen and plans a graph call; the branch binds nothing, asks nothing (no referring word) and plans develop's topic search (checked offline with the same fakes on both trees, not live). When the model tags "COVID-19" as a disease, the model-span lookup runs as on develop.
- A Unicode-hyphen organism span in #173's exclusion is unchanged: #173 matches the model's span against the question text exactly, so a span copied with a different dash than the person typed does not claim its tokens. On an SRA question this fix's skip now covers that gap for the disease fallback; the gene-shaped fallback is unchanged.
- The model-span disease lookup can bind a word the model mis-tagged as a disease ("respiratory", live run 18). Unchanged from develop.
- Act and Write were not run.
