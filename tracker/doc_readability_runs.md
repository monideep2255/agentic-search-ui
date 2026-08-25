# Doc readability runs

Evidence log for every run of the `doc-readability` skill: the preservation script, the style script, and the `doc-auditor` agent's grading round, one row per run. A fresh session cannot otherwise tell whether the gate ever ran on a given document, per `.claude/rules/goal-contracts.md`'s requirement that a verify surface leave evidence rather than a claim. This file is that evidence.

The table below has exactly one row, and it is an example, marked as such in its Date and Notes cells. The first real run of the skill replaces it rather than following it: delete the example row in the same edit that appends the first real row, so the table never carries both a placeholder and real evidence at once.

## Index by date

- 2026-08-25: example row only, seeded to show the shape. No real run has landed yet.

## Table

Each row's detail sits behind a "why it landed here" dropdown in the Notes cell, matching the `<details><summary>` convention `DECISIONS.md` uses, so the table scans as one line per run and you open only the row you care about.

Column meaning:

- Date: the date the run happened, `YYYY-MM-DD`.
- Document: the file path the skill ran against.
- Mode: `optimize` for a restructure of an existing document with a before version, `author` for a freshly written document with no before version.
- Preservation: `check_preservation.py`'s exit code, plus its one-line summary (atoms checked, findings, additions, retention).
- Style: the style script's exit code, plus the defect count before and after the restructure.
- Auditor: the `doc-auditor` agent's overall verdict, PASS or FAIL, plus which round produced it (a FAIL is expected to trigger another round).
- Additions: the count of manifest rows by classification (for example, how many were genuinely new explanation versus how many the auditor caught as reworded prose walls).
- Notes: anything that does not fit the columns above, wrapped in `<details>` so the table stays scannable.

Rows are append-only. A row is never edited or deleted once a real run lands it, the same rule `DECISIONS.md` and `LEARNINGS.md` already follow for their own history. A wrong row is corrected by appending a new row that says so, not by rewriting the old one.

| Date | Document | Mode | Preservation | Style | Auditor | Additions | Notes |
|------|----------|------|---------------|-------|---------|-----------|-------|
| 2026-08-25 | (example row, not a real run) | optimize | exit 0, 118 atoms checked, 0 findings, 4 additions, retention 0.981 | exit 0, 6 defects before, 0 after | PASS, round 1 | 4 total: 3 genuine, 1 reworded wall caught and fixed before this row landed | <details><summary>why it landed here</summary>This row exists only to show the table's shape before the skill has run for real. Replace it, do not append after it: when the first genuine run lands, delete this row in the same edit that adds the real one, so the log never shows a placeholder sitting alongside actual evidence.</details> |
