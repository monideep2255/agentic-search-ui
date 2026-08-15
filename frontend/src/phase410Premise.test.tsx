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
 *   NOT exercised:  the backend's own admission, isolation, atomicity and
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
    });
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
      // F-4.9-A-16, closed by T-4.10-09. Both surfaces used to be a
      // hardcoded, false "unlimited searches"; both must now show the
      // SAME real number, from the SAME source, or one of the two is
      // still lying.
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
        expect(within(menu).getByText(/up to 100 searches a day/i)).toBeInTheDocument(),
      );

      const rail = screen.getByTestId("history-rail");
      expect(within(rail).getByText(/up to 100 searches a day/i)).toBeInTheDocument();
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
