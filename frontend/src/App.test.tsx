/**
 * App-level routing.
 *
 * REWRITTEN in build phase 4.8 for a deliberately changed contract, not
 * weakened to make new code pass.
 *
 * What changed and why: build phase 1.2 rendered `AuthGate` and nothing else
 * until a token resolved, so a visitor without an account could not see the
 * product at all. The approved design for build phase 4.8 makes the landing
 * screen the entry point, with a free allowance before sign-in is required.
 * That inverts the first assertion in this file, and only that one.
 *
 * Every other guarantee this suite held is preserved, because none of them
 * stopped being true:
 *
 *   - a non-empty question navigates away from the landing
 *   - an empty question does not
 *   - leaving a run returns to the landing
 *   - signing in still works through the real AuthGate
 *   - a signed-in question still reaches createRun WITH ITS BEARER TOKEN
 *
 * That last one is the load-bearing one. The first version of phase 4.8's
 * assembly dropped `createRun` entirely in favour of a demo timeline, and every
 * screen still rendered, so a suite that had lost this assertion would have
 * certified an interface wired to nothing.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

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

const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));

/** Sign in through the real gate, the way a user does. */
async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
  await mainArea().findByRole("textbox", { name: /question/i });
}

/** Ask a question from the landing screen. */
async function ask(user: ReturnType<typeof userEvent.setup>, question: string) {
  const main = mainArea();
  await user.type(main.getByRole("textbox", { name: /question/i }), question);
  await user.click(main.getByRole("button", { name: /^ask$/i }));
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
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
  });

  it("shows the landing screen to a visitor with no account", () => {
    // INVERTED from the phase 1.2 contract, deliberately. The old assertion
    // was that the sign-in gate came first; the approved design makes the
    // landing the entry point. Both halves are asserted so this cannot pass
    // against a blank page.
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /ask a biomedical question/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("reaches the sign-in gate from the app bar", () => {
    render(<App />);
    expect(navArea().getByRole("button", { name: /log in/i })).toBeInTheDocument();
  });

  it("signs in through the real gate and returns to the landing", async () => {
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);

    expect(mainArea().getByRole("textbox", { name: /question/i })).toBeInTheDocument();
    // The bar must stop offering "Log in" once signed in, otherwise the page
    // carries two controls with the same accessible name.
    expect(navArea().queryByRole("button", { name: /^log in$/i })).not.toBeInTheDocument();
  });

  it("leaves the landing when a non-empty question is submitted", async () => {
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "Which diseases are associated with BRCA1?");

    // Asserted as the page HEADING rather than as loose text. The question now
    // legitimately appears twice, once as the run's heading and once in the
    // history rail, so a bare text match is ambiguous. The heading role is the
    // stricter assertion: it requires the run screen to have taken over the
    // page, not merely for the string to appear somewhere.
    expect(
      screen.getByRole("heading", { name: "Which diseases are associated with BRCA1?" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /ask a biomedical question/i }),
    ).not.toBeInTheDocument();
  });

  it("does not leave the landing when the question is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(mainArea().getByRole("button", { name: /^ask$/i }));

    expect(
      screen.getByRole("heading", { name: /ask a biomedical question/i }),
    ).toBeInTheDocument();
  });

  it("returns to the landing from a run", async () => {
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "test query");
    await user.click(screen.getByRole("button", { name: /new search/i }));

    expect(
      screen.getByRole("heading", { name: /ask a biomedical question/i }),
    ).toBeInTheDocument();
  });

  it("passes the acquired token to createRun once a question is submitted", async () => {
    // The guarantee that must survive the routing change. Phase 4.8's first
    // assembly dropped createRun for a demo timeline and every screen still
    // rendered, so losing this assertion would certify a disconnected app.
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);
    await ask(user, "Which diseases are associated with BRCA1?");

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Which diseases are associated with BRCA1?" }),
      "test-token",
    );
  });

  it("does not call createRun for an anonymous visitor, who has no token", async () => {
    // The honest consequence of an open landing: an anonymous question cannot
    // reach an authenticated endpoint. The allowance that will govern this is
    // build phase 6.0's, and the surface is declared in stubs/registry.ts.
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "Which diseases are associated with BRCA1?");

    expect(createRunMock).not.toHaveBeenCalled();
  });
});
