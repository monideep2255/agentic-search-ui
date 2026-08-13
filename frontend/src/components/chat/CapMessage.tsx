import type { AgentEvent } from "../../lib/events";

interface CapMessageProps {
  events: AgentEvent[];
}

type ErrorEvent = Extract<AgentEvent, { type: "error" }>;

/**
 * DOCUMENTED CHOICE, the ambiguous trigger condition this ticket's prompt
 * asks to be resolved and recorded: a "cap-shaped" non-fatal `error` event
 * is one with `payload.fatal === false` whose `payload.source` contains
 * "cap" (case-insensitive). Technical_specification.md Section 12.6 gives
 * `per_query_cost_cap` as its one worked example `source` value, but
 * neither Section 12.6 nor Section 2.3 enumerates every cap source string
 * the backend may emit; `system-design-patterns.md` pattern 4 names four
 * distinct caps (per-query, per-user daily, system-wide daily, per-step
 * timeout), and hardcoding one exact string risks silently missing a
 * sibling cap's error event. Matching on "cap" as a substring is the
 * reasonable, documented engineering call: broad enough to catch every cap
 * source this repo's caps are named after, narrow enough that an ordinary
 * tool or network failure (whose `source` names the failing tool or layer,
 * not a cap) does not falsely trigger this banner.
 */
export const isCapShapedError = (event: AgentEvent): event is ErrorEvent =>
  event.type === "error" && event.payload.fatal === false && /cap/i.test(event.payload.source);

export const CAP_MESSAGE_COPY =
  "This answer stopped early because it reached its processing budget.";

/**
 * Renders on a non-fatal, cap-shaped `error` event, per Technical_
 * specification.md Section 12.6's "mid-stream cap" case: the partial
 * answer built so far stays visible (this component renders alongside
 * `AnswerStream`, it does not replace it), with an explanatory line.
 *
 * PROP SHAPE: takes the full `events: AgentEvent[]` array; see
 * `QueryPipelineStepper.tsx`'s docstring for why every component in this
 * ticket shares that shape.
 *
 * `CAP_MESSAGE_COPY` is a single fixed string with no interpolation slot.
 * `payload.message` (free-form backend text describing the failure) is
 * deliberately never rendered here, the same defense `GuardrailBanner`
 * uses: Section 12.6 requires no dollar figure, token count, or cost
 * figure can ever reach this copy, and the only way to guarantee that
 * against a field this frontend does not control is to never render that
 * field's raw value.
 */
export function CapMessage({ events }: CapMessageProps) {
  const capEvent = [...events].reverse().find(isCapShapedError);

  if (!capEvent) {
    return null;
  }

  return (
    <div role="alert" className="cap-message">
      {CAP_MESSAGE_COPY}
    </div>
  );
}
