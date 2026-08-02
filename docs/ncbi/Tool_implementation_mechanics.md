# Tool implementation mechanics

Reference for anyone about to write, review, or debug a tool in `system_03_search_agent/tools/`. Every entry below is a verified, non-obvious fact about a specific NCBI, PubTator3, LitVar2, or ClinicalTrials.gov endpoint that produces a wrong result, a silent failure, or a broken citation if a builder does not know about it before writing the code. Source: the locked `requirements/Technical_specification.md`, Section 6 (lines 712 to 1467), the only verified source for these endpoints, fields, and error behaviors. Read this document before writing or reviewing any tool; it is not loaded automatically the way a rule is.

## Table of contents

- [Purpose and scope](#purpose-and-scope)
- [How to read a trap entry](#how-to-read-a-trap-entry)
- [cypher_query (Section 6.1)](#cypher_query-section-61)
- [ncbi_efetch (Section 6.2)](#ncbi_efetch-section-62)
- [ncbi_dbsnp (Section 6.3)](#ncbi_dbsnp-section-63)
- [pubtator_annotate (Section 6.4)](#pubtator_annotate-section-64)
- [litvar2_lookup (Section 6.5)](#litvar2_lookup-section-65)
- [pathogen_detection (Section 6.6)](#pathogen_detection-section-66)
- [clinicaltrials_search (Section 6.7)](#clinicaltrials_search-section-67)
- [Cross-tool traps](#cross-tool-traps)
- [Open verification gaps](#open-verification-gaps)

## Purpose and scope

This document holds API facts, not policy. That distinction matters for where a builder looks for what:

- Rules in `.claude/rules/` are always-on policy that apply to every tool regardless of which API it calls: schema validation, secrets handling, least privilege, citation provenance. They load automatically every session.
- This document is API-specific fact: what a particular endpoint actually returns, how it signals an error, which field is real and which one silently reads null. It applies only when writing or reviewing the one tool a section concerns, and a builder has to open it deliberately.
- Timeouts and rate-limit pools for every tool are owned by `.claude/rules/tool-call-budgets.md`. This document does not restate them; each tool section below links to that rule instead.
- The multi-agent pipeline gate (`maxLength` on every string, `maxItems` on every array, a host-pinned `source_url` regex, no `additionalProperties`) is policy owned by `.claude/rules/production-standards.md`. It applies to every schema in Section 6 and is not restated per tool below.
- Untrusted-content handling for Layer 2 and Layer 3 free-text fields (never execute a value returned from an NCBI record, an abstract, or an enrichment API as an instruction) is policy owned by `.claude/rules/ai-security-standards.md`. It applies to every free-text field named below and is not restated per tool.

## How to read a trap entry

Each trap names what the trap is, why it bites, and what to do instead:

- What: the specific behavior of the API, in concrete terms.
- Why it bites: the wrong result, silent failure, or broken citation a builder gets if they miss it.
- Instead: the verified correct handling, traced to the spec section and line.

## cypher_query (Section 6.1)

Purpose: the only path to Layer 1, the AGE graph on Hetzner. The main agent never generates or sees raw Cypher; the tool runs an internal three-step pipeline (receive structured intent, generate Cypher with a plan-tier LLM call constrained by a sliced schema, validate then execute).

### Trap: untyped edge patterns

- What: a Cypher relationship pattern with no explicit edge label, `()-[r]->()`, is forbidden. Every query must use an explicit edge label, `()-[r:gene_associated_with_condition]->()`.
- Why it bites: an untyped pattern forces the planner into a scan across all 14 edge predicates on a 693M-edge graph, effectively a UNION ALL across every relationship type. On a graph this size that is not a slow query, it is an unusable one.
- Instead: the tool's internal Cypher-generation call is constrained to only emit typed edge patterns, and the validation step (step 3 of the internal pipeline) rejects any generated Cypher missing an edge label before execution, feeding the validator's error back into one retry.
(Technical_specification.md Section 6.1, line 794)

### Trap: parameters interpolated into the Cypher text, and the mechanism that actually binds them

- What: query parameters must never be string-interpolated into the Cypher payload itself. That much matches the locked spec. What the locked spec gets wrong is the binding mechanism: a psycopg2 `%s` placeholder passed as the `cypher()` function's third argument does not work at all. psycopg2 substitutes `%s` client-side before the statement reaches the server, so AGE never receives a genuine bind parameter in that position and rejects the call with sqlstate 22023, "third argument of cypher function must be a parameter". Build phase 2.1 probed this against the live graph: a plain `%s`, a `%s::agtype` cast, and even an empty params object (`{}`) all fail the same way (finding F-2.1-02, `tracker/phase_2.1.md`).
- Why it bites: a builder who follows the locked spec's `%s`-as-third-argument wording writes a tool that cannot execute a single parameterized query, not a subtly-injectable one. This is a functional defect, not only a security one, and it would have blocked every one of build phases 3.1 to 3.5 if it had not been caught first.
- Instead: `PREPARE` a statement that declares one `agtype` parameter, then `EXECUTE` it with the params JSON bound through the psycopg2 `%s` placeholder on the `EXECUTE` call, never on the `cypher()` call itself, then `DEALLOCATE` the statement in a `finally` block. When there are no caller-supplied parameters, omit the third argument to `cypher()` entirely rather than passing `{}`. This is the shipped mechanism in `src/system_03_search_agent/tools/graph_connection.py` (`_build_prepare_sql`, `_build_execute_sql`, `_build_deallocate_sql`, wired together in `execute_cypher`). See `.claude/rules/production-standards.md` query-safety gate and `.claude/rules/production-examples.md` example 1 for the full before and after.
(Technical_specification.md Section 6.1, line 794, wrong on the binding mechanism, reconciliation pending at Step 6.2; `tracker/phase_2.1.md` finding F-2.1-02 is the corrected account)

### Trap: missing LIMIT

- What: a generated query with no `LIMIT` clause.
- Why it bites: an unbounded result set against a 693M-edge graph can return far more rows than the agent should ever inline into model context.
- Instead: the tool injects `row_limit` (default 100, hard max 500) before execution if the generated Cypher omits one, and sets `truncated: true` plus `total_available` whenever the true row count exceeds what was returned.
(Technical_specification.md Section 6.1, line 800)

### Trap: treating zero rows as an error

- What: a query that legitimately matches nothing.
- Why it bites: mapping an empty result to `status: "error"` instead of `status: "empty"` breaks the cite-or-refuse contract downstream: Write needs to distinguish "nothing found, refuse cleanly" from "something went wrong, surface the failure."
- Instead: zero rows is `status: "empty"`, not an error. This is the Layer 1 cite-or-refuse trigger.
(Technical_specification.md Section 6.1, line 798)

### Trap: exposing raw Cypher to the end user

- What: the `cypher_executed` output field is the literal generated Cypher string.
- Why it bites: rendering this field directly to a user turns an internal audit artifact into a UI element, and it is not filtered for anything user-safe.
- Instead: `cypher_executed` is audit trail only. It supports debugging and tracing (LangSmith), never rendered raw to the end user.
(Technical_specification.md Section 6.1, line 788)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## ncbi_efetch (Section 6.2)

Purpose: the general Layer 2 client. Covers Entrez E-utilities (search, fetch, summary, link, coordinate_overlap) across 14 databases, the NCBI Datasets API v2, and PubChem PUG REST, one tool with seven actions discriminated by the `action` field.

### Trap: trusting HTTP 200 as success

- What: E-utilities returns HTTP 200 for a genuinely empty result (`count: "0"`, `idlist: []`) and for several distinct error classes (an invalid db name arrives as a 200 body with `esearchresult.ERROR`, EFetch on a nonexistent id arrives as a 200 with an empty record set and no error node).
- Why it bites: code that branches on HTTP status to decide success or failure, the natural instinct for anyone who has built a REST client before, will treat every one of these cases as success and either synthesize an answer from nothing or crash trying to parse a missing field.
- Instead: for every E-utilities action, inspect the response body, never the HTTP status, to decide `status: "ok"` vs `"empty"` vs `"error"`. This is the single most load-bearing finding for this tool. Datasets v2 and PubChem are the exception: they return proper HTTP status codes (400 with a structured `{"error", "code", "message"}` or `{"Fault": {...}}` body), so those two actions branch on status directly, the opposite convention from every other action on this same tool.
(Technical_specification.md Section 6.2, line 982)

### Trap: ELink without an explicit target db

- What: calling ELink's `link` action without setting `db` explicitly.
- Why it bites: ELink's default behavior can be dominated by computed neighbor sets like `pubmed_pubmed*`, which are similarity-based, not the direct cross-reference the caller actually wants.
- Instead: the `link` action's input schema requires `db` as an explicit target database. It is never left to the ELink default.
(Technical_specification.md Section 6.2, line 858)

### Trap: unknown ESearch field tags

- What: passing an ESearch field tag (`field_tags`) that is not a real field for the target `db`.
- Why it bites: E-utilities does not error on an unknown field tag. It silently falls back to a broad, unfiltered search, which returns results but not the results the caller asked for, with no signal that the filter was ignored.
- Instead: validate every field tag against the EInfo field list for that `db` before the call. Never build `field_tags` from free text passed straight through.
(Technical_specification.md Section 6.2, line 829 and line 978)

### Trap: trusting the raw ESearch coordinate range as interval overlap

- What: dbVar and ClinVar coordinate-range search on Entrez (`<chr>[CHR] AND <start>:<end>[BASE]` or `[C37]`/`[CPOS]`) looks like true genomic interval overlap but is not.
- Why it bites: this is a proven live bug, not a theoretical one. Three sampled "hits" on a chr1 GRCh38 window were all 0bp point insertions that matched only because a GRCh37 unplaced-scaffold start happened to pair numerically with a GRCh38 end. Trusting the raw ESearch range as the answer silently returns false-positive variants.
- Instead: run the five-step procedure. ESearch coarse prefilter, then ESummary each candidate id and read the actual placement (`dbvarplacementlist` for dbVar, `C37`/`CPOS`/`VLEN` for ClinVar), select the placement entry matching the requested assembly, then apply the exact overlap predicate in tool code, `placement.chr_start <= end AND placement.chr_end >= start`. Drop any candidate that fails the predicate. Skipping the ESummary and predicate steps and trusting the raw ESearch range is the exact bug proven live.
(Technical_specification.md Section 6.2, lines 961 to 969)

### Trap: ClinVar's germline_classification field shape

- What: `germline_classification` in ClinVar ESummary output is an object, not a flat scalar.
- Why it bites: code written against an assumed flat string, the natural shape to guess, silently extracts the wrong value or crashes on a type mismatch. This is a drift-verified field, meaning the shape was confirmed live, not assumed from documentation.
- Instead: parse `germline_classification` as an object. Treat any ESummary field extraction as unverified until checked against a live response, not against API documentation alone.
(Technical_specification.md Section 6.2, line 952)

### Trap: two different error-signaling conventions on one tool

- What: `ncbi_efetch` wraps both E-utilities (200-with-body-error) and Datasets v2 or PubChem (proper HTTP status codes) behind a single tool with one output shape.
- Why it bites: error-handling code written once and assumed to cover every action on the tool will get one family right and the other silently wrong.
- Instead: branch error handling on which action is running, not on a single shared code path. E-utilities-backed actions (search, fetch, summary, link, coordinate_overlap) inspect the response body. Datasets- and PubChem-backed actions (dataset_report, pubchem_property) branch on HTTP status.
(Technical_specification.md Section 6.2, lines 973 to 982)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## ncbi_dbsnp (Section 6.3)

Purpose: variant normalization and dbSNP record retrieval. Primary path is NCBI Variation Services, a separate host and rate pool from E-utilities; a secondary dbSNP ESummary call supplies clinical and population fields Variation Services does not carry.

### Trap: reading global_maf instead of global_mafs

- What: dbSNP ESummary exposes both a flat `global_maf` scalar and a `global_mafs` array. They look interchangeable from the field name alone.
- Why it bites: `global_maf` is verified null. Code that reads it returns no frequency data at all, with no error to indicate anything went wrong. The failure is silent: the field parses fine, it is just always empty.
- Instead: read frequency data only from the `global_mafs` array. Never read the flat `global_maf` scalar.
(Technical_specification.md Section 6.3, line 1072)

### Trap: parallelizing the two sub-calls

- What: this tool makes two calls, a Variation Services normalization call and a dbSNP ESummary clinical fetch. Running them concurrently looks like a natural latency optimization.
- Why it bites: the clinical fetch depends on the canonical SPDI the normalization call produces. Running them in parallel means the clinical fetch either races ahead with an unnormalized identifier or has nothing to key off yet.
- Instead: run Variation Services normalization and the dbSNP ESummary clinical fetch sequentially within one tool invocation, never in parallel. Budget up to 30 seconds worst case for the full sequential invocation. This is also the tighter of the tool's two rate pools: Variation Services is roughly 1 request/second, its own pool separate from E-utilities, which is a second, independent reason not to parallelize against it.
(Technical_specification.md Section 6.3, line 1076)

### Trap: treating an empty global_mafs as a failure

- What: `global_mafs: []` with no other error signal.
- Why it bites: some variants genuinely carry no population MAF data. Treating an empty array as a tool failure produces a false error on a request that actually succeeded.
- Instead: `global_mafs: []` alone is `status: "ok"` with `population_frequencies: []`, not a failure.
(Technical_specification.md Section 6.3, line 1074)

### Trap: assuming Variation Services error behavior without verification

- What: Variation Services' behavior on an invalid rsid, SPDI, or HGVS input was not live-verified in the capability sheet; only successful 200 responses were probed.
- Why it bites: shipping error handling based on an assumption rather than a verified response risks the tool mishandling exactly the input class most likely to appear from a malformed user query.
- Instead: tool code defensively treats any non-200 response, or a 200 body missing `refsnp_id`, as `status: "error"`. This defensive path is an open verification gap and must be confirmed live before the tool ships (see Open verification gaps below).
(Technical_specification.md Section 6.3, line 1074)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## pubtator_annotate (Section 6.4)

Purpose: Layer 3 enrichment, entity normalization for free text and entity annotation on publications, via PubTator3.

### Trap: assuming a bare BioC document

- What: the biocjson export endpoint (`/publications/export/biocjson?pmids={csv}`) wraps documents in a top-level `{"PubTator3": [...]}` object.
- Why it bites: code written against the plain BioC document shape, which is what the underlying format's own name suggests, fails to find any content because it never unwraps the outer key. This is a documented drift point from the format's baseline shape.
- Instead: read annotations at `.PubTator3[i].passages[].annotations[]`, each carrying an `infons` object with `type`, `identifier`, `normalized_id` (nullable), `valid`, `biotype`, `database`, `accession`, `name`.
(Technical_specification.md Section 6.4, line 1174)

### Trap: one error convention assumed across both actions

- What: this tool has two modes, `entity_lookup` and `annotate_publications`, with different error-signaling conventions. A no-match `entity_lookup` returns `[]` with HTTP 200 (the same 200-with-empty-body pattern as E-utilities). A biocjson export on a nonexistent PMID returns HTTP 400 with `{"detail": "Could not retrieve publications"}`.
- Why it bites: error-handling code copied from one mode to the other silently mishandles the mode it was not written for.
- Instead: `entity_lookup`'s empty match maps to `status: "empty"`. `annotate_publications`'s HTTP 400 maps to `status: "error"` with the `detail` string as the message. Handle the two modes with separate branches, not one shared path.
(Technical_specification.md Section 6.4, line 1176)

### Trap: treating entity fields as trusted

- What: `name`, `description`, and every annotation field returned by this tool are free text extracted from a source publication.
- Why it bites: treating this text as anything other than data risks the agent acting on an instruction embedded in a publication's text, the prompt-injection surface every Layer 2/3 free-text field carries.
- Instead: these fields get an isolated reader pass before the Synth model sees them. Full policy in `.claude/rules/ai-security-standards.md`; not restated here.
(Technical_specification.md Section 6.4, line 1178)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## litvar2_lookup (Section 6.5)

Purpose: Layer 3 enrichment, variant-to-literature evidence, via LitVar2.

### Trap: unencoded litvar_id in the publications lookup

- What: a `litvar_id` (format `litvar@rs334##`) passed to `/variant/get/{litvar_id}/publications` without URL encoding.
- Why it bites: the `@` and `#` characters in the id are not URL-safe. An unencoded id either fails the request outright or, worse, is silently truncated at the `#` if the client treats it as a fragment separator.
- Instead: URL-encode the id before the call: `@` as `%40`, `#` as `%23`. The tool performs this encoding itself; it is never the caller's responsibility.
(Technical_specification.md Section 6.5, line 1205 and line 1251)

### Trap: inlining the full pmids list

- What: a variant's linked-publication count can be large. The capability sheet's verified example, rs334, carries 589 PMIDs.
- Why it bites: inlining all 589 ids into agent context on every lookup wastes context budget on a list the model does not need in full, and risks crowding out other content in the prompt.
- Instead: `pmids` is capped at `maxItems: 50` in the output schema, with `total_pmids` carrying the true count. Always truncate, always report the total.
(Technical_specification.md Section 6.5, line 1255)

### Trap: assuming the zero-PMID publications case without verification

- What: a publications lookup on an id with zero linked PMIDs is expected to return `{"pmids": []}`, consistent with LitVar2's other verified empty behavior, but this specific case was not independently live-verified.
- Why it bites: shipping this as a confirmed behavior when it is actually inferred by analogy risks a mismatch if the real response shape differs for this specific case.
- Instead: treat this as a low-risk, unverified inference, not a confirmed fact (see Open verification gaps below).
(Technical_specification.md Section 6.5, line 1253)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## pathogen_detection (Section 6.6)

Purpose: Layer 2, bulk access to the NCBI Pathogen Detection PDG snapshot tree. Versioned bulk TSV and tar.gz retrieval with snapshot pinning, not a parameterized Entrez, Datasets, or PubChem call, which is why it is its own tool rather than an `ncbi_efetch` action.

### Trap: pinning to a mid-build snapshot

- What: the FTP results tree (`https://ftp.ncbi.nlm.nih.gov/pathogen/Results/<Taxon>/PDG*/`) can contain a snapshot directory that only has `Metadata/` populated, with `Clusters/` and `AMR/` not yet written.
- Why it bites: resolving to the newest snapshot directory by name alone, without checking which subdirectories actually exist, can pin the tool to a snapshot mid-build. A cluster or AMR query against that snapshot then fails or returns incomplete data, not because the data does not exist, but because the snapshot the tool picked has not finished writing it yet.
- Instead: resolve to the newest COMPLETE snapshot, defined as one whose Metadata, Clusters, and AMR directories are all present. Never a mid-build snapshot.
(Technical_specification.md Section 6.6, line 1348)

### Trap: treating a newer snapshot appearing as an error

- What: a newer complete PDG snapshot can appear between calls, since the underlying data is on NCBI's own build cadence, not the tool's request cadence.
- Why it bites: surfacing this as an error condition would produce spurious failures purely because upstream data updated, which is expected and desired behavior, not a fault.
- Instead: cache until a newer complete snapshot is pinned, re-checked daily. The tool silently re-pins on its next daily check; this is never surfaced as an error.
(Technical_specification.md Section 6.6, line 1356)

### Trap: streaming a full TSV into agent context

- What: the underlying Metadata, Clusters, and AMR files are bulk TSVs that can be large.
- Why it bites: loading a full TSV into context to find the matched rows defeats the same context-budget concern as any other large tool result, and risks crowding out the rest of the prompt.
- Instead: index and read only the matched rows. Never stream or load a full TSV into agent context. Report `total_available` whenever `isolates` is truncated.
(Technical_specification.md Section 6.6, line 1360)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## clinicaltrials_search (Section 6.7)

Purpose: Layer 3, the disease-to-trials path, via ClinicalTrials.gov API v2. Not folded into `ncbi_efetch` because the host is NLM-hosted at a non-`ncbi.nlm.nih.gov` domain.

### Trap: reusing the NCBI host-pinned source_url regex

- What: every other tool's `source_url` pattern is pinned to an `ncbi.nlm.nih.gov` subdomain (`NCBI_RECORD_HOST`). ClinicalTrials.gov is a different domain entirely.
- Why it bites: copying the `NCBI_RECORD_HOST` pattern onto this tool's schema either rejects every valid ClinicalTrials.gov citation or, if loosened carelessly to compensate, opens the host-pinning check up too far and defeats the purpose of pinning it at all.
- Instead: this tool uses its own host-pinned pattern, `CLINICALTRIALS_HOST`: `^https://(www\.)?clinicaltrials\.gov/study/`. Never reuse the NCBI pattern here.
(Technical_specification.md Section 6.7, line 1411)

### Trap: treating trial free text as trusted

- What: `brief_title`, `eligibility_summary`, and every free-text module field are content submitted by a trial sponsor, not generated or vetted by NCBI.
- Why it bites: same prompt-injection surface as any other Layer 2/3 free-text field, treating it as trusted risks the agent acting on embedded content as if it were an instruction.
- Instead: these fields get the isolated reader pass before Synth ever sees them. Full policy in `.claude/rules/ai-security-standards.md`; not restated here.
(Technical_specification.md Section 6.7, line 1433)

Timeouts and rate limits: `.claude/rules/tool-call-budgets.md`.

## Cross-tool traps

Two traps are not specific to one tool. They apply across the whole roster.

### Trap: citation URLs pointing at the fetch host instead of the record page

- What: every tool calls a fetch host to retrieve data, `eutils.ncbi.nlm.nih.gov`, `api.ncbi.nlm.nih.gov`, and so on, but the citation the user sees must point somewhere a human can actually read.
- Why it bites: a `source_url` that resolves to the API endpoint the tool called, rather than the human-facing record page, is technically a working URL but breaks the entire point of a citation: a reader following it gets a raw API response, not the record.
- Instead: every `source_url` always resolves to the human-facing record page, `www.ncbi.nlm.nih.gov/...`, `pubmed.ncbi.nlm.nih.gov/...`, `clinicaltrials.gov/study/...`, never the `eutils.` or `api.` host the tool actually called. This is the concrete enforcement point for the host-pinned `source_url` regex on every schema in Section 6: a looser any-subdomain pattern would let a fetch host leak into a citation.
(Technical_specification.md Section 6, line 716)

### Trap: fuzzy-matching an identifier that was already exact

- What: running embedding similarity or entity normalization (PubTator3, LitVar2) on a query that already contains a recognizable exact identifier, a PMID, an rsID (`rs\d+`), a gene symbol, an accession pattern (`NM_`, `NC_`, `NP_`), or a CURIE already in `prefix:local_id` form.
- Why it bites: a fuzzy pass over an already-exact identifier can resolve it to the wrong nearby concept where an exact-match check would have found the right one with zero ambiguity. This is the identifier-dropping failure mode semantic search has on exact identifiers.
- Instead: before any fuzzy matching, the Think step checks the query text for a recognizable exact identifier first. An exact match resolves directly and is treated as ground truth for every downstream tool call. Fuzzy matching runs only when no recognizable exact identifier is present, and once fuzzy matching resolves a CURIE, the query is handled as an exact-ID lookup from that point forward, never carried as an ongoing fuzzy filter through the rest of the loop.
(Technical_specification.md, line 2719)

## Open verification gaps

Three items in Section 6 are flagged as verified-behavior assumptions rather than live-confirmed facts. Each must be live-verified before the tool it concerns ships.

| Gap | Tool | What is assumed | What must be confirmed |
|-----|------|-------------------|--------------------------|
| Variation Services error behavior | ncbi_dbsnp | Any non-200 response, or a 200 body missing `refsnp_id`, is treated as `status: "error"` | Live-verify actual Variation Services responses to an invalid rsid, SPDI, or HGVS input |
| Zero-PMID publications lookup | litvar2_lookup | `{"pmids": []}` by analogy to autocomplete's verified empty-array-plus-200 shape | Independently live-verify a publications lookup against an id with zero linked PMIDs |
| PubTator3 relations endpoint | pubtator_annotate | Endpoint exists for entity-pair relations (chemical-disease, gene-disease) | Live-verify exact path and fields; deferred to a fast-follow addition once verified, not built in v1 |

(Technical_specification.md Section 6.2 line 1174, Section 6.3 line 1074, Section 6.5 line 1253, and the Open items note at the close of Section 6, lines 1461 to 1467.)
