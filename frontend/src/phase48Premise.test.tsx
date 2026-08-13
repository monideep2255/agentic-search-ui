/**
 * Build phase 4.8 premise gate.
 *
 * Written BEFORE any build code, and watched failing, per
 * `docs/build/Build_workflow_cadence.md` stage 5 and LEARNINGS.md's record of
 * what happens when a gate is written after the thing it grades.
 *
 * The premise, from `tracker/phase_4.8.md`:
 *
 *   Every screen in the approved prototype exists in the running React app,
 *   built from the design system's own tokens rather than approximations of
 *   them, and the 120 existing frontend tests still pass because no behaviour
 *   changed.
 *
 * Four clauses, in descending order of how load-bearing they are:
 *
 *   1. Token conformance   the theme equals the design system's own hex values
 *   2. Structure           each component still renders its contract's elements
 *   3. Assembly            the landing renders with no token, and every screen
 *                          is reachable from the assembled app
 *   4. Stub registry       every stubbed surface is declared with its owner
 *
 * Contrast (WCAG 2.1 AA) is the fifth clause and lives in the Playwright suite
 * rather than here, because it needs a real browser and `@axe-core/playwright`.
 * Named here so this file's coverage statement is honest about what it omits.
 *
 * WHY THE IMPORTS ARE DYNAMIC. A static import of a module that does not exist
 * yet fails the whole SUITE at transform time, which reports "0 tests" and
 * proves nothing about whether the assertions below can actually fail. Loading
 * each module inside its own test makes every clause fail individually, with a
 * message naming the ticket that owns it, so "watched failing" means something.
 *
 * COVERAGE STATEMENT, per `goal-contracts`'s requirement that a gate declare
 * its own blind spots:
 *
 *   Exercised:      theme token values, component structure, route
 *                   reachability without a token, that a signed-in question
 *                   actually reaches createRun with its bearer token, and stub
 *                   declaration completeness.
 *   NOT exercised:  visual fidelity (a layout can satisfy every assertion here
 *                   and still look wrong; that is the judge and adversary
 *                   rounds' job), stubbed-surface data correctness, docs prose
 *                   accuracy against the live API, and colour contrast, which
 *                   is Playwright's.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

/**
 * The design system is the fixture. These values are transcribed from
 * `docs/build/design/design-system/foundations/colors.html`, which is
 * generated from the approved prototype, so a drift here means the theme and
 * the design have diverged.
 */
const DESIGN_TOKENS = {
  navy: "#112F4E",
  blue: "#205493",
  link: "#0071BC",
  layer1: "#205493",
  layer2: "#2E8540",
  layer3: "#4C2C92",
  risk: "#981B1E",
  warn: "#7A5900",
  canvas: "#F0F0F0",
  surface: "#FFFFFF",
  line: "#D6D7D9",
  ink: "#1B1B1B",
  inkMuted: "#565C65",
} as const;

const norm = (value: string) => value.trim().toUpperCase();

/**
 * Load a module a ticket is expected to create, failing with that ticket's name.
 *
 * The specifier is resolved at runtime through `new URL(...)` and marked
 * `@vite-ignore`, because Vite statically analyses even a dynamic import with a
 * literal path and fails the whole SUITE at transform time when the target does
 * not exist. That reports "0 tests" and proves nothing. Resolving at runtime
 * turns a missing module into an ordinary rejected promise, so each clause below
 * fails on its own and names what has not landed.
 */
async function need<T>(ticket: string, specifier: string): Promise<T> {
  try {
    return (await import(/* @vite-ignore */ new URL(specifier, import.meta.url).href)) as T;
  } catch (error) {
    throw new Error(
      `${ticket} has not landed yet: ${(error as Error).message.split("\n")[0]}`,
    );
  }
}

const loadTheme = () => need<any>("T-4.8-02 (theme)", "./theme.ts");
const loadShell = () =>
  need<any>("T-4.8-03 (app shell)", "./components/shell/AppShell.tsx");
const loadHome = () =>
  need<any>("T-4.8-04 (home screen)", "./components/screens/HomeScreen.tsx");
const loadRun = () =>
  need<any>("T-4.8-05 (run screen)", "./components/screens/RunScreen.tsx");
const loadAnswer = () =>
  need<any>("T-4.8-06 (answer screen)", "./components/screens/AnswerScreen.tsx");
const loadRegistry = () =>
  need<any>("T-4.8-14 (stub registry)", "./stubs/registry.ts");
const loadApp = () => need<any>("T-4.8-12 (assembly)", "./App.tsx");

/** One source with every provenance field Section 9.1 requires. */
const SOURCE = {
  n: 1,
  layer: 1,
  name: "NCBI Gene 672",
  tool: "cypher_query",
  evidence: "curated assertion",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/gene/672",
};

describe("clause 1: token conformance", () => {
  it("the theme carries every design-system colour, unmodified", async () => {
    // T-4.8-02. A nudged blue fails here, the cheapest defect this gate can
    // catch and the most common one in a restyle.
    const { theme } = await loadTheme();
    for (const [name, hex] of Object.entries(DESIGN_TOKENS)) {
      expect(
        norm(theme.designTokens[name as keyof typeof DESIGN_TOKENS]),
        `token "${name}" diverged from the design system`,
      ).toBe(norm(hex));
    }
  });

  it("routes MUI's own palette slots at the design tokens, not near them", async () => {
    // Catches a theme that declares the tokens correctly then hands MUI
    // something else, leaving every component subtly off-palette.
    const { theme } = await loadTheme();
    expect(norm(theme.palette.primary.main)).toBe(norm(DESIGN_TOKENS.blue));
    expect(norm(theme.palette.background.default)).toBe(norm(DESIGN_TOKENS.canvas));
    expect(norm(theme.palette.text.primary)).toBe(norm(DESIGN_TOKENS.ink));
    expect(norm(theme.palette.error.main)).toBe(norm(DESIGN_TOKENS.risk));
  });

  it("commits to a single light theme, with no dark mode", async () => {
    // Product-owner decision, 2026-08-12. A dark palette reintroduced by an
    // MUI default would silently break every contrast assumption behind it.
    const { theme } = await loadTheme();
    expect(theme.palette.mode).toBe("light");
  });
});

describe("clause 2: structure", () => {
  it("the app shell renders the bar, the disclaimer strip and the persona", async () => {
    // T-4.8-03. The disclaimer strip is permanent and not dismissible, so its
    // absence is a compliance defect rather than a styling one.
    const { AppShell } = await loadShell();
    render(
      <AppShell>
        <div />
      </AppShell>,
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByText(/not medical advice/i)).toBeInTheDocument();
    expect(screen.getByTestId("persona-chip")).toBeInTheDocument();
  });

  it("the home screen offers a question field and the depth control", async () => {
    // T-4.8-04. Depth defaults to researcher, per Section 12.9.
    const { HomeScreen } = await loadHome();
    render(<HomeScreen />);
    expect(screen.getByRole("textbox", { name: /question/i })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /depth/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /researcher/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("the run screen renders all five loop steps and a stop control", async () => {
    // T-4.8-05. Five steps, always: the loop's shape is the product's story.
    const { RunScreen } = await loadRun();
    render(<RunScreen question="Which diseases are associated with BRCA1?" />);
    for (const step of ["Guard", "Think", "Plan", "Act", "Write"]) {
      expect(screen.getByText(step)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("a citation chip declares which layer backed it", async () => {
    // T-4.8-06. Layer colour is the identity; a chip that does not carry its
    // layer is indistinguishable from a plain footnote.
    const { AnswerScreen } = await loadAnswer();
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[{ text: "BRCA1 is associated with HBOC.", layer: 1, citation: 1 }]}
        sources={[SOURCE]}
      />,
    );
    expect(screen.getByTestId("citation-1")).toHaveAttribute("data-layer", "1");
  });

  it("a source card renders every provenance field the contract requires", async () => {
    // T-4.8-06. Dropping the licence because it is fiddly is the exact defect
    // this asserts against; Section 9.1 makes all of these required.
    const { AnswerScreen } = await loadAnswer();
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[{ text: "BRCA1 is associated with HBOC.", layer: 1, citation: 1 }]}
        sources={[SOURCE]}
      />,
    );
    const card = screen.getByTestId("source-1");
    for (const field of ["cypher_query", "curated assertion", "high", "public domain"]) {
      expect(card).toHaveTextContent(field);
    }
  });

  it("the provenance spine renders one segment per claim, carrying its layer", async () => {
    // T-4.8-06, and the product owner's settled decision to keep it always on.
    const { AnswerScreen } = await loadAnswer();
    render(
      <AnswerScreen
        question="Two claims"
        claims={[
          { text: "First claim.", layer: 1, citation: 1 },
          { text: "Second claim, uncited.", layer: null, citation: null },
        ]}
        sources={[SOURCE]}
      />,
    );
    const segments = screen.getAllByTestId(/^spine-segment-/);
    expect(segments).toHaveLength(2);
    // An uncited claim must be visibly distinguishable, which is the whole
    // reason the spine exists rather than being decoration.
    expect(segments[1]).toHaveAttribute("data-layer", "none");
  });
});

describe("clause 3: assembly", () => {
  it("a visitor with no token reaches the landing screen, not an auth wall", async () => {
    // T-4.8-12, and the structural change this phase carries: App.tsx today
    // renders AuthGate and nothing else until a token resolves, so the landing
    // is unreachable without an account. The approved design makes the landing
    // the entry point, with an allowance before sign-in is required.
    const { default: App } = await loadApp();
    render(<App />);
    expect(screen.getByRole("textbox", { name: /question/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("every prototype screen is reachable from the assembled app", async () => {
    // Guards LEARNINGS.md's 2026-07-28 defect: components that each pass in
    // isolation while the assembled page renders none of them.
    const { default: App } = await loadApp();
    render(<App />);
    // Scoped to the main navigation landmark rather than the whole document.
    // This is STRICTER, not looser: it now requires the landmark to exist as
    // well as to hold all four. The unscoped version was ambiguous because the
    // home screen's own submit button is also called "Search", which is itself
    // a real accessibility problem and is why the landmark is now labelled.
    const nav = screen.getByRole("navigation", { name: /main/i });
    for (const name of [/search/i, /integrations/i, /docs/i, /about/i]) {
      expect(within(nav).getByRole("button", { name })).toBeInTheDocument();
    }
  });
});

describe("clause 3b: the assembled app is still connected to the agent", () => {
  it("a signed-in question reaches createRun with the bearer token", async () => {
    // ADDED after this gate let a real regression through. The first version of
    // T-4.8-12 replaced createRun with a demo timeline: every screen rendered,
    // navigation worked, and all 13 clauses passed, while nothing connected the
    // interface to the agent at all. Rendering is not wiring, and a gate that
    // only checks rendering will certify a disconnected app.
    //
    // This is the same shape LEARNINGS.md records for build phase 1.2 and again
    // for `build_stable_prefix()` with zero callers: a component satisfying its
    // own criteria while the system it belongs to does not work.
    const api = await import("./lib/api");
    const createRunSpy = vi
      .spyOn(api, "createRun")
      .mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" } as never);
    const loginSpy = vi.spyOn(api, "login").mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    } as never);
    vi.spyOn(api, "openEventStream").mockReturnValue(new Promise(() => {}) as never);

    const user = userEvent.setup();
    const { default: App } = await loadApp();
    render(<App />);

    await user.click(
      within(screen.getByRole("navigation", { name: /main/i })).getByRole("button", {
        name: /log in/i,
      }),
    );
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));
    await waitFor(() => expect(loginSpy).toHaveBeenCalled());

    // Scoped to the main landmark: "Search" is legitimately both a navigation
    // destination and a form action, and they are distinguishable because they
    // sit in different landmarks. Asserting inside main is what this test
    // means, and it is stricter than an unscoped query, not looser.
    const main = screen.getByRole("main");
    const field = await within(main).findByRole("textbox", { name: /question/i });
    await user.type(field, "Which diseases are associated with BRCA1?");
    await user.click(within(main).getByRole("button", { name: /^search$/i }));

    await waitFor(() => expect(createRunSpy).toHaveBeenCalledTimes(1));
    expect(createRunSpy).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Which diseases are associated with BRCA1?" }),
      "test-token",
    );
  });
});

describe("clause 4: stub registry", () => {
  it("declares every surface this phase stubs, with the phase that wires it", async () => {
    // T-4.8-14. A stub nobody can find is how a placeholder ships to
    // production; this makes the set enumerable rather than discoverable.
    const { STUB_REGISTRY } = await loadRegistry();
    const surfaces = STUB_REGISTRY.map((entry: { surface: string }) => entry.surface);
    for (const expected of [
      "persona",
      "audience-depth",
      "follow-up",
      "history",
      "feedback",
      "guest-allowance",
      "kgx-export",
    ]) {
      expect(surfaces).toContain(expected);
    }
    for (const entry of STUB_REGISTRY as { surface: string; wiredBy: string }[]) {
      expect(entry.wiredBy, `stub "${entry.surface}" has no owning phase`).toMatch(
        /^\d\.\d$/,
      );
    }
  });

  it("no stub is visibly marked as a stub in the interface", async () => {
    // The design must read as finished. A stub is marked in code, never on
    // screen: a demo audience must not be able to tell a stubbed surface from
    // a live one.
    //
    // GATE INTEGRITY. The absence assertion alone passes vacuously against an
    // app that renders almost nothing, which is exactly what `App.tsx` does
    // today, so this test passed before a line of phase work existed. That is
    // the defect shape that failed build phase 4.1's first judge round: an
    // assertion that cannot fail. The presence assertions below run FIRST, so
    // the test can only pass once the real UI is on screen and clean.
    const { default: App } = await loadApp();
    const { container } = render(<App />);

    expect(
      screen.getByRole("textbox", { name: /question/i }),
      "the assembled app must render the landing before this test means anything",
    ).toBeInTheDocument();
    expect(screen.getByTestId("persona-chip")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /depth/i })).toBeInTheDocument();

    expect(container.textContent ?? "").not.toMatch(
      /stub|placeholder|coming soon|TODO/i,
    );
  });
});
