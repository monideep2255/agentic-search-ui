# Build phase 4.4 judge report, round 1

Judge round 1 of a maximum of 2.
Branch: `phase/4.4-kgx-export`. Build committed at `76defaf`.
Graded: T-4.4-02, T-4.4-03, T-4.4-04, T-4.4-05 against their acceptance criteria in `tracker/phase_4.4.md`.
Read-only on source. No live graph test run; the adversary owns live-graph access this phase.

No finding in this round sits inside code written to fix an earlier finding in this phase. There is no `Regression of:` entry, and the phase does not stop mid-round on that ground.

## Verdict

FAIL against the merge bar: 3 blocking findings (0 critical, 3 reachable major), 7 non-blocking findings (0 critical, 0 reachable major, 7 minor or latent).

## What was run

- `venv/bin/python -m pytest tests/system_03_search_agent/export/ -q --ignore=.../test_kgx_export_premise.py`: `90 passed in 0.27s`.
- `venv/bin/ruff check tests/system_03_search_agent/export/`: `All checks passed!`
- A read-only reachability probe against the real `traversal.py` with a mocked `execute_cypher`, run from the scratchpad, never written into `src/` or `tests/`. Its output is quoted in F-4.4-02.
- Query-safety greps: no `f"` and no `.format(` appears anywhere in `traversal.py`, `kgx.py`, or `manifest.py`; no `psycopg2` import and no second connection factory anywhere under `src/system_03_search_agent/export/`.

## Blocking findings

### F-4.4-02: the manifest reports the edge labels REQUESTED as the labels TRAVERSED, and a default export can query one label while listing fourteen

Status: filed
Raised by: judge
Severity: major
Round: 1
Reachable: yes. It fires on the plain documented invocation `s3-kgx-export NCBIGene:7157 --output-dir DIR`, with no flags, and was reproduced against the real `traversal.py` code.
Ticket: T-4.4-04 (the manifest field), with the cause in T-4.4-02 (the traversal never reports which labels it queried)
Location: `src/system_03_search_agent/export/manifest.py:109`, `src/system_03_search_agent/export/kgx.py:335`, `src/system_03_search_agent/export/traversal.py:522-535`

What happened: `manifest.build_manifest`'s own docstring defines the field as "edge_labels_used: the edge labels actually traversed" (`manifest.py:109`). `kgx.export_subgraph` populates it with `edge_labels if edge_labels is not None else EDGE_LABELS` (`kgx.py:335`), which is the label set the caller ASKED for, never the set the traversal actually issued a query for. The traversal does not record the latter at all, so the value cannot be derived even in principle from what `traverse_subgraph` returns.

Two independent mechanisms make requested and traversed diverge, and both are on the default path:

- `_directions_for` returns `[]` for any label whose `EDGE_ENDPOINTS` pair does not include the expanding vertex's label (`traversal.py:325`). For a Gene seed, `has_mesh_annotation`, `has_phenotype`, `cited_in` and `subclass_of` are never queried. The manifest lists all four.
- `EDGE_LABELS` is ordered by row count descending, so `mentioned_in` (Gene to Article) is the FIRST label queried for a Gene seed, and `gene_associated_with_condition` is ninth. `max_nodes` is shared across all labels, so a hub gene's article neighbourhood consumes the whole node budget before any later label is reached.

Reproduced against the real module with a mocked `execute_cypher`, default caps, `hops=1`, `edge_labels=None`, seed `NCBIGene:7157`:

```
graph calls issued: 2
    MATCH (n:Gene {id: $seed_id}) RETURN n LIMIT 1
    MATCH (a:Gene {id: $seed_id})-[r:mentioned_in]->(b:Article) RETURN r, b LIMIT 500
nodes: 500 edges: 499
node labels present: ['Article', 'Gene']
truncated: True [{'cap': 'max_nodes', 'value': 500}, {'cap': 'max_edges', 'value': 1000}]
```

One edge label was queried. The manifest for that same run lists fourteen under a field documented as "actually traversed", and discloses only `max_nodes=500`. A consumer reading that manifest concludes the export sampled across all fourteen relationship types up to a 500-node ceiling. It sampled one. Someone checking whether TP53 has disease associations in this export would find none and have nothing in the manifest telling them the label was never queried.

The cap-level truncation disclosure is real and is not the defect. The defect is that the manifest positively asserts coverage the export does not have. This is the same shape as build phase 4.3's two criticals: a value (which labels were traversed) decided by a proxy for that value (which labels were requested) rather than by the value itself.

History:
- 2026-08-19 judge: filed

### F-4.4-03: an edge's `source_url` is attributed from its subject endpoint with no marking, and a raw stored URL is passed through unre-derived, reversing F-2.1-B06, F-2.1-C04 and F-2.1-C05

Status: filed
Raised by: judge
Severity: major
Round: 1
Reachable: yes. Every edge row in every export goes through `_edge_row`; there is no other edge path.
Ticket: T-4.4-03
Location: `src/system_03_search_agent/export/kgx.py:233`, `src/system_03_search_agent/export/kgx.py:163-177`

What happened: `_edge_row` resolves an edge's citation with

```python
resolved_url = _resolve_source_url(subject_curie, properties.get("source_url"))
```

which (a) keeps the edge's raw stored `source_url` string verbatim whenever it prefix-matches the host pattern, and (b) otherwise derives a URL from the SUBJECT endpoint's CURIE, unconditionally, never the object, and with nothing on the row saying the citation belongs to an endpoint rather than to the edge.

`cypher_provenance` already owns this exact problem and solved it differently, under three filed findings this repository paid for:

- `_attributed_endpoint_curie` (`cypher_provenance.py:531-546`) reverse-derives the CURIE from the edge's OWN stored `source_url` first, because that is edge-intrinsic and does not depend on which sibling column a query happened to project (F-2.1-C05). Only when that fails does it fall back to an endpoint, and it tries `start_id` then `end_id`, not subject-only.
- `_shape_entity` (`cypher_provenance.py:628-644`) then RE-DERIVES the canonical URL from that verified CURIE and never passes the raw stored string through, in its own words so that "a stored value's own formatting (a missing trailing slash, stray whitespace) must never leak into the citation, or two differently-formatted stored URLs for the same record would defeat F-2.1-C04's determinism guarantee".
- It sets `fields["_cited_via_endpoint_curie"]` to mark the row as "an edge citing an endpoint's record, never presented as the edge's own identity", which is precisely the misattribution F-2.1-B06 filed: a citation that "survives inspection while pointing at the wrong thing".

`edges.tsv` carries none of that. The host check is `re.match`, a prefix check, so a stored value such as `https://www.ncbi.nlm.nih.gov/gene/7157 https://elsewhere.example/x` passes and is written whole into the `source_url` column, which is the pass-through F-2.1-C04 closed. And on the fallback path, the reproduced run in F-4.4-02 would write 499 `mentioned_in` edge rows, each asserting "TP53 mentioned_in PMID:N", every one of them citing the TP53 gene page and none of them marked as an endpoint citation.

`kgx.py`'s module docstring (lines 15-21) claims parity with "the same host-pinned builder `cypher_query`'s own citation path uses". The builder is the same. The attribution policy around it is not, and the docstring is where a reader would stop checking. This repository's citation rule is stated as non-negotiable in `CLAUDE.md`, and `edges.tsv` is a delivery surface a consumer reads without the agent in the loop.

History:
- 2026-08-19 judge: filed

### F-4.4-04: the CLI renders every input-validation error as a graph-transport failure, discarding the precise message the validator built

Status: filed
Raised by: judge
Severity: major
Round: 1
Reachable: yes. `s3-kgx-export NCBIGene:7157 --output-dir DIR --edge-label gene_associated_with_disease` reaches it with one documented flag and a plausible typo.
Ticket: T-4.4-05
Location: `src/system_03_search_agent/export/cli.py:312-330`, against `src/system_03_search_agent/export/traversal.py:266-274`

What happened: `run()` catches `GraphError` first and prints its (already redacted) message, then catches every other `Exception` and prints only the type name plus a fixed remediation string:

```
s3-kgx-export: the export failed (ValueError); check that the output directory is
writable and that the graph transport (the SSH tunnel to the Hetzner graph host)
is reachable, then retry
```

Three distinct pure input-validation failures land in that arm, all of them raised before any graph contact:

- `_validate_edge_labels` (`traversal.py:266-274`) on an unknown `--edge-label`. It builds the exact right message, naming the offending label and listing all fourteen valid ones, and the CLI throws it away.
- `traverse_subgraph`'s `hops must be zero or greater` on a negative `--hops`.
- `export_subgraph`'s `export_subgraph requires at least one seed CURIE`.

For all three, both remediations the message offers are wrong, and retrying does nothing. `production-standards`' retry-safety gate is that an error must say what to do next; this says what to do next confidently and incorrectly, and it sends the operator to check an SSH tunnel that is fine. It is a systematic misclassification of the whole input-validation class, not one message.

The catch-all's own comment justifies suppressing `str(exc)` on credential-leak grounds, and that reasoning is sound for genuinely unknown exception shapes; `tests/.../test_kgx_cli.py:437-454` proves it works. The gap is that `ValueError` from this module's own two known validators is not an unknown shape, and nothing distinguishes it.

History:
- 2026-08-19 judge: filed

## Non-blocking findings, tracked with an owner

### F-4.4-05: `manifest.summary_lines` is dead code, and the drift it exists to prevent has already happened

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: yes as drift, no as a wrong output. The function is never called from any non-test code, so its own behaviour cannot reach a user.
Ticket: T-4.4-04
Location: `src/system_03_search_agent/export/manifest.py:174-201`, `src/system_03_search_agent/export/cli.py:229-253`
Owner: the T-4.4-04/T-4.4-05 seam owner, next touch of either file.

What happened: `summary_lines`' docstring states it "exists so a caller that also prints to the command's own output (T-4.4-05's batch entry point, a different builder's file) states the same facts the manifest file states, worded identically, rather than re-deriving a summary that could drift". A repository-wide grep finds exactly one definition and no caller outside `test_kgx_manifest.py`. `cli._print_disclosures` re-derives its own wording, which is the drift the function was written to prevent. Six tests in `TestSummaryLines` exercise a function nothing runs.

One user-visible consequence: `summary_lines` emits an explicit "This export hit no cap; it is the complete requested subgraph." line. `cli._print_disclosures` emits nothing in that case, so on the command's own output "complete" is signalled only by the absence of a truncation line, which is disclosure by omission at the surface a user actually reads. T-4.4-04's criterion 3 is scoped to the manifest, where the explicit `truncated: false` does satisfy it, so this is a gap rather than a criterion miss.

History:
- 2026-08-19 judge: filed

### F-4.4-06: the regression guard for the ambiguous-truncation disclosure is vacuous

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: no as a product defect. It is a hole in the verify surface, not in the shipped code.
Ticket: T-4.4-02
Location: `tests/system_03_search_agent/export/test_kgx_traversal.py:240-264`
Owner: whoever fixes F-4.4-02, since both touch the same disclosure path.

What happened: `test_an_earlier_unrelated_cap_hit_does_not_suppress_this_disclosure` names, in twenty lines of comment, the property at `traversal.py:556-572`: that comparing `caps_hit` against a snapshot rather than against emptiness stops an earlier unrelated cap from suppressing a later disclosure. It then never calls `traverse_subgraph`. It constructs a `_Budget` with caps of 5000, marks one, calls `mark_binding_cap(10, 10)` where 4990 rooms remain under both caps, and asserts `set(budget.caps_hit) == caps_before`.

That assertion cannot fail. `mark_binding_cap` marks only when a remaining count is at or below zero, so with room left it is a no-op by construction, in this test and in any conceivable future version of it. I could not construct an input under which it fails. The branch it claims to guard is untested; `TestAmbiguousMaxRowLimitTruncation`'s first test covers the empty-`caps_hit` path only.

History:
- 2026-08-19 judge: filed

### F-4.4-07: two guard branches inside the row loop are unreachable, including one that is the only in-loop cap disclosure

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: no. The branches themselves cannot be entered, which is the finding.
Ticket: T-4.4-02
Location: `src/system_03_search_agent/export/traversal.py:576-577`, `src/system_03_search_agent/export/traversal.py:617-619`
Owner: T-4.4-02, tracked not fixed.

What happened: `limit_n = budget.fetch_limit(len(nodes), len(edges))` is computed before the query (`traversal.py:530`) and equals `min(max_nodes - len(nodes), max_edges - len(edges))`; rows are then trimmed to `limit_n` (`traversal.py:573`); each row adds at most one node and at most one edge. So at row index `i`, `len(nodes) <= N0 + i <= N0 + limit_n - 1 <= max_nodes - 1`, and identically for edges. Both `len(nodes) >= max_nodes` at line 576 and `len(edges) >= max_edges` at line 617 are therefore always false.

The line 617 arm is the only place inside the row loop that calls `budget.mark(_CAP_MAX_EDGES, ...)`, so the in-loop edge-cap disclosure never fires. Cap enforcement rests entirely on the pre-query `fetch_limit` computation, which does hold. Nothing is currently mis-reported. The finding is that two arms present themselves as defence in depth and provide none, which will read as coverage to the next person who changes the trimming logic.

History:
- 2026-08-19 judge: filed

### F-4.4-08: an edge whose endpoints do not resolve is dropped silently and counted nowhere

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: no with today's graph. It needs a vertex carrying no `properties.id` or no AGE internal `id`, which the BioLink-conformant graph does not produce; I could not construct a live input that reaches it.
Ticket: T-4.4-02
Location: `src/system_03_search_agent/export/traversal.py:604-609`, `src/system_03_search_agent/export/traversal.py:615-616`
Owner: T-4.4-02, tracked not fixed.

What happened: two `continue` statements drop an edge with no counter and no truncation entry. Line 615 drops any edge whose `start_id` or `end_id` is absent from `curie_by_internal_id`; line 604 drops an edge whose far vertex could not be admitted. `TraversalResult` has no field for dropped rows, so the manifest cannot disclose them even if the caller wanted to. Silent dropping is this project's most-filed defect class, so it is worth a counter on `TraversalResult` even though nothing reaches it today.

History:
- 2026-08-19 judge: filed

### F-4.4-09: two docstring safety claims in `traversal.py` have no test asserting them

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: yes for the query shape, no for a demonstrated failure. Both claims may well be true; neither is checked.
Ticket: T-4.4-02
Location: `src/system_03_search_agent/export/traversal.py:109-116` and `:536-538`; `src/system_03_search_agent/export/traversal.py:300-303` and `:362`
Owner: T-4.4-02, tracked not fixed.

What happened, two claims:

- The per-call 30 second budget. `_PER_CALL_TIMEOUT_S = 30.0` and `remaining_call_time = max(min(_PER_CALL_TIMEOUT_S, budget.time_remaining()), 1.0)` implement T-4.4-02's fifth criterion correctly by inspection, but `FakeGraph.__call__` accepts `timeout_s` and ignores it, and no test in the file asserts anything about the value passed. The criterion is met by code and unasserted by test.
- The mixed-endpoint speed claim. `_directions_for`'s docstring says of `close_match` and `exact_match` that "the edge label itself is still explicit, which is the property that keeps this query fast; only the far vertex label is unknown". The phase's measurement (23.2s unscoped versus 2.3s scoped) was taken on `gene_associated_with_condition`, which has labelled endpoints at both ends. No measurement covers an edge-labelled query with an UNLABELLED far end, which is what `_hop_cypher` emits for those two labels (`traversal.py:362`, `far_pattern = "(b)"`), in both directions, for every frontier vertex, on the default `edge_labels=None` path. The claim is extrapolated from a measurement that did not cover its shape. Worst case is bounded: a slow call hits the 30 second timeout, is caught as `GraphTimeoutError`, and is disclosed as `time_budget_s`.

History:
- 2026-08-19 judge: filed

### F-4.4-10: the hop limit is never reported as a bound, though T-4.4-02's criterion names it alongside the node and edge caps

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: yes, on any export whose frontier is still non-empty at the hop limit, which is the normal case.
Ticket: T-4.4-02
Location: `src/system_03_search_agent/export/traversal.py:120-123`, `src/system_03_search_agent/export/traversal.py:509`
Owner: T-4.4-02, tracked not fixed.

What happened: T-4.4-02's fourth criterion reads "A traversal that would exceed its node cap, edge cap, or hop limit stops at the cap and reports which cap it hit". `_CAP_ORDER` contains `max_nodes`, `max_edges` and `time_budget_s` only. When `while depth < hops` exits with a non-empty `next_frontier`, nothing is recorded, `truncated` stays False, and the manifest reads as an export that hit no bound. `hops` is recorded elsewhere in the manifest, and the hop limit is the caller's own request rather than a cap the traversal imposed, which is why this is minor rather than a blocker; the criterion nonetheless names three bounds and the code reports two of them plus a fourth.

History:
- 2026-08-19 judge: filed

### F-4.4-11: `graph_snapshot_version` states a hardcoded fallback as fact, with nothing marking it as a fallback

Status: filed
Raised by: judge
Severity: minor
Round: 1
Reachable: yes today. `GRAPH_SNAPSHOT_VERSION` does not appear in `.env`, so every manifest this phase writes takes the fallback.
Ticket: T-4.4-04
Location: `src/system_03_search_agent/export/manifest.py:73-83`
Owner: tracked, not this phase. It is pre-existing `cypher_query` behaviour restated, and changing it changes both.

What happened: with the environment variable unset, `graph_snapshot_version()` returns the constant `"ncbi_kg_v1_2026-04-22"`, and `build_manifest` writes it into `graph_snapshot_version` with no flag distinguishing a value read from configuration from a value assumed. A consumer cannot tell that the export's stated snapshot was never read from the graph. Deliberately mirrors `cypher_query`, is documented as doing so, and would drift if changed here alone, so it is recorded rather than fixed.

## Criterion-by-criterion grading

### T-4.4-02, bounded subgraph traversal

| # | Criterion | Grade | Evidence |
|---|-----------|-------|----------|
| 1 | Reads Layer 1 through `graph_connection.execute_cypher`, no second connection factory, no second credential | MET | `traversal.py:71-76` imports only `execute_cypher`, `ConnectionFactory`, `GraphTimeoutError`. Grep for `psycopg2`, `connect(`, `os.environ` across `src/system_03_search_agent/export/`: one hit, `manifest.py:80`, and it is `GRAPH_SNAPSHOT_VERSION`, not a credential |
| 2 | Every value reaching the Cypher payload bound through PREPARE/EXECUTE; no f-string, no `.format()` in any query text | MET | `traversal.py:394` and `:542` pass `params={"seed_id": ...}`; `_seed_lookup_cypher:289` and `_hop_cypher:362-370` use `+` concatenation of validated constants only. Grep for `f"` in `traversal.py`, `kgx.py`, `manifest.py`: three hits, all inside docstrings. Grep for `.format(`: none |
| 3 | Every relationship pattern carries an explicit edge label from `EDGE_LABELS` | MET | `_hop_cypher:353-354` rejects any label outside `EDGE_LABELS` before concatenation; `:366` and `:368` emit `-[r:<label>]->`. `test_kgx_traversal.py:97` fails the fake on any query shape outside the three regexes, all of which require a labelled relationship |
| 4 | A traversal exceeding its node cap, edge cap, or hop limit stops and reports which cap | PARTIALLY MET | Node, edge and time caps are marked and returned (`traversal.py:210-251`, verified by `test_kgx_traversal.py:137-167`, `:203-238`, `:337-357`). The hop limit is not: F-4.4-10 |
| 5 | Each graph call within the 30s budget; wall-clock exhaustion returns the partial subgraph, never a hang | MET IN CODE, UNASSERTED BY TEST | `_PER_CALL_TIMEOUT_S = 30.0` at `:116`, applied at `:487` and `:536-538`; `GraphTimeoutError` caught at `:490` and `:548` and returned as partial. No test asserts the value of `timeout_s`: F-4.4-09 |
| 6 | A seed CURIE matching no vertex returns an empty subgraph with a reason, not an exception | MET | `_lookup_seed:405` returns None, `:494-495` continues, `:651-655` sets `empty_reason`. `test_kgx_traversal.py:192-200` |
| 7 | No variable-length relationship pattern ever emitted | MET | `_hop_cypher` emits `[r:<label>]` only, from a fixed constant tuple; no `*` is constructible. `test_kgx_traversal.py:376-379` |

Also filed against this ticket: F-4.4-06 (vacuous guard), F-4.4-07 (unreachable branches), F-4.4-08 (silent edge drop), F-4.4-09 (unasserted claims), and F-4.4-02's cause.

### T-4.4-03, KGX serialization

| # | Criterion | Grade | Evidence |
|---|-----------|-------|----------|
| 1 | `nodes.tsv` first five columns `id, category, name, source, source_url`, in order | MET | `kgx.py:74`, ordering enforced by `_build_fieldnames:128`. `test_kgx_serialization.py:52`, `:67` |
| 2 | `edges.tsv` first seven columns in order | MET | `kgx.py:75-83`; `test_kgx_serialization.py:71-74` |
| 3 | Extras follow sorted alphabetically; a row missing a column is an empty field, not a shifted row | MET | `_build_fieldnames:128` returns `required + sorted(extra)`; `_write_tsv:158` fills every fieldname with `record.get(name, "")`. `test_kgx_serialization.py:46-60`, `:76-93` |
| 4 | List and tuple values pipe-joined | MET | `serialize_value:109-110`; `test_kgx_serialization.py:28-32`, `:120-128` |
| 5 | Every `source_url` from the host-pinned builders; an unbuildable URL is empty and counted, never guessed | LITERALLY MET, POLICY DIVERGES | `_resolve_source_url:163-177` uses `NCBI_RECORD_URL_PATTERN` and `source_url_for_curie` only, and returns None rather than a guess; the empty count flows to the manifest via `rows_from_traversal:263`. For EDGES the CURIE used is the subject endpoint's, unmarked, and a raw stored URL is passed through unre-derived: F-4.4-03 |
| 6 | A value containing a tab, newline or quote round-trips through a standard TSV reader without shifting or splitting | MET | `_write_tsv:148-159` opens with `newline=""` and uses `csv.DictWriter` default QUOTE_MINIMAL; `test_kgx_serialization.py:95-118` asserts byte-for-byte round trip of all three characters in one field, with a following row intact |
| 7 | UTF-8 with a header row; a zero-row export still writes both files with headers | MET | `encoding="utf-8"` at `:148`, `writer.writeheader()` at `:156` unconditionally; `test_kgx_serialization.py:64-74`. `export_subgraph:332-333` writes both files on every path |

### T-4.4-04, manifest, truncation disclosure, and the Layer 1 limitation

| # | Criterion | Grade | Evidence |
|---|-----------|-------|----------|
| 1 | Every export writes `manifest.json` alongside the two TSV files | MET | `kgx.py:352` unconditional; `manifest.py:169` writes into `output_dir` only. `test_kgx_manifest.py:118-123` |
| 2 | Records seeds, hop limit, every cap value, node and edge counts, snapshot version, timestamp | MET | `manifest.py:138-158`. `test_kgx_manifest.py:58-74` |
| 3 | A cap hit records which cap and at what value and that the subgraph is incomplete; no cap hit is recorded explicitly, not by omission | MET IN THE MANIFEST | `truncated` and `truncation` always present (`manifest.py:149-150`); `test_kgx_manifest.py:90-98`. On the command's own output the no-cap case prints nothing: F-4.4-05 |
| 4 | The manifest states Layer 1 only, and that Layers 2 and 3 are fetched live and absent | MET | `_LAYER_NOTE` at `manifest.py:64-70`, always emitted at `:153`. `test_kgx_manifest.py:76-84` |
| 5 | The count of rows written with an empty `source_url` appears in the manifest | MET | `manifest.py:154`, fed from `kgx.rows_from_traversal:263`. `test_kgx_manifest.py:100-102` |
| 6 | The same limitation and truncation statements appear on the command's own output | MET WITH A GAP | `cli._print_disclosures:229-253`; `test_kgx_cli.py:282-311`. The no-cap statement is absent and the wording is re-derived rather than shared: F-4.4-05 |

Also filed against this ticket: F-4.4-02 (the `edge_labels` field) and F-4.4-11 (the snapshot fallback).

### T-4.4-05, the batch entry point

| # | Criterion | Grade | Evidence |
|---|-----------|-------|----------|
| 1 | Invoked by its own console script and by `python -m`; neither routes through the REST API or the agent loop | PARTIALLY MET, PRE-EXISTING | `pyproject.toml:55` registers `s3-kgx-export`; `cli.py:362-363` provides the `__main__` guard, exercised as a real subprocess at `test_kgx_cli.py:508-535`. The console script does not resolve because nothing is installed, already filed as F-4.4-01 and owned by build phase 6.1. No import of `adapters.cli`, the REST client, or the agent loop anywhere in `cli.py` |
| 2 | Accepts seeds, a hop limit, an output directory and cap overrides; rejects an unparseable CURIE with an actionable message naming the expected shape | MET FOR CURIEs | `_parse_args:138-203`, `_invalid_seeds:206-212`, message at `:270-273` naming `NCBIGene:7157`. `test_kgx_cli.py:120-172`. Every OTHER validation failure is misrendered: F-4.4-04 |
| 3 | Exits non-zero when the graph is unreachable, naming the transport rather than a stack trace | MET | `cli.py:303-311` for `GraphError`, `:312-330` for anything else; both name the SSH tunnel and neither prints a traceback. `test_kgx_cli.py:379-424`, parameterised over all three `GraphError` subclasses |
| 4 | Writes no file outside the output directory it was given | MET | `cli.py` writes no file itself; `export_subgraph:332-352` writes exactly three paths under `output_dir`. `test_kgx_cli.py:355-376` asserts the target holds exactly those three names and a sibling directory is untouched |
| 5 | No credential value in the command's output or any log line, on success or failure | MET | `cli.py:312-330` prints `type(exc).__name__` only for non-`GraphError`; `test_kgx_cli.py:437-454` raises a `ValueError` carrying a full DSN with a password and asserts neither the password nor the DSN reaches stdout or stderr |

## The cap-default coupling, checked in code

`cli.run` omits `max_nodes`, `max_edges` and `time_budget_s` from `call_kwargs` unless the corresponding flag was given (`cli.py:294-299`), and omits `edge_labels` unless `--edge-label` was passed (`:292`). `export_subgraph`'s signature (`kgx.py:266-274`) declares `max_nodes=DEFAULT_MAX_NODES`, `max_edges=DEFAULT_MAX_EDGES`, `time_budget_s=DEFAULT_TIME_BUDGET_S`, `edge_labels=None`, and forwards all four unchanged to `traverse_subgraph` (`:320-328`). Every keyword name matches on both sides, including `time_budget_s` against the flag's `--time-budget`. The coupling holds in the code, not only in the report. `hops` is the one value the CLI mirrors (`cli.py:165`, default 1) and it matches `export_subgraph`'s own default. `test_kgx_cli.py:202-219` pins the omission and `:221-259` pins the pass-through.

One consequence worth naming: `--max-nodes 0` and `--max-edges 0` are passed through (`args.max_nodes is not None`), and the traversal handles both as a cap hit with an explicit `empty_reason` rather than a crash (`traversal.py:485`, `:634-650`, and `test_kgx_traversal.py:137-167`). That is correct behaviour, not a defect.

## The single thing to fix first

F-4.4-02. It is the one finding where the export's own disclosure artifact positively asserts coverage the export does not have, and the fix is small: have `traverse_subgraph` record the labels it actually issued a query for and have `export_subgraph` put that list, not the requested one, in the manifest.
