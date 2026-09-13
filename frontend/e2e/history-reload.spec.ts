/**
 * T-4.13-03/05: a signed-in account's past search survives a reload,
 * measured against the real backend (`mock_llm_backend.py`'s real,
 * unmodified `app.py`, only the outbound LLM call faked, the same
 * backend every other spec in this directory drives).
 *
 * WHY A RELOAD ALONE IS NOT ENOUGH, and this file signs back in rather
 * than just calling `page.reload()`. `App.tsx`'s access token is held in
 * React state only; unlike the guest token, it is never persisted to
 * `localStorage` (see the seeding effect's own comment in `App.tsx`), so
 * a bare reload always drops a signed-in visitor back to signed out. That
 * is a real, separate gap this ticket does not fix (adding token
 * persistence is a different change, to a different piece of state, with
 * its own security review), and this spec exercises the case that gap
 * still leaves reachable: a person who closes the browser, comes back,
 * and SIGNS BACK IN sees their old searches, which is the phase's own
 * "what this phase is for" sentence (`tracker/phase_4.13.md`).
 *
 * WHY THIS RETRIES RELOAD-AND-LOGIN RATHER THAN WAITING ONCE. The
 * `interactions` row this reads back is written by a server-side
 * background task dispatched after the run's `done` event (Section 16,
 * best-effort capture), with no client-visible completion signal this
 * suite is allowed to wait on: adding one would mean a new debug route in
 * `tests/e2e_support/mock_llm_backend.py`, which is out of this ticket's
 * file scope (`src/` and `tests/` belong to the sibling backend ticket).
 * A single `GET /v1/history` fetched too early would simply return an
 * empty list with no error and nothing to retry against, since the fetch
 * itself succeeds. So this polls the actual mechanism under test, a fresh
 * sign-in, up to `MAX_ATTEMPTS` times with a short backoff, rather than
 * asserting once against a race it cannot see.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const TEST_PASSWORD = "Str0ngPassw0rd!";
const MAX_ATTEMPTS = 6;

async function dismissDisclaimerIfShown(page: Page): Promise<void> {
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

async function signUpFreshAccount(page: Page, email: string): Promise<void> {
  await page.goto("/");
  await dismissDisclaimerIfShown(page);
  await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: /log in/i }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("main").getByRole("textbox", { name: /question/i }),
  ).toBeVisible({ timeout: 20_000 });
}

/** Signs into an ALREADY-REGISTERED account, the "Log in" action, not "Sign up". */
async function logIntoExistingAccount(page: Page, email: string): Promise<void> {
  await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: /log in/i }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(
    page.getByRole("main").getByRole("textbox", { name: /question/i }),
  ).toBeVisible({ timeout: 20_000 });
}

test.describe("durable history across a reload (T-4.13-03)", () => {
  test("a signed-in account's earlier search is restored after closing and reopening the browser", async ({
    page,
  }) => {
    const email = `e2e-history-${randomUUID()}@example.com`;
    const question = "What gene is associated with cystic fibrosis?";

    await signUpFreshAccount(page, email);
    await page.getByRole("main").getByRole("textbox", { name: /question/i }).fill(question);
    await page
      .getByRole("main")
      .getByRole("button", { name: /^search the knowledge graph$/i })
      .click();
    // The run must actually LAND before capture has anything to write.
    await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
      timeout: 30_000,
    });

    let restored = false;
    for (let attempt = 0; attempt < MAX_ATTEMPTS && !restored; attempt++) {
      // A short backoff before each attempt: the FIRST reload happens
      // immediately after landing, on purpose, to prove the fast path
      // works when capture is quick; later attempts give the background
      // write more room if it was not.
      if (attempt > 0) await page.waitForTimeout(1_500 * attempt);

      await page.reload();
      // sessionStorage survives a reload in the same tab, so the
      // disclaimer does not reappear; signing out is what a reload does
      // here, not re-accepting a notice.
      await logIntoExistingAccount(page, email);

      const rail = page.getByTestId("history-rail");
      restored = await rail
        .getByRole("button", { name: new RegExp(escapeRegExp(question), "i") })
        .isVisible()
        .catch(() => false);
    }

    expect(
      restored,
      `the question was never restored into the rail after ${MAX_ATTEMPTS} reload-and-sign-in attempts`,
    ).toBe(true);

    // CLICKING RE-ASKS; IT DOES NOT REPLAY AN ANSWER. The scope boundary
    // this ticket names before any ticket was written (`tracker/
    // phase_4.13.md`, decision D-4.13-01): `interactions` stores no answer
    // narrative, so the ONLY way this reaches a landed answer again is a
    // genuine fresh run through the real agent loop, exactly as clicking a
    // live rail item does today. If a restored item instead replayed
    // cached or fabricated content, this would either show the answer
    // immediately (no run heading, no wait) or show it with nothing behind
    // it; both are the exact fabrication class `App.tsx`'s own file
    // docstring forbids on every other path, and this is what would catch
    // it were it to reappear here.
    const rail = page.getByTestId("history-rail");
    await rail.getByRole("button", { name: new RegExp(escapeRegExp(question), "i") }).click();
    await expect(page.getByRole("heading", { name: question })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
      timeout: 30_000,
    });
  });
});

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
