# Card 56 diagnosis: organisms and accessions in Think

Read-only diagnosis, 2026-10-05, against develop (guest sessions, no sign-in, no tokens saved). Raw event logs and NCBI answers are in `raw/`.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Reproduction table](#reproduction-table)
- [How entity resolution works today](#how-entity-resolution-works-today)
- [The cause](#the-cause)
- [The D9 measurement](#the-d9-measurement)
- [Fix options](#fix-options)
- [Recommendation](#recommendation)
- [What was not covered](#what-was-not-covered)

## What the person sees

- SARS-CoV-2 question: an answer about a disease called SARS, one record "SARS Coronavirus Protease Pathway", flagged "Based on 1 source, not yet confirmed". No SRA runs. A note says the answer does not address "Probable SARS" and "SARS (severe acute respiratory syndrome) confirmed", which the person never asked about.
- Mycobacterium tuberculosis assemblies question: "which gene, variant or condition do you mean?" and an example about BRCA1. The question named an organism and a database record type and gets asked for a gene.
- Salmonella isolate question: asked "which resistance gene or gene family should the isolates carry?", although the question already asks which AMR genes the isolate carries. No search runs.

## Reproduction table

Ten live questions were spent of the ten allowed. Files: `raw/sars_run{1..3}.json`, `raw/g036_run{1,2}.json`, `raw/g004_run{1,2}.json`.

| Question | Run | Entity Think resolved | Tools that ran | Answer |
|---|---|---|---|---|
| SARS-CoV-2 SRA (G-005, card 56) | 1 | 3 MedGen records for the span "SARS" (C1519126, C4302012, C4302019) | cypher_query, 2 pubtator_annotate, clinicaltrials_search, 4 ncbi_efetch (medgen) | One MedGen record, outcome ask, 13 s |
| SARS-CoV-2 SRA | 2 | Same three | Same eight calls | Same record, plus a note that a background search did not finish, 47 s |
| SARS-CoV-2 SRA | 3 | Same three | Same eight calls | Same record, 19 s |
| M. tuberculosis assemblies (G-036) | 1 | None | None | Refusal asking for a gene, variant or condition, 6 s |
| M. tuberculosis assemblies | 2 | None | None | Same refusal, 6 s |
| Salmonella isolate (G-004) | 1 | None | None | Asks which resistance gene, 24 s |
| Salmonella isolate | 2 | None | None | Same, 4 s |

Result: 3 of 3 SARS-CoV-2 runs resolved the wrong entity (the disease), 2 of 2 G-036 and 2 of 2 G-004 resolved nothing and ran no tool. On this day the SARS-CoV-2 failure was steady, not intermittent. The older "refused in some runs" pattern (Think returns nothing) is the same cause with a different roll of the dice, see below.

## How entity resolution works today

Steps in order, all in `src/system_03_search_agent/core/graph.py` unless noted.

1. `_think` (line 3724) starts. Three fixed-rule recognisers run first, no model: `resolve_exact_identifiers` (typed CURIEs, rs numbers, PMIDs, line 5057), `coordinate_window.parse_coordinate_window` and `accession.parse_accession` (`core/accession.py`, regex for BioProject, BioSample, SRA run and assembly accessions, then `resolve_accession` line 3260), and `isolate_search.parse_isolate_question` (`core/isolate_search.py`).
2. The isolate recogniser needs an isolate word ("isolate", "Pathogen Detection") in the text (`_ISOLATE_WORDS`, line 206) and then looks for an organism in a hand-written table `ORGANISMS` (line 102, 20 organisms with regexes and taxonomy ids) plus a resistance gene family word. The table is a word list.
3. One model call, `_run_think_classification` (line 3525), with `_THINK_SYSTEM_INSTRUCTION` (line 2353). It returns a query class and a list of spans, each typed by `_ThinkExtractedEntity` (line 2301) as gene, disease, organism, variant or other. The prompt asks for only gene, organism and disease. Task 2 tells the model not to extract isolate, run, project or accession identifiers as genes.
4. `_confirm_extracted_entities` (line 2995) confirms spans live. Gene spans go to `resolve_symbol_to_curie` (line 5352). Disease spans go to `resolve_disease_mention_to_curies` (line 2861, MedGen esearch). Organism spans do exactly one thing: `_confirmed_taxon_for_extraction` (line 2785) checks them with `_organism_is_known` (line 2734, esearch db=taxonomy) and `_taxon_for_extraction` (line 2687) returns the span as the species to resolve gene symbols against. The organism never becomes a resolved entity or a CURIE. The code comment at line 2307 says this outright: only gene is confirmed live, the other types "never contribute a CURIE".
5. If nothing resolved, two fallbacks run: `_gene_shaped_fallback_candidates` (line 3158) takes tokens of 2 to 8 characters that are all capitals or contain a digit, and tries them as genes, then as MedGen disease mentions (the D3 fallback in `_think`, about line 3900).
6. With no resolved entity and no accession or isolate shape, Plan has nothing to bind. The ask-back text at line 5942 says "which gene, variant or condition do you mean?".

## The cause

Three separate mechanisms, one root: an organism is not an entity type that Think can resolve. It is only a modifier on a gene lookup.

- SARS-CoV-2 read as the disease "SARS": the model's organism span (if it gave one) is dropped on the floor because nothing consumes it. With no gene or disease resolved, the fallback at step 5 splits "SARS-CoV-2" on the hyphen. The token pattern `\b[A-Za-z0-9]{2,8}\b` yields "SARS" (all capitals, so it passes the shape rule), and "SRA" ahead of it. MedGen answers "SARS" with 3 disease records, and the narrative even says "SARS: 3 MedGen records matched by name". The retired-guess protections check that a token confirms live, but MedGen confirming a name does not prove the name is the thing the person meant. The live NCBI Taxonomy answer for "SARS-CoV-2" (taxid 2697049) is never asked for. The raw Think model output was not logged in the event stream, so whether the model returned an organism span on these runs is inferred from the code path, not seen.
- G-036: Mycobacterium tuberculosis is in the `ORGANISMS` table, but the table is only consulted when the question contains an isolate word. "Genome assemblies" is not one. No assembly or genome-assembly path exists for an organism. The model tags the organism, nothing consumes it, nothing resolves, step 6 fires.
- G-004: the question has an isolate word and an organism (Salmonella enterica), so the isolate recogniser fires. It needs a resistance gene family or gene token to build a search. The question asks which AMR genes the isolate carries, so there is none to give. The recogniser returns a clarification asking for a gene family, which the person cannot answer sensibly. The shape needs an isolate accession (an SNP cluster question is about one isolate) and the question has none.

Why it varies run to run: when the model returns no usable span, the fallback decides the entity. Different spans or none give the "refused in some runs" pattern recorded on card 56.

## The D9 measurement

Question D9 in `testing/Board_plan.md`: would semantic matching of a person's words to graph concepts fix these. Every entity mention in the three failing questions, tested against what exact matching returns today and against NCBI's own lookup (`raw/ncbi_lookups.json`, 17 of 30 lookups used, under 3 requests per second).

| Mention | Today's result | Right concept | Fixed by NCBI lookup | Needs semantic matching |
|---|---|---|---|---|
| SARS-CoV-2 | Becomes the disease "SARS", 3 MedGen records, wrong | NCBI Taxonomy 2697049, Severe acute respiratory syndrome coronavirus 2 (esearch db=taxonomy returns exactly 1 hit; "SARS coronavirus 2" returns 0, so the written name matters) | Yes | No |
| SRA runs | Not resolved, read as database name | The SRA database (db=sra), a record type, and txid2697049 in SRA gives 6,183,835 Illumina records | Yes, as a database choice plus the taxon filter | No |
| Illumina | Not resolved | An SRA platform attribute, a filter, not an entity (Taxonomy returns 0) | Not an entity | No |
| clinical respiratory samples | Not resolved | A BioSample or SRA metadata filter in free text | Not an entity | Not shown to need it; untested |
| Mycobacterium tuberculosis | Organism span unused, nothing resolves | Taxonomy 1773 (esearch returns 1 hit, species rank) | Yes | No |
| genome assemblies | Not resolved | The assembly database; txid1773 gives 8,934 assembly records | Yes, as database choice plus taxon | No |
| Salmonella enterica | Matched by the regex `Salmonella` to taxid 590 (genus), only if an isolate word and a gene family are present | Taxonomy 28901, species (esearch returns 1 hit) | Yes | No |
| isolates | Part of the isolate shape | The Pathogen Detection isolate set for that organism | Yes, by the existing table path | No |
| SNP cluster | Not resolved | A Pathogen Detection field of one isolate | Not an entity | No |
| AMR genes | Treated as missing gene family, triggers the clarification | A request for a field, not a gene to resolve | Not an entity | No |

Accessions: none of the three questions contains an accession, so none of the failures is an accession failure. The accession path (`core/accession.py`) is a regex and already works for BioProject, BioSample, SRA run and assembly forms.

Counts: 10 mentions, 3 are organisms and all 3 resolve exactly through NCBI Taxonomy esearch with one call each. The other 7 are record types or filters, which are a database choice by the classifier model, not a concept lookup. 0 of 10 need semantic matching.

## Fix options

| Option | What it does | Size | Risk |
|---|---|---|---|
| 1. Organism as a resolved entity | In `_confirm_extracted_entities`, organism spans that Taxonomy confirms become an entity with a Taxonomy CURIE and a Taxonomy esummary citation (the isolate path already cites organisms to Taxonomy this way). `_gene_shaped_fallback_candidates` skips tokens that sit inside a span the model tagged organism, which stops "SARS" being cut out of "SARS-CoV-2". Plan gets an organism-anchored route for SRA and assembly: an `ncbi_efetch` esearch with a taxon filter. | M to L, mostly Plan | Medium. Plan must handle a resolved entity with no gene, which the graph route does not expect |
| 2. Smaller step: stop the wrong answer first | Do only the fallback guard from option 1, plus change the ask-back text so an organism question asks about the record type, not "gene, variant or condition". | S | Low. Refuses honestly instead of answering with the wrong disease, but still gives no SRA runs |
| 3. Embeddings for graph concepts | Embed concept names and match a person's words. | L, new infrastructure | High. The failing cases are not near-miss spellings, so it fixes none of them |

Both option 1 and option 2 respect the standing rule that the classifier model decides and code only verifies: the model already tags the organism, code confirms it with Taxonomy. No word list is added, and in fact the `ORGANISMS` table could later be retired in favour of the live Taxonomy check.

## Recommendation

Option 2 first (small, removes a confident wrong record, which the owner rule ranks worse than a missing one), then option 1. Do not start with embeddings. Also change the isolate recogniser so an isolate question about one named organism with no gene asks about an isolate accession, or answers organism-level with a sentence that an isolate accession would narrow it (this is the open question on card 33).

Answer for D9: semantic matching is not needed, since 0 of the 10 mentions in the failing questions need it and the 3 organisms resolve with 1 NCBI Taxonomy esearch each.

## What was not covered

- The model's raw Think output (the organism span itself) is not in the event stream, so whether it tagged SARS-CoV-2 as an organism on each run is inferred from the code path. A direct check would run `_run_think_classification` alone several times.
- Plan and Act were not read in depth, so the size of option 1's Plan change is an estimate.
- Only 3 questions, 7 live runs. The intermittent "no entity" pattern on card 56 did not recur, so its rate was not measured.
- Whether "clinical respiratory samples" needs fuzzy matching against BioSample isolation-source text was not measured.
- Accession-shaped questions were not run live. One accession per database kind, resolved against the real database, would settle whether accessions need anything beyond the existing regex path.
- Live NCBI use: 17 of 30 lookups, 7 of 10 live questions.
