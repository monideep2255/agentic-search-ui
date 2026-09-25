---
description: "Autonomous execution mode - suspends deliberation rules, runs each phase inside 8 hours, 8 dispatches and two review rounds, ends every phase on a product review of develop"
---

## Bossman mode rule

When bossman mode is active (user has invoked `/bossman` and activation checklist passed):

### Suspended behaviors

- **Do not pause to check if clarification is needed** (overrides the pause-before-acting check in anti-rationalization, step 2). Rules still apply, but you do not stop to ask.
- **Do not ask what the user thinks before acting** (overrides preserve-your-thinking). Decisions were made during planning. Execute.
- **Do not run Socratic clarification before drafting** (overrides the clarify-before-drafting section of preserve-your-thinking). Scope is defined.
- **Do not ask "should I do X or Y?"** - pick the better path, note the choice, keep moving.

### Preserved behaviors

- File protection: never delete without informing.
- Dependency tracking: track what you build.
- Writing style: output quality stays high.
- Git workflow: phase branches, MRs, clean commits, no co-author lines.
- Parallel-first (in plan-then-fan-out): maximize speed via agent teams for builders.
- Boil-the-lake (in goal-contracts): do it 100%.
- Skill chain at phase end: one judge round, one adversary round, one fix-and-verify round, the gates named in `docs/build/Build_workflow_cadence.md` stage 7 (`verify`, `dev-standards` where warranted, `eval-harness` when an answer-generation feature shipped) -> `ship`. After the owner merges, the product reviewer runs against the deployed develop app, and on an answer-path change the golden consistency run blocks. Amended 2026-09-24 from the bossman redesign (DECISIONS.md, the eight rows of that date). Rewritten at Step 6.2, 2026-08-10, to match measured practice: `release-workflow` as a single mandatory phase-end dispatch had a 0-of-6 real dispatch rate through build phase 3.4, while the judge, adversary, and gate sequence above ran, and caught real defects, every phase. Per this repo's own `attack-the-constraint` standard, an unenforced mandate is an ownerless requirement; `release-workflow` stays available to invoke directly whenever its end-to-end local-verify-then-ship ritual is wanted, it is just no longer the assumed default.

### Dispatch model

- 2+ parallel builder tasks: use agent teams (teammates in tmux panes)
- Single-task roles (judge, adversary, fix agent, verifier, product reviewer, clerk): use sub-agents
- At most 8 agent dispatches per phase, reviewers and the product reviewer included
- Workers never dispatch agents. Only the lead dispatches
- See `.claude/skills/bossman-mode/SKILL.md` for the six roles, their tiers and the flow

### What every phase runs inside

Accepted by the product owner on 2026-09-24 from `docs/build/Bossman_mode_redesign.md` ("Accept all eight"), one line per decision:

- Order: work is picked by what a person sees first, answer quality and speed ahead of technical specification Section 25's order. Section 25 still defines each phase and its real dependencies.
- Product review: a product reviewer drives the deployed develop app at 1280 and 390 beside the design prototype and reads answers against a five-line rubric, as a pre-screen before the owner's retest. It never closes an item. This reverses the 2026-09-01 decision that the assistant drives the browser only when asked, for this pre-screen only.
- Golden run: the golden consistency run blocks every answer-path change. Any drop in the answered count, measured over its three passes, stops the phase.
- Review rounds: one judge round and one adversary round, then one fix-and-verify. There is no third round, ever. After round two, merge with the open item named, or revert.
- Checks: no premise gate, mutation harness file or coverage claim for anything except answer behaviour. Breaking a control to see a test go red is one line on the judge's checklist.
- Budget: 8 hours from phase open to ready for owner, and 8 agent dispatches.
- Narrative: the build narrative lives in `requirements/Plan.md`, not in CLAUDE.md or the board.
- Modes: build-phase mode and UI fix mode merge into one cadence with a risk dial AFTER the next build phase closes. Until then they stay two modes, and the carve-outs below stay bounded by mode.

### Three-state permissions

Allow:
- Write files, run commands, dispatch agents and teammates without conversational confirmation
- Create agent teams for parallel builder tasks
- Make tactical decisions (library choice, file structure, naming) and log them
- Execute an entire phase autonomously on a phase branch
- Run the judge round, the adversary round, one fix-and-verify round and the phase-end gates, then ship, at phase end
- Dispatch the product reviewer against the deployed develop app before every owner retest, and run the golden consistency run on every answer-path change

Ask:
- Architecture-level changes that contradict the agreed plan
- Anything that affects phases beyond the current one
- Deleting files or reverting prior work
- External data downloads: present exact URLs and file names for user verification before downloading
- A ninth agent dispatch in one phase
- Accepting a drop in the golden answered count: only the product owner may, never the lead

Deny:
- Proceeding to the next phase without user MR approval and the owner's retest verdict
- A third review round, even with the owner's authorisation: after round two, merge with the open item named, or revert
- Running past 8 hours on one phase: stop, write the handoff, escalate with options
- A worker dispatching an agent
- Landing anything else on develop while the golden answered count sits below its floor
- Writing a premise gate, a mutation harness file or a coverage claim for anything that is not answer behaviour
- Ignoring a blocker by guessing
- Pushing to develop directly (push to phase branch only, merge via MR). Two carve-outs, both narrow and both named, and nothing else:
  - The sanctioned /ship release chain at phase end, where ship/SKILL.md's explicit user directive overrides this and permits pushing directly to develop
  - UI fix mode, invoked as `/bossman --ui`, where the whole point of the cadence is that a product-owner defect lands on develop immediately and their retest is the verification step. Product-owner decision of 2026-09-12, re-confirmed on 2026-09-20

THE CARVE-OUTS ARE BOUNDED BY MODE, NOT BY CONVENIENCE, and the wording above is
deliberate. UI fix mode is a one-off cadence for defects the product owner hits
while testing, not a standing licence: build-phase mode still branches, still
opens a pull request, and still runs the judge and adversary rounds. An agent
that wants to push to develop must be able to name which of the two carve-outs
it is standing in, and `/bossman` with no `--ui` flag is neither of them.

WHY THIS WAS AMENDED RATHER THAN LEFT, recorded because the amendment weakens a
Deny entry and that should never be quiet. Between 2026-09-12 and 2026-09-20 the
UI fix loop pushed to develop directly on every fix, by design, while this line
forbade it outright. A Deny entry that the team's own sanctioned cadence breaks
daily is worse than no entry: it trains the next reader to treat the whole Deny
list as advisory, which is the one thing a Deny list cannot survive. The
alternative, changing the practice back to match the rule, was rejected by the
product owner, who established the cadence deliberately and re-confirmed it.
Amended on their explicit sign-off, 2026-09-20.

### When bossman mode is NOT active

This rule has no effect. All suspended rules operate normally.
