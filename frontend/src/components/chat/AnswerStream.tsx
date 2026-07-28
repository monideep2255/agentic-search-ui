import type { AgentEvent } from "../../lib/events";

interface AnswerStreamProps {
  events: AgentEvent[];
}

type TokenEvent = Extract<AgentEvent, { type: "token" }>;

const isTokenEvent = (event: AgentEvent): event is TokenEvent => event.type === "token";

/**
 * Renders each `token.payload.text` in arrival order, concatenated into one
 * running narrative (Technical_specification.md Section 12.3/12.4).
 *
 * PROP SHAPE: takes the full `events: AgentEvent[]` array and filters for
 * `token` events itself; see `QueryPipelineStepper.tsx`'s docstring for why
 * every component in this ticket shares that shape.
 *
 * `token.payload.marker_ids` references citations that resolve via a
 * `citation` event (Section 12.4's `CitationChip`). No real `citation`
 * event exists until build phases 2.2 and 3.4 (tracker/phase_1.2.md's
 * Scope note), so this component never builds `CitationChip`, not even a
 * placeholder, per `v1-scope-boundary.md`. A token that carries
 * `marker_ids` is still rendered exactly like any other token: its `text`
 * is concatenated in place, plainly, with no special styling and no marker
 * placeholder inserted. Nothing here reads `marker_ids` at all, which is
 * itself the guarantee against crashing or silently dropping text on an
 * unresolved marker: there is no code path that could fail to resolve one,
 * because none is attempted. Whichever phase builds `CitationChip` replaces
 * this plain-text rendering at the same positions; this component does not
 * need to change to allow that.
 */
export function AnswerStream({ events }: AnswerStreamProps) {
  const text = events
    .filter(isTokenEvent)
    .map((event) => event.payload.text)
    .join("");

  // The wrapping element (and its `aria-live="polite"` region, Section
  // 12.10 success criterion 4.1.3) is always rendered, even with no tokens
  // yet, rather than returning `null` until the first token arrives. A live
  // region must already exist in the DOM before content changes for a
  // screen reader to have registered it; mounting the region only once
  // there is something to announce would miss that first announcement.
  return (
    <p className="answer-stream" aria-live="polite" aria-atomic="false">
      {text}
    </p>
  );
}
