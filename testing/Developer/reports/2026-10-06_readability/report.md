# Readability run of 2026-10-06

Three documents went through the doc-readability optimize steps in one fan-out: `testing/UI_fixes_done.md`, `testing/Board_plan.md` and `PROGRESS.md`. Each passed both scripts and failed its fresh-context auditor twice, so by the skill's two-round cap none is done. What this report holds:

- All three were restored to develop's version, and the archive the first run created was taken out of the worktree. The worktree matches develop commit d8179c4e apart from this report, and nothing was committed.
- The owner's questions from the planner, with one more that tonight's result raises.
- The auditors' findings, round by round, and the facts the workers found stale and left alone.

## Table of contents

- [The result in one table](#the-result-in-one-table)
- [What the reporter did](#what-the-reporter-did)
- [UI_fixes_done.md](#ui_fixes_donemd)
- [Board_plan.md](#board_planmd)
- [PROGRESS.md](#progressmd)
- [What the audits said about the process](#what-the-audits-said-about-the-process)
- [Facts the workers found stale](#facts-the-workers-found-stale)
- [The planner's owner questions](#the-planners-owner-questions)
- [Documents left unchanged and why](#documents-left-unchanged-and-why)
- [Checks](#checks)
- [Not covered](#not-covered)
- [Second pass](#second-pass)
- [Third pass](#third-pass)
- [What merged, and the walls left for the next pass](#what-merged-and-the-walls-left-for-the-next-pass)

## The result in one table

| Document | Action | Lines before | Lines after (round 2) | Hard style findings before | Hard style findings after | Auditor | Now in the worktree |
|---|---|---|---|---|---|---|---|
| `testing/UI_fixes_done.md` | Closed history moved to a new `testing/UI_fixes_archive.md`, prose walls cut at sentence boundaries | 3,024 | 687 in the done file, 2,422 in the archive | 3 | 0 in both files | FAIL, FAIL (criteria 6 and 7 in round 2) | Develop's version, 3,024 lines; archive taken out |
| `testing/Board_plan.md` | Five comma-chained sentences made into bullets and a one-row table | 215 | 246 | 4 | 0 | FAIL, FAIL (criterion 7 in round 2) | Develop's version, 215 lines |
| `PROGRESS.md` | Dated subheadings, status paragraphs cut into bullets, sprint narratives gathered, the problems table split into open and settled | 1,194 | 1,282 | 2 | 0 | FAIL, FAIL (criteria 2 and 7 in round 2) | Develop's version, 1,194 lines |

Every preservation gate exited 0 with 0 atoms lost, 0 orphan claims and 0 negation drops, so no fact was lost in any of the three restructures. What failed each time was the reader's test, criterion 7: a paragraph or cell that still packs three or more facts a reader would compare. Round 2 of each run fixed what round 1 named, and the fresh auditor then found walls the first had not named.

## What the reporter did

- Restored `PROGRESS.md`, `testing/Board_plan.md` and `testing/UI_fixes_done.md` to develop's version with `git checkout`.
- Moved `testing/UI_fixes_archive.md` out of the worktree into the session scratch folder, under `readability/UI_fixes_done/`, as `UI_fixes_archive.reverted.md`. The repository's delete hook blocks shell deletions, so the file was moved, not deleted. It is untracked and the lead or owner can delete it.
- Confirmed `git diff develop` was empty for the whole worktree before this report was added.
- Appended no row to `tracker/doc_readability_runs.md`: the task writes one row per PASS document and there is none. The log has recorded two-round FAILs before (2026-09-20 and 2026-09-22 on `testing/UI_fix_plan.md`), so whether tonight's three runs get evidence rows is the lead's call. The lead's call came with the second pass: the three rows were added then, see [Second pass](#second-pass).
- Ran the three repository checks and the style check; results in [Checks](#checks).

## UI_fixes_done.md

Action: the owner approved, on 2026-10-06, moving closed history out of this file into a linked archive. The worker:

- Created `testing/UI_fixes_archive.md` and moved every closed set, older session table and the developer detail into it with no word changed.
- Left a "Moved to the archive" link line in each place history left.
- Cut the prose walls that stayed behind at their sentence boundaries.
- Kept all 20 registered anchors and parsed table headers exactly once in the done file.
- Left a build script in the scratch folder that rebuilds both files from the before text and asserts that each cut joins back to the original.

| Measure | Before | After round 2 |
|---|---|---|
| Lines | 3,024 | 687 (done file) plus 2,422 (archive) |
| Hard style findings | 3 | 0 in the done file, 0 in the archive |
| Preservation | not applicable | exit 0, 28,184 atoms, 0 lost, 0 orphan claims, lex retention 1.000, checked against both files concatenated |
| Additions manifest | not applicable | 3 script rows, all classified, 0 unclassified |

Auditor: FAIL in round 1, FAIL in round 2. Round 2 passed criteria 1 to 5, 8, 9 and 11, and failed two:

- Criterion 6, one added summary row was wrong: the closing "Moved to the archive" table said "Every item of sets 1 to 12 with its detail" moved, but the open items 10.4, 12.14, 12.16 and 12.17 and their detail stayed in the done file. Fix named: "Every closed item", plus a note that the open items stay under "Detail for items on the board".
- Criterion 7, the new "Detail 12.16" table: one cell holds four numbered parts each with its own status, another holds five rules and a measurement note, a third holds three shipped parts with figures. The worker chose a table because the preservation script lets at most six after-units cover one before-unit and bullets failed that gate on a first try. The auditor's view: the shape was picked to pass the script, not for the reader. The auditor also listed six more prose walls left in the done file (the phase 8.7 bullet, the guardrail bullet, the card 94 lines, the lock file lines, the Factory lane line and the "Next in order" intro).

What a reader would have found easier, now lost with the restore:

- The done file opened at 687 lines instead of 3,024, with the retest table, the done features table, the cutoff and this week's session tables, and nothing closed.
- Each place history left carried a link straight to its archive heading.
- The "Set 12, still open" table pointed at a detail block per item instead of holding the detail in a cell, the same shape the archived Set 11 table already uses.
- The 2026-10-05 test-queries row was three rows, morning, afternoon and final.

The auditor also noted stale pointers that already existed, not graded as failures: three sentences in the done file still describe sections that would have moved, and the archive's last line tells each set to update a progress table that would have moved with it.

## Board_plan.md

Action: the five comma-chained sentences the style check named (the intro, the cards outside the root causes, the functions that force a build order, wave 0 and the "Later" line) became bullets and a one-row table. Everything else is identical to the before. All eight registered anchors, every Waves table header and the "card N" wording survived.

| Measure | Before | After round 2 |
|---|---|---|
| Lines | 215 | 246 |
| Hard style findings | 4 | 0 |
| Preservation | not applicable | exit 0, 1,659 atoms, 0 lost, 0 orphan claims, lex retention 1.000 |
| Additions manifest | not applicable | 6 rows, all structural scaffolding, 0 unclassified |

Auditor: FAIL in round 1 (criteria 3 and 6, a source count tied to the wrong folder, fixed in round 2 by restoring the original wording), FAIL in round 2 on criterion 7 alone.

- The round 2 finding: the Progress entry for the evening of 2026-10-05 is one bullet carrying at least eight status facts. They are which waves are live, the pull request range and merge count, about fifteen Retest items, card 13 proposed for closing, card 99 waiting on a measurement, phase 8.7 waiting on a top-up with its balance, the guardrail design waiting on logs, and D9 decided.
- The restructure left that entry untouched because the style check never flagged it.
- Three secondary walls were named: the gate bullet under "How each change is checked", the Factory lane entry and the pause entry.
- Criterion 4 passed with a note: `select_template` and `_ASK_BACK` share one bullet. Splitting them made the preservation script report an orphan claim, since its anchor search spends one of its six units on the Dependencies graph.

What a reader would have found easier, now lost with the restore:

- The opening said in three bullets what the plan covers, then named its sources and their two folders.
- The cards outside the sixteen root causes were one bullet each with size and what each waits on.
- Wave 0 was a one-row table like waves 1 to 5.
- The three later decisions were bullets under "Later, each when its wave opens:".

## PROGRESS.md

Action, with no archive needed:

- Both status sections got dated subheadings.
- Status paragraphs became a lead sentence plus bullets cut at existing boundaries.
- The ten sprint narratives were gathered under "The story so far", newest first, and the sprint table was sorted newest first.
- The problems table was split into an "Open" table of 74 rows and a "Fixed or settled, kept for the record" table of 40 rows, every row verbatim.
- The second Mermaid diagram was relabelled so every node label is under 30 characters. This went against the planner's note to leave it alone, because round 1 failed criterion 9 on it.

| Measure | Before | After round 2 |
|---|---|---|
| Lines | 1,194 | 1,282 |
| Hard style findings | 2 | 0 |
| Preservation | not applicable | exit 0, 18,621 atoms, 0 lost, 0 orphan claims, lex retention 1.000 |
| Additions manifest | not applicable | 30 rows, all classified, 0 unclassified, plus a second table listing every changed line that is not an addition |

Auditor: FAIL in round 1 (criteria 3, 5, 6 and 9, all fixed in round 2), FAIL in round 2 on two criteria:

- Criterion 2: sorting the sprint table newest first put row 5.2, "The machine meant to score answers against those questions", above row 5.1, which introduces the fifty questions, so "those questions" now points at nothing. Rows 5.0 to 5.2 share the date 2026-08-30. Fix named: keep the before's relative order within a tie.
- Criterion 7: six places still pack three or more facts a reader would compare, each cuttable at an existing colon or sentence boundary: the three causes of lost answers, the "39 passed, 9 failed, 3 wait" sentence, the three "honest limits" in one bullet, two held pieces of work with timing figures, the bullet holding the 140,476 count with the gene families and organism list, and the "seven of thirty, five of seven, two of five" sentence.

The auditor also found the manifest's claim "every node id and number kept" false for the diagram: node ids Gql2 and Style2, which readers never see, are gone. Criteria 1, 3 to 6 and 8 to 11 passed.

What a reader would have found easier, now lost with the restore:

- A reader opening "What works today" or "What does not work yet" saw a dated heading per update instead of ALL-CAPS lead-ins inside running text.
- The sprint story read in one place, newest first, instead of seven narratives sitting under the problems section.
- Open problems and settled ones sat in separate tables, so a reader looking for what is still broken did not read through forty settled rows.

The worker proposed a convention for `/phase-checkpoint` if the split returns: when it settles a problem row, move the row from the Open table to the settled table, directly below the row it supersedes.

## What the audits said about the process

Each auditor opened with a dispatch note. The same points came up across all three, and they are about the fan-out, not about any one document:

- The task reached each auditor as a workflow-harness computed task, so none could confirm the doc-readability skill dispatched it.
- The additions manifest arrived as a file path, not inline, in all three runs.
- The eleven-item checklist was not sent, so each auditor graded against its own definition.
- The round 2 manifest for `testing/UI_fixes_done.md` carried preservation-script results ("every one of them passes the preservation gate", "bullets fail it with an orphan claim", the MAX_UNION_UNITS limit), and the task text asserted the owner's approval. The auditor said its verdict was therefore not a clean fresh-context one, and checked the approval itself in DECISIONS.md. The skill's Step 12 forbids script output reaching the auditor; a manifest must list additions and nothing about how the gates behaved.
- Two workers hit the preservation script's six-unit anchor limit and chose a shape to pass it: a table instead of bullets for 12.16, and two functions in one bullet in the board plan. Both auditors saw the result as a shape chosen for the script rather than the reader. The skill forbids loosening the threshold, so a wall whose one sentence carries more than six facts cannot be cut into bullets under the current script. That is a gap for the lead to raise: either the script learns to anchor one before-unit to a bullet list, or such walls are declared out of a structure-only pass.

## Facts the workers found stale

A structure-only pass may not change a fact, so the workers left these as they found them. Each is for the lead or the owner:

| Document | What is stale |
|---|---|
| `testing/UI_fixes_done.md` | "What is waiting on the product owner" still points at the Retest column of `testing/UI_fix_plan.md`, which moved to the done file on 2026-10-06; the planner listed two more lines saying the same |
| `testing/UI_fixes_done.md` | The Set 12 still-open table records 12.14 and 12.17 as of 2026-09-24, though the owner approved both on 2026-09-29 |
| `.claude/skills/phase-checkpoint/SKILL.md` | Step 5a's "into that set's own section" would have no target once sets move to an archive |
| `testing/Future.md` | Line pointers `:107`, `:67` and `:125` into the done file are stale |
| `testing/Board_plan.md` | The intro says seven diagnoses, but the 2026-10-05 card folders hold eight diagnosis files |
| `testing/Board_plan.md` | Progress says D9 is decided (organisms resolve through NCBI Taxonomy), but the decisions table still lists D9 as needed before wave 3 |
| `PROGRESS.md` | "question understanding never built" and "nothing runs checks automatically" in the gap section no longer hold |
| `PROGRESS.md` | One row says a problem is "tracked further down this page" when the row sits above it |

## The planner's owner questions

The planner raised four decisions that are the owner's. Each is reproduced with its recommendation and cost, for the lead to ask through the question tool per the decision cadence rule.

1. The board, `testing/UI_fix_plan.md`: may the Waiting on cells longer than about three sentences (cards 56, 101, 94, 5, 42, 50, 52 and 75) move into a "### Card N" detail subsection under To do, below the table, leaving each cell its first sentence and a pointer, the way the architecture cards' detail already sits under To do? Recommendation: yes. Cost: a card move touches two places instead of one, and the sync check still reads the # and Waiting on columns unchanged. Without it the board stays as it is: its shape is the owner's (2026-09-24, exactly three sections, no table of contents).
2. The test queries document: the only closed history left in it is 47 lines, queries 53 to 55 (tests removed on 2026-09-12, nothing to type) and the "Where each query came from" provenance table. Recommendation: leave them in place and create no `testing/Test_queries_archive.md`, since a tester gains nothing from a second file and the document's length is its 103 live queries. Alternative: move those 47 lines to the archive as approved on 2026-10-06, each replaced by one link line.
3. Should `testing/UI_fixes_archive.md` join `tracker/Living_documents.md` the way `docs/build/Handoff_history.md` did, with `/phase-checkpoint` as its owner for one job, moving a session table older than the current and previous week from the done file into it, and the rule "nothing in it is current"? Recommendation: yes, one registry row and one DECISIONS.md row, so registry-paths and `--shape` guard the archive. Alternative: leave it unregistered and move nothing further into it by hand. Note from tonight: the archive does not exist in the worktree after the restore, so this question now goes with the decision to rerun the done-file move.
4. Inside "Where we stopped", the subsection "The result that should shape what happens next" (superseded in part on 2026-09-24 and kept as the record of why the sentence check was needed, about 40 lines) is closed history, but the cutoff section is on the never-move list. May it go to `testing/UI_fixes_archive.md` with a one-line link in its place? Recommendation: yes. Alternative: it stays in the cutoff as today.

A fifth decision arises from tonight's result: all three runs stopped at the skill's two-round cap, which is the "ask the owner" state. The owner's options:

- Approve a third round on each, as on 2026-08-31 for the debugging guide.
- Accept the round 2 versions with the auditors' findings fixed by hand.
- Leave the documents as they are.

The round 2 versions, the before baselines, the manifests and the rebuild scripts are all in the session scratch folder under `readability/`, so a third round starts from them rather than from scratch.

## Documents left unchanged and why

| Document | Why unchanged |
|---|---|
| `testing/UI_fixes_done.md` | Audited FAIL twice; restored to develop. Its archive was moved to scratch |
| `testing/Board_plan.md` | Audited FAIL twice; restored to develop |
| `PROGRESS.md` | Audited FAIL twice; restored to develop |
| `testing/UI_fix_plan.md` | A before baseline was captured, but no result reached the reporter. Its restructure waits on owner question 1 |
| `testing/Test_queries_and_workflows.md` | A before baseline was captured, but no result reached the reporter. Its archive move waits on owner question 2 |
| `README.md`, `testing/Future.md`, `docs/build/Factory_onboarding.md`, `docs/architecture/Model_architecture.md` | A before baseline was captured for each, but no result reached the reporter, so nothing was changed and nothing was audited |
| `tracker/doc_readability_runs.md` | No PASS, so no row in the first pass; the three first-pass rows were added in the [second pass](#second-pass) |

## Checks

All run from the worktree root after the restore, on a tree identical to develop. They prove the restore left the repository consistent; they say nothing about the three restructures, which no longer exist in the worktree.

| Check | Result |
|---|---|
| `python3 tracker/check_doc_sync.py` | exit 0, the board, the done file, the test queries, the board plan, the Factory brief, the handoff and the registry agree |
| `python3 tracker/check_doc_drift.py --check` | exit 0, 2 facts computed, 0 stale, 0 structural |
| `python3 tracker/check_living_docs.py --shape` | exit 0, 18 rows, shape as registered |
| `check_style.py testing/UI_fixes_done.md` | 3 hard, 15 advisory, matching the worker's before figure |
| `check_style.py testing/Board_plan.md` | 4 hard, 0 advisory, matching the worker's before figure |
| `check_style.py PROGRESS.md` | 2 hard, 0 advisory, matching the worker's before figure |

The style check on the three restored documents is the baseline the next run starts from. No check failed, so no formatting fix was needed and none was made. Inside each run, the workers reported `check_doc_sync`, `check_doc_drift --check` and `check_living_docs --shape` at exit 0 on their round 2 versions as well.

## Not covered

- The reporter did not read the round 2 versions line by line; the figures and findings above come from the workers' and auditors' reports.
- The auditors checked preservation and style against the before files only, never a fact against the code, the live product or the world. A number that was wrong in the before and survived passes every gate.
- The `testing/UI_fixes_done.md` auditor compared the archive by heading offsets and eight line-range samples, not every one of its 2,422 lines.
- Two scratch tracing scripts (`dbg.py`, `dbg2.py`) remain in the Board_plan scratch folder; the delete hook blocked their removal too.

## Second pass

The lead decided the four planning questions on the owner's behalf, the owner asleep and having approved the lead's recommendations:

- Long Waiting on cells move into per-card detail under To do.
- The test queries file stays whole.
- `testing/UI_fixes_archive.md` joins the registry.
- The "The result that should shape what happens next" subsection moves to the archive with a one-line link.

Four documents then went through the optimize steps again from develop d8179c4e, in a fresh scratch folder (`readability2/`). None reached PASS. Line counts below are `wc -l` counts; the first pass's table counted one more line for `testing/UI_fixes_done.md` and `PROGRESS.md`.

| Document | Action this pass | Lines before | Lines after | Hard style findings before | Hard style findings after | Verdict and rounds | Now in the worktree |
|---|---|---|---|---|---|---|---|
| `testing/UI_fixes_done.md` | No edit by this pass's worker: a second writer was rebuilding the done file and the archive at the same time, so it stopped | 3,024 | 642 in the done file plus 2,458 in the archive, the other writer's version at the time of the restore | 3 | 0 in both files | BLOCKED. One audit ran, FAIL on criteria 5 and 7, and it graded a moving target | Develop's version; the archive moved to scratch |
| `testing/Board_plan.md` | Four prose walls cut into bullets with no new words; the worker restored the file itself when the preservation gate left one orphan claim | 215 | 244 in the worker's saved attempt; 252 in a later writer's version found in the worktree | 4 | 0 in both versions | NOT_RUN: no auditor saw either version | Develop's version |
| `PROGRESS.md` | Rebuilt from develop with the first pass's script plus a second script fixing every round 2 finding: no re-sort, dated subheadings, four more paragraphs cut, the diagram relabelled | 1,193 | 1,262 | 2 | 0 | FAIL, one round, on criterion 7 alone; the night's cap is reached | Develop's version |
| `testing/UI_fix_plan.md` | Nine long Waiting on cells keep their first sentence and a link; the rest moved word for word into `### Card N` subsections under To do; three detail passages cut into bullets | 405 | 461 | 1 (the missing table of contents, the owner's exception of 2026-09-24) | 1, the same | FAIL, one round, on criterion 7 alone; the night's cap is reached | Develop's version |

### UI_fixes_done.md

- What happened: the worker found files it had not written changing every few seconds, between 22:19:45 and 22:20:20, in the same worktree and the same scratch folder: the done file, the archive, the build script and the manifest, rewritten by another agent's script. Two writers on one file is what made the first pass's audit invalid, so it made no edit. The auditor, dispatched in parallel, read the done file at 622 lines, then at 644, and the archive's headings renamed between reads.
- The audit, for what it is worth on a moving target: criteria 1 to 4, 6 and 8 to 11 passed on the version last read. Criterion 5 failed because the manifest described a version that no longer existed and four additions were unlisted, among them a Factory bullet under "ADDED 2026-10-05" repeated word for word on the next line. Criterion 7 failed on the archive's set sections, moved word for word and never restructured: Set 7's "What you will see" (five facts), Set 9's "What you will see" (six) and "Two things for your decision", and the Set 11 intro (six status words defined in running prose).
- What a reader would have found easier, now lost with the restore: a done file of about 640 lines instead of 3,024; a "How the board came to be" section and a dated "Session history, 2026-09-21 to 2026-09-27" heading in the archive; a link from each place history left to its archive heading.
- Restored and why: not PASS. The done file is back at develop's version. The worktree's archive and done file are in scratch under `readability2/UI_fixes_done/`, as `UI_fixes_archive.reverted.md` and `UI_fixes_done.reverted.md`, beside the other writer's `build.py`, `after_combined.md`, `manifest.md`, `goal_contract.md` and `fact_ledger.md`. The version this pass's worker set aside at 22:18:55, before it saw the other writer, is in `readability2/UI_fixes_done_set_aside_by_second_writer/`. Nothing was deleted.
- For the lead: exactly one agent must own this document, and its writes must stop before a fresh auditor reads a frozen version. Separately, the archive's set sections need a decision: restructure each wall keeping every fact, or declare the archive exempt as a locked historical record. The move itself cannot pass criterion 7 until one of those is chosen.

### Board_plan.md

- What happened: the worker's attempt fixed all four hard findings with no added word, and the style, sync, drift and shape checks all passed on it. The preservation gate left one orphan claim, at before line 97, the sentence listing the six functions that force a build order. The claim check combines at most six after-units, chosen greedily; here it spends one on the Dependencies Mermaid fence, one on the lead line and, on a tie, one on a Progress sentence, so it never reaches the `write_node` bullet. One function per bullet and a two-column table both leave the same orphan. The only layout that passes puts `select_template` and `_ASK_BACK` in one bullet, as the first pass did, which adds a grouping the original does not have. The worker restored the file and returned blocked.
- A later writer: after that restore, a 252-line version appeared in the worktree at 22:18:30, with `after_pass.md`, `build_pass.py` and `manifest_pass.md` in the Board_plan scratch folder. It is not the version the worker reported, no auditor saw it, and its manifest lists no additions. It is saved in scratch as `Board_plan.reverted.md`.
- What a reader would have found easier, in the saved attempt: the opening as three bullets (what gets built in what order, what blocks what, what the owner decides); the cards outside the sixteen root causes one per bullet; the six ordering functions one per bullet; the three later decisions as bullets; the long 2026-10-05 evening Progress entry as one sub-bullet per sentence in its original order. No table, wave or heading moved, nothing was re-sorted, and every "below" stayed true.
- Restored and why: NOT_RUN, so not PASS. Develop's version is in the worktree.
- For the lead, one of three: accept the two-in-one bullet with no added "and"; leave line 97 as prose and accept one hard style finding; or change the claim check's tie-break or union cap, a tool change outside a documentation pass. Re-applying the attempt is a copy of `after_attempt.md` once one is chosen.

### PROGRESS.md

- What happened: the worker rebuilt the first version from develop and fixed every round 2 finding. The sprint table keeps its original order, the five sprint narratives sit under "The story so far" in their original order, each dated block in both status sections has its own date heading, the 5 October and 29 September headlines are bullets cut at their commas, four more dense paragraphs became bullets cut at existing sentence ends, and the second Mermaid diagram's labels are all under 30 characters. The auditor's suggested labels ("Trace", "Aggregate counts", "Lookup log") were not added, because the pass adds no new word. Fitting the diagram under 30 characters dropped some words ("Can now ask questions too" became "Other programs can now ask"); the manifest lists every dropped word.
- Gates: preservation exit 0 with 18,621 atoms and 0 lost; 27 additions, all headings or link markup, all classified; the three repository checks exit 0; the five registered anchors unchanged.
- The audit: criteria 1 to 6 and 8 to 11 pass. Criterion 7 fails on walls the first two rounds never named: the three source kinds at line 28; hard-wrapped lines at 317 to 321, 349 to 355 and 747 to 757 that Markdown renders as one paragraph each, comparing counts of questions, searches and changes; the 30 August headline at line 447; "Three things are worth saying plainly" at line 646 giving all three in one paragraph; and lines 874 to 878. The style script does not see hard-wrapped paragraphs as walls, which is why they survive every gate.
- Outside the criteria, for a content pass with the owner: the diagram still shows as not done work other sections call done; near-duplicate problem rows; a "tracked further down this page" cell pointing at a row above it. A formatting pass may not change any of them.
- What a reader would have found easier, now lost with the restore: a date heading per update instead of ALL-CAPS lead-ins; the sprint story in one place; headlines as bullets; a diagram whose labels fit their boxes.
- Restored and why: FAIL at the night's cap, so not PASS. Develop's version is in the worktree; the second-pass version is in scratch as `PROGRESS.reverted.md`, with `transform.py` and `fix2.py` that rebuild it.

### UI_fix_plan.md

- What happened: the nine Waiting on cells longer than about three sentences (cards 56, 101, 94, 75, 5, 42, 50, 52 and 55) keep their opening sentence and a "Detail: Card N below." link; the rest of each moved word for word, in order, into a `### Card N` subsection under To do after the architecture detail. Card 5's third-bench sentence and card 50's two findings stay with the sentences they depend on. Detail 11.29's FIRST, SECOND and THIRD are three bullets with "System 3 can only read." back in FIRST; the 11.32 measurements and the 11.38 threshold properties are bullets. Card 75's "this row" became "card 75's row" and "that section" named its file, the only rewording, declared in the manifest.
- Gates: preservation exit 0 with 4,340 atoms and 0 lost; 20 additions, all classified; the three repository checks exit 0; the five registered anchors present once each; the style gate's one hard finding is the missing table of contents, which the auditor confirmed as the owner's exception in `DECISIONS.md`, 2026-09-24.
- The audit: ten criteria pass. Criterion 7 fails in two places. The intro paragraph (lines 8 to 16) packs at least seven "where X lives" facts and grew by the added pointer sentence; the fix named is to keep the first sentence as prose and make the pointers a bullet list. The "THE MODEL CHECK" bullet (lines 388 to 398) packs about eight facts into one bullet. Secondary: the 11.38 "Where it stands" cell and card 50's Item cell.
- Outside the criteria, and for the owner before any merge: `DECISIONS.md`, 2026-09-24, says the detail behind every card moves to `testing/UI_fixes_done.md` and the board carries only To do, Build in progress and Retest. Nine card-detail subsections on the board cut against that row, and they move owner-facing facts behind links: card 42's wait for the owner's yes, card 52's five decisions, card 55's expert review. That is the "never hide the owner's work" preference. The lead's decision (1) tonight chose this move on the owner's behalf; the two decisions now disagree and the owner picks.
- What a reader would have found easier, now lost with the restore: the board table read card by card, with no cell running to a dozen sentences.
- Restored and why: FAIL at the night's cap, so not PASS. Develop's version is in the worktree; the second-pass version is in scratch as `UI_fix_plan.reverted.md`.

### What the reporter did

- Restored `testing/UI_fixes_done.md`, `testing/Board_plan.md`, `PROGRESS.md` and `testing/UI_fix_plan.md` to develop's version with `git checkout`, after saving each worktree version to its scratch folder. Confirmed `git diff develop` is empty for every tracked file.
- Moved `testing/UI_fixes_archive.md` out of the worktree into scratch, as above. Nothing was deleted.
- Added no registry row for `testing/UI_fixes_archive.md` to `tracker/Living_documents.md`: the row was conditional on its document passing, and it did not. The archive does not exist in the worktree, so a row would also fail registry-paths.
- Appended three rows to `tracker/doc_readability_runs.md`, one for each first-pass FAILED_TWICE run (`testing/UI_fixes_done.md`, `testing/Board_plan.md`, `PROGRESS.md`), with each run's preservation, style, auditor and additions figures from this report, and one Index by date entry for 2026-10-06. No PASS row, because there is no PASS. The second pass's four runs have no rows of their own: the task wrote rows for PASS documents and the first-pass failures only, so whether they get evidence rows is the lead's call.
- Ran the checks below.

### Checks, second pass

All run from the worktree root after the restore and after the ledger and report edits.

| Check | Result |
|---|---|
| `python3 tracker/check_doc_sync.py` | exit 0, the board, the done file, the test queries, the board plan, the Factory brief, the handoff and the registry agree |
| `python3 tracker/check_doc_drift.py --check` | exit 0, 2 facts computed, 0 stale, 0 structural |
| `python3 tracker/check_living_docs.py --shape` | exit 0, 18 rows, shape as registered |
| `check_style.py tracker/doc_readability_runs.md` | exit 0, 0 hard, 0 advisory |
| `check_style.py` on the report | exit 0, see the line under this table |
| `check_style.py` on the four restored documents | 3, 4, 2 and 1 hard, the develop baselines, matching the before figures above |
| `check_style.py` on the moved archive, in scratch | 0 hard, 15 advisory |

No check failed, so no formatting fix was needed and none was made.

### What the second pass learned

- Two agents wrote to `testing/UI_fixes_done.md` and `testing/Board_plan.md` in one worktree during this pass. A document in an optimize run needs exactly one writer, and the auditor needs a frozen file; the fan-out has to guarantee both before a verdict means anything.
- Every auditor again received its manifest as a file path, and two manifests carried the maker's own narrative of its work, which is close to a fact ledger. The skill's Step 12 wants the manifest inline and limited to classified additions.
- Walls that survive every script: a sentence listing more than six items cannot become one bullet per item under the preservation gate's six-unit cap, and a paragraph written as hard-wrapped lines with no blank line between them is invisible to the style script. Both are tool gaps, named here for the lead.
- The night's state for each document is the skill's "ask the owner" state: a third round, the saved version with the auditor's findings fixed by hand, or leave it. The saved versions, scripts and manifests for a third round are all in scratch under `readability2/<basename>/`.

## Third pass

The lead decided four things before the third pass, from the second pass's findings:

- The board's Waiting on cells stay on the board. The lead's decision 1 of the second pass, long cells moving into per-card detail under To do, is withdrawn in favour of the `DECISIONS.md` row of 2026-09-24: the detail behind every card lives in `testing/UI_fixes_done.md`, and the board carries only To do, Build in progress and Retest.
- `PROGRESS.md` starts from the second pass's saved version, not from develop, and fixes that pass's audit findings.
- `testing/Board_plan.md`'s sentence listing the six functions that force a build order stays prose, with its one hard style finding accepted.
- `testing/UI_fixes_archive.md` is a locked record: its moved body is graded for loss and change, not for prose walls.

Four documents then went through the optimize steps once more from develop d8179c4e, in a fresh scratch folder (`readability3/`), with one writer per document and each writer told to stop writing before its auditor read the file. None reached PASS. Every preservation gate exited 0 with 0 atoms lost, and what failed each time was criterion 7, the reader's test, in one case with a tool at the root.

| Document | Action this pass | Lines before | Lines after | Hard style findings before | Hard style findings after | Verdict and rounds | Now in the worktree |
|---|---|---|---|---|---|---|---|
| `testing/UI_fix_plan.md` | Eight prose regions cut into bullets, no table cell touched, no word added | 405 | 430 | 1 (the missing table of contents, the owner's exception of 2026-09-24) | 1, the same | FAIL, FAIL, both on criterion 7 alone; the two-round cap | Develop's version |
| `PROGRESS.md` | The second pass's version with its audit findings fixed, develop's diagram put back byte for byte | 1,193 | 1,391 | 2 | 0 | FAIL (criteria 3 and 7), FAIL (criteria 7 and 9); the two-round cap | Develop's version |
| `testing/Board_plan.md` | Four prose walls cut into bullets, no word added; line 115 left as prose by the lead's decision | 215 | 237 | 4 | 1 (line 115, the accepted exception) | FAIL, FAIL, both on criterion 7 at line 115 alone; the two-round cap | Develop's version |
| `testing/UI_fixes_done.md` | Closed history moved to `testing/UI_fixes_archive.md` with no word changed; the walls that stayed cut into bullets under their own Detail headings | 3,024 | 663 in the done file plus 2,458 in the archive | 3 | 0 in both files | FAIL on criterion 7, then BLOCKED on one table cell before a second round | Develop's version; the archive moved to scratch |

### UI_fix_plan.md

- What happened: the board reads word for word as before, in the same order, with long paragraphs turned into short lists. The first round cut the intro's "where things live" pointers and the THE MODEL CHECK bullet; the second cut the four paragraphs the first auditor named in Details 11.29, 11.32 and 11.38 (FIRST, SECOND and THIRD as bullets with "System 3 can only read." kept at the end of FIRST, the speed argument's five steps, the CORRECTION's five sentences) and three nearby paragraphs by the same rule. No table cell was moved, shortened or split, and the board kept exactly three sections with no contents list.
- Gates: preservation exit 0 with 4,340 atoms, 0 lost and 0 additions; the word sequence matches the before token for token, 7,652 tokens each, bullet markers aside. The style gate's one hard finding is the missing table of contents, which both auditors confirmed as the owner's exception in `DECISIONS.md`. The sync, drift and shape checks exit 0.
- The audits: round 1 failed criterion 7 on the four Detail paragraphs, all fixed. Round 2 failed criterion 7 on one paragraph, "What is NOT cheap: ACTING on a confidence number.", three facts in one sentence beside a sibling that had just become bullets, and named three borderline paragraphs (NOTHING IS DESIGNED, the "three places" sentence and the Retest paragraph). Ten criteria passed in each round. Both auditors recorded that the dispatch carried scope statements, so neither verdict was fully fresh-context; the second also found the scope statement wrong, since eight regions changed, not two.
- Left alone on purpose: the Retest paragraph, which `tracker/Living_documents.md` records as a one-paragraph pointer; two carried-over defects, a stray space in "widen ." and a missing full stop after "untouched"; and the long Waiting on cells, by the lead's first decision.
- What a reader would have found easier, now in the saved version: the Detail sections' arguments read as numbered points instead of one paragraph each, and the intro's pointers as a list.
- Restored and why: FAIL at the two-round cap, so not PASS. Develop's version is in the worktree; the pass's version is in scratch as `UI_fix_plan.reverted.md` under `readability3/`.

### PROGRESS.md

- What happened: the worker started from the second pass's saved version and fixed every point its auditor raised. Where splitting into bullets had narrowed a shared clause, the sentence was joined back together, in three places; the two named prose walls and two borderline paragraphs became bullets under the sentences that already introduced them; the "What is next" diagram went back to develop's version byte for byte, because the second pass's relabelling had changed its wording. The five sprint write-ups that moved from "Problems we know about" to "The story so far" stayed, and the manifest now lists that move.
- Gates: preservation exit 0 with 18,621 atoms, 0 lost and 0 additions; style exit 0, 0 hard and 0 advisory; the three repository checks exit 0; the five registered anchors unchanged.
- The audits: round 1 failed criteria 3 and 7, the narrowed clauses and two walls, all fixed. Round 2 failed criterion 7 on four paragraphs no earlier round had named (the practice-site separation, the two halves of the debugging guide, the fourteen problems' counts, the three reviewers' counts) and criterion 9 on three diagram labels exactly 30 characters long. Those labels are develop's own; the second pass had shortened them and dropped words, and this pass put them back. Nine criteria passed. The round 2 auditor also found the manifest short: about 40 split sites are unlisted, and the moved sections were split into bullets as well as moved.
- Outside the criteria, carried over from develop and for a content pass with the owner: a garbled sentence about live checks, the stale diagram showing done work as future, three pairs of contradicting problem rows, two pointers pointing the wrong way, and a "Before ... put on the internet" line written before the site went public.
- What a reader would have found easier, now in the saved version: a date heading per update in both status sections, the sprint story in one place, headlines as bullets, and the shared clauses back where they govern every bullet.
- Restored and why: FAIL at the two-round cap, so not PASS. Develop's version is in the worktree; the pass's version is in scratch as `PROGRESS.reverted.md` under `readability3/`, with `fix3.py` and `fix4.py` that rebuild it from `start.md`.

### Board_plan.md

- What happened: the intro, the 2026-10-05 evening Progress entry, the cards outside the root causes and the "Later" line became bullets with no word added and every "below" still true. Every table, the Mermaid block and the eight registered anchors are unchanged. Line 115 stayed prose by the lead's decision; the worker also tried the auditor's own fix in scratch (`probe_bullets.md`, one bullet per function) and the preservation gate rejected it with one orphan claim, as the second pass found.
- Gates: preservation exit 0 with 1,659 atoms, 0 lost and 0 additions; style exit 1 with exactly one hard finding, the line 115 comma chain; the three repository checks exit 0.
- The audits: both rounds failed criterion 7 at line 115 alone, the file unchanged between them, and passed the other ten. Both auditors recorded that the dispatch carried a paraphrase of the preservation gate's result on that sentence and an instruction not to fail it there, so neither verdict was fully fresh-context. Both graded the criterion as written and set the waiver aside as the owner's call, not theirs.
- What a reader would have found easier, now in the saved version: the opening as three bullets, the evening Progress entry as one sub-bullet per fact, the cards outside the root causes one per bullet, and the three later decisions as bullets.
- Restored and why: FAIL at the two-round cap, so not PASS. Develop's version is in the worktree; the pass's version is in scratch as `Board_plan.reverted.md` under `readability3/`. Whether the lead's acceptance of one hard style finding counts as the owner's is for the owner to say.

### UI_fixes_done.md

- What happened: one writer this time. The done file went to 663 lines and the closed history sits word for word in `testing/UI_fixes_archive.md`, 2,458 lines. After the first audit the worker fixed every dense block it named but one: the 12.14, 12.17 and first 12.15 cells now hold a "Full detail" link with their sentences as bullets under their own Detail heading; the 2026-10-05 session table's test-query results and Process cell moved the same way; the four Loose ends items and the "Recorded in 12.16's row" line got a parent bullet with sub-bullets; the 11.31 pointer links to its exact archive section.
- Gates: preservation exit 0 with 28,184 atoms, 0 lost and 0 orphan claims, both files concatenated against the before; style exit 0 on both files, 0 hard in the done file (1 advisory) and 0 in the archive (15 advisory); the three repository checks exit 0. A check against develop found no duplicated line.
- The audit: one round, FAIL on criterion 7 in the done file, with ten criteria passing. The named walls were row 12.16's "Where it stands" cell, about 3,000 characters, and the smaller ones above. It also noted that the archive's "nothing here is kept current" line sits beside a done-file pointer that still sends readers to the archive for what is live on develop.
- Blocked, and why: the 12.16 cell cannot be cut under the rules. Any bullet or prose layout makes at least 11 claim units, seven of its sentences carry atoms it must keep, and the preservation gate covers one before-unit with at most six after-units, so every bullet layout leaves an orphan claim, and loosening the gate is forbidden. A table of six or fewer long cells passes, but the first pass's auditor rejected that shape as chosen for the script. The cell went back exactly as on develop, and the worker returned blocked before a second round.
- For the lead, two decisions: exempt that cell from criterion 7, or change the script so it can cover one cell with a bullet list. For the owner, a fact and not a structure: 12.16 part 3, 12.14 and 12.17 were approved on 2026-09-29 in "Done features at a glance", yet "Set 12, still open" still lists them as open.
- What a reader would have found easier, now in the saved version: a done file of 663 lines instead of 3,024, every open item's detail under its own heading instead of in a cell, and a link from each place history left to its archive heading.
- Restored and why: not PASS. Develop's version is in the worktree; the pass's done file and archive are in scratch under `readability3/` as `UI_fixes_done.reverted.md` and `UI_fixes_archive.reverted.md`, beside `build.py`, `round2.py` and the earlier states `done_round1_failed.md`, `done_round2_try1.md` and `archive_round1.md`. No registry row was added for the archive, since its document did not pass.

### What the reporter did

- Saved each of the four worktree versions to its `readability3/` scratch folder as `<basename>.reverted.md`, restored `testing/UI_fix_plan.md`, `PROGRESS.md`, `testing/Board_plan.md` and `testing/UI_fixes_done.md` to develop's version with `git checkout`, and moved `testing/UI_fixes_archive.md` out of the worktree into the same scratch folder. Nothing was deleted. Confirmed that every tracked file except `tracker/doc_readability_runs.md` matches develop.
- Added no registry row to `tracker/Living_documents.md`: the row was conditional on the done file passing, and it did not.
- Appended eight rows to `tracker/doc_readability_runs.md`, one per run: the second pass's four and the third pass's four, with one Index by date entry for them. No PASS row, because there is no PASS.
- Ran the checks below.

### Checks, third pass

All run from the worktree root after the restore and after the ledger and report edits.

| Check | Result |
|---|---|
| `python3 tracker/check_doc_sync.py` | exit 0, the board, the done file, the test queries, the board plan, the Factory brief, the handoff and the registry agree |
| `python3 tracker/check_doc_drift.py --check` | exit 0, 2 facts computed, 0 stale, 0 structural |
| `python3 tracker/check_living_docs.py --shape` | exit 0, 18 rows, shape as registered |
| `check_style.py tracker/doc_readability_runs.md` | exit 0, 0 hard, 0 advisory |
| `check_style.py` on the report | exit 0, 0 hard, 1 advisory, a missing-diagram suggestion |
| `check_style.py` on the four restored documents | exit 1 each: 1, 2, 4 and 3 hard, the develop baselines, matching the before figures above |
| `check_style.py` on the moved archive, in scratch | exit 0, 0 hard, 15 advisory |

No check failed, so no formatting fix was needed and none was made.

### What the third pass learned

- One writer per document and a frozen file fixed the second pass's failure mode: no audit graded a moving target, and every preservation gate agreed with its auditor on what was lost, which was nothing.
- The dispatch text still leaks. Six of the seven audits recorded a scope statement, an exemption or a paraphrase of a gate result in their task, and each said its verdict was therefore not fully fresh-context. The skill's Step 12 wants the auditor to receive the before, the after and the classified manifest, and nothing else.
- Two walls cannot be cut under the current tools, and both are now named with their numbers: a table cell whose sentences make more than six claim units (12.16) and a sentence listing more than six items (Board_plan line 115). Either the preservation gate learns to cover one before-unit with a bullet list, or such walls are declared exceptions before a run starts, so an auditor is not asked to fail what the gate forbids fixing.
- A fresh auditor finds a new tier of wall each round in a long document. `PROGRESS.md` has now had five audits across three passes, each naming paragraphs no earlier one had, and the hard-wrapped paragraphs the style script never sees are among them.
- Every document is develop's version. The saved versions, scripts and manifests for any further round are in scratch under `readability3/<basename>/`, and the earlier passes' under `readability/` and `readability2/`.

## What merged, and the walls left for the next pass

After the third pass the lead merged all four documents under a narrower bar, logged in `DECISIONS.md` on 2026-10-06:

- No fact lost against develop.
- Every no-loss criterion (1 to 6) passed by an auditor.
- Every remaining failure is a dense paragraph or label develop already has.

| Document | Version merged | No-loss gate against develop | Hard style findings, develop to merged |
|---|---|---|---|
| `testing/UI_fix_plan.md` | Third pass, round 2 | 4,340 atoms, 0 lost | 1 to 1, the owner's table of contents exception |
| `PROGRESS.md` | Third pass, round 2 | 18,621 atoms, 0 lost | 2 to 0 |
| `testing/Board_plan.md` | Third pass | 1,659 atoms, 0 lost | 4 to 1, the six-function sentence kept as prose |
| `testing/UI_fixes_done.md` and `testing/UI_fixes_archive.md` | Third pass, round 1, the version an auditor graded; round 2 was not audited and moved table cells behind links | 28,184 atoms, 0 lost, 4 additions, all link lines | 3 to 0 in both files |

Walls the auditors named that develop already has, for the next pass:

- `testing/UI_fix_plan.md`: "What is NOT cheap: ACTING on a confidence number."; the NOTHING IS DESIGNED paragraph; the long Waiting on cells, left by the owner's 2026-09-24 shape.
- `PROGRESS.md`: the practice-site paragraph; the two-halves paragraph; the fourteen-problems paragraph; three diagram labels of exactly 30 characters.
- `testing/Board_plan.md`: the six-function sentence, which no bullet layout passes the no-loss gate with.
- `testing/UI_fixes_done.md`: the 12.14, 12.16 and 12.17 cells and the 12.15 Test query cell; the 2026-10-05 session table's test queries and Process cells; three Loose ends bullets.
- Tool gaps behind them: the style script does not see hard-wrapped paragraphs, and the no-loss gate's six-unit cap blocks a sentence listing more than six items from becoming one bullet per item.
