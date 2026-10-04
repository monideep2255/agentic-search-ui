---
description: "For skills or agent runs producing substantial output, grade with a second agent that has fresh context against pass/fail criteria. The agent that produced the output never signs off on it."
scope: portable
alwaysApply: false
paths: ["tracker/phase_*.md", ".claude/skills/bossman-mode/**/*", ".claude/agents/**/*", "testing/Developer/reports/**/*"]
---

## Self-eval loop

The maker never signs off its own substantial output. A second agent with fresh context grades it against a numbered pass or fail checklist, and receives only the output and the checklist.

- The scripted checker always runs and owns accept or reject.
- An unscripted adversary joins when the output is runnable and a plausible wrong answer is worse than a crash, as with this search agent's cite-or-refuse gate.
- A finding goes to the shared ledger the moment it is established. The finder never closes its own finding.
- A fix is reviewed harder than new code.

Full text: `.claude/rules-reference/self-eval-loop.md`.

The test: did my substantial output get graded by a fresh-context agent, or did I only self-review in the same context?
