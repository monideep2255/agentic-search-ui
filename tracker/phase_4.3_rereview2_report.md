# Re-review 2, build phase 4.3, branch phase/4.3-graphql-api, HEAD 1625bf1
Started. Append-only. Each finding recorded the moment it is confirmed.

## RR2-01 (CRITICAL) The R-09 fix reopens F-4.3-A-12: any GraphQLError from a resolver is disclosed verbatim

`src/system_03_search_agent/adapters/graphql/security.py:367-373`

```python
    if isinstance(original, GraphQLError):
        if error.extensions is None or "code" not in error.extensions:
            error.extensions = {... "code": INPUT_VALIDATION_ERROR_CODE}
        return False
```

This branch sits BEFORE `_is_allowlisted_application_exception` (line 374) and
therefore bypasses the `PUBLIC_ERROR_MARKER` declaration rule entirely for the
whole `GraphQLError` family. The rule that branch replaces is stated at
security.py:222-224: "Trust is declared by the exception class itself, never
inferred from where the class happens to be defined." The new branch infers
trust from CLASS FAMILY, which is the same category of inference, and it fails
OPEN on the disclosure axis.

Proven end to end against the real mounted app over ASGITransport, a resolver
raising a bare `graphql.GraphQLError`:

```
### LEAK-1 resolver raises GraphQLError directly
status=200
{"data": null, "errors": [{"message": "AGE_DSN=postgresql://kg_reader:hunter2@10.0.0.1:5432/kg at /Users/secret/path/fold.py:912", "locations": [...], "path": ["ask"], "extensions": {"code": "BAD_USER_INPUT"}}]}
```

A DSN with its password, the host, the port, the database user, an absolute
source path and a line number reached the caller verbatim. This is the SAME
demonstration that made F-4.3-A-12 critical, and the identical `RuntimeError`
with the identical message is still correctly masked (probe REG-1):

```
### REG-1 internal still masked
{"errors": [{"message": "This request could not be completed due to an internal error."...}]}
```

Only the base class differs. A `GraphQLError` subclass leaks the same way
(probe LEAK-2). The code's own comment (security.py:363-366) asserts the
inverse -- "anything OUR code raises that is not caller-facing is a plain
Python exception, not a `GraphQLError`" -- which is an assumption about the
current call tree, not an enforced invariant, and is exactly the kind of
comment-asserting-a-security-property that `self-eval-loop.md` requires a test
to assert instead. Nothing tests it. `graphql-core`, `strawberry`, and any
future resolver can raise `GraphQLError`; the default-deny posture the marker
rule established is inverted for all of them, and worse, the leaked text is
labelled `BAD_USER_INPUT`, i.e. blamed on the caller.

The narrow fix the intent actually needs: gate on the error NOT having an
`original_error` chain that came from a resolver, e.g. only treat it as caller
input when `error.path is None` (coercion/validation happen before a path
exists) -- both leak probes above carry `"path": ["ask"]` while every genuine
coercion error carries no path.

## RR2-02 (MAJOR) The R-04 fix duplicates every merged warning into `trust_signal.message`

`src/system_03_search_agent/adapters/graphql/fold.py:855-857` extends `notes`
with the distinct trust messages. `fold.py:973-976` then merges `notes` back
into `trust_payload.message`, which ALREADY contains those same messages
(built at `fold.py:349` by `_merge_disclosure_messages(None, messages)`). Each
warning is therefore emitted twice in the caller-visible message.

Measured end to end (probe: two claim-scoped signals, messages
"ALPHA-warning-text" and "BETA-warning-text"):

```
### two short warnings, notes: ["ALPHA-warning-text", "BETA-warning-text"]
### message: "ALPHA-warning-text BETA-warning-text ALPHA-warning-text BETA-warning-text"
### ALPHA count in message: 2
```

Two consequences, the second worse than the first:

1. The message stutters. Before 1625bf1 it read "ALPHA-warning-text
   BETA-warning-text" once.
2. It consumes the 500-char `TrustSignalPayload.message` budget TWICE, so the
   merged message now hits `_MESSAGE_TRUNCATION_MARKER` at roughly half the
   warning volume it used to. The commit set out to stop warning text being
   cut; on this axis it makes the cut arrive sooner.

`fold.py:852-854`'s comment says the extend is skipped for a single signal
"so copying it into notes would show the reader the same sentence twice" --
the author saw exactly this hazard and then let it through for every
multi-signal run, which is the majority case the fix targets.

## RR2-03 (MAJOR) The R-04 fix lets trust warnings EVICT the surface's own structural disclosures

`fold.py:855-857` appends the trust messages at the HEAD of `notes` (it runs
first in `_finalize`), and `_cap_notes` (`fold.py:816-824`) keeps the FIRST
`MAX_DISCLOSURE_NOTES - 1` = 9. So run-supplied warning text now displaces the
surface's own disclosures, which are appended later.

Two runs, identical except for the number of claim-scoped trust signals
(oversized answer -> truncation, 70 citations -> 20 omitted, fatal error):

n_warnings = 0 (pre-fix behaviour):
```
[
 "No trust assessment ... rather than assumed to be safe.",
 "The answer above was truncated to this surface's 8000-character limit; some content was omitted.",
 "20 citation(s) beyond this surface's 50-citation limit were omitted; some citation markers in the answer above may not resolve to a returned citation.",
 "This query failed unexpectedly before finishing."
]
```

n_warnings = 12 (post-fix):
```
[
 "W00-a trust warning", ... "W08-a trust warning",
 "6 further disclosure(s) did not fit this surface's 10-disclosure limit and were omitted."
]
### answer-truncation note present: False
### citations-omitted note present: False
### fatal-error note present: False
```

Every one of the surface's own disclosures is gone, from `notes` AND from
`trust_signal.message`. `answerTruncated`/`citationsOmitted` survive as
structured booleans/ints, but the FATAL-ERROR disclosure ("This query failed
unexpectedly before finishing.") has no structured field and is simply lost.

Before 1625bf1 `notes` never carried trust-signal text, so this eviction was
not reachable. The commit's stated purpose is closing premise clause C5
("anything the surface drops or shortens, it says so"); on this path it makes
the surface stop saying so about its own fatal error.

Aggravated by RR2-02: because every warning is written twice into the message,
the same run's `trust_signal.message` is also truncated. Full message from the
n=12 run shows W00..W11 then W00..W08 again, then the marker.

## RR2-04 (MINOR) The R-04 preservation claim is false past 9 warnings, and the code comment asserts it flatly

`fold.py:844-850`: "`_merge_disclosure_messages`'s contract is that a cut
message always survives in full in `disclosures.notes` ... Preserving each
distinct warning as its own note makes the helper's stated contract true at
this call site too". The commit message repeats it: "each distinct warning is
also preserved in full in `disclosures.notes`".

Measured with 50 distinct warnings:
```
### 50 warnings: note count = 10
### warning tags surviving in notes: ['W00-'...'W08-']
### missing: ['W09-' ... 'W49-']   (41 of 50)
```
`_cap_notes` does disclose the cut, so C5's letter survives, but the comment
and the commit message state an unconditional guarantee the code does not
provide. This is the exact pattern `self-eval-loop.md` names ("a code comment
that CLAIMS a property is a claim to be tested"): nothing tests the claim.

## RR2-05 (MINOR) The truncation marker now fires when nothing was actually omitted

Because of RR2-02's duplication, the merged message can exceed 500 chars purely
from the duplicate copy, so the caller is told disclosures were omitted when
every one of them is present.

Two warnings of ~150 chars each:
```
### merged-once length would be: 301
### floor message length: 301          <- fits, no marker
### floor marker present: False
### actual message length: 500
### marker present: True               <- caller told text was omitted
```
Nothing was omitted; the second copy was cut. A surface whose premise is
honesty about what it dropped now reports a drop that did not happen.

## RR2-06 (MINOR) R-09 attaches a code only on the variable-coercion path; every other caller mistake still ships codeless

Probed against the mounted app. Coded (`BAD_USER_INPUT` / `INVALID_ASK_INPUT`):
bad enum via variable, wrong scalar type, list-for-object, unknown input field,
explicit null, scalar bounds. NOT coded at all:

```
### R09-1 inline literal bad enum
{"errors":[{"message":"Value 'NOPE' does not exist in 'AudienceDepth' enum.","locations":[...]}]}   <- no extensions

### R09-5 unknown variable used in doc
{"errors":[{"message":"Variable '$nope' of required type 'AskInput!' was not provided."...}]}       <- no extensions

### R09-6 variable type mismatch
{"errors":[{"message":"Variable '$input' of type 'String!' used in position expecting type 'AskInput!'."...}]}  <- no extensions

### R09-7 missing variables key entirely
{"errors":[{"message":"Variable '$input' of required type 'AskInput!' was not provided."...}]}      <- no extensions

### R09-11 unknown field selection / R09-12 syntax error                                            <- no extensions
```
These reach `_should_mask_error` with `original_error is None` and return at
`security.py:339-340` before any code is attached. Same caller mistake
(`audienceDepth: NOPE`) publishes `BAD_USER_INPUT` through a variable and no
code at all inline, so a client cannot branch on code alone. Honest (not
"internal error"), so this is incompleteness, not a masking defect.

Transport-level shapes are handled correctly and honestly (HTTP 400, plain
text): malformed JSON body -> "Unable to parse request body as JSON"; missing
`query` key -> "No GraphQL query found in the request"; `variables` not a map
-> "The GraphQL operation's `variables` must be an object or null, if
provided." No leak in any of them.

## RR2-07 (MAJOR) VACUOUS ARM, 12th this phase, 5th by the lead

`tests/.../test_phase_4_3_premise.py:1495-1503`, the first clause of
`TestDisclosuresSurvive::test_merged_trust_warnings_are_never_cut_without_saying_so`:

```python
        # The full text of every distinct warning survives, so nothing a
        # merge had to cut is lost. This is the clause that actually closes
        # C5, and it goes red the moment the preservation is removed.
        for marker in ("WARNING-ALPHA", "WARNING-OMEGA"):
            assert any(marker in note for note in notes), ...
```

It asserts a PREFIX marker appears somewhere in some note. It does not assert
the note is the full warning. Mutation M6, applied to `fold.py:857`:

```python
            notes.extend(m[:20] for m in trust_messages)   # was: notes.extend(trust_messages)
```

Result:
```
M6 applied: notes carry only the first 20 chars of each warning
1 passed, 2 warnings in 9.27s
```

Every preserved warning is cut to 20 characters, undisclosed, and the arm that
exists precisely to prove "the full text survives, so nothing a merge had to
cut is lost" stays GREEN. The clause is vacuous with respect to the property it
names -- which is R-04 itself, one layer down. Restored, `fold.py` sha256
`e903dde868a9fdbfda965b36451c95095117fd3c00700273655c65fd4c47612a` matches the
pre-mutation hash.

### Mutation ledger for the other new clauses (all LIVE, none vacuous)

| Mutation | Target | Result |
|---|---|---|
| M1 remove the `isinstance(original, GraphQLError)` branch, `security.py:367-373` | `TestCallerInputIsNeverAnInternalError::test_a_malformed_request_is_named_not_masked` | 3 failed, 1 passed -- all three params red |
| M2 `_should_mask_error` returns False unconditionally | same class | 4 failed -- the converse arm is live |
| M3 `INPUT_VALIDATION_ERROR_CODE = "SOMETHING_ELSE"` | same class | 3 failed -- the code clause is independently live |
| M4 restore `" ".join(messages)[:MAX_DISCLOSURE_NOTE_LENGTH]`, `fold.py:349` | R-04 arm | red at line 1536, the floor `"omitted"` clause |
| M5 disable `notes.extend(trust_messages)`, `fold.py:857` | R-04 arm | red at line 1501, the preservation clause |
| M6 `notes.extend(m[:20] for m in trust_messages)` | R-04 arm | GREEN -- see RR2-07 above |

Every mutation restored from a byte-copy taken before the round; both source
hashes verified identical afterward (`security.py`
`f1c011692f2122aae878ba608232213613f7e1a3e574bd55188eec06733dd045`, `fold.py`
`e903dde868a9fdbfda965b36451c95095117fd3c00700273655c65fd4c47612a`).

## RR2-01b (MAJOR, same root cause as RR2-01) The branch catches EXECUTION errors, not only coercion/validation, and mislabels a server bug as the caller's fault

`security.py:342-343` states the scope: "A `GraphQLError` raised by graphql-core
ITSELF during input coercion or validation". The `isinstance` test enforces no
such scope. graphql-core raises bare `GraphQLError`s at EXECUTION time too, and
they are now all disclosed and stamped `BAD_USER_INPUT`.

Reachable with no hostile code: `graphql/execution/execute.py:380` raises
`GraphQLError("Expected Iterable, but did not find one for field 'X.Y'.")` when
a list field's resolver returns a non-iterable. `AskResult.citations` is a list
field. Probed end to end:

```
### LEAK-3 library GraphQLError at execution
{"data": null, "errors": [{"message": "Expected Iterable, but did not find one for field 'AskResult.citations'.", "locations": [...], "path": ["ask","citations"], "extensions": {"code": "BAD_USER_INPUT"}}]}
```

A server-side bug is reported to the caller as `BAD_USER_INPUT`. The commit's
own justification for the fix is that misattributing fault "tells a caller
their own malformed request was OUR fault"; this runs the identical error in
the opposite direction, and `BAD_USER_INPUT` reads as permanent, so it tells a
client never to retry something that a server fix would make succeed.

Other library sites in the same class, unreachable only because the schema has
no abstract types or enum outputs TODAY: `execute.py:883-927`
(`ensure_valid_runtime_type`, whose messages embed `inspect(result)`, i.e. the
resolver's returned internal object) and `type/definition.py:1265` (`Enum 'X'
cannot represent value: <internal value>`). Adding one union, interface or enum
output field in a later phase silently turns those into live disclosure paths.

Note again that every genuine coercion/validation error carries NO `path`,
while both leak probes carry `"path": ["ask"]` / `["ask","citations"]`.

## RR2-08 (MINOR) C5 drop-site sweep: `fallback_link` is dropped with no disclosure

`fold.py:364-366`:
```python
        fallback_link=next(
            (payload.fallback_link for payload in payloads if payload.fallback_link), None
        ),
```
Two claim-scoped signals carrying DIFFERENT fallback links:
```
### fallback_link kept: warning 1 warning 2 | https://www.ncbi.nlm.nih.gov/gene/671
### the other link mentioned anywhere? False
```
The second link is discarded silently. `citation_id=None` (fold.py:361) drops
the per-claim attribution too. Pre-existing, not introduced by 1625bf1, but it
is a drop site C5 covers and neither the gate nor the R-04 fix touches it.

# SECTION 4: premise clauses re-graded

## C5, "anything the surface drops or shortens, it says so": NOT MET

Every drop/shorten site on the surface, enumerated independently:

| # | Site | Disclosure | Verdict |
|---|---|---|---|
| 1 | Answer text at `MAX_ANSWER_LENGTH`, `fold.py:921-927` (incl. `_truncate_on_word_boundary`'s extra trim) | note + `answerTruncated` | MET |
| 2 | Citations at `MAX_CITATIONS` and every per-reason reject, `fold.py:611,629` | `citationsOmitted` + per-reason notes | MET, but evictable (see 4) |
| 3 | Citations export truncation, `fold.py:1155,1168` | `exportTruncated` + `citationsOmitted` | MET |
| 4 | `_cap_notes` at `MAX_DISCLOSURE_NOTES`, `fold.py:816-824` | count note | letter MET, substance NOT -- RR2-03 |
| 5 | `_merge_disclosure_messages` 500-char cut, `fold.py:444-447` | `_MESSAGE_TRUNCATION_MARKER` | MET but now FALSE-POSITIVE -- RR2-05 |
| 6 | Merged trust warnings, `fold.py:349` (the R-04 site) | marker + notes | floor MET, "in full" claim false past 9 -- RR2-04 |
| 7 | `_distinct_trust_messages` dedup, `fold.py:300-304` | none | N/A, no information lost |
| 8 | `fallback_link` (`fold.py:364-366`) and `citation_id` (`fold.py:361`) dropped in the floor | NONE | NOT MET -- RR2-08 |
| 9 | Malformed events / unscoped signals / truncated tool results / non-fatal error classes, `fold.py:934-948` | notes | MET, but all evictable -- RR2-03 |
| 10 | Cost stripped by `sanitize_event_for_end_user` | by design | out of C5's scope |

The two sites the round set out to fix are now honest AT THE FLOOR. But the fix
introduced a new undisclosed-loss path (RR2-03: the fatal-error disclosure has
no second channel and is now evictable), a disclosure that fires when nothing
was dropped (RR2-05), and a guarantee stated in code and commit that the code
does not provide (RR2-04). Site 8 was never covered by any round.

## C10, "every clause is mutation-proven": NOT MET

`tracker/phase_4.3.md:269` already records this clause was false when written
(9 vacuous of 33 checked, ~27%). RR2-07 makes it 12, the 5th written by the
lead, and it is inside the newest commit -- the same pattern the phase file
itself names at line 342: "this phase has now had three review rounds and every
single one found its worst defect inside the previous round's fix".

## RR2-09 (MINOR) The gate-size figure in CLAUDE.md and BOARD.md is stale

`CLAUDE.md`: "its premise gate is green 42 of 42".
`tracker/BOARD.md:65`: "gate 42 of 42 mutation-swept, graphql suite 122".

Measured now:
```
57 tests collected in 0.08s          # test_phase_4_3_premise.py
55                                    # `def test_` declarations
194 passed                            # tests/system_03_search_agent/adapters/graphql
```
`venv/bin/python tracker/check_doc_drift.py --check` reports
`ok: 10 facts computed | 0 stale | 0 structural`, i.e. the drift checker does
not track this number, so "0 stale" is not evidence for it. The "42 of 42
mutation-swept" phrase is also load-bearing and now doubly wrong: 42 is not the
arm count, and 33 of the arms were the only ones ever swept.

# BASELINE EVIDENCE

- Working tree: clean at start and at finish. `git rev-parse HEAD` =
  `1625bf1b96d8ef8495f41afd9e7522ba22c9a5a1`.
- `venv/bin/python -m pytest -q`: `6 failed, 3082 passed, 113 skipped, 1 xfailed`
  -- the six failures are the known live-network-gated
  `test_citation_trust_full_premise.py` cases, matching the commit's own claim.
- `venv/bin/ruff check src/`: All checks passed.
- `venv/bin/ruff check`: 18 errors, every one pre-existing and outside
  `adapters/graphql` (`.claude/skills/...`, `tracker/*.py`, three unrelated
  tool test files).
- Probe files were written under
  `tests/system_03_search_agent/adapters/graphql/test_zz_rereview_probe*.py`
  and MOVED OUT of the repository to the scratchpad at the end (not deleted;
  `rm` is blocked by `block-bash-delete.sh` and was not circumvented).
