# Card 56 follow-up: build report, round 2

Builder report for `fix/card56-r2`, 2026-10-06. Round 1 (`build.md`) failed review (`judge.md`, `adversary.md`), and the owner chose a narrower design. This round starts from round 1's code and changes only Think and Write in `src/system_03_search_agent/core/graph.py`, with tests in `tests/system_03_search_agent/core/`.

## Table of contents

- [What changed, in the user's words](#what-changed-in-the-users-words)
- [Each finding](#each-finding)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [Tests](#tests)
- [Live runs](#live-runs)
- [Offline probe rerun](#offline-probe-rerun)
- [Gates](#gates)
- [Time added and spend](#time-added-and-spend)
- [Not covered](#not-covered)

## What changed, in the user's words

The owner's rule for this round: a question about SARS-CoV-2 sequencing runs is never answered about the disease SARS and never silently plans nothing, and no question that works on develop today gets worse.

| Part | Now |
|---|---|
| 1. Ask Think again, narrowly | Only when Think's reply names nothing at all, asks for SRA runs or assemblies, and the question carries no typed identifier, accession, coordinate window or isolate shape. The second reply is used only when it still asks for those records and names an organism that is text of the question (any case, any dash). It may use only what is left of Think's own budget, and is not made with less than 2 seconds left |
| 2. Round 1's name rule is gone | The token fallback is develop's again: "TP53-mutant and KRAS-mutant and EGFR-mutant" offers all three genes, "MERS-CoV" offers MERS, "type-2" offers nothing. The #173 rule stays: a token inside a named organism is never a candidate |
| 3. The disease fallback, and when to ask | On a question for SRA runs or assemblies, the disease fallback (MedGen by token) does not run; the gene fallback runs as on develop, so "SRA runs of BRCA1 knockout cells" with nothing tagged still finds BRCA1. The person is asked "which organism's SRA sequencing records do you want?" only when nothing resolved, no organism was named and no gene span failed, so "SRA runs of BRCA9 knockouts" keeps "BRCA9 was not recognised" |
| 4. A search condition read as a gene | Kept from round 1, with four fixes. When the classifier calls "Illumina" a condition, the answer itself carries a note: "Illumina was not applied to this search: it finds the SRA sequencing records filed under SARS-CoV-2, by organism only." Think's narrative cuts the model's own words first, never the disclosure. The span is one line and at most 60 characters wherever code places it. A gene, allele or resistance gene the runs should carry is a gene, not a condition |
| 5. The parse retry | It now lists all four keys, `record_type` included, and the key repair counts `record_type` as known, so a reply that needed either keeps its SRA route |
| 6. Pasted dashes | A named organism claims its tokens whatever dash the person pasted: U+2010, U+2011, U+2012, an en dash or a minus sign |

On the double-miss path (empty reply twice), the gene fallback tries "SRA" and "SARS". Checked live with free NCBI calls on 2026-10-06: `resolve_symbol_to_curie("SARS")` and `resolve_symbol_to_curie("SRA")` both return None (control: "BRCA1" returns `NCBIGene:672`). So no gene is bound, the disease fallback does not run, and the person is asked which organism.

Code, by name: `_OrganismRetry`, `_names_nothing_but_wants_organism_records`, `_second_reply_names_a_question_organism`, `_ORGANISM_RETRY_MIN_BUDGET_S`, `_retry_contradictory_classification` (part 1); `_gene_shaped_fallback_candidates` restored, `_name_pattern`, `_span_is_in_question`, `_NAME_DASHES` (parts 2 and 6); the D3 gate and the organism-question gate in `_think` (part 3); `_condition_span_text`, `_OrganismRecords.conditions_not_applied`, `_organism_conditions_note`, `_narrative_with_clauses`, the `_GENE_OR_CONDITION` criteria (part 4); `_THINK_REPLY_KEYS` and `_repair_think_narrative_key` (part 5). No file outside the fence, no schema change: the answer note is one more entry in Write's existing notes list, and its data rides on `_OrganismRecords`, a dataclass in `graph.py` that `GraphState.organism_records` already types as `Any`.

## Each finding

Judge findings:

| Finding | Outcome | How |
|---|---|---|
| J-56-01 "type-2" binds unrelated MedGen records | Fixed | Round 1's name rule removed; "type-2", "phase-3", "day-14" offer nothing (`test_the_token_rule_is_develops`). Live: below |
| J-56-02 whole words take slots, pieces lost | Fixed | Develop's rule restored; three mutant genes, MERS-CoV (same test) |
| J-56-03 retry fires on accession and gene questions | Fixed | Retry only on an empty reply, and not offered with an identifier, accession, window or isolate shape (`test_a_reply_that_names_anything_makes_no_extra_call`, `test_a_question_with_an_identifier_is_not_asked_again`) |
| J-56-04 parse retry and key repair drop `record_type` | Fixed | `test_the_parse_retry_lists_every_key_and_keeps_the_sra_route`, `test_a_synonym_key_beside_record_type_is_repaired` |
| J-56-05 a gene question asked for an organism | Fixed | `test_an_sra_question_with_nothing_tagged_still_finds_its_gene`, `test_a_mistyped_gene_with_no_organism_keeps_its_refusal`; live below |
| J-56-06 Unicode dashes | Fixed for the #173 span exclusion | `test_the_organism_span_claims_its_tokens_under_any_dash`; residuals in "Not covered" |
| J-56-07 a "none" second reply is taken | Fixed | `test_a_second_reply_that_does_not_name_a_question_organism_keeps_the_first` (dropped-record-type cases) |
| J-56-08 fresh 45-second budget | Fixed | `test_the_retry_gets_only_what_is_left_of_thinks_budget`, `test_too_little_budget_left_makes_no_retry` |
| J-56-09 fake binds SARS for the whole name | Fixed | The fake matches the exact term `SARS[title]` only. Live, the code's own lookup `resolve_disease_mention_to_curies("SARS-CoV-2")` returned `([], 0)` (one free NCBI call) |
| J-56-10 two bounds without a failing test | Fixed | Echo: `test_the_retry_echoes_a_long_first_reply_bounded`. Span: `test_a_released_span_enters_state_narrative_and_note_one_line_and_bounded`. Both go red when the bound is removed (M2, M16, M17) |
| J-56-11 lint gate fails on the adversary's probe | Fixed | In the first commit, `ruff check --fix` only: three unused `noqa` markers removed, one import line moved |
| J-56-12 the 500-character cut removes "not applied" | Fixed | `_narrative_with_clauses`; `test_a_long_model_narrative_never_cuts_the_disclosure`, `test_the_narrative_is_unchanged_inside_the_limit` |
| J-56-13 span in the decision state unnormalised | Fixed | Same span test as J-56-10 |

Adversary findings:

| Finding | Outcome | How |
|---|---|---|
| A-56-01 digitless gene pieces lost (BRAF-V600E, anti-TNF) | Fixed | Develop's rule; `test_the_token_rule_is_develops` (braf-v600e, anti-tnf). The offline `part3` mode now shows no question changed against develop |
| A-56-02 the cut leaves "are not" | Fixed | As J-56-12; the offline `trunc` mode now keeps "not applied" with a 328-character model narrative |
| A-56-03 the clause never reaches the answer | Fixed | `_organism_conditions_note`, emitted by `write_node` as a note token; `test_a_released_condition_is_named_under_the_answer` drives `write_node` and finds the exact sentence |
| A-56-04 a "none" retry turns the guard off | Fixed | As J-56-07; offline `none_retry` now keeps the first reply, searches no MedGen and asks which organism |
| A-56-05 the retry accepts an organism never typed | Fixed | `_second_reply_names_a_question_organism`; test case organism-not-in-question; offline `hallucinated_org` now asks which organism |
| A-56-06 "SARS-CoV-2" reaches MedGen as "SARS[title] AND CoV[title]" | Checked, nothing to fix | Live, that lookup binds nothing. With round 1's name rule gone, the whole name reaches MedGen only when the model tags it as a disease; live run 18 below did exactly that and bound nothing |
| A-56-07 retry 11.7 seconds, fresh budget | Fixed | As J-56-08 |
| A-56-08 retry when a gene resolved | Fixed | As J-56-03; offline `brca_tagged_no_org` now makes 1 call |
| A-56-09 E. coli example for a gene question | Not reachable as reported; wording kept | With the gene fallback back, "SRA runs for BRCA1" with nothing tagged resolves BRCA1 and asks nothing (offline `brca_no_org`). The question, with its fixed example, is now asked only when nothing at all was found |
| A-56-10 a gene used as a filter | Fixed | The "gene" criterion names alleles, resistance genes and genes the records should carry; `test_the_gene_criterion_covers_a_gene_the_runs_should_carry`. Live: 4 of 4 kept mcr-1 and blaKPC a gene |
| A-56-11 span forges a second "Span:" line | Fixed | As J-56-13; offline `span_injection` now shows one line |
| A-56-12, A-56-13 | Corrections only | Nothing to do |

Counts: judge, 13 of 13 fixed. Adversary, 9 fixed, 1 checked with nothing to fix, 1 not reachable as reported, 2 corrections.

## Choices for the lead to log

| Choice | Alternatives considered | Why |
|---|---|---|
| The retry's organism check is a case-folded containment match, any dash for any dash and any whitespace run for any other | Exact substring; word boundaries | The person's spelling and the model's copy differ mostly in case and dashes. Word boundaries would refuse "SARS-CoV-2" inside "SARS-CoV-2's". A blank span is never accepted |
| The retry is not made with less than 2 seconds of Think's budget left | No floor; 5 seconds | Live retries took 1.0 to 5.3 seconds on 16 of 17 calls across both rounds; a call with less than 2 seconds is most likely cut off, which costs money and changes nothing |
| The retry may still follow a parse retry, inside the same deadline | Skip it after a parse retry, as the judge suggested | The deadline already bounds the total. A parse-retried reply is the one most likely to come back empty, and skipping would leave that person with the organism question when one more call could have read the organism |
| The answer note appears only when a span was set aside | A note on every organism-records answer ("by organism only; other conditions not applied") | The owner asked for the not-applied sentence of part 4 to reach the answer. A note on every organism-records answer would change answers that work on develop today; it is listed for the owner as a possible follow-up |
| The note says "filed under SARS-CoV-2" | "SARS-CoV-2's SRA runs", as the brief's example | No possessive to get wrong on names ending in "s" ("Mycobacterium tuberculosis's") |
| The disease fallback is skipped on every SRA or assembly question, whether or not an organism was named | Skip only when no organism was named | The owner's wording. With an organism confirmed, something already resolved and the fallback never ran anyway |
| A Taxonomy-rejected organism span counts as no organism named for the question asked back | Count any span the model tagged | Kept from round 1: "SRA runs from hospital samples" names no organism NCBI knows |
| The retry key list and the repair's known keys are read from the schema | Add "record_type" by hand | A key added to the schema later cannot be forgotten again, which is how J-56-04 happened |
| The dash class also takes U+2012 and U+2212 | Only U+2010, U+2011 and the en dash, as briefed | Same category, same cost; fix by category |
| Condition spans are bounded once, in Think, and stored bounded | Bound at each reader | One place to get right; the state, the narrative and the note read the same text |
| A cut model narrative loses trailing spaces | Cut exactly | Avoids "and an  (" with two spaces; inside the limit the text is byte-for-byte develop's |
| The probe prints five more fields (unresolved spans, the question asked back, MedGen records bound, conditions set aside) | Read them from logs | The 20-run count needs "silent nothing planned" and "MedGen SARS binding" per row |

## Tests

`tests/system_03_search_agent/core/test_think_empty_extraction.py`, rewritten: 66 cases. `test_think_organisms.py` is back to develop's version, since its round 1 change only followed round 1's name rule.

Each mutation below changed one property in `graph.py`, ran the named test, saw it fail, and restored the file (scripted, one at a time; after all 24 the file passed 66 of 66 and `graph.py` was byte-identical to the backup).

| Test | Property | Mutation that turned it red |
|---|---|---|
| `test_a_reply_that_names_nothing_and_wants_sra_runs_is_asked_once_more` | The retry is asked, echo first, every key listed, no hint | M1, retry never asked |
| `test_the_retry_echoes_a_long_first_reply_bounded` | Echo cut to 300 | M2, echo unbounded |
| `test_a_reply_that_names_anything_makes_no_extra_call` (5 cases) | A gene-only reply is not asked again | M3, trigger reads "no organism" (2 cases red) |
| `test_a_question_with_an_identifier_is_not_asked_again` (2 cases) | Accession and typed identifier make one call | M4, identifier gate removed (2 red) |
| `test_the_question_without_an_identifier_is_asked_again_through_think` | Populate check for M4 | None; guards the other direction |
| `test_without_the_retry_offered_an_empty_reply_is_not_asked_again` | No retry object, no retry | None; a wiring check |
| `test_a_second_reply_that_does_not_name_a_question_organism_keeps_the_first` (7 cases) | A "none" second reply and an organism the question lacks keep the first | M5, "none" accepted (1 red); M6, no question check (2 red) |
| `test_a_second_reply_naming_the_question_organism_is_used` (4 cases) | Populate check: case and dash variants accepted | None; guards the other direction |
| `test_a_failed_or_unusable_retry_keeps_the_first_reply` (3 cases) | Unusable, failed, cost cap | Not mutated this round; carried from round 1, where M1e turned it red |
| `test_the_retry_gets_only_what_is_left_of_thinks_budget` | Budget is the remainder | M7, fresh step budget |
| `test_too_little_budget_left_makes_no_retry` | The floor | M8, floor removed |
| `test_nothing_named_twice_asks_which_organism_and_binds_no_disease` | Double miss: gene fallback as develop, no MedGen, the question asked, no tool | M9, disease fallback not skipped; M12, question never asked |
| `test_an_sra_question_with_nothing_tagged_still_finds_its_gene` | BRCA1 found with nothing tagged | M10, gene fallback gated on record type |
| `test_a_mistyped_gene_with_no_organism_keeps_its_refusal` | BRCA9 refusal kept | M11, question ignores a failed span |
| `test_an_organism_span_taxonomy_rejects_is_asked_about` | Rejected span still asked about | Covered by M9 and M12 in kind; not run separately |
| `test_with_no_record_type_both_fallbacks_still_run` | Populate check: record type "none" unchanged from develop | None; guards the other direction |
| `test_a_retry_that_names_the_organism_searches_its_runs` | Retry to SRA route end to end | Covered by M1 in kind; not run separately |
| `test_the_organism_question_names_the_record_kind_and_what_to_type` | Wording | None; a wording check |
| `test_the_token_rule_is_develops` (6 cases) | Digitless hyphen pieces offered, "type-2" not | M13, digitless hyphen pieces dropped (4 red) |
| `test_the_organism_span_claims_its_tokens_under_any_dash` (4 cases) | Any dash | M14, one dash only (3 red; the ASCII case passes as it should) |
| `test_a_span_is_in_the_question` (6 cases) | The matcher's own cases | Covered by M14 in kind |
| `test_a_span_the_classifier_calls_a_condition_is_released_and_named` | Release, narrative, records carry the span | M24, conditions not carried |
| `test_a_long_model_narrative_never_cuts_the_disclosure` | Disclosure kept whole | M15, cut at the end as before |
| `test_the_narrative_is_unchanged_inside_the_limit` | Develop's composition inside the limit | None; guards the other direction |
| `test_a_released_span_enters_state_narrative_and_note_one_line_and_bounded` | One line, bounded, in all three places | M16, state span raw; M17, released span unbounded |
| `test_a_released_condition_is_named_under_the_answer` | The note reaches Write's answer tokens; none without organism records | M18, note left out of the answer |
| `test_the_note_names_several_conditions_and_none_when_nothing_was_set_aside` | Wording, plural, None | None; a wording check |
| `test_a_mistyped_gene_keeps_its_refusal` | Kept from round 1 | Round 1's M4c |
| `test_no_usable_pick_keeps_the_refusal` | No pick, no release | M23, no pick read as condition |
| `test_one_gene_among_conditions_releases_nothing` | All or nothing | M22, `any` for `all` |
| `test_the_classifier_is_asked_only_on_the_organism_route` (3 cases) | Kept from round 1 | Round 1's M4e |
| `test_the_gene_criterion_covers_a_gene_the_runs_should_carry` | A-56-10's wording | M19, criterion without allele |
| `test_the_decision_cap_holds_with_the_new_point` | Constant check | None |
| `test_the_parse_retry_lists_every_key_and_keeps_the_sra_route` | Four keys; parse retry then organism retry reaches the SRA route | M20, three keys |
| `test_a_synonym_key_beside_record_type_is_repaired` | Repair with `record_type` | M21, three known keys |

The mutation script lived in the session scratchpad and is not committed; each mutation is the one-line change named above.

Where the answer note is shown: Write emits notes as answer tokens of kind "note" before the `done` event, and the UI renders them under the answer. `DonePayload` carries no notes, so the test asserts on the note token and that the run reached `done`.

## Live runs

Guardrail, Think and Plan only, with `raw/think_probe.py`, on develop's plan model (its id is the `model` field of every row) with `CLASSIFIER_PROVIDER=jev`. No Act, no Write, nothing written. Raw output: `raw/r2/*.jsonl`, with each run's log lines in the matching `_log.txt`. Log lines are matched to rows by trace order.

The SARS-CoV-2 question, 22 consecutive runs, all valid (no step error), so the target's 20 are runs 1 to 20:

| Outcome | Runs 1 to 20 | All 22 | Which |
|---|---|---|---|
| SARS-CoV-2 tagged on the first reply, SRA route on `NCBITaxon:2697049` | 9 | 10 | 1, 3, 4, 7, 8, 10, 12, 16, 19, 21 (8, 12, 16: "Illumina" also tagged as an organism, which Taxonomy does not know) |
| "Illumina" tagged as a gene and failed, the classifier called it a condition, SRA route, note set | 5 | 5 | 9, 11, 14, 17, 20 |
| First reply named nothing, the retry named SARS-CoV-2, SRA route | 5 | 6 | 2, 5, 6, 13, 15, 22 |
| SARS-CoV-2 tagged only as a disease, so no organism named: asked which organism | 1 | 1 | 18 |
| Bound a MedGen SARS record | 0 | 0 | |
| Planned nothing without asking or naming why | 0 | 0 | |

Run 21 also needed the existing parse retry (an extra `note` key on each entity) and kept its SRA route. Run 18 is a new model habit to this report: the reply tagged "SARS-CoV-2" as a disease and nothing as an organism. The disease lookup bound nothing (the code's MedGen term for the whole name finds nothing), the disease fallback did not run, and the person was asked which organism. On develop the same reply would have reached the disease fallback with "SARS" cut out of the name and bound the three SARS records. It is honest but asks for something the person typed; see "Not covered".

Regression set, 3 valid runs each:

| Question | Result |
|---|---|
| What diseases are linked to BRCA1? | 3 of 3: `NCBIGene:672`, record type "none", 13 tool calls planned (graph route), no retry |
| Mycobacterium tuberculosis genome assemblies | 3 of 3: `NCBITaxon:1773`, record type "assembly", 3 tool calls, no retry |
| SRA runs of BRCA9 knockouts in human cells | 3 of 3: BRCA9 and human tagged, the classifier kept BRCA9 a gene, nothing planned, BRCA9 named as not recognised, no organism question |
| SRA runs of BRCA1 knockout cells | 3 of 3 valid: BRCA1 tagged, `NCBIGene:672`, 13 tool calls, no retry. One further run ended "a step failed" when Think's first call timed out at 45 seconds (an upstream stall; no retry line in its log, record type unread); it was re-run (`regression_4_rerun.jsonl`) and is not counted |
| What causes type-2 diabetes? | 3 of 3: the model tagged "type-2 diabetes" as a disease; 8 MedGen records bound, all diabetes records, none of the unrelated "type" records J-56-01 found. Two of the eight are not type 2 diabetes ("Diabetes mellitus type 1", "Maturity-onset diabetes of the young type 2"): that is the model-span disease lookup, unchanged from develop, which drops the one-character "2" from its title search. Titles read with one free NCBI call. See "Not covered" |

Criterion check for A-56-10, 2 runs each: "Escherichia coli SRA runs carrying mcr-1" and "Klebsiella pneumoniae SRA runs carrying the blaKPC gene". On all 4 the classifier kept the gene a gene; nothing planned, the gene named as not recognised (as on develop). On the SARS-CoV-2 runs the same new criteria still released "Illumina" 5 of 5.

## Offline probe rerun

The adversary's `raw/adversary/offline_probe.py`, all eight modes, against this branch; output in `raw/r2/offline_probe_rerun.txt`. It reuses this test file's fakes, now with the realistic MedGen fake.

| Mode | Round 1 | Now |
|---|---|---|
| part3 (28 questions against develop's rule) | 9 changed | 0 changed |
| trunc (328-character model narrative) | "not applied" cut | Kept; 499 characters |
| none_retry | MedGen searched, no question | First reply kept, no MedGen search, organism question |
| hallucinated_org | Every Homo sapiens run | First reply kept, organism question |
| gene_released (ORF8, mcr-1 with a mocked "condition" pick) | Released | Released; the pick is the live classifier's job, and A-56-10's live check held |
| brca_no_org | Organism question with an E. coli example | BRCA1 and TP53 resolve by the fallback, nothing asked (2 calls: the reply named nothing) |
| brca_tagged_no_org | 2 calls | 1 call |
| span_injection | Two "Span:" lines | One line; the forged text is part of the bounded span |

## Gates

Run in the worktree with the main checkout's virtual environment first on `PATH`, as CI runs them.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass |
| `gate03_lint.sh` (ruff, whole repository) | Pass |
| `gate04_unit_suite.sh` | 6993 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 374 seconds. The six tests that need Postgres on localhost passed on this run |
| `/verify`, backend-only | No file under `frontend/` changed, so no screen was captured; the verdict is the facts check's alone. `check_facts.py` with the virtual environment: "facts: 80, stale 0, not fully checked 0, places: PASS 225, FAIL 0, GAP 0, ERROR 0, PASS". Its report lines are kept here rather than in a separate verify folder, which is outside this round's file fence |
| Golden run and rubric (`/verify` Step 5, answer path) | Still to run, by the lead: this change decides whether some SRA questions are answered or asked back, and adds an answer note |

## Time added and spend

| Path | Measured |
|---|---|
| Organism retry, 6 live calls this round | 1,773 to 5,324 ms, median 3,224 ms |
| Guardrail to Plan, SARS-CoV-2 runs | Median 8.2 s with the retry (6 runs), 4.8 s without (16 runs) |
| Worst case of the retry | It ends no later than Think's own deadline, 45 seconds from the start of Think, and is not made with under 2 seconds left. So it can never make Think outlast its declared budget; before this round it could add a fresh 45 seconds |
| A reply that names anything, or a question with an identifier | No extra call, by construction and by test |
| `think.gene_or_condition` | Unchanged from round 1: one decision per failed span, at once |

Spend: $0.0193 across 42 probe runs (the probe's per-run cost, decisions included), plus free NCBI calls, against the $0.10 limit.

## Not covered

- Act was not run, live or in a unit test. Write was run in one unit test with a faked answer model; the note sentence was not seen live.
- The record type "none" path is develop's: a SARS-CoV-2 question that is not read as an SRA question, with nothing tagged, still offers "SARS" to the disease fallback (`test_with_no_record_type_both_fallbacks_still_run` keeps this as a populate check). A space-separated "SARS CoV 2" is not matched to a span the model wrote with hyphens.
- Run 18's habit: a reply that tags the organism as a disease gets the organism question. The rate is 1 in 22 here; asking Think again for it would need a wider retry trigger than the owner chose.
- The model-span disease lookup drops one-character words, so "type-2 diabetes" also binds type 1 and MODY type 2 records. Unchanged from develop and outside this card, filed here for the lead.
- The double-miss path (empty twice) was not seen live: all 6 retries this round named SARS-CoV-2. It is covered offline, and the "SARS" gene lookup it makes was checked live.
- The retry still costs one call on "SRA runs for BRCA1" when the reply names nothing, by design.
- Other plan models were not run.
