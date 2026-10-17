# Card 105 fresh verifier report, second attempt

Fresh verifier of the second attempt. Pull request #268, branch `fix/card105-window-r2`: develop `655e9dfe`, a merge `4e073a38` of the closed #260's commits `4e6c44b9`, `952a7ea9`, `26e23632`, and one new commit `96444af3`. Read in a detached worktree at `96444af3` (`<worktrees>/card105r-ver`), compared with `origin/develop` at `655e9dfe`. Paths are under `src/system_03_search_agent/` unless written in full; line numbers are the branch's. Probes and their output are in `<scratchpad>/card105r_ver/`. There is no fix round: anything worse than develop closes the card again.

## Table of contents

- [What the branch changes](#what-the-branch-changes)
- [Findings](#findings)
- [Hunt 1, the gene the line names](#hunt-1-the-gene-the-line-names)
- [Hunt 2, the marker in layer3_raw_outputs](#hunt-2-the-marker-in-layer3_raw_outputs)
- [Hunt 3, the second sentence](#hunt-3-the-second-sentence)
- [Earlier classes, re-checked](#earlier-classes-re-checked)
- [Tests and gates](#tests-and-gates)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## What the branch changes

`git diff --stat origin/develop...HEAD`: `core/graph.py` 149 lines, `test_bare_topic_clarification.py` 265, `test_window_graph_papers.py` 274. No other source file. In `core/graph.py`:

| Change | Where |
|---|---|
| `_PlannedToolCall.undated_papers_left_out`, default False | `:4779` |
| Plan sets it on `planned_tool_calls[0]` only when `publication_window is not None` and the plan holds a `pubmed_search` | `:7375` to `:7380` |
| `_without_article_rows` | `:7648` |
| Act filters when the flag is set, records `undated_articles_dropped` on `_CallOutcome` | `:8678` to `:8682`, `:8737` |
| Act writes `True` into `layer3_raw_outputs` under `<call_id>:undated-articles-dropped` | `:9147` to `:9148` |
| `_window_no_papers_line`, note and refusal wrappers | `:10089` to `:10159` |
| `_answer_call_ids` adds the windowed abstracts call when the flag is set | `:12888` to `:12896` |
| The refusal's `none_linked` slot and the notes tuple take the line | `:15316`, `:15355` |

## Findings

Written as each is established.

### V-105-04, minor (instrument): no test holds the line naming the first gene when two genes are typed

- Evidence: mutation "searched gene taken as the last gene" (`core/graph.py:10117`, `_first_gene_curie(list(reversed(...)))`) leaves both card files green, `73 passed in 16.48s` (`<scratchpad>/card105r_ver/mutations.txt`). The rs id and PMID tests have one gene each, so they cannot tell first from last.
- The behaviour is right today. Probe H1d, "recent papers on TP53 and BRCA1" with TP53 resolved first: the windowed ESearch term is `TP53[Title/Abstract] AND ("2025/10/17"[dp] : "3000"[dp])` and the line reads "No PubMed papers from the last 12 months were found for TP53. ...". The line and the plan read the gene through the same `_first_gene_curie` over the same `target_entities` (`:7291` and `:10117`), so they agree by construction.
- Worse than develop: no.

### V-105-03, still open from the first attempt, minor: the flag also reaches a disease-anchored question

- Re-derived on `96444af3`. Probe H4, "recent work on MedGen:C0010674", 5 years picked, the graph returns a CFTR Gene row (disease templates hop only to genes, so there is no Article row to drop).
  ```
  branch, PubMed none:  'Found 1 gene record for MedGen:C0010674: CFTR [1]. '  note: 'No PubMed papers from the last 5 years were found.'  answer
  develop, PubMed none: 'Found 1 gene record for MedGen:C0010674: CFTR [1]. '  (no note)  answer
  branch, PubMed one:   'Found 1 pubmed record and 1 gene record for MedGen:C0010674: ...'  PubMed table first
  develop, PubMed one:  'Found 1 gene record for MedGen:C0010674: CFTR [1]. '  PubMed table second
  ```
- What changed for this person: the windowed papers lead and are counted, and an empty window is said in one true sentence. With `searched_curie` None (`:10117`) and no abstracts `gene_symbol`, the line names no subject rather than the MedGen id it named on `26e23632`; the second sentence is absent because nothing was dropped. No record is lost and no wrong subject is named.
- Worse than develop: no. The owner's decision speaks of "a "How far back" window is picked", not only of gene questions.

No other finding. Every hunt below held.

## Hunt 1, the gene the line names

The newest commit reads the gene through `_first_gene_curie(graph_call.cypher_input.target_entities)` (`:10117`), the same function and the same list the plan uses to pick the search symbol (`:7291`, then `_mention_by_curie` at `:7306` to `:7310`). The text comes from Think's resolved entity for that CURIE, which is the same string `_mention_by_curie` holds, so the line names exactly the gene the windowed ESearch searched, written as the count line writes it (`answer_mentions`, `:14337`).

Probes run through the real five-node graph with the card's own stubs (`<scratchpad>/card105r_ver/test_probe_r2.py`, output `out_card105r-ver.txt` and `out_card105r-ver-dev.txt`). Every windowed PubMed term searched only the gene named in the line.

| Probe | Windowed ESearch term | The line or refusal on the branch | Develop |
|---|---|---|---|
| H1a, "recent papers on rs80357906 in BRCA1", 12 months, Gene row | `BRCA1[Title/Abstract] AND (...)` | note: "No PubMed papers from the last 12 months were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here." | 2 graph papers and the gene, `ask` |
| H1b, same, Articles only | same | refusal: "No PubMed papers from the last 12 months were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here. Pick a longer window, or ask without one. https://www.ncbi.nlm.nih.gov/search/all/?term=dbSNP%3Ars80357906%20NCBIGene%3A672" | 2 graph papers, `ask` |
| H1c and H1c2, "recent papers like PMID:12345678 on BRCA1" | `BRCA1[...]` | "... were found for BRCA1. ..." in the note and in the refusal | 2 graph papers |
| H1d, "recent papers on TP53 and BRCA1", TP53 resolved first | `TP53[...]` | "... were found for TP53. ..." | 2 graph papers |
| H1d2, "recent papers on BRCA1 and TP53", Articles only | `BRCA1[...]` | refusal "... were found for BRCA1. ..." | 2 graph papers |
| H1e, "recent papers on NCBIGene:672 BRCA1", Articles only | none planned | no line, no flag: "Found 2 article records for NCBIGene:672, of 3487 available: PMID:10026184 [1] and PMID:10417300 [2]." | identical |
| H1e2, "recent papers on BRCA1 (NCBIGene:672)" | none planned | no line; graph papers and gene kept | identical |
| H1f, "C9orf43" | `C9ORF43[...]` | "... were found for C9orf43. ...", count line "for C9orf43" | 2 graph papers |
| H1g, "c9orf43" typed lower case | `C9ORF43[...]` | "... were found for c9orf43. ...", count line "for c9orf43" | count line "for c9orf43" |
| H1h, "C9ORF43" typed upper case, Articles only | `C9ORF43[...]` | refusal "... were found for C9ORF43. ..." | count line "for C9ORF43" |

Why the typed CURIE with a symbol takes no flag: an exact identifier is laid down first and `confirmed_new` drops a model-confirmed symbol whose CURIE an exact match already holds (`:4579` to `:4585`), so the gene's only text is `NCBIGene:672`; it contains ":" so no symbol and no `pubmed_search` is planned (`:7309`), and the setter's `any(... "pubmed_search" ...)` is false (`:7375`).

Mutations: "lookup back to any resolved target" turns `test_an_rs_id_typed_before_the_gene_does_not_become_the_searched_gene` and `test_a_pmid_typed_before_the_gene_does_not_become_the_searched_gene` red. The two-gene order has no test (V-105-04).

The count line on a windowed rs question reads "Found 4 pubmed records for rs80357906 and BRCA1" (live run 3). That joins every typed mention, as develop's count line does over graph papers ("Found 2 article records and 1 gene record for rs80357906 and BRCA1", probe H1a on develop). Pre-existing wording, not made worse.

## Hunt 2, the marker in layer3_raw_outputs

Every reader of `layer3_raw_outputs` in `src/` and `services/` (`grep -rn layer3_raw_outputs`):

| Reader | How it reads | Can it meet the marker |
|---|---|---|
| Act, `:9137` to `:9148`, returns it at `:9229` | writes | it is the writer |
| `_window_no_papers_line`, `:10137` | `.get(graph call id + suffix)` | the one intended reader |
| `_isolate_count_note`, `:10176` | `.values()`, then `isinstance(output, PathogenDetectionOutput)` | a `True` value fails the type check and is skipped |
| `_citations_from_grounded_claims`, `:11493` and `:11544`, through `_layer3_row_for_synth_finding` `:12561` | `.get(finding.call_id)` | no: every call id is `<prefix>-<12 hex>` (`:5210`, `:5407`, `:5525`, `:5550`, `:6439`, `:6809`) or `<id>-articles` (`:8705`); none ends with `:undated-articles-dropped` |
| `_write_answer`, `:13940`, passed to the two citation builds `:14363`, `:14982` | same `.get` path | no, as above |
| `core/state.py:253` | type declaration only | no |

Nothing else reads the state. `core/run.py` hands every surface the event stream only (`run_streaming` yields `partial_state["events"]` and custom events, `core/run.py:918` to `:945`), and memory is built from the events (`_remember_turn(query, seen_events)`). The web adapter, the command line, MCP and GraphQL all go through `core/run_registry.py:628` `run_streaming(...)`; GraphQL's fold never calls it directly. `done.total_tool_calls` is `state["findings_count"]` (`:13935`), not a count over the raw outputs. The tracer would see a boolean under a call id key, developer side only.

Proven on the events: each of the 29 probes (windowed and unwindowed, answer and refusal) dumps every event payload as JSON and searches it for `undated-articles-dropped` and `undated_articles`: `marker in any event: False` on all 29. The citation count on every probe equals the records listed (for example H3d: 2 citations, the PubMed paper and the gene).

## Hunt 3, the second sentence

| Probe | Rows dropped | The line |
|---|---|---|
| H3a, the graph returns nothing on its own, 12 months, PubMed none | none | refusal: "No PubMed papers from the last 12 months were found for BRCA1. Pick a longer window, or ask without one. https://www.ncbi.nlm.nih.gov/search/all/?term=NCBIGene%3A672". Develop: "I could not find grounded evidence for this. Try NCBI's cross-database search: ..." Both `refuse` |
| H3b, a variants result, no Article row, 5 years, PubMed none | none | note: "No PubMed papers from the last 5 years were found for BRCA1." Card 30's line above it, identical to develop |
| H3c, Articles and a Gene row, 5 years, PubMed none | 2 | "No PubMed papers from the last 5 years were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here." |
| H3d, papers found | 2 | no line; "Found 1 pubmed record and 1 gene record for BRCA1: BRCA1 and a recent finding [1] and BRCA1 DNA repair associated [2]." |

The record is set only when `_without_article_rows` returned a new object (`:8681`); it returns the same object when nothing was removed (`:7660` `if len(kept) == len(output.rows): return output`). Mutations: sentence always added, red (`test_the_second_sentence_shows_only_when_graph_papers_were_left_out`); Act records always, red (`test_act_records_the_left_out_papers_only_when_articles_were_removed`); Act never records, red (`test_a_picked_window_with_no_papers_in_it_says_so`); the line reads the bare call id, 2 red. V-105-02 is closed.

## Earlier classes, re-checked

| Class | Result | Evidence |
|---|---|---|
| An unpicked question is byte-identical to develop | Holds | Seven unpicked probes plus a typed follow-up: "recent papers on BRCA1 from the last 5 years?" typed (Articles only), the same with 12 months, "which papers mention BRCA1?", "recent papers on rs80357906 in BRCA1", "recent papers on BRCA1 variants", "papers on coffee and exercise", "recent papers on NCBIGene:672". Every event payload, normalised only for random call ids and timings, is identical on both trees: `diff` exit 0 over 405 lines (`u_card105r-ver.txt`, `u_card105r-ver-dev.txt`). The 245 raw lines that differ are call ids only |
| No call added, so nothing slower | Holds | Plan narratives and PubMed terms identical on all 25 first probes; `tool_start` counts per tool identical on both trees |
| A failed or timed out search is never "none found" | Holds | H3e (search `error`, Articles only): "One of my searches did not finish, so I could not find grounded evidence this time. Ask again to retry, ..."; H3f (error, Gene row): "The background search of PubMed did not finish, ..." and `ask`; H3g (search hangs past a 0.5 s budget): the same "did not finish" refusal, and with a Gene row "The background search of NCBI records did not finish because it took too long, ..." and `ask`. No "No PubMed papers" on any. Mutation removing the `error` guard: red |
| A typed follow-up takes no flag | Holds | Probe "U typed follow-up after a picked answer": "which papers mention BRCA1?" after a picked answer lists "Found 2 article records and 1 gene record for BRCA1, of 3487 available", as develop |
| A topic question takes no flag | Holds | The setter is in the final `else` after `elif topic_term is not None` (`:7212`); "papers on coffee and exercise" identical to develop |
| A disease question | Takes the flag, not worse | V-105-03 above |
| The refusal says what to type next | Holds | "Pick a longer window, or ask without one." plus develop's cross-database link, H1b, H1c2, H1d2, H1h, H3a |
| Card 30's line unchanged | Holds | H3b: "ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, ..." on both trees; `synthesis/answer_layout.py` is not in the diff |
| Slice A1's rows unchanged | Holds | `answer_layout.py` untouched; the filter touches only `cypher_query` results, never a dbSNP `Variant record`. Live run 3 lists "Variant record clinical_significance: pathogenic, risk-factor, uncertain-significance [6]" under "Variant record records found" |
| Earlier mutations still red | Holds | A-105-01, A-105-02, A-105-04, J-105-03, Act ignores the flag (6 red), Plan never sets the flag (3 red). `restored: True`, `git status --short` empty |

Two answers the branch turns from `ask` into `refuse` (H3e and H3g with Articles only, the adversary's A2 class) lose only graph Article rows on a picked window, the loss the owner's decision names; the refusal is honest about the failed search.

## Tests and gates

| Run | Result |
|---|---|
| The two card files and the 16 other files under `tests/system_03_search_agent/core/` naming `publication_window`, `_answer_call_ids`, `_PlannedToolCall`, `_execute_planned_call`, `refusal_message_for` or `layer3_raw_outputs`, 18 files | `686 passed in 39.84s` |
| Gate 3, `ruff check` with no path, from the worktree root | `All checks passed!` |
| Gate 2, `isort --check-only --diff src tests services tracker alembic .claude .github` | `Skipped 2 files`, exit 0 |
| Mutations, one at a time on `core/graph.py`, the two card files | 11 of 12 red; the green one is V-105-04. `<scratchpad>/card105r_ver/mutations.txt` |
| CI on #268, head `96444af36921d3ecf482e7d638dfee86cb24c41c` | Python gates (1, 2, 3, 4, 6, 9) SUCCESS; Integration suite (5) SUCCESS; Frontend gates (7, 8) SUCCESS; Accessibility (10) SUCCESS |

## Live runs

Branch tree, `core.run.run_streaming()`, `CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`, synth model from the local env, session ids `card105r-ver-<scenario>-<hex>`. A pick is the ask and then a click on the offered option in the same session and owner. Full output: `<scratchpad>/card105r_ver/live_branch.txt`. Four runs, seven `run_streaming` calls, spend $0.071 (sum of `done.total_cost_usd`).

| Run | Question then click | What it lists | Line or refusal | Trust line | Time |
|---|---|---|---|---|---|
| 1 | "recent papers on BRCA1", then "Recent papers on BRCA1 from the last 5 years?" | "Found 4 pubmed records for BRCA1: BRCA1: An Endocrine and Metabolic Regulator. [1], EXO1 protects BRCA1-deficient cells against toxic DNA lesions. [2], BRCA1, BRCA2, and Associated Cancer Risks and Management for Male Patients: A Review. [3] and BRCA1 and BRCA2: from cancer susceptibility to synthetic lethality. [4]."; then gene, 5 ClinVar, OMIM, 5 trials, PMID 20301425; no 1999 paper, no "of 3487" | none (papers found) | "Based on 17 sources cited", answer | 19.2 s |
| 2 | "recent papers on C9orf43", then "Recent papers on C9orf43 from the last 12 months?" | "Found 1 gene record and 5 clinvar records for C9orf43: C9orf43 [1], NM_001278629.2(C9orf43):c.293C>T (p.Pro98Leu) [2], ..." | "No PubMed papers from the last 12 months were found for C9orf43. Papers in the knowledge graph carry no publication date, so they are not listed here." (develop listed 16 graph papers here, so rows were dropped) | "Based on 6 sources cited", answer | 31.1 s |
| 3 | "recent papers on rs80357906 in BRCA1", then "Recent papers on rs80357906 in BRCA1 from the last 12 months?" | "Found 4 pubmed records for rs80357906 and BRCA1: HSP90 buffers deleterious genetic variations in BRCA1. [1], Integrated Spatial Analysis Reveals the Molecular Landscape of Ovarian Precancerous Lesions. [2], IFI16 senses and protects stalled replication forks. [3] and Focus on BRCA1 and BRCA2. [4]."; gene, the dbSNP record, 5 ClinVar, OMIM, 5 trials, PMID 20301425 | none (papers found); note "The background search of the knowledge graph did not finish, so this answer may be missing sources from it. Ask again to retry." | "Based on 18 sources cited, not yet confirmed", ask | 13.0 s |
| 4, control | "recent papers on BRCA1 from the last 5 years?" typed in a new session, no offer | "Found 40 article records for BRCA1, of 3487 available", then gene, PubMed, ClinVar, OMIM, trials; plan line "the date range in your question could not be applied, so papers from any year were searched"; "no written summary could be checked" note | none | "Based on 57 sources cited, not yet confirmed", ask | 58.3 s |

On the times:

- Run 4 is the unpicked path, which the stubbed probes show runs develop's code event for event; its synth call alone took 20.5 s (`cost` event `call_elapsed_s`), against 14.6 s and 17.3 s for the same control in the two earlier rounds. Live model and NCBI latency, not the branch.
- Run 2's 31.1 s: synth 5.5 s, the guard call on the ask 6.3 s; the branch plans the same calls as develop (probe plans identical) and its only new work in the newest commit is one dict write and one dict read. Earlier rounds measured this question at 12.1 s (branch) and 12.0 s (develop).
- Run 3's failed graph call (`cq-e405c62b706f`, `status: error`) is not the filter's doing: `_without_article_rows` returns an error result with no rows unchanged (`:7659` to `:7661`), and the failure note is develop's own.
- The brief's run budget allowed no develop rerun to pair these times, so speed rests on the code evidence: no call added on any path.

## Verdict

Nothing on this branch shows any person something worse than develop:

- The empty-window line and the refusal name the gene the windowed search searched, for an rs id or a PMID typed first, two genes, a CURIE with a symbol (no flag at all) and every case of C9orf43.
- The marker never leaves the state: no event, count, citation, saved answer or memory row reads it.
- The second sentence shows only when graph Article rows were removed.
- Unpicked questions, typed follow-ups and topic questions match develop event for event; no call is added; failed and timed out searches never say "none found"; card 30's line and slice A1's rows are unchanged; the 18 files pass, both lint gates are clean and CI is green on `96444af3`.

V-105-04 (an untested two-gene order) and V-105-03 (the flag reaches disease questions, with true copy and no lost record) are minor and not worse than develop.

VERDICT: PASS
