/**
 * Superscript citation markers, 2026-09-14 (product-owner request: the boxed
 * inline chips "overwhelm the answer").
 *
 * WHAT THIS FILE PINS:
 * - the collapse rule: one to three sources are a comma list, four or more
 *   are one marker, a range when consecutive and "first +N" otherwise;
 * - every marker's accessible name says which source and which layer, and a
 *   range names every member with its own layer;
 * - the card opens on keyboard focus, lists the source, its id, its layer in
 *   words and the record link, and closes on Escape;
 * - the card links ONLY an allowlisted https host, and says so when it does
 *   not link;
 * - an uncited sentence still says so in words;
 * - the answer screen renders markers, not the old boxed chip.
 *
 * WHAT IT DOES NOT PIN: the card's on-screen position and its clamping at
 * 390px (jsdom has no layout, so `getBoundingClientRect` is all zeros). That
 * is the Playwright screenshots' job, recorded in the report.
 */

import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  CitationMarkers,
  collapseCitations,
  markerLabel,
  markerSpokenName,
  type CitationSource,
} from "./CitationMarkers";
import { AnswerScreen } from "../screens/AnswerScreen";

function source(n: number, layer: 1 | 2 | 3, overrides: Partial<CitationSource> = {}): CitationSource {
  return {
    n,
    layer,
    name: `MedGen C00${n}`,
    tool: "ncbi_efetch",
    url: `https://www.ncbi.nlm.nih.gov/medgen/C00${n}`,
    ...overrides,
  };
}

describe("collapseCitations and the marker label", () => {
  it("keeps one to three sources as separate markers", () => {
    expect(collapseCitations([])).toEqual([]);
    expect(collapseCitations([4])).toEqual([[4]]);
    expect(collapseCitations([1, 2, 3])).toEqual([[1], [2], [3]]);
  });

  it("collapses four or more sources into one marker, keeping every member", () => {
    const thirteen = Array.from({ length: 13 }, (_, i) => i + 1);
    expect(collapseCitations([1, 2, 3, 4])).toEqual([[1, 2, 3, 4]]);
    expect(collapseCitations(thirteen)).toEqual([thirteen]);
  });

  it("drops a repeated index rather than rendering two markers for one card", () => {
    expect(collapseCitations([2, 2, 5])).toEqual([[2], [5]]);
  });

  it("shows a range for consecutive indices and first +N otherwise", () => {
    expect(markerLabel([7])).toBe("7");
    expect(markerLabel([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13])).toBe("1–13");
    expect(markerLabel([9, 1, 4, 7])).toBe("1 +3");
  });

  it("speaks a range in words, with every source's own layer", () => {
    const layerOf = (n: number) => (n <= 2 ? 2 : 3) as 1 | 2 | 3;
    expect(markerSpokenName([1], layerOf)).toBe("Source 1, layer 2");
    expect(markerSpokenName([1, 2, 3, 4], layerOf)).toBe(
      "Sources 1 to 4: Source 1, layer 2; Source 2, layer 2; Source 3, layer 3; Source 4, layer 3",
    );
    expect(markerSpokenName([1, 4, 7, 9], layerOf)).toMatch(/^Sources 1, 4, 7 and 9: /);
  });
});

describe("CitationMarkers rendering", () => {
  it("renders a comma list of three markers, each named by source and layer", () => {
    const sources = [source(1, 1), source(2, 2), source(3, 3)];
    render(<CitationMarkers citations={[1, 2, 3]} sources={sources} claimLayer={1} claimIndex={0} />);

    expect(screen.getByRole("button", { name: "Source 1, layer 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Source 2, layer 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Source 3, layer 3" })).toBeInTheDocument();
    const markers = screen.getByTestId("citation-markers-0");
    // A superscript, not a boxed chip.
    expect(markers.tagName).toBe("SUP");
    // Visible glyphs read "1, 2, 3"; the hidden names are not part of that.
    const visible = Array.from(markers.querySelectorAll('[aria-hidden="true"]'))
      .map((node) => node.textContent)
      .join("")
      // REQUIREMENT CHANGE, 2026-09-14: a hidden word joiner (U+2060) keeps
      // the first marker on the line of the word it cites; it is not a glyph.
      .replace(/\u2060/g, "");
    expect(visible).toBe("1, 2, 3");
  });

  it("renders thirteen sources as ONE range marker that names all thirteen", async () => {
    const user = userEvent.setup();
    const thirteen = Array.from({ length: 13 }, (_, i) => i + 1);
    const sources = thirteen.map((n) => source(n, n <= 4 ? 2 : 3));
    render(<CitationMarkers citations={thirteen} sources={sources} claimLayer={2} claimIndex={0} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveAccessibleName(
      /^Sources 1 to 13: Source 1, layer 2; .*Source 5, layer 3; .*Source 13, layer 3$/,
    );
    expect(buttons[0]).toHaveAttribute("data-testid", "citation-group-1");
    expect(buttons[0]).toHaveAttribute("data-layer", "mixed");
    expect(within(buttons[0]).getByText("1–13")).toBeInTheDocument();

    await user.tab();
    const card = screen.getByTestId("cite-popover-1");
    for (const n of thirteen) {
      expect(within(card).getByTestId(`cite-popover-row-${n}`)).toBeInTheDocument();
    }
  });

  it("opens the card on keyboard focus with the source, id, layer and an allowlisted link", async () => {
    const user = userEvent.setup();
    render(
      <CitationMarkers
        citations={[1]}
        sources={[source(1, 2, { name: "MedGen C0346153", url: "https://www.ncbi.nlm.nih.gov/medgen/C0346153" })]}
        claimLayer={2}
        claimIndex={0}
      />,
    );
    const marker = screen.getByRole("button", { name: "Source 1, layer 2" });
    expect(marker).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("cite-popover-1")).toBeNull();

    // Keyboard only: Tab lands on the marker and that alone opens the card.
    await user.tab();
    expect(marker).toHaveFocus();
    expect(marker).toHaveAttribute("aria-expanded", "true");
    const card = screen.getByTestId("cite-popover-1");
    expect(marker).toHaveAttribute("aria-controls", card.id);
    expect(card).toHaveTextContent("MedGen C0346153");
    expect(card).toHaveTextContent("ncbi_efetch");
    // The layer in words, so colour is never the only signal.
    expect(card).toHaveTextContent(/L2 · live/);
    const link = within(card).getByRole("link");
    expect(link).toHaveAttribute("href", "https://www.ncbi.nlm.nih.gov/medgen/C0346153");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(new URL(link.getAttribute("href") ?? "").hostname).toBe("www.ncbi.nlm.nih.gov");

    // Tab moves INTO the card rather than closing it.
    await user.tab();
    expect(link).toHaveFocus();
    expect(screen.getByTestId("cite-popover-1")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByTestId("cite-popover-1")).toBeNull();
  });

  it("never links an off-host or javascript: record, and says why", async () => {
    const user = userEvent.setup();
    render(
      <CitationMarkers
        citations={[1, 2]}
        sources={[
          source(1, 1, { url: "https://evil.example.com/fake-ncbi-record" }),
          source(2, 1, { url: "javascript:alert(1)" }),
        ]}
        claimLayer={1}
        claimIndex={0}
      />,
    );
    for (const n of [1, 2]) {
      await act(async () => {
        screen.getByTestId(`citation-${n}`).focus();
      });
      const card = screen.getByTestId(`cite-popover-${n}`);
      // Populate-check: the card rendered its source, so the missing anchor
      // below means "not linked", not "nothing rendered".
      expect(card).toHaveTextContent(`MedGen C00${n}`);
      expect(within(card).queryByRole("link")).toBeNull();
      expect(card.querySelector("a")).toBeNull();
      expect(card).toHaveTextContent("Not linked: this URL is not on a recognised NCBI host.");
      await user.keyboard("{Escape}");
    }
  });

  it("says an uncited sentence has no source, and renders no marker", () => {
    render(<CitationMarkers citations={[]} sources={[]} claimLayer={null} claimIndex={0} />);
    expect(screen.getByText("This sentence has no source.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("the answer screen uses markers, not boxed chips", () => {
  it("renders a cited claim with a superscript marker and an uncited one with the words", () => {
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[
          { text: "BRCA1 is associated with HBOC.", layer: 1, citations: [1] },
          { text: "It is widely discussed.", layer: null, citations: [] },
        ]}
        sources={[{ ...source(1, 1), evidence: "curated", confidence: "high", license: "public domain" }]}
      />,
    );
    const marker = screen.getByTestId("citation-1");
    expect(marker.tagName).toBe("BUTTON");
    expect(marker.closest("sup")).not.toBeNull();
    expect(marker).not.toHaveAttribute("role", "note");
    // REQUIREMENT CHANGE, 2026-09-14: the name is the button's aria-label, so
    // it is announced but never part of the copied prose.
    expect(marker).toHaveAccessibleName("Source 1, layer 1");
    expect(screen.getByTestId("claim-text-0").textContent).not.toMatch(/Source \d+, layer/);
    // The old chip printed the source name inline; the marker does not.
    expect(screen.getByTestId("claim-text-0")).not.toHaveTextContent(/MedGen C001/);
    expect(screen.getByTestId("claim-text-1")).toHaveTextContent("This sentence has no source.");
  });
});
