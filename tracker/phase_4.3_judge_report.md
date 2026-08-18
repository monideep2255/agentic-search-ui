# Judge findings, build phase 4.3 (GraphQL adapter)

Dispatch started 2026-08-17. Append-only. Each finding carries file:line or pasted output.

Status: IN PROGRESS

## Baseline (recorded before any mutation)

`git status --short` at dispatch start, on `phase/4.3-graphql-api`:
```
 M tracker/BOARD.md
 M tracker/board.html
 M tracker/phase_4.3.md
```
Three files were ALREADY dirty before I touched anything. "Clean at finish" therefore means "back to exactly these three", not "zero".

Files read in full before any judgement: tracker/phase_4.3.md (300 lines), adapters/graphql/{types,fold,schema,security,context,router}.py.

---

# SECTION 2 FIRST (ran early because it is the perishable, machine-verifiable work)

Harness: `judge_sweep.py` in this scratchpad. 22 mutations over the 27 gate arms the lead's own
15-arm sweep never touched. Same discipline: edit the real source file, run the single arm,
restore byte-for-byte, assert the restore. `git status` verified clean afterwards (the three
tracker files that were dirty at my start were committed by the lead mid-run as 5c54b48; `git
diff --stat HEAD -- src tests` is empty).

Result: **22 mutations, 5 VACUOUS, 0 skipped.**

## J-01 (MAJOR) The citations-export disclosure arm cannot fail in the direction that matters

`TestDisclosuresSurvive::test_the_citations_export_carries_its_header_only_disclosures_as_fields`
stays GREEN under BOTH of these mutations:

```
src/system_03_search_agent/adapters/graphql/fold.py:571
-        export_truncated=citation_events_total > MAX_CITATIONS,
+        export_truncated=False,

src/system_03_search_agent/adapters/graphql/fold.py:572
-        run_cancelled=entry.cancelled,
+        run_cancelled=False,
```

Both stayed green. The arm only ever exercises a golden-path run and asserts:

```
tests/system_03_search_agent/adapters/graphql/test_phase_4_3_premise.py:1393-1395
        assert export["exportTruncated"] is False
        assert export["runCancelled"] is False
        assert export["citations"]
```

Every assertion is the NEGATIVE state. A fold that hardcodes both fields to `False` passes it.

Why this is major and not cosmetic: this arm is the one the phase premise names by name.
`tracker/phase_4.3.md:54` says "a citations export that the server already marked truncated ...
carry an explicit disclosure field. This closes on a new surface the gap
`X-Citations-Export-Truncated` currently fills with an HTTP response header, which GraphQL has no
channel for." The arm's own comment (test file, line ~1376) says its mutation is "drop
exportTruncated or runCancelled ... without explicit fields these two disclosures vanish silently
on this surface, which is exactly how F-4.0-A-12 went wrong once already." Dropping the FIELD
turns it red (the document would not validate). Making the field permanently lie does not. The
silent-vanish failure mode the arm was written for is precisely the one it does not detect.

Fix shape: a second arm that drives >MAX_CITATIONS citation events and a cancelled run, and
asserts `exportTruncated is True` / `runCancelled is True`.

## J-02 (MAJOR) The truncation arm's "must be named, not just flagged" assertion is satisfied by an unrelated note

```
src/system_03_search_agent/adapters/graphql/fold.py:412
-        answer_truncated = True
-        notes.append(
+        answer_truncated = True
+        [].append(
```
i.e. keep the flag, throw the truncation sentence away. Arm stayed GREEN.

```
tests/.../test_phase_4_3_premise.py:1333-1334
        assert data["disclosures"]["answerTruncated"] is True
        assert data["disclosures"]["notes"], "a truncation must be named, not just flagged"
```

`notes` is non-empty regardless, because the same fixture (`_oversized_answer_stream`) also
trips the citation-omission note at `fold.py:419`. So the assertion whose message says
"a truncation must be named" is satisfied by a note about citations. The flag half of the arm is
sound (`answer_truncated = False` DOES turn it red); the naming half is vacuous.

Fix shape: assert the truncation note's own substring, e.g. `any("truncated" in n and
"character limit" in n for n in notes)`.

## J-03 (MINOR) The concurrency-cap arm gates the wrong property

```
src/system_03_search_agent/core/run_registry.py:238
-DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER = 12
+DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER = 6
```
Arm `TestConcurrencyBound::test_the_concurrent_run_cap_is_not_the_free_allowance` stayed GREEN.
(Reverting to 5 does turn it red, so the arm is not fully vacuous.)

The arm is `assert DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER != FREE_RUN_ALLOWANCE` and nothing more.
But the phase file's own History row for this value (`tracker/phase_4.3.md:269`) claims the
value is load-bearing for a STRUCTURAL reason: "the builder set 12, ABOVE `ATTEMPT_ALLOWANCE`
(10), so a guest identity always hits the honest allowance refusal before it can hit the
concurrency cap. That is a structural fix to the ambiguous-refusal shape rather than an arbitrary
offset, and it is better than the brief asked for."

Nothing tests that. Any value != 5 passes, including 6, which is BELOW `ATTEMPT_ALLOWANCE` and
therefore reintroduces exactly the ambiguous-refusal shape the row says was structurally closed.
The property the phase is proudest of is ungated.

Fix shape: `assert DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER > ATTEMPT_ALLOWANCE`.

## J-04 (MINOR) `fold.py`'s own synthetic risk-tier fallback is ungated

```
src/system_03_search_agent/adapters/graphql/fold.py:374
-            risk_tier="unknown",
+            risk_tier="low",
```
Arm `TestRiskTierHonesty::test_a_refusal_reports_an_unassessed_risk_tier_as_unknown` stayed GREEN.

The arm drives `_guardrail_refusal_stream`, which emits a real answer-scope `trust_signal` from
the core, so `_finalize` takes the `acc.answer_trust_signal is not None` branch (fold.py:354) and
never reaches its own no-signal fallback at fold.py:360-379. That fallback is the branch where
this surface invents a trust signal from nothing, and it is exactly the F-4.1-J3-02 shape the
phase says it is closing. It is correct in the shipped code and is covered by no gate arm.

Note the asymmetry: the sibling arm `test_no_refusal_site_in_the_core_still_hardcodes_a_low_risk_
tier` greps `core/graph.py` for the literal, so the CORE is protected by a source grep while this
surface's own equivalent is not protected at all.

## Arms that DID turn red (17 of 22) - recorded so a later reader does not re-run them

grounding: cite-or-refuse floor dropped -> RED
grounding: claim trust first-wins -> RED
golden path: fold returns no citations -> RED
golden path: fold drops the answer text -> RED
ownership: registry owner comparison deleted -> RED
ownership: `Query.run` stops calling `_resolve_owned` -> RED
ownership: `stopRun` stops calling `_resolve_owned` -> RED
disclosure: answer truncated silently (flag off) -> RED
disclosure: citationsOmitted always zero -> RED
disclosure: fatal error interpolates raw internal message -> RED
cost: a `total_cost_usd` field added to AskResult -> RED
timeout: `app.add_middleware(RequestTimeoutMiddleware)` removed -> RED (so the arm proves the
   MIDDLEWARE, and confirms the schema-extension "second layer" does NOT in fact cover it, which
   matches F-4.3-L-05's account)
websocket: library subscription protocols restored -> RED (F-4.3-L-06's fix holds)
attribution: `trace_id` decoupled from the returned run id -> RED
cap: 12 -> 5 -> RED
cap: `str(exc)` at the GraphQL catch site -> RED
auth: guest refusal collapsed into the generic 401 -> RED

---

# SECTION 3: CITE-OR-REFUSE

Traced `fold.py`'s aggregation by hand and then drove it directly with hand-built event streams
(`judge_probe_grounding.py` in this scratchpad). I did not trust the docstring.

## The floor HOLDS. Verdict: PASS on the core question.

Three independent gates stand between "no citation" and "reported as grounded":

1. `fold.py:390-397`, the unconditional floor. It runs AFTER the trust-payload selection, so it
   overrides even an explicit answer-scope `trust_signal` claiming `outcome: "answer",
   grounded: true`. Proven by probe A:
   ```
   A: claims grounded, cites nothing
     outcome='refuse' grounded=False risk='low'
     citations=0
   ```
   Proven live, not just by reading: my mutation `if not acc.citations:` -> `if False:` turns
   `TestRefusalIsASuccess::test_an_uncited_answer_is_never_reported_as_grounded` RED.

2. `fold.py:375`, the synthetic-signal branch: `grounded=bool(acc.citations) and
   resolved_outcome == "answer"`. Cannot produce `grounded=True` with an empty list.

3. `contracts/events.py`'s `Event` model validates the citation payload AT CONSTRUCTION, so a
   citation with an off-host or control-byte `source_url` cannot enter the registry at all. I
   verified this directly: `Event(... type="citation", payload={... "source_url":
   "https://www.ncbi.nlm.nih.gov/gene/672\n" ...})` raises `ValidationError`. The host-pinned
   pattern is enforced twice (Event model, then `Citation.from_payload`'s `fullmatch` +
   full re-validation), and I could not construct a string that passes one and fails the other.

`_floor_trust_signal_for_fatal_error` and the floor both only ever LOWER a verdict
(`aggregate` takes the minimum severity, `grounded` is forced False, `risk_tier` forced "high").
There is no path in `_finalize` that raises a verdict.

## But three overstatement-adjacent defects fall out of the trace

## J-05 (MINOR, latent) The citation-omission note states a FALSE reason

`fold.py:417-423` computes `citations_omitted = citation_events_seen - len(citations)` and then
attributes EVERY omission to the cap:

```
fold.py:419-423
        notes.append(
            f"{citations_omitted} citation(s) beyond this surface's {MAX_CITATIONS}-"
            "citation limit were omitted; ..."
        )
```

But `citations` also loses entries to `_build_citation_from_event` returning `None` on a payload
that fails validation (`fold.py:275-283`). Probe C, driving 2 citation events of which one has an
off-host URL:

```
C: claims grounded, 1 of 2 citations dropped as off-host
  outcome='answer' grounded=True  citations=1  citationsOmitted=1
  notes=["1 citation(s) beyond this surface's 50-citation limit were omitted; ..."]
```

Two citations existed. The note claims a 50-citation limit was hit. It tells the caller the
surface has MORE evidence it withheld for capacity, when in fact the surface REJECTED that
evidence as untrustworthy. Those are opposite meanings on a trust surface, and the second is the
one a caller needs.

Reachability, stated honestly rather than inflated: I could not reach this through the real event
path, because `Event` validates the citation payload at construction (see gate 3 above), so
`_build_citation_from_event` can only return `None` for an event built via `model_construct` or by
a future producer that bypasses validation. It is a latent wrong-reason disclosure on a defensive
branch, not a live one. `adapters/web_sse/app.py:1186-1190` documents its own equivalent branch
the same way ("not expected to fire").

## J-06 (MINOR) `fold_citations` drops a rejected citation with `exportTruncated: false`, and has no field that could say otherwise

Probe E, 3 citation events, one off-host:
```
E: citations export with 1 of 3 dropped as off-host
  citations returned = 2 of 3 events
  exportTruncated = False
  runCancelled    = False
  -> CitationsExport fields: ['run_id', 'export_truncated', 'run_cancelled', 'citations']
```

`fold.py:571` sets `export_truncated = citation_events_total > MAX_CITATIONS` only. A
validation-dropped citation is logged and silently omitted, and `CitationsExport` carries no
`disclosures` field (unlike `AskResult`/`RunResult`, which do).

This is a direct miss against the premise clause at `tracker/phase_4.3.md:54`: "Anything the
surface drops or shortens, it says so."

Mitigation, and it is real: REST behaves IDENTICALLY
(`adapters/web_sse/app.py:1191-1216` sets `X-Citations-Export-Truncated` only on the count
comparison, and logs-and-omits an invalid payload). So this is an inherited gap, not a regression
this phase introduced, and closing it here would create the second-semantic divergence the phase
exists to avoid. Recorded as a premise-clause miss, not as a defect to fix inside this phase.

Interaction with J-01: the gate arm that exists for exactly this clause cannot see either
condition, because it only ever asserts the False state.

## J-07 (MINOR) `Query.run` on a mid-flight run reports a hard `refuse`, and says the run "ended"

`Query.run` is documented (`schema.py:190-193`) as "non-blocking by design ... so a caller can
poll". Polling is the ONLY way to observe an in-progress run on this surface, since scope
reading 3 declines subscriptions. Probe D, a run with one token event and nothing terminal:

```
D: mid-flight, tokens only, no done
  outcome='refuse' grounded=False risk='unknown'
```

And with no tokens yet, `_fallback_answer_text` (`fold.py:256`) returns the literal
"This query could not be completed: the run ended before producing an answer." on a run where
`RunResult.finished` is `False` in the very same response. The two fields contradict each other.

Direction of error is SAFE (understates, never overstates), so this is not a grounding defect.
It is a correctness/actionability defect on the one polling read the surface offers: every poll
of a healthy in-progress run returns `outcome: "refuse"` and a sentence asserting the run ended.
No gate arm covers `Query.run` against an UNFINISHED run: `test_a_caller_can_read_its_own_run`
asserts `finished is True`, i.e. it only ever polls a completed run.

## J-08 (MINOR) Asymmetric defensive posture inside the fold

`_consume_event` (`fold.py:307-345`) wraps ONLY the citation branch in a degrade-to-None handler.
`TokenPayload(**event.payload)`, `TrustSignalPayload(**event.payload)`, `GuardPayload(...)`,
`ErrorPayload(...)` and `DonePayload(...)` are all unguarded, so one malformed payload of any of
those five classes raises out of `fold_run` and is masked by `MaskErrors` into
"This request could not be completed due to an internal error." The whole answer is lost rather
than degraded. Same reachability caveat as J-05 (the `Event` model validates upstream), so latent.
Noting it because `fold.py:259-274`'s docstring argues at length for the defensive posture on
citations without saying why the other five branches do not get it.

---

# SECTION 4: THE SHARED-CONTRACT EDITS

Checked all four, and read every changed test file's diff specifically hunting for an assertion
that got LOOSER rather than updated.

## No weakened test found. This is the strongest part of the phase.

Mechanical proof, the whole diff's removed assertion-bearing lines:

```
$ git diff develop...HEAD -- 'tests/**' 'frontend/src/**test*' \
    | grep -E "^-" | grep -viE "^---" | grep -iE "assert|expect|parametrize|raises"
-    magnitude tighter, and the assertion is exact: the cap fires at     # docstring prose
-    @pytest.mark.parametrize("surface", ["web_ui", "rest_sse", "mcp", "cli"])
```

Exactly two hits, and neither is a weakening:
- The first is a docstring sentence, rewritten in place, not an assertion.
- The second is the `RequestContext.surface` parametrize list, replaced by the SAME list plus
  `"graphql"`. Additive. `tests/system_03_search_agent/contracts/test_query.py:104-112`.

`tests/system_03_search_agent/core/test_run_registry.py` (+174 lines, the largest test diff)
removes exactly one line in total, an import statement, and adds only new cases.

## Per-edit verdicts

### 1. `risk_tier="unknown"` at the refusal sites: OK, and consumers were actually checked

Both sites (`core/graph.py:3972`, `core/graph.py:4245`) are early-return refusal paths. I
confirmed by reading the surrounding control flow that NEITHER can co-occur with a claim-scoped
signal: `graph.py:3943-3989` returns before `claim_trusts` is ever built, and `graph.py:4236-4252`
sits in the `if trust_outcome == "refuse":` arm whose `else` is the only place claim signals are
emitted. So no run can emit both an "unknown" and a "high" signal today.

Consumers found and their disposition:
- `synthesis/trust.py:224` `if self.risk_tier == "low"` reads `ClaimTrust.risk_tier`, typed
  `RiskTier` (`trust.py:192`), a computed dataclass and not the emitted payload. Not on this path.
  The phase file's claim about this is correct.
- `contracts/events.py:246` types `risk_tier` as a bare `str(max_length=16)`, so "unknown" needs
  no type widening. Correct.
- `frontend/src/lib/events.ts:136,363` type-guards it as `typeof === "string"`. Unaffected.
- `frontend/src/hooks/useRunView.ts:463` updated, with a new two-armed test
  (`phase48Premise.test.tsx:442-488`) whose second arm proves a genuinely unrecognised tier
  ("critical") still over-reports. Good practice, not a weakening.

### J-09 (MINOR) A latent frontend interaction the edit creates but nothing tests

`useRunView.ts:427-434` ranks an unrecognised tier as MAX_SAFE_INTEGER, i.e. worst, deliberately
(F-4.8-A-19: over-report, never vanish). "unknown" is unrecognised, so it now ranks worse than
"high". Line 463 then EXCLUDES "unknown" from the pill. Composed:

  a run emitting both an "unknown" signal and a "high" signal reduces `worstRisk` to "unknown",
  which is then suppressed, so the "high risk claim" pill DISAPPEARS.

That is the exact vanish-not-over-report inversion F-4.8-A-19 was filed to prevent, reintroduced
by composition of the two rules. It is NOT reachable today, for the control-flow reason proved
above, and I state that rather than overclaiming. But it is reachable the moment any code path
emits an "unknown" tier alongside a claim-scoped one, and nothing in the suite would catch it.
The `phase48Premise.test.tsx` arm tests each rule alone, never the pair.
Fix shape: exclude "unknown" from `rank()` as well, not only from the pill.

### 2. Concurrency cap decoupled to 12: value correct, reasoning ungated

Verified: `core/run_registry.py:238` is 12, `data/guest_sessions.FREE_RUN_ALLOWANCE` is 5,
`ATTEMPT_ALLOWANCE` is 10. The structural claim (12 > 10, so a guest always hits the honest
allowance refusal first) holds in the shipped value. It is not gated: see J-03 above, a mutation
to 6 keeps the arm green.

Both existing catch sites updated to branch on the new `.bound` attribute, and BOTH keep a
`.get(..., fallback)` so an unknown future bound still produces the correct concurrency message
rather than a blank: `adapters/web_sse/app.py:299-310, 933-940` and `adapters/graphql/schema.py:
120-126, 254-259`. `ConcurrentRunCapExceededError.__init__` gained `bound` with a default, so no
existing raise site breaks. Backward compatible.

The REST wire `reason` string is deliberately unchanged (`concurrent_run_cap_exceeded`), with the
reasoning written at `app.py:914-930`: the frontend and CLI already key on it. Correct call, and
it means no existing consumer breaks.

### 3. `"graphql"` added to `RequestContext.surface`: OK

Additive enum member, v1-legal per `system-design-patterns.md` pattern 10. I re-ran the phase
file's claim that no second hand-maintained copy of the closed set exists and confirmed it:
grepping `frontend/src` for `riskTier|risk_tier|surface` turns up only
`frontend/src/stubs/registry.ts`'s unrelated feature-stub key. No second enum to widen.

### 4. `RunRegistry.resolve_owned_run` promoted out of `app.py`: OK, and mutation-proven

`app.py:957-976`'s `_get_owned_run` is now a pure two-error mapper; the unknown-before-ownership
ordering moved into the registry unchanged. I mutation-proved the rule is genuinely shared:
deleting `if entry.owner_id != owner_id:` in `core/run_registry.py` turns the GraphQL ownership
arm RED, and deleting `_resolve_owned(...)` from EITHER GraphQL resolver also turns its arm RED.
Three separate mutations, three reds. No second authorization rule was created.

---

# SECTION 5: RULES COMPLIANCE

## J-10 (MAJOR) Every caller-side input error on `ask` is reported as an internal error

This is my single most important finding, and it is live, trivially reachable, and a regression
against the surface this one mirrors.

`schema.py:227-235` builds `contracts.query.Query` inside the `ask` resolver. That model bounds
`text` (`min_length=1, max_length=2000`, plus a whitespace-only validator) and `session_id`
(`max_length=64`) at `contracts/query.py:30-31,45-63`. `AskInput` (`types.py:314-318`) declares
none of those bounds at the GraphQL layer, so a violating value passes GraphQL validation, reaches
the resolver, and raises `pydantic_core.ValidationError`.

`security.py:236-254`'s allowlist recognises an exception by the PACKAGE its class is defined in.
`pydantic_core._pydantic_core` is not under `adapters.graphql`, so the error is MASKED.

Measured end to end against the real mounted app (probe kept at `judge_probe_inputs.py` in this
scratchpad; it was created inside `tests/` to reuse the gate's own `_client`/`_real_user_headers`
helpers, then moved back out, and `git status` is verified empty):

```
### 2001 chars (max_length=2000):   HTTP 200  errors: ['This request could not be completed due to an internal error.']  codes: [None]
### empty string (min_length=1):    HTTP 200  errors: ['This request could not be completed due to an internal error.']  codes: [None]
### whitespace only:                HTTP 200  errors: ['This request could not be completed due to an internal error.']  codes: [None]
### sessionId 200 chars (max 64):   HTTP 200  errors: ['This request could not be completed due to an internal error.']
### create_run reached: 0
```

Four rules broken at once:

- `production-standards.md`, retry-safety gate: "Error messages must say what to do next, not just
  what failed. The agent loop reads the error and decides its next action." This says neither.
  It also actively misdirects: an INTERNAL error reads as transient, so a client's retry logic
  will retry a request that can never succeed until the caller shortens their question.
- `production-standards.md`, hardening: "No endpoint without input validation, tests (valid,
  invalid, null)". The 42-arm premise gate has NO invalid-input arm for `ask` at all. Every arm
  sends a well-formed input.
- `tool-call-budgets.md`: same actionability requirement.
- `production-standards.md`, multi-agent pipeline gate: "`maxLength` on every string field ... are
  required, not optional". `AskInput.text` and `AskInput.session_id` carry no bound at this
  surface's own boundary; the bound exists only one layer inward, where breaching it is a crash
  rather than a refusal.

REST does this correctly for the same input: `POST /v1/query` takes a Pydantic request model, so
FastAPI answers 422 with the offending field named. So this surface is strictly WORSE than the
one the phase premise says it mirrors ("gets back the same cited answer the REST surface produces
for the same question").

A biomedical question over 2000 characters is an entirely ordinary thing for a developer
integration to send. This is not an edge case.

Fix shape: catch `ValidationError` around the `CoreQuery(...)` construction and re-raise a
`SchemaError` subclass (which the allowlist then exposes with a stable code), naming the field
and the bound.

## J-11 (MINOR) The request body is unbounded

```
### 5MB variable body: HTTP 200 errors: ['This request could not be completed due to an internal error.']
```
`MaxTokensLimiter(1000)` bounds the DOCUMENT, not the `variables` object, so a 5MB string rides in
as a variable, is fully read, parsed and coerced before anything rejects it (and then rejects it
via J-10's masked path). Starlette applies no default body cap. `security.py`'s bounds table has
no entry for request size.

Genuinely build phase 6.0 territory (`tracker/phase_4.3.md:72` already disclaims load), so minor,
but the gate's coverage statement claims only that the NUMBERS are unproven under load, not that a
whole dimension (body size) is unbounded. See Section 6.

## Rules that PASS, with the evidence

- `tool-call-budgets.md`, declared timeout on every call path: `fold_run` carries
  `_FOLD_LOOP_TIMEOUT_S = 240.0` (`fold.py:130,471`); the whole operation carries
  `REQUEST_TIMEOUT_S = 270.0` enforced by `RequestTimeoutMiddleware` (`router.py:98-100`).
  I mutation-proved the middleware is the live enforcement point: commenting out
  `app.add_middleware(RequestTimeoutMiddleware)` turns the timeout arm RED, which also confirms
  the schema extension does NOT cover it, matching F-4.3-L-05's account. `fold_run_snapshot` and
  `fold_citations` do no I/O (bounded loops over a buffered list), so they need none.
- Host-pinned URLs: `Citation.source_url` is checked twice (`Event` model at construction, then
  `types.py:162`'s `fullmatch` plus a full `model_validate`). `TrustSignal.fallback_link` inherits
  `contracts/events.py:252-254`'s `pattern=NCBI_SOURCE_URL_PATTERN` and is re-validated by
  `TrustSignal.from_payload`. Both end-anchored, both host-pinned. I could not construct a string
  that passes one check and fails the other.
- `ai-security-standards.md`, least privilege / no second entry point: `schema.py` has four
  resolvers, none of which touches a tool. Every run goes through `default_registry.create_run`,
  the same one core. No per-tool resolver. Scope reading 1 is honoured in the code.
- `ai-security-standards.md`, human-approval and write actions: this surface is read plus
  create-run plus cancel-run only. No graph write path.
- `v1-scope-boundary.md`: NO violation. GraphQL is Section 25's own build phase 4.3 row. No BLAST,
  no sequence similarity, no VCF, no UCSC, no non-NCBI federation. Subscriptions were available
  (Strawberry supports them, `run_registry.subscribe()` is multi-consumer) and were deliberately
  NOT built, with the reasoning written down. That is the rule working as intended.
- `supply-chain-security.md`: `strawberry-graphql==0.324.0` pinned EXACTLY in both
  `pyproject.toml:41` and `requirements.txt:62`, package registered in the setuptools list. I ran
  `venv/bin/pip-audit -r requirements.txt` myself: "No known vulnerabilities found". The
  `cross-web` transitive widening is named rather than absorbed silently.
- `git-workflow.md`: seven commits, all Conventional Commits with correct types and scopes; zero
  `Co-authored-by` trailers (`git log develop..HEAD --format=%b | grep -ci` returns 0).
- `writing-style.md`: zero em or en dashes across all six new modules and `tracker/phase_4.3.md`.
- `dependency-tracking.md`: all six modules carry the `Depends on:` / `Reads:` / `Writes:`
  docstring blocks.
- `ruff check`: 18 findings repo-wide, ALL pre-existing and NONE in this phase's files (they sit
  in `.claude/skills/skill-adapt-verify/`, `tests/system_03_search_agent/tools/`, and `tracker/`).
- Batching: I probed a JSON-array body directly. `HTTP 400 "Batching is not enabled"`. So the
  one-run-per-document bound cannot be bypassed at the HTTP layer either, which the gate never
  checks but which holds by the library default (`StrawberryConfig.batching_config is None`).
- GET refused: probed, `HTTP 400`.

## Environment note, NOT a phase defect

The full suite is `6 failed, 3005 passed, 113 skipped, 1 xfailed`. All six failures are in
`tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py`, all carry the
`@live_only` marker, and all fail on `graph=error live=error` because the Hetzner tunnel and NCBI
are unreachable from this sandbox. The file is untouched by this phase's diff. Recorded because a
`/verify` or `/release-workflow` gate run will report a red suite, and someone should know why
before reading it as this phase's fault.

---

# SECTION 1: THE PHASE PREMISE, GRADED CLAUSE BY CLAUSE

Graded against the ASSEMBLED SURFACE, not the tickets. `tracker/phase_4.3.md` lines 48 to 64.

| # | Clause (source line) | Verdict |
|---|---|---|
| C1 | registered caller POSTs to `/graphql`, gets the same cited answer REST produces, HTTP 200, no `errors` (48) | PARTIAL |
| C2 | `trustSignal`, `citations` field-for-field, host-pinned `sourceUrl`, `runId` (50) | MET |
| C3 | a guardrail refusal is a successful response, never a transport error (50) | MET |
| C4 | no cost figure ever reaches this surface; `operator_mode` pinned False; no field to select one into (52) | MET |
| C5 | anything the surface drops or shortens, it says so (54) | NOT MET |
| C6 | the schema is bounded against a hostile DOCUMENT; one document never starts many runs (56) | PARTIAL |
| C7 | a run is owned by its creator; ownership reuses `_get_owned_run`'s rule, not a second one (58) | MET |
| C8 | the withdrawn existence-oracle claim (60) | MET (honestly handled) |
| C9 | every run is attributed `surface="graphql"`, never `rest_sse` (62) | MET |
| C10 | "Every clause is mutation-proven" (64) | NOT MET |

## C1, PARTIAL

Met for a well-formed request. Two gaps:

- "the same cited answer the REST surface produces for the same question" is asserted by NO arm.
  There is no cross-surface equivalence test anywhere: the gate fakes an event stream and folds
  it, and the REST gate folds its own separately. Nothing would catch the two surfaces diverging
  on the same stream. Given F-4.3-L-02 already records that the fold logic is DUPLICATED rather
  than shared, this is the exact divergence the duplication makes likely, and the premise's own
  equivalence claim is the thing not tested.
- For a malformed request, this surface is measurably WORSE than REST, not the same: J-10.

## C5, NOT MET

Three distinct holes, in order of how much they matter:

1. J-06: `fold_citations` drops a citation that fails validation and reports
   `exportTruncated: false`, with no field on `CitationsExport` that could say otherwise.
   Mitigated by REST behaving identically, so this is inherited rather than introduced.
2. J-05: when the note DOES fire, it attributes every omission to the 50-citation cap, including
   omissions caused by a rejected payload. Latent (see Section 3 for the reachability argument),
   but it is a false statement on the trust surface.
3. `fold.py:437` caps `notes[:MAX_DISCLOSURE_NOTES]` and `fold.py:235` caps the merged
   `trust_signal.message` at 500 characters. Both silently drop DISCLOSURES. A surface whose
   premise is "if we drop something we say so" truncates its own saying-so undisclosed. Latent
   today (at most three notes exist), and the full text does survive in `disclosures.notes` even
   when the `message` copy is cut, so it is the mildest of the three.

And the arm that exists for this clause cannot fail in the direction that matters (J-01).

## C6, PARTIAL

The four named vectors (depth, aliases, tokens, run-creating fields) are all enforced before
execution, at the validation phase, and I mutation-proved the alias, token, one-run and
subscription bounds turn their arms red. Batching is off by library default, verified by probe
(`HTTP 400 "Batching is not enabled"`), so one HTTP request cannot start many runs either.

Two qualifications:

- The depth bound is not a control. `MAX_QUERY_DEPTH = 10` but the deepest LEGAL document on this
  schema nests about 3, because no type is self-referential. Already open as F-4.3-L-10 and I
  confirm it: the clause claims a bound that no valid document can approach.
- "bounded against a hostile DOCUMENT, not only against a hostile value" is the clause's own
  framing, and the hostile REQUEST is not bounded at all: a 5MB `variables` payload is read,
  parsed and coerced with nothing rejecting it on size (J-11).

## C10, NOT MET, and this is the most important line in Section 1

`tracker/phase_4.3.md:64`: "Every clause is mutation-proven: for each, the mutation that turns it
red is named in the test file beside the clause."

Two sweeps have now run against 33 of the 42 arms, disjointly (the lead's 15, my 18). Between
them they found **9 vacuous arms**: the lead's 4 (F-4.3-L-09) plus F-4.3-L-06, and my 5 (J-01 x2,
J-02, J-03, J-04). That is a ~27 percent vacuity rate among the arms anyone has actually checked.

The claim was never true when written, and it is still not true now. Nine arms remain
mutation-unchecked; several of those are deliberate control arms whose job is to pass
(`test_a_caller_can_read_its_own_run`, `test_a_single_ask_document_still_works`,
`test_a_real_ncbi_source_url_is_accepted`, `test_an_untruncated_answer_does_not_claim_truncation`)
and are fine, but these five are not, and nobody has checked them:

- `TestGoldenPath::test_internal_step_events_are_folded_out_entirely`
- `TestRefusalIsASuccess::test_a_guardrail_refusal_is_http_200_with_no_errors_array`
- `TestAuth::test_a_missing_token_never_reaches_the_core`
- `TestAuth::test_an_invalid_token_is_refused`
- `TestConcurrencyBound::test_the_cap_refusal_names_which_bound_was_hit`

The honest statement the phase file should carry instead: "33 of 42 arms have been
mutation-checked across two sweeps; 9 were found vacuous and fixed; 9 arms remain unchecked, of
which 4 are deliberate control arms."

## C2, C3, C4, C7, C9: MET, with evidence

- C2: verified mechanically, not by eye. `CitationPayload` has 14 fields and `Citation` publishes
  exactly 14, no missing, no extra. `TrustSignalPayload` has 8 and `TrustSignal` publishes 8, no
  missing, no extra. `sourceUrl` is host-pinned end-anchored, enforced twice.
- C4: my mutation adding a `total_cost_usd` field to `AskResult` turns the schema-grep arm RED,
  and the lead's two mutations (unpin `operator_mode`, skip the sanitizer) were already checked.
  Three independent protections: the sanitizer, the pinned `operator_mode`, and the absence of any
  field to select into.
- C7: three separate mutations, three reds (registry comparison, `Query.run`'s call, `stopRun`'s
  call). The rule genuinely lives in one place and both surfaces genuinely reach it.
- C9: mutation to `rest_sse` turns the attribution arm red.

---

# SECTION 6: WHAT WOULD THIS GATE MISS?

The gate's declared coverage gaps (`test_phase_4_3_premise.py:44-66`, restated at
`tracker/phase_4.3.md:66-75`) are six: no live model or graph, no real socket, no load, no
persisted queries, no client library, no subscriptions. Every one of those is honest and
accurate. Two of them are even stated more carefully than usual, e.g. "this gate would pass with
numbers that are far too generous, as long as they bound something."

But the declaration is INCOMPLETE, and it is incomplete in the direction that matters: it names
what the gate does not RUN, and says nothing about what the gate does not ASSERT on the things it
does run. Four whole shapes of defect are invisible to both the gate and both mutation sweeps.

## Shape 1: assertions only ever exercised in their false/negative state

Neither the gate's coverage note nor either sweep can see this class, because a mutation sweep
only asks "does the arm turn red when I break the thing", and an arm that pins a boolean to
`False` on a golden path turns red for the wrong reason (a dropped FIELD) while staying green for
the right one (a field that always lies). This is the class J-01 belongs to.

The gate has no arm anywhere that drives `exportTruncated: true`, `runCancelled: true`, or a
cancelled run through `citations`. Every disclosure boolean on `CitationsExport` is asserted only
as `False`. The test to write is a coverage audit, not another mutation: for every boolean field
the surface publishes, is there an arm that observes it in BOTH states?

## Shape 2: invalid input, on every operation

Stated plainly because it is a whole quadrant, not one case: all 42 arms send WELL-FORMED input.
There is not one arm that sends an out-of-bounds `text`, an empty `text`, an over-length
`sessionId`, a malformed `runId`, or an unknown `audienceDepth` value. `production-standards.md`
names "tests (valid, invalid, null)" as the minimum bar and the gate covers only the first.
J-10 is what lived in that quadrant, and it is a live defect that both sweeps and 42 green arms
walked straight past.

## Shape 3: the surface's own non-terminal states

`Query.run` is the surface's only polling read, and the only arm that exercises it
(`test_a_caller_can_read_its_own_run`) asserts `finished is True`. The gate never once polls an
in-progress run, which is the entire reason the operation exists. J-07 lives here.
Same shape for `citations` on an unfinished run: not in the gate (I had to probe it by hand; it
behaves correctly, returning `RUN_NOT_YET_FINISHED_ERROR`, but no arm holds that).

## Shape 4: composition of two individually-tested rules

Each rule tested alone, the pair untested. J-09 is the measured instance: `useRunView.ts` ranks an
unrecognised tier as worst (tested), and excludes "unknown" from the pill (tested), and the
composition makes a "high" pill vanish (untested, and it is the exact inversion F-4.8-A-19 was
filed to prevent). Neither arm can see it because each holds one rule fixed.

## What the gate's own coverage note should say, added

Beyond the six already listed:

- Invalid, out-of-bounds and null inputs on every operation. Not exercised at all.
- Request-body size. Bounded by nothing; the token limiter bounds the document, not `variables`.
- Non-terminal run states through `run` and `citations`. Only terminal states are driven.
- Every disclosure boolean is observed in one state only.
- Cross-surface equivalence with REST, which the premise's first sentence explicitly claims.
- HTTP-level batching. It is off by library default, not by anything this phase configured or
  asserts, so a future `StrawberryConfig` edit that enables it would silently defeat the
  one-run-per-document bound with no arm turning red.

## Answering the rule's own test

`goal-contracts.md`: "if someone asked 'what would this gate miss', could they answer from the
gate itself?" Partly. They would correctly answer "live model, socket, load, persisted queries,
clients, subscriptions". They would NOT answer "any invalid input at all", which is where the one
live major defect in this phase actually sits. The declaration lists the environments it cannot
reach and omits the inputs it chose not to send.

---

# SUMMARY

VERDICT: FAIL.

Counts: 2 major (J-01, J-02 are gate-vacuity majors; J-10 is the code major) => **3 major**,
8 minor (J-03, J-04, J-05, J-06, J-07, J-08, J-09, J-11), 0 blocking-critical.

Single most important reason to fail: **J-10.** Every caller-side input error on the `ask`
mutation (a question over 2000 characters, an empty question, an over-length session id) is
returned as `"This request could not be completed due to an internal error."` with no error code.
It is live, it is on the ordinary path, it breaks `production-standards.md`'s retry-safety gate
and the multi-agent schema-bounds gate, and it makes this surface strictly worse than the REST
surface the phase premise claims it matches. The 42-arm gate cannot see it because not one arm
sends invalid input.

Second reason, and the one that generalises: the phase premise's claim that "every clause is
mutation-proven" is false. Two disjoint sweeps have now checked 33 of 42 arms and found 9 vacuous
between them. The vacuity rate among checked arms is about 27 percent, and my 5 were found after
the lead had already fixed 5 and written the discipline up as a closed finding.

What is genuinely strong, and should be said: the cite-or-refuse floor holds under direct probing
and under mutation; ownership is one rule reached by both surfaces and mutation-proven three
different ways; the cost bound has three independent layers; no test anywhere in the diff was
weakened; the supply-chain work is real (exact pin, `pip-audit` clean when I ran it myself, the
transitive widening named); and the v1 scope boundary was respected in the one place it was
tempting to cross (subscriptions were available and were not built).

`git status`: CLEAN. `git status --porcelain --untracked-files=all` returns empty. Every mutation
was restored byte-for-byte with the restore asserted, and the one temporary probe file created
inside `tests/` was moved back out to the scratchpad (the `block-bash-delete.sh` hook correctly
refused `rm`, so it was moved rather than deleted).
