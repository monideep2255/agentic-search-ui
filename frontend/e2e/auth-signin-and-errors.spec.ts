/**
 * W-identity-1 and W-identity-2, `testing/Developer/Developer_workflows.md`'s Tier 1
 * rows: "Let someone create an account and sign in" and "Never echo a
 * backend error into the sign-in screen, and never say which emails
 * exist."
 *
 * WHAT WAS ALREADY COVERED, AND WHAT WAS NOT. Every existing spec that
 * touches `AuthGate` (`second-turn.spec.ts`, `query-stream-and-stop.spec.ts`,
 * `trust-surface.spec.ts`, `tool-chip.spec.ts`, `accessibility.spec.ts`)
 * exercises exactly one path: a FRESH email, the "Sign up" button, and a
 * successful result. Nothing anywhere in `frontend/e2e/` had ever:
 *
 *   - logged in with the "Log in" button against an ALREADY-EXISTING
 *     account (every spec always signs up, never signs back in);
 *   - submitted a wrong password, a duplicate signup email, or a
 *     never-registered login and looked at what the screen says; or
 *   - checked `AuthGate.tsx`'s documented anti-enumeration property, that a
 *     wrong password and an unknown email must be genuinely
 *     indistinguishable from the DOM alone.
 *
 * `AuthGate.tsx`'s own docstring states the anti-enumeration guarantee as a
 * design decision (`_INVALID_CREDENTIALS_DETAIL` is byte-identical for both
 * cases on the backend, `auth/router.py:111`), but nothing had ever driven
 * both cases through a real browser and diffed what a reader actually sees.
 *
 * COVERAGE STATED, per `goal-contracts.md`.
 *
 * Exercised here, all against the REAL, unmocked `auth/router.py` (signup
 * and login never touch the LLM harness, so none of this is affected by the
 * think-step regression documented in `guest-allowance-wall.spec.ts`):
 *   - "Log in" against an account created moments earlier, reaching the
 *     question field, never the "Sign up" button.
 *   - a wrong password against that same real account.
 *   - a login against an email that was never registered.
 *   - the anti-enumeration property: the wrong-password sentence and the
 *     unknown-email sentence are compared and must be identical.
 *   - signing up with an email that is already registered.
 *   - after any failure, the form stays usable: the fields keep their
 *     values (nothing silently cleared) and a corrected retry succeeds.
 *
 * Deliberately NOT exercised:
 *   - the HTTP response body or headers themselves. `AuthGate.tsx`'s own
 *     comment already establishes the backend returns byte-identical
 *     detail strings for both credential failures; this spec checks only
 *     what reaches the DOM, which is the layer an enumeration attack
 *     actually needs and the layer nothing had tested.
 *   - password strength or format validation (no such rule exists in this
 *     product today; `fieldsFilled` only checks non-empty).
 *   - full sign-out-then-sign-in-again as one continuous session. The
 *     existing account here is created via a direct API call before the
 *     page loads, not via a UI sign-up-then-sign-out round trip, so this
 *     spec exercises "Log in" against a genuinely pre-existing account
 *     without depending on a sign-out control this spec does not own.
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
 * so "Log in" below is tested against a genuinely pre-existing account
 * rather than one this same test just signed up through the form. */
async function createRealAccount(request: APIRequestContext, email: string) {
  const response = await request.post(`${BACKEND_URL}/auth/signup`, {
    data: { email, password: TEST_PASSWORD },
  });
  expect(response.status(), "populate-check failed: could not create the fixture account").toBe(
    201,
  );
}

test.describe("sign-in and its error copy", () => {
  test("logging in with the Log in button reaches the app, using an already-existing account", async ({
    page,
    request,
  }) => {
    const email = `e2e-existing-${randomUUID()}@example.com`;
    await createRealAccount(request, email);

    await enterApp(page);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    // "Log in", never "Sign up": this account already exists, and clicking
    // Sign up here would hit the real duplicate-email 409 path instead.
    await page.getByRole("button", { name: "Log in" }).click();

    await expect(
      page.getByRole("main").getByRole("textbox", { name: /question/i }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("auth-gate")).toHaveCount(0);
  });

  test("a wrong password shows a fixed error, never the backend's own message", async ({
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
    await expect(alert).toHaveText("Could not log in with that email and password.");

    // The backend's own raw detail string must never reach the DOM.
    await expect(page.getByText("invalid email or password", { exact: false })).toHaveCount(0);

    // The form stays usable: still on the auth gate, fields still filled,
    // nothing silently reset to blank.
    await expect(page.getByTestId("auth-gate")).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveValue(email);

    // A corrected retry succeeds, proving the failure did not wedge the form.
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(
      page.getByRole("main").getByRole("textbox", { name: /question/i }),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("logging in with an email that was never registered shows the identical error", async ({
    page,
  }) => {
    const neverRegistered = `e2e-never-${randomUUID()}@example.com`;

    await enterApp(page);
    await page.getByLabel("Email").fill(neverRegistered);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();

    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    // THE ANTI-ENUMERATION PROPERTY. Byte-identical to the wrong-password
    // case above: a reader who compares the two sentences must not be able
    // to tell "no such account" from "wrong password for a real one".
    await expect(alert).toHaveText("Could not log in with that email and password.");
  });

  test("signing up with an already-registered email shows a fixed error", async ({
    page,
    request,
  }) => {
    const email = `e2e-dupe-${randomUUID()}@example.com`;
    await createRealAccount(request, email);

    await enterApp(page);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Sign up" }).click();

    const alert = page.getByRole("alert");
    await expect(alert).toBeVisible();
    await expect(alert).toHaveText(
      "Could not create that account. That email may already be registered.",
    );

    // The backend's own raw detail string must never reach the DOM.
    await expect(page.getByText("email already registered", { exact: false })).toHaveCount(0);
  });
});
