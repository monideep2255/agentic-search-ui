/**
 * Card 24 (2026-09-25), product-owner decision the same day: the answer's
 * own status strip carries the Plain language / Researcher toggle, and
 * switching it re-runs the same question at the other depth.
 *
 * Deliberately an App-level test that drives a real SSE stream through
 * `openEventStream`, the same reasoning `App.test.tsx`'s system-notes and
 * privacy suites already give: the wiring under test is `App.tsx`'s own
 * `onDepthChange` handler calling `ask` again, one prop above what
 * `AnswerScreen.depthToggle.test.tsx` can see. A direct `AnswerScreen` test
 * proves the toggle calls `onDepthChange`; only a test that starts at the
 * top of the tree can prove that call actually re-dispatches a run.
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ApiError: actual.ApiError,
    fetchPersona: vi.fn(async () => ({ persona_name: "Mendel" })),
    fetchMe: vi.fn(async () => ({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "plain_language",
      persona_name: "Mendel",
    })),
    login: vi.fn(),
    signup: vi.fn(),
    createRun: vi.fn(),
    openEventStream: vi.fn(),
    stopRun: vi.fn(),
    mintGuest: vi.fn(),
    getAllowance: vi.fn(),
    fetchHistory: vi.fn(),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

import { createRun, fetchHistory, getAllowance, mintGuest, openEventStream } from "./lib/api";

const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const mintGuestMock = vi.mocked(mintGuest);
const getAllowanceMock = vi.mocked(getAllowance);
const fetchHistoryMock = vi.mocked(fetchHistory);

const mainArea = () => within(screen.getByRole("main"));

async function ask(user: ReturnType<typeof userEvent.setup>, question: string) {
  const main = mainArea();
  await user.type(main.getByRole("textbox", { name: /question/i }), question);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
}

/** Same stepped fake-timer helper `App.test.tsx` uses for the reveal delay. */
async function revealNow(ms = 8_000, step = 110) {
  vi.useFakeTimers();
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    await act(async () => {
      vi.advanceTimersByTime(Math.min(step, ms - elapsed));
    });
  }
  vi.useRealTimers();
}

const frame = (seq: number, type: string, payload: unknown, traceId: string): string =>
  `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
    type,
    version: "v1",
    trace_id: traceId,
    seq,
    ts: "2026-09-25T00:00:00Z",
    payload,
  })}\n\n`;

function landedStream(traceId: string, text: string): string {
  return [
    frame(0, "guard", { passed: true, category: "ok", reason: null }, traceId),
    frame(
      1,
      "think",
      {
        narrative: "Resolving the gene named in the question.",
        query_class: "single_hop",
        resolved_entities: [],
        clarifying_question: null,
      },
      traceId,
    ),
    frame(2, "plan", { narrative: "Read the curated edges.", tool_calls: [] }, traceId),
    frame(3, "token", { text, marker_ids: ["k1"] }, traceId),
    frame(
      4,
      "citation",
      {
        citation_id: "k1",
        display_index: 1,
        source: "NCBI Gene",
        source_id: "672",
        source_url: "https://www.ncbi.nlm.nih.gov/672",
        layer: "layer_1_graph",
        field: "cypher_query",
        claim_text: "x",
        evidence_kind: "curated assertion",
        assertion_confidence: "high",
        population_ancestry_context: null,
        license: "public domain",
      },
      traceId,
    ),
    frame(5, "trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: false }, traceId),
    frame(6, "done", { total_cost_usd: 0.001, total_tool_calls: 1, elapsed_ms: 1200, trust_outcome: "answer" }, traceId),
  ].join("");
}

function scriptedResponse(body: string): Promise<Response> {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return Promise.resolve(new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }));
}

describe("card 24: the answer status strip's depth toggle re-runs the question", () => {
  beforeEach(() => {
    window.localStorage.clear();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    mintGuestMock.mockResolvedValue({ guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5 });
    getAllowanceMock.mockResolvedValue({ kind: "guest", used: 0, total: 5, counted: true });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("dispatches a fresh run at the OTHER depth, for the same question, when the strip's toggle is clicked", async () => {
    const user = userEvent.setup();
    createRunMock.mockResolvedValueOnce({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockImplementationOnce(() => scriptedResponse(landedStream("trace-1", "BRCA1 causes HBOC [1]. ")));

    render(<App />);
    await ask(user, "Which diseases are associated with BRCA1?");
    await revealNow();

    // The default depth (`DEFAULT_ANSWER_MODE`) is plain_language, so the
    // first dispatch carries it; the strip's toggle should now show
    // "Plain language" lit and "Researcher" as the switch target.
    expect(createRunMock).toHaveBeenCalledTimes(1);
    expect(createRunMock.mock.calls[0][0]).toMatchObject({
      text: "Which diseases are associated with BRCA1?",
      audience_depth: "plain_language",
    });

    createRunMock.mockResolvedValueOnce({ run_id: "run-2", persona_name: "Mendel" });
    openEventStreamMock.mockImplementationOnce(() =>
      scriptedResponse(landedStream("trace-2", "BRCA1 is a tumour suppressor gene on 17q21 [1]. ")),
    );

    const group = mainArea().getByRole("group", { name: /answer depth/i });
    await user.click(within(group).getByRole("button", { name: "Researcher" }));

    // Card 24: the click shows the cost and runs nothing. Mutation: the
    // toggle's handler both holds the mode and calls `ask`.
    expect(screen.getByTestId("answer-depth-confirm")).toBeInTheDocument();
    expect(createRunMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Ask again" }));
    await revealNow();

    // Mutation this catches: `App` calling `ask` with the SAME depth
    // (a no-op toggle), or with a different question text, or not calling
    // `ask` at all so the confirm silently does nothing.
    expect(createRunMock).toHaveBeenCalledTimes(2);
    expect(createRunMock.mock.calls[1][0]).toMatchObject({
      text: "Which diseases are associated with BRCA1?",
      audience_depth: "researcher",
    });

    // It counts as one new question, the same as any other follow-up: the
    // first answer folds into the thread rather than vanishing.
    await waitFor(() => expect(screen.getByTestId("thread")).toBeInTheDocument());
  });

  async function landAndClickResearcher(user: ReturnType<typeof userEvent.setup>) {
    createRunMock.mockResolvedValueOnce({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockImplementationOnce(() => scriptedResponse(landedStream("trace-1", "BRCA1 causes HBOC [1]. ")));
    render(<App />);
    await ask(user, "Which diseases are associated with BRCA1?");
    await revealNow();
    const group = mainArea().getByRole("group", { name: /answer depth/i });
    await user.click(within(group).getByRole("button", { name: "Researcher" }));
    return screen.getByTestId("answer-depth-confirm");
  }

  it("a counted caller (a guest) sees how many searches are left today", async () => {
    // Mutation: build the guest form whatever `counted` says.
    getAllowanceMock.mockResolvedValue({ kind: "guest", used: 2, total: 5, counted: true });
    const line = await landAndClickResearcher(userEvent.setup());
    expect(line).toHaveTextContent(
      "Ask this question again in Researcher? It counts as one new search (3 left today).",
    );
  });

  it("an uncounted caller (signed in) sees no number", async () => {
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 0, counted: false });
    const line = await landAndClickResearcher(userEvent.setup());
    expect(line).toHaveTextContent("Ask this question again in Researcher? It runs as one new search.");
    expect(line.textContent).not.toMatch(/\d/);
  });

  it("the switch is gone while the confirmed run is in flight", async () => {
    // Mutation: render the switch on the streaming branch too.
    const user = userEvent.setup();
    const line = await landAndClickResearcher(user);
    expect(line).toBeInTheDocument();
    createRunMock.mockResolvedValueOnce({ run_id: "run-2", persona_name: "Mendel" });
    openEventStreamMock.mockImplementationOnce(() => new Promise<Response>(() => {}));
    await user.click(screen.getByRole("button", { name: "Ask again" }));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("group", { name: /answer depth/i })).toBeNull();
    expect(screen.queryByTestId("answer-depth-confirm")).toBeNull();
  });
});
