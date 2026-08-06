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
        "dbinfo": {
            "dbname": "gene",
            "fieldlist": [
                {"name": "SYM", "fullname": "Symbol"},
                {"name": "ORGN", "fullname": "Organism"},
                {"name": "GENE", "fullname": "Gene Name"},
            ],
        }
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
        assert scripted.calls[1]["params"]["term"] == "(TP53)[sym]"

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

    @pytest.mark.asyncio
    async def test_unverified_db_falls_back_to_generic_capped_passthrough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bioproject has no verified field list (the spec-gap note): generic fallback."""
        _install(
            monkeypatch,
            [
                _json_response(
                    {
                        "result": {
                            "uids": ["999"],
                            "999": {"uid": "999", "some_field": "some_value"},
                        }
                    }
                )
            ],
        )
        output = await ncbi_eutils_actions.summary(
            NcbiEfetchSummaryInput(action="summary", db="bioproject", ids=["999"])
        )
        assert output.status == "ok"
        assert output.records[0].fields == {"some_field": "some_value"}

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
