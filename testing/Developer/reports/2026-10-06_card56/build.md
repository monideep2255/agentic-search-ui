# Card 56 follow-up: build report

Builder report for `fix/card56-empty-extraction`, 2026-10-06. The diagnosis is `findings.md` in this folder. Everything changed is in Think (`src/system_03_search_agent/core/graph.py`), with tests in `tests/system_03_search_agent/core/`.

## Table of contents

- [What changed, in the user's words](#what-changed-in-the-users-words)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [Tests](#tests)
- [Gates](#gates)
- [Live runs](#live-runs)
- [Found on the way, not changed](#found-on-the-way-not-changed)
- [Not covered](#not-covered)

## What changed, in the user's words

The person asks "Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched."

| Part | Before | Now |
|---|---|---|
| 1. Contradiction retry | About 1 run in 5, Think's reply said "this asks for SRA runs" and named no organism, and the run went on with that | Think is asked once more, with its reply echoed and the two fields that disagree named. On 5 of 22 live runs this fired, and all 5 second replies named SARS-CoV-2. A reply that agrees with itself makes no extra call |
| 2. Ask instead of guessing | With no organism named, a token cut from the question was looked up as a gene and then as a disease | When the second reply still names no organism, nothing is guessed. The person is asked: "One more detail is needed: which organism's SRA sequencing records do you want? Ask again naming the organism, for example "Escherichia coli SRA sequencing records"." |
| 3. A name is never cut into pieces | "SARS-CoV-2" was split on its hyphens, and "SARS" bound three MedGen records about the disease SARS | A hyphen-joined word is tried whole first. A piece of it is tried only when the piece carries a digit. "SARS-CoV-2" never offers "SARS"; "COVID-19" is tried as "COVID-19"; "TP53-mutant" still offers "TP53"; "NKX2-5" offers "NKX2-5" first |
| 4. A failed "gene" that is a search condition | About 1 run in 6, "Illumina" was read as a gene, the lookup failed, and the question was refused with nothing planned | The classifier is asked, one span at a time, whether the span is a gene the person asks about or a condition on the search. Only when it calls every such span a condition does the SARS-CoV-2 search run, and the narrative says "Illumina and any other condition the question names are not applied to the search". "SRA runs of BRCA9 knockouts in human cells" keeps its refusal |

Code details:

- Part 1 lives in `_run_think_classification`, so the probe and `_think` both see the classification Think finally used. New helpers: `_wants_organism_records_but_names_none`, `_retry_contradictory_classification`.
- Part 2: `organism_unnamed` in `_think` gates the gene-shaped fallback and the D3 disease fallback and sets the question (`_which_organism_question`). It reads the organism spans NCBI Taxonomy did not reject, so a span the model mis-tagged as an organism ("hospital") is asked about too.
- Part 3: `_gene_shaped_fallback_candidates`, with `_HYPHEN_JOINED_WORD_PATTERN` and `_MAX_HYPHEN_WORD_CHARS` (12). The docstring states the new rule and its residual.
- Part 4: a new decision point `think.gene_or_condition` (`_GENE_OR_CONDITION`, fail open to "gene"), asked through `_decide_point` by `_failed_spans_that_are_conditions`. `_organism_records_disclosure` takes the released spans.
- Decision cap: a run could already make seven decisions (the comment said six and missed `plan.paper_links`). This adds at most three (`_MAX_LIVE_SYMBOL_LOOKUPS`), so ten at most, inside `DonePayload.decisions`' cap of 16. No schema change; the comment beside `_MAX_DONE_DECISIONS` now says ten and names the points.

## Choices for the lead to log

| Choice | Alternatives considered | Why |
|---|---|---|
| The retry sits inside `_run_think_classification` | A second call from `_think` after the classification returns | It stays inside the task that already overlaps the recent-years decision, and every reader of the classification, the probe included, sees the one Think used |
| Part 1 reads the reply's own entity types; part 2 reads the spans Taxonomy did not reject | Both on entity types; both on Taxonomy | The retry is a check of the reply against itself, with no network call. The question asked back must also cover a span NCBI says is not an organism |
| The second reply is used only when it is usable and no longer contradicts itself; otherwise the first is kept | Always take the second; pick by entity count | Neither contradictory reply is better than the other, and keeping the first changes nothing downstream. "None" as the second record type is not a contradiction, so it is used |
| A failed retry (cost cap, call error, unusable reply) keeps the first reply | End the run with the cap or step error, as the parse retry does | The first reply is usable. The retry is optional, and the person then gets the organism question rather than an error |
| The retry message names both fields and the required keys, and says "Read the query again" | Name what is missing ("add the organism"); say nothing but "try again" | T-8.1-01's rule: state what is wrong, never what to report. A bare retry repeats the same habit |
| The organism question is asked even beside a failed gene span | Keep the gene refusal when a span failed | Nothing can be searched until an organism is named; the span is judged once one is |
| The example in the question is "Escherichia coli", fixed | "SARS-CoV-2", as the brief suggested; an organism read from the question | SARS-CoV-2 is the test question's own organism, which the owner rule forbids lifting. A question that names no organism has none to read |
| Whole hyphen-joined words capped at 12 characters | 10, the length of "SARS-CoV-2"; 30, the resolver's field | It admits "SARS-CoV-2", "COVID-19" and hyphenated gene symbols ("HLA-DRB1", "NKX2-5") with room, and keeps descriptions such as "SARS-CoV-2-positive" (19) from being tried whole |
| A whole hyphen-joined word must start with a letter | The shape rule alone, as briefed | "10-fold", "24-hour" and "2020-2021" pass the digit rule. The old token rule admitted none of them, and the disease fallback binds by-name hits, so each would be a new chance of a confident wrong record |
| Part 4 releases spans all or nothing | Release each span the classifier calls a condition | The search runs only when nothing is left unresolved. Releasing some would only change which names the refusal lists |
| Part 4 takes the seam's usable pick (Jev's, or the guard tier's after a Jev failure) | Jev's pick only (`_jev_picked`) | It is what every other `decide()` point acts on. No pick at all keeps the refusal |
| Part 4's decisions run at once, each bounded by Think's own deadline | One after another | The person waits for the slowest, not the sum |
| One code commit for the four parts | One commit per part | The parts interleave in `_think`; splitting them would need interactive staging, which this environment does not run |

## Tests

New file `tests/system_03_search_agent/core/test_think_empty_extraction.py`, 32 cases. Each mutation below changed one property in `graph.py`, ran the named test, saw it fail, and restored the file. After all 19 mutations the file passed again, 32 of 32.

| Test | What it proves | Mutation that turned it red |
|---|---|---|
| `test_a_reply_that_wants_sra_runs_and_names_no_organism_is_asked_once_more` | One extra call; the first reply echoed, bounded; the statement names both fields and no word of the question; the second reply is used | M1a, the retry never asked |
| `test_a_reply_without_the_contradiction_makes_no_extra_call` (3 cases) | SRA with an organism, "none" with no entities and "none" with a gene make one call | M1b, the check ignores the record type |
| `test_a_second_reply_that_still_names_no_organism_keeps_the_first` (sra, assembly) | The first reply is kept, and never more than one extra call | M1c, a still-contradictory second reply used; M1d, the retry asked twice |
| `test_a_second_reply_that_drops_the_record_type_is_used` | Populate check: "none" is no contradiction | None; a populate check that guards the other direction |
| `test_a_failed_or_unusable_retry_keeps_the_first_reply` (unusable, call failed, cost cap) | Nothing is invented and the run goes on | M1e, a failed call re-raised |
| `test_still_no_organism_asks_which_organism_and_guesses_nothing` | Through `think_node` and `plan_node`: the organism question, no gene lookup, no MedGen search, no tool | M2a, gene fallback not gated; M2b, disease fallback not gated; M2c, no organism question |
| `test_the_organism_question_names_the_record_kind_and_what_to_type` | The wording for SRA and assemblies, what to type next, no "gene", under 500 characters | None run; a wording check |
| `test_an_organism_span_taxonomy_rejects_is_asked_about_too` | A span NCBI rejects is no organism: no retry, the question is asked | M2d, the gate reads raw entity types |
| `test_with_no_record_type_the_fallbacks_still_run` | Populate check: the same empty reply with "none" runs both fallbacks as before | None; a populate check |
| `test_a_retry_that_names_the_organism_searches_its_runs` | End to end: a retry that names SARS-CoV-2 routes to `NCBITaxon:2697049` and `sra` | M1a, run against this test separately |
| `test_a_hyphen_joined_name_is_never_cut_into_pieces` (8 cases) | The four briefed outcomes, plus: a 19-character chain is not tried whole, measures and dates stay out, plain tokens and the cap of 3 are unchanged, de-duplication holds | M3a, pieces without a digit allowed; M3b, whole words dropped; M3c, pieces before the whole; M3d, no length cap; M3e, no leading-letter rule |
| `test_the_whole_word_cap_admits_the_measured_names` | The cap admits "SARS-CoV-2" and stops "SARS-CoV-2-positive" | None run; a constant check |
| `test_a_span_the_classifier_calls_a_condition_is_released_and_named` | "Illumina" called a condition: the decision's state is the question and the span, the SARS-CoV-2 SRA route runs, no refusal, and the narrative names Illumina as not applied | M4b, the span left out of the narrative |
| `test_a_mistyped_gene_keeps_its_refusal` | "BRCA9" called a gene keeps its refusal by name | M4c, released without reading the pick |
| `test_no_usable_pick_keeps_the_refusal` | Code never decides "condition" itself | M4d, no pick read as a condition |
| `test_one_gene_among_conditions_releases_nothing` | One "gene" among conditions releases nothing | M4a, `any` in place of `all` |
| `test_the_classifier_is_asked_only_on_the_organism_route` (3 cases) | No decision with record type "none", with nothing failed, or with an organism NCBI files under two taxa | M4e, asked off the route |
| `test_the_decision_cap_holds_with_the_new_point` | Seven plus three fits the cap of 16; the spec fails open to "gene" | None run; a constant check |

The mutation script lived in the session scratchpad and is not committed; each mutation is the one-line change named above.

Existing tests: one assertion changed, in `test_think_organisms.py::test_a_token_inside_an_organism_span_is_never_a_candidate`. Its populate check asserted the question with no organism span still yields "SARS". Part 3 makes that impossible by design, so the check now asserts the name is offered whole ("SARS-CoV-2") without the span and not at all with it. The intent, that the organism span claims its tokens, is unchanged.

## Gates

Run in the worktree with the main checkout's virtual environment on `PATH`, exactly as CI runs them.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass |
| `gate03_lint.sh` (ruff, whole repository) | Pass, after a lint-only fix to `raw/think_probe.py` (below) |
| `gate04_unit_suite.sh` | 6959 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 334 seconds. The six tests that need Postgres on localhost:5432 passed on this run |

The probe the lead placed in `raw/` failed `gate03` with seven fixable findings: six unused `noqa: E402` markers and one unsorted import block. `ruff check --fix` removed the markers and moved one import line (`contracts.query` ahead of `core`) inside a block that runs after the environment is set, so the probe behaves exactly as before. Committed that way, since report folders count as source for the lint gate.

## Live runs

Guardrail, Think and Plan only, with `raw/think_probe.py`: develop's plan model (its id is the `model` field of every row), `CLASSIFIER_PROVIDER=jev`, no Act, no Write, nothing written. Raw output: the `raw/after_fix_*_runs.jsonl` files, with each run's log lines (retry outcome and timing, every decision call) in the matching `_log.txt`. A run's log lines are matched to its row by trace order.

The SARS-CoV-2 question, 22 consecutive runs, all valid (no step error):

| Outcome | Runs | Which |
|---|---|---|
| SARS-CoV-2 tagged on the first reply, SRA route planned on `NCBITaxon:2697049` | 12 | 1, 3, 4, 5, 9, 11, 13, 15, 16, 19, 21, 22 |
| "Illumina" tagged as a gene and failed, the classifier called it a condition, SRA route planned | 5 | 6, 7, 8, 12, 14 |
| First reply named no organism, the retry named SARS-CoV-2, SRA route planned | 5 | 2, 10, 17, 18, 20 |
| Bound a MedGen SARS record | 0 | |
| Planned nothing without asking | 0 | |
| Asked which organism | 0 | |

All 22 planned the SRA search (3 tool calls, resolved `NCBITaxon:2697049`), so the done-when holds on the first 20 and on all 22. Run 4 also needed the existing parse retry (an entity type outside the schema). Runs 1 and 21 tagged "Illumina" as an organism; Taxonomy has no such name, so SARS-CoV-2 alone resolved.

Regression and edge questions, same settings:

| Question | Valid runs | Result |
|---|---|---|
| What diseases are linked to BRCA1? | 3 of 3 | BRCA1 tagged, `NCBIGene:672`, record type `none`, 13 tool calls planned (the graph route), no retry |
| Mycobacterium tuberculosis genome assemblies | 3 of 3 | `NCBITaxon:1773`, record type `assembly`, 3 tool calls planned, no retry |
| SRA runs of BRCA9 knockouts in human cells | 3 of 3 | The classifier called BRCA9 a gene on all 3; nothing planned, the BRCA9 refusal kept |
| Find SRA runs sequenced on Illumina from clinical respiratory samples | 3 of 4 | No organism on either reply, kept the first, asked a question back on all 3 valid runs. The fourth ended at the guardrail after a 10-second upstream timeout and was re-run, not counted |

Time added:

| Path | Measured |
|---|---|
| Contradiction retry, 8 live retries | 1,638 to 3,119 ms, median 2,394 ms |
| `think.gene_or_condition`, 8 live decisions | 197 to 332 ms each, one per run, so one decision's time per run |
| A reply without the contradiction | No extra call, by construction and by test |

Spend: about $0.012 in all (the probe's per-run cost, decisions included), against the $0.10 limit.

## Found on the way, not changed

Both are in `graph.py` but outside the four parts, so they are left for the lead:

- The parse-failure retry message (T-8.1-01) still lists only "query_class", "narrative" and "entities" as the keys to use. Since card 56 added `record_type`, a model that obeys it drops the record type, which then defaults to "none", so an SRA question that needed the parse retry loses its organism route. Run 4 above needed that retry and still kept "sra", so the model does not always obey.
- `_repair_think_narrative_key` treats only those three keys as known, so a reply that writes "why" for "narrative" and also carries `record_type` is no longer repaired and goes to the parse retry.
- Pre-existing: Think's narrative is cut at 500 characters after the disclosures are added, so a long model narrative can cut the "not applied" clause.

## Not covered

- Act and Write were not run, live or in a unit test for these paths: the answer text, and whether Show work carries the "not applied" clause, are unseen.
- The organism question was seen live only on a question that names no organism. On the SARS-CoV-2 question every retry recovered the organism, so the ask path was not reached there.
- The rate of empty-entity replies on other question shapes was not measured.
- Other plan models were not run after the fix.
- The residual of part 3: an all-capitals gene symbol with no digit inside a hyphen-joined word ("CFTR-related") is no longer a fallback candidate. It is still found when the model extracts it.
- The classifier's pick for each `think.gene_or_condition` decision is not in the probe's output; it is read from the outcome (released, so every span was called a condition; refused, so at least one was called a gene).
