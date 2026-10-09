/**
 * Card 109 fix round (F-109-V-01): the rail text for a row with no saved
 * answer, through the REAL `fetchHistory`. `App.test.tsx` mocks
 * `fetchHistory`, so it cannot see the validator drop `has_saved_answer:
 * false`. Here only `fetch` is stubbed.
 *
 * Mutation: `withValidatedOptionalFields` keeping the flag only when true
 * turns this red, because the row then reads "21 sources cited".
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
    createRun: vi.fn(),
    openEventStream: vi.fn(() => new Promise(() => {})),
    stopRun: vi.fn(),
    mintGuest: vi.fn(async () => ({ guest_id: "guest-1", used: 0, total: 5 })),
    getAllowance: vi.fn(async () => ({ kind: "user", used: 0, total: 100, counted: false })),
    fetchHistoryAnswer: vi.fn(),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));

describe("card 109: history rail text through the real fetchHistory", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("a row whose flag is false reads 'No answer saved', and the others keep their count", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            items: [
              { trace_id: "stopped-1", question: "Stopped question", citation_count: 21, has_saved_answer: false },
              { trace_id: "answered-1", question: "Answered question", citation_count: 21, has_saved_answer: true },
              { trace_id: "old-1", question: "Older api question", citation_count: 21 },
            ],
            count: 3,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(navArea().getByRole("button", { name: /log in/i }));
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));
    await mainArea().findByRole("textbox", { name: /question/i });

    const rail = await screen.findByTestId("history-rail");
    const row = (name: RegExp) => within(rail).getByRole("button", { name });
    await waitFor(() => expect(row(/stopped question/i).textContent).toMatch(/No answer saved/));
    expect(row(/stopped question/i).textContent).not.toMatch(/sources cited/i);
    expect(row(/^answered question/i).textContent).toMatch(/21 sources cited/i);
    expect(row(/older api/i).textContent).toMatch(/21 sources cited/i);
  });
});
