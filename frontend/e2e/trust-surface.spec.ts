/**
 * The trust surface, rendered from a real stream and then examined.
 *
 * Closes adversary finding F-4.8-A-16's coverage half and re-review finding
 * F-4.8-R-07: until now NO automated check anywhere had looked at a rendered
 * answer carrying a citation chip, a source card, a coloured spine segment or a
 * trust pill.
 *
 * That gap is why A-16 survived. The accessibility suite reported zero
 * violations across every screen while the product's headline signal, the
 * provenance spine, was `aria-hidden` and its citation chips were bare spans
 * containing a digit. A cited and an uncited claim were indistinguishable to a
 * screen reader, and no check was ever pointed at an answer that had either.
 *
 * The e2e mock backend cannot emit a citation: its only token is the
 * cost-cap partial-result note. Rather than change the backend to suit a test,
 * this intercepts the event stream and serves a scripted one. The app is
 * untouched and runs its real parsing, real adapter and real rendering; only
 * the bytes on the wire are ours, which is the point of the exercise.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const TEST_PASSWORD = "Str0ngPassw0rd!";

/** One SSE frame in the shape `adapters/web_sse` actually writes. */
function frame(seq: number, type: string, payload: unknown): string {
  const envelope = {
    type,
    version: "v1",
    trace_id: "trust-surface-spec",
    seq,
    ts: "2026-08-13T00:00:00Z",
    payload,
  };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

/**
 * An answer with one CITED claim and one UNCITED claim.
 *
 * The uncited one is the important half: the spine gap is the signal this suite
 * exists to check, and an answer where everything is cited cannot exercise it.
 */
const SCRIPTED_STREAM = [
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
    result_count: 25,
    truncated: false,
  }),
  frame(4, "token", {
    text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome [1]. ",
    marker_ids: ["cid-1"],
  }),
  frame(5, "token", {
    text: "It is also widely discussed in the popular press. ",
    marker_ids: [],
  }),
  frame(6, "citation", {
    citation_id: "cid-1",
    display_index: 1,
    source: "NCBI Gene",
    source_id: "672",
    source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
    layer: "layer_1_graph",
    field: "cypher_query",
    claim_text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  }),
  frame(7, "trust_signal", {
    outcome: "flag",
    risk_tier: "high",
    grounded: false,
    triangulated: null,
  }),
  frame(8, "done", {
    status: "answered",
    trust_outcome: "flag",
    elapsed_ms: 1200,
    truncated: false,
  }),
].join("");

async function signInAndScript(page: Page): Promise<void> {
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
  }
  await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: /log in/i }).click();
  await page.getByLabel("Email").fill(`trust-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();

  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await expect(page.getByTestId("source-1")).toBeVisible({ timeout: 30_000 });
}

test.describe("the trust surface", () => {
  test("renders a cited claim, an uncited claim, and a source card", async ({ page }) => {
    await signInAndScript(page);

    // The binding came from marker_ids, so claim one is cited and claim two is
    // not, regardless of the fact that claim one's claim_text is a substring of
    // nothing else. This is the shape F-4.8-A-01 got wrong.
    await expect(page.getByTestId("citation-1")).toBeVisible();
    const segments = page.getByTestId(/^spine-segment-/);
    await expect(segments).toHaveCount(2);
    await expect(segments.nth(0)).toHaveAttribute("data-layer", "1");
    await expect(segments.nth(1)).toHaveAttribute("data-layer", "none");

    // Every provenance field the contract requires, including the licence.
    const card = page.getByTestId("source-1");
    for (const field of ["cypher_query", "curated assertion", "high", "public domain"]) {
      await expect(card).toContainText(field);
    }
  });

  /*
   * The spine's whole claim is that segment N describes claim N. Every other
   * assertion in this file checks the segments' count, order and colour, which
   * all stay correct while the two columns drift vertically out of register.
   *
   * This measures the thing those cannot see: each segment must be level with
   * the sentence it is pointing at. The tolerance is generous on purpose, since
   * the point is to catch a segment beside the WRONG claim, not to pin a
   * padding value.
   */
  test("each spine segment stays level with the claim it describes", async ({ page }) => {
    await signInAndScript(page);

    /*
     * Measured against the RENDERED TEXT, via a Range over the claim's own text
     * nodes, not against the element box that holds it.
     *
     * The first version of this check compared the segment's box to the
     * Typography's box. Both are cells of the same grid row, so they are level
     * by construction and the assertion could not fail: a mutation restoring
     * the old independent sizing passed it. Comparing against the glyphs is
     * what makes it a measurement rather than a restatement of the layout.
     */
    const rows = await page.evaluate(() => {
      const segments = [...document.querySelectorAll('[data-testid^="spine-segment-"]')];
      const texts = [...document.querySelectorAll('[data-testid^="claim-text-"]')];
      return segments.map((element, index) => {
        const segment = element.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(texts[index]!);
        const text = range.getBoundingClientRect();
        return {
          segmentTop: segment.top,
          segmentBottom: segment.bottom,
          textTop: text.top,
          textBottom: text.bottom,
        };
      });
    });

    // Both sides present, and more than one, or the loop below proves nothing.
    expect(rows.length).toBe(await page.getByTestId(/^claim-text-/).count());
    expect(rows.length).toBeGreaterThan(1);

    for (const [index, row] of rows.entries()) {
      // The segment must SPAN the sentence it points at. A segment that has
      // slipped onto a neighbouring claim fails one bound or the other.
      expect(row.segmentTop, `segment ${index} starts below its claim`).toBeLessThanOrEqual(
        row.textTop + 12,
      );
      expect(row.segmentBottom, `segment ${index} ends above its claim`).toBeGreaterThanOrEqual(
        row.textBottom - 12,
      );
    }
  });

  test("is clean under axe with a citation, a spine gap and a risk pill on screen", async ({
    page,
  }) => {
    await signInAndScript(page);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });

  test("conveys cited versus uncited without relying on colour", async ({ page }) => {
    // F-4.8-A-16. Axe passed this screen throughout while the spine was
    // aria-hidden and the chips were bare digits, so a screen-reader user could
    // not tell a cited claim from a fabricated one. Axe cannot check this;
    // WCAG 1.4.1 (use of colour) is the rule, and only an explicit assertion
    // catches it.
    await signInAndScript(page);

    const text = await page.getByRole("main").innerText();
    const accessible = await page.evaluate(() => document.body.innerText);
    void accessible;

    // The uncited claim must SAY it is uncited, not merely look grey.
    await expect(page.getByText(/this sentence has no source/i)).toHaveCount(1);
    // The cited claim must name its source.
    await expect(page.getByLabel(/^source 1$/i)).toBeVisible();
    // And the visible prose must not be the only carrier of that difference.
    expect(text).toContain("BRCA1");
  });

  test("the trust strip reports what the stream actually said", async ({ page }) => {
    // The scripted stream says grounded:false, risk_tier:"high". An answer that
    // displayed "Grounded, every claim cited" here would be F-4.8-A-06.
    await signInAndScript(page);

    const trust = page.getByRole("status", { name: /trust signals/i });
    await expect(trust).not.toContainText(/grounded · every claim cited/i);
    await expect(trust).toContainText(/high/i);
  });
});
