---
name: phase-checkpoint
description: "Sync planning or build documentation at a phase boundary: after closing a planning sub-phase or full phase (Plan.md Phases 2 to 5), or after a build phase's pull request merges to main (Plan.md Phase 6 onward, one checkpoint per merged build phase). Appends new decisions to DECISIONS.md and refreshes the mode-appropriate artifacts: the planning session doc, meeting note, and phase continuation prompt in planning mode, or the Phase 6 continuation prompt and Plan.md status in build mode. Distinct from /ship, which commits and pushes to GitHub: this updates the planning artifacts and runs before /ship, and never touches git. Distinct from /release, which is the local-verify-then-ship ritual for code changes."
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

Purpose: at the end of a sub-phase, a full planning phase, or a merged build phase, bring the relevant documentation into a consistent state so a fresh session can resume with zero loss. User-invoked only. Does not commit or push (that is `/ship`).

This skill exists because the documentation ritual repeats at every phase boundary, and a single forgotten artifact (a stale continuation prompt, a Plan.md status line that still says "not started") breaks a clean resume. The skill turns the ritual into a checklist so no artifact is skipped, in either mode below.

## Two modes

The steps differ by which side of Plan.md Phase 6 the checkpoint falls on. Determine the mode before running any step.

| | Planning-phase checkpoint | Build-phase checkpoint |
|---|---|---|
| Applies to | Plan.md Phases 2 to 5 | Plan.md Phase 6 onward, one run per merged build phase (1.0, 1.1, 1.2, ...) |
| Trigger | Finishing a sub-phase (2.3) or a full phase | A build phase's PR merges to `main` |
| Session doc | `requirements/phase_N/Session_<Month>_<Day>.md`, updated | N/A. `tracker/phase_N.M.md` already carries the ticket-by-ticket record, evidence, and history, written during the build itself, not at checkpoint time |
| Meeting note | `requirements/meetings/YYYY-MM-DD_Phase_N_steps_X-Y.md`, created or updated | N/A. No meeting-note convention exists for build execution; `LEARNINGS.md` plays the equivalent "what happened" role |
| Continuation prompt | `requirements/phase_N/Continuation_prompt.md`, one file per planning phase | `requirements/phase_6/Continuation_prompt.md`, one file spanning all of Phase 6, refreshed after every merged build phase, not created per sub-phase |
| Synthesis doc | `requirements/phase_N/Phase_N_synthesis.md`, phase-end only | N/A per build phase. Step 6.2's one scheduled reconciliation plays this role once, mid-build, from the accumulated `LEARNINGS.md` record, not after every phase |
| Plan.md status | Bumped at phase-end only | Bumped every time, since a build phase is atomic: it merges as a whole PR, so every checkpoint is phase-end shaped, there is no partial-build-phase checkpoint |

A planning-phase checkpoint can be sub-phase (mid-phase) or phase-end (whole phase closes); a build-phase checkpoint is always phase-end shaped, because Plan.md Phase 6's own numbered items (1.0, 1.1, ...) are each a complete, individually-merged unit by the time anyone would run this skill against one.

## One-owner convention

Every fact this checkpoint touches has exactly one owner file. A checkpoint updates the fact in its owner file and replaces every other mention with a pointer to that file. It never writes the same fact into two files.

| Fact | Single owner | Everywhere else |
|------|--------------|-------------------|
| Per-phase tickets, findings, evidence | `tracker/phase_N.M.md` | A pointer, never a copy |
| Phase status and open flags | `tracker/BOARD.md` | A pointer |
| Phase narrative and history | `requirements/Plan.md` Revision history | A pointer |
| Current state and next action | `requirements/phase_6/Continuation_prompt.md` | A pointer |
| Failures and their fixes | `LEARNINGS.md` | A pointer |
| Choices between alternatives | `DECISIONS.md` | A pointer |
| Build order | `requirements/Technical_specification.md` Section 25 | A pointer |
| Counts (tests, decisions, entries, flags) | Computed by `tracker/check_doc_drift.py` | Only CLAUDE.md and the continuation prompt may state them |
| The plain-language state of the project, for a non-technical reader | `PROGRESS.md` | Nowhere else. It is the only document written for someone outside the build |

`PROGRESS.md` is the one deliberate exception to the pointer rule, and it is worth saying why. Every other row above avoids restating a fact because a second copy drifts. `PROGRESS.md` restates many of them on purpose, in different words, because its reader cannot follow a pointer into `tracker/phase_N.M.md` and get anything useful out of it. The protection against drift is that it is refreshed at Step 5b of every checkpoint, from the same sources, rather than edited ad hoc.

This is why Step 4 and Step 5 below say refresh and update, not add a new section. A build phase's own ticket-level detail belongs in `tracker/phase_N.M.md`, written during the build itself. The continuation prompt and Plan.md hold only a pointer to it plus the current state, never a second copy of the ticket-level record.

## When to run

- Planning-phase checkpoint: after finishing a sub-phase (for example 2.3) or a full phase during requirements planning (Plan.md Phases 2 to 5).
- Build-phase checkpoint: after a build phase's pull request merges to `main` (Plan.md Phase 6 onward).
- Invoke explicitly with `/phase-checkpoint`. Do not auto-run. Whether a sub-phase or a build phase is actually done is a judgment the user makes, not a mechanical trigger.

## Inputs the skill needs

Confirm before writing. Ask if unclear from context:

1. Which mode: planning-phase or build-phase.
2. Planning-phase mode: which phase and sub-phase(s) this checkpoint closes (for example "Phase 2, steps 2.1 to 2.3"), and whether this is a sub-phase or a phase-end checkpoint (phase-end adds Step 5).
3. Build-phase mode: which build phase just merged (for example "1.0"), and its PR number.

## Steps

### Step 1: DECISIONS.md (both modes)

- Scan the session for decisions made since the last checkpoint that are not yet in DECISIONS.md.
- Append each as a row (Date, Decision, Alternatives considered, Why). Append-only, never modify existing rows. Follow decision-logging.md.
- If every decision is already logged, say so and move on.

### Step 2: session doc (planning-phase mode only)

- Ensure the phase session file exists: `requirements/phase_N/Session_<Month>_<Day>.md` (per writing-style.md: one file per day, append each step as a section).
- Append or update sections for the sub-phase(s) closed, capturing discussion, rationale, and any diagrams. This is the detailed record and the personal learning log.
- Build-phase mode: skip, and say why (`tracker/phase_N.M.md` already holds this record).

### Step 3: meeting note (planning-phase mode only)

- Create or update the dated meeting note: `requirements/meetings/YYYY-MM-DD_Phase_N_steps_X-Y.md` (per writing-style.md).
- Nested bullets with an action-items section. Keep it a concise cadence record, not a duplicate of the session doc.
- Build-phase mode: skip, and say why (no meeting-note convention applies to build execution).

### Step 4: continuation prompt (both modes, different target)

- Planning-phase mode: refresh `requirements/phase_N/Continuation_prompt.md`: update the progress tracker, the decisions-so-far list, the DECISIONS.md count, and the next-up section so a new chat can resume cleanly.
- Build-phase mode: refresh `requirements/phase_6/Continuation_prompt.md` instead, the single file spanning all of Phase 6. Update: the opening status line (which build phase just merged, its PR number), the "read these first" list (the current LEARNINGS.md count, the current `tracker/BOARD.md` state including any new flags), the "then start build phase X" command to name the next build phase, a short "build phase N.M, done" section summarizing what just merged, and the "what it delivers" section for the phase now next up. Carry forward any open item the merged phase's release gate created (for example an accepted CVE deferred to a later phase) into the "Open items to resolve during Phase 6" table.
- The continuation prompt is rewritten in place, not appended to: every field above is edited where it already sits. A section describing a state the merge just superseded, a prior "build phase N.M, done" section, a prior status line, a prior "then start build phase X" pointer, is deleted, not left below the new one. This is the failure this rule exists to prevent: after five build phases handled as appends instead of rewrites, the file described build phase 2.1 in five contradictory sections at once, and its own copy-paste block told the next agent not to open build phase 2.2, the phase that was actually next.

### Step 5: synthesis and Plan status (both modes, different scope)

- Planning-phase mode, phase-end only: extend or write `requirements/phase_N/Phase_N_synthesis.md`, the topic-organized narrative of the phase's decisions, ready for the downstream phase.
- Build-phase mode: no per-phase synthesis doc (Step 6.2's one scheduled reconciliation plays that role once, mid-build). Instead, always update `requirements/Plan.md`: bump the Phase 6 status-table row to name the build phase just merged and the one next up, update the last-updated line, and append a Revision history entry naming what merged, its PR number, and its release-gate outcome (tests passing, findings fixed, any decisions logged). Plan.md no longer carries a separate "Summary of what happens next" paragraph, so there is no fourth edit to make; do not recreate one.

### Step 5b: PROGRESS.md, the plain-language update (both modes)

Refresh `PROGRESS.md` at the repo root. It is the one document written for someone who has never seen the code: a sprint-demo style update in ordinary English, saying what works, what does not, and what is next.

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

### Step 6: structural hygiene pass (both modes)

Before the exit checklist, verify the structure of every document this checkpoint created or updated, per writing-style.md. This step exists because a status block was once crammed into a single run-on paragraph, and a table of contents lagged the body as sections were appended.

- No walls of text: any passage that enumerates three or more items (decisions, steps, sources, dispositions) is a bulleted list or a table, not a run-on paragraph chained by semicolons or commas. A status is a table; a changelog is a dated bullet list, newest first.
- Table of contents current: every `##` section added this checkpoint has a matching ToC entry, and the ToC lists all sections, not just the early ones.
- Status and counts current: the continuation prompt, the Plan.md status table, and any progress table name the correct current phase and the correct DECISIONS.md count. No finished phase is labeled "next", and no just-merged build phase is labeled "not started".
- Titles and filenames current: a session doc or meeting note whose title or filename names fewer steps than it now covers is retitled, and the file renamed with `mv` (never `rm`) if the step span in the name is wrong.

### Step 7: drift check (both modes)

Run `python tracker/check_doc_drift.py --check` before declaring the checkpoint done. It computes the tracked counts (tests, DECISIONS.md rows, LEARNINGS.md entries, open flags, PR numbers) from source and fails if any tracked document states a stale value. A nonzero exit blocks the checkpoint: fix the drifted document the script names in its output, then rerun the check. Never declare the checkpoint done on a failing or unrun drift check.

## Constraints

- Append-only for DECISIONS.md and session docs. Never delete or rewrite existing content.
- Follow writing-style.md (no em dashes, sentence case headings, no bold, no walls of text, ToC and status kept current, file naming conventions).
- Do not commit or push. Hand off to `/ship` for that.
- If a required input is missing (which mode, which phase or build phase, or sub-phase versus phase-end), ask before writing.
- Never invent a build phase or its deliverables. Build-phase mode content comes from `requirements/Technical_specification.md` Section 25 and the merged phase's own `tracker/phase_N.M.md`, not from memory.

## Exit checklist

Before declaring the checkpoint done, verify:

- [ ] Every decision made this session is in DECISIONS.md (append-only).
- [ ] Planning-phase mode: the phase session doc has a section for each sub-phase closed, and a dated meeting note exists with an action-items section.
- [ ] Build-phase mode: `requirements/phase_6/Continuation_prompt.md` names the correct just-merged build phase, the correct next-up build phase, the current LEARNINGS.md count, and any open item the merged phase's release gate created.
- [ ] `PROGRESS.md` refreshed: the sprint table has a row for the phase that just merged, "what works today" and "what does not work yet" reflect the current state, item 1 of "what is next" is genuinely next, the known-problems table matches the open flags on `tracker/BOARD.md`, and the last-updated date is today. Written in plain English with no internal finding identifiers in the body.
- [ ] The continuation prompt (whichever mode) reflects current state: no just-merged phase described as "not started" or "next up" to build.
- [ ] Planning-phase mode, phase-end: the phase synthesis is updated.
- [ ] Build-phase mode: `requirements/Plan.md`'s status table, last-updated line, and Revision history are all updated to name the merged build phase.
- [ ] No existing content in DECISIONS.md or a session doc was deleted or rewritten. Every other document this checkpoint touched, including the continuation prompt, was corrected in place: a superseded section was deleted, not left below the new one.
- [ ] No wall of text: every enumerated passage in a touched doc is a list or a table, not a run-on paragraph (writing-style.md).
- [ ] Every touched doc's table of contents, status, counts, titles, and filenames are current: no missing ToC entry, no finished phase labeled "next", no stale count, no title or filename naming fewer steps than the file covers.
- [ ] `python tracker/check_doc_drift.py --check` exits 0.

## Output

Report: which mode ran, which artifacts were created or updated (with paths), the new DECISIONS.md count, and (build-phase mode) which build phase just closed and which is next. Suggest running `/ship` next to commit and push.
