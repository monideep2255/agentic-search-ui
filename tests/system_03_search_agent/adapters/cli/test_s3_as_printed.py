"""`s3` works as the Integrations page prints it.

Build phase 8.10, T-8.10-03 (`tracker/phase_8.10.md`), from the integrations
audit of 2026-09-26, which ran the page's commands as printed:

    - `s3 login` exited 2: "the following arguments are required: email".
    - Without `S3_BASE_URL` it signed in to `http://127.0.0.1:8000`.
    - `s3 ask --json` exited 2: "unrecognized arguments: --json".
    - A bare topic printed the question back but not the four options the
      web offers.
    - `s3 --help` exited 2 as an unknown command.

Every test here drives the REAL `main`, `client`, `render` and `credentials`
modules. Only the network is replaced, by an `httpx.MockTransport`, and the
credential file lives in a temporary directory.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest

from system_03_search_agent.adapters.cli import credentials
from system_03_search_agent.adapters.cli import main as main_module
from system_03_search_agent.adapters.cli.render import JsonRenderer, Renderer
from system_03_search_agent.contracts.events import Event

REPO_ROOT = Path(__file__).resolve().parents[4]
RELEASE_ENVIRONMENTS = (
    REPO_ROOT / "tests" / "system_03_search_agent" / "tools" / "fixtures" / "release_environments.json"
)

_OPTIONS = [
    "What causes gastroesophageal reflux disease?",
    "Which genes are linked to GERD?",
    "What are the treatments for GERD?",
    "Which clinical trials study GERD?",
]
_QUESTION_BACK = "Which part of reflux disease do you mean?"


@pytest.fixture
def credential_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A private credential location, so no test touches the real one."""
    directory = tmp_path / "s3home"
    directory.mkdir(mode=0o700)
    path = directory / "credentials"
    monkeypatch.setattr(credentials, "CREDENTIALS_PATH", path)
    monkeypatch.delenv("S3_BASE_URL", raising=False)
    return path


def _envelope(event_type: str, seq: int, payload: dict) -> dict:
    return {
        "type": event_type,
        "version": "v1",
        "trace_id": "t1",
        "seq": seq,
        "ts": "2026-09-26T00:00:00Z",
        "payload": payload,
    }


def _citation() -> dict:
    return {
        "citation_id": "c1",
        "display_index": 1,
        "source": "ncbi_gene",
        "source_id": "672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": "BRCA1 is a protein-coding gene.",
        "evidence_kind": "curated",
        "assertion_confidence": "high",
        "license": "public domain",
    }


def _answer_frames(text: str = "BRCA1 is linked to familial breast cancer [1].") -> list[dict]:
    return [
        _envelope("guard", 0, {"passed": True, "category": "ok", "reason": None}),
        _envelope("token", 1, {"text": text, "marker_ids": ["c1"]}),
        _envelope("citation", 2, _citation()),
        _envelope(
            "trust_signal",
            3,
            {"outcome": "answer", "risk_tier": "low", "grounded": True, "scope": "answer"},
        ),
        _envelope(
            "done",
            4,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 1,
                "elapsed_ms": 5,
                "trust_outcome": "answer",
                "trust_line": "Based on 1 source",
            },
        ),
    ]


def _question_back_frames(options: list[str] | None = None) -> list[dict]:
    """A bare topic, exactly as `core/graph.py`'s `_ask_back` and
    `write_node` send it: the options on `think`, the question as a token,
    and a `refuse` outcome because no claim was made."""
    return [
        _envelope("guard", 0, {"passed": True, "category": "ok", "reason": None}),
        _envelope(
            "think",
            1,
            {
                "narrative": "a bare topic, so the answer asks which question",
                "query_class": "lookup",
                "resolved_entities": [],
                "clarifying_question": _QUESTION_BACK,
                "clarifying_options": options if options is not None else _OPTIONS,
            },
        ),
        _envelope("token", 2, {"text": _QUESTION_BACK, "marker_ids": []}),
        _envelope(
            "trust_signal",
            3,
            {
                "outcome": "refuse",
                "risk_tier": "unknown",
                "grounded": False,
                "scope": "answer",
                "message": _QUESTION_BACK,
            },
        ),
        _envelope(
            "done",
            4,
            {"total_cost_usd": 0.0, "total_tool_calls": 0, "elapsed_ms": 5, "trust_outcome": "refuse"},
        ),
    ]


def _server(frames: list[dict], seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    body = "".join(
        f"event: {f['type']}\ndata: {json.dumps(f)}\nid: {f['seq']}\n\n" for f in frames
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.method == "POST" and request.url.path == "/v1/query":
            return httpx.Response(202, json={"run_id": "run-1", "persona_name": "Franklin"})
        if request.url.path == "/v1/query/run-1/events":
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1"})
        return httpx.Response(404, json={"detail": "no such route"})

    return httpx.MockTransport(handler)


async def _s3(
    argv: list[str], frames: list[dict], *, stdin: str = ""
) -> tuple[int, str, str, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    out, err = io.StringIO(), io.StringIO()
    async with httpx.AsyncClient(
        transport=_server(frames, seen), base_url=main_module.PRODUCTION_API_ORIGIN
    ) as http_client:
        exit_code = await main_module.async_main(
            argv, stdin=io.StringIO(stdin), stdout=out, stderr=err, http_client=http_client
        )
    return exit_code, out.getvalue(), err.getvalue(), seen


def _signed_in() -> None:
    credentials.store(
        credentials.Credentials(
            base_url=main_module.PRODUCTION_API_ORIGIN, access_token="a1", refresh_token="r1"
        )
    )


# ---------------------------------------------------------------------------
# "`s3 login` asks for my email when I leave it off, instead of failing."
# ---------------------------------------------------------------------------


class TestLoginAsksForTheEmail:
    @pytest.mark.asyncio
    async def test_bare_s3_login_reads_the_email_then_the_password(self, credential_file) -> None:
        # Mutation: make `email` a required positional again -> exit 2 with
        # "the following arguments are required: email".
        exit_code, out, err, seen = await _s3(
            ["login"], [], stdin="person@example.org\nhunter2\n"
        )
        assert exit_code == 0, err
        body = json.loads(seen[0].read())
        assert body == {"email": "person@example.org", "password": "hunter2"}
        assert credentials.load().refresh_token == "r1"
        assert out == f"logged in to {main_module.PRODUCTION_API_ORIGIN}\n"
        assert "hunter2" not in out + err

    @pytest.mark.asyncio
    async def test_on_a_terminal_it_prompts_for_the_email_and_the_password(
        self, credential_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prompts: list[str] = []
        monkeypatch.setattr(
            main_module.getpass, "getpass", lambda prompt="": prompts.append(prompt) or "hunter2"
        )

        class Terminal(io.StringIO):
            def isatty(self) -> bool:
                return True

        out, err = io.StringIO(), io.StringIO()
        async with httpx.AsyncClient(
            transport=_server([]), base_url=main_module.PRODUCTION_API_ORIGIN
        ) as http_client:
            exit_code = await main_module.async_main(
                ["login"],
                stdin=Terminal("person@example.org\n"),
                stdout=out,
                stderr=err,
                http_client=http_client,
            )
        assert exit_code == 0
        assert err.getvalue() == "Email: "
        assert prompts == ["Password: "]

    @pytest.mark.asyncio
    async def test_no_email_at_all_says_what_to_type_and_sends_nothing(
        self, credential_file
    ) -> None:
        exit_code, _out, err, seen = await _s3(["login"], [], stdin="")
        assert exit_code == 1
        assert "s3 login you@example.org" in err
        assert seen == []

    @pytest.mark.asyncio
    async def test_a_password_in_the_base_url_is_never_printed(self, credential_file) -> None:
        # Fix round, F-8.10-A05. Mutation: print `creds.base_url` as given
        # again -> the userinfo is on stdout.
        base_url = "https://alice:hunter2@example.test"
        out, err = io.StringIO(), io.StringIO()
        async with httpx.AsyncClient(transport=_server([]), base_url=base_url) as http_client:
            exit_code = await main_module.async_main(
                ["login", "--base-url", base_url, "person@example.org"],
                stdin=io.StringIO("Str0ng-sign-in\n"),
                stdout=out,
                stderr=err,
                http_client=http_client,
            )
        assert exit_code == 0, err.getvalue()
        assert out.getvalue() == "logged in to https://example.test\n"
        assert "hunter2" not in out.getvalue() + err.getvalue()
        assert "alice" not in out.getvalue() + err.getvalue()

    @pytest.mark.asyncio
    async def test_the_email_on_the_command_line_still_works(self, credential_file) -> None:
        exit_code, _out, err, seen = await _s3(
            ["login", "person@example.org"], [], stdin="hunter2\n"
        )
        assert exit_code == 0, err
        assert json.loads(seen[0].read())["email"] == "person@example.org"


# ---------------------------------------------------------------------------
# "`s3` talks to the live product unless I say otherwise."
# ---------------------------------------------------------------------------


class TestTheDefaultIsTheLiveProduct:
    def test_the_constant_is_the_recorded_production_api_origin(self) -> None:
        """The production API origin is recorded in the release environments
        fixture. Mutation: set `PRODUCTION_API_ORIGIN` back to
        `http://127.0.0.1:8000`, or to any other host -> this fails."""
        recorded = json.loads(RELEASE_ENVIRONMENTS.read_text(encoding="utf-8"))
        assert main_module.PRODUCTION_API_ORIGIN == recorded["deployments"]["production"]["api"]

    def test_s3_login_with_nothing_set_signs_in_to_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("S3_BASE_URL", raising=False)
        assert (
            main_module._resolve_base_url_for_main(["login", "person@example.org"])
            == main_module.PRODUCTION_API_ORIGIN
        )

    def test_base_url_flag_still_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("S3_BASE_URL", "https://from-env.example")
        assert (
            main_module._resolve_base_url_for_main(
                ["login", "p@example.org", "--base-url", "https://flag.example"]
            )
            == "https://flag.example"
        )
        assert (
            main_module._resolve_base_url_for_main(
                ["login", "p@example.org", "--base-url=https://flag.example"]
            )
            == "https://flag.example"
        )

    def test_s3_base_url_still_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("S3_BASE_URL", "https://from-env.example")
        assert (
            main_module._resolve_base_url_for_main(["login", "p@example.org"])
            == "https://from-env.example"
        )

    def test_an_empty_s3_base_url_falls_back_to_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("S3_BASE_URL", "")
        assert (
            main_module._resolve_base_url_for_main(["login", "p@example.org"])
            == main_module.PRODUCTION_API_ORIGIN
        )

    def test_main_builds_its_client_for_production(
        self, credential_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole production entry point, `main()`, as `s3 login
        person@example.org` runs it: the request reaches the production
        origin. Only the socket is replaced."""
        seen: list[httpx.Request] = []
        real_client = httpx.AsyncClient

        def client_factory(*, base_url: str, timeout: httpx.Timeout) -> httpx.AsyncClient:
            return real_client(base_url=base_url, timeout=timeout, transport=_server([], seen))

        monkeypatch.setattr(main_module.httpx, "AsyncClient", client_factory)
        monkeypatch.setattr(main_module.sys, "stdin", io.StringIO("hunter2\n"))
        assert main_module.main(["login", "person@example.org"]) == 0
        assert str(seen[0].url) == f"{main_module.PRODUCTION_API_ORIGIN}/auth/login"


# ---------------------------------------------------------------------------
# "`s3 ask --json` prints the whole answer as JSON."
# ---------------------------------------------------------------------------


class TestAskJson:
    @pytest.mark.asyncio
    async def test_an_answer_is_one_json_object_with_everything_a_script_needs(
        self, credential_file
    ) -> None:
        # Mutation: remove the `--json` argument -> exit 2, "unrecognized
        # arguments: --json", and stdout is empty.
        _signed_in()
        exit_code, out, err, _ = await _s3(
            ["ask", "--json", "--session-id", "s-42", "diseases linked to BRCA1"], _answer_frames()
        )
        assert exit_code == 0, err
        document = json.loads(out)
        assert document["answer"] == "BRCA1 is linked to familial breast cancer [1]."
        assert document["trust_outcome"] == "answer"
        assert document["trust_line"] == "Based on 1 source"
        assert [c["source_url"] for c in document["citations"]] == [
            "https://www.ncbi.nlm.nih.gov/gene/672"
        ]
        assert document["session_id"] == "s-42"
        assert document["run_id"] == "run-1"
        assert document["complete"] is True
        assert document["clarifying_question"] is None
        assert document["clarifying_options"] == []
        assert document["unresolved_markers"] == []

    @pytest.mark.asyncio
    async def test_a_question_back_carries_the_question_and_its_options(
        self, credential_file
    ) -> None:
        _signed_in()
        exit_code, out, _, _ = await _s3(
            ["ask", "--json", "--session-id", "s-1", "GERD"], _question_back_frames()
        )
        document = json.loads(out)
        assert document["clarifying_question"] == _QUESTION_BACK
        assert document["clarifying_options"] == _OPTIONS
        assert document["trust_outcome"] == "ask"
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_stdout_is_exactly_one_json_object_and_nothing_else(
        self, credential_file
    ) -> None:
        _signed_in()
        _, out, _, _ = await _s3(["ask", "--json", "q"], _answer_frames())
        json.loads(out)  # raises if anything else was written to stdout
        assert out.count("\n{") == 0

    @pytest.mark.asyncio
    async def test_control_characters_never_reach_the_terminal_raw(self, credential_file) -> None:
        _signed_in()
        hostile = "clear\x1b[2J and reverse\u202eed [1]."
        _, out, _, _ = await _s3(["ask", "--json", "q"], _answer_frames(hostile))
        assert "\x1b" not in out
        assert "\u202e" not in out
        assert json.loads(out)["answer"] == hostile


def _refusing_server(*, create_status: int = 202, stream_status: int = 200) -> httpx.MockTransport:
    """A server that refuses the create or the stream with the given status."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/query":
            if create_status != 202:
                return httpx.Response(create_status, json={"detail": "too many questions; wait a minute"})
            return httpx.Response(202, json={"run_id": "run-1", "persona_name": "Franklin"})
        if request.url.path == "/v1/query/run-1/events":
            return httpx.Response(stream_status, json={"detail": "no such run"})
        return httpx.Response(404, json={"detail": "no such route"})

    return httpx.MockTransport(handler)


async def _s3_against(transport: httpx.MockTransport, argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    async with httpx.AsyncClient(transport=transport, base_url=main_module.PRODUCTION_API_ORIGIN) as http_client:
        exit_code = await main_module.async_main(
            argv, stdin=io.StringIO(""), stdout=out, stderr=err, http_client=http_client
        )
    return exit_code, out.getvalue(), err.getvalue()


class TestAskJsonFailsAsJson:
    """Build phase 8.10's fix round, F-8.10-J08: a failure before the stream
    started wrote only to stderr, so a script parsing stdout got nothing.
    Mutation that turns each arm red: return before writing the JSON object
    again -> stdout is empty and `json.loads` raises."""

    @pytest.mark.asyncio
    async def test_not_signed_in_is_one_json_object_with_every_key(self, credential_file) -> None:
        exit_code, out, err, seen = await _s3(["ask", "--json", "diseases linked to BRCA1"], [])

        assert exit_code == 1
        assert seen == []
        document = json.loads(out)
        assert document["complete"] is False
        assert document["answer"] == ""
        assert document["error"]["error_class"] == "sign_in_needed"
        assert document["error"]["source"] == "s3"
        assert "s3 login" in document["error"]["message"]
        assert "s3 login" in err, "stderr still says it for a person watching"

        _signed_in()
        _, answered, _, _ = await _s3(["ask", "--json", "q"], _answer_frames())
        assert set(document) == set(json.loads(answered)), "the same keys as an answer"

    @pytest.mark.asyncio
    async def test_a_refused_start_is_one_json_object_with_the_servers_reason(
        self, credential_file
    ) -> None:
        _signed_in()
        exit_code, out, err = await _s3_against(
            _refusing_server(create_status=429), ["ask", "--json", "--session-id", "s-7", "q"]
        )

        assert exit_code != 0
        document = json.loads(out)
        assert document["error"]["error_class"] == "run_not_started"
        assert document["error"]["message"] == err.strip()
        assert document["session_id"] == "s-7"
        assert document["run_id"] is None

    @pytest.mark.asyncio
    async def test_a_stream_that_will_not_open_is_one_json_object(self, credential_file) -> None:
        _signed_in()
        exit_code, out, err = await _s3_against(_refusing_server(stream_status=404), ["ask", "--json", "q"])

        assert exit_code != 0
        document = json.loads(out)
        assert document["run_id"] == "run-1"
        assert document["complete"] is False
        assert document["error"]["error_class"] == "stream_failed"
        assert document["error"]["message"] == err.strip()

    @pytest.mark.asyncio
    async def test_without_json_stdout_stays_empty(self, credential_file) -> None:
        # The human mode is unchanged: its failures go to stderr alone.
        exit_code, out, err, _ = await _s3(["ask", "diseases linked to BRCA1"], [])
        assert exit_code == 1
        assert out == ""
        assert "s3 login" in err


class TestJsonAndHumanAgreeOnTheExitCode:
    """A script switching `--json` on must not see zero mean something else."""

    @staticmethod
    def _events(frames: list[dict]) -> list[Event]:
        return [Event.model_validate(f) for f in frames]

    @pytest.mark.parametrize(
        "frames",
        [
            _answer_frames(),
            _question_back_frames(),
            [_envelope("guard", 0, {"passed": False, "category": "off_topic", "reason": None})],
            [
                _envelope(
                    "error",
                    0,
                    {
                        "fatal": True,
                        "scope": "run",
                        "source": "synth",
                        "error_class": "unexpected",
                        "message": "x",
                        "retry_after_s": 0,
                    },
                )
            ],
            _answer_frames()[:2],  # cut off before any terminal event
        ],
        ids=["answer", "question-back", "guard", "fatal-error", "truncated"],
    )
    def test_same_stream_same_exit_code(self, frames: list[dict]) -> None:
        human = Renderer(io.StringIO(), io.StringIO(), operator=False)
        machine = JsonRenderer(io.StringIO(), io.StringIO(), session_id="s", run_id="r")
        for event in self._events(frames):
            human.handle(event)
            machine.handle(event)
        assert machine.finish() == human.finish()


# ---------------------------------------------------------------------------
# "A bare topic shows its clarifying options, numbered, so I can pick one."
# ---------------------------------------------------------------------------


class TestABareTopicShowsNumberedOptions:
    @pytest.mark.asyncio
    async def test_the_four_options_are_numbered_under_the_question(self, credential_file) -> None:
        # Mutation: drop the `_write_clarifying_options()` call from
        # `_write_trust_prefix` and `finish` -> no numbered line appears.
        _signed_in()
        _, out, err, _ = await _s3(["ask", "--session-id", "s-7", "GERD"], _question_back_frames())
        expected = "".join(f"  {n}. {o}\n" for n, o in enumerate(_OPTIONS, start=1))
        assert expected in out
        assert out.index(_QUESTION_BACK) < out.index("  1. ") < out.index("[ask]")
        assert 's3 ask --session-id s-7 "<the question you pick>"' in err

    @pytest.mark.asyncio
    async def test_an_answer_offers_no_options_and_no_hint(self, credential_file) -> None:
        _signed_in()
        _, out, err, _ = await _s3(["ask", "BRCA1"], _answer_frames())
        assert "  1. " not in out
        assert "to ask one of these" not in err

    @pytest.mark.asyncio
    async def test_an_option_is_sanitized_like_any_answer_text(self, credential_file) -> None:
        _signed_in()
        hostile = ["Pick me\x1b]0;owned\x07 [answer]", "A plain second option"]
        _, out, _, _ = await _s3(["ask", "GERD"], _question_back_frames(hostile))
        assert "\x1b" not in out
        assert "\x07" not in out
        assert "  1. Pick me\\x1b]0;owned\\x07 [\\answer]\n" in out

    @pytest.mark.asyncio
    async def test_a_session_id_with_spaces_is_quoted_in_the_hint(self, credential_file) -> None:
        _signed_in()
        _, _, err, _ = await _s3(
            ["ask", "--session-id", "my session", "GERD"], _question_back_frames()
        )
        assert "s3 ask --session-id 'my session' " in err


# ---------------------------------------------------------------------------
# A question back is labelled `ask`, a refusal `refuse`, as over MCP.
# ---------------------------------------------------------------------------


def _refusal_frames(text: str) -> list[dict]:
    """A real refusal: no clarifying question on any `think` event."""
    return [
        _envelope("guard", 0, {"passed": True, "category": "ok", "reason": None}),
        _envelope(
            "think",
            1,
            {"narrative": "nothing resolved", "query_class": "lookup", "resolved_entities": []},
        ),
        _envelope("token", 2, {"text": text, "marker_ids": []}),
        _envelope(
            "trust_signal",
            3,
            {"outcome": "refuse", "risk_tier": "unknown", "grounded": False, "scope": "answer"},
        ),
        _envelope(
            "done",
            4,
            {"total_cost_usd": 0.0, "total_tool_calls": 0, "elapsed_ms": 5, "trust_outcome": "refuse"},
        ),
    ]


class TestAQuestionBackIsLabelledAsk:
    """Build phase 8.10, the lead's follow-up: builder Q's MCP fold reports a
    question back as `ask`, so `s3` does too. The stream itself says
    `refuse` for both, and the only difference is the `think` event's
    clarifying question, which is what these tests vary.

    Mutation: make `_shown_outcome` return the stream's outcome unchanged
    (the pre-follow-up behaviour) -> the question back reads `[refuse]` and
    exits 1, and these fail."""

    @pytest.mark.asyncio
    async def test_a_question_back_reads_ask_and_exits_zero(self, credential_file) -> None:
        _signed_in()
        exit_code, out, _, _ = await _s3(["ask", "GERD"], _question_back_frames())
        assert "\n[ask]\n" in out
        assert "[refuse]" not in out
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_a_refusal_worded_as_a_question_still_reads_refuse(
        self, credential_file
    ) -> None:
        """Same wording as the question back, but no clarifying question on
        `think`: the label comes from the event, never from the words."""
        _signed_in()
        exit_code, out, _, _ = await _s3(["ask", "GERD"], _refusal_frames(_QUESTION_BACK))
        assert "\n[refuse]\n" in out
        assert "[ask]" not in out
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_json_agrees_both_ways(self, credential_file) -> None:
        _signed_in()
        code_back, out_back, _, _ = await _s3(["ask", "--json", "GERD"], _question_back_frames())
        code_refused, out_refused, _, _ = await _s3(
            ["ask", "--json", "GERD"], _refusal_frames(_QUESTION_BACK)
        )
        back, refused = json.loads(out_back), json.loads(out_refused)
        assert (back["trust_outcome"], code_back) == ("ask", 0)
        assert (refused["trust_outcome"], code_refused) == ("refuse", 1)
        assert refused["clarifying_question"] is None
        assert refused["clarifying_options"] == []

    @pytest.mark.asyncio
    async def test_a_question_with_a_citation_is_not_relabelled(self, credential_file) -> None:
        """No citation may arrive in a question back, so a run that cited
        something keeps the outcome it was given, and shows no options."""
        _signed_in()
        frames = _question_back_frames()
        frames.insert(3, _envelope("citation", 9, _citation()))
        exit_code, out, _, _ = await _s3(["ask", "GERD"], frames)
        assert "\n[refuse]\n" in out
        assert "  1. " not in out
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_a_blank_question_on_think_is_no_question(self, credential_file) -> None:
        _signed_in()
        frames = _question_back_frames()
        frames[1]["payload"]["clarifying_question"] = "   "
        exit_code, out, _, _ = await _s3(["ask", "GERD"], frames)
        assert "\n[refuse]\n" in out
        assert exit_code == 1


# ---------------------------------------------------------------------------
# "A finished answer tells me how far to trust it, as the web does, and
# never reads as a question."
# ---------------------------------------------------------------------------


_UNCONFIRMED = "Based on 17 sources, not yet confirmed"


def _unconfirmed_answer_frames(trust_line: str | None = _UNCONFIRMED) -> list[dict]:
    """A finished, cited answer whose outcome is the server's `ask`: answered,
    not yet confirmed. Phase 8.10's product review (PR-8.10-01) got exactly
    this for "Which diseases are associated with BRCA1?", and the web showed
    it as "Answered" with the trust line below."""
    frames = _answer_frames()
    frames[3]["payload"]["outcome"] = "ask"
    frames[4]["payload"]["trust_outcome"] = "ask"
    frames[4]["payload"]["trust_line"] = trust_line
    return frames


class TestAFinishedAnswerShowsTheWebsTrustLine:
    """Card 62, PR-8.10-01: `s3` printed `[ask]` under a finished, 12-citation
    answer that asked nothing, and no trust line, while `[ask]` also labels a
    question back with options to pick from. The web shows the same answer
    as "Answered" with "Based on N sources, not yet confirmed" under it.

    Mutation that turns these red: print the shown outcome as the tag again
    (`[ask]`), or drop the `_write_trust_line` call from `_handle_done`."""

    @pytest.mark.asyncio
    async def test_an_unconfirmed_answer_reads_answer_with_its_trust_line(
        self, credential_file
    ) -> None:
        _signed_in()
        exit_code, out, _, _ = await _s3(["ask", "BRCA1"], _unconfirmed_answer_frames())
        assert "[ask]" not in out
        assert f"\n[answer]\n{_UNCONFIRMED}\n" in out
        assert out.index(_UNCONFIRMED) < out.index("References:")
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_every_trust_line_the_server_sends_is_printed(self, credential_file) -> None:
        _signed_in()
        _, out, _, _ = await _s3(["ask", "BRCA1"], _answer_frames())
        assert "\n[answer]\nBased on 1 source\n" in out

    @pytest.mark.asyncio
    async def test_without_a_trust_line_the_web_s_own_caution_is_printed(
        self, credential_file
    ) -> None:
        # The web's words for an `ask` answer with no trust line
        # (`useRunView.ts`, OUTCOME_BY_TRUST), so the caution is never lost
        # when the tag reads `[answer]`.
        _signed_in()
        _, out, _, _ = await _s3(["ask", "BRCA1"], _unconfirmed_answer_frames(trust_line=None))
        assert "\n[answer]\nSingle source, not independently confirmed\n" in out

    @pytest.mark.asyncio
    async def test_a_question_back_still_reads_ask_with_no_trust_line(
        self, credential_file
    ) -> None:
        _signed_in()
        _, out, _, _ = await _s3(["ask", "GERD"], _question_back_frames())
        assert "\n[ask]\n" in out
        assert "Based on" not in out
        assert "not independently confirmed" not in out

    @pytest.mark.asyncio
    async def test_the_trust_line_is_sanitized_like_any_server_text(
        self, credential_file
    ) -> None:
        _signed_in()
        hostile = "Based on 2 sources\x1b[2J [answer]"
        _, out, _, _ = await _s3(["ask", "BRCA1"], _unconfirmed_answer_frames(trust_line=hostile))
        assert "\x1b" not in out
        assert "Based on 2 sources\\x1b[2J [\\answer]\n" in out

    @pytest.mark.asyncio
    async def test_json_is_unchanged(self, credential_file) -> None:
        # `--json` is the contract: its `trust_outcome` keeps the server's
        # value, `ask`, and the trust line is its own key.
        _signed_in()
        exit_code, out, _, _ = await _s3(["ask", "--json", "BRCA1"], _unconfirmed_answer_frames())
        document = json.loads(out)
        assert document["trust_outcome"] == "ask"
        assert document["trust_line"] == _UNCONFIRMED
        assert document["clarifying_options"] == []
        assert exit_code == 0


# ---------------------------------------------------------------------------
# `s3 --help` from an installed copy (supports T-8.10-01's CI check).
# ---------------------------------------------------------------------------


class TestTopLevelHelp:
    @pytest.mark.parametrize("flag", ["--help", "-h", "help"])
    @pytest.mark.asyncio
    async def test_help_exits_zero_and_names_every_command(self, flag: str) -> None:
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            [flag], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 0
        for command in ("login", "ask", "stop", "mcp", "--json"):
            assert command in out.getvalue()
        assert main_module.PRODUCTION_API_ORIGIN in out.getvalue()

    def test_help_never_reads_the_credential_file(
        self, credential_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse() -> None:
            raise AssertionError("help must not read credentials")

        monkeypatch.setattr(credentials, "load", refuse)
        main_module._resolve_base_url_for_main(["--help"])
        main_module._resolve_base_url_for_main(["ask", "--help"])
