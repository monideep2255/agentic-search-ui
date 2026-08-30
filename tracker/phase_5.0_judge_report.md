# Build phase 5.0 judge report

Graded at commit `c8a8e7d` on branch `phase/5.0-observability`, 2026-08-29, from fresh context with no prior involvement in the phase.

Write target: this file only. `tracker/phase_5.0.md` is the adversary's target and is not touched here.

Status: COMPLETE. Sections were appended as each result was established, per the write-first rule in `.claude/rules/self-eval-loop.md`. Verdict at the end of this file.

## Table of contents

- [Scope of the change](#scope-of-the-change)
- [G1 the central design claim](#g1-the-central-design-claim)
- [G2 Section 20.3 field compliance](#g2-section-203-field-compliance)
- [G3 the PII boundary](#g3-the-pii-boundary-section-201)
- [G4 mutation testing every gate](#g4-mutation-testing-every-gate)
- [G5 the round-4 fixes](#g5-the-round-4-fixes)
- [G6 production and AI security gates](#g6-production-and-ai-security-gates)
- [G7 scope](#g7-scope)
- [Premise: does the ticket set satisfy the done-when](#premise-does-the-ticket-set-satisfy-the-done-when)
- [Verify commands](#verify-commands)
- [Findings](#findings)
- [Verdict](#verdict)

## Scope of the change

`git diff --stat develop...HEAD` at `c8a8e7d`:

```
 .gitignore                                         |    9 +
 env.example                                        |   44 +-
 requirements/phase_6/Continuation_prompt.md        |   10 +-
 src/system_03_search_agent/adapters/web_sse/app.py |   24 +
 src/system_03_search_agent/core/run.py             |  276 +++-
 .../observability/__init__.py                      |   35 +
 .../observability/analytics.py                     |  405 +++++
 src/system_03_search_agent/observability/audit.py  |  777 ++++++++++
 src/system_03_search_agent/observability/config.py |  227 +++
 .../observability/tracing.py                       |  409 +++++
 .../tools/graph_connection.py                      |  130 +-
 src/system_03_search_agent/tools/ncbi_transport.py |  155 +-
 .../tools/pathogen_ftp_transport.py                |  146 +-
 tests/conftest.py                                  |   38 +
 .../observability/__init__.py                      |    1 +
 .../observability/test_analytics.py                |  398 +++++
 .../observability/test_audit.py                    | 1586 ++++++++++++++++++++
 .../observability/test_config.py                   |  195 +++
 .../observability/test_hermetic_guard.py           |   88 ++
 .../observability/test_observability_mutation.py   |  975 ++++++++++++
 .../observability/test_observability_premise.py    |  693 +++++++++
 .../observability/test_tracing.py                  |  439 ++++++
 .../observability/test_wiring.py                   |  660 ++++++++
 tracker/BOARD.md                                   |    9 +-
 tracker/board.html                                 |   16 +-
 tracker/phase_5.0.md                               |  392 +++++
 26 files changed, 8001 insertions(+), 136 deletions(-)
```

Observability directory suite, run first thing:

```
$ PYTHONPATH=src python -m pytest tests/system_03_search_agent/observability/ -q
164 passed, 1 skipped in 3.13s
```

Note this is 164 passed, not the `101 passed, 1 skipped` the phase document records at the pause. The phase document's figure predates the round-3 and round-4 additions and is stale rather than wrong.

## G1 the central design claim

The claim under grade, from `tracker/phase_5.0.md`'s finding one: an `act_node` audit hook structurally misses five production call sites, so the hook belongs at three transport chokepoints instead.

### The five bypass sites still bypass `act_node`, verified

All five exist at the claimed line numbers on this commit.

```
$ grep -n "await ncbi_efetch(" src/system_03_search_agent/core/graph.py
2038:    dataset_output = await ncbi_efetch(
2098:    search_output = await ncbi_efetch(
2139:    summary_output = await ncbi_efetch(

$ grep -n "execute_cypher(" src/system_03_search_agent/export/traversal.py
558:        rows, _ = execute_cypher(
801:            rows, _ = execute_cypher(
```

All three `graph.py` sites are inside `_resolve_symbol_to_curie_uncached` (`src/system_03_search_agent/core/graph.py:2019`), reached from `think_node`, not from `act_node`. Both `traversal.py` sites call `graph_connection.execute_cypher` directly, imported at `src/system_03_search_agent/export/traversal.py:109`, bypassing the `cypher_query` tool wrapper as well as `act_node`. PASS.

### The three chokepoints carry the hook, verified

```
$ grep -rn "record_tool_call(" src/ | grep -v observability/audit.py
src/system_03_search_agent/tools/ncbi_transport.py:1311:        record_tool_call(
src/system_03_search_agent/tools/ncbi_transport.py:1335:    record_tool_call(
src/system_03_search_agent/tools/graph_connection.py:718:        record_tool_call(
src/system_03_search_agent/tools/graph_connection.py:737:    record_tool_call(
src/system_03_search_agent/tools/pathogen_ftp_transport.py:128:        record_tool_call(
src/system_03_search_agent/tools/pathogen_ftp_transport.py:138:    record_tool_call(
src/system_03_search_agent/tools/pathogen_ftp_transport.py:324:    record_tool_call(
src/system_03_search_agent/tools/pathogen_ftp_transport.py:336:    record_tool_call(
```

Each chokepoint has a matched pair, one on the exception path and one on the success path, so a failed call is audited as well as a successful one. `ncbi_transport.execute_get` brackets only the awaited request (`ncbi_transport.py:1286` `audit_started = time_fn()`, immediately before the try), not the URL assembly above it. `graph_connection.execute_cypher` does the same at `graph_connection.py:707`. PASS.

### The premise gate drives the REAL bypass callers, not the shared function

This was the specific thing to check, because `test_wiring.py`'s own coverage statement admits its `TestBypassArms` calls `execute_cypher` and `execute_get` directly rather than through the real callers.

`tests/system_03_search_agent/observability/test_observability_premise.py:255-355`, class `TestRealBypassCallersAreAudited`, closes that gap for real:

- `test_think_node_symbol_resolution_is_audited_by_its_real_caller` (line 256) calls `graph_module._resolve_symbol_to_curie_uncached("BRCA1", "human")` unmodified, faking only `httpx.AsyncClient.get`. It carries three genuine populate-checks: `assert not log_path.exists()` before the call (line 268), `assert curie == "NCBIGene:672"` (line 302) so a broken dispatch cannot pass by writing some other line, and an exact-endpoint assertion at line 313 pinning `api.ncbi.nlm.nih.gov/datasets/v2/gene/symbol/BRCA1/taxon/human`.
- `test_kgx_export_traversal_is_audited_by_its_real_caller` (line 318) calls `traversal.traverse_subgraph(["MONDO:0007254"], hops=0, ...)`, the real `s3-kgx-export` entry point, and asserts `result.seeds_resolved == []` (line 340) as the populate-check that the seed-lookup loop genuinely ran.

PASS on the specific check asked for. The design's central claim is tested at the real callers, not only at the shared function underneath.

### Where G1 is short of its own goal contract

The goal contract's verify surface says: "One arm per bypass call site, asserting a line is written." There are five bypass call sites and two real-caller arms.

- `core/graph.py:2098` (ESearch fallback leg) and `:2139` (ESummary leg) are never driven. The one arm that reaches that function asserts `len(entries) == 1` with the comment "the ESearch fallback is never reached" (`test_observability_premise.py:305-310`), so those two legs are covered by construction (identical `execute_get`) rather than by an arm.
- `export/traversal.py:801` (hop expansion) is never driven; `hops=0` is chosen deliberately and the arm's own docstring says so (line 327).

This is DISCLOSED rather than hidden, in the arms' own docstrings, and the by-construction argument is sound because there is exactly one `execute_get` and one `execute_cypher` to reach. I record it as a shortfall against the contract's literal wording rather than as a defect: filed below as J-04, minor.

## G2 Section 20.3 field compliance

Graded against Section 20.3's own text at `requirements/Technical_specification.md:2874`, not against what the code emits.

Section 20.3's field list, from the second bullet plus the `authorization` requirement in the first:

| Section 20.3 field | Key on the line | Producer in `src/`? |
|---|---|---|
| `trace_id` | `trace_id` | yes, ContextVar via `current_trace_id()` |
| tool name | `tool` | yes |
| endpoint or database called | `endpoint` | yes |
| redacted params | `params` | yes, through `redact_params` + `_bounded` |
| returned record ids | `record_ids` | NO PRODUCER. Always `[]` |
| HTTP status | `http_status` | yes at `ncbi_transport`; structurally None at the graph and FTP chokepoints, which is correct |
| body-level error and empty signal for E-utilities | `error_code` members `http_error`, `empty` | NO PRODUCER (already filed F-5.0-23) |
| latency in milliseconds | `latency_ms` | yes |
| timestamp | `timestamp` | yes |
| authorization (first bullet) | `authorization` | yes, by identifier |

Every field is PRESENT. Two of the ten have no producer.

### `record_ids` has no producer anywhere, and nothing says so

This is a NEW finding, not covered by F-5.0-23. Established by driving the real chokepoint rather than by reading:

```
$ grep -rn "record_ids" src/
src/system_03_search_agent/tools/pathogen_ftp_transport.py:343:        record_ids=None,
src/system_03_search_agent/observability/audit.py:661:    record_ids: Sequence[Any] | None = None,
src/system_03_search_agent/observability/audit.py:689:        record_ids: identifiers the call returned, ...
src/system_03_search_agent/observability/audit.py:754:            "record_ids": list(record_ids) if record_ids is not None else [],
```

The only call site that mentions it passes `None` explicitly. Neither `ncbi_transport.py:1311/1335` nor `graph_connection.py:718/737` passes it at all, so it defaults to `None` and serializes as `[]`.

Driven through the real `execute_get` chokepoint with a response body that DOES carry record ids (`idlist: ["672","675"]`), the written line is:

```
{
  "authorization": "none",
  "endpoint": "eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
  "error_class": null,
  "error_code": null,
  "http_status": 200,
  "latency_ms": 0.025540997739881277,
  "layer": 2,
  "params": {"db": "gene", "term": "BRCA1"},
  "record_ids": [],
  "timestamp": "2026-08-30T00:32:10.355763+00:00",
  "tool": "ncbi_transport:eutils",
  "trace_id": "judge-g2"
}
```

The ids were in the response and are not on the line. This is structural, not a missed branch, and it is the exact mirror of F-5.0-23: the transport holds the raw `httpx.Response` but never parses it, and the parsing that extracts record ids happens in the action modules above, none of which calls `record_tool_call`.

What makes this a finding rather than a known gap:

- `tests/system_03_search_agent/observability/test_audit.py:215` passes `record_ids=["gene:7157"]` and `:244` asserts it round-trips. That is a direct `record_tool_call` invocation. It gives a reader the impression the field works while no production path ever populates it, which is this repository's recorded safety-by-proxy shape.
- The premise gate's Section 20.3 arm asserts PRESENCE only (`test_observability_premise.py:505-507`), and its own long coverage statement names `http_error` and `empty` as declared-and-unexercised while saying nothing about `record_ids`. A coverage statement that names one unproduced field and omits another of the same class reads as complete when it is not, which is build phase 4.15's recorded failure mode.
- `tracker/phase_5.0.md` never mentions `record_ids` outside F-5.0-01's incidental prose. Neither does the phase's Coverage section.

Filed below as J-01, major.

### The design's own premise argument is overstated

`tracker/phase_5.0.md`'s finding two is titled "the transport is the only place Section 20.3's required fields actually exist". Measured against the ten fields above, that holds for `http_status` and `latency_ms` and is FALSE for `record_ids` and for the E-utilities body-level signal, both of which exist only ABOVE the transport, in exactly the action modules the argument dismisses.

The chokepoint design is still the right call, for the reason G1 establishes: it is the only placement that covers the five bypasses. But it is a TRADE, not a strict improvement, and the phase document presents it as a strict improvement. Filed below as J-02, minor, against the record rather than the code.

## G3 the PII boundary, Section 20.1

Section 20.1 (`requirements/Technical_specification.md:2864`): "only the `trace_id` and the query and tool-result content go to LangSmith ... User-account PII from the auth service (email, session token) never leaves the auth service boundary and is never attached to a trace."

Note on evidence formatting in this section: every stand-in credential below was generated at runtime with `uuid.uuid4().hex`. Where a pasted line would otherwise carry the literal, it is shown as `STANDIN`; the equality and containment results printed alongside are verbatim and are what carries the proof.

### The redaction holds, measured

The two models and their allowlists:

```
Query fields:          ['audience_depth', 'owner_id', 'session_id', 'text', 'trace_id', 'user_id']
RequestContext fields: ['operator_mode', 'session_memory', 'surface']
_QUERY_SAFE_FIELDS           = {"text", "trace_id", "audience_depth"}   tracing.py:120
_REQUEST_CONTEXT_SAFE_FIELDS = {"surface", "operator_mode"}             tracing.py:121
```

Driven through `redact_payload` with a realistic `GraphState`-shaped payload carrying generated stand-in identities:

```
--- PII LEAK CHECK (each must be False) ---
owner_id         present in trace payload: False
user_id          present in trace payload: False
session_id       present in trace payload: False
session_memory   present in trace payload: False
```

PASS. The structural default-deny is genuine: `_QUERY_FIELDS` is read from `Query.model_fields` at import (`tracing.py:108`), so a field added to either model in a later phase is redacted by default rather than leaked by default.

### It does NOT over-redact. Replay value survives intact

This was the specific risk to check, since a trace stripped of everything is worthless to build phase 5.1's graders. Section 20.4 names what they need: "extract the tool_result set and the final answer's citations". Same run, same payload:

```
--- REPLAY VALUE CHECK (each must be True) ---
question text kept                 True
trace_id kept                      True
final answer token text kept       True
citation source_url kept           True
citation id kept                   True
tool name kept                     True
tool result count kept             True
raw layer2 record kept             True
resolved curie kept                True

redacted marker count: 4
```

Exactly four values were replaced, and they are exactly the four Section 20.1 forbids. Nothing a grader needs was touched. PASS, and the marker count is a real populate-check: it separates "redaction fired" from "those fields were never there to begin with".

I also checked the two structural over-redaction routes that could have gutted a trace, and neither fires:

- `GraphState`'s own keys are `['cap_exceeded', 'context', 'daily_cap_declined', 'events', 'findings', 'findings_count', 'guard_refused', 'harness', 'layer2_raw_outputs', 'query', 'query_class', 'resolved_entities', 'seq', 'start_monotonic', 'step_error', 'tool_calls', 'unresolved_entity_symbols']`. Intersection with `Query.model_fields` is empty, so the top-level state is never misrecognized as a Query and gutted.
- The richest event payloads (`Event`, `CitationPayload`, `ToolResultPayload`, `ResolvedEntity`, `TokenPayload`) each intersect `Query.model_fields` in at most ONE name, below `_looks_like_model`'s co-occurrence floor of 2 and never a pure subset, so none is misrecognized either.

### The langsmith precedence claim in the docstring is TRUE, verified against the installed source

`build_traced_client`'s docstring (`tracing.py:283-299`) asserts that the anonymizer runs before and instead of `hide_inputs`/`hide_outputs`, and that `_hide_run_metadata` never consults it. Both checked against langsmith 0.10.10 at `venv/lib/python3.11/site-packages/langsmith/client.py`:

```
2724:    def _hide_run_inputs(self, inputs: dict):
2725:        if self._hide_inputs is True:
2726:            return {}
2727:        if self._anonymizer:
2728:            json_inputs = _orjson.loads(_dumps_json(inputs))
2729:            return self._anonymizer(json_inputs)
...
2766:    def _hide_run_metadata(self, metadata: dict) -> dict:
2767:        if self._hide_metadata is True:
2768:            return {}
2769:        if self._hide_metadata is False:
2770:            return metadata
2771:        return self._hide_metadata(metadata)
```

Both halves hold exactly as written, and `build_traced_client` wires `anonymizer=redact_payload, hide_metadata=redact_payload` accordingly (`tracing.py:301-306`). This is a comment asserting a property that a test would be right to pin, and unlike the four confident-sentence failures build phase 4.15 recorded, this one is true.

Both `core/run.py` sites are wired, checked rather than assumed: `traced_graph_run` plus `build_runnable_config` at `core/run.py:569-572` (`run()`) and at `core/run.py:728-732` (`run_streaming()`), which is the entry point real SSE traffic reaches. Wiring only the first would have left production traffic untraced while looking done, and it did not happen.

### The gap: LangSmith's THIRD anonymizer path is the run ERROR string, and `redact_payload` passes it through unchanged

This is a NEW finding and it is the one I would not merge without a decision on.

`langsmith/client.py:2744` defines a third hook that the module docstring, the code, the tests and `tracker/phase_5.0.md` all fail to mention. Its own docstring names the exact threat:

```
2744:    def _hide_run_error(self, error: Any):
2745:        """Apply the configured anonymizer to a run's error string.
2748:        formatted traceback ...) that can capture credentials the user never
2749:        explicitly logged -- e.g. an HTTP client exception whose request-object
2750:        repr includes an ``Authorization`` header. Route it through the same
2751:        anonymizer as inputs/outputs so secrets are scrubbed client-side
2752:        before upload.
...
2759:        if not self._anonymizer or error is None:
2760:            return error
2761:        scrubbed = self._anonymizer({"error": error})
```

Called on the live upload path at `client.py:2318` and `client.py:3684`. So setting `anonymizer=redact_payload` OPTS THIS SYSTEM IN to having `redact_payload` scrub run error strings, and `redact_payload` does not scrub strings at all: `{"error": ...}` matches no `_PII_KEY_CATEGORIES` entry, is not a subset of either model, and intersects neither in two names, so `_allowlist_for` returns None (`tracing.py:214`) and the value is returned untouched at `tracing.py:270`.

Measured, in the exact `{"error": ...}` shape langsmith constructs, with generated stand-in credentials:

```
input : HTTPStatusError: Server error '500' for url 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gene&term=BRCA1&api_key STANDIN'
output: HTTPStatusError: Server error '500' for url 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gene&term=BRCA1&api_key STANDIN'
byte-identical (no redaction happened): True
credential present in output: True

DSN case byte-identical: True
DSN credential present in output: True
```

In the real probe the two pasted lines carry a literal `api_key=` assignment followed by a 32-character generated hex value; `STANDIN` replaces it here only because this repository's own `scan-secrets.sh` hook correctly refuses to let that shape through a shell command, which is the security layer working rather than friction. The DSN case used the shape `OperationalError: connection to postgresql://kg_reader:STANDIN@h/db failed`, the same shape F-5.0-13 measured against the audit sink. The reproduction script is `g3_error.py` in this session's scratchpad and regenerates its own credential on every run.

Why this matters more than its reachability alone: this is the SAME defect class as F-5.0-13, on the other transmission path, and it is defended today by exactly the argument this phase spent three rounds rejecting. `tracker/phase_5.0.md`'s F-5.0-13 row says it in its own words: "Today's psycopg2 path happens to be clean, because `_classify_connect_error` redacts the password when it BUILDS the GraphError, but that is a PROVENANCE argument, not a value check ... `except Exception` is bounded by nothing." The audit sink was closed structurally. The LangSmith path was left on the provenance argument, and nothing in the phase record notes the asymmetry.

Reachability, stated precisely rather than overclaimed:

- Not reachable through `ncbi_transport`'s OWN exceptions, which use `_host_of` deliberately (`ncbi_transport.py:1184`) and therefore carry no query string. This is a real mitigation and I am not discounting it.
- Reachable through any exception this repository does not construct: an httpx, psycopg2 or driver exception whose message carries a URL or DSN, propagating out of a LangGraph node. That is precisely the unbounded set `except Exception` covers, and it is the set the phase already ruled insufficient once.
- Gated behind a real `LANGSMITH_API_KEY`. One is now provisioned per the phase record, so this is live rather than latent.
- No test anywhere exercises it. `grep -n "hide_run_error\|anonymizer" tests/system_03_search_agent/observability/test_tracing.py` returns nothing, and `grep -n "hide_run_error" tracker/phase_5.0.md` returns nothing.

The fix is cheap and already exists in this repository: `observability/audit.py` has `_redact_value_string`, built and hardened across three rounds against exactly this input shape. `redact_payload` does not use it.

Filed below as J-03, major.

Grade for G3: PASS on the account-PII boundary and PASS on replay preservation, which are the two things Section 20.1 and Section 20.4 actually require. FAIL on the credential half of the same transmission path, which Section 20.1 does not name but `production-standards.md`'s secrets gate does.

## G4 mutation testing every gate

The instruction was to break the thing each gate exists to catch and confirm it goes red, and to verify the permanent harness discriminates rather than trusting it. I did NOT re-run the harness and read its result. I applied 23 independent SOURCE-LEVEL text mutations, on disk, ran the observability suite against each, restored the file, and asserted byte-identical restoration by SHA-256 on every one. The driver is `mutate.py`, `mutate2.py` and `mutate3.py` in this session's scratchpad; it refuses to proceed if an anchor is missing and raises if restoration is not exact.

This is a different mechanism from the permanent harness, which is monkeypatch-based by design (its own docstring explains why). Two mechanisms agreeing is the point.

### Result: 20 of 23 mutations turn the gate RED

| # | Mutation applied to source | Result | Arm that caught it |
|---|---|---|---|
| M1b | `execute_get` success-path audit hook deleted | RED | `test_observability_mutation.py::test_endpoint_for_audit_reverted_to_raw_url_turns_the_wiring_arm_red` |
| M2 | `execute_cypher` success-path audit hook deleted | RED | `test_observability_premise.py::TestRealBypassCallersAreAudited::test_kgx_export_traversal_is_audited_by_its_real_caller` |
| M3 | `classify_error_code` fails OPEN, returns the caller's value | RED | `test_audit.py::TestErrorFieldIsStructurallyBounded::test_oversized_text_cannot_reach_the_error_fields_at_all` |
| M4 | round-4 fix reverted: `type(value) is str` to `isinstance` in `classify_error_code` | RED | `test_audit.py::TestGuardsRefuseAHostileStrSubclass::test_a_subclass_overriding_eq_cannot_write_itself_into_error_code` |
| M5 | round-4 fix reverted: `type(value) is str` to `isinstance` in `_safe_error_class` | RED | `test_audit.py::TestGuardsRefuseAHostileStrSubclass::test_a_subclass_lying_about_both_bounds_cannot_reach_error_class` |
| M6 | `_QUERY_SAFE_FIELDS` widened to every `Query` field | RED | `test_tracing.py::test_redact_payload_denies_every_query_field_not_on_the_safe_allowlist` |
| M7 | `anonymizer=redact_payload` DELETED from `build_traced_client` | GREEN | nothing. `164 passed, 1 skipped` |
| M8 | `hide_metadata=redact_payload` DELETED from `build_traced_client` | GREEN | nothing. `164 passed, 1 skipped` |
| M9 | pathogen FTP `stream_filtered_tsv_rows` success hook deleted | RED | `test_wiring.py::TestPathogenChokepoint::test_stream_filtered_tsv_rows_writes_one_audit_line` |
| M10 | pathogen FTP `_get_directory_listing` success hook deleted | GREEN | nothing. `164 passed, 1 skipped` |
| M11 | `redact_params` dropped from the `params` field | RED | `test_audit.py::TestRedaction::test_secret_value_never_appears_anywhere_in_written_line` |
| M12 | `_bounded` size cap dropped from `params` | RED | `test_audit.py::TestRedaction::test_oversized_params_are_disclosed_not_silently_truncated` |
| M13 | category (`_is_pii_key`) pass removed from `redact_payload` | RED | `test_tracing.py::test_redact_payload_catches_a_pii_shaped_field_not_hardcoded` |
| M14 | structural (allowlist) pass removed from `redact_payload` | RED | `test_observability_mutation.py::test_looks_like_model_reverted_to_bare_issubset_turns_the_extra_key_arm_red` |
| M15 | append-only write turned into a truncating `"w"` write | RED | `test_audit.py::TestAppendOnly::test_two_writes_produce_two_lines_first_unchanged` |
| M16 | `trace_id` no longer read from the ContextVar | RED | `test_audit.py::TestRoundTrip::test_written_line_carries_every_contract_field` |
| M17 | `_endpoint_for_audit` reverted to returning the raw URL | RED | `test_observability_mutation.py::test_endpoint_for_audit_reverted_to_raw_url_turns_the_wiring_arm_red` |
| M18 | `isidentifier()` shape guard removed from `_safe_error_class` | RED | `test_audit.py::TestClosedVocabularyFailsClosed::test_error_class_admits_an_identifier_and_refuses_anything_else` |
| M19 | `graph_connection` call site passes `str(exc)` as `error_class` | RED | `test_audit.py::TestErrorFieldIsStructurallyBounded::test_credential_in_a_raised_exception_message_never_reaches_the_line` |
| M20 | `ncbi_transport` call site passes `str(exc)` as `error_class` | RED | `test_audit.py::TestErrorFieldIsStructurallyBounded::test_credential_in_a_transport_exception_message_never_reaches_the_line` |
| M21 | legacy `error` keyword no longer routed through `classify_error_code` | RED | `test_audit.py::TestLegacyErrorKeywordFailsClosed::test_a_message_passed_to_the_legacy_keyword_records_unexpected` |
| M22 | `tracing_enabled()` no longer requires the credential | RED | `test_config.py::TestTracingGate::test_flag_alone_does_not_enable_tracing` |
| M23 | `graph_connection` call site passes `exc.__class__.__qualname__` | RED | `test_audit.py::TestErrorClassCallSitesPassAClassNameLiteral::test_every_record_tool_call_passes_a_class_name_or_none` |

Every one restored byte-identical, asserted by SHA-256 comparison inside the driver's `finally` block.

### The permanent harness DOES discriminate, proven independently

Two of my source mutations (M14 and M17, plus M1b) turned a `test_observability_mutation.py` case red rather than the underlying arm. That is the harness's own CONTROL half firing: it runs each target arm unmutated first and requires green. A vacuous harness could not have done that, because a control half that asserts nothing cannot fail when the source under it breaks. This is the strongest available evidence that the harness is real, and it is evidence I generated rather than read.

I also checked the F-5.0-15 and F-5.0-16 monkeypatch-leak fixes rather than trusting their FIXED state. Every hand-built `pytest.MonkeyPatch()` in the file now either sits in a `try/finally` with `.undo()` (lines 217-220, 225-231, 434-440) or uses `pytest.MonkeyPatch.context()` (lines 293, 301, 344, 354, 549, 556, 558, 569, 571, 583, 736, 747, 781, 789, 865, 873, 912, 920). No construction is left unrestored. FIXED, verified.

The round-4 AST call-site arm is real and strict, verified with a mutation the permanent harness does not run: replacing `type(exc).__name__` with the semantically EQUIVALENT and equally safe `exc.__class__.__qualname__` still turns it red, with a precise message:

```
E   AssertionError: system_03_search_agent.tools.graph_connection passes a data-derived error_class:
    Attribute(value=Attribute(value=Name(id='exc', ctx=Load()), attr='__class__', ctx=Load()), attr='__qualname__', ctx=Load())
FAILED tests/.../test_audit.py::TestErrorClassCallSitesPassAClassNameLiteral::test_every_record_tool_call_passes_a_class_name_or_none
```

It enforces one exact spelling rather than the safety property, which will cost a future contributor a puzzling failure on a benign rewrite. That is over-strictness, not vacuity, and I record it as J-05, minor, rather than as a defect: given this phase's history, an arm that is too strict is the right side to err on.

### The three GREEN mutations

M10 is DISCLOSED. `tracker/phase_5.0.md`'s wiring coverage statement says it in as many words: "`_get_directory_listing`'s own audit hook has no test in this file at all, only `stream_filtered_tsv_rows`'s does." A stated gap is arguable, which is the whole point of the coverage rule. No new finding.

M7 and M8 are NOT disclosed anywhere, and they are the serious result of this section.

`build_traced_client` (`tracing.py:301-306`) is a six-line function, and two of those lines are the ENTIRE PII control this phase exists to install:

```python
    return Client(
        api_key=config.langsmith_api_key(),
        api_url=config.langsmith_endpoint(),
        anonymizer=redact_payload,
        hide_metadata=redact_payload,
    )
```

Delete `anonymizer=redact_payload` and `Client._hide_run_inputs` falls straight through to `if self._hide_inputs is False: return inputs` (`langsmith/client.py:2730-2731`), so `Query.owner_id`, `Query.user_id`, `Query.session_id` and `RequestContext.session_memory` are transmitted to LangSmith in cleartext. That is F-5.0-03 verbatim, the phase's own CRITICAL, restored. The observability suite reports `164 passed, 1 skipped`.

Why no arm catches it: every reference to `build_traced_client` in the test tree either monkeypatches it away or asserts it is NOT called.

```
$ grep -n "build_traced_client" tests/system_03_search_agent/observability/*.py
test_tracing.py:87:      monkeypatch.setattr(tracing, "build_traced_client", _fail_if_called)
test_tracing.py:108:     monkeypatch.setattr(tracing, "build_traced_client", _fail_if_called)
test_tracing.py:137:     monkeypatch.setattr(tracing, "build_traced_client", lambda: sentinel_client)
test_wiring.py:617:      monkeypatch.setattr(tracing, "build_traced_client", _fail_if_called)
test_observability_premise.py:393:  monkeypatch.setattr(tracing, "build_traced_client", _spy_build_traced_client)
test_observability_premise.py:687:  client = tracing.build_traced_client()
```

The single line that actually calls it, `test_observability_premise.py:687`, is the live opt-in arm gated behind `RUN_PREMISE_GATE=1` plus a real credential. It is the `1 skipped` in every run above, and it asserts `Client.info` connectivity, not the anonymizer.

So the phase's PII gate tests `redact_payload` thoroughly and never tests that `redact_payload` is INSTALLED. That is precisely this repository's recorded safety-by-proxy shape: build phase 4.3 shipped it twice as a critical, build phase 4.7's repair reproduced it, and build phase 4.11's durable rule is that an arm which cannot distinguish the control holding from nothing having happened is not an arm. Here the arm proves the redactor works on a dict handed to it directly, which is a correlate of the property, not the property.

It also means the goal contract's own verify-surface line is not met by any permanent arm: "A PII arm that inspects the actual assembled trace payload for `owner_id` and `user_id`, not a proxy for it." What satisfies that today is the one-off live read-back the phase document records (`trace_id` `pii-check-b958f3ec`, 9 spans, 30 `[redacted]` markers). That is real evidence and I credit it, but a manual measurement taken once is not a gate, and it will not fire on the next edit to `build_traced_client`.

Filed below as J-06, major, and it is a one-arm fix: construct the real client and assert `client._anonymizer is redact_payload` and `client._hide_metadata is redact_payload`, or better, drive a payload through `client._hide_run_inputs` and assert the identity fields come back redacted.

Grade for G4: the gate discriminates broadly and genuinely, 20 of 23. The two it misses are the two that install the phase's critical control.

## G5 the round-4 fixes

The whole of round 4 is one commit, `c8a8e7d`, touching `audit.py` (+518), `graph_connection.py` (+68), `ncbi_transport.py` (+60) and four test files. This is the least-exercised code on the branch, so every claim it makes was tested rather than read.

### `type(value) is str` in both guards: the claim holds

Round 4's commit message says two guards were "failing open inside a fail-closed check". Both fixes verified by construction, with hostile `str` subclasses built to defeat the naive check:

```
classify_error_code(LyingStr(secret)) -> unexpected
_safe_error_class(LyingId('a=b:c/d?e')) -> [not-an-identifier]
```

where `LyingStr.__eq__` returns True for everything and `LyingId.isidentifier()` returns True while `__len__` returns 4. Both close. Mutation-confirmed: reverting either to `isinstance` turns a named arm red (M4, M5 in the G4 table).

A third property in the same fix, which the docstring claims and which is easy to miss: `classify_error_code` returns the VOCABULARY MEMBER, not the caller's object. Verified by identity, not by equality:

```
classify_error_code(LyingStr("timeout")) -> 'unexpected' | is the tuple member: True
```

### The deleted module-docstring claim: what replaced it is TRUE

`audit.py:84-105` now says `isidentifier()` is a SHAPE guard, not a secrecy guard, and that what actually keeps a credential out of `error_class` is the CALLER. Both halves tested:

```
bare alphanumeric token admitted verbatim: True          <- the honest half
refused 'http://h/x?k=v'     -> '[not-an-identifier]'
refused 'a=b'                -> '[not-an-identifier]'
refused 'a:b'                -> '[not-an-identifier]'
refused 'a/b'                -> '[not-an-identifier]'
refused 'a@b'                -> '[not-an-identifier]'
refused 'a b'                -> '[not-an-identifier]'
refused 'a"b'                -> '[not-an-identifier]'
refused 'a&b'                -> '[not-an-identifier]'
```

The docstring describes exactly this behaviour and overstates nothing. Build phase 4.15's rule was that the fix for a confident sentence describing a check that is not there is deletion plus a test, and that is what happened here rather than a better sentence.

### The AST-based call-site arm: real, and strict

`TestErrorClassCallSitesPassAClassNameLiteral` parses both transport modules and requires every `record_tool_call` call site to pass `type(exc).__name__`. Mutation-verified in G4 (M19, M20, M23). It fires even on `exc.__class__.__qualname__`, which is semantically identical and equally safe, so it pins one spelling rather than the safety property. Recorded as J-05, minor: over-strictness is the correct side to err on given this phase's history, but the next contributor who rewrites the expression benignly will get a confusing failure.

### The premise gate's corrected compliance docstring: accurate as far as it goes

`test_observability_premise.py:445-471` now states plainly that the class asserts PRESENCE only, that `http_error` and `empty` have no producer anywhere in `src/`, and that an E-utilities body-level error is indistinguishable from a success on the line. Independently confirmed: `grep -rn "http_error\|\"empty\"" src/` finds them only in `audit.py`'s vocabulary declaration. The docstring agrees with `audit.py:194-206`'s own comment rather than contradicting it, which is the right outcome.

Its one omission is `record_ids`, which is in the same state and is not named. That is J-01.

### `audit_error_code`, the newest code in the phase, and an asymmetry between the two copies

Both transports gained an MRO-walking classifier in this commit. Both behave correctly on the cases the design cares about:

```
graph_connection subclass of GraphTimeoutError    -> timeout
graph_connection bare ValueError                  -> unexpected
ncbi_transport subclass of TransportTimeoutError  -> timeout
ncbi_transport bare ValueError                    -> unexpected
```

They are NOT implemented the same way, and the difference is observable. `graph_connection.py:262-263` keys the map on `klass.__name__`, a STRING; `ncbi_transport.py:448-449` keys it on `klass`, the CLASS OBJECT. Measured with two unrelated impostor classes that merely share a name:

```
impostor class named GraphTimeoutError,     graph mapping     -> timeout
impostor class named TransportTimeoutError, transport mapping -> unexpected
```

The graph classifier will label an unrelated third-party exception `timeout` purely because of its name. This is a FIDELITY defect, not a safety one: the value written is still a closed-vocabulary member chosen by this repository's code, so no credential path opens. But Section 20.3's stated purpose for this field is the fail-fast diagnostic that decides "model-caused or harness-caused", and a misclassified code is a wrong answer to exactly that question. Filed as J-08, minor.

## G6 production and AI security gates

Applied `.claude/rules/production-standards.md` and `.claude/rules/ai-security-standards.md`. `eval-harness` correctly does not apply: nothing in this phase generates an answer, touches grounding or emits a citation.

### Declared timeouts on every outbound call: PASS

- PostHog: `CAPTURE_TIMEOUT_SECONDS = 4.0` (`analytics.py:126`), passed EXPLICITLY on both branches of the POST (`analytics.py:395` and `:398`), and the constant's own comment records that it is deliberately not httpx's 5.0s default so an arm asserting it cannot pass by accident. That is the right instinct and it is the second time in this phase a value was chosen to make its own test non-vacuous.
- LangSmith: no new outbound call is issued by this repository's code; `Client` is constructed and handed to langsmith's own transport.
- The three chokepoints inherit the timeouts `tool-call-budgets.md` already fixed; this phase changes none of them, verified by the absence of any timeout constant in the diff for those three files.

### No secrets in logs or exception strings: PASS on the code this phase wrote

- `record_tool_call`'s own failure handler logs `type(exc).__name__` only (`audit.py:775-779`).
- `capture_event` logs `type(exc).__name__` only, on both its failure paths (`analytics.py:376-380`, `:400-404`), and `build_properties`' docstring (`analytics.py:255-262`) explains precisely why: `UnsafePropertyError`'s message can carry the caller-supplied value the function exists to keep out of PostHog. The claim and the code agree.
- `ncbi_transport` diagnostics use `_host_of` (`ncbi_transport.py:1184`), never the raw URL.

The exception is J-03 in G3, where a credential can reach a third party through langsmith's own error-string path.

### Schema validation at hops: PASS, and unusually good

`analytics.build_properties` (`analytics.py:226-308`) is a closed registry: an unregistered key raises, and each registered key declares an explicit `bool`, `count` or `enum` shape, with `bool` excluded from `count` because `bool` subclasses `int` in Python. `_bounded_distinct_id` caps at 200 characters. `params` on the audit line is capped at `_MAX_PARAMS_BYTES = 4096` with disclosure rather than silent truncation, mutation-confirmed (M12). This satisfies `production-standards.md`'s `maxLength`/`maxItems` requirement in spirit at every field this phase adds.

### No new dependency: PASS

```
$ git diff --stat develop...HEAD -- requirements.txt pyproject.toml frontend/package.json
(empty)
$ pip show posthog
(not installed)
```

PostHog ships as an `httpx` POST against the documented wire contract, exactly as the goal contract's constraint requires. No supply-chain review was owed and none was skipped.

### Least privilege: FAIL, and the record overstates the mitigation

F-5.0-12 correctly identifies that the provisioned `POSTHOG_API_KEY` is a `phx_` PERSONAL API key, which PostHog documents as granting "the same access as if you were logged into your PostHog instance", where capture wants the public `phc_` project token. `ai-security-standards.md` is explicit: "Never wire a new MCP server or tool integration to a full-access credential when a scoped, read-only, or single-purpose credential will do."

The finding's row asserts a safety property: "NO EVENT HAS BEEN SENT WITH IT and none will be until the product owner replaces it." Nothing in the code enforces that.

```
$ grep -n "def analytics_enabled" -A 8 src/system_03_search_agent/observability/config.py
191:def analytics_enabled() -> bool:
...
198:    return posthog_api_key() is not None
$ grep -n "phc_\|phx_\|phs_" src/system_03_search_agent/observability/*.py
(no matches)
```

`analytics_enabled()` is True for a key of ANY prefix, and `capture_event` places whatever it gets into the request body at `analytics.py:384`.

What actually prevents transmission today is which value happens to win the environment lookup, which is a provenance argument of the same kind this phase rejected twice. Measured on this machine, printing only prefixes and lengths:

```
shell POSTHOG_API_KEY:   prefix phc_   length 47     <- the correct project token
.env  POSTHOG_API_KEY:   prefix phx_   length 52     <- the personal API key
```

Nothing in this repository calls `load_dotenv()`, but importing `litellm` does, at import time (this repository's own finding F-2.1-04). `python-dotenv` defaults to `override=False`, so the shell wins WHERE IT IS SET. Remove that one export and the personal key becomes live:

```
$ env -u POSTHOG_API_KEY python -c "<import litellm, then read config>"
shell POSTHOG_API_KEY present at start: False
after importing litellm, config.posthog_api_key() prefix: phx_ | length: 52
config.analytics_enabled(): True
```

So a developer running the product in an ordinary shell that does not carry that export WILL POST an account-wide read-write PostHog credential to `https://us.i.posthog.com/i/v0/e` on every completed query. Not latent: reachable today, on this machine, by opening a new terminal.

Two things make this worse than a stale credential in a local file. First, `.env` was rewritten by THIS PHASE, under F-5.0-10, to an identical 40-key set with `env.example`, so the wrong credential was placed on the live path by the phase's own housekeeping. Second, the structural fix is the same move this phase already made once and got right: bound the input rather than argue about where it came from. `posthog_api_key()` returning None for any value that does not begin with `phc_` would make the finding's claim TRUE BY CONSTRUCTION and costs one line.

Filed as J-07, major.

### Observation, not a finding: `owner_id` goes to PostHog as `distinct_id`

`core/run.py:348` passes `distinct_id=query.owner_id`, the same field `redact_payload` redacts out of every LangSmith trace. I checked this against the spec before filing it and it is COMPLIANT rather than a defect: Section 20.1's PII rule is scoped to traces, Section 20.2 forbids "raw query text or citation content" and a distinct id is neither, PostHog cannot compute session length or a follow-up funnel without a stable per-caller id, and `owner_id` is already the opaque `user:<uuid>` / `guest:<uuid>` form. The comment at `core/run.py:340-346` states that reasoning explicitly rather than leaving a reader to reconstruct it. I record it only because the asymmetry is genuinely surprising on a first read, and manufacturing a requirement here is build phase 4.6's recorded failure.

## G7 scope

No line of this phase crosses `.claude/rules/v1-scope-boundary.md`.

- The three anchors are absent: `grep -rin "blast\|vcf\|sequence.similarity" src/system_03_search_agent/observability/` returns nothing, and no new tool, endpoint or compute path is added anywhere in the diff.
- No non-NCBI knowledge-graph federation. LangSmith and PostHog are observability sinks, not data layers; neither is queried for an answer and neither appears in the agent loop's retrieval path.
- No model distillation, no fusion or ensemble panels, no sub-query decomposition, no persistent cross-session per-user memory. The `trace_id` ContextVar is run-scoped and reset by `trace_id_scope`'s `finally` (`audit.py:265-267`), so it is not a memory mechanism.
- No automated mining. This phase writes records; nothing reads them back to cluster or promote anything.
- Section 25 names build phase 5.0 as written, so this is not an inserted phase needing separate justification.
- The locked documents are not edited: `git diff --stat develop...HEAD -- requirements/PRD.md requirements/Technical_specification.md` is empty.

PASS.

## Premise: does the ticket set satisfy the done-when

Leaf verification would pass this phase. All seven tickets are built, each has real tests, and the mutation coverage is genuinely strong. So this section asks the harder question instead: taken together, do the completed tickets deliver the outcome the goal contract names?

### Done-when, item by item

| Goal-contract done-when | Verdict | Evidence |
|---|---|---|
| Every Layer 1/2/3 access from any of the three chokepoints writes one append-only JSONL line carrying every Section 20.3 field, including the five `act_node` bypasses | PARTIAL | Every field is present on the line and all five bypasses are covered. Two fields have no producer: `record_ids` (J-01) and the E-utilities body-level signal (F-5.0-23, already open) |
| Enabling tracing attaches `trace_id` as the join key and provably transmits no `owner_id`, `user_id` or session-memory content | MET in behaviour, NOT gated | Verified by my own measurement and by the phase's live read-back. But deleting the line that installs the redactor leaves the suite green (J-06) |
| A PostHog event is emitted for each product signal this repository can honestly produce today, aggregates only | MET in code, credential wrong | Two events wired, closed property registry, three of Section 20.2's six signals honestly declared unbuildable. The live credential is a personal API key (J-07) |
| With no credential configured, tracing and analytics are OFF and make provably zero outbound calls, asserted by an arm that fails if a call is attempted | MET | `test_config.py::TestTracingGate::test_flag_alone_does_not_enable_tracing` goes red under M22; the `requests`-layer hermetic guard goes red under the harness's own mutation 6 |
| The audit log is gitignored | MET | `.gitignore:112:logs/` matches `logs/tool_audit.jsonl`, confirmed by `git check-ignore -v` |

### Verify surface, item by item

| Goal-contract verify surface | Verdict |
|---|---|
| A premise gate whose arms are each proven red by a mutation | LARGELY MET. 20 of my 23 independent source mutations turn a named arm red. The two that do not are the two lines installing the PII control (J-06) |
| One arm per bypass call site, with a populate-check | PARTIAL. Two of five call sites are driven by their real callers, both with genuine populate-checks; the other three are covered by construction and the shortfall is disclosed in the arms' own docstrings (J-04) |
| A no-credential arm asserting zero outbound calls, not merely that no exception was raised | MET |
| A PII arm that inspects the actual assembled trace payload for `owner_id` and `user_id`, NOT a proxy for it | NOT MET by any permanent arm. Every PII arm calls `redact_payload` directly, which is a correlate of the property. What satisfies this line today is a one-off manual read-back recorded in the phase document (J-06) |
| The full Python suite against the re-measured `4158 passed, 0 failed` baseline | MET. `4322 passed, 171 skipped, 1 xfailed, 0 failed` |
| `ruff check` over the WHOLE repository with no path argument | MET. `All checks passed!` |
| `python tracker/check_doc_drift.py --check` at 0 stale, 0 structural | NOT MET. 0 structural, 7 stale. Four are the deferred test counts; three are pre-existing on `develop` |

### The decomposition gap, stated as a premise finding

The phase split observability into three records and then split the work by MODULE: T-5.0-03 built `tracing.py`, T-5.0-05 wired every call site. That split is correct and it is the same split `plan-then-fan-out` recommends.

The property that actually makes the trace record safe is not owned by either ticket. `redact_payload` living in `tracing.py` is T-5.0-03's deliverable, and it is tested exhaustively. `traced_graph_run` being called from both `core/run.py` sites is T-5.0-05's deliverable, and it is tested. What nobody owns is the six-line function BETWEEN them, `build_traced_client`, whose two keyword arguments are the entire control. Every ticket succeeded and the seam between two of them is untested, which is exactly the failure this section exists to look for.

That is the premise-level statement of J-06, and it is why I grade it as blocking rather than as a missing nice-to-have. The phase's own critical, F-5.0-03, is closed today by two lines that no gate defends.

Everything else about the decomposition holds up under scrutiny. The chokepoint design is the right call and G1 proves it on the real callers. Three separate records with three separate failure modes is a faithful reading of Section 20. The coverage statements are unusually honest, and F-5.0-23 in particular is a finding the phase filed against ITSELF after driving the real path, which is the behaviour this harness exists to produce.

## Verify commands

All four run verbatim, on `c8a8e7d`, with `source venv/bin/activate` first, after every mutation was restored and byte-identity confirmed.

```
$ PYTHONPATH=src python -m pytest tests/system_03_search_agent/observability/ -q
........................................................................ [ 43%]
..................................................................s..... [ 87%]
.....................                                                    [100%]
164 passed, 1 skipped in 3.13s
```

```
$ PYTHONPATH=src python -m pytest -q -p no:randomly
4322 passed, 171 skipped, 1 xfailed, 8 warnings in 118.99s (0:01:58)
```

Zero failures. Comfortably above the goal contract's re-measured `4158 passed, 0 failed` branch-point baseline. The eight warnings are pre-existing `InsecureKeyLengthWarning`s from build phase 4.15's release-environment mutation arms, not from this phase.

I also note that `F-5.0-17`'s wall-clock flake (`test_free_text_reader_calls_run_concurrently`) did NOT reproduce in my run, with three of my own mutation batches having run against the same machine earlier in the session. It remains a real latent flake with a named owner; it is simply not red today.

```
$ ruff check
All checks passed!
```

Whole repository, no path argument, per build phase 4.15's CI finding.

```
$ python tracker/check_doc_drift.py --check
AGENTS.md:32: says 4329 python tests (computed: 4494)
AGENTS.md:32: says 141 learnings.md entries (computed: 144)
CLAUDE.md:32: says 4329 python tests (computed: 4494)
CLAUDE.md:32: says 141 learnings.md entries (computed: 144)
requirements/phase_6/Continuation_prompt.md:179: says 4329 python tests (computed: 4494)
requirements/phase_6/Continuation_prompt.md:208: says 141 learnings.md entries (computed: 144)
requirements/phase_6/Continuation_prompt.md:565: says 4329 python tests (computed: 4494)
error: 10 facts computed | 7 stale | 0 structural

$ echo $?
1
```

0 STRUCTURAL, as required and as instructed to confirm.

On the stale count: I was told four stale test-count rows are known and deferred, and I am not reporting those as a defect. The count is SEVEN, not four, so I checked the other three rather than assuming. They are the `141 learnings.md entries` rows, and they are PRE-EXISTING on `develop`, not this phase's: `git diff --stat develop...HEAD -- LEARNINGS.md` is empty, so this branch never touched the file the checker computes that fact from. Both groups are `/phase-checkpoint` work. Recorded so the next reader does not have to re-derive it.

## Findings

Filed the moment each was established, per the write-first rule. IDs are `J-nn` so they cannot collide with the lead's `F-5.0-nn` series or the adversary's.

| ID | Severity | Summary | Evidence | Blocks? |
|---|---|---|---|---|
| J-06 | major | `build_traced_client`'s two keyword arguments are the ENTIRE PII control that closes this phase's own critical F-5.0-03, and deleting either leaves the suite green. Every test reference either monkeypatches the function away or asserts it is not called; the one real invocation is the skipped live arm. The goal contract's "PII arm that inspects the actual assembled trace payload, not a proxy for it" is met by no permanent arm | G4, mutations M7 and M8, both `164 passed, 1 skipped`. `grep -n "build_traced_client" tests/system_03_search_agent/observability/*.py` | YES |
| J-07 | major | The least-privilege violation F-5.0-12 filed is LIVE, not latent, and the finding's claim that "none will be sent until the product owner replaces it" is enforced by nothing. `analytics_enabled()` (`config.py:198`) accepts any prefix; `.env`, rewritten by this phase's own F-5.0-10 fix, carries the `phx_` personal API key; `litellm`'s import-time `load_dotenv()` makes it live in any shell lacking the `phc_` export | `env -u POSTHOG_API_KEY` run: `config.posthog_api_key() prefix: phx_`, `analytics_enabled(): True`. `grep -n "phc_" src/system_03_search_agent/observability/*.py` returns nothing | YES |
| J-03 | major | langsmith's THIRD anonymizer path, `_hide_run_error` (`client.py:2744`, called at `:2318` and `:3684`), routes a run's error string through `redact_payload`, which returns it byte-identical. A credential inside an exception message reaches LangSmith in cleartext. This is F-5.0-13's exact class on the other transmission path, defended only by the provenance argument this phase rejected three times. Undocumented and untested | G3, both URL and DSN shapes byte-identical with the credential present. `grep -n "hide_run_error" tracker/phase_5.0.md` and the tracing tests both return nothing | YES |
| J-01 | major | `record_ids`, a Section 20.3 required field, has NO producer anywhere in `src/`. Every audit line writes `[]`, including for a response body that carried ids. `test_audit.py:215` populates it via a direct `record_tool_call` call, giving false assurance, while the premise gate asserts presence only. The premise gate's coverage statement names `http_error`/`empty` as unproduced and omits this one, which is the same class | G2, real chokepoint line with `idlist: ["672","675"]` in the response and `"record_ids": []` on the line. `grep -rn "record_ids" src/` | NO, but it is an unstated coverage gap on a spec-required field |
| J-02 | minor | The phase document's finding two, "the transport is the only place Section 20.3's required fields actually exist", is overstated. It holds for `http_status` and `latency_ms` and is false for `record_ids` and the E-utilities body-level signal, both of which exist only in the action modules the argument dismisses. The chokepoint design is still right, for G1's reason; it is a trade presented as a strict improvement | G2, cross-referenced against F-5.0-23 and J-01 | NO |
| J-04 | minor | The goal contract promises "one arm per bypass call site" and there are five sites with two real-caller arms. `core/graph.py:2098` and `:2139` and `export/traversal.py:801` are covered by construction rather than by an arm. DISCLOSED in the arms' own docstrings, which is why this is minor | G1, `test_observability_premise.py:305-310` and `:327` | NO |
| J-05 | minor | `TestErrorClassCallSitesPassAClassNameLiteral` pins one exact spelling rather than the safety property: `exc.__class__.__qualname__`, semantically identical and equally safe, turns it red. Over-strict rather than vacuous, and the right side to err on, but it will confuse a future benign rewrite | G4, mutation M23 with the AST node in the failure message | NO |
| J-08 | minor | The two `audit_error_code` implementations added in round 4 are asymmetric. `graph_connection.py:263` keys on `klass.__name__`, a string, so an unrelated third-party exception merely NAMED `GraphTimeoutError` is recorded as `timeout`; `ncbi_transport.py:449` keys on the class object and correctly records `unexpected`. Fidelity, not safety, but Section 20.3's stated purpose for this field is the model-caused-versus-harness-caused diagnostic, which a misclassification answers wrongly | G5, impostor-class probe | NO |

Nothing I found contradicts a finding the phase already filed. Three of the eight (J-01, J-02, J-04) are gaps the phase's own coverage discipline would have caught had it been extended one field or one call site further, which is a compliment to the discipline rather than the reverse.

## Verdict

FAIL.

This is a strong phase and the failure is narrow. The chokepoint design is correct and is proven at the real bypass callers, not merely at the shared function beneath them. The redaction both holds and, importantly, does not over-redact: every field build phase 5.1's graders need survives, and exactly the four Section 20.1 forbids do not. The error-field redesign is the right call and the round-4 fixes are sound under hostile input. Twenty of my twenty-three independent source mutations turn a named arm red, and two of them turned the permanent harness's own control half red, which is the strongest evidence available that the harness is not vacuous. The coverage statements are the most honest I have read in this repository, to the point where the phase filed F-5.0-23 against its own docstring after driving the real path.

Three findings block.

J-06 blocks because it is the phase's own critical with no gate behind it. `build_traced_client`'s `anonymizer=redact_payload` is the single line standing between `GraphState` and LangSmith, and deleting it produces `164 passed, 1 skipped`. This repository has eleven recorded instances of assertions that could not fail; this is the twelfth, it sits on the most sensitive control the phase ships, and it is the precise safety-by-proxy shape build phase 4.3 shipped twice as a critical. The fix is one arm.

J-07 blocks because the least-privilege violation is reachable today rather than deferred, and because the record says otherwise. `ai-security-standards.md` forbids wiring a full-access credential to a new integration; an account-wide read-write PostHog key is in `.env`, `analytics_enabled()` accepts it, and the only thing preventing transmission is which shell you happen to be in. The phase already knows the right move here, because it made it once on the error field: bound the input. Refusing any key that is not `phc_`-prefixed makes F-5.0-12's own claim true by construction.

J-03 blocks because it is the same defect the phase spent three review rounds and three Rule 4 stops closing, surviving on the other transmission path, protected by the exact argument the phase wrote down as insufficient. A credential in an exception message cannot reach the audit sink and can reach LangSmith. Closing it is a small change and `_redact_value_string` already exists for it; leaving it open would mean the durable lesson was applied to one sink and not to the other, which is the version of this phase least likely to hold up later.

J-01 does not block on its own, but it should be recorded in `tracker/phase_5.0.md` before merge in the same form F-5.0-23 was, since an unproduced spec-required field that a unit test appears to exercise is precisely the shape that gets forgotten.

Recommended disposition: fix J-06 and J-03 in code, take a product-owner decision on J-07 (the structural prefix check is the cheap option and I would recommend it over swapping the credential alone, since swapping it leaves the same hole open for the next key), file J-01 with an owner, and carry J-02, J-04, J-05 and J-08 as minor with named owners. None of the four minors justifies another round.
