## Decision cadence

Product-owner rule, 2026-09-27: a decision that is the product owner's is asked the moment it comes up, not held for a daily list. This replaces the batching language in earlier rules and skills, which capped questions at ten a day and wrote them once a day into a list.

The product owner's own words: "anytime you need a decision, from me ... you're going to ask that question ... until and unless I tell you I'm going to sleep or I'm busy, and I want you to run overnight, then you ask the questions before. But if some questions come up ... during the day, if you send me a notification, I'm going to respond to it because I have the remote version on ... that rule should be baked in to maybe boss man mode, verify, or any of the, these things."

A decision held for a list waits hours for an answer the owner can give in seconds from their phone, and any work that depends on it stalls for no reason. The ten-a-day cap existed to avoid flooding the owner. The notification's cost is the owner's to judge, and they have asked for it.

### The cadence

1. When a decision is the owner's to make, ask it at once, through the question tool, as a yes, no or pick-one question, with the recommendation first and the cost of each option in plain words. At the same moment, send a phone notification: one line, under 200 characters, naming the decision and the recommendation.
2. Keep working on everything that does not wait on the answer. Work that does wait on it stops at a clean point.
3. When the owner says they are going to sleep, are busy, or want an overnight run, ask every decision foreseeable before they go, and record the answers.
4. A decision that comes up while the owner is away:
   - Takes the recommended option only where a standing owner decision already covers it, such as merging a pull request whose checks pass.
   - Otherwise, stops that line of work, queues the question, sends the notification, and asks it the moment the owner is back.
5. A decision is never buried in a status report, never held for a daily list, and never bundled with another. One question per decision. Several independent decisions may go into one question-tool call, each still its own question.
6. Every decision and its answer lands as a `DECISIONS.md` row, as today.

This agrees with `communication-style`'s "ask ONE question at a time": one question per decision, never one decision per day. A list of several decisions is fine only when each item in it is asked and answered as its own question, in order, as `communication-style` already requires.

### Where this applies

Any place a rule or skill in this repository escalates to the product owner:

- Bossman mode, at every dial position.
- The UI fix loop.
- `/verify`.
- `/standup`.
- `/phase-checkpoint`.
- Any future skill that asks the owner something.

A skill that names a specific escalation point points here rather than restating the cadence.

### Three-state permissions

Allow:
- Ask a product-owner decision the moment it is identified, with a notification, without waiting for any other decision to accumulate.
- Take the recommended option on a decision a standing owner decision already covers, while the owner is away.
- Put several independent decisions into one question-tool call, each asked and answered as its own question.

Ask:
- Nothing here needs asking beyond the decision itself; this rule is about when to ask, not whether.

Deny:
- Never hold a decision for a daily list, a status report, or a batch of ten.
- Never bundle two decisions into one question.
- Never take an unrecommended or non-standing action on the owner's behalf while they are away; queue it and ask when they return.
- Never skip the `DECISIONS.md` row for a decision and its answer.

The test: did this decision reach the owner the moment it came up, as its own question with a notification, or did it wait for a list?
