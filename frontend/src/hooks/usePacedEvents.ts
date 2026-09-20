/**
 * Pace the PRESENTATION of a run's events, UI fix 11.28 (2026-09-14) and its
 * follow-up (2026-09-20).
 *
 * The product owner, 11.28: "the transition of the agent searching to
 * streaming answer now is too quick... Stagger the process to make it
 * smooth." Then, testing 11.28 live: "still feel very fast since I cannot
 * read all the scientist name and they disappear." What they want to watch:
 * "the main scientist understand the task, calls 3 scientists to search 3
 * resources, 3 scientists hand back to the main scientist and then the main
 * scientist is writing."
 *
 * WHY 11.28 WAS NOT ENOUGH. Two things, the second being the real one. First,
 * `helperGapMs` was too short to read a name. Second, and load-bearing:
 * `maxLagMs` was a single FIXED ceiling on how far any event may be held
 * behind its own arrival, so a burst arrival (`act_node` emits its tool
 * starts together and often its results together, or a scripted stream
 * arrives as one chunk) compressed the ENTIRE narrative, guard through the
 * last helper, into one fixed window no matter how many helpers ran. Three
 * named scientists got the same window as one.
 *
 * THE FIX: the lag ceiling SCALES with how many helpers the plan actually
 * named, read from the `plan` event's own `tool_calls` the moment it
 * arrives, per `maxLagFor`. A plan naming three helpers earns three helpers'
 * worth of reveal time; a plan naming one gets `baseMaxLagMs` alone. This
 * only ever ADDS time to a burst arrival. It never touches a genuinely slow
 * arrival, because the arrival-clamp rule below is unchanged: an event
 * already spaced out in real time is shown the instant it arrives regardless
 * of what the ceiling allows, so a 15-second real run pays nothing extra.
 * That is what protects UI fix 11.8's latency work: pacing only spends time
 * a fast run was not going to use anyway.
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
 *   - No event is ever held more than `maxLagFor(helperCount, timing)`
 *     behind its own arrival, so the answer lands at most that much later
 *     than it would unpaced, and that bound grows only with the number of
 *     helpers the plan actually named.
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
  /** The lag ceiling when the plan names one helper, or before Plan has arrived at all. */
  baseMaxLagMs: number;
  /** Extra lag ceiling earned per helper beyond the first, so naming three helpers earns three helpers' worth of reveal time rather than one fixed window. */
  perHelperLagMs: number;
}

/**
 * The values, chosen by watching the paced run against the e2e stream at 1280
 * and 390, then re-tuned 2026-09-20 after the product owner could not read a
 * name before it disappeared. `helperGapMs` rose from 350ms, roughly a third
 * of a reading beat, to 900ms. `maxLagMs` split into a base plus a per-helper
 * share: for `n` helpers the ceiling is `baseMaxLagMs + (n - 1) *
 * perHelperLagMs` (see `maxLagFor`), sized so the full minimum-dwell chain
 * for one through four helpers always fits inside it rather than being
 * truncated:
 *
 *   n=1: 2900ms chain, ceiling 3200ms
 *   n=2: 4700ms chain, ceiling 5100ms
 *   n=3: 6500ms chain, ceiling 7000ms
 *   n=4: 8300ms chain, ceiling 8900ms
 *
 * This only ever lengthens a burst arrival's reveal window. A genuinely slow
 * arrival pays none of it, because the ceiling is an upper bound on lag, not
 * an added delay: see the module doc's "arrival-clamp" note.
 */
export const PACING: PacingTiming = {
  guardMs: 600,
  thinkMs: 700,
  planMs: 700,
  helperGapMs: 900,
  handoffMs: 900,
  baseMaxLagMs: 3200,
  perHelperLagMs: 1900,
};

/** Reduced motion: the same order, each stage held only long enough to paint. */
export const REDUCED_PACING: PacingTiming = {
  guardMs: 100,
  thinkMs: 100,
  planMs: 100,
  helperGapMs: 50,
  handoffMs: 100,
  baseMaxLagMs: 1000,
  perHelperLagMs: 100,
};

/** How many helpers the plan named, from its `tool_calls`, or 0 before Plan has arrived. */
export function helperCount(events: AgentEvent[]): number {
  for (const event of events) {
    if (event.type === "plan") return event.payload.tool_calls.length;
  }
  return 0;
}

/**
 * The lag ceiling for a run naming this many helpers. Never less than
 * `baseMaxLagMs`; each helper beyond the first adds `perHelperLagMs`, so a
 * plan naming more helpers earns proportionately more time to show each one
 * rather than sharing one fixed window.
 */
export function maxLagFor(count: number, timing: PacingTiming): number {
  return timing.baseMaxLagMs + Math.max(0, count - 1) * timing.perHelperLagMs;
}

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
    // Read once per effect run, not per event: the plan is fixed for a run,
    // so the ceiling it earns is fixed for the whole loop below.
    const maxLag = maxLagFor(helperCount(events), timing);
    let next = count;
    let dueAt: number | null = null;
    while (next < events.length) {
      const arrival = current.arrivals[next]!;
      const earliest =
        next === 0 ? arrival : current.releases[next - 1]! + dwellAfter(events[next - 1]!, events[next]!, timing);
      const target = Math.min(Math.max(arrival, earliest), arrival + maxLag);
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
