/**
 * Set 1 (2026-09-12, `testing/UI_fix_plan.md`), R1 to R3: a guest is never
 * limited and never walled.
 *
 * This file used to hold W-GUEST-6, "stop a guest at five answers with an
 * honest wall", skipped because every real run through the mock backend
 * died at the think step before landing. The product owner removed the
 * five-search allowance, the ten-attempt ceiling and every sign-in wall, so
 * the workflow it was written for no longer exists. The file name is kept so
 * its history stays in one place.
 *
 * WHAT THIS CAN CHECK WITHOUT A LANDED ANSWER. Admission is decided when
 * `POST /v1/query` answers, before any model call, so the think-step failure
 * does not affect it. Each ask below waits for that response and requires a
 * 202, which is the real, unmocked server enforcement this spec is about.
 *
 * COVERAGE STATED, per `goal-contracts.md`.
 *
 * Exercised: seven guest asks from one browser, past both the old answer
 * allowance and, counting the old refunds, well into the old attempt
 * ceiling's range; every one admitted 202 by the real server; no allowance
 * dots and no sign-in wall on the landing afterwards.
 *
 * NOT exercised: the ten-attempt boundary itself (the backend premise gate
 * asserts the eleventh attempt is admitted); the shared anonymous daily cap
 * and per-connection share, which still exist and are asserted in the
 * backend premise gate; and any landed answer, since the mock backend still
 * fails at the think step.
 */

import { expect, test, type Page } from "@playwright/test";

const QUESTIONS = [
  "Which diseases are associated with BRCA1?",
  "Which diseases are associated with TP53?",
  "Which diseases are associated with BRCA2?",
  "Which diseases are associated with EGFR?",
  "Which diseases are associated with KRAS?",
  "Which diseases are associated with PTEN?",
  "Which diseases are associated with MLH1?",
];

async function enterApp(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

async function askFromHome(page: Page, question: string): Promise<number> {
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  const [response] = await Promise.all([
    page.waitForResponse(
      (res) => /\/v1\/query$/.test(res.url()) && res.request().method() === "POST",
      { timeout: 20_000 },
    ),
    main.getByRole("button", { name: /^search the knowledge graph$/i }).click(),
  ]);
  return response.status();
}

test.describe("a guest is never limited", () => {
  test("seven guest asks are all admitted, with no dots and no wall", async ({ page }) => {
    for (const [index, question] of QUESTIONS.entries()) {
      // A fresh page load per ask returns to the landing without depending
      // on a run landing. The guest token persists in local storage, so every
      // ask is the SAME guest identity, which is what makes this a check of
      // a per-guest limit rather than of seven separate visitors.
      await enterApp(page);
      const status = await askFromHome(page, question);
      expect(status, `guest ask ${index + 1} was not admitted`).toBe(202);
      await expect(page.getByTestId("sign-in-wall")).toHaveCount(0);
    }

    await enterApp(page);
    await expect(
      page.getByRole("main").getByRole("textbox", { name: /question/i }),
      "populate-check failed: the landing did not render, so the absences below prove nothing",
    ).toBeVisible();
    await expect(page.getByTestId("guest-allowance")).toHaveCount(0);
    await expect(page.getByText(/\d+ searches? left/i)).toHaveCount(0);
  });
});
