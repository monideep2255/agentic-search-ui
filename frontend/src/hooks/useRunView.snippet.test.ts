/**
 * Card 29: the one abstract sentence under a cited paper, as it travels from
 * the wire to the source list.
 *
 * The server sends the listing's citations before the writer runs, then
 * sends a paper's citation again with `snippet` once the batched pick is
 * back. Pinned here: the later send carries the sentence to the source, the
 * number and record stay as first shown, a send with no sentence leaves the
 * source without the field, and the sentence alone never makes two sends
 * count as different citations.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { parseAgentEvent, type AgentEvent } from "../lib/events";
import { updatesCitation, useRunView } from "./useRunView";

let seq = 0;
function ev(type: string, payload: Record<string, unknown>): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "t29", seq, ts: "2026-10-15T00:00:00Z", payload } as unknown as AgentEvent;
}

const SENTENCE = "Caffeine intake of three milligrams per kilogram improved performance in trained cyclists.";

const citation = (extra: Record<string, unknown> = {}): AgentEvent =>
  ev("citation", {
    citation_id: "k1",
    display_index: 1,
    source: "pubmed",
    source_id: "31234567",
    source_url: "https://pubmed.ncbi.nlm.nih.gov/31234567/",
    layer: "layer_2_api",
    field: "title",
    claim_text: "Caffeine and cycling",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
    ...extra,
  });

const token = ev("token", {
  text: "Caffeine and cycling [1].",
  marker_ids: ["k1"],
  kind: "claim",
});
const done = ev("done", { total_cost_usd: 0.01, total_tool_calls: 1, elapsed_ms: 9000, trust_outcome: "answer" });

const view = (events: AgentEvent[]) => renderHook(() => useRunView(events)).result.current;

describe("useRunView: the abstract sentence on a paper's source", () => {
  it("carries the sentence from a citation sent again after the listing", () => {
    // Mutation that turns this red: leave "snippet" out of the fields
    // `updatesCitation` ignores, so the second send is dropped as a conflict.
    const now = view([citation(), token, citation({ snippet: SENTENCE }), done]);
    expect(now.sources).toHaveLength(1);
    expect(now.sources[0]!.snippet).toBe(SENTENCE);
    expect(now.sources[0]!.n).toBe(1);
  });

  it("leaves the source without the field when no sentence was picked", () => {
    const now = view([citation(), token, citation({ snippet: null }), done]);
    expect(now.sources[0]!.snippet).toBeUndefined();
  });

  it("takes a sentence that arrives with the first send", () => {
    const now = view([citation({ snippet: SENTENCE }), token, done]);
    expect(now.sources[0]!.snippet).toBe(SENTENCE);
  });

  it("still refuses a send that changes the number or the record", () => {
    const renumbered = citation({ display_index: 4, snippet: SENTENCE });
    const otherRecord = citation({ source_url: "https://pubmed.ncbi.nlm.nih.gov/999/", snippet: SENTENCE });
    const now = view([citation(), token, renumbered, otherRecord, done]);
    expect(now.sources).toHaveLength(1);
    expect(now.sources[0]!.snippet).toBeUndefined();
  });

  it("reads a send as the same citation when only the sentence was added", () => {
    const early = (citation() as unknown as { payload: Parameters<typeof updatesCitation>[0] }).payload;
    expect(updatesCitation(early, { ...early, snippet: SENTENCE })).toBe(true);
    expect(updatesCitation(early, { ...early, snippet: SENTENCE, display_index: 2 })).toBe(false);
  });
});

describe("the citation event contract: snippet is optional and a string or null", () => {
  const wire = (extra: Record<string, unknown>) => {
    const event = citation(extra) as unknown as Record<string, unknown>;
    return event;
  };

  it("parses a citation with a sentence, with null, and with the field absent", () => {
    for (const extra of [{ snippet: SENTENCE }, { snippet: null }, {}]) {
      const event = wire(extra);
      expect(parseAgentEvent("citation", event).type).toBe("citation");
    }
  });

  it("refuses a sentence that is not a string", () => {
    expect(() => parseAgentEvent("citation", wire({ snippet: 7 }))).toThrow();
  });
});
