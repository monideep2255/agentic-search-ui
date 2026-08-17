# Adversary findings, build phase 4.3 (GraphQL surface)

Branch: phase/4.3-graphql-api. Started: 2026-08-17 15:09:43.
Append-only. Each finding written the moment it is found.

## Attack 1, the money bound: result summary (no critical found on the primary bound)

Probe: `a1_money.py` in this scratchpad. Every case counts real
`default_registry.create_run` invocations by wrapping it, and drives the real
app over `ASGITransport` with a real signed-up user.

| Vector | HTTP | create_run calls | Verdict |
|---|---|---|---|
| baseline single `ask` | 200 | 1 | correct |
| two aliased `ask` in one operation | 200 | 0 | refused, `TOO_MANY_RUN_CREATING_FIELDS` |
| two operations + `operationName` | 200 | 0 | refused |
| two fragment spreads | 200 | 0 | refused |
| nested fragments | 200 | 0 | refused |
| inline fragments | 200 | 0 | refused |
| same fragment spread twice | 200 | 0 | refused |
| same fragment twice under two inline fragments | 200 | 0 | refused |
| batched JSON array body | 400 | 0 | "Batching is not enabled" |
| duplicated JSON `query` keys | 200 | 0 | refused (last key wins, still counted) |
| GET with `query` param | 400 | 0 | "mutations are not allowed when using GET" |
| multipart body | 400 | 0 | "Unsupported content type" |
| `__typename` aliasing beside `ask` | 200 | 1 | correct |
| `@skip(if:true)` on one of two `ask` | 200 | 0 | refused (counts skipped field too) |

ONE HTTP REQUEST STARTING TWO RUNS: not achieved by any of the above. The
validation rule counts by field NAME across every operation and every
fragment in the document, before execution, so it is not alias-evadable,
fragment-evadable, or operationName-evadable. This is the phase's strongest
control and it holds.

Residual concerns filed separately below (orphaned billed runs on
disconnect/timeout, and a serve-cost recursion issue).

## Attack 2, honesty. Findings.

Probe: `a2_honesty.py`. Each case monkeypatches
`system_03_search_agent.core.run_registry.run_streaming` with a hostile
event stream, then POSTs the full `ask` document as a real registered user
and reads the real HTTP response body.

Run it with:
`cd <repo> && PYTHONPATH=src venv/bin/python <scratchpad>/a2_honesty.py`

---

### F-4.3-A-02 major CONFIRMED (filed critical, downgraded to major by my own later reachability check, see "Correction to F-4.3-A-02's reachability" near the end): a `trust_signal` with `scope=None` is silently discarded, and its warning is replaced with a more reassuring synthetic one

`fold.py:332-337` (`_consume_event`):

```python
elif event.type == "trust_signal":
    candidate = TrustSignalPayload(**event.payload)
    if candidate.scope == "answer":
        acc.answer_trust_signal = candidate
    elif candidate.scope == "claim":
        acc.claim_trust_signals.append(candidate)
```

`TrustSignalPayload.scope` is `Literal["claim","answer"] | None = None`
(`contracts/events.py:250`) and DEFAULTS TO NONE. A signal with no scope
matches neither branch and is dropped on the floor. The fold then falls
through to its synthetic branch (`fold.py:360-379`) and manufactures a
signal from `done.trust_outcome`.

Repro, probe case `2-trust-signal-scope-none`. The run emitted exactly one
trust assessment:

```python
TrustSignalPayload(outcome="flag", risk_tier="high", grounded=False,
                   triangulated=False, citation_id=None, scope=None,
                   message="this answer contradicts its sources")
```

Observed response:
```
outcome=answer risk=unknown grounded=True cites=1 notes=0 msg=None
answer: 'A dangerous claim [1].'
```

The system said: FLAG, HIGH RISK, NOT GROUNDED, "this answer contradicts
its sources". The caller was told: ANSWER, GROUNDED, no message. Every
field moved in the reassuring direction, and the warning text was deleted.

Why it matters: this is the single worst shape available on this surface,
a `trustSignal` that overstates what happened, on a system whose entire
moat is that its trust signal is honest. The drop is silent: no note, no
`errors` entry, nothing in `disclosures`. It fails open.

Severity note: reachability turns on whether any producer emits a
scope-less signal. `scope` is optional with a None default precisely so
payloads predating build phase 2.2 validate unchanged
(`contracts/events.py:218-223`), so a scope-less signal is a
contract-legal event that this surface must handle and does not. The MCP
sibling should be checked for the same shape. Rated critical because the
failure direction is "silently upgrade a flagged refusal into a grounded
answer"; downgrade to major if every producer is shown to always set
`scope`.

---

### F-4.3-A-01 major CONFIRMED: a claim-scoped `risk_tier` of `"unknown"` is silently reported as `"low"`

`fold.py:178-180` (`_aggregate_claim_trust_signals`):

```python
risk_tier: Literal["low", "high"] = (
    "high" if any(signal.risk_tier == "high" for signal in claim_signals) else "low"
)
```

`TrustSignalPayload.risk_tier` is `str` (`contracts/events.py:246`), NOT a
two-value Literal. Anything that is not the exact string `"high"` collapses
to `"low"`, including the value `"unknown"` THIS PHASE ITSELF INTRODUCED as
the honest "no assessment ran" marker (T-4.3-05, `core/graph.py`, and
`fold.py:374`'s own synthetic branch).

Repro, probe case `1-claim-risk-unknown-aggregated`: two claim-scoped
signals, each `risk_tier="unknown"`, no answer-scope signal.

Observed:
```
outcome=answer risk=low grounded=True cites=2
```

Expected: `riskTier` no better than `"unknown"`.

Why it matters: this is exactly the defect the phase file says it folded a
fix in for ("Report `risk_tier` as `unknown` rather than a hardcoded `low`
when no assessment ran"), reintroduced one function away through the
aggregation path. The phase fixed the two refusal sites in `core/graph.py`
and left the aggregator that consumes the same field converting `unknown`
into a reassuring `low`. A caller reading `riskTier: "low"` on a biomedical
answer is being told a risk assessment ran and cleared it. None ran.

The same line is a general downgrade, not only an `unknown` bug: any future
tier value (`"medium"`, `"critical"`) also becomes `"low"`. The floor
should be "worst wins over an ordered severity map", the way the sibling
field `triangulated` is already handled three lines below via
`_TRIANGULATION_SEVERITY`. In one function, `risk_tier` got a boolean
special case and `triangulated` got a severity map.

---

### F-4.3-A-03 major CONFIRMED: `grounded: true` is asserted when no grounding assessment ran at all

`fold.py:375`, inside the branch taken when NO `trust_signal` event of any
scope arrived:

```python
grounded=bool(acc.citations) and resolved_outcome == "answer",
```

Repro, probe case `7-done-with-no-trust-signal`: guard, one token, one
citation, `done(trust_outcome="answer")`, and no trust signal.

Observed: `outcome=answer risk=unknown grounded=True`.

Why it matters: `risk_tier` on the line immediately above is set to
`"unknown"` with a six-line comment explaining that asserting a value when
no assessment ran is F-4.1-J3-02's defect. Then the very next line asserts
`grounded=True` from nothing but "at least one citation event went past".
"A citation exists" is not "the answer is grounded in it"; that inference
is exactly the check the grounding step performs and this run never
performed. The honest value is `grounded=False`, or an `unknown` tri-state
matching what was just done for `risk_tier`.

The two lines contradict each other inside one object literal, which is why
this is worth reporting even though the direction feels small: the
principle was applied to one field and not to its neighbour.

---

### F-4.3-A-04 major CONFIRMED: a non-fatal `error` event is dropped with no disclosure

`fold.py:340-343`:

```python
elif event.type == "error":
    payload = ErrorPayload(**event.payload)
    if payload.fatal:
        acc.fatal_error_payload = payload
```

A non-fatal error is consumed and thrown away. Nothing reaches
`disclosures.notes`, `trust_signal.message`, or the answer text.

Repro, probe case `3-nonfatal-error-undisclosed`: a tool-scope
`ErrorPayload(fatal=False, source="cypher_query", error_class="transient",
message="graph unreachable, layer 1 skipped")` mid-run, then a normal
cited answer.

Observed: `outcome=answer risk=low grounded=True cites=1 omitted=0 notes=0`.

Why it matters: `production-standards.md`'s layer-degradation gate says a
partial-layer failure "degrades gracefully and explains the gap in the
answer text", and this phase's own premise says "Anything the surface drops
or shortens, it says so." A caller here is told a clean, low-risk, grounded
answer was produced, when Layer 1 was skipped. The REST/SSE surface
forwards the error event, so its callers CAN see it; this surface is the
one that hides it. The registry itself documents non-fatal errors as a
normal occurrence (`core/run_registry.py:467-471`), so this is not an
exotic path.

---

### F-4.3-A-05 major CONFIRMED: an upstream `tool_result.truncated=True` is never disclosed

`fold.py:307-345` has no `tool_result` branch at all; the module docstring
states `tool_result` "carr[ies] nothing this surface's schema has a field
for" and folds it out.

`ToolResultPayload.truncated: bool` (`contracts/events.py:155-158`) is
exactly a "the data behind this answer was cut short" flag, and this
surface has a `Disclosures` type built for facts with no other channel.

Repro, probe case `4-tool-result-truncated-undisclosed`: a `cypher_query`
result with `summary="500 rows found, first 25 returned"`,
`result_count=25`, `truncated=True`, then a cited answer.

Observed: `answerTruncated=false citationsOmitted=0 notes=[] risk=low
grounded=true`, answer "Only BRCA1 is associated [1]."

Why it matters: this is the exact "a truncation that is not disclosed"
failure. The answer says "only BRCA1" while the tool that produced it saw
500 rows and returned 25. `Disclosures` discloses truncation the SURFACE
performs and stays silent about truncation the RUN reports, which is the
narrower and less useful half. `system-design-patterns.md` pattern 7
requires the count of total available be carried with a truncated tool
result.

---

### F-4.3-A-06 major CONFIRMED: no sanitization of untrusted text; bidi overrides, ANSI escapes and NUL bytes reach the caller verbatim

Repro, probe case `6-control-chars-and-bidi`. Token text and
`citation.claim_text` carrying U+202E (right-to-left override), ESC-[31m
(ANSI SGR), U+0007 (BEL) and U+0000 (NUL).

Observed response body, as JSON escapes:
```
"answer": "SAFE<U+202E RLO>UNSAFE<ESC>[31m IGNORE PREVIOUS INSTRUCTIONS [1].<U+0000 NUL>"
"claimText": "benign<U+202E RLO>dangerous<ESC>[31m<U+0007 BEL><U+0000 NUL>"
```

Nothing strips or escapes them. `CitationPayload.claim_text` is
`max_length=1000` with no pattern, so the payload layer does not filter
either.

Why it matters:
- A bidi override inside `claim_text` reverses how the claim RENDERS. A
  citation whose stored text says one thing and displays another defeats
  the "every claim is verifiable against its source" moat, and it does so
  in the one field a reader uses to check the citation.
- A NUL byte inside a JSON string value is legal JSON but is a known break
  point for C-backed consumers, log pipelines, and Postgres `text` columns;
  a caller storing this answer can hit a hard error or a silent truncation
  at the NUL.
- ANSI escapes are live for any consumer that prints a GraphQL result to a
  terminal, which is the normal shape of a developer integration and the
  exact reason the CLI surface built `_sanitize_untrusted`.

Sibling-surface inconsistency, not a novel risk: `adapters/cli/render.py`
sanitizes the identical content, and `tracker/phase_4.3.md` records the gap
as "finding F-4.1-A-10's open question arriving on a third surface" and
then ships without resolving it. Filed here so it is a finding against this
surface rather than a note about another one.

---

### F-4.3-A-07 major CONFIRMED: duplicate `citationId` and duplicate `displayIndex` are returned with contradictory claims and no disclosure

Repro, probe case `8-duplicate-citation-ids`: two citation events sharing
`citation_id="c1"` and `display_index=1`, with opposite claim text.

Observed:
```json
"citations": [
 {"citationId":"c1","displayIndex":1,"claimText":"BRCA1 causes cancer",
  "sourceUrl":"https://www.ncbi.nlm.nih.gov/gene/671"},
 {"citationId":"c1","displayIndex":1,"claimText":"BRCA1 does NOT cause cancer",
  "sourceUrl":"https://www.ncbi.nlm.nih.gov/gene/9999"}
]
```
answer `"Fact [1]."`, `citationsOmitted: 0`, `notes: []`.

Why it matters: this is "citations attributed to claims they do not
support", reachable without any hostile URL. The marker `[1]` in the answer
now resolves to two different sources making opposite assertions, and the
caller has no way to pick. `citation_id` is documented as the join key
between a trust signal and its citation (`contracts/events.py:224-229`), so
a duplicated id also makes per-claim trust attribution ambiguous: a
claim-scoped signal naming `citation_id "c1"` cannot be bound to one
citation. Nothing in the fold dedupes by `citation_id`, checks
`display_index` uniqueness, or discloses a collision.

---

### F-4.3-A-08 major CONFIRMED: a run that ends without a terminal event is reported as an ordinary refusal, carrying partial answer text and no disclosure

Found by accident, then reproduced deliberately: an exception raised inside
`run_streaming` (rather than a fatal `error` event) ends the run.
`core/run_registry.py:637-648` sets `entry.finished = True` in a `finally`
and appends NO error event on that path; only `asyncio.CancelledError` gets
a synthesized cancellation event. `fold_run`'s `async for` over `subscribe`
then simply ends.

`_finalize` has no notion of "did a terminal event actually arrive". With
some tokens already consumed, the caller receives the partial answer text
plus `outcome=refuse, grounded=false, risk=unknown, notes=[]`, which is
identical in shape to a legitimate guardrail refusal that produced no
answer.

Observed (probe case `5-all-citations-malformed`, whose stream raises at
its second event):
```
outcome=refuse risk=unknown grounded=False cites=0 omitted=0 notes=0
answer: 'Fact one [1]. Fact two [2].'
```
A partial answer body carrying two dangling citation markers, zero
citations, and an affirmative `citationsOmitted: 0`.

Why it matters: the caller cannot distinguish "the system declined to
answer" from "the system died halfway and handed you half an answer". The
`answer` field is populated with unvouched partial text WHILE `outcome`
says refuse, and `citationsOmitted: 0` is a positive false statement about
a body that visibly cites `[1]` and `[2]`. The fold should require a
terminal event (`done`, or a fatal `error`) and disclose its absence.

CONFIRMED for the behaviour. The trigger used here (a raising
`run_streaming`) contradicts that function's documented contract, so treat
the LIKELIHOOD as lower than the other findings in this section while the
failure SHAPE is the worst of them.

---

### Attack 2 cases that behaved correctly

Recorded so this pass's coverage is arguable, per `goal-contracts.md`.

- 2000 citation events: capped at 50, `disclosures.citationsOmitted` and
  `trust_signal.message` both state 1950 omitted, accurately.
- Empty run (a lone `done`): refuse, grounded false, no fabricated answer.
- Events after `done`: the fold stops at the terminal event rather than
  folding post-terminal content.
- The cite-or-refuse floor (`fold.py:390-397`) correctly overrode an
  answer-scope signal claiming `outcome="answer", grounded=true` on a run
  with zero usable citations.
- An off-host `source_url` is rejected by `Citation.from_payload`'s
  `fullmatch` (see F-4.3-A-09 for the disclosure that misattributes why).

## Attack 3, auth and ownership: result summary (no critical found)

Probe: `a3_auth.py`. Two real accounts signed up through `/auth/signup` and
`/auth/login`; A creates a run, B attacks it.

| Vector | HTTP | Verdict |
|---|---|---|
| no `Authorization` header | 401 | generic "invalid or expired credentials" |
| valid guest token | 403 | actionable guest-specific refusal, distinct from 401 |
| `bearer` lowercase scheme | 200 | accepted (intended, matches REST) |
| `BeArEr` mixed case | 200 | accepted (intended) |
| leading whitespace before `Bearer` | 401 | refused |
| `Bearer\t<token>` | 401 | refused |
| `Bearer  <token>` (double space) | 200 | accepted, token stripped |
| `Bearer <token>   ` trailing space | 200 | accepted, token stripped |
| `Bearer<token>` no separator | 401 | refused |
| `Basic <token>` | 401 | refused |
| garbage token / empty token | 401 | refused |
| two identical `Authorization` headers | 401 | treated as absent, per the MCP precedent |
| good + bogus `Authorization` headers, either order | 401 | treated as absent, no first-wins or last-wins |
| token in a cookie | 401 | not accepted from a cookie |
| token in a query parameter | 401 | not accepted from a query parameter |

Ownership, B attacking A's run id:

| Operation | Result |
|---|---|
| `run(runId:)` | `RUN_NOT_OWNED`, `data: null` |
| `citations(runId:)` | `RUN_NOT_OWNED`, `data: null` |
| `stopRun(runId:)` | `RUN_NOT_OWNED`, run not stopped |
| unknown run id | `RUN_NOT_FOUND` (the accepted F-4.3-L-01 oracle) |

The whole serialized body was searched for A's answer text, A's entity
names and A's namespaced owner id on every refusal. No leak. Run ids shaped
as `' OR 1=1 --`, `../../etc/passwd`, a 5000-character string, an empty
string and a NUL-prefixed string all resolve to a clean `RUN_NOT_FOUND`.

---

## Attack 4, leakage and cost: result summary

ANY dollar figure, token count or cost field reaching a caller: NONE FOUND.
`totalCostUsd` and `cost` are both rejected as non-existent fields on
`AskResult`; the fold drops `cost` events and redacts `done.total_cost_usd`
through `sanitize_event_for_end_user`; `operator_mode` is pinned `False` in
`schema.py:246` with no path to unpin it. This is the phase's second
strongest control and it holds.

Internal text: a `RuntimeError` carrying a live-looking DSN
(`46.225.128.133 port 5432 ... user 'kg_reader'`) raised from inside
`fold.fold_run` surfaced to the caller as exactly
`"This request could not be completed due to an internal error."` with no
`code`, no host, no port, no username, no stack frame, no file path and no
library version. `MaskErrors` is doing its job on the default path.

Introspection is off and field suggestions are off: a misspelled `answr`
returns `Cannot query field 'answr' on type 'AskResult'.` with no "Did you
mean" clause.

Findings below.

---

### F-4.3-A-09 minor CONFIRMED: validation errors publish schema type names, so the schema is enumerable field by field despite introspection being disabled

Repro, from `a3_auth.py`'s schema-probe block:

```
mutation A($input: AskInput!) { ask(input: $input) { totalCostUsd } }
-> {"errors":[{"message":"Cannot query field 'totalCostUsd' on type 'AskResult'."}]}

query { runn(runId: "x") { runId } }
-> {"errors":[{"message":"Cannot query field 'runn' on type 'Query'."}]}
```

Why it matters: `DisableIntrospection` and `disable_field_suggestions=True`
are both on, and the phase file treats the pair as closing the schema
("a lock on the front door and an open window"). They close the CHEAP
enumeration, not enumeration itself. The validation error still confirms or
denies each guessed field name AND names the owning type, so a caller can
still walk the schema by brute force at one request per guess, learning
`AskResult`, `Query`, `Mutation` and every field on them.

This is graphql-core behaviour, not a defect the builders introduced, and
closing it fully means masking validation errors too, which would break the
actionability this surface deliberately preserves. Filed as minor and as a
COVERAGE GAP in the phase's own claim rather than as a bug: the phase file
says introspection is off, and should also say what remains derivable.

Related: there is no rate limit on this surface (build phase 6.0's
territory per the gate's own coverage note), so a brute-force schema walk is
currently unthrottled. Worth carrying into 6.0's scope.

---

### F-4.3-A-10 minor CONFIRMED: `POST /graphql/` (trailing slash) 307-redirects, and the redirect drops the request body

Repro:
```
POST /graphql/  ->  307, empty body
POST /graphql   ->  200
POST /graphql?x=1 -> 200
POST /GRAPHQL   ->  404
POST /graphqlXYZ -> 404
POST //graphql  ->  404
```

Why it matters: `tracker/phase_4.3.md`'s own history records this exact trap
("`app.mount` gives the sub-app its own path space, so a bare `POST
/graphql` 307-redirected, the identical trailing-slash trap `app.py` already
documents for the MCP mount") and records fixing it in the bare direction.
The mirror case is still live: a client that writes the URL with a trailing
slash, which is a normal thing for a client library or a proxy to do, gets a
307 on a POST. Many HTTP clients drop the body or downgrade the method on a
307/308 for a POST, so the symptom a developer sees is an empty or malformed
GraphQL request rather than a redirect. Cheap to close with an explicit
route or a documented note; filed because the phase already paid for this
lesson once in the other direction.

---

### F-4.3-A-11 minor CONFIRMED: the request-timeout middleware matches by path PREFIX, so it bounds paths that are not this surface

`router.py:94`:

```python
if scope["type"] != "http" or not scope.get("path", "").startswith(GRAPHQL_PATH):
```

`startswith("/graphql")` matches `/graphql`, `/graphql/`, and also
`/graphqlXYZ`, `/graphql-admin`, `/graphqlanything`. Today those all 404, so
the effect is nil. It becomes real the moment any future route is added
under a `/graphql`-prefixed name: that route silently inherits this
surface's 270-second bound and this surface's GraphQL-shaped 200-with-errors
timeout body, which would be a wrong response shape for a non-GraphQL route.

The docstring above the check claims it "bounds only its own surface", which
is true today and is not what the code says. An exact match plus an explicit
trailing-slash allowance would make the code state the claim.

## Attacks 4, 5 and 6: further findings

Probe: `a5_bounds.py`.

---

### F-4.3-A-12 critical CONFIRMED: the masking allowlist is a working credential-disclosure primitive, not a theoretical one (F-4.3-L-07 realised end to end)

`tracker/phase_4.3.md` files this as F-4.3-L-07, severity MINOR, state
"open", with the reason "The current modules were read and their messages
are caller-safe, so this is correct today". I drove it and it disclosed a
live-shaped credential verbatim.

`security.py:236-254` decides whether to mask an exception by the PACKAGE
ITS CLASS IS DEFINED IN:

```python
module = type(exc).__module__
return module == _TRUSTED_EXCEPTION_PACKAGE or module.startswith(
    _TRUSTED_EXCEPTION_PACKAGE + "."
)
```

Repro (`a5_bounds.py`, `allowlist_disclosure`), which builds exactly what a
future phase adding one exception class to any `adapters/graphql/` module
produces:

```python
LeakyError = type(
    "SecretLeakingError", (Exception,),
    {"__module__": "system_03_search_agent.adapters.graphql.fold"})

async def boom(run_id, **kw):
    raise LeakyError(
        "AGE_DSN=postgresql://kg_reader:hunter2@46.225.128.133:5432/kg "
        "failed at /Users/build/src/tools/graph_connection.py:462")
```

Observed response body, verbatim:

```json
{"data": null, "errors": [{"message":
 "AGE_DSN=postgresql://kg_reader:hunter2@46.225.128.133:5432/kg failed at /Users/build/src/tools/graph_connection.py:462",
 "locations": [{"line": 1, "column": 33}], "path": ["ask"],
 "extensions": {"code": "SECRET_LEAKING_ERROR"}}]}
```

Password, host, port, database user, absolute file path and source line: all
disclosed. The control group in the same probe, an identical
`RuntimeError` with the identical message, is correctly masked to
"This request could not be completed due to an internal error." The ONLY
difference is which package the class is defined in.

Why the "safe today" reasoning does not hold up:
- It is a fail-OPEN default on the disclosure axis, in a codebase whose own
  F-4.1-A-09 finding was a live database host, port and username reaching a
  caller through "a field assumed safe". The phase quotes that finding and
  then ships the same failure direction one layer over.
- It is not fully safe today either. `types.py:170-174`'s
  `InvalidCitationPayloadError` message interpolates a caught exception:
  `f"citation {payload.citation_id!r} failed re-validation against
  CitationPayload: {exc}"`. Pydantic v2's `ValidationError` string embeds
  `input_value=...`, so that message carries the rejected field's VALUE.
  Every caller of it currently swallows it (`fold.py:275-283`), so it does
  not escape today, and that is a property of the CALL SITES, not of the
  allowlist. Move that raise one call site and it is disclosed.
- `_error_code_for` publishes the Python class name as the public
  `extensions.code`, so an internal class name reaches callers as well
  (already filed by the lead as F-4.3-L-08).

The inversion the phase file itself suggests (an explicit marker base class
or class attribute, so disclosure is opt-in) is the fix. Filed as CRITICAL
rather than minor because the mechanism is proven, the payload is a
credential, and nothing but review discipline stands between the current
state and a disclosure.

---

### F-4.3-A-13 major CONFIRMED: `ask` and `run` return contradictory answers for the same run, and `run` reports `grounded: true` on content `ask` refused

`fold.py`'s module comment claims the two entry points "consume the same
event sequence through the same `_consume_event` function and the same
`_finalize` function, so the two entry points can never silently diverge on
what folding means." They diverge on WHICH EVENTS THEY CONSUME.

- `fold_run` reads `default_registry.subscribe(...)`, which STOPS at the
  terminal event (`run_registry.py:1009-1013`).
- `fold_run_snapshot` reads `entry.events` directly, the whole buffer,
  including every event appended AFTER the terminal one.

Repro (`a5_bounds.py`, `read_paths`): a stream emitting `guard`, then
`done(trust_outcome="refuse")`, then `token("POST-TERMINAL LEAKED TEXT")`, a
citation, and an answer-scope `trust_signal(outcome="answer",
grounded=True)`.

Observed, same run id, same caller, one second apart:

```
ask   -> answer: "This query could not be completed: the run ended before producing an answer."
run   -> answer: "POST-TERMINAL LEAKED TEXT"
         trustSignal: {"outcome": "answer", "grounded": true}
         citations: [{"citationId": "c1"}]
citations -> citations: [{"citationId": "c1"}]
```

Why it matters:
- Two operations on ONE surface give a caller two different answers for one
  run, and the difference is not "more has arrived since" (the run was
  already `finished: true`), it is a different definition of what the run
  said.
- The divergence runs in the unsafe direction: `run` folds post-terminal
  content and reports it as `grounded: true`, content that the run's own
  terminal event had already closed as `refuse`.
- The module comment asserting the two cannot diverge is exactly the shape
  `self-eval-loop.md` warns about: a confident comment is where the next
  reader stops checking. There is no test asserting the two agree.

The fix is for `fold_run_snapshot` to stop at the terminal event the same
way `subscribe` does, and for a test to assert `ask` and `run` agree on a
finished run.

---

### F-4.3-A-14 major CONFIRMED: a hostile document crashes the parser with an unhandled recursion failure, reported as a generic internal error

Repro (`a5_bounds.py`, `bounds`), a 7 KB document of nested inline
fragments:

```python
doc = "mutation A($input: AskInput!) {" + "... on Mutation {" * 400 \
      + " ask(input: $input) { runId }" + "}" * 400 + "}"
```

Observed:
```
inline-fragment-depth  50 -> 200, run created (within bounds)
inline-fragment-depth 200 -> 200, "Syntax Error: Document contains more than 1000 tokens. Parsing aborted."
inline-fragment-depth 400 -> 200, "This request could not be completed due to an internal error."
```

The 400-deep document is STRICTLY LARGER than the 200-deep one that the
token limiter correctly refuses, and yet it produces an internal error
instead of the token-limit message. The recursion failure happens before
the token count is reported, so a bigger hostile document gets a WORSE
outcome than a smaller one: the bound that exists is skipped over by making
the attack larger.

Why it matters:
- The phase premise says "The schema is bounded against a hostile document,
  not only against a hostile value... A query deeper than the configured
  limit... is rejected before execution." This document is not rejected, it
  is absorbed as an unhandled crash.
- `MaskErrors` turns it into a non-actionable "internal error", so a
  legitimate client sending an over-deep document cannot tell what to fix,
  and an operator reading logs sees an internal error rather than a refused
  document.
- `MAX_QUERY_DEPTH = 10` never fires on this input, which is consistent
  with the lead's own F-4.3-L-10 ("the depth limiter is dead weight against
  real documents today"). This finding is the sharper version of that one:
  the depth limiter is dead weight against HOSTILE documents too, because
  the parser dies before the depth-limiting validation rule ever runs.
- `security.py`'s own `_count_run_creating_fields` is likewise unbounded
  recursion over the same structures, and its validation rule runs at rule
  CONSTRUCTION, before graphql-core's visiting phase, so `QueryDepthLimiter`
  cannot protect it either. Any input deep enough to reach it would fail the
  same way, inside the one bound that guards money.

Costs about 0.01s per request, so this is a correctness and reporting
defect rather than a strong denial-of-service lever on its own. It becomes
one in combination with F-4.3-A-15 below.

---

### F-4.3-A-15 major CONFIRMED: request bodies are unbounded; 20 MB of unused GraphQL variables is accepted and served

Repro (`a5_bounds.py`, `bounds`):

```python
junk = {"input": {"text": "q", "sessionId": "s1"},
        "junk": ["z" * 1000] * 20000}          # ~20 MB of variables
r = await post_graphql(c, ASK, headers=hdr, variables=junk)
```

Observed: `status=200`, 0.11s, and A RUN WAS CREATED
(`{"data": {"ask": {"runId": "55789560-..."}}}`). The 20 MB payload is
JSON-parsed on every request and the operation proceeds normally.

Also observed: a 2 MB inline string argument inside the document itself
is accepted by `MaxTokensLimiter` (a string literal is ONE token) and takes
0.29s before failing on the Pydantic bound.

Why it matters: `MaxTokensLimiter(1000)` bounds the DOCUMENT and nothing
bounds the VARIABLES or the body. `production-standards.md`'s multi-agent
pipeline gate requires "`maxLength` on every string field and `maxItems` on
every array... they cap the blast radius", and the phase's own library
table lists the four defaults it hardened without a body-size bound among
them. The gate's coverage note says load is build phase 6.0's territory,
which covers "are the numbers right"; it does not cover "there is no number
at all on the request body".

Unauthenticated callers cannot reach this (auth runs first, and it holds),
so the exposure is per-account rather than anonymous. It is still an
unbounded allocation per request on a surface with no rate limit.

---

### F-4.3-A-16 major CONFIRMED: `AskInput` carries no bounds, so every input-validation failure reaches the caller as a masked "internal error"

`types.py:314-318`:

```python
@strawberry.input
class AskInput:
    text: str
    session_id: str
    audience_depth: AudienceDepth | None = None
```

No length bound on either string. The real bounds live on
`contracts.query.Query` (`text` min 1 / max 2000, `session_id` max 64, plus
a whitespace-only validator). `schema.py:227` constructs that model inside
the resolver, so a violation raises `pydantic.ValidationError`, whose module
is `pydantic` and therefore NOT allowlisted, so `MaskErrors` replaces it.

Repro (`a5_bounds.py`, `bounds`), a 100 000-character question:

```
{"data": null, "errors": [{"message":
 "This request could not be completed due to an internal error.",
 "path": ["ask"]}]}
```

The same masked message covers an empty question, a whitespace-only
question, an over-long question and an over-long `sessionId`: four
different, entirely user-fixable mistakes, all reported as an internal
server fault with no code and no guidance.

Why it matters:
- `tool-call-budgets.md`: "an error message must say what to do next, not
  just what failed". "Internal error" says neither.
- It is a cross-surface inconsistency: REST returns a 422 naming the field.
  A developer integrating against GraphQL is told the server broke.
- It misattributes fault. A caller cannot distinguish "you sent 100 000
  characters" from a genuine server fault, so the natural response is retry,
  which cannot ever succeed.
- The whole point of a typed schema layer is that the type rejects bad input
  before the resolver runs. `AudienceDepth` got exactly that treatment (a
  real enum, with the reasoning written down in `types.py:286-291`); `text`
  and `session_id`, the two fields an attacker actually controls, did not.

`types.py` names `MAX_ANSWER_LENGTH`, `MAX_CITATIONS`,
`MAX_DISCLOSURE_NOTES` and `MAX_DISCLOSURE_NOTE_LENGTH` as module constants
for OUTPUT, and declares no bound for INPUT.

---

### F-4.3-A-17 minor CONFIRMED: the request timeout tells the caller the operation "was aborted", but the billed run keeps running

`router.py:100-123`: on expiry the child task is cancelled and the parent
writes

> "This GraphQL operation exceeded this surface's 270s request timeout and
> was aborted before finishing."

Nothing cancels the RUN. `RunRegistry.cancel_run` is never called on this
path, and the run's background task is independent of the request task
(`create_run` starts it, `run_registry.py:838-896`).

Related, from the same probe (`a5_bounds.py`, `lifecycle`): a client that
abandons its request mid-flight leaves the run running to completion.
Observed after abandoning at 1s a 6-second run: the entry is still
`finished=False, cancelled=False` immediately after abandonment, and reaches
`finished=True, cancelled=False` on its own schedule.

Why it matters: the sentence is false about the thing the caller cares
about. The operation was abandoned; the spend was not. The caller is told to
"retry with a narrower question", which starts a SECOND billed run while the
first is still burning budget and still holding one of the 12 concurrency
slots. Either cancel the run on timeout, or say plainly that the run
continues and give the caller its `runId` so it can `stopRun` it. Today the
timeout body carries no `runId` at all, so the caller cannot stop it even if
it wanted to.

This is parity with REST's abandonment behaviour rather than a regression,
which is why it is minor; the FALSE SENTENCE is specific to this surface.

---

### F-4.3-A-18 minor UNCONFIRMED: 5 of 20 concurrent requests never returned within 60 seconds

Repro (`a5_bounds.py`, `lifecycle`): 20 concurrent `ask` mutations from one
account against a 6-second fake run, `httpx` client timeout 60s.

Observed: `codes={200: 15, 'TimeoutError': 5} cap_refusals=3`.

Twelve succeeded (the concurrency cap), three were correctly refused with
`CONCURRENT_RUN_CAP_EXCEEDED`, and five received nothing at all in sixty
seconds. A cap refusal is a fast, cheap, synchronous path, so the expected
result was 12 successes plus 8 immediate refusals.

Marked UNCONFIRMED: this ran over `httpx.ASGITransport` in-process, which
the premise gate's own coverage note explicitly excludes as not exercising
real socket behaviour, so the starvation may be an artifact of the harness
rather than of the surface. Reported rather than dropped because the shape
(some concurrent callers getting no response rather than a refusal) is worth
five minutes of someone else's time to rule out before build phase 6.0
tunes these numbers.

---

### Attacks 5 and 6: what behaved correctly

- Cross-surface: a run created through GraphQL is readable through
  `GET /v1/query/{run_id}/citations` by its owner, and the registry's
  concurrency cap is shared. `DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER = 12` sits
  above `guest_sessions.ATTEMPT_ALLOWANCE = 10` and
  `FREE_RUN_ALLOWANCE = 5`, so a guest identity hits the honest allowance
  wall before the concurrency wall, which is what the phase file claims.
- REST `POST /v1/query` still returns 202 after the shared edits.
- The concurrency cap DOES fire on this surface, with the
  `CONCURRENT_RUN_CAP_EXCEEDED` code and no internal cap value or namespaced
  owner id in the message.
- Fragment-spread chains of 200 and 400 are refused by the token limiter
  with an actionable message.
- A 2 MB inline string argument does not hang the server (0.29s).

## Final verifications and remaining findings

Probes: `a7_final.py`, `a8_moneyclose.py`.

---

### F-4.3-A-19 major CONFIRMED: the four honesty defects above are duplicated onto the MCP surface, and one of them into `core/graph.py`. F-4.3-L-02 is not a future risk, it has already happened

`tracker/phase_4.3.md` files the fold duplication as F-4.3-L-02, "open", "It
remains a real future-divergence risk". The divergence is not in the future.
The defects were COPIED IN, so a fix applied to one fold will now miss the
other, in both directions.

Verified by reading `adapters/mcp/server.py` (`a7_final.py`, `mcp_parity`):

| Defect | GraphQL `fold.py` | MCP `server.py` | `core/graph.py` |
|---|---|---|---|
| F-4.3-A-01 `risk_tier` boolean collapse to `"low"` | present | present | present, line 4281 |
| F-4.3-A-02 `scope=None` trust signal dropped | present | present (same two-branch shape) | n/a |
| F-4.3-A-04 non-fatal `error` discarded | present | present (`if payload.fatal`) | n/a |
| F-4.3-A-05 `tool_result.truncated` discarded | present | present (discarded by design, lines 613-615) | n/a |

Two honest qualifications, so this is not overstated:
- F-4.3-A-05 is NOT a regression this phase introduced; MCP discards
  `tool_result` deliberately and says so. The finding stands against both
  surfaces, not against this one specifically.
- The synthetic-branch `risk_tier="unknown"` fix DID land on MCP as well
  (T-4.3-05), so the phase's stated fold-in was carried across. It was the
  AGGREGATION path, in all three files, that nobody looked at.

`core/graph.py:4281-4287` is the one worth naming separately, because it is
not adapter code:

```python
TrustSignalPayload(
    outcome=trust_outcome,
    risk_tier=("high" if any(t.risk_tier == "high" for t in claim_trusts)
               else "low"),
    grounded=True,
    ...
    scope="answer",
)
```

The same `unknown -> low` collapse, plus an unconditional `grounded=True`,
inside the core's own answer-scope emitter. Every surface reads it. Fixing
`fold.py` alone would leave the wrong value arriving pre-computed.

---

### F-4.3-A-20 minor CONFIRMED: `stopRun` reports `stopped: true` for a run it did not stop

`schema.py:272-273`:

```python
default_registry.cancel_run(resolved)
return StopRunResult(run_id=resolved, stopped=True)
```

`stopped` is a fixed literal. `cancel_run` is a documented no-op on a run
whose task has already finished (`run_registry.py:1005-1007`).

Repro (`a7_final.py`, `surface_and_stop`): stop an already-finished run.

```
stopRun          -> {"runId": "...", "stopped": true}
registry state   -> finished=True cancelled=False
citations.runCancelled -> false
```

The surface says `stopped: true`; the registry says the run was never
cancelled; and `citations.runCancelled`, a field on this same surface,
says `false`. Two fields on one surface contradict each other about one run.

Idempotency requires that a repeated stop not ERROR. It does not require
lying about what happened. `stopped` should report whether this call
actually cancelled a running task, or the field should be renamed to
something that is true unconditionally (`accepted`). A caller currently
cannot tell whether its stop had any effect, which is the one thing it
called the mutation to find out.

---

### Verifications that came back clean

- The money bound fails CLOSED on the recursion path (F-4.3-A-14). Probe
  `a8_moneyclose.py` sent recursion-crashing documents at depths 300, 400,
  800 and 2000 with `create_run` instrumented: `new_runs=0` at every depth.
  The crash happens during parse or validation, strictly before execution,
  so no run and no spend. The document is a reporting defect, not a money
  defect.
- `security._count_run_creating_fields`, the money bound's own recursive
  counter, DOES raise `RecursionError` at nesting depth 3000 when called
  directly. It is not reachable at that depth through the surface, because
  `MaxTokensLimiter(1000)` and the parser's own recursion limit both bind
  first (an inline fragment costs 3 tokens, so ~330 is the deepest
  parseable). Recorded because the ordering that saves it is incidental:
  the counter runs at validation-RULE CONSTRUCTION, before graphql-core's
  visiting phase, so `QueryDepthLimiter` never protects it. Raising
  `MAX_TOKEN_COUNT` in a future phase would expose it.
- Surface attribution is correct: `RequestContext.surface` observed as
  `'graphql'` inside `run_streaming` for a GraphQL-started run, never
  `rest_sse`.
- Reading a run after eviction returns a clean `RUN_NOT_FOUND`, not an
  internal error.
- `citations()` on an unfinished run returns an actionable
  `RUN_NOT_YET_FINISHED` naming what to wait for.
- `stopRun` called twice does not error.
- Guest refusal, duplicate-header handling, cookie and query-parameter token
  rejection, and cross-user ownership on all three run-addressed operations:
  all correct (Attack 3 table above).
- No cost, dollar or token figure is reachable anywhere (Attack 4).

---

## Correction to F-4.3-A-02's reachability, recorded rather than edited

After filing F-4.3-A-02 I read every `TrustSignalPayload(...)` construction
in `core/` and `synthesis/`. All four sites (`core/graph.py` lines 3959,
4238, 4269, 4281) set `scope` explicitly, to `"answer"` or `"claim"`. So NO
CURRENT PRODUCER emits a scope-less trust signal, and the defect is not
live today.

It stays filed, at major rather than the critical I first wrote, because:
- `scope` is contract-optional with a `None` default, so a scope-less signal
  is a VALID event this surface must handle. Its optionality exists on
  purpose (`contracts/events.py:218-223`).
- The fold's handling of it fails silently and in the reassuring direction,
  which is the property that makes it worth fixing before something emits
  one, not after.
- The identical shape is on the MCP surface, so a future emitter breaks two
  surfaces at once.

An `else:` branch that treats an unscoped signal as answer-scope, or that
refuses to fold rather than discarding it, closes it in one line.

---

## What this pass did NOT cover

Stated per `.claude/rules/goal-contracts.md`'s coverage-declaration
discipline, so the gap is arguable rather than invisible.

- A live model and a live graph. Every run was faked through
  `run_streaming`, so nothing here says anything about grounding quality,
  real latency, or real cost.
- A real socket. Everything ran over `httpx.ASGITransport` in-process.
  F-4.3-A-18's concurrency observation is the one finding this limitation
  most likely distorts, which is why it is marked UNCONFIRMED.
- Sustained load and rate limiting. Single requests and one 20-way burst
  only. No finding here establishes what happens under real concurrency.
- The frontend. No GraphQL consumer was exercised; F-4.3-A-06's rendering
  consequences are argued from the payload, not demonstrated in a client.
- Persisted queries, an operation allowlist, and subscriptions: not built,
  so not attacked.
- Auth token cryptography. I attacked how the header is PARSED and which
  token families are accepted; I did not attack signing, expiry maths, or
  key separation.
- The REST and MCP surfaces themselves. Attack 6 checked the shared
  registry, the shared cap, the surface literal and read-back across
  surfaces, and read MCP's fold source. It did not drive MCP end to end, so
  F-4.3-A-19's MCP rows are established by source reading, not by execution.


---

## Postscript: this findings file was itself corrupted by F-4.3-A-06's payload

Worth recording because it is the cheapest possible demonstration of why
F-4.3-A-06 matters. Quoting the observed response body verbatim into this
markdown file embedded 2 NUL bytes, 2 ESC bytes, 1 BEL byte and a U+202E
right-to-left override into it. `grep` then classified the file as BINARY
and silently returned nothing for every pattern, including patterns that
were present. A downstream tool did not error; it reported an empty result
for a file full of matches.

That is exactly the class of harm the unsanitized `answer` and `claimText`
fields hand to any consumer that stores or greps a GraphQL response. The
control bytes in this file have since been replaced with their escaped
names so it stays readable and greppable.
