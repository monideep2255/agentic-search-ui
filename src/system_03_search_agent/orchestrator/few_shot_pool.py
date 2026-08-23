"""The few-shot routing pool: loaded once per process, never per request.

Depends on:
    - system_03_search_agent.feedback.promotion (`FewShotExample`, the
      Pydantic model Section 17 fixes the shape of, reused rather than
      redeclared; `DEFAULT_POOL_PATH`, the same path build phase 4.6's
      promotion path already writes to)

Reads:
    - orchestrator/few_shot_examples.json, exactly once per process
      (`.claude/rules/prompt-cache-discipline.md` obligation 3: "never
      read the pool from a live database on every request... a changing
      prefix source, even one that happens to return the same content, is
      a liveness risk the caching design does not tolerate"). Never a
      per-request read, never a database read.

Writes:
    - orchestrator/few_shot_examples.json, via `append_example`, the one
      atomic, lock-serialized writer implementation this file and
      `feedback.promotion._append_pool_entry` both call through
      (F-4.6-A-08, T-4.7-03).

Build phase 4.7 (T-4.7-02, T-4.7-03). `tracker/phase_4.7.md`,
`tests/system_03_search_agent/core/test_cq_routing_premise.py` (arms P8,
P9, P11) are this module's acceptance criteria and premise gate.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from pathlib import Path
from typing import Any

from system_03_search_agent.feedback.promotion import DEFAULT_POOL_PATH, FewShotExample

#: Section 17: "It lives as a versioned file in the repo... loaded once at
#: process start, not a live table read on every request." A module-level
#: cache, not a request-scoped one, is the whole point: production code
#: calls `load_pool()` and gets the same in-memory list for the life of the
#: process. `reset_pool_cache()` below exists for tests only; production
#: code never calls it, since that would reintroduce the per-request-read
#: liveness risk prompt-cache-discipline.md obligation 3 forbids.
_POOL_CACHE: list[FewShotExample] | None = None

#: Guards `_POOL_CACHE` against two threads racing `load_pool()`'s
#: check-then-populate on the very first call in a process (an ordinary
#: read-write race on a module global, not F-4.6-A-08's file-corruption
#: concern, which `append_example`'s file lock below owns separately).
_POOL_CACHE_LOCK = threading.Lock()

#: The only schema version this loader understands. `few_shot_examples.json`
#: declares its own `schema_version`; a value other than this one is refused
#: rather than read optimistically (T-4.7-02: "Rejects an unknown
#: schema_version").
_SUPPORTED_SCHEMA_VERSION = 1

#: A promoted entry (`feedback.promotion.promote_candidate`) carries this
#: bookkeeping field alongside Section 17's `few_shot_example` shape,
#: tagging it back to the `cq_candidates` row that produced it ("tagged
#: with the cq_candidates.id for traceability back to its source
#: interactions", Section 17). It is stripped before validating an entry
#: against `FewShotExample`, whose `extra="forbid"` config exists to catch
#: a field Section 17's payload shape does not name, not to reject this
#: repository's own provenance tag on every promoted row.
_ENTRY_BOOKKEEPING_FIELDS: tuple[str, ...] = ("cq_candidate_id",)


def _validate_entry(raw_entry: dict[str, Any], *, index: int, path: Path) -> FewShotExample:
    """Validate one pool entry against `FewShotExample`, bookkeeping fields stripped first.

    Raises `ValueError` naming the file and the entry's index on a
    malformed entry, per T-4.7-02's "fail loudly at startup on a malformed
    file rather than degrading to an empty pool, since an empty pool is
    silently the old behaviour".
    """
    payload = {
        key: value for key, value in raw_entry.items() if key not in _ENTRY_BOOKKEEPING_FIELDS
    }
    try:
        return FewShotExample.model_validate(payload)
    except Exception as exc:
        raise ValueError(
            f"{path}: examples[{index}] does not match Section 17's "
            f"`few_shot_example` shape: {exc}. The pool file is malformed; "
            "it is never silently treated as an empty pool, since an empty "
            "pool is indistinguishable from the pre-build-phase-4.7 "
            "unwired state"
        ) from exc


def _load_from_disk(path: Path) -> list[FewShotExample]:
    """Read, parse, and schema-validate the pool file. No caching here; `load_pool` owns that."""
    if not path.exists():
        raise FileNotFoundError(
            f"the few-shot pool file does not exist at {path}. Section 17's "
            "seven-question seed pool must be present before this process "
            "starts; a missing file is never treated as an empty pool"
        )

    raw_text = path.read_text(encoding="utf-8")
    try:
        document = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} is not valid JSON: {exc}. Refusing to start with a "
            "pool file that failed to parse rather than silently falling "
            "back to an empty pool"
        ) from exc

    if not isinstance(document, dict):
        raise TypeError(
            f"{path} must be a JSON object with 'schema_version' and "
            f"'examples' keys, got a top-level {type(document).__name__}"
        )

    schema_version = document.get("schema_version")
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"{path} declares schema_version={schema_version!r}, but this "
            f"loader only understands schema_version={_SUPPORTED_SCHEMA_VERSION!r}. "
            "An unrecognized schema version is refused rather than read "
            "optimistically: a silent format drift would inject whatever "
            "the new shape happens to contain into the model's stable "
            "prefix with no validation at all"
        )

    raw_examples = document.get("examples")
    if not isinstance(raw_examples, list):
        raise TypeError(
            f"{path}['examples'] must be a JSON array, got "
            f"{type(raw_examples).__name__}"
        )

    return [
        _validate_entry(raw_entry, index=index, path=path)
        for index, raw_entry in enumerate(raw_examples)
    ]


def load_pool() -> list[FewShotExample]:
    """Return the few-shot pool, reading `DEFAULT_POOL_PATH` at most once per process.

    The first call in a process reads and schema-validates the file, holds
    the result in a module-level cache, and returns it. Every later call in
    the same process returns the cached list without touching the
    filesystem again. This is the exact "loaded once at process start" rule
    prompt-cache-discipline.md's obligation 3 states, enforced rather than
    merely documented: `tests/system_03_search_agent/core/
    test_cq_routing_premise.py::test_p9_the_pool_is_read_from_disk_once_per_process`
    counts `Path.read_text` calls against this file across six `load_pool()`
    calls and asserts exactly one.

    Raises whatever `_load_from_disk` raised on the first call (a missing
    file, invalid JSON, an unknown `schema_version`, or a malformed entry).
    The failure is never cached as "the pool is empty": the next call
    retries the read rather than remembering a false negative.
    """
    global _POOL_CACHE
    with _POOL_CACHE_LOCK:
        if _POOL_CACHE is None:
            _POOL_CACHE = _load_from_disk(DEFAULT_POOL_PATH)
        return _POOL_CACHE


def reset_pool_cache() -> None:
    """Test-only: forget the cached pool so the next `load_pool()` call re-reads the file.

    Production code never calls this. A live hot reload mid-session is
    exactly what prompt-cache-discipline.md's obligation 3 forbids ("never
    a live hot reload"); this exists solely so
    `test_p9_the_pool_is_read_from_disk_once_per_process` can start from a
    known-empty cache regardless of what ran before it in the same test
    session.
    """
    global _POOL_CACHE
    with _POOL_CACHE_LOCK:
        _POOL_CACHE = None


def _default_document() -> dict[str, Any]:
    return {"schema_version": _SUPPORTED_SCHEMA_VERSION, "examples": []}


def append_example(pool_path: Path, entry: dict[str, Any]) -> None:
    """Append one `few_shot_example` entry, serialized against concurrent writers.

    F-4.6-A-08 (filed against build phase 4.6, closed here because this is
    the phase that first reads this file at process start, so a corrupted
    file becomes a startup failure rather than a silently ignored one): two
    operators or two shells running the promotion path at once could
    previously interleave a bare read-modify-write and either lose an
    entry or leave the file as invalid JSON.

    This is the single writer implementation for this file.
    `feedback.promotion._append_pool_entry` delegates here rather than
    keeping a second, independently-drifting copy of the same logic.

    Two mechanisms together close the race, not one:

    - An advisory lock (`fcntl.flock`, `LOCK_EX`) on a sibling `.lock` file,
      held for the full read-modify-write-replace sequence, so a second
      writer blocks until the first finishes rather than interleaving with
      it. The lock lives on a sibling path rather than `pool_path` itself
      so a plain reader opening `pool_path` (`load_pool`, or a human eyeballing
      the file) is never blocked by a writer's lock, and the lock file's own
      lifecycle never touches the content a reader sees.
    - An atomic replace (`os.replace`, POSIX-atomic within the same
      directory): the new document is written to a temp file first, then
      renamed over the target in one step. A reader can only ever observe
      the complete old file or the complete new one, never a partially
      written one.

    Dedup: an incoming `entry` carrying `cq_candidate_id` is treated as
    already present when an existing entry in the file shares that id,
    which is the idempotency `feedback.promotion.promote_candidate` relies
    on (running promotion twice on the same candidate must not append
    twice). An entry with no `cq_candidate_id` (a hand-seeded example, or
    the shape `test_p11_two_concurrent_promotions_cannot_corrupt_the_pool`
    uses) is never deduped against another entry that also has none: two
    absent ids are not evidence of the same candidate, and treating
    `None == None` as a match would silently drop the second of two
    genuinely distinct hand-authored entries, which is exactly the data
    loss this function exists to prevent.

    Args:
        pool_path: The pool file to append to. Created, with the default
            empty document, if it does not exist yet.
        entry: One `few_shot_example`-shaped dict, already validated by the
            caller (`feedback.promotion.promote_candidate` validates via
            `FewShotExample` before calling this; a raw dict shape is
            accepted here rather than re-requiring a `FewShotExample`
            instance so this function has no import-time dependency on any
            one caller's validation step).
    """
    pool_path = Path(pool_path)
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = pool_path.with_name(pool_path.name + ".lock")

    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            if pool_path.exists():
                document = json.loads(pool_path.read_text(encoding="utf-8"))
            else:
                document = _default_document()
            document.setdefault("examples", [])

            candidate_id = entry.get("cq_candidate_id")
            already_present = candidate_id is not None and any(
                existing.get("cq_candidate_id") == candidate_id
                for existing in document["examples"]
            )
            if already_present:
                return

            document["examples"].append(entry)

            # Same directory as the target, so `os.replace` is a same-
            # filesystem rename (POSIX-atomic) rather than a cross-device
            # copy. The pid and thread id in the name keep two concurrent
            # writers (already serialized by the lock above, but this also
            # protects a stray leftover temp file from a prior crashed
            # writer) from ever colliding on the same temp path.
            tmp_path = pool_path.with_name(
                f"{pool_path.name}.tmp-{os.getpid()}-{threading.get_ident()}"
            )
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2)
                handle.write("\n")
            os.replace(tmp_path, pool_path)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
