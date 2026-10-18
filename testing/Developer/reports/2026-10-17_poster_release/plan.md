# Poster release plan

The plan for 2026-10-18, the last working day before the innovation day poster, decided by the product owner on 2026-10-17 (`DECISIONS.md`): no new features; release develop to production, set its limits for a crowd, and verify the questions a visitor will try. Visitors scan a QR code that opens the production web app.

## Table of contents

- [Where things stand](#where-things-stand)
- [The day, in order](#the-day-in-order)
- [The owner's four calls](#the-owners-four-calls)
- [Demo questions](#demo-questions)
- [Rollback](#rollback)
- [Not tomorrow](#not-tomorrow)

## Where things stand

| | Production | Develop |
|---|---|---|
| Commit | `v0.2.0`, tag `cde4f592`, released 2026-09-21 | `38158991`, product commit `6935a0a3` |
| Health on 2026-10-17 | `/health` answers, `app_env` production | Answers; median 13.8 s in card 125's product check |
| Gap | 264 merged pull requests behind develop, including four database migrations (0008 to 0011) | Nothing in flight; 61 retest rows wait for the owner |

- Web address for the QR code: `https://search-agent-web-production.up.railway.app`.
- The release procedure: `docs/build/Release_flow.md`, "The release procedure".
- Known items a visitor could meet, all on the board: "SARS CoV-2" typed with a space (card 56), a CFTR Researcher answer with no summary or note (card 128), an occasional answer near 20 s.

## The day, in order

1. Morning, the owner: retest the top rows of `testing/Retest_product_owner.md` (card 125 and the night of 16 to 17 October).
2. The owner's four calls, below, each asked on its own.
3. The lead: cut `release/<version>` from develop's tip, open a pull request into `production`, wait for all CI gates, merge with a merge commit (never squash).
4. Production redeploys; its start command runs `alembic upgrade head` (the four migrations) before the app starts. Confirm `/health` reads `app_env: production`, and both services' deploys reach SUCCESS.
5. Merge the release job's back-merge pull request into develop.
6. The demo questions below, five runs each on production at 1280 and 390 pixels, by the product reviewer, in a dated report folder. A question that fails is dropped from the poster's list, not fixed tomorrow.
7. The QR code to the production web address, checked from a phone.

## The owner's four calls

| # | The call | The lead's recommendation |
|---|---|---|
| 1 | Release develop's tip as it stands, with retests still open | Yes: it is the most tested build, and nothing is in flight |
| 2 | Production's settings match what develop's code needs (the decision model's provider and key, the writer model, the cost caps). The owner reads the variable names in the Railway dashboard, or lets the lead read them knowing the tool returns values | The owner checks them in the dashboard, so no secret value enters a session |
| 3 | The crowd limits for the event: `ANON_DAILY_RUN_CAP` (all guests together, runs per day; the example file says 200) and `SYSTEM_DAILY_CAP_USD` (develop runs at $25) | Sized from the expected visitors and the measured cost of about a cent per run; set back after the event |
| 4 | The live migration: alembic 0008 to 0011 run once against production's database when the release deploys | Yes, with the downgrade order below written down first |

## Demo questions

Candidates, each with a known good answer on develop; the product reviewer confirms them on production:

- `Which diseases are associated with BRCA1?` (query 1)
- `Which papers in the graph mention the CFTR gene, and what do they cover?` (query 117)
- `What are the known orthologs of TP53 in other species?` (query 116)
- `recent papers on BRCA1`, then pick "the last 5 years" (query 108)
- An off-topic question, to show a refusal that says what to type next (query 111's control)

## Rollback

- Each Railway service rolls back separately in the Railway console: redeploy the previous build of the API and of the web service.
- If the migrations ran, first run `alembic downgrade` to the revision before 0008 from the new build's code, then redeploy the previous build at once (`docs/build/Release_flow.md`, "Rolling back"; each migration's docstring names its command).
- A rollback does not undo the tag or the GitHub Release; the next merge to `production` redeploys forward.

## Not tomorrow

- No new card is built or merged, on develop or production.
- Factory's lane does not run.
- Develop keeps its own caps and settings; only production's change.
