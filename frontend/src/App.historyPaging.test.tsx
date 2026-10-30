/**
 * Card 136.1: "Your searches" reaches past the latest 20.
 *
 * What the person gets: with more than 20 searches, "Show older searches" at
 * the foot of the list loads the next older ones, as many times as there are
 * any; the control goes when there are none left; and a new search goes on
 * top without making the older ones they loaded disappear.
 *
 * Through the REAL `fetchHistory`, with only `fetch` stubbed, as
 * `App.historyNoAnswer.test.tsx` does: the stub reads `before` off the URL
 * and serves the page a keyset server would, so the cursor the app sends and
 * the `has_more` it reads are the ones a real response carries.
 *
 * Mutations, each measured red then restored (build_s4.md lists them):
 * - the rail ignoring `hasOlder` (always rendering the control): the
 *   "exactly 20" arm goes red;
 * - `showOlderSearches` not passing `before`: the first arm goes red at the
 *   second page;
 * - not setting `historyPagedOlder` (so a re-ask trims to 20 again): the
 *   "new ask" arm goes red;
 * - the trim no longer turning the control on: the "trimmed row" arm goes red.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
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
    createRun: vi.fn(async () => ({ run_id: "run-136", persona_name: "Mendel" })),
    openEventStream: vi.fn(() => new Promise(() => {})),
    stopRun: vi.fn(),
    mintGuest: vi.fn(async () => ({ guest_id: "guest-1", used: 0, total: 5 })),
    getAllowance: vi.fn(async () => ({ kind: "user", used: 0, total: 100, counted: false })),
    fetchHistoryAnswer: vi.fn(),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

const PAGE = 20;
const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));
const rail = () => within(screen.getByTestId("history-rail"));
const rowTexts = () =>
  rail()
    .getAllByRole("button")
    // The question is the row's first span; the second is its meta line.
    .map((button) => button.querySelector("span")?.textContent ?? "")
    .filter((text) => text.startsWith("Past question") || text.startsWith("A brand new question"));
const showOlder = () => rail().queryByRole("button", { name: /show older searches/i });

/** `count` stored searches, newest first, named so their order is readable. */
function serverRows(count: number) {
  return Array.from({ length: count }, (_, n) => ({
    trace_id: `t-${n}`,
    question: `Past question ${n}`,
    asked_at: "2026-10-20T10:00:00Z",
    citation_count: 2,
    has_saved_answer: true,
  }));
}

type Stub = { befores: (string | null)[]; failNext: boolean };

/** A keyset server over `rows`: the page after `before`, and `has_more`. */
function stubServer(rows: ReturnType<typeof serverRows>): Stub {
  const stub: Stub = { befores: [], failNext: false };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://localhost");
      if (!url.pathname.endsWith("/v1/history")) return new Response("{}", { status: 404 });
      const before = url.searchParams.get("before");
      stub.befores.push(before);
      if (stub.failNext) {
        stub.failNext = false;
        return new Response(JSON.stringify({ detail: "down" }), { status: 503 });
      }
      const start = before === null ? 0 : rows.findIndex((row) => row.trace_id === before) + 1;
      const rest = before !== null && start === 0 ? [] : rows.slice(start);
      const items = rest.slice(0, PAGE);
      return new Response(
        JSON.stringify({ items, count: items.length, omitted_count: 0, has_more: rest.length > PAGE }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  return stub;
}

async function signIn(): Promise<ReturnType<typeof userEvent.setup>> {
  const user = userEvent.setup();
  render(<App />);
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await mainArea().findByRole("textbox", { name: /question/i });
  await screen.findByTestId("history-rail");
  return user;
}

const expectedRows = (from: number, to: number) =>
  Array.from({ length: to - from }, (_, n) => `Past question ${from + n}`);

describe("card 136.1: Show older searches", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads older pages until there are none left, then the control goes", async () => {
    const stub = stubServer(serverRows(45));
    const user = await signIn();
    await waitFor(() => expect(rowTexts()).toEqual(expectedRows(0, 20)));
    expect(showOlder(), "45 searches, 20 shown: the control must be there").not.toBeNull();

    await user.click(showOlder()!);
    await waitFor(() => expect(rowTexts()).toEqual(expectedRows(0, 40)));
    expect(stub.befores.at(-1)).toBe("t-19");
    expect(showOlder()).not.toBeNull();

    await user.click(showOlder()!);
    await waitFor(() => expect(rowTexts()).toEqual(expectedRows(0, 45)));
    expect(stub.befores.at(-1)).toBe("t-39");
    expect(showOlder(), "no older searches left: the control must go").toBeNull();
  });

  it("with exactly 20 searches there is no control", async () => {
    stubServer(serverRows(20));
    await signIn();
    await waitFor(() => expect(rowTexts()).toEqual(expectedRows(0, 20)));
    expect(showOlder()).toBeNull();
  });

  it("a new ask goes on top and keeps every older row already loaded", async () => {
    stubServer(serverRows(45));
    const user = await signIn();
    await waitFor(() => expect(rowTexts()).toHaveLength(20));
    await user.click(showOlder()!);
    await waitFor(() => expect(rowTexts()).toHaveLength(40));

    await user.type(mainArea().getByRole("textbox", { name: /question/i }), "A brand new question");
    await user.click(mainArea().getByRole("button", { name: /^search the knowledge graph$/i }));

    await waitFor(() => expect(rowTexts()[0]).toBe("A brand new question"));
    expect(rowTexts().slice(1), "an older row the person loaded disappeared").toEqual(expectedRows(0, 40));
    expect(showOlder()).not.toBeNull();
  });

  it("a row the first page's trim drops stays reachable through the control", async () => {
    const stub = stubServer(serverRows(20));
    const user = await signIn();
    await waitFor(() => expect(rowTexts()).toHaveLength(20));
    expect(showOlder()).toBeNull();

    await user.type(mainArea().getByRole("textbox", { name: /question/i }), "A brand new question");
    await user.click(mainArea().getByRole("button", { name: /^search the knowledge graph$/i }));
    await waitFor(() => expect(rowTexts()[0]).toBe("A brand new question"));
    expect(rowTexts()).not.toContain("Past question 19");
    expect(showOlder(), "the trimmed row must stay reachable").not.toBeNull();

    await user.click(showOlder()!);
    await waitFor(() => expect(rowTexts().at(-1)).toBe("Past question 19"));
    expect(stub.befores.at(-1)).toBe("t-18");
    expect(showOlder()).toBeNull();
  });

  it("a failed load says so and keeps the control, and a retry loads the page", async () => {
    const stub = stubServer(serverRows(25));
    const user = await signIn();
    await waitFor(() => expect(rowTexts()).toHaveLength(20));

    stub.failNext = true;
    await user.click(showOlder()!);
    expect(await rail().findByText(/older searches did not load/i)).toBeInTheDocument();
    expect(rowTexts()).toHaveLength(20);
    expect(showOlder()).not.toBeNull();

    await user.click(showOlder()!);
    await waitFor(() => expect(rowTexts()).toEqual(expectedRows(0, 25)));
    expect(rail().queryByText(/older searches did not load/i)).toBeNull();
    expect(showOlder()).toBeNull();
  });
});
