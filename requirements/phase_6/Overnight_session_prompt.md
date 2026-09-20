# Overnight session prompt

Paste the block below into a fresh session to continue or restart the unattended run of 2026-09-19. It is written to be sufficient on its own. Written 2026-09-19 by the session that started the run.

## The prompt

You are the main agent (Opus) on `agentic-search-ui`, branch `develop`, working the UI fix loop unattended overnight. The product owner is asleep and will read your report in the morning. Do not ask questions: decide, record the decision, and keep moving.

Read first, in this order:

- `CLAUDE.md` and every file under `.claude/rules/`.
- `testing/UI_fix_plan.md`, section "Where we stopped", which owns the cutoff, then its Set 11 table.
- `requirements/phase_6/Continuation_prompt.md`, Step 2.
- The newest reports under `testing/Developer/reports/2026-09-19_verification/` and `2026-09-14_*`.

### Goal contract

Done when: every item in "Tonight's list" below is either live on `develop` and verified live, or stopped with a written reason naming what blocked it. No item is left in an unknown state.

Verify surface, immutable: a change ships only after its own tests pass, `ruff check` (whole repository) and `isort --check-only src tests` exit 0, a frontend change also passes `npm run build`, `python3 tracker/check_doc_drift.py --check` exits 0 before any push, the push reaches `origin/develop` with matching hashes, both Railway develop services report SUCCESS, and a live check on the deployed app answers. You may add checks. You may never weaken, narrow or skip one to make an item pass.

Output: the morning report is the "Where we stopped" section of `testing/UI_fix_plan.md`, rewritten in place, plus per-item rows in the Set 11 table and a report per piece of work under `testing/Developer/reports/2026-09-19_*`.

Constraints: work directly on `develop`, no branch and no pull request, per the UI fix loop. Conventional Commit subjects. Never add a Co-Authored-By line. Never release to production. Never edit the two locked requirements documents. Never weaken cite-or-refuse or the grounding gate. Keep the stable prefix byte-identical and prove it. Stage files by name, never `git add -A`.

Blocked-stop, any one of these ends that item and starts the next: a review round finds a defect inside the previous round's fix, the same check fails twice for different reasons, a live check fails after a push (revert that push first), or an item needs a decision reserved for the product owner.

### Tonight's list, in order

1. Make CI green on `develop`. The Python gates job has failed on the last four pushes. Diagnose from `gh run view <id> --log-failed`, fix the cause, push, and confirm the run goes green. Do not disable or narrow a gate to achieve this.
2. Land UI fix 11.27 (less bold) and 11.28 (paced transition) from the worktree `.claude/worktrees/agent-a8393711bb57d579b`. The inventory is in `testing/Developer/reports/2026-09-19_verification/bold_and_stagger_state.md`. Merge, push, then check live at 1280 and 390 that only the question title and the lead's main point are bold, and that a run visibly steps through the lead starting, the handoff, each helper landing, the writing banner, then sentences.
3. Land the broad search wiring, UI fix 11.17 and 11.21, from its worktree. Its contract is in `testing/Developer/reports/2026-09-14_breadth_tool_layer/review.md` under "For the graph.py wiring". After the push, prove live that a BRCA1 answer and an HNF1A answer now cite PubMed, ClinVar, OMIM, the gene summary and GO terms beside the graph rows, and that the same question returns the same number and set of sources across three runs.
4. Keep the failure instrumentation in place and report the live failure rate with any captured error payload, using `testing/Developer/reports/2026-09-19_verification/measure_with_errors.py`. On 2026-09-19 it measured 15 of 15 answered with no error captured.
5. Refresh the documents: `testing/UI_fix_plan.md` (Set 11 rows and the cutoff), `DECISIONS.md` for every decision you take, and `requirements/phase_6/Continuation_prompt.md` Step 2.

Already done, do not redo: the E-utilities rate is 10 per second on develop through the code default, with no environment variable set.

### How to work

Follow `.claude/rules/plan-then-fan-out.md`. Scout first, decompose into non-overlapping tasks, and never let two workers write the same file. You keep the planning, the merging, the pushing and the final judgement.

| Work | Model |
|---|---|
| Planning, merging, verification, synthesis | Opus, you |
| Retrieval, grounding, agent-loop and `core/graph.py` work | Fable |
| Bounded UI work with browser tests, and measurement | Sonnet |
| Mechanical edits, counts, formatting | Haiku |

Give every worker a goal contract with a done-when, a named output path and a blocked-stop. Workers report and never commit; you verify and commit. A stopped worker is not woken by its own background job, so tell each one to poll its own jobs, and resume any worker that hands back early. Write a finding to a file the moment it is established, never only in context.

### Never decide these, park and report them

- The 20-source citation cap, which is why HNF1A shows 5 variant rows against the reference prototype's 13.
- The provenance note under the mapping table.
- Whether the mode toggle moves into the status strip, and whether switching re-runs the question.
- The trust-line wording, currently "Based on N sources, not yet confirmed".
- Any release to production.
- Shipping abstracts as evidence, UI fix 11.22. Two review rounds showed a sentence rule quotes claims the next sentence refutes. Design it and stop.

### State at handover, 2026-09-19, 00:15 local

Measured just before this file was written, so the new session starts from fact rather than memory.

| Thing | State |
|---|---|
| `develop`, local and remote | Both at `ba38cc9`, nothing ahead, nothing behind |
| Railway develop, web and API | Both SUCCESS on `ba38cc9`. `GET /health` returns `app_env: develop` |
| Live reliability | 15 of 15 searches answered on 2026-09-19, versus 5 failures in 53 on 2026-09-14. No error event occurred, so no cause is captured yet |
| Answers | Verified directly: a BRCA1 researcher answer carries 5 claims, 5 headings, 6 list items, a 5-row table and 11 citations, in 7.5 seconds |
| CI | Red on `ba38cc9`, Python gates job. The cause is NOT yet diagnosed: the worker was stopped before it reported, and `python_gates.md` was never written. Start here |
| 11.27 and 11.28 worktree | `.claude/worktrees/agent-a8393711bb57d579b`, branch `worktree-agent-a8393711bb57d579b`, based on `e5947e0`, uncommitted. Inventory: 473 of 474 unit tests pass, tsc and build clean, no conflict with develop. A worker was mid-fix on the one failing test, `src/phase49Premise.test.tsx`, when it was stopped, so re-check that file's state before trusting it |
| Broad search wiring | Not started. Its worker was stopped while still reading, and its empty worktree was cleaned up. Nothing is lost |
| Reports written tonight | `testing/Developer/reports/2026-09-19_verification/`: `live_check.md` (with a correction section), `bold_and_stagger_state.md`, `measure_with_errors.py`, `run_detail.json` |
| Untracked and deliberate | Set 10's `2026-09-12_consistency_baseline/`, an empty `writetest.txt`, and tonight's verification folder |

One correction worth carrying forward, because it wasted time tonight: `trust_outcome: "ask"` is the trust tier, rendered as "Based on N sources, not yet confirmed". It does NOT mean the answer is a clarifying question. A worker read it that way and filed a false finding.
