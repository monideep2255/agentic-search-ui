import { useEffect, useRef, useState } from "react";

/**
 * Whole seconds since a run started, ticking once a second while it runs.
 *
 * Build phase 6.2, T-6.2-05, complaint 2 in `docs/build/UI_feedback.md`.
 *
 * ## Why a ticking number rather than a nicer spinner
 *
 * The measured wait is 12 to 14 seconds, and the sequence a user actually
 * experiences is: question submitted, a gap, some tool chips, another gap
 * of several seconds, then the whole answer at once. The run screen already
 * names the live step and colours the tool chips, and neither of those
 * MOVES. Across a five-second gap on one step the page is indistinguishable
 * from a page that has died.
 *
 * A spinner would move and would say nothing. A number that counts up is
 * the only element here that is simultaneously always-moving and
 * informative: it tells the user the process is alive, and it tells them
 * honestly that this takes a while, which sets an expectation rather than
 * hiding it. The stepper keeps carrying WHICH step, per that ticket's
 * criterion that progress is named rather than an undifferentiated spinner.
 *
 * ## The accessibility trap this deliberately avoids
 *
 * A number that changes every second is hostile inside an ARIA live region:
 * a screen reader would announce "one second, two seconds, three seconds"
 * for the whole run and bury the step transitions that actually carry
 * meaning. So the caller renders this value `aria-hidden`, and announces
 * STEP CHANGES politely instead. This hook returns a number and takes no
 * view on that, but the trap is recorded here because it is the reason the
 * value is not simply dropped into the existing `role="status"` element.
 *
 * ## Behaviour
 *
 * - `startedAt` null means no run is in flight, and the hook returns 0 and
 *   schedules nothing.
 * - The interval is cleared on unmount and whenever `startedAt` changes, so
 *   a new run never inherits the previous run's timer.
 * - Elapsed is recomputed from `Date.now()` on each tick rather than
 *   incremented. An incremented counter drifts, and it stops entirely when
 *   a background tab throttles timers, so it would UNDERSTATE the wait in
 *   exactly the case where a user tabbed away and came back wanting to know
 *   how long they had been waiting.
 */
export function useElapsedSeconds(startedAt: number | null): number {
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef(startedAt);
  startedAtRef.current = startedAt;

  useEffect(() => {
    if (startedAt === null) {
      setElapsed(0);
      return;
    }

    // Set immediately as well as on the interval, so a run that lands in
    // under a second still shows a truthful 0s rather than nothing.
    const compute = () => {
      const from = startedAtRef.current;
      if (from === null) return;
      setElapsed(Math.max(0, Math.floor((Date.now() - from) / 1000)));
    };
    compute();

    const handle = window.setInterval(compute, 1000);
    return () => window.clearInterval(handle);
  }, [startedAt]);

  return elapsed;
}
