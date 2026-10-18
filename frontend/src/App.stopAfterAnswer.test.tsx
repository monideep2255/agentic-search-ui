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
 *
 * The fix round (judge and adversary round 1) adds:
 *
 *   - J-59-04, A-59-02: a stop request that fails late, after the person has
 *     asked a new question, never closes the new question's stream.
 *   - J-59-06: arms that go red if the 5 second fallback, the reveal freeze
 *     while the reply is awaited, or the error suppression on a confirmed
 *     stop is removed.
 */

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  /** Ends the stream the way a real fetch body ends when its request is aborted. */
  honour: (signal: AbortSignal | undefined) => void;
} {
  const queue: string[] = [first];
  let wake: (() => void) | null = null;
  let pulls = 0;
  let aborted = false;
  const rouse = () => {
    const resolve: (() => void) | null = wake;
    wake = null;
    resolve?.();
  };
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      pulls += 1;
      while (queue.length === 0 && !aborted) {
        await new Promise<void>((resolve) => {
          wake = resolve;
        });
      }
      if (aborted) {
        controller.error(new DOMException("The operation was aborted.", "AbortError"));
        return;
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
      rouse();
    },
    firstChunkRead: () => pulls >= 2,
    honour: (signal) => {
      signal?.addEventListener("abort", () => {
        aborted = true;
        rouse();
      });
    },
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
async function ask(
  stream: ReturnType<typeof openStream>,
  { awaitGuard = true }: { awaitGuard?: boolean } = {},
): Promise<ReturnType<typeof userEvent.setup>> {
  openEventStreamMock.mockImplementationOnce(() => stream.response);
  const user = userEvent.setup();
  render(<App />);
  const main = within(screen.getByRole("main"));
  await user.type(main.getByRole("textbox", { name: /question/i }), QUESTION);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  await waitFor(() => expect(stream.firstChunkRead(), "the run's first chunk was never read").toBe(true));
  // Build phase 8.7: a run whose text has arrived is shown at once, so its
  // steps are never on screen to wait for.
  if (awaitGuard) await screen.findByTestId("step-Guard");
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

  it("an answer the server finished is on screen the moment it arrives, with its sources and trust line, and Stop is gone", async () => {
    // Build phase 8.7: the screen no longer holds a finished answer back, so
    // there is no window in which the server has finished and the reader
    // still sees only the steps. The old arm pressed Stop in that window;
    // `Stop while done is in flight` below keeps the race that remains.
    const stream = openStream(sse([...SEARCH, ...ANSWER_FRAMES]));
    const stopped = watchFor("run-stopped");
    await ask(stream, { awaitGuard: false });

    expect(await screen.findByTestId("source-1", {}, { timeout: 1_500 })).toBeInTheDocument();
    expect(answerOnScreen(), "the finished answer is not on screen").toBe(true);
    expect(screen.getByTestId("trust-line")).toBeInTheDocument();
    expect(resultPage(), "the answer did not land on the result page").not.toBeNull();
    expect(stopButton(), "Stop is offered over a finished answer").toBeNull();
    stopped.stop();
    expect(stopped.seen(), "Search stopped showed for an answer that had already finished").toBe(false);
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
    // J-59-06 (M6): nor is the stream's own failure notice. The server's
    // `cancelled` error is the stop the person asked for, confirmed, so a
    // confirmed stop carries no failure text. Mutation that turns this red:
    // stop suppressing `streamError` on a confirmed stop in `App.tsx`.
    expect(screen.queryByTestId("run-failure"), "a confirmed stop showed a failure notice").toBeNull();
    expect(pageText()).not.toMatch(/run failed/i);
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

  it("J-59-06 (M1): a stop that gets no reply reads Stopping for 5 seconds, then Search stopped, never for ever", async () => {
    const stream = openStream(sse(SEARCH));
    await ask(stream);
    expect(stopButton(), "populate-check: Stop was not offered").toBeEnabled();

    // Every timer from the press on is fake, so the 5 seconds are exact.
    vi.useFakeTimers();
    act(() => {
      fireEvent.click(stopButton()!);
    });
    expect(stopRunMock).toHaveBeenCalledWith("run-59", GUEST);
    expect(stopButton()).toHaveTextContent("Stopping…");

    // The stop request succeeded, but the server's reply never comes.
    await advance(4_500);
    expect(screen.queryByTestId("run-stopped"), "the fallback fired before 5 seconds").toBeNull();
    expect(stopButton()).toHaveTextContent("Stopping…");

    // Mutation that turns this red: delete the `STOP_CONFIRM_TIMEOUT_MS`
    // effect in `App.tsx`. Stop then reads "Stopping…" for ever.
    await advance(1_000);
    expect(screen.queryByTestId("run-stopped"), "Stopping… never ended without a reply").not.toBeNull();
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(answerOnScreen()).toBe(false);
  });

  it("J-59-06 (M7): no sentence of the answer appears while Stopping, nor after the stop is confirmed", async () => {
    // Only the searches have arrived when Stop is pressed. The answer's
    // sentence, citation and verdict reach the browser while the reply is
    // awaited, `done` never does. Build phase 8.7 shows arrived text at once,
    // so what keeps it off the screen is that a press freezes the screen at
    // the events that had arrived.
    const stream = openStream(sse(SEARCH));
    await ask(stream);
    expect(answerOnScreen(), "populate-check: the answer was already on screen").toBe(false);
    expect(stopButton(), "populate-check: Stop was not offered").toBeEnabled();

    vi.useFakeTimers();
    act(() => {
      fireEvent.click(stopButton()!);
    });
    expect(stopButton()).toHaveTextContent("Stopping…");

    act(() => stream.push(sse(ANSWER_FRAMES.slice(0, -1), SEARCH.length)));
    await advance(3_000);
    expect(answerOnScreen(), "a sentence appeared while Stop was awaiting the server").toBe(false);

    act(() => stream.push(sse([CANCELLED], SEARCH.length + ANSWER_FRAMES.length - 1)));
    await advance(5_000);
    expect(screen.getByTestId("run-stopped")).toHaveTextContent("Search stopped");
    expect(answerOnScreen(), "a partial answer showed under a confirmed stop").toBe(false);
    expect(screen.queryByTestId("source-1")).toBeNull();
  });

  it("J-59-04: a stop request that fails after a new question was asked never touches the new question", async () => {
    // Fake from the first timer, moving with real time too, so the pacing of
    // question B's steps can be stepped through below without a timer left
    // on the real clock.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // Question A's stop request hangs, then fails: a slow proxy error.
    let failStop: (reason: Error) => void = () => undefined;
    stopRunMock.mockReset();
    stopRunMock.mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          failStop = reject;
        }),
    );
    const first = openStream(sse(SEARCH));
    const user = await ask(first);
    await user.click(stopButton()!);
    expect(stopButton(), "populate-check: Stop did not show it was stopping").toHaveTextContent("Stopping…");

    // Before A's stop comes back, the person asks question B.
    const second = openStream(sse(SEARCH));
    let secondSignal: AbortSignal | undefined;
    openEventStreamMock.mockImplementationOnce((_runId, _token, options) => {
      secondSignal = options?.signal;
      second.honour(secondSignal);
      return second.response;
    });
    createRunMock.mockResolvedValueOnce({ run_id: "run-59-b", persona_name: "Mendel" });
    await user.click(screen.getByRole("button", { name: /^new search$/i }));
    const main = within(screen.getByRole("main"));
    await user.type(main.getByRole("textbox", { name: /question/i }), "What is TP53?");
    await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
    await waitFor(() => expect(second.firstChunkRead(), "B's first chunk was never read").toBe(true));
    expect(secondSignal, "populate-check: B's stream was opened without a signal").toBeDefined();

    // A's stop request now fails.
    await act(async () => {
      failStop(new Error("502 from the proxy"));
      await Promise.resolve();
    });
    // Mutation that turns this red: drop the `askSeq` check in
    // `stopCurrentRun`'s catch. A's failure then closes B's stream.
    expect(secondSignal!.aborted, "A's failed stop closed question B's stream").toBe(false);

    // B's answer arrives and lands, whole, with no Stop anywhere near it.
    act(() => second.push(sse(ANSWER_FRAMES, SEARCH.length)));
    await advance(20_000, 200);
    expect(answerOnScreen(), "question B's answer never reached the screen").toBe(true);
    expect(screen.getByTestId("source-1")).toBeInTheDocument();
    expect(screen.queryByTestId("run-stopped"), "question B read Search stopped").toBeNull();
  });
});
