/**
 * Superscript citation markers and the "writing the answer" state, in a real
 * browser, with screenshots for the 2026-09-14 report.
 *
 * Product-owner request, 2026-09-14: the boxed inline chips "overwhelm the
 * answer", and the wait should read as a scientist writing.
 *
 * Scripted streams, the same approach as `trust-surface.spec.ts`: the app runs
 * its real parsing, adapter and rendering; only the bytes on the wire are ours.
 *
 * WHAT IT COVERS:
 * - a thirteen-source summary sentence renders ONE range marker, and a
 *   two-source sentence renders a comma list;
 * - the marker card opens on keyboard focus and fits a 390px screen without
 *   sideways scroll;
 * - a stream that has sent sentences but no `done` shows "{Lead} is writing
 *   the answer" and the "writing" mark after the text;
 * - screenshots at 1280 and 390 wide of both states.
 *
 * WHAT IT DOES NOT COVER: that the ellipsis visibly animates (a screenshot is
 * one frame), and the real backend's token timing. The unit files
 * `CitationMarkers.test.tsx` and `WritingState.test.tsx` carry the rules.
 */

import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const TEST_PASSWORD = "Str0ngPassw0rd!";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.resolve(
  __dirname,
  "..",
  "..",
  "testing/Developer/reports/2026-09-14_citations_and_writing",
);

function frame(seq: number, type: string, payload: unknown): string {
  const envelope = {
    type,
    version: "v1",
    trace_id: "citations-and-writing-spec",
    seq,
    ts: "2026-09-14T00:00:00Z",
    payload,
  };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

const DISEASES = [
  "C0346153",
  "C2676676",
  "C3280442",
  "C4554406",
];

function citationFrame(seq: number, n: number): string {
  const layer = n <= 5 ? "layer_2_api" : n === 6 ? "layer_1_graph" : "layer_3_enrichment";
  const isTrial = layer === "layer_3_enrichment";
  const isGraph = layer === "layer_1_graph";
  return frame(seq, "citation", {
    citation_id: `cid-${n}`,
    display_index: n,
    source: isTrial ? "clinicaltrials.gov" : isGraph ? "NCBIGene" : n === 5 ? "gene" : "MedGen",
    source_id: isTrial
      ? `NCT0059${String(n).padStart(4, "0")}`
      : isGraph
        ? "NCBIGene:672"
        : n === 5
          ? "672"
          : `MedGen:${DISEASES[(n - 1) % DISEASES.length]}`,
    source_url: isTrial
      ? `https://clinicaltrials.gov/study/NCT0059${String(n).padStart(4, "0")}`
      : isGraph || n === 5
        ? "https://www.ncbi.nlm.nih.gov/gene/672"
        : `https://www.ncbi.nlm.nih.gov/medgen/${DISEASES[(n - 1) % DISEASES.length]}`,
    layer,
    field: isTrial ? "clinicaltrials_search" : isGraph ? "cypher_query" : "ncbi_efetch",
    claim_text: "",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  });
}

const HEAD = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "Look up disease records.", tool_calls: [] }),
  frame(3, "tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running" }),
  frame(4, "tool_result", {
    call_id: "c1",
    tool: "ncbi_efetch",
    layer: "layer_2_api",
    status: "ok",
    summary: "",
    result_count: 13,
    truncated: false,
  }),
];

const THIRTEEN = Array.from({ length: 13 }, (_, i) => i + 1);

const TOKENS = [
  frame(5, "token", {
    text:
      "Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian " +
      "cancer susceptibility 1, Pancreatic cancer susceptibility 4 and Fanconi anemia " +
      `complementation group S ${THIRTEEN.map((n) => `[${n}]`).join("")}. `,
    marker_ids: THIRTEEN.map((n) => `cid-${n}`),
  }),
  frame(6, "token", {
    text: 'The gene symbol "BRCA1" is recorded in NCBI Gene [5][6]. ',
    marker_ids: ["cid-5", "cid-6"],
  }),
  frame(7, "token", {
    text: "Clinical trial name: Germline BRCA1 and BRCA2 Mutations in Jewish Women Affected by Breast Cancer [7]. ",
    marker_ids: ["cid-7"],
  }),
];

const LANDED_STREAM = [
  ...HEAD,
  ...TOKENS,
  ...THIRTEEN.map((n) => citationFrame(7 + n, n)),
  frame(21, "trust_signal", { outcome: "answer", risk_tier: "high", grounded: true, triangulated: null }),
  frame(22, "done", {
    total_cost_usd: 0.02,
    total_tool_calls: 1,
    elapsed_ms: 5800,
    trust_outcome: "answer",
  }),
].join("");

/** Sentences sent, no citation frames and no `done`: the run stays in Write. */
const WRITING_STREAM = [...HEAD, ...TOKENS.slice(0, 2)].join("");

async function ask(page: Page, body: string): Promise<void> {
  await page.route("**/v1/query/*/events*", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body,
    }),
  );
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
  }
  const nav = page.getByRole("navigation", { name: /main/i });
  const login = nav.getByRole("button", { name: /log in/i });
  if (await login.isVisible().catch(() => false)) {
    await login.click();
  } else {
    // Below 720px the nav collapses into its overflow menu.
    await page.getByRole("button", { name: "More pages" }).click();
    await page.getByRole("menuitem", { name: /log in/i }).click();
  }
  await page.getByLabel("Email").fill(`cite-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

async function noSidewaysScroll(page: Page): Promise<void> {
  const [scroll, client] = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    document.documentElement.clientWidth,
  ]);
  expect(scroll, `the page scrolls sideways: ${scroll} > ${client}`).toBeLessThanOrEqual(client);
}

for (const width of [1280, 390]) {
  test.describe(`at ${width}px`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 } });

    test("a cited answer shows quiet superscript markers and a card on focus", async ({ page }) => {
      await ask(page, LANDED_STREAM);
      await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });

      // Thirteen sources on one sentence: ONE marker, a range.
      const range = page.getByTestId("citation-group-1");
      await expect(range).toBeVisible();
      await expect(range).toContainText("1–13");
      await expect(page.getByTestId("citation-markers-0").getByRole("button")).toHaveCount(1);
      // Two sources: a comma list of two markers.
      await expect(page.getByRole("button", { name: /^source 5, layer 2$/i })).toBeVisible();
      await expect(page.getByRole("button", { name: /^source 6, layer 1$/i })).toBeVisible();
      await noSidewaysScroll(page);
      await page.screenshot({ path: path.join(SHOTS, `w${width}_cited_answer.png`), fullPage: true });

      await range.focus();
      const card = page.getByTestId("cite-popover-1");
      await expect(card).toBeVisible();
      await expect(card.getByTestId("cite-popover-row-13")).toBeAttached();
      const box = await card.boundingBox();
      expect(box, "the card has no box").not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      await noSidewaysScroll(page);
      await page.screenshot({ path: path.join(SHOTS, `w${width}_marker_card_open.png`) });
    });

    test("the Write step reads as the lead writing the answer", async ({ page }) => {
      await ask(page, WRITING_STREAM);
      const caption = page.getByTestId("persona-caption");
      await expect(caption).toBeVisible({ timeout: 30_000 });
      await expect(caption).toContainText(/is writing the answer\.\.\./);
      const mark = page.getByTestId("streaming-writing-indicator");
      await expect(mark).toBeVisible();
      await expect(mark).toContainText("writing...");
      // Follow-up, 2026-09-14: citation frames have not arrived in this
      // stream, so no raw "[1][2]" may show, and the sentences read as
      // pending rather than uncited. Populate-check first.
      const claims = page.getByTestId("claims");
      await expect(claims).toContainText("Found 4 disease records for BRCA1");
      expect(await claims.innerText()).not.toMatch(/\[\d+\]/);
      await expect(page.getByTestId("citation-pending-0")).toBeAttached();
      await expect(page.getByTestId("spine-segment-0")).toHaveAttribute("data-layer", "pending");
      await expect(page.getByText("This sentence has no source.")).toHaveCount(0);
      await noSidewaysScroll(page);
      await page.screenshot({ path: path.join(SHOTS, `w${width}_write_step.png`), fullPage: true });
    });
  });
}
