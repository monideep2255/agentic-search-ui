import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CapMessage } from "./CapMessage";
import type { AgentEvent, ErrorPayload } from "../../lib/events";

function errorEvent(payload: ErrorPayload, seq = 1): AgentEvent {
  return {
    type: "error",
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: new Date(2026, 0, 1, 0, 0, seq).toISOString(),
    payload,
  };
}

const NO_COST_FIGURE_PATTERN = /\$|\d+\s*(usd|dollars?)|\bcost\b|\btokens?\b/i;

const CAP_COPY = "This answer stopped early because it reached its processing budget.";

describe("CapMessage", () => {
  it("renders nothing when there is no error event", () => {
    const { container } = render(<CapMessage events={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing on a fatal error, even one whose source names a cap", () => {
    const { container } = render(
      <CapMessage
        events={[
          errorEvent({
            fatal: true,
            scope: "run",
            source: "per_query_cost_cap",
            error_class: "unexpected",
            message: "budget exceeded",
            retry_after_s: 0,
          }),
        ]}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing on a non-fatal error whose source is not cap-shaped", () => {
    const { container } = render(
      <CapMessage
        events={[
          errorEvent({
            fatal: false,
            scope: "tool",
            source: "ncbi_efetch",
            error_class: "transient",
            message: "upstream timed out",
            retry_after_s: 5,
          }),
        ]}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the exact partial-result-plus-explanation copy as role=alert on a cap-shaped non-fatal error", () => {
    render(
      <CapMessage
        events={[
          errorEvent({
            fatal: false,
            scope: "run",
            source: "per_query_cost_cap",
            error_class: "recoverable",
            message: "internal budget detail should never render",
            retry_after_s: 0,
          }),
        ]}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(CAP_COPY);
  });

  it("matches any cap-shaped source case-insensitively, not just the one worked example", () => {
    render(
      <CapMessage
        events={[
          errorEvent({
            fatal: false,
            scope: "run",
            source: "DAILY_USER_CAP",
            error_class: "recoverable",
            message: "irrelevant",
            retry_after_s: 0,
          }),
        ]}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(CAP_COPY);
  });

  it("never renders a dollar figure, token count, or cost figure, even when payload.message contains one", () => {
    render(
      <CapMessage
        events={[
          errorEvent({
            fatal: false,
            scope: "run",
            source: "per_query_cost_cap",
            error_class: "recoverable",
            message: "stopped at $3.20 after 9000 tokens, cost exceeded budget",
            retry_after_s: 0,
          }),
        ]}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert.textContent ?? "").not.toMatch(NO_COST_FIGURE_PATTERN);
    expect(alert).toHaveTextContent(CAP_COPY);
  });
});
