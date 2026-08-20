"""The stable named scientist persona: T-4.5-09, Section 14.2.

Presentation only. The persona never changes which tools run, which records
are retrieved, or what the trust signal says. Section 14.1 puts
personalization in orchestration and synthesis style, never in grounding, and
the persona is the purest presentation half of that: it is a label.

Two properties Section 14.2 fixes, both enforced here rather than by
convention:

    IT IS STABLE. A registered account keeps the same name for the life of
    the account. An anonymous session keeps one for that session and draws a
    new one next session. `persona_for_session` is a pure function of the
    identity it is given, so stability does not depend on a caller
    remembering to cache it.

    IT IS DELIVERED ONCE. The name reaches the caller on the `POST /v1/query`
    response body, never repeated on every streamed event. This module owns
    where the name comes from; Section 12.7 owns rendering it.

The list is deceased-only by product decision, 2026-08-20. A living
scientist's name rendered above a generated biomedical answer reads as an
association or an endorsement that person never gave, on a product that makes
biomedical claims and that will sometimes be wrong. Every entry carries a
year of death, which is what makes that property CHECKABLE rather than
trusted, and the premise gate asserts it against the data file so a later
extension toward 100 is caught by a test rather than by a reader.

Depends on:
    - system_03_search_agent/data/personas_v1.json (the curated list)

Writes:
    - Nothing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: The versioned list. Loaded ONCE at first use and cached for the process
#: lifetime, never re-read per request. `.claude/rules/prompt-cache-
#: discipline.md` requires exactly this for the few-shot pool and the reason
#: generalizes: a per-request read of a file that is supposed to be constant
#: is a liveness risk even when it happens to return the same bytes.
_PERSONA_FILE = Path(__file__).resolve().parent.parent / "data" / "personas_v1.json"

#: The ceiling the mechanism is built for, per the 2026-08-20 decision to
#: ship roughly 30 with everything sized for 100. Extending the data file up
#: to this is a data change with no code change.
MAX_PERSONAS = 100


@dataclass(frozen=True)
class Persona:
    """One curated scientist.

    `died` is not decoration. It is the field that makes the deceased-only
    property checkable, so it is required rather than optional: an entry
    without it cannot be verified and is rejected at load time.
    """

    name: str
    full_name: str
    died: int
    basis: str


@lru_cache(maxsize=1)
def load_persona_list() -> tuple[Persona, ...]:
    """Load and validate the curated list, once per process.

    Validation runs at LOAD time rather than at draw time on purpose. A
    malformed or non-compliant list should fail loudly when the process
    starts, not silently hand out a name that violates the product decision
    on some later request.
    """
    raw = json.loads(_PERSONA_FILE.read_text(encoding="utf-8"))
    entries = raw.get("personas", [])
    if not entries:
        raise ValueError(f"the persona list at {_PERSONA_FILE.name} is empty")
    if len(entries) > MAX_PERSONAS:
        raise ValueError(
            f"the persona list holds {len(entries)} entries, past the "
            f"{MAX_PERSONAS} the draw and storage are sized for"
        )

    personas: list[Persona] = []
    seen: set[str] = set()
    for entry in entries:
        died = entry.get("died")
        if not isinstance(died, int):
            # ValueError rather than the TypeError ruff's TRY004 suggests:
            # this is a malformed DATA FILE, not a caller passing the wrong
            # type to this function, and every other rejection in this loader
            # raises ValueError for the same reason. A caller catching bad
            # persona data should not have to catch two exception types to
            # cover one failure mode.
            raise ValueError(  # noqa: TRY004
                f"persona {entry.get('name')!r} has no year of death. The list "
                "is deceased-only by product decision (2026-08-20) and the "
                "year is how that is checkable rather than trusted"
            )
        name = str(entry["name"])
        if name in seen:
            # A duplicate would silently skew the draw toward one name, which
            # is invisible in any test that only checks membership.
            raise ValueError(f"duplicate persona name {name!r}")
        seen.add(name)
        personas.append(
            Persona(
                name=name,
                full_name=str(entry["full_name"]),
                died=died,
                basis=str(entry["basis"]),
            )
        )
    return tuple(personas)


def persona_for_session(*, session_id: str, user_id: str | None) -> str:
    """The persona name for this caller.

    Deterministic rather than random, and that is the mechanism by which
    Section 14.2's stability requirement holds: the same identity always maps
    to the same name, so nothing has to be stored for the name to be stable
    within a session, and a stored value on the user row (T-4.5-05) is a
    persistence optimization rather than the source of truth.

    Keyed on `user_id` when there is one, so a registered account keeps its
    name across sessions and devices, and on `session_id` otherwise, so an
    anonymous session holds one name and draws a new one next session. That
    is exactly the split Section 14.2 describes.

    SHA-256 rather than `hash()`, because Python's string hash is salted per
    process, so `hash()` would give a user a different scientist every time
    the server restarted. That is a real bug that a test inside one process
    could never see.
    """
    identity = user_id or session_id
    personas = load_persona_list()
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % len(personas)
    return personas[index].name


__all__ = ["MAX_PERSONAS", "Persona", "load_persona_list", "persona_for_session"]
