/**
 * Card 102 (2026-10-07): a reopened saved answer lists its sources.
 *
 * On deployed develop a reopened answer read "Based on 21 sources cited" and
 * then nothing: `GET /v1/history/{trace_id}/answer` sends each citation as
 * stored, with `layer` as the wire string ("layer_2_api"), and the client
 * dropped every one. This opens a saved answer in the real app and asserts
 * what a person sees: the trust line, then one source row per page, as many
 * rows as the line names.
 *
 * The fake-model backend handles sign-up for real. The two history replies
 * are ours, because the fake model's runs cite nothing: the list holds one
 * search with a saved answer, and the answer carries the 18 citations of
 * `fixtures/card22_brca1_citations.json` in the stored shape, every key the
 * deployed reply carried, with obviously fake values where a field is not in
 * the fixture.
 *
 * Phone width follow-up (F-102-V-05): two more pages carry the longest real
 * link shapes, a Pathogen Detection isolate link (the shape
 * `tools/pathogen_detection.py`'s `_build_isolate_source_url` builds) and a
 * seven-digit ClinVar variation link, both with fake IDs. A URL has no
 * spaces, so it only stays inside its row if the row lets it break; the
 * spec checks every link's right edge against its row as well as the page.
 *
 * Screenshots at 1280 and 390 only when CARD102_SHOTS=1.
 */

import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const shots = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-10-07_card102");

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
) as { citations: FixtureCitation[]; expected_after: { sources_cited: number; trust_line: string } };
const AFTER = FIXTURE.expected_after;

/** The longest real link shapes, each its own page, with fake IDs. */
const LONG_LINKS: FixtureCitation[] = [
  {
    display_index: 19,
    source_url: "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:SAMN99999999",
    layer: "layer_2_api",
    source: "Pathogen Detection",
    source_id: "biosample:SAMN99999999",
    field: "isolate",
  },
  {
    display_index: 20,
    source_url: "https://www.ncbi.nlm.nih.gov/clinvar/variation/9999999/",
    layer: "layer_2_api",
    source: "ClinVar",
    source_id: "ClinVar:9999999",
    field: "classification",
  },
];
const ROWS = AFTER.sources_cited + LONG_LINKS.length;
const TRUST_LINE = AFTER.trust_line.replace(String(AFTER.sources_cited), String(ROWS));

const QUESTION = "Which diseases are associated with BRCA1?";
const TRACE_ID = "card102-e2e-trace";

const SAVED_ANSWER = {
  trace_id: TRACE_ID,
  question: QUESTION,
  asked_at: "2026-10-07T04:00:00Z",
  depth: "researcher",
  answer_markdown: "Found 4 disease records for BRCA1 [2][3][4][5]. The gene page is cited three times [1][6][9].",
  citations: [...FIXTURE.citations, ...LONG_LINKS].map((c) => ({
    citation_id: `cit-test-${c.display_index}`,
    display_index: c.display_index,
    source: c.source,
    source_id: c.source_id,
    source_url: c.source_url,
    layer: c.layer,
    field: c.field,
    claim_text: "A test claim.",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "test licence",
    snapshot_date: null,
    entity_name: null,
  })),
  trust_signal: "ask",
  trust_line: TRUST_LINE,
};

async function signInWithOneSavedSearch(page: Page): Promise<void> {
  await page.route(/\/v1\/history(\?[^/]*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            trace_id: TRACE_ID,
            question: QUESTION,
            asked_at: SAVED_ANSWER.asked_at,
            trust_signal: "ask",
            citation_count: ROWS,
            has_saved_answer: true,
          },
        ],
        count: 1,
      }),
    }),
  );
  await page.route(/\/v1\/history\/[^/]+\/answer$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SAVED_ANSWER) }),
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
  await page.getByLabel("Email").fill(`card102-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("main").getByRole("textbox", { name: /question/i })).toBeVisible({
    timeout: 20_000,
  });
}

for (const width of [1280, 390]) {
  test(`a reopened saved answer lists one source row per page under its trust line, at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width < 720 ? 844 : 900 });
    await signInWithOneSavedSearch(page);

    if (width < 720) {
      // On a phone the rail is a panel opened from the app bar.
      const panel = page.getByRole("dialog", { name: /your searches/i });
      const opened = await panel
        .waitFor({ state: "visible", timeout: 5_000 })
        .then(() => true)
        .catch(() => false);
      if (!opened) {
        await page.getByRole("banner").getByRole("button", { name: /show or hide your searches/i }).click();
      }
    }
    await page
      .getByTestId("history-rail")
      .getByRole("button", { name: new RegExp(QUESTION.replace("?", "\\?"), "i") })
      .click();

    if (width < 720) {
      // Tapping a past search leaves the panel open over the answer on a
      // phone (found by this build, reported to the lead, not card 102's
      // fix), so close it as a person would, to read the answer.
      const panel = page.getByRole("dialog", { name: /your searches/i });
      if (await panel.isVisible().catch(() => false)) {
        await panel.getByRole("button", { name: /^hide your searches$/i }).click();
        await expect(panel).toBeHidden();
      }
    }

    const screen = page.getByTestId("saved-answer-screen");
    await expect(screen).toBeVisible({ timeout: 10_000 });
    const trust = screen.getByTestId("saved-answer-trust-line");
    await expect(trust).toContainText(`Based on ${ROWS} sources cited`);

    // The rows a person counts are the sources the line names.
    const rows = screen.getByRole("list").getByRole("listitem");
    await expect(rows).toHaveCount(ROWS);
    const geneRows = rows.filter({ hasText: "/gene/672" });
    await expect(geneRows).toHaveCount(1);
    await expect(geneRows).toContainText("1, 6, 9.");
    // Every row links to its record, except the OMIM page, which is not on
    // an NCBI host and says so ("Not linked"), as on the live answer.
    await expect(screen.getByRole("list").getByRole("link")).toHaveCount(ROWS - 1);
    const notLinked = rows.filter({ hasText: "Not linked" });
    await expect(notLinked).toHaveCount(1);
    await expect(notLinked).toContainText(/^8\. /);

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    // Every link ends inside its own row: a link that runs over the row's
    // border breaks the card even when the page itself does not scroll.
    const spills = await screen.getByRole("list").evaluate((list) =>
      Array.from(list.querySelectorAll("li")).flatMap((row) => {
        const link = row.querySelector("a");
        if (!link) return [];
        const over = link.getBoundingClientRect().right - row.getBoundingClientRect().right;
        return over > 0.5 ? [`${link.getAttribute("href")} by ${Math.round(over)} px`] : [];
      }),
    );
    console.log(`card102 ${width}px: page overflow ${overflow} px, links past their row: ${spills.length}`, spills);
    expect(spills, "every source link stays inside its row").toEqual([]);
    expect(overflow, "the saved answer must not scroll sideways").toBeLessThanOrEqual(0);

    if (process.env.CARD102_SHOTS === "1") {
      await mkdir(shots, { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: path.join(shots, `saved_answer_${width}.png`),
        fullPage: true,
        mask: [page.getByText(/Working as /), page.getByText(/card102-[a-f0-9-]+@example\.com/)],
        maskColor: "#f0f0f0",
      });
    }
  });
}
