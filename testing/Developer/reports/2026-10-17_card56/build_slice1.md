# Card 56, slice 1: build report

Builder's report for the whole-phrase lookup and the guarded word fallback (Parts 1 and 2 of `design.md`), built on 2026-10-17 on branch `fix/card56-phrase-lookup` from develop 535943bc. Paths are relative to `<repo-root>`; scratch files are under `<scratchpad>/card56/`. Nothing was pushed, no pull request was opened.

## Table of contents

- [What a person gets](#what-a-person-gets)
- [The design as built](#the-design-as-built)
- [Where the build departs from the brief](#where-the-build-departs-from-the-brief)
- [Tests](#tests)
- [Mutations](#mutations)
- [Live Think runs](#live-think-runs)
- [Suite, lint and commits](#suite-lint-and-commits)
- [For the lead to decide](#for-the-lead-to-decide)
- [What was not covered](#what-was-not-covered)
- [Digit exception](#digit-exception)

## What a person gets

- "SARS CoV-2", "SARS CoV 2", "SARS-CoV-2" and "COVID-19 virus" read as the virus, NCBI Taxonomy 2697049, whether the model tagged the phrase as a disease, as nothing, or as an organism. When the lookup did the reading, the plan line says so: "Read 'SARS CoV-2' as the organism Severe acute respiratory syndrome coronavirus 2 (NCBI Taxonomy 2697049)".
- No candidate is ever a piece of a word: "SARS" is never taken out of "SARS CoV-2", "SARS CoV 2", "SARS-CoV-2", "SARS/CoV-2" or "SARS.CoV.2", and "COVID" never out of "COVID-19", on every record type.
- A phrase that confirms as its tagged type is never looked up again: BRCA1, lower-case "brca1", GCK, MODY, "gerd", rs334 and the isolate question plan as on develop.
- Several fits: the person is asked, with the choices as buttons. Nothing fits, on a question asking for an organism's SRA runs or assemblies: the person is told what was not found and what to type.
- Live, on develop's plan model, 0 of 30 runs answered about the wrong subject (the SARS disease or the remembered BRCA1).

## The design as built

All in `src/system_03_search_agent/core/graph.py` unless named.

| Part | Where | What it does |
|---|---|---|
| Unconfirmed disease spans | `_EntityResolution.unconfirmed` 6673, set at 3628 | A disease span MedGen bound nothing for is kept instead of dropped (code map B2) |
| Rejected organism spans | `_organism_spans_rejected` 3167 | Organism spans Taxonomy answered zero for, from the same cached lookup, no new call |
| MedGen exact title | `medgen_exact_title_records` 3492, `_disease_lookup_key` 3476, cache value at 3472 | The exact-title rule only, sharing `resolve_disease_mention_to_curies`'s search, summary and cache, so a phrase the disease check already asked about costs nothing |
| The lookup | `phrase_lookup.look_up` (`core/phrase_lookup.py` 376) | Taxonomy `<phrase>[All Names]`; Gene by `resolve_symbol_to_curie` in the question's organism (human by default) when the phrase is symbol-shaped; MedGen exact title. Outcome one, several, none, or unknown when a database could not be asked |
| The cap | `phrase_lookup.LookupBudget` 239, `MAX_PHRASES` 72, `MAX_CALLS` 78 | Two phrases, ten NCBI calls, each batch in a call-budget scope of its own, so the question's 20-call ceiling never pays for a lookup. The slots the lookup may not spend are charged up front under a reserved name that reaches no network, which makes the cap hard: the eleventh call is refused at the transport before it goes out |
| Wiring, model spans | `_think` 4622 to 4690 | After span confirmation, before the gene fallback; only when nothing resolved, no unresolved gene, no typed identifier, and not on the window, accession or isolate paths. Skipped when a known organism already anchors a records question (`organism_route_ahead` 4673) |
| One fit | `_read_whole_phrases` 4630 | An organism joins the organism spans and is bound by the existing anchor (`_anchor_organism` 4764, called at 4793 and 4857) with its reading line; a gene or MedGen record binds directly with its line |
| Content retry | `_content_retry_reason` 4213, `_content_retry_message` 4227, `_run_think_content_retry` 4248, wired at 4521 | Think asked once more, reusing the parse retry's exchange (bounded echo, then what was missing), within Think's own deadline; any failure keeps the first reply |
| Guarded fallback | `_gene_shaped_fallback_candidates` 3682, `phrase_lookup.name_runs` 191 | Whole words only; a hyphen-joined word is one candidate; adjacent words that read as one name are one candidate; a multi-word run is kept whole when Taxonomy knows it (`split_unplaced_runs` 417), otherwise its words may be tried as exact gene symbols only |
| Fallback order | 4696 to 4860 | Gene fallback on single symbol-shaped words, as before; the anchor; the disease fallback on whole candidates (replacing #186's hyphen skip); then each candidate that bound nothing goes through the lookup |
| The asks | 4871 onward; `several_question` 469, `none_question` 496 | Asked only when nothing else resolved, after every fallback: several, always; none, only for a phrase the model named on an SRA or assembly question |
| Plan line kept whole | 5028 | When the narrative and the disclosures exceed 500 characters, the model's narrative is shortened, never the disclosure |
| No options | `_ask_back` 4002 | An ask with no choices sends none, never an empty list |

The ask texts, as a person reads them:

- Several: "'SARS' matches more than one NCBI record, so I have not picked one for you. Choose the one you mean below, or ask again using its full name." Each button is the person's own question with the phrase replaced by the record's name.
- None: "I could not find 'Xyzzyvirus' as an organism, gene or condition in NCBI, so I cannot tell which organism's SRA sequencing records you want. Ask again naming the organism as NCBI spells it, for example "SRA sequencing records of Escherichia coli"."

`docs/build/Debugging_guide.md` has a row for the new module and the coverage manifest is regenerated.

## Where the build departs from the brief

| Brief | As built | Why |
|---|---|---|
| "SARS" alone is several (Taxonomy 694009, 3 human genes, 3 MedGen) and asked | The test pins "several is asked" with a fake human gene whose own symbol is SARS | Live, under the brief's own fit rules, no human gene's official symbol is SARS (`resolve_symbol_to_curie` answers none) and no MedGen title is exactly "SARS", so a lookup of "SARS" alone would be exactly one, Taxonomy 694009. It never gets there: tagged as a disease, MedGen binds it by containment as today; tagged as an organism, Taxonomy confirms it as today. The "3 and 3" counts in the code map are raw search counts, not fits |
| Several or none: ask | None asks only for a phrase the model named, only on SRA and assembly questions | A papers question naming a disease MedGen does not title-match answers today with a topic search; asking instead would make it worse. A fallback word that fits nothing ("SRA" in "What SRA runs are there for it?") is not asked about, so the remembered-subject follow-ups pinned in `test_think_sra_disease_fallback.py` keep working until slice 3 |
| Plan line "Read 'SARS CoV-2' as the virus SARS-CoV-2" | "Read 'SARS CoV-2' as the organism Severe acute respiratory syndrome coronavirus 2 (NCBI Taxonomy 2697049)" | The name is NCBI's scientific name from one Taxonomy summary call inside the lookup budget; "virus" would need a table of NCBI divisions. A span the model tagged as an organism keeps today's disclosure ("SARS CoV-2: NCBI Taxonomy 2697049; searching ..."), which names the id but not the name, because a confirmed span is never looked up |
| Contradiction: record type sra or assembly with no organism | Retry when the reply names no gene, disease or organism, or asks for records and names only genes | "SRA runs from MODY patients" names a disease and pays nothing, keeping "a reply that names something pays nothing" |
| Fallback "never a word followed or preceded by another word of the same name" | A text rule proposes the run ("SARS CoV-2", "SARS CoV 2", "SARS COV 2"), NCBI Taxonomy decides it: known, kept whole; unknown ("BRCA1 ClinVar"), split, its words tried as exact gene symbols only | No text rule tells "SARS CoV-2" from "BRCA1 ClinVar" (both have a mixed-case second word). One cached Taxonomy search per run, inside the lookup's ten calls |
| Lookup gate: spans that did not confirm | Also requires no unresolved gene and nothing resolved | Keeps every question that resolves something, and today's refusal by name ("BRCA9", the withdrawn BRCA3 naming BRCA2), unchanged. The "Illumina" refusal stays for slice 2 |

Stated costs, all on a reply that names nothing twice (12 of 30 first replies named nothing; every content retry named something):

- "BRCA1-mutant" and "TP53-null" offered the whole word only, never BRCA1 or TP53. Superseded by the owner's digit exception, below.
- "sars cov 2" in lower case has no candidate, so nothing is read; nothing wrong is bound either.
- "AML PubMed papers": the split word AML is tried as a gene only, not as a disease.

## Tests

New: `tests/system_03_search_agent/core/test_think_phrase_lookup.py`, 77 arms, driving the real `think_node` with the model, NCBI search and summary, and the gene resolver faked from live values. Fakes charge the call budget as the real transport does.

| Property | Arms |
|---|---|
| The four variants bind 2697049, tagged as a disease (with the plan line), as nothing then tagged on the retry (with the plan line), and as an organism (today's route, one model call, no lookup) | 12 |
| Twice-empty replies read the whole name: "SARS CoV-2", "SARS-CoV-2", "SARS CoV 2", "COVID-19 virus" (as "COVID-19"); "sars cov 2" binds nothing | 5 |
| No piece is ever a candidate, eleven spellings, and whole words still are | 12 |
| No record type binds a piece, five questions by three record types | 15 |
| A run Taxonomy does not know is never cut into a disease ("SARS.CoV.2"); "BRCA1 ClinVar" still resolves BRCA1 | 2 |
| Confirmed or fixed-rule questions never reach the lookup: BRCA1, brca1, GCK, MODY, gerd, MODY on SRA, SARS as a disease, GCK twice-empty, rs334, the isolate question (query 34), a known organism on a records question | 11 |
| Several asked with buttons; none on SRA says what to type; none on papers searches as before; a follow-up naming nothing is left to memory | 4 |
| Content retry fires only on empty or gene-only records replies, carries every schema key and nothing from the question; a failed retry keeps the first reply; a second empty reply runs the guarded fallback (GCK answers); small talk never retries | 9 |
| The cap: two phrases with three unplaceable ones, the question ceiling paying only for the disease checks; ten calls apart from the ceiling; a lookup past the cap is unknown and binds nothing | 3 |
| Fit rules, wording bounds, retry key list | 4 |

Changed, three pinned tests and one populate check:

- `test_think_sra_disease_fallback.py`, the SRA arm (was `:196`) and the assembly arm (`:213`): intent kept (no MedGen record from a piece); the outcome moves from develop's generic question to the organism route on 2697049, because the whole word is now the candidate and the lookup reads it.
- `test_think_sra_disease_fallback.py:247`, the papers arm, pinned develop's wrong SARS binding on purpose. It now asserts no piece binds and the whole word is looked up; nothing binds and Plan searches the question's words.
- `test_think_organisms.py:149`, the populate check expected the piece "SARS" from the unguarded fallback; it now expects "SARS-CoV-2" and not "SARS".

Every other test code map B4 lists passes unchanged, including `test_layer_handoff.py:637`, `:656`, `:673`, `:700`, `test_cq_routing_mutation.py:605`, `test_think_disease_and_organism.py:259`, the organism arms at `test_think_organisms.py:162` and `:181`, MODY at `:231`, the three memory follow-ups at `:266`, and `test_cq_routing_premise.py:670`.

Pass lines:

```
tests/system_03_search_agent/core/ (before the last two commits): 1661 passed, 56 skipped, 2 warnings in 113.77s
test_think_phrase_lookup.py, test_think_sra_disease_fallback.py, test_think_organisms.py, test_layer_handoff.py (final): 133 passed in 12.26s
test_debugging_guide_coverage.py: 7 passed in 1.96s
```

## Mutations

Each applied to the worktree by `<scratchpad>/card56/mutate.py`, run against the four Think test files, and restored; `git status` was clean of the mutation after each. Unmutated: 133 passed.

| Mutation | Result |
|---|---|
| M1, the fallback cuts a hyphen piece (pieces no longer joined into one word) | 3 failed: AML-derived, BRCA1-mutant, TP53-null. "SARS-CoV-2" survives this one because the run rule rejoins "SARS", "CoV" and "2" on its own |
| M1b, the fallback offers the first piece of every word | 33 failed |
| M6, a word split out of an unknown run reaches the disease fallback | 1 failed: "SARS.CoV.2" |
| M2, a confirmed span reaches the lookup | 15 failed |
| M3, MedGen's loose title search in the lookup | 1 failed: the exact-title unit arm ("Mycobacterium tuberculosis" becomes several) |
| M4, no content retry | 13 failed |
| M5, no cap (no phrase limit, no reserved slots) | 3 failed |

M3 and M6 are each held by one arm.

## Live Think runs

Guardrail, Think and Plan only, `CLASSIFIER_PROVIDER=jev`, plan model `deepseek/deepseek-v4-flash`, probe `<scratchpad>/card56/think_probe_s1.py` (adapted from `2026-10-06_card56/raw/think_probe.py`, adding session memory and the retry capture). Raw rows: `<scratchpad>/card56/live_q1.jsonl` to `live_q4.jsonl`. Run on commit f3b431a3; the two later commits change only a known organism beside unplaced conditions on a records question (lookup skipped, same outcome) and twice-empty runs of names Taxonomy does not know, which no run produced.

| Question | Runs | Organism route on 2697049 | Read by the lookup, plan line shown | Read after the content retry | Wrong subject | "Illumina" refusal (slice 2) |
|---|---|---|---|---|---|---|
| "Find SRA runs of SARS CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched." | 10 | 7 | 1 (tagged as a disease, the round 3 failure shape) | 2 | 0 | 3 |
| The hyphenated question, BRCA1 remembered | 6 | 6 | 0 | 3 | 0 (never bound to BRCA1) | 0 |
| "SRA runs from AML-derived cell lines" | 6 | not applicable; AML bound to its 3 MedGen records on 6 | 0 | 4 | 0 | 0 |
| The hyphenated question, no memory | 7 | 6 | 0 | 2 | 0 | 1 |

Per run, in order (first reply, then what happened):

- Spaced question: organism plus Illumina as gene, refused; disease plus Illumina as organism, read by the lookup with the line; empty, retry tagged the organism; empty, retry tagged the organism; organism plus Illumina as gene, refused; organism; organism plus two conditions as diseases; empty, retry tagged the organism; organism plus Illumina as organism; organism plus Illumina as gene, refused.
- With BRCA1 remembered: organism; organism; empty, retry tagged the organism; organism; empty, retry; empty, retry. No run bound memory.
- AML: empty, retry tagged AML; empty, retry; AML; AML; empty, retry; empty, retry.
- Hyphenated: organism plus Illumina as disease; organism; empty, retry; empty, retry; organism plus Illumina as gene, refused; organism; organism plus a condition as disease.

The content retry fired on 12 of 30 runs and every second reply named the subject. Retry runs took about 1 s longer (for example 4.6, 4.4 and 4.0 s against 4.3, 3.4 and 3.4 s with memory).

Spend: 30 runs, $0.0144 by the probe's cost field ($0.0047, $0.0032, $0.0031, $0.0033), against $0.30 allowed. Live NCBI calls for the measurements in this report: about 30 lookups, no model.

## Suite, lint and commits

- `ruff check .` over the whole repository: all checks passed.
- Gate 2's exact command, `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0. (`graph.py` is in isort's skip list, so a direct file check of it reports a pre-existing order the gate never sees.)
- Gate 4, `pytest -m "not integration" -q -rs --junitxml=unit-results.xml`, once, on 0057ad30: `1 failed, 8138 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 774.86s (0:12:54)`. The one failure is `test_pubtator_act_cap.py::test_a_seven_second_literature_search_is_cut_off_at_six` ("the search ran 7.5 simulated seconds, past the cap"), a timing arm in Act that this branch does not touch; the machine's load average was 17.5 with two reviewers' runs beside it. Run alone three times afterwards: `5 passed` each time.

Commits on `fix/card56-phrase-lookup`, no co-author trailer:

| Hash | Subject |
|---|---|
| f3b431a3 | fix(think): Read an unplaced name whole in NCBI and never cut a word |
| 9b7403bc | fix(think): Look up nothing more when a records question names a known organism |
| 0057ad30 | fix(think): Try a word split out of an unknown name only as a gene symbol |

## For the lead to decide

1. "SARS" alone: the brief expected several; under the fit rules it would be one (Taxonomy 694009, the species "Severe acute respiratory syndrome-related coronavirus"). It cannot reach the lookup today, but if it ever does it binds that species with the plan line. Accept, or require a phrase of one all-capitals word to need a second fit before it binds.
2. "Nothing fits" asks only on SRA and assembly questions and only for phrases the model named. Asking on every record type would turn today's topic-search answers into questions.
3. The plan line names "the organism" with NCBI's scientific name rather than "the virus SARS-CoV-2"; a model-tagged organism gets no reading line (no lookup, no extra call).
4. The content retry costs about 1 s on 40 percent of these questions. By the brief's rule it also fires on a pronoun follow-up whose reply names nothing ("What variants cause it?"), where it adds time and changes nothing; slice 3's memory check may want to skip it there.
5. Twice-empty replies lose "BRCA1-mutant"'s gene (owner's "never a piece"), and a lower-case "sars cov 2" reads nothing. Answered by the owner on 2026-10-17: see "Digit exception" below.

## What was not covered

- Act and Write were not run, so the rendered answer, the buttons on screen and the plan line's place in the UI were not seen.
- The lookup's latency on a cold cache was not measured; the live runs shared one process cache per batch.
- The Gene leg cannot tell a failed lookup from "no such symbol" when the resolver is a stand-in, so a Gene transport failure reads as "no gene fit". Taxonomy and MedGen failures read as unknown and never bind.
- Kimi and other plan models were not run.

## Digit exception

The product owner's answers of 2026-10-17 on the five points above, relayed by the lead:

| Point | Answer |
|---|---|
| 1, 3, 4 | Kept as built, the lead's call: the plan line uses NCBI's scientific name; the retry on pronoun follow-ups is left for slice 3 |
| 2 | Kept: "nothing fits" asks only on SRA and assembly questions; papers questions keep today's topic search |
| 5 | One exception to "never cut a word": a piece of a hyphen-joined word that carries a digit may be tried, only as an exact official human gene symbol |

As built, commit e01a4e72:

- `phrase_lookup.digit_pieces` names the pieces of a hyphen-joined word that carry a digit and pass the shape rule: "BRCA1" in "BRCA1-mutant", "TP53" in "TP53-null". A piece with no digit ("SARS", "COVID", "CoV") and a bare number ("2", "19") are never pieces.
- `_think`'s fallback candidates carry a kind: "whole", "split" (a word split out of a run Taxonomy does not know) or "digit_piece". The gene fallback tries a digit piece only when the question's gene organism is human, the default; in a question naming another organism it is not tried at all, so no human gene answers a mouse question (F-4.7-A-03). The disease fallback and the whole-phrase lookup take "whole" candidates only.
- `_gene_shaped_fallback_candidates` itself is unchanged: it still returns whole words only; the pieces are added in Think.

Tests, in `test_think_phrase_lookup.py`, both ways:

| Arm | What it shows |
|---|---|
| `test_a_digit_piece_finds_its_gene_as_on_develop`, 2 cases | "SRA runs of BRCA1-mutant tumours" binds NCBIGene:672 and "papers on TP53-null cells" NCBIGene:7157, with no MedGen or Taxonomy search for the piece |
| `test_a_digit_piece_that_is_no_gene_is_never_a_disease_or_a_lookup` | "XYZ9" from "XYZ9-derived" is asked of Gene only, never MedGen or Taxonomy, even where MedGen would bind it |
| `test_a_digit_piece_is_not_tried_when_the_question_names_another_organism` | With "mouse" tagged, "TP53" is never asked |
| `test_a_piece_without_a_digit_is_never_tried`, 3 cases | "SARS-CoV-2", "SARS CoV-2", "COVID-19": no piece is asked of Gene or MedGen |
| `test_digit_pieces_are_only_digit_bearing_pieces_of_joined_words` | The pure rule, both ways |

Mutation M7, the digit piece reaching the disease fallback (the disease filter changed from "whole" to "not split"): 2 failed, 139 passed (the XYZ9 arm and the mouse arm, where the piece then reaches the lookup's gene leg in the mouse taxon); restored, `git status` clean of it. The same filter now also holds M6's property, whose original line no longer exists.

Pass lines:

```
Think test files (phrase lookup, SRA fallback, organisms, layer handoff, disease and organism, retry): 162 passed in 11.75s
tests/system_03_search_agent/core/: 1674 passed, 56 skipped, 2 warnings in 106.94s
ruff check .: All checks passed!
isort --check-only on phrase_lookup.py and the test file: clean
```

Residual found while testing: "HIV-1" is offered whole, as intended, but `resolve_disease_mention_to_curies` drops one-character words from its MedGen term, so the whole word searches `HIV[title]` and can bind HIV disease records, as develop does through the piece. That term builder serves every confirmed disease span, so it is left for a separate change rather than altered in this slice.
