import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const shots = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-10-06_factory_card43b");
const name = "NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG";
const shorterName = "NM_007294.4(BRCA1):c.5243_5277+2788del";

test.use({ contextOptions: { reducedMotion: "reduce" } });

let seq = 0;
function frame(type: string, payload: unknown): string {
  seq += 1;
  const envelope = { type, version: "v1", trace_id: "long-variant-spec", seq, ts: "2026-10-06T00:00:00Z", payload };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

const token = (payload: Record<string, unknown>) => frame("token", { marker_ids: [], ...payload });

function answer(): string {
  return [
    frame("guard", { passed: true, category: "ok", reason: null }),
    frame("think", { narrative: "Looking up a BRCA1 record.", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
    frame("plan", {
      narrative: "Read the ClinVar record.",
      tool_calls: [{ tool: "ncbi_efetch", call_id: "c1", layer: "layer_2_api", persona: "Salk" }],
    }),
    frame("tool_start", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "running", persona: "Salk" }),
    frame("tool_result", { call_id: "c1", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", persona: "Salk", summary: "", result_count: 1, truncated: false }),
    token({ kind: "claim", text: `The ClinVar record names ${name} [10]. `, marker_ids: ["cid-10"] }),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "claim", text: `This ClinVar record also names ${shorterName} [5]. `, marker_ids: ["cid-5"] }),
    token({ kind: "heading", text: "Where this answer comes from\n\n" }),
    token({ kind: "list_item", text: `Sequence variant name: ${name} [10]. `, cells: [name], marker_ids: ["cid-10"] }),
    token({ kind: "list_item", text: `Sequence variant name: ${shorterName} [5]. `, cells: [shorterName], marker_ids: ["cid-5"] }),
    token({ kind: "table_header", text: "", cells: ["Record", "Identifier"] }),
    token({ kind: "table_row", text: `Sequence variant name: ${name} [10]. `, cells: ["ClinVar entry", name], marker_ids: ["cid-10"] }),
    frame("citation", {
      citation_id: "cid-10", display_index: 10, source: "clinvar", source_id: name,
      source_url: "https://www.ncbi.nlm.nih.gov/clinvar/variation/123456/",
      layer: "layer_2_api", field: "ncbi_efetch", claim_text: name,
      evidence_kind: "curated assertion", assertion_confidence: "high",
      population_ancestry_context: null, license: "public domain",
    }),
    frame("citation", {
      citation_id: "cid-5", display_index: 5, source: "clinvar", source_id: shorterName,
      source_url: "https://www.ncbi.nlm.nih.gov/clinvar/variation/654321/",
      layer: "layer_2_api", field: "ncbi_efetch", claim_text: shorterName,
      evidence_kind: "curated assertion", assertion_confidence: "high",
      population_ancestry_context: null, license: "public domain",
    }),
    frame("trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: null, scope: "answer" }),
    frame("done", { total_cost_usd: 0, total_tool_calls: 1, elapsed_ms: 100, trust_outcome: "answer" }),
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
  await page.getByLabel("Email").fill(`variant-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Log in" }).click();
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill("What does BRCA1 do?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

async function noSidewaysScroll(page: Page): Promise<void> {
  const [scroll, width] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(scroll, `the page scrolls sideways: ${scroll} > ${width}`).toBeLessThanOrEqual(width);
}

async function markerAndNameLastLine(page: Page, selector: string): Promise<{ nameBottom: number; markerTop: number }> {
  return page.locator(selector).evaluate((element, variant) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let text: Node | null;
    let lastCharacters: Text | null = null;
    while ((text = walker.nextNode())) {
      if (text.textContent?.includes(variant.slice(-3))) {
        lastCharacters = text as Text;
        break;
      }
    }
    if (!lastCharacters) throw new Error("Variant text is missing from the claim");
    const end = lastCharacters.textContent!.indexOf(variant.slice(-3)) + 3;
    const range = document.createRange();
    range.setStart(lastCharacters, end - 3);
    range.setEnd(lastCharacters, end);
    const marker = element.querySelector('[data-testid="citation-5"]');
    if (!marker) throw new Error("Citation 5 is missing from the claim");
    return { nameBottom: range.getBoundingClientRect().bottom, markerTop: marker.getBoundingClientRect().top };
  }, shorterName);
}

for (const width of [390, 412, 414, 1280]) {
  test(`the long variant name stays inside the answer at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width < 720 ? 844 : 900 });
    await ask(page, answer());
    await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
    const records = page.getByTestId("answer-records-0");
    const prose = page.getByTestId("claim-text-0");
    await expect(prose).toContainText(name);
    await expect(records).toContainText(name);

    await page.locator('[data-testid="sources-disclosure"] > summary').click();
    await page.locator('[data-testid="sources-group-2"] > summary').click();
    const source = page.getByTestId("source-10");
    await expect(source).toContainText(name);
    if (process.env.FACTORY_SHOTS === "1") {
      await mkdir(shots, { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: path.join(shots, `answer_${width}.png`),
        fullPage: true,
        mask: [
          page.getByText(/Working as /),
          page.getByText(/variant-[a-f0-9-]+@example\.com/),
        ],
        maskColor: "#f0f0f0",
      });
    }

    if (width < 720) {
      const row = records.locator("li > span").first();
      await expect(row).toContainText(name);
      const lines = await row.evaluate((element) => {
        const range = document.createRange();
        range.selectNodeContents(element.firstChild!);
        return range.getClientRects().length;
      });
      expect(lines, "the record name wraps inside its own row").toBeGreaterThan(1);
      const identifier = page.getByTestId("answer-records-1").locator("li > span").nth(1);
      await expect(identifier).toContainText(name);
      const identifierLines = await identifier.evaluate((element) => {
        const range = document.createRange();
        range.selectNodeContents(element);
        return range.getClientRects().length;
      });
      expect(identifierLines, "the identifier wraps inside its own row").toBeGreaterThan(1);
      await noSidewaysScroll(page);
      const marker = records.getByTestId("citation-10");
      await expect(marker).toBeVisible();
      const markerBox = (await marker.boundingBox())!;
      expect(markerBox.x + markerBox.width).toBeLessThanOrEqual(width);
      expect((await source.locator("summary").boundingBox())!.x).toBeGreaterThanOrEqual(0);
      const shortRow = records.locator("li").filter({ hasText: shorterName });
      await expect(shortRow).toBeVisible();
      const { nameBottom, markerTop } = await markerAndNameLastLine(page, '[data-testid="answer-records-0"] li:nth-child(2) > span:first-child');
      expect(markerTop, "citation 5 sits alone below the variant name").toBeLessThan(nameBottom);
      const prosePosition = await markerAndNameLastLine(page, '[data-testid="claim-text-1"]');
      expect(prosePosition.markerTop, "the prose citation sits alone below the variant name").toBeLessThan(prosePosition.nameBottom);
    } else {
      await expect(page.getByTestId("answer-table")).toHaveCount(2);
      const lines = await records.locator("tbody tr:first-child td:first-child").evaluate((element) => {
        const range = document.createRange();
        range.selectNodeContents(element);
        return range.getClientRects().length;
      });
      expect(lines, "the desktop record name stays on one line").toBe(1);
      await noSidewaysScroll(page);
    }
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
  });
}
