---
description: "Autonomous execution mode - suspends deliberation rules, runs one cadence with a risk dial inside 8 hours, 8 dispatches and two review rounds, ends every change on a product review of develop"
paths: ["HANDOFF.md", "DECISIONS.md", "LEARNINGS.md", "testing/UI_fix_plan.md", "testing/UI_fixes_done.md", "docs/build/*", ".claude/skills/bossman-mode/*", ".claude/skills/bossman-mode/reference/*", "{tracker,requirements}/**/*"]
---
## Bossman mode rule

When bossman mode is active (user has invoked `/bossman` and activation checklist passed):

### Suspended behaviors

- Do not pause to check if clarification is needed (overrides the pause-before-acting check in anti-rationalization, step 2). Rules still apply, but you do not stop to ask.
- Do not ask what the user thinks before acting (overrides preserve-your-thinking). Decisions were made during planning. Execute.
- Do not run Socratic clarification before drafting (overrides the clarify-before-drafting section of preserve-your-thinking). Scope is defined.
- Do not ask "should I do X or Y?" - pick the better path, note the choice, keep moving.

### Preserved behaviors

- File protection: never delete without informing.
- Dependency tracking: track what you build.
- Writing style: output quality stays high.
- Git workflow: a branch and a pull request for every numbered phase and for any change at the dial's third position (auth, the graph credential, the event schema or `.claude/`), clean commits, no co-author lines.
- Parallel-first (in plan-then-fan-out): maximize speed via agent teams for builders.
- Boil-the-lake (in goal-contracts): do it 100%.
- Skill chain at the end of a change: one judge round, one adversary round and one fix-and-verify round where the dial runs them (positions two and three), then the gates in `.claude/skills/bossman-mode/reference/Phase_execution.md` step 5 (`verify`, then `ship`'s CI gates run locally) -> `ship`. After the change lands on develop, the product reviewer runs against the deployed app, and on an answer-path change the golden consistency run blocks. History of this line, so the trimming is not quiet: rewritten at Step 6.2 (2026-08-10) when `release-workflow` as a mandatory phase-end dispatch measured 0 of 6 real dispatches through build phase 3.4 while the judge, adversary and gate sequence ran and caught real defects every phase; amended 2026-09-24 from the bossman redesign (DECISIONS.md, the eight rows of that date); trimmed 2026-09-25 by the build harness review (D4), which found `eval-harness`, `dev-standards` and `check_learnings_coverage.py` left no trace in any 8.x ledger. Per this repo's own `attack-the-constraint` standard an unenforced mandate is an ownerless requirement. All four stay available to invoke directly whenever their ritual is wanted; none is the assumed default.

### Dispatch model

- Agent teams (teammates in tmux panes) for 2+ parallel builder tasks; sub-agents for single-task roles (judge, adversary, fix agent, verifier, product reviewer, clerk)
- At most 8 agent dispatches per phase, reviewers and the product reviewer included, counted in the ledger's dispatch table with each dispatch's model, effort, start, end and tokens, never by hand
- Workers never dispatch agents. Only the lead dispatches. Builders start from the pushed phase branch, and the lead records each builder's base commit in the ledger's History
- See `.claude/skills/bossman-mode/SKILL.md` for the six roles, their tiers, the dial and the flow

### What every phase runs inside

Accepted by the product owner on 2026-09-24 from `docs/build/Bossman_mode_redesign.md` ("Accept all eight"), one line per decision:

- Order: work is picked by what a person sees first, answer quality and speed ahead of technical specification Section 25's order. Section 25 still defines each phase and its real dependencies.
- Product review: a product reviewer drives the deployed develop app at 1280 and 390 beside the design prototype and reads answers against a five-line rubric, as a pre-screen before the owner's retest. It never closes an item. This reverses the 2026-09-01 decision that the assistant drives the browser only when asked, for this pre-screen only.
- Golden run: the golden consistency run blocks every answer-path change. Any drop in the answered count, measured over its three passes, stops the phase.
- Review rounds: one judge round and one adversary round, then one fix-and-verify. There is no third round, ever. After round two, merge with the open item named, or revert.
- Checks: no premise gate, mutation harness file or coverage claim for anything except answer behaviour. Breaking a control to see a test go red is one line on the judge's checklist.
- Budget: 8 hours from phase open to ready for owner, and 8 agent dispatches.
- Narrative: the build narrative lives in `requirements/Plan.md`, not in CLAUDE.md or the board.
- Modes: build-phase mode and UI fix mode merged into one cadence with a risk dial on 2026-09-25, once the next build phase had closed (three closed that day). The dial, in the owner's accepted words: a copy or layout fix is builder, clerk and product review; a change to runnable behaviour adds the judge and the adversary; auth, the graph credential, the event schema or `.claude/` adds a branch and a pull request. A numbered phase keeps its branch and pull request at every position (`git-workflow`, the decision of 2026-07-26). Phase 8.6, open when the modes merged, finishes under the two modes.
- Added 2026-09-25 from the build harness review, under the owner's delegation of that day (DECISIONS.md, 2026-09-25, "The lead implements both harness reviews' takeaways"), each detailed in the skill: no fix without a written diagnosis, which the lead may write itself when the cause is plain; a phase-end chain of gates a ledger records as run; builders start on the pushed phase branch and every brief carries four worker rules (a process is polled until it exits, numbers are pasted never retyped, a lead's mid-run factual claim is checked against the code, a failure over five minutes is a `LEARNINGS.md` row before continuing); a dispatch table with model, effort, times and tokens in every ledger; the lead decides wording, placement and housekeeping cards inside `decide-from-the-users-chair` and questions reach the owner as one list of at most ten a day, each a yes, no or pick-one with a recommendation; the product reviewer reports answered well beside answered, and any drop in answered still blocks.

### Three-state permissions

The lists below are the owner's to change item by item: the 2026-09-20 amendment of the Deny entry on pushing to develop was made on their explicit sign-off, and so was its rewrite to the dial's positions on 2026-09-26 (DECISIONS.md, 2026-09-26, "Two rule edits approved item by item").

Allow:
- Write files, run commands, dispatch agents and teammates without conversational confirmation
- Create agent teams for parallel builder tasks
- Make tactical decisions (library choice, file structure, naming) and log them
- Execute an entire phase autonomously on a phase branch
- Run the judge round, the adversary round, one fix-and-verify round and the phase-end gates, then ship, at phase end
- Dispatch the product reviewer against the deployed develop app before every owner retest, and run the golden consistency run on every answer-path change
- Land a card alone at dial position one or two on develop once its position's steps have run

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
- Pushing to develop directly, except where the dial puts the change there. The exception is bounded by the dial's positions, each named here, and by nothing else:
  - Position one, a copy or layout fix, as a card alone: builder, clerk and product review, then the push to develop. The push is the cadence, not a favour.
  - Position two, a change to runnable behaviour, as a card alone: the judge and the adversary read the unpushed commits and one fix-and-verify runs, then the push to develop.
  - Position three, auth, the graph credential, the event schema or `.claude/`: never pushed to develop directly. A branch, a pull request, the owner merges.
  - A numbered phase, at any position: never pushed to develop directly. Its branch and pull request come from the 2026-07-26 decision `git-workflow` encodes, which the dial does not touch.
  - The documents `/phase-checkpoint` and `/ship` refresh after a change has landed are position one and land on develop the same way.

THE EXCEPTION IS BOUNDED BY THE DIAL, NOT BY CONVENIENCE, and the wording above is deliberate. An agent that wants to push to develop must be able to name the position it is standing in and show that the position's steps have run: at position two, the report folder holds the judge's and the adversary's rows before the push exists. "It is small" is not a position. "The owner will retest anyway" is not a position.

WHY THIS WAS AMENDED RATHER THAN LEFT, recorded on 2026-09-20 because the amendment weakened a Deny entry and that should never be quiet:
- Between 2026-09-12 and 2026-09-20 the UI fix loop pushed to develop directly on every fix, by design, while this line forbade it outright.
- A Deny entry that the team's own sanctioned cadence breaks daily is worse than no entry: it trains the next reader to treat the whole Deny list as advisory, which is the one thing a Deny list cannot survive.
- The alternative, changing the practice back to match the rule, was rejected by the product owner, who established the cadence deliberately and re-confirmed it.
- Amended on their explicit sign-off, 2026-09-20, as two carve-outs bounded by mode: the /ship release chain and UI fix mode.

WHY THE BOUNDARY MOVED FROM THE MODE TO THE DIAL, recorded in the same spirit and amended on the product owner's explicit sign-off, 2026-09-26:
- The product owner accepted on 2026-09-24 that the two modes merge into one cadence with a risk dial once the next build phase closed, with the counter-argument on the table: the develop carve-out was bounded by mode on purpose, and a dial blurs that line (DECISIONS.md, 2026-09-24).
- Three phases closed on 2026-09-25. The build harness review of that day measured what the mode boundary cost: a phase with zero product lines ran a judge round, a verifier and a revert, 1 hour 42 minutes of review, while a fix-loop card that changed runnable behaviour got no engineering review at all.
- With the modes gone, "bounded by mode" names nothing, so the entry now names the dial's positions instead.
- It is not weaker: position two adds a judge and an adversary to work that used to land on develop with neither, and a numbered phase still never lands without a pull request.
- The mode-era carve-out for the /ship release chain is folded in, since the documents that chain pushes after a change has landed are position one.

### When bossman mode is NOT active

This rule has no effect. All suspended rules operate normally.
