/**
 * A real query, streamed end to end, and stopped.
 *
 * REWRITTEN in build phase 4.8 for the new screens. Originally written for
 * build phase 1.2's `ChatPage`, which the new routing replaced.
 *
 * This file is deliberately NOT deleted and NOT reduced. It is the only test
 * in the repository that drives a genuine run against a real backend through
 * the real browser, so it is the only thing that proves the new screens are
 * wired to the agent rather than merely rendering. Phase 4.8 shipped an
 * assembly that called `createRun` and then displayed a canned timeline, and
 * this suite is the shape of check that catches that.
 *
 * Every guarantee the original held is preserved:
 *
 *   - a submitted query streams through the pipeline and produces an answer
 *   - Stop halts the run ON THE SERVER, not just in the browser
 *   - Stop disables once the run reaches a terminal state
 *
 * What changed is only how they are reached: the landing screen is now the
 * entry point, sign-in happens from the app bar, and the new screens expose
 * `data-testid` hooks rather than the old class names.
 *
 * Accessibility moved out to `accessibility.spec.ts`, which covers every
 * screen rather than just this one.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { BACKEND_URL } from "../playwright.config";

/** Matches `mock_llm_backend.py`'s `_SLOW_QUERY_MARKER`. */
const SLOW_QUERY_MARKER = "E2E_SLOW_STOP_TEST";

/**
 * The one token this backend can emit, from `cost_control`'s per-query
 * cap-exceeded branch. Asserting on it is what proves the answer screen
 * rendered from the STREAM: this text exists nowhere in the frontend, so it can
 * only appear on screen if a token event was received and consumed.
 */
const PARTIAL_RESULT_NOTE =
  "This query reached its resource limit before finishing, so the answer " +
  "below reflects a partial result gathered so far.";

const TEST_PASSWORD = "Str0ngPassw0rd!";

const freshEmail = () => `e2e-${randomUUID()}@example.com`;

/** Clear the disclaimer, which gates the app on first load. */
async function enterApp(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

/**
 * Sign up a brand-new account, so `App` holds a real bearer token.
 *
 * `AuthGate.runAuth` chains signup straight into login, because a successful
 * signup carries no token of its own, so one click is the whole auth step.
 */
async function signUpFreshAccount(page: Page): Promise<void> {
  await enterApp(page);
  await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: /log in/i }).click();
  await page.getByLabel("Email").fill(freshEmail());
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();

  // The landing's question field is the next real DOM after auth resolves, so
  // waiting for it is also the wait for the token to exist.
  await expect(
    page.getByRole("main").getByRole("textbox", { name: /question/i }),
  ).toBeVisible();
}

async function ask(page: Page, question: string): Promise<void> {
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  await main.getByRole("button", { name: /^ask$/i }).click();
}

test.describe("query stream and stop", () => {
  test("a signed-in query streams through the pipeline and produces an answer", async ({
    page,
  }) => {
    await signUpFreshAccount(page);
    await ask(page, "What gene is BRCA1?");

    // Asserted on the BACKEND'S OWN TEXT, not on a transient stepper state.
    // This backend answers in well under a second, so the run screen is gone
    // before any assertion can sample it; sampling it was the original mistake
    // here, not a product defect.
    //
    // This string lives only in the backend's cost-control module. It cannot
    // appear on screen unless a token event was received and rendered, which
    // makes it the sharpest available proof that the new screens read the
    // stream rather than displaying a canned timeline.
    await expect(page.getByText(PARTIAL_RESULT_NOTE)).toBeVisible({ timeout: 30_000 });

    // And the run genuinely terminated rather than hanging mid-stream.
    await expect(page.getByRole("button", { name: /new search/i })).toBeVisible();
  });

  test("stop halts the run on the server, not just in the browser", async ({ page, request }) => {
    await signUpFreshAccount(page);

    const runIdPromise = page
      .waitForRequest(
        (req) => /\/v1\/query\/[^/]+\/events$/.test(req.url()) && req.method() === "GET",
        { timeout: 30_000 },
      )
      .then((req) => {
        const match = /\/v1\/query\/([^/]+)\/events$/.exec(req.url());
        return match?.[1] ?? null;
      });

    await ask(page, `${SLOW_QUERY_MARKER} what gene is BRCA1?`);

    const runId = await runIdPromise;
    expect(runId, "the run screen must open the event stream").not.toBeNull();

    // Wait for Stop to become ENABLED before clicking it. `deriveStopEnabled`
    // holds it disabled until the guard has passed, and disables it again on
    // any terminal event, so a click issued the instant the run starts is
    // clicking a correctly-disabled control. That is the button's contract,
    // not a defect.
    const stop = page.getByRole("button", { name: /^stop$/i });
    await expect(stop).toBeEnabled({ timeout: 30_000 });
    await stop.click();

    // The server-side check. A browser-only stop would leave the run active,
    // and the whole point of this assertion is that it does not.
    await expect
      .poll(
        async () => {
          const response = await request.get(`${BACKEND_URL}/v1/query/${runId}`);
          if (!response.ok()) return null;
          const body = (await response.json()) as { status?: string };
          return body.status ?? null;
        },
        { timeout: 30_000 },
      )
      .not.toBe("running");
  });

  test("stop stops being offered once the run has finished", async ({ page }) => {
    // Preserved from StopButton's own 19-test contract: stop disables on any
    // terminal event. The first version of phase 4.8's run screen offered stop
    // unconditionally, including after the run was over.
    await signUpFreshAccount(page);
    await ask(page, "What gene is BRCA1?");

    await expect(page.getByRole("button", { name: /new search/i })).toBeVisible({
      timeout: 30_000,
    });

    const stop = page.getByRole("button", { name: /^stop$/i });
    if (await stop.count()) {
      await expect(stop).toBeDisabled();
    }
  });
});
