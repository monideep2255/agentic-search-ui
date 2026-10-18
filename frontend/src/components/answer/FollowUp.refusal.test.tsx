/**
 * UI fix set 12, item 12.4: a refusal no longer invites the reader to
 * "continue" a conversation that produced nothing.
 *
 * A second tester, seeing "No answer found in NCBI records", asked in their
 * own words why they would "continue the conversation" and suggested "ask
 * another question" themselves. Their screenshot is in
 * `testing/User-feedback/`. Worse than the label: the three canned hint
 * chips ("What variants cause it?") each carry a referring word with no
 * antecedent on a refusal, which the backend's `_needs_clarification` then
 * catches, so the product's own suggestion walked the reader into a second
 * dead end.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FollowUp } from "./FollowUp";

const ANSWER_HINTS = ["What variants cause it?", "Which trials are recruiting?"];

describe("a refusal asks for another question, not a continued one", () => {
  it("reads 'Continue this conversation' with its hints on an ordinary answer", () => {
    // Mutation: hardcoding the refusal string, or dropping the isRefusal
    // check entirely, turns this red on the default (false) case.
    render(<FollowUp hints={ANSWER_HINTS} />);

    expect(screen.getByText("Continue this conversation")).toBeInTheDocument();
    expect(screen.queryByText("Ask another question")).not.toBeInTheDocument();
    expect(screen.getByText("What variants cause it?")).toBeInTheDocument();
  });

  it("switches to 'Ask another question' and hides the hints on a refusal", () => {
    // Mutation: only gating the heading and not the hints (or the reverse)
    // turns this red, since both assertions must hold together.
    render(<FollowUp hints={ANSWER_HINTS} isRefusal />);

    expect(screen.getByText("Ask another question")).toBeInTheDocument();
    expect(screen.queryByText("Continue this conversation")).not.toBeInTheDocument();
    expect(screen.queryByText("What variants cause it?")).not.toBeInTheDocument();
    expect(screen.queryByText("Which trials are recruiting?")).not.toBeInTheDocument();
  });

  it("suppresses the hints on a refusal even if a future caller forgets to withhold them", () => {
    // The load-bearing arm for "checked here, not only at the call site."
    // Mutation: moving the suppression to App.tsx alone (removing the
    // `!isRefusal &&` guard in FollowUp) would still pass every OTHER arm
    // here, since none of them pass hints while isRefusal is true from a
    // call site that also strips hints; this one does exactly that, the
    // shape a careless future caller would produce.
    render(<FollowUp hints={ANSWER_HINTS} isRefusal nextStep={null} />);

    expect(screen.queryByText("What variants cause it?")).not.toBeInTheDocument();
  });

  it("keeps the follow-up field itself on a refusal", () => {
    // A person who was refused must still be able to type their next
    // question without hunting for New search.
    render(<FollowUp hints={ANSWER_HINTS} isRefusal />);

    expect(screen.getByRole("textbox", { name: "Ask a follow-up question" })).toBeInTheDocument();
  });
});
