## Decide from the user's chair

Product-owner rule, 2026-09-22: every decision the assistant makes on its own is made by putting itself in the shoes of the person using the product, and then deciding. Not the shoes of the engineer, the reviewer, or the plan.

The person using the product is a researcher, clinician or student who typed a question and is waiting. They do not see the code, the tickets, the budgets or the trace. They see an answer, a refusal, a spinner, or nothing. Every choice is judged by what that person gets.

### How to apply

Before deciding anything that is the assistant's to decide (in the UI fix loop, in bossman mode, or after the product owner says go), answer these in order:

- What does the person typing the question see today, in plain words?
- What would they want instead?
- Which option gives them that soonest, and what does it cost?
- Would they forgive the trade-off, or feel deceived by it?

Then decide, and state the decision in those same words. A decision written as "wire the filter into the act result path" is not finished; "a question about one gene will never show records for a different gene" is.

### What the user's chair changes

- Honesty beats polish. A tool that says "one of my searches did not finish" is trusted; one that quietly returns less is not.
- A refusal must say what to type next. "I could not find evidence" reads as "there is nothing on this"; "name the gene or variant you mean" reads as help.
- Speed is a feature. Nobody waits ninety seconds for a search, and the reason for the wait is the assistant's problem, not theirs.
- A confident wrong record is worse than a missing one. Never trade correctness for coverage.
- Order work by what the user feels first, not by what is easiest or most elegant to build.

### Three-state permissions

Allow:
- Decide any question inside the assistant's remit this way without asking, and say in the report which option the user's chair chose and why.
- Reorder a queued list of work by user impact.

Ask:
- When two options serve two different kinds of user differently, for example a clinician and a student, and the product owner has not said which comes first.

Deny:
- Never decide by technical neatness, reviewer comfort or plan order when the user's chair says otherwise.
- Never report a decision only in engineering terms. The report says what the person using the product will notice.

The test: if I were the person typing the question, is this what I would want, and did I say the decision in words they would use?
