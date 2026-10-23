# Card 134 adversary round, 2026-10-22

Branch fix/card134-papers-keep-their-titles (pull request #299). Findings are appended as they are established. Ids A-134-01 and up.

## Findings

### A-134-01: A non-English paper's translated title is dropped, and the row then says "Title not retrieved" although the title was retrieved
- Severity: major
- What: PubMed writes the English translation of a non-English title inside square brackets. PubTator3 passes that through as the title passage. `clean_article_title` (`synthesis/article_titles.py:128`, `_BRACKETED_ONLY = ^\[[^\[\]]*\]\s?\.?$`, applied at line 191) treats every fully bracketed title as a placeholder like "[Not Available]." and returns None. The row title is then None (`core/graph.py:5101`), so `record_label` returns `UNTITLED_PAPER_LABEL` (`synthesis/answer_layout.py:982-984`). The label states a fact that is false: the run holds the paper's real title.
- Reproduction: one live PubTator3 export (2026-10-22, `pmids=33855558,9500320,20137807,42851203,42477928,41699232,34370262,28340353,28340353`) and one ESummary for the same ids, then the branch's `_parse_publication` and `clean_article_title`:
  - 42477928 (lang `chi`): PubTator3 title `'[Clinical and familial characterisation of ovarian cancer patients with germline mutations in the BRCA1/2 gene and the current status of prevention in high-risk groups].'`, shown title `None`
  - 42851203 (lang `chi`): PubTator3 title `'[Macrophage MerTK modulates the cGAS-STING pathway to drive immune evasion in BRCA1/2-mutated breast cancer].'`, shown title `None`
  - Both PMIDs came from ESearch `chinese[la] AND BRCA1[ti]`: 2 of the first 2 Chinese BRCA1 papers are affected. Every non-English PubMed record whose English title is bracketed is in this class.
- Why it matters: for a researcher this is the one place the honest label is dishonest. "Title not retrieved" says the system could not get the title; it had it. The bracket rule was written for placeholders and is wider than placeholders. The rule is pre-existing (card 125 era) and shared with graph papers, but this card is what turns its None into a sentence on screen for enrichment papers. Develop showed the number, which was ugly but not false.
- NOT FIXED

### A-134-02: A retracted paper is now listed under its full, unqualified title, with nothing saying it was retracted
- Severity: major (unsure whether it belongs to this card or to a separate card; the gap is product-wide)
- What: PubTator3's title passage carries the original title of a retracted paper with no retraction mark, and the PubTator3 response carries no publication type. The branch shows that title as the row's name. PubMed itself records the retraction only in `pubtype` ("Retracted Publication"), which this row never sees. `grep -rni retract src` finds only a grounding comment (`synthesis/grounding.py:942`), so no surface flags a retraction for any paper.
- Reproduction: same live PubTator3 export and ESummary as A-134-01, through the branch's `_parse_publication` and `clean_article_title`:
  - 9500320: shown `'Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children.'`; ESummary pubtype `['Journal Article', "Research Support, Non-U.S. Gov't", 'Retracted Publication']`
  - 20137807 (the retraction notice): shown `'Retraction--Ileal-lymphoid-nodular hyperplasia, ...'`, pubtype `['Retraction Notice']`. This one says so only because its title does.
  - Develop for the same row: `9500320 PMID:9500320`, which made no claim.
- Why it matters: "A confident wrong record is worse than a missing one." A clinician asking about autism and the gut now sees the retracted Wakefield paper named in plain words, in a list headed as records found, indistinguishable from a sound paper. On develop it was an opaque number they had to click. The title makes the paper look like it supports the question; the retraction is only visible on PubMed. The same holds for the PubMed EFetch path, so this is not a regression in kind, but this card adds a new surface on which it shows.
- NOT FIXED

### A-134-03: PubTator3 drops characters PubMed's title keeps (a registered mark), so the shown title is not PubMed's
- Severity: minor
- What: separate from J-134-01's closing full stop. PubTator3's title passage removes non-ASCII marks that PubMed keeps, and leaves a double space where they were. The branch collapses the space and shows the rest.
- Reproduction: same live export as A-134-01. 34370262: PubTator3 text `'Kaftrio  - Dreifachkombi bei Cystischer Fibrose : CFTR-Modulator.'`, shown `'Kaftrio - Dreifachkombi bei Cystischer Fibrose : CFTR-Modulator.'`, ESummary `'Kaftrio(®) - Dreifachkombi bei Cystischer Fibrose : CFTR-Modulator.'`. The diagnosis's claim that the titles are PubMed's words once tags are removed does not hold character for character; 1 of 8 live titles differs here.
- Why it matters: cosmetic for "(®)". The worry is the class: if PubTator3 drops other non-ASCII characters (Greek letters such as alpha or beta in gene and protein names, the plus-minus sign), a title can change meaning ("TGF-β" read as "TGF-"). Not observed in my 8 titles; filed so it is measured.
- NOT FIXED

### A-134-04 (evidence for A-134-01 and A-134-02, end to end): the screen as a researcher sees it
- Severity: evidence for A-134-01 and A-134-02
- Reproduction: my own probe drives `graph.write_node` with the writer faked (a sentence that grounds nothing, so the code-built list is the page), and feeds the live PubTator3 documents for 42477928, 42851203 and 9500320 through `_parse_publication` and `_layer_tool_output_to_structured_fields`. I ran the same probe on the branch and on a `git archive` copy of develop base `bae47b6e`.
  - Branch, Researcher: `['Title not retrieved', 'PMID:42477928']`, `['Title not retrieved', 'PMID:42851203']`, `['Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children.', 'PMID:9500320']`
  - Branch, Plain: `Published paper`, `Published paper`, then the retracted paper's full title
  - Develop, Researcher: `['42477928', 'PMID:42477928']`, `['42851203', 'PMID:42851203']`, `['9500320', 'PMID:9500320']`; Plain: three `Published paper`
- So on the branch, the only paper with a readable name is the retracted one, and the two genuine papers are marked as having no title.
- NOT FIXED

### A-134-05: PubTator3 transliterates non-ASCII characters in titles, so 5 of 6 sampled titles differ from PubMed's (measured follow-up to A-134-03)
- Severity: minor (it partly answers A-134-03's worry: Greek letters are spelled out, not dropped)
- What: PubTator3 writes PubMed's title in ASCII. It spells out Greek letters, flattens superscripts and drops marks. The branch shows PubTator3's version, so the title on screen differs from the one on the PubMed page the row links to.
- Reproduction: one ESearch (`(β-catenin[ti] AND BRCA1[ti]) OR (Ca2+[ti] AND CFTR[ti]) OR (α-synuclein[ti] AND GBA[ti])`), then one PubTator3 export and one ESummary for the 6 ids, run through the branch's `_parse_publication` and `clean_article_title`:
  - 42560815: shown `'... better alpha-synuclein clearance ...'`, PubMed `'... better α-synuclein clearance ...'`
  - 42784884: shown `'CFTR correctors suppress Ca2+-cAMP signaling ...'`, PubMed `'... Ca²⁺-cAMP ...'`
  - 39702307: shown `'... Ca2+-mobilizing agonists normalizing abnormal Ca2+ levels ...'`, PubMed `'... Ca(2+)-mobilizing ... Ca(2+) levels ...'`
  - 42378827 and 39940047: `alpha` against `α`
  - 40882878: identical
- Why it matters: the meaning holds in every sampled case, because letters are spelled out rather than lost. But the diagnosis's statement that these are PubMed's titles is true only up to transliteration, and someone who copies the shown title into a PubMed search for "α-synuclein" would be searching a string that is not on screen. Since the run often also holds PubMed's own title (the EFetch row for the same PMID), which source names the row decides which spelling the reader sees (see J-134-04 for that order dependence).
- NOT FIXED

### A-134-06: The summary sentence's new "name an untitled paper by its PMID" branch is unreachable; its test pins a path production never takes
- Severity: minor (dead code with a test that passes, not a user-visible defect)
- What: `summary_label` gained a Card 134 branch (`synthesis/answer_layout.py:1788-1792`) that returns `PMID:<n>` for an untitled `Publication`. Its only caller (`answer_layout.py:2007`) filters with `if not _is_paper_finding(f)`, and `_is_paper_finding` is True for `Publication` (probe: `_lead_in_nouns('Publication')` returns `('paper', 'papers')`, `_is_paper_finding(entity_type='Publication')` returns `True`). Papers are counted in the summary ("Found 5 papers [1]...[5]"), never named, so the branch cannot run in a real answer. `test_the_summary_names_an_untitled_paper_by_its_pmid` calls `summary_label` directly.
- Reproduction: in a `git archive HEAD` scratch copy, the branch's condition is replaced with `if False:`. Running `tests/system_03_search_agent/synthesis`, `core/test_enrichment_paper_titles.py`, `core/test_graph.py` and `core/test_topic_search.py` gives `2 failed, 1634 passed`. The failures are the author's direct unit test and `test_card23_the_screen_finds_the_line_by_the_words_that_ship`, and the second is an artifact of the scratch copy (it needs `frontend/src/hooks/useRunView.ts`; it passes in the worktree). No end-to-end test sees the change. My own `write_node` probes, Researcher and Plain, with untitled papers show `Found 3 papers [1][2][3].` on both branch and develop.
- Why it matters: the diagnosis and the code comment describe a summary behaviour no user will ever see. A reader of the code believes the summary names untitled papers by PMID. If someone later lets papers be named in the summary, the new behaviour arrives untested end to end.
- NOT FIXED

### A-134-07: Removing `<sup>` and `<sub>` fuses a superscript into the text before it, which can turn an exponent into a range and alter variant notation
- Severity: unsure (I observed no live PubTator3 title with `<sup>`; PubTator3 already writes `Ca²⁺` as `Ca2+` itself, see A-134-05)
- What: `_FORMATTING_TAG` (`tools/pubtator_annotate.py:691-693`) deletes `<sup>`/`<sub>` and puts nothing in their place. The judge (J-134-03) treated `Ca2+` as an acceptable loss. These are cases where the deletion produces a different statement.
- Reproduction: `clean_article_title(_publication_title([{"infons":{"type":"title"},"text":T}]))` on the branch:
  - `'Mutation rate of 10<sup>-9</sup> per site per generation'` gives `'Mutation rate of 10-9 per site per generation'` (ten to the minus nine now reads "10 to 9")
  - `'Risk at P &lt; 5 x 10<sup>-8</sup>'` gives `'Risk at P &lt; 5 x 10-8'`
  - `'Variants c.68_69delAG<sup>a</sup> in <i>BRCA1</i>'` gives `'Variants c.68_69delAGa in BRCA1'` (a footnote letter joins the HGVS string and reads as part of the deleted sequence)
  - `'x<sup>2</sup> + y<sup>2</sup>'` gives `'x2 + y2'`
- Why it matters: the owner's rule names this exact risk, a confident wrong record. Rendering `^` or `(-9)` in place of the tag (PubMed's own ESummary writes `Ca(2+)`, A-134-05) would keep the meaning. No test covers sup or sub inside a number or a variant.
- NOT FIXED

### A-134-08: The bracket rule is inconsistent for translated titles: an inner bracket keeps the title, its absence drops it
- Severity: minor (follow-on to A-134-01)
- What: `_BRACKETED_ONLY = ^\[[^\[\]]*\]\s?\.?$` (`synthesis/article_titles.py:128`) drops a fully bracketed title only when it has no inner bracket. Two translated titles of the same kind therefore get different treatment, decided by punctuation inside them.
- Reproduction: branch, `clean_article_title(_publication_title(...))`:
  - `'[Clinical study of BRCA1 [ER+] tumours].'` gives `'[Clinical study of BRCA1 [ER+] tumours].'` (shown)
  - live 42477928 `'[Clinical and familial characterisation of ovarian cancer patients ...].'` gives `None`, so the row shows "Title not retrieved"
  - `'[Title in Chinese]'` and `'[Not Available].'` give `None`, which is right
- Why it matters: it shows the rule tells placeholders from titles by shape alone. A real placeholder list ("Not Available", "In Process Citation", "Title in <language>") would separate them.
- NOT FIXED

### A-134-09: The same translated title shows when the PubMed row names the paper and becomes "Title not retrieved" when the PubTator3 row does
- Severity: major (it sharpens A-134-01: the system does hold the title, and shows it on another path)
- What: the PubMed EFetch row keeps a fully bracketed translated title as written. The PubTator3 row, through `clean_article_title`'s bracket rule, drops it. Whichever finding comes first in the fold names the paper (J-134-04's order dependence). So for one paper in one answer, the label is either the full title or the claim that no title was retrieved.
- Reproduction: my own `write_node` probe, the writer faked. The input is an EFetch `pubmed_abstracts` finding for 42477928 with its live title `'[Clinical and familial characterisation of ovarian cancer patients ... in high-risk groups].'`, plus the live PubTator3 document for 42477928:
  - Branch, PubMed first, Researcher: `['[Clinical and familial characterisation ... high-risk groups].', 'PMID:42477928']`
  - Branch, PubTator3 first, Researcher: `['Title not retrieved', 'PMID:42477928']`; Plain: `Published paper`
  - Develop, PubTator3 first: `['42477928', 'PMID:42477928']`
  - The same probe for 42560815: PubMed first shows `α-synuclein`, PubTator3 first shows `alpha-synuclein` (A-134-05). Develop, PubTator3 first, shows `42560815`.
- Why it matters: "Title not retrieved" is false here by the system's own evidence, and the label depends on finding order, not on the record.
- NOT FIXED

### A-134-10 (evidence, no defect): list length, order, PMID-to-title pairing and relevance are as on develop
- Severity: none, evidence only
- Pairing: `_parse_publication` reads the title from the same document whose `id` gives the PMID and the link. PubTator3 returned the 9-id batch in its own order (ascending PMID, not request order) and collapsed the duplicate 28340353. On all 14 live documents (2 batches), the title on each row is the title ESummary gives for that row's PMID, up to A-134-03 and A-134-05. I found no path where a title can attach to another paper's row. `_row_fields_for` matches on the source URL, which is built from the PMID.
- Length and order: the same `write_node` probe on branch and develop base `bae47b6e`. Live 8-document batch: 5 rows both sides, same PMIDs in the same order (20137807, 28340353, 33855558, 34370262, 41699232). Two PubTator3 calls with overlapping PMIDs in reversed order: 6 rows both sides, same order. 3-document set: 3 rows both sides. The cap is `_LAYER_TOOL_ROW_CAP = 5` after a sort by URL string (`core/graph.py:5106-5107`), unchanged.
- Relevance: `breadth_plan.plan_literature_follow_up` hands PubTator3 exactly the 5 PMIDs the PubMed abstract fetch gets (`breadth_plan.py:839-872`). So a PubTator3 title names a paper the PubMed path would have named with the same title. Showing the title adds no paper and makes no relevance claim beyond what PubMed's own row already makes when it finishes. The confident-wrong-record risks I found are A-134-02 (retraction) and A-134-07 (fused superscripts), not the title of an off-topic paper.
- Prompt and model: not re-tested (J-134-05 covers it).

## Runs

- Network: 9 read-only calls. 4 PubMed ESearch, 2 PubTator3 export (`publications/export/biocjson`), 2 PubMed ESummary, plus 1 ESearch that returned nothing (`erratum[pt] AND BRCA1[ti]`, so no erratum was tested live). No model calls.
- Probes: `_parse_publication` plus `clean_article_title` on live documents; `graph.write_node` with the writer faked, on the branch worktree and on a `git archive bae47b6e` copy of develop; one mutation in a `git archive HEAD` copy (A-134-06). Everything ran in the session scratchpad, never in the worktree.
- After all probes, `git status --short` in the worktree shows only `?? frontend/node_modules`, and `git diff HEAD --stat` is empty.

## Verdict

FAIL against the owner's rule "A confident wrong record is worse than a missing one", on two findings that are new to the screen with this card:

- A-134-01, A-134-04, A-134-09: a non-English paper whose title the run holds is labelled "Title not retrieved", which is false.
- A-134-02: a retracted paper is now named in full, with no mark, where develop showed a number.

Neither sits inside a fix from an earlier round of this card: this is round one.

| Claim | How checked |
|---|---|
| Title belongs to the row's PMID, including batched and out-of-order responses | Own probe, 14 live documents in 2 batches (A-134-10) |
| Retracted paper and retraction notice | Own probe, live 9500320 and 20137807 (A-134-02) |
| Placeholder titles | Own probe, synthetic `[Not Available].` and `[Title in Chinese]`: dropped, which is correct (A-134-08) |
| Non-English titles | Live Chinese and German (A-134-01, A-134-03); end to end both sides (A-134-04, A-134-09) |
| HGVS and angle brackets | Live 33855558 kept; synthetic sup and sub fusion (A-134-07) |
| Duplicate PMID across two tools | Own probe, both orders, both sides (A-134-09) |
| Same length and order as develop | Own probe, three sets, both sides (A-134-10) |
| Summary sentence change | Read, then a mutation run (A-134-06) |
| Erratum | Not tested live: the ESearch returned no ids |
| Read only, not probed | Production finding order in Act, frontend rendering of `cells`, PubTator3 full-text documents (none were returned) |
