/**
 * Card 59: an answer that finished before Stop arrived stands (owner decision
 * D18, `testing/Board_plan.md`).
 *
 * The defect, in the reader's words: a question stopped after the server had
 * already finished showed "Search stopped", yet came back as answered in
 * history after a reload, and the conversation remembered it. The screen
 * decided "stopped" on its own, the instant Stop was pressed, while the server
 * had already recorded the answer and kept the turn in memory
 * (`testing/Developer/reports/2026-10-08_card59/diagnosis.md`).
 *
 * The rule these arms hold: the server's own stream is the verdict.
 *
 *   - `done` already arrived when Stop is pressed: the answer stands and shows
 *     at once, in full, with its sources and trust line. Nothing is sent to
 *     the server, since there is nothing left to stop.
 *   - `done` not arrived yet: the stop is sent and the stream is kept open.
 *     Stop reads "Stopping…" until the server replies. Its `cancelled` error
 *     means the stop landed first: "Search stopped", nothing of the answer.
 *     A `done` instead means the server finished first: the answer stands.
 *
 * The boundary arm, Stop pressed while `done` is in flight, is the one a rule
 * based on what the browser has seen cannot get right, and the reason the
 * server decides. A watcher records every element added to the page, so
 * "Search stopped" flashing up before the answer would fail it.
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
/** An obviously fake guest credential, the same shape card 58's arms use. */
const GUEST = "guest-token-59";

type Frame = [string, Record<string, unknown>];

/** Frames as server-sent events, numbered from `firstSeq`. */
const sse = (frames: Frame[], firstSeq = 0): string =>
  frames
    .map(([type, payload], i) => {
      const seq = firstSeq + i;
      return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
        type,
        version: "v1",
        trace_id: "t-59",
        seq,
        ts: "2026-10-08T00:00:00Z",
        payload,
      })}\n\n`;
    })
    .join("");

const HELPERS = [
  ["cypher_query", "layer_1_graph"],
  ["ncbi_efetch", "layer_2_api"],
  ["pubtator_annotate", "layer_3_enrichment"],
] as const;

/** Guard to the last helper handing back: everything before the Write step. */
const SEARCH: Frame[] = [
  ["guard", { passed: true, category: "ok", reason: null }],
  [
    "think",
    {
      narrative: "Resolving the gene named in the question.",
      query_class: "single_hop",
      resolved_entities: [],
      clarifying_question: null,
    },
  ],
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

/** A cited sentence, its citation, the verdict and `done`: the finished answer. */
const ANSWER_FRAMES: Frame[] = [
  ["token", { text: `${ANSWER} [1]. `, marker_ids: ["k1"] }],
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
    { total_cost_usd: 0.0031, total_tool_calls: 3, elapsed_ms: 11400, trust_outcome: "answer" },
  ],
];

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

/**
 * A run's event stream the test can feed while it is open, the way the
 * server's stream stays open while a run is in flight. `firstChunkRead` is
 * the populate-check: the client has read the first chunk and is waiting for
 * more.
 */
function openStream(first: string): {
  response: Promise<Response>;
  push: (body: string) => void;
  firstChunkRead: () => boolean;
} {
  const queue: string[] = [first];
  let wake: (() => void) | null = null;
  let pulls = 0;
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
    push: (body) => {
      queue.push(body);
      const resolve: (() => void) | null = wake;
      wake = null;
      resolve?.();
    },
    firstChunkRead: () => pulls >= 2,
  };
}

/** Records whether an element with `testId` was ever added to the page. */
function watchFor(testId: string): { seen: () => boolean; stop: () => void } {
  const selector = `[data-testid="${testId}"]`;
  let seen = document.querySelector(selector) !== null;
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      for (const node of Array.from(record.addedNodes)) {
        if (!(node instanceof Element)) continue;
        if (node.matches(selector) || node.querySelector(selector) !== null) seen = true;
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  return { seen: () => seen, stop: () => observer.disconnect() };
}

const answerOnScreen = () => screen.queryByText(new RegExp(ANSWER)) !== null;
const stopButton = () => screen.queryByRole("button", { name: /^stop/i });
const resultPage = () => document.querySelector('[data-tour="answer"]');
const pageText = () => document.body.textContent ?? "";

/** Ask, and return once the first chunk of `stream` has been read. */
async function ask(stream: ReturnType<typeof openStream>): Promise<ReturnType<typeof userEvent.setup>> {
  openEventStreamMock.mockImplementationOnce(() => stream.response);
  const user = userEvent.setup();
  render(<App />);
  const main = within(screen.getByRole("main"));
  await user.type(main.getByRole("textbox", { name: /question/i }), QUESTION);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  await waitFor(() => expect(stream.firstChunkRead(), "the run's first chunk was never read").toBe(true));
  await screen.findByTestId("step-Guard");
  return user;
}

/** Step fake time in small `act`s. */
async function advance(ms: number, step = 100) {
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    await act(async () => {
      vi.advanceTimersByTime(Math.min(step, ms - elapsed));
    });
  }
}

describe("card 59: an answer that finished before Stop arrived stands", () => {
  beforeEach(() => {
    window.localStorage.clear();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    stopRunMock.mockReset();
    stopRunMock.mockResolvedValue({ stopped: true });
    createRunMock.mockResolvedValue({ run_id: "run-59", persona_name: "Mendel" });
    mintGuestMock.mockResolvedValue({ guest_token: GUEST, guest_id: "guest-59", used: 0, total: 5 });
    getAllowanceMock.mockResolvedValue({ kind: "guest", used: 1, total: 5, counted: true });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("Stop after the server finished shows the whole answer with its sources and trust line, never Search stopped", async () => {
    const stream = openStream(sse([...SEARCH, ...ANSWER_FRAMES]));
    const user = await ask(stream);

    // `done` has arrived; the pacing still holds the answer back.
    expect(answerOnScreen(), "populate-check: the answer was already on screen").toBe(false);
    expect(stopButton(), "populate-check: Stop was not offered").toBeEnabled();

    const stopped = watchFor("run-stopped");
    await user.click(stopButton()!);

    // At once, not after the pacing: the reader asked to stop waiting.
    expect(await screen.findByTestId("source-1", {}, { timeout: 1_500 })).toBeInTheDocument();
    expect(answerOnScreen(), "the finished answer is not on screen").toBe(true);
    expect(screen.getByTestId("trust-line")).toBeInTheDocument();
    expect(resultPage(), "the answer did not land on the result page").not.toBeNull();
    stopped.stop();
    expect(stopped.seen(), "Search stopped showed for an answer that had already finished").toBe(false);
    // Nothing to stop on the server, and a stop sent now could cut its
    // record-keeping short.
    expect(stopRunMock).not.toHaveBeenCalled();
  });

  it("Stop before the server finished reads Stopping until the server confirms, then Search stopped and nothing of the answer", async () => {
    const stream = openStream(sse(SEARCH));
    const user = await ask(stream);
    expect(stopButton(), "populate-check: Stop was not offered").toBeEnabled();

    await user.click(stopButton()!);
    expect(stopRunMock).toHaveBeenCalledWith("run-59", GUEST);

    // The server has not answered the stop yet: nothing is claimed.
    expect(screen.queryByTestId("run-stopped"), "Search stopped showed before the server confirmed").toBeNull();
    expect(stopButton(), "Stop did not show it was stopping").toHaveTextContent("Stopping…");
    expect(stopButton()).toBeDisabled();

    // The server confirms: the stop landed before the run finished.
    act(() => stream.push(sse([CANCELLED], SEARCH.length)));
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");

    vi.useFakeTimers();
    await advance(10_000);
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(answerOnScreen(), "an answer appeared after a confirmed stop").toBe(false);
    expect(resultPage(), "a confirmed stop reached the result page").toBeNull();
    expect(screen.queryByTestId("trust-line")).toBeNull();
    // The server's own wording for the cancellation is not shown as a failure.
    expect(pageText()).not.toMatch(/stopped before it finished/i);
  });

  it("Stop while done is in flight: the answer stands, and the screen never shows both or neither", async () => {
    const stream = openStream(sse(SEARCH));
    const user = await ask(stream);
    expect(answerOnScreen(), "populate-check: the answer was already on screen").toBe(false);

    const stopped = watchFor("run-stopped");
    await user.click(stopButton()!);
    expect(stopRunMock).toHaveBeenCalledWith("run-59", GUEST);
    expect(screen.queryByTestId("run-stopped"), "Search stopped showed before the server replied").toBeNull();

    // The server finished first: its stream ends in `done`, not `cancelled`.
    act(() => stream.push(sse(ANSWER_FRAMES, SEARCH.length)));

    expect(await screen.findByTestId("source-1", {}, { timeout: 1_500 })).toBeInTheDocument();
    expect(answerOnScreen(), "the answer the server finished is not on screen").toBe(true);
    expect(screen.getByTestId("trust-line")).toBeInTheDocument();
    stopped.stop();
    expect(stopped.seen(), "Search stopped showed for an answer the server had finished").toBe(false);
    expect(screen.queryByTestId("run-stopped")).toBeNull();
  });

  it("a stop the server never receives falls back to Search stopped, so the screen is never left with neither", async () => {
    stopRunMock.mockReset();
    stopRunMock.mockRejectedValue(new Error("network down"));
    const stream = openStream(sse(SEARCH));
    const user = await ask(stream);

    await user.click(stopButton()!);
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(answerOnScreen()).toBe(false);
  });
});
