# Cards 133 and 137 diagnosis, 2026-10-22

Read-only diagnosis of two cards filed from the 2026-10-18 browser retest (`testing/Developer/reports/2026-10-18_browser_retest/report.md`, rows 15, 31, 37, 40 and the defects table). Code is cited at `origin/develop` commit `bae47b6e`. The retest ran on `6935a0a3`; nothing merged since then touches the code named here (checked with `git log 6935a0a3..origin/develop` over the four files). No model was called and no NCBI call was made beyond one ESummary lookup of five gene names.

In short: card 133 and the first half of card 137 are one defect. The answer's record list keeps the graph's gene record and the live NCBI Gene record as two rows when their names differ, while every count on the answer treats them as one page. The second half of card 137 (the "DNA REPAIR PATHWAY DISEASE" heading over a fragment) is a separate defect in the grounding pass, and confirming its exact cause needs one live run.

## Table of contents

- [What a person sees](#what-a-person-sees)
- [Card 137, part 1: the gene record listed twice](#card-137-part-1-the-gene-record-listed-twice)
- [Card 133: the list and the sources count differ by one](#card-133-the-list-and-the-sources-count-differ-by-one)
- [Card 137, part 2: a heading over one broken fragment](#card-137-part-2-a-heading-over-one-broken-fragment)
- [Smallest true fixes](#smallest-true-fixes)
- [Do 133 and 137 touch the same code](#do-133-and-137-touch-the-same-code)
- [Runs that would confirm what code reading cannot](#runs-that-would-confirm-what-code-reading-cannot)
- [Out of scope, seen on the way](#out-of-scope-seen-on-the-way)

## What a person sees

| Card | Answer | What the reader sees |
|---|---|---|
| 137 | `What does BRCA1 do?`, the follow-up "and what about it in children?" | The BRCA1 gene record twice: "BRCA1 DNA repair associated" and "BRCA1" |
| 133 | Query 24 (MLH1 and MSH2) | List total 24, sources 23 |
| 133 | Query 29 (the CFTR window) | 71 against 70 |
| 133 | Query 25 (TP53 GEO datasets) | 23 against 22 |
| 133 | Query 116 (TP53 orthologs), Researcher | "Found 40" over a table of 41 (row 4), sources 40 |
| 137 | Query 1, Researcher | A heading "DNA REPAIR PATHWAY DISEASE" over one sentence, "The association with Fanconi anemia complementation group S." |

The rule broken: card 22, "one count everywhere" (DECISIONS.md, 2026-10-06, the card 22 rows), and owner decision D14 (`testing/Board_plan.md:223`): "N sources" means distinct records everywhere.

## Card 137, part 1: the gene record listed twice

### The chain, step by step

1. A gene question earns a second, live lookup of the first gene. `plan_node` appends an `ncbi_efetch` gene report for the first Gene CURIE Think resolved (`src/system_03_search_agent/core/graph.py:7290-7299`, `_first_gene_curie`). Only the first gene gets it, which is why every case is off by exactly one.
2. The two layers name the gene differently. The graph's Gene row cites field `name` = "BRCA1 DNA repair associated"; the live Datasets row cites field `symbol` = "BRCA1". The code already documents this pair as "the system's own single most common dual-layer citation pair" (`graph.py:11796-11834`, `_FIELD_NAME_ALIASES`).
3. The two links differ by a trailing slash. The graph builds `https://www.ncbi.nlm.nih.gov/gene/672` (`src/system_03_search_agent/tools/cypher_provenance.py:231`); Datasets builds `.../gene/672/` (`src/system_03_search_agent/tools/ncbi_datasets_actions.py:327`).
4. Both rows get the same identifier cell. The live row has `curie` "" and its `gene_id` withheld (`graph.py:8273-8288`, `graph.py:7747`), so `record_identifier` falls back to the citation's own `source` "gene" and `source_id` "672" and writes "NCBIGene:672" (`src/system_03_search_agent/synthesis/answer_layout.py:551-555`, `558-600`). The graph row's CURIE is also "NCBIGene:672".
5. The row labels differ. `record_label` takes the first name-like field (`answer_layout.py:934`, `941-983`): "BRCA1 DNA repair associated" for the graph row, "BRCA1" for the live row (its fields carry `symbol`, not `name`).
6. The listing refuses to merge them. Card 104 keys a candidate repeat on (page key, identifier), which match (`graph.py:13363-13369`), but `merged_cells` then requires the name cells to be equal (`graph.py:13371-13389`: `shown[0] != later[0]` returns None). Both the Plain language list (`graph.py:13597-13607`) and the Researcher table (`graph.py:13776-13795`) go through it, so both depths show two rows.

### Why the rule is there

Card 104's first build merged this exact case (case B in `testing/Developer/reports/2026-10-08_card103_104/diagnosis.md`). Its judge found J-103-05: graph edges with no CURIE of their own borrow their start gene's CURIE and page (`cypher_provenance.py:741-757`, marked `_cited_via_endpoint_curie`), so three ortholog edges merged under one edge's label. The fix round answered by requiring every cell, the name included, to agree, and pinned case B as two rows in `tests/system_03_search_agent/core/test_write_answer_structure.py:1527-1538` (`test_one_page_with_two_names_stays_two_rows`, which asserts exactly the "BRCA1 DNA repair associated" and "BRCA1" pair). The defect is therefore pinned by a passing test. The DECISIONS.md row for card 104 (2026-10-08) reads "two table rows merge only when their page key and identifier both match"; the name condition came in with the fix round.

### Reproduced offline

An offline probe, not committed, written in the scratchpad against an export of develop and reusing the test file's own helpers. It used two Gene rows: `.../gene/672` named "BRCA1 DNA repair associated" and `.../gene/672/` with symbol "BRCA1". Result:

| Depth | Rows shown | Citations | Distinct pages | Opening line | Trust line |
|---|---|---|---|---|---|
| Researcher | 2: `["BRCA1 DNA repair associated", "NCBIGene:672"]`, `["BRCA1", "NCBIGene:672"]` | 2 | 1 | "Found 1 gene record for BRCA1: BRCA1 DNA repair associated [1]." | "Based on 1 source cited, from NCBI Gene" |
| Plain language | 2: "BRCA1 DNA repair associated", "BRCA1" | 2 | 1 | "I found 1 gene related to BRCA1 [1]." | "Based on 1 source cited, from NCBI Gene" |

The two existing card 104 tests also pass on develop's code (`test_one_page_with_two_names_stays_two_rows`, `test_the_plain_language_list_does_not_repeat_a_record`).

## Card 133: the list and the sources count differ by one

The same two rows, counted two ways:

| Surface | Rule | BRCA1 example |
|---|---|---|
| Record list (rows, the table's "of N", the last chip number) | One row per (page, identifier) only when names agree (`graph.py:13371-13389`) | 2 rows, chips [1] and [2] |
| Opening count line ("Found 40") | One record per page, `source_page_key` (`answer_layout.py:1861-1879`) | 1 gene |
| Sources heading and meta line | One card per page, `sourcePageKey`; a page cited from two layers is one card naming both (`frontend/src/components/screens/AnswerScreen.tsx:712-731`, `775-819`) | 1 source "from 2 layers" |
| Trust line "Based on N sources cited" | `source_page_key` (`src/system_03_search_agent/contracts/events.py:196`) | 1 |

Every count except the list follows card 22's page key; the list follows card 104's stricter name rule. Each of the four answers is anchored on a gene, the first gene gets the live lookup, and the graph's name differs from the symbol, so each shows one extra row. NCBI Gene's names, checked by ESummary today:

| Gene | Graph row would read (NCBI name) | Live row reads (symbol) | Answer |
|---|---|---|---|
| 4292 | mutL homolog 1 | MLH1 | Query 24 |
| 1080 | CF transmembrane conductance regulator | CFTR | Query 29 |
| 7157 | tumor protein p53 | TP53 | Queries 25 and 116 |
| 672 | BRCA1 DNA repair associated | BRCA1 | Query 1, `What does BRCA1 do?` |

Why the tester saw it as a duplicate only on BRCA1: there the symbol sits inside the full name; "mutL homolog 1" and "MLH1" do not look like the same record, so the extra row reads as a count error instead.

Confidence: the BRCA1 duplicate is confirmed by code, the passing test and the offline probe. That the four 133 answers carry this same pair (and not, say, a paper cited by title and abstract) follows from the code and from "exactly one" on four gene-anchored answers, but was not watched live; the confirming run is named below.

## Card 137, part 2: a heading over one broken fragment

### Why the heading shows

- A model-written heading is shown, Researcher only, when `heading_is_supported` accepts it and at least one sentence of the paragraph under it survives (`graph.py:13860-13882`).
- `heading_is_supported` checks each content word against the words of all the answer's findings plus a small section vocabulary (`answer_layout.py:108-127`, `217-246`). "disease" is in the vocabulary; "DNA" and "repair" come from the gene's own name, "BRCA1 DNA repair associated"; "pathway" must come from another finding's words (a paper title, for instance). The words are licensed by the answer as a whole, not by the paragraph the heading sits over.
- So the heading is a symptom: it stands because one sentence of its paragraph survived, and that sentence is a fragment.

### Why the fragment survives

- The grounding pass binds each clause to the marker that ends it, and strips any unmarked text that asserts something (`src/system_03_search_agent/synthesis/grounding.py:1534-1548`).
- A strip in the middle of a sentence drops the whole sentence (T-6.2-15, `grounding.py:1791-1794`), and so does a held copied clause (card 101, `grounding.py:1806-1807`).
- A strip at the end is kept on purpose (`grounding.py:1776-1790`): "A [1], B [2], and C [3]" losing C leaves a grammatical list. The owner accepted that rule.
- The only end-strip guards are unbalanced brackets or quotes, a lowercase record fragment, or a bare pronoun opening (`grounding.py:1820-1862`). None looks for a missing verb.
- The likely path: the writer produced "The association with Fanconi anemia complementation group S [4] <is ...>." The unmarked predicate after [4] was stripped as an uncited claim, and the verbless prefix shipped. The other path is that the writer wrote the fragment itself. Code reading cannot tell the two apart; the run below can.

## Smallest true fixes

### Fix A, for card 137 part 1 and card 133 together

What a person would notice: "a question about one gene lists that gene's record once, with both its citation numbers, and the list, the Found line, Sources and the Based on line all give the same number."

- Change: in `_answer_parts`'s listing, two rows that already share a page key and identifier are the same record, and may merge although their names differ, when all three hold:
  - the identifier is the record's own: neither row's fields carry `_cited_via_endpoint_curie` or `_cited_via_gene_curie` (`cypher_provenance.py:221`, `747`, `774`), which keeps J-103-05's borrowed edge rows apart;
  - the identifier is not blank (the no-identifier rule pinned at `test_write_answer_structure.py:1821-1850` stays);
  - both rows are the same kind of record, `entity_type_noun` equal ("Gene" and "gene" are both "gene"), which keeps derived rows and edge rows apart.
- Name cell: never hide a name. Keep the first name and add the second in brackets when it differs: "mutL homolog 1 (MLH1)", "BRCA1 DNA repair associated (BRCA1)". The other option, the first name alone, was card 104's original recommendation; the fix round rejected it because a merge then hides a name. Every other cell keeps today's rule (a blank takes the other row's value, two values keep two rows).
- Files and lines:
  - `src/system_03_search_agent/core/graph.py:13355-13440` (`ListedRow` gains the finding's noun and a borrowed flag; `merged_cells` takes a same-record flag; `merge_into` passes it);
  - `graph.py:13597-13607` and `13776-13795` (the two callers pass the finding).
- Tests:
  - rewrite `test_one_page_with_two_names_stays_two_rows` (`test_write_answer_structure.py:1527-1538`) to expect one row with both markers;
  - add a graph row plus a live gene row (no CURIE, `source` "gene", trailing slash) in both depths, asserting rows equal pages, the opening count and the trust count;
  - add controls that must stay separate: three borrowed ortholog edges, a derived row on the gene's CURIE, and a different identifier on one page (the existing test at `test_write_answer_structure.py:1550`).
  - Mutations: drop the borrowed check and the edge control goes red; drop the noun check and the derived control goes red.
- No frontend change. Sources already merge the two citations into one card "from 2 layers" (`AnswerScreen.tsx:775-819`), and the count line and trust line already count pages.
- Owner rules:
  - Code verifies identity (an equal record identifier read from the record), and nothing is decided by wording.
  - No test question is lifted into a prompt.
  - No record is invented or renamed: a merged row shows both retrieved names, and both citation numbers open the same NCBI page, so it cannot become a confident wrong record.
- Risk: medium-low.
  - The real risk is an over-merge of two different records. That needs the same page key, the same identifier read from each record, and the same record kind, which together mean the same record.
  - It reverses a fix-round rule pinned by a test, so it needs its own DECISIONS.md row. The 2026-10-08 card 104 row already words the rule as "page key and identifier both match", so the lead can decide it from the user's chair.
  - Saved answers replay their stored rows, so answers saved before the fix keep two rows.

### Fix B, for card 137 part 2 (after the confirming run)

What a person would notice: "an answer never shows a heading over half a sentence."

| If the run shows | Smallest fix | Files and lines | Rule check | Risk |
|---|---|---|---|---|
| An unmarked predicate was stripped after the last marker | Treat an end strip of unmarked asserting text like a middle strip: drop the whole sentence. A failed marked clause at the end ("A [1], B [2]" losing C) keeps today's rule. The heading then goes with its emptied paragraph, through the existing `graph.py:13860-13882` | `grounding.py:1770-1810`, the segment walk at `1534-1548` records which kind of strip happened | Structural, like T-6.2-15 and item 9.7; no word lists, no model | Medium. A sentence with an uncited tail loses its cited front half from the prose; the records list still shows every record. It changes an owner-accepted rule, so the owner decides |
| The writer wrote the fragment itself | Code cannot judge completeness without a word list. Send it to the existing guard-tier sentence check (card 101) as a yes/no on "is this a complete statement" | `grounding.py` around `1800-1810` and `src/system_03_search_agent/synthesis/sentence_check.py` | A classifier model decides, code only acts on its answer | Medium-high, and adds model time; it overlaps card 101, which is "Design with you first" |

Tightening `heading_is_supported` to the paragraph's own findings would hide this heading but leave the fragment, so it is not the true fix.

## Do 133 and 137 touch the same code

| Pair | Same code | Build order |
|---|---|---|
| 133 and 137 part 1 | Yes, one defect: `graph.py:13355-13440` and its two callers | Build as one change. Fix A closes 133, and 133's check is the count assertions in Fix A's tests |
| 137 part 1 and 137 part 2 | No: `graph.py` listing against `grounding.py` sentence commit | Can be built in parallel |
| 137 part 2 and card 101 | Yes, the same block of `grounding.py` (`1791-1810`, `held_for_check`) | One after the other |
| Fix A and cards 121, 130, 131 | Near, not the same lines: those touch the count line and headings in `answer_layout.py` and the notes in `graph.py`; 131 merged today | Rebase Fix A on develop after any of them merges |

## Runs that would confirm what code reading cannot

Blocked-stop items, not run here (no model calls allowed):

1. For card 133's four answers: on deployed develop through the API as a guest, run query 24 in Plain language and query 116 in Researcher. In the stream, find the list rows (`list_item` or `table_row` tokens) whose first marker's citation events share one `source_page_key`, one from `cypher_query` (`layer_1_graph`) and one from `ncbi_efetch` (`layer_2_api`), named "mutL homolog 1" and "MLH1", and "tumor protein p53" and "TP53". Expect exactly one such pair per answer. Queries 25 and 29 the same if wanted.
2. For card 137 part 2: query 1 in Researcher with tracing on. Read the write step's raw writer reply and the grounding result for the sentence holding "Fanconi anemia complementation group S". Check whether an unmarked predicate after its marker was stripped (Fix B, first row) or whether the writer wrote the fragment (Fix B, second row). It is a model output, so one run may not show it; up to five runs, as the owner's answer-quality rule asks.

## Out of scope, seen on the way

- Row 6: query 23 reads "1 source cited from 2 layers" with a LitVar2 citation [2] sharing the dbSNP page. That is card 22's page-key merge working as designed, but the list shows one row while chip [2] sits only in the prose. It is a related count question, not card 133.
- Rows 12 and 14: citation numbers run past the count (14 against 12, 3 jumping to 74) because a paper's live abstract takes its own number. Same family: numbers count citations, totals count pages. It is a different code path (`_pubmed_abstract_rows`), so it is not fixed by Fix A.
