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

import { ThemeProvider } from "@mui/material";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { theme } from "../../theme";
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

    const group = screen.getByRole("group", { name: /answer mode/i });
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

    expect(screen.queryByRole("group", { name: /answer mode/i })).toBeNull();
  });

  const STEPS = [{ step: "Think" as const, at: "0.1s", text: "Read the question." }];
  let lastRerender: ReturnType<typeof render>["rerender"];
  const renderLanded = (
    onDepthChange = vi.fn(),
    extra: Record<string, unknown> = {},
    depthValue: "plain_language" | "researcher" = "plain_language",
  ) => {
    const result = render(
      <ThemeProvider theme={theme}>
        <AnswerScreen
          question="Which diseases are associated with BRCA1?"
          claims={[CLAIM]}
          sources={[SOURCE]}
          meta="1 tool · 1 source from 1 layer"
          outcome="Answered"
          steps={STEPS}
          onDepthChange={onDepthChange}
          depthValue={depthValue}
          {...extra}
        />
      </ThemeProvider>,
    );
    lastRerender = result.rerender;
    return onDepthChange;
  };

  it("clicking the other mode shows the cost line and runs nothing", async () => {
    // Card 24 cost step. Mutation: the toggle's handler also calls
    // `onDepthChange` (`(m) => { setHeldDepth(m); onDepthChange?.(m); }`).
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Researcher" }));

    expect(screen.getByTestId("answer-depth-confirm")).toHaveTextContent(
      "Ask this question again in Researcher? It runs as one new search.",
    );
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
    expect(screen.queryByRole("group", { name: /answer mode/i })).toBeNull();
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
    expect(screen.getAllByRole("group", { name: /answer mode/i })).toHaveLength(1);
  });

  it("the cost line has no number for any reader (J-24-01, A-24-05)", async () => {
    // Mutation: the line text gains "(5 left today)".
    const user = userEvent.setup();
    renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    expect(screen.getByTestId("answer-depth-confirm").textContent).not.toMatch(/\d/);
    expect(screen.getByTestId("answer-depth-confirm").textContent).not.toMatch(/left/i);
  });

  it("Cancel returns focus to the switch button that opened the line (J-24-02)", async () => {
    // Mutation: cancelHeld stops calling focus().
    const user = userEvent.setup();
    renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Researcher" })).toHaveFocus();
  });

  it("Ask again moves focus to the question heading (J-24-02)", async () => {
    // Mutation: the Ask again wrapper stops focusing the heading.
    const user = userEvent.setup();
    renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    await user.click(screen.getByRole("button", { name: "Ask again" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveFocus();
  });

  it("Escape closes the line without running and returns focus to the switch (J-24-03)", async () => {
    // Mutation: the Escape branch is removed from the strip's key handler.
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
    expect(screen.getByRole("button", { name: "Researcher" })).toHaveFocus();
    expect(onDepthChange).not.toHaveBeenCalled();
  });

  it("clicking the lit mode while the line is open closes it and runs nothing (J-24-04, A-24-03)", async () => {
    // Mutation: DepthStripToggle stops calling onSelectCurrent.
    const user = userEvent.setup();
    const onDepthChange = renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    expect(screen.getByTestId("answer-depth-confirm")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Plain language" }));
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
    expect(onDepthChange).not.toHaveBeenCalled();
  });

  it("Tab from the switch reaches Ask again, then Cancel, then Show work (J-24-03)", async () => {
    // Mutation: the line is rendered after the Show work button in the DOM.
    const user = userEvent.setup();
    renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    await user.tab();
    expect(screen.getByRole("button", { name: "Ask again" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: /show work/i })).toHaveFocus();
  });

  it.each([
    ["a refusal", { refusal: "Outside biomedical research." }],
    ["a refusal label (also how an ask-back arrives)", { refusalLabel: "Needs a narrower question" }],
    ["a failure", { failure: "The run failed." }],
    ["a capped answer", { capMessage: "Stopped on its processing budget." }],
  ])("offers no switch on %s (A-24-01, J-24-12)", (_name, extra) => {
    // Mutation: `switchable` ignores that outcome field.
    renderLanded(vi.fn(), extra);
    expect(screen.queryByRole("group", { name: /answer mode/i })).toBeNull();
  });

  it("labels each folded answer with the mode it was asked at (J-24-06)", () => {
    // Mutation: FoldedTurn stops rendering the mode label.
    const previousTurns: PreviousTurn[] = [
      { question: "Q", meta: "m", claims: [CLAIM], sources: [SOURCE], outcome: "Answered", depth: "plain_language" },
      { question: "Q", meta: "m", claims: [CLAIM], sources: [SOURCE], outcome: "Answered", depth: "researcher" },
    ];
    renderLanded(vi.fn(), { previousTurns }, "researcher");
    expect(screen.getByTestId("previous-turn-0-mode")).toHaveTextContent("Plain language");
    expect(screen.getByTestId("previous-turn-1-mode")).toHaveTextContent("Researcher");
  });

  it("draws 4px corners, the design's, in the app theme (J-24-07)", () => {
    // Mutation: borderRadius back to 1 (8px).
    renderLanded();
    const group = screen.getByRole("group", { name: /answer mode/i });
    expect(getComputedStyle(group).borderRadius).toBe("4px");
  });

  it("names the control as the home page does (J-24-08)", () => {
    // Mutation: aria-label back to "Answer depth".
    renderLanded();
    expect(screen.getByRole("group", { name: "Answer mode, audience-level depth" })).toBeInTheDocument();
  });

  it("clears the held mode when the answer's mode changes (J-24-09)", async () => {
    // Mutation: the clearing useEffect in AnswerBody removed.
    const user = userEvent.setup();
    renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    expect(screen.getByTestId("answer-depth-confirm")).toBeInTheDocument();
    lastRerender(
      <ThemeProvider theme={theme}>
        <AnswerScreen
          question="Which diseases are associated with BRCA1?"
          claims={[CLAIM]}
          sources={[SOURCE]}
          meta="1 tool · 1 source from 1 layer"
          outcome="Answered"
          steps={STEPS}
          onDepthChange={vi.fn()}
          depthValue="researcher"
        />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
  });

  it("clears the held mode when the question changes (J-24-09)", async () => {
    // Mutation: the same useEffect removed.
    const user = userEvent.setup();
    renderLanded();
    await user.click(screen.getByRole("button", { name: "Researcher" }));
    lastRerender(
      <ThemeProvider theme={theme}>
        <AnswerScreen
          question="A different question?"
          claims={[CLAIM]}
          sources={[SOURCE]}
          meta="1 tool · 1 source from 1 layer"
          outcome="Answered"
          steps={STEPS}
          onDepthChange={vi.fn()}
          depthValue="plain_language"
        />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
  });
});
