---
description: "Always identify and attack the bottleneck before optimizing anything else."
scope: portable
alwaysApply: false
paths: ["tracker/phase_*.md", "testing/Future.md", "requirements/Plan.md", "src/system_03_search_agent/harness/**/*"]
---

## Attack the constraint

Before optimizing, automating or adding to anything, ask what the bottleneck is right now: time, skill, clarity, access or tooling. Optimizing a non-bottleneck is wasted effort.

- When the constraint is process overhead, run the five steps in order: make requirements less dumb, delete, simplify, accelerate, automate.
- When a model's output is wrong, read its input first. Print the exact prompt, schema or context it received, and check the right answer was even expressible from it. Build phase 2.1 spent five review rounds hardening a binder while the schema slice it was given had no Disease label.
- Not when the constraint is external, or mid-way through a clear plan.

Full text, with the idiot index check and three measured examples: `.claude/rules-reference/attack-the-constraint.md`.
