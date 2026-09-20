/**
 * UI fixes 11.27 (bold) and 11.28 (stagger) in a real browser, 2026-09-14,
 * with the screenshots the bold-and-stagger report shows.
 *
 * Scripted streams, the approach of `answer-layout.spec.ts`: the whole run
 * arrives as ONE response body, which is exactly the burst the pacing exists
 * for, while the app runs its real parsing, pacing, view derivation, reveal
 * and rendering against the e2e harness backend (mock model).
 *
 * WHAT IT COVERS:
 * - a landed Researcher and Plain answer at 1280 and 390: the question is
 *   bold, the Researcher lead's main point is the only bold word in the
 *   claims, and the status word and trust spans are regular weight;
 * - a burst run is shown in stages, in order, each held at least most of its
 *   dwell: Think, Plan, each helper's handoff line, the writing banner, the
 *   first sentence, then the landed answer; with a screenshot mid-handoff at
 *   1280 and 390.
 *
 * WHAT IT DOES NOT COVER: exact dwell values (the unit tests pin those with
 * fake timers; a loaded machine only lengthens gaps, so this spec asserts
 * lower bounds), the 3.5s lag cap, Stop or reduced motion (unit tests), and
 * the live backend's own timing.
 */

import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-09-14_bold_and_stagger");
const QUESTION = "Which diseases are associated with BRCA1?";

let seq = 0;
function frame(type: string, payload: unknown): string {
  seq += 1;
  const envelope = { type, version: "v1", trace_id: "bold-stagger-spec", seq, ts: "2026-09-14T00:00:00Z", payload };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

const DISEASES: [string, string][] = [
  ["Familial cancer of breast", "C0346153"],
  ["Familial breast-ovarian cancer susceptibility 1", "C2676676"],
  ["Pancreatic cancer susceptibility 4", "C3280442"],
  ["Fanconi anemia complementation group S", "C4554406"],
];

function head(): string[] {
  return [
    frame("guard", { passed: true, category: "ok", reason: null }),
    frame("think", { narrative: "Resolving BRCA1.", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
    frame("plan", {
      narrative: "Diseases and literature.",
      tool_calls: [
        { tool: "ncbi_efetch", call_id: "c1", layer: "layer_2_api", persona: "Salk" },
        { tool: "pubtator_annotate", call_id: "c2", layer: "layer_3_enrichment", persona: "Nightingale" },
      ],
    }),
    frame("tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running", persona: "Salk" }),
    frame("tool_start", { call_id: "c2", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "running", persona: "Nightingale" }),
    frame("tool_result", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", persona: "Salk", summary: "", result_count: 4, truncated: false }),
    frame("tool_result", { call_id: "c2", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "ok", persona: "Nightingale", summary: "", result_count: 1, truncated: false }),
  ];
}

const token = (payload: Record<string, unknown>) => frame("token", { marker_ids: [], ...payload });

function stream(mode: "plain" | "researcher"): string {
  const researcher = mode === "researcher";
  return [
    ...head(),
    token({
      kind: "claim",
      text: "NCBI records link BRCA1 to four diseases: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S [1][2][3][4]. ",
      marker_ids: ["cid-1", "cid-2", "cid-3", "cid-4"],
      // What `emphasis_for` sends for Researcher prose: every name, longest first.
      ...(researcher
        ? { emphasis: ["Fanconi anemia complementation group S", "familial breast-ovarian cancer susceptibility 1", "pancreatic cancer susceptibility 4", "familial cancer of breast", "BRCA1"] }
        : {}),
    }),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({
      kind: "claim",
      text: "The literature index holds one BRCA1 gene entity [5]. ",
      marker_ids: ["cid-5"],
      ...(researcher ? { emphasis: ["BRCA1"] } : {}),
    }),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "heading", text: "Diseases linked to BRCA1\n\n" }),
    token({ kind: "table_header", text: "", cells: ["Disease", "MedGen record"] }),
    ...DISEASES.map(([name, id], i) =>
      token({
        kind: "table_row", text: `Disease name: ${name} [${i + 1}]. `, marker_ids: [`cid-${i + 1}`], cells: [name, id],
        ...(researcher ? { emphasis: [name] } : {}),
      }),
    ),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "note", text: "Disease names are shown as NCBI MedGen records them." }),
    ...(researcher ? [] : [token({ kind: "note", text: "This is a research summary, not medical advice." })]),
    ...DISEASES.map(([name, id], i) =>
      frame("citation", {
        citation_id: `cid-${i + 1}`, display_index: i + 1, source: "medgen", source_id: id,
        source_url: `https://www.ncbi.nlm.nih.gov/medgen/${id}`, layer: "layer_2_api", field: "ncbi_efetch",
        claim_text: name, evidence_kind: "curated assertion", assertion_confidence: "high",
        population_ancestry_context: null, license: "public domain",
      }),
    ),
    frame("citation", {
      citation_id: "cid-5", display_index: 5, source: "PubTator3", source_id: "@GENE_BRCA1",
      source_url: "https://www.ncbi.nlm.nih.gov/research/pubtator3/", layer: "layer_3_enrichment",
      field: "pubtator_annotate", claim_text: "BRCA1", evidence_kind: "literature annotation",
      assertion_confidence: "moderate", population_ancestry_context: null, license: "public domain",
    }),
    frame("trust_signal", { outcome: "answer", risk_tier: "high", grounded: true, triangulated: null, scope: "answer" }),
    frame("done", {
      total_cost_usd: 0.02, total_tool_calls: 2, elapsed_ms: 6200, trust_outcome: "answer",
      trust_line: "Based on 2 sources, not yet confirmed",
    }),
  ].join("");
}

/** Records, in page time, the first moment each stage is on screen. */
const STAGE_RECORDER = () => {
  const stages: Record<string, number> = {};
  (window as unknown as { __stages: Record<string, number> }).__stages = stages;
  const probes: [string, string][] = [
    ["think", '[data-testid="step-Think"][data-state="live"]'],
    ["plan", '[data-testid="step-Plan"][data-state="live"]'],
    ["handoff2", '[data-testid="handoff-layer-2"]'],
    ["handoff3", '[data-testid="handoff-layer-3"]'],
    ["searched2", '[data-testid="handoff-layer-2"][data-state="done"]'],
    ["banner", '[data-testid="writing-banner"]'],
    ["sentence", '[data-testid="claim-text-0"]'],
    ["landed", '[data-testid="answer-meta"]'],
  ];
  new MutationObserver(() => {
    for (const [name, selector] of probes) {
      if (!(name in stages) && document.querySelector(selector)) stages[name] = performance.now();
    }
  }).observe(document, { subtree: true, childList: true, attributes: true });
};

async function ask(page: Page, body: string): Promise<void> {
  await page.route("**/v1/query/*/events*", (route) =>
    route.fulfill({ status: 200, headers: { "content-type": "text/event-stream", "cache-control": "no-cache" }, body }),
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
    await page.getByRole("button", { name: "More pages" }).click();
    await page.getByRole("menuitem", { name: /log in/i }).click();
  }
  await page.getByLabel("Email").fill(`stagger-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Log in" }).click();
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(QUESTION);
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

const fontWeight = (page: Page, selector: string) =>
  page.locator(selector).evaluateAll((nodes) => nodes.map((node) => getComputedStyle(node).fontWeight));

for (const width of [1280, 390]) {
  test.describe(`bold and stagger at ${width}px`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 } });

    for (const mode of ["researcher", "plain"] as const) {
      test(`only the title and the main point are bold in the landed ${mode} answer`, async ({ page }) => {
        test.setTimeout(120_000);
        await ask(page, stream(mode));
        await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 60_000 });

        expect(await fontWeight(page, "h1")).toEqual(["700"]);
        const strong = page.getByTestId("claims").locator("strong, b");
        if (mode === "researcher") {
          await expect(strong).toHaveCount(1);
          await expect(strong).toHaveText("BRCA1");
        } else {
          await expect(strong).toHaveCount(0);
        }
        // Populate-check: the status strip and trust line are really there.
        await expect(page.getByTestId("answer-meta")).toContainText("Answered");
        await expect(page.getByTestId("trust-risk")).toContainText("High-risk claim");
        const statusWeights = await fontWeight(page, '[data-testid="answer-meta"], [data-testid="answer-meta"] *');
        expect(statusWeights.every((w) => w === "400")).toBe(true);
        const trustWeights = await fontWeight(page, '[data-testid="trust-line"] [data-testid^="trust-"]');
        expect(trustWeights.length).toBeGreaterThan(0);
        expect(trustWeights.every((w) => w === "400")).toBe(true);

        await page.screenshot({ path: path.join(SHOTS, `w${width}_${mode}_landed.png`), fullPage: true });
      });
    }

    test("a burst run is shown in stages, in order, with a visible handoff", async ({ page }) => {
      test.setTimeout(120_000);
      await page.addInitScript(STAGE_RECORDER);
      await ask(page, stream("plain"));

      // Mid-handoff: both helpers named, the writing banner not yet up.
      await expect(page.getByTestId("handoff-layer-3")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("writing-banner")).toHaveCount(0);
      await page.screenshot({ path: path.join(SHOTS, `w${width}_paced_handoff.png`), fullPage: true });

      await expect(page.getByTestId("writing-banner")).toBeVisible({ timeout: 30_000 });
      await page.screenshot({ path: path.join(SHOTS, `w${width}_paced_writing.png`), fullPage: true });
      await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 60_000 });

      const stages = await page.evaluate(() => (window as unknown as { __stages: Record<string, number> }).__stages);
      const order = ["think", "plan", "handoff2", "handoff3", "searched2", "banner", "sentence", "landed"];
      // Populate-check: every stage was seen.
      expect(Object.keys(stages).sort()).toEqual([...order].sort());
      for (let i = 1; i < order.length; i += 1) {
        expect(stages[order[i]!]!, `${order[i]} after ${order[i - 1]}`).toBeGreaterThanOrEqual(stages[order[i - 1]!]!);
      }
      // Lower bounds a loaded machine cannot break (dwells 700, 700, 350+800, 350, 1500).
      expect(stages.plan! - stages.think!).toBeGreaterThanOrEqual(600);
      expect(stages.handoff2! - stages.plan!).toBeGreaterThanOrEqual(600);
      expect(stages.searched2! - stages.handoff3!).toBeGreaterThanOrEqual(700);
      expect(stages.sentence! - stages.banner!).toBeGreaterThanOrEqual(1300);
    });
  });
}
