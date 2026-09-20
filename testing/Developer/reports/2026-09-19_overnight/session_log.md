# Overnight session log, 2026-09-19 into 2026-09-20

Running record of the unattended session. Written as it happened, so a stopped session leaves a usable trace rather than nothing. The morning report is the "Where we stopped" section of `testing/UI_fix_plan.md`; this file is the working detail behind it.

## Table of contents

- [State at the start](#state-at-the-start)
- [Item 1: CI green](#item-1-ci-green)
- [Item 2: 11.27 and 11.28](#item-2-1127-and-1128)
- [Item 3: broad search wiring](#item-3-broad-search-wiring)
- [Item 4: live failure rate](#item-4-live-failure-rate)
- [Item 5: documents](#item-5-documents)
- [Decisions taken](#decisions-taken)

## State at the start

Measured, not assumed.

| Thing | State at 00:10 local |
|---|---|
| `develop`, local and remote | Both at `6e4aae1`, nothing ahead, nothing behind. The handover's `ba38cc9` had already been followed by one docs commit |
| Railway develop API | `GET /health` returns `{"status":"ok","app_env":"develop"}` |
| Railway develop web | HTTP 200 at `https://search-agent-web-develop-2aeb.up.railway.app` |
| CI | Red. Run `35487809398` on `6e4aae1` failed the Python gates job with `5 failed, 4998 passed, 157 skipped, 23 deselected, 1 xfailed`. Identical failures to run `34892563076` five days earlier, so the redness is stable rather than flaky |
| Worktrees | Two: the 11.27 and 11.28 work at `agent-a8393711bb57d579b`, and a new one cut for the wiring |

## Item 1: CI green

Diagnosed from `gh run view 34892563076 --log-failed`. The handover said the cause was not yet diagnosed. It is now, and it is three independent causes, not one.

| Cause | Failing test | Root cause |
|---|---|---|
| A | `test_debugging_guide_coverage.py::test_no_repurposed_file_keeps_a_stale_row` | The docstring of `contracts/events.py` changed to "twelve-member" when UI fix 11.16 added the `step` event. Neither `docs/build/Debugging_guide.md` nor the manifest was regenerated in that commit, which is the obligation the test exists to enforce |
| B | three tests in `core/test_think_retry.py` | A poisoned process-wide SQLAlchemy engine. `data/base.py` holds `_engine` as a singleton built on first use from whatever `USER_DB_URL` said at that moment. About a dozen test files monkeypatch it to `postgresql://localhost:5432/search_agent_users`, with no user and no password. The traceback confirms it: the engine is `Engine(postgresql://localhost:5432/search_agent_users)` although CI sets a credential-bearing URL in the job environment. That URL works on a developer's machine under local trust authentication, which is exactly why this is invisible locally and red in CI |
| C | `test_phase_4_1_production_mount.py::TestProductionMount::test_the_real_shipped_app_answers_a_real_mcp_call_end_to_end` | `RuntimeError: StreamableHTTPSessionManager .run() can only be called once per instance`. The module-level MCP app's session manager cannot be restarted, and an earlier test in the same process already entered the real app's lifespan |

Cause A is fixed by the lead: the guide row now names the twelve members and `StepPayload`, and the manifest is regenerated. Causes B and C are with a worker.

The framing decision is recorded below: these are fixed as test-isolation defects, never by relaxing the gate.

## Item 2: 11.27 and 11.28

Confirmed before starting that the merge is clean: `git diff --stat e5947e0..develop -- frontend/` is empty, so no frontend file on develop has moved since the worktree's base commit. With a worker.

## Item 3: broad search wiring

With a worker in its own worktree. See item 4 for evidence that landed on this ticket mid-session.

## Item 4: live failure rate

Done and reported in `../2026-09-19_live_measure/findings.md`. Thirty live runs, five questions six times each, against the deployed develop app on `6e4aae1`.

- Reliability: 30 of 30 answered, no fatal `error` event, no transport error. With the 15 of 15 measured on 2026-09-19 that is 45 consecutive clean runs. The instrumentation that would capture an error payload is in place and had nothing to capture, so the 2026-09-14 failure is not reproducing rather than diagnosed.
- A defect found instead: finding L-01, the same question returning three different source sets across six identical runs, which is UI fix 11.21's headline requirement failing live before any of tonight's changes. Every varying source is graph-derived. Passed to the wiring worker, since determinism is its ticket.

## Item 5: documents

Last, once the outcomes of items 1 to 3 are known.

One document defect fixed early because the drift gate blocks a push on it: `2026-09-19_verification/live_check.md` had a table of contents missing its own correction section. The summary paragraph there also still asserted the claim that section corrects, so it now carries a pointer to the correction rather than being silently rewritten.

## Decisions taken

Logged here as they are taken, and copied to `DECISIONS.md` at the end.
