# Fresh verifier: card 37 slice A1

Pull request #262, branch `fix/card37-rs334-named-by-its-id`, commit `b250b689` on develop `78c68c1c`. Dial 1, layout only: no judge or adversary ran, so this report carries the correctness check and the hunt for a misleading record. Worktrees: `<worktrees>/card37a1-ver` (branch head) and `<worktrees>/card37a1-ver-dev` (develop, for comparison).

## Table of contents

- [Findings](#findings)
- [Evidence](#evidence)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

### V-37-01, major, worse than develop: a dbSNP record whose significance is withheld loses its one cited fact from the screen

The tool withholds the whole `clinical_significance` list when one term is over 40 characters or the list over 10 items (`tools/ncbi_dbsnp.py:1515` to `:1522`, `_split_comma_field` at `:1334`). Then the row's first field, and its one finding, is `functional_consequence`. On develop that value was the row's label, so it was on screen. On the branch the label is the rs id and no column shows the consequence, so the cited fact is gone from both depths' cells. This is the same loss the diagnosis's correction 2 calls worse for the significance values, on the variants the correction did not look at.

How common: 7 of the first 12 rs ids I fetched through the product's own `ncbi_dbsnp` tool had the significance withheld: rs6025, rs1801133, rs1800562, rs1042522, rs80359198, rs429358, rs1799945 (and rs67376798 of a second 22). Probe `<scratchpad>/card37a1_ver/probe_real_dbsnp.py`, output `probe_real_dbsnp.out`.

The page for real rs6025, faked writer whose sentence does not survive (the 2026-10-09 fallback shape), `<scratchpad>/card37a1_ver/probe_real_pages.py`:

```
DEV table_header ['Variant', 'Identifier']
DEV table_row    ['coding_sequence_variant, missense_variant', 'rs6025']
DEV claim        'Found 1 variant record record: coding_sequence_variant, missense_variant [1]. '
BR  table_header ['Variant', 'Identifier', 'Gene']
BR  table_row    ['rs6025', 'rs6025', 'F5']
BR  claim        'Found 1 variant record record: rs6025 [1]. '
```

Same shape for rs1801133 (MTHFR), rs429358 (APOE), rs80359198 (BRCA2). The marker [1] on the branch row cites a consequence the row no longer shows. The web screen renders `cells`, not `text` (`frontend/src/components/screens/AnswerScreen.tsx:532` to `:538`), so the row's sentence does not rescue it; the command line and MCP print `text` (`adapters/cli/render.py:876` onward), so there only the opening sentence changes.

When the writer's sentence survives, the consequence can still reach the prose; the listing loses it every time, and the no written answer fallback loses it entirely.

Fixable inside the fence in one round: one more row in the closed table, `("Variant record", "functional_consequence")` to a "Consequence" column, read only when the significance is absent (the loop already returns the first match in insertion order), plus a test on the withheld shape. Plain language would still read "Genetic variant (F5)", which the decision names.

### V-37-02, minor, inside the decision's named label: Plain language no longer shows any significance value

Live query 23 at Plain language took the no written answer fallback (below). The page reads "I found 1 genetic variant related to rs334 [1]." and one row, "Genetic variant (HBB)". No significance value is anywhere on the web screen: the row renders `cells[0]` (`AnswerScreen.tsx:538`) and the Sources card shows `entity_name` or `source`, never `claim_text` (no `claim_text` reference under `frontend/src/components`). Develop showed the list as the row's title. The owner's decision names the Plain language label "Genetic variant (HBB)", so I do not count this as worse; the lead should confirm the owner knows Plain language loses the values, since the diagnosis's correction 2 only places them in a Researcher column.

### V-37-03, minor, reachable in principle, not observed: the significance column is cut at 128 characters mid term

`record_status_or_year` returns `value.strip()[:MAX_IDENTIFIER_CHARS]`, 128 (`answer_layout.py:633`, `:492`), with no word clip. dbSNP allows 10 terms of up to 40 characters (`tools/ncbi_dbsnp.py:389`, `:398`), so a list can reach 418 characters, and a hard cut can turn "pathogenic-likely-pathogenic" into "pathogenic" or drop the last terms silently: the exact defect class `_split_comma_field`'s docstring records (`tools/ncbi_dbsnp.py:1344` to `:1349`). Develop's label for the same row allowed 500. Probe: a constructed 177 character list of eight real dbSNP terms comes back as 128 characters ending "likely-benign, benign-like", with "established-risk-allele" and "drug-response" gone. In 34 real rs ids fetched tonight the longest list was 98 characters (rs3918290), so no person sees it today. Not worse than develop for any record observed; a `clip_to_word` or a 500 cap would close it.

### V-37-04, minor, not worse than develop: the guard test does not read the real dbSNP row builder

`test_the_writers_input_and_the_trust_verdict_do_not_move` says the row is "shaped by the real builder", but `_rs334_row` hand-builds the fields and calls `_pseudo_row`. Mutation: put `"rsid": snp.rsid` first in the `ncbi_dbsnp` branch of `core/graph.py` (`:5032`), which would make the rs id the writer's finding and move every rs id answer's trust verdict. Result: the new file `13 passed`, `core/test_layer_handoff.py` `28 passed`. Restored. The branch does not touch `core/graph.py`, so nothing is worse today; the guard simply does not guard the builder it names.

### V-37-05, minor: the label's URL guard is untested

Mutation: drop `and not _URL_PREFIX.match(value)` from `_row_type_label`. Result `13 passed`. An rs id is never a URL in practice, so no person is affected.

## Evidence

### Tests

- `test_variant_record_label.py`, `test_answer_layout.py`, `core/test_write_answer_structure.py`, `test_answer_quality.py`, `core/test_graph.py`, `test_listing_one_row_per_record.py` (every file that calls `record_label`, `plain_record_label` or `record_status_or_year`, plus a neighbour): `490 passed in 28.54s`.
- `ruff check` on both changed Python files: `All checks passed!`. `isort --check-only`: exit 0.

### Mutations, one property each, restored after each (`git status --short` clean)

| Mutation | Result |
|---|---|
| Significance column for every row type (drop `row_type == entity_type`) | 1 failed, 12 passed |
| Remove the `TABLE_COLUMNS` entry (no Gene column) | 2 failed, 11 passed |
| Plain label returns the rs id | 2 failed, 11 passed |
| Label not read from `rsid` | 3 failed, 10 passed |
| Significance cut at 20 characters | 2 failed, 11 passed |
| Drop the URL guard in `_row_type_label` | 13 passed (V-37-05) |
| Plain suffix loop ignores the row type | 13 passed; unreachable, the branch is already gated on `Variant record` by `_row_type_label` |
| Real dbSNP builder puts `rsid` first (`core/graph.py`) | 13 passed, and `test_layer_handoff.py` 28 passed (V-37-04) |

### The writer's input and the trust verdict, both trees

`<scratchpad>/card37a1_ver/probe_pages.py` runs `write_node` with a faked writer over 17 row shapes (rs334; no genes; "HBB, HBD"; "HBB,HBD"; no rsid; significance as a list; significance withheld; rs id only; dbSNP plus LitVar2 on the same page and on its own page; two dbSNP rows, one without a gene; PubTator3 entity plus publication; LitVar2 alone; Layer 2 `gene`; Layer 2 `clinvar`; graph `SequenceVariant` with a condition fold; a trial), at Researcher, Plain language and `clinical_brief`, with a writer reply that grounds nothing and one that echoes the prompt lines, plus rs334 on the command line and MCP surfaces: 106 pages per tree, no crash on either.

- Writer prompt: identical on all 106 (`prompt differs: []`).
- Every non token event (citation, trust_signal, step, cost, done, error) identical once the wall clock `call_elapsed_s` is dropped (`non-token events differ after dropping timings: []`). rs334's verdict on both: claim `ask`, `high`; answer `ask`, `high`.
- Tokens identical on 50 pages: every PubTator3, LitVar2 alone, Layer 2 `gene`, ClinVar, graph `SequenceVariant` and trial page, and the significance list page.
- Tokens differ only on pages holding a `Variant record` row.

### Edge shapes, branch against develop (Researcher cells unless named)

| Shape | Develop | Branch |
|---|---|---|
| rs334 | `[SIG, 'rs334']` | `['rs334', 'rs334', 'HBB', SIG]`, header `Variant, Identifier, Gene, Clinical significance`, four cells |
| No `genes` | `[SIG, 'rs334']` | `['rs334', 'rs334', SIG]`; Plain "Genetic variant" |
| "HBB, HBD" (the builder's own join) | `[SIG, 'rs334']` | `['rs334', 'rs334', 'HBB, HBD', SIG]`; Plain "Genetic variant (HBB, HBD)" |
| No `rsid` | list item `[SIG]` | table `[SIG, 'HBB', SIG]`, the list twice; unreachable live, since a dbSNP row with no rs id has no `source_url` (`tools/ncbi_dbsnp.py:1406`) and is dropped (`core/graph.py:5028`) |
| Significance a list | refusal page | the same refusal page; the builder always joins to a string (`core/graph.py:5034`) |
| Significance withheld | `['missense variant', 'rs334']` | `['rs334', 'rs334', 'HBB']` (V-37-01) |
| Two dbSNP rows, one with no gene | `[SIG, 'rs334']`, `['benign', 'rs7412']` | `['rs334', 'rs334', SIG]`, `['rs7412', 'rs7412', 'benign']`: the Gene column drops for both, as every mapping column does when one row has none |

SIG is "not-provided, protective, likely-benign, pathogenic, other".

- Opening sentence (no written answer): develop "Found 1 variant record record: not-provided, protective, likely-benign, pathogenic, other [1].", branch "Found 1 variant record record: rs334 [1]." The doubled noun is develop's (card 121).
- "Clinical significance" pre-empts `_STATUS_FIELDS` only for `Variant record`, `<scratchpad>/card37a1_ver/probe_status.py`, both trees identical except: `Variant record` with `clinical_significance` and `overall_status` gives `('Status', 'X')` on develop and `('Clinical significance', 'pathogenic')` on the branch. A trial, a LitVar2 row, a ClinVar row, an Assembly row and a lower case `variant record` type with the same field give the same result on both.
- Four cell cap: `cells` is `max_length=4`, each cell 500 (`contracts/events.py:428`). The widest branch row is four cells; the rs334 test asserts it.
- Surfaces: the web screen and the saved answer render `cells` (`AnswerScreen.tsx:532` to `:538`, `savedAnswerMarkdown.tsx`); the command line and MCP print `text` (`adapters/cli/render.py:876` onward, `adapters/mcp/server.py:1270`), which the branch does not change, so there only the opening sentence moves. No frontend code keys on a column label.
- `record_labels_by_page` (grounding) reads finding fields, not `record_label`, so no grounding or restatement check sees the new label (`synthesis/grounding.py:2080`).

## Live runs

Three runs on the branch through `core.run.run_streaming()`, web surface, placement on, `CLASSIFIER_PROVIDER=jev`, guard and plan models as in card 115's adversary run (line 99 of its report), writer from the local settings, `PER_QUERY_COST_CAP_USD=0.25`, session ids `card37a1-ver-q23-researcher`, `card37a1-ver-q23-plain`, `card37a1-ver-rs1-control`. Spend 0.0043 + 0.0032 + 0.0086 = 0.016 USD. Times 8.2 s, 8.0 s, 9.2 s. Session memory and interaction capture logged `CallerIdentityRequired` because the script passes no caller; the answer path is unaffected. Script `<scratchpad>/card37a1_ver/live.py`.

Query 23, Researcher (writer sentence survived):

```
claim   'Found 1 literature variant record for rs334: c.20A>T [2]. '
claim   'The variant is also identified in the literature by the name c.20A>T [2]. '
heading 'Variant record records found'
header  ['Variant', 'Identifier', 'Gene', 'Clinical significance']
row     ['rs334', 'rs334', 'HBB', 'not-provided, protective, likely-benign, pathogenic, other']
trust line: "Based on 1 source cited, not yet confirmed" (outcome ask); claim [1] dbsnp ask high, claim [2] litvar2 answer low
```

Query 23, Plain language (no written answer fallback):

```
claim   'I found 1 genetic variant related to rs334 [1]. '
heading 'Where this answer comes from'
item    ['Genetic variant (HBB)']
note    'Note: no written summary could be checked against the records, so the records found are listed below with their sources'
note    'This is a research summary, not medical advice.'
trust line: "Based on 1 source cited, not yet confirmed" (outcome ask); claim [1] dbsnp ask high
```

Control, "What does the RS1 gene do?", Researcher: Gene rows `['retinoschisin 1', 'NCBIGene:6247']`, `['RS1', 'NCBIGene:6247']`; PubMed rows title plus PMID; ClinVar rows `['NM_000330.4(RS1):c.78+2T>C', 'VCV001723073']` and four more; OMIM rows; trial rows with a Status column (`COMPLETED`). No Clinical significance or Gene column appears on any of them. Trust line "Sources disagree on at least one claim" (outcome flag), from two claim-level flags, a path the offline probe shows byte identical on both trees.

The opening sentence naming the LitVar2 record and "1 source cited" for two citations on one page are develop behaviour this branch does not touch (the trust and citation events are identical in the offline probe).

## Verdict

What the branch gets right, with evidence: rs334 is called rs334 on the web screen and the saved answer, and in the opening sentence on the command line and MCP (which print the unchanged row sentence); its Researcher row shows HBB and the significance values in a column of their own, four cells; the writer's prompt, the citations and every trust signal are byte identical to develop over 106 pages; every other row type renders exactly as on develop.

What is worse than develop: V-37-01. For a dbSNP record whose significance dbSNP's tool withholds (7 of the first 12 well known rs ids fetched, including rs6025, rs1801133, rs429358 and rs80359198), the record's one cited fact, its functional consequence, leaves the listing, and in the no written answer fallback it leaves the screen. It is one more row in the slice's own closed table plus a test, inside the fence.

VERDICT: FIX FIRST
