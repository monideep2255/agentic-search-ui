/**
 * Card 22 (owner, 2026-10-06): every total says what it counts.
 *
 * One BRCA1 Researcher answer showed "13 tools · 18 sources from 3 layers",
 * a Sources heading of 17 and "Based on 17 sources". The meta line counted
 * numbered citations; the other two counted pages. The owner chose one count:
 * every number that says "sources" counts distinct pages under one key, and a
 * trailing slash does not make a second page.
 *
 * The cases and the rebuilt evidence come from the fixture the backend test
 * (`tests/system_03_search_agent/synthesis/test_trust_line_names_its_count.py`)
 * reads too, so the two page keys are held to the same inputs.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent, Layer } from "../../lib/events";
import { useRunView } from "../../hooks/useRunView";
import {
  AnswerScreen,
  TRUST_LINE_EXPLAINER,
  citedSourceCounts,
  groupSourcesByLayer,
  sourcePageKey,
  type Source,
} from "./AnswerScreen";

interface FixtureCitation {
  display_index: number;
  source_url: string;
  layer: Layer;
  source: string;
  source_id: string;
  field: string;
}

interface Fixture {
  page_key_cases: [string, string][];
  citations: FixtureCitation[];
  evidence_before: { meta_sources: number; sources_heading: number; tool_calls: number };
  expected_after: {
    sources_cited: number;
    layers: number;
    groups: Record<string, number>;
    meta: string;
    trust_line: string;
  };
}

const FIXTURE = JSON.parse(
  readFileSync(
    path.resolve(__dirname, "../../../e2e/fixtures/card22_brca1_citations.json"),
    "utf8",
  ),
) as Fixture;

let seq = 0;
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "card22", seq, ts: "2026-10-06T12:00:00Z", payload } as AgentEvent;
}

function toolResult(n: number): AgentEvent {
  return envelope("tool_result", {
    call_id: `call-${n}`,
    tool: "cypher_query",
    layer: "layer_1_graph",
    status: "ok",
    summary: "",
    result_count: 1,
    truncated: false,
  });
}

function citation(c: FixtureCitation): AgentEvent {
  return envelope("citation", {
    citation_id: `cid-${c.display_index}`,
    display_index: c.display_index,
    source: c.source,
    source_id: c.source_id,
    source_url: c.source_url,
    layer: c.layer,
    field: c.field,
    claim_text: "x",
    evidence_kind: "primary_assertion",
    assertion_confidence: "asserted",
    population_ancestry_context: null,
    license: "public_domain_us_gov",
  });
}

function runEvents(toolCalls: number, citations: FixtureCitation[], trustLine: string): AgentEvent[] {
  return [
    envelope("guard", { passed: true, category: "ok", reason: null }),
    ...Array.from({ length: toolCalls }, (_, n) => toolResult(n + 1)),
    envelope("token", {
      text: "BRCA1 is associated with several conditions [1]. ",
      marker_ids: citations.length > 0 ? [`cid-${citations[0].display_index}`] : [],
    }),
    ...citations.map(citation),
    envelope("trust_signal", { outcome: "ask", risk_tier: "high", grounded: true, triangulated: false }),
    envelope("done", {
      total_cost_usd: 0.01,
      total_tool_calls: toolCalls,
      elapsed_ms: 11200,
      trust_outcome: "ask",
      trust_line: trustLine,
    }),
  ];
}

function source(n: number, url: string, layer: 1 | 2 | 3 = 2): Source {
  return { n, layer, name: "r", tool: "t", evidence: "e", confidence: "c", license: "l", url };
}

describe("the page key", () => {
  it.each(FIXTURE.page_key_cases)("keys %j as %j", (url, key) => {
    expect(sourcePageKey(url)).toBe(key);
  });

  it("keys a missing link as no page", () => {
    expect(sourcePageKey(undefined)).toBe("");
    expect(sourcePageKey(null)).toBe("");
  });
});

describe("the Sources list", () => {
  it("shows a link with and without a trailing slash as one card carrying both markers", () => {
    const groups = groupSourcesByLayer([
      source(1, "https://www.ncbi.nlm.nih.gov/gene/672"),
      source(2, "https://www.ncbi.nlm.nih.gov/gene/672/"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].items).toHaveLength(1);
    expect(groups[0].items[0].ns).toEqual([1, 2]);
  });

  it("never merges two sources that have no link", () => {
    const groups = groupSourcesByLayer([source(1, ""), source(2, "")]);
    expect(groups[0].items).toHaveLength(2);
  });

  it("keeps the first link's spelling on the merged card", () => {
    const [group] = groupSourcesByLayer([
      source(1, "https://www.ncbi.nlm.nih.gov/gene/672/"),
      source(2, "https://www.ncbi.nlm.nih.gov/gene/672"),
    ]);
    expect(group.items[0].url).toBe("https://www.ncbi.nlm.nih.gov/gene/672/");
  });
});

describe("the BRCA1 evidence of 2026-09-27", () => {
  it("reproduces the old numbers under the old exact-link count (populate-check)", () => {
    const urls = FIXTURE.citations.map((c) => c.source_url);
    expect(urls).toHaveLength(FIXTURE.evidence_before.meta_sources);
    expect(new Set(urls).size).toBe(FIXTURE.evidence_before.sources_heading);
  });

  it("states one number for sources in the meta line, the Sources heading and the trust line", () => {
    const after = FIXTURE.expected_after;
    const events = runEvents(FIXTURE.evidence_before.tool_calls, FIXTURE.citations, after.trust_line);
    const view = renderHook(() => useRunView(events)).result.current;

    expect(view.landed).toBe(true);
    expect(view.meta).toBe(after.meta);
    expect(citedSourceCounts(view.sources)).toEqual({ pages: after.sources_cited, layers: after.layers });
    const groups = Object.fromEntries(
      groupSourcesByLayer(view.sources).map((group) => [String(group.layer), group.items.length]),
    );
    expect(groups).toEqual(after.groups);

    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={view.claims}
        sources={view.sources}
        meta={view.meta}
        trust={view.trust}
      />,
    );
    expect(screen.getByTestId("answer-meta")).toHaveTextContent(
      `${after.sources_cited} sources cited from ${after.layers} layers`,
    );
    expect(screen.getByTestId("sources-count")).toHaveTextContent(new RegExp(`^${after.sources_cited}$`));
    expect(screen.getByTestId("trust-line")).toHaveTextContent(
      `Based on ${after.sources_cited} sources cited, not yet confirmed`,
    );
  });
});

describe("the meta line's words", () => {
  it("says tool calls, and sources cited from layers", () => {
    const events = runEvents(13, FIXTURE.citations, FIXTURE.expected_after.trust_line);
    const { meta } = renderHook(() => useRunView(events)).result.current;
    expect(meta).toMatch(/^13 tool calls · \d+ sources cited from \d+ layers$/);
  });

  it("uses the singular for one of each", () => {
    const one = FIXTURE.citations.slice(0, 1);
    const events = runEvents(1, one, "Based on 1 source cited");
    const { meta } = renderHook(() => useRunView(events)).result.current;
    expect(meta).toBe("1 tool call · 1 source cited from 1 layer");
  });

  it("counts layers as the Sources list groups them when one page is cited from two layers", () => {
    // The graph's gene link has no trailing slash and the live Datasets link
    // has one: one page, one card, filed under the layer cited first. The
    // meta line must say one layer, as the list shows, not two.
    const graph: FixtureCitation = {
      display_index: 1,
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
      layer: "layer_1_graph",
      source: "NCBIGene",
      source_id: "NCBIGene:672",
      field: "symbol",
    };
    const live: FixtureCitation = { ...graph, display_index: 2, source_url: `${graph.source_url}/`, layer: "layer_2_api" };
    const events = runEvents(2, [graph, live], "Based on 1 source cited");
    const { meta, sources } = renderHook(() => useRunView(events)).result.current;
    expect(sources).toHaveLength(2);
    expect(meta).toBe("2 tool calls · 1 source cited from 1 layer");
  });

  it("says no sources cited without a layer clause when nothing was cited", () => {
    const events = runEvents(2, [], "");
    const { meta } = renderHook(() => useRunView(events)).result.current;
    expect(meta).toBe("2 tool calls · 0 sources cited");
  });
});

describe("the trust line's info card", () => {
  it("says what the sources number counts, and that confirmed counts databases", () => {
    expect(TRUST_LINE_EXPLAINER).toContain("Sources cited counts the record pages this answer cites");
    expect(TRUST_LINE_EXPLAINER).toContain("two links to one page count once");
    expect(TRUST_LINE_EXPLAINER).toContain("two or more independent databases");
    expect(TRUST_LINE_EXPLAINER).not.toMatch(/counted by the database/);
  });
});
