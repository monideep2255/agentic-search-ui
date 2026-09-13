/**
 * T-4.13-03/05 and fix set 4's requirement R46: a signed-in account's past
 * search survives a reload, AND so does the sign-in itself, measured
 * against the real backend (`mock_llm_backend.py`'s real, unmodified
 * `app.py`, only the outbound LLM call faked, the same backend every other
 * spec in this directory drives).
 *
 * WHAT CHANGED HERE, AND WHY THE OLD VERSION SIGNED BACK IN. This file used
 * to reload and then log in again on every attempt, because `App.tsx` held
 * the access token in React state alone and never persisted the refresh
 * token the backend has issued since build phase 1.1, so a bare reload
 * always dropped a signed-in visitor back to signed out. Its own docstring
 * named that as a real, separate gap needing its own security review.
 * Product-owner decision U8 (2026-09-12) closed it: the refresh token is
 * persisted, the access token is re-minted from it on load, and the rail
 * refills off the restored token. So this spec no longer signs back in, and
 * that removal is the assertion: if the restore regressed, the app bar would
 * show Log in, the rail would be empty, and nothing here would paper over it
 * by logging in first.
 *
 * WHY THIS STILL RETRIES RELOAD RATHER THAN WAITING ONCE. The `interactions`
 * row this reads back is written by a server-side background task dispatched
 * after the run's `done` event (Section 16, best-effort capture), with no
 * client-visible completion signal this suite is allowed to wait on: adding
 * one would mean a new debug route in
 * `tests/e2e_support/mock_llm_backend.py`, out of scope here. A single
 * `GET /v1/history` fetched too early simply returns an empty list with no
 * error, so there is nothing to retry against inside one attempt. This
 * therefore polls the actual mechanism under test, a fresh load, up to
 * `MAX_ATTEMPTS` times with a short backoff.
 *
 * EACH RELOAD ROTATES THE CREDENTIAL, which makes the retry loop worth more
 * than its own patience: `POST /auth/refresh` revokes the token it is given
 * and issues a replacement, and replaying a revoked one revokes the whole
 * family and answers 401 (F-1.1-07). So a restore that stored the token it
 * SENT rather than the one it RECEIVED would survive attempt one and fail
 * every attempt after it, and a restore that fired twice per load would fail
 * on the first.
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

test.describe("durable history and a durable sign-in across a reload (T-4.13-03, R46)", () => {
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

    const nav = page.getByRole("navigation", { name: /main/i });

    let restored = false;
    for (let attempt = 0; attempt < MAX_ATTEMPTS && !restored; attempt++) {
      // A short backoff before each attempt: the FIRST reload happens
      // immediately after landing, on purpose, to prove the fast path
      // works when capture is quick; later attempts give the background
      // write more room if it was not.
      if (attempt > 0) await page.waitForTimeout(1_500 * attempt);

      await page.reload();
      // sessionStorage survives a reload in the same tab, so the
      // disclaimer does not reappear.
      //
      // R46: NOBODY LOGS IN HERE. The reload restores the session from the
      // persisted refresh token, so the app bar names the account and the
      // Log in button is gone. Both halves are asserted, because either one
      // alone would pass against a half-restored shell.
      await expect(nav.getByRole("button", { name: new RegExp(escapeRegExp(email), "i") })).toBeVisible({
        timeout: 20_000,
      });
      await expect(nav.getByRole("button", { name: /^log in$/i })).toHaveCount(0);
      await expect(
        page.getByRole("main").getByRole("textbox", { name: /question/i }),
      ).toBeVisible({ timeout: 20_000 });

      const rail = page.getByTestId("history-rail");
      restored = await rail
        .getByRole("button", { name: new RegExp(escapeRegExp(question), "i") })
        .isVisible()
        .catch(() => false);
    }

    expect(
      restored,
      `the question was never restored into the rail after ${MAX_ATTEMPTS} reloads without signing in again`,
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
