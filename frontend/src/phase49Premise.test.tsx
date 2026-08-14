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
 * A landed run with three cited claims across all three layers.
 *
 * Three layers on purpose: the layer-count pill and the per-source layer word
 * are both meaningless against a single-layer run.
 */
const STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "Read the curated edges, then confirm live.", tool_calls: [] }),
  frame(3, "tool_result", { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "ok", summary: "", result_count: 25, truncated: false }),
  frame(4, "tool_result", { call_id: "c2", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", summary: "", result_count: 1, truncated: false }),
  frame(5, "tool_result", { call_id: "c3", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "ok", summary: "", result_count: 1, truncated: false }),
  frame(6, "token", { text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome [1]. ", marker_ids: ["c-1"] }),
  frame(7, "token", { text: "The MedGen record describes an autosomal dominant pattern [2]. ", marker_ids: ["c-2"] }),
  frame(8, "token", { text: "Biallelic variants are reported in Fanconi anemia group S [3]. ", marker_ids: ["c-3"] }),
  frame(9, "citation", { citation_id: "c-1", display_index: 1, source: "NCBI Gene", source_id: "672", source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: "layer_1_graph", field: "cypher_query", claim_text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome", evidence_kind: "curated assertion", assertion_confidence: "high", population_ancestry_context: null, license: "public domain" }),
  frame(10, "citation", { citation_id: "c-2", display_index: 2, source: "MedGen", source_id: "C0677776", source_url: "https://www.ncbi.nlm.nih.gov/medgen/C0677776", layer: "layer_2_api", field: "ncbi_efetch", claim_text: "The MedGen record describes an autosomal dominant pattern", evidence_kind: "live record", assertion_confidence: "high", population_ancestry_context: null, license: "public domain" }),
  frame(11, "citation", { citation_id: "c-3", display_index: 3, source: "PubMed", source_id: "21990134", source_url: "https://pubmed.ncbi.nlm.nih.gov/21990134/", layer: "layer_3_enrichment", field: "pubtator_annotate", claim_text: "Biallelic variants are reported in Fanconi anemia group S", evidence_kind: "literature", assertion_confidence: "moderate", population_ancestry_context: null, license: "public domain" }),
  frame(12, "trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: true }),
  /*
   * The REAL `done` shape, corrected 2026-08-14 while building T-4.9-01.
   *
   * The first version of this fixture sent `{status, trust_outcome, elapsed_ms,
   * truncated}`, which the client's own validator REJECTS: the wire carries
   * `total_cost_usd`, `total_tool_calls`, `elapsed_ms` and `trust_outcome`, and
   * no status word at all. A fixture authored from a reading of the design
   * rather than the contract is the exact failure LEARNINGS.md records twice
   * for build phase 3.1, and it is why the answer screen rendered a schema
   * error in the 2026-08-14 comparison screenshots.
   */
  frame(13, "done", { total_cost_usd: 0.0031, total_tool_calls: 3, elapsed_ms: 11400, trust_outcome: "answer" }),
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
    expect(strip).toHaveTextContent(/3 tools/);
    expect(strip).toHaveTextContent(/3 layers/);
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
    expect(wrap).toHaveTextContent("3");

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

    await user.click(within(one).getByText(/NCBI Gene 672/));
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
    expect(screen.getByTestId("source-1")).toHaveTextContent(/L1\s*·\s*graph/i);
    expect(screen.getByTestId("source-2")).toHaveTextContent(/L2\s*·\s*live/i);
    expect(screen.getByTestId("source-3")).toHaveTextContent(/L3\s*·\s*literature/i);
  });

  // ---------------------------------------------------------------- F-4.8-D-04
  it("carries the source's identity on the citation chip", async () => {
    const user = userEvent.setup();
    render(<App />);
    await landAnAnswer(user);

    // The prototype's id-bearing chip: the index AND what it points at.
    const chip = screen.getByTestId("citation-1");
    expect(chip).toHaveTextContent("1");
    expect(chip).toHaveTextContent(/Gene\s*672/);
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
    expect(screen.getByTestId("trust-plain")).toHaveTextContent(/3 layers agreed/i);
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
