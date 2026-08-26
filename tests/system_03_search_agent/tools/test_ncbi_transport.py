"""Unit tests for `ncbi_transport`, the shared HTTP transport for `ncbi_efetch`.

No live network anywhere in this file. Every case mocks at the HTTP client
boundary (`_FakeClient` below returns canned `httpx.Response` objects or
raises canned `httpx` exceptions) or calls a classifier directly with
hand-built body text, per the ticket's instruction. Live-network coverage
of the real endpoints is `test_ncbi_efetch_premise.py`'s job, not this
file's.

What this file proves, mapped to T-3.1-02's acceptance:

    - All three E-utilities 200 outcomes (ok, empty via zero-hit search,
      empty via nonexistent-id XML, error via invalid db) classify
      correctly, and the near-miss pair (zero hits vs invalid db) lands in
      different buckets despite differing by one JSON key.
    - An unparseable or unrecognized 200 body fails closed to "error"
      (the allowlist requirement), never a silent "ok".
    - A DOCTYPE with no internal subset (the real PubMed EFetch shape)
      parses successfully; a DOCTYPE that declares an internal subset, or
      any body carrying an ENTITY declaration anywhere, is rejected. See
      the T-3.1-11 correction: a blanket reject on every DOCTYPE (this
      module's shipped-but-wrong first version) made real PubMed records
      unparseable, and this file's cases now pin the corrected boundary.
    - Datasets v2 and PubChem 400s classify by HTTP status, using each
      API's own error envelope for the message.
    - The two classifiers are provably independent: the E-utilities one
      ignores HTTP status entirely (same body, different status, same
      verdict), and the status-coded one ignores body shape entirely
      (error-shaped body, 2xx status, still "ok").
    - Retry fires exactly once on a transient failure (connection error,
      timeout, or 429/5xx), and never on a 400 or a 200-with-ERROR-body.
    - The per-call timeout is actually forwarded to the HTTP client.
    - The rate limiter fails fast, with an actionable message naming the
      family and a retry hint, when a call would exceed its queue depth
      or its own wait ceiling, rather than joining an unbounded wait.
      Both real limiter-produced messages are asserted to carry that
      retry hint, not only a hand-built stand-in string (F-3.1-32).
    - The wait ceiling is a budget for the WHOLE call, spent across both
      attempts, never re-issued in full to a retry (F-3.1-37). Driven by
      a fake clock so the doubling is observable rather than inferred.
    - A server-stated `Retry-After` on a 429 or 503 is parsed (numeric
      seconds and the rarer HTTP-date form), surfaced to the caller, and
      preferred over the fixed backoff constant for this module's own one
      retry, bounded so a huge value cannot park the call (F-3.1-19).
    - NCBI_API_KEY's value never reaches a log record or an exception
      string, on both the success and the failure path.
    - T-3.2-02: the `"variation"` rate-limit family (NCBI Variation
      Services, added for `ncbi_dbsnp`) is wired the same way as the three
      existing families: its default rate (1 req/s, the verified,
      undisputed figure per Section 6.3 line 1078), its `NCBI_VARIATION_RPS`
      env override, and its queue-depth cap all resolve correctly, and a
      call exceeding either the queue depth or the wait ceiling fails fast
      with `TransportRateLimitedError` rather than joining an unbounded
      wait, the same property already proven for `eutils` and `pubchem`
      above, now proven for `variation` too.

What this file deliberately does NOT cover, per `goal-contracts`'s
"a verify surface must state its own coverage":

    - Real network behavior of any endpoint. Every case stops at the HTTP
      client boundary; live coverage is `test_ncbi_efetch_premise.py`.
    - Concurrency beyond the single controlled interleaving in the
      queue-depth test. Multi-waiter fairness and ordering under the FIFO
      queue are not exercised.
    - Any action module's use of these results. Whether
      `ncbi_eutils_actions` actually reads `retry_after_for_response`
      into its 429 error text is that module's test's job, not this
      file's; this file proves only that the value is produced and
      reachable.

Depends on:
    - system_03_search_agent.tools.ncbi_transport (the module under test)
    - httpx, for constructing canned Response objects and transient
      exception types

Writes:
    - Nothing.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC
from typing import Any, Self

import httpx
import pytest

from system_03_search_agent.tools import ncbi_transport


async def _no_sleep(_seconds: float) -> None:
    """A sleep_fn stand-in that never actually waits, for fast tests."""
    return


class _FakeClient:
    """Mocks the HTTP client boundary: a scripted sequence of responses or exceptions."""

    def __init__(self, items: list[httpx.Response | Exception]) -> None:
        self._items = list(items)
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, timeout: float | None = None) -> httpx.Response:
        self.calls.append({"url": url, "timeout": timeout})
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch: pytest.MonkeyPatch):
    """Fresh rate-limiter state and clean NCBI_* env vars for every test."""
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    monkeypatch.delenv("NCBI_EUTILS_RPS", raising=False)
    monkeypatch.delenv("NCBI_DATASETS_RPS", raising=False)
    monkeypatch.delenv("NCBI_PUBCHEM_RPS", raising=False)
    monkeypatch.delenv("NCBI_VARIATION_RPS", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


# ===========================================================================
# classify_eutils_response: body-only, allowlist-based, fail-closed.
# ===========================================================================


def test_eutils_json_ok_search_returns_ok_with_parsed_body() -> None:
    result = ncbi_transport.classify_eutils_response(
        content_type="application/json",
        text='{"esearchresult": {"count": "1", "idlist": ["7157"]}}',
    )
    assert result.status == "ok"
    assert result.body["esearchresult"]["idlist"] == ["7157"]


def test_eutils_json_zero_hit_search_is_empty_not_error() -> None:
    """The near-miss twin of the invalid-db case below: one JSON key apart."""
    result = ncbi_transport.classify_eutils_response(
        content_type="application/json",
        text='{"esearchresult": {"count": "0", "idlist": []}}',
    )
    assert result.status == "empty"


def test_eutils_json_invalid_db_is_error_with_message_from_body() -> None:
    """The other half of the near-miss pair. One JSON key (ERROR) apart from empty."""
    result = ncbi_transport.classify_eutils_response(
        content_type="application/json",
        text=(
            '{"esearchresult": {"ERROR": "Invalid db name specified: notadatabase", '
            '"count": "0"}}'
        ),
    )
    assert result.status == "error"
    assert result.error_message is not None
    assert "Invalid db name specified" in result.error_message


def test_eutils_json_elink_body_level_error_is_error() -> None:
    """F-3.1-16 (adversary finding 4, CRITICAL): ELink puts ERROR at the TOP
    level of the body and makes linksets a LIST:
    {"linksets":[],"ERROR":"Invalid db name specified: notadatabase"}.
    Before this fix, the matched envelope was a list, so isinstance(envelope,
    dict) was False and the ERROR check was skipped entirely, giving status ok.
    """
    result = ncbi_transport.classify_eutils_response(
        content_type="application/json",
        text='{"linksets":[],"ERROR":"Invalid db name specified: notadatabase"}',
    )
    assert result.status == "error", (
        f"ELink body-level ERROR must classify as error, got {result.status!r}"
    )
    assert result.error_message is not None
    assert "Invalid db name specified" in result.error_message


def test_eutils_xml_nonexistent_id_is_empty_and_fabricates_nothing() -> None:
    result = ncbi_transport.classify_eutils_response(
        content_type="text/xml",
        text="<PubmedArticleSet></PubmedArticleSet>",
    )
    assert result.status == "empty"
    assert list(result.body) == []


def test_eutils_xml_with_articles_is_ok() -> None:
    result = ncbi_transport.classify_eutils_response(
        content_type="text/xml",
        text="<PubmedArticleSet><PubmedArticle><PMID>21376230</PMID></PubmedArticle></PubmedArticleSet>",
    )
    assert result.status == "ok"


def test_eutils_unrecognized_json_envelope_fails_closed_to_error() -> None:
    """The allowlist requirement: a 200 body matching no known-good shape is 'error'."""
    result = ncbi_transport.classify_eutils_response(
        content_type="application/json",
        text='{"somethingUnexpected": {"surprise": true}}',
    )
    assert result.status == "error"
    assert result.error_message is not None


def test_eutils_unparseable_json_fails_closed_to_error() -> None:
    result = ncbi_transport.classify_eutils_response(
        content_type="application/json",
        text="{not valid json at all",
    )
    assert result.status == "error"


def test_eutils_unparseable_xml_fails_closed_to_error() -> None:
    result = ncbi_transport.classify_eutils_response(
        content_type="text/xml",
        text="<PubmedArticleSet><unclosed>",
    )
    assert result.status == "error"


def test_eutils_disallowed_xml_root_fails_closed_to_error() -> None:
    result = ncbi_transport.classify_eutils_response(
        content_type="text/xml",
        text="<SomeUnrecognizedRoot></SomeUnrecognizedRoot>",
    )
    assert result.status == "error"


def test_eutils_neither_json_nor_xml_fails_closed_to_error() -> None:
    result = ncbi_transport.classify_eutils_response(content_type="text/plain", text="ok")
    assert result.status == "error"


def test_eutils_xml_doctype_is_rejected_before_parsing() -> None:
    """XXE / billion-laughs defense: reject on sight, never reaches ElementTree.fromstring.

    Rewritten under T-3.1-11: this payload is rejected because it declares
    an INTERNAL SUBSET containing an ENTITY, not merely because it has a
    DOCTYPE at all. A bare DOCTYPE with no internal subset (the real
    PubMed EFetch shape) is legitimate and must parse; see
    `test_eutils_xml_real_pubmed_doctype_with_no_internal_subset_parses`
    below for that boundary's positive case. The original version of this
    test predated that distinction and, paired with the module's earlier
    blanket-reject implementation, encoded the bug this correction fixes.
    """
    hostile = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE PubmedArticleSet [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>"
        "<PubmedArticleSet>&xxe;</PubmedArticleSet>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=hostile)
    assert result.status == "error"


def test_eutils_xml_real_pubmed_doctype_with_no_internal_subset_parses() -> None:
    """DEFECT 1 regression (T-3.1-11, live premise gate cases 4 and 8,
    2026-08-04/05). This is the EXACT DOCTYPE line every real PubMed EFetch
    response begins with. The module's first shipped version rejected any
    body containing '<!doctype' at all, which made it unable to parse a
    single real PubMed record: this pins the corrected boundary, a bare
    DOCTYPE (no internal `[...]` subset) is not itself the attack.
    """
    real_pubmed_body = (
        '<?xml version="1.0" ?>'
        '<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" '
        '"https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">'
        "<PubmedArticleSet><PubmedArticle><PMID>21376230</PMID></PubmedArticle></PubmedArticleSet>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=real_pubmed_body)
    assert result.status == "ok"
    assert result.body.tag == "PubmedArticleSet"


def test_eutils_xml_doctype_internal_subset_entity_is_rejected() -> None:
    """The direct boundary case: an internal subset that declares an ENTITY."""
    hostile = '<!DOCTYPE x [ <!ENTITY a "b"> ]><x>&a;</x>'
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=hostile)
    assert result.status == "error"


def test_eutils_xml_classic_xxe_file_read_payload_is_rejected() -> None:
    hostile = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<foo>&xxe;</foo>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=hostile)
    assert result.status == "error"


def test_eutils_xml_billion_laughs_payload_is_rejected() -> None:
    hostile = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE lolz ["
        '<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
        '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
        "]>"
        "<lolz>&lol3;</lolz>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=hostile)
    assert result.status == "error"


def test_eutils_xml_entity_declared_after_the_doctype_span_is_still_rejected() -> None:
    """An ENTITY smuggled into the body AFTER the DOCTYPE's closing `>`, not in
    the first bytes the DOCTYPE scan walks, must still be caught. The
    ENTITY check runs over the WHOLE body independently of the DOCTYPE
    scan, so it cannot be evaded by placing the declaration somewhere the
    DOCTYPE-span scan does not look.
    """
    hostile = (
        '<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" '
        '"https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">'
        "<PubmedArticleSet><PubmedArticle><PMID>1</PMID>"
        '<!ENTITY smuggled SYSTEM "file:///etc/passwd">'
        "</PubmedArticle></PubmedArticleSet>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=hostile)
    assert result.status == "error"


def test_eutils_xml_remote_dtd_reference_triggers_no_network_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real PubMed DOCTYPE names a remote DTD by URL. Parsing it must never
    cause an actual network fetch of that DTD: stdlib ElementTree does not
    resolve external entities or DTDs by default, and permitting a bare
    DOCTYPE here must not accidentally change that. Proven by making any
    socket connection attempt during classification raise.
    """
    import socket

    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no network connection may be attempted while parsing XML")

    monkeypatch.setattr(socket.socket, "connect", _forbidden_connect)
    monkeypatch.setattr(socket, "create_connection", _forbidden_connect)

    real_pubmed_body = (
        '<?xml version="1.0" ?>'
        '<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN" '
        '"https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">'
        "<PubmedArticleSet><PubmedArticle><PMID>21376230</PMID></PubmedArticle></PubmedArticleSet>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=real_pubmed_body)
    assert result.status == "ok"


def test_eutils_classifier_ignores_http_status_entirely() -> None:
    """Same body, two different real-world status codes, identical verdict.

    Proves classify_eutils_response cannot branch on status even by
    accident: it has no http_status parameter to branch on.
    """
    body_text = '{"esearchresult": {"count": "1", "idlist": ["7157"]}}'
    result_as_200 = ncbi_transport.classify_eutils_response(
        content_type="application/json", text=body_text
    )
    result_as_500 = ncbi_transport.classify_eutils_response(
        content_type="application/json", text=body_text
    )
    assert result_as_200.status == result_as_500.status == "ok"


# ===========================================================================
# classify_status_coded_response: HTTP status only, the opposite convention.
# ===========================================================================


def test_status_coded_2xx_is_ok_regardless_of_body() -> None:
    result = ncbi_transport.classify_status_coded_response(http_status=200, text='{"gene_id": "7157"}')
    assert result.status == "ok"


def test_status_coded_datasets_400_is_error_with_message() -> None:
    result = ncbi_transport.classify_status_coded_response(
        http_status=400,
        text='{"error": "INVALID_ARGUMENT", "code": 400, "message": "no gene found for symbol"}',
    )
    assert result.status == "error"
    assert result.error_message == "no gene found for symbol"


def test_status_coded_pubchem_400_fault_is_error_with_message() -> None:
    result = ncbi_transport.classify_status_coded_response(
        http_status=400,
        text='{"Fault": {"Code": "PUGREST.NotFound", "Message": "No CID found"}}',
    )
    assert result.status == "error"
    assert result.error_message == "No CID found"


def test_status_coded_500_with_unparseable_body_is_error_with_generic_message() -> None:
    result = ncbi_transport.classify_status_coded_response(http_status=500, text="<html>oops</html>")
    assert result.status == "error"
    assert "500" in result.error_message


def test_status_coded_classifier_uses_status_not_body() -> None:
    """An error-shaped body under a 2xx status is still 'ok': status decides, body doesn't."""
    error_shaped_body_under_200 = '{"Fault": {"Code": "irrelevant", "Message": "should be ignored"}}'
    result = ncbi_transport.classify_status_coded_response(
        http_status=200, text=error_shaped_body_under_200
    )
    assert result.status == "ok"


# ===========================================================================
# execute_get: retry exactly once on transient failure, never otherwise.
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_get_retries_once_on_connection_error_then_succeeds() -> None:
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([httpx.ConnectError("connection refused"), ok_response])

    response = await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        client=client,
        sleep_fn=_no_sleep,
    )

    assert response is ok_response
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_execute_get_raises_transport_timeout_after_exactly_two_attempts() -> None:
    client = _FakeClient(
        [httpx.ReadTimeout("slow"), httpx.ReadTimeout("still slow"), httpx.ReadTimeout("never called")]
    )

    with pytest.raises(ncbi_transport.TransportTimeoutError):
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "TP53"},
            family="eutils",
            client=client,
            sleep_fn=_no_sleep,
        )

    assert len(client.calls) == 2, "must retry exactly once, never zero, never more than once"


@pytest.mark.asyncio
async def test_execute_get_retries_once_on_transient_500_then_succeeds() -> None:
    transient = httpx.Response(500, text="upstream hiccup")
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([transient, ok_response])

    response = await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        client=client,
        sleep_fn=_no_sleep,
    )

    assert response is ok_response
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_execute_get_does_not_retry_on_400() -> None:
    """A 400 is a permanent failure: retrying would just re-fetch the same wrong answer."""
    bad_request = httpx.Response(400, json={"error": "bad", "code": 400, "message": "bad request"})
    client = _FakeClient([bad_request])

    response = await ncbi_transport.execute_get(
        "https://api.ncbi.nlm.nih.gov/datasets/v2/gene/symbol/NOTREAL/taxon/human",
        {},
        family="datasets",
        client=client,
        sleep_fn=_no_sleep,
    )

    assert response is bad_request
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_execute_get_does_not_retry_on_200_with_error_body() -> None:
    """The transport layer never inspects the body, so an ERROR-body 200 is not retried.

    This is what makes the near-miss pair safe: retrying an invalid-db
    response would just re-fetch the identical wrong answer.
    """
    error_body_200 = httpx.Response(
        200, json={"esearchresult": {"ERROR": "Invalid db name specified: notadatabase"}}
    )
    client = _FakeClient([error_body_200])

    response = await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "notadatabase", "term": "cancer"},
        family="eutils",
        client=client,
        sleep_fn=_no_sleep,
    )

    assert response is error_body_200
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_execute_get_forwards_timeout_to_the_http_client() -> None:
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([ok_response])

    await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        timeout_s=15.0,
        client=client,
        sleep_fn=_no_sleep,
    )

    assert client.calls[0]["timeout"] == 15.0


def test_execute_get_default_client_survives_across_different_event_loops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEFECT 2 regression (T-3.1-11, live premise gate cases 2, 5, 18,
    2026-08-05): a module-level `httpx.AsyncClient` singleton, first built on
    whichever event loop happened to be running at first use, raised
    `RuntimeError: Event loop is closed` intermittently when a LATER call
    reused it from a different, still-running event loop after the first
    loop had closed. That is exactly the shape pytest-asyncio's default
    per-test event loop produces, and a real risk anywhere a process
    legitimately runs more than one event loop over its life.

    Deliberately NOT `@pytest.mark.asyncio`: two independent
    `asyncio.new_event_loop()` calls, driven by hand, so this reproduces the
    bug at the same granularity the live gate found it (no `client=`
    override on either call, the real default-client code path both
    times), rather than relying on whatever loop-per-test policy
    pytest-asyncio happens to use.
    """
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})

    async def _fake_get(
        _self: httpx.AsyncClient, _url: str, timeout: float | None = None
    ) -> httpx.Response:
        return ok_response

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    async def _call() -> httpx.Response:
        return await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "TP53"},
            family="eutils",
            sleep_fn=_no_sleep,
        )

    loop_one = asyncio.new_event_loop()
    try:
        response_one = loop_one.run_until_complete(_call())
    finally:
        loop_one.close()

    loop_two = asyncio.new_event_loop()
    try:
        response_two = loop_two.run_until_complete(_call())
    finally:
        loop_two.close()

    assert response_one is ok_response
    assert response_two is ok_response


# ===========================================================================
# RateLimiter: bounded queue, fail-fast, never an unbounded wait.
# ===========================================================================


@pytest.mark.asyncio
async def test_rate_limiter_allows_a_call_within_its_ceiling() -> None:
    limiter = ncbi_transport.RateLimiter(requests_per_second=100.0, queue_depth=10, family="test")
    await limiter.acquire(5.0, sleep_fn=_no_sleep)  # must not raise


@pytest.mark.asyncio
async def test_rate_limiter_fails_fast_when_wait_exceeds_ceiling() -> None:
    limiter = ncbi_transport.RateLimiter(requests_per_second=0.01, queue_depth=30, family="eutils")
    clock = {"now": 0.0}

    def frozen_time() -> float:
        return clock["now"]

    # First call: a fresh limiter's next_available starts at 0.0, at or
    # before "now", so this always has wait == 0 and consumes the slot,
    # pushing next_available roughly 100s ahead of the frozen clock.
    await limiter.acquire(1000.0, time_fn=frozen_time, sleep_fn=_no_sleep)

    with pytest.raises(ncbi_transport.TransportRateLimitedError) as exc_info:
        await limiter.acquire(1.0, time_fn=frozen_time, sleep_fn=_no_sleep)

    assert exc_info.value.family == "eutils"
    assert exc_info.value.retry_after > 1.0


@pytest.mark.asyncio
async def test_rate_limiter_fails_fast_when_queue_depth_exceeded() -> None:
    limiter = ncbi_transport.RateLimiter(requests_per_second=1.0, queue_depth=1, family="pubchem")
    clock = {"now": 0.0}

    def frozen_time() -> float:
        return clock["now"]

    release = asyncio.Event()

    async def controlled_sleep(_seconds: float) -> None:
        await release.wait()

    # First call: wait == 0 on a fresh limiter, completes without ever
    # calling controlled_sleep, but leaves next_available 1s ahead of the
    # still-frozen clock.
    await limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)

    # Second call now computes wait == 1.0s (> 0), so it genuinely awaits
    # controlled_sleep and occupies the depth-1 queue until release fires.
    second = asyncio.ensure_future(
        limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)
    )
    await asyncio.sleep(0)  # yield so `second` reaches its sleep_fn await

    try:
        with pytest.raises(ncbi_transport.TransportRateLimitedError) as exc_info:
            await limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)
        assert exc_info.value.family == "pubchem"
        assert "queue is full" in str(exc_info.value)
    finally:
        release.set()
        await second


def test_get_rate_limiter_reads_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NCBI_EUTILS_RPS", "7.5")
    ncbi_transport.reset_rate_limiters_for_tests()

    limiter = ncbi_transport.get_rate_limiter("eutils")

    assert limiter.requests_per_second == pytest.approx(7.5)


def test_get_rate_limiter_default_is_the_conservative_floor() -> None:
    """Not 10, not 100: the conservative, independently-verified floor per the unresolved conflict."""
    limiter = ncbi_transport.get_rate_limiter("eutils")
    assert limiter.requests_per_second == pytest.approx(3.0)


# ===========================================================================
# Secrets: NCBI_API_KEY's value never reaches a log record or an exception.
# ===========================================================================


class _DirectLogCapture:
    """Capture records straight off a named logger, bypassing `caplog`.

    Why this exists rather than `caplog`. Both log-based tests in this phase
    passed in isolation and failed in the full suite: `caplog.text` came back
    empty once `tests/system_03_search_agent/harness` had run first. The
    assertion that broke was the POSITIVE control ("a line was logged at
    all"), never the security assertion, so the property under test held the
    whole time and the test was simply going blind. A security test that can
    silently stop observing is worse than one that fails loudly, which is why
    this attaches its own handler to the module's own logger and restores the
    previous state afterwards. It depends on no global logging configuration
    and no other test module's behavior.
    """

    def __init__(self, logger_name: str, level: int = logging.DEBUG) -> None:
        self._logger = logging.getLogger(logger_name)
        self._level = level
        self.records: list[logging.LogRecord] = []

    def __enter__(self) -> Self:
        outer = self

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                outer.records.append(record)

        self._handler = _Handler()
        self._handler.setLevel(self._level)
        self._prev_level = self._logger.level
        self._prev_disable = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        self._logger.setLevel(self._level)
        self._logger.addHandler(self._handler)
        return self

    def __exit__(self, *exc: object) -> None:
        self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._prev_level)
        logging.disable(self._prev_disable)

    @property
    def text(self) -> str:
        return "\n".join(r.getMessage() for r in self.records)


@pytest.mark.asyncio
async def test_api_key_value_never_appears_in_log_on_success(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "SUPER-SECRET-NCBI-KEY-24601"
    monkeypatch.setenv("NCBI_API_KEY", secret)
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([ok_response])

    with _DirectLogCapture("system_03_search_agent.tools.ncbi_transport") as capture:
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "TP53"},
            family="eutils",
            include_api_key=True,
            client=client,
            sleep_fn=_no_sleep,
        )

    assert secret not in capture.text
    # The positive control. Without it this test passes on a code path that
    # logs nothing at all, which is exactly how it failed in the full suite.
    assert "NCBI_API_KEY present" in capture.text
    # The load-bearing assertion: no LOG RECORD carries the URL-with-key,
    # even though the request URL itself legitimately does.
    assert not any(secret in record.getMessage() for record in capture.records)


@pytest.mark.asyncio
async def test_api_key_value_never_appears_in_log_or_exception_on_failure(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "SUPER-SECRET-NCBI-KEY-24601"
    monkeypatch.setenv("NCBI_API_KEY", secret)
    client = _FakeClient([httpx.ConnectError("refused"), httpx.ConnectError("refused again")])

    with (
        _DirectLogCapture("system_03_search_agent.tools.ncbi_transport") as capture,
        pytest.raises(ncbi_transport.TransportConnectionError) as exc_info,
    ):
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "TP53"},
            family="eutils",
            include_api_key=True,
            client=client,
            sleep_fn=_no_sleep,
        )

    assert secret not in str(exc_info.value)
    # Positive control, same reasoning as the success-path test above.
    assert capture.records, "the retry path must log something to be checkable"
    assert not any(secret in record.getMessage() for record in capture.records)


def test_rate_limited_error_message_never_needs_a_secret_to_be_actionable() -> None:
    """Sanity check on the error text itself: names the family and a next step.

    F-3.1-32: the `retry` assertion below was deleted during an earlier fix
    round with no replacement, while this file's own docstring kept
    claiming it checked "an actionable message naming the family and a
    retry hint". It is restored here, and
    `test_rate_limiter_real_failure_messages_always_carry_a_retry_hint`
    below extends the same check to the messages the limiter ACTUALLY
    produces, since a hand-built string can drift from the real one
    without either test noticing.
    """
    error = ncbi_transport.TransportRateLimitedError(
        "eutils rate pool queue is full (15 already waiting), retry after the queue drains",
        family="eutils",
        retry_after=0.33,
    )
    assert "eutils" in str(error)
    assert "retry" in str(error).lower()


@pytest.mark.asyncio
async def test_rate_limiter_real_failure_messages_always_carry_a_retry_hint() -> None:
    """Both real fail-fast paths, not a hand-built stand-in (F-3.1-32).

    `.claude/rules/tool-call-budgets.md`: a rate-limited error is an
    instruction to the next agent step, so every message the limiter can
    emit must name the saturated family, carry a numeric `retry_after`,
    and say what to do next.
    """
    clock = {"now": 0.0}

    def frozen_time() -> float:
        return clock["now"]

    # Path 1: the wait ceiling is exceeded.
    ceiling_limiter = ncbi_transport.RateLimiter(
        requests_per_second=0.01, queue_depth=30, family="eutils"
    )
    await ceiling_limiter.acquire(1000.0, time_fn=frozen_time, sleep_fn=_no_sleep)
    with pytest.raises(ncbi_transport.TransportRateLimitedError) as ceiling_exc:
        await ceiling_limiter.acquire(1.0, time_fn=frozen_time, sleep_fn=_no_sleep)

    assert "eutils" in str(ceiling_exc.value)
    assert "retry" in str(ceiling_exc.value).lower()
    assert ceiling_exc.value.retry_after > 0

    # Path 2: the bounded queue is full.
    queue_limiter = ncbi_transport.RateLimiter(
        requests_per_second=1.0, queue_depth=1, family="pubchem"
    )
    release = asyncio.Event()

    async def controlled_sleep(_seconds: float) -> None:
        await release.wait()

    await queue_limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)
    occupant = asyncio.ensure_future(
        queue_limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)
    )
    await asyncio.sleep(0)
    try:
        with pytest.raises(ncbi_transport.TransportRateLimitedError) as queue_exc:
            await queue_limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)
        assert "pubchem" in str(queue_exc.value)
        assert "retry" in str(queue_exc.value).lower()
        assert queue_exc.value.retry_after > 0
    finally:
        release.set()
        await occupant


# ===========================================================================
# F-3.1-18: query-string parameter injection (CRITICAL, security)
# ===========================================================================


def test_build_query_string_encodes_ampersand_and_equals() -> None:
    """F-3.1-18: `safe=""` must encode `&` and `=` so caller-supplied
    values cannot inject arbitrary parameters into the URL.
    """
    from system_03_search_agent.tools.ncbi_transport import _build_query_string

    result = _build_query_string(
        {"db": "gene", "term": "BRCA1[sym] AND human[orgn]&retstart=500", "retmax": "10"}
    )
    # The injected &retstart=500 must NOT appear as a literal parameter separator
    assert "&retstart=500" not in result, (
        f"injected parameter must be encoded, got {result!r}"
    )
    # The injected & must be percent-encoded
    assert "%26retstart" in result, (
        f"the & in the term value must be percent-encoded as %26, got {result!r}"
    )


# ===========================================================================
# F-3.1-37: the wait ceiling is one budget for the whole call (MAJOR).
# ===========================================================================


def _make_fake_clock() -> tuple[dict[str, float], Any, Any]:
    """A clock the test drives by hand, plus a sleep that advances it.

    Real elapsed time is what draws down a wait budget in production, so a
    test that asserts anything about that budget has to be able to see time
    pass. `_no_sleep` cannot: it returns instantly and leaves the clock
    where it was, which is exactly why a doubled budget was invisible to
    every existing test in this file.
    """
    clock = {"now": 0.0}

    def fake_time() -> float:
        return clock["now"]

    async def advancing_sleep(seconds: float) -> None:
        clock["now"] += seconds

    return clock, fake_time, advancing_sleep


@pytest.mark.asyncio
async def test_execute_get_wait_budget_is_shared_across_attempts_not_reissued_per_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.1-37 reproduction, with a fake clock.

    F-3.1-22's fix moved `limiter.acquire` inside the retry loop, which was
    correct (a retry must not escape the pool) but handed each attempt its
    own full copy of `wait_ceiling_s`. A call declaring a 1.5s wait budget
    could then wait 1.0s before its first request and another 1.0s before
    its retry: 2.0s total against a 1.5s ceiling.
    `.claude/rules/tool-call-budgets.md` ties that ceiling to the calling
    query's remaining latency budget, so a budget that silently doubles
    under retry is not a budget.

    The scenario: the eutils pool is paced at 1 request/second and already
    has a call scheduled at t=1.0, so it is saturated. The call under test
    declares a 1.5s wait budget and gets a 503 on its first attempt.

        attempt 0: waits 1.0s for the pool (inside the 1.5s budget), gets
                   a 503, backs off 0s.
        attempt 1: only 0.5s of budget is left, but the pool's next free
                   slot is 1.0s away, so it must fail fast.

    Before the fix, attempt 1 received a fresh 1.5s ceiling, waited another
    full 1.0s, and returned a 200 after 2.0s of waiting. This test therefore
    fails loudly (DID NOT RAISE, and 2 client calls) against the old code.
    """
    monkeypatch.setenv("NCBI_EUTILS_RPS", "1.0")
    ncbi_transport.reset_rate_limiters_for_tests()

    clock, fake_time, advancing_sleep = _make_fake_clock()

    limiter = ncbi_transport.get_rate_limiter("eutils")
    # Saturate the pool: this consumes the t=0 slot with no wait of its own
    # and pushes the next free slot to t=1.0.
    await limiter.acquire(10.0, time_fn=fake_time, sleep_fn=advancing_sleep)
    assert clock["now"] == 0.0, "priming the pool must not itself consume clock time"

    transient = httpx.Response(503, text="overloaded")
    would_be_second = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([transient, would_be_second])

    with pytest.raises(ncbi_transport.TransportRateLimitedError) as exc_info:
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "TP53"},
            family="eutils",
            wait_ceiling_s=1.5,
            backoff_s=0.0,
            client=client,
            sleep_fn=advancing_sleep,
            time_fn=fake_time,
        )

    assert exc_info.value.family == "eutils"
    assert len(client.calls) == 1, (
        "the retry must never be issued once the call's shared wait budget is spent"
    )
    assert clock["now"] <= 1.5, (
        f"total wait must stay inside the declared 1.5s ceiling, spent {clock['now']}s"
    )


@pytest.mark.asyncio
async def test_execute_get_wait_budget_is_not_charged_for_request_or_backoff_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-review round 1, adversarial pass (ADV-FIX2-6): F-3.1-37's own
    fix shared the wait budget by WALL-CLOCK DEADLINE, which charges the
    ceiling for the HTTP request's own elapsed time and the backoff
    sleep, not only time spent actually waiting for the pool. With the
    common case `wait_ceiling_s == timeout_s`, a first attempt that
    times out has, by construction, already consumed the entire
    deadline before the retry's own acquisition ever runs, so the retry
    always got ~0.0s of pool-wait budget in exactly the case a retry
    exists for: recovering from a timeout.

    Scenario: a 15s timeout on attempt 0, wait_ceiling_s of only 1.0s
    (deliberately far smaller than timeout_s, the shape this bug hit
    hardest), a 1s backoff, then a pool that genuinely needs a 0.5s wait
    for attempt 1. The declared 1.0s ceiling comfortably covers a 0.5s
    pool wait; only wall-clock-deadline double-charging could make this
    fail. Before this fix: DID NOT RAISE was the wrong outcome to hope
    for, since the bug's failure mode is the OPPOSITE of the F-3.1-22
    scenario above, a retry that fails fast when it should not have to.
    """
    clock, fake_time, advancing_sleep = _make_fake_clock()
    monkeypatch.setenv("NCBI_EUTILS_RPS", "1.0")
    ncbi_transport.reset_rate_limiters_for_tests()
    limiter = ncbi_transport.get_rate_limiter("eutils")

    would_be_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    calls: list[float] = []

    async def _get_advancing_time_then_saturating_pool(
        url: str, timeout: float | None = None
    ) -> httpx.Response:
        calls.append(clock["now"])
        if len(calls) == 1:
            # The request itself takes the full 15s timeout to fail, the
            # same wall-clock cost a real ConnectTimeout has.
            clock["now"] += 15.0
            # While this call was blocked, another caller reserved the
            # pool's next slot for 0.5s after the retry actually runs
            # (the 1.0s backoff below still has to happen first), so
            # attempt 1's own acquisition has a real, non-zero wait to
            # do, not one that has already silently elapsed by the time
            # it runs.
            limiter._next_available = clock["now"] + 1.0 + 0.5
            raise httpx.ConnectTimeout("simulated timeout")
        return would_be_response

    class _FunctionClient:
        def __init__(self, get_fn: Any) -> None:
            self._get_fn = get_fn

        async def get(self, url: str, timeout: float | None = None) -> httpx.Response:
            return await self._get_fn(url, timeout=timeout)

    output = await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        wait_ceiling_s=1.0,
        timeout_s=15.0,
        backoff_s=1.0,
        client=_FunctionClient(_get_advancing_time_then_saturating_pool),
        sleep_fn=advancing_sleep,
        time_fn=fake_time,
    )

    assert output is would_be_response, (
        "the retry must succeed: its own 1.0s wait ceiling easily covers "
        "the 0.5s the pool genuinely needs, and must not be starved by "
        "the unrelated 15s the failed first request and its backoff cost"
    )
    assert len(calls) == 2, "the retry must actually be attempted, not failed fast"


@pytest.mark.asyncio
async def test_execute_get_retry_blocked_by_budget_keeps_the_first_failure_as_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failing fast on the retry must not erase why the retry was needed.

    The first attempt timed out. The retry could not be scheduled inside
    what was left of the wait budget. The raised TransportRateLimitedError
    is correct and actionable, and the underlying ReadTimeout is chained
    onto it rather than replaced by it, so "it timed out, then could not be
    retried in budget" is still recoverable from the raised error.
    """
    monkeypatch.setenv("NCBI_EUTILS_RPS", "1.0")
    ncbi_transport.reset_rate_limiters_for_tests()

    _clock, fake_time, advancing_sleep = _make_fake_clock()

    limiter = ncbi_transport.get_rate_limiter("eutils")
    await limiter.acquire(10.0, time_fn=fake_time, sleep_fn=advancing_sleep)

    client = _FakeClient([httpx.ReadTimeout("slow"), httpx.ReadTimeout("never reached")])

    with pytest.raises(ncbi_transport.TransportRateLimitedError) as exc_info:
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "TP53"},
            family="eutils",
            wait_ceiling_s=1.5,
            backoff_s=0.0,
            client=client,
            sleep_fn=advancing_sleep,
            time_fn=fake_time,
        )

    assert isinstance(exc_info.value.__cause__, httpx.ReadTimeout)
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_execute_get_still_retries_when_the_shared_budget_covers_both_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other arm: a shared budget must not break a retry that genuinely fits.

    Same saturated pool, same two 1.0s waits, but a 2.5s budget this time.
    A fix that simply refused every second acquisition would pass the test
    above and destroy the retry path, so this pins the admit side of the
    boundary the way the guardrail phase's premise gate pins its own.
    """
    monkeypatch.setenv("NCBI_EUTILS_RPS", "1.0")
    ncbi_transport.reset_rate_limiters_for_tests()

    clock, fake_time, advancing_sleep = _make_fake_clock()

    limiter = ncbi_transport.get_rate_limiter("eutils")
    await limiter.acquire(10.0, time_fn=fake_time, sleep_fn=advancing_sleep)

    transient = httpx.Response(503, text="overloaded")
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([transient, ok_response])

    response = await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        wait_ceiling_s=2.5,
        backoff_s=0.0,
        client=client,
        sleep_fn=advancing_sleep,
        time_fn=fake_time,
    )

    assert response is ok_response
    assert len(client.calls) == 2
    assert clock["now"] <= 2.5


# ===========================================================================
# F-3.1-19 (reopened): a numeric retry_after from a real server 429/503.
# ===========================================================================


def test_parse_retry_after_reads_numeric_seconds() -> None:
    assert ncbi_transport.parse_retry_after({"Retry-After": "30"}) == 30.0


def test_parse_retry_after_header_name_is_case_insensitive() -> None:
    assert ncbi_transport.parse_retry_after({"retry-after": "12"}) == 12.0
    assert ncbi_transport.parse_retry_after({"RETRY-AFTER": "12"}) == 12.0


def test_parse_retry_after_absent_header_returns_the_default() -> None:
    assert ncbi_transport.parse_retry_after({}) is None
    assert ncbi_transport.parse_retry_after({}, default=1.0) == 1.0


def test_parse_retry_after_unparseable_value_returns_the_default() -> None:
    assert ncbi_transport.parse_retry_after({"Retry-After": "soon"}, default=2.0) == 2.0
    assert ncbi_transport.parse_retry_after({"Retry-After": "   "}, default=2.0) == 2.0


def test_parse_retry_after_rejects_nan_and_infinity() -> None:
    """float() accepts "nan" and "inf"; either would poison every downstream compare."""
    assert ncbi_transport.parse_retry_after({"Retry-After": "nan"}, default=1.0) == 1.0
    assert ncbi_transport.parse_retry_after({"Retry-After": "inf"}, default=1.0) == 1.0
    assert ncbi_transport.parse_retry_after({"Retry-After": "-inf"}, default=1.0) == 1.0


def test_parse_retry_after_negative_seconds_clamp_to_zero() -> None:
    assert ncbi_transport.parse_retry_after({"Retry-After": "-5"}) == 0.0


def test_parse_retry_after_accepts_the_http_date_form() -> None:
    """The rarer absolute form, converted to a delay relative to now."""
    import email.utils
    from datetime import datetime, timedelta

    when = datetime.now(UTC) + timedelta(seconds=45)
    parsed = ncbi_transport.parse_retry_after({"Retry-After": email.utils.format_datetime(when)})

    assert parsed is not None
    assert parsed == pytest.approx(45.0, abs=5.0)


def test_parse_retry_after_past_http_date_clamps_to_zero() -> None:
    import email.utils
    from datetime import datetime, timedelta

    when = datetime.now(UTC) - timedelta(seconds=600)
    parsed = ncbi_transport.parse_retry_after({"Retry-After": email.utils.format_datetime(when)})

    assert parsed == 0.0


def test_retry_after_for_response_surfaces_the_server_value() -> None:
    response = httpx.Response(429, text="slow down", headers={"Retry-After": "30"})
    assert ncbi_transport.retry_after_for_response(response) == 30.0


def test_retry_after_for_response_falls_back_to_the_backoff_budget() -> None:
    response = httpx.Response(429, text="slow down")
    assert ncbi_transport.retry_after_for_response(response) == ncbi_transport.DEFAULT_BACKOFF_S


def test_status_coded_429_carries_the_server_retry_after() -> None:
    result = ncbi_transport.classify_status_coded_response(
        http_status=429,
        text='{"message": "too many requests"}',
        headers={"Retry-After": "30"},
    )
    assert result.status == "error"
    assert result.retry_after == 30.0


def test_status_coded_503_carries_the_server_retry_after() -> None:
    result = ncbi_transport.classify_status_coded_response(
        http_status=503,
        text='{"message": "service unavailable"}',
        headers={"Retry-After": "7"},
    )
    assert result.retry_after == 7.0


def test_status_coded_non_rate_limit_status_never_carries_a_retry_after() -> None:
    """A 400 with a stray Retry-After is not a rate limit; do not tell the agent to wait."""
    result = ncbi_transport.classify_status_coded_response(
        http_status=400,
        text='{"message": "no gene found for symbol"}',
        headers={"Retry-After": "30"},
    )
    assert result.status == "error"
    assert result.retry_after is None


def test_status_coded_headers_stay_optional_and_default_to_no_retry_after() -> None:
    result = ncbi_transport.classify_status_coded_response(
        http_status=429, text='{"message": "too many requests"}'
    )
    assert result.status == "error"
    assert result.retry_after is None


@pytest.mark.asyncio
async def test_execute_get_429_leaves_a_numeric_retry_after_reachable_by_the_caller() -> None:
    """F-3.1-19 reproduction: a stubbed 429 carrying `Retry-After: 30`.

    Before this fix, no numeric `retry_after` was produced from a real
    server 429 anywhere in this module: `TransportRateLimitedError` only
    ever carried this module's OWN client-side throttle estimate, and a
    429 the server actually sent reached the caller as a bare
    `httpx.Response` with nothing read off it.

    Two things are asserted, matching the two halves of the interface:

        the caller can turn the returned response into the number 30
        (this is what `ncbi_eutils_actions._get_or_error` wires into its
        429 error text), and

        this module's own one retry waited on the server's value rather
        than its fixed 1.0s backoff constant, capped at
        `_MAX_BACKOFF_FROM_RETRY_AFTER_S` so a large header value cannot
        park the call past its own timeout budget.
    """
    rate_limited = httpx.Response(429, text="slow down", headers={"Retry-After": "30"})
    client = _FakeClient([rate_limited, rate_limited])
    slept: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        slept.append(seconds)

    response = await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        client=client,
        sleep_fn=recording_sleep,
    )

    assert response.status_code == 429
    assert len(client.calls) == 2
    assert ncbi_transport.retry_after_for_response(response) == 30.0
    assert slept[0] == pytest.approx(ncbi_transport._MAX_BACKOFF_FROM_RETRY_AFTER_S)


@pytest.mark.asyncio
async def test_execute_get_honors_a_small_server_retry_after_verbatim() -> None:
    """Under the cap, the server's number is used exactly, not the fixed backoff."""
    rate_limited = httpx.Response(503, text="busy", headers={"Retry-After": "3"})
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([rate_limited, ok_response])
    slept: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        slept.append(seconds)

    await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        backoff_s=1.0,
        client=client,
        sleep_fn=recording_sleep,
    )

    assert slept[0] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_execute_get_never_retries_sooner_than_its_own_backoff() -> None:
    """A server asking for 0s must not shorten this module's own pacing floor."""
    rate_limited = httpx.Response(503, text="busy", headers={"Retry-After": "0"})
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([rate_limited, ok_response])
    slept: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        slept.append(seconds)

    await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        backoff_s=1.0,
        client=client,
        sleep_fn=recording_sleep,
    )

    assert slept[0] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_execute_get_uses_the_fixed_backoff_when_no_retry_after_is_sent() -> None:
    """The unchanged path: no header, no behavior change from before F-3.1-19."""
    transient = httpx.Response(500, text="upstream hiccup")
    ok_response = httpx.Response(200, json={"esearchresult": {"count": "1"}})
    client = _FakeClient([transient, ok_response])
    slept: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        slept.append(seconds)

    await ncbi_transport.execute_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "gene", "term": "TP53"},
        family="eutils",
        backoff_s=1.0,
        client=client,
        sleep_fn=recording_sleep,
    )

    assert slept[0] == pytest.approx(1.0)


# ===========================================================================
# T-3.2-02: the "variation" rate-limit family (NCBI Variation Services).
#
# These mirror the existing eutils/pubchem coverage above (rate-limiter
# construction, env override, queue-depth cap, fail-fast-not-unbounded-wait)
# for the new family, per `.claude/rules/tool-call-budgets.md`'s explicit
# requirement that every rate-limited API family carry this proof, not only
# the ones that existed before this ticket.
# ===========================================================================


def test_variation_is_a_registered_rate_limit_family() -> None:
    """RATE_LIMIT_FAMILIES and RateLimitFamily both name "variation" now."""
    assert "variation" in ncbi_transport.RATE_LIMIT_FAMILIES


def test_get_rate_limiter_variation_default_is_the_verified_floor() -> None:
    """1 req/s, not the eutils/datasets/pubchem defaults, and not disputed.

    Unlike eutils' 3-vs-10-vs-100 conflict, Section 6.3 line 1078 and
    Section 21.1 both state this figure plainly with no competing number.
    """
    limiter = ncbi_transport.get_rate_limiter("variation")
    assert limiter.requests_per_second == pytest.approx(1.0)


def test_get_rate_limiter_variation_reads_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NCBI_VARIATION_RPS", "2.5")
    ncbi_transport.reset_rate_limiters_for_tests()

    limiter = ncbi_transport.get_rate_limiter("variation")

    assert limiter.requests_per_second == pytest.approx(2.5)


def test_variation_queue_depth_is_smaller_than_eutils_and_datasets() -> None:
    """A small multiple of ~1 req/s must be a shallower queue than the
    other families' pools, per the ticket's explicit instruction and the
    reasoning recorded in `ncbi_transport._FAMILY_CONFIGS`."""
    eutils_depth = ncbi_transport.get_rate_limiter("eutils")._queue_depth
    datasets_depth = ncbi_transport.get_rate_limiter("datasets")._queue_depth
    variation_depth = ncbi_transport.get_rate_limiter("variation")._queue_depth

    assert variation_depth < eutils_depth
    assert variation_depth < datasets_depth
    assert variation_depth > 0


@pytest.mark.asyncio
async def test_rate_limiter_variation_fails_fast_when_wait_exceeds_ceiling() -> None:
    """Same property already proven for eutils above (line ~583), now for
    variation: a call whose computed wait would exceed its own ceiling
    fails fast with TransportRateLimitedError rather than sleeping past it.
    """
    limiter = ncbi_transport.RateLimiter(requests_per_second=0.01, queue_depth=5, family="variation")
    clock = {"now": 0.0}

    def frozen_time() -> float:
        return clock["now"]

    # First call occupies the slot and pushes next_available ~100s ahead.
    await limiter.acquire(1000.0, time_fn=frozen_time, sleep_fn=_no_sleep)

    with pytest.raises(ncbi_transport.TransportRateLimitedError) as exc_info:
        await limiter.acquire(1.0, time_fn=frozen_time, sleep_fn=_no_sleep)

    assert exc_info.value.family == "variation"
    assert exc_info.value.retry_after > 1.0


@pytest.mark.asyncio
async def test_rate_limiter_variation_fails_fast_when_queue_depth_exceeded() -> None:
    """Same property already proven for pubchem above (line ~603), now for
    variation, at variation's own (smaller) configured queue depth: once
    the depth-N queue is full, the next call raises
    TransportRateLimitedError instead of joining an unbounded wait, per
    `.claude/rules/tool-call-budgets.md`.
    """
    queue_depth = ncbi_transport.get_rate_limiter("variation")._queue_depth
    limiter = ncbi_transport.RateLimiter(
        requests_per_second=1.0, queue_depth=queue_depth, family="variation"
    )
    clock = {"now": 0.0}

    def frozen_time() -> float:
        return clock["now"]

    release = asyncio.Event()

    async def controlled_sleep(_seconds: float) -> None:
        await release.wait()

    # First call: wait == 0 on a fresh limiter, completes immediately, but
    # leaves next_available 1s ahead of the still-frozen clock so every
    # later call in this test genuinely waits.
    await limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)

    # Fill the queue to exactly its depth with calls that block on
    # controlled_sleep until released.
    pending = [
        asyncio.ensure_future(limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep))
        for _ in range(queue_depth)
    ]
    for _ in range(queue_depth):
        await asyncio.sleep(0)  # yield so each pending call reaches its sleep_fn await

    try:
        with pytest.raises(ncbi_transport.TransportRateLimitedError) as exc_info:
            await limiter.acquire(10.0, time_fn=frozen_time, sleep_fn=controlled_sleep)
        assert exc_info.value.family == "variation"
        assert "queue is full" in str(exc_info.value)
    finally:
        release.set()
        await asyncio.gather(*pending)


def test_variation_family_does_not_alter_existing_families(monkeypatch: pytest.MonkeyPatch) -> None:
    """Additive-only per the ticket: eutils/datasets/pubchem defaults and
    queue depths are exactly what they were before this family was added.
    """
    assert ncbi_transport.get_rate_limiter("eutils").requests_per_second == pytest.approx(3.0)
    assert ncbi_transport.get_rate_limiter("datasets").requests_per_second == pytest.approx(5.0)
    assert ncbi_transport.get_rate_limiter("pubchem").requests_per_second == pytest.approx(5.0)
    assert ncbi_transport.get_rate_limiter("eutils")._queue_depth == 15
    assert ncbi_transport.get_rate_limiter("datasets")._queue_depth == 25
    assert ncbi_transport.get_rate_limiter("pubchem")._queue_depth == 25
