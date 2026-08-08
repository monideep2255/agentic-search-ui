"""The premise gate for build phase 3.2: does `ncbi_dbsnp` tell the truth
about what NCBI Variation Services and dbSNP ESummary actually return?

`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory and
blocking for this tool phase, the same as build phase 3.1's own gate. It is
written first and watched failing before any of `ncbi_dbsnp` exists.

## Why this gate needed no fixture authored from documentation

Build phase 3.1's adversary round (LEARNINGS.md row 60) found two criticals
that shipped past review because their test fixtures were hand-written from a
reading of NCBI's documentation rather than captured from a live response.
Applying that lesson before any tool code exists rather than after: every
constant below was read from the real endpoint, and two design-time findings
came directly out of doing so (see F-3.2-01 and F-3.2-02 in
`tracker/phase_3.2.md`, both about fields whose live shape does not match
what a reader would guess from Section 6.3's plain-English field list):

    dbSNP ESummary's `global_mafs[].freq` is a compound string
    (`"A=0.027356/137"`), not the `{population, allele, frequency}` triple
    the output schema names. Case 1 and case 3 pin the PARSED shape, not the
    raw one.

    `clinical_significance` and `fxn_class` are comma-separated strings in the
    raw response, not arrays. Case 3 pins that the tool actually splits them.

## The arms, and why they are not 3.1's arms

This tool makes the same repeated decision every `ncbi_efetch` action makes,
given a response, is this `ok`, `empty`, or `error`, but the space of
reachable answers is narrower here. Pre-build live probing (documented in
`tracker/phase_3.2.md`) found that Variation Services does NOT have a
200-with-empty-body convention the way E-utilities does: a nonexistent rsid
returns a genuine HTTP 404, and a malformed SPDI or HGVS expression returns a
genuine HTTP 400, both with a `{"error": {"code", "message"}}` body. So the
open verification gap Section 6.3 and `Tool_implementation_mechanics.md` both
flag (`ncbi_dbsnp`'s error behavior was never live-verified before this
phase) is resolved here, live, rather than assumed: every malformed-input case
below is `error`, and there is no reachable `empty` case on this tool's
Variation Services calls. `empty` versus `ok` is decided entirely by whether
`global_mafs` came back non-empty, which Section 6.3 line 1074 states
explicitly is never itself a failure.

## The sequential-ordering trap, made into an assertion rather than a comment

Section 6.3 line 1076 and `Tool_implementation_mechanics.md` both say the
dbSNP ESummary clinical fetch must run AFTER Variation Services normalization
completes, keyed on the CANONICAL id, never the caller's raw input. Stated as
prose, that property is easy to satisfy by accident (a tool that always keys
on the raw input passes as long as the raw input already happens to equal the
canonical one) and easy to break silently. Case 8 makes it a live assertion:
`rs3168321` is a real, obsolete rsid that merged into the current `rs334`
(confirmed live, `refsnp/3168321.dbsnp1_merges` and `refsnp/334`'s own merge
history both show it). A tool that fetches ESummary on the raw input gets
`snp_id: 334` back from `esummary.fcgi?id=3168321` (NCBI's own ESummary
silently redirects merged ids to their current record), which would make this
case pass even on the wrong implementation. What actually distinguishes a
correct implementation is `rsid` in the OUTPUT: a tool keyed on the caller's
raw input reports `rs3168321`; a tool that normalizes first and keys the
clinical fetch on the result reports `rs334`, the current canonical id. This
is the same near-miss discipline build phase 3.1's premise gate used for its
own ordering-sensitive cases, applied to a case where NCBI's own leniency
would otherwise mask the defect.

## What this gate needs, and the one respect in which it is stronger than 3.1's

Needs: network reach to `api.ncbi.nlm.nih.gov` (Variation Services) AND
`eutils.ncbi.nlm.nih.gov` (dbSNP ESummary), and `NCBI_API_KEY` for the
authenticated E-utilities pool.

Unlike build phase 3.1's gate, which skips its own end-to-end case 16 because
the AGE graph tunnel cannot be opened from this environment, this tool never
touches Layer 1. Both APIs it calls are plain public HTTPS, already confirmed
reachable from here during pre-build probing. So this gate has no
tunnel-gated skip anywhere in it; every case below either runs or the whole
gate is skipped on its single opt-in flag, never a partial run.

## Coverage: what this gate exercises and what it deliberately omits

`.claude/rules/goal-contracts.md` requires this statement.

Exercised: all three `query_type` values (`rsid` cases 1/2/3/4/8, `spdi` case
5, `hgvs` cases 6/7), both `ok` and `error`, the `include_clinical=True`
default path, the `global_mafs` empty-is-ok rule, the comma-split parsing
trap, and the normalize-before-clinical-fetch ordering trap.

Deliberately NOT exercised:

- `all_equivalent_contextual` (multiple equivalent contextual alleles for one
  variant). No case here needs allele-equivalence resolution, and Section 6.3
  does not name it as required for a correct answer to any of the seven v1
  must-pass moat questions.
- `include_clinical=False`. The output shape when the clinical fetch is
  skipped entirely is a real code path with no live case pinning it here.
- The `variation` rate-limit family's actual ~1 req/s throttling under
  concurrent load. This gate runs each case sequentially against the live
  API; T-3.2-02's own unit tests on `RateLimiter` are where contention is
  covered, not here.
- An rsid with more than one equivalent SPDI representation reaching
  `all_equivalent_contextual` disagreement. Not constructed; no ground truth
  pinned for it.
- Whether `ncbi_dbsnp` is dispatched from `act_node` as an answer-bearing
  tool. Same carried scope decision as `ncbi_efetch`'s F-3.1-04, tracked to
  T-3.1-28 and not reopened here.
- J-01 (2026-08-08): the truncation/overflow-refusal behavior fixed for
  F-3.2-A-01/A-14 (a value that would need truncation to fit its schema cap
  now fails the whole call closed rather than shipping under `status: "ok"`)
  and the `allele_role` attribution fixed for F-3.2-A-03 are BOTH still
  NOT exercised live by this gate. Neither rs334 nor any other ground-truth
  rsid pinned here happens to carry a field that overflows its cap, and
  constructing a live case that genuinely does (a real rsid whose real
  ESummary data happens to overflow a cap, not a hand-crafted oversized
  value, which this gate's own discipline forbids fabricating) was not
  attempted in this fix pass. Both are covered by mocked, non-live cases in
  `test_ncbi_dbsnp.py` instead. This is the SAME shape of gap J-01 itself
  named: a gate whose coverage statement, until this edit, did not disclose
  it. Left open rather than closed with a fabricated live case.

## Case 7's assertion, corrected for the F-3.2-A-06 fix (2026-08-08)

F-3.2-A-06's fix (see `ncbi_dbsnp.py`'s module docstring) changes a
successful `spdi`/`hgvs` normalization from `status: "ok"` to `status:
"empty"`, since neither query_type ever resolves a citable rsid and an
uncited `"ok"` is exactly the AI-answer-grounding-gate violation that
finding exists to close. The fix builder correctly left case 7's assertion
untouched, out of its authorized scope, and flagged the mismatch in this
docstring and the test's own docstring for the lead to correct once
independently reproduced live. Reproduced live 2026-08-08 (7 of 8 passing,
case 7 failing in exactly the documented, expected direction), then
corrected: case 7 now asserts `status == "empty"` and `source_url is None`,
matching the equivalent update already made to `test_ncbi_dbsnp.py`'s mocked
spdi/hgvs cases. This is a strengthening of the gate to match a deliberately
and correctly changed behavior, not a weakening; per `.claude/rules/goal-
contracts.md`, adding or correcting a check to reflect a real fix is allowed,
only weakening one to make a bug disappear is forbidden.

## A known weakness of this gate, stated rather than hidden

Case 2 (empty `global_mafs`) asserts `population_frequencies == []` and
`status == "ok"`. A tool hardcoded to always return an empty list passes this
case vacuously. It is meaningful only in combination with case 1, which
requires a NON-empty, correctly-parsed list on a different real rsid. Neither
arm is sound read alone, the same caveat build phase 3.1's gate states for its
own `empty` cases.

## Running it

    RUN_PREMISE_GATE=1 python -m pytest \
        tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py -v

Same opt-in convention as every prior gate: dormant by deliberate choice, not
because a resource happened to be unavailable. This gate spends no model
money but does draw from Variation Services' roughly 1 req/s shared public
pool, which is the tightest rate constraint of any tool in the roster
(`.claude/rules/tool-call-budgets.md`), so it is not run implicitly by the
default test collection.

Depends on:
    - system_03_search_agent.tools.ncbi_dbsnp (does not exist yet, by design)
    - system_03_search_agent.tools.ncbi_dbsnp_schemas (same)
    - NCBI_API_KEY, for the authenticated E-utilities pool
    - Network reach to api.ncbi.nlm.nih.gov and eutils.ncbi.nlm.nih.gov
    - RUN_PREMISE_GATE=1, the explicit opt-in

Writes:
    - Nothing.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_env_explicitly() -> None:
    """Populate NCBI_API_KEY from .env (F-2.1-04's fix, restated per-gate).

    Relying on an import-time dotenv side effect from a third-party package is
    order-dependent and has broken once already in this repo.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _api_key_is_configured() -> bool:
    _load_env_explicitly()
    return bool(os.environ.get("NCBI_API_KEY"))


_OPT_IN_VAR = "RUN_PREMISE_GATE"


def _opted_in() -> bool:
    _load_env_explicitly()
    return os.environ.get(_OPT_IN_VAR, "").strip().lower() in {"1", "true", "yes"}


def _hosts_are_reachable() -> bool:
    """Probe BOTH transports this tool depends on, not just one.

    LEARNINGS.md row 58 records a dispatch that trusted a green pre-flight
    against the wrong host entirely. This tool genuinely needs two different
    NCBI hosts to answer a single call (Variation Services, then E-utilities),
    so a probe of only one would report "ready" while the other half of every
    case fails.
    """
    for host in ("api.ncbi.nlm.nih.gov", "eutils.ncbi.nlm.nih.gov"):
        try:
            with socket.create_connection((host, 443), timeout=10):
                continue
        except OSError:
            return False
    return True


premise_gate = pytest.mark.skipif(
    not (_api_key_is_configured() and _opted_in() and _hosts_are_reachable()),
    reason=(
        f"set {_OPT_IN_VAR}=1 to run the ncbi_dbsnp premise gate. It needs "
        "NCBI_API_KEY and live network reach to BOTH api.ncbi.nlm.nih.gov "
        "(Variation Services) and eutils.ncbi.nlm.nih.gov (dbSNP ESummary)."
    ),
)


# ---------------------------------------------------------------------------
# Ground truth, read from the live endpoints on 2026-08-08.
#
# WHEN ONE OF THESE MOVES: re-verify against the endpoint and update the
# constant here, with a new date. Never relax an assertion to make a moved
# value pass; a moved value is news about NCBI, a relaxed assertion is a gate
# that has stopped measuring anything (`.claude/rules/goal-contracts.md`).
# ---------------------------------------------------------------------------

# rs334, the HBB missense variant (HbS, sickle-cell), already this repo's
# canonical dbSNP example (Section 6.5's LitVar2 spec cites it, 589 PMIDs).
RS334 = "rs334"
RS334_GENE_NAME = "HBB"
RS334_GENE_ID = "3043"
RS334_CHROMOSOME_PREFIX = "NC_000011"  # chromosome 11
# global_mafs, confirmed live 2026-08-08: the "1000Genomes" study entry reads
# freq="A=0.027356/137", i.e. allele "A", frequency 0.027356. A tool that
# parses correctly reports this as a separate {population, allele, frequency}
# triple, not the raw string.
RS334_1000GENOMES_ALLELE = "A"
RS334_1000GENOMES_FREQUENCY = 0.027356
# clinical_significance, raw ESummary value:
# "not-provided,protective,likely-benign,pathogenic,other". A correctly
# splitting tool reports "pathogenic" as one of several distinct entries, not
# as a substring of one blob.
RS334_CLINICAL_SIGNIFICANCE_CONTAINS = "pathogenic"

# A real rsid with a genuine gene linkage but zero population data. Confirmed
# live 2026-08-08: esummary.fcgi?db=snp&id=2141234567 returns global_mafs:
# [] with no other error signal, and refsnp/2141234567 normalizes cleanly.
RS_EMPTY_MAFS = "rs2141234567"
RS_EMPTY_MAFS_GENE_NAME = "IGF1R"
RS_EMPTY_MAFS_GENE_ID = "3480"

# Deliberately nonexistent. Confirmed live 2026-08-08: refsnp/999999999999
# returns HTTP 404, body {"error": {"code": 404, "message": "RefSNP not
# found"}}. Variation Services does NOT emit E-utilities' 200-with-empty-body
# convention; this is the resolved open verification gap.
NONEXISTENT_RSID = "rs999999999999"

# Malformed SPDI. Confirmed live 2026-08-08: HTTP 400, body {"error":
# {"code": 400, "message": "Invalid SPDI: 'not-a-real-spdi'"}}.
MALFORMED_SPDI = "not-a-real-spdi"

# Malformed HGVS. Confirmed live 2026-08-08: HTTP 400.
MALFORMED_HGVS = "not-real-hgvs"

# A real HBB coding change, confirmed live 2026-08-08 against
# /hgvs/{hgvs}/contextuals (the `>` must be percent-encoded per Section 6.3's
# own note; the tool is responsible for that encoding, this constant is the
# unencoded caller-facing form). Response: {"data": {"spdis": [{"seq_id":
# "NM_000518.5", "position": 69, "deleted_sequence": "A",
# "inserted_sequence": "T"}], "input_hgvs_validity": "valid"}}.
REAL_HGVS = "NM_000518.5:c.20A>T"
REAL_HGVS_SEQ_ID = "NM_000518.5"
REAL_HGVS_POSITION = 69

# An OBSOLETE rsid that merged into rs334. Confirmed live 2026-08-08:
# refsnp/3168321 resolves (dbsnp1_merges history), and
# esummary.fcgi?db=snp&id=3168321 returns snp_id: 334, i.e. NCBI's own
# ESummary is lenient about merged ids and answers with the CURRENT record
# regardless of what a tool queries. That leniency is exactly what makes
# case 8 a real test rather than a decorative one: it is not enough for the
# clinical fields to come back correct, since ESummary would return them
# correctly even for a tool that never normalized at all. What distinguishes
# a correct implementation is the OUTPUT's own `rsid` field: it must report
# the canonical "rs334", not the caller's raw "rs3168321", because that value
# can only be produced by a tool that ran Variation Services normalization
# FIRST and threaded its result through, exactly what Section 6.3 line 1076
# requires and what a raw-input-keyed implementation would get wrong.
OBSOLETE_MERGED_RSID = "rs3168321"


def _call_input(payload: dict[str, Any]) -> Any:
    """Build a tool input from the Section 6.3 documented shape.

    Routed through `model_validate` on a plain dict, not a hand-built
    constructor, so this gate pins the SPEC's contract rather than dictating
    the schema module's internal structure, a builder decision.
    """
    from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpInput

    return NcbiDbsnpInput.model_validate(payload)


async def _run(payload: dict[str, Any]) -> Any:
    """Call the tool the way the Act step will, once it is wired in.

    Imported inside the function on purpose: until `ncbi_dbsnp` exists this
    raises ImportError per case, giving a readable per-case failure count
    ("N of 8 failed, all ModuleNotFoundError") instead of one collection
    error that says nothing about how much of the premise is unmet.
    """
    from system_03_search_agent.tools.ncbi_dbsnp import ncbi_dbsnp

    return await ncbi_dbsnp(_call_input(payload))


def _find_population_entry(output: Any, population: str) -> Any:
    for entry in output.population_frequencies or []:
        if entry.population == population:
            return entry
    return None


# ===========================================================================
# ARM 1: ok. Real records come back, and the parsing traps are actually
# closed, not merely believed closed.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_01_rsid_resolves_rs334_with_parsed_clinical_and_population_fields() -> None:
    """Case 1. The full happy path, asserted on MEANING, not shape.

    "A record came back" is the assertion that let build phase 2.1 ship
    twenty-five orthologs. This asserts the specific gene, the specific
    chromosome, and that F-3.2-01's population-frequency parsing trap is
    actually closed: the frequency is a real float, not the raw compound
    string NCBI sends.
    """
    output = await _run({"query": RS334, "query_type": "rsid"})

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    assert output.rsid == RS334
    assert output.spdi_canonical, "spdi_canonical must not be empty on a real, resolvable rsid"
    assert output.spdi_canonical.startswith(RS334_CHROMOSOME_PREFIX), (
        f"expected an SPDI on {RS334_CHROMOSOME_PREFIX} (chromosome 11), "
        f"got {output.spdi_canonical!r}"
    )

    gene_names = [g.name for g in output.genes or []]
    assert RS334_GENE_NAME in gene_names, f"expected gene {RS334_GENE_NAME!r} in {gene_names!r}"
    gene_ids = [g.gene_id for g in output.genes or []]
    assert RS334_GENE_ID in gene_ids, f"expected gene_id {RS334_GENE_ID!r} in {gene_ids!r}"

    entry = _find_population_entry(output, "1000Genomes")
    assert entry is not None, "expected a parsed 1000Genomes entry in population_frequencies"
    assert entry.allele == RS334_1000GENOMES_ALLELE, (
        f"F-3.2-01: expected allele {RS334_1000GENOMES_ALLELE!r} parsed out of "
        f"the raw 'A=0.027356/137' string, got {entry.allele!r}"
    )
    assert entry.frequency == pytest.approx(RS334_1000GENOMES_FREQUENCY, abs=1e-6), (
        f"F-3.2-01: expected frequency {RS334_1000GENOMES_FREQUENCY} as a real "
        f"float, got {entry.frequency!r}"
    )
    # Guard directly against the shipped-raw-string failure mode: no entry's
    # allele or frequency should ever equal the whole unparsed source string.
    for pop_entry in output.population_frequencies or []:
        assert "=" not in str(pop_entry.allele), (
            f"F-3.2-01: allele {pop_entry.allele!r} looks like an unparsed "
            f"raw freq string, not a parsed allele"
        )


@premise_gate
@pytest.mark.asyncio
async def test_02_empty_global_mafs_is_ok_not_error() -> None:
    """Case 2. Section 6.3 line 1074: no population data is a fact, not a failure."""
    output = await _run({"query": RS_EMPTY_MAFS, "query_type": "rsid"})

    assert output.status == "ok", (
        f"a real rsid with zero global_mafs entries must still be ok, "
        f"got {output.status}: {output.error}"
    )
    assert output.population_frequencies == [], (
        f"expected population_frequencies == [], got {output.population_frequencies!r}"
    )
    gene_names = [g.name for g in output.genes or []]
    assert RS_EMPTY_MAFS_GENE_NAME in gene_names
    gene_ids = [g.gene_id for g in output.genes or []]
    assert RS_EMPTY_MAFS_GENE_ID in gene_ids


@premise_gate
@pytest.mark.asyncio
async def test_03_clinical_significance_and_fxn_class_are_split_not_wrapped() -> None:
    """Case 3. F-3.2-02: the comma-split trap, asserted directly.

    A tool that wraps the raw ESummary string as one array element instead of
    splitting it is schema-valid (a one-item array is still an array) and
    semantically wrong: a caller checking "pathogenic" in the list gets False.
    """
    output = await _run({"query": RS334, "query_type": "rsid"})

    assert output.status == "ok"
    assert output.clinical_significance is not None
    assert RS334_CLINICAL_SIGNIFICANCE_CONTAINS in output.clinical_significance, (
        f"F-3.2-02: expected {RS334_CLINICAL_SIGNIFICANCE_CONTAINS!r} as its "
        f"own entry in {output.clinical_significance!r}"
    )
    assert len(output.clinical_significance) > 1, (
        f"expected multiple distinct clinical_significance values (raw ESummary "
        f"is 'not-provided,protective,likely-benign,pathogenic,other'), got "
        f"{output.clinical_significance!r}, which looks like one unsplit blob"
    )
    for value in output.clinical_significance:
        assert "," not in value, (
            f"F-3.2-02: {value!r} still contains a comma, the raw string was "
            f"not actually split"
        )


# ===========================================================================
# ARM 2: error. Malformed input is refused, never fabricated as ok.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_04_nonexistent_rsid_is_error_not_fabricated() -> None:
    """Case 4. Resolves the Section 6.3 open verification gap, live.

    Confirmed live during gate design: Variation Services answers a
    nonexistent rsid with HTTP 404, never a 200-with-empty-body the way
    E-utilities does. There is no reachable 'nothing matched, still ok' case
    on this endpoint; a bad rsid is unambiguously an error.
    """
    output = await _run({"query": NONEXISTENT_RSID, "query_type": "rsid"})

    assert output.status == "error", (
        f"a nonexistent rsid must be status error, got {output.status}. "
        f"A tool that fabricates a blank ok record here is the fabricated-"
        f"citation shape the whole system exists to prevent."
    )
    assert output.error, "an error status must carry an actionable message"


@premise_gate
@pytest.mark.asyncio
async def test_05_malformed_spdi_is_error() -> None:
    """Case 5. Confirmed live: HTTP 400 on a syntactically invalid SPDI."""
    output = await _run({"query": MALFORMED_SPDI, "query_type": "spdi"})

    assert output.status == "error", f"expected error, got {output.status}"
    assert output.error


@premise_gate
@pytest.mark.asyncio
async def test_06_malformed_hgvs_is_error() -> None:
    """Case 6. Confirmed live: HTTP 400 on a syntactically invalid HGVS expression."""
    output = await _run({"query": MALFORMED_HGVS, "query_type": "hgvs"})

    assert output.status == "error", f"expected error, got {output.status}"
    assert output.error


# ===========================================================================
# ARM 3: the phase's own reason. The traps Section 6.3 and
# Tool_implementation_mechanics.md name explicitly.
# ===========================================================================


@premise_gate
@pytest.mark.asyncio
async def test_07_hgvs_query_type_resolves_a_real_coding_variant() -> None:
    """Case 7. The third query_type, exercised end to end, not assumed to work
    because rsid and spdi do.

    Section 6.3 requires the `>` in an HGVS expression be percent-encoded
    (`%3E`) before the call. This case sends the UNENCODED, caller-facing
    form; the tool is responsible for the encoding, and a tool that forgets
    it gets a 400 here instead of the real result.

    CORRECTED 2026-08-08 for the F-3.2-A-06 fix: a successful hgvs
    normalization with no citable rsid is now `status: "empty"`, not `"ok"`,
    per `.claude/rules/production-standards.md`'s AI answer grounding gate (an
    `ok` claim with no citation is the exact failure that gate blocks). This
    case still proves the normalization itself is correct; it no longer
    claims the result is citable, because it is not. The fix builder correctly
    left this assertion untouched (out of its authorized scope) and flagged it
    for the lead to correct once independently reproduced live; see this
    file's module docstring, "Known stale assertion: case 7", now resolved.
    """
    output = await _run({"query": REAL_HGVS, "query_type": "hgvs"})

    assert output.status == "empty", (
        f"a resolved hgvs variant with no citable rsid must be 'empty', not "
        f"'ok' with source_url=None (F-3.2-A-06). Got {output.status}: "
        f"{output.error}"
    )
    assert output.source_url is None, (
        "an 'empty' status must carry no citation; a non-None source_url "
        "here would mean the empty/ok split itself is inconsistent"
    )
    assert output.spdi_canonical, "spdi_canonical must not be empty"
    assert REAL_HGVS_SEQ_ID in output.spdi_canonical, (
        f"expected the resolved SPDI to reference {REAL_HGVS_SEQ_ID!r}, "
        f"got {output.spdi_canonical!r}"
    )
    assert str(REAL_HGVS_POSITION) in output.spdi_canonical, (
        f"expected position {REAL_HGVS_POSITION} in {output.spdi_canonical!r}"
    )


@premise_gate
@pytest.mark.asyncio
async def test_08_clinical_fetch_is_keyed_on_the_normalized_id_not_the_raw_input() -> None:
    """Case 8. The sequential-ordering trap, made into a live assertion.

    rs3168321 is a real, obsolete rsid that merged into the current rs334.
    NCBI's own ESummary is lenient about merged ids and answers correctly for
    EITHER id, which means the clinical fields alone cannot distinguish a
    correct implementation from a lucky one. The `rsid` field in the OUTPUT
    can: it reads "rs334" only if the tool ran Variation Services
    normalization FIRST and threaded the canonical id through to the
    clinical fetch and the output, exactly what Section 6.3 line 1076
    requires. A tool that echoes the caller's raw input here has not proven
    it normalizes before it fetches, whatever its clinical fields say.
    """
    output = await _run({"query": OBSOLETE_MERGED_RSID, "query_type": "rsid"})

    assert output.status == "ok", f"expected ok, got {output.status}: {output.error}"
    assert output.rsid == RS334, (
        f"expected the CANONICAL id {RS334!r} in the output (proving "
        f"normalize-before-fetch ran), got {output.rsid!r}. NCBI's own "
        f"ESummary is lenient about merged ids, so a correct clinical_"
        f"significance value alone does not prove this; the output's own "
        f"rsid field is the property that does."
    )
    gene_names = [g.name for g in output.genes or []]
    assert RS334_GENE_NAME in gene_names
