# Re-review of build phase 4.3 fix round

Branch `phase/4.3-graphql-api`. Prime suspects: `d467dcf` (fix round), `6601cca` (critical security fix).
Status: IN PROGRESS. Findings appended as found, never batched.

---

## R-01 (MAJOR): the critical fix's central claim is false. The public marker INHERITS.

Claim under test, stated twice:
- commit `6601cca`: "Trust is now DECLARED... Sharing a base class, or a package, grants nothing."
- `security.py:266-267` (`_is_allowlisted_application_exception` docstring): "Everything else, including every exception defined in this same package, is masked."

The code is `getattr(type(exc), PUBLIC_ERROR_MARKER, False) is True` (`security.py:278`). `getattr` on a
class walks the MRO, so ANY subclass of a marked class inherits the marker. Measured:

```
SchemaError subclass allowlisted: True
GraphQLSecurityError subclass allowlisted: True
InvalidAskInput declares its own marker: False   (inherits it from SchemaError)
MRO: InvalidAskInput -> GraphQLError -> SchemaError -> Exception
```

Sharing a base class grants EVERYTHING. It is not an oversight that can simply be tightened either:
the fix round's own new class `types.InvalidAskInput` gets its disclosure ONLY by inheritance, so the
mechanism as shipped depends on the behaviour the commit message says it does not have.

Why this matters rather than being a wording nit. The commit's stated security property is "an
exception added in a future phase is masked until somebody decides otherwise, which inverts the
failure direction." That property does not hold for the case that will actually occur. This phase's
own convention (`tracker/phase_4.3.md` pre-build read, `schema.py:101-107`) is that every error on
this surface subclasses one shared base so catch sites dispatch on a base class, and `schema.py`'s
comment says outright "every class below inherits from `SchemaError`". So the natural next exception
on this surface WILL subclass `SchemaError`, and will be disclosed by default with no reviewable
opt-in line, which is the exact failure mode F-4.3-A-12 was filed against.

No LIVE disclosure today: all four current subclasses (`RunNotFound`, `RunNotOwned`,
`ConcurrentRunCapExceeded`, `InvalidAskInput`) carry fixed literals. This is a false security claim
plus a latent primitive, not a working one. The fix is `PUBLIC_ERROR_MARKER in type(exc).__dict__`
(a per-class declaration, which is what "declared" means), plus an explicit marker line on
`InvalidAskInput` and on each `SchemaError` subclass that is genuinely safe.

---

## R-02 (MAJOR): the critical fix silently re-broke J-10 at two new sites. `citations` on an unfinished run is now a masked "internal error".

The fix round for J-10 spent ~500 lines making caller-fixable input errors actionable. The commit
BEFORE it (`6601cca`, the critical fix) made two previously-actionable errors NON-actionable, and
nobody noticed because no arm asserts either one at the wire.

The old allowlist docstring named the casualties explicitly (`git show 6601cca`, removed lines):
"`fold.py`'s `FoldError` and its subclasses ... all qualify without needing to be named here".
`FoldError` was never given `__graphql_public__`. Measured:

```
fold.FoldError:              disclosed=False
fold.FoldTimeoutError:       disclosed=False
fold.RunNotYetFinishedError: disclosed=False
```

Driven end to end over the real app (`scratchpad/probe3.py`: real signup, real token, real run in
flight, real `/graphql` POST):

```
citations on unfinished run -> 200
{"data": null, "errors": [{"message": "This request could not be completed due to an internal error.",
 "locations": [...], "path": ["citations"]}]}
```

No `extensions.code`. The judge measured the OLD behaviour by hand and recorded it as correct
(judge report line 649: "it behaves correctly, returning `RUN_NOT_YET_FINISHED_ERROR`, but no arm
holds that"). The absent arm is exactly why the regression landed.

Two casualties, both on the ordinary path:
1. `citations(runId:)` on a run that has not finished. `fold.py:1046` calls this the mirror of
   REST's 409. REST answers 409 with a reason; GraphQL now answers "internal error", so a client
   polling for citations cannot tell "not ready yet, poll again" from "the server is broken", and
   the retry-safety gate in `production-standards.md` fails on the same wording J-10 failed on.
2. `fold_run`'s `FoldTimeoutError`, whose message was REWRITTEN in the fix round to be maximally
   actionable ("retry with a narrower question, or use the REST/SSE surface to watch the run's own
   event stream"). That text can no longer reach any caller.

And a comment that now asserts a false property, which is the class `self-eval-loop.md` names:
`security.py:186-190` still says "in the common case, `fold_run`'s own more specific
`FoldTimeoutError` fires and is DISCLOSED BY NAME before this coarser whole-operation bound would
trigger". It is not disclosed by name. It is masked.

Test coverage of the two classes is unit-only (`test_fold.py:446`, `:561`, `:576-577` assert the
exception is raised and its base class). Nothing asserts what a caller receives, which is the only
thing that changed.

---

## R-03 (MINOR, structural claim false): the third read path still stops on a DIFFERENT predicate, so `citations` can still return a post-terminal citation `ask` and `run` refuse.

`d467dcf`'s own words: "`_consume_event` now raises `terminal_event_seen` and both loops break on it,
so the two consume an identical prefix BY CONSTRUCTION rather than by a comment claiming they do",
and A-13's fix is described as covering all three read paths.

It does not. `fold_citations` never calls `_consume_event`. It re-implements the stopping rule
inline (`fold.py:1060-1062`) as a raw-dict test, `sanitized.payload.get("fatal") is True`, while
`_consume_event` (`fold.py:693-699`) parses `ErrorPayload` and reads the Pydantic-COERCED `.fatal`.
Three predicates for one rule (the registry's `subscribe`, `fold.py:1060`, `fold.py:697`), two of
which are raw-dict identity tests and one of which is a coercing parse.

Reproduced with fully valid `Event` objects, no `model_construct` bypass
(`scratchpad/probe4.py`; a fatal error at seq 3, then a post-terminal token, citation `c2`,
`trust_signal(outcome=answer, grounded=true)` and `done`):

```
--- well-formed fatal error (control) ---
  run(): citation ids= ['c1']      citations(): ids= ['c1']         AGREE: True
--- fatal=1 (int) ---
  run(): citation ids= ['c1']      citations(): ids= ['c1', 'c2']   AGREE: False
--- fatal="true" (string) ---
  run(): citation ids= ['c1']      citations(): ids= ['c1', 'c2']   AGREE: False
```

`c2` is a post-terminal citation, and `citations(runId:)` hands it to a caller that `ask` and `run`
refuse to show. That is A-13's sentence verbatim.

Reachability today is low: the core builds `ErrorPayload(...).model_dump()`, which yields a real
bool. This is the same closed-world posture the transport agent used to dispute part of the
`core/graph.py` finding, and it is stated the same way here rather than inflated. What is NOT
closed-world is the structure: any future terminal condition added to `_consume_event` is invisible
to `fold_citations`, and the round's claim that the three paths agree "by construction" is exactly
the kind of confident comment `self-eval-loop.md` says to treat as a claim to be tested.

The fix is one shared predicate, ideally `fold_citations` consuming through `_consume_event` like
the other two.

---

## R-04 (MAJOR): premise clause C5 is STILL not met. The fold silently truncates merged trust warnings, and unlike the site that was fixed, the dropped text survives nowhere.

The judge graded C5 NOT MET on three holes and named hole 3 as TWO sites: the notes cap, and
"`fold.py:235` caps the merged `trust_signal.message` at 500 characters. Both silently drop
DISCLOSURES."

The fix round fixed the notes cap (`_cap_notes` + `_NOTES_TRUNCATION_NOTE`) and the notes-into-
message merge (`_merge_disclosure_messages` + `_MESSAGE_TRUNCATION_MARKER`). It did NOT fix the
site the judge actually pointed at by line number. `fold.py:293` is still:

```python
merged_message = " ".join(messages)[:MAX_DISCLOSURE_NOTE_LENGTH] or None
```

A bare slice, no marker, no note. Measured (`scratchpad/probe5.py`: two claim-scoped
`trust_signal` events, each with a message legally inside `TrustSignalPayload.message`'s own
500-char bound):

```
len(warning A) + len(warning B) + 1 = 528
len(returned message)               = 500
second warning FULLY present        : False      <- its last sentence is gone
disclosures.notes                   : []
any note mentions the cut           : False
```

The returned message ends mid-sentence at "...A second, ind". The sentence that was cut off is
"A second, independent source is required." on a claim flagged `risk_tier=high`.

Why this is worse than the hole that WAS fixed, and the reason the judge's own severity note does
not carry over: the judge called hole 3 "the mildest of the three" explicitly because "the full text
does survive in `disclosures.notes` even when the `message` copy is cut". That mitigation does not
exist here. Trust-signal messages are never copied into `notes`; `notes` is empty in the run above.
The dropped safety warning survives in no field of the response at all.

Clause C5 is "Anything the surface drops or shortens, it says so." This drops and shortens a
high-risk warning and says nothing. C5 remains NOT MET.

### R-01 addendum: the fix round's OWN test arm pins the behaviour the commit denies

`test_types.py:732-741`, added in `d467dcf`:

```python
def test_it_declares_the_public_marker_that_security_py_requires(self) -> None:
    # Mutation that turns this red: stop descending from SchemaError (or
    # drop the marker from SchemaError).
    assert issubclass(types_module.InvalidAskInput, types_module.SchemaError)
    assert getattr(types_module.InvalidAskInput, security_module.PUBLIC_ERROR_MARKER, False) is True
```

The arm is named "declares the public marker" and what it actually asserts is that the marker is
INHERITED from a base class. So the repository simultaneously ships a commit message stating
"sharing a base class grants nothing" and a test pinning the fact that sharing a base class grants
disclosure. Whichever is meant, the two cannot both stand, and the one written down as the security
property is the false one.

---

## R-05 (MINOR): the new pre-auth refusals disclose four internal bounds, and `router.py` claims they disclose one.

`router.py:110-111`: "It is enforced BEFORE authentication, which is deliberate... The refusal
discloses only this module's own cap."

Measured with NO credentials of any kind (`scratchpad/probe6.py`):

```
1. unauth oversized body -> 200
   "...exceeds this surface's 256 KiB limit... The document itself is separately capped at
    1000 tokens..."                                    code REQUEST_BODY_TOO_LARGE
2. unauth over-nested doc -> 200
   "...nests deeper than this surface's 64-level limit... This schema executes at most 10 levels
    of selection..."                                   code DOCUMENT_TOO_DEEPLY_NESTED
3. unauth ordinary        -> 401 {"detail":"invalid or expired credentials"}
```

An unauthenticated caller learns `MAX_REQUEST_BODY_BYTES`, `security.MAX_TOKEN_COUNT`,
`MAX_DOCUMENT_NESTING_DEPTH` and `security.MAX_QUERY_DEPTH`. Two of the four belong to
`security.py`, not "this module", so the docstring's claim is false as written. This is the same
class as R-02's stale comment: a confident sentence asserting a property the code does not have.

The disclosure itself is low value (these are bounds, not secrets) and the actionability argument
for publishing a caller's own bound is sound, which is why this is minor rather than major. But it
is inconsistent with the surface's OWN stated discipline two files over: `types.py:483-484` says the
input messages quote the caller's bounds "that is the opposite of schema.py's concurrency-cap
message, which deliberately omits the internal cap value", and `schema.py:127-130` omits the cap
precisely so an unauthenticated or low-privilege caller cannot enumerate it. Four caps are now
enumerable with no credential at all.

What I could NOT turn into anything worse, stated so the negative result is on the record:
- The bounds are not a denial-of-service lever. The drain caps the running total at
  `MAX_REQUEST_BODY_BYTES` plus one chunk regardless of a lying or absent `content-length`; a
  chunked 400 KiB body was refused (`probe6.py` case 5), and the largest work an unauthenticated
  request can force is one 256 KiB read, one `json.loads` and one linear scan.
- A legitimate large-but-valid request is not refused. The largest legal request on this schema is
  a ~2 KB document plus a 2000-character `text` and a 64-character `sessionId`, two orders of
  magnitude under the cap. The premise gate's own control arm covers the ordinary case.
- Both spellings are bounded: `/graphql/` refuses an oversized body identically (`probe6.py` case 6).
- No content-type bypass: the installed Strawberry accepts only `application/json` (and multipart
  when `multipart_uploads_enabled`, which is False), so a raw `application/graphql` body cannot slip
  past `_document_is_too_deeply_nested`'s `json.loads` and reach the parser.

## R-06 (MINOR): a batch-shaped body is exempt from the new nesting bound.

`_document_is_too_deeply_nested` returns False for any body that is not a JSON object
(`router.py:306-307`), so a JSON LIST body skips the nesting scan entirely. Measured
(`probe6.py` case 4): a batch-shaped body carrying a 100-deep document passes the bound and reaches
the auth layer.

It is harmless today because batching is off by library default and
`_validate_batch_request` rejects the list before `graphql.parse` runs. It matters because the judge
already filed batching as a silent single point of failure ("a future `StrawberryConfig` edit that
enables it would silently defeat the one-run-per-document bound with no arm turning red"), and this
round added a SECOND bound that the same one-line config change would defeat, in the same
undetectable way. The nesting bound should scan every `query` string in a list body too.

## R-07 (MINOR): the two risk-tier aggregators this round wrote disagree, and `core/graph.py`'s routes an unrecognised tier into the bucket its own docstring says the UI deletes.

`fold.py::_floor_risk_tier` ranks an unrecognised tier WORST and returns it verbatim.
`core/graph.py::_aggregate_answer_scope_trust` ranks it in the MIDDLE and renames it to `"unknown"`
(the `else` branch, `graph.py:3787-3792`). One rule, two implementations, written in one commit.

The second one contradicts its own stated reasoning. Its docstring argues `"high"` must outrank
`"unknown"` because "the web UI ... suppresses the risk pill for `"unknown"` specifically, so
letting `"unknown"` win over `"high"` here would delete a high-risk warning from the screen"
(confirmed: `frontend/src/hooks/useRunView.ts:463`). Its `else` branch then maps every unrecognised
tier, a future `"critical"` or `"moderate"`, INTO `"unknown"`, i.e. into exactly the suppressed
bucket, at the answer-scope signal.

Impact is small today and is stated honestly rather than inflated: `ClaimTrust.risk_tier` is a
two-value Literal so the `else` branch is unreachable, and the frontend also reads the CLAIM-scoped
events, whose unrecognised tier its own reduce ranks worst, so the pill would still render. The
real cost is that `fold.py`'s carefully-built unrecognised-worst ranking can never observe an
unrecognised tier arriving from the core, because `graph.py` launders it into `"unknown"` first, so
the fix-by-category the commit describes is inert end to end.

## R-08 (MINOR): `types.py` publishes a default-resolution helper that the resolver does not call, and the resolver hardcodes the literal the helper exists to own.

`types.py:400-412` defines `DEFAULT_AUDIENCE_DEPTH` and `resolve_audience_depth`, whose docstring
says they exist "so schema.py's `ask` resolver has one place to read it from rather than hardcoding
the string a second time". `schema.py:289-291` hardcodes it a second time:

```python
audience_depth=(input.audience_depth.value if input.audience_depth is not None else "researcher"),
```

Grep confirms `resolve_audience_depth` and `DEFAULT_AUDIENCE_DEPTH` have no caller anywhere in
`src/`. Two arms (`test_types.py:353` and `:359`) exercise the uncalled helper; the line the surface
actually runs is exercised by nothing that would notice the two disagreeing. Related: the
`"audience_depth"` row of `ASK_INPUT_MESSAGES_BY_CORE_FIELD` is unreachable, since the field is a
real GraphQL enum and its `.value` is always core-legal.

---

## R-09 (MAJOR): J-10 is only half fixed. Three more caller-fixable `ask` inputs still come back as a bare "internal error" with no code.

`d467dcf`: "Every caller-side input error was returned as a masked 'internal error' with no code,
which reads as transient, so a client retries forever on input that can never succeed."

Measured, authenticated, over the real app (`scratchpad/probe7.py`):

```
ask, text over 2000 chars : code='INVALID_ASK_INPUT'  (fixed)
ask, empty text           : code='INVALID_ASK_INPUT'  (fixed)
ask, whitespace text      : code='INVALID_ASK_INPUT'  (fixed)
ask, sessionId over 64    : code='INVALID_ASK_INPUT'  (fixed)
ask, text as an int       : code='INVALID_ASK_INPUT'  (fixed)
ask, bad audienceDepth    : code=None  msg='This request could not be completed due to an internal error.'
ask, missing sessionId    : code=None  msg='This request could not be completed due to an internal error.'
ask, null text            : code=None  msg='This request could not be completed due to an internal error.'
```

Three inputs that are 100 percent the caller's to fix, an out-of-set enum value, an omitted
required field, and an explicit null, still produce the exact string and the exact missing code
J-10 was filed on. A client that omits `sessionId` retries forever on input that can never succeed.

Mechanism, and why the fix could not reach them. `_should_mask_error` (`security.py:310-317`) masks
any `GraphQLError` whose `original_error` is not marked public. graphql-core's variable coercion
re-wraps every failure as `GraphQLError(prefix + "; " + error.message, original_error=error)`, where
`error` is the inner failure. For the five fixed cases the inner error is `InvalidAskInput`, which
carries the marker, so it is disclosed. For an enum mismatch, a missing field or a null, the inner
error is a plain graphql-core `GraphQLError`, which carries nothing, so it is masked. The fix
therefore covers exactly the fields that happen to have a custom scalar and no others, and adding
a scalar cannot fix a MISSING field or a null in any case.

The durable fix is in `_should_mask_error`, not in `types.py`: a `GraphQLError` whose
`original_error` is itself a `GraphQLError` with no non-GraphQL cause is a coercion or validation
diagnostic, exactly like the `original_error is None` case the function already declines to mask,
and carries no internal exception text.

The judge's Shape 2 ("all 42 arms send WELL-FORMED input ... there is not one arm that sends ... an
unknown `audienceDepth` value") named this literal case, and the fix round added arms for the
scalar-guarded fields only. `test_types.py`'s new `TestAskInputBounds` sends 12 invalid inputs and
not one of them is a missing field, a null, or a bad enum.

## R-10 (MINOR): the message that reaches the caller is NOT the fixed literal `types.py` guarantees.

`types.py:479-484`: "Every message is a FIXED module-level literal, assembled once at import time
from this module's own constants and never from a caught exception, a caller value, a host, or any
runtime state (F-4.3-A-12)."

The literal is what `types.py` RAISES. What the caller RECEIVES is graphql-core's composition
(`scratchpad/probe9.py`):

```
message prefix : "Variable '$input' got invalid value 'SENTINEL-CALLER-TEXTyyyyyyyyyyyyy..."
caller text echoed back : True
```

The delivered message is `"Variable '$input' got invalid value " + inspect(input_value) + " at
'input.text'; " + <the module literal>`. The surface deliberately UNMASKS this whole string, so the
`__graphql_public__` marker is authorising text this module did not write.

Bounded and low risk, stated plainly rather than inflated: `inspect()` truncates (a 60 KB input
produced a 380-character message and a 510-byte response, so there is no amplification), and the
echoed content is the caller's own input going back to the same caller. What is wrong is the
INVARIANT, and the invariant is the whole justification for the marker: the same commit that removed
`InvalidCitationPayloadError`'s interpolation of a Pydantic `input_value`, on the grounds that
embedding a rejected value in a disclosed message is the F-4.3-A-12 defect, shipped a new disclosed
path where graphql-core performs the identical interpolation. If the discipline is "a disclosed
message is a fixed literal", it does not currently hold, and the file says it does.

## R-11 (MAJOR): THREE fix-round arms proven vacuous, including BOTH arms guarding the critical body cap.

27 mutations run against the fix round's own arms, each applied to the real source file, run, then
restored from an in-memory original with the SHA-256 asserted equal. Harness: `scratchpad/mutate.py`.
24 turned their arms red. Three stayed green.

### V-1 and V-2: both `MAX_REQUEST_BODY_BYTES` arms are self-referential (F-4.3-A-15's fix is unpinned)

Mutation: `MAX_REQUEST_BODY_BYTES = 256 * 1024` -> `256 * 1024 * 1024`. Result: **9 passed**, the
whole of `TestTransportBounds` green with the body cap effectively removed and a 20 MB body,
the exact F-4.3-A-15 attack, once again accepted and served.

Cause, and it is structural rather than a slip. Both arms build their probe FROM the constant they
are testing:

```python
oversized = "x" * (router_module.MAX_REQUEST_BODY_BYTES + 4096)   # arm 1
oversized = b"x" * (router_module.MAX_REQUEST_BODY_BYTES + 4096)  # arm 3
```

So the probe grows with the cap and the arm proves only "whatever the cap is, it is enforced",
never "the cap is at a value that bounds anything". The mutation arm 1 names for itself is "raise
MAX_REQUEST_BODY_BYTES above the probe size", which is impossible by construction: the probe size
is DEFINED as the cap plus 4096.

This is the highest-value vacuity in the set, because F-4.3-A-15 is the adversary finding about
money and unbounded allocation, and the two arms that exist to hold its fix cannot fail on the
number that IS the fix. The repair is a literal probe size (say 512 KiB) plus a separate arm
asserting `MAX_REQUEST_BODY_BYTES <= some literal ceiling`.

### V-3: the string-skipping arm puts its braces where the scanner never looks

Mutation: delete the string-literal branch from `_max_nesting_depth` (`if char == '"':` ->
`if False:`). Result: **9 passed**.

`test_the_nesting_scan_is_not_fooled_by_braces_inside_strings` sends its 500 braces as the value of
`input.text`, i.e. in `variables`. `_document_is_too_deeply_nested` reads `payload["query"]` and
nothing else, so the braces are never in the scanned text at all. Measured (`scratchpad/probe8.py`):

```
arm's document nesting depth  : 2     (the braces are in `variables`)
inline-literal document depth : 3     (braces inside a GraphQL string in the DOCUMENT)
MAX_DOCUMENT_NESTING_DEPTH    : 64
```

The arm's own named mutation is "count every `{` in the raw body rather than skipping strings",
which describes scanning the body; the code scans only the document, and the probe never puts a
brace there. The ~30 lines of block-string, string-escape and comment handling in
`_max_nesting_depth` are therefore pinned by nothing: delete them and a caller sending an INLINE
literal question containing braces is refused, with no arm turning red. The repair is to send the
question as an inline literal in the document rather than as a variable.

### V-4 (not an arm, an unpinned branch): `_floor_risk_tier`'s empty case

Mutation: `if not risk_tiers: return UNASSESSED_RISK_TIER` -> `return "low"`. Result: **92 passed**
across the whole of `test_fold.py` AND the whole premise gate. The "empty means unassessed, never
low" branch has no arm anywhere. Its exact sibling in `core/graph.py`
(`_aggregate_answer_scope_trust`'s `if not claim_trusts`) DOES have one
(`test_aggregating_nothing_reports_unknown_and_ungrounded_never_vacuously_true`), which is what
makes the gap visible: the same defensive branch was written twice in one commit and armed once.
Unreachable today from either call site, so this is a coverage gap rather than a live defect.

Full mutation table (24 red, 3 green) is in `scratchpad/mutate.py` and the two task outputs.
Every mutation was restored and every restore was hash-verified; `git status --porcelain
--untracked-files=all` is EMPTY.

---

# THE PREMISE, RE-GRADED CLAUSE BY CLAUSE

Graded against the assembled surface after `d467dcf`. The judge's four problem clauses were C1
(partial), C5 (not met), C6 (partial), C10 (not met).

| # | Clause | Judge | Now | Why |
|---|--------|-------|-----|-----|
| C1 | same cited answer REST produces, HTTP 200, no `errors` | PARTIAL | **PARTIAL, unchanged** | Both of the judge's two gaps survive. There is still NO cross-surface equivalence arm anywhere (no `/v1/query` call in the gate), and the surface is still measurably worse than REST for a malformed request: REST answers 422 naming the field for a missing or null one, this surface answers "internal error" with no code (R-09) |
| C2 | `trustSignal`, `citations` field-for-field, host-pinned `sourceUrl`, `runId` | MET | MET | Nothing in the round touched the field mapping; suite green at the same six known live-network failures |
| C3 | a refusal is a successful response | MET | MET | Confirmed by probe |
| C4 | no cost figure reaches this surface | MET | MET | The round added no field and no figure. The new timeout message mentions billing in prose with no number, and the gate greps the printed SDL, not runtime prose |
| C5 | anything the surface drops or shortens, it says so | NOT MET | **NOT MET** | The judge's holes 1 and 2 are genuinely closed (`_CitationCollector` records a reason per drop; `CitationsExport.disclosures` is required). Hole 3 is HALF closed: the notes cap and the notes-to-message merge now disclose their cut, and the site the judge named by line number still truncates silently, on content that survives nowhere else (R-04) |
| C6 | bounded against a hostile DOCUMENT; one document never starts many runs | PARTIAL | **PARTIAL, improved** | J-11 is genuinely closed: the request body is now bounded, twice, before authentication, and a chunked or lying sender is caught. Two reasons it is not MET. The body cap's only two arms cannot fail on the cap's value (R-11 V-1/V-2), so the bound is real but unpinned. And F-4.3-L-10 is untouched: `MAX_QUERY_DEPTH = 10` while the deepest legal document on this schema nests about 3, so the depth bound still bounds nothing a caller can reach |
| C7 | ownership reuses one rule | MET | MET | Unknown and foreign runs answer `RUN_NOT_FOUND` / `RUN_NOT_OWNED` on all four operations |
| C8 | the withdrawn existence-oracle claim | MET | MET | Unchanged |
| C9 | every run attributed `surface="graphql"` | MET | MET | Unchanged |
| C10 | "Every clause is mutation-proven" | NOT MET | **NOT MET** | Three sweeps have now run. The lead found 5, the judge found 5 (one overlapping count), and this sweep found 3 more plus one unarmed branch, all of them in arms the FIX ROUND itself added. The claim was false when written, was false after the judge, and is false now |

---

# SUMMARY

VERDICT: **FAIL.**

Counts: **5 major** (R-01, R-02, R-04, R-09, R-11), **6 minor** (R-03, R-05, R-06, R-07, R-08,
R-10), 0 blocking-critical.

Single most important reason: **R-02.** The critical security fix (`6601cca`) took two
caller-facing, actionable errors, `citations(runId:)` on an unfinished run and `fold_run`'s
timeout, and turned them into the bare uncoded "This request could not be completed due to an
internal error." The judge had measured the old behaviour by hand and recorded it as correct, and
no arm holds it, so the regression landed invisibly INSIDE the round that was spending five hundred
lines fixing that exact defect class for a different field. That is build phase 4.2's measured
lesson reproduced precisely: the worst defect in a round lives inside the previous round's fix.

Second reason, and the one that generalises: **the round's own claims outran its code in five
separate places, and each claim is written in the confident tone that stops the next reader
checking.** "Sharing a base class grants nothing" (R-01, contradicted by the round's own test arm).
"Both loops break on it, so the two consume an identical prefix by construction" (R-03, the third
path uses a different predicate). "The refusal discloses only this module's own cap" (R-05, it
discloses four caps from two modules). "Every message is a FIXED module-level literal" (R-10, the
delivered message is graphql-core's and embeds the caller's rejected value).
"`FoldTimeoutError` ... is disclosed by name" (R-02, it is masked).

What is genuinely strong and should be said. The honesty cluster is real work, well done, and it
holds under mutation: 24 of 27 mutations turned their arms red, including every one of the risk-tier
severity, terminal-event, duplicate-id, non-fatal-error, tool-truncation, notes-cap and
input-bounds arms. Reading the input bounds off `contracts.query.Query` at import time is the right
shape and its drift arm is real. The transport bounds work end to end, before authentication, on
both path spellings, against both an honest and a lying sender. `core/graph.py`'s extraction is
byte-identical today exactly as claimed (verified: `trust_for_claims` hardcodes `grounded=True` and
`ClaimTrust.risk_tier` is a two-value Literal). The `stopRun` correction, the timeout-message
correction and the trailing-slash fix are all right and all mutation-proven. No test anywhere in the
diff was weakened.

Suite: 6 failed, 3076 passed, 113 skipped, 1 xfailed, matching the commit's own account of the six
known live-network-gated failures in `test_citation_trust_full_premise.py`.

Lint: `venv/bin/ruff check` reports 18 errors, NONE of them in this phase's files (all in
`tracker/*.py`, `.claude/skills/`, and three unrelated tool tests). Clean for this diff.

`git status --porcelain --untracked-files=all`: **EMPTY**. Every one of the 27 mutations was applied
to the real source file and restored from an in-memory original with the SHA-256 asserted equal
before the next mutation ran; the harness aborts on a failed restore and never aborted. No file in
the repository was left modified, and every probe and harness file lives in the session scratchpad.
