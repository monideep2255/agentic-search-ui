# Card 15 adversary report, round 1

Base: 24b20e7d307ad43483548d424ca7578fd7a1fbe3 (fix/card15-checked-graph-searches). Reviewer: adversary. Findings are filed as found; none are fixed, triaged or closed here.

## Findings

### A-15-01: A count question Think calls single_hop, or asks in German, is treated as not a count and gets the disease's own record
- Severity: major
- What: `written_search_allowed` is `_wants_count`, which accepts "count" and "number of" only on the `aggregate` class and recognises only the English "how many". A count question on any other class, or in another language, is classed as not a count. With no shaped template it now takes the disease's own record, where develop let a written search try to count.
- Reproduction (routing probe, `select_template` on this branch against `origin/develop`'s `cypher_templates.py`, same bindings):
  - `Count the pathogenic variants in cystic fibrosis`, single_hop, [MedGen:C0010674]: dev=WRITTEN(model), new=disease_record_one
  - `Wie viele Varianten verursachen Mukoviszidose?`, aggregate, [MedGen:C0010674]: dev=WRITTEN(model), new=disease_record_one (the module already lists "Krankheit" for G-050, so German questions are expected)
- What a person sees: they asked for a number and get one cystic fibrosis record, cited and shown as a successful graph result, with no number and no word that the graph was never asked to count.
- NOT FIXED

### A-15-02: A disease question asking for variants, papers or phenotypes now shows the disease's own record as the graph answer, including the canned "What variants cause it?" chip
- Severity: major
- What: a Disease has only one shape ("genes"). A variants, papers or phenotype word on a Disease anchor matches no shape, so on single_hop or multi_hop `_shaped_template` returns None and `_record_fallback` returns `disease_record_one`. The result is `status: ok` with one row, so nothing says the variants were not searched. `_shaped_template`'s own comment still gives the reason a Disease on the hop classes must NOT take the record: a disease Think resolved from a common noun ("tumour") would turn a correct refusal into an unrelated record (G-014). The new fallback brings that back for one bound disease.
- Reproduction (same probe):
  - `Which variants cause cystic fibrosis?`, single_hop, [MedGen:C0010674]: dev=WRITTEN(model), new=disease_record_one
  - `What variants cause it?` (the follow-up chip in `frontend/src/App.tsx:143`, memory-bound to the disease), single_hop: dev=WRITTEN(model), new=disease_record_one
  - `Which variants cause tumour?`, single_hop, [MedGen:C0027651]: dev=WRITTEN(model), new=disease_record_one
  - `Which papers mention cystic fibrosis?`, single_hop: dev=WRITTEN(model), new=disease_record_one
  - `Which diseases have phenotype seizures?`, single_hop, [MedGen:C0036572]: dev=WRITTEN(model), new=disease_record_one
- What a person sees: a variants question answered by a cited card for the disease itself, which reads as "the graph's answer is this disease record". There is no variants list and no sentence saying the graph search for variants was skipped. With "tumour" it is a confident record for a disease concept the person never named.
- NOT FIXED

### A-15-03: An organism with any hop word gets only its own taxon record ("Which genes are in Salmonella enterica?", "What diseases are in humans?")
- Severity: minor
- What: OrganismTaxon joined `_TEMPLATED_LABELS` with no hop rows, so every non-count organism question takes `organismtaxon_record_one`.
- Reproduction: `Which genes are in Salmonella enterica?`, single_hop, [NCBITaxon:28901]: dev=WRITTEN(model), new=organismtaxon_record_one. `What diseases are in humans?`, single_hop, [NCBITaxon:9606]: dev=WRITTEN(model), new=organismtaxon_record_one.
- What a person sees: a genes question answered by one Homo sapiens or Salmonella taxonomy card, shown as a successful graph result with no word that the genes were not searched.
- NOT FIXED

### A-15-04: "Is ClinVar:17661 pathogenic for disease?" and "What gene is ClinVar:17661 in?" are now answered by a different question's template
- Severity: minor (unsure)
- What: the keyword "disease" sends any variant question that contains it to `sequencevariant_diseases_one`. A variant question with a gene word (SequenceVariant has no "genes" shape) takes the variant record.
- Reproduction: `Is ClinVar:17661 pathogenic for disease?`, lookup: dev=WRITTEN(model), new=sequencevariant_diseases_one. `What gene is ClinVar:17661 in?`, single_hop: dev=WRITTEN(model), new=sequencevariant_record_one.
- What a person sees: a list of linked conditions in answer to a significance question, and a variant card in answer to a gene question. Unsure whether the variant record carries its gene and significance in its fields, which would make the second case adequate.
- NOT FIXED

### A-15-05: A graph search that never ran is shown to the person as a graph search that ran and found nothing
- Severity: major
- What: when D5 declines the graph search, `cypher_query` returns `status: "empty"` with the reason only in `error`. Act's summary appends `error` only when `status == "error"` (`core/graph.py`, after `summary = f"{output.row_count} row(s) of ..."`), so the stream carries the same "0 row(s) of 0" a real search with no hits carries. The `tool_start` frame for the planned call is already on screen, so the person sees the knowledge-graph helper "is searching the knowledge graph" (`RunProgress.tsx:208`), then "0 rows" and "cypher_query, 0 results" (`useRunView.ts:511`, `:1037`).
- Reproduction (`core.graph._execute_planned_call` with a stub harness that raises on any model use, and `execute_cypher` replaced by a recorder returning no rows):
  - `What is GO:0006281?`, lookup, [GO:0006281]: `status=empty summary='0 row(s) of 0' result_count=0 graph_calls=0`, structured.error='No checked graph search fits this question, so the knowledge graph was not searched; ...'
  - `Which diseases are linked to BRCA1?`, single_hop, [NCBIGene:672], where the graph WAS searched and returned nothing: `status=empty summary='0 row(s) of 0' result_count=0 graph_calls=1`
  - The two stream summaries are byte-identical. Only the structured `error` differs, and nothing in the UI path reads it.
- What a person sees: "searching the knowledge graph ... 0 results", which reads as "the graph has nothing on this", when the graph was never asked. Develop showed "The background search of the knowledge graph did not finish ... Ask again to retry" for a lost written search: wrong advice, but it did say the graph was not consulted. The branch replaces it with a false negative, which is the lying trust signal the card set out to avoid. The code comment at the gate ("the person is not told a search did not finish") treats this as intended. It is still a silent absence claim.
- NOT FIXED

### A-15-06: The new variant-conditions search returns conditions with no readable name, including a placeholder shown as a condition
- Severity: major
- What: on the live graph, every Disease row `sequencevariant_diseases_one` returned for three probed variants carries a source-vocabulary token as its `name`, not a condition name. One row, MedGen:C3661900, came back for two unrelated variants and is, as far as I know, ClinVar's "not provided" placeholder concept, which the graph names "OMIM allelic variant". I did not confirm that identity from the graph; the graph row carries no other name and empty xrefs.
- Reproduction (read-only, `cypher_query` with a stub harness that raises on any model use, `.env` reader credentials, run 2026-10-08):
  - `What conditions is this variant linked to?`, single_hop, [ClinVar:17661]: template=sequencevariant_diseases_one, 12 rows, names 'MONDO', 'MeSH', 'SNOMEDCT_US', 'MONDO', 'HPO', 'SNOMEDCT_US', 'MONDO', 'MedGen', 'OMIM allelic variant', 'MedGen', 'MedGen', 'MedGen'. `core.graph._is_vocabulary_token_artifact` returns True for all 12.
  - [ClinVar:12345]: 1 row, MedGen:C1275126, name 'GARD'.
  - [ClinVar:1179956] (an NM_000162.5(GCK) intronic variant): 1 row, MedGen:C3661900, name 'OMIM allelic variant'. The same id is row 9 for ClinVar:17661.
  - The forced record of MedGen:C3661900, CN221562, CN377757 and C3280442: names 'OMIM allelic variant', 'MedGen', 'MedGen', 'MedGen', xrefs '' on every row.
- What a person sees: "conditions linked to this variant" as a list of cited MedGen links with no condition name. If C3661900 is "not provided", the only cited condition for ClinVar:1179956 is "no condition given", shown as a condition the graph links to the variant: a confident wrong record. The data fault is the known MedGen ETL defect (F-2.1-B07). What is new is this branch routing variant questions onto it, so the fallback no longer reaches the variant's own record, which has a readable HGVS name.
- NOT FIXED

### A-15-06, addendum: the downstream placeholder drop softens the list but not the count
- Severity: unchanged, major. This addendum narrows the finding; it does not close it.
- What I read afterwards: `findings.drop_placeholder_condition_findings` removes a Disease finding whose resolved MedGen title is "not provided", "not specified" or "see cases", and `apply_resolved_disease_names` replaces artifact names with live MedGen titles. So the list a person sees may show real names and drop C3661900 if it resolves to "not provided". I did not run that live path (it needs a Layer 2 call). For ClinVar:1179956 the variant's only condition would be dropped, and I have not established what the answer then says. Filed as unsure.
- The count form is not covered by that drop. See A-15-09.

### A-15-09: "How many conditions is this variant linked to?" counts ClinVar's placeholder links as conditions
- Severity: major
- What: `sequencevariant_diseases_one_count` is `count(DISTINCT x)` over every `has_phenotype` Disease, placeholders included. The placeholder rule (D2: "a cell and a count exclude them") is applied to findings, not to this aggregate row.
- Reproduction (read-only live, stub harness, no model call): `How many conditions is ClinVar:1179956 linked to?`, lookup, [ClinVar:1179956]: template=sequencevariant_diseases_one_count status=ok rows=1 fields={'diseases_count': 1}, cited to https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956/. The records form for the same variant returns one row, MedGen:C3661900, which the list path drops as a placeholder if it resolves to "not provided".
- What a person sees: "linked to 1 condition", cited to the ClinVar page, for a variant whose ClinVar record names no condition. For ClinVar:17661 the count would be 12, while the list shows fewer after placeholders are dropped. The number and the list disagree, with no word on why. Unsure of C3661900's MedGen title; the graph names it "OMIM allelic variant".
- NOT FIXED

### A-15-07: Questions that are not graph counts still take the model-written search because they contain "how many"
- Severity: major
- What: the "true count" gate is the regex `\bhow\s+many\b` anywhere in the raw question (`query_intent` is the question text, `core/graph.py` builds it from `query_text[:1000]`). A question asking about people, years, or "no matter how many" passes the gate, and the plan tier writes a graph search for it.
- Reproduction (`select_template` plus `written_search_allowed` on this branch):
  - `How many people in the US have Lynch syndrome?`, single_hop, [MedGen:C0009405]: WRITTEN
  - `How many people with BRCA1 variants get breast cancer?`, multi_hop, [NCBIGene:672, MedGen:C0006142]: WRITTEN
  - `No matter how many there are, list every paper on PMID 1 and PMID 2`, single_hop, [PMID:1, PMID:2]: WRITTEN
  - `Tell me about BRCA1 and TP53 and how many papers each has`, exploratory, [NCBIGene:672, NCBIGene:7157]: WRITTEN
  - `What is the count of patients with ClinVar:17661?`, aggregate, [ClinVar:17661, NCBIGene:672]: WRITTEN
- What a person sees: the graph holds no prevalence data, so a written count over it answers a different question (G-014's failure) with a confident, cited number. The ticket says "only a true count question may still use a written one". These are not true counts, and the third is a list request.
- NOT FIXED

### A-15-08: A variant-and-disease or variant-and-gene question now runs no graph search, though the new hop answers it
- Severity: major
- What: SequenceVariant now has a label and a `has_phenotype` hop, but `_mixed_gene_disease_template` handles only Gene plus Disease. A ClinVar id bound with a Disease or a Gene is a label mix, so `_record_fallback` refuses (two bindings), and `cypher_query` returns `empty` with no graph call. Develop sent these to the written search. The same happens when an organism CURIE rides beside a disease.
- Reproduction (routing probe, this branch against `origin/develop`):
  - `Is ClinVar:17661 linked to breast cancer?`, lookup and single_hop, [ClinVar:17661, MedGen:C0006142]: dev=WRITTEN(model), new=NO_GRAPH_SEARCH
  - The same question with only [ClinVar:17661] bound (disease unresolved): new=sequencevariant_record_one. The person asked about a link and gets the variant card.
  - `What disease does ClinVar:17661 in BRCA1 cause?`, multi_hop, [ClinVar:17661, NCBIGene:672]: dev=WRITTEN(model), new=NO_GRAPH_SEARCH
  - `Which variants in BRCA1 and BRCA2 cause breast cancer?`, multi_hop, [NCBIGene:672, NCBIGene:675, MedGen:C0006142]: dev=WRITTEN(model), new=NO_GRAPH_SEARCH
  - `Which genes are linked to cystic fibrosis in humans?`, single_hop, [MedGen:C0010674, NCBITaxon:9606]: dev=WRITTEN(model), new=NO_GRAPH_SEARCH. Without the taxon this question takes `disease_genes_one`, so adding "in humans" turns the graph off.
  - `Tell me about PMID 11237011 and PMID 12345`, multi_hop: dev=WRITTEN(model), new=NO_GRAPH_SEARCH
- What a person sees: "searching the knowledge graph ... 0 results" (A-15-05) for the one question the graph is built to answer, whether this variant is linked to this disease. The live answer gets thinner and nothing says why. The build report lists GO, MeSH, several-Article, Gene-plus-Article and several-gene paths as lost, but not the variant-plus-disease, variant-plus-gene and organism-qualifier paths.
- NOT FIXED

### A-15-10: The several-variant conditions search silently drops every condition a later variant shares with an earlier one, under a completeness claim
- Severity: major. This is inside new code from this phase: the `("SequenceVariant", "diseases")` hop and its `_many` form.
- What: `sequencevariant_diseases_many` returns `RETURN a, x` as a flat row stream, and `cypher_query._dedupe_by_cited_record` keeps only the first row per CURIE across the whole stream. A condition linked to two variants is listed under the first variant only. Variants from one gene share most of their conditions, and every variant shares the ClinVar placeholders, so later variants lose most of their list. `total_available` and `row_count` both report the deduplicated number and `truncated` is False. This is the F-2.1-J4-03 shape ("silent deletion under a completeness claim") on a new template. The `gene_*_many` hops likely share the same mechanism; I did not probe them.
- Reproduction (read-only live, stub harness, no model call). Each variant alone (`sequencevariant_diseases_one`) against the same five in one call (`sequencevariant_diseases_many`), with rows grouped by the preceding SequenceVariant row:
  - ClinVar:17661 alone 12, in combined 12, lost []
  - ClinVar:17662 alone 13, in combined 3, lost ['MedGen:C0027672', 'MedGen:C0346153', 'MedGen:C0677776', 'MedGen:C0919267', 'MedGen:C2676676', 'MedGen:C3280442', 'MedGen:C3661900', 'MedGen:C4554406', 'MedGen:CN221562', 'MedGen:CN377757']
  - ClinVar:17665 alone 8, in combined 1, lost ['MedGen:C0006142', 'MedGen:C0027672', 'MedGen:C0677776', 'MedGen:C2676676', 'MedGen:C3661900', 'MedGen:CN221562', 'MedGen:CN377757']
  - combined rows 19, against 33 true variant-condition links
  - The same effect with two variants: [ClinVar:17661, ClinVar:1179956] gives 14 rows. MedGen:C3661900 appears only under ClinVar:1179956, so ClinVar:17661 shows 11 of its 12.
- What a person sees: asking which conditions ClinVar:17662 and ClinVar:17665 are linked to, they are shown ClinVar:17665 with one condition, and MedGen:C0006142 (the MedGen concept for breast cancer, by my reading) not attributed to it. Nothing says rows were removed. A confident, cited, incomplete mapping.
- NOT FIXED

### A-15-11: A ClinVar id typed as an accession (VCV, RCV) or with a leading zero finds nothing, and reads as "the graph has no conditions"
- Severity: minor
- What: `resolve_exact_identifiers` takes any verbatim `ClinVar:<id>` as ground truth at confidence 1.0, and the new hop matches `id` exactly. The graph keys variants as `ClinVar:<variation id>`, so the VCV accession of the same variant, an RCV accession, or a zero-padded id return 0 rows. The tool reports `status: empty` with no note, the same as a variant that has no conditions.
- Reproduction (read-only live, stub harness, `What diseases are linked to ...?`, single_hop):
  - [ClinVar:17661]: sequencevariant_diseases_one ok rows=12
  - [ClinVar:017661]: sequencevariant_diseases_one empty rows=0 0.43s
  - [ClinVar:VCV000017661]: sequencevariant_diseases_one empty rows=0 0.41s
  - [ClinVar:RCV000019230]: sequencevariant_diseases_one empty rows=0 0.42s
- What a person sees: "searching the knowledge graph ... 0 results" for a variant the graph holds with 12 linked conditions. Develop's written search probably missed these too, so this is not certainly a regression. It is filed because the new checked search is now the only graph route for these questions.
- NOT FIXED

### A-15-12: A true "how many" question about an organism or a variant, classed lookup or exploratory, now gets a record and no count
- Severity: major. Inside this phase's change: adding SequenceVariant and OrganismTaxon to `_TEMPLATED_LABELS`.
- What: `_shaped_template` returns `_record_template` for ANY no-shape question on the lookup or exploratory class, before `_wants_count` is consulted. Develop sent ClinVar and NCBITaxon anchors to the written search, because neither label could anchor a template. Now they hit the record branch first. The ticket's own exception, "only a true count question may still use a written one", is not honoured for these questions, though `written_search_allowed` returns True for them. The comment above `_HOW_MANY_PATTERN` says the tool's premise gate sends every question as `lookup`, which would make this the common case.
- Reproduction (routing probe, this branch against `origin/develop`):
  - `How many genes does Salmonella enterica have?`, lookup, [NCBITaxon:28901]: dev=WRITTEN(model), new=organismtaxon_record_one
  - same question, exploratory: dev=WRITTEN(model), new=organismtaxon_record_one
  - `How many submissions does ClinVar:17661 have?`, lookup: dev=WRITTEN(model), new=sequencevariant_record_one
  - `How many genes is ClinVar:17661 in?`, exploratory: dev=WRITTEN(model), new=sequencevariant_record_one
  - Pre-existing and unchanged, for context: `How many variants cause cystic fibrosis?`, lookup, gives disease_record_one on both, and on single_hop gives WRITTEN on both. The same count question gets a record or a written count depending only on Think's class.
- What a person sees: they asked for a number and get one organism or variant card, shown as a successful graph result, with no number and no word that no count was attempted.
- NOT FIXED

### A-15-13: When the live layers also come back empty, the refusal says "could not find grounded evidence" about a graph that was never searched
- Severity: minor (unsure of how often the live layers are all empty on these paths)
- What: a declined graph search is `empty`, not `error`, so it never reaches `failed_searches`. `synthesis/refuse.py`'s chooser then falls through to `REFUSE_MESSAGE`. Its own comment reserves that message for "Nothing failed and nothing was found".
- Reproduction (read, plus the A-15-05 probe showing the declined call's outcome is `status=empty` with no failed-search entry): with A-15-08's `Is ClinVar:17661 linked to breast cancer?` and no Layer 2 or 3 rows, the reply is "I could not find grounded evidence for this. Try NCBI's cross-database search: ...". I did not run Write end to end.
- What a person sees: "could not find" read as "the evidence does not exist", when the system chose not to look in its own graph.
- NOT FIXED

### A-15-14: A mistyped ClinVar id returns a different variant's conditions, and nothing shown names the variant they belong to
- Severity: major (unsure of how much the live layers would catch it)
- What: `sequencevariant_diseases_one` returns only the Disease rows (`RETURN x`), never the anchor variant. A ClinVar id is typed by the person and taken as ground truth (confidence 1.0, no live check), so a transposed digit binds a different real variant. Its conditions come back as the answer, and no returned row carries the variant's HGVS name or gene. Before this phase the question had no checked graph route.
- Reproduction (read-only live, stub harness, `What conditions is this variant linked to?`, single_hop):
  - [ClinVar:17661] (BRCA1 c.181T>G): 12 Disease rows
  - [ClinVar:17616] (digits transposed): template=sequencevariant_diseases_one status=ok rows=1 types=['Disease'] curies=['MedGen:C1869123']. The record template for the same id shows it is `NM_000070.3(CAPN3):c.257C>T (p.Ser86Phe)`, a CAPN3 variant; the conditions result carries no such row.
  - [ClinVar:1766]: empty, 0 rows, and the record is empty too
- What a person sees: someone asking about a BRCA1 variant who slips two digits gets a cited condition for a CAPN3 variant, a different gene and a different disease, and the graph rows give them no way to tell. "A confident wrong record is worse than a missing one."
- NOT FIXED

### A-15-15: The author's routing test binds rs334 to ClinVar:17661, which is a different variant
- Severity: minor (test quality, unsure)
- What: `test_a_variant_conditions_question_takes_the_checked_has_phenotype_hop` has the row `("Which diseases are associated with rs334?", ["ClinVar:17661"], "single_hop", "sequencevariant_diseases_one")`. rs334 is the HBB sickle-cell variant, and ClinVar:17661 is BRCA1 c.181T>G (its graph record name, `NM_007294.4(BRCA1):c.181T>G (p.Cys61Gly)`, is shown in my live probe for A-15-10). The test checks routing only, so it passes. It does write a wrong question-to-id pairing into the suite as an expected case. If the build believed an rs id resolves to a ClinVar id this way, that belief is untested anywhere I saw.
- Reproduction: `git diff origin/develop...HEAD -- tests/system_03_search_agent/tools/test_cypher_templates.py`, the parametrize list for that test.
- NOT FIXED

## Verdict

FAIL against the ticket's promise as a person reads it: "The system never writes its own graph search for a question a checked search can answer; only a true count question may still use a written one."

- The first half holds for every routing case I probed: no non-count question reached the plan tier.
- The second half does not hold in either direction:
  - Non-counts still reach the written search through "how many" (A-15-07).
  - True counts are denied it and get a record (A-15-01, A-15-12).
- The trust signal is worse than develop's in one way: a graph search that never ran is shown as "searching the knowledge graph, 0 results" (A-15-05).
- The new variant-conditions search loses most of a later variant's conditions while claiming completeness (A-15-10), counts placeholders (A-15-09), and returns a mistyped id's conditions with no variant shown (A-15-14).

Inside this phase's new code (the review loop's stop condition): A-15-10, A-15-12 and A-15-14 sit in the new `SequenceVariant` and `OrganismTaxon` labels and the new `has_phenotype` hop. A-15-05 sits in the new `empty` decline path.

Verified with my own probes:
- Routing on this branch against `origin/develop` (`select_template`, `written_search_allowed`): A-15-01 to A-15-04, A-15-07, A-15-08, A-15-12.
- Act's outcome for a declined call, through `core.graph._execute_planned_call`: A-15-05.
- Read-only live graph through `cypher_query` with a model-refusing stub harness: A-15-06, A-15-09, A-15-10, A-15-11, A-15-14.

Read only, not run:
- The UI wording in `RunProgress.tsx` and `useRunView.ts`.
- The Write-side placeholder drop and MedGen title resolution (A-15-06 addendum).
- The refusal chooser (A-15-13).
- The identity of MedGen:C3661900 as "not provided".

The author's two test files pass on my run: 87 passed; 15 passed, 1 skipped. That is not evidence for or against the findings above.
