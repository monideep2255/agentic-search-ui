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
async function signInFromNav(
  user: ReturnType<typeof userEvent.setup>,
  action: "log in" | "sign up" = "log in",
) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(
    screen.getByRole("button", { name: action === "log in" ? /^log in$/i : /^sign up$/i }),
  );
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

  describe("the dots read the server's own count, never a client guess", () => {
    it("renders GuestAllowance from GET /v1/allowance's used/total, after returning to the landing", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      // The SERVER's count after this run, 3 of 5 spent: 2 left. If the
      // dots were still a client counter incremented once per ask, a
      // single ask would show "4 searches left" (5 - 1), not this value;
      // asserting the SERVER's number is what makes this a real check of
      // the source, not just of the widget rendering at all.
      getAllowanceMock.mockResolvedValue({ kind: "guest", used: 3, total: 5, counted: true });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(getAllowanceMock).toHaveBeenCalledWith("guest-token-1"));

      await user.click(screen.getByRole("button", { name: "New search" }));

      const widget = await screen.findByTestId("guest-allowance");
      expect(within(widget).getByText(/2 searches left/i)).toBeInTheDocument();
      // The unblocked arm of the dot-state assertion below: with nothing
      // blocking, the dots still report the guest's own true count. Without
      // this, a change that marked every dot spent unconditionally would
      // satisfy the blocked clauses and destroy the widget.
      expect(widget.querySelectorAll('[data-dot-state="spent"]')).toHaveLength(3);
      expect(widget.querySelectorAll('[data-dot-state="available"]')).toHaveLength(2);
    });

    /**
     * F-4.10-V-03, and the coverage hole that finding named.
     *
     * `blocked_reason` was on the wire and honest from the moment the server
     * learned to send it, and nothing in `frontend/src/` branched on it, so
     * the gate could assert the endpoint was truthful and still leave a
     * visitor looking at unspent dots while every query came back refused.
     * The attempt-ceiling case is the one that made carrying it untenable:
     * `attempts_used` never decreases, so those dots stay wrong for the
     * remaining life of a 7-day token with no event that would ever make
     * them true.
     *
     * Each reason is asserted with its OWN sentence and with the other two
     * absent, the same discipline the wall-copy clauses use, because a
     * single hedged caption covering all three would pass a looser check
     * while telling a visitor behind a busy office address that the whole
     * product is down.
     *
     * NOT exercised here: that the refusal itself is handled, which is the
     * wall clauses below and is a different path (a 403 or 429 on `ask`,
     * not a field on the allowance read).
     */
    it.each([
      ["guest_attempt_limit_reached", /no guest searches left/i],
      ["anon_daily_cap_reached", /guest searches are paused for today/i],
      [
        "anon_source_daily_cap_reached",
        /this network has used its guest searches for today/i,
      ],
    ] as const)(
      "stops promising a search when the server reports blocked_reason %s",
      async (reason, expectedCopy) => {
        mintGuestMock.mockResolvedValue({
          guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
        });
        createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
        // `used: 0` deliberately. This is exactly the shape F-4.10-V-03
        // measured: the guest's own numbers are true and untouched (their
        // answers were refunded), and the NEXT query is refused anyway. A
        // fixture with `used: 5` would pass even with the field ignored,
        // because `5 - 5` already renders zero left.
        getAllowanceMock.mockResolvedValue({
          kind: "guest", used: 0, total: 5, counted: true, blocked_reason: reason,
        });
        const user = userEvent.setup();
        render(<App />);

        await ask(user, "What gene is BRCA1?");
        await waitFor(() => expect(getAllowanceMock).toHaveBeenCalledWith("guest-token-1"));
        await user.click(screen.getByRole("button", { name: "New search" }));

        const widget = await screen.findByTestId("guest-allowance");
        expect(within(widget).getByText(expectedCopy)).toBeInTheDocument();
        // The COUNT is what promised a search, so the count is what must be
        // gone. Matched on the digit rather than on the words, because "No
        // guest searches left" legitimately contains "searches left" and a
        // check that forbade the phrase would forbid the honest caption too.
        expect(within(widget).queryByText(/\d+ searches? left/i)).not.toBeInTheDocument();
        // The dots are the affordance, and they promise independently of the
        // caption: four blue dots beside "No guest searches left" restates
        // the same contradiction one element to the left of where it was
        // fixed. Asserted on state rather than colour so the check can
        // actually fail.
        expect(widget.querySelectorAll('[data-dot-state="available"]')).toHaveLength(0);
        expect(widget.querySelectorAll('[data-dot-state="spent"]')).toHaveLength(5);
      },
    );
  });

  describe("the wall: only the server's own refusal, never a client prediction", () => {
    it("shows the sign-in wall on a 403 carrying guest_allowance_exhausted", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 5, total: 5,
      });
      createRunMock.mockRejectedValueOnce(
        new ApiError(
          403,
          "createRun failed with 403: you have used all of your free searches",
          "guest_allowance_exhausted",
        ),
      );
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      expect(await screen.findByTestId("sign-in-wall")).toBeInTheDocument();
    });

    it("does not show the wall on a 429 concurrent-run-cap refusal, a transient failure", async () => {
      // design decision 5: 403 and 429 mean different things. A 429 here is
      // `concurrent_run_cap_exceeded` (F-4.0-A-10), which is genuinely
      // transient (finishing or stopping a run frees a slot); showing the
      // sign-in wall for it would tell the visitor "sign in to keep going"
      // when signing in does nothing to fix the actual condition.
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

  describe("migration: the held guest token reaches signup and login", () => {
    it("passes the guest token as the guest_token body field on signup and login", async () => {
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

      await signInFromNav(user, "sign up");

      await waitFor(() =>
        expect(signupMock).toHaveBeenCalledWith(
          expect.objectContaining({ guest_token: "guest-token-1" }),
        ),
      );
      expect(loginMock).toHaveBeenCalledWith(
        expect.objectContaining({ guest_token: "guest-token-1" }),
      );
    });

    it("omits guest_token entirely for a visitor who never held a guest session", async () => {
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
      const user = userEvent.setup();
      render(<App />);

      await signInFromNav(user, "log in");

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

      await signInFromNav(user, "log in");
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

  describe("the sign-in wall promises only what the server delivers (F-4.10-A-07)", () => {
    it("states the free searches are spent and makes no claim about history", async () => {
      // The wall appears on the SIXTH search, so by construction the visitor
      // has already run five. Migration reaches only runs the in-memory
      // `RunRegistry` still holds, and it evicts anything finished more than
      // `DEFAULT_RETENTION_SECONDS` (300) ago, so a promise about "the ones
      // from this visit" covers none of the searches this screen is shown
      // after. Nothing in the UI would show a migrated run either way: the
      // browser's history list is React state that survives sign-in in the
      // same tab regardless.
      //
      // The negative assertions are the point of this clause. A promise about
      // carrying searches across sign-in must not come back in a third
      // wording, so both the original ("your history moves with you") and its
      // narrowed successor ("the ones from this visit") are named here, and
      // so is the general shape they share.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 5, total: 5,
      });
      createRunMock.mockRejectedValueOnce(
        new ApiError(
          403,
          "createRun failed with 403: you have used all of your free searches",
          "guest_allowance_exhausted",
        ),
      );
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      const wall = await screen.findByTestId("sign-in-wall");
      expect(within(wall).getByText(/you have used your free searches/i)).toBeInTheDocument();
      expect(wall.textContent ?? "").not.toMatch(/move[sd]? with you/i);
      expect(wall.textContent ?? "").not.toMatch(/your history/i);
      expect(wall.textContent ?? "").not.toMatch(/from this visit/i);
    });

    it("does not tell a migrated browser it used searches it may never have used", async () => {
      // F-4.10-R-02. The clause above pins the sentence on the ONE trigger
      // it is true for. This one drives a trigger the sign-out fix added,
      // where it is false: this visitor asked once, signed up, signed out,
      // and is being shown the wall having used one of five. The same wall
      // is reachable at zero used, by a visitor who created an account
      // without ever asking a question.
      //
      // The gate already drove this exact scenario ("walls a returning
      // visitor whose guest identity was migrated") and asserted only that
      // the wall appeared. Driving a screen without reading what it says is
      // how three copy fixes in a row replaced one false statement with
      // another.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 1, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
      await signInFromNav(user, "log in");
      await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
      await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
      await user.click(screen.getByRole("menuitem", { name: /log out/i }));
      await ask(user, "What variants cause it?");

      const wall = await screen.findByTestId("sign-in-wall");
      expect(wall.textContent ?? "").not.toMatch(/used your free searches/i);
      expect(wall.textContent ?? "").not.toMatch(/free searches are (spent|finished)/i);
      // And it still says something, and something actionable: an empty or
      // silent wall would pass every negative assertion above.
      expect(
        within(wall).getByText(/guest session was moved into an account/i),
      ).toBeInTheDocument();
      expect(
        within(wall).getByRole("button", { name: /create account or sign in/i }),
      ).toBeInTheDocument();
    });

    it("does not tell a visitor at the attempt limit they used searches they never got", async () => {
      // F-4.10-R-01's refusal reaching F-4.10-R-02's screen. This visitor
      // asked ten questions, every one of which the guardrail refused, so
      // every answer was refunded and they received none. "You have used
      // your free searches" is false for them in the strongest possible
      // sense: they used none and got none.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockRejectedValueOnce(
        new ApiError(
          403,
          "createRun failed with 403: you have asked as many questions as a guest can",
          "guest_attempt_limit_reached",
        ),
      );
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      const wall = await screen.findByTestId("sign-in-wall");
      expect(wall.textContent ?? "").not.toMatch(/used your free searches/i);
      expect(
        within(wall).getByText(/asked as many questions as a guest can/i),
      ).toBeInTheDocument();
    });

    it("shows the exhausted-allowance sentence only for the exhausted-allowance refusal", async () => {
      // The arm that stops the fix from being made by weakening the copy to
      // something vague enough to be true everywhere. "You have used your
      // free searches" is the right thing to say to somebody who used their
      // five free searches, and it must survive.
      //
      // Without this clause, deleting the sentence outright, or replacing
      // all three with one hedged line, passes every negative assertion in
      // the two clauses above.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 5, total: 5,
      });
      createRunMock.mockRejectedValueOnce(
        new ApiError(
          403,
          "createRun failed with 403: you have used all of your free searches",
          "guest_allowance_exhausted",
        ),
      );
      const user = userEvent.setup();
      render(<App />);

      await ask(user, "What gene is BRCA1?");

      const wall = await screen.findByTestId("sign-in-wall");
      expect(within(wall).getByText(/you have used your free searches/i)).toBeInTheDocument();
      expect(wall.textContent ?? "").not.toMatch(/moved into an account/i);
      expect(wall.textContent ?? "").not.toMatch(/as many questions as a guest can/i);
    });
  });

  describe("signing out does not hand out a fresh allowance (F-4.10-A-05)", () => {
    /**
     * The measured hole: `App.tsx` cleared the guest token on sign-out AND
     * on sign-in, so sign in, sign out, ask five more, repeat handed out an
     * unlimited number of free allowances with no developer tools and no
     * storage clearing involved. The 2026-08-14 product-owner decision
     * accepted that a person who deliberately clears their token gets five
     * more; it did not accept that the application clears it for them.
     *
     * BOTH ARMS, because this control has no safe direction of failure. An
     * app that walls every anonymous visitor forever passes the refuse arm
     * perfectly and destroys the product, and no attack test would ever
     * catch it. So the second clause asserts that a visitor who never
     * converted a guest identity is still admitted normally.
     */
    const signedInAllowance = { kind: "user" as const, used: 0, total: 100, counted: false };

    it("walls a returning visitor whose guest identity was migrated, instead of minting a new one", async () => {
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 1, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue(signedInAllowance);
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      const { unmount } = render(<App />);

      // Ask once anonymously, so a real guest identity exists to migrate.
      await ask(user, "What gene is BRCA1?");
      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));

      // Sign in: the server migrates and REVOKES that guest session.
      await signInFromNav(user, "log in");
      await waitFor(() =>
        expect(loginMock).toHaveBeenCalledWith(
          expect.objectContaining({ guest_token: "guest-token-1" }),
        ),
      );

      // Sign out, the ordinary way, from the account menu.
      await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
      await user.click(screen.getByRole("menuitem", { name: /log out/i }));

      await ask(user, "What variants cause it?");

      const wall = await screen.findByTestId("sign-in-wall");
      expect(wall).toBeInTheDocument();
      // F-4.10-R-02: this clause DROVE the false sentence and never read it.
      // Every assertion it already made is unchanged and still required;
      // this one is added, so a wall that appears with the wrong sentence
      // can no longer satisfy the clause that creates the state.
      expect(wall.textContent ?? "").not.toMatch(/used your free searches/i);
      expect(mintGuestMock).toHaveBeenCalledTimes(1);
      expect(createRunMock).toHaveBeenCalledTimes(1);

      // THE SAME THING AFTER A RELOAD, and this half is not decoration.
      // Mutation-tested: with only the in-tab assertions above, restoring the
      // old sign-out clear (drop the token, drop the marker) still passed,
      // because React state carried the fact across the sign-out on its own
      // and nothing forced the persisted half to be read. Remounting is what
      // makes what sign-out wrote to storage load-bearing.
      unmount();
      render(<App />);
      await ask(user, "Which trials are recruiting?");

      expect(await screen.findByTestId("sign-in-wall")).toBeInTheDocument();
      expect(mintGuestMock).toHaveBeenCalledTimes(1);
    });

    it("still admits a visitor who signed in without ever holding a guest identity", async () => {
      // The admit arm. Signing in from the nav bar before ever asking a
      // question migrates nothing, so signing out must leave this browser
      // exactly as anonymous as it was, free to mint its first guest
      // identity. Without this, the fix above could wall everyone who ever
      // touched the login screen and every refusal test would still pass.
      mintGuestMock.mockResolvedValue({
        guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
      });
      createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
      getAllowanceMock.mockResolvedValue(signedInAllowance);
      loginMock.mockResolvedValue({
        access_token: "test-token", refresh_token: "r", token_type: "bearer",
      });
      const user = userEvent.setup();
      render(<App />);

      await signInFromNav(user, "log in");
      await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
      expect(loginMock.mock.calls[0][0]).not.toHaveProperty("guest_token");

      await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
      await user.click(screen.getByRole("menuitem", { name: /log out/i }));

      await ask(user, "What gene is BRCA1?");

      await waitFor(() => expect(mintGuestMock).toHaveBeenCalledTimes(1));
      expect(screen.queryByTestId("sign-in-wall")).not.toBeInTheDocument();
    });

    it("walls, rather than re-minting, when the server reports the guest session revoked", async () => {
      // The second, independent path the adversary named: `ask`'s error
      // branch cleared the guest token on ANY 401 while signed out, and
      // `POST /v1/query` answers 401 for a revoked session, so the very
      // refusal that ends a migrated guest's allowance caused the next ask
      // to mint a brand-new one. The reason string is what separates this
      // from an ordinary expired token (the clause below).
      window.localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, "revoked-token");
      createRunMock.mockRejectedValueOnce(
        new ApiError(
          401,
          "createRun failed with 401: this guest session is no longer valid",
          "guest_session_revoked",
        ),
      );
      const user = userEvent.setup();
      const { unmount } = render(<App />);

      await ask(user, "What gene is BRCA1?");

      const revokedWall = await screen.findByTestId("sign-in-wall");
      expect(revokedWall).toBeInTheDocument();
      // The third trigger, and the third place the old single sentence was
      // false: a revoked session says nothing about how many searches were
      // used (F-4.10-R-02).
      expect(revokedWall.textContent ?? "").not.toMatch(/used your free searches/i);
      expect(mintGuestMock).not.toHaveBeenCalled();

      // And it survives a reload. A marker that lived only in React state
      // would be forgotten by the next page load, which is the same hole one
      // refresh later.
      unmount();
      render(<App />);
      await ask(user, "What variants cause it?");

      expect(await screen.findByTestId("sign-in-wall")).toBeInTheDocument();
      expect(mintGuestMock).not.toHaveBeenCalled();
    });

    it("mints a fresh identity when the guest token merely expired, rather than walling", async () => {
      // The other admit arm, and the reason the backend carries a
      // machine-readable reason at all. A guest token past its 7-day TTL is
      // not about the allowance, and a returning visitor must not be walled
      // for it. A 401 with no reason is exactly that case.
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
