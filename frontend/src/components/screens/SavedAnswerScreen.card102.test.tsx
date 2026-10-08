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

import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHistoryAnswer } from "../../lib/api";
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

async function reopen(citations: unknown[], trustLine: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          trace_id: "card102",
          question: "Which diseases are associated with BRCA1?",
          asked_at: "2026-10-07T04:00:00Z",
          depth: "researcher",
          answer_markdown: "BRCA1 is associated with several conditions [1].",
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
