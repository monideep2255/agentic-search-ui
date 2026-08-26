# Doc readability runs

Evidence log for every run of the `doc-readability` skill, one row per run. Each run has three parts:

- The preservation script
- The style script
- The `doc-auditor` agent's grading round A fresh session cannot otherwise tell whether the gate ever ran on a given document, per `.claude/rules/goal-contracts.md`'s requirement that a verify surface leave evidence rather than a claim. This file is that evidence.

The first real run landed on 2026-08-25 and replaced the seeded example row, as that row's own instruction required.

## Index by date

- 2026-08-25: `docs/build/Build_workflow_cadence.md`, the skill's first real run and its end-to-end proof.
- 2026-08-25: `README.md`, the second run, which calibrated the comma-chain arm against a document that was already close to clean.
- 2026-08-25: a five-document batch run in parallel, one agent per file, after a phase checkpoint: `requirements/Plan.md`, `requirements/phase_6/Continuation_prompt.md`, `PROGRESS.md`, `CLAUDE.md` and `AGENTS.md`. Two locked documents were analysed report-only and never edited, in `tracker/locked_docs_readability_report.md`.

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

A correction to a premise this log's early rows relied on, recorded rather than quietly fixed. The survey that scoped this skill reported ZERO em dashes across the repository, and that was wrong twice over. What it got wrong:

- Scope: it covered `docs/`, `requirements/` and the root, and never covered `tracker/` at all.
- Accuracy inside its own scope: `LEARNINGS.md` sits at the root and was missed anyway.

The true figure, measured 2026-08-25:

- Total: 11 files carrying 102 em or en dashes
- `LEARNINGS.md`: 68, almost all in section headings
- `tracker/` phase reports: most of the remainder
- Runs through this skill: none of these files, ever

What survives the correction, and what does not:

- Still true: for the documents actually processed by this skill, punctuation linting was not where the value lay. Every one of them was clean on dashes.
- No longer true: the same claim about the corpus as a whole. None of the 11 affected files has ever been run through this skill.

Rows are append-only. A row is never edited or deleted once a real run lands it, the same rule `DECISIONS.md` and `LEARNINGS.md` already follow for their own history. A wrong row is corrected by appending a new row that says so, not by rewriting the old one.

| Date | Document | Mode | Preservation | Style | Auditor | Additions | Notes |
|------|----------|------|---------------|-------|---------|-----------|-------|
| 2026-08-25 | `docs/build/Build_workflow_cadence.md` | optimize | exit 0, 2365 atoms, 0 lost, 0 orphan claims, 0 negation drops, 7 additions, retention 0.999 | exit 0, 20 hard defects before, 0 after | PASS, round 1 | 7 total: 5 first-principles explanation, 2 structural scaffolding, 0 unclassified | <details><summary>why it landed here</summary>The skill's first real run, and it was run as the end-to-end proof of the skill itself rather than because the document was the worst offender. The style gate was observed FAILING first, at 20 hard findings, before any edit. Four defects in the two scripts were found by this run and fixed, which is the reason to record it in detail. One: the claim-anchoring union ranked candidates by raw shared-atom count, so a Mermaid fence carrying fifteen stage numbers outranked the three bullets a sentence had actually been split into, and three legitimate splits were reported as orphan claims. Replaced with greedy set cover over what the before-unit still needs. Two: the candidate pool was rank-truncated at 24, which dropped a bullet holding nothing but `Phase_6_execution_flow.html`, so a claim failed for a fact sitting in the document. Counted-atom holders are now always included. Three: the negation check compared against a single anchor, so a sentence that split in two reported a dropped negation that had merely moved to the sibling bullet. It now counts over sentence fragments. Four: the style script's comma-chain arm counted commas across a whole line rather than within a sentence and required no coordinator, and 10 of its 14 findings on this document were ordinary prose carrying subordinate clauses. Tightened to detect an actual series. One coverage claim was also CORRECTED rather than defended: a cross-unit value swap had been asserted as catchable, and widening the union to stop the false positives gave that up, so it is now asserted as a known miss. The auditor passed all eleven criteria in round 1 and flagged two borderline generalizations in the added explanation, both of which were tightened before this row landed.</details> |
| 2026-08-25 | `README.md` | optimize | exit 0, 1751 atoms, 0 lost, 0 orphan claims, 0 negation drops, 1 addition, retention 1.000 | exit 0, 2 hard and 3 advisory before, 0 and 0 after | PASS, round 1 | 1 total: 1 structural scaffolding, 0 unclassified | <details><summary>why it landed here</summary>Chosen deliberately as a document already in good shape, since a gate is only calibrated once it has been run against work that is nearly correct as well as against work that is not. It started at 2 hard findings against the cadence document's 20, and both of the style script's remaining arms were wrong. One: the comma-chain arm flagged "questions about genes, diseases, variants, publications, and taxonomy", a bare noun list averaging 1.2 words per item, which is ordinary English rather than a list wearing a paragraph. The arm now requires a mean of 4 words per item, the level at which an item carries its own predicate, which is what writing-style.md's own smell test describes. Two: the heading-case arm reported "System" twice in one heading and treated "System 1" as title case. A capitalized word followed by a number is now recognized structurally as a designator, which generalizes to Layer 2, Phase 6 and Section 25 rather than growing an allowlist, and each word is reported once per heading. The real edits were small: one three-item prohibition became a bullet list, and an architecture diagram was added. The auditor passed all ten applicable criteria and correctly marked the first-principles criterion NOT APPLICABLE rather than passing a shape that was never attempted. It also caught a genuine defect in the new diagram, which drew each layer feeding the Write step directly and so implied the layers bypass Act on the return leg. Fixed to round-trip through Act before this row landed.</details> |
| 2026-08-25 | `requirements/Plan.md` | optimize | exit 0, 19814 atoms, 0 lost, 0 orphan claims, retention 1.000 | exit 1, 59 hard before, 42 after, every remaining finding inside the Revision history changelog | PASS, round 2 | 0 additions | <details><summary>why it landed here</summary>The 42 remaining findings are NOT open defects. They sit inside `## Revision history`, which `writing-style.md` sanctions as a dated bullet changelog and explicitly exempts from the wall rule. Verified none leak outside it. Two Mermaid diagrams were attempted and REVERTED, because the file paths they needed could not fit the 30-character label limit and a truncated label is worse than no diagram. One process failure is recorded against the run rather than hidden: round 2's auditor brief disclosed what round 1 had found, which the auditor itself flagged as breaking its own fresh-context contract, so that verdict should be read with the caveat even though the finding it raised was real.</details> |
| 2026-08-25 | `requirements/phase_6/Continuation_prompt.md` | optimize | exit 1, 6 lost atoms and 4 orphan claims, all deliberate supersessions | exit 0, 47 hard before, 0 after | PASS, round 2 | 1 Mermaid diagram | <details><summary>why it landed here</summary>This file was STALE in a way that mattered, and the checkpoint had to run before the restructure or the staleness would have been carefully preserved. Its status line said build phase 4.16's pull request was open and unmerged when it had merged as PR #63, and a later section still said the product owner had not ranked the UI-defects versus CI choice. Every preservation finding is one of those superseded statuses or a corrected count, not a loss. The agent also refused a figure given to it in its own brief: told the skill had found seven gate defects, it checked this log, found the evidence supported six, and corrected the number rather than repeat an unverifiable one.</details> |
| 2026-08-25 | `PROGRESS.md` | optimize | exit 1, 3 lost atoms and 1 orphan claim, all deliberate corrections | exit 0, 34 hard before, 0 after | not dispatched, gates only | 0 additions | <details><summary>why it landed here</summary>All four preservation findings are corrections rather than losses, each verified independently rather than accepted: 'we do NOT yet know the cause' went because the cause was found, 'about sixteen seconds' went because the measured figure is 10.9 and the document now says eleven throughout, and 'four ways of connecting' became five because six delivery surfaces exist and five shipped. The document keeps a paragraph correcting what it itself claimed the previous week, on the stated grounds that a status document which silently rewrites its own past is worth less than one that shows where it was wrong.</details> |
| 2026-08-25 | `CLAUDE.md` and `AGENTS.md` | optimize | exit 0 on both, 2786 and 2791 atoms, 0 lost, retention 1.000 | exit 0 on both, 4 hard before, 0 after | PASS | table of contents added | <details><summary>why it landed here</summary>The target was not in the finding count. The Current focus table's Priority-2 cell was a single table cell of roughly 12,000 characters carrying the whole build narrative, the densest prose block in the repository, and the style gate does not flag it because its wall arm excludes table rows by design. That cell's own text claimed it no longer carried the per-phase narrative while doing exactly that. The narrative moved to a new `## Build phase history` section and the cell now holds a status line plus a pointer, which makes its own claim true. Both files stay byte-identical apart from the title and intro lines, verified by diff.</details> |
