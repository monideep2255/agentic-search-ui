# Cards 103 and 104: fresh judge

Judge of pull request 205, branch `fix/card103-104-answer-tables` against develop `2182aff3`. Findings are written as they are established; the verdict comes last.

## Table of contents

- [Findings](#findings)
- [Method](#method)
- [Answers to the brief](#answers-to-the-brief)
- [Tests run](#tests-run)
- [Verified by probe versus only read](#verified-by-probe-versus-only-read)
- [Verdict](#verdict)

## Findings

### J-103-01: a placeholder plus a failed lookup reads "None named", which the record does not say

- Severity: minor
- Regression: yes, a new wording (develop showed an empty cell, which asserts nothing)
- What: `empty_cell_reason` (`src/system_03_search_agent/synthesis/answer_layout.py`, the two `parts.append` lines near the end of the function) writes "None named: the ClinVar record says not provided; Name could not be looked up" for a variant linked to one placeholder and one condition whose title did not resolve. The second condition is a real link the record makes; we only failed to fetch its name. "None named" states that the record names no condition, which is not what the record says.
- Reproduction: judge probe `s1_hnf1a_placeholders` (real `write_node`, Researcher), variant `ClinVar:2000004` linked to `MedGen:C3661900` ("not provided") and `MedGen:C9999999` (lookup returns None). Branch cell: `None named: the ClinVar record says not provided; Name could not be looked up`. Develop cell: `""`. The unit test `test_empty_cell_reason_names_both_placeholders_and_a_failed_lookup` pins this exact wording.
- Why it matters: the card's own rule is that a failed lookup must never read as "names none". Here it half does. A reader can take "None named" as ClinVar asserting no disease, when a disease is linked and simply unnamed on our side. A wording such as "Not provided in the ClinVar record; another linked condition's name could not be looked up" would not overstate. Small blast radius: it needs a placeholder and a resolver gap (cap or outage) on one row.

### J-103-02: a gene-to-disease row is told "the ClinVar record says", though the row is a Gene record

- Severity: minor (unsure how often the graph gives a gene a placeholder-only fold)
- Regression: yes, new wording on a table develop left blank
- What: `empty_cell_reason` is called for every mapped type in `TABLE_COLUMNS` (`core/graph.py`, the `cells.append(second or empty_cell_reason(...))` line in the Researcher group loop), including `Gene` with `medgen_condition_ids`. Its text hard-codes "the ClinVar record", so a Gene row whose only linked condition is a placeholder title is attributed to a ClinVar record the row is not and does not cite. The row's citation chip opens the NCBI Gene page.
- Reproduction: judge probe `s5_gene_fold_placeholder`, Researcher, rows BRCA1 (`medgen_condition_ids: [MedGen:C0677776]`, a real title) and BRCA2 (`medgen_condition_ids: [MedGen:C3661900]`, "not provided"). Branch: `['BRCA2', 'NCBIGene:675', 'None named: the ClinVar record says not provided']` under header `Gene | Identifier | Associated disease`. Develop: `['BRCA2', 'NCBIGene:675', '']`.
- Why it matters: every shown fact must point at its source. The cell names a source (ClinVar) that the row's own citation does not open. Either scope the reason to `SequenceVariant`, or word it from the row's own type ("the linked MedGen record is titled not provided").

### J-103-03: a merged citation is dropped when the first row already carries 20 markers

- Severity: minor (needs a row with 19 or more cited linked diseases plus a second citation of the same record)
- Regression: yes. Develop showed the repeat as its own row, so its citation number was reachable; the branch shows no row for it at all
- What: `merge_into` (`src/system_03_search_agent/core/graph.py`, the `len(first.marker_ids) < 20` guard inside the new helper) silently skips a later citation once the first row has 20 markers. The first row's markers are its own citation followed by up to 19 linked-disease markers, so a mapping row with many linked diseases fills the cap before the merge runs. The repeat is then neither a row nor a chip.
- Reproduction: judge probe `s14_marker_cap` (real `write_node`, Researcher). One variant `ClinVar:9` linked to 22 cited Disease records, cited a second time through the same page without the trailing slash. Sources lists citation 24 (`ClinVar:9`, `.../clinvar/variation/9`). Develop: a second `variant ClinVar:9` row carries marker 24. Branch: one row, markers `[1, 2, ..., 20]`; citation 24 appears in no token's `marker_ids` (unreached citations: develop `[]`, branch `[24]`). Plain language is unaffected (list items carry no disease markers: `[1, 24]`).
- Why it matters: the brief's contract is that every citation number stays reachable from a row. Here a Sources entry has no chip anywhere in the answer. Putting a record's own citation markers ahead of the linked-disease markers, or reserving room for them, would keep it.

### J-103-04: merged citation numbers are not in order on a row that links a disease

- Severity: minor (cosmetic, every chip still opens the right page)
- Regression: no for reachability, but it falsifies the build note's claim "A row's merged citations read in order"
- What: `merge_into` appends the later row's markers after the first row's full marker list, which already ends with the linked-disease markers (`sentence_token(..., extra_marker_ids=linked)`). The chips render in `marker_ids` order (`frontend/src/hooks/useRunView.ts`, the `cited` map), so a mapping row reads own, disease, own.
- Reproduction: judge probe `s15_order` (real `write_node`, Researcher). `ClinVar:7` cited at 1 (`.../variation/7/`) and 2 (`.../variation/7`), its linked disease cited at 3. Branch row: `['variant ClinVar:7', 'ClinVar:7', 'Maturity-onset diabetes of the young']`, markers `[1, 3, 2]`. Develop: two rows, `[1, 3]` and `[2, 3]`. The new tests cover only rows with no linked disease (`test_one_gene_page_is_one_row_with_every_citation`, `test_one_page_with_two_names_keeps_the_first_name`), so they cannot see it.
- Why it matters: a reader scanning "[1][3][2]" reads it as a glitch; the brief asked for citation numbers kept in order. Inserting the record's own markers before the disease markers would fix this and J-103-03 together.

### J-103-05: edge rows that borrow a gene's CURIE now hang every edge's chip under the first edge's label

- Severity: unsure
- Regression: unsure. The root cause is on develop; the branch changes which chips are visible
- What: `cypher_provenance._shape_entity` gives an edge with no CURIE its start gene's CURIE and page. Three `orthologous_to` edges from BRCA1 therefore share page `.../gene/672` and identifier `NCBIGene:672`, and `record_label` (through `_row_for`) labels all three with the first edge's fields. Develop showed one row with chip 1 and left citations 2 and 3 on no row. The branch merges them into one row whose chips are 1, 2 and 3, under the label of edge 1 only.
- Reproduction: judge probe `s4_edges_through_one_gene`, three edge rows named "ortholog link to mouse Brca1", "... rat Brca1", "... dog BRCA1". Develop row: `['ortholog link to mouse Brca1', 'NCBIGene:672']` markers `[1]`, unreached citations `[2, 3]`. Branch row: same cells, markers `[1, 2, 3]`, unreached `[]`. Opening line, trust line and citations identical.
- Why it matters: more citations become reachable (better), but chips 2 and 3, whose claims are about rat and dog, sit beside a label naming mouse. All three open the same gene page, so no chip leads to a wrong record. Filed so the owner can judge; I have not shown this edge shape reaches the listing on a live query.

### J-103-06: four one-line mutations survive the touched test file, including the guard against merging two records

- Severity: minor (the code is right today; nothing would catch it going wrong)
- Regression: no, a test gap
- What: 16 one-line mutations were applied to a scratch copy of the branch and the touched file was run each time. 12 went red. These 4 stayed green (34 passed):
  - M6, `record_merge_key` returns `(page, identifier, "")`, so the label no longer guards a row with no identifier. Run through the real `write_node` (judge probe `g1_no_identifier_same_page`), two different records with no identifier on one page, "first thing" [1] and "second thing" [2], become one row `['first thing']` with markers `[1, 2]`: a record disappears under another's name. This is the exact over-merge the build note says the label prevents ("Two different records on one page must not merge on a blank"), and no test pins it.
  - M10, the Researcher list path (a group with only names, `if not as_table:`) never merges. Untested.
  - M14, `mapped` turned true when any row has an empty-cell reason. Judge probe `g2_all_placeholder_group` then shows a mapping column of nothing but "None named" cells. The build note's "The explanation alone must never create a table" holds in the code (unchanged `mapped`), but no test pins it.
  - M16, the placeholder words are no longer de-duplicated. Untested ("not provided and not provided" would pass).
- Reproduction: mutation runner over `tests/system_03_search_agent/core/test_write_answer_structure.py`; survivors printed `M6 never use label: rc=0 ['34 passed']`, `M10 researcher list path never merges: rc=0 ['34 passed']`, `M14 ...: rc=0 ['34 passed']`, `M16 ...: rc=0 ['34 passed']`.
- Why it matters: M6 guards the one way card 104 could show a confident wrong record. The next edit to `record_merge_key` can drop it and stay green.

### J-103-07: the Notes line still says placeholder links "are not listed" while the cells now quote them

- Severity: unsure (wording consistency)
- Regression: no change to the note; the contrast is new
- What: the unchanged disclosure note reads "4 variant links to ClinVar placeholder conditions ('not provided', 'not specified' or 'see cases') are not listed." On the branch the same answer's cells read "None named: the ClinVar record says not provided". A careful reader may see the note and the cells disagree about whether those links are listed. The build note records this as out of scope ("no test showed a contradiction").
- Reproduction: judge probe `s1_hnf1a_placeholders`, Researcher, branch notes: `["Each row lists the conditions the variant's ClinVar record names; ...", "4 variant links to ClinVar placeholder conditions ('not provided', 'not specified' or 'see cases') are not listed."]`, beside the cells shown under J-103-01.
- Why it matters: small, but two lines of one answer should not read as disagreeing. "are not listed as diseases" would remove the doubt.

### J-103-08: a real name beside a failed lookup is still silent, and the 500-character cut still lands mid-word

- Severity: minor
- Regression: no, both identical on develop (named in the diagnosis, kept out of scope by the build note)
- What: when a row has at least one real title, `table_second_cell` returns it and `empty_cell_reason` is never called, so a second condition whose name did not resolve leaves no trace in the cell or the Notes. The diagnosis asked that "a failed lookup is never silent"; the build counts it only when the cell would otherwise be blank. Separately, `table_second_cell` still slices the joined titles at 500 characters (`answer_layout.py`, `return "; ".join(titles)[:500]`), mid-word, dropping later titles with no mark.
- Reproduction: judge probe `s1_hnf1a_placeholders`, `ClinVar:2000006` linked to MODY and to an id that resolves to None: branch and develop cell both `Maturity-onset diabetes of the young`. Judge probe `s8_long_cell`: a four-title cell ends `...word word word word word ` on both branches, the fourth title missing.
- Why it matters: the card's promise, "never blank without a reason", holds, but "never silent about a missing name" does not. Not worse than develop.

### J-103-09: "the ClinVar record says see cases" reads like an instruction

- Severity: minor
- Regression: yes, a new wording
- What: `empty_cell_reason` quotes the placeholder title verbatim. For the third placeholder in `PLACEHOLDER_CONDITION_TITLES`, the cell reads "None named: the ClinVar record says see cases", which a reader can take as the product telling them to "see cases".
- Reproduction: judge probe `g3_dup_placeholder_words`, `ClinVar:3` linked to a condition titled "see cases". Branch cell: `None named: the ClinVar record says see cases`. Develop: `""`.
- Why it matters: quoting the record is right, but without quotation marks this one reads as our instruction. Quoting the title ("says 'see cases'") would fix it for all three.

### J-103-10: the cell wordings and the merge key are recorded in the build note, not in DECISIONS.md

- Severity: unsure (process)
- Regression: no
- What: the build note's "Choices and rejected alternatives" table holds three choices between alternatives (say why in the cell; merge on page plus identifier; label needed when there is no identifier). `git diff origin/develop...HEAD -- DECISIONS.md` is empty, and `DECISIONS.md` has no card 103 or 104 row. The merge key is also explained in a code comment, which the decision-logging rule accepts; the reader-facing wording is not.
- Reproduction: `git diff --stat origin/develop...HEAD -- DECISIONS.md` prints nothing; `grep -n "card 103\|Card 104" DECISIONS.md` prints nothing.
- Why it matters: the wording is what a reader sees; if the owner revisits it, the alternatives should be findable where decisions live.

## Method

- Probes: three scratch scripts that call the real `core.graph.write_node` (the Synth model call faked to restate each finding line, as the touched test file does) on 16 scenarios, each in Researcher and Plain language, run once against the branch and once against a `git archive` of `origin/develop` `2182aff3`. Every run printed the opening claim, every listing row with its cells and marker numbers, the citations, the distinct page count, the trust line and outcome, and any citation no token reaches.
- The 25-id cap was driven through the real `disease_names.resolve_concept_ids` with only `_search_uids` and `_summary_titles` faked to answer every id (probe `s7_cap25`): ids 26 to 30 read "Name could not be looked up" on the branch and blank on develop, and the lookup was asked about 25 ids.
- Mutations: 16 one-line mutations on a scratch copy of the branch (`git archive HEAD`), the touched test file run after each, the copy restored after each. The worktree was never edited.

## Answers to the brief

| Question | Answer | How |
|---|---|---|
| 1. Each wording path | Placeholder-only, both placeholders, failed lookup, mixed, no link (stays empty), real plus placeholder (real name only, no noise), over the 25-id cap (says it could not be looked up), 500-character cut (unchanged): all as the build note says. Defects: J-103-01, J-103-02, J-103-09; J-103-08 not worse | Probes `s1`, `s5`, `s7`, `s8`, `g2`, `g3` |
| 2. Never merges two different records | Held in every probe: same page with different identifier (2 rows), same identifier with different page (PMID 12345678 merged only where the page matched), gene plus mouse ortholog gene (2 rows), GO rows cited through the TP53 page (4 rows), variants, isolates (same name, different BioSample: 2 rows), papers (same title, different PMID: 2 rows), no identifier with different names (2 rows). Order and reachability: J-103-03, J-103-04; edge rows: J-103-05 | Probes `s2`, `s6`, `s10`, `s11`, `s13`, `s15`, `s16`, `g1`, branch's own test of a different identifier |
| 3. Every stated number unchanged | Yes. Across 32 scenario and depth runs, the opening claim ("Found N ..."), trust line, trust outcome, citation list, distinct Sources page count, headings and notes are identical to develop. The meta line reads the same citations, so it cannot differ | Probes, all scenarios, compared field by field |
| 4. Nothing worse than develop | No row develop shows is lost except by merge into its own record. One citation develop showed is lost (J-103-03). Wordings that overstate or misattribute: J-103-01, J-103-02, J-103-09 | Probes |
| 5. Break it | 12 of 16 mutations go red; 4 survive (J-103-06), including the label guard against over-merging | Mutation runner |
| 6. Production standards | Type hints present on the new helpers; no new dependency, endpoint, query, secret or schema; cell text is short and bounded; marker lists stay within the 20 cap. `ruff check` over the whole repository: all checks passed. `isort --check-only` locally flags an import block in `core/graph.py` that the branch did not touch, and the same file from develop fails the same way here; CI gate 2 passes on pull request 205, so this is local tooling, not the branch | Commands run |

## Tests run

- `tests/system_03_search_agent/core/test_write_answer_structure.py`: 34 passed (branch), and 34 passed on a scratch copy before mutation.
- `tests/system_03_search_agent/synthesis/test_answer_layout.py` with `tests/system_03_search_agent/core/test_isolate_search.py`: 115 passed.
- CI on pull request 205: Python gates, integration, frontend and accessibility all pass (read from `gh pr checks`, not rerun).

## Verified by probe versus only read

- Verified with my own probes: every row of the "Answers to the brief" table except the CI line; the wordings; the cap path through the real resolver; that counts, trust line, citations and notes match develop; that merged rows carry every citation except in J-103-03; the mutation results.
- Only read: that the frontend renders chips in `marker_ids` order (`useRunView.ts`), which J-103-04's cosmetic impact rests on; that edge rows take the start gene's CURIE (`cypher_provenance._shape_entity`), which J-103-05 rests on; that a saved answer replays stored tokens; CI status.
- Not probed: a live run on deployed develop or the live graph.

All findings sit in this branch's own new code (the first build of cards 103 and 104), not inside a fix from an earlier review round.

## Verdict

FAIL. Both cards do what they promise on the cases they were built for, and every number the answer states is unchanged. The brief's contract also says nothing worse than develop, and three things are: one citation develop shows becomes unreachable when a row is full (J-103-03), a mixed cell says "None named" when the record does name a condition we failed to look up (J-103-01), and a Gene row's cell is attributed to a ClinVar record (J-103-02). Each is minor in reach and small to fix.

Worse than develop: yes
