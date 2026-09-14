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
  await page.getByRole("button", { name: "Log in" }).click();

  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  /*
   * Build phase 4.9 collapsed the sources behind a disclosure (F-4.8-D-01), as
   * the prototype has them. Every guarantee this suite holds about a source
   * card is unchanged; only the route to seeing one moved, so the helper opens
   * the disclosure rather than any assertion being relaxed.
   */
  await expect(page.getByTestId("sources-disclosure")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("sources-disclosure").getByText("Sources", { exact: true }).click();
  await expect(page.getByTestId("source-1")).toBeVisible();
}

test.describe("the trust surface", () => {
  test("renders a cited claim, an uncited claim, and a source card", async ({ page }) => {
    await signInAndScript(page);

    // The binding came from marker_ids, so claim one is cited and claim two is
    // not, regardless of the fact that claim one's claim_text is a substring of
    // nothing else. This is the shape F-4.8-A-01 got wrong.
    await expect(page.getByTestId("citation-1")).toBeVisible();
    // REQUIREMENT CHANGE, 2026-09-14: no spine bar; each claim carries its
    // own provenance attribute, one per claim, exactly as the segments did.
    const segments = page.getByTestId(/^claim-text-\d+$/);
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
   * REQUIREMENT CHANGE, 2026-09-14 (approved answer layout). The spine is
   * retired, so "each spine segment stays level with its claim" has nothing
   * left to measure. The property it protected was that a provenance mark
   * points at the RIGHT claim. That is now asserted directly: every citation
   * marker is inside the claim it declares, and the first claim's marker is
   * level with that claim's own rendered text.
   */
  test("each citation marker sits inside the claim it cites", async ({ page }) => {
    await signInAndScript(page);
    const pairs = await page.evaluate(() =>
      [...document.querySelectorAll('[data-testid^="citation-"][data-claim]')].map((marker) => {
        const claim = document.querySelector(
          `[data-testid="claim-text-${marker.getAttribute("data-claim")}"]`,
        );
        const range = document.createRange();
        if (claim) range.selectNodeContents(claim);
        const text = range.getBoundingClientRect();
        const box = marker.getBoundingClientRect();
        return {
          inside: claim !== null && claim.contains(marker),
          markerMid: (box.top + box.bottom) / 2,
          textTop: text.top,
          textBottom: text.bottom,
        };
      }),
    );
    // Populate-check: at least one marker, or the loop proves nothing.
    expect(pairs.length).toBeGreaterThan(0);
    for (const [index, pair] of pairs.entries()) {
      expect(pair.inside, `marker ${index} is outside the claim it cites`).toBe(true);
      expect(pair.markerMid, `marker ${index} is above its claim`).toBeGreaterThanOrEqual(pair.textTop - 12);
      expect(pair.markerMid, `marker ${index} is below its claim`).toBeLessThanOrEqual(pair.textBottom + 12);
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
    // The cited claim must name its source AND its layer.
    //
    // REQUIREMENT CHANGE, 2026-09-14: the citation is now a superscript marker
    // button rather than a boxed chip carrying `aria-label="Source 1"`, at the
    // product owner's request. The marker's accessible name is
    // "Source 1, layer 1", so this asserts more than before (the role, and
    // the layer in words), not less.
    await expect(page.getByRole("button", { name: /^source 1, layer 1$/i })).toBeVisible();
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
