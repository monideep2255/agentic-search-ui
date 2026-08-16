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

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ApiError: actual.ApiError,
    login: vi.fn(),
    signup: vi.fn(),
    createRun: vi.fn(),
    openEventStream: vi.fn(),
    stopRun: vi.fn(),
    // T-4.10-08/09. Both real for build phase 4.10: an anonymous ask mints
    // a guest token, and sign-in fetches the caller's real allowance.
    mintGuest: vi.fn(),
    getAllowance: vi.fn(),
  };
});

import { createRun, getAllowance, login, mintGuest, openEventStream } from "./lib/api";

const loginMock = vi.mocked(login);
const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const mintGuestMock = vi.mocked(mintGuest);
const getAllowanceMock = vi.mocked(getAllowance);

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
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
}

describe("App", () => {
  beforeEach(() => {
    // Each clause below is written as a separate visitor arriving at a fresh
    // browser, and `lib/guestSession.ts` persists real state to
    // `localStorage` (the guest token since T-4.10-08, and the migrated
    // marker since the F-4.10-A-05 fix). jsdom keeps one storage for the
    // whole file, so without this the anonymous-ask clauses leak a guest
    // token into the sign-in clauses that follow them, and those in turn
    // leak a migrated marker into the anonymous clause at the end.
    //
    // This is isolation, not a relaxed assertion: it was already leaking
    // before this fix round and merely happened to be cleaned up as a side
    // effect of the sign-in handler clearing the token, which the product
    // owner's decision changed. `phase410Premise.test.tsx` has cleared
    // storage in its own `beforeEach` from the start, for the same reason.
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    // T-4.10-08/09: an anonymous ask mints a guest identity, and sign-in
    // fetches the caller's real allowance. Defaulted here so every test
    // that merely signs in or asks does not also have to think about
    // these two calls; a test that cares about the exact shape overrides
    // with its own `mockResolvedValueOnce`.
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
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

  it("leaves the landing when a signed-in user submits a question", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await ask(user, "Which diseases are associated with BRCA1?");

    // Asserted as the page HEADING rather than as loose text: the question now
    // legitimately appears twice, once as the run's heading and once in the
    // history rail. The heading role requires the run screen to have taken
    // over the page, not merely for the string to appear somewhere.
    expect(
      screen.getByRole("heading", { name: "Which diseases are associated with BRCA1?" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /ask a biomedical question/i }),
    ).not.toBeInTheDocument();
  });

  it("gives an anonymous visitor a real run, not the wall, on an ordinary ask", async () => {
    // INVERTED, build phase 4.10 (T-4.10-08). Before this phase, no backend
    // route existed for a caller with no account, so refusing outright with
    // the wall was the only honest option, and this test asserted exactly
    // that. `POST /auth/guest` and a guest bearer token on `/v1/query` are
    // now real, so an anonymous ask reaches a genuine run instead: the wall
    // is no longer shown merely because the visitor has no account (design
    // decision 5, `tracker/phase_4.10.md`), only when the SERVER refuses
    // with `guest_allowance_exhausted` (covered separately).
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "What is the capital of the USA?");

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "What is the capital of the USA?" }),
      "guest-token-1",
    );
    expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();
  });

  it("never shows an anonymous visitor a claim, a source or a trust signal", async () => {
    // The COUNTERFACTUAL for F-4.8-J-01, and the assertion whose absence let
    // it ship. Asserting the wall appears (the OLD mechanism) was never the
    // point; what matters, unchanged by build phase 4.10, is that no
    // fabricated answer content is EVER reachable without a real run's own
    // event stream behind it. `openEventStreamMock` is a promise that never
    // resolves (see `beforeEach`), so this run never lands and nothing it
    // would have produced can be on screen; `createRun` now legitimately
    // IS called, with the visitor's guest token, which is the new honest
    // mechanism this phase built, not a regression of this guarantee.
    const user = userEvent.setup();
    const { container } = render(<App />);

    await ask(user, "What is the capital of the USA?");

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("source-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^spine-segment-/)).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^citation-/)).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^trust-/)).not.toBeInTheDocument();
    // No NCBI record URL, and no grounding claim, may appear without a run.
    expect(container.textContent ?? "").not.toMatch(/ncbi\.nlm\.nih\.gov/i);
    expect(container.textContent ?? "").not.toMatch(/grounded/i);
  });

  it("does not leave the landing when the question is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(mainArea().getByRole("button", { name: /^search the knowledge graph$/i }));

    expect(
      screen.getByRole("heading", { name: /ask a biomedical question/i }),
    ).toBeInTheDocument();
  });

  it("returns to the landing from a run", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await ask(user, "test query");
    // EXACT, not /new search/i. The rail now carries the prototype's own
    // "+ New search" control, so the loose regex matches two buttons. The
    // screen's own control is the one this test means: it is asserting that
    // leaving a RUN returns to the landing.
    await user.click(screen.getByRole("button", { name: "New search" }));

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

  it("calls createRun for an anonymous visitor, using its minted guest token", async () => {
    // INVERTED, build phase 4.10 (T-4.10-08): the mirror image of "passes
    // the acquired token to createRun once a question is submitted" above,
    // for the anonymous path this phase adds. Before this phase an
    // anonymous question could not reach an authenticated endpoint at all,
    // because there was no token of any kind to send; the honest option was
    // to refuse. Now there is a real anonymous bearer token (a guest token,
    // minted lazily on this first ask), and it is that token, never the
    // absent access token, that reaches `createRun`.
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "Which diseases are associated with BRCA1?");

    await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Which diseases are associated with BRCA1?" }),
      "guest-token-1",
    );
  });
});
