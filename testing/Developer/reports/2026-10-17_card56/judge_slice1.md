# Card 56 slice 1, judge round 1

Judge, 2026-10-17, dial position 2. Branch `fix/card56-phrase-lookup` (f3b431a3, 9b7403bc, 0057ad30, e01a4e72) against develop 535943bc. Findings are appended the moment each is established; the verdict comes last.

## Findings

How the probes run: a judge-written script (`<scratchpad>/card56_judge/probes/probe.py`, not the builder's test file) drives the real `think_node`, then `plan_node`, in two detached worktrees, develop 535943bc and the branch e01a4e72, with the Think model's replies, NCBI ESearch and ESummary and `resolve_symbol_to_curie` faked from the code map's E1 values. Each run sits inside `call_budget.query_budget_scope("lookup")`, so "ceiling calls" is what the question's own 20-call ceiling was charged. "DEV" and "BR" lines below are pasted from `probes/cmp.py` output.

### J-56a-01: The content retry replaces a reply that already named a gene, so a second reply that drops the gene loses an answer develop gives

- Severity: major. Worse than develop for a person: yes, on the shape below.
- Where: `src/system_03_search_agent/core/graph.py`, `_content_retry_reason` (the "records" reason fires when `record_type` is sra or assembly and the reply names only genes) and the wiring in `_think` (`if second_reading is not None: classification = second_reading`), commit f3b431a3. The second reply is used whole, never merged with the first.
- Reproduction: question "Find SRA runs for kras mutant lung tumours", first reply `[("kras","gene")]` record_type sra.
  - Second reply `[]`: DEV `resolved: [['kras', 'NCBIGene:3845']]`, plan "searching 3 layers for NCBIGene:3845" (13 calls). BR `resolved: []`, plan "no gene, variant or disease was named, so searching the published literature for: sra, runs, kras, mutant, lung, tumours".
  - Second reply `[("lung tumours","disease")]`: BR asks "I could not find 'lung tumours' as an organism, gene or condition in NCBI, so I cannot tell which organism's SRA sequencing records you want. Ask again naming the organism ..." The person named a gene; develop searched it.
  - With the second call raising `HarnessCallError`, the first reply is kept (`resolved: [['kras', 'NCBIGene:3845']]`), so only a second reply that parses but names less loses the gene.
- Why it matters: the retry's own message tells the model the reply "named no organism or disease whose records are wanted", which invites exactly a reply that swaps the gene for a condition. Every SRA or assembly question naming only a gene pays the second call (probe P3c, "Find SRA runs for BRCA1 mutant tumours": `model_calls: DEV=1, BR=2`, same outcome). A lower-case or title-case gene the word fallback cannot recover ("kras", no digit, not all capitals) is lost outright. Not measured live, so how often the second reply drops the gene is unknown.
- NOT FIXED

### J-56a-02: "Several records fit" is asked on every record type, against the owner's call 8, which limits asking to sequencing and assembly questions

- Severity: major as a departure from an owner's call; low frequency (it needs a phrase MedGen binds nothing for and Taxonomy files under two or more records). Worse than develop for a person: yes, a papers question that searched now asks.
- Where: `src/system_03_search_agent/core/graph.py`, the ask block at the end of the lookup in `_think`: `if several_fits:` returns `_ask_back(...)` with no `record_type` test; only the "none" branch tests `classification.record_type in breadth_plan.ORGANISM_RECORD_DBS`. Commit f3b431a3. `DECISIONS.md` row of 2026-10-17, call 8: "a name that fits nothing or several records is asked about only on sequencing and assembly questions ... a papers question keeps today's PubMed search of the typed words". `build_slice1.md` states "several, always", and the lead's relay of point 2 there mentions only "nothing fits".
- Reproduction: "Recent papers on Flavivirus X1 vectors in Brazil", reply `[("Flavivirus X1","disease")]`, record_type none, Taxonomy faked to answer two ids for the phrase.
  - DEV: `clarification: None`, plan "no gene, variant or disease was named, so searching the published literature for: flavivirus, x1, vectors, brazil".
  - BR: `clarification: 'Flavivirus X1' matches more than one NCBI record, so I have not picked one for you. Choose the one you mean below, or ask again using its full name.`, options `['Recent papers on the organism NCBI Taxonomy 9001 vectors in Brazil', ...]`, plan None.
- Why it matters: the owner chose that a papers question keeps its search. The buttons also read oddly when Taxonomy gave no scientific name ("the organism NCBI Taxonomy 9001"). No test pins call 8's "several" half: no arm asks a papers question with several fits.
- NOT FIXED

### J-56a-03: Search conditions the model tagged as diseases use up the two-phrase cap, and the person is asked to name an organism they already named

- Severity: minor. Worse than develop for a person: no (develop answered about the disease SARS on the same reply), but the ask is wrong about what the person typed.
- Where: `_read_whole_phrases` in `_think` reads model phrases in the model's order before any fallback candidate; `LookupBudget.take_phrase` (`core/phrase_lookup.py:284`) refuses the third phrase, and the "none" ask quotes only the model's phrases. Commit f3b431a3.
- Reproduction:
  - "Find SRA runs of SARS CoV-2 sequenced on Illumina from clinical respiratory samples", reply `[("Illumina","disease"),("clinical respiratory samples","disease"),("SARS CoV-2","disease")]`. Taxonomy was asked `['Illumina[All Names]', 'clinical respiratory samples[All Names]', 'SARS CoV-2[All Names]']` (the third by the disease path's organism check, never by the lookup). BR: `resolved: []`, clarification "I could not find 'Illumina' or 'clinical respiratory samples' as an organism, gene or condition in NCBI, so I cannot tell which organism's SRA sequencing records you want. Ask again naming the organism as NCBI spells it ...".
  - Same question, reply `[("Illumina","disease"),("respiratory samples","disease")]` (the virus untagged): same ask; the whole-word candidate "SARS CoV-2" is never looked up because the cap is spent.
- Why it matters: the acceptance says "SARS CoV-2" reads as the virus however the model tagged it; on this shape it does not, and the person who typed the organism is told to type the organism. Model-tagged conditions are exactly slice 2's subject, so the shape is live today (the builder saw "organism plus two conditions as diseases" and "Illumina as disease" in its 30 runs).
- NOT FIXED

- Correction to J-56a-03's first reproduction bullet: the third Taxonomy search, `SARS CoV-2[All Names]`, is `phrase_lookup.split_unplaced_runs` checking the fallback run, not the disease path. So on that run the code had already learned Taxonomy files "SARS CoV-2" under one record, and still asked the person which organism, because the phrase cap was spent.

### J-56a-04: On a reply that names nothing twice, two adjacent capitalised words are joined into one run and the disease develop binds is lost

- Severity: minor (needs two empty model replies). Worse than develop for a person: yes.
- Where: `phrase_lookup.name_runs` and `_continues_a_name` (`core/phrase_lookup.py:162` to `:212`) join "AML MDS" and "ALS/FTD"; `split_unplaced_runs` (`:435`) then marks each word `split_out`, and `_think`'s disease fallback takes `kind == "whole"` only. Commit 0057ad30, the fix round's second commit.
- Reproduction, both replies `[]`:
  - "SRA runs from AML MDS patients": DEV `resolved: [['AML', 'MedGen:C1759111'], ['AML', 'MedGen:C0023467'], ['AML', 'MedGen:C348707']]`; BR `resolved: []`, plan "searching the published literature for: sra, runs, aml, mds, patients". Taxonomy asked `AML MDS[All Names]`; MedGen never asked for AML.
  - "papers on ALS/FTD genetics", record_type none: DEV `resolved: [['ALS', 'MedGen:C0002736']]`; BR `resolved: []`, topic search "als, ftd, genetics".
- Why it matters: "ALS/FTD" is a standard way to write the pair. The text rule cannot tell two acronyms from one name, and the Taxonomy check only says "not an organism", so a split word loses its disease reading. A finding inside a fix made during this phase.
- NOT FIXED

### J-56a-05: A digit piece takes one of the three fallback slots, so "BRCA1-mutant TP53-null" binds BRCA1 and loses TP53, which develop binds

- Severity: minor (needs two empty model replies). Worse than develop for a person: yes.
- Where: `_fallback_candidates` in `_think`, `expanded[:_MAX_FALLBACK_CANDIDATES]` after adding `(piece, "digit_piece")` items, commit e01a4e72, the newest fix. The two hyphen words are also joined into one run by J-56a-04's rule.
- Reproduction: "Find SRA runs of BRCA1-mutant TP53-null tumours", both replies `[]`. DEV `resolved: [['BRCA1', 'NCBIGene:672'], ['TP53', 'NCBIGene:7157']]`; BR `resolved: [['BRCA1', 'NCBIGene:672']]`; genes asked on BR `[['SRA', 'human'], ['BRCA1', 'human']]`, Taxonomy asked `BRCA1-mutant TP53-null[All Names]`.
- Why it matters: the owner's call 9 was made so the double miss keeps the gene develop finds; with two such words it keeps one. A finding inside the newest fix of this phase.
- NOT FIXED

### J-56a-06: When NCBI Taxonomy fails, a gene beside another capitalised word is no longer tried, though develop finds it with no Taxonomy call

- Severity: minor (needs two empty replies and a Taxonomy failure). Worse than develop for a person: yes.
- Where: `split_unplaced_runs` (`core/phrase_lookup.py:459`): `if taxids is None or taxids:` keeps the run whole when the check could not run; the gene fallback then tries only `is_single_token` candidates. The same holds when the lookup's ten calls are spent before the check, since a refused call reads as None (`LookupBudget` docstring, `:266`). Commit 0057ad30.
- Reproduction: "Show BRCA1 ClinVar variants", both replies `[]`, record_type none, Taxonomy search raising. DEV `resolved: [['BRCA1', 'NCBIGene:672']]`, no Taxonomy call. BR `resolved: []`; Taxonomy asked twice for `BRCA1 ClinVar[All Names]`, MedGen asked `BRCA1[title] AND ClinVar[title]`. With Taxonomy up, BR binds BRCA1 (probe P10b).
- Why it matters: "never cut a word on a guess" is applied to a gene develop never needed Taxonomy for, so an outage of a database the question is not about removes the gene.
- NOT FIXED

### J-56a-07: A stalled content retry holds Think for its whole 45-second budget, on questions develop answers at once

- Severity: minor to major, the owner's to weigh against "every answer within 20 s". Worse than develop for a person: yes, when the plan-tier provider stalls on the second call.
- Where: `_think`'s retry wiring, `_await_within_step(retry_task, step_deadline, None, point="think.content_retry", ...)`, with `budget_s=budget_for_step("think", "lookup")` in `_run_think_content_retry`; `budget_for_step("think", "lookup")` prints 45.0. Commit f3b431a3.
- Reproduction: Think model faked so the second Think call sleeps 60 s.
  - "What variants cause it?" with BRCA1 remembered, first reply `[]`, record_type none: BR `think_s: 45.01, model_calls: 2`, log line "decision think.content_retry still running when its step's budget ran out (trace t-judge); taking its default"; DEV, same first reply, `think_s: 0.01, model_calls: 1`. Both then answer about BRCA1.
  - "Find SRA runs of SARS CoV-2 sequenced on Illumina", first reply `[]`: BR `think_s: 45.01`, then reads 2697049 correctly.
  - A 5-second stall: BR `think_s: 5.01`.
- Why it matters: the retry fires on every reply naming no gene, disease or organism, which includes every pronoun follow-up ("What variants cause it?", "and what about it in children?"), lower-case "brca1", GCK when the model misses it, a variant-only reply ("TP53 R175H" tagged as variant) and a drug question ("metformin" tagged other): `model_calls: DEV=1, BR=2` on each in the probes. The build report measured about 1 s per retry on a healthy provider; a stall costs up to 45 s, where develop would not have waited at all. Mutation MJ6 (the retry's deadline moved an hour later) stays green, 162 passed, so nothing pins the bound either.
- NOT FIXED

### J-56a-08: Five properties the change states have no test: mutating each leaves all 162 Think tests green

- Severity: minor (instrument). Worse than develop for a person: no, by itself.
- Where and what, each mutation applied alone in a judge worktree, run against `test_think_phrase_lookup.py`, `test_think_sra_disease_fallback.py`, `test_think_organisms.py`, `test_layer_handoff.py`, `test_think_disease_and_organism.py`, `test_think_retry.py`, then restored (`git status src` empty after each). Baseline `162 passed in 10.33s`.
  - MJ3, the plan line kept whole (`graph.py`, `think_narrative = (think_narrative[: max(500 - len(clause), 0)] + clause)[:500]`, build report row "Plan line kept whole"), reverted to develop's `(think_narrative + clause)[:500]`: `162 passed in 11.27s`.
  - MJ5, "A span whose check could not run is in neither list" (`_organism_spans_rejected` docstring), `is False` changed to `is not True`: `162 passed in 11.26s`.
  - MJ6, the retry's step deadline moved one hour later: `162 passed in 13.41s`.
  - MJ7, "kept whole ... when the check could not run, so a name is never cut on a guess" (`split_unplaced_runs` docstring), `if taxids is None or taxids:` changed to `if taxids:`: `162 passed in 10.43s`.
  - MJ12, the second reply used only when it names something (the opposite of J-56a-01's replace rule): `162 passed in 10.74s`. Nothing pins whether a second reply replaces or keeps the first.
  - MJ10, "several" asked only on records questions (owner call 8, J-56a-02): `162 passed in 10.88s`. Nothing pins call 8's "several" half either way.
- Why it matters: Review_rounds.md, "A code comment that claims a ... correctness property is a claim to be tested". Two of these (MJ5, MJ7) are docstring claims; MJ3 is a stated build-report property.
- NOT FIXED

- Live check for J-56a-04 and J-56a-05, NCBI E-utilities, 2026-10-17, no key: Taxonomy `AML MDS[All Names]` 0, `ALS FTD[All Names]` 0, `BRCA1-mutant TP53-null[All Names]` 0 (so each run is split, as in the probes); MedGen `ALS[title]` 6, `AML[title]` 3, `FTD[title]` 3 (so develop's whole-word fallback binds ALS and AML live). Taxonomy `COVID-19[All Names]` and `SARS CoV-2[All Names]` each 1, 2697049, matching the fakes.

### J-56a-09: With a gene remembered, "sars-cov-2" in lower case, named by no reply, is still searched as the remembered gene

- Severity: minor. Worse than develop for a person: no, the same as develop; it is the A2 failure surviving for one spelling.
- Where: `phrase_lookup.admits_token_shape` (`core/phrase_lookup.py:150`) admits no piece of "sars-cov-2", so there is no candidate and nothing to look up; Plan's memory binding then runs as on develop. The build report states "sars cov 2" in lower case "binds nothing", but not that with memory it binds the remembered subject.
- Reproduction: "Find SRA runs of sars-cov-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched." with BRCA1 remembered, both replies `[]`. DEV and BR alike: `resolved: []`, plan "searching 3 layers for NCBIGene:672 ...". BR spends the second model call (`model_calls: DEV=1, BR=2`).
- Why it matters: the acceptance's first sentence ("a name the system cannot place at first is looked up whole") does not reach a name typed in lower case when both replies miss it, and the result is the confident wrong subject. Slice 3 (the memory check) is where this is meant to close; filed so the slice 1 close does not claim it.
- NOT FIXED

### J-56a-10: The cap's comment says a lookup takes up to six calls; it takes seven, measured

- Severity: minor (instrument, a confident sentence). Worse than develop for a person: no.
- Where: `core/phrase_lookup.py:73` to `:77`: "A lookup takes up to six: one Taxonomy search, up to three for the gene (Datasets, ESearch, ESummary), two for MedGen (search and summary ...), and one Taxonomy summary". The parts listed sum to seven.
- Reproduction: `look_up("ABC1", "human", LookupBudget("lookup"))` with the gene resolver charging three calls, Taxonomy two ids, MedGen one record: searches `[('taxonomy', 'ABC1[All Names]'), ('medgen', 'ABC1[title]')]`, summaries `[('medgen', ('9',)), ('taxonomy', ('1', '2'))]`, three gene calls: seven. The second phrase was then refused at the transport after three more ("MedGen disease search failed: CallBudgetExceededError", "Taxonomy name lookup failed: CallBudgetExceededError"), `calls_used: 10`, outcome `('several', 2, False)`; the third phrase got `None`. The cap itself holds: the question's own count stayed at 5 before and after.
- Why it matters: two lookups of symbol-shaped phrases cannot both complete inside ten calls, so the second reads as "unknown" or "several" with incomplete data more often than the comment implies.
- NOT FIXED

### J-56a-11: On an SRA or assembly question, the whole word "HIV-1" now binds HIV disease records where develop bound nothing

- Severity: major in kind (the card's own failure class: a virus read as a disease on a records question), rare in rate (it needs two replies naming nothing; the builder saw 0 of 12 second replies empty). Worse than develop for a person: yes.
- Where: `_think`'s disease fallback now takes "whole" candidates on every record type, replacing #186's skip (diff hunk at old `graph.py:4519`), and runs before the whole-phrase lookup; `resolve_disease_mention_to_curies` drops one-character words, so "HIV-1" searches `HIV[title]`. Commit f3b431a3. The build report's residual says this binds "as develop does through the piece"; on an SRA or assembly question develop skipped the piece (#186), so that sentence holds only for other record types.
- Reproduction: "Find SRA runs of HIV-1 from Kenya", both replies `[]`, record_type sra.
  - DEV: `resolved: []`, plan "no gene, variant or disease was named, so searching the published literature for: sra, runs, hiv-1, kenya".
  - BR: `resolved: [['HIV-1', 'MedGen:C0019682'], ['HIV-1', 'MedGen:C0019693']]`, narrative "(HIV-1: 2 MedGen records matched by name)", plan "Layer 1, the knowledge graph: cypher_query". The lookup, which would have read Taxonomy 11676, never runs because the disease fallback bound first.
  - Live, 2026-10-17: MedGen `HIV[title]` 36 records; Taxonomy `HIV-1[All Names]` 1, 11676.
- Why it matters: the person asked for HIV-1 sequencing runs and gets a graph answer about the disease. Any virus written as letters, hyphen, one digit ("HIV-1", "HTLV-1", "HSV-1", "HPV-16" has two digits and is kept) meets the same path.
- NOT FIXED

### J-56a-12: An organism the model tagged that Taxonomy files under several records is not asked about on a records question

- Severity: minor. Worse than develop for a person: no, the same as develop.
- Where: `_organism_spans_rejected` passes on only spans with zero Taxonomy records, and `organism_route_ahead` (commit 9b7403bc) skips the lookup whenever any organism span was not rejected; `resolve_organism` then needs exactly one id, so a span with several ids neither binds nor reaches `several_question`.
- Reproduction: "Find SRA runs of HIV from Kenya", reply `[("HIV","organism")]` sra, Taxonomy faked with two ids (live `HIV[All Names]` is 5, code map E1): DEV and BR alike `resolved: []`, `clarification: None`, plan "searching the published literature for: sra, runs, hiv, kenya". The same for "Which influenza genome assemblies are complete?", `[("influenza","organism")]` assembly.
- Why it matters: the acceptance says that on sequencing and assembly questions "several ... is asked about with choices"; for the commonest shape of "several", a model-tagged organism name, the person gets a literature search on the words instead. Filed so the slice does not claim it.
- NOT FIXED

### J-56a-13: Think can now make three plan-tier calls on one question, though the retry's docstring says "Never a third call"

- Severity: minor. Worse than develop for a person: slightly slower and dearer on this path only.
- Where: `_run_think_content_retry` docstring, "Never a third call", in `graph.py`; the content retry runs after `_run_think_classification`, whose own parse retry may already have made two calls. Commit f3b431a3.
- Reproduction: "Find SRA runs of SARS CoV-2 sequenced on Illumina", replies in order: unparseable text, `[]`, `[("SARS CoV-2","organism")]`. DEV `model_calls 2` (and binds the three SARS disease records); BR `model_calls 3`, binds NCBITaxon:2697049.
- Why it matters: the outcome is right, but the sentence is a coverage claim a reader will trust; the stall in J-56a-07 can follow two calls rather than one.
- NOT FIXED

## Checklist evidence

### 1. Correctness, run the way production runs it

`think_node` then `plan_node`, model and NCBI faked, develop against branch. "Bound" is `resolved_entities`; "route" is the plan narrative.

| Case | Develop | Branch |
|---|---|---|
| A1 "SARS CoV-2" tagged organism | 2697049, SRA by organism | Same, 1 model call, no lookup |
| A1 "SARS CoV-2" tagged disease | 3 SARS MedGen records, graph query | 2697049, SRA by organism, line "Read 'SARS CoV-2' as the organism Severe acute respiratory syndrome coronavirus 2 (NCBI Taxonomy 2697049)" |
| A1 empty twice ("SARS CoV-2", "SARS CoV 2") | 3 SARS records | 2697049 with the reading line, 2 model calls |
| A1 empty, then tagged disease | 3 SARS records | 2697049 with the reading line |
| A1 "sars-cov-2" empty twice | nothing, topic search | nothing, topic search |
| A1 "COVID-19 virus" empty twice | nothing | 2697049 via "COVID-19" |
| A2 hyphenated, BRCA1 remembered, empty twice | BRCA1 gene fan-out (13 calls) | 2697049, SRA by organism |
| A2 spaced, BRCA1 remembered, empty twice | 3 SARS records | 2697049, SRA by organism |
| A3 "AML" tagged disease | 3 AML records | Same |
| A3 empty twice | nothing, topic search | nothing, topic search |
| A4 organism plus "Illumina" as gene | refusal, unresolved ['Illumina'] | Same (slice 2) |
| A4 disease plus "Illumina" as gene | refusal | Same |
| F21 GCK, tagged and empty | NCBIGene:2645, gene fan-out | Same; empty costs 2 model calls |
| F78 MODY | MedGen:C1833382 | Same, no Taxonomy call |
| F1 then F20 "What variants cause it?" | BRCA1 by memory | Same, 2 model calls |
| F111 "and what about it in children?" | BRCA1 by memory | Same, 2 model calls |
| F76 "and BRCA2?", tagged and empty | NCBIGene:675 | Same |
| F24 MLH1, MSH2, colorectal cancer | 4292, 4436, C0009402 | Same |
| F34 isolates, tagged and empty | NCBITaxon:590, pathogen_detection | Same, 1 model call, no lookup |
| F70 "any trials for gerd?" | C0017168 | Same |
| F103 M. tuberculosis assemblies; SARS-CoV-2 tagged organism | 1773 assembly; 2697049 SRA | Same |
| rs334; lower-case "brca1" empty | dbSNP:rs334; NCBIGene:672 | Same; "brca1" costs 2 model calls |

Confirmed spans never reach the lookup: on the branch F21, F78, F1, F76, F24, F34, F70 and rs334 made no Taxonomy search at all, and F103 and A1-organism made only the span's own `[All Names]` search, exactly as develop.

### 2. The owner's calls

| Call | Held? | Evidence |
|---|---|---|
| 1, whole phrase, one fit used and named | Yes, with gaps J-56a-03, J-56a-09, J-56a-11, J-56a-12 | Table above |
| 4, retry then guarded fallback | Yes for the SARS forms; regressions J-56a-04, J-56a-05, J-56a-06 | P6, P7, P8, P10 |
| 8, ask only on sequencing and assembly | "None": yes (papers question with an unplaced name searches, M2). "Several": no, J-56a-02 | P1 |
| 9, digit piece only as an exact human gene | Yes: "SRA runs of BRCA1-mutant tumours" binds 672; "papers on TP53-null mouse embryos" with mouse tagged asks Gene for "TP53-null" in mouse via the lookup, never "TP53" | N4, N5 |
| Never re-check a confirmed span | Yes | Section 1 |
| Cap, two phrases and ten calls outside the 20 | Yes: question count 5 before and after three lookups, `calls_used: 10`, third phrase `None`; gene questions' ceiling counts equal develop's (BRCA1 2 and 2, GCK empty 2 and 2, MLH1 and MSH2 6 and 6, BRCA9 5 and 5); `MAX_LAYER_2_3_CALLS_PER_QUERY` 20 on both | Cap probe; ceiling probe |
| Isolate, accession and window paths untouched | Yes: F34 and a mixed isolate plus "SARS CoV-2" question bind 590 with 1 model call; "PRJNA614995" gives develop's "BioProject PRJNA614995 was not found in NCBI. Check the accession and ask again."; an assembly-less window gives develop's GRCh38 or GRCh37 question; each with 1 model call | Ceiling probe C5, C6, C8 |
| The ask's wording | Says what to type ("Ask again naming the organism as NCBI spells it, for example "SRA sequencing records of Escherichia coli"" and "Choose the one you mean below, or ask again using its full name"); names no persona and belittles no one. Wrong about what the person typed in J-56a-03 | P1, P2, C7 |

### 3. The content retry

- Fires: a reply naming no gene, disease or organism (pronoun follow-ups, variant-only, "other"-only, empty), and an SRA or assembly reply naming only genes.
- Does not fire: a typed identifier (rs334), an isolate question (F34), an accession (C5), a window (C6): `model_calls 1` each. Small talk is gated in code (`_is_small_talk`); not probed by me.
- Cost: one plan-tier call; up to the rest of Think's 45 s when the call stalls (J-56a-07); a third Think call after a parse retry (J-56a-13).
- Second call fails: `HarnessCallError` keeps the first reply (P5, P5c: kras kept); unparseable text keeps it (P5b); a stall past the step deadline keeps it at 45.01 s (H1, H2). A second reply that parses but names less replaces the first (J-56a-01), which is where an answer develop gives is lost.

### 4. Break it

One property each, in a separate judge worktree, against the six Think test files, restored after each (`git status src` empty). Baseline `162 passed in 10.33s`.

| Mutation | Result |
|---|---|
| MJ1a, the ten-call cap's reserved slots not charged | Red: 2 failed (`test_the_lookup_budget_is_ten_calls_apart_from_the_question_ceiling`, `test_a_lookup_past_the_call_cap_is_unknown_and_binds_nothing`) |
| MJ1b, the lookup charges the question's own ceiling | Red: 3 failed |
| MJ2, the MedGen cache key not case-folded (`_disease_lookup_key`) | Red: 19 failed |
| MJ4, the "nothing fits" ask sends `[]` instead of no options | Red: 1 failed |
| MJ8, "none" asked for fallback words as well as model phrases | Red: 3 failed, including both memory follow-up arms |
| MJ9, no retry on a records reply naming only genes | Red: 1 failed |
| MJ11, the organism reading line dropped | Red: 12 failed |
| MJ3, MJ5, MJ6, MJ7, MJ10, MJ12 | Green, J-56a-08 |

A first MJ1 that set the scope handle to None went red by crashing in `reset_query_budget`; not counted, since it removed a working symbol rather than a property.

### 5. Gates, in a detached judge worktree of e01a4e72

- `ruff check .`: "All checks passed!", exit 0.
- `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02's command): exit 0, "Skipped 2 files".
- `tests/system_03_search_agent/test_debugging_guide_coverage.py`: `7 passed in 1.75s`.
- `tests/system_03_search_agent/core/`: `1674 passed, 56 skipped, 2 warnings in 120.41s (0:02:00)`.
- `test_pubtator_act_cap.py` alone, three times, load average 11.5: `5 passed in 6.72s`, `5 passed in 6.73s`, `5 passed in 6.74s`. The failing arm drives `act_node` directly with `_build_layer_tool_calls` and scales Act's clock by `_SCALE = 10.0`, so a loaded machine stretches its wall time; the branch's `graph.py` diff has 24 hunks, all in Think, the disease cache and `_ask_back`, and none names `act_node`, `_build_layer_tool_calls`, `_LAYER_TOOL_ACT_TIMEOUT_SECONDS` or `enforce_timeout` (count 0). The branch cannot touch it.

## What I verified by my own probes and what I only read

- Verified by probe: every row of section 1; J-56a-01 to J-56a-07, J-56a-09 to J-56a-13; the cap and ceiling; the fixed-rule paths; the retry's failure handling and timing; all mutations; all gates; five Taxonomy and five MedGen counts live.
- Read only, not run: the rendered answer, the buttons on screen and where the reading line appears in the UI (Act and Write not run); how often a live model's second reply drops a gene (J-56a-01) or returns empty (J-56a-04, J-56a-05, J-56a-06, J-56a-11); small-talk gating of the retry; `_quoted`'s handling of markup in a quoted phrase.
- The fakes return the code map's measured counts; a fake cannot show what NCBI does under a key or under load.

## Verdict

FAIL against the slice's acceptance.

- "Everything that answers today answers the same way" does not hold: J-56a-01 (a gene lost to the retry's second reply), J-56a-11 (an HIV-1 SRA question answered as the disease), J-56a-04, J-56a-05 and J-56a-06 (diseases or genes develop binds on a double miss), and J-56a-07 (a stalled retry adds up to 45 s where develop waits for nothing).
- The owner's call 8 is not built as decided for "several" (J-56a-02).
- Findings inside fixes made during this phase, for the stop condition: J-56a-04 and J-56a-06 sit in 0057ad30, J-56a-05 in e01a4e72 (the newest commit), J-56a-12 in 9b7403bc.
- What holds, by probe: the card's own SARS forms read as 2697049 whether tagged disease, organism or nothing; no piece without a digit is ever a candidate; confirmed spans never reach the lookup; the cap and the 20-call ceiling; the isolate, accession and window paths; the ask's wording.
