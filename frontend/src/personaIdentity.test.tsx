/**
 * The persona chip has exactly one writer before the first answer:
 * F-4.5-A-12's frontend half.
 *
 * WHAT THIS FILE EXERCISES, and what it does not.
 *
 * Exercised:
 *
 *   - `App` asks `fetchPersona` with the caller's bearer token, so the
 *     server can key the name on the account rather than on the client's
 *     session id. Before the fix the request was always anonymous and the
 *     landing chip named a different scientist than every answer.
 *   - `fetchMe`'s own `persona_name` never reaches the chip. That second
 *     writer, racing the first with no ordering and no cross-cancellation,
 *     is what made the displayed name depend on which HTTP response landed
 *     second.
 *   - Signing in re-asks with the new credential, so the chip follows the
 *     identity without a reload.
 *
 * NOT exercised:
 *
 *   - The server's own keying. That is asserted in
 *     `tests/system_03_search_agent/core/test_persona.py`, against the real
 *     handler. Here the api module is mocked, so these arms prove which
 *     value `App` adopts, never which value the server would have sent.
 *   - Real network timing. The race is closed by construction, one effect
 *     and one writer, rather than by a delay this suite tunes. Asserting on
 *     an instrumented delay would test the tuning, not the construction.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ApiError: actual.ApiError,
    fetchPersona: vi.fn(),
    fetchMe: vi.fn(),
    login: vi.fn(),
    signup: vi.fn(),
    createRun: vi.fn(),
    openEventStream: vi.fn(),
    stopRun: vi.fn(),
    mintGuest: vi.fn(),
    getAllowance: vi.fn(),
    // T-4.13-03: sign-in now also seeds the rail from `GET /v1/history`. An
    // api mock that omits an export App actually calls throws inside a
    // useEffect and takes the whole render down, the same reasoning this
    // mock's own `fetchPersona` line already exists for.
    fetchHistory: vi.fn(async () => ({ items: [], count: 0 })),
    // Fix set 4, R46 (decision U8): App now restores a session on load and
    // revokes the refresh token on log out. An api mock that omits an export
    // App actually calls throws inside a useEffect or a handler and takes
    // the render down, the same reasoning `fetchPersona` above already
    // carries.
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

import {
  createRun,
  fetchMe,
  fetchPersona,
  getAllowance,
  login,
  openEventStream,
} from "./lib/api";

const fetchPersonaMock = vi.mocked(fetchPersona);
const fetchMeMock = vi.mocked(fetchMe);
const loginMock = vi.mocked(login);
const getAllowanceMock = vi.mocked(getAllowance);
const openEventStreamMock = vi.mocked(openEventStream);
const createRunMock = vi.mocked(createRun);

const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));
const mainArea = () => within(screen.getByRole("main"));

/** Sign in through the real gate, the way a user does. */
async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
  await mainArea().findByRole("textbox", { name: /question/i });
}

describe("the persona chip has one writer", () => {
  beforeEach(() => {
    window.localStorage.clear();
    fetchPersonaMock.mockReset();
    fetchMeMock.mockReset();
    loginMock.mockReset();
    getAllowanceMock.mockReset();
    openEventStreamMock.mockReset();
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
  });

  it("asks for the persona anonymously before anyone signs in", async () => {
    // Pins: that the pre-answer chip comes from `GET /v1/persona` at all,
    // and that a visitor with no credential asks without one. If this arm
    // ever went green while the app drew a name locally, the whole file
    // would be measuring a fabrication.
    fetchPersonaMock.mockResolvedValue({ persona_name: "Franklin" });
    fetchMeMock.mockResolvedValue({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "Pauling",
    });

    render(<App />);

    await waitFor(() => expect(fetchPersonaMock).toHaveBeenCalled());
    expect(fetchPersonaMock.mock.calls[0][1]?.token ?? null).toBeNull();
    expect(await screen.findByTestId("persona-chip")).toHaveTextContent("Franklin");
  });

  it("asks again WITH the bearer token once the caller signs in", async () => {
    /**
     * Pins: `token` in the persona effect's dependency array and in the
     * `fetchPersona` options. F-4.5-J-12: the server keys the name on the
     * account when a credential is presented, so a client that never sends
     * one gets the session-keyed name on the landing screen and the
     * account-keyed name on every answer.
     *
     * The two mocked names are asserted BY NAME rather than by inequality.
     * "the chip changed after sign-in" would pass for a dozen unrelated
     * reasons; "the chip shows the value returned for the tokened request"
     * passes for one.
     */
    fetchPersonaMock.mockImplementation(async (_sessionId, options) =>
      options?.token != null
        ? { persona_name: "AccountKeyed" }
        : { persona_name: "SessionKeyed" },
    );
    fetchMeMock.mockResolvedValue({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "NeverShown",
    });

    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByTestId("persona-chip")).toHaveTextContent("SessionKeyed");

    await signIn(user);

    await waitFor(() =>
      expect(screen.getByTestId("persona-chip")).toHaveTextContent("AccountKeyed"),
    );
  });

  it("never adopts the persona name that /auth/me happens to carry", async () => {
    /**
     * Pins: the removal of `setPersona(me.persona_name)` from the `/auth/me`
     * effect. That was the second, unordered writer in F-4.5-A-12: two
     * effects, one keyed on the session and one on the token, both writing
     * one piece of state, with nothing sequencing them and nothing
     * cancelling one when the other resolved. The chip showed whichever
     * response landed second.
     *
     * `fetchMe` deliberately returns a name no other source returns, so the
     * assertion can name the exact string that must never appear rather than
     * asserting that two values happened to agree.
     */
    fetchPersonaMock.mockResolvedValue({ persona_name: "AccountKeyed" });
    fetchMeMock.mockResolvedValue({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "deep_technical",
      persona_name: "TheRacingName",
    });

    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    // `/auth/me` really did run and really did deliver its payload: the
    // depth control adopted the account's stored value. So this arm is not
    // passing merely because the request never happened.
    //
    // UI fix set 9: the control offers two modes, and a stored
    // `deep_technical` lights the Researcher button (`displayedMode`). The
    // default is Plain language, so Researcher pressed still proves delivery.
    await waitFor(() => expect(fetchMeMock).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /^researcher$/i }),
      ).toHaveAttribute("aria-pressed", "true"),
    );

    expect(screen.getByTestId("persona-chip")).toHaveTextContent("AccountKeyed");
    expect(screen.getByTestId("persona-chip")).not.toHaveTextContent("TheRacingName");
  });
});

describe("the depth control starts where the account left it", () => {
  /**
   * T-4.5-08 and Section 14.5, "once auth is live, depth defaults to the
   * user's last-used value", asserted on the control a person actually sees.
   *
   * Pins: `HomeScreen`'s `depth` / `onDepthChange` props and App passing
   * them. Found while fixing F-4.5-J-15's server half: `HomeScreen` owned its
   * own depth in local state seeded from the literal "researcher", App had
   * been reading the account's stored value from `GET /auth/me` since build
   * phase 4.5, and the two were different pieces of state. A returning caller
   * whose account said `deep_technical` was shown `researcher`, and the first
   * question they asked went out at `researcher`.
   *
   * Three things are asserted, not two, and the third was added because a
   * mutation exposed the arm without it. Seeding the display without seeding
   * the request would be the more dangerous half-fix, so the value the next
   * question carries is asserted as well as the control. And lifting the
   * state to a parent that never sends a change back down would freeze the
   * control at the seeded value, which is the failure a controlled component
   * with no `onChange` always has; a mutation dropping `onDepthChange` left
   * the first two assertions green, so the arm now also changes the depth by
   * hand and asserts BOTH halves again.
   */
  beforeEach(() => {
    window.localStorage.clear();
    fetchPersonaMock.mockReset();
    fetchMeMock.mockReset();
    loginMock.mockReset();
    getAllowanceMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    fetchPersonaMock.mockResolvedValue({ persona_name: "Franklin" });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Franklin" });
  });

  /*
   * UI fix set 9 changed the control from three depths to two modes, Plain
   * language (the default) and Researcher. These two arms keep every property
   * they pinned and move the stored value to `researcher`, the one value that
   * differs from the new default, so a pressed button still proves the seed
   * rather than the default.
   */
  it("shows the account's stored depth and sends it on the next question", async () => {
    fetchMeMock.mockResolvedValue({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "Franklin",
    });

    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^researcher$/i })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );

    await user.type(
      mainArea().getByRole("textbox", { name: /question/i }),
      "Which diseases are associated with BRCA1?",
    );
    await user.click(
      mainArea().getByRole("button", { name: /^search the knowledge graph$/i }),
    );

    await waitFor(() => expect(createRunMock).toHaveBeenCalled());
    expect(createRunMock.mock.calls[0][0].audience_depth).toBe("researcher");
  });

  it("stays changeable after it has been seeded", async () => {
    fetchMeMock.mockResolvedValue({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "Franklin",
    });

    const user = userEvent.setup();
    render(<App />);
    await signIn(user);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^researcher$/i })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );

    await user.click(screen.getByRole("button", { name: /plain language/i }));

    expect(screen.getByRole("button", { name: /plain language/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.type(
      mainArea().getByRole("textbox", { name: /question/i }),
      "Which diseases are associated with BRCA1?",
    );
    await user.click(
      mainArea().getByRole("button", { name: /^search the knowledge graph$/i }),
    );

    await waitFor(() => expect(createRunMock).toHaveBeenCalled());
    expect(createRunMock.mock.calls[0][0].audience_depth).toBe("plain_language");
  });
});
