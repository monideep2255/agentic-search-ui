/**
 * DIAGNOSTIC for T-4.16-02. Where does the follow-up field actually sit,
 * at viewport sizes people really use?
 *
 * The product owner reported they could not find it. An earlier note in
 * this phase said it "renders late"; that was WRONG and is corrected here
 * rather than carried: the count of zero came from a capture taken while
 * the run screen was still up, because the landed signal was the "New
 * search" button, which both screens render. With a correct signal the
 * follow-up is in the DOM the moment the answer screen is.
 *
 * So the remaining question is purely positional, and it is measured
 * rather than argued.
 *
 * RESULT, 2026-08-25, and it rules the positional theory out. The input's
 * top is 463px at every viewport tested, including a 13-inch laptop's
 * 650px, so it is ABOVE THE FOLD in all three. On the deployed demo, with
 * a real answer above it, it measured 509px. Position is not why it could
 * not be found.
 *
 * WHAT IS LEFT IS SALIENCE, and one specific competing affordance. "New
 * search" is a bordered button in the answer's top-right corner; the
 * follow-up is a 10.5px uppercase grey label over a quiet field, lower
 * down. A reader who wants to ask another question reaches for the button
 * they can see, which RESETS to the landing screen rather than continuing.
 * That reads exactly as "then chat does not continue" while every
 * mechanism underneath works, which is what this phase measured twice.
 *
 * Kept as a diagnostic rather than promoted to a gate: asserting a
 * pixel offset would pin a layout the design cards own, and the numbers
 * above are evidence for a design decision, not a contract.
 */

import { expect, test, type Page } from "@playwright/test";

const VIEWPORTS = [
  { name: "13in laptop", width: 1280, height: 650 },
  { name: "14in laptop", width: 1440, height: 760 },
  { name: "large display", width: 1440, height: 1000 },
] as const;

async function enterApp(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

test.describe("follow-up position diagnostic", () => {
  for (const vp of VIEWPORTS) {
    test(`where the follow-up sits at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await enterApp(page);

      const main = page.getByRole("main");
      await main.getByRole("textbox", { name: /question/i }).fill("What gene is BRCA1?");
      await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
      await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 60_000 });

      const followUp = page.getByTestId("follow-up");
      const box = await followUp.boundingBox();
      const input = await followUp.getByRole("textbox").boundingBox();
      const scrollHeight = await page.evaluate(() => document.body.scrollHeight);

      console.log(
        `${vp.name} (${vp.width}x${vp.height}): ` +
          `label top=${Math.round(box!.y)} ` +
          `input top=${Math.round(input!.y)} ` +
          `inputBelowFold=${input!.y > vp.height} ` +
          `pageHeight=${scrollHeight} ` +
          `needsScroll=${scrollHeight > vp.height}`,
      );
    });
  }
});
