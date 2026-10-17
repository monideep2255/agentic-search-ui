# Card 30 diagnosis: BRCA1's "pathogenic" variants are unclassified ones

Re-diagnosed against develop `78c68c1c`, 2026-10-16, after phase 8.7 merged (#218, #229). Code reading, a local probe that imports the product's own functions (no network, no model), and four free read-only E-utilities calls with `tool=` set and no key. No question was sent to the develop or production API. It replaces the line numbers of `testing/Developer/reports/2026-10-08_overnight/card30_diagnosis.md`, which are stale.

The owner's standing decision D15 (`testing/Board_plan.md:223`): "Card 30 keeps its list, says plainly that classification was not retrieved, and its trust verdict is "ask"".

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Tests](#tests)
- [Overlap with tonight's other cards](#overlap-with-tonights-other-cards)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

Still happens. Nothing on develop tells the person that the listed variants carry no classification.

| Check | Result on `78c68c1c` |
|---|---|
| Any code for card 30 or D15 | None. The probe's search of `core/graph.py` for "not retrieved", "card 30" and "asks_classification" finds nothing |
| The card 23 note on a plain variant list | `variant_to_disease_source_note("SequenceVariant", False)` returns None (probe), so a BRCA1 variant list gets no line |
| What phase 8.7 changed | The listing now leaves Write before the writer call (card 50), the count line can follow a lead sentence (card 2), and card 2 added an "honest gap" clause to the opening line. None of these touches classification |
| Card 2's honest gap, could it fire here | No. It fires only for a decision already made (`think.asks_features` is the only one, `src/system_03_search_agent/core/graph.py:12797`) and only on positive evidence that a source was read and lists none (`records_lack_field`, `src/system_03_search_agent/synthesis/answer_layout.py:1499`). Card 30 is the opposite case: the field was never read |
| The verdict | Unchanged since 2026-10-08. With no grounded model sentence the structured fallback floors it at `ask` (`core/graph.py:14797`); otherwise it can be `answer`, as the saved run of 2026-10-05 was: "Based on 58 sources" (`testing/Developer/reports/2026-10-05_board_plan/scripts_w1/out/brca1_path.json`) |

## What a person sees

A researcher types "Which BRCA1 variants are pathogenic?" and reads "Found 40 sequence variant records for BRCA1, of 15350 available", then 40 variant names such as c.4709T>C (p.Leu1570Pro), each linked to ClinVar, then five live ClinVar titles and five trials. Nothing says these are not the pathogenic ones. The writing model said twice that "the pathogenicity status of these variants cannot be determined from the retrieved data alone", and the citation gate removed it (`tracker/phase_8.1.md:810`, F-8.1-A16).

Measured tonight, one ClinVar ESummary call for those exact 40 variants (ids from the saved run):

| ClinVar's classification | Variants of the 40 |
|---|---|
| Conflicting classifications of pathogenicity | 23 |
| Uncertain significance | 15 |
| Pathogenic | 2 |

So 38 of the 40 variants listed under "which are pathogenic" are not classified pathogenic by ClinVar. A confident wrong answer about cancer risk.

## The cause

| Link | Evidence |
|---|---|
| 1. The graph's variant search returns vertices with no classification. The gene's variants template is `("Gene", "variants")`, edge `is_sequence_variant_of` | `src/system_03_search_agent/tools/cypher_templates.py:262`, built by `_hop_template` (`:581`). The vertex keys are `agent_type, id, knowledge_level, name, source, source_url, xrefs` (card 23's read-only probe, `testing/Developer/reports/2026-10-06_card23/fix_round.md`). The graph row's finding is its `name` (probe: `_pick_representative_field` picks `name`) |
| 2. The live ClinVar records do carry the classification, and it is fetched and then not shown. Plan searches `BRCA1[gene]`, cap 10; ESummary keeps `germline_classification`; the row keeps it too; the finding is the `title` alone | Search: `src/system_03_search_agent/core/breadth_plan.py:756`, cap `:122`. ESummary allowlist: `src/system_03_search_agent/tools/ncbi_eutils_actions.py:871`. Row fields: `_BREADTH_FIELDS_BY_PURPOSE["clinvar_summary"]`, `core/graph.py:7650`; probe: row fields `accession, genes, germline_classification, title`, picked field `title`. Five rows reach the answer (`_LAYER_TOOL_ROW_CAP`, `core/graph.py:4851`). One field per row: `build_synth_findings`, `src/system_03_search_agent/synthesis/findings.py:497`; the only second field allowed is a gene's `summary` (`_EXPLANATORY_FIELDS`, `findings.py:128`) |
| 3. The writer's honest caveat cannot pass the citation gate: a sentence about an absence quotes no record value | F-8.1-A16. The gate is correct and stays as strict (`tracker/phase_8.9.md`, Constraints) |
| 4. Nothing code-built fills the gap. Card 23's line says the classification is not shown, but only under the variant-to-disease table, at Researcher depth | `VARIANT_TO_DISEASE_SOURCE_NOTE` and `variant_to_disease_source_note`, `synthesis/answer_layout.py:352` and `:359`; emitted only inside `grouped_listing`, `core/graph.py:13573` to `:13576` |
| 5. Nothing floors the verdict for this question. The floors that exist are the structured fallback, an unaddressed entity, omitted records and a failed search | `core/graph.py:14797`, `:14836`, `:14888`, `:14907` |

## The smallest fix

Two steps. Step 1 is what D15 decided. Step 2 is the real answer and is the owner's cost choice.

### Step 1: the plain line and the "ask" verdict

| Item | Value |
|---|---|
| What changes, in the person's words | Under a list of a gene's variants from the knowledge graph, one line reads: "ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, so this list does not say which are pathogenic. Each variant's ClinVar record shows its classification." When the question asks which variants are pathogenic, benign or clinically significant, the answer's verdict is "ask", never "answer". The list itself is unchanged |
| Note, when it shows | Code verifies only, keyed on record type and field (the phase 8.9 precedent): at least one shown finding is a graph `SequenceVariant` record (`layer_1_graph`), and no shown finding cites a classification field (`clinical_significance` or `germline_classification`). Skipped when card 23's line is already on the page (Researcher, variant-to-disease table), so the fact is never said twice |
| Floor, when it applies | Only when a new classifier decision, `think.asks_classification`, picks `asks_classification` AND the note's condition holds. Applied as `trust_outcome = aggregate([trust_outcome, "ask"])`, the mechanism the four existing floors use; `claim_trusts` are left as `decide()` computed them |
| Why the floor needs a classifier | Whether a question asks about classification is a reading of its words ("pathogenic", "clinically significant", "harmful", "disease causing", "benign", in any wording). The owner's rule is that a decision goes to a classifier and code only verifies, never a word list. Code alone can verify the record shape, but flooring on shape alone would turn every variant listing (for example "What variants are in GCK?" or query 79's HNF1A table) from "answer" to "ask" when nothing about them asked for a classification |
| Why the note does not need it | It is true on every listing it fires on, it costs one line, and it still protects the reader when the classifier misses a wording |
| File fence | `src/system_03_search_agent/synthesis/answer_layout.py`: one constant `VARIANT_CLASSIFICATION_NOTE` and one selector `variant_classification_note(findings)` beside `variant_to_disease_source_note`. `src/system_03_search_agent/core/graph.py`: one `_DecisionSpec` `_ASKS_CLASSIFICATION` beside `_ASKS_FEATURES` (`:1184`); one field `classification_task` on `_RunDecisions` (`:1249`); started and cancelled in `think_node` beside `features_task` (`:4132` to `:4148`); dropped in `write_node`'s `finally` beside `_drop_features_decision` (`:13698`); read once in `_write_answer` with `_read_late_decision`, as `_clinical_features_asked` is (`:1506`, `:14007`); the floor beside the partial answer floor (`:14830`); the note passed to `_answer_parts` and emitted first in its notes part unless the card 23 note was emitted (`_answer_parts`, `:13001`; notes part `:13676`). Tests in `tests/system_03_search_agent/core/` and `tests/system_03_search_agent/synthesis/` |
| Answer path | Yes |
| Dial | 2, runnable behaviour. No change to `contracts/events.py`: the note is an ordinary `note` token and the decision rides in the existing `DonePayload.decisions` list (eight decisions against its bound of 16, `_MAX_DONE_DECISIONS`, `core/graph.py:1212`) |
| Size | M: about 60 lines of product code plus tests |
| Migration, package, event schema, setting | None |
| Cost and speed | One more classifier call per non small talk question, started at Think so nobody waits on it; Jev's measured price is about $0.0001 per call (`docs/build/Debugging_guide.md`, `harness/jev_client.py`). Read in Write with the existing 1 second late grace (`_LATE_DECISION_GRACE_S`, `core/graph.py:1222`), so the worst case adds 1 second, normally 0 |
| Frontend | No change. A trailing `note` token lands in the answer's Notes list (`frontend/src/hooks/useRunView.ts:800` to `:808`, `:925`) in both depths |

Ways step 1 could make an answer develop gives today worse, and the test that catches each:

| Risk | Catch |
|---|---|
| The note contradicts a classification the answer does show (query 23: the dbSNP row's finding is `clinical_significance`, golden G-024) | A selector test with an rs334 shaped answer (a `Variant record` finding citing `clinical_significance`, no graph variant) returns None; a Write test asserts no note and no floor |
| Card 23's line and this line both say the classification is not shown under the HNF1A table | A Write test at Researcher with a mapped variant table asserts exactly one of the two lines (card 23's) |
| The floor fires on a question that did not ask about classification | Write tests: decision `not_applicable`, no decision, a failed decision and a decision still running past the grace all leave the verdict as computed |
| The floor is set by marking a claim `insufficient`, which card 8's new wording would read as "their values could not be compared" | A Write test asserts every `claim_trusts` outcome is unchanged and only the answer-level outcome moves |
| The new decision keeps spending after a refusal or an early exit | Mirror `test_a_write_that_ends_early_stops_the_features_decision` (`tests/system_03_search_agent/core/test_graph.py:2252`) and the Think finally path |
| The decision's description leaks a test question | Review check: the description is code-authored instructions and criteria only, as `_ASKS_FEATURES` is; no golden or test question appears |
| The note pushes the done event or a token past a bound | The note is under 200 characters, far inside a token's 1,000 |

Not a fix here: loading the classification into the graph. That is System 1's pipeline in the other repository (`.claude/rules/file-protection.md`).

### Step 2: show each variant's ClinVar classification (the owner's cost choice)

Three shapes, smallest first. Each is dial 2, answer path yes, no migration and no event schema change.

| Shape | What the person sees | Extra calls | Extra seconds | Fence | Size |
|---|---|---|---|---|---|
| 2a. Show what is already fetched | The five live ClinVar records each show ClinVar's classification ("Pathogenic", "Uncertain significance"); the 40 graph variants still show none | 0 | 0 | `synthesis/findings.py` (a second finding from `germline_classification.description`, the way `_EXPLANATORY_FIELDS` emits a gene's summary, or a column in `answer_layout.TABLE_COLUMNS` keyed on the `clinvar` row type); `core/graph.py` `_ncbi_efetch_output_to_structured_fields` to flatten the nested value | S to M |
| 2b. Look up the classification of every graph variant shown | Every listed variant shows its classification, for example 2 Pathogenic, 15 Uncertain significance and 23 Conflicting for tonight's 40. The note from step 1 then no longer fires | 1 ClinVar ESummary per 50 variants shown (`NcbiEfetchInput.ids` holds at most 50, `src/system_03_search_agent/tools/ncbi_efetch_schemas.py:271`), so 1 for this question | Measured 0.31 s for the 40 ids from this machine, 117 KB before the product's field allowlist; through the product's E-utilities pool, estimate 0.5 to 1.5 s, in Write like the MedGen name lookup | A new Write time resolver beside `synthesis/disease_names.py`, keyed on `ClinVar:` CURIEs; `core/graph.py` `write_node`; `synthesis/answer_layout.py` a column | M |
| 2c. Answer the question asked: list ClinVar's pathogenic variants | The answer leads with ClinVar's pathogenic and likely pathogenic BRCA1 variants (4,731 of ClinVar's 16,104 BRCA1 records, ESearch tonight), each with its classification; the graph list follows | 0 if the existing ClinVar search is replaced by the filtered one when the decision says so; 2 (ESearch plus ESummary) if added beside it | 0.12 to 0.16 s per ESearch from this machine; estimate under 1 s each through the pool | `core/breadth_plan.py` (the term `BRCA1[gene] AND ("clinsig pathogenic"[Properties] OR "clinsig likely pathogenic"[Properties])`, verified live tonight), Plan wiring in `core/graph.py`, reading the step 1 decision at Plan, plus 2a to show it | L |

Every shape stays inside the 20 call ceiling, charged at the transport. 2a alone leaves a mixed list (5 classified beside 40 not), which needs the step 1 line to stay.

## Tests

Each fails on develop's code and passes on step 1.

| Test | File |
|---|---|
| `test_card30_a_graph_variant_list_says_classification_was_not_retrieved`: findings with graph `SequenceVariant` names and live ClinVar titles; the selector returns the pinned line | `tests/system_03_search_agent/synthesis/test_answer_layout.py` |
| `test_card30_no_line_when_a_shown_record_gives_a_classification`: an rs334 shaped answer (dbSNP `clinical_significance`, LitVar2 names) returns None | `tests/system_03_search_agent/synthesis/test_answer_layout.py` |
| `test_card30_the_line_shows_in_both_depths_and_once_beside_the_variant_table`: `_answer_tokens` for a BRCA1 shaped list at `plain_language` and `researcher` carries the line once in the notes part; a mapped HNF1A shaped table at Researcher carries only card 23's line | `tests/system_03_search_agent/core/test_write_answer_structure.py`, beside `test_card23_the_source_note_sits_directly_under_the_variant_table` (`:1095`) |
| `test_card30_a_classification_question_over_unclassified_variants_is_ask`: hand Write the decision `asks_classification` (the `_hand_write_the_features_decision` pattern, `tests/system_03_search_agent/core/test_graph.py:1952` onward) and a BRCA1 shaped graph result that would otherwise be `answer`; the done event's `trust_outcome` is `ask` and each claim's trust signal is unchanged | `tests/system_03_search_agent/core/test_graph.py` |
| `test_card30_no_floor_without_the_decision`: `not_applicable`, none, failed and late each leave `answer` | `tests/system_03_search_agent/core/test_graph.py` |
| `test_card30_a_write_that_ends_early_stops_the_classification_decision` | `tests/system_03_search_agent/core/test_graph.py` |

## Overlap with tonight's other cards

| Card | Their likely fence | Overlap with step 1 | Overlap with step 2 |
|---|---|---|---|
| 105, a picked date window also limits graph papers | `core/breadth_plan.py`, `tools/cypher_templates.py`, Plan wiring in `core/graph.py` | None in code: step 1 touches neither file nor Plan | 2c edits `breadth_plan.py`'s gene search builder (`:756`), the same function that applies the PubMed window; build after 105 or in one branch |
| 37 and 38, records carry the field asked for | `tools/cypher_templates.py`, `tools/cypher_query.py`, `synthesis/answer_layout.py` labels, `synthesis/findings.py`, `core/graph.py` `_layer_tool_output_to_structured_fields` and `write_node` | Same two files, different functions: step 1 adds a constant and selector to `answer_layout.py` and one line to `write_node`'s `finally`. A text merge, not a logic one. If 38 adds a `gene` field to variant rows, the selector still keys on record type and the classification fields only, so it is unaffected | Direct: 2a and 2b add a second field or column to variant rows, which is 37 and 38's companion rule (a closed table keyed on record type and field). Build 2a or 2b inside or after that work |
| 18, the `_answer_tokens` merge | `core/graph.py`, `merge_into` inside `_answer_parts` | Same function, different lines: step 1 adds one keyword to `_answer_parts` and emits the note in the notes part, after the listing; `merge_into` is untouched | None |
| 8, the trust line wording | `synthesis/trust.py` `answer_trust_line` | None in code. In what a person sees: today an `ask` reads "Based on N sources cited, not yet confirmed"; after card 8 a floor `ask` reads "Based on N sources cited, all from ClinVar", with no caution, so the line from step 1 becomes the only visible caveat. Step 1 must floor through `trust_outcome`, never a claim's outcome, or card 8 adds the false clause "their values could not be compared" (card 8's diagnosis says the same) | None |

## Needs the owner

| Choice | Options and cost | Recommendation |
|---|---|---|
| Step 2, fetching and showing classifications | 2b first: one call and about a second per answer with graph variants, and every listed variant shows its classification. 2a: free, but only five records gain one and the list is mixed. 2c: 0 to 2 calls and about a second, the answer becomes ClinVar's pathogenic list, size L. Or none: step 1's line stays the answer | 2b. It turns tonight's 40 rows into "2 Pathogenic, 15 Uncertain, 23 Conflicting" for one call, which is what a researcher came for. 2c after it, once 105 has merged |
| Where the line sits | In the Notes list after the answer: no frontend change. Directly under the variant list, as card 23's line sits under its table: a frontend prefix match in `useRunView.ts`, size M | The Notes list now, in step 1. Move it under the list only if the retest finds it is missed |
| Query 22 changes with this | "Which clinically significant variants have been reported in CFTR?" is the same shape: 54 unclassified graph variants (golden G-023). With step 1 it gains the line and, when the classifier reads "clinically significant" as a classification question, the "ask" verdict. Its sources do not change. Its entry says it "keeps answering the same way" | Yes: query 22 gets the line and "ask", for the reason D15 gives card 30. Update its expected text when step 1 lands |

Not the owner's: which questions get the line (every listing of unclassified graph variants, because it is true there and protects against a missed wording) and the classifier for the floor (the owner's standing rule already decides it).

## Test query

Query 23 (rs334) does not change: its answer cites dbSNP's `clinical_significance` and lists no graph variant, so neither the line nor the floor applies. Query 79 does not change at Researcher (card 23's line stays the only one under the table); in Plain language it gains this line where today it shows none. Query 22 changes as above.

No query covers card 30. Proposed new entry, section 3. The number is provisional; the lead assigns the next free number (114 is the highest today).

```markdown
### 115. Variants are never shown as pathogenic unless ClinVar says so (card 30)

Queries to try:

- `Which BRCA1 variants are pathogenic?`: ask it once in Plain language and once in Researcher.
- `What is rs334 and what condition is it associated with?`, in either mode, as the control.

What you should see:

- The BRCA1 answer still lists BRCA1's variant records, each linked to its ClinVar record.
- Below the answer, one line reads "ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, so this list does not say which are pathogenic. Each variant's ClinVar record shows its classification."
- The BRCA1 answer is never marked as a confirmed answer, and no sentence calls the listed variants pathogenic.
- Both modes carry the same line, once.
- The rs334 answer shows dbSNP's clinical significance and carries no such line.
- Why it matters: of the first 40 BRCA1 variants this question listed on 2026-10-05, ClinVar classifies 2 as pathogenic; a person asking which variants are pathogenic reads any list under that question as the answer, and an unmarked list of unclassified variants is a confident wrong answer about cancer risk.
```

When step 2b is built, the expectation becomes: each listed variant shows its ClinVar classification, and the line no longer appears.
