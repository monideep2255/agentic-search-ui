# Phase 2.1: cypher_query over Layer 1

Build phase 2.1 delivers `cypher_query`, the only path to Layer 1: a three-step internal pipeline (receive structured intent, generate Cypher against a sliced schema with a plan-tier call, validate then execute), plus edge-label enforcement and the Act-step wiring that makes F-2.0-08 and F-2.0-14 live.

Depends on: phase 2.0 (done, merged as PR #9)
Branch: `phase/2.1-cypher-tool`
Spec: `requirements/Technical_specification.md` Section 6.1, Section 9 (provenance), Section 19 (cost control)
Reference: `docs/ncbi/Tool_implementation_mechanics.md`, `docs/data-engineering/Knowledge_graph_on_server_reference.md`

## Phase premise (the done-when)

A real query reaches the live AGE graph through `cypher_query` and returns cited rows, with the main agent never generating or seeing raw Cypher. A phase where every ticket passes but no query reaches the graph is a failed phase, not a passed one (LEARNINGS rows 28 and 30).

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
- `src/system_03_search_agent/tools/graph_connection.py`: `GraphError`/`GraphConnectionError`/`GraphTimeoutError`/`GraphAuthError` at lines 93 to 109; `execute_cypher()` signature at line 236 matches the required interface exactly, plus an optional `as_clause` kwarg; `_wrap_cypher()` at line 202 builds the SQL wrapper via plain string concatenation (no f-string, no `.format()`), rejects a literal `$$` inside the Cypher body, and validates `as_clause` shape; `_SEARCH_PATH_SQL` at line 68 sets `search_path` only, no `LOAD 'age'` anywhere in the module; `_classify_connect_error()` at line 124 and the `except psycopg2.errors.QueryCanceled` / `except psycopg2.OperationalError` chain at lines 314 to 330 give connection-refused, auth-failure, and timeout each a distinct `GraphError` subclass with an actionable message; `_redact()` at line 112 strips a credential value out of any message before it is raised, applied to both the default and any injected `connection_factory`; truncation and `total_available` computed at lines 334 to 339.
- Test run: `"/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/venv/bin/python" -m pytest tests/system_03_search_agent/tools/ -q` from the worktree root → `...............s` then `15 passed, 1 skipped in 0.04s`. The 1 skip is `test_live_graph_returns_brca1_via_labelled_edge`, marked `@pytest.mark.integration`, skipped with reason "GRAPH_PG_HOST is not set; no SSH tunnel to the graph host is available in this environment" (`tests/system_03_search_agent/tools/test_graph_connection.py` line ~319), exactly the designed behavior for a worktree with no `.env`.
- Credential-redaction tests: `test_no_credential_value_appears_in_connection_error_message` and `test_no_credential_value_appears_in_any_raised_exception_across_all_paths` (`tests/system_03_search_agent/tools/test_graph_connection.py`) both set a sentinel password value, force a `psycopg2.OperationalError` whose message contains that sentinel, and assert the sentinel string is absent from the raised `GraphError`'s message. Both pass.
- `ruff check src/system_03_search_agent/tools/graph_connection.py tests/system_03_search_agent/tools/test_graph_connection.py` → `All checks passed!` (one intentional `BLE001` blind-exception catch carries a `# noqa` with an inline justification, since it is the deliberate last-resort classification path for a non-default `connection_factory`).
- Did not create `tests/system_03_search_agent/tools/__init__.py` per the lead's coordination note; ran pytest against the test directory directly, which collected and ran without it.

History:
- 2026-07-29 lead: created, scoped from Section 6.1
- 2026-07-29 builder-c: implemented `graph_connection.py` (execute_cypher, GraphError hierarchy, connect/auth/timeout classification, credential redaction, row truncation) and `test_graph_connection.py` (16 tests, 15 pass + 1 clean skip); fast-forwarded this worktree's branch onto `phase/2.1-cypher-tool` first since the worktree had opened before the phase-open commits landed; set status to in-review

---

### T-2.1-07: cypher_query three-step pipeline

Status: todo
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
- (filled at close)

History:
- 2026-07-29 lead: created, scoped from Section 6.1

---

### T-2.1-08: Act-step wiring, cost cap and output caps

Status: todo
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
- (filled at close)

History:
- 2026-07-29 lead: created, scoped from F-2.0-08 and F-2.0-14

---

### T-2.1-09: End-to-end verification against the live graph

Status: todo
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
