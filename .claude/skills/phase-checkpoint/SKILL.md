---
name: phase-checkpoint
description: "Sync the planning documentation at a phase or sub-phase boundary during requirements planning: append new decisions to DECISIONS.md, update the phase session doc, create or update the dated meeting note, refresh the phase continuation prompt, and at a phase end extend the phase synthesis and bump Plan.md status. Invoke with /phase-checkpoint when you finish a sub-phase (x.y) or a full phase in Plan.md Phases 2 to 5. Distinct from /ship, which commits and pushes to GitHub: this updates the planning artifacts and runs before /ship, and never touches git. Distinct from /release, which is the local-verify-then-ship ritual for code changes."
scope: project
depends_on:
  - requirements/Plan.md
  - DECISIONS.md
  - .claude/rules/file-naming.md
  - .claude/rules/writing-style.md
  - .claude/rules/decision-logging.md
depended_by:
  - CLAUDE.md
  - AGENTS.md
---

# /phase-checkpoint - sync planning docs at a phase boundary

Purpose: at the end of a sub-phase (x.y) or a full phase, bring the planning documentation into a consistent state so a fresh session can resume with zero loss. User-invoked only. Does not commit or push (that is `/ship`).

This skill exists because the planning documentation ritual repeats across every requirements phase, and a single forgotten artifact (a stale continuation prompt, a missing meeting note) breaks a clean resume. The skill turns the ritual into a checklist so no artifact is skipped.

## When to run

- After finishing a sub-phase (for example 2.3) or a full phase during requirements planning (Plan.md Phases 2 to 5).
- Invoke explicitly with `/phase-checkpoint`. Do not auto-run. Whether a sub-phase is actually done is a judgment the user makes, not a mechanical trigger.

## Inputs the skill needs

Confirm two things before writing. Ask if either is unclear from context:

1. Which phase and sub-phase(s) this checkpoint closes (for example "Phase 2, steps 2.1 to 2.3").
2. Whether this is a sub-phase checkpoint (mid-phase) or a phase-end checkpoint (the whole phase is done). Phase-end adds Step 5.

## Steps

### Step 1: DECISIONS.md

- Scan the session for decisions made since the last checkpoint that are not yet in DECISIONS.md.
- Append each as a row (Date, Decision, Alternatives considered, Why). Append-only, never modify existing rows. Follow decision-logging.md.
- If every decision is already logged, say so and move on.

### Step 2: session doc

- Ensure the phase session file exists: `requirements/phase_N/Session_<Month>_<Day>.md` (per file-naming.md: one file per day, append each step as a section).
- Append or update sections for the sub-phase(s) closed, capturing discussion, rationale, and any diagrams. This is the detailed record and the personal learning log.

### Step 3: meeting note

- Create or update the dated meeting note: `requirements/meetings/YYYY-MM-DD_Phase_N_steps_X-Y.md` (per file-naming.md).
- Nested bullets with an action-items section. Keep it a concise cadence record, not a duplicate of the session doc.

### Step 4: continuation prompt

- Refresh `requirements/phase_N/Continuation_prompt.md`: update the progress tracker, the decisions-so-far list, the DECISIONS.md count, and the next-up section so a new chat can resume cleanly.

### Step 5 (phase-end only): synthesis and Plan status

- Extend or write `requirements/phase_N/Phase_N_synthesis.md`: the topic-organized narrative of the phase's decisions, ready for the downstream phase.
- Update `requirements/Plan.md`: bump the phase status, update the last-updated line and the top-of-file status paragraph, and note the threads carried forward.

### Step 6: structural hygiene pass

Before the exit checklist, verify the structure of every document this checkpoint created or updated, per writing-style.md. This step exists because a status block was once crammed into a single run-on paragraph, and a table of contents lagged the body as sections were appended.

- No walls of text: any passage that enumerates three or more items (decisions, steps, sources, dispositions) is a bulleted list or a table, not a run-on paragraph chained by semicolons or commas. A status is a table; a changelog is a dated bullet list, newest first.
- Table of contents current: every `##` section added this checkpoint has a matching ToC entry, and the ToC lists all sections, not just the early ones.
- Status and counts current: the continuation prompt, the Plan.md status table, and any progress table name the correct current phase and the correct DECISIONS.md count. No finished phase is labeled "next".
- Titles and filenames current: a session doc or meeting note whose title or filename names fewer steps than it now covers is retitled, and the file renamed with `mv` (never `rm`) if the step span in the name is wrong.

## Constraints

- Append-only for DECISIONS.md and session docs. Never delete or rewrite existing content.
- Follow writing-style.md (no em dashes, sentence case headings, no bold, no walls of text, ToC and status kept current) and file-naming.md.
- Do not commit or push. Hand off to `/ship` for that.
- If a required input is missing (which phase, or sub-phase versus phase-end), ask before writing.

## Exit checklist

Before declaring the checkpoint done, verify:

- [ ] Every decision made this session is in DECISIONS.md (append-only).
- [ ] The phase session doc has a section for each sub-phase closed.
- [ ] A dated meeting note exists for this session with an action-items section.
- [ ] The continuation prompt's progress tracker, decisions list, and next-up reflect current state.
- [ ] (phase-end) The phase synthesis and Plan.md status are updated.
- [ ] No existing content was deleted or rewritten.
- [ ] No wall of text: every enumerated passage in a touched doc is a list or a table, not a run-on paragraph (writing-style.md).
- [ ] Every touched doc's table of contents, status, counts, titles, and filenames are current: no missing ToC entry, no finished phase labeled "next", no stale count, no title or filename naming fewer steps than the file covers.

## Output

Report: which artifacts were created or updated (with paths), the new DECISIONS.md count, and whether this was a sub-phase or a phase-end checkpoint. Suggest running `/ship` next to commit and push.
