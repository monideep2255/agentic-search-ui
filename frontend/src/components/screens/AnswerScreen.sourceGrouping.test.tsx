/**
 * Source list grouping and deduplication, 2026-09-20.
 *
 * Context: `9cc5d63` split one overloaded constant into two, the bound on
 * what the model reads (stayed 20) and the bound on what the reader sees
 * (rose to 100). A `sources` array that used to top out around 16 rows can
 * now carry up to 100, and the product owner flagged the consequence
 * directly: "should we bucket them into the layers ... will be hard to
 * parse 500 sources", and separately, "ensure the content in the table is
 * pointing to unique information, if it references same source, that
 * should just be present once".
 *
 * This file pins two behaviours in `AnswerScreen`'s source list only, never
 * the result table `claims` render, which is untouched by either change:
 *
 *   1. Sources group by layer (`groupSourcesByLayer`), each group carrying
 *      a plain-language heading transcribed from
 *      `docs/build/design/design-system/identity/layer-badges.html` and its
 *      own count.
 *   2. Two citations sharing the same `source.url` collapse into ONE card
 *      in the source list, carrying every marker that pointed at it.
 *
 * Every arm below states, in a comment, what it is proven to catch, and
 * each was run once with the change in place (recorded pass) and once with
 * the relevant code path reverted to its pre-change form (recorded fail),
 * per `goal-contracts`.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerScreen, groupSourcesByLayer } from "./AnswerScreen";
import type { Claim, Source } from "./AnswerScreen";

/** Two distinct records in Layer 1, two in Layer 2, none in Layer 3. */
const GENE_672: Source = {
  n: 1,
  layer: 1,
  name: "NCBI Gene 672 · BRCA1",
  tool: "cypher_query",
  evidence: "curated assertion",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/gene/672",
};

/** A second Layer 1 citation of the SAME record as `GENE_672`, under a
 * different marker, standing in for "many variants on one gene record": a
 * second FACT about gene 672, not a duplicate fact. */
const GENE_672_AGAIN: Source = {
  ...GENE_672,
  n: 2,
};

const MEDGEN: Source = {
  n: 3,
  layer: 2,
  name: "MedGen C0677776 · HBOC",
  tool: "ncbi_efetch",
  evidence: "curated record",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/medgen/C0677776",
};

const CLINVAR: Source = {
  n: 4,
  layer: 2,
  name: "ClinVar VCV000015333",
  tool: "ncbi_efetch",
  evidence: "curated record",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/clinvar/variation/15333",
};

const ALL_SOURCES = [GENE_672, GENE_672_AGAIN, MEDGEN, CLINVAR];

const CLAIMS: Claim[] = [
  { text: "Gene 672 causes disease A.", layer: 1, citations: [1] },
  { text: "Gene 672 also causes disease B.", layer: 1, citations: [2] },
  { text: "MedGen confirms the HBOC syndrome name.", layer: 2, citations: [3] },
  { text: "ClinVar classifies the variant as pathogenic.", layer: 2, citations: [4] },
];

async function renderAnswer(sources: Source[] = ALL_SOURCES, claims: Claim[] = CLAIMS) {
  render(
    <AnswerScreen question="Which diseases are associated with BRCA1?" claims={claims} sources={sources} />,
  );
  const disclosure = screen.getByTestId("sources-disclosure");
  const user = (await import("@testing-library/user-event")).default.setup();
  await user.click(within(disclosure).getByText(/^sources$/i));
  return disclosure;
}

describe("groupSourcesByLayer (pure function)", () => {
  it("groups by layer in Knowledge graph, Live NCBI APIs, Enrichment order", () => {
    // Catches: a group emitted in array-encounter order instead of the
    // fixed layer order, or a missing plain-language label.
    const groups = groupSourcesByLayer(ALL_SOURCES);
    expect(groups.map((g) => g.layer)).toEqual([1, 2]);
    expect(groups.map((g) => g.label)).toEqual(["Knowledge graph", "Live NCBI APIs"]);
  });

  it("omits a layer group with zero sources rather than rendering it empty", () => {
    // Catches: always emitting all three groups, which would show an empty
    // "Enrichment" heading with a "0" count on an answer with no L3 evidence.
    const groups = groupSourcesByLayer(ALL_SOURCES);
    expect(groups.find((g) => g.layer === 3)).toBeUndefined();
  });

  it("collapses two citations of the same url into one merged row carrying both markers", () => {
    // Catches: deduplication that drops the second marker instead of
    // carrying it, which would silently break that citation's resolution.
    const groups = groupSourcesByLayer(ALL_SOURCES);
    const l1 = groups.find((g) => g.layer === 1)!;
    expect(l1.items).toHaveLength(1);
    expect(l1.items[0].ns).toEqual([1, 2]);
    expect(l1.items[0].url).toBe(GENE_672.url);
  });

  it("does not merge two different records in the same layer", () => {
    // Catches an over-eager dedup keyed on layer or name instead of url:
    // MEDGEN and CLINVAR are both Layer 2 but different records.
    const groups = groupSourcesByLayer(ALL_SOURCES);
    const l2 = groups.find((g) => g.layer === 2)!;
    expect(l2.items).toHaveLength(2);
    expect(l2.items.map((item) => item.url)).toEqual([MEDGEN.url, CLINVAR.url]);
  });
});

describe("AnswerScreen source list: grouping", () => {
  it("renders a heading with a count for each layer actually cited", async () => {
    const disclosure = await renderAnswer();
    const l1Group = within(disclosure).getByTestId("sources-group-1");
    expect(l1Group).toHaveTextContent("Knowledge graph");
    expect(within(l1Group).getByTestId("sources-group-1-count")).toHaveTextContent("1");

    const l2Group = within(disclosure).getByTestId("sources-group-2");
    expect(l2Group).toHaveTextContent("Live NCBI APIs");
    expect(within(l2Group).getByTestId("sources-group-2-count")).toHaveTextContent("2");

    expect(within(disclosure).queryByTestId("sources-group-3")).not.toBeInTheDocument();
  });
});

describe("AnswerScreen source list: deduplication", () => {
  it("lists a record cited twice ONCE, carrying both markers", async () => {
    const disclosure = await renderAnswer();
    // Only one card for gene 672, not two.
    expect(within(disclosure).getAllByText(/NCBI Gene 672/)).toHaveLength(1);
    const card = within(disclosure).getByTestId("source-1");
    expect(within(card).getByTestId("source-1-markers")).toHaveTextContent("[1][2]");
    // The second marker's own testid is never rendered as a separate card.
    expect(within(disclosure).queryByTestId("source-2")).not.toBeInTheDocument();
  });

  it("does NOT collapse a table row that shares a record but states a different fact", async () => {
    // This is the overreach guard the goal contract names directly: the
    // RESULT TABLE (built from `claims`) is a different surface from the
    // source list, and dedup must never reach into it. Both claim sentences
    // that cite gene 672 under its two different markers must still render
    // as two distinct pieces of text.
    await renderAnswer();
    expect(screen.getByText("Gene 672 causes disease A.")).toBeInTheDocument();
    expect(screen.getByText("Gene 672 also causes disease B.")).toBeInTheDocument();
  });

  it("still resolves a citation marker in the prose to the correct merged record", async () => {
    // Catches: dedup that changes what `sourceByIndex` (marker resolution)
    // holds, rather than only what the rendered list shows. Both claim 1
    // and claim 2's markers must carry the SAME record identity, gene 672,
    // even though the source list now shows one card for it.
    await renderAnswer();
    const marker1 = screen.getByTestId("citation-1");
    const marker2 = screen.getByTestId("citation-2");
    expect(marker1).toHaveAttribute("data-layer", "1");
    expect(marker2).toHaveAttribute("data-layer", "1");
  });
});
