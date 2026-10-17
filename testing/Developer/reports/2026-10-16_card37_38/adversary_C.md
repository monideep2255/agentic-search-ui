# Card 38 slice C adversary report: graph papers by title

Pull request #263, branch `fix/card38-graph-papers-by-title`, commit `22730d97` on develop `78c68c1c`. Adversary round, one pass. Probes in `<scratchpad>/card38c_adv/`.

## Table of contents

- [Findings](#findings)
- [Probes that held](#probes-that-held)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

Filed as found.

### A-38-01, minor, worse than develop: a paper with no abstract is listed twice in Researcher

When one answer holds the same paper twice, once from a live PubMed fetch whose record carries a title and no abstract, and once from the graph, Researcher's table now lists it twice with the same title. Develop lists it once.

Cause: `one_finding_per_record` (`src/system_03_search_agent/synthesis/findings.py:1154`) keeps every finding of a page when every finding on it has the same field name ("separate records that happen to share a page"), and collapses a page whose findings carry different fields. On develop the graph paper is field `curie` beside the live `title`, so the page collapses to the live row. On the branch `apply_resolved_article_titles` (`synthesis/article_titles.py:354` to `:364`) makes the graph paper field `title` too, so the page now reads as two records and both rows ship. With an abstract on the live record the page has mixed fields and still collapses, so only abstract-less papers (letters, editorials, older papers) are hit.

Evidence, probe E (`<scratchpad>/card38c_adv/test_probe_e_dup_write.py`, write_node at both depths, live record 111 title only plus graph papers 111 and 222):

```
branch researcher:abstract=False
    ['A letter on CFTR chloride channels', 'PMID:111']
    ['Another live paper on CFTR', 'PMID:444']
    ['A letter on CFTR chloride channels', 'PMID:111']
    ['A graph only paper on CFTR', 'PMID:222']
develop researcher:abstract=False
    ['A letter on CFTR chloride channels', 'PMID:111']
    ['Another live paper on CFTR', 'PMID:444']
    ['PMID:222', 'PMID:222']
```

Plain language dedups on its own path (three rows on the branch), but the branch still emits four citation events there, two for page 111. The Sources list merges by page key, so its card count is unchanged. Unit level (probe D, `one_finding_per_record` alone): branch keeps `ef-1` and `cq-3`, develop keeps `ef-1` only.

In a person's words: "The same letter is in my table twice." Not a wrong record, but a regression of item 12.7's one row per record. Fixable inside the fence: `apply_resolved_article_titles` can leave a graph paper alone (or drop it) when a live finding already names the same page, which is develop's outcome. Ticket T-8.9-01 step 6 names this; the build report says it was left out, and says "Both rows would now carry the same title and page" without noting develop shows one.

### A-38-02, minor, accepted by the decision: on the CFTR papers question the Sources list holds no knowledge graph card at all

Live run 1 (Researcher) and run 2 (Plain language): every one of the 54 graph papers is cited `layer_2_api`, `ncbi_efetch`, field `title`, and the gene row is cited from the live gene record, so not one citation is `layer_1_graph`. Pasted from the summarizer over run 1's citation events: `CITATION events 76 pages 71 home groups {'layer_2_api': 66, 'layer_3_enrichment': 5}`. `groupSourcesByLayer` (`frontend/src/components/screens/AnswerScreen.tsx:777`) drops an empty group (`.filter((group) => group.items.length + group.alsoCited.length > 0)`), so the person who asked "Which papers in the graph mention the CFTR gene" sees Sources under Live NCBI APIs and Enrichment only, "71 sources cited from 2 layers". On develop the 54 papers sit under Knowledge graph.

The answer still names the graph in words: the opening "Found 54 article records for CFTR, of 1962 available" and the note "only 117 of the 1962 records that matched this question in the graph were retrieved", and the steps show both `cypher_query` calls. Nothing on screen says the graph found nothing. The lead's decision names this move, so it is not counted as worse; it is filed so the product reviewer sees the extreme case: on G-021 the Knowledge graph group is gone entirely, not shrunk.

### A-38-03, minor, not worse in records: Plain language now opens its summary with "A third shows that ..."

Live run 2 (Plain language), the summary in placement order, pasted:

```
20.34 summary claim A third shows that disrupting a complex between the DeltaF508 CFTR protein and its chapero
20.34 summary claim I found 54 published papers related to CFTR, out of 1962 available [1][2][3]...
20.34 summary claim A fourth reports that a co-chaperone called CHIP marks unfinished CFTR protein for destruc
20.34 summary claim Another reports that protein kinase A, a regulatory enzyme, attaches to CFTR through a lin
...
20.34 summary claim A third reports a new D513G mutation in exon 10 of the CFTR gene found in a French patient
...
20.34 summary claim A third analyzes a regulatory DNA site located about 20.9 kilobases upstream of the CFTR g
```

The writer now has 54 titles and writes 20 to 30 sentences about them; the gate drops the writer's first ones, and what survives opens with ordinals that have no antecedent ("A third" three times, "A fourth", "One more"), the first of them placed ahead of the count sentence. Query 75's line "No paragraph reads 'Another is titled ...' with no first paper named before it" is the same defect class. On develop this question gets no prose at all (the fallback note), so no record is lost or wrong and the list is far better; but the opening line a person reads is "A third shows that ...". Each sentence is a fair reading of its cited title ("One reports that early diagnosis through newborn screening prevents severe malnutrition ..." cites PMID 11134427, whose title says that). Not fixable inside this card's fence without touching the writer or the gate; for the lead to weigh against the gain.

### A-38-04, minor, worse than develop in Plain language: PubMed's "[Not Available]." placeholder becomes a paper's name

PubMed writes `<ArticleTitle>[Not Available].</ArticleTitle>` for a paper with no English title (the real title is in `VernacularTitle`). `clean_article_title` keeps it (probe A, `<scratchpad>/card38c_adv/probe_a_bodies.py`, case `not_available`: `PMID:5001 -> '[Not Available].'`; direct call: `'[Not Available].'`), so the finding is rewritten to that "title". Probe F through write_node, pasted:

```
plain_language list_item cells ['[Not Available].']
researcher table_row cells ['[Not Available].', 'PMID:666']
```

On develop the same paper reads "Published paper" in Plain language and "PMID:666" in Researcher. "[Not Available]." reads as "this paper is not available", which is a wrong statement about the record; Researcher keeps the PMID beside it, Plain language does not. The ticket's own rule is "PubMed returns no title, the paper keeps its PubMed number"; this is PubMed returning a placeholder in the title slot. Fixable inside the fence in one line: treat a title that is only a bracketed placeholder ("[Not Available].", and "[In Process Citation]" for the same reason) as no title. Rare: none of the 54 CFTR papers in the live runs carried it.

### A-38-05, minor, evidence: the added wait is serial and close to a second

`_prefetch_answer_names` has no caller (`grep -rn _prefetch_answer_names src` finds only its definition at `core/graph.py:8743` and a comment at `:9071`), so the lookup runs in Write, in line, before the writer call (`core/graph.py:14003` to `:14008`). Measured inside the live runs (a timing wrapper around `graph.resolve_article_titles`): 0.929 s (Researcher) and 0.656 s (Plain language), 54 of 54 titles each time. The builder's five local runs: 1.440, 0.909, 0.784, 0.513, 0.629 s. So the median is under a second, and about one run in five or six is over. Its bound is 15 s (`article_titles.py:110`, `asyncio.wait_for`), the same per-call budget the MedGen name lookup in Write inherits from the transport (`tools/ncbi_transport.py:338`, `DEFAULT_TIMEOUT_S = 15.0`), so a slow PubMed can hold the answer up to 15 s, as a slow MedGen already can. Not counted as worse by the median; for the lead, the whole G-021 answer sat at 18.9 s and 20.3 s, at the 20 s goal.

### A-38-06, minor, evidence: on the command line and MCP a multi-sentence title is split into marked fragments

The CLI and MCP read token `text`, never `cells` (`adapters/mcp/server.py:1270`, `joined_text(answer_parts)`; no `cells` read in `adapters/cli/` or `adapters/mcp/`). The listing narrative marks each sentence of a multi-sentence value separately (item 11.34), so live run 1's rows read on those surfaces:

```
'Identification of a D579G homozygote cystic fibrosis patient with pancreatic sufficiency and minor lung involvement [2]. Mutations in brief no [2]. 221 [2]. Online [2]. '
'Article title: Unique presentations and chronic complications in adult cystic fibrosis: do they teach us anything about CFTR [43]. '
```

A question mark becomes a full stop, and "no. 221. Online." becomes three marked fragments. The web table reads the cells and is clean. On develop these rows read "Article record PMID:10094564 [2]." on those surfaces. The mechanism is develop's own and already applies to live PubMed titles; the branch extends it to graph papers. Not counted as worse: the reader gains the title, garbled at the edges.

## Probes that held

| Hunt | Probe | Result |
|---|---|---|
| Records in another order, one dropped | Probe A `reverse_and_drop`, crafted XML through the real transport classifier and parser (`ncbi_transport.execute_get` faked) | `PMID:1001 -> 'Title one'`, `PMID:1002 -> None`, `PMID:1003 -> 'Title three'`. Joined by `MedlineCitation/PMID`, never by position |
| A merged PMID (PubMed answers with another record) | Probe A `merged_pmid` | `PMID:2001 -> None`: the unasked record is ignored, the paper keeps its number |
| Retraction or erratum PMIDs inside the record | Probe A `retracted_with_cc` | The parser reads `./MedlineCitation/PMID` only (`tools/ncbi_eutils_actions.py:1249`); `CommentsCorrections` PMIDs never become the record's id |
| A retracted paper shown clean | Probe A `retracted_with_cc`, `retracted_prefix` | Title shown with no warning (`'A retracted paper on CFTR'`). Develop shows no retraction warning on any paper, graph or live (`grep -rni retract src` finds only a grounding comment); pre-existing, not worse. A "RETRACTED:" prefix is kept |
| Erratum record | Probe A `erratum` | `'Erratum: Mutation analysis of CFTR'`, the true title of that PMID |
| Inline markup in a title | Probe A `inline_markup` | `itertext` keeps the whole title: `'Role of CFTR in Ca2+ signalling of airway cells'` |
| Book article, empty set, DeleteCitation, cut title, 501 characters | Probe A | Each `None`, PMID kept; exactly 500 characters kept whole |
| One PMID twice, one blank | Probe A `dup_one_blank` | `None`, withheld |
| Hostile title: newline, bidi, zero width, markers, instruction | Probe A `hostile` | One line; `[3]`, `[4]`, `[12: "cure"]`, `[1#2]`, `[ 5 ]` become parentheses. `[3,4]`, `[3-5]`, `[3a]`, `[1000]` and fullwidth brackets survive, and neither the grounding marker (`synthesis/grounding.py:57`, `\[(\d{1,3})\]`) nor the web's (`frontend/src/hooks/useRunView.ts:855`) reads them as citations |
| A title stated as a finding, an injected claim, a title cited to the wrong record | Probe C, ten scripted writer sentences at both depths, both trees | Dropped: "BRCA1 causes cystic fibrosis [2]", "Research has established that BRCA1 causes cystic fibrosis [2]", title 3 cited as [1], title 1 cited as [3], an added "[4]". Kept: "These papers show that CFTR is protective against cholera in heterozygous carriers [1]", trust line "Based on 3 sources cited". Develop already lets the writer do this with a live PubMed title (`answer_layout.py:527`, a live paper's row is `{"title": ...}`), so the class is not new; the branch adds the "ARTICLE TITLES ... not a verified result" line for graph papers only |
| The join and the defusal are load-bearing | Mutation, one property each, restored with `git checkout` | Positional join: 9 tests fail. Defusal removed: 2 fail (`test_hostile_title_is_one_printable_line_with_no_marker`, `test_a_hostile_title_cannot_create_a_numbered_line_or_a_citation`) |
| Card 22's count after the move | Live runs 1 and 2 | "Based on 71 sources cited" over 71 distinct pages (`record_database` and the count key on the page, never the layer, `synthesis/trust.py:535`) |
| Card 8's database names | `testing/UI_fix_plan.md:38` | Card 8 is not on develop (it is a parked diff), so nothing on develop names a database by layer; `record_database` names a paper's database from its PubMed page in either layer |
| Questions with no graph paper | Live runs 3 and 4 | No title request (no `TITLE_LOOKUP` line), records and wording as before: query 1 lists its four MedGen diseases; query 75 lists five papers once each |
| Plain language versus Researcher | Live runs 1 and 2 | Same 54 graph papers in both, same 71 pages, same trust line |
| The new tests | `pytest -q` on the two new files | `38 passed in 9.91s` |

## Live runs

Five runs on the branch tree through `core.run.run_streaming()`, script `<scratchpad>/card38c_adv/live.py`, develop's settings as card 115's adversary used them (`CLASSIFIER_PROVIDER=jev`, develop's guard and plan models, the local writer model, `PER_QUERY_COST_CAP_USD=0.25`), session ids `card38c-adv-<label>`, `RequestContext(surface="web_ui", reads_placement=True)`. Spend: 0.0136 + 0.0205 + 0.0101 + 0.0204 + 0.0013 = about 0.066 USD. Each run ends with a `CallerIdentityRequired` traceback from session memory after `done` (no owner id in a script); the answer is complete before it.

| Run | Question, depth | What it lists | Sources grouping (home group per page) | Trust line | Done at | Title lookup | Develop's saved time |
|---|---|---|---|---|---|---|---|
| 1 | CFTR papers, Researcher | 54 graph papers by title with PMID ("The Hdj-2/Hsc70 chaperone pair facilitates early steps in CFTR biogenesis.", PMID:10075921, ...), CFTR gene, 5 live PubMed papers, 5 ClinVar, 1 OMIM, 5 trials; opening "Found 54 article records for CFTR, of 1962 available"; two prose sentences under "Chaperone and Protein Quality Control"; truncation note naming the graph | 71 pages: Live NCBI APIs 66, Enrichment 5, Knowledge graph 0 | Based on 71 sources cited | 18.92 s | 54 of 54 in 0.929 s | 24.3, 24.6, 23.2 s (`2026-09-29_card63_golden/runs.jsonl`, `server_elapsed_s`, before phase 8.7) |
| 2 | CFTR papers, Plain language | The same 54 papers by title, no "Published paper" row; 23 prose sentences, one per paper, opening "A third shows that ..." (A-38-03) | 71 pages: Live NCBI APIs 66, Enrichment 5, Knowledge graph 0 | Based on 71 sources cited | 20.34 s | 54 of 54 in 0.656 s | as above |
| 3 | Query 1, BRCA1 diseases, Researcher | Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, Fanconi anemia complementation group S, plus gene, papers, ClinVar, OMIM, trials | 21 pages: Live NCBI APIs 16, Enrichment 5 (unchanged path: MedGen names were already Layer 2) | Based on 21 sources cited, not yet confirmed | 9.28 s | none (no graph paper) | 16.0 s (card 115 adversary, develop's tree, 2026-10-15) |
| 4 | Query 75, caffeine papers, Researcher | 5 PubMed papers, each once; 4 prose sentences | 5 pages: Live NCBI APIs 5 | Based on 5 sources cited | 11.77 s | none | 12.3 s and 12.5 s means (card 29 build, 2026-10-15) |
| 5 | "What is the latest literature on BRCA1?", Researcher | Asked back "How far back should I search?" (card 105's window question), no tool call | none | none (refuse) | 1.65 s | none | not compared |

Run 5 was spent hunting A-38-01 live and did not reach it; A-38-01 stands on probes D and E. The time comparisons cross days and model latency; the lookup's own measured time is the honest added cost (A-38-05).

## Verdict

The join, the quarantine and the marker defusal held every crafted body: no title was joined to the wrong PMID, and no injected title produced a citation or survived the sentence check as a claim. Two things are worse than develop, both small and both inside the card's fence:

- A-38-01: a paper with no abstract, found by both a live PubMed fetch and the graph, is listed twice in Researcher (develop lists it once).
- A-38-04: PubMed's "[Not Available]." placeholder becomes the paper's name in Plain language, where develop says "Published paper".

A-38-02 (no knowledge graph card on G-021) is the move the lead's decision names. A-38-03, A-38-05 and A-38-06 are evidence for the lead and the product reviewer, not counted against the card.

VERDICT: FIX FIRST
