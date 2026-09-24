---
name: phase-checkpoint
description: "Sync planning, build and UI-fix-loop docs at a phase boundary. Runs at a planning sub-phase or phase end, a build phase's PR merge to develop or a UI-fix-loop session boundary. Refreshes PROGRESS.md in every mode. Planning mode also refreshes the session doc and continuation prompt. Build mode refreshes the Phase 6 continuation prompt and Plan.md status. UI-fix-loop mode refreshes the fix plan and the day's shipped list. Distinct from /ship, which commits and pushes: this updates artifacts and runs before /ship, never touching git."
scope: project
depends_on:
  - requirements/Plan.md
  - DECISIONS.md
  - tracker/BOARD.md
  - .claude/rules/writing-style.md
  - .claude/rules/decision-logging.md
depended_by:
  - CLAUDE.md
  - AGENTS.md
---

# /phase-checkpoint - sync planning or build docs at a phase boundary

Purpose: bring the relevant documentation into a consistent state at a phase boundary, so a fresh session can resume with zero loss. User-invoked only. Does not commit or push (that is `/ship`). Runs at the end of:

- A sub-phase or a full planning phase.
- A merged build phase.
- A UI-fix-loop session boundary.

This skill exists because the documentation ritual repeats at every phase boundary, and a single forgotten artifact (a stale continuation prompt, a Plan.md status line that still says "not started") breaks a clean resume. The skill turns the ritual into a checklist so no artifact is skipped, in any mode below.

## Table of contents

- [Three modes](#three-modes)
- [One-owner convention](#one-owner-convention)
- [When to run](#when-to-run)
- [Inputs the skill needs](#inputs-the-skill-needs)
- [Steps](#steps)
- [Constraints](#constraints)
- [Exit checklist](#exit-checklist)
- [Output](#output)

## Three modes

The steps differ by which kind of work the checkpoint closes. Determine the mode before running any step.

The third mode was added on 2026-09-20 because the skill had only two and neither fitted the work actually being done. The UI fix loop, a product-owner decision of 2026-09-12, replaces the build-phase cadence for UI fixes: no build phase, no branch, no pull request. Running build-phase mode against it asks for a merged build phase and a PR number that do not exist, and, worse, it never touches `testing/UI_fix_plan.md`, which is the single owner of per-item status and the cutoff. A checkpoint that skips the one living document of the mode it is running in is not a checkpoint.

| | Planning-phase checkpoint | Build-phase checkpoint | UI-fix-loop checkpoint |
|---|---|---|---|
| Applies to | Plan.md Phases 2 to 5 | Plan.md Phase 6 onward, one run per merged build phase (1.0, 1.1, 1.2, ...) | The UI fix loop, product-owner decision of 2026-09-12. Set 11 onward in `testing/UI_fix_plan.md` |
| Trigger | Finishing a sub-phase (2.3) or a full phase | A build phase's PR merges to `develop` | A working session ends, or a fix set closes. There is no PR and no build phase to wait for |
| Session doc | `requirements/phase_N/Session_<Month>_<Day>.md`, updated | N/A. `tracker/phase_N.M.md` already carries the ticket-by-ticket record, evidence, and history, written during the build itself, not at checkpoint time | N/A. `testing/UI_fix_plan.md`'s Set table carries the per-item record, and its "Where we stopped" section carries the cutoff |
| Meeting note | `requirements/meetings/YYYY-MM-DD_Phase_N_steps_X-Y.md`, created or updated | N/A. No meeting-note convention exists for build execution; `LEARNINGS.md` plays the equivalent "what happened" role | N/A. A session report under `testing/Developer/reports/YYYY-MM-DD_*/` plays that role, written during the work |
| Continuation prompt | `requirements/phase_N/Continuation_prompt.md`, one file per planning phase | `requirements/phase_6/Continuation_prompt.md`, one file spanning all of Phase 6, refreshed after every merged build phase, not created per sub-phase | `requirements/phase_6/Continuation_prompt.md`, same file. Only Step 2, the next action, and any session-boundary note |
| Synthesis doc | `requirements/phase_N/Phase_N_synthesis.md`, phase-end only | N/A per build phase. Step 6.2's one scheduled reconciliation plays this role once, mid-build, from the accumulated `LEARNINGS.md` record, not after every phase | N/A |
| Plan.md status | Bumped at phase-end only | Bumped every time, since a build phase is atomic: it merges as a whole PR, so every checkpoint is phase-end shaped, there is no partial-build-phase checkpoint | Revision history entry only. The Phase 6 status row names build phases, and a UI fix is not one, so do NOT bump it to name a fix set |

A planning-phase checkpoint can be sub-phase (mid-phase) or phase-end (whole phase closes); a build-phase checkpoint is always phase-end shaped, because Plan.md Phase 6's own numbered items (1.0, 1.1, ...) are each a complete, individually-merged unit by the time anyone would run this skill against one.

## One-owner convention

Every fact this checkpoint touches has exactly one owner file. A checkpoint updates the fact in its owner file and replaces every other mention with a pointer to that file. It never writes the same fact into two files.

| Fact | Single owner | Everywhere else |
|------|--------------|-------------------|
| Per-phase tickets, findings, evidence | `tracker/phase_N.M.md` | A pointer, never a copy |
| Phase status and open flags | `tracker/BOARD.md` | A pointer, for build phases only; the UI fix loop does not write it and its last write was 2026-09-01 |
| Per-item UI fix status, and the session cutoff | `testing/UI_fix_plan.md` for every item still being built or still to do, its open-item tables and its "Where we stopped" section; `testing/UI_fixes_done.md` for every finished item | A pointer, never a copy. `tracker/BOARD.md` does NOT track UI fix items and is not expected to. An item lives in exactly one of the two files |
| Phase narrative and history | `requirements/Plan.md` Revision history | A pointer |
| Current state and next action | `requirements/phase_6/Continuation_prompt.md` | A pointer |
| Failures and their fixes | `LEARNINGS.md` | A pointer; Step 1b checks the session's failures are logged |
| Choices between alternatives | `DECISIONS.md` | A pointer |
| Build order | `requirements/Technical_specification.md` Section 25 | A pointer |
| Counts (tests, decisions, entries, flags) | Computed by `tracker/check_doc_drift.py` | Only CLAUDE.md and the continuation prompt may state them |
| The plain-language state of the project, for a non-technical reader | `PROGRESS.md` | Nowhere else. It is the only document written for someone outside the build |
| The day's shipped list: one row per item shipped that day, the numbered "What to retest" items, and what was measured rather than built | `testing/Shipped_<YYYY-MM-DD>.md` | A pointer by item number, never a copy |
| Where every feature stands: features being built and still to do, additional notes | The high-level tracker at the top of `testing/UI_fix_plan.md`, refreshed by this checkpoint from the item rows it summarises, since it is a derived index and can drift | Nowhere else |
| Every finished feature, its test query and its retest item | The "Done features at a glance" table at the top of `testing/UI_fixes_done.md`, in step with `testing/Test_queries_and_workflows.md` and the shipped lists | Nowhere else |
| The tracked counts on line 32 of `CLAUDE.md` and `AGENTS.md` (Python tests, decisions, learnings) and Plan.md's "Decisions logged" line | This checkpoint, in Step 5d, from the values `tracker/check_doc_drift.py` computes | Nowhere else |

`PROGRESS.md` is the one deliberate exception to the pointer rule, and it is worth saying why. Every other row above avoids restating a fact because a second copy drifts. `PROGRESS.md` restates many of them on purpose, in different words, because its reader cannot follow a pointer into `tracker/phase_N.M.md` and get anything useful out of it. The protection against drift is that it is refreshed at Step 5b of every checkpoint, from the same sources, rather than edited ad hoc.

This is why Step 4 and Step 5 below say refresh and update, not add a new section. A build phase's own ticket-level detail belongs in `tracker/phase_N.M.md`, written during the build itself. The continuation prompt and Plan.md hold only a pointer to it plus the current state, never a second copy of the ticket-level record.

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

### Step 1: DECISIONS.md (all modes)

- Scan the session for decisions made since the last checkpoint that are not yet in DECISIONS.md.
- Append each as a row (Date, Decision, Alternatives considered, Why). Append-only, never modify existing rows. Follow decision-logging.md.
- If every decision is already logged, say so and move on.

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

### Step 4: continuation prompt (all modes, different target)

- Planning-phase mode: refresh `requirements/phase_N/Continuation_prompt.md`: update the progress tracker, the decisions-so-far list, the DECISIONS.md count, and the next-up section so a new chat can resume cleanly.
- Build-phase mode: refresh `requirements/phase_6/Continuation_prompt.md` instead, the single file spanning all of Phase 6. Update: the opening status line (which build phase just merged, its PR number), the "read these first" list (the current LEARNINGS.md count, the current `tracker/BOARD.md` state including any new flags), the "then start build phase X" command to name the next build phase, a short "build phase N.M, done" section summarizing what just merged, and the "what it delivers" section for the phase now next up. Carry forward any open item the merged phase's release gate created (for example an accepted CVE deferred to a later phase) into the "Open items to resolve during Phase 6" table.
- UI-fix-loop mode: rewrite Step 2 of `requirements/phase_6/Continuation_prompt.md` IN PLACE so its first bullet answers three questions in one line each for a fresh session: what is live on develop (commit hashes), what awaits the product owner's retest (item numbers in `testing/Shipped_<date>.md`), and the one next action (the fix plan's "Next, in order" item 1). Rewrite the "session boundary" subsection in place too: its "what landed" table, its "what did not land" list, its instruments-taught list, and its closing "what the next session does first" line. Delete any sentence describing a state the session superseded; never append a second version below the old one. Do NOT write a "build phase N.M, done" section: no build phase merged.
- The continuation prompt is rewritten in place, not appended to: every field above is edited where it already sits. A section describing a state the merge just superseded, a prior "build phase N.M, done" section, a prior status line, a prior "then start build phase X" pointer, is deleted, not left below the new one. This is the failure this rule exists to prevent: after five build phases handled as appends instead of rewrites, the file described build phase 2.1 in five contradictory sections at once, and its own copy-paste block told the next agent not to open build phase 2.2, the phase that was actually next.

### Step 5: synthesis and Plan status (all modes, different scope)

- Planning-phase mode, phase-end only: extend or write `requirements/phase_N/Phase_N_synthesis.md`, the topic-organized narrative of the phase's decisions, ready for the downstream phase.
- Build-phase mode: no per-phase synthesis doc (Step 6.2's one scheduled reconciliation plays that role once, mid-build). Instead, always update `requirements/Plan.md`: bump the Phase 6 status-table row to name the build phase just merged and the one next up, update the last-updated line, and append a Revision history entry naming what merged, its PR number, and its release-gate outcome (tests passing, findings fixed, any decisions logged). Plan.md no longer carries a separate "Summary of what happens next" paragraph, so there is no fourth edit to make; do not recreate one.

- UI-fix-loop mode: append a `requirements/Plan.md` Revision history entry naming the session's date, what landed, what was reverted or held and why, and any decision logged. Update the last-updated line. Do NOT bump the Phase 6 status-table row, which names build phases; a fix set is not one, and writing one in there makes the table claim a phase exists that Section 25 does not contain.

### Step 5a: the UI fix plan (UI-fix-loop mode only)

`testing/UI_fix_plan.md` is the single owner of what is being built, what is next and the cutoff, so it is the first artifact this mode updates, not the last. Finished items live in `testing/UI_fixes_done.md`: the product owner split the plan on 2026-09-24 because one file holding both had grown past 2,500 lines and broke on every edit.

- WHEN AN ITEM GOES LIVE on develop, move its row and its detail section, verbatim, from `testing/UI_fix_plan.md` to `testing/UI_fixes_done.md`, add its row to the done file's "Done features at a glance" table with its test query number and its shipped retest item, and leave ONE row in the plan's "To do" table, waiting on "Your retest", until the product owner approves it. On approval, delete that one row and set the done file's status to Approved.

- The item tables in both files: update the status word and the "where it stands" cell for every item that changed state this session, in whichever file the item lives. Status words are Live, In progress, Queued, Not started, Answered, Done, and any other word needs a reason in the cell.
- The "Where we stopped" section: rewrite it in place. It is the cutoff, and the next session starts from it rather than reconstructing state. It carries what is live, what is parked and why, what is waiting on the product owner, the known loose ends, and the ordered next actions.
- An item that was merged and then reverted is NOT quietly returned to its earlier status. Say it was reverted, and say what question is open, or the next session will re-land the same work into the same defect.
- Refresh the "Where every feature stands" tracker at the top of `testing/UI_fix_plan.md` for every item that changed state this session: features still to implement, features done (with the approval exceptions named item by item), and additional notes. It is a derived index of the rows below it and drifts if left alone.
- Add one row per item to the session table under "Where we stopped" for every item this session touched.
- Rewrite "Next, in order" and step 4 of "How to start the next session" in place, so item 1 is genuinely next and the retest range names the right item numbers.

### Step 5b: PROGRESS.md, the plain-language update (all modes)

Refresh `PROGRESS.md` at the repo root. It is the one document written for someone who has never seen the code, a sprint-demo style update in ordinary English. It says:

- What works.
- What does not.
- What is next.

Every other artifact this skill touches is written for a builder. This one is not, and that is the whole point of keeping it separate rather than folding it into `README.md` (technical) or the continuation prompt (written for the next agent).

What to update, every checkpoint:

- The "what works today" list, in user-facing terms. What can a person actually do now that they could not do before this phase.
- The "what does not work yet" section, and its honest headline. Say the single biggest limitation in one sentence, in plain words.
- The sprint table: add a row for the phase that just merged, with its plain-terms description and its date.
- The "what is next" ordered list, so item 1 is genuinely the next thing.
- The known-problems table: add anything this phase carried, remove anything it closed, and keep each row's "when it gets fixed" honest rather than aspirational.
- The last-updated date.

Rules for the writing, which are stricter here than anywhere else in the repo:

- No jargon at all, or explain it in the same sentence. Not "the guardrail rejects prompt injection" but "the gatekeeper turns away questions that try to manipulate the system".
- No internal identifiers in the body. A reader does not know what F-2.1-07 is. Describe the problem, not its ticket number.
- Concrete over abstract. "It currently only knows about one gene by name" beats "entity resolution coverage is limited".
- Keep the failures in. The value of this document is that a non-technical reader can see what went wrong and what it cost, not a sanitized highlight reel.

### Step 5c: the day's shipped list (UI-fix-loop mode only)

`testing/Shipped_<YYYY-MM-DD>.md` is created on the first ship of a day and extended after that on the same day.

- "What shipped, in order": one row per item, naming the item, its commit, and what a person notices.
- A numbered "What to retest" item for every shipped item, with the exact query a retester types and what they should see. The section's intro sentence must name the current range of items awaiting retest.
- "What was measured rather than built": the bullets recording what the session checked against reality rather than what it constructed.
- "What the day taught": a short closing note.

The continuation prompt and the fix plan point at these items by number, so a retest item's number must not be renumbered once written.

### Step 5d: the tracked counts (all modes)

- Run `python tracker/check_doc_drift.py --check`. It takes about two minutes, since it collects the whole test suite.
- For every "says X (computed: Y)" line it reports, update that document to Y: `CLAUDE.md` and `AGENTS.md` line 32 for tests, decisions, and learnings, and `requirements/Plan.md` line 20 for decisions.
- Set `CLAUDE.md`'s "Last updated" line to today.
- Never edit the checker to make it pass, per `.claude/rules/goal-contracts.md`.

### Step 6: structural hygiene pass (all modes)

Before the exit checklist, verify the structure of every document this checkpoint created or updated, per writing-style.md. This step exists because a status block was once crammed into a single run-on paragraph, and a table of contents lagged the body as sections were appended.

- No walls of text: any passage that enumerates three or more items (decisions, steps, sources, dispositions) is a bulleted list or a table, not a run-on paragraph chained by semicolons or commas. A status is a table; a changelog is a dated bullet list, newest first.
- Table of contents current: every `##` section added this checkpoint has a matching ToC entry, and the ToC lists all sections, not just the early ones.
- Status and counts current: the continuation prompt, the Plan.md status table, and any progress table name the correct current phase and the correct DECISIONS.md count. No finished phase is labeled "next", and no just-merged build phase is labeled "not started".
- Titles and filenames current: a session doc or meeting note whose title or filename names fewer steps than it now covers is retitled, and the file renamed with `mv` (never `rm`) if the step span in the name is wrong.

### Step 7: drift check (all modes)

Run `python tracker/check_doc_drift.py --check` before declaring the checkpoint done. It computes the tracked counts (tests, DECISIONS.md rows, LEARNINGS.md entries, open flags, PR numbers) from source and fails if any tracked document states a stale value. A nonzero exit blocks the checkpoint: fix the drifted document the script names in its output, then rerun the check. Never declare the checkpoint done on a failing or unrun drift check.

The check is run a second time here, after Step 5d's edits, so the run ends on a green check rather than on the one that named the stale values.

## Constraints

- Append-only for DECISIONS.md and session docs. Never delete or rewrite existing content.
- Follow writing-style.md (no em dashes, sentence case headings, no bold, no walls of text, ToC and status kept current, file naming conventions).
- Do not commit or push. Hand off to `/ship` for that.
- If a required input is missing (which mode, which phase or build phase, or sub-phase versus phase-end), ask before writing.
- Never invent a build phase in UI-fix-loop mode. There is no merged phase and no PR number; a checkpoint that writes one into Plan.md or the board makes both claim a phase Section 25 does not contain.
- Never invent a build phase or its deliverables. Build-phase mode content comes from `requirements/Technical_specification.md` Section 25 and the merged phase's own `tracker/phase_N.M.md`, not from memory.

## Exit checklist

Before declaring the checkpoint done, verify:

- [ ] Every decision made this session is in DECISIONS.md (append-only).
- [ ] Planning-phase mode: the phase session doc has a section for each sub-phase closed, and a dated meeting note exists with an action-items section.
- [ ] Build-phase mode: `requirements/phase_6/Continuation_prompt.md` names the correct just-merged build phase, the correct next-up build phase, the current LEARNINGS.md count, and any open item the merged phase's release gate created.
- [ ] UI-fix-loop mode: every item that changed state has the correct status in whichever file it lives, every item that went live has moved to `testing/UI_fixes_done.md` with its row in "Done features at a glance", and `testing/UI_fix_plan.md`'s "Where we stopped" section is rewritten in place as the cutoff, naming what is parked and why.
- [ ] UI-fix-loop mode: `requirements/Plan.md` has a Revision history entry for the session, and its Phase 6 status row was NOT bumped to name a fix set.
- [ ] `PROGRESS.md` refreshed: the sprint table has a row for the phase that just merged, "what works today" and "what does not work yet" reflect the current state, item 1 of "what is next" is genuinely next, the known-problems table matches the open flags on `tracker/BOARD.md`, and the last-updated date is today. Written in plain English with no internal finding identifiers in the body.
- [ ] The continuation prompt (whichever mode) reflects current state: no just-merged phase described as "not started" or "next up" to build.
- [ ] Planning-phase mode, phase-end: the phase synthesis is updated.
- [ ] Build-phase mode: `requirements/Plan.md`'s status table, last-updated line, and Revision history are all updated to name the merged build phase.
- [ ] No existing content in DECISIONS.md or a session doc was deleted or rewritten. Every other document this checkpoint touched, including the continuation prompt, was corrected in place: a superseded section was deleted, not left below the new one.
- [ ] No wall of text: every enumerated passage in a touched doc is a list or a table, not a run-on paragraph (writing-style.md).
- [ ] Every touched doc's table of contents, status, counts, titles, and filenames are current: no missing ToC entry, no finished phase labeled "next", no stale count, no title or filename naming fewer steps than the file covers.
- [ ] `python tracker/check_doc_drift.py --check` exits 0.
- [ ] UI-fix-loop mode: `testing/Shipped_<date>.md` has a row and a numbered retest item for every item shipped this session, and its "What to retest" intro names the current range.
- [ ] UI-fix-loop mode: the "Where every feature stands" tracker at the top of `testing/UI_fix_plan.md` agrees with every item row it summarises (spot-check each item that changed state).
- [ ] All modes: every failure the session hit is a row in LEARNINGS.md.
- [ ] All modes: the counts on CLAUDE.md and AGENTS.md line 32 and Plan.md's decisions line equal the drift check's computed values.
- [ ] The fresh-session test: from the continuation prompt's Step 2 alone, a new session can state what is live, what awaits retest and where, and the one next action.

## Output

Report: which mode ran, which artifacts were created or updated (with paths), the new DECISIONS.md count, (build-phase mode) which build phase just closed and which is next, (UI-fix-loop mode) which fix items changed state and what the next session starts on, the shipped list's new retest item numbers, and the count values written. Suggest running `/ship` next to commit and push.
