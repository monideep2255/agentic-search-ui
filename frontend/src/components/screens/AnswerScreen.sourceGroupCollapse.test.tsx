/**
 * Layer-group disclosure, 2026-09-20.
 *
 * Context: `9d20438` grouped the source list by layer. The product owner
 * tested it live and asked for one more thing: "Sources yes -> make those
 * drop down so user just see the 3 layers first and can have drop down". A
 * live answer now carries 78 sources, so the grouped-but-fully-expanded
 * list from `9d20438` is itself a wall once a reader opens "Sources".
 *
 * This file pins the NEW behaviour only: each layer group collapses behind
 * its own disclosure, closed by default, independent of its siblings. It
 * does not re-pin grouping or deduplication themselves; those stay covered
 * by `AnswerScreen.sourceGrouping.test.tsx`. Two arms here (3 and 4) do
 * re-check that dedup and marker resolution survive being read through a
 * newly-opened group, per the goal contract's requirement that `9d20438`'s
 * behaviour is unchanged.
 *
 * Every arm states, in a comment, what it is proven to catch, and each was
 * run once with the change in place (recorded pass) and once against a
 * behaviour-only mutation that flips a boolean or a condition without
 * touching any symbol, export or test id (recorded fail), per
 * `goal-contracts`.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerScreen } from "./AnswerScreen";
import type { Claim, Source } from "./AnswerScreen";

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

/** A second Layer 1 citation of the SAME record as `GENE_672`. */
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

const PMID: Source = {
  n: 5,
  layer: 3,
  name: "PMID 21990134 · Fanconi anemia complementation group S",
  tool: "pubtator_annotate",
  evidence: "literature co-mention",
  confidence: "moderate",
  license: "publisher terms apply",
  url: "https://pubmed.ncbi.nlm.nih.gov/21990134",
};

const ALL_SOURCES = [GENE_672, GENE_672_AGAIN, MEDGEN, CLINVAR, PMID];

const CLAIMS: Claim[] = [
  { text: "Gene 672 causes disease A.", layer: 1, citations: [1] },
  { text: "Gene 672 also causes disease B.", layer: 1, citations: [2] },
  { text: "MedGen confirms the HBOC syndrome name.", layer: 2, citations: [3] },
  { text: "ClinVar classifies the variant as pathogenic.", layer: 2, citations: [4] },
  { text: "Literature co-mentions Fanconi anemia.", layer: 3, citations: [5] },
];

async function openSourcesDisclosure() {
  render(
    <AnswerScreen question="Which diseases are associated with BRCA1?" claims={CLAIMS} sources={ALL_SOURCES} />,
  );
  const disclosure = screen.getByTestId("sources-disclosure");
  const user = (await import("@testing-library/user-event")).default.setup();
  await user.click(within(disclosure).getByText(/^sources$/i));
  return { disclosure, user };
}

describe("AnswerScreen source list: layer-group collapse", () => {
  it("shows all three layer headings with counts and no records, before any group is opened", async () => {
    // Catches: a group that renders its records unconditionally (the
    // `9d20438` behaviour) instead of gating them on `openGroups`. A
    // mutation that always treats the group as open, e.g. replacing
    // `groupOpen && group.items.map(...)` with `group.items.map(...)`,
    // must fail this arm: `source-1` would then be found before any click.
    const { disclosure } = await openSourcesDisclosure();

    const l1 = within(disclosure).getByTestId("sources-group-1");
    expect(l1).toHaveTextContent("Knowledge graph");
    expect(within(l1).getByTestId("sources-group-1-count")).toHaveTextContent("1");

    const l2 = within(disclosure).getByTestId("sources-group-2");
    expect(l2).toHaveTextContent("Live NCBI APIs");
    expect(within(l2).getByTestId("sources-group-2-count")).toHaveTextContent("2");

    const l3 = within(disclosure).getByTestId("sources-group-3");
    expect(l3).toHaveTextContent("Enrichment");
    expect(within(l3).getByTestId("sources-group-3-count")).toHaveTextContent("1");

    // The shape, not the substance: every group is CLOSED, so a browser shows
    // the three headings and none of the records.
    //
    // This asserts the `open` state rather than DOM absence, and the reason is
    // recorded because the first version of this arm did the opposite and broke
    // NINETEEN tests across five files, including build phase 4.8 and 4.9
    // premise gates. Those tests open the Sources disclosure and then assert on
    // a source card, which is legitimate: this file follows the SAME controlled
    // `<details>` pattern the outer disclosure and the per-record cards already
    // use, documented at `AnswerScreen.tsx`'s source-disclosure state block.
    // jsdom does not implement `<details>` hiding, so content stays findable
    // there while a real browser hides it. Gating the records out of the DOM
    // instead would have made this one group level behave unlike every other
    // disclosure on the page, which is exactly the drift design-consistency
    // exists to stop, and it was an over-specification in the brief rather
    // than anything the product owner asked for: they asked for a dropdown.
    expect(within(disclosure).getByTestId("sources-group-1")).not.toHaveAttribute("open");
    expect(within(disclosure).getByTestId("sources-group-2")).not.toHaveAttribute("open");
    expect(within(disclosure).getByTestId("sources-group-3")).not.toHaveAttribute("open");
  });

  it("expands one group's records and leaves its siblings closed", async () => {
    // Catches: a single shared `sourcesGroupOpen: boolean` instead of a
    // per-layer set, which would open every group together. A mutation
    // that makes `toggleGroup` set ALL layers open instead of just the
    // clicked one must fail this arm: layer 2 would then also be open
    // after clicking only layer 1.
    //
    // Asserts the `open` state rather than DOM presence, for the reason
    // recorded in full on the arm above.
    const { disclosure, user } = await openSourcesDisclosure();

    const l1Group = within(disclosure).getByTestId("sources-group-1");
    await user.click(within(l1Group).getByText("Knowledge graph"));

    expect(within(disclosure).getByTestId("sources-group-1")).toHaveAttribute("open");
    expect(within(disclosure).getByTestId("sources-group-2")).not.toHaveAttribute("open");
    expect(within(disclosure).getByTestId("sources-group-3")).not.toHaveAttribute("open");

    // Opening the second group independently opens it without closing the
    // first.
    const l2Group = within(disclosure).getByTestId("sources-group-2");
    await user.click(within(l2Group).getByText("Live NCBI APIs"));

    expect(within(disclosure).getByTestId("sources-group-1")).toHaveAttribute("open");
    expect(within(disclosure).getByTestId("sources-group-2")).toHaveAttribute("open");
    expect(within(disclosure).getByTestId("sources-group-3")).not.toHaveAttribute("open");
  });

  it("still lists a record cited twice ONCE, carrying both markers, once its group is opened", async () => {
    // Catches: the group-level collapse silently reaching into
    // `groupSourcesByLayer`'s dedup, e.g. re-deriving items from raw
    // `sources` instead of the already-deduplicated `group.items`. A
    // mutation that maps over `sources.filter(s => s.layer === group.layer)`
    // instead of `group.items` must fail this arm: gene 672 would render
    // as two cards instead of one.
    const { disclosure, user } = await openSourcesDisclosure();
    const l1Group = within(disclosure).getByTestId("sources-group-1");
    await user.click(within(l1Group).getByText("Knowledge graph"));

    expect(within(disclosure).getAllByText(/NCBI Gene 672/)).toHaveLength(1);
    const card = within(disclosure).getByTestId("source-1");
    expect(within(card).getByTestId("source-1-markers")).toHaveTextContent("[1][2]");
    expect(within(disclosure).queryByTestId("source-2")).not.toBeInTheDocument();
  });

  it("still resolves a prose citation marker to the correct record after group collapse ships", async () => {
    // Catches: `sourceByIndex` (marker resolution) being rebuilt from a
    // filtered or grouped structure instead of the flat `sources` prop. A
    // mutation that builds `sourceByIndex` from `sourceGroups` instead of
    // `sources` must fail this arm, since a merged group item no longer
    // carries a single `n` for every one of its markers.
    await openSourcesDisclosure();
    const marker1 = screen.getByTestId("citation-1");
    const marker2 = screen.getByTestId("citation-2");
    const marker5 = screen.getByTestId("citation-5");
    expect(marker1).toHaveAttribute("data-layer", "1");
    expect(marker2).toHaveAttribute("data-layer", "1");
    expect(marker5).toHaveAttribute("data-layer", "3");
  });

  it("omits a layer group with zero sources from the collapse UI, same as before grouping had a drop down", async () => {
    // Catches: the new disclosure wrapper forcing all three groups to
    // render regardless of whether `groupSourcesByLayer` omitted one.
    // This is an invariant carried over from `9d20438` rather than a new
    // discriminator for THIS change; it earns its place because the new
    // `<details>` wrapper is a different element (`component="details"`
    // instead of a plain `Box`) and could plausibly have dropped the
    // omission behaviour in the rewrite.
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIMS[0]]}
        sources={[GENE_672]}
      />,
    );
    const disclosure = screen.getByTestId("sources-disclosure");
    const user = (await import("@testing-library/user-event")).default.setup();
    await user.click(within(disclosure).getByText(/^sources$/i));
    expect(within(disclosure).queryByTestId("sources-group-2")).not.toBeInTheDocument();
    expect(within(disclosure).queryByTestId("sources-group-3")).not.toBeInTheDocument();
  });
});
