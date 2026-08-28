# Build phase 4.15 gap-check report

The four checks a previous re-verifier never ran, because it stopped correctly under a
stop rule after finding one critical. "Not run" is a fail, never a pass, so they are run
here from fresh context, against the code and the live deployments rather than against
any report, commit message or findings row.

Branch `phase/4.15-release-environments`, HEAD `a48d1fb`. Verified 2026-08-28.

## Table of contents

- [Verdict summary](#verdict-summary)
- [Check 1: the P3a and P3b pair that replaced F-4.15-J-04](#check-1-the-p3a-and-p3b-pair-that-replaced-f-415-j-04)
- [Check 2: the live web bundles that F-4.15-A-14 was filed against](#check-2-the-live-web-bundles-that-f-415-a-14-was-filed-against)
- [Check 3: the one commit parser that replaced two](#check-3-the-one-commit-parser-that-replaced-two)
- [Check 4: whether P5 could pass today](#check-4-whether-p5-could-pass-today)
- [Findings filed](#findings-filed)
- [What this report does not cover](#what-this-report-does-not-cover)

## Verdict summary

| Check | Subject | Verdict |
|---|---|---|
| 1 | F-4.15-J-04's replacement pair, P3a and P3b | FAIL, a proxy remains (F-4.15-GC-01, major) |
| 2 | F-4.15-A-14, the develop bundle's API host | PASS, measured on both live bundles |
| 3 | F-4.15-A-01, A-03 and A-07, the single commit parser | PASS on all seven required cases, with a minor prose and contract defect (F-4.15-GC-02) |
| 4 | The claim that P5 cannot pass before this branch merges | PASS, the claim is true and is not an excuse |

## Check 1: the P3a and P3b pair that replaced F-4.15-J-04

Three questions were put. They are answered separately because they do not have the same
answer.

Can P3a pass against a deployment that does NOT verify signatures? No, and this half is
sound. P3a
(`tests/system_03_search_agent/tools/test_release_environments_premise.py:298-414`) signs
up, logs in, asserts the untampered token returns 200 from `/auth/me` as a positive
control, then flips one character in the MIDDLE of the signature segment and requires 401.
A deployment that skipped verification would return 200 on the tampered token and go red.
The positive control closes the other direction, so a deployment that rejected everything
cannot pass either. The route is the right one: `/auth/me` is
`src/system_03_search_agent/auth/router.py:659-662`, which depends on `get_current_user`,
so the access-token path is exercised and not the guest fallback. The docstring's citation
of `src/system_03_search_agent/auth/dependencies.py:108-111` for the database lookup is
accurate; the lookup and its raise are lines 108 to 110.

Does P3b read what it claims to read? Not quite. P3b (`:417-489`) claims the two
deployments "hold" different signing keys. It shells out to
`railway variables --kv` and compares SHA-256 digests of the `AUTH_SECRET` variable
CONFIGURED on each project's `search-agent-api` service. That is the configured value, not
the value the running process holds. The hashing is done correctly and no secret can reach
an assertion message, so the security objection the module docstring raised is genuinely
answered.

Is the pair sufficient? No. P3a never reads a variable and P3b never sends a request, so
nothing links the key each deployment actually verifies with to the variable P3b compared.
P3a's own claim that the two arms together prove "the keys differ, and each deployment
enforces its own" (`:322-329`) is false on the second clause. The concrete state that
makes both arms green while the property is false: both running containers hold the same
signing key while the two configured variables differ, which is what a Railway environment
duplicate followed by rotating only production's value produces whenever the other service
has not redeployed onto the new value. P3a is green on each deployment, because each is
self-consistent with the key its own process holds, which is the shared one. P3b is green,
because the configured strings differ. A develop-minted token's signature then verifies on
production and the 401 arrives on the missing user row at `auth/dependencies.py:108-110`,
which is exactly the database-separation proxy F-4.15-J-04 was filed to remove.

This is a defect in the gate's proof, not a product vulnerability.
`src/system_03_search_agent/auth/tokens.py:47-60` reads `AUTH_SECRET` from the environment
at call time and raises rather than falling back, so the shipped code cannot verify with a
third key.

A direct arm was available and was not written. P3b already holds both plaintext secrets
in process and `jwt` is already a dependency, so an arm can create an account on
production, read its real user id from `/auth/me`, mint a token for THAT id signed with
DEVELOP's secret, and require 401, with the positive control that the same id signed with
PRODUCTION's own secret returns 200. That composition measures the property with no proxy,
and the positive control is what distinguishes a key rejection from a missing-row
rejection, which is the one thing the current pair cannot do.

Filed as F-4.15-GC-01, major.

## Check 2: the live web bundles that F-4.15-A-14 was filed against

PASS. Both bundles were fetched and read; nothing here is taken from a report.

Both index pages return 200 and reference different asset hashes, so the two deployments
are serving different builds:

```
===== PRODUCTION web =====   http=200 size=399   /assets/index-D0Q-7r85.js
===== DEVELOP web =====      http=200 size=399   /assets/index-BnGS20ut.js
```

Both bundles downloaded (394462 and 394466 bytes) and every absolute host extracted:

```
===== HOSTS IN PRODUCTION BUNDLE =====
  18 http://www.w3.org
   2 https://search-agent-api-production.up.railway.app
   2 https://react.dev
   1 https://mui.com
===== HOSTS IN DEVELOP BUNDLE =====
  18 http://www.w3.org
   2 https://search-agent-api-develop-43b3.up.railway.app
   2 https://react.dev
   1 https://mui.com
```

Each bundle contains exactly one API host and it is its own, matching
`tests/system_03_search_agent/tools/fixtures/release_environments.json`. The loopback
address F-4.15-A-14 was filed for is gone from both, confirmed by explicit count rather
than by absence of a grep hit:

```
=== bundle_prod ===  127.0.0.1: 0   localhost: 0   :8000: 0
=== bundle_dev  ===  127.0.0.1: 0   localhost: 0   :8000: 0
```

The develop web app can now reach its own API. F-4.15-A-14 is closed on measurement.

## Check 3: the one commit parser that replaced two

PASS on every required case. `commit_lib.sh`, `derive_version.sh` and `write_changelog.sh`
were copied into a scratch directory and run against purpose-built throwaway git
repositories. The real repository was never used as a subject and nothing was pushed
anywhere. Baseline tag `v1.2.3` in every case.

| Case | Input | Required | Observed | Verdict |
|---|---|---|---|---|
| A | `BREAKING CHANGE:` mid-sentence in a body | no major bump | `bump=patch -> v1.2.4`, commit under Maintenance | PASS |
| B | real `BREAKING CHANGE:` footer | major bump and a breaking section | `bump=major -> v2.0.0`, first group `### Breaking changes` | PASS |
| C | `feat(api)!:` header | major bump and a breaking section | `bump=major -> v2.0.0`, first group `### Breaking changes` | PASS |
| D | `wip:` and a capitalised `Fix:` | still appear in the changelog | both under `### Other changes`, none dropped | PASS |
| E | subject containing `\|` | not truncated or mangled | `- web: tables \| pipes \| everywhere` rendered whole | PASS |
| F | markdown and HTML control characters | neutralised | `\[click me\](...)`, `&lt;img ...&gt;`, `\*b\*`, `\_i\_`, `\~s\~`, escaped backticks and backslash | PASS |
| G | empty range, tag at HEAD | no release, no changelog | `should_release=false`, exit 0; changelog exits 1, "nothing to write" | PASS |

Two further cases were run beyond the required set, because both are the class the earlier
findings belong to.

The empty repository, which is F-4.15-J-11's class. A repository with no commits and no
tags: `git log failed for range <whole history> (exit 128)`, `derive exit=1`, and
`GITHUB_OUTPUT` empty. A failing `git log` now stops the release rather than falling
through to the `patch` default, and nothing is emitted.

A mixed range, which is the A-01, A-03 and A-07 disagreement class stated directly. Five
commits, the breaking one fourth, carrying the `BREAKING-CHANGE:` alias footer on a
non-conventional capitalised subject. `derive_version.sh` printed `bump=major -> v2.0.0`
and `write_changelog.sh` put that same commit first under `### Breaking changes`, with all
five commits present across Breaking changes, Features, Security and Maintenance. The two
readers agree because there is now only one reader. The class is genuinely closed.

Two contract defects were found while running this, both latent and both filed as
F-4.15-GC-02, minor. `commit_lib.sh:40` documents `release_commit_shas` as printing shas
"oldest first" and it returns them newest first, since `:44` has no `--reverse`; measured
as creation order `chore, docs, feat, Fix, security` returning
`security, Fix, feat, docs, chore`. And both readers end in `printf '%s'` (`:51`, `:66`)
with no trailing newline, so the documented "one full sha per line" contract is broken on
the last line; piping the call into `while read -r` returned 4 of 5 commits, losing the
oldest, silently. Both shipped call sites use a here-string, and `<<<` appends the missing
newline, which is the only reason no commit is dropped today. A third caller that pipes
would lose one, and `write_changelog.sh`'s completeness check could not catch it because
both of its counts derive from the same truncated list.

## Check 4: whether P5 could pass today

PASS, the claim is true. It was verified rather than accepted, by fetching both endpoints:

```
=== https://search-agent-api-production.up.railway.app/health ===
{"status":"ok"}
HTTP=200
=== https://search-agent-api-develop-43b3.up.railway.app/health ===
{"status":"ok"}
HTTP=200
```

Neither deployment reports `app_env`, so P5's first assertion,
`assert "app_env" in payload`, fails on production before it reaches anything else. P5 is
red for the stated reason.

The reason is structural rather than a configuration accident, which is what makes the
claim honest rather than convenient. `HealthResponse`
(`src/system_03_search_agent/adapters/web_sse/app.py:323-325`) declares `app_env: str` as
a REQUIRED field, and `get_health` (`:360`) always populates it, defaulting to `unknown`
when `APP_ENV` is unset. So a deployment running this branch's code would return `app_env`
unconditionally, whatever its variables say. Both deployments return `{"status":"ok"}` and
nothing else, so neither is running this branch's code. P5 could not pass today by any
configuration change, and the constraint is real.

## Findings filed

| ID | Severity | One line |
|---|---|---|
| F-4.15-GC-01 | major | The P3a and P3b pair still contains a proxy: nothing ties the key each running deployment verifies with to the `AUTH_SECRET` variable P3b compares, and P3a's docstring claims the composition proves it does |
| F-4.15-GC-02 | minor | `commit_lib.sh` documents an ordering it does not produce, and emits no trailing newline on a contract documented as one sha per line, so a future caller that pipes it silently loses the oldest commit |

Both were written to `tracker/phase_4.15.md` at the moment they were established, before
this report was composed.

## What this report does not cover

Stated rather than left to be discovered, per `.claude/rules/goal-contracts.md`.

- It covers only the four checks the previous re-verifier left unrun. The rest of the
  phase was reviewed by other agents and was deliberately not re-reviewed here, so a
  finding outside these four areas would not have been looked for.
- The premise gate was NOT executed. `RUN_PREMISE_GATE=1` was never set, because two arms
  create real accounts on the live deployments. Every statement about P3a, P3b and P5
  above is derived from reading the arms against the code they exercise, plus unauthenticated
  live probes of `/health`, `/`, and the two asset bundles. No arm was observed passing or
  failing in a test runner.
- F-4.15-GC-01 is reasoned from code, not demonstrated against a live deployment. The state
  that makes both arms green while the property is false was not induced on Railway, which
  would have meant deliberately misconfiguring a running environment. The argument stands on
  what each arm reads and what it never reads.
- Check 3 exercised the scripts through `derive_version.sh` and `write_changelog.sh` only.
  `tag_and_release.sh` and `open_backmerge_pr.sh` were read but never run, since running
  them means tagging and opening a pull request.
- Nothing here re-verifies F-4.15-A-14's history. It confirms the CURRENT state of both
  live bundles and says nothing about what the develop bundle contained when the finding
  was filed.
