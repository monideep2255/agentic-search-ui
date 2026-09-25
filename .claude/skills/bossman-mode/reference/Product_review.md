# The product review

Read this before dispatching the product reviewer, and before any answer-path change lands. It is the one stage in this cadence that looks at the product the way a person uses it: the deployed develop app, at the widths people use, with real answers to the golden questions.

Two product-owner decisions of 2026-09-24 put it here, from `docs/build/Bossman_mode_redesign.md`:

- Add a product reviewer that drives the deployed develop app at 1280 and 390 beside the design prototype and reads answers against a five-line rubric, as a pre-screen before the owner's retest that never closes an item. This reverses the 2026-09-01 decision that the assistant drives the browser only when asked, for this pre-screen only.
- The golden consistency run blocks every answer-path change: any drop in the answered count stops the phase, measured over repeated runs, not one.

Why, from the build record:

- Before the fix loop, no stage asked "would a researcher want this answer?"
- No stage looked at the deployed screen at phone width until the last UI phase.
- The first person to see the deployed product found six defects no suite could see.
- On 2026-09-12, after 35 merged phases had passed their reviews, the golden questions answered in 13 of 85 runs that started.

## Table of contents

- [What the product reviewer is, and is not](#what-the-product-reviewer-is-and-is-not)
- [When it runs](#when-it-runs)
- [Step 1: capture the screens](#step-1-capture-the-screens)
- [Step 2: the golden consistency run](#step-2-the-golden-consistency-run)
- [Step 3: read the answers against the rubric](#step-3-read-the-answers-against-the-rubric)
- [Step 4: report what to look at first](#step-4-report-what-to-look-at-first)
- [What is automated, and what waits](#what-is-automated-and-what-waits)

## What the product reviewer is, and is not

It is `.claude/agents/product-reviewer.md`: read-only tools plus Bash for the capture, no Write or Edit, no Agent tool. One dispatch, counted against the phase's 8.

- A script captures; the model only judges. Every judgement names the screenshot or answer file it read. The 2026-09-01 decision was taken because every capture the assistant interpreted needed correcting at least once, so a judgement with no file behind it is not written.
- It is a pre-screen. It tells the owner what to look at first. It never moves a card, sets a ticket state, or closes a finding. The owner's verdict closes.
- It files findings; it does not fix them. In build-phase mode its findings are ledger rows in `tracker/phase_N.M.md`. In UI fix mode they go to the report folder below.

## When it runs

- Build-phase mode: after the owner merges the phase's pull request and develop has deployed it, before the owner retests.
- UI fix mode: before the owner retests an item, on any item that changes a screen or the answer path.
- Every answer-path change, in either mode, waits on Step 2. An answer-path change is one that can change what an answer says, which records it names or cites, or whether a question is answered or refused.

Before capturing anything, confirm which app answered. A screenshot of the wrong deployment looks identical to a screenshot of the right one.

- The API's `/health` reports `app_env`, and it must read develop.
- `frontend/e2e/live-target.ts` is the reference. The develop web app is its `DEVELOP_WEB` value, overridable with `S3_LIVE_WEB_URL`.

Evidence goes to one output folder the brief names, by default `testing/Developer/reports/<date>_product_review_<topic>/`, written by the capture commands. The reviewer writes nothing else.

## Step 1: capture the screens

For every screen the change touches, named by the lead in the brief from the diff:

1. Screenshot the deployed develop app at 1280 and at 390 pixels wide, full page.
2. Screenshot the same screen in `docs/build/design/design-system/prototype/app.html` at the same two widths. The prototype is the assembled product and the only file that says what happens at 390, since every media query lives there.
3. At 390, measure horizontal overflow: the page's `scrollWidth` minus its `clientWidth`. Anything above zero is a finding, whatever the screenshot looks like.
4. Check `docs/build/design/README.md`'s coverage table for each screen. A screen with no design is named as a gap, never judged against an invented look.

Commands, run from `frontend/`, since Playwright is installed there:

- A static page: `npx playwright screenshot --full-page --viewport-size "1280, 900" <url> <out.png>`, and again with `"390, 844"`.
- A screen that needs a click or a question to reach: a short `node -e` Playwright script run through Bash, which navigates, waits for the screen's test id, screenshots, and prints the overflow measurement.
- The live journeys under `frontend/e2e/journeys/`, behind `RUN_LIVE_JOURNEYS=1`, already film the landing, the wait, follow-ups and the narrow viewports. Reuse them where one covers the screen; journey 7 films 390, 768 and 1440, so 1280 still needs its own shot.

Then Read each pair of screenshots and compare them. What to look for: position, not presence. Build phase 4.8's checks asserted what is on screen and never where, and the whole app shipped in a 720px strip.

## Step 2: the golden consistency run

The one premise check that survives in this cadence, and it blocks.

The instrument is `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py`: every golden question in `eval/golden/golden_dataset.json`, three passes, two workers partitioned by question, a fresh session per run, signed in with one account per worker. That is 150 runs, about 40 minutes.

```bash
python3 testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py \
  <out_dir> --accounts <accounts.json> --commit <deployed sha>
python3 testing/Developer/reports/2026-09-22_10.3_consistency/summarize.py \
  <out_dir> <floor run's runs.jsonl>
```

- The accounts file holds sign-in bodies and is never committed or printed. The lead passes its path in the brief. The per-user daily cap is 100, which is why there are two accounts and two workers.
- The floor is the answered count of the latest run the owner accepted. Today that is 86 of 150, the 2026-09-22 run at commit `63ec316`. When the owner approves a change whose run answered more, that run becomes the floor.
- Any drop in the total answered count below the floor stops the phase. Nothing else lands on develop until the change is fixed or reverted.
- Repeated runs, not one: the three passes are the repetition. Outcomes vary between runs of one question (15 of 32 questions gave different outcomes across runs on 2026-09-12), which is why one pass per question is never the measure.
- A drop is not argued away as noise, and the run is not repeated until it comes out green. That is corrupting the check. The lead may show the owner the per-question table; only the owner may accept a drop.
- A run with any rate-limit signal (`rate_limit_signals` above zero) is contaminated and does not count either way. Re-run it after the pool clears.
- Report, beside the total: the questions that got worse, the questions that never answer, and time to answer from the summary's Latency section, median, p90 and worst, with every answered question over 25 seconds named.

## Step 3: read the answers against the rubric

Read the answer text the run saved under `raw/` for the answered questions, and grade each against five lines, in the owner's own words from the fix loop:

1. Does the first sentence answer the question, or does it "list what was found instead of answering" (item 12.10 in `testing/UI_fixes_done.md`)?
2. Would a researcher, a clinician or a student learn something a general chatbot would not tell them? The owner's verdict of 2026-09-20 was that "the answers all look surface level" and that general chatbots answer better (the detail for item 11.29 in `testing/UI_fixes_done.md`).
3. Do Plain language and Researcher read differently (item 12.9, "Plain language and researcher return the SAME text")? The consistency run asks at the default depth only, so for this line ask three answered golden questions once at each depth on develop and read the pairs side by side.
4. How many seconds until the answer landed?
5. Does each screen match its design at both widths, and is any surface missing a design (`docs/build/design/README.md`, coverage table)?

Each line gets one of three verdicts, and each verdict quotes the sentence or names the screenshot it rests on:

- Pass.
- Needs the owner's eye.
- Fail.

## Step 4: report what to look at first

The report is short and ranked, because the owner reads it before retesting:

- The golden result: answered against the floor, blocked or clear, and the questions that got worse.
- The ranked list of what the owner should look at first: every fail, then every "needs your eye", each with its screenshot or answer file.
- Every screen with horizontal overflow at 390, and every surface with no design.
- What was not captured and why, stated rather than implied.

Then stop. The owner retests, and their verdict moves the item.

## What is automated, and what waits

Automate last, and only what already exists. The consistency run and the live journeys already exist, so they are the capture step today. Nothing new gets automated, including a nightly schedule on develop, until the product review has run by hand on two phases and the owner has seen both reports.
