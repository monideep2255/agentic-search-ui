# Card 22 adversary review

Round 1, fresh context, 2026-10-06. Branch `fix/card22-name-every-total`. Findings are appended as they are established.

## Findings

### A-22-01: "Confirmed by 2 independent databases" when both records are ClinVar

- Blocking: yes. The card's own new noun makes a false statement; the number did not change, but the word now asserts something the number does not count.
- Input: a high-risk claim cited twice, once from the graph's ClinVar row (`tool=cypher_query`, `curie=ClinVar:17661`, field `clinical_significance`, value `Pathogenic`) and once from a live `ncbi_efetch` fetch of the same ClinVar record (`tool=ncbi_efetch`, no curie, same field and value, URL `.../clinvar/variation/17661/`). `ncbi_efetch.py:103` does emit `clinical_significance` for ClinVar, so this is a reachable shape.
- What the person sees: "Confirmed by 2 independent databases". There is one database.
- Evidence: `raw/adversary/probe_confirmed.py`, case 1, run offline with the module's own `trust_for_claims` and `answer_trust_line`:
  - `case1 triangulation: [('c1', 'high', 'concordant', 'answer'), ('c2', 'high', 'concordant', 'answer')]`
  - `case1 line: Confirmed by 2 independent databases`
  - `case1 origin_database: ['clinvar', 'ncbi_efetch']`
- Why: `_origin_database` reads the CURIE prefix, but only Layer 1 rows carry a `curie` (grep: only `cypher_query.py` and `cypher_provenance.py` emit `"curie"`), so every Layer 2 and Layer 3 finding falls back to its tool name. The build report's table says this number counts "Distinct origin databases (record id prefix)"; for every live and enrichment record it counts tools. The same holds for `triangulate`'s `_origin_of` (tool name unless `field == "curie"`), which is why the pair counts as concordant at all; Section 8.3.2's rule against counting a snapshot and a live fetch of one database twice is not enforced for Layer 2.
- Two further faces of the same defect, same probe, case 3: the graph gene record keys `ncbigene` and the live Datasets gene record keys `ncbi_datasets`, so one database is two. In the other direction, `ncbi_efetch` fetches from gene, pubmed and clinvar alike and keys all of them as one `ncbi_efetch`, so two databases can be one.
- Suggested fix: derive the origin database for Layer 2 and Layer 3 findings from the record page (host plus first path segment, or the tool's database parameter) and map `NCBIGene` and `ncbi_datasets` gene pages to one key; or, if that is out of this card's scope, keep the old noun until the count really counts databases. Either way it is the owner's call, because the card's wording change is what turned an internal miscount into a stated fact.
- NOT FIXED

### A-22-02: "Confirmed by N independent databases" counts every database the answer cites, not the ones that confirm

- Blocking: yes. The explainer text this card wrote says "Confirmed means two or more independent databases agree on the same high-stakes fact", so a person reads N as the number that agree.
- Input: one high-risk claim (`clinical_significance = Pathogenic`) concordant between a graph ClinVar row and a LitVar2 record, plus three low-risk records from ClinicalTrials.gov, PubTator and live Datasets that say nothing about pathogenicity.
- What the person sees: "Confirmed by 5 independent databases". Two databases agreed on the fact; three others were merely cited elsewhere in the answer. (And per A-22-01 the "5" is five tool or prefix keys, not five databases.)
- Evidence: `raw/adversary/probe_confirmed.py`, case 2:
  - `case2: [('c1', 'high', 'concordant'), ('c2', 'high', 'concordant'), ('c3', 'low', 'insufficient'), ('c4', 'low', 'insufficient'), ('c5', 'low', 'insufficient')] answer`
  - `case2 line: Confirmed by 5 independent databases`
- Why: `trust.py:652` computes `database_count` over all `claims`, and `trust.py:663` prints it. Pre-existing arithmetic, but the old "independent sources" was vague enough to be read as "sources in the answer"; "N independent databases" beside "Confirmed by" is a specific claim of N agreeing databases.
- Suggested fix: count the distinct origins among the concordant high-risk claims and their corroborating findings only, or word the line so the number is not attached to "confirmed" (for example "Confirmed by two or more independent databases").
- NOT FIXED

### A-22-03: the opening line still counts a slash pair as two records, above one source card

- Blocking: no, but it is a total that disagrees with the list on one screen, which is this card's hunt. Reachability is conditional (below), so I rate it unsure on how often a person meets it.
- Input: the opening sentence built from two cited answer findings for one gene page, the graph's `https://www.ncbi.nlm.nih.gov/gene/672` and the live Datasets `https://www.ncbi.nlm.nih.gov/gene/672/`, both `entity_type="Gene"`.
- What the person sees: Researcher "Found 2 gene records for BRCA1: BRCA1 [1] and BRCA1 [2]."; Plain language "I found 2 genes related to BRCA1 [1][2]." The Sources list under it shows one gene card, "Based on 1 source cited", meta "1 source cited".
- Evidence: `raw/adversary/probe_summary.py`, run offline against `answer_summary_sentence`:
  - `researcher -> Found 2 gene records for BRCA1: BRCA1 [1] and BRCA1 [2].`
  - `plain_language -> I found 2 genes related to BRCA1 [1][2].`
  - `distinct page keys: 1`
- Why: `answer_layout.py:1021` keys records by `(finding.source_url or "").strip()`, without the trailing-slash trim. Its own comment at `:1015-1017` says it keys "by exact `source_url` as the list and the trust line key it"; this card changed the list and the trust line key and left this third consumer behind, so the comment is now false and the three counts can split again. `answer_layout.py:864` (`shown_by_url`) has the same exact-URL key.
- Reachability: `core/graph.py:12879-12881` counts only the planned answer calls' findings, falling back to all findings when none of those was citable; the graph-plus-live pair lands in the count on the fallback path or when both calls are answer calls. Not measured live.
- Suggested fix: key `by_page` (and `shown_by_url`) with `trust.source_page_key`, which keeps "the same rule, everywhere" true. This is the owner's "opening line unchanged" decision only in its wording, not in its key.
- NOT FIXED

### A-22-04: the truncation note and the "more to show" count still count citations, and call them records

- Blocking: no. Pre-existing and outside this card's file fence, filed because it is a third unit for the same thing on the same screen.
- Input: any answer where `citations_capped` or the row limit fires and one page is cited twice (two fields of one record, or the slash pair).
- What the person sees: "Note: this answer was truncated to 18 records ..." (`core/graph.py:13549`, `shown=len(citations)`, worded at `:10320-10326`) beside "16 sources cited" and a Sources heading of 16. The next-step offer's remaining count is `known_total - len(citations)` (`core/graph.py:13828`), so it undercounts what is left by the number of repeat citations.
- Evidence: read, not run. `shown=len(citations)` and `remaining_records = known_total - len(citations)` are counts of numbered citations, the unit this card retired; their wording says "records".
- Suggested fix: pass the distinct page count (`len({source_page_key(c.source_url) or c.citation_id for c in citations})`) to both, or word them as citations.
- NOT FIXED

### A-22-05: a reopened saved answer says "Based on 16 sources cited" above 18 source rows

- Blocking: yes. This is the brief's "saved answer reopened from history" case, and the build report's not-covered note ("It states no total") is wrong: the trust line on that screen is a total, and this card changed its wording to claim it counts the listed pages.
- Input: the card's own BRCA1 fixture (`frontend/e2e/fixtures/card22_brca1_citations.json`, 18 citations) rendered through `SavedAnswerScreen` with the trust line this branch stores, "Based on 16 sources cited, not yet confirmed".
- What the person sees: "Based on 16 sources cited, not yet confirmed", then a Sources list of 18 rows, three of them the BRCA1 gene page. The info card text this card wrote says sources cited are "the same pages listed under Sources; two links to one page count once". On this screen neither half is true.
- Evidence: `raw/adversary/probe_front.test.tsx`, probe P5, output in `raw/adversary/probe_front_output.txt`:
  - `P5 {"trust":"Based on 16 sources cited, not yet confirmed","rows":18,"geneRows":3,"fixtureCitations":18}`
- Why: `SavedAnswerScreen.tsx:285-301` maps `answer.citations` one row per citation and never calls `groupSourcesByLayer`.
- Suggested fix: render the saved list through `groupSourcesByLayer` (or the same `sourcePageKey` dedupe) so a reopened answer shows the same cards as the live one, or have the lead record an owner-approved exception.
- NOT FIXED

### A-22-06: the YOUR SEARCHES item changes from "16 sources cited" to "18 sources" after a reload

- Blocking: yes, owner call. The build report lists it as not covered and outside the file fence. Filing it because it is a sources number that counts citations, the exact thing option B retired, and the person watches it change on the same search.
- Input: the BRCA1 answer, live, then a page reload.
- What the person sees: while live the rail item carries the answer's meta (`App.tsx:1175`, `meta: view.meta`), "13 tool calls · 16 sources cited from 3 layers". After a reload the same item reads "18 sources · Oct 6" (`App.tsx:264-269`, `formatHistoryMeta`, from `citation_count`, which is `len(citations)` in `feedback/history.py:146` and `:289`).
- Evidence: read, not run. The history-reload end-to-end spec fails on develop on this machine per the build report, so I did not drive it; the arithmetic is one `len()` over the stored citation list, which holds 18 entries for this answer.
- Suggested fix: count distinct `source_page_key` values in `_citation_count`, and word the label "sources cited".
- NOT FIXED

### A-22-07: the two page keys are not the identical rule the code comments claim

- Blocking: no. Every differing input below fails the citation wire pattern, so no live citation can carry one today.
- Input: 28 URLs run through `sourcePageKey` (TypeScript) and `source_page_key` (Python).
- What differs: 6 of 28. Python's `str.strip` removes `\x85` and `\x1c` to `\x1f`, which JavaScript's `trim` keeps; JavaScript's `trim` removes `﻿`, which Python keeps. Examples: `'﻿https://x/'` gives py `'﻿https://x'`, js `'https://x'`; `'https://x/\x85'` gives py `'https://x'`, js `'https://x/\x85'`.
- Evidence: `raw/adversary/probe_front.test.tsx` P1 writes `raw/adversary/front_keys.json`; `raw/adversary/probe_parity.py` compares: `cases 28 diffs 6`, each with `passes wire pattern: False`.
- Why it still matters a little: the backend counts `SynthFinding.source_url`, which is not pattern-checked, while the frontend only ever sees pattern-checked citation URLs, so the "same cases" fixture proves agreement only on the cases it lists. The docstrings say "identical rule".
- Suggested fix: strip only ASCII whitespace on both sides (`strip(" \t\r\n\f\v")` and `replace(/^[ \t\r\n\f\v]+|[ \t\r\n\f\v]+$/g, "")`), or soften the comments.
- NOT FIXED

### A-22-08: the command line prints "Based on 16 sources cited" over 18 numbered references

- Blocking: no, same root as A-22-05 on a second surface. The build report says the command line "shows no other total"; it shows a numbered list a person can count.
- Input: the card's BRCA1 fixture fed as events to `adapters/cli/render.py`'s `Renderer` with the stored trust line.
- What the person sees:
  - `Based on 16 sources cited, not yet confirmed`
  - `References:` then `[1] NCBIGene - https://www.ncbi.nlm.nih.gov/gene/672/` ... `[6] NCBIGene - https://www.ncbi.nlm.nih.gov/gene/672` ... `[9] NCBIGene - https://www.ncbi.nlm.nih.gov/gene/672/` ... `[18] ...`, eighteen lines, the BRCA1 gene three times.
- Evidence: `raw/adversary/probe_cli.py`, run offline; full output reproduced above, 18 reference lines.
- Suggested fix: either group the references by `source_page_key` ("[1][6][9] NCBIGene - ..."), as the web list does, or accept that a numbered reference list counts citations and say so. The MCP surface returns `trust_line` beside the full citation list too (`adapters/mcp/server.py:1189`, `:1299`), so a client that lists them has the same mismatch.
- NOT FIXED

### A-22-09: a live record merged into a graph card is labelled "L1 · graph", and the meta says one layer while its chip says layer 2

- Blocking: yes. This sits inside this card's own change: before the new page key, the graph link and the live link were two cards; the merge, and so this mislabel, is new on this branch. Per the review rules, a finding inside the phase's own fix escalates.
- Input: a gene answer citing the graph's gene record `[1]` (`layer_1_graph`, `https://www.ncbi.nlm.nih.gov/gene/672`, the shape `cypher_provenance.py:231` builds) and the live Datasets record `[2]` (`layer_2_api`, `https://www.ncbi.nlm.nih.gov/gene/672/`, the shape `ncbi_datasets_actions.py:327` builds), each on its own sentence: "BRCA1 is a gene in the graph [1]. The live gene record names it BRCA1 [2]."
- What the person sees:
  - Chip `[2]`: green, spoken name "Source 2, layer 2".
  - Meta: "2 tool calls · 1 source cited from 1 layer".
  - Sources: one group, Knowledge graph, one card, "[1][2] NCBIGene 672 L1 · graph".
  - So the sentence about the live record points at a card that says graph, and no Live NCBI APIs group exists although the answer cites a live fetch and the reasoning log shows the live call.
- Evidence: `raw/adversary/probe_xlayer.test.tsx`, output in `raw/adversary/probe_xlayer_output.txt`:
  - `XL {"meta":"2 tool calls · 1 source cited from 1 layer","heading":"1","groups":[["sources-group-1-count","1"]],"chip2Layer":"2","chip2Aria":"Source 2, layer 2","cardLayer":"1","cardSummary":"▶[1][2]NCBIGene 672L1 · graph"}`
- Why: `groupSourcesByLayer` keeps the first citation's layer, name, tool, evidence and licence for the merged card (`AnswerScreen.tsx:566-575`), and `citedSourceCounts` reads layers off those groups. The build report justifies one card by "Section 8.3.2 already treats a graph snapshot and a live fetch of one database as one origin", but the code's own origin count does not: `_origin_database` keys the pair as `ncbigene` and `ncbi_datasets`, two (A-22-01, case 3). The author's own unit test pins the "1 layer" result as correct (`AnswerScreen.card22.test.tsx`, "counts layers as the Sources list groups them").
- Suggested fix: the owner's call between two honest options. Either a merged card names every layer it carries ("L1 · graph, L2 · live", counted in both groups' layers for the meta), or the merge stays within one layer (key on layer plus page) so the graph and live records remain two cards and the sources count says 2. The current form makes the count agree by mislabelling a record.
- NOT FIXED

### A-22-10: the new comment in `useRunView.ts` states the wrong number

- Blocking: no. Documentation in the new code only.
- What: the card 22 comment at `frontend/src/hooks/useRunView.ts:1170-1172` says the BRCA1 meta line now reads "13 tool calls · 17 sources cited from 3 layers". The build report, the fixture and the screenshots all say 16, and 17 is the old trailing-slash split this card removed.
- Evidence: `grep -n "17 sources cited" frontend/src/hooks/useRunView.ts` matches line 1171.
- Suggested fix: 16.
- NOT FIXED

### A-22-10: "Confirmed by 2 independent databases" above a Sources list of 1, which query 107 says cannot happen

- Blocking: no on its own; it is the visible face of A-22-01, and it makes query 107's stated expectation false.
- Input: A-22-01's case 1, the graph ClinVar row and the live efetch ClinVar record for one variant, `.../clinvar/variation/17661` and `.../clinvar/variation/17661/`.
- What the person sees: Sources heading 1 (the slash pair is one page under the new key) and "Confirmed by 2 independent databases". Query 107 tells the tester the database number "can be smaller than S"; it can also be larger, and here it is larger because one database is counted twice.
- Evidence: `raw/adversary/probe_confirmed.py` case 1 prints `Confirmed by 2 independent databases`; `source_page_key` of the two URLs is one key (same rule as `probe_summary.py`'s `distinct page keys: 1`).
- Suggested fix: resolve A-22-01; until then, query 107's line should not promise N is at most S.
- NOT FIXED

### A-22-11: the new comment in `useRunView.ts` states the wrong number

- Blocking: no. Documentation in the newest code.
- What: `frontend/src/hooks/useRunView.ts:1170-1172` says the meta line now "reads '13 tool calls · 17 sources cited from 3 layers'". The card's own result, its tests and its screenshots say 16. A later reader checking the code against the evidence will be told 17.
- Evidence: `git diff origin/develop...HEAD -- frontend/src/hooks/useRunView.ts`, and `AnswerScreen.card22.test.tsx` expecting `16 sources cited from 3 layers`.
- Suggested fix: change 17 to 16.
- NOT FIXED

### A-22-09, addendum: reproduced in the real app

- The fake-model end-to-end harness on this branch, scripted stream, `raw/adversary/adv_card22.spec.ts` with `raw/adversary/pw.adv.config.ts`, 2 passed at 1280 and 390:
  - `ADV 1280 {"meta":"✓ Answered1.0s · 2 tool calls · 1 source cited from 1 layer","heading":"1","trust":"Based on 1 source cited","card":"▶[1][2]NCBIGene 672L1 · graph","chip2":"Source 2, layer 2","rail":["2 tool calls · 1 source cited from 1 layer", ...]}`
  - `ADV 390` the same values.
- Screenshot `raw/adversary/adv_xlayer_390.png`: the sentence "The live gene record names it BRCA1." carries a green layer 2 marker, and the only card under it is blue, Knowledge graph, "L1 · graph". Sign-in email masked.

## What held

Verified with my own probes:

- The meta line, the Sources heading and the trust line agree on the card's BRCA1 fixture (16, 16, 16) when rendered through `useRunView` and `AnswerScreen` (probe P4 and the author's evidence numbers reproduced independently in P5's input).
- The slash pair merges on both sides; query strings and fragments are kept apart on both sides, so isolate links (`isolates#/search/biosample_acc:...`) and PubTator `?query=` links stay distinct.
- Link-less sources are never merged (frontend keys `#n`, backend keys the citation id).
- Singular and zero wording: "1 tool call · 1 source cited from 1 layer", "2 tool calls · 0 sources cited" with no layer clause.
- The live YOUR SEARCHES item carries the same meta as the answer (end-to-end, 1280).
- Phone width 390: the meta line wraps to two lines, nothing is cut off (my screenshot and the author's).
- The backend's trust-line claims and the frontend's citations come from the same `grounding` object; nothing reassigns it between `_citations_from_grounded_claims` (`core/graph.py:13366`) and `answer_trust_line` (`:13848`).
- Plain language and Researcher render the same Sources list and meta; the frontend has no depth branch.

Read, not run:

- Previous turns of a conversation render their own `meta` and their own grouped Sources, so a follow-up does not mix counts.
- The legacy "N layers agreed" pill still counts layers over all citations (`useRunView.ts:848`, `:1151`), but it only appears when a run carries no `trust_line`, an older backend.

## Not covered

- No live model run and no live graph, by the brief. Whether the graph-plus-live gene pair of A-22-09 and A-22-03 appears in today's live answers is not measured; the URL shapes are from the builders' own code.
- The history reload path (A-22-06) was not driven end to end.
- The isolate table and the paper-links answer were checked only for their URL shapes, not rendered.
- A Layer 2 or Layer 3 citation whose builder returns None (backend counts it, frontend does not) was not reached: every URL builder I read encodes its input and pins its host.
- Large counts: "1200 sources cited" renders without a thousands separator; the display cap is far lower, so I did not file it.

## Verdict

FAIL.

Blocking items:

- A-22-01: "Confirmed by 2 independent databases" for two copies of one ClinVar record; the new noun names something the count does not count.
- A-22-02: "Confirmed by N independent databases" counts every database cited, not those that confirm.
- A-22-05: a reopened saved answer says 16 sources cited above 18 rows.
- A-22-06: the rail item turns from "16 sources cited" into "18 sources" after a reload (owner call; the build report lists it as known).
- A-22-09: inside this card's own change. Merging a graph record and a live record into one card labels the live record "L1 · graph" and drops its layer from the meta. This finding sits inside a fix made during this phase.

Verified by my own probes: A-22-01, A-22-02, A-22-03, A-22-05, A-22-07, A-22-08, A-22-09 (unit and end to end), A-22-10. Read only: A-22-04, A-22-06.
### A-22-09 addendum: reproduced in the real app

- The fake-model end-to-end harness, with the scripted stream from `raw/adversary/adv_card22.spec.ts`, shows the same at 1280 and 390: meta "2 tool calls · 1 source cited from 1 layer", the rail item the same, the one card "[1][2] NCBIGene 672 L1 · graph", chip `[2]` "Source 2, layer 2". Output: `raw/adversary/adv_e2e_output.txt`; screenshots `raw/adversary/adv_xlayer_1280.png` and `adv_xlayer_390.png` (sign-in email masked).

## What held

Verified with my own probes:

- One number on the live answer screen. On the card's BRCA1 fixture and on my own inputs (slash pairs, a page cited from two layers, link-less sources), the meta line, the Sources heading and the group counts always agreed with each other (`probe_front.test.tsx` P2, P4; `probe_xlayer`; the end-to-end run).
- The backend and frontend counts agree wherever a URL can reach the wire. Every input where the two page keys differ fails `NCBI_SOURCE_URL_PATTERN` (A-22-07), and `grounding` is not reassigned between building the citations (`core/graph.py:13366`) and the trust line (`:13848`), so both count the same claims.
- A query string, a fragment, `http` against `https`, an uppercase host, a percent-encoded path and the two PubMed hosts are all left as separate pages by both keys. No merge on a guess. (`front_keys.json` and the Python run, no diff on those inputs.)
- Link-less sources are never merged (`groupSourcesByLayer` gives `#n`).
- Wording at 0, 1 and large counts: "2 tool calls · 0 sources cited" with no layer clause, "1 tool call · 1 source cited from 1 layer" (the author's test, consistent with my P6 run), "1200 sources cited from 1 layer". The meta wraps cleanly at 390 in the author's screenshot.
- Plain language against Researcher: the frontend has no depth branch in the meta, heading or trust line (grep), so the numbers are depth-independent.
- A follow-up turn's earlier answer renders through the same `AnswerBody` with its own `meta`, so it carries the same counts (read, `AnswerScreen.tsx:2312-2327`).
- No tracked file changed in the worktree during this round (`git status --short` shows only untracked report files).

Read only, not run:

- The live YOUR SEARCHES item uses `view.meta` (`App.tsx:1175`), so while live it matches the answer.
- The legacy "N layers agreed" pill still counts layers over all citations (`useRunView.ts:848`, `:1151-1156`) and could now disagree with "from N layers" after a cross-layer merge, but it only renders when `done` carries no `trust_line`, which today's backend always sends on an answer.

## Not covered

- No live model run, by instruction. Whether a real answer cites the graph gene link and the live Datasets gene link together (A-22-09) and whether the opening line counts both (A-22-03) were not measured live.
- The YOUR SEARCHES reload path (A-22-06) was not driven end to end; the history-reload spec fails on develop on this machine per the build report.
- The pathogen isolate table and the paper-links answer were checked only by reading URL builders (isolates differ by fragment, so they stay apart); no render.
- Whether any Layer 2 or Layer 3 citation builder returns None in practice, which would make the backend count a page the screen does not list. All builders I read encode their URLs and pin the host.
- A stray `raw/adversary/package.json` (`{"type":"module","private":true}`) appeared in my folder during the round; I did not create it by hand. `raw/adversary/node_modules` is a symlink to `frontend/node_modules` so the throwaway specs resolve. Both untracked, safe to delete with the folder.

## Verdict

FAIL against the card's contract, "every number that says sources counts distinct pages, one number everywhere, each total names what it counts".

Blocking:

- A-22-01: "Confirmed by N independent databases" counts tool names for every live and enrichment record, so one ClinVar record fetched twice reads "2 independent databases".
- A-22-02: N counts every database the answer cites, not the ones that confirm, while the new explainer says N agree.
- A-22-05: a reopened saved answer says "Based on 16 sources cited" over 18 rows.
- A-22-06: the rail item turns "16 sources cited" into "18 sources" on reload (owner call; the build report lists it as known).
- A-22-09: inside this card's own change. The new page key merges a graph record and a live record into one card labelled "L1 · graph", and the meta says one layer while the live chip says layer 2. This fires the stop condition and goes to the product owner.

Probed versus read: A-22-01, 02, 03, 05, 07, 08, 09 and 10 were reproduced with my own scripts or specs; A-22-04, 06 and 11 are from reading.


## Note on this file: a second writer

While this round ran, a second writer appended to this same file, interleaved with my appends. I did not rewrite the file, so nothing of theirs is lost. What a reader should know:

- Two headings read "A-22-10". The one titled "the new comment in `useRunView.ts` states the wrong number" is the same defect as A-22-11; treat them as one finding. The A-22-10 titled "'Confirmed by 2 independent databases' above a Sources list of 1" stands as A-22-10.
- "A-22-09 addendum", "What held", "Not covered" and "Verdict" appear twice. Both verdicts are FAIL with the same five blocking items (A-22-01, 02, 05, 06, 09), and both say A-22-09 sits inside this card's own change.
- The lead should check which process the second writer was before the next round.
