/**
 * UI fix set 9, items 9.1, 9.2 and 9.12: two answer modes, an explainer, and
 * the lock.
 *
 * Mutations each arm was run against: re-adding a third option turns the
 * two-modes arm red; removing `disabled={locked}` turns the lock arm red
 * (a click reaches `onChange`); mapping `deep_technical` to Plain language
 * turns the legacy-value arm red.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DepthControl, DepthStripToggle, displayedMode } from "./DepthControl";

describe("DepthControl, set 9", () => {
  it("offers exactly Plain language and Researcher, Plain language by default", () => {
    render(<DepthControl variant="onLight" />);
    const group = screen.getByRole("group", { name: /answer mode/i });
    const buttons = Array.from(group.querySelectorAll("button"));
    expect(buttons.map((b) => b.textContent)).toEqual(["Plain language", "Researcher"]);
    expect(screen.getByRole("button", { name: "Plain language" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Researcher" })).toHaveAttribute("aria-pressed", "false");
  });

  it("sends the chosen mode", () => {
    const onChange = vi.fn();
    render(<DepthControl variant="onLight" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Researcher" }));
    expect(onChange).toHaveBeenCalledWith("researcher");
  });

  it("shows each mode as its own block, label set apart, closing line last", () => {
    render(<DepthControl variant="onLight" />);
    fireEvent.click(screen.getByRole("button", { name: /about answer modes/i }));
    const dialog = screen.getByRole("dialog");

    const blocks = Array.from(
      dialog.querySelectorAll<HTMLElement>("[data-testid^='answer-mode-']"),
    );
    expect(blocks.map((block) => block.dataset.testid)).toEqual([
      "answer-mode-plain_language",
      "answer-mode-researcher",
      "answer-mode-closing",
    ]);

    expect(blocks[0]).toHaveTextContent(
      "Plain language: the answer in simple terms, easy to understand.",
    );
    expect(blocks[1]).toHaveTextContent(
      "Researcher: the answer in technical terms, with the specifics and the records listed or in tables.",
    );
    expect(blocks[2]).toHaveTextContent(
      "Both modes cite every claim. A change applies to your next question.",
    );

    // The label is visibly set apart from its description: a bold element
    // inside the same block, not merely a stylistic difference a test
    // cannot see.
    expect(within(blocks[0]).getByText("Plain language:").tagName).toBe("B");
    expect(within(blocks[1]).getByText("Researcher:").tagName).toBe("B");
  });

  it("is locked while a search runs, and says so", () => {
    const onChange = vi.fn();
    render(<DepthControl variant="onLight" locked onChange={onChange} />);
    const researcher = screen.getByRole("button", { name: "Researcher" });
    expect(researcher).toBeDisabled();
    fireEvent.click(researcher);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId("depth-locked")).toHaveTextContent("Locked while this search runs");
  });

  it("shows a stored legacy value as the nearer of the two modes", () => {
    expect(displayedMode("deep_technical")).toBe("researcher");
    expect(displayedMode("clinical_brief")).toBe("plain_language");
    render(<DepthControl variant="onLight" value="deep_technical" />);
    expect(screen.getByRole("button", { name: "Researcher" })).toHaveAttribute("aria-pressed", "true");
  });
});

/**
 * Card 24 (2026-09-25): the compact status-strip toggle. No "Answer mode"
 * label and no info button, unlike `DepthControl` above, per the transcribed
 * mockup (see the component's own docstring).
 */
describe("DepthStripToggle, card 24", () => {
  it("offers exactly Plain language and Researcher, with the current value lit", () => {
    render(<DepthStripToggle value="plain_language" />);
    const group = screen.getByRole("group", { name: /answer depth/i });
    const buttons = Array.from(group.querySelectorAll("button"));
    expect(buttons.map((b) => b.textContent)).toEqual(["Plain language", "Researcher"]);
    expect(screen.getByRole("button", { name: "Plain language" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Researcher" })).toHaveAttribute("aria-pressed", "false");
    // Card 24's whole point: no repeat of the pre-ask explainer on this
    // surface.
    expect(screen.queryByText(/answer mode/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /about answer modes/i })).toBeNull();
  });

  it("calls onChange with the OTHER depth when clicked", () => {
    const onChange = vi.fn();
    render(<DepthStripToggle value="plain_language" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Researcher" }));
    expect(onChange).toHaveBeenCalledWith("researcher");
  });

  it("does nothing when the already-selected option is clicked", () => {
    // Re-running the same question at the depth already on screen would
    // burn a run and a cap slot for nothing the reader asked for.
    const onChange = vi.fn();
    render(<DepthStripToggle value="plain_language" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Plain language" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("is locked while a search runs, matching item 9.12", () => {
    const onChange = vi.fn();
    render(<DepthStripToggle value="plain_language" onChange={onChange} locked />);
    const researcher = screen.getByRole("button", { name: "Researcher" });
    expect(researcher).toBeDisabled();
    fireEvent.click(researcher);
    expect(onChange).not.toHaveBeenCalled();
  });
});
