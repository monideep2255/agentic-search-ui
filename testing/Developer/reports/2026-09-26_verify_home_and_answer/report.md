# Verify report: develop's home and answer screens, 2026-09-26

The first `/verify` run, card 42 step 1, as a guest, with `.claude/skills/verify/specs/home_and_answer.json`. It checks no particular change: it captures develop as it stood, on the home screen and on the answer to "What does BRCA1 do?".

## Table of contents

- [Target](#target)
- [Check lines](#check-lines)
- [Answer path](#answer-path)
- [Not captured](#not-captured)
- [Notes for the owner](#notes-for-the-owner)
- [Verdict](#verdict)

## Target

- Web: `https://search-agent-web-develop-2aeb.up.railway.app`
- API: `https://search-agent-api-develop-43b3.up.railway.app`
- `app_env`: develop, from the API's `/health`
- Local checkout: `d042860`
- Deployed commit: not known, since none was passed to the script
- Round: 1

## Check lines

Fails first. The scripted lines are copied unchanged from `results.json`. The four judgement lines come from reading each screenshot beside the prototype at the same width.

```text
- FAIL | home at 390 | accessibility, serious or critical | 1: color-contrast | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- FAIL | answer at 390 | horizontal overflow | 59 px | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- FAIL | answer at 390 | accessibility, serious or critical | 1: color-contrast | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- FAIL | home at 1280 | matches the prototype | same order and centring (heading, search bar, mode control, seed questions, stats), but the hero sits on the light page background where the prototype draws it on navy, the mode control offers two options where the prototype offers three, the search bar is a two-line field with an arrow button where the prototype has one line and a Search button, and a tour invitation sits where the prototype has none | home_1280.png, prototype_home_1280.png
- FAIL | home at 390 | matches the prototype | search bar full width under the heading, as designed; but the hero is on the light background where the prototype is navy, the mode control offers two options where the prototype offers three, and the seed questions are centred pills where the prototype draws full-width rows | home_390.png, home_390_fold.png, prototype_home_390.png
- FAIL | answer at 1280 | matches the prototype | the card sits at the prototype's width with the same order (question, answered line, answer, sources, follow-up, feedback), but no provenance spine runs beside the claims, the citations are superscript numbers where the prototype draws boxed chips naming the record, and the trust pills under the sources are missing | answer_1280.png, prototype_answer_1280.png
- FAIL | answer at 390 | matches the prototype | the page scrolls sideways: the app bar ends at 390 px of a 449 px page, and the unwrapped name NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG pushes citation chip 10 off the screen, where the prototype's answer fits the width; the spine and boxed chips are missing, as at 1280 | answer_390.png, answer_390_fold.png, prototype_answer_390.png
- PASS | home at 1280 | screen reached | 1 s | testing/Developer/reports/2026-09-26_verify_home_and_answer/home_1280.png
- PASS | home at 1280 | horizontal overflow | 0 px | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | home at 1280 | console errors | 0 | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | home at 1280 | accessibility, serious or critical | 0 | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | home at 390 | screen reached | 0.8 s | testing/Developer/reports/2026-09-26_verify_home_and_answer/home_390.png
- PASS | home at 390 | horizontal overflow | 0 px | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | home at 390 | console errors | 0 | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | answer at 1280 | screen reached | 16.5 s | testing/Developer/reports/2026-09-26_verify_home_and_answer/answer_1280.png
- PASS | answer at 1280 | horizontal overflow | 0 px | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | answer at 1280 | console errors | 0 | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | answer at 1280 | accessibility, serious or critical | 0 | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
- PASS | answer at 390 | screen reached | 15.8 s | testing/Developer/reports/2026-09-26_verify_home_and_answer/answer_390.png
- PASS | answer at 390 | console errors | 0 | testing/Developer/reports/2026-09-26_verify_home_and_answer/results.json
```

What `results.json` records behind the three scripted fails:

- Home at 390: the "Take the tour" button, `#0071bc` on `#e7eef6`, has a contrast of 4.39 where 4.5 is the minimum.
- Answer at 390, overflow: the one element past the screen edge is citation chip 10, ending at 449 px.
- Answer at 390, contrast: the same chip 10, `#2e8540` on `#f0f0f0`, has a contrast of 4.05.

## Answer path

Not applicable: the run checks no answer-path change, so the golden consistency run and the five-line rubric were not run.

## Not captured

- A signed-in view: the capture runs as a guest.
- The run screen while a question is working, and the streaming answer: the spec names only the landed answer.
- The answer's words: the prototype draws a canned answer to a different question, so only layout and structure were compared.

## Notes for the owner

- Some of the home screen's differences may be your later decisions rather than drift. One is recorded: the arrow-only submit button is your decision of 2026-09-13, per the comment above it in `frontend/src/components/screens/HomeScreen.tsx`. The light hero, the two answer modes and the centred seed pills are not traced to a decision here. Each line stays FAIL until you say which differences are deliberate.
- The answer's missing provenance spine, boxed chips and trust pills may also be later decisions. Nothing in this run traces them.
- The three scripted fails are cards 43 and 44 on `testing/UI_fix_plan.md`.
- The sticky footer band appears mid-page in the full-page shots. The first-screen shots show it at the bottom of the screen, where a person sees it.

## Verdict

FAIL. Seven lines still fail: the three scripted fails at 390 and the four prototype comparisons. Every scripted check passed at 1280.
