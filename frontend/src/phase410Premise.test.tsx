/**
 * Build phase 4.10 frontend premise gate: the anonymous run path and the
 * guest allowance, `App.tsx`'s side (T-4.10-08 and T-4.10-09).
 *
 * The backend half of this phase has its own premise gate
 * (`tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py`)
 * and is done: 17 of 17 green. This file is the frontend's own coverage of
 * the same premise, from `tracker/phase_4.10.md`:
 *
 *   A caller the server has never seen can complete five real, cited runs
 *   without an account, the server alone decides when the fifth is spent,
 *   and no guest can read, stop, or spend another caller's runs.
 *
 * The backend gate covers admission, isolation and atomicity against the
 * real API. This file covers what only the UI can be wrong about: that the
 * client asks for a guest identity lazily rather than eagerly, sends the
 * SERVER's own token and count rather than a client guess, shows the wall
 * on the one refusal that means it and never on the other, and that no
 * fabricated or leaked surface (an anonymous stored-searches rail, a false
 * "unlimited searches" line) survives the change.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      lazy minting (not on mount), reuse of a token persisted
 *                   from a prior visit, the dots reading `GET /v1/allowance`
 *                   rather than a local counter, the wall appearing on a 403
 *                   `guest_allowance_exhausted` and NOT on a 429
 *                   `concurrent_run_cap_exceeded`, F-4.8-P-04's non-regression
 *                   (no rail for an anonymous visitor, asserted after an ask,
 *                   not merely before one), `guest_token` reaching
 *                   `signup`/`login` when a guest session is held and being
 *                   absent when it is not, and the account menu and rail
 *                   footer stating the identical real limit from the same
 *                   fetch.
 *
 *                   Added in fix round 1: that signing out does NOT hand
 *                   out a fresh five-search allowance (F-4.10-A-05), in both
 *                   directions, a migrated identity is walled and a visitor
 *                   who never had one is still admitted; that the marker
 *                   carrying that fact survives a reload; that a 401 naming
 *                   a revoked session walls while an ordinary expired-token
 *                   401 still mints; that both limit surfaces state the true
 *                   copy and neither names an unenforced cap (F-4.10-A-06);
 *                   and that the sign-in wall makes no claim about carrying
 *                   searches across sign-in (F-4.10-A-07).
 *
 *                   Added in fix round 2 (F-4.10-R-02): that the wall says
 *                   something TRUE on each of its three triggers, not one
 *                   sentence written for the first of them. The exhausted
 *                   allowance keeps "you have used your free searches"; a
 *                   migrated browser and a visitor at the attempt ceiling
 *                   (F-4.10-R-01) each get their own, and neither claims a
 *                   search was used. Both arms: the negative assertions
 *                   alone would be satisfied by deleting the sentence, so a
 *                   third clause requires the original wording to survive
 *                   where it is true. The two clauses that DRIVE a migrated
 *                   browser now read the copy as well as the testid, which
 *                   is the specific gap that let the false sentence ship.
 *                   Set 1 (2026-09-12, `testing/UI_fix_plan.md`) REMOVED the
 *                   allowance, its dots and every sign-in wall. The clauses
 *                   that pinned them are replaced: no dots or count render,
 *                   a shared daily cap is stated in words, a migrated or
 *                   revoked browser mints a fresh identity rather than being
 *                   walled, Log out lands on the search home page, and the
 *                   guest token reaches signup or login under one Log in.
 *   NOT exercised:  the wall's copy against a server that refuses with a
 *                   reason string this client does not know; an unknown
 *                   `reason` reaches `setDispatchError` rather than the
 *                   wall, which is `App.tsx`'s existing fall-through. Also
 *                   the backend's own admission, isolation, atomicity and
 *                   token-domain-separation guarantees (the backend premise
 *                   gate's job, already green); real network behaviour
 *                   (`lib/api.ts`'s functions are mocked throughout); colour
 *                   contrast and any other WCAG 2.1 AA concern (the
 *                   accessibility suite's); visual position and geometry
 *                   (`e2e/`'s).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ApiError: actual.ApiError,
    // T-4.5-10 added `fetchPersona`, which App calls once at load so the
    // shell's persona chip has a real name before the first question. Stubbed
    // rather than left out: an api mock that omits an export App actually
    // calls throws inside a useEffect and takes the whole render down.
    fetchPersona: vi.fn(async () => ({ persona_name: "Mendel" })),
    // T-4.5-08: App reads the account's last-used depth on sign-in.
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
    // T-4.13-03: sign-in now also seeds the rail from `GET /v1/history`. An
    // api mock that omits an export App actually calls throws inside a
    // useEffect and takes the whole render down, the same reasoning
    // `fetchPersona`'s own comment above already gives.
    fetchHistory: vi.fn(async () => ({ items: [], count: 0 })),
  };
});

import { ApiError, createRun, getAllowance, login, mintGuest, openEventStream, signup } from "./lib/api";

const loginMock = vi.mocked(login);
const signupMock = vi.mocked(signup);
const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const mintGuestMock = vi.mocked(mintGuest);
const getAllowanceMock = vi.mocked(getAllowance);

const GUEST_TOKEN_STORAGE_KEY = "agentic-search-ui.guest-token.v1";

const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));

async function ask(user: ReturnType<typeof userEvent.setup>, question: string) {
  const main = mainArea();
  await user.type(main.getByRole("textbox", { name: /question/i }), question);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
}

/** Signs in through the real gate, from the nav bar's "Log in" action. */
async function signInFromNav(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
}

describe("build phase 4.10: the anonymous run path and the guest allowance", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    signupMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    // A run that never lands, matching every other App-level suite in this
    // repo: what is under test here is admission and the allowance, never
    // an answer, so nothing that would require the stream to resolve is
    // asserted against.
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
  });

  describe("minting: lazy, persisted, reused", () => {
    it("does not mint a guest token merely from mounting the app", () => {
      render(<App />);
      expect(mintGuestMock).not.toHaveBeenCalled();
    });

    it("mints a guest token on the first question an anonymous visitor actually asks", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
      expect(createRunMock).toHaveBeenCalledWith(
        expect.objectContaining({ text: "What gene is BRCA1?" }),
        "guest-token-1",
      );
    });

    it("reuses a guest token persisted from a prior visit, rather than minting a fresh one", async () => {
      // Design decision 1 (`tracker/phase_4.10.md`): the token is clearable,
      // and clearing it on purpose is how a fresh allowance is obtained, but
      // an ORDINARY reload must not do that by accident. Seeding storage
      // before `render` simulates exactly that reload.
      window.localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, "persisted-token");
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue({ kind: "guest", used: 3, total: 5, counted: true });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
      expect(createRunMock).toHaveBeenCalledWith(
        expect.objectContaining({ text: "What gene is BRCA1?" }),
        "persisted-token",
      );
      expect(mintGuestMock).not.toHaveBeenCalled();
    });
  });

  describe("set 1: no guest allowance on screen", () => {
    /**
     * Set 1, R1 and R2 (2026-09-12, `testing/UI_fix_plan.md`): the
     * five-search allowance and its dots are gone. This replaces the build
     * phase 4.10 clauses that pinned the dots to the server's count, because
     * the requirement they pinned was removed, not because they failed.
     */
    it("shows no dots and no search count to a guest, after an ask and back on the landing", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue({ kind: "guest", used: 3, total: 5, counted: true });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(getAllowanceMock).toHaveBeenCalledWith("guest-token-1"));
      await user.click(screen.getByRole("button", { name: "New search" }));

      await screen.findByRole("textbox", { name: /question/i });
      expect(screen.queryByTestId("guest-allowance")).not.toBeInTheDocument();
      expect(screen.queryByText(/\d+ searches? left/i)).not.toBeInTheDocument();
    });

    /**
     * The shared daily caps still exist (R4), so when the server reports one
     * as reached the landing says so in words. Each reason keeps its own
     * sentence, since one means the product is paused for everyone and the
     * other means only this network has had its share.
     */
    it.each([
      ["anon_daily_cap_reached", /guest searches are paused for today/i],
      ["anon_source_daily_cap_reached", /this network has used its guest searches for today/i],
    ] as const)(
      "states the daily cap in words when the server reports blocked_reason %s",
      async (reason, expectedCopy) => {
        mintGuestMock.mockResolvedValue({
          guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
        });
        createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
        getAllowanceMock.mockResolvedValue({
          kind: "guest", used: 0, total: 5, counted: true, blocked_reason: reason,
        });
        const user = userEvent.setup();
        render(<App />);

        await ask(user, "What gene is BRCA1?");
        await waitFor(() => expect(getAllowanceMock).toHaveBeenCalledWith("guest-token-1"));
        await user.click(screen.getByRole("button", { name: "New search" }));

        expect(await screen.findByText(expectedCopy)).toBeInTheDocument();
        expect(screen.queryByTestId("guest-allowance")).not.toBeInTheDocument();
      },
    );
  });

  describe("a transient refusal is an error on the answer screen, never a wall", () => {
    it("shows the failure banner on a 429 concurrent-run-cap refusal", async () => {
      // design decision 5: a 429 here is `concurrent_run_cap_exceeded`
      // (F-4.0-A-10), which is genuinely transient (finishing or stopping a
      // run frees a slot).
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockRejectedValueOnce(
        new ApiError(
          429,
          "createRun failed with 429: you already have the maximum number of runs in flight",
          "concurrent_run_cap_exceeded",
        ),
      );
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      const failure = await screen.findByTestId("answer-failure");
      expect(failure).toBeInTheDocument();
      expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();
    });
  });

  describe("F-4.8-P-04 does not regress", () => {
    it("gives an anonymous visitor no stored-searches rail, even after a real ask", async () => {
      // This is the exact branch T-4.10-08 changes (the `if (!signedIn)`
      // intercept in `ask`), so the non-regression is asserted AFTER an
      // ask, not only on the bare landing screen the way the original
      // F-4.8-P-04 fix's own test (`railCollapsePremise.test.tsx`) does.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));

      expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
      expect(screen.queryByTestId("collapsed-rail")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /show or hide your searches/i }),
      ).not.toBeInTheDocument();
    });
  });

  describe("migration: the held guest token reaches the account", () => {
    it("sends the guest token to signup when Log in creates a new account, and not again to login", async () => {
      // Set 1, R5: one Log in button that tries signup first. Signup
      // migrates and revokes the guest session when it creates the account,
      // so the token goes to signup only.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 1, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
      signupMock.mockResolvedValue({ id: "user-1", email: "person@example.com" });
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));

      await signInFromNav(user);

      await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
      expect(signupMock).toHaveBeenCalledWith(
        expect.objectContaining({ guest_token: "guest-token-1" }),
      );
      expect(loginMock.mock.calls[0][0]).not.toHaveProperty("guest_token");
    });

    it("sends the guest token to login when the email is already registered", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 1, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
      signupMock.mockRejectedValue(new ApiError(409, "signup failed with 409"));
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));

      await signInFromNav(user);

      await waitFor(() =>
        expect(loginMock).toHaveBeenCalledWith(
          expect.objectContaining({ guest_token: "guest-token-1" }),
        ),
      );
    });

    it("omits guest_token entirely for a visitor who never held a guest session", async () => {
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
      const user = userEvent.setup();
      render(<App />);

      await signInFromNav(user);

      await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
      expect(loginMock.mock.calls[0][0]).not.toHaveProperty("guest_token");
    });
  });

  describe("the account menu and the rail footer state the identical real limit", () => {
    it("read it from the same GET /v1/allowance fetch, not two hardcoded copies", async () => {
      // F-4.9-A-16, closed by T-4.10-09, then corrected by F-4.10-A-06.
      //
      // Both surfaces used to be a hardcoded, false "unlimited searches".
      // T-4.10-09 replaced that with "up to 100 searches a day", which is
      // false in the opposite direction: the 100/day cap counts rows in
      // `interactions` and nothing writes that table (F-2.0-04), so it
      // cannot fire. `counted: false` is the server saying exactly that, and
      // the client used to read the field and then state the number anyway.
      //
      // The guarantee is unchanged: both surfaces state the SAME thing from
      // the SAME fetch, or one of the two is lying. It is now checked
      // against the true copy, and with an added negative on each surface so
      // a regression back to naming an unenforced cap fails rather than
      // passing.
      getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      await signInFromNav(user);
      await ask(user, "What gene is BRCA1?");
      await screen.findByTestId("history-rail");

      await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
      const menu = screen.getByRole("menu");
      await waitFor(() =>
        expect(within(menu).getByText(/no search limit in effect yet/i)).toBeInTheDocument(),
      );
      expect(within(menu).queryByText(/100 searches/i)).not.toBeInTheDocument();
      expect(within(menu).queryByText(/unlimited searches/i)).not.toBeInTheDocument();

      const rail = screen.getByTestId("history-rail");
      expect(within(rail).getByText(/no search limit in effect yet/i)).toBeInTheDocument();
      expect(within(rail).queryByText(/100 searches/i)).not.toBeInTheDocument();
    });
  });

  describe("set 1: logging out returns this browser to an ordinary guest", () => {
    /**
     * Set 1, R1 to R3 and R6 (2026-09-12, `testing/UI_fix_plan.md`). The
     * build phase 4.10 clauses here walled a browser whose guest identity had
     * been moved into an account (F-4.10-A-05), and pinned the wall's copy on
     * each trigger (F-4.10-A-07, F-4.10-R-02). The product owner removed the
     * allowance and every wall, so those clauses are replaced by their
     * opposite: a migrated browser is admitted and mints a fresh identity.
     * What bounds anonymous spend now is the server's daily cap and
     * per-connection share, asserted in the backend premise gate.
     */
    const signedInAllowance = { kind: "user" as const, used: 0, total: 100, counted: false };

    it("mints a fresh identity for a migrated browser after Log out, and lands on the search home page", async () => {
      mintGuestMock
        .mockResolvedValueOnce({ guest_token: "guest-token-1", guest_id: "guest-1", used: 1, total: 5 })
        .mockResolvedValueOnce({ guest_token: "guest-token-2", guest_id: "guest-2", used: 0, total: 5 });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue(signedInAllowance);
      signupMock.mockRejectedValue(new ApiError(409, "signup failed with 409"));
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      // Ask once anonymously, so a real guest identity exists to migrate.
      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));

      await signInFromNav(user);
      await waitFor(() =>
        expect(loginMock).toHaveBeenCalledWith(
          expect.objectContaining({ guest_token: "guest-token-1" }),
        ),
      );

      // R6: Log out from a screen other than Search still lands on the
      // search home page.
      await user.click(navArea().getByText(/^integrations$/i));
      await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
      await user.click(screen.getByRole("menuitem", { name: /log out/i }));
      expect(await mainArea().findByRole("textbox", { name: /question/i })).toBeInTheDocument();

      await ask(user, "What variants cause it?");

      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(2));
      expect(createRunMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ text: "What variants cause it?" }),
        "guest-token-2",
      );
      expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();
    });

    it("still admits a visitor who signed in without ever holding a guest identity", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue(signedInAllowance);
      signupMock.mockRejectedValue(new ApiError(409, "signup failed with 409"));
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      await signInFromNav(user);
      await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
      expect(loginMock.mock.calls[0][0]).not.toHaveProperty("guest_token");

      await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
      await user.click(screen.getByRole("menuitem", { name: /log out/i }));

      await ask(user, "What gene is BRCA1?");

      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
      expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();
    });

    it("drops a revoked guest token with a plain message, and mints a fresh identity on the next ask", async () => {
      window.localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, "revoked-token");
      createRunMock
        .mockRejectedValueOnce(
          new ApiError(
            401,
            "createRun failed with 401: this guest session is no longer valid",
            "guest_session_revoked",
          ),
        )
        .mockResolvedValue({ run_id: "run-2", persona_name: "Mendel" });
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-2", guest_id: "guest-2", used: 0, total: 5,
      });
      getAllowanceMock.mockResolvedValue({ kind: "guest", used: 0, total: 5, counted: true });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      const failure = await screen.findByTestId("answer-failure");
      expect(failure.textContent).toMatch(/send the question again/i);
      expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();
      expect(window.localStorage.getItem(GUEST_TOKEN_STORAGE_KEY)).toBeNull();

      await user.click(mainArea().getByRole("button", { name: /new search/i }));
      await ask(user, "What variants cause it?");

      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
      expect(createRunMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ text: "What variants cause it?" }),
        "guest-token-2",
      );
    });

    it("mints a fresh identity when the guest token merely expired", async () => {
      window.localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, "expired-token");
      createRunMock
        .mockRejectedValueOnce(
          new ApiError(401, "createRun failed with 401: invalid or expired credentials"),
        )
        .mockResolvedValue({ run_id: "run-2", persona_name: "Mendel" });
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-2", guest_id: "guest-2", used: 0, total: 5,
      });
      getAllowanceMock.mockResolvedValue({ kind: "guest", used: 1, total: 5, counted: true });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
      expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();

      await user.click(mainArea().getByRole("button", { name: /new search/i }));
      await ask(user, "What variants cause it?");

      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
      expect(createRunMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ text: "What variants cause it?" }),
        "guest-token-2",
      );
    });
  });

  describe("no fabricated content on the anonymous path (F-4.10-03)", () => {
    /**
     * Added by the LEAD after mutation-testing this phase's own work, and
     * it is here because a check went quiet without anyone weakening it.
     *
     * Build phase 4.8's judge round 1 filed its first critical against
     * exactly this: an anonymous visitor asking any question was shown a
     * fabricated, fully cited answer carrying a real NCBI source URL. The
     * guard against it is `phase48Premise.test.tsx`'s clause 3e, and this
     * phase preserved every one of its assertions verbatim.
     *
     * Preserving them was not enough. Clause 3e reaches its assertions
     * through a run whose stream NEVER RESOLVES, so the answer screen
     * never mounts and its absence checks pass without being able to
     * fail. Before this phase the same clause ran with the visitor sitting
     * on the sign-in wall, and the defect it was written against rendered
     * an answer screen, so the checks did bite. Making the anonymous path
     * real moved the scenario out from under them.
     *
     * Measured, not reasoned: a fabricated cited source was injected
     * unconditionally into `AnswerScreen`'s source list, and clause 3e
     * PASSED. Two other suites caught it, neither of them the anonymous-
     * fabrication guard.
     *
     * The general form, worth more than the fix: an assertion can be
     * hollowed out without being edited, by changing the state the code
     * reaches before evaluating it. Reviewing the diff of a test file
     * cannot detect that. Only running a mutation can.
     *
     * So this clause lands the run instead of hanging it, which is the
     * only way the answer screen mounts and the absence assertions can
     * fail at all.
     */
    const frame = (seq: number, type: string, payload: unknown): string =>
      `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
        type, version: "v1", trace_id: "phase410", seq,
        ts: "2026-08-15T00:00:00Z", payload,
      })}\n\n`;

    /** A run that genuinely LANDS and genuinely cites nothing. */
    const groundlessRun = (): Promise<Response> => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode([
            frame(0, "guard", { passed: true, category: "ok", reason: null }),
            frame(1, "think", {
              narrative: "Reading the question.", query_class: "lookup",
              resolved_entities: [], clarifying_question: null,
            }),
            frame(2, "plan", { narrative: "Nothing to call.", tool_calls: [] }),
            frame(3, "trust_signal", {
              outcome: "refuse", risk_tier: "low", grounded: false, triangulated: null,
            }),
            frame(4, "done", {
              total_cost_usd: 0.0, total_tool_calls: 0, elapsed_ms: 12,
              trust_outcome: "refuse",
            }),
          ].join("")));
          controller.close();
        },
      });
      return Promise.resolve(new Response(body, {
        status: 200, headers: { "content-type": "text/event-stream" },
      }));
    };

    it("shows an anonymous visitor no source, citation or NCBI url when the run cited nothing", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      getAllowanceMock.mockResolvedValue({ kind: "guest", used: 1, total: 5, counted: true });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      openEventStreamMock.mockReturnValue(groundlessRun());

      const user = userEvent.setup();
      const { container } = render(<App />);
      await ask(user, "What is the capital of the USA?");

      // The run must genuinely reach a terminal state first. Without this
      // the assertions below would be passing on an unmounted screen,
      // which is precisely the failure this clause exists to correct.
      await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
      // POSITIVE anchor, and it is the whole point of this clause. The
      // first version of this test waited for a `run-screen` testid that
      // does not exist anywhere in this codebase, so the wait resolved
      // instantly and every absence assertion below ran against the RUN
      // screen, where a fabricated source could not appear regardless.
      // Mutation-testing caught it: with a fabricated cited source forced
      // into the answer screen, this clause still passed. Waiting on a
      // real element that only the ANSWER screen renders is what makes
      // the absences below capable of failing.
      await screen.findByTestId("answer-meta", undefined, { timeout: 5000 });

      expect(screen.queryByTestId("source-1")).not.toBeInTheDocument();
      expect(screen.queryByTestId(/^citation-/)).not.toBeInTheDocument();
      expect(container.textContent ?? "").not.toMatch(/ncbi\.nlm\.nih\.gov/i);
      // The guest reached the backend on a guest credential, never on an
      // access token it does not have.
      expect(createRunMock).toHaveBeenCalledWith(
        expect.objectContaining({ text: "What is the capital of the USA?" }),
        "guest-token-1",
      );
    });
  });
});
