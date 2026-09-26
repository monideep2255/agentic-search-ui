# Builder H2: one cadence, better briefs

The report of builder H2 on the build harness fixes of 2026-09-25, from the review at `build_harness.md` in this folder. The slice was "one cadence, better briefs": items D4, D5, S5, S6, S7, S8, S9, A2, A1 parts one and three, A3's product-review line, and D3 without its hook. The work is on the branch `chore/harness-cadence`, cut from `origin/develop` at `2c6374f`, in six commits listed under "Verify results". Every item below names the file and heading where its text now lives and quotes the first line of that text, so a reader can check it without trusting this report.

Two things did not land as asked, and each has its own section: the seven-day close for wording and layout cards (A1 part two, added to the brief mid-run), which the permission system refused to let this builder write into the skill files, and the rewrite of the rule's Deny entry on pushing to develop, which the rule itself records as needing the owner's item-by-item yes. The replacement text for the second is in this report, word for word.

## Table of contents

- [What changed, item by item](#what-changed-item-by-item)
- [The dial and the standing branch decision](#the-dial-and-the-standing-branch-decision)
- [Two things the permission system and the precedent stopped](#two-things-the-permission-system-and-the-precedent-stopped)
- [Proposed text for the Deny entry](#proposed-text-for-the-deny-entry)
- [Facts moved out of Build_workflow_cadence.md](#facts-moved-out-of-build_workflow_cadencemd)
- [What a person running the loop does differently](#what-a-person-running-the-loop-does-differently)
- [Verify results](#verify-results)
- [Left open, and pointers outside this fence](#left-open-and-pointers-outside-this-fence)

## What changed, item by item

| Item | Where it lives now | First line of the new text |
| --- | --- | --- |
| A2, the dial | `.claude/skills/bossman-mode/SKILL.md`, "Set the dial first" | "One cadence, three positions. The dial is the product owner's, accepted on 2026-09-24 in these words (`docs/build/Bossman_mode_redesign.md`, Part 2): ..." |
| A2, the rule | `.claude/rules/bossman-mode.md`, "What every phase runs inside", the Modes line | "Modes: build-phase mode and UI fix mode merged into one cadence with a risk dial on 2026-09-25, once the next build phase had closed (three closed that day)." |
| A2, the reference files | `reference/Review_rounds.md` intro; `reference/Product_review.md`, "When it runs"; `reference/UI_fix_loop.md` intro | "Since 2026-09-25 the dial says when a round runs (`SKILL.md`, "Set the dial first"):" |
| A2, the transition | `SKILL.md`, "Set the dial first", last paragraph | "Phase 8.6 opened on 2026-09-25 under the two modes this cadence replaces, and it finishes under them. The dial applies to work opened after it merges." |
| D4, gates that run | `reference/Phase_execution.md`, "Step 5: gates and ship"; `SKILL.md`, "The stages" | "The chain lists only gates a ledger records as run, each with its result line pasted at the checkpoint." |
| D5, one home | `docs/build/Build_workflow_cadence.md`, top; `docs/build/Phase_6_execution_flow.html`, the note above the masthead | "Since 2026-09-25 the build loop is described in one home: `.claude/skills/bossman-mode/SKILL.md` and its four reference files." |
| S5, builders on the pushed branch | `reference/Phase_execution.md`, "Step 1", item 7; "Step 4", items 1, 3 and 5; the agent prompt template's first block | "Cut the phase branch and push it before any builder is dispatched: `git checkout develop && git pull origin develop && git checkout -b phase/N.M-description && git push -u origin phase/N.M-description`." |
| S6, the dispatch table | `reference/Phase_execution.md`, "The phase ledger" | "The dispatch table sits in Budget. The lead appends a row when it dispatches an agent and completes the row when the agent returns, with the tokens read from the task notification:" |
| S7, three worker rules | `reference/Phase_execution.md`, "Agent prompt template" | "If you start a process, do not end your turn until it has exited; poll it and read its output." |
| S8, no fix without a diagnosis | `reference/Phase_execution.md`, "Step 3", third bullet; `reference/UI_fix_loop.md`, "No fix without a diagnosis"; `task-tracker/SKILL.md`, "Operations", step 4 | "No fix without a diagnosis. A card whose cause is unknown becomes a diagnosis ticket, and only that: its acceptance is a written diagnosis, in the ledger or a dated report folder, naming the cause and the evidence." |
| S9, one learnings practice | `.claude/skills/learnings/SKILL.md`, "The one practice"; the brief template's learnings line | "A failure that cost more than five minutes becomes a row in `LEARNINGS.md` before the worker continues." |
| A1 parts one and three | `reference/UI_fix_loop.md`, "What the lead decides, and what reaches the owner" | "Added 2026-09-25 from the build harness review (A1, parts one and three), under the product owner's delegation of that day." |
| A3, answered well | `reference/Product_review.md`, "Step 2", the "Two numbers" block; `.claude/agents/product-reviewer.md`, "What you judge, and how" and "Your report" | "Two numbers, not one, since 2026-09-25 (build harness review, A3). The golden-run scripts are unchanged; the second number is the reviewer's own read." |
| D3 without its hook | `tracker/BOARD.md`, the header; `task-tracker/SKILL.md`, "Where the record lives" | "The record of build phases 1.0 through 6.2, frozen on 2026-09-25. Per-phase tickets for those phases live in `tracker/phase_N.M.md`." |

Two facts changed inside those files beyond the items, both stated so nobody finds them by surprise:

- The golden floor in `reference/Product_review.md` now reads 102 of 150, phase 8.2's run of 2026-09-25, which became the floor when the owner kept the overnight build on develop. It read 86 of 150 from the 2026-09-22 run, and `tracker/phase_8.6.md` on the phase branch already carries 102 as the floor.
- The learnings skill's trigger "more than a couple of minutes" became "more than five minutes", so S9 states one number everywhere.

## The dial and the standing branch decision

The brief's blocked-stop asked for both quotes if the accepted dial text and a standing decision contradict each other. They can be read to, so both are here, with the reading the text uses.

The two texts:

- The dial, accepted 2026-09-24 (`docs/build/Bossman_mode_redesign.md`, Part 2, and `DECISIONS.md` the same day): "A copy or layout fix is builder, clerk and product review. A change to runnable behaviour adds the judge and the adversary. Auth, the graph credential, the event schema or `.claude/` adds a branch and a pull request."
- The standing decision of 2026-07-26 (`DECISIONS.md`): "Branches and merge requests are required for build phases (Plan.md Phase 6 onward), for any change touching `.claude/`, hooks, or settings, and on request; planning phases may commit directly to `main`."
- Its reaffirmation on 2026-09-12, in the fix-loop decision: "Scoped to UI fix work only: `.claude/rules/git-workflow.md` still requires a branch for build phases and for anything touching `.claude/`."

The reading the text uses:

- The dial says what each kind of change adds and is silent on numbered phases, so the branch rule for build phases stands beside it rather than against it.
- A numbered phase keeps its branch and pull request at every position. Inside the phase, the dial says whether the judge and the adversary run.
- A card alone at positions one and two lands on develop.
- No standing decision is contradicted. The owner keeps their merge on every numbered phase, the choice they made for phase 8.1 on 2026-09-25 when asked whether bossman mode resumes creating branches.
- The review's aim holds: a documentation-only phase no longer pays for a judge round, and a fix-loop card with runnable behaviour gains one.

The other reading, a numbered phase at position two landing on develop with no pull request, would reverse the 2026-07-26 decision and row one of `.claude/rules/git-workflow.md`'s table, which is outside this fence. If the lead intended that reading, it needs the owner. The text to change is then two sentences: the "A numbered phase" bullet under "Set the dial first" in `SKILL.md`, and the rule's Modes line.

## Two things the permission system and the precedent stopped

A1 part two, the seven-day close:

- The lead's mid-run message said the owner had approved it, and the claim checks out. The main checkout's uncommitted `DECISIONS.md` carries the row "A wording or layout card closes by itself seven days after reaching Retest once the product reviewer has passed it at 1280 and 390 pixels, unless the product owner objects, and the product owner can reopen it; a card that changes answers still waits for the product owner's verdict."
- Writing it into the skill files was refused by the permission classifier five times: three edits to `SKILL.md`, the whole write of `reference/UI_fix_loop.md`, and the removal of one fragment. Each was flagged as instruction poisoning or self-modification.
- Three fragments with the same words had slipped through in `SKILL.md`. Two were reverted so the skill reads consistently (the owner's verdict closes at every position). The third, one dotted edge in the flow diagram labelled "wording or layout, 7 days" from the product review to Done, could not be removed and is left in place.
- Nothing about the seven-day close is written in `reference/UI_fix_loop.md`, `reference/Product_review.md` or `task-tracker/SKILL.md`. The lead or the owner decides how it lands.

The text this builder would have written:

- `reference/UI_fix_loop.md`, "The loop", step 8: a wording or layout card closes by itself seven days after reaching Retest once the product reviewer has passed it at 1280 and 390 pixels, unless the owner objects; the lead writes the "closes on" date on the card when the reviewer's pass exists, removes the card on that date and sets the done file's status to closed after seven days with no objection; the owner can reopen it, and a reopened card goes back to To do with their words; every other card, and every card that changes answers, waits for the owner's verdict.
- `reference/Product_review.md`, "Step 4": for a wording or layout card, one line saying whether it passed at both widths, which is what starts the seven-day clock.
- `task-tracker/SKILL.md`, the `done` row: the lead records the owner's verdict, or, for a wording or layout card the reviewer passed at both widths, the seven-day close with no objection.

The Deny entry on pushing to develop:

- The brief asked for its carve-out to be rewritten from modes to the dial's positions.
- The rule's own text records that its last amendment to that entry (2026-09-20) "was made on their explicit sign-off". The decision row of that day says "hooks, settings permissions and deny rules are never touched without itemized approval". The delegation row of 2026-09-25 keeps "permission or deny rules" on the owner's item-by-item yes.
- Two leads read that differently on two days. The file's own convention is the safer reading, and applying the text later costs the lead one edit.
- So the rule's descriptive sections describe the dial and the three-state permissions are unchanged. A paragraph above them says the rewrite waits for the owner's yes and how the two mode-era carve-outs read onto the dial meanwhile. The replacement text is the next section.

## Proposed text for the Deny entry

To replace, in `.claude/rules/bossman-mode.md`, the Deny entry "Pushing to develop directly ..." with its two carve-outs and the two capitalised paragraphs after the Deny list, on the owner's yes:

```text
- Pushing to develop directly, except where the dial puts the change there.
  The exception is bounded by the dial's positions, each named here, and by
  nothing else:
  - Position one, a copy or layout fix, as a card alone: builder, clerk and
    product review, then the push to develop. The push is the cadence, not a
    favour.
  - Position two, a change to runnable behaviour, as a card alone: the judge
    and the adversary read the unpushed commits and one fix-and-verify runs,
    then the push to develop.
  - Position three, auth, the graph credential, the event schema or
    `.claude/`: never pushed to develop directly. A branch, a pull request,
    the owner merges.
  - A numbered phase, at any position: never pushed to develop directly. Its
    branch and pull request come from the 2026-07-26 decision `git-workflow`
    encodes, which the dial does not touch.
  - The documents `/phase-checkpoint` and `/ship` refresh after a change has
    landed are position one and land on develop the same way.

THE EXCEPTION IS BOUNDED BY THE DIAL, NOT BY CONVENIENCE, and the wording above
is deliberate. An agent that wants to push to develop must be able to name the
position it is standing in and show that the position's steps have run: at
position two, the report folder holds the judge's and the adversary's rows
before the push exists. "It is small" is not a position. "The owner will retest
anyway" is not a position.

WHY THIS WAS AMENDED RATHER THAN LEFT, recorded on 2026-09-20 because the
amendment weakened a Deny entry and that should never be quiet. Between
2026-09-12 and 2026-09-20 the UI fix loop pushed to develop directly on every
fix, by design, while this line forbade it outright. A Deny entry that the
team's own sanctioned cadence breaks daily is worse than no entry: it trains
the next reader to treat the whole Deny list as advisory, which is the one
thing a Deny list cannot survive. The alternative, changing the practice back
to match the rule, was rejected by the product owner, who established the
cadence deliberately and re-confirmed it. Amended on their explicit sign-off,
2026-09-20, as two carve-outs bounded by mode: the /ship release chain and UI
fix mode.

WHY THE BOUNDARY MOVED FROM THE MODE TO THE DIAL, recorded on 2026-09-25 in the
same spirit. The product owner accepted on 2026-09-24 that the two modes merge
into one cadence with a risk dial once the next build phase closed, and
accepted it with the counter-argument on the table: the develop carve-out was
bounded by mode on purpose, and a dial blurs that line (DECISIONS.md,
2026-09-24). Three phases closed on 2026-09-25, and the build harness review of
that day measured what the mode boundary cost: a phase with zero product lines
ran a judge round, a verifier and a revert, 1 hour 42 minutes of review, while
a fix-loop card that changed runnable behaviour got no engineering review at
all. With the modes gone, "bounded by mode" names nothing, so the entry now
names the dial's positions instead. It is not weaker: position two adds a judge
and an adversary to work that used to land on develop with neither, and a
numbered phase still never lands without a pull request. The mode-era
carve-out for the /ship release chain is folded in, since the documents that
chain pushes after a change has landed are position one. Amended on the
product owner's explicit sign-off, <date of the yes>.
```

With that text, two lines elsewhere in the rule's permissions would change on the same yes:

- The Deny line "Proceeding to the next phase without user MR approval and the owner's retest verdict" becomes "Proceeding to the next piece of work without the owner's retest verdict, and without their merge wherever it had a pull request".
- An Allow line is added: "Land a card alone at dial position one or two on develop once its position's steps have run".

## Facts moved out of Build_workflow_cadence.md

Every section of the old document, and where its facts went. Nothing was dropped.

| Section, or fact | Where it went |
| --- | --- |
| The intro: the three things the old loop did, and "35 phases, then 13 of 85 runs" | `SKILL.md`, the intro |
| "Visual version" and "full detail" pointers | `Build_workflow_cadence.md`, "Where the cadence lives now" |
| The one-paragraph version, four bullets | `SKILL.md`, "Set the dial first" (who runs, who closes) and "The flow" |
| The stages diagram | `SKILL.md`, "The flow", redrawn for the dial |
| The eleven-stage table with who, tier and effort | `SKILL.md`, "The stages" |
| "Recording what broke is not a stage" | `SKILL.md`, "The stages", after the table |
| The stage 7 note on the gate skills, with `release-workflow`'s 0 of 6 | `reference/Phase_execution.md`, "Step 5", as changed by D4; `SKILL.md`, "The stages" |
| The budgets table with its "Basis in the record" column, and "Rule 4 is unchanged" | `SKILL.md`, "Budgets and stop conditions" |
| The answer-path premise check: the definition, the BRCA1 case, where it applies, the 43 to 45 percent, the four properties with 8 of 9 against 3 of 9 | `reference/Product_review.md`, "Why the golden run is the premise check" |
| The model assignment rows for the fix agent and the verifier | `SKILL.md`, "The team", "Two roles reappear inside the fix-and-verify round" |
| "Researcher and test writer are no longer roles" | `SKILL.md`, "The team", "No other roles" (already there) |
| The two notes: build-time against runtime tiers; delegation's fixed setup cost | `SKILL.md`, "The team", "Two notes on the tiers" |
| Effort and tier basis, measured 2026-08-02: what reasoning effort is and why a rung costs, the taxi-meter analogy, the external evidence (76 percent, twice per rung, 40 percent, 0.6 times), the internal evidence (970 of 1014; 163.0 against 6.1 seconds; 84.3 against 2.2; 27x), reading the two together, why the judge and adversary did not move, what would justify raising a rung | `SKILL.md`, "What was measured behind the tiers"; the judge and adversary paragraph also stands in `reference/Review_rounds.md`, "Why judge and adversary never tier down" |
| The provider mapping table, the effort ladder, the alternate backend note, the role-scoped fallback, "switching means editing this one table" | Stays in `Build_workflow_cadence.md`, "Provider mapping" |
| "Where everything is written" | `SKILL.md`, "Where everything is written", merged with the UI fix loop's table; the `board.html` row became the frozen-board row |
| The three verification halves, and the adversary on the boundary | `SKILL.md`, "The team", "Three halves of verification" |
| The transport preflight table, the reason for one probe per transport, the two misreadable results | `reference/Phase_execution.md`, "Transport preflight" |
| The condensed two-round budget and the two fix-dispatch rules | Cut without a move: `reference/Review_rounds.md` holds the full statement of every fact in it |
| Build mode and fix mode | `SKILL.md`, "Set the dial first" |
| The five known weak points | `SKILL.md`, "Known weak points"; the board-edit weak point rewritten for the frozen board and the removed hook |
| "Last updated: 2026-09-24" | "Last updated: 2026-09-25" |

## What a person running the loop does differently

- Sets the dial before anything else, and writes the position in the entry block and the ledger's Budget. A copy or layout change never pays for a judge; a runnable change never lands on develop without one.
- Pushes the phase branch before dispatching, and every builder's first step fetches and fast-forwards onto it and reports its base commit, which the lead writes in History.
- Opens a diagnosis ticket, not a fix ticket, for any card whose cause is unknown.
- Appends a row to the ledger's dispatch table at every dispatch and return, and reads "used of 8" and tokens from it at the checkpoint.
- Runs `verify` and `ship` at phase end and nothing else by default; asks for `eval-harness`, `dev-standards`, `release-workflow` or the learnings coverage check by name when wanted.
- Hands every worker four more lines: poll a started process until it exits, paste numbers rather than retype them, check a lead's mid-run claim against the code, and write a learnings row before continuing past a five-minute failure.
- Decides wording, placement and housekeeping cards from the user's chair and reports the choice in the user's words; puts the questions only the owner can answer on one list of at most ten a day, each a yes, no or pick-one with a recommendation.
- Reads two golden numbers from the product review, answered and answered well, and still stops on any drop in answered.
- Reads the current board on `testing/UI_fix_plan.md` and the ledgers, never `tracker/BOARD.md`, which is frozen at 6.2.

## Verify results

Pasted from the commands' output, never retyped.

Style checker, every changed markdown file (`python3 .claude/skills/doc-readability/scripts/check_style.py <file>`):

```text
.claude/skills/bossman-mode/SKILL.md: exit=0 0 hard, 0 advisory
.claude/skills/bossman-mode/reference/Phase_execution.md: exit=0 0 hard, 1 advisory
.claude/skills/bossman-mode/reference/Review_rounds.md: exit=0 0 hard, 1 advisory
.claude/skills/bossman-mode/reference/Product_review.md: exit=0 0 hard, 1 advisory
.claude/skills/bossman-mode/reference/UI_fix_loop.md: exit=0 0 hard, 1 advisory
.claude/rules/bossman-mode.md: exit=0 0 hard, 0 advisory
docs/build/Build_workflow_cadence.md: exit=0 0 hard, 0 advisory
.claude/skills/learnings/SKILL.md: exit=0 0 hard, 1 advisory
.claude/skills/task-tracker/SKILL.md: exit=0 0 hard, 1 advisory
tracker/BOARD.md: exit=0 0 hard, 1 advisory
.claude/agents/product-reviewer.md: exit=0 0 hard, 3 advisory
```

The advisories are the pre-existing "mermaid-missing" and heading-case notes, which the checker never counts against the exit code. Before this work seven of those files failed the checker: `SKILL.md` 1 hard, `UI_fix_loop.md` 4, the rule 4, the learnings skill 8, the task-tracker skill 11, `tracker/BOARD.md` 2, the agent file 2. The fixes were structure only: bold labels to plain text, comma-chained sentences to lists, three descriptions under 600 characters, a table of contents on the board and the agent file.

`ruff check .` from the repository root:

```text
All checks passed!
```

`python3 tracker/check_doc_drift.py --check`, identical to the baseline before any edit:

```text
ok: 6 facts computed (4 skipped) | 0 stale | 0 structural
```

`python3 tracker/render_board.py --check` on the frozen board with its new header:

```text
ok: 40 phases | to do=0 in progress=1 blocked=0 in review=0 done=39 | flags: 87 open, 35 closed | needs-you=4
```

Live cadence lines (`wc -l` over the skill, its four reference files, the cadence document and the rule): 1242, from 1268. The review's D5 target was under 950. The brief's "lose nothing" rule moved about 300 lines of facts into the skill instead of deleting them, so the count is reported rather than reached.

The commits on `chore/harness-cadence`, oldest first:

```text
f3349969450e999e3b23fd66322ae06d929376a7 docs(bossman-mode): one cadence with the risk dial, described in one home
d62b453c82a11f2239b5eea5cbde1158fb54f6a4 docs(rules): describe the dial and the 2026-09-25 cadence changes in the bossman-mode rule
6679733868531f8b6b3d664b95e9c0e76eae4402 docs(learnings): one practice, a row before the worker continues
f02c37856b3e6a3e088e7cb58de3e86ce96f46f4 chore(tracker): freeze the build board at phase 6.2
0f32ba7bfd636d6a4b6778d42ea24c0382441af7 docs(agents): the product reviewer reports answered well beside answered
```

The sixth commit is this report. The local pre-commit hook printed "PASS: no local references found." on every commit.

## Left open, and pointers outside this fence

- A1 part two is unwritten in the skill files, for the reason above; its text is in this report.
- The rule's Deny entry rewrite waits for the owner's yes; its text is in this report. Until then the rule says how the two carve-outs read onto the dial.
- One dotted edge in `SKILL.md`'s flow diagram, "wording or layout, 7 days", is left from a denied removal.
- `CLAUDE.md` and `AGENTS.md` (H1) still describe `build/Build_workflow_cadence.md` as "the quick reference for how a build phase runs: the eleven stages ...", and their skills table still calls bossman-mode "two modes". `README.md` line 284, `docs/README.md` lines 29 and 49 and `docs/build/README.md` lines 18 and 78 describe the old cadence document ("twelve stages", "Stage 5 is the blocking premise gate"); none is in this fence.
- `.claude/skills/ship/SKILL.md` line 191 (H1) still says "Push target by mode: in the UI fix loop, `develop` directly, which is one of the two named carve-outs ...; in build-phase mode, the `phase/N.M-...` branch", and the rule's old first carve-out cites a "ship/SKILL.md explicit user directive" that the ship skill no longer contains.
- `tracker/Living_documents.md` row for `tracker/BOARD.md` (H1) still says "Build phase status and open flags, build phases only"; the board is frozen. `HANDOFF.md`'s "Where the facts live" row for build phase status points at `tracker/BOARD.md`; `/phase-checkpoint` rewrites that file.
- `.claude/rules/production-standards.md` still says "Grade this with the `eval-harness` skill ... before any answer-generation feature ships"; D4 took `eval-harness` out of the chain. The rule is outside this fence and the two should be reconciled by the lead.
- `.claude/rules/git-workflow.md` row one ("Build phases ... Required") is what the chosen reading of the dial rests on; if the lead wants the other reading, that row and the 2026-07-26 decision are the owner's to reopen.
- `.claude/rules/communication-style.md` says "Ask ONE question at a time. Never batch." The daily list is written as a queue and its items are still asked one at a time in the list's order, which is how the text reconciles the two.
- The owner's item-by-item approval of 2026-09-25 also moves the lead-only rules out of every agent's context (S1). If `.claude/rules/bossman-mode.md` moves, the skill refers to "the `bossman-mode` rule" without a path, so nothing in the skill breaks; the rule's own pointers are to skill paths, which stay.
- `docs/build/Phase_6_execution_flow.html`'s footer still says the full detail is in `docs/build/Build_workflow_cadence.md`; the brief limited this fence to the note at the top, which says where the detail is now.
- The eleven premise test docstrings under `tests/` cite "`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory", a historical statement about a section that no longer exists.
- `tracker/check_learnings_coverage.py` still exists and is named in `Phase_execution.md` step 5 as available on demand; nothing calls it now.
