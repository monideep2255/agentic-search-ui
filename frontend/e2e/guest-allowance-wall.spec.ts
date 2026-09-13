/**
 * W-GUEST-6, `testing/Developer/Developer_workflows.md`'s Tier 1 row: "Stop a guest at
 * five answers with an honest wall, not a broken page."
 *
 * WHY THIS WAS UNCOVERED AT LAYER A. The only existing coverage is
 * `frontend/e2e/journeys/guest-allowance.spec.ts`, a Layer B journey gated
 * on `RUN_LIVE_JOURNEYS=1`: it spends a real guest's entire five-answer
 * allowance against the DEPLOYED app with a real model call per question,
 * and its own docstring calls this "the entire allowance of one guest
 * identity plus the refusal... run it deliberately and rarely." A Tier 1
 * workflow with no free, deterministic, always-on check is exactly the gap
 * `testing/Developer/Developer_workflows.md`'s three-layer split exists to avoid.
 *
 * WHY THIS SPEC DOES NOT DO WHAT ITS TITLE SAYS YET. The plan was to spend
 * five REAL, free, cap-exceeded runs against the mock backend (which
 * genuinely spends the real, unmocked `guest_sessions` allowance,
 * `FREE_RUN_ALLOWANCE = 5` in `data/guest_sessions.py`) and assert the
 * sixth hits the sign-in wall. Building it surfaced a REGRESSION that
 * blocks it, not a gap in this spec's own design, and it is recorded here
 * rather than papered over with a scripted stream that would stop testing
 * the thing this workflow actually needs proven: real, server-side
 * enforcement.
 *
 * THE REGRESSION, confirmed by direct API calls and a direct read of the
 * `guest_sessions` table (bypassing the browser entirely):
 *
 *   - Every real run through `tests/e2e_support/mock_llm_backend.py` now
 *     dies at the THINK step with a fatal error, "the plan tier did not
 *     return valid JSON for query classification" (`core/graph.py:1180`,
 *     `ThinkClassificationUnavailableError`). `think_node` always requires
 *     a structured JSON classification response since build phase 4.7's
 *     competency-question routing; the mock's `_fake_acompletion` was only
 *     ever updated for the GUARD call's JSON contract (build phase 4.8) and
 *     still answers every other call with a bare "ok" string, which fails
 *     `_parse_think_classification`'s `json.loads`.
 *   - This never reaches the cost-cap partial result
 *     `mock_llm_backend.py`'s own docstring calls its "one real code path
 *     that emits a token event", so a query landing that way, the shape
 *     `query-stream-and-stop.spec.ts`'s first test depends on, IS ITSELF
 *     BROKEN at baseline: that test currently fails on this branch with no
 *     changes from this session, `getByTestId("answer-cap")` never
 *     becoming visible. See this session's full suite run for the exact
 *     failure.
 *   - Because the run ends having produced no answer,
 *     `run_registry.py`'s `_fire_guard_refusal_callback` (F-4.10-V-02)
 *     refunds the guest's ANSWER allowance (`guest_sessions.runs_used`) on
 *     every single real run. Two real asks against one fresh guest identity
 *     measured `runs_used: 0, attempts_used: 2` on the real database row:
 *     the attempt ceiling counts correctly (it is never refunded), and the
 *     answer allowance this workflow is actually about cannot be moved off
 *     zero by any real, unscripted run today.
 *
 * WHAT WOULD AND WOULD NOT FIX THIS FOR THIS SPEC. Scripting the SSE stream
 * the way `cite-or-refuse.spec.ts` and `citation-host-allowlist.spec.ts` do
 * does NOT help here: the refund is computed SERVER-SIDE, from the real
 * backend task's own real events (`_drain_into_entry` reads them
 * internally), independently of whatever `page.route` serves to the
 * browser. Intercepting the browser's view of the stream cannot change what
 * the server already decided to charge or refund. The only fix is to the
 * mock backend's classification response (or to `think_node`'s contract),
 * neither of which is a Playwright spec change, and both are outside this
 * session's ownership (`frontend/e2e/` only, per this task's own scope).
 *
 * THIS SPEC IS THEREFORE SKIPPED rather than deleted or left to fail. Its
 * body is written for the day the regression above is fixed, so re-enabling
 * it is a one-line change once `mock_llm_backend.py` (or `think_node`)
 * speaks the same contract again, and the coverage this Tier 1 workflow
 * needs is not lost to a silently-vanished draft.
 *
 * COVERAGE STATED, per `goal-contracts.md`. Once unskipped, this would
 * exercise: the dots counting down from 5 to 0 across five real answers,
 * the sixth ask refusing with the sign-in wall (reason
 * `allowance_exhausted`), and the wall's exact, trigger-specific copy
 * (F-4.10-R-02). It would deliberately still not exercise the ATTEMPT
 * ceiling (`W-GUEST-5`, Tier 3, a separate, higher bound), session
 * migration (`W-GUEST-8`/`W-GUEST-10`), or the daily system-wide cap,
 * each with its own refusal reason and its own copy.
 */

import { expect, test, type Page } from "@playwright/test";

const QUESTIONS = [
  "Which diseases are associated with BRCA1?",
  "Which diseases are associated with TP53?",
  "Which diseases are associated with BRCA2?",
  "Which diseases are associated with EGFR?",
  "Which diseases are associated with KRAS?",
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

async function askFromHome(page: Page, question: string): Promise<void> {
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

const answerLanded = (page: Page) =>
  expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });

test.describe("the guest allowance wall", () => {
  test.skip(
    true,
    "BLOCKED: every real run through the mock backend now dies at the think " +
      "step (ThinkClassificationUnavailableError) before landing, and the " +
      "guest answer allowance is refunded on every such run, so it cannot be " +
      "exhausted by real asks until that regression is fixed. See this file's " +
      "docstring for the full account.",
  );

  test("five real answers spend the allowance, and the sixth hits an honest wall", async ({
    page,
  }) => {
    await enterApp(page);

    for (const [index, question] of QUESTIONS.entries()) {
      const n = index + 1;
      await askFromHome(page, question);
      await answerLanded(page);

      await page.getByRole("button", { name: "New search", exact: true }).first().click();

      const dots = page.getByTestId("guest-allowance");
      await expect(
        dots,
        `populate-check failed: no allowance footer after question ${n}`,
      ).toBeVisible();

      // POLLED, not a one-shot `.count()`: `App.tsx` refreshes the allowance
      // from `GET /v1/allowance` in a fire-and-forget call issued right
      // after `createRun` resolves, a separate network round trip.
      await expect(
        dots.locator('[data-dot-state="spent"]'),
        `after ${n} answers, ${n} dots should read spent`,
      ).toHaveCount(n, { timeout: 10_000 });

      if (n < QUESTIONS.length) {
        await expect(dots).toContainText(`${QUESTIONS.length - n} search`);
      }
    }

    await expect(page.getByTestId("sign-in-wall")).toHaveCount(0);

    await askFromHome(page, "Which diseases are associated with PTEN?");

    const wall = page.getByTestId("sign-in-wall");
    await expect(wall, "a sixth guest ask did not produce the sign-in wall at all").toBeVisible({
      timeout: 15_000,
    });
    await expect(wall).toContainText(
      "You have used your free searches. Sign in or create an account to keep going.",
    );

    // NEGATIVE CHECK, per F-4.10-R-02: this reason's sentence must not be
    // one of the OTHER two triggers' sentences.
    await expect(wall).not.toContainText("as many questions as a guest can");
    await expect(wall).not.toContainText("moved into an account");

    await expect(wall.getByRole("button", { name: /create account or sign in/i })).toBeVisible();
    await expect(page.getByTestId("step-Guard")).toHaveCount(0);
  });
});
