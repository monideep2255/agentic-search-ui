# Factory onboarding

The brief for Factory, the second development agent on this repository, written by the lead development agent on 2026-10-06 when the product owner restarted the trial that was paused on 2026-10-05. Read all of it before your first change: it is the whole of what you need to start.

## Table of contents

- [Who is who](#who-is-who)
- [What this product is](#what-this-product-is)
- [Read before your first change](#read-before-your-first-change)
- [Your lane](#your-lane)
- [Your cards, in order](#your-cards-in-order)
- [How one card runs](#how-one-card-runs)
- [Checks before you push](#checks-before-you-push)
- [The pull request](#the-pull-request)
- [Hard rules](#hard-rules)
- [House style for everything you write](#house-style-for-everything-you-write)
- [When you are stuck](#when-you-are-stuck)

## Who is who

| Role | Who | Owns |
|---|---|---|
| Product owner | The person who runs this project | Every product decision, every retest verdict, scope, cost, anything on the security layer. Their verdict closes a card |
| Lead | The main development agent | The answer path (`src/system_03_search_agent/core/`, `synthesis/`, `harness/`), the board, `DECISIONS.md`, `HANDOFF.md`, the merge queue, the review rounds on your pull requests |
| You, Factory | The second development agent | The cards in [Your cards, in order](#your-cards-in-order), each in your own worktree and branch, ending in a pull request |

You and the lead cannot message each other. You talk through files and the product owner: your pull request body and your report file reach the lead; a question for a decision goes to the product owner.

## What this product is

A biomedical search engine for researchers, clinicians and students. A person types a question; an agent answers it from NCBI's data with a citation on every claim. The loop is Guardrail, Think, Plan, Act, Write, over three data layers: a read-only knowledge graph, live NCBI APIs, and enrichment APIs. The web app is React with MUI in `frontend/`; the API is FastAPI in `src/system_03_search_agent/`.

Two things matter more than anything else here:

- Trust. Every fact links to its source record. A confident wrong record is worse than a missing one.
- The person typing the question. Every choice is made from their chair: what do they see today, what would they want, and would they feel deceived by the trade-off. Say a choice in their words ("a long variant name wraps on a phone"), never only in engineering terms.

`develop` deploys automatically to the develop app on every merge. `production` moves only by a release the product owner approves. The repository is public: everything you commit, including commit messages, is world-readable and permanent.

## Read before your first change

In this order. The rules under `.claude/rules/` are written for another agent harness, where they load by themselves; under Factory none of them loads unless you read it, and none of this repository's automatic safety hooks runs for you either. So reading them is the enforcement.

| # | File | Why |
|---|---|---|
| 1 | `AGENTS.md` | The project in one page |
| 2 | `HANDOFF.md` | What is live today and what the lead is working on |
| 3 | `.claude/rules/public-repository-privacy.md` | What must never be committed |
| 4 | `.claude/rules/git-workflow.md` | Branches, commits, pull requests |
| 5 | `.claude/rules/writing-style.md` | House style for every word you write |
| 6 | `.claude/rules/file-protection.md` | What you may not delete or touch |
| 7 | `.claude/rules/decide-from-the-users-chair.md` | How choices are made here |
| 8 | `.claude/rules/production-standards.md` | The gates code must pass |
| 9 | `.claude/rules/design-consistency.md` | For any screen: the design system is the source of truth, never invention |
| 10 | `.claude/rules/supply-chain-security.md` | Before any `npm` or `pip` command |
| 11 | `testing/UI_fix_plan.md`, the rows of your cards | Each card's own words and evidence |
| 12 | The rest of `.claude/rules/`, quickly | They are short; skip none that names a file you are about to change |

Skills under `.claude/skills/` are plain instructions you can follow by reading their `SKILL.md`; slash commands do not work for you. The two you will use: `.claude/skills/verify/SKILL.md` (prove a screen at 1280 and 390 pixels) and `.claude/skills/ship/SKILL.md` (only its checks; you never push to `develop`).

## Your lane

You own:

- `frontend/` (source, unit tests, end-to-end specs), except `package.json` and `package-lock.json`.
- The design system files under `docs/build/design/design-system/`, for card 47.
- For card 61, `src/system_03_search_agent/adapters/cli/` and `adapters/mcp/` and their tests.
- Your report folder for each card, `testing/Developer/reports/<date>_factory_card<N>/`.

You never edit, even to fix a typo:

- `src/system_03_search_agent/core/`, `synthesis/`, `harness/`, `tools/`, `guardrail/`: the answer path, the lead's lane. Two agents in one function collide.
- `.claude/` (rules, skills, hooks, settings), `.github/`, `CLAUDE.md`, `AGENTS.md`.
- `testing/UI_fix_plan.md`, `testing/Board_plan.md`, `testing/UI_fixes_done.md`, `DECISIONS.md`, `HANDOFF.md`, `LEARNINGS.md`, `PROGRESS.md`, `requirements/`. The lead is the single writer of these. Put what they need in your pull request body instead (see [The pull request](#the-pull-request)).
- `reference/`, which is read-only material from another repository.
- `package.json`, `package-lock.json`, `pyproject.toml`, `requirements*.txt`: a new or changed dependency needs the product owner's approval first.

## Your cards, in order

One card at a time. Finish one, open its pull request, then start the next; do not hold several open. The order is what a person notices first.

| Order | Card | What the person sees today | Done when | Dial |
|---|---|---|---|---|
| 1 | 43 | On a phone, an answer that cites a long variant name scrolls sideways: the page is 449 pixels wide on a 390 pixel screen, because `NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG` does not wrap and pushes citation chip 10 off the screen. Evidence: `testing/Developer/reports/2026-09-26_verify_home_and_answer/report.md`, the answer at 390, and `answer_390.png` beside it | At 390 pixels no answer screen scrolls sideways (`document.documentElement.scrollWidth` is at most the window width) with that name in the answer text and in the sources; the name wraps inside its own block; every citation chip stays on screen; nothing changes at 1280. An end-to-end spec with that name in a fake answer proves it at 390 and goes red without your fix | 1 |
| 2 | 44 | Two controls are below the 4.5 contrast minimum: the "Take the tour" button, `#0071bc` on `#e7eef6`, 4.39; a green citation chip, `#2e8540` on `#f0f0f0`, 4.05. Same report, the axe scan at 390 | Both reach 4.5 or more using colours that already exist as tokens in `frontend/src/theme.ts` and `docs/build/design/design-system/foundations/colors.html`. The accessibility end-to-end spec passes and the axe scan at 390 shows no color-contrast violation on the home and answer screens. If no existing token passes, stop and ask the product owner: a new colour is their decision | 1 |
| 3 | 47 | The design prototype still draws the old navy home hero and full-width example rows, which the product owner replaced on 2026-09-12 with a light home page and white rounded example chips (commit cbb04cc, `DECISIONS.md` 2026-09-26). So every screen check flags the live home page as wrong | `docs/build/design/design-system/prototype/app.html` and `screens/home.html` draw the home page as the app does today: the light canvas, ink text, the bordered white search bar, white rounded example chips, using the design system's own tokens. Change only those two differences; list the other differences the report names (two answer modes against three, the arrow submit button, the tour invitation) in your report for the product owner, unchanged | 1 |
| 4 | 61 | Ten small edge cases in the command line and the MCP bridge, F-8.10-V01 to V10 in `tracker/phase_8.10.md`: for example a comment of only an invisible character erases an earlier rating, a bracketed year counts as a missing citation, an unsafe sign-in file prints its own path | Write a plan first in your report folder, `plan.md`: each finding, its file, the fix in one line, its test. Then build V01 to V05, V07 and V08, one commit per finding, each with a test that goes red without its fix. Leave V06 (public wording), V09 and V10 (marked unsure) unbuilt and list each in the pull request as a question for the product owner, with your recommendation | 2 |

Dial 1 means a copy, layout or design-file change: your build, your checks, the lead's merge, then the product owner's retest. Dial 2 means runnable behaviour: the lead also runs a judge and an adversary review on your pull request before merging, and you fix what they find in one round.

Not yours now, so leave them alone even though the board once listed them in your lane:

| Card | Why it waits |
|---|---|
| 18, 23 | Their wiring is in `core/graph.py`, the answer path the lead is changing this week; 23 also waits on a product owner decision |
| 24 | Waits on the product owner's decision of where the language toggle goes |
| 25 | Installs a new package, the public design system base; that needs the product owner's approval and a supply-chain review first |

## How one card runs

1. Start from the newest `develop`, in your own worktree beside the main checkout, never in the main checkout itself:

   ```bash
   git fetch origin
   git worktree add -b factory/card43-wrap-long-names ../asu-factory-43 origin/develop
   ```

   Branch names: `factory/card<N>-<short-description>`.
2. Install the frontend from the committed lockfile, which adds nothing new: `cd frontend && npm ci`. Never `npm install <package>`, never edit `package.json` or `package-lock.json`.
3. Read the card's evidence, then find the surface in the design system before styling anything (`design-consistency`: `prototype/app.html` first, it holds every 390 pixel rule).
4. Write the test first where you can, then the fix. A test proves something only if it fails without the fix: break the one property your fix adds, see it go red, put it back. Reverting the whole change does not count, because a test usually then fails on a missing name before it checks anything.
5. Run the checks in [Checks before you push](#checks-before-you-push).
6. Write your report, `testing/Developer/reports/<date>_factory_card<N>/report.md`: what the person sees now, in their words; files changed; the tests and what turned each red; the check results; screenshots at 1280 and 390 named `<screen>_<width>.png`; what you did not cover. No absolute local paths anywhere in it; write `<repo-root>`.
7. Commit, push your branch, open the pull request ([The pull request](#the-pull-request)), and tell the product owner it is ready. Then stop work on that card. The lead merges, one pull request at a time; several at once starve CI.
8. After it merges, remove your worktree (`git worktree remove ../asu-factory-43`) and start the next card from the new `develop`.

## Checks before you push

The same commands CI runs. Run every one that applies; paste the result lines into the pull request.

| When | Command, from the worktree root |
|---|---|
| Frontend changed | `cd frontend && npm run build && npm test` |
| A screen changed | `cd frontend && npx playwright test e2e/<the specs you touched> e2e/accessibility.spec.ts`. These start the real backend with a fake model at fixed ports 5273 and 8931; the backend needs the main checkout's Python environment, `<repo-root>/venv`, on your PATH |
| Python changed (card 61) | `bash .github/gates/gate03_lint.sh` (ruff over the whole repository), `bash .github/gates/gate02_import_order.sh`, `bash .github/gates/gate04_unit_suite.sh` (the whole suite, no path). Six tests need a local Postgres and may fail on a machine without one; name them, do not hide them |
| Any markdown changed | `python3 tracker/check_doc_drift.py --check` |
| Always, last | `python3 .claude/skills/ship/scripts/check_public_leaks.py --base origin/develop`. A secret finding blocks the push. It reads every commit and every untracked file |

Screenshots: capture the changed screens at 1280 and 390 pixels against your local stack, following `.claude/skills/verify/SKILL.md` and its script `.claude/skills/verify/scripts/capture.mjs`. After the merge the product owner and the lead check the deployed develop app, so a local screenshot is your evidence, not the final word.

Live questions on the develop app cost real model spend from an account that is running low. Ask at most three live questions per card, and none if the fake-model specs prove the change.

## The pull request

Into `develop`, from your `factory/` branch, with `gh pr create --base develop`. Never merge it yourself; the lead merges.

Title: a Conventional Commit subject, sentence case after the colon, for example `fix(web-ui): Wrap a long variant name on a phone instead of scrolling sideways`.

Body, in this order:

```markdown
Card <N>: <the card's words>.

What the person sees now:
- <one line per change, in their words>

Checks:
- <each command and its result line>

Report: `testing/Developer/reports/<date>_factory_card<N>/report.md`

For the lead to log (DECISIONS.md rows, board, learnings):
- <each choice between alternatives: what you chose, what you did not, why>
- <anything that broke and cost you more than five minutes, and what fixed it>

Not covered:
- <what you did not check>
```

## Hard rules

These are the ones a newcomer breaks. Each has bitten this project before.

- Never add a `Co-authored-by` line, or any trailer, to a commit or pull request. This repository forbids them. If your tooling adds one by default, remove it before committing.
- Commit as the repository's configured identity, the GitHub noreply address. Never a work address.
- Conventional Commits: `<type>(<scope>): <Description in sentence case>`. Types: feat, fix, docs, chore, refactor, test, ci, security. One logical change per commit. No emoji.
- Stage files by name. Never `git add -A` or `git add .`.
- Never `git push --force`, never amend a pushed commit, never `--no-verify`. The git hooks block local file paths in commits and messages; if one blocks you, fix the content.
- Never commit an absolute or home-relative path, a secret, a person's name or email, a real user's query, or anything from the owner's employer. Screenshots and logs are where paths leaked before: check them.
- Never push to `develop` or `production`. Never deploy, never change a setting on the hosting service, never run a database migration, never write to the knowledge graph.
- Never delete a file you did not create without saying so in the pull request.
- No hardcoded colour: read tokens from `frontend/src/theme.ts`. When the design system and `theme.ts` disagree, report it rather than resolving it silently.
- Text in the app never belittles a reader or names who they are. It says what a mode gives, never who it is for.
- Never write a word list or rule in code to make a judgement a classifier model should make. (Mostly the lead's lane, but it applies to you in card 61 too.)

## House style for everything you write

Reports, commit messages, pull request bodies and comments in code:

- Sentence case in headings and titles.
- No em dashes or en dashes, and no hyphen used as a dash. Use commas, colons or separate sentences.
- No bold text. Use "Label: description".
- Three or more facts a reader would compare go in a table or a list, not a paragraph.
- A document with three or more `##` sections gets a "Table of contents" list after its intro.
- Never name an LLM vendor or model product in prose.
- Write "repository", never "repo".
- Short sentences, active voice, no buzzwords, no "consider" or "look into".

## When you are stuck

Stop and ask the product owner, one question at a time, with your recommendation first and each option's cost in plain words, when:

- A fix needs a file outside your lane, a new dependency, a new colour, or new public wording.
- A check fails for a reason you cannot explain after one honest attempt.
- The card's evidence and what you see on screen disagree.

Do not guess and do not widen the change to get around a blocker. A smaller pull request that says plainly what it left undone is worth more here than a large one that surprises the reviewers.
