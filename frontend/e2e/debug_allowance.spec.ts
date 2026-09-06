/**
 * NOT A SPEC. A throwaway diagnostic script, kept only as evidence for the
 * regression this session found while investigating W-GUEST-6 (see
 * `guest-allowance-wall.spec.ts`'s docstring for the full account).
 *
 * It queries the real backend directly (bypassing the browser entirely) and
 * proves that EVERY real run through `tests/e2e_support/mock_llm_backend.py`
 * now dies at the think step with a fatal error ("the plan tier did not
 * return valid JSON for query classification", `core/graph.py:1180`), never
 * reaching the cost-cap partial result the mock backend's own docstring
 * says is its one real code path. `core/graph.py`'s `think_node` now always
 * requires a structured JSON classification response (build phase 4.7's
 * competency-question routing); the mock's `_fake_acompletion` was never
 * updated for that contract and still answers every non-guard call with a
 * bare "ok" string.
 *
 * SIDE EFFECT MEASURED HERE: because the run ends having produced no
 * answer, `run_registry.py`'s `_fire_guard_refusal_callback` (F-4.10-V-02)
 * refunds the guest's ANSWER allowance (`runs_used`) but not the ATTEMPT
 * allowance (`attempts_used`). Two real asks against a fresh guest identity
 * left `runs_used: 0, attempts_used: 2` on the real `guest_sessions` row
 * (confirmed by a direct database read), so the five-answer allowance
 * cannot currently be exhausted by any real, unscripted run.
 *
 * This test is SKIPPED: it is a diagnostic record, not a check this suite
 * should run or gate on. THE CALLING AGENT SHOULD DELETE THIS FILE once the
 * finding above has been filed wherever this repository tracks regressions
 * (`tracker/`); it was left in place rather than removed because this
 * session's file-protection rule requires informing a human before
 * deleting, and the sandbox's own delete-block hook enforces that at the
 * tool level.
 */

import { test } from "@playwright/test";
import { BACKEND_URL } from "../playwright.config";

test.skip("diagnostic only: think-step JSON classification breaks on the mock backend", async ({
  request,
}) => {
  const mint = await request.post(`${BACKEND_URL}/auth/guest`, {
    data: { session_id: "debug-session-2" },
  });
  const mintBody = (await mint.json()) as { guest_token: string };
  const guestAuth = "Bearer " + mintBody.guest_token;

  const run = await request.post(`${BACKEND_URL}/v1/query`, {
    headers: { Authorization: guestAuth },
    data: { text: "question 0", audience_depth: "researcher", session_id: "debug-session-2" },
  });
  const runBody = (await run.json()) as { run_id: string };

  await new Promise((r) => setTimeout(r, 800));

  const events = await request.get(`${BACKEND_URL}/v1/query/${runBody.run_id}/events`, {
    headers: { Authorization: guestAuth },
  });
  // eslint-disable-next-line no-console
  console.log("EVENTS:\n" + (await events.text()));
});
