"""ncbi_dbsnp: variant normalization and dbSNP record retrieval (T-3.2-04).

Section 6.3's two-call sequential procedure: NCBI Variation Services
normalizes the caller's `rsid`/`spdi`/`hgvs` query to a canonical rsid and
SPDI FIRST, then, only if that succeeds and `include_clinical` is true, a
dbSNP ESummary call keyed on the CANONICAL rsid (never the caller's raw
input) supplies clinical significance, functional consequence, gene
linkage, and population frequency data Variation Services does not carry.
The two calls run strictly sequentially, never via `asyncio.gather`: the
second call's input is the first call's output, and Variation Services'
own ~1 request/second pool (`ncbi_transport`'s `"variation"` family) is a
second, independent reason not to parallelize against it.

## Three live-probed traps this module resolves, none guessable from the
## locked spec or from documentation alone (LEARNINGS.md row 60's
## discipline: fixtures and assumptions come from the real endpoint, not a
## reading of what it should do)

1. THE SPDI CANONICAL_REPRESENTATIVE ENDPOINT IS CURRENTLY BROKEN
   SERVER-SIDE. `tracker/phase_3.2.md`'s pre-build probes left this
   unresolved ("a seemingly well-formed, real SPDI 500s on this endpoint,
   not yet explained"). Live re-probing for this ticket (2026-08-08)
   confirms it is NOT a client-side request-shape issue: NCBI's OWN
   documented example (`NC_000001.10:12345:0:C`, from the service's own
   `var_service.yaml`) and NCBI's OWN self-generated `_links.canonical_representative.href`
   value (percent-encoded exactly as NCBI itself produced it) both return
   `HTTP 500 {"error":{"code":500,"message":"Internal error"}}` when
   fetched. `all_equivalent_contextual` is broken the identical way, on
   the identical documented example. Every SIBLING sub-resource of the
   same base `/spdi/{spdi}/` resource works normally: the base resource
   itself, `/contextual`, `/hgvs`, and `/vcf_fields` all return clean 200s
   for the same inputs. This is a live NCBI-side defect isolated to
   exactly two named sub-resources, not a request-shape problem this
   module could fix by encoding or formatting the SPDI differently.

   Given that, `_normalize_spdi` below deliberately calls `/spdi/{spdi}/contextual`
   instead of the spec-named `/spdi/{spdi}/canonical_representative`.
   `/contextual` performs genuine normalization (NCBI's Blossom Precision
   Correction Algorithm, right-shifting an over-precise input to its
   minimal contextual representation), unlike the bare base resource
   (`/spdi/{spdi}/`), which only validates and echoes the input back
   unmodified. It is the closest live-working analog to what
   `canonical_representative` was supposed to provide, and it shares the
   same non-200-is-error contract (confirmed live: a malformed SPDI still
   404/400s the same way through this endpoint). This is a deliberate,
   documented substitution forced by a live external-service defect in the
   literal endpoint the ticket names, not a silent workaround: if
   `canonical_representative` starts working again, this should be
   reconsidered, since it may perform additional canonicalization
   `/contextual` does not (e.g. choosing among several equivalent
   representations, which `all_equivalent_contextual`, also broken, would
   otherwise resolve). No premise-gate case exercises the SPDI-`ok` path
   directly (per the gate's own "Deliberately NOT exercised" section,
   `query_type="spdi"` is only exercised via the malformed-input error
   case), so this substitution is unverified by the live gate beyond the
   error path, and is flagged here for the phase lead to confirm or
   revisit.

2. A REFSNP RESPONSE FOR A MERGED/OBSOLETE RSID HAS NO
   `primary_snapshot_data` AT ALL. Not named anywhere in Section 6.3, the
   mechanics doc, or the phase tracker's pre-build probes (which only
   probed a currently-canonical rsid). Live-confirmed 2026-08-08:
   `refsnp/3168321` (the merged rsid the premise gate's case 8 uses)
   returns `{"refsnp_id": "3168321", ..., "merged_snapshot_data":
   {"merged_into": ["334"], ...}, ...}` with NO `primary_snapshot_data`
   key present at all. A normalization path that only looks for
   `primary_snapshot_data.placements_with_allele` (the shape a currently-
   canonical rsid like `refsnp/334` has) finds nothing and fails closed,
   which would make case 8 fail even though `rs3168321` is a perfectly
   legitimate, resolvable query. `_normalize_rsid` below checks for
   `merged_snapshot_data.merged_into` FIRST and follows it (re-fetching
   `refsnp/{merged_into[0]}`), bounded to `_MAX_MERGE_HOPS` hops so a
   pathological or circular merge chain cannot loop forever. This is what
   actually makes the "normalize before clinical-fetch" ordering property
   case 8 tests possible to satisfy at all, not only what makes it correct.

3. dbSNP ESUMMARY'S OWN `spdi` FIELD IS ALSO A COMMA-JOINED STRING OF
   MULTIPLE ALLELES, THE SAME SHAPE AS F-3.2-02'S `clinical_significance`/
   `fxn_class` TRAP. Live-confirmed on rs334: `"spdi":
   "NC_000011.10:5227001:T:A,NC_000011.10:5227001:T:C,NC_000011.10:5227001:T:G"`
   (three equivalent alt-allele SPDIs for one multiallelic position,
   comma-joined, not an array). This module does NOT read ESummary's
   `spdi` field at all for `spdi_canonical`: that field is populated
   exclusively from the Variation Services normalization call (per
   Section 6.3 line 1076's own ordering requirement), so this trap is
   avoided by construction rather than by careful parsing. Flagged here as
   a new, undocumented finding for whoever next reads ESummary's raw
   `spdi` field for any other purpose.

## Judge round 1 fix pass (2026-08-08): truncation policy, rsid shape,
## allele attribution, uncited ok, withdrawn/5xx messaging

Five fixes landed after `tracker/phase_3.2.md`'s judge round 1 FAIL
verdict. Each is a real, documented design decision, not a mechanical
patch; recorded here rather than only in the ticket tracker so a reader of
this module sees the reasoning next to the code it governs.

### Truncation policy, revised twice: REFUSE (round 1), then WITHHOLD-WITH-
### SIGNAL for everything except `spdi_canonical` (round 2, F-3.2-A-15)

Round 1 (F-3.2-A-01, F-3.2-A-14, J-05): `_cap()` used to truncate every
over-length string to fit its schema cap before construction, silently,
under `status: "ok"`. Live-reproduced by both the adversary and the judge,
independently: a clinical-significance term truncated mid-word into a
DIFFERENT real term (`"conflicting-interpretations-of-pathogeni"`), a
clinical_significance LIST silently shortened from 11 real entries to 10
with `"likely-pathogenic"` dropped and no signal anywhere in the output, a
population-frequency allele truncated from a real 14bp repeat into a
real-looking but WRONG 10bp allele, and `spdi_canonical` truncated from a
150bp insertion into a syntactically valid but wrong 128bp one naming a
different variant. Every one of these shipped as a confident, cited
`status: "ok"` answer. Round 1's fix made ANY of these overflow the WHOLE
call to `status: "error"`, discarding everything else that had already
fetched successfully.

Round 2 (F-3.2-A-15, independent re-review of round 1's fix): round 1's
whole-call refusal was itself measured, live, to be its own defect at
scale. A live 800-record sample found roughly 10.4 percent of real
clinically-cited variants hit the `clinical_significance` item cap (40
chars) or list cap (10 items) alone, because two standard ClinVar
vocabulary terms, `conflicting-interpretations-of-pathogenicity` (44
chars) and `no-classifications-from-unflagged-records` (41 chars), are
common. Flagship variants this repo already uses as ground truth,
rs429358 (APOE epsilon4), rs6025 (Factor V Leiden), rs1801133 (MTHFR
C677T), rs1800562 (HFE C282Y), rs1042522 (TP53 P72R), rs80359198 (BRCA2),
all returned `status: "error"` for an otherwise fully successful fetch:
the gene linkage, the SPDI, and the population data were all correctly
resolved and then discarded along with the one over-cap field. Live-
reconfirmed here: rs429358's raw `clinical_significance` is
`"association,drug-response,risk-factor,protective,uncertain-significance,
pathogenic,not-provided,conflicting-interpretations-of-pathogenicity,
pathogenic-established-risk-allele,other,likely-pathogenic"`, 11 items
(exceeds the 10-item cap) with one 44-char item (exceeds the 40-char cap).

The policy is now WITHHOLD-WITH-SIGNAL, field-level, for every capped
field EXCEPT `spdi_canonical`: `alleles` (item and list), every
`clinical_significance` entry and list, every `functional_consequence`
entry and list, every gene `name`/`gene_id`, the `population_frequencies`
list and its `population`/`allele` item fields, and `chrpos`. When a
field's value would need truncation to fit its schema cap, THAT FIELD
alone is set to its empty default (`[]` for a list field, `None` for
`chrpos`) and its name is appended to the output's `fields_withheld` list
(`ncbi_dbsnp_schemas.NcbiDbsnpOutput.fields_withheld`, design decision 7).
Everything else that fetched successfully, including every OTHER field
that was within cap, still ships under `status: "ok"`. `fields_withheld`
is the caller-visible signal that a real value existed upstream and was
deliberately dropped for exceeding this tool's own schema cap, distinct
from the field genuinely being absent or empty in the source data (an
absent field is never added to `fields_withheld`). This is different from
truncating: a truncated `"conflicting-interpretations-of-pathogeni"` looks
like a real, complete, wrong term; a withheld field is empty and flagged,
so a reader can tell "nothing here" from "something here, dropped" from "a
different, shorter real value". `_cap_or_withhold` below is round 2's
mechanism for a single string field; the list-shaped fields
(`clinical_significance`/`functional_consequence` via `_split_comma_field`,
`genes` via `_parse_genes`, `population_frequencies` via
`_parse_global_mafs`) each apply the same field-level (not item-level)
withhold: if ANY item or the list itself overflows, the WHOLE field is
withheld to its empty default, not partially trimmed.

`spdi_canonical` is the sole, deliberate exception, unchanged from round 1:
an over-length `spdi_canonical` still refuses the WHOLE call,
`status: "error"`, via `_cap_or_refuse`/`_FieldOverflowError`. Without a
citable `spdi_canonical` there is no variant identity left to attach any
other field to; withholding it and shipping the rest under `status: "ok"`
would mean an `"ok"` record with no stated identity for what it is about,
which is a worse failure than refusing outright. This exception is
narrower than round 1's blanket refusal: it fires only when
`spdi_canonical` ITSELF overflows, never when a peripheral field like
`clinical_significance` does.

RESIDUAL, explicitly not fixed by round 2 and not authorized to fix
unilaterally: the numeric caps themselves
(`_MAX_CLINICAL_SIG_CHARS` = 40, etc., mirrored in
`ncbi_dbsnp_schemas.py`'s `Field(max_length=...)`/`Field(max_items=...)`
values) are locked by Section 6.3 of the technical specification, and
raising any of them is a deliberate, reviewed product-owner decision, not
something this fix round makes. Real NCBI clinical-significance vocabulary
routinely exceeds the 40-char item cap and the 10-item list cap
(demonstrated above on ~10 percent of a live sample); this tool now
DISCLOSES that gap via `fields_withheld` rather than either fabricating a
truncated value (round 1's original defect) or discarding a whole
successful fetch over it (round 1's fix, round 2's finding). If this
recurs at a rate that matters, the correct next step is raising the caps
in `ncbi_dbsnp_schemas.py`, explicitly, not silently working around them
here.

Deliberately UNCHANGED, and left to F-3.2-A-04/A-10 (carried forward, not
this round's job): `_error_output`'s own `rsid`, `spdi_canonical`, and
`error` parameters still use the OLD silent-truncating `_cap()`, exactly as
before, on the paths where they echo the caller's raw, already-validated
(`max_length=200`) but otherwise untrusted query text back on an
already-failed request (a malformed SPDI or HGVS expression that never
normalized). That is a different, narrower problem (raw caller text
landing in an unpinned field on an error path that is already `status:
"error"`, never a confident `"ok"`) and is explicitly out of scope for this
fix; see F-3.2-A-04/A-10 in `tracker/phase_3.2.md`.

### rsid shape validation (F-3.2-A-02, J-03)

Moved to `ncbi_dbsnp_schemas.py`'s `NcbiDbsnpInput._validate_rsid_shape`
(design decision 2, revised): a `query_type: "rsid"` request now requires
an explicit `rs`/`RS` prefix, rejected at the Pydantic layer before any
network call. See that schema's docstring for the full reasoning; this
tool's own `_strip_rs_prefix` is unaffected (still strips the prefix it
can now assume is present) and `refsnp/{id}`'s live 404 still owns
classifying a syntactically valid but nonexistent rsid, unchanged.

### Population-frequency allele attribution (F-3.2-A-03)

`NcbiDbsnpPopulationFrequency.allele_role` (`ncbi_dbsnp_schemas.py`, design
decision 6) labels each row `"variant"`, `"reference"`, or `"other"`
relative to `spdi_canonical`'s own two alleles, computed by `_allele_role`
below from `spdi_canonical`'s own already-published string. See that
schema's docstring for why labeling was chosen over reselecting which
allele `spdi_canonical` names.

### spdi/hgvs uncited "ok" becomes "empty" (F-3.2-A-06)

`spdi`/`hgvs` queries never resolve an rsid (see "rsid resolution" below),
so `source_url` was always `None` on that path, forever, yet the tool
still reported `status: "ok"`: a permanent, uncited confident claim,
exactly what `.claude/rules/production-standards.md`'s AI answer grounding
gate exists to block. `_ncbi_dbsnp_impl` now branches this case out
separately from the `include_clinical=False` case (F-3.2-A-05, carried
forward, real ambiguity but the caller set that flag knowingly and DOES
still get a citable `rsid`/`source_url` when the query_type is `rsid`):
when normalization succeeds but no numeric rsid was ever resolvable
(`spdi`/`hgvs`), the result is `status: "empty"`, with an informational
`error` message distinguishing "nothing to cite" from a genuine failure,
never a bare uncited `"ok"`.

### Withdrawn rsid and 5xx-vs-404 messaging (F-3.2-A-07, F-3.2-A-08, J-02)

A withdrawn rsid (live-reproduced: rs100, rs386) is a THIRD `refsnp`
response shape, `withdrawn_snapshot_data`, neither `primary_snapshot_data`
nor `merged_snapshot_data.merged_into`. `_withdrawn_info` below detects it,
checked BEFORE the merge-follow logic (a withdrawal is permanent; no merge
chain could ever resolve it), and reports a non-retrying error carrying the
live `withdrawn_time` when NCBI provides one.

J-02's root cause: `ncbi_transport.ClassificationResult` carries no HTTP
status, so all three normalization functions collapsed a 404 (bad input,
do not retry), a withdrawn 200 (permanent, do not retry), and a 429/5xx
(transient, DO retry, the transport's own single backoff retry may not
have been enough) into identical "verify your input, retry" guidance. Per
the judge's own assessment, this is fixed LOCALLY here rather than by
changing the shared `ncbi_transport.ClassificationResult` structure every
other caller of `classify_status_coded_response` also depends on:
`_get_variation` already has `response.status_code` in hand before it ever
discards it into a bare `ClassificationResult`, and `_VariationResponse`
below is this module's own local wrapper that threads it through to
`_variation_error_message`, which picks retry-vs-no-retry guidance from the
status the transport module itself never persists.

ROUND 2 (F-3.2-A-16, independent re-review of the fix above): round 1's own
"a 429/5xx is always transient, retry" claim was itself live-reproduced
false for a 5xx specifically. `_looks_like_input_shaped_problem` and the
`_variation_error_message` revision above close it: a 429 is still always
treated as transient (NCBI's own unambiguous rate-limit signal), but a 5xx
is now inspected for input-shaped language in its own message before ever
telling the agent to retry, and a genuinely ambiguous 5xx gets hedged
language ("MAY be transient") instead of round 1's confident, and now
disproven, assertion. See the full live repro and reasoning above
`_looks_like_input_shaped_problem`'s definition.

## F-3.2-01 and F-3.2-02, closed

`_parse_global_mafs` and `_split_comma_field` close the two findings filed
at design time in `tracker/phase_3.2.md`. One live nuance beyond what that
finding predicted: rs334's own `global_mafs` includes a genuine
`"freq": "A=0./0"` entry (PRJEB36033, frequency exactly zero with a
trailing bare decimal point, no digits after it). A regex requiring at
least one digit after the decimal point rejects this real, live value as
malformed and would fail the whole `ok` case closed (F-3.2-01 requires
failing closed on a genuinely malformed value, but "0." is not malformed,
it is a valid zero). `_GLOBAL_MAFS_FREQ_PATTERN` requires digits BEFORE
the decimal point and makes the digits AFTER it optional, so both
`"0.027356"` and `"0."` parse, while a value with no recognizable
`<allele>=<digits>[.<digits>]/<digits>` shape still fails closed exactly
as F-3.2-01 requires.

## Two-call sequencing, and what happens when the second call fails

Both Variation Services calls (normalization, always) and the dbSNP
ESummary call (clinical fetch, only when `include_clinical` is true and a
numeric rsid was resolved) are `await`ed in a strict order in
`_ncbi_dbsnp_impl` below: nothing about the second call is started, or
could be started, before the first call's result is in hand, since the
second call's own request parameters (`numeric_rsid`) are read out of the
first call's return value.

If normalization succeeds but the clinical fetch then fails (a transport
error, a malformed `global_mafs` entry per F-3.2-01, an ESummary response
missing the resolved id), the WHOLE call returns `status: "error"`, not a
partial `"ok"` with the clinical fields silently blank. This mirrors the
house style `ncbi_eutils_actions.py` and `ncbi_datasets_actions.py` both
use (one verdict per call, never a hybrid "ok but something also failed"
shape this codebase does not have anywhere else), and keeps the contract
simple for a downstream reader: `status: "ok"` means every field this call
was configured to fetch is trustworthy, not merely "the parts that
worked". The successfully normalized `rsid` and `spdi_canonical` are still
carried on the error output rather than blanked to empty strings, since
they are genuinely correct values this call already obtained; the raw,
UNRESOLVED caller query is carried instead only when normalization itself
never succeeded.

`rsid` resolution for `spdi`/`hgvs` query types: NEITHER `/spdi/{spdi}/contextual`
nor `/hgvs/{hgvs}/contextuals` returns an rsid (Variation Services has a
separate `/spdi/{spdi}/rsids` endpoint for that, not named in this
ticket's four-endpoint list and not called here). So `rsid` is `""` on a
successful `spdi`/`hgvs` normalization, and the clinical fetch is skipped
entirely for those two query types regardless of `include_clinical`,
since ESummary has no numeric id to key on. `source_url` is `None`
whenever `rsid` is empty, since a citation URL with nothing after
`/snp/` does not resolve to a real record. This is a known, narrower
capability than the `rsid` query type gets; flagged here rather than
silently assumed away.

Never raises: `ncbi_dbsnp` (the public entry point) wraps
`_ncbi_dbsnp_impl` in a `try`/`except`, the same outer-boundary pattern
`ncbi_efetch.py`'s dispatcher uses, so an unexpected exception from
anywhere in this module's own parsing (not already a classified
`ncbi_transport.TransportError`) still returns a `status: "error"` output
with an actionable message instead of propagating out of a tool call.

Depends on:
    - system_03_search_agent.tools.ncbi_transport (T-3.2-02's `"variation"`
      rate-limit family; `execute_get`, `classify_status_coded_response`,
      `classify_eutils_response`, `http_status_error_message`,
      `TransportError`)
    - system_03_search_agent.tools.ncbi_dbsnp_schemas (T-3.2-03;
      `NcbiDbsnpInput`, `NcbiDbsnpOutput`, `NcbiDbsnpGene`,
      `NcbiDbsnpPopulationFrequency`, `NCBI_DBSNP_RECORD_URL_PATTERN`)

Reads:
    - Nothing directly. `NCBI_API_KEY` is read indirectly, inside
      `ncbi_transport.execute_get` for the ESummary call only
      (`include_api_key=True`); Variation Services calls carry no API key,
      it does not use one.

Writes:
    - Nothing. Outbound HTTPS requests only, via `ncbi_transport`.

Depended by:
    - system_03_search_agent.harness.cache (T-3.2-05, tool registration)
    - tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py, via
      its `_run` helper, which imports `ncbi_dbsnp` from this module by
      name
    - tests/system_03_search_agent/tools/test_ncbi_dbsnp.py
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, Final, Literal

from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.synthesis.provenance_defaults import (
    clinvar_term_confidence,
    defaults_for_tool,
)
from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.ncbi_dbsnp_schemas import (
    NCBI_DBSNP_RECORD_URL_PATTERN,
    NcbiDbsnpGene,
    NcbiDbsnpInput,
    NcbiDbsnpOutput,
    NcbiDbsnpPopulationFrequency,
)

_VARIATION_BASE: Final[str] = "https://api.ncbi.nlm.nih.gov/variation/v0"
_ESUMMARY_ENDPOINT: Final[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Field length caps, mirroring NcbiDbsnpOutput/NcbiDbsnpGene/
# NcbiDbsnpPopulationFrequency's own Field(max_length=...) constraints
# exactly (ncbi_dbsnp_schemas.py). Pydantic raises on an over-length string
# rather than truncating it, so every value that could plausibly come from
# untrusted upstream content is capped here, before construction, per
# production-standards.md's bounded-context-items gate.
_MAX_RSID_CHARS: Final[int] = 20
_MAX_SPDI_CHARS: Final[int] = 150
_MAX_ERROR_CHARS: Final[int] = 500
_MAX_ALLELE_CHARS: Final[int] = 20
_MAX_CLINICAL_SIG_CHARS: Final[int] = 40
_MAX_FXN_CLASS_CHARS: Final[int] = 60
_MAX_GENE_NAME_CHARS: Final[int] = 30
_MAX_GENE_ID_CHARS: Final[int] = 20
_MAX_POP_NAME_CHARS: Final[int] = 20
_MAX_POP_ALLELE_CHARS: Final[int] = 10
_MAX_CHRPOS_CHARS: Final[int] = 30

_MAX_ALLELES: Final[int] = 10
_MAX_CLINICAL_SIG_ITEMS: Final[int] = 10
_MAX_FXN_CLASS_ITEMS: Final[int] = 10
_MAX_GENES: Final[int] = 10
_MAX_POP_FREQS: Final[int] = 30

# Bounded, not unbounded: a merge chain following merged_snapshot_data
# more than this many hops without landing on a primary_snapshot_data-
# bearing response fails closed rather than looping. Real dbSNP merge
# chains observed so far (rs3168321 -> rs334) are a single hop; this
# leaves headroom for a short chain without letting a circular or
# pathological one run away.
_MAX_MERGE_HOPS: Final[int] = 3

# F-3.2-01: `global_mafs[].freq` is `"<allele>=<freq>/<sample_count>"`.
# Digits are REQUIRED before the decimal point and OPTIONAL after it, so
# both "0.027356" and the genuine live value "0." (PRJEB36033 on rs334,
# frequency exactly zero) parse, while a string with no recognizable
# allele=freq/n shape still fails to match and is treated as malformed,
# per this module's own docstring section on the live nuance this closes.
_GLOBAL_MAFS_FREQ_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<allele>[^=]+)=(?P<freq>[0-9]+\.?[0-9]*)/(?P<n>[0-9]+)$"
)


def _quote_path_segment(value: str) -> str:
    """URL-encode one path segment. Matches `ncbi_pubchem_actions._quote_path_segment`.

    `value` is caller-supplied (the tool's own `query` field) and lands in
    the URL PATH, not a query string, so every reserved character is
    encoded (`safe=""`), not just the query-string-safe subset
    `ncbi_transport._build_query_string` uses for actual query parameters.
    This is also what Section 6.3's `>` -> `%3E` requirement for HGVS
    expressions reduces to: full path-segment encoding percent-encodes
    `>` as a side effect of encoding everything, and live-confirmed
    (`tracker/phase_3.2.md`'s pre-build probe) to also require the `:`
    characters in an HGVS or SPDI expression to be percent-encoded, not
    left literal, for the request to reach the intended route.
    """
    return urllib.parse.quote(value, safe="")


def _cap(value: str, limit: int) -> str:
    return value[:limit]


class _FieldOverflowError(Exception):
    """`spdi_canonical` must never be silently truncated and exceeds its schema cap.

    F-3.2-A-01 / F-3.2-A-14 / J-05 introduced this for every capped field.
    F-3.2-A-15 (round 2, see the module docstring's "Truncation policy"
    section) narrowed its use to `spdi_canonical` alone: every other capped
    field now WITHHOLDS (`_cap_or_withhold` below, or an equivalent inline
    field-level check) rather than raising. Raised only by `_cap_or_refuse`,
    and caught close to the call site that raised it (never allowed to
    reach `ncbi_dbsnp`'s generic last-resort catch, which would report a
    bare "unexpected exception" instead of naming the field, its cap, and
    its actual size), so the resulting `_error_output` can still carry
    whatever rsid context was already resolved at that point.
    """

    def __init__(self, field: str, limit: int, actual: int) -> None:
        super().__init__(f"{field}: {actual} exceeds the {limit} cap")
        self.field = field
        self.limit = limit
        self.actual = actual


def _overflow_message(exc: _FieldOverflowError) -> str:
    return (
        f"ncbi_dbsnp refuses to return an incomplete record: {exc.field} is "
        f"{exc.actual} characters/items, exceeding the {exc.limit} cap this "
        "tool's own output schema enforces. This is real upstream data, not "
        "a malformed request; refusing rather than silently truncating or "
        "dropping part of a citable field under status 'ok'. spdi_canonical "
        "is the sole field this tool still refuses the whole call for "
        "(F-3.2-A-15): without it there is no variant identity left to "
        "attach any other field to. If this recurs on genuinely legitimate "
        "data, the cap may need to be reconsidered for this field; "
        "retrying the same query will not change the outcome."
    )


def _cap_or_refuse(value: str, limit: int, field: str) -> str:
    """Return `value` unchanged, or raise `_FieldOverflowError` if it exceeds `limit`.

    Used ONLY for `spdi_canonical` as of F-3.2-A-15 (round 2): see the
    module docstring's "Truncation policy" section for why that one field
    still refuses the whole call while every other capped field withholds
    instead. `_cap` itself is kept, unchanged, for the two fields this
    module deliberately does NOT touch here: see the same section for why
    `_error_output`'s own raw-caller-query echo is out of scope
    (F-3.2-A-04/A-10, carried forward).
    """
    if len(value) > limit:
        raise _FieldOverflowError(field, limit, len(value))
    return value


def _cap_or_withhold(value: str, limit: int, field: str) -> tuple[str | None, str | None]:
    """Return `(value, None)` within cap, or `(None, field)` when it overflows.

    F-3.2-A-15 (round 2): the single-string-field mechanism for
    "withhold, don't truncate, don't refuse the whole call". The caller
    appends the returned field name to the output's `fields_withheld` list
    when it is not `None`; the field itself becomes empty/`None`, never a
    truncated value. See the module docstring's "Truncation policy" section
    for the full reasoning, including why `spdi_canonical` (`_cap_or_refuse`
    above) is the one field this does NOT apply to.
    """
    if len(value) > limit:
        return None, field
    return value, None


def _error_output(rsid: str, spdi_canonical: str, message: str) -> NcbiDbsnpOutput:
    """Build a `status: "error"` output. `rsid`/`spdi_canonical` are always present.

    Section 6.3 line 1020 requires `rsid` and `spdi_canonical` on every
    output, including an error one. Callers pass whichever of the two
    values they actually have: the raw, UNRESOLVED caller query when
    normalization itself never succeeded (so the caller can trace the
    error back to what they searched), or the genuinely resolved values
    when normalization succeeded but a later step (the clinical fetch)
    failed, since those values are correct and more useful than blanking
    them.
    """
    return NcbiDbsnpOutput(
        status="error",
        rsid=_cap(rsid, _MAX_RSID_CHARS),
        spdi_canonical=_cap(spdi_canonical, _MAX_SPDI_CHARS),
        error=_cap(message, _MAX_ERROR_CHARS),
    )


def _strip_rs_prefix(raw_rsid: str) -> str:
    """Strip a leading `rs`/`RS` prefix, per Section 6.3's `refsnp/{rsid}` shape.

    Whatever remains is used as-is, URL-encoded as a path segment. This
    module does not shape-validate the remainder as numeric-only: per
    `ncbi_dbsnp_schemas.py`'s own design decision 2, a malformed remainder
    is left for the live endpoint to classify (a non-numeric id 400s or
    404s the same way a nonexistent numeric one does), not rejected here
    before the request is even sent.
    """
    stripped = raw_rsid.strip()
    if stripped[:2].lower() == "rs":
        return stripped[2:]
    return stripped


@dataclass(frozen=True)
class _NormalizationResult:
    """The output of Variation Services normalization, threaded into the clinical fetch.

    `rsid` is the CANONICAL rsid (e.g. `"rs334"`), never the caller's raw
    input; `""` when this query_type does not resolve one (`spdi`/`hgvs`,
    see the module docstring). `numeric_rsid` is the bare digits used to
    key the ESummary clinical fetch, `None` under the same condition.

    `fields_withheld` (F-3.2-A-15) names any field this normalization step
    itself withheld for exceeding its schema cap, currently only ever
    `"alleles"`: threaded into every `NcbiDbsnpOutput` this normalization
    result eventually produces, in `_ncbi_dbsnp_impl`, regardless of which
    branch (empty/ok-without-clinical/ok-with-clinical) is taken.
    """

    rsid: str
    numeric_rsid: str | None
    spdi_canonical: str
    alleles: list[str]
    fields_withheld: list[str] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class _VariationResponse:
    """Local wrapper: `ClassificationResult` plus the HTTP status the shared
    transport module classifies FROM but never PERSISTS onto the result it
    returns (F-3.2-A-08/J-02).

    `ncbi_transport.ClassificationResult` deliberately carries no
    `http_status` field, and this fix does not add one there (per the
    judge's own assessment: the gap is local to how this module used the
    result, not to what the shared classifier returns; a shared-structure
    change would ripple to every other caller of
    `classify_status_coded_response` for a fix only this tool's error
    messages need). `_get_variation` already has `response.status_code` in
    hand before it classifies, so this module-local dataclass is what
    threads it through to `_variation_error_message` without touching
    `ncbi_transport.py` at all.
    """

    classification: ncbi_transport.ClassificationResult
    http_status: int


async def _get_variation(url: str) -> _VariationResponse | str:
    """GET one Variation Services URL and classify it, or return an error message.

    Returns a `_VariationResponse` for any COMPLETED HTTP exchange (2xx or
    non-2xx alike: `classify_status_coded_response` already turns a
    non-2xx into `status == "error"` with an actionable `error_message`,
    per the third branch added to `_extract_status_coded_error_message` in
    `ncbi_transport.py` for Variation Services' `{"error": {"message":
    ...}}` body shape), carrying the raw HTTP status alongside it (see
    `_VariationResponse`'s own docstring for why that status is threaded
    through locally rather than added to the shared `ClassificationResult`
    type). Returns a bare `str` only when the TRANSPORT itself failed
    before any HTTP response existed to classify (timeout, connection
    failure, rate limit). Callers check `isinstance(result, str)` to tell
    the two apart, the same shape of short-circuit
    `ncbi_eutils_actions._get_or_error`'s `isinstance(result,
    NcbiEfetchOutput)` check uses for E-utilities calls.
    """
    try:
        response = await ncbi_transport.execute_get(url, {}, family="variation")
    except ncbi_transport.TransportError as exc:
        return str(exc)
    classification = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text, headers=response.headers
    )
    return _VariationResponse(classification=classification, http_status=response.status_code)


# F-3.2-A-16 (round 2, independent re-review of the F-3.2-A-07/A-08 fix):
# Variation Services does NOT reserve HTTP 5xx for genuine server-side
# conditions. Live-reproduced 2026-08-08: a reference-mismatch SPDI
# (`NC_000011.10:5227000:AT:AA`, where the true reference at that position
# is `CT`, not `AT`) returns HTTP 500 with
# `{"error":{"code":500,"message":"The reference sequence for
# 'NC_000011.10' at position '5227000' ('CT'), is not equal to variant's
# asserted reference ('AT')"}}`: a deterministic, PERMANENT client input
# error wearing a 5xx status. The round-1 fix's blanket "any 5xx is
# transient, retry" claim is therefore false, and told the agent to retry a
# request that can never succeed, burning a call against the roughly
# 1-req/s Variation Services pool (`.claude/rules/tool-call-budgets.md`) on
# a request no retry will ever fix.
#
# This is a keyword heuristic, not a parser: Variation Services has no
# documented, structured way to distinguish "genuinely transient" from
# "deterministic input problem wearing a 5xx" other than the free-text
# `message` field, so this function inspects that text for language that
# describes a problem WITH THE INPUT (a reference-sequence mismatch, an
# invalid coordinate) rather than a server condition. A message this list
# does not recognize is treated as genuinely ambiguous, not confidently
# asserted to be transient (see `_variation_error_message` below); a false
# negative here (an input-shaped 5xx this function does not recognize)
# degrades to the pre-fix hedge language, not to a false "this is
# transient" claim, so the residual risk of an unrecognized phrasing is a
# missed optimization, not a resurrection of F-3.2-A-16 itself.
_INPUT_SHAPED_5XX_MARKERS: Final[tuple[str, ...]] = (
    "reference sequence",
    "asserted reference",
    "is not equal to",
    "does not match",
    "invalid coordinate",
    "invalid position",
    "out of range",
    "out of bounds",
    "invalid spdi",
    "invalid hgvs",
)


def _looks_like_input_shaped_problem(reason: str | None) -> bool:
    """F-3.2-A-16: does `reason`'s own text describe a caller-input problem, not a server one?

    See `_INPUT_SHAPED_5XX_MARKERS` above for the full reasoning and the
    live repro this closes.
    """
    if not reason:
        return False
    lowered = reason.lower()
    return any(marker in lowered for marker in _INPUT_SHAPED_5XX_MARKERS)


def _variation_error_message(action: str, query_repr: str, http_status: int, reason: str | None) -> str:
    """F-3.2-A-07/A-08/J-02, revised for F-3.2-A-16: retry guidance that matches reality.

    `_extract_status_coded_error_message` (`ncbi_transport.py`) already
    supplies a human-readable `reason`; this function decides the RETRY
    ADVICE from the status code (and, for a 5xx, the reason text itself)
    that function's caller used to discard after classification.

    A 404/400 (bad input) never suggests retrying: retrying an unaltered
    bad request just gets the same 404/400 again, unchanged from round 1.

    A 429 is unambiguous: it is NCBI's own rate-limit signal, always
    transient, so it always suggests retrying after a backoff; no reason-
    text inspection is needed or done for it.

    A 5xx is NOT unambiguous (F-3.2-A-16): Variation Services can return a
    5xx for a genuine, deterministic input error (a reference-sequence
    mismatch, confirmed live), not only a real transient condition. When
    `reason` names a specific input-shaped problem
    (`_looks_like_input_shaped_problem`), this reports a PERMANENT,
    non-retrying verdict instead of the old blanket "this is transient"
    claim. When `reason` is generic, unhelpful, or absent, this notes a
    transient condition is POSSIBLE and retrying after a backoff is
    reasonable, but does not assert it as settled fact the way round 1 did,
    since the same endpoint has now been shown to lie about that on a
    5xx often enough to matter.
    """
    text = reason or "unknown error"
    if http_status == 429:
        return (
            f"Variation Services {action} for {query_repr} returned HTTP "
            f"{http_status} ({text}). This is NCBI's own rate-limit signal, "
            "always transient; retry after a backoff."
        )
    if http_status >= 500:
        if _looks_like_input_shaped_problem(reason):
            # Kept deliberately terse (unlike the hedge branch below): the
            # live-reproduced repro this closes carries a long NCBI-supplied
            # `text` (a full reference-sequence-mismatch sentence), and
            # `_error_output`'s own 500-char error cap silently truncates
            # via `_cap()` (F-3.2-A-04/A-10, carried forward, out of scope
            # here) if the fixed template is too verbose on top of it.
            return (
                f"Variation Services {action} for {query_repr} returned HTTP "
                f"{http_status} ({text}). This is a PERMANENT, deterministic "
                "input error (F-3.2-A-16), not a transient server condition; "
                "retrying will not help. Correct the input before retrying."
            )
        return (
            f"Variation Services {action} for {query_repr} returned HTTP "
            f"{http_status} ({text}). This MAY be a transient, server-side "
            "condition, but Variation Services can also return a 5xx for a "
            "genuine, deterministic input error (F-3.2-A-16), so this is not "
            "certain from the status code alone; retrying after a backoff is "
            "reasonable, and if it recurs unchanged, treat it as an input "
            "problem rather than continuing to retry."
        )
    return (
        f"Variation Services rejected {action} {query_repr}: {text}. This "
        f"is a client-side rejection (HTTP {http_status}, a malformed "
        "input or a nonexistent record), not a transient condition; "
        "retrying the same request will not help. Verify the input is "
        "correct before retrying."
    )


# ---------------------------------------------------------------------------
# Normalization: rsid, via refsnp/{id}, with the merge-follow trap (2 above).
# ---------------------------------------------------------------------------


def _withdrawn_info(body: dict[str, Any]) -> dict[str, Any] | None:
    """F-3.2-A-07: a THIRD refsnp response shape, neither primary nor merged.

    Live-reproduced 2026-08-08 on rs100 and rs386 (`tracker/phase_3.2.md`,
    adversary round 1), and re-confirmed while fixing this finding:
    `GET /variation/v0/refsnp/100` returns `{"refsnp_id": "100", ...,
    "withdrawn_snapshot_data": {"withdrawn_time": "2016-06-17T16:22Z", ...},
    ...}`, with NO `primary_snapshot_data` and NO `merged_snapshot_data`
    key at all. Checked in `_normalize_rsid` BEFORE the merge-follow check
    (`_merged_into_ids`), since a withdrawal is a PERMANENT condition, not
    something a merge chain could ever resolve into a live record.
    """
    withdrawn = body.get("withdrawn_snapshot_data")
    return withdrawn if isinstance(withdrawn, dict) else None


def _merged_into_ids(body: dict[str, Any]) -> list[Any]:
    """Return `merged_snapshot_data.merged_into` when `body` has no `primary_snapshot_data`.

    See the module docstring's trap 2: a refsnp response for a merged rsid
    carries `merged_snapshot_data.merged_into` instead of
    `primary_snapshot_data`. Checking for the ABSENCE of
    `primary_snapshot_data` first (rather than merely checking for the
    presence of `merged_snapshot_data`) means a future response shape that
    carries both would still be treated as already-resolved, which is the
    safer of the two readings: prefer the data that is actually present
    over following a redirect that may not be needed.
    """
    if "primary_snapshot_data" in body:
        return []
    merged = body.get("merged_snapshot_data")
    if isinstance(merged, dict):
        into = merged.get("merged_into")
        if isinstance(into, list) and into:
            return into
    return []


def _extract_canonical_spdi_from_refsnp(
    body: dict[str, Any],
) -> tuple[str, list[str], list[str]] | None:
    """Extract `spdi_canonical` and `alleles` from a resolved refsnp response.

    Reads `primary_snapshot_data.placements_with_allele`, selects the ONE
    placement marked `is_ptlp: true` (the primary top-level placement, the
    current reference assembly's own coordinates; a resolved refsnp
    response carries several other placements too, for prior assembly
    builds and for RefSeq transcript/protein projections, none of which
    are the canonical genomic placement), and within it finds the first
    allele entry whose `deleted_sequence != inserted_sequence` (a genuine
    variant, skipping the self-referential ref-matching entry every
    placement's `alleles` list also carries). `alleles` collects every
    distinct sequence observed at this position (the reference and every
    alternate), in encounter order.

    Returns `None`, never raises, on any of: no `primary_snapshot_data`, no
    `placements_with_allele`, no `is_ptlp` placement, or no variant allele
    found. Fail-closed by design: a placement structure this module cannot
    make sense of is not guessed at.

    Otherwise returns `(spdi_canonical, alleles, withheld_fields)`. Raises
    `_FieldOverflowError` (F-3.2-A-01, caught by `_normalize_rsid`) ONLY
    when `variant_spdi` itself would need truncation to fit its schema cap:
    per the module docstring's "Truncation policy" (F-3.2-A-15, round 2),
    `spdi_canonical` is the sole field this module still refuses the WHOLE
    call for. An over-length or over-count `alleles` list is WITHHELD
    instead (`withheld_fields` contains `"alleles"`, `alleles` returned as
    `[]`), never truncated and never a whole-call refusal: this used to
    truncate silently (`len(alleles) < _MAX_ALLELES` stopped collecting
    extra distinct alleles with no signal, and each allele was
    `_cap()`-truncated before being appended), which is exactly how a real
    14bp allele shipped as a real-looking but WRONG 10bp one under
    `status: "ok"` (the original F-3.2-A-01 defect this module must not
    resurrect).
    """
    psd = body.get("primary_snapshot_data")
    if not isinstance(psd, dict):
        return None
    placements = psd.get("placements_with_allele")
    if not isinstance(placements, list):
        return None
    primary_placement = next(
        (p for p in placements if isinstance(p, dict) and p.get("is_ptlp") is True),
        None,
    )
    if primary_placement is None:
        return None
    entries = primary_placement.get("alleles")
    if not isinstance(entries, list):
        return None

    alleles: list[str] = []
    variant_spdi: str | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        allele_obj = entry.get("allele")
        spdi = allele_obj.get("spdi") if isinstance(allele_obj, dict) else None
        if not isinstance(spdi, dict):
            continue
        deleted = spdi.get("deleted_sequence")
        inserted = spdi.get("inserted_sequence")
        seq_id = spdi.get("seq_id")
        position = spdi.get("position")
        if not isinstance(deleted, str) or not isinstance(inserted, str):
            continue
        if deleted and deleted not in alleles:
            alleles.append(deleted)
        if inserted and inserted not in alleles:
            alleles.append(inserted)
        if (
            variant_spdi is None
            and deleted != inserted
            and seq_id is not None
            and position is not None
        ):
            variant_spdi = f"{seq_id}:{position}:{deleted}:{inserted}"

    if variant_spdi is None:
        return None
    capped_spdi = _cap_or_refuse(variant_spdi, _MAX_SPDI_CHARS, "spdi_canonical")
    withheld_fields: list[str] = []
    if len(alleles) > _MAX_ALLELES or any(len(a) > _MAX_ALLELE_CHARS for a in alleles):
        withheld_fields.append("alleles")
        alleles = []
    return capped_spdi, alleles, withheld_fields


async def _normalize_rsid(raw_rsid: str) -> _NormalizationResult | NcbiDbsnpOutput:
    """Resolve `raw_rsid` to its canonical rsid and SPDI via `refsnp/{id}`.

    Follows a merged/obsolete rsid's `merged_snapshot_data.merged_into`
    (trap 2 above) up to `_MAX_MERGE_HOPS` times before giving up. Any
    non-200 response, or a 200 body that does not carry
    `primary_snapshot_data` with a resolvable variant allele after
    following every merge in the chain, is `status: "error"`: this is the
    resolved open verification gap Section 6.3 and
    `Tool_implementation_mechanics.md` both flagged, confirmed live by
    `tracker/phase_3.2.md`'s pre-build probes (a nonexistent rsid 404s,
    never a 200-with-empty-body).
    """
    current_id = _strip_rs_prefix(raw_rsid)
    hops = 0
    while True:
        url = f"{_VARIATION_BASE}/refsnp/{_quote_path_segment(current_id)}"
        result = await _get_variation(url)
        if isinstance(result, str):
            return _error_output(
                raw_rsid,
                "",
                f"Variation Services refsnp lookup for {raw_rsid!r} failed: {result}. "
                "Retry once; if this recurs, Variation Services may be degraded.",
            )
        if result.classification.status == "error":
            return _error_output(
                raw_rsid,
                "",
                _variation_error_message(
                    "rsid lookup", repr(raw_rsid), result.http_status,
                    result.classification.error_message,
                ),
            )
        body = result.classification.body
        if not isinstance(body, dict):
            return _error_output(
                raw_rsid,
                "",
                f"Variation Services refsnp/{current_id} returned an unrecognized "
                f"response shape for {raw_rsid!r}, refusing to guess its meaning. "
                "Retry once; if this recurs, report it.",
            )

        # F-3.2-A-07: a withdrawn rsid is a THIRD, permanent response shape.
        # Checked BEFORE the merge-follow logic below: no merge chain could
        # ever resolve a withdrawal into a live record, so this is not a
        # "keep following" condition, it is a terminal one.
        withdrawn = _withdrawn_info(body)
        if withdrawn is not None:
            withdrawn_time = withdrawn.get("withdrawn_time")
            time_note = f" (withdrawn {withdrawn_time})" if withdrawn_time else ""
            return _error_output(
                raw_rsid,
                "",
                f"{raw_rsid!r} refers to a WITHDRAWN rsid{time_note}, a "
                "permanent condition. It will never resolve to a live "
                "record; do not retry, and this is not a service error.",
            )

        merged_into = _merged_into_ids(body)
        if merged_into:
            hops += 1
            if hops > _MAX_MERGE_HOPS:
                return _error_output(
                    raw_rsid,
                    "",
                    f"{raw_rsid!r}'s merge chain exceeded {_MAX_MERGE_HOPS} hops "
                    "without resolving to a current rsid with primary_snapshot_data. "
                    "This is unusual; report it rather than retrying.",
                )
            current_id = str(merged_into[0])
            continue

        refsnp_id = body.get("refsnp_id")
        if not refsnp_id:
            return _error_output(
                raw_rsid,
                "",
                f"Variation Services refsnp/{current_id} has no refsnp_id, cannot "
                f"resolve {raw_rsid!r} to a canonical rsid. Retry once; if this "
                "recurs, report it.",
            )

        canonical_rsid = "rs" + str(refsnp_id)
        try:
            extracted = _extract_canonical_spdi_from_refsnp(body)
        except _FieldOverflowError as exc:
            return _error_output(canonical_rsid, "", _overflow_message(exc))
        if extracted is None:
            return _error_output(
                canonical_rsid,
                "",
                f"Variation Services refsnp/{current_id} has no primary top-level "
                f"placement with a resolvable variant allele for {raw_rsid!r}, "
                "cannot determine spdi_canonical. Retry once; if this recurs, "
                "report it.",
            )
        spdi_canonical, alleles, withheld_fields = extracted
        return _NormalizationResult(
            rsid=canonical_rsid,
            numeric_rsid=str(refsnp_id),
            spdi_canonical=spdi_canonical,
            alleles=alleles,
            fields_withheld=withheld_fields,
        )


# ---------------------------------------------------------------------------
# Normalization: spdi, via /spdi/{spdi}/contextual (trap 1's substitution).
# ---------------------------------------------------------------------------


async def _normalize_spdi(raw_spdi: str) -> _NormalizationResult | NcbiDbsnpOutput:
    """Normalize an SPDI expression via `/spdi/{spdi}/contextual`.

    See the module docstring's trap 1 for why this calls `/contextual`
    rather than the spec-named `/canonical_representative`: the latter is
    confirmed live-broken (HTTP 500) on every well-formed input tested,
    including NCBI's own documented example. `rsid` is always `""` on
    success (Variation Services' SPDI-keyed endpoints do not return an
    rsid; see the module docstring), so the clinical fetch never runs for
    this query_type.
    """
    url = f"{_VARIATION_BASE}/spdi/{_quote_path_segment(raw_spdi)}/contextual"
    result = await _get_variation(url)
    if isinstance(result, str):
        return _error_output(
            "",
            raw_spdi,
            f"Variation Services SPDI normalization for {raw_spdi!r} failed: "
            f"{result}. Retry once; if this recurs, Variation Services may be "
            "degraded.",
        )
    if result.classification.status == "error":
        return _error_output(
            "",
            raw_spdi,
            _variation_error_message(
                "SPDI normalization", repr(raw_spdi), result.http_status,
                result.classification.error_message,
            ),
        )
    body = result.classification.body
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return _error_output(
            "",
            raw_spdi,
            f"Variation Services' contextual response for SPDI {raw_spdi!r} has no "
            "'data' object, refusing to guess its meaning. Retry once; if this "
            "recurs, report it.",
        )
    seq_id = data.get("seq_id")
    position = data.get("position")
    deleted = data.get("deleted_sequence")
    inserted = data.get("inserted_sequence")
    if seq_id is None or position is None or deleted is None or inserted is None:
        return _error_output(
            "",
            raw_spdi,
            f"Variation Services' contextual response for SPDI {raw_spdi!r} is "
            "missing seq_id/position/deleted_sequence/inserted_sequence, cannot "
            "normalize it. Retry once; if this recurs, report it.",
        )
    spdi_canonical = f"{seq_id}:{position}:{deleted}:{inserted}"
    try:
        capped_spdi = _cap_or_refuse(spdi_canonical, _MAX_SPDI_CHARS, "spdi_canonical")
    except _FieldOverflowError as exc:
        return _error_output("", raw_spdi, _overflow_message(exc))
    # F-3.2-A-15: an over-length or over-count alleles pair is WITHHELD, not
    # refused; see _extract_canonical_spdi_from_refsnp's docstring for the
    # same reasoning applied to the rsid-keyed normalization path.
    raw_alleles = [str(a) for a in (deleted, inserted) if a]
    withheld_fields: list[str] = []
    if len(raw_alleles) > _MAX_ALLELES or any(len(a) > _MAX_ALLELE_CHARS for a in raw_alleles):
        withheld_fields.append("alleles")
        raw_alleles = []
    return _NormalizationResult(
        rsid="",
        numeric_rsid=None,
        spdi_canonical=capped_spdi,
        alleles=raw_alleles,
        fields_withheld=withheld_fields,
    )


# ---------------------------------------------------------------------------
# Normalization: hgvs, via /hgvs/{hgvs}/contextuals.
# ---------------------------------------------------------------------------


async def _normalize_hgvs(raw_hgvs: str) -> _NormalizationResult | NcbiDbsnpOutput:
    """Normalize an HGVS expression via `/hgvs/{hgvs}/contextuals`.

    Section 6.3 requires `>` be percent-encoded (`%3E`) before the call;
    `_quote_path_segment`'s full path-segment encoding does this as part
    of encoding the whole expression, live-confirmed to also require the
    `:` characters encoded (see that helper's own docstring). `rsid` is
    always `""` on success, the same reasoning as `_normalize_spdi`.
    """
    url = f"{_VARIATION_BASE}/hgvs/{_quote_path_segment(raw_hgvs)}/contextuals"
    result = await _get_variation(url)
    if isinstance(result, str):
        return _error_output(
            "",
            raw_hgvs,
            f"Variation Services HGVS normalization for {raw_hgvs!r} failed: "
            f"{result}. Retry once; if this recurs, Variation Services may be "
            "degraded.",
        )
    if result.classification.status == "error":
        return _error_output(
            "",
            raw_hgvs,
            _variation_error_message(
                "HGVS normalization", repr(raw_hgvs), result.http_status,
                result.classification.error_message,
            ),
        )
    body = result.classification.body
    data = body.get("data") if isinstance(body, dict) else None
    spdis = data.get("spdis") if isinstance(data, dict) else None
    if not isinstance(spdis, list) or not spdis:
        return _error_output(
            "",
            raw_hgvs,
            f"Variation Services' contextuals response for HGVS {raw_hgvs!r} "
            "carries no spdis, cannot normalize it. Retry once; if this recurs, "
            "report it.",
        )
    first = spdis[0]
    if not isinstance(first, dict):
        return _error_output(
            "",
            raw_hgvs,
            f"Variation Services' contextuals response for HGVS {raw_hgvs!r} has "
            "a malformed spdis entry, refusing to guess its meaning.",
        )
    seq_id = first.get("seq_id")
    position = first.get("position")
    deleted = first.get("deleted_sequence")
    inserted = first.get("inserted_sequence")
    if seq_id is None or position is None or deleted is None or inserted is None:
        return _error_output(
            "",
            raw_hgvs,
            f"Variation Services' contextuals response for HGVS {raw_hgvs!r} is "
            "missing seq_id/position/deleted_sequence/inserted_sequence, cannot "
            "normalize it. Retry once; if this recurs, report it.",
        )
    spdi_canonical = f"{seq_id}:{position}:{deleted}:{inserted}"
    try:
        capped_spdi = _cap_or_refuse(spdi_canonical, _MAX_SPDI_CHARS, "spdi_canonical")
    except _FieldOverflowError as exc:
        return _error_output("", raw_hgvs, _overflow_message(exc))
    # F-3.2-A-15: same withhold-not-refuse treatment as _normalize_spdi.
    raw_alleles = [str(a) for a in (deleted, inserted) if a]
    withheld_fields: list[str] = []
    if len(raw_alleles) > _MAX_ALLELES or any(len(a) > _MAX_ALLELE_CHARS for a in raw_alleles):
        withheld_fields.append("alleles")
        raw_alleles = []
    return _NormalizationResult(
        rsid="",
        numeric_rsid=None,
        spdi_canonical=capped_spdi,
        alleles=raw_alleles,
        fields_withheld=withheld_fields,
    )


# ---------------------------------------------------------------------------
# Clinical fetch: dbSNP ESummary, keyed on the CANONICAL numeric rsid only.
# ---------------------------------------------------------------------------


async def _fetch_esummary_entry(numeric_rsid: str) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch dbSNP ESummary for `numeric_rsid`. Returns `(entry, None)` or `(None, message)`.

    Uses `classify_eutils_response` (the E-utilities body-inspecting
    classifier, never `classify_status_coded_response`), since ESummary is
    an E-utilities endpoint and follows E-utilities' 200-with-body
    convention, the opposite of Variation Services' proper status codes.
    """
    try:
        response = await ncbi_transport.execute_get(
            _ESUMMARY_ENDPOINT,
            {"db": "snp", "id": numeric_rsid, "retmode": "json"},
            family="eutils",
            include_api_key=True,
        )
    except ncbi_transport.TransportError as exc:
        return None, str(exc)

    status_message = ncbi_transport.http_status_error_message("dbSNP ESummary", response)
    if status_message is not None:
        return None, status_message

    result = ncbi_transport.classify_eutils_response(
        content_type=response.headers.get("content-type", ""), text=response.text
    )
    if result.status == "error":
        return None, result.error_message or (
            "dbSNP ESummary returned an unrecognized response shape"
        )
    # classify_eutils_response only ever collapses to "empty" for an
    # esearchresult envelope with count "0" (its own docstring); an
    # ESummary "result" envelope is always "ok" or "error" from that
    # classifier. Handled as "ok" defensively below rather than assumed.
    body = result.body
    envelope = body.get("result") if isinstance(body, dict) else None
    entry = envelope.get(numeric_rsid) if isinstance(envelope, dict) else None
    if not isinstance(entry, dict):
        return None, f"dbSNP ESummary has no entry for id {numeric_rsid!r}"
    if "error" in entry:
        # F-3.1-13's shape, reused: {"uid": ..., "error": "..."} for a
        # per-uid failure inside an otherwise-ok envelope. Since this
        # numeric id was already confirmed to resolve via Variation
        # Services one step earlier, reaching this path means ESummary
        # itself is degraded for this exact id; fail closed rather than
        # build a citation around an empty entry.
        return None, f"dbSNP ESummary could not summarize id {numeric_rsid!r}: {entry.get('error')}"
    return entry, None


def _spdi_alleles(spdi_canonical: str) -> tuple[str, str] | None:
    """Split `spdi_canonical`'s own DELETED and INSERTED alleles out of `seq_id:position:deleted:inserted`.

    F-3.2-A-03: this is what lets `_allele_role` attribute each
    `population_frequencies` row back to `spdi_canonical`'s own two
    alleles without re-deriving them from a second source. Returns `None`,
    never raises, when `spdi_canonical` is empty or not in the expected
    4-part colon-separated shape.
    """
    if not spdi_canonical:
        return None
    parts = spdi_canonical.split(":")
    if len(parts) != 4:
        return None
    return parts[2], parts[3]


def _allele_role(spdi_canonical: str, allele: str) -> Literal["variant", "reference", "other"] | None:
    """F-3.2-A-03: this population_frequencies row's relationship to `spdi_canonical`.

    See `ncbi_dbsnp_schemas.py`'s design decision 6 for the full reasoning
    behind labeling rather than reselecting which allele `spdi_canonical`
    names.
    """
    alleles = _spdi_alleles(spdi_canonical)
    if alleles is None:
        return None
    deleted, inserted = alleles
    if allele == inserted:
        return "variant"
    if allele == deleted:
        return "reference"
    return "other"


def _parse_global_mafs(
    raw: Any, spdi_canonical: str
) -> tuple[list[NcbiDbsnpPopulationFrequency], str | None, str | None]:
    """F-3.2-01: parse `global_mafs[].freq` (`"<allele>=<freq>/<n>"`) into structured entries.

    Returns `(entries, error_message, withheld_field)`. Two DISTINCT failure
    shapes, deliberately kept separate:

    MALFORMED data (`error_message` set, `entries`/`withheld_field`
    irrelevant): a shape this module cannot make sense of AT ALL, a non-list
    `global_mafs`, a non-object entry, a non-string `freq`, or a `freq`
    string that does not match `_GLOBAL_MAFS_FREQ_PATTERN`. This is a DATA-
    INTEGRITY problem, per the allowlist-not-blocklist discipline
    `ai-security-standards.md` and LEARNINGS.md row 56 both require: this is
    untrusted upstream content, and a malformed entry still fails the WHOLE
    call closed, UNCHANGED by F-3.2-A-15 (round 2), because this module
    cannot safely guess what a malformed entry meant. `raw is None` (the
    field absent) and `raw == []` (Section 6.3 line 1074's "no population
    data is a fact, not a failure") both return `([], None, None)`, never an
    error.

    CAP OVERFLOW (`withheld_field == "population_frequencies"`, `entries ==
    []`, `error_message is None`): every entry is well-formed and
    PARSEABLE, but the list itself, or one entry's `population`/`allele`,
    would need truncation to fit its schema cap. F-3.2-A-15 (round 2)
    changed this from a whole-call refusal to a per-field WITHHOLD: the
    caller (`_ncbi_dbsnp_impl`) appends `"population_frequencies"` to the
    output's `fields_withheld` list and ships the rest of the record under
    `status: "ok"`, rather than discarding an otherwise successful fetch
    over one over-cap population row. This is field-level, not row-level:
    ANY row's overflow withholds the WHOLE `population_frequencies` field,
    it does not selectively drop just the offending row. See the module
    docstring's "Truncation policy" section for the full reasoning.

    F-3.2-A-03: `spdi_canonical` is threaded in so every entry's
    `allele_role` can be computed against it (`_allele_role`), so a caller
    can tell which rows describe the SAME allele `spdi_canonical` names
    versus the reference or a third allele at a multiallelic site.
    """
    if raw is None:
        return [], None, None
    if not isinstance(raw, list):
        return [], "dbSNP ESummary's global_mafs field is not a list, refusing to guess its meaning", None

    overflow = len(raw) > _MAX_POP_FREQS
    entries: list[NcbiDbsnpPopulationFrequency] = []
    for item in raw:
        if not isinstance(item, dict):
            return [], (
                f"dbSNP ESummary's global_mafs contains a non-object entry "
                f"({item!r}), refusing to guess its meaning"
            ), None
        study = item.get("study")
        freq_raw = item.get("freq")
        if not isinstance(freq_raw, str):
            return [], (
                f"F-3.2-01: dbSNP ESummary's global_mafs entry for {study!r} has a "
                f"non-string freq value ({freq_raw!r})"
            ), None
        match = _GLOBAL_MAFS_FREQ_PATTERN.match(freq_raw)
        if match is None:
            return [], (
                f"F-3.2-01: dbSNP ESummary's global_mafs freq value {freq_raw!r} "
                "does not match the expected '<allele>=<float>/<int>' shape, "
                "refusing to guess its meaning. Report this; NCBI's response "
                "shape may have changed."
            ), None
        allele = match.group("allele")
        try:
            frequency = float(match.group("freq"))
        except ValueError:
            return [], (
                f"F-3.2-01: dbSNP ESummary's global_mafs freq value {freq_raw!r} "
                "has an unparseable numeric part"
            ), None

        # F-3.2-A-15: a cap overflow WITHHOLDS the whole field rather than
        # refusing the whole call. Once known, stop building entries (they
        # will be discarded anyway) but keep looping: a later MALFORMED
        # entry is a worse, still fail-closed condition and must still be
        # caught even after an earlier entry already triggered a withhold.
        if study is not None and len(str(study)) > _MAX_POP_NAME_CHARS:
            overflow = True
            continue
        if len(allele) > _MAX_POP_ALLELE_CHARS:
            overflow = True
            continue
        if overflow:
            continue
        entries.append(
            NcbiDbsnpPopulationFrequency(
                population=str(study) if study else None,
                allele=allele,
                frequency=frequency,
                allele_role=_allele_role(spdi_canonical, allele),
            )
        )
    if overflow:
        return [], None, "population_frequencies"
    return entries, None, None


def _split_comma_field(raw: Any, max_items: int, max_chars: int, field: str) -> tuple[list[str], bool]:
    """F-3.2-02: split a comma-joined ESummary string field, stripping and dropping empties.

    An empty raw string (no value reported) becomes `[]` here, never
    `[""]`, which plain `str.split(",")` would otherwise produce.

    F-3.2-A-15 (round 2): returns `(pieces, overflowed)`. `overflowed=True`
    means the list, or one piece, exceeded its schema cap; the caller
    (`_ncbi_dbsnp_impl`) withholds the WHOLE field (empty list, `field`
    appended to `fields_withheld`) rather than the round-1 behavior of
    refusing the whole call. Never truncates or shortens a piece: a value
    is either present in full or absent with a signal, never trimmed. This
    used to be exactly how "conflicting-interpretations-of-pathogenic"
    shipped as "conflicting-interpretations-of-pathogeni", a DIFFERENT real
    term, and how an 11-entry clinical_significance list shipped as 10 with
    "likely-pathogenic" silently dropped, both under `status: "ok"`; round
    1 fixed that by refusing the whole call, and round 2 (this revision)
    narrowed the blast radius to the one field, per F-3.2-A-15's live
    finding that ~10 percent of real clinically-cited variants hit exactly
    this cap and lost their whole record over it.
    """
    if not isinstance(raw, str) or not raw:
        return [], False
    pieces = [piece.strip() for piece in raw.split(",") if piece.strip()]
    if len(pieces) > max_items or any(len(piece) > max_chars for piece in pieces):
        return [], True
    return pieces, False


def _parse_genes(raw: Any) -> tuple[list[NcbiDbsnpGene], bool]:
    """Map ESummary's `genes` (already `[{"name", "gene_id"}, ...]`) onto `NcbiDbsnpGene`.

    Unlike `global_mafs`/`clinical_significance`/`fxn_class`, this field's
    raw shape already matches the output contract's shape; this function
    only applies the length caps and constructs the typed model, it does
    not need to re-parse a compound or comma-joined string.

    F-3.2-A-15 (round 2): returns `(genes, overflowed)`, the same
    field-level withhold-not-refuse contract as `_split_comma_field` above:
    `overflowed=True` (with `genes == []`) means the list itself, or one
    gene's `name`/`gene_id`, exceeded its schema cap. NEW-3 (carried
    forward, not this round's job): a non-dict entry in `raw` is still
    silently skipped via `continue`, unchanged from before this fix.
    """
    if not isinstance(raw, list):
        return [], False
    if len(raw) > _MAX_GENES:
        return [], True
    genes: list[NcbiDbsnpGene] = []
    overflow = False
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        gene_id = item.get("gene_id")
        if name and len(str(name)) > _MAX_GENE_NAME_CHARS:
            overflow = True
            continue
        if gene_id and len(str(gene_id)) > _MAX_GENE_ID_CHARS:
            overflow = True
            continue
        genes.append(
            NcbiDbsnpGene(
                name=str(name) if name else None,
                gene_id=str(gene_id) if gene_id else None,
            )
        )
    if overflow:
        return [], True
    return genes, False


def _build_source_url(rsid: str) -> str | None:
    """`https://www.ncbi.nlm.nih.gov/snp/{rsid}`, or `None` when `rsid` is empty.

    Re-checks the built URL against `NCBI_DBSNP_RECORD_URL_PATTERN` as
    defense in depth on top of `NcbiDbsnpOutput`'s own schema-level pattern
    validator, the same "fail closed to no citation rather than raise"
    discipline `ncbi_eutils_actions._build_record_url` uses: a wrong URL
    here should never surface as a `pydantic.ValidationError` out of a
    tool call.
    """
    if not rsid:
        return None
    url = "https://www.ncbi.nlm.nih.gov/snp/" + _quote_path_segment(rsid)
    if re.match(NCBI_DBSNP_RECORD_URL_PATTERN, url) is None:
        return None
    return url


async def _ncbi_dbsnp_impl(tool_input: NcbiDbsnpInput) -> NcbiDbsnpOutput:
    """The real implementation. See `ncbi_dbsnp` below for the never-raises wrapper."""
    query = tool_input.query
    query_type = tool_input.query_type

    if query_type == "rsid":
        normalization = await _normalize_rsid(query)
    elif query_type == "spdi":
        normalization = await _normalize_spdi(query)
    elif query_type == "hgvs":
        normalization = await _normalize_hgvs(query)
    else:
        # Defensive, not assumed impossible: query_type is a closed
        # Literal["rsid", "hgvs", "spdi"] pydantic has already validated,
        # so every branch above is reachable by construction and this one
        # exists only as a last resort, matching ncbi_efetch.py's own
        # trailing-branch discipline for its action dispatch.
        return _error_output(
            "",
            "",
            f"ncbi_dbsnp has no normalization branch for query_type {query_type!r}. "
            "This is a tool defect, not a caller error; report it rather than "
            "retrying.",
        )

    if isinstance(normalization, NcbiDbsnpOutput):
        return normalization

    if normalization.numeric_rsid is None:
        # F-3.2-A-06: this query_type (spdi/hgvs) never resolved a numeric
        # rsid to key ESummary on, so no citable source_url is, or ever
        # will be, available for it (see the module docstring). Reporting
        # this as "ok" was a permanent, uncited confident claim; "empty" is
        # correct here, distinct from "error", since normalization itself
        # genuinely succeeded. fields_withheld (F-3.2-A-15) carries forward
        # anything the normalization step itself withheld (only ever
        # "alleles" on this path).
        return NcbiDbsnpOutput(
            status="empty",
            rsid=normalization.rsid,
            spdi_canonical=normalization.spdi_canonical,
            alleles=normalization.alleles,
            source_url=None,
            fields_withheld=list(normalization.fields_withheld),
            error=(
                "Variant normalized successfully via Variation Services, "
                "but this query_type does not resolve a dbSNP rsid, so no "
                "citable source_url is available for this record. Query "
                "by rsid instead if a citation is required."
            ),
        )

    if not tool_input.include_clinical:
        # F-3.2-A-05 (carried forward): the caller explicitly opted out of
        # the clinical fetch. A real rsid was resolved (checked above), so
        # source_url IS available here, unlike the spdi/hgvs branch above.
        return NcbiDbsnpOutput(
            status="ok",
            rsid=normalization.rsid,
            spdi_canonical=normalization.spdi_canonical,
            alleles=normalization.alleles,
            source_url=_build_source_url(normalization.rsid),
            fields_withheld=list(normalization.fields_withheld),
        )

    entry, clinical_error = await _fetch_esummary_entry(normalization.numeric_rsid)
    if entry is None:
        return _error_output(
            normalization.rsid,
            normalization.spdi_canonical,
            f"normalization succeeded ({normalization.rsid}) but the dbSNP "
            f"ESummary clinical fetch failed: {clinical_error}. Retry once; if "
            "this recurs, call again with include_clinical=False for the "
            "normalization result alone.",
        )

    # F-3.2-A-15 (round 2): every field parsed below WITHHOLDS itself (empty
    # default, name appended here) rather than refusing the whole call when
    # it overflows its schema cap. Only a genuinely MALFORMED global_mafs
    # entry (a data-integrity problem, not a cap-length one) still refuses
    # the whole call, via mafs_error below, UNCHANGED from F-3.2-01.
    fields_withheld: list[str] = list(normalization.fields_withheld)

    population_frequencies, mafs_error, mafs_withheld = _parse_global_mafs(
        entry.get("global_mafs"), normalization.spdi_canonical
    )
    if mafs_error is not None:
        return _error_output(normalization.rsid, normalization.spdi_canonical, mafs_error)
    if mafs_withheld is not None:
        fields_withheld.append(mafs_withheld)

    clinical_significance, cs_overflow = _split_comma_field(
        entry.get("clinical_significance"),
        _MAX_CLINICAL_SIG_ITEMS,
        _MAX_CLINICAL_SIG_CHARS,
        "clinical_significance",
    )
    if cs_overflow:
        fields_withheld.append("clinical_significance")

    functional_consequence, fc_overflow = _split_comma_field(
        entry.get("fxn_class"),
        _MAX_FXN_CLASS_ITEMS,
        _MAX_FXN_CLASS_CHARS,
        "functional_consequence",
    )
    if fc_overflow:
        fields_withheld.append("functional_consequence")

    genes, genes_overflow = _parse_genes(entry.get("genes"))
    if genes_overflow:
        fields_withheld.append("genes")

    chrpos_raw = entry.get("chrpos")
    chrpos: str | None = None
    if chrpos_raw:
        chrpos, chrpos_withheld = _cap_or_withhold(str(chrpos_raw), _MAX_CHRPOS_CHARS, "chrpos")
        if chrpos_withheld is not None:
            fields_withheld.append(chrpos_withheld)

    return NcbiDbsnpOutput(
        status="ok",
        rsid=normalization.rsid,
        spdi_canonical=normalization.spdi_canonical,
        alleles=normalization.alleles,
        chrpos=chrpos,
        clinical_significance=clinical_significance,
        functional_consequence=functional_consequence,
        genes=genes,
        population_frequencies=population_frequencies,
        source_url=_build_source_url(normalization.rsid),
        fields_withheld=fields_withheld,
    )


async def ncbi_dbsnp(tool_input: NcbiDbsnpInput) -> NcbiDbsnpOutput:
    """Variant normalization and dbSNP record retrieval. Never raises.

    See the module docstring for the two-call sequential procedure. This
    public entry point is a thin wrapper around `_ncbi_dbsnp_impl`: every
    expected failure (a transport error, a rejected input, a malformed
    upstream field) is already classified and returned as a `status:
    "error"` output by the functions above. This wrapper's own
    `try`/`except` is the last-resort boundary for an UNEXPECTED exception
    (a `KeyError`, an `AttributeError` surfacing a genuine defect), the
    same outer-boundary pattern `ncbi_efetch.py`'s dispatcher uses, per
    `.claude/rules/production-standards.md`'s retry-safety gate: an error
    message must say what to do next, not just what failed.
    """
    try:
        return await _ncbi_dbsnp_impl(tool_input)
    except Exception as exc:  # noqa: BLE001 - the module's deliberate last-resort catch
        return _error_output(
            "",
            "",
            f"ncbi_dbsnp raised an unexpected {type(exc).__name__} instead of "
            f"returning a classified result: {exc}. Retry once; if this recurs, "
            "this tool has a defect that needs fixing before it can be trusted.",
        )


# ---------------------------------------------------------------------------
# T-3.4-04: citation-building. Section 9.2's per-tool `CitationPayload`.
# ---------------------------------------------------------------------------


def _mint_citation_id(prefix: str, seed: str, display_index: int) -> str:
    """A short, deterministic-shaped citation id, mirroring `core/graph.py`'s
    `_citation_for_row` pattern (a stable id plus a display-index suffix),
    adapted for a tool with no `call_id` of its own: the id is minted from a
    short hash of the real source id instead. Only needs to be non-colliding
    within one tool's own output, not globally unique across a whole answer.
    """
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"{prefix}-{digest}-{display_index}"[:64]


def _population_ancestry_context(result: NcbiDbsnpOutput) -> str | None:
    """A short, honest summary of which populations `population_frequencies`
    actually reports data for, or `None` when there is nothing to report.

    Never fabricates an ancestry group: dbSNP's `global_mafs` names
    contributing STUDIES/populations (e.g. "1000Genomes", "TOPMED", "ALFA"),
    not a normalized ancestry taxonomy, so this states exactly what the
    tool's own real data carries, capped to the schema's own 256-char limit
    on `CitationPayload.population_ancestry_context`.
    """
    names = [pf.population for pf in result.population_frequencies if pf.population]
    if not names:
        return None
    unique_names = list(dict.fromkeys(names))
    context = "Population frequency data reported for: " + ", ".join(unique_names)
    return context[:256]


def build_citation(
    result: NcbiDbsnpOutput, field: str, display_index: int = 1
) -> CitationPayload:
    """Build a Section 9.2 `CitationPayload` from a real `ncbi_dbsnp` result.

    Raises `ValueError` with an actionable message, never returns a
    placeholder, when `result` carries no `source_url` (nothing to cite,
    per production-standards.md's cite-or-refuse gate) or no real value for
    `field`.

    `evidence_kind` and `license` come from
    `provenance_defaults.defaults_for_tool("ncbi_dbsnp")`. `assertion_
    confidence`: when `field == "clinical_significance"`,
    `clinvar_term_confidence` decides it from the first reported term (a
    `list[str]` per this tool's own schema); every other field defaults to
    `"asserted"`, this tool's structured, non-hedged data. `population_
    ancestry_context` reports the real population labels
    `population_frequencies` carries, or an honest `None` when it carries
    none; it is NEVER an `assembly` field, which belongs on the separate
    `AsOfMarker` (Section 7.3, T-3.4-06's own scope), not on
    `CitationPayload`.
    """
    if not result.source_url:
        raise ValueError(
            f"ncbi_dbsnp result for rsid {result.rsid!r} has no source_url; "
            "refusing to build a citation rather than fabricate one."
        )

    defaults = defaults_for_tool("ncbi_dbsnp")
    if field == "clinical_significance":
        if not result.clinical_significance:
            raise ValueError(
                f"ncbi_dbsnp result for rsid {result.rsid!r} has no "
                "clinical_significance values to cite."
            )
        confidence = clinvar_term_confidence(result.clinical_significance[0])
        value_repr = ", ".join(result.clinical_significance)
    else:
        value = getattr(result, field, None)
        if value in (None, "", []):
            raise ValueError(
                f"ncbi_dbsnp result for rsid {result.rsid!r} has no real value "
                f"for field {field!r} to cite; refusing to fabricate one."
            )
        confidence = "asserted"
        value_repr = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)

    source_id = (result.rsid or "unknown")[:128]
    claim_text = f"dbSNP {source_id}: {field}={value_repr}"[:1000]

    return CitationPayload(
        citation_id=_mint_citation_id("ncbidbsnp", source_id, display_index),
        display_index=display_index,
        source="dbsnp"[:128],
        source_id=source_id,
        source_url=result.source_url,
        layer="layer_2_api",
        field=field[:128],
        claim_text=claim_text,
        evidence_kind=defaults["evidence_kind"],
        assertion_confidence=confidence,
        population_ancestry_context=_population_ancestry_context(result),
        license=defaults["license"],
    )
