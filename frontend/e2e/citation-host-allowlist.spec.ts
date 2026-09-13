/**
 * W-thread-5, `testing/Developer/Developer_workflows.md`'s Tier 1 row: "Never link a
 * citation to a host outside the allowed NCBI set, and say so when it
 * cannot." Built as `isLinkableCitationUrl` in `AnswerScreen.tsx:198-215`,
 * checked against `ALLOWED_CITATION_HOSTS` (the NCBI and ClinicalTrials.gov
 * hosts) with an https-only, exact-hostname match, never a substring or
 * scheme-only check.
 *
 * WHY THIS WAS UNCOVERED. `isLinkableCitationUrl` had NO test anywhere in
 * the repository before this spec, at any layer: no Vitest unit test on the
 * function itself, and no Playwright spec had ever scripted a citation
 * whose `source_url` fails the host check. `production-standards.md`'s
 * multi-agent pipeline gate names exactly this shape of defect as the one
 * to design against: adversary finding F-4.8-A-24 originally reached a
 * `javascript:` URL rendered as a clickable "Record" link for a source
 * labelled "NCBI Gene", survivable only by accident because nothing was
 * clickable yet. Making citations clickable (A-17) is exactly what removed
 * that accident of safety, which is why this check exists and why it
 * deserves its own direct test rather than living as an assumption behind
 * `trust-surface.spec.ts`'s already-NCBI-hosted fixture.
 *
 * COVERAGE STATED, per `goal-contracts.md`.
 *
 * Exercised here:
 *   - a `source_url` on a host outside `ALLOWED_CITATION_HOSTS`: renders as
 *     plain text, never a clickable anchor, with the visible disclosure
 *     "Not linked: this URL is not on a recognised NCBI host."
 *   - a `javascript:` URL, the exact shape F-4.8-A-24 found live.
 *   - a `source_url` on an allowed host (`ncbi.nlm.nih.gov`): renders as a
 *     real `<a href>` anchor with no disclosure, so the check is proven to
 *     distinguish the two rather than always refusing to link.
 *
 * Deliberately NOT exercised:
 *   - the other five allowed hosts (`www.ncbi.nlm.nih.gov`,
 *     `pubmed.ncbi.nlm.nih.gov`, `pmc.ncbi.nlm.nih.gov`,
 *     `clinicaltrials.gov`, `www.clinicaltrials.gov`). `isLinkableCitationUrl`
 *     checks membership in one fixed array with one equality test per
 *     entry, so one allowed host and one denied host already exercise the
 *     function's only branch; enumerating the rest would repeat the same
 *     assertion under a different string.
 *   - a non-`https` scheme on an otherwise-allowed host (e.g.
 *     `http://ncbi.nlm.nih.gov/...`). The `javascript:` case below already
 *     proves the scheme check fires; a bare `http:` case would prove the
 *     same branch a second way.
 *   - where a hostile `source_url` could originate (a compromised Layer 2 or
 *     Layer 3 API response, a prompt-injected field). This spec starts from
 *     the citation already on the wire and checks only what the BROWSER
 *     does with it, the same scope boundary `cite-or-refuse.spec.ts` states
 *     for the grounding decision.
 */

import { expect, test, type Page } from "@playwright/test";

function frame(seq: number, type: string, payload: unknown): string {
  const envelope = {
    type,
    version: "v1",
    trace_id: "citation-host-allowlist-spec",
    seq,
    ts: "2026-09-05T00:00:00Z",
    payload,
  };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

/**
 * Three citations: one off-host, one `javascript:`, one on an allowed NCBI
 * host. Each claim carries its own marker_id so all three source cards open
 * from the same run.
 */
function buildStream(): string {
  return [
    frame(0, "guard", { passed: true, category: "ok", reason: null }),
    frame(1, "think", {
      narrative: "",
      query_class: "lookup",
      resolved_entities: [],
      clarifying_question: null,
    }),
    frame(2, "plan", { narrative: "", tool_calls: [] }),
    frame(3, "tool_result", {
      call_id: "c1",
      tool: "cypher_query",
      layer: "layer_1_graph",
      status: "ok",
      summary: "",
      result_count: 3,
      truncated: false,
    }),
    frame(4, "token", {
      text:
        "BRCA1 is associated with hereditary breast and ovarian cancer syndrome [1]. " +
        "It is discussed on an unrelated site [2]. " +
        "A confirming record exists on NCBI [3].",
      marker_ids: ["cid-1", "cid-2", "cid-3"],
    }),
    // [1] an off-host URL, the F-4.8-A-24 shape: a real host, just not one
    // this product may point a reader to.
    frame(5, "citation", {
      citation_id: "cid-1",
      display_index: 1,
      source: "NCBI Gene",
      source_id: "672",
      source_url: "https://evil.example.com/fake-ncbi-record",
      layer: "layer_1_graph",
      field: "cypher_query",
      claim_text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome",
      evidence_kind: "curated assertion",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public domain",
    }),
    // [2] a javascript: URL. `isCitationPayload` only checks `typeof ===
    // "string"`, so this must be caught downstream by the host/scheme check,
    // not by schema validation.
    frame(6, "citation", {
      citation_id: "cid-2",
      display_index: 2,
      source: "Unrelated Site",
      source_id: "n/a",
      source_url: "javascript:alert(1)",
      layer: "layer_1_graph",
      field: "cypher_query",
      claim_text: "It is discussed on an unrelated site",
      evidence_kind: "curated assertion",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public domain",
    }),
    // [3] a legitimate NCBI record: the contrast case.
    frame(7, "citation", {
      citation_id: "cid-3",
      display_index: 3,
      source: "NCBI Gene",
      source_id: "672",
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
      layer: "layer_1_graph",
      field: "cypher_query",
      claim_text: "A confirming record exists on NCBI",
      evidence_kind: "curated assertion",
      assertion_confidence: "high",
      population_ancestry_context: null,
      license: "public domain",
    }),
    frame(8, "trust_signal", { outcome: "answer", risk_tier: "low", grounded: true, triangulated: null }),
    frame(9, "done", {
      total_cost_usd: 0.02,
      total_tool_calls: 1,
      elapsed_ms: 900,
      trust_outcome: "answer",
    }),
  ].join("");
}

async function askWithScriptedCitations(page: Page): Promise<void> {
  await page.route("**/v1/query/*/events*", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: buildStream(),
    }),
  );

  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }

  const main = page.getByRole("main");
  await main
    .getByRole("textbox", { name: /question/i })
    .fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });

  // Every card lives behind the sources disclosure (build phase 4.9,
  // F-4.8-D-01), same as `trust-surface.spec.ts`'s helper opens it.
  await expect(page.getByTestId("sources-disclosure")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("sources-disclosure").getByText("Sources", { exact: true }).click();
}

test.describe("citation host allowlist", () => {
  test("an off-host citation renders unlinked, with the disclosure text", async ({ page }) => {
    await askWithScriptedCitations(page);

    const card = page.getByTestId("source-1");
    await expect(card).toBeVisible();
    // POPULATE-CHECK: without this the anchor-absence assertion below could
    // not tell "the URL is not rendered as a link" from "the card never
    // rendered at all".
    await expect(card, "populate-check failed: the source card is empty").toContainText(
      "evil.example.com",
    );

    await expect(
      card.locator("a"),
      "an off-host citation rendered as a clickable link",
    ).toHaveCount(0);
    await expect(card).toContainText("Not linked: this URL is not on a recognised NCBI host.");
  });

  test("a javascript: URL renders unlinked, with the disclosure text", async ({ page }) => {
    await askWithScriptedCitations(page);

    const card = page.getByTestId("source-2");
    await expect(card).toBeVisible();
    await expect(card, "populate-check failed: the source card is empty").toContainText(
      "javascript:alert(1)",
    );

    await expect(
      card.locator("a"),
      "a javascript: URL rendered as a clickable link",
    ).toHaveCount(0);
    await expect(card).toContainText("Not linked: this URL is not on a recognised NCBI host.");
  });

  test("a citation on an allowed NCBI host renders as a real, clickable link", async ({
    page,
  }) => {
    await askWithScriptedCitations(page);

    const card = page.getByTestId("source-3");
    await expect(card).toBeVisible();

    const link = card.locator("a");
    await expect(link, "an on-host citation did not render as a link at all").toHaveCount(1);
    await expect(link).toHaveAttribute("href", "https://www.ncbi.nlm.nih.gov/gene/672");
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
    await expect(card).not.toContainText("Not linked");
  });
});
