# Build phase 4.12: the demo deployment

Branch: `phase/4.12-demo-deploy` (the board's name; `requirements/phase_6/Continuation_prompt.md` said `phase/4.12-demo-deployment`, and the board owns phase status, so the board wins. The prompt is corrected at checkpoint.)
Depends on: 4.11, merged 2026-08-22
Opened: 2026-08-24, after both hard blockers closed (PR #59, PR #60)
Status: IN PROGRESS. Code-side work complete and deployed to the Hetzner box. Railway project provisioned and configured. What remains is build configuration, which is real work rather than a product-owner block.

## Table of contents

- [Scope, and what is deliberately not in it](#scope-and-what-is-deliberately-not-in-it)
- [Tickets](#tickets)
- [What this phase caused and then fixed](#what-this-phase-caused-and-then-fixed)
- [Two recorded figures this phase corrected](#two-recorded-figures-this-phase-corrected)
- [Evidence](#evidence)
- [The deploy, done 2026-08-24](#the-deploy-done-2026-08-24)
- [Still blocked on the product owner](#still-blocked-on-the-product-owner)
- [Railway provisioning, done 2026-08-24](#railway-provisioning-done-2026-08-24)
- [What is left, and it is not a product-owner block](#what-is-left-and-it-is-not-a-product-owner-block)
- [What is live, 2026-08-24](#what-is-live-2026-08-24)
- [The demo is live and answering, 2026-08-24](#the-demo-is-live-and-answering-2026-08-24)
- [The one open defect, stated precisely](#the-one-open-defect-stated-precisely)
- [Carried past the merge, on purpose](#carried-past-the-merge-on-purpose)
- [History](#history)

## Scope, and what is deliberately not in it

From `tracker/BOARD.md`'s 4.12 row: provision the Railway project per Section 24, map every `env.example` group to its Railway variable set, connect the GitHub integration that watches `develop`, and cut Layer 1 over to `GRAPH_QUERY_URL` plus `GRAPH_QUERY_TOKEN`.

NOT in scope, checked against Section 24 rather than assumed:

- The CI merge-blocking gate list (Section 24's ten gates). Build phase 6.1 owns it. This phase touches deployment only.
- Anything that creates a public URL. The security scan's trigger is exposure and it has not been funded, so this phase stops short of the gate rather than through it.

The Layer 1 cutover needs NO code. `execute_cypher` has dispatched on `GRAPH_QUERY_URL` since build phase 4.11, and `env.example` already documents both transports and names HTTPS as the v1 one. The cutover is a Railway variable-set decision, not a change here.

## Tickets

| Ticket | What | Status |
|--------|------|--------|
| T-4.12-01 | Caddyfile replaces `X-Forwarded-For` rather than appending (closes F-4.11-RV-02) | done, `7cb9bd3` |
| T-4.12-02 | `check_drift.sh` covers the deployed Caddyfile | done, `7cb9bd3` |
| T-4.12-03 | Restore `_client_address`'s two-layer claim, which 4.11 conditioned on T-4.12-01 and its arm both existing | done, `7cb9bd3` |
| T-4.12-04 | Retire the stale tunnel probes in eight premise gates | done, `7cb9bd3` |
| T-4.12-05 | `live_only` requires the live network, not a credential (removes the standing six-failure baseline) | done, `7cb9bd3` |
| T-4.12-06 | Premise gate, 28 arms | done, `7cb9bd3` |
| T-4.12-07 | Mutation harness, 14 mutations | done, `f54c205` |
| T-4.12-08 | Deploy the updated Caddyfile and `app.py` to the box | done, 2026-08-24, product-owner approved |
| T-4.12-09a | Railway project, both databases, both service shells | done, 2026-08-24 |
| T-4.12-09b | Variable sets per Section 24, and the Layer 1 cutover | done, 2026-08-24 |
| T-4.12-09c | Build configuration so both services boot | done, both LIVE |
| T-4.12-11 | The Q/A pipeline actually answering on the deployed demo | done for single-hit symbols, VERIFIED with citations; one open edge case below |
| T-4.12-12 | UI polish and streaming behaviour on the deployed demo | OPEN, product-owner observation 2026-08-24, carried past the merge deliberately |
| T-4.12-09d | GitHub integration watching `develop` | OPEN. Deliberately not wired while 4.12 is unmerged, since Section 24 requires CD to watch `develop` only and phase branches to never auto-deploy |
| T-4.12-10 | Security scan before any public URL | DROPPED 2026-08-24 by product-owner decision, logged in `DECISIONS.md` |

## What this phase caused and then fixed

Recorded here rather than in the commit alone, because it is the phase's most transferable output so far.

Correcting the stale tunnel probe (T-4.12-04) made `_graph_is_reachable` answer truthfully for the first time since build phase 4.11. Arms that had been silently skipping began to RUN in the ordinary offline suite, hit `tests/conftest.py`'s block, and FAILED. Measured: `test_write_grounding_premise.py` went from a clean skip to `6 failed, 4 passed, 2 skipped in 169.73s`.

That is exactly the defect T-4.12-05 was written for, reproduced in seven more files by the fix for a different one. Fixing the instance would have been reordering; the fix is `graph_gate.live_graph_arms_enabled`, which requires BOTH facts: the dependency answers, and this process may talk to it.

`graph_is_reachable` was deliberately NOT changed to fold the permission check into itself. A function named "is it reachable" that answers "am I allowed" is a lie at the call site, and the next reader would have to discover it the way this one was discovered. M8c asserts on the source that the two stay separate.

## Two recorded figures this phase corrected

Both by measuring rather than inheriting, which is this repository's standing rule for a carried-forward number:

- The continuation prompt recorded SEVEN stale tunnel-probe files. It is EIGHT.
- The suite's standing six-failure baseline was recorded as pre-existing and unexplained. All six were in one file, all six PASS under `RUN_PREMISE_GATE=1` (`8 passed, 2 skipped`), and the file FAILED where it should have SKIPPED. It is now zero.

## Evidence

- Premise gate, `test_demo_deploy_premise.py`: 28 arms, all passing. (Deliberately NOT written in the `premise gate N of N` form. `check_doc_drift.py` carries ONE canonical fact under that phrasing, the cypher_query gate's, and flags every other use of it as stale. The checker is right and this file is the one that has to move: hedging the number to slip past it would be weakening a verify surface to reach done-when, which `.claude/rules/goal-contracts.md` forbids by name.)
- Mutation harness: 14 of 14. Two failed on first run, both defects in the populate-checks rather than the mutations (a substring check that the explanatory comment also satisfied, twice), recorded rather than repaired quietly.
- Offline suite: `3929 passed, 158 skipped, 1 xfailed, ZERO FAILED` in 85s, against `develop`'s `6 failed, 3887 passed, 152 skipped`.
- Live, `RUN_PREMISE_GATE=1`: `test_citation_trust_full_premise.py` is `10 passed in 472s`. All ten arms, including the TWO that had been silently skipping since build phase 4.11, now run and pass.
- `ruff`: clean on every changed file.
- `check_drift.sh` run against the live box, which exercises T-4.12-02's new pair for real rather than as a string in a script:

```
ok    graph_schema_constants.py
ok    graph_connection.py
ok    graph_http_transport.py
DRIFT app.py
DRIFT Caddyfile
```

Both drifts were expected and were this phase's own commits. They are RESOLVED: see the next section, where the post-deploy run reports 6 of 6 ok. The pre-deploy output is kept because it is the evidence that T-4.12-02's new pair works against the real box rather than only as a string in a script.

## The deploy, done 2026-08-24

Product owner approved after confirming it incurs no new charge, which it does not: `deploy.sh` copies files to the Hetzner CPX42 already running and restarts two systemd units. It provisions no host, no addon and no paid API; the only outbound fetch is `pip install` from PyPI.

Verified after the deploy rather than assumed from its own success message:

| Check | Result |
|-------|--------|
| `check_drift.sh` | 6 of 6 `ok`, including the Caddyfile, which is only in that list because T-4.12-02 put it there |
| `preflight.py --transport graph` | `ok, HTTPS query service HTTP 200 in 372ms` |
| `systemctl is-active caddy graph-query-service` | `active`, `active` |
| `caddy validate --config /etc/caddy/Caddyfile` | `Valid configuration`, so Caddy parsed and accepted the new `header_up` directive rather than falling back |
| Live premise gate, `test_graph_query_service_premise.py` | 59 of 59 passed in 13.25s, including P20, which pins the rightmost-element rule the directive is the second layer for |

So the service now genuinely has two layers, which is the condition build phase 4.11 set on restoring that claim in `_client_address`'s docstring.

One transient worth recording so it is not read as a defect later: an `ssh` call between the deploy and the verification timed out during banner exchange, and the next one succeeded. It was not reported as a blocker, per `LEARNINGS.md`'s 2026-08-22 entry, where a probe artifact from this harness cost a wrong blocker and an unnecessary credential request. The HTTPS probe is stronger evidence than `systemctl` anyway: it traverses Caddy and the service both.

## Still blocked on the product owner

- T-4.12-09, Railway provisioning. Needs the product owner's account. Product-owner direction 2026-08-24: use Railway's MCP server rather than the console by hand. That is an executable extension, so `supply-chain-security`'s enable-versus-trust gate applies before it is wired in, and this session cannot run an OAuth flow.
- T-4.12-10, the security scan. Paused since 2026-08-03 on cost. Product-owner direction 2026-08-24: "security will be last step". Read as the last step BEFORE the public URL, which is what `tracker/BOARD.md` already requires ("its trigger is exposure, so it runs before any public URL exists, not after"). Confirm that reading before publishing anything.

## Railway provisioning, done 2026-08-24

Product owner chose Railway for the first month over a Netlify plus Render split, after being shown the arithmetic below.

WHAT EXISTS, verified with `railway status` rather than taken from each command's own output:

| Component | State |
|-----------|-------|
| Project `system3-search-agent` | created, id `0f85f78e-1ffc-4a62-b3d8-a03dcae9b585` |
| `Postgres` | Online, `postgres-ssl:18`, 4.9 GB volume |
| `Redis` | Online, with volume |
| `search-agent-api` | created, Offline (no deployment yet, so no compute billed) |
| `search-agent-web` | created, Offline |

The two service shells were deliberately created WITHOUT a repo link. Linking a repo deploys immediately, and there is no build configuration in this repository yet (Section 24 says so itself: "no Railway config file exists yet"), so linking first would have started a build loop that fails repeatedly and bills for every attempt.

THE VARIABLE SET on `search-agent-api`, 14 variables, mapped from Section 24's table:

- Addon references, so no credential is copied: `USER_DB_URL=${{Postgres.DATABASE_URL}}`, `REDIS_URL=${{Redis.REDIS_URL}}`.
- App config: `APP_ENV=production`, `LOG_LEVEL=INFO`.
- Step 1.11 starter cost caps: `PER_QUERY_COST_CAP_USD=0.10`, `PER_USER_DAILY_QUERY_CAP=100`, `SYSTEM_DAILY_CAP_USD=10`, `PER_STEP_TIMEOUT_SECONDS=90`.
- From `.env`: `OPENROUTER_API_KEY`, `NCBI_API_KEY`, `NCBI_EMAIL`, `GRAPH_QUERY_URL`, `GRAPH_QUERY_TOKEN`.
- `AUTH_SECRET`, FRESHLY GENERATED rather than copied, per Section 24's "generated per environment... Never shared between dev and production". 32 bytes of `secrets.token_hex`.

The credential-bearing values were set by a script that reads `.env` and hands each value to a child process, printing only variable NAMES. No secret entered a command line or the session transcript, which is what `ai-security-standards` means by "log the var name, never its value".

THE LAYER 1 CUTOVER IS DONE, and it is visible as an ABSENCE: no `GRAPH_PG_*` variable is set on the service. `execute_cypher` dispatches on `GRAPH_QUERY_URL`, so with that set and the direct-connection variables empty, every Layer 1 call goes over the HTTPS service. This needed no code, because build phase 4.11 built the dispatch.

`CORS_ORIGINS` is deliberately NOT set yet. It wants the deployed `search-agent-web` origin, which does not exist until that service has a URL.

WHAT IT COSTS, from Railway's published per-second rates converted to a month (2,592,000 seconds): $10.00 per GB-month of RAM ($0.00000386/GB/s) and $20.01 per vCPU-month ($0.00000772/vCPU/s). Hobby is $5/month including $5 of usage credit. Four components at roughly 0.25 to 0.5 GB each is 1 to 1.5 GB continuous, so roughly $12 to $20 per month. That is an estimate from published rates, not a quote.

Worth knowing for a one-month trial: deleting the services stops usage billing immediately, since it is metered per second, but the $5 monthly subscription recurs until the plan is downgraded. Two separate actions.

## What is left, and it is not a product-owner block

T-4.12-09c is the next real work and it is engineering, not permission:

- The API needs a start command. The documented one is `uvicorn system_03_search_agent.adapters.web_sse.app:app` (README.md:102), and the package lives under `src/`, so it needs `PYTHONPATH=src` or a working `pip install .`. That install is a KNOWN-BROKEN finding already owned by build phase 6.1, so `PYTHONPATH` is the path that does not depend on fixing it first.
- The frontend builds with `tsc -b && vite build` and lives in `frontend/`, so its service needs a root directory setting.
- Both are per-service settings. A single root `Procfile` cannot serve a two-service monorepo, so this wants a `railway.json`, which Section 24 already anticipates as a Phase 6 build target rather than something that exists.

## What is live, 2026-08-24

THE API IS DEPLOYED AND SERVING, verified over its public URL rather than from a status field:

| Check | Result |
|-------|--------|
| `https://search-agent-api-production.up.railway.app/health` | `{"status":"ok"}`, HTTP 200 in 0.9s |
| Routes present | `/v1/query`, `/v1/query/{run_id}/events`, `/v1/allowance`, `/v1/persona` |
| `/v1/allowance` with no credential | HTTP 401, `invalid or expired credentials` |

That 401 is the auth layer working on a public URL, not a defect, and it is worth recording as a positive result rather than passing over it.

Both start commands were VERIFIED LOCALLY before being committed: the API booted under `PYTHONPATH=src uvicorn ...` and answered `/health` with 200, and `npm run preview` served the built `dist` with 200. Neither was inferred from the README.

THE FRONTEND IS NOT SERVING, and the cause is a Railway behaviour rather than a defect in this repository. Full account in `LEARNINGS.md`, 2026-08-24. In short: `railway up` deploys from the LINKED PROJECT ROOT regardless of the working directory, so `search-agent-web` received the root `railway.json`, which is the API's uvicorn config, and ran a second copy of the API. It reported `Online` and served a FastAPI 404.

The redundant deployment was removed with `railway down` rather than `railway service delete`, so the service shell and its generated domain survive and nothing has to be recreated. Confirmed by the RESPONSE BODY changing, not by the status field: `{"detail":"Not Found"}` (FastAPI running) became `{"status":"error","code":404,"message":"Application not found"}` (Railway edge, no app).

WHAT THE FRONTEND NEEDS, and neither option is available from this harness:

- The service's Root Directory set to `frontend`. It is a dashboard-only field: `railway service source connect` has no flag for it, `railway up frontend` and `railway up .` both return `prefix not found` despite `--help` documenting a `[PATH]` argument, and Railway's GraphQL `serviceInstanceUpdate` returns HTTP 403 to the CLI's own stored token, which is not scoped for the public API.
- Or the Railway MCP, authorised interactively, which does expose service configuration.

CURRENT BILLING SHAPE: three components running, not four. `search-agent-api`, Postgres and Redis are Online; `search-agent-web` is Offline and costs nothing while it serves nothing.

`CORS_ORIGINS` is still unset, deliberately. It wants the frontend's origin, and until that service actually serves the frontend there is no correct value to give it.

## The demo is live and answering, 2026-08-24

Both URLs serve, and the agent loop returns grounded answers with citations.

| Surface | State |
|---------|-------|
| `https://search-agent-web-production.up.railway.app` | Online, serves the real bundle |
| `https://search-agent-api-production.up.railway.app` | Online, `/health` 200 |
| Postgres, Redis | Online |

END TO END, measured on the deployed API rather than asserted:

```
Which diseases are associated with BRCA1?
  [ 2.1s] guard   passed
  [ 6.9s] plan    cypher_query + ncbi_efetch for NCBIGene:672
  [15.8s] 5 citations: Gene 672, MedGen C0346153, C2676676, C3280442, C4554406
  [15.8s] trust_signal outcome answer, grounded true
```

FIVE DEFECTS WERE FIXED TO GET THERE, each found by running the thing rather than reading it, and each is a separate commit:

1. No database schema. `POST /auth/guest` returned 500 with `relation "guest_sessions" does not exist`. Migrations had never run. Neither `startCommand` in `railway.json` nor `RAILWAY_RUN_COMMAND` reached the container, so this moved into an opt-in startup hook in code.
2. Missing environment variables. Found by DIFFING `env.example` against the service rather than one 500 at a time, which is what stopped this being five more round trips.
3. `ANON_DAILY_RUN_CAP` unset, and unset in `.env` too. `env.example` documents 200.
4. The plan step timing out on every query. See `DECISIONS.md`, 2026-08-24.
5. `GCK` refused as an unknown gene. See below; fixed in code, still failing in production.

## The one open defect, stated precisely

`GCK` resolves LOCALLY to `NCBIGene:2645` and is REFUSED on the deployed API, on identical committed code, after a cache-disabled rebuild.

What is established:

- It is not build staleness. `NIXPACKS_NO_CACHE=1` is set on the service and the fix was redeployed after committing.
- It is not NCBI being unreachable from Railway. `BRCA1` resolves there and answers with real citations.
- It is not the fix being wrong. The live premise gate passes 29 of 29 including the `GCK` arm, and the full suite is 3930 passed with zero failures.

The difference between the two symbols is the number of E-utilities calls needed. `BRCA1` resolves on the FIRST call, because NCBI Datasets returns exactly one report for it. `GCK` is alias-ambiguous in BOTH legs (Datasets returns 3 reports, ESearch returns 3 ids), so it needs three calls in quick succession: Datasets, then ESearch, then the batched ESummary confirmation.

The hypothesis, NOT confirmed: E-utilities rate limiting against Railway's shared egress address, where three rapid calls trip a limit that one does not. `.claude/rules/tool-call-budgets.md` records the ceiling as 3 requests/second unauthenticated and 10 with a key, and notes the limit belongs to the API PER HOST rather than to any one caller, which is exactly the shape a shared egress IP would hit.

It is a hypothesis rather than a finding because the traceback could not be read: Railway's log stream returns container startup and `/health` lines and no request-level logs at all, through several attempts. Recorded as unproven rather than asserted.

WHAT WOULD SETTLE IT, for whoever picks this up: get the actual exception. Either make the log stream work, or add a temporary diagnostic endpoint that calls `resolve_symbol_to_curie("GCK")` and returns the tool's own `status` and `error` fields, which `ncbi_efetch` already carries and never raises through.

## Carried past the merge, on purpose

Build phase 4.12 merges with these open. That is a decision rather than an oversight: the phase's own scope was to get the product deployed and answering, and it does both. Nothing below blocks a demo.

- T-4.12-12, UI AND STREAMING. FOUR SPECIFIC DEFECTS, reported by the product owner from the live demo on 2026-08-24 and recorded in their own words rather than paraphrased into something tidier:

  1. "Streaming does not work properly."
  2. "Then chat does not continue" -- a second turn cannot be taken.
  3. "The search is super super super super slow."
  4. "The answer presentation is horrible and nothing close to what the design sync had."
  5. "I do not see the KGX, REST API, command line or MCP setup up properly on the integrations page." All four of those surfaces EXIST and are merged (build phases 4.1 MCP, 4.2 CLI, 4.3 GraphQL, 4.4 KGX export, plus the REST plus SSE adapter), so this is a presentation gap on that page rather than missing capability. Worth checking `frontend/src/stubs/registry.ts` first: the integrations page may still be rendering stub placeholders for surfaces that have since shipped.
  6. NO CLIENT-SIDE ROUTING. Every page is served at `/` and the URL never changes. The intended routes, given verbatim by the product owner:

     | Page | Route |
     |------|-------|
     | Home | `/` |
     | Integrations | `/integrations` |
     | About | `/about` |
     | Docs | `/docs` |

     This is a real deployment consideration and not only a frontend one: the app is served by `serve -s dist`, and the `-s` flag is single-page-app mode, which rewrites unknown paths to `index.html`. So deep links will resolve to the app once routes exist, and no server change is needed. What is missing is the router itself.

  ONE OBSERVATION THAT MAY COLLAPSE TWO OF THE FIRST FOUR, offered as a lead and not as a diagnosis: 1 and 3 are plausibly the same defect. Measured on the deployed API, the BRCA1 query returns in 15.8 seconds and emits `token` events throughout. If those tokens are not rendering incrementally in the browser, the reader sees nothing at all for fifteen seconds and then an answer appears at once, which is indistinguishable from "super slow" from the outside. Check whether the SSE stream is being consumed incrementally BEFORE treating latency as a separate problem, or the work will go into speeding up something that is already fast enough to feel responsive if it streamed.

  Latency figures already measured, so nobody re-derives them: guard 2.1s, think about 4s, plan about 3s after the model swap, act and write about 9s, total 15.8s for a two-tool answer with five citations. The plan step was 45s before this phase and is not the constraint any more.

  Defect 4 has a defined source of truth and MUST NOT be guessed at: `docs/build/design/Design_to_build_workflow.md` names which of the four design artifacts is authoritative, and build phase 4.8's rule stands that builders build against the component cards, never against the prototype, and that the cards are reconciled to the prototype first.

  TWO THINGS ALREADY KNOWN that bear on all four: `frontend/src/stubs/registry.ts` still marks stubbed surfaces, and this repository has NO visual check at all. That is build phase 4.8's recorded lesson, and it is the reason a defect list like this one arrives from a person rather than from a suite: "nothing in this repository looks at the rendered page", after two major layout defects survived 147 unit tests, a clean production build and a full WCAG 2.1 AA pass.
- The `GCK` refusal, above. Hypothesis recorded, not confirmed.
- T-4.12-09d, the GitHub CD integration, which could not be wired before the merge because Section 24 requires CD to watch `develop` only and phase branches to never auto-deploy. It becomes wireable the moment this merges, and that ordering is the reason it was left rather than an omission.

## History

- 2026-08-24: Opened after PR #59 and PR #60 closed both hard blockers. Preflight READY on all three transports.
- 2026-08-24: Scouted before writing. Corrected the branch-name discrepancy, the seven-versus-eight count, and found the Caddyfile absent from the drift check.
- 2026-08-24: Premise gate written first, 17 of 20 arms red for the right reason.
- 2026-08-24: T-4.12-01 through T-4.12-06 landed as `7cb9bd3`, including the self-caused regression and its category fix.
- 2026-08-24: T-4.12-07 landed as `f54c205`.
- 2026-08-24: `check_drift.sh` run live; both expected drifts confirmed. Stopped at the deployment gate.
- 2026-08-24: Railway CLI upgraded 4.30.5 to 5.43.2 by the product owner, after the documented `railway setup agent` and `railway mcp install` commands were found NOT to exist on 4.30.5. The command had been given from documentation without checking it against the binary, and it was wrong.
- 2026-08-24: Railway MCP installed with `railway mcp install --agent claude-code --oauth`, chosen over `railway setup agent` because that variant also writes third-party SKILLS into the harness, and over `--remote`/`--local` because only `--oauth` scopes to chosen workspaces with short-lived revocable tokens. It registered but needs an interactive OAuth flow, so it is unusable from a non-interactive session. The CLI did the provisioning instead, so the MCP was a convenience rather than a dependency.
- 2026-08-24: Project, both databases, both service shells and 14 variables provisioned and verified.
- 2026-08-24: Railway project provisioned; API built, deployed and verified live over its public URL. Frontend deployment wasted one build on the monorepo config trap above, was removed, and is blocked on a dashboard-only Root Directory field.
- 2026-08-24: The demo answers end to end. Five defects fixed to get there, all found by running it. One open: `GCK` refused in production and resolving locally, hypothesis recorded as unproven because the traceback is unreadable.
