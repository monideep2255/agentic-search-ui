# Phase 3.2: ncbi_dbsnp, the second Layer 2 tool

Build phase 3.2 delivers `ncbi_dbsnp`: variant normalization and dbSNP record retrieval over two sequential API families, NCBI Variation Services (primary, canonical SPDI normalization) and dbSNP ESummary via E-utilities (secondary, clinical and population fields).

Depends on: build phase 3.1 (done, PR #23) and build phase 3.0 (done, PR #19)
Branch: `phase/3.2-ncbi-dbsnp`
Spec: `requirements/Technical_specification.md` Section 6.3, with Section 21.1 for rate limits
Reference: `docs/ncbi/Tool_implementation_mechanics.md`, `.claude/rules/tool-call-budgets.md`, `LEARNINGS.md` build phase 3.1 entries and the build phase 2.1 retrospective

## Scope note: Section 25's build order line for this phase names a deliverable already shipped

`requirements/Technical_specification.md` Section 25 lists this phase's delivery as: "`ncbi_dbsnp` over Variation Services, plus the Q1 dbVar two-step coordinate-overlap sub-tool (ESearch prefilter, placement post-filter)". The second half of that sentence is not new work. It is the same five-step placement procedure Section 6.2 (`ncbi_efetch`) describes, and it already shipped in build phase 3.1 as ticket T-3.1-10, `tools/ncbi_coordinate_overlap.py`, the `coordinate_overlap` action of `ncbi_efetch`. It went through both 3.1 re-review rounds: F-3.1-02 (chromosome never compared), F-3.1-15 (`chr1` spelling), F-3.1-24 (`total_available` honesty), F-3.1-27 (inverted/zero-length windows), and F-3.1-40 (unencoded citation ids) are all `closed` in `tracker/phase_3.1.md`'s Findings table, all against this exact code path.

This is a genuine spec-versus-reality gap, not a judgment call to route around silently, per `.claude/rules/goal-contracts.md`'s "a builder that thinks one of them is wrong reports it; it does not work around it." Filed here rather than fixed unilaterally, and carried to the Step 6.2 reconciliation of Section 25 (see `tracker/BOARD.md`'s Open flags, alongside the other Section 25 divergences already tracked there such as F-2.1-01 and F-2.1-16). This phase's actual code scope is `ncbi_dbsnp` over Variation Services and dbSNP ESummary only. No ticket below duplicates `ncbi_coordinate_overlap.py`.

## Phase premise (the done-when)

A question resolving to a real, well-known dbSNP variant (rs334, the HbS sickle-cell missense variant, already the canonical example this repo uses for LitVar2 in Section 6.5) comes back from `ncbi_dbsnp` with the correct canonical SPDI, correct clinical significance and gene linkage, and population frequency data read only from `global_mafs`, never the null `global_maf` scalar. A malformed or nonexistent rsid, SPDI, or HGVS expression is classified `error`, not fabricated as `ok` and not silently swallowed. The tool's two calls, Variation Services normalization and the dbSNP ESummary clinical fetch, run strictly sequentially, the clinical fetch keyed on the canonical id the normalization call returned, never on the caller's raw input.

Unlike build phase 3.1's premise gate (skipped on end-to-end case 16 because the AGE graph tunnel is unreachable from this environment), Variation Services and E-utilities are both plain public HTTPS APIs reachable directly from here. This phase's premise gate has no tunnel-gated skip; every case can be run live, and case 16's shape is not repeated.

The verify surface is `tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py`, not a suite total, per `tracker/phase_3.1.md`'s standing rule.

Per `tracker/phase_3.1.md`'s F-3.1-04 carry, this phase, like 3.1, delivers the tool itself. Whether `ncbi_dbsnp` is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision already carried to T-3.1-28 for `ncbi_efetch`, and this phase does not resolve it unilaterally either. `ncbi_dbsnp` registers into the tool schema and the stable prompt prefix; `act_node` wiring is out of scope here, same as 3.1.

## Pre-build live probes (done before any tool code, before any fixture)

Per LEARNINGS.md row 60 (build phase 3.1 adversary round 1): two of that phase's criticals shipped because their fixtures were hand-authored from a reading of NCBI documentation rather than captured from a live response. Applying that lesson here, before writing any ticket's fixtures:

| Probe | Result | What it resolves |
|-------|--------|-------------------|
| `GET /variation/v0/refsnp/334` | HTTP 200, real `refsnp_id`, `present_obs_movements`, citations | The `ok` baseline |
| `GET /variation/v0/refsnp/999999999999` (nonexistent rsid) | HTTP 404, body `{"error":{"code":404,"message":"RefSNP not found"}}` | Closes the Section 6.3 / Tool_implementation_mechanics.md open verification gap. Variation Services does NOT return 200-with-empty-body for a nonexistent rsid the way E-utilities does; it returns a genuine 404. The spec's defensive fallback ("any non-200 response... is `status: error`") is confirmed correct, and there is no reachable `status: "empty"` case on this endpoint via a bad rsid; a malformed input is `error`, full stop |
| `GET /variation/v0/spdi/not-a-real-spdi/canonical_representative` | HTTP 400, body `{"error":{"code":400,"message":"Invalid SPDI: 'not-a-real-spdi'"}}` | Confirms the same non-200-is-error contract on the SPDI endpoint for syntactically invalid input |
| `GET /variation/v0/spdi/NC_000011.10:5227001:T:A/canonical_representative` (a real allele read directly off rs334's own ESummary `spdi` field) | HTTP 500, body `{"error":{"code":500,"message":"Internal error"}}` | UNRESOLVED. A seemingly well-formed, real SPDI 500s on this endpoint. Not yet explained (candidates: interbase 0-based-vs-1-based position mismatch between ESummary's `spdi` field and what this endpoint expects, or a required parameter this probe omitted). T-3.2-04 must resolve this with further live probing before trusting any canonical-SPDI code path; do not paper over a 500 with a generic error mapping until the actual cause is known, since a systematic 500 on real input would make the tool's primary path unusable |
| `GET /variation/v0/hgvs/NM_000518.5%3Ac.20A%3ET/contextuals` (a real HBB coding change, URL-encoded per Section 6.3's own note that `>` must be `%3E`) | HTTP 200, `{"data":{"spdis":[{"seq_id":"NM_000518.5","position":69,...}],"input_hgvs_validity":"valid"}}` | Confirms the HGVS path works for well-formed input, and confirms SPDI positions are 0-based interbase (transcript offset 69 for `c.20`, not 20 or 19), the likely lead behind the canonical_representative 500 above |
| `GET /variation/v0/hgvs/not-real-hgvs/contextuals` | HTTP 400 | Same non-200-is-error contract, third endpoint |
| `esummary.fcgi?db=snp&id=334&retmode=json` | HTTP 200, real body | See two new findings below |

Two things this probe surfaced that are not documented anywhere in the locked spec or `Tool_implementation_mechanics.md`, filed as new findings rather than absorbed silently:

### F-3.2-01: dbSNP ESummary's `global_mafs[].freq` is a compound string, not separate fields

Severity: would be critical if shipped unnoticed. Status: filed at design time, owned by T-3.2-04.

Live body: `"global_mafs": [{"study": "1000Genomes", "freq": "A=0.027356/137"}, ...]`. The output schema's `population_frequencies` shape is `{population, allele, frequency}`, three separate fields, but the raw API gives one string combining allele and frequency with a sample-count suffix (`A=0.027356/137` reads as allele `A`, frequency `0.027356`, sample size `137`). A naive read of "the field is already named `freq`, use it as the frequency" produces a `frequency` field holding the string `"A=0.027356/137"` where the schema requires a `number`, which either fails Pydantic validation outright (the safe failure) or, if the field were typed loosely, ships a nonsensical value. T-3.2-04 must parse this string (`allele=freq_string.split("=")[0]`, `frequency=float(freq_string.split("=")[1].split("/")[0])`) and must fail closed, `status: "error"`, rather than crash or silently drop the row, on any `freq` string that does not match the expected `<allele>=<float>/<int>` shape, since this is untrusted upstream content per the allowlist-not-blocklist discipline `ai-security-standards.md` and LEARNINGS.md row 56 both require.

### F-3.2-02: `clinical_significance` and `fxn_class` are comma-separated strings in ESummary, not arrays

Severity: would be critical if shipped unnoticed. Status: filed at design time, owned by T-3.2-04.

Live body: `"clinical_significance": "not-provided,protective,likely-benign,pathogenic,other"`, `"fxn_class": "coding_sequence_variant,missense_variant"`. Both are single comma-joined strings in the raw ESummary response. The output schema requires both as arrays (`maxItems: 10`). A field extraction that copies the raw string into an array-typed output field fails validation or, worse, silently wraps the whole string as a single one-element array (`["not-provided,protective,likely-benign,pathogenic,other"]`), which is technically schema-valid and semantically wrong: a caller checking `"pathogenic" in clinical_significance` gets `False` for a variant ESummary itself calls pathogenic. T-3.2-04 must split on `,` and strip whitespace, mirroring how `ncbi_eutils_actions.py` already handles ClinVar's own multi-value ESummary fields for `ncbi_efetch`. An empty string (no value reported) splits to `[""]` in Python; guard for that and emit `[]` instead, not a one-element array holding an empty string.

## Ticket map

| Ticket | Slice | Files |
|--------|-------|-------|
| T-3.2-01 | The premise gate, blocking | `tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py` |
| T-3.2-02 | Transport: add the `variation` rate-limit family (~1 req/s, its own pool, separate from `eutils`) to the shared transport module | `tools/ncbi_transport.py` |
| T-3.2-03 | Schemas: input (rsid/hgvs/spdi discriminated by `query_type`), output, a local host-pinned `NCBI_DBSNP_RECORD_URL_PATTERN` scoped to `/snp/` (Section 6.3's pattern is narrower than `NCBI_EFETCH_RECORD_URL_PATTERN`, which has no path requirement) | `tools/ncbi_dbsnp_schemas.py` |
| T-3.2-04 | The tool itself: Variation Services normalization (`refsnp`, `spdi/.../canonical_representative`, `spdi/.../all_equivalent_contextual`, `hgvs/.../contextuals`) run first, then the dbSNP ESummary clinical fetch keyed on the resolved canonical id, strictly sequential, never parallel. Owns F-3.2-01, F-3.2-02, and resolving the canonical_representative 500 above. Resolves the two Open verification gaps from `Tool_implementation_mechanics.md` for this tool | `tools/ncbi_dbsnp.py` |
| T-3.2-05 | Tool registration: `ncbi_dbsnp` into the tool registry and the stable prompt prefix, in alphabetical position between `cypher_query` and `ncbi_efetch`, with a `TOOL_REGISTRY_VERSION` bump per the fingerprint gate F-3.1-11 built | `harness/cache.py` |

Depends-on chain: T-3.2-01 blocks everything (written and watched failing first). T-3.2-02 and T-3.2-03 have no dependency on each other. T-3.2-04 depends on both. T-3.2-05 depends on T-3.2-04.

Dispatch plan, stated because this session is not running inside tmux (`tmux` is installed, `$TMUX` is unset): agent-team panes would not render. Per the phase's real size, two sequential sub-agent builders rather than a parallel agent team: Builder 1 takes T-3.2-02 and T-3.2-03 together (small, unrelated files, no benefit to parallelizing two sub-30-minute tickets against a fresh dispatch's fixed setup cost, and `ncbi_transport.py` is the exact shared file whose parallel-worktree fragmentation cost 3.1 two cross-file seams during its fix round). Builder 2 takes T-3.2-04 and T-3.2-05 once Builder 1's branch is merged into the phase branch.

## Premise gate design

WRITTEN and watched failing before any tool code exists. Baseline: `RUN_PREMISE_GATE=1 python -m pytest tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py -v` on 2026-08-08, 8 failed, 0 passed, every failure `ModuleNotFoundError: No module named 'system_03_search_agent.tools.ncbi_dbsnp'`. Every failure is in the correct direction (the artifact under construction is absent), none from a network fault or a syntax error, per LEARNINGS.md row 43's discipline.

File: `tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py`.

### The arms

Same shape as 3.1's tool-level gate: this tool makes one repeated decision, given a Variation Services or ESummary response, is this `ok`, `empty`, or `error`. Unlike 3.1, the pre-build probes above already resolved most of the open verification-gap question, so the gate pins live-confirmed behavior rather than an assumption.

| Arm | Cases | What it pins |
|-----|-------|---------------|
| ok | rs334 resolves with correct `spdi_canonical`, non-empty `clinical_significance` containing `"pathogenic"`, `genes` containing HBB/3043, and `population_frequencies` correctly parsed from `global_mafs` (not `global_maf`) | The real end-to-end path, correct field parsing, F-3.2-01 and F-3.2-02 closed |
| ok, empty population data | A real rsid whose `global_mafs` genuinely returns `[]` | `global_mafs: []` alone is `status: "ok"`, `population_frequencies: []`, never treated as a failure, per Section 6.3 line 1074 |
| error | A nonexistent rsid (404), a malformed SPDI (400), a malformed HGVS (400) | The resolved open verification gap: Variation Services' non-200 responses map to `status: "error"`, confirmed live rather than assumed |
| the phase's own reason | Sequential-not-parallel: an rsid whose Variation-Services-normalized canonical SPDI differs from any SPDI substring naively extractable from the raw input keys the ESummary clinical fetch off the NORMALIZED id, not the raw one | Pins the ordering trap named in `Tool_implementation_mechanics.md` and Section 6.3 line 1076 as a correctness assertion, not just a code-review comment |
| the phase's own reason | `global_maf` (the flat scalar) is present and null on a live response, and the tool's `population_frequencies` output is unaffected by its value | Pins that the tool never reads the flat scalar, live, not by code inspection alone |

### Coverage, stated in the gate's own module docstring per `goal-contracts.md`

Exercises: both API families (Variation Services, dbSNP ESummary via E-utilities), all three `query_type` values (rsid, hgvs, spdi) at least once each, the `include_clinical` flag's default-true path, the `ok`/`error` split for all three Variation Services endpoints touched. Does NOT exercise: `all_equivalent_contextual` (multiple equivalent contextual alleles for one variant; no case in this gate needs allele-equivalence resolution, and Section 6.3 does not name it as required for a correct answer, only as an available endpoint); the `variation` rate-limit family's actual 1 req/s throttling under concurrent load (covered by a unit test on `RateLimiter` itself in T-3.2-02, not by this gate, which runs each case sequentially against the live API and would not exercise contention regardless). A future case exercising a variant with multiple equivalent SPDI representations, and a concurrency test against the new rate-limit family, are both explicitly named gaps rather than silently absent.

## Findings

State vocabulary per `tracker/phase_3.1.md` and `.claude/skills/task-tracker/SKILL.md`: `filed` / `confirmed` / `open` (a decision, not a bug) / `closed`.

| ID | State | Summary |
|----|-------|---------|
| F-3.2-01 | closed | `global_mafs[].freq` is a compound string (`"A=0.027356/137"`), not separate fields. `_parse_global_mafs` in `ncbi_dbsnp.py` fails closed on any unrecognized shape, live-verified against rs334 including a genuine `"0."` (bare-zero) edge case, pinned by premise gate case 1 |
| F-3.2-02 | closed | `clinical_significance` and `fxn_class` are comma-separated strings in raw ESummary, not arrays. `_split_comma_field` closes it, pinned by premise gate case 3 |
| F-3.2-03 | filed | Section 6.3 names `spdi/{spdi}/canonical_representative` as the SPDI normalization endpoint. Live-confirmed broken server-side (HTTP 500 on every well-formed input tried, including NCBI's own documented example), not a client request-shape issue. `ncbi_dbsnp.py` substitutes `/spdi/{spdi}/contextual` instead, a live-working sibling endpoint that performs genuine normalization but is not proven equivalent to what `canonical_representative` would have returned (it may omit some canonicalization `all_equivalent_contextual`, also broken, would otherwise resolve). The premise gate's `query_type="spdi"` coverage is error-path only (case 5, a malformed SPDI); no case exercises a real, valid SPDI through the `ok` path, so this substitution is unverified beyond "it does not crash and it does reject malformed input the same way." Needs a judge/adversary look specifically, and a Step 6.2 note that Section 6.3's named endpoint is unusable as documented |
| F-3.2-04 | filed | `rsid` is always empty and no clinical fetch runs for `query_type="spdi"` or `"hgvs"`, because neither of Variation Services' SPDI/HGVS-keyed endpoints returns an rsid (a separate `/spdi/{spdi}/rsids` endpoint exists and is not called; not named in this ticket's four-endpoint list). This is a real, narrower capability than the `rsid` query type gets, not a bug in what was asked for, but worth a product-owner read: an spdi/hgvs query never gets clinical_significance/population_frequencies even with `include_clinical=True` |

### Adversary round 1, 2026-08-08

Ran live against the real tool and real NCBI endpoints (~40 Variation Services calls spaced 1.3s+, plus a bulk ESummary scan over ~350 real dbSNP records). Touched no repository file. Every finding below is state `filed`; the adversary files, it never closes.

| ID | Severity | Summary |
|----|----------|---------|
| F-3.2-A-01 | critical | Every `_cap()` call silently truncates instead of failing closed, shipping the mangled value as `status: "ok"`. Five live instances: a clinical-significance term truncated mid-word into a different-looking real term (`conflicting-interpretations-of-pathogeni`), the clinical_significance LIST silently shortened from 11 to 10 entries with `likely-pathogenic` dropped and no signal, a population-frequency allele truncated from a 14bp poly-A repeat into a real-looking but wrong 10bp allele, `spdi_canonical` truncated from a 150bp insertion into a syntactically valid 128bp one naming a different variant, and duplicate `alleles` entries from capping two distinct raw sequences to the same 20-char string. None of these are reachable by the premise gate's own assertions |
| F-3.2-A-02 | critical | A numeric identifier from ANY namespace, sent as `query_type: "rsid"`, returns a fully cited record for an unrelated variant, since every integer is valid input to `refsnp/{id}` and there is no malformed shape for the live endpoint to reject. Live-reproduced: querying `"3043"` (HBB's own Gene ID, already load-bearing ground truth in this phase's premise gate) as an rsid returns a confident, cited, unrelated ALDH1B1 variant. The fabricated-citation shape the whole system exists to prevent, reached with no malformed input at all |
| F-3.2-A-03 | major | `population_frequencies` mixes reference-allele and multiple alt-allele frequencies in one flat list with no link to `spdi_canonical` and no multiallelic marker. On rs334, a 50 percent SGDP_PRJ frequency for the REFERENCE allele T sits unmarked beside the sickle allele A's real frequency, readable as "the sickle allele reaches 50 percent". Which allele `spdi_canonical` even names is itself the first `deleted != inserted` entry NCBI happens to return first, not a deliberate selection |
| F-3.2-A-04 | major | Raw caller text, including embedded instruction-shaped text and a spoofed citation URL, is laundered verbatim into the unpinned `spdi_canonical` and `error` fields on the error path. `source_url` is correctly host-pinned and blocked; `spdi_canonical`/`error` are not, and a Synth-tier model reading the tool result would see attacker-controlled text in a field whose declared semantics are "the canonical SPDI" |
| F-3.2-A-05 | major | `include_clinical=False` is output-shape-identical to "this variant genuinely has no clinical data" (case 2's own shape), with no `clinical_fetched` marker distinguishing "not fetched" from "fetched and empty" |
| F-3.2-A-06 | major | Every `spdi`/`hgvs` query returns `status: "ok"` with substantive content and `source_url: null`, permanently, for two of the tool's three query types. Under the cite-or-refuse gate an uncited `ok` claim is the exact failure the gate blocks |
| F-3.2-A-07 | major | A withdrawn rsid (live-reproduced: rs100, rs386) is an undocumented THIRD `refsnp` response shape (`withdrawn_snapshot_data`, neither primary nor merged) and the resulting error message says "retry once" for a permanent condition, discarding the genuinely useful withdrawal date NCBI provides |
| F-3.2-A-08 | major | A genuine Variation Services 5xx (live-reproduced via a query/query_type mismatch) is reported to the agent with the SAME message and guidance as a 404 nonexistent-rsid, so the agent cannot distinguish "does not exist" from "service degraded," and the message tells it to retry when it already did (once, silently, via the transport's own backoff) |
| F-3.2-A-09 | major | The merge substitution (rs3168321 -> rs334) is correct and required by case 8, but nothing in the OUTPUT records that a substitution happened; a transcript reads as the tool answering a different question than the one asked |
| F-3.2-A-10 | minor | The error path's `rsid`/`spdi_canonical` fields carry a truncated raw caller query that can look like a plausible but fabricated identifier (a truncated SPDI reported as if it were an `rsid` value) |
| F-3.2-A-11 | minor | Control characters (NUL byte, RTL override) are echoed raw into typed output fields with no sanitization |
| F-3.2-A-12 | minor | An empty `spdi`/`hgvs` query collapses the request URL and produces an error message naming a value the caller never sent |
| F-3.2-A-13 | minor | `_NormalizationResult.rsid` is not capped on the `ok` path, unlike the error path; not reachable with current NCBI id lengths |
| F-3.2-A-14 | minor | Latent instances of F-3.2-A-01's mechanism on `_MAX_POP_FREQS`/`_MAX_GENES`/`_MAX_FXN_CLASS_ITEMS`/gene-name/`chrpos` caps, unexercised across ~350 sampled live records but structurally identical |

Attacked and held, no defect found: the 200/201-char schema boundary, rsid case/whitespace normalization, query-type-mismatch cross-contamination, the F-3.2-03 `/contextual` substitution's correctness (reference validation and right-shift normalization both verified live and self-consistent with the `refsnp` path across multiple distinct real SPDIs), `_GLOBAL_MAFS_FREQ_PATTERN` against ~350 live records at clinically dense loci (zero false positives, zero false negatives), the comma-split's safety against real data, merge-hop generality (traced twelve real chains, all single-hop, all correct), and the never-raises outer boundary under every hostile input tried.

Process note from the adversary, recorded because it is a real instance of `goal-contracts.md`'s coverage-declaration discipline working as designed: F-3.2-A-01, A-05, and A-06 all live inside code paths the premise gate's own module docstring already names as deliberately unexercised (`include_clinical=False`, the `spdi` ok path, multiple equivalent representations). The gate is currently green while three of the four highest-severity findings sit in exactly what it says it does not measure.

### Judge round 1: FAIL, 2026-08-08

First attempt died on a connection error while running concurrently with the adversary (the concurrent-Opus session-limit collision LEARNINGS.md row 44 already documents). Re-dispatched sequentially, alone, once the adversary returned.

Independently reproduced both criticals live, from its own commands, not the adversary's notes: F-3.2-A-01's `spdi_canonical` truncation (a 150bp insertion shipped as a 127bp one, `status: "ok"`) and clinical-significance list-shortening (`rs429358`, `likely-pathogenic` silently dropped from 11 real entries down to 10, `status: "ok"`); F-3.2-A-02 exactly (`{"query": "3043", "query_type": "rsid"}` returns a confident, cited, unrelated ALDH1B1 variant for HBB's own Gene ID).

Gates: full suite 1801 passed / 90 skipped / 1 xfailed, premise gate 8/8 live, `ruff` clean, confirmed no test assertion anywhere was weakened (the only five removed lines all made an assertion stricter, not weaker). Confirmed live: `global_maf` (the flat scalar) is never read anywhere in `ncbi_dbsnp.py`; the two Variation-Services/ESummary calls are never raced (no `asyncio.gather`/concurrent construct exists, the second call's own input is read out of the first's return value). All 24 schema caps confirmed to actually fire when hand-constructed over-limit values are validated directly against the Pydantic models.

Root cause identified for F-3.2-A-01 and structurally for the schema-cap gate: `_cap()` (`ncbi_dbsnp.py:255`) pre-truncates every value before construction, so the 24 verified-firing Pydantic caps are unreachable from the tool's own call path. The multi-agent pipeline gate is satisfied on paper and defeated at runtime.

Root cause identified for F-3.2-A-08, and found BROADER than filed: `ClassificationResult` (`ncbi_transport.py:387-390`) carries no `http_status` field, so downstream code cannot structurally distinguish a 429/500/502/503 from a genuine 400/404. All three normalization functions (`_normalize_rsid`, `_normalize_spdi`, `_normalize_hgvs`) collapse every non-2xx into "verify your input is correct," including a rate-limited 429. `_get_variation` already holds `response.status_code` and discards it; the fix is local to `ncbi_dbsnp.py`, no shared-transport change needed.

New findings from the judge itself, not in the adversary's set:

| ID | Severity | Summary |
|----|----------|---------|
| J-01 | major | The premise gate's own "Deliberately NOT exercised" coverage statement omits the two things that turned out to matter most: over-length/cap behavior (F-3.2-A-01's whole surface) and population-frequency allele attribution (F-3.2-A-03's). `goal-contracts.md` requires a gate state its own coverage gaps; this one's statement is itself incomplete |
| J-02 | major | `ClassificationResult` has no `http_status` field; root cause of F-3.2-A-08, detailed above |
| J-03 | major | `ncbi_dbsnp_schemas.py`'s design decision 2 asserts "the live endpoint returns a structured 400 for malformed input" as the reason `query` is not shape-validated. Live-verified false for the `rsid` branch: every integer is well-formed input to `refsnp/{id}`, so there is no malformed shape for the endpoint to reject. The F-2.1-J5-01 pattern (a confident comment asserting an unverified property), recurring |
| J-04 | minor | `python tracker/check_doc_drift.py --check` reports 3 stale test counts (CLAUDE.md, AGENTS.md, the continuation prompt all say 1812, computed 1892, +80 net, no removals). Routine phase-checkpoint work |
| J-05 | major | Structural restatement of F-3.2-A-01/J-01: `_cap()` renders all 24 verified schema caps unreachable from the tool's own path |
| J-06 | observation | The unit tests and the premise gate are blind in the SAME direction: neither covers over-length values, the withdrawn-rsid shape, or 5xx-vs-404. The build phase 2.1 retrospective's named pattern (a gate with the same blind spot as the code it grades), recurring |

Triage, every adversary finding, judge's own recommendation with reason:

| ID | Triage | Reason |
|----|--------|--------|
| F-3.2-A-01 | confirmed-blocking | Reproduced independently; drops a real clinical term and ships a wrong-length variant, both under `status: "ok"` |
| F-3.2-A-02 | confirmed-blocking | Reproduced exactly; the schema's own stated justification for not validating this branch is provably false |
| F-3.2-A-03 | confirmed-blocking | Reproduced on the flagship rs334 case itself: a reference-allele frequency sits unmarked beside the real variant's frequency, readable as the variant's own |
| F-3.2-A-04 | confirmed-carry-forward | Reproduced, but the laundered content is the caller's own already-guardrailed query text, not external NCBI payload; second-order. Fix alongside A-10 |
| F-3.2-A-05 | confirmed-carry-forward | Reproduced; real ambiguity but the caller set the flag knowingly |
| F-3.2-A-06 | confirmed-blocking | Reproduced; a permanent uncited `ok` for 2 of 3 query types is a direct grounding-gate violation, and the fix is one line (`empty` instead of `ok`) |
| F-3.2-A-07 | confirmed-carry-forward | Real defect, verdict correct, only guidance wrong; fix alongside A-08, same functions |
| F-3.2-A-08 | confirmed-carry-forward, fold into this round | Broader than filed (all three normalization paths, including 429); cheap local fix using data already in hand |
| F-3.2-A-09 | confirmed-carry-forward | Needs a schema decision (a new output field), not a patch |
| F-3.2-A-10 | confirmed-carry-forward | Same mechanism as A-01/A-04, closes with them |
| F-3.2-A-11 | confirmed-carry-forward | Real but cosmetic-severity next to A-01 |
| F-3.2-A-12 | confirmed-carry-forward | Good catch, low severity |
| F-3.2-A-13 | confirmed-carry-forward | Unreachable at current NCBI id lengths; latent |
| F-3.2-A-14 | confirmed-carry-forward | Structurally identical to A-01, closes automatically once A-01's `_cap` fix lands |

Zero rejected findings. Overall verdict: FAIL. Must fix before phase close: F-3.2-A-01, F-3.2-A-02, F-3.2-A-03, F-3.2-A-06, plus F-3.2-A-07/A-08 folded in as a near-free fix using data already available, plus J-01's gate coverage statement. Everything else carries forward with an explicit disposition (see table above and the Open items list this phase adds to `tracker/BOARD.md`).

### Fix round 1, 2026-08-08: all five confirmed-blocking findings fixed

F-3.2-A-01/A-14/J-05 (truncation): fixed by refusal, not truncation. `_cap_or_refuse`/`_cap_list_or_refuse` in `ncbi_dbsnp.py` make the whole call `status: "error"`, naming the exact field and cap, rather than silently shipping a shortened value under `ok`. Chosen over an explicit `truncated: true` field: a citation-grounded system refuses rather than answers with less than the full truth. Live-verified: `rs429358` (11 real `clinical_significance` values against a 10-item cap) now refuses cleanly instead of silently dropping `likely-pathogenic`.

F-3.2-A-02/J-03 (bare numeric rsid): fixed at the schema layer, `NcbiDbsnpInput`'s new `model_validator` requires an `rs`/`RS` prefix for `query_type: "rsid"`, rejected before any network call. `ncbi_dbsnp_schemas.py`'s design decision 2 corrected to no longer claim a property live-verified false. Live-verified: `{"query": "3043", "query_type": "rsid"}` now rejected by Pydantic, never reaches Variation Services.

F-3.2-A-03 (allele attribution): fixed by labeling, not reselection. `NcbiDbsnpPopulationFrequency` gained `allele_role` (`"variant"`/`"reference"`/`"other"`), computed against `spdi_canonical`'s own alleles. Reselecting which allele `spdi_canonical` names by "best population support" was considered and rejected: no defensible single definition, and it would not attribute the legitimate reference-allele rows either way.

F-3.2-A-06 (uncited ok): a resolved `spdi`/`hgvs` normalization with no citable rsid now returns `status: "empty"`, never a permanent uncited `"ok"`. `include_clinical=False`'s real, citable `"ok"` (F-3.2-A-05, carried forward) is unaffected, a different code path.

F-3.2-A-07/A-08/J-02 (withdrawn rsid, 5xx-vs-404): a new `_withdrawn_info` check recognizes `withdrawn_snapshot_data` (checked before merge-follow, since a withdrawal is permanent) and surfaces the withdrawal date. HTTP status now threads through to the error message locally in `ncbi_dbsnp.py` (`ncbi_transport.py` untouched, confirming the judge's assessment that this needed no shared-transport change): a 429/5xx gets transient/retry guidance, a 404/400 does not.

One item deferred correctly rather than silently: the fix builder was scoped to not touch `test_ncbi_dbsnp_premise.py`'s assertions, only its coverage docstring. F-3.2-A-06's fix correctly made case 7 (hgvs resolves, `status: "ok"`) stale, since a resolved-but-uncited hgvs result is now `"empty"`. The builder flagged this explicitly in three places rather than leaving it to be discovered. The lead reproduced the 7-of-8 failure live, confirmed it was in the correct, expected direction (a strengthening from the fix, not a regression), and corrected case 7's assertion to `status == "empty"` plus `source_url is None`.

Gates after the fix round, lead-verified independently: full suite 1818 passed / 90 skipped / 1 xfailed (net +17 tests from 1801 before this round), live premise gate 8 of 8, `ruff check` clean on every touched file. No existing assertion weakened anywhere; the two pre-existing test corrections the fix builder made were both to match the intentionally changed contract (a schema fixture's `query_type` corrected from `"rsid"` to `"spdi"` since it tests `max_length` rather than rsid shape), never to hide a defect.

Carried forward, unchanged from the judge's disposition: F-3.2-03 (spec correction, Step 6.2), F-3.2-04's capability half, F-3.2-A-04, A-05, A-09, A-10, A-11, A-12, A-13, J-04 (doc counts, at phase-checkpoint), J-06 (observation). J-01's coverage gap on the truncation-refusal and allele-attribution paths is itself now only partially closed: both are covered by mocked cases in `test_ncbi_dbsnp.py`, neither by a live premise-gate case, a residual the gate's own coverage statement now discloses rather than hides.

### Independent re-review, fix round 1, 2026-08-08

Dispatched with zero prior context specifically because every verification so far had been same-session, per this repo's own precedent (`tracker/phase_3.1.md`'s "Final independent review"). Re-ran every gate independently (full suite 1818/90/1 matching exactly, premise gate 8/8, ruff clean, confirmed the only 17 removed test lines all strengthened rather than weakened an assertion) and re-reproduced all five fixes from its own live commands, confirming each genuinely closed: the refuse-not-truncate policy audited by code reading (only 3 sites, all inside the carried-forward error-path scope) plus three independent live triggers on different caps; the rsid shape validator confirmed to make zero network calls on rejection; `allele_role` confirmed to correctly distinguish three real roles on one rs334 record and correctly re-derived on rs3043 (G as reference there, not always "variant"); the empty/ok split confirmed to cost zero wasted ESummary calls and to leave the `include_clinical=False` citable path untouched; the withdrawn-rsid message confirmed non-retrying and date-carrying on both rs100 and rs386.

Two new findings from its own adversarial probing of the fix code itself, both against confirmed live evidence:

| ID | Severity | Summary |
|----|----------|---------|
| F-3.2-A-15 | major | The refuse-not-truncate policy (F-3.2-A-01's fix) makes the tool return `status: "error"`, discarding an otherwise fully successful fetch, for roughly 10.4% of real clinically-cited variants in a live 800-record sample, because two standard ClinVar vocabulary terms (`conflicting-interpretations-of-pathogenicity`, 44 chars; `no-classifications-from-unflagged-records`, 41 chars) exceed the locked spec's 40-char `clinical_significance` item cap. Confirmed end to end through the real tool on flagship variants: rs429358 (APOE ε4), rs6025 (Factor V Leiden), rs1801133 (MTHFR C677T), rs1800562 (HFE C282Y), rs1042522 (TP53 P72R), rs80359198 (BRCA2). This cost was never measured or disclosed when F-3.2-A-01 was closed |
| F-3.2-A-16 | major | The status-code-threading fix (F-3.2-A-07/A-08) confidently asserts "not a bad request, retry after a backoff" for ANY Variation Services 5xx, but live-reproduced: a reference-mismatch SPDI (a genuine, deterministic client input error, the most common 5xx this API actually emits per the pre-build probes) also returns HTTP 500, and the tool now tells the agent the opposite of the truth, burning a wasted retry against the tightest rate pool in the roster on a request that can never succeed. The exact F-2.1-J5-01 pattern (a confident assertion contradicted by the live endpoint), and the one unit test guarding this path uses a hand-picked genuinely-transient 503, blind in the same direction as the code it grades (J-06, recurring) |

Also filed, not blocking: NEW-3 (inconsistent malformed-entry policy between `_parse_genes`/`_extract_canonical_spdi_from_refsnp`, which silently `continue` past a bad entry, versus `_parse_global_mafs`, which fails closed — same untrusted-content surface, opposite policies), NEW-4 (`_RSID_SHAPE_PATTERN` anchors on `$` rather than `\Z`, not currently exploitable since `_strip_rs_prefix` already calls `.strip()` first, but one refactor away from being live), NEW-5 (only 3 of 11 refuse sites have a direct test, though uniformity was independently confirmed by code reading), NEW-6 (a `spdi`/`hgvs` `status: "empty"` now carries substantive normalized data plus a non-null `error` string, a contract shape worth a line in the Write step's own spec once wired), and the F-3.2-A-02 residual (`rs` + a foreign numeric id still resolves to a confident wrong-but-honestly-labeled variant; disclosed in code but not in this table until now, and materially narrower than the original since the output truthfully names which rsid was actually fetched).

Recommendation: not yet ready for the skill chain. F-3.2-A-15 and F-3.2-A-16 need one more fix pass before phase close.

### Fix round 2, 2026-08-08: F-3.2-A-15 and F-3.2-A-16 closed

F-3.2-A-15: the refuse-not-truncate policy changed from whole-call refusal to field-level withholding with an explicit signal. `NcbiDbsnpOutput` gained `fields_withheld: list[str]`, naming which fields were dropped for exceeding their locked-spec cap; a withheld field is emptied, never truncated, and its name appended to the list, so a caller can always tell "genuinely absent" from "present but withheld" from "silently wrong." `spdi_canonical` is the one deliberate exception, kept as whole-call refusal, reasoned as the sole field without which there is no variant identity to attach anything else to. The numeric caps themselves are unchanged, exactly as Section 6.3 locks them; this is a disclosure fix, not a spec deviation. Live-verified: rs429358 (APOE ε4) now returns `status: "ok"` with gene `APOE`/348, `spdi_canonical`, and 22 population_frequencies rows all intact, `fields_withheld: ["clinical_significance"]`.

F-3.2-A-16: `_variation_error_message` no longer asserts a blanket "not a bad request, retry" for every 5xx. A 429 stays unconditionally transient (NCBI's own rate-limit signal). A 5xx whose message names a specific input problem (reference-sequence mismatch, invalid coordinate) is now reported as a permanent, non-retrying rejection; a genuinely generic 5xx gets hedged "may be transient" language instead of a confident, disproven claim. Live-verified: the reference-mismatch SPDI (`NC_000011.10:5227000:AT:AA`) now returns `status: "error"` stating "This is a PERMANENT, deterministic input error... not a transient server condition; retrying will not help," correcting the exact inversion the independent reviewer found.

NEW-4 folded in: `_RSID_SHAPE_PATTERN`'s `$` anchor corrected to `\Z`.

Gates, lead-verified independently a third time: full suite 1830 passed / 90 skipped / 1 xfailed (net +12 from 1818), live premise gate 8 of 8, `ruff check` clean on every file this phase touches (the two remaining `ruff` findings anywhere in the touched-file set, `PYI034`/`SIM117` in `test_ncbi_transport.py`'s `_DirectLogCapture` helper, are pre-existing on `main`, confirmed via `git stash` diff by the first foundation builder, untouched by any commit in this phase). Both original repros re-verified directly by the lead against the running (not mocked) fixed code, matching the fix round's own claims exactly.

### Ledger close, 2026-08-08

All 16 adversary findings and all 6 judge findings now have a final disposition. Every finding this phase's own review found real; zero rejected across two full review rounds.

| Status | Findings |
|--------|----------|
| Closed, live-verified across two independent reviewers plus the lead | F-3.2-01, F-3.2-02, F-3.2-A-01, F-3.2-A-02, F-3.2-A-03, F-3.2-A-06, F-3.2-A-07, F-3.2-A-08, F-3.2-A-15, F-3.2-A-16, J-02, J-05 |
| Carried forward, explicit disposition, no product-owner decision needed to ship this phase | F-3.2-A-04, F-3.2-A-05, F-3.2-A-09 through F-3.2-A-14, NEW-3, NEW-5, NEW-6, J-06 (all detailed above with their own reasoning) |
| Carried forward, needs a product-owner or Step 6.2 decision | F-3.2-03 (Section 6.3 names a live-broken Variation Services endpoint), F-3.2-04's capability half (spdi/hgvs never carries clinical data), the F-3.2-A-02 residual (`rs` + a foreign numeric id still resolves, honestly labeled), J-04 (doc counts, routine at phase-checkpoint) |
| Coverage gap disclosed rather than hidden | J-01, now further extended: the withhold-with-signal and inverted-5xx-message fixes are covered by mocked unit tests, not by a live premise-gate case (no live ground truth was captured for either during this fix round, per the file's own no-fabricated-fixtures discipline) |

This phase went through: pre-build live probing, a blocking premise gate written and watched failing, two builders, an adversary round (14 findings), a judge round (FAIL, 6 more findings, all 14 adversary findings independently triaged), a fix round (5 confirmed-blocking findings closed), an independent fresh-context re-review (2 new findings from the fix round itself), and a second fix round (both closed, lead-verified a third time). Six full review passes total. Proceeding to the standard skill chain.

## History

- 2026-08-08 lead: phase opened immediately after 3.1 fully closed (PR #23, merged 2026-08-07) and the F-2.1-C15 generation-bound fix merged (PR #24, same day). Dependencies 3.0 and 3.1 both verified `done` on the board. Section 6.3, Section 21.1, and the tool-mechanics trap list read. `tracker/phase_3.1.md` and the build phase 2.1 retrospective read for transferable lessons. Branch `phase/3.2-ncbi-dbsnp` cut from `main` at `3bba944`. Five tickets decomposed. A spec-versus-reality gap found during decomposition: Section 25's build-order line for this phase names the dbVar coordinate-overlap sub-tool as this phase's deliverable, but it already shipped in 3.1 as T-3.1-10; documented above rather than duplicated or silently dropped, carried to Step 6.2. Pre-build live probes run against Variation Services (`refsnp`, `spdi/.../canonical_representative`, `hgvs/.../contextuals`) and dbSNP ESummary before any fixture was written, per LEARNINGS.md row 60. Two new findings filed at design time (F-3.2-01, F-3.2-02) from what those probes actually returned. One probe result (SPDI canonical_representative 500s on a real, well-formed allele) left unresolved and handed to T-3.2-04 rather than guessed at. Stage 5 not yet started.
