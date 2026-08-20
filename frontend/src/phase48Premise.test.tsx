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
 *                   actually reaches createRun with its bearer token, that the
 *                   screens RENDER FROM the resulting event stream rather than
 *                   from a timer, that the adapter never overstates what the
 *                   events said, that NO answer content is reachable without a
 *                   run behind it, and stub declaration completeness.
 *   NOT exercised:  visual fidelity (a layout can satisfy every assertion here
 *                   and still look wrong; that is the judge and adversary
 *                   rounds' job), stubbed-surface data correctness, docs prose
 *                   accuracy against the live API, and colour contrast, which
 *                   is Playwright's.
 */

import { render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

/**
 * T-4.5-10. `App` fetches the session's persona once at load from
 * `GET /v1/persona`, so the shell's persona chip carries the name the server
 * assigned rather than one the browser invented. This file deliberately uses
 * dynamic imports and mocks no module (see WHY THE IMPORTS ARE DYNAMIC
 * above), so the one network call that clause 2 and clause 4 depend on is
 * stubbed at the `fetch` level instead.
 *
 * Only `/v1/persona` is answered here. Anything else this suite reaches for
 * still fails exactly as it did before, so this stub cannot quietly satisfy
 * an assertion it was not written for.
 */
const _realFetch = globalThis.fetch;
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input.toString();
  if (url.includes("/v1/persona")) {
    return Promise.resolve(
      new Response(JSON.stringify({ persona_name: "Mendel" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  return _realFetch(input, init);
}) as typeof fetch;

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
  /*
   * Added 2026-08-14 with F-4.8-D-08. This token was NOT in the fixture while
   * it was the one drifting: it failed AA on two of the design system's own
   * surfaces, the design was corrected from #71767A to #666B70, and nothing
   * here would have noticed the theme keeping the old value.
   *
   * A token the theme uses and the fixture omits is a token the gate does not
   * grade, which is the gap this closes rather than a new nicety.
   */
  inkFaint: "#666B70",
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
    // T-4.5-10: the shell no longer invents a persona. It used to default to
    // a hardcoded "Mendel", which meant this assertion passed whether or not
    // a real name ever reached the component. The name is now an INPUT,
    // resolved server-side from the curated deceased-only list, so the gate
    // supplies one and the assertion tests rendering rather than a default.
    render(
      <AppShell personaName="Mendel">
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
        claims={[{ text: "BRCA1 is associated with HBOC.", layer: 1, citations: [1] }]}
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
        claims={[{ text: "BRCA1 is associated with HBOC.", layer: 1, citations: [1] }]}
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
          { text: "First claim.", layer: 1, citations: [1] },
          { text: "Second claim, uncited.", layer: null, citations: [] },
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
    // T-4.10-08/09: signing in now fetches the caller's real allowance
    // (`App.tsx`'s `onAuthenticated`) so the account menu can state the
    // real daily limit instead of the old hardcoded "unlimited searches"
    // (F-4.9-A-16). Mocked here so this clause exercises `api.login` and
    // `api.createRun` without also making a real, unmocked network call to
    // `GET /v1/allowance` the moment sign-in succeeds.
    vi.spyOn(api, "getAllowance").mockResolvedValue({
      kind: "user", used: 0, total: 100, counted: false,
    } as never);

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
    await user.click(within(main).getByRole("button", { name: /^search the knowledge graph$/i }));

    await waitFor(() => expect(createRunSpy).toHaveBeenCalledTimes(1));
    expect(createRunSpy).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Which diseases are associated with BRCA1?" }),
      "test-token",
    );
  });
});

describe("clause 3c: the screens render from the real event stream", () => {
  it("derives steps, tools, claims and citations from events, not from a timer", async () => {
    // ADDED after a second regression of the same family. The assembly called
    // createRun (so clause 3b passed) and then rendered a canned five-step walk
    // on setTimeout, ignoring the stream entirely. The only code that consumed
    // events lived in ChatPage, which the new routing had orphaned: a module
    // with no callers, which is LEARNINGS.md's row 28.
    //
    // Asserted at the adapter rather than through the DOM, because the mapping
    // IS the join. A DOM test would pass against a component that happened to
    // render the right shapes from anywhere.
    const { useRunView, layerNumber } = await need<any>(
      "T-4.8-12 (event adapter)",
      "./hooks/useRunView.ts",
    );

    expect(layerNumber("layer_1_graph")).toBe(1);
    expect(layerNumber("layer_2_api")).toBe(2);
    expect(layerNumber("layer_3_enrichment")).toBe(3);

    const events = [
      { type: "guard", payload: { passed: true, category: "ok" } },
      { type: "think", payload: {} },
      { type: "plan", payload: {} },
      {
        type: "tool_result",
        payload: {
          call_id: "c1",
          tool: "cypher_query",
          layer: "layer_1_graph",
          status: "ok",
          summary: "",
          result_count: 25,
          truncated: false,
        },
      },
      // Two tokens, because the backend emits ONE PER SENTENCE. The first
      // declares its citation by citation_id in marker_ids; the second declares
      // none and must therefore render as a gap on the spine.
      {
        type: "token",
        payload: { text: "BRCA1 is associated with HBOC [1]. ", marker_ids: ["cid-1"] },
      },
      { type: "token", payload: { text: "It is also unsupported. ", marker_ids: [] } },
      {
        type: "citation",
        payload: {
          citation_id: "cid-1",
          display_index: 1,
          source: "NCBI Gene",
          source_id: "672",
          source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
          layer: "layer_1_graph",
          field: "cypher_query",
          claim_text: "BRCA1 is associated with HBOC",
          evidence_kind: "curated assertion",
          assertion_confidence: "high",
          population_ancestry_context: null,
          license: "public domain",
        },
      },
      { type: "trust_signal", payload: { outcome: "answer", risk_tier: "high", grounded: true, triangulated: null } },
      { type: "done", payload: {} },
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    // The run landed, so no step is live. Derived from the done event, not a clock.
    expect(view.landed).toBe(true);
    expect(view.activeStep).toBeNull();

    // A tool chip exists because a tool event arrived, carrying its real layer.
    expect(view.toolCalls).toHaveLength(1);
    expect(view.toolCalls[0]).toMatchObject({ name: "cypher_query", layer: 1 });

    // The cited claim carries its citation; the uncited one carries the GAP,
    // which is the whole reason the provenance spine exists.
    expect(view.claims).toHaveLength(2);
    expect(view.claims[0]).toMatchObject({ citations: [1], layer: 1 });
    expect(view.claims[1]).toMatchObject({ citations: [], layer: null });
    // The backend's own inline [N] marker is stripped, because the UI renders
    // its own chip from marker_ids and showing both produced "...HBOC [1]. 1".
    expect(view.claims[0].text).not.toContain("[1]");

    // Provenance comes off the citation event, licence included.
    expect(view.sources[0]).toMatchObject({
      n: 1,
      layer: 1,
      evidence: "curated assertion",
      license: "public domain",
    });

    // The trust strip reports what arrived and never manufactures a verdict.
    expect(view.trust.map((t: { kind: string }) => t.kind)).toContain("good");
    expect(view.trust.some((t: { label: string }) => /high/i.test(t.label))).toBe(true);
  });

  it("does not render an 'unknown risk claim' pill for a refusal with no assessment", async () => {
    // T-4.3-05 (build phase 4.3) regression. The backend now emits
    // risk_tier: "unknown" on a refusal path where no risk assessment ran
    // (closing F-4.1-J3-02), rather than a hardcoded "low". Before this
    // fix, useRunView's `risk_tier !== "low"` check treated "unknown" the
    // same as a genuinely elevated tier and pushed a spurious "unknown
    // risk claim" pill alongside "Not fully grounded", implying an
    // assessed elevated risk where none was ever computed. Mutation that
    // turns this red: drop the `&& payload.risk_tier !== "unknown"` clause
    // from useRunView.ts's risk-pill condition.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");

    const events = [
      { type: "guard", payload: { passed: false, category: "off_topic", reason: "outside biomedical research" } },
      {
        type: "trust_signal",
        payload: {
          outcome: "refuse",
          risk_tier: "unknown",
          grounded: false,
          triangulated: null,
        },
      },
      { type: "done", payload: {} },
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    const labels = view.trust.map((t: { label: string }) => t.label);
    expect(labels.some((label: string) => /not fully grounded/i.test(label))).toBe(true);
    expect(labels.some((label: string) => /unknown risk claim/i.test(label))).toBe(false);
    // The second arm: a GENUINELY unrecognised (not "unknown") tier must
    // still over-report, per F-4.8-A-19's own reasoning, so this is not a
    // control that silently stopped reporting every non-"low" tier.
    const escalatedEvents = [
      {
        type: "trust_signal",
        payload: { outcome: "flag", risk_tier: "critical", grounded: true, triangulated: null },
      },
      { type: "done", payload: {} },
    ];
    const { result: escalated } = renderHook(() => useRunView(escalatedEvents));
    expect(
      escalated.current.trust.some((t: { label: string }) => /critical risk claim/i.test(t.label)),
    ).toBe(true);
  });

  it("reports no progress when no events have arrived", async () => {
    // The counterfactual. A timer-driven stepper advances on an empty stream;
    // an event-driven one cannot, and that difference is the defect this
    // clause exists to catch.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");
    const { result } = renderHook(() => useRunView([]));
    expect(result.current.activeStep).toBeNull();
    expect(result.current.toolCalls).toEqual([]);
    expect(result.current.claims).toEqual([]);
    expect(result.current.landed).toBe(false);
  });
});

describe("clause 3d: the adapter never overstates what the events said", () => {
  it("binds a claim to its citation by marker_ids, never by matching text", async () => {
    // F-4.8-A-03, and the root cause of four other findings. `_narrative_chunks`
    // emits one token per sentence carrying `marker_ids`, the citation_id values
    // that sentence cites, and its docstring states the contract: "A surface
    // binds a token to its citation by that key, then looks up the number."
    //
    // That binding was discarded in favour of matching each sentence against
    // `claim_text` with `String.includes`. This clause pins the real contract
    // AND its counterfactual, which is what the previous version lacked: every
    // fixture here set `marker_ids: []`, so the gate could not see the defect
    // at all.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");

    const citation = (id: string, index: number, claimText: string) => ({
      type: "citation",
      payload: {
        citation_id: id, display_index: index, source: "NCBI Gene", source_id: "672",
        source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: "layer_1_graph",
        field: "cypher_query", claim_text: claimText, evidence_kind: "curated assertion",
        assertion_confidence: "high", population_ancestry_context: null,
        license: "public domain",
      },
    });

    const events = [
      // Sentence one cites cid-1. Sentence two cites NOTHING, but contains the
      // cited sentence's claim_text as a substring, which is exactly how a
      // dangerous fabricated claim previously acquired a citation.
      { type: "token", payload: { text: "BRCA1 is linked to cancer [1]. ", marker_ids: ["cid-1"] } },
      {
        type: "token",
        payload: {
          text: "Every patient with this cancer should stop chemotherapy immediately. ",
          marker_ids: [],
        },
      },
      citation("cid-1", 1, "cancer"),
      { type: "done", payload: {} },
    ];

    const { result } = renderHook(() => useRunView(events));
    const claims = result.current.claims;

    expect(claims).toHaveLength(2);
    expect(claims[0].citations).toEqual([1]);
    // THE COUNTERFACTUAL. The uncited sentence must stay uncited even though it
    // contains the cited claim_text verbatim.
    expect(claims[1].citations).toEqual([]);
    expect(claims[1].layer).toBeNull();
  });

  it("keeps every citation a claim declared, not just the first", async () => {
    // F-4.8-J-14, which F-4.8-A-04 showed fires on ordinary semicolon-joined
    // backend output rather than only on an edge case.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");
    const cite = (id: string, index: number, layer: string) => ({
      type: "citation",
      payload: {
        citation_id: id, display_index: index, source: "NCBI", source_id: `${index}`,
        source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer,
        field: "cypher_query", claim_text: "", evidence_kind: "curated assertion",
        assertion_confidence: "high", population_ancestry_context: null,
        license: "public domain",
      },
    });
    const events = [
      { type: "token", payload: { text: "A claim citing two sources [1][2]. ", marker_ids: ["a", "b"] } },
      cite("a", 1, "layer_1_graph"),
      cite("b", 2, "layer_2_api"),
      { type: "done", payload: {} },
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.claims[0].citations).toEqual([1, 2]);
  });

  it("folds trust signals worst-wins rather than taking the first", async () => {
    // F-4.8-J-06. This took the FIRST trust_signal and discarded later ones, so
    // a downgraded verdict still displayed as grounded and low risk. That is
    // the critical build phase 4.1 closed at the MCP fold, reappearing here.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");
    const events = [
      { type: "trust_signal", payload: { outcome: "answer", risk_tier: "low", grounded: true, triangulated: null } },
      { type: "trust_signal", payload: { outcome: "flag", risk_tier: "high", grounded: false, triangulated: null } },
      { type: "done", payload: {} },
    ];
    const { result } = renderHook(() => useRunView(events));
    const labels = result.current.trust.map((t: { label: string }) => t.label).join(" ");
    expect(labels).not.toMatch(/grounded · every claim cited/i);
    expect(labels).toMatch(/high/i);
  });
});

describe("clause 3f: the fix rounds' own defects stay fixed", () => {
  // F-4.8-R-01 IS NOT ASSERTED HERE, and the reason is recorded rather than
  // left as a hole.
  //
  // The defect is that `useAgentRun` reset its buffer in an effect, so a render
  // could observe the NEW run id beside the PREVIOUS run's events, and a
  // consumer deriving "finished?" from events skipped the run screen entirely
  // for every question after the first, making Stop unreachable.
  //
  // Two attempts to pin it here both produced assertions that could not fail,
  // proven by mutation-testing rather than by reading them. Reading
  // `result.current` after effects flush sees the effect's own reset; probing
  // during render sees nothing, because a run with a mocked never-resolving
  // stream never accumulates events to go stale in the first place.
  //
  // Reproducing it needs a real stream that really lands, so the assertion
  // lives in `e2e/query-stream-and-stop.spec.ts` ("a second question shows the
  // run screen"), where it was verified to fail with the fix disabled. Named
  // here so this file's coverage is honest about what it does not cover, the
  // same way colour contrast is.


  it("applies one citation-usability rule to chips and to source cards alike", async () => {
    // F-4.8-R-03. `sources` dropped an unusable display_index; the claim chips
    // were built from the same events with no check, so a chip could render
    // "[0]" with no card behind it, or point at a different citation's card.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");
    const cite = (id: string, index: number) => ({
      type: "citation",
      payload: {
        citation_id: id, display_index: index, source: "NCBI", source_id: "1",
        source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: "layer_1_graph",
        field: "cypher_query", claim_text: "", evidence_kind: "curated assertion",
        assertion_confidence: "high", population_ancestry_context: null,
        license: "public domain",
      },
    });
    const events = [
      { type: "token", payload: { text: "A claim [0]. ", marker_ids: ["bad"] } },
      cite("bad", 0),
      { type: "done", payload: {} },
    ];
    const { result } = renderHook(() => useRunView(events));
    // Unusable everywhere, not just in one of the two renderings.
    expect(result.current.sources).toEqual([]);
    expect(result.current.claims[0].citations).toEqual([]);
  });

  it("keeps every system-status note off the provenance spine, not just the cap note", async () => {
    // F-4.8-R-04. write_node emits THREE bare status notes; the A-14 fix
    // handled one, leaving two rendering as uncited grey claims. Both of those
    // are disclosures, so the spine was misreporting on precisely the outputs
    // that exist to be trustworthy.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");
    const events = [
      { type: "token", payload: { text: "Note: this result was truncated. Showing 20 of 15310 matching rows. ", marker_ids: [] } },
      { type: "token", payload: { text: "Note: this answer does not address the following entities named in the question: GCK. ", marker_ids: [] } },
      { type: "done", payload: {} },
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.claims).toEqual([]);
    // Removed from the claims, but NOT discarded: they are disclosures.
    expect(result.current.systemNotes).toHaveLength(2);
  });

  it("strips only the markers a token actually cites, never prose", async () => {
    // F-4.8-R-05. The strip removed EVERY bracketed 1-3 digit number, so
    // "The cohort in study [12] reported..." silently lost "[12]". A lossy,
    // undisclosed edit of answer text is the same family as fabricating one.
    const { useRunView } = await need<any>("T-4.8-12 (event adapter)", "./hooks/useRunView.ts");
    const events = [
      {
        type: "token",
        payload: { text: "The cohort in study [12] reported a 40 percent rate. ", marker_ids: [] },
      },
      { type: "done", payload: {} },
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.claims[0].text).toContain("[12]");
  });
});

describe("clause 3e: no answer content without a run behind it", () => {
  it("an anonymous visitor is shown no claim, source, citation or trust signal", async () => {
    // F-4.8-J-01, the phase's worst defect and the assertion whose absence let
    // it ship. The anonymous path rendered a canned cited answer for ANY
    // question, bypassing the phase 3.0 guardrail entirely.
    //
    // UPDATED, build phase 4.10 (T-4.10-08). The guarantee this clause exists
    // to protect is UNCHANGED: no claim, source, citation or trust signal may
    // ever appear without a real run behind it. What changed is the mechanism
    // an anonymous visitor now reaches a run through. Before this phase there
    // was no backend route for a caller with no account, so the only honest
    // option was to refuse the ask outright and `createRun` was never called.
    // Now `POST /auth/guest` and a guest bearer token on `/v1/query` are real,
    // so an anonymous ask legitimately DOES reach `createRun` (with a guest
    // token, never an access token). The old
    // `expect(createRunSpy).not.toHaveBeenCalled()` line encoded "anonymous
    // callers never reach the backend," which this phase deliberately makes
    // false; the surrounding "no fabricated content" assertions, which this
    // phase does NOT change, are kept exactly as they were.
    const api = await import("./lib/api");
    // Cleared: clause 3b spies on the same module and signs in, so its call
    // history would otherwise leak into this assertion. Test isolation, not a
    // weakened check: the assertion below still fails if THIS render calls it.
    const createRunSpy = vi.spyOn(api, "createRun");
    createRunSpy.mockClear();
    createRunSpy.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" } as never);
    vi.spyOn(api, "mintGuest").mockResolvedValue({
      guest_token: "guest-token-1", guest_id: "g1", used: 0, total: 5,
    } as never);
    vi.spyOn(api, "getAllowance").mockResolvedValue({
      kind: "guest", used: 1, total: 5, counted: true,
    } as never);
    const user = userEvent.setup();
    const { default: App } = await loadApp();
    const { container } = render(<App />);

    const main = screen.getByRole("main");
    await user.type(
      within(main).getByRole("textbox", { name: /question/i }),
      "What is the capital of the USA?",
    );
    await user.click(within(main).getByRole("button", { name: /^search the knowledge graph$/i }));

    // The run is real (createRun WAS called, with a guest token, not the
    // absent access token), and it never lands: `openEventStream` is still
    // the never-resolving promise clause 3b's spy left in place, so nothing
    // this run's stream would have produced is on screen either. Both
    // conditions together are what make the absence below meaningful rather
    // than vacuous.
    await waitFor(() => expect(createRunSpy).toHaveBeenCalledTimes(1));
    expect(createRunSpy).toHaveBeenCalledWith(
      expect.objectContaining({ text: "What is the capital of the USA?" }),
      "guest-token-1",
    );
    expect(screen.queryByTestId("source-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^citation-/)).not.toBeInTheDocument();
    expect(screen.queryByTestId(/^trust-/)).not.toBeInTheDocument();
    expect(container.textContent ?? "").not.toMatch(/ncbi\.nlm\.nih\.gov/i);
  });
});

describe("clause 4: stub registry", () => {
  it("declares every surface this phase stubs, with the phase that wires it", async () => {
    // T-4.8-14. A stub nobody can find is how a placeholder ships to
    // production; this makes the set enumerable rather than discoverable.
    const { STUB_REGISTRY } = await loadRegistry();
    const surfaces = STUB_REGISTRY.map((entry: { surface: string }) => entry.surface);
    // "persona" was removed from this list by T-4.5-10, which WIRED that
    // surface: the chip now renders the server-assigned name from the
    // curated deceased-only list, so there is no persona stub left to
    // declare. The list is deliberately not emptied of the others; each
    // remaining entry is still a real placeholder with an owning phase.
    for (const expected of [
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
      // WIDENED, build phase 4.10. The single-digit-after-the-dot pattern
      // this used to be (`/^\d\.\d$/`) rejected a perfectly valid phase
      // number the moment this repo's own numbering passed 4.9: "4.10" is
      // two digits after the dot, not one. This is the same shape of bug
      // as a two-digit year field, caused by the checked value outliving
      // an assumption baked into the check rather than into the data. The
      // guarantee itself (an "N.M" phase number, not an empty string or
      // free text) is unchanged; only the digit-count assumption is fixed.
      expect(entry.wiredBy, `stub "${entry.surface}" has no owning phase`).toMatch(
        /^\d+\.\d+$/,
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
    // T-4.5-10: the persona arrives from `GET /v1/persona` (stubbed at the
    // top of this file), so it lands a tick after first paint rather than
    // being drawn synchronously in the client. Awaited rather than asserted
    // synchronously, which is the honest consequence of the name now coming
    // from the server instead of being invented locally.
    expect(await screen.findByTestId("persona-chip")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /depth/i })).toBeInTheDocument();

    expect(container.textContent ?? "").not.toMatch(
      /stub|placeholder|coming soon|TODO/i,
    );
  });
});
