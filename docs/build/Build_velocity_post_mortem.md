# Build velocity post-mortem: why one phase now takes a whole day

Answers one question: why has the build slowed down, is that slowdown real work or ceremony, and is autonomous execution ("auto mode") the cause. Measured from git history, the tracker files, LEARNINGS.md, and the harness's own file sizes, not from memory or impression.

## Table of contents

- [The measured answer](#the-measured-answer)
- [Is the reference repo a fair comparison](#is-the-reference-repo-a-fair-comparison)
- [This repo's own velocity, phase by phase](#this-repos-own-velocity-phase-by-phase)
- [Where 2026-08-03 actually went](#where-2026-08-03-actually-went)
- [The harness's own overhead](#the-harnesss-own-overhead)
- [Idiot index: work versus overhead](#idiot-index-work-versus-overhead)
- [Is auto mode the cause](#is-auto-mode-the-cause)
- [The algorithm, applied honestly](#the-algorithm-applied-honestly)
- [What to change](#what-to-change)
- [Correction, 2026-08-04: the pre-flight check covers one transport, not two](#correction-2026-08-04-the-pre-flight-check-covers-one-transport-not-two)
- [What could not be measured](#what-could-not-be-measured)

## The measured answer

Three things are happening at once, and they are not the same thing:

- Four phases (1.0, 1.1, 1.2, 2.0) shipped in under two calendar days (2026-07-27 08:51 to 2026-07-28 22:24), each with real production code, tests, and a judge and adversary pass. Auto mode was running the whole time. It was fast.
- Build phase 2.1 took four calendar days (2026-07-29 to 2026-08-01) because a single composition defect survived four consecutive reviews behind a green 879-test suite, and needed a fifth round to find. This is documented exhaustively in LEARNINGS.md's own retrospective and is the single biggest time sink measured in this repo's history.
- Build phase 2.2 ran one session of about 6.7 hours on 2026-08-03 (11:44 to 18:27) and paused, not because of process bloat but because three network outages killed two premise-gate runs and three review agents (an estimated 1 to 1.5 hours of dead dispatches), layered on top of a review round that found two critical defects: a negation grounding as support for the claim it denies, and a fabrication (an invented treatment-discontinuation instruction) shipping uncited by exploiting a prefix-only exemption check.

The reference repo's "weekend" claim is true for what a weekend actually bought: a five-day, single-orchestrator, zero-review MVP. It is not comparable to what build phases 2.1 and 2.2 are building, a system with an adversarial review gate whose job is to catch the exact class of failure ("confident wrong answer, fully cited") that a weekend prototype has no mechanism to catch at all. Full comparison below.

Auto mode is not the primary cause of the slowdown. It is a real cost multiplier for how the review cost shows up: a phase that needs five review rounds pays for five separate agent dispatches, each re-loading the harness's roughly 150KB of always-on context, rather than one continuous human reviewer's attention. That multiplication is real and worth reducing. It is not the same claim as "autonomous execution is slow," which the four two-day phases directly disprove.

## Is the reference repo a fair comparison

Read from `reference/ncbi_ai_agents-ncbi-kg`, a read-only symlink resolving to `/Users/anuradhachakraborti/Desktop/Tech Skills/ncbi_ai_agents`.

| Metric | Reference repo | This repo (System 3, since 2026-05-05) |
|--------|----------------|------------------------------------------|
| Total commits | 557, spanning 2025-07-10 to 2026-04-07 (9 months) | 267 |
| Code files (py/js/ts/tsx/jsx, excluding venv/node_modules) | 142 | separate counts below |
| Total lines across those files | 30,262 | separate counts below |
| Test lines | 3,873 | 17,326 (src tests) |
| Review process | None found in git history: no judge, no adversary, no premise gate | Judge, adversary, mutation pass, premise gate, all with cited evidence |
| Citation or grounding gate | None found | Deterministic cite-or-refuse, the subject of build phase 2.2 |

The "weekend" claim holds for a specific, narrower thing than the whole reference repo. Its first commit is 2025-07-10. By 2025-07-15, five days later, the commit messages read "Phase 3 MVP Complete: Streamlit UI + LangSmith Observability", with a PMC API wrapper, a ClinVar wrapper, NCBI Datasets integration, and single-shot OpenAI GPT-4o orchestration already built. That is the weekend-scale prototype the product owner remembers, and the memory is accurate.

What is not comparable:

- The 557-commit, 9-month history is everything built AFTER that five-day MVP: a Neo4j to AGE migration, a KGX export pipeline, BioLink validation, a force-graph frontend, an MCP server package, and roughly a dozen skills. That is a different, much larger project than "one phase."
- No commit in the reference repo's history shows a judge pass, an adversary pass, a premise gate, or a citation-grounding gate. Its README and CHANGELOG (338 and 212 lines) document features shipped, not defects a review process caught before shipping.
- This repo's build phase 2.2 is not "add a feature." It is the deterministic half of a cite-or-refuse gate, the mechanism this repo's own `production-standards.md` calls "the single highest-leverage correctness gate for a biomedical search system, where a confident wrong answer is worse than no answer." The reference repo has no equivalent deliverable to time against.

Fair reading: the reference repo proves a single developer, working alone with no adversarial review, can ship a demo-quality prototype in a weekend. It says nothing about how long the same developer would need to also catch a negation grounding as medical support, or a fabricated drug-discontinuation instruction, before shipping. Nothing in its history shows that check ever running.

## This repo's own velocity, phase by phase

Commit timestamps read directly from `git log`, not estimated.

| Phase | Calendar span | Session window | Commits | Outcome |
|-------|---------------|-----------------|---------|---------|
| 1.0 (FastAPI skeleton) | 2026-07-27 | 11:25 to 14:26 (about 3 hours) | 31 that day, phase-scoped subset smaller | Merged same day, PR #5 |
| 1.1, 1.2, 2.0 (auth, React shell, LangGraph loop) | 2026-07-28 | 08:51 to 22:24 (about 13.5 hours) | 92 that day | Three phases merged, PRs #12 and prior |
| 2.1 (cypher_query) | 2026-07-29 to 2026-08-01 (4 calendar days, one gap day 07-30) | 11:10 (07-29) to 21:22 (08-01) | 23 + 27 + 14 = 64 | Merged PR #15, after 5 review rounds |
| 2.2 (write-step grounding) | 2026-08-03, single day, still open | 11:44 to 18:27 (about 6.7 hours) | 8 | Paused, not merged, per the product owner's own call |

The pattern is not a steady slowdown. Four phases moved fast (1.0 to 2.0). One phase (2.1) was expensive for a specific, documented reason. One phase (2.2) is mid-flight and was cut short mostly by infrastructure, not process.

Code volume for build phase 2.2, from `git diff --stat main phase/2.2-write-step-grounding`:

| Category | Lines | Share |
|----------|-------|-------|
| Production source (`contracts/events.py`, `core/graph.py`, `synthesis/*.py`) | 1,962 | 49% |
| Tests (`tests/system_03_search_agent/...`) | 1,676 | 42% |
| Docs and tracker (`DECISIONS.md`, `LEARNINGS.md`, `tracker/phase_2.2.md`, board render) | 412 | 10% |
| Total | 3,997 lines inserted, 53 deleted | |

That ratio, roughly half production code and four-tenths tests, with a tenth spent on the append-only record of what happened, is not a bloated ratio by itself. It is close to what a team with real test coverage and a paper trail would produce for the same feature. The cost this document investigates is not line volume. It is wall-clock time spent on multi-round review and rework, which the line count above does not show at all.

## Where 2026-08-03 actually went

Attributed from `tracker/phase_2.2.md`'s own findings (F-2.2-01 through F-2.2-07), its "Review round" section, and the product owner's stated network figures.

| Bucket | Evidence | Estimate |
|--------|----------|----------|
| Writing production code (7 tickets: findings list, grounding pass, trust signal, refuse path, contract fields, Write-step rewiring) | `git diff --stat`, 1,962 production lines | Majority of the session |
| Writing tests (20 required-path tests, a 10-question premise gate, prompt-cache byte-equality test) | 1,676 test lines, `tests/.../test_write_grounding_premise.py` at 873 lines alone | Roughly a third of the session |
| Review rounds (judge, adversary, mutation pass, independent fix re-review) | "Review round on 2026-08-03" section, tracker/phase_2.2.md: 4 separate passes, 2 critical findings from judge and adversary independently, mutation pass found the new gates had zero tests at first | 1 to 2 hours across the 4 dispatches, per the 15-25 minute per-agent figure the product owner supplied |
| Rework from review findings | F-2.2's two critical fixes: inverting an infinite blocklist to a finite allowlist for content-bearing words, and replacing a weak two-hop assertion (J-05) that had silently dropped anchor verification | Meaningful, not cosmetic: both fixes changed the shape of a checking function, not a string |
| Environmental loss | Product owner's own figures: 3 network outages, 2 premise-gate runs killed (6-10 min each) and 3 review agents killed (15-25 min each) | Roughly 57 to 95 minutes, call it 1 to 1.5 hours |
| Process overhead (tracker file, DECISIONS.md, LEARNINGS.md, commit messages) | 412 lines across `tracker/phase_2.2.md`, `DECISIONS.md`, `LEARNINGS.md` | Small: this is text a lead writes in minutes per entry, not an hours-long activity |

Two things stand out against the product owner's "auto mode" hypothesis:

- The two critical defects the review round found were not process noise. F-2.2-A-02/J-02 is the finding that produced an invented drug-discontinuation instruction shipping without a citation, the exact example named in this investigation's brief. Catching it before it reached a user is the review process's entire purpose, and here it worked.
- Environmental loss (1 to 1.5 hours) is a larger, more addressable chunk of the day than the process paperwork (well under an hour to produce 412 lines of record-keeping). If the goal is to get a day back, the network is a bigger lever than trimming the tracker.

## The harness's own overhead

`.claude/rules/` and `CLAUDE.md` load on every single turn, per this repo's own architecture. Measured directly, not estimated:

| Item | Count | Bytes |
|------|-------|-------|
| Rule files (`.claude/rules/*.md`) | 22 | 134,463 |
| `CLAUDE.md` | 1 | 16,201 |
| Combined, loaded every turn | | 150,664 (roughly 37,700 tokens at 4 bytes/token) |
| Skills (`.claude/skills/`) | 15 | not measured, loaded on demand rather than every turn |
| Hooks (`.claude/hooks/*.sh`) | 9 (7 scripts, `lib/`, plus `session-start.sh`) | not measured |

This confirms the 2026-08-02 DECISIONS.md entry exactly: the figure was 132,181 bytes before a consolidation pass and 134,463 bytes after, across 22 files instead of 28. The consolidation moved content between files. It did not shrink the always-loaded total, and that was recorded plainly as a measured negative result at the time, not discovered fresh here.

This is a real, standing cost, but it is a cost per model call (context tax, paid in tokens and dollars), not the dominant driver of the wall-clock "whole day" complaint. Processing 150KB of stable, cache-eligible prefix text takes seconds, not the tens of minutes a review agent or a network-dropped dispatch costs. Where it does compound: every fresh agent dispatch (a new judge, a new adversary, a new builder) pays this cost again on its first call, since a fresh session has no warm cache. A phase needing many separate dispatches, as 2.1's five review rounds did, pays this tax five or more times over. That is a second, smaller instance of the same multi-agent multiplication effect described in the answer above, not a new cause.

`docs/build/Build_workflow_cadence.md`'s own 12-stage table is the other standing structural cost. Two things in it are directly relevant here:

- The cadence already dropped reasoning effort from `high` to `medium` for most roles on 2026-08-02, the day before build phase 2.2 opened, on measured evidence: 76 percent fewer output tokens at the same completion rate externally, and an internal 27x latency multiple (163.0 seconds versus 6.1 seconds) for one bounded Cypher-generation call with no quality loss. Judge, adversary, decomposition, and the premise gate stayed at `depth`/`high` deliberately, because this repo has direct evidence (build phase 2.1) that weakening review costs whole rounds, not just latency.
- `release-workflow` is stated as "mandatory, no skips" at every phase end. Measured dispatch count across the five completed phases: 0 of 5. This is a real, ongoing drift between what the process document says and what actually runs, independent of network outages or review depth, and it is addressed under "What to change" below.

## Idiot index: work versus overhead

Applying `.claude/rules/attack-the-constraint.md`'s idiot-index check to build phase 2.2's single day:

| Component | Share of the day | Judgment |
|-----------|-------------------|----------|
| Writing production code and tests (the actual work) | Majority, roughly half the session by line volume | Necessary. Not the constraint |
| Review rounds that found real, ship-blocking defects | 1 to 2 hours | Expensive, but the two defects it caught (negation-as-support, uncited fabrication) are exactly what a citation-grounding system exists to prevent. High ratio of cost to work here is buying something real |
| Rework from those findings | Folded into the code totals above | Not separable from "the actual work" in this phase, since the fixes changed real logic, not typos |
| Environmental loss (network outages) | 1 to 1.5 hours | Pure overhead. Zero value produced. The single largest wasteful bucket measured for 2026-08-03 |
| Process paperwork (tracker, DECISIONS.md, LEARNINGS.md) | Well under an hour | Small in absolute terms. Not the constraint, despite being the most visible "ceremony" |

The idiot-index verdict: the constraint on 2026-08-03 was not process ceremony (paperwork is a small fraction of the day) and was not the review depth (it earned its cost, measurably, twice in one day). The largest addressable waste was infrastructure: a machine whose DNS or network dropped three times mid-session, killing agent dispatches that then had to restart from zero rather than resume.

Separately, and structurally rather than for this one day: `release-workflow`, marked mandatory in the bossman-mode rule, has a 0-of-5 real dispatch rate. An ownerless-in-practice requirement, carried forward unquestioned, is exactly the smell `attack-the-constraint`'s step 1 exists to catch.

## Is auto mode the cause

Direct answer: no, not as stated, but there is a real mechanism buried inside the hypothesis worth pulling out separately.

Evidence against "auto mode causes slowness":

- The same autonomous, judge-and-adversary-reviewed harness shipped four phases (1.0, 1.1, 1.2, 2.0) in under two calendar days. If autonomy itself were the drag, the fast phases and the slow ones would not differ this sharply while running the identical process.
- What actually differed between the fast phases and build phase 2.1 was not autonomy, it was whether a real defect existed to find. LEARNINGS.md's own retrospective is explicit: "Neither component was wrong... The defect was in the composition, and nothing in the process looked there." A human reviewer working alone, without a judge, an adversary, and a premise gate, has no demonstrated mechanism in either repo's history for finding a composition defect like that faster. The reference repo's weekend prototype has no review step at all, so it could not have found the ortholog bug or the tamoxifen fabrication either; it would have shipped them.

Evidence for a narrower, real version of the hypothesis:

- Multi-agent dispatch does multiply cost when many review rounds are needed. Each of build phase 2.1's five rounds, and each of build phase 2.2's four passes, is a separate agent dispatch that re-pays the roughly 150KB context load and restarts its own 15-25 minute clock. A single continuous human reviewer would not re-pay a context-load tax between passes. Five rounds of that tax is a real, auto-mode-specific cost that a solo human review process does not incur in the same way, even though the human process would likely be slower overall for other reasons (no adversarial fresh-context grading, no cited-evidence discipline).
- The same multiplication applies to environmental failure: a network drop kills one agent's in-flight work and the dispatch restarts from zero, again paying the context tax. A human whose connection drops mid-review does not lose their own train of thought the way a stateless agent dispatch does.

So: auto mode is not the cause of the slowdown, but it is the reason the cost of finding a real defect, or of a flaky network, shows up as several discrete, expensive, from-scratch dispatches rather than one continuous session. That is a genuine, addressable design property of the current cadence, not evidence that autonomy itself is slower than the alternative.

## The algorithm, applied honestly

Per `.claude/rules/attack-the-constraint.md`, run in order, not skipped to automation.

### 1. Make requirements less dumb

- `release-workflow` to `ship` as "mandatory, no skips" at every phase end: 0 of 5 real dispatches. Ownerless in the sense that nothing has enforced it and nothing has visibly suffered from its absence yet. Suspect by this rule's own standard. Either the requirement is right and needs actual enforcement, or the requirement is wrong and should say what the practice already is.
- The premise gate as a blocking stage before any tool-phase code: directly measured value (caught two regressions before a reviewer did on build phase 2.1, cost $0.013 and 40 minutes to build). Not ownerless. Keep without question.
- Judge and adversary at `depth`/`high effort`: directly measured value twice over (build phase 2.1's composition defect, build phase 2.2's negation-grounding and fabrication findings). Not ownerless. Keep.
- A separate mutation-testing pass, on top of judge, adversary, and the premise gate: it caught something real on 2026-08-03 (the new gates had zero tests behind them at first), a distinct failure class from what judge and adversary check. Worth asking whether "does every new check have a test that can kill a mutant" could instead be one line item on the judge's own checklist rather than a fully separate agent dispatch, since the finding is checklist-shaped, not adversarial-reasoning-shaped.

### 2. Delete

- Already done, cited as precedent: `CHANGELOG.md` was deleted outright on 2026-08-02 rather than backfilled, and the Sub-planner and Integrator roles were removed from the cadence after zero dispatches across five phases. This repo already deletes when the evidence supports it.
- Candidate for this pass: fold the mutation-testing pass into the judge's stage-8 checklist rather than running it as stage 10's own dispatch. If judge dispatches already run at `depth`/`high effort` and already read the diff, adding one explicit instruction ("does every new validation function have a test that fails if the check is removed") likely catches the same gap without a fifth agent dispatch.
- Not a candidate for deletion: the premise gate, the judge, or the adversary. All three earned their cost with a specific, cited catch in the last week alone.

### 3. Simplify

- The premise-gate-versus-network-outage confusion cost real time twice on 2026-08-03 before the tracker file wrote down the diagnostic (`curl` against the model provider, `nc -z` against the graph tunnel). That diagnostic already exists in `tracker/phase_2.2.md`'s "Resume here" section. Promoting it from a paragraph in a paused-phase file to a one-line pre-flight check run automatically before any premise-gate or review-agent dispatch would simplify the failure mode from "a defect until proven otherwise" to "a known, fast, first check."

### 4. Accelerate

- Already executed: the 2026-08-02 reasoning-effort drop from `high` to `medium` for most roles, keeping `depth`/`high` only for judge, adversary, decomposition, and the premise gate. Measured externally at 76 percent fewer output tokens for the same completion rate, and internally at a 27x latency multiple with no quality loss on one bounded task. This already happened, one day before the phase this document investigates, and nothing in 2026-08-03's slowdown traces back to it; the slowdown that day was network and genuine findings, not reasoning-effort waste.
- Remaining acceleration target: the network itself. A pre-flight health check (the `curl`/`nc` commands already written down in the tracker file) run automatically before dispatching a premise-gate or review agent would turn a 15-25 minute dead dispatch into a near-instant "not ready, retry" and recover most of the 1 to 1.5 hours lost on 2026-08-03.

### 5. Automate

- The one clean automation candidate, reached only after the four steps above: a pre-flight script that runs the two health checks already named in `tracker/phase_2.2.md` before any premise-gate run or review-agent dispatch, and blocks the dispatch with a clear message rather than letting it burn its full 15-25 minute budget against a dead connection. This is a guard script, not a new agent, and it does not touch the review process itself.
- Automating anything else now, before steps 1 through 4 are actually acted on, would be automating a process not yet confirmed right, which `attack-the-constraint` explicitly warns against.

## What to change

Prioritized, in the order this investigation found them, delete first:

| Priority | Action | Why |
|----------|--------|-----|
| 1 | Add a pre-flight health check before dispatching any premise-gate run or review agent, with ONE PROBE PER TRANSPORT. See the correction below: the commands in `tracker/phase_2.2.md`'s "Resume here" section cover premise-gate runs only and do not cover agent dispatch at all | Recovers the single largest measured waste on 2026-08-03 (1 to 1.5 hours), and prevents the same diagnostic confusion (outage read as defect) from costing time a third time |
| 2 | Resolve the `release-workflow`/`ship` "mandatory, no skips" gap: either actually run it at every phase end, or rewrite the rule to state the real, chosen practice | 0 of 5 real dispatches against a rule that says mandatory is an ownerless requirement by this repo's own `attack-the-constraint` standard, and it is a live contradiction sitting in `bossman-mode.md` right now |
| 3 | Fold the mutation-testing pass into the judge's stage-8 checklist as an explicit line item, rather than a separate stage-10 dispatch | Same catch (does every new check have a test that can kill a mutant), one fewer agent dispatch and one fewer context-reload tax per phase with a review round |
| 4 | Keep the judge, adversary, and premise gate exactly as they are, at `depth`/`high effort` | Twice measured this week alone to catch a defect that would otherwise have shipped as a confident, fully cited, wrong or dangerous answer: 25 non-human orthologs for a disease question (2.1), and an uncited invented drug-discontinuation instruction (2.2). This is the highest-value spend in the entire cadence and should not be the target of any future cost-cutting pass |
| 5 | Leave the 2026-08-02 reasoning-effort tiering as is | Already measured and already correct; nothing in 2026-08-03's slowdown traces back to it |
| 6 | Do not shrink `.claude/rules/` further as a velocity fix | It is a real per-call token cost (134,463 bytes, confirmed unchanged by the prior consolidation attempt), but it is a dollar-cost lever, not a wall-clock lever. The 2026-08-03 slowdown was network and genuine review findings, not context size |

## Correction, 2026-08-04: the pre-flight check covers one transport, not two

Recommendation 1 above was acted on at the start of build phase 3.0 and did not work, for a reason worth recording rather than quietly fixing.

The check named in `tracker/phase_2.2.md` and repeated in `requirements/phase_6/Continuation_prompt.md` is:

```bash
curl -s -o /dev/null -w "%{http_code}" --max-time 15 https://openrouter.ai/api/v1/models
```

That command was run at phase open and returned 200. Two researcher agents were dispatched on that evidence, and both died without producing any output: one closed its connection mid-response, the other stalled for 600 seconds.

The check is not wrong, it is scoped to the wrong half of the recommendation. There are two independent transports in play and the recommendation's own wording ("before dispatching any gate run or review agent") spans both:

| What is being dispatched | Which provider it reaches | Covered by the curl check |
|--------------------------|---------------------------|---------------------------|
| A premise-gate run, or any test that calls `harness.call_tier` | OpenRouter, the product's model provider | Yes |
| A review agent, a builder, a researcher, any subagent | The build harness's own provider, a different endpoint | No |

So a green pre-flight predicts nothing about whether an agent dispatch will survive, and the more expensive of the two failure modes is the uncovered one. A dead premise-gate run costs 6 to 10 minutes; a dead review agent costs 15 to 25.

What this changes:

- A correct pre-flight needs one probe per transport, not one probe. The OpenRouter probe stays as is and covers gate runs. Agent dispatch needs its own probe against the harness provider, and no such probe is written down anywhere in this repo yet.
- Until that second probe exists, treat a dead dispatch as an expected outcome rather than a signal about the work. Retry once, and if it dies again, do the work inline.

The second, cheaper lesson from the same incident: the delegated task was two file reads and a documentation grep. Doing it inline after both dispatches died cost less than either dispatch had already burned. `docs/build/Build_workflow_cadence.md` already says "each dispatched agent should carry a task worth its overhead", and that line was written about builders. It applies to researchers too, and the overhead it refers to includes the failure rate, not just the setup cost.

## What could not be measured

Stated plainly rather than glossed over:

- Exact wall-clock hours worked per phase. Git commit timestamps give a session window (first commit to last commit each day), not actual continuous working time, breaks, or overlap with other work.
- Exact dollar cost per phase or per agent dispatch. No LiteLLM billing log was available to this investigation; the $0.013-per-run premise-gate figure and the 100k-175k-token full-security-scan figure are both prior measurements cited from `docs/build/Build_workflow_cadence.md` and `DECISIONS.md`, not re-measured here.
- Exact token counts for the 2026-08-03 review round's four dispatches. The 15-25 minute per-agent and 6-10 minute per-premise-gate-run figures were supplied as known facts for this investigation and are used as given, not independently re-timed.
- The reference repo's actual effort in hours during its five-day MVP window. Only commit dates and messages are available, not session logs, so "weekend" is confirmed as a commit-date pattern, not as a measured hour count.
- Whether folding mutation testing into the judge's checklist (change 3 above) actually saves a dispatch without losing coverage. This is a reasoned recommendation from the evidence available, not something tested by running it.
