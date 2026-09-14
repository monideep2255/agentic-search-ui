/**
 * The approved answer layout in a real browser, 2026-09-14, with the
 * screenshots the report compares against `design/Main.dc.html`,
 * `Researcher.dc.html`, `Mobile.dc.html` and `Streaming.dc.html`.
 *
 * Scripted streams, the same approach as `citations-and-writing.spec.ts`: the
 * app runs its real parsing, view derivation, reveal and rendering against the
 * e2e harness backend (mock model); only the event bytes are ours, shaped like
 * a BRCA1 answer with prose, a disease table, a trials table and notes.
 *
 * WHAT IT COVERS:
 * - the landed answer at 1280 and 390, Plain language and Researcher shapes,
 *   with no sideways scroll and no axe violations;
 * - copying the answer (a real selection and the clipboard) yields prose with
 *   no "Source N, layer L" strings, and innerText agrees;
 * - findings-tail record lines render as a record block, never inline;
 * - the writing banner during the silent gap after Act, and the answer
 *   building one sentence at a time under it.
 *
 * WHAT IT DOES NOT COVER: that the dots or rise animate (a screenshot is one
 * frame), or the real backend's timing.
 */

import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-09-14_answer_layout");

let seq = 0;
function frame(type: string, payload: unknown): string {
  seq += 1;
  const envelope = { type, version: "v1", trace_id: "answer-layout-spec", seq, ts: "2026-09-14T00:00:00Z", payload };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

const DISEASES: [string, string][] = [
  ["Familial cancer of breast", "C0346153"],
  ["Familial breast-ovarian cancer susceptibility 1", "C2676676"],
  ["Pancreatic cancer susceptibility 4", "C3280442"],
  ["Fanconi anemia complementation group S", "C4554406"],
];
const TRIALS: [string, string][] = [
  ["Germline BRCA1 and BRCA2 mutations in Jewish women affected by breast cancer", "NCT00590109"],
  ["BRCA1 haploinsufficiency and gene expression", "NCT00597987"],
  ["Treatment customized according to RAP80 and BRCA1 in advanced lung carcinoma", "NCT00617656"],
  ["Letrozole in preventing breast cancer in postmenopausal women with a BRCA1 or BRCA2 mutation", "NCT00673335"],
  ["Recombinant human chorionic gonadotropin in preventing breast cancer in premenopausal women with BRCA1 mutations", "NCT00700778"],
];

function citations(): string[] {
  const out: string[] = [];
  DISEASES.forEach(([name, id], i) =>
    out.push(
      frame("citation", {
        citation_id: `cid-${i + 1}`, display_index: i + 1, source: "medgen", source_id: id,
        source_url: `https://www.ncbi.nlm.nih.gov/medgen/${id}`, layer: "layer_2_api", field: "ncbi_efetch",
        claim_text: name, evidence_kind: "curated assertion", assertion_confidence: "high",
        population_ancestry_context: null, license: "public domain",
      }),
    ),
  );
  out.push(
    frame("citation", {
      citation_id: "cid-5", display_index: 5, source: "gene", source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: "layer_2_api", field: "ncbi_efetch",
      claim_text: "BRCA1", evidence_kind: "curated assertion", assertion_confidence: "high",
      population_ancestry_context: null, license: "public domain",
    }),
    frame("citation", {
      citation_id: "cid-6", display_index: 6, source: "PubTator3", source_id: "@GENE_BRCA1",
      source_url: "https://www.ncbi.nlm.nih.gov/research/pubtator3/", layer: "layer_3_enrichment",
      field: "pubtator_annotate", claim_text: "BRCA1", evidence_kind: "literature annotation",
      assertion_confidence: "moderate", population_ancestry_context: null, license: "public domain",
    }),
  );
  TRIALS.forEach(([name, id], i) =>
    out.push(
      frame("citation", {
        citation_id: `cid-${i + 7}`, display_index: i + 7, source: "clinicaltrials.gov", source_id: id,
        source_url: `https://clinicaltrials.gov/study/${id}`, layer: "layer_3_enrichment",
        field: "clinicaltrials_search", claim_text: name, evidence_kind: "registry record",
        assertion_confidence: "high", population_ancestry_context: null, license: "public domain",
      }),
    ),
  );
  return out;
}

function head(): string[] {
  return [
    frame("guard", { passed: true, category: "ok", reason: null }),
    frame("think", { narrative: "Resolving BRCA1.", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
    frame("plan", {
      narrative: "Diseases, the gene and trials.",
      tool_calls: [
        { tool: "ncbi_efetch", call_id: "c1", layer: "layer_2_api", persona: "Salk" },
        { tool: "pubtator_annotate", call_id: "c2", layer: "layer_3_enrichment", persona: "Nightingale" },
      ],
    }),
    frame("tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running", persona: "Salk" }),
    frame("tool_start", { call_id: "c2", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "running", persona: "Nightingale" }),
    frame("tool_result", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", persona: "Salk", summary: "", result_count: 5, truncated: false }),
    frame("tool_result", { call_id: "c2", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "ok", persona: "Nightingale", summary: "", result_count: 6, truncated: false }),
  ];
}

const token = (payload: Record<string, unknown>) => frame("token", { marker_ids: [], ...payload });
const markers = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => `cid-${from + i}`);
const brackets = (from: number, to: number) => markers(from, to).map((id) => `[${id.slice(4)}]`).join("");

function answerTokens(mode: "plain" | "researcher"): string[] {
  const researcher = mode === "researcher";
  const out = [
    token({
      kind: "claim",
      text: researcher
        ? `NCBI records link BRCA1 (NCBI Gene 672) to four MedGen disease concepts, spanning hereditary breast and ovarian cancer susceptibility (familial cancer of breast, familial breast-ovarian cancer susceptibility 1), pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S ${brackets(1, 5)}. `
        : `NCBI records link BRCA1 to four diseases: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S ${brackets(1, 4)}. `,
      marker_ids: researcher ? markers(1, 5) : markers(1, 4),
      emphasis: ["BRCA1", "familial cancer of breast", "familial breast-ovarian cancer susceptibility 1", "pancreatic cancer susceptibility 4", "Fanconi anemia complementation group S"],
    }),
    // Two lead paragraphs, as the mockups draw them.
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({
      kind: "claim",
      text: researcher
        ? `The PubTator3 literature index holds one BRCA1 gene entity [6], and ClinicalTrials.gov lists five studies that name BRCA1, from germline mutation cohorts to breast cancer prevention trials in carriers ${brackets(7, 11)}. `
        : `Each disease below comes from its own MedGen record, and five clinical trials that name BRCA1 are listed after them ${brackets(7, 11)}. `,
      marker_ids: researcher ? ["cid-6", ...markers(7, 11)] : markers(7, 11),
    }),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "heading", text: "Diseases linked to BRCA1\n\n" }),
    token({
      kind: "table_header", text: "",
      cells: researcher ? ["Disease", "MedGen record", "Source layer"] : ["Disease", "MedGen record"],
    }),
    ...DISEASES.map(([name, id], i) =>
      token({
        kind: "table_row", text: `Disease name: ${name} [${i + 1}]. `, marker_ids: [`cid-${i + 1}`],
        cells: researcher ? [name, id, "L2 · live"] : [name, id],
      }),
    ),
  ];
  if (researcher) {
    out.push(
      token({ kind: "heading", text: "Gene and literature records\n\n" }),
      token({ kind: "table_header", text: "", cells: ["Record", "Identifier", "Source layer"] }),
      token({ kind: "table_row", text: "Gene symbol: BRCA1 [5]. ", marker_ids: ["cid-5"], cells: ["BRCA1, BRCA1 DNA repair associated", "NCBI Gene 672", "L2 · live"] }),
      token({ kind: "table_row", text: "Literature entity name: BRCA1 [6]. ", marker_ids: ["cid-6"], cells: ["BRCA1 gene entity in the literature index", "@GENE_BRCA1", "L3 · literature"] }),
    );
  } else {
    out.push(
      token({ kind: "heading", text: "The gene\n\n" }),
      token({ kind: "claim", text: "BRCA1 is NCBI Gene 672 [5], with a matching entry in the PubTator3 literature index [6]. ", marker_ids: ["cid-5", "cid-6"] }),
    );
  }
  out.push(
    token({ kind: "heading", text: "Related clinical trials\n\n" }),
    token({ kind: "table_header", text: "", cells: ["Trial", "Study"] }),
    ...TRIALS.map(([name, id], i) =>
      token({ kind: "table_row", text: `Clinical trial name: ${name} [${i + 7}]. `, marker_ids: [`cid-${i + 7}`], cells: [name, id] }),
    ),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "note", text: researcher ? "Disease names are the MedGen concept titles, shown in reading order." : "Disease names are shown as NCBI MedGen records them." }),
    token({ kind: "note", text: "The trials are the five ClinicalTrials.gov studies that match BRCA1, in study-number order." }),
  );
  if (!researcher) out.push(token({ kind: "note", text: "This is a research summary, not medical advice." }));
  return out;
}

function landedStream(mode: "plain" | "researcher"): string {
  return [
    ...head(),
    ...answerTokens(mode),
    ...citations(),
    frame("trust_signal", { outcome: "answer", risk_tier: "high", grounded: true, triangulated: null, scope: "answer" }),
    frame("done", {
      total_cost_usd: 0.02, total_tool_calls: 2, elapsed_ms: 6200, trust_outcome: "answer",
      trust_line: "Based on 4 sources, not yet confirmed",
    }),
  ].join("");
}

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
  await page.getByLabel("Email").fill(`layout-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
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
  test.describe(`answer layout at ${width}px`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 } });

    for (const mode of ["plain", "researcher"] as const) {
      test(`the landed ${mode} answer matches the approved structure`, async ({ page }) => {
        await ask(page, landedStream(mode));
        await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });

        // Prose, headings, record blocks, notes, then Sources and the trust line.
        await expect(page.getByTestId("claim-text-0")).toContainText("NCBI records link");
        await expect(page.getByRole("heading", { name: "Diseases linked to BRCA1" })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Related clinical trials" })).toBeVisible();
        await expect(page.getByTestId("answer-notes")).toBeVisible();
        await expect(page.getByTestId("sources-disclosure")).toBeVisible();
        await expect(page.getByTestId("trust-line")).toContainText("Based on 4 sources, not yet confirmed");
        if (mode === "plain") await expect(page.getByTestId("answer-medical-note")).toBeVisible();
        else await expect(page.getByTestId("answer-medical-note")).toHaveCount(0);
        if (width === 390) {
          await expect(page.getByTestId("answer-table")).toHaveCount(0);
          await expect(page.getByTestId("answer-records-0").locator("li")).toHaveCount(DISEASES.length);
        } else {
          await expect(page.getByTestId("answer-table")).toHaveCount(mode === "plain" ? 2 : 3);
        }
        await expect(page.getByTestId(/^spine-segment-/)).toHaveCount(0);
        await noSidewaysScroll(page);

        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();
        expect(results.violations).toEqual([]);

        await page.screenshot({ path: path.join(SHOTS, `w${width}_${mode}_landed.png`), fullPage: true });
      });
    }
  });
}

test.describe("copying the answer", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("yields prose with no 'Source N, layer L' strings", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await ask(page, landedStream("plain"));
    await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
    // The names are still there for assistive technology.
    await expect(page.getByRole("button", { name: /^Sources 1 to 4: Source 1, layer 2/ })).toBeVisible();

    const selected = await page.evaluate(() => {
      const claims = document.querySelector('[data-testid="claims"]')!;
      const selection = window.getSelection()!;
      selection.removeAllRanges();
      const range = document.createRange();
      range.selectNodeContents(claims);
      selection.addRange(range);
      return selection.toString();
    });
    await page.keyboard.press("ControlOrMeta+c");
    const clipboard = await page.evaluate(() => navigator.clipboard.readText());
    const inner = await page.getByTestId("claims").innerText();

    for (const [label, text] of [["selection", selected], ["clipboard", clipboard], ["innerText", inner]] as const) {
      expect(text, `${label}: populate-check`).toContain("NCBI records link BRCA1 to four diseases");
      expect(text, `${label} carries a screen-reader string`).not.toMatch(/Sources? \d+(,| to) /);
      expect(text, label).not.toMatch(/layer \d/);
    }
  });
});

test.describe("findings-tail record lines", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("render as a record block, never as one run-on line", async ({ page }) => {
    const body = [
      ...head(),
      token({ kind: "claim", text: "NCBI records link BRCA1 to four diseases [1]. ", marker_ids: ["cid-1"] }),
      token({ kind: "paragraph_break", text: "\n\n" }),
      token({ kind: "note", text: "Note: the records below were retrieved for this question and are listed as found." }),
      ...DISEASES.slice(1).map(([name], i) =>
        token({ kind: "claim", text: `Disease name: ${name} [${i + 2}]. `, marker_ids: [`cid-${i + 2}`] }),
      ),
      token({ kind: "claim", text: "gene symbol: BRCA1 [5]. ", marker_ids: ["cid-5"] }),
      ...citations(),
      frame("trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: null, scope: "answer" }),
      frame("done", { total_cost_usd: 0.02, total_tool_calls: 2, elapsed_ms: 5000, trust_outcome: "answer" }),
    ].join("");
    await ask(page, body);
    await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
    const block = page.getByTestId("answer-records-0");
    await expect(block).toHaveAttribute("data-record-source", "record_line");
    await expect(block.locator("tr")).toHaveCount(3);
    await expect(page.getByRole("heading", { name: "Disease name" })).toBeVisible();
    const text = await page.getByTestId("claims").innerText();
    expect(text).toContain("Familial breast-ovarian cancer susceptibility 1");
    expect(text).not.toMatch(/Disease name: /);
    await page.screenshot({ path: path.join(SHOTS, "w1280_findings_tail_records.png"), fullPage: true });
  });
});

test.describe("the writing state", () => {
  for (const width of [1280, 390]) {
    test(`shows the banner in the gap after Act, then builds the answer one sentence at a time (${width}px)`, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      // Act closed, no token yet, no done: the silent gap.
      await ask(page, head().join(""));
      const banner = page.getByTestId("writing-banner");
      await expect(banner).toBeVisible({ timeout: 30_000 });
      await expect(banner).toContainText("is writing the answer");
      await expect(banner).toContainText("Salk and Nightingale found 11 records");
      await expect(page.getByTestId("step-Write")).toHaveAttribute("data-state", "live");
      await noSidewaysScroll(page);
      await page.screenshot({ path: path.join(SHOTS, `w${width}_writing_gap.png`), fullPage: true });
    });
  }

  test("reveals a burst of sentences progressively under the banner", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    // Every sentence in one burst, no done: the run stays live.
    await ask(page, [...head(), ...answerTokens("plain"), ...citations()].join(""));
    await expect(page.getByTestId("writing-banner")).toBeVisible({ timeout: 30_000 });
    const claims = page.getByTestId(/^claim-text-\d+$/);
    await expect(claims.first()).toBeVisible({ timeout: 10_000 });
    const early = await claims.count();
    await page.screenshot({ path: path.join(SHOTS, "w1280_writing_reveal.png"), fullPage: true });
    await expect(page.getByTestId("streaming-writing-indicator")).toContainText("writing...");
    await expect.poll(() => claims.count(), { timeout: 10_000 }).toBeGreaterThan(early);
    expect(early, "the burst rendered all at once").toBeLessThan(DISEASES.length + TRIALS.length + 3);
  });
});
