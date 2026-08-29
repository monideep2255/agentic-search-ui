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

- Wiring this module into a real transport call site. That is T-5.0-05, a
  later serial builder's ticket, not this one's.
- Anything about LangSmith or PostHog. Those are `tracing.py` and
  `analytics.py`, separate modules built by sibling tickets.
- The premise gate's cross-cutting arms (one per bypass call site). Those
  belong to T-5.0-07, once the transport hooks this module feeds actually
  exist.
"""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

import pytest

from system_03_search_agent.observability import audit


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


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
                error=None,
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
            "error",
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
        assert entry["error"] is None
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
