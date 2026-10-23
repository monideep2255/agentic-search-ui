# Card 139 note 3: judge round

Judge, one round, on branch fix/card139-note-names-what-was-asked (commit 4bbfab63) against origin/develop. Findings are appended as they are established. Ids J-139c-NN.

## Findings

Method: the judge's own probes, a scratch pytest file outside the repository that reuses the branch's `_write_with_targets` helper and runs the whole `write_node` with a faked MedGen title lookup. The same file was run against a `git archive` of origin/develop's `src`, so every branch number below sits beside develop's for the same input. No live model or network call.

| Probe | Shape | Develop | Branch |
|-------|-------|---------|--------|
| P1 | "MODY", one mention, 8 MedGen records, only the 8th cited | ask, note lists 7 record titles | answer, no note |
| P2 | "MODY", one mention, 8 records, none cited (only a gene page cited) | ask, note lists 8 titles | answer, no note |
| P3 | breast cancer and ovarian cancer, 3 records each, 1 of each cited | ask, note lists 4 titles | answer, no note |
| P4 | rs80357906 plus breast cancer, only the rsID cited | ask, 3 titles | ask, "breast cancer" |
| P5 | the same, only one breast cancer record cited | ask, "rs80357906, Title 2, Title 3" | ask, "rs80357906" |
| P6 | two genes whose mentions differ only in case ("BRCA1", "brca1"), one cited | ask, "brca1" | answer, no note |
| P7 | BRCA1 and TP53, BRCA1 cited | ask, "TP53" | ask, "TP53" |
| P8 | window plus two typed rsIDs, CFTR and one rsID cited | ask, "CFTR-AS1, rs75527207" | ask, "rs75527207" |
| P9 | window, "Besides CFTR", CFTR uncited | ask, "CFTR, TP53" | answer, no note |
| P10 | typed NCBIGene:672 and MedGen:C0006142, gene cited | ask, MedGen title | ask, MedGen title |
| P11 | breast and ovarian cancer, a shared record owned by the first mention only, it alone cited | ask, 2 titles | ask, "ovarian cancer" |
| P12 | mention text "TP53." | "TP53.." (double stop) | "TP53" |

### J-139c-01: a one-mention question whose bound records go uncited now reads "answer", where develop read "ask"
- Severity: major (unsure: the owner's call, see Why it matters). This sits inside this round's fix.
- What: `_unaddressed_mentions` returns `[]` whenever fewer than two mentions are grouped (`src/system_03_search_agent/core/graph.py:10272`, `if len(groups) < 2: return []`), and the caller floors `trust_outcome` at `ask` only when that list is non-empty (`graph.py:15213-15214`). On develop the same F-3.4-A-01 completeness check counted records, so a one-mention question with any bound record uncited was floored at `ask`. That check is the only thing that lowered develop's breast cancer shape: the branch and develop produce different outcomes for identical inputs, and the only note on develop's side is the partial-answer note.
- Reproduction: P1, "What genes are associated with MODY?", targets = 8 MedGen records all with mention "MODY", one citation to the 8th record only. Develop: `outcome: ask`, note "does not address ... Title of MedGen:C0000001, ... C0000007". Branch: `outcome: answer`, no note. P2, the same with no MedGen record cited at all (one citation, `https://www.ncbi.nlm.nih.gov/gene/2645`): develop `ask`, branch `answer`.
- Why it matters: the judgment the brief asks for. For the breast cancer shape the builder pinned (the first, exact-title record cited) develop's "ask" was a side effect: the person asked about one thing and the answer cites that thing. But `resolve_disease_mention_to_curies` (`graph.py:3308`) binds up to N records, title-contains matches first and then synonym-only matches, so the one cited record can be the weakest match ("Impaired glucose tolerance in MODY" for "MODY", 1 of 8), or none at all (P2). The branch then shows the clean "nothing to flag" outcome on an answer that cites 1 of 8, or 0 of 8, of the records the system itself chose to stand for the only thing the person asked about. Develop's sentence was false ("named in the question"), but its floor was sometimes true. The one remaining disclosure is Think's progress narrative ("MODY: 8 MedGen records matched by name", `graph.py:4678-4685`), which says how many records were bound, not how many the answer used. A truthful alternative exists and was not built: keep a one-mention note naming the scale ("this answer draws on 1 of the 8 MedGen records matched for MODY"). That needs the owner's yes on new wording, so it is a decision, not a fix, and it should go to the owner rather than be settled by the builder's test that pins `outcome == "answer"` (`tests/system_03_search_agent/core/test_graph.py`, `test_write_names_no_record_of_a_one_mention_disease_question`).
- NOT FIXED

### J-139c-02: two mentions both partly covered read "answer" with no note
- Severity: minor (unsure)
- What: a mention counts as addressed when any one of its records is cited (`graph.py:10274-10278`, `all(curie in left_out ...)`), so a two-mention question citing 1 of 3 records for each mention passes as complete.
- Reproduction: P3, "Genes in breast cancer and ovarian cancer?", 3 records per mention, citations to the 3rd of each. Develop `ask` with 4 titles listed; branch `answer`, no note.
- Why it matters: the same weak-match problem as J-139c-01, now on a two-mention question. This is the rule the card asked for ("addressed when any of its records is cited"), so it is filed for the record, not as a departure from the brief.
- NOT FIXED

### J-139c-03: mentions that differ only in case are merged into one, so citing one record addresses an unrelated one
- Severity: minor (unsure about how often it happens in production)
- What: `_unaddressed_mentions` groups on `mention.casefold()` (`graph.py:10271`). Two different records whose Think mentions differ only in case end up in one group, and citing either addresses both, which is exactly the "unrelated record that happens to share the mention" case.
- Reproduction: P6, targets `NCBIGene:672` (mention "BRCA1") and `NCBIGene:7157` (mention "brca1"), only 672 cited. Develop: `ask`, "does not address ... brca1". Branch: `answer`, no note.
- Why it matters: a gene and a disease, or two genes, rarely share a mention text in one question, since `_confirm_extracted_entities` resolves a span as one kind and Think's disease fallback runs only for symbols that failed as genes. So this is unlikely today. It is still a property of the code that no test pins: grouping by mention text alone, not by mention text plus the span it came from.
- NOT FIXED

### J-139c-04: a gene the person typed beside a window is no longer named when the answer leaves it out
- Severity: minor (unsure: option A was the diagnosis's recommendation; I found no record of the owner choosing it)
- What: on a window question every target that is not an exact identifier (`resolve_exact_identifiers`, a regex pre-pass over CURIE, rsID, PMID and RefSeq shapes, `graph.py:5703-5768`) goes into `not_named` (`graph.py:15207-15209`). A window gene's symbol the person also typed is therefore dropped from the count.
- Reproduction: P9, "Besides CFTR, what genes sit in chr7:117,480,025-117,668,665 on GRCh38, ...", targets CFTR, CFTR-AS1 (and TP53, see note), only CFTR-AS1 cited. Develop: `ask`, "CFTR, TP53". Branch: `answer`, no note. Note: TP53 in this probe is not production-shaped, because Think skips confirming the model's gene spans on the window path (`graph.py:4373-4390`), so a typed non-window symbol never reaches `target_entities` there. CFTR is production-shaped: it is a window gene with its symbol as its mention.
- Why it matters: the window rule is structure, not a word list, as the brief requires (the pre-pass is regexes over identifier shapes; it holds no symbol table). The cost of that is that a typed symbol is not an identifier, so a person who typed CFTR beside a window gets no note when CFTR goes uncited. Probably the right trade under "a confident wrong record is worse than a missing one", but it is a behaviour change the owner has not seen.
- NOT FIXED

### J-139c-05: a record shared by two disease mentions belongs to the first mention only
- Severity: minor
- What: Think dedups `resolved_entities` by CURIE (`graph.py:4616-4619`, `if curie in seen_curies: continue`), so a record both mentions bound (for example a hereditary breast and ovarian cancer record) carries only the first mention's text, and the write step's `mention_by_curie` (`graph.py:15202-15205`) assigns it to that mention alone.
- Reproduction: P11, breast cancer owns C0000001 and C0000099, ovarian cancer owns C0000004, only C0000099 cited. Branch: `ask`, "does not address ... ovarian cancer". If the shared record is the one cited, the second mention is reported unaddressed though the cited record is about it too. In the other direction, a second mention whose records are all shared has no group, and the "two or more mentions" count drops by one.
- Why it matters: it errs towards saying too much (an extra note), not towards a false "answer", so it is low risk. It is filed because the grouping depends on a Think dedup it does not mention.
- NOT FIXED

### J-139c-06: two parts of the new naming code can be removed with every test green
- Severity: minor
- What: break-it on the worktree, one scratch edit at a time, each restored with `git checkout -- src/system_03_search_agent/core/graph.py` and checked with `git diff HEAD --stat` (empty after each).
  - B7: `listed = ", ".join(unaddressed_entities)` in place of the `.strip().rstrip(".")` join (`graph.py:10291`). Result over test_graph.py and test_write_completeness.py: `298 passed`. My P12 shows the stop strip is real: develop printed "TP53.." for a mention ending in a full stop, the branch prints "TP53".
  - B8: `title = None` in place of the bare-id title lookup (`graph.py:15228`), so a typed MedGen CURIE would be named by its raw code, the 2026-09-14 "MedGen:C0271653" shape this block's comment cites. Result over the ten related test files: `441 passed, 5 skipped`. My P10 shows the branch does name it by title today.
- Why it matters: both are behaviour the commit adds or keeps and nothing pins, so a later edit can undo either silently.
- NOT FIXED

### J-139c-07: the unit test for the window rule cannot fail on the window rule
- Severity: minor
- What: `test_unaddressed_mentions_never_names_a_windows_genes` passes every target as `not_named`, so `_unaddressed_mentions` sees no groups and returns `[]` whatever its grouping does. The rule that decides `not_named` lives in the caller (`graph.py:15206-15209`) and is not exercised by this test.
- Reproduction: B2 (`not_named = frozenset()` in the caller) turned only the full-path test `test_write_names_no_gene_of_a_window_question` red: `1 failed, 24 passed`. The unit test stayed green.
- Why it matters: low, because the full-path test does cover the rule. The unit test's docstring claims more than it checks.
- NOT FIXED

## Break it

Each mutation was applied to the worktree, the tests run, and the file restored. `git diff HEAD --stat` was empty after each restore, and `git status --short` shows only `?? frontend/node_modules`.

| Mutation | Result |
|----------|--------|
| B1, grouping off (`mention = curie`) | `6 failed, 19 passed`: the four `_unaddressed_mentions` unit tests and both full-path disease tests red |
| B2, window rule off (`not_named = frozenset()`) | `1 failed`: `test_write_names_no_gene_of_a_window_question` |
| B3, threshold `< 2` to `< 1` | `1 failed`: `..._one_mention_with_no_record_cited_names_nothing` |
| B4, `all` to `any` | `1 failed`: `..._counts_a_mention_addressed_by_any_one_record` |
| B5, `ask` floor removed | `2 failed`: `test_write_floors_trust_outcome_to_ask_when_a_named_entity_is_unaddressed`, `..._two_mention_question_left_out` |
| B6, window rule applied to every question | `2 failed, 296 passed` |
| B7, stop strip removed | `298 passed` (J-139c-06) |
| B8, bare-id title lookup off | `441 passed, 5 skipped` (J-139c-06) |

## Test and gate output, on the branch unedited

- test_graph.py and test_write_completeness.py: `298 passed in 7.74s`
- test_graph.py, eval/test_write_step_eval_gate.py, test_write_completeness.py and the seven other test files that mention "does not address" or `resolve_concept_ids`: `441 passed, 5 skipped in 20.64s`
- Frontend, `npx vitest run src/answerNotesHidden.test.tsx src/hooks/`: `Test Files  13 passed (13)`, `Tests  100 passed (100)`. The prefix `useRunView.ts:66` matches, "Note: this answer does not address the following entities", is still how the new sentence opens.
- Gate 2, `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0, "Skipped 2 files"
- Gate 3, `venv/bin/ruff check .`: exit 0, "All checks passed!"

## What I checked with my own probes and what I only read

Probed, branch beside develop: the twelve shapes in the table above; the five break-it mutations the fix hangs on, plus three more; the gate commands; the frontend note tests.

Read only, not probed:
- That Think's disease binding pairs every bound record with its mention (`_confirm_extracted_entities`, `graph.py:3528-3550`) and that a window gene's mention is its symbol (`graph.py:4413`). My probes hand-build `resolved_entities` the same way the builder's tests do.
- That a follow-up bound through memory carries one CURIE (`graph.py:6799-6804`), so the check never runs on it, on develop or the branch.
- That the window rule is structure: `resolve_exact_identifiers` is four regexes over identifier shapes with no word list (`graph.py:5703-5768`).

## Verdict

FAIL, pending one owner decision. Card 139 note 3's acceptance holds on every shape I probed: the note names only mentions as Think extracted them, never a window's genes or a disease's extra records, fires only with two or more mentions, and still names typed identifiers. No probe found a wrong name. The fix also changed the trust outcome: J-139c-01, inside this round's fix, is a case where the branch reads "answer" and develop read "ask" on one-mention questions whose answer cites 1 of 8 bound records, or none (P1, P2). For the builder's own breast cancer shape develop's "ask" was a side effect of the false note. For a weak-match or zero-cited binding it was not, so on those shapes the branch's trust line claims more than develop's did. Whether a one-mention scale note should exist is the owner's call.
