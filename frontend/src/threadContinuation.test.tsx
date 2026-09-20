/**
 * UI fix set 7, R22: a follow-up never leaves the answer screen.
 *
 * The product owner's words, 2026-09-13: "Secondly, it goes to a new page,
 * which it should not. The first answer should minimise and the chat should
 * continue on the same screen. That is one of the most important things."
 *
 * WHAT WAS ACTUALLY WRONG, and why it is an App-level test rather than a
 * component one. Every piece already worked: the second run dispatched, the
 * thread archived, the answer landed. `ask()` then called
 * `setSearchView({ name: "run" })`, which swaps the WHOLE screen for
 * `RunScreen`, so the conversation left the page for the length of the
 * second run and came back when it finished. No component could see that:
 * `AnswerScreen` was simply unmounted, and `RunScreen` rendered exactly what
 * it was asked to. The defect lives in which screen App chooses, so that is
 * what these arms assert.
 *
 * The arms are written against DOM ORDER and against a marker only the
 * answer screen carries (`data-tour="answer"`), not against "a second answer
 * eventually appeared", which was already true before this change and is the
 * assertion build phase 4.16 recorded as having measured the wrong property
 * twice.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
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
      audience_depth: "researcher",
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

import {
  createRun,
  fetchHistory,
  getAllowance,
  mintGuest,
  openEventStream,
} from "./lib/api";

const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const mintGuestMock = vi.mocked(mintGuest);
const getAllowanceMock = vi.mocked(getAllowance);
const fetchHistoryMock = vi.mocked(fetchHistory);

const mainArea = () => within(screen.getByRole("main"));

/**
 * One complete, landing run, as server-sent frames.
 *
 * `answer` is interpolated so the two turns say different things: an arm
 * that could not tell turn one's text from turn two's would pass against a
 * screen that never updated at all.
 */
const streamFor = (trace: string, answer: string): string =>
  [
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
      {
        total_cost_usd: 0.0031,
        total_tool_calls: 1,
        elapsed_ms: 11400,
        trust_outcome: "answer",
      },
    ],
  ]
    .map(
      ([type, payload], seq) =>
        `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
          type,
          version: "v1",
          trace_id: trace,
          seq,
          ts: "2026-09-13T00:00:00Z",
          payload,
        })}\n\n`,
    )
    .join("");

function scripted(body: string): Promise<Response> {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return Promise.resolve(
    new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
  );
}

/** A stream that opens and never sends anything: a run still in flight. */
const neverLands = (): Promise<Response> => new Promise(() => {});

/** True when `first` precedes `second` in document order. */
const precedes = (first: Element, second: Element): boolean =>
  (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;

const FIRST_Q = "What gene is BRCA1?";
const SECOND_Q = "What diseases are associated with it?";

async function askFirst(user: ReturnType<typeof userEvent.setup>) {
  const main = mainArea();
  await user.type(main.getByRole("textbox", { name: /question/i }), FIRST_Q);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  // The landed answer, not merely a screen change: `source-1` is written
  // from the run's own citation event and cannot render before it arrives.
  await screen.findByTestId("source-1", undefined, { timeout: 10000 });
}

async function askFollowUp(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/ask a follow-up question/i), SECOND_Q);
  await user.click(screen.getByRole("button", { name: /^ask$/i }));
}

describe("R22: a follow-up continues on the same screen", () => {
  beforeEach(() => {
    window.localStorage.clear();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    createRunMock
      .mockResolvedValueOnce({ run_id: "run-1", persona_name: "Mendel" })
      .mockResolvedValue({ run_id: "run-2", persona_name: "Mendel" });
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1",
      guest_id: "guest-1",
      used: 0,
      total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "guest", used: 1, total: 5, counted: true });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("keeps the answer screen mounted and renders the thread above the inline run", async () => {
    openEventStreamMock
      .mockImplementationOnce(() => scripted(streamFor("t-1", "BRCA1 is a tumour suppressor")))
      .mockImplementation(neverLands);

    const user = userEvent.setup();
    render(<App />);
    await askFirst(user);

    // POPULATE-CHECK. There is nothing to keep before a follow-up, so a
    // thread here would mean the arm below proves nothing about archiving.
    expect(screen.queryByTestId("thread")).toBeNull();

    await askFollowUp(user);

    // 1. The run is in flight and its progress is on screen. `step-Guard`
    //    exists only inside `RunProgress`.
    const guard = await screen.findByTestId("step-Guard");

    // 2. THE SCREEN DID NOT CHANGE. `data-tour="answer"` is on the answer
    //    screen's card and nowhere else, so its presence during a live run
    //    is the direct proof that no full-screen run replaced it. This is
    //    the assertion that goes red if `ask()` ever routes a continuation
    //    back through `{ name: "run" }`.
    const answerCard = document.querySelector('[data-tour="answer"]');
    expect(answerCard, "a full-screen run replaced the answer screen").not.toBeNull();

    // 3. The earlier turn is still here, collapsed, and ABOVE the run.
    const thread = screen.getByTestId("thread");
    expect(screen.getByTestId("previous-turn-0")).toHaveTextContent(FIRST_Q);
    expect(screen.getByTestId("previous-turn-0")).not.toHaveAttribute("open");
    expect(precedes(thread, guard), "the thread renders below the running turn").toBe(true);

    // 4. And the new question is the heading of the turn now running, so
    //    the progress is labelled by what it is working on rather than
    //    sitting under the previous question.
    const heading = screen.getByRole("heading", { name: SECOND_Q });
    expect(precedes(thread, heading)).toBe(true);
    expect(precedes(heading, guard)).toBe(true);
  });

  it("replaces the inline run with its answer in place, thread still above", async () => {
    openEventStreamMock
      .mockImplementationOnce(() => scripted(streamFor("t-1", "BRCA1 is a tumour suppressor")))
      .mockImplementation(() => scripted(streamFor("t-2", "It is linked to HBOC")));

    const user = userEvent.setup();
    render(<App />);
    await askFirst(user);

    /*
     * THE SAME DOM NODE, BEFORE AND AFTER. This is what makes this arm
     * able to fail, and the first draft of it could not.
     *
     * Asserting only that the second answer eventually appears with the
     * thread above it passes against the OLD behaviour too: the run screen
     * took over, the answer screen came back when the run landed, and the
     * end state is identical. What distinguishes them is whether the
     * screen ever left. React unmounts a component when the view switches
     * to another screen, and `App`'s fade wrapper is keyed on the view name
     * as well, so a trip through the run screen detaches this node and
     * mounts a new one. Holding the node and checking it is still the same
     * one is the direct test of "on the same screen".
     *
     * Verified by mutation: restoring `setSearchView({ name: "run" })` for
     * a continuation turns this line red while every other assertion in
     * this arm stays green.
     */
    const cardBefore = document.querySelector('[data-tour="answer"]');
    expect(cardBefore, "populate-check: no answer card to hold on to").not.toBeNull();

    await askFollowUp(user);

    // The second answer's own prose, which exists nowhere in the frontend
    // and can only come from the second run's token event.
    await screen.findByText(/It is linked to HBOC/, undefined, { timeout: 10000 });

    expect(
      document.querySelector('[data-tour="answer"]'),
      "the answer screen was unmounted and remounted, so the conversation left the page",
    ).toBe(cardBefore);

    // The progress is gone, replaced rather than pushed down.
    await waitFor(() => expect(screen.queryByTestId("step-Guard")).toBeNull());

    // The first turn is still here, still collapsed, still above.
    const thread = screen.getByTestId("thread");
    expect(screen.getByTestId("previous-turn-0")).toHaveTextContent(FIRST_Q);
    expect(precedes(thread, screen.getByTestId("claim-text-0"))).toBe(true);

    // And the follow-up field is back, so a third turn is possible.
    expect(screen.getByLabelText(/ask a follow-up question/i)).toBeInTheDocument();
  });

  it("still gives a question asked from the landing screen the full run screen", async () => {
    // The other side of the rule, and the reason `continuesThread` is a
    // parameter rather than inferred from "the answer screen is showing".
    // A first question starts a conversation, so there is nothing to keep
    // on screen and the full-screen run is still correct.
    openEventStreamMock.mockImplementation(neverLands);

    const user = userEvent.setup();
    render(<App />);
    const main = mainArea();
    await user.type(main.getByRole("textbox", { name: /question/i }), FIRST_Q);
    await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));

    await screen.findByTestId("step-Guard");
    expect(
      document.querySelector('[data-tour="answer"]'),
      "the first question rendered the answer screen instead of the run screen",
    ).toBeNull();
  });
});
