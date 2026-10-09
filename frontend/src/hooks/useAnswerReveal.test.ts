/**
 * What the screen shows of the answer, and what Stop leaves on it.
 *
 * BUILD PHASE 8.7, T-8.7-03 (2026-09-27): the screen follows the stream.
 * This file used to pin a timed reveal: the first sentence held until the
 * writing banner had shown 1.5 seconds, then one sentence per 110 ms. The
 * phase's acceptance ("nothing that has arrived is held back") removes that
 * reveal on purpose, so its three timing arms are replaced by the arm below
 * that pins the opposite: every arrived sentence shows in the render it
 * arrives in. Every Stop arm is kept, card 58's included, and the owner's
 * decision of 2026-09-27 on records already on screen is added.
 *
 * WHAT THIS PINS:
 * - every arrived sentence and record shows at once, and the view is the
 *   input object itself (nothing held, dropped or reworded);
 * - Stop before any of the answer was on screen withholds the whole answer
 *   (card 58, F-58-J02, F-58-A01);
 * - Stop after records were on screen keeps exactly those records, and
 *   nothing that arrives afterwards shows: no summary, no count-line change,
 *   no note, no trust line (the owner, 2026-09-27);
 * - Stop mid-summary keeps what was shown and shows nothing new;
 * - a failed stream, a refusal and a new run pass straight through.
 *
 * WHAT IT DOES NOT PIN: the rise animation (CSS, see the AnswerScreen tests).
 */

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Claim } from "../components/screens/AnswerScreen";
import { EMPTY_RUN_VIEW } from "./useRunView";
import type { RunView } from "./useRunView";
import { useAnswerReveal, whatStopLeavesOnScreen } from "./useAnswerReveal";

const sentence = (i: number): Claim => ({ text: `Sentence ${i}.`, layer: 2, citations: [i] });
const record = (i: number): Claim => ({
  text: `Disease name: Disease ${i} [${i}].`,
  layer: 1,
  citations: [i],
  kind: "table_row",
  cells: [`Disease ${i}`],
  placement: "listing",
});

function viewWith(claims: Claim[], overrides: Partial<RunView> = {}): RunView {
  return {
    ...EMPTY_RUN_VIEW,
    activeStep: "Write",
    reachedSteps: ["Guard", "Think", "Plan", "Act", "Write"],
    claims,
    sources: claims.map((_, i) => ({
      n: i + 1,
      name: `Record ${i + 1}`,
      tool: "cypher_query",
      layer: 1 as const,
      url: "https://www.ncbi.nlm.nih.gov/gene/672",
      rows: [],
    })) as unknown as RunView["sources"],
    ...overrides,
  };
}

const records = [record(1), record(2), record(3)];
/** What arrives after the records: the summary, its verdict and `done`. */
const landedAnswer = viewWith([...records, sentence(4), sentence(5)], {
  landed: true,
  activeStep: null,
  meta: "3 tools · 5 sources",
  outcome: "Answered",
  trust: [{ kind: "good", label: "Grounded · every claim cited" }],
  systemNotes: ["Note: one further record was not shown."],
});

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("useAnswerReveal: the screen follows the stream", () => {
  it("shows every arrived sentence in the render it arrives in, with no timer", () => {
    const { result, rerender } = renderHook(
      ({ view }) => useAnswerReveal(view, { runKey: "run-1", stopped: false }),
      { initialProps: { view: viewWith([]) } },
    );
    const five = viewWith([1, 2, 3, 4, 5].map(sentence));
    // Populate-check: five sentences arrived.
    expect(five.claims).toHaveLength(5);
    rerender({ view: five });
    // No time has passed and all five are shown: nothing arrived is held.
    expect(result.current.claims).toHaveLength(5);
    expect(result.current).toBe(five);
    expect(vi.getTimerCount(), "a timer is still holding something back").toBe(0);
  });

  it("shows a landed answer as it arrived, landed, the very object", () => {
    const { result } = renderHook(() => useAnswerReveal(landedAnswer, { runKey: "run-1", stopped: false }));
    expect(result.current).toBe(landedAnswer);
    expect(result.current.landed).toBe(true);
    expect(result.current.meta).toBe("3 tools · 5 sources");
  });

  it("shows records the moment they arrive, before any summary", () => {
    const listingOnly = viewWith(records);
    const { result } = renderHook(() => useAnswerReveal(listingOnly, { runKey: "run-1", stopped: false }));
    expect(result.current.claims.map((claim) => claim.text)).toEqual(records.map((claim) => claim.text));
    expect(result.current.landed).toBe(false);
  });
});

describe("useAnswerReveal: what Stop leaves on screen", () => {
  it("withholds the whole answer when Stop latches before any of it was on screen (card 58, F-58-J02, F-58-A01)", () => {
    // What Stop's flush hands the hook: the per-question cap's partial
    // result, landed, with no sentence, carrying its note, a verdict, and a
    // clarification the person had already read.
    const flushed = viewWith([], {
      landed: true,
      activeStep: null,
      meta: "3 tools · 0 sources",
      outcome: "Partial result",
      trust: [{ kind: "plain", label: "Not verified" }],
      capMessage: "This answer stopped early because it reached its processing budget.",
      systemNotes: ["Note: this result was truncated."],
      clarification: "Which gene do you mean?",
      refusal: "Which gene do you mean?",
    });
    const { result } = renderHook(() => useAnswerReveal(flushed, { runKey: "run-1", stopped: true }));

    expect(result.current.landed, "a stopped run landed on the result page").toBe(false);
    expect(result.current.claims).toEqual([]);
    expect(result.current.trust, "a trust line survived Stop").toEqual([]);
    expect(result.current.capMessage, "the stopped answer's cap note survived Stop").toBeNull();
    expect(result.current.systemNotes).toEqual([]);
    expect(result.current.meta).toBe("");
    expect(result.current.outcome).toBeNull();
    // Kept: shown the moment it arrived, before any Stop, and it says what to type next.
    expect(result.current.clarification).toBe("Which gene do you mean?");
    expect(result.current.refusal).toBe("Which gene do you mean?");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("withholds an answer that arrives in the same moment as a Stop pressed during the search", () => {
    // Stop pressed while the helpers were still searching; the whole answer
    // then reaches the hook in the same render as the Stop.
    const { result, rerender } = renderHook(
      ({ view, stopped }) => useAnswerReveal(view, { runKey: "run-1", stopped }),
      { initialProps: { view: viewWith([], { activeStep: "Act" }), stopped: false } },
    );
    expect(result.current.claims).toHaveLength(0);
    rerender({ view: landedAnswer, stopped: true });
    expect(result.current.claims, "part of an answer the reader had not seen showed after Stop").toEqual([]);
    expect(result.current.landed).toBe(false);
  });

  it("keeps the records already on screen when Stop latches, and shows nothing that arrives after it (the owner, 2026-09-27)", () => {
    const listingOnly = viewWith(records);
    const { result, rerender } = renderHook(
      ({ view, stopped }) => useAnswerReveal(view, { runKey: "run-1", stopped }),
      { initialProps: { view: listingOnly, stopped: false } },
    );
    // Populate-check: the records were on screen before Stop.
    expect(result.current.claims).toHaveLength(3);

    rerender({ view: listingOnly, stopped: true });
    expect(result.current.claims.map((claim) => claim.text), "the records were taken back by Stop").toEqual(
      records.map((claim) => claim.text),
    );
    expect(result.current.landed).toBe(false);

    // The server's summary, verdict, note and `done` arrive after Stop.
    // Populate-check: they really arrive, and would show without the Stop.
    expect(landedAnswer.claims).toHaveLength(5);
    rerender({ view: landedAnswer, stopped: true });
    expect(
      result.current.claims.map((claim) => claim.text),
      "something arrived after Stop and was shown",
    ).toEqual(records.map((claim) => claim.text));
    expect(result.current.trust, "a trust line showed after Stop").toEqual([]);
    expect(result.current.systemNotes, "a note showed after Stop").toEqual([]);
    expect(result.current.meta).toBe("");
    expect(result.current.outcome).toBeNull();
    expect(result.current.landed, "a stopped run landed on the result page").toBe(false);
    // The citation markers still resolve through the same sources.
    expect(result.current.sources).toBe(listingOnly.sources);
  });

  it("keeps a summary already partly on screen when Stop latches mid-write, and shows nothing new", () => {
    const partly = viewWith([...records, sentence(4)]);
    const { result, rerender } = renderHook(
      ({ view, stopped }) => useAnswerReveal(view, { runKey: "run-1", stopped }),
      { initialProps: { view: partly, stopped: false } },
    );
    rerender({ view: partly, stopped: true });
    rerender({ view: landedAnswer, stopped: true });
    expect(result.current.claims).toBe(partly.claims);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps the rule in one function: nothing shown means nothing kept, something shown means exactly that", () => {
    expect(whatStopLeavesOnScreen(landedAnswer, null).claims).toEqual([]);
    expect(whatStopLeavesOnScreen(landedAnswer, viewWith([])).claims).toEqual([]);
    const shown = viewWith(records);
    const kept = whatStopLeavesOnScreen(landedAnswer, shown);
    expect(kept.claims).toBe(shown.claims);
    expect(kept.trust).toEqual([]);
    expect(kept.landed).toBe(false);
  });
});

describe("useAnswerReveal: runs that pass straight through", () => {
  it("shows everything at once when the stream failed", () => {
    const failed = viewWith([1, 2, 3, 4].map(sentence));
    const { result } = renderHook(() => useAnswerReveal(failed, { runKey: "run-1", stopped: false, flush: true }));
    expect(result.current).toBe(failed);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("passes a run with no sentences straight through", () => {
    const refusal = { ...EMPTY_RUN_VIEW, landed: true, refusal: "No answer found." };
    const { result } = renderHook(() => useAnswerReveal(refusal, { runKey: "run-1", stopped: false }));
    expect(result.current).toBe(refusal);
  });

  it("does not carry what one run showed into a Stop on the next", () => {
    const { result, rerender } = renderHook(
      ({ view, runKey, stopped }) => useAnswerReveal(view, { runKey, stopped }),
      { initialProps: { view: viewWith(records), runKey: "run-1", stopped: false } },
    );
    expect(result.current.claims).toHaveLength(3);
    // Run two is stopped before anything of it was shown. Run one's records
    // must not be what Stop keeps.
    rerender({ view: landedAnswer, runKey: "run-2", stopped: true });
    expect(result.current.claims).toEqual([]);
  });
});
