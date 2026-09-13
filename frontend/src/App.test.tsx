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
    // T-4.10-08/09. Both real for build phase 4.10: an anonymous ask mints
    // a guest token, and sign-in fetches the caller's real allowance.
    mintGuest: vi.fn(),
    getAllowance: vi.fn(),
    // T-4.13-03: sign-in now also seeds the rail from `GET /v1/history`. An
    // api mock that omits an export App actually calls throws inside the
    // seeding effect and takes the whole render down, the same reasoning
    // the comment above `fetchPersona` already gives.
    fetchHistory: vi.fn(),
  };
});

import {
  createRun,
  fetchHistory,
  getAllowance,
  login,
  mintGuest,
  openEventStream,
} from "./lib/api";

const loginMock = vi.mocked(login);
const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const mintGuestMock = vi.mocked(mintGuest);
const getAllowanceMock = vi.mocked(getAllowance);
const fetchHistoryMock = vi.mocked(fetchHistory);

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
    fetchHistoryMock.mockReset();
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
    // T-4.13-03: no server history unless a test says otherwise. Defaulted
    // to empty rather than left unresolved so a test that merely signs in
    // does not also have to think about this call.
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
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

describe("T-4.13-03: durable history", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  /** Sign out through the account menu, the same route railCollapsePremise.test.tsx uses. */
  async function signOut(user: ReturnType<typeof userEvent.setup>) {
    await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
    await user.click(screen.getByRole("menuitem", { name: /log out/i }));
  }

  it("seeds the rail from the server once a signed-in principal exists", async () => {
    // Mutation: gating the seeding effect on something other than `token`,
    // or never calling `setHistory` from its resolved value, leaves the
    // rail on its empty state and turns this red.
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?" }],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    expect(within(rail).getByRole("button", { name: /what is brca1\?/i })).toBeInTheDocument();
  });

  it("does not duplicate a run this tab already made once its server copy arrives", async () => {
    // The critical this ticket names before it is written (`tracker/
    // phase_4.13.md`), restated at the UI layer: a session run and its
    // later-arriving server row render as ONE item, matched on
    // `trace_id`/`run_id`, never on question text alone (see
    // `mergeServerHistory`'s own docstring in App.tsx). Mutation: matching
    // on question text instead of `traceId`, or never setting `traceId`
    // when `createRun` resolves, both turn this red, since the rail would
    // then show the question twice.
    let resolveHistory!: (value: {
      items: { trace_id: string; question: string }[];
      count: number;
    }) => void;
    fetchHistoryMock.mockReturnValue(
      new Promise((resolve) => {
        resolveHistory = resolve;
      }),
    );
    createRunMock.mockResolvedValue({ run_id: "run-42", persona_name: "Mendel" });
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);
    await ask(user, "Which diseases are associated with BRCA1?");
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));

    // The server's own copy of the SAME run now arrives, carrying the same
    // trace_id `createRun` just returned as `run_id`.
    resolveHistory({
      items: [{ trace_id: "run-42", question: "Which diseases are associated with BRCA1?" }],
      count: 1,
    });

    const rail = await screen.findByTestId("history-rail");
    expect(
      within(rail).getAllByRole("button", {
        name: /which diseases are associated with brca1\?/i,
      }),
    ).toHaveLength(1);
  });

  it("leaves the live list on screen when the history fetch fails", async () => {
    // Mutation: letting the rejection propagate instead of being caught,
    // or clearing `history` on any fetch outcome, either crashes the
    // effect or blanks a session item that was never at fault, turning
    // this red.
    fetchHistoryMock.mockRejectedValue(new Error("fetchHistory failed with 401"));
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);
    await ask(user, "What variants cause cystic fibrosis?");

    const rail = await screen.findByTestId("history-rail");
    expect(
      within(rail).getByRole("button", { name: /what variants cause cystic fibrosis\?/i }),
    ).toBeInTheDocument();
  });

  it("clears on sign-out, and a second identity does not inherit the first's list", async () => {
    // The critical build phase 4.5 already shipped once (every guest
    // shared one ownership identity), restated at the UI layer: nothing
    // from the previous principal's fetch may still be on screen once a
    // different principal has signed in. Mutation: dropping
    // `setHistory([])` from the sign-out handler turns this red, because
    // the first identity's restored row would still be present alongside
    // the second's rather than gone.
    fetchHistoryMock.mockResolvedValueOnce({
      items: [{ trace_id: "row-a", question: "Old question for the first identity" }],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);

    await signIn(user);
    const firstRail = await screen.findByTestId("history-rail");
    expect(
      within(firstRail).getByRole("button", { name: /old question for the first identity/i }),
    ).toBeInTheDocument();

    await signOut(user);
    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();

    fetchHistoryMock.mockResolvedValueOnce({
      items: [{ trace_id: "row-b", question: "New question for the second identity" }],
      count: 1,
    });
    await signIn(user);

    const secondRail = await screen.findByTestId("history-rail");
    expect(
      within(secondRail).getByRole("button", { name: /new question for the second identity/i }),
    ).toBeInTheDocument();
    expect(
      within(secondRail).queryByRole("button", { name: /old question for the first identity/i }),
    ).not.toBeInTheDocument();
  });
});

describe("F-4.13-A-10: a restored row renders something asked_at makes possible", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("renders more than bare question text for a restored row that carries asked_at and citation_count", async () => {
    // The endpoint carries no tool or layer count (`HistoryItem` in
    // `adapters/web_sse/app.py` has only trace_id, question, asked_at,
    // trust_signal, citation_count), so the closest honest substitute for
    // the prototype's "N tools · N layers · N sources" is citation_count
    // plus the asked date. Mutation: a fix that populates `meta` with
    // something that never renders, or that renders only for a live run,
    // leaves this red.
    fetchHistoryMock.mockResolvedValue({
      items: [
        {
          trace_id: "row-1",
          question: "What is BRCA1?",
          asked_at: "2026-08-20T12:00:00Z",
          trust_signal: "answer",
          citation_count: 3,
        },
      ],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    const item = within(rail).getByRole("button", { name: /what is brca1\?/i });
    // Bare question text with nothing else is exactly what the shipped bug
    // renders (F-4.13-A-10's own description: "arrives on screen as bare
    // question text with no date and no meta").
    expect(item.textContent).not.toBe("What is BRCA1?");
    expect(item.textContent).toMatch(/3 source/i);
  });

  it("does not render 'Invalid Date' for a restored row with a malformed asked_at", async () => {
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?", asked_at: "not-a-real-timestamp" }],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    const item = within(rail).getByRole("button", { name: /what is brca1\?/i });
    expect(item.textContent).not.toMatch(/invalid date/i);
  });

  it("does not crash when asked_at is absent from a restored row", async () => {
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "row-1", question: "What is BRCA1?" }],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    expect(within(rail).getByRole("button", { name: /what is brca1\?/i })).toBeInTheDocument();
  });
});

describe("F-4.13-A-07: re-asking a restored question", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("moves the re-asked row to the top instead of relabeling it in place", async () => {
    // Two restored rows, newest first (the server's own order). The
    // OLDER one, "What is BRCA1?", is re-asked from the rail.
    //
    // The shipped bug (`App.tsx`'s `ask`, the `current.some(...) ? current
    // : [...]` dedup): since the question text already exists in
    // `history`, NOTHING is added and NOTHING is moved, so the row stays
    // in its original, lower position. The prototype's `start()` instead
    // filters the old entry out and unshifts a fresh one to the top
    // (`app.html` around line 1262), which is what this test requires.
    fetchHistoryMock.mockResolvedValue({
      items: [
        { trace_id: "restored-newer", question: "Which variant is pathogenic in CFTR?" },
        { trace_id: "restored-older", question: "What is BRCA1?" },
      ],
      count: 2,
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    const rail = await screen.findByTestId("history-rail");
    const olderItem = within(rail).getByRole("button", { name: /what is brca1\?/i });
    await user.click(olderItem);
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "What is BRCA1?" }),
      "test-token",
    );

    const afterRail = screen.getByTestId("history-rail");
    // No duplicate: still exactly one row for the re-asked question.
    expect(
      within(afterRail).getAllByRole("button", { name: /what is brca1\?/i }),
    ).toHaveLength(1);

    // Moved to the top: ahead of the row that was newer before the re-ask.
    const buttonTexts = within(afterRail)
      .getAllByRole("button")
      .map((button) => button.textContent ?? "");
    const brca1Index = buttonTexts.findIndex((text) => /what is brca1\?/i.test(text));
    const cftrIndex = buttonTexts.findIndex((text) => /cftr/i.test(text));
    expect(brca1Index).toBeGreaterThan(-1);
    expect(cftrIndex).toBeGreaterThan(-1);
    expect(brca1Index).toBeLessThan(cftrIndex);
  });

  it("does not relabel an unrelated restored row's meta when a different question lands", async () => {
    // A narrower regression guard for the same defect class: landing a
    // run for question B must never touch a DIFFERENT row's meta, which
    // is what F-4.13-A-07's `.map` over every item matching `question`
    // would do if two rows ever shared text. This test only pins the
    // ordering fix above does not remove the traceId-tagging discipline
    // `ask` already had (the comment above its own `setHistory` call).
    fetchHistoryMock.mockResolvedValue({
      items: [{ trace_id: "restored-1", question: "What is BRCA1?" }],
      count: 1,
    });
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    await screen.findByTestId("history-rail");
    await user.type(
      screen.getByRole("textbox", { name: /question/i }),
      "What variants cause cystic fibrosis?",
    );
    await user.click(screen.getByRole("button", { name: /^search the knowledge graph$/i }));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));

    const afterRail = screen.getByTestId("history-rail");
    expect(
      within(afterRail).getByRole("button", { name: /what is brca1\?/i }),
    ).toBeInTheDocument();
    expect(
      within(afterRail).getByRole("button", { name: /what variants cause cystic fibrosis\?/i }),
    ).toBeInTheDocument();
  });
});

describe("F-4.13-RV-01: a rail row's identity survives the list shrinking", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    // Deliberately EMPTY, and that is the point of this clause. Both
    // F-4.13-A-07 clauses above seed the rail from `fetchHistory`, so every
    // row they touch carries a `trace_id` as its id, and a positional-id
    // collision is unreachable from them. It is reachable only among rows
    // this tab created itself, so this clause creates every row it uses.
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("re-asks the clicked row's own question after a re-ask has shrunk the list", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    // 1. Ask A. The rail holds one locally-created row.
    await ask(user, "What is BRCA1?");
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));

    // 2. Re-ask A from the rail, the exact interaction F-4.13-A-07's fix
    //    exists to enable. Filter-then-unshift REMOVES the old row and adds
    //    one, so the list length is 1 before and 1 after: the moment a
    //    length-derived id stops being unique.
    let rail = await screen.findByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /what is brca1\?/i }));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(2));

    // 3. Ask B. Under a positional id it takes the SAME id the row from
    //    step 2 holds, and `onOpen`'s `history.find` then resolves BOTH
    //    rail rows to whichever one happens to sit first.
    await user.click(screen.getByRole("button", { name: "New search" }));
    await ask(user, "Which variant is pathogenic in CFTR?");
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(3));

    rail = screen.getByTestId("history-rail");
    expect(
      within(rail).getByRole("button", { name: /what is brca1\?/i }),
    ).toBeInTheDocument();
    expect(within(rail).getByRole("button", { name: /cftr/i })).toBeInTheDocument();

    // 4. Each row must run ITS OWN question. Both are asserted rather than
    //    only the one that fails today: `find` returns the first match, so
    //    which row exposes a collision depends on the ordering F-4.13-A-07's
    //    fix deliberately changed, and pinning only one would go vacuous the
    //    next time that ordering moves.
    createRunMock.mockClear();
    await user.click(within(rail).getByRole("button", { name: /what is brca1\?/i }));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "What is BRCA1?" }),
      "test-token",
    );

    createRunMock.mockClear();
    rail = screen.getByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /cftr/i }));
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Which variant is pathogenic in CFTR?" }),
      "test-token",
    );
  });
});

/**
 * F-4.13-FV-01: a landing run must not rewrite another row's meta.
 *
 * The meta effect (`App.tsx`, the `view.landed` effect) matches rail rows by
 * QUESTION TEXT and rewrites every match. That was safe for as long as `ask`
 * was the only writer to `history`, because `ask` guarantees at most one row
 * per question text. Build phase 4.13 added a second writer,
 * `mergeServerHistory`, which de-duplicates on `traceId` and never on text,
 * so two rows carrying the same question can now coexist for the first time.
 *
 * The line did not change. The invariant underneath it did, which is the same
 * shape as F-4.13-RV-01 one level up, and is why `git blame` pointing two
 * weeks before this phase is true and misleading.
 *
 * What a person sees: they asked something on 1 August, ask it again today,
 * and the August row's own source count and date are replaced by today's
 * run's numbers. A row then reports data belonging to a run it never was,
 * which is the fabrication class F-4.8-J-01 already made a rule about.
 *
 * The restored row is deliberately given a DIFFERENT citation count and a
 * different date from the landing run's, so the two cannot be confused for
 * each other and the assertion cannot pass by their agreeing.
 */
describe("F-4.13-FV-01: a landing run does not rewrite another row's meta", () => {
  const REPEATED = "What is BRCA1?";
  let releaseHistory: () => void = () => {};

  /** One SSE frame, in the shape `lib/events.ts` actually validates. */
  const frame = (seq: number, type: string, payload: unknown): string =>
    `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
      type,
      version: "v1",
      trace_id: "fv01",
      seq,
      ts: "2026-08-27T00:00:00Z",
      payload,
    })}\n\n`;

  const STREAM = [
    frame(0, "guard", { passed: true, category: "ok", reason: null }),
    frame(1, "think", {
      narrative: "Resolving the gene named in the question.",
      query_class: "single_hop",
      resolved_entities: [],
      clarifying_question: null,
    }),
    frame(2, "plan", { narrative: "Read the curated edges.", tool_calls: [] }),
    frame(3, "tool_result", {
      call_id: "c1", tool: "cypher_query", layer: "layer_1_graph",
      status: "ok", summary: "", result_count: 25, truncated: false,
    }),
    frame(4, "token", { text: "BRCA1 is associated with HBOC [1]. ", marker_ids: ["k1"] }),
    frame(5, "citation", {
      citation_id: "k1", display_index: 1, source: "NCBI Gene", source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/672", layer: "layer_1_graph",
      field: "cypher_query", claim_text: "x", evidence_kind: "curated assertion",
      assertion_confidence: "high", population_ancestry_context: null,
      license: "public domain",
    }),
    frame(6, "trust_signal", {
      outcome: "answer", risk_tier: "low", grounded: true, triangulated: false,
    }),
    frame(7, "done", {
      total_cost_usd: 0.0031, total_tool_calls: 1, elapsed_ms: 11400,
      trust_outcome: "answer",
    }),
  ].join("");

  function scriptedResponse(): Promise<Response> {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(STREAM));
        controller.close();
      },
    });
    return Promise.resolve(
      new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );
  }

  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token", refresh_token: "test-refresh", token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockImplementation(() => scriptedResponse());
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    // Held open deliberately. Resolving this at sign-in would put the
    // restored row in the list BEFORE the ask, and `ask`'s own filter would
    // then remove it on question text, so the meta effect would never see
    // two rows at all and this clause would be red for a reason unrelated
    // to what it tests. The finding's real sequence is ask first, server
    // copy second: `mergeServerHistory` keys on `traceId`, so it does not
    // collide with the local row and both survive.
    releaseHistory = () => {};
    fetchHistoryMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          releaseHistory = () =>
            resolve({
              items: [
                {
                  // The SAME question, asked weeks ago, carrying its own
                  // count and its own date. Nine sources and 1 August cannot
                  // be confused with this run's single source and today's
                  // date, which is what stops the assertion passing by the
                  // two happening to agree.
                  trace_id: "server-trace-1",
                  question: REPEATED,
                  asked_at: "2026-08-01T09:00:00Z",
                  trust_signal: "answer",
                  citation_count: 9,
                },
              ],
              count: 1,
            });
        }),
    );
  });

  it("leaves a restored row's own count and date alone when the same question is re-asked", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    // 1. Ask first, while the server's copy is still in flight.
    await ask(user, REPEATED);
    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));

    // 2. The server's copy of the SAME question now arrives. It carries a
    //    `traceId` the local row does not, so `mergeServerHistory` keeps
    //    both, and two rows share a question text for the first time.
    releaseHistory();

    // The control, and it is what makes the assertion below mean anything.
    // If the restored row never arrived, or arrived without its own meta,
    // then "its meta did not change" is satisfied by a row that never had
    // one, and this clause would pass against any implementation at all.
    const rail = await screen.findByTestId("history-rail");
    await within(rail).findByRole("button", { name: /9 sources/i });

    // 3. Now let this run land. `source-1` is the landing signal the other
    //    vitest suites use; `answer-cap` is reached only by the browser
    //    suite, and waiting for it here made an earlier version of this
    //    clause fail for a reason unrelated to what it tests.
    await screen.findByTestId("source-1", undefined, { timeout: 5000 });

    // The restored row must still report ITS OWN run. This run produced one
    // source today; if the nine-source row is gone, the landing run has
    // written its numbers onto a row it never belonged to.
    const railAfter = screen.getByTestId("history-rail");
    const rows = within(railAfter).getAllByRole("button", {
      name: new RegExp(REPEATED.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"),
    });
    const stillNine = rows.some((row) => /9 sources/i.test(row.textContent ?? ""));
    expect(stillNine).toBe(true);
  });
});

describe("system notes: App forwards the run's disclosures to AnswerScreen", () => {
  /**
   * Regression test for a wiring gap, not a rendering gap.
   *
   * `useRunView` already lifted a truncation or unaddressed-entity token
   * out of `claims` and into `systemNotes`, and `AnswerScreen` already
   * rendered a `systemNotes` array as a notice. Neither piece was broken.
   * `App` simply never passed `view.systemNotes` to `<AnswerScreen>`, so
   * both disclosures were computed and then dropped on the floor between
   * the two components that each handled their half correctly.
   *
   * This is deliberately an App-level test that drives a real SSE stream
   * through `openEventStream`, the same path `useAgentRun` and
   * `useRunView` consume, rather than a unit test that renders
   * `AnswerScreen` directly with a hand-built `systemNotes` prop. A direct
   * `AnswerScreen` test would pass against the broken code, because the
   * broken code was entirely in `App`, one prop above `AnswerScreen`. Only
   * a test that starts at the top of the tree can see whether the wiring
   * between the two actually exists.
   */
  const frame = (seq: number, type: string, payload: unknown): string =>
    `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
      type,
      version: "v1",
      trace_id: "sysnote-1",
      seq,
      ts: "2026-09-05T00:00:00Z",
      payload,
    })}\n\n`;

  const STREAM = [
    frame(0, "guard", { passed: true, category: "ok", reason: null }),
    frame(1, "think", {
      narrative: "Resolving the gene named in the question.",
      query_class: "single_hop",
      resolved_entities: [],
      clarifying_question: null,
    }),
    frame(2, "plan", { narrative: "Read the curated edges.", tool_calls: [] }),
    frame(3, "tool_result", {
      call_id: "c1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "ok",
      summary: "",
      result_count: 30,
      truncated: true,
    }),
    frame(4, "token", { text: "BRCA1 is associated with HBOC [1]. ", marker_ids: ["k1"] }),
    frame(5, "citation", {
      citation_id: "k1",
      display_index: 1,
      source: "NCBI Gene",
      source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/672",
      layer: "layer_1_graph",
      field: "cypher_query",
      claim_text: "x",
      evidence_kind: "curated assertion",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public domain",
    }),
    // The disclosure under test. `write_node` emits this as a bare token
    // with no marker_ids, which `useRunView` recognises by prefix and
    // lifts into `systemNotes` instead of the claim list.
    frame(6, "token", {
      text: "Note: this result was truncated. Showing 5 of 30 matching rows.",
      marker_ids: [],
    }),
    frame(7, "trust_signal", {
      outcome: "answer",
      risk_tier: "low",
      grounded: true,
      triangulated: false,
    }),
    frame(8, "done", {
      total_cost_usd: 0.0031,
      total_tool_calls: 1,
      elapsed_ms: 4200,
      trust_outcome: "answer",
    }),
  ].join("");

  function scriptedResponse(): Promise<Response> {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(STREAM));
        controller.close();
      },
    });
    return Promise.resolve(
      new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );
  }

  beforeEach(() => {
    window.localStorage.clear();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockImplementation(() => scriptedResponse());
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1",
      guest_id: "guest-1",
      used: 0,
      total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("renders the truncation disclosure once the run lands", async () => {
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "What genes are associated with HBOC?");

    const note = await screen.findByTestId("answer-note-0");
    expect(note.textContent).toMatch(/showing 5 of 30 matching rows/i);
  });
});

/**
 * The privacy leak (W-identity-9). `setThread([])` used to appear only in
 * the three New-search handlers, never in sign-out, so a shared browser
 * kept the previous person's collapsed conversation turns, their
 * questions, claims, sources and trust verdicts, on screen for whoever
 * signed in next.
 *
 * Deliberately an App-level test that drives a real SSE stream through
 * `openEventStream`, not a unit test that renders `AnswerScreen` directly
 * with a hand-built `previousTurns` prop. The defect is entirely in
 * `App.tsx`'s sign-out handler, one prop above `AnswerScreen`, which
 * already renders whatever `previousTurns` it is given correctly; a direct
 * `AnswerScreen` test would exercise none of that handler and would pass
 * against the broken code.
 */
describe("privacy: the previous person's thread is cleared on sign-out", () => {
  const frame = (seq: number, type: string, payload: unknown): string =>
    `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
      type,
      version: "v1",
      trace_id: "privacy-1",
      seq,
      ts: "2026-09-05T00:00:00Z",
      payload,
    })}\n\n`;

  const STREAM = [
    frame(0, "guard", { passed: true, category: "ok", reason: null }),
    frame(1, "think", {
      narrative: "Resolving the gene named in the question.",
      query_class: "single_hop",
      resolved_entities: [],
      clarifying_question: null,
    }),
    frame(2, "plan", { narrative: "Read the curated edges.", tool_calls: [] }),
    frame(3, "tool_result", {
      call_id: "c1", tool: "cypher_query", layer: "layer_1_graph",
      status: "ok", summary: "", result_count: 25, truncated: false,
    }),
    frame(4, "token", { text: "BRCA1 is associated with HBOC [1]. ", marker_ids: ["k1"] }),
    frame(5, "citation", {
      citation_id: "k1", display_index: 1, source: "NCBI Gene", source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/672", layer: "layer_1_graph",
      field: "cypher_query", claim_text: "x", evidence_kind: "curated assertion",
      assertion_confidence: "high", population_ancestry_context: null,
      license: "public domain",
    }),
    frame(6, "trust_signal", {
      outcome: "answer", risk_tier: "low", grounded: true, triangulated: false,
    }),
    frame(7, "done", {
      total_cost_usd: 0.0031, total_tool_calls: 1, elapsed_ms: 11400,
      trust_outcome: "answer",
    }),
  ].join("");

  function scriptedResponse(): Promise<Response> {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(STREAM));
        controller.close();
      },
    });
    return Promise.resolve(
      new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );
  }

  /** Sign out through the account menu, the same route `T-4.13-03` uses. */
  async function signOut(user: ReturnType<typeof userEvent.setup>) {
    await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
    await user.click(screen.getByRole("menuitem", { name: /log out/i }));
  }

  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token", refresh_token: "test-refresh", token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockImplementation(() => scriptedResponse());
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("does not show the next signed-in person the previous person's collapsed turns", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    // 1. Land a real answer, then continue the conversation. Continuing
    //    archives the landed turn into `thread`, so `thread` is non-empty
    //    the instant sign-out fires below.
    await ask(user, "What is BRCA1?");
    await screen.findByTestId("source-1", undefined, { timeout: 5000 });
    await user.type(
      screen.getByLabelText(/ask a follow-up question/i),
      "What variants cause it?",
    );
    await user.click(screen.getByRole("button", { name: /^ask$/i }));
    // Continuing the thread starts a new run under the follow-up question;
    // waiting for its heading confirms the archive above already ran,
    // since it happens synchronously before this new run is dispatched.
    await screen.findByRole("heading", { name: "What variants cause it?" });

    // 2. The person at this workstation signs out.
    await signOut(user);

    // 3. The next person signs in and lands their OWN, unrelated answer.
    await signIn(user);
    await ask(user, "What variants cause cystic fibrosis?");
    await screen.findByTestId("source-1", undefined, { timeout: 5000 });

    // The first person's archived turn must not be here. `AnswerScreen`
    // only renders the `data-testid="thread"` wrapper when `previousTurns`
    // is non-empty, so its absence is a direct proof `thread` was cleared,
    // not an inference from something else.
    expect(screen.queryByTestId("thread")).not.toBeInTheDocument();
    expect(screen.queryByText(/what is brca1\?/i)).not.toBeInTheDocument();
  });
});

/**
 * The returning-guest allowance gap (W-GUEST-4). `allowance` was seeded
 * `null` on every mount and the only two writers were a landed run and a
 * fresh sign-in, so a guest whose token was restored from storage saw no
 * dots at all until their NEXT ask spent a third search, even though the
 * server already knew their count.
 */
describe("a returning guest's allowance is fetched at mount", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  // Set 1, R2 (2026-09-12): the allowance is still read at mount, so a
  // shared daily cap can be stated, but no count or dots render.
  it("reads the allowance at mount for a token restored from a prior visit, and shows no count", async () => {
    // `persistGuestToken` writes through the same key `guestToken`'s own
    // initializer reads (`loadPersistedGuestToken`), so this is exactly
    // what a prior visit's mint would have left behind, not a hand-built
    // storage key that could drift from the real one.
    const { persistGuestToken } = await import("./lib/guestSession");
    persistGuestToken("restored-guest-token");
    // Two of five already spent, per the server, from a prior visit.
    getAllowanceMock.mockResolvedValue({ kind: "guest", used: 2, total: 5, counted: true });

    const user = userEvent.setup();
    render(<App />);
    void user; // not driving any interaction; the fetch must happen unasked

    await waitFor(() => expect(getAllowanceMock).toHaveBeenCalledTimes(1));
    expect(getAllowanceMock).toHaveBeenCalledWith(
      "restored-guest-token",
      expect.anything(),
    );

    await waitFor(() => expect(screen.queryByTestId("guest-allowance")).not.toBeInTheDocument());
    expect(screen.queryByText(/\d+ searches? left/i)).not.toBeInTheDocument();
    // Nothing was asked, so nothing should have minted a fresh identity or
    // started a run: this is purely the mount-time read of an existing one.
    expect(mintGuestMock).not.toHaveBeenCalled();
    expect(createRunMock).not.toHaveBeenCalled();
  });

  it("does not change what a brand-new visitor with no persisted token sees", async () => {
    // The control for the test above, and the boundary F-4.10-A-13
    // (`tracker/phase_4.10.md`) leaves open: a visitor with NO persisted
    // token still sees no footer at all before their first ask. Left alone
    // deliberately, since that is a separate, open product-owner question.
    render(<App />);

    expect(getAllowanceMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("guest-allowance")).not.toBeInTheDocument();
  });
});

/**
 * Honest copy that never reached the reader (W-GUEST-11). The backend
 * emits `anon_daily_cap_reached` and `anon_source_daily_cap_reached` as
 * 429s, each carrying a purpose-written sentence in
 * `GuestAllowance.tsx`'s own `BLOCKED_COPY`, and `ask`'s catch block
 * branched only on the two 403 personal-allowance reasons, so a guest
 * hitting either shared daily ceiling saw the generic dispatch-failure
 * fallback instead of the true, already-written reason.
 */
describe("a guest hitting a shared daily ceiling sees the true reason", () => {
  beforeEach(() => {
    window.localStorage.clear();
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    mintGuestMock.mockReset();
    getAllowanceMock.mockReset();
    fetchHistoryMock.mockReset();
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    mintGuestMock.mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "guest-1", used: 0, total: 5,
    });
    getAllowanceMock.mockResolvedValue({ kind: "guest", used: 0, total: 5, counted: true });
    fetchHistoryMock.mockResolvedValue({ items: [], count: 0 });
  });

  it("shows GuestAllowance's own sentence for anon_daily_cap_reached, not the generic failure", async () => {
    const { ApiError } = await import("./lib/api");
    createRunMock.mockRejectedValueOnce(
      new ApiError(429, "createRun failed with 429", "anon_daily_cap_reached"),
    );
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "What is BRCA1?");

    const failure = await screen.findByTestId("answer-failure");
    expect(failure.textContent).toMatch(/guest searches are paused for today/i);
    expect(failure.textContent).not.toMatch(/could not be sent/i);
  });

  it("shows GuestAllowance's own sentence for anon_source_daily_cap_reached, not the generic failure", async () => {
    const { ApiError } = await import("./lib/api");
    createRunMock.mockRejectedValueOnce(
      new ApiError(429, "createRun failed with 429", "anon_source_daily_cap_reached"),
    );
    const user = userEvent.setup();
    render(<App />);

    await ask(user, "What is BRCA1?");

    const failure = await screen.findByTestId("answer-failure");
    expect(failure.textContent).toMatch(/this network has used its guest searches for today/i);
    expect(failure.textContent).not.toMatch(/could not be sent/i);
  });
});
