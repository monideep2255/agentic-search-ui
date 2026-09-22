import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GuardrailBanner } from "./GuardrailBanner";
import type { AgentEvent, GuardPayload } from "../../lib/events";

function guardEvent(payload: GuardPayload, seq = 1): AgentEvent {
  return {
    type: "guard",
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: new Date(2026, 0, 1, 0, 0, seq).toISOString(),
    payload,
  };
}

// A no-dollar-figure/no-token-count/no-cost-figure check run over the
// component's ACTUAL RENDERED OUTPUT, not a visual read-through of the
// source template. Matches: a literal "$", a digit immediately adjacent to
// "usd"/"dollar(s)", or the standalone words "cost" or "token(s)" anywhere
// in the rendered text, case-insensitive.
const NO_COST_FIGURE_PATTERN = /\$|\d+\s*(usd|dollars?)|\bcost\b|\btokens?\b/i;

describe("GuardrailBanner", () => {
  it("renders nothing when the latest guard event passed", () => {
    const { container } = render(
      <GuardrailBanner events={[guardEvent({ passed: true, category: "ok", reason: null })]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when there is no guard event yet", () => {
    const { container } = render(<GuardrailBanner events={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("reacts to the LATEST guard event, not the first, when more than one is present", () => {
    render(
      <GuardrailBanner
        events={[
          guardEvent({ passed: false, category: "off_topic", reason: null }, 1),
          guardEvent({ passed: true, category: "ok", reason: null }, 2),
        ]}
      />,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  const categoryCases: Array<{ category: GuardPayload["category"]; expectedCopy: string }> = [
    {
      category: "off_topic",
      expectedCopy:
        "This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question.",
    },
    {
      category: "medical_advice",
      expectedCopy:
        "I can assemble cited evidence about a condition or variant, but a clinician makes the diagnosis or treatment call.",
    },
    {
      category: "injection",
      expectedCopy: "That request could not be processed as a research question.",
    },
    {
      category: "rate_limited",
      expectedCopy: "You have reached today's question limit. Try again after (reset time).",
    },
    {
      category: "cost_capped",
      expectedCopy: "The system is at capacity right now. Please try again shortly.",
    },
    // Added 2026-09-22 with the `compute_request` category. Section 12.6 has
    // no row for it, so this arm pins the copy the component actually ships
    // rather than a line quoted from the locked spec.
    {
      category: "compute_request",
      expectedCopy:
        "This product cannot run a sequence search or read a variant file. Ask about a specific gene, variant, or paper and I can assemble cited evidence.",
    },
  ];

  it.each(categoryCases)(
    "renders the exact Section 12.6 copy for category=$category as role=alert",
    ({ category, expectedCopy }) => {
      render(
        <GuardrailBanner
          events={[guardEvent({ passed: false, category, reason: "irrelevant free-form text" })]}
        />,
      );

      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent(expectedCopy);
    },
  );

  it.each(categoryCases)(
    "never renders a dollar figure, token count, or cost figure for category=$category",
    ({ category }) => {
      render(<GuardrailBanner events={[guardEvent({ passed: false, category, reason: null })]} />);
      const alert = screen.getByRole("alert");
      expect(alert.textContent ?? "").not.toMatch(NO_COST_FIGURE_PATTERN);
    },
  );

  it("does not leak payload.reason into the rendered copy even if reason contains a cost figure", () => {
    render(
      <GuardrailBanner
        events={[
          guardEvent({
            passed: false,
            category: "cost_capped",
            reason: "blocked at $4.50, 12000 tokens used",
          }),
        ]}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert.textContent ?? "").not.toMatch(NO_COST_FIGURE_PATTERN);
    expect(alert).toHaveTextContent("The system is at capacity right now. Please try again shortly.");
  });
});
