/**
 * T-4.16-09: something in this repository finally LOOKS AT a tool chip.
 *
 * Build phase 4.16's top defect was that `core/graph.py` never emitted
 * `tool_start` or `tool_result`, so the Act step was invisible on every
 * surface and no tool chip had rendered on any run since build phase 4.8
 * built one. Two things let that survive:
 *
 * - No Playwright spec had ever emitted a `tool_start`. Exactly one emitted
 *   a `tool_result` (`trust-surface.spec.ts`), and nothing at all asserted
 *   a rendered chip.
 * - `useRunView`'s own docstring PREDICTED the consequence in 2026-08-12,
 *   "if the agent emits no `tool_start`, no tool chip appears", and it was
 *   read as a design principle rather than as a live symptom.
 *
 * WHAT THIS PROVES, AND WHAT IT DOES NOT. It drives a SCRIPTED stream, so
 * it proves the renderer turns tool frames into chips and into a truthful
 * meta line. It does NOT prove the backend emits those frames. Build phase
 * 8.5 deleted the dedicated premise/mutation pair that used to own that
 * half (`test_phase_4_16_premise.py` and `test_phase_4_16_mutation.py`,
 * card 37); `act_node` never emitting `tool_start` or `tool_result` is now
 * caught incidentally by several backend suites that happen to assert on
 * those event types (`test_bare_topic_clarification.py`,
 * `test_breadth_wiring.py`, `test_clarification.py`,
 * `test_layer_handoff.py`), not by a dedicated gate. Whether the two
 * frames arrive LIVE rather than buffered at Act's return (the build
 * phase 4.16 timing regression) is covered only by the product reviewer's
 * time-to-answer measure, per the phase 8.5 product-owner ruling
 * (DECISIONS.md, 2026-09-25, card 37), not by any test. The two halves
 * that remain are deliberately in different languages against different
 * surfaces, and NEITHER alone would have caught the shipped defect: the
 * producer side cannot see the chip, and this cannot see a silent
 * producer.
 *
 * WHY NOT DRIVE THE REAL BACKEND HERE, which was tried first and abandoned
 * with the reason recorded rather than the attempt hidden. The e2e mock
 * replaces the outbound MODEL call only; entity resolution and the tools
 * themselves are real, so `plan_node` needs a live NCBI lookup to resolve
 * BRCA1 before it can plan any tool at all. Against the mock backend the
 * answer came back "0 tools, 0 sources", and raising
 * `PER_QUERY_COST_CAP_USD` did not change it, ruling out the cost cap. So
 * the browser suite cannot reach a real tool dispatch today. That is a
 * HARNESS GAP with an owner in `tracker/phase_4.16.md`, not something to
 * paper over by asserting something weaker and calling it end to end.
 *
 * MUTATION-PROVEN before commit. Deleting the four tool frames from the
 * scripted stream reproduces the deployed meta line character for
 * character, "0 tools, 1 source from 1 layer", and turns the first arm red
 * while the chip arm stays green. That asymmetry is the point: the chip arm
 * cannot see a missing Act step, which is why both exist.
 */

import { expect, test, type Page } from "@playwright/test";

function frame(seq: number, type: string, payload: unknown): string {
  const envelope = {
    type,
    version: "v1",
    trace_id: "tool-chip-spec",
    seq,
    ts: "2026-08-25T00:00:00Z",
    payload,
  };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

/**
 * Two tools across two layers, each STARTED and then RESULTED, which is the
 * shape `act_node` now produces for the reported BRCA1 question.
 *
 * `status: "running"` on the start frames is not decoration: it is the enum
 * value T-4.16-01 had to add, and a client that rejects it drops the frame.
 * `parseAgentEvent` THROWS on a payload its guard refuses, which
 * `useAgentRun` turns into an aborted stream, so a regression there would
 * fail this spec with no answer at all rather than with a missing chip.
 */
const SCRIPTED_STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "Query the graph, then confirm live.", tool_calls: [] }),
  frame(3, "tool_start", {
    call_id: "c1",
    tool: "cypher_query",
    layer: "layer_1_graph",
    status: "running",
  }),
  frame(4, "tool_result", {
    call_id: "c1",
    tool: "cypher_query",
    layer: "layer_1_graph",
    status: "ok",
    summary: "4 rows",
    result_count: 4,
    truncated: false,
  }),
  frame(5, "tool_start", {
    call_id: "c2",
    tool: "ncbi_efetch",
    layer: "layer_2_api",
    status: "running",
  }),
  frame(6, "tool_result", {
    call_id: "c2",
    tool: "ncbi_efetch",
    layer: "layer_2_api",
    status: "ok",
    summary: "1 record",
    result_count: 1,
    truncated: false,
  }),
  frame(7, "token", {
    text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome [1]. ",
    marker_ids: ["cid-1"],
  }),
  frame(8, "citation", {
    citation_id: "cid-1",
    display_index: 1,
    source: "NCBIGene",
    // A FULL CURIE, the Layer 1 shape, so this also guards T-4.16-03's
    // chip-label fix end to end rather than only in its unit test.
    source_id: "NCBIGene:672",
    source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
    layer: "layer_1_graph",
    field: "name",
    claim_text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome",
    evidence_kind: "primary_assertion",
    assertion_confidence: "asserted",
    population_ancestry_context: null,
    license: "public_domain_us_gov",
  }),
  frame(9, "trust_signal", {
    outcome: "answer",
    risk_tier: "high",
    grounded: true,
    triangulated: true,
  }),
  frame(10, "done", {
    total_cost_usd: 0,
    total_tool_calls: 2,
    elapsed_ms: 11400,
    trust_outcome: "answer",
  }),
].join("");

async function runScriptedAnswer(page: Page): Promise<void> {
  await page.route("**/v1/query/*/events*", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: SCRIPTED_STREAM,
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
  await main.getByRole("textbox", { name: /question/i }).fill("What gene is BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
}

test("the answer reports the tools that ran, never zero", async ({ page }) => {
  await runScriptedAnswer(page);

  const text = (await page.getByTestId("answer-meta").textContent()) ?? "";

  // POPULATE-CHECK. The meta line only mentions tools when the run reports
  // at least one, so without this the arm below could not tell a wrong
  // count from a meta line that never discusses tools at all.
  expect(
    text,
    `populate-check failed: the meta line says nothing about tools. Saw: ${text}`,
  ).toMatch(/tool/i);

  expect(
    text,
    `the answer reports no tools on a run that ran two. This is exactly what ` +
      `the product owner saw on the deployed demo: "0 tools" beside five ` +
      `sources from two layers. Saw: ${text}`,
  ).not.toMatch(/\b0 tools\b/);
  expect(text).toMatch(/\b2 tools\b/);
});

test("a citation chip never repeats its own source", async ({ page }) => {
  await runScriptedAnswer(page);

  const chip = page.getByTestId("citation-1");
  await expect(chip, "the citation chip did not render at all").toBeVisible();

  /*
   * REQUIREMENT CHANGE, 2026-09-14. The source's name used to be printed on
   * the chip itself. At the product owner's request the inline citation is
   * now a small superscript number, and the name lives in the card the
   * number opens on focus. The T-4.16-03 guard is unchanged; it reads the
   * card rather than the chip, because that is where the name now is.
   */
  await chip.focus();
  const card = page.getByTestId("cite-popover-1");
  await expect(card, "focusing the citation marker opened no card").toBeVisible();
  const label = (await card.textContent()) ?? "";
  expect(label, `populate-check failed: the chip carries no text. Saw: ${label}`).toMatch(
    /672/,
  );
  expect(
    label,
    `the chip repeats its source: T-4.16-03's defect, seen live as ` +
      `"MedGen MedGen:C0346153". Saw: ${label}`,
  ).not.toMatch(/NCBIGene\s*NCBIGene:/);
});
