/**
 * What the screen shows of the answer, and what Stop leaves on it.
 *
 * BUILD PHASE 8.7, T-8.7-03 (2026-09-27, card 50): THE SCREEN FOLLOWS THE
 * STREAM. This hook used to hold the answer back: the first sentence waited
 * until the writing banner had shown for 1.5 seconds, then one sentence per
 * 110 ms, and the pacing ahead of it (`usePacedEvents`) held arrived text
 * behind the helper narrative for up to 13 seconds on develop. The owner's
 * acceptance for this phase is that nothing that has arrived is held back,
 * so every sentence, record and citation is shown in the render it arrives
 * in. The writing state is still seen, because it is now real: the records
 * arrive the moment the searches end and the writing mark stands above them
 * while the summary is written (`AnswerScreen`'s `WritingMark`).
 *
 * WHAT IS LEFT HERE is Stop, card 58's rule plus the owner's answer of
 * 2026-09-27, in one function, `whatStopLeavesOnScreen`:
 *
 *   - Stop before any of the answer was on screen shows no part of it (card
 *     58, F-58-J02 and F-58-A01): "Search stopped" alone.
 *   - Stop after the records were on screen keeps exactly those records, as
 *     they were, and shows nothing that arrives afterwards: no summary, no
 *     count-line change, no note, no trust line. The owner, relayed by the
 *     lead: "keep them".
 *
 * The same rule covers a summary already partly on screen, which only happens
 * while the server is still writing: what was shown stays, nothing new comes.
 */

import { useRef } from "react";

import type { RunView } from "./useRunView";

export interface AnswerRevealOptions {
  /** The run being shown. A new key starts again from nothing on screen. */
  runKey: string | null;
  /** Stop latched: keep what was on screen, show nothing new. */
  stopped: boolean;
  /**
   * The stream failed (`useAgentRun` status "error"): show everything that
   * arrived. A failed run has nothing to stop, and holding its sentences back
   * would hide what the reader is owed.
   */
  flush?: boolean;
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
 * Since build phase 8.7 no arrived text is held back, so the case above now
 * arises only when the answer arrives in the same moment as the Stop, or
 * after it. The rule is unchanged: what the reader had not seen, they never
 * see.
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

/**
 * What a Stop leaves on screen, in ONE place (the lead's condition while the
 * owner decided, 2026-09-27), given the view as it arrives now and the view
 * that was on screen the moment before Stop latched.
 *
 *   - Nothing of the answer was on screen: withhold all of it, card 58.
 *   - Records, or sentences, were on screen: keep exactly those, with the
 *     sources their citation markers resolve through, and nothing else from
 *     the answer: no trust line, no status line, no note, no cap notice, and
 *     nothing that arrived after Stop. The view never lands, so the result
 *     page never comes up for a stopped run.
 */
export function whatStopLeavesOnScreen(view: RunView, shownBeforeStop: RunView | null): RunView {
  if (shownBeforeStop === null || shownBeforeStop.claims.length === 0) return withholdAnswer(view);
  return {
    ...withholdAnswer(view),
    claims: shownBeforeStop.claims,
    sources: shownBeforeStop.sources,
  };
}

export function useAnswerReveal(
  view: RunView,
  { runKey, stopped, flush = false }: AnswerRevealOptions,
): RunView {
  // What is on screen, recorded on every render before Stop. Written during
  // render, the pattern `usePacedEvents` uses for arrival times: it is a
  // fact about this render, and a repeated render writes the same value.
  const shownRef = useRef<{ key: string | null; view: RunView } | null>(null);
  if (!stopped) shownRef.current = { key: runKey, view };

  if (runKey === null || flush || !stopped) return view;
  const shown = shownRef.current !== null && shownRef.current.key === runKey ? shownRef.current.view : null;
  return whatStopLeavesOnScreen(view, shown);
}

export default useAnswerReveal;
