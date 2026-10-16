/**
 * Card 24 (2026-09-25): the Plain language / Researcher toggle on the
 * answer's own status strip, product-owner decision the same day. The
 * pre-ask control (`DepthControl`, chosen before asking) is unchanged and
 * covered by `components/controls/DepthControl.test.tsx`; this file pins
 * that `AnswerScreen` wires the compact strip toggle (`DepthStripToggle`,
 * same file) to the right place: present on the live turn, absent from a
 * streaming preview or a folded previous turn, and calling `onDepthChange`
 * with the OTHER depth rather than `AnswerScreen` re-running anything
 * itself, since re-running the question is the caller's job (`App.tsx`).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnswerScreen } from "./AnswerScreen";
import type { Claim, PreviousTurn, Source } from "./AnswerScreen";

const SOURCE: Source = {
  n: 1,
  layer: 1,
  name: "NCBI Gene 672",
  tool: "cypher_query",
  evidence: "curated assertion",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/gene/672",
};

const CLAIM: Claim = { text: "BRCA1 is associated with HBOC.", layer: 1, citations: [1] };

describe("AnswerScreen's depth toggle (card 24)", () => {
  it("renders the toggle on the landed answer's status strip when onDepthChange is given", () => {
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        meta="1 tool · 1 source from 1 layer"
        outcome="Answered"
        onDepthChange={vi.fn()}
        depthValue="plain_language"
      />,
    );

    const group = screen.getByRole("group", { name: /answer depth/i });
    expect(group).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plain language" })).toHaveAttribute("aria-pressed", "true");
  });

  it("does not render the toggle when the caller passes no onDepthChange", () => {
    // A caller with nothing to do about a depth change (there is none
    // today outside `App.tsx`) gets no interactive control it cannot act
    // on, rather than a toggle that silently does nothing when clicked.
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        meta="1 tool · 1 source from 1 layer"
        outcome="Answered"
      />,
    );

    expect(screen.queryByRole("group", { name: /answer depth/i })).toBeNull();
  });

  const renderLanded = (onDepthChange = vi.fn()) => {
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        meta="1 tool · 1 source from 1 layer"
        outcome="Answered"
        onDepthChange={onDepthChange}
        depthValue="plain_language"
        depthConfirmCopy={(label) => `COPY for ${label}`}
      />,
    );
    return onDepthChange;
  };

  it("clicking the other mode shows the cost line and runs nothing", async () => {
    // Card 24 cost step. Mutation: the toggle's handler also calls
    // `onDepthChange` (`(m) => { setHeldDepth(m); onDepthChange?.(m); }`).
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Researcher" }));

    expect(screen.getByTestId("answer-depth-confirm")).toHaveTextContent("COPY for Researcher");
    expect(onDepthChange).not.toHaveBeenCalled();
  });

  it("Ask again runs once with the held mode and closes the line", async () => {
    // Mutation: Ask again clears the held mode without calling onDepthChange.
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    await user.click(screen.getByRole("button", { name: "Ask again" }));

    expect(onDepthChange).toHaveBeenCalledTimes(1);
    expect(onDepthChange).toHaveBeenCalledWith("researcher");
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
  });

  it("Cancel closes the line and runs nothing", async () => {
    // Mutation: Cancel calls onDepthChange with the held mode.
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onDepthChange).not.toHaveBeenCalled();
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
  });

  it("clicking the mode already shown does nothing", async () => {
    // Mutation: the held setter accepts the shown mode.
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    await user.click(screen.getByRole("button", { name: "Plain language" }));

    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
    expect(onDepthChange).not.toHaveBeenCalled();
  });

  it("keeps a polite live region mounted before any mode is held", () => {
    renderLanded();
    expect(screen.getByTestId("answer-status-strip").querySelector('[aria-live="polite"]')).not.toBeNull();
  });

  it("does not appear on the streaming preview while a run is still in flight", () => {
    // `progress` present means `AnswerScreen` renders the RunProgress node
    // and, once claims arrive, a STREAMING AnswerBody, never the landed one
    // `onDepthChange` is wired to (item 9.12's lock: there is nothing to
    // switch to yet, and nothing running should be switchable).
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        progress={<div data-testid="stub-progress">running</div>}
        meta="1 tool · 1 source from 1 layer"
        outcome="Answered"
        onDepthChange={vi.fn()}
        depthValue="plain_language"
      />,
    );

    expect(screen.getByTestId("stub-progress")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /answer depth/i })).toBeNull();
  });

  it("does not appear on a folded previous turn", () => {
    const previousTurns: PreviousTurn[] = [
      {
        question: "What is BRCA1?",
        meta: "1 tool · 1 source from 1 layer",
        claims: [CLAIM],
        sources: [SOURCE],
        outcome: "Answered",
      },
    ];
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        meta="1 tool · 1 source from 1 layer"
        outcome="Answered"
        previousTurns={previousTurns}
        onDepthChange={vi.fn()}
        depthValue="plain_language"
      />,
    );

    // Exactly one toggle on the page: the live turn's, never a second one
    // repeated inside the folded turn above it.
    expect(screen.getAllByRole("group", { name: /answer depth/i })).toHaveLength(1);
  });
});
