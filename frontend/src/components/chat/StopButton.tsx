import { useEffect, useState } from "react";
import type { AgentEvent } from "../../lib/events";
import { stopRun } from "../../lib/api";

/**
 * `StopButton` calls `POST /v1/query/{run_id}/stop` and closes the local
 * event stream (Technical_specification.md Section 12.3), enabled only
 * while a run is actually in flight.
 *
 * PROP SHAPE: takes the full `events: AgentEvent[]` array to derive its
 * enabled/disabled window, the same convention `QueryPipelineStepper.tsx`'s
 * docstring documents for every sibling component in this ticket set, plus
 * the three additional props this component needs to actually perform a
 * stop (`runId`, `token`, `stop`). `stop` is the exact callback
 * `useAgentRun` already exposes for this purpose (see that hook's
 * docstring: "Exposed for a later ticket's stop button (T-1.2-06)...");
 * this component calls it rather than re-implementing an AbortController
 * of its own, so there is exactly one place client-side connection
 * lifecycle is owned.
 */
interface StopButtonProps {
  events: AgentEvent[];
  runId: string;
  token: string;
  stop: () => void;
}

/**
 * Pure derivation of the enabled window from the raw event array, exported
 * for direct unit testing without rendering the component (same pattern as
 * `QueryPipelineStepper.tsx`'s exported `deriveSteps`).
 *
 * Enabled from the moment a `guard` event with `payload.passed: true` has
 * arrived, until a `done` or a fatal `error` (`payload.fatal === true`)
 * event arrives: the window in which the server may still be working on
 * the run. A non-fatal error does not end the window, matching
 * `useAgentRun`'s own fatal-only close logic and this ticket's acceptance
 * criteria.
 *
 * A `trust_signal` NO LONGER ENDS IT (card 58, 2026-09-27). It used to, on
 * the reading that a verdict meant the answer was being delivered. A trust
 * signal is PART of the answer, never its end: on develop every one arrives
 * in the same burst as the tokens and `done`, and once answers stream
 * sentence by sentence a claim-scope verdict can arrive while the server is
 * still writing the rest. Ending Stop there would end it while there is
 * still something to stop.
 *
 * DOCUMENTED CHOICE: this checks for the *existence* of a passing `guard`
 * event and the *existence* of a terminal event anywhere in the array,
 * rather than comparing their relative array positions. In a real run
 * these events can only ever arrive in that order (the agent loop cannot
 * emit `done` before `guard` passes), so existence and position agree in
 * practice; existence is the simpler, equally correct check and avoids
 * re-deriving an ordering guarantee `useAgentRun`'s arrival-order contract
 * already provides.
 */
export function deriveStopEnabled(events: AgentEvent[]): boolean {
  const guardPassed = events.some((event) => event.type === "guard" && event.payload.passed);
  if (!guardPassed) {
    return false;
  }
  const reachedTerminal = events.some(
    (event) => event.type === "done" || (event.type === "error" && event.payload.fatal === true),
  );
  return !reachedTerminal;
}

/**
 * What the reader has been shown so far, which is not what has arrived.
 *
 * `usePacedEvents` and `useAnswerReveal` hold arrived events back so each
 * stage can be read, so the screen can sit many seconds behind the stream.
 * These are the two facts about the SCREEN that Stop depends on, read off
 * the view the screen actually renders.
 */
export interface StopScreenState {
  /** The screen has moved to its final state: an answer, a refusal or a failure. */
  landed: boolean;
  /** How many answer sentences are on screen. */
  claimsShown: number;
}

/**
 * Whether Stop is offered on screen, card 58.
 *
 * The product owner, 2026-09-27: "a user should be able to stop the answer
 * at any point of time until the answer pops out." Stop used to follow the
 * arrived stream alone, so it went grey the moment the server finished,
 * which on develop was up to 13 seconds BEFORE the screen showed the first
 * sentence (G-013, `testing/Developer/reports/2026-09-27_card58_stop/
 * builder.md`): the reader watched the helpers hand back and the writing
 * banner with a grey Stop and nothing to read.
 *
 * THE ANSWER APPEARS when its first sentence is on screen. Not at a trust
 * signal, not when the server finishes. So Stop is offered:
 *
 *   - once the guard has passed, and never after a fatal error, whose
 *     failure notice is shown at once because the pacing flushes on it;
 *   - until the view lands, since a landed answer, refusal or failure has
 *     nothing left to stop;
 *   - while no sentence is on screen, whatever the server has done;
 *   - after the first sentence only while the server is still writing,
 *     because then Stop still cuts the rest of the answer short (UI fix set
 *     9, item 9.6). On develop today the whole answer arrives with `done`,
 *     so the first sentence on screen is also the end of Stop.
 *
 * `events` is the ARRIVED stream, for what the server has done. `shown` is
 * the revealed view, for what the reader has seen.
 */
export function deriveStopOffered(events: AgentEvent[], shown: StopScreenState): boolean {
  const guardPassed = events.some((event) => event.type === "guard" && event.payload.passed);
  if (!guardPassed || shown.landed) {
    return false;
  }
  const failed = events.some((event) => event.type === "error" && event.payload.fatal === true);
  if (failed) {
    return false;
  }
  if (shown.claimsShown === 0) {
    return true;
  }
  return deriveStopEnabled(events);
}

export function StopButton({ events, runId, token, stop }: StopButtonProps) {
  // Tracks a click on this specific run, independent of `events`. Clicking
  // stop closes the local connection immediately (see the handler below),
  // but the parent's `events` array may not gain a new terminal event right
  // away since this client has stopped listening; without this flag the
  // button would stay enabled after a click until the parent happens to
  // re-render with a later event, defeating the "feels instantly
  // responsive" requirement and allowing a rapid double click to fire
  // `stopRun` twice. Reset whenever `runId` changes, so a parent that
  // reuses this component across runs (rather than remounting it) does not
  // carry a stale "already stopped" state into a new run.
  const [hasStopped, setHasStopped] = useState(false);

  useEffect(() => {
    setHasStopped(false);
  }, [runId]);

  const enabled = deriveStopEnabled(events) && !hasStopped;

  const handleClick = () => {
    // Order matters: `stop()` runs first and synchronously, so the local
    // connection closes and this button's own disabled state flips before
    // anything network-related happens. `stopRun` is fired without
    // `await`, deliberately, so a slow or hung backend response never
    // delays the local "stopped" feedback (Section 12.3's "feels instantly
    // responsive" requirement; T-1.2-06 acceptance criterion 2).
    stop();
    setHasStopped(true);
    stopRun(runId, token).catch((caughtError) => {
      // Swallowed deliberately, not logged as a user-facing error: the
      // local stop above has already ended this client's view of the run,
      // and `stopRun` is documented as idempotent on the backend (a repeat
      // or late call still returns `{stopped: true}`), so a network
      // failure reaching this catch does not change the user-facing
      // outcome and must not surface as a thrown error or an error toast
      // (acceptance criterion 3). Logged for operator visibility only;
      // never logs `token`.
      console.warn(`stopRun request failed for run ${runId}`, caughtError);
    });
  };

  return (
    <button type="button" className="stop-button" onClick={handleClick} disabled={!enabled}>
      {hasStopped ? "Stopping…" : "Stop"}
    </button>
  );
}
