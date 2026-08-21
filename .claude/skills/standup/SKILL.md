---
name: standup
description: "Answer where the build stands right now, in four plain lines: the phase, what worked, what is next, what is blocked. Reads the tracker and git rather than the conversation, so it is correct in a fresh session and in a long one. TRIGGER on 'standup', 'catch me up', 'where are we', 'what is the status', 'what did I miss', 'quick update'. Distinct from task-tracker, which maintains the board and ticket detail: this only reports, never edits. Distinct from phase-checkpoint, which syncs planning documents at a phase boundary."
scope: project
---

# Standup skill

Four lines. No preamble, no headings, no ticket ids unless asked.

Its whole reason for existing is that the product owner asks "where are we" mid-flight, often while several agents are running, and the honest answer has to come from files rather than from what happens to be in this session's context. A summary reconstructed from conversation is wrong in a fresh session and stale in a long one.

## What to read, in this order

1. `git branch --show-current` and `git log --oneline -8`: what is actually committed, and on what.
2. `git status --short`: whether anything is uncommitted right now.
3. `tracker/BOARD.md`: the phase in flight and its open flags.
4. `tracker/phase_N.M.md` for that phase, bottom first: the newest sections carry the current state, and a WITHDRAWN or superseded heading there outranks anything older in the same file.
5. `requirements/phase_6/Continuation_prompt.md`, the "State now" and "The next session starts here" sections: what the last session left for this one.

Skip any of these that cannot answer the question at hand. Reading all five costs little; reading none and answering from memory is the failure this skill prevents.

## The four lines

- Phase: which build phase, and what it is about, in words a non-engineer follows.
- What worked: what actually landed and is verified. Name the user-visible effect, not the mechanism.
- Next: the one next action.
- Blockers: what is stopping progress, or "None". If something needs the product owner's decision, say so here and say what the decision is.

## Rules

Plain language. A defect is described by what it did to a user, not by its finding id: "any visitor could read another visitor's conversation" rather than "F-4.5-J-02, an ownership comparison defect".

Say what is verified and what is only claimed. If a fix was written by an agent and nobody independently checked it, that belongs in the standup, because it is exactly the difference between done and looks done.

Report background work as running, never as finished. If agents are in flight, say how many and on what. Never predict what they will find.

Report a withdrawn or corrected finding as withdrawn. A blocker named yesterday and disproven today must not survive into today's standup, and the correction is worth one clause: "reported a blocker last night, it was my measuring tool, not the code".

Four lines is the default, not a cap. If the honest answer needs a fifth, use it. If two lines cover it, use two.

Never edit anything. This skill reads and reports. `task-tracker` owns the board, `phase-checkpoint` owns the planning documents, `learnings` owns LEARNINGS.md.

## When NOT to use

- The product owner asked a specific technical question. Answer that question instead.
- A phase just closed and the documents need syncing: that is `phase-checkpoint`.
- The request is for the full findings ledger or ticket detail: that is `task-tracker` or the phase file itself.
