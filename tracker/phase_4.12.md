# Build phase 4.12: the demo deployment

Branch: `phase/4.12-demo-deploy` (the board's name; `requirements/phase_6/Continuation_prompt.md` said `phase/4.12-demo-deployment`, and the board owns phase status, so the board wins. The prompt is corrected at checkpoint.)
Depends on: 4.11, merged 2026-08-22
Opened: 2026-08-24, after both hard blockers closed (PR #59, PR #60)
Status: IN PROGRESS. Code-side work complete; provisioning and the security scan are the product owner's.

## Table of contents

- [Scope, and what is deliberately not in it](#scope-and-what-is-deliberately-not-in-it)
- [Tickets](#tickets)
- [What this phase caused and then fixed](#what-this-phase-caused-and-then-fixed)
- [Two recorded figures this phase corrected](#two-recorded-figures-this-phase-corrected)
- [Evidence](#evidence)
- [Blocked on the product owner](#blocked-on-the-product-owner)
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
| T-4.12-08 | Deploy the updated Caddyfile and `app.py` to the box | BLOCKED, product-owner approval |
| T-4.12-09 | Railway provisioning, variable sets, GitHub integration | BLOCKED, product owner |
| T-4.12-10 | Security scan before any public URL | BLOCKED, not funded |

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

- Premise gate: 28 of 28.
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

Both drifts are expected and are this phase's own commits. They resolve by running `deploy.sh`, which is T-4.12-08.

## Blocked on the product owner

Three items, in the order they gate each other:

1. T-4.12-08, deploying the Caddyfile and `app.py` to the Hetzner box. `ssh` from this harness works (verified: `hostname` returned `agentic-search-vps`), so this is NOT a technical blocker. It is a policy one: `.claude/rules/ai-security-standards.md` states an agent never autonomously deploys to production or modifies infrastructure. Needs an explicit go-ahead.
2. T-4.12-09, Railway provisioning. Needs the product owner's account and credentials.
3. T-4.12-10, the security scan. Paused since 2026-08-03 on cost; its trigger is exposure and 4.12 is the first exposure. Needs a funding decision before any public URL exists.

Until 1 lands, the `X-Forwarded-For` fix exists in this repository and NOT on the box, so the service is still running with one safeguard. That is the honest state and it is why `check_drift.sh` now reports it.

## History

- 2026-08-24: Opened after PR #59 and PR #60 closed both hard blockers. Preflight READY on all three transports.
- 2026-08-24: Scouted before writing. Corrected the branch-name discrepancy, the seven-versus-eight count, and found the Caddyfile absent from the drift check.
- 2026-08-24: Premise gate written first, 17 of 20 arms red for the right reason.
- 2026-08-24: T-4.12-01 through T-4.12-06 landed as `7cb9bd3`, including the self-caused regression and its category fix.
- 2026-08-24: T-4.12-07 landed as `f54c205`.
- 2026-08-24: `check_drift.sh` run live; both expected drifts confirmed. Stopped at the deployment gate.
