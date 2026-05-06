---
description: "Always identify and attack the bottleneck before optimizing anything else."
scope: portable
alwaysApply: true
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
- Starting a work block - of the options in my cluster (Build/Learn/Practice), which one attacks the constraint?

**Do NOT apply when:**
- The constraint is external and you can't act on it (waiting on someone else)
- You're in execution mode on a clear plan - don't re-question the plan mid-sprint
- Recovery/rest days - not everything needs to be optimized

**Idiot index check:**
When something feels expensive (in time, effort, or friction), break it into components. How much of the cost is the actual work vs overhead, process, or indecision? A high ratio of overhead to actual work means the constraint is the process, not the task.

**The Algorithm (when the constraint is process overhead):**

Once you've identified the bottleneck as process, run these 5 steps in order. The order matters - don't skip ahead.

1. **Make requirements less dumb** - question every requirement. Who asked for this? Are they still right? Ownerless requirements are suspect by default.
2. **Delete** - remove whole steps, parts, or processes entirely. If you never have to add something back ~10% of the time, you're not deleting aggressively enough.
3. **Simplify** - only after deletion. Otherwise you're polishing things that shouldn't exist.
4. **Accelerate** - speed up cycle times only once you're building the right, simplified thing. "If you're digging your grave, don't dig it faster."
5. **Automate** - last, not first. Automating a broken process just produces fast wrongness.

**Examples:**
- 6 FTP sources, 278M edges, 1 OOM crash - the constraint is memory during export, not download speed. Fix: add append_edges() streaming before optimizing anything else.
- Gene pipeline OOM during export - the constraint isn't parsing speed, it's memory. Fix: stream edges to disk instead of accumulating in a list.
- Gate 1 has three pipelines to validate - the constraint is the Gene parser (largest dataset), not MedGen (smallest). Fix: run MedGen first to validate the flow, then tackle Gene.
