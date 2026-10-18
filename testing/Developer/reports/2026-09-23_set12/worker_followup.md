VERDICT: DONE. Full vitest suite green (531/531) on the second, clean run.

## What changed

`frontend/src/components/answer/FollowUp.tsx`:
- Added a new prop, `isRefusal?: boolean` (default `false`).
- The heading now reads `isRefusal ? "Ask another question" : "Continue this conversation"`. It is plain text inside the existing `<Typography component="p">`, nothing hidden from the accessibility tree, so whichever string is in the DOM is what a screen reader reads. No separate ARIA work was needed.
- The hint-chip row is now gated `{!isRefusal && hints.length > 0 ? (...) : null}`, checked inside `FollowUp` itself, not only at the call site. If a future caller passes hints on a refusal by mistake, the component still refuses to show them.
- The follow-up field, the "Ask" button, and the `nextStep`/`nextStepQuery` offer block are untouched.

`frontend/src/App.tsx`:
- `FollowUp` now also receives `isRefusal={view.refusal !== null || view.refusalLabel !== null}`, the exact same test `AnswerScreen` already uses internally to decide its own "refusal" outcome branch (line ~1106-1107), so the two can never disagree about what counts as a refusal. `FOLLOW_UP_HINTS` is still passed unconditionally; `FollowUp`'s own gate is what suppresses it, which is the belt-and-suspenders choice recorded above.

New test file, `frontend/src/components/answer/FollowUp.refusal.test.tsx`, 4 arms:
1. Default/answer case still shows "Continue this conversation" plus hints.
2. `isRefusal` shows "Ask another question", hides both heading text and all hint chips.
3. `isRefusal` with hints passed anyway still hides them (proves the suppression lives inside the component, not only at the call site).
4. The field itself stays reachable (`getByRole("textbox", ...)`) under a refusal.

## What I chose to show instead of the chips, and why

Nothing. From the reader's chair: a refusal already carries its own message, either the clarification's "I could not tell which gene, variant, disease or organism you mean. Name one and I will search" or the general refusal's NCBI fallback link. A chip repeating that in different words would add a click without adding information, and the three existing chips are answer-shaped ("What variants cause it?") with a referring word that has no antecedent on a refusal, which is the exact defect the tester hit. Manufacturing a fourth, refusal-specific chip risked shipping a second version of the same trap under time pressure, so I left the space empty rather than invent a replacement the design system does not specify.

## Design-system check

Searched `docs/build/design/design-system/` for a refusal-state follow-up treatment, including `prototype/app.html` per `design-consistency.md`'s instruction not to check one file. No component, screen, or flow file designs a distinct "refusal follow-up" heading or chip row; `components/trust-pills.html`'s own note ("Refusal is a first-class state, not an error") only covers the trust-pill/outcome-word suppression that `AnswerScreen` already implements, not this field. This is a genuine gap, named rather than filled: no visual value was invented, since the fix is copy and a conditional, not a new surface. Every existing value (`designTokens.inkFaint`, the 10.5px/700-weight/uppercase heading style, the `border-top` divider, the field's own token set) is unchanged; nothing new needed a token because nothing new was drawn.

## Existing tests touched

None had to change. I checked `AnswerScreen.refusal.test.tsx` and `useRunView.clarification.test.ts` as flagged in the brief: neither renders or asserts on the `followUp` prop or `FollowUp`'s copy, so both were case three (right about something else, not touching this surface) and needed no edit. A repo-wide grep confirmed no test anywhere pins the literal string "Continue this conversation" outside `FollowUp.tsx`'s own source comments.

## Verification

`cd frontend && npx vitest run --silent`, run twice. First run (before I'd finished writing this report) showed 4 failures, all `Test timed out in 15000ms` in `src/phase49Premise.test.tsx` and `src/threadContinuation.test.tsx`, none touching `FollowUp`, `isRefusal`, or refusal copy. I stashed my changes to confirm these were pre-existing (they were the same timeout shape on the unmodified tree, over interaction sequences unrelated to this fix), then immediately popped the stash back and re-ran clean. Second run: 531/531 passed, 59/59 files, exit code 0. The 4 timeouts read as flaky/slow on this machine (15s budget against ~550s total test time under load), not a regression from this change.

## What I could not close

Nothing outstanding on this ticket's own scope. The absent refusal-specific design in the design system is worth a note back to the design track, since a future pass may want an intentional empty state rather than "nothing renders," but that is a design decision above this fix's remit, not a defect in it.
