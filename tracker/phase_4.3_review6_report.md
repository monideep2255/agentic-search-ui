# Review 6 findings, build phase 4.3

Started. HEAD b1de288.

## F1 (Section 2) MAJOR, BLOCKING (pending my own verification): `citations(runId:)` hardcodes runFailed=False
fold.py:1211-1221 `fold_citations()` passes `run_failed=False` literally; it never builds an _Accumulator
and never inspects the fatal error payload. So a run that died reports runFailed:false on the citations
surface, with empty notes. Reachable: entry.finished is set in the same finally block for a fatal error
(core/run_registry.py:647), so citations(runId:) is callable on any failed run.
Reported by subagent sec2 with a live probe. TO VERIFY MYSELF.

## Section 1 notes so far (no finding yet)
- MaskErrors.anonymise_error DROPS extensions (good); keeps nodes/source/positions/path, all caller-derived.
- Scalar parsers in types.py raise only fixed module literals -> the `Variable '$x' got invalid value.{0,400}$`
  tail carries only caller data + a fixed literal TODAY. A future scalar raising a non-GraphQLError would be
  wrapped as "Expected type 'X'. <str(exc)>" and would ride out through that same tail. LATENT.
- graphql-core inspect() truncates strings at 240 chars, so a long caller value cannot push the message
  past the .{0,400} tail on its own. Verified pyutils/inspect.py max_str_size=240.

## F2 (Section 1) MAJOR but LATENT -> NON-BLOCKING: the content rule is NOT the only disclosure path
security.py:570-574. `_should_mask_error`'s last branch discloses ANY exception whose class carries
PUBLIC_ERROR_MARKER, VERBATIM, without calling `_disclose_if_message_is_authored` and without touching
_DISCLOSABLE_MESSAGE_PATTERNS. PROVEN LIVE: probe P18 `query { run(runId:"nope") { runId } }` returned
  {"message":"no such run","extensions":{"code":"RUN_NOT_FOUND"},"path":["run"]}
"no such run" matches NONE of the 22 authored patterns. It went out solely because RunNotFound inherits
SchemaError.__graphql_public__.
So security.py:348-351's claim -- "A message reaches a caller only if it matches a shape authored HERE...
Anything else, from any raiser, in any phase, of any class, is replaced by a fixed literal and a code" --
is FALSE as written. The class-marker proxy (round 1 package -> round 4 class family -> now marker) survives
underneath the content rule, and the docstring hides that.
REACHABILITY TODAY: every marker-carrying class (SchemaError + RunNotFound/RunNotOwned/
ConcurrentRunCapExceeded/InvalidAskInput, FoldError + FoldTimeoutError/RunNotYetFinishedError,
GraphQLSecurityError which is never raised) raises a fixed module literal, a caller-supplied run_id, or a
module bound constant. No internal text reaches a caller today. So: LATENT, NON-BLOCKING.
It becomes a leak the first time someone writes a marked subclass whose message interpolates a caught
exception -- which is exactly what types.py's own InvalidCitationPayloadError used to do.

## F3 (Section 4) MAJOR, BLOCKING: two authored patterns are DEAD, and both blunt a live caller-facing error
- Introspection. Probe P13 `{ __schema { types { name } } }` returns
  "This request was rejected as malformed. No further detail is available for this failure."
  with NO extensions/code. Pattern `^Introspection is disabled\.?.{0,120}$` never matches strawberry's real
  wording, so the caller loses the one thing that would tell them the surface deliberately refuses
  introspection.
- Anonymous operation. Probe P20 `{ run(...) } query Named { run(...) }` returns the same generic literal.
  Pattern `^Anonymous operation must be the only defined operation\.$` misses graphql-core's real string
  ("This anonymous operation must be the only defined operation." -- leading "This ").
Both are shipped, both reachable by any caller, both destroy actionability with no code to branch on
(production-standards.md retry-safety gate). And both patterns are VACUOUS: nothing in the suite makes them
fire, so nobody noticed they match nothing.

## F3 (final form) MAJOR, BLOCKING: default-deny blunts 15 ordinary caller-side GraphQL errors
Measured live over the real router (probe2/probe3, HTTP 200, codeless generic literal
"This request was rejected as malformed. No further detail is available for this failure."):
  unused variable | undefined variable | duplicate argument | duplicate variable name |
  duplicate operation name | directive in wrong location | field conflict | fragment cycle |
  leaf field with a selection set | object field with no selection set | subscription operation |
  anonymous + named operation | { __schema } | { __type } | non-null variable given null
Disclosed correctly (control, so the finding is not "everything is masked"):
  Unknown directive / Fragment 'F' is never used / Field 'run' argument 'runId' ... is required /
  Cannot query field / ask input field ... / Expected value of type 'AskText!', found null. /
  Field 'AskInput.text' of required type ... / Value 'NOPE' does not exist ... /
  Variable '$i' of required type 'AskInput!' was not provided. / Variable '$i' got invalid value ...
Three of the blunted ones have an authored pattern that MISSES the installed library's real wording,
i.e. the pattern is vacuous and nobody could have noticed:
  - `^Introspection is disabled\.?.{0,120}$`   vs real "GraphQL introspection has been disabled, but the
    requested query contained the field '__schema'."  (graphql/validation/rules/custom/no_schema_introspection.py:26)
  - `^Anonymous operation must be the only defined operation\.$` vs real "This anonymous operation must be
    the only defined operation."  (graphql/validation/rules/lone_anonymous_operation.py:35)
  - `^Subscriptions are not enabled.{0,120}$` vs real "Schema is not configured to execute subscription operation."
The rest have no pattern at all. security.py:11-16 claims every decision in the file is "verified against the
INSTALLED library rather than trusted from documentation"; this pattern table is the one place it was not.
BLOCKING: reachable by any caller with a well-formed POST, breaks production-standards.md's retry-safety gate
(an error must say what to do next) on 15 real shapes, and is a REGRESSION introduced by fc9eebf, the commit
whose stated purpose was to stop exactly this ("Masking these was a real defect, not a cosmetic one").

## F4 MINOR, NON-BLOCKING: an unknown operationName escapes the GraphQL envelope
POST {"query":"query Q {...}","operationName":"Missing"} -> HTTP 400, body is the PLAIN STRING
'Unknown operation named "Missing".' with no JSON at all. router.py:157-161 states this surface answers
"HTTP 200 with a populated errors array, never a 4xx or 5xx ... A caller writes one parser, not two."
That claim is false for this path (Strawberry raises CannotGetOperationTypeError out of Schema.execute,
which its FastAPI view turns into a 400). Pre-existing Strawberry behaviour, not introduced by these commits.

## F5 MINOR, NON-BLOCKING: MaskErrors is bypassed when an exception escapes the operation context manager
strawberry/schema/schema.py's async `execute`: the `except Exception as exc:` handler that builds
`PreExecutionError(errors=[_coerce_error(exc)])` sits OUTSIDE `async with extensions_runner.operation()`.
Extension hooks are contextlib generators, so throwing into them skips MaskErrors' post-yield masking pass
entirely, and `_coerce_error` puts `str(exc)` on the wire verbatim. Nothing on this surface can reach that
handler today (parse and validate errors are returned not raised; resolver errors become located errors in
result.errors; the three re-raised Strawberry errors go to the HTTP layer). LATENT, but it is a hole in the
"every error goes through _should_mask_error" premise that no comment in security.py acknowledges.

## F6 MINOR, NON-BLOCKING: fold.py:114-118 asserts a property its own raise site breaks
FoldError's docstring: "Every message raised as this class or a subclass is a fixed literal, or is built only
from a `run_id` the caller already supplied, so none of them carries a host, a credential, a path, an
INTERNAL BOUND or a caught exception's text." fold.py:1073-1078 raises FoldTimeoutError interpolating
`_FOLD_LOOP_TIMEOUT_S` (240s), which is an internal bound. Harmless value, false claim. Exactly the
"comment asserting a property" shape self-eval-loop.md warns about.

## F7 MINOR, NON-BLOCKING: `^Syntax Error: Document contains more than \d+ tokens.*$` is dead code
Pattern 22 can never be the matching pattern: pattern 7 `^Syntax Error: .{0,120}$` already matches
"Syntax Error: Document contains more than 1000 tokens. Parsing aborted." (57 chars after the prefix).
Confirmed live in probe P19. Two patterns also use an unbounded `.*$` tail (this one and
`^Field '...' argument '...' of type '...' is required.*$`), against the file's own bounded-tail discipline.

## F2 UPGRADED WITH PROOF (still LATENT -> NON-BLOCKING)
Direct call, no repository mutation:
  Leaky(SchemaError)          masked=False leaked=True code=LEAKY
  Leaky2(FoldError)           masked=False leaked=True code=LEAKY2
  Leaky3(GraphQLSecurityError) masked=False leaked=True code=LEAKY3
message "INTERNALMARKER host=db-internal.example port=5432 user=kgreader /Users/private/fold.py:912"
went out VERBATIM in all three. So test_security.py's new arm
`test_a_message_reaches_a_caller_only_if_its_shape_was_authored` asserts a property the code does not
have. Its six parameter cases deliberately never include a marker-carrying exception, which is the one
branch that falsifies its own title. Not exploitable today (no marked class interpolates internal text),
so NON-BLOCKING -- but the arm's NAME and security.py:348-351's docstring both need correcting, or the
next author will add a marked subclass believing the content rule protects it.

## F8 (Section 3) VACUOUS ARM, PROVEN: test_a_rejected_token_never_names_its_real_neighbours
Added in 6adfaaf. Its own comment names the mutation: "remove either `_strip_schema_suggestions` call".
I applied the equivalent (made `_strip_schema_suggestions` the identity) and ran the whole GraphQL suite:
  206 passed  (baseline: 206 passed)
Mechanism, shown live with the mutation in place:
  unknown argument -> "This request was rejected as malformed. No further detail is available..."
  unknown type     -> "This request was rejected as malformed. No further detail is available..."
  unknown output field -> "Cannot query field 'nope' on type 'AskResult'."   (no suggestion: that one is
                          covered by StrawberryConfig(disable_field_suggestions=True), not by this code)
  unknown input field  -> "Field 'AskInput.text' of required type 'AskText!' was not provided."
With the stripper gone, a message carrying "Did you mean ...?" no longer matches any authored pattern, so
default-deny replaces it with the generic literal -- which satisfies BOTH of the arm's assertions
("Did you mean" absent, message non-empty). None of its four cases can ever fail. Fourteenth vacuous arm
in this phase, and the newest.
Corollary worth stating: after the fc9eebf redesign, `_strip_schema_suggestions` no longer prevents schema
enumeration at all (default-deny already does). Its only remaining function is to let a suggestion-bearing
message match a pattern so it stays actionable. The arm should assert the message still names the caller's
own rejected token, not merely that it is non-empty.

## Mutation sweep results (Section 3), whole GraphQL suite, 206 baseline
M1 `_is_disclosable_message` always True              -> 2 failed  ARMED
M2 authored-error-code check removed                  -> 1 failed  ARMED
M3 `_strip_schema_suggestions` identity               -> 206 passed VACUOUS (F8)
M4 `and error.path is None` dropped (reopens critical) -> 1 failed  ARMED
M5 marker check always True (default-open)            -> 8 failed  ARMED
M6 fold.py `run_failed = False` on the ask/run path   -> 1 failed  ARMED
Every mutation restored from a byte copy; `git status --porcelain` and `git diff --stat` empty after each.

## VERDICT
DO-NOT-MERGE. 2 BLOCKING (F1, F3), 6 non-blocking (F2, F4, F5, F6, F7, F8).
