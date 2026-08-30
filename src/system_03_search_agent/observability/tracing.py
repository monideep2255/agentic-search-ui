"""T-5.0-03: the LangSmith tracing module, tech spec Section 20.1.

THE CRITICAL CONTEXT THIS MODULE EXISTS TO CLOSE (F-5.0-03). `.env` and
`env.example:107` already set `LANGCHAIN_TRACING_V2=true`, and the installed
langsmith (0.10.10, `utils.py:121-139`) honours that spelling across both
the `LANGSMITH_` and `LANGCHAIN_` namespaces, so the flag is live everywhere
today. The only thing that has ever suppressed tracing is a hardcoded
`tracing_context(enabled=False)` in `core/run.py` at two call sites
(T-5.0-05's job, not this ticket's). Simply removing that override would
turn tracing on and start transmitting PII, because LangGraph attaches a
LangSmith tracer to every node automatically, independent of any code in
this repository, and the object it captures each time is `GraphState`,
which carries `Query.owner_id`, `Query.user_id` and
`RequestContext.session_memory`. Section 20.1: user-account PII from the
auth service never leaves the auth service boundary and is never attached
to a trace. Redaction is therefore built here, in the same module that
turns tracing on, not as a follow-up.

Depends on:
    - system_03_search_agent.observability.config (tracing_enabled,
      langsmith_api_key, langsmith_project, langsmith_endpoint). Every
      environment read goes through these four functions; this module never
      reads `os.environ` itself.
    - system_03_search_agent.contracts.query (Query, RequestContext),
      introspected through `model_fields` rather than re-typed as a
      hardcoded field list. See `_allowlist_for` for why: a field added to
      either model in a later phase is redacted by default, not leaked by
      default, because it will not be on this module's small SAFE allowlist
      unless someone deliberately adds it there too.

Reads:
    - Nothing beyond `observability.config`'s four functions above.

Writes:
    - Nothing directly. `build_traced_client` constructs a `langsmith.Client`
      that writes to LangSmith over HTTPS when a caller actually uses it;
      this module itself performs no I/O.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from typing import Any

from langchain_core.runnables.config import RunnableConfig
from langsmith import Client
from langsmith.run_helpers import tracing_context as _langsmith_tracing_context

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.observability import config

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

#: What a redacted value looks like in a trace. A literal marker rather than
#: a dropped key, so a reader of the trace sees that a field existed and was
#: intentionally withheld, not an unexplained gap that reads like a bug.
_REDACTED = "[redacted]"

#: What replaces an exception MESSAGE once its class name has been taken
#: off the front. A literal marker for the same reason `_REDACTED` is one:
#: a reader of the trace must be able to tell that a message existed and
#: was withheld by design, rather than that a run failed with no detail.
_REDACTED_ERROR = "[redacted error]"

#: The closed set of NORMALIZED key names whose value is treated as an
#: exception message rather than as trace content.
#:
#: WHY THIS FIELD IS BOUNDED RATHER THAN SCANNED (A-5.0-13, J-03). langsmith
#: routes a run's error through the configured anonymizer, wrapped as
#: `{"error": <string>}` (`client.py:2759-2764`), and that string is
#: `repr(exc)` plus a formatted traceback
#: (`run_helpers._format_error_with_exceptions_to_handle:1442`). In this
#: system that message carries a URL with the NCBI api_key appended by
#: `ncbi_transport._append_api_key`, or the `kg_reader` DSN password, both
#: measured. Before this change `redact_payload` walked dicts and lists and
#: returned every other type unchanged, so the string came back
#: byte-identical and shipped off-box to a third-party SaaS.
#:
#: `audit.py`'s module docstring records what this phase already paid four
#: rounds to learn about exactly that string: three consecutive rounds tried
#: to make a scanner safe enough for it, each passed its own tests, and each
#: was defeated by an input of the same family. The durable fix there was to
#: stop accepting free text at all and accept a closed vocabulary plus an
#: exception class name instead. This is the same bound applied at the other
#: sink, and it is applied here rather than in the message's assembly for a
#: reason worth stating: langsmith assembles the string, but it takes this
#: module's RETURN VALUE verbatim as the field it uploads
#: (`client.py:2318`, `client.py:3684`), so emission is a chokepoint this
#: repository does control even though assembly is not.
#:
#: What a trace actually needs from a failure is which run failed, already
#: carried by the run record and by `trace_id`, and what KIND of failure it
#: was. A class name answers the second. Build phase 5.1's eval graders need
#: a run's inputs, outputs, citations and tool results, none of which travel
#: under any key named below, so bounding this field costs them nothing.
_ERROR_TEXT_KEYS: frozenset[str] = frozenset(
    {"error", "errors", "exception", "traceback", "stacktrace"}
)

#: Cap on an extracted exception class name, the same bound and the same
#: reasoning as `audit._MAX_ERROR_CLASS_CHARS`: it bounds LENGTH and
#: nothing else, so it is not a second bound on secrecy (F-5.0-21).
_MAX_ERROR_CLASS_CHARS = 128

#: A dotted Python identifier, applied ANCHORED at position 0 of the error
#: string and required to be followed immediately by `(`. Both constraints
#: are load-bearing. Anchoring means the only thing this can ever capture
#: is the leading `repr(exc)`'s class name, which is written in a `class`
#: statement rather than assembled from data, the same developer-controlled
#: versus data-assembled distinction `audit._safe_error_class` rests on; a
#: message cannot place itself in front of its own class name. The
#: character class excludes every character a credential needs to travel,
#: no `=`, `:`, `/`, `@`, `?`, `&`, whitespace or quote, so neither a
#: query-string assignment nor a DSN userinfo segment is spellable here.
_ERROR_CLASS_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")

# Category patterns for identity- and credential-shaped keys, matched against
# a NORMALIZED key (lowercased, every non-alphanumeric character stripped),
# not against an enumerated list of exact field names. This is the
# category-not-enumeration discipline `.claude/rules/system-design-patterns.md`
# pattern 8 already applies to tool access, carried over to redaction: a
# field named `caller_user_id`, `secondary_owner_id` or `refresh_token` was
# never hardcoded here, but each one contains one of these substrings once
# normalized, so each is caught the same way the field it resembles is,
# with no code change. This pass runs at EVERY nesting depth (see
# `redact_payload`), not only at the top level of a payload.
#
# `sessionid` added under F-5.0-09. `Query.session_id` is the one SAFE-
# allowlist-excluded field that had NO category coverage at all, so it
# depended entirely on the structural rule below recognizing the dict it
# lives in. `_looks_like_model`'s co-occurrence path needs at least two
# matching field names to fire, which leaves a narrow residual case open
# (see that function's docstring), and this entry closes exactly that
# case for `session_id` specifically: a payload carrying `session_id`
# alone, or `session_id` plus keys that are not Query or RequestContext
# fields, is still caught here even when the structural rule cannot
# recognize the shape at all.
_PII_KEY_CATEGORIES: tuple[str, ...] = (
    "ownerid",
    "userid",
    "sessionid",
    "sessionmemory",
    "sessiontoken",
    "email",
    "password",
    "credential",
    "apikey",
    "accesstoken",
    "authtoken",
    "refreshtoken",
    "ssn",
    "socialsecurity",
    "phonenumber",
)

# The two containers the critical finding names by name. Introspected via
# `model_fields` at import time rather than copied out as a hardcoded tuple
# of strings, so this set tracks the live model: a field added to `Query` or
# `RequestContext` in a later build phase appears here automatically, with
# no edit to this file, and is therefore covered by the default-deny
# allowlist check below the moment it exists.
_QUERY_FIELDS = frozenset(Query.model_fields.keys())
_REQUEST_CONTEXT_FIELDS = frozenset(RequestContext.model_fields.keys())

# The only fields on each model Section 20.1 actually clears for a trace:
# the question text itself (already public NCBI-domain biomedical text) and
# the routing metadata needed to make sense of a run, never an account
# identifier and never session memory content. Everything else on either
# model, present today or added later, is redacted by default because it is
# simply not on this list. This is the inverse of an enumerated-block
# defense: the list below names what is DELIBERATELY KEPT, not what is
# blocked, so an omission fails closed instead of open.
_QUERY_SAFE_FIELDS = frozenset({"text", "trace_id", "audience_depth"})
_REQUEST_CONTEXT_SAFE_FIELDS = frozenset({"surface", "operator_mode"})


def _normalize_key(key: object) -> str:
    """Lowercase and strip separators so `owner_id`, `ownerId` and
    `OWNER-ID` all normalize to the same string for category matching.

    Returns the empty string for a non-string key, which matches no
    category below and therefore never redacts a value it cannot classify.
    """
    if not isinstance(key, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_pii_key(key: object) -> bool:
    normalized = _normalize_key(key)
    return any(category in normalized for category in _PII_KEY_CATEGORIES)


def _looks_like_model(key_set: set[str], model_fields: frozenset[str]) -> bool:
    """True when `key_set` should be treated as an instance of the model
    that declares `model_fields`, even when `key_set` also carries keys the
    model does not declare at all.

    F-5.0-09: the previous version of this check was `key_set.issubset(
    model_fields)`, a pure subset test. That test answers "does this dict
    contain nothing I do not expect", which is a PROXY for "is this a
    Query", not the property itself, and a proxy that flips the wrong way
    under the one input that matters most: adding a single key the model
    does not declare turns a real Query dict into something the subset
    test no longer recognizes at all, which switches the entire allowlist
    off and lets every field, including `session_id`, ship unredacted.
    Unexpected content should tighten a default-deny control, never
    disable it. That is what "fails open" means here, measured rather
    than asserted: `_allowlist_for({"session_id": "x", ...all six real
    Query fields..., "billing_address": "y"})` returned None under the old
    check, `_QUERY_SAFE_FIELDS` under this one.

    Two independent ways to match, checked in order:

    1. PURE SUBSET (`key_set <= model_fields`): every key in `key_set` is
       a declared field on the model and nothing else. Kept from the
       original check because it is genuinely needed: a nested LangGraph
       state slice can carry a partial view of a model with an optional
       field simply absent, and a dict naming only one or two real fields
       with no unexpected key alongside them is still a legitimate,
       recognizable partial view.
    2. CO-OCCURRENCE (`len(key_set & model_fields) >= 2`): two or more of
       the model's declared field names appear in `key_set` together,
       regardless of what else `key_set` also carries. This is the branch
       that fixes F-5.0-09: an extra, undeclared key no longer defeats
       recognition, because recognition here no longer requires the ABSENCE
       of unexpected keys, only the PRESENCE of enough expected ones.
       Two field names is a deliberately higher bar than one, because a
       single shared field name (for example a tool result that happens
       to use a key literally called `text`) is not distinctive enough on
       its own to justify redacting the rest of an unrelated dict; two
       names from the same model appearing together is.

    What defeats this rule, stated rather than assumed: a dict that
    carries exactly ONE field from `model_fields` alongside one or more
    keys that are not declared on either model. That input satisfies
    neither branch (not a pure subset, and the intersection is 1, below
    the co-occurrence floor), so it is not structurally recognized and the
    allowlist does not apply to it. In this codebase that gap matters for
    exactly one field: `Query.session_id`, the only SAFE-allowlist-excluded
    field with no matching entry in `_PII_KEY_CATEGORIES`. That specific
    gap is closed by a second, independent layer instead of a lower
    threshold here (a threshold of 1 would itself start misrecognizing
    unrelated single-field-overlap dicts): `_PII_KEY_CATEGORIES` gained a
    `sessionid` entry under this same finding, so `session_id` is redacted
    by the category pass in `redact_payload` even on the input that
    defeats this function. Every other field this module protects
    (`owner_id`, `user_id`, `session_memory`, and any future field whose
    name resembles an existing category) was already covered by the
    category pass independently of this function; this paragraph exists
    because `session_id` was the one exception, not because the category
    pass is new.
    """
    if not key_set:
        return False
    if key_set <= model_fields:
        return True
    return len(key_set & model_fields) >= 2


def _is_error_text_key(key: object) -> bool:
    """Whether `key` names a field carrying an exception message."""
    return _normalize_key(key) in _ERROR_TEXT_KEYS


def _bound_error_text(value: str) -> str:
    """Reduce an exception message to a marker plus, at most, its class name.

    The message itself is DISCARDED, never scanned, truncated or rewritten.
    That is what makes this a structural bound rather than a fourth attempt
    at the scanner this phase abandoned: there is no path down which any
    part of a URL, a DSN or a response body can reach the returned value,
    because nothing but an anchored dotted identifier is ever read out of
    the input at all.

    A class name is recovered only when the string opens with the exact
    shape `repr(exc)` produces, a dotted identifier immediately followed by
    `(`. Anything else, including a message langsmith or a LangChain tracer
    formatted with `str(exc)` rather than `repr(exc)`, yields the bare
    marker. Failing closed to less information is correct here: the class
    name is a diagnostic nicety on top of the run record, never the record.

    The residual, stated rather than assumed, and it is the same one
    `audit._safe_error_class` documents under F-5.0-21: an identifier is a
    SHAPE, and a bare alphanumeric token is a legal identifier, so this
    bound would not by itself exclude an opaque API key sitting where a
    class name belongs. What keeps that from happening is position, not the
    character class: position 0 followed by `(` is occupied by
    `type(exc).__name__`, which the raising code chooses, and a message
    cannot move itself in front of it.
    """
    match = _ERROR_CLASS_PATTERN.match(value)
    if match is None or match.end() >= len(value) or value[match.end()] != "(":
        return _REDACTED_ERROR
    class_name = match.group(0)
    if len(class_name) > _MAX_ERROR_CLASS_CHARS:
        return _REDACTED_ERROR
    return _REDACTED_ERROR + " " + class_name


def _bound_error_value(value: Any) -> Any:
    """Apply the error-field bound to whatever sits under an error-shaped key.

    Four cases, and there is deliberately no fifth that passes text
    through:

    - `None` stays `None`. A run that did not fail records no error, and
      inventing a marker there would read as a failure that never happened.
    - An exact `str` is bounded by `_bound_error_text`. This is the only
      shape langsmith actually produces (`client.py:2761` wraps the
      formatted message and nothing else).
    - A `str` SUBCLASS becomes the bare marker with no class-name
      extraction attempted. `type(value) is str` rather than `isinstance`
      is F-5.0-22's lesson carried across from `audit.py`: a subclass can
      override the very methods a guard calls, so the exact type test
      stands in front of the ones it could lie to.
    - A dict or list recurses under the ordinary rules, because a container
      is structure rather than a message. Its own keys get this same
      treatment at depth.

    Any other scalar (a number, a bool) is returned unchanged: it carries
    no text and therefore no credential.
    """
    if value is None:
        return None
    if type(value) is str:
        return _bound_error_text(value)
    if isinstance(value, str):
        return _REDACTED_ERROR
    if isinstance(value, dict | list):
        return redact_payload(value)
    return value


def _allowlist_for(keys: Iterable[str]) -> frozenset[str] | None:
    """Return the SAFE-field allowlist for a dict recognized as Query or
    RequestContext shaped, or None when the dict is neither.

    Recognition is `_looks_like_model`, not a plain subset test; see that
    function's docstring for the fail-open defect this replaced (F-5.0-09)
    and what still defeats the replacement. An empty key set is excluded
    explicitly before either model is even considered, since an empty
    dict holds nothing to redact either way and classifying it either way
    changes nothing observable.
    """
    key_set = set(keys)
    if not key_set:
        return None
    if _looks_like_model(key_set, _QUERY_FIELDS):
        return _QUERY_SAFE_FIELDS
    if _looks_like_model(key_set, _REQUEST_CONTEXT_FIELDS):
        return _REQUEST_CONTEXT_SAFE_FIELDS
    return None


def redact_payload(payload: Any) -> Any:
    """Strip account PII from a LangGraph run's inputs or outputs.

    Recurses through every dict and list at any nesting depth (a run's
    payload is `GraphState`, which nests `Query` under `"query"` and
    `RequestContext` under `"context"`, so a shallow, top-level-only pass
    would miss both). Two independent passes run at every dict encountered,
    together rather than as alternatives, because each covers a gap the
    other does not:

    1. STRUCTURAL: a dict whose keys are recognized as Query or
       RequestContext (see `_allowlist_for`) is rebuilt keeping only that
       model's SAFE allowlist; every other field on the model, including
       one added after this module was written, is replaced with the
       redacted marker. This is what makes a NEW PII field on either model
       caught by default: it is on the model's `model_fields` the moment
       it exists, and it is not on the small SAFE allowlist unless someone
       deliberately adds it there, so it redacts without this file
       changing at all.
    2. CATEGORY: independent of whether a dict is recognized as either
       model, any key matching an identity- or credential-shaped category
       (`_is_pii_key`) is redacted wherever it occurs, including inside an
       object this module does not structurally recognize at all, for
       example a nested echo of an identifier inside a tool result.

    3. ERROR BOUND (A-5.0-13, J-03): a value under an error-shaped key
       (`_ERROR_TEXT_KEYS`) never passes through as free text. The message
       is discarded and replaced with a marker plus, at most, the leading
       `repr(exc)`'s class name. This is the third anonymizer path
       langsmith drives, `_hide_run_error`, and it is the one that carried
       a live credential off-box before this bound existed. See
       `_ERROR_TEXT_KEYS` for why the field is bounded rather than scanned,
       and `_bound_error_text` for what the bound does and does not
       guarantee.

    Never raises on an unexpected shape. A value that is neither a dict
    nor a list (a string, a number, `None`, a bool) is returned unchanged
    once it survives whichever pass above it fell under, since a scalar
    value cannot itself carry nested PII.

    WHAT THIS STILL DOES NOT DO, stated because a green gate that reads as
    "strings are handled" would be worse than no statement at all
    (A-5.0-14, open): an ordinary string under an ordinary key is returned
    unchanged. A credential echoed into a tool result under a key named
    neither for a secret nor for an error is not caught here. Pass 3 bounds
    the one position langsmith is known to put a formatted exception
    message in, not every position a string can occupy.
    """
    if isinstance(payload, dict):
        allowlist = _allowlist_for(payload.keys())
        result: dict[Any, Any] = {}
        for key, value in payload.items():
            unlisted = allowlist is not None and key not in allowlist
            if unlisted or _is_pii_key(key):
                result[key] = _REDACTED
            elif _is_error_text_key(key):
                # Ordered AFTER the two redaction rules on purpose: a key
                # that is both error-shaped and PII-shaped must take the
                # stronger outcome, and full redaction is stronger than a
                # bound that keeps a class name.
                result[key] = _bound_error_value(value)
            else:
                result[key] = redact_payload(value)
        return result
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return payload


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def build_traced_client() -> Client:
    """A `langsmith.Client` configured to redact account PII from every run
    it sends, never a bare `Client()`.

    Wires `redact_payload` in through `anonymizer`, not `hide_inputs` or
    `hide_outputs`, and this is not a style choice: probed against the
    installed langsmith 0.10.10 (`client.py`, `Client._hide_run_inputs` and
    `_hide_run_outputs`), the anonymizer check runs BEFORE either hide_*
    callable and, once an anonymizer is set, it is applied to inputs and
    outputs UNCONDITIONALLY. Both hide_* callables become dead code the
    moment an anonymizer is also configured. Passing `redact_payload` to
    both parameters would therefore silently run it twice through one path
    and never through the other, so it is wired into exactly the parameter
    that actually executes.

    `hide_metadata` has no such short-circuit in the installed source
    (`Client._hide_run_metadata` never consults `self._anonymizer`), so it
    is wired separately with the same function: metadata is exactly as
    capable of carrying an identity field as a run's inputs or outputs are,
    and leaving it unredacted because the anonymizer parameter happens to
    exist would be the false-symmetry mistake, not a saving.
    """
    return Client(
        api_key=config.langsmith_api_key(),
        api_url=config.langsmith_endpoint(),
        anonymizer=redact_payload,
        hide_metadata=redact_payload,
    )


# ---------------------------------------------------------------------------
# Scoped tracing context
# ---------------------------------------------------------------------------


@contextmanager
def traced_graph_run(
    *, run_name: str, tags: list[str] | None = None
) -> Generator[None, None, None]:
    """Wrap one graph invocation with tracing intentionally ON or OFF,
    decided by `config.tracing_enabled()` and nothing else.

    Usable identically around a single `await` and around a whole
    `async for` loop, which is exactly what T-5.0-05 needs for `run()`
    (one `await compiled_graph.ainvoke(...)`) and `run_streaming()` (one
    `async for ... in compiled_graph.astream(...)`). This works because
    `langsmith.run_helpers.tracing_context` is a SYNC context manager
    (probed: a `@contextmanager`-decorated generator yielding `None`, using
    ordinary `__enter__`/`__exit__`), so entering and exiting it never
    needs an event loop of its own; it only sets a contextvar for whatever
    async code runs inside its `with` block, the same primitive
    `core/run.py`'s existing two call sites already use in their disabled
    form.

    OFF path: no `Client` is constructed at all, so there is no outbound
    transport for a test, or a production run, to observe. This is
    deliberately a stronger guarantee than "the client exists but is never
    called": with no key configured, `build_traced_client` is never even
    reached, which is what makes "no credential means provably zero
    outbound calls" true by construction (`observability/config.py`'s own
    docstring names this as the reason `tracing_enabled()` requires the key
    rather than the flag alone).

    ON path: a real, redaction-wired client is built and handed to
    `tracing_context` so every run traced inside the block goes through
    `redact_payload` before anything leaves this process.
    """
    if not config.tracing_enabled():
        with _langsmith_tracing_context(enabled=False):
            yield
        return

    client = build_traced_client()
    with _langsmith_tracing_context(
        enabled=True,
        project_name=config.langsmith_project(),
        tags=list(tags) if tags else None,
        client=client,
    ):
        yield


# ---------------------------------------------------------------------------
# RunnableConfig builder
# ---------------------------------------------------------------------------


def build_runnable_config(
    *, trace_id: str, run_name: str, tags: list[str] | None = None
) -> RunnableConfig:
    """The `config=` dict T-5.0-05 passes to `compiled_graph.ainvoke` or
    `compiled_graph.astream`.

    `metadata["trace_id"]` is the join key, per Section 20.1: "It is the
    single join key across LangSmith, the Postgres interactions table
    ..., and the tool-call audit log." The metadata dict built here holds
    exactly that one key plus nothing else, so it needs no pass through
    `redact_payload` to be safe: `trace_id` is not account PII (Section
    20.1 clears it explicitly, and `redact_payload`'s own SAFE allowlist
    for `Query` keeps it for the same reason), and no other value is ever
    placed here.

    `run_id` is attempted, not assumed: `RunnableConfig.run_id` is typed
    `uuid.UUID | None` (probed via `RunnableConfig.__annotations__`), and
    this project's own `trace_id` is a plain string minted by
    `Harness(trace_id=...)` with no guarantee of being UUID-shaped. Parsing
    it as a UUID is tried, and a failure is swallowed rather than raised:
    `run_id` is an optional LangSmith correlation nicety on top of the
    join key above, never the join key itself, so a `trace_id` that does
    not parse simply means this one run carries no extra `run_id`, not a
    broken run.
    """
    metadata: dict[str, Any] = {"trace_id": trace_id}
    result: RunnableConfig = {
        "run_name": run_name,
        "tags": list(tags) if tags else [],
        "metadata": metadata,
    }
    try:
        result["run_id"] = uuid.UUID(trace_id)
    except (ValueError, AttributeError, TypeError):
        pass
    return result


__all__ = [
    "build_runnable_config",
    "build_traced_client",
    "redact_payload",
    "traced_graph_run",
]
