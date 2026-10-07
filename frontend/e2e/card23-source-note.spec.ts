/**
 * Card 23's second part (J-23-01, A-23-01, 2026-10-07): the line under the
 * variant-to-disease table sits directly under that table, in a real browser,
 * at 1280 and 390, including when the table ends the answer. Before the fix,
 * that shape showed the line first in the Notes list after the answer.
 *
 * The stream is scripted, as in `card22-name-every-total.spec.ts`: the
 * fake-model backend handles sign-in and the run, and only the event bytes are
 * ours, shaped like the token stream `write_node` emits for the variant fold
 * with no gene record after it (the judge's probe, `judge.md`).
 *
 * Screenshots at 1280 and 390 only when CARD23_SHOTS=1.
 */

import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const shots = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-10-06_card23");

const SOURCE_LINE =
  "Each row lists the conditions the variant's ClinVar record names; the record's classification " +
  "(for example pathogenic, benign or uncertain) is not shown here. Disease names are MedGen titles looked up from NCBI.";
const PLACEHOLDER = "2 variant links to ClinVar placeholder conditions (not provided, not specified) are not listed.";

test.use({ contextOptions: { reducedMotion: "reduce" } });

let seq = 0;
function frame(type: string, payload: unknown): string {
  seq += 1;
  const envelope = { type, version: "v1", trace_id: "card23-spec", seq, ts: "2026-10-07T00:00:00Z", payload };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

const token = (payload: Record<string, unknown>) => frame("token", { marker_ids: [], ...payload });

const VARIANTS: [string, string, string][] = [
  ["NM_000545.8(HNF1A):c.737T>G", "1134661", "Maturity-onset diabetes of the young type 3; Monogenic diabetes"],
  ["NM_000545.8(HNF1A):c.1011C>T", "1036297", "Maturity-onset diabetes of the young"],
];

function answer(moreAfter: boolean): string {
  const rows = VARIANTS.map(([name, id, disease], i) =>
    token({
      kind: "table_row",
      text: `Sequence variant name: ${name} [${i + 1}]. `,
      cells: [name, `ClinVar:${id}`, disease],
      marker_ids: [`cid-${i + 1}`],
    }),
  );
  const citations = VARIANTS.map(([name, id], i) =>
    frame("citation", {
      citation_id: `cid-${i + 1}`, display_index: i + 1, source: "ClinVar", source_id: `ClinVar:${id}`,
      source_url: `https://www.ncbi.nlm.nih.gov/clinvar/variation/${id}/`, layer: "layer_1_graph", field: "name",
      claim_text: name, evidence_kind: "primary_assertion", assertion_confidence: "asserted",
      population_ancestry_context: null, license: "public_domain_us_gov",
    }),
  );
  const gene = moreAfter
    ? [
        token({ kind: "paragraph_break", text: "\n\n" }),
        token({ kind: "heading", text: "Gene records found\n\n" }),
        token({ kind: "list_item", text: "Gene HNF1A [3]. ", cells: ["HNF1A"], marker_ids: ["cid-3"] }),
        frame("citation", {
          citation_id: "cid-3", display_index: 3, source: "NCBIGene", source_id: "NCBIGene:6927",
          source_url: "https://www.ncbi.nlm.nih.gov/gene/6927", layer: "layer_1_graph", field: "symbol",
          claim_text: "HNF1A", evidence_kind: "primary_assertion", assertion_confidence: "asserted",
          population_ancestry_context: null, license: "public_domain_us_gov",
        }),
      ]
    : [];
  return [
    frame("guard", { passed: true, category: "ok", reason: null }),
    frame("tool_result", { call_id: "g1", tool: "cypher_query", layer: "layer_1_graph", status: "ok", summary: "", result_count: 2, truncated: false }),
    token({ kind: "claim", text: "Variants in HNF1A are linked to two conditions in ClinVar [1][2]. ", marker_ids: ["cid-1", "cid-2"] }),
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "heading", text: "Variant-to-disease mapping\n\n" }),
    token({ kind: "table_header", text: "", cells: ["Variant", "Identifier", "Linked disease"] }),
    ...rows,
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "note", text: SOURCE_LINE }),
    ...gene,
    token({ kind: "paragraph_break", text: "\n\n" }),
    token({ kind: "note", text: PLACEHOLDER }),
    ...citations,
    frame("trust_signal", { outcome: "ask", risk_tier: "high", grounded: true, triangulated: false, scope: "answer" }),
    frame("done", { total_cost_usd: 0, total_tool_calls: 1, elapsed_ms: 1000, trust_outcome: "ask", trust_line: "Based on 2 sources cited" }),
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
  await page.getByLabel("Email").fill(`card23-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Log in" }).click();
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill("What diseases are caused by variants in the HNF1A gene?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

for (const width of [1280, 390]) {
  for (const moreAfter of [false, true]) {
    const shape = moreAfter ? "more records follow it" : "the table ends the answer";
    test(`the source line sits directly under the variant table when ${shape}, at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 720 ? 844 : 900 });
      await ask(page, answer(moreAfter));

      const records = page.getByTestId("answer-records-0");
      await expect(records).toBeVisible({ timeout: 30_000 });
      const line = page.getByText(SOURCE_LINE, { exact: true });
      await expect(line).toHaveCount(1);
      await expect(line).toHaveAttribute("data-testid", /answer-inline-note-\d+$/);

      // Directly under: the element right after the table's block is the line.
      const nextIsLine = await records.evaluate(
        (node, text) => node.nextElementSibling?.textContent?.trim() === text,
        SOURCE_LINE,
      );
      expect(nextIsLine).toBe(true);
      const table = await records.boundingBox();
      const note = await line.boundingBox();
      expect(table && note).toBeTruthy();
      expect(note!.y).toBeGreaterThanOrEqual(table!.y + table!.height - 1);
      expect(note!.y - (table!.y + table!.height)).toBeLessThan(48);

      // Never in the answer-wide Notes list; the placeholder note stays there.
      const notes = page.getByTestId("answer-notes");
      await expect(notes).toContainText(PLACEHOLDER);
      await expect(notes).not.toContainText("ClinVar record names");

      // No sideways scroll on a phone.
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);

      if (process.env.CARD23_SHOTS === "1") {
        await mkdir(shots, { recursive: true });
        await line.scrollIntoViewIfNeeded();
        await page.screenshot({
          path: path.join(shots, `part2_${moreAfter ? "more_after" : "table_last"}_${width}.png`),
          fullPage: true,
          mask: [page.getByText(/Working as /), page.getByText(/card23-[a-f0-9-]+@example\.com/)],
          maskColor: "#f0f0f0",
        });
      }
    });
  }
}
