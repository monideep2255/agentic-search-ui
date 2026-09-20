/**
 * The one-by-one answer reveal, 2026-09-14.
 *
 * WHAT THIS PINS:
 * - a burst of 5 sentences that arrives at once is revealed progressively,
 *   one per `perItemMs`, never all at once;
 * - the first sentence waits until the writing state has been visible for
 *   `minBannerMs`;
 * - once `done` has arrived, the rest is revealed at `afterDoneMs` each, the
 *   view stays unlanded until the last one, and the landed view is the input
 *   object itself (nothing dropped);
 * - Stop mid-reveal freezes the count and leaves no pending timer;
 * - a run with no sentences (a refusal) passes straight through;
 * - a new run starts from zero.
 *
 * WHAT IT DOES NOT PIN: the rise animation (CSS, see AnswerScreen tests).
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EMPTY_RUN_VIEW } from "./useRunView";
import type { RunView } from "./useRunView";
import { REVEAL_TIMING, useAnswerReveal } from "./useAnswerReveal";

function viewWith(n: number, overrides: Partial<RunView> = {}): RunView {
  return {
    ...EMPTY_RUN_VIEW,
    activeStep: "Write",
    reachedSteps: ["Guard", "Think", "Plan", "Act", "Write"],
    claims: Array.from({ length: n }, (_, i) => ({
      text: `Sentence ${i + 1}.`,
      layer: 2 as const,
      citations: [i + 1],
    })),
    ...overrides,
  };
}

beforeEach(() => {
  vi.useFakeTimers();
});

/**
 * Advance in small steps, each inside its own `act`, because React schedules
 * the NEXT reveal timer in an effect that runs only after `act` returns.
 */
function advance(ms: number, step = 10) {
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    act(() => vi.advanceTimersByTime(Math.min(step, ms - elapsed)));
  }
}
afterEach(() => {
  vi.useRealTimers();
});

describe("useAnswerReveal", () => {
  it("reveals a burst of 5 sentences one at a time, not all at once", () => {
    const { result, rerender } = renderHook(
      ({ view }) => useAnswerReveal(view, { runKey: "run-1", stopped: false }),
      { initialProps: { view: viewWith(0) } },
    );
    // The writing state has already been on screen for longer than the minimum.
    act(() => vi.advanceTimersByTime(REVEAL_TIMING.minBannerMs + 10));
    rerender({ view: viewWith(5) });

    // Populate-check: the input really carries five sentences.
    expect(viewWith(5).claims).toHaveLength(5);
    act(() => vi.advanceTimersByTime(0));
    expect(result.current.claims).toHaveLength(1);
    expect(result.current.activeStep).toBe("Write");

    const seen = [result.current.claims.length];
    for (let i = 0; i < 4; i += 1) {
      act(() => vi.advanceTimersByTime(REVEAL_TIMING.perItemMs));
      seen.push(result.current.claims.length);
    }
    expect(seen).toEqual([1, 2, 3, 4, 5]);
  });

  it("keeps the writing banner up for the minimum before the first sentence", () => {
    const { result, rerender } = renderHook(
      ({ view }) => useAnswerReveal(view, { runKey: "run-1", stopped: false }),
      { initialProps: { view: viewWith(0) } },
    );
    // Tokens land 200ms after Write began: a fast write.
    act(() => vi.advanceTimersByTime(200));
    rerender({ view: viewWith(3) });
    act(() => vi.advanceTimersByTime(REVEAL_TIMING.minBannerMs - 300));
    expect(result.current.claims).toHaveLength(0);
    act(() => vi.advanceTimersByTime(150));
    expect(result.current.claims).toHaveLength(1);
  });

  it("finishes quickly once done arrives, stays unlanded until the end, and drops nothing", () => {
    const landedView = viewWith(5, { landed: true, activeStep: null, meta: "1 tool · 5 sources" });
    const { result } = renderHook(
      ({ view }) => useAnswerReveal(view, { runKey: "run-1", stopped: false }),
      { initialProps: { view: landedView } },
    );
    act(() => vi.advanceTimersByTime(REVEAL_TIMING.minBannerMs));
    expect(result.current.claims).toHaveLength(1);
    expect(result.current.landed).toBe(false);
    expect(result.current.activeStep).toBe("Write");
    expect(result.current.meta).toBe("");

    for (let i = 2; i <= 4; i += 1) {
      act(() => vi.advanceTimersByTime(REVEAL_TIMING.afterDoneMs));
      expect(result.current.claims).toHaveLength(i);
      expect(result.current.landed).toBe(false);
    }
    act(() => vi.advanceTimersByTime(REVEAL_TIMING.afterDoneMs));
    // Landed, and it is the very object that arrived.
    expect(result.current).toBe(landedView);
    expect(result.current.claims.map((c) => c.text)).toEqual(landedView.claims.map((c) => c.text));
  });

  it("freezes cleanly when Stop latches mid-reveal", () => {
    const { result, rerender } = renderHook(
      ({ view, stopped }) => useAnswerReveal(view, { runKey: "run-1", stopped }),
      { initialProps: { view: viewWith(5), stopped: false } },
    );
    advance(REVEAL_TIMING.minBannerMs + REVEAL_TIMING.perItemMs);
    expect(result.current.claims).toHaveLength(2);

    rerender({ view: viewWith(5), stopped: true });
    expect(vi.getTimerCount()).toBe(0);
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.claims).toHaveLength(2);
    expect(result.current.landed).toBe(false);
  });

  it("cuts the banner minimum under reduced motion, keeping banner-then-sentences order", () => {
    const { result, rerender } = renderHook(
      ({ view }) => useAnswerReveal(view, { runKey: "run-1", stopped: false, reducedMotion: true }),
      { initialProps: { view: viewWith(0) } },
    );
    rerender({ view: viewWith(3) });
    // Populate-check: the reduced minimum really is shorter.
    expect(REVEAL_TIMING.reducedMinBannerMs).toBeLessThan(REVEAL_TIMING.minBannerMs);
    act(() => vi.advanceTimersByTime(REVEAL_TIMING.reducedMinBannerMs - 50));
    expect(result.current.claims).toHaveLength(0);
    act(() => vi.advanceTimersByTime(60));
    expect(result.current.claims).toHaveLength(1);
  });

  it("shows everything at once when the stream failed", () => {
    const failed = viewWith(4);
    const { result } = renderHook(() =>
      useAnswerReveal(failed, { runKey: "run-1", stopped: false, flush: true }),
    );
    // Populate-check: four sentences arrived, and all four show immediately.
    expect(result.current.claims).toHaveLength(4);
    expect(result.current).toBe(failed);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("passes a run with no sentences straight through", () => {
    const refusal = { ...EMPTY_RUN_VIEW, landed: true, refusal: "No answer found." };
    const { result } = renderHook(() => useAnswerReveal(refusal, { runKey: "run-1", stopped: false }));
    expect(result.current).toBe(refusal);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("starts a new run from zero", () => {
    const { result, rerender } = renderHook(
      ({ view, runKey }) => useAnswerReveal(view, { runKey, stopped: false }),
      { initialProps: { view: viewWith(2, { landed: true }), runKey: "run-1" } },
    );
    advance(REVEAL_TIMING.minBannerMs + 200);
    expect(result.current.claims).toHaveLength(2);

    rerender({ view: viewWith(3), runKey: "run-2" });
    expect(result.current.claims).toHaveLength(0);
    act(() => vi.advanceTimersByTime(REVEAL_TIMING.minBannerMs));
    expect(result.current.claims).toHaveLength(1);
  });
});
