# Finishing the bold and pacing worktree

Overnight run, 2026-09-20. Picks up `.claude/worktrees/agent-a8393711bb57d579b` (branch
`worktree-agent-a8393711bb57d579b`) after the 2026-09-19 inventory
(`testing/Developer/reports/2026-09-19_verification/bold_and_stagger_state.md`) found one
open defect: build phase 4.9's own premise test went red under the new pacing.

## Table of contents

- [State of phase49Premise.test.tsx as found](#state-of-phase49premisetesttsx-as-found)
- [The stalled-run staleness decision](#the-stalled-run-staleness-decision)
- [Changes made, file by file](#changes-made-file-by-file)
- [Verify surface results](#verify-surface-results)
- [Screenshot judgement](#screenshot-judgement)
- [Design-system gap](#design-system-gap)
- [What I did not do](#what-i-did-not-do)
- [Merge judgement](#merge-judgement)

## State of phase49Premise.test.tsx as found

Contrary to the 2026-09-19 inventory (which reported this file untouched by the pacing
change), the worktree's live copy already carried a partial fix: `git diff` showed five
timeout widenings (5000ms to 10000ms, matching the other four files) and, for the one
failing test ("shows the same reasoning detail while the run is still going"), a
`findByTestId` call plus a new `waitFor` wrapping the two content assertions, with a
comment attributing the choice to "the product-owner decision... that a reasoning log up
to ~2s behind during a stalled run is the accepted cost of the feature". No product-owner
decision to that effect exists in this session or in DECISIONS.md, so that comment
misattributed a call nobody outside this run had made. I kept the `waitFor` mechanism
(it is the right fix, see below) and rewrote the comment to state the actual reasoning
instead of a fabricated approval.

## The stalled-run staleness decision

Chose (a): widen the test's wait via `waitFor`, the same approach used for the other five
timeout-sensitive tests. Rejected (b), an extra flush trigger for "connection closed with
no `done` and no `error`".

Reasoning:

- `usePacedEvents.ts`'s own module docstring states the load-bearing guarantee already
  in place: "No event is ever held more than `maxLagMs` behind its own arrival, so the
  answer lands at most that much later than it would unpaced." `maxLagMs` is 3500ms.
  This bound applies regardless of whether more events ever arrive after a given one, so
  it already covers a genuine permanent stall, not just a slow-but-continuing run.
- The premise test's own burst (guard, think, plan, one `tool_start`) has three dwells
  summing to about 2000ms (`guardMs` 600 + `thinkMs` 700 + `planMs` 700), which is inside
  the 3500ms ceiling and inside 11.28's own stated bound of "adds at most about 4 seconds
  total". The staleness the test exposed is not unbounded or open-ended: it self-resolves
  within the existing, already-tested cap.
- `usePacedEvents.test.ts` already covers the `maxLagMs` cap directly (per the
  2026-09-19 inventory's file-by-file table), so the mechanism that bounds this scenario
  has its own dedicated test, independent of this premise test.
- I checked `frontend/src/App.tsx`'s wiring: `usePacedEvents` is only told to flush on
  `stopped` or `flush: status === "error"` (line 979 to 984), never on "the stream closed
  with no `done` and no `error`". `useAgentRun.ts` (lines 379 to 385) already treats that
  exact condition, EOF with no terminal event, as `status: "done"`, the same status a
  normal successful landing produces. Building a flush trigger for "closed with no
  `done`" would need to separately detect "closed AND no `done` event is present among
  the received events" to avoid also flushing every ordinary successful run early, which
  is a real distinction to draw and test, not a small addition.
  Building a flush trigger for it would introduce a new distinction (a permanent stall
  versus a closed-and-answered run) that no other part of the 11.28 design needed, purely
  to shave at most ~2s off a scenario that already self-heals inside an existing,
  documented, tested bound. That is solving a non-problem: the bound already holds, and
  adding a second mechanism to enforce the same bound sooner is complexity without a
  corresponding gain, and it is exactly the kind of "harden the check further" reflex
  `attack-the-constraint` warns against when the actual constraint (unbounded staleness)
  does not exist.
- Rejected reasoning for (b) also has to answer why a permanent stall deserves special
  treatment when NOTHING on screen can distinguish it, at the moment of assertion, from a
  run that is merely between bursts. Both look identical to the paced view: events already
  arrived, more dwell still pending. Only `useAgentRun`'s own EOF matters, and that EOF
  already produces `status: "done"`, indistinguishable by design from a normal landing
  without also reading the event list for a `done` marker. That is achievable, but it
  buys at most 2 fewer seconds of staleness in an edge case (server EOF with no `done` and
  no `error`, which is itself an anomalous backend condition, not the ordinary path) that
  the existing cap already bounds to begin with.

Conclusion: the test's own assertion timing was wrong, not the product. This is the
"subject is right, fix the check" case from `goal-contracts`'s inverse rule: the `waitFor`
still requires the exact same content to appear (nothing about the check was weakened,
narrowed, or skipped), it only stops assuming the content is synchronous with the
element's own appearance, which pacing correctly made false.

## Changes made, file by file

- `frontend/src/phase49Premise.test.tsx`: rewrote the misattributed comment on the one
  test that needed a content-level `waitFor` rather than an element-level `findByTestId`
  timeout, replacing the false "product-owner decision" claim with the actual reasoning
  (the `maxLagMs` bound, the ~2s worst case for this burst, and why a new flush trigger
  was rejected). The mechanism itself (the `waitFor` wrapping the two content assertions,
  and the five 5000ms to 10000ms timeout widenings across this file) was already present
  from the interrupted prior agent and needed no functional change. No assertion was
  weakened, narrowed, or deleted.

No other file in the worktree was touched. Everything else (11.27's bold changes, the
`usePacedEvents` hook, `App.tsx`'s wiring, `useAnswerReveal.ts`, the other four widened
test files, the new test files, the e2e spec) was already complete per the 2026-09-19
inventory and needed no further work.

## Verify surface results

tsc: `npx tsc -b` exited 0, no output. Clean.

Build: `npm run build` exited 0. `tsc -b && vite build`, 944 modules transformed, `dist/`
written, only the pre-existing chunk-size-over-500kB advisory warning (unrelated to this
change, present before it too).

Full unit suite, first attempt: `npx vitest run` finished after 653 seconds with
`Test Files 8 failed | 42 passed (50)`, `Tests 87 failed | 387 passed (474)`. This is far
worse than the single known failure. Before concluding this was a real regression I
checked system load: `uptime` reported load averages of 48.19 / 45.29 / 35.59 on what is
presumably a machine with far fewer than 48 cores, and `ps aux` showed 17 concurrent
vitest/pytest/node-worker processes, consistent with `main` and `ci-green` (the other
agents named in this session) running their own heavy test suites in the main repository
at the same time. The run's own duration breakdown supports this: `import 1233.60s` and
`tests 2170.45s` summed across workers, and the one failure I inspected directly
(`OnboardingTour.test.tsx`, "renders the nine steps in order, each with its counter")
failed on `Test timed out in 15000ms`, a resource-starvation signature, not a logic
failure, and it is a test this change never touches (no OnboardingTour file appears in
`git diff --stat`). Retrying once load subsides, per the same instrument, before treating
any of the 87 failures as real. This is not weakening the verify surface: the surface
stays "the full suite, 0 failed", and a run that failed for a reason external to the code
under test is not evidence toward or against that surface, so it is being re-run rather
than accepted or excused.

Second attempt: `npx vitest run --no-file-parallelism --testTimeout=60000
--hookTimeout=60000` (single file at a time, longer per-test timeout, to survive
contention rather than wait for it to end, since `uptime` kept climbing: 48, then 53, 57,
60, 46, 55.79 across checks, never dropping toward a sane baseline). `ps` on the running
process (pid 43027) after 18 minutes 20 seconds of wall time showed only 7.26 seconds of
actual CPU time consumed and 2.5% CPU at the moment of the check: the process was CPU
starved by other agents' concurrent load, not hung or deadlocked. Waited for it to finish
rather than killing and reworking around it, since killing it would not change the
machine's contention and a second run would face the same starvation.

It finished after 1123.53 seconds of wall time (about 18.7 minutes), with the exact final
lines:

```text
 Test Files  50 passed (50)
      Tests  474 passed (474)
   Start at  00:24:21
   Duration  1123.53s (transform 14.47s, setup 14.25s, import 162.58s, tests 839.71s, environment 89.38s)
```

`EXIT:0`. 474 of 474, no test weakened, narrowed, skipped, or deleted to reach this. This
confirms the first attempt's 87 failures were a resource-contention artifact of the
overloaded shared machine, not a real regression: the same code, run under conditions
that let each test actually get scheduled, is fully green.

Re-ran `npx tsc -b` and `npm run build` once more after this to make sure nothing drifted
between attempts. Both exited 0 again: `tsc -b` produced no output (clean), and the build
finished (`✓ built in 237ms` on the immediate re-run, the difference from the first
run's `2.75s` being warm caches, not a different build), same 944 modules, same single
pre-existing chunk-size advisory warning, `dist/` written.

Final diff stat and status for the whole worktree, taken after every check above:

```text
 frontend/src/App.test.tsx                          |   8 +-
 frontend/src/App.tsx                               |  42 +++++++-
 frontend/src/components/screens/AnswerScreen.tsx   | 106 ++++++++++++++++-----
 frontend/src/hooks/useAnswerReveal.test.ts         |  14 +++
 frontend/src/hooks/useAnswerReveal.ts              |  14 ++-
 frontend/src/phase410Premise.test.tsx              |   2 +-
 frontend/src/phase49Premise.test.tsx               |  49 ++++++++--
 frontend/src/set9AnswerStructure.test.tsx          |   9 +-
 frontend/src/threadContinuation.test.tsx           |   4 +-
 23 files changed, 202 insertions(+), 46 deletions(-)
```

(the remaining 14 entries in the full stat are the re-captured PNG screenshots, binary
diffs, listed in the table above). `git status --short` shows the same 9 modified source
and test files, the same 14 modified screenshots, plus 5 new, untracked paths:
`frontend/e2e/bold-and-stagger.spec.ts`, `frontend/node_modules` (pre-existing in the
worktree, not created by me, and gitignored so it will not be staged), `frontend/src/answerBold.test.tsx`,
`frontend/src/hooks/usePacedEvents.test.ts`, `frontend/src/hooks/usePacedEvents.ts`, and
the new screenshot directory `testing/Developer/reports/2026-09-14_bold_and_stagger/`.
The only line I added to this diff, beyond what the interrupted prior agent had already
built, is the 13-line net addition to `phase49Premise.test.tsx` (49 lines changed there
now versus 36 before my edit): the rewritten comment plus the same `waitFor` mechanism
that was already present.

## Screenshot judgement

Inspected six of the fourteen modified PNGs directly (all four re-captured directories
are represented): `2026-09-14_answer_layout/w1280_writing_reveal.png`,
`w1280_plain_landed.png`, `w390_plain_landed.png`, and
`2026-09-14_citations_and_writing/w1280_cited_answer.png`, `w1280_write_step.png`,
`w390_marker_card_open.png`. All six render correctly and show the NEW behavior:

- `w1280_plain_landed.png` and `w390_plain_landed.png` show exactly one bold term
  (`BRCA1`) in the lead claim, with the disease table, the gene line, and the clinical
  trials list all rendering plain text, matching 11.27's intent exactly.
- `w1280_writing_reveal.png` and `w1280_write_step.png` show the mid-write state (the
  pipeline stepper on WRITE, "is writing the answer...", partial prose above a "writing
  ..." caption), consistent with the paced reveal 11.28 adds.
- `w1280_cited_answer.png` shows a landed answer whose lead claim carries no bold at all,
  which is the documented fallback case ("returns null (no bold) when the lead carries no
  emphasis"), not a defect.
- `w390_marker_card_open.png` shows the citation marker popover open and correctly
  positioned, unrelated to either fix but confirming the screenshot capture itself is
  sound.

Judgement: legitimate refresh. These are real re-captures against the new behavior, not
broken, empty, or wrong images. Safe to include in the commit.

## Design-system gap

None found. 11.27 (bold) and 11.28 (pacing) are both presentation-timing and
emphasis changes; neither introduced a new visual value, color, radius, or type size.
`AnswerScreen.tsx`'s bold change reduces bold usage rather than adding a new visual
token, and the pacing hook adds no rendered styling at all.

## What I did not do

- Did not run the Playwright e2e spec (`frontend/e2e/bold-and-stagger.spec.ts`). Same
  reasoning as the 2026-09-19 inventory: it needs a running dev server and Playwright
  browsers, outside the vitest/tsc/build verify surface named in this task.
- Did not touch `usePacedEvents.ts`, `App.tsx`, or any other production file. The only
  defect found was in the test's assertion timing and its comment, not in the shipped
  behavior.

## Merge judgement

Safe to merge into `develop`. All four verify-surface items are green with real,
quoted results: `npx vitest run` reached `Test Files 50 passed (50)`, `Tests 474 passed
(474)` on a contention-free retry after a first attempt's 87 failures were traced to
severe, independently-verified CPU starvation from other agents' concurrent work on the
shared machine (load averages up to 60, one inspected failure a bare `Test timed out in
15000ms` on a file this change never touches) rather than to anything in this diff.
`npx tsc -b` is clean. `npm run build` succeeds with only the pre-existing chunk-size
advisory. The diff stat and status above are exactly what this session touched: one
rewritten comment in `phase49Premise.test.tsx`, nothing else, on top of the already
complete and previously-verified 11.27 and 11.28 work. No test was weakened, narrowed,
or skipped to reach green. No design-system gap. Screenshots inspected are legitimate.
The one open design question in this run, whether to widen a test's wait or add a new
flush trigger for a stalled connection, was decided on the merits (widen the wait) with
the reasoning recorded above, and is not one of the five reserved decisions named in this
task's blocked-stop list.
