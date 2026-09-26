# First /verify run: develop's home and answer screens

The first run of `/verify` (card 42, step 1), against deployed develop on 2026-09-26, as a guest. `/health` read `app_env` develop, and the checkout was d042860. A script captured every check in `results.json` and the model judged the screenshots beside `docs/build/design/design-system/prototype/app.html`. Two runs gave the same result: 13 checks passed, 3 failed.

## Table of contents

- [The judgement](#the-judgement)
- [What was captured](#what-was-captured)
- [Cards this run opened](#cards-this-run-opened)

## The judgement

One line per check, in the skill's format: verdict, screen and width, the check, what was seen, and the files that prove it.

- PASS | home at 1280 | overflow, console errors, accessibility scan | 0 px overflow, 0 console errors, no serious or critical violation | `results.json`, `home_1280.png`
- FAIL | home at 390 | accessibility scan | "Take the tour" has a contrast of 4.39 (`#0071bc` on `#e7eef6`, 13.5 px bold) where 4.5 is the minimum | `results.json`, `home_390_fold.png`
- NEEDS THE OWNER'S EYE | home at 390 | matches the prototype | the search bar is full width under the heading, as designed. Three differences from the prototype look like later product decisions rather than drift, so they are the owner's to confirm:
  - the hero sits on the light background where the prototype is navy;
  - "Answer mode" has two options where the prototype's "Answer depth" has three;
  - the example questions are centred pills where the prototype has full-width rows.
  - Files: `home_390.png`, `home_390_fold.png`, `prototype_home_390.png`.
- PASS | answer at 1280 | overflow, console errors, accessibility scan | 0 px overflow, 0 console errors, no serious or critical violation; ready in 16.5 s | `results.json`, `answer_1280.png`
- FAIL | answer at 390 | no sideways scrolling | the page is 449 px wide on a 390 px screen: the variant name `NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG` does not wrap and pushes citation chip 10 off the screen. The top of the answer reads correctly | `results.json`, `answer_390.png`, `answer_390_fold.png`, `prototype_answer_390.png`
- FAIL | answer at 390 | accessibility scan | citation chip 10 has a contrast of 4.05 (`#2e8540` on `#f0f0f0`) where 4.5 is the minimum | `results.json`
- Not a defect: the navy band mid-page in the full-page shots is the sticky footer, which sits at the bottom in the first-screen shots.

## What was captured

- Widths: 1280x900 and 390x844, with reduced motion and a 1.5 s settle.
- Per screen and width: a full-page screenshot, a first-screen screenshot, horizontal overflow, console errors, and an axe scan against WCAG 2.1 A and AA.
- The prototype's same screen at both widths.
- The two answers' text, in `answer_1280.txt` and `answer_390.txt`.
- The spec that drove the run, in `spec.json`.

## Cards this run opened

The two failures a person meets are now cards on `testing/UI_fix_plan.md`:

- Card 43: on a phone, an answer that cites a long variant name scrolls sideways.
- Card 44: two small controls fail the contrast minimum.
