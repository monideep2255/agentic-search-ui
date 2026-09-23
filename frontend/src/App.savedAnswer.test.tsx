/**
 * Item 10.2, overnight run 2026-09-22/23: opening a history item.
 *
 * `App.test.tsx` already covers the rail's own seeding and de-duplication.
 * This file covers what `onOpen` does with a click once a row can carry
 * `has_saved_answer`: the saved answer renders with no new search, Run
 * again still performs one, and every way the saved path can fail to
 * deliver a real answer falls back to exactly today's re-ask, unchanged.
 *
 * Same mocking approach as `App.test.tsx`, for the same reason: this suite
 * needs precise control over what each network call returns and, for the
 * "no new search" assertion, precise knowledge of whether `createRun` was
 * ever called at all.
 *
 * Every test states, in a comment, the mutation it is proven to catch.
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
    mintGuest: vi.fn(async () => ({ guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5 })),
    getAllowance: vi.fn(),
    fetchHistory: vi.fn(),
    fetchHistoryAnswer: vi.fn(),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

import {
  createRun,
  fetchHistory,
  fetchHistoryAnswer,
  getAllowance,
  login,
  openEventStream,
} from "./lib/api";

const loginMock = vi.mocked(login);
const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const fetchHistoryMock = vi.mocked(fetchHistory);
const fetchHistoryAnswerMock = vi.mocked(fetchHistoryAnswer);
const getAllowanceMock = vi.mocked(getAllowance);

const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
  await mainArea().findByRole("textbox", { name: /question/i });
}

const SAVED_ANSWER = {
  trace_id: "row-1",
  question: "What is BRCA1?",
  asked_at: "2026-09-20T10:00:00Z",
  depth: "plain_language",
  answer_markdown: "BRCA1 is a gene associated with hereditary breast cancer.",
  citations: [],
  trust_signal: "Grounded, every claim cited",
  trust_line: null,
};

describe("App: opening a history item (item 10.2)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    fetchHistoryMock.mockReset();
    fetchHistoryAnswerMock.mockReset();
    getAllowanceMock.mockReset();
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    // Never resolves, so a run this file accidentally starts never lands
    // and cannot be mistaken for the saved-answer path landing instead.
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
  });

  it("renders the saved answer at once and starts no new search", async () => {
    // Mutation: `onOpen` calling `ask` unconditionally, the way it did
    // before this ticket, turns this red: `createRun` would be called even
    // though `has_saved_answer` is true and the fetch succeeds.
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?", has_saved_answer: true }],
      count: 1,
    });
    fetchHistoryAnswerMock.mockResolvedValue(SAVED_ANSWER);
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /what is brca1\?/i }));

    expect(
      await screen.findByText("BRCA1 is a gene associated with hereditary breast cancer."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("saved-answer-marker")).toBeInTheDocument();
    expect(createRunMock).not.toHaveBeenCalled();
  });

  it("falls back to asking when the row carries no saved answer", async () => {
    // Mutation: gating the fallback on the wrong flag, or fetching the
    // saved-answer endpoint anyway when `has_saved_answer` is not true,
    // turns this red.
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?" }],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /what is brca1\?/i }));

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock.mock.calls[0][0]).toMatchObject({ text: "What is BRCA1?" });
    expect(fetchHistoryAnswerMock).not.toHaveBeenCalled();
  });

  it("falls back to asking, exactly today's behaviour, when the saved-answer fetch fails", async () => {
    // Mutation: leaving the saved-answer screen showing its loading state
    // forever on a failed fetch, instead of re-asking, turns this red.
    // This is done-when item 3: nobody loses a working control because a
    // new one is absent.
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?", has_saved_answer: true }],
      count: 1,
    });
    fetchHistoryAnswerMock.mockRejectedValue(new Error("fetchHistoryAnswer failed with 404"));
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /what is brca1\?/i }));

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock.mock.calls[0][0]).toMatchObject({ text: "What is BRCA1?" });
    expect(screen.queryByTestId("saved-answer-body")).not.toBeInTheDocument();
  });

  it("Run again beside the saved answer performs a fresh search", async () => {
    // Mutation: wiring Run again to do nothing, or to re-show the same
    // saved answer instead of calling `createRun`, turns this red.
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?", has_saved_answer: true }],
      count: 1,
    });
    fetchHistoryAnswerMock.mockResolvedValue(SAVED_ANSWER);
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /what is brca1\?/i }));
    await screen.findByText("BRCA1 is a gene associated with hereditary breast cancer.");

    await user.click(screen.getByRole("button", { name: /run this search again/i }));

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock.mock.calls[0][0]).toMatchObject({ text: "What is BRCA1?" });
  });
});
