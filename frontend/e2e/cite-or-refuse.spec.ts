/**
 * W-thread-3, `testing/Developer/Developer_workflows.md`'s Tier 1 row: "Tie every claim
 * to a source, or refuse and say so. No answering from model priors." This
 * repository's own `production-standards` rule calls cite-or-refuse "the
 * single highest-leverage correctness gate" in the system, and a confident
 * wrong answer is worse than a crash here.
 *
 * WHAT WAS ALREADY COVERED, AND WHAT WAS NOT. `trust-surface.spec.ts`
 * proves the CITE half: a claim with a marker_id gets a citation chip and a
 * coloured spine segment, and an uncited claim renders grey with the
 * screen-reader text "This sentence has no source." That is the case where
 * SOME claims are grounded and one is not.
 *
 * Nothing anywhere exercised the REFUSE half: the case where retrieval
 * produced nothing groundable at all, and the whole answer must refuse
 * rather than render as prose. `core/graph.py`'s `write_node` has two
 * refusal sites for this (a general no-data refuse, and an earlier exit
 * when the only candidate entity never resolved), and a 2026-09-05 fix
 * (`useRunView.ts`'s `answerRefusalSignal`, unit-tested in
 * `useRunView.refusal.test.ts`) routes both into the SAME `refusal` field a
 * guardrail refusal already uses, specifically so a no-data refusal can
 * never reach the claims list as an ordinary sentence. This spec is the
 * first thing to look at a BROWSER rendering of that fix, the same way
 * `trust-surface.spec.ts` is the first thing to look at a rendered
 * citation.
 *
 * COVERAGE STATED, per `goal-contracts.md`'s requirement that a verify
 * surface declare its own gaps.
 *
 * Exercised here:
 *   - a general no-data refusal (tool ran, produced nothing groundable)
 *   - an unresolved-entity refusal (no tool ever ran)
 *   - a genuinely grounded, cited answer, to prove the fix has no false
 *     positive: a real answer must never be swallowed into the refusal
 *     notice.
 *
 * Deliberately NOT exercised:
 *   - a guardrail refusal (the question itself refused before Think). That
 *     is a different code path (`guard` event carrying `passed: false`),
 *     already reachable through `refusal` by construction since build
 *     phase 4.8; this spec is scoped to the newer no-data half.
 *   - the actual grounding-pass DECISION (whether a given synthesis
 *     narrative should count as grounded). That is `synthesis/trust.py`'s
 *     job, covered by `test_write_grounding_premise.py` and
 *     `test_grounding_hardening.py` in the Python suite. This spec starts
 *     from the decision already made (a `trust_signal` on the wire) and
 *     checks only what the BROWSER does with it.
 *   - why the mock backend cannot produce this stream on its own: its one
 *     real code path is the cost-cap partial result, so the SSE endpoint is
 *     intercepted and served a scripted stream, the same technique
 *     `trust-surface.spec.ts` and `tool-chip.spec.ts` already use. The app
 *     is untouched; only the bytes on the wire are ours.
 */

import { expect, test, type Page } from "@playwright/test";

function frame(seq: number, type: string, payload: unknown): string {
  const envelope = {
    type,
    version: "v1",
    trace_id: "cite-or-refuse-spec",
    seq,
    ts: "2026-09-05T00:00:00Z",
    payload,
  };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

/**
 * A general no-data refusal. A tool ran (so the run is not an early exit)
 * and produced results, but synthesis could not ground an answer in them,
 * so `write_node` ships the refuse sentence as a bare `token` (no
 * `marker_ids`, there is nothing to bind it to) plus the Section 8.4
 * `trust_signal` that carries the SAME message and a fallback link. Text
 * taken verbatim from `useRunView.refusal.test.ts`'s own fixture, which
 * cites `synthesis/refuse.py`'s `REFUSE_MESSAGE`/`FALLBACK_BASE` as its
 * source, so this spec is not inventing new copy either.
 */
const REFUSE_MESSAGE =
  "I could not find grounded evidence for this. Try NCBI's cross-database search:";
const FALLBACK_LINK = "https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA9";
const REFUSAL_TOKEN_TEXT = `${REFUSE_MESSAGE} ${FALLBACK_LINK}`;

const NO_DATA_REFUSAL_STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "Query the graph.", tool_calls: [] }),
  frame(3, "tool_result", {
    call_id: "c1",
    tool: "cypher_query",
    layer: "layer_1_graph",
    status: "ok",
    summary: "",
    result_count: 3,
    truncated: false,
  }),
  // The refuse sentence itself, as an ordinary token with no marker_ids.
  // Nothing here binds it to a claim, which is the whole point.
  frame(4, "token", { text: REFUSAL_TOKEN_TEXT, marker_ids: [] }),
  frame(5, "trust_signal", {
    outcome: "refuse",
    risk_tier: "unknown",
    grounded: false,
    triangulated: null,
    scope: "answer",
    message: REFUSE_MESSAGE,
    fallback_link: FALLBACK_LINK,
  }),
  frame(6, "done", {
    total_cost_usd: 0.01,
    total_tool_calls: 1,
    elapsed_ms: 800,
    trust_outcome: "refuse",
  }),
].join("");

/**
 * The unresolved-entity refusal: `plan_node` already determined the only
 * candidate entity does not resolve, so `act_node` never runs at all. No
 * `tool_result` frame exists in this stream, which is the shape
 * `core/graph.py`'s early-exit branch actually produces.
 */
const UNRESOLVED_MESSAGE =
  "I could not identify that gene. NCBI has no record matching the name in " +
  "your question, so no graph query was attempted.";
const UNRESOLVED_LINK = "https://www.ncbi.nlm.nih.gov/search/all/?term=NOTAGENE";
const UNRESOLVED_TOKEN_TEXT = `${UNRESOLVED_MESSAGE} ${UNRESOLVED_LINK}`;

const UNRESOLVED_ENTITY_REFUSAL_STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "",
    query_class: "lookup",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "", tool_calls: [] }),
  frame(3, "token", { text: UNRESOLVED_TOKEN_TEXT, marker_ids: [] }),
  frame(4, "trust_signal", {
    outcome: "refuse",
    risk_tier: "unknown",
    grounded: false,
    triangulated: null,
    scope: "answer",
    message: UNRESOLVED_MESSAGE,
    fallback_link: UNRESOLVED_LINK,
  }),
  frame(5, "done", {
    total_cost_usd: 0.0,
    total_tool_calls: 0,
    elapsed_ms: 300,
    trust_outcome: "refuse",
  }),
].join("");

/** A genuinely grounded, cited answer. The false-positive guard. */
const GROUNDED_ANSWER_STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "",
    query_class: "lookup",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "", tool_calls: [] }),
  frame(3, "tool_result", {
    call_id: "c1",
    tool: "cypher_query",
    layer: "layer_1_graph",
    status: "ok",
    summary: "",
    result_count: 1,
    truncated: false,
  }),
  frame(4, "token", {
    text: "BRCA1 is associated with hereditary breast cancer [1].",
    marker_ids: ["cid-1"],
  }),
  frame(5, "citation", {
    citation_id: "cid-1",
    display_index: 1,
    source: "NCBI Gene",
    source_id: "672",
    source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
    layer: "layer_1_graph",
    field: "cypher_query",
    claim_text: "BRCA1 is associated with hereditary breast cancer",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  }),
  frame(6, "trust_signal", {
    outcome: "answer",
    risk_tier: "low",
    grounded: true,
    triangulated: null,
    scope: "claim",
  }),
  frame(7, "trust_signal", {
    outcome: "answer",
    risk_tier: "low",
    grounded: true,
    triangulated: null,
    scope: "answer",
  }),
  frame(8, "done", {
    total_cost_usd: 0.02,
    total_tool_calls: 1,
    elapsed_ms: 900,
    trust_outcome: "answer",
  }),
].join("");

async function askWithScriptedStream(page: Page, stream: string, question: string): Promise<void> {
  await page.route("**/v1/query/*/events*", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: stream,
    }),
  );

  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }

  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
}

test.describe("cite or refuse", () => {
  test("a no-data refusal renders as a refusal notice, never as a claim", async ({ page }) => {
    await askWithScriptedStream(page, NO_DATA_REFUSAL_STREAM, "Is BRCA9 associated with any disease?");

    // The refusal block, built from the SAME trust_signal fields a
    // guardrail refusal would use.
    const notice = page.getByTestId("answer-refusal");
    await expect(notice).toBeVisible();
    await expect(notice).toContainText(REFUSE_MESSAGE);
    await expect(notice).toContainText(FALLBACK_LINK);

    // R13, R14 and R44 (2026-09-12). The label a reader scans first, the
    // address as a real link rather than characters on a page, and no red
    // verdict beside either: a refusal is a first-class state, not an
    // error. The two assertions above still hold unchanged, because the
    // anchor's visible text IS the address.
    await expect(notice).toContainText("No answer found in NCBI records");
    const fallback = notice.getByRole("link", { name: FALLBACK_LINK });
    await expect(fallback).toHaveAttribute("href", FALLBACK_LINK);
    await expect(fallback).toHaveAttribute("rel", "noopener noreferrer");
    await expect(page.getByTestId("trust-risk")).toHaveCount(0);
    await expect(page.getByTestId("answer-meta")).not.toContainText(/refused/i);

    // THE WHOLE POINT: no claim, cited or uncited, exists on the spine.
    // Before the 2026-09-05 fix this exact token rendered as an ordinary
    // uncited claim, per `testing/Developer/Developer_workflows.md`'s defect #5.
    await expect(page.getByTestId(/^claim-text-/)).toHaveCount(0);
    await expect(page.getByTestId(/^citation-\d+$/)).toHaveCount(0);

    // And the refuse sentence itself must not ALSO appear as ordinary prose
    // outside the notice, which would be the same double-rendering defect
    // `query-stream-and-stop.spec.ts` already guards for the cap note.
    const bodyText = await page.getByRole("main").innerText();
    const occurrences = bodyText.split(REFUSE_MESSAGE).length - 1;
    expect(occurrences, "the refusal sentence rendered more than once").toBe(1);
  });

  test("an unresolved-entity refusal also renders as a refusal notice, never as a claim", async ({
    page,
  }) => {
    await askWithScriptedStream(
      page,
      UNRESOLVED_ENTITY_REFUSAL_STREAM,
      "What gene is NOTAGENE?",
    );

    const notice = page.getByTestId("answer-refusal");
    await expect(notice).toBeVisible();
    await expect(notice).toContainText(UNRESOLVED_MESSAGE);
    await expect(notice).toContainText(UNRESOLVED_LINK);

    // The two answer-level refusal shapes are not distinguishable on the
    // wire, so they share one label; the sentence above carries the
    // difference. The address is a link here too (R14).
    await expect(notice).toContainText("No answer found in NCBI records");
    await expect(notice.getByRole("link", { name: UNRESOLVED_LINK })).toHaveAttribute(
      "href",
      UNRESOLVED_LINK,
    );
    await expect(page.getByTestId("trust-risk")).toHaveCount(0);

    await expect(page.getByTestId(/^claim-text-/)).toHaveCount(0);

    // No tool ever ran on this path (`act_node` never dispatched), so no
    // tool chip and no source card exist either. Answering from priors
    // would have to invent one of these to look grounded.
    await expect(page.getByTestId(/^source-\d+$/)).toHaveCount(0);
  });

  test("a genuinely grounded, cited answer is never swallowed into the refusal notice", async ({
    page,
  }) => {
    // The false-positive guard: `answerRefusalSignal` matches on
    // `scope === "answer" && outcome === "refuse"`, and this stream's two
    // trust_signal frames are both `outcome: "answer"`. A check that only
    // ever asserted the refuse cases above could not tell a correct fix
    // from one that refuses everything.
    await askWithScriptedStream(page, GROUNDED_ANSWER_STREAM, "What gene is BRCA1?");

    await expect(page.getByTestId("answer-refusal")).toHaveCount(0);
    await expect(page.getByTestId("citation-1")).toBeVisible();
    await expect(page.getByTestId(/^claim-text-\d+$/)).toHaveCount(1);
  });
});
