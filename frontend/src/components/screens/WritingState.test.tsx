/**
 * "{Lead} is writing the answer", 2026-09-14 (product-owner request: "show
 * people the answer is loading, in the sense like [scientist] is writing the
 * answer....").
 *
 * WHAT THIS FILE PINS:
 * - during Write the caption reads "{Lead} is writing the answer" followed
 *   by an ellipsis, and no other step shows the ellipsis;
 * - the caption and its ellipsis are gone once the run lands or is stopped;
 * - under prefers-reduced-motion the ellipsis is static;
 * - while sentences stream in, a "writing" mark sits after them, and it goes
 *   when the run lands or is stopped.
 *
 * WHAT IT DOES NOT PIN: that the dots visibly animate in a browser (jsdom runs
 * no animations). The reduced-motion arm asserts the opacity the dots settle
 * at, which is the rendered fact jsdom can compute.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunProgress } from "./RunProgress";
import { AnswerScreen } from "./AnswerScreen";

const CLAIMS = [{ text: "BRCA1 is a gene.", layer: 2 as const, citations: [] }];

function mockReducedMotion(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("prefers-reduced-motion") ? matches : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the lead's writing caption", () => {
  it("reads '{Lead} is writing the answer' with an animated ellipsis during Write", () => {
    render(<RunProgress question="q" activeStep="Write" startedAt={Date.now()} personaName="Mendel" />);
    const caption = screen.getByTestId("persona-caption");
    expect(caption).toHaveTextContent("Mendel is writing the answer...");
    const dots = screen.getByTestId("persona-caption-ellipsis");
    expect(dots).toHaveAttribute("aria-hidden", "true");
    expect(dots).toHaveAttribute("data-motion", "animated");
  });

  it("shows no ellipsis on any other step", () => {
    const { rerender } = render(
      <RunProgress question="q" activeStep="Act" startedAt={Date.now()} personaName="Mendel" />,
    );
    expect(screen.getByTestId("persona-caption")).toHaveTextContent("Mendel is reading the records");
    expect(screen.queryByTestId("persona-caption-ellipsis")).toBeNull();
    rerender(<RunProgress question="q" activeStep="Plan" startedAt={Date.now()} personaName="Mendel" />);
    expect(screen.queryByTestId("persona-caption-ellipsis")).toBeNull();
  });

  it("is gone after the run lands and after Stop", () => {
    const { rerender } = render(
      <RunProgress question="q" activeStep="Write" startedAt={Date.now()} personaName="Mendel" />,
    );
    expect(screen.getByTestId("persona-caption-ellipsis")).toBeInTheDocument();

    // Landed: `App` passes a null step and a null start.
    rerender(<RunProgress question="q" activeStep={null} startedAt={null} personaName="Mendel" />);
    expect(screen.queryByTestId("persona-caption")).toBeNull();
    expect(screen.queryByTestId("persona-caption-ellipsis")).toBeNull();

    // Stopped: `App` passes `stopped` with a null step.
    rerender(
      <RunProgress question="q" activeStep={null} startedAt={null} stopped personaName="Mendel" />,
    );
    expect(screen.getByTestId("run-stopped")).toBeInTheDocument();
    expect(screen.queryByTestId("persona-caption-ellipsis")).toBeNull();
  });

  it("is static under prefers-reduced-motion", () => {
    mockReducedMotion(true);
    render(<RunProgress question="q" activeStep="Write" startedAt={Date.now()} personaName="Mendel" />);
    const dots = screen.getByTestId("persona-caption-ellipsis");
    expect(dots).toHaveAttribute("data-motion", "static");
    for (const dot of Array.from(dots.children)) {
      expect(getComputedStyle(dot).opacity).toBe("1");
    }
  });

  it("dims the dots for animation when motion is allowed (the mutation arm for the one above)", () => {
    mockReducedMotion(false);
    render(<RunProgress question="q" activeStep="Write" startedAt={Date.now()} personaName="Mendel" />);
    const dots = screen.getByTestId("persona-caption-ellipsis");
    expect(dots).toHaveAttribute("data-motion", "animated");
    expect(getComputedStyle(dots.children[0] as Element).opacity).toBe("0.35");
  });
});

describe("the writing mark under a streaming answer", () => {
  const progress = <RunProgress activeStep="Write" startedAt={Date.now()} personaName="Mendel" />;

  it("sits after the streamed sentences while the run is live", () => {
    render(<AnswerScreen question="q" progress={progress} claims={CLAIMS} sources={[]} />);
    const mark = screen.getByTestId("streaming-writing-indicator");
    expect(mark).toHaveTextContent("writing...");
    // AFTER the claims, not before them.
    const claims = screen.getByTestId("claims");
    expect(claims.compareDocumentPosition(mark) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("is gone once the run lands", () => {
    render(<AnswerScreen question="q" claims={CLAIMS} sources={[]} />);
    expect(screen.getByTestId("claim-text-0")).toBeInTheDocument();
    expect(screen.queryByTestId("streaming-writing-indicator")).toBeNull();
  });

  it("is gone once the run is stopped, even though the partial sentences stay", () => {
    render(<AnswerScreen question="q" progress={progress} stopped claims={CLAIMS} sources={[]} />);
    expect(screen.getByTestId("claim-text-0")).toBeInTheDocument();
    expect(screen.queryByTestId("streaming-writing-indicator")).toBeNull();
  });

  it("is static under prefers-reduced-motion", () => {
    mockReducedMotion(true);
    render(<AnswerScreen question="q" progress={progress} claims={CLAIMS} sources={[]} />);
    const mark = screen.getByTestId("streaming-writing-indicator");
    const dots = mark.querySelector('[data-motion]');
    expect(dots).toHaveAttribute("data-motion", "static");
  });
});
