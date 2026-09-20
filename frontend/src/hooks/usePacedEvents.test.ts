/**
 * The presentation queue, UI fix 11.28, 2026-09-14.
 *
 * WHAT THIS PINS:
 * - a run whose events all arrive at once is released one stage at a time, in
 *   arrival order, with each stage's minimum dwell (guard, think, plan, each
 *   helper's search appearing, the handoff, each search completing), and the
 *   result is always a prefix of what arrived;
 * - a run already slower than the pacing is shown the moment each event
 *   arrives, with no delay at all;
 * - nothing is ever held more than `maxLagMs` behind its own arrival;
 * - Stop, a failed stream, an `error` event and a failed guard flush at once
 *   and leave no timer;
 * - reduced motion keeps the order with the minimum dwells;
 * - a new run, or a reset buffer, starts from zero.
 *
 * WHAT IT DOES NOT PIN: how the stages look (RunProgress tests and the
 * bold-and-stagger e2e screenshots) or `useAnswerReveal`'s own banner time.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentEvent } from "../lib/events";
import { PACING, REDUCED_PACING, usePacedEvents } from "./usePacedEvents";

let seq = 0;
function ev(type: string, payload: Record<string, unknown>): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "t", seq, ts: "2026-09-14T00:00:00Z", payload } as unknown as AgentEvent;
}

function run(helpers = 2): AgentEvent[] {
  const ids = Array.from({ length: helpers }, (_, i) => `c${i + 1}`);
  return [
    ev("guard", { passed: true, category: "ok", reason: null }),
    ev("think", { narrative: "n", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
    ev("plan", { narrative: "p", tool_calls: [] }),
    ...ids.map((id) => ev("tool_start", { call_id: id, tool: "ncbi_efetch", layer: "layer_2_api", status: "running" })),
    ...ids.map((id) =>
      ev("tool_result", { call_id: id, tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", summary: "", result_count: 3, truncated: false }),
    ),
    ev("token", { text: "A sentence. ", marker_ids: [] }),
    ev("done", { total_cost_usd: 0, total_tool_calls: helpers, elapsed_ms: 1, trust_outcome: "answer" }),
  ];
}

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

/** Advance in small steps, each in its own `act`, so effects reschedule between them. */
function advance(ms: number, step = 10) {
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    act(() => vi.advanceTimersByTime(Math.min(step, ms - elapsed)));
  }
}

describe("usePacedEvents", () => {
  it("releases a burst one stage at a time, in order, with each minimum dwell", () => {
    const events = run(2);
    const { result } = renderHook(() => usePacedEvents(events, { runKey: "r1", stopped: false }));

    // Populate-check: nine events arrived at once.
    expect(events).toHaveLength(9);
    // The time each count first appears, in ms since arrival.
    const firstSeen = new Map<number, number>([[result.current.length, 0]]);
    for (let t = 10; t <= PACING.maxLagMs + 100; t += 10) {
      act(() => vi.advanceTimersByTime(10));
      if (!firstSeen.has(result.current.length)) firstSeen.set(result.current.length, t);
      // Always a prefix of what arrived, never a reordering.
      result.current.forEach((event, i) => expect(event).toBe(events[i]));
    }
    const at = (n: number) => firstSeen.get(n);
    expect(at(1)).toBe(0); // guard: the lead starting
    expect(at(2)).toBe(PACING.guardMs); // think
    expect(at(3)).toBe(PACING.guardMs + PACING.thinkMs); // plan
    const planAt = PACING.guardMs + PACING.thinkMs + PACING.planMs;
    expect(at(4)).toBe(planAt); // first helper's search appears
    expect(at(5)).toBe(planAt + PACING.helperGapMs); // second helper's search appears
    const handoffEnd = planAt + PACING.helperGapMs + PACING.handoffMs;
    expect(at(6)).toBe(handoffEnd); // first search completes
    // Second completes; the token and done follow with no dwell of their own.
    expect(at(7)).toBeUndefined();
    expect(at(8)).toBeUndefined();
    expect(at(9)).toBe(handoffEnd + PACING.helperGapMs);
    expect(at(9)).toBeLessThanOrEqual(PACING.maxLagMs);
    expect(result.current).toBe(events);
  });

  it("adds no delay at all when the real run is slower than the pacing", () => {
    const all = run(2);
    const { result, rerender } = renderHook(
      ({ events }) => usePacedEvents(events, { runKey: "r1", stopped: false }),
      { initialProps: { events: all.slice(0, 1) } },
    );
    for (let n = 1; n <= all.length; n += 1) {
      const arrived = all.slice(0, n);
      rerender({ events: arrived });
      // Shown the moment it arrives: the very array that arrived.
      expect(result.current).toBe(arrived);
      act(() => vi.advanceTimersByTime(2000));
    }
  });

  it("never holds an event more than maxLagMs behind its arrival", () => {
    const events = run(4);
    const { result } = renderHook(() => usePacedEvents(events, { runKey: "r1", stopped: false }));
    // Populate-check: the full dwells for four helpers exceed the cap.
    const uncapped =
      PACING.guardMs + PACING.thinkMs + PACING.planMs + 3 * PACING.helperGapMs + PACING.handoffMs + 3 * PACING.helperGapMs;
    expect(uncapped).toBeGreaterThan(PACING.maxLagMs);
    advance(PACING.maxLagMs - 10);
    expect(result.current.length).toBeLessThan(events.length);
    advance(20);
    expect(result.current).toBe(events);
  });

  it("flushes at once when Stop latches, and leaves no timer", () => {
    const events = run(2);
    const { result, rerender } = renderHook(
      ({ stopped }) => usePacedEvents(events, { runKey: "r1", stopped }),
      { initialProps: { stopped: false } },
    );
    advance(PACING.guardMs + 10);
    expect(result.current).toHaveLength(2);
    rerender({ stopped: true });
    expect(result.current).toBe(events);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("flushes at once when the stream failed", () => {
    const events = run(2);
    const { result } = renderHook(() => usePacedEvents(events, { runKey: "r1", stopped: false, flush: true }));
    expect(result.current).toBe(events);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("shows an error or a refusal at once", () => {
    const withError = [
      ...run(2).slice(0, 4),
      ev("error", { fatal: true, scope: "run", source: "x", error_class: "transient", message: "m" }),
    ];
    const errored = renderHook(() => usePacedEvents(withError, { runKey: "r1", stopped: false }));
    expect(errored.result.current).toBe(withError);

    const refused = [
      ev("guard", { passed: false, category: "off_topic", reason: null }),
      ev("done", { total_cost_usd: 0, total_tool_calls: 0, elapsed_ms: 1, trust_outcome: "refuse" }),
    ];
    const guarded = renderHook(() => usePacedEvents(refused, { runKey: "r2", stopped: false }));
    expect(guarded.result.current).toBe(refused);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps the order under reduced motion with the minimum dwells", () => {
    const events = run(2);
    const { result } = renderHook(() =>
      usePacedEvents(events, { runKey: "r1", stopped: false, reducedMotion: true }),
    );
    const counts = [result.current.length];
    for (let t = 0; t < 600; t += 10) {
      act(() => vi.advanceTimersByTime(10));
      counts.push(result.current.length);
    }
    // Still one stage at a time (never shrinks, starts at the guard alone)...
    expect(counts[0]).toBe(1);
    expect(counts.every((n, i) => i === 0 || n >= counts[i - 1]!)).toBe(true);
    expect(new Set(counts).size).toBeGreaterThan(5);
    // ...and finished by the sum of the reduced dwells.
    const reducedTotal =
      REDUCED_PACING.guardMs + REDUCED_PACING.thinkMs + REDUCED_PACING.planMs +
      REDUCED_PACING.helperGapMs + REDUCED_PACING.handoffMs + REDUCED_PACING.helperGapMs;
    expect(reducedTotal).toBeLessThan(PACING.maxLagMs / 5);
    expect(result.current).toBe(events);
  });

  it("starts from zero for a new run and for a reset buffer", () => {
    const first = run(1);
    const { result, rerender } = renderHook(
      ({ events, runKey }) => usePacedEvents(events, { runKey, stopped: false }),
      { initialProps: { events: first, runKey: "r1" } },
    );
    advance(PACING.maxLagMs + 50);
    expect(result.current).toBe(first);

    const second = run(1);
    rerender({ events: second, runKey: "r2" });
    expect(result.current).toHaveLength(1);
    expect(result.current[0]).toBe(second[0]);

    // Same key, but the buffer was reset and refilled with different events.
    const refilled = run(1);
    rerender({ events: refilled, runKey: "r2" });
    expect(result.current).toHaveLength(1);
    expect(result.current[0]).toBe(refilled[0]);
  });
});
