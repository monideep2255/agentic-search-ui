/**
 * Cards 84 and 72, step 1 of the guardrail design (owner, 2026-10-08): when
 * the guardrail fails, the person reads plain words that say nothing was
 * searched and the problem was ours, and a rate limit that named a wait says
 * how long, in seconds up to two minutes and in minutes past that.
 *
 * Only a fatal error whose `source` is the guardrail AND whose class is
 * "transient" changes: the guardrail's own check not finishing, two timeouts
 * or two unreadable replies (fix round, A-GR-10; `core/graph.py` sends both
 * as "transient"). A guardrail failure the question caused ("recoverable": a
 * content-policy refusal, a 400) keeps "rephrase the question"; one asking
 * again cannot fix ("unexpected": a 401) keeps its own line. Every other
 * failure keeps its own line, "in a moment" included, and a stopped run keeps "This run was stopped". The backend's
 * free-form `message` is never rendered (F-4.8-A-15): the messages below are
 * quoted from `core/graph.py` only to prove they never reach the screen.
 *
 * Findings closed here: F-72-V05 and F-84-A02 (a long wait read as thousands
 * of seconds; no "in a moment" for a guardrail failure), F-84-A01 and A09 (a
 * wait that has passed, or none named, never tells the person to wait), and
 * the design's rule that only guardrail failures change (A09's other half).
 *
 * MUTATION PROOF: dropping the `source === "guardrail"` branch from
 * `useRunView` turns every guardrail case red; reading the branch for every
 * source turns "other failures keep their own words" red; dropping the
 * minutes arm turns the long-wait case red; reading the branch for every
 * class but "cancelled" (the first build) turns the content-policy, 400 and
 * 401 cases red. Whether two unreadable replies read these words rests on
 * the class `core/graph.py` sends, pinned by the backend's
 * `test_each_kind_of_guardrail_failure_carries_its_own_category`.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent, ErrorPayload } from "../lib/events";
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
    trace_id: "trace-guardrail-failure",
    seq,
    ts: `2026-10-08T12:00:0${seq % 10}Z`,
    payload,
  } as AgentEvent;
}

function failed(overrides: Partial<ErrorPayload>): AgentEvent[] {
  return [
    envelope("error", {
      fatal: true,
      scope: "step",
      source: "guardrail",
      error_class: "transient",
      message: "A step in this query hit a temporary error. Retrying the query may succeed.",
      retry_after_s: 0,
      ...overrides,
    }),
  ];
}

function failure(overrides: Partial<ErrorPayload>): string | null {
  return renderHook(() => useRunView(failed(overrides))).result.current.failure;
}

const PLAIN =
  "We could not finish checking your question, so nothing was searched. " +
  "This was a problem on our side, not with your question. Try asking again.";
const WITH_WAIT = (words: string): string =>
  "We could not finish checking your question, so nothing was searched. " +
  `This was a problem on our side, not with your question. Try asking again in about ${words}.`;

// `core/graph.py`'s `_STEP_ERROR_END_USER_MESSAGES` and
// `_GUARDRAIL_NO_USABLE_VERDICT_MESSAGE`, quoted to prove they never render.
const TRANSIENT_MESSAGE =
  "A step in this query hit a temporary error. Retrying the query may succeed.";
const NO_USABLE_VERDICT_MESSAGE =
  "A step in this query could not complete. Retrying the query may succeed.";
const RECOVERABLE_MESSAGE = "A step in this query could not complete as requested.";
const UNEXPECTED_MESSAGE = "A step in this query failed unexpectedly.";

// Develop's words for the classes a guardrail failure keeps (A-GR-10).
const REPHRASE = "This run could not be completed. Try asking again, or rephrase the question.";

describe("useRunView: a guardrail failure reads plain words", () => {
  it("a double timeout reads the plain words", () => {
    expect(failure({ error_class: "transient", message: TRANSIENT_MESSAGE })).toBe(PLAIN);
  });

  it("two unreadable replies read the same words, never 'rephrase the question'", () => {
    // The backend sends two unreadable replies as "transient" (A-GR-10).
    const text = failure({ error_class: "transient", message: NO_USABLE_VERDICT_MESSAGE });
    expect(text).toBe(PLAIN);
    expect(text).not.toContain("rephrase");
    expect(text).not.toContain("Retrying the query");
  });

  it("a named wait reads in seconds, 'second' for one", () => {
    expect(failure({ retry_after_s: 20 })).toBe(WITH_WAIT("20 seconds"));
    expect(failure({ retry_after_s: 1 })).toBe(WITH_WAIT("1 second"));
    expect(failure({ retry_after_s: 0.2 })).toBe(WITH_WAIT("1 second"));
    expect(failure({ retry_after_s: 120 })).toBe(WITH_WAIT("120 seconds"));
  });

  it("a wait past two minutes reads in whole minutes", () => {
    expect(failure({ retry_after_s: 121 })).toBe(WITH_WAIT("3 minutes"));
    expect(failure({ retry_after_s: 5400 })).toBe(WITH_WAIT("90 minutes"));
    expect(failure({ retry_after_s: 86400 })).not.toContain("seconds");
  });

  it("a wait that has passed, or none named, never says to wait", () => {
    for (const wait of [0, -3, Number.NaN, Number.POSITIVE_INFINITY]) {
      const text = failure({ retry_after_s: wait });
      expect(text).toBe(PLAIN);
      expect(text).not.toContain("in a moment");
      expect(text).not.toContain("Wait a little");
    }
  });

  it("never renders the backend's own message", () => {
    for (const message of [TRANSIENT_MESSAGE, RECOVERABLE_MESSAGE, "secret backend detail"]) {
      const text = failure({ message, retry_after_s: 20 });
      expect(text).not.toContain("Retrying the query");
      expect(text).not.toContain("secret backend detail");
    }
  });
});

describe("useRunView: a guardrail failure the question caused, or that asking again cannot fix, keeps develop's words", () => {
  // Fix round, A-GR-10: decided by category, from `source` and `error_class`.
  it("a content-policy refusal reads develop's words, not 'a problem on our side'", () => {
    const text = failure({ error_class: "recoverable", message: RECOVERABLE_MESSAGE });
    expect(text).toBe(REPHRASE);
    expect(text).not.toContain("problem on our side");
  });

  it("a 400 reads develop's words, a named wait ignored", () => {
    expect(failure({ error_class: "recoverable", retry_after_s: 20 })).toBe(REPHRASE);
  });

  it("a 401 reads develop's words, never 'not with your question'", () => {
    const text = failure({ error_class: "unexpected", message: UNEXPECTED_MESSAGE });
    expect(text).toBe(REPHRASE);
    expect(text).not.toContain("not with your question");
  });
});

describe("useRunView: every other failure keeps its own words", () => {
  it("a failure from another step is unchanged, a wait included", () => {
    expect(failure({ source: "plan", retry_after_s: 20 })).toBe(
      "This run could not be completed. Try asking again in a moment.",
    );
    expect(failure({ source: "write", error_class: "recoverable" })).toBe(
      "This run could not be completed. Try asking again, or rephrase the question.",
    );
    expect(failure({ source: "core.run.run", scope: "run", error_class: "unexpected" })).toBe(
      "This run could not be completed. Try asking again, or rephrase the question.",
    );
  });

  it("a stopped run keeps its own line, whatever its source", () => {
    for (const source of ["run_registry", "guardrail"]) {
      expect(failure({ source, error_class: "cancelled", retry_after_s: 20 })).toBe(
        "This run was stopped before it finished, so no answer was written.",
      );
    }
  });
});
