# Phase 8.7 builder S: the screen

Branch `feat/8.7-screen`, base 586d7151. Steps 2 and 7 of the resume plan.

## Table of contents

- [Findings and plan deviations](#findings-and-plan-deviations)
- [Design gaps](#design-gaps)
- [Mutation checks](#mutation-checks)
- [Learnings](#learnings)

## Findings and plan deviations

- The `placement` field is not in this branch. `frontend/src/lib/events.ts` needs commit 1e030148's hunk for `tsc` to pass. It sits in the working tree uncommitted, identical to 1e030148, and is left out of both commits (outside the file fence). The step 7 commit does not compile alone until 1e030148 is merged first.
- cb407508 did not apply cleanly to today's code. Three conflicts, resolved by hand:
  - `App.tsx`: kept today's `stopping` and `answerStood` (card 59). The reveal hook gets `stopped: stopped || stopping` and `flush: status === "error" || answerStood`, with no `reducedMotion`. The inline progress keeps `stopping={stopping}`.
  - `useRunView.ts`: card 23's `openTableRow` (the variant source note under a table) moved into the per-region state, so a listing row never takes a summary note.
  - `AnswerScreen.tsx`: kept today's long-final-name and main-point handling and added `placementAttribute(claim)` to it.
- Six arms of `App.stopUntilAnswer.test.tsx` failed, not seven. All six are reshaped. Their premise was that the screen holds arrived text back. It no longer does, so each arm now sends the text after the Stop press on the open stream (the real race) and checks it never shows.
- Two arms of `App.stopAfterAnswer.test.tsx` failed for the same reason. That file is not in the ticket's list, but it is `App.tsx`'s test, so I reshaped them:
  - "Stop after the server finished" became "an answer the server finished is on screen the moment it arrives, and Stop is gone". The window it pressed Stop in no longer exists. "Stop while done is in flight" keeps the remaining race.
  - The M7 arm now sends the answer after the press.
- New arms added to `App.stopUntilAnswer.test.tsx`: Stop after the records (first run and follow-up) keeps them under "Search stopped", with no summary, trust line or writing mark. Another arm shows Stop stays on through the records and the first summary sentence (the server is still writing), and goes off when `done` lands.
- The Stop arms must not send `done` and then `cancelled`: the server sends one or the other (card 59, D18). My first version sent both and the answer stood.
- `summarySentencesShown` in the Stop count (cb407508) is close to vestigial now: with no reveal timer, claims on screen means the run is either live (Stop stays on while the server writes) or landed. No test fails if the count includes records. Kept as cb407508 has it; flagging for the lead.
- Also taken from cb407508 beyond the named files: `useAnswerReveal.test.ts` and the new `useRunView.placement.test.ts` (tests of the hooks the ticket names).
- Full `npx vitest run` run: see the final report for counts. `eslint` has no config in the repository (`eslint.config.*` missing), so it could not run.
- `resultPage()` (`[data-tour="answer"]`) matches the AnswerScreen root in the running state too, so it cannot tell a stopped-with-records page from a landed one. The new arm checks for the "Answered" result line instead.

## Design gaps

- The writing mark standing in the summary's slot above the records is cb407508's own placement. `streaming.html` shows the mark under the text only. This is named in `WritingMark`'s comment in `AnswerScreen.tsx`. Not changed here.
- Not looked at in a browser (no `/verify` in this ticket). The 1280 and 390 pixel comparison against `streaming.html` and `prototype/app.html` is still to do.

## Mutation checks

Each was one property changed, then restored.

- Token not a flush (`isFlushEvent`): 3 `usePacedEvents` arms fail.
- Summary region rendered after the listing: 5 `AnswerScreen.listingFirst` arms fail.
- Body wrapper keyed on running: "keeps every record row when the run lands" fails.
- `placementAttribute` removed: 3 arms fail.
- `isHiddenNote` also hiding "no written summary": the note arm fails.
- `whatStopLeavesOnScreen` always withholding: both "Stop after the records" arms fail.
- Stop slice (`shownEvents`) removed alone, or `claims: shownBeforeStop.claims` alone: no arm fails. They are two layers of one rule. With both removed, 5 `stopUntilAnswer` arms and the M7 arm fail.

## Learnings

- The repository guard (`mod-public-repo-guard`) held every `git commit` call with "the guard failed while checking this call". See the final report for whether it cleared.
- `rm` is blocked by a hook, so a mutation backup must be restored with `cp` from the scratchpad, and temp files moved with `mv`.
