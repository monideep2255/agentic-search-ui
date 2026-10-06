# Card 56 adversary, round 3

Fresh-context adversary for branch `fix/card56-r3-minimal` against `origin/develop`. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [What held](#what-held)
- [What I did not cover](#what-i-did-not-cover)
- [Spend and an incident](#spend-and-an-incident)
- [Verdict](#verdict)

## Findings

### A3-56-01: the skip does not hold when "SARS-CoV-2" is typed with a space, a soft hyphen or other punctuation

- Non-blocking. Not a regression: develop does the same. A gap in what the build report claims ("SRA runs of SARS-CoV-2 is never answered about the disease SARS").
- Question typed, with Think's model returning no entity and record type "sra" (the 5-in-26 habit findings.md measured): "SRA runs of SARS CoV-2", "SRA runs of SARS CoV 2", "SRA runs of SARS(U+00AD)CoV(U+00AD)2" (soft hyphen, invisible, carried by text pasted from PDFs and web pages), "SRA runs of SARS(U+00A0)-CoV-2", "SRA runs of SARS -CoV-2", "SRA runs of SARS- CoV-2", "SRA runs of SARS/CoV-2", "SRA runs of SARS.CoV.2", "SRA runs of (SARS)-CoV-2", and the two dash look-alikes outside category Pd, U+2043 hyphen bullet and U+02D7 modifier minus.
- On develop and on this branch alike: "SARS" reaches the MedGen lookup and binds; live, "SARS" binds the three SARS records (C1519126, C4302012, C4302019), the same confident wrong subject the card exists to remove.
- Evidence: `raw/adversary_r3/probe.py` over `scen1.json`, output `branch1.jsonl` and `dev1.jsonl`, rows "SAME sra" for each of the questions above with `medgen_lookups` containing "SARS". Live NCBI Taxonomy (`raw/adversary_r3/live_lookups.py`) knows "SARS CoV 2", "SARS CoV-2", "SARS CoV2" and the soft-hyphen form as organisms, so a person can reasonably type them. Live MedGen binding of "SARS": `raw/adversary_r3/medgen_live.py`.
- Suggested fix: out of this round's minimal scope. The spaced forms "SARS CoV-2" and "SARS CoV 2" are the realistic ones; a soft hyphen could be treated as a joiner (category Cf U+00AD) at no cost. Whether to widen is the owner's call; at minimum the build report's sentence should say the hyphen-joined form only.

### A3-56-02: a disease written as the first piece of a hyphenated word no longer binds on an SRA or assembly question

- Non-blocking. Different, mostly not worse; listed because two cases are a real loss. Partly disclosed in build_r3.md ("COVID-19" only).
- Questions typed, Think's model returning no entity, record type "sra" or "assembly": "SRA runs from COVID-19 patients", "HIV-1 genome assemblies", "SRA runs from HIV-positive patients", "SRA runs from AML-derived cell lines", "SRA runs of ALS-associated motor neurons", "SRA runs of COPD-related lung samples", "SRA runs of H5N1-infected ducks", "SRA runs of IBD-associated E. coli", "SRA runs of MERS-CoV", "Find SRA runs from ALS-patients", "SRA runs of CML-BCR-ABL cells".
- Develop: the piece reaches MedGen and binds; the answer is a disease-route answer about those records. This branch: nothing binds, Plan takes the topic search over the question's words (PubMed), with no SRA runs on either.
- What develop bound, live MedGen through the real `resolve_disease_mention_to_curies`:

| Token | Develop binds | Verdict for the person |
|---|---|---|
| COVID | "COVID Reinfection", "long COVID brain fog" | Wrong subject on develop; branch better |
| HIV | 8 of 20, led by "Acute HIV infection", "HIV wasting syndrome", "HIV status" | Narrow slices on develop; branch arguably better |
| IBD | "Chronic inflammatory bowel disease (IBD)" and "Deficiency of isobutyryl-CoA dehydrogenase" (an acronym collision) | Half wrong on develop; branch better |
| MERS | "Positive bloodstream MERS coronavirus nucleic acid test" | Wrong subject on develop; branch better |
| AML | "Acute myeloid leukemia" among 3 | Right on develop; branch loses it |
| H5N1 | "Influenza caused by Influenza A virus subtype H5N1" | Right on develop; branch loses it |
| ALS | 6, incl. "Muscle atrophy due to ALS" and a juvenile ALS type | Partly right on develop; branch loses it |
| COPD | 2 narrow COPD records | Partly right on develop |

- Evidence: `raw/adversary_r3/branch1.jsonl` and `dev1.jsonl` (the "DIFF" rows), live MedGen in `medgen_live.py` and `medgen_titles.py` output quoted above. Record type "none" is unchanged in every one of these (all "SAME none").
- Why it matters: "SRA runs from AML-derived cell lines" and "SRA runs of H5N1-infected ducks" answered on the right disease on develop and now get a PubMed word search. Neither tree gives SRA runs, so the loss is of a related answer, not of the asked-for records. Only on runs where the model tags nothing.
- Suggested fix: none required for this round in my view; record it as a known trade in the build report beside the COVID-19 line, with the AML and H5N1 examples.

### A3-56-03: live on this branch, the card's own question typed "SARS CoV-2" (a space for the first hyphen) was answered with the three SARS records, 1 run of 6

- Blocking for closing card 56 as "a SARS-CoV-2 SRA question is never answered about the disease SARS". Non-blocking for merging this branch: not a regression, develop takes the same path, and the branch is better than develop on the hyphenated form. The live reproduction of A3-56-01.
- Question typed: "Find SRA runs of SARS CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched." (the findings.md question, one hyphen replaced by a space).
- This branch, live, deepseek/deepseek-v4-flash, `CLASSIFIER_PROVIDER=jev`, 6 runs: run 2 tagged "SARS CoV-2" as a disease (record type "sra"), resolved `MedGen:C1519126`, `MedGen:C4302012`, `MedGen:C4302019` ("SARS Coronavirus Protease Pathway", "Probable SARS", "SARS (severe acute respiratory syndrome) confirmed") and planned 8 calls. Runs 1, 3 and 5 took the organism route on `NCBITaxon:2697049`; runs 4 and 6 tagged "Illumina" as a gene and planned nothing.
- Mechanism, checked: the model's own disease span "SARS CoV-2" binds nothing in MedGen (live `medgen_live.py`: 0 matched), so the D3 token fallback runs; no organism span was tagged, so #173 claims nothing; "SARS" stands as a whole word before the space, so `_only_a_piece_of_a_joined_name` returns False and it binds.
- What the person sees: a confident, cited answer about the disease SARS, a different virus, to a question about SARS-CoV-2 sequencing runs. The card's defect, on its own question, one character away.
- Evidence: `raw/adversary_r3/live_space.jsonl` and `live_space_log.txt`.
- Suggested fix: out of the owner's minimal scope; a follow-up card. One shape that stays inside the "no word list" rule: on an SRA or assembly question, skip a fallback token that is the first word of a run NCBI Taxonomy confirms as an organism (the same cached `_organism_is_known` lookup), so a spaced organism name is protected as a hyphenated one is.

### A3-56-04: live, "SRA runs from AML-derived cell lines" lost its disease on 1 run of 3 and fell to a PubMed search with 0 hits

- Non-blocking in my reading, close to the line; the owner may weigh it otherwise. Live confirmation of A3-56-02, inside this round's change (the new skip), so not a regression of J-56-04 but a cost of this round's own fix.
- Question typed: "SRA runs from AML-derived cell lines".
- This branch, live, deepseek/deepseek-v4-flash, 3 runs: runs 1 and 2 tagged "AML" as a disease and bound the three AML records by the model-span lookup (`MedGen:C1860794`, `C5435576`, `C0023467`, the last "Acute myeloid leukemia"), 8 calls planned. Run 3 returned no entity, record type "sra": the new skip dropped "AML" (it stands only as "AML-derived"), nothing resolved, Plan took the topic search.
- On develop, run 3's reply reaches the D3 fallback with "AML" and binds the same three records as runs 1 and 2 (offline: `dev1.jsonl`, "SRA runs from AML-derived cell lines", sra, lookups "SRA", "AML"; live MedGen binding in `medgen_live.py`).
- The topic search the branch plans is `sra AND runs AND aml-derived AND cell AND lines` (`breadth_plan.plan_topic_search`), and PubMed ESearch for that term returns Count 0 (live, 2026-10-06). The same holds for "SRA runs from COVID-19 patients" (`sra AND runs AND covid-19 AND patients`, 0) and "SRA runs of H5N1-infected ducks" (0); "HIV-1 genome assemblies" gives 957.
- What the person sees: on develop, an answer about acute myeloid leukaemia (not SRA runs, but the right disease, cited); on this branch, on one sample in three, an answer built on a search that found nothing. The same question now answers two different ways depending on the model's sample, where develop answered it one way.
- Evidence: `raw/adversary_r3/live_aml.jsonl`, `live_aml_log.txt`.
- Suggested fix: none forced. If the owner wants it closed cheaply: let the skip apply only when the token's other side is a mixed-case or digit-led piece (the shape of "CoV-2", "1"), or accept and document the trade. Note COVID-19 is the opposite case: develop's "COVID" binding is "COVID Reinfection" and "long COVID brain fog", so there the empty answer is the more honest one.

### A3-56-05: on a papers question, the same SARS binding happens 2 runs of 3 live, and this change leaves it by design

- Non-blocking, out of this round's scope, unsure how much of it reaches the person. Not a regression.
- Question typed: "SARS-CoV-2 sequencing papers".
- This branch, live, 3 runs: the classifier set record type "none" each time (so the brief's worry, a papers question misread as "sra", did not occur), and in runs 1 and 2 returned no entity, so the D3 fallback cut "SARS" out of "SARS-CoV-2" and bound the three SARS records, `MedGen:C1519126`, `C4302012`, `C4302019`. All three runs planned 3 calls (the topic search, by the call count).
- Develop does the same on these replies; the branch's skip is gated on "sra" and "assembly" and the paper arm of its tests pins develop's behaviour on purpose.
- What the person sees: probably papers on "sars-cov-2 AND sequencing" (the topic route wins when no gene resolved), with the SARS records still carried as Think's resolved entities into the think event and Write. Write was not run, so whether the SARS records are shown or cited beside the papers is not established.
- Evidence: `raw/adversary_r3/live_papers.jsonl`, `live_papers_log.txt`.
- Suggested fix: a follow-up card; the empty-entity rate on this question (2 of 3) is higher than on the SRA question (5 of 26), so the papers path may be where the card's defect is now most often met.

## What held

All by my own probes unless marked "read".

- The hyphen-joined form, every joiner tried: on an SRA or assembly question with no entity, "SARS" is skipped for the ASCII hyphen, U+2010, U+2011, the em dash, U+2E3A, the minus sign U+2212 and the fullwidth hyphen U+FF0D, where develop looks it up (`branch1.jsonl` against `dev1.jsonl`, "DIFF" rows). "MERS" in "MERS-CoV" likewise.
- A whole word still binds: "SARS and SARS-CoV-2 SRA runs", "SRA runs of MODY-like patients and MODY families", "SRA runs - MODY patients" (spaced dash) and "SRA runs of ALS" look up the same tokens on both trees.
- A piece carrying a gene is unaffected: "SRA runs of BRCA1-mutant breast tumours", "TP53-null", "KRAS-G12D" resolve the gene before D3 on both trees, no MedGen lookup.
- Record type "none" is untouched: every one of the 43 attack questions run with record type "none" gives byte-identical output on both trees.
- A papers question misread as "sra" ("SARS-CoV-2 sequencing papers", "Latest SARS-CoV-2 research", forced offline): develop binds "SARS", the branch binds nothing. The skip helps there. Live, the classifier did not misread it (3 of 3 "none"), see A3-56-05.
- Parse retry (J-56-04), offline with scripted replies (`scen_retry.json`): the retry message lists `"query_class", "narrative", "entities", "record_type"`; a first reply of `not json` then a gene reply carrying `"record_type": "sra"` still resolves BRCA1 and takes the gene route on both trees (the organism route needs nothing else resolved), so a wrong record type in the repaired reply did not reroute a gene question; a reply with an invalid record type "SRA" twice ends in the same step error on both trees.
- Narrative repair (J-56-04): a reply with "why" and `record_type` is repaired on the branch and takes the organism route on SARS-CoV-2, where develop refused it, retried, and (with my fake second reply) bound the SARS records. A "why" reply with an extra unknown key ("organism") still fails on both trees, and one carrying both "why" and "reason" is left alone.
- Edge cases of `_only_a_piece_of_a_joined_name`, run directly: a leading dash with nothing before it ("-SARS") and a trailing dash at the end ("SARS-") are whole words; "a-SARS" and "SARS-x" are pieces; matching is case-insensitive ("SARS" against "sars" counts the whole word).
- Live gene lookups: "SARS", "SRA", "MERS", "COVID", "HIV", "IBD", "AML", "H5N1" are none of them human gene symbols, so the unchanged gene-shaped fallback does not bind them on either tree.

## What I did not cover

- Write and Act were not run; what the person reads in A3-56-04 and A3-56-05 is inferred from Think's bindings, Plan's call count and a live PubMed count, not from a rendered answer.
- The parse retry was not exercised live: the probe cannot force a malformed first reply. Whether the plan model, told to use "exactly these keys" including `record_type`, sets "sra" on a question that does not ask for records was not measured.
- Session-memory follow-ups ("And its SRA runs?") were not attacked beyond reading the builder's tests.
- The empty-entity rate behind A3-56-02 and A3-56-04 is from 3 live runs per question, too few to state a rate.
- Kimi (the local plan model) was not run.

## Spend and an incident

- Live probe runs: 12 of 12 allowed, deepseek/deepseek-v4-flash, $0.0049 by the probe's cost field (6 for "SARS CoV-2", 3 papers, 3 AML).
- Incident, disclosed: my first offline comparison run did not block the network, and the three classifier decisions Think starts (`think.recent_years`, `think.asks_features`, `plan.literature`) went live on the guard tier, about 190 calls before I stopped it. Cost not measured; guard-tier classifier calls, expected to be a few cents at most. Every later offline run disables sockets in `probe.py` and showed 0 successful model calls.
- Live NCBI only (no model): about 30 MedGen, Gene and Taxonomy lookups and 4 PubMed counts, to establish what develop binds.
- Nothing outside this report and `raw/adversary_r3/` was written; no source file changed (`git status`). My scripts pass ruff check, ruff format and isort.

## Verdict

PASS for the branch against its stated contract, which I verified with my own probes: on an SRA or assembly question, a token standing only as a piece of a hyphen-joined name is never tried as a disease, every Unicode dash in category Pd and U+2212 counts, a whole word still binds, record type "none" is byte-identical to develop, and the J-56-04 key-list fixes behave as claimed offline. No finding sits inside the J-56-04 fix.

Not a pass for closing card 56 on the sentence "a SARS-CoV-2 SRA question is never answered about the disease SARS": A3-56-03 reproduced exactly that answer live on this branch, 1 run of 6, with the question typed "SARS CoV-2". It is not a regression and should not hold this merge; it should hold the card open or become a follow-up.

Verified by my own probes: A3-56-01 (offline, both trees), A3-56-02 (offline both trees, live MedGen), A3-56-03 (live), A3-56-04 (live, offline, live PubMed count), A3-56-05 (live), and everything under "What held". Only read: the session-memory follow-up behaviour, the builder's gate results, and how Write presents bound records.
