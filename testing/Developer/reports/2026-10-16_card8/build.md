# Card 8 build report: the trust line names its databases

Branch `fix/card8-trust-line-names-databases`, from develop `78c68c1c`. Wording only.

## What changed in the person's words

- The line under an answer says which databases it rests on: "Based on 16 sources cited from MedGen and OMIM", "Based on 4 sources cited, all from ClinVar", "Based on 1 source cited, from MedGen".
- At four or more databases it names the three most cited, then "and N other databases".
- "Not yet confirmed" is gone from every line.
- "; their values could not be compared" shows only on an "ask" answer from two or more databases that has a high-risk claim that could not be compared.
- "Confirmed by N independent databases" and "Sources disagree on at least one claim" are unchanged.
- The explainer card's last sentence now describes the new lines.

## Diff by file

| File | Change |
|---|---|
| `src/system_03_search_agent/synthesis/trust.py` | New closed table `_DATABASE_NAMES` (keys are `record_database` outputs plus the CURIE fallbacks), helpers `_join_names` and `_databases_phrase`, and a rewritten tail of `answer_trust_line`. Docstring updated. `decide`, `DECISION_TABLE`, `triangulate`, `aggregate` untouched. |
| `src/system_03_search_agent/contracts/events.py` | Comment example only. No field change. |
| `src/system_03_search_agent/adapters/mcp/server.py` | Comment example only (it quoted the old line; one line, outside the named fence but comment only). |
| `frontend/src/lib/events.ts` | Comment example only. |
| `frontend/src/components/screens/AnswerScreen.tsx` | `TRUST_LINE_EXPLAINER` last sentence and its doc comment rewritten. |
| Python tests | New `synthesis/test_trust_line.py`; pinned text updated in `test_trust_line_names_its_count.py`, `test_answer_layout.py`, adapters (cli, mcp, graphql), feedback (two files). |
| Frontend tests | Updated `AnswerScreen.card22.test.tsx`, `SavedAnswerScreen.test.tsx`, `riskTag.parity.test.tsx`, `set9AnswerStructure.test.tsx`, `answerLayout.test.tsx`, `answerPagination.test.tsx`; e2e specs and the shared fixture `card22_brca1_citations.json` (`expected_after.trust_line`) text only. |

## Rules in the code

- Database per cited page via `record_database`; counted by distinct pages; named most cited first, ties by name.
- Unknown or empty keys fold into "other databases" and are never printed.
- Clause: outcome `ask`, two or more databases, and any claim with `risk_tier == "high"` and `triangulation == "insufficient"`.

## Tests

`tests/system_03_search_agent/synthesis/test_trust_line.py` (53 tests): one per row of the wording table; a sweep of over a thousand database and state combinations for the 200 character cap; only-confirmed-starts-with-Confirmed; no "not yet confirmed" or "which differ"; the clause only with ask, high-risk insufficient and two or more databases (all-low-risk ask and floor-only ask have none); a sweep of every table key (page keys through real sample URLs, CURIE fallbacks) mapping to a proper name; unknown host never printed. On develop's `trust.py` the file fails at collection (it imports `_DATABASE_NAMES`), and its wording tests would fail on the old text.

## Commands and results

- New file: 53 passed.
- `tests/system_03_search_agent/synthesis/`: all passed.
- Adapters and the two feedback files: one cli test needed a text update, then passed on rerun of that test.
- Frontend: vitest on the six test files above, and `npx tsc --noEmit` (results in the summary).
- `ruff check` and `isort --check-only` clean. `ruff format --check` reports pre-existing unformatted code in 10 touched files (trust.py also fails on develop); the new test file is formatted.

## Unsure or noticed

- A lone unknown database reads "Based on N sources cited, from 1 other database"; a rare case.
- The fixture's `evidence_before.trust_line` keeps the old text on purpose: it records the 2026-09-27 screen.
- Core tests (`test_write_failed_search.py` and others) mention "not yet confirmed" only in comments; left alone.
- `useRunView.ts:1184` has a comment quoting the old line; outside the fence, left alone.
- Test queries 100 and 74 in `testing/Test_queries_and_workflows.md` still describe the old text; outside the fence.

## Fix round

| Finding | What changed | Evidence |
|---|---|---|
| V-8-01a | `test_write_answer_structure.py` `_DEVELOP_NUMBERS` pins the new line text ("Based on 7 sources cited, all from ClinVar", "Based on 1 source cited, from NCBI Gene"); counts unchanged. A sweep of `tests/` for other bare "sources cited" pins found only a prefix check in `test_s3_as_printed.py`, which still holds. | `test_write_answer_structure.py`: stated-numbers tests pass |
| V-8-01b | `_DATABASE_NAMES` in `trust.py` is built from `_NCBI_HOST` plus two path tables; no literal `host/path` string remains. The guard test is untouched. | `harness/test_tiers.py` passes |
| V-8-02 | `TRUST_LINE_EXPLAINER` now reads "When an answer rests on two or more databases and a high-stakes fact could not be checked against a second one, the line adds "their values could not be compared"." Its comment and pinned test updated. Code condition unchanged. | `AnswerScreen.card22.test.tsx` 24 passed, `tsc` clean |
| V-8-03 | `test_trust_line.py` now holds a hand-written mapping of each key to a sample page and proper name (and one for the CURIE fallbacks), plus a test that it covers every table key. | Mutating the `clinvar` entry to "ClinVarX" turned 7 tests red; restored |

Lint: `ruff check` (no path) and the isort gate are clean.
- Full gate 4 suite: 7934 passed, 143 skipped, 24 deselected, 1 xfailed.
