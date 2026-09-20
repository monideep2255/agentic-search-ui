/**
 * Pace the PRESENTATION of a run's events, UI fix 11.28, 2026-09-14.
 *
 * The product owner: "the transition of the agent searching to streaming
 * answer now is too quick. It is also the fun part of watching the agent
 * starting, giving to other agents to search and then coming up with the
 * answer. Stagger the process to make it smooth."
 *
 * WHY. Events reach the browser in bursts: `act_node` emits its tool starts
 * together and often its results together, and a scripted or replayed stream
 * arrives as one chunk. Every screen state (the lead scientist starting, the
 * handoff line, each helper's search, the writing banner) derives from the
 * events received so far, so a burst races through all of them in one frame.
 *
 * WHAT IT DOES, and nothing else. It sits between `useAgentRun` and
 * `useRunView` and returns a PREFIX of the events that arrived, growing it one
 * event at a time so each stage stays on screen for a minimum dwell:
 *
 *   - Never shows anything that has not arrived: the result is always
 *     `events.slice(0, n)`, never a reordering, never an invented event.
 *   - An event is released at `max(arrival, previous release + dwell)`, so
 *     when the real run is slower than the pacing, it is released the moment
 *     it arrives and no delay is added at all.
 *   - No event is ever held more than `maxLagMs` behind its own arrival, so
 *     the answer lands at most that much later than it would unpaced.
 *   - Stop, a stream failure, any `error` event, a failed guard, an
 *     answer-level refusal and a clarification FLUSH: everything that
 *     arrived shows at once and the rest of the run is unpaced.
 *   - Under `prefers-reduced-motion` the order is kept and the dwells drop to
 *     `REDUCED_PACING`'s minimum.
 *   - A new `runKey`, or an event array that no longer starts with the events
 *     already seen (a reset buffer), starts again from zero.
 *
 * Once every event is released it returns the input array itself, so the
 * memoised view downstream is exactly what arrived.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import type { AgentEvent } from "../lib/events";

export interface PacingTiming {
  /** Dwell after the guard passes: the lead scientist starting. */
  guardMs: number;
  /** Dwell after `think`. */
  thinkMs: number;
  /** Dwell after `plan`. */
  planMs: number;
  /** Between two helpers' searches appearing, or two completing. */
  helperGapMs: number;
  /** After the last search in a group appears: the handoff line naming the helpers. */
  handoffMs: number;
  /** The most any event is held behind its own arrival. */
  maxLagMs: number;
}

/**
 * The values, chosen by watching the paced run against the e2e stream at 1280
 * and 390 (screenshots in the bold-and-stagger report). For a two-helper run
 * whose events all arrive at once they sum to 3500ms, exactly `maxLagMs`, so
 * every stage gets its full dwell and the answer lands at most 3.5s later.
 */
export const PACING: PacingTiming = {
  guardMs: 600,
  thinkMs: 700,
  planMs: 700,
  helperGapMs: 350,
  handoffMs: 800,
  maxLagMs: 3500,
};

/** Reduced motion: the same order, each stage held only long enough to paint. */
export const REDUCED_PACING: PacingTiming = {
  guardMs: 100,
  thinkMs: 100,
  planMs: 100,
  helperGapMs: 50,
  handoffMs: 100,
  maxLagMs: 1000,
};

/** How long `event` stays the newest thing on screen before `next` may show. */
export function dwellAfter(event: AgentEvent, next: AgentEvent, timing: PacingTiming): number {
  switch (event.type) {
    case "guard":
      return timing.guardMs;
    case "think":
      return timing.thinkMs;
    case "plan":
      return timing.planMs;
    case "tool_start":
      return next.type === "tool_start" ? timing.helperGapMs : timing.handoffMs;
    case "tool_result":
      // The last result opens the writing banner, whose own minimum lives in
      // `useAnswerReveal`, so the gap is only between two completions.
      return next.type === "tool_result" ? timing.helperGapMs : 0;
    default:
      // Tokens, citations, trust signals and `done` change nothing a reader
      // watches while the run is live, so they never hold the queue.
      return 0;
  }
}

/** An event that must show at once, and ends pacing for the run. */
export function isFlushEvent(event: AgentEvent): boolean {
  switch (event.type) {
    case "error":
      return true;
    case "guard":
      return event.payload.passed === false;
    case "trust_signal":
      return event.payload.scope === "answer" && event.payload.outcome === "refuse";
    case "think":
      return (
        typeof event.payload.clarifying_question === "string" &&
        event.payload.clarifying_question.trim().length > 0
      );
    default:
      return false;
  }
}

export interface PacedEventsOptions {
  /** The run being paced. A new key starts from zero. */
  runKey: string | null;
  /** Stop latched: show everything that arrived, at once. */
  stopped: boolean;
  /** The stream failed: show everything that arrived, at once. */
  flush?: boolean;
  /** `prefers-reduced-motion: reduce`. */
  reducedMotion?: boolean;
  /** Test seam; defaults to `PACING` or `REDUCED_PACING`. */
  timing?: PacingTiming;
}

interface Schedule {
  /** Bumped on every reset, so a released count from an earlier buffer is never reused. */
  gen: number;
  key: string | null;
  seen: AgentEvent[];
  arrivals: number[];
  releases: number[];
  flushed: boolean;
}

export function usePacedEvents(events: AgentEvent[], options: PacedEventsOptions): AgentEvent[] {
  const { runKey, stopped, flush = false, reducedMotion = false } = options;
  const timing = options.timing ?? (reducedMotion ? REDUCED_PACING : PACING);
  const [released, setReleased] = useState<{ gen: number; count: number }>({ gen: 0, count: 0 });
  const [tick, setTick] = useState(0);
  const scheduleRef = useRef<Schedule>({
    gen: 0,
    key: runKey,
    seen: [],
    arrivals: [],
    releases: [],
    flushed: false,
  });

  // Record arrivals during render, the pattern `useAnswerReveal` uses for its
  // write start: the time an event was first seen is a fact about this render.
  const schedule = scheduleRef.current;
  const now = Date.now();
  const sameRun =
    schedule.key === runKey &&
    events.length >= schedule.seen.length &&
    schedule.seen.every((event, i) => events[i] === event);
  if (!sameRun) {
    scheduleRef.current = {
      gen: schedule.gen + 1,
      key: runKey,
      seen: [],
      arrivals: [],
      releases: [],
      flushed: false,
    };
  }
  const current = scheduleRef.current;
  for (let i = current.seen.length; i < events.length; i += 1) {
    current.seen.push(events[i]!);
    current.arrivals.push(now);
    if (isFlushEvent(events[i]!)) current.flushed = true;
  }
  const unpaced = runKey === null || stopped || flush || current.flushed;

  const count = released.gen === current.gen ? Math.min(released.count, events.length) : 0;

  useEffect(() => {
    if (unpaced || count >= events.length) return;
    const at = Date.now();
    let next = count;
    let dueAt: number | null = null;
    while (next < events.length) {
      const arrival = current.arrivals[next]!;
      const earliest =
        next === 0 ? arrival : current.releases[next - 1]! + dwellAfter(events[next - 1]!, events[next]!, timing);
      const target = Math.min(Math.max(arrival, earliest), arrival + timing.maxLagMs);
      if (target > at) {
        dueAt = target;
        break;
      }
      current.releases[next] = target;
      next += 1;
    }
    if (next !== count) {
      setReleased({ gen: current.gen, count: next });
      return;
    }
    if (dueAt === null) return;
    const timer = setTimeout(() => setTick((t) => t + 1), dueAt - at);
    return () => clearTimeout(timer);
    // `tick` re-runs the schedule when a dwell has elapsed.
  }, [unpaced, count, events, runKey, timing, current, tick]);

  return useMemo(
    () => (unpaced || count >= events.length ? events : events.slice(0, count)),
    [unpaced, count, events],
  );
}

export default usePacedEvents;
