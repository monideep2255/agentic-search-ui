# Cards 103 and 104: diagnosis of two answer-table defects

Diagnosis only, on `fix/card103-104-answer-tables` at develop `2182aff3`. No source or test file was changed. Both defects were reproduced offline with the real table builder, and card 103's five rows were read from the knowledge graph read-only.

## Table of contents

- [In the reader's words](#in-the-readers-words)
- [Card 103: the empty disease cells](#card-103-the-empty-disease-cells)
- [Card 104: one gene page, two rows](#card-104-one-gene-page-two-rows)
- [How each was reproduced](#how-each-was-reproduced)
- [Proposed fixes](#proposed-fixes)
- [Tests that would prove them](#tests-that-would-prove-them)

## In the reader's words

| Card | What the reader sees | Why, in one line |
|---|---|---|
| 103 | Five HNF1A variants with an empty "Associated disease(s)" cell under a line promising each row lists conditions | Each of those variants' ClinVar records names only "not provided" or "not specified", and the table hides those and leaves the cell blank with no word beside it |
| 104 | "BRCA1 NCBIGene:672" twice in "Gene records found", while Sources shows the page once | The table removes a repeated record only when its link and every cell match exactly; Sources and the opening line match on the page key instead |

## Card 103: the empty disease cells

The cause is decision D2's placeholder rule doing what it was built to do, with the explanation placed only in the Notes list.

- `src/system_03_search_agent/synthesis/answer_layout.py:623-648`, `condition_titles`: a condition whose MedGen title is "not provided", "not specified" or "see cases" is counted and not shown. A condition whose name lookup returned nothing is also counted and not shown.
- `src/system_03_search_agent/synthesis/answer_layout.py:807-812`, `table_second_cell`: joins the remaining titles. When none remain, the cell is the empty string, by design (its docstring: "an empty cell asserts nothing").
- `src/system_03_search_agent/core/graph.py:12362-12375`: the table keeps the mapping column as long as one row has a name, so blank rows sit beside named ones.
- `src/system_03_search_agent/core/graph.py:12425`: `cells.append(second or "")` writes the blank cell.
- `src/system_03_search_agent/core/graph.py:13738-13752`: the only explanation, "39 variant links to ClinVar placeholder conditions ... are not listed", goes to the Notes list, far below the table.
- `tests/system_03_search_agent/core/test_write_answer_structure.py:399` pins the blank cell (`["variant number 2", "ClinVar:2", ""]`).

What the graph says about the five rows (`raw/probe_card103_graph_output.json`, read-only MATCH through `execute_cypher`, titles from the repository's own MedGen resolver):

| Variant | Its only linked condition | MedGen title |
|---|---|---|
| ClinVar:1048822 | MedGen:C3661900 | not provided |
| ClinVar:1051750 | MedGen:C3661900 | not provided |
| ClinVar:1098821 | MedGen:CN169374 | not specified |
| ClinVar:1104934 | MedGen:C3661900 | not provided |
| ClinVar:1105252 | MedGen:C3661900 | not provided |

So on this page the cause is placeholders only, not a failed name lookup. The lookup-failure path is real but latent, and it is worse than the placeholder path because nothing discloses it:

- `answer_layout.py:809` discards the unresolved count (`_unresolved`), and `placeholder_link_count` (`answer_layout.py:818-832`) counts placeholders only. A link whose name could not be looked up leaves a blank or shorter cell and no note anywhere. The offline repro prints 0 for such a link.
- `src/system_03_search_agent/synthesis/disease_names.py:132` and `:303-306`: one lookup asks about at most 25 condition ids, the first 25 in sorted order; the rest resolve to nothing. HNF1A does not reach it: its first 38 variants fold 8 distinct condition ids, and its first 100 fold 14 (`raw/probe_card103_cap_output.txt`). A gene with more distinct conditions, or an NCBI outage, would.
- `answer_layout.py:812` cuts the joined cell at 500 characters with a plain slice, which can end mid-word. Twelve titles of up to 200 characters each can pass 500. Not seen live.

## Card 104: one gene page, two rows

- `src/system_03_search_agent/core/graph.py:12434`: the Researcher table skips a row only when `(finding.source_url, tuple(cells))` repeats. The key is the raw link, stripped of spaces, plus every cell.
- `src/system_03_search_agent/contracts/events.py:190`, `source_page_key`: Sources, the meta line, the trust line and the opening line's record count (`answer_layout.py:1079-1090`) all key on the page, trailing slashes removed. Card 22 moved every count to this key and left the table on the old one.

Two ways the same page becomes two rows, both reproduced:

| Case | Evidence | Why the table key differs |
|---|---|---|
| A: two links to one page | Query 107: "BRCA1 NCBIGene:672" at citations 8 and 12; HNF1A: "HNF1A NCBIGene:6927" at 45 and 49 (`2026-10-07_card102/product_measurements.json`) | The graph's gene link has no trailing slash (`tools/cypher_provenance.py:231`), the live Datasets link has one (`tools/ncbi_datasets_actions.py:327`) |
| B: one link, two names | Saved gene answer: "BRCA1 DNA repair associated [2]" and "BRCA1 [3]" | Same link, but the name cells differ, and the key includes the cells |

A third effect follows from the same line. When the key does match, the second finding is skipped entirely, so its citation number vanishes from the table though Sources lists it (the control case in `raw/repro_offline_output.txt` shows only `[8]`).

The Plain language list has the same key at `core/graph.py:12287` (link plus label), so it can repeat a record the same two ways.

## How each was reproduced

| Script | What it does | Result |
|---|---|---|
| `raw/probe_card103_graph.py` | Read-only MATCH for the five variants' linked conditions, then the repository's MedGen resolver | All five link only to a placeholder |
| `raw/probe_card103_cap.py` | Read-only run of the HNF1A fold query, counts distinct condition ids | 8 for 38 rows, 14 for 100, under the cap of 25 |
| `raw/repro_offline.py` | Calls `core.graph._answer_tokens` on findings shaped like the evidence, no network | Card 103: five blank cells under the line, plus a Notes line; card 104 cases A and B: two "NCBIGene:672" rows under one Sources page key |

Run each from the worktree root with the project's Python; the two probes take the path of an environment file holding the graph credentials.

## Proposed fixes

### Card 103

Recommended: say in the cell why it is empty. A placeholder-only row reads "None named (record says not provided)" or "(record says not specified)", quoting the record's own placeholder title. A row whose lookup failed reads "Name could not be looked up". The mapping column still appears only when at least one row has a real name, so the explanation never makes a table on its own.

| Option | What the reader gets | Cost to the reader |
|---|---|---|
| Say why in the cell (recommended) | Every row answers the line above it; the record's own words, beside its own citation | One more phrase per row; the Notes count stays, and is now repeated by the cells |
| Drop placeholder-only rows | A table of named conditions only | "Found 38 variants" no longer matches the rows, cited variant records disappear, pagination and citations change; the largest change, and it hides records the reader may still want |
| Reword the line ("a blank cell means the record names no condition") | The line becomes true | A blank still looks broken, and a lookup failure would read as "names none", a confident wrong statement |

Answer path: yes, the cell text is part of the answer tokens. It changes no grounded sentence, citation, count or opening line. The unresolved case also needs its own count in the Notes line, or a second note, so a failed lookup is never silent.

Risk: low. One function (`table_second_cell`) returns a reason string, with `mapped` computed on real titles only. The pinned test at line 399 changes on purpose. The frontend renders cells as text, so no screen change beyond the words.

### Card 104

Recommended: one row per page key in the Researcher table and the Plain language list, as Sources does. Key on `source_page_key(finding.source_url)` (falling back to the citation id when there is no link), keep the first row's cells, and add each later finding's citation to that row's markers through the existing `extra_marker_ids`, so the row reads "BRCA1 [8][12]".

| Option | What the reader gets | Cost to the reader |
|---|---|---|
| One row per page, citations merged (recommended) | One gene, one row, every citation number still reachable from it; matches Sources and "Found 1 gene record" | The row shows the first name found; a second name ("BRCA1 DNA repair associated") is not shown in the table, though its own citation still opens it |
| Page key plus cells (only fixes case A) | The slash duplicate goes | Case B, two names for one page, still shows two rows |
| Prefer the longer name when merging | The fuller name wins | A rule about names in code; more to test for little reader gain |

Answer path: yes, it changes which table rows appear. It never changes a grounded sentence, a citation or a count; the counts already use this key, so after the fix the table agrees with them.

Risk: low to medium. Keying on the page alone could merge two different records that share a page, for example a gene's GO rows cited through the gene page (`core/graph.py:11973-11997` documents that case). The fix should merge only when the identifier cell also matches, or skip merging for rows of a different type. Answers already saved keep their duplicate rows, since the saved answer replays stored tokens.

## Tests that would prove them

- Card 103: `_answer_tokens` with placeholder-only variant rows gives the reason text in each cell and no blank cell; a row with a failed lookup gives the lookup text and the Notes line counts it; a table whose every row is placeholder-only still renders as a plain list, not a mapping table; the existing line 399 assertion is updated. Mutation: return "" again and the new assertion goes red.
- Card 104: cases A and B from `raw/repro_offline.py` as unit tests, each giving one row carrying both citation ids; a control where two GO rows share the gene page stays two rows; the Plain language list gets the same pair. Mutation: restore the raw-link key and case A goes red; restore the cells in the key and case B goes red.
- Both: a live check on deployed develop afterwards with the HNF1A Researcher question and query 107, five or more runs, reading the table rows beside Sources.
