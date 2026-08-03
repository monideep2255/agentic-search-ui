# Session July 26

Phase 5, system and tooling updates. Steps 5.1 to 5.4, opened and closed in one session on branch `phase/5.0-system-tooling-updates`.

## Table of contents

- [How the phase opened](#how-the-phase-opened)
- [The reframe that set the scope](#the-reframe-that-set-the-scope)
- [Step 5.1: the build harness](#step-51-the-build-harness)
- [Step 5.2: skills and rules](#step-52-skills-and-rules)
- [Step 5.3: root documents](#step-53-root-documents)
- [Step 5.4: reference documentation](#step-54-reference-documentation)
- [The software team vision](#the-software-team-vision)
- [The gitignore reversal](#the-gitignore-reversal)
- [What the verification found](#what-the-verification-found)
- [Carried forward](#carried-forward)

## How the phase opened

Phase 5's stated goal was to make every skill, agent, rule, and root document consistent with the locked PRD and technical specification. The document's own Step 5.2 floated four candidate skills: API development, React component, tool testing, and Cypher query development.

The opening move was to treat those four as speculative rather than as a to-do list. They were written in Phase 0, before the specification existed, each with a question mark, and Plan.md's own instruction two lines later is to create only what is needed.

## The reframe that set the scope

The product owner pushed back on the framing directly: if skills already exist, why add more, and should we not weave in what we have before building what is missing?

That reframed Step 5.2 from "which skills do we build" into a coverage question: which obligations does the locked specification impose, and which of them does something already enforce? Only an obligation with no owner can justify anything new.

The method that followed, applying `plan-then-fan-out` and `parallel-first` at the product owner's request:

- The reasoning model scouted the terrain, carved non-overlapping slices, and wrote each worker a contract with a done-when and an output path.
- Ten Sonnet workers ran in parallel, each reading one bounded slice and writing to its own file. Five covered the technical specification by section range, one the PRD, one the evaluation playbook, one inventoried all 25 rules and 13 skills with their triggers, one audited the root documents, and one surveyed the personal-os reference for reusable patterns.
- The reasoning model kept the synthesis and verified every worker claim before acting on it.

Deliberate design choice: the demand-side workers were given only the list of rule and skill names, never the rule files themselves. A worker that cannot read a rule cannot talk itself into believing the rule covers something it does not. Every proposed match was then verified against the actual rule text during synthesis, which is the maker-checker split applied to the analysis itself.

Result: 303 obligations extracted, 246 already owned, 57 unowned. The full map is in `requirements/phase_5/Coverage_map.md`.

Three findings shaped everything after:

1. The unowned 57 wanted rules and documentation, not skills. Rules load automatically every session; a skill must be remembered and invoked. Checking the ten-item cross-tool contract by hand showed seven of the ten already covered by `production-standards`, `ai-security-standards`, and `system-design-patterns`, so a tool-build skill would have been roughly 70 percent restatement.
2. The real defects were wiring, not absence. Skills that existed were never invoked at the moment they were needed.
3. One existing skill had drifted badly. `eval-harness` never referenced `Evaluation_playbook.md` and was missing 13 of its 17 demands, while being the gate that decides whether an answer-generation feature ships.

## Step 5.1: the build harness

`bossman-mode` had a live defect and several gaps against the locked specification.

The branch bug, and its cascade. The skill created branches named `feature/description`, contradicting `git-workflow.md`, the `bossman-mode` rule, and tech spec Section 25, all of which specify `phase/N.M-description`. `release-workflow` had the same bug. The cascade is the part that mattered: `ship/SKILL.md` only offers to create the MR when the branch matches `phase/*`, so a real bossman run would have created the wrong branch and then silently skipped the MR step.

Everything else changed in 5.1:

- Phase definitions now read from tech spec Section 25, the 26 numbered build phases, rather than from an unnamed "plan document".
- Dependency verification before a phase opens, so nothing builds on an unmerged dependency.
- Worktree isolation promoted from a post-collision fallback to the default for concurrent file-mutating builders, with read-only agents staying in the shared checkout and teardown at phase close.
- A product owner role, plus per-phase product-owner-required marking.
- A scope check against the v1 boundary, which matters most precisely when no human is watching.
- A Playwright gate for UI phases, on the reasoning that an agent can verify a button exists but cannot verify the result is good.
- The phase-end chain grew from two skills to six: `verify`, `eval-harness`, `dev-standards`, `release-workflow`, `ship`, `task-tracker`.

## Step 5.2: skills and rules

Two new skills, both for the build process rather than the product:

- `task-tracker`: the in-repo board at `tracker/BOARD.md` plus `tracker/phase_N.M.md`. The useful discovery was that bossman-mode already specified the ledger state machine in prose (single writer per state, mandatory reason on judgment states, append-only history, the raiser never closes) and had no file to write it to. Giving it one was most of the work.
- `learnings`: `LEARNINGS.md`, written at the moment of failure and read before every phase opens. Adopted from the personal-os per-skill `memory.md` pattern. The portable part is not the table format, it is the read-first discipline, which is what separates a log nobody opens from a system that stops repeating mistakes.

Rewritten: `eval-harness`, now carrying the playbook's 8-point rubric, the 13-of-16 threshold, the three hard-fails, the coverage metric, the moat test, the seven must-pass questions, model selection, and the five-stage feedback loop, with an explicit convention about what to inline versus what to reference so it cannot drift the same way again.

Rules: added `tool-call-budgets` and `v1-scope-boundary`, adopted and adapted `prompt-cache-discipline` from personal-os, extended `production-standards` and `system-design-patterns`, and narrowed `dependency-tracking` to hooks only.

Zero of the four originally floated skills were built.

## Step 5.3: root documents

19 stale statements corrected across CLAUDE.md, README.md, and Plan.md. The worst were in README.md, which claimed a build phase was in progress when no application code exists, and stated `.claude/` was git-tracked a day after it was untracked.

Also fixed: the pull request template still gated on BioLink and KGX validation inherited from the System 1 and 2 template repo, and three slash commands documented in CLAUDE.md (`/bossman`, `/release`, `/socratic`) did not match their skills' actual names and would not have resolved.

## Step 5.4: reference documentation

`docs/ncbi/Tool_implementation_mechanics.md`, 19 per-tool API traps drawn from tech spec Section 6. Six were identified during the coverage map; the worker found 13 more reading the section in full. The document holds API facts; the rules hold policy, and the file says so explicitly so the boundary survives future edits.

## The software team vision

The product owner described the target operating model: bossman mode running like a software development team. A lead engineer decomposes with the team, tasks are tracked Linear or Jira style with breakdown steps and acceptance criteria, phases complete and get reviewed, and the product owner is called at inspection points or phase end. Branches or worktrees, PRs reviewed then merged. The product owner coordinates only with the lead engineer, who has full authority over execution method.

This opened a second demand surface. The coverage map answered "what does the product specification need", and the answer was no new skills. The team operating model is a different question, and that surface was genuinely empty. Both `task-tracker` and `learnings` come from it.

Overnight autonomous runs were discussed and deferred. The product owner asked directly whether stacking merge requests delays development, which exposed sloppy framing in the original recommendation. The correction: stacking does not delay the build, because a dependent phase branches off the previous branch and starts immediately. What waits is the merge, and the merge is not on the critical path. The deeper point is that merging overnight buys no throughput at all for dependent phases, since phase 2.1 needs phase 2.0's code whether that code sits on main or on a branch, so full autonomy would only remove the review gate rather than accelerate anything. The better model, which Section 25's dependency graph already supports, is to fan out where phases are independent and stack only where the graph forces it.

The product owner also specified being needed for UI phases, with Playwright installed for verification. Playwright is scheduled for Phase 6, must clear the `supply-chain-security` checks before it lands, and becomes a hard gate rather than an available tool.

## The gitignore reversal

A verification detail turned into a decision. Six workers each reported `git status --short` as empty after writing files, which initially read as silent write failures. The cause was that `.claude/` had been gitignored the previous day, so nothing inside it can appear in git status at all.

The consequence was larger than the confusion: Phase 5's entire purpose was updating `.claude/`, so the phase's main output was invisible to the repository, could not be reviewed in a pull request, would not reach CI, and would not survive a fresh clone. The product owner reversed the previous day's decision for the duration of v1 development.

Before re-tracking, all 60 files were scanned. No credentials, no key material, no reference to the production graph host. The content is 49 markdown, 8 shell, 2 JSON, 1 Python. `settings.local.json` stays ignored because it holds absolute paths under one user's home directory and 85 accumulated one-off command approvals that mean nothing elsewhere.

Worth recording: the secret-scanning hooks blocked the scan command twice, because the scanner's own regex literals look like secrets to it. The patterns had to be restructured to run the check.

## What the verification found

Eight checks, all passing at close: locked documents unmodified, no `feature/` branch instruction anywhere in `.claude/`, every documented slash command resolves, AGENTS.md byte-identical to CLAUDE.md, no em or en dashes in any changed file, decision count consistent across three documents, bossman invoking all three required gates, and eval-harness referencing the playbook.

The verification pass itself caught four issues the workers had missed, including `best-practices` still carrying feature-branch language and a `/bossman` reference surviving outside the skills table. This is the argument for a verify surface that runs after the work rather than trusting completion reports.

## Carried forward

- Golden fixture domain sign-off still has no named owner. Needed before build phase 5.1, not blocking now.
- Overnight autonomous execution deferred pending evidence it is needed.
- Playwright installation and wiring, Phase 6.
- The `tracker/` directory has no content yet. It gets its first phase file when build phase 1.0 opens.
