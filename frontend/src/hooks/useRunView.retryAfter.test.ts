/**
 * R-10's fix round, F-72-A01: a rate-limited run tells the person how long
 * to wait, in the web app's own words.
 *
 * The guardrail's error event carries the provider's wait in
 * `retry_after_s` (`core/graph.py`, `_rate_limited_step_error`). The web
 * app renders a fixed sentence per `error_class` and never the backend's
 * free-form `message` (F-4.8-A-15, F-4.9-A-01), so before this fix a
 * rate-limited person read "Try asking again in a moment", retried at once
 * and met the same limit. The number is read now; the sentence stays this
 * app's own.
 *
 * Fixtures are the real event shapes the adversary drove through the real
 * guardrail node: the backend message is quoted from
 * `_GUARDRAIL_RATE_LIMITED_WAIT_MESSAGE` and `_GUARDRAIL_RATE_LIMITED_MESSAGE`.
 *
 * MUTATION PROOF: dropping the `retry_after_s` branch from `useRunView`
 * turns the first two cases red ("in a moment" again).
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { useRunView } from "./useRunView";

let seq = 0;

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-rate-limited",
    seq,
    ts: `2026-09-29T12:00:0${seq % 10}Z`,
    payload,
  } as AgentEvent;
}

function rateLimited(retryAfterS: number, message: string): AgentEvent[] {
  return [
    envelope("error", {
      fatal: true,
      scope: "step",
      source: "guardrail",
      error_class: "transient",
      message,
      retry_after_s: retryAfterS,
    }),
  ];
}

const BUSY_20 =
  "The service that checks each question is busy right now. " +
  "Try the query again in about 20 seconds, not straight away.";
const BUSY_1 =
  "The service that checks each question is busy right now. " +
  "Try the query again in about 1 second, not straight away.";
const BUSY_NO_WAIT =
  "The service that checks each question is busy right now. " +
  "Wait a little before trying the query again.";

describe("useRunView: a rate-limited run says how long to wait", () => {
  it("says about 20 seconds when the provider named 20", () => {
    const { result } = renderHook(() => useRunView(rateLimited(20, BUSY_20)));
    expect(result.current.failure).toBe(
      "This run could not be completed. Try asking again in about 20 seconds.",
    );
  });

  it("says second, not seconds, for one", () => {
    const { result } = renderHook(() => useRunView(rateLimited(1, BUSY_1)));
    expect(result.current.failure).toBe(
      "This run could not be completed. Try asking again in about 1 second.",
    );
  });

  it("keeps the class's own words when no wait was named", () => {
    const { result } = renderHook(() => useRunView(rateLimited(0, BUSY_NO_WAIT)));
    expect(result.current.failure).toBe(
      "This run could not be completed. Try asking again in a moment.",
    );
  });

  it("never renders the backend's own message", () => {
    for (const [wait, message] of [
      [20, BUSY_20],
      [1, BUSY_1],
      [0, BUSY_NO_WAIT],
    ] as const) {
      const { result } = renderHook(() => useRunView(rateLimited(wait, message)));
      expect(result.current.failure).not.toContain("service that checks");
      expect(result.current.failure).not.toContain("straight away");
    }
  });
});
