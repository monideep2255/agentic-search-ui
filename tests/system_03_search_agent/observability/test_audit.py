"""Tests for `system_03_search_agent.observability.audit` (T-5.0-02).

## Coverage: what this file exercises and what it deliberately omits

Per `.claude/rules/goal-contracts.md`, a verify surface must state its own
coverage so a gap is arguable rather than silently assumed away.

Exercised:

- A written line round-trips as JSON and carries every field this module's
  contract promises: `trace_id`, `timestamp`, `tool`, `layer`, `endpoint`,
  `authorization`, `params`, `record_ids`, `http_status`, `error`,
  `latency_ms`.
- Append-only: two writes produce two lines, and the first line's raw bytes
  are unchanged after the second write lands.
- Concurrency: many threads writing at once produce exactly that many
  well-formed lines, none interleaved, none truncated, none dropped.
- The redactor replaces a secret value at the top level, nested inside a
  dict, and inside a list, using a key name this test invents rather than
  one copied from the module's own marker list, to prove the category rule
  rather than a coincidence of matching literals.
- Value-level redaction (F-5.0-08): a secret embedded inside a VALUE under
  an innocuous key, specifically a URL query parameter (the
  `_append_api_key` shape in `ncbi_transport.py`) and a connection-string
  password, is caught even though the key-name rule above cannot see it.
  The host, path, and non-secret query parameters of the URL are asserted
  to survive, so an arm here fails both if redaction stops working and if
  it over-redacts an endpoint into uselessness. A URL carrying no secret is
  asserted to pass through byte-identical.
- Embedded-URL redaction (F-5.0-13, gap two): a credential inside a URL or
  DSN that is itself embedded in a larger string, an exception message's
  prose rather than a value that IS the whole URL, is caught. Covers both
  measured leak shapes (a DSN after "connection failed: ", an API key
  query parameter inside "HTTP 500 calling ... after N retries") and a
  credential shape not hardcoded anywhere in this module, to prove the
  category rule rather than a coincidence of two known reproductions. Each
  arm asserts the secret is absent AND that the surrounding prose plus the
  host and path survive.
- The error field, now STRUCTURALLY BOUNDED rather than scanned. It
  carries a code from `AUDIT_ERROR_CODES` plus optionally an exception
  class name, and never free text, after three rounds (F-5.0-13,
  F-5.0-14, F-5.0-19) of hardening a string scanner were each defeated by
  an input of the same family. Proven end to end through BOTH converted
  chokepoints, `graph_connection.execute_cypher` and
  `ncbi_transport.execute_get`, by raising an exception whose message
  carries a generated credential and asserting no fragment of that
  message reaches the line, with a populate-check that the line was
  actually written. The fail-closed branch, the deprecated `error`
  keyword, and the exception-type mapping in both modules each have their
  own class below, the last enumerated from the modules' own
  `__subclasses__()` so a new unmapped type is a build failure.
- The KNOWN GAP in the params value scanner (F-5.0-19) is pinned by
  `TestKnownGapF5019`, which asserts the leak STILL HAPPENS. That is
  deliberate: a limitation nobody can forget is one an executable arm
  states. Its companion arm asserts the shapes the scanner does still
  catch, so "the known gap" can never be confused with a dead scanner.
- A secret VALUE never appears anywhere in the raw written line, checked
  against the file's raw text rather than against the parsed structure, so
  a bug that redacted the wrong key would still be caught.
- `trace_id` is recorded when `trace_id_scope` is active and null when it
  is not, proving the ContextVar actually gates the field rather than a
  caller-supplied default doing the work.
- A writer failure (a path whose parent cannot be created) does not raise
  to the caller and leaves `record_tool_call` returning normally.
- `audit_enabled() is False` writes nothing at all: no file, no directory,
  no bytes.
- The size cap discloses truncation in the line itself rather than
  silently dropping an oversized payload.

Every assertion below is written so a specific, nameable code change turns
it red: each test's docstring says what that change is.

NOT exercised, deliberately:

- Wiring this module into a real transport call site, BEYOND the two
  error-classification arms above. Those two drive `execute_cypher` and
  `execute_get` because the property under test is that the CALL SITE
  classifies rather than stringifies, which cannot be proven from the
  sink alone. Everything else about the wiring is still `test_wiring.py`'s
  and the premise gate's.
- `pathogen_ftp_transport.py`'s two audit call sites, which still pass the
  deprecated `error` keyword and are outside this change's file scope
  (F-5.0-20). What is exercised is that the keyword cannot carry text; what
  is not exercised is that module's own conversion, because it has not
  happened.
- Anything about LangSmith or PostHog. Those are `tracing.py` and
  `analytics.py`, separate modules built by sibling tickets.
- The premise gate's cross-cutting arms (one per bypass call site). Those
  belong to T-5.0-07, once the transport hooks this module feeds actually
  exist.
"""

from __future__ import annotations

import ast
import inspect
import json
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest

from system_03_search_agent.observability import audit
from system_03_search_agent.tools import (
    graph_connection,
    graph_http_transport,  # noqa: F401 - registers GraphRateLimitedError
    ncbi_transport,
)


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


#: The two modules converted to the classified error field. Read from
#: their own source by the call-site arm below rather than described, so a
#: third call site added without an entry here is visible as a gap rather
#: than silently uncovered.
_AUDIT_CALL_SITE_MODULES: tuple[Any, ...] = (graph_connection, ncbi_transport)


def _module_source(module: Any) -> str:
    """Read a module's own source text.

    Indirected through a function rather than called inline so the
    permanent mutation harness can feed the arm below a doctored source
    and prove it actually discriminates.
    """
    return inspect.getsource(module)


def _error_class_arguments(source: str) -> list[ast.expr]:
    """Every `error_class=` keyword expression on a `record_tool_call`."""
    found: list[ast.expr] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if called != "record_tool_call":
            continue
        for keyword in node.keywords:
            if keyword.arg == "error_class":
                found.append(keyword.value)
    return found


def _is_class_name_literal(node: ast.expr) -> bool:
    """Whether an expression is `type(<name>).__name__`.

    That shape is the one whose value is fixed by the source code rather
    than assembled from data, which is the property F-5.0-21 established
    the `isidentifier()` guard does NOT provide on its own.
    """
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "__name__"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "type"
        and len(node.value.args) == 1
    )


class _HostileEqStr(str):
    """A `str` subclass claiming equality with everything.

    Not hypothetical: tuple containment evaluates `value.__eq__(member)`
    first, so this shape was measured writing its own payload into
    `error_code`, a value in no vocabulary at all (F-5.0-22).
    """

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash(str(self))


class _HostileIdentifierStr(str):
    """A `str` subclass lying about BOTH of `_safe_error_class`'s bounds.

    Both bounds are `str` methods, so a subclass owns them. This shape was
    measured being returned verbatim carrying `=`, `:`, `/` and `?`
    (F-5.0-22).
    """

    def isidentifier(self) -> bool:
        return True

    def __len__(self) -> int:
        return 4


class TestRoundTrip:
    def test_written_line_carries_every_contract_field(self, tmp_path, monkeypatch):
        """Fails if any Section 20.3 / ticket field is dropped from the entry dict."""
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        with audit.trace_id_scope("trace-abc"):
            audit.record_tool_call(
                tool="cypher_query",
                layer=1,
                endpoint="kg",
                latency_ms=12.5,
                authorization="kg_reader",
                params={"query_intent": "gene_disease"},
                record_ids=["gene:7157"],
                http_status=None,
                error_code=None,
                error_class=None,
            )

        lines = _read_lines(log_path)
        assert len(lines) == 1
        entry = json.loads(lines[0])
        expected_fields = {
            "trace_id",
            "timestamp",
            "tool",
            "layer",
            "endpoint",
            "authorization",
            "params",
            "record_ids",
            "http_status",
            "error_code",
            "error_class",
            "latency_ms",
        }
        assert expected_fields <= entry.keys()
        assert entry["trace_id"] == "trace-abc"
        assert entry["tool"] == "cypher_query"
        assert entry["layer"] == 1
        assert entry["endpoint"] == "kg"
        assert entry["authorization"] == "kg_reader"
        assert entry["record_ids"] == ["gene:7157"]
        assert entry["http_status"] is None
        assert entry["error_code"] is None
        assert entry["error_class"] is None
        assert entry["latency_ms"] == 12.5
        assert isinstance(entry["timestamp"], str) and entry["timestamp"]

    def test_line_is_terminated_by_exactly_one_newline(self, tmp_path, monkeypatch):
        """Fails if `_append_line` writes zero or two newlines per entry."""
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(tool="t", layer=2, endpoint="e", latency_ms=1.0)

        raw = log_path.read_bytes()
        assert raw.count(b"\n") == 1
        assert raw.endswith(b"\n")


class TestAppendOnly:
    def test_two_writes_produce_two_lines_first_unchanged(self, tmp_path, monkeypatch):
        """Fails if a second write rewrites, truncates, or reorders the file
        rather than appending, since the first line's bytes would then
        differ between the two reads.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(tool="first", layer=2, endpoint="e1", latency_ms=1.0)
        first_line_before = _read_lines(log_path)[0]

        audit.record_tool_call(tool="second", layer=2, endpoint="e2", latency_ms=2.0)
        lines_after = _read_lines(log_path)

        assert len(lines_after) == 2
        assert lines_after[0] == first_line_before
        assert json.loads(lines_after[0])["tool"] == "first"
        assert json.loads(lines_after[1])["tool"] == "second"


class TestConcurrency:
    def test_many_concurrent_writes_produce_that_many_well_formed_lines(
        self, tmp_path, monkeypatch
    ):
        """Fails if the write lock is removed: without it, concurrent
        `open(..., "a")` + write + close calls from separate threads can
        interleave their bytes and produce a line that is not valid JSON,
        or fewer lines than writers.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        writer_count = 60

        def _write(index: int) -> None:
            audit.record_tool_call(
                tool=f"tool-{index}",
                layer=2,
                endpoint="e",
                latency_ms=float(index),
            )

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(writer_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        lines = _read_lines(log_path)
        assert len(lines) == writer_count

        seen_tools = set()
        for line in lines:
            entry = json.loads(line)  # raises if any line is malformed or interleaved
            seen_tools.add(entry["tool"])
        assert seen_tools == {f"tool-{i}" for i in range(writer_count)}


class TestRedaction:
    def test_secret_key_redacted_at_top_level(self):
        """Fails if a key literally named 'api_key' is left in the clear."""
        result = audit.redact_params({"api_key": "sk-super-secret"})
        assert result["api_key"] == audit.REDACTED_PLACEHOLDER

    def test_secret_key_redacted_nested_in_dict(self):
        """Fails if the redactor stops at the top level of the structure."""
        result = audit.redact_params({"config": {"db_password": "hunter2"}})
        assert result["config"]["db_password"] == audit.REDACTED_PLACEHOLDER

    def test_secret_key_redacted_inside_list(self):
        """Fails if the redactor does not descend into list elements."""
        result = audit.redact_params(
            {"items": [{"note": "fine"}, {"auth_token": "abc123"}]}
        )
        assert result["items"][1]["auth_token"] == audit.REDACTED_PLACEHOLDER
        assert result["items"][0]["note"] == "fine"

    def test_redaction_is_by_category_not_by_enumerated_name(self):
        """Fails if the redactor was implemented as a hardcoded key list
        rather than a category match: 'vendor_credential_blob' is a key
        name this module's source never spells out anywhere, it merely
        contains the 'credential' marker.
        """
        result = audit.redact_params({"vendor_credential_blob": "top-secret-value"})
        assert result["vendor_credential_blob"] == audit.REDACTED_PLACEHOLDER

    def test_non_secret_values_pass_through_unchanged(self):
        """Fails if the redactor over-redacts and destroys ordinary params."""
        result = audit.redact_params({"query_intent": "gene_disease", "limit": 25})
        assert result == {"query_intent": "gene_disease", "limit": 25}

    def test_secret_value_never_appears_anywhere_in_written_line(
        self, tmp_path, monkeypatch
    ):
        """Fails if any redaction path leaves the raw secret string reachable
        in the final serialized line, checked against the raw file text
        rather than the parsed dict so a stray unredacted copy elsewhere in
        the entry would still be caught.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        secret_value = "correct-horse-battery-staple-9f8e7d"
        audit.record_tool_call(
            tool="ncbi_efetch",
            layer=2,
            endpoint="/efetch",
            latency_ms=5.0,
            params={
                "ncbi_api_key": secret_value,
                "nested": {"connection_dsn": secret_value},
                "batch": [{"auth": secret_value}],
            },
        )

        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text

    def test_oversized_params_are_disclosed_not_silently_truncated(
        self, tmp_path, monkeypatch
    ):
        """Fails if an oversized payload is either written whole (blowing
        the cap) or dropped with no trace of what happened, since this
        repository's standing rule is that a shortened or dropped value
        must say so in the output itself.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        huge_params = {"payload": "x" * (audit._MAX_PARAMS_BYTES * 2)}
        audit.record_tool_call(
            tool="pubtator_annotate", layer=3, endpoint="/annotate",
            latency_ms=1.0, params=huge_params,
        )

        entry = json.loads(_read_lines(log_path)[0])
        assert "_audit_note" in entry["params"]
        assert "payload" not in entry["params"]
        assert entry["params"]["_audit_original_bytes"] > audit._MAX_PARAMS_BYTES


class TestValueLevelRedaction:
    """F-5.0-08: a credential embedded in a VALUE under an innocuous key.

    The key-name rule above (`TestRedaction`) cannot see this shape by
    construction: `_append_api_key` in `ncbi_transport.py` appends the NCBI
    API key to a URL's query string, so the secret rides inside a value
    held under a key like `endpoint`, which matches none of
    `_SECRET_KEY_MARKERS`. Every secret here is generated at runtime with
    `uuid.uuid4().hex` rather than typed as a literal, since a PreToolUse
    hook in this repository blocks commands containing secret-shaped
    literals.
    """

    def test_reproduction_api_key_in_url_under_endpoint_key(self, tmp_path, monkeypatch):
        """Fails if `api_key=` inside a URL value survives redaction, and
        separately fails if the redactor over-redacts and destroys the
        host or path an operator needs to read the audit line at all.
        This is F-5.0-08's exact reproduction: `endpoint` is not a
        secret-ish key name, so only value-scanning catches this.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        secret_value = uuid.uuid4().hex
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            "?db=gene&id=7157&api_key=" + secret_value
        )
        audit.record_tool_call(
            tool="ncbi_efetch",
            layer=2,
            endpoint="/efetch",
            latency_ms=4.0,
            params={"endpoint": url},
        )

        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text
        assert "eutils.ncbi.nlm.nih.gov" in raw_text
        assert "/entrez/eutils/efetch.fcgi" in raw_text
        assert "db=gene" in raw_text
        assert "id=7157" in raw_text

    def test_connection_string_password_redacted_under_non_secret_key(self):
        """Fails if a DSN's inline password survives redaction when it sits
        under a key name (here, 'target') that the key-name rule does not
        catch. Asserts the username and host are preserved so the line
        stays diagnostically useful.
        """
        secret_value = uuid.uuid4().hex
        dsn = "postgresql://appuser:" + secret_value + "@db.internal:5432/graph"

        result = audit.redact_params({"target": dsn})

        assert secret_value not in result["target"]
        assert "appuser" in result["target"]
        assert "db.internal" in result["target"]
        assert "graph" in result["target"]

    def test_secret_ish_query_param_not_hardcoded(self):
        """Proves the category rule rather than an enumerated list: the
        query parameter name below, 'x_forward_auth_stamp', appears nowhere
        in this module's or the module under test's marker list literally.
        It merely CONTAINS the 'auth' marker. A non-secret sibling
        parameter ('region') must survive untouched.
        """
        secret_value = uuid.uuid4().hex
        url = "https://api.example.com/v1?region=us&x_forward_auth_stamp=" + secret_value

        result = audit.redact_params({"request_url": url})

        assert secret_value not in result["request_url"]
        assert "region=us" in result["request_url"]
        assert "api.example.com" in result["request_url"]

    def test_secret_in_url_nested_inside_list_inside_dict(self):
        """Fails if value-scanning only runs at the top level and does not
        descend into a list nested inside a dict, mirroring
        `test_secret_key_redacted_inside_list` for the key-name rule.
        """
        secret_value = uuid.uuid4().hex
        result = audit.redact_params(
            {
                "batch": [
                    {"note": "fine"},
                    {"request": "https://api.example.com/v1?token=" + secret_value},
                ]
            }
        )

        assert secret_value not in json.dumps(result)
        assert result["batch"][0]["note"] == "fine"
        assert "api.example.com" in result["batch"][1]["request"]

    def test_url_with_no_secret_passes_through_completely_unchanged(self):
        """Fails if the redactor mangles an ordinary URL that carries no
        secret at all, for example by reordering or re-encoding its query
        string, which would make the audit log's endpoints unreliable even
        when nothing sensitive was ever present.
        """
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gene&term=BRCA1"

        result = audit.redact_params({"endpoint": url})

        assert result["endpoint"] == url


class TestEmbeddedUrlRedaction:
    """F-5.0-13, gap two: a credential inside a URL or DSN embedded in a
    larger string, not only when the whole value IS the URL. This is
    precisely the shape a caught `Exception`'s `str()` produces: a
    connection error or an HTTP failure message with the URL sitting
    inside prose. Every secret is generated with `uuid.uuid4().hex`, never
    a literal, per this module's own PreToolUse hook constraint.
    """

    def test_dsn_embedded_after_a_prose_prefix_is_redacted(self):
        """F-5.0-13's first measured leak: a DSN password surviving inside
        `"connection failed: postgresql://...".` Fails if the whole-string
        check from F-5.0-08 is the only thing scanning, since this value is
        not itself a URL, a URL is embedded inside it.
        """
        secret_value = uuid.uuid4().hex
        message = (
            "connection failed: postgresql://kg_reader:"
            + secret_value
            + "@10.0.0.5:5432/kg"
        )

        result = audit.redact_params(message)

        assert secret_value not in result
        assert result.startswith("connection failed: ")
        assert "kg_reader" in result
        assert "10.0.0.5:5432/kg" in result

    def test_api_key_embedded_before_a_prose_suffix_is_redacted(self):
        """F-5.0-13's second measured leak: an `api_key=` query parameter
        surviving inside `"HTTP 500 calling https://... after N retries".`
        Fails the same way as above, and separately fails if the trailing
        prose after the URL is swallowed or dropped by the scan.
        """
        secret_value = uuid.uuid4().hex
        message = (
            "HTTP 500 calling https://eutils.ncbi.nlm.nih.gov/e.fcgi"
            "?db=gene&api_key=" + secret_value + " after 3 retries"
        )

        result = audit.redact_params(message)

        assert secret_value not in result
        assert result.startswith("HTTP 500 calling ")
        assert result.endswith(" after 3 retries")
        assert "eutils.ncbi.nlm.nih.gov" in result
        assert "/e.fcgi" in result
        assert "db=gene" in result

    def test_credential_shape_not_hardcoded_embedded_in_prose(self):
        """Proves the category rule rather than a list of the two shapes
        the finding measured: `mongodb://` and the query parameter name
        `x_replica_set_auth` appear nowhere else in this module or its
        tests. Fails if the scanner is secretly still keyed to
        `postgresql://` and `api_key=` specifically.

        Trailing punctuation is deliberately separated from the matched
        token by whitespace rather than butted directly against it: this
        function's own docstring names an adjacent boundary character as
        something that can be swept into a redacted value along with it,
        so a token-adjacent comma is not this arm's concern and is covered
        separately by the no-credential passthrough arm below.
        """
        secret_value = uuid.uuid4().hex
        message = (
            "retry exhausted for mongodb://svc_reader:"
            + secret_value
            + "@replica.internal:27017/kg?x_replica_set_auth=on then giving up"
        )

        result = audit.redact_params(message)

        assert secret_value not in result
        assert result.startswith("retry exhausted for ")
        assert result.endswith(" then giving up")
        assert "svc_reader" in result
        assert "replica.internal:27017/kg" in result

    def test_ordinary_error_message_with_no_credential_passes_through_unchanged(self):
        """Fails if the embedded-URL scan mangles a diagnostic message that
        happens to contain a URL with nothing secret in it, which would
        make ordinary errors unreliable even when nothing sensitive was
        ever present.
        """
        message = (
            "graph query exceeded 30s calling https://kg.internal.example/query"
            "?db=kg, retry with a narrower query_intent"
        )

        result = audit.redact_params(message)

        assert result == message

    def test_multiple_embedded_urls_in_one_message_are_all_scanned(self):
        """Fails if the scan stops after the first match, leaving a second
        credential later in the same message untouched.
        """
        secret_one = uuid.uuid4().hex
        secret_two = uuid.uuid4().hex
        message = (
            "primary https://a.example/x?api_key=" + secret_one
            + " failed, falling back to https://b.example/y?api_key=" + secret_two
        )

        result = audit.redact_params(message)

        assert secret_one not in result
        assert secret_two not in result
        assert "a.example/x" in result
        assert "b.example/y" in result


class TestSecretAssignmentRedaction:
    """F-5.0-14: the third iteration on this control, and the one that
    stopped trying to find where a URL ends.

    The two rounds before this one delimited a URL-shaped token inside
    prose and redacted within it. Both were defeated by an input of the
    same family, because a bracket, parenthesis or quote is legal inside a
    query value AND is ordinary prose punctuation, so the token stopped
    early and everything after the stop was never scanned. `_append_api_key`
    appends the credential LAST, so every other query parameter sits
    upstream of it and any one of them carrying such a character defeated
    the whole scan.

    What this class covers, stated so a gap is arguable rather than
    invisible: the three shapes F-5.0-14 measured leaking, a control with
    no boundary character at all (without which a green suite cannot
    distinguish "truncation fixed" from "scanner dead"), a secret-ish
    assignment in prose with no URL wrapper, boundary characters INSIDE the
    credential, the one input family that still bounds redaction, and two
    byte-identity arms against over-redaction. What it does NOT cover: a
    credential carried with no `name=value` assignment and no userinfo
    segment at all, for instance an `Authorization: Bearer ...` header
    rendered into a message, which neither rule can see by construction.

    Every secret is generated with `uuid.uuid4().hex`, URL-safe hex, which
    is the alphabet the previous round's docstring wrongly called safe.
    """

    def test_a_bracket_in_an_earlier_query_parameter_no_longer_truncates_the_scan(self):
        """F-5.0-14's first measured leak, and the one that is real Entrez
        syntax rather than a synthetic probe: a square bracket in the
        `term` parameter, which sits BEFORE the appended credential. Fails
        if the redactor stops scanning at that bracket, which is what the
        URL-token approach did. Separately fails if the bracketed term or
        the surrounding prose is destroyed.
        """
        secret_value = uuid.uuid4().hex
        message = (
            "HTTP 500 calling https://eutils.ncbi.nlm.nih.gov/e.fcgi"
            "?db=gene&term=BRCA1[gene]&api_key=" + secret_value + " after 3 retries"
        )

        result = audit.redact_params(message)

        assert secret_value not in result
        assert "term=BRCA1[gene]" in result
        assert "db=gene" in result
        assert result.startswith("HTTP 500 calling ")
        assert result.endswith(" after 3 retries")

    def test_a_parenthesis_earlier_in_the_path_no_longer_truncates_the_scan(self):
        """F-5.0-14's second measured leak: the boundary character sits in
        the PATH, upstream of the query string entirely, so no amount of
        care about query-value punctuation would have caught it. Fails if
        the path parenthesis truncates the scan.
        """
        secret_value = uuid.uuid4().hex
        message = "failed on https://host.example/path(v2)/x?api_key=" + secret_value + " giving up"

        result = audit.redact_params(message)

        assert secret_value not in result
        assert "/path(v2)/x" in result
        assert result.endswith(" giving up")

    def test_an_apostrophe_in_an_earlier_value_no_longer_truncates_the_scan(self):
        """F-5.0-14's third measured leak: an apostrophe in an ordinary
        author-name search term. Fails if the quote truncates the scan
        before the appended credential is reached.
        """
        secret_value = uuid.uuid4().hex
        message = "url=https://host.example/e.fcgi?term=O'Brien&api_key=" + secret_value

        result = audit.redact_params(message)

        assert secret_value not in result
        assert "O'Brien" in result
        assert "host.example" in result

    def test_control_no_boundary_character_before_the_credential_is_redacted(self):
        """The control the three arms above need to mean anything. Without
        it a green suite cannot tell "truncation is fixed" from "the
        scanner is dead and redacts nothing anywhere". This is the same
        URL shape with every boundary character removed, so it must be
        redacted by any working implementation, including the broken one
        F-5.0-14 was raised against.
        """
        secret_value = uuid.uuid4().hex
        message = (
            "HTTP 500 calling https://eutils.ncbi.nlm.nih.gov/e.fcgi"
            "?db=gene&api_key=" + secret_value + " after 3 retries"
        )

        result = audit.redact_params(message)

        assert secret_value not in result
        assert "db=gene" in result

    def test_secret_assignment_in_prose_with_no_url_at_all_is_redacted(self):
        """The case the previous implementation's docstring declared out of
        scope, closed for free by attacking the assignment rather than the
        URL. Fails if redaction still requires a `scheme://` wrapper
        somewhere in the string, since there is none here.
        """
        secret_value = uuid.uuid4().hex
        message = "authentication rejected, token=" + secret_value + " expired 4h ago"

        result = audit.redact_params(message)

        assert secret_value not in result
        assert audit.REDACTED_PLACEHOLDER in result
        assert result.startswith("authentication rejected, ")
        assert result.endswith(" expired 4h ago")

    def test_boundary_characters_inside_the_credential_do_not_truncate_it(self):
        """The limitation the previous round asserted in prose, now an
        executable arm. That docstring said a credential containing a
        token-boundary character could survive in part; here the credential
        carries a square bracket and a parenthesis in its middle and every
        fragment of it must be gone. Fails if any fragment survives, and
        separately fails if the trailing prose is swallowed with it.
        """
        secret_value = uuid.uuid4().hex
        awkward = secret_value[:8] + "[" + secret_value[8:20] + "](" + secret_value[20:] + ")"
        message = "https://host.example/x?api_key=" + awkward + " retrying"

        result = audit.redact_params(message)

        assert secret_value[:8] not in result
        assert secret_value[8:20] not in result
        assert secret_value[20:] not in result
        assert audit.REDACTED_PLACEHOLDER in result
        assert result.endswith(" retrying")

    def test_a_raw_ampersand_inside_a_credential_bounds_the_redaction_at_it(self):
        """The one input family that genuinely still bounds this rule, kept
        as an executable pin rather than a sentence in a docstring, because
        this control has now shipped two false prose claims about its own
        limits.

        A raw ampersand ends a value under URL rules, so no parser can tell
        a credential containing one from two adjacent parameters. The half
        before the ampersand is redacted and the half after survives. This
        arm goes red if either half changes, which is the point: a future
        change to the terminator set must re-examine this deliberately
        rather than move it by accident.
        """
        credential_head = uuid.uuid4().hex
        credential_tail = uuid.uuid4().hex
        message = (
            "https://host.example/x?api_key=" + credential_head + "&" + credential_tail
        )

        result = audit.redact_params(message)

        assert credential_head not in result
        assert credential_tail in result

    def test_url_with_percent_encoded_brackets_and_no_secret_is_byte_identical(self):
        """Over-redaction guard. This is what `_build_query_string` actually
        produces, percent-encoded with `safe=""`, and it carries no
        credential, so it must come back unchanged to the byte. Fails if
        the assignment rule redacts a parameter whose name is not
        secret-ish, or rebuilds the string it did not need to touch.
        """
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            "?db=gene&term=BRCA1%5Bgene%5D&retmax=20"
        )

        result = audit.redact_params({"endpoint": url})

        assert result["endpoint"] == url

    def test_prose_with_a_url_carrying_raw_punctuation_and_no_secret_is_byte_identical(self):
        """Over-redaction guard for the shape this fix widened most: an
        ordinary diagnostic message whose URL carries raw brackets and
        whose prose carries parentheses and a comma, with nothing secret
        anywhere in it. Section 20.3 records the endpoint and the error so
        an operator can diagnose the failure, so a line redacted into
        uselessness defeats its own purpose. Fails if any of it is
        rewritten.
        """
        message = (
            "HTTP 429 calling https://eutils.ncbi.nlm.nih.gov/e.fcgi"
            "?db=gene&term=BRCA1[gene] (attempt 2 of 3), backing off"
        )

        result = audit.redact_params(message)

        assert result == message


class TestValueTerminatorSet:
    """F-5.0-16: the `_redact_value_string` docstring's stated terminator
    class was narrower than the code, missing the angle bracket. F-5.0-18:
    the character list F-5.0-16 itself used to describe that gap was wrong
    in the other direction, naming eight characters, `( ) [ ] { , ; +`, that
    do not terminate the value at all. Both rounds enumerated in prose, and
    prose enumerated twice drifted twice, in opposite directions.

    This class pins the ACTUAL terminator set by walking
    `audit._VALUE_TERMINATOR_CHARS`, the code's own definition, instead of
    a list re-typed here that could drift from the regex the same way the
    docstring did. A character added to or removed from that constant
    changes what this class exercises without anyone needing to also edit
    a hardcoded list.
    """

    def test_every_declared_terminator_character_ends_the_value(self):
        """Each character in `_VALUE_TERMINATOR_CHARS`, injected immediately
        after the credential, must stop the match there and let whatever
        follows survive in plain text. Fails if a character is removed from
        the constant while the regex keeps honoring it (constant narrower
        than reality, F-5.0-16's shape) or if the constant names a
        character the regex does not actually treat as a boundary.
        """
        for char in audit._VALUE_TERMINATOR_CHARS:
            credential = uuid.uuid4().hex
            message = "api_key=" + credential + char + "TAIL"

            result = audit.redact_params(message)

            assert credential not in result, f"{char!r} did not bound the credential"
            assert "TAIL" in result, f"{char!r} was swallowed into the value instead of ending it"

    def test_whitespace_also_ends_the_value(self):
        """Whitespace terminates alongside `_VALUE_TERMINATOR_CHARS` but is
        matched via `\\s` in the regex rather than being a member of that
        string constant, so it is pinned here rather than by the walk above.
        """
        for char in (" ", "\t", "\n"):
            credential = uuid.uuid4().hex
            message = "api_key=" + credential + char + "TAIL"

            result = audit.redact_params(message)

            assert credential not in result
            assert "TAIL" in result

    def test_characters_outside_the_terminator_set_do_not_end_the_value(self):
        """The other side of the same pin, and the one F-5.0-16's own wrong
        character list would have failed: none of these end the value, so a
        credential carrying one mid-string is redacted whole, tail included,
        rather than truncated with the tail leaking in plain text. Includes
        every character F-5.0-16 wrongly claimed as an additional
        terminator, plus an ordinary alphanumeric run, so this fails both if
        a real terminator goes missing from the set above and if a
        non-terminator starts being treated as one.
        """
        candidates = "()[]{},;+" + "aZ9_.-%"
        non_terminators = [c for c in candidates if c not in audit._VALUE_TERMINATOR_CHARS]
        assert non_terminators, "the candidate list collapsed to nothing, this arm would be vacuous"

        for char in non_terminators:
            credential = uuid.uuid4().hex
            message = "api_key=" + credential + char + "TAIL&other=1"

            result = audit.redact_params(message)

            assert credential not in result
            assert "TAIL" not in result, f"{char!r} unexpectedly terminated the value"
            assert "other=1" in result

    def test_terminator_set_content_is_exactly_six_characters(self):
        """Pins the CONTENT of `_VALUE_TERMINATOR_CHARS`, not only its
        behavior, so a silent addition or removal is caught even in the
        unlikely case it happens to preserve every case above by
        coincidence. `_redact_value_string`'s docstring names this set by
        reference to the constant rather than spelling it out a third time:
        ampersand, fragment marker, quote of either kind, angle bracket.
        """
        assert set(audit._VALUE_TERMINATOR_CHARS) == {"&", "#", '"', "'", "<", ">"}


class TestErrorFieldIsStructurallyBounded:
    """The successor to `TestErrorFieldRedaction` (F-5.0-13, gap one).

    That class proved a credential inside a free-text `error` string was
    REDACTED before it was written. Every arm below is the same arm asked
    about the successor property instead, per the design change the
    product owner authorized after three rounds of scanner hardening were
    each defeated by an input of the same family: the message is never
    used at all, so there is nothing to redact. Nothing here was deleted
    to make a check pass; each arm now asserts the stronger property that
    replaced the one it used to assert.
    """

    def test_credential_in_a_raised_exception_message_never_reaches_the_line(
        self, tmp_path, monkeypatch
    ):
        """The load-bearing arm, driven through the REAL graph chokepoint
        rather than through `record_tool_call` directly, so it proves the
        call site classifies rather than merely that the sink could.

        Fails if `execute_cypher`'s audit wrapper goes back to passing
        `str(exc)`, AND fails if `classify_error_code` stops failing
        closed, since defeating the arm needs both. The populate-check
        (the line exists, has content, and names this call) is required so
        the arm cannot pass by nothing having been written at all.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        secret_value = uuid.uuid4().hex
        message = (
            "connection failed: postgresql://kg_reader:"
            + secret_value
            + "@10.0.0.5:5432/kg"
        )

        def _raise(*args, **kwargs):
            raise graph_connection.GraphConnectionError(message)

        monkeypatch.setattr(graph_connection, "_execute_cypher_impl", _raise)

        with pytest.raises(graph_connection.GraphConnectionError):
            graph_connection.execute_cypher("MATCH (n:Gene) RETURN n")

        # Populate-check: a line was actually written, for this call.
        lines = _read_lines(log_path)
        assert len(lines) == 1
        assert lines[0]
        entry = json.loads(lines[0])
        assert entry["tool"] == "cypher_query"

        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text
        # Not merely absent: no fragment of the message is present either,
        # which is what distinguishes "the message was never used" from
        # "the message was scanned and happened to come back clean".
        assert "postgresql" not in raw_text
        assert "connection failed" not in raw_text
        assert entry["error_code"] == "connection"
        assert entry["error_class"] == "GraphConnectionError"

    @pytest.mark.asyncio
    async def test_credential_in_a_transport_exception_message_never_reaches_the_line(
        self, tmp_path, monkeypatch
    ):
        """The same property at the other converted chokepoint. Fails if
        `execute_get`'s audit wrapper goes back to `str(exc)`. The
        credential here rides in the shape `_append_api_key` produces, an
        `api_key=` query parameter inside a URL inside prose, which is
        F-5.0-19's own leaking shape: the point is that this path no
        longer depends on whether the scanner catches it.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        secret_value = uuid.uuid4().hex
        message = (
            "request url=https://eutils.ncbi.nlm.nih.gov/e.fcgi?db=gene&api_key="
            + secret_value
            + " timed out after 2 attempts"
        )

        async def _raise(*args, **kwargs):
            raise ncbi_transport.TransportTimeoutError(message)

        monkeypatch.setattr(ncbi_transport, "_execute_with_retry", _raise)

        with pytest.raises(ncbi_transport.TransportTimeoutError):
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/e.fcgi",
                {"db": "gene"},
                family="eutils",
                client=object(),
            )

        lines = _read_lines(log_path)
        assert len(lines) == 1
        assert lines[0]
        entry = json.loads(lines[0])
        assert entry["tool"] == "ncbi_transport:eutils"

        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text
        assert "timed out after" not in raw_text
        assert entry["error_code"] == "timeout"
        assert entry["error_class"] == "TransportTimeoutError"

    def test_an_ordinary_failure_still_records_a_readable_reason(
        self, tmp_path, monkeypatch
    ):
        """The successor to the old no-credential round-trip arm, which
        existed to fail if redaction was so blunt it destroyed an ordinary
        message. The equivalent risk now is a line so bounded it says
        nothing, so this fails if a classified failure records neither a
        code nor a class an operator can read.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(
            tool="cypher_query",
            layer=1,
            endpoint="kg",
            latency_ms=30000.0,
            error_code="timeout",
            error_class="GraphTimeoutError",
        )

        entry = json.loads(_read_lines(log_path)[0])
        assert entry["error_code"] == "timeout"
        assert entry["error_class"] == "GraphTimeoutError"

    def test_no_error_still_round_trips_as_none(self, tmp_path, monkeypatch):
        """Fails if routing the error half through the vocabulary check
        turns a successful call's `None` into something else, for example
        the string "None" or the fail-closed `unexpected` code, which
        would make every successful call read as a failure.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(
            tool="cypher_query", layer=1, endpoint="kg", latency_ms=8.0,
        )

        entry = json.loads(_read_lines(log_path)[0])
        assert entry["error_code"] is None
        assert entry["error_class"] is None

    def test_oversized_text_cannot_reach_the_error_fields_at_all(
        self, tmp_path, monkeypatch
    ):
        """The successor to the old oversized-error disclosure arm. That
        arm proved an oversized error string was capped and the drop
        disclosed; the successor property is stronger and is what this
        asserts instead: an oversized string is not a vocabulary member
        and not an identifier, so it never becomes a field value at all
        and there is nothing left to cap. Fails if either field starts
        admitting bulk text.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        huge = "x" * (audit._MAX_PARAMS_BYTES * 2)
        audit.record_tool_call(
            tool="cypher_query", layer=1, endpoint="kg", latency_ms=8.0,
            error_code=huge, error_class=huge,
        )

        raw_text = log_path.read_text(encoding="utf-8")
        entry = json.loads(_read_lines(log_path)[0])
        assert entry["error_code"] == audit.UNEXPECTED_ERROR_CODE
        assert entry["error_class"] == audit._REFUSED_ERROR_CLASS
        # No fragment of the oversized value survives anywhere on the line.
        assert "xxxx" not in raw_text
        assert len(raw_text) < audit._MAX_PARAMS_BYTES


class TestClosedVocabularyFailsClosed:
    """The closed vocabulary is the whole control, so these arms test the
    boundary rather than the happy path.
    """

    def test_every_declared_code_is_admitted_unchanged(self):
        """Walks `AUDIT_ERROR_CODES` itself rather than a hand-typed copy,
        so a member added to the vocabulary is covered without editing
        this arm, and a member removed turns it red.
        """
        assert audit.AUDIT_ERROR_CODES, "populate-check: the vocabulary is empty"
        for code in audit.AUDIT_ERROR_CODES:
            assert audit.classify_error_code(code) == code

    @pytest.mark.parametrize(
        "unknown",
        [
            "TIMEOUT",
            "timed_out",
            "connection refused to postgresql://u:p@h/db",
            "",
            " timeout",
            "timeout ",
            42,
            object(),
            ["timeout"],
            {"code": "timeout"},
        ],
    )
    def test_anything_outside_the_vocabulary_fails_closed(self, unknown):
        """Fails if the fail-closed branch is ever softened into a
        permissive passthrough, which is the single change that would
        reopen the hole this design removes. Covers a near-miss spelling,
        a wrong case, surrounding whitespace, an empty string, and four
        non-string types, since a permissive fallback usually arrives as
        "just let a string through".
        """
        assert audit.classify_error_code(unknown) == audit.UNEXPECTED_ERROR_CODE

    def test_none_is_not_turned_into_a_failure(self):
        """Fails if the fail-closed branch swallows None too, which would
        make every successful call record `unexpected`.
        """
        assert audit.classify_error_code(None) is None

    def test_error_class_admits_an_identifier_and_refuses_anything_else(self):
        """`str.isidentifier()` is the bound, so this walks the characters
        a credential actually needs, an equals sign, a colon, a slash, an
        at sign, a question mark, an ampersand, a space and a quote, and
        asserts none of them can appear in a recorded class name.
        """
        assert audit._safe_error_class("GraphTimeoutError") == "GraphTimeoutError"
        assert audit._safe_error_class(None) is None
        for hostile in "=:/@?& \"'":
            value = "Graph" + hostile + "Error"
            assert audit._safe_error_class(value) == audit._REFUSED_ERROR_CLASS
        assert audit._safe_error_class("x" * 200) == audit._REFUSED_ERROR_CLASS
        assert audit._safe_error_class(123) == audit._REFUSED_ERROR_CLASS


class TestGuardsRefuseAHostileStrSubclass:
    """F-5.0-22. Both guards trusted the caller's object, and every bound
    either one rests on is something a `str` subclass controls: `__eq__`
    for the vocabulary check, `isidentifier` and `__len__` for the class
    name check. Each arm drives the REAL sink, so it fails on the line
    that was written rather than only on a helper's return value.
    """

    def test_a_subclass_overriding_eq_cannot_write_itself_into_error_code(
        self, tmp_path, monkeypatch
    ):
        """Fails if `classify_error_code` goes back to `isinstance` plus
        returning the caller's object. The payload is a fresh uuid so a
        match in the written line cannot come from anywhere else.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        payload = uuid.uuid4().hex
        hostile = _HostileEqStr(payload)
        # Populate-check on the attack itself: if the subclass no longer
        # compares equal to a vocabulary member, this arm would pass for
        # the wrong reason.
        assert hostile == "timeout"
        assert hostile in audit.AUDIT_ERROR_CODES

        audit.record_tool_call(
            tool="cypher_query",
            layer=1,
            endpoint="kg",
            latency_ms=4.0,
            error_code=hostile,
            error_class="GraphTimeoutError",
        )

        lines = _read_lines(log_path)
        assert len(lines) == 1
        assert lines[0]
        entry = json.loads(lines[0])
        assert entry["tool"] == "cypher_query"
        assert entry["error_code"] == audit.UNEXPECTED_ERROR_CODE
        assert payload not in log_path.read_text(encoding="utf-8")

    def test_a_subclass_lying_about_both_bounds_cannot_reach_error_class(
        self, tmp_path, monkeypatch
    ):
        """Fails if `_safe_error_class` goes back to `isinstance`. The
        value carries the exact character class the design says an
        identifier structurally cannot contain, so a pass here means the
        stated property is false rather than merely unproven.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        payload = uuid.uuid4().hex
        hostile = _HostileIdentifierStr("https://h/x?api_key=" + payload)
        # Populate-check on the attack itself.
        assert hostile.isidentifier()
        assert len(hostile) == 4

        audit.record_tool_call(
            tool="ncbi_transport:eutils",
            layer=2,
            endpoint="eutils.ncbi.nlm.nih.gov",
            latency_ms=4.0,
            error_code="timeout",
            error_class=hostile,
        )

        lines = _read_lines(log_path)
        assert len(lines) == 1
        assert lines[0]
        entry = json.loads(lines[0])
        assert entry["tool"] == "ncbi_transport:eutils"
        assert entry["error_class"] == audit._REFUSED_ERROR_CLASS
        raw_text = log_path.read_text(encoding="utf-8")
        assert payload not in raw_text
        assert "api_key" not in raw_text

    def test_a_matched_code_is_recorded_as_the_vocabulary_member_itself(self):
        """The other half of the fix, asserted by IDENTITY rather than by
        equality: what is written is the object from `AUDIT_ERROR_CODES`,
        never the caller's, so nothing a caller controls survives even
        when it compared equal.
        """
        assert audit.AUDIT_ERROR_CODES, "populate-check: the vocabulary is empty"
        for code in audit.AUDIT_ERROR_CODES:
            distinct = "".join(list(code))
            # Populate-check: an interned copy would make `is` trivially
            # true and the arm vacuous.
            assert distinct is not code
            assert audit.classify_error_code(distinct) is code


class TestErrorClassCallSitesPassAClassNameLiteral:
    """F-5.0-21. `audit.py`'s module docstring used to claim an identifier
    left a credential no path at all. It does not: `isidentifier()` is a
    shape guard and a bare alphanumeric token passes it. What actually
    keeps the field free of data is a property of the CALLERS, so it is
    pinned here, against the callers, rather than left as a sentence
    standing in front of the guard.

    Reads both converted modules' own source with `ast`, so a future call
    site passing `str(exc)`, an f-string, or any other data-derived
    expression turns this red in the edit that writes it.
    """

    def test_every_record_tool_call_passes_a_class_name_or_none(self):
        seen_literals = 0
        for module in _AUDIT_CALL_SITE_MODULES:
            arguments = _error_class_arguments(_module_source(module))
            assert arguments, (
                "populate-check: no error_class keyword found in " + module.__name__
            )
            for node in arguments:
                if isinstance(node, ast.Constant) and node.value is None:
                    continue
                assert _is_class_name_literal(node), (
                    module.__name__
                    + " passes a data-derived error_class: "
                    + ast.dump(node)
                )
                seen_literals += 1
        # Populate-check: the failure paths this arm exists to pin are
        # actually present, one per converted module, so it cannot pass by
        # having found only `error_class=None` on the success paths.
        assert seen_literals >= len(_AUDIT_CALL_SITE_MODULES)


class TestExceptionTypesAreEnumeratedNotHandTyped:
    """Every exception type in both converted modules maps to a code.

    The subclass sets below are read from the modules' own class
    definitions with `__subclasses__()`, never typed out here, so a NEW
    exception type added to either family with no mapping row turns these
    arms red instead of being silently classified `unexpected`. That is
    the difference between a fail-closed default (correct) and a silently
    unmapped type (a coverage hole wearing a fail-closed costume).
    """

    def test_every_graph_error_subclass_maps_to_a_specific_code(self):
        subclasses = graph_connection.GraphError.__subclasses__()
        names = {klass.__name__ for klass in subclasses}
        # Populate-check on the ENUMERATION itself: an import ordering that
        # left `graph_http_transport` unloaded would shrink this set and
        # make the arm pass while testing almost nothing.
        assert "GraphRateLimitedError" in names, (
            "populate-check: graph_http_transport's subclass is not registered, "
            "so this arm is not enumerating the whole family"
        )
        assert len(subclasses) >= 4
        for klass in subclasses:
            code = graph_connection.audit_error_code(klass.__new__(klass))
            assert code in audit.AUDIT_ERROR_CODES
            assert code != audit.UNEXPECTED_ERROR_CODE, (
                f"{klass.__name__} has no mapping row and fell to the catch-all"
            )

    def test_bare_graph_error_and_a_foreign_exception_both_fail_closed(self):
        assert (
            graph_connection.audit_error_code(graph_connection.GraphError("m"))
            == audit.UNEXPECTED_ERROR_CODE
        )
        assert (
            graph_connection.audit_error_code(ValueError("m"))
            == audit.UNEXPECTED_ERROR_CODE
        )

    def test_every_transport_error_subclass_maps_to_a_specific_code(self):
        subclasses = ncbi_transport.TransportError.__subclasses__()
        assert len(subclasses) >= 3, "populate-check: the family is not enumerated"
        for klass in subclasses:
            code = ncbi_transport.audit_error_code(klass.__new__(klass))
            assert code in audit.AUDIT_ERROR_CODES
            assert code != audit.UNEXPECTED_ERROR_CODE, (
                f"{klass.__name__} has no mapping row and fell to the catch-all"
            )

    def test_bare_transport_error_and_a_foreign_exception_both_fail_closed(self):
        assert (
            ncbi_transport.audit_error_code(ncbi_transport.TransportError("m"))
            == audit.UNEXPECTED_ERROR_CODE
        )
        assert (
            ncbi_transport.audit_error_code(ValueError("m"))
            == audit.UNEXPECTED_ERROR_CODE
        )

    def test_a_subclass_of_a_mapped_error_inherits_its_parents_code(self):
        """The MRO walk, not a flat dict lookup. Fails if the classifier
        stops walking, since a future refinement of an existing error, for
        example a statement-level timeout, would then read `unexpected`
        rather than `timeout`.
        """

        class NarrowerTimeout(graph_connection.GraphTimeoutError):
            pass

        assert graph_connection.audit_error_code(NarrowerTimeout("m")) == "timeout"


class TestLegacyErrorKeywordFailsClosed:
    """F-5.0-20. `pathogen_ftp_transport.py` still passes `error=str(exc)`
    at both of its audit call sites and is outside this change's declared
    file scope, so the `error` keyword survives as a deprecated alias
    routed through the SAME closed vocabulary.

    These arms are what stop that alias becoming a quiet hole: they assert
    it cannot carry text, and they assert the fidelity cost is real rather
    than pretended away, so removing the deprecation is a deliberate edit
    to this file rather than something that drifts.
    """

    def test_a_message_passed_to_the_legacy_keyword_records_unexpected(
        self, tmp_path, monkeypatch
    ):
        """Fails if the legacy keyword is ever routed anywhere other than
        `classify_error_code`, which is the only reason it is safe.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        secret_value = uuid.uuid4().hex
        audit.record_tool_call(
            tool="pathogen_detection",
            layer=2,
            endpoint="ftp.ncbi.nlm.nih.gov/pathogen",
            latency_ms=1.0,
            error="download failed from https://h/x?api_key=" + secret_value,
        )

        lines = _read_lines(log_path)
        assert len(lines) == 1
        assert lines[0]
        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text
        assert "download failed" not in raw_text
        assert json.loads(lines[0])["error_code"] == audit.UNEXPECTED_ERROR_CODE

    def test_a_real_code_on_the_legacy_keyword_is_still_honoured(
        self, tmp_path, monkeypatch
    ):
        """Fails if the alias is neutered into always writing `unexpected`.
        The alias exists so an unconverted caller keeps working, and one
        that already passes a vocabulary member should be recorded
        faithfully.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(
            tool="pathogen_detection", layer=2, endpoint="e", latency_ms=1.0,
            error="timeout",
        )

        assert json.loads(_read_lines(log_path)[0])["error_code"] == "timeout"

    def test_error_code_wins_when_both_are_supplied(self, tmp_path, monkeypatch):
        """Fails if the deprecated keyword can override the current one,
        which would let a converted call site be silently downgraded by a
        stray legacy argument.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(
            tool="t", layer=2, endpoint="e", latency_ms=1.0,
            error_code="auth", error="some raw message",
        )

        assert json.loads(_read_lines(log_path)[0])["error_code"] == "auth"


class TestKnownGapF5019:
    """F-5.0-19, PINNED AS A KNOWN GAP RATHER THAN FIXED.

    `_redact_value_string` is best-effort defense in depth over `params`,
    not a control, and it has a measured hole: a non-secret assignment
    whose value is a URL swallows the secret assignment inside it, so
    nothing is redacted at all. This class asserts the hole IS STILL
    THERE. That is deliberate and it is how this repository stops a known
    limitation being quietly forgotten: the arm fails loudly if someone
    later closes the gap without also correcting `_redact_value_string`'s
    docstring and this class, which is exactly the drift F-5.0-16 and
    F-5.0-18 were both filed for.

    If you are here because this arm went red, the gap is probably fixed.
    Do not weaken the assertion. Update the docstring in `audit.py`,
    update `tracker/phase_5.0.md`'s F-5.0-19 row, and convert these arms
    to assert redaction instead.

    The gap is no longer reachable through the error field, which is why
    it is pinned rather than escalated a fourth time: the error field
    takes a code, not a message, so this scanner is now only ever asked
    about caller-supplied `params` values.
    """

    @pytest.mark.parametrize(
        "template",
        [
            "url=https://h/x?api_key={secret}",
            "endpoint=https://h/x?api_key={secret}",
            "request url=https://h/x?api_key={secret} failed",
        ],
    )
    def test_a_url_valued_assignment_still_swallows_the_secret_inside_it(
        self, template
    ):
        """F-5.0-19's three measured shapes, output byte-identical to
        input. The discriminator is the preceding `name=` whose value is a
        URL, not the character class and not whether the value is a URL.
        """
        secret_value = uuid.uuid4().hex
        probe = template.format(secret=secret_value)
        assert audit._redact_value_string(probe) == probe
        assert secret_value in audit._redact_value_string(probe)

    def test_the_controls_that_do_still_work_are_not_also_broken(self):
        """The other half of pinning a gap: without this, an arm asserting
        a leak would also pass against a redactor that had stopped working
        entirely, which would read as "the known gap" while actually being
        a dead scanner. These two shapes differ from the ones above only
        in the leading assignment, and both must still redact.
        """
        secret_value = uuid.uuid4().hex
        bare_url = "https://h/x?api_key=" + secret_value
        assert secret_value not in audit._redact_value_string(bare_url)
        after_other_param = "db=gene api_key=" + secret_value
        assert secret_value not in audit._redact_value_string(after_other_param)


class TestTraceIdContextVar:
    def test_trace_id_recorded_when_scope_is_active(self, tmp_path, monkeypatch):
        """Fails if `record_tool_call` ignores the ContextVar and always
        writes null, or hardcodes a value.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        with audit.trace_id_scope("run-123"):
            audit.record_tool_call(tool="t", layer=1, endpoint="kg", latency_ms=1.0)

        entry = json.loads(_read_lines(log_path)[0])
        assert entry["trace_id"] == "run-123"

    def test_trace_id_is_null_when_no_scope_is_active(self, tmp_path, monkeypatch):
        """Fails if a prior test's scope leaks, or if the getter fabricates
        a value instead of returning None for a caller with no run in
        scope (the s3-kgx-export case named in the ticket).
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)
        assert audit.current_trace_id() is None

        audit.record_tool_call(tool="t", layer=1, endpoint="kg", latency_ms=1.0)

        entry = json.loads(_read_lines(log_path)[0])
        assert entry["trace_id"] is None

    def test_scope_restores_previous_value_on_exit(self):
        """Fails if `trace_id_scope` leaks its value past the `with` block,
        which would bleed one run's trace_id into the next call on the same
        thread or task.
        """
        with audit.trace_id_scope("outer"):
            with audit.trace_id_scope("inner"):
                assert audit.current_trace_id() == "inner"
            assert audit.current_trace_id() == "outer"
        assert audit.current_trace_id() is None


class TestBestEffort:
    def test_writer_failure_does_not_raise(self, tmp_path, monkeypatch):
        """Fails if a filesystem error (here, a parent path component that
        is a plain file rather than a directory, so mkdir cannot create it)
        propagates out of `record_tool_call` instead of being swallowed.
        """
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        unwritable_path = blocker / "audit.jsonl"

        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: unwritable_path)

        # No exception means the test itself passes; the assertion below
        # confirms the call actually reached the failing path rather than
        # returning early for an unrelated reason.
        audit.record_tool_call(tool="t", layer=1, endpoint="kg", latency_ms=1.0)
        assert not unwritable_path.exists()

    def test_disabled_writes_nothing_at_all(self, tmp_path, monkeypatch):
        """Fails if `record_tool_call` creates the file or its parent
        directory even when `audit_enabled()` is False.
        """
        log_path = tmp_path / "should_not_exist" / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: False)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(
            tool="t", layer=1, endpoint="kg", latency_ms=1.0,
            params={"api_key": "should-never-be-touched"},
        )

        assert not log_path.exists()
        assert not log_path.parent.exists()


class TestParamsAreOptional:
    def test_none_params_and_none_record_ids_round_trip_as_empty(
        self, tmp_path, monkeypatch
    ):
        """Fails if a caller with no params or record ids (a graph query
        with no returned rows) crashes rather than recording empty
        collections.
        """
        log_path = tmp_path / "audit.jsonl"
        monkeypatch.setattr(audit, "audit_enabled", lambda: True)
        monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)

        audit.record_tool_call(
            tool="cypher_query", layer=1, endpoint="kg", latency_ms=3.0,
            params=None, record_ids=None,
        )

        entry = json.loads(_read_lines(log_path)[0])
        assert entry["params"] == {}
        assert entry["record_ids"] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
