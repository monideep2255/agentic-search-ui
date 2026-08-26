# Build phase 4.14: continuous integration

Branch: `phase/4.14-ci-gates`
Depends on: 4.12, merged 2026-08-24 as PR #61
Opened: 2026-08-26
Status: IN PROGRESS

Pulled forward from build phase 6.1 by product-owner decision, 2026-08-24, the fourth such exception after 4.8, 4.10 and 4.11/4.12. Section 25 does not contain it. Section 24 specifies its ten gates in full and build phase 6.1 owned them; build phase 4.12 changed the urgency by wiring CD to `develop`, so an unguarded merge now reaches a live public URL.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [Every gate measured before any YAML was written](#every-gate-measured-before-any-yaml-was-written)
- [The three findings the measurement produced](#the-three-findings-the-measurement-produced)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [Findings](#findings)
- [History](#history)

## What this phase is for

Nothing runs the test suite on a pull request. A merge to `develop` auto-deploys to a live public URL, so the only thing between a bad commit and the demo is a person choosing to run `pytest`.

This repository has already paid for that gap once. Build phase 4.8 recorded a broken production build sitting unnoticed on `develop`, and a browser suite that had been broken for five phases, both for the same reason: nothing runs the suites except a person choosing to.

The deliverable is Section 24's ten merge-blocking gates, in Section 24's order, running on every pull request.

## Every gate measured before any YAML was written

Measured on `phase/4.14-ci-gates` at its branch point, `b7716dd`, on 2026-08-26. This table is the input to the design, not a summary of it: four of the ten gates did not pass, and the shape of the workflow follows from which four.

| Gate | Command measured | Result at branch point |
|------|------------------|------------------------|
| 1. Python compiles | `python -m compileall -q src services tests` | PASS, exit 0 |
| 2. Import order | `isort --check-only --profile black --line-length 100 src tests services` | FAIL, 50 files. isort was never configured in this repository and is not a declared dependency |
| 3. Lint | `ruff check src services` | PASS. `ruff check tests` FAILS with 5 errors, so the gate passes only because nobody had pointed it at `tests/` |
| 4. Unit suite | `pytest -m "not integration" -q` | PASS, 3947 passed, 136 skipped, 23 deselected, 1 xfailed, ZERO FAILED, 113s |
| 5. Integration suite | `pytest -m integration` | 2 marked files, both network-gated |
| 6. Python dependency audit | `pip-audit` | FAIL, 2 findings. `pip-audit -r requirements.txt` PASSES. See finding F-4.14-01 |
| 7. Frontend dependency audit | `npm audit --audit-level=high` | PASS, 0 vulnerabilities |
| 8. Frontend build and test | `npm run build`, `npm test` | PASS, built in 253ms; 17 files, 216 tests passed |
| 9. Required-path tests | `test_cite_or_refuse_compliance`, `test_zero_retrieval_refusal` | Neither name exists as a function. Both exist as a FILE. See finding F-4.14-02 |
| 10. Accessibility | WCAG 2.1 AA | `frontend/e2e/accessibility.spec.ts` exists and drives axe against a real browser. Needs both servers and a real PostgreSQL |

## The three findings the measurement produced

Each of these changes the design rather than decorating it. All three are recorded in the Findings table below.

F-4.14-01, gate 6 was a false alarm from the measuring environment. `pip-audit` with no argument audits the ambient virtualenv, not the project. Its two findings were `cryptography 49.0.0`, which `pip show` reports as `Required-by:` nothing at all, and `pip 26.1.2`, the installer itself. `pip-audit -r requirements.txt`, which audits what this project actually declares, returns "No known vulnerabilities found". Scoping the gate to the requirements file is the fix; changing a dependency to satisfy an instrument that was pointed at the wrong thing would have been the inverse-reward-hacking failure `goal-contracts` names.

F-4.14-02, gate 9's two test names do not exist. Section 24 names `test_cite_or_refuse_compliance` and `test_zero_retrieval_refusal`. Neither is a function anywhere in `tests/`. Both are section headings inside `tests/system_03_search_agent/synthesis/test_required_paths.py`, whose own docstring quotes Section 23's instruction that they never get deleted, narrowed or weakened. The gate points at the file.

F-4.14-03, and this is the one that would have shipped a green vacuous gate. Every database-backed test in this repository SKIPS, rather than fails, when `USER_DB_URL` is unreachable: `tests/system_03_search_agent/auth/test_router.py` probes the connection and calls `pytest.skip("set USER_DB_URL and ensure the server is running to run this suite")`. On this machine PostgreSQL is running, so those tests RAN inside the 3947. A GitHub Actions runner has no PostgreSQL, so the identical command would have reported the identical green while silently skipping every one of them. A gate that cannot tell "passed" from "did not run" is not a gate.

## Goal contract

Done when: a pull request against `develop` runs all ten of Section 24's gates, in Section 24's order; each gate is a separately-named, separately-failing step; every gate has been mutation-proven to go red when the thing it exists to catch is broken; and the unit-suite gate fails rather than skips if its database is absent.

Verify: `.github/workflows/ci.yml` runs green on this phase's own pull request, which is the first pull request in this repository's history that CI has ever seen; plus `tests/ci/test_ci_workflow_premise.py`, an offline premise gate asserting the workflow's content against the ten-row Section 24 table and against the real commands in `pyproject.toml` and `frontend/package.json`; plus a recorded mutation run per gate.

Output: `.github/workflows/ci.yml`, `.github/pull_request_template.md` (rewritten), `pyproject.toml` (isort configuration and dev dependency), the premise gate, and this file.

Constraints: no gate is weakened to make it pass. Where a gate fails today, the code is fixed, not the gate. Section 24's gate list and order are locked and are followed exactly. No secret is required for any gate to run, so a fork's pull request gets the same signal.

Blocked-stop: if a gate cannot run on a GitHub-hosted runner without a credential this repository cannot put in CI, it is recorded as such with the reason rather than quietly dropped or stubbed green.

## Tickets

| ID | Title | Acceptance criteria | Status | Owner | Evidence |
|----|-------|---------------------|--------|-------|----------|
| T-4.14-01 | The CI workflow, Section 24's ten gates in Section 24's order | `.github/workflows/ci.yml` triggers on `pull_request` and on `push` to `develop`. Every gate is its own named step so a failure names itself. Gate order matches the Section 24 table exactly | todo | | |
| T-4.14-02 | Gate 2, make `isort --check` real | isort configured in `pyproject.toml` and declared as a dev dependency. Its configuration agrees with ruff's `I` rules, proven by both running clean on the same tree rather than asserted. The repository is sorted once as a formatting-only change | todo | | |
| T-4.14-03 | Gate 3, point `ruff check` at the whole repository | The 5 existing errors under `tests/` are fixed at the category level. `ruff check` with no path argument exits 0 | todo | | |
| T-4.14-04 | Gate 6, scope `pip-audit` to what the project declares | The gate runs `pip-audit -r requirements.txt`. F-4.14-01's reasoning is recorded in the workflow itself, so the next reader does not "fix" it back | todo | | |
| T-4.14-05 | Gates 4 and 5, a database the suite can actually reach | The unit-suite job runs a PostgreSQL service and creates the schema. A no-silent-skip assertion fails the job if any test skips for an unreachable database. Gate 5 is a separate network-gated job | todo | | |
| T-4.14-06 | Gate 9, the required paths as their own failing step | `tests/system_03_search_agent/synthesis/test_required_paths.py` runs as its own step after gate 4, so a required-path failure is legible as itself and not as one line inside 3947 | todo | | |
| T-4.14-07 | Gate 10, accessibility on UI-touching pull requests only | A path-filtered job runs `frontend/e2e/accessibility.spec.ts` when `frontend/**` changes. Skipped cleanly, and visibly, when it does not | todo | | |
| T-4.14-08 | Replace the stale pull request template | `.github/pull_request_template.md`'s QA gate list becomes Section 24's ten gates. Closes Section 24's own open-flags row, which has been open since Phase 5 | todo | | |
| T-4.14-09 | The premise gate, and mutation proof for every gate | `tests/ci/test_ci_workflow_premise.py`, offline, asserting the workflow against Section 24's table and against the real commands the repository actually has. Every arm carries a populate-check. Each gate is mutation-proven to go red | todo | | |
| T-4.14-10 | Reproducibility: pinned versions, caching, concurrency | Tool versions pinned so CI and a developer's machine agree. Dependency caching. `concurrency` cancels superseded runs on the same branch | todo | | |

## Coverage: what this phase does not cover

Stated here so a gap is arguable rather than discovered, per `goal-contracts`.

- Covered: the ten Section 24 gates on a pull request, each separately failing, each mutation-proven.
- Not covered: CD. Railway's GitHub integration already watches `develop` and is unchanged by this phase. Making a deploy wait for CI is build phase 4.15's two-environment release flow, not this one.
- Not covered: the live premise gates. All 136 skips in the measured baseline are `RUN_PREMISE_GATE=1` arms that need a real model key, real money, and live network reach to NCBI. They stay opt-in and out of CI deliberately; a gate that spends real budget on every pull request is a gate someone switches off.
- Not covered: the standing `query-stream-and-stop.spec.ts` `answer-cap` failure, proven pre-existing at build phase 4.16's branch point and still unowned. The Playwright suite as a whole is therefore NOT a merge-blocking gate in this phase; only `accessibility.spec.ts` is.
- Not covered: F-4.16-02, that the browser suite cannot reach a real tool dispatch. The board assigns it to this phase. It is a property of the e2e mock backend rather than of CI, and folding it in here would widen this phase past its stated done-when.

## Findings

| ID | Severity | Raised by | Finding | State | Resolution |
|----|----------|-----------|---------|-------|------------|
| F-4.14-01 | medium | lead, at phase open | `pip-audit` with no argument audits the ambient virtualenv rather than the project, and reported 2 findings for packages this project does not declare. `pip-audit -r requirements.txt` is clean | confirmed | T-4.14-04 scopes the gate to the requirements file. No dependency changed |
| F-4.14-02 | low | lead, at phase open | Section 24 gate 9 names two tests by exact name; neither exists as a function. Both exist as sections of `tests/system_03_search_agent/synthesis/test_required_paths.py` | confirmed | T-4.14-06 points the gate at the file |
| F-4.14-03 | high | lead, at phase open | Every database-backed test SKIPS rather than fails when `USER_DB_URL` is unreachable. On a runner with no PostgreSQL the unit gate would have reported green while silently skipping all of them | confirmed | T-4.14-05 runs a PostgreSQL service AND asserts no test skipped for a missing database |

## History

- 2026-08-26: phase opened on `phase/4.14-ci-gates`. Every one of Section 24's ten gates measured at the branch point BEFORE any YAML was written, on the `attack-the-constraint` principle that the input is cheaper to inspect than the output is to debug. Four gates did not pass. Three findings filed, one of them (F-4.14-03) a vacuous-gate risk that would have shipped a green CI run skipping every database-backed test.
