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

import { render, renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { HistoryAnswerResponse } from "../../lib/api";
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
import { SavedAnswerScreen, savedSourceRows } from "./SavedAnswerScreen";

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

function source(n: number, url: string, layer: 1 | 2 | 3 = 2, name = "r", tool = "t"): Source {
  return { n, layer, name, tool, evidence: "e", confidence: "c", license: "l", url };
}

/**
 * Card 22 fix round, the owner's decision of 2026-10-06 (J-22-02, A-22-09):
 * the graph's gene link (no trailing slash, layer 1) and the live Datasets
 * gene link (trailing slash, layer 2) are one page. It stays ONE card that
 * names both layers, and both layer groups stay in the list.
 */
const GRAPH_GENE = "https://www.ncbi.nlm.nih.gov/gene/672";
const LIVE_GENE = `${GRAPH_GENE}/`;

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

  it("files a page cited from two layers under the lowest-numbered layer, whichever was cited first", () => {
    // The rule (groupSourcesByLayer's docstring): the card sits under the
    // group of the lowest-numbered layer it was cited from. Both orders are
    // asserted, so a merge that keeps the FIRST citation's layer fails the
    // live-first arm and one that keeps the LAST fails the graph-first arm
    // (J-22-07's surviving mutation M2).
    for (const order of [
      [source(1, GRAPH_GENE, 1, "graph gene", "cypher_query"), source(2, LIVE_GENE, 2, "live gene", "ncbi_datasets")],
      [source(1, LIVE_GENE, 2, "live gene", "ncbi_datasets"), source(2, GRAPH_GENE, 1, "graph gene", "cypher_query")],
    ]) {
      const groups = groupSourcesByLayer(order);
      const graph = groups.find((group) => group.layer === 1);
      const live = groups.find((group) => group.layer === 2);
      expect(graph?.items).toHaveLength(1);
      expect(graph?.items[0].layer).toBe(1);
      expect(graph?.items[0].layers).toEqual([1, 2]);
      expect(graph?.items[0].ns).toHaveLength(2);
      // Name and link from the citation in the layer it sits under; tools from both.
      expect(graph?.items[0].name).toBe("graph gene");
      expect(graph?.items[0].url).toBe(GRAPH_GENE);
      expect(graph?.items[0].tool.split(", ").sort()).toEqual(["cypher_query", "ncbi_datasets"]);
      // The live group does not vanish: it names the page, with no second card.
      expect(live?.items).toHaveLength(0);
      expect(live?.alsoCited).toHaveLength(1);
      expect(live?.alsoCited[0]).toBe(graph?.items[0]);
      expect(citedSourceCounts(order)).toEqual({ pages: 1, layers: 2 });
    }
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

  it("counts every layer a cited page came from when one page is cited from two layers", () => {
    // The graph's gene link has no trailing slash and the live Datasets
    // link has one: one page, one card, cited from two layers. The owner's
    // decision (2026-10-06): the meta line says "from 2 layers". The first
    // build pinned "1 layer" here, which hid the live lookup (J-22-02).
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
    expect(meta).toBe("2 tool calls · 1 source cited from 2 layers");
  });

  it("says no sources cited without a layer clause when nothing was cited", () => {
    const events = runEvents(2, [], "");
    const { meta } = renderHook(() => useRunView(events)).result.current;
    expect(meta).toBe("2 tool calls · 0 sources cited");
  });
});

describe("one page cited from the graph and from a live lookup, on screen", () => {
  it("shows one card naming both layers, keeps the live group, and every marker keeps its layer", async () => {
    const sources = [
      source(1, GRAPH_GENE, 1, "NCBIGene 672", "cypher_query"),
      source(2, LIVE_GENE, 2, "NCBIGene 672", "ncbi_datasets"),
    ];
    render(
      <AnswerScreen
        question="What is BRCA1?"
        claims={[
          { text: "BRCA1 is a gene in the graph.", layer: 1, citations: [1] },
          { text: "The live gene record names it BRCA1.", layer: 2, citations: [2] },
        ]}
        sources={sources}
      />,
    );
    const user = userEvent.setup();
    const disclosure = screen.getByTestId("sources-disclosure");
    await user.click(within(disclosure).getByText(/^sources$/i));
    expect(screen.getByTestId("sources-count")).toHaveTextContent(/^1$/);

    const graph = screen.getByTestId("sources-group-1");
    await user.click(within(graph).getByText("Knowledge graph"));
    const card = within(graph).getByTestId("source-1");
    expect(card).toHaveAttribute("data-layers", "1 2");
    expect(within(card).getByTestId("source-1-markers")).toHaveTextContent("[1][2]");
    expect(within(card).getByTestId("source-1-layers")).toHaveTextContent("L1 · graph, L2 · live");

    const live = screen.getByTestId("sources-group-2");
    expect(within(live).getByTestId("sources-group-2-count")).toHaveTextContent(/^1$/);
    await user.click(within(live).getByText("Live NCBI APIs"));
    const line = within(live).getByTestId("sources-group-2-also-1");
    expect(line).toHaveTextContent("[2]");
    expect(line).toHaveTextContent("listed under Knowledge graph");
    expect(within(live).queryByTestId("source-2")).toBeNull();
  });
});

describe("a reopened saved answer", () => {
  it("lists one row per page, so its rows agree with its stored trust line", () => {
    // J-22-04, A-22-05: "Based on 16 sources cited" above 18 rows, the gene
    // page three times. Mutation: map one row per citation again and this
    // reads 18 rows and 3 gene rows.
    const after = FIXTURE.expected_after;
    const answer: HistoryAnswerResponse = {
      trace_id: "card22",
      question: "Which diseases are associated with BRCA1?",
      asked_at: "2026-09-27T12:00:00Z",
      depth: "researcher",
      answer_markdown: "BRCA1 is associated with several conditions [1].",
      citations: FIXTURE.citations.map((c) => ({
        display_index: c.display_index,
        source: c.source,
        source_url: c.source_url,
        layer: Number(c.layer.slice(6, 7)) as 1 | 2 | 3,
      })),
      trust_signal: "ask",
      trust_line: after.trust_line,
    };
    expect(savedSourceRows(answer.citations)).toHaveLength(after.sources_cited);
    render(<SavedAnswerScreen question={answer.question} loading={false} answer={answer} onRunAgain={() => undefined} />);
    expect(screen.getByTestId("saved-answer-trust-line")).toHaveTextContent(
      `Based on ${after.sources_cited} sources cited`,
    );
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows).toHaveLength(after.sources_cited);
    const geneRows = rows.filter((row) => row.textContent?.includes("/gene/672"));
    expect(geneRows).toHaveLength(1);
    expect(geneRows[0]).toHaveTextContent(/1, 6, 9\./);
  });

  it("names every layer a merged row was cited from and never merges rows without a link", () => {
    const rows = savedSourceRows([
      { display_index: 1, source: "NCBIGene", source_url: GRAPH_GENE, layer: 1 },
      { display_index: 2, source: "NCBIGene", source_url: LIVE_GENE, layer: 2 },
      { display_index: 3, source: "x", source_url: "", layer: 2 },
      { display_index: 4, source: "y", source_url: "", layer: 2 },
    ]);
    expect(rows.map((row) => row.indices)).toEqual([[1, 2], [3], [4]]);
    expect(rows[0].layers).toEqual([1, 2]);
  });
});

describe("the trust line's info card", () => {
  it("says what the sources number counts, and that confirmed counts databases", () => {
    expect(TRUST_LINE_EXPLAINER).toContain("Sources cited counts the record pages this answer cites");
    expect(TRUST_LINE_EXPLAINER).toContain("two links to one page count once");
    expect(TRUST_LINE_EXPLAINER).toContain("two or more independent databases");
    expect(TRUST_LINE_EXPLAINER).not.toMatch(/counted by the database/);
  });

  it("explains a not-yet-confirmed answer that is incomplete, not only one missing a second database", () => {
    // J-22-08: the backend also floors an incomplete answer (a search that
    // did not finish, more records than the answer lists) at "not yet
    // confirmed". Mutation: revert to the one-cause sentence and this fails.
    expect(TRUST_LINE_EXPLAINER).toContain("has not been found in a second independent database");
    expect(TRUST_LINE_EXPLAINER).toContain("or this answer may be incomplete");
    expect(TRUST_LINE_EXPLAINER).toContain("a search did not finish");
  });
});
