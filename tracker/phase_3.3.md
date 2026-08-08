# Phase 3.3: pubtator_annotate and litvar2_lookup, the two Layer 3 enrichment tools

Build phase 3.3 delivers `pubtator_annotate` (PubTator3: entity normalization for free text, entity annotation on publications) and `litvar2_lookup` (LitVar2: variant-to-literature evidence). Both are the first tools whose retrieved content is genuinely untrusted external text (entity names, descriptions, annotation fields extracted from a source publication) rather than a structured API record, so `production-standards`' multi-agent pipeline gate and untrusted-source-reader tier separation apply directly, not by analogy.

Depends on: build phase 3.1 (done, PR #23, merged 2026-08-07)
Branch: `phase/3.3-enrichment-tools`
Spec: `requirements/Technical_specification.md` Section 6.4 and 6.5, with Section 21.1 for rate limits
Reference: `docs/ncbi/Tool_implementation_mechanics.md`, `.claude/rules/tool-call-budgets.md`, `.claude/rules/ai-security-standards.md` (untrusted content), `LEARNINGS.md` build phase 3.1/3.2 entries and the build phase 2.1 retrospective

## Phase premise (the done-when)

A question resolving to a real, well-known entity (BRCA1, or the flagship rs334 sickle-cell variant this repo already uses as its canonical LitVar2 example in Section 6.5) comes back from `pubtator_annotate` and `litvar2_lookup` with correctly parsed entities, correctly unwrapped `biocjson` annotations, and correctly capped/withheld (never silently truncated) publication lists. A no-match query is classified `empty`, not fabricated as `ok`. A malformed or partially-invalid request (a mixed batch of valid and nonexistent PMIDs, an unencoded LitVar2 id) is classified `error` or handled per its live-confirmed real behavior, never silently swallowed as full success. Every free-text field extracted from PubTator3 or LitVar2 (`name`, `description`, annotation fields) is treated as untrusted content: it reaches the output schema capped/withheld, never executed or treated as an instruction, and gets the isolated-reader-pass tier separation on the tool's own permissions (read plus one API, no write, no other tools).

Same carry as build phases 3.1 and 3.2: whether either tool is dispatched as an answer-bearing tool from `act_node` is the open product-owner scope decision already carried to T-3.1-28. This phase delivers both tools themselves, registered into the tool schema and stable prompt prefix; `act_node` wiring is out of scope here too.

The verify surface is `tests/system_03_search_agent/tools/test_pubtator_annotate_premise.py` and `tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py`, not a suite total, per `tracker/phase_3.1.md`'s standing rule.

## Pre-build live probes (done before any tool code, before any fixture)

Per LEARNINGS.md row 60 (build phase 3.1) and the phase 3.2 retrospective ("pre-build live probing before any fixture is written catches a defect class a fixture authored from documentation cannot"), run against the real APIs before any ticket's fixtures:

| Probe | Result | What it resolves |
|-------|--------|-------------------|
| `GET /entity/autocomplete/?query=BRCA1&limit=5` | HTTP 200, real gene/variant entities, `_id` prefixed `@GENE_`/`@VARIANT_`, `db_id: "672"` for the BRCA1 gene | The `ok` baseline for `entity_lookup` |
| `GET /entity/autocomplete/?query=zzzznotarealtermxyz123&limit=5` | HTTP 200, `[]` | Confirms the documented no-match-is-200-empty-array shape |
| `GET /entity/autocomplete/?query=&limit=5` (empty query) | HTTP 400, body `["query is a mandatory parameter."]`, a bare JSON array of strings | A THIRD distinct PubTator3 error body shape, not documented anywhere in Section 6.4 or `Tool_implementation_mechanics.md`. Neither `{"detail": ...}` (the documented `annotate_publications` shape) nor an enveloped object. See F-3.3-02 |
| `GET /publications/export/biocjson?pmids=34083286` (a real BRCA1 paper) | HTTP 200, `{"PubTator3": [...]}`, annotations at `.PubTator3[0].passages[].annotations[]`, `infons` carrying exactly the documented field set (`type`, `identifier`, `normalized_id`, `valid`, `biotype`, `database`, `accession`, `name`) plus undocumented extras (`normalized`, and type-specific fields like `hgvs`/`rsid` for Variant) | Confirms the documented wrapper and `infons` shape live. Gene, Variant, CellLine, Disease, and Chemical annotation types all observed in one document |
| `GET /publications/export/biocjson?pmids=999999999999` (nonexistent PMID) | HTTP 400, `{"detail": "Could not retrieve publications"}` | Confirms the documented all-invalid-batch shape |
| `GET /publications/export/biocjson?pmids=34083286,999999999999` (one valid, one nonexistent, in the SAME request) | HTTP 200, `{"PubTator3": [<only the valid doc>]}`, the invalid PMID silently absent with no per-PMID error signal anywhere in the body | UNDOCUMENTED. See F-3.3-01, critical |
| `GET /variant/autocomplete/?query=rs334` | HTTP 200, real variant matches, `_id: "litvar@rs334##"`, `data_clinical_significance` array present on some rows and absent on others | The `ok` baseline for `variant_search`, confirms the optional field must be defaulted, never assumed present |
| `GET /variant/autocomplete/?query=zzznotavariant123` | HTTP 200, `[]` | Confirms the documented no-match shape |
| `GET /variant/autocomplete/?query=V600E` (name, not rsid) | HTTP 200, one match, `"match": "Matched on hgvs <m>p.V600E</m>"` | Confirms `variant_search` genuinely accepts a variant name, not only an rsid, per spec |
| `GET /variant/get/litvar%40rs334%23%23/publications` (correctly `%40`/`%23`-encoded) | HTTP 200, `{"pmids": [589+ ids]}` | Confirms the documented encoding requirement and the truncation trap (`maxItems: 50` against 589+ real ids) |
| `GET /variant/get/litvar@rs334##/publications` (deliberately UNencoded) | HTTP 400, `{"detail": "Variant not found: litvar@rs334"}` | Confirms `Tool_implementation_mechanics.md`'s encoding trap is real: the unencoded id is silently truncated at the `#` boundary before it ever reaches LitVar2, and the wrong (truncated) id is what gets reported not-found. Not a hard crash, a wrong-answer risk if any caller ever bypassed the tool's own encoding |
| `GET /variant/get/litvar%40rs99999999999%23%23/publications` (nonexistent variant id) | HTTP 400, `{"detail": "Variant not found: litvar@rs99999999999##"}` | Confirms `publications_lookup`'s error convention is genuinely status-coded (like Datasets v2/PubChem/Variation Services), never the E-utilities 200-with-body pattern |
| Hunting for a real litvar_id with `pmids_count: 0` (`rs1000000000`, `rs987654321`, `rs555555555`, none autocomplete-match) | No candidate found; LitVar2's corpus appears to only index variants with at least one literature mention, so a reachable `litvar_id` (one `variant_search` would ever return) structurally cannot have zero linked publications | The "Open verification gaps" zero-PMID case (`docs/ncbi/Tool_implementation_mechanics.md`) is not confirmable this way. Documented as likely-unreachable via the tool's own two-step flow rather than fixed or exhaustively hunted further. Carried, not closed |
| rs334's live `data_clinical_significance` includes `"conflicting-interpretations-of-pathogenicity"` (44 chars) | Exceeds the locked `litvar2_lookup.output` schema's `clinical_significance` item cap, `maxLength: 30` (Section 6.5 line 1236), by 14 characters | The SAME spec-versus-reality gap phase 3.2 found for `ncbi_dbsnp`'s `clinical_significance` (there capped at 40, also too tight for this exact ClinVar term), now confirmed live a second time on a DIFFERENT tool with an EVEN TIGHTER cap. See F-3.3-03 |

Two new findings, filed at design time rather than discovered by an adversary later:

### F-3.3-01: PubTator3 biocjson silently drops nonexistent PMIDs from a mixed batch

Severity: would be critical if shipped unnoticed, same class as phase 3.2's F-3.2-A-01 (silent truncation shipped under `status: "ok"`). Status: filed at design time, owned by T-3.3-06.

A request for `pmids=[A, B]` where `A` is real and `B` does not exist returns HTTP 200 with `PubTator3: [<A's document only>]`. Nothing in the body signals that `B` was requested and dropped; the only way to notice is to diff the requested PMID list against the PMIDs actually present in the response. Section 6.4's own output schema is `additionalProperties: false` with a fixed property set (`status`, `mode`, `entities`, `publications`, `error`), no room for a per-PMID miss signal, and it is a locked document (`.claude/rules/v1-scope-boundary.md`, `.claude/rules/writing-style.md`'s "never edit the locked spec"). Per `system-design-patterns` pattern 10 ("within v1, service contract changes are additive only: a new optional field"), and following the exact precedent build phase 3.2 set for its own too-tight cap (field-level withholding via an additive `fields_withheld` field, never silent truncation), T-3.3-06 adds one additive, optional field, `pmids_not_found: string[]`, to `pubtator_annotate.output`. `status` stays `"ok"` when at least one requested PMID resolved (matching PubTator3's own convention: it is not an error, it is a partial result), `pmids_not_found` names every requested PMID absent from the response, and `status` becomes `"error"` only when the API itself returned the documented HTTP 400 all-invalid-batch shape.

### F-3.3-02: PubTator3 has a third, undocumented error-body shape

Severity: minor, defensive-depth only in practice (T-3.3-05/07 close the client-side path that would trigger it, via `minLength: 1` on `query`). Status: filed at design time, owned by T-3.3-02.

An empty `query` string, which the locked input schema's `maxLength: 200` alone does not reject (no `minLength`), returns HTTP 400 with a BARE JSON ARRAY OF STRINGS, `["query is a mandatory parameter."]`, not the `{"detail": ...}` object shape `annotate_publications` uses on its own 400. `ncbi_transport.classify_status_coded_response`'s error-message extraction (`_extract_status_coded_error_message`) only ever inspects `dict` bodies; a list body falls through to its generic `"HTTP {status} with no structured error body"` fallback today, which is a safe, non-crashing behavior (fails closed, `status: "error"`, just with a less specific message) but not the actual server message. T-3.3-02 adds `minLength: 1` to both `pubtator_annotate.query` and `litvar2_lookup.query` at the schema layer (closing the only realistic path to this shape from this tool), and does not otherwise change the shared transport helper for a shape neither tool should ever be able to trigger in production. Named here so the gap is visible rather than silently absent, per `goal-contracts.md`'s "a verify surface must state its own coverage".

### F-3.3-03: litvar2_lookup's clinical_significance item cap is too tight for real ClinVar vocabulary, confirmed live

Severity: would be critical if shipped unnoticed, phase 3.2's F-3.2 finding recurring on a second tool. Status: filed at design time, owned by T-3.3-06.

Section 6.5's locked output schema caps each `clinical_significance` array item at `maxLength: 30` (line 1236). The live rs334 response carries `"conflicting-interpretations-of-pathogenicity"`, 44 characters, a standard ClinVar significance term, not a malformed or adversarial value. A naive `_cap()`-style truncation would ship a real-looking but wrong term (`conflicting-interpretations-of`), exactly F-3.2-A-01's failure mode on `ncbi_dbsnp`. Per the precedent that fix set (field-level withholding, never silent truncation, `_cap_or_withhold` in `ncbi_dbsnp.py`), T-3.3-06 drops any individual `clinical_significance` item that exceeds its cap from the array rather than truncating it, and records the drop via an additive, optional `fields_withheld: string[]` field on `litvar2_lookup.output`, naming which `variant_matches[i].clinical_significance` entries were withheld, following the same additive-field pattern F-3.3-01 uses and `ncbi_dbsnp.py` already shipped. Filed at design time from a real live response, not discovered by an adversary.

## Ticket map

| Ticket | Slice | Files |
|--------|-------|-------|
| T-3.3-01 | The premise gates, blocking, one file per tool | `tests/system_03_search_agent/tools/test_pubtator_annotate_premise.py`, `tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py` |
| T-3.3-02 | Transport: extend `ncbi_transport._extract_status_coded_error_message` with a `{"detail": ...}` branch (shared by PubTator3's `annotate_publications` 400 and LitVar2's both error paths), add a `"pubtator"` and `"litvar2"` rate-limit family (~5 req/s provisional throttle each, per Section 21.1's undocumented-API default, separate pools since the two hosts are unrelated) | `tools/ncbi_transport.py` |
| T-3.3-03 | Schemas: `pubtator_annotate` input/output, `minLength: 1` on `query`, local host-pinned `NCBI_PUBTATOR_RECORD_URL_PATTERN` scoped to `pubmed.` per the Multi-agent pipeline gate compliance table | `tools/pubtator_annotate_schemas.py` |
| T-3.3-04 | Schemas: `litvar2_lookup` input/output, `minLength: 1` on `query`, local host-pinned `NCBI_LITVAR2_RECORD_URL_PATTERN` (`^https://(www\.\|pubmed\.)?ncbi\.nlm\.nih\.gov/`, per Section 6.5 line 1242, unscoped beyond host unlike PubTator3's `pubmed.`-only pin), additive `fields_withheld` field for F-3.3-03 | `tools/litvar2_lookup_schemas.py` |
| T-3.3-05 | The `pubtator_annotate` tool itself: `entity_lookup` and `annotate_publications`, separate branches per Tool_implementation_mechanics.md's error-convention trap, owns F-3.3-01, the untrusted-content isolated-reader-pass tier (read plus PubTator3 only, no write, no other tools) | `tools/pubtator_annotate.py` |
| T-3.3-06 | The `litvar2_lookup` tool itself: `variant_search` and `publications_lookup`, URL-encoding the `litvar_id` before every publications call, `maxItems: 50` truncation with an honest `total_pmids`, owns F-3.3-03, same untrusted-content tier separation | `tools/litvar2_lookup.py` |
| T-3.3-07 | Tool registration: both tools into `REGISTERED_TOOL_SCHEMAS` in alphabetical position (`litvar2_lookup` between `cypher_query` and `ncbi_dbsnp`; `pubtator_annotate` after `ncbi_efetch`), `TOOL_REGISTRY_VERSION` v3 to v4, new fingerprint row, `tests/system_03_search_agent/harness/test_cache.py` updated to match | `harness/cache.py` |

Depends-on chain: T-3.3-01 blocks everything (written and watched failing first). T-3.3-02 has no dependency on 03/04. T-3.3-03 and T-3.3-04 have no dependency on each other. T-3.3-05 depends on T-3.3-02 and T-3.3-03. T-3.3-06 depends on T-3.3-02 and T-3.3-04. T-3.3-07 depends on both T-3.3-05 and T-3.3-06.

Dispatch plan: T-3.3-02 done first by the lead directly (small, shared, and every other ticket's fixtures depend on its error-message branch existing so a builder is not blocked mid-task waiting on a shared file). T-3.3-03/05 (`pubtator_annotate`, its own schema and tool files, zero overlap with the other tool's files) and T-3.3-04/06 (`litvar2_lookup`) dispatch as two parallel builders once T-3.3-02 lands, each with `isolation: "worktree"` since both run concurrently against the same repo. T-3.3-07 is done by the lead directly after both merge back to the phase branch, the same single-shared-file caution phase 3.2's dispatch plan used for `ncbi_transport.py`.

## Premise gate design

WRITTEN and watched failing before any tool code exists. Baseline: `RUN_PREMISE_GATE=1 python -m pytest tests/system_03_search_agent/tools/test_pubtator_annotate_premise.py tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py -v` on 2026-08-08, 12 failed, 0 passed, every failure `ModuleNotFoundError` (6 for `system_03_search_agent.tools.pubtator_annotate`, 6 for `system_03_search_agent.tools.litvar2_lookup`). Every failure is in the correct direction, none from a network fault or a syntax error, per LEARNINGS.md row 43's discipline.

Files: `tests/system_03_search_agent/tools/test_pubtator_annotate_premise.py`, `tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py`.

### The arms

| Arm | Cases | What it pins |
|-----|-------|---------------|
| ok, entity_lookup / variant_search | `BRCA1` resolves a gene entity with `db_id: "672"`; `rs334` resolves a variant match with `rsid: "rs334"`, non-empty `gene` containing `"HBB"` | The real end-to-end path for both tools' first mode |
| empty | A nonsense query on both tools' first mode returns `status: "empty"`, `[]`, never fabricated | The documented no-match-is-200-empty-array shape, live-confirmed |
| ok, annotate_publications / publications_lookup | A real PMID (34083286) unwraps correctly from `.PubTator3[0].passages[].annotations[]`, with a `Gene` annotation naming `identifier: "672"`; `litvar@rs334##` (correctly encoded) returns a truncated `pmids` list (`maxItems: 50`) with `total_pmids` carrying the true count above 50 | Section 6.4's drift-point wrapper unwrapped correctly, Section 6.5's truncation-with-honest-total trap closed |
| the phase's own reason, F-3.3-01 | A mixed batch of one real and one nonexistent PMID reports the nonexistent one in `pmids_not_found`, `status` stays `"ok"` for the real one's data | Pins the undocumented silent-drop behavior as a correctness assertion, not left implicit |
| error | An all-invalid PMID batch (`annotate_publications`), a genuinely not-found LitVar2 id (`publications_lookup`) both classify `"error"` | The documented status-coded error convention for both tools' second mode |
| the phase's own reason, encoding trap | An UNENCODED `litvar_id` passed to the tool's own internal encoding step still reaches LitVar2 correctly (i.e., the tool encodes internally regardless of whether the caller already did) | Pins `Tool_implementation_mechanics.md`'s encoding trap as a behavioral assertion on the tool, not just a code comment |
| the phase's own reason, F-3.3-03 | A `variant_search` on `rs334` or an equivalently long-clinical-significance-term variant reports `fields_withheld` for the over-length item, never a truncated-but-plausible-looking term | Pins withhold-not-truncate as the tool's real behavior against real data, not a hoped-for design decision |
| untrusted content | A crafted PMID annotation or entity `name`/`description` field is never executed, is capped/withheld like any other field, and is asserted to reach the output as inert data | The tier-separation and untrusted-content requirement, `ai-security-standards.md` |

### Coverage, stated in the gate's own module docstrings per `goal-contracts.md`

Exercises: both tools, both modes each, the `ok`/`empty`/`error` split live for every mode, the F-3.3-01 mixed-batch drop, the F-3.3-03 withhold-not-truncate path, the LitVar2 encoding trap, and one untrusted-content assertion per tool. Does NOT exercise: the PubTator3 relations endpoint (deliberately, per the "Open verification gaps" convention: not live-verified, not built in v1, `pubtator_annotate` has no `mode` for it); concurrent load against either new rate-limit family's actual pacing (covered by a unit test on the shared `RateLimiter`, not by a gate that runs sequentially against the live API); a `zero_pmids` case for `publications_lookup` (F-3.3's own pre-build probe could not construct a reachable one; documented as likely-unreachable rather than silently absent from this gate).

## Findings

State vocabulary per `tracker/phase_3.1.md`/`tracker/phase_3.2.md` and `.claude/skills/task-tracker/SKILL.md`: `filed` / `confirmed` / `open` (a decision, not a bug) / `closed`.

| ID | State | Summary |
|----|-------|---------|
| F-3.3-01 | filed | PubTator3 `annotate_publications` silently drops nonexistent PMIDs from a mixed batch under `status: "ok"`. Owned by T-3.3-06, closed by an additive `pmids_not_found` field |
| F-3.3-02 | filed | PubTator3 has a third, undocumented error-body shape (a bare JSON array of strings) on an empty query. Owned by T-3.3-02/03, closed by `minLength: 1` at the schema layer plus a safe generic-fallback message in the shared transport helper |
| F-3.3-03 | filed | `litvar2_lookup`'s locked `clinical_significance` item cap (`maxLength: 30`) is too tight for real ClinVar vocabulary, confirmed live a second time on a second tool (after phase 3.2's `ncbi_dbsnp` finding of the same class). Owned by T-3.3-06, closed by withhold-not-truncate and an additive `fields_withheld` field, same precedent as `ncbi_dbsnp.py` |

Adversary and judge rounds appended below as they run.
