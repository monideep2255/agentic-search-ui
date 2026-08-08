"""The premise gate for build phase 3.3's `litvar2_lookup`: does it tell the
truth about what LitVar2 actually returns?

`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory and
blocking for this tool phase. Written first and watched failing before any of
`litvar2_lookup` exists.

## Why this gate needed no fixture authored from documentation

Every constant below was read from the real LitVar2 API on 2026-08-08
(`tracker/phase_3.3.md`'s pre-build probes), not guessed from Section 6.5's
plain-English field list. One design-time finding came directly out of doing
so, F-3.3-03: rs334's real `data_clinical_significance` includes
`"conflicting-interpretations-of-pathogenicity"`, 44 characters, against the
locked output schema's 30-character item cap, the same class of finding
build phase 3.2 made for `ncbi_dbsnp`'s own (also too-tight, there 40-char)
`clinical_significance` cap. Case 3 pins withhold-not-truncate as this
tool's real behavior on real data, not a hoped-for design decision: a
truncated `"conflicting-interpretations-of"` looks like a real, different,
shorter ClinVar term, exactly the failure phase 3.2's F-3.2-A-01 shipped
once already on a sibling tool.

## The encoding trap, made into an assertion rather than a comment

`Tool_implementation_mechanics.md`'s "unencoded litvar_id" trap: the id
format `litvar@rs334##` contains `@` and `#`, neither URL-safe. Sending it
unencoded does not crash; LitVar2 silently treats the string up to `#` as
the whole id and 400s with a WRONG "not found" message
(`{"detail": "Variant not found: litvar@rs334"}`, missing the `##` suffix
entirely), live-confirmed 2026-08-08. A tool that forgot to encode would
report a real, resolvable variant as not found, a wrong-answer risk stated
in prose is easy to miss. Case 5 asserts the tool succeeds on a real id
regardless of whether the CALLER already encoded it, proving the tool does
its own encoding rather than trusting the caller's.

## The arms

Two modes, both genuinely status-coded (unlike PubTator3's
`entity_lookup`/`annotate_publications` split, LitVar2 uses the same
HTTP-status convention on both of its own modes, confirmed live):

    variant_search: ok (a real match), empty (a genuine no-match, `[]` with
    HTTP 200).

    publications_lookup: ok (a real variant id, `pmids` capped at
    `maxItems: 50` with an honest `total_pmids`), error (a genuinely
    not-found variant id, the documented HTTP 400 `{"detail": ...}` shape).

The zero-PMID publications case named in `Tool_implementation_mechanics.md`'s
"Open verification gaps" is NOT given a case here: the pre-build probe could
not construct one (every `litvar_id` `variant_search` can return already has
at least one linked publication, since LitVar2's own corpus is built from
literature mining), so this gate does not assert unverified behavior. See
the coverage statement below.

## Running it

    RUN_PREMISE_GATE=1 python -m pytest \\
        tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py -v

This tool needs no API key (Section 6.5: "no API key"); gates only on
opt-in and live network reach, same as `pubtator_annotate`'s gate.

## Coverage, stated per goal-contracts.md ("a verify surface must state its
own coverage")

Exercises: both modes, the `ok`/`empty` split for `variant_search`, the
`ok`/`error` split for `publications_lookup`, the `maxItems: 50` truncation
with an honest `total_pmids`, the F-3.3-03 withhold-not-truncate path, and
the encoding trap as a behavioral assertion. Case 3 also asserts the
withheld note's INDEX matches the withheld term's actual position in
`variant_matches`, not merely that the note contains the right term
(F-3.3-J-03). Does NOT exercise: the zero-PMID `publications_lookup` case
(structurally unreachable via this tool's own two-step flow, per the
pre-build probe; documented here rather than silently absent); concurrent
load against the new `"litvar2"` rate-limit family's actual 5 req/s pacing
(a `RateLimiter` unit test's job); a response withholding MORE THAN ONE
field in the same call, judge round 1's F-3.3-J-01 window (`fields_withheld`
exceeding its own 20-item schema cap; live rs334 data never produces more
than a handful of withheld notes, so this gate cannot reach that shape
without a scripted response, which is `test_litvar2_lookup.py`'s job, not
this live gate's); a `variant_search` response where every row fails to
parse, judge round 1's F-3.3-J-02 window (live LitVar2 has no known query
that returns a non-empty array of all-unparseable rows, so this gate
cannot reach that shape either; covered by a mocked case in
`test_litvar2_lookup.py` instead).

Depends on:
    - system_03_search_agent.tools.litvar2_lookup (does not exist yet, by
      design)
    - system_03_search_agent.tools.litvar2_lookup_schemas (same)
    - Network reach to www.ncbi.nlm.nih.gov

Writes:
    - Nothing.
"""

from __future__ import annotations

import os
import socket
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Live ground truth, read from the real API on 2026-08-08
# (tracker/phase_3.3.md's pre-build probes), not guessed from documentation.
# ---------------------------------------------------------------------------

RS334 = "rs334"
RS334_GENE = "HBB"
RS334_LITVAR_ID = "litvar@rs334##"
RS334_LITVAR_ID_UNENCODED_WOULD_BE_WRONG = "litvar@rs334"  # what a missed-encoding bug sends
RS334_LONG_CLINICAL_TERM = "conflicting-interpretations-of-pathogenicity"  # 44 chars, live-confirmed

NO_MATCH_QUERY = "zzznotavariant123"

NONEXISTENT_LITVAR_ID = "litvar@rs99999999999##"


def _opted_in() -> bool:
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {"1", "true", "yes"}


def _host_is_reachable() -> bool:
    try:
        with socket.create_connection(("www.ncbi.nlm.nih.gov", 443), timeout=10):
            return True
    except OSError:
        return False


premise_gate = pytest.mark.skipif(
    not (_opted_in() and _host_is_reachable()),
    reason=(
        "set RUN_PREMISE_GATE=1 to run the litvar2_lookup premise gate. "
        "It needs live network reach to www.ncbi.nlm.nih.gov. No API key "
        "required (Section 6.5)."
    ),
)


async def _run(payload: dict[str, Any]) -> Any:
    """Call the tool the way the Act step will, once it is wired in.

    Imported inside the function on purpose: until `litvar2_lookup` exists
    this raises ImportError per case, giving a readable per-case failure
    count instead of one collection error.
    """
    from system_03_search_agent.tools.litvar2_lookup import litvar2_lookup
    from system_03_search_agent.tools.litvar2_lookup_schemas import Litvar2LookupInput

    return await litvar2_lookup(Litvar2LookupInput(**payload))


# ===========================================================================
# ARM 1: variant_search, ok / empty.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_01_variant_search_resolves_rs334() -> None:
    """Case 1. The full happy path, asserted on meaning."""
    output = await _run({"mode": "variant_search", "query": RS334})

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    assert output.variant_matches, "expected at least one variant match"
    rs334_matches = [m for m in output.variant_matches if m.rsid == RS334]
    assert rs334_matches, f"expected rs334 among the matches, got {[m.rsid for m in output.variant_matches]!r}"
    assert RS334_GENE in rs334_matches[0].gene, (
        f"expected gene {RS334_GENE!r} among {rs334_matches[0].gene!r}"
    )
    assert rs334_matches[0].litvar_id == RS334_LITVAR_ID


@premise_gate
@pytest.mark.asyncio
async def test_02_variant_search_no_match_is_empty_not_fabricated() -> None:
    """Case 2. A genuine no-match is `status: "empty"`, never invented content."""
    output = await _run({"mode": "variant_search", "query": NO_MATCH_QUERY})

    assert output.status == "empty", f"expected empty, got {output.status}: {output.error}"
    assert not output.variant_matches, (
        f"expected no variant_matches on a no-match query, got {output.variant_matches!r}"
    )


@premise_gate
@pytest.mark.asyncio
async def test_03_long_clinical_significance_term_is_withheld_not_truncated() -> None:
    """Case 3, F-3.3-03. rs334's real data carries a 44-char clinical
    significance term against a locked 30-char item cap. The tool must drop
    the over-length item and name the drop in `fields_withheld`, never ship
    a truncated-but-plausible-looking shorter term (phase 3.2's F-3.2-A-01
    failure mode, on a second tool, confirmed live before this ticket was
    ever coded rather than found by an adversary after).
    """
    output = await _run({"mode": "variant_search", "query": RS334})

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    rs334_indexed = [
        (i, m) for i, m in enumerate(output.variant_matches) if m.rsid == RS334
    ]
    assert rs334_indexed, "expected rs334 among the matches"
    rs334_index, rs334_match = rs334_indexed[0]
    terms = rs334_match.clinical_significance or []
    for term in terms:
        assert len(term) <= 30, (
            f"F-3.3-03: {term!r} ({len(term)} chars) exceeds the 30-char cap "
            f"and was not withheld; a value this long that made it through "
            f"is either truncated (wrong) or the cap was silently widened "
            f"(a spec change no ticket authorized)"
        )
        assert not RS334_LONG_CLINICAL_TERM.startswith(term) or term == RS334_LONG_CLINICAL_TERM, (
            f"{term!r} looks like a truncated prefix of "
            f"{RS334_LONG_CLINICAL_TERM!r} rather than a withheld or "
            f"genuinely short term"
        )
    assert any(RS334_LONG_CLINICAL_TERM in field for field in (output.fields_withheld or [])), (
        f"F-3.3-03: expected the over-length term to be named in "
        f"fields_withheld, got {output.fields_withheld!r}"
    )
    # F-3.3-J-03: the note must key to rs334's own OUTPUT position in
    # variant_matches (whatever it actually is, since other matches may
    # sort before it), never an assumed or raw-response index. A note
    # naming the wrong index would silently point a caller at some other
    # match's data.
    expected_prefix = f"variant_matches[{rs334_index}].clinical_significance"
    matching_notes = [
        note
        for note in (output.fields_withheld or [])
        if RS334_LONG_CLINICAL_TERM in note
    ]
    assert matching_notes, "expected at least one fields_withheld note naming the long term"
    assert all(note.startswith(expected_prefix) for note in matching_notes), (
        f"F-3.3-J-03: expected the withheld note to key to rs334's actual "
        f"output index ({rs334_index}), got {matching_notes!r}"
    )


# ===========================================================================
# ARM 2: publications_lookup, ok / error.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_04_publications_lookup_truncates_with_an_honest_total() -> None:
    """Case 4. `Tool_implementation_mechanics.md`'s inlining trap: rs334
    carries 500+ real PMIDs. `pmids` must cap at 50 with `total_pmids`
    carrying the true count, never inlined in full and never silently
    reported as exactly 50.
    """
    output = await _run({"mode": "publications_lookup", "litvar_id": RS334_LITVAR_ID})

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    assert len(output.pmids) <= 50, f"expected pmids capped at 50, got {len(output.pmids)}"
    assert output.total_pmids > 50, (
        f"rs334 is live-confirmed to carry 500+ PMIDs; expected total_pmids "
        f"> 50, got {output.total_pmids}"
    )
    assert output.total_pmids != len(output.pmids), (
        "total_pmids must reflect the TRUE count, not merely echo the "
        "truncated list length"
    )


@premise_gate
@pytest.mark.asyncio
async def test_05_tool_encodes_the_litvar_id_regardless_of_caller_input() -> None:
    """Case 5. The encoding trap as a live assertion, not a code comment.

    Passing the id in its natural, unencoded form (the shape any caller
    would reasonably construct from a `variant_search` result's own
    `litvar_id` field) must still resolve correctly. If the tool trusted the
    caller to have already encoded it, this call would 400 with the wrong
    "Variant not found: litvar@rs334" message, live-confirmed to be what
    LitVar2 itself returns for the truncated, unencoded form.
    """
    output = await _run(
        {"mode": "publications_lookup", "litvar_id": RS334_LITVAR_ID_UNENCODED_WOULD_BE_WRONG + "##"}
    )

    assert output.status == "ok", (
        f"expected the tool to encode {RS334_LITVAR_ID_UNENCODED_WOULD_BE_WRONG}## "
        f"itself and resolve it correctly, got {output.status}: {output.error}"
    )
    assert output.pmids, "expected a non-empty pmids list for a correctly-encoded rs334 lookup"


@premise_gate
@pytest.mark.asyncio
async def test_06_nonexistent_variant_id_is_error_not_fabricated() -> None:
    """Case 6. The documented not-found shape: HTTP 400, `{"detail": ...}`."""
    output = await _run({"mode": "publications_lookup", "litvar_id": NONEXISTENT_LITVAR_ID})

    assert output.status == "error", f"expected error, got {output.status}"
    assert output.error, "expected a non-empty error message"
    assert not output.pmids, f"expected no pmids on an error, got {output.pmids!r}"
