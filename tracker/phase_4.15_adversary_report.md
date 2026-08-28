# Build phase 4.15: adversary report

Run on 2026-08-27 against branch `phase/4.15-release-environments` at `5dea231`, by the unscripted half of the review. The scripted judge graded the phase against its checklist in parallel; nothing here was coordinated with it.

Seventeen findings filed, `F-4.15-A-01` through `F-4.15-A-17`: one critical, twelve major, four minor. Every one is written up in `tracker/phase_4.15.md` under Findings, with the method that established it in the Reason column. This document says what was tried, in what order, and what held.

## Table of contents

- [The worst thing found](#the-worst-thing-found)
- [What was attacked](#what-was-attacked)
- [Area 1: the release automation](#area-1-the-release-automation)
- [Area 2: the isolation claim](#area-2-the-isolation-claim)
- [Area 3: the premise gate itself](#area-3-the-premise-gate-itself)
- [Area 4: what the branch skew broke](#area-4-what-the-branch-skew-broke)
- [What held](#what-held)
- [The pattern across the findings](#the-pattern-across-the-findings)

## The worst thing found

F-4.15-A-14, the only critical. The develop web application cannot reach any API. Its shipped JavaScript bundle carries `http://127.0.0.1:8000`, the local development fallback, where production's carries `https://search-agent-api-production.up.railway.app`. `VITE_` variables are compile-time substitutions, so a variable set after the build leaves the old bundle serving.

Why it is the worst rather than merely the most broken: the phase exists to create a place to see a change running before the audience sees it, and the surface a person actually looks at is dead. It passes T-4.15-12's acceptance, "all four live surfaces answer 200", because a static file server returns 200 for a bundle that points at the visitor's own laptop. No arm observes it. P1 compares the two `web` values as fixture strings and never issues a single HTTP request to either web URL.

## What was attacked

| Order | Target | Method | Outcome |
|---|---|---|---|
| 1 | `.github/release/*.sh` | Executed in six throwaway git repositories under the scratchpad, with hostile and boundary histories | 8 findings |
| 2 | The two live APIs | HTTP only: signup, login, cross-token, CORS preflight, malformed and type-confused bodies, GraphQL, OpenAPI diff | Isolation held, 1 finding |
| 3 | The premise gate and its mutation harness | Read against their own docstrings and acceptance claims; set arithmetic over arm names | 5 findings |
| 4 | Branch skew and migration state | `git rev-parse` and `git show` across the three branches; live bundle download; `/v1/history` | 1 critical, 2 findings |
| 5 | `docs/build/Release_flow.md` | Read against measured live behaviour | 1 finding |

Nothing was pushed anywhere. No script was run against this repository. No denial of service was attempted, no cap was exercised, and the graph credential was not touched.

## Area 1: the release automation

The soft target, and it was soft. Everything here was found by RUNNING the scripts, not by reading them. Reading them is how they were written, and the code is correct for every history the author had in mind.

What broke:

- F-4.15-A-01, major: a `docs:` commit whose body merely mentions the phrase `BREAKING CHANGE:` in a sentence bumps the MAJOR version. Measured: `v1.2.3` became `v2.0.0`. Conventional Commits defines it as a footer; the script matches it anywhere on any body line. Anyone who can open a pull request chooses that text, and the resulting tag is permanent and published.
- F-4.15-A-02, major: commit subjects land verbatim in `CHANGELOG.md` and in the GitHub Release body. A subject containing a markdown link publishes a live clickable link in the project's official release notes. The workflow's header comment reasons carefully about shell injection and concludes commit text is safe because it is "only matched against, never executed", which is true of the shell and false of the artifact.
- F-4.15-A-03, major: the version and the changelog contradict each other on exactly the case the major bump exists for. A `BREAKING CHANGE:` footer bumps major, and the changelog's Breaking changes group matches only the `!:` header form, so a genuine major release ships with no breaking-change section.
- F-4.15-A-07, major: unrecognised commit types are silently dropped. Measured: six commits in range, one in the changelog. `revert:`, `perf:`, `build:`, `style:` and a capitalised `Fix:` all vanished. A dropped `revert` is the line a reader opens a release note to find.
- F-4.15-A-08, major: a leading-zero version component passes the numeric guard, the arithmetic then fails, and `set -euo pipefail` does not abort. Measured against tag `v1.2.08`: stderr said `value too great for base`, exit status was 0, and `$GITHUB_OUTPUT` carried `should_release=true` with a version identical to the previous tag.
- F-4.15-A-12, major: the back-merge pull request is the one pull request CI never runs on, because events raised by the default `GITHUB_TOKEN` do not create workflow runs. It reaches the default branch with an empty checks list, which reads as nothing to report rather than nothing ran. The same behaviour means the `[skip ci]` marker is not, as its comment claims, what makes the release loop terminate.
- F-4.15-A-05 and F-4.15-A-06, minor: a `|` in a subject silently truncates its changelog line, and the `Full diff` block ends with a bare `echo` carrying no redirect, so from the second release onward every section's last line is glued to the next section's heading. The second one is the same defect the file's own comment says it fixed thirty lines above, arriving from the other end.

What held here: the shell-injection defence is real. No `${{ github.event }}` value is interpolated anywhere. Commit text reaches the scripts through `git log` as data on a pipe, and no subject tried, including backticks, `$(...)`, `##`, and leading dashes, escaped into execution or broke the awk that extracts the release body. The `--match` filter added by F-4.15-05 correctly rejects the repository's real non-semver tag and correctly stops on a prerelease tag. The concurrency group serialises two pushes to the same ref. `open_backmerge_pr.sh` hardcodes `--base develop` and nothing observed can redirect it.

## Area 2: the isolation claim

This is the part of the phase that is genuinely solid, and it was attacked hardest over HTTP because a failure here would have been the worst possible result.

Every attempt failed, which is the correct outcome:

- An account created on develop was refused by production with 401.
- A bearer token minted on develop was refused by production's `/auth/me` with 401, and the converse also held, with both positive controls passing on their own deployment.
- A CORS preflight from the production web origin against the develop API returned 400 with no `access-control-allow-origin`, and the same in the other direction, while each API admitted its own origin with an explicit allow header.
- Malformed JSON, a type-confusion body (`{"email":{"$ne":1},"password":[1,2]}`) and a NUL byte inside an email all produced clean 422 responses from Pydantic. No hostname, database name, connection string, stack trace or file path appeared in any error body.
- GraphQL is behind auth and returns 401 to an unauthenticated introspection query rather than a schema.
- The two OpenAPI documents are byte-comparable on route sets: 16 paths, identical, which is consistent with both deployments running `9b4d1ad`.

One finding, F-4.15-A-16, minor: P3 permanently appends an account to the production user database on every run and there is no teardown. The phase constraint says nothing in this phase rewrites production data, which is literally satisfied and misses the case.

## Area 3: the premise gate itself

The gate is better than most in this repository. Every live arm carries a real positive control, P6 and P7 carry populate-checks, and P8 and P9 both strip comments before parsing after being defeated by their own comments during development, which is recorded in the file rather than quietly fixed. Attempts to find a vacuous arm of the build phase 4.11 shape found none.

The holes are elsewhere, in what the arms claim versus what they contain:

- F-4.15-A-10, major: P1's docstring says "the service ids reported by the two deployments are compared too, because two hostnames can still front one service". No such comparison exists. The arm compares two strings from the same fixture and reads no response field but `status`. The exact failure the docstring names as excluded leaves P1 green.
- F-4.15-A-11, major: no arm can detect a recurrence of F-4.15-01, the finding this phase opened around. P7 never reads a deployment; it compares `env.example` against a 26-name list hardcoded in the test body and dated 2026-08-27. P6 compares production against develop, never against `env.example`. The live set and the documented set are never compared in either direction.
- F-4.15-A-13, major: P9 verifies that `release.yml` contains no shell and then never looks at the shell. Its only statement about the four scripts is that they exist and are executable. All eight behavioural defects above live in files no arm opens, and no test in the repository invokes any of them.
- F-4.15-A-15, major: P6 and P9 have no mutation case at all, so "every arm is proven able to fail by a mutation harness" is false for two of nine. P9 is the worse omission: it is the only arm guarding the release automation.

On the specific questions asked of the gate. P6 comparing names rather than values is real but already disclosed in the phase's own coverage statement, so it is not filed. P2 and P3 running twice is safe: `_throwaway_credentials()` mints a fresh uuid per run, so re-runs never collide. Rate-limited or capped signup does not produce a false pass: `assert created.status_code == 201` fails first and loudly. A deployment broken so that every request fails identically does not pass the gate either, because P2, P3 and P4 each assert a positive control before their negative one.

## Area 4: what the branch skew broke

`git rev-parse` shows `origin/production` and `origin/develop` are BOTH at `9b4d1ad`. Neither contains this phase's changes. That produced two findings beyond the critical one.

- F-4.15-A-09, major: P5 is red live right now on both deployments, since neither `/health` reports `app_env`, and T-4.15-10's stated remedy is wrong. Production deploys from `production`, which a merge to `develop` does not move, so P5 stays red after this pull request merges and clears only after a full release, which the coverage statement places outside this phase. Done-when 5 is therefore unreachable within the phase.
- F-4.15-A-17, minor: `Release_flow.md` states the `app_env` behaviour in the present tense and makes reading it step 7 of the release procedure. The first operator to follow the runbook will find the confirmation step impossible, immediately after a production merge.

Migrations were checked by exercising the API rather than by reading code. `GET /v1/history` on develop, authenticated with a token minted there, returned 200 and `{"items":[],"count":0,"omitted_count":0}`. That is build phase 4.13's owner-scoped read over the `interactions` table against develop's brand new Postgres, so `RUN_MIGRATIONS_ON_STARTUP` did its job and there is no schema difference between the two deployments. Signup, login and `/auth/me` all work on develop, so the `users` table is present too.

## What held

Stated explicitly, because a review that lists only failures misreports the phase.

- Cross-deployment auth isolation, in both directions, through the code path that depends on it.
- Per-deployment CORS, in both directions, with the positive half of each check passing.
- Error hygiene. Nothing tried leaked a hostname, a credential, a path or a stack trace.
- Shell-injection defence in the release workflow, which is genuinely correctly reasoned and correctly implemented.
- Migration state on the new develop database.
- The gate's positive controls and populate-checks, which are the parts this repository has historically got wrong.

## The pattern across the findings

Three shapes account for fourteen of the seventeen.

- A document or docstring asserts a property the code beside it does not implement. F-4.15-A-10, F-4.15-A-11, F-4.15-A-12, F-4.15-A-13, F-4.15-A-15, F-4.15-A-17. This is the F-2.1-J5-01 shape LEARNINGS.md already names: a confident comment is where the next reader stops checking. It is the dominant failure of this phase, and the phase file's own prose is unusually good, which is exactly what makes it load-bearing when it is wrong.
- A defect that reading cannot find and one execution finds immediately. F-4.15-A-01, A-05, A-06, A-07, A-08, and the critical A-14. Every one was found by running something, and every one is invisible to review because the code is correct for the inputs its author had in mind. This is the same result F-4.15-05 already recorded inside this phase, repeated eight more times, which suggests the lesson was filed rather than generalised.
- Verification moved somewhere nothing verifies. F-4.15-A-13 is the clean case: build phase 4.14's rule that a `run:` body must be exactly one script path is correct and was applied correctly, and it relocated one hundred percent of the release logic into files the gate does not open. A rule that makes one surface checkable by moving the risk to an unchecked surface has not reduced the risk, and no coverage statement mentions the move.

The single highest-value fix is not any one finding: it is a test that executes `derive_version.sh` and `write_changelog.sh` against fixture histories. Eight of seventeen findings die to it, and T-4.15-11's acceptance already claims it exists.
