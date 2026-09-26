---
name: phase-checkpoint
description: "Sync planning, build and UI-fix-loop docs at a phase boundary. Runs at a planning sub-phase or phase end, a build phase's PR merge to develop or a UI-fix-loop session boundary. Its first step is a decision guard: it reads the DECISIONS.md rows added since the last checkpoint and updates the living-documents registry (tracker/Living_documents.md) before writing anything, so a product-owner decision that reshapes a document is never overruled by a stale instruction. Every mode rewrites HANDOFF.md in place and refreshes PROGRESS.md. Build mode also bumps Plan.md status. UI-fix-loop mode also refreshes the board and the done file. Distinct from /ship, which commits and pushes: this updates artifacts and runs before /ship, never touching git."
scope: project
depends_on:
  - tracker/Living_documents.md
  - tracker/check_living_docs.py
  - HANDOFF.md
  - requirements/Plan.md
  - DECISIONS.md
  - tracker/BOARD.md
  - .claude/rules/writing-style.md
  - .claude/rules/decision-logging.md
depended_by:
  - CLAUDE.md
  - AGENTS.md
  - .claude/skills/ship/SKILL.md
---

# /phase-checkpoint - sync planning or build docs at a phase boundary

Purpose: bring the relevant documentation into a consistent state at a phase boundary, so a fresh session can resume with zero loss. User-invoked only. Does not commit or push (that is `/ship`). Runs at the end of:

- A sub-phase or a full planning phase.
- A merged build phase.
- A UI-fix-loop session boundary.

This skill exists because the documentation ritual repeats at every phase boundary, and a single forgotten artifact (a stale handoff, a Plan.md status line that still says "not started") breaks a clean resume. The skill turns the ritual into a checklist so no artifact is skipped, in any mode below.

## Table of contents

- [The registry names the sections, this skill names the jobs](#the-registry-names-the-sections-this-skill-names-the-jobs)
- [Three modes](#three-modes)
- [One-owner convention](#one-owner-convention)
- [When to run](#when-to-run)
- [Inputs the skill needs](#inputs-the-skill-needs)
- [Steps](#steps)
- [Constraints](#constraints)
- [Exit checklist](#exit-checklist)
- [Output](#output)

## The registry names the sections, this skill names the jobs

`tracker/Living_documents.md` is the registry of every document this skill keeps current: its one job, its owner, its current shape as a list of section names, the line that carries its date, and the DECISIONS.md rows that set that shape. This skill reads the registry at Step 0 and takes every section name and column name from it. Nothing below names a section directly; each instruction names the job a section does ("the cutoff", "the board's columns", "the ordered next actions") and the registry says what that section is called today.

Why, measured on 2026-09-24: the product owner restructured `testing/UI_fix_plan.md` twice in one day, first splitting it, then turning it into a kanban board with three columns. Both times this skill named the old sections and had to be rewritten by hand, and without that rewrite the next checkpoint would have rebuilt the sections the owner had just removed. A skill that recreates a section its owner deleted is a skill overruling a decision. So the shape lives in one registry row, a shape change is one row edit plus one decision row, and this skill never changes.

The rule that follows from it: this skill never creates, rebuilds or rewrites a section the registry does not list. If the work seems to need one, that is a decision for the product owner, not a section for the skill.

## Three modes

The steps differ by which kind of work the checkpoint closes. Determine the mode before running any step.

The third mode was added on 2026-09-20 because the skill had only two and neither fitted the work actually being done. The UI fix loop, a product-owner decision of 2026-09-12, replaces the build-phase cadence for UI fixes: no build phase, no branch, no pull request. Running build-phase mode against it asks for a merged build phase and a PR number that do not exist, and, worse, it never touches the board, which is the single owner of per-item status. A checkpoint that skips the one living document of the mode it is running in is not a checkpoint.

| | Planning-phase checkpoint | Build-phase checkpoint | UI-fix-loop checkpoint |
|---|---|---|---|
| Applies to | Plan.md Phases 2 to 5 | Plan.md Phase 6 onward, one run per merged build phase (1.0, 1.1, 1.2, ...) | The UI fix loop, product-owner decision of 2026-09-12 |
| Trigger | Finishing a sub-phase (2.3) or a full phase | A build phase's PR merges to `develop` | A working session ends, or a fix set closes. There is no PR and no build phase to wait for |
| Session doc | `requirements/phase_N/Session_<Month>_<Day>.md`, updated | N/A. `tracker/phase_N.M.md` already carries the ticket-by-ticket record, evidence, and history, written during the build itself, not at checkpoint time | N/A. The board carries the per-item record, and the done file's cutoff section carries the cutoff (both named in the registry) |
| Meeting note | `requirements/meetings/YYYY-MM-DD_Phase_N_steps_X-Y.md`, created or updated | N/A. No meeting-note convention exists for build execution; `LEARNINGS.md` plays the equivalent "what happened" role | N/A. A session report under `testing/Developer/reports/YYYY-MM-DD_*/` plays that role, written during the work |
| Handoff | `HANDOFF.md`, rewritten in place. The planning-phase continuation prompts under `requirements/phase_N/` are records of finished phases and are not refreshed | `HANDOFF.md`, rewritten in place | `HANDOFF.md`, rewritten in place |
| Synthesis doc | `requirements/phase_N/Phase_N_synthesis.md`, phase-end only | N/A per build phase. Step 6.2's one scheduled reconciliation plays this role once, mid-build, from the accumulated `LEARNINGS.md` record, not after every phase | N/A |
| Plan.md status | Bumped at phase-end only | Bumped every time, since a build phase is atomic: it merges as a whole PR, so every checkpoint is phase-end shaped, there is no partial-build-phase checkpoint | Revision history entry only. The Phase 6 status row names build phases, and a UI fix is not one, so do NOT bump it to name a fix set |

A planning-phase checkpoint can be sub-phase (mid-phase) or phase-end (whole phase closes); a build-phase checkpoint is always phase-end shaped, because Plan.md Phase 6's own numbered items (1.0, 1.1, ...) are each a complete, individually-merged unit by the time anyone would run this skill against one.

## One-owner convention

Every fact this checkpoint touches has exactly one owner file. A checkpoint updates the fact in its owner file and replaces every other mention with a pointer to that file. It never writes the same fact into two files. The registry is the full list of owners; the rows below are the ones this skill writes, stated by job.

| Fact | Single owner | Everywhere else |
|------|--------------|-------------------|
| Which documents this skill keeps current, and their current shape | `tracker/Living_documents.md` | Nowhere else. This skill names jobs, the registry names sections |
| What a fresh session needs: what is live, what awaits the product owner, the one next action, pointers | `HANDOFF.md`, under about 80 lines, rewritten in place | Nowhere else. It states no fact another file owns beyond its pointers, and never a count |
| Per-phase tickets, findings, evidence | `tracker/phase_N.M.md` | A pointer, never a copy |
| Phase status and open flags | `tracker/BOARD.md` | A pointer, for build phases only; the UI fix loop does not write it |
| What is not yet started, what is being built now, and what is live awaiting retest | The board, `testing/UI_fix_plan.md`, one card per item in the column its status says | Nowhere else. `tracker/BOARD.md` does NOT track UI fix items and is not expected to |
| Every closed item with its detail, the detail behind every card, the cutoff, the ordered next actions, and each day's shipped list as a session table | `testing/UI_fixes_done.md` | A pointer, never a copy. An item's card lives in exactly one board column until approved, and its detail lives in exactly one of the two files |
| Every query worth typing, what a person should see, and the retest steps the board's Retest cards point at by query number | `testing/Test_queries_and_workflows.md` | A pointer by query number, never a copy |
| Phase narrative and history | `requirements/Plan.md` Revision history | A pointer |
| Failures and their fixes | `LEARNINGS.md` | A pointer; Step 1b checks the session's failures are logged |
| Choices between alternatives | `DECISIONS.md` | A pointer |
| Build order | `requirements/Technical_specification.md` Section 25 | A pointer |
| Counts (tests, decisions, entries, flags) | Computed on demand by `python3 tracker/check_doc_drift.py --counts`, and stored in no document | Nowhere. No document states them as current and no step here writes one (build harness review item D1, 2026-09-25) |
| The plain-language state of the project, for a non-technical reader | `PROGRESS.md` | Nowhere else. It is the only document written for someone outside the build |

`PROGRESS.md` is the one deliberate exception to the pointer rule, and it is worth saying why. Every other row above avoids restating a fact because a second copy drifts. `PROGRESS.md` restates many of them on purpose, in different words, because its reader cannot follow a pointer into `tracker/phase_N.M.md` and get anything useful out of it. The protection against drift is that it is refreshed at Step 5b of every checkpoint, from the same sources, rather than edited ad hoc.

This is why Step 4 and Step 5 below say refresh and update, not add a new section. A build phase's own ticket-level detail belongs in `tracker/phase_N.M.md`, written during the build itself. The handoff and Plan.md hold only a pointer to it plus the current state, never a second copy of the ticket-level record.

## When to run

- Planning-phase checkpoint: after finishing a sub-phase (for example 2.3) or a full phase during requirements planning (Plan.md Phases 2 to 5).
- Build-phase checkpoint: after a build phase's pull request merges to `develop` (Plan.md Phase 6 onward).
- UI-fix-loop checkpoint: at the end of a working session in the UI fix loop, or when a fix set closes. Nothing merges to trigger it, so the trigger is the session boundary itself.
- Invoke explicitly with `/phase-checkpoint`. Do not auto-run. Whether a sub-phase or a build phase is actually done is a judgment the user makes, not a mechanical trigger.

## Inputs the skill needs

Confirm before writing. Ask if unclear from context:

1. Which mode: planning-phase, build-phase, or UI-fix-loop.
2. Planning-phase mode: which phase and sub-phase(s) this checkpoint closes (for example "Phase 2, steps 2.1 to 2.3"), and whether this is a sub-phase or a phase-end checkpoint (phase-end adds Step 5).
3. Build-phase mode: which build phase just merged (for example "1.0"), and its PR number.
4. UI-fix-loop mode: which fix set and which items changed state this session. There is no build phase and no PR number, so do not ask for either.

## Steps

### Step 0: the decision guard (all modes, before anything is written)

The first step, and the reason this skill no longer overrules a decision. Nothing is written until it is done.

1. Read `tracker/Living_documents.md` in full. It is the list of documents this run may write, and the shape of each.
2. Run `python3 tracker/check_living_docs.py --shape`. A red line names a document whose registered anchors are no longer in the file, or a row whose shape is `unpinned`. A red line is a question, not an instruction: the document may have been reshaped on purpose, and the registry is what is stale.
3. Read every `DECISIONS.md` row below the registry's watermark (the "decision guard watermark" section names the last guarded row), including rows appended this session and rows still uncommitted. For each row that changes a document's shape, its job, its owner, or a process this skill runs: edit that document's registry row first, and cite the decision row in its "Set by" cell. If the decision changes a process rather than a shape (a file family is no longer written, a step moves to another owner), the registry row records that, and this skill's job-level instruction below already follows the registry.
4. Rerun `--shape`. Every red line must now be explained by a registry edit made in this step, or by a shape still marked `unpinned` because the rewrite that pins it has not landed. A red line with no decision behind it means the document was reshaped without a recorded decision: STOP and ask the product owner whether the new shape stands (then log the row and register it) or the old one does (then they restore it). Never choose.
5. Move the watermark to the last row read, and set the registry's date line to today.

A planned edit that conflicts with a product-owner decision, at this step or any later one, stops the run and asks. The skill does not pick the reading that lets it continue.

### Step 1: DECISIONS.md (all modes)

- Scan the session for decisions made since the last checkpoint that are not yet in DECISIONS.md.
- Append each as a row (Date, Decision, Alternatives considered, Why). Append-only, never modify existing rows. Follow decision-logging.md.
- If every decision is already logged, say so and move on.
- A row appended here that changes a document's shape goes back through Step 0 before the run continues, so the registry never lags a decision this run itself made.

### Step 1b: LEARNINGS.md (all modes)

`LEARNINGS.md` was written by neither this skill nor `/ship`, so the session's lessons were reaching it only when someone remembered to log them by hand. This step closes that gap.

- Scan the session for failures that took more than a couple of minutes, wrong assumptions that cost rework, or fixes whose reason is not obvious from the code.
- For each one not yet in LEARNINGS.md, append a row in the `learnings` skill's shape: Date, Applies to, What broke, then a `<details><summary>what was tried</summary>` block and a `<details><summary>what fixed it</summary>` block.
- Append-only, never rewrite an existing row. No blank line inside the table.
- If nothing this session met the bar, say so and move on.

### Step 2: session doc (planning-phase mode only)

- Ensure the phase session file exists: `requirements/phase_N/Session_<Month>_<Day>.md` (per writing-style.md: one file per day, append each step as a section).
- Append or update sections for the sub-phase(s) closed, capturing discussion, rationale, and any diagrams. This is the detailed record and the personal learning log.
- Build-phase mode: skip, and say why (`tracker/phase_N.M.md` already holds this record).

### Step 3: meeting note (planning-phase mode only)

- Create or update the dated meeting note: `requirements/meetings/YYYY-MM-DD_Phase_N_steps_X-Y.md` (per writing-style.md).
- Nested bullets with an action-items section. Keep it a concise cadence record, not a duplicate of the session doc.
- Build-phase mode: skip, and say why (no meeting-note convention applies to build execution).

### Step 4: the handoff (all modes)

Rewrite `HANDOFF.md` in place. It replaced the Phase 6 continuation prompt on 2026-09-24 (the prompt is kept as `requirements/phase_6/Continuation_prompt-archive.md` and is never edited), because a file scoped to one phase and restating facts other files own went stale while the checkpoint ran every session: a CI line contradicted by the latest run, an open-items table whose rows CLAUDE.md recorded as closed, two superseded sections still on the page.

What it holds, and only this, in the sections the registry names for it:

- What is live: develop's product commit and production's tag, whether anything is being built between sessions, and whether CI is running. Hashes and tags, never counts.
- What awaits the product owner: retests and decisions, stated as pointers into the board's columns rather than as copied lists.
- The one next action: one line, naming where its reasons live.
- Where the facts live: the pointer table, one row per owner file.

Rules:

- Under about 80 lines. If it is longer, it is restating something an owner file already says: move the fact to its owner and leave a pointer.
- Rewritten in place, never appended to. Every sentence describing a state this session superseded is deleted, not left below the new one. This is the failure the rule exists to prevent: after five build phases handled as appends instead of rewrites, the old continuation prompt described build phase 2.1 in five contradictory sections at once, and its own copy-paste block told the next agent not to open build phase 2.2, the phase that was actually next.
- No history. What landed goes to Plan.md's Revision history (Step 5) and, in the UI fix loop, the done file's session table (Step 5a). No counts: none is stated in any document, and `python3 tracker/check_doc_drift.py --counts` computes them on demand.
- Set its date line to today. It is the one document every session end rewrites, so it is the one document dated at every session end.

### Step 5: synthesis and Plan status (all modes, different scope)

- Planning-phase mode, phase-end only: extend or write `requirements/phase_N/Phase_N_synthesis.md`, the topic-organized narrative of the phase's decisions, ready for the downstream phase.
- Build-phase mode: no per-phase synthesis doc (Step 6.2's one scheduled reconciliation plays that role once, mid-build). Instead, always update `requirements/Plan.md`: bump the Phase 6 status-table row to name the build phase just merged and the one next up, and append a Revision history entry naming what merged, its PR number, and its release-gate outcome (tests passing, findings fixed, any decisions logged). Plan.md no longer carries a separate "Summary of what happens next" paragraph, so there is no fourth edit to make; do not recreate one.
- UI-fix-loop mode: append a `requirements/Plan.md` Revision history entry naming the session's date, what landed, what was reverted or held and why, and any decision logged. Do NOT bump the Phase 6 status-table row, which names build phases; a fix set is not one, and writing one in there makes the table claim a phase exists that Section 25 does not contain.

### Step 5a: the board and the done file (UI-fix-loop mode only)

The board, `testing/UI_fix_plan.md`, is the single owner of what is not yet started, what is being built now, and what is live awaiting retest, so it is the first artifact this mode updates, not the last. It carries only its title, a short intro, its date line, and the columns the registry names. Everything else, every closed item, the cutoff, the detail behind every card, and the session tables, lives in `testing/UI_fixes_done.md`, in the sections the registry names. The product owner split the two on 2026-09-24 because one file holding both had grown past 2,500 lines and broke on every edit, and reshaped the plan into a board the same day so the columns, not a narrative tracker, are what they read first.

Each instruction below names a job. The registry row for the file says which section or column does that job today.

- WHEN AN ITEM GOES LIVE on develop: move its card from the building column to the retest column; move its detail from the section that holds detail for items on the board into that set's own section; add its row to the done file's index of finished features, with its test query number and the status the registry's owner uses for live-awaiting-retest; and make sure the query it points at exists in `testing/Test_queries_and_workflows.md`, since the card's steps are that query's number. On the product owner's approval, remove the card and set the done file's status for it to Approved.
- WHEN A NEW ITEM IS ADDED: write its card in the not-started column, in priority order with what it is waiting on (the values the column already uses), and its detail under the section for items on the board, before any work starts on it. The board is the source of truth for what gets worked on, so an item exists there first.
- WHEN WORK STARTS on a not-started item: move its card to the building column.
- Keep the columns current and in priority order. The building column carries the sentence the file already uses when nothing is being built. The retest column lists newest first.
- When a card moved, move the board's date line to today in the same edit. A board nothing changed on keeps its date.
- Rewrite the done file's cutoff section in place. It is the cutoff, and the next session starts from it rather than reconstructing state. It carries what is live, what is parked and why, what is waiting on the product owner, the known loose ends, and the ordered next actions. Set its date line to today.
- An item that was merged and then reverted is NOT quietly returned to its earlier status. Say it was reverted, and say what question is open, or the next session will re-land the same work into the same defect.
- Rewrite the ordered next actions in the same order as the not-started column. The two must agree: the ordered list is the detail and reasons behind the board's priority order, not a separate ordering.
- Add a session table, one row per item this session touched, under the done file's session history. This is the day's shipped list. No separate per-day file is written: the product owner stopped the `testing/Shipped_<date>.md` family on 2026-09-24 ("Yes, stop them"), and the three that exist are records.
- Rewrite the "how to start the next session" section in place, so its retest pointer names the right cards.

### Step 5b: PROGRESS.md, the plain-language update (all modes)

Refresh `PROGRESS.md` at the repository root. It is the one document written for someone who has never seen the code, a sprint-demo style update in ordinary English. It says:

- What works.
- What does not.
- What is next.

Every other artifact this skill touches is written for a builder. This one is not, and that is the whole point of keeping it separate rather than folding it into `README.md` (technical) or the handoff (written for the next agent).

What to update, every checkpoint, in the sections the registry names for it:

- The "what works today" list, in user-facing terms. What can a person actually do now that they could not do before this phase.
- The "what does not work yet" section, and its honest headline. Say the single biggest limitation in one sentence, in plain words.
- The sprint table: add a row for the phase that just merged, with its plain-terms description and its date.
- The "what is next" ordered list, so item 1 is genuinely the next thing.
- The known-problems table: add anything this phase carried, remove anything it closed, and keep each row's "when it gets fixed" honest rather than aspirational.

Rules for the writing, which are stricter here than anywhere else in the repository:

- No jargon at all, or explain it in the same sentence. Not "the guardrail rejects prompt injection" but "the gatekeeper turns away questions that try to manipulate the system".
- No internal identifiers in the body. A reader does not know what F-2.1-07 is. Describe the problem, not its ticket number.
- Concrete over abstract. "It currently only knows about one gene by name" beats "entity resolution coverage is limited".
- Keep the failures in. The value of this document is that a non-technical reader can see what went wrong and what it cost, not a sanitized highlight reel.

### Step 5c: the test queries (UI-fix-loop mode only)

`testing/Test_queries_and_workflows.md` is where the board's Retest cards point, by query number, which the product owner asked three times on 2026-09-23 to keep in step with the board. Its shape is whatever the registry says; while the registry marks it `unpinned`, do the minimum the job needs and nothing that assumes a section name:

- Every item shipped this session has a query: the exact text a person types, and what they should see. The board's Retest card for the item names that query's number.
- An item still being built gets its query written before the item lands, so the card can point at it the moment it goes live.
- A query's number is never renumbered once a card points at it.

There is no per-query status line to keep in step: the card's column is the status, and the 2026-09-24 rewrite removed the per-query lines.

### Step 6: structural hygiene pass (all modes)

Before the exit checklist, verify the structure of every document this checkpoint created or updated, per writing-style.md. This step exists because a status block was once crammed into a single run-on paragraph, and a table of contents lagged the body as sections were appended.

- No walls of text: any passage that enumerates three or more items (decisions, steps, sources, dispositions) is a bulleted list or a table, not a run-on paragraph chained by semicolons or commas. A status is a table; a changelog is a dated bullet list, newest first.
- Table of contents current: every `##` section added this checkpoint has a matching ToC entry, and the ToC lists all sections, not just the early ones.
- Status current: the handoff, the Plan.md status table, and any progress table name the correct current phase. No finished phase is labeled "next", and no just-merged build phase is labeled "not started".
- Titles and filenames current: a session doc or meeting note whose title or filename names fewer steps than it now covers is retitled, and the file renamed with `mv` (never `rm`) if the step span in the name is wrong.

### Step 7: the two checks (all modes)

- `python3 tracker/check_doc_drift.py --check`. It checks the structure of every tracked document (tables of contents, duplicate phase headings, the two append-only tables) and its phase and pull request references, and fails on a defect or on a fact it could not compute. It compares no count and runs no tests, so it takes seconds.
- `python3 tracker/check_living_docs.py --shape`: every registered anchor exists.

A nonzero exit from either blocks the checkpoint: fix the document the script names, then rerun. Never declare the checkpoint done on a failing or unrun check, and never edit a checker so it passes.

## Constraints

- Append-only for DECISIONS.md and session docs. Never delete or rewrite existing content.
- Follow writing-style.md (no em dashes, sentence case headings, no bold, no walls of text, ToC and status kept current, file naming conventions).
- Do not commit or push. Hand off to `/ship` for that.
- If a required input is missing (which mode, which phase or build phase, or sub-phase versus phase-end), ask before writing.
- Never write a section the registry does not list for that document, and never restore one a red `--shape` says is gone. Both are decisions, and Step 0 says what to do with a decision.
- Never invent a build phase in UI-fix-loop mode. There is no merged phase and no PR number; a checkpoint that writes one into Plan.md or the board makes both claim a phase Section 25 does not contain.
- Never invent a build phase or its deliverables. Build-phase mode content comes from `requirements/Technical_specification.md` Section 25 and the merged phase's own `tracker/phase_N.M.md`, not from memory.
- Write no count. Test, decision and learning counts are computed on demand by `python3 tracker/check_doc_drift.py --counts` and stated in no document. Build harness review item D1, delegated by the product owner on 2026-09-25 (DECISIONS.md, the lead implements both harness reviews' takeaways): 87 of the 92 commits to `CLAUDE.md` in the two weeks before only moved a count or a date.
- Move no date on its own. A document's "Last updated" line moves in the same edit that changes its content, and never in an edit of its own. `HANDOFF.md`, rewritten at every checkpoint (Step 4), is the one document dated at every session end. Review item D2, the same delegation.

## Exit checklist

Before declaring the checkpoint done, verify:

- [ ] Step 0 ran first: every DECISIONS.md row below the watermark was read, every shape or process change it made is in the registry with its "Set by" cell, the watermark moved, and no red `--shape` line is unexplained.
- [ ] Every decision made this session is in DECISIONS.md (append-only).
- [ ] Planning-phase mode: the phase session doc has a section for each sub-phase closed, and a dated meeting note exists with an action-items section.
- [ ] `HANDOFF.md` is rewritten in place, under about 80 lines, dated today, with no count and no fact another file owns beyond its pointers, and no sentence describing a state this session superseded.
- [ ] The fresh-session test: from `HANDOFF.md` alone, a new session can state what is live on develop and production, what awaits the product owner, and the one next action.
- [ ] UI-fix-loop mode: every card sits in the column its item's status says, every item that went live has its card in the retest column and its detail moved to the done file with its row in the index of finished features, and the done file's cutoff section is rewritten in place, naming what is parked and why.
- [ ] UI-fix-loop mode: the board carries only its title, intro, date line and the registered columns, and the not-started column's order matches the done file's ordered next actions.
- [ ] UI-fix-loop mode: the done file's session history has a table for this session, one row per item touched, and no `testing/Shipped_<date>.md` was created.
- [ ] UI-fix-loop mode: every item whose state changed says the same thing in the places that carry it: its card's column, its detail section, and its query in `testing/Test_queries_and_workflows.md`. Measured 2026-09-24: seven statuses had gone stale in the items' own detail because only a derived summary was updated.
- [ ] UI-fix-loop mode: `requirements/Plan.md` has a Revision history entry for the session, and its Phase 6 status row was NOT bumped to name a fix set.
- [ ] `PROGRESS.md` refreshed: the sprint table has a row for the phase that just merged, "what works today" and "what does not work yet" reflect the current state, item 1 of "what is next" is genuinely next, and the known-problems table matches the open flags on `tracker/BOARD.md`. Written in plain English with no internal finding identifiers in the body.
- [ ] Planning-phase mode, phase-end: the phase synthesis is updated.
- [ ] Build-phase mode: `requirements/Plan.md`'s status table and Revision history are both updated to name the merged build phase.
- [ ] No existing content in DECISIONS.md or a session doc was deleted or rewritten. Every other document this checkpoint touched was corrected in place: a superseded section was deleted, not left below the new one.
- [ ] No wall of text: every enumerated passage in a touched doc is a list or a table, not a run-on paragraph (writing-style.md).
- [ ] Every touched doc's table of contents, status, titles, and filenames are current: no missing ToC entry, no finished phase labeled "next", no title or filename naming fewer steps than the file covers.
- [ ] All modes: every failure the session hit is a row in LEARNINGS.md.
- [ ] All modes: no document this checkpoint touched states a test, decision or learning count as current, and no edit this checkpoint made only moved a date.
- [ ] `python3 tracker/check_doc_drift.py --check` exits 0.
- [ ] `python3 tracker/check_living_docs.py --shape` exits 0, or the only red line is a shape the registry marks `unpinned` and the report says so.

## Output

Report: which mode ran, what Step 0 found (rows read, registry rows changed, any stop), which artifacts were created or updated (with paths), the DECISIONS.md and LEARNINGS.md rows appended this session, (build-phase mode) which build phase just closed and which is next, and (UI-fix-loop mode) which fix items changed state and what `HANDOFF.md` now names as the next action. Suggest running `/ship` next to commit and push.
