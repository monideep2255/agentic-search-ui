/**
 * Card 24: the Plain language / Researcher switch on an answer, in a real
 * browser at 1280 and 390. Clicking the other mode shows the cost line and
 * sends nothing; "Ask again" sends exactly one new POST at `researcher`.
 * Scripted stream copied from `answer-layout.spec.ts`; the harness backend
 * answers `POST /v1/query` for real, so every POST is recorded.
 *
 * WHAT IT DOES NOT COVER: the counted-guest form of the line (the unit
 * tests in `App.depthToggle.test.tsx` cover both forms) and the real
 * backend's refusal at zero searches left.
 */

import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.use({ contextOptions: { reducedMotion: "reduce" } });

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-10-16_card24");

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
  // The harness account may start on Researcher, so choose Plain language on
  // the home page, where the choice exists today, and let it settle.
  const plain = main.getByRole("button", { name: "Plain language" });
  await plain.click();
  await expect(plain).toHaveAttribute("aria-pressed", "true");
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
  test.describe(`answer depth switch at ${width}px`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 } });

    test("asks first, then runs once at Researcher", async ({ page }) => {
      const posts: string[] = [];
      page.on("request", (request) => {
        if (request.method() === "POST" && /\/v1\/query$/.test(new URL(request.url()).pathname)) {
          posts.push(request.postData() ?? "");
        }
      });
      await ask(page, landedStream("plain"));
      await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
      expect(posts).toHaveLength(1);

      const group = page.getByRole("group", { name: /answer mode/i });
      await expect(group).toBeVisible();
      await expect(group.getByRole("button", { name: "Plain language" })).toHaveAttribute("aria-pressed", "true");

      await group.getByRole("button", { name: "Researcher" }).click();
      const line = page.getByTestId("answer-depth-confirm");
      await expect(line).toBeVisible();
      await expect(line).toHaveText(/^Ask this question again in Researcher\? It runs as one new search\.\s*Ask againCancel$/);
      expect(posts).toHaveLength(1);
      await noSidewaysScroll(page);

      const results = await new AxeBuilder({ page })
        .include('[data-testid="answer-status-strip"]')
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);

      if (process.env.FACTORY_SHOTS === "1") {
        await mkdir(SHOTS, { recursive: true });
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: path.join(SHOTS, `w${width}_cost_line.png`), fullPage: true });
      }

      await line.getByRole("button", { name: "Ask again" }).click();
      await expect.poll(() => posts.length, { timeout: 15_000 }).toBe(2);
      expect(JSON.parse(posts[1]).audience_depth).toBe("researcher");
      // J-24-11: wait for the new answer to land, then check no third
      // request arrived late. The folded first answer is labelled by mode
      // (J-24-06) and the switch now lights Researcher on the new answer.
      await expect(page.getByTestId("previous-turn-0-mode")).toHaveText("Plain language");
      const landed = page.getByRole("group", { name: /answer mode/i });
      await expect(landed.getByRole("button", { name: "Researcher" })).toHaveAttribute("aria-pressed", "true", {
        timeout: 30_000,
      });
      await page.waitForTimeout(1_000);
      expect(posts).toHaveLength(2);
      await noSidewaysScroll(page);
    });
  });
}
