"""Unit tests for `ncbi_eutils_actions`: search, summary, fetch, link.

No live network anywhere in this file. Every case mocks at the transport
boundary, `ncbi_transport.execute_get`, patched to return a canned
`httpx.Response` or raise a canned `ncbi_transport.TransportError`. Live
network coverage of the real endpoints is `test_ncbi_efetch_premise.py`'s
job, not this file's.

Covers, per action: happy path, empty, error-body-under-200, and the four
traps named in `ncbi_eutils_actions`'s module docstring:

    1. An unvalidated field tag is rejected before any request is sent
       (search).
    2. source_url always resolves to the record host, never the fetch host
       eutils.ncbi.nlm.nih.gov (fetch, summary, link).
    3. link only ever returns records whose db matches the requested
       target, even when the raw ELink body carries a linksetdb aimed at a
       different db (link).
    4. An empty response fabricates zero records, never a placeholder with
       a source_url (search, fetch, link).

Depends on:
    - system_03_search_agent.tools.ncbi_eutils_actions (the module under
      test)
    - system_03_search_agent.tools.ncbi_transport, monkeypatched at
      execute_get
    - system_03_search_agent.tools.ncbi_efetch_schemas, for constructing
      valid action input models
    - httpx, for constructing canned Response objects

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from system_03_search_agent.tools import ncbi_eutils_actions, ncbi_transport
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchFetchInput,
    NcbiEfetchLinkInput,
    NcbiEfetchSearchInput,
    NcbiEfetchSummaryInput,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Fresh EInfo cache for every test, so one test's seed never leaks into another."""
    ncbi_eutils_actions.reset_einfo_cache_for_tests()
    yield
    ncbi_eutils_actions.reset_einfo_cache_for_tests()


def _json_response(body: dict[str, Any], *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


def _xml_response(text: str, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code, content=text.encode(), headers={"content-type": "text/xml"}
    )


class _ScriptedTransport:
    """Replaces ncbi_transport.execute_get with a scripted sequence of responses.

    Each entry is either an httpx.Response (returned) or an Exception
    (raised), popped in call order. Records every call's (url, params) so a
    test can assert whether the transport was invoked at all, and how many
    times.
    """

    def __init__(self, items: list[httpx.Response | Exception]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, url: str, params: dict[str, Any], **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, "params": dict(params), "kwargs": kwargs})
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _install(monkeypatch: pytest.MonkeyPatch, items: list[httpx.Response | Exception]) -> _ScriptedTransport:
    scripted = _ScriptedTransport(items)
    monkeypatch.setattr(ncbi_eutils_actions.ncbi_transport, "execute_get", scripted)
    return scripted


_EINFO_GENE_FIELDS = {
    "einforesult": {
        # Re-review round 1, adversarial pass (2026-08-07): live EInfo
        # wraps dbinfo in a ONE-ELEMENT LIST, not a bare dict, and its
        # `db=gene` fieldlist has NO entry whose abbreviation is "SYM" (the
        # closest is "GENE", fullname "Gene Name", description "Symbol or
        # symbols of the gene"). The previous fixture invented both the
        # dict shape and a "SYM" entry that live NCBI never returns, which
        # is exactly how this module's own field-tag validation shipped
        # broken against every real EInfo response: the tests it was
        # supposed to satisfy were testing the author's belief about the
        # shape, not the shape NCBI actually sends. `sym` still validates
        # correctly below via `_EINFO_HIDDEN_VALID_FIELDS`, the same
        # supplement production code uses for this exact gap.
        "dbinfo": [
            {
                "dbname": "gene",
                "fieldlist": [
                    {"name": "ORGN", "fullname": "Organism"},
                    {"name": "GENE", "fullname": "Gene Name"},
                ],
            }
        ]
    }
}


def _seed_einfo_cache(db: str, fields: set[str]) -> None:
    """Directly warm the EInfo cache, bypassing any network call.

    Used by the trap-1 test below to prove field-tag rejection needs zero
    transport calls once the cache is warm, matching how a real process
    behaves after its first EInfo fetch for a db.
    """
    ncbi_eutils_actions._einfo_field_cache[db] = frozenset(f.lower() for f in fields)


# ===========================================================================
# search
# ===========================================================================


class TestSearch:
    @pytest.mark.asyncio
    async def test_happy_path_returns_idlist_in_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [_json_response({"esearchresult": {"count": "1", "idlist": ["7157"]}})],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(
                action="search", db="gene", term="TP53[sym] AND human[orgn]", retmax=10
            )
        )
        assert output.status == "ok"
        assert output.action == "search"
        assert output.records[0].fields["idlist"] == ["7157"]
        assert output.record_count == 1

    @pytest.mark.asyncio
    async def test_relevance_sort_is_forwarded_to_esearch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UI fix loop, 2026-09-20: the ESearch request must carry `sort=relevance`.

        Live-verified against the real API (not exercised here, no network
        in this file): ESearch with no `sort` parameter orders by
        most-recently-added rather than relevance, which is how a GCK query
        surfaced "Fermentation of mulberry leaf extract by Aspergillus
        chevalieri" instead of a paper about the gene. This pins the wiring
        that closes it: `NcbiEfetchSearchInput`'s default `sort="relevance"`
        must actually reach the transport call's params, not just exist on
        the schema. Reverting the `request_params["sort"] = params.sort`
        line in `ncbi_eutils_actions.search` fails this test with a
        `KeyError` on `scripted.calls[0]["params"]["sort"]`, confirmed
        while writing this test.
        """
        scripted = _install(
            monkeypatch,
            [_json_response({"esearchresult": {"count": "1", "idlist": ["7157"]}})],
        )
        await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="gene", term="GCK", retmax=10)
        )
        assert scripted.calls[0]["params"]["sort"] == "relevance"

    @pytest.mark.asyncio
    async def test_zero_hit_is_empty_not_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Trap 4, half of the near-miss pair: count 0, no ERROR key, no records fabricated."""
        _install(
            monkeypatch,
            [_json_response({"esearchresult": {"count": "0", "idlist": []}})],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="pubmed", term="zzznohits", retmax=10)
        )
        assert output.status == "empty"
        assert output.records == []
        assert output.record_count == 0

    @pytest.mark.asyncio
    async def test_error_body_under_http_200_is_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trap 4, the other half: an ERROR key under HTTP 200 must not read as ok or empty."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "esearchresult": {
                            "ERROR": "Search Backend failed: ... Empty Term in the request",
                            "count": "0",
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="pubmed", term="((()))", retmax=10)
        )
        assert output.status == "error"
        assert output.records == []
        assert "Empty Term in the request" in output.error

    @pytest.mark.asyncio
    async def test_unvalidated_field_tag_rejected_with_no_transport_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trap 1. Cache pre-warmed, so rejection needs zero calls to the transport."""
        _seed_einfo_cache("gene", {"sym", "orgn", "gene"})
        scripted = _install(monkeypatch, [])  # no responses scripted: any call is a test failure

        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(
                action="search",
                db="gene",
                term="TP53",
                field_tags=["notarealfieldtag"],
                retmax=10,
            )
        )

        assert output.status == "error"
        assert "notarealfieldtag" in output.error
        assert scripted.calls == [], (
            "an unvalidated field tag must be rejected before any request, but the "
            f"transport was invoked: {scripted.calls!r}"
        )

    @pytest.mark.asyncio
    async def test_valid_field_tag_fetches_einfo_then_proceeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A validated tag does cost one EInfo call (cold cache) plus the ESearch call."""
        scripted = _install(
            monkeypatch,
            [
                _json_response(_EINFO_GENE_FIELDS),
                _json_response({"esearchresult": {"count": "1", "idlist": ["7157"]}}),
            ],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(
                action="search", db="gene", term="TP53", field_tags=["sym"], retmax=10
            )
        )
        assert output.status == "ok"
        assert len(scripted.calls) == 2
        assert "einfo.fcgi" in scripted.calls[0]["url"]
        assert "esearch.fcgi" in scripted.calls[1]["url"]
        # F-3.1-29: an ATOMIC term takes the tag bare. The parenthesized form
        # "(TP53)[sym]" this used to assert is not valid Entrez syntax: live
        # ESearch parses it as `TP53[All Fields] AND sym[All Fields]`, which
        # unscopes the search entirely. See TestFieldTagScoping below.
        assert scripted.calls[1]["params"]["term"] == "TP53[sym]"

    @pytest.mark.asyncio
    async def test_second_call_reuses_cached_einfo_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted = _install(
            monkeypatch,
            [
                _json_response(_EINFO_GENE_FIELDS),
                _json_response({"esearchresult": {"count": "1", "idlist": ["1"]}}),
                _json_response({"esearchresult": {"count": "1", "idlist": ["2"]}}),
            ],
        )
        params = NcbiEfetchSearchInput(
            action="search", db="gene", term="X", field_tags=["sym"], retmax=10
        )
        await ncbi_eutils_actions.search(params)
        await ncbi_eutils_actions.search(params)
        # 1 EInfo call (cached after) + 2 ESearch calls = 3, not 4.
        assert len(scripted.calls) == 3

    @pytest.mark.asyncio
    async def test_transport_error_maps_to_status_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [ncbi_transport.TransportTimeoutError("eutils.ncbi.nlm.nih.gov timed out")],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="pubmed", term="x", retmax=10)
        )
        assert output.status == "error"
        assert "timed out" in output.error

    @pytest.mark.asyncio
    async def test_record_count_equals_len_records_on_a_multi_id_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-25 (reopened): `record_count` means "how many record objects
        are in `records`" in EVERY action of this module.

        `search` used to report `len(idlist)` while `len(records)` was 1, so
        the one action returning an aggregate record was also the one action
        measuring `record_count` in a different unit from the other three. A
        25-id search reported `record_count=25` alongside a single record.
        """
        ids = [str(7000 + n) for n in range(25)]
        _install(
            monkeypatch,
            [_json_response({"esearchresult": {"count": "25", "idlist": ids}})],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="gene", term="kinase", retmax=100)
        )
        assert output.status == "ok"
        assert len(output.records) == 1
        assert output.record_count == len(output.records), (
            f"record_count must equal len(records) in every action; got "
            f"record_count={output.record_count} with {len(output.records)} record(s)"
        )
        # The ID population is still reported, in its own units, never mixed
        # into the record units.
        assert output.records[0].fields["idlist_count"] == 25
        assert output.total_available == 25
        assert output.truncated is False

    @pytest.mark.asyncio
    async def test_idlist_beyond_one_hundred_ids_is_capped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-12: the 100-id cap had a comment claiming it prevented a
        max_length bypass, but no test ever fed more than 100 ids, so the
        claim was unenforced. `retmax` accepts up to 500
        (ncbi_efetch_schemas.py), so this is reachable with ordinary input.

        Per `self-eval-loop`'s "review a fix harder than new code": where a
        comment asserts a correctness property, a test must assert the same
        property, or the comment is a liability rather than an aid.
        """
        ids = [str(100000 + n) for n in range(500)]
        _install(
            monkeypatch,
            [_json_response({"esearchresult": {"count": "500", "idlist": ids}})],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="gene", term="kinase", retmax=500)
        )
        assert output.status == "ok"
        capped = output.records[0].fields["idlist"]
        assert len(capped) == 100, (
            f"the idlist must be capped at 100 to match the record list's own "
            f"max_length bound; got {len(capped)} ids through the aggregate record"
        )
        assert capped == ids[:100]
        assert output.records[0].fields["idlist_count"] == 100
        assert output.record_count == 1
        # 500 available versus 100 returned: truncation must be reported.
        assert output.total_available == 500
        assert output.truncated is True

    @pytest.mark.asyncio
    async def test_einfo_rate_limit_reports_a_rate_limit_not_a_validation_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-19 remainder: `_get_einfo_fields` never read
        `response.status_code`, so a 429 or 503 on the EInfo hop surfaced as
        "could not validate field_tags", telling the next agent step to
        rewrite its request when the correct action is to back off and retry.
        """
        _install(
            monkeypatch,
            [
                httpx.Response(
                    429,
                    content=b"rate limited",
                    headers={"content-type": "text/plain", "retry-after": "7"},
                )
            ],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(
                action="search", db="gene", term="TP53", field_tags=["sym"], retmax=10
            )
        )
        assert output.status == "error"
        assert "429" in output.error
        assert "rate limited" in output.error
        assert "backoff" in output.error
        # F-3.1-12: the numeric retry delay is surfaced when it is available.
        assert "7 seconds" in output.error, (
            f"a Retry-After value must reach the error message so the next "
            f"agent step knows how long to wait; got {output.error!r}"
        )

    @pytest.mark.asyncio
    async def test_einfo_server_error_is_actionable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-19 remainder, the 5xx arm of the same EInfo gap."""
        _install(
            monkeypatch,
            [httpx.Response(503, content=b"", headers={"content-type": "text/plain"})],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(
                action="search", db="gene", term="TP53", field_tags=["sym"], retmax=10
            )
        )
        assert output.status == "error"
        assert "503" in output.error
        assert "server error" in output.error
        assert "Retry after a backoff" in output.error

    @pytest.mark.asyncio
    async def test_rate_limited_search_keeps_backoff_guidance_without_retry_after(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-12: with no `retry_after` available from either the transport
        layer or the upstream header, the message still names the next action.
        """
        _install(
            monkeypatch,
            [httpx.Response(429, content=b"", headers={"content-type": "text/plain"})],
        )
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="pubmed", term="x", retmax=10)
        )
        assert output.status == "error"
        assert "Retry after a backoff" in output.error
        assert "reduce the request rate" in output.error
        assert "seconds" not in output.error

    @pytest.mark.asyncio
    async def test_transport_supplied_retry_after_is_surfaced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-review round 1 integration fix: `_retry_after_hint` reads the
        `Retry-After` header through `ncbi_transport.parse_retry_after`
        rather than a hand-rolled `headers.get("retry-after")`, so it
        inherits that module's more careful parsing. An HTTP-date-form
        header (the rarer of the two RFC 9110 forms, and the case a naive
        `float(header)` cast cannot handle at all) must still produce a
        numeric second count in the message, not be silently dropped.
        """
        from datetime import UTC, datetime, timedelta

        future = datetime.now(UTC) + timedelta(seconds=42)
        http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response = httpx.Response(
            429,
            content=b"",
            headers={"content-type": "text/plain", "retry-after": http_date},
        )
        _install(monkeypatch, [response])
        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(action="search", db="pubmed", term="x", retmax=10)
        )
        assert output.status == "error"
        assert "seconds" in output.error
        # Allow a couple of seconds of test-execution drift rather than
        # asserting an exact "42 seconds", since the date is relative to
        # "now" at two different points a few lines apart.
        import re

        match = re.search(r"Retry after ([\d.]+) seconds", output.error)
        assert match is not None, output.error
        assert 38 <= float(match.group(1)) <= 42


# ===========================================================================
# field_tags scoping (F-3.1-29 / F-3.1-23)
# ===========================================================================


class TestFieldTagScoping:
    """F-3.1-29: Entrez scopes a field tag to an ATOMIC term only.

    Every expectation here was live-verified against real ESearch on db=gene
    while the fix was written:

        BRCA1[sym] AND human[orgn]    -> count 1,   idlist ["672"]
            querytranslation: BRCA1[sym] AND "Homo sapiens"[Organism]
        (BRCA1)[sym] AND human[orgn]  -> count 190, first id "1956"
            querytranslation: BRCA1[All Fields] AND sym[All Fields] AND ...

    The parenthesized form is not a stylistic difference. Entrez does not
    apply a tag to a parenthesized group: it reads the group and the tag as
    two separate unscoped ANDed terms, the literal word "sym" becomes a
    free-text search term, and the flagship symbol lookup then ranks a wrong
    gene (1956, EGFR) above the intended one (672, BRCA1).

    What this class does NOT cover, stated so the gap is arguable rather than
    invisible (per `goal-contracts`, "a verify surface must state its own
    coverage"): it asserts the TERM STRING this module builds, against
    behavior measured live at fix time. It does not re-query ESearch on every
    run, so a future change in Entrez's own parsing of `term[tag]` would not
    be caught here. The live assertions belong to the premise gate, not to
    this no-network file.
    """

    def test_atomic_term_takes_the_tag_bare_with_no_parentheses(self) -> None:
        term, error = ncbi_eutils_actions._apply_field_tags("BRCA1", ["sym"])
        assert error is None
        assert term == "BRCA1[sym]", (
            f"an atomic term must take the tag bare; {term!r} with parentheses "
            f"is parsed by Entrez as two unscoped ANDed terms"
        )

    def test_parenthesized_form_is_never_emitted(self) -> None:
        """The specific wrong-answer shape F-3.1-29 names, pinned directly."""
        term, _ = ncbi_eutils_actions._apply_field_tags("BRCA1", ["sym"])
        assert "(" not in term and ")" not in term

    def test_multi_word_term_fails_closed_with_an_actionable_error(self) -> None:
        term, error = ncbi_eutils_actions._apply_field_tags("BRCA1 AND cancer", ["sym"])
        assert term is None, (
            "a multi-token term has no safe single-field scoping, so it must "
            "fail closed rather than emit syntax that silently misscopes"
        )
        assert error is not None
        assert "single-token" in error
        assert "never sent" in error
        # Actionable: it must say what to do next, not only what failed.
        assert "omit" in error or "Retry" in error

    @pytest.mark.asyncio
    async def test_multi_word_term_sends_no_request_at_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failing closed means failing BEFORE the wire, like trap 1's own path."""
        _seed_einfo_cache("gene", {"sym", "orgn", "gene"})
        scripted = _install(monkeypatch, [])  # any call is a test failure

        output = await ncbi_eutils_actions.search(
            NcbiEfetchSearchInput(
                action="search",
                db="gene",
                term="BRCA1 AND cancer",
                field_tags=["sym"],
                retmax=10,
            )
        )
        assert output.status == "error"
        assert "single-token" in output.error
        assert scripted.calls == [], (
            f"a term that cannot be safely scoped must never reach the wire, "
            f"but the transport was invoked: {scripted.calls!r}"
        )

    @pytest.mark.parametrize(
        "hostile_term",
        [
            "BRCA1] OR cancer[titl",  # closes its own tag, opens another
            "BRCA1]OR[titl",  # the same, with no whitespace to trip on
            "(BRCA1 OR TP53)",  # a pre-parenthesized boolean group
            'BRCA1"',  # an unbalanced quote
            "BRCA1 ",  # trailing whitespace, still not atomic
        ],
    )
    def test_a_term_cannot_escape_its_own_scoping_construct(
        self, hostile_term: str
    ) -> None:
        term, error = ncbi_eutils_actions._apply_field_tags(hostile_term, ["sym"])
        assert term is None, (
            f"{hostile_term!r} must not be placed into a `term[tag]` construct; "
            f"it produced {term!r}"
        )
        assert error is not None

    def test_multiple_tags_scope_each_tag_against_the_atomic_term(self) -> None:
        """Live-verified: `(BRCA1[sym] OR BRCA1[gene])` keeps BOTH tags scoped.

        querytranslation came back as `BRCA1[sym] OR BRCA1[gene]`, with no
        All Fields fallback. The old form, `(BRCA1)[sym] OR (BRCA1)[gene]`,
        returned 37585 hits against the correct form's 660.
        """
        term, error = ncbi_eutils_actions._apply_field_tags("BRCA1", ["sym", "gene"])
        assert error is None
        assert term == "(BRCA1[sym] OR BRCA1[gene])"

    def test_a_malformed_tag_is_refused_rather_than_interpolated(self) -> None:
        """Defense in depth behind the EInfo validation: a tag carrying a
        bracket could break out of the construct it is placed into.
        """
        term, error = ncbi_eutils_actions._apply_field_tags("BRCA1", ["sym] OR x["])
        assert term is None
        assert error is not None
        assert "well-formed" in error

    def test_empty_field_tags_leaves_the_term_untouched(self) -> None:
        """Premise gate case 1's shape: the term already carries its own tags."""
        term, error = ncbi_eutils_actions._apply_field_tags(
            "BRCA1[sym] AND human[orgn]", []
        )
        assert error is None
        assert term == "BRCA1[sym] AND human[orgn]"


# ===========================================================================
# summary
# ===========================================================================


class TestSummary:
    @pytest.mark.asyncio
    async def test_happy_path_extracts_verified_gene_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["7157"],
                            "7157": {
                                "uid": "7157",
                                "name": "TP53",
                                "description": "tumor protein p53",
                                "chromosome": "17",
                                "maplocation": "17p13.1",
                                "mim": ["191170"],
                                "organism": {"scientificname": "Homo sapiens"},
                                "extraneous_untracked_field": "should not appear",
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gene", ids=["7157"])
        )
        assert output.status == "ok"
        assert output.record_count == 1
        fields = output.records[0].fields
        assert fields["name"] == "TP53"
        assert fields["description"] == "tumor protein p53"
        assert fields["chromosome"] == "17"
        assert "extraneous_untracked_field" not in fields
        assert output.records[0].source_url == "https://www.ncbi.nlm.nih.gov/gene/7157"

    @pytest.mark.asyncio
    async def test_gene_summary_field_passes_through_the_allowlist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`summary` is an addition beyond Section 6.2's table (see the
        comment beside `_SUMMARY_FIELDS_BY_DB["gene"]`): the only
        plain-English explanatory text NCBI publishes per gene. This is the
        populate-check that the addition actually reaches the caller, not
        just that the constant contains the string.

        The mutation arm for this check is `_SUMMARY_FIELDS_BY_DB["gene"]`
        itself: remove `"summary"` from that tuple and this assertion goes
        red, because the field is no longer allowlisted through. Verified by
        hand while writing this test, then restored; there is no separate
        mutation-harness file for this module, so the arm is the allowlist
        constant itself rather than a parametrized mutation table like
        `core/test_discontinued_gene_mutation.py` uses for `status` and
        `currentid`.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["672"],
                            "672": {
                                "uid": "672",
                                "name": "BRCA1",
                                "summary": (
                                    "This gene encodes a 190 kD nuclear "
                                    "phosphoprotein that plays a role in "
                                    "maintaining genomic stability, and it "
                                    "also acts as a tumor suppressor."
                                ),
                                "an_unlisted_field": "should not appear",
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gene", ids=["672"])
        )
        assert output.status == "ok"
        fields = output.records[0].fields
        assert "summary" in fields, (
            "`summary` must reach the caller for `db=gene`, but it was "
            f"filtered out; fields returned: {sorted(fields)}"
        )
        assert fields["summary"].startswith(
            "This gene encodes a 190 kD nuclear phosphoprotein"
        )
        assert "an_unlisted_field" not in fields, (
            "the allowlist must still filter everything not named in it, "
            "even with `summary` added"
        )

    @pytest.mark.asyncio
    async def test_medgen_clinical_features_are_parsed_out_of_conceptmeta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-8.1-06 (tracker/phase_8.1.md): a phenotype question names
        phenotypes. `clinical_features` is an addition beyond Section 6.2's
        table, exactly as `gene`'s `summary` field is: `conceptmeta` never
        reaches the caller whole (see the comment above
        `_parse_medgen_clinical_features`), only this parsed, bounded list.

        The fixture's `conceptmeta` mirrors MedGen's real shape for Marfan
        syndrome (UID 44287), measured live 2026-09-25: several sibling
        top-level elements (`Names`, `ClinicalFeatures`, ...), not one
        document, with the HPO id on the `ClinicalFeature` element's own
        `SDUI` attribute.
        """
        conceptmeta = (
            "<Names><Name type=\"preferred\">Marfan syndrome</Name></Names>"
            "<ClinicalFeatures>"
            '<ClinicalFeature uid="8153" CUI="C0003504" TUI="T047" SDUI="HP:0001659">'
            "<Name>Aortic regurgitation</Name>"
            "<SemanticType>Disease or Syndrome</SemanticType>"
            "</ClinicalFeature>"
            '<ClinicalFeature uid="2047" CUI="C0003706" TUI="T019" SDUI="HP:0001166">'
            "<Name>Arachnodactyly</Name>"
            "</ClinicalFeature>"
            '<ClinicalFeature uid="41704" CUI="C0013581" TUI="T019">'
            "<Name>No HPO id on this one</Name>"
            "</ClinicalFeature>"
            "</ClinicalFeatures>"
        )
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["44287"],
                            "44287": {
                                "uid": "44287",
                                "conceptid": "C0024796",
                                "title": "Marfan syndrome",
                                "definition": "A connective tissue disorder.",
                                "semantictype": ["Disease or Syndrome"],
                                "conceptmeta": conceptmeta,
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="medgen", ids=["44287"])
        )
        assert output.status == "ok"
        fields = output.records[0].fields
        assert "conceptmeta" not in fields, (
            "the raw 35KB conceptmeta blob must never reach the caller whole"
        )
        features = fields["clinical_features"]
        assert features == [
            {"name": "Aortic regurgitation", "hpo_id": "HP:0001659"},
            {"name": "Arachnodactyly", "hpo_id": "HP:0001166"},
            {"name": "No HPO id on this one"},
        ]

    @pytest.mark.asyncio
    async def test_medgen_with_no_clinical_features_states_an_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When MedGen carries no `ClinicalFeatures` block at all (a concept
        with nothing but names and cross-references), the key is still
        present as `[]`, never omitted, so a caller can disclose "MedGen
        lists no clinical features for this concept" instead of reading a
        missing key as "not checked" (the ticket's acceptance criterion)."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["1"],
                            "1": {
                                "uid": "1",
                                "conceptid": "C0000001",
                                "title": "A concept with no clinical features",
                                "conceptmeta": "<Names><Name>x</Name></Names>",
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="medgen", ids=["1"])
        )
        assert output.records[0].fields["clinical_features"] == []

    @pytest.mark.asyncio
    async def test_medgen_clinical_features_are_capped_in_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ticket's own measurement, 70 `ClinicalFeature` entries for
        Marfan syndrome, is capped to `_MAX_CLINICAL_FEATURES` (30) before it
        reaches a prompt, per `.claude/rules/production-standards.md`'s
        multi-agent pipeline gate (`maxItems` on every array)."""
        many = "".join(
            f'<ClinicalFeature SDUI="HP:{i:07d}"><Name>Feature {i}</Name></ClinicalFeature>'
            for i in range(70)
        )
        conceptmeta = f"<ClinicalFeatures>{many}</ClinicalFeatures>"
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["44287"],
                            "44287": {
                                "uid": "44287",
                                "conceptid": "C0024796",
                                "title": "Marfan syndrome",
                                "conceptmeta": conceptmeta,
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="medgen", ids=["44287"])
        )
        features = output.records[0].fields["clinical_features"]
        assert len(features) == ncbi_eutils_actions._MAX_CLINICAL_FEATURES
        assert features[0]["name"] == "Feature 0"

    @pytest.mark.asyncio
    async def test_medgen_conceptmeta_with_a_doctype_or_entity_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`.claude/rules/production-standards.md`: NCBI XML parsers must
        disable external entities. `conceptmeta` is a content fragment, so a
        legitimate one never carries a DOCTYPE; one that does is rejected
        outright rather than parsed, matching `ncbi_transport.py`'s own
        DOCTYPE/ENTITY reject for the same reason. Fails closed to an empty
        list, never a crash, never the raw markup passed through."""
        hostile = (
            '<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            "<ClinicalFeatures><ClinicalFeature><Name>&xxe;</Name></ClinicalFeature>"
            "</ClinicalFeatures>"
        )
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["1"],
                            "1": {
                                "uid": "1",
                                "conceptid": "C0000001",
                                "title": "hostile",
                                "conceptmeta": hostile,
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="medgen", ids=["1"])
        )
        assert output.records[0].fields["clinical_features"] == []

    @pytest.mark.asyncio
    async def test_clinvar_germline_classification_passed_through_as_object(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """docs/ncbi/Tool_implementation_mechanics.md:110-115: an object, not a flat scalar."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["12345"],
                            "12345": {
                                "uid": "12345",
                                "accession": "VCV000012345",
                                "germline_classification": {
                                    "description": "Pathogenic",
                                    "review_status": "criteria provided",
                                },
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="clinvar", ids=["12345"])
        )
        classification = output.records[0].fields["germline_classification"]
        assert isinstance(classification, dict)
        assert classification["description"] == "Pathogenic"

    @pytest.mark.parametrize(
        ("db", "allowlisted_key", "allowlisted_value"),
        [
            ("bioproject", "project_title", "A real project title"),
            ("biosample", "accession", "SAMN12345678"),
            ("assembly", "assemblyaccession", "GCF_000001405.40"),
            ("gds", "accession", "GSE12345"),
            ("sra", "runs", "<Run acc=\"SRR1\"/>"),
        ],
    )
    @pytest.mark.asyncio
    async def test_the_five_formerly_unlisted_dbs_now_filter_by_allowlist(
        self,
        monkeypatch: pytest.MonkeyPatch,
        db: str,
        allowlisted_key: str,
        allowlisted_value: str,
    ) -> None:
        """F-3.1-10 (reopened): these five databases had no field allowlist at
        all and copied EVERY response key through, bounded only by a 40-key
        count cap. A count cap is not a field filter: it bounds how MUCH
        untrusted external content reaches the model, not WHICH content, and
        four of the five return fewer than 40 keys, so the cap never engaged.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["999"],
                            "999": {
                                "uid": "999",
                                allowlisted_key: allowlisted_value,
                                "an_unlisted_key": "must not reach the model",
                                "sortkey": "internal ranking noise",
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db=db, ids=["999"])
        )
        assert output.status == "ok"
        fields = output.records[0].fields
        assert fields[allowlisted_key] == allowlisted_value
        assert "an_unlisted_key" not in fields, (
            f"db={db} must filter response keys through an allowlist, but an "
            f"unlisted key reached the output: {sorted(fields)}"
        )
        assert "sortkey" not in fields

    @pytest.mark.asyncio
    async def test_every_summary_db_has_an_allowlist(self) -> None:
        """F-3.1-10 (reopened): the generic passthrough is unreachable from
        `summary` now, so no future db can silently regain a raw passthrough
        just by being added to the enum without a field list.
        """
        from system_03_search_agent.tools.ncbi_efetch_schemas import SummaryDb

        declared = set(SummaryDb.__args__)
        allowlisted = set(ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB)
        assert declared - allowlisted == set(), (
            f"every SummaryDb value needs a field allowlist, otherwise it falls "
            f"back to a raw passthrough of untrusted content; missing: "
            f"{sorted(declared - allowlisted)}"
        )

    @pytest.mark.asyncio
    async def test_a_hostile_value_nested_in_a_dict_is_capped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-10 (reopened): the per-value cap applied to TOP-LEVEL strings
        only, so a 50,000-character value nested one level down inside a dict
        bypassed it entirely and flowed to the model uncapped.

        clinvar's `germline_classification` is a real nested object, so this
        is the ordinary shape of the data, not a contrived one.
        """
        hostile = "A" * 50_000
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["12345"],
                            "12345": {
                                "uid": "12345",
                                "accession": "VCV000012345",
                                "germline_classification": {
                                    "description": hostile,
                                    "review_status": "criteria provided",
                                },
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="clinvar", ids=["12345"])
        )
        nested = output.records[0].fields["germline_classification"]["description"]
        assert len(nested) < 50_000, (
            f"a value nested inside a dict must be capped, but {len(nested)} "
            f"characters of untrusted content survived"
        )
        assert len(nested) <= ncbi_eutils_actions._MAX_FIELD_VALUE_CHARS + 20
        assert nested.endswith("[truncated]")
        # The sibling key must survive the cap intact.
        assert (
            output.records[0].fields["germline_classification"]["review_status"]
            == "criteria provided"
        )

    @pytest.mark.asyncio
    async def test_a_hostile_value_nested_in_a_list_is_capped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-10 (reopened), the list arm. gds's `samples` is a real list of
        objects, so a list of dicts is the ordinary shape here too.
        """
        hostile = "B" * 50_000
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["200342712"],
                            "200342712": {
                                "uid": "200342712",
                                "accession": "GSE12345",
                                "title": [hostile, {"deeper": hostile}],
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gds", ids=["200342712"])
        )
        listed = output.records[0].fields["title"]
        assert len(listed[0]) < 50_000, (
            f"a string inside a list must be capped, {len(listed[0])} characters survived"
        )
        assert len(listed[1]["deeper"]) < 50_000, (
            "a string inside a dict inside a list must be capped too"
        )

    def test_deep_nesting_terminates_and_still_caps(self) -> None:
        """A self-nested payload must neither exhaust the stack nor smuggle
        uncapped text past the depth bound.
        """
        hostile = "C" * 50_000
        payload: Any = hostile
        for _ in range(50):
            payload = {"next": payload}
        capped = ncbi_eutils_actions._cap_value(payload)
        rendered = json.dumps(capped)
        assert hostile not in rendered, (
            "an uncapped 50,000-character string survived a deeply nested payload"
        )

    def test_a_wide_nested_dict_is_bounded_by_key_count(self) -> None:
        wide = {f"k{n}": "v" for n in range(500)}
        capped = ncbi_eutils_actions._cap_value({"outer": wide})
        assert len(capped["outer"]) <= ncbi_eutils_actions._MAX_RECORD_FIELDS

    def test_a_long_nested_list_is_bounded_by_item_count(self) -> None:
        capped = ncbi_eutils_actions._cap_value({"outer": list(range(5000))})
        assert len(capped["outer"]) <= ncbi_eutils_actions._MAX_NESTED_ITEMS

    @pytest.mark.asyncio
    async def test_empty_result_yields_no_records(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch, [_json_response({"result": {"uids": []}})])
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gene", ids=["999999999"])
        )
        assert output.status == "empty"
        assert output.records == []

    @pytest.mark.asyncio
    async def test_error_body_under_http_200_is_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [_json_response({"result": {"ERROR": "Invalid uid 999999999999999"}})],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gene", ids=["999999999999999"])
        )
        assert output.status == "error"
        assert "Invalid uid" in output.error

    @pytest.mark.asyncio
    async def test_per_uid_error_entry_is_skipped_not_cited(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-13 (adversary finding 1, CRITICAL): a per-uid ESummary error
        object must NOT produce a record with a real host-pinned source_url
        and empty fields, which is a fabricated citation indistinguishable
        from a genuine one.

        ESummary answers a nonexistent uid with a per-uid error dict carrying
        only "uid" and "error" keys, inside a top-level "result" envelope
        with no ERROR key. The classifier returns ok (correctly: the envelope
        is valid), but the extractor must skip entries with no allowlisted
        fields.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["999999999"],
                            "999999999": {
                                "uid": "999999999",
                                "error": "cannot get document summary",
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gene", ids=["999999999"])
        )
        assert output.status == "empty", (
            f"a per-uid error entry with no allowlisted fields must produce "
            f"empty, not {output.status!r} with a fabricated citation"
        )
        assert output.records == []
        assert output.record_count == 0

    @pytest.mark.asyncio
    async def test_mixed_batch_keeps_real_record_drops_error_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-13 continued: a mixed batch of one real uid and one
        nonexistent one must keep the real record and drop the error entry.
        Both being ok with one having empty fields is indistinguishable
        downstream.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["672", "999999999"],
                            "672": {
                                "uid": "672",
                                "name": "BRCA1",
                                "description": "breast cancer 1",
                                "chromosome": "17",
                            },
                            "999999999": {
                                "uid": "999999999",
                                "error": "cannot get document summary",
                            },
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="gene", ids=["672", "999999999"])
        )
        assert output.status == "ok"
        assert output.record_count == 1, (
            f"mixed batch of 1 real + 1 error must yield 1 record, "
            f"got {output.record_count}: {[r.id for r in output.records]}"
        )
        assert output.records[0].id == "672"


# ===========================================================================
# _parse_medgen_clinical_features, direct unit tests (T-8.1-06)
# ===========================================================================


class TestParseMedgenClinicalFeatures:
    """Below the `summary()`-level tests above: `_parse_medgen_clinical_features`
    exercised directly against non-string and malformed input, which never
    reaches NCBI at all and so never needs a scripted transport."""

    def test_none_and_non_string_input_yields_empty_list(self) -> None:
        assert ncbi_eutils_actions._parse_medgen_clinical_features(None) == []
        assert ncbi_eutils_actions._parse_medgen_clinical_features(42) == []
        assert ncbi_eutils_actions._parse_medgen_clinical_features(["not", "a", "string"]) == []

    def test_blank_string_yields_empty_list(self) -> None:
        assert ncbi_eutils_actions._parse_medgen_clinical_features("") == []
        assert ncbi_eutils_actions._parse_medgen_clinical_features("   ") == []

    def test_malformed_xml_fails_closed_to_empty_list(self) -> None:
        assert ncbi_eutils_actions._parse_medgen_clinical_features("<ClinicalFeatures><unclosed") == []

    def test_a_feature_with_no_name_element_is_skipped(self) -> None:
        conceptmeta = (
            "<ClinicalFeatures>"
            '<ClinicalFeature SDUI="HP:0000001"><SemanticType>x</SemanticType></ClinicalFeature>'
            "<ClinicalFeature><Name>Real feature</Name></ClinicalFeature>"
            "</ClinicalFeatures>"
        )
        assert ncbi_eutils_actions._parse_medgen_clinical_features(conceptmeta) == [
            {"name": "Real feature"}
        ]

    def test_an_sdui_that_is_not_an_hpo_id_is_dropped(self) -> None:
        """`SDUI` is MedGen's generic source-descriptor-unique-id column and
        is not always an HPO term (it can be a MeSH id like `D008382`, seen
        live on MedGen's own `Names` block for Marfan syndrome). Only a
        genuine `HP:`-prefixed value is surfaced as `hpo_id`."""
        conceptmeta = (
            '<ClinicalFeatures><ClinicalFeature SDUI="D008382">'
            "<Name>Not an HPO term</Name></ClinicalFeature></ClinicalFeatures>"
        )
        assert ncbi_eutils_actions._parse_medgen_clinical_features(conceptmeta) == [
            {"name": "Not an HPO term"}
        ]

    def test_a_long_name_is_capped(self) -> None:
        long_name = "x" * 500
        conceptmeta = f"<ClinicalFeatures><ClinicalFeature><Name>{long_name}</Name></ClinicalFeature></ClinicalFeatures>"
        (feature,) = ncbi_eutils_actions._parse_medgen_clinical_features(conceptmeta)
        assert len(feature["name"]) <= ncbi_eutils_actions._MAX_CLINICAL_FEATURE_NAME_CHARS


# ===========================================================================
# fetch
# ===========================================================================


class TestFetch:
    @pytest.mark.asyncio
    async def test_happy_path_cites_record_host_not_fetch_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trap 2, the cross-tool citation trap, at the unit level."""
        _install(
            monkeypatch,
            [
                _xml_response(
                    "<PubmedArticleSet><PubmedArticle><MedlineCitation>"
                    "<PMID>21376230</PMID>"
                    "<Article><ArticleTitle>A real title</ArticleTitle>"
                    "<Abstract><AbstractText>Real abstract text.</AbstractText></Abstract>"
                    "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
                )
            ],
        )
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch", db="pubmed", ids=["21376230"], rettype="abstract", retmode="xml"
            )
        )
        assert output.status == "ok"
        assert output.record_count == 1
        record = output.records[0]
        assert record.id == "21376230"
        assert record.fields["title"] == "A real title"
        assert record.fields["abstract"] == "Real abstract text."
        assert record.source_url == "https://pubmed.ncbi.nlm.nih.gov/21376230/"
        assert "eutils.ncbi.nlm.nih.gov" not in record.source_url

    @pytest.mark.asyncio
    async def test_empty_article_set_fabricates_no_records(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trap 4: a blank PubmedArticleSet must yield zero records, never a blank one."""
        _install(monkeypatch, [_xml_response("<PubmedArticleSet></PubmedArticleSet>")])
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch",
                db="pubmed",
                ids=["999999999"],
                rettype="abstract",
                retmode="xml",
            )
        )
        assert output.status == "empty"
        assert output.records == []
        assert output.record_count == 0

    @pytest.mark.asyncio
    async def test_error_body_under_http_200_is_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [_json_response({"esearchresult": {"ERROR": "Invalid db name specified: bogus"}})],
        )
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch", db="gene", ids=["1"], rettype="docsum", retmode="json"
            )
        )
        assert output.status == "error"
        assert "Invalid db name" in output.error

    @pytest.mark.parametrize(
        "db", ["pubmed", "gene", "clinvar", "dbvar", "omim", "medgen", "gtr", "sra"]
    )
    @pytest.mark.asyncio
    async def test_schema_default_docsum_json_refuses_for_every_fetch_db(
        self, monkeypatch: pytest.MonkeyPatch, db: str
    ) -> None:
        """F-3.1-20 (reopened): the guard was scoped to `params.db == "pubmed"`
        only, while `FetchDb` names eight databases and all eight reproduce
        the identical defect on the SCHEMA DEFAULTS (`rettype="docsum"`,
        `retmode="json"`).

        Live-verified against real EFetch: `db=pubmed&id=21376230`,
        `db=gene&id=672` and `db=clinvar&id=12345` all return the same
        ESummary envelope. On the seven non-pubmed databases that body fell
        through to the generic extractor, producing ONE record holding the
        whole multi-record payload with `id=None`, `source_url=None`, and
        `record_count` misreported as 1, all at `status="ok"`. An uncited
        blob presented as a successful answer is exactly what the
        cite-or-refuse gate exists to stop.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "header": {"type": "esummary"},
                        "result": {
                            "uids": ["1", "2"],
                            "1": {"uid": "1", "title": "first record"},
                            "2": {"uid": "2", "title": "second record"},
                        },
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch", db=db, ids=["1", "2"], rettype="docsum", retmode="json"
            )
        )
        assert output.status == "error", (
            f"db={db} on schema defaults returned {output.status!r} with "
            f"{output.record_count} record(s); an ESummary-shaped multi-record "
            f"blob must never be reported as a successful fetch"
        )
        assert output.records == []
        assert output.record_count == 0
        # Actionable: name the alternative route, not just the failure.
        assert "summary action" in output.error
        assert db in output.error

    @pytest.mark.asyncio
    async def test_no_fabricated_uncited_blob_reaches_the_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-3.1-20 (reopened): pin the exact wrong-answer shape, so a future
        regression is caught by the symptom and not only by the status.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "header": {"type": "esummary"},
                        "result": {"uids": ["672"], "672": {"uid": "672", "name": "BRCA1"}},
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch", db="gene", ids=["672"], rettype="docsum", retmode="json"
            )
        )
        assert not any(
            record.id is None and record.source_url is None for record in output.records
        ), "a record with no id and no source_url is an uncitable fabrication"

    @pytest.mark.asyncio
    async def test_esummary_shaped_body_refused_even_off_the_default_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The shape arm of the guard, independent of the parameter arm: a
        server answering with a summary envelope for parameters that did not
        ask for one is still not per-record extractable.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {"result": {"uids": ["1"], "1": {"uid": "1", "title": "x"}}}
                )
            ],
        )
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch", db="gene", ids=["1"], rettype="full", retmode="json"
            )
        )
        assert output.status == "error"
        assert output.records == []

    @pytest.mark.asyncio
    async def test_article_with_no_pmid_is_skipped_not_emitted_blank(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [
                _xml_response(
                    "<PubmedArticleSet><PubmedArticle><MedlineCitation>"
                    "<Article><ArticleTitle>No PMID here</ArticleTitle></Article>"
                    "</MedlineCitation></PubmedArticle></PubmedArticleSet>"
                )
            ],
        )
        output = await ncbi_eutils_actions.fetch(
            NcbiEfetchFetchInput(
                action="fetch", db="pubmed", ids=["1"], rettype="abstract", retmode="xml"
            )
        )
        assert output.status == "empty"
        assert output.records == []


# ===========================================================================
# link
# ===========================================================================


class TestLink:
    @pytest.mark.asyncio
    async def test_happy_path_honors_explicit_target_db(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trap 3, at the unit level: only the explicitly requested target db's ids come back."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "gene",
                                "ids": ["7157"],
                                "linksetdbs": [
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed",
                                        "links": ["21376230", "11111111"],
                                    }
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="pubmed", ids=["7157"])
        )
        assert output.status == "ok"
        assert output.record_count == 2
        for record in output.records:
            assert record.db == "pubmed"
            assert record.source_url.startswith("https://pubmed.ncbi.nlm.nih.gov/")

    @pytest.mark.asyncio
    async def test_linksetdb_targeting_a_different_db_is_filtered_out(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The server sends back an extra linksetdb under a different dbto; it must not leak."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "gene",
                                "ids": ["7157"],
                                "linksetdbs": [
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed",
                                        "links": ["21376230"],
                                    },
                                    {
                                        "dbto": "pubmed_pubmed",
                                        "linkname": "pubmed_pubmed",
                                        "links": ["99999999"],
                                    },
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="pubmed", ids=["7157"])
        )
        ids = [record.id for record in output.records]
        assert ids == ["21376230"]
        assert "99999999" not in ids

    @pytest.mark.asyncio
    async def test_pubmed_to_pmc_keeps_only_the_direct_linkname(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UI fix set 11, trap 3's second half. The fixture below is a
        CONSTRUCTED response shape, not a live capture (round 2, N-05): on
        2026-09-14 the live ELink for PMID 31452104 returned only
        `pubmed_pmc_refs`, so the ids here are illustrative. What is live-
        verified is the two-linkname shape itself: `dbfrom=pubmed&db=pmc`
        can answer `pubmed_pmc` (the paper's own PMC copy) beside
        `pubmed_pmc_refs` (every PMC paper citing it), both under
        `dbto: "pmc"`. Only the direct one may contribute, and the record
        URL is the PMC article page.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "pubmed",
                                "ids": ["31452104"],
                                "linksetdbs": [
                                    {
                                        "dbto": "pmc",
                                        "linkname": "pubmed_pmc",
                                        "links": ["7184428"],
                                    },
                                    {
                                        "dbto": "pmc",
                                        "linkname": "pubmed_pmc_refs",
                                        "links": ["13547197", "13490894", "13465198"],
                                    },
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="pubmed", db="pmc", ids=["31452104"])
        )
        assert output.status == "ok"
        assert [record.id for record in output.records] == ["7184428"]
        assert output.records[0].db == "pmc"
        assert (
            output.records[0].source_url
            == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7184428/"
        )

    @pytest.mark.asyncio
    async def test_f03_gene_to_pubmed_keeps_every_matching_linkset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Review F-03 (2026-09-14): preferring `<dbfrom>_<db>` for every pair
        dropped `gene_pubmed_citedinomim`, 120 of 477 ids live for gene
        2645. The preference is an allowlist of verified pairs, today only
        (pubmed, pmc); gene to pubmed keeps all matching linksets.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "gene",
                                "ids": ["2645"],
                                "linksetdbs": [
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed",
                                        "links": ["21376230", "11111111"],
                                    },
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed_citedinomim",
                                        "links": ["22222222", "33333333"],
                                    },
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed_rif",
                                        "links": ["44444444"],
                                    },
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="pubmed", ids=["2645"])
        )
        assert sorted(record.id for record in output.records) == [
            "11111111",
            "21376230",
            "22222222",
            "33333333",
            "44444444",
        ]

    @pytest.mark.asyncio
    async def test_f03_pubmed_to_pubmed_keeps_citedin_beside_similar_articles(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "pubmed",
                                "ids": ["1"],
                                "linksetdbs": [
                                    {"dbto": "pubmed", "linkname": "pubmed_pubmed", "links": ["2"]},
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "pubmed_pubmed_citedin",
                                        "links": ["3"],
                                    },
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="pubmed", db="pubmed", ids=["1"])
        )
        assert sorted(record.id for record in output.records) == ["2", "3"]

    @pytest.mark.asyncio
    async def test_without_a_direct_linkname_every_matching_dbto_still_contributes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pair outside the allowlist keeps every matching linkset."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "gene",
                                "ids": ["7157"],
                                "linksetdbs": [
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed_rif",
                                        "links": ["21376230"],
                                    },
                                    {
                                        "dbto": "pubmed",
                                        "linkname": "gene_pubmed_pmc",
                                        "links": ["11111111"],
                                    },
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="pubmed", ids=["7157"])
        )
        assert sorted(record.id for record in output.records) == ["11111111", "21376230"]

    @pytest.mark.asyncio
    async def test_pmc_direct_linkname_with_no_links_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Null case: a paper with no PMC copy answers `empty`, never the
        citing-paper set in its place.
        """
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "linksets": [
                            {
                                "dbfrom": "pubmed",
                                "ids": ["1"],
                                "linksetdbs": [
                                    {"dbto": "pmc", "linkname": "pubmed_pmc", "links": []},
                                    {
                                        "dbto": "pmc",
                                        "linkname": "pubmed_pmc_refs",
                                        "links": ["13547197"],
                                    },
                                ],
                            }
                        ]
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="pubmed", db="pmc", ids=["1"])
        )
        assert output.status == "empty"
        assert output.records == []

    @pytest.mark.asyncio
    async def test_no_links_is_empty_not_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            [_json_response({"linksets": [{"dbfrom": "gene", "ids": ["1"], "linksetdbs": []}]})],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="pubmed", ids=["1"])
        )
        assert output.status == "empty"
        assert output.records == []

    @pytest.mark.asyncio
    async def test_error_body_under_http_200_is_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [_json_response({"linksets": {"ERROR": "Invalid db name specified: bogus"}})],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="bogus", ids=["1"])
        )
        assert output.status == "error"
        assert "Invalid db name" in output.error

    @pytest.mark.asyncio
    async def test_transport_error_maps_to_status_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            [ncbi_transport.TransportConnectionError("api.ncbi.nlm.nih.gov connection failed")],
        )
        output = await ncbi_eutils_actions.link(
            NcbiEfetchLinkInput(action="link", dbfrom="gene", db="pubmed", ids=["1"])
        )
        assert output.status == "error"
        assert "connection failed" in output.error
