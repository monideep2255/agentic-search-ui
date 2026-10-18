# Handoff history

What `HANDOFF.md` used to say. `HANDOFF.md` holds only the current state, capped at about 4 KB, so a fresh session loads little. At every rewrite, `/phase-checkpoint` moves the outgoing version here, verbatim, under a dated heading, newest first. Nothing here is current: a statement in this file was true on its heading's date. For what is true now, read `HANDOFF.md`.

Last updated: 2026-10-17.

## Table of contents

- [Starting on another computer](#starting-on-another-computer)
- [Handoff as of 2026-10-17, evening](#handoff-as-of-2026-10-17-evening)
- [Handoff as of 2026-10-17, morning](#handoff-as-of-2026-10-17-morning)
- [Handoff as of 2026-10-16, afternoon](#handoff-as-of-2026-10-16-afternoon)
- [Handoff as of 2026-10-16, daytime](#handoff-as-of-2026-10-16-daytime)
- [Handoff as of 2026-10-16, morning](#handoff-as-of-2026-10-16-morning)
- [Handoff as of 2026-10-15](#handoff-as-of-2026-10-15)
- [Handoff as of 2026-10-09, night](#handoff-as-of-2026-10-09-night)
- [Handoff as of 2026-10-09, morning](#handoff-as-of-2026-10-09-morning)
- [Handoff as of 2026-10-08, morning](#handoff-as-of-2026-10-08-morning)
- [Handoff as of 2026-10-07](#handoff-as-of-2026-10-07)
- [Handoff as of 2026-10-05, night](#handoff-as-of-2026-10-05-night)
- [Handoff as of 2026-10-05, evening](#handoff-as-of-2026-10-05-evening)
- [Handoff as of 2026-10-04](#handoff-as-of-2026-10-04)
- [Handoff as of 2026-09-30](#handoff-as-of-2026-09-30)

## Starting on another computer

Standing setup steps for a new laptop, moved out of `HANDOFF.md` on 2026-10-04 because they change rarely and a session on an already-set-up laptop never needs them. Edit them here when a step changes.

On an Intel Mac, step 1 cannot run: Homebrew's installer stops with "Homebrew on macOS is only supported on Apple Silicon processors!". The second laptop, set up on 2026-09-29, used a standalone Python 3.11 from python-build-standalone and Miniforge from conda-forge for PostgreSQL, Redis and Node, all in the home folder, with `cryptography` held at 48.0.1 for the local install (`DECISIONS.md` and `LEARNINGS.md`, 2026-09-29). Every other step below applies unchanged.

For a laptop with nothing installed. The commands are for macOS on Apple silicon, like the laptop this build ran on. Git carries the code, the documents and every parked branch; everything else below is installed or copied by hand. Run the steps in order, in one terminal.

1. System tools. Install Apple's command line tools, then Homebrew with the one command on https://brew.sh, and run the two lines Homebrew prints at the end, which put `brew` on the PATH. Then install what this build uses and start the database:

   ```bash
   xcode-select --install
   brew install git gh python@3.11 node postgresql@15 tmux railway
   brew link --force postgresql@15
   brew services start postgresql@15
   ```

   - Python 3.11 is what CI runs. Node must be 22 or newer; the first laptop ran 24.
   - PostgreSQL 15 is keg-only in Homebrew, so the `link` line puts `psql` and `createdb` on the PATH.
   - Skip Redis. `README.md` lists it, but no code uses it and the first laptop never had it.
   - The assistant's own command-line tool installs separately, by its own instructions.

2. Sign-ins and commit identity. Sign in to GitHub as the owner's account, which pushes, merges pull requests and reads CI, and to Railway, which `/ship` uses to confirm a deploy. Commits use the GitHub noreply address, never a work address (`public-repository-privacy`):

   ```bash
   gh auth login
   gh auth setup-git
   railway login
   git config --global user.name "Monideep Chakraborti"
   git config --global user.email "65699118+monideep2255@users.noreply.github.com"
   ```

3. Clone both repositories side by side, in a folder outside iCloud with no space in its path. On the first laptop, iCloud made " 2" copies inside `.git` that broke `git fetch` (`LEARNINGS.md`, 2026-09-25), and the worktree isolation guard cannot read a path with a space in it. The data engineering repository goes beside this one because `reference/agentic-search-data-engineering` is a relative link to it.

   ```bash
   cd <parent-folder>
   gh repo clone monideep2255/agentic-search-ui
   gh repo clone monideep2255/agentic-search-data-engineering
   cd agentic-search-ui
   ```

4. Privacy hook. `.git/hooks/` is never cloned, so the local pre-commit and commit-msg hooks are missing. Reinstall them from the owner's private notes (not published) before the first commit. GitHub push protection still blocks secrets, but nothing else catches a local path or a name.

5. Secrets. Three files hold the keys and private context, and nothing runs without the first. Never send them through git, email or a chat:
   - `.env` at the root: the model provider keys, the graph query service address and token, the auth secret. `env.example` names every key if you rebuild it instead.
   - `frontend/.env`, one line, `VITE_API_BASE_URL`.
   - `requirements/context/Private_NCBI_context.md`.

   Copy each back to its own path by hand, or rebuild `.env` from `env.example`.

   With `.env` in place, the app and the preflight reach the graph over the HTTPS query service, so the new laptop needs no SSH tunnel. The direct-connection graph keys in `.env` are only the rollback path (`env.example`).

6. Packages. Build them fresh, the way CI does. Never copy `venv/` or `frontend/node_modules/` across, since they were built for the old machine. The last line installs the browser `/verify` takes its screenshots with.

   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   .github/gates/setup_python.sh
   npm ci --prefix frontend
   npx --prefix frontend playwright install chromium
   ```

7. The user database. Create it and build its tables. The migration reads the database address from the environment, not from `.env`, so it is set on the same line:

   ```bash
   createdb search_agent_users
   USER_DB_URL=postgresql://localhost:5432/search_agent_users alembic upgrade head
   ```

8. The assistant's own setup, which lives outside the repository on each machine:
   - Its memory folder, which holds the owner's standing feedback. Copy it by hand, or the first session starts without it.
   - Its user-level settings for agent teams in tmux (`docs/build/Agent_teams_tmux_quickstart.md`), its plugins, and the gitignored `.claude/settings.local.json`.

9. Prove it. The preflight probes the model providers and the graph, and the unit suite needs the database from step 7. Both read `.env` themselves. Both must pass before any build work:

   ```bash
   python3 tracker/preflight.py
   .github/gates/gate04_unit_suite.sh
   ```

   To see the app, run the API in this terminal and the frontend in a second one, then open http://localhost:5173:

   ```bash
   uvicorn system_03_search_agent.adapters.web_sse.app:app --reload
   npm run dev --prefix frontend
   ```

## Handoff as of 2026-10-17, evening

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-17.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `6935a0a3` is the product (card 125, #271); documents since then only. Deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged today, behind CI, a judge and an adversary, then checked on deployed develop at 1280 and 390: card 125, no paper's title or abstract can pose as the answer writer's instructions, and records read exactly as PubMed writes them. Its third attempt; three small items merged open by your call (`testing/Future.md`, row 61).
- Closed today, never pushed, each back in To do as "Design with you first": card 126 (the disagreement line fired where nothing disagreed) and card 56's first slice (a single NCBI fit trusted for an acronym, "HEV" read as a pig virus). Why: `DECISIONS.md`, rows dated 2026-10-17.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.

### What awaits the product owner

- Retests: the rows at the top of `testing/Retest_product_owner.md`, card 125 first, then the night of 16 to 17 October; each checked by the team on deployed develop.
- The poster release: four calls for you in the plan above, each asked on its own tomorrow.
- After the event, privacy: whether to rewrite git history to drop two private symlink targets (`DECISIONS.md`, 2026-10-17); the current tree is clean.
- Designs, after the event: card 56's next slice (the design and the first slice's reviews: `testing/Developer/reports/2026-10-17_card56/`), card 126, and the other "Design with you first" cards on the board.
- New cards: 127 (a remembered organism never reaches its sequencing records) and 128 (a CFTR answer with no summary and no note), both buildable.
- On 23 October, card 84's row: a week of the server's lag lines decides the freeze fix.
- Every decision taken today: `DECISIONS.md`, rows dated 2026-10-17. What broke: `LEARNINGS.md`.

### The one next action

Tomorrow, Sunday 18 October, is a freeze-and-release day for the innovation day poster, by your call: no new features; retest the top rows of `testing/Retest_product_owner.md`, answer the four release calls, then release develop to production and verify the demo questions there. The plan, step by step: `testing/Developer/reports/2026-10-17_poster_release/plan.md`.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; today's: `testing/Developer/reports/2026-10-17_card56/`, `_card125/`, `_card126/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-17, morning

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-17.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `cf9be15d` is the product; documents since then only. Deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged overnight 2026-10-16 to 17, each behind CI, its reviews and a fresh verifier, then checked on deployed develop at desktop and phone width:
  - Card 30, step 1 (#261): a gene's variant list says it is not a list of pathogenic variants.
  - Card 37, slice A1 (#262): rs334 is named by its id, with its gene and significance.
  - Card 8 (#266): the line under an answer names the databases it rests on.
  - Card 38, slices B (#265) and C (#267): orthologs show their species; graph papers show their titles.
  - Card 105 (#268): a picked "How far back" window leaves out the graph's undated papers.
- Closed by your rule, back in To do with their reviews: card 18, card 37's slice A2 and card 30's step 2b. Three more (8, 105, 38 C) closed once and were rebuilt and merged. Why: `DECISIONS.md`, rows dated 2026-10-16 and 17.
- A usage limit stopped the session from 01:40 to 11:32, so the 07:00 close ran late (`LEARNINGS.md`, 2026-10-17).
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.

### What awaits the product owner

- Retests: the night's rows at the top of `testing/Retest_product_owner.md`, each checked by the team on deployed develop.
- Two calls on card 8's row: MedGen counted under "other databases" when databases tie, and the rare case where two databases disagree.
- One security call on card 38 slice C's row: whether every paper title path, live ones included, gets a stricter cleaning.
- Designs: cards 18 and 37 (slice A2) now say "Design with you first"; card 30's step 2b says what its next attempt needs.
- New cards from the night's checks, 119 to 124, at the bottom of To do.
- On 23 October, card 84's row: the night's checks saw two more safety-check timeouts on develop.
- Every decision taken for you: `DECISIONS.md`, rows dated 2026-10-16 and 17. What broke: `LEARNINGS.md`.

### The one next action

Retest the night's cards from the top of `testing/Retest_product_owner.md`, then choose the first "Design with you first" card on the board to design together.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `testing/Developer/reports/2026-10-16_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-16, afternoon

### What is live

- Develop: `b15038e3` is the product; documents since then only. Deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged 2026-10-16, each behind CI and three independent reviews (one checks the code, one hunts for a wrong answer, a third re-checks with fresh eyes):
  - Overnight: cards 115, 17, 94's timeout fix and 24, each checked on deployed develop at desktop and phone width.
  - Today, cards 75 (#252) and 118 (#253): when the command line cannot tell whether its sign-in was renewed, it asks for `s3 login` once, so nobody is signed out of the web app by surprise.
  - Today, the freeze count (#251, cards 84 and 72): the server logs each moment it falls behind.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.
- The board's To do column has a Next move column: the team or Factory builds it now, a design with you first, or yours.
- Factory works again, on cards 100, 106, 117 and 113 (`docs/build/Factory_onboarding.md`). The Factory review loop is paused and not installed (`docs/build/Factory_review_loop.md`), so Factory's pull requests come to me through you.

### What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first. Cards 75 and 118 show only when a sign-in renewal fails, so there is nothing to type for them.
- On 23 October, decide whether the safety check's freeze fix is worth building (card 84's row): read a week of `event loop lag` lines from develop's log; each is a moment the server fell behind, not freezes alone.
- The cards marked "Design with you first" on the board, starting with card 101.
- The cards marked "Yours" on the board: your decisions (such as card 40's hook and rule changes) and your own architecture work.
- Findings the product check flagged for you: `testing/Developer/reports/2026-10-16_product_check/report.md`.
- Every decision taken for you: `DECISIONS.md`, rows dated 2026-10-15 and 16. What broke: `LEARNINGS.md`.

### The one next action

Retest the night's cards from `testing/Retest_product_owner.md`, then pick the first "Design with you first" card on the board (101, where a quoted record sentence ends) to design together.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `testing/Developer/reports/2026-10-15_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-16, daytime

### What is live

- Develop: `b15038e3`, deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged 2026-10-16, each behind CI and three independent reviews (one checks the code, one hunts for a wrong answer, a third re-checks with fresh eyes):
  - Overnight: cards 115, 17, 94's timeout fix and 24, each checked on deployed develop at desktop and phone width.
  - Today, cards 75 (#252) and 118 (#253): when the command line cannot tell whether its sign-in was renewed, it asks for `s3 login` once, so nobody is signed out of the web app by surprise.
  - Today, the freeze count (#251, cards 84 and 72): the server logs each moment it falls behind.
- Closed overnight by your rule, each back in To do with its reviews on develop: cards 48, 29, 94's lookup, 110, 101, 20 and 15. Why: `DECISIONS.md`, rows dated 2026-10-15 and 16.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.
- Factory works again, on cards 100, 106, 117 and 113 (`docs/build/Factory_onboarding.md`). The board's To do column says who moves each card next.

### What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first. The team checked the overnight four on deployed develop; cards 75 and 118 show only when a sign-in renewal fails, so there is nothing to type.
- On 23 October, decide whether the safety check's freeze fix is worth building (card 84's row):
  - Read a week of `event loop lag` lines from develop's log.
  - Each line is a moment the server fell behind: a freeze, a busy server or a host pause, not freezes alone.
- Findings the product check flagged for you to look at: `testing/Developer/reports/2026-10-16_product_check/report.md`.
- The Factory review loop is paused, not installed (`docs/build/Factory_review_loop.md`); Factory's pull requests come to me through you meanwhile.
- Still open from before: a stronger writer model for develop (card 5), and card 40's hook and rule changes.
- Every decision taken for you: `DECISIONS.md`, rows dated 2026-10-15 and 16. What broke: `LEARNINGS.md`.

### The one next action

Retest the night's cards from `testing/Retest_product_owner.md`. After that, the board's To do column top down: each closed card needs a design agreed with you before it is built again, starting with card 101, where a quoted record sentence ends.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `testing/Developer/reports/2026-10-15_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-16, morning

### What is live

- Develop: `de53c6aa`, deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged overnight: cards 115 (#240), 17 (#241), 94's timeout fix (#246) and 24 (#245).
  - Each passed CI and three independent reviews: one checks the code, one hunts for a wrong answer, a third re-checks with fresh eyes.
  - Each passed the product check on deployed develop at 1280 and 390 (`testing/Developer/reports/2026-10-16_product_check/` and `2026-10-16_product_check_card24/`).
- Closed overnight by your rule, each back in To do with its reviews and final diff on develop: cards 48, 75, 29, 94's lookup, 110, 101, 20 and 15. Why, one row each: `DECISIONS.md`, rows dated 2026-10-15 and 16.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.
- Factory is paused; its brief lists cards 75 and 100. Develop's model settings: `docs/architecture/Model_architecture.md`.

### What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first, the night's four cards on top. The team checked all four on deployed develop.
- Two rules only you can set:
  - Should a question asked after a long server pause be checked like any other? Today develop refuses some of them (cards 84 and 72, `testing/Developer/reports/2026-10-15_card84_72/design.md`).
  - When a sign-in renewal reply cannot be read, should the person stay signed in? (card 75)
- The product check's "needs your eye" findings: `testing/Developer/reports/2026-10-16_product_check/report.md`.
- Still open from before: a stronger writer model for develop (card 5), and card 40's hook and rule changes.
- Every decision taken for you overnight: `DECISIONS.md`, rows dated 2026-10-15 and 16. What broke: `LEARNINGS.md`.

### The one next action

Retest the night's four cards from `testing/Retest_product_owner.md`, then answer the two rules above. After that, the board's To do column top down: each closed card needs a design agreed with you before it is built again, starting with card 101, where a quoted record sentence ends.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `2026-10-15_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-15

### What is live

- Develop: `f3950564`, deployed and checked at 1280 and 390 (`testing/Developer/reports/2026-10-15_product_check/`). Production: `v0.2.0`, tag `cde4f592`. CI is green on develop again.
- Merged 2026-10-15: card 114 (#233, develop's writer priced again, strawberry-graphql 0.327.7), card 35 (#228, merged with V2-35-02 open as card 115) and card 111 (#234, re-split alone).
- Develop's API sets `SYNTH_MODEL=z-ai/glm-5.2`, `GUARD_MODEL` and `PLAN_MODEL=deepseek/deepseek-v4-flash`, `CLASSIFIER_PROVIDER=jev` and `PER_QUERY_COST_CAP_USD=0.25`. litellm's downloaded price map lacks OpenRouter entries today, so prices come from `harness/tiers.py`'s table.
- GitHub also holds open pull requests #230 (card 48, waiting for its redesign) and #223 (skill lessons), and two parked branches: `fix/cards110-111-summary-opening` (card 110) and `fix/card20-isolate-year-place`.
- Locally, besides `develop`: worktrees `~/asu-wt/card48` and `skill` for those pull requests; on the Desktop `asu-card22`, `asu-card56` and `asu-factory-43`, `-43b`, `-44`, `-47`, none removable by the clean-up checks; local branch `fix/card20-isolate-year-place`.

### What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first, today's cards 114, 35 and 111 on top.
- The product check's findings marked "needs your eye": `testing/Developer/reports/2026-10-15_product_check/product_review.md`.
- Still open from before: the guardrail's step 3b, whether develop's writer becomes Opus 5.5 (card 5), card 40's 27 items, pull request #223. Every decision of today: `DECISIONS.md`, rows dated 2026-10-15; what broke: `LEARNINGS.md`.

### The one next action

Build card 94's single-isolate lookup with the SNP-distance scan skipped, your call of 2026-10-15: it is the first card in the board's To do that waits on no design. Its timeout crash and empty-result wording come first (`testing/Developer/reports/2026-10-09_card94/build.md`, "Parked"). Your other calls of today, cards 48, 20, 17 and 115, follow in the board's order.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; today's: `2026-10-15_*`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-09, night

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-09.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `a2bb7732`. Production: `v0.2.0`, tag `cde4f592`.
- Merged 2026-10-09, each behind green CI, a judge, an adversary, one fix round and a fresh verifier, then checked on deployed develop at 1280 and 390: phase 8.7 (#218) and its follow-ups (#229), the guardrail's safe part (#227), cards 19 (#224), 109 (#225), 94 part (#226) and 112 (#231). The checks: `testing/Developer/reports/2026-10-09_product_check_*`.
- Develop's API has `PER_QUERY_COST_CAP_USD=0.25`. OpenRouter: $31.36 left; tonight spent $0.41.
- A command line installed from develop since the evening of 2026-10-08 prints a "redefined" warning per cited record until reinstalled; production's is unaffected.
- GitHub also holds open pull requests #223 (overnight skill lessons), #228 (card 35) and #230 (card 48), and the parked branch `fix/card20-isolate-year-place`.
- Locally, besides `develop`: worktrees `~/asu-wt/card35`, `card48` and `skill` for those pull requests; on the Desktop `asu-card22` (raw review files), `asu-card56` (5 unmerged commits), and `asu-factory-43`, `-43b`, `-44`, `-47` (uncommitted changes from a damaged index, `-43` still partly evicted), none removable by the clean-up checks; local branch `fix/card20-isolate-year-place`.

### What awaits the product owner

- Card 35, #228: merge as it is, or a one-line change and a fresh verifier (V-35-03).
- Card 48, #230: redesign so the classifier judges whether a message names a record (the lead's recommendation), or merge as it is (V-48-04).
- Card 20: a separate extraction call on isolate questions (recommended), or Think extracting with the listed fixes.
- Card 94's single-isolate lookup: keep or trim the 19 s SNP scan (F-3.5-A-05). Card 17: accept two dropped sentences, or another option.
- The guardrail's step 3b; whether develop's writer becomes Opus 5.5 (card 5); card 40's 27 items; pull request #223.
- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`. Every decision taken for you tonight: `DECISIONS.md`, rows dated 2026-10-09; what broke: `LEARNINGS.md`.

### The one next action

Decide #228 and #230, then build cards 110 and 111, the first-sentence pick and the sentence made only of record titles, from `testing/Developer/reports/2026-10-09_product_check_8.7/diagnosis.md`.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests, the cutoff, closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Phase 8.7: `tracker/phase_8.7.md`; each card's reviews: `testing/Developer/reports/2026-10-09_card*`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-09, morning

Last updated: 2026-10-09.

### What is live

- Develop: `599c6e67`. Production: `v0.2.0`, tag `cde4f592`.
- Merged overnight 2026-10-08 to 09, each behind green CI, a judge, an adversary, one fix round and a fresh verifier, then checked on deployed develop at 1280 and 390: cards 71 (#212, with migration 0011), 32 (#214), 36 (#215), 37 (#213, its fix round's case change reverted), 85 (#220) and 51 (#219, its fix round's rewording reverted). The checks: `testing/Developer/reports/2026-10-09_product_check_*`.
- Parked, code under local `parked/` tags, reports kept: the guardrail (84 and 72), card 15's next step, card 101's last slices. Why: the `DECISIONS.md` rows of 2026-10-08.
- OpenRouter: $31.77 left of $36.11; phase 8.7 spent $3.67 of its $20, everything else about $0.66.
- GitHub also holds `phase/8.7-answers-sooner` (open pull request #218) and `feat/8.7-s1` to `s3`, whose work it carries.
- Locally, besides `develop`: worktrees `asu-card22` (raw review files not on develop) and `asu-card56`, `asu-factory-43`, `-43b`, `-44`, `-47` (still downloading from iCloud, unchecked). `asu-audit` and `asu-card99` were checked and removed.

### What awaits the product owner

- Phase 8.7, pull request #218: merge now with A04 and A07 as follow-up cards (the lead's recommendation), or fix them first. With any merge, set `PER_QUERY_COST_CAP_USD=0.25` on develop's API; the permission layer refused the lead's attempt. Whether develop's writer becomes Opus 5.5 is a separate choice: at a true 25-cent bound its repairs are refused on 3 to 19 of 24 bench questions.
- The guardrail's re-split, proposed in its `DECISIONS.md` row.
- Card 40: 27 items, each a yes or no, in `testing/Developer/reports/2026-10-08_card40/itemized_list.md`.
- Closing cards 11 and 12, proposed: neither reproduced since 2026-09-25 and both fixes were reverted; reopen on a failing test query.
- Cards needing a design or decision, from tonight's diagnoses: 17, 20, 29, 33 (D19), 48, 16 (fold into 56), and the `.claude/` and A07 parts of 51 and 85. New cards found: `testing/Developer/reports/2026-10-08_overnight/new_cards.md`.
- After the 8.7 merge: delete `feat/8.7-s1` to `s3` (the lead's tag-and-delete was refused).
- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`. The night's decisions: `DECISIONS.md`, rows dated 2026-10-08.

### The one next action

Decide pull request #218, then build cards 18, 19, 30, 38 and 94 from their diagnoses in `testing/Developer/reports/2026-10-08_overnight/`, which wait on it.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests, the cutoff, closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Phase 8.7: `tracker/phase_8.7.md` on its branch; the night's plan: `testing/Developer/reports/2026-10-08_overnight/plan.md`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-08, morning

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-08.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `29d8d8a0`, the merge of #208. Both Railway services redeploy on every push to `develop`; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- Merged on the night of 2026-10-07 to 08, each behind CI and a fresh verifier finding nothing worse than develop, then its test queries on develop at 1280 and 390: cards 71 part (#203), 54 (#202), 101 part (#204), 103 and 104 (#205), 67 (#207, no live check possible), 59 (#208), and the overnight-development skill (#206). Detail: the done file's session table.
- Not done that night: card 54's warning line for older answers, reverted for false alarms; card 67's dated first version, redone; the golden run, at the owner's choice.
- The data engineering repository is released as `v1.1.0`, through its own release workflow.
- GitHub holds `develop`, `production` and phase 8.7's four branches (`feat/8.7-s1` to `s3`, `phase/8.7-answers-sooner`), which wait on the OpenRouter top-up.
- Locally, besides `develop`: nine old worktrees on merged branches, unchecked for untracked work because iCloud evicted their files: `asu-audit`, `asu-card22`, `asu-card56`, `asu-card56-r3`, `asu-card99`, `asu-factory-43`, `asu-factory-43b`, `asu-factory-44`, `asu-factory-47`.
- Factory did no work on 2026-10-08; its next cards stay 75, 24 and 100 (`docs/build/Factory_onboarding.md`).

### What awaits the product owner

- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`, newest first, cards 59, 67, 103 and 104, 101 part, 54 and 71 part on top.
- The guardrail design's seven yes or no questions: `testing/Developer/reports/2026-10-08_guardrail_design/design.md`.
- The "High-risk claim" tag on a reopened answer (card 71): approved, a migration built in a daytime session with you present.
- Card 40: the itemized hook and always-loaded rule changes, now with one git-workflow line (tags count, every session end, both repositories).
- The decisions taken for you overnight: `DECISIONS.md`, rows dated 2026-10-08.
- The nine evicted worktrees above: once iCloud restores them, the lead checks each and removes what clears all three checks.
- From before: decisions D5 to D21 in `testing/Board_plan.md`, the OpenRouter top-up, the privacy hooks and `railway link` on the second laptop.

### The one next action

Read the night's loose ends in `testing/UI_fixes_done.md` ("Where we stopped"), then build from the board's To do column top down: card 94's remaining isolate work next, since card 56 waits on a design with you.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The build order and progress: `testing/Board_plan.md`
- Retests, the cutoff and every closed item: `testing/UI_fixes_done.md`; older history in `testing/UI_fixes_archive.md`
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- Factory's brief: `docs/build/Factory_onboarding.md`
- Work outside the board: `testing/Future.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry and the sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-07

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-07.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `fde37ddf`, the merge of #199. Both Railway services redeploy on every push to `develop`; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`, released 2026-09-20. Nothing since is on it. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- The overnight run of 2026-10-06 to 07 merged the readability pass (#196) and cards 22, 23 and 102 (#197 to #199), each behind CI and a fresh verifier. What it did and why: the done file's session table and `DECISIONS.md` rows dated 2026-10-06 and 2026-10-07.
- Factory works every day from `docs/build/Factory_onboarding.md`; its next cards are 75, then 24, then 100. Paste-in prompt: "Read docs/build/Factory_onboarding.md in full, then build card 75, one pull request; then card 24, then card 100." The lead verifies each pull request before merging.
- Kept on GitHub: `fix/card101-copied-cuts` (card 101, parked); `feat/8.7-s1` to `s3` and `phase/8.7-answers-sooner` (phase 8.7); `fix/card72-r10-guardrail` and `fix/card84-r10-sound-parts` (guardrail reference).
- Fourteen local worktrees wait for the morning clean-up, each on a merged or pushed branch (`git worktree list`): tonight's six and eight from 2026-10-06. Check each for uncommitted work before removing it. GitHub holds only develop, production and the kept branches.

### What awaits the product owner

- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`, newest first, cards 102, 23 and 22 on top. Product checks on develop passed them, except that an answer over 50 citations reopens with only 50 (card 54).
- Card 101: whether to try dropping the whole sentence whenever a copied cut is held back, on its parked branch (`DECISIONS.md`, 2026-10-07).
- The decisions the lead took on your behalf overnight, each a `DECISIONS.md` row: the readability merge bar, the withdrawn board-cell move, the last rounds of cards 22 and 101, and card 102.
- Card 40: the itemized list of hook and always-loaded rule changes, each for your yes or no. Nothing in the security layer changed overnight.
- From before: decisions D5 to D21 in `testing/Board_plan.md` (taken as recommended unless you object), the OpenRouter top-up phase 8.7 waits on, the MedGen encoding note to NCBI, and the privacy hooks and `railway link` on the second laptop.

### The one next action

Ask the owner card 101's question, then build from the board's To do column top down: card 56's remaining cases with a design agreed first, per `testing/UI_fixes_done.md`, "Next, in order". Review Factory's pull requests as they arrive.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The build order and progress: `testing/Board_plan.md`
- Retests, the cutoff and every closed item: `testing/UI_fixes_done.md`; older history in `testing/UI_fixes_archive.md`
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- Factory's brief: `docs/build/Factory_onboarding.md`
- Work outside the board: `testing/Future.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry and the sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`

## Handoff as of 2026-10-05, night

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-05.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `042985a3`, the merge of #175. Both Railway services redeploy on every push to `develop`. Nothing is built between sessions; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`, released 2026-09-20. Nothing since is on it. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- The gate for a change is the test queries document, run by agent runners on develop; the golden run is an alarm only (`DECISIONS.md`, 2026-10-05).
- The build order is `testing/Board_plan.md`: root causes, waves, the owner's decisions. Its Progress list says where the waves stand.
- One development agent is active. Factory's trial was paused on 2026-10-05; its lane (cards 43, 44, 18, 23, 24, 25, 47, the rest of 61) is provisional and pending. Merge one pull request at a time; several at once starve CI (`LEARNINGS.md`, 2026-10-05).
- Kept on GitHub by the owner's choice: `feat/8.7-s1` to `s3` and `phase/8.7-answers-sooner` (phase 8.7; resume plan `testing/Developer/reports/2026-10-05_phase_8.7_resume/plan.md`), and `fix/card72-r10-guardrail`, `fix/card84-r10-sound-parts` (guardrail reference).

### What awaits the product owner

- Retests: the board's Retest column, newest first, each card naming its test query.
- Whether Factory shares tasks, and with what guidance: the first question of the next session. Its eight cards stay pending until then.
- A top-up of the OpenRouter account before phase 8.7 (about $38.50 left against its approved $60; develop's live answers draw on it too).
- Decisions D5 to D21 in `testing/Board_plan.md` are taken as recommended unless the owner objects.
- A note to NCBI about the broken encoding in MedGen's Muir-Torré syndrome record, drafted by the lead for the owner to send.
- Unchanged from earlier: the privacy hooks and `railway link` on the second laptop.

### The one next action

First, before any build work, ask the owner one question: "Do you want Factory to share tasks with me this session, and if so, with what guidance?" If yes, give it its lane per the guidance and merge its pull requests through the one queue; if no, its cards stay pending.

Then: diagnose why the SARS-CoV-2 question still answers about the disease SARS on develop though card 56's fix passed locally (card 56 at the top of To do; evidence `testing/Developer/reports/2026-10-05_final_test_queries/results.md`). Then card 99's measurement, then phase 8.7 once the account is topped up.

How to start a session: read this file, then `git status --short` and `git worktree list` (expect the main checkout on `develop` alone), then the board's Retest and To do columns. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The build order and progress: `testing/Board_plan.md`
- The cutoff and every closed item: `testing/UI_fixes_done.md`, from "Where we stopped"
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- Work outside the board: `testing/Future.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry: `tracker/Living_documents.md`

## Handoff as of 2026-10-05, evening

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-05.

### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop: `042985a3`, the merge of #175. Both Railway services redeploy on every push to `develop`. Nothing is built between sessions; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`, released 2026-09-20. Nothing since is on it. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- The gate for a change is the test queries document, run by agent runners on develop; the golden run is an alarm only (`DECISIONS.md`, 2026-10-05).
- The build order is `testing/Board_plan.md`: root causes, waves, the owner's decisions. Its Progress list says where the waves stand.
- Two development agents: this lead (answer path, the board, the plan, the one merge queue) and Factory (screens and wording, cards 43, 44, 18, 23, 24, 25, 47 and the rest of 61, on `factory/` branches). Merge one pull request at a time; several at once starve CI of runners (`LEARNINGS.md`, 2026-10-05).
- Parked on GitHub: `feat/8.7-s1` to `s3` and `phase/8.7-answers-sooner` (phase 8.7, resume plan in `testing/Developer/reports/2026-10-05_phase_8.7_resume/plan.md`); `fix/card72-r10-guardrail` and `fix/card84-r10-sound-parts` (guardrail, returns as an agreed design).

### What awaits the product owner

- Retests: the board's Retest column, newest first, each card naming its test query.
- A top-up of the OpenRouter account before phase 8.7 (about $38.50 left against its approved $60; develop's live answers draw on it too).
- Decisions D5 to D21 in `testing/Board_plan.md` are taken as recommended unless the owner objects.
- A note to NCBI about the broken encoding in MedGen's Muir-Torré syndrome record, drafted by the lead for the owner to send.
- Unchanged from earlier: the privacy hooks and `railway link` on the second laptop.

### The one next action

Diagnose why the SARS-CoV-2 question still answers about the disease SARS on develop though card 56's fix passed locally (card 56 at the top of To do; evidence `testing/Developer/reports/2026-10-05_final_test_queries/results.md`). Then card 99's measurement, then phase 8.7 once the account is topped up.

How to start a session: read this file, then `git status --short` and `git worktree list` (expect the main checkout on `develop`, plus any Factory worktrees, which are not ours to touch), then `git ls-remote --heads origin 'factory/*'` and `gh pr list` for Factory's work (move its cards on the board as they start and land), then the board's Retest and To do columns. At the end, run `/phase-checkpoint`, then `/ship`.

### Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The build order and progress: `testing/Board_plan.md`
- The cutoff and every closed item: `testing/UI_fixes_done.md`, from "Where we stopped"
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- Work outside the board: `testing/Future.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry: `tracker/Living_documents.md`

## Handoff as of 2026-10-04

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-05.

#### Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

### What is live

- Develop's product code: card 73's merge, #139 at ca85a03d. `git log --merges --first-parent develop` lists what came before.
- The gate for a change is the test queries document, run by agent runners; the golden run is an alarm only (`DECISIONS.md`, 2026-10-05).
- Develop's API carries `CLASSIFIER_PROVIDER=jev` and `SYSTEM_DAILY_CAP_USD=25`. Both Railway services redeploy on every push to `develop`.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing since is on it. The changelog fix, `testing/Future.md` row 53 (formerly board card 65), lands first.
- `/ship` runs the public-repository leak scan before every push. Open items: `testing/Developer/reports/2026-09-29_ship_leak_scan/verifier.md`.
- The lead merges into develop with `gh pr merge --merge --admin --delete-branch` once checks pass (`DECISIONS.md`, 2026-09-29).
- Test sign-ins are fresh accounts made on develop, kept only in the lead's scratch folder (`LEARNINGS.md`, 2026-09-29).
- Nothing is built between sessions. Check `gh run list --branch develop --limit 3` before trusting CI.

Parked branches, all on GitHub. Pick one up with `git worktree add .claude/worktrees/<name> <branch>`; the full table is in the history file, 2026-09-30.

- `fix/card72-r10-guardrail` and `fix/card84-r10-sound-parts`: stopped by the owner; return only as an agreed design.
- `feat/8.7-s1`, `feat/8.7-s2`, `feat/8.7-s3`: phase 8.7's three builders, unmerged. Plan in `tracker/phase_8.7.md`.

### What awaits the product owner

- Approve, through the permission system, making the leak scan's email findings warnings rather than blocks (`DECISIONS.md`, 2026-09-30).
- The privacy pre-commit and commit-msg hooks on the second laptop. Until then, check every commit there by hand.
- `railway link` on the second laptop, choosing `system3-search-agent-develop`.
- Three cards in the Retest column after the 2026-09-29 batch retest (`testing/Developer/reports/2026-09-29_retest/`).

### The one next action

Build from `testing/Board_plan.md`, wave by wave. Wave 0, cards 88, 89, 57 and 17, is on `fix/card88-89-answers-survive` in `.claude/worktrees/card88-89`; wave 1's six small builds start in parallel. Decisions D5 to D21 in the plan carry the lead's recommendation and are taken unless the owner objects.

How to start a session: read this file, then `git status --short` and `git worktree list` (expect `develop` alone locally), then the board's Retest and To do columns. At the end, run `/phase-checkpoint`, then `/ship`. A new laptop starts with the setup steps in `docs/build/Handoff_history.md`.

### Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The cutoff and every closed item: `testing/UI_fixes_done.md`, from "Where we stopped"
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Work outside the board: `testing/Future.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- The golden run: `.claude/skills/bossman-mode/reference/Product_review.md`, Step 2
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a phase or card runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry: `tracker/Living_documents.md`

## Handoff as of 2026-09-30

The full `HANDOFF.md` rewritten at the 2026-09-30 checkpoint, apart from the setup steps above, with its headings moved down one level.

What a fresh session needs, and nothing else. Rewritten in place at every `/phase-checkpoint`, never appended to. It states no fact another file owns beyond the pointers in the last section; history goes to `requirements/Plan.md`'s Revision history and `testing/UI_fixes_done.md`, never here.

Last updated: 2026-09-30.


### What is live

- Develop's product code is card 73's merge, #139 at ca85a03d: a crashed search writes its reason and trace id to the log. Before it, card 53 (#134) and card 62 (#133): truthful pages, a first-try install and `s3`'s trust line. `git log --merges --first-parent develop` lists what came before.
- Card 63 passed test queries 100 and 67 on develop on 2026-09-29, and its golden run answered 98 of 150, below its floor of 101. The owner kept card 63 and accepted that run; the floor for the next change stays 101 (`DECISIONS.md`, 2026-09-29). The lost runs are guard-model timeouts and a crash that logs no reason, now cards 72 and 73.
- Golden runs and test queries sign in with fresh test accounts made on develop; their sign-ins live only in the lead's scratch folder, never committed. A new session makes its own the same way (`LEARNINGS.md`, 2026-09-29).
- Develop's API carries `CLASSIFIER_PROVIDER=jev` and `SYSTEM_DAILY_CAP_USD=25`. Both Railway services redeploy on every push to `develop`.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing since is on it.
- `/ship` runs a public-repository leak scan before every push, in both repositories (`.claude/skills/ship/scripts/check_public_leaks.py` here, `scripts/check_public_leaks.py` in data engineering): a secret blocks the push, and the owner's local private-name check runs or the scan stops. Its open items: `testing/Developer/reports/2026-09-29_ship_leak_scan/verifier.md`.
- Merging into develop: the lead merges with `gh pr merge --merge --admin --delete-branch` once checks pass; develop's ruleset stays for outside contributors (`DECISIONS.md`, 2026-09-29). The harness's auto-mode check may still ask for the owner's approval in the conversation.
- Releases: the release job tags `production` and never pushes to it. Card 65 fixes the release fix's open findings before the next release.
- Parked tags, on the first laptop only: `parked/phase-8.4-2026-09-25`, `parked/phase-8.8-snippets-2026-09-25` and `parked/verify-facts-118-2026-09-27`.
- Nothing is being built between sessions. Check `gh run list --branch develop --limit 3` before trusting that CI is green.

#### Parked work

Every branch below is on GitHub. To pick one up: `git worktree add .claude/worktrees/<name> <branch>`. Delete each on both sides when it merges or is dropped (`git-workflow`).

| Work | State | Where | Not done |
|---|---|---|---|
| R-10 and card 72's first guard fix: a hedged guard request, R-10's eight flags | Built and reviewed; the fresh verifier found an off-topic question could be admitted in a slow spell (F-72-V08), so the owner chose not to merge | `fix/card72-r10-guardrail` at 1961518c; records in `testing/Developer/reports/2026-09-29_card72/` | Reused by card 84 (R-10's sound parts) and card 72's redesign; not merged as is |
| Card 84: R-10's guardrail fixes alone, no hedge | Built; its adversary found an off-topic question and a disguised injection admitted under a rate limit (F-84-A05, A07), so the owner stopped it | `fix/card84-r10-sound-parts` at 5a0adc02; records in `testing/Developer/reports/2026-09-29_card84/` | Returns only as a design agreed with the owner first |
| Phase 8.7 builder A: the first sentence answers the question | Built, not reviewed; its unit suite never finished | `feat/8.7-s1` at 32e5945e | Review its own diff, run the suite, commit it properly |
| Phase 8.7 builder B: records on screen while the summary is written | The `placement` field (1e030148); the screen work, not reviewed | `feat/8.7-s2` at cb407508 | The screen and App-level Stop tests, reshaping `App.stopUntilAnswer.test.tsx`, the mutation reds, the gates |
| Phase 8.7 builder C: shorter waits, the Opus writer | Six commits, every mutation red | `feat/8.7-s3` at da2c04f6 | Its final gates |
| Phase 8.7 as a whole | Tickets, findings and every decision | `tracker/phase_8.7.md`, branch `phase/8.7-answers-sooner` | Merge the three builders into the phase branch, then the judge, the adversary and one fix-and-verify; then the golden run at 101 or more plus test queries 1, 2, 17, 72 and 98, reverting on failure; then the product review. At merge, set `PER_QUERY_COST_CAP_USD=0.25` on develop. Up to 12 dispatches |

The reviewers' probes from 2026-09-27 are gone, so any resumed phase 8.7 reviewer reruns its own.

### What awaits the product owner

- Approve, through the permission system, making the leak scan's email findings warnings rather than blocks, as you asked on 2026-09-30; the permission layer refused the change as a security weakening, so emails still block (`DECISIONS.md`, 2026-09-30).
- The privacy pre-commit and commit-msg hooks on the second laptop, from your private notes. Until they are in, every commit there is checked by hand.
- `~/.local/bin/railway link` on the second laptop, choosing `system3-search-agent-develop`, so `/ship` can confirm deploys.
- Retests: three cards left in the Retest column after the batch retest of 2026-09-29, each needing the owner's eye (`testing/Developer/reports/2026-09-29_retest/`). The owner approved the 39 that passed; the 9 that failed are cards 86 to 94 in To do.

### The one next action

The owner picks the next piece from the top of To do: cards 86 to 94 failed the batch retest of 2026-09-29, each needing a diagnosis first, and phase 8.7 is parked on its branches. Guardrail work (cards 72 and 84) returns only as a design agreed with the owner first. One piece at a time, carried to done (`DECISIONS.md`, 2026-09-29).

### Where the facts live

| Question | Owner |
|---|---|
| What is not started, being built, or live awaiting retest | `testing/UI_fix_plan.md`, the board |
| The cutoff, the ordered next actions, what is parked and why, every closed item | `testing/UI_fixes_done.md`, starting at "Where we stopped" |
| The exact queries to type and what a person should see | `testing/Test_queries_and_workflows.md` |
| Phase 8.7's tickets, findings, decisions and where each builder stopped | `tracker/phase_8.7.md` |
| Phases 8.6 and 8.10, and earlier numbered phases | `tracker/phase_N.M.md`; `tracker/BOARD.md` is frozen at 6.2 |
| Phase 8.9's plan, not yet opened | `tracker/phase_8.9.md` |
| Card 63's reviews, fix round and verifier | `testing/Developer/reports/2026-09-27_card63/review.md` |
| Card 58's reviews | `testing/Developer/reports/2026-09-27_card58_stop/review.md` |
| The release fix's reviews and its open findings | `testing/Developer/reports/2026-09-27_release_fix/review.md`, card 65 |
| Which model does what, and how the calls hand off | `docs/architecture/Model_architecture.md` |
| The golden run and its floor | `.claude/skills/bossman-mode/reference/Product_review.md`, Step 2; the owner set 101 for card 63 and phase 8.7 (`DECISIONS.md`, 2026-09-27) |
| The remaining work outside the board | `testing/Future.md` |
| Which documents the session-closing skills keep current | `tracker/Living_documents.md` |
| Why something was decided | `DECISIONS.md`, newest rows last |
| What broke and what fixed it | `LEARNINGS.md` |
| The dated narrative of every phase and session | `requirements/Plan.md`, Revision history |
| The plain-language state, for someone outside the build | `PROGRESS.md` |
| How a phase or a card runs | `.claude/skills/bossman-mode/SKILL.md` and its `reference/` files |
| How a release is cut | `docs/build/Release_flow.md` |

How to start: read this file, then `git status --short` and `git worktree list`. Expect `develop` alone locally, on every laptop, with the parked branches listed by `git branch -r`. Then read the board's Retest and To do columns. Run `/phase-checkpoint` then `/ship` at the session's end.
