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
- [Why the golden run is the premise check](#why-the-golden-run-is-the-premise-check)
- [Step 3: read the answers against the rubric](#step-3-read-the-answers-against-the-rubric)
- [Step 4: report what to look at first](#step-4-report-what-to-look-at-first)
- [What is automated, and what waits](#what-is-automated-and-what-waits)

## What the product reviewer is, and is not

It is `.claude/agents/product-reviewer.md`: read-only tools plus Bash for the capture, no Write or Edit, no Agent tool. One dispatch, counted against the phase's 8.

- A script captures; the model only judges. Every judgement names the screenshot or answer file it read. The 2026-09-01 decision was taken because every capture the assistant interpreted needed correcting at least once, so a judgement with no file behind it is not written.
- It is a pre-screen. It tells the owner what to look at first. It never moves a card, sets a ticket state, or closes a finding. The owner's verdict closes.
- It files findings; it does not fix them. For a numbered phase its findings are ledger rows in `tracker/phase_N.M.md`. For a card worked alone they go to the report folder below.

## When it runs

- A numbered phase: after the owner merges the phase's pull request and develop has deployed it, before the owner retests.
- A card alone: after it lands on develop, before the owner retests, on any card that changes a screen or the answer path.
- Every answer-path change, at every dial position, waits on Step 2. An answer-path change is one that can change what an answer says, which records it names or cites, or whether a question is answered or refused.

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
- The floor is the answered count of the latest run the owner accepted. Today that is 102 of 150, phase 8.2's run of 2026-09-25 (`testing/Developer/reports/2026-09-25_phase_8.2_golden/summary.md`), which became the floor when the owner kept the overnight build on develop. When the owner approves a change whose run answered more, that run becomes the floor.
- Any drop in the total answered count below the floor stops the phase. Nothing else lands on develop until the change is fixed or reverted.
- Repeated runs, not one: the three passes are the repetition. Outcomes vary between runs of one question (15 of 32 questions gave different outcomes across runs on 2026-09-12), which is why one pass per question is never the measure.
- A drop is not argued away as noise, and the run is not repeated until it comes out green. That is corrupting the check. The lead may show the owner the per-question table; only the owner may accept a drop.
- A run with any rate-limit signal (`rate_limit_signals` above zero) is contaminated and does not count either way. Re-run it after the pool clears.
- Report, beside the total: the questions that got worse, the questions that never answer, and time to answer from the summary's Latency section, median, p90 and worst, with every answered question over 25 seconds named.

Two numbers, not one, since 2026-09-25 (build harness review, A3). The golden-run scripts are unchanged; the second number is the reviewer's own read.

- Answered: the total the summary prints, against the floor. Any drop blocks, as above.
- Answered well: the rubric read of a fixed sample of ten answered golden questions, the same ten every run. The sample is the ten lowest-numbered golden questions that the floor run answered in all three passes, listed by id in the report so the next run reads the same ten; it changes only when the floor does. A question counts as answered well when rubric lines 1 and 2 in Step 3 both pass, each verdict quoting the sentence it rests on.
- The summary's "Answered every time" count is the stable number to read beside them. In the two overnight runs of 2026-09-25 it was 33 in both, and the questions answered only some of the time numbered 0 and 2, where the 2026-09-12 baseline varied on 15 of 32.

Why: phase 8.1's run answered 99 of 150, and its product review read 11 of 17 answers failing rubric line 2; one question's gain from 0 to 3 was an SRA question answered with a SARS pathway (`testing/Developer/reports/2026-09-25_product_review_8.1/report.md`). A change that raises answered and lowers answered well is visible on one line.

## Why the golden run is the premise check

A premise check is a test that runs the real model against real ground truth and asserts the answer means the right thing. An ordinary test suite checks the SHAPE of an answer: rows came back, every row is cited. Both of those pass on an answer that is completely wrong.

The case that created it: build phase 2.1 shipped a fully green suite that answered "which diseases are associated with BRCA1?" with twenty-five non-human orthologs. Every row carried a real, resolving NCBI citation, so every shape check passed.

Where it applies now, and where it does not:

- Answer behaviour only: a change that can alter what an answer says, which records it names or cites, or whether a question is answered or refused.
- For every such change, the check is this golden consistency run, 50 questions three times on develop, and it blocks.
- An answer-path phase may still add a premise gate for a behaviour the golden questions cannot see. It is written first and seen failing before the code it grades. Its acceptance criteria are fixed: the four properties below, a statement of which shapes of question it exercises and which it omits, and a red run before any other ticket opens. A gate that passed on first run has not been shown able to fail.
- Nothing else gets a premise gate, a mutation harness file or a coverage claim. Spread from model-generated output to CI, release and rate limiting, those instruments became the main source of findings, 43 to 45 percent late in the build. Breaking a control to see a test go red is one line on the judge's checklist.

The four properties that make an answer-path check worth running, each a measured failure in 2.1:

- It does NOT mock the model. A mocked call supplies an answer someone already knew was correct.
- It asserts on the MEANING of the answer, not its shape.
- Its ground truth is read from the live source and pinned, so "correct" is checkable rather than plausible.
- It runs the way PRODUCTION runs. A first draft of 2.1's gate hand-picked an input and scored 8 of 9, where the input production actually sends scored 3 of 9. The golden run meets this by asking the deployed develop API.

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

- The golden result: answered against the floor, blocked or clear; answered well of the fixed ten, with the ten ids; the questions that got worse.
- The ranked list of what the owner should look at first: every fail, then every "needs your eye", each with its screenshot or answer file.
- Every screen with horizontal overflow at 390, and every surface with no design.
- What was not captured and why, stated rather than implied.

Then stop. The owner retests, and their verdict moves the item.

## What is automated, and what waits

Automate last, and only what already exists. The consistency run and the live journeys already exist, so they are the capture step today. Nothing new gets automated, including a nightly schedule on develop, until the product review has run by hand on two phases and the owner has seen both reports. It has run on phases 8.1 and 8.2; the schedule is still the owner's to ask for.
