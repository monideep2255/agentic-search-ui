/**
 * UI fix plan item 12.3: a bare one-to-three-word question that opens a
 * conversation ("reflux disease", "GERD") gets a clarifying question PLUS
 * four full questions the reader can pick with one click, rather than only
 * the free-text field item 7.5's own clarification already gives.
 *
 * This file pins what the frontend owns: the four options render as
 * clickable chips, clicking one asks that EXACT question (not the
 * clarification's own wording), and they stay visible under a
 * clarification even though item 12.4 hides the generic three hints there
 * (`FollowUp.refusal.test.tsx` owns that suppression; this file is its
 * sibling for the options that must NOT be suppressed the same way).
 *
 * NOT exercised: how `useRunView` derives `clarificationOptions` from the
 * `think` event (`useRunView.clarificationOptions.test.ts` owns that), and
 * the backend's `_bare_topic_clarification`
 * (`tests/system_03_search_agent/core/test_bare_topic_clarification.py`).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FollowUp } from "./FollowUp";

const CLARIFYING_OPTIONS = [
  "What is reflux disease and what are its symptoms?",
  "Which genes or variants are linked to reflux disease?",
  "Are there clinical trials for reflux disease?",
  "What does recent research say about reflux disease?",
];

describe("the clarification's four ready-made options", () => {
  it("renders all four as chips", () => {
    render(<FollowUp clarifyingOptions={CLARIFYING_OPTIONS} isRefusal />);

    const chips = screen.getAllByTestId("clarifying-option");
    // POPULATE-CHECK: exactly four, not "at least one", so a regression
    // that dropped three of them still fails this arm.
    expect(chips).toHaveLength(4);
    for (const option of CLARIFYING_OPTIONS) {
      expect(screen.getByText(option)).toBeInTheDocument();
    }
  });

  it("clicking one option asks that exact question, not the others", async () => {
    const onAsk = vi.fn();
    render(<FollowUp clarifyingOptions={CLARIFYING_OPTIONS} isRefusal onAsk={onAsk} />);

    await userEvent.click(
      screen.getByText("Which genes or variants are linked to reflux disease?"),
    );

    expect(onAsk).toHaveBeenCalledTimes(1);
    expect(onAsk).toHaveBeenCalledWith(
      "Which genes or variants are linked to reflux disease?",
    );
  });

  it("clicking a different option asks THAT one, proving no chip is wired to a fixed index", async () => {
    const onAsk = vi.fn();
    render(<FollowUp clarifyingOptions={CLARIFYING_OPTIONS} isRefusal onAsk={onAsk} />);

    await userEvent.click(screen.getByText("Are there clinical trials for reflux disease?"));

    expect(onAsk).toHaveBeenCalledWith("Are there clinical trials for reflux disease?");
    expect(onAsk).not.toHaveBeenCalledWith(
      "Which genes or variants are linked to reflux disease?",
    );
  });

  it("stays visible under a clarification, unlike the generic hints item 12.4 hides", () => {
    // The load-bearing arm for item 12.3's own design: a clarification is
    // a refusal (`isRefusal` true, matching how `App.tsx` actually sets
    // it), and item 12.4 correctly hides the three generic hint chips
    // there, but these four are the ANSWER to the clarification, not a
    // suggestion that assumes something was found, so hiding them would
    // turn one dead end into two.
    render(
      <FollowUp
        hints={["What variants cause it?"]}
        isRefusal
        clarifyingOptions={CLARIFYING_OPTIONS}
      />,
    );

    expect(screen.getAllByTestId("clarifying-option")).toHaveLength(4);
    // The unrelated generic hint is still correctly suppressed.
    expect(screen.queryByText("What variants cause it?")).not.toBeInTheDocument();
  });

  it("renders nothing when there is no clarification, null and omitted both", () => {
    // The wire field is optional AND nullable: an ordinary answer, an
    // older backend, and item 7.5's own clarification (which sends no
    // options) must all render identically to each other here.
    const { rerender } = render(<FollowUp clarifyingOptions={null} />);
    expect(screen.queryByTestId("clarifying-options")).toBeNull();

    rerender(<FollowUp />);
    expect(screen.queryByTestId("clarifying-options")).toBeNull();

    rerender(<FollowUp clarifyingOptions={[]} />);
    expect(screen.queryByTestId("clarifying-options")).toBeNull();
  });
});
