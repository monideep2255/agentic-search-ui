"""Phase 4.2 premise gate: `tracker/phase_4.2.md`.

The done-when this file pins (the phase's own "Phase premise" section): a
user with an account runs `s3 ask "<question>"` against a running server
and gets the same cited answer the web UI gets, streamed to stdout as it
is produced, with a references block after it naming `source` and
`source_url` per marker, and exit code 0. The answer body carries the
trust prefix (`[answer]`, `[flag]`, `[ask]`, `[refuse]`) and the inline
`[n]` markers match the `marker_ids` the server actually sent, never a
client-side renumbering.

The credential comes from `~/.system3/credentials` (`S3_CREDENTIALS_PATH`
overridable). The CLI creates that file at mode 600 and REFUSES TO READ IT
if the mode is wider than 600. An expired access token is refreshed
transparently and the rotated refresh token is written back BEFORE the
retried request is issued; two concurrent `s3` invocations never both
spend the same refresh token, because refresh is serialized by an
exclusive lock on the credential file. The stream is opened immediately
after run creation, inside the server's cumulative-unwatched abandonment
budget. The SSE parser skips `: ping` comment lines, never treats a gap in
`id:` as a dropped event (the server strips `cost` events for a
non-operator caller while `id:` keeps the real envelope `seq`), and
decodes `data:` as the full `Event` envelope. `POST /v1/query` is NEVER
retried by the CLI's retry policy (no idempotency key; retry is confined
to idempotent reads and to `stop`). A guardrail refusal and a fatal error
print to stderr and exit nonzero; a non-fatal transient/recoverable error
does not exit, the retry policy gets its chance first; `done` exits 0
after the references block prints. Ctrl-C sends `POST
/v1/query/{run_id}/stop` before the process exits; a second Ctrl-C during
that stop exits immediately rather than hanging. No cost figure is ever
printed for a non-operator credential, and the CLI's own suppression holds
independently of the server's.

Driven through the REAL entry point with REAL argv, over the REAL FastAPI
app in-process via `httpx.AsyncClient(transport=ASGITransport(app=app))`,
asserting on REAL captured stdout, stderr, and exit codes. The ONLY thing
faked anywhere in this file is `run_streaming` at `system_03_search_agent.
core.run_registry`, monkeypatched to a controlled fake async generator,
because the real `cypher_query` tool reaches the live Hetzner AGE graph
over an SSH tunnel this environment cannot open (the same constraint
`test_phase_4_0_premise.py` and `test_phase_4_1_premise.py` already state
for their own gates). Everything else, including the two custom
`httpx.AsyncBaseTransport` wrappers used below (`_CallCountingTransport`,
`_SlowStopTransport`), only OBSERVES or DELAYS a real call through the
real, unfaked `ASGITransport(app=app)`; neither one changes what the
server actually does or returns.

## The main.py contract this gate establishes (not one of the lead's four
## fixed interfaces)

`tracker/phase_4.2.md`'s "The interfaces, fixed by the lead before
dispatch" section fixes `credentials.py`, `sse.py`, and `client.py`
exactly, and gives `render.py`'s `Renderer` class. It does NOT fix
`main.py`'s entry-point shape, and the pre-build source read explicitly
flags that "the CLI's HTTP client MUST be injectable so the gate can pass
an `ASGITransport` and still exercise the real client code." Since a gate
written before the implementation has to drive SOME real, importable
callable, this file establishes and depends on the following shape for
T-4.2-05 to build against. This is a gap this gate fills, not a
contradiction of anything the lead fixed, and it is called out here (and
again in the final report) precisely so it can be confirmed or overridden
rather than silently assumed:

    async def async_main(
        argv: Sequence[str],
        *,
        stdin: TextIO,
        stdout: TextIO,
        stderr: TextIO,
        http_client: httpx.AsyncClient,
        interrupt_signals: asyncio.Queue[None] | None = None,
    ) -> int

    def main(argv: Sequence[str] | None = None) -> int
        # Production entry point: real sys.argv[1:], real stdio, a real
        # httpx.AsyncClient built from the stored credentials' base_url,
        # a real SIGINT handler that feeds a fresh asyncio.Queue. Wraps
        # async_main via asyncio.run().

`interrupt_signals` is this gate's test seam for Ctrl-C: one `put_nowait`
per SIGINT the production signal handler observes, so a test can simulate
a first and, distinctly, a second Ctrl-C without touching real OS signal
delivery (`os.kill`/`signal.signal` inside a pytest-asyncio process is its
own source of flakiness this gate avoids). `argv[0]` is the subcommand
(`"ask"`, `"stop"`, `"login"`); `ask` takes the question as a positional
argument and `--session-id` as a flag. Only `ask` is exercised below: none
of the twelve arms in `tracker/phase_4.2.md`'s premise-gate table name
`stop` or `login` directly (Ctrl-C drives the STOP API through an
in-flight `ask`, not the `stop` subcommand), so this gate does not
independently prove `s3 stop <run_id>` or `s3 login` work end to end, even
though T-4.2-05 must still build both. Noted here as a real, additional
gap this gate carries beyond the tracker's own list below, not folded into
that list since the instruction was to reproduce it unmodified.

## What this gate deliberately does NOT cover

Reproduced verbatim from `tracker/phase_4.2.md`'s own "What this gate
deliberately does NOT cover" section, per `.claude/rules/goal-contracts.md`'s
coverage-declaration discipline:

    - Real terminal and TTY behavior: colour, width detection, whether the
      dim status lines actually render dim. The gate captures streams, not
      a terminal.
    - Non-POSIX file-permission semantics. The mode-600 arms assert POSIX
      mode bits and are skipped on a platform without them. Windows is not
      covered and is not claimed.
    - A real socket. Every arm runs over `ASGITransport` in-process, per
      `tests/conftest.py`'s live-HTTP block. Genuine network flakiness,
      TCP resets, and true mid-stream reconnect against a real server are
      NOT exercised; the `Last-Event-ID` resume arms drive the resume code
      path, not a real dropped connection.
    - Multi-process concurrency at load. The refresh-lock arm proves the
      lock serializes two contending in-process attempts; it does not
      prove behavior across many simultaneous `s3` processes on a loaded
      machine. That is build phase 6.0's territory.
    - Interactive password entry. `s3 login` reads the password from a
      non-TTY stream in the gate.
"""

from __future__ import annotations

import asyncio
import io
import os
import stat
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import sqlalchemy as sa

from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
    DonePayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    ToolCall,
    ToolResultPayload,
    ToolStartPayload,
    TokenPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)

_TEST_AUTH_SECRET = "test-only-auth-secret-for-phase-4-2-premise-tests-do-not-reuse"


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


# ---------------------------------------------------------------------------
# Uniform ModuleNotFoundError, per the phase 4.1 gate's own precedent
# (`_require_mcp_server_module`): every test in this file depends on the
# `system_03_search_agent.adapters.cli` package existing, whether a given
# test imports `.main`, `.credentials`, `.client`, `.sse`, or `.render`
# directly. Importing one fixed module here means every test fails
# uniformly with ModuleNotFoundError before implementation exists, never a
# downstream symptom that is accurate but not the clean signal this
# repo's failing-first discipline requires.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_cli_main_module() -> None:
    import system_03_search_agent.adapters.cli.main  # noqa: F401


# ---------------------------------------------------------------------------
# DB-independent arm: credential-file mode handling needs no HTTP call, no
# auth, and no live database, so it runs unconditionally and BEFORE the DB
# reachability skip below (mirrors test_phase_4_0_premise.py's split).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "the mode-600 arms assert POSIX file-mode bits (tracker/phase_4.2.md's "
        "own stated exclusion: 'Non-POSIX file-permission semantics ... Windows "
        "is not covered and is not claimed')"
    ),
)
class TestCredentialMode:
    def test_a_file_at_0644_is_refused_not_read_with_a_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli import credentials as credentials_module

        creds_path = tmp_path / "credentials"
        monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
        credentials_module.store(
            credentials_module.Credentials(
                base_url="http://test", access_token="a", refresh_token="r"
            )
        )
        os.chmod(creds_path, 0o644)

        # Mutation: read-with-a-warning instead of refuse -> load() would
        # return a Credentials instead of raising, so asserting the
        # exception TYPE (not just "something failed") pins the refusal
        # rather than any unrelated failure.
        with pytest.raises(credentials_module.InsecureCredentialsError):
            credentials_module.load()

    def test_a_file_the_cli_creates_is_mode_600_at_creation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli import credentials as credentials_module

        creds_path = tmp_path / "credentials"
        monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
        credentials_module.store(
            credentials_module.Credentials(
                base_url="http://test", access_token="a", refresh_token="r"
            )
        )

        # Mutation: create at the OS umask default (commonly 0644) and
        # chmod down afterward -> the FINAL mode assertion below still
        # catches a wrong final mode; the "never widened first" half of
        # the premise is a during-creation property (os.open(..., 0o600)
        # vs open()+chmod()) this single external stat call cannot observe
        # without a race window of its own, so it is stated here rather
        # than independently proven.
        mode = stat.S_IMODE(os.stat(creds_path).st_mode)
        assert mode == 0o600

    def test_load_succeeds_on_a_file_genuinely_at_mode_600(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """No false positive: the refusal above is specific to a WIDER
        mode, not to every real file. Mutation: refuse every file
        regardless of mode -> this call would also raise."""
        from system_03_search_agent.adapters.cli import credentials as credentials_module

        creds_path = tmp_path / "credentials"
        monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
        credentials_module.store(
            credentials_module.Credentials(
                base_url="http://test", access_token="a", refresh_token="r"
            )
        )
        loaded = credentials_module.load()
        assert loaded.refresh_token == "r"
        assert loaded.access_token == "a"


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run the HTTP-level "
        "half of the phase 4.2 premise gate (every arm but credential-file mode)",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app  # noqa: E402
from system_03_search_agent.core import run_registry as run_registry_module  # noqa: E402
from system_03_search_agent.harness import cost_control  # noqa: E402
from system_03_search_agent.harness import harness as harness_module  # noqa: E402


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("ANON_DAILY_RUN_CAP", "10000")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch):
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty", action="dataset_report", records=[], record_count=0,
            total_available=None, truncated=False, error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda session, user_id, **kw: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda session, **kw: None)


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _signup_and_login(client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Real signup + real login against the real app. Returns (user_id,
    access_token, refresh_token) -- the raw tokens, not just a headers
    dict, since this gate's own credential store needs them directly."""
    email, password = _unique_email(), "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    body = login.json()
    return user_id, body["access_token"], body["refresh_token"]


def _provision_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path, *, access_token: str, refresh_token: str, base_url: str = "http://test"
):
    """Point CREDENTIALS_PATH at a fresh per-test file and write real,
    working tokens to it via the real store() function -- never a
    hand-built file, since the on-disk format is an implementation detail
    T-4.2-02 owns, not something this gate should guess at.

    Monkeypatches the MODULE ATTRIBUTE directly (not the S3_CREDENTIALS_PATH
    env var), since CREDENTIALS_PATH is declared as a module-level constant
    computed once; an env var set after the module's first import in this
    test session would not be re-read.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module

    creds_path = tmp_path / "credentials"
    monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
    credentials_module.store(
        credentials_module.Credentials(base_url=base_url, access_token=access_token, refresh_token=refresh_token)
    )
    return creds_path


async def _run_ask_main(
    argv: list[str], http_client: httpx.AsyncClient, *, stdin_text: str = ""
) -> tuple[int, str, str]:
    from system_03_search_agent.adapters.cli.main import async_main

    out, err = io.StringIO(), io.StringIO()
    exit_code = await async_main(
        argv, stdin=io.StringIO(stdin_text), stdout=out, stderr=err, http_client=http_client
    )
    return exit_code, out.getvalue(), err.getvalue()


def _only_active_run_id_for_owner(registry: "run_registry_module.RunRegistry", owner_id: str) -> str:
    """No public "list runs for owner" API exists on RunRegistry (only
    count_active_runs_for_owner). Reaching into `_runs` directly is the
    same private-attribute access this repo's own module docstring in
    run_registry.py already discusses at length ("No lock guards
    RunRegistry._runs ...")."""
    matches = [
        run_id
        for run_id, entry in registry._runs.items()  # noqa: SLF001 - no public accessor exists
        if entry.owner_id == owner_id and not entry.finished
    ]
    assert len(matches) == 1, f"expected exactly one active run for {owner_id!r}, found {matches}"
    return matches[0]


def _event(event_type: str, trace_id: str, seq: int, payload: object) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),  # type: ignore[attr-defined]
    )


def _citation(citation_id: str, display_index: int) -> CitationPayload:
    return CitationPayload(
        citation_id=citation_id,
        display_index=display_index,
        source="ncbi_gene",
        source_id="672",
        source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        layer="layer_1_graph",
        field="symbol",
        claim_text="BRCA1 is a protein-coding gene.",
        evidence_kind="direct",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public-domain",
    )


async def _golden_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A full, successful run, including a `cost` event: the server
    strips it for a non-operator caller (harness/cost_control.py's
    `sanitize_event_for_end_user`, real and unfaked), which is what
    naturally produces the real `id:` sequence gap `TestSseWireTolerance`
    checks the CLI tolerates."""
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "think", trace_id, 1,
        ThinkPayload(
            narrative="classified as a single-hop lookup", query_class="single_hop",
            resolved_entities=[], clarifying_question=None,
        ),
    )
    yield _event(
        "plan", trace_id, 2,
        PlanPayload(
            narrative="dispatch cypher_query",
            tool_calls=[ToolCall(tool="cypher_query", call_id="call-1", layer="layer_1_graph")],
        ),
    )
    yield _event(
        "tool_start", trace_id, 3,
        ToolStartPayload(call_id="call-1", tool="cypher_query", layer="layer_1_graph", status="ok"),
    )
    yield _event(
        "tool_result", trace_id, 4,
        ToolResultPayload(
            call_id="call-1", tool="cypher_query", layer="layer_1_graph", status="ok",
            summary="found 1 row", result_count=1, truncated=False,
        ),
    )
    yield _event(
        "token", trace_id, 5,
        TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"]),
    )
    yield _event("citation", trace_id, 6, _citation("c1", 1))
    yield _event(
        "trust_signal", trace_id, 7,
        TrustSignalPayload(
            outcome="answer", risk_tier="low", grounded=True, triangulated=None,
            citation_id="c1", scope="claim",
        ),
    )
    yield _event(
        "trust_signal", trace_id, 8,
        TrustSignalPayload(
            outcome="answer", risk_tier="low", grounded=True, triangulated=None,
            citation_id=None, scope="answer",
        ),
    )
    yield _event(
        "cost", trace_id, 9,
        CostPayload(query_cost_usd=0.0123, query_cap_usd=1.0, cap_fraction=0.0123, model_tier="synth"),
    )
    yield _event(
        "done", trace_id, 10,
        DonePayload(total_cost_usd=0.0123, total_tool_calls=1, elapsed_ms=120, trust_outcome="answer"),
    )


async def _refusal_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """The same cite-or-refuse shape core/graph.py's write_node itself
    emits on its refusal branch: a token carrying the refusal text, an
    answer-scope trust_signal with outcome="refuse", never a different or
    weaker wording for this surface."""
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token", trace_id, 1,
        TokenPayload(
            text="I could not find information on this in the available sources. ",
            marker_ids=[],
        ),
    )
    yield _event(
        "trust_signal", trace_id, 2,
        TrustSignalPayload(
            outcome="refuse", risk_tier="low", grounded=False, triangulated=None,
            citation_id=None, scope="answer",
            message="No groundable citation was found for this query.",
            fallback_link="https://www.ncbi.nlm.nih.gov/gene/",
        ),
    )
    yield _event(
        "cost", trace_id, 3,
        CostPayload(query_cost_usd=0.005, query_cap_usd=1.0, cap_fraction=0.005, model_tier="synth"),
    )
    yield _event(
        "done", trace_id, 4,
        DonePayload(total_cost_usd=0.005, total_tool_calls=1, elapsed_ms=90, trust_outcome="refuse"),
    )


async def _fake_stream_never_finishes(query: Query, context: RequestContext) -> AsyncIterator[Event]:  # pragma: no cover - see per-test override
    yield _event("guard", query.trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    await asyncio.sleep(3600)
    yield _event(  # pragma: no cover - unreachable
        "done", query.trace_id, 1,
        DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="answer"),
    )


class _CallCountingTransport(httpx.AsyncBaseTransport):
    """Wraps a real transport and counts requests by (method, path).
    Never changes what the real app returns; used only where the gate
    needs to OBSERVE call counts a real ASGITransport round trip does not
    otherwise expose (T-4.2-01's construction rule 1: the only FAKE in
    this file is run_streaming; this and _SlowStopTransport below only
    observe or delay, never replace, a real call's outcome)."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner
        self.calls: list[tuple[str, str]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        return await self._inner.handle_async_request(request)

    def count(self, method: str, path: str) -> int:
        return sum(1 for m, p in self.calls if m == method and p == path)


class _SlowStopTransport(httpx.AsyncBaseTransport):
    """Wraps a real transport and delays only the stop call, so a test can
    observe whether the CLI waits for that call's response before acting
    on a second interrupt. Delays timing only; the eventual response is
    the real, unfaked one."""

    def __init__(self, inner: httpx.AsyncBaseTransport, *, delay_seconds: float) -> None:
        self._inner = inner
        self._delay_seconds = delay_seconds

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/stop"):
            await asyncio.sleep(self._delay_seconds)
        return await self._inner.handle_async_request(request)


# ---------------------------------------------------------------------------
# Arm 1: Golden path
# ---------------------------------------------------------------------------


class TestGoldenPath:
    @pytest.mark.asyncio
    async def test_real_main_with_real_argv_streams_a_cited_answer_and_exits_0(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)

        async with _client() as client:
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, out, err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        # Mutation: swallow a step failure and still print a fake answer,
        # or hardcode 0 -> refusal/error arms below catch the reverse; this
        # pins the POSITIVE case actually completing cleanly.
        assert exit_code == 0
        # Mutation: drop the trust-prefix rendering entirely.
        assert "[answer]" in out
        # Mutation: paraphrase or truncate the server's own token text
        # instead of streaming it verbatim.
        assert "BRCA1 is a protein-coding gene" in out
        # Mutation: renumber markers client-side instead of using the
        # server's own marker_ids/display_index.
        assert "[1]" in out
        # Mutation: omit the references block, or omit source/source_url
        # per marker.
        assert "ncbi_gene" in out
        assert "https://www.ncbi.nlm.nih.gov/gene/672" in out
        assert err.strip() == ""


# ---------------------------------------------------------------------------
# Arm 2: Refusal path
# ---------------------------------------------------------------------------


class TestRefusalPath:
    @pytest.mark.asyncio
    async def test_a_zero_retrieval_run_prints_the_honest_refusal_with_no_fabricated_citations_and_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _refusal_path_stream)

        async with _client() as client:
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, out, err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        # Mutation: treat any terminal `done` as success regardless of
        # trust_outcome -> exit_code stays 0 for a refusal.
        assert exit_code != 0
        combined = out + err
        # Mutation: drop the trust-prefix rendering, or print [answer] for
        # a refuse outcome.
        assert "[refuse]" in combined
        assert "I could not find information on this" in combined
        # Mutation: render an empty references block as if complete, or
        # fabricate a citation to fill it.
        assert "ncbi_gene" not in out
        assert "672" not in out


# ---------------------------------------------------------------------------
# Arm 3: Credential mode -- see TestCredentialMode above (DB-independent,
# runs before the reachability skip).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Arm 4: Refresh rotation
# ---------------------------------------------------------------------------


class TestRefreshRotation:
    @pytest.mark.asyncio
    async def test_the_rotated_refresh_token_is_persisted_before_the_retried_request_is_issued(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli import credentials as credentials_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)

        async with _client() as setup_client:
            user_id, _access_token, refresh_token = await _signup_and_login(setup_client)

        creds_path = tmp_path / "credentials"
        monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
        # A syntactically well-formed but WRONG access token, forcing the
        # very first authenticated call to 401 deterministically, rather
        # than waiting out the real 15-minute access-token TTL in a test.
        credentials_module.store(
            credentials_module.Credentials(
                base_url="http://test", access_token="not-a-real-access-token", refresh_token=refresh_token
            )
        )

        recorded_refresh_token_on_reissue: list[str | None] = []

        class _OrderingTransport(httpx.AsyncBaseTransport):
            def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
                self._inner = inner
                self._create_calls_seen = 0

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                if request.method == "POST" and request.url.path == "/v1/query":
                    self._create_calls_seen += 1
                    if self._create_calls_seen == 2:
                        # This IS the retried create call (the first 401'd
                        # on the garbage access token above). The on-disk
                        # refresh_token must already be the NEW one at
                        # THIS exact point, not merely by the time the
                        # whole command finishes.
                        #
                        # Mutation: write the rotated token back AFTER
                        # issuing the retry (or not at all) -> the value
                        # read here would still equal the OLD refresh_token,
                        # failing the assertion below instead of only the
                        # weaker end-state check.
                        recorded_refresh_token_on_reissue.append(credentials_module.load().refresh_token)
                return await self._inner.handle_async_request(request)

        observing_client = httpx.AsyncClient(
            transport=_OrderingTransport(httpx.ASGITransport(app=app)), base_url="http://test"
        )
        try:
            exit_code, out, _err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], observing_client
            )
        finally:
            await observing_client.aclose()

        assert exit_code == 0
        assert "BRCA1 is a protein-coding gene" in out
        assert recorded_refresh_token_on_reissue, "the retried create call was never observed"
        assert recorded_refresh_token_on_reissue[0] != refresh_token
        assert recorded_refresh_token_on_reissue[0] == credentials_module.load().refresh_token


# ---------------------------------------------------------------------------
# Arm 5: Refresh lock
# ---------------------------------------------------------------------------


class TestRefreshLock:
    @pytest.mark.asyncio
    async def test_two_concurrent_s3_invocations_never_both_spend_the_same_refresh_token(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli import credentials as credentials_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)

        async with _client() as setup_client:
            _user_id, _access_token, refresh_token = await _signup_and_login(setup_client)

        creds_path = tmp_path / "credentials"
        monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
        credentials_module.store(
            credentials_module.Credentials(
                base_url="http://test", access_token="not-a-real-access-token", refresh_token=refresh_token
            )
        )

        client_a = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        client_b = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        try:
            # Both "processes" read the SAME on-disk stale access token and
            # race to refresh it -- the exact interleaving two real `s3`
            # invocations launched together would produce.
            #
            # Mutation: remove the exclusive lock around the credential
            # file's read-refresh-write critical section -> the LOSER of
            # the race presents an already-rotated (now-revoked) refresh
            # token, which the server's real, unfaked reuse detection
            # (auth/router.py's _revoke_family_on_reuse) treats as a
            # stolen-token signal and revokes the WHOLE session family,
            # including the winner's brand-new session. One of the two
            # invocations below would then exit nonzero instead of both
            # succeeding.
            result_a, result_b = await asyncio.gather(
                _run_ask_main(["ask", "What gene is BRCA1?", "--session-id", "session-a"], client_a),
                _run_ask_main(["ask", "What gene is BRCA1?", "--session-id", "session-b"], client_b),
            )
        finally:
            await client_a.aclose()
            await client_b.aclose()

        exit_a, out_a, err_a = result_a
        exit_b, out_b, err_b = result_b
        assert exit_a == 0, f"first concurrent invocation was logged out: {err_a}"
        assert exit_b == 0, f"second concurrent invocation was logged out: {err_b}"
        assert "BRCA1 is a protein-coding gene" in out_a
        assert "BRCA1 is a protein-coding gene" in out_b


# ---------------------------------------------------------------------------
# Arm 6: Abandonment budget
# ---------------------------------------------------------------------------


class TestAbandonmentBudget:
    @pytest.mark.asyncio
    async def test_the_stream_is_attached_within_the_servers_abandonment_budget(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        # Shrinks the REAL, shared default_registry's abandonment grace
        # window to near-zero, so any measurable delay between run
        # creation and the CLI's own attach is enough to get the run
        # cancelled out from under it.
        #
        # Mutation: insert any delay before the CLI opens its SSE
        # connection after create (a second round trip, unnecessary
        # logging, a sleep) -> the run is cancelled before the CLI ever
        # subscribes, and the golden-path assertions below (a real `done`
        # and a real answer) fail instead of a clean exit 0.
        monkeypatch.setattr(run_registry_module.default_registry, "_abandon_grace_seconds", 0.05)
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)

        async with _client() as client:
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, out, _err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        assert exit_code == 0
        assert "BRCA1 is a protein-coding gene" in out


# ---------------------------------------------------------------------------
# Arm 7: Create is never retried
# ---------------------------------------------------------------------------


class TestCreateIsNeverRetried:
    @pytest.mark.asyncio
    async def test_a_create_call_that_times_out_is_never_reissued_by_the_client(self) -> None:
        """Direct unit coverage of client.py's CliClient (the fixed
        interface), the same accepted pattern test_phase_4_1_premise.py's
        own TestTrustSignalHelpers uses for a property that is small,
        pure, and awkward to force through the full app: an
        httpx.MockTransport that fails on every call lets this test prove
        create_run performs NO internal retry, distinct from the 401
        refresh-and-reissue TestRefreshRotation proves above. A 401 is
        rejected before any handler body runs (get_caller's dependency
        fails first), so it is always safe to reissue with a fresh token;
        a network timeout carries no such guarantee, since the server may
        already have processed the request and spent the caller's
        allowance even though the client never saw the response. That
        asymmetry is the entire reason this call must never be blindly
        retried.
        """
        from system_03_search_agent.adapters.cli.client import CliClient
        from system_03_search_agent.adapters.cli.credentials import Credentials

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.ReadTimeout("simulated network timeout", request=request)

        http = httpx.AsyncClient(transport=httpx.MockTransport(_handler), base_url="http://test")
        client = CliClient(http, Credentials(base_url="http://test", access_token="a", refresh_token="r"))
        try:
            with pytest.raises(httpx.ReadTimeout):
                await client.create_run(text="What gene is BRCA1?", session_id="s1", audience_depth="researcher")
        finally:
            await http.aclose()

        # Mutation: wrap create_run's call in the same generic
        # retry-on-transient-failure helper every idempotent client
        # method uses -> call_count becomes 2 or more, since MockTransport
        # re-raises the identical failure on every invocation.
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_a_create_call_that_fails_creates_at_most_one_run_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """The end-to-end complement: force a REAL, server-side refusal on
        create (a structured 429, concurrent_run_cap_exceeded, real and
        unfaked) and confirm the CLI does not spend a second attempt
        against a resource that may already exist."""
        counting_transport = _CallCountingTransport(httpx.ASGITransport(app=app))
        client = httpx.AsyncClient(transport=counting_transport, base_url="http://test")
        try:
            monkeypatch.setattr(run_registry_module.default_registry, "_max_active_runs_per_owner", 0)
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, _out, err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )
        finally:
            await client.aclose()

        assert exit_code != 0
        assert err.strip() != ""
        # Mutation: retry a 429-refused create -> this count becomes 2 or
        # more.
        assert counting_transport.count("POST", "/v1/query") == 1


# ---------------------------------------------------------------------------
# Arm 8: SSE wire tolerance
# ---------------------------------------------------------------------------


class TestSseWireTolerance:
    def test_a_keepalive_comment_line_yields_no_event(self) -> None:
        from system_03_search_agent.adapters.cli.sse import parse_sse_lines

        lines = [
            "event: guard",
            'data: {"type": "guard"}',
            "id: 0",
            "",
            ": ping - 2026-08-16T00:00:00Z",
            "",
        ]
        # Mutation: treat a `:`-prefixed line as malformed data instead of
        # skipping it -> a second, spurious tuple appears, or parsing
        # raises.
        results = list(parse_sse_lines(lines))
        assert len(results) == 1
        assert results[0] == ("guard", '{"type": "guard"}', "0")

    def test_a_gap_in_id_yields_no_resume_loop_and_data_is_the_full_envelope(self) -> None:
        from system_03_search_agent.adapters.cli.sse import parse_sse_lines

        lines = [
            "event: guard",
            'data: {"type": "guard", "seq": 0}',
            "id: 0",
            "",
            "event: done",
            'data: {"type": "done", "seq": 2}',
            "id: 2",
            "",
        ]
        # Mutation: infer the missing seq=1 and synthesize a resume/refetch
        # -> a third tuple would appear, or an exception would be raised
        # for the "gap".
        results = list(parse_sse_lines(lines))
        assert [r[2] for r in results] == ["0", "2"]
        assert results[1][0] == "done"
        # Mutation: decode only the payload's own fields instead of the
        # full envelope -> this would not carry "type"/"seq" wrapped as
        # the raw data string.
        assert results[1][1] == '{"type": "done", "seq": 2}'

    @pytest.mark.asyncio
    async def test_a_real_non_operator_run_naturally_produces_an_id_gap_the_cli_tolerates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """The golden-path fixture's `cost` event is real; the STRIPPING
        of it for a non-operator caller is the server's real, unfaked
        sanitize_event_for_end_user. This proves the CLI survives the
        resulting real id gap end to end, not merely at the parser-unit
        level above."""
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)

        async with _client() as client:
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, out, _err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        # Mutation: treat a gap in id as a missed event and loop retrying a
        # resume -> this call either hangs (caught by the test timeout) or
        # never reaches exit 0.
        assert exit_code == 0
        assert "BRCA1 is a protein-coding gene" in out


# ---------------------------------------------------------------------------
# Arm 9: Stopped run
# ---------------------------------------------------------------------------


class TestStoppedRun:
    @pytest.mark.asyncio
    async def test_a_run_whose_terminal_event_is_a_fatal_cancelled_error_exits_nonzero_and_does_not_hang(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli.main import async_main

        started = asyncio.Event()

        async def _hanging_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
            yield _event("guard", query.trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
            started.set()
            await asyncio.sleep(3600)
            yield _event(  # pragma: no cover - unreachable
                "done", query.trace_id, 1,
                DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="answer"),
            )

        monkeypatch.setattr(run_registry_module, "run_streaming", _hanging_stream)

        async with _client() as client:
            user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            out, err = io.StringIO(), io.StringIO()
            ask_task = asyncio.create_task(
                async_main(
                    ["ask", "What gene is BRCA1?", "--session-id", "session-1"],
                    stdin=io.StringIO(""), stdout=out, stderr=err, http_client=client,
                )
            )
            await asyncio.wait_for(started.wait(), timeout=5.0)

            owner_id = f"user:{user_id}"
            run_id = _only_active_run_id_for_owner(run_registry_module.default_registry, owner_id)
            # Simulates a stop coming from elsewhere (a server-side
            # abandonment cancel, or another client's stop call), the same
            # terminal shape app.py's post_v1_query_stop produces: a fatal
            # `error` with error_class="cancelled", never a `done`.
            run_registry_module.default_registry.cancel_run(run_id)

            # Mutation: key exit-code logic only on the `done` event type
            # -> this hangs waiting for a `done` a cancelled run never
            # produces, timing out here instead of returning a real
            # nonzero exit code.
            exit_code = await asyncio.wait_for(ask_task, timeout=5.0)

        assert exit_code != 0
        assert err.strip() != ""


# ---------------------------------------------------------------------------
# Arm 10: Ctrl-C
# ---------------------------------------------------------------------------


class TestCtrlC:
    @pytest.mark.asyncio
    async def test_sigint_sends_stop_before_the_process_exits(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli.main import async_main

        started = asyncio.Event()
        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)

        async def _hanging_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
            yield _event("guard", query.trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
            started.set()
            await asyncio.sleep(3600)

        monkeypatch.setattr(run_registry_module, "run_streaming", _hanging_stream)

        async with _client() as client:
            user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            out, err = io.StringIO(), io.StringIO()
            interrupt_signals: asyncio.Queue[None] = asyncio.Queue()
            ask_task = asyncio.create_task(
                async_main(
                    ["ask", "What gene is BRCA1?", "--session-id", "session-1"],
                    stdin=io.StringIO(""), stdout=out, stderr=err, http_client=client,
                    interrupt_signals=interrupt_signals,
                )
            )
            await asyncio.wait_for(started.wait(), timeout=5.0)

            owner_id = f"user:{user_id}"
            run_id = _only_active_run_id_for_owner(run_registry_module.default_registry, owner_id)

            interrupt_signals.put_nowait(None)  # the one, simulated Ctrl-C
            exit_code = await asyncio.wait_for(ask_task, timeout=5.0)

        assert exit_code != 0
        # Mutation: exit on SIGINT without ever calling
        # POST /v1/query/{run_id}/stop -> the run stays neither cancelled
        # nor finished after the CLI process exits.
        entry = run_registry_module.default_registry.get_run(run_id)
        assert entry.cancelled or entry.finished

    @pytest.mark.asyncio
    async def test_a_second_sigint_during_the_stop_call_exits_immediately_rather_than_hanging(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli.main import async_main

        started = asyncio.Event()

        async def _hanging_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
            yield _event("guard", query.trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
            started.set()
            await asyncio.sleep(3600)

        monkeypatch.setattr(run_registry_module, "run_streaming", _hanging_stream)

        # The stop call itself is instant over an in-process ASGITransport
        # with no fake, so there is no natural window to interrupt DURING
        # it. _SlowStopTransport only delays the timing of this one real
        # call (never changing its outcome), which is what manufactures a
        # real, observable race window for the second interrupt to land
        # in.
        slow_client = httpx.AsyncClient(
            transport=_SlowStopTransport(httpx.ASGITransport(app=app), delay_seconds=2.0),
            base_url="http://test",
        )
        try:
            user_id, access_token, refresh_token = await _signup_and_login(slow_client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            out, err = io.StringIO(), io.StringIO()
            interrupt_signals: asyncio.Queue[None] = asyncio.Queue()
            ask_task = asyncio.create_task(
                async_main(
                    ["ask", "What gene is BRCA1?", "--session-id", "session-1"],
                    stdin=io.StringIO(""), stdout=out, stderr=err, http_client=slow_client,
                    interrupt_signals=interrupt_signals,
                )
            )
            await asyncio.wait_for(started.wait(), timeout=5.0)

            interrupt_signals.put_nowait(None)  # first Ctrl-C: begins the (slow) stop call
            await asyncio.sleep(0.2)  # let the CLI actually enter the stop call
            interrupt_signals.put_nowait(None)  # second Ctrl-C: arrives while stop is still in flight

            start = time.monotonic()
            # Mutation: wait for the first stop call's response before
            # honoring the second interrupt -> this would take >= the
            # artificial 2.0s delay, well past the bound asserted below.
            exit_code = await asyncio.wait_for(ask_task, timeout=3.0)
            elapsed = time.monotonic() - start
        finally:
            await slow_client.aclose()

        assert exit_code != 0
        assert elapsed < 1.5


# ---------------------------------------------------------------------------
# Arm 11: Error-body shapes
# ---------------------------------------------------------------------------


class TestErrorBodyShapes:
    @pytest.mark.asyncio
    async def test_a_structured_429_body_renders_without_crashing_and_is_actionable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        # Forces app.py's own real, unfaked precheck to refuse every
        # create with a STRUCTURED 429 body
        # ({"reason": "concurrent_run_cap_exceeded", "message": ...}).
        monkeypatch.setattr(run_registry_module.default_registry, "_max_active_runs_per_owner", 0)

        async with _client() as client:
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, _out, err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        # Mutation: index the body assuming a bare string (`detail`) ->
        # KeyError/TypeError on this dict body crashes the renderer
        # instead of a clean nonzero exit with a real message.
        assert exit_code != 0
        assert err.strip() != ""
        assert "wait" in err.lower() or "stop" in err.lower()

    @pytest.mark.asyncio
    async def test_a_bare_string_401_body_renders_without_crashing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from system_03_search_agent.adapters.cli import credentials as credentials_module

        creds_path = tmp_path / "credentials"
        monkeypatch.setattr(credentials_module, "CREDENTIALS_PATH", creds_path)
        # Neither token was ever really issued: /auth/refresh's 401 body
        # is a bare string ("invalid or expired refresh token"), the
        # opposite shape from the 429 above.
        credentials_module.store(
            credentials_module.Credentials(
                base_url="http://test", access_token="not-a-real-access-token",
                refresh_token="not-a-real-refresh-token",
            )
        )

        async with _client() as client:
            # Mutation: index the body assuming a structured dict
            # (`detail["message"]`) -> KeyError/TypeError on this bare
            # string body crashes the renderer instead of a clean nonzero
            # exit.
            exit_code, _out, err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        assert exit_code != 0
        assert err.strip() != ""


# ---------------------------------------------------------------------------
# Arm 12: Never cost, two layers
# ---------------------------------------------------------------------------


class TestNeverCostTwoLayers:
    @pytest.mark.asyncio
    async def test_a_non_operator_run_prints_no_dollar_figure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)

        async with _client() as client:
            _user_id, access_token, refresh_token = await _signup_and_login(client)
            _provision_credentials(monkeypatch, tmp_path, access_token=access_token, refresh_token=refresh_token)

            exit_code, out, err = await _run_ask_main(
                ["ask", "What gene is BRCA1?", "--session-id", "session-1"], client
            )

        assert exit_code == 0
        # Mutation: forward the done event's total_cost_usd (or a stray
        # cost event) straight into rendered output -> "$" or the real
        # fake-stream cost figure would appear.
        assert "$" not in out
        assert "$" not in err
        assert "0.0123" not in out

    def test_the_renderer_itself_suppresses_cost_independently_of_the_server(self) -> None:
        """The second, independent layer: hands the renderer a hand-built
        `cost` event and a `done` event with a NON-ZERO total_cost_usd
        directly, bypassing the server's own sanitize_event_for_end_user
        entirely. Even a future server-side regression that stops
        stripping `cost` events must not surface a dollar figure through
        this surface."""
        from system_03_search_agent.adapters.cli.render import Renderer

        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        cost_event = _event(
            "cost", "t1", 0,
            CostPayload(query_cost_usd=9.99, query_cap_usd=10.0, cap_fraction=0.999, model_tier="synth"),
        )
        done_event = _event(
            "done", "t1", 1,
            DonePayload(total_cost_usd=9.99, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"),
        )
        renderer.handle(cost_event)
        renderer.handle(done_event)
        renderer.finish()

        # Mutation: render done.total_cost_usd unconditionally instead of
        # gating it on operator -> "9.99" or "$" appears in the output.
        assert "9.99" not in out.getvalue()
        assert "$" not in out.getvalue()
        assert "$" not in err.getvalue()
