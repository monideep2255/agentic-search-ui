---
description: "Always identify and attack the bottleneck before optimizing anything else."
scope: portable
alwaysApply: false
paths: ["HANDOFF.md", "DECISIONS.md", "LEARNINGS.md", "testing/UI_fix_plan.md", "testing/UI_fixes_done.md", "docs/build/*", ".claude/skills/bossman-mode/*", ".claude/skills/bossman-mode/reference/*", "{tracker,requirements}/**/*"]
---
## Attack the constraint

Before optimizing, automating, or adding to any system, ask: **what is the bottleneck right now?**

Optimizing a non-bottleneck is wasted effort. Elon's version: "Attack the constraint" - find what's actually limiting throughput and focus resources there.

**The question to ask:**

For any goal, project, or system: what single thing, if removed or improved, would unlock the most progress? Is the constraint time, skill, clarity, access, or tooling?

**Apply when:**
- Planning a pipeline phase - what data format issue is actually blocking progress, not parser optimization?
- Choosing what to fix - which parser error blocks the gate, not which code looks cleanest?
- Reviewing the OS itself - is the system overhead (rules, docs-sync, retros) justified by the value it creates?
- Weekly reflection - what blocked me this week? Same thing as last week? Then it's the real constraint.

**Do NOT apply when:**
- The constraint is external and you can't act on it (waiting on someone else)
- You're in execution mode on a clear plan - don't re-question the plan mid-sprint

**Idiot index check:**
When something feels expensive (in time, effort, or friction), break it into components. How much of the cost is the actual work vs overhead, process, or indecision? A high ratio of overhead to actual work means the constraint is the process, not the task.

**The Algorithm (when the constraint is process overhead):**

Once you've identified the bottleneck as process, run these 5 steps in order. The order matters - don't skip ahead.

1. **Make requirements less dumb** - question every requirement. Who asked for this? Are they still right? Ownerless requirements are suspect by default.
2. **Delete** - remove whole steps, parts, or processes entirely. If you never have to add something back ~10% of the time, you're not deleting aggressively enough.
3. **Simplify** - only after deletion. Otherwise you're polishing things that shouldn't exist.
4. **Accelerate** - speed up cycle times only once you're building the right, simplified thing. "If you're digging your grave, don't dig it faster."
5. **Automate** - last, not first. Automating a broken process just produces fast wrongness.

**When the output is model-generated, read the INPUT first**

A model that produces a wrong answer is the visible symptom. What it was
given is the constraint, and it is almost always cheaper to inspect.

Build phase 2.1 measured it: `cypher_query` returned twenty-five non-human
orthologs for "which diseases are associated with BRCA1?", every row
correctly cited, and three review rounds hardened the parameter binder in
response, roughly 25 real defects fixed, none of them causal, before
printing the assembled prompt on round five showed the schema slice
handed to the model contained no Disease label at all. Full account:
LEARNINGS.md's retrospective ("why build phase 2.1 took five review
rounds").

So before debugging a wrong generated output:

- Print the exact prompt, tool schema, or retrieved context the model
  actually received, not the one the code is supposed to assemble.
- Check whether the correct answer is even EXPRESSIBLE from what it was
  given. If it is not, the generation is not the defect.
- Only then look at what the model did with it.

The general form: when a component is fed by an assembly step, the
assembly step is upstream of it and is therefore the constraint until
proven otherwise. Optimizing the fed component is optimizing a
non-bottleneck.

**Examples:**
- Cypher generation timeouts survived a 3x budget increase, 30s to 90s, 9 of 10 real-model queries still timed out - the constraint was the plan tier's reasoning effort spent on one line of Cypher, not the timeout value. Fix: drop the plan tier to `effort: none`, cutting latency 27x with no quality loss.
- Guardrail and think steps ran 10 to 15 seconds per stub classification, generating a full unused answer every call - the constraint was a bare user question sent to a real model with no system instruction, not slow inference. Fix: give each stub a one-word system instruction and cap `max_tokens` at 128.
- A CURIE lookup against the live graph took 42 seconds - the constraint was the query planner's row-count estimate under a small LIMIT clause, not connection latency. Fix: `SET enable_seqscan = off`, cutting 42034ms to 108ms.
