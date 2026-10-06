# Card 56 round 2: adversary report

Branch `fix/card56-r2`, one round, fresh context. Findings are appended as they are established.

## Findings

### A2-56-01: the retry's "organism in the question" check is satisfied by any span tagged organism, so a non-organism question word ("Illumina") lets an invented organism through

- Blocking. Regression of: A-56-05 (inside round 2's fix, `_second_reply_names_a_question_organism`)
- Question typed: "Find SRA runs sequenced on Illumina from clinical respiratory samples" (names no organism)
- What the person sees: no question asked back. Every human SRA run, introduced as "Homo sapiens: NCBI Taxonomy 9606; searching NCBI SRA sequencing records filed under it, by organism alone". The person never typed a species; the model guessed the host
- Evidence: `raw/adversary_r2/offline_r2.py illumina_org_bypass`. First reply `entities: [], record_type: sra`; second reply `[("Illumina", "organism"), ("Homo sapiens", "organism")]`. Log: "asked once more, used the second reply". Output: `model_calls 2`, `resolved [["Homo sapiens", "NCBITaxon:9606"]]`, `organism_records ["Homo sapiens", "9606", "sra", []]`, `clarification null`, Taxonomy searched for `Illumina[All Names]` (no hit) then `Homo sapiens[All Names]`. Cause: `_second_reply_names_a_question_organism` (graph.py, `any(entity.entity_type == "organism" and _span_is_in_question(...))`) accepts the reply if ANY organism-tagged span is question text; `resolve_organism` then drops the Taxonomy-unknown span and resolves the other, the one the person never typed. The check and the resolver look at different spans. Tagging "Illumina" as an organism is a measured live habit of this model: build_r2.md runs 8, 12 and 16 of 22
- Why it matters: this is exactly the confident wrong record A-56-05 asked to close, still reachable through a habit the builder's own live runs show. The person gets a whole species' runs and no sign the organism was a guess
- Suggested fix: run the containment check on the organism `resolve_organism` actually returns (its `mention` must be question text), not on any organism-tagged span; or require every organism span of the second reply to be question text. Test: second reply with one question-text span Taxonomy rejects plus one invented span Taxonomy knows; expect the first reply kept and the organism question asked
- NOT FIXED

### A2-56-02: the containment check matches inside words, so "rat" passes in "respiratory", "human" in "humanized", "pig" in "pigmented", "ant" in "variant"

- Non-blocking (the model must still offer the short name on the retry; unmeasured live). Regression of: A-56-05 (inside round 2's `_span_is_in_question`)
- Question typed: "Find SRA runs sequenced on Illumina from clinical respiratory samples"; "SRA runs of humanized immune system samples"; "Genome assemblies of the pigmented isolates from the outbreak"; "SRA runs of the variant strains from the hospital"
- What the person sees, if the retry offers the short name: every SRA run of rat (`NCBITaxon:10116`), human (9606), pig (9823) or a fruit fly genus answering to "ant" in the fake, with no question asked
- Evidence: `raw/adversary_r2/offline_r2.py substring`, second reply one organism span each: all four logged "used the second reply", `clarification null`, `organism_records` set to the short name. `_name_pattern` has no word boundary; build_r2.md records the choice ("Word boundaries would refuse "SARS-CoV-2" inside "SARS-CoV-2's""). A boundary at the start of the span only, plus letters allowed after it only when followed by an apostrophe, or a check on whole word tokens, would keep "SARS-CoV-2's" and refuse "respiratory"
- Why it matters: "human" inside "humanized" is the realistic one: a humanized-mouse question becomes every human SRA run. The guard was built to refuse an organism the person never typed, and it accepts one cut out of a longer word
- Suggested fix: require the match to start at a word boundary and end at a word boundary or before "'s"; add the four questions above as refusing cases beside the accepted "SARS-CoV-2's"
- NOT FIXED

### A2-56-03: a person who typed "E. coli" or "SARS CoV 2" is asked which organism when the retry spells the name out, and the example offered is the organism they typed

- Non-blocking (not worse than develop, which asked a generic question here; it reads as not listening)
- Question typed: "SRA runs of E. coli from hospital wastewater"; "Find SRA runs of SARS CoV 2 sequenced on Illumina"; "Genome assemblies of M. tuberculosis lineage 2"
- What the person sees, when the first reply names nothing and the retry names "Escherichia coli", "SARS-CoV-2" or "Mycobacterium tuberculosis": "One more detail is needed: which organism's SRA sequencing records do you want? Ask again naming the organism, for example "Escherichia coli SRA sequencing records"."
- Evidence: `raw/adversary_r2/offline_r2.py renamed`, all three "kept the first reply: the second names no organism the question carries", then the question above. The model normalising an abbreviation to the full name is a common habit; the containment check treats it as an invented organism
- Why it matters: the person named the organism and is asked for it, and for E. coli is shown their own organism as the example. Honest, but it will feel like the product did not read the question
- Suggested fix: accept a second-reply organism not in the question when Taxonomy resolves it to the same single taxid as some question span (look up the question's organism-shaped span, or the first reply's), or at least make the organism question name what was not understood. The owner's rule is "a refusal says what to type next"; this one already does, so this is wording and recall, not trust
- NOT FIXED

### A2-56-04: on the test question itself the answer note appears on 5 of 21 organism searches; the other 16 run the identical organism-only search with no note, so whether the person is told depends on how the model tagged "Illumina"

- Non-blocking against the owner's scoped design (the decision row puts the note on the "failed gene that is a search condition" path only), but I would put it to the owner: it is the lying trust signal by omission, and the note's presence is now a coin toss on one question
- Question typed: "Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched."
- What the person sees: on every one of the 21 runs that took the organism route the search is `txid2697049[Organism:exp]` alone (`breadth_plan.plan_organism_records`), Illumina and the sample type not applied. When the model tagged "Illumina" as a gene (runs 9, 11, 14, 17, 20) the answer carries "Illumina was not applied to this search: it finds the SRA sequencing records filed under SARS-CoV-2, by organism only." When it tagged "Illumina" as an organism (runs 8, 12, 15, 16), or did not tag it (runs 1 to 7, 10, 13, 19, 21, 22), the answer carries no note, while Synth is asked by the question to "explain why each one matched"
- Evidence: build_r2.md's own live rows, `raw/r2/sars_runs.jsonl`, field `conditions_not_applied`: non-empty on 5 of 22 rows, organism route on 21 of 22. Offline, `raw/adversary_r2/offline_r2.py note_presence`: the same organism-only search gives `note` = the sentence above for `[SARS-CoV-2 organism, Illumina gene]` (picked condition) and `note: null` for `[SARS-CoV-2 organism, Illumina organism]`, run 12's shape and `[SARS-CoV-2 organism]`; the Think narrative says "any other condition the question names is not applied" on all four, but it lives behind Show work. `_organism_conditions_note` returns None unless `conditions_not_applied` is non-empty. Write gives Synth nothing from `organism_records` (`grep organism_records` in Write finds only the note)
- Why it matters: a person who sees the note on one run and not on the next has every reason to read the second as filtered. A-56-03's fix closed the case where code set a span aside, not the case where the model never tagged it, which is the common one
- Suggested fix: emit the note on every organism-records answer, naming the released spans when there are any ("Only the organism was applied to this search: it finds the SRA sequencing records filed under SARS-CoV-2; other conditions in the question, such as a platform or sample type, were not applied."). build_r2.md lists this as an owner follow-up; I would ask now
- NOT FIXED

### A2-56-05: a person who types an organism's full name of more than 30 characters ("Severe acute respiratory syndrome coronavirus 2") is asked "which organism's SRA sequencing records do you want?", live 2 of 2

- Blocking, in my view; the lead may weigh it as non-blocking because develop also asked a wrong question here (its generic "which gene, variant or condition"). The question text is round 2's new `_which_organism_question` gate; the cause is card 56's own `_organism_spans_not_rejected`, which is on develop
- Question typed: "Severe acute respiratory syndrome coronavirus 2 SRA runs sequenced on Illumina"
- What the person sees: "One more detail is needed: which organism's SRA sequencing records do you want? Ask again naming the organism, for example "Escherichia coli SRA sequencing records"." They named it, in NCBI's own spelling
- Evidence: live, `raw/adversary_r2/live_longname.jsonl`, 2 runs, both `entities` carry `["Severe acute respiratory syndrome coronavirus 2", "organism"]`, both `resolved []`, `ended "asked a question back"`, the clarification above. Offline, `raw/adversary_r2/offline_r2.py long_name`: the only Taxonomy search made is `Severe acute respiratory syndr[All Names]`, and the same for "Salmonella enterica subsp. enterica serovar Typhimurium genome assemblies" (`Salmonella enterica subsp. ent[All Names]`, asked "which organism's genome assemblies"); "Klebsiella pneumoniae SRA runs" (21 characters) takes the route. Cause: `_organism_spans_not_rejected` checks each span with `_organism_is_known`, which cuts the name at `_MAX_TAXON_CHARS` = 30 (graph.py:2940), so a cut name finds nothing and the span is rejected; the organism route needs `organism_spans`, so `resolve_organism`'s 100-character lookup (`_MAX_ORGANISM_LOOKUP_CHARS`, decided for exactly this 47-character name in card 56's DECISIONS row) is never reached
- Why it matters: card 56's decision row names "Severe acute respiratory syndrome coronavirus 2" as a name the organism lookup must read. Round 2 now tells that person, in words, that they did not name an organism. Subspecies and serovar names (Salmonella, Staphylococcus aureus subsp. aureus) hit it the same way
- Suggested fix: check organism spans with `_MAX_ORGANISM_LOOKUP_CHARS` in `_organism_spans_not_rejected` (the gene-taxon path may keep its 30), or let a span `resolve_organism` confirms count as named. Add the 47-character name as a test
- NOT FIXED

### A2-56-06: an SRA question whose subject is a disease, when Think names nothing, now asks "which organism" where develop bound the disease

- Non-blocking: this is the owner's stated design (the disease fallback is skipped on SRA and assembly questions), recorded so the trade is seen with examples. Lives inside round 2's D3 gate
- Question typed: "SRA runs from COVID-19 patients", "SRA runs from MODY patients", "Sequencing runs from CF patients in SRA", each with Think's reply naming nothing (the 5-in-26 habit) on both calls
- What the person sees: "One more detail is needed: which organism's SRA sequencing records do you want? Ask again naming the organism, for example "Escherichia coli SRA sequencing records"." On develop the same replies bound the disease by token (COVID, MODY, CF) and answered about the disease's records. Neither answers with SRA runs; develop's at least names the person's subject, and the E. coli example points a COVID-19 or MODY patient question at a bacterium
- Evidence: `raw/adversary_r2/compare.py develop|branch covid_patients_empty mody_empty cf_empty` (develop's graph.py loaded in place of the branch's, same fakes; MedGen faked to bind one record for the token): develop `resolved [["COVID", "MedGen:C5203670"]]`, `clarification null`, 1 call; branch `resolved []`, 2 calls, the question above. Same for MODY and CF. When the first reply DOES tag the disease, nothing changes from develop (no retry, the model-span lookup binds it)
- Why it matters: the person's real subject (patients with a disease) is dropped, and the example nudges them to the wrong organism. A person who answers "human" gets every human SRA run
- Suggested fix: for the owner, not the builder. If asking is kept, name the disease in the ask ("which organism's SRA runs for COVID-19 patients? for example SARS-CoV-2 or human") is not possible without reading the question, so at least drop the fixed E. coli example in favour of the shape ("naming the species")
- NOT FIXED

### A2-56-04, live evidence added: a gene the person asked about, left untagged, is dropped with no note

- "SARS-CoV-2 SRA runs with the ORF-8 deletion", 2 live runs (`raw/adversary_r2/live_orf8dash.jsonl`). Run 1: the model tagged only `["SARS-CoV-2", "organism"]`, the organism route ran (`NCBITaxon:2697049`, 3 tool calls planned), `conditions_not_applied []`, so the answer lists every SARS-CoV-2 run with no note that ORF-8 was not applied. Run 2: the model tagged "ORF-8" as a gene, the lookup failed, the classifier kept it a gene, nothing was planned, and the answer is the refusal naming ORF-8 as not recognised. The same question gives either a silent all-runs answer or a refusal, and the note this round added fires on neither

### A2-56-07: the retry's second reply may switch the record type from SRA runs to genome assemblies and is still used; the owner's design says it must keep the record type

- Non-blocking (unseen live; the answer would name "genome assemblies", so the person can notice). Inside round 2's fix, `_second_reply_names_a_question_organism`
- Question typed: "Find SRA runs of SARS-CoV-2 sequenced on Illumina", first reply `entities: [], record_type: sra`, second reply `[("SARS-CoV-2", "organism")]` with `record_type: assembly`
- What the person sees: SARS-CoV-2 genome assemblies, not the SRA runs they asked for, with no question asked
- Evidence: `raw/adversary_r2/compare.py branch retry_flips_record_type`: log "used the second reply", `organism_records ["SARS-CoV-2", "2697049", "assembly"]`. The check is `second.record_type in breadth_plan.ORGANISM_RECORD_DBS`, membership in {sra, assembly}, not equality with `first.record_type`. The decision row of 2026-10-06 reads "accepting a second reply only if it names an organism the question contains and keeps the record type"
- Why it matters: the first reply read the person's record kind correctly; the retry message only complains about the missing organism, so a changed record kind is the model drifting, and the code takes it
- Suggested fix: require `second.record_type == first.record_type`; add the flip as a refusing case beside the "none" case
- NOT FIXED

### A2-56-08: the retry's log line cannot tell "the second reply named no organism" from "it named an organism the person never typed", so the invention rate A-56-05 asked about cannot be measured

- Non-blocking (instrument)
- Evidence: live, "Find SRA runs sequenced on Illumina from clinical respiratory samples", 3 runs (`raw/adversary_r2/live_noorg.jsonl` and `_log.txt`): the retry fired 3 of 3 (928, 1,734 and 1,883 ms) and each logged "kept the first reply: the second names no organism the question carries"; all three then asked which organism. The probe records the final classification only, so whether those second replies invented an organism (the A-56-05 and A2-56-01 path) or named none is not recorded anywhere. Same on "SRA runs of humanized immune system samples" run 2
- Why it matters: the guard held on these 4 live retries, but nobody can say whether it held because the model behaved or because the guard caught an invention, which is the number that says how often A2-56-01's bypass is one step away
- Suggested fix: log, bounded, which case it was (no organism span; organism span not in the question; Taxonomy-unknown span only), never the span text itself
- NOT FIXED

### A2-56-09: a host-plus-pathogen SRA question ("SARS-CoV-2 SRA runs from human clinical samples") gets a literature search, not SRA runs and not a question; the retry now reaches the same path

- Non-blocking for this round: the first-reply path is card 56's own, on develop; round 2 adds a second way in (a retry reply naming the question's organism and a host)
- Question typed: "SARS-CoV-2 SRA runs from human clinical samples"
- What the person sees: an answer built from a PubMed-style search (`ncbi_efetch` search, its follow-up, `pubtator_annotate`), with no SRA run and, as far as Think's output shows, no sentence saying SRA was not searched or why
- Evidence: live, 1 run (`raw/adversary_r2/live_hostpathogen.jsonl`): `entities [["SARS-CoV-2", "organism"], ["human", "organism"]]`, `resolved []`, `clarification null`, `ended "planned 3 tool calls"`. Offline (`raw/adversary_r2/compare.py branch host_and_pathogen retry_two_orgs`), Plan's three calls are `ncbi_efetch`, an `ncbi_efetch` follow-up and `pubtator_annotate`; the retry case (first reply empty, second naming "SARS-CoV-2" and an invented "Homo sapiens") ends the same way after "used the second reply". Cause: `resolve_organism` returns None for two organisms Taxonomy knows, `organism_spans` is non-empty so the new which-organism question does not fire, and `_needs_clarification` asks only on a referring word
- Why it matters: a host and a pathogen in one SRA question is the ordinary way to ask for clinical sequencing data; the person asked for runs and silently gets papers. The owner's rule this round was "never silently plans nothing"; this plans something else silently
- Suggested fix: when the record type is SRA or assembly and two or more organisms resolve, ask which one the runs should be filed under, naming both; or prefer the organism that is not a host, which is a reading of the question and belongs to a classifier, not code
- NOT FIXED

### Addendum to A2-56-01, A2-56-02 and A2-56-03: the matcher's own cases

Pure calls to `_span_is_in_question(span, question)` on this branch:

| Span | Question | Result | Bears on |
|---|---|---|---|
| "-" | "SRA runs of SARS-CoV-2" | True | A2-56-01: a lone dash span matches any dash; Taxonomy cleans it to nothing, so it is one more question-text span that lets an invented second organism through |
| "human" | "SRA runs of humanized mice" | True | A2-56-02 |
| "rat" | "respiratory samples" | True | A2-56-02 |
| "Homo sapiens" | "Homo sapiens neanderthalensis runs" | True | A2-56-02, a subspecies question widened to the species |
| "mouse" | "SRA runs of mouse-adapted SARS-CoV-2" | True | A real word of the question, but a retry naming only "mouse" turns a SARS-CoV-2 strain question into every mouse run; containment cannot see this, only a check that the organism is the subject can |
| "E. coli" | "SRA runs of E.coli" | False | A2-56-03 |
| "E. coli" | "SRA runs of E coli isolates" | False | A2-56-03 |
| "SARS-CoV-2" | "SRA runs of SARS-CoV2" | False | A2-56-03 |
| "SARS-CoV-2" | "SRA runs of SARSCoV2" | False | A2-56-03 |

### A2-56-04, second live addendum and a severity change: raised to blocking

- "Klebsiella pneumoniae SRA runs with KPC", 1 live run (`raw/adversary_r2/live_kpc.jsonl`): the model tagged only `["Klebsiella pneumoniae", "organism"]`, the organism route ran (`NCBITaxon:573`, 3 tool calls planned), `conditions_not_applied []`. The person asked for runs with a carbapenemase gene and gets every K. pneumoniae run with no note
- With the ORF-8 run above, 2 of the 2 live runs this round in which the model left the person's gene untagged produced an organism-wide answer with nothing in the answer saying the gene was not applied. When the model does tag the gene, the classifier keeps it a gene (mecA 2 of 2, mcr-1 1 of 1, ORF-8 1 of 1) and the person gets a refusal. So the round 2 note, built for a gene-shaped span set aside, fires on neither of the two shapes the live model actually produces for a gene filter
- I now hold this blocking against the card's goal ("a person asking for an organism's SRA runs never gets a confident wrong answer"); the lead may hold it to the owner's narrower decision row, in which case it goes to the owner as a question, not into the merge silently. The fix stays one line of policy: the note on every organism-records answer

### Correction to A2-56-06's suggested fix

The suggested-fix sentence of A2-56-06 is garbled. Read it as: the choice to ask is the owner's; if it is kept, replace the fixed "Escherichia coli" example with the shape ("Ask again naming the species, for example a pathogen or human") so a disease-patient question is not pointed at a bacterium.

### A2-56-10: a bacterial or viral gene kept a gene on an SRA question gets "NCBI has no record matching the name in your question", which is false for mecA, mcr-1 and ORF8

- Non-blocking for this round (the refusal and its wording are on develop); recorded because round 2's classifier now routes every gene-filter SRA question it keeps a gene into this sentence
- Question typed: "Staphylococcus aureus SRA runs carrying mecA" (live 2 of 2), "E. coli mcr-1 SRA runs" (live 1 valid of 2), "SARS-CoV-2 SRA runs with the ORF-8 deletion" (live run 2)
- What the person sees: "I could not identify that gene. NCBI has no record matching the name in your question, so no graph query was attempted." plus the fallback link
- Evidence: `raw/adversary_r2/live_meca.jsonl`, `live_mcr1.jsonl`, `live_orf8dash.jsonl`: `unresolved ["mecA"]`, `["mcr-1"]`, `["ORF-8"]`, `ended "planned 0 tool calls"`, a `think.gene_or_condition` decision in each log. The sentence is `_unresolved_entity_refusal_message(["mecA"])`, printed directly. NCBI Gene files mecA and mcr-1 under strain-level taxa, so the species-level lookup misses them; ORF8 resolved live in round 1 (`NCBIGene:43740577`) and only the dash spelling failed
- Why it matters: the person is told NCBI has no record for a gene NCBI holds. The classifier's correct "gene" pick (round 1's A-56-10 and this round's criteria fix) lands the person on a false statement instead of the organism's runs with a note
- Suggested fix: outside this card, but the organism-records route could offer, with the note, "mecA could not be matched to an NCBI Gene record for Staphylococcus aureus, so it was not applied; these are all its SRA runs", which is honest and useful. That is an owner choice
- NOT FIXED

## What held

| Attack | How | Result |
|---|---|---|
| Round 1's failing paths, again | Round 1's `raw/adversary/offline_probe.py`, modes part3, trunc, none_retry, hallucinated_org, brca_no_org, brca_tagged_no_org, span_injection, on this branch | All held: part3 matches develop on every question, "not applied" survives a 328-character narrative (499 characters), a "none" second reply and a single invented organism are refused and the organism question asked, BRCA1 and TP53 found, one call when a gene was tagged, the forged "Span:" line is one bounded line |
| Judge round 1's token cases | `_gene_shaped_fallback_candidates` directly | "type-2 diabetes" offers nothing, "TP53-mutant and KRAS-mutant and EGFR-mutant" offers all three genes, a U+2011 "SARS-CoV-2" claims its tokens (only "SRA" left) |
| Develop against branch on gene questions | `raw/adversary_r2/compare.py develop|branch brca1_empty brca9_noorg tp53_assembly_empty orf8_gene_kept` (develop's graph.py loaded in place) | Same resolution and refusals as develop; BRCA9 keeps its refusal with no organism named; the only difference is one extra model call when the reply names nothing |
| A real gene released as a condition | Live: mecA 2 runs, mcr-1 1 valid run, ORF-8 1 run where it was tagged | The classifier kept every tagged gene a gene (4 of 4); nothing released. The failure is elsewhere (A2-56-04, A2-56-10) |
| The answer note's truth | Read `plan_organism_records`: the search is `txid<taxid>[Organism:exp]` alone | When the note appears, what it says is true: the condition was not applied and the search was by organism only |
| Markup or instruction in the note | Read `useRunView.ts` note handling and `_condition_span_text` | Note text is plain text, one line, each span at most 60 characters plus the elision note; the span is the model's copy of the person's own words, so only the person who typed it could be misled |
| The note on the wrong answer | `grep organism_records` across `src` | Only Think sets it, per run in `GraphState`; no checkpointer, so a later turn cannot inherit a note |
| The retry inventing an organism, live | "Find SRA runs sequenced on Illumina from clinical respiratory samples" 3 runs, "SRA runs of humanized immune system samples" 1 retry | The retry fired 4 times and kept the first reply each time; the person was asked which organism. What the second replies said is not logged (A2-56-08) |
| The parse retry and key repair | Printed `_THINK_REPLY_KEYS`; parsed a "why" reply carrying `record_type` | Four keys listed; the repair keeps `record_type: sra` |
| The builder's test file | Ran once | 66 passed. Not relied on |

## What I did not cover

- Act and Write live. The answer text Synth writes beside an organism-only search ("explain why each one matched") was not seen; A2-56-04's harm rests on the note's absence, not on observed Synth wording
- The live rate of A2-56-01 and A2-56-02: the bypass needs a retry whose second reply carries a Taxonomy-unknown question word tagged as an organism plus an invented one; I saw the retry fire 4 times live and could not see its second replies
- Live Taxonomy for the cut term in A2-56-05: the outcome (asked which organism, 2 of 2) is live, the cause is read from code and reproduced offline
- What the literature path in A2-56-09 tells the person; only Think and Plan were run
- Other plan models; the classifier provider other than Jev
- The decision cap with three condition spans plus the other points (read, not run)
- Live spend: 15 probe runs (long name 2, mcr-1 2 with 1 guardrail transient, mecA 2, ORF-8 2, no-organism 3, humanized 2, host and pathogen 1, KPC 1), each about $0.0003 to $0.0004, about $0.005 in all. No other live call

Files in `raw/adversary_r2/`: `offline_r2.py` and `compare.py` (throwaway probes, ruff clean), `develop_graph.py` (a copy of develop's `graph.py` that `compare.py` loads for the side-by-side; do not commit it as source), and the `live_*.jsonl` rows with their `_log.txt` files.

## Verdict

FAIL against the goal contract "a person asking for an organism's SRA runs never gets a confident wrong answer or a lying trust signal, and no question that works on develop gets worse".

Blocking:

- A2-56-01, inside round 2's fix of A-56-05 (Regression of: A-56-05): the retry's containment check is satisfied by any organism-tagged question word, so "Illumina" tagged as an organism (a habit measured live 3 of 22 by the builder) lets an invented "Homo sapiens" through, and the person gets every human SRA run with no question asked. This sits inside a fix made during this phase, which fires the review loop's stop condition: escalate to the owner rather than start another round
- A2-56-04, an incomplete fix of A-56-03: the answer note fires only when the classifier set a gene-tagged span aside; on the test question 16 of 21 organism-only searches carry no note, and live the person's gene filter (ORF-8, KPC) was silently dropped on 2 of 2 runs where the model left it untagged. Blocking against the card's goal; the lead may hold it to the owner's narrower decision row, which makes it an owner question
- A2-56-05: a person who types an organism's full name over 30 characters is asked which organism (live 2 of 2), in round 2's new wording; cause on develop. The lead may weigh it non-blocking

Non-blocking: A2-56-02 (substring matches, inside round 2's matcher, Regression of: A-56-05), A2-56-03 (abbreviation spelled out on the retry asks the person for the organism they typed), A2-56-06 (owner's design, disease-subject SRA questions now asked), A2-56-07 (a record-type flip on the retry is accepted, contrary to the decision row), A2-56-08 (retry log cannot measure invention), A2-56-09 (host plus pathogen gets a literature search, pre-existing, now also reachable by the retry), A2-56-10 (false "NCBI has no record" refusal for real bacterial genes, pre-existing).

Verified with my own probes:

- Offline, mocked model, classifier and NCBI: A2-56-01, A2-56-02, A2-56-03, A2-56-04's note presence by reply shape, A2-56-05's cut Taxonomy term, A2-56-06 and A2-56-09 side by side with develop's graph.py, A2-56-07, the matcher table, A2-56-10's refusal sentence, and round 1's probe modes
- Live, 15 probe runs: A2-56-05 (2 of 2), A2-56-04's ORF-8 and KPC drops, A2-56-08's four retries, A2-56-09's literature plan, A2-56-10's mecA, mcr-1 and ORF-8 refusals

Only read, not run:

- That the note renders as plain text in the UI, and that no checkpointer carries `organism_records` between turns
- That Synth sees nothing from `organism_records`
- The live Taxonomy answer for a name cut at 30 characters (the end result was observed live)
- The builder's 66 tests: run once, green, not mutated and not relied on
