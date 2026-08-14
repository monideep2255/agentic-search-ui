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
 *   NOT exercised:  the responsive rule. The prototype hides both the rail and
 *                   the strip under 860px via a media query, and jsdom does not
 *                   evaluate media queries, so no assertion here can tell a
 *                   working breakpoint from a broken one. That belongs in the
 *                   Playwright suite and is NOT claimed here.
 *
 *                   Pixel fidelity: the 46px strip width, the vertical
 *                   `writing-mode` label and the badge colour are transcribed
 *                   from the prototype and asserted by eye against a running
 *                   app, not by this file.
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

/** The app bar's own <header> landmark, so "in the bar" is checkable. */
const appBar = () => screen.getByRole("banner");

const toggleName = /show or hide your searches/i;
const collapseName = /^hide your searches$/i;
const expandName = /^show your searches$/i;

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
  await user.click(main.getByRole("button", { name: /^ask$/i }));
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
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockReturnValue(new Promise(() => {}));
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

  it("offers no toggle once the user signs out", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signInWithOneSearch(user);

    // PRESENCE FIRST, deliberately. An absence-only assertion passes against a
    // control that was never built, which is how this phase's stub-marker test
    // passed vacuously on its first run. This clause must fail today.
    expect(screen.getByRole("button", { name: toggleName })).toBeInTheDocument();

    await user.click(navArea().getByRole("button", { name: /^account$/i }));

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
