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
    - NCBI_API_KEY's value never reaches a log record or an exception
      string, on both the success and the failure path.

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
from typing import Any

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
    """XXE / billion-laughs defense: reject on sight, never reaches ElementTree.fromstring."""
    hostile = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE PubmedArticleSet [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>"
        "<PubmedArticleSet>&xxe;</PubmedArticleSet>"
    )
    result = ncbi_transport.classify_eutils_response(content_type="text/xml", text=hostile)
    assert result.status == "error"


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

    def __enter__(self) -> "_DirectLogCapture":
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

    with _DirectLogCapture("system_03_search_agent.tools.ncbi_transport") as capture:
        with pytest.raises(ncbi_transport.TransportConnectionError) as exc_info:
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
    """Sanity check on the error text itself: names the family and a next step."""
    error = ncbi_transport.TransportRateLimitedError(
        "eutils rate pool queue is full (15 already waiting), retry after the queue drains",
        family="eutils",
        retry_after=0.33,
    )
    assert "eutils" in str(error)
    assert "retry" in str(error).lower()
