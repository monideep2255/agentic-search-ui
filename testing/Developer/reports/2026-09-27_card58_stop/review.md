# Card 58 review record

Card 58, "Stop works until the answer appears", at risk dial position 2: one judge round and one adversary round, one fix round, then a fresh verifier. The builder's report and the fix round are in `builder.md` beside this file. This file records the three reviews' findings and verdicts, filed by the lead from their final messages on 2026-09-27.

## Table of contents

- [Verdicts](#verdicts)
- [Findings fixed in the fix round](#findings-fixed-in-the-fix-round)
- [Findings left as notes](#findings-left-as-notes)
- [What the person using the product notices](#what-the-person-using-the-product-notices)

## Verdicts

| Round | Verdict | Blocking |
|---|---|---|
| Judge | FAIL | F-58-J02 |
| Adversary | PASS, with one should-fix | none |
| Fix round | four findings fixed, each shown red then green | none |
| Fresh verifier, at 27dfeace | MERGE | none; no finding inside a fix commit |

## Findings fixed in the fix round

- F-58-J02, blocking, new code: a run that ended with no answer sentences, the per-question cap's partial result, offered Stop, and pressing it landed the result page anyway. Fixed by `withholdAnswer` in `frontend/src/hooks/useAnswerReveal.ts` (0aeca9d6).
- F-58-A01, should-fix, older code made reachable: the stopped screen could show "This answer stopped early because it reached its processing budget." from the discarded answer. Same fix.
- F-58-J03, should-fix: no test covered Stop on a follow-up in the same thread. Test added (de961024).
- F-58-J01, should-fix: no test covered a stopped run being charged once. Test S4 added (855bcf2e); the code was already correct.

## Findings left as notes

- F-58-V01, should-fix, the builder's test arm "keeps Stop on through the writing wait": it passes only because its fake-time loop takes longer in real time than a real timer's remaining delay. It can only fail red, never pass falsely. Card 64.
- F-58-V02, and the adversary's F-58-A05: a Stop pressed after the server finished still leaves that turn in session memory and in the history rail. Card 59.
- F-58-J04: the per-sentence check call has no cancellation branch, so a Stop during it is not metered.
- F-58-J05: a refusal whose `done` has not yet arrived shows with Stop on; in practice the two arrive together.
- F-58-J06: when the answer lands, keyboard focus falls to the page body, nothing announces that Stop has gone, and the button border's contrast is 2.24:1.
- F-58-J07 and F-58-A04: test strength and load timeouts in the card's test files.
- F-58-A02: the non-streaming `run()` still undercounts a cancelled call; nothing calls it.
- F-58-A03: a stopped run records the harness's cancellation estimate as spent, which makes the daily cap stricter, never looser.
- F-58-A06: Stop is off until the guard passes, two to three seconds after Search.
- F-58-A07, F-58-V03, F-58-V04 and F-58-V05: dead code, defensive clearing with no test, the cap note under the writing banner before Stop, and a flag every caller already guards.

## What the person using the product notices

- Stop stays usable from the moment the question is accepted until the first sentence of the answer is on screen, including the whole writing step.
- Pressed in that window, it always shows "Search stopped", never an answer, part of one, a note from it, or a trust line.
- A question stopped mid-write is now charged for the writing it used, once.
