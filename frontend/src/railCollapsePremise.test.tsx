/**
 * Premise gate for F-4.8-P-03, the stored-searches rail's collapse control.
 *
 * Written BEFORE the fix and watched failing, per
 * `docs/build/Build_workflow_cadence.md` stage 5.
 *
 * THE PREMISE, from `tracker/phase_4.8.md`'s product owner review:
 *
 *   A signed-in user can collapse the stored-searches rail and bring it back,
 *   from the app bar and from the rail itself, and a collapsed rail leaves a
 *   strip that says what it is holding rather than vanishing.
 *
 * The source of truth is the approved prototype,
 * `docs/build/design/design-system/prototype/app.html`, which carries three
 * separate controls (`#railBtn` in the app bar, `.rmin` inside the rail,
 * `#railStub` when collapsed) and gates all of them on
 * `avail = st.loggedIn && onSearch`.
 *
 * WHY THIS FILE ASSERTS POSITION AND STATE, NOT PRESENCE. Build phase 4.8
 * shipped two major layout defects and all three of the product owner's
 * findings past 147 unit tests, 19 browser tests, a clean production build and
 * a full WCAG 2.1 AA pass, because every check in this repository asserts what
 * is on screen and never WHERE it is or WHAT STATE it is in. A presence-only
 * version of this gate would pass against a hamburger rendered in the footer,
 * wired to nothing. So each clause below either compares DOM order with
 * `compareDocumentPosition`, asserts an `aria-expanded` value, or asserts that
 * an element left the document.
 *
 * COVERAGE STATEMENT, per `goal-contracts`'s requirement that a gate declare
 * its own blind spots:
 *
 *   Exercised:      that the toggle lives inside the app bar's own <header>
 *                   and not merely somewhere on the page; that the rail
 *                   precedes main content in DOM order; that the toggle is
 *                   absent for a signed-out visitor and on a non-search
 *                   screen; that `aria-expanded` tracks the real state in both
 *                   directions; that collapsing REMOVES the rail rather than
 *                   restyling it; that the collapsed strip carries the count of
 *                   what it holds; and that all three controls (app bar,
 *                   in-rail, strip) drive the same state.
 *
 *   NOT exercised:  VISUAL POSITION. Every clause here reads DOM order, which
 *                   is reading order, not layout. Mutation-testing proved this
 *                   is a real hole rather than a theoretical one: adding
 *                   `order: -1` to the content column moves the rail to the
 *                   visual RIGHT of the page and every clause below stays
 *                   green. `e2e/rail-collapse.spec.ts` measures bounding boxes
 *                   in a real browser and is what actually catches that; it is
 *                   mutation-tested against this exact case.
 *
 *                   The responsive rule. The prototype hides both the rail and
 *                   the strip under 860px via a media query, and jsdom does not
 *                   evaluate media queries, so no assertion here can tell a
 *                   working breakpoint from a broken one. Also covered by
 *                   `e2e/rail-collapse.spec.ts`, and NOT claimed here.
 *
 *                   Pixel fidelity beyond the strip's width: the vertical
 *                   `writing-mode` label and the badge colour are transcribed
 *                   from the prototype and checked by eye against a running
 *                   app, not by any file.
 *
 *                   The prototype renders the rail with an empty-state message
 *                   when a signed-in user has no history, where the shipped
 *                   rail renders nothing at all. That difference is REAL and is
 *                   deliberately out of this fix's scope, which is the collapse
 *                   control only. It is filed rather than silently closed here.
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
    // T-4.10-08/09: sign-in now also fetches the caller's real allowance,
    // which the rail's footer line (below) is built from.
    mintGuest: vi.fn(),
    getAllowance: vi.fn(),
    // T-4.13-03: sign-in now also seeds the rail from `GET /v1/history`.
    // Defaulted to empty directly here, matching `fetchPersona` above,
    // since no clause in this file needs a non-empty server history.
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

import { createRun, getAllowance, login, openEventStream } from "./lib/api";

const loginMock = vi.mocked(login);
const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const getAllowanceMock = vi.mocked(getAllowance);

const mainArea = () => within(screen.getByRole("main"));
const navArea = () => within(screen.getByRole("navigation", { name: /main/i }));

/** The app bar's own <header> landmark, so "in the bar" is checkable. */
const appBar = () => screen.getByRole("banner");

const toggleName = /show or hide your searches/i;
const collapseName = /^hide your searches$/i;
const expandName = /^show your searches$/i;

/**
 * Sign out through the account menu.
 *
 * Build phase 4.9 replaced the bare "Account" button, whose only action was
 * sign-out, with the prototype's menu (F-4.8-A-20). These clauses assert what
 * happens to the RAIL on sign-out, and that guarantee is unchanged; only the
 * route to signing out moved, so only the route is updated here.
 */
async function signOut(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /person@example\.com/i }));
  await user.click(screen.getByRole("menuitem", { name: /log out/i }));
}

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
  await mainArea().findByRole("textbox", { name: /question/i });
}

async function ask(user: ReturnType<typeof userEvent.setup>, question: string) {
  const main = mainArea();
  await user.type(main.getByRole("textbox", { name: /question/i }), question);
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
}

/** Sign in and run one question, so the rail has something in it. */
async function signInWithOneSearch(user: ReturnType<typeof userEvent.setup>) {
  await signIn(user);
  await ask(user, "Which diseases are associated with BRCA1?");
  await screen.findByTestId("history-rail");
}

describe("F-4.8-P-03: the stored-searches rail collapses", () => {
  beforeEach(() => {
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    getAllowanceMock.mockReset();
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
    // Matches this repo's real PER_USER_DAILY_QUERY_CAP default (100/day,
    // `harness/cost_control.py`), which is what T-4.10-09's clause below
    // asserts the rail footer now states instead of the old "unlimited".
    getAllowanceMock.mockResolvedValue({ kind: "user", used: 0, total: 100, counted: false });
  });

  it("puts the toggle inside the app bar, not merely somewhere on the page", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    // POSITION, not presence. `getByRole` alone would pass against a toggle
    // rendered in the footer.
    const toggle = within(appBar()).getByRole("button", { name: toggleName });
    expect(appBar().contains(toggle)).toBe(true);
  });

  it("puts the rail before the screen's content in DOM order", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const rail = screen.getByTestId("history-rail");
    // The screen's own heading, as the anchor for "the content". Note the rail
    // is a DESCENDANT of <main> in this app, not its sibling as in the
    // prototype, so comparing against <main> itself returns CONTAINED_BY and
    // would assert nothing. That structural difference is real and is filed,
    // not fixed here: it is outside the collapse control's scope.
    const heading = screen.getByRole("heading", {
      name: /diseases are associated with BRCA1/i,
    });
    // A left rail that follows the content in the DOM reads in the wrong order
    // to a screen reader even when CSS puts it on the left.
    expect(
      heading.compareDocumentPosition(rail) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });

  /*
   * F-4.8-P-04. The rail itself, not just its toggle.
   *
   * Found 2026-08-14 by screenshotting the app beside the prototype, NOT by
   * any assertion here: the anonymous landing rendered a full rail with its
   * empty state, where the prototype has none. The clauses below tested the
   * TOGGLE's absence when the rail is unavailable and never the RAIL's, so a
   * three-way render collapsed into a two-way ternary passed them all.
   *
   * It was latent until this same session's baseline alignment: `HistoryRail`
   * used to return null on an empty list, which masked the ternary's else
   * branch rendering it unconditionally. Removing that guard, correctly, per
   * the prototype, unmasked the defect the guard had been hiding.
   */
  it("shows an anonymous visitor no rail at all", () => {
    render(<App />);

    // Both halves. The heading proves the landing actually rendered, so this
    // cannot pass against a blank page.
    expect(
      screen.getByRole("heading", { name: /ask a biomedical question/i }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
    expect(screen.queryByTestId("collapsed-rail")).not.toBeInTheDocument();
  });

  it("takes the rail away again on sign-out", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);
    expect(screen.getByTestId("history-rail")).toBeInTheDocument();

    await signOut(user);

    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
    expect(screen.queryByTestId("collapsed-rail")).not.toBeInTheDocument();
  });

  it("shows no rail on a screen that has none", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);
    expect(screen.getByTestId("history-rail")).toBeInTheDocument();

    await user.click(navArea().getByRole("button", { name: /^about$/i }));

    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
    expect(screen.queryByTestId("collapsed-rail")).not.toBeInTheDocument();
  });

  it("offers no toggle once the user signs out", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    // PRESENCE FIRST, deliberately. An absence-only assertion passes against a
    // control that was never built, which is how this phase's stub-marker test
    // passed vacuously on its first run. This clause must fail today.
    expect(screen.getByRole("button", { name: toggleName })).toBeInTheDocument();

    await signOut(user);

    // `avail = st.loggedIn && onSearch` in the prototype. A visitor with no
    // rail must not be offered a control that toggles nothing.
    expect(screen.queryByRole("button", { name: toggleName })).not.toBeInTheDocument();
  });

  it("offers no toggle on a screen that has no rail", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);
    expect(screen.getByRole("button", { name: toggleName })).toBeInTheDocument();

    await user.click(navArea().getByRole("button", { name: /^about$/i }));

    expect(screen.queryByRole("button", { name: toggleName })).not.toBeInTheDocument();
  });

  it("reports the rail's real state through aria-expanded, in both directions", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const toggle = within(appBar()).getByRole("button", { name: toggleName });
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("removes the rail when collapsed, rather than restyling it", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    await user.click(within(appBar()).getByRole("button", { name: toggleName }));

    // Gone from the document. A rail still present with `visibility: hidden`
    // stays in the tab order and in the accessibility tree.
    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
  });

  it("leaves a strip that says what it holds, with the count", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    await user.click(within(appBar()).getByRole("button", { name: toggleName }));

    const stub = screen.getByTestId("collapsed-rail");
    expect(stub).toBeInTheDocument();
    expect(within(stub).getByText(/your searches/i)).toBeInTheDocument();
    // One search has been run, so the badge says so. Asserted as a value, not
    // as "a badge exists", or a hardcoded zero would pass.
    expect(within(stub).getByText("1")).toBeInTheDocument();
  });

  it("keeps the strip in the rail's own position, before the screen's content", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    await user.click(within(appBar()).getByRole("button", { name: toggleName }));

    const stub = screen.getByTestId("collapsed-rail");
    // Same content anchor as the rail's own position clause above, and for the
    // same reason: the strip is a descendant of <main>, so comparing against
    // <main> returns CONTAINED_BY and asserts nothing. Collapsing must not
    // move the slot from the left of the content to the right of it.
    const heading = screen.getByRole("heading", {
      name: /diseases are associated with BRCA1/i,
    });
    expect(
      heading.compareDocumentPosition(stub) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });

  it("brings the rail back from the strip", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    await user.click(within(appBar()).getByRole("button", { name: toggleName }));
    await user.click(screen.getByRole("button", { name: expandName }));

    expect(screen.getByTestId("history-rail")).toBeInTheDocument();
    expect(screen.queryByTestId("collapsed-rail")).not.toBeInTheDocument();
    expect(within(appBar()).getByRole("button", { name: toggleName })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("collapses from the rail's own control too, driving the same state", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const rail = screen.getByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: collapseName }));

    // The in-rail control and the app bar control must not be two states.
    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("collapsed-rail")).toBeInTheDocument();
    expect(within(appBar()).getByRole("button", { name: toggleName })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  /*
   * BASELINE ALIGNMENT, added 2026-08-14 at the product owner's direction.
   *
   * The first version of this fix delivered the collapse control and left three
   * differences from the prototype in place, two of them as deliberate judgment
   * calls (the strip's surface, and omitting the "+ New search" button the
   * prototype pairs with the collapse control) and one filed as a gap (the
   * empty-state rail). The instruction is that the prototype IS the baseline
   * and those were not judgment calls to make. These clauses hold the rail to
   * `prototype/app.html`'s own `renderRail()`.
   */

  it("carries the prototype's New search button in the rail's top row", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const rail = screen.getByTestId("history-rail");
    const newSearch = within(rail).getByRole("button", { name: /new search/i });
    const heading = within(rail).getByText(/^your searches$/i);

    // POSITION: `.rtop` sits ABOVE `.rh` in the prototype's markup. A button
    // rendered below the list would satisfy a presence-only assertion.
    expect(
      heading.compareDocumentPosition(newSearch) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });

  it("pairs New search with the collapse control on one row, in that order", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const rail = screen.getByTestId("history-rail");
    const newSearch = within(rail).getByRole("button", { name: /new search/i });
    const collapse = within(rail).getByRole("button", { name: collapseName });

    expect(
      newSearch.compareDocumentPosition(collapse) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("returns to the landing screen from the rail's New search", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const rail = screen.getByTestId("history-rail");
    await user.click(within(rail).getByRole("button", { name: /new search/i }));

    expect(mainArea().getByRole("textbox", { name: /question/i })).toBeInTheDocument();
  });

  it("shows the rail with an empty state before the first search", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    // The prototype's `avail = st.loggedIn && onSearch` does NOT depend on
    // history, and `renderRail` emits `.rempty` when the list is empty. The
    // shipped rail rendered nothing at all here.
    //
    // T-4.13-03 corrected this copy: the prototype's own "in this session"
    // wording went false the moment the rail started seeding from
    // `GET /v1/history`, so this clause now asserts the corrected text
    // rather than the prototype's stale claim (`FollowUp.tsx`'s own
    // comment on the `.rempty` block records why the divergence is
    // deliberate).
    const rail = await screen.findByTestId("history-rail");
    expect(within(rail).getByText(/your searches appear here/i)).toBeInTheDocument();
  });

  it("offers the toggle from sign-in, before any search has been run", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    expect(within(appBar()).getByRole("button", { name: toggleName })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("names the signed-in account in the rail's footer, with the real search limit", async () => {
    // The prototype's `.rfoot` is `esc(st.email) + '<br>Unlimited searches'`.
    // The email is real data (what the user typed into the gate that just
    // authenticated them), which this clause still asserts unchanged.
    //
    // UPDATED TWICE, and the guarantee is the same both times: the rail's
    // footer names the account's REAL search standing, whatever that is.
    //
    // Build phase 4.10 (T-4.10-09, closing F-4.9-A-16) replaced "Unlimited
    // searches" with "up to 100 searches a day", because a 100/day cap is
    // shipped in `harness/cost_control.py`.
    //
    // The fix round (F-4.10-A-06) replaced that in turn, because it was
    // false in the other direction: `check_user_daily_query_cap` counts rows
    // in `interactions` and nothing writes that table (F-2.0-04), so the cap
    // cannot fire and no limit is actually in effect. The server says so on
    // the wire with `counted: false`, and the footer now says so too.
    //
    // What this clause protects is unchanged and is asserted MORE strictly
    // than before, not less: the footer must state the real standing from
    // the real fetch, and it must not assert EITHER false claim, the old
    // "unlimited" one or the 100/day one. A footer that silently dropped
    // the line entirely would fail the positive assertion, and a footer that
    // went back to naming an unenforced number would fail the two negatives.
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    const rail = screen.getByTestId("history-rail");
    expect(within(rail).getByText("person@example.com")).toBeInTheDocument();
    await waitFor(() =>
      expect(within(rail).getByText(/no search limit in effect yet/i)).toBeInTheDocument(),
    );
    expect(within(rail).queryByText(/unlimited searches/i)).not.toBeInTheDocument();
    expect(within(rail).queryByText(/100 searches/i)).not.toBeInTheDocument();
  });

  it("keeps the collapsed choice across a new search", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    await user.click(within(appBar()).getByRole("button", { name: toggleName }));
    await user.click(mainArea().getByRole("button", { name: /new search/i }));
    await ask(user, "What is the clinical significance of rs334?");

    // A collapse the user chose must survive the next question, or the control
    // reads as broken.
    expect(screen.queryByTestId("history-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("collapsed-rail")).toBeInTheDocument();
  });
});
