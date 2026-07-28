import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

// T-1.2-08 put a real `AuthGate` in front of the home/chat switch this
// suite already exercised, so every scenario below now signs in first.
// `lib/api.ts` is mocked at the module level, the same convention
// `StopButton.test.tsx` established, so this suite never makes a real
// network call for `login`, `createRun`, or `openEventStream`.
vi.mock("./lib/api", () => ({
  login: vi.fn(),
  signup: vi.fn(),
  createRun: vi.fn(),
  openEventStream: vi.fn(),
  stopRun: vi.fn(),
}));

import { createRun, login, openEventStream } from "./lib/api";

const loginMock = vi.mocked(login);
const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: /ask the agent a biomedical question/i }),
    ).toBeInTheDocument();
  });
}

describe("App", () => {
  beforeEach(() => {
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    // Never resolves within these tests: this suite covers sign-in and
    // page-level navigation, not the streaming pipeline itself (that is
    // `ChatPage.test.tsx` and `useAgentRun.test.ts`'s job).
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
  });

  it("shows the sign-in gate before the home page on initial render", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /ask the agent a biomedical question/i }),
    ).not.toBeInTheDocument();
  });

  it("renders the home page (EmptyState + QueryInput) after signing in", async () => {
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);

    expect(
      screen.getByRole("heading", { name: /ask the agent a biomedical question/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/ask a question/i)).toBeInTheDocument();
  });

  it("navigates to the chat page when a non-empty query is submitted", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const input = screen.getByLabelText(/ask a question/i);
    await user.type(input, "What genes are linked to BRCA1?");
    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(
      screen.getByText("What genes are linked to BRCA1?"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("does not navigate when the query is empty", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(
      screen.getByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();
  });

  it("returns to the home page when the chat page's exit button is clicked", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await user.type(
      screen.getByLabelText(/ask a question/i),
      "test query{Enter}",
    );
    await user.click(screen.getByRole("button", { name: /back to search/i }));

    expect(
      screen.getByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();
  });

  it("passes the acquired token down to createRun once a query is submitted", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await user.type(
      screen.getByLabelText(/ask a question/i),
      "What genes are linked to BRCA1?{Enter}",
    );

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "What genes are linked to BRCA1?" }),
      "test-token",
    );
  });
});
