/**
 * R-10 line 4, card 84 (F-72-A01, J04, V05): a rate-limited run tells the
 * person how long to wait, in the web app's own words, and says to wait a
 * little when no wait is known.
 *
 * The guardrail's error event carries the provider's wait in
 * `retry_after_s` (`core/graph.py`, `_rate_limited_step_error`). The web
 * app renders a fixed sentence per `error_class` and never the backend's
 * free-form `message` (F-4.8-A-15, F-4.9-A-01), so before this change a
 * rate-limited person read "Try asking again in a moment", retried at once
 * and met the same limit. The number is read now; the sentence stays this
 * app's own.
 *
 * The backend messages below are quoted from `core/graph.py`'s three
 * `_GUARDRAIL_RATE_LIMITED_*` messages, only to prove they never render.
 *
 * MUTATION PROOF: dropping the `retry_after_s` branch from `useRunView`
 * turns the first two cases red; "in a moment" as the transient line again
 * turns the third red.
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

function failed(
  retryAfterS: number,
  message: string,
  errorClass: "transient" | "cancelled" | "recoverable" = "transient",
): AgentEvent[] {
  return [
    envelope("error", {
      fatal: true,
      scope: "step",
      source: "guardrail",
      error_class: errorClass,
      message,
      retry_after_s: retryAfterS,
    }),
  ];
}

const BUSY_20 =
  "The service that checks each question is busy right now. " +
  "Try the query again in about 20 seconds, not straight away.";
const BUSY_1 =
  "The service that checks each question is busy right now. Try the query again in about 1 second.";
const BUSY_NO_WAIT =
  "The service that checks each question is busy right now. " +
  "Wait a little before trying the query again.";
const BUSY_PASSED =
  "The service that checks each question was busy a moment ago. Try the query again.";

describe("useRunView: a rate-limited run says how long to wait", () => {
  it("says about 20 seconds when the provider named 20", () => {
    const { result } = renderHook(() => useRunView(failed(20, BUSY_20)));
    expect(result.current.failure).toBe(
      "This run could not be completed. Try asking again in about 20 seconds.",
    );
  });

  it("says second, not seconds, for one", () => {
    const { result } = renderHook(() => useRunView(failed(1, BUSY_1)));
    expect(result.current.failure).toBe(
      "This run could not be completed. Try asking again in about 1 second.",
    );
  });

  it("says to wait a little when no wait is known, never 'in a moment'", () => {
    for (const message of [BUSY_NO_WAIT, BUSY_PASSED]) {
      const { result } = renderHook(() => useRunView(failed(0, message)));
      expect(result.current.failure).toBe(
        "This run could not be completed. Wait a little, then try asking again.",
      );
      expect(result.current.failure).not.toContain("in a moment");
    }
  });

  it("reads a wait only on a transient error", () => {
    const { result } = renderHook(() => useRunView(failed(20, "stopped", "cancelled")));
    expect(result.current.failure).toBe(
      "This run was stopped before it finished, so no answer was written.",
    );
  });

  it("never renders the backend's own message", () => {
    for (const [wait, message] of [
      [20, BUSY_20],
      [1, BUSY_1],
      [0, BUSY_NO_WAIT],
      [0, BUSY_PASSED],
    ] as const) {
      const { result } = renderHook(() => useRunView(failed(wait, message)));
      expect(result.current.failure).not.toContain("service that checks");
      expect(result.current.failure).not.toContain("straight away");
    }
  });
});
