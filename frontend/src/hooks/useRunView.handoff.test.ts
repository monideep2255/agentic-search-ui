/**
 * UI fix set 8 (R30): the tool-chip derivation carries the helper persona
 * and UPSERTS a call's status when its `tool_result` arrives.
 *
 * The second property is the one that changed. The earlier loop kept the
 * first frame per `call_id` and skipped the result, so a chip read
 * "running" for the life of the run; the handoff badge needs the status.
 * Mutation-checked by hand: restoring first-frame-wins turns the second
 * arm red on `status` and `detail` both.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { useRunView } from "./useRunView";

let seq = 0;

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: `2026-09-13T12:00:0${seq % 10}Z`,
    payload,
  } as AgentEvent;
}

const PERSONA = {
  persona: "Koch",
  persona_about: "Postulates.",
  persona_wikipedia: "https://en.wikipedia.org/wiki/Robert_Koch",
};

describe("useRunView: tool chips carry the helper and follow the result", () => {
  it("reads the persona off tool_start and reports the call as running", () => {
    const events = [
      envelope("tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running", ...PERSONA }),
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.toolCalls).toEqual([
      {
        name: "ncbi_efetch",
        detail: "running",
        layer: 2,
        status: "running",
        persona: "Koch",
        personaAbout: "Postulates.",
        personaWikipedia: "https://en.wikipedia.org/wiki/Robert_Koch",
      },
    ]);
  });

  it("updates the same chip when the tool_result lands, never a second chip", () => {
    const events = [
      envelope("tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running", ...PERSONA }),
      envelope("tool_result", {
        call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok",
        summary: "1 record", result_count: 1, truncated: false, ...PERSONA,
      }),
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.toolCalls).toHaveLength(1);
    expect(result.current.toolCalls[0].status).toBe("ok");
    expect(result.current.toolCalls[0].detail).toBe("1 rows");
  });

  it("leaves persona null for a backend that sends none", () => {
    const events = [
      envelope("tool_start", { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "running" }),
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.toolCalls[0].persona).toBeNull();
    expect(result.current.toolCalls[0].personaAbout).toBeNull();
  });
});
