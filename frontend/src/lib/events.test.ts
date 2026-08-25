import { describe, expect, it } from "vitest";
import {
  KNOWN_EVENT_TYPES,
  parseAgentEvent,
  type AgentEvent,
  type CitationPayload,
  type DonePayload,
  type ErrorPayload,
  type GuardPayload,
  type PlanPayload,
  type ThinkPayload,
  type ToolResultPayload,
  type ToolStartPayload,
  type TokenPayload,
  type TrustSignalPayload,
} from "./events";

/**
 * Sample envelopes below are hand-built to match
 * `src/system_03_search_agent/contracts/events.py`'s Pydantic models
 * field-for-field, cross-checked against that file directly (not against
 * Section 2.3's prose alone), per T-1.2-04's instructions. Each sample is
 * used two ways: a compile-time `satisfies AgentEvent` check (the
 * TypeScript union accepts the real shape) and a runtime
 * `parseAgentEvent` check (the defensive parser accepts the same shape
 * when it arrives as untyped JSON off the wire).
 */

const BASE = {
  version: "v1" as const,
  trace_id: "11111111-1111-4111-8111-111111111111",
  seq: 0,
  ts: "2026-07-28T12:00:00Z",
};

describe("AgentEvent union: every non-cost payload shape", () => {
  it("accepts a guard event", () => {
    const payload: GuardPayload = { passed: true, category: "ok", reason: null };
    const event = { ...BASE, type: "guard" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("guard", event)).toEqual(event);
  });

  it("accepts a guard event that failed, with a reason", () => {
    const payload: GuardPayload = {
      passed: false,
      category: "off_topic",
      reason: "query is unrelated to biomedical search",
    };
    const event = { ...BASE, type: "guard" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("guard", event)).toEqual(event);
  });

  it("accepts a think event with resolved entities", () => {
    const payload: ThinkPayload = {
      narrative: "Resolving cystic fibrosis to a CURIE before planning tool calls.",
      query_class: "single_hop",
      resolved_entities: [
        { text: "cystic fibrosis", curie: "MONDO:0009061", confidence: 0.97 },
      ],
      clarifying_question: null,
    };
    const event = { ...BASE, type: "think" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("think", event)).toEqual(event);
  });

  it("accepts a plan event with tool calls", () => {
    const payload: PlanPayload = {
      narrative: "Querying the graph, then confirming against dbSNP.",
      tool_calls: [
        { tool: "cypher_query", call_id: "call-1", layer: "layer_1_graph" },
        { tool: "ncbi_dbsnp", call_id: "call-2", layer: "layer_2_api" },
      ],
    };
    const event = { ...BASE, type: "plan" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("plan", event)).toEqual(event);
  });

  it("accepts a tool_start event", () => {
    const payload: ToolStartPayload = {
      call_id: "call-1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "ok",
    };
    const event = { ...BASE, type: "tool_start" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("tool_start", event)).toEqual(event);
  });

  it("accepts a tool_result event (extends tool_start's fields)", () => {
    const payload: ToolResultPayload = {
      call_id: "call-1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "ok",
      summary: "Found 3 matching gene nodes.",
      result_count: 3,
      truncated: false,
    };
    const event = { ...BASE, type: "tool_result" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("tool_result", event)).toEqual(event);
  });

  /**
   * T-4.16-01. These two are a pair and they guard opposite sides of one
   * change, so neither is redundant.
   *
   * The first is the one that would have taken the deployed app down.
   * The backend now emits `tool_start` with `status: "running"`, because a
   * start event is written before dispatch and cannot know an outcome. This
   * guard is a RUNTIME check, and `parseAgentEvent` THROWS on a payload it
   * rejects rather than returning null. That throw propagates out of
   * `consumeEventStream` into `useAgentRun`'s catch, which sets
   * `status: "error"` and abandons the stream.
   *
   * So had the union been widened on the producer alone, every query would
   * have died in the browser at the FIRST tool frame, with no answer shown
   * at all. Not a dropped chip, a dead run. Recorded precisely because the
   * first draft of this comment guessed "silently dropped", and the test
   * below is what corrected it: the assertion was written as `toBeNull()`
   * and failed, which is the whole argument for writing the test rather
   * than reasoning about the guard.
   *
   * The second pins the re-narrowing. `isToolResultPayload` delegates to
   * `isToolStartPayload`, so widening the start guard widens the result
   * guard too unless it is stopped explicitly. A finished call reporting
   * itself as still running would leave a chip spinning for ever.
   */
  it("accepts a tool_start carrying the running status", () => {
    const payload: ToolStartPayload = {
      call_id: "call-1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "running",
    };
    const event = { ...BASE, type: "tool_start" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("tool_start", event)).toEqual(event);
  });

  it("rejects a tool_result claiming the running status", () => {
    const payload = {
      call_id: "call-1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "running",
      summary: "Found 3 matching gene nodes.",
      result_count: 3,
      truncated: false,
    };
    const event = { ...BASE, type: "tool_result", payload };
    expect(() => parseAgentEvent("tool_result", event)).toThrow(
      /does not match the "tool_result" payload schema/,
    );
  });

  it("accepts a token event, including one carrying marker_ids", () => {
    const payload: TokenPayload = {
      text: "CFTR is the gene most commonly implicated",
      marker_ids: ["cit-1", "cit-2"],
    };
    const event = { ...BASE, type: "token" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("token", event)).toEqual(event);
  });

  it("accepts a citation event", () => {
    const payload: CitationPayload = {
      citation_id: "cit-1",
      display_index: 1,
      source: "ClinVar",
      source_id: "VCV000007105",
      source_url: "https://www.ncbi.nlm.nih.gov/clinvar/VCV000007105",
      layer: "layer_1_graph",
      field: "clinical_significance",
      claim_text: "Pathogenic for cystic fibrosis",
      evidence_kind: "graph_node",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public_domain",
    };
    const event = { ...BASE, type: "citation" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("citation", event)).toEqual(event);
  });

  // T-4.10-07: snapshot_date and entity_name, both additive and optional.
  // A payload omitting them (above) still validates; these cover a real
  // server payload that sends both, and one where the server states a
  // real value for each.

  it("accepts a citation event whose payload states both new fields as null", () => {
    const payload: CitationPayload = {
      citation_id: "cit-1",
      display_index: 1,
      source: "ClinVar",
      source_id: "VCV000007105",
      source_url: "https://www.ncbi.nlm.nih.gov/clinvar/VCV000007105",
      layer: "layer_1_graph",
      field: "clinical_significance",
      claim_text: "Pathogenic for cystic fibrosis",
      evidence_kind: "graph_node",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public_domain",
      snapshot_date: null,
      entity_name: null,
    };
    const event = { ...BASE, type: "citation" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("citation", event)).toEqual(event);
  });

  it("accepts a citation event whose payload states real values for both new fields", () => {
    const payload: CitationPayload = {
      citation_id: "cit-1",
      display_index: 1,
      source: "NCBI Gene",
      source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
      layer: "layer_1_graph",
      field: "name",
      claim_text: "BRCA1 DNA repair associated",
      evidence_kind: "primary_assertion",
      assertion_confidence: "asserted",
      population_ancestry_context: null,
      license: "public_domain_us_gov",
      snapshot_date: "2026-04-22",
      entity_name: "BRCA1",
    };
    const event = { ...BASE, type: "citation" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("citation", event)).toEqual(event);
  });

  it("rejects a citation event whose snapshot_date is not a string or null", () => {
    const payload = {
      citation_id: "cit-1",
      display_index: 1,
      source: "NCBI Gene",
      source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
      layer: "layer_1_graph",
      field: "name",
      claim_text: "BRCA1 DNA repair associated",
      evidence_kind: "primary_assertion",
      assertion_confidence: "asserted",
      population_ancestry_context: null,
      license: "public_domain_us_gov",
      snapshot_date: 20260422,
      entity_name: "BRCA1",
    };
    const event = { ...BASE, type: "citation" as const, payload };
    expect(() => parseAgentEvent("citation", event)).toThrow();
  });

  it("accepts a trust_signal event", () => {
    const payload: TrustSignalPayload = {
      outcome: "answer",
      risk_tier: "low",
      grounded: true,
      triangulated: true,
    };
    const event = { ...BASE, type: "trust_signal" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("trust_signal", event)).toEqual(event);
  });

  it("accepts a non-fatal error event", () => {
    const payload: ErrorPayload = {
      fatal: false,
      scope: "tool",
      source: "ncbi_efetch",
      error_class: "transient",
      message: "NCBI E-utilities request timed out, retrying with backoff",
      retry_after_s: 2,
    };
    const event = { ...BASE, type: "error" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("error", event)).toEqual(event);
  });

  it("accepts a fatal error event", () => {
    const payload: ErrorPayload = {
      fatal: true,
      scope: "run",
      source: "agent_loop",
      error_class: "unexpected",
      message: "unrecoverable failure in the write step",
      retry_after_s: 0,
    };
    const event = { ...BASE, type: "error" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("error", event)).toEqual(event);
  });

  it("accepts a done event", () => {
    const payload: DonePayload = {
      total_cost_usd: 0.0421,
      total_tool_calls: 2,
      elapsed_ms: 4231,
      trust_outcome: "answer",
    };
    const event = { ...BASE, type: "done" as const, payload } satisfies AgentEvent;
    expect(parseAgentEvent("done", event)).toEqual(event);
  });

  it("KNOWN_EVENT_TYPES lists all ten non-cost types and never cost", () => {
    expect(KNOWN_EVENT_TYPES).toEqual([
      "guard",
      "think",
      "plan",
      "tool_start",
      "tool_result",
      "token",
      "citation",
      "trust_signal",
      "error",
      "done",
    ]);
    expect(KNOWN_EVENT_TYPES).not.toContain("cost");
  });
});

describe("parseAgentEvent: rejects malformed or unexpected frames", () => {
  it("rejects a cost event: no client-side variant exists for a non-operator caller", () => {
    const costLikeEvent = {
      ...BASE,
      type: "cost",
      payload: {
        query_cost_usd: 0.01,
        query_cap_usd: 1.0,
        cap_fraction: 0.01,
        model_tier: "plan",
      },
    };
    expect(() => parseAgentEvent("cost", costLikeEvent)).toThrow(/unknown or unsupported event type/);
  });

  it("rejects a payload missing a required field", () => {
    const malformed = {
      ...BASE,
      type: "guard",
      payload: { passed: true, category: "ok" }, // missing `reason`
    };
    expect(() => parseAgentEvent("guard", malformed)).toThrow(/does not match/);
  });

  it("rejects a payload with a value outside the declared enum", () => {
    const malformed = {
      ...BASE,
      type: "guard",
      payload: { passed: true, category: "not_a_real_category", reason: null },
    };
    expect(() => parseAgentEvent("guard", malformed)).toThrow(/does not match/);
  });

  it("rejects a frame whose data.type does not match the SSE event: name", () => {
    const mismatched = {
      ...BASE,
      type: "think",
      payload: { passed: true, category: "ok", reason: null },
    };
    expect(() => parseAgentEvent("guard", mismatched)).toThrow(/does not match the SSE frame/);
  });

  it("rejects an unsupported contract version", () => {
    const wrongVersion = {
      ...BASE,
      version: "v2",
      type: "guard",
      payload: { passed: true, category: "ok", reason: null },
    };
    expect(() => parseAgentEvent("guard", wrongVersion)).toThrow(/unsupported event contract version/);
  });

  it("rejects raw data that is not an object", () => {
    expect(() => parseAgentEvent("guard", "not an object")).toThrow(/is not an object/);
  });
});
