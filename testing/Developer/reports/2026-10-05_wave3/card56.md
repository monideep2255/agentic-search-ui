# Card 56: an organism in a question is resolved through NCBI Taxonomy

Owner decision D9, 2026-10-05: organisms are resolved through NCBI's own Taxonomy lookup, with no embeddings and no semantic search. The diagnosis is `testing/Developer/reports/2026-10-05_card56/diagnosis.md`.

## Table of contents

- [The change](#the-change)
- [Choices made](#choices-made)
- [Tests](#tests)
- [Gates](#gates)
- [Live runs](#live-runs)
- [Not covered](#not-covered)

## The change

Two commits on `fix/card56-organisms`.

Commit 1 stops the confident wrong answer:

- A question about SARS-CoV-2 SRA runs no longer becomes an answer about the disease SARS. The token fallback (`_gene_shaped_fallback_candidates` in `core/graph.py`) skips every token inside a span the model tagged as an organism and NCBI Taxonomy did not reject. A span Taxonomy rejects ("MODY", tagged as an organism on 2 of 20 GCK runs) keeps its tokens, exactly as before.
- A question that names an organism and no gene, and needs a question asked back, is asked which kind of record about the organism it wants, in the organism's own spelling. It is no longer asked "which gene, variant or condition do you mean?".
- An isolate question with an organism and no gene is asked the same thing (`isolate_search.record_question`), not which resistance gene the isolates should carry. The `ORGANISMS` table is unchanged.

Commit 2 resolves organisms and routes them:

- Think's classification gains one field, `record_type`: `sra`, `assembly` or `none`, defaulting to `none`. The model decides it from what the question asks for; no word list is involved.
- `resolve_organism` confirms the model's organism span with one ESearch on `db=taxonomy` (`<name>[All Names]`, through `ncbi_eutils_actions.search`, so through the existing NCBI transport, key and rate limit). The lookup is cached and shared with the gene path's existing organism check, so a name costs one call, not two. The result is a `ResolvedOrganism` with its Taxonomy id, the CURIE `NCBITaxon:<taxid>` and the citation `https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=<taxid>` (from `cypher_provenance.source_url_for_curie`).
- When the classifier read `sra` or `assembly`, and nothing else resolved (no gene, disease, typed identifier, failed span, window, accession or isolate shape), the organism becomes the question's resolved entity and Think hands Plan `organism_records`.
- Plan then plans, with no graph call: an `ncbi_efetch` ESearch on `txid<taxid>[Organism:exp]` in `sra` or `assembly`, the organism's Taxonomy ESummary (as the isolate path does), and an ESummary follow-up on up to 10 of the ids the search returned. The summaries reuse the `sra_summary` and `assembly_summary` purposes the accession path already shapes and cites.
- The Think and Plan narratives say the search is by organism alone, so any other condition in the question (a platform, a sample type) is not applied.
- No tool and no integration was added. Every call is `ncbi_efetch`, whose `search` and `summary` enums already list `sra`, `assembly` and `taxonomy` (Technical specification Section 6.2).

## Choices made

These are for the lead to log in `DECISIONS.md`; this branch does not touch it.

| Choice | Alternatives | Why |
|---|---|---|
| The record type is a field on Think's existing classification call | A new `decide()` point; a word list | One model call already reads the question and tags the organism; no new call, no wait, no list |
| The organism becomes a resolved entity only when a record route exists | Always add it | Added unconditionally, `NCBITaxon` would reach the graph call and stop the literature path that organism-only questions take today, a regression for "papers on X" questions |
| A name resolves only when Taxonomy files it under exactly one taxon, and only one organism is named | Take the first hit; pick one of two organisms | A guessed organism is a confident wrong record |
| The resolving lookup reads up to 100 characters of the name | Keep the gene path's 30 | A written-out name such as "Severe acute respiratory syndrome coronavirus 2" is 47 characters; the gene path's 30-character check is unchanged |

## Tests

New file `tests/system_03_search_agent/core/test_think_organisms.py`, 16 tests. Each was run against the code before its commit by copying the old files from git into the worktree and copying the new ones back (no stash).

| Test | Proves | On the old code |
|---|---|---|
| `test_a_token_inside_an_organism_span_is_never_a_candidate` | "SARS-CoV-2" yields no "SARS" candidate; without the span it does | Red |
| `test_a_span_taxonomy_rejects_keeps_its_tokens` | A rejected span ("MODY") keeps its token | Red |
| `test_an_organism_name_is_never_bound_as_a_disease` | Through `think_node`: no MedGen entity, no `SARS[title]` search | Red: the three MedGen records the live runs bound |
| `test_an_organism_question_asks_which_kind_of_record` | The question asked back names the organism and no gene | Red: the gene question |
| `test_a_question_with_no_organism_still_gets_the_gene_question` | Populate check | Green, as it should be |
| `test_an_organism_span_resolves_to_its_taxonomy_record_with_a_citation` | Mocked Taxonomy answer becomes taxid, CURIE and Taxonomy page URL, one search shared with the gene path | Red |
| `test_no_basis_to_pick_one_organism_resolves_nothing` | Two taxa, two organisms or an unknown name resolve nothing | Red |
| `test_a_failed_taxonomy_lookup_resolves_nothing` | A transport failure resolves nothing and is not cached | Red |
| `test_think_resolves_the_organism_for_a_record_question` | Think hands Plan the organism and `sra`, discloses it, asks nothing back | Red |
| `test_with_no_record_type_the_organism_question_is_asked_back` | The classifier's record type, not the organism alone, routes | Red |
| `test_an_organism_and_sra_runs_plan_the_sra_search` | Plan: SRA search on `txid2697049[Organism:exp]`, Taxonomy summary, SRA summary follow-up, no graph call | Red |
| `test_an_organism_and_assemblies_plan_the_assembly_search` | Plan: the assembly path for `txid1773` | Red |
| `test_the_follow_ups_fetch_the_ids_the_search_returned` | Act builds the summaries from the search's ids, sorted and deduplicated | Red |
| `test_a_gene_question_is_unchanged` (two cases) | A resolved gene keeps the graph call first and no organism route, with record type `none` or `sra` | `none`: green, a regression guard; `sra`: red only because the field did not exist |
| `test_the_organism_question_quotes_only_name_characters` | No markup reaches the question | Red |

Existing tests changed to the new intended behaviour, not weakened:

- `test_isolate_search.py` and `test_isolate_search_wiring.py`: the organism-with-no-gene arms now expect the record-kind question.
- `test_layer_handoff.py` and `test_cq_routing_mutation.py`: the two mutations that empty the fallback extractor now accept the new argument. The routing harness's arm had been going red by `TypeError` rather than by the mutation, which would have hidden a real failure.

## Gates

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass, both commits |
| `gate03_lint.sh` (ruff, whole repository) | Pass, both commits |
| `gate04_unit_suite.sh` | 6548 passed, 6 failed. The 6 need a Postgres server on localhost:5432, which this machine does not run: three in `adapters/graphql/test_no_cost_channel.py` and three in `core/test_think_retry.py`. The same 6 fail on `origin/develop` here. CI provides the database |

## Live runs

Think and Plan only, run locally against the real models and NCBI, three runs per question. The script loaded only the model, NCBI and budget settings; no user database, Redis, tracing, analytics or audit log, so nothing was written.

| Question | Runs | Resolved | Plan |
|---|---|---|---|
| SARS-CoV-2 SRA runs on Illumina from clinical respiratory samples | 3 of 3 | SARS-CoV-2, `NCBITaxon:2697049`, record type `sra` | SRA search `txid2697049[Organism:exp]`, Taxonomy summary, SRA summary follow-up; no graph call, no MedGen |
| Mycobacterium tuberculosis genome assemblies | 3 of 3 | Mycobacterium tuberculosis, `NCBITaxon:1773`, record type `assembly` | Assembly search `txid1773[Organism:exp]`, Taxonomy summary, assembly summary follow-up |
| Salmonella enterica isolate SNP cluster and AMR genes | 3 of 3 | Nothing; the isolate shape fires | Asks "Which kind of Salmonella record do you want?" with assemblies, SRA runs and isolates by gene family as examples; no tool |

One read-only probe then ran the two routes' NCBI calls through the real `ncbi_efetch` actions:

- SRA: the search found 7,577,870 records for the taxon, 10 ids, and the summaries shaped into 5 rows led by run accessions, cited to `ncbi.nlm.nih.gov/sra/<uid>`.
- Assembly: the search found 8,934 records, 10 ids, and 5 rows such as `GCF_061389275.1`, "Complete Genome", cited to `ncbi.nlm.nih.gov/assembly/<uid>`.

## Not covered

- Act and Write were not run end to end, live or in a unit test; the answer text for the two routes is unseen. The lead's test queries on develop are the gate.
- The search is by organism alone. "Illumina" and "clinical respiratory samples" are not applied, and the answer cannot explain why each run matched those conditions. The narratives say so, but only Show work carries them (cards 94, 91, 77).
- The record count NCBI holds (7.5 million SRA records, 8,934 assemblies) is not stated under the answer; only the planned cap of 10 is named.
- The Salmonella isolate question still gets no answer. It now asks for the kind of record rather than a resistance gene; answering with what is findable is card 33 (D19).
- A question that names two organisms ("SARS-CoV-2 from human samples", if the model tags both) resolves neither and keeps today's behaviour. Not seen in the 6 live routed runs.
- Record kinds beyond SRA and assemblies (BioSamples, BioProjects by organism) have no route; the classifier reads them as `none`.
