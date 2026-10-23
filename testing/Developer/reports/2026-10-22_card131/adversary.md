# Card 131 part 1: adversary round 1

Adversary round for pull request 292, branch fix/card131-count-line-titles. Findings are appended as they are established. Ids A-131-01 and up. Filed, never fixed or closed.

## Findings

### A-131-01: the offer and the note under the count line still say "pubmed records" and "variant record records"
- Severity: major
- What: the change fixes the nouns only inside `answer_summary_sentence`. The follow-up offer (`core/graph.py:11040-11049`, `_build_next_step_offer`) and the further-records note (`core/graph.py:10900-10921`, `_build_incomplete_answer_note`) build their nouns separately from `entity_type_noun`, so the same answer now calls one set of records "papers" in its first line and "pubmed records" or "article records" in its offer, and the dbSNP "Variant record" type still reads "variant record records", the exact wording the card names.
- Reproduction: scratch probe on the branch calling the three builders with three findings of one type, subject "CFTR", total 100, remaining 97:
  - type "pubmed": count line `Found 3 papers for CFTR, of 100 available [1][2][3].`, offer `Would you like me to go through the 97 further pubmed records found for this question?`, note `Note: 3 further pubmed records were found ...`
  - type "Article": offer `... 97 further article records ...`; type "Publication": `... 97 further publication records ...`
  - type "Variant record" (the `_pseudo_row` type ncbi_dbsnp emits, `core/graph.py:5104`): count line `Found 3 variant records for CFTR ...`, offer `Would you like me to go through the 97 further variant record records found for this question?`, note `Note: 3 further variant record records were found ...`
- Why it matters: the offer is shown to the reader (the note is hidden only in the web UI by `HIDDEN_NOTE_PATTERNS`, and still reaches the API, CLI and MCP). The card's complaint survives on the same screen one paragraph lower, and the two counts of the same records now use two different nouns, which reads as two kinds of record.
- NOT FIXED

### A-131-02: in a mixed answer the nouns no longer follow the markers, and the two depths now list the nouns in different orders
- Severity: major
- What: `answer_layout.py:1957-1960` inserts the paper count at position 0 of `parts`, while the bare markers after it stay in slot order. Before this change a mixed answer of six or fewer records attached each marker to a name, so a marker's record was readable; now every mixed answer with a paper shows bare markers after a noun list whose order does not match them. The Plain sentence keeps first-appearance order, so the item 12.9 contract in the docstring ("EXACTLY the records, the count, the total and the markers of the technical form below, in the same order") no longer holds for the noun order.
- Reproduction: scratch probe, findings in slot order [Gene "BRCA1", Article "A1.", Clinical trial "T1", Article "A2."], subject BRCA1:
  - branch Researcher: `Found 2 papers, 1 gene record and 1 clinical trial record for BRCA1 [1][2][3][4].` A reader maps [1][2] to the two papers; [1] is the gene and [3] is the trial.
  - branch Plain: `I found 1 gene, 2 published papers and 1 clinical trial related to BRCA1 [1][2][3][4].`
  - develop Researcher: `Found 1 gene record, 2 article records and 1 clinical trial record for BRCA1: BRCA1 [1], A1. [2], T1 [3] and A2. [4].`
- Why it matters: a researcher who taps the first chip after "2 papers" lands on a gene record. Marker integrity in the sense that every [n] still points at its record holds; what is lost is the reader's ability to tell which record a marker is, which the names used to give. Related to J-131-03 (names dropped for non-papers), but this is the ordering, which would remain even if J-131-03 were fixed by naming non-papers after the paper count.
- NOT FIXED

### A-131-03: paper titles reached through a projected column still paste inline, as "derived records"
- Severity: minor (unsure how often a live plan projects article titles; "derived records" has reached the count line live before, F-8.6-P03 in `tracker/phase_8.6.md`)
- What: paper detection keys on `entity_type` alone (`answer_layout.py:1941-1944`). A graph query that projects a scalar column (`RETURN a.title, a.pmid`) yields rows typed "derived" (`cypher_provenance.py:934`), cited to the PubMed page when the projected id resolves. Those rows are not papers to `_lead_in_nouns`, so their titles are still named inline, and the noun is the code word "derived".
- Reproduction: scratch probe on the branch, two findings with `entity_type="derived"`, `field="title"`, values "BRCA1 and breast cancer." and "A second paper.", source_url `https://pubmed.ncbi.nlm.nih.gov/111/` and `/222/`, subject BRCA1:
  - Researcher: `Found 2 derived records for BRCA1: BRCA1 and breast cancer [1] and A second paper [2].`
  - Plain: `I found 2 records related to BRCA1 [1][2].`
- Why it matters: the card's rule "papers are counted, never named" holds only when the row kept its graph label. A model-written query (the Plan tier writes one when no template fits) can route the same papers around it. The source page is a PubMed page, so the signal that this is a paper is available (`source_page_key`), but the code does not use it.
- NOT FIXED
- Addendum to A-131-02, end to end on the real fixture: `write_node` on `test_write_answer_structure._mixed_state("researcher")` (graph diseases, live trials, live papers; scratch pytest file outside the repository importing the test module's helpers, model stubbed with its `_restating`) opens `Found 2 papers, 3 disease records and 2 clinical trial records for BRCA1 [1][2][3][4][5][6][7].` The papers are [6] and [7] (`ne-mixed-6`, `ne-mixed-7`); [1] to [3] are the diseases. The first two chips after "2 papers" are both disease records.

### A-131-04: the heading right under "Found 2 papers" still reads "Pubmed records found"
- Severity: minor
- What: the listing heading below the count line is built elsewhere and still uses the record type, so the reader sees "papers" in the first line and "Pubmed records" as the section heading directly under it, with rows reading "Pubmed title: ...". The card names "pubmed records" as the wording to remove.
- Reproduction: same scratch run, `write_node(_papers_state("researcher"))`, tokens in reading order:
  - `claim 'Found 2 papers [1][2]. '`
  - `heading 'Pubmed records found\n\n'`
  - `table_row 'Pubmed title: Caffeine ingestion and endurance cycling performance in trained athletes [1]. '`
  - The mixed state gives the same `'Pubmed records found'` heading after `Disease records found` and `Clinical trial records found`.
- Why it matters: one answer now uses two nouns for one set of records, side by side. Together with A-131-01 (offer and note) the card's "pubmed records" fix holds in one sentence of four places the reader sees. I did not check whether the web UI renders the heading token's text or substitutes its own; the table header in the same answer is "Paper" (asserted at `test_write_answer_structure.py:820`), so the heading and the header also disagree.
- NOT FIXED
- Addendum to A-131-04: the heading is `f"{noun[:1].upper()}{noun[1:]} records found"` at `core/graph.py:13712-13714`, with `noun = entity_type_noun(raw_type)` (`core/graph.py:13635`). Called directly on the branch, `entity_type_noun` gives the headings `Variant record records found` (dbSNP, ncbi_dbsnp's row type), `Pubmed records found`, `Article records found` and `Publication records found`. So a dbSNP answer opens `Found 1 variant record for rs334: rs334 [1].` over a heading `Variant record records found`: the card's "record records" moved from the first line to the heading below it. Heading built from the token, not run in a browser.

### A-131-05: with titles gone, the count line no longer shows the reader that the papers are off the subject
- Severity: unsure (a judgment about what the line is for; the titles are still in the list below)
- What: the subject phrase "for BRCA1" comes from the plan's resolved entity (`_summary_subject`), not from the papers. Before this change the titles sat inline and a reader could see at once when they were about something else. Now the first line is a bare assertion that N papers were found for the subject, which reads as an answer whatever the papers are about.
- Reproduction: scratch probe, two Article findings titled "TP53 in cancer." and "EGFR signalling.", subject BRCA1:
  - branch: `Found 2 papers for BRCA1 [1][2].`
  - develop: `Found 2 article records for BRCA1: TP53 in cancer. [1] and EGFR signalling. [2].`
  - The measured live shape this matters for is F-8.6-RA04 (`tracker/phase_8.6.md:478`): off-topic questions answered from a keyword PubMed list, where develop's line, `Found 5 pubmed records: Proteomic differences in apple spur buds ... [5], ...`, showed the mismatch in the first sentence. On the branch that shape opens `Found 5 papers [1]...[5].` (the subject is empty for a topic question, as `_papers_state` shows: `Found 2 papers [1][2].`).
- Why it matters: "A confident wrong record is worse than a missing one" (decide-from-the-users-chair). The trust line and risk tag do not read the count line, so nothing else on the screen changes to compensate. Not a regression in the facts the line states, only in what it lets the reader check at a glance; filed for the owner's judgment.
- NOT FIXED

### A-131-06: two checks in the owner's gate document go stale, and one can no longer fail
- Severity: minor
- What: the pull request changes the count line's wording but not `testing/Test_queries_and_workflows.md`, the document that is the gate (owner, 2026-09-26).
  - Line 1576: "Neither answer reads "Found 5 pubmed records:" followed only by a list of titles with no explanatory sentence." The branch never writes "pubmed records:" in the count line, so this check passes on the defect it was written for: an answer that is only `Found 5 papers [1][2][3][4][5].` over a list of titles, with no explanatory sentence, now satisfies it.
  - Line 133: "Both modes open with one sentence counting what was found and naming it". On the branch any answer with a paper in it no longer names anything (J-131-03), and Plain never named.
- Reproduction: `sed -n 1576p testing/Test_queries_and_workflows.md` and `sed -n 133p` on the branch; `git diff origin/develop...HEAD --stat` lists no file under `testing/`. The bare-list shape is the `_papers_state` run above: `Found 2 papers [1][2].`, then the heading and two title rows, no prose in that stubbed run.
- Why it matters: the tester following the gate document is told to look for wording the product can no longer produce, so the check reports a pass whether or not the answer explains anything.
- NOT FIXED

### A-131-07: merging paper types into one noun turns two records of one paper into "2 papers"
- Severity: unsure (no code path in `core/` names `pmc`, so a live answer holding both copies is speculative; the planner may still choose `db=pmc`, a `SearchDb` value)
- What: the per-page dedup keys on the source page, and a paper's PubMed page and its PMC page are two pages. Develop counted them as two records of two types, which was true. The branch folds every paper type into "papers", so the line now states a count of papers that is wrong.
- Reproduction: scratch probe, findings [type "pubmed", title "Same paper.", `https://pubmed.ncbi.nlm.nih.gov/31234567/`] and [type "pmc", title "Same paper.", `https://pmc.ncbi.nlm.nih.gov/articles/PMC6543210/`], no subject:
  - branch: `Found 2 papers [1][2].`
  - develop: `Found 1 pubmed record and 1 pmc record: Same paper. [1] and Same paper. [2].`
- Why it matters: "papers" is a claim about the world, "records" a claim about the retrieval. The new noun is only as honest as the dedup beneath it. The same applies to a preprint and its published version, though no preprint type is emitted today.
- NOT FIXED

## Checks that held, with evidence
- Every paper type a tool emits today is caught: the graph's only paper label is "Article" (`tools/graph_schema_constants.py:45`), PubTator3 rows are "Publication" (`core/graph.py:5088`), efetch rows take `record.db` and the paper databases in `SearchDb`, `FetchDb` and `SummaryDb` are only "pubmed" and "pmc" (`tools/ncbi_efetch_schemas.py:175-214`). Probes: "pmc", "pubmed", "Publication", "article", "Article" all give "N papers".
- Types the table does not know still name their titles, but no tool emits them: "Preprint" gives `Found 2 preprint records for BRCA1: Pre [1] and Pre2 [2].`, "Review", "BookChapter", "books", "PMC Article" and "PubMed Central" likewise.
- A gene type containing "article" is not taken for a paper: the lookup is an exact key after removing case and punctuation (`answer_layout.py:1398-1400`). "GeneArticle" gives `Found 1 gene article record for BRCA1: x [1].`
- Same paper from the graph and from live efetch (`.../1/` and `.../1`) counts once: `Found 1 paper for BRCA1 [1].`
- Card 133's off-by-one is neither better nor worse: the diff does not touch `counted`, the per-page dedup, `markers` or `total`; every probe gives the same totals and marker sets as develop.
- Markers: in every probe each [n] still belongs to a counted record or a named linked disease, none orphaned or duplicated. What changed is which record a reader can tell a marker is (A-131-02).
- Saved answers store `answer_markdown` as shown (`feedback/history.py:325-356`), so a reopened answer renders the line it was saved with. Read, not run.
- CLI and GraphQL: both consume the same token stream (`contracts/token_order.joined_text`, `adapters/cli/main.py:1429`), and no adapter matches "Found " or "records:". Read, not run through either surface.
- The frontend's `parseRecordLine` (`AnswerScreen.tsx:430-445`) needs a type-plus-field prefix and cannot match a line opening "Found". `HIDDEN_NOTE_PATTERNS` matches only "Note: ... further".

## Verdict
- FAIL against the card's stated goal, in addition to the judge's J-131-02 and J-131-03. The count line itself no longer says "pubmed records" or "record records", but the same words survive on the same screen in the offer, the note and the heading under it (A-131-01, A-131-04), and the mixed-answer line now puts its nouns in an order its markers do not follow (A-131-02), shown end to end on the real `_mixed_state` fixture.
- None of these sits inside a fix made during an earlier round of this phase; this is round one. A-131-02 is a direct product of this change's `parts.insert(0, ...)`.
- Verified by my own probes: A-131-01, 02, 03, 04 (the token and the heading function, not a browser), 05, 07, and the paper-type, dedup, count and marker checks above. End to end through `write_node` with the test module's stubbed model: the `_papers_state` and `_mixed_state` outputs.
- Read only: A-131-06 (document text), the saved-answer, CLI and GraphQL surfaces, and whether the web UI shows the heading token's text as is.
- Worktree left as found: `git diff HEAD --stat` empty, `git status --short` shows only `?? frontend/node_modules`. All probes ran from the scratchpad; develop's `src` was unpacked there by `git archive`.
