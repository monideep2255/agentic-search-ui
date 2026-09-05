/**
 * DIAGNOSTIC, not a gate. Points a real browser at the DEPLOYED demo to
 * reproduce the product owner's defect 2, "then chat does not continue",
 * which does NOT reproduce locally against the mock backend on either the
 * signed-in or the guest path.
 *
 * It is quarantined out of the ordinary suite by its own `describe.skip`
 * below, and must be run explicitly. It reaches the public internet, spends
 * two of a guest's five real answers, and costs real model budget, so it is
 * not something a CI run should ever fire on its own.
 */

import { expect, test, type Page } from "@playwright/test";

// T-6.2-12: the target is no longer hardcoded, and it is no longer
// PRODUCTION. Every measurement in `testing/UI_feedback.md` was taken against
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

  // T-6.2-12: see the sibling spec. Which deployment answered is part of
  // the diagnostic, not context someone is expected to remember.
  test.beforeAll(async () => {
    console.log(`[live target] ${await describeTarget()}`);
  });

  test("two turns against the deployed demo, as a guest", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(`console: ${m.text()}`);
    });
    const failedRequests: string[] = [];
    page.on("response", (r) => {
      if (r.status() >= 400) failedRequests.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    });

    await enterApp(page);
    const main = page.getByRole("main");

    await main.getByRole("textbox", { name: /question/i }).fill("What gene is BRCA1?");
    await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();

    const landed = page.getByRole("button", { name: "New search", exact: true });
    await expect(landed).toBeVisible({ timeout: 90_000 });
    console.log("TURN 1 landed");

    const followUp = page.getByTestId("follow-up");
    console.log("follow-up present after turn 1:", await followUp.isVisible().catch(() => false));

    await followUp.getByRole("textbox").fill("What diseases are associated with it?");
    await followUp.getByRole("textbox").press("Enter");
    console.log("TURN 2 submitted");

    await page.waitForTimeout(5_000);
    console.log("5s after turn 2:", JSON.stringify({
      newSearchVisible: await landed.isVisible().catch(() => false),
      followUpVisible: await followUp.isVisible().catch(() => false),
      bodyText: (await page.getByRole("main").textContent().catch(() => ""))?.slice(0, 400),
    }, null, 2));

    const landedAgain = await landed.isVisible({ timeout: 90_000 }).catch(() => false);
    console.log("TURN 2 landed:", landedAgain);
    console.log("FAILED REQUESTS:", JSON.stringify(failedRequests, null, 2));
    console.log("ERRORS:", JSON.stringify(errors, null, 2));
  });
});
