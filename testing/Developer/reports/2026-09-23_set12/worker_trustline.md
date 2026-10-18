# Worker report: item 12.8, the trust line undercounts its sources

Verdict: fixed. The "Based on N source(s)" line now counts the distinct citations a reader can see and click. The "Confirmed by N independent sources" line still counts distinct origin databases, which is the correct concept for that specific claim.

## Table of contents

- [What the number actually counted](#what-the-number-actually-counted)
- [Which of goal-contracts' three cases](#which-of-goal-contracts-three-cases)
- [The transferable part: a true sentence in the wrong context](#the-transferable-part-a-true-sentence-in-the-wrong-context)
- [Before and after, all four measured counts](#before-and-after-all-four-measured-counts)
- [Surfaces checked](#surfaces-checked)
- [Mutation proof](#mutation-proof)
- [Tests changed](#tests-changed)
- [Gates](#gates)
- [Left open](#left-open)

## What the number actually counted

`answer_trust_line` (`src/system_03_search_agent/synthesis/trust.py`) computed one `count` and used it for every wording. That count came from `_origin_database(finding)`, which reads the database prefix off a finding's CURIE (`medgen`, `pubmed`, `clinicaltrials`, `ncbigene`, and so on) and groups every citation from the same database into one. It was never a records count and never a citations count. It was a distinct-database count.

Established by execution, not by reading the code. Ran the real question behind fix-plan item 12.7 and printed both halves side by side:

    python3 testing/Developer/scripts/local_loop_run_depth.py "..." --depth researcher --print

`q1_plain_language.json` carries 20 entries in `sources`: 5 PubMed IDs, 1 bare gene ID, 8 MedGen IDs, 5 NCT trial IDs. Its `trust_line` was "Based on 4 sources, not yet confirmed". Four is not a plausible undercount of twenty by any citation-based rule; it is exactly the number of distinct databases in that list (pubmed, medgen, clinicaltrials, and one more for the bare gene ID, which falls back to the tool name). That match, on real output, is what established the count was database-based rather than citation-based, before touching a line of `trust.py`.

The code confirmed it: `_origin_database`'s own docstring says "for counting sources... a Layer 1 snapshot row and a Layer 2 live fetch of the same database count ONCE", and a test named `test_trust_line_counts_databases_not_records` asserted exactly that behaviour on purpose. This was a considered design, not an oversight. It was wrong in only one of its two uses.

## Which of goal-contracts' three cases

The three cases: the subject is wrong, the check is wrong, or both are right and are measuring different things. This ticket was not a single case across the whole function. `answer_trust_line` produces two different sentences from the same count, and each line needed its own answer.

"Confirmed by N independent sources": case three, both right about different things. Section 8.3.2's triangulation rule genuinely requires independent-origin corroboration, and counting citations there would overstate independence. Twenty ClinVar rows sharing one database are not twenty confirmations. The database count is the correct number for a claim about corroboration, and nothing here needed to change.

"Based on N source(s)" and "Based on N source(s), not yet confirmed": a plain defect, the subject was wrong. These two lines make a weaker claim than "confirmed": how much evidence backs this answer, stated to a reader looking at a specific list of clickable chips. To that reader, "source" means one of those chips. Reusing the triangulation count here was not a second correct reading of the same number, it was applying the wrong number to a claim the number was never designed to answer.

## The transferable part: a true sentence in the wrong context

The reason this survived as long as it did is that the number was correct for the claim it was originally written for. `_origin_database` and the count it produces are exactly right for "N independent sources corroborate this", which is what "Confirmed by" needed. The defect was not a wrong computation, it was reusing a computation that answers one question ("how many independent databases agree") to answer a different question ("how much can you click through"), where the same English word, "source", carries two different meanings depending on which sentence it sits in.

This is the same shape as this repository's rule that a red gate is a question rather than an instruction (goal-contracts.md, "The inverse: never corrupt the subject to satisfy the check"). Here the check was green and the temptation would have been to leave it alone, since it was passing its own test and its own docstring said what it did. But a check being right about what it measures does not mean every caller of that check is asking the right question. The fix was not to change what `_origin_database` counts, it was to stop asking it a question it was never built to answer, and add a second, different count for the sentence that actually needed one.

## Before and after, all four measured counts

| Visible citations | Databases | Before | After |
|---|---|---|---|
| 20 | 4 | Based on 4 sources, not yet confirmed | Based on 20 sources, not yet confirmed |
| 12 | 3 | Based on 3 sources, not yet confirmed | Based on 12 sources, not yet confirmed |
| 5 | 2 | Based on 2 sources, not yet confirmed | Based on 5 sources, not yet confirmed |
| 5 (all PubMed, post-12.7 dedup) | 1 | Based on 1 source | Based on 5 sources |

The "not yet confirmed" clause's trigger, `trust_outcome == "ask"`, was not touched. Only the number inside the sentence changed.

## Surfaces checked

`trust_line` is computed exactly once, in `core/graph.py`'s `write_node`, via `answer_trust_line`, and placed on the `done` event's `DonePayload.trust_line`. Checked every other surface that carries the word `trust_line` in the codebase (`adapters/web_sse/app.py`, `adapters/mcp/server.py`, `adapters/cli/render.py`, `adapters/graphql/fold.py`, `feedback/capture.py`, `feedback/contracts.py`, `feedback/history.py`, `feedback/writer.py`, `data/models.py`) and none of them recompute it; each one either stores or relays the same string that came off the `done` event, or off the saved interaction row that was itself populated from that event. There is exactly one computation and every surface reads the same value, so fixing it in `trust.py` fixed it everywhere at once with nothing left to keep in sync.

## Mutation proof

Reverted both new `citation_count` uses in the two "Based on" return statements back to `database_count` by hand (a direct file edit, not through the normal patch tooling, specifically to prove the arms are load-bearing rather than to ship it). Reran the targeted trust-line tests: `test_trust_line_based_on_counts_visible_citations_not_databases` and `test_trust_line_five_papers_one_database_reads_five_not_one` both went red, with the assertion failure showing the old database count where the new citation count was expected. Restored the fix and reran; both green again. This proves the two new test arms actually exercise the changed line and are not vacuous.

## Tests changed

`tests/system_03_search_agent/synthesis/test_answer_layout.py`:

- Renamed `test_trust_line_counts_databases_not_records` to `test_trust_line_based_on_counts_visible_citations_not_databases`, and re-asserted its fixture (three distinct citations sharing two databases) now reads "Based on 3 sources, not yet confirmed" instead of "Based on 2 sources, not yet confirmed". This test used to lock in the defect under its own name.
- Added `test_trust_line_confirmed_still_counts_independent_databases`, using the same three-citation, two-database fixture, to prove the "Confirmed by" line still reports 2, not 3, so the two lines cannot silently converge on one shared count again.
- Added `test_trust_line_five_papers_one_database_reads_five_not_one`, the exact field-measured case from the ticket: five distinct PubMed citations, one database, asserting "Based on 5 sources".

`tests/system_03_search_agent/core/test_write_answer_structure.py`:

- `test_the_done_event_carries_one_trust_line` broke on the first full-suite run after this fix. Its fixture, `_ROWS`, is three distinct MedGen citations (`MedGen:C1`, `C2`, `C3`), one database. The old assertion was `startswith("Based on 1 source")`, itself an instance of the exact defect this ticket exists to close. Corrected to `startswith("Based on 3 sources")` with a comment explaining why, and reran green in isolation.

## Gates

`ruff check .` (whole repository, no path): one pre-existing `I001` import-sort failure in `testing/Developer/reports/2026-09-23_set12/rerun_both_depths.py`, an untracked file belonging to a concurrent worker in this session, confirmed via `git status --porcelain` and not created or touched by this task. `isort --check-only` on the two files this task changed (`trust.py`, `test_answer_layout.py`) is clean.

`bash .github/gates/gate04_unit_suite.sh`, full run: `1 failed, 5661 passed, 155 skipped, 23 deselected, 1 xfailed`. The one failure was `test_write_answer_structure.py::test_the_done_event_carries_one_trust_line`, caused by this change and fixed as described above, then reran green in isolation. Per the coordinator's instruction, a second full-suite run was not started by this worker; the coordinator is running it directly to avoid the CPU contention two concurrent full suites caused earlier in this session.

## Left open

Nothing from the ticket's done-when is left open. The count is honest at 20, 12, 5 and the post-dedup 5-paper case; "not yet confirmed" is unweakened; every surface agrees because there is one computation; the fix was verified by running real questions and comparing the printed line against the citation list, not by unit tests alone.

Did not touch `src/system_03_search_agent/synthesis/depth.py` or any depth-directive assembly, which belongs to the concurrent worker on item 12.9.
