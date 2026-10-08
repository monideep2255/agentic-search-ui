/**
 * Card 58: Stop works until the answer appears, through the whole app.
 *
 * The product owner, 2026-09-27: "a user should be able to stop the answer at
 * any point of time until the answer pops out ... till the time the answer
 * has not started streaming, the user should be allowed to stop."
 *
 * WHY AN APP-LEVEL TEST. The rule lives in `deriveStopOffered`, which has its
 * own unit tests and a replay of a real develop stream. What only `App` can
 * get wrong is the WIRING: which view Stop reads. Before card 58 `App` fed
 * Stop the arrived stream, so the moment `done` arrived Stop went grey while
 * the screen, held back by the pacing and the reveal, still showed no
 * answer. These arms deliver a whole run in one chunk, which is how develop
 * delivers an answer, and then look at the screen.
 *
 * Verified by mutation: restoring the `realStopEnabled` override in `App`
 * turns the first arm red at "Stop was grey with no answer on screen" and
 * the second at the same line.
 *
 * CARD 59 (owner decision D18): an answer that finished before Stop arrived
 * stands. A Stop pressed after `done` has arrived now lands that answer, and
 * `App.stopAfterAnswer.test.tsx` holds that rule. So every arm here that
 * presses Stop keeps its run's stream OPEN at the press, the server still
 * working, and then confirms the stop with the server's `cancelled` error,
 * which is what these arms were always about: what a stop leaves on screen.
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ApiError: actual.ApiError,
    fetchPersona: vi.fn(async () => ({ persona_name: "Mendel" })),
    fetchMe: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    createRun: vi.fn(),
    openEventStream: vi.fn(),
    stopRun: vi.fn(async () => ({ stopped: true })),
    mintGuest: vi.fn(),
    getAllowance: vi.fn(),
    fetchHistory: vi.fn(),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

import {
  createRun,
  fetchHistory,
  getAllowance,
  mintGuest,
  openEventStream,
  stopRun,
} from "./lib/api";

const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const mintGuestMock = vi.mocked(mintGuest);
const getAllowanceMock = vi.mocked(getAllowance);
const fetchHistoryMock = vi.mocked(fetchHistory);
const stopRunMock = vi.mocked(stopRun);

const QUESTION = "What gene is BRCA1?";
const ANSWER = "BRCA1 is a tumour suppressor gene";

type Frame = [string, Record<string, unknown>];

/** Frames as server-sent events, the wire shape `useAgentRun` reads. */
const sse = (frames: Frame[], trace = "t-58", firstSeq = 0): string =>
  frames
    .map(
      ([type, payload], i) =>
        `id: ${firstSeq + i}\nevent: ${type}\ndata: ${JSON.stringify({
          type,
          version: "v1",
          trace_id: trace,
          seq: firstSeq + i,
          ts: "2026-09-27T00:00:00Z",
          payload,
        })}\n\n`,
    )
    .join("");

/** What `core/run_registry.py` sends when a stop lands before the run finished. */
const CANCELLED: Frame = [
  "error",
  {
    fatal: true,
    scope: "run",
    source: "run_registry",
    error_class: "cancelled",
    message: "this run was stopped before it finished",
    retry_after_s: 0,
  },
];

const GUARD: Frame = ["guard", { passed: true, category: "ok", reason: null }];
const THINK: Frame = [
  "think",
  {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop",
    resolved_entities: [],
    clarifying_question: null,
  },
];

/** A cited sentence, its citation, the verdicts and `done`: the answer. */
const answerFrames = (answer: string): Frame[] => [
  ["token", { text: `${answer} [1]. `, marker_ids: ["k1"] }],
  [
    "citation",
    {
      citation_id: "k1",
      display_index: 1,
      source: "NCBI Gene",
      source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
      layer: "layer_1_graph",
      field: "cypher_query",
      claim_text: "x",
      evidence_kind: "curated assertion",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public domain",
    },
  ],
  ["trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: false }],
  [
    "done",
    { total_cost_usd: 0.0031, total_tool_calls: 1, elapsed_ms: 11400, trust_outcome: "answer" },
  ],
];

/** One complete run, answer and `done` included. */
const wholeRunFrames: Frame[] = [
  GUARD,
  THINK,
  ["plan", { narrative: "Read the curated edges.", tool_calls: [] }],
  [
    "tool_result",
    {
      call_id: "c1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "ok",
      summary: "",
      result_count: 25,
      truncated: false,
    },
  ],
  ...answerFrames(ANSWER),
];

/** The same run as server-sent frames. */
const wholeRun = sse(wholeRunFrames);

/** A run as it stands just before the server sends `done`. */
const withoutDone = (frames: Frame[]): Frame[] => frames.filter(([type]) => type !== "done");

/**
 * The whole run in one chunk, and a flag that turns true once the client has
 * read past the end of it. The flag is the populate-check: it proves `done`
 * has ARRIVED before any arm asserts on what the screen shows.
 */
function oneChunkRun(body: string = wholeRun): {
  response: Promise<Response>;
  fullyRead: () => boolean;
} {
  let pulls = 0;
  let read = false;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      pulls += 1;
      if (pulls === 1) {
        controller.enqueue(new TextEncoder().encode(body));
        return;
      }
      read = true;
      controller.close();
    },
  });
  return {
    response: Promise.resolve(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    ),
    fullyRead: () => read,
  };
}

const answerOnScreen = () => screen.queryByText(new RegExp(ANSWER)) !== null;
const stopButton = () => screen.queryByRole("button", { name: /^stop$/i });

/** Step fake time in small `act`s, the way the reveal's own tests do. */
async function advance(ms: number, step = 100, each?: () => void) {
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    await act(async () => {
      vi.advanceTimersByTime(Math.min(step, ms - elapsed));
    });
    each?.();
  }
}

/**
 * A run whose stream stays open after `body`, the server still working, as a
 * run is at the moment a person presses Stop before it finishes. `confirmStop`
 * sends the server's reply to that stop. `fullyRead` turns true once the
 * client has read `body` and is waiting for more.
 */
function openRun(body: string, trace = "t-58"): {
  response: Promise<Response>;
  fullyRead: () => boolean;
  confirmStop: () => void;
} {
  const queue: string[] = [body];
  let wake: (() => void) | null = null;
  let pulls = 0;
  const sent = (body.match(/^event: /gm) ?? []).length;
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      pulls += 1;
      while (queue.length === 0) {
        await new Promise<void>((resolve) => {
          wake = resolve;
        });
      }
      controller.enqueue(new TextEncoder().encode(queue.shift()!));
    },
  });
  return {
    response: Promise.resolve(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    ),
    fullyRead: () => pulls >= 2,
    confirmStop: () => {
      queue.push(sse([CANCELLED], trace, sent));
      const resolve: (() => void) | null = wake;
      wake = null;
      resolve?.();
    },
  };
}

/** Ask, with the run's stream left open after `body`. */
async function askWithTheRunStillOpen(body: string): Promise<ReturnType<typeof openRun>> {
  const run = openRun(body);
  openEventStreamMock.mockImplementationOnce(() => run.response);
  const user = userEvent.setup();
  render(<App />);
  const main = within(screen.getByRole("main"));
  await user.type(main.getByRole("textbox", { name: /question/i }), QUESTION);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  await waitFor(() => expect(run.fullyRead(), "the run's stream was never read").toBe(true));
  await screen.findByTestId("step-Guard");
  return run;
}

/** Press Stop, then let the server confirm it. */
async function pressStopAndConfirm(run: ReturnType<typeof openRun>, runId: string): Promise<void> {
  const user = userEvent.setup();
  await user.click(stopButton()!);
  expect(stopRunMock).toHaveBeenCalledWith(runId, "guest-token-58");
  act(() => run.confirmStop());
  expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");
}

async function askAndLetTheWholeRunArrive(body: string = wholeRun): Promise<void> {
  const run = oneChunkRun(body);
  openEventStreamMock.mockImplementationOnce(() => run.response);
  const user = userEvent.setup();
  render(<App />);
  const main = within(screen.getByRole("main"));
  await user.type(main.getByRole("textbox", { name: /question/i }), QUESTION);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  await waitFor(() => expect(run.fullyRead(), "the run's stream was never read to its end").toBe(true));
  await screen.findByTestId("step-Guard");
}

/** A signed-out guest with allowance left, and one run id per question. */
function standardMocks(): void {
  window.localStorage.clear();
  createRunMock.mockReset();
  openEventStreamMock.mockReset();
  mintGuestMock.mockReset();
  getAllowanceMock.mockReset();
  fetchHistoryMock.mockReset();
  stopRunMock.mockClear();
  createRunMock.mockResolvedValue({ run_id: "run-58", persona_name: "Mendel" });
  mintGuestMock.mockResolvedValue({
    guest_token: "guest-token-58",
    guest_id: "guest-58",
    used: 0,
    total: 5,
  });
  getAllowanceMock.mockResolvedValue({ kind: "guest", used: 1, total: 5, counted: true });
  fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
}

describe("card 58: Stop stays on until the answer is on screen", () => {
  beforeEach(standardMocks);

  afterEach(() => {
    vi.useRealTimers();
  });

  it("offers Stop while the answer is held back, and a confirmed Stop discards it for good", async () => {
    // The answer has arrived but `done` has not: the server is still
    // finishing. The screen is still pacing through the steps.
    const run = await askWithTheRunStillOpen(sse(withoutDone(wholeRunFrames)));
    expect(answerOnScreen(), "populate-check: the answer was already on screen").toBe(false);
    expect(stopButton(), "Stop was grey with no answer on screen").toBeEnabled();

    await pressStopAndConfirm(run, "run-58");

    // No answer arrives afterwards, however long the reader waits: the
    // pacing and the reveal that were holding it are frozen by Stop.
    vi.useFakeTimers();
    await advance(10_000);
    expect(answerOnScreen(), "the answer appeared after Stop").toBe(false);
    expect(screen.queryByTestId("source-1")).toBeNull();
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
  });

  it("keeps Stop on through the writing wait, and off once the first sentence is on screen", async () => {
    await askAndLetTheWholeRunArrive();
    expect(stopButton(), "Stop was grey with no answer on screen").toBeEnabled();

    // Walk the screen forward. Before the first sentence Stop must be on;
    // from the first sentence it must be off or gone.
    vi.useFakeTimers();
    const offWhileWaiting: number[] = [];
    const onWithAnswer: number[] = [];
    let at = 0;
    let sawSentence = false;
    await advance(8_000, 100, () => {
      at += 100;
      const stop = stopButton();
      const enabled = stop !== null && !stop.hasAttribute("disabled");
      if (answerOnScreen()) {
        sawSentence = true;
        if (enabled) onWithAnswer.push(at);
      } else if (!enabled) {
        offWhileWaiting.push(at);
      }
    });

    expect(sawSentence, "populate-check: the answer never reached the screen").toBe(true);
    expect(offWhileWaiting, "Stop went off before the answer was on screen").toEqual([]);
    expect(onWithAnswer, "Stop stayed on with the answer on screen").toEqual([]);
    // Landed: the answer screen carries no Stop at all.
    expect(screen.getByTestId("source-1")).toBeInTheDocument();
    expect(stopButton()).toBeNull();
  });
});

/*
 * THE FIX ROUND, F-58-J02, F-58-A01 and F-58-J03.
 *
 * The arms above prove Stop is OFFERED. These prove what pressing it LEAVES
 * ON SCREEN whatever the run's shape, and that it works on a follow-up.
 *
 * Each run below names three helpers, so the pacing holds its end for about
 * six seconds after the whole run has arrived, as it does on develop. That
 * is the window a person presses Stop in.
 */

/** The server's `PER_QUERY_CAP_PARTIAL_RESULT_NOTE` (`harness/cost_control.py`). */
const CAP_NOTE =
  "This query reached its resource limit before finishing, so the answer below reflects a partial result gathered so far.";

const HELPERS = [
  ["cypher_query", "layer_1_graph"],
  ["ncbi_efetch", "layer_2_api"],
  ["pubtator_annotate", "layer_3_enrichment"],
] as const;

/** Guard to the last helper handing back: everything before the Write step. */
const threeHelperSearch: Frame[] = [
  GUARD,
  THINK,
  [
    "plan",
    {
      narrative: "Read the graph, the gene record and the literature.",
      tool_calls: HELPERS.map(([tool, layer], i) => ({ tool, call_id: `c${i + 1}`, layer })),
    },
  ],
  ...HELPERS.map(
    ([tool, layer], i): Frame => ["tool_start", { call_id: `c${i + 1}`, tool, layer, status: "running" }],
  ),
  ...HELPERS.map(
    ([tool, layer], i): Frame => [
      "tool_result",
      { call_id: `c${i + 1}`, tool, layer, status: "ok", summary: "", result_count: 5, truncated: false },
    ],
  ),
];

/**
 * The per-question cap's partial result, `_partial_result_for_cap` in
 * `core/graph.py`: one note token and `done` with `trust_outcome` "flag". No
 * answer sentence, no error event and no trust signal, so the reveal has
 * nothing to hold back and nothing flushes the pacing early.
 */
const capRunFrames: Frame[] = [
  ...threeHelperSearch,
  ["token", { text: CAP_NOTE, marker_ids: [] }],
  ["done", { total_cost_usd: 0.05, total_tool_calls: 3, elapsed_ms: 20000, trust_outcome: "flag" }],
];
const capRun = sse(capRunFrames);

/** An answer sentence that also carries the cap note. */
const answerWithCapNoteFrames: Frame[] = [
  ...threeHelperSearch,
  ["token", { text: CAP_NOTE, marker_ids: [] }],
  ...answerFrames(ANSWER),
];

const pageText = () => document.body.textContent ?? "";
const resultPage = () => document.querySelector('[data-tour="answer"]');

/**
 * Wait in REAL time for a run to land. Fake time cannot do it here: the
 * pacing has already scheduled its next release on a real timer by the time
 * the run has arrived, and advancing fake time never fires that timer, so a
 * fast machine walks ten fake seconds with the run stuck at the guard. The
 * ceiling is about three times the slowest landing below (three helpers,
 * about 6.5 s), so load cannot push it over.
 */
const LAND_CEILING = { timeout: 20_000 };

describe("card 58 fix round: what a Stop before the answer leaves on screen", () => {
  beforeEach(standardMocks);

  afterEach(() => {
    vi.useRealTimers();
  });

  it("populate-check: left alone, the cap result lands on the result page with its note and a trust line", async () => {
    // The shape the next arm stops. If it ever stopped landing on its own,
    // that arm would pass without proving anything.
    await askAndLetTheWholeRunArrive(capRun);
    expect(await screen.findByTestId("answer-cap", {}, LAND_CEILING)).toBeInTheDocument();
    expect(resultPage(), "the cap result never reached the result page").not.toBeNull();
    expect(screen.getByTestId("trust-line")).toBeInTheDocument();
  }, 30_000);

  it("F-58-J02: Stop on the cap result, which has no sentences, shows Search stopped and never the result page", async () => {
    // The note has arrived and `done` has not; the pacing holds the note.
    const run = await askWithTheRunStillOpen(sse(withoutDone(capRunFrames)));
    expect(resultPage(), "populate-check: the result page was already showing").toBeNull();
    expect(stopButton(), "Stop was grey with nothing on screen").toBeEnabled();

    await pressStopAndConfirm(run, "run-58");

    vi.useFakeTimers();
    await advance(10_000);

    expect(resultPage(), "Stop was pressed, and the result page came up anyway").toBeNull();
    expect(
      screen.queryByTestId("run-stopped"),
      "Stop was pressed before the answer appeared, but Search stopped is not on screen",
    ).not.toBeNull();
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(screen.queryByTestId("trust-line"), "a trust line showed after Stop").toBeNull();
    expect(pageText(), "the stopped answer's note showed after Stop").not.toMatch(/resource limit/i);
    expect(pageText(), "the cap notice showed after Stop").not.toMatch(/processing budget/i);
  });

  it("F-58-A01: Stop before the answer shows no notice from the answer it discarded", async () => {
    // A sentence and the cap note arrive together. Before Stop the pacing
    // holds both, so no notice is on screen; the view below never lands,
    // because the reveal holds the sentence, which keeps this arm about the
    // notice alone.
    const run = await askWithTheRunStillOpen(sse(withoutDone(answerWithCapNoteFrames)));
    expect(screen.queryByTestId("cap-notice"), "populate-check: the cap notice was already showing").toBeNull();
    expect(stopButton(), "Stop was grey with nothing on screen").toBeEnabled();

    await pressStopAndConfirm(run, "run-58");

    vi.useFakeTimers();
    await advance(10_000);

    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(
      screen.queryByTestId("cap-notice"),
      "a notice from the discarded answer showed under Search stopped",
    ).toBeNull();
    expect(pageText()).not.toMatch(/processing budget|resource limit/i);
    expect(answerOnScreen(), "the answer appeared after Stop").toBe(false);
  });
});

describe("card 58 fix round: Stop on a follow-up in the same thread, F-58-J03", () => {
  const FOLLOW_UP = "What diseases are associated with it?";
  const SECOND_ANSWER = "It is linked to hereditary breast and ovarian cancer";

  beforeEach(() => {
    standardMocks();
    createRunMock.mockReset();
    createRunMock
      .mockResolvedValueOnce({ run_id: "run-58-1", persona_name: "Mendel" })
      .mockResolvedValue({ run_id: "run-58-2", persona_name: "Mendel" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  /**
   * Turn one lands; the follow-up `body` then arrives whole, inline, on the
   * same screen. Returns once its stream is read to the end and its progress
   * is on screen, with Stop checked as offered: under the mutation
   * `stopEnabled={false}` on the inline `RunProgress`, this is where every
   * arm goes red.
   */
  async function landTurnOneThenFollowUpWith(body: string): Promise<ReturnType<typeof openRun>> {
    await askAndLetTheWholeRunArrive();
    expect(
      await screen.findByTestId("source-1", {}, LAND_CEILING),
      "populate-check: turn one never landed",
    ).toBeInTheDocument();

    // Turn two's stream stays open: the server is still working on it.
    const second = openRun(body, "t-58-2");
    openEventStreamMock.mockImplementationOnce(() => second.response);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/ask a follow-up question/i), FOLLOW_UP);
    await user.click(screen.getByRole("button", { name: /^ask$/i }));
    await waitFor(() => expect(second.fullyRead(), "turn two's stream was never read to its end").toBe(true));
    await screen.findByTestId("step-Guard");

    expect(resultPage(), "populate-check: the follow-up left the answer screen").not.toBeNull();
    expect(screen.queryByTestId("trust-line"), "populate-check: turn two's trust line was already showing").toBeNull();
    expect(stopButton(), "Stop was grey on a follow-up with no answer on screen").toBeEnabled();
    return second;
  }

  /** Press Stop on turn two, let the server confirm it, then wait ten seconds for anything to appear. */
  async function stopTurnTwo(second: ReturnType<typeof openRun>): Promise<void> {
    await pressStopAndConfirm(second, "run-58-2");
    vi.useFakeTimers();
    await advance(10_000);
  }

  it("offers Stop on the follow-up until its answer is on screen, and Stop keeps that answer off it", async () => {
    const second = await landTurnOneThenFollowUpWith(
      sse(withoutDone([...threeHelperSearch, ...answerFrames(SECOND_ANSWER)]), "t-58-2"),
    );
    expect(screen.queryByText(new RegExp(SECOND_ANSWER)), "populate-check: turn two was already on screen").toBeNull();

    await stopTurnTwo(second);

    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(screen.queryByText(new RegExp(SECOND_ANSWER)), "turn two's answer appeared after Stop").toBeNull();
    expect(screen.queryByTestId("trust-line"), "a trust line showed for the stopped follow-up").toBeNull();
    // The conversation is kept: turn one is still in the thread above.
    expect(screen.getByTestId("previous-turn-0")).toHaveTextContent(QUESTION);
  }, 30_000);

  it("F-58-J02 on a follow-up: Stop on the cap result keeps Search stopped inline, never the result", async () => {
    const second = await landTurnOneThenFollowUpWith(
      sse([...threeHelperSearch, ["token", { text: CAP_NOTE, marker_ids: [] }]], "t-58-2"),
    );

    await stopTurnTwo(second);

    expect(
      screen.queryByTestId("run-stopped"),
      "Stop was pressed on the follow-up, but Search stopped is not on screen",
    ).not.toBeNull();
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(screen.queryByTestId("trust-line"), "a trust line showed for the stopped follow-up").toBeNull();
    expect(screen.queryByTestId("answer-cap"), "the stopped follow-up's note showed").toBeNull();
    expect(pageText()).not.toMatch(/processing budget|resource limit/i);
    expect(screen.getByTestId("previous-turn-0")).toHaveTextContent(QUESTION);
  }, 30_000);
});
