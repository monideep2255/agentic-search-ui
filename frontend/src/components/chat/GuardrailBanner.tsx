import type { AgentEvent, GuardPayload } from "../../lib/events";

interface GuardrailBannerProps {
  events: AgentEvent[];
}

type GuardEvent = Extract<AgentEvent, { type: "guard" }>;

const isGuardEvent = (event: AgentEvent): event is GuardEvent => event.type === "guard";

/**
 * Copy chosen purely by `guard.payload.category`, matching Technical_
 * specification.md Section 12.6's table exactly (word for word, including
 * the literal "(reset time)" placeholder Section 12.6 itself uses for
 * `rate_limited`, since no `reset_time` field exists on `GuardPayload` to
 * interpolate a real value from).
 *
 * `category: "ok"` is included only because `GuardPayload["category"]`'s
 * type requires an exhaustive `Record`; the server never emits `passed:
 * false` alongside `category: "ok"` (that combination is a contract
 * violation), but this component fails safe with generic copy instead of
 * crashing or rendering nothing if it ever did, per `ai-security-
 * standards.md`'s "treat AI/upstream output as untrusted until verified".
 */
const CATEGORY_COPY: Record<GuardPayload["category"], string> = {
  ok: "This question could not be processed. Please try rephrasing it.",
  off_topic:
    "This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question.",
  medical_advice:
    "I can assemble cited evidence about a condition or variant, but a clinician makes the diagnosis or treatment call.",
  injection: "That request could not be processed as a research question.",
  rate_limited: "You have reached today's question limit. Try again after (reset time).",
  cost_capped: "The system is at capacity right now. Please try again shortly.",
};

/**
 * Renders whenever the latest `guard` event failed (`payload.passed ===
 * false`).
 *
 * PROP SHAPE: takes the full `events: AgentEvent[]` array; see
 * `QueryPipelineStepper.tsx`'s docstring for why every component in this
 * ticket shares that shape.
 *
 * No dollar figure, token count, or cost figure can ever appear in this
 * component's rendered output. That is enforced structurally, not just by
 * writing careful copy: `CATEGORY_COPY` is a fixed lookup table with no
 * interpolation slot at all, and no other field from the `guard` event
 * (including `payload.reason`, which is free-form backend text this
 * frontend does not control) is ever rendered here. A future backend
 * change that puts a number into `reason` cannot leak it into this banner,
 * because this component never reads `reason`.
 */
export function GuardrailBanner({ events }: GuardrailBannerProps) {
  const latestGuard = [...events].reverse().find(isGuardEvent);

  if (!latestGuard || latestGuard.payload.passed) {
    return null;
  }

  return (
    <div role="alert" className="guardrail-banner">
      {CATEGORY_COPY[latestGuard.payload.category]}
    </div>
  );
}
