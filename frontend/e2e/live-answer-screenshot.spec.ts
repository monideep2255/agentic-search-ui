/**
 * DIAGNOSTIC, not a gate. Lands one real answer on the DEPLOYED demo and
 * captures the answer screen, for two open tickets at once:
 *
 *   - T-4.16-02, defect 2. The second turn provably works in both
 *     environments, so "then chat does not continue" is about something
 *     other than a failed dispatch. The live run reported the follow-up
 *     field as not visible the instant the answer landed, which is the only
 *     lead there is.
 *   - T-4.16-03, defect 4, "the answer presentation is horrible and nothing
 *     close to what the design sync had". `Design_to_build_workflow.md`
 *     forbids guessing at this, so the gap list has to come from looking at
 *     the rendered page beside the component cards.
 *
 * Reaches the public internet and spends one of a guest's five real
 * answers, so it is skipped by default and run explicitly.
 */

import { expect, test, type Page } from "@playwright/test";

// T-6.2-12: the target is no longer hardcoded, and it is no longer
// PRODUCTION. Every measurement in `UI_feedback.md` was taken against
// production and should not have been: production lags whatever is
// being worked on, so a run there measures an older build than the one
// anyone is fixing. Defaults to develop, overridable with
// S3_LIVE_WEB_URL. See `live-target.ts`.
import { LIVE_WEB_URL as LIVE, describeTarget } from "./live-target";

async function enterApp(page: Page): Promise<void> {
  await page.goto(LIVE, { waitUntil: "domcontentloaded" });
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

// GATED, and this line is the gate rather than the docstring above it.
// Both of these files reach the public internet, spend one of a real
// guest's five answers and real model budget on every run. The first
// draft of each said "skipped by default" in its docstring and had NO
// skip, so an ordinary `npx playwright test` would have fired them, and
// a CI run would have fired them on every pull request. A comment
// claiming a property is not that property, which is this repository's
// F-2.1-J5-01 lesson reached from a new direction.
const LIVE_ENABLED = process.env.RUN_LIVE_DIAGNOSTICS === "1";

test.describe(LIVE_ENABLED ? "LIVE diagnostic" : "LIVE diagnostic (skipped: set RUN_LIVE_DIAGNOSTICS=1)", () => {
  test.skip(!LIVE_ENABLED, "reaches the deployed demo and spends real budget");
  test.describe.configure({ timeout: 180_000 });

  // T-6.2-12: record which deployment actually answered, read from the
  // API's own /health rather than inferred from the URL. A screenshot of
  // an answer screen looks identical whichever app produced it, and an
  // evidence file that does not say which one cannot be compared against
  // a later run.
  test.beforeAll(async () => {
    console.log(`[live target] ${await describeTarget()}`);
  });

  test("capture the deployed answer screen", async ({ page }, testInfo) => {
    testInfo.annotations.push({ type: "live-target", description: await describeTarget() });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await enterApp(page);
    const main = page.getByRole("main");

    await main.getByRole("textbox", { name: /question/i }).fill(
      "Which diseases are associated with BRCA1?",
    );
    await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();

    // `answer-meta` only, NEVER "New search". That button is on the run
    // screen too, so waiting for it captures a stepper mid-run rather than
    // an answer. The first version of this file did exactly that and
    // produced a screenshot of five pending pips.
    await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 120_000 });

    // Settle, so late-rendering pieces are in the capture.
    await page.waitForTimeout(1_500);

    const dir = process.env.SHOT_DIR ?? testInfo.outputPath();
    await page.screenshot({ path: `${dir}/live-answer-full.png`, fullPage: true });
    await page.screenshot({ path: `${dir}/live-answer-fold.png` });
    console.log("SAVED:", dir);

    const followUp = page.getByTestId("follow-up");
    console.log("follow-up in DOM:", await followUp.count());
    console.log("follow-up visible:", await followUp.isVisible().catch(() => false));
    const fuBox = await followUp.boundingBox().catch(() => null);
    console.log("follow-up box:", JSON.stringify(fuBox));
    console.log("page height:", await page.evaluate(() => document.body.scrollHeight));

    const vp = page.viewportSize()!;
    for (const id of ["follow-up", "feedback", "sources-disclosure", "answer-meta"]) {
      const loc = page.getByTestId(id);
      const n = await loc.count();
      const bb = n ? await loc.first().boundingBox() : null;
      console.log(
        `${id}: count=${n}` +
          (bb ? ` y=${Math.round(bb.y)} belowFold=${bb.y > vp.height}` : ""),
      );
    }
  });
});
