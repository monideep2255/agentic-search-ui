/**
 * The About page's guided walk, "What happens to your question"
 * (product-owner request of 2026-09-13).
 *
 * These arms pin the facts the walk is judged on, each of which would read as
 * fine if it were wrong:
 *
 * - The SEVEN stop headings, IN ORDER. A walk is an ordered thing: seven
 *   headings all present but shuffled would describe a different system, and
 *   an assertion that merely finds each one would pass against that. So the
 *   order is asserted as a sequence, not as seven independent lookups.
 * - The three layer badges, with the layer each one names. The colour system
 *   is the product's identity and a badge naming the wrong layer is a
 *   provenance error wearing a design detail.
 * - The "cite or refuse" sentence, which is the one rule the whole walk
 *   exists to make legible.
 * - That the pre-existing "How an answer is built" heading and the three
 *   layer cards below still render. The walk was ADDED before existing
 *   content, and the way that goes wrong is silently replacing it.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      the stop headings and their order, the layer badges, the
 *                   cite-or-refuse sentence, the question the walk follows,
 *                   the annotated answer mock's presence, and the survival of
 *                   the page's pre-existing heading and layer cards.
 *
 *   NOT exercised:  that every factual claim in the prose is TRUE of the
 *                   running system. No unit test can know that. Each claim
 *                   was read out of the source it describes and the file and
 *                   symbol for each is listed in `InfoScreens.tsx`'s own
 *                   comment block above `AboutScreen`, which is where a
 *                   reviewer checks them.
 *
 *                   LAYOUT: that the spine reads as one column, that its
 *                   connector joins the nodes, and that nothing scrolls
 *                   sideways at 390px. Those are geometry, not DOM, and
 *                   LEARNINGS.md's 2026-08-14 entry is why that is stated
 *                   rather than assumed covered: `order: -1` moves an element
 *                   across the page while every DOM-order assertion stays
 *                   green. Checked with a real browser instead.
 *
 *                   Colour token conformance, which the build phase 4.8
 *                   premise gate already owns, and contrast, which needs a
 *                   real browser and is covered by `e2e/accessibility.spec.ts`'s
 *                   About arm.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AboutScreen } from "./InfoScreens";

/** The seven stops, in the order the walk must present them. */
const STOPS = [
  "You ask",
  "The model steps, tier by tier",
  "The search goes out",
  "The records come back",
  "The answer is written, then streamed to you",
  "What you get",
  "What it will not do",
] as const;

describe("AboutScreen: what happens to your question", () => {
  it("renders the section heading and the question the walk follows", () => {
    render(<AboutScreen />);

    expect(
      screen.getByRole("heading", { name: "What happens to your question" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("about-journey-question")).toHaveTextContent(
      "Which diseases are associated with BRCA1?",
    );
  });

  it("renders the seven stops in order", () => {
    render(<AboutScreen />);

    const walk = screen.getByTestId("about-journey");
    // Every stop heading is a level-3 heading inside the walk, so reading
    // them off in DOM order is what makes this an ORDER assertion rather than
    // seven independent presence checks.
    const headings = within(walk)
      .getAllByRole("heading", { level: 3 })
      .map((node) => node.textContent);

    expect(headings).toEqual([...STOPS]);
  });

  it("numbers every stop", () => {
    render(<AboutScreen />);

    const walk = screen.getByTestId("about-journey");
    const items = within(walk).getAllByRole("listitem");
    expect(items).toHaveLength(STOPS.length);
    items.forEach((item, index) => {
      expect(item.textContent).toContain(String(index + 1));
    });
  });

  it("names all three data layers on the Act stop, each with its own tools", () => {
    render(<AboutScreen />);

    const layers = screen.getByTestId("about-journey-layers");

    const one = within(layers).getByTestId("about-journey-layer-1");
    expect(one).toHaveTextContent("Knowledge graph");
    expect(one).toHaveTextContent("L1");
    expect(one).toHaveTextContent("cypher_query");

    const two = within(layers).getByTestId("about-journey-layer-2");
    expect(two).toHaveTextContent("Live NCBI APIs");
    expect(two).toHaveTextContent("L2");
    expect(two).toHaveTextContent("ncbi_efetch, ncbi_dbsnp");

    const three = within(layers).getByTestId("about-journey-layer-3");
    expect(three).toHaveTextContent("Enrichment");
    expect(three).toHaveTextContent("L3");
    expect(three).toHaveTextContent("pubtator_annotate");
    expect(three).toHaveTextContent("clinicaltrials_search");
  });

  it("names all three harness tiers and says a tier's model is held for the query", () => {
    render(<AboutScreen />);

    const walk = screen.getByTestId("about-journey");
    expect(walk).toHaveTextContent("Guard tier, a fast, inexpensive model");
    expect(walk).toHaveTextContent("Plan tier, a mid-range model");
    expect(walk).toHaveTextContent("Synth tier, the strongest model");
    expect(walk).toHaveTextContent(/held there, so it cannot change partway through a run/);
  });

  it("states the cite-or-refuse rule by name", () => {
    render(<AboutScreen />);

    expect(screen.getByTestId("about-journey")).toHaveTextContent(
      /That rule is called cite or refuse\./,
    );
  });

  it("shows the annotated answer mock with its four parts", () => {
    render(<AboutScreen />);

    const mock = screen.getByTestId("about-answer-mock");
    expect(mock).toHaveTextContent("A cited sentence");
    expect(mock).toHaveTextContent("Grounded · every claim cited");
    expect(mock).toHaveTextContent("L1 · knowledge graph");
    expect(mock).toHaveTextContent("Ask a follow-up");
  });

  it("keeps the page's pre-existing content below the walk", () => {
    render(<AboutScreen />);

    // The page title, unchanged. Asserted because the walk was inserted
    // BEFORE this content, and the way that goes wrong is replacing it.
    expect(
      screen.getByRole("heading", { name: "How an answer is built", level: 1 }),
    ).toBeInTheDocument();

    for (const name of ["Knowledge graph", "Live NCBI APIs", "Enrichment"]) {
      expect(screen.getByRole("heading", { name, level: 2 })).toBeInTheDocument();
    }

    expect(screen.getByRole("heading", { name: "Cite or refuse" })).toBeInTheDocument();
  });
});
