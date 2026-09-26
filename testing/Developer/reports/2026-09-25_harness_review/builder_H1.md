# Builder H1: delete the bookkeeping

Builder H1's report on its slice of the build harness review (`build_harness.md` in this folder): items D1, D2, S3 and S4. The product owner delegated the review's takeaways to the lead on 2026-09-25 (DECISIONS.md, "The lead implements both harness reviews' takeaways"), and the lead handed this slice to one builder with a file fence. Everything below is on branch `chore/harness-bookkeeping`, cut from `origin/develop` at `2c6374f`. Nothing was pushed.

Every number in this report is pasted from the command that printed it.

## Table of contents

- [What changed, by item](#what-changed-by-item)
- [What a person running the two skills now does differently](#what-a-person-running-the-two-skills-now-does-differently)
- [D1: no counts in the living documents](#d1-no-counts-in-the-living-documents)
- [S3: never a silent ok](#s3-never-a-silent-ok)
- [D2: no freshness gate, no checkpoint before every push](#d2-no-freshness-gate-no-checkpoint-before-every-push)
- [S4: the watermark names a row by its words](#s4-the-watermark-names-a-row-by-its-words)
- [The gates, run as CI runs them](#the-gates-run-as-ci-runs-them)
- [Left open for the lead](#left-open-for-the-lead)

## What changed, by item

| Item | Commit | What changed | Check removed |
|---|---|---|---|
| D1, the script | `8d7c0d3` | `tracker/check_doc_drift.py --check` compares no count and no date. The counting code moved behind a new print-only `--counts`. New `tests/tracker/test_check_doc_drift.py` | The stale-count scan (`scan_stale_facts` with its patterns) and the Last-updated currency check (`check_last_updated`) |
| S3 | `6fed897` | A fact `--check` reads that could not be computed, or a tracked-file list git could not produce, is a failure line. In `--counts`, so is a count that could not be computed and a pytest collection that reports errors | None. Two checks got stricter |
| D1, the documents | `78ede79` | The counts sentence left `CLAUDE.md`'s build row (and `AGENTS.md`), and `Plan.md`'s "Decisions logged" line left too. Each became one line naming `--counts`. The registry dropped Plan.md's `Decisions logged:` anchor | None in this commit |
| D2 | `6b6d614` | `check_living_docs.py --fresh` and the registry's Freshness column are gone. `/ship` no longer runs it or requires `/phase-checkpoint` first. `/phase-checkpoint` lost Step 5d and every date-only refresh. The stale CI fact in `/ship` is corrected. New `tests/tracker/test_check_living_docs.py` | The freshness gate and the checkpoint-before-every-push rule |
| S4 | `655c629` | The decision-guard watermark names the last guarded row by its date and quoted first words, in the registry and in `/phase-checkpoint` Step 0 | None |
| This report | the commit that adds this file | This file | None |

Every commit body names the check it removed, the delegation of 2026-09-25 and the review item.

## What a person running the two skills now does differently

`/ship`:

- Runs `python3 tracker/check_doc_drift.py --check` in seconds rather than about two minutes, because it collects no tests and compares no count.
- Does not run `check_living_docs.py --fresh`, and does not need `/phase-checkpoint` before a push.
- At a session end, still rewrites `HANDOFF.md` before the push. Its `Last updated:` line reading today is the one date anything asks for.
- Reads CI as running again: it failed from 2026-09-22 into 2026-09-24 and completed green on develop on 2026-09-25 and 2026-09-26. A push that changes only Markdown runs no workflow, and the skill now says so.

`/phase-checkpoint`:

- Still runs the Step 0 decision guard first and still rewrites `HANDOFF.md` at Step 4.
- No longer edits a count anywhere: Step 5d is gone, and so is every "update the last-updated line" instruction for Plan.md, PROGRESS.md, CLAUDE.md and AGENTS.md.
- Moves a document's date only in the same edit as its content, never on its own. A board nothing changed on keeps its date.
- Finds the watermark by searching DECISIONS.md for a quoted date and first words, and writes the new watermark the same way.

## D1: no counts in the living documents

The four documents no longer state any tracked count as current. The proof uses develop's own scanner, run by a scratch script:

- It loads develop's copy of `check_doc_drift.py` and points it at this branch.
- It runs that copy's `scan_stale_facts` with every fact set to -1.
- So every line the old check treated as a live count is listed, whatever number it states.

On develop before the change it listed nine lines in the four documents: four in `CLAUDE.md` line 31, four in `AGENTS.md` line 31, one in `requirements/Plan.md` line 20. On this branch:

```text
live count assertions in the four D1 documents: 0
live count assertions anywhere else: 2
  tracker/phase_2.1.md:415: says premise gate 9 of 9 (computed: -1 of -1)
  tracker/phase_2.2.md:253: says premise gate 9 of 9 (computed: -1 of -1)
```

The two left are dated build ledgers outside this fence. A broader phrase scan of `CLAUDE.md` and `AGENTS.md` (numbers beside "tests", "decisions", "learnings", "Playwright", "declarations", "premise gates") finds only line 74, "premise gates for everything else were retired on 2026-09-24", which describes the cadence document and states no count. `PROGRESS.md` states no live count: its numbers sit in dated sprint stories, so it needed no edit.

Kept as written, because they are dated records rather than live claims:

- Plan.md's Revision history.
- Plan.md's verbatim copy of CLAUDE.md "as it stood on 2026-09-24", under a dated heading.

`--check` on this branch, in a worktree with no `venv/`:

```text
ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural
```

The retained checks are byte-for-byte the same code as on develop. An AST comparison with docstrings stripped reported SAME for all 27 retained functions, including the five that `.claude/skills/doc-readability/scripts/check_style.py` imports (`fenced_line_mask`, `heading_index`, `slugify`, `dedupe_slugs`, `check_toc`). `scan_structural` is the one DIFFERENT function, because it no longer calls `check_last_updated`.

## S3: never a silent ok

Before, in any worktree with no `venv/bin/python`, develop's `--check` printed `ok: 6 facts computed (4 skipped)` and exited 0 while the count it tracked was stale (F-8.5-J04, F-8.5-V05).

`--counts` in this worktree, which has no `venv/` and no `frontend/node_modules`:

```text
could not compute Python tests: venv/bin/python not found, so pytest could not run. Run this from a checkout that has the repository venv, or create it there
could not compute Premise gate tests: venv/bin/python not found, so pytest could not run. Run this from a checkout that has the repository venv, or create it there
could not compute Frontend tests: frontend/node_modules not found
could not compute Frontend test files: frontend/node_modules not found
error: 4 counts computed | 4 could not be computed
exit=1
```

`--counts` with `VENV_PYTHON` pointed at the real repository venv (a scratch runner sets the module global and calls the script's own `main`):

```text
exit=1
  Python tests: 5738
  Premise gate tests: 9
could not compute Frontend tests: frontend/node_modules not found
could not compute Frontend test files: frontend/node_modules not found
error: 6 counts computed | 2 could not be computed
```

The Python arm passes normally; the two frontend failures are S3 working, because this worktree has no `node_modules`. 5738 is develop's 5704 plus the 34 tests this branch adds.

`--check` with `BOARD_MD` pointed at a path that does not exist:

```text
could not compute Build phase statuses: BOARD.md not found
could not compute Merged PR numbers per phase: could not read BOARD.md's Build phases branch column
error: 0 facts computed | 2 could not be computed | 0 stale | 0 structural
exit=1
```

A real collection error, end to end: a probe directory holds one importable test module (two tests) and two modules importing a missing name. Pytest 9.1.1 prints `2 tests collected, 2 errors in 0.12s` and exits 2. The same probe through each version of the script:

```text
develop's code: skipped=False value=2
skipped=True value=None
reason: pytest reported 2 collection errors, so the 2 tests it did collect leave out every test in the modules that failed to import. Run `python -m pytest --collect-only -q` to see which modules failed
```

So observation 8's mechanism is real: develop reported the lowered count as the truth.

A defect found and fixed while proving this. The first version of the parser searched the whole collection output for "Interrupted: N errors during collection". This branch's own parametrized test ids quoted that fixture text, and `--collect-only -q` lists every test id, so a clean run of this repository read as "1 collection error". Both patterns are now anchored to the start of a line, where a test id (which starts with its file path) cannot match. The test ids are plain, and a regression test pins the case.

Each new control was broken once in a scratch copy holding only `test_check_doc_drift.py` (27 tests), to show its test can fail:

```text
applied break 'no-unmeasured'
  FAILED tests/tracker/test_check_doc_drift.py::test_check_fails_when_a_fact_it_reads_could_not_be_computed
  FAILED tests/tracker/test_check_doc_drift.py::test_counts_fails_when_a_count_could_not_be_computed
applied break 'ignore-errors'
  FAILED tests/tracker/test_check_doc_drift.py::test_a_collection_with_errors_yields_no_python_test_count
applied break 'no-toc'
  FAILED tests/tracker/test_check_doc_drift.py::test_check_still_fails_on_a_table_of_contents_that_misses_a_heading
restored pristine copy
  27 passed in 0.10s
```

## D2: no freshness gate, no checkpoint before every push

`tracker/check_living_docs.py` checks shape only. The registry has five columns. A leftover `--fresh` call fails loudly rather than passing:

```text
living documents: 12 rows, shape as registered
self-test: 2 arms, 0 failed
usage: check_living_docs.py [-h] [--shape] [--self-test]
check_living_docs.py: error: unrecognized arguments: --fresh
```

In `.claude/skills/ship/SKILL.md`:

- The `--fresh` gate line is gone from Step 0.
- The Step 1 paragraph that required `/phase-checkpoint` before `/ship` became: a push needs no checkpoint, and a session end rewrites `HANDOFF.md` first.
- The guard now reads the same way.
- The CI section no longer says CI "has not run since 2026-09-22". `gh run list --branch develop --limit 40`, counted by day and outcome, showed failures on 2026-09-22, 2026-09-23 and 2026-09-24 (plus one success on 2026-09-24), then 8 successes and 2 cancellations on 2026-09-25 and 5 successes on 2026-09-26.

In `.claude/skills/phase-checkpoint/SKILL.md`:

- Step 5d is deleted.
- The date refreshes in Steps 5 and 5b are deleted, and Step 5a's board date moves only when a card moved.
- The counts items in Step 6, Step 7, the exit checklist and the output are deleted.
- Two constraints replace them: write no count, and move no date on its own.
- Step 0 and Step 4 are kept.

In `CLAUDE.md`, the two skill rows now say what the skills do. The `bossman-mode` row is untouched, left for H2.

## S4: the watermark names a row by its words

The watermark said "Guarded through DECISIONS.md row 716". At the commit that wrote it (`7762662`), DECISIONS.md had 716 lines and 687 dated rows (`grep -c` on the file as of that commit), so 716 was the line number of the file's last row. That row is:

> | 2026-09-25 | Keep the four streaming-timing test files (the card 37 deletion reverted in phase 8.5) until all three of W4's non-timing controls have ordinary tests | ...

The watermark now quotes its date and first words. `grep -c -F` of the quote returns 1 in develop's DECISIONS.md and 1 in the main checkout's newer copy. The watermark did not move, because the rows after it have not been through a decision guard. `/phase-checkpoint` Step 0 now finds the watermark by that search and writes the next one the same way, never as a line or row number.

## The gates, run as CI runs them

| Gate | Command | Result |
|---|---|---|
| Lint, gate 3 | `ruff check` (no path) | `All checks passed!`, exit 0 |
| Import order, gate 2 | `isort --check-only --diff src tests services tracker alembic .claude .github` | `Skipped 2 files`, exit 0 |
| New tracker tests | `pytest tests/tracker -q` | `47 passed` |
| Unit suite, gate 4 | `pytest -m "not integration" -q -rs` with the python-gates job's placeholder environment | `6 failed, 5261 passed, 212 skipped, 24 deselected, 1 xfailed, 7 warnings in 223.61s (0:03:43)`: the same six as the develop baseline, none new |
| Drift check | `python3 tracker/check_doc_drift.py --check` | `ok: 2 facts computed \| 0 could not be computed \| 0 stale \| 0 structural` |
| Registry shape | `python3 tracker/check_living_docs.py --shape` | `living documents: 12 rows, shape as registered` |

The unit suite ran on this machine without CI's Postgres service. A local Postgres answers on port 5432 but has no `postgres` role, so six database-backed tests fail here exactly as they did on the untouched develop baseline, run the same way before any change:

- Baseline, develop at `2c6374f`: `6 failed, 5227 passed, 212 skipped, 24 deselected, 1 xfailed`.
- This branch: `6 failed, 5261 passed, 212 skipped, 24 deselected, 1 xfailed`.
- The six: three in `adapters/graphql/test_no_cost_channel.py` and three in `core/test_think_retry.py`. Compared test by test from the two runs' junit files, the failing set is identical, with nothing new and nothing fixed.
- 5261 minus 5227 is 34, the tests this branch adds under `tests/tracker/`.

The drift check is not a CI gate (no workflow or gate script mentions it), so `.github/workflows/ci.yml` needed no change.

## Left open for the lead

Outside this fence, and now describing behaviour that is gone:

- `.claude/skills/verify/SKILL.md` check 6 (line 98) still says the drift check "computes the tracked counts from source" and fails on "a last-updated date older than the file's newest content".
- `.claude/agents/docs-sync.md` line 75 still says the build row's counts are "Owned by /phase-checkpoint Step 5d".
- `docs/build/Debugging_guide.md` line 696 still says the script "computes every tracked fact (a test count, a decision count ...)", and line 831 maps "No stated count has gone stale" to `--check`.

Decisions this builder made that the lead may want to reverse:

- The review's D1 keep-list included "stale dates" (the Last-updated check). The brief said `--check` must keep only checks that are "not a count or a freshness date" and must not fail "because a ... date moved". I removed `check_last_updated`, because with the checkpoint no longer moving dates, the next Plan.md revision-history entry would turn it red. Restoring it is one call in `scan_structural` plus the function from `8d7c0d3^`.
- `CLAUDE.md`'s portability bullet for `check_doc_drift.py` was edited, beyond the counts and the two skill rows, because it said the script "computes every tracked count ... and fails on a stale value". No instruction in it changed.
- `CLAUDE.md` and the registry now read `Last updated: 2026-09-26`, because their content changed on 2026-09-26, under the new rule that a date moves with its content.
- Row 729's limits include "nothing weakens a gate or threshold". D1 and D2 remove two documentation gates by the brief's instruction. The review's open questions 3 and 4 asked the product owner about exactly these two.

Facts found on the way:

- The sync hook does not sync a worktree. `.claude/hooks/sync-agents-md.sh` resolves its root from `CLAUDE_PROJECT_DIR`, which is the main checkout, so editing a worktree's `CLAUDE.md` leaves that worktree's `AGENTS.md` stale. I ran the hook's own generator with `CLAUDE_PROJECT_DIR` pointed at this worktree. The main checkout's `AGENTS.md` was not touched: its sha256 began `10323b04` before and after. A fix is a hook change, which needs the product owner's item-by-item yes.
- The removed CLAUDE.md sentence said "43 Playwright end-to-end declarations", and `--counts` computes 70 top-level `test(` calls. The old check never compared the two, because its pattern did not match "declarations".
- `requirements/Plan.md`'s Phase 6 status row still says phase 8.4 "is built on its branch", and that branch no longer exists (the review, section 2). Not this slice's item, so left as is.
- Rows 717 to 727 of develop's DECISIONS.md, plus the main checkout's uncommitted rows, sit after the watermark and await the next decision guard. The registry's "Set by" cells already cite row 729 for the rows this branch changed.
- `--check` now reads `tracker/BOARD.md` through `render_board`, and fails loudly if the board cannot be parsed. If builder H2 freezes the board for D3, it has to stay parseable. A header paragraph is fine, because the parser finds its tables by heading.
- F-8.5-V05 in `tracker/phase_8.5.md` is what S3 closes. The ledger is outside this fence and is left for the lead to close.

Housekeeping on this machine, none of it in the repository:

- Running the unit suite in this worktree created a git-ignored `logs/` folder here.
- My first break-check copy wrote into an existing session scratch folder, `scratchpad/mut`, a full repository copy another agent left at 05:48. It overwrote that copy's `tracker/check_doc_drift.py`, `tracker/render_board.py` and `tracker/BOARD.md`, and added three files. I restored the three from develop, whose last change to them (2026-09-24 22:27) predates the copy, and moved the three added files into `scratchpad/h1_moved_out_of_mut`. The break check was then rerun in a fresh folder, `scratchpad/h1_s3_break`.
