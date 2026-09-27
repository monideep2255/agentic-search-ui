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

/** One complete run, answer and `done` included, as server-sent frames. */
const wholeRun = [
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
    { total_cost_usd: 0.0031, total_tool_calls: 1, elapsed_ms: 11400, trust_outcome: "answer" },
  ],
]
  .map(
    ([type, payload], seq) =>
      `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
        type,
        version: "v1",
        trace_id: "t-58",
        seq,
        ts: "2026-09-27T00:00:00Z",
        payload,
      })}\n\n`,
  )
  .join("");

/**
 * The whole run in one chunk, and a flag that turns true once the client has
 * read past the end of it. The flag is the populate-check: it proves `done`
 * has ARRIVED before any arm asserts on what the screen shows.
 */
function oneChunkRun(): { response: Promise<Response>; fullyRead: () => boolean } {
  let pulls = 0;
  let read = false;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      pulls += 1;
      if (pulls === 1) {
        controller.enqueue(new TextEncoder().encode(wholeRun));
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

async function askAndLetTheWholeRunArrive(): Promise<void> {
  const run = oneChunkRun();
  openEventStreamMock.mockImplementationOnce(() => run.response);
  const user = userEvent.setup();
  render(<App />);
  const main = within(screen.getByRole("main"));
  await user.type(main.getByRole("textbox", { name: /question/i }), QUESTION);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  await waitFor(() => expect(run.fullyRead(), "the run's stream was never read to its end").toBe(true));
  await screen.findByTestId("step-Guard");
}

describe("card 58: Stop stays on until the answer is on screen", () => {
  beforeEach(() => {
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
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("offers Stop after the server finished, and Stop then discards the answer for good", async () => {
    await askAndLetTheWholeRunArrive();

    // The whole answer and `done` have arrived; the screen is still pacing
    // through the steps, so there is nothing to read yet.
    expect(answerOnScreen(), "populate-check: the answer was already on screen").toBe(false);
    expect(stopButton(), "Stop was grey with no answer on screen").toBeEnabled();

    const user = userEvent.setup();
    await user.click(stopButton()!);

    expect(stopRunMock).toHaveBeenCalledWith("run-58", "guest-token-58");
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");

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
