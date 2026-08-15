/**
 * Build phase 4.9 premise gate: answer-screen and chrome fidelity.
 *
 * Written BEFORE any build code and watched failing, per
 * `docs/build/Build_workflow_cadence.md` stage 5.
 *
 * THE PREMISE:
 *
 *   The run and answer screens present what the approved prototype presents,
 *   in the prototype's own order, with the specifics the prototype names
 *   rather than summaries of them.
 *
 * Source of truth: `docs/build/design/design-system/prototype/app.html`,
 * `#s-answer` and its `finish()` renderer. The prototype's own order is
 * askline, `.summary` (verdict + meta + Show work), the spine and answer grid,
 * then `#tail`: sources, verdict pills, follow-up, feedback.
 *
 * WHY THESE NINE, AND HOW THEY WERE FOUND. Every clause below traces to a
 * finding raised on 2026-08-14 by screenshotting the running app beside the
 * prototype in the same four states, which is the first time that comparison
 * had been run in this repository. Four of the nine (D-09 through D-12) were
 * invisible to every existing check and to three prior review rounds.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      the nav's ORDER, not merely its membership; that the
 *                   status strip states an outcome and an elapsed time rather
 *                   than counts alone; that Show work reveals the run's own
 *                   steps and hides them again; that the run screen carries
 *                   the same reasoning detail; that sources start COLLAPSED
 *                   and open on demand, each card independently; that a source
 *                   names its layer in words; that a citation chip carries its
 *                   source identity; that the follow-up precedes the rating;
 *                   and that the account control is a menu naming the account.
 *
 *   NOT exercised:  visual position and geometry. Every clause here reads DOM
 *                   order, text and state, which is not layout. The lesson is
 *                   recorded in LEARNINGS.md, 2026-08-14: `order: -1` moves an
 *                   element across the page while every DOM-order assertion
 *                   stays green. Geometry lives in `e2e/`.
 *
 *                   Two fields the prototype shows that the backend does not
 *                   send, and which are therefore NOT built and NOT asserted:
 *                   the source card's SNAPSHOT date, and the entity name in
 *                   the source header (`NCBI Gene 672 · BRCA1`). Neither
 *                   exists on `CitationPayload`. Both are build phase 6.0g's,
 *                   which is already touching the backend. Stated here so the
 *                   omission is arguable rather than discovered.
 *
 *                   The risk REASON behind a high-risk pill (the prototype's
 *                   "High-risk claim · gene to disease"). `risk_tier` carries
 *                   only the tier. The layer-count half of F-4.8-D-12 IS
 *                   asserted, because it is derivable from the run's own tool
 *                   calls.
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

/** One SSE frame in the shape `adapters/web_sse` actually writes. */
function frame(seq: number, type: string, payload: unknown): string {
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({
    type,
    version: "v1",
    trace_id: "phase49",
    seq,
    ts: "2026-08-14T00:00:00Z",
    payload,
  })}\n\n`;
}

/**
 * A landed run, deliberately NON-COLLINEAR on every axis this file asserts.
 *
 * F-4.9-J-02. The first fixture had citation index == layer number == card
 * position, and tools == layers == sources == 3. A judge re-keyed the layer
 * word off the CARD NUMBER instead of the layer, and separately aliased the
 * three strip counts to each other, and the gate stayed 13 of 13 green through
 * both. A fixture whose axes agree cannot tell them apart, so it grades the
 * shape of the code rather than its behaviour.
 *
 * Every axis is now distinct, and each distinction is load-bearing:
 *
 *   4 tool calls, 2 layers among the sources, 3 sources   no count aliases another
 *   citation 1 is Layer 3, citation 2 is Layer 1          index never equals layer
 *   card 1 is Layer 3, card 2 is Layer 1                  position never equals layer
 *   two sources share Layer 3                             layer never identifies a card
 *
 * The 4 tool calls span three layers while only two layers produce citations,
 * which is the ordinary shape of a run that queried somewhere and found
 * nothing there, and is exactly the case that made the strip and the pill
 * disagree (F-4.9-A-06).
 */
const CIT = (id: string, index: number, source: string, sourceId: string, layer: string, tool: string, kind: string) =>
  frame(0, "citation", {
    citation_id: id, display_index: index, source, source_id: sourceId,
    source_url: `https://www.ncbi.nlm.nih.gov/${sourceId}`, layer, field: tool,
    claim_text: "x", evidence_kind: kind, assertion_confidence: "high",
    population_ancestry_context: null, license: "public domain",
  });

const STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop", resolved_entities: [], clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "Read the curated edges, then confirm live.", tool_calls: [] }),
  frame(3, "tool_result", { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "ok", summary: "", result_count: 25, truncated: false }),
  frame(4, "tool_result", { call_id: "c2", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", summary: "", result_count: 1, truncated: false }),
  frame(5, "tool_result", { call_id: "c3", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "ok", summary: "", result_count: 1, truncated: false }),
  frame(6, "tool_result", { call_id: "c4", tool: "clinicaltrials_search", layer: "layer_3_enrichment", status: "ok", summary: "", result_count: 2, truncated: false }),
  frame(7, "token", { text: "Biallelic variants are reported in Fanconi anemia group S [1]. ", marker_ids: ["k1"] }),
  frame(8, "token", { text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome [2]. ", marker_ids: ["k2"] }),
  frame(9, "token", { text: "A recruiting trial lists the same indication [3]. ", marker_ids: ["k3"] }),
  CIT("k1", 1, "PubMed", "21990134", "layer_3_enrichment", "pubtator_annotate", "literature"),
  CIT("k2", 2, "NCBI Gene", "672", "layer_1_graph", "cypher_query", "curated assertion"),
  CIT("k3", 3, "PubMed", "31145812", "layer_3_enrichment", "pubtator_annotate", "literature"),
  frame(12, "trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: true }),
  /*
   * The REAL `done` shape, corrected 2026-08-14 while building T-4.9-01.
   *
   * The first version of this fixture sent `{status, trust_outcome, elapsed_ms,
   * truncated}`, which the client's own validator REJECTS: the wire carries
   * `total_cost_usd`, `total_tool_calls`, `elapsed_ms` and `trust_outcome`, and
   * no status word at all. A fixture authored from a reading of the design
   * rather than the contract is the exact failure LEARNINGS.md records twice
   * for build phase 3.1.
   */
  frame(13, "done", { total_cost_usd: 0.0031, total_tool_calls: 4, elapsed_ms: 11400, trust_outcome: "answer" }),
].join("");

/** A `Response` whose body streams the scripted frames, as the real one does. */
function scriptedResponse(): Promise<Response> {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(STREAM));
      controller.close();
    },
  });
  return Promise.resolve(new Response(body, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  }));
}

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.click(navArea().getByRole("button", { name: /log in/i }));
  await user.type(screen.getByLabelText(/email/i), "person@example.com");
  await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
  await mainArea().findByRole("textbox", { name: /question/i });
}

/** Sign in, ask, and wait for the answer to land. */
async function landAnAnswer(user: ReturnType<typeof userEvent.setup>) {
  await signIn(user);
  const main = mainArea();
  await user.type(main.getByRole("textbox", { name: /question/i }), "Which diseases are associated with BRCA1?");
  await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  await screen.findByTestId("source-1", undefined, { timeout: 5000 });
}

describe("build phase 4.9: the app presents what the prototype presents", () => {
  beforeEach(() => {
    loginMock.mockReset();
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    loginMock.mockResolvedValue({ access_token: "t", refresh_token: "r", token_type: "bearer" });
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "Mendel" });
    openEventStreamMock.mockImplementation(scriptedResponse);
  });

  // ---------------------------------------------------------------- F-4.8-D-09
  it("orders the nav as the prototype does", () => {
    render(<App />);
    const labels = navArea()
      .getAllByRole("button")
      .map((b) => b.textContent?.trim())
      .filter((l): l is string => Boolean(l));

    // ORDER, not membership. The app had all four and the last two swapped,
    // which every membership assertion in this repository accepted.
    expect(labels.slice(0, 4)).toEqual(["Search", "Integrations", "About", "Docs"]);
  });

  // ---------------------------------------------------------------- F-4.8-D-05
  it("states the outcome and the elapsed time, not counts alone", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    const strip = screen.getByTestId("answer-meta");
    expect(strip).toHaveTextContent(/answered/i);
    // 11400ms from the run's own `done` event, rendered as seconds.
    expect(strip).toHaveTextContent(/11\.4\s*s/i);
    // Three DIFFERENT numbers (F-4.9-J-02): 4 tool calls, 2 layers that
    // produced citations, 3 sources. Aliasing any of them to another now
    // fails, which it did not when all three were 3.
    expect(strip).toHaveTextContent(/4 tools/);
    expect(strip).toHaveTextContent(/2 layers/);
    expect(strip).toHaveTextContent(/3 sources/);
  });

  it("reopens the run's own steps behind Show work, and closes them again", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    // Hidden until asked for: the prototype's `#workPanel` starts hidden.
    expect(screen.queryByTestId("work-panel")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /show work/i }));
    const panel = screen.getByTestId("work-panel");
    // The run's OWN narratives, not a placeholder.
    expect(panel).toHaveTextContent(/resolving the gene named in the question/i);
    expect(panel).toHaveTextContent(/read the curated edges/i);
    expect(panel).toHaveTextContent(/cypher_query/);

    await user.click(screen.getByRole("button", { name: /hide work/i }));
    expect(screen.queryByTestId("work-panel")).not.toBeInTheDocument();
  });

  it("does not open a passing run's log with a refusal message", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);
    await user.click(screen.getByRole("button", { name: /show work/i }));

    /*
     * F-4.9-L-01, found by looking at the rendered screen after every clause
     * here was already green.
     *
     * The log's guard line was built from `CATEGORY_COPY`, which is REFUSAL
     * copy whose `ok` entry is a fallback, so a run that passed the guardrail
     * opened its own reasoning with "This question could not be processed."
     * Both halves are asserted: the refusal text must be absent AND the
     * in-scope text present, since an absence-only clause passes against a
     * panel that renders nothing.
     */
    const panel = screen.getByTestId("work-panel");
    expect(panel).not.toHaveTextContent(/could not be processed/i);
    expect(panel).toHaveTextContent(/in scope/i);
  });

  // ---------------------------------------------------------------- F-4.8-D-10
  it("shows the same reasoning detail while the run is still going", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);
    // A stream that never terminates, so the run screen stays up.
    openEventStreamMock.mockImplementation(() => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(STREAM.slice(0, STREAM.indexOf("event: token"))));
          /*
           * CLOSE it. The first version left the controller open to simulate a
           * run still in flight, which left a reader pending for the rest of
           * the file's lifetime and cost the whole suite: across five full
           * runs, unrelated tests in other files timed out at 15s and once at
           * 23s, while every implicated file passed alone.
           *
           * Closing the body does not end the RUN. No `done` event was sent,
           * so `landed` stays false and the run screen stays up, which is the
           * only thing this clause needs.
           */
          controller.close();
        },
      });
      return Promise.resolve(new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } }));
    });

    const main = mainArea();
    await user.type(main.getByRole("textbox", { name: /question/i }), "Which diseases are associated with BRCA1?");
    await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));

    const reasoning = await screen.findByTestId("reasoning-log", undefined, { timeout: 5000 });
    expect(reasoning).toHaveTextContent(/resolving the gene named in the question/i);
    expect(reasoning).toHaveTextContent(/read the curated edges/i);
  });

  // ---------------------------------------------------------------- F-4.8-D-01
  it("starts the sources collapsed, with their count, and opens them", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    const wrap = screen.getByTestId("sources-disclosure");
    expect(wrap).not.toHaveAttribute("open");
    expect(wrap).toHaveTextContent(/sources/i);
    /*
     * F-4.9-J-01. This read `toHaveTextContent("3")` on the whole <details>,
     * and the fixture's third source id is 21990134, which contains a "3". A
     * judge DELETED the count badge outright and the gate stayed 13 of 13
     * green. Asserted on the badge's own element now, with its exact text.
     */
    expect(screen.getByTestId("sources-count")).toHaveTextContent(/^3$/);

    await user.click(within(wrap).getByText(/^sources$/i));
    expect(wrap).toHaveAttribute("open");
  });

  it("collapses each source card independently", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);
    await user.click(within(screen.getByTestId("sources-disclosure")).getByText(/^sources$/i));

    const one = screen.getByTestId("source-1");
    const two = screen.getByTestId("source-2");
    expect(one).not.toHaveAttribute("open");

    await user.click(within(one).getByText(/PubMed 21990134/));
    expect(one).toHaveAttribute("open");
    // Opening one must not open its neighbour.
    expect(two).not.toHaveAttribute("open");
  });

  // ---------------------------------------------------------------- F-4.8-D-02
  it("names each source's layer in words, not just L1", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);
    await user.click(within(screen.getByTestId("sources-disclosure")).getByText(/^sources$/i));

    // The prototype's `s.tag`: "L1 · graph", "L2 · live", "L3 · literature".
    // Card POSITION never equals layer here, and two cards share a layer, so
    // a mapping keyed off the card number cannot pass (F-4.9-J-02).
    expect(screen.getByTestId("source-1")).toHaveTextContent(/L3\s*·\s*literature/i);
    expect(screen.getByTestId("source-2")).toHaveTextContent(/L1\s*·\s*graph/i);
    expect(screen.getByTestId("source-3")).toHaveTextContent(/L3\s*·\s*literature/i);
  });

  // ---------------------------------------------------------------- F-4.8-D-04
  it("carries the source's identity on the citation chip", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    // The prototype's id-bearing chip: the index AND what it points at.
    // Citation 1 is the LAYER 3 PubMed source and citation 2 is the Layer 1
    // Gene source, so an index-keyed or position-keyed label cannot pass.
    expect(screen.getByTestId("citation-1")).toHaveTextContent(/PubMed\s*21990134/);
    expect(screen.getByTestId("citation-2")).toHaveTextContent(/Gene\s*672/);
  });

  // ---------------------------------------------------------------- F-4.8-D-11
  it("puts the follow-up before the rating, as the prototype does", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    const followUp = screen.getByTestId("follow-up");
    const feedback = screen.getByTestId("feedback");
    expect(
      feedback.compareDocumentPosition(followUp) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });

  it("labels the follow-up the way the prototype does", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    expect(screen.getByTestId("follow-up")).toHaveTextContent(/continue this conversation/i);
  });

  // ---------------------------------------------------------------- F-4.8-D-12
  it("says how many layers agreed, not merely that they did", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    // The run used three layers, so the pill must say three. Asserted as the
    // NUMBER, since "Cross-checked across layers" is true of any run and
    // therefore says nothing.
    expect(screen.getByTestId("trust-plain")).toHaveTextContent(/2 layers agreed/i);
  });

  /*
   * ADVERSARY ROUND 1, the four criticals. Each was reproduced in code before
   * being fixed rather than taken on the adversary's word.
   */

  /** A landed stream with one part swapped, for the clauses below. */
  const variant = (opts: {
    trust?: string | null;
    guardPassed?: boolean;
    fatal?: boolean;
    twoLayerClaim?: boolean;
  } = {}) => {
    const f = [
      frame(0, "guard", {
        passed: opts.guardPassed !== false,
        category: opts.guardPassed === false ? "off_topic" : "ok",
        reason: null,
      }),
      frame(1, "tool_result", { call_id: "t1", tool: "cypher_query", layer: "layer_1_graph", status: "ok", summary: "", result_count: 2, truncated: false }),
    ];
    if (opts.twoLayerClaim) {
      f.push(frame(2, "token", { text: "BRCA1 is associated with hereditary breast cancer [1][2]. ", marker_ids: ["k1", "k2"] }));
      f.push(CIT("k1", 1, "NCBI Gene", "672", "layer_1_graph", "cypher_query", "curated assertion"));
      f.push(CIT("k2", 2, "PubTator", "12345", "layer_3_enrichment", "pubtator_annotate", "literature"));
    } else {
      f.push(frame(2, "token", { text: "BRCA1 repairs DNA [1]. ", marker_ids: ["k1"] }));
      f.push(CIT("k1", 1, "NCBI Gene", "672", "layer_1_graph", "cypher_query", "curated assertion"));
    }
    if (opts.trust !== null) {
      f.push(frame(10, "trust_signal", { outcome: opts.trust ?? "answer", risk_tier: "low", grounded: true, triangulated: true }));
    }
    f.push(
      opts.fatal
        ? frame(11, "error", { fatal: true, scope: "run", source: "write_node", error_class: "unexpected", message: "synth tier failed after $0.019 of $0.02 spent on run r-99", retry_after_s: 0 })
        : frame(11, "done", { total_cost_usd: 0.01, total_tool_calls: 1, elapsed_ms: 5000, trust_outcome: opts.guardPassed === false ? "refuse" : "answer" }),
    );
    return f.join("");
  };

  const serve = (body: string) => () => {
    const s = new ReadableStream<Uint8Array>({
      start(c) { c.enqueue(new TextEncoder().encode(body)); c.close(); },
    });
    return Promise.resolve(new Response(s, { status: 200, headers: { "content-type": "text/event-stream" } }));
  };

  async function askIt(user: ReturnType<typeof userEvent.setup>) {
    await signIn(user);
    const main = mainArea();
    await user.type(main.getByRole("textbox", { name: /question/i }), "Which diseases are associated with BRCA1?");
    await user.click(main.getByRole("button", { name: /^search the knowledge graph$/i }));
  }

  it("does not dress a refusal in a success tick (F-4.9-A-03)", async () => {
    const user = userEvent.setup();
    openEventStreamMock.mockImplementation(serve(variant({ guardPassed: false })));
    render(<App />);
    await askIt(user);

    const strip = await screen.findByTestId("answer-meta");
    expect(strip).toHaveTextContent(/refused/i);
    // A green tick beside "Refused" reads as "done, fine" at a glance.
    expect(strip).not.toHaveTextContent("✓");
  });

  it("never reports a grounding verdict the run did not give (F-4.9-A-02)", async () => {
    const user = userEvent.setup();
    openEventStreamMock.mockImplementation(serve(variant({ trust: null })));
    render(<App />);
    await askIt(user);

    await screen.findByTestId("answer-meta");
    /*
     * In a cite-or-refuse system the ABSENCE of a grounding verdict must read
     * as "not verified", never as silence. A dropped or never-emitted
     * trust_signal turned the guarded state into the unguarded one.
     */
    expect(screen.getByTestId("trust-risk")).toHaveTextContent(/not verified/i);
  });

  it("keeps backend text and cost figures off the screen when a run dies (F-4.9-A-01)", async () => {
    const user = userEvent.setup();
    openEventStreamMock.mockImplementation(serve(variant({ fatal: true })));
    render(<App />);
    await askIt(user);

    const failure = await screen.findByTestId("answer-failure");
    expect(failure).not.toHaveTextContent(/\$0\.0/);
    expect(failure).not.toHaveTextContent(/synth tier/i);
    expect(failure).toHaveTextContent(/could not be completed/i);
  });

  it("floors the trust verdict when the run dies (F-4.9-A-01)", async () => {
    const user = userEvent.setup();
    openEventStreamMock.mockImplementation(serve(variant({ fatal: true })));
    render(<App />);
    await askIt(user);

    await screen.findByTestId("answer-failure");
    // The last positive verdict emitted before the crash must not survive it.
    // This is build phase 4.1's closed critical, at the UI layer.
    expect(screen.queryByText(/grounded · every claim cited/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("trust-risk")).toBeInTheDocument();
  });

  it("colours each citation chip by its OWN source's layer (F-4.9-A-04)", async () => {
    const user = userEvent.setup();
    openEventStreamMock.mockImplementation(serve(variant({ twoLayerClaim: true })));
    render(<App />);
    await askIt(user);

    await screen.findByTestId("citation-1");
    // Chip 2 points at a Layer 3 PubTator annotation. Painting it Layer 1
    // tells the reader a text-mined co-mention is a curated graph assertion.
    expect(screen.getByTestId("citation-1")).toHaveAttribute("data-layer", "1");
    expect(screen.getByTestId("citation-2")).toHaveAttribute("data-layer", "3");
  });

  // ---------------------------------------------------------------- F-4.8-A-20
  it("gives the account control a menu that names the account", async () => {
    const user = userEvent.setup();
    render(<App />);
    await signIn(user);

    // The prototype's chip shows the email; sign-out lives INSIDE the menu
    // rather than being the control's only action.
    const control = navArea().getByRole("button", { name: /person@example\.com/i });
    expect(control).toHaveAttribute("aria-expanded", "false");

    await user.click(control);
    expect(control).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /log out/i })).toBeInTheDocument();
  });
});
