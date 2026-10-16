/**
 * Card 112: "Your searches" keeps every earlier search of the same question
 * when that question is asked again, and a stopped search's row reads what
 * the server will say after a reload, before any reload.
 *
 * The finding (PR-109-02): straight after a Stop, the rail fell from 11 rows
 * to 5. Every earlier "Which diseases are associated with BRCA1?" row was
 * gone until a reload, and the new row had no second line. The cause was in
 * `ask`, not in the Stop: the rail filtered out every row with the same
 * question text the moment the question was asked again, so an answered
 * re-ask lost them too. The second arm pins that.
 *
 * The history comes through the REAL `fetchHistory` with only `fetch`
 * stubbed, as `App.historyNoAnswer.test.tsx` does, so the rows are the ones
 * the validator and `formatHistoryMeta` really produce.
 *
 * Mutation: restoring `...current.filter((item) => item.question !== question)`
 * in `ask` turns both arms red at "an earlier row of the same question
 * vanished"; dropping the stopped-row effect turns the first arm red at
 * "the stopped row has no 'No answer saved' line".
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ApiError: actual.ApiError,
    fetchHistory: actual.fetchHistory,
    fetchPersona: vi.fn(async () => ({ persona_name: "Mendel" })),
    fetchMe: vi.fn(async () => ({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "Mendel",
    })),
    login: vi.fn(async () => ({ access_token: "test-token", refresh_token: "test-refresh", token_type: "bearer" })),
    signup: vi.fn(),
    createRun: vi.fn(async () => ({ run_id: "run-112", persona_name: "Mendel" })),
    openEventStream: vi.fn(),
    stopRun: vi.fn(async () => ({ stopped: true })),
    mintGuest: vi.fn(),
    getAllowance: vi.fn(async () => ({ kind: "user", used: 0, total: 100, counted: false })),
    fetchHistoryAnswer: vi.fn(),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

import { createRun, fetchHistoryAnswer, openEventStream, stopRun } from "./lib/api";

const openEventStreamMock = vi.mocked(openEventStream);
const createRunMock = vi.mocked(createRun);
const fetchHistoryAnswerMock = vi.mocked(fetchHistoryAnswer);
const stopRunMock = vi.mocked(stopRun);

const QUESTION = "Which diseases are associated with BRCA1?";

type Frame = [string, Record<string, unknown>];

const sse = (frames: Frame[], firstSeq = 0): string =>
  frames
    .map(
      ([type, payload], i) =>
        `id: ${firstSeq + i}\nevent: ${type}\ndata: ${JSON.stringify({
          type,
          version: "v1",
          trace_id: "run-112",
          seq: firstSeq + i,
          ts: "2026-10-09T00:00:00Z",
          payload,
        })}\n\n`,
    )
    .join("");

const citation = (n: number): Frame => [
  "citation",
  {
    citation_id: `r${n}`,
    display_index: n,
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

/** The searches and the records, as a run stands when a person presses Stop. */
const searchAndRecords: Frame[] = [
  ["guard", { passed: true, category: "ok", reason: null }],
  [
    "think",
    { narrative: "Resolving BRCA1.", query_class: "single_hop", resolved_entities: [], clarifying_question: null },
  ],
  ["plan", { narrative: "Read the graph.", tool_calls: [{ tool: "cypher_query", call_id: "c1", layer: "layer_1_graph" }] }],
  [
    "tool_result",
    { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "ok", summary: "", result_count: 2, truncated: false },
  ],
  ["token", { text: "Found 2 disease records for BRCA1.", marker_ids: [], placement: "listing" }],
  ["token", { text: "Disease name: Alpha disease [1].", marker_ids: ["r1"], placement: "listing" }],
  ["token", { text: "Disease name: Beta disease [2].", marker_ids: ["r2"], placement: "listing" }],
  citation(1),
  citation(2),
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

const answerAndDone: Frame[] = [
  ["token", { text: "BRCA1 is linked to inherited breast cancer [1]. ", marker_ids: ["r1"], placement: "summary" }],
  ["trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: false }],
  ["done", { total_cost_usd: 0.003, total_tool_calls: 1, elapsed_ms: 9000, trust_outcome: "answer" }],
];

/** A run whose stream stays open after `body`; `send` adds frames to it. */
function openRun(body: string): { response: Promise<Response>; send: (frames: Frame[]) => void } {
  const queue: string[] = [body];
  let wake: (() => void) | null = null;
  let sent = (body.match(/^event: /gm) ?? []).length;
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
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
    send: (frames) => {
      queue.push(sse(frames, sent));
      sent += frames.length;
      const resolve: (() => void) | null = wake;
      wake = null;
      resolve?.();
    },
  };
}

/** The account's history before the ask: the question three times, and one other. */
const SERVER_HISTORY = {
  items: [
    { trace_id: "t-answered-2", question: QUESTION, asked_at: "2026-10-09T05:00:00Z", citation_count: 21, has_saved_answer: true },
    { trace_id: "t-egfr", question: "What is known about EGFR mutations?", asked_at: "2026-10-09T04:00:00Z", citation_count: 55, has_saved_answer: true },
    { trace_id: "t-stopped-1", question: QUESTION, asked_at: "2026-10-09T03:00:00Z", citation_count: 21, has_saved_answer: false },
    { trace_id: "t-answered-1", question: QUESTION, asked_at: "2026-10-08T03:00:00Z", citation_count: 21, has_saved_answer: true },
  ],
  count: 4,
};

const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));
const railRows = () =>
  within(screen.getByTestId("history-rail"))
    .getAllByRole("button")
    .filter((button) => (button.textContent ?? "").startsWith(QUESTION));
const allRailRows = () =>
  within(screen.getByTestId("history-rail"))
    .getAllByRole("button")
    .filter((button) => /^(Older question|Which diseases)/.test(button.textContent ?? ""));
/** The highlighted row is the one whose style class differs from its siblings'. */
const highlightedIndexes = () => {
  const classes = railRows().map((row) => row.className);
  const count = (c: string) => classes.filter((x) => x === c).length;
  const common = [...classes].sort((x, y) => count(y) - count(x))[0];
  return railRows().flatMap((row, i) => (row.className === common ? [] : [i]));
};

async function signInAndAsk(
  run: ReturnType<typeof openRun>,
  history: { items: unknown[]; count: number } = SERVER_HISTORY,
  restoredRows = 3,
): Promise<void> {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify(history), { status: 200, headers: { "Content-Type": "application/json" } }),
    ),
  );
  openEventStreamMock.mockImplementationOnce(() => run.response);
  const user = userEvent.setup();
  render(<App />);
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await mainArea().findByRole("textbox", { name: /question/i });
  await screen.findByTestId("history-rail");
  await waitFor(() =>
    expect(
      restoredRows === 3 ? railRows() : allRailRows(),
      "populate-check: the restored history never arrived",
    ).toHaveLength(restoredRows),
  );

  await user.type(mainArea().getByRole("textbox", { name: /question/i }), QUESTION);
  await user.click(mainArea().getByRole("button", { name: /^search the knowledge graph$/i }));
  expect(await screen.findByText(/Alpha disease/), "populate-check: the records never reached the screen").toBeInTheDocument();
}

describe("card 112: earlier searches of the same question stay in the history list", () => {
  beforeEach(() => {
    window.localStorage.clear();
    openEventStreamMock.mockReset();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("after a Stop, every earlier row stays and the stopped row reads 'No answer saved' with its date", async () => {
    const run = openRun(sse(searchAndRecords));
    await signInAndAsk(run);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^stop$/i }));
    act(() => run.send([CANCELLED]));
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");

    const today = new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" });
    await waitFor(() =>
      expect(railRows()[0]?.textContent, "the stopped row has no 'No answer saved' line").toBe(
        `${QUESTION}No answer saved · ${today}`,
      ),
    );
    expect(railRows(), "an earlier row of the same question vanished").toHaveLength(4);
    expect(railRows().map((row) => row.textContent)).toEqual([
      `${QUESTION}No answer saved · ${today}`,
      expect.stringMatching(/21 sources cited/),
      expect.stringMatching(/No answer saved/),
      expect.stringMatching(/21 sources cited/),
    ]);
    expect(within(screen.getByTestId("history-rail")).getByRole("button", { name: /EGFR/ })).toBeInTheDocument();
  });

  it("after an answered re-ask, every earlier row stays too", async () => {
    const run = openRun(sse(searchAndRecords));
    await signInAndAsk(run);
    act(() => run.send(answerAndDone));
    expect(await screen.findByText(/BRCA1 is linked to inherited breast cancer/)).toBeInTheDocument();

    expect(railRows(), "an earlier row of the same question vanished").toHaveLength(4);
    expect(railRows()[0]?.textContent).not.toMatch(/No answer saved/);
  });
});

describe("card 112 fix round", () => {
  beforeEach(() => {
    window.localStorage.clear();
    openEventStreamMock.mockReset();
    createRunMock.mockReset();
    createRunMock.mockResolvedValue({ run_id: "run-112", persona_name: "Mendel" } as never);
    stopRunMock.mockReset();
    stopRunMock.mockResolvedValue({ stopped: true } as never);
    fetchHistoryAnswerMock.mockReset();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("a stop whose request failed leaves the row as it was", async () => {
    stopRunMock.mockRejectedValueOnce(new Error("network down"));
    const run = openRun(sse(searchAndRecords));
    await signInAndAsk(run);
    await userEvent.setup().click(screen.getByRole("button", { name: /^stop$/i }));
    expect(await screen.findByTestId("run-stopped")).toHaveTextContent("Search stopped");
    await waitFor(() => expect(stopRunMock).toHaveBeenCalled());
    expect(railRows()[0]?.textContent, "a failed stop must not write 'No answer saved'").toBe(QUESTION);
  });

  // Honest limit: reverting the tag to match on question text does NOT turn
  // this red. A stray run id on an older bare row has no effect on screen
  // (that row has no saved-answer flag, so it still re-asks). The test pins
  // what a person can see: the run's own row opens its own run, the bare one
  // re-asks.
  it("a run's results are tagged to its own row id, not to an older row of the same question", async () => {
    createRunMock.mockRejectedValueOnce(new Error("network down"));
    const run = openRun(sse(searchAndRecords));
    openEventStreamMock.mockImplementationOnce(() => run.response);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ items: [], count: 0 }), { status: 200, headers: { "Content-Type": "application/json" } }),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(navArea().getByRole("button", { name: /log in/i }));
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));
    await mainArea().findByRole("textbox", { name: /question/i });
    await screen.findByTestId("history-rail");
    await user.type(mainArea().getByRole("textbox", { name: /question/i }), QUESTION);
    await user.click(mainArea().getByRole("button", { name: /^search the knowledge graph$/i }));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(railRows()).toHaveLength(1));
    // Ask it again from the rail: the first, bare row stays; the new run is the second row.
    await user.click(railRows()[0]!);
    expect(await screen.findByText(/Alpha disease/)).toBeInTheDocument();
    act(() => run.send(answerAndDone));
    await screen.findByText(/BRCA1 is linked to inherited breast cancer/);
    await waitFor(() => expect(railRows()).toHaveLength(2));
    fetchHistoryAnswerMock.mockImplementation(() => new Promise(() => undefined));
    // The newest row (this run) opens its saved answer under its own id.
    await user.click(railRows()[0]!);
    await waitFor(() => expect(fetchHistoryAnswerMock).toHaveBeenCalledWith("test-token", "run-112"));
    expect(fetchHistoryAnswerMock).toHaveBeenCalledTimes(1);
    // The older, bare row never carried a run id, so it re-asks instead of opening a saved answer.
    createRunMock.mockClear();
    createRunMock.mockRejectedValueOnce(new Error("network down"));
    await user.click(railRows()[railRows().length - 1]!);
    await waitFor(() => expect(createRunMock).toHaveBeenCalled());
    expect(fetchHistoryAnswerMock).toHaveBeenCalledTimes(1);
  });

  it("the stopped row's date is the day the stop was confirmed", async () => {
    const run = openRun(sse(searchAndRecords));
    await signInAndAsk(run);
    const user = userEvent.setup();
    const realNow = Date.now;
    // The ask was sent on 1 Jan; the stop is confirmed on 3 Jan.
    vi.spyOn(Date, "now").mockImplementation(() => new Date(2027, 0, 3, 12, 0, 0).getTime());
    await user.click(screen.getByRole("button", { name: /^stop$/i }));
    act(() => run.send([CANCELLED]));
    await screen.findByTestId("run-stopped");
    await waitFor(() => expect(railRows()[0]?.textContent).toBe(`${QUESTION}No answer saved · Jan 3`));
    Date.now = realNow;
    vi.restoreAllMocks();
  });

  it("with the server's limit of rows shown, a re-ask keeps the list at that limit and drops the oldest", async () => {
    const items = Array.from({ length: 20 }, (_, i) => ({
      trace_id: `t-${i}`,
      question: i === 5 ? QUESTION : `Older question ${i}`,
      asked_at: "2026-10-08T03:00:00Z",
      citation_count: 3,
      has_saved_answer: true,
    }));
    const run = openRun(sse(searchAndRecords));
    await signInAndAsk(run, { items, count: 20 }, 20);
    expect(allRailRows()).toHaveLength(20);
    expect(screen.queryByRole("button", { name: /Older question 19/ })).not.toBeInTheDocument();
  });

  it("opening an older row of a re-asked question highlights that row, not the newest", async () => {
    const run = openRun(sse(searchAndRecords));
    await signInAndAsk(run);
    act(() => run.send(answerAndDone));
    await screen.findByText(/BRCA1 is linked to inherited breast cancer/);
    await waitFor(() => expect(railRows()).toHaveLength(4));
    fetchHistoryAnswerMock.mockImplementation(() => new Promise(() => undefined));
    const user = userEvent.setup();
    await user.click(railRows()[3]!);
    await waitFor(() => expect(fetchHistoryAnswerMock).toHaveBeenCalledWith("test-token", "t-answered-1"));
    await waitFor(() => expect(highlightedIndexes()).toEqual([3]));
  });
});
