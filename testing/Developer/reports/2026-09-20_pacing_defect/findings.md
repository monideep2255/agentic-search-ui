# UI fix 11.28: it is a real defect, not event-loop starvation

Written 2026-09-20. Supersedes the starvation hypothesis recorded in
`testing/UI_fix_plan.md`'s cutoff earlier the same day.

## What was believed, and by whom

The overnight cutoff of 2026-09-19 could not separate two explanations for the CI
failure that forced 11.28's revert:

- A real defect: on a stream closing with no `done`, the last paced events may never release.
- Event-loop starvation: the same suite failed 87 tests at load average 48 to 60 and passed only serially.

On 2026-09-20 the lead read `usePacedEvents.ts` and argued the first could not be
true, because each event's release target is `min(max(arrival, earliest), arrival +
maxLagMs)`, computed from that event's OWN arrival, and the `setTimeout` loop drains
the queue on wall clock alone. Nothing can hold an event past arrival plus 3.5
seconds except the event loop not running. The lead concluded starvation and wrote
that into the plan.

## What was measured

An agent instrumented the hooks and ran the premise test "shows the same reasoning
detail while the run is still going" ALONE on an idle machine, load average 2.68 to
2.87, three times. It FAILED all three times, identically.

| Event | Released at | Ceiling |
|---|---|---|
| guard | lag 5ms | 3500ms |
| think | lag 627ms | 3500ms |
| plan | lag 1325ms | 3500ms |
| tool_start | lag 2025ms | 3500ms |

`useRunView`'s derived `steps` array reaches `Guard, Think, Plan` at about 1.3
seconds of wall clock.

And the DOM never shows the plan narrative, for the full 10 second window, in all
three runs.

## The finding

The pacing hook is correct. The view hook is correct. The DOM does not reflect
either. The defect lives between `useRunView`'s output and `ReasoningLog`'s render
in `RunProgress.tsx`, and it appears ONLY with pacing applied: the same test passes
on develop, where CI is green.

So the revert of 2026-09-19 was right, for a better reason than anyone had.

## Why the lead's reasoning failed, which is the transferable part

The argument about `usePacedEvents` was CORRECT and the conclusion drawn from it was
WRONG. Proving that one component cannot hold an event says nothing about whether
the event survives the rest of the path to the screen. The lead reasoned about the
file it had open rather than about the whole path from event to pixel.

This repository has already written that lesson down twice and it was not applied:

- Build phase 5.0: four consecutive rounds hardened the local audit sink while the
  identical string shipped off-box with no control at all, because "every round was
  scoped from the file the previous round had been editing rather than from where
  credentials actually flow".
- `attack-the-constraint`: when a component is fed by an assembly step, the assembly
  step is upstream and is the constraint until proven otherwise. Here the reverse
  applies, the component is CONSUMED by a render path, and the render path was never
  examined.

The cheap check that would have settled it in one step, and was not run: compare
what the hook holds against what the DOM shows, rather than reasoning about whether
the hook could be late.

## Status

The root cause is being localised by experiment, hop by hop from the paced output to
the rendered node, rather than by reading. 11.28 is NOT on develop and must not land
until the premise test passes on an idle machine and is shown to still fail with the
fix reverted.

The test's timeout was already widened once as part of this change. That is how the
defect stayed hidden, and it is why the investigation brief forbids touching the
assertion or its timeout.

## Root cause, found by experiment

The first hop where the data stops arriving is not the pacing hook at all.

`phase49Premise.test.tsx`'s shared `STREAM` fixture sent a `plan` frame carrying
`tool_calls: []`, and then four `tool_result` frames. THAT COMBINATION CANNOT OCCUR
IN PRODUCTION, checked rather than asserted: every `tool_calls=[]` emission in
`core/graph.py` (lines 3932, 3935, 4017, 4022 and 4027) is a "no tool selected"
refusal that returns immediately, so no tool result can follow one.

The empty array told `useRunView`'s `planSelectedNoTool` check that the plan had
selected no tool, so `activeStep` became `Write`. `RunProgress.tsx` line 817 renders
the reasoning log only while `!writingNow`, so `<ReasoningLog>` UNMOUNTED. The test
was holding the node returned by `findByTestId("reasoning-log")`, which was now
detached. 741ms later the real `tool_start` arrived, `activeStep` returned to `Act`,
and the log remounted as a NEW node carrying the Plan line, which the test's
captured reference could never see.

Before pacing, that false `Write` state lasted under one millisecond, because `plan`
and the first `tool_result` landed in the same events snapshot. Pacing stretched it
to roughly 700ms, which is long enough to unmount.

So pacing introduced no defect. It widened a pre-existing fixture inconsistency from
invisible to observable.

## Why fixing the fixture is not weakening the check

`goal-contracts` names three cases when a gate fires, and this is the first one: the
subject is wrong, so fix the subject. The fixture described a stream the backend
cannot emit. Correcting it turns a false statement into a true one. The assertion
and its timeout were NOT touched, which matters because that timeout had already
been widened once as part of 11.28, and widening it is how the defect stayed hidden.

Verified in both directions by the reviewer rather than by the author of the fix:

| State | Result |
|---|---|
| Fixture corrected | `1 passed` |
| Fixture reverted | `1 failed` |
| Full worktree suite, fixture corrected | `50 passed, 474 passed, 0 failed` |

## The residual risk, recorded rather than declared clean

The investigating agent concluded this is "a test-fixture bug, not a defect in the
pacing feature". That is right about this test and it is not the whole picture.

The unmount path is real production code. What pacing changed is its blast radius: a
transient false `Write` state that previously lasted under a millisecond now lasts
about 700ms, which is long enough to unmount and remount the reasoning log where it
previously could not.

Here the only trigger was a fixture production cannot produce. There is NO evidence
that another path produces a transient false `Write`, and equally NO evidence that
none does, because nobody has looked. Owner: whoever next touches `useRunView`'s
step derivation or `RunProgress`'s `writingNow` gating.

The cheap check if it ever matters: a real refusal run reaches `plan` with empty
`tool_calls` legitimately, and there the unmount is correct, since the run really is
moving to Write and no tool result follows to bring it back.
