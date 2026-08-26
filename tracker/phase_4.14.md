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
| T-4.14-01 | The CI workflow, Section 24's ten gates in Section 24's order | `.github/workflows/ci.yml` triggers on `pull_request` and on `push` to `develop`. Every gate is its own named step so a failure names itself. Gate order matches the Section 24 table exactly | in-review | lead | Four jobs, ten gates: `python-gates` carries 1, 2, 3, 4, 6, 9; `integration` carries 5; `frontend-gates` carries 7, 8; `accessibility` carries 10. Gate order verified in-job by `test_p2`, and the gate LIST is read out of Section 24 at test time by `test_p1`/`test_p1b` rather than copied |
| T-4.14-02 | Gate 2, make `isort --check` real | isort configured in `pyproject.toml` and declared as a dev dependency. Its configuration agrees with ruff's `I` rules, proven by both running clean on the same tree rather than asserted | in-review | lead | `ruff check` → `All checks passed!` and `isort --check-only` → clean, on the same tree, with `I001` ENABLED. Reached by `known-third-party = ["alembic"]` (23 disagreements → 2) plus a documented 2-file isort skip where ruff still checks. See the correction below |
| T-4.14-03 | Gate 3, point `ruff check` at the whole repository | The 5 existing errors under `tests/` are fixed at the category level. `ruff check` with no path argument exits 0 | in-review | lead | 35 errors fixed (5 in `tests/`, 30 in harness scripts and migrations). `ruff check`, no path argument, no exclusions: `All checks passed!`. Every touched gate script re-verified by its own `--self-test` and `--mutation-test`. Re-narrowing to `ruff check src` is now caught by `test_p17` |
| T-4.14-04 | Gate 6, scope `pip-audit` to what the project declares | The gate runs `pip-audit -r requirements.txt`. F-4.14-01's reasoning is recorded in the workflow itself, so the next reader does not "fix" it back | in-review | lead | `pip-audit -r requirements.txt` → "No known vulnerabilities found". Reasoning inline at the step; regression caught by `test_p3` and a permanent mutation arm |
| T-4.14-05 | Gates 4 and 5, a database the suite can actually reach | The unit-suite job runs a PostgreSQL service and creates the schema. A no-silent-skip assertion fails the job if any test skips for an unreachable database. Gate 5 is a separate network-gated job | in-review | lead | Postgres 16 service, `alembic upgrade head`, and `assert_no_db_skips.py`. Proven end to end: the full suite against a genuinely fresh CI-shaped database (created empty, migrated) passes. The guard catches 51 of 51 unsanctioned skips against a dead database where the first version caught 10, and stays quiet across all 137 legitimate ones |
| T-4.14-06 | Gate 9, the required paths as their own failing step | `tests/system_03_search_agent/synthesis/test_required_paths.py` runs as its own step after gate 4, so a required-path failure is legible as itself and not as one line inside 3947 | in-review | lead | Own step plus `assert_required_paths_ran.py`, which anchors on module IDENTITY and on the source still referencing `REFUSAL_TEXT` and `ground_claim`. The adversary's attack (20 unrelated tests named for a blue border) is rejected |
| T-4.14-07 | Gate 10, accessibility on UI-touching pull requests only | A path-filtered job runs `frontend/e2e/accessibility.spec.ts` when `frontend/**` changes. Skipped cleanly, and visibly, when it does not | in-review | lead | Path filter FAILS CLOSED after F-4.14-A-07: missing commits, a failed `git diff`, or an absent base SHA all RUN the gate and raise a `::warning`, rather than skipping it and printing a false summary line. Guarded by `test_p20` |
| T-4.14-08 | Replace the stale pull request template | `.github/pull_request_template.md`'s QA gate list becomes Section 24's ten gates. Closes the stale-template row in that section's own known-gaps table, outstanding since Phase 5 | in-review | lead | Rewritten to the ten gates plus the human gates CI deliberately does not run. Closes the known-gaps row outstanding since Phase 5. Note the phrasing here avoids putting a bare "24" next to the words "open flags", which `check_doc_drift.py` reads as a claim about the board's flag count |
| T-4.14-09 | The premise gate, and mutation proof for every gate | `tests/ci/test_ci_workflow_premise.py`, offline, asserting the workflow against Section 24's table and against the real commands the repository actually has. Every arm carries a populate-check. Each gate is mutation-proven to go red | in-review | lead | 31 premise arms, 35 mutation arms, 29 assertion-script tests: 95 in `tests/ci/`. REWRITTEN mid-phase after both reviewers broke the first version; all 16 of their strongest mutations are now permanent arms and all 16 are caught with a clean control |
| T-4.14-10 | Reproducibility: pinned versions, caching, concurrency | Tool versions pinned so CI and a developer's machine agree. Dependency caching. `concurrency` cancels superseded runs on the same branch | in-review | lead | `ruff==0.16.0` exact-pinned, since no explicit `select` means the enabled rule set IS the version. pip and npm caching. `concurrency` cancels superseded pull-request runs only, never a run on `develop`. Pin enforced by `test_p12`, which parses TOML rather than raw text |
| T-4.14-11 | Tests for the three assertion scripts | Each script is tested in BOTH directions: red on the failure it exists to catch, quiet on the healthy reports this repository really produces, and failing closed on a missing, empty, truncated or entity-bearing report | in-review | lead | `tests/ci/test_assert_scripts.py`, 29 tests. Added after F-4.14-A-08: these three scripts decide whether gates 4, 5 and 9 mean anything and shipped with no test at all, which is the direct cause of four of the adversary's findings |

## Coverage: what this phase does not cover

Stated here so a gap is arguable rather than discovered, per `goal-contracts`.

- Covered: the ten Section 24 gates on a pull request, each separately failing, each mutation-proven.
- NOT covered, and this is the honest headline: the gates are ADVISORY, not merge-blocking. Branch protection cannot be configured on this repository today (F-4.14-A-04). A red run puts a red mark next to a Merge button that still works. Escalated to the product owner and unresolved.
- NOT covered: whether the workflow succeeds on a GitHub runner. Nothing offline can prove it, and this phase's own pull request is the first this repository has ever run CI on. Every gate's command was measured locally; the orchestration around them has not been executed.
- Not covered: CD. Railway's GitHub integration already watches `develop` and is unchanged by this phase. Making a deploy wait for CI is build phase 4.15's two-environment release flow, not this one.
- Not covered: the live premise gates. All 136 skips in the measured baseline are `RUN_PREMISE_GATE=1` arms that need a real model key, real money, and live network reach to NCBI. They stay opt-in and out of CI deliberately; a gate that spends real budget on every pull request is a gate someone switches off.
- Not covered: the standing `query-stream-and-stop.spec.ts` `answer-cap` failure, proven pre-existing at build phase 4.16's branch point and still unowned. The Playwright suite as a whole is therefore NOT a merge-blocking gate in this phase; only `accessibility.spec.ts` is.
- Not covered: F-4.16-02, that the browser suite cannot reach a real tool dispatch. The board assigns it to this phase. It is a property of the e2e mock backend rather than of CI, and folding it in here would widen this phase past its stated done-when.

## Findings

| ID | Severity | Raised by | Finding | State | Resolution |
|----|----------|-----------|---------|-------|------------|
| F-4.14-01 | medium | lead, at phase open | `pip-audit` with no argument audits the ambient virtualenv rather than the project, and reported 2 findings for packages this project does not declare. `pip-audit -r requirements.txt` is clean | confirmed | T-4.14-04 scopes the gate to the requirements file. No dependency changed |
| F-4.14-02 | low | lead, at phase open | Section 24 gate 9 names two tests by exact name; neither exists as a function. Both exist as sections of `tests/system_03_search_agent/synthesis/test_required_paths.py` | confirmed | T-4.14-06 points the gate at the file |
| F-4.14-03 | high | lead, at phase open | Every database-backed test SKIPS rather than fails when `USER_DB_URL` is unreachable. On a runner with no PostgreSQL the unit gate would have reported green while silently skipping all of them | confirmed, and PARTLY OVERSTATED, see the correction below | T-4.14-05 runs a PostgreSQL service, migrates it, AND asserts no unsanctioned skip occurred |

### Review round 1: what the judge and the adversary found

Both ran against commit `4ea0778`, from separate briefs and separate contexts. The judge returned FAIL. The adversary answered its central question, "can this CI report a confident green while verifying nothing", with YES and four ways.

They converged independently on the same worst defect, which is the strongest signal in the round: the premise gate verified what the workflow SAID rather than what it DID.

| ID | Severity | Raised by | Finding | State | Resolution |
|----|----------|-----------|---------|-------|------------|
| F-4.14-A-01 | critical | adversary | The phase's own headline fix did not work. `test_phase_4_10_premise.py` skips with "user database unreachable at ...", matching none of the guard's six phrasings. Against a dead database, 36 tests vanished and the guard printed "none of them for a database reason", exit 0 | closed | `assert_no_db_skips.py` rewritten as an ALLOWLIST: every skip must match a sanctioned opt-in, anything else fails. Catches 51 of 51 where the first version caught 10 |
| F-4.14-A-02 | critical | adversary | That marker list was the enumerate-the-instances shape its own docstring disclaimed. Six of six plausible phrasings evaded it | closed | Same rewrite. Deny-by-default cannot be evaded by phrasing. Eight phrasings, including all six, are now permanent tests |
| F-4.14-J-01 | critical | judge | The import-order decision was a gate turned off with a story attached, and the "irreconcilable" premise did not survive measurement | closed | `I001` RESTORED. `known-third-party = ["alembic"]` takes 23 disagreements to 2; the last 2 are an isort skip where ruff still checks. Correction logged in `DECISIONS.md` |
| F-4.14-J-02 | critical | judge | 16 independent mutations passed all 49 gate tests, with a clean control: `continue-on-error`, `\|\| true`, `if: false`, re-scoping gate 3 to `ruff check src`, relaxing gate 7 to `critical`, stripping `--check-only`, hoisting a secret to workflow-level `env` | closed | Premise gate rewritten around `command_text`, which strips shell comments. New arms assert each gate's real command and flags, and reject every neutralising construct at step and job level. All 16 are permanent mutation arms |
| F-4.14-A-05 | high | adversary | Every gate body replaced by `true`, with the command kept in a comment, left 15 of 16 arms green | closed | Same rewrite. This is the build phase 4.16 defect exactly, a fixture matching values inside the comment documenting them |
| F-4.14-A-03 | critical | adversary | Gate 5 with a credential present but unreachable: 23 skipped, 0 passed, exit 0, plain green check. Worse, it could NEVER run, because the workflow deliberately never set `RUN_PREMISE_GATE` and `conftest.py` blocks outbound HTTP without it. Adding the secret would have switched the honest NOT RUN warning OFF | closed | Gate 5 now sets `RUN_PREMISE_GATE=1` and pipes its report through the new `assert_gate_ran.py`, so a run that executed nothing fails and annotates instead of passing |
| F-4.14-A-06 | high | adversary | Gate 9's assertion was satisfied by two `assert True` tests named `test_the_citation_widget_renders_a_blue_border` and `test_the_settings_page_refuses_to_scroll_horizontally` | closed | Anchored on module IDENTITY plus a source check for `REFUSAL_TEXT` and `ground_claim`, not on test names. A name is not evidence of what a test does |
| F-4.14-A-07 | high | adversary | Gate 10's path filter failed OPEN. Any `git diff` error inside the `if` condition skipped the WCAG gate, exited 0, and printed "No file under frontend/ changed" on a pull request that changed frontend files | closed | Filter fails CLOSED: missing commits, a failed diff, or an absent base SHA all run the gate and raise a `::warning` |
| F-4.14-A-08 | high | adversary | Neither assertion script had a single test, and they are the only new executable logic in the phase | closed | `tests/ci/test_assert_scripts.py`, 29 tests over all three scripts, both directions each |
| F-4.14-J-04 | major | judge | P5's populate-checks were correlates: a `redis:7` image passed, because the `POSTGRES_*` env keys satisfied the substring, and so did `USER_DB_URL: ""` | closed | P5 now checks the IMAGE and requires a non-empty `postgresql://` DSN. Both are permanent mutation arms |
| F-4.14-A-10 | medium | adversary | P12 and P13 matched raw text, so a commented-out pin satisfied them | closed | Both parse TOML via `tomllib`. A commented-out pin is a permanent mutation arm |
| F-4.14-A-11 | medium | adversary | `assert_no_db_skips.py` had no populate-check; a zero-testcase report exited 0 saying `ok` | closed | Minimum-testcase floor, tested in both directions |
| F-4.14-A-12 | low | adversary | M20 claimed to prove the populate-check works but verified a correlate, never invoking the fixture | closed | M20 now drives the real fixture against a real reworded file |
| F-4.14-A-13 | low | adversary | Gate 1 is named "compiles and imports cleanly" and never imported anything | closed | Gate 1 now imports the web, core and CLI entry points after compiling |
| F-4.14-J-05 | major | judge | The board was committed at phase-open state: ten tickets `todo`, no evidence, and the contract's "recorded mutation run per gate" did not exist | closed | Tickets carry evidence; this table and the mutation record below exist |
| F-4.14-J-06 | major | judge | `check_doc_drift.py --check` was red on the commit: 9 stale facts | closed | Synced at phase checkpoint |
| F-4.14-A-04 | critical | adversary | NOTHING makes any of these gates merge-blocking. Branch protection needs a paid plan or a public repository; `gh api .../branches/develop/protection` returns 403 "Upgrade to GitHub Pro". The done-when as written is not achievable on this repository today | OPEN, ESCALATED to the product owner | Not fixable in code. See "The one finding this phase cannot close" below |
| F-4.14-03-CORRECTION | major | lead, during the fix round | F-4.14-03 as originally written was OVERSTATED. It claimed a runner without PostgreSQL would print "an identical, confident green". That was measured on ONE FILE and never run against the suite. Run, it is false: the full suite against a dead database returns 56 failed, 25 errors, and gate 4 goes RED | closed | The real defect survives in a narrower and still-serious form: 51 tests skip SILENTLY, and they are three ENTIRE premise gates (build phases 4.1, 4.2 and 4.10) vanishing from the run while unrelated tests fail loudly. Recorded in `LEARNINGS.md` rather than quietly reworded |

### What the first CI run found, which is the point of the whole phase

CI ran for the first time in this repository's history on pull request #68, and it failed. Two of four jobs went red on one root cause, and it is a real defect in shipped code rather than a defect in the workflow:

```text
error: package directory 'system_03_search_agent' does not exist
ERROR: Failed to build ... when getting requirements to build editable
```

| ID | Severity | Raised by | Finding | State | Resolution |
|----|----------|-----------|---------|-------|------------|
| F-4.14-CI-01 | major | the first CI run | `pip install -e .` was broken and had been for the life of the project. setuptools auto-detects a `src/` layout only when `packages` is NOT set explicitly; `pyproject.toml` sets it, which disables the detection, so setuptools looked for the package at the repository root and found nothing | closed | `package-dir = { "" = "src" }`. Verified in a throwaway virtualenv: the package imports from outside the repository and both console scripts appear on PATH |
| F-4.14-CI-02 | major | the second CI run | The job's `env:` block was missing most of what the suite needs. `PER_QUERY_COST_CAP_USD` and its siblings RAISE when unset rather than defaulting, deliberately, so a missing cap can never read as "no limit", and every such gap became a test error: 55 failed, 25 errors | closed | The env block derived by DIFFING `env.example` against what the job set, rather than adding one variable per red run. Verified by reproducing CI's environment locally |

| F-4.14-CI-03 | major | the third CI run | `test_p11_goes_red_when_the_promotion_write_loses_its_lock`, build phase 4.7's mutation harness, FAILED on the runner while passing on this machine. Its mutation replaces a locked write with an atomic-but-unlocked one and expects the graded arm to notice a lost entry. The arm starts both threads on a barrier, which makes them START together but does not make them INTERLEAVE: `os.replace` is fast enough that one thread can finish its whole read-modify-write before the other reads, both entries survive, and the harness reports a healthy arm as VACUOUS | closed | A second barrier between the READ and the WRITE, so both threads are guaranteed to have read the same original document before either writes. The later write then necessarily drops the earlier entry, on any hardware. Verified 5 runs of 5, and the whole 43-case file still passes |

| F-4.14-CI-04 | major | the skip guard, on CI's fourth run | 25 tests skipped on a runner where PostgreSQL was healthy and every other database-backed test passed against it. `tests/system_03_search_agent/data/test_models.py` and `tests/system_03_search_agent/harness/test_cost_control.py` HARDCODE their DSN instead of reading `USER_DB_URL`, unlike the ten sibling files that read it. So on any host needing a different DSN they cannot connect, and they skip rather than fail | closed | Both read `os.environ.get("USER_DB_URL", ...)` now. Verified: 102 tests that were skipping now execute |

F-4.14-CI-04 is the phase justifying itself. Gate 4 reported `4019 passed, 161 skipped, 0 failed`, which is a clean green by any ordinary reading, and 25 of those skips were tests that could never have run in CI at all, silently, forever. Nothing but the skip guard distinguishes that from a healthy run, and the guard is the piece this phase added after F-4.14-A-01 showed the first version of it did not work. It also validates the ALLOWLIST design specifically: the phrasing here, "search_agent_users PostgreSQL database is not reachable", is a seventh wording that the original deny-list of six phrasings would have let through.

F-4.14-CI-03 is the same class as build phase 4.11's non-deterministic preservation gate, arriving from the opposite direction. There the gate reported findings that moved between runs; here a gate reports a healthy arm as vacuous depending on core count and scheduling. Both are a gate whose answer moves, and a moving answer makes a real finding indistinguishable from noise. It is worth noting what found it: not a reader, not a review round, but a machine with different hardware running the same test, which is a capability this repository did not have until this phase.

The root cause of F-4.14-CI-02 is worth separating from its fix, because it invalidates something this file claimed earlier.

A developer's shell loads `.env`, which on this machine carries about thirty variables. Every "verified locally" figure in this phase, including "4044 passed, zero failed", was therefore measured in a materially different environment from the one CI provides, and the phase had no way to notice: a suite that passes because of ambient configuration looks exactly like a suite that passes because the code is right.

The fix was proven by removing the difference rather than by reasoning about it. `.env` was moved aside, the job's `env:` block was exported verbatim, and the suite was run in a scrubbed environment (`env -i`):

```text
4044 passed, 136 skipped, 23 deselected, 1 xfailed in 93.21s
```

One deliberate substitution, stated rather than hidden: `USER_DB_URL` points at the local database, because the CI DSN carries a `postgres:postgres` credential this machine's PostgreSQL does not accept. The first attempt at this reproduction did NOT make that substitution, returned 55 failed, and was failing for local authentication reasons rather than for the reason under test, which would have been an easy and wrong thing to report as a confirmation.

Why nothing had ever noticed. Three separate paths reach this code and not one of them installs it: pytest resolves the package through `pythonpath = ["src", "."]`, Railway's start command sets `PYTHONPATH=src`, and every developer works from the repository root. So the two console scripts declared in `[project.scripts]`, `s3` and `s3-kgx-export`, could not be installed by anyone, and build phase 4.2 shipped the CLI adapter without that being visible to any gate, review round or premise test in this repository.

The uncomfortable part, recorded rather than smoothed over: this phase's own coverage statement predicted it in as many words, saying that every gate's command had been measured locally but "the orchestration around them has not been executed". The prediction was written, published, and not acted on. It took the machine actually running to turn a known gap into a known defect.

Both red jobs shared this one cause. Neither failure sat inside a round-1 fix, so the phase did not hit the Rule 4 stop condition.

### Review round 2: the phase STOPPED here

A fresh-context re-verifier, which filed none of the round-1 findings, returned **FAIL**. The phase stopped on the spot under `bossman-mode`'s Rule 4 rather than opening a third round, and it is escalated to the product owner.

| ID | Severity | Finding | State |
|----|----------|---------|-------|
| F-4.14-RV-03 | CRITICAL, `Regression of: F-4.14-A-05` | `command_text` strips a comment only when `#` follows whitespace. Bash also starts a comment after `;`, `&&`, `\|\|` and `(`. So `:;#ruff check` runs NOTHING and the arm reads it as containing the command. Eight of the ten gate bodies were rewritten this way in a detached worktree and all 97 tests stayed green, including the mutation harness whose whole job is proving these arms can fail | OPEN, blocks the phase |
| F-4.14-RV-09 | major, reopens F-4.14-A-06 | Gate 9's source check is a substring test, so a file of 16 `assert True` tests whose DOCSTRING names `REFUSAL_TEXT` and `ground_claim` satisfies it | OPEN |
| F-4.14-RV-05 | major, reopens F-4.14-J-01 | `test_p13` claims to defend "no file skipped by both tools" and only checks the `ignore` spelling. Adding `per-file-ignores` for the two files isort skips leaves them checked by neither, and a scrambled import block passed both gates | OPEN |
| F-4.14-RV-08 | major | Gate 5's strict path has never executed. Every green so far is the NOT RUN branch | OPEN, needs a credential |

Four minors were also filed. Both of the lead's corrections were independently CONFIRMED, including on a real checkout of `4ea0778`, where deleting `ignore = ["I001"]` turns `All checks passed!` into 21 I001 errors.

**Why this is a stop rather than a fix.** F-4.14-RV-03 sits inside `b2dfda5`, the round-1 fix commit, and it is the SAME defect class that commit was written to close: a command that is really a comment being counted as a command. Twice now the answer to "does this gate read what actually executes" has been string matching, and twice it has been beaten. Rule 4 exists for exactly this signal: a finding inside a fix means the fix APPROACH is wrong rather than incomplete, so a third string-matching patch is the move the rule forbids.

The irony is worth recording rather than smoothing over. `test_p19_no_gate_is_neutralised` enumerates four named tricks and misses the fifth, which is the enumerate-the-instances shape that `assert_no_db_skips.py` correctly diagnoses and rejects, in its own docstring, in the same commit.

### The one finding this phase cannot close

F-4.14-A-04 is a product-owner decision, not a defect to fix, and it is the largest remaining gap between what this phase claims and what exists.

Section 24 marks all ten gates `Blocking: Yes`, and this phase has been describing its deliverable as "Section 24's ten merge-blocking gates". A GitHub Actions workflow does not block anything. Required status checks under branch protection do, and on this repository they cannot be configured at all:

```
$ gh api repos/monideep2255/agentic-search-ui/branches/develop/protection
{"message":"Upgrade to GitHub Pro or make this repository public to enable this feature.","status":"403"}
```

So after this phase, the thing standing between a bad commit and the live demo is a person choosing to LOOK at a check mark, rather than a person choosing to RUN pytest. That is a real improvement and it is not the claim Section 24 makes.

Three options, for the product owner rather than the lead:

- Upgrade to GitHub Pro, which enables branch protection on a private repository and makes the ten gates genuinely blocking.
- Make the repository public, which enables it at no cost, and is a decision with much wider consequences than CI.
- Accept advisory CI for now, and say so plainly wherever this phase's deliverable is described, so nobody reads "merge-blocking" and believes a merge is actually blocked.

Until it is settled, this phase's coverage statement says advisory, not blocking.

## History

- 2026-08-26: phase opened on `phase/4.14-ci-gates`. Every one of Section 24's ten gates measured at the branch point BEFORE any YAML was written, on the `attack-the-constraint` principle that the input is cheaper to inspect than the output is to debug. Four gates did not pass. Three findings filed, one of them (F-4.14-03) a vacuous-gate risk that would have shipped a green CI run skipping every database-backed test.
