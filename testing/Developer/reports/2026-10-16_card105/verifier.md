# Card 105 fresh verifier report

Fresh verifier after the one fix round. Pull request #260, branch `fix/card105-window-leaves-undated-papers-out`: build commits `4e6c44b9` and `952a7ea9`, fix commit `26e23632`, on develop `78c68c1c`. Read in a detached worktree at `26e23632`, compared with `origin/develop`. Paths are under `src/system_03_search_agent/` unless written in full; line numbers are the branch's. Probes and their output are in `<scratchpad>/card105_ver/`.

## Table of contents

- [Tests and gates run](#tests-and-gates-run)
- [Earlier findings, re-derived](#earlier-findings-re-derived)
- [The new refusal path, re-tested](#the-new-refusal-path-re-tested)
- [Where the flag can reach](#where-the-flag-can-reach)
- [Live runs](#live-runs)
- [Findings](#findings)
- [Verdict](#verdict)

## Tests and gates run

| Run | Result |
|---|---|
| The two card files and every file under `tests/system_03_search_agent/core/` naming `publication_window`, `_answer_call_ids`, `_PlannedToolCall`, `_execute_planned_call` or `refusal_message_for`, 18 files | `669 passed in 47.59s` |
| `ruff check` with no path, from the worktree root | `All checks passed!` |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | `Skipped 2 files`, exit 0 |

## Earlier findings, re-derived

Each mutation below changes one property in `core/graph.py`, runs the two card files, and restores the file (`<scratchpad>/card105_ver/mutate.py`, which checks the anchor occurs exactly once and prints `restored: True`). Unmutated, the two files give 63 passed.

| Finding | Closed in code | Mutation | Result |
|---|---|---|---|
| A-105-01 | Yes. The setter (`:7314` to `:7319`) needs a picked window and a planned `pubmed_search`; in this branch every such search is windowed (`breadth_plan.py:751` to `:753`; `_build_layer_tool_calls` plans none). Live run 3 keeps develop's 57 graph papers | Set the flag whenever a window is picked | red: `test_a_picked_window_on_a_gene_typed_as_a_curie_keeps_the_graph_papers` |
| A-105-02 | Yes. `refusal_message_for`'s `none_linked` slot (`:15197`) takes the line plus "Pick a longer window, or ask without one."; `refusal_message_for` still returns a failure message before `none_linked` (`synthesis/refuse.py:229` to `:236`); the diff touches no file under `contracts/` | Drop the slot argument | red: `test_a_refusal_the_left_out_papers_caused_says_what_happened_and_what_to_type` |
| A-105-02, next step | Yes | Return the line without the next step | red: the same test |
| A-105-03 | The case matches the count line (live run 2: "for C9orf43" in both), but the new lookup names the wrong entity when an identifier is typed first: V-105-01 | Skip the resolved-entity lookup | red: `test_the_line_writes_the_symbol_as_the_count_line_does` |
| A-105-04, J-105-02 | Yes | Remove `output.status == "error"` from `:10034` | red: `test_a_failed_windowed_search_never_says_no_papers_were_found` |
| J-105-03 | Yes | Replace the flag lookup with any `_PlannedToolCall` | red: `test_the_line_needs_the_flag` |
| Act filter, as a control | Yes | Act ignores the flag | 5 red, including the A-105-02 refusal test |

## The new refusal path, re-tested

Probes P1 to P8 in `<scratchpad>/card105_ver/test_probe_ver.py`, run through the real five-node graph on both trees with the card's own stubs; output in `out_*.txt` and `out2_*.txt`.

| Earlier claim | Branch, refusal path | Verdict |
|---|---|---|
| Never "none found" over a failed search | P6, picked, PubMed search `error`, graph Articles only: "One of my searches did not finish, so I could not find grounded evidence this time. Ask again to retry, ..." | Holds |
| Never "none found" over a timed out search | P8, PubMed search hangs past a 0.5 s budget: the same "did not finish" refusal | Holds |
| Never names the wrong gene | P2: "No PubMed papers from the last 12 months were found for rs80357906. ..." when only BRCA1 was searched | Fails, V-105-01 |
| A refusal stays a refusal where develop refused | P7, graph empty on its own: `refuse` on both trees, the branch's text is the window line | Holds, with V-105-02's overclaim |
| Unpicked questions keep develop's refusal | The line returns None before any lookup when no planned call carries the flag (`:10023` to `:10024`), so the slot gets `X or None` | Holds |

Where develop answered from graph papers alone and the branch refuses (P6, P8, and the adversary's A2), the lost records are graph Article rows on a picked window, the loss the owner's decision names.

## Where the flag can reach

| Question | Can the flag be set | Evidence |
|---|---|---|
| No picked window, including the option's words typed | No | `publication_window is None` short-circuits the setter (`:7314`); one setter in `src/` (`grep undated_papers_left_out`: `:4718` default, `:7318` set, `:8613`, `:10023`, `:12802` read). Probe P5 prints the same answer on both trees: "Found 2 article records for BRCA1, of 3487 available: PMID:10026184 [1] and PMID:10417300 [2]." with the same truncation note and `answer`. Live run 4 lists 40 graph papers first, as develop |
| A typed follow-up after a picked answer | No | The plan is rebuilt per run and the window needs the whole text to equal a stored option (`core/clarify.py:356` to `:372`); the adversary's A7b shows the follow-up with develop's graph papers |
| A topic question | No | The topic branch (`:7151`) never reaches the setter |
| A disease-anchored question in the gene branch | Yes | V-105-03 |
| A gene typed as a CURIE | No | No symbol, no `pubmed_search` (`:7248`); live run 3 |

On an unpicked question every changed line is a false guard or `X or None`: the setter, `getattr(planned, "undated_papers_left_out", False)` in Act, the early None in `_window_no_papers_line`, and `any(...)` in `_answer_call_ids`. So the unpicked path runs develop's behaviour; no call is added on any path.

## Live runs

Branch tree, `core.run.run_streaming()`, `CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`, session ids `card105-ver-<scenario>-<hex>`. A pick is the ask and the click in one session and owner. Full output: `<scratchpad>/card105_ver/live_branch.txt`. Spend about $0.039 over the four runs (seven `run_streaming` calls).

| Run | Question then click | What it lists | Line or refusal | Trust line | Time |
|---|---|---|---|---|---|
| 1 | "recent papers on BRCA1", then "Recent papers on BRCA1 from the last 5 years?" | "Found 4 pubmed records for BRCA1: BRCA1: An Endocrine and Metabolic Regulator. [1], Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis. [2], EXO1 protects BRCA1-deficient cells against toxic DNA lesions. [3] and BRCA1 and BRCA2: from cancer susceptibility to synthetic lethality. [4]."; then gene, 5 ClinVar, OMIM, 5 trials, PMID 20301425; no 1999 paper, no "of 3487" | none (papers found) | "Based on 17 sources cited", answer | 18.1 s |
| 2 | "recent papers on C9orf43", then "... from the last 12 months?" | "Found 1 gene record and 5 clinvar records for C9orf43: C9orf43 [1], ..." | "No PubMed papers from the last 12 months were found for C9orf43. Papers in the knowledge graph carry no publication date, so they are not listed here." | "Based on 6 sources cited", answer | 12.1 s |
| 3 | "recent papers on NCBIGene:672", then "... from the last 5 years?" | "Found 57 article records for NCBIGene:672, of 3487 available", PMID:10026184 first, then the gene record; the plan line still says "PubMed papers published in the last 5 years only" with no PubMed search planned (develop's own wording, unchanged) | none | "Based on 58 sources cited, not yet confirmed", ask | 18.0 s |
| 4, control | "recent papers on BRCA1 from the last 5 years?" typed, no offer | "Found 40 article records for BRCA1, of 3487 available", PMID:10026184 first, then gene, 5 PubMed, ClinVar, OMIM, trials; plan line "the date range in your question could not be applied, so papers from any year were searched" | none | "Based on 57 sources cited, not yet confirmed", ask | 14.6 s |

Run 2's 12.1 s matches the adversary's develop run of the same question (12.0 s); run 1's 18.1 s compares with 34.9 s on develop in the diagnosis. Run 2 confirms A-105-03 live: the line and the count line both write "C9orf43".

## Findings

Written as each was established.

### V-105-01, major: the empty-window line names a typed rs id or PMID as the subject of a PubMed search that never ran for it

- Regression of: A-105-03. The fix commit `26e23632` replaced the searched symbol with the first entity Think resolved among the graph call's targets (`core/graph.py:10039` to `:10054`, in `_window_no_papers_line` at `:10013`). That lookup takes any resolved entity, not the gene that was searched. Think's list puts typed identifiers (rs ids, PMIDs, CURIEs) first (`core/graph.py:4524`, `resolved_entities = list(exact_matches)[:exact_budget]`), so when one is typed before the gene, the line names it. At `952a7ea9` the line read the `pubmed_abstracts` follow-up's `gene_symbol`, the gene actually searched.
- What was searched: only the gene. `plan_first_stage` builds the PubMed term from the gene symbol alone (`core/breadth_plan.py:718` to `:753`), the plan line confirms "searching 3 layers for NCBIGene:672 ... PubMed papers published in the last 12 months only".
- Reproduction: `<scratchpad>/card105_ver/test_probe_ver.py`, through the real five-node graph with the card's own stubs, "recent papers on rs80357906 in BRCA1", the ask-back's "from the last 12 months" option clicked, the windowed PubMed search finds nothing. Branch, pasted from `out_card105-ver.txt`:
  ```
  P1 (graph has the Gene row):
  token[claim]: 'Found 1 gene record for rs80357906 and BRCA1: BRCA1 DNA repair associated [1]. '
  token[note]: 'No PubMed papers from the last 12 months were found for rs80357906. Papers in the knowledge graph carry no publication date, so they are not listed here.'
  P2 (graph returns Articles only, the real template's shape):
  token: 'No PubMed papers from the last 12 months were found for rs80357906. Papers in the knowledge graph carry no publication date, so they are not listed here. Pick a longer window, or ask without one. https://www.ncbi.nlm.nih.gov/search/all/?term=dbSNP%3Ars80357906%20NCBIGene%3A672'
  trust_signal: outcome=refuse
  P3, "recent papers like PMID:12345678 on BRCA1":
  token[note]: 'No PubMed papers from the last 12 months were found for PMID:12345678. ...'
  ```
  Develop, same probes (`out_card105-ver-dev.txt`): no such sentence; the graph papers and the gene record are listed under `answer` or `ask`.
- What the person reads: a plain statement that PubMed has no recent papers on the variant they typed, when no search for that variant was made. A researcher could drop a variant from a literature review on the strength of it. That is a confident wrong statement, the class the brief names ("never names the wrong gene").
- Reach: a picked window, a typed rs id, PMID or other identifier ahead of the gene, and a windowed gene search with no hits (a rarely studied gene, or the 12 month window). Rare, but every part is ordinary input for this product's users.
- Worse than develop: yes. Develop shows no sentence there; the branch adds a false one, on the answer path and in the refusal.
- Fixable inside the fence in one round: yes. Restrict the lookup to the gene CURIE the search was planned from (`_first_gene_curie(graph_call.cypher_input.target_entities)`), with the follow-up's symbol as the fallback, and add a test with an rs id typed first.

### V-105-02, minor: the line's second sentence says graph papers were left out where none were

- Evidence: probe P7, a picked 12 month window where the graph itself returns nothing (not the filter) and PubMed finds nothing. Branch: `'No PubMed papers from the last 12 months were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here. Pick a longer window, or ask without one. https://www.ncbi.nlm.nih.gov/search/all/?term=NCBIGene%3A672'`, `refuse`. Develop: `"I could not find grounded evidence for this. Try NCBI's cross-database search: ..."`, `refuse`. The adversary's A6 (variants shape, PubMed none) shows the same sentence under twelve variants, where no Article row existed. `_window_no_papers_line` (`core/graph.py:10013`) checks the flag, never whether `_without_article_rows` removed a row.
- What the person reads: that the graph holds papers being hidden from them, and "ask without one", which on P7 refuses again.
- Worse than develop: no. The refusal stays a refusal where develop refused, its first sentence is true, and a longer window can find papers. It is an overclaim in new copy.

### V-105-03, minor: the flag also reaches a disease-anchored question

- Evidence: the setter sits in `plan_node`'s final `else` branch (`core/graph.py:7314` to `:7319`), which also plans a disease anchor when no gene resolved and the literature decision is not "wants literature"; `_build_breadth_calls` then plans the windowed PubMed search on the MedGen title (`core/graph.py:5417` to `:5423`), so the condition holds. Probe P4, "recent work on MedGen:C0010674", 5 years picked, PubMed none: branch adds `'No PubMed papers from the last 5 years were found for MedGen:C0010674. Papers in the knowledge graph carry no publication date, so they are not listed here.'` and `answer`, develop has no such line. Present since the build commit, not new in the fix.
- What it changes for a real disease question: the disease templates hop only to genes (`tools/cypher_templates.py:269`), so no row is lost; the windowed PubMed papers join the answer through `_answer_call_ids`, which the owner's decision asks for; and V-105-02's sentence can appear.
- Worse than develop: no record lost, no wrong subject (the line names the entity the title search was planned from). Reported so the lead knows the fence is wider than "gene path only".

## Verdict

What holds: every earlier finding's test goes red under its own mutation; a failed or timed out search never gets the "none found" line; no question without a picked window, no typed follow-up and no topic question takes a changed line; nothing is slower; the 18 files pass and both lint gates are clean.

What does not: V-105-01. The fix for A-105-03 made the new line name whichever entity Think resolved first, so a typed rs id or PMID ahead of the gene becomes the subject of "No PubMed papers ... were found for rs80357906", on the answer path and in the new refusal, when only the gene was searched. Develop shows no such sentence. It sits inside the fix round's own code (Review_rounds.md, Rule 4), and it is fixable inside the fence in one change: read the text for the gene CURIE the search was planned from (`_first_gene_curie`), falling back to the follow-up's symbol, with a test that types an rs id first. The review budget has no further round, so the lead decides between closing the pull request and naming the item.

V-105-02 and V-105-03 are minor and not worse than develop.

VERDICT: FIX FIRST
