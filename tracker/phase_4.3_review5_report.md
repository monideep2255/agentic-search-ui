# Review round 5, build phase 4.3, branch phase/4.3-graphql-api, HEAD 153eb8d

Started. Append-only. Each finding written the moment it is confirmed.

## F-R5-01 (HIGH, disclosure) -- the third proxy fails open the same way the first two did

`src/system_03_search_agent/adapters/graphql/security.py:389`

    if isinstance(original, GraphQLError) and error.path is None:

The module comment at security.py:374-388 asserts:

    "So `path is None` means no resolver ran: the request was rejected against
     the schema and the caller's own values, and nothing internal has been
     touched yet."

That claim is FALSE. Variable coercion runs THIS SURFACE'S OWN CODE:
`types.py:_parse_ask_text` and `types.py:_parse_ask_session_id` are the
`parse_value` of the `AskText` / `AskSessionId` scalars. A resolver did not run,
but application code did.

graphql-core then launders any exception that code raises straight to the caller.
`venv/.../graphql/utilities/coerce_input_value.py:166-171`:

    except Exception as error:
        on_error(..., GraphQLError(
            f"Expected type '{type_.name}'. {error}", original_error=error))

and `venv/.../graphql/execution/values.py:137-142` re-wraps THAT:

    on_error(GraphQLError(prefix + "; " + error.message, var_def_node,
                          original_error=error))

so the delivered error has `original_error` that IS a `GraphQLError`, `path is
None`, and a `message` containing `str(<internal exception>)` verbatim.

PROVEN END TO END against the mounted app (`adapters/web_sse/app.py`, real
router, raw HTTP, real bearer token). A `RuntimeError` raised from `AskText`'s
`parse_value` came back as HTTP 200 with:

    "message": "Variable '$input' got invalid value 'hello world' at
     'input.text'; Expected type 'AskText'. connect failed:
     postgresql://kg_user:<pw>@46.225.128.133:5432/kg at /srv/app/db.py:88",
    "extensions": {"code": "BAD_USER_INPUT"}

That is the DSN, the credential, the host, the port, the database name, the
source file and the line number -- the exact payload of F-4.3-A-12 -- plus the
exact inversion R-09 was filed to fix: our internal fault stamped
`BAD_USER_INPUT`, blaming the caller.

Repro: scratchpad/attack1.py::test_A_scalar_parse_value_internal_exception_leaks

Reachability today: the two shipped `parse_value` bodies only raise
`InvalidAskInput`, so no CURRENT input triggers it. This is a latent fail-open,
not a live leak, which is why HIGH and not CRITICAL. But it is precisely the
failure class `PUBLIC_ERROR_MARKER` was designed to close: security.py:244-248
promises "a new exception added to this package in a future phase is MASKED
unless its author opts it in". For the coercion phase that promise is void --
anything raised there is disclosed with no declaration, no marker, no review.
A third scalar, a `len()` on a value that turns out not to be sized, a helper
that touches config: all disclosed.

The durable fix is the same one the module already articulates: disclose the
error graphql-core BUILT, never the text of an exception it CAUGHT. Concretely,
require the innermost `original_error` chain to terminate in either no Python
exception at all or an exception carrying `PUBLIC_ERROR_MARKER`.

## F-R5-02 (HIGH, disclosure) -- the round-4 CRITICAL repro still works, moved one phase earlier

The round-4 gate arm proves a bare `GraphQLError` raised from a RESOLVER is masked.
Raise the identical error from the COERCION phase and it is disclosed verbatim.

Repro: scratchpad/attack3.py::test_bare_graphqlerror_in_coercion_leaks
`AskText.parse_value` raises `GraphQLError(<internal text>)`. Response, HTTP 200:

    "message": "Variable '$input' got invalid value 'hello world' at 'input.text';
                connect failed: postgresql://kg_user:<pw>@46.225.128.133:5432/kg
                at /srv/app/db.py:88",
    "extensions": {"code": "BAD_USER_INPUT"}

Mechanism: `coerce_input_value`'s `except GraphQLError` branch
(venv/.../graphql/utilities/coerce_input_value.py:162-164) hands the raised error
straight to `on_error`, which re-wraps it with `original_error=<that GraphQLError>`
and no path. security.py:389 then discloses it.

The round-4 fix narrowed the leak from "any GraphQLError anywhere" to "any
GraphQLError raised before a resolver runs". It did not close it. The gate arm
added for it only covers the resolver phase, so the gate is green on a hole of
the same shape.

## F-R5-03 (HIGH, disclosure) -- `extensions` is an unmasked side channel on the disclosed path

security.py's masking only ever rewrites `message` (Strawberry's
`MaskErrors.anonymise_error`, venv/.../strawberry/extensions/mask_errors.py:36-44,
drops `extensions` by passing `original_error=None`). That is correct for the
MASKED path. On the newly-DISCLOSED `path is None` path the whole error object
goes out untouched, and graphql-core's `GraphQLError.__init__` COPIES
`extensions` from `original_error` when the wrapper has none, so an exception's
`extensions` dict propagates to the caller in full.

Proven, message deliberately clean, detail only in extensions
(scratchpad/attack3.py::test_extensions_channel_leaks):

    "message": "Variable '$input' got invalid value 'hello world' at 'input.text'; bad value",
    "extensions": {"code": "OOPS",
                   "dsn": "postgresql://kg_user:<pw>@46.225.128.133:5432/kg",
                   "trace": "/srv/app/db.py:88"}

Control (`test_extensions_channel_from_resolver`) passes: the same payload raised
from the resolver IS stripped. So the difference is entirely the new branch.
security.py:390-394 also only ADDS a code when one is absent; it never audits or
strips the keys already there.

## F-R5-04 (MAJOR, disclosure, REACHABLE TODAY, introduced by 1625bf1) -- the R-09 fix reopened schema enumeration that DisableIntrospection exists to close

Reachable by any authenticated caller, no monkeypatching, no latent bug. Proven
against the mounted app (scratchpad/attack4.py):

    POST {"query": "mutation A($input: AskInput!) { ask(input:$input){runId} }",
          "variables": {"input": {"tex": "hi there", "sessionId": "s"}}}
    -> 200
    "message": "Variable '$input' got invalid value {...}; Field 'tex' is not
                defined by type 'AskInput'. Did you mean 'text'?"
    "extensions": {"code": "BAD_USER_INPUT"}

Same for 'sesionId' -> "Did you mean 'sessionId'?" and 'audiencedepth' ->
"Did you mean 'audienceDepth'?".

Before 1625bf1 these were coercion errors with no marker, so they were MASKED.
The R-09 branch discloses them. An attacker now brute-forces near-miss strings
and reads back the exact input-object field set of a schema whose introspection
is deliberately off (`DisableIntrospection`, security.py:669) and whose field
suggestions are deliberately off (`disable_field_suggestions=True`,
security.py:701).

The control proves the asymmetry is real and not ambient: an OUTPUT field
near-miss returns "Cannot query field 'ru' on type 'Query'." with the suggestion
stripped.

Root cause, read from the installed library rather than assumed
(venv/.../strawberry/schema/base.py:113-120):

    @staticmethod
    def remove_field_suggestion(error: GraphQLError) -> None:
        if (error.message.startswith("Cannot query field")
                and "Did you mean" in error.message):
            error.message = error.message.split("Did you mean")[0].strip()

`disable_field_suggestions` strips suggestions ONLY from messages beginning
"Cannot query field". Nothing else. security.py:695-701's comment claims this
setting closes the "open window" beside the locked front door. It closes one
pane of it.

## F-R5-05 (MINOR, pre-existing but now demonstrably in scope) -- two more suggestion channels leak the schema

Same run, same document, no masking involved (these are validation errors with
`original_error is None`, disclosed by security.py:339-340):

    query { run(runID: "x") { runId } }
    -> "Unknown argument 'runID' on field 'Query.run'. Did you mean 'runId'?"

    mutation A($input: AskInpu!) { ask(input: $input) { runId } }
    -> "Unknown type 'AskInpu'. Did you mean 'AskInput'?"

Argument names and type names are both enumerable the same way. Not introduced
by the last two commits, but it is the same window as F-R5-04 and the premise
gate's Introspection row is graded green over all of it.

## F-R5-06 (MAJOR, honesty) -- 153eb8d updated the test count in CLAUDE.md's phase cell and left every prose claim in it false

`CLAUDE.md` on disk at HEAD 153eb8d (verified, `git status --porcelain` empty):

  "its independent review HAS now run, across three rounds"
      -> FALSE. Four. `tracker/phase_4.3_rereview2_report.md` is on disk and was
         added by 153eb8d itself.

  "TWO MAJORS REMAIN OPEN (R-04 ...; R-09 ...)"
      -> FALSE per the same commits. 1625bf1's own message says it "Closes the
         two majors the re-review round left open".

  "Reports: tracker/phase_4.3_judge_report.md, _adversary_report.md,
   _rereview_report.md"
      -> omits `_rereview2_report.md`, which the same commit created.

  "Every one of its three review rounds found its worst defect inside the
   previous round's fix"
      -> should read four, and understates the pattern the commit is about.

153eb8d touched exactly one number in that cell (3202 -> 3203) and nothing else.

This is the same defect class 1625bf1's own message claims credit for fixing
("corrects a stale claim in CLAUDE.md that told the next reader this phase had
never been independently reviewed").

Compounding it, the guard is blind to it:

    $ venv/bin/python tracker/check_doc_drift.py --check
    ok: 10 facts computed | 0 stale | 0 structural

`check_doc_drift.py` verifies COUNTS only. It reports 0 stale over a cell whose
every prose claim about the review state is wrong, and the commit message cites
that green result ("doc drift 0 stale") as evidence the docs are current. Under
`.claude/rules/goal-contracts.md` ("a verify surface must state its own
coverage") this gate does not declare that it grades no prose, so a green read
means more than it is entitled to.

## Section 3 result for security.py's new arms: NOT VACUOUS (verified by mutation)

Mutations installed by replacing the module attribute `security._should_mask_error`
(faithful, because `SCHEMA_EXTENSIONS`' `lambda: MaskErrors(should_mask_error=
_should_mask_error, ...)` resolves the global at call time). No repository file
was edited. Plugin: scratchpad/mutplugin.py.

Target: test_phase_4_3_premise.py::TestCallerInputIsNeverAnInternalError and
::TestDisclosuresSurvive (10 tests).

  baseline                 10 passed
  drop_path_check          1 failed  -> test_a_resolver_raising_a_graphql_error_still_masks
  drop_isinstance_branch   3 failed  -> all 3 test_a_malformed_request_is_named_not_masked params
  never_mask               5 failed  -> both converse arms + all 3 params
  always_mask              3 failed  -> all 3 params
  invert_path_check        4 failed  -> 3 params + the resolver-masking arm

Every arm goes red under the mutation its own comment names. No vacuous arm found
in this cluster. Restore asserted: the fixture restores the original attribute in
a `finally`, and the baseline re-run after the sweep is 10 passed (below).

## F-R5-07 (CRITICAL, clause C5) -- the fatal-error disclosure is evicted by the notes cap and survives NOWHERE

153eb8d's own commit body names this exact damage as the thing it was fixing:

  "a run with a dozen warnings lost its answer-truncation note, its
   citations-omitted note and its fatal-error disclosure, the last of which has
   no structured field to fall back on."

The fix reordered ONLY the preserved trust warnings to the end. The
fatal-error note itself is still appended LAST among the surface's own notes:

    fold.py:997-999   if acc.fatal_error_payload is not None:
                          trust_payload = _floor_trust_signal_for_fatal_error(...)
                          notes.append(_fatal_error_disclosure(acc.fatal_error_payload))
    fold.py:1005      notes = _cap_notes(notes)
    fold.py:809-824   _cap_notes keeps notes[: MAX_DISCLOSURE_NOTES - 1]  (the FIRST 9)

Ten earlier notes evict it. And because fold.py:1006-1009 merges the
ALREADY-CAPPED list into `trust_signal.message`, the message loses it too.
The hole the commit set out to close is still open for the one note the commit
itself singles out as having no fallback.

PROVEN END TO END through the mounted app, HTTP 200, real bearer token
(scratchpad/attack5.py). Event stream: oversized answer, 49 citations plus a
duplicate display index plus a duplicate id plus 6 over cap, one truncated tool
result, four distinct non-fatal error classes, one unscoped trust signal, then a
FATAL error event. Response:

  disclosures.notes (10):
    [0] The answer above was truncated ...
    [1] 1 citation(s) repeated a citation id ...
    [2] 6 citation(s) beyond this surface's 50-citation limit ...
    [3] 1 returned citation(s) share a display index ...
    [4] 1 tool result(s) behind this answer were truncated ...
    [5] Part of this run hit a temporary error ...
    [6] Part of this run could not complete as requested ...
    [7] Part of this run failed unexpectedly ...
    [8] Part of this run was stopped before it finished ...
    [9] 2 further disclosure(s) did not fit this surface's 10-disclosure limit
        and were omitted.

  trustSignal.message: "unscoped warning The answer above was truncated ...
                        [further disclosures omitted, see notes]"
  trustSignal.outcome/riskTier: flag / high

  Expected fatal disclosure: "This query failed unexpectedly before finishing."
  present in notes:   False
  present in message: False

What the caller is left with: an answer, 50 citations, `outcome: flag`,
`riskTier: high`, and nine notes about truncation and non-fatal blips. Nothing
anywhere says the run DIED. `flag` and `high` are also reachable without any
fatal error (the floor at fold.py:397-406 only raises to flag/high, it does not
introduce a distinct state), so the two fields cannot substitute for the note.
A caller cannot distinguish "we answered, with caveats" from "we failed".

That is a cite-or-refuse-adjacent honesty failure of the exact class
`production-standards.md`'s layer-degradation gate forbids ("synthesize from
whatever layers responded and explain the gap in the answer text").

The premise gate is green over it: `TestDisclosuresSurvive` never combines a
fatal error with ten other simultaneous notes, so no arm exercises the eviction
order the fix rearranged.

Independently corroborated by a second reviewer working from the private
functions (`_finalize` with a constructed `_Accumulator`), reaching the same
result by a different route.

Related, same reviewer, not independently re-verified by me and reported as
their evidence rather than mine:
  - MAJOR: `_cap_notes` is applied twice (fold.py:1005 and fold.py:1018). When
    the first cap fires, the second treats its synthetic summary as one slot and
    can evict it, emitting an omission count that undercounts and misattributes
    (12 real notes + 5 preserved warnings reported "6 omitted" against a true 8).
  - MAJOR: `trust_signal.message`'s 500-character budget can be consumed entirely
    by trust-warning text in `_floor_trust_payloads` (fold.py:349), after which
    the second merge at fold.py:1005-1009 contributes nothing, so the fatal-error
    sentence is absent from the message even in runs where it survives in notes.

## F-R5-08 (MINOR, honesty) -- "Lint clean" is not true as stated

153eb8d's commit body: "Lint clean, doc drift 0 stale."

    $ venv/bin/ruff check
    Found 18 errors.
    $ venv/bin/ruff check src/.../adapters/graphql/ tests/.../adapters/graphql/
    All checks passed!

The GraphQL surface itself is clean; the repository is not. The 18 are
pre-existing debt in `tracker/*.py`, a skill script and four unrelated test
files, so this is a wording defect rather than a code defect, but a reader
gating on that sentence would be misled, and `/verify` runs bare `ruff check`.

## Section 3 result for the corrected TestDisclosuresSurvive arm: LIVE, but PARTIALLY VACUOUS

Mutations applied directly to `src/system_03_search_agent/adapters/graphql/fold.py`,
each restored from a byte-copy afterwards. Restore proven by SHA-256 equality
(bbe610731a1ef395c05472981c4061ad4ce420953b25d5b76cc1976c401e6344 before and
after) and by an empty `git status --porcelain`.

Target: ::TestDisclosuresSurvive::test_merged_trust_warnings_are_never_cut_without_saying_so

  M1  truncate each preserved warning to 20 chars   -> 1 failed  (RR2-04's own mutation, correction holds)
  M2  preserved_trust_warnings = []                 -> 1 failed
  M3  restore the silent cut in _floor_trust_payloads-> 1 failed
  M4  keep only the FIRST and LAST preserved warning-> 5 passed   <-- SURVIVES

## F-R5-09 (MAJOR, vacuity) -- the thirteenth: the just-corrected arm is still blind to a silent drop of every middle warning

M4 above silently discards every preserved trust warning except the first and
the last, with no disclosure. The entire `TestDisclosuresSurvive` class stays
green: 5 passed.

Cause: the fixture `_many_trust_warnings_stream` emits exactly three warnings,
ALPHA / BETA / OMEGA, and the corrected assertion lists only two of them
(test_phase_4_3_premise.py, the `expected = [...]` list added by 153eb8d):

    expected = [
        "WARNING-ALPHA " + ("a" * 200),
        "WARNING-OMEGA " + ("z" * 200),
    ]

The fixture's own docstring states the intent: "The two markers asserted by the
arm sit in the FIRST and LAST warning deliberately". First-and-last is exactly
the shape a middle-dropping mutation defeats. RR2-04 fixed the depth of the
assertion (prefix -> full text) and left its breadth unfixed, so a run losing
n-2 of its n warnings, undisclosed, is still a green gate. That is the same
clause C5 the arm exists to hold.

Fix: assert on the full set, `set(expected) <= set(notes)` over all three, or
assert the count.

---

## VERDICT: FAIL

Counts: 1 critical (F-R5-07), 3 high (F-R5-01, F-R5-02, F-R5-03),
3 major (F-R5-04, F-R5-06, F-R5-09), 2 minor (F-R5-05, F-R5-08).
Plus 2 majors reported by the fold.py reviewer that I did not independently
re-verify (double `_cap_notes`, message-budget starvation).

Baseline verified: 3203 tests total, 3083 passing, 6 failing, all six
`@live_only` in tests/.../synthesis/test_citation_trust_full_premise.py blocked
by the no-network conftest guard. The graphql package alone: 195 passed.
`ruff check` on the graphql adapter: clean. Repository-wide: 18 pre-existing.

git status --porcelain: EMPTY. HEAD 153eb8d, unchanged.
Every mutation restored; fold.py SHA-256 identical before and after.
