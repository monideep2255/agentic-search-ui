# Card 23 judge report

Judge round for card 23 (source note under the variant-to-disease table), branch `fix/card23-source-note`, base develop d8179c4e. One round, fresh context. Findings are written as they are established.

## Findings

### J-23-01: When the variant table is the last thing in the answer, the line leaves the table and lands in the answer-wide "Notes" list
- Severity: major. Blocking: yes, my call, see the last bullet
- File: `src/system_03_search_agent/core/graph.py:12441` (the line is emitted as a `note` token after the table) and `frontend/src/hooks/useRunView.ts:709` to `:715`, `:809` to `:812`, `:827` (a `note` token only attaches to the NEXT claim as `noteBefore`; with no later claim it is pushed into `systemNotes`, the list after the answer)
- What a person sees: they ask about one gene's variants, the graph search returns only the variants and their diseases, and the "Variant-to-disease mapping" table ends the answer. The line is not under the table. It appears in the Notes list after the answer, first, beside "2 variant links to ClinVar placeholder conditions ... are not listed." and, on the fallback path, beside "Note: no written summary could be checked against the records, so the records found are listed below with their sources", which now reads as if it described the source line.
- Evidence (my own probe, scratchpad `probe/test_judge_probe.py`, the real `write_node` with only the model faked, rows `_FOLDED_VARIANT_ROWS` alone, no gene row): token stream at Researcher, clinical_brief and deep_technical depths ends `8 table_row ... 9 table_row ... 10 paragraph_break, 11 note 'Variant-to-disease links are ClinVar assertions...', 12 paragraph_break, 13 note '2 variant links to ClinVar placeholder conditions...'`. Nothing that is a claim follows the note, so by `useRunView.ts:827` (`systemNotes.push(...pendingNotes)`) both land in the answer-wide notes. Same on the structured fallback (model prose grounds nothing): tokens 11, 13, 15 are three notes after the last row.
- Why this is the common shape, not an edge case: the grouped listing moves the Disease group ahead of any table (`graph.py:12334` to `:12335`), so for the two variant fold templates' own output (variants plus their diseases) the variant table is always last. The live runs only avoided it because the Plan step also fetched the gene record, which made a "Gene records found" group follow the table.
- Why it matters: the card's whole point is that the line sits with the one table it describes. `testing/Test_queries_and_workflows.md:566` now promises "Directly under that table", which is false for this shape. The text is still true where it lands, so this is a placement failure, not a truth failure. The builder disclosed it under "Not covered" in `build.md`; disclosure does not make the card's acceptance hold.
- Blocking call: blocking against the card's stated acceptance ("only under that table"). If the lead or owner accepts "in the Notes list when the table is last" as good enough, downgrade to non-blocking and soften the test-queries line to match.
- Suggested fix: frontend, attach a `note` token that directly follows a table's last row to that records block (for example a `noteAfter` on the last `table_row` claim, rendered after the table in `buildAnswerBlocks`), or backend, emit the line as part of the table (a final cell-less marker the screen renders under the table). Either way add a test with the variant table last.
- NOT FIXED

### J-23-02: "read live from NCBI" is not true for a repeated question; a title can be up to a week old
- Severity: minor. Blocking: no
- File: `src/system_03_search_agent/synthesis/answer_layout.py:322` (the pinned text) against `src/system_03_search_agent/synthesis/disease_names.py:144` (`_CACHE_TTL_S = 7 * 24 * 60 * 60`) and `:289` to `:292` (a cache hit returns without any NCBI call)
- What a person reads: "Disease names are MedGen titles read live from NCBI" says the names were fetched from NCBI for this answer. On a warm server, the second time anyone asks about the same diseases, no call to NCBI is made at all and the name is whatever was fetched up to seven days earlier. A failed or empty lookup is cached the same way (negative caching, `disease_names.py` docstring around line 140), so a disease whose name came back empty once stays blank for a week.
- Evidence (my probe, scratchpad `probe/cache_probe.py`, network functions replaced by counters): two consecutive `resolve_concept_ids(["MedGen:C0342276"])` calls in one process returned the same title and the counter showed exactly one ESearch and one ESummary, both from the first call. `_CACHE_TTL_S` printed 604800.
- Does it mislead: mildly. MedGen titles change rarely, so the name shown is almost always what NCBI says today; the risk is the word "live", which a researcher may read as a freshness guarantee. The builder flagged this honestly in `build.md` and offered "looked up from NCBI". The wording is the owner's of 2026-09-25, so this is the owner's call, not a code defect.
- Suggested fix: ask the owner whether to drop "live" ("Disease names are MedGen titles looked up from NCBI."); no code change otherwise.
- NOT FIXED

### J-23-03: Disease names are MedGen titles reworded into reading order, not the titles verbatim
- Severity: minor, unsure. Blocking: no
- File: `src/system_03_search_agent/synthesis/answer_layout.py:624` (`readable_disease_name(title.strip())` on every table cell) and `src/system_03_search_agent/synthesis/disease_names.py:371`
- What a person reads: the line says "Disease names are MedGen titles". A researcher who clicks through sees MedGen's title "Breast-ovarian cancer, familial, susceptibility to, 1" while the table showed "Familial breast-ovarian cancer susceptibility 1". It is a deterministic reordering of the record's own words, so it is not a different source, but it is not the title as MedGen spells it.
- Evidence (my probe): `readable_disease_name("Breast-ovarian cancer, familial, susceptibility to, 1")` returned `Familial breast-ovarian cancer susceptibility 1`. Titles are also clipped to 200 characters (`clip_to_word(..., 200)`, same line).
- Does it mislead: I judge not materially; the source claim (MedGen) is true. Filed so the owner can decide whether "MedGen titles" needs "in reading order"; I would leave it.
- NOT FIXED

### J-23-01, addendum: the existing placement fixture hits it when its two groups are swapped
- My differential probe ran rows `[_FOLDED_GENE_ROW, *_FOLDED_VARIANT_ROWS]` (the gene record first). Grouped order is Disease, then gene table, then variant table, so the variant table is last and the line again has no claim after it: same Notes-list outcome. The card's placement test only passes because its fixture puts the gene row after the variants (`tests/system_03_search_agent/core/test_write_answer_structure.py:1041`). Which group comes last is decided by the order the graph returned rows, not by anything the card controls.

### J-23-04: The cherry-picked commit's subject is not in sentence case
- Severity: minor. Blocking: no
- File: commit `2f7850bd`, subject "feat(write): the variant-to-disease table says where it comes from"
- What: `.claude/rules/git-workflow.md` asks for the description in sentence case. The subject was carried over unchanged from the parked commit `830e1d05`. Its body still says card 32, which is the right historical number (`DECISIONS.md:693`, phase 8.4) but a reader following card 23 meets two numbers; the source comment at `src/system_03_search_agent/synthesis/answer_layout.py:317` says "Card 32" too.
- Suggested fix: none needed for behaviour. If the branch is not yet pushed, a reword is cheap; otherwise leave it, never amend a published commit.
- NOT FIXED

### J-23-05: The untracked adversary probes in this folder fail gate03 if they are committed as they stand
- Severity: minor, not this card's code. Blocking: no
- File: `testing/Developer/reports/2026-10-06_card23/raw/adversary/probe.py`, `probe_cache.py`, `probe_mixed.py`, `probe_negative_cache.py` (untracked, written by the sibling adversary round, not on the branch)
- Evidence: `bash .github/gates/gate03_lint.sh` exits 1 with 18 errors, every one in those four files. `ruff check --exclude testing/Developer/reports/2026-10-06_card23/raw/adversary` prints "All checks passed!" and exits 0, so the committed branch is clean.
- Why it matters: report folders count as source for gate03 (`run-the-ci-gates-exact-commands-before-push`). Whoever stages the adversary's evidence must run `ruff check --fix` on it first or CI goes red.
- NOT FIXED

### Line-number corrections to the findings above
- J-23-01 addendum: the placement test's fixture line is `test_write_answer_structure.py:1045`, not `:1041`.
- J-23-02: `_CACHE_TTL_S` is at `disease_names.py:136`, not `:144`.

## Checklist

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | Truth: every row from ClinVar `has_phenotype`, cited to its variation record; every name a MedGen title from NCBI | Pass, with two wording notes (J-23-02, J-23-03) | The mapping column reads `clinvar_condition_ids` (`answer_layout.py:297`). Only `_apply_fold` writes it (`tools/cypher_query.py:1840` to `:1866`, template path only, `fold is None` on the model path), and only the two variant templates carry that fold (`tools/cypher_templates.py:497` to `:537`), both `MATCH (v:SequenceVariant)-[:has_phenotype]->(x:Disease)`. Read-only check of the System 1 reference: the ClinVar variant-summary parser is the only `has_phenotype` producer, one edge per MedGen CUI, `source="ClinVar"`, `source_url` the ClinVar variation page, the same URL as the variant node (`parse_variant_summary.py:157`, `:193` to `:200`). Names: the cell is `condition_titles` over `resolve_concept_ids` only (`graph.py:12797` to `:12806`); `_normalize` refuses every non-MedGen prefix (`disease_names.py:178` to `:194`); an unresolved or placeholder id leaves the cell empty, never a code. No Layer 2 or 3 row can enter the table: `mapped` needs every row in the group to carry the fold field (`graph.py:12352` to `:12356`), so a foreign row turns the table off rather than joining it. "Read live" is true on a cold process and up to a week stale on a warm one (J-23-02, probed). Names are MedGen titles put into reading order (J-23-03, probed). A reader concludes "ClinVar asserted each pairing and MedGen named each disease", which is true. |
| 2 | Placement | Fail (J-23-01) | Under the table and nowhere else in the token stream: verified on 14 fixture shapes times 4 depths by differential probe (below). Plain language: no line, verified. On screen, the line sits under the table only when another group follows it; when the variant table is last, which is the variant templates' native shape, the screen moves it into the Notes list after the answer. Reproduced with the real `write_node` at three technical depths and on the structured fallback, then traced through `useRunView.ts:709` to `:715`, `:809` to `:812`, `:827` and `AnswerScreen.tsx:346`, `:1677` to `:1699`. The saved-answer markdown (`feedback/capture.py:193` to `:197`) keeps the line in place, under the table, so the screen and the saved answer disagree in that shape. |
| 3 | Cherry-pick `2f7850bd` and card 95's tests | Pass | `git show --stat`: `2f7850bd` touches only `answer_layout.py` (+32) and `test_answer_layout.py` (+36); `c75dbf81` only `graph.py` (+13) and `test_write_answer_structure.py` (+122); `0dfb2688` one line of the test-queries document; `2af0fe44` the report folder. The added `+`/`-` lines of `2f7850bd` and the parked `830e1d05` are identical for both `src` and `tests` (diffed). `git diff d8179c4e HEAD -- src tests` removes zero lines. Card 95's block is intact (its test count on develop 37, branch 39, the two added being the helper's; the card 95 marker comment is present once on both). Nothing else from the parked tag came in. |
| 4 | No regression, no extra model call, no schema change | Pass | Differential probe: develop's `src` exported to the scratchpad with `git archive`, the same 56 runs (14 shapes: the six firewall fixtures, isolates, isolates with an organism, unfolded variants, an intronic variant, trials, gene table before variants, variants before gene table, folded fallback; times Plain language, Researcher, clinical_brief, deep_technical) through the real `write_node` on each tree. The only differences in any event stream are one `note` and one `paragraph_break` token, in the 12 runs with a variant-to-disease table at a technical depth, plus `call_elapsed_s` timing in the cost event. Model call counts identical in all 56. Event types identical; `TokenPayload` kind `note` already exists (`contracts/events.py:367`). |
| 5 | Tests and mutations | Pass | Card tests plus `test_answer_layout.py`: 100 passed. Three mutations of my own, each restored with `git checkout --`: helper keyed on `as_table` instead of `mapped` (red: `test_card23_no_variant_table_no_source_note[variants_without_diseases]`); the note emitted twice (red: `test_card23_the_source_note_sits_directly_under_the_variant_table`); the Plain language list given the note when it lists a folded variant (red: `test_card23_no_variant_table_no_source_note[plain_language]`). `git status` afterwards: no tracked change. Gap: no test has the variant table last, which is why J-23-01 is green. |
| 6 | Gates | Pass for the branch | gate02 exit 0. gate03 exit 1 on the working tree, all 18 errors in the sibling adversary's untracked probes (J-23-05); with that folder excluded, "All checks passed!". `check_public_leaks.py --base origin/develop`: PASS, 4 commits, 0 findings. My own grep of the diff for home paths, the owner's name and credential words: nothing. Commit identity is the noreply address; no co-author trailers. |

## Verified by my own probes versus only read

- Probed: the variant-table-last placement in the token stream at four depths and on the fallback (J-23-01); the 56-run differential against develop, including model call counts; the title cache's one-lookup-per-week behaviour and the title reordering (J-23-02, J-23-03); three mutations; the gates; the cherry-pick's identity with the parked commit.
- Read, not run: the screen's handling of the tokens (`useRunView.ts`, `AnswerScreen.tsx`). I reproduced the `noteBefore` and `systemNotes` logic in a Python model of it, not in a browser or in vitest, so "what a person sees" for J-23-01 is traced, not screenshotted. The System 1 `has_phenotype` producer and the graph's actual contents: read in the reference repository, not queried. The builder's live runs: read, not rerun (no live calls in this round).

## Not covered

- No live model, graph or NCBI call; no browser check of the screen.
- A model-written graph query that returns a `SequenceVariant` node whose stored properties happen to include a key named `clinvar_condition_ids`: I did not check the graph's property names. If one existed, its row would bypass the fold and still feed the table. I judge it very unlikely and did not file it.
- Two listings in one answer (structured fallback and a findings tail both listing variant rows) would show the table, and so the line, twice. I did not establish that both can be non-empty at once.
- Streaming: while the answer is still arriving, the line waits in `pendingNotes` until the next claim lands; not exercised.

## Verdict

FAIL against the card's stated acceptance, on one blocking item:

- J-23-01: when the variant-to-disease table is the last group of an answer, the screen shows the line in the Notes list after the answer, not under the table. This is the variant templates' own output shape, and the test-queries document now promises "Directly under that table".

The line is true wherever it appears (checklist item 1), it reaches no other table and no Plain language answer, nothing else in any answer changed, and no model call was added. If the owner accepts the Notes-list placement for that shape, J-23-01 drops to non-blocking and the card passes, with the test-queries line softened to match.

J-23-01 sits in this card's own new wiring (`c75dbf81`), not in a fix made during a review round, so the review loop's stop condition for "a defect inside this phase's fix" does not fire. The builder had disclosed the gap under "Not covered".
