/**
 * Build phase 6.2, T-6.2-08: the next-step offer, on the frontend.
 *
 * The backend decides WHETHER there is an honest offer and what it says.
 * This file pins the two things the frontend is responsible for:
 *
 *   - Accepting an offer continues the thread, because it dispatches
 *     through the same `onAsk` as anything typed. That was the product
 *     owner's condition on the whole feature: an offer the system makes and
 *     then forgets making is worse than no offer.
 *   - No offer means nothing is rendered, with no empty box and no
 *     placeholder, because a system that always asks something pads.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FollowUp } from "./FollowUp";

const OFFER = "Would you like me to go through the 3 further disease records found for this question?";

describe("the next-step offer", () => {
  it("renders the offer the backend actually sent", () => {
    render(<FollowUp nextStep={OFFER} />);
    expect(screen.getByTestId("next-step-offer")).toHaveTextContent(
      "3 further disease records",
    );
  });

  it("renders nothing at all when there is no honest next step", () => {
    // Both the null and the omitted case, because the wire field is
    // optional AND nullable: a backend predating this feature sends
    // neither, and the two must behave identically.
    const { rerender } = render(<FollowUp nextStep={null} />);
    expect(screen.queryByTestId("next-step-offer")).toBeNull();

    rerender(<FollowUp />);
    expect(screen.queryByTestId("next-step-offer")).toBeNull();
  });

  it("accepting the offer asks it as a follow-up, continuing the thread", async () => {
    // THE LOAD-BEARING ARM. If accepting an offer ever dispatched through
    // anything other than `onAsk`, it would start a fresh run and the
    // system would have proposed a topic and then forgotten proposing it,
    // which is the exact failure the ordering of T-6.2-07 before T-6.2-08
    // exists to prevent.
    const onAsk = vi.fn();
    render(<FollowUp nextStep={OFFER} onAsk={onAsk} />);

    await userEvent.click(screen.getByTestId("next-step-accept"));

    expect(onAsk).toHaveBeenCalledTimes(1);
    expect(onAsk).toHaveBeenCalledWith(OFFER);
  });

  /*
   * UI fix set 7, R21. The product owner: "Yes, go deeper" must send a real
   * question, not the offer's yes/no wording.
   *
   * The offer above is addressed to a reader and reads as a yes/no
   * question about the interface. Sending it to the agent verbatim ran a
   * biomedical search on "Would you like me to go through the 3 further
   * disease records found for this question?", which is not a question
   * about biology and cannot be answered as one.
   */
  const OFFER_QUERY = "What are the 3 further diseases associated with BRCA1?";

  it("sends the backend's searchable question, not the offer's wording", async () => {
    const onAsk = vi.fn();
    render(<FollowUp nextStep={OFFER} nextStepQuery={OFFER_QUERY} onAsk={onAsk} />);

    await userEvent.click(screen.getByTestId("next-step-accept"));

    expect(onAsk).toHaveBeenCalledTimes(1);
    expect(onAsk).toHaveBeenCalledWith(OFFER_QUERY);
    // Stated as its own assertion rather than left to the equality above,
    // because this is the defect: the old code passed `nextStep` here and
    // an equality that merely happened to differ would not say why.
    expect(onAsk).not.toHaveBeenCalledWith(OFFER);
  });

  it("still shows the offer's own wording on screen, unchanged", () => {
    // The two strings have different audiences. Sending the query must not
    // start showing the reader the query: an offer that reads like a search
    // box entry is not an offer.
    render(<FollowUp nextStep={OFFER} nextStepQuery={OFFER_QUERY} />);

    const offer = screen.getByTestId("next-step-offer");
    expect(offer).toHaveTextContent("3 further disease records");
    expect(offer).not.toHaveTextContent(OFFER_QUERY);
  });

  it("falls back to the offer text when the backend sends no query", async () => {
    // A backend predating R21 sends neither the field nor a value, and both
    // must behave exactly as they did before the field existed. Without
    // this arm, a fallback that dispatched nothing at all would leave the
    // button dead against every older backend and every test above would
    // still pass, since they all supply the offer alone.
    const onAsk = vi.fn();
    const { rerender } = render(
      <FollowUp nextStep={OFFER} nextStepQuery={null} onAsk={onAsk} />,
    );
    await userEvent.click(screen.getByTestId("next-step-accept"));
    expect(onAsk).toHaveBeenLastCalledWith(OFFER);

    rerender(<FollowUp nextStep={OFFER} onAsk={onAsk} />);
    await userEvent.click(screen.getByTestId("next-step-accept"));
    expect(onAsk).toHaveBeenLastCalledWith(OFFER);
    expect(onAsk).toHaveBeenCalledTimes(2);
  });

  it("keeps the offer separate from the fixed hint menu", () => {
    // The hints are the same three on every answer. The offer is one
    // sentence about THIS answer, earned from what this retrieval left out.
    // Folding it into the menu would make a specific offer look generic,
    // which is a presentation choice with a correctness flavour: a reader
    // who learns the menu is boilerplate will stop reading the offer too.
    // Distinctive hint text on purpose. An earlier version of this arm used
    // "a" and failed against the offer's own prose, because
    // `toHaveTextContent` matches a SUBSTRING and the offer contains the
    // letter a. The arm was wrong, not the component, and a single-letter
    // fixture is what made it wrong.
    const HINT = "Which trials are recruiting?";
    render(<FollowUp nextStep={OFFER} hints={[HINT]} />);

    const offer = screen.getByTestId("next-step-offer");
    expect(offer).toBeInTheDocument();
    expect(offer).not.toHaveTextContent(HINT);
    // And the hint is still rendered, outside the offer. Without this the
    // arm would pass on a component that dropped the hints entirely.
    expect(screen.getByText(HINT)).toBeInTheDocument();
  });
});
