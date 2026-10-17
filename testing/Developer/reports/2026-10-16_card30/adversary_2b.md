# Card 30 step 2b adversary report

Pull request #269, branch `fix/card30-variant-classifications-shown`, commits `6498efd7` and `14571f3a` on develop `655e9dfe`. One adversary round. Worktree `<worktrees>/card30b-adv` at `14571f3a`, detached. Probes in `<scratchpad>/card30b_adv/`.

The decisions under test: every listed knowledge graph variant shows ClinVar's classification of it, verbatim from its record; step 1's line goes only when every shown row has one; a classification question stays "ask".

## Table of contents

- [Findings](#findings)
- [Local probes](#local-probes)
- [Live runs](#live-runs)
- [Hunts that held](#hunts-that-held)
- [Verdict](#verdict)

## Findings

### A-30-01: card 23's line under the variant-to-disease table now says the classification "is not shown here" directly under a "ClinVar classification" column

- Severity: major. Worse than develop: yes, a stated fact that is true on develop becomes false on the branch.
- Where: `src/system_03_search_agent/synthesis/answer_layout.py:652` adds `("SequenceVariant", CLASSIFICATION_ROW_FIELD): "ClinVar classification"` to `_ROW_TYPE_COLUMNS`, which `record_status_or_year` (`answer_layout.py:756` onward) reads for every `SequenceVariant` group, the mapped variant-to-disease table included. `core/graph.py` then emits card 23's `VARIANT_TO_DISEASE_SOURCE_NOTE` under that same table unchanged (`variant_to_disease_source_note(entity_type, mapped)`, the block after the table rows in `_answer_parts`). The note's text, `answer_layout.py:356` to `:360`: "Each row lists the conditions the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here."
- Reproduction: `<scratchpad>/card30b_adv/probes/test_adv_card30b.py::test_probe_hnf1a_mapped_table_with_classifications`, the repository's own card 23 fixture (`_FOLDED_VARIANT_ROWS` plus `_FOLDED_GENE_ROW`, Researcher) with the lookup returning two values. Branch output, pasted:
  ```
  {"k": "heading", "text": "Variant-to-disease mapping\n\n"}
  {"k": "table_header", "cells": ["Variant", "Identifier", "Associated disease(s)", "ClinVar classification"]}
  {"k": "table_row", "cells": ["variant number 1", "ClinVar:1", "Maturity-onset diabetes of the young", "Likely benign"]}
  {"k": "table_row", "cells": ["variant number 2", "ClinVar:2", "None named: the ClinVar record says not provided", "Pathogenic"]}
  {"k": "note", "text": "Each row lists the conditions the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here. D..."}
  ```
- Who sees it: query 79 (`What diseases are caused by variants in the HNF1A gene?`) at Researcher, and any variant-to-disease table whose variants carry `ClinVar:` ids. The frontend pins this line directly under its own table by its prefix (`VARIANT_TABLE_SOURCE_NOTE_PREFIX`, `frontend/src/hooks/useRunView.ts`), so the person reads the column and, one line below, that the column does not exist.
- Why the builder's checks missed it: the build report's develop comparison ran the folded HNF1A table "lookup returning nothing" (`build_2b.md`, "Probe against develop"), and `test_card30b_*` never hands a mapped table a classification.
- In the user's words: a person told "the classification is not shown here" right under a column of classifications cannot tell which to believe, and may decide the column is not ClinVar's.
- Fixable inside the fence in one round: yes (card 23's line or the column, keyed on whether the table shows a classification; `answer_layout.py` and `_answer_parts` are both in the fence).

### A-30-02: live, the step 1 line goes while five ClinVar variant rows on the same page still show no classification, under "Which BRCA1 variants are pathogenic?"

- Severity: major. Worse than develop: yes. On develop the line ("ClinVar's classification of these variants ... was not retrieved, so this list does not say which are pathogenic") covers every variant on the page; on the branch it is gone while a second variant table carries no classification.
- Where: `variant_classification_note` (`synthesis/answer_layout.py:401` to `:421`) drops the line when every `layer_1_graph` `SequenceVariant` finding is classified. The live ClinVar search rows (Plan's `BRCA1[gene]` ESummary, five rows) are not graph variants, so they are never counted, and their own `germline_classification` is fetched but not shown (step 2a, not built).
- Reproduction: live run `brca1-res` (below), branch tree, Researcher. The graph table is fully classified and the line is absent (`notes: {"card30": 0}`), and the page then shows, pasted from the token log:
  ```
  heading 'Clinvar records found'
  table_header ['Variant', 'Identifier']
  table_row ['NM_007294.4(BRCA1):c.5243_5277+2788del', 'VCV000267740']
  table_row ['NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG', 'VCV000267741']
  table_row ['NG_005905.2:g.(147057_150288)_(160933_166866)del', 'VCV000373892']
  table_row ['GRCh37/hg19 17q21.31(chr17:41267743-41267796)x3', 'VCV004823850']
  table_row ['NM_007294.4(BRCA1):c.2145C>G (p.Thr715=)', 'VCV004848411']
  ```
  ClinVar's own classifications of those five, free ESummary tonight: "no classification for the single variant" three times, "Uncertain significance", "Likely benign". None is pathogenic.
- In the user's words: someone who asked which BRCA1 variants are pathogenic sees five more BRCA1 variants listed with nothing beside them and no line saying their classification is missing, one of them likely benign. After card 8 (merged on develop as `ec547c2a`, not in this branch's base), an "ask" trust line no longer says "not yet confirmed", so nothing on the page cautions about these five rows.
- The same shape live in query 22 (`q22-plain`): 54 classified graph rows, then five "Clinvar title" list items with no classification, and no line. In Plain language the five sit in the same "Where this answer comes from" list right after 40 rows that each carry a classification.
- This is the brief's hunt "the step 1 line removed while a row still lacks a value": the decision says the line goes "only when every shown row has one", and these are shown rows.
- Fixable inside the fence in one round: yes (count every shown ClinVar variant row in the line's condition, or show the classification those rows already carry).

### A-30-03: at the per-query call ceiling, the new lookup takes the last call and the variant-to-disease table loses its disease names

- Severity: minor (a narrow edge: the question must reach Write with 18 Layer 2/3 calls spent, or 17 with two lookup chunks, and the MedGen titles must not be cached). Worse than develop: yes, a table develop shows is lost.
- Where: `core/graph.py`, `_write_answer`, the lookup is started with `asyncio.create_task(resolve_variant_classifications(variant_curies))` before the MedGen lookups and awaited after them. The transport charges the ceiling synchronously at entry (`tools/ncbi_transport.py`, `call_budget.charge_one_call` before `limiter.acquire`). So the MedGen ESearch charges first, the ClinVar ESummary charges while that ESearch is in flight, and the MedGen ESummary is then refused. `_requests_allowed` (`synthesis/variant_classifications.py`) checks the ceiling but does not leave room for the name lookups it runs beside.
- Reproduction: `<scratchpad>/card30b_adv/probes/test_adv_card30b.py::test_probe_ceiling_race_real_network`, the card 23 HNF1A shaped fixture at Researcher, real free MedGen and ClinVar E-utilities calls, MedGen cache cleared, the writer stubbed, the query budget preset to 16, 17 and 18 calls. Pasted, used=18:
  ```
  branch  (calls_after=20)
  ["OMIM included", "MedGen:C0342276"]
  ["OMIM allelic variant", "MedGen:C3661900"]
  ["Variant", "Identifier", "ClinVar classification"]
  ["variant number 1", "ClinVar:1", ""]
  ["variant number 2", "ClinVar:2", "Pathogenic/Likely pathogenic"]
  develop (calls_after=20)
  ["Maturity-onset diabetes of the young", "MedGen:C0342276"]
  ["Variant", "Identifier", "Associated disease(s)"]
  ["variant number 1", "ClinVar:1", "Maturity-onset diabetes of the young"]
  ["variant number 2", "ClinVar:2", "None named: the ClinVar record says not provided"]
  ```
  At 16 and 17 both trees keep the names and the mapping.
- In the user's words: on a question that used nearly all its lookups, the table of which disease each variant is linked to disappears, the disease list shows "OMIM included" in place of a disease name, and a classification column appears instead.
- Fixable inside the fence in one round: yes (start the ClinVar lookup after the name lookups have charged, or have it leave the calls they need).

### A-30-04: a slow or hung ClinVar reply holds the whole answer up to 4 seconds longer than develop

- Severity: minor (rare path; the decision accepted "about a second"). Worse than develop: yes on that path, by more than a second.
- Where: `synthesis/variant_classifications.py`, `_REQUEST_TIMEOUT_S = 4.0`, `asyncio.wait_for(summary(...), timeout=_REQUEST_TIMEOUT_S)`. `_write_answer` awaits the task before the listing and the writer, so on a question with no MedGen lookup to overlap (BRCA1, CFTR, GCK) the full wait lands on the answer, the early listing included.
- Reproduction: `<scratchpad>/card30b_adv/probes/hang_probe.py`, `summary` replaced by a 30 second sleep, 80 CURIEs. Pasted: `ClinVar classification lookup failed: TimeoutError` then `hung ESummary: result {} elapsed 4.01 s`. Rows are kept and the line stays, so nothing is lost; only time. The build report's own live timing shows the 429 path at 2.32 s.
- Fixable inside the fence: yes, if the owner wants the bound nearer a second (a shorter timeout).

### A-30-05: the owner's test queries document still expects step 1's line where the branch removes it

- Severity: minor, documentation, not product. Worse than develop: no.
- Where: `testing/Test_queries_and_workflows.md` (develop and the night's docs branch): query 22, "Below the answer, one line reads 'ClinVar's classification of these variants ... was not retrieved'"; query 79's Plain language bullet, "its Notes list carries card 30's line"; query 115 and the lines at about `:603` and `:1530`. The diagnosis says "When step 2b is built, the expectation becomes: each listed variant shows its ClinVar classification, and the line no longer appears." The pull request changes no document.
- Live: query 22 on the branch shows no line (run `q22-plain`), so a retest against today's text fails it.
- For the lead's docs pull request, not this card's fence.

## Local probes

All on both trees: the branch `<worktrees>/card30b-adv` (`14571f3a`) and develop `<worktrees>/card30b-adv-dev` (`ec547c2a`, develop today; it adds card 8's trust line over this pull request's base `655e9dfe`; `git merge-tree` of the two is clean).

| Probe | Branch | Develop | Holds? |
|---|---|---|---|
| Card 23 HNF1A fixture, Researcher, lookup returns two values | Fourth column "ClinVar classification", card 23's line says it is "not shown here" | Three columns, line true | No, A-30-01 |
| `_UNCLASSIFIED_VARIANT_ROWS` with "Pathogenic/Likely pathogenic", "no classification for the single variant", "not provided" | Each shown verbatim, both depths; line absent | No column, line present | Yes, ClinVar's words unchanged |
| Ceiling preset to 16, 17, 18 with real lookups | Names lost at 18 | Names kept at 18 | No, A-30-03 |
| Hung ESummary | 4.01 s, `{}`, rows kept | No lookup | Rows yes, time A-30-04 |
| A deleted ClinVar id (`ClinVar:1`, ESummary has no `title`, real call) | Row kept, cell empty | Row kept | Yes, nothing invented |
| Somatic only TP53 records 4539756, 4539755, 4539750 (free ESummary) | `germline_classification.description` is `''`, so unread; their "Likely oncogenic" is never shown as germline | n/a | Yes |
| Graph id space: 40 saved BRCA1 graph CURIEs against ESummary (`<scratchpad>/card30b_adv/esum_check.py`) | Every graph name equals the ClinVar record title for the same id, so `ClinVar:<n>` is the Variation ID ESummary keys on | n/a | Yes |
| Branch tests, `test_variant_classifications.py`, `test_write_answer_structure.py`, `test_answer_layout.py` with `-k "card30 or card23 or classification"` | `54 passed, 164 deselected in 10.85s` | n/a | Yes |


## Live runs

Five runs through `core.run.run_streaming()` on the branch tree, `reads_placement=True`, session ids `card30b-adv-<label>`, settings as card 115's adversary (`CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`, the writer from the local env). Script `<scratchpad>/card30b_adv/live.py`; it times the lookup task and the moment Write reaches the await. Rows checked by `<scratchpad>/card30b_adv/rows_check.py`, one free ESummary per 50 shown ids. Spend: $0.0405 of $0.75.

| Run | Rows checked | Verbatim match | Step 1 line | Classification decision | Trust outcome and line | Lookup wait | Done, branch | Done, develop equivalent |
|---|---|---|---|---|---|---|---|---|
| `brca1-res` | 40 of 40 | 40 | absent | `asks_classification` | ask, "Based on 57 sources cited, not yet confirmed" | 0.283 s | 18.02 s | 12.62 s |
| `brca1-plain` | 40 of 40 | 40 | absent | `asks_classification` | ask, same line | 0.305 s | 16.61 s | none run |
| `q22-plain` | 54 of 54 | 54 | absent | `asks_classification` | ask, "Based on 71 sources cited, not yet confirmed" | 0.329 s | 16.87 s | 12.94 s |
| `gck-res` | 50 of 50 | 50 | absent | `not_applicable` | ask (structured fallback), "Based on 68 sources cited, not yet confirmed" | 0.340 s | 11.43 s | 11.01 s |
| `rs334-res` | 0 graph variants | n/a | absent | `not_applicable` | ask, "Based on 1 source cited, not yet confirmed" | no lookup | 16.03 s | none run |

Develop equivalent times are card 30 step 1's verifier runs on the same questions and depths (`<scratchpad>/card30_ver/live_*.jsonl`), the code develop now carries for this path. Every gap beyond the lookup wait is the writer and guard models: the rs334 run, which makes no lookup, spent 7.98 s in `guardrail.classify` alone. The time the branch adds is the measured wait, 0.28 to 0.34 s, under a second.

Counts shown: BRCA1 15 Uncertain significance, 23 Conflicting classifications of pathogenicity, 2 Pathogenic (both depths, identical to the diagnosis's 2026-10-16 count). CFTR 40 Uncertain significance, 4 Pathogenic, 4 Pathogenic/Likely pathogenic, 2 Likely pathogenic, 3 Likely benign, 1 Conflicting. GCK 13 Benign, 11 Likely benign, 3 Benign/Likely benign, 8 Pathogenic, 2 Pathogenic/Likely pathogenic, 2 Likely pathogenic, 7 Uncertain significance, 4 Conflicting. Every shown record's gene list includes the asked gene. rs334 kept its row `["rs334", "rs334", "HBB", "not-provided, protective, likely-benign, pathogenic, other"]` under "Clinical significance", no lookup made, no line.

Ten rows per run (plus the compound values), shown against the ClinVar record tonight:

BRCA1, Researcher (`brca1-res`):

| Record | Variant | Shown | ClinVar record today | Verbatim |
|---|---|---|---|---|
| ClinVar:1000183 | NM_007294.4(BRCA1):c.4709T>C (p.Leu1570Pro) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1000551 | NM_007294.4(BRCA1):c.3664G>A (p.Glu1222Lys) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1001081 | NM_007294.4(BRCA1):c.353T>C (p.Leu118Pro) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1002154 | NM_007294.4(BRCA1):c.1226T>G (p.Val409Gly) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1002750 | NM_007294.4(BRCA1):c.2614T>C (p.Phe872Leu) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1003072 | NM_007294.4(BRCA1):c.3017A>C (p.His1006Pro) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1003150 | NM_007294.4(BRCA1):c.4328G>T (p.Arg1443Leu) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1004428 | NM_007294.4(BRCA1):c.1810A>G (p.Lys604Glu) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1004775 | NM_007294.4(BRCA1):c.1976C>G (p.Pro659Arg) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1004786 | NM_007294.4(BRCA1):c.3556C>G (p.Leu1186Val) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |

query 22 CFTR, Plain language (`q22-plain`):

| Record | Variant | Shown | ClinVar record today | Verbatim |
|---|---|---|---|---|
| ClinVar:1000823 | NM_000492.4(CFTR):c.1384G>A (p.Ala462Thr) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1002760 | NM_000492.4(CFTR):c.2929T>G (p.Ser977Ala) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1003660 | NM_000492.4(CFTR):c.3508C>T (p.Pro1170Ser) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1007213 | NM_000492.4(CFTR):c.2131T>C (p.Phe711Leu) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1009171 | NM_000492.4(CFTR):c.1051A>G (p.Thr351Ala) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1009391 | NM_000492.4(CFTR):c.2950G>A (p.Asp984Asn) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1009463 | NM_000492.4(CFTR):c.2546A>G (p.Tyr849Cys) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1010196 | NM_000492.4(CFTR):c.3691T>C (p.Ser1231Pro) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1011536 | NM_000492.4(CFTR):c.3064G>A (p.Val1022Met) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1012571 | NM_000492.4(CFTR):c.744-9G>T | Uncertain significance | Uncertain significance | yes |
| ClinVar:1027585 | NM_000492.4(CFTR):c.1585-2A>T | Pathogenic/Likely pathogenic | Pathogenic/Likely pathogenic | yes |
| ClinVar:1052121 | NM_000492.4(CFTR):c.1502C>T (p.Thr501Ile) | Likely pathogenic | Likely pathogenic | yes |
| ClinVar:1065566 | NM_000492.4(CFTR):c.327T>G (p.Tyr109Ter) | Pathogenic/Likely pathogenic | Pathogenic/Likely pathogenic | yes |

GCK, Researcher (`gck-res`):

| Record | Variant | Shown | ClinVar record today | Verbatim |
|---|---|---|---|---|
| ClinVar:1028584 | NM_000162.5(GCK):c.415A>T (p.Met139Leu) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1045215 | NM_000162.5(GCK):c.762T>G (p.Asn254Lys) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1074406 | NM_000162.5(GCK):c.359dup (p.Met121fs) | Pathogenic/Likely pathogenic | Pathogenic/Likely pathogenic | yes |
| ClinVar:1077171 | NM_000162.5(GCK):c.397T>C (p.Phe133Leu) | Conflicting classifications of pathogenicity | Conflicting classifications of pathogenicity | yes |
| ClinVar:1098819 | NM_000162.5(GCK):c.1139A>C (p.His380Pro) | Pathogenic | Pathogenic | yes |
| ClinVar:1172675 | NM_000162.5(GCK):c.82G>A (p.Glu28Lys) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1172895 | NM_000162.5(GCK):c.691A>G (p.Asn231Asp) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1172896 | NM_000162.5(GCK):c.660C>A (p.Cys220Ter) | Pathogenic | Pathogenic | yes |
| ClinVar:1179956 | NM_000162.5(GCK):c.363+318G>A | Benign | Benign | yes |
| ClinVar:1187444 | NM_000162.5(GCK):c.434C>T (p.Pro145Leu) | Uncertain significance | Uncertain significance | yes |
| ClinVar:1191898 | NM_000162.5(GCK):c.617C>T (p.Thr206Met) | Pathogenic/Likely pathogenic | Pathogenic/Likely pathogenic | yes |
| ClinVar:1192245 | NM_000162.5(GCK):c.138G>A (p.Arg46=) | Benign/Likely benign | Benign/Likely benign | yes |
| ClinVar:1197671 | NM_000162.5(GCK):c.579+29G>T | Benign/Likely benign | Benign/Likely benign | yes |


`brca1-plain` showed the same 40 values as `brca1-res`, each as "<name>, ClinVar classification: <value>". In both BRCA1 runs and in CFTR, five live ClinVar search rows followed with no classification and no line (A-30-02).


## Hunts that held

| Hunt | Result |
|---|---|
| A variant shown with another variant's classification | Held. Joined by the record's own uid (`_summary_classifications`); 184 of 184 live rows match their own record, and every graph name equals its record's title |
| Stale or superseded classification | Held. Live ESummary per answer, no cache; a deleted id gives an empty cell |
| Somatic or oncogenicity shown as germline | Held. Only `germline_classification.description` is read; somatic only records read as unread. A record with both shows only the germline one under "ClinVar classification" (evidence, not a finding) |
| A word changed ("Pathogenic" for "Pathogenic/Likely pathogenic") | Held. 8 compound values live, all verbatim |
| A classification for a variant under a different gene | Held. Every live record's gene list includes the asked gene; the value is always the listed record's own |
| Line removed while a graph row still lacks a value | Held for graph rows: `test_card30b_one_unread_variant_keeps_its_row_and_the_line` passes in both depths in my run above. Not held for the other ClinVar rows on the page, A-30-02 |
| A fully classified list read as confirmed | Held. Both classification questions stayed "ask" with the line gone (second commit's floor) |
| Slower by more than a second | Held on the normal path (0.28 to 0.34 s). Not on a hung reply, A-30-04 |
| A 429 or timeout drops rows | Held. Every failure returns `{}` and the rows stay as today |
| ClinVar's own non answers ("no classification for the single variant", "not provided") | Shown verbatim and counted as classified, so the line goes. True to ClinVar; the build report already asks the owner about it |


## Verdict

Two major findings are worse than develop and fixable inside the card's fence in one round: A-30-01 (card 23's line contradicts the new column under query 79's table) and A-30-02 (the line goes while five ClinVar variant rows on the same page show no classification). A-30-03 and A-30-04 are minor and also worse than develop on narrow paths. Every classification the branch shows matched its ClinVar record word for word, 184 of 184.

VERDICT: FIX FIRST
