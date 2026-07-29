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
 * arrived, until a `trust_signal`, a `done`, or a fatal `error`
 * (`payload.fatal === true`) event arrives. A non-fatal error does not end
 * the window, matching `useAgentRun`'s own fatal-only close logic and this
 * ticket's acceptance criteria.
 *
 * DOCUMENTED CHOICE: this checks for the *existence* of a passing `guard`
 * event and the *existence* of a terminal event anywhere in the array,
 * rather than comparing their relative array positions. In a real run
 * these events can only ever arrive in that order (the agent loop cannot
 * emit `trust_signal`/`done` before `guard` passes), so existence and
 * position agree in practice; existence is the simpler, equally correct
 * check and avoids re-deriving an ordering guarantee `useAgentRun`'s
 * arrival-order contract already provides.
 */
export function deriveStopEnabled(events: AgentEvent[]): boolean {
  const guardPassed = events.some((event) => event.type === "guard" && event.payload.passed);
  if (!guardPassed) {
    return false;
  }
  const reachedTerminal = events.some(
    (event) =>
      event.type === "trust_signal" ||
      event.type === "done" ||
      (event.type === "error" && event.payload.fatal === true),
  );
  return !reachedTerminal;
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
