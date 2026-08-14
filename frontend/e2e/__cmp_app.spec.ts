import { randomUUID } from "node:crypto";
import { test, type Page } from "@playwright/test";
const DIR = "/private/tmp/claude-501/-Users-anuradhachakraborti-Desktop-Tech-Skills-agentic-search-ui/5071737f-3fc1-4077-8bbc-f22e1383fa74/scratchpad/cmp";

function frame(seq: number, type: string, payload: unknown): string {
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({ type, version: "v1", trace_id: "cmp", seq, ts: "2026-08-14T00:00:00Z", payload })}\n\n`;
}
const STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", { narrative: "Resolving the gene named in the question.", query_class: "single_hop", resolved_entities: [], clarifying_question: null }),
  frame(2, "plan", { narrative: "Query the graph, confirm live, check literature.", tool_calls: [] }),
  frame(3, "tool_result", { call_id: "c1", tool: "cypher_query", layer: "layer_1_graph", status: "ok", summary: "", result_count: 25, truncated: false }),
  frame(4, "tool_result", { call_id: "c2", tool: "ncbi_efetch", layer: "layer_2_api", status: "ok", summary: "", result_count: 1, truncated: false }),
  frame(5, "tool_result", { call_id: "c3", tool: "pubtator_annotate", layer: "layer_3_enrichment", status: "ok", summary: "", result_count: 1, truncated: false }),
  frame(6, "token", { text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome, the best-characterised of its disease links [1]. ", marker_ids: ["c-1"] }),
  frame(7, "token", { text: "The current MedGen record describes an autosomal dominant inheritance pattern with markedly elevated lifetime risk [2]. ", marker_ids: ["c-2"] }),
  frame(8, "token", { text: "Biallelic variants have also been reported in Fanconi anemia complementation group S, drawn from the literature rather than a curated record [3]. ", marker_ids: ["c-3"] }),
  frame(9, "citation", { citation_id: "c-1", display_index: 1, source: "NCBI Gene", source_id: "672", source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: "layer_1_graph", field: "cypher_query", claim_text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome", evidence_kind: "curated assertion", assertion_confidence: "high", population_ancestry_context: null, license: "public domain" }),
  frame(10, "citation", { citation_id: "c-2", display_index: 2, source: "MedGen", source_id: "C0677776", source_url: "https://www.ncbi.nlm.nih.gov/medgen/C0677776", layer: "layer_2_api", field: "ncbi_efetch", claim_text: "The current MedGen record describes an autosomal dominant inheritance pattern", evidence_kind: "live record", assertion_confidence: "high", population_ancestry_context: null, license: "public domain" }),
  frame(11, "citation", { citation_id: "c-3", display_index: 3, source: "PubMed", source_id: "21990134", source_url: "https://pubmed.ncbi.nlm.nih.gov/21990134/", layer: "layer_3_enrichment", field: "pubtator_annotate", claim_text: "Biallelic variants have also been reported in Fanconi anemia complementation group S", evidence_kind: "literature", assertion_confidence: "moderate", population_ancestry_context: null, license: "public domain" }),
  frame(12, "trust_signal", { outcome: "answer", risk_tier: "high", grounded: true, triangulated: true }),
  frame(13, "done", { total_cost_usd: 0.0031, total_tool_calls: 3, elapsed_ms: 11400, trust_outcome: "answer" }),
].join("");

async function enter(page: Page) {
  await page.goto("/");
  const d = page.getByTestId("disclaimer-modal");
  if (await d.isVisible().catch(() => false)) {
    await d.getByRole("checkbox").check();
    await d.getByRole("button", { name: /continue/i }).click();
  }
}

test("app states", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/v1/query/*/events*", (r) =>
    r.fulfill({ status: 200, headers: { "content-type": "text/event-stream", "cache-control": "no-cache" }, body: STREAM }));

  await enter(page);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${DIR}/A1-landing-anon.png` });

  await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: /log in/i }).click();
  await page.getByLabel("Email").fill(`demo-${randomUUID()}@ncbi.test`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Sign up" }).click();
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).waitFor({ timeout: 20000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/A2-landing-in.png` });

  await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${DIR}/A3-run.png` });

  await page.getByTestId("sources-disclosure").waitFor({ timeout: 30000 }).catch(() => {});
  await page.getByTestId("sources-disclosure").getByText("Sources", { exact: true }).click().catch(() => {});
  await page.getByRole("button", { name: /show work/i }).click().catch(() => {});
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/A4-answer.png`, fullPage: true });
});
