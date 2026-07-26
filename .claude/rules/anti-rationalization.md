---
description: "Block the LLM from rationalizing away steps in multi-step skills by naming common shortcuts and countering them."
scope: portable
alwaysApply: true
---

## Anti-rationalization

LLMs quietly skip steps in multi-step skills when those steps feel like "extra work" relative to just answering. Repeating "do the step" does not fix it because the model already saw the instruction. What works: naming the likely excuse and explicitly blocking it.

This pattern comes from testing 25+ skills over 75 runs (Aakash Gupta's 10 Laws for High-Trust Skills, Law 7).

### Common rationalizations and counters

| The model thinks | The counter |
|------------------|-------------|
| "The user already validated this, so I can skip the existence check" | The user asked you to run the full skill. Run every step. |
| "This is straightforward enough that I don't need the self-review" | Straightforward tasks are where errors hide. Run the review. |
| "I already know the answer from context, so I can skip reading the file" | Your memory of file contents may be stale. Read the file. |
| "The user seems in a hurry, so I'll skip the non-critical steps" | Speed is not permission to skip. If a step is in the skill, it is critical. |
| "This step is similar to what I just did, so it's redundant" | Similar is not identical. Run it separately. |
| "The output is good enough without the final formatting pass" | "Good enough" is not the bar. The exit checklist is the bar. |
| "I can combine these steps to be more efficient" | Combining steps loses intermediate verification. Run them separately unless the skill explicitly says to combine. |

### When to apply

- Any skill with 4+ steps, including `/ship`, `/release`, `/dev-standards`, `/verify`, and bossman-mode phases
- Any skill with an exit checklist
- Any skill where the model has previously skipped steps (add the specific rationalization to this table)

### When NOT to apply

- Simple, single-step tasks
- When the user explicitly says "skip step X" or "just the essentials"
- When in bossman-mode execution (speed is prioritized, but exit checklists still apply)

### How to extend this rule

When you notice a new rationalization pattern (Claude skipping a step and producing a plausible excuse), add it to the table above. This rule should grow from real failures, not hypothetical ones.

The test: did I run every step in the skill, or did I skip one with a plausible excuse?
