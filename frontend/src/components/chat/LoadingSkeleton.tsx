export type LoadingSkeletonState = "cold_start" | "guard_pending";

interface LoadingSkeletonProps {
  state: LoadingSkeletonState;
}

/**
 * Renders Technical_specification.md Section 12.5's two pre-stream loading
 * states, so neither ever shows a blank pane:
 *
 * - `cold_start`: the event stream has been opened but no event has
 *   arrived yet. Section 12.5: "a generic connecting spinner,
 *   `aria-label="Connecting"`."
 * - `guard_pending`: the query was submitted but no `guard` event has
 *   arrived yet. Section 12.5 describes this as `PersonaHeader` with a
 *   pulsing indicator and no stepper content. `PersonaHeader`'s real
 *   persona assignment is build phase 4.5's job (tracker/phase_1.2.md's
 *   Scope note), so this renders a generic "Checking your question"
 *   placeholder with the same pulsing affordance rather than building a
 *   stub `PersonaHeader` that is not this ticket's file to create.
 *
 * A parent component (a later ticket's `ChatPage` wiring) decides which
 * state applies from `useAgentRun`'s `status` and the presence of a
 * `guard` event in `events`; this component only renders the two known
 * states, it does not derive them.
 */
export function LoadingSkeleton({ state }: LoadingSkeletonProps) {
  if (state === "cold_start") {
    return (
      <div
        className="loading-skeleton loading-skeleton--cold-start"
        role="status"
        aria-label="Connecting"
      >
        <span className="loading-skeleton__spinner" aria-hidden="true" />
        <p>Connecting…</p>
      </div>
    );
  }

  return (
    <div
      className="loading-skeleton loading-skeleton--guard-pending"
      role="status"
      aria-label="Checking your question"
    >
      <span className="loading-skeleton__pulse" aria-hidden="true" />
      <p>Checking your question…</p>
    </div>
  );
}
