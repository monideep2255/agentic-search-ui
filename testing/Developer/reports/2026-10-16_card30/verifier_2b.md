# Card 30 step 2b fresh verifier

Pull request #269, branch `fix/card30-variant-classifications-shown`, head `66a56dfe`, against develop `cf9be15d`. Worktree `<worktrees>/card30b-ver`, detached. Probes in `<scratchpad>/card30b_ver/`. One fresh verification after the one fix round.

## Table of contents

- [Findings](#findings)
- [Prior findings](#prior-findings)
- [Mutations](#mutations)
- [Earlier classes on the merged tree](#earlier-classes-on-the-merged-tree)
- [Commands](#commands)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

(Filed as established.)

### V-30b-01, minor: the new ceiling test leaves the MedGen name cache filled, and three develop tests fail after it

- Where: `tests/system_03_search_agent/core/test_write_answer_structure.py`, `test_card30b_at_18_calls_used_the_name_lookup_still_gets_its_call` (`:2349` onward). It resets `disease_names` before each of its two runs (`disease_names.reset_cache_for_tests()`) but not after, so "MedGen:C0346153" stays resolved to "A disease" for every later test in the process.
- Evidence, branch `66a56dfe`:

```
pytest -q test_write_answer_structure.py::test_card30b_at_18_calls_used_the_name_lookup_still_gets_its_call \
  test_graph.py::test_a_vocabulary_token_name_downgrades_confidence_instead_of_asserting_it \
  test_graph.py::test_flagship_disease_row_hedges_its_citation_and_flags_its_payload_fields \
  test_graph.py::test_plan_selects_only_cypher_query_for_a_disease_anchored_query
3 failed, 1 passed
E       AssertionError: a citation built from a vocabulary-token value must be downgraded, never asserted
```

  The same with `test_card30b_the_lookup_is_stopped_when_write_ends_early` in its place: `4 passed`. `test_graph.py` alone: `254 passed`. Develop `cf9be15d`, `test_write_answer_structure.py test_graph.py test_answer_layout.py`: `432 passed`; the branch, same three files: `3 failed, 449 passed`.
- Reach: test order only. CI's gate04 (`pytest -m "not integration" -q -rs`) collects `core/test_graph.py` before `core/test_write_answer_structure.py`, so the three named tests run first there; see "Commands" for whether a later file is hit. No person sees it.
- Worse than develop: no, for a person. It is an instrument defect: a reset after the test (a fixture or `try/finally`) closes it.

### V-30b-02, minor: two fix round properties have no test that reads them (the text clip and the fold's reserve)

- The clip. `core/graph.py`, `sentence_token`: `text = text[: 1000 - len(suffix)] + suffix`. Mutation M1b (`text = text[:1000] + suffix`, which can exceed the cap) stays GREEN, `485 passed`. The test named for it, `test_card30b_the_text_suffix_stays_inside_the_token_cap`, never brings a row near the cap: its 992 to 1992 character name is not in the row sentence at all. `<scratchpad>/card30b_ver/test_zz_ver_cap_probe.py`, pasted:

```
CAP 990 [74] ['t record ClinVar:1 [1]. ClinVar classification: Pathogenic. ']
CAP 1400 [74] ['t record ClinVar:1 [1]. ClinVar classification: Pathogenic. ']
CAP 1990 [74] ['t record ClinVar:1 [1]. ClinVar classification: Pathogenic. ']
```

  The clip itself is right by reading, and no live row came near it (longest row text in the four live runs below is under 200 characters), so nothing reaches a person. The test name claims a property it does not check.
- The fold's reserve. `reserve_calls=(4 if curie_fallback_curies else 0) + (2 if folds_conditions else 0)`: dropping the `+ 2` (M4b) stays GREEN, `485 passed`. The only Write level ceiling test has a fallback disease and no fold. It matters only on a mixed answer (some variant or gene rows folded, other graph variants not) at 18 calls.
- Worse than develop: no. Instrument gaps.

### V-30b-03, minor: step 1's line still goes beside a dbSNP or LitVar2 variant row that shows no classification

- Where: `synthesis/answer_layout.py:422` to `:425`: the fix keeps the line for a live row only when `f.entity_type.lower().startswith("clinvar")`. A dbSNP row is `Variant record` and a LitVar2 row is `Literature variant` (`core/graph.py:5162`), so neither counts. The owner's words were "every shown variant row, the live ClinVar records included"; the fix names one source rather than the class (Review_rounds rule 2).
- Evidence: `<scratchpad>/card30b_ver/line_probe.py`, the selector with one graph variant classified, on both trees:

```
develop cf9be15d                                   branch 66a56dfe
graph only: line=shown                             graph only: line=absent
graph + live clinvar summary row: line=shown       graph + live clinvar summary row: line=shown
graph + LitVar2 Literature variant, no significance: line=shown    ... line=absent
graph + dbSNP Variant record, no significance: line=shown          ... line=absent
```

- Reach: narrow. dbSNP and LitVar2 run only when the question names an rs id (`_layer_tool_calls`, `core/graph.py`, "one each per rs id written in the question"), and a row that does carry `clinical_significance` already removes the line on develop too (`_CLASSIFICATION_FIELDS`). So it needs a gene variant listing plus an rs id that has no clinical significance in dbSNP and LitVar2, for example "Which BRCA1 variants are pathogenic, and what about rs<n>?" with a non clinical rs id. That person sees the graph rows classified, the rs row with none, and no line.
- Worse than develop: yes, in that narrow shape (develop shows the line). Fixable in the fence by keying the live rows on "any non graph variant row without a classification field" rather than on the ClinVar prefix.

### V-30b-04, major: on MCP and GraphQL the added row text pushes variant answers past the 8000 character answer cap, and query 22 loses its trial records and step 1's line

- Where: the fix round's suffix (`classification_text_suffix`, `synthesis/answer_layout.py:435`; appended in `sentence_token`, `core/graph.py`) adds about 45 to 60 characters to every classified row's text. MCP and GraphQL both cut the joined text at 8000 characters: `_MAX_ANSWER_LENGTH = 8000` and `_truncate_on_word_boundary` (`adapters/mcp/server.py:202`, `:1033`, `:1295` onward); `MAX_ANSWER_LENGTH = 8000` (`adapters/graphql/types.py:173`, applied in `adapters/graphql/fold.py:1112`). The command line has no cap, and the web page and saved answer read `cells`, so those are unaffected.
- Evidence: the four live runs below, the token text joined as MCP does, cut by MCP's own `_truncate_on_word_boundary` (`<scratchpad>/card30b_ver/trunc_probe.py`). "Develop equivalent" is the same tokens with only the suffix removed, which is what develop emits for those rows (the A/B probe below shows the suffix is the only token difference when every row is classified, apart from step 1's line):

| Run | Develop equivalent | Branch | What MCP and GraphQL lose on the branch |
|---|---|---|---|
| BRCA1, Researcher | 5735, whole | 8137, cut at 7995 | the end of the "only N of M records" note and the "no written summary could be checked" note |
| BRCA1, Plain language | 5627, whole | 8029, cut at 7991 | the end of "This is a research summary, not medical advice." |
| Query 22, Researcher | 6468, whole | 9021, cut at 7994 | the five "Clinical trial records found" rows, step 1's line, and both closing notes |
| Query 79, Researcher | 6369, whole | 6369, whole | nothing (no variant looked up) |

  Query 22's lost tail, pasted: `Clinical trial records found ... Clinical trial name: NPDT Evaluation in Children With CFTR and (PSC) [60]. Clinical trial name: Study of VX-809 in Cystic Fibrosis Subjects With the ∆F508-CFTR Gene Mutation [63]. ... ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, so this list does not say which are pathogenic. ...`
- What the person sees: an MCP agent or GraphQL client asking query 22 gets 54 classified graph rows, then the five live ClinVar rows with no classification, then "The answer above was truncated to this surface's 8000-character limit". On develop it gets the whole answer, the trials and step 1's line included. So the step 1 line that item 3 of the fix round exists to keep is cut on exactly the surfaces item 1 was written for. These runs had no written summary (the writer's prose was not shown in any of them, as in the adversary's and step 1 verifier's runs of the same questions), so an answer with prose crosses the cap sooner.
- Worse than develop: yes, a lost record and a lost sentence develop shows, on two surfaces, on a gate query (22) and on the card's own question. The owner's decision does not name this loss.
- Fixable inside the fence in one round: plausibly (a shorter text form of the classification, for example the value alone after the marker, or the text form only where the joined answer stays under the surfaces' cap), but every form adds characters per row, so the lead should check the arithmetic: 54 rows at even 20 characters each still brings query 22 to about 7550.

## Prior findings

Each re-derived on head `66a56dfe` against develop `cf9be15d`.

| Finding | Closed? | Evidence |
|---|---|---|
| J-30b-01, text surfaces lose the line and show no value | Closed as stated, but see V-30b-04. Every classified row's text now ends "ClinVar classification: X. " after its own marker; command line row, live: `SequenceVariant ClinVar:1000183, name: NM_007294.4(BRCA1):c.4709T>C (p.Leu1570Pro) [1]. ClinVar classification: Uncertain significance. ` | M1, M1c, M1e red; `rows_check.py` text value equals cell value on 134 of 134 live rows, no row with the words twice |
| J-30b-02 and A-30-01, card 23's line under a classification column | Closed. Mapped variants are not looked up: live query 79 header `['Variant', 'Identifier', 'Associated disease(s)']`, card 23's line once, lookup never started (`lookup` has no `start`) | M2 red |
| A-30-02, the line goes beside live ClinVar rows | Closed for live ClinVar rows: the line shows in all three live variant runs, each with five live ClinVar rows. Not for dbSNP or LitVar2 rows (V-30b-03) | M3 red; `line_probe.py` |
| J-30b-03 and A-30-03, the lookup takes a name lookup's call | Closed for the fallback names (M4, M4c, M4d red). The fold's two calls are reserved in code but no test reads them (V-30b-02). Live: 12 calls before, 13 or 14 after, `reserve_calls` 4 | mutation table |
| J-30b-04, the task outlives an early Write end | Closed. `_drop_variant_lookup` in `write_node`'s `finally` (`core/graph.py:13970`) runs on every exit of the `try`, normal, raise or cancel, and `_cancel_if_pending` never awaits; the field is cleared after the await (`variant_lookup_task = None`), so a normal end cancels nothing | M6, M6b red |
| J-30b-05 and A-30-04, 4 s worst case | Closed: `_REQUEST_TIMEOUT_S = 1.5`, the test reads the product's constant | M5 red |
| J-30b-06, germline block not pinned | Closed | M7 red |
| A-30-05, documents | Closed: queries 22, 79 and 115 now say what a person sees; the query 22 text promises the line while a live ClinVar record shows none, which holds on the web and command line but not on MCP and GraphQL (V-30b-04) | `git diff origin/develop...HEAD -- testing/Test_queries_and_workflows.md` |

## Mutations

`<scratchpad>/card30b_ver/mutate.py`, one property per run over `core/test_graph.py`, `synthesis/test_answer_layout.py`, `synthesis/test_variant_classifications.py`, `core/test_write_answer_structure.py` (in that order, because of V-30b-01), each file restored and compared byte for byte; `git status --short` empty afterwards. Baseline `485 passed`.

| Mutation | Result |
|---|---|
| M1 the text suffix returns "" | RED, `test_card30b_the_text_surfaces_carry_each_classification[plain_language]` |
| M1b the suffix appended past the 1000 cap | GREEN (V-30b-02) |
| M1c the table row site without the suffix | RED, `...carry_each_classification[researcher]` |
| M1d the grouped list item site without the suffix | GREEN, equivalent: a classified variant always adds the "ClinVar classification" column, so its group is always a table (`as_table = len(columns) > 1`, `core/graph.py:13745`) |
| M1e the Plain list site without the suffix | RED, `...[plain_language]` |
| M2 mapped variants looked up | RED, `test_card30b_the_variant_to_disease_table_has_no_classification` |
| M3 live rows ignored by the line | RED, `test_a_live_clinvar_row_keeps_the_line` |
| M4 `reserve_calls=0` at the call site | RED, `test_card30b_at_18_calls_used_the_name_lookup_still_gets_its_call` |
| M4b the fold's 2 dropped | GREEN (V-30b-02) |
| M4c the fallback's 4 dropped | RED, the same |
| M4d the reserve ignored in `_requests_allowed` | RED, `test_the_lookup_leaves_the_calls_the_name_lookups_need` |
| M5 timeout back to 4 s | RED, `test_a_hung_reply_costs_at_most_one_and_a_half_seconds` |
| M6 no cancel in `finally` | RED, `test_card30b_the_lookup_is_stopped_when_write_ends_early` |
| M6b the task never registered on `_RunDecisions` | RED, the same |
| M7 oncogenicity block read first | RED, `test_only_the_germline_block_is_read` |
| M8 the floor back on the line | RED, `test_card30b_a_fully_read_list_drops_the_line_and_keeps_the_ask` |
| M9 join by position | RED, `test_classification_joins_by_record_id_with_records_shuffled` |

## Earlier classes on the merged tree

| Class | Holds? | Evidence |
|---|---|---|
| Every shown value is ClinVar's germline value word for word, joined by record id | Yes, 134 of 134 | `rows_check.py`, free ESummary per 50 shown ids: BRCA1 Researcher 40, Plain 40, CFTR 54, `mismatches: 0`, every record's title holds the row's name. BRCA1: 15 Uncertain significance, 23 Conflicting classifications of pathogenicity, 2 Pathogenic. CFTR: 40 Uncertain significance, 4 Pathogenic, 4 Pathogenic/Likely pathogenic, 2 Likely pathogenic, 3 Likely benign, 1 Conflicting |
| No row lost on any failure | Yes | A/B probe (below), lookup returning nothing: every event identical to develop in all 21 cases; returning part: only the classified rows' text differs |
| Row text under 1000, not duplicated or garbled | Yes on every live row (longest 159 characters), the value once, after the row's own marker. The clip is untested (V-30b-02) | `rows_check.py` `TEXT` checks: none fired |
| Slice C's paper titles | Unchanged: titles shown, for example `['BRCA1: An Endocrine and Metabolic Regulator.', 'PMID:35432218']`; the A/B probe shows only variant row tokens differ | live logs |
| Slice A1's dbSNP rows | None on these answers (no rs id in the questions); A/B: non variant tokens identical | A/B |
| Card 8's trust line | True: "Based on 57 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases" (BRCA1), 71 for CFTR, 61 for HNF1A. Citations, the done payload and claim trust are identical to develop in all 21 A/B cases; the classification adds no citation | A/B: `citations_same=True done_same=True claims_same=True` |
| Verdict paths | Unchanged. Develop floors on `variant_classification_note(...) is not None`, which is "a graph variant and no classification field"; the branch's `lists_graph_variant` is the same condition written out (`core/graph.py:15258`). A/B: `ask->ask` and `answer->answer` in every case | A/B; M8 red |
| Writer input | Unchanged | A/B `writer_same=True` |

A/B probe: `<scratchpad>/card30b_ver/test_zz_ver_ab_probe.py` (the judge's, with `**_kw`), run from the scratchpad against each tree, `compare_ab.py`. With every variant classified, the only differences are the suffixed row text and step 1's line with its paragraph break gone, as decided.

## Commands

In `<worktrees>/card30b-ver` at `66a56dfe`:

| Command | Result |
|---|---|
| `pytest -q tests/system_03_search_agent/synthesis/ core/test_graph.py core/test_write_answer_structure.py` | `1286 passed, 10 skipped, 1 xfailed in 37.89s` |
| `pytest -q tests/system_03_search_agent/adapters/` | `959 passed, 2 warnings in 84.59s` |
| The four touched files with `test_variant_classifications.py` and `test_write_answer_structure.py` first | `3 failed, 482 passed` (V-30b-01); in collection order `485 passed` |
| `ruff check` (gate03) | `All checks passed!` |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02) | exit 0 |
| gate01 compile and import | exit 0 |
| `ruff format --check` on the two new files | `2 files already formatted` |
| CI on #269, head `66a56dfe` | Python gates (1, 2, 3, 4, 6, 9) pass 6m35s, Integration suite pass, Frontend gates pass, Accessibility pass. So V-30b-01 does not bite in gate04's order |

## Live runs

Four runs through `core.run.run_streaming()` on the branch tree, `<scratchpad>/card30b_ver/live.py`, session ids `card30b-ver-<label>`, settings as card 115's adversary (`CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`). Spend: $0.0386 of $0.60. In all four the writer's prose was not shown ("Note: no written summary could be checked against the records"), as in the adversary's and step 1 verifier's runs of the same questions. A first loop of four failed on an argument error before any model call and spent nothing.

| Run | Classification decision | Step 1 line | Trust outcome and line | Done | Lookup |
|---|---|---|---|---|---|
| BRCA1, Researcher | `asks_classification` | shown once (5 live ClinVar rows without one) | ask, "Based on 57 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases" | 19.60 s | 40 asked, 40 read, 0.275 s, 1 call |
| BRCA1, Plain language | `asks_classification` | shown once | ask, the same line | 19.06 s | 40 of 40, 0.269 s, 1 call |
| Query 22, Researcher | `asks_classification` | shown once | ask, "Based on 71 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases" | 20.38 s | 54 of 54, 0.312 s, 2 calls |
| Query 79, Researcher | `not_applicable` | absent; card 23's line once | answer, "Based on 61 sources cited from ClinVar, MedGen, ClinicalTrials.gov and 3 other databases" | not measurable: the machine slept from 01:41:47 to 01:57:24 (`pmset -g log`), so the done event read 953.83 s; first token 6.34 s | none started (all variants mapped) |

The time the branch adds is the lookup wait, 0.27 to 0.31 s; the rest of each run is the guard and planning calls (the BRCA1 Researcher guard classify alone took 6.26 s). Query 22's 20.38 s is over the owner's 20 s with 0.31 s of it from the lookup.

Ten rows per run, the shown value against the ClinVar record tonight:

| Run | Record | Variant | Shown | ClinVar | Same |
|---|---|---|---|---|---|
| BRCA1 Res | ClinVar:1000183 | NM_007294.4(BRCA1):c.4709T>C (p.Leu1570Pro) | Uncertain significance | Uncertain significance | yes |
| BRCA1 Res | ClinVar:1002750 | NM_007294.4(BRCA1):c.2614T>C (p.Phe872Leu) | Conflicting classifications of pathogenicity | the same | yes |
| BRCA1 Res | ClinVar:1004775 | NM_007294.4(BRCA1):c.1976C>G (p.Pro659Arg) | Conflicting classifications of pathogenicity | the same | yes |
| BRCA1 Res | ClinVar:1005598 | NM_007294.4(BRCA1):c.4333C>T (p.Pro1445Ser) | Uncertain significance | the same | yes |
| BRCA1 Res | ClinVar:1007698 | BRCA1 | Conflicting classifications of pathogenicity | the same | yes |
| BRCA1 Res | ClinVar:1009204 | NM_007294.4(BRCA1):c.500C>T (p.Thr167Ile) | Uncertain significance | the same | yes |
| BRCA1 Res | ClinVar:1009551 | BRCA1 | Conflicting classifications of pathogenicity | the same | yes |
| BRCA1 Res | ClinVar:1010631 | NM_007294.4(BRCA1):c.547+5G>A | Uncertain significance | the same | yes |
| BRCA1 Res | ClinVar:1012156 | NM_007294.4(BRCA1):c.3982del (p.Ser1328fs) | Pathogenic | Pathogenic | yes |
| BRCA1 Res | ClinVar:1014279 | BRCA1 | Conflicting classifications of pathogenicity | the same | yes |
| BRCA1 Plain | the same ten records | as Researcher | the same ten values, each as "<name>, ClinVar classification: <value>", for example "NM_007294.4(BRCA1):c.3982del (p.Ser1328fs), ClinVar classification: Pathogenic" | the same | yes, 10 of 10 |
| Query 22 | ClinVar:1000823 | NM_000492.4(CFTR):c.1384G>A (p.Ala462Thr) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1009171 | NM_000492.4(CFTR):c.1051A>G (p.Thr351Ala) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1011536 | NM_000492.4(CFTR):c.3064G>A | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1018890 | NM_000492.4(CFTR):c.4028G>A (p.Gly1343Asp) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1029874 | NM_000492.4(CFTR):c.389T>C (p.Leu130Pro) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1036122 | NM_000492.4(CFTR):c.3498C>G (p.Phe1166Leu) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1038737 | NM_000492.4(CFTR):c.1444A>G (p.Ile482Val) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1043026 | CFTR | Conflicting classifications of pathogenicity | the same | yes |
| Query 22 | ClinVar:1044502 | NM_000492.4(CFTR):c.2764G>A (p.Val922Ile) | Uncertain significance | the same | yes |
| Query 22 | ClinVar:1052121 | NM_000492.4(CFTR):c.1502C>T (p.Thr501Ile) | Likely pathogenic | the same | yes |
| Query 79 | ClinVar:1025247 | NM_000545.8(HNF1A):c.780G>A (p.Thr260=) | none, by design; disease cell "Maturity-onset diabetes of the young" | n/a | as develop |
| Query 79 | ClinVar:1026109, ClinVar:1033090 | HNF1A deletion and c.58G>A | none, by design; disease cells named | n/a | as develop |

"BRCA1" and "CFTR" in the variant column above are rows whose long name I cut in my table, not on the page. Query 79 is 38 variant rows, none with a classification, three columns, card 23's line true.

One row as the command line prints it:

- BRCA1 Researcher: `SequenceVariant ClinVar:1000183, name: NM_007294.4(BRCA1):c.4709T>C (p.Leu1570Pro) [1]. ClinVar classification: Uncertain significance. `
- BRCA1 Plain language: the same text.
- Query 22: `SequenceVariant ClinVar:1000823, name: NM_000492.4(CFTR):c.1384G>A (p.Ala462Thr) [1]. ClinVar classification: Uncertain significance. `
- Query 79: `SequenceVariant ClinVar:1025247, name: NM_000545.8(HNF1A):c.780G>A (p.Thr260=) [1]. `, as develop.

## Verdict

The fix round closed every judge and adversary finding it named, and each new test goes red under its own mutation, except the token cap clip and the fold's reserve (V-30b-02). Every shown classification is ClinVar's germline word for its own record, 134 of 134 live. No row is lost on a failure, and the trust line, citations, claim trust, writer input and verdict paths are as on develop.

One thing is worse than develop on the card's own questions. V-30b-04: the row text item 1 added pushes the variant answers past MCP's and GraphQL's 8000 character cap. On query 22 those surfaces then lose the five trial records and step 1's line that develop shows. V-30b-03 is worse only in a narrow rs id shape. V-30b-01 and V-30b-02 are instrument gaps.

VERDICT: FIX FIRST
