"""Tests for the observability config resolver.

The arms here exist because this module answers one question, "is this
turned on", for three separate records, and a wrong answer is silent in
the worst direction: it transmits. Two properties carry almost all of that
risk and both are asserted below against inputs constructed to make them
fail rather than to make them pass.

First, an empty-but-present variable must read as absent. `env.example`
and this repository's `.env` both ship `LANGSMITH_API_KEY=` and
`POSTHOG_API_KEY=` as bare assignments, so a membership test would report
both services configured on every machine here. `test_empty_string_is_
absent_not_present` fails if anyone rewrites `_first_set` as an `in
os.environ` check.

Second, and this is the phase's critical finding F-5.0-03: the tracing
FLAG is already `true` in `.env` and `env.example:107` and has been since
long before tracing was built, so it carries no operator intent. Requiring
the key as well is what makes "no credential means zero outbound calls"
true by construction. `test_flag_alone_does_not_enable_tracing`
reconstructs exactly the environment every machine in this project is in
today and fails if the key requirement is ever relaxed to a flag-only
check.

Every arm monkeypatches the environment rather than reading the ambient
one, since an arm whose result depends on the developer's own `.env` is
measuring the machine rather than the code.
"""

import uuid

import pytest

from system_03_search_agent.observability import config

_ALL_OBSERVABILITY_VARS = (
    "LANGSMITH_API_KEY",
    "LANGCHAIN_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGCHAIN_PROJECT",
    "LANGSMITH_ENDPOINT",
    "LANGCHAIN_ENDPOINT",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING",
    "POSTHOG_API_KEY",
    "POSTHOG_HOST",
    "TOOL_AUDIT_LOG_PATH",
    "TOOL_AUDIT_LOG_ENABLED",
)


@pytest.fixture(autouse=True)
def _clean_observability_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every variable this module reads before each arm.

    Autouse rather than opt-in because the failure it prevents is an arm
    that passes for the wrong reason: a developer whose shell exports
    POSTHOG_API_KEY, which is the actual situation on the machine this
    phase was built on, would otherwise see `analytics_enabled()` return
    True in an arm that never set it.
    """
    for name in _ALL_OBSERVABILITY_VARS:
        monkeypatch.delenv(name, raising=False)


class TestPresenceRules:
    def test_empty_string_is_absent_not_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSTHOG_API_KEY", "")
        assert config.posthog_api_key() is None
        assert config.analytics_enabled() is False

    def test_whitespace_only_is_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSTHOG_API_KEY", "   ")
        assert config.posthog_api_key() is None

    def test_value_is_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSTHOG_API_KEY", "  phc_real  ")
        assert config.posthog_api_key() == "phc_real"


class TestTracingGate:
    """The critical finding, F-5.0-03, pinned as arms."""

    def test_flag_alone_does_not_enable_tracing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The exact environment every machine in this project is in today.

        This is the arm that would have caught the naive implementation of
        this phase. The flag is on, inherited from a `.env` written before
        tracing existed; no key was ever provisioned; nothing may transmit.
        """
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "")

        assert config.tracing_flag_set() is True
        assert config.tracing_enabled() is False

    def test_key_alone_does_not_enable_tracing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_notreal")
        assert config.tracing_flag_set() is False
        assert config.tracing_enabled() is False

    def test_flag_and_key_together_enable_tracing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_notreal")
        assert config.tracing_enabled() is True

    @pytest.mark.parametrize("spelling", ["LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2"])
    def test_both_namespaces_are_honoured(
        self, monkeypatch: pytest.MonkeyPatch, spelling: str
    ) -> None:
        """langsmith resolves LANGSMITH_ before LANGCHAIN_ and honours both.

        This repository's own `.env` uses the LANGCHAIN_ spelling for the
        flag and the LANGSMITH_ spelling for everything else, so a resolver
        that honoured only one namespace would disagree with the library
        about whether tracing is on.
        """
        monkeypatch.setenv(spelling, "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_notreal")
        assert config.tracing_enabled() is True

    @pytest.mark.parametrize("raw", ["1", "yes", "on", "True ", "TRUE"])
    def test_truthiness_matches_the_library_exactly(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        """Only `true` counts, case-insensitively after stripping.

        Deliberately reproducing the installed library's narrow rule rather
        than a friendlier one. A resolver that accepted `1` while the
        library did not would produce the worst available outcome: this
        repository assembles and attaches a trace payload that langsmith
        then silently drops, and every arm asserting "tracing is on"
        passes while nothing is ever recorded.
        """
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", raw)
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_notreal")

        expected = raw.strip().lower() == "true"
        assert config.tracing_enabled() is expected


class TestAuditDefaults:
    def test_audit_is_on_by_default(self) -> None:
        """No credential and no opt-in required.

        The audit log implements a PRD obligation rather than an optional
        integration, and a record that defaults to off is not an audit
        trail.
        """
        assert config.audit_enabled() is True
        assert str(config.audit_log_path()) == "logs/tool_audit.jsonl"

    def test_audit_off_needs_the_literal_word_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`0` must NOT disable the audit trail.

        A hurried operator setting `TOOL_AUDIT_LOG_ENABLED=0` is more
        likely to have meant "off" than "on", but guessing either way is
        worse than requiring the unambiguous word, and the safe default
        when the intent is unclear is to keep auditing.
        """
        monkeypatch.setenv("TOOL_AUDIT_LOG_ENABLED", "0")
        assert config.audit_enabled() is True

        monkeypatch.setenv("TOOL_AUDIT_LOG_ENABLED", "false")
        assert config.audit_enabled() is False

        monkeypatch.setenv("TOOL_AUDIT_LOG_ENABLED", "FALSE")
        assert config.audit_enabled() is False

    def test_path_is_overridable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOOL_AUDIT_LOG_PATH", "/var/log/s3/audit.jsonl")
        assert str(config.audit_log_path()) == "/var/log/s3/audit.jsonl"


class TestHosts:
    def test_posthog_host_trailing_slash_is_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PostHog's router does not treat a double slash as equivalent."""
        monkeypatch.setenv("POSTHOG_HOST", "https://eu.i.posthog.com/")
        assert config.posthog_host() == "https://eu.i.posthog.com"

    def test_defaults_are_the_documented_hosts(self) -> None:
        assert config.posthog_host() == "https://us.i.posthog.com"
        assert config.langsmith_endpoint() == "https://api.smith.langchain.com"


class TestPostHogKeyKindIsBounded:
    """J-07 and F-5.0-12: `analytics_enabled()` accepted ANY prefix, and the
    key actually configured was a `phx_` PERSONAL api key, account-wide and
    read-write. `litellm`'s import-time `load_dotenv()` made it live in any
    shell that had not exported the right value, so the finding's claim
    that nothing would be sent was enforced by which shell you were in.

    Every key below is a generated stand-in with a real prefix, never a
    literal credential and never whatever the ambient environment holds:
    the autouse fixture clears the real variable first, so these arms
    measure the code rather than the machine.
    """

    def test_a_project_key_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The positive control, without which every arm below would pass
        equally against a function that refused everything.
        """
        key = "phc_" + uuid.uuid4().hex
        monkeypatch.setenv("POSTHOG_API_KEY", key)

        assert config.posthog_api_key() == key
        assert config.analytics_enabled() is True
        assert config.posthog_key_refusal_reason() is None

    def test_a_personal_key_is_refused_by_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The exact credential that was live. Refused, and the reason says
        which kind it was so an operator is not left with a bare
        "analytics off" beside a key visibly present in `.env`.
        """
        monkeypatch.setenv("POSTHOG_API_KEY", "phx_" + uuid.uuid4().hex)

        assert config.posthog_api_key() is None
        assert config.analytics_enabled() is False
        reason = config.posthog_key_refusal_reason()
        assert reason is not None
        assert "PERSONAL" in reason

    def test_a_project_secret_key_is_refused_by_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSTHOG_API_KEY", "phs_" + uuid.uuid4().hex)

        assert config.posthog_api_key() is None
        assert config.analytics_enabled() is False
        reason = config.posthog_key_refusal_reason()
        assert reason is not None
        assert "SECRET" in reason

    def test_an_unrecognised_prefix_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The load-bearing arm. A key kind nobody here has reasoned about
        must mean analytics OFF, never on: this is the difference between a
        bound and an enumerated blocklist, and an enumerated blocklist is
        what the pre-fix code effectively was with an empty list.
        """
        monkeypatch.setenv("POSTHOG_API_KEY", "phz_" + uuid.uuid4().hex)

        assert config.posthog_api_key() is None
        assert config.analytics_enabled() is False
        assert config.posthog_key_refusal_reason() is not None

    def test_a_refusal_reason_never_carries_the_key_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The diagnostic exists so a misconfiguration is not silent, and a
        diagnostic that prints the credential would be a worse outcome than
        the silence it replaces.
        """
        secret_value = uuid.uuid4().hex
        monkeypatch.setenv("POSTHOG_API_KEY", "phx_" + secret_value)

        reason = config.posthog_key_refusal_reason()

        assert reason is not None
        assert secret_value not in reason

    def test_no_key_at_all_is_an_absence_not_a_refusal(self) -> None:
        """A caller must be able to tell "nothing configured" from "the
        wrong thing configured", which is why the reason is a separate
        function rather than a second return value.
        """
        assert config.posthog_api_key() is None
        assert config.analytics_enabled() is False
        assert config.posthog_key_refusal_reason() is None
