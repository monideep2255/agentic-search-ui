# Build phase 5.0 adversary report

Role: unscripted adversary. Fresh context, no prior involvement in this phase.
Branch `phase/5.0-observability`, commit `c8a8e7d`.

Written incrementally. Every finding below was appended the moment it was
established, before any further verification or prose, per
`.claude/rules/self-eval-loop.md`'s write-first rule.

I never fix, triage, or close. The finder is never the closer.

## Rules I worked under

- No writes anywhere but this file. Nothing under `src/` was modified; every
  mutation was an in-process monkeypatch, restored.
- Nothing was POSTed to PostHog. Its configured credential is a `phx_`
  personal API key (F-5.0-12) and no probe of mine touched it.
- No real PII and no real credential was transmitted to LangSmith. Probes ran
  against the redaction functions and assembled payloads directly, with the
  key emptied.
- Stand-in secrets are `uuid.uuid4().hex`, never a real-looking literal.

## Findings

(appended below in the order established)

### A-5.0-01 (major): the str-subclass family F-5.0-22 closed in two functions is still open in the third, `redact_params`

What I did. F-5.0-22 fixed `classify_error_code` and `_safe_error_class` by
replacing `isinstance(value, str)` with `type(value) is str`, because a `str`
subclass can override the very methods those guards call. `redact_params`,
`_is_secret_key` and `_redact_value_string` were NOT changed and still use
`isinstance`. I passed a `str` subclass through `params`, in both positions.

Reproduction, `scratchpad/p1_audit_params.py`, arms A1 and A2:

```python
class LyingKey(str):
    def lower(self): return "harmless"          # _is_secret_key calls .lower()

class LyingValue(str):
    def __contains__(self, o): return False     # _redact_value_string's early return

record_tool_call(tool="probe", layer=2, endpoint="e", latency_ms=1.0,
                 params={LyingKey("api_key"): SECRET})
record_tool_call(tool="probe", layer=2, endpoint="e", latency_ms=1.0,
                 params={"endpoint": LyingValue("https://h/x?api_key=" + SECRET)})
```

What happened, with the populate-check satisfied on every arm (each wrote
exactly one line, and the two controls on the same run wrote a line with the
secret ABSENT, so the sink and the redactor were both demonstrably working):

```
[CONTROL plain api_key value]              wrote=1  SECRET_PRESENT=False
[CONTROL embedded assignment]              wrote=1  SECRET_PRESENT=False
[A1 key subclass overriding lower()]       wrote=1  SECRET_PRESENT=True
[A2 value subclass overriding __contains__] wrote=1 SECRET_PRESENT=True
```

A1's written line: `"params": {"api_key": "<secret>"}`, under a key literally
named `api_key`, in the append-only sink.

Why it matters. The phase's own record says this family was found and closed.
It was closed at two of the three sites that need it. `_is_secret_key` is the
function BOTH the key rule and the value rule delegate to, so it is the single
highest-value target of the three, and it is the one left on `isinstance`.

Severity: major. Reachability is the mitigating half (a real call site would
have to construct a `str` subclass), and the exposure is the highest available
in this system: an unscrubbable file.

### A-5.0-02 (major): THE FIFTH FAMILY. A non-`str` object bypasses the redactor entirely and is stringified into the line afterwards by `json.dumps(default=str)`

This is the one the brief predicted, and it needs no subclass and no
overridden dunder. It is not a scanner gap. It is an ORDERING gap.

What I did. `redact_params` inspects `dict`, `list` and `str` and returns
"non-dict, non-list, non-string leaves ... unchanged". `record_tool_call` then
serializes the whole entry with `json.dumps(entry, default=str)`. So any
object that is not one of those three types is handed past every redaction
rule as an opaque leaf, and is only converted to text at write time, by which
point nothing is looking at it.

Reproduction, `scratchpad/p1_audit_params.py`, arm A3b:

```python
class Deferred:                       # any object at all, no dunder tricks
    def __str__(self):
        return "postgresql://kg_reader:" + SECRET + "@host/db"

record_tool_call(tool="probe", layer=2, endpoint="e", latency_ms=1.0,
                 params={"endpoint": Deferred()})
```

What happened (populate-check: one line written; the two controls in the same
run redacted their secrets correctly):

```
[A3b non-str leaf under innocuous key] wrote=1  SECRET_PRESENT=True
  "params": {"endpoint": "postgresql://kg_reader:<secret>@host/db"}
```

The identical DSN passed as a plain `str` under the same key IS redacted. The
only difference is the type at redaction time.

Note the near miss that shows the shape clearly: the same object under the key
`dsn_obj` WAS redacted (`SECRET_PRESENT=False`), because the key-name rule
fired on `dsn` before the value type ever mattered. The value rule, the one
F-5.0-08 and F-5.0-13 exist to provide, is the half that is structurally
unreachable for a non-`str`.

Why it matters. Every previous defeat in this phase was "something upstream
consumed the credential before the check saw it". This is the same sentence
with a different upstream: the TYPE SYSTEM consumed it. `default=str` is the
thing that re-materializes it, after redaction is over. Real candidates for a
non-`str` leaf in `params` are ordinary: a `pathlib.Path`, a `yarl`/`httpx.URL`,
a `psycopg2` DSN wrapper, a `datetime`, an enum, an exception object, any model
object a future caller drops into a params mapping. `httpx.URL.__str__` returns
the full URL including the query string, which is exactly the F-5.0-08 shape.

Severity: major. I would rate it critical if a shipped call site passed a
non-`str` leaf today; see A-5.0-09 for what I could establish about that.

### A-5.0-03 (major): `endpoint`, `tool` and `authorization` reach the append-only line with NO redaction and NO bound of any kind

What I did. Read `record_tool_call`'s body, then wrote to each field directly.
`params` gets `redact_params` plus `_bounded`. `error_code` gets a closed
vocabulary. `error_class` gets an identifier shape guard and a length cap.
`tool`, `endpoint` and `authorization` get NOTHING: each is placed into the
entry dict verbatim.

Reproduction, `scratchpad/p1_audit_params.py`, arms A4 and A6:

```python
record_tool_call(tool="probe", layer=2,
                 endpoint="https://h/x?" + KEYNAME + "=" + SECRET,
                 latency_ms=1.0)
record_tool_call(tool=KEYNAME + "=" + SECRET, layer=2, endpoint="e",
                 latency_ms=1.0, authorization="scheme-" + SECRET)
```

What happened, populate-check satisfied (one line each, and controls in the
same run redacted correctly):

```
[A4 endpoint field]     wrote=1  SECRET_PRESENT=True
  "endpoint": "https://h/x?<credential query parameter, value intact>"
[A6 tool/authorization] wrote=1  SECRET_PRESENT=True
```

Why it matters, and this is the part I want the lead to sit with. F-5.0-08 was
filed as CRITICAL and its statement was, verbatim, that "the `url` at the
transport chokepoint carries the secret" and "a field named `endpoint` or `url`
holding that URL is not redacted by anything". The fix that closed it was
`ncbi_transport._endpoint_for_audit`, which is a CALLER-side fix: it stops ONE
of three chokepoints from handing the sink a raw URL. The sink ITSELF is
exactly as defenceless as the day F-5.0-08 was filed. The other two
chokepoints, and every future caller, are one careless argument away from
reproducing the original critical, and no arm at the sink would notice.

`authorization`'s own docstring states the rule it does not enforce: "the NAME
of the credential used ... Never the credential value itself (PRD)". Build
phase 4.15's recorded lesson is that a confident sentence describing a check
that is not there is the exact defect class that ships. This is one.

Separately, `production-standards`' multi-agent pipeline gate requires
`maxLength` on every string field, in this repository's own words "required,
not optional ... they cap the blast radius". Three string fields on this sink
have none. See A-5.0-06 for what the absence of a bound does on its own.

Severity: major. It is the reintroduction surface for a finding this phase
already rated critical, and the only thing standing in front of it is that
today's callers happen to behave.

### A-5.0-04 (major): `record_ids` is untrusted external content, written unredacted and unbounded

What I did. `record_ids` is documented as "identifiers the call returned, for
example a list of NCBI UIDs or graph node ids". That means its contents come
from a live NCBI or enrichment API response, which
`.claude/rules/ai-security-standards.md` classifies as untrusted external
content by name. `record_tool_call` does `list(record_ids)` and nothing else:
no `redact_params`, no `_bounded`, no element type check, no `maxItems`.

Reproduction, arm A5:

```python
record_tool_call(tool="probe", layer=2, endpoint="e", latency_ms=1.0,
                 record_ids=[KEYNAME + "=" + SECRET, Deferred()])
```

What happened (populate-check: one line written):

```
[A5 record_ids field] wrote=1  SECRET_PRESENT=True
  "record_ids": ["<credential assignment intact>",
                 "postgresql://kg_reader:<secret>@host/db"]
```

Both elements landed verbatim. The second is also A-5.0-02's deferred-`__str__`
object, showing the two compose: `record_ids` has neither the redactor nor the
serializer guard.

Why it matters. `params` is caller-assembled and therefore at least
partly under this repository's control. `record_ids` is the one field on the
line whose contents are, by design, whatever a third party returned. It is the
field on this sink with the strongest claim to a `maxItems` and a per-element
bound, and it is the field with the fewest controls of any on the line.

Severity: major.

### A-5.0-05 (major): one unserializable value in `record_ids` silently DELETES the whole audit line

What I did. `params` is protected by `_bounded`, which wraps its `json.dumps`
in `try/except (TypeError, ValueError)` and substitutes a disclosure marker.
`record_ids` has no such wrapper, and the FINAL `json.dumps(entry, default=str)`
that builds the line is inside `record_tool_call`'s blanket
`except Exception`. So a value the serializer refuses does not degrade the
field, it kills the record.

`default=str` rescues most objects, but it is never consulted for a
non-string dict KEY, so that is the shape I used:

```python
record_tool_call(tool="probe", layer=2, endpoint="e", latency_ms=1.0,
                 record_ids=[{("a", "b"): 1}])
```

What happened:

```
[A7 unserializable record_ids] lines written=0
tool-call audit write failed for tool=probe (TypeError)     <- stderr, that is all
```

Populate-check: this is a negative result, so it needs one. The same process
wrote 11 other lines to the same file before and after this call, so the sink
was demonstrably working; the zero is this call's, not the harness's.

Why it matters. This is not a leak, it is the opposite failure and it is worse
for an AUDIT record specifically. The line the operator would use to
reconstruct what happened is the line that does not exist, the only trace is a
`logger.warning` naming an exception class with no arguments, and the sink's
own contract in `tracker/phase_5.0.md` is one line per Layer 1/2/3 access.
"Never raises" is satisfied. "Always records" was never separately stated, and
this is the gap between the two.

An adversary reading of it: any input that can steer the SHAPE of a returned
identifier collection into something non-serializable removes its own audit
record, and the removal is indistinguishable from the call never happening.

Severity: major. Silent, total loss of the record that exists to be durable.

### A-5.0-06 (minor): the `params` size cap measures one serialization and writes a different one

What I did. `_bounded` computes `json.dumps(redacted, default=str)`, measures
THAT, and on success returns `redacted`, the original object graph. The line is
then built by a SECOND `json.dumps(entry, default=str)`. For any leaf whose
`__str__` is not pure, the value measured and the value written are different
values. Classic time-of-check / time-of-use, on a size cap.

```python
class GrowingStr:
    def __init__(self): self.n = 0
    def __str__(self):
        self.n += 1
        return "x" if self.n == 1 else ("Q" * 200000 + SECRET)

record_tool_call(tool="probe", layer=2, endpoint="e", latency_ms=1.0,
                 params={"payload": GrowingStr()})
```

What happened:

```
[A8 size-cap TOCTOU] wrote=1  bytes=200296  cap=4096  SECRET_PRESENT=True
```

A 200 KB payload written under a 4096-byte cap, carrying the stand-in
credential, with no `_audit_note` and nothing to tell a reader the cap was
bypassed.

Why it matters. It is contrived on its own; I file it because it is the same
root cause as A-5.0-02 seen from the other side. `_bounded`'s own docstring
argues carefully that redaction must run BEFORE truncation, which is correct,
and then the code measures a stringification that the write does over again.
The durable form of both fixes is the same one: serialize once, redact the
serialized text, write the bytes you measured.

Severity: minor, on reachability alone.

### A-5.0-07 (CRITICAL, pending the reachability check in A-5.0-08): `redact_payload` walks `dict` and `list` and nothing else, so the `Query` and `RequestContext` PYDANTIC OBJECTS pass through untouched

This is the same family as A-5.0-02 in the other module, and it lands on the
one boundary Section 20.1 names by name.

What I did. `GraphState` is a `TypedDict` (`core/state.py:159`), so at runtime
it is a plain `dict`, but its VALUES are not: `query` holds a `Query` model
INSTANCE and `context` holds a `RequestContext` model INSTANCE. `redact_payload`
recurses on `dict` and `list`, and its final line returns everything else
unchanged. A Pydantic model is neither.

Reproduction, `scratchpad/p2_tracing.py`, arms C1/C2 (controls) and B1:

```python
q   = Query(text="...", trace_id="t-1", owner_id=OWNER, user_id=USER,
            session_id=SESSION, audience_depth="researcher")
ctx = RequestContext(surface="web_ui", operator_mode=False, session_memory=mem)

redact_payload(q.model_dump())                       # the shape the tests use
redact_payload({"query": q, "context": ctx, "seq": 0})   # the shape LangGraph has
```

What happened. The populate-check is the control pair: the dict forms redact
correctly in the same run, so the redactor is working and the difference is the
type alone.

```
[C1 plain dict of Query fields]         LEAKED=none
[C2 GraphState as dicts]                LEAKED=none
[B1 GraphState with real model objects] LEAKED=['owner_id','session_id',
                                                'session_memory','user_id']
   {"query": {"text": "...", "session_id": "session-<id>", "trace_id": "t-1",
              "user_id": "user-<id>", "owner_id": "owner-<id>", ...},
    "context": {"surface": "web_ui", "session_m...
[B1b bare Query object at the root]     LEAKED=['owner_id','session_id','user_id']
```

Every marker Section 20.1 forbids on a trace, plus session-memory content,
survives redaction whole.

Why it matters. F-5.0-03, this phase's own critical, is stated as: LangGraph
"captures `GraphState`, which carries `Query.owner_id`, `Query.user_id` plus
`RequestContext.session_memory`". The redactor built to close it was written
and tested against `Query`-shaped DICTS. `GraphState` does not contain
`Query`-shaped dicts. It contains `Query` objects. The test suite and the
threat are describing two different data structures, and the tests construct
the one that is safe.

This also silently disables F-5.0-09's fix: `_looks_like_model` can never fire
on a payload whose model values are objects, because it only ever sees the
outer `GraphState` key set (`query`, `context`, `harness`, `seq`, ...), which
intersects `_QUERY_FIELDS` in zero places.

Severity: CRITICAL if langsmith's anonymizer receives the raw objects, MAJOR if
langsmith serializes before calling it. That single question is A-5.0-08 and I
went and answered it; read that finding next.

### A-5.0-09 (major): `redact_payload` does not walk a tuple, a set, or a mapping proxy, and each of the three carries PII to the wire

Same probe, arms B2, B2b, B2c:

```
[B2  tuple]                 LEAKED=['owner_id','user_id']
   {"batch": [{"owner_id": "owner-<id>", "user_id": "user-<id>"}]}
[B2b set of strings]        LEAKED=['owner_id']
[B2c MappingProxyType]      LEAKED=['owner_id']
```

The tuple case is the one that matters. `redact_payload` returns the tuple
unchanged because it is not a `list`, and the JSON serializer downstream then
renders it AS a list, so the value arrives at LangSmith in exactly the shape
the redactor would have walked if only it had been asked to. Nothing about
the wire format differs; only the Python type at redaction time does.

Tuples are not exotic in this payload. `dict.items()` views, `zip` results,
`namedtuple`s and frozen dataclass containers all serialize this way, and
LangGraph's own channel plumbing hands tuples around freely.

The set and mapping-proxy cases degrade to `str(...)` at serialization, which
is arguably worse than passing the structure through: the identifier is still
there, and it is now inside an opaque string that no downstream scrubber
would recognize as structured data.

Populate-check: the same run's C1/C2 controls redact correctly, so the
redactor was live for every one of these.

Severity: major.

### A-5.0-10 (major): the two redactors in this phase disagree about what a secret is, and the tracing one is much the weaker

What I did. `audit.py` uses `_SECRET_KEY_MARKERS = (key, token, secret,
password, credential, auth, dsn, connection)`. `tracing.py` uses a completely
separate `_PII_KEY_CATEGORIES` list. I fed the tracing redactor one key name at
a time (probe arm B3) and recorded which pass through:

```
token          -> PASSES THROUGH      auth             -> PASSES THROUGH
api_token      -> PASSES THROUGH      account_id       -> PASSES THROUGH
secret         -> PASSES THROUGH      ip_address       -> PASSES THROUGH
authorization  -> PASSES THROUGH      full_name        -> PASSES THROUGH
bearer         -> PASSES THROUGH      postal_address   -> PASSES THROUGH
jwt            -> PASSES THROUGH      dsn              -> PASSES THROUGH
cookie         -> PASSES THROUGH      connection_string-> PASSES THROUGH
```

Fourteen of fourteen. `secret` and a bare `token` are not covered because the
category list spells only the compound forms (`sessiontoken`, `accesstoken`,
`authtoken`, `refreshtoken`) and the check is `category in normalized`, which
runs the wrong direction for a SHORTER key: `"accesstoken" in "token"` is
False.

Why it matters. `audit.py`'s own comment argues at length that the marker list
is "deliberately broad" because "a false positive here costs a placeholder in a
log line, and a false negative costs a live credential". The identical
asymmetry applies to a trace, arguably harder, since a trace leaves this
process entirely and lands in a third-party service. The tracing module took
the opposite trade with no stated reason, and there is nothing in either file
pointing at the other.

`redact_payload` is also wired to `hide_metadata`, so this list is the only
thing standing between an arbitrary metadata dict and LangSmith.

Severity: major.

### A-5.0-11 (minor): a non-`str` dict key defeats the tracing redactor entirely

Arm B5: `redact_payload({b"owner_id": OWNER})` returns the value untouched.
`_normalize_key` returns `""` for a non-string key by design, and its docstring
says so, which makes this documented rather than hidden. What is not documented
is that `_allowlist_for` cannot save it either, since the bytes key is not in
`_QUERY_FIELDS`. Contrast `_is_secret_key` in `audit.py`, which has the same
`isinstance` gate and the same outcome.

Populate-check: the string-keyed form of the identical dict redacts in the same
run.

Severity: minor. I file it because "the redactor returns the empty string for a
key it cannot classify and therefore never redacts a value it cannot classify"
is a fail-OPEN default written down as if it were a safety property.

### A-5.0-12 (informational, a NEGATIVE result worth recording)

The `str`-subclass key attack that defeats `audit.redact_params` (A-5.0-01) does
NOT defeat `tracing.redact_payload`. Arm B4: a `LyingKey("owner_id")` whose
`.lower()` returns `"harmless"` is still redacted, because a `str` subclass
hashes and compares equal to its base value, so `key_set <= _QUERY_FIELDS`
holds and the structural default-deny rule fires independently of the category
pass. Two independent layers is what saved it. The audit module has only one.

### A-5.0-08 (the reachability check A-5.0-07 promised, and it CORRECTS A-5.0-07 and A-5.0-09 downward on one path and confirms them on another)

Filed after A-5.0-09 through A-5.0-12 because I established it after them; the
report is append-only in discovery order and I am not reordering it.

What I did. Read the installed langsmith 0.10.10 `client.py` rather than
assuming, then drove its four private hooks directly with a Client constructed
against an unreachable host and an EMPTY credential
(`scratchpad/p3_langsmith_paths.py`). No request was issued by any probe.

What the source says, `client.py:2724-2771`:

| Hook | What it hands the anonymizer |
|---|---|
| `_hide_run_inputs` (2724) | `_orjson.loads(_dumps_json(inputs))`, a JSON ROUND-TRIP first |
| `_hide_run_outputs` (2734) | same round-trip first |
| `_hide_run_error` (2744) | `self._anonymizer({"error": error})`, the raw string wrapped |
| `_hide_run_metadata` (2766) | `self._hide_metadata(metadata)`, the RAW OBJECT, no round-trip |

Measured, all four:

```
1. inputs, GraphState with real Query/RequestContext objects
     owner_id leaked? False      query value type after hook: dict
     -> {'query': {'text':'q','session_id':'[redacted]','trace_id':'t',
                   'user_id':'[redacted]','owner_id':'[redacted]',...}}
2. inputs, a tuple of dicts        owner_id leaked? False
3. METADATA, same two shapes       owner_id leaked? TRUE
     -> {'query': Query(text='q', ..., user_id='user-<id>',
                        owner_id='owner-<id>', ...),
         'path': ({'owner_id': 'owner-<id>'},)}
5. populate-check (control)        plain PII dict on inputs -> redacted
```

So, stated plainly and against my own two earlier findings:

- ON THE INPUTS AND OUTPUTS PATH, A-5.0-07 and A-5.0-09 are NOT reachable.
  langsmith's own pre-serialization normalizes the Pydantic model to a dict and
  the tuple to a list before `redact_payload` ever runs, and the redactor then
  works correctly. The defect in `redact_payload` is real and the payload that
  reaches it in production is not the one I feared. I am recording this
  correction rather than leaving the stronger claim standing.
- ON THE METADATA PATH THEY ARE FULLY REACHABLE, because `_hide_run_metadata`
  performs no round-trip. `redact_payload` is wired to `hide_metadata`
  deliberately, with a paragraph in `build_traced_client` explaining why, and
  on exactly that parameter its type gaps are live. LangGraph populates run
  metadata itself (`langgraph_node`, `langgraph_step`, `langgraph_path`, which
  IS a tuple, `thread_id`, plus everything under `configurable`), so raw
  non-dict, non-list values on this path are the normal case, not a contrived
  one.

Revised severity for A-5.0-07 and A-5.0-09: major, on the metadata path, and
latent on inputs and outputs where they depend on a THIRD-PARTY LIBRARY'S
internal choice to serialize first. That dependency is itself worth naming: the
safety of the inputs path is currently a property of langsmith 0.10.10's
implementation, not of any code in this repository, and nothing in this
repository records that or pins the version against it.

### A-5.0-13 (CRITICAL): a run's ERROR string reaches LangSmith completely unredacted, carrying exactly the credentials this phase spent four rounds removing from the audit sink

This is the finding I would fix first.

What I did. `_hide_run_error` (client.py:2744) DOES route the error through the
configured anonymizer, wrapped as `{"error": <string>}`. `redact_payload` walks
dicts and lists and returns everything else unchanged, and a string is
"everything else": it has no string-scanning rule of any kind. So the hook
fires, the anonymizer runs, and the string comes back byte-identical.

Reproduction, `scratchpad/p3_langsmith_paths.py` arm 4, with two messages of
the exact shapes this repository's own findings say it produces:

```python
client._hide_run_error(
    "Client error '401 Unauthorized' for url "
    "'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=gene&term=BRCA1&<credential query parameter>'")

client._hide_run_error(
    "connection failed: postgresql://kg_reader:<secret>@46.225.128.133:5432/ncbi_kg")
```

Result:

```
secret leaked in run error?          True
   -> Client error '401 Unauthorized' for url 'https://eutils.ncbi.nlm.nih.gov/
      entrez/eutils/esearch.fcgi?db=gene&term=BRCA1&<credential intact>'
DSN password leaked in run error?    True
```

Populate-check: arm 5 in the same run, same Client, same anonymizer, redacts a
plain PII dict correctly. The anonymizer is wired and firing; it simply does
nothing to a string.

Why this is the one. Read these two facts next to each other:

- This phase spent FOUR review rounds and findings F-5.0-13, F-5.0-14, F-5.0-19
  and F-5.0-21 establishing that an exception message in this system carries
  URLs with `api_key` appended and DSNs with the `kg_reader` password, and
  ended by removing free text from the audit sink ENTIRELY, because no scanner
  could be made safe. `audit.py`'s module docstring is four screens of that
  argument.
- The identical exception message, formatted by
  `langsmith.run_helpers._format_error_with_exceptions_to_handle` as
  `repr(exc)` plus a traceback, is transmitted to a third-party SaaS on every
  failed node, with a redactor attached that does not look at strings.

The audit sink is a local file. LangSmith is off-box, retained, and shared. The
phase hardened the weaker exposure to a structural bound and left the stronger
one with no control at all.

`httpx.HTTPStatusError.__str__` embeds the request URL, and
`ncbi_transport._append_api_key` puts the credential in that URL's query
string, so this is not a hypothetical message shape: it is the one the shipped
transport produces. The `_endpoint_for_audit` fix that closed F-5.0-08
deliberately strips the query string for the AUDIT line and has no effect here.

langsmith's own docstring at `client.py:2745-2757` says this in as many words:
the error string "can capture credentials the user never explicitly logged --
e.g. an HTTP client exception whose request-object repr includes an
Authorization header", and that this is why it routes error through the
anonymizer at all. The library handed this repository the hook. The anonymizer
this repository supplied declines it.

Severity: CRITICAL. Reachable on the normal failure path of the shipped
transport, with a real `LANGSMITH_API_KEY` now present and tracing enabled,
sending a live credential off-box.

### A-5.0-14 (minor): `redact_payload` has no string rule at all, and `audit.py` has one it could have reused

Arm 6 of the same probe, stated separately because it is the general form of
A-5.0-13 rather than the one instance:

```python
redact_payload({"note": "here is a DSN postgresql://u:<secret>@h/db and "
                        "<credential assignment>"})   # returned unchanged: True
```

`audit.py` ships `_redact_value_string`, `_redact_netloc_credentials` and
`_redact_secret_assignments`, which catch both of those shapes, are already
tested, and are in the same package. `tracing.py` imports none of them and
reimplements neither. Any string anywhere in a traced payload, a tool result
echoed into a node output, a retrieved passage, a formatted error, is passed to
LangSmith exactly as it arrived.

I file this at minor because on the inputs and outputs path
`_SECRET_KEY_MARKERS`-style key names would usually catch a credential first,
and because A-5.0-13 already carries the reachable instance. It belongs on the
record as the root cause of that one.

### A-5.0-15: A-5.0-13 CONFIRMED END TO END ON THE WIRE, through the real `traced_graph_run`, a real LangGraph run and the real shipped client

I did not want to file a critical off a private hook, so I built the whole
path: a real `StateGraph`, invoked inside the shipped
`tracing.traced_graph_run` with the shipped `build_runnable_config`, state
carrying real `Query` and `RequestContext` objects, and captured the ACTUAL
multipart body langsmith assembles.

Containment: `LANGSMITH_ENDPOINT` pinned to `http://127.0.0.1:1`,
`requests.adapters.HTTPAdapter.send` replaced with a recorder that captures the
body and then raises `ConnectionError` without performing any I/O, and the key
a `uuid4` stand-in. Nothing left this machine and no real credential was used.
Script: `scratchpad/p5_wire.py`.

Two runs, identical except for what the single node does:

```
=== A. successful run ===
[A success] captured 4 outbound request(s), 14586 bytes of body
    owner_id                 ON THE WIRE: False
    user_id                  ON THE WIRE: False
    session_memory thread    ON THE WIRE: False
    credential in error      ON THE WIRE: False

=== B. the node raises, with the message shape ncbi_transport produces ===
[B failure] captured 4 outbound request(s), 28650 bytes of body
    owner_id                 ON THE WIRE: False
    user_id                  ON THE WIRE: False
    session_memory thread    ON THE WIRE: False
    credential in error      ON THE WIRE: True
    context: ..."RuntimeError(\"Client error '401 Unauthorized' for url
      'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
       ?db=gene&term=BRCA1&<credential intact>'\")Trac...
```

Read the two together, because they are each other's populate-check and each
other's control:

- The PII redaction this phase built WORKS. All three account markers are
  absent from 14 KB and 28 KB of real wire payload. That is a genuine
  achievement and I want it on the record as measured, not assumed.
- The SAME payload, on the same run, carries a credential in cleartext, because
  it travelled in the run's `error` field, which the anonymizer receives and
  does nothing to.

The capture mechanism is identical in both runs and finds nothing in A, so
"absent" means absent and "present" means present.

Severity: CRITICAL, confirmed. A real `LANGSMITH_API_KEY` is now present in
this environment and tracing is enabled, so this is a live path, not a
prospective one.

### A-5.0-16 (NEGATIVE RESULT, the no-credential path HOLDS, measured at the socket)

Target 3 of my brief. I tried to make it call anyway and could not.

What I did. Replaced `socket.socket.connect` with a recorder that appends the
address and refuses, then drove a real LangGraph invocation inside the shipped
`traced_graph_run` three times. Script: `scratchpad/p4_nocred.py`.

```
[ARM1 flag=true key=absent]      tracing_enabled=False  socket connects=0  []
[ARM2 flag=true key=whitespace]  tracing_enabled=False  socket connects=0  []
[ARM3 POPULATE-CHECK key=present endpoint=127.0.0.1:1]
                                 tracing_enabled=True   socket connects=3
                                 [('127.0.0.1',1), ('127.0.0.1',1), ('127.0.0.1',1)]
```

ARM3 is the populate-check and it is the reason ARM1 and ARM2 mean anything:
the same harness, the same graph, the same wrapper, one env value different,
and the spy records three connects. A zero from ARM1 is therefore an absence,
not a broken instrument. ARM2 also confirms `_first_set`'s whitespace-stripping
holds for the shape `env.example` actually ships (`LANGSMITH_API_KEY=` empty).

I also checked the two ways I expected to get around it and neither exists
here: there is exactly one graph invocation site in `src/`
(`core/run.py`, both forms, both wrapped), and the only thread boundaries in
the codebase are `asyncio.to_thread` calls in `tools/cypher_query.py`, which
COPY the context and therefore carry both the tracing contextvar and the
audit `trace_id` var across. A bare `threading.Thread` would not, and would
escape both the OFF override and the redacting client into langsmith's
env-driven default client; there isn't one today, and it is worth knowing that
is the shape that would break this.

### A-5.0-17 (minor): the premise gate's no-credential arm asserts a PROXY, and the property it stands for is one library version away

`test_observability_premise.py:367-411` asserts that `build_traced_client` is
never CALLED. The goal contract in `tracker/phase_5.0.md` asks for "a
no-credential arm that asserts zero outbound calls, not merely that no
exception was raised". "No client is constructed" is a proxy for "no call is
made", not the property, and it is the safety-by-proxy shape build phase 4.3
shipped as a critical twice and build phase 4.7 hit again.

The arm does carry a real populate-check (it wraps the live `tracing_enabled`
and counts consultations), so it is a good arm of its kind. My point is
narrower: nothing in this suite ever observes a socket, so if a future
langsmith release, or an OTEL exporter, or a stray `Client()` anywhere else
began emitting under `tracing_context(enabled=False)`, every arm here would
stay green. A-5.0-16 shows the socket-level assertion is about fifteen lines of
work and needs no live service.

Severity: minor. The property is TRUE today, measured. The arm is not the one
that would tell you when it stops being.

### A-5.0-18 (minor): a fresh `langsmith.Client` is built per graph invocation, each one issuing its own `GET /info` and leaving a background flush thread behind

Observed incidentally in every arm above: constructing a `Client` triggers an
immediate outbound `GET /info` (visible in the probe output), and each client
carries its own queue and background ingestion thread. `traced_graph_run` calls
`build_traced_client()` on every ON invocation, and nothing ever closes the
client.

On the ON path, that is one extra outbound round trip and one thread per user
query, on the request path, with no reuse and no cleanup. `analytics.py`'s
sibling decision, an `httpx.AsyncClient` scoped to exactly one call and closed,
is deliberate and documented; this one is not discussed anywhere I could find.

Severity: minor. Not a correctness or secrecy defect, and I flag it because
"one client per query, never closed" is the shape that turns into a file
descriptor or thread exhaustion report weeks later rather than now.

### A-5.0-19 (major): TWO PROCESSES writing the sink CORRUPT it, and the only reason it does not happen today is the field caps that A-5.0-03 and A-5.0-04 show are absent

What I did. `audit.py`'s module docstring argues carefully that a
`threading.Lock` "removes the dependency on that [POSIX atomic-append]
guarantee rather than relying on it, which is what Section 20.3's 'one writer
per process' line actually asks for". A `threading.Lock` is per-PROCESS. I ran
four PROCESSES against one sink.

`scratchpad/p6_hostile_ops.py` arm O7 and `scratchpad/p7_mp_small.py`:

```
four processes x 300 lines, ~400 byte lines:   expected=1200 got=1200  unparseable=0
four processes x 300 lines, ~20 KB lines:      expected=1200 got=924   unparseable=251
(and O7, four processes x 200 lines, 20 KB:    expected=800  got=636   unparseable=153)
```

A quarter of every line destroyed, interleaved into each other, in an
APPEND-ONLY file that by contract is never rewritten. The corruption is
permanent by design.

The small-line control is what makes this precise rather than alarmist: below
the ~8 KB text-buffer size, `handle.write(line)` plus `handle.write("\n")`
flushes as one `write(2)` and POSIX `O_APPEND` keeps it whole. Above it, Python
emits several syscalls and the interleaving begins.

So this defect is only reachable through a line larger than the buffer, and the
only three fields that can produce one are `tool`, `endpoint` and `record_ids`,
the exact three A-5.0-03 and A-5.0-04 report as having no cap. `params` cannot
do it: `_MAX_PARAMS_BYTES` stops it at 4096. The caps and the lock are one
control between them, and each is documented as if it stood alone.

Two processes on one sink is not hypothetical here. `s3-kgx-export` is a
separate CLI process (build phase 4.2) that reaches the graph through the same
audited `execute_cypher` chokepoint and resolves the same default
`logs/tool_audit.jsonl`, so running an export while the API is serving is two
writers by ordinary use. Any multi-worker uvicorn configuration is a third.

Severity: major. I would call it critical if the field caps were present and it
still corrupted, or if a real line today exceeded 8 KB; today it needs one of
the missing caps to be exercised first.

### A-5.0-20 (minor): a value's `__str__` runs TWICE per record, so a side effect is duplicated and the record can differ from the record that was measured

Arm O2. An object in `params` whose `__str__` writes its own audit line:

```
new lines=3  inner=2  outer=1   (no deadlock)
```

The INNER line was written twice, and both times BEFORE the outer line it is
nested inside. The cause is the same double serialization A-5.0-06 reports:
`_bounded` calls `json.dumps` once to measure, and `record_tool_call` calls it
again to write. No deadlock, because no caller code runs while `_write_lock` is
held; the lock is correctly scoped.

Severity: minor, and I file it mostly as a second, independent witness for
A-5.0-06's root cause: the value that is measured is not the value that is
written, and anything with a side effect proves it directly.

### A-5.0-21 (informational, THREE NEGATIVE RESULTS the sink passes cleanly)

I tried to break the never-raises contract and could not, and I tried to forge
a line and could not. Recording these because a report of only failures is not
an accurate picture.

- LINE FORGERY IS NOT POSSIBLE (arm O1). `endpoint` containing embedded
  newlines and a complete fake JSON object, plus `params` values carrying CR,
  LF, a NUL byte and an astral-plane emoji: one line written, it parses, and
  zero forged lines were produced. `json.dumps` escapes every control
  character, so no caller-controlled string can terminate a line early. Given
  A-5.0-03 (no bound, no redaction on `endpoint`), this was the first thing I
  tried, and the serializer holds it.
- NEVER-RAISES HOLDS on a hostile filesystem (arms O3, O4). Sink path is a
  DIRECTORY: no raise, `IsADirectoryError` logged by class name only. Log
  directory chmod 0500: no raise, `PermissionError` logged by class name only,
  no file created. Both degrade exactly as the contract promises.
- IN-PROCESS CONCURRENCY IS CLEAN (arm O6). Eight threads, 150 lines each, every
  line 20 KB: 1200 of 1200 present, zero unparseable. The lock does its job
  within a process. It is only the cross-process case (A-5.0-19) that fails.

### A-5.0-22 (minor): the sink follows a symlink and appends into whatever it points at

Arm O5. `TOOL_AUDIT_LOG_PATH` set to a symlink pointing at an existing file:
`path.open("a")` follows it and appends audit lines into the target, leaving
the pre-existing content in place above them.

`TOOL_AUDIT_LOG_PATH` is an operator-set environment variable, so this is not
an attacker-reachable primitive on its own. It matters because of what the sink
IS: an append-only record with no `O_NOFOLLOW`, no ownership check, and a
default path (`logs/tool_audit.jsonl`) inside a working directory that a
deployment may share. If anything can plant that symlink first, every
subsequent audit line, including the `authorization` identifiers and
`record_ids`, lands in a file of the planter's choosing.

Severity: minor, on reachability. Worth one line in the module's docstring,
which currently discusses log rotation carefully and symlinks not at all.

### A-5.0-23 (reachability confirmation for A-5.0-13 and A-5.0-15): tracing is LIVE in any real process, turned on by an import side effect

I wanted to know whether A-5.0-13 is a live path or a prospective one, so I
measured the actual on/off state a real process reaches. Booleans only; no
client was constructed, no graph was run, nothing was transmitted.
Script: `scratchpad/p9_ambient.py`.

```
before importing litellm:
   tracing_flag_set = False   key present = False   tracing_enabled = False
after importing litellm (F-2.1-04: it calls load_dotenv() at import time):
   tracing_flag_set = True    key present = True    tracing_enabled = True
```

`.env` on this branch holds a real 51-character `lsv2`-prefixed
`LANGSMITH_API_KEY` and `LANGCHAIN_TRACING_V2=true`. Neither is in the shell
environment, so a naive check says tracing is off. It is not: this
repository's own long-standing finding F-2.1-04 records that importing
`litellm` calls `load_dotenv()` at import time, and the harness imports
litellm on every run. One import flips `tracing_enabled()` from False to True.

So A-5.0-13's credential-bearing error string reaches LangSmith on the next
failed node of the next real query. It is not waiting on anyone to provision
anything.

I note in passing that "the feature's on/off state is decided by a third-party
package's import side effect" is itself worth someone's attention, though this
phase did not create it.

### A-5.0-24 (major): the analytics event is `await`ed INLINE on the query path, so a slow PostHog adds up to 4 seconds to a user's query

`core/run.py:346` is a bare `await capture_event(...)` in the run epilogue.
`capture_event` builds a fresh `httpx.AsyncClient` and POSTs with
`CAPTURE_TIMEOUT_SECONDS = 4.0`. There is no `create_task`, no background
queue, no fire-and-forget.

The goal contract in `tracker/phase_5.0.md` states the constraint: "Observability
is best-effort and never blocks or fails a user's query, following
`feedback/writer.py`'s existing discipline." The implementation satisfies "never
fails" precisely and carefully, and does not satisfy "never blocks" at all: an
unreachable or slow PostHog costs every single query up to the full timeout plus
DNS and connect time, on the user's request path, after the answer is already
computed.

`analytics_enabled()` is True in this environment right now (measured above), so
this cost is live, not conditional.

The same shape applies at `adapters/web_sse/app.py:1851`, the feedback endpoint's
`await capture_event(...)`.

Severity: major. A third-party analytics outage becoming user-visible latency on
every query is exactly the coupling a best-effort side channel exists to avoid,
and it is the one part of the constraint that no arm in the phase measures.

### A-5.0-25 (minor): `distinct_id` is the one value reaching PostHog that the allowlist does not govern, and its safety is a caller-provenance argument with no pinning test

`build_properties` is genuinely excellent: a closed schema, an allowlist not a
blocklist, per-key kinds, `bool` excluded from `count` because it subclasses
`int`. Nothing free-text can travel in `properties`.

`distinct_id` travels in the same body and goes through `_bounded_distinct_id`,
which truncates to 200 characters and applies no other rule whatsoever. Its
docstring asserts the value is "an opaque namespaced identifier, `user:<uuid>`
or `guest:<uuid>`, never an email address or another directly identifying
value", and then says plainly "this function only handles its LENGTH, not its
content".

That is the identical structure F-5.0-21 was filed for on `error_class`: the
field is safe because of what the CALLER passes, not because of what the guard
checks. F-5.0-21's fix was not to strengthen the guard, it was to PIN the caller
with `TestErrorClassCallSitesPassAClassNameLiteral`, an arm that parses the call
sites and turns red if one ever passes something else. `distinct_id` has no such
arm. `query.owner_id` is correct today; nothing keeps it correct.

Severity: minor, and it is a one-arm fix using a technique this phase already
built.

### A-5.0-26 (minor): the analytics and capture epilogues log `exc_info=True`, dumping the full exception text the modules underneath took care never to log

`observability/analytics.py` logs `type(exc).__name__` and never `str(exc)`,
and its `build_properties` docstring explains at length that the exception
MESSAGE "can carry exactly the caller-supplied content this function exists to
keep out of PostHog, so it must never reach a log line". `audit.py` applies the
same discipline. `feedback/writer.py` is cited as the source of it.

`core/run.py` then wraps those calls in handlers that log the full traceback:

```
core/run.py:313  "interaction capture failed ...", exc_info=True
core/run.py:362  (the analytics epilogue),          exc_info=True
core/run.py:430  "session memory not loaded ...",   exc_info=True
core/run.py:605, :775                                exc_info=True
```

`exc_info=True` writes `str(exc)` and every frame. Anything an inner module
declined to log is logged here instead, one frame up, including an httpx
exception carrying a request URL and an `UnsafePropertyError` whose message
embeds the rejected caller value via `!r`.

I file this as minor because these are application logs rather than the
append-only sink or a third-party trace, and because at least one of these
predates this phase. It belongs on the record because the phase's own argument
for the class-name-only rule is undermined at the call site directly above it.

### A-5.0-27 (major, and it partly UPDATES F-5.0-12): TWO different PostHog credentials of TWO different types are configured, and which one is live depends on load order nobody has written down

Measured, shapes only, never values:

| Source | Length | Prefix | PostHog's classification |
|---|---|---|---|
| `.env` on this branch | 52 | `phx_` | PERSONAL API key, account-wide read AND write |
| the shell environment | 47 | `phc_` | PROJECT token, designed to be public, write-only capture |

F-5.0-12 is filed against the `phx_` key and is open. The `phc_` key in the
shell is the CORRECT credential and matches the "Everything measured" table's
own row ("a real 47-character `phc_`-prefixed project key"), so the two
measurements in `tracker/phase_5.0.md` were both right, about different places.

What makes this worth a finding rather than a footnote: `python-dotenv` defaults
to `override=False`, so the shell wins ONLY WHERE THE SHELL HAS IT SET.
Unset that one shell export, or deploy to a host that has no `POSTHOG_API_KEY`
in its own environment while `.env` ships, and the ACCOUNT-WIDE PERSONAL KEY
becomes the live capture credential and is transmitted in the request BODY of
every capture POST. `analytics_enabled()` is True today and `capture_event`
sends `"api_key": api_key` in that body.

Per my brief I sent nothing to PostHog and made no request of any kind against
it. This finding is from reading configuration only.

I should disclose one thing for the lead's convergence bookkeeping: while
grepping the repository for `load_dotenv` I saw a single line of
`tracker/phase_5.0_judge_report.md` scroll past that appears to reach the same
conclusion. I did not open that file and my analysis above was already complete
when it appeared. Treat any overlap as independent convergence, with that
caveat stated rather than hidden.

Severity: major. One environment variable away from shipping an account-wide
read-write credential to a third party on every query.

### A-5.0-28: F-5.0-19's ACTUAL REACH, which was target 4 of my brief

The question I was asked: which real call sites can feed `params` a value of
the shape `url=https://host/x?api_key=<secret>`, the shape F-5.0-19 measured
passing through byte-identical?

I enumerated every `record_tool_call` call site in `src/` and every value each
one can put in `params`.

| Chokepoint | What it passes as `params` | Can a value be free text? | Can a value carry a CREDENTIAL today? |
|---|---|---|---|
| `ncbi_transport.execute_get` (2 sites) | `dict(params)`, the caller's query-parameter mapping | YES: `term`, `query`, `id` are model- and user-derived | NO |
| `graph_connection.execute_cypher` (2 sites) | `{"cypher": cypher, "params": params or {}}` | YES: `cypher` is a model-generated string | NO |
| `pathogen_ftp_transport` (4 sites) | `{"key_column": ..., "one_row_per_key": ...}` or nothing | NO, both are internal enum-ish values | NO |

So the two halves of the answer, and they point opposite ways:

- THE SHAPE IS REACHABLE. Three of the eight call sites can put arbitrary
  attacker- or model-influenced free text into a `params` value: an E-utilities
  `term`, a LitVar2 `query` (`litvar2_lookup.py:820` passes `{"query": query}`),
  and the whole generated `cypher`. A question crafted to make the planner emit
  `url=https://h/x?api_key=...` inside a term or a Cypher literal reaches
  `_redact_value_string` in exactly F-5.0-19's shape and passes through
  unredacted.
- NO CREDENTIAL REACHES IT. I traced every credential this system holds and
  none of them lands in a `params` VALUE. `NCBI_API_KEY` is appended by
  `_append_api_key` to the QUERY STRING, after `params` is captured, and
  `execute_get`'s own comment says so correctly. `GRAPH_QUERY_TOKEN` travels in
  a header (`graph_http_transport.py`). The graph DSN password is never
  serialized into a Cypher parameter. `LANGSMITH_API_KEY` and
  `POSTHOG_API_KEY` never touch a tool call.

CONCLUSION FOR THE LEAD: F-5.0-19's severity as filed is correct as a latent
defect and I would NOT raise it. What an attacker can get through it today is
their own text, echoed back into a local file, which is not a credential leak.
The path from "shape reachable" to "credential leaked" requires a future call
site to place a secret-bearing string in a `params` value, and the decision to
carry it open with a named owner looks right to me.

What I would change is where the attention goes. F-5.0-19 is a gap in a
BEST-EFFORT scanner over the ONE field on the line that already has both a
redactor and a size cap. `endpoint`, `tool` and `record_ids` (A-5.0-03,
A-5.0-04) have NEITHER, and `endpoint` is the field F-5.0-08's critical was
about. The phase has spent four rounds on the best-defended field on the line.

### A-5.0-29 (minor): the F-5.0-08 control exists as TWO copies that are not the same function, and nothing asserts they agree

`ncbi_transport._endpoint_for_audit` (line 1195) uses `urllib.parse.urlparse`.
`pathogen_ftp_transport._endpoint_for_audit` (line 98) uses
`urllib.parse.urlsplit`. The second's docstring says it deliberately mirrors
the first and explains why it is a copy rather than an import.

They do not agree. `urlparse` strips RFC 3986 path parameters from the last
segment into a separate field; `urlsplit` does not:

```
'https://h/a/b;jsessionid=Z?x=1'   urlparse -> h/a/b
                                   urlsplit -> h/a/b;jsessionid=Z
'https://h/p;q'                    urlparse -> h/p
                                   urlsplit -> h/p;q
```

Both still strip the query string, so neither leaks today and this is not the
F-5.0-08 leak returning. It is a drift risk on a security control that has been
duplicated: the two copies already differ in behaviour on the first input I
tried, and nothing anywhere asserts they behave the same.

This repository has already solved this exact problem once, well: build phase
4.11 copied `validate_cypher` and `execute_cypher` to the graph service box and
made `check_drift.sh` assert the copies BYTE-IDENTICAL, precisely so two
validators could not diverge. That precedent applies here and was not followed.

Severity: minor. No leak today, and the fix is either one shared helper or one
equality arm.

### A-5.0-30 (informational, two more NEGATIVE results)

- THE `trace_id` CONTEXTVAR LIFECYCLE IS CORRECT. I went looking for a
  cross-request trace_id leak, because `run_streaming` deliberately uses a bare
  `set_trace_id`/`reset_trace_id` pair rather than the `trace_id_scope` context
  manager, and because an async generator runs each step in its CALLER's
  context, so that `set` mutates the driving task's context rather than a
  private one. It holds: `run_registry._drain_into_entry` both drives and
  `aclose()`s the generator from inside the same task
  (`run_registry.py:694`), so the token is always reset in the context that
  created it, and a `ValueError: Token was created in a different Context` is
  not reachable by any route I could find. The one shape that would break it,
  `aclose()` called from a different task than the one that drove the
  generator, does not occur.
- `logs/` IS GITIGNORED (`.gitignore:112`) and `git ls-files logs` is empty.
  F-5.0-01 is genuinely closed.

### The gate is green and every finding above is additional to it

`venv/bin/python -m pytest tests/system_03_search_agent/observability -q`
-> `164 passed, 1 skipped in 2.98s`, on the branch as committed at `c8a8e7d`,
with nothing under `src/` modified by me at any point. Every one of the 29
findings above coexists with a fully green observability suite including its
premise gate and its mutation harness.

## Summary

30 findings filed, A-5.0-01 through A-5.0-30.

| Severity | Count | Findings |
|---|---|---|
| Critical | 1 | A-5.0-13 |
| Critical, confirming evidence for A-5.0-13 | 2 | A-5.0-15 (end to end on the wire), A-5.0-23 (confirmed live today) |
| Major | 11 | A-5.0-01, 02, 03, 04, 05, 07, 09, 10, 19, 24, 27 |
| Minor | 10 | A-5.0-06, 11, 14, 17, 18, 20, 22, 25, 26, 29 |
| Informational: negative results and analysis | 6 | A-5.0-08, 12, 16, 21, 28, 30 |

A-5.0-07 and A-5.0-09 are recorded at major AS REVISED by A-5.0-08, which
corrected both downward on the inputs path and confirmed both on the metadata
path. Read them together; do not act on the original wording alone.

Against the six targets in my brief:

1. THE APPEND-ONLY SINK: a fifth family found (A-5.0-02, deferred
   stringification: a non-`str` object bypasses redaction entirely and is
   converted to text afterwards by `json.dumps(default=str)`), plus the
   `isinstance`-vs-`type` family left unfixed in the one function both
   redaction rules delegate to (A-5.0-01), plus three fields with no control of
   any kind (A-5.0-03, A-5.0-04), plus a way to delete an audit record outright
   (A-5.0-05).
2. THE PII BOUNDARY: the account-PII redaction WORKS on inputs and outputs,
   proven on 28 KB of real wire payload. The `error` field does not, at all
   (A-5.0-13). The type gaps are live on the metadata path (A-5.0-08).
3. THE NO-CREDENTIAL PATH: HOLDS, measured at the socket with a populate-check
   (A-5.0-16). I could not make it call.
4. F-5.0-19's REACH: the shape is reachable from three real call sites, no
   credential is (A-5.0-28). Severity as filed is right; the attention is on
   the wrong field.
5. POSTHOG: nothing was sent. Two conflicting credentials of two different
   types are configured and the dangerous one is one unset shell variable away
   from being live (A-5.0-27).
6. OPERATIONAL HOSTILITY: cross-process writes corrupt the sink once a line
   exceeds the buffer (A-5.0-19), and the fields that can produce such a line
   are exactly the uncapped ones. Line forgery, a hostile filesystem and
   in-process concurrency all pass cleanly (A-5.0-21).

## The one I would fix first

A-5.0-13: a run's ERROR string reaches LangSmith completely unredacted.

Every other finding is either a local file, a latent path, or a shape no
shipped caller produces. This one is live right now (A-5.0-23: importing
litellm loads the real `lsv2` key from `.env` and flips `tracing_enabled()` to
True), it fires on the ordinary failure path of the shipped NCBI transport, and
it sends a live credential OFF-BOX to a retained third-party service.

The asymmetry is what makes it first rather than merely worst. This phase spent
four review rounds, three Rule 4 escalations and a design reversal establishing
that an exception message in this system carries credentials and cannot be
safely scanned, and then removed free text from the audit sink entirely. The
identical string is shipped to LangSmith on every failed node with a redactor
attached that does not look at strings. The weaker exposure got a structural
bound. The stronger one got nothing.

The fix is small and this repository already owns both halves: give
`redact_payload` a string branch, and the obvious body for it is
`audit._redact_value_string`, which is in the same package, already tested, and
already catches both the DSN and the query-parameter shapes I used. That
inherits F-5.0-19's known gap, which is a real objection, and it is still
strictly better than the nothing that is there now. A stronger version drops
the error string to a class name, exactly the move `audit.py` already made.

Whatever is chosen, the arm that pins it should assert on a CAPTURED WIRE
PAYLOAD rather than on `redact_payload`'s return value: `scratchpad/p5_wire.py`
is about sixty lines, needs no live service and no credential, and it is the
only shape of arm that would have caught this one, since the redactor was
correctly wired the whole time and the field it does not cover was never in any
test's field of view.
