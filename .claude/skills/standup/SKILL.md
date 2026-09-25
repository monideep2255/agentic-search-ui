---
name: standup
description: "Answer where the build stands right now, in seven plain lines: the phase, what has landed, what is in motion this moment, what is next, how long until it is done, what decisions are waiting on the product owner, and what is blocked. Reports BOTH committed work and uncommitted work, including running agents, running commands, and what the assistant is mid-way through, since the product owner asking mid-flight is usually asking about the present and the present is not in the git log yet. Reads the tracker and git rather than the conversation, so it is correct in a fresh session and in a long one. TRIGGER on 'standup', 'catch me up', 'where are we', 'what is the status', 'what did I miss', 'what are you doing', 'quick update'. Distinct from task-tracker, which maintains the board and ticket detail: this only reports, never edits. Distinct from phase-checkpoint, which syncs planning documents at a phase boundary."
scope: project
---

# Standup skill

Seven lines, in plain words. No preamble, no headings, no ticket ids unless asked. Prefer bullets to sentences: a line carrying three or more things is a list, per `.claude/rules/writing-style.md`.

Its whole reason for existing is that the product owner asks "where are we" mid-flight, often while several agents are running, and the honest answer has to come from files rather than from what happens to be in this session's context. A summary reconstructed from conversation is wrong in a fresh session and stale in a long one.

## What to read, in this order

1. `git branch --show-current` and `git log --oneline -8`: what is actually committed, and on what.
2. `git status --short`: whether anything is uncommitted right now.
3. `tracker/BOARD.md`: the phase in flight and its open flags.
4. `tracker/phase_N.M.md` for that phase, bottom first: the newest sections carry the current state, and a WITHDRAWN or superseded heading there outranks anything older in the same file.
5. `HANDOFF.md`: what is live, what awaits the product owner, and the one next action the last session left for this one.

Skip any of these that cannot answer the question at hand. Reading all five costs little; reading none and answering from memory is the failure this skill prevents.

## The seven lines

- Phase: which build phase, and what it is about, in words a non-engineer follows.
- Landed: what is committed and verified. Name the user-visible effect, not the mechanism.
- Right now: what is in motion this moment and is NOT committed. See below; this line is the one most often skipped and the one most often wanted.
- Next: the one next action.
- Time to done: how long until this phase is finished, and what that estimate assumes. See below.
- Your call: the decisions waiting on the product owner, each written so the answer is yes, no, or pick one. See below.
- Blockers: what is stopping progress, or "None".

Write every line in plain words. A defect is what it did to a person, not its finding id. Prefer bullets over sentences, per `.claude/rules/writing-style.md`: if a line carries three or more things, break it into bullets rather than chaining them with commas.

## The "right now" line is mandatory

A standup built only from git history describes the past. The product owner asking "where are we" mid-flight is usually asking about the present, and the present is not in the log yet. Report both, always, even when one of them is empty. "Nothing uncommitted, nothing running" is a real and useful answer; silence about it is not.

Four sources, all cheap:

- `git status --short`: files edited but not committed. Say what they are and whether they are finished or half-done.
- Background agents: how many are running and what each was sent to do. Report them as RUNNING. Never state or guess their findings before they return, and never imply a result is in when it is not.
- Background commands: a live measurement, a long test run, a build. Say what it is measuring and that the number is not in yet.
- What the assistant is personally mid-way through in this turn: the file being edited, the probe being written, the thing being verified. This is invisible to every file on disk, so it exists only if it is said.

Two failure modes this line exists to prevent, both observed:

- Reporting a task as done because its agent was dispatched. A dispatched agent is not a result.
- Reporting a clean tree as "everything is committed" while several files are half-edited, so the product owner believes work is safe that would be lost.

If work is uncommitted, say plainly whether it is safe to interrupt.

## The "time to done" line

The product owner is deciding whether to wait, go do something else, or cut scope. None of that is answerable from a status list. So give a number, and give the two or three things it depends on.

How to build it honestly:

- Count what is left, not what is done. Open tickets on the phase file, plus any review round still owed.
- Price the work you can see. A ticket someone has already scoped is hours. A ticket that needs a decision first is unknown until the decision lands.
- Add the review rounds. This project's own history is that a phase takes more rounds than planned, so a phase with no review yet is not close to done however much code exists.
- State the assumption in the same breath. "Half a day if the review passes" and "half a day" are different claims, and only the first is honest.

Use ranges, not false precision. "One to two more sessions" beats "roughly 47 percent complete", which measures nothing.

Say "unknown, and here is what would tell us" when that is the truth. An estimate invented to fill the line is worse than no line, because it will be planned against.

Never let this line imply that running agents will succeed. If the estimate assumes a review passes, say so, because a FAIL verdict usually resets it.

## The "your call" line

The point of this line is that the product owner should never have to reverse-engineer a decision out of a status report. If something is waiting on them, it says so, in words that can be answered directly.

Write each decision as:

- The choice, in one sentence a non-engineer can answer.
- What it costs, in money, time, or risk, using real numbers where they exist.
- What happens if it waits. Some decisions block everything; most block one thing; a few can wait a week with no harm. Say which.
- A recommendation, where there is one, and the reason in a clause.

Rules for this line:

- One decision per bullet. Never bundle two questions into one sentence.
- No jargon in the question itself. The detail can carry a term of art; the question cannot.
- If nothing is waiting, say "Nothing waiting on you" and mean it. A standing invitation to review everything is not a decision.
- A decision already made is not repeated here. Move it to Landed or drop it.

The failure this prevents, observed: a status report that mentions a cost concern in passing, so the product owner does not realise a decision was theirs, and the work stalls while each side waits for the other.

## Rules

Plain language. A defect is described by what it did to a user, not by its finding id: "any visitor could read another visitor's conversation" rather than "F-4.5-J-02, an ownership comparison defect".

Say what is verified and what is only claimed. If a fix was written by an agent and nobody independently checked it, that belongs in the standup, because it is exactly the difference between done and looks done.

Report background work as running, never as finished. If agents are in flight, say how many and on what. Never predict what they will find.

Report a withdrawn or corrected finding as withdrawn. A blocker named yesterday and disproven today must not survive into today's standup, and the correction is worth one clause: "reported a blocker last night, it was my measuring tool, not the code".

Seven lines is the shape, not a quota. Five of them are almost always needed. Two are allowed to be short:

- Time to done can be "unknown, and here is what would tell us".
- Your call can be "nothing waiting on you".

Saying either of those is a real answer. Omitting the line is not, because silence reads as "no decision needed" and that is exactly the failure these two lines exist to prevent.

Never edit anything. This skill reads and reports. `task-tracker` owns the board, `phase-checkpoint` owns the planning documents, `learnings` owns LEARNINGS.md.

## When NOT to use

- The product owner asked a specific technical question. Answer that question instead.
- A phase just closed and the documents need syncing: that is `phase-checkpoint`.
- The request is for the full findings ledger or ticket detail: that is `task-tracker` or the phase file itself.
