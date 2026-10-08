# Adversary review: cards 103 and 104

Branch `fix/card103-104-answer-tables`, pull request #205 against develop. One round, adversarial, findings filed as established. Probes ran offline against the branch code in a scratch folder outside the repository.

## Table of contents

- [Findings](#findings)
- [What held](#what-held)
- [Verdict](#verdict)

## Findings

### A-103-01: a gene row is told "the ClinVar record says not provided"

- Severity: minor (unsure on reachability)
- Regression: yes, new text from this branch; develop shows a blank cell
- What: `empty_cell_reason` is called for every type in `TABLE_COLUMNS` with a fold, which includes `Gene` (`medgen_condition_ids`, the gene-to-disease table). The wording is fixed to "the ClinVar record". A gene row's chip opens the NCBI Gene page, and its fold comes from `gene_associated_with_condition` (MedGen) or, in the fallback, from many variants pooled. There is no single ClinVar record behind a gene row.
- Reproduction: offline probe calling `core.graph._answer_tokens` with three graph `Gene` rows, HNF1A folding `MedGen:C0342276`, GCK folding only `MedGen:C3661900`, condition names `{C3661900: "not provided", C0342276: "Maturity-onset diabetes of the young"}`. Output row: `['GCK', 'NCBIGene:2645', 'None named: the ClinVar record says not provided']  markers=['cq-2']`, where cq-2 is the gene page.
- Why it matters: the cell names a source the chip beside it does not open. Reaching it needs a placeholder concept among the bound diseases, which this probe did not show happens live, so it may be latent. The fix's own scope (ClinVar variants) suggests the wording should depend on the entity type.
- NOT FIXED

### A-103-02: a merged mapping row keeps the first row's cell but takes the second row's disease chips

- Severity: minor (latent; the contradiction is certain once reached, the reaching is not shown)
- Regression: yes, inside this branch's card 104 merge
- What: in the variant-to-disease table, `merge_into(listed_records, record_key, sentence, linked)` appends the later row's `linked` disease citation ids to the first row, but the first row's cells are never revisited. When two findings for one ClinVar page and one identifier come from rows whose folds differ, the merged row shows the first row's cell text and chips for diseases that text does not name, and the later row's disease name disappears from the table.
- Reproduction: offline probe, two graph calls each returning `ClinVar:100` on the same page (call A folds only `MedGen:C3661900` "not provided"; call B folds `MedGen:C0342276`), plus a cited Disease finding for C0342276. Branch output: `['variant ClinVar:100', 'ClinVar:100', 'None named: the ClinVar record says not provided']  markers=['a-1', 'b-1', 'd-1']`, where d-1 is "Maturity-onset diabetes of the young". On develop the same input gives two rows, one blank and one naming the disease.
- Why it matters: this is the exact pattern the card exists to prevent. The cell says the record names no condition, and a chip beside it opens a named condition. Reachability is limited: `build_synth_findings` drops a second finding with the same `(source_url, field, value)`, so it needs one page reached under two different finding identities with different folds (for example a filtered `gene_variant_disease_link` fold and an unfiltered one, or two URL spellings). Not observed live. The new tests cover merging only for rows with identical or absent folds.
- NOT FIXED

### A-103-03: the command line answer loses the merged citation number from the body

- Severity: minor
- Regression: yes, inside this branch's card 104 merge
- What: the merge adds the later citation only to the first token's `marker_ids`. The token's `text` keeps only the first sentence's marker. `adapters/cli/render.py` prints `token.text` verbatim and says outright that `marker_ids` is never used to build a `[n]` string. So on the command line the merged row reads "BRCA1 [8]." and nothing in the body points to [12], which the references block still lists.
- Reproduction: offline probe, BRCA1 graph row at `.../gene/672` (citation 8) and a live Datasets row at `.../gene/672/` (citation 12, source "gene", id "672"). Branch tokens: one row, `cells=['BRCA1', 'NCBIGene:672']`, `marker_ids=['g8', 'n12']`, `text='BRCA1 [8].'`. On develop the same input gives two tokens, texts "BRCA1 [8]." and "BRCA1 [12].". The renderer behaviour was read, not run (`render.py` `_handle_token` writes `payload.text`).
- Why it matters: the build note says "keeping every citation number". That holds in the web app and in the saved-answer markdown (`feedback/capture.py` builds markers from `marker_ids`), but not on the command line surface, where a cited source now has no marker in the body.
- NOT FIXED

### A-103-04: the Notes line still says placeholder links "are not listed" while the cells now quote them

- Severity: minor
- Regression: yes, a new contradiction between two surfaces; the note itself is unchanged
- What: `placeholder_links_note` still reads "N variant links to ClinVar placeholder conditions ('not provided', 'not specified' or 'see cases') are not listed." On this branch a placeholder-only row's cell reads "None named: the ClinVar record says not provided", which lists the placeholder. The build note ("The Notes line and the line under the table are unchanged") made this choice knowingly but recorded no check that the two agree.
- Reproduction: the author's own offline fixture (five HNF1A placeholder-only variants plus one mixed row). Branch cells: four "None named: the ClinVar record says not provided", one "... not specified". Note built by `placeholder_links_note(placeholder_link_count(...))`: "6 variant links to ClinVar placeholder conditions (...) are not listed." Five of those six links are now shown in a cell.
- Why it matters: a reader comparing the table and the note sees two statements that cannot both be true. Small, but it is a trust line.
- NOT FIXED

### A-103-05: "None named" for a record whose ClinVar title is "see cases"

- Severity: unsure
- Regression: yes, new text from this branch
- What: "see cases" is in `PLACEHOLDER_CONDITION_TITLES`, so a row folding only that concept reads "None named: the ClinVar record says see cases". In ClinVar, "See cases" usually means the submitter gave the condition per observed case, not that the record names none. "None named" may say more than the record does.
- Reproduction: offline probe with `ClinVar:300` folding a concept titled "See cases" beside a mapped row. Branch cell: `None named: the ClinVar record says see cases`.
- Why it matters: a confident "none" where the record points to case-level conditions. The meaning of "See cases" was not checked against a live record in this round, so this is filed as unsure.
- NOT FIXED

### A-103-06: a merge drops any cell the later row had and the first row lacked

- Severity: minor (latent for the types probed)
- Regression: yes, inside this branch's card 104 merge
- What: the merge key ignores every cell except the identifier (and the label only when there is no identifier). The first row's cells win. On develop, rows whose cells differed were both shown, so a value carried only by the later row (a Published year, a Status, a mapping cell) was visible; on the branch it is gone, with its citation folded into a row that shows a blank.
- Reproduction: offline probe, one paper reached twice in one "Publication" group: a graph row at `https://pubmed.ncbi.nlm.nih.gov/123` (`curie` PMID:123, title only) and a live row at `.../123/` with `pdat: "2019 Jan 5"`. Graph row first: `['A paper', 'PMID:123', '']  markers=['c1', 'c2']`. Live row first: `['A paper', 'PMID:123', '2019']`. The year shown depends on sentence order. On develop both orders show a row carrying 2019.
- Why it matters: the reader loses a fact the answer had retrieved and cited, and what is shown depends on which source was numbered first. In this probe it needs both rows in one type group, and the graph's "Publication" and the live "pubmed" type fall into different groups, so the live route was not shown. The gene case the card targets differs only in the label, which the build accepts on purpose.
- NOT FIXED

### A-103-07: "Name could not be looked up" also covers lookups that were never made or that came back empty

- Severity: unsure
- Regression: no; new wording where develop showed a blank, not worse
- What: `disease_names.resolve_concept_ids` maps three different cases to `None`: an id past the 25-id cap (never sent), an id that does not match the MedGen id shape (never sent), and an id MedGen answered with no title (looked up, nothing found, cached negative). `empty_cell_reason` shows all three as "Name could not be looked up".
- Reproduction: read, plus the offline probe where a condition id was absent from `condition_names` entirely (never looked up): cell `Name could not be looked up`.
- Why it matters: the words are close enough for the never-sent case. For "MedGen has no title for this id" they suggest a transient failure when the answer is that the record could not be named.
- NOT FIXED

### A-103-08: a failed name lookup beside a named condition is still silent

- Severity: minor
- Regression: no, unchanged from develop
- What: `empty_cell_reason` runs only when the cell is empty. A row folding one named condition and one whose lookup failed shows the name alone. `table_second_cell` still discards the unresolved count, and `placeholder_link_count` counts placeholders only, so nothing says a linked condition was left out.
- Reproduction: read (`synthesis/answer_layout.py`, the call is `second or empty_cell_reason(...)` in `core/graph.py`). The diagnosis names this path as latent.
- Why it matters: "Each row lists the conditions the variant's ClinVar record names" stays false for that row with no disclosure. Card 103's goal ("no cell under the line is blank without a reason") holds, but a short cell can still drop a condition without a word.
- NOT FIXED

### A-103-09: no test guards the "no identifier also needs the same name" rule

- Severity: minor
- Regression: no behaviour regression; a gap in the branch's tests for its own over-merge guard
- What: the build's choices table says "A row with no identifier also needs the same name to merge ... Two different records on one page must not merge on a blank." Mutating `record_merge_key` to `return (page, identifier, "")`, which merges any two identifier-less records on one page, leaves `test_write_answer_structure.py` fully green. The page-only mutant `return (page, "", "")` is caught (by `test_same_page_different_identifier_stays_two_rows`).
- Reproduction: copied `src`, `tests` and `pyproject.toml` to a scratch folder, applied the mutation to `core/graph.py`, ran `pytest -q tests/system_03_search_agent/core/test_write_answer_structure.py`: "34 passed". Unmutated: 34 passed.
- Why it matters: the guard against the worst card 104 outcome (two different records folded into one row, one citation pointing at a record whose name is not shown) can be removed in a later change without any test going red.
- NOT FIXED

Addendum to A-103-09: the same mutant also passes the wider `tests/system_03_search_agent/core/` selection `-k "listing or plain or table or record or answer"`: 279 passed, 14 skipped.

### A-103-10: merging a later row's disease chips into the first row is untested

- Severity: minor
- Regression: no behaviour regression; a gap in the branch's tests on the code path behind A-103-02
- What: `merge_into(..., linked)` adds the later mapping row's disease citation ids to the first row. Removing that (mutating the loop to `for marker in [*marker_ids(sentence)]`) leaves `test_write_answer_structure.py` green, 34 passed. So whether merged mapping rows carry disease chips, and whether those chips match the cell (A-103-02), is not pinned either way.
- Reproduction: scratch copy as in A-103-09, the mutation above, `pytest -q tests/system_03_search_agent/core/test_write_answer_structure.py`: "34 passed".
- Why it matters: the one merge input that can make a cell and its chips disagree has no test.
- NOT FIXED

## What held

Verified with my own offline probes against the branch code (`core.graph._answer_tokens` with constructed findings and citations, no network, no graph, no model):

- Card 103's main path. The author's five HNF1A placeholder-only rows read "None named: the ClinVar record says not provided" (four) and "... not specified" (one). The real name row is unchanged. A placeholder id absent from the name lookup reads "Name could not be looked up". The mapping column still needs one real name: a gene group with only reasons got no column.
- Mutation checks that the new tests do catch: an empty reason (two tests red), a reason hard-coded to "not provided" (two red), a merge that adds no citation ids (three red), and a page-only merge key (one red).
- Card 104, URL spellings: `.../gene/672` against `.../672/` and `.../672//` merge into one row carrying both citation ids. `.../Gene/672/` (case) and `.../672/?report=full` (query string) stay two rows. In every case the row count equals the number of distinct Sources page keys from `source_page_key`, so the table and Sources agree. `http://` cannot occur: `CitationPayload` rejects it, as it rejects a trailing space.
- Card 104, identifiers: a live gene citation with source "gene" or "Gene" gives "NCBIGene:672" and merges with the graph row. A live citation whose source fell back to "ncbi_efetch" gives "ncbi_efetch 672" and does not merge, which matches develop rather than making it worse.
- The Plain language list merges the same cases the Researcher table does (slash case, two-name case) and leaves the query-string case as two items, matching Sources.
- The web app draws chips from `marker_ids` (`useRunView.ts`) and the saved-answer markdown builds markers from `marker_ids` (`feedback/capture.py`), so merged citation numbers stay reachable on those two surfaces. This was read, not run in a browser.
- `_answer_tokens` returns a finished list before any token is emitted, so changing a token's marker ids after it was appended reaches what is streamed. Read.
- No wrong merge of two different real records was found among the shapes checked: GO rows cited through a gene page (each keeps its own `GO:` CURIE), isolates (`biosample_acc`), trials (`nct_id`), PubTator entities (`pubtator_id`), LitVar matches (dbSNP page plus rsid), and different ClinVar variants that share an rsid (different pages).
- The branch's seven targeted tests pass (7 passed). That is not counted as verification.

Only read, not probed: the opening "Found N" line, the trust line and the meta line after a merge. They key on `source_page_key` exactly as before, and the merge changes no citation, so they should be unchanged. The frontend "Showing 1 to 10 of N" bar counts the rows it receives, so it falls with the merge, consistently.

Residual, outside this branch: a graph variant row and a live ClinVar row for the same page land in different type groups ("sequence variant" and "clinvar"), with identifiers "ClinVar:N" and "clinvar N". They still show as two records while Sources shows one page, as on develop.

## Verdict

PASS with findings, against the cards' stated goals. No cell under the variant-to-disease line is blank without a reason, and one gene page with one identifier is now one row carrying every citation number in the web app. The findings inside this branch's own fix are A-103-01 (gene rows told "the ClinVar record"), A-103-02 (a merged row's cell can contradict its chips), A-103-03 (merged citations missing from the command line body), A-103-04 (the Notes line now contradicts the cells) and A-103-06 (a later row's cells dropped). None was observed on live data; A-103-03 and A-103-04 are certain wherever a merge or a placeholder row occurs. Because these sit inside a fix made in this phase, the review loop's stop condition applies and the decision goes to the product owner.

On the measured cases the web answer is not worse than develop. Two surfaces are narrowly worse: the command line body loses a citation number develop showed (A-103-03), and the Notes line now contradicts cells that develop left blank (A-103-04). On that basis the line below says yes.

Worse than develop: yes
