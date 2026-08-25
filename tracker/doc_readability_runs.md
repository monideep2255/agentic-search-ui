# Doc readability runs

Evidence log for every run of the `doc-readability` skill: the preservation script, the style script, and the `doc-auditor` agent's grading round, one row per run. A fresh session cannot otherwise tell whether the gate ever ran on a given document, per `.claude/rules/goal-contracts.md`'s requirement that a verify surface leave evidence rather than a claim. This file is that evidence.

The first real run landed on 2026-08-25 and replaced the seeded example row, as that row's own instruction required.

## Index by date

- 2026-08-25: `docs/build/Build_workflow_cadence.md`, the skill's first real run and its end-to-end proof.

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
| 2026-08-25 | `docs/build/Build_workflow_cadence.md` | optimize | exit 0, 2365 atoms, 0 lost, 0 orphan claims, 0 negation drops, 7 additions, retention 0.999 | exit 0, 20 hard defects before, 0 after | PASS, round 1 | 7 total: 5 first-principles explanation, 2 structural scaffolding, 0 unclassified | <details><summary>why it landed here</summary>The skill's first real run, and it was run as the end-to-end proof of the skill itself rather than because the document was the worst offender. The style gate was observed FAILING first, at 20 hard findings, before any edit. Four defects in the two scripts were found by this run and fixed, which is the reason to record it in detail. One: the claim-anchoring union ranked candidates by raw shared-atom count, so a Mermaid fence carrying fifteen stage numbers outranked the three bullets a sentence had actually been split into, and three legitimate splits were reported as orphan claims. Replaced with greedy set cover over what the before-unit still needs. Two: the candidate pool was rank-truncated at 24, which dropped a bullet holding nothing but `Phase_6_execution_flow.html`, so a claim failed for a fact sitting in the document. Counted-atom holders are now always included. Three: the negation check compared against a single anchor, so a sentence that split in two reported a dropped negation that had merely moved to the sibling bullet. It now counts over sentence fragments. Four: the style script's comma-chain arm counted commas across a whole line rather than within a sentence and required no coordinator, and 10 of its 14 findings on this document were ordinary prose carrying subordinate clauses. Tightened to detect an actual series. One coverage claim was also CORRECTED rather than defended: a cross-unit value swap had been asserted as catchable, and widening the union to stop the false positives gave that up, so it is now asserted as a known miss. The auditor passed all eleven criteria in round 1 and flagged two borderline generalizations in the added explanation, both of which were tightened before this row landed.</details> |
