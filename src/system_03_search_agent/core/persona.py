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

    IT SURVIVES AN EXTENSION OF THE LIST. The 2026-08-20 product decision
    ships roughly 30 names with the mechanism SIZED for 100, so that a
    later extension is a data change and not a code change. A draw that
    reshuffles when the list grows defeats exactly that decision, so the
    draw is not a modulus over the list length. See `persona_for_session`
    for the mechanism and for the one case in which an identity does move.

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
import random
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

#: The longest `about` line the chip's card is designed to hold: one or two
#: sentences, never a biography.
MAX_ABOUT_LENGTH = 160

#: The one host a persona's "Learn more" link may point at.
WIKIPEDIA_PREFIX = "https://en.wikipedia.org/wiki/"


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
    #: One or two sentences on what the scientist did, for the "about" card
    #: behind the persona chip (product-owner request, 2026-09-13). Capped
    #: at `MAX_ABOUT_LENGTH` at load time so the card stays a caption.
    about: str
    #: An `https://en.wikipedia.org/wiki/...` address, host-pinned at load
    #: time so a data edit cannot turn the "Learn more" link into a link to
    #: anywhere else. The frontend pins the host again before rendering.
    wikipedia: str


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
        about = entry.get("about")
        if not isinstance(about, str) or not about.strip():
            raise ValueError(
                f"persona {name!r} has no 'about' line. Every entry carries one "
                "or two sentences on what the scientist did, for the chip's card"
            )
        if len(about) > MAX_ABOUT_LENGTH:
            raise ValueError(
                f"persona {name!r} has an 'about' line of {len(about)} characters, "
                f"past the {MAX_ABOUT_LENGTH} the chip's card is designed to hold"
            )
        wikipedia = entry.get("wikipedia")
        if not isinstance(wikipedia, str) or not wikipedia.startswith(WIKIPEDIA_PREFIX):
            raise ValueError(
                f"persona {name!r} has no Wikipedia address under "
                f"{WIKIPEDIA_PREFIX!r}. The link is host-pinned by product decision "
                "so a data edit cannot point a reader anywhere else"
            )
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
                about=about.strip(),
                wikipedia=wikipedia,
            )
        )
    return tuple(personas)


def persona_record(name: str) -> Persona:
    """The curated record behind a name the draw handed out.

    Raises `KeyError` for a name the shipped list does not carry, which
    cannot happen for a name produced by `persona_for_session` in the same
    process, since both read the same cached list.
    """
    for persona in load_persona_list():
        if persona.name == name:
            return persona
    raise KeyError(name)


def persona_record_for_session(*, session_id: str, user_id: str | None) -> Persona:
    """`persona_for_session`, returning the whole record rather than the name.

    The draw itself is unchanged: this looks the drawn name back up, so the
    name a caller has seen for months is exactly the name this returns.
    """
    return persona_record(persona_for_session(session_id=session_id, user_id=user_id))


def _rendezvous_score(identity: str, name: str) -> bytes:
    """One candidate's score for one identity.

    The NUL separator is load-bearing rather than decorative: without a
    separator, identity "ab" with name "c" and identity "a" with name "bc"
    would hash the same bytes, and a persona name can never contain a NUL
    because the curated file is JSON text.
    """
    return hashlib.sha256(
        identity.encode("utf-8") + b"\x00" + name.encode("utf-8")
    ).digest()


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

    NOT a modulus over the list length, and that is finding F-4.5-J-10's fix
    rather than a style choice. `int.from_bytes(digest) % len(personas)`
    changes its answer for essentially every identity the moment
    `len(personas)` changes, so growing the curated file from 32 entries
    toward the 100 the mechanism is sized for would rebind every existing
    account to a different scientist. That is a breach of the 2026-08-20
    product decision, whose whole point was that a later extension is a DATA
    change: a data change that silently rewrites every user's identity is a
    code change wearing a data change's clothes.

    The draw is instead a highest-random-weight (rendezvous) selection: score
    every candidate with `sha256(identity || NUL || name)` and take the
    largest score. Three properties follow, and the tests in
    `tests/.../core/test_persona.py` pin all three:

        ADDING a name moves an identity only if that identity's score for
        the NEW name beats its current best. An identity that moves
        therefore moves TO the newly added scientist, never from one
        pre-existing scientist to another pre-existing one. Some movement is
        unavoidable, since a name nobody is ever drawn for would be dead
        weight in the file; what the old modulus did, and this does not, is
        reshuffle identities between names that both already existed.

        REORDERING the file changes nothing at all, because the score is
        keyed on the name and never on the position.

        The distribution stays even, because SHA-256 over distinct inputs is
        uniform and the maximum of N independent uniform scores is equally
        likely to fall on any of the N candidates.

    Ties are broken on the name, so two candidates that somehow produced an
    identical 32-byte score would still resolve deterministically rather
    than depending on iteration order.
    """
    identity = user_id or session_id
    personas = load_persona_list()
    best_name = personas[0].name
    best_score = _rendezvous_score(identity, best_name)
    for persona in personas[1:]:
        score = _rendezvous_score(identity, persona.name)
        if score > best_score or (score == best_score and persona.name < best_name):
            best_score = score
            best_name = persona.name
    return best_name


#: One helper per data layer, UI fix set 8 (R30): the lead hands the question
#: to three scientists, one for the knowledge graph, one for live NCBI
#: records, one for literature and trials.
HELPER_COUNT = 3


def draw_helpers(
    *,
    lead_name: str,
    count: int = HELPER_COUNT,
    rng: random.Random | None = None,
) -> tuple[Persona, ...]:
    """Draw `count` distinct helper scientists, never the lead, at random.

    UI fix set 8, items 8.2 and 8.4 (product-owner decision U5, 2026-09-12):
    the three helpers are picked at random on EVERY run, unlike the lead,
    which `persona_for_session` keeps stable for the session or the
    account. Two visits may therefore show different helpers over the same
    answer, and that is the requirement rather than a defect: the helpers
    are a label on the progress screen and nothing else.

    The lead is excluded by NAME, so the same scientist can never appear
    as both the coordinator and one of the people it hands off to. The
    draw is `random.sample` over the curated list minus the lead, so the
    `count` names are distinct by construction.

    `rng` exists for tests: a seeded `random.Random` makes the draw
    reproducible, and the default is `random.SystemRandom()`, which is the
    OS entropy source and cannot be seeded, because a helper list that
    repeated per process restart would read as a bug on the product
    owner's screen. Presentation only, so cryptographic strength is not
    the point; unpredictability across restarts is.

    Raises `ValueError` if the list minus the lead holds fewer than
    `count` names, which the shipped 32-entry list cannot reach; stated
    rather than silently returning fewer, since a caller assigning one
    helper per layer would otherwise index past the end.
    """
    candidates = [persona for persona in load_persona_list() if persona.name != lead_name]
    if len(candidates) < count:
        raise ValueError(
            f"the persona list holds {len(candidates)} names besides the lead "
            f"{lead_name!r}, fewer than the {count} helpers a run hands off to"
        )
    chooser = rng if rng is not None else random.SystemRandom()
    return tuple(chooser.sample(candidates, count))


__all__ = [
    "HELPER_COUNT",
    "MAX_PERSONAS",
    "Persona",
    "draw_helpers",
    "load_persona_list",
    "persona_for_session",
]
