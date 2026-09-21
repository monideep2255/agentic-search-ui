/**
 * The Architecture page (product-owner request of 2026-09-13).
 *
 * WHAT THESE ARMS ARE FOR. Every figure on this page is a claim about a
 * system the page cannot reach, and a wrong one reads exactly like a right
 * one: nobody spots that a graph has 115,406,671 nodes rather than
 * 115,406,761 by looking at it. So the arms below pin the EXACT strings,
 * character for character, and a transposed digit fails the build rather
 * than shipping. That is the whole point of asserting a count that a human
 * eye cannot check.
 *
 * The five database names are pinned the same way and for the same reason:
 * the product owner asked for the databases to be named, and a page naming
 * four of five, or naming dbSNP (which is deliberately NOT in the graph, see
 * `docs/architecture/Three_layer_data_architecture.md`'s excluded table),
 * would look complete and be wrong.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      the four stop headings and their order, the five source
 *                   database names with the node count and graph label of
 *                   each, the snapshot date, the node and edge counts, the
 *                   label counts, the five pipeline steps in order, the three
 *                   layer cards with every tool name and per-call budget, the
 *                   PLACEMENT of the L1 card inside layer 1 rather than in a
 *                   block of its own, the example Cypher, and that the closing
 *                   cross-link calls back when wired and degrades to prose
 *                   when it is not.

 *
 *   ALSO EXERCISED, and it is the arm the 2026-09-13 restructure exists for:
 *   that the layer 1 card appears BEFORE the layer 2 heading in DOM order. The
 *   product owner's whole instruction was that the `L1` badge belongs beside
 *   the graph it names. Every other arm on this page passes just as happily
 *   with all three cards piled at the foot, which is the shape they were in
 *   before, so presence assertions cannot see the change at all. Order can.
 *
 *   NOT exercised:  that any figure is TRUE of the running system. No unit
 *                   test can know that; each was read out of a named document
 *                   and the file for each is listed in
 *                   `lib/architectureFacts.ts`, which is where a reviewer
 *                   checks them. An arm here proves only that what was read
 *                   still reaches the screen intact.
 *
 *                   LAYOUT: that the spine reads as one column and that
 *                   nothing scrolls sideways at 390px. Geometry, not DOM.
 *                   Checked in a real browser instead, the same split
 *                   `AboutScreen.test.tsx` states for the same reason.
 *
 *                   Contrast, which needs a real browser and is covered by
 *                   `e2e/accessibility.spec.ts`'s architecture arm.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  EDGE_COUNT,
  NODE_COUNT,
  SNAPSHOT_DATE,
  SOURCE_DATABASES,
} from "../../lib/architectureFacts";
import { ArchitectureScreen } from "./ArchitectureScreen";

/**
 * The four stops, in the order the page must present them.
 *
 * The wording is the product owner's own, twice over (2026-09-13): they
 * renumbered the page after reading it live, then corrected "system" to
 * "layer" minutes later. Both corrections are pinned here, so a revert to
 * either earlier shape fails rather than passing quietly.
 */
const STOPS = [
  "Layer 1, the data pipelines and the knowledge graph",
  "Layer 2, live NCBI APIs",
  "Layer 3, enrichment",
  "All three layers feed the search agent",
] as const;

describe("ArchitectureScreen", () => {
  it("renders the page title and the four stops in order", () => {
    render(<ArchitectureScreen />);

    expect(screen.getByRole("heading", { name: "Architecture", level: 1 })).toBeInTheDocument();

    const stack = screen.getByTestId("architecture-layers");
    const headings = within(stack)
      .getAllByRole("heading", { level: 3 })
      .map((node) => node.textContent);
    expect(headings).toEqual([...STOPS]);
  });

  it("never calls the three layers systems", () => {
    // The product owner's correction of 2026-09-13, "I meant layers, wrong to
    // use system". `CLAUDE.md` and the data-engineering repository both number
    // three SYSTEMS and are deliberately left alone, so the word is one
    // copy-paste away from coming back here. An arm is cheaper than noticing.
    render(<ArchitectureScreen />);
    const stack = screen.getByTestId("architecture-layers");
    // POPULATE-CHECK. An empty element contains no "system" either, so
    // without this the arm would pass against a page that rendered nothing.
    expect(stack.textContent).toMatch(/Layer 1, the data pipelines/);
    expect(stack.textContent).not.toMatch(/system/i);
  });

  it("states the snapshot date and the exact node and edge counts", () => {
    render(<ArchitectureScreen />);

    // Pinned as literals rather than through the imported constants alone.
    // Asserting `toHaveTextContent(NODE_COUNT)` would pass against any value
    // the module happened to hold, including a typo, since both sides would
    // move together. These two lines are the ones that cannot.
    expect(NODE_COUNT).toBe("115,406,761");
    expect(EDGE_COUNT).toBe("693,295,991");
    expect(SNAPSHOT_DATE).toBe("22 April 2026");

    const snapshot = screen.getByTestId("architecture-snapshot");
    expect(snapshot).toHaveTextContent("115,406,761");
    expect(snapshot).toHaveTextContent("nodes");
    expect(snapshot).toHaveTextContent("693,295,991");
    expect(snapshot).toHaveTextContent("edges");
    expect(snapshot).toHaveTextContent("11");
    expect(snapshot).toHaveTextContent("vertex labels");
    expect(snapshot).toHaveTextContent("14");
    expect(snapshot).toHaveTextContent("edge labels");

    // The date appears in the prose and again as the eyebrow above the
    // figures, so it is matched on the page rather than on one element.
    expect(screen.getAllByText(/22 April 2026/).length).toBeGreaterThan(0);
  });

  it("names all five source databases, each with its node count and graph label", () => {
    render(<ArchitectureScreen />);

    // The exact five, pinned. A sixth or a substitution fails here.
    expect(SOURCE_DATABASES.map((db) => db.source)).toEqual([
      "NCBI Gene",
      "PubMed",
      "ClinVar",
      "NCBI Taxonomy",
      "MedGen",
    ]);

    const sources = screen.getByTestId("architecture-sources");
    const expected: [string, string, string][] = [
      ["Gene", "NCBI Gene", "67,536,325"],
      ["Article", "PubMed", "40,387,670"],
      ["SequenceVariant", "ClinVar", "4,467,468"],
      ["OrganismTaxon", "NCBI Taxonomy", "2,736,611"],
      ["Disease", "MedGen", "200,845"],
    ];
    for (const [label, source, nodes] of expected) {
      const card = within(sources).getByTestId(`architecture-source-${label}`);
      expect(card).toHaveTextContent(source);
      expect(card).toHaveTextContent(`${nodes} nodes`);
      expect(card).toHaveTextContent(label);
    }
  });

  it("shows the five pipeline steps in order", () => {
    render(<ArchitectureScreen />);

    const pipeline = screen.getByTestId("architecture-pipeline");
    for (const step of ["Download", "Parse", "Map to BioLink", "Validate", "Export KGX"]) {
      expect(pipeline).toHaveTextContent(step);
    }
    // Order, not just membership. The arrow between steps is decorative, so
    // the text of the strip is read as one string and the steps must appear
    // in sequence within it.
    expect(pipeline.textContent?.replace(/\s+/g, " ")).toMatch(
      /Download.*Parse.*Map to BioLink.*Validate.*Export KGX/,
    );
  });

  it("describes the graph itself: where it runs, what a query looks like, and its budget", () => {
    render(<ArchitectureScreen />);

    const stack = screen.getByTestId("architecture-layers");
    expect(stack).toHaveTextContent("PostgreSQL 15 with the Apache AGE extension");
    expect(stack).toHaveTextContent("read-only credential");
    expect(stack).toHaveTextContent("90 seconds");
    expect(stack).toHaveTextContent("500 rows");

    const cypher = screen.getByTestId("architecture-cypher");
    expect(cypher).toHaveTextContent("MATCH (g:Gene {id: 'NCBIGene:672'})");
    expect(cypher).toHaveTextContent("gene_associated_with_condition");
  });

  it("names every tool under its own layer, with the budget the code enforces", () => {
    render(<ArchitectureScreen />);

    const layers = screen.getByTestId("architecture-layers");

    const one = within(layers).getByTestId("architecture-layer-1");

    expect(one).toHaveTextContent("Knowledge graph");
    expect(one).toHaveTextContent("L1");
    expect(one).toHaveTextContent("cypher_query");
    expect(one).toHaveTextContent("90 seconds, at most 500 rows");

    const two = within(layers).getByTestId("architecture-layer-2");
    expect(two).toHaveTextContent("Live NCBI APIs");
    expect(two).toHaveTextContent("L2");
    expect(two).toHaveTextContent("ncbi_efetch");
    expect(two).toHaveTextContent("E-utilities");
    expect(two).toHaveTextContent("ncbi_dbsnp");
    expect(two).toHaveTextContent("Variation Services");
    expect(two).toHaveTextContent("pathogen_detection");
    expect(two).toHaveTextContent("120 seconds");

    const three = within(layers).getByTestId("architecture-layer-3");
    expect(three).toHaveTextContent("Enrichment");
    expect(three).toHaveTextContent("L3");
    expect(three).toHaveTextContent("pubtator_annotate");
    expect(three).toHaveTextContent("PubTator3");
    expect(three).toHaveTextContent("litvar2_lookup");
    expect(three).toHaveTextContent("LitVar2");
    expect(three).toHaveTextContent("clinicaltrials_search");
    expect(three).toHaveTextContent("ClinicalTrials.gov API v2");
  });

  it("puts the layer 1 card inside layer 1, before the layer 2 heading", () => {
    // THE ARM THE 2026-09-13 RESTRUCTURE EXISTS FOR. The three cards used to
    // sit together at the foot of the page, three sections away from the
    // graph the `L1` badge names. Every other arm in this file passes just as
    // happily against that shape, because they only ask whether each card is
    // present. This one asks where it is.
    render(<ArchitectureScreen />);

    const card = screen.getByTestId("architecture-layer-1");
    const layerTwoHeading = screen.getByRole("heading", {
      name: "Layer 2, live NCBI APIs",
      level: 3,
    });

    // `DOCUMENT_POSITION_FOLLOWING` on the card means the heading comes after
    // it, which is the whole claim: the card is inside layer 1's stop.
    expect(
      card.compareDocumentPosition(layerTwoHeading) & Node.DOCUMENT_POSITION_FOLLOWING,
      "the layer 1 card is not inside layer 1: the layer 2 heading comes before it",
    ).toBeTruthy();

    // And the mirror, so an arm that would pass with the card at the very top
    // of the page fails too: the card must come after layer 1's own heading.
    const layerOneHeading = screen.getByRole("heading", {
      name: "Layer 1, the data pipelines and the knowledge graph",
      level: 3,
    });
    expect(
      layerOneHeading.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("says how each layer's facts are cited", () => {
    render(<ArchitectureScreen />);

    const stack = screen.getByTestId("architecture-layers");
    expect(stack).toHaveTextContent(/source URL that was stored on the node or edge/);
    expect(stack).toHaveTextContent(/links to the record page for the identifier/);
  });

  it("links back to About when wired, and names the tab when it is not", () => {
    const onNavigateToAbout = vi.fn();
    const { unmount } = render(<ArchitectureScreen onNavigateToAbout={onNavigateToAbout} />);

    screen.getByRole("button", { name: "open About" }).click();
    expect(onNavigateToAbout).toHaveBeenCalledTimes(1);
    unmount();

    render(<ArchitectureScreen />);
    expect(screen.queryByRole("button", { name: "open About" })).not.toBeInTheDocument();
    expect(screen.getByText(/open About in the bar above/)).toBeInTheDocument();
  });
});
