/**
 * Card 22 (owner, 2026-10-06): every total says what it counts.
 *
 * The BRCA1 Researcher answer of 2026-09-27 showed "13 tools · 18 sources
 * from 3 layers", a Sources heading of 17 and "Based on 17 sources". This
 * replays its 18 citations (`fixtures/card22_brca1_citations.json`, the same
 * fixture the backend and unit tests read) through the real app and asserts
 * what a person now sees: one sources number, 16, in the meta line, the
 * Sources heading and the trust line, each saying what it counts, and the
 * opening "Found 4 disease records" line untouched.
 *
 * The stream is scripted, as in `trust-surface.spec.ts`: the fake-model
 * backend handles sign-in and the run, and only the event bytes are ours.
 * The trust line is the backend's own wording for this evidence, which
 * `test_trust_line_names_its_count.py` holds against the same fixture.
 *
 * Screenshots at 1280 and 390 only when CARD22_SHOTS=1.
 */

import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const shots = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-10-06_card22");

interface FixtureCitation {
  display_index: number;
  source_url: string;
  layer: string;
  source: string;
  source_id: string;
  field: string;
}

const FIXTURE = JSON.parse(
  readFileSync(path.join(__dirname, "fixtures", "card22_brca1_citations.json"), "utf8"),
) as {
  citations: FixtureCitation[];
  evidence_before: { tool_calls: number };
  expected_after: { sources_cited: number; layers: number; meta: string; trust_line: string };
};
const AFTER = FIXTURE.expected_after;

test.use({ contextOptions: { reducedMotion: "reduce" } });

let seq = 0;
function frame(type: string, payload: unknown): string {
  seq += 1;
  const envelope = { type, version: "v1", trace_id: "card22-spec", seq, ts: "2026-10-06T00:00:00Z", payload };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

const cid = (n: number) => `cid-${n}`;

function answer(): string {
  const tools = Array.from({ length: FIXTURE.evidence_before.tool_calls }, (_, n) =>
    frame("tool_result", {
      call_id: `c${n + 1}`,
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "ok",
      summary: "",
      // Distinct counts: the reasoning log keys a chip by tool and count.
      result_count: n + 1,
      truncated: false,
    }),
  );
  return [
    frame("guard", { passed: true, category: "ok", reason: null }),
    frame("think", {
      narrative: "Looking up diseases for BRCA1.",
      query_class: "single_hop",
      resolved_entities: [],
      clarifying_question: null,
    }),
    frame("plan", { narrative: "Query the graph and the live records.", tool_calls: [] }),
    ...tools,
    frame("token", {
      kind: "claim",
      text: "Found 4 disease records for BRCA1: Familial cancer of breast [2], Breast-ovarian cancer [3], Pancreatic cancer [4] and Fanconi anemia [5]. ",
      marker_ids: [cid(2), cid(3), cid(4), cid(5)],
    }),
    frame("token", {
      kind: "claim",
      text: "Mutations in this gene are responsible for approximately 40% of inherited breast cancers [1]. ",
      marker_ids: [cid(1)],
    }),
    frame("token", {
      kind: "claim",
      text: "The gene record and the variant, OMIM and trial records are listed under Sources [6][7][8][9][10][11][12][13][14][15][16][17][18]. ",
      marker_ids: Array.from({ length: 13 }, (_, n) => cid(n + 6)),
    }),
    ...FIXTURE.citations.map((c) =>
      frame("citation", {
        citation_id: cid(c.display_index),
        display_index: c.display_index,
        source: c.source,
        source_id: c.source_id,
        source_url: c.source_url,
        layer: c.layer,
        field: c.field,
        claim_text: "x",
        evidence_kind: "primary_assertion",
        assertion_confidence: "asserted",
        population_ancestry_context: null,
        license: "public_domain_us_gov",
      }),
    ),
    frame("trust_signal", { outcome: "ask", risk_tier: "high", grounded: true, triangulated: false, scope: "answer" }),
    frame("done", {
      total_cost_usd: 0,
      total_tool_calls: FIXTURE.evidence_before.tool_calls,
      elapsed_ms: 11200,
      trust_outcome: "ask",
      trust_line: AFTER.trust_line,
    }),
  ].join("");
}

async function ask(page: Page): Promise<void> {
  const body = answer();
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
  await page.getByLabel("Email").fill(`card22-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Log in" }).click();
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

for (const width of [1280, 390]) {
  test(`every total says what it counts, one sources number, at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width < 720 ? 844 : 900 });
    await ask(page);

    const meta = page.getByTestId("answer-meta");
    await expect(meta).toBeVisible({ timeout: 30_000 });
    await expect(meta).toContainText(AFTER.meta);
    await expect(meta).not.toContainText(/\b18 sources\b/);

    await expect(page.getByTestId("sources-count")).toHaveText(String(AFTER.sources_cited));
    const trust = page.getByTestId("trust-line");
    await expect(trust).toContainText(AFTER.trust_line);

    // The opening "Found N ... records" line is unchanged by this card.
    await expect(page.getByTestId("answer-body")).toContainText("Found 4 disease records for BRCA1");

    // The trailing-slash pair is one card carrying all three gene markers.
    await page.locator('[data-testid="sources-disclosure"] > summary').click();
    await page.locator('[data-testid="sources-group-2"] > summary').click();
    const geneCards = page.locator('[data-testid^="source-"]').filter({ hasText: "672" });
    await expect(geneCards).toHaveCount(1);

    if (process.env.CARD22_SHOTS === "1") {
      await mkdir(shots, { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: path.join(shots, `answer_${width}.png`),
        fullPage: true,
        mask: [page.getByText(/Working as /), page.getByText(/card22-[a-f0-9-]+@example\.com/)],
        maskColor: "#f0f0f0",
      });
    }
  });
}
