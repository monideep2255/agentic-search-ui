/**
 * The presentation queue, UI fix 11.28 (2026-09-14) and its follow-up
 * (2026-09-20).
 *
 * WHAT THIS PINS:
 * - a run whose events all arrive at once is released one stage at a time, in
 *   arrival order, with each stage's minimum dwell (guard, think, plan, each
 *   helper's search appearing, the handoff, each search completing), and the
 *   result is always a prefix of what arrived;
 * - a run already slower than the pacing is shown the moment each event
 *   arrives, with no delay at all, and the 2026-09-20 ceiling change adds
 *   NOTHING material to that: this is the arm that protects UI fix 11.8;
 * - nothing is ever held more than `maxLagFor(helperCount, timing)` behind
 *   its own arrival, and that ceiling SCALES with how many helpers the plan
 *   named, so a burst naming three helpers gets a visibly wider spread than
 *   one naming two, each helper landing far enough apart to read its name;
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
import { helperCount, maxLagFor, PACING, REDUCED_PACING, usePacedEvents } from "./usePacedEvents";
import type { PacingTiming } from "./usePacedEvents";

let seq = 0;
function ev(type: string, payload: Record<string, unknown>): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "t", seq, ts: "2026-09-14T00:00:00Z", payload } as unknown as AgentEvent;
}

function run(helpers = 2): AgentEvent[] {
  const ids = Array.from({ length: helpers }, (_, i) => `c${i + 1}`);
  // `tool_calls` names one call per helper, mirroring what the server
  // actually sends: `helperCount` reads its length to size the lag ceiling,
  // so a test plan with an empty array would silently fall back to the
  // one-helper ceiling regardless of `helpers`.
  const toolCalls = ids.map((id) => ({ tool: "ncbi_efetch", call_id: id, layer: "layer_2_api" }));
  return [
    ev("guard", { passed: true, category: "ok", reason: null }),
    ev("think", { narrative: "n", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
    ev("plan", { narrative: "p", tool_calls: toolCalls }),
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
    const ceiling = maxLagFor(helperCount(events), PACING);
    const { result } = renderHook(() => usePacedEvents(events, { runKey: "r1", stopped: false }));

    // Populate-check: nine events arrived at once, naming two helpers.
    expect(events).toHaveLength(9);
    expect(helperCount(events)).toBe(2);
    // The time each count first appears, in ms since arrival.
    const firstSeen = new Map<number, number>([[result.current.length, 0]]);
    for (let t = 10; t <= ceiling + 100; t += 10) {
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
    expect(at(9)).toBeLessThanOrEqual(ceiling);
    expect(result.current).toBe(events);
  });

  it("spreads a THREE-helper burst wider than a two-helper burst, so each name lands distinguishably apart", () => {
    // This is the arm the 2026-09-20 follow-up exists for: the product owner
    // could not read a name before it disappeared, and the root cause was
    // that every burst, regardless of helper count, shared one fixed 3500ms
    // window. Naming a third helper must now visibly widen that window, and
    // consecutive helper stages must land at least a full `helperGapMs`
    // apart, not a few hundred milliseconds like the old 350ms gap did.
    const two = run(2);
    const three = run(3);
    expect(helperCount(three)).toBe(3);
    const ceilingTwo = maxLagFor(helperCount(two), PACING);
    const ceilingThree = maxLagFor(helperCount(three), PACING);
    expect(ceilingThree).toBeGreaterThan(ceilingTwo);

    const { result } = renderHook(() => usePacedEvents(three, { runKey: "r1", stopped: false }));
    // 11 events: guard, think, plan, 3 tool_start, 3 tool_result, token, done.
    expect(three).toHaveLength(11);
    const firstSeen = new Map<number, number>([[result.current.length, 0]]);
    for (let t = 10; t <= ceilingThree + 100; t += 10) {
      act(() => vi.advanceTimersByTime(10));
      if (!firstSeen.has(result.current.length)) firstSeen.set(result.current.length, t);
    }
    const at = (n: number) => firstSeen.get(n)!;
    const planAt = PACING.guardMs + PACING.thinkMs + PACING.planMs;
    // The three tool_start reveals (indices 4, 5, 6), each a full
    // helperGapMs apart, and each gap is at least 900ms, comfortably enough
    // to read a name (versus 11.28's 350ms).
    expect(at(4)).toBe(planAt);
    expect(at(5)).toBe(planAt + PACING.helperGapMs);
    expect(at(6)).toBe(planAt + 2 * PACING.helperGapMs);
    expect(at(5) - at(4)).toBeGreaterThanOrEqual(900);
    expect(at(6) - at(5)).toBeGreaterThanOrEqual(900);
    // The whole run still finishes inside its (wider) ceiling, uncapped.
    expect(at(11)).toBeLessThanOrEqual(ceilingThree);
    expect(result.current).toBe(three);
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

  it("does not delay the answer on a genuinely slow real run, the shape UI fix 11.8 optimized", () => {
    // The actual production shape from the module doc: guard, think, plan and
    // every tool_start arrive in one fast opening burst (the agent's own
    // decisions are quick), then a REAL multi-second gap while the tools
    // genuinely run, then the results, the answer token and done arrive
    // together. This is the arm most likely to be missing: raising
    // helperGapMs and the lag ceiling to fix the burst case must not cost
    // this case anything, since this is exactly the run UI fix 11.8 sped up
    // from ~6s to ~17s median.
    const all = run(3);
    const openingBurstEnd = 6; // guard, think, plan, tool_start x3 (indices 0..5)
    const opening = all.slice(0, openingBurstEnd);
    const { result, rerender } = renderHook(
      ({ events }) => usePacedEvents(events, { runKey: "r1", stopped: false }),
      { initialProps: { events: opening } },
    );
    // Let the opening burst's own dwell chain fully resolve, exactly as the
    // first burst test does, so it is showing everything it has.
    advance(maxLagFor(3, PACING) + 100);
    expect(result.current).toBe(opening);

    // Real tool execution: a genuine 15-second gap while nothing new arrives.
    advance(15000);
    expect(result.current).toBe(opening);

    // The results, the token and done all land together once the tools
    // finish. The first result releases the instant it arrives: because the
    // opening burst's dwell chain finished ~15 seconds ago in real time,
    // `earliest` for it is already far in the past relative to `now`, so the
    // arrival clamp does not hold it at all.
    rerender({ events: all });
    expect(result.current).toHaveLength(openingBurstEnd + 1);

    // The two remaining results still stagger by `helperGapMs` each, same as
    // the burst case: THAT is intended, it is the "helpers hand back one at
    // a time" narrative the product owner asked to watch. What matters is
    // that this residual wait is small and FIXED by helper count, not
    // inflated by the 15-second gap that already elapsed or by the run's
    // (much larger) lag ceiling.
    const residual = 2 * PACING.helperGapMs + 50;
    expect(residual).toBeLessThan(3000);
    advance(residual);
    expect(result.current).toBe(all);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("never holds an event more than its helper-scaled ceiling behind its arrival", () => {
    // The production PACING constants are deliberately sized so the ceiling
    // always outgrows the dwell chain (a design choice: never truncate a
    // reasonable helper count, see the PACING doc comment). To prove the cap
    // is a genuine upper bound rather than a number that happens to always
    // be big enough, this arm uses a custom timing, via the hook's own test
    // seam, whose per-helper dwell cost deliberately outgrows its per-helper
    // ceiling budget.
    const timing: PacingTiming = {
      guardMs: 100,
      thinkMs: 100,
      planMs: 100,
      helperGapMs: 500,
      handoffMs: 500,
      baseMaxLagMs: 300,
      perHelperLagMs: 50,
    };
    const events = run(6);
    const ceiling = maxLagFor(helperCount(events), timing);
    const { result } = renderHook(() => usePacedEvents(events, { runKey: "r1", stopped: false, timing }));
    // Populate-check: the full dwell chain for six helpers exceeds the ceiling.
    const uncapped = timing.guardMs + timing.thinkMs + timing.planMs + 5 * timing.helperGapMs + timing.handoffMs + 5 * timing.helperGapMs;
    expect(uncapped).toBeGreaterThan(ceiling);
    advance(ceiling - 10);
    expect(result.current.length).toBeLessThan(events.length);
    advance(20);
    expect(result.current).toBe(events);
  });

  it("scales the ceiling with helper count: three helpers earn more than the one-helper base", () => {
    expect(maxLagFor(0, PACING)).toBe(PACING.baseMaxLagMs);
    expect(maxLagFor(1, PACING)).toBe(PACING.baseMaxLagMs);
    expect(maxLagFor(3, PACING)).toBe(PACING.baseMaxLagMs + 2 * PACING.perHelperLagMs);
    expect(maxLagFor(3, PACING)).toBeGreaterThan(maxLagFor(1, PACING));
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
    expect(reducedTotal).toBeLessThan(maxLagFor(2, PACING) / 5);
    expect(result.current).toBe(events);
  });

  it("starts from zero for a new run and for a reset buffer", () => {
    const first = run(1);
    const { result, rerender } = renderHook(
      ({ events, runKey }) => usePacedEvents(events, { runKey, stopped: false }),
      { initialProps: { events: first, runKey: "r1" } },
    );
    advance(maxLagFor(helperCount(first), PACING) + 50);
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
