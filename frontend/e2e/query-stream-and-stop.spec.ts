import { randomUUID } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { BACKEND_URL } from "../playwright.config";

/**
 * T-1.2-07: the first real end-to-end suite. Drives a real Chromium
 * browser against the real Vite dev server and the real FastAPI backend
 * (`playwright.config.ts`'s `webServer` array starts both); only the
 * backend's outbound LLM call is faked, in a separate process, via
 * `tests/e2e_support/mock_llm_backend.py`. Read that module's docstring
 * before touching this file: it explains why `PER_QUERY_COST_CAP_USD` is
 * fixed at 0.02 (the one code path in this build phase, T-2.0-07's stub
 * `write_node`, that emits a real `token` event), why a query's text can
 * opt into an artificial per-call delay via a fixed marker string, and why
 * a `/__e2e__/run_status` route exists (the only way to prove a stopped
 * run's server-side task was genuinely cancelled, not just that the
 * browser stopped listening).
 *
 * `PARTIAL_RESULT_NOTE` below is copied verbatim from
 * `src/system_03_search_agent/harness/cost_control.py`'s
 * `PER_QUERY_CAP_PARTIAL_RESULT_NOTE`. It cannot be imported across the
 * Python/TypeScript boundary, so it is duplicated here; keep the two in
 * sync if that Python constant's text ever changes.
 */
const PARTIAL_RESULT_NOTE =
  "This query reached its resource limit before finishing, so the answer " +
  "below reflects a partial result gathered so far.";

// Matches `mock_llm_backend.py`'s `_SLOW_QUERY_MARKER`. Only a query whose
// text contains this exact string gets the artificial per-call delay; every
// other query in this suite stays fast.
const SLOW_QUERY_MARKER = "E2E_SLOW_STOP_TEST";

function freshEmail(): string {
  return `e2e-${randomUUID()}@example.com`;
}

const TEST_PASSWORD = "Str0ngPassw0rd!";

/**
 * Signs up a brand-new account and lands on `HomePage` with a real bearer
 * token held in `App`'s state. `AuthGate.tsx`'s own `runAuth` chains
 * signup straight into login (a successful signup carries no token of its
 * own), so one click on "Sign up" is the complete auth step; a separate
 * "Log in" click is neither required nor correct for a brand-new account,
 * per `AuthGate.tsx`'s own docstring on why login and signup are two
 * distinct, non-overlapping actions.
 */
async function signUpFreshAccount(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Email").fill(freshEmail());
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();
  // AuthGate unmounts once `App` holds a token; HomePage's query input is
  // the next real DOM this page renders, so waiting for it is also the
  // wait for auth to have actually succeeded.
  await expect(page.getByLabel("Ask a question")).toBeVisible();
}

test.describe("query stream and stop (T-1.2-07)", () => {
  test("a submitted query streams through the pipeline to a partial answer", async ({
    page,
  }) => {
    await signUpFreshAccount(page);

    await page.getByLabel("Ask a question").fill("What gene is BRCA1?");
    await page.getByRole("button", { name: "Search" }).click();

    const steps = page.locator(".pipeline-step");

    // guard, think, plan, in that fixed order (QueryPipelineStepper.tsx's
    // `deriveSteps`: no tool steps exist this build phase, `plan`'s
    // `tool_calls` stub is always empty). All three reach "done": under
    // this backend's fixed PER_QUERY_COST_CAP_USD=0.02, guard/think/plan
    // each pass their own pre-flight cap check and only Write's own check
    // trips (see mock_llm_backend.py's docstring for the arithmetic), so
    // this is real pipeline progress, not a hand-built event sequence.
    await expect(steps.nth(0)).toHaveAttribute("data-status", "done"); // guard
    await expect(steps.nth(1)).toHaveAttribute("data-status", "done"); // think
    await expect(steps.nth(2)).toHaveAttribute("data-status", "done"); // plan

    // The one real token this build phase can produce: write's own
    // per-query-cap-exceeded partial result.
    await expect(page.locator(".answer-stream")).toHaveText(PARTIAL_RESULT_NOTE);

    // `deriveStopEnabled` (StopButton.tsx) disables on any terminal event,
    // including `done`; a disabled Stop button is this run's own UI-level
    // proof that it reached a terminal state.
    await expect(page.locator(".stop-button")).toBeDisabled();

    // No fatal error, and no cap-shaped non-fatal error either (the
    // partial result above is a `token`+`done` pair, never an `error`
    // event): both banners stay absent.
    await expect(page.locator(".guardrail-banner")).toHaveCount(0);
    await expect(page.locator(".cap-message")).toHaveCount(0);
  });

  test("clicking stop mid-stream halts the run on the server, not just in the browser", async ({
    page,
    request,
  }) => {
    await signUpFreshAccount(page);

    // Not `POST /v1/query`'s own response: `<StrictMode>` (main.tsx) makes
    // React 19's dev server double-invoke `ChatPage`'s mount effect (mount,
    // cleanup, mount again), so `createRun` genuinely fires twice against
    // this real backend and two real runs are created; only the second
    // response ever reaches `setRunId` (the first's callback is gated by
    // the effect's own `cancelled` flag, set by the first mount's
    // cleanup). Racing on the first `POST /v1/query` response is a proven
    // flake here: it can capture the abandoned run's id, not the one
    // `ChatPage` actually renders. The `GET /v1/query/{run_id}/events`
    // request is the reliable signal instead, since `useAgentRun` only
    // ever opens that connection for whichever `run_id` actually won and
    // landed in React state.
    const eventsRequestPromise = page.waitForRequest(
      (req) => /\/v1\/query\/[^/]+\/events$/.test(req.url()) && req.method() === "GET",
    );

    await page
      .getByLabel("Ask a question")
      .fill(`What gene is BRCA1? ${SLOW_QUERY_MARKER}`);
    await page.getByRole("button", { name: "Search" }).click();

    const eventsRequest = await eventsRequestPromise;
    const runId = eventsRequest.url().match(/\/v1\/query\/([^/]+)\/events$/)?.[1];
    if (!runId) {
      throw new Error(`could not extract run_id from events request URL: ${eventsRequest.url()}`);
    }

    // Enabled the moment a passing `guard` event arrives (~2s in, per the
    // marker-gated delay); still well before `think`'s own delayed call
    // would return (~4s in without a stop).
    const stopButton = page.locator(".stop-button");
    await expect(stopButton).toBeEnabled();
    await stopButton.click();

    // Server-side proof, independent of the browser: `request` is
    // Playwright's own Node-side HTTP client, never routed through this
    // page's `AbortController`, so it is not itself affected by the
    // client-side stop it is verifying. Polls because `Task.cancel()`
    // schedules cancellation at the task's next await point; it is not
    // synchronous with the `stop` HTTP call returning.
    await expect
      .poll(
        async () => {
          const statusResponse = await request.get(`${BACKEND_URL}/__e2e__/run_status/${runId}`);
          const body = (await statusResponse.json()) as { task_cancelled: boolean };
          return body.task_cancelled;
        },
        { message: "server-side run task never reported cancelled", timeout: 5_000 },
      )
      .toBe(true);

    // Client-side proof: `think` (the second pipeline step) needs another
    // ~2s delayed call to reach "done", which never fires because the run
    // was stopped right after `guard`. Waiting past that point and finding
    // it still not "done" shows no further events reached this page.
    await page.waitForTimeout(3_000);
    await expect(page.locator(".pipeline-step").nth(1)).not.toHaveAttribute("data-status", "done");
  });

  test("the rendered ChatPage has no automatically detectable accessibility violations", async ({
    page,
  }) => {
    await signUpFreshAccount(page);

    await page.getByLabel("Ask a question").fill("What gene is BRCA1?");
    await page.getByRole("button", { name: "Search" }).click();

    // Scan once the run has reached a settled, fully-rendered terminal
    // state (every one of the six chat components ChatPage.tsx mounts has
    // had a chance to render its real content, not just its loading
    // state), per Technical_specification.md Section 12.10's "automated
    // axe-core check in CI as a baseline".
    await expect(page.locator(".stop-button")).toBeDisabled();

    // Scoped to WCAG 2.1 A/AA conformance rules (Technical_specification.md
    // Section 12.10, v1-scope-boundary.md's "reasonable-effort
    // accessibility" framing for the Track 1 prototype), not axe-core's
    // full, stricter "best-practice" ruleset. An unscoped run against this
    // page surfaces two real, pre-existing "best-practice"-tagged findings
    // (`landmark-one-main`, `page-has-heading-one`; both `cat.semantics`/
    // `best-practice`, neither tagged `wcag2a`/`wcag2aa`): the app has no
    // `<main>` landmark and no `<h1>`. Both are genuine and worth fixing,
    // but fixing them means editing `HomePage.tsx`/`ChatShell.tsx`, already-
    // merged component source this ticket's prompt forbids touching. Judgment
    // call, logged in DECISIONS.md; flagging the gap here rather than
    // silently loosening the assertion to make it pass.
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });
});
