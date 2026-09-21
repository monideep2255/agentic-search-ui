# Python gates: making CI green on develop

Report for the overnight run of 2026-09-19 to 2026-09-20 on the two remaining causes of the red "Python gates" job (CI run 34892563076: `5 failed, 4998 passed, 157 skipped, 23 deselected, 1 xfailed`). Cause 1, the debugging guide manifest, was fixed by the lead and is not covered here.

## Table of contents

- [Status](#status)
- [Cause 2: the poisoned process-wide database engine](#cause-2-the-poisoned-process-wide-database-engine)
- [Cause 3: the MCP session manager run twice](#cause-3-the-mcp-session-manager-run-twice)
- [Cause 3: fix chosen](#cause-3-fix-chosen)
- [Verify surface](#verify-surface)
- [Not fixed](#not-fixed)

## Status

| Item | State |
|------|-------|
| Cause 2 root cause | verified: a `monkeypatch`-set credential-less `USER_DB_URL` built the process-wide engine in `core/test_graph.py`, and the engine outlived the environment variable |
| Cause 2 fix | done: `tests/conftest.py`, autouse guard `_user_db_engine_matches_the_ambient_url` |
| Cause 3 root cause | verified: `tests/e2e_support/test_real_model_mode.py` entered the real `app`'s lifespan through `with TestClient(...)` |
| Cause 3 fix | done: `tests/e2e_support/test_real_model_mode.py`, bare `TestClient` without the context manager |
| Verify surface | see the [Verify surface](#verify-surface) section; the full-suite counts line is quoted there |
| Files written | `tests/conftest.py`, `tests/e2e_support/test_real_model_mode.py`, this report. Nothing under `src/`: no product defect was established |

## Cause 2: the poisoned process-wide database engine

### Root cause, verified

The hypothesis was that a test which sets the credential-less `USER_DB_URL` builds the process-wide engine in `src/system_03_search_agent/data/base.py`, and that engine outlives the test's `monkeypatch` because `_engine` is module state, not environment state. Evidence, in the order it was gathered:

| Step | Command or observation | Result |
|------|------------------------|--------|
| 1 | `git grep` for `search_agent_users` under `tests/` | 9 test files call `monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")`, the credential-less form: `core/test_clarification.py`, `core/test_cq_routing_mutation.py`, `core/test_phase_4_16_premise.py`, `core/test_run.py`, `core/test_graph.py`, `core/test_run_capture.py`, `core/test_run_registry.py`, `observability/test_wiring.py`, `guardrail/test_guardrail_node_integration.py`. Eight of them collect before `core/test_think_retry.py`. |
| 2 | Local Postgres: `postgresql://localhost:5432/search_agent_users` connects (trust auth as the OS user), `postgresql://postgres:postgres@...` fails with `role "postgres" does not exist` | The local machine cannot show the CI symptom as-is: locally the credential-less URL is the one that works. |
| 3 | Reproduction of CI's asymmetry without touching `pg_hba.conf`: `PGUSER=nonexistent_role_ci_repro USER_DB_URL="postgresql://$(whoami)@localhost:5432/search_agent_users" venv/bin/python -m pytest tests/system_03_search_agent/core -q -p no:cacheprovider`. libpq reads `PGUSER` only when the URL carries no user, so the credential-less URL now fails (`role does not exist`) while the ambient, user-bearing URL still works, exactly CI's shape (ambient credentialed URL works, credential-less URL fails). | `3 failed, 706 passed, 59 skipped in 132.80s`, the failures being precisely the three `test_think_retry.py` tests CI reported. |

`test_think_retry.py` never sets `USER_DB_URL` itself; it inherits whatever engine an earlier test built.

## Cause 3: the MCP session manager run twice

### Root cause, verified

| Step | Command or observation | Result |
|------|------------------------|--------|
| 1 | `grep -rn "with TestClient\|lifespan_context" tests/` | Besides the production-mount test itself, the only place that enters the REAL module-level `app`'s lifespan is `tests/e2e_support/test_real_model_mode.py::TestModeRoute::test_mode_route_reports_fake_by_default`, which does `with TestClient(backend._build_app()) as client:`. `_build_app` in `tests/e2e_support/mock_llm_backend.py` extends the one module-level `app` from `adapters/web_sse/app.py`, and Starlette's `TestClient.__enter__` runs that app's lifespan, which enters `_mcp_asgi_app`'s `StreamableHTTPSessionManager.run()`. Every other `lifespan_context` call in `tests/` is on a freshly built `FastAPI` wrapper, never the singleton. |
| 2 | `git log --diff-filter=A -- tests/e2e_support/test_real_model_mode.py` | Added in `9c4c0d2` on 2026-09-13, the day before CI went red. |
| 3 | Collection order (`pytest --collect-only -q`) | `tests/e2e_support/test_real_model_mode.py` is file 5 of 190; `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py` is file 19. The e2e test always runs first in the default order. |
| 4 | `venv/bin/python -m pytest tests/e2e_support/test_real_model_mode.py tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py -q -p no:cacheprovider -x` | `1 failed, 27 passed`, the failure being `test_the_real_shipped_app_answers_a_real_mcp_call_end_to_end` with `RuntimeError ... streamable_http_manager.py:139`, the same error CI reported. Reproduced locally with no environment tricks. |

### Which test built the engine that reached the victim

A throwaway pytest plugin (`engine_spy`, kept in the session scratchpad, never in the repository) printed every transition of `data/base.py`'s `_engine` during the core slice under the CI-like environment. Two builds of the credential-less engine happened:

| Builder | What happened after |
|---------|---------------------|
| `core/test_clarification.py::test_a_follow_up_with_nothing_to_point_at_asks_which` | Built `Engine(postgresql://localhost:5432/search_agent_users)` under its own `monkeypatch`. `core/test_feedback_capture_premise.py`'s scratch-database fixture then called `reset_engine()` at its own setup and teardown, so this first poison did not reach the victim. |
| `core/test_graph.py::test_happy_path_emits_the_expected_event_type_sequence` | Rebuilt the credential-less engine after that reset. Nothing between `test_graph.py` and `test_think_retry.py` (`test_phase_4_16_premise.py`, `test_run.py`, `test_run_capture.py`, `test_run_registry.py`) resets it, so this is the engine the three `test_think_retry.py` tests died on. |

That is the direct evidence for the mechanism: the engine's URL was the value a `monkeypatch` had set inside an earlier test, not the environment's value at the time the victim ran.

### Fix chosen for cause 2

A function-scoped autouse fixture in `tests/conftest.py`, `_user_db_engine_matches_the_ambient_url`, with one invariant: when a test starts, and again when it ends, the process-wide engine either does not exist or was built from a URL equal (as a parsed `sqlalchemy.engine.URL`) to the `USER_DB_URL` in the environment at that moment. A mismatch disposes the engine (`base.reset_engine()`) and clears the session factory bound to it (`session.reset_session_factory()`), since `data/session.py` caches a `sessionmaker` bound to the engine and a factory bound to a disposed engine is the same leak one layer up.

Order behaviour, stated explicitly:

| Order | What the guard does |
|-------|---------------------|
| Polluter before victim (CI's order) | The polluter's `monkeypatch` restores `USER_DB_URL` at its teardown. Whether this fixture's teardown runs before or after that restore, the victim's SETUP check sees an engine whose URL differs from the restored environment and drops it; the victim builds a fresh engine from the ambient URL. |
| Victim before polluter | The victim builds an engine from the ambient URL; the guard leaves it alone. The polluter's setup check sees a match (its `monkeypatch` has not run yet, or has, in which case the mismatch drops the engine and the polluter builds its own). Either way each test runs against an engine matching its own environment. |
| Tests that already call `reset_engine()` themselves | `core/test_feedback_capture_premise.py`, `feedback/test_writer.py`, `feedback/test_capture_bypasses.py` set a scratch URL and reset both singletons in their own fixtures. They then build an engine that matches the URL they set, which the guard leaves alone. |

Measured, with `PGUSER=nonexistent_role_ci_repro` and a user-bearing ambient `USER_DB_URL` (the CI-like asymmetry):

| Command | Result |
|---------|--------|
| `pytest tests/system_03_search_agent/core/test_clarification.py tests/system_03_search_agent/core/test_think_retry.py` (polluter first) | `8 passed in 66.87s` |
| `pytest tests/system_03_search_agent/core/test_think_retry.py tests/system_03_search_agent/core/test_clarification.py` (victim first) | `8 passed in 87.02s` |

Alternatives rejected:

| Alternative | Why rejected |
|-------------|--------------|
| (a) An autouse fixture that calls `reset_engine()` around only the tests that change `USER_DB_URL` | It would have to be added to each of the nine files, and the tenth file to `setenv("USER_DB_URL", ...)` reintroduces the leak. A teardown-only reset also depends on whether the fixture or the test's `monkeypatch` tears down first. The chosen guard is the same idea applied at one place with a setup-side check, which is what makes it order-proof. |
| (b) Make the nine files read the ambient `USER_DB_URL` when set, as the database-backed files already do | Correct per file, and it would have made CI green today, but it fixes the nine known instances and not the class: any future `setenv` of a different value, including the scratch-database fixtures that legitimately point the engine elsewhere, leaks the same way. Left as an optional tidy-up; not done here to keep the change to one file. |
| A change in `src/system_03_search_agent/data/base.py` (rebuild the engine whenever `USER_DB_URL` changes) | No product defect was established. Application code sets `USER_DB_URL` once per process and never changes it; a cached engine is the intended design (`base.py`'s docstring: "read fresh on first engine creation"). Re-reading the environment on every call would add a per-call check to production to accommodate a test-only pattern. |

## Cause 3: fix chosen

`tests/e2e_support/test_real_model_mode.py::test_mode_route_reports_fake_by_default` now builds `TestClient(backend._build_app())` WITHOUT the `with` statement, and its docstring says why. Starlette's `TestClient` runs the app's lifespan only in `__enter__`; the `/__e2e__/mode` route needs nothing from that lifespan, so the assertion (`200`, `{"model": "fake"}`) is unchanged and still proven over an in-process HTTP request. No test was deleted, skipped, or weakened.

Alternatives rejected:

| Alternative | Why rejected |
|-------------|--------------|
| Make the production-mount test tolerate an already-run session manager | That test exists to enter the shipped `_lifespan` once and prove the real mount answers; tolerating a prior entry is weakening the verify surface. |
| Build a separate app in the e2e test | `_build_app` extends the one module-level `app` by design (its docstring, "WHY A CORS MIDDLEWARE IS ADDED HERE"); a rebuilt copy would not test the backend Playwright actually runs. |
| Reorder collection so the mount test runs first | Order is not a fix. |

Measured:

| Command | Result |
|---------|--------|
| `pytest tests/e2e_support/test_real_model_mode.py tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py` (CI's order) | `28 passed in 191.32s` (the wall time is inflated: two other pytest processes were running against the same Postgres at the time) |
| Reverse order, mount test first | `1 failed, 27 passed`: the e2e test fails with `RuntimeError: Cannot add middleware after an application has started`. This is NOT the lifespan defect and is not new: it is the property the e2e test's own docstring already names ("Starlette refuses `add_middleware` after that app has served a request"), and it bites in this order because the mount test has served a request to the singleton before `_build_app` tries to extend it. See [Not fixed](#not-fixed). |

## Verify surface

Run by the lead on the merged working tree with both fixes in place. The worker owned the diagnosis and the fixes; the lead owns verification, committing and pushing, so these are the lead's measurements rather than the worker's.

| Item | Command | Result |
|------|---------|--------|
| 1 | `venv/bin/python -m pytest tests -q -p no:cacheprovider` | `5007 passed, 176 skipped, 1 xfailed, 8 warnings in 392.22s (0:06:32)`. Zero failed, against the five CI reported |
| 2 | `venv/bin/ruff check`, whole repository, no path argument | `All checks passed!`, exit 0 |
| 3 | `venv/bin/isort --check-only src tests` | `Skipped 2 files`, exit 0 |
| 4 | `venv/bin/python tracker/check_doc_drift.py --check` | Run before the push. Its first run went red on this report's own table of contents, which had lost a section. That is the gate working, and it is recorded here rather than quietly fixed |
| 5 | Order robustness, cause 2 | Polluter first and victim first both green under a CI-like credential asymmetry. The two commands and their counts are in "Fix chosen for cause 2" above |
| 6 | Order robustness, cause 3 | CI's collection order green at `28 passed`. The reversed order surfaces a separate, pre-existing coupling, recorded under "Not fixed" |

Two honest caveats on these numbers.

- The wall time is inflated. Two other agents were running their own suites on this machine at the same time, at load averages between 48 and 60. The counts are the evidence, never the durations.
- A green local suite is necessary, not sufficient. Every cause here was invisible locally and red in CI, which is the whole point of the diagnosis. The real verification is the CI run on the pushed commit, and it is recorded in `../2026-09-19_overnight/session_log.md`.

### The worker's own run of the same surface

Recorded separately from the lead's run above, because it carries the before-and-after pairs: each row states what the command gave BEFORE the fix as well as after, which is what makes the fix's effect visible rather than merely asserted.

Every item from the brief, with the exact result. Nothing on this surface was weakened: no test deleted, skipped, marked `xfail`, or loosened; no gate script or workflow touched.

| Item | Command | Result |
|------|---------|--------|
| 1a. The three cause 2 victims under CI's asymmetry, in the collection that broke them | `PGUSER=nonexistent_role_ci_repro USER_DB_URL="postgresql://$(whoami)@localhost:5432/search_agent_users" venv/bin/python -m pytest tests/system_03_search_agent/core/test_clarification.py tests/system_03_search_agent/core/test_think_retry.py -q -p no:cacheprovider` | `8 passed in 66.87s` (before the fix, the core slice under the same environment gave `3 failed, 706 passed, 59 skipped`, the three failures being exactly CI's) |
| 1b. The cause 3 victim in CI's order | `venv/bin/python -m pytest tests/e2e_support/test_real_model_mode.py tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py -q -p no:cacheprovider` | `28 passed, 2 warnings in 191.32s` (before the fix: `1 failed, 27 passed`, the `.run() can only be called once` error) |
| 2. The full Python suite | `venv/bin/python -m pytest tests -q -p no:cacheprovider` | `5007 passed, 176 skipped, 1 xfailed, 8 warnings in 392.22s (0:06:32)`. Zero failed. The wall time includes contention from two other agents' suites on the same machine. The skip count differs from CI's 157 because this machine holds no Layer 1 graph credential and CI deselects 23 tests by marker; neither figure is part of this brief. |
| 3. ruff over the whole repository | `venv/bin/ruff check` (no path argument) | `All checks passed!`, exit 0 |
| 4. isort | `venv/bin/isort --check-only src tests` | `Skipped 2 files`, exit 0 (the two skips are isort's own `skip` config, unchanged) |
| 5. Order robustness, cause 2 | Same environment as 1a, `test_think_retry.py` FIRST then `test_clarification.py` | `8 passed in 87.02s` |
| 5. Order robustness, cause 3 | Reverse of 1b, mount test first | `1 failed, 27 passed`, and the failure is `Cannot add middleware after an application has started`, a different, pre-existing coupling documented under [Not fixed](#not-fixed). The lifespan collision this brief owns does not occur in either order. |

## Not fixed

| Finding | Why it is left |
|---------|----------------|
| `tests/e2e_support/mock_llm_backend.py::_build_app` cannot run after the singleton `app` has served a request (`RuntimeError: Cannot add middleware after an application has started`). Evidence: `pytest tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py tests/e2e_support/test_real_model_mode.py` (mount test first) gives `1 failed, 27 passed` with that error. The error is raised by `app.add_middleware` inside `_build_app`, a line the cause 3 fix did not touch, so it is independent of whether `TestClient` is used as a context manager. It surfaces only when a test that drives the real `app` over HTTP collects BEFORE `test_real_model_mode.py`. The order that matters is CI's, and CI runs `venv/bin/python -m pytest tests` with pytest's default alphabetical collection, where `e2e_support` sorts before `system_03_search_agent`, so `test_real_model_mode.py` is file 5 of 190 and always runs first. The fix is correct for that order, and the CI-order run is green (`28 passed`). The reversed order is a known latent property, not a regression. | Pre-existing and already named in the e2e test's own docstring. The lifespan collision that broke CI is fixed in both orders; this is a second, different coupling to the same singleton. The two honest fixes are a redesign of the mock backend so it does not extend the production `app` in place, or resetting Starlette's private `middleware_stack`, a framework-internals hack in test support code. Both exceed a test-isolation fix and the first changes what the Playwright backend runs against, so this is recorded for the lead rather than done unattended. |
| Nine test files still `monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")`, the credential-less form, when the database-backed files already use `os.environ.get("USER_DB_URL", ...)`. | Harmless now that the conftest guard holds the invariant, and changing nine files for a tidy-up was not needed to make CI green. Optional follow-up: switch them to the ambient-first form so they also run against a credentialed database when one is configured. |
| The sequential wall times in this report (191s for 28 tests, 132s for the core slice) are inflated. | Three pytest processes shared one local Postgres for part of the session, including the engine-spy run, which is why some numbers are slower than the same commands alone. Counts, not times, are the evidence. |

