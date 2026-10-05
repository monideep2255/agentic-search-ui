/**
 * Item: the Notes section, removed 2026-09-21 by product-owner decision.
 *
 * "the Notes section is super confusing. remove it", naming the
 * verification note and the further-records note exactly.
 *
 * These arms pin what is hidden AND what is not, because the risk in a
 * hide-by-pattern is over-matching: a pattern that swallowed the truncation
 * note or the medical-advice line would remove disclosure nobody asked to
 * remove, and it would do so silently.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AnswerScreen, { isHiddenNote } from "./components/screens/AnswerScreen";

describe("the notes the web UI hides", () => {
  it("shows the no-written-summary note (owner decision D1, 2026-10-05)", () => {
    expect(
      isHiddenNote(
        "Note: no written summary could be checked against the records, so the records found are listed below with their sources",
      ),
    ).toBe(false);
    // The earlier wording of the same note stays visible too.
    expect(
      isHiddenNote(
        "Note: the written summary of these records could not be verified against them, so this answer lists the records found instead",
      ),
    ).toBe(false);
    expect(
      isHiddenNote("Note: this question reached its resource limit before it finished, so this answer lists the records gathered so far"),
    ).toBe(false);
  });

  it("hides the further-records note for any count, not just the singular", () => {
    // The first attempt at this filter matched "one further" and "1 further"
    // only, and the live note reads "5 further pubmed records". This arm is
    // that bug.
    expect(isHiddenNote("Note: 5 further pubmed records were found for this question and are not included in the list above")).toBe(true);
    expect(isHiddenNote("Note: 12 further disease records were found for this question and are not covered in the summary above")).toBe(true);
    expect(isHiddenNote("Note: one further disease record was found for this question and is not included in the list above")).toBe(true);
  });

  it("leaves every other note alone", () => {
    // Disclosures the product owner did NOT ask to remove. If a future
    // widening of the pattern swallows one of these, this arm goes red.
    const kept = [
      "Note: this answer was truncated to 100 of the 124 records found",
      "Note: this answer does not address the following entities named in your question",
      "Note: this answer's completeness check could not run to the end",
      "Note: the records below were retrieved for this question",
      "This is a research summary, not medical advice",
    ];
    for (const note of kept) {
      expect(isHiddenNote(note), `must not hide: ${note}`).toBe(false);
    }
  });

  it("is not defeated by leading whitespace", () => {
    expect(isHiddenNote("   Note: 5 further pubmed records were found")).toBe(true);
  });
});

describe("the no-written-summary note reaches the screen", () => {
  it("renders the one plain line among the answer's notes", () => {
    const note =
      "Note: no written summary could be checked against the records, so the records found are listed below with their sources";
    render(
      <AnswerScreen
        question="Which genes cause MODY?"
        claims={[{ text: "GCK[1]", layer: 1, citations: [1] }]}
        sources={[]}
        systemNotes={[note]}
      />,
    );
    expect(screen.getByText(note)).toBeInTheDocument();
  });
});
