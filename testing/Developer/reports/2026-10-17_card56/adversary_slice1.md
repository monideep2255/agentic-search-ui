# Card 56 slice 1: adversary round

Branch `fix/card56-phrase-lookup` (f3b431a3, 9b7403bc, 0057ad30, e01a4e72) on develop 535943bc. One round, dial position 2. Findings are filed as they are found, numbered A-56a-01 and up. The adversary files, it never fixes or closes.

## Findings

### A-56a-01: A disease acronym that is also a human gene symbol is read as the gene, now with a confident "Read as" line
- Severity: major (not worse than develop for the binding; the new line presents the wrong reading as settled)
- What: when the model tags a disease acronym that MedGen's title search binds nothing for, and the acronym is an official human gene symbol, the lookup's Gene leg is the one fit and the question is answered about the gene. "PAH" (pulmonary arterial hypertension) becomes phenylalanine hydroxylase; "CAD" (coronary artery disease) becomes carbamoyl-phosphate synthetase. Develop binds the same gene through the gene fallback, silently.
- Reproduction: offline Think driver (real NCBI, scripted model reply `[("PAH","disease")]`, record type none), `think_offline.py` against detached worktrees of both commits:
  - develop 535943bc: `"Which clinical trials are recruiting for PAH?"` resolved `[["PAH", "NCBIGene:5053"]]`, narrative `Model narrative.`
  - branch e01a4e72: resolved `[["PAH", "NCBIGene:5053"]]`, narrative `Model narrative. (Read 'PAH' as the human gene PAH (NCBI Gene 5053))`
  - `"What genes raise the risk of CAD?"`, tag `("CAD","disease")`: both bind `NCBIGene:790`; branch adds `Read 'CAD' as the human gene CAD (NCBI Gene 790)`.
  - NCBI-only probe of the primitives: `PAH` disease_bind [] matched 0, lookup "one" `NCBIGene:5053`; `CAD` disease_bind [] matched 0, lookup "one" `NCBIGene:790`.
- Why it matters: a clinician asking about trials for pulmonary hypertension gets an answer about a phenylketonuria gene. The owner's rule "a single fit can still be the wrong reading; the answer must say which record it used" is met in letter, but the line is buried in the plan narrative and reads as confirmation. The model said disease; a gene fit for a span the model tagged as a disease is a type contradiction the lookup could treat as "several" (the model's type versus NCBI's) rather than "one". Not worse than develop.
- NOT FIXED
A-56a-01, more of the same shape (NCBI-only probe of the branch's `look_up` with the human gene taxon, after the disease check bound nothing): `SCD` (sickle cell disease) is one fit, `NCBIGene:6319` stearoyl-CoA desaturase; `CAPS` (cryopyrin-associated periodic syndromes) is one fit, `NCBIGene:828` calcyphosine. Also `CMV` is one Taxonomy fit, `NCBITaxon:12305` "cucumber mosaic cucumovirus", not cytomegalovirus; it reaches a binding only through an organism tag (unchanged from develop) because MedGen binds 13 records for `CMV` as a disease.

### A-56a-02: The "nothing fits" ask tells a person a well-known disease is not in NCBI, and asks for an organism on a human-patient question
- Severity: major (worse than develop on honesty: develop asked nothing and searched; the branch states something false)
- What: a disease acronym the model tags on an SRA or assembly question, which MedGen's title search does not bind, reaches `none_question`. The ask says the acronym is not in NCBI "as an organism, gene or condition", which is false for chronic myeloid leukaemia, hepatocellular carcinoma, tuberculosis and chronic kidney disease, and tells the person to name an organism "as NCBI spells it" when they asked about human patients.
- Reproduction: offline Think driver, real NCBI, scripted reply `[("CML","disease")]`, record type sra:
  - develop: `"Find SRA runs from CML patients treated with imatinib"` resolved `[]`, ask `null`, Think goes on to Plan.
  - branch: ask `I could not find 'CML' as an organism, gene or condition in NCBI, so I cannot tell which organism's SRA sequencing records you want. Ask again naming the organism as NCBI spells it, for example "SRA sequencing records of Escherichia coli".`
  - The same ask, branch only, for `"Find SRA runs of HCC tumour RNA-seq"` (HCC as disease), `"SRA runs from TB patients' sputum"` (TB as disease) and `"Genome assemblies of bacteria from CKD patients"` (CKD as disease, "genome assemblies" wording).
  - NCBI-only probe: `CML`, `HCC`, `CKD`, `TB` each bind 0 MedGen records by the code's title search and give lookup "none", because the exact-title rule needs the title to be the acronym.
- Why it matters: "a refusal says what to type next" is met, but what it tells the person to type is wrong for them (an organism, for a human-disease question), and the sentence before it is untrue. A clinician who reads "could not find 'TB' ... in NCBI" stops trusting the product. The "none" outcome only proves that no Taxonomy name, human gene symbol or exact MedGen title equals the acronym, not that NCBI has no such condition; the ask should say what was actually checked.
- NOT FIXED

### A-56a-03: A disease named on an SRA question is now read as its virus and answered with the virus's sequencing runs
- Severity: major (worse than develop: develop bound nothing)
- What: "COVID-19" tagged as a disease binds nothing in MedGen (`COVID[title] AND 19[title]` is 0), so the lookup reads it whole; Taxonomy files "COVID-19" under SARS-CoV-2, so it is one fit and the organism anchor searches the virus's SRA runs. A question about patients' gut microbiome gets SARS-CoV-2 genome sequencing runs.
- Reproduction: offline Think driver, scripted reply `[("COVID-19","disease")]`, record type sra, question `"Find SRA runs from COVID-19 patients' gut microbiome"`:
  - develop: resolved `[]`, organism_records `null`.
  - branch: resolved `[["COVID-19", "NCBITaxon:2697049"]]`, organism_records `["NCBITaxon:2697049", "sra"]`, narrative `Model narrative. (Read 'COVID-19' as the organism Severe acute respiratory syndrome coronavirus 2 (NCBI Taxonomy 2697049); COVID-19: NCBI Taxonomy 2697049; searching NCBI SRA sequencing records filed under it, by organism alone, so any other condition the question names is not applied to the search)`
- Why it matters: the model said disease; the person asked about samples from people with the disease. The answer lists 7.6 million virus runs with a line saying it read the disease as the virus. The "not applied" clause is the only signal, and "gut microbiome" is the whole point of the question. The type contradiction (disease tagged, organism fit) is the same shape as A-56a-01. Also minor: the plan line states the reading twice ("Read 'COVID-19' as ..." then "COVID-19: NCBI Taxonomy 2697049").
- NOT FIXED

### A-56a-04: A whole hyphenated word now reaches the disease fallback and "IL-6" binds a rare congenital disorder
- Severity: major (differently wrong from develop, and further from the question)
- What: on a reply that names nothing twice, the whole word "IL-6" is a disease-fallback candidate. `resolve_disease_mention_to_curies` drops the one-character "6", searches `IL[title]`, and binds MedGen C2931006, "ALG9 congenital disorder of glycosylation" (also called CDG IL). This is the one-character-word residual the build report names for "HIV-1", but it is not limited to HIV-1: any hyphenated symbol ending in one character (IL-6, IL-1, TNF-a, HIV-1, HPV-6, CD-4) now reaches it as a whole word.
- Reproduction: offline Think driver, scripted reply empty on both calls, record type none, question `"IL-6 inhibitors in COVID-19 papers"`:
  - develop: resolved `[['COVID', 'MedGen:C5784539'], ['COVID', 'MedGen:C5828618']]` (the old piece defect)
  - branch: resolved `[['IL-6', 'MedGen:C2931006']]`; MedGen C2931006 title, by ESummary: `ALG9 congenital disorder of glycosylation`
- Why it matters: a researcher asking for IL-6 inhibitor papers gets an answer about a glycosylation disorder, with a disclosure "IL-6: 1 MedGen record matched by name" that reads as a precise hit. Develop was wrong about COVID records, which are at least on topic for the question.
- NOT FIXED

### A-56a-05: "Find SRA runs of HIV-1" now binds HIV disease records instead of the virus, because the disease fallback runs before the lookup
- Severity: major (worse than develop: develop bound nothing on this SRA question)
- What: on a twice-empty reply to an SRA question, the whole word "HIV-1" goes to the disease fallback first, which binds four HIV disease records by containment (`HIV[title]`, the one-character "1" dropped). The whole-phrase lookup, which would read "HIV-1" as NCBI Taxonomy 11676 (Human immunodeficiency virus 1, measured: lookup outcome "one"), never runs because something already resolved. The same order makes "H5N1 genome assemblies", "MRSA genome assemblies", "SRA runs of RSV in infants" and "SRA runs of HPV16" bind disease records rather than the organism (these match develop, so are not regressions, but the lookup that would fix them is unreachable).
- Reproduction: offline Think driver, scripted reply empty twice, record type sra, question `"Find SRA runs of HIV-1 from Africa"`:
  - develop: resolved `[]`, organism_records `None`
  - branch: resolved `[['HIV-1', 'MedGen:C0019693'], ['HIV-1', 'MedGen:C0282616'], ['HIV-1', 'MedGen:C0458074'], ['HIV-1', 'MedGen:C0481430']]`, organism_records `None`. Titles: "Human immunodeficiency virus infection", "HIV enteropathy", "HIV status", "HIV not detected".
  - NCBI-only probe: `look_up("HIV-1")` outcome "one", `NCBITaxon:11676`.
- Why it matters: a person asking for HIV-1 sequencing runs gets an answer built on "HIV status" and "HIV not detected" records, not SRA runs. On a records question the organism reading should come before a containment match in MedGen.
- NOT FIXED

### A-56a-06: "HEV" (hepatitis E virus) is read as a pig virus and its SRA runs are searched
- Severity: critical (worse than develop: develop bound nothing; this is a confident wrong organism inside the new lookup)
- What: NCBI Taxonomy `HEV[All Names]` answers exactly one record, 42005, Porcine hemagglutinating encephalomyelitis virus, not hepatitis E virus. Whether the model tags "HEV" as a disease (MedGen title search binds 0) or names nothing twice, the lookup calls that one fit and the organism anchor searches the pig virus's SRA runs.
- Reproduction: offline Think driver, real NCBI, question `"Find SRA runs of HEV from pork liver"`, record type sra:
  - develop, reply `[("HEV","disease")]`: resolved `[]`, organism_records `None`. Reply empty: the same.
  - branch, reply `[("HEV","disease")]`: resolved `[['HEV', 'NCBITaxon:42005']]`, organism_records `['NCBITaxon:42005', 'sra']`, narrative `Model narrative. (Read 'HEV' as the organism Porcine hemagglutinating encephalomyelitis virus (NCBI Taxonomy 42005); HEV: NCBI Taxonomy 42005; searching NCBI SRA sequencing records ...`
  - branch, reply empty twice: the same binding and line.
- Why it matters: "a confident wrong record is worse than a missing one". A person asking for hepatitis E sequencing runs from pork liver (a real food-safety question) gets runs of a different pig virus. The reading line names the wrong virus, but a reader who typed "HEV" may not recognise "Porcine hemagglutinating encephalomyelitis virus" as wrong, and it looks plausible beside "pork". The general cause: one Taxonomy hit for a short acronym under `[All Names]` is not proof of meaning (also `CMV` is one hit, cucumber mosaic virus; `IBV`, `MHV` and `RSV` are acronyms shared by several viruses where Taxonomy happens to hold one or two). An all-capitals acronym of five letters or fewer matched only as a Taxonomy synonym could be treated as "several" or asked.
- NOT FIXED

### A-56a-07: "fruit fly" asks the person to choose between two Drosophila species, the first an obscure one
- Severity: minor (develop bound nothing and went on to search)
- What: "fruit fly" tagged as a disease reaches the lookup, Taxonomy answers two ids (it reads two), and the several-ask offers "Drosophila gunungcola" first and "Drosophila melanogaster" second as rewritten questions.
- Reproduction: offline Think driver, reply `[("fruit fly","disease")]`, record type assembly, question `"Genome assemblies of the fruit fly gut bacteria"`:
  - develop: resolved `[]`, no ask.
  - branch: ask `'fruit fly' matches more than one NCBI record, so I have not picked one for you. ...`, options `['Genome assemblies of the Drosophila gunungcola gut bacteria', 'Genome assemblies of the Drosophila melanogaster gut bacteria']`
- Why it matters: the choices are whatever two ids Taxonomy returned first, not the records that fit best, and neither choice answers the question asked (gut bacteria of flies). Because `_organism_taxids` reads only two ids, "several" never lists more than two organisms, so the buttons may omit the one meant.
- NOT FIXED

### A-56a-08: The two-phrase cap is spent on "Illumina" and the word "SRA", so the card's own question asks "which organism?" while naming SARS CoV-2
- Severity: major (better than develop, which answered about the disease SARS, but the card's own question still fails, with a misleading ask)
- What: when the model tags a condition as a disease ("Illumina", or "clinical respiratory samples") and names no organism, that span takes lookup slot 1. The fallback candidates are `['SRA', 'SARS CoV-2']`, both unbound by the disease fallback, and "SRA", the database name the person typed, takes slot 2. "SARS CoV-2" hits the cap and is never looked up. The question ends with the none-ask about "Illumina".
- Reproduction: offline Think driver with a trace of `LookupBudget.take_phrase` and `look_up`, reply `[("Illumina","disease")]`, record type sra, question `"Find SRA runs of SARS CoV-2 sequenced on Illumina from clinical respiratory samples"`:
  ```
  TAKE_PHRASE 1 True
  LOOKUP 'Illumina' none
  TAKE_PHRASE 2 True
  LOOKUP 'SRA' none
  TAKE_PHRASE 2 False
  LOOKUP 'SARS CoV-2' None
  ask: I could not find 'Illumina' as an organism, gene or condition in NCBI, so I cannot tell which organism's SRA sequencing records you want. Ask again naming the organism as NCBI spells it, ...
  ```
  - With `("clinical respiratory samples","disease")` instead: ask `I could not find 'clinical respiratory samples' as an organism, gene or condition in NCBI, so I cannot tell which organism's SRA sequencing records you want.`
  - develop, both replies: resolved the three SARS disease records.
- Why it matters: the person named the virus and is told the system cannot tell which organism they mean. The candidate order puts the database's own name ahead of the subject, and the cap is counted per phrase in order rather than spent on the most name-like candidates. The model tagging a condition as a disease with no organism is a live shape (the build report's own runs show "organism plus two conditions as diseases" and "Illumina as disease"); without the organism tag this is what happens.
- NOT FIXED

### A-56a-09: A name run swallows the next word, so "SARS CoV 2 SRA runs" and "SARS-CoV-2 BA.5 SRA runs" read nothing on a twice-empty reply
- Severity: minor (develop bound the disease SARS on the first and nothing on the second; the branch binds nothing on both)
- What: `name_runs` joins any following all-capitals word to a name, so the candidate is "SARS CoV 2 SRA" or "SARS-CoV-2 BA.5 SRA". Taxonomy does not know the run, `split_unplaced_runs` splits it into words tried only as exact gene symbols, and the virus is never read. The same happens to any organism name followed by an acronym ("HIV-1 RT", "SARS-CoV-2 RBD", "MERS CoV ORF").
- Reproduction: `_gene_shaped_fallback_candidates("SARS CoV 2 SRA runs", [], [])` returns `['SARS CoV 2 SRA']`; for `"SARS-CoV-2 BA.5 SRA runs"` it returns `['SARS-CoV-2 BA.5 SRA']`. Offline Think driver, empty reply, record type sra: branch resolved `[]`, organism_records `None` on both; develop resolved the SARS disease records on the first and `[]` on the second.
- Why it matters: the build report states twice-empty replies read "SARS CoV 2"; that holds only when the name is followed by a lower-case word. A person who puts the virus first in the question gets no reading and no ask.
- NOT FIXED

### A-56a-10: The several-ask's buttons replace the phrase inside another word, so a click asks a garbled question
- Severity: minor (new code; reachability depends on the phrase also standing inside an earlier word)
- What: `several_question` rewrites the person's question with `re.compile(re.escape(phrase), re.IGNORECASE).sub(..., count=1)`, with no word boundary. The first match can be inside a longer word, and only that one is replaced.
- Reproduction: direct call of the branch's `phrase_lookup.several_question`, no network:
  - phrase "fly", question `'Butterfly and fly genome assemblies'`: options `['ButterDrosophila melanogaster and fly genome assemblies', 'ButterDrosophila gunungcola and fly genome assemblies']`
  - phrase "RSV", question `'Find SRA runs of hRSV and RSV in infants'`: options `['Find SRA runs of hRespiratory syncytial virus and RSV in infants', 'Find SRA runs of hTenuivirus oryzaclavatae and RSV in infants']`
- Why it matters: the buttons are the person's way out of the ask; a click sends a question that still contains the ambiguous phrase and a nonsense word, so it can be asked again or misread. The phrase's own position in the question is known to the caller for fallback candidates (`name_runs` offsets) and could be used instead of a search.
- NOT FIXED

### A-56a-11: The content retry fires on every topic question that names no gene, disease or organism, and one live run took 46 s before any search
- Severity: major (worse than develop: speed is a feature, and the owner's ceiling is 20 s for the whole answer)
- What: `_content_retry_reason` returns "nothing" for any reply that names no gene, disease or organism. A topic question legitimately names none ("CRISPR base editing papers ..."), so every such question pays a second Think call, which can change nothing useful (its reply is empty again). On one of three live runs the retry did not come back usable and Guardrail, Think and Plan alone took 46.4 s; the same question on develop took 2.7 to 4.0 s. The retry is bounded only by Think's own step deadline, not by a budget of its own.
- Reproduction: live, `CLASSIFIER_PROVIDER=jev`, plan model `deepseek/deepseek-v4-flash`, the builder's probe adapted (Guardrail, Think and Plan only), question `"CRISPR base editing papers from the last two years"`, 3 runs each:
  - develop: `4.0s`, `2.7s`, `2.9s`; first reply `[]` each time; cost 0.00039 to 0.0004
  - branch: `4.8s` (retry reply `[]`), `46.4s` (retry_reason `nothing`, retry `None`, cost `0.00152`), `11.3s` (retry reply `[]`); cost 0.00058 on the two normal runs
  - raw line of the slow run: `{"run": 2, "secs": 46.4, "first": [], "first_record_type": "none", "retry_reason": "nothing", "retry": null, "resolved": [], ... "ended": "planned 3 tool calls", ... "cost": 0.00152}`
- Why it matters: topic questions are a large share of what people type (papers on a method, a technique, a field). Each now costs a second model call (about +45 percent of the Think, Plan cost measured here) and seconds of waiting, and a slow or failed provider reply on the retry holds the whole answer. The 46 s run may be a provider stall that develop would equally have suffered on its first call, so I am unsure how often it happens; but it happened inside the retry, which develop never makes. A retry gated to records questions (the card's failure shape), or a short deadline of its own, would avoid this.
- NOT FIXED

A-56a-11, the bound read from the code: the retry is awaited against Think's step deadline (`_step_deadline("think")`), and the plan tier's step budget is 45 s (`harness._TIER_STEP_BUDGET_S["plan"] = 45.0`); the retry's own call is given `budget_for_step("think", "lookup")`. So a retry that stalls may hold Think for up to about 45 s minus the first call, which matches the 46.4 s run. Nothing caps the retry near the 20 s answer ceiling.

A-56a-06, live (same probe as A-56a-11, question `"Find SRA runs of HEV from pork liver"`, 2 runs each): develop's model tagged `HEV` as a disease once and as a gene once, and bound nothing (`res=[]`, one run refused on the unresolved gene `HEV`). The branch's model tagged `HEV` as an organism on both runs, and both bound `NCBITaxon:42005` with `organism_records ['NCBITaxon:42005', 'sra']`. The organism-tag path is unchanged code, so develop would bind the pig virus too when its model tags HEV as an organism; the difference in these four runs is sampling. The branch-only paths (disease tag, empty reply) are the offline reproductions above.

### A-56a-12: Every gene SRA question pays the "records" retry, which changed nothing on 3 of 3 live runs
- Severity: minor (worse than develop on speed and cost only)
- What: `_content_retry_reason` returns "records" when the reply asks for SRA runs or assemblies and names only genes. A gene's SRA runs are a normal question; the retry asks the model to name an organism or disease, and the model answered with the same gene.
- Reproduction: live, same probe, `"Find SRA runs for TP53 knockout cell lines"`, 3 runs each:
  - develop: `3.3s`, `2.6s`, `3.2s`; first `[['TP53', 'gene']]`, resolved `NCBIGene:7157`; cost 0.00039 to 0.0004
  - branch: `5.7s`, `4.3s`, `3.9s`; retry `records:[['TP53', 'gene']]` each time; resolved `NCBIGene:7157`; cost `0.00079`, `0.0006`, `0.00059`
  - offline, a retry reply that swaps the gene for `("human","organism")` still resolves TP53 on the branch (the gene fallback reads it from the text), so I found no wrong answer from this retry, only time.
- Why it matters: 1 to 2.4 s and about half again the Think and Plan cost on every gene records question, for no change in these runs.
- NOT FIXED

### A-56a-13: A pronoun follow-up whose first reply names nothing is pushed to name something, and a condition word then replaces the remembered gene
- Severity: major, unsure (simulated reply; the one live retry on this shape tagged the remembered BRCA1 correctly)
- What: the retry message says `Leave "entities" empty only if the query names none of these`, and fires on a follow-up like "and what about it in children?" whose correct reply names nothing (memory supplies BRCA1). If the second reply tags "children" or "variants" as a disease, MedGen binds eight generic records by containment, something resolved, so memory never binds. Develop makes one call; an empty reply goes to memory.
- Reproduction: offline Think driver, memory `BRCA1 -> NCBIGene:672`, first reply empty, second reply as stated:
  - `"and what about it in children?"`, second reply `[("children","disease")]`: develop resolved `[]` (memory binds BRCA1 in Plan); branch resolved `[['children', 'MedGen:C0423941'], ['children', 'MedGen:C0425209'], ['children', 'MedGen:C0425239']]`, narrative `(children: 8 of at least 20 MedGen records matched by name)`
  - `"What variants cause it?"`, second reply `[("variants","disease")]`: branch resolved `[['variants', 'MedGen:C0042331'], ...]`, `(variants: 8 of at least 20 MedGen records matched by name)`
  - live, `"and what about it in children?"` with BRCA1 remembered, 3 runs on the branch: one first reply was empty, its retry tagged `[['BRCA1', 'gene']]` and answered correctly. So the bad second reply is not yet observed live; the build report also notes the retry fires on pronoun follow-ups and was left for slice 3.
- Why it matters: the code map's query 111 controls and queries 1 then 20 are the follow-ups most people type. A retry that makes the model find a subject where the right answer is "none, use memory" turns a right answer about BRCA1 into an answer about generic "children" records. Skipping the "nothing" retry when session memory exists would remove the exposure until slice 3.
- NOT FIXED

### A-56a-14: The digit-piece exception is skipped when the model names the human organism as "Homo sapiens", so "TP53-null" loses TP53
- Severity: minor (worse than develop on this question)
- What: a digit piece is tried only when `fallback_taxon.casefold() == _DEFAULT_TAXON`, that is, when the taxon text is literally "human". A model span "Homo sapiens" (or "humans", "H. sapiens") is the human organism but fails the text comparison, so the piece is never tried.
- Reproduction: offline Think driver, reply `[("Homo sapiens","organism")]`, record type none, question `"papers on TP53-null Homo sapiens cell lines"`: develop resolved `[['TP53', 'NCBIGene:7157']]`; branch resolved `[]`.
- Why it matters: a gene question that answers on develop answers with no gene. The check could compare the confirmed taxon id (9606) rather than the text.
- NOT FIXED

## Held, with my own probes

- No piece cut: "SARS" was never taken out of "SARS CoV-2", "SARS COV2" or "SARS CoV-2 variants" on any branch run (offline, empty and tagged replies; live, 2 runs). "SARS COV2" and "SARS CoV-2 variants" now read as 2697049 where develop bound the disease SARS.
- Confirmed spans unchanged: BRCA1, brca1, GCK, MODY, MET, SET, CAT, ALS, MLH1 and MSH2 with colorectal cancer, the Salmonella isolate question, "and BRCA2?" after BRCA1, "BRCA1 ClinVar", and the hyphenated gene questions TP53-mutant, BRCA1/2 and HER2-positive gave the same bindings as develop offline, and live for BRCA2, HER2-positive and SARS-not-COVID.
- The cap: with three unplaceable names, two phrases were looked up, the third was not, and the question's own ceiling paid only for the disease checks (offline trace of every NCBI call).

## Verdict

FAIL against the card's goal ("never answer about the wrong subject"):

- A-56a-06 is a new confident wrong organism (HEV read as a pig virus).
- A-56a-03 and A-56a-05 bind a different subject where develop bound nothing.
- A-56a-02 tells a person that well-known diseases are not in NCBI.
- A-56a-08: the card's own question still fails when the model tags a condition and no organism.
- A-56a-11: the content retry adds a second model call to every topic question and, once, 46 s.

All of these sit inside this slice's new code: the lookup, the fallback order, the none-ask and the content retry.

What I verified with my own probes, and what I only read:

- Verified by running: every reproduction above.
  - Offline, through `think_node` with real NCBI and scripted model replies, against detached worktrees of develop 535943bc and the branch e01a4e72.
  - Through the branch's `look_up` primitives directly.
  - Live, 56 Guardrail, Think and Plan runs, paired develop and branch.
- Only read: the cap's "eleventh call is refused at the transport" (I saw the phrase cap hold, not a call refused); the Gene leg's failure reading as "no gene"; the 500-character narrative rule.
- Not run: Act and Write, so the rendered answer and the buttons on screen were not seen.

Spend: 56 live runs, $0.0307 by the probe's cost field. NCBI E-utilities without a key, paced at about one request a second.
