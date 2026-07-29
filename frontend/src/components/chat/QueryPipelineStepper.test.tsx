import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QueryPipelineStepper, deriveSteps } from "./QueryPipelineStepper";
import type { AgentEvent, ToolCall } from "../../lib/events";

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
  seq: number,
): AgentEvent {
  return {
    type,
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: new Date(2026, 0, 1, 0, 0, seq).toISOString(),
    payload,
  } as AgentEvent;
}

const guardPassed = () =>
  envelope("guard", { passed: true, category: "ok", reason: null }, 1);
const guardFailed = () =>
  envelope("guard", { passed: false, category: "off_topic", reason: "not biomedical" }, 1);
const think = () =>
  envelope(
    "think",
    {
      narrative: "Classifying the question",
      query_class: "lookup",
      resolved_entities: [],
      clarifying_question: null,
    },
    2,
  );
const plan = (toolCalls: ToolCall[]) =>
  envelope("plan", { narrative: "Planning the search", tool_calls: toolCalls }, 3);
const toolStart = (callId: string, seq: number) =>
  envelope(
    "tool_start",
    { call_id: callId, tool: "cypher_query", layer: "layer_1_graph", status: "ok" },
    seq,
  );
const toolResult = (callId: string, status: "ok" | "empty" | "error", seq: number) =>
  envelope(
    "tool_result",
    {
      call_id: callId,
      tool: "cypher_query",
      layer: "layer_1_graph",
      status,
      summary: "found 3 rows",
      result_count: 3,
      truncated: false,
    },
    seq,
  );

describe("deriveSteps", () => {
  it("starts with only guard active and everything else pending, given no events", () => {
    const steps = deriveSteps([]);
    expect(steps).toHaveLength(3);
    expect(steps[0]).toMatchObject({ id: "guard", status: "active" });
    expect(steps[1]).toMatchObject({ id: "think", status: "pending" });
    expect(steps[2]).toMatchObject({ id: "plan", status: "pending" });
  });

  it("moves guard to done and think to active once guard passes", () => {
    const steps = deriveSteps([guardPassed()]);
    expect(steps[0]).toMatchObject({ id: "guard", status: "done" });
    expect(steps[1]).toMatchObject({ id: "think", status: "active" });
    expect(steps[2]).toMatchObject({ id: "plan", status: "pending" });
  });

  it("blocks think and plan at pending forever when guard fails", () => {
    const steps = deriveSteps([guardFailed()]);
    expect(steps[0]).toMatchObject({ id: "guard", status: "error" });
    expect(steps[1]).toMatchObject({ id: "think", status: "pending" });
    expect(steps[2]).toMatchObject({ id: "plan", status: "pending" });
  });

  it("advances think to done and plan to active once think arrives", () => {
    const steps = deriveSteps([guardPassed(), think()]);
    expect(steps[0]).toMatchObject({ status: "done" });
    expect(steps[1]).toMatchObject({ id: "think", status: "done" });
    expect(steps[2]).toMatchObject({ id: "plan", status: "active" });
  });

  it("seeds pending tool steps from the plan event's tool_calls before any tool_start arrives", () => {
    const steps = deriveSteps([
      guardPassed(),
      think(),
      plan([{ tool: "cypher_query", call_id: "call-1", layer: "layer_1_graph" }]),
    ]);
    expect(steps).toHaveLength(4);
    expect(steps[2]).toMatchObject({ id: "plan", status: "done" });
    expect(steps[3]).toMatchObject({ id: "tool:call-1", status: "pending" });
  });

  it("moves a tool step to active on its tool_start and done on a successful tool_result", () => {
    const base = [
      guardPassed(),
      think(),
      plan([{ tool: "cypher_query", call_id: "call-1", layer: "layer_1_graph" }]),
    ];

    const activeSteps = deriveSteps([...base, toolStart("call-1", 4)]);
    expect(activeSteps[3]).toMatchObject({ id: "tool:call-1", status: "active" });

    const doneSteps = deriveSteps([...base, toolStart("call-1", 4), toolResult("call-1", "ok", 5)]);
    expect(doneSteps[3]).toMatchObject({ id: "tool:call-1", status: "done", detail: "found 3 rows" });
  });

  it("marks a tool step as error when its tool_result carries status error", () => {
    const steps = deriveSteps([
      guardPassed(),
      think(),
      plan([{ tool: "cypher_query", call_id: "call-1", layer: "layer_1_graph" }]),
      toolStart("call-1", 4),
      toolResult("call-1", "error", 5),
    ]);
    expect(steps[3]).toMatchObject({ id: "tool:call-1", status: "error" });
  });

  it("tracks two tool calls independently, each active only once its own tool_start arrives", () => {
    const steps = deriveSteps([
      guardPassed(),
      think(),
      plan([
        { tool: "cypher_query", call_id: "call-1", layer: "layer_1_graph" },
        { tool: "ncbi_efetch", call_id: "call-2", layer: "layer_2_api" },
      ]),
      toolStart("call-1", 4),
    ]);
    expect(steps[3]).toMatchObject({ id: "tool:call-1", status: "active" });
    expect(steps[4]).toMatchObject({ id: "tool:call-2", status: "pending" });
  });
});

describe("QueryPipelineStepper", () => {
  it("renders an aria-live=polite ordered list reflecting the current state", () => {
    render(<QueryPipelineStepper events={[guardPassed(), think()]} />);

    const list = screen.getByRole("list", { name: /search progress/i });
    expect(list).toHaveAttribute("aria-live", "polite");

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveAttribute("data-status", "done");
    expect(items[1]).toHaveAttribute("data-status", "done");
    expect(items[2]).toHaveAttribute("data-status", "active");
  });

  it("updates rendered status as more events are fed in across re-renders", () => {
    const { rerender } = render(<QueryPipelineStepper events={[]} />);
    expect(screen.getAllByRole("listitem")[0]).toHaveAttribute("data-status", "active");

    rerender(<QueryPipelineStepper events={[guardPassed()]} />);
    expect(screen.getAllByRole("listitem")[0]).toHaveAttribute("data-status", "done");
    expect(screen.getAllByRole("listitem")[1]).toHaveAttribute("data-status", "active");
  });
});
