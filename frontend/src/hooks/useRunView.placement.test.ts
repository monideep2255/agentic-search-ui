/**
 * The record listing and the written summary, as the view derives them.
 * Build phase 8.7, T-8.7-03 (2026-09-27, card 50).
 *
 * The server sends the code-built count line and the record listing
 * (`placement: "listing"`) the moment the searches end, and the written
 * summary later. The screen shows the records at once and the summary above
 * them when it lands.
 *
 * WHAT THIS PINS:
 * - listing tokens become claims tagged `placement: "listing"` the moment
 *   they arrive, before any summary, and the run is in its Write step;
 * - `claims` stays in arrival order: a summary that lands later is appended,
 *   so no record already on screen changes its index, which is its identity;
 * - the two regions are classified apart: a listing that ends in its
 *   findings tail, or with a heading or table header pending, does not turn
 *   the summary's first sentence into a record line or give it that heading;
 * - a token with no placement, from an older producer, is the summary, and
 *   its claims carry no placement key at all, exactly as before this phase;
 * - Stop counts summary sentences only (`summarySentencesShown`).
 *
 * WHAT IT DOES NOT PIN: where the regions render (the AnswerScreen test) or
 * the server's own choice of which tokens are the listing (builder A's).
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent, TokenPayload } from "../lib/events";
import { summarySentencesShown } from "../components/screens/AnswerScreen";
import { FINDINGS_TAIL_NOTE_PREFIX, useRunView } from "./useRunView";

let seq = 0;
function ev(type: string, payload: Record<string, unknown>): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "t87", seq, ts: "2026-09-27T00:00:00Z", payload } as unknown as AgentEvent;
}

const listing = (payload: Omit<TokenPayload, "placement">): AgentEvent =>
  ev("token", { ...payload, placement: "listing" });
const summary = (payload: Omit<TokenPayload, "placement">): AgentEvent =>
  ev("token", { ...payload, placement: "summary" });

const citation = (n: number): AgentEvent =>
  ev("citation", {
    citation_id: `k${n}`,
    display_index: n,
    source: "MedGen",
    source_id: `C00${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C00${n}`,
    layer: "layer_2_api",
    field: "name",
    claim_text: `Disease ${n}`,
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  });

const search: AgentEvent[] = [
  ev("guard", { passed: true, category: "ok", reason: null }),
  ev("think", { narrative: "n", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
  ev("plan", { narrative: "p", tool_calls: [{ tool: "ncbi_efetch", call_id: "c1", layer: "layer_2_api" }] }),
  ev("tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running" }),
  ev("tool_result", {
    call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok",
    summary: "", result_count: 3, truncated: false,
  }),
];

const listingTokens: AgentEvent[] = [
  listing({ text: "Found 3 disease records for BRCA1 [1][2][3].", marker_ids: ["k1", "k2", "k3"], kind: "claim" }),
  listing({ text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
  listing({ text: "Disease records found\n\n", marker_ids: [], kind: "heading" }),
  listing({ text: "", marker_ids: [], kind: "table_header", cells: ["Disease", "MedGen record"] }),
  ...[1, 2, 3].map((n) =>
    listing({ text: `Disease name: Disease ${n} [${n}].`, marker_ids: [`k${n}`], kind: "table_row", cells: [`Disease ${n}`, `C00${n}`] }),
  ),
  citation(1),
  citation(2),
  citation(3),
];

const summaryTokens: AgentEvent[] = [
  summary({ text: "BRCA1 is linked to familial breast cancer [1].", marker_ids: ["k1"], kind: "claim", emphasis: ["BRCA1"] }),
  summary({ text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
  summary({ text: "It is also linked to Disease 3 [3].", marker_ids: ["k3"], kind: "claim" }),
];

const landing: AgentEvent[] = [
  ev("trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: null, scope: "answer" }),
  ev("done", { total_cost_usd: 0.01, total_tool_calls: 1, elapsed_ms: 12000, trust_outcome: "answer" }),
];

const view = (events: AgentEvent[]) => renderHook(() => useRunView(events)).result.current;

describe("useRunView: the record listing and the summary (build phase 8.7)", () => {
  it("makes the listing's claims the moment they arrive, tagged as the listing, before any summary", () => {
    const now = view([...search, ...listingTokens]);
    expect(now.claims.map((claim) => claim.text)).toEqual([
      "Found 3 disease records for BRCA1.",
      "Disease name: Disease 1.",
      "Disease name: Disease 2.",
      "Disease name: Disease 3.",
    ]);
    expect(now.claims.every((claim) => claim.placement === "listing")).toBe(true);
    // Records with their citations, resolved: numbers 1 to 3, not pending.
    expect(now.claims.map((claim) => claim.citations)).toEqual([[1, 2, 3], [1], [2], [3]]);
    expect(now.claims[1]!.tableHeader).toEqual(["Disease", "MedGen record"]);
    expect(now.claims[1]!.heading).toBe("Disease records found");
    expect(now.activeStep).toBe("Write");
    expect(now.landed).toBe(false);
    expect(summarySentencesShown(now.claims), "records counted as answer sentences").toBe(0);
  });

  it("appends the summary when it lands, so no record changes its index", () => {
    const before = view([...search, ...listingTokens]);
    const after = view([...search, ...listingTokens, ...summaryTokens, ...landing]);
    // Arrival order: the four listing claims keep indexes 0 to 3.
    expect(after.claims.slice(0, 4).map((claim) => claim.text)).toEqual(before.claims.map((claim) => claim.text));
    expect(after.claims.slice(4).map((claim) => claim.text)).toEqual([
      "BRCA1 is linked to familial breast cancer.",
      "It is also linked to Disease 3.",
    ]);
    // The summary's claims carry no placement key: they are what every claim was before 8.7.
    expect(after.claims.slice(4).every((claim) => !("placement" in claim))).toBe(true);
    expect(summarySentencesShown(after.claims)).toBe(2);
    expect(after.landed).toBe(true);
  });

  it("classifies the summary apart from the listing: no heading, table header or findings tail carries over", () => {
    // A listing that ends inside its findings tail, with a heading and a
    // table header still pending, then the summary. Populate-check: in ONE
    // region, the same sequence does carry all three into the next sentence.
    const trailing: TokenPayload[] = [
      { text: `${FINDINGS_TAIL_NOTE_PREFIX} but not written about.`, marker_ids: [], kind: "note" },
      { text: "Disease name: Disease 1 [1].", marker_ids: ["k1"], kind: "claim" },
      { text: "More records\n\n", marker_ids: [], kind: "heading" },
      { text: "", marker_ids: [], kind: "table_header", cells: ["Disease", "Id"] },
    ];
    const lead: TokenPayload = { text: "Disease name: Disease 2 is the one asked about [2].", marker_ids: ["k2"], kind: "table_row" };

    const oneRegion = view([
      ...search,
      ...trailing.map((payload) => ev("token", payload as unknown as Record<string, unknown>)),
      ev("token", lead as unknown as Record<string, unknown>),
      citation(1),
      citation(2),
    ]);
    const leakedInto = oneRegion.claims[oneRegion.claims.length - 1]!;
    expect(leakedInto.heading).toBe("More records");
    expect(leakedInto.tableHeader).toEqual(["Disease", "Id"]);

    const twoRegions = view([
      ...search,
      ...trailing.map((payload) => listing(payload)),
      summary(lead),
      citation(1),
      citation(2),
    ]);
    const summaryLead = twoRegions.claims.find((claim) => claim.placement !== "listing")!;
    expect(summaryLead.text).toBe("Disease name: Disease 2 is the one asked about.");
    expect(summaryLead.heading, "the listing's pending heading attached to the summary").toBeUndefined();
    expect(summaryLead.tableHeader, "the listing's table header attached to the summary").toBeUndefined();
    expect(summaryLead.paragraph).toBe(0);
  });

  it("does not read the summary's first sentence as part of a listing that ended in its findings tail", () => {
    const tail: TokenPayload[] = [
      { text: `${FINDINGS_TAIL_NOTE_PREFIX} but not written about.`, marker_ids: [], kind: "note" },
      { text: "Disease name: Disease 1 [1].", marker_ids: ["k1"], kind: "claim" },
    ];
    const lead: TokenPayload = { text: "Disease name: Disease 2 is the one asked about [2].", marker_ids: ["k2"], kind: "claim" };
    // Populate-check: in ONE region, the lead is read as a record line.
    const oneRegion = view([
      ...search,
      ...[...tail, lead].map((payload) => ev("token", payload as unknown as Record<string, unknown>)),
      citation(1),
      citation(2),
    ]);
    expect(oneRegion.claims[oneRegion.claims.length - 1]!.findingsTail).toBe(true);

    const twoRegions = view([...search, ...tail.map((payload) => listing(payload)), summary(lead), citation(1), citation(2)]);
    const summaryLead = twoRegions.claims.find((claim) => claim.placement !== "listing")!;
    expect(summaryLead.findingsTail, "the summary was read as part of the listing's findings tail").toBeUndefined();
  });

  it("reads a token with no placement, an older producer's, as the summary, exactly as before", () => {
    const strip = (event: AgentEvent): AgentEvent => {
      if (event.type !== "token") return event;
      const { placement: _dropped, ...payload } = event.payload;
      void _dropped;
      return { ...event, payload } as AgentEvent;
    };
    const asSummary = (event: AgentEvent): AgentEvent =>
      event.type === "token" ? ({ ...event, payload: { ...event.payload, placement: "summary" } } as AgentEvent) : event;

    // Today's develop order: the count line, the prose, then the listing, all
    // in one region.
    const today = [...search, ...listingTokens, ...summaryTokens, ...landing];
    const withoutPlacement = view(today.map(strip));
    // Populate-check: the stripped stream really carries no placement.
    expect(today.map(strip).some((event) => event.type === "token" && "placement" in event.payload)).toBe(false);

    expect(withoutPlacement.claims.every((claim) => !("placement" in claim))).toBe(true);
    expect(withoutPlacement.claims).toEqual(view(today.map(asSummary)).claims);
    expect(summarySentencesShown(withoutPlacement.claims)).toBe(withoutPlacement.claims.length);
  });
});
