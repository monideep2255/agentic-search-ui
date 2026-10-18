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
 *
 * BUILD PHASE 8.7 (the owner's decisions of 2026-09-27): the screen no longer
 * holds back text that has arrived, so an answer that is on the wire is on
 * screen in the same render, and Stop is offered only until the first
 * sentence of the written summary is there. What these arms pin is therefore
 * what a Stop leaves behind, not what the screen was holding:
 * - Stop before any record: "Search stopped" alone, and nothing that arrives
 *   after the press is ever shown;
 * - Stop after the records: "Search stopped" stands above the records already
 *   shown, and nothing new appears after it.
 * Text that arrives after the press is sent on the open stream on purpose: it
 * is the race a real Stop runs, and it is what the old pacing used to hide.
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

const SUMMARY = "BRCA1 is linked to two inherited conditions";

const citationFrame = (n: number): Frame => [
  "citation",
  {
    citation_id: `r${n}`,
    display_index: n + 1,
    source: "MedGen",
    source_id: `C00${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C00${n}`,
    layer: "layer_2_api",
    field: "name",
    claim_text: `Disease ${n}`,
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  },
];

/** The count line and two records the moment the searches end (build phase 8.7). */
const recordsFrames: Frame[] = [
  ["token", { text: "Found 2 disease records for BRCA1.", marker_ids: [], placement: "listing" }],
  ["token", { text: "Disease name: Alpha disease [2].", marker_ids: ["r1"], placement: "listing" }],
  ["token", { text: "Disease name: Beta disease [3].", marker_ids: ["r2"], placement: "listing" }],
  citationFrame(1),
  citationFrame(2),
];

/** The written summary, which lands later and is shown above the records. */
const summaryFrames: Frame[] = [
  ["token", { text: `${SUMMARY} [1]. `, marker_ids: ["k1"], placement: "summary" }],
  answerFrames(ANSWER)[1]!,
];

/** The verdict, without `done`: a stopped run never sends it (`done` and `cancelled` are exclusive). */
const trustFrames: Frame[] = [
  ["trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: false }],
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
  /** The server sends more frames on the open stream, e.g. after the press. */
  send: (frames: Frame[]) => void;
} {
  const queue: string[] = [body];
  let wake: (() => void) | null = null;
  let pulls = 0;
  let sent = (body.match(/^event: /gm) ?? []).length;
  const push = (text: string) => {
    queue.push(text);
    const resolve: (() => void) | null = wake;
    wake = null;
    resolve?.();
  };
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
      push(sse([CANCELLED], trace, sent));
      sent += 1;
    },
    send: (frames) => {
      push(sse(frames, trace, sent));
      sent += frames.length;
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
  await pressStop(runId);
  act(() => run.confirmStop());
  expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");
}

/** Press Stop and stop there: the server's reply, and anything else it sends, comes after. */
async function pressStop(runId: string): Promise<void> {
  const user = userEvent.setup();
  await user.click(stopButton()!);
  expect(stopRunMock).toHaveBeenCalledWith(runId, "guest-token-58");
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

  it("offers Stop before any record is on screen, and what arrives after the press is never shown", async () => {
    // The searches are under way and nothing readable has arrived.
    const run = await askWithTheRunStillOpen(sse(threeHelperSearch));
    expect(answerOnScreen(), "populate-check: the answer was already on screen").toBe(false);
    expect(stopButton(), "Stop was grey with no answer on screen").toBeEnabled();

    await pressStop("run-58");
    // The race a real Stop runs: the records and the answer reach the browser
    // after the press and before the server's reply.
    act(() => run.send([...recordsFrames, ...answerFrames(ANSWER).filter(([type]) => type !== "done")]));
    act(() => run.confirmStop());
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");

    vi.useFakeTimers();
    await advance(10_000);
    expect(answerOnScreen(), "the answer appeared after Stop").toBe(false);
    expect(screen.queryByText(/Alpha disease/), "a record appeared after Stop").toBeNull();
    expect(screen.queryByTestId("source-1")).toBeNull();
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
  });

  it("keeps Stop on while the records and the first summary sentence are on screen, and off once the answer lands", async () => {
    const run = await askWithTheRunStillOpen(sse([...threeHelperSearch, ...recordsFrames]));
    expect(await screen.findByText(/Alpha disease/), "populate-check: the records never reached the screen").toBeInTheDocument();
    expect(answerOnScreen(), "populate-check: the summary was already on screen").toBe(false);
    // Records alone do not take Stop away: the reader is still waiting for the answer.
    expect(stopButton(), "Stop went grey at the records").toBeEnabled();

    // The first sentence is on screen but the server is still writing: Stop
    // still cuts the rest short (UI fix set 9, item 9.6).
    act(() => run.send(summaryFrames));
    expect(await screen.findByText(new RegExp(SUMMARY))).toBeInTheDocument();
    expect(stopButton(), "Stop went grey while the server was still writing").toBeEnabled();

    // `done` lands the answer: nothing is left to stop.
    act(() => run.send([...trustFrames, ["done", { total_cost_usd: 0.0031, total_tool_calls: 1, elapsed_ms: 11400, trust_outcome: "answer" }]]));
    expect(await screen.findByTestId("source-1")).toBeInTheDocument();
    expect(stopButton(), "Stop stayed on over a landed answer").toBeNull();
  });

  it("owner decision 2026-09-27: Stop after the records keeps them under Search stopped, and nothing new follows", async () => {
    const run = await askWithTheRunStillOpen(sse([...threeHelperSearch, ...recordsFrames]));
    expect(await screen.findByText(/Alpha disease/), "populate-check: the records never reached the screen").toBeInTheDocument();
    expect(stopButton(), "Stop was grey with only the records on screen").toBeEnabled();

    await pressStop("run-58");
    // The summary and the verdicts arrive after the press.
    act(() => run.send([...summaryFrames, ...trustFrames]));
    act(() => run.confirmStop());
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");

    vi.useFakeTimers();
    await advance(10_000);
    const stopped = screen.getByTestId("run-stopped");
    expect(stopped).toHaveTextContent("Search stopped");
    // The records stay, below the Search stopped block.
    const records = screen.getByText(/Alpha disease/);
    expect(
      Boolean(stopped.compareDocumentPosition(records) & Node.DOCUMENT_POSITION_FOLLOWING),
      "the records are not below Search stopped",
    ).toBe(true);
    expect(screen.getByText(/Beta disease/)).toBeInTheDocument();
    // Nothing that arrived after the press is shown.
    expect(screen.queryByText(new RegExp(SUMMARY)), "the summary appeared after Stop").toBeNull();
    expect(screen.queryByTestId("trust-line"), "a trust line showed under Stop").toBeNull();
    expect(screen.queryByTestId("streaming-writing-indicator"), "the writing mark stayed under Stop").toBeNull();
    expect(screen.queryByText(/✓ Answered/), "the landed result line came up for a stopped run").toBeNull();
    expect(stopButton(), "Stop is still offered on a stopped run").toBeNull();
  }, 30_000);
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
    // Only the searches have arrived. A sentence and the cap note reach the
    // browser after the press; nothing that arrives after Stop is shown.
    const run = await askWithTheRunStillOpen(sse(threeHelperSearch));
    expect(screen.queryByTestId("cap-notice"), "populate-check: the cap notice was already showing").toBeNull();
    expect(stopButton(), "Stop was grey with nothing on screen").toBeEnabled();

    await pressStop("run-58");
    act(() => run.send(answerWithCapNoteFrames.slice(threeHelperSearch.length).filter(([type]) => type !== "done")));
    act(() => run.confirmStop());
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");

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
    const second = await landTurnOneThenFollowUpWith(sse(threeHelperSearch, "t-58-2"));
    expect(screen.queryByText(new RegExp(SECOND_ANSWER)), "populate-check: turn two was already on screen").toBeNull();

    await pressStop("run-58-2");
    // The follow-up's answer reaches the browser after the press.
    act(() => second.send(answerFrames(SECOND_ANSWER).filter(([type]) => type !== "done")));
    act(() => second.confirmStop());
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");
    vi.useFakeTimers();
    await advance(10_000);

    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(screen.queryByText(new RegExp(SECOND_ANSWER)), "turn two's answer appeared after Stop").toBeNull();
    expect(screen.queryByTestId("trust-line"), "a trust line showed for the stopped follow-up").toBeNull();
    // The conversation is kept: turn one is still in the thread above.
    expect(screen.getByTestId("previous-turn-0")).toHaveTextContent(QUESTION);
  }, 30_000);

  it("owner decision 2026-09-27 on a follow-up: Stop after its records keeps them under Search stopped", async () => {
    const second = await landTurnOneThenFollowUpWith(sse([...threeHelperSearch, ...recordsFrames], "t-58-2"));
    expect(await screen.findByText(/Alpha disease/), "populate-check: the follow-up's records never showed").toBeInTheDocument();

    await pressStop("run-58-2");
    act(() => second.send([...summaryFrames, ...trustFrames]));
    act(() => second.confirmStop());
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");
    vi.useFakeTimers();
    await advance(10_000);

    expect(screen.getByText(/Alpha disease/), "the records were taken back").toBeInTheDocument();
    expect(screen.queryByText(new RegExp(SUMMARY)), "the summary appeared after Stop").toBeNull();
    expect(screen.queryByTestId("trust-line"), "a trust line showed under Stop").toBeNull();
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
