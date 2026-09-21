/**
 * W-identity-1 and W-identity-2, `testing/Developer/Developer_workflows.md`'s Tier 1
 * rows: "Let someone create an account and sign in" and "Never echo a
 * backend error into the sign-in screen".
 *
 * SET 1 CHANGE, 2026-09-12 (`testing/UI_fix_plan.md`, R5 and X3). The sign-in
 * screen has ONE button, Log in. It tries signup first: a new email creates
 * the account, and a registered email logs in. Decision X3 accepted that a
 * wrong password for a registered email now says so, which reveals that the
 * email is registered. So the anti-enumeration clause this spec used to hold,
 * "a wrong password and an unknown email show identical text", is replaced by
 * its new truth: an unknown email creates an account.
 *
 * COVERAGE STATED, per `goal-contracts.md`.
 *
 * Exercised here, all against the REAL, unmocked `auth/router.py` (signup
 * and login never touch the LLM harness):
 *   - Log in against an account created moments earlier, reaching the
 *     question field.
 *   - Log in with a never-registered email creating the account and reaching
 *     the question field.
 *   - a wrong password against a real account showing the fixed
 *     wrong-password sentence, never the backend's own message, and a
 *     corrected retry succeeding with the form still filled.
 *   - exactly one button on the sign-in screen.
 *
 * Deliberately NOT exercised:
 *   - the HTTP response bodies themselves; only what reaches the DOM.
 *   - password strength or format validation (no such rule exists in this
 *     product today; `fieldsFilled` only checks non-empty).
 *   - the guest token reaching signup or login, which `AuthGate.test.tsx`
 *     and `phase410Premise.test.tsx` assert against mocked calls.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { BACKEND_URL } from "../playwright.config";

const TEST_PASSWORD = "Str0ngPassw0rd!";
const WRONG_PASSWORD = "WrongPassw0rd!";

async function enterApp(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
  await page
    .getByRole("navigation", { name: /main/i })
    .getByRole("button", { name: /log in/i })
    .click();
  await expect(page.getByTestId("auth-gate")).toBeVisible();
}

/** Creates a real account directly against the backend, bypassing the UI,
 * so Log in below is tested against a genuinely pre-existing account. */
async function createRealAccount(request: APIRequestContext, email: string) {
  const response = await request.post(`${BACKEND_URL}/auth/signup`, {
    data: { email, password: TEST_PASSWORD },
  });
  expect(response.status(), "populate-check failed: could not create the fixture account").toBe(
    201,
  );
}

const questionField = (page: Page) =>
  page.getByRole("main").getByRole("textbox", { name: /question/i });

test.describe("sign-in and its error copy", () => {
  test("the sign-in screen offers exactly one button, Log in", async ({ page }) => {
    await enterApp(page);
    const gate = page.getByTestId("auth-gate");
    await expect(gate.getByRole("button")).toHaveCount(1);
    await expect(gate.getByRole("button", { name: "Log in" })).toBeVisible();
    await expect(gate.getByRole("button", { name: /sign up/i })).toHaveCount(0);
  });

  test("Log in reaches the app for an already-existing account", async ({ page, request }) => {
    const email = `e2e-existing-${randomUUID()}@example.com`;
    await createRealAccount(request, email);

    await enterApp(page);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();

    await expect(questionField(page)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("auth-gate")).toHaveCount(0);
  });

  test("Log in with a never-registered email creates the account and reaches the app", async ({
    page,
    request,
  }) => {
    const email = `e2e-new-${randomUUID()}@example.com`;

    await enterApp(page);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();

    await expect(questionField(page)).toBeVisible({ timeout: 20_000 });
    // The account now really exists: a direct login with the same password
    // succeeds against the unmocked backend.
    const login = await request.post(`${BACKEND_URL}/auth/login`, {
      data: { email, password: TEST_PASSWORD },
    });
    expect(login.status()).toBe(200);
  });

  test("a wrong password says so in a fixed sentence, never the backend's own message", async ({
    page,
    request,
  }) => {
    const email = `e2e-wrongpw-${randomUUID()}@example.com`;
    await createRealAccount(request, email);

    await enterApp(page);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(WRONG_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();

    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).toHaveText("That password does not match this email. Check it and try again.");

    // The backend's own raw detail strings must never reach the DOM.
    await expect(page.getByText("invalid email or password", { exact: false })).toHaveCount(0);
    await expect(page.getByText("email already registered", { exact: false })).toHaveCount(0);

    // The form stays usable: still on the auth gate, fields still filled.
    await expect(page.getByTestId("auth-gate")).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveValue(email);

    // A corrected retry succeeds, proving the failure did not wedge the form.
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(questionField(page)).toBeVisible({ timeout: 20_000 });
  });
});
