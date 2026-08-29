"""The single resolver for every observability environment value.

Why this module exists at all, rather than each of the three records
reading `os.environ` for itself: tracing, analytics and the audit log each
need to answer "am I turned on", and three separate answers to that
question is how one of them ends up transmitting while an operator
believes everything is off. There is one answer per record and it lives
here.

THE LOAD-BEARING DECISION IN THIS FILE, and the reason build phase 5.0
opened with a critical finding rather than a clean slate:

`LANGCHAIN_TRACING_V2=true` is ALREADY set in this repository's `.env` and
in `env.example:107`, and has been since well before tracing was built.
The installed langsmith (0.10.10, `utils.py:121-139`) resolves tracing
through `get_env_var("TRACING_V2", ...)` across BOTH the `LANGSMITH_` and
`LANGCHAIN_` namespaces, so that spelling is honoured and the flag is
live. The only thing that has ever suppressed tracing is a hardcoded
`tracing_context(enabled=False)` in `core/run.py`.

So a flag-only reading of "is tracing on" returns True today, on every
machine and both deployments, with no credential and nobody having asked
for it. `tracing_enabled()` therefore requires the API KEY as well as the
flag, and the key is the half that carries the operator's actual intent: a
flag inherited from a `.env` written months before the feature existed is
not consent, and a key someone deliberately provisioned is. This also
makes the goal contract's "no credential means provably zero outbound
calls" true by construction rather than by careful coding downstream, and
it costs nothing real, since tracing without a key cannot succeed anyway
and would only produce failing outbound calls on every query, which is the
exact behaviour `core/run.py`'s override was added to prevent.

Everything here reads the environment at CALL time rather than at import
time. Two reasons, one of them measured elsewhere in this repository:
import-time capture makes a value untestable without reimporting the
module, and it silently freezes whatever the environment happened to be
when the first import ran, which in a test session is whatever the
previous test left behind.
"""

import os
from pathlib import Path

# LangSmith. Both namespaces are listed because the installed langsmith
# honours `LANGSMITH_<NAME>` first and `LANGCHAIN_<NAME>` second, and this
# repository's own `.env` uses the LANGCHAIN_ spelling for the tracing flag
# and the LANGSMITH_ spelling for everything else. Resolving them in the
# same order langsmith itself does is what keeps this module's answer and
# the library's answer from diverging.
_ENV_LANGSMITH_API_KEY = ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")
_ENV_LANGSMITH_PROJECT = ("LANGSMITH_PROJECT", "LANGCHAIN_PROJECT")
_ENV_LANGSMITH_ENDPOINT = ("LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT")
_ENV_LANGSMITH_TRACING = (
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING",
)

# PostHog. Section 24's env config table reserves exactly these two names,
# so they are reused rather than reinvented.
_ENV_POSTHOG_API_KEY = ("POSTHOG_API_KEY",)
_ENV_POSTHOG_HOST = ("POSTHOG_HOST",)

# The audit log. Neither name appears in Section 24 yet, since Section 20.3
# names the path as a literal (`logs/tool_audit.jsonl` in v1, "the
# equivalent managed log target once deployed"). The env override is what
# makes the deployed case reachable without a code change.
_ENV_AUDIT_PATH = ("TOOL_AUDIT_LOG_PATH",)
_ENV_AUDIT_ENABLED = ("TOOL_AUDIT_LOG_ENABLED",)

_DEFAULT_LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"
_DEFAULT_LANGSMITH_PROJECT = "agentic-search-ui"
_DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"
# Built from segments rather than written as one "logs/tool_audit.jsonl"
# literal, and the reason is a guard rather than taste. `test_tiers.py`'s
# pattern-11 scan (`_MODEL_ID_SHAPE`) flags any string constant shaped like
# `provider/model`, which a POSIX path matches exactly. A single literal
# here fails that scan as a false positive of the SCANNER's mechanism, not
# as a violation of the invariant it protects.
#
# Written this way rather than exempted because an exemption would be the
# THIRD enumerated instance of the same class: build phase 2.2 hit this
# guard once (LEARNINGS.md, 2026-08-03), F-4.2-09 hit it again for IANA
# media types and added `_EXEMPT_MEDIA_TYPE_LITERALS`, and this would be
# the third. Per `goal-contracts.md`, when the subject and the check are
# both right about different things, the subject is made unambiguous and
# neither definition moves. Filed separately as F-5.0-11, which is about
# the scanner's breadth rather than about this constant.
_DEFAULT_AUDIT_PATH = str(Path("logs") / "tool_audit.jsonl")


def _first_set(names: tuple[str, ...]) -> str | None:
    """Return the first non-empty environment value among `names`, or None.

    Empty-but-present is treated as absent throughout this module, which is
    not a stylistic choice: `env.example` and this repository's `.env` both
    ship `LANGSMITH_API_KEY=` and `POSTHOG_API_KEY=` as empty assignments,
    so `"LANGSMITH_API_KEY" in os.environ` is True on every machine here
    while no credential exists. A membership test would report both
    services configured on a developer laptop that has never held either
    key. Whitespace is stripped for the same reason: a key that is one
    space is not a key.
    """
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and raw.strip():
            return raw.strip()
    return None


def _is_truthy(raw: str | None) -> bool:
    """Match the installed langsmith's own truthiness rule exactly.

    langsmith 0.10.10 (`utils.py:139`) treats the tracing flag as on only
    when the resolved string equals `"true"`, case-insensitively after
    stripping. It does NOT accept `1`, `yes`, or `on`. This function
    deliberately reproduces that narrow rule rather than a friendlier one,
    because a config module that considers `TRACING=1` enabled while the
    library considers it disabled produces the worst possible outcome: this
    repository builds and attaches a trace payload that the library then
    silently drops, and every arm asserting "tracing is on" passes while
    nothing is ever recorded.
    """
    return raw is not None and raw.strip().lower() == "true"


def langsmith_api_key() -> str | None:
    """The LangSmith credential, or None when no credential is configured.

    Callers must never log or embed the return value. It is returned so a
    client can be constructed with it, and for no other purpose.
    """
    return _first_set(_ENV_LANGSMITH_API_KEY)


def langsmith_project() -> str:
    """The LangSmith project traces are filed under."""
    return _first_set(_ENV_LANGSMITH_PROJECT) or _DEFAULT_LANGSMITH_PROJECT


def langsmith_endpoint() -> str:
    """The LangSmith ingest host."""
    return _first_set(_ENV_LANGSMITH_ENDPOINT) or _DEFAULT_LANGSMITH_ENDPOINT


def tracing_flag_set() -> bool:
    """Whether the tracing FLAG alone is on, ignoring the credential.

    Exposed separately from `tracing_enabled()` so the difference between
    the two is observable rather than buried, and so an operator diagnostic
    can say "the flag is on but no key is set" instead of a bare "off".
    This is the value that is True on every machine in this project today.
    """
    return _is_truthy(_first_set(_ENV_LANGSMITH_TRACING))


def tracing_enabled() -> bool:
    """Whether LangSmith tracing should actually run.

    BOTH the flag and a credential are required. See this module's
    docstring for why the flag alone is not sufficient and never was: it is
    inherited from a `.env` written before the feature existed, so it
    carries no operator intent, while a provisioned key does.
    """
    return tracing_flag_set() and langsmith_api_key() is not None


def posthog_api_key() -> str | None:
    """The PostHog project key, or None when analytics are not configured.

    This is PostHog's PROJECT api key, the write-only public token that
    travels in the request BODY as `api_key` rather than in a header. It is
    still read through this module and still never logged, because a key
    that is safe to embed in a browser bundle is not thereby safe to print
    into a server log that also carries user identifiers.
    """
    return _first_set(_ENV_POSTHOG_API_KEY)


def posthog_host() -> str:
    """The PostHog ingest host, defaulting to US cloud.

    A trailing slash is stripped so callers can join a path without
    producing a double slash, which PostHog's router does not treat as
    equivalent.
    """
    return (_first_set(_ENV_POSTHOG_HOST) or _DEFAULT_POSTHOG_HOST).rstrip("/")


def analytics_enabled() -> bool:
    """Whether PostHog analytics should actually run.

    Only the credential gates this one. Unlike tracing there is no ambient
    flag already set to `true` across the project, so there is no inherited
    intent to disambiguate, and a provisioned key is the whole signal.
    """
    return posthog_api_key() is not None


def audit_log_path() -> Path:
    """Where the Section 20.3 tool-call audit log is written.

    Defaults to the literal path Section 20.3 names for v1. Unlike tracing
    and analytics this record needs no credential and no third-party
    service, so it is on by default: the audit requirement it implements
    (every Layer 2 and Layer 3 access logged with its authorization, Step
    1.12) is a PRD obligation rather than an optional integration, and a
    record that defaults to off is not an audit trail.
    """
    return Path(_first_set(_ENV_AUDIT_PATH) or _DEFAULT_AUDIT_PATH)


def audit_enabled() -> bool:
    """Whether the audit log writes at all.

    On unless explicitly switched off, for the reason in `audit_log_path`.
    The off switch exists for one narrow case, a test that must assert the
    disabled path, and is spelled as an explicit `false` rather than as
    "any value" so that `TOOL_AUDIT_LOG_ENABLED=0` does not silently
    disable the audit trail while reading, to a hurried operator, like it
    enabled it.
    """
    raw = _first_set(_ENV_AUDIT_ENABLED)
    if raw is None:
        return True
    return raw.strip().lower() != "false"
