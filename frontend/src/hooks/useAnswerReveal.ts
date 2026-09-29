/**
 * Reveal a burst of answer sentences one at a time, 2026-09-14.
 *
 * WHY THIS EXISTS. Measured on develop (6 live runs, 28 frames at 250ms): the
 * write step holds every event until it returns, so an answer's 14 to 33
 * `token` events land within 217ms of each other, usually together with
 * `done`. Rendered as they arrive, the answer appeared all at once and the
 * approved "writing" state (`design/Streaming.dc.html`) was never seen.
 *
 * WHAT IT DOES, and nothing else. It sits between `useRunView` and every
 * consumer in `App`, and returns the SAME view with fewer claims while a
 * reveal is in progress:
 *
 *   - The first sentence waits until the Write state has been on screen for
 *     `minBannerMs`, so a fast write still reads as writing.
 *   - Then one sentence per `perItemMs` while the run is live, or per
 *     `afterDoneMs` once `done` has arrived, so a finished answer catches up
 *     quickly.
 *   - Until the last sentence is shown, the view reports `landed: false` and
 *     `activeStep: "Write"`, so the screen stays in the writing state instead
 *     of jumping to a landed answer with half its sentences.
 *   - Stop freezes the reveal where it is and clears the pending timer.
 *   - Stop before the first sentence withholds the whole answer, see
 *     `withholdAnswer` below.
 *   - Once every sentence is shown, the input view is returned UNCHANGED, the
 *     same object, so the landed answer is exactly what arrived.
 *
 * NOTHING IS DROPPED OR REWORDED while the reveal runs: claims are sliced,
 * never filtered, and the slice only grows until it equals the input. The one
 * exception is the Stop above, where the reader asked for no answer at all.
 */

import { useEffect, useRef, useState } from "react";

import type { RunView } from "./useRunView";

export const REVEAL_TIMING = {
  /** The writing banner is visible at least this long before the first sentence. */
  minBannerMs: 1500,
  /** One sentence per this many ms while the run is still live. */
  perItemMs: 110,
  /** One sentence per this many ms once `done` has arrived. */
  afterDoneMs: 40,
  /**
   * UI fix 11.28: the banner minimum under `prefers-reduced-motion`. The
   * order is kept (banner, then sentences) but the hold is cut to a minimum.
   */
  reducedMinBannerMs: 300,
} as const;

export interface AnswerRevealOptions {
  /** The run being revealed. A new key starts a new reveal from zero. */
  runKey: string | null;
  /** Stop latched: freeze where the reveal is. */
  stopped: boolean;
  /**
   * The stream failed (`useAgentRun` status "error"): show everything that
   * arrived at once. A failed run has no writing to pace, and holding its
   * sentences back would hide what the reader is owed.
   */
  flush?: boolean;
  /** `prefers-reduced-motion: reduce`: hold the banner `reducedMinBannerMs` only. */
  reducedMotion?: boolean;
}

/**
 * What a run stopped before its first sentence shows: no part of its answer.
 *
 * Card 58's fix round, F-58-J02 and F-58-A01. Stop now stays offered until
 * the first sentence is on screen, which is often after the server has
 * finished. Stop then flushes the pacing (`usePacedEvents`), so the whole
 * held-back answer reaches `useRunView` in one go. The reveal's freeze used
 * to be the only thing keeping it off screen, and it only holds SENTENCES:
 *
 *   - J02. The per-question cap's partial result (`_partial_result_for_cap`
 *     in `core/graph.py`) has no sentences, only a note and `done`. Nothing
 *     was held, the view landed, and a person who pressed Stop was taken to
 *     the result page with the note and a trust line.
 *   - A01. An answer's own cap note becomes `capMessage`, which the stopped
 *     screen renders under "Search stopped", so the page said "This answer
 *     stopped early" under "No answer was produced".
 *
 * So the answer is withheld as a whole: the view never lands, and everything
 * `useRunView` derives from the Write step's output is cleared.
 *
 * KEPT, because each was on screen before any Stop could discard it:
 *
 *   - The refusal, its label and link, and a clarification. Every source of
 *     them (a failed guard, a clarifying `think`, an answer-level refusal
 *     signal) flushes the pacing the moment it arrives, so the person has
 *     already read it, and it says what to type next.
 *   - `failure`, from a fatal error, which flushes the same way.
 *   - The search itself: steps, helpers and layers. The stopped screen does
 *     not show them, and they describe the search, not the answer.
 *
 * DROPPED: the cap notice as well, whatever its source. On develop its only
 * source is the answer's own note, since the server never sends a cap-shaped
 * error (its one non-fatal error, in `core/graph.py`'s refusal path, names
 * `write` or `cypher_query` as its source), and its copy speaks of "this
 * answer" beside "No answer was produced".
 */
export function withholdAnswer(view: RunView): RunView {
  return {
    ...view,
    landed: false,
    claims: [],
    sources: [],
    trust: [],
    meta: "",
    outcome: null,
    outcomeTone: null,
    elapsedMs: null,
    nextStep: null,
    nextStepQuery: null,
    capMessage: null,
    systemNotes: [],
  };
}

export function useAnswerReveal(
  view: RunView,
  { runKey, stopped, flush = false, reducedMotion = false }: AnswerRevealOptions,
): RunView {
  const minBannerMs = reducedMotion ? REVEAL_TIMING.reducedMinBannerMs : REVEAL_TIMING.minBannerMs;
  const [state, setState] = useState<{ key: string | null; count: number }>({
    key: runKey,
    count: 0,
  });
  const writeStartRef = useRef<{ key: string | null; at: number } | null>(null);

  const total = view.claims.length;
  const count = state.key === runKey ? state.count : 0;
  const inWrite = view.activeStep === "Write" || total > 0;

  // When the Write state (or the first sentence) was first seen for this run.
  if (inWrite && (writeStartRef.current === null || writeStartRef.current.key !== runKey)) {
    writeStartRef.current = { key: runKey, at: Date.now() };
  }

  useEffect(() => {
    if (runKey === null || stopped || flush || count >= total) return;
    const pace = view.landed ? REVEAL_TIMING.afterDoneMs : REVEAL_TIMING.perItemMs;
    let delay: number = pace;
    if (count === 0) {
      const startedAt = writeStartRef.current?.at ?? Date.now();
      delay = Math.max(0, startedAt + minBannerMs - Date.now());
    }
    const timer = setTimeout(() => {
      setState((current) => ({
        key: runKey,
        count: (current.key === runKey ? current.count : 0) + 1,
      }));
    }, delay);
    return () => clearTimeout(timer);
  }, [runKey, stopped, flush, count, total, view.landed, minBannerMs]);

  if (runKey === null || flush) return view;
  // Stop froze the reveal before its first sentence: the reader saw no
  // answer and asked for none. Checked before `count >= total`, because a run
  // with no sentences at all has nothing to slice and would otherwise land.
  if (stopped && count === 0) return withholdAnswer(view);
  if (count >= total) return view;

  const reachedSteps = view.reachedSteps.includes("Write")
    ? view.reachedSteps
    : [...view.reachedSteps, "Write" as const];
  return {
    ...view,
    claims: view.claims.slice(0, count),
    landed: false,
    activeStep: stopped ? view.activeStep : "Write",
    reachedSteps,
    meta: "",
  };
}

export default useAnswerReveal;
