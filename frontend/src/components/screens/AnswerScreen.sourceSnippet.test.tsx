/**
 * The one-sentence abstract snippet under a cited paper (build phase 8.8,
 * "card 44", "answer on top, evidence below", DECISIONS.md 2026-09-25).
 *
 * Pins three behaviours in the source list's per-record card:
 *
 *   1. A record whose `Source.snippet` is set shows it, quoted, under the
 *      title, and it reads even while the record's own `<details>` stays
 *      collapsed (the whole point of the product-owner request: the
 *      sentence must not be one more click away).
 *   2. A record with no snippet renders no snippet element at all: no
 *      empty line, no stray quote marks.
 *   3. `groupSourcesByLayer` carries `snippet` through its merge exactly
 *      like every other per-record field.
 *
 * Follows the render harness and testid conventions
 * `AnswerScreen.sourceGrouping.test.tsx` already established, so this file
 * reads as a sibling of that one rather than a new pattern.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerScreen, groupSourcesByLayer } from "./AnswerScreen";
import type { Claim, Source } from "./AnswerScreen";

const GENE_WITH_SNIPPET: Source = {
  n: 1,
  layer: 1,
  name: "NCBI Gene 672 · BRCA1",
  tool: "cypher_query",
  evidence: "curated assertion",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/gene/672",
  snippet: "Carriers of pathogenic BRCA1 variants have a substantially increased lifetime risk of breast cancer.",
};

const MEDGEN_NO_SNIPPET: Source = {
  n: 2,
  layer: 2,
  name: "MedGen C0677776 · HBOC",
  tool: "ncbi_efetch",
  evidence: "curated record",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/medgen/C0677776",
};

const CLAIMS: Claim[] = [
  { text: "Gene 672 causes disease A.", layer: 1, citations: [1] },
  { text: "MedGen confirms the HBOC syndrome name.", layer: 2, citations: [2] },
];

async function renderAnswer(sources: Source[]) {
  render(
    <AnswerScreen question="What is the risk from BRCA1 variants?" claims={CLAIMS} sources={sources} />,
  );
  const disclosure = screen.getByTestId("sources-disclosure");
  const user = (await import("@testing-library/user-event")).default.setup();
  await user.click(within(disclosure).getByText(/^sources$/i));
  return { disclosure, user };
}

describe("groupSourcesByLayer carries snippet through the merge", () => {
  it("keeps the snippet on the merged record", () => {
    const groups = groupSourcesByLayer([GENE_WITH_SNIPPET, MEDGEN_NO_SNIPPET]);
    const l1 = groups.find((g) => g.layer === 1)!;
    expect(l1.items[0].snippet).toBe(GENE_WITH_SNIPPET.snippet);
  });

  it("leaves snippet undefined for a record that never had one", () => {
    const groups = groupSourcesByLayer([GENE_WITH_SNIPPET, MEDGEN_NO_SNIPPET]);
    const l2 = groups.find((g) => g.layer === 2)!;
    expect(l2.items[0].snippet).toBeUndefined();
  });

  it("backfills the snippet from a SECOND citation of the same url that arrives later", () => {
    // The realistic shape: `core/graph.py`'s `_pubmed_abstract_rows` emits
    // a paper's abstract-field citation AFTER its title citation, both
    // sharing one `source_url`. The title citation (the first one this
    // function sees for that url) carries no snippet of its own; the
    // second, later citation does. Without the backfill this function's
    // own "first citation's fields win" rule would drop it.
    const titleCitation: Source = { ...GENE_WITH_SNIPPET, n: 5, snippet: undefined };
    const abstractCitation: Source = { ...GENE_WITH_SNIPPET, n: 6 };
    const groups = groupSourcesByLayer([titleCitation, abstractCitation]);
    const l1 = groups.find((g) => g.layer === 1)!;
    expect(l1.items[0].ns).toEqual([5, 6]);
    expect(l1.items[0].snippet).toBe(GENE_WITH_SNIPPET.snippet);
  });

  it("never overwrites the first citation's own snippet with a later duplicate's", () => {
    const first: Source = { ...GENE_WITH_SNIPPET, n: 5 };
    const second: Source = { ...GENE_WITH_SNIPPET, n: 6, snippet: "A different sentence entirely." };
    const groups = groupSourcesByLayer([first, second]);
    const l1 = groups.find((g) => g.layer === 1)!;
    expect(l1.items[0].snippet).toBe(GENE_WITH_SNIPPET.snippet);
  });
});

describe("AnswerScreen source card: snippet line", () => {
  it("shows the quoted snippet under the title WITHOUT opening the record's own disclosure", async () => {
    const { disclosure, user } = await renderAnswer([GENE_WITH_SNIPPET, MEDGEN_NO_SNIPPET]);
    // Open only the outer Sources panel and the layer group, exactly as
    // `renderAnswer` does. The individual record card (`source-1`) is
    // deliberately left closed: `openSources` starts empty and nothing
    // here clicks it.
    const l1Group = within(disclosure).getByTestId("sources-group-1");
    await user.click(within(l1Group).getByText("Knowledge graph"));

    const card = within(disclosure).getByTestId("source-1");
    const snippet = within(card).getByTestId("source-1-snippet");
    expect(snippet).toHaveTextContent(GENE_WITH_SNIPPET.snippet!);

    // The load-bearing structural proof: the snippet sits inside the
    // record's `<summary>`, the one part of a native `<details>` element a
    // browser always renders regardless of the `open` attribute. The
    // metadata `<dl>` (Tool, Evidence, Confidence...) sits OUTSIDE the
    // summary, inside the collapsible body, which is why moving the
    // snippet here (rather than beside "Tool" in the `<dl>`) is what makes
    // it visible without opening the card. jsdom does not apply the
    // browser's native collapse styling (this file's sibling tests already
    // note that), so this checks DOM placement rather than visibility.
    expect(snippet.closest("summary")).not.toBeNull();
    const toolRow = within(card).getByText("cypher_query");
    expect(toolRow.closest("summary")).toBeNull();
    expect(toolRow.closest("dl")).not.toBeNull();
  });

  it("renders no snippet element at all when the record has none", async () => {
    const { disclosure, user } = await renderAnswer([GENE_WITH_SNIPPET, MEDGEN_NO_SNIPPET]);
    const l2Group = within(disclosure).getByTestId("sources-group-2");
    await user.click(within(l2Group).getByText("Live NCBI APIs"));

    const card = within(disclosure).getByTestId("source-2");
    expect(within(card).queryByTestId("source-2-snippet")).not.toBeInTheDocument();
  });
});
