/**
 * UI fix set 8 (R30): the parser accepts the persona fields on `plan`'s
 * tool calls and on `tool_start`/`tool_result`, and ignores their absence.
 *
 * Kept in its own file rather than appended to `events.test.ts`, which set 9
 * is editing in the same pass for its own additive fields.
 */

import { describe, expect, it } from "vitest";

import { parseAgentEvent } from "./events";

const BASE = {
  version: "v1" as const,
  trace_id: "11111111-1111-4111-8111-111111111111",
  seq: 0,
  ts: "2026-09-13T12:00:00Z",
};

const PERSONA = {
  persona: "Franklin",
  persona_about: "Took the X-ray image that showed the double helix.",
  persona_wikipedia: "https://en.wikipedia.org/wiki/Rosalind_Franklin",
};

describe("parseAgentEvent: the helper persona fields (set 8)", () => {
  it("accepts a plan whose tool calls carry a persona, and one whose calls carry none", () => {
    const withPersona = {
      ...BASE,
      type: "plan" as const,
      payload: {
        narrative: "three layers",
        tool_calls: [{ tool: "cypher_query", call_id: "c1", layer: "layer_1_graph", ...PERSONA }],
      },
    };
    expect(parseAgentEvent("plan", withPersona)).toEqual(withPersona);

    const without = {
      ...BASE,
      type: "plan" as const,
      payload: {
        narrative: "one layer",
        tool_calls: [{ tool: "cypher_query", call_id: "c1", layer: "layer_1_graph" }],
      },
    };
    expect(parseAgentEvent("plan", without)).toEqual(without);

    const nulled = {
      ...BASE,
      type: "plan" as const,
      payload: {
        narrative: "one layer",
        tool_calls: [
          { tool: "cypher_query", call_id: "c1", layer: "layer_1_graph", persona: null, persona_about: null, persona_wikipedia: null },
        ],
      },
    };
    expect(parseAgentEvent("plan", nulled)).toEqual(nulled);
  });

  it("accepts tool_start and tool_result frames with and without a persona", () => {
    const start = {
      ...BASE,
      type: "tool_start" as const,
      payload: { call_id: "c1", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "running", ...PERSONA },
    };
    expect(parseAgentEvent("tool_start", start)).toEqual(start);
    const result = {
      ...BASE,
      type: "tool_result" as const,
      payload: {
        call_id: "c1",
        tool: "pubtator_annotate",
        layer: "layer_3_enrichment",
        status: "ok",
        summary: "ok: 1 record(s)",
        result_count: 1,
        truncated: false,
        ...PERSONA,
      },
    };
    expect(parseAgentEvent("tool_result", result)).toEqual(result);
    const bare = {
      ...BASE,
      type: "tool_start" as const,
      payload: { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "running" },
    };
    expect(parseAgentEvent("tool_start", bare)).toEqual(bare);
  });

  it("rejects a persona field of the wrong type", () => {
    const bad = {
      ...BASE,
      type: "tool_start" as const,
      payload: { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "running", persona: 42 },
    };
    expect(() => parseAgentEvent("tool_start", bad)).toThrow(/tool_start/);
  });
});
