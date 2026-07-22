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

## Constraints

- Append-only for DECISIONS.md and session docs. Never delete or rewrite existing content.
- Follow writing-style.md (no em dashes, sentence case headings, no bold) and file-naming.md.
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

## Output

Report: which artifacts were created or updated (with paths), the new DECISIONS.md count, and whether this was a sub-phase or a phase-end checkpoint. Suggest running `/ship` next to commit and push.
