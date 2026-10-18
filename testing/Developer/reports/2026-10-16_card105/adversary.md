# Card 105 adversary report: a picked window leaves undated papers out

Adversary round on pull request #260, branch `fix/card105-window-leaves-undated-papers-out`, commits `4e6c44b9` and `952a7ea9` on develop `78c68c1c`. Worktree `<worktrees>/card105-adv` (detached at `952a7ea9`), compared with a detached develop worktree `<worktrees>/card105-adv-dev`. Probes in `<scratchpad>/card105_adv/`.

## Table of contents

- [Method](#method)
- [Findings](#findings)
- [Local probes, branch beside develop](#local-probes-branch-beside-develop)
- [Live runs](#live-runs)
- [What held](#what-held)
- [Verdict](#verdict)

## Method

- Read `diagnosis.md`, `build.md`, `git diff origin/develop...HEAD`, query 108 and PR-36-01.
- Local probe file `<scratchpad>/card105_adv/test_probe_card105.py`, run through the real five-node graph on both trees with the test module's own model and decision stubs. Its graph stub returns what the real `gene_articles_one` template returns: Article rows only (`tools/cypher_templates.py:268`, `RETURN x ORDER BY x.id` at `:614`). The builder's end-to-end stub adds a Gene row to the graph result, which the real template never returns.
- Outputs: `out_card105-adv.txt` and `out_card105-adv-dev.txt` (scenarios A1 to A8), `outG_*.txt` (with a live gene record), `outC_*.txt` (typed CURIE).

## Findings

Written as each was established.

### A-105-01: a picked window on a gene named only by its CURIE drops every paper and says nothing

- Severity: minor (rare input; worse than develop)
- Where: `core/graph.py:7212` sets `undated_papers_left_out` on every gene path graph call with a picked window, before and regardless of whether a `pubmed_search` was planned. A gene typed as a CURIE has no symbol (`plan_node` comment at `core/graph.py:7243`: "a gene named only as a typed CURIE has no symbol and plans no text search"), so no PubMed search exists. `_window_no_papers_note` then returns None at `if not searches: return None` (`core/graph.py:10018`, in the new function at `:10002`).
- Reproduction: `test_probe_typed_curie` in the probe file, "recent papers on NCBIGene:672", option "from the last 5 years" clicked, gene record live, graph returns three Article rows. Pasted from `outC_*.txt`:
  ```
  branch, plan: "... Layer 2, live NCBI records: ncbi_efetch; PubMed papers published in the last 5 years only"
  branch, answer: Found 1 gene record for NCBIGene:672: BRCA1 [1].   (no paper, no note)   trust answer
  develop, answer: Found 3 article records for NCBIGene:672, of 3487 available: PMID:10026184 [1], ...   trust answer
  ```
- What the person sees: they asked for recent papers and picked five years; the plan line says PubMed papers from the last 5 years were searched (a pre-existing develop claim, no search is planned on either tree), and the answer lists no paper and gives no reason. The lead's added rule, "when no PubMed paper inside the window was found, one plain line says so", is not met because no search ran at all.
- Worse than develop: yes. Develop showed graph papers (off window, the loss the owner accepted); the branch shows none and is silent about it, under a plan line that claims a search.
- Fixable inside the fence in one round: set the flag only when the plan holds a windowed `pubmed_search`, or let the note speak when no search was planned.

### A-105-02: when nothing but the graph's papers would have grounded the answer, a picked window turns an answer into a generic refusal and the "none found" line is never shown

- Severity: minor (needs the gene's own NCBI record to be empty or fail as well; worse than develop in that case)
- Where: the new line rides the `notes` tuple in `_write_answer` (`core/graph.py:15202`), which is reached only on the answer path. When the graph call becomes `empty` (`_without_article_rows`, real `gene_articles_one` returns Article rows only) and the windowed search found nothing, and no context call has a row, the trust outcome is `refuse` and the refusal text is the generic one.
- Reproduction: probe scenarios A2 and A7a (gene record stubbed empty), pasted from `out_card105-adv.txt`:
  ```
  branch A2 (12 months picked, PubMed empty):
    "I could not find grounded evidence for this. Try NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=NCBIGene%3A672"
    trust refuse
  develop A2: Found 3 article records for BRCA1, of 3487 available: PMID:10026184 [1], ...   trust answer
  ```
  With the gene record present (`outG_card105-adv.txt`) the branch is right:
  ```
  Found 1 gene record for BRCA1: BRCA1 [1].
  note: No PubMed papers from the last 12 months were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here.
  trust answer
  ```
- The builder's end-to-end tests do not reach this: `_install_gene_papers` returns a Gene row inside the graph result (`test_bare_topic_clarification.py`, the new helper), which the real hop template (`RETURN x`) never returns, so the graph call never goes empty in any card 105 test.
- Same shape when the PubMed search fails or times out with no gene record (A3, A4, A8): the branch refuses with "One of my searches did not finish, so I could not find grounded evidence this time. Ask again to retry"; develop shows the graph papers under `ask` with "The background search of PubMed did not finish". The branch's wording is honest, and with a gene record present both trees end at `ask` (outG, 'error').
- Worse than develop: yes, narrowly. Answer becomes refuse, and the refusal does not say that the window had no papers. Live, a resolved gene nearly always has its NCBI gene record, so this needs an NCBI Datasets failure as well.

### A-105-03: the new line names the gene in capitals, not by its symbol

- Severity: minor (copy; not worse than develop, the line is new)
- Where: `_window_no_papers_note` takes `gene_symbol` from the abstracts follow-up, which `plan_node` builds as `mention.strip().upper()` (`core/graph.py:7253`).
- Live evidence, branch, "Recent papers on C9orf43 from the last 12 months?" (picked):
  ```
  token[claim]: 'Found 1 gene record and 5 clinvar records for C9orf43: C9orf43 [1], ...'
  token[note]: 'No PubMed papers from the last 12 months were found for C9ORF43. Papers in the knowledge graph carry no publication date, so they are not listed here.'
  ```
- The count line and the record say C9orf43; the line says C9ORF43. Same gene, so not a wrong record, but a symbol written differently from the record it sits under. The same would happen to any mixed-case symbol (open reading frame genes, non-human genes).

### A-105-04: no test fails when the "the search failed" guard is removed from the new line

- Severity: minor (instrument; not worse than develop)
- Mutation, one property: in `_window_no_papers_note`, `if output is None or output.status == "error" or _search_ids(output):` changed to `if output is None or _search_ids(output):`. Result on the two card test files:
  ```
  57 passed in 21.84s
  ```
  File restored with `git checkout`, `git status --short` empty.
- The behaviour itself is right today. Probe G with a failed PubMed search and a live gene record shows only the existing failure note, no "none found" line:
  ```
  token[note]: 'The background search of PubMed did not finish, so this answer may be missing sources from it. Ask again to retry.'
  done.trust_outcome: ask
  ```
  (`_search_ids` already returns [] for a non-ok status, so the mutant would print "No PubMed papers ... were found" over a failed search, beside the failure note.) Nothing pins it.

## Local probes, branch beside develop

Graph stub: three Article rows (the real template's shape), `total_available=3487`. Gene record stubbed empty unless stated.

| Scenario | Branch | Develop |
|---|---|---|
| A1, 5 years, PubMed finds 2 | "Found 2 pubmed records for BRCA1: ...", 2 citations, answer | "Found 3 article records for BRCA1, of 3487 available", answer |
| A2, 12 months, PubMed finds none | generic refusal (A-105-02) | 3 graph papers, answer |
| A3, 5 years, PubMed search error | refusal "One of my searches did not finish" | 3 graph papers plus failure note, ask |
| A4, 5 years, PubMed search timeout (0.5 s budget) | same refusal as A3 | 3 graph papers plus timeout note, ask |
| A5, variants shape, PubMed finds 2 | "Found 2 pubmed records and 12 sequence variant records", PubMed table first, all 12 variants | "Found 12 sequence variant records", variants first, both tables |
| A6, variants shape, PubMed finds none | 12 variants, the new line, answer | 12 variants, answer |
| A7a then A7b, typed follow-up in the same session | follow-up "which papers mention BRCA1?" shows the 3 graph papers, "of 3487", truncation note: the flag does not carry over | same |
| A7c, a second option of the same offer clicked later | still windowed (the offer is kept by design, `clarify.picked_recent_window`) | same window |
| A8, ids found, abstracts fetch fails | same refusal as A3 | 3 graph papers plus failure note, ask |
| G, gene record live, 12 months, none / error / found | line shown, answer / failure note, ask / 1 PubMed record leads, answer | graph papers each time |
| C, typed CURIE (A-105-01) | gene record only, no paper, no line | graph papers |
| V, 40 variants and 5 windowed papers | 40 variants and 5 papers listed, count line counts both | 40 variants and 5 papers listed, count line counts variants |

Variant, disease and GO shaped graph results lose no row: `_without_article_rows` keeps every non-Article row (V lists all 40 on both trees). What changes on a windowed non-paper question is order and the count line: the windowed PubMed papers now answer too, through `_answer_call_ids`. The owner's decision says the window's papers lead, so this is reported as evidence, not a finding.

## Live runs

Branch tree, `core.run.run_streaming()`, `CLASSIFIER_PROVIDER=jev`, guard and plan models `deepseek/deepseek-v4-flash`, `PER_QUERY_COST_CAP_USD=0.25`, synth model from the local env. Session ids `card105-adv-<scenario>-<hex>`. A pick is the ask then the click in one session and owner. Full output: `<scratchpad>/card105_adv/live_branch.txt`, develop `live_dev.txt`.

| Run | Question then click | Lists | Trust line | Elapsed |
|---|---|---|---|---|
| 1 | "recent papers on BRCA1", then "... from the last 5 years?" | "Found 4 pubmed records for BRCA1": PMID 35432218, 36914836, 38266640, 39510841 (2022 to 2024), each titled; gene record, 5 ClinVar, OMIM, 5 trials, PMID 20301425 under "Publication records found"; no 1999 paper, no "of 3487" | "Based on 17 sources cited", answer | 21.8 s |
| 2 | "recent papers on TEX33", then 12 months | refusal "I could not identify that gene"; TEX33 is not a current NCBI symbol (ESearch on gene finds none), same on develop's code path | none, refuse | 6.1 s |
| 3 | "recent papers on C9orf43", then "... from the last 12 months?" | "Found 1 gene record and 5 clinvar records for C9orf43", then the line "No PubMed papers from the last 12 months were found for C9ORF43. Papers in the knowledge graph carry no publication date, so they are not listed here." | "Based on 6 sources cited", answer | 15.0 s |
| 4, control | "recent papers on BRCA1 from the last 5 years?" typed in a new session, no offer | "Found 40 article records for BRCA1, of 3487 available", PMID:10026184 first, then gene, 5 PubMed, ClinVar, OMIM, trials; plan line "the date range in your question could not be applied, so papers from any year were searched": develop's code, as designed | "Based on 57 sources cited, not yet confirmed", ask | 17.3 s |
| 5 | "recent papers on cystic fibrosis", then 5 years | topic path (no flag): "Found 5 pubmed records for cystic fibrosis", 5 titled papers | "Based on 5 sources cited", answer | 16.5 s |

- Counts agree with what is listed. Run 1: 17 distinct source pages (the gene page is cited as `/gene/672/` and `/gene/672`, counted once). Run 3: gene page plus 5 ClinVar is 6.
- Develop, run 3's question: "Found 16 article records for C9orf43", "Based on 22 sources cited, not yet confirmed", ask, 12.0 s. The branch was 3 s slower on that one pair; the branch adds no call (it removes rows and, with them, the quarantine reader pass), and the two runs differed in whether the writing model's summary was kept, so I read it as model latency noise, not a regression. Run 1 at 21.8 s compares with 34.9 s measured on develop in the diagnosis.
- Spend: branch about $0.053 over the five runs, develop about $0.009, total about $0.062.

## What held

- The flag reaches only a picked question: it needs `_picked_publication_window(query)` (`core/graph.py:7209`), so the control (live run 4 and the builder's unpicked test) and the typed follow-up (A7b) run develop's code.
- The topic path is untouched (live run 5): the flag is set only in the `else` branch after `elif topic_term is not None`.
- The new line never says "none found" over a failed or timed out search (A3, A4, A8, G error): `None` raw output for a timeout, `status == "error"` for a failure. Pinned by no test (A-105-04).
- The label is the window's own phrase ("the last 12 months", "the last 5 years"), read from the stored offer.
- `row_count`, `total_available` and `truncated` agree after the drop; no "of 3487" note on a windowed answer.

## Verdict

Two findings are worse than develop, both minor and both inside `core/graph.py`:

- A-105-01: a picked window on a gene with no searchable symbol (typed CURIE) shows no paper and says nothing, under a plan line that claims a PubMed search.
- A-105-02: when no other record grounds the answer, a windowed question refuses with a generic message and the "none found" line is lost.

A-105-03 and A-105-04 are not worse than develop.

VERDICT: FIX FIRST
