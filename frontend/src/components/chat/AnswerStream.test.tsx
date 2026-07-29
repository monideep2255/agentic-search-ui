import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerStream } from "./AnswerStream";
import type { AgentEvent, TokenPayload } from "../../lib/events";

function tokenEvent(text: string, seq: number, markerIds: string[] = []): AgentEvent {
  const payload: TokenPayload = { text, marker_ids: markerIds };
  return {
    type: "token",
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: new Date(2026, 0, 1, 0, 0, seq).toISOString(),
    payload,
  };
}

describe("AnswerStream", () => {
  it("renders nothing but an empty live region when there are no tokens yet", () => {
    const { container } = render(<AnswerStream events={[]} />);
    const region = container.querySelector("p.answer-stream");
    expect(region).not.toBeNull();
    expect(region).toHaveTextContent("");
    expect(region).toHaveAttribute("aria-live", "polite");
  });

  it("concatenates token text in the order the array provides, not resorted", () => {
    // Deliberately constructed out of "natural typing order": if the
    // component silently sorted by `seq` or reordered anything, this
    // would fail. The array's own order is the contract this component
    // must honor, per useAgentRun's arrival-order guarantee.
    const events = [
      tokenEvent("The ", 3),
      tokenEvent("gene ", 1),
      tokenEvent("is ", 2),
      tokenEvent("pathogenic.", 4),
    ];

    render(<AnswerStream events={events} />);

    expect(screen.getByText("The gene is pathogenic.")).toBeInTheDocument();
  });

  it("renders a token's text plainly when it carries marker_ids, without crashing or dropping it", () => {
    const events = [
      tokenEvent("A variant ", 1),
      tokenEvent("is linked to this condition", 2, ["cite-1", "cite-2"]),
    ];

    render(<AnswerStream events={events} />);

    expect(screen.getByText("A variant is linked to this condition")).toBeInTheDocument();
  });

  it("ignores non-token events mixed into the array", () => {
    const events: AgentEvent[] = [
      {
        type: "guard",
        version: "v1",
        trace_id: "trace-1",
        seq: 1,
        ts: new Date().toISOString(),
        payload: { passed: true, category: "ok", reason: null },
      },
      tokenEvent("Only this renders.", 2),
    ];

    render(<AnswerStream events={events} />);

    expect(screen.getByText("Only this renders.")).toBeInTheDocument();
  });
});
