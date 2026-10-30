/**
 * Card 102 (2026-10-07): a reopened saved answer lists its sources.
 *
 * Deployed develop showed "Based on 21 sources cited" and then nothing. The
 * endpoint sent every citation as stored, with `layer` as the wire string
 * ("layer_2_api"), and the client's saved-answer parser kept only the numbers
 * 1, 2 or 3, so it dropped them all. Card 22's own saved-answer test built
 * its citations with numeric layers by hand, past the parser, which is why it
 * stayed green.
 *
 * These tests run the stored shape through the real parser
 * (`fetchHistoryAnswer`, with `fetch` stubbed) into the real screen, so the
 * chain the reader sees is the chain under test.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { render, renderHook, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useRunView } from "../../hooks/useRunView";
import { fetchHistoryAnswer } from "../../lib/api";
import type { AgentEvent } from "../../lib/events";
import { SavedAnswerScreen } from "./SavedAnswerScreen";

interface FixtureCitation {
  display_index: number;
  source_url: string;
  layer: string;
  source: string;
  source_id: string;
  field: string;
}

const FIXTURE = JSON.parse(
  readFileSync(
    path.resolve(__dirname, "../../../e2e/fixtures/card22_brca1_citations.json"),
    "utf8",
  ),
) as { citations: FixtureCitation[]; expected_after: { sources_cited: number; trust_line: string } };

/** A citation as `interactions.citations` stores it: the live `CitationPayload`. */
function stored(c: FixtureCitation, layer: unknown = c.layer) {
  return {
    citation_id: `cit-test-${c.display_index}`,
    display_index: c.display_index,
    source: c.source,
    source_id: c.source_id,
    source_url: c.source_url,
    layer,
    field: c.field,
    claim_text: "A test claim.",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "test licence",
    snapshot_date: null,
    entity_name: null,
  };
}

async function reopen(
  citations: unknown[],
  trustLine: string,
  markdown = "BRCA1 is associated with several conditions [1].",
) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          trace_id: "card102",
          question: "Which diseases are associated with BRCA1?",
          asked_at: "2026-10-07T04:00:00Z",
          depth: "researcher",
          answer_markdown: markdown,
          citations,
          trust_signal: "ask",
          trust_line: trustLine,
        }),
        { status: 200 },
      ),
    ),
  );
  const answer = await fetchHistoryAnswer("token-test", "card102", { baseUrl: "https://api.test" });
  render(
    <SavedAnswerScreen question={answer.question} loading={false} answer={answer} onRunAgain={() => undefined} />,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("a reopened saved answer, from the stored citations", () => {
  it("lists one row per page under its trust line, each naming its layer", async () => {
    // Mutation: restore the numeric-only layer check in `lib/api.ts` and
    // the Sources list never renders (0 rows), red.
    const after = FIXTURE.expected_after;
    await reopen(FIXTURE.citations.map((c) => stored(c)), after.trust_line);

    const line = screen.getByTestId("saved-answer-trust-line");
    expect(line).toHaveTextContent(`Based on ${after.sources_cited} sources cited`);
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows).toHaveLength(after.sources_cited);

    const geneRows = rows.filter((row) => row.textContent?.includes("/gene/672"));
    expect(geneRows).toHaveLength(1);
    expect(geneRows[0]).toHaveTextContent(/1, 6, 9\./);
    expect(geneRows[0]).toHaveTextContent(/live/i);
    const words = rows.map((row) => row.textContent ?? "");
    expect(words.filter((text) => /graph/i.test(text.replace(/medgen/gi, "")))).toHaveLength(4);
    expect(words.filter((text) => /literature/i.test(text))).toHaveLength(5);
  });

  it("still lists a source whose stored layer is not recognised, with its link and no layer word", async () => {
    // Mutation: drop a citation with an unrecognised layer again and this
    // finds one row, not two; guess a layer for it and its row names one.
    const [gene, medgen] = FIXTURE.citations.filter((c) => c.display_index <= 2);
    await reopen([stored(gene), stored(medgen, "layer_4_new")], "Based on 2 sources cited");

    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    const unknown = rows.find((row) => row.textContent?.includes(medgen.source_url));
    expect(unknown).toBeDefined();
    expect(within(unknown as HTMLElement).getByRole("link")).toHaveAttribute("href", medgen.source_url);
    expect(unknown).not.toHaveTextContent(/graph|live|literature/i);
  });
});

/** Three stored citations whose `source` is a tool's internal string, as query 33 and query 1 stored them. */
const TOOL_NAMED: FixtureCitation[] = [
  {
    display_index: 1,
    source: "pathogen_detection",
    source_id: "SAMN00715300",
    source_url: "https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN00715300",
    layer: "layer_2_api",
    field: "isolate",
  },
  {
    display_index: 2,
    source: "clinicaltrials.gov",
    source_id: "NCT00590109",
    source_url: "https://clinicaltrials.gov/study/NCT00590109",
    layer: "layer_3_enrichment",
    field: "brief_title",
  },
  {
    display_index: 3,
    source: "ncbi_efetch",
    source_id: "NCBIGene:672",
    source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
    layer: "layer_2_api",
    field: "summary",
  },
];

/** The live answer's names for the same stored payloads, from the real view. */
function liveNames(citations: FixtureCitation[]): string[] {
  const events = citations.map(
    (c, i) =>
      ({
        type: "citation",
        version: "v1",
        trace_id: "card135",
        seq: i + 1,
        ts: "2026-10-29T00:00:00Z",
        payload: stored(c),
      }) as unknown as AgentEvent,
  );
  const { result } = renderHook(() => useRunView(events));
  return result.current.sources.map((source) => source.name);
}

describe("a reopened saved answer names and cites its sources as the live one does, card 135", () => {
  it("names each tool-named source by its database with its record id, the live answer's own label", async () => {
    // Mutation: restore `entity_name ?? source` on the saved row and the
    // rows read "pathogen_detection", "clinicaltrials.gov", "ncbi_efetch",
    // red; or name the live list differently and the two lists disagree.
    const live = liveNames(TOOL_NAMED);
    expect(live).toEqual([
      "Pathogen Detection SAMN00715300",
      "ClinicalTrials.gov NCT00590109",
      "NCBI Gene 672",
    ]);
    await reopen(TOOL_NAMED.map((c) => stored(c)), "Based on 3 sources cited");
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    rows.forEach((row, i) => {
      expect(row).toHaveTextContent(`${i + 1}. ${live[i]}`);
      expect(row).not.toHaveTextContent(/pathogen_detection|ncbi_efetch|clinicaltrials\.gov /);
    });
  });

  it("names a normal gene answer's rows exactly as the live answer names them", async () => {
    // The BRCA1 run's own citations: no tool names, so nothing changes
    // from the live list's labels.
    const live = liveNames(FIXTURE.citations);
    await reopen(FIXTURE.citations.map((c) => stored(c)), FIXTURE.expected_after.trust_line);
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    const geneRow = rows.find((row) => row.textContent?.includes("/gene/672"));
    expect(geneRow).toHaveTextContent(`1, 6, 9. ${live[0]}`);
    expect(live[0]).toBe("NCBIGene 672");
  });

  it("shows the stored [n] as the live marker, through the real parser into the real screen", async () => {
    // Mutation: drop `citations` from `SavedAnswerMarkdown` in the screen
    // and "[1][2][3]" shows as text, red.
    await reopen(
      TOOL_NAMED.map((c) => stored(c)),
      "Based on 3 sources cited",
      "One isolate, one trial and one gene [1][2][3]. A study [9] is not cited.",
    );
    const body = screen.getByTestId("saved-answer-body");
    expect(body.textContent).not.toContain("[1]");
    expect(body.textContent).toContain("A study [9] is not cited.");
    expect(within(body).getByRole("button", { name: "Source 2, layer 3" })).toBeInTheDocument();
    expect(within(body).getAllByRole("button")).toHaveLength(3);
  });
});
