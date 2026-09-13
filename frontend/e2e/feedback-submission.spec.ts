/**
 * T-4.6-09: the feedback surface, exercised end to end against the real
 * backend (only the outbound LLM call faked, per `mock_llm_backend.py`'s
 * own docstring, the same backend `query-stream-and-stop.spec.ts` drives).
 *
 * WHY THIS FILE EXISTS, beyond `FeedbackSurface.test.tsx` and
 * `AnswerScreen.feedback.test.tsx`'s jsdom coverage. This repository's own
 * phase notes, quoted in this ticket's brief: "Nothing in this repository
 * looks at the rendered page... found by starting the application and
 * looking at it." A jsdom test proves the component calls `postFeedback`
 * with the right arguments against a MOCKED module. It cannot prove a real
 * browser click reaches a real running backend, that the backend's real
 * `POST /v1/query/{run_id}/feedback` route (`app.py`'s
 * `post_v1_query_feedback`, T-4.6-08) accepts the payload, or that the
 * whole path composes end to end.
 *
 * CURRENT STATUS, recorded here rather than left to be rediscovered. This
 * ticket's file scope was `FeedbackSurface.tsx`, `AnswerScreen.tsx` (only
 * where it renders the feedback surface), `lib/api.ts` and the stub
 * registry; `App.tsx` (the "assembly", T-4.8-12) was explicitly out of
 * scope for T-4.6-09, owned by a concurrent ticket in this same phase.
 * `AnswerScreen` accepts `runId`/`authToken` props and threads them
 * straight into `FeedbackSurface`. F-4.6-08 closed the remaining gap:
 * `App.tsx` now passes its own `runId` state and `authToken` (the same
 * values `useAgentRun` and the Stop action already read) onto
 * `<AnswerScreen>`, so a real landed answer carries a real POST target.
 *
 * This spec proves BOTH states honestly, rather than asserting only the
 * happy path:
 *
 *   - the now-reachable send path: a rating actually reaches the real
 *     backend and the panel confirms it. Previously `test.fixme`, un-skipped
 *     once F-4.6-08 landed this wiring.
 *   - the one case that stays genuinely blocked even with the wiring
 *     landed: `createRun` itself can still fail (a network error, a
 *     dropped connection) before any run exists at all, and that path
 *     never sets `runId`. `FeedbackSurface` must keep refusing visibly
 *     there, since there is nothing to attach feedback to. This replaces
 *     the old "today, sending visibly refuses" test, which asserted the
 *     unwired behaviour on a run that HAD landed; that premise is false
 *     now that `App.tsx` supplies `runId`/`authToken` on every landed
 *     answer, so the refusal is exercised on the one path where it is
 *     still the correct, honest outcome.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const TEST_PASSWORD = "Str0ngPassw0rd!";
const freshEmail = () => `e2e-feedback-${randomUUID()}@example.com`;

async function enterApp(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

async function signUpFreshAccount(page: Page): Promise<void> {
  await enterApp(page);
  await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: /log in/i }).click();
  await page.getByLabel("Email").fill(freshEmail());
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("main").getByRole("textbox", { name: /question/i }),
  ).toBeVisible({ timeout: 20_000 });
}

async function ask(page: Page, question: string): Promise<void> {
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

test.describe("feedback submission", () => {
  test("the panel renders on a real landed answer and a rating is selectable", async ({
    page,
  }) => {
    await signUpFreshAccount(page);
    await ask(page, "What gene is BRCA1?");
    await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
      timeout: 30_000,
    });

    const panel = page.getByTestId("feedback");
    await expect(panel).toBeVisible();
    const helpful = panel.getByRole("button", { name: "Helpful", exact: true });
    await helpful.click();
    await expect(helpful).toHaveAttribute("aria-pressed", "true");
    await expect(panel.getByRole("button", { name: /^send feedback$/i })).toBeVisible();
  });

  /**
   * T-4.16-10. The product owner's defect 7, from the live demo: "the
   * feedback buttons were not working properly. The down arrow was outside
   * the box."
   *
   * IT IS ONE DEFECT WITH TWO SYMPTOMS, and the functional one falls out of
   * the visual one. `Thumb`'s rotation was on the outermost `<svg>`, where
   * `transform` is resolved as a CSS transform in the element's own pixel
   * space rather than as an SVG transform in the viewBox coordinate system.
   * `rotate(180 8 8)` therefore rotated about a point 8 CSS pixels from the
   * element origin instead of about the centre of a `0 0 16 16` viewBox,
   * displacing the glyph 16px down and right. The `<button>` stayed a
   * correct 30x30 hit target, so the thumb a person could SEE sat outside
   * the control it belonged to and clicking it missed.
   *
   * WHY IT IS HERE AND NOT IN JSDOM. All 211 vitest tests assert what is on
   * screen and never WHERE it is, and jsdom has no layout at all, so a pure
   * geometry defect is invisible to every one of them. `LEARNINGS.md` rows
   * 107, 108 and 109 are three prior instances of exactly this, including
   * one where a guard written for the blind spot HAD the blind spot because
   * it compared DOM order instead of position. Bounding boxes in a real
   * browser are the only thing that sees this class.
   *
   * MUTATION PROOF, run before this was committed. Moving the `transform`
   * back from the inner `<g>` onto the `<svg>` makes this test fail on the
   * down thumb with right and bottom overflow of 8.5px, and leaves the up
   * thumb green, which is the asymmetry the defect actually had. Measured
   * in Chromium rather than reasoned about, because the two placements are
   * one word apart and read identically.
   */
  test("both feedback thumbs render inside their own buttons", async ({ page }) => {
    await signUpFreshAccount(page);
    await ask(page, "What gene is BRCA1?");
    await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
      timeout: 30_000,
    });

    const panel = page.getByTestId("feedback");
    await expect(panel).toBeVisible();

    for (const [label, glyph] of [
      ["Helpful", "thumb-up-glyph"],
      ["Not helpful", "thumb-down-glyph"],
    ] as const) {
      const button = panel.getByRole("button", { name: label, exact: true });
      const box = await button.boundingBox();
      const icon = await panel.locator(`[data-testid="${glyph}"]`).boundingBox();

      // POPULATE-CHECK. Without it a missing button or a missing glyph
      // would make every comparison below vacuously unreachable rather
      // than false, and the arm would report success on a surface that
      // rendered nothing at all.
      expect(box, `${label}: the button itself did not render`).not.toBeNull();
      expect(icon, `${label}: the thumb glyph did not render`).not.toBeNull();
      expect(icon!.width, `${label}: the glyph has no width to measure`).toBeGreaterThan(4);

      // Half a pixel of tolerance for sub-pixel rounding, which is far
      // below the 8.5px the real defect overflowed by, so this cannot pass
      // the regression while still tolerating ordinary rasterisation.
      const slack = 0.5;
      expect(icon!.x, `${label}: glyph overflows its button on the left`).toBeGreaterThanOrEqual(
        box!.x - slack,
      );
      expect(icon!.y, `${label}: glyph overflows its button on the top`).toBeGreaterThanOrEqual(
        box!.y - slack,
      );
      expect(
        icon!.x + icon!.width,
        `${label}: glyph overflows its button on the right`,
      ).toBeLessThanOrEqual(box!.x + box!.width + slack);
      expect(
        icon!.y + icon!.height,
        `${label}: glyph overflows its button on the bottom`,
      ).toBeLessThanOrEqual(box!.y + box!.height + slack);
    }
  });

  // F-4.6-08. REPLACES the old "today, sending visibly refuses... pending
  // App.tsx's runId/authToken wiring" test, which asserted the unwired
  // behaviour on a run that had actually landed. That premise is false now
  // that `App.tsx` passes its own `runId`/`authToken` to `AnswerScreen` on
  // every landed answer (see the module docstring's CURRENT STATUS). The
  // one path that still has no run to attach feedback to is a `createRun`
  // failure itself: `App.tsx` never calls `setRunId` on that path, so it is
  // the genuine, still-current case for this refusal, not the wiring gap.
  //
  // Mutation proof: reverting the `App.tsx` fix (dropping `runId={runId}
  // authToken={authToken}` from the `<AnswerScreen>` call) makes the FIRST
  // test below fail, since `postFeedback` would never be reached at all.
  // Reverting `FeedbackSurface`'s own guard (removing the `runId === null
  // || authToken === null` check) makes the SECOND test below fail, since
  // it would then attempt a POST to a URL built from a null run id instead
  // of refusing visibly. Both were run and confirmed red, then restored.
  test("a dispatched question with no run yet still refuses feedback visibly, never silently", async ({
    page,
  }) => {
    await signUpFreshAccount(page);
    // Force createRun to fail before any run_id exists, reproducing the one
    // case that survives F-4.6-08's fix: a dispatch failure, not a wiring
    // gap. Matches only the exact `POST /v1/query` call, not
    // `/v1/query/{id}/events`, `/stop`, or `/feedback`.
    await page.route("**/v1/query", (route) => route.abort("failed"));

    await ask(page, "What gene is BRCA1?");
    await expect(page.getByTestId("answer-failure")).toBeVisible({ timeout: 10_000 });

    const feedbackPost = page.waitForRequest(
      (req) => /\/v1\/query\/[^/]+\/feedback$/.test(req.url()),
      { timeout: 3_000 },
    );

    const panel = page.getByTestId("feedback");
    await panel.getByRole("button", { name: "Helpful", exact: true }).click();
    await panel.getByRole("button", { name: /^send feedback$/i }).click();

    await expect(page.getByRole("alert")).toHaveText(/feedback is not available/i);
    await expect(feedbackPost).rejects.toThrow();
  });

  // F-4.6-08: App.tsx now threads runId/authToken into AnswerScreen, so this
  // is the real send-to-backend path rather than the known-blocked case.
  // Un-skipped, not weakened; every assertion below is unchanged from the
  // fixme version.
  test(
    "a rating actually reaches the backend and the panel confirms it",
    async ({ page }) => {
      await signUpFreshAccount(page);
      await ask(page, "What gene is BRCA1?");
      await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
        timeout: 30_000,
      });

      const feedbackPost = page.waitForRequest(
        (req) => /\/v1\/query\/[^/]+\/feedback$/.test(req.url()) && req.method() === "POST",
      );

      const panel = page.getByTestId("feedback");
      await panel.getByRole("button", { name: "Helpful", exact: true }).click();
      await panel.getByRole("button", { name: /^send feedback$/i }).click();

      const request = await feedbackPost;
      const response = await request.response();
      expect(response?.status()).toBe(204);
      await expect(page.getByText(/thanks\. this goes to the review queue/i)).toBeVisible();
    },
  );
});
