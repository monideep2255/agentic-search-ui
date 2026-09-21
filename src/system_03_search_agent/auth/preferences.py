"""Per-account preferences stored on `users.profile`: T-4.5-08, Section 14.5.

Exactly one preference lives here today, the audience depth, and the module
exists rather than the two call sites reaching into the JSONB blob directly
because `profile` is schemaless. A schemaless column with two hand-rolled
readers drifts on the first typo, and the typo is silent: a misspelled key
reads as "no preference set" and the user's choice is quietly forgotten
rather than erroring.

Depends on:
    - system_03_search_agent.data.models (User.profile)

Writes:
    - users.profile, one key.
"""

from __future__ import annotations

from typing import Any

#: The `profile` key. Named once, read and written only through this module.
_DEPTH_KEY = "audience_depth"

#: Section 14.5's three values and its default. Restated here rather than
#: imported from the Pydantic Literal because a stored preference is
#: untrusted input on the way back OUT: a row written by an older or buggier
#: version, or edited by hand, must not be able to put an arbitrary string
#: into a prompt directive. Anything unrecognised falls back to the default.
_ALLOWED = frozenset({"clinical_brief", "researcher", "deep_technical", "plain_language"})
_DEFAULT = "researcher"


def read_audience_depth(user: Any) -> str:
    """The account's last-used depth, or the default if it has none.

    Never raises. A profile that is missing, not a dict, or holds an
    unrecognised value all mean the same thing to a caller, which is "this
    account has no usable preference", and the answer is the default rather
    than an error: a corrupt preference must not be able to fail a login.
    """
    profile = getattr(user, "profile", None)
    if not isinstance(profile, dict):
        return _DEFAULT
    value = profile.get(_DEPTH_KEY)
    return value if value in _ALLOWED else _DEFAULT


def write_audience_depth(user: Any, depth: str) -> bool:
    """Record `depth` as this account's last-used value.

    Returns True when the stored value actually changed, so the caller can
    skip a database write on the common case where it did not. Every query
    carries a depth, so writing unconditionally would put one UPDATE on the
    hot path of every authenticated request to record a value that is almost
    always the same as the one already there.

    Rejects an unrecognised value silently rather than storing it, for the
    same reason `read_audience_depth` refuses to return one: the stored
    preference feeds a prompt directive, and the set of things that may
    appear there is closed.
    """
    if depth not in _ALLOWED:
        return False
    profile = getattr(user, "profile", None)
    if not isinstance(profile, dict):
        profile = {}
    if profile.get(_DEPTH_KEY) == depth:
        return False
    # Reassigned rather than mutated in place: SQLAlchemy does not track
    # in-place mutation of a plain JSONB dict, so `profile[key] = value`
    # alone would be silently dropped at flush. This is the defect that makes
    # a JSONB preference look like it saved and then not.
    user.profile = {**profile, _DEPTH_KEY: depth}
    return True


def resolve_audience_depth(*, requested: str | None, user: Any | None) -> str:
    """The depth a run should actually use: F-4.5-J-15 and F-4.5-A-13's fix.

    Section 14.5: "once auth is live, depth defaults to the user's last-used
    value". Until this function existed, that sentence was true of exactly
    one caller. `write_audience_depth` ran on every authenticated query and
    `read_audience_depth` was served on `GET /auth/me`, and the round trip
    closed only because the browser re-echoed the value on the next request.
    A CLI, GraphQL, MCP or bare REST caller that omitted the field got the
    hardcoded contract default no matter what the account had stored. A
    preference honored by one of several clients is not a stored preference,
    it is a client-side setting the server happens to persist.

    So the resolution moves to the server, and it is stated once, here,
    rather than at each surface. The order is:

        A depth the caller named explicitly always wins, per Section 14.5's
        "always overridable per query". `None` means "not named", which is
        why the surfaces make the field nullable rather than defaulting it.

        Otherwise the account's stored value, when there is an account.

        Otherwise the contract default, `researcher`.

    `user` is `None` for a guest or an anonymous caller, which has no row to
    remember against. Section 14.5's "before that, it defaults per session"
    is NOT implemented by this function and is not implemented anywhere: it
    needs a per-session depth store that does not exist. Carried as an open
    item rather than faked here, because falling back to the contract
    default is the honest behavior and a comment claiming otherwise would be
    the exact shape `self-eval-loop` warns about.

    Never raises, for the same reason `read_audience_depth` never raises: a
    corrupt or unrecognised stored preference means "this account has no
    usable preference", not "fail this query".
    """
    if requested in _ALLOWED:
        # `requested` is validated by each surface's own contract before it
        # reaches here. Re-checked anyway, because this function is what
        # decides what reaches a prompt directive, and the closed set is
        # cheap to re-assert at the boundary that actually depends on it.
        return str(requested)
    if user is None:
        return _DEFAULT
    return read_audience_depth(user)
