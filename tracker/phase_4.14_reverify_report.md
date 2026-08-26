# Build phase 4.14 re-verification report

VERDICT: IN PROGRESS

Fresh-context re-verification (round 2) of the round-1 fixes on `phase/4.14-ci-gates`.
Subject commits: `4ea0778` (original), `b2dfda5`, `8675147`, `36adf16`, `e2bc2ac`.
Re-verifier did not file the round-1 findings. Everything below is re-derived from
code and from commands run in this session. Written incrementally.

## Findings

(appended as confirmed)

## Round-1 finding re-verification table

(appended)

## What I could NOT verify

(appended)

---

## Priority 1: `.github/scripts/assert_no_db_skips.py` (the deny-list to allowlist inversion)

### Both directions verified. Both hold.

RED on a dead database. Command run:

```
USER_DB_URL="postgresql://postgres:postgres@127.0.0.1:59999/nope" \
  ./venv/bin/python -m pytest -m "not integration" -q --junitxml=/tmp/rv_dead.xml -p no:randomly
```
```
55 failed, 3578 passed, 184 skipped, 23 deselected, 1 xfailed, 4 warnings, 25 errors in 87.94s
```
```
$ ./venv/bin/python .github/scripts/assert_no_db_skips.py /tmp/rv_dead.xml
FAIL: 51 test(s) skipped for a reason nothing sanctions. The gate cannot certify what it did not run.
...
51 of these mention a database. Check that the `postgres` service in .github/workflows/ci.yml is healthy...
EXIT=1
```

It catches the skip the round-1 adversary said the DENY-list version missed. Confirmed by
re-derivation, not by reading the claim:

```
tests.system_03_search_agent.adapters.web_sse.test_phase_4_10_premise.TestAdmitArm::...
  user database unreachable at postgresql://postgres:postgres@127.0.0.1:59999/nope;
  the guest allowance is a server-side count
```
That message contains none of the six phrasings the first version listed, and it is now caught.

Leak check, which was the specific risk the inversion creates. I re-ran the script's own
`classify()` and `sanctioned_reason()` over the dead-database report and cross-matched every
SANCTIONED skip against the script's own `_LIKELY_DATABASE` regex:

```
total 3843  unsanctioned 51
sanctioned {'the live premise-gate opt-in': 101,
            'a live Layer 1 graph or model credential CI does not hold': 32,
            'a known open finding, deliberately skipped and tracked': 1}
count of DB-mentioning sanctioned skips: 0
```

Every distinct sanctioned message was printed and inspected. The 32 admitted by the broad
`live graph|layer 1 graph|graph tunnel|graph service|real model key` pattern reduce to five
distinct messages, none of which is a database skip:

```
Layer 1 graph unreachable: open the tunnel and re-run
needs the Layer 1 graph tunnel, which cannot be opened from this environment (T-3.0-07)...
the premise gate needs the live graph AND a real model key, since its whole purpose is to exercise cross-layer...
the premise gate needs the live graph AND a real model key, since its whole purpose is to exercise generation...
the premise gate needs the live graph AND a real model key, since its whole purpose is to exercise synthesis...
```

So on today's suite the answer to "could a database skip match a sanctioned pattern and be
silently re-admitted" is measured NO, not asserted no. Two residual observations below.

### F-4.14-RV-01 — MINOR — the allowlist is not conjunctive, so one future message re-admits a database skip

`.github/scripts/assert_no_db_skips.py:135-152` (`_SANCTIONED_SKIPS`), `:171-176`
(`sanctioned_reason`).

`sanctioned_reason` returns on the FIRST pattern that appears anywhere in the message. Nothing
requires that the message be ONLY about the sanctioned dependency. A skip message that names
both a sanctioned dependency and the database is admitted whole. Demonstrated:

```
>>> sanctioned_reason("search_agent_users PostgreSQL is not reachable, and the live graph is down")
'a live Layer 1 graph or model credential CI does not hold'
```

This is not hypothetical shaped: eight files in this repository already skip on a graph-or-model
condition, and several premise gates already need BOTH a database and a graph. The day one of them
words its message with both, the gate re-admits it and prints `ok`. The `_LIKELY_DATABASE` regex
that would have caught it is deliberately advisory only ("Matching this changes nothing about the
verdict") and never consulted on the sanctioned path.

The cheap durable fix, which I am not applying (I edit no file but this report): consult
`_LIKELY_DATABASE` on the sanctioned path too, and treat a message that matches BOTH as
unsanctioned. That makes the allowlist conjunctive without enumerating phrasings.

### F-4.14-RV-02 — MINOR — `_MINIMUM_TESTCASES = 500` is defensible in direction, near-useless in magnitude

`.github/scripts/assert_no_db_skips.py:127`.

Measured: the report carries 3843 test cases. The floor is 500, i.e. 13% of reality. It catches
total collection collapse and nothing else. Concretely, EVERY database-backed test in this
repository disappearing at collection is about 500 cases; the floor would still see 3300+ and pass.
The docstring's stated purpose ("well above zero so a collection failure does [trip it]") is met
only for a whole-suite collection failure, not for a directory-scale one. It is arbitrary in the
weak sense: no measurement ties 500 to anything. A floor derived from the drift-checked figure
`tracker/check_doc_drift.py` already computes (4107) would be a real populate-check; 500 is a
smoke alarm in the next building. Not a blocker, and the direction is right.

