# Phase 2.1: cypher_query over Layer 1

Build phase 2.1 delivers `cypher_query`, the only path to Layer 1: a three-step internal pipeline (receive structured intent, generate Cypher against a sliced schema with a plan-tier call, validate then execute), plus edge-label enforcement and the Act-step wiring that makes F-2.0-08 and F-2.0-14 live.

Depends on: phase 2.0 (done, merged as PR #9)
Branch: `phase/2.1-cypher-tool`
Spec: `requirements/Technical_specification.md` Section 6.1, Section 9 (provenance), Section 19 (cost control)
Reference: `docs/ncbi/Tool_implementation_mechanics.md`, `docs/data-engineering/Knowledge_graph_on_server_reference.md`

## Phase premise (the done-when)

A real query reaches the live AGE graph through `cypher_query` and returns cited rows, with the main agent never generating or seeing raw Cypher. A phase where every ticket passes but no query reaches the graph is a failed phase, not a passed one (LEARNINGS rows 28 and 30).

## Phase close status: reworked, NOT re-reviewed

Read this before opening build phase 2.2. It is the one thing about this phase that a reader would otherwise get wrong.

The premise is met. `tests/system_03_search_agent/tools/test_cypher_query_e2e.py` runs 9 tests against the live graph with only the model call mocked, and all 9 pass. The full suite is 798 passing. That gate cannot be satisfied by mocks, which is precisely what caught the original failure.

What did not happen: the judge and the adversary reviewed the code as it stood BEFORE the rework, and both failed it. Everything shipped since that verdict is unreviewed by any independent agent:

- agtype parsing and the provenance mapping (F-2.1-A1, F-01)
- the true-total count query (A2)
- entity extraction in `plan_node` (A3)
- the cite-or-refuse enforcement path (F-02, A5)
- four Cypher validator bypass fixes (A4, A8, A9, F-08)
- the recursive structured-field caps (F-03)
- the per-query cost cap inside the tool (F-04)
- the Seq Scan planner fix (F-2.1-07)

This phase's own history is the reason that matters. The first time every ticket read green, the judge found the phase premise unmet and the adversary found 17 defects. A green suite has already been wrong once here.

The product owner merged with this gap explicitly recorded rather than glossed, trading a second review round against a budget limit. That is a deliberate, informed decision, not an oversight. Build phase 2.2 depends directly on this code and should treat a fresh judge and adversary pass over the phase 2.1 surface as its own first task, not as optional.

Also carried forward, not fixed: F-06 (2 of 6 model calls bypass the stable prompt prefix, a cost inefficiency rather than a correctness defect) and the operational fact that the SSH tunnel to the graph is a manual step no repo code performs, so a fresh clone cannot run the live tests without it.

## Layer 1 access, verified 2026-07-29

Established during phase open, before any ticket was scoped:

- Transport: SSH local port-forward, `ssh -N -L 15432:127.0.0.1:5432 root@46.225.128.133`. This is Decision D phase one. Postgres listens on 127.0.0.1 only; port 5432 is refused from outside, so there is no direct-connect option.
- Credential: role `kg_reader`, created 2026-07-29 with product-owner approval. Non-superuser, `LOGIN`, `pg_read_all_data`, `default_transaction_read_only = on`, `statement_timeout = 30s`, `session_preload_libraries = age`.
- Why `session_preload_libraries`: a non-superuser cannot run `LOAD 'age'` (`InsufficientPrivilege: access to library "age" is not allowed`). Setting the preload per role makes AGE available at session start without adding `age` to `shared_preload_libraries`, which would have required restarting the production database.
- Proven read: `MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: 'NCBIGene:672'})` returned 3 real ClinVar rows in 133 ms as `kg_reader`.
- Proven refusal: `CREATE TABLE`, `INSERT`, Cypher `CREATE`, and Cypher `DETACH DELETE` all rejected. Graph integrity re-verified afterwards: BRCA1 node present, 15,310 variant edges, `Gene` table at 67,536,325 rows, no probe table created.

Credentials live in the gitignored `.env` as `GRAPH_PG_HOST`, `GRAPH_PG_PORT`, `GRAPH_PG_USER`, `GRAPH_PG_PASSWORD`, `GRAPH_PG_DBNAME`. Never logged, never committed.

## Ticket map

| Ticket | Owner slice | Files |
|--------|-------------|-------|
| T-2.1-01, 02, 03 | Builder A, the input and generation side | `tools/cypher_schemas.py`, `tools/schema_slice.py`, `tools/cypher_generation.py` |
| T-2.1-04, 05 | Builder B, pure transforms | `tools/cypher_validator.py`, `tools/cypher_provenance.py` |
| T-2.1-06 | Builder C, the I/O side | `tools/graph_connection.py` |
| T-2.1-07, 08 | Lead, integration | `tools/cypher_query.py`, `core/graph.py`, `harness/coordinator_worker.py` |
| T-2.1-09 | Test writer | `tests/system_03_search_agent/tools/test_cypher_query_e2e.py` |

No two tickets write the same file.

## Tickets

### T-2.1-01: Section 6.1 input and output schemas

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: none
Spec: Technical_specification.md Section 6.1
Files: `src/system_03_search_agent/tools/cypher_schemas.py`, `tests/system_03_search_agent/tools/test_cypher_schemas.py`

Acceptance criteria:
- [x] `CypherQueryInput` accepts exactly `query_intent` (max 1000 chars), `query_class` (enum: lookup, single_hop, multi_hop, aggregate, exploratory), `target_entities` (max 10 items, each max 100 chars), `row_limit` (1 to 500, default 100), and rejects any additional property
- [x] `CypherQueryOutput` carries `status` (enum: ok, empty, error), `rows` (max 500 items), `row_count`, `total_available`, `truncated`, `cypher_executed` (max 2000 chars), `error` (max 500 chars), and rejects any additional property
- [x] `CypherQueryRow` carries `node_or_edge_type` (max 50), `curie` (max 100), `fields` (max 30 properties), `source_url`, `graph_snapshot_version` (max 40)
- [x] `source_url` is validated against the host-pinned pattern `^https://(www\.|pubmed\.)?ncbi\.nlm\.nih\.gov/` and a URL on any other host is rejected
- [x] A `row_limit` of 0, 501, or a non-integer is rejected; a `query_class` outside the enum is rejected
- [x] Tests cover valid input, invalid input, and null or missing input for every model

Evidence:
- `CypherQueryInput` class and `extra="forbid"`: `cypher_schemas.py:54,62`; `row_limit` bounds `Field(ge=1, le=500)` default 100: `cypher_schemas.py:69`; `target_entities` max 10 items, each max 100 chars: `cypher_schemas.py:65-68`
- `QueryClass` enum (lookup, single_hop, multi_hop, aggregate, exploratory): `cypher_schemas.py:40-49`
- `CypherQueryOutput` class, `status` pattern enum, `rows` max_length 500, `cypher_executed` max 2000, `error` max 500: `cypher_schemas.py:116-133`
- `CypherQueryRow` class, field length caps, `_cap_fields_count` maxProperties=30 validator: `cypher_schemas.py:73-113`
- `source_url` host-pinned pattern imported (never duplicated) from `graph_schema_constants.NCBI_RECORD_URL_PATTERN`: `cypher_schemas.py:34,94`
- Test run, this file only: `pytest tests/system_03_search_agent/tools/test_cypher_schemas.py -q` -> `39 passed in 0.03s`
- Full three-module run: `pytest tests/system_03_search_agent/tools/ -q` -> `72 passed in 0.05s` (no other builders' test files present yet in this worktree)
- Valid/invalid/null coverage for all three models: `test_cypher_schemas.py` has 39 tests spanning `test_input_valid_full`/`test_input_valid_defaults` through `test_input_rejects_*`, `test_row_valid_*` through `test_row_rejects_*`, and `test_output_valid_*` through `test_output_rejects_missing_*`/`test_output_rejects_null_truncated`
- `ruff check` on all three of this ticket's files plus siblings: `All checks passed!`

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-a: implemented, all acceptance criteria hold, 39/39 tests pass, set in-review

---

### T-2.1-02: Sliced graph schema for prompt injection

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: none
Spec: Technical_specification.md Section 6.1, `.claude/rules/prompt-cache-discipline.md`
Files: `src/system_03_search_agent/tools/schema_slice.py`, `tests/system_03_search_agent/tools/test_schema_slice.py`

The 11 vertex labels and 14 edge labels are enumerated in `docs/data-engineering/Knowledge_graph_on_server_reference.md` sections D, E, and F. They are static, so this module hardcodes them rather than querying the live graph on every call.

Acceptance criteria:
- [x] `VERTEX_LABELS` holds all 11 labels from reference section D, `EDGE_LABELS` holds all 14 from section E, `CURIE_PREFIXES` holds all 9 from section F
- [x] `GRAPH_NAME` is `ncbi_kg`
- [x] `full_schema_text()` returns a deterministic string, byte-identical across calls in one process, suitable for the stable prompt prefix
- [x] `build_schema_slice(query_class, target_entities)` returns only the labels and predicates plausibly relevant to that query class, never the full 693M-edge topology dump
- [x] Each edge label in the emitted slice carries its typical endpoint pair, so a generator cannot invent a `Gene -> Article` edge that has no label
- [x] The emitted slice states the three performance rules from reference section H: always specify the edge label, match by `id` with the right CURIE prefix, keep regex matches narrow
- [x] Two calls with the same arguments return byte-identical output, asserted by SHA-256 comparison

Evidence:
- `VERTEX_LABELS`, `EDGE_LABELS`, `CURIE_PREFIXES` are imported, never re-declared, from `graph_schema_constants` (source of truth, already holds all 11/14/9): `schema_slice.py:38-44`. Coverage asserted in `test_full_schema_text_contains_every_vertex_label`, `test_full_schema_text_contains_every_edge_label`, `test_full_schema_text_contains_every_curie_prefix`
- `GRAPH_NAME` re-exported: `schema_slice.py:42`, `__all__` at `schema_slice.py:56`; asserted in `test_graph_name_reexported` (`schema_slice.GRAPH_NAME == "ncbi_kg"`)
- `full_schema_text()`: `schema_slice.py:154-160`; determinism proven with SHA-256 in `test_full_schema_text_deterministic_across_calls`
- `build_schema_slice()`: `schema_slice.py:218-243`; hop-based filtering by `query_class` via `_QUERY_CLASS_HOPS` (`schema_slice.py:80-87`), `_direct_labels`/`_expand_labels`/`_edges_for_labels` (`schema_slice.py:163-215`); determinism proven with SHA-256 in `test_build_schema_slice_deterministic_same_args`
- Endpoint pair on every emitted edge, or the mixed-pair note for close_match/exact_match: `_endpoint_text` at `schema_slice.py:95-103`; asserted in `test_full_schema_text_every_edge_has_endpoint_pair_stated` and `test_build_schema_slice_edges_carry_endpoint_pairs`
- Three performance rules from reference section H stated verbatim in substance: `_PERFORMANCE_RULES` at `schema_slice.py:61-77`; asserted in `test_full_schema_text_states_performance_rules` and `test_build_schema_slice_states_performance_rules`
- Test run, this file only: `pytest tests/system_03_search_agent/tools/test_schema_slice.py -q` -> `19 passed in 0.01s`
- Full three-module run: `pytest tests/system_03_search_agent/tools/ -q` -> `72 passed in 0.05s`
- `ruff check schema_slice.py`: `All checks passed!` (fixed one `__all__` sort order and three implicit-string-concatenation warnings during review)

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-a: implemented, all acceptance criteria hold, 19/19 tests pass, set in-review

---

### T-2.1-03: Cypher generation with one repair retry

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: T-2.1-01, T-2.1-02
Spec: Technical_specification.md Section 6.1, Section 3.3
Files: `src/system_03_search_agent/tools/cypher_generation.py`, `tests/system_03_search_agent/tools/test_cypher_generation.py`

Section 6.1: validation failure gets one retry that feeds the validator's error back into the generation call. A second failure returns `status: "error"`. The repair retry is in v1 scope.

Acceptance criteria:
- [x] `generate_cypher(harness, tool_input, schema_slice, prior_error=None)` issues exactly one plan-tier call via `harness.call_tier("plan", ...)` and returns the generated Cypher string
- [x] The model is resolved through the harness tier, never hardcoded (`system-design-patterns` rule 11)
- [x] When `prior_error` is supplied, the prompt includes the validator's error text and the previously rejected Cypher, so the retry is informed rather than a blind resample
- [x] The generation prompt instructs explicit edge labels on every relationship and parameterized values, never literals interpolated into the Cypher text
- [x] The returned string is the Cypher body only, with no markdown fence, no prose, and no `SELECT * FROM cypher(...)` wrapper
- [x] A model response containing prose around the Cypher is stripped to the Cypher body deterministically, or rejected; it is never passed through raw
- [x] Tests mock the harness and cover: a clean generation, a generation with `prior_error` set, a fenced response, and a response with no recoverable Cypher

Evidence:
- `generate_cypher()`, exactly one `harness.call_tier("plan", messages)` call: `cypher_generation.py:214-243`; no model id string anywhere in this module (only `"plan"`, the tier name, is passed; `harness` is untyped/`HarnessLike` Protocol at `cypher_generation.py:75-88` so no `harness.harness.Harness` import is even taken)
- `prior_error` threaded into the user message, including validator error text and the caller-supplied rejected-Cypher text: `_build_user_message` at `cypher_generation.py:200-211`
- System prompt instructs explicit edge labels, `$param_name` parameterization, no fence/prose/SQL wrapper, no self-added `LIMIT`: `_build_system_message` at `cypher_generation.py:184-198`
- Deterministic extraction: fenced block first, then a bare SQL-wrapper across the whole response, then first Cypher-keyword-opening line, each run through `_strip_sql_wrapper`; no recoverable case raises `CypherGenerationError` rather than passing raw text through: `_extract_cypher_body` at `cypher_generation.py:108-181`, `_strip_sql_wrapper` at `cypher_generation.py:91-104`
- Test run, this file only: `pytest tests/system_03_search_agent/tools/test_cypher_generation.py -q` -> `14 passed in 0.02s`, covering clean generation, exactly-one-call, prompt-includes-schema-slice, prompt instructs edge labels/parameters, prior_error with validator error and rejected Cypher present, no-prior_error omits retry language, fenced-with-language-tag, bare-fenced, prose-before-keyword, SQL-wrapper-inside-fence, SQL-wrapper-without-fence, no-recoverable-Cypher raises, empty-response raises, empty-fence raises
- Full three-module run: `pytest tests/system_03_search_agent/tools/ -q` -> `72 passed in 0.05s`. No network or database call anywhere in this file: `harness.call_tier` is a hand-written async fake (`_FakeHarness` in the test file), never `litellm` or a real `Harness`
- `ruff check cypher_generation.py`: `All checks passed!`

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-a: implemented, all acceptance criteria hold, 14/14 tests pass, set in-review

---

### T-2.1-04: Cypher validator

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: none (pure logic, validates strings)
Spec: Technical_specification.md Section 6.1, `docs/ncbi/Tool_implementation_mechanics.md`, `.claude/rules/production-standards.md`
Files: `src/system_03_search_agent/tools/cypher_validator.py`, `tests/system_03_search_agent/tools/test_cypher_validator.py`

Acceptance criteria:
- [x] `validate_cypher(cypher, row_limit)` returns a result object carrying `ok`, a machine-readable `reason` code, a human-readable message, and the normalized Cypher
- [x] An untyped relationship pattern (`-[r]-`, `-->`, `-[]->`) is rejected with reason `missing_edge_label`, since AGE compiles it to a UNION ALL across all 14 edge tables
- [x] A relationship carrying a label not in `EDGE_LABELS` is rejected with reason `unknown_edge_label`
- [x] A node pattern carrying a label not in `VERTEX_LABELS` is rejected with reason `unknown_vertex_label`
- [x] Any write clause (`CREATE`, `MERGE`, `DELETE`, `DETACH DELETE`, `SET`, `REMOVE`, `DROP`) is rejected with reason `write_clause_forbidden`, whatever its casing or surrounding whitespace
- [x] A query with no `LIMIT` has `LIMIT {row_limit}` injected before execution; a query whose `LIMIT` exceeds 500 is lowered to 500
- [x] A validated query never contains a value interpolated by f-string or `.format()`; the validator rejects Cypher whose literal count suggests interpolation of a caller-supplied entity when a parameter was available
- [x] Validation is deterministic: the same input string always yields the same verdict, with no model call and no fuzzy scoring
- [x] Tests cover every reason code above, plus a valid single-hop query, a valid multi-hop query, and casing variants of each forbidden keyword

Evidence:
- `src/system_03_search_agent/tools/cypher_validator.py`: `ValidationResult` frozen dataclass at line 108, `validate_cypher` at line 209, reason constants at lines 55 to 60.
- `tests/system_03_search_agent/tools/test_cypher_validator.py`: 41 tests, one per acceptance criterion plus casing variants (12 casings across the 8 forbidden clauses) and 5 untyped-relationship shorthands.
- Test run, from the worktree root:
  `"/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/venv/bin/python" -m pytest tests/system_03_search_agent/tools/test_cypher_validator.py -v`
  Result: `41 passed in 0.04s` (last line of the run), zero failures, zero skips.
- Determinism check: `test_validation_is_deterministic_across_repeated_calls` runs `validate_cypher` 5 times on the same string and asserts all 5 `ValidationResult` values are equal (test_cypher_validator.py line ~304).
- Substring false-positive guard verified directly: `test_identifier_containing_forbidden_keyword_as_substring_is_not_flagged` (a `dataset_id` property with no literal passes cleanly) and `test_identifier_substring_with_a_real_literal_fails_for_the_right_reason` (a `dataset_id` property with a literal value fails with `literal_interpolation_suspected`, never `write_clause_forbidden`).

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-b: implemented `cypher_validator.py` and its test suite, all 41 tests passing, set to in-review

---

### T-2.1-05: Layer 1 provenance and source URLs

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: none (pure transform)
Spec: Technical_specification.md Section 9, Section 6.1
Files: `src/system_03_search_agent/tools/cypher_provenance.py`, `tests/system_03_search_agent/tools/test_cypher_provenance.py`

Acceptance criteria:
- [x] `source_url_for_curie(curie)` maps each of the 9 CURIE prefixes in reference section F to its NCBI record page: NCBIGene to `/gene/`, ClinVar to `/clinvar/variation/`, MedGen to `/medgen/`, PMID to `pubmed.ncbi.nlm.nih.gov/`, NCBITaxon to `/Taxonomy/Browser/`, and the remaining prefixes to their documented targets. Disposition: GO, MeSH, HP, and MONDO have no NCBI-hosted record page (Gene Ontology, HPO, and Mondo are not NCBI databases), so their documented target is `None`, never a fabricated non-NCBI host URL. Documented in the module docstring, not silently decided.
- [x] Every URL produced matches the host-pinned pattern `^https://(www\.|pubmed\.)?ncbi\.nlm\.nih\.gov/`
- [x] A CURIE with an unrecognized prefix returns `None` rather than a guessed or malformed URL
- [x] A node or edge that already carries a stored `source_url` keeps it, and that stored value is validated against the host-pinned pattern before use; a stored URL on a foreign host is discarded, not passed through
- [x] `to_output_row(raw_row, snapshot_version)` returns a dict satisfying `CypherQueryRow` with `node_or_edge_type`, `curie`, `fields`, `source_url`, and `graph_snapshot_version` all populated
- [x] A row that cannot be given a valid `source_url` is returned with `source_url` absent (`None`) and never a fabricated link
- [x] Tests cover all 9 prefixes, an unknown prefix, a stored-URL passthrough, and a stored URL on a foreign host

Evidence:
- `src/system_03_search_agent/tools/cypher_provenance.py`: `source_url_for_curie` at line 96, `to_output_row` at line 164, the five documented URL builders at lines 46 to 68, the GO/MeSH/HP/MONDO disposition documented in the module docstring (lines 1 to 26).
- `tests/system_03_search_agent/tools/test_cypher_provenance.py`: 24 tests. `test_documented_prefix_maps_to_expected_ncbi_record_url` (5 cases, one per mapped prefix), `test_non_ncbi_ontology_prefix_returns_none` (4 cases, GO/MeSH/HP/MONDO), `test_every_curie_prefix_in_the_graph_schema_is_covered_by_a_test` (asserts the 5 plus 4 equal all 9 `CURIE_PREFIXES`, guards a future 10th prefix landing untested), `test_unrecognized_or_malformed_curie_returns_none` (6 cases including an unknown prefix, empty string, no colon, empty prefix, empty local id), `test_to_output_row_keeps_a_valid_stored_source_url`, `test_to_output_row_discards_a_stored_source_url_on_a_foreign_host`, `test_to_output_row_falls_back_to_none_when_no_valid_url_can_be_derived`.
- Test run, from the worktree root:
  `"/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/venv/bin/python" -m pytest tests/system_03_search_agent/tools/test_cypher_provenance.py -v`
  Result: `24 passed in 0.04s` (last line of the run), zero failures, zero skips.
- Combined run for both T-2.1-04 and T-2.1-05:
  `"/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/venv/bin/python" -m pytest tests/system_03_search_agent/tools/ -q`
  Result: `65 passed in 0.05s`.

History:
- 2026-07-29 lead: created, scoped from Section 9
- 2026-07-29 builder-b: implemented `cypher_provenance.py` and its test suite, all 24 tests passing, set to in-review. Flagged one scope judgment call for lead review: GO/MeSH/HP/MONDO map to `None` rather than a guessed URL, since none of the four is an NCBI-hosted database.

---

### T-2.1-06: Graph connection and execution

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: none
Spec: Technical_specification.md Section 6.1, `.claude/rules/tool-call-budgets.md`
Files: `src/system_03_search_agent/tools/graph_connection.py`, `tests/system_03_search_agent/tools/test_graph_connection.py`

Follows the AGE connection pattern in `reference/agentic-search-data-engineering/system-02-knowledge-graph/loader/connection.py`, adapted for a read-only, non-superuser role that preloads AGE rather than issuing `LOAD 'age'`.

Acceptance criteria:
- [x] `execute_cypher(cypher, params, row_limit, timeout_s=30.0)` wraps the Cypher as `SELECT * FROM cypher('ncbi_kg', $$ ... $$, %s) AS (...)` and returns rows plus a total-available count
- [x] Parameters pass through the psycopg2 `%s` placeholder as a JSON object; the Cypher text itself is never built with an f-string or `.format()`
- [x] The connection sets `search_path = ag_catalog, "$user", public` and does not call `LOAD 'age'`, since the role preloads it
- [x] A query exceeding 30 seconds returns a timeout error naming the cause and the retry path ("graph query exceeded 30s, retry with a narrower query_intent or a smaller query_class"), and does not leave the connection open
- [x] Connection refused, auth failure, and timeout each return a distinct structured error, never a bare "failed"
- [x] Credentials are read from environment variables only, and no credential value appears in any log line or exception string
- [x] Rows beyond `row_limit` are truncated, with `total_available` reporting the true count and `truncated` set true
- [x] Tests run against a mocked psycopg2 connection for every error path, and one test marked `integration` runs against the live graph and skips cleanly when `GRAPH_PG_HOST` is unset

Evidence:
- `src/system_03_search_agent/tools/graph_connection.py`: `GraphError`/`GraphConnectionError`/`GraphTimeoutError`/`GraphAuthError` at lines 93 to 109; `execute_cypher()` signature at line 236 matches the required interface exactly, plus an optional `as_clause` kwarg; `_SEARCH_PATH_SQL` at line 68 sets `search_path` only, no `LOAD 'age'` anywhere in the module; `_classify_connect_error()` at line 124 and the `except psycopg2.errors.QueryCanceled` / `except psycopg2.OperationalError` chain give connection-refused, auth-failure, and timeout each a distinct `GraphError` subclass with an actionable message; `_redact()` at line 112 strips a credential value out of any message before it is raised, applied to both the default and any injected `connection_factory`; truncation and `total_available` computed at the end of `execute_cypher()`.
- Defect fix (this entry): the original `_wrap_cypher()` passed the params JSON object through a bare psycopg2 `%s` as the `cypher()` function's third argument. Confirmed against the live graph that AGE rejects that with sqlstate 22023, "third argument of cypher function must be a parameter", because psycopg2 substitutes `%s` client-side before the statement reaches the server, so AGE never received a real bind parameter. Every parameterized call was failing. Fixed by replacing `_wrap_cypher()` with `_validate_cypher_and_as_clause()` (shared `$$` and `as_clause` shape checks), `_new_statement_name()` (a `cq_` + `uuid4().hex` unique, code-generated identifier per call), `_build_prepare_sql()` (`PREPARE name(agtype) AS SELECT * FROM cypher(..., $1) AS (...)`), `_build_execute_sql()` (`EXECUTE name(%s);`, the JSON params bound through the real psycopg2 placeholder here, which AGE accepts as a genuine parameter), `_build_deallocate_sql()`, and `_build_no_params_sql()` (omits the third argument to `cypher()` entirely when `params` is empty or None, since AGE rejects an empty params object the same way). `execute_cypher()` now branches on `bound_params`: non-empty uses PREPARE/EXECUTE/DEALLOCATE in a nested try/finally so a failed DEALLOCATE (caught broadly and discarded, `# noqa: BLE001, S110`) never masks the original result or error; empty uses the no-third-argument form directly. The Cypher body is still never built with an f-string or `.format()` from caller-supplied values; the only code-generated, non-caller-supplied token concatenated in is the statement name.
- Injection probe (already run against the live graph before this fix, cited here as the safety evidence for the PREPARE/EXECUTE path): a `gene_id` value of `NCBIGene:672'}) RETURN v UNION MATCH (x:Gene) RETURN x //` passed through the bound EXECUTE parameter returned 0 rows, confirming AGE treats the parameter as an opaque literal rather than as Cypher structure, since psycopg2 escapes the value at the outer `%s` before it ever reaches AGE.
- Test run (tools directory only): `venv/bin/python -m pytest tests/system_03_search_agent/tools/ -q` → `157 passed, 1 skipped in 0.13s`. The 1 skip is `test_live_graph_returns_brca1_via_labelled_edge`, because in a directory-scoped run nothing imports `litellm`, so `GRAPH_PG_HOST` is never populated from `.env` and the new reachability-checking skip guard (`_graph_host_reachable()`, a short TCP connect with a 2 second timeout) correctly reports the host unset.
- Test run (full suite, SSH tunnel open on 127.0.0.1:15432): `venv/bin/python -m pytest -q` → `697 passed, 1 warning in 21.24s`, zero skips. Re-ran filtered to the live test alone to confirm it actually ran rather than being folded into a broad pass count: `venv/bin/python -m pytest -q -k test_live_graph_returns_brca1_via_labelled_edge -v` → `1 passed, 696 deselected, 1 warning in 5.95s`. The live test executed the real `MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) RETURN v` query against the live AGE graph via the fixed PREPARE/EXECUTE path and returned real BRCA1 variant rows (`total_available > 0`), proving the fix resolves the confirmed 22023 defect, not just the mocked unit tests.
- Skip-guard defect fix: the guard previously skipped only when `GRAPH_PG_HOST` was unset in the process environment. Importing `litellm` anywhere in a process calls `load_dotenv()` at import time (`venv/lib/python3.11/site-packages/litellm/__init__.py:27`), which silently loads this repo's `.env` and populates `GRAPH_PG_HOST` even with no SSH tunnel open, so a full-suite run on a machine with no tunnel would have errored instead of skipping. `_graph_host_reachable()` now does a short TCP connect to `GRAPH_PG_HOST:GRAPH_PG_PORT` (default port 5432, 2 second timeout) and the guard skips unless both the variable is set and the host is actually reachable.
- New unit tests added: `test_params_supplied_uses_prepare_execute_deallocate_sequence` asserts exactly one `PREPARE`, one `EXECUTE`, and one `DEALLOCATE` call sharing the same generated statement name, and that no bare `%s` is ever passed as the `cypher()` third argument. `test_no_params_supplied_omits_third_argument_to_cypher` asserts no `PREPARE`/`EXECUTE`/`DEALLOCATE` calls occur and the `cypher()` call has no third argument at all. `test_deallocate_failure_never_masks_a_successful_result` asserts a `DEALLOCATE` that raises `psycopg2.Error` does not affect the returned rows. The existing `test_query_params_pass_through_json_placeholder_not_string_interpolation` was renamed to `test_query_params_pass_through_prepared_statement_not_string_interpolation` and its assertions rewritten to check the `PREPARE` statement text and the `EXECUTE` call's bound parameter separately, since a single combined `cypher(...)` statement no longer exists on the parameterized path.
- Credential-redaction tests: `test_no_credential_value_appears_in_connection_error_message` and `test_no_credential_value_appears_in_any_raised_exception_across_all_paths` (`tests/system_03_search_agent/tools/test_graph_connection.py`) both set a sentinel password value, force a `psycopg2.OperationalError` whose message contains that sentinel, and assert the sentinel string is absent from the raised `GraphError`'s message. Both still pass, unaffected by this fix.
- `venv/bin/ruff check src/system_03_search_agent/tools/graph_connection.py` → `All checks passed!` (the deallocate cleanup's blind `except Exception: pass` carries `# noqa: BLE001, S110` with an inline justification, since masking a DEALLOCATE failure onto the caller would violate the "never mask the original error" requirement).
- Did not create `tests/system_03_search_agent/tools/__init__.py` per the lead's coordination note; ran pytest against the test directory directly, which collected and ran without it.

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-c: implemented `graph_connection.py` (execute_cypher, GraphError hierarchy, connect/auth/timeout classification, credential redaction, row truncation) and `test_graph_connection.py` (16 tests, 15 pass + 1 clean skip); fast-forwarded this worktree's branch onto `phase/2.1-cypher-tool` first since the worktree had opened before the phase-open commits landed; set status to in-review
- 2026-07-29 fix agent: confirmed defect against the live graph, `execute_cypher`'s bare `%s` cypher() third argument fails every parameterized call with sqlstate 22023. Replaced the single `_wrap_cypher()` with a PREPARE/EXECUTE/DEALLOCATE path for non-empty params (unique per-call statement name, DEALLOCATE in a finally block that never masks the original result or error) and a no-third-argument path for empty or absent params. Fixed the live integration test's skip guard to check actual TCP reachability of `GRAPH_PG_HOST:GRAPH_PG_PORT`, not just whether the env var happens to be set, closing the gap where `litellm`'s import-time `load_dotenv()` populates it from `.env` regardless of whether a tunnel is open. Added 3 new unit tests and rewrote 1 existing test whose assertions no longer matched the corrected SQL shape. Verified: `pytest tests/system_03_search_agent/tools/ -q` → 157 passed, 1 skipped; full suite `pytest -q` → 697 passed, 0 skipped, live test confirmed passing (not skipped) against the real graph over the open SSH tunnel; `ruff check` → all checks passed. Left status at in-review for the lead/judge to close out.

---

### T-2.1-07: cypher_query three-step pipeline

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: T-2.1-01, T-2.1-02, T-2.1-03, T-2.1-04, T-2.1-05, T-2.1-06
Spec: Technical_specification.md Section 6.1
Files: `src/system_03_search_agent/tools/cypher_query.py`, `tests/system_03_search_agent/tools/test_cypher_query.py`

This is the integration ticket, named at decomposition time rather than discovered later (LEARNINGS row 30). It owns the assembly of every module above into the tool the Act step actually calls.

Acceptance criteria:
- [ ] `cypher_query(harness, tool_input)` runs the Section 6.1 pipeline: slice the schema, generate, validate, execute, map to output rows
- [ ] The main agent never receives raw Cypher; the generated string appears only in the `cypher_executed` audit field, never in an event payload rendered to a user
- [ ] A validation failure triggers exactly one repair retry that feeds the validator error back into generation; a second failure returns `status: "error"` with an actionable message
- [ ] Zero rows returns `status: "empty"`, never `status: "error"`, since empty is the Layer 1 cite-or-refuse trigger
- [ ] Every returned row carries a valid host-pinned `source_url` and a `graph_snapshot_version`
- [ ] The whole tool call is bounded at 30 seconds regardless of how the internal steps divide it
- [ ] Tests cover: a successful lookup, a successful multi-hop query, zero rows, a first-attempt validation failure that the retry repairs, two consecutive validation failures, and a timeout

Evidence:
- `src/system_03_search_agent/tools/cypher_query.py` (new). Section 6.1 pipeline: schema slice, generate, validate, execute, provenance-map. Exactly one repair retry; a 30-second outer budget via `asyncio.wait_for`; zero rows returns `status="empty"` and never `"error"`. `cypher_executed` capped at 2000 chars and never copied elsewhere in the output. The function never raises: every failure path folds into `status="error"`.
- `tests/system_03_search_agent/tools/test_cypher_query.py` (new), 9 tests: successful lookup, successful multi-hop, zero rows, first-attempt validation failure repaired by the retry, two consecutive validation failures, outer timeout, `GraphTimeoutError`, `GraphConnectionError`, unrecoverable generation. `pytest tests/system_03_search_agent/tools/test_cypher_query.py -v` -> `9 passed`.
- Full suite after this ticket: `716 passed, 1 warning in 21.5s`, including the live graph integration test. `ruff check src/system_03_search_agent/` -> `All checks passed!`.
- Commit `7c5b8d6` on `phase/2.1-cypher-tool`.
- Known limitation raised by the builder itself and filed as F-2.1-05: `target_entities` binds to the generated Cypher's `$param_name`s POSITIONALLY, because no naming contract exists between the generation step and the binding step. Under judge and adversary review.
- Acceptance criteria deliberately left unchecked here. The lead recorded this evidence but did not build the module and does not check its own criteria; the judge verifies and checks them at close.

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-d: implemented and committed as `7c5b8d6`, set in-review
- 2026-07-29 lead: pasted builder-d's evidence, since builder-d was told not to touch this file while two other agents held it

---

### T-2.1-08: Act-step wiring, cost cap and output caps

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: T-2.1-07
Spec: Technical_specification.md Section 19.1, Section 3.4; findings F-2.0-08 and F-2.0-14
Files: `src/system_03_search_agent/core/graph.py`, `src/system_03_search_agent/harness/coordinator_worker.py`, plus their existing test modules

Closes the two findings phase 2.0 deferred here. Both were latent only because `plan_node` produced an empty `tool_calls` list; this ticket is what makes them live.

Acceptance criteria:
- [ ] `plan_node` selects `cypher_query` for a graph-answerable query and emits a real `ToolCall`, replacing the phase 2.0 stub that always returned an empty list
- [ ] `act_node` executes the selected tool call and passes the real result into `coordinator_worker_execute`, replacing the `[], []` placeholder
- [ ] F-2.0-08: every coordinator-worker reader call is subject to the per-query cost cap and the per-step timeout; a reader call that would breach the cap is not issued, and the query returns a partial result rather than overspending
- [ ] F-2.0-14: the structured pass-through path enforces `maxLength` on every string field and `maxItems` on every array before a `Finding` is built, so a hostile or oversized tool payload cannot reach the Write step unbounded
- [ ] A Cypher row is structured data and passes through without a reader call; no graph row is routed through the free-text reader
- [ ] `build_stable_prefix()` output is still injected into every model call in `graph.py`, verified by asserting the mocked call receives it (guards the LEARNINGS row 28 regression)
- [ ] Tests cover: a query that selects `cypher_query`, a query that selects no tool, a cost-cap breach during Act, and an oversized tool payload that gets capped

Evidence:
- `plan_node` (`core/graph.py`) now deterministically selects `cypher_query` for a substantive query and emits a real `ToolCall`, replacing the phase 2.0 stub's always-empty list. A small fixed set of greetings and non-questions selects no tool.
- `act_node` executes the selected call and maps `CypherQueryOutput` into `ToolExecutionResult.structured_fields`, deliberately omitting `cypher_executed`, replacing the `coordinator_worker_execute(harness, [], [])` placeholder. Graph rows always take the structured pass-through path, never the free-text reader.
- F-2.0-08: the isolated reader pass now calls `cost_control.check_per_query_cap` before dispatch and wraps the call in `harness.enforce_timeout`. A cap breach or timeout degrades to an empty `Finding` rather than raising out of `asyncio.gather`. `act_node` independently checks the cap before invoking `cypher_query` at all, and excludes an un-dispatched call from both `tool_calls` and `results` so the 1:1 pairing holds.
- F-2.0-14: `_structured_pass_through` runs every payload through `_cap_structured_fields` (top-level key count, string length, list length, and one level of nested dict and list capping) before a `Finding` is built.
- Tests: 5 new in `tests/system_03_search_agent/core/test_graph.py`, 6 new in `tests/system_03_search_agent/harness/test_coordinator_worker.py`. Combined run with the tool tests -> `49 passed`.
- Full suite: `716 passed, 1 warning in 21.5s`. `ruff check src/system_03_search_agent/` -> `All checks passed!`. Commit `7c5b8d6`.
- Flagged for the judge, not resolved by the lead: commit `7c5b8d6` changed the shared query fixture in `test_graph.py` and `test_run.py` from "What gene is BRCA1?" to "hello", because the original text now triggers real tool selection and broke phase-2.0-era assertions. New tests were added for the tool path (`_GRAPH_ANSWERABLE_QUERY_TEXT`, +141 lines). Whether this is a legitimate refactor or a weakened verify surface under `goal-contracts.md` is explicitly the judge's call, not the builder's and not the lead's.
- Acceptance criteria deliberately left unchecked here, same reason as T-2.1-07.

History:
- 2026-07-29 lead: created, scoped from F-2.0-08 and F-2.0-14
- 2026-07-29 builder-d: implemented and committed as `7c5b8d6`, set in-review
- 2026-07-29 lead: pasted builder-d's evidence and flagged the test-fixture change for judge adjudication

---

### T-2.1-09: End-to-end verification against the live graph

Status: in-review
Refine: refined
Branch: phase/2.1-cypher-tool
Depends on: T-2.1-08
Spec: Technical_specification.md Section 23
Files: `tests/system_03_search_agent/tools/test_cypher_query_e2e.py`

Acceptance criteria:
- [ ] A query runs the full Guardrail, Think, Plan, Act, Write loop with `cypher_query` executing against the live graph, and returns cited rows
- [ ] The BRCA1 lookup returns the gene name from the live graph, matching the value the phase-open probe recorded
- [ ] A multi-hop query traverses a labelled edge and returns real ClinVar variant rows
- [ ] A query for an entity absent from the graph returns `status: "empty"` and the loop produces a refusal, not a fabricated answer
- [ ] Every citation in the produced answer resolves to a host-pinned NCBI URL
- [ ] Live tests skip cleanly with a stated reason when `GRAPH_PG_HOST` is unset, so the suite stays green on a machine with no tunnel
- [ ] The suite does not depend on an already-open tunnel: it either opens one or skips

Evidence:
- (filled at close)

History:
- 2026-07-29 lead: created, scoped from Section 23

---

## Findings

### F-2.1-01: Spec says 10 concept labels, the graph has 11

Status: filed
Raised by: lead
Severity: low
Ticket: none yet

What happened: `Technical_specification.md` Section 6.1 and `.claude/rules/prompt-cache-discipline.md` both state "the 10 concept labels and 14 edge predicates". `docs/data-engineering/Knowledge_graph_on_server_reference.md` section D enumerates 11 vertex labels (Article, Gene, SequenceVariant, OrganismTaxon, Disease, BiologicalProcess, MolecularActivity, CellularComponent, OntologyClass, PhenotypicFeature, NamedThing), and the live graph confirms 11. The eleventh, `NamedThing`, is the dangling-endpoint stub label from the merge, which is plausibly why it was excluded from a "concept" count.

Why it matters: the schema slice feeds the stable prompt prefix. If the slice omits a label the graph actually has, a generated query against that label fails validation for no good reason. If it includes one the spec did not intend, the prefix disagrees with the locked spec.

Disposition: T-2.1-02 uses all 11 from the reference doc, since that is what the live graph contains and a generator that cannot name `NamedThing` cannot query it. The spec wording is a Step 6.2 reconciliation item, since both documents are locked until then.

History:
- 2026-07-29 lead: filed during phase open, after the live schema was verified

---

### F-2.1-02: Section 6.1's parameter-passing mechanism is not implementable

Status: filed
Raised by: lead
Severity: high
Ticket: T-2.1-06 (fixed, awaiting judge confirmation)

What happened: Section 6.1 states "Query parameters pass through the SQL `%s` placeholder as a JSON object, never string-interpolated into the Cypher text". `docs/ncbi/Tool_implementation_mechanics.md` repeats it. That mechanism cannot work. psycopg2 interpolates `%s` client-side before the statement reaches the server, so AGE never receives a genuine bind parameter and rejects the call.

Probed against the live graph, all four forms:

- `%s` plain: sqlstate 22023, "third argument of cypher function must be a parameter"
- `%s::agtype`: same failure
- Empty params object: same failure, so an empty dict must omit the third argument entirely rather than pass `{}`
- `PREPARE name(agtype) AS SELECT * FROM cypher(...,$1) AS (...)` then `EXECUTE name(%s)`: works, returned 15,310 rows for the BRCA1 variant query

Injection resistance of the working form was verified separately, not assumed: passing `NCBIGene:672'}) RETURN v UNION MATCH (x:Gene) RETURN x //` as the parameter value returned 0 rows, with the value treated as an opaque literal.

Why it matters beyond this tool: the same claim appears in the tech spec, the tool mechanics doc, and `.claude/rules/production-examples.md` example 1, whose "correct" code sample uses the non-working form. Every one of the six remaining tools will be written against that sample. This is a documentation defect that propagates.

Disposition: fixed in `graph_connection.py` (commit `6c49f3f`) using PREPARE/EXECUTE with a uuid4-suffixed statement name and a DEALLOCATE in a finally block. The spec and rule wording are a Step 6.2 reconciliation item, since the tech spec is locked until then. The lead raised this and must not also close it; the judge confirms.

History:
- 2026-07-29 lead: filed after probing four forms against the live graph
- 2026-07-29 fix agent: implemented PREPARE/EXECUTE, live integration test passes

---

### F-2.1-03: MeSH CURIEs silently lost their citation

Status: filed
Raised by: lead
Severity: high
Ticket: T-2.1-05 (fixed, awaiting judge confirmation)

What happened: `source_url_for_curie()` returned `None` for GO, MeSH, HP, and MONDO, on the stated reasoning that none is NCBI-hosted. That holds for GO (geneontology.org), HP (hpo.jax.org), and MONDO (Monarch Initiative). It is wrong for MeSH, which is NCBI database `mesh` with 355,735 records (`docs/ncbi/NCBI_databases_and_APIs_reference.md` line 65).

Why it matters: `has_mesh_annotation` is the largest edge class in the graph at 349,158,184 edges, and `OntologyClass` nodes carry `MeSH:` CURIEs. Every MeSH-derived fact would have been emitted with no citation, against CLAUDE.md's "every fact in a response must link back to its source". An uncited fact is not a formatting nit here, it is the trust moat failing open.

Note on the builder's reasoning: the rule it applied, never fabricate a URL for a prefix with no NCBI record page, is correct and was applied correctly to the other three. It flagged the call for review rather than guessing. The defect is a misclassification of one database, not a bad principle.

Disposition: fixed (commit `c79be23`), MeSH now maps to `https://www.ncbi.nlm.nih.gov/mesh/?term=<local_id>` with the local id URL-encoded. All six mapped prefixes curl-verified at HTTP 200. GO, HP, MONDO still return `None`, unchanged. The lead raised this and must not also close it; the judge confirms.

History:
- 2026-07-29 lead: filed after checking MeSH against the NCBI database reference
- 2026-07-29 fix agent: mapped MeSH, re-verified the other five mappings as correct

---

### F-2.1-04: The live integration test runs only as a side effect of importing litellm

Status: filed
Raised by: lead
Severity: medium
Ticket: none yet

What happened: `litellm/__init__.py:27` calls `load_dotenv()` at import time. Nothing in this repo calls it. So `.env` reaches `os.environ` only when some test imports the app, which imports the harness, which imports litellm. The live graph test's guard reads `GRAPH_PG_HOST` from the environment, so:

- Full suite: litellm gets imported, `.env` loads, the test runs. Verified: `697 passed`, zero skips.
- `pytest tests/system_03_search_agent/tools/`: litellm never imported, `GRAPH_PG_HOST` is unset, the test skips with the reason "None:5432 is not reachable" even when a tunnel is open.

Why it matters: someone scoping a run to the tools directory gets a silent skip and believes live coverage ran. The reachability guard added in `6c49f3f` makes the failure mode safe (skip, not a false pass), so this is a coverage illusion rather than a correctness bug. It also means an unrelated dependency's import side effect silently decides whether this project's live test executes.

Disposition: not fixed. The test should load `.env` explicitly if it intends to run against live infrastructure, rather than inheriting it. Needs an owner and a phase.

History:
- 2026-07-29 lead: filed after the test skipped in isolation but passed in the full suite

---

### F-2.1-05: target_entities binds to generated Cypher parameters positionally

Status: filed
Raised by: builder-d, self-reported
Severity: medium, pending judge and adversary assessment
Ticket: T-2.1-07

What happened: `cypher_query.py` binds the caller's `target_entities` list to the generated Cypher's `$param_name` placeholders by position, because no naming contract exists between the generation step and the binding step. The generator is free to name parameters however it likes; the binder assumes an order.

Why it matters: the plausible failure is not a crash. If the generator emits parameters in a different order than `target_entities`, or a different count, the tool can bind the wrong entity to the wrong slot and return rows that are real, well-formed, cited, and about the wrong thing. A confidently wrong biomedical answer is the worst output this system can produce, and it is exactly the class a passing test suite does not catch.

Disposition: raised by the builder itself rather than hidden, which is the right behavior. Under active judge and adversary review; the adversary was tasked to attack this specific binding directly. Not closed by the raiser.

History:
- 2026-07-29 builder-d: self-reported as a known limitation while implementing T-2.1-07
- 2026-07-29 lead: recorded as a tracked finding and routed to the judge and adversary

---

### F-2.1-06: execute_cypher blocks the event loop, so its 30 second bound cannot fire

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: high
Ticket: none yet

What happened: `graph_connection.execute_cypher` is a plain `def`, not `async def` (`graph_connection.py:336`), and `cypher_query` calls it with no `await`, no `asyncio.to_thread`, and no executor from inside the coroutine `_run_pipeline` (`cypher_query.py:587`, and again at `:385` for the count query).

A synchronous call inside a coroutine cannot be cancelled by `asyncio.wait_for`, so both the tool's own 30 second bound (`cypher_query.py:682`) and Act's `enforce_timeout` (`graph.py:784-788`) are dead code for the duration of every graph query. The judge measured it: a `wait_for` with a 0.5 second timeout around a 4 second blocking call returned normally after 4.01 seconds, with the event loop ticking once where a healthy loop ticks roughly 40 times.

Failure scenario: two users query concurrently. User A's Cypher runs 25 seconds server-side. User B's SSE stream, every other in-flight run, and every FastAPI health check are frozen for those 25 seconds, because the single event loop ticked once. The only real bound left is the server-side `statement_timeout`.

Why nothing caught it: the phase's 9 live end-to-end tests run sequentially, so none of them has a second concurrent request to starve. No ticket's acceptance criteria asked whether the tool was actually async. This is the ticket-boundary shape of LEARNINGS rows 28, 30, and 33 again, in a fourth form.

Rules: `tool-call-budgets.md` ("never ship a tool with no per-call timeout", which it nominally has and cannot execute) and `system-design-patterns` pattern 6 (time to first token under one second).

History:
- 2026-07-31 judge: filed with a reproduction, confirmed by the lead reading the two signatures

---

### F-2.1-07: Entity extraction resolves one gene symbol, and the phase gate is satisfiable by that table

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: high
Ticket: none yet

What happened: `_KNOWN_GENE_SYMBOL_CURIES` holds exactly one entry, `{"BRCA1": "NCBIGene:672"}` (`core/graph.py:585-587`), and the phase's own end-to-end gate queries BRCA1.

The judge measured the real reach: of five realistic gene-symbol queries (TP53, BRCA2, EGFR, KRAS, MECP2), zero resolve. All return `target_entities=[]`, which produces `status="error"` with `UndefinedParameter` and a refusal. Against roughly 20,000 protein-coding gene symbols in the graph plus every disease and phenotype term, this resolves well under 0.01 percent of realistic biomedical queries.

On the mitigation already in place: `test_full_loop_works_for_a_gene_outside_the_symbol_seed_table` queries `"What is NCBIGene:7157?"`. The judge's assessment is that this is not cosmetic, since it genuinely exercises `_CURIE_IN_TEXT_PATTERN`, a distinct code path from the seed table, but it is not sufficient either, because a user typing a raw NCBI gene id is not the query class this system exists to serve. The lead's docstring on that test claiming "only the general path can satisfy it" overstates what it proves.

It fails safe, refusing rather than answering wrongly, which is the right direction. It still means the phase premise is satisfied by a hand-listed entity set.

Disposition: needs an explicit product-owner decision. Either accept it as a documented dependency that build phase 2.2 or a later entity-resolution phase closes, or fix it now. Real symbol-to-CURIE resolution is arguably a different capability from this phase's Section 25 row.

History:
- 2026-07-31 judge: filed with a five-query measurement

---

### F-2.1-08: The loop-level empty-to-refuse branch is unproven

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: medium
Ticket: none yet

What happened: `test_full_loop_refuses_when_the_graph_returns_nothing` queries `"What is known about the gene ZZZFAKE9?"`. `ZZZFAKE9` is neither a CURIE nor a seed-table entry, so `target_entities` is empty and the tool returns `status="error"` on an unbound parameter, never `status="empty"`. Both paths produce `trust_outcome="refuse"`, so the assertion passes and cannot distinguish them.

The empty-to-refuse half of the loop-level cite-or-refuse gate is therefore untested end to end. The tool-level half is genuinely proven by `test_absent_entity_returns_empty_never_a_fabricated_row`.

The lead wrote this test believing it proved the empty path.

Fix: name a real-shaped CURIE that is absent from the graph, for example `"What is NCBIGene:99999999?"`, so the tool actually returns `empty`.

History:
- 2026-07-31 judge: filed with a probe showing `status='error'` rather than `'empty'`

---

### F-2.1-09: Worst-case tool wall time roughly doubles the locked 30 second budget

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: medium
Ticket: none yet

What happened: `remaining_budget` is computed once (`cypher_query.py:577`) and passed unchanged both to the main `execute_cypher` (`:591`) and to `_fetch_true_total` (`:618`), so each gets its own full server-side `statement_timeout`.

Failure scenario: two generation calls take 8 seconds, leaving `remaining_budget` at 22 seconds. The main query takes 21 seconds and returns exactly `row_limit` rows, triggering the count query, which carries no LIMIT and runs with `enable_seqscan=off` over a 693M-edge graph, and gets a fresh 22 seconds. Total roughly 51 seconds against Section 6.1's locked 30 second per-call budget. Compounded by F-2.1-06, nothing in Python can interrupt it.

History:
- 2026-07-31 judge: filed

---

### F-2.1-10: Finding.truncated has no readers

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: medium
Ticket: none yet

What happened: the F-03 fix added a `truncated` field to `Finding` specifically so truncation "is never silent" (`coordinator_worker.py:118-128,295`). Nothing in `core/` or `adapters/` reads it. The only `.truncated` hit elsewhere is `graph.py:742`, which reads `CypherQueryOutput.truncated`, a different field on a different object.

So a `Finding` silently cut to fit the 50,000 byte ceiling reaches `write_node` indistinguishable from a complete one. A field added to close an invisible-truncation finding, that nothing reads, has not closed it. This is the LEARNINGS row 28 shape (a module with no callers) in miniature.

History:
- 2026-07-31 judge: filed

---

### F-2.1-11: The byte ceiling can silently turn a successful query into a refusal

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: medium
Ticket: none yet

What happened: `_cap_structured_fields` binary-searches `list_item_limit` down to as low as zero (`coordinator_worker.py:532-547`) when the payload exceeds `_MAX_FINDING_TOTAL_BYTES`. A 100-row multi-hop result with rich property maps can have `rows` trimmed or emptied while `status` stays `"ok"`, so `_citations_from_findings` yields fewer or zero citations and `write_node` emits `refuse` for a query that actually succeeded.

It fails in the safe direction, but silently, and F-2.1-10 means the caller cannot detect it.

History:
- 2026-07-31 judge: filed

---

### F-2.1-12: Write's synth call is pure waste

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: medium
Ticket: none yet

What happened: `write_node` sends `[{"role": "user", "content": query.text}]` (`graph.py:1019`), never reads the return value, and emits no `token` event on the success path. The findings never reach it.

Synth is the most expensive tier and was measured at 17,527 to 21,572 ms. Every query therefore pays roughly 20 seconds of latency and the full synth spend for output nobody reads. It is the single largest contributor to end-to-end latency.

Defensible as a phase 2.2 placeholder, since real synthesis is exactly what 2.2 builds. Filed because it is not documented as a known cost anywhere, and because the same shape (a discarded response) is what made F-2.1's guardrail and think steps generate 1000 tokens each until it was measured.

History:
- 2026-07-31 judge: filed

---

### F-2.1-13: _build_count_cypher mishandles UNION and skips validation

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: low
Ticket: none yet

What happened: `cypher_query.py:350-356` takes everything before the first `RETURN` and appends `RETURN count(*) AS total_count`. On a UNION query, which the validator explicitly supports (`cypher_validator.py:467-525`), every branch after the first is discarded, so `total_available` reports the first branch's count as the whole result's total, presented as authoritative.

The count query is also never passed back through `validate_cypher` and carries no LIMIT, so the validator's own "a query with no LIMIT gets one injected before execution" contract does not hold for it.

History:
- 2026-07-31 judge: filed

---

### F-2.1-14: claim_text carries raw graph text into a citation without the untrusted-reader gate

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: low today, becomes live in build phase 2.2
Ticket: none yet

What happened: `_pick_representative_field` (`graph.py:881-895`) selects `fields["name"]` or the first key in insertion order, and `_citation_for_row` interpolates it into `claim_text` (`:931-934`). Cypher rows are routed `contains_untrusted_free_text=False` by construction (`graph.py:806`), so arbitrary free-text property values reach the client as citation text with no reader mediation.

Harmless today only because `write_node` never feeds findings into a model prompt. It becomes a live prompt-injection surface the moment build phase 2.2 wires findings into the synth call, which is precisely what 2.2 is for.

History:
- 2026-07-31 judge: filed as forward-looking

---

### F-2.1-15: Stale comments and a dead public function

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: low
Ticket: none yet

What happened: `coordinator_worker.py:193` states the reader timeout "matches `budget_for_query_class("single_hop")` (10 seconds)"; that value is now 20.0, so the stated invariant is false. `graph.py:135,141,776` still narrate the `max(budget_for_query_class(...), ...)` design that `budget_for_step` replaced. `budget_for_query_class` itself (`harness.py:412`) now has no production caller, only stale comments and tests.

History:
- 2026-07-31 judge: filed

---

### F-2.1-16: The spec-versus-code budget divergence was not filed in this phase file

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: low
Ticket: none yet

What happened: the `budget_for_step` change diverges from `Technical_specification.md` Section 19.1's per-query-class shape. It is recorded in `DECISIONS.md` with product-owner approval and named as a Step 6.2 item there, but unlike F-2.1-01 and F-2.1-02 it was never filed in this phase file's Findings section, so a reader of the phase file alone would not see it.

Filed here now, which closes it.

History:
- 2026-07-31 judge: filed
- 2026-07-31 lead: recorded here, which is the fix

---

### F-2.1-17: The lead cited the wrong rule for the stub-step scope check

Status: confirmed
Raised by: judge (second pass, 2026-07-31)
Severity: low, process
Ticket: none

What happened: the lead justified the guardrail and think stub instruction as not crossing `.claude/rules/v1-scope-boundary.md`. That rule governs the PRD out-of-scope list and the Section 25 fast-follow table. Build phase 3.0 is inside the locked build order, so it appears on neither list, and doing 3.0's work early is a build-order concern rather than a v1-scope crossing.

The conclusion held, and the judge independently verified it: both payloads are hardcoded and both model responses are discarded, so nothing in the emitted payload depends on the model. The justification was a category error.

Worth keeping because a rule cited wrongly and reached the right answer is a habit that will eventually reach the wrong one.

History:
- 2026-07-31 judge: filed

---

## Phase notes

Learnings that bind here, read before building:

- Row 28 (build phase 2.0): `build_stable_prefix()` passed every acceptance criterion with zero callers. T-2.1-08 carries an explicit criterion that the prefix still reaches every model call.
- Row 30 (build phase 1.2): six components passed their own criteria while nothing assembled them, because no ticket owned the wiring. T-2.1-07 and T-2.1-08 are that ticket here, named up front.
- Row 25 (build phase 1.1): a worktree builder's green test run proves nothing about the checkout it merges into. The lead re-runs the full suite in the main checkout after every merge.
- Row 27 (build phase 2.0): a builder set its own ticket to `done`. The lead diffs each worktree's tracker file for a status-field change before merging.
- Row 29 (build phase 2.0): a credential-shaped literal in a Bash heredoc trips the secret-scanning hook. Write scripts to a file and generate secrets at runtime.

Deliverables checklist, from Section 25:

- [ ] `cypher_query` over Layer 1 using the prototype transport
- [ ] Schema slicing
- [ ] Validate-then-execute generation pipeline
- [ ] Edge-label enforcement
- [ ] F-2.0-08 and F-2.0-14 closed
- [ ] A real query reaching the live graph end to end
