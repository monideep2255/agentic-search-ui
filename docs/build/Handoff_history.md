# Handoff history

What `HANDOFF.md` used to say. `HANDOFF.md` holds only the current state, capped at about 4 KB, so a fresh session loads little. At every rewrite, `/phase-checkpoint` moves the outgoing version here, verbatim, under a dated heading, newest first. Nothing here is current: a statement in this file was true on its heading's date. For what is true now, read `HANDOFF.md`.

Last updated: 2026-10-07.

## Table of contents

- [Starting on another computer](#starting-on-another-computer)
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
