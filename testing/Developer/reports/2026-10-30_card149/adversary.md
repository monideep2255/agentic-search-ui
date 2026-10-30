# Card 149 adversary report, 2026-10-30

Adversary round for draft pull request #320 (fix/card149-human-gene-record-only, 3997dede). Findings are filed as they are established. Judge findings J-149-01 to 03 are not re-filed.

## Findings

### A-149-01: "And in mice?" after a GCK question answers with the human GCK record and does not say the mouse was not searched
- Severity: major (already on develop; this diff neither causes nor fixes it, but it changes what the wrong answer shows)
- What a person sees: they ask "What does GCK do?", then "And in mice?". The second answer opens "Found 1 gene record for GCK: glucokinase [1]", cites only https://www.ncbi.nlm.nih.gov/gene/2645 (human) as the gene record, and lists the same PubMed, ClinVar (human NM_000162.5 variants), OMIM and trial records as the first answer. Nothing says that no mouse record was searched. Think itself understood the question: its narrative reads "Follow-up asking about mouse ortholog of previously established human gene GCK", but `resolved_entities` is `[]` and Plan reads "searching 3 layers for NCBIGene:2645". So the human record is cited as the answer to a mouse question.
- Evidence: live run (branch 3997dede, one session, `run_streaming`), files in the session scratchpad `card149adv/live/gck_mice_0.json` and `gck_mice_1.json`. Run 2 citations: gene/2645, gene/2645/, pubmed 19790256 ..., clinvar/variation/4881360 ..., omim 138079, five NCT ids; no mouse Gck (103988) record anywhere. Tool results: `pubtator_annotate empty: 0 record(s)` (branch drops the rat 24385 row develop would have cited, which on develop would have been a rat record shown for a mouse question).
- Worse than develop: no. On develop the same plan runs and additionally cites rat Gck 24385, so develop is worse; the branch removes the one non-human record, which also removes the only visual hint that the answer was not about mice.
- NOT FIXED

### A-149-02: A mouse Shh question cites five vorinostat (SAHA) cancer trials as "Clinical trial records found" for the gene
- Severity: major (already on develop; `clinicaltrials_search` is untouched by this diff)
- What a person sees: "What does the mouse Shh gene do?" answers about mouse Shh (correct gene record, NCBI Gene 20423, kept by the branch), then lists under "Clinical trial records found": "Suberoylanilide Hydroxamic Acid in Treating Patients With Advanced Cancer", "Oral SAHA ... in Advanced Cutaneous T-cell Lymphoma", "... Advanced Solid Tumors", "... Advanced Multiple Myeloma", "An Investigational Study of a Histone Deacetylase (HDAC) Inhibitor Plus Targretin ...". None is about sonic hedgehog; they are trials of the drug SAHA, which the registry's condition search evidently matches to the text "SHH". Each is cited (NCT00045006, NCT00091559, NCT00106626, NCT00109109, NCT00127101) with `assertion_confidence: asserted`. A confident wrong record of the "another entity's record" kind the card names, through the trials path rather than the PubTator3 path.
- Evidence: live run, branch 3997dede, `card149adv/live/shh_mouse_0.json` in the session scratchpad. `clinicaltrials_search ok: 5 record(s)`, query_cond is the uppercased mention "SHH" (`_build_layer_tool_calls`, `core/graph.py:5336`).
- Worse than develop: no, identical path on develop. Filed because the card's acceptance ("never cites ... another gene's record ... as if it were the gene I asked about") is still violated on a gene question through a sibling Layer 3 call.
- NOT FIXED

### A-149-03: A mouse Shh question lists human SHH ClinVar variants and the human OMIM entry under the mouse gene with no species label
- Severity: minor (unsure; already on develop)
- What a person sees: the same mouse Shh answer lists "Clinvar records found: NM_000193.4(SHH):c.757T>C ..." (five human transcript variants) and "Omim records found: SONIC HEDGEHOG SIGNALING MOLECULE [5]" (OMIM 600725, human). The answer is about mouse Shh (gene 20423) and nothing labels these records as human. ClinVar and OMIM are human-only databases, so a reader who knows that is fine; a student reading "mouse Shh gene ... ClinVar records found" may take them as mouse variants.
- Evidence: same live run, citations clinvar/variation/4690046, 4755846, 4822560, 4823430, 4849004 and omim.org/entry/600725. Plan searched `SHH[gene]` in ClinVar and `SHH` in OMIM from the mention, with no taxon.
- Worse than develop: no.
- NOT FIXED

### A-149-04: "And in humans?" after a mouse Shh question searches the literature for the word "humans" and opens "Found 5 papers for Shh" over papers on rabies, skin microbiota and human-robot facial expressions
- Severity: major (already on develop; Think and the topic path are untouched by this diff)
- What a person sees: after "What does the mouse Shh gene do?", the follow-up "And in humans?" answers "Found 5 papers for Shh [1][2][3][4][5]" and then summarises "[Rabies]", "Dialogue between skin microbiota and immunity", "Aquaticity: A discussion of the term and of how it applies to humans", "Animal sources of antimicrobial-resistant bacterial infections in humans", "Human-robot facial coexpression". Five confident wrong records, each cited, labelled as papers for Shh.
- Evidence: live run, branch 3997dede, `card149adv/live/shh_mouse_1.json`. Think narrative: "it asks for the human ortholog/equivalent of the mouse Shh gene already discussed ... graph traversal from mouse gene to human ortholog", `resolved_entities: []`. Plan: "no gene, variant or disease was named, so searching the published literature for: humans". Citations pubmed 23351694, 25414304, 27210836, 37577944, 38536902.
- Contrast with A-149-01: the reverse follow-up ("And in mice?" after a human gene) keeps the remembered gene; this one drops it. Two follow-ups of one shape, two different wrong outcomes.
- Worse than develop: no (no code on this path changed).
- NOT FIXED

### A-149-05: An AR gene question cites a nasal ciclesonide trial and a sympathetic nervous system trial as "Clinical trials referencing AR"
- Severity: major (already on develop; same path as A-149-02, `clinicaltrials_search` on the bare uppercased symbol)
- What a person sees: "What does the AR gene do?" resolves human AR (NCBI Gene 367) correctly and cites it. The answer then says "Clinical trials referencing AR include ..." and "Two further trials—Brain Receptors in Sympathetic Nervous System Regulation [6] and a scintigraphy study of nasal ciclesonide deposition [9]." (an unfinished sentence, with an em dash, as written). NCT01371786 is a nasal inhaler deposition study (most likely matched through "AR" as allergic rhinitis); NCT00029627 has no androgen receptor content in its title. Both are listed under "Clinical trial records found" for the gene.
- Evidence: live run, branch 3997dede, `card149adv/live/ar_0.json` in the session scratchpad. `clinicaltrials_search ok: 5 record(s)`; citations clinicaltrials.gov/study/NCT00029627 and NCT01371786 beside three genuine AR trials (NCT01974765, NCT02000375, NCT02353988).
- Worse than develop: no. Shows the card's acceptance ("never cites ... another gene's record ... as if it were the gene I asked about") holds for the PubTator3 path only; a two-letter symbol that is also a common abbreviation still pulls unrelated records through the trials path.
- NOT FIXED

### Evidence AE-1: the branch's PubTator3 rule against develop's on live replies, including the symbols that are also words
Probe (mine, not the author's tests): the real `pubtator_annotate` tool against live PubTator3, then `_layer_tool_output_to_structured_fields` with `expected_gene_id` empty (develop's rule) and with the id `_build_layer_tool_calls` sets (branch). Ids from the real `resolve_symbol_to_curie` (live NCBI), which gave AR 367, MET 4233, SET 6418, CAT 847, TNF 7124, SNCA 6622, mouse Shh 20423, mouse Tnf 21926, mouse Trp53 22059, rat Gck 24385, zebrafish shha 30269.

| Question's gene (id) | Literature entities cited, develop rule | Branch |
|---|---|---|
| AR (367) | Arginine, Arrhythmias Cardiac, Arsenic, Arthritis, Arthritis Rheumatoid (five MeSH records) | none |
| MET (4233) | Methanol, Metabolic Diseases, Metals, Methionine, Metabolic Syndrome | none |
| SET (6418) | SETBP1, SETD2, Setd7, SETD1A, SETDB1 (five other genes) | none |
| mouse Tp53 (22059), query "TP53" | human TP53 7157 | mouse Trp53 22059 |
| mouse Brca1 (12189), query "BRCA1" | human BRCA1 672 | none |
| mouse Tnf (21926) | rat Tnf 24835 | none |
| rat Gck (24385), mouse Shh (20423), zebrafish shha (30269) | the asked record | the asked record, kept |
| CAT 847, HTT 3064, CFTR 1080 | the human record | the same |

So the branch removes a larger class of confident wrong records than the card names (every symbol that is also a word or a prefix, and every mouse question whose symbol PubTator3 files under the human record), and it keeps the right non-human record when the question asked for that organism. No case found where develop cited the asked gene's own record and the branch dropped it. PubTator3 `db_id` was a plain integer for every `ncbi_gene` entity in 62 symbols sampled (no multi-id or prefixed form that the strict string comparison would miss).
More symbols whose only PubTator3 gene entity is another species, adding to the judge's J-149-03 count: NOTCH1 (rat 25496), NPHS1 (rat 54631), UGT1A1 (rat 24861), XIST (mouse 213742).

### A-149-06: Disease questions keep develop's "no exact name, keep everything" rule, so a MODY question cites MODY type 1, type 3, type 8, Mason-type diabetes and type 2 diabetes as its literature entities
- Severity: minor (unsure; already on develop, and the card's acceptance asks that disease questions do not change)
- What a person would see: a disease question resolved to MedGen:C0342276 searches PubTator3 for its MedGen name "maturity-onset diabetes of the young". No entity has that exact name, so the old rule keeps every citeable entity: Mason-Type Diabetes (C562772), MODY Type 3 (C563933), MODY Type 1 (C565101), MODY Type 8 with Exocrine Dysfunction (C565225), Diabetes Mellitus Type 2 (D003924), each a cited "Literature entity" for the disease asked about. The same rule the branch now replaces for genes, left as it was for diseases.
- Evidence: my probe, live `resolve_disease_mention_to_curies("maturity-onset diabetes of the young")` gives `['MedGen:C0342276']`, `_disease_search_text` gives `maturity-onset diabetes of the young`; real `pubtator_annotate` on that text shaped by `_layer_tool_output_to_structured_fields` (branch code, expected id empty as `_build_layer_tool_calls` sets for a disease) yields the five rows above. Not driven through a live answer (no spend).
- Side observation, same probe: the mention "MODY" resolves to eight concepts and the search text chosen is "impaired glucose tolerance in mody" (the first CURIE, C0271653), so "Any trials for MODY?" would search the trials registry and PubTator3 for a narrower condition than the one typed. Already on develop; unsure whether the owner counts it.
- Worse than develop: no (identical).
- NOT FIXED

### A-149-07: "What are the orthologs of GCK?" opens "Found 51 gene records for GCK, of 776 available" over 51 other species' glucokinase records, with no written summary
- Severity: minor (already on develop; the graph ortholog path is untouched by this diff)
- What a person sees: the headline calls 51 non-human glucokinase genes (NCBI Gene 100030125, 100037406, ... 102060530) "gene records for GCK". The species is shown, but only as the third cell of each table row (`kind: table_row`, cells e.g. `["glucokinase", "NCBIGene:100475738", "Ailuropoda melanoleuca"]`); the sentence form of each row reads "Gene NCBIGene:100475738, name: glucokinase [9]" with no organism, and the human record appears only as "Gene symbol: GCK [52]". The answer ends "Note: no written summary could be checked against the records, so this answer lists the records found with their sources", and the counts disagree with each other: "of 776 available" in the headline, "only 120 of the 776 records" in the note, and Act's own `100 row(s) of 756` plus `20 row(s) of 20`.
- Why it matters for this card: the card's promise is that another species' record is never cited "as if it were the gene I asked about". Here the question asked for orthologs, so citing them is right, but the headline wording presents them as GCK's own records; in the plain sentence form, which is also what a copy or export carries, nothing says they are other species.
- Evidence: live run, branch 3997dede, `card149adv/live/orth_0.json` in the session scratchpad. `pubtator_annotate empty: 0 record(s)` (the branch dropped the rat row, correct).
- Worse than develop: no (develop runs the same graph path, and additionally cites rat Gck 24385 as a literature entity).
- NOT FIXED

### A-149-04 addendum: on develop, one run of the same pair answered the follow-up correctly, so "not worse than develop" is unverified
- Severity: unsure
- What I observed: the identical two-question session on develop (15363460, a separate develop worktree) resolved "And in humans?" to `{"text": "Shh", "curie": "NCBIGene:6469"}` (Think narrative "... now clarified to human") and answered about human SHH, citing gene/6469. The branch run (A-149-04) resolved nothing and searched the literature for "humans". One run each, so this is n=1 against n=1.
- Why I believe it is model variance and not this diff, without having proven it: the diff changes only Plan's `_build_layer_tool_calls` arguments, the planned call's `expected_gene_id` and Act's shaping; Think runs before all of them. Question 1's PubTator3 result was identical on both (`pubtator_annotate ok: 1 record(s)`, the mouse 20423 row kept on both), so the session memory Think reads for question 2 should not differ. I had no live runs left to repeat the branch pair. Recommend the lead repeats "What does the mouse Shh gene do?" then "And in humans?" on the branch three to five times before calling A-149-04 pre-existing.
- Evidence: `card149adv/live/dev_shh_0.json`, `dev_shh_1.json` (develop) and `shh_mouse_0.json`, `shh_mouse_1.json` (branch) in the session scratchpad.
- NOT FIXED

### Evidence AE-2: develop live runs confirm A-149-02 and the card's own defect on a second gene
- Develop, "What does the mouse Shh gene do?": the same five SAHA (vorinostat) trials NCT00045006, NCT00091559, NCT00106626, NCT00109109, NCT00127101, and the same human ClinVar and OMIM rows. A-149-02 and A-149-03 are pre-existing, verified by probe.
- Develop, follow-up resolved to human SHH (6469): the answer cites `https://www.ncbi.nlm.nih.gov/gene/20423 | Literature entity name: Shh`, the mouse record, as the literature entity of a human SHH answer. This is card 149's defect live on develop for SHH; the branch's rule would drop it (the shaper probe in AE-1 gives SHH with expected 6469 an empty result, since PubTator3's only SHH gene entity is 20423).

## Verdict

PASS against the card's acceptance for the path the card names, with no finding inside this card's own fix. Every finding above is on a path the diff does not touch, and every one is already on develop (A-149-04's "already on develop" is unverified, see its addendum).

| Claim | Method | Result |
|---|---|---|
| A human gene question no longer cites another species' PubTator3 record | My shaper probe on live PubTator3 (AE-1, 17 genes), my live runs (GCK twice, AR, GCK orthologs), develop live run (SHH cites mouse 20423) | Verified by probe |
| Another gene's record is no longer cited as the asked gene | Shaper probe: AR, MET, SET (develop cites five unrelated MeSH or gene records each; branch none) | Verified by probe, PubTator3 path only. Not true of the trials path: A-149-02, A-149-05 |
| The human record stays cited | Live runs: gene/2645 and gene/367 cited | Verified by probe |
| A non-human question keeps its own record | Shaper probe with resolver ids: mouse Shh 20423, rat Gck 24385, zebrafish shha 30269 kept; mouse Tp53 now 22059 instead of human 7157; live mouse Shh run keeps 20423 | Verified by probe |
| Genes whose record is already right are unchanged | Shaper probe: CAT, HTT, CFTR, C9ORF72, PARK7 identical | Verified by probe |
| Disease questions unchanged | Read the guard (`gene_id if gene_symbol else ""`, disease text only when no gene) plus a branch shaper probe on four disease names | Probed on the branch only, not compared byte for byte with develop (the judge did that) |
| A follow-up or two-gene question cannot slip a wrong record through the new rule | Read only for two-gene questions; follow-ups live-run (A-149-01, A-149-04) | Partly verified |

Live runs spent: 8 of 8 (branch: GCK + "And in mice?", mouse Shh + "And in humans?", AR, GCK orthologs; develop: mouse Shh + "And in humans?").
