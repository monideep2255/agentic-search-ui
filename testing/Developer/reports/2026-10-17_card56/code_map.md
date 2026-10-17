# Card 56 code map for the owner's three calls

Read-only scout, 2026-10-17, against develop at 535943bc. Every code reference is `path:line` read today, paths relative to `<repo-root>`. No model was called. NCBI E-utilities were called 60 times without a key, 0.4 s apart; every request and reply count is in [E](#e-live-ncbi-measurements).

The owner's three calls (`DECISIONS.md`, last row, 2026-10-17):

1. A word the system cannot place is looked up whole, live, in NCBI Taxonomy, Gene and MedGen; exactly one fit is used and named, otherwise the person is asked with the choices found; a word is never cut into pieces.
2. Remembered subjects fill in only when the question names no subject of its own, never in place of a name that could not be read.
3. The model marks each phrase as a subject or a condition; only subjects go through check-then-ask; a condition is applied where the database supports it, or the answer says it was not applied.

## Table of contents

- [Findings that change the design's premise](#findings-that-change-the-designs-premise)
- [A. Today's path for the four open failures](#a-todays-path-for-the-four-open-failures)
- [B. Call 1, the whole-phrase lookup](#b-call-1-the-whole-phrase-lookup)
- [C. Call 2, remembered subjects](#c-call-2-remembered-subjects)
- [D. Call 3, subjects and conditions](#d-call-3-subjects-and-conditions)
- [E. Live NCBI measurements](#e-live-ncbi-measurements)
- [F. Risks to questions that work today](#f-risks-to-questions-that-work-today)
- [What was not covered](#what-was-not-covered)

## Findings that change the design's premise

| # | Finding | Evidence | What it means for the design |
|---|---|---|---|
| P1 | Call 1 needs a phrase, and on the failing runs the model returns none. On 5 of 26 runs of the SARS-CoV-2 SRA question and 2 of 3 runs of "SARS-CoV-2 sequencing papers" Think returned no entity at all. The only phrase source then is the token fallback, which cuts words | `testing/Developer/reports/2026-10-06_card56/findings.md`; `adversary_r3.md` A3-56-05; fallback at `src/system_03_search_agent/core/graph.py:4449` and `:4513` | The token fallback cannot simply be deleted. Either Think is asked again when its reply names no subject (never built: no content retry exists, only the parse retry at `graph.py:4031`), or a separate classifier says "this question names a subject", and the person is asked when nothing was read |
| P2 | Removing the token fallback breaks questions that pass today and are pinned by tests: GCK, lower-case "brca1", the flagship BRCA1 under an empty extraction, MODY on an SRA question | Tests listed in [B4](#b4-what-tests-pin-the-token-fallback-today) | The fallback can be guarded (never cut a word, never on a word inside a subject the model named), not removed, unless P1's replacement covers empty extractions |
| P3 | "Exactly one fits" by raw search counts is true for only 5 of 14 phrases, and one of the five is wrong for a person: "CF" fits exactly one record, the human gene CFTR (Gene id 1080, CF is its alias), because MedGen's title index has no "CF" | [E](#e-live-ncbi-measurements), rows CF | "Fits" must be defined per database, and a single fit can still be the wrong reading. Saying which record was used (the owner's wording) is what protects the person here |
| P4 | Gene across all organisms is never "exactly one" for a real gene symbol: TP53 684 records, BRCA1 678, SARS 284 | [E](#e-live-ncbi-measurements) | Gene must be searched in one organism (human by default, or the organism the question names), as `resolve_symbol_to_curie` already does (`graph.py:5998`) |
| P5 | MedGen by containment is "several" for almost any real phrase, including organisms and genes: "Mycobacterium tuberculosis" 61, "Salmonella enterica" 5, TP53 92, BRCA1 16, HIV 36 | [E](#e-live-ncbi-measurements) | If MedGen "fits" means "any title hit", nearly every phrase becomes "several" and is asked back. MedGen needs its existing exact-title rule (`graph.py:3425` onward) or a narrower test, and a model-tagged gene or organism that already confirmed must not enter the three-way lookup at all |
| P6 | The whole phrase fixes the spaced name, measured: Taxonomy answers exactly one record, 2697049, for "SARS CoV-2", "SARS-CoV-2", "sars cov 2" and "COVID-19 virus", and none of them hits Gene or MedGen's code-form search | [E](#e-live-ncbi-measurements) | The premise of call 1 holds for the card's own question |
| P7 | A piece looked up alone would still be wrong in a new way: "SARS" alone is exactly one record in Taxonomy (694009, the 2003 SARS coronavirus species), 3 human genes and 3 MedGen records | [E](#e-live-ncbi-measurements) | "Never cut a word into pieces" must hold for the new lookup too, or "SARS" becomes a confident wrong organism |
| P8 | A follow-up about an organism never reaches the organism's records: with Mycobacterium tuberculosis remembered and nothing tagged, "And its SRA runs?" binds NCBITaxon:1773 to a graph query, not the SRA search | `tests/system_03_search_agent/core/test_think_sra_disease_fallback.py:266` to `:316` (arm "tuberculosis-no-entity"); memory binding only in `_select_planned_tool_call`, `graph.py:6799` to `:6804`; `organism_records` set only in Think, `graph.py:4482` to `:4502` | Call 2 is wider than the SARS case: a remembered organism has no path to its SRA or assembly records |
| P9 | Pathogen Detection's isolate search cannot apply any condition: its input is the taxon folder, AMR gene prefixes and a sample size, nothing else | `src/system_03_search_agent/tools/pathogen_detection_schemas.py:258` to `:277` | For call 3, isolates can only ever say "not applied" for a condition such as a place or a year, unless the tool gains a filter |
| P10 | Each whole-phrase lookup costs up to 5 NCBI calls (Taxonomy 1, Gene 2 legs, MedGen search and summary 2), and every one counts against the per-question ceiling of 20 | `src/system_03_search_agent/harness/call_budget.py:101`; charged at `src/system_03_search_agent/tools/ncbi_transport.py:1605` | Three phrases could spend 15 of 20 before a gene question's own fan-out (11 calls, `graph.py:4384` comment). The lookup needs its own cap and should run only for words nothing else placed |

## A. Today's path for the four open failures

What #186 changed (merge 87359f60, `git diff 87359f60^1 87359f60`): `_is_name_joiner` (`graph.py:3691`), `_only_a_piece_of_a_joined_name` (`graph.py:3699`), the skip in the disease fallback (`graph.py:4538` and `:4542`), and the parse retry's key list read from the schema (`_THINK_RETRY_KEY_LIST`, `graph.py:2611`). Nothing else in Think changed; the round 1 ideas in `findings.md` (a content retry, the Illumina classifier) were not built.

Think's order, all in `src/system_03_search_agent/core/graph.py`:

| Step | Line | What it does |
|---|---|---|
| Opening ask-back | 4266 | Only when the session has no memory and the question is 1 to 3 words |
| Exact identifiers | 4307 | Typed CURIEs, rs numbers, PMIDs |
| Window, accession, isolate | 4316, 4329, 4339 | Fixed rules; any of them skips model span confirmation (4379 to 4396) |
| Think model call | 4340 to 4374 | Question plus session memory suffix (4341) |
| Confirm model spans | 4398, `_confirm_extracted_entities` 3442 | Genes live (3518), diseases in MedGen (3542), a failed gene tried as a disease (3559); organism only sets the gene taxon (3509) |
| Organism spans kept | 4411, `_organism_spans_not_rejected` 3139 | Spans Taxonomy did not reject (3161) |
| Gene token fallback | 4449 to 4467 | Runs when nothing resolved; candidates from `_gene_shaped_fallback_candidates` 3605 |
| Organism anchor | 4482 to 4502 | Record type sra or assembly, organism span, nothing resolved, no unresolved gene; `resolve_organism` 3190 needs exactly one taxid (3219) |
| Disease token fallback | 4513 to 4560 | Nothing resolved and no unresolved gene; #186's skip at 4538 and 4542 |
| Clarification | 4642 to 4656 | `_needs_clarification` 6619; organism question 6600 when an organism span exists |
| Unresolved key | 4726 | Set only when nothing resolved |

### A1. "SARS CoV-2" typed with a space, and its variants

Question: "Find SRA runs of SARS CoV-2 sequenced on Illumina from clinical respiratory samples". The outcome depends on what the model tags.

| Model reply | Deciding line | Outcome |
|---|---|---|
| "SARS CoV-2" as organism | `_organism_taxids` 3039 answers 1 id (2697049, measured); span protected at 3666; anchor 4482 to 4502 resolves it | SRA search on NCBITaxon:2697049 (unless "Illumina" is also tagged a gene, see A4) |
| "SARS CoV-2" as disease | MedGen term `SARS[title] AND CoV[title]` answers 0 (measured), so 3542 binds nothing and the span is dropped without trace; no organism span, so 3666 protects nothing | Gene fallback tries "SRA", "SARS" (3678 all-capitals rule) and binds nothing; disease fallback reaches "SARS"; `_only_a_piece_of_a_joined_name` 3699 returns False because a space follows it; `resolve_disease_mention_to_curies("SARS")` binds 3 SARS records at 4544. Answer about the disease SARS (adversary_r3 A3-56-03, 1 run of 6 live) |
| No entity | Same as the disease row from the gene fallback on | Same wrong binding |

The variants:

| Typed | Tokens the fallback sees (3599, 3678) | Result with no organism span |
|---|---|---|
| SARS CoV-2 | SARS (whole word before a space) | SARS records bound |
| SARS CoV 2 | SARS; "CoV" fails the shape rule; "2" is one character | SARS records bound |
| sars-cov-2 | none: lower case fails the all-capitals rule | Nothing bound; topic search or ask |
| COVID-19 virus | COVID (piece of "COVID-19") | SRA or assembly question: skipped by #186. Any other record type: MedGen binds "COVID Reinfection" and "long COVID brain fog" (adversary_r3 A3-56-02) |

### A2. A SARS-CoV-2 SRA question after a BRCA1 question, model returns no organism

| Step | Line | What happens |
|---|---|---|
| Opening ask-back | 4266 | Skipped: memory is not None |
| Think model | 4341 | Sees the memory block "resolved BRCA1 to NCBIGene:672 (Gene)" in its user message (`_build_think_messages` 2766, suffix at 2795) |
| Confirm, fallbacks | 3442, 4449, 4513 | Nothing resolves; "SARS" skipped by #186 if hyphenated, bound as in A1 if spaced |
| Clarification | 4645, `_needs_clarification` 6643 | Returns False because memory holds an antecedent, so nothing is asked |
| Plan memory binding | `_select_planned_tool_call` 6799 to 6804 | Binds NCBIGene:672, `memory_bound=True` |
| Topic escape | 7076, 7106 to 7116 | Topic search is dropped because "each one" contains "one", a referring word (`_REFERRING_WORDS` 6516); without "each one", two or more content words keep the topic search |
| Result | 7311 | Gene fan-out on BRCA1, including PubMed by the remembered symbol |

Judge round 3 reproduced this offline (`2026-10-06_card56/judge_r3.md` J3-56-01). No test pins the SARS-CoV-2 plus memory case; `test_think_sra_disease_fallback.py:266` pins only "What SRA runs are there for it?" with BRCA1 remembered, which call 2 keeps.

### A3. "SRA runs from AML-derived cell lines"

| Model reply | Deciding line | Outcome |
|---|---|---|
| "AML" as disease (2 of 3 live) | 3542, `resolve_disease_mention_to_curies` 3308 | Binds 3 MedGen records including C0023467 "Acute myeloid leukemia" (MedGen `AML[title]` count 3, measured) |
| No entity (1 of 3 live) | Gene fallback 4449: "SRA", "AML"; `AML[sym] AND human[orgn]` is 0 (measured), so nothing. Disease fallback 4538 to 4542: "AML" stands only in "AML-derived", so #186 skips it | Nothing resolves; no referring word, so no question back; Plan takes the topic search `sra AND runs AND aml-derived AND cell AND lines` (`breadth_plan.py:644`), 0 PubMed hits (adversary_r3 A3-56-04) |

### A4. A SARS-CoV-2 Illumina SRA question where "Illumina" is tagged a gene

| Step | Line | What happens |
|---|---|---|
| Gene spans | 3502 | "Illumina" collected as a gene |
| Taxon | 3509, `_confirmed_taxon_for_extraction` 3115 | If "SARS-CoV-2" was tagged organism and Taxonomy confirmed it, the gene is looked up against taxon "SARS-CoV-2", otherwise human |
| Gene lookup | 3518, 3526 | Fails: `ILLUMINA[sym]` is 0 in human and in all organisms (measured); filed unresolved |
| Failed gene as disease | 3559 | `Illumina[title]` in MedGen is 0 (measured); stays unresolved |
| Gene fallback | 4449 | Tries "SRA" (the organism span is protected); nothing |
| Organism anchor | 4485 to 4486 | Blocked by `not model_resolution.unresolved_symbols` |
| Disease fallback | 4515 | Blocked by the same condition |
| Clarification | 6641 | False on any unresolved symbol |
| Unresolved key | 4726 | Set to ["Illumina"] |
| Plan | 6780 | `_UnresolvedEntityRefusal`; plan narrative "unresolved gene symbol candidate(s): Illumina" (7123) and Write refuses |

Rate: 7 of 20 live runs on 2026-10-06 (card 56 row in `testing/UI_fix_plan.md`). The Think instruction lists database, method and clinical acronyms that are not genes (`graph.py:2660` to `:2671`) but has no notion of a search condition.

## B. Call 1, the whole-phrase lookup

### B1. What Think's model returns today

| Field | Type | Line |
|---|---|---|
| `query_class` | one of lookup, single_hop, multi_hop, aggregate, exploratory | 2591 |
| `narrative` | text, at most 500 characters | 2592 |
| `entities` | at most 20 spans | 2593 |
| `entities[].text` | the span as written, at most 200 characters | 2578 |
| `entities[].entity_type` | gene, disease, organism, variant, other; the prompt asks for the first three only (2703 to 2711) | 2579 |
| `record_type` | sra, assembly, none; defaults to none | 2600 |

There is no position in the question, no confidence, no role and no "condition" type. Both models use `extra="forbid"` (2576, 2589), so a new field needs a schema change, a prompt change (the system instruction is fixed text, 2627 to 2632) and, for a top-level field, nothing more for the retry: `_THINK_RETRY_KEY_LIST` (2611) and the narrative repair (2836) read the schema's own field list.

### B2. Where the lookup would sit

| Place | Line | Why there |
|---|---|---|
| After span confirmation, before the gene fallback | between 4411 and 4449 | Every model span has been tried by its tagged type; what is left is exactly "a word the system cannot place" |
| Inputs it needs that do not exist today | `_EntityResolution` 6279 | Today the result carries confirmed CURIEs and failed gene symbols only. A disease span that bound nothing is dropped silently (3542 to 3550), and an organism span Taxonomy rejected is dropped silently (3133, 3161). The lookup needs a list of "spans that did not confirm as their type" |
| Primitives to reuse, all cached | `_organism_taxids` 3039, `resolve_symbol_to_curie` 5998, `resolve_disease_mention_to_curies` 3308 | One Taxonomy search; Datasets then ESearch for a gene; MedGen search plus summary |
| The ask with choices | `_ask_back` 3957 | Already emits a question with options; used by the opening ask-back and the recent-years ask |
| Gates it must respect | 4379 to 4396 | Window, accession and isolate questions skip model confirmation today because of the call ceiling |

The model-tagged "SARS CoV-2" disease span (A1, second row) is exactly the case: its tagged type failed, and the whole phrase answers one Taxonomy record. "Illumina" (A4) is the other: its tagged type failed, and the whole phrase answers nothing anywhere, so call 1 alone would ask the person "what is Illumina?". Only call 3 (Illumina is a condition) keeps that question from being asked.

### B3. Can the token fallback go, or only be guarded

Only guarded, unless P1 is solved first. The fallback (3605) exists for one reason: the model returns no span at all on some runs. Three places use it:

| Use | Line | Gate today |
|---|---|---|
| Gene fallback | 4449 to 4467 | Nothing resolved, no accession, no isolate; organism spans excluded (3666) |
| Organism span exclusion | 3662 to 3667 | Any span Taxonomy did not reject |
| Disease fallback | 4513 to 4560 | Nothing resolved, no unresolved gene; #186 skips hyphen pieces on SRA and assembly questions only |

A guard that matches call 1's "never cut a word" would treat a token as a candidate only when it stands alone in the question (not joined by a hyphen, and not followed or preceded by another word of the same name). That is a text rule, not a word list. It still cannot tell "SARS CoV-2" from "SARS patients"; only a whole-phrase lookup or the model can.

### B4. What tests pin the token fallback today

| Test | File:line | What it pins |
|---|---|---|
| Gene shapes only, cap of three | `tests/system_03_search_agent/core/test_layer_handoff.py:637` | "GCK", "MODY"; "brca1"; never lower-case or title-case words |
| GCK resolves with an empty extraction | `test_layer_handoff.py:656` | The GCK question answers when the model returns nothing |
| Fallback skipped when the model named a span | `test_layer_handoff.py:673` | Only "BRCA1" is looked up |
| Mutation: emptied extractor | `test_layer_handoff.py:700` | Goes red with no candidates |
| Flagship under empty extraction | `tests/system_03_search_agent/core/test_cq_routing_mutation.py:605` | Premise arm P2 depends on the fallback naming BRCA1 |
| Fallback after every model span failed | `tests/system_03_search_agent/core/test_think_disease_and_organism.py:259` | A transport miss on GCK recovers through the fallback |
| Organism span protects its tokens | `tests/system_03_search_agent/core/test_think_organisms.py:149`, `:162`, `:181` | "SARS" never a candidate inside a tagged organism |
| SRA and assembly, hyphen pieces skipped | `tests/system_03_search_agent/core/test_think_sra_disease_fallback.py:196`, `:213` | Asserts the generic gene question is asked back (`CLARIFICATION_QUESTION`), which call 1 and call 2 would change |
| Whole word still binds on SRA | `test_think_sra_disease_fallback.py:231` | "SRA runs from MODY patients" binds MODY |
| Paper question keeps develop's SARS binding | `test_think_sra_disease_fallback.py:247` | Pins today's wrong SARS binding on "papers on SARS-CoV-2"; call 1 would turn it red on purpose |
| Retired regex stays retired | `tests/system_03_search_agent/core/test_cq_routing_premise.py:670` | Structural: names `_SYMBOL_CANDIDATE_STOPWORDS` and `_GENE_SYMBOL_TOKEN_PATTERN` only, not today's `_GENE_SHAPED_TOKEN_PATTERN` |

Question shapes that rely on the fallback today, each with its test: a gene named in capitals with an empty extraction (GCK, `test_layer_handoff.py:656`); a gene in lower case with a digit ("what diseases are linked to brca1?", `:637`); the flagship BRCA1 question (`test_cq_routing_mutation.py:605`); a disease acronym with an empty extraction (MODY, `test_think_sra_disease_fallback.py:231`); a model gene span that failed on a transport miss (`test_think_disease_and_organism.py:259`).

## C. Call 2, remembered subjects

### C1. Every place memory supplies or protects a subject

All in `src/system_03_search_agent/core/graph.py`.

| Place | Line | What memory does there |
|---|---|---|
| Plan's antecedent binding | 6799 to 6804 | The one place memory changes the subject: when Think resolved nothing, binds the most recently mentioned CURIE (`_antecedent_curie` 6471) |
| Asking back is suppressed | `_needs_clarification` 6643 | Any remembered entity stops the "which gene, variant or condition" question |
| Opening ask-back is skipped | 4266 | A session with memory never reaches the 1-to-3-word ask-back |
| Think model sees memory | 4341, 2795 | The memory block rides in Think's user message; the model could copy a remembered name into its spans. Not measured |
| Memory versus topic search | 7106 to 7116 | A memory-bound plan drops the topic search when the question has a referring word or fewer than two content words |
| Remembered symbol in searches | 7311 | PubMed and trials searches use the remembered mention |
| Next-step label | 7485 to 7491 | Labels the follow-up offer with the remembered mention |
| Guardrail admission | 1982, 2285; `_relevancy_state` 6551 | Not a subject source: admits a follow-up whose previous question was biomedical |

Memory never feeds `organism_records` (P8), and never feeds the isolate or accession paths.

### C2. How a classifier could decide "the question names no subject of its own"

What exists:

- `_is_memory_bound_follow_up` (6521) is a word list (`_REFERRING_WORDS`, 6516), which misfires on "each one" in the card's own question.
- The classifier seam: decision specs such as `_RELEVANCY` (1017) and `_ASK_BACK` (1049), each with options, criteria and a fail-open value, called through `_decide_point`. `_relevancy_state` (6551) already hands a decision the previous question beside the new one.
- Think's own reply: entities and record type. On the misses, the reply says it asks for SRA runs and names no organism (`findings.md`, "In every miss the model still set record_type to sra").

Three ways, from the code:

| Option | Cost | Weakness |
|---|---|---|
| A top-level Think field, such as "names_subject", in the same reply | No extra call | The same sample that drops the organism can drop this, so the two failures are correlated |
| A per-span role from call 3: "no subject span" means no subject | No extra call | Same correlation: an empty reply has no spans and so "names no subject", which is today's failure |
| A new decision point asked only when memory exists and nothing resolved this turn, given the question and the previous question (the `_relevancy_state` shape) | One classifier call, only on that narrow path | Needs a fail-open choice. The owner's call points to "ask" when it fails, which changes today's "bind memory" default |

Only the third is independent of the Think sample that fails. It would replace the word list at 6643 and 7112, not the guardrail's use at 1982 and 2285 (a separate decision).

Tests that pin today's memory behaviour and would need to hold: `test_plan_memory_binding.py:118`, `:201`, `:263`, `:315`; `test_topic_search.py:808`, `:832`, `:853`, `:870`, `:1013`; `test_clarification.py:160`, `:191`, `:213`; `test_think_sra_disease_fallback.py:266` (three arms).

## D. Call 3, subjects and conditions

### D1. What Think returns for conditions today

Nothing. The schema has no condition (B1). A condition reaches the plan only by accident: tagged as a gene ("Illumina", A4, which refuses), tagged as a disease (binds whatever MedGen matches), or as words in the topic search (`build_topic_term`, `src/system_03_search_agent/core/breadth_plan.py:644`, every content word ANDed). The organism search already says conditions were not applied: `_organism_records_disclosure` (`graph.py:3245`) adds "by organism alone, so any other condition the question names is not applied to the search".

### D2. Which tools can apply which conditions

| Tool and path | Where the search is built | Conditions it can carry | Measured |
|---|---|---|---|
| SRA via `ncbi_efetch` search | `breadth_plan.py:1025`, term `txid<id>[Organism:exp]`; term free text up to 500 characters (`src/system_03_search_agent/tools/ncbi_efetch_schemas.py:251`, cut at `breadth_plan.py:713`) | Platform (`illumina[Platform]`), and any SRA field tag or free text in the term | 7,578,367 runs for the organism; 6,184,164 with Illumina; 1,255,829 with Illumina and "respiratory" in any field |
| Assembly via `ncbi_efetch` search | `breadth_plan.py:1025` | Assembly level (`"complete genome"[Assembly Level]`), other assembly field tags | 688 complete Mycobacterium tuberculosis genomes |
| Pathogen Detection isolate search | `src/system_03_search_agent/core/isolate_search.py:355`; input `pathogen_detection_schemas.py:258` to `:277` | Taxon folder and AMR gene prefixes only. Location and date come back per isolate (`pathogen_detection_schemas.py:327`, `:328`) but cannot be searched on, and filtering the returned sample after the fact would break `total_available` | Not measured |
| PubMed topic search | `breadth_plan.py:683` | Every content word as untagged text, plus a publication window | Not measured |
| Graph `cypher_query` | `graph.py:6806` | None: target entities and a row limit | Not applicable |

Free text such as "respiratory[All Fields]" matches any field and is not a curated sample type; an answer that applies it must say it was matched as text. A closed set the classifier picks from (SRA platforms, assembly levels) can be applied exactly. A condition the database cannot express (sample type on SRA beyond text, anything on isolates) goes to "not applied".

## E. Live NCBI measurements

Run 2026-10-17, no key, 0.4 s between requests, `retmax=5`, 60 requests in all. Search forms are the code's own:

- Taxonomy: `<phrase>[All Names]` after `_organism_taxids`'s cleaning (`graph.py:3039`).
- Gene, human: `<PHRASE>[sym] AND human[orgn]`, the ESearch leg of `resolve_symbol_to_curie` (`graph.py:5998`). The Datasets leg, tried first by the code, was not measured.
- Gene, all organisms: `<PHRASE>[sym]`.
- MedGen: the code's form, each word of two or more characters as `<word>[title]`, ANDed (`graph.py:3308`). "SARS CoV-2", "SARS-CoV-2" and "sars cov 2" all become `SARS[title] AND CoV[title]`, so one request served all three.

### E1. Counts per phrase

| Phrase | Taxonomy | Gene, human | Gene, all organisms | MedGen (code form) | Taxonomy, Gene human, MedGen: exactly one? |
|---|---|---|---|---|---|
| SARS CoV-2 | 1 (2697049) | 0 | 0 | 0 | Yes, Taxonomy 2697049 |
| SARS-CoV-2 | 1 (2697049) | 0 | 0 | 0 | Yes, Taxonomy 2697049 |
| sars cov 2 | 1 (2697049) | 0 | 0 | 0 | Yes, Taxonomy 2697049 |
| COVID-19 virus | 1 (2697049) | 0 | 0 | 0 (`COVID[title] AND 19[title] AND virus[title]`) | Yes, Taxonomy 2697049 |
| SARS | 1 (694009) | 3 (6301, 54938, 59279) | 284 | 3 (927688, 927681, 276768) | No, several |
| Illumina | 0 | 0 | 0 | 0 | No, none |
| AML | 0 | 0 | 5 | 3 (1759111, 348707, 9730) | No, several (all MedGen) |
| acute myeloid leukemia | 0 | 0 | 0 | 237 | No, several |
| Mycobacterium tuberculosis | 1 (1773) | 0 | 0 | 61 | No, several |
| Salmonella enterica | 1 (28901) | 0 | 0 | 5 | No, several |
| TP53 | 0 | 1 (7157) | 684 | 92 | No, several |
| BRCA1 | 0 | 1 (672) | 678 | 16 | No, several |
| CF | 0 | 1 (1080, CFTR) | 6 | 0 | Yes, but the gene CFTR |
| HIV | 5 | 0 | 1 (44821) | 36 | No, several |

Tally, Taxonomy plus human Gene plus MedGen: exactly one 5 of 14 (the four SARS-CoV-2 forms and CF), several 8, none 1 (Illumina). With Gene across all organisms instead of human: exactly one 4, several 9, none 1.

Two whole-phrase MedGen searches in `[All Fields]`, to see where a whole phrase lands outside the title index: `SARS-CoV-2[All Fields]` 151 records, 123 ms; `SARS CoV-2[All Fields]` 151 records, 157 ms. NCBI translated both to `"Severe acute respiratory syndrome coronavirus 2"[All Fields] OR ...`, so the whole phrase lands on SARS-CoV-2 records there, never on SARS, but it is "several".

### E2. Response times

| Database | Requests | Median | Worst |
|---|---|---|---|
| Taxonomy | 14 | 160 ms | 191 ms |
| Gene, human | 14 | 157 ms | 484 ms |
| Gene, all organisms | 14 | 155 ms | 260 ms |
| MedGen, code form | 12 | 161 ms | 219 ms |
| MedGen, all fields | 2 | 140 ms | 157 ms |
| SRA | 3 | 176 ms | 5,883 ms (the first, organism only) |
| Assembly | 1 | 190 ms | 190 ms |

Three databases searched side by side would add about 0.2 s at the median and 0.5 s at the worst measured, before MedGen's summary call and Gene's Datasets leg, which were not timed. Without a key the limit is 3 requests a second, so sequential lookups of three phrases across three databases would take at least 3 s.

### E3. The condition searches

| Request | Count | Time |
|---|---|---|
| sra `txid2697049[Organism:exp]` | 7,578,367 | 5,883 ms |
| sra `txid2697049[Organism:exp] AND illumina[Platform]` | 6,184,164 | 165 ms |
| sra `txid2697049[Organism:exp] AND illumina[Platform] AND respiratory[All Fields]` | 1,255,829 | 176 ms |
| assembly `txid1773[Organism:exp] AND "complete genome"[Assembly Level]` | 688 | 190 ms |

## F. Risks to questions that work today

From `testing/Test_queries_and_workflows.md`:

| Query | Today | How the design could make it worse | Guard |
|---|---|---|---|
| 21, "Which diseases are associated with GCK?", and the GCK fallback | Answers even when the model returns no span (`test_layer_handoff.py:656`) | Deleting the token fallback leaves an empty extraction with nothing to look up; the person is asked back or gets a topic search | Keep the fallback guarded (B3), or a content retry before it |
| 78, "What genes are associated with MODY?" | MODY binds 8 MedGen records by containment, including through the fallback | Under a count-based "exactly one", MODY in MedGen is several, so the question is asked back instead of answered | Call 1 only for spans that did not confirm as their tagged type; never re-check a disease MedGen already bound |
| 1 and 20, BRCA1 then "What variants cause it?" | Memory binds BRCA1 (`test_plan_memory_binding.py:263`) | A classifier that misreads the follow-up as naming its own subject asks back; a call 1 run on a confirmed gene finds BRCA1 in Gene and in 16 MedGen titles and asks "which BRCA1?" | Run the call 2 classifier only when Think resolved nothing; never send a confirmed span to the three-way lookup |
| 111 controls after query 1, such as "and what about it in children?" | Answered about BRCA1 | "children" could be read as a subject by call 3 and replace the remembered gene; or call 2's classifier fails and asks | Call 2's fail-open choice decides this; measure it on these controls |
| 76, "and BRCA2?" after query 1 | Answered about BRCA2 | Unchanged if BRCA2 is tagged; on an empty extraction with the fallback removed, memory would bind BRCA1, the case call 2 forbids | Call 2 classifier must say "names a subject", then ask, which is safe |
| 24, "Compare what is known about MLH1 and MSH2 in colorectal cancer risk." | Both genes and the disease bind | Call 3 could mark "colorectal cancer" a condition; the graph query has no condition input, so it would be "not applied" where it is applied as a subject today | The model prompt must say a disease asked about is a subject; test this question |
| 34, "Which Salmonella isolates in Pathogen Detection carry ESBL genes?" | Fixed table, Salmonella genus 590 (`isolate_search.py:106`), no model span confirmed (`graph.py:4379` to `:4396`) | If call 1 or an organism lookup ran on isolate questions, Taxonomy gives 28901 for "Salmonella enterica" (measured), which has no Pathogen Detection folder mapping | Keep call 1 off the isolate path, as model confirmation is today |
| 70, "any trials for gerd?" | Model tags "gerd" a disease; MedGen binds | Under a count-based "exactly one", several GERD records means an ask | Same as query 78 |
| 103, the card's own two questions | M. tuberculosis assemblies answer; SARS-CoV-2 SRA answers on most runs | With call 3, "Illumina" applied as a platform narrows 7.6 million to 6.2 million runs; "clinical respiratory samples" as free text must be disclosed as a text match, or the answer claims a filter it did not apply | The disclosure at `graph.py:3245` must change from "not applied" to what was applied, per condition |

## What was not covered

- No model was called, so how often the model would mark a phrase as a subject or a condition, or return no spans with a role field added, is not known.
- The Datasets leg of the gene lookup was not measured; for "SARS" in human the ESearch leg answers 3 ids, and earlier live runs show no gene bound, but Datasets alone was not asked.
- MedGen's exact-title rule (`graph.py:3425` onward) needs a summary call per search; not measured, so how many phrases MedGen would "fit" under that rule is unknown.
- Whether the Think model copies a remembered subject out of the memory block into its spans (C1, "Think model sees memory") was not measured.
- Pathogen Detection and the PubMed topic search were not called.
