# Build phase 4.4: KGX export

Branch: `phase/4.4-kgx-export`
Spec: `requirements/Technical_specification.md` Section 25 (the 4.4 row), Section 1.1 (the six delivery surfaces), `requirements/PRD.md` "Delivery formats"
Depends on: nothing in this repository. Layer 1 access already exists.
Opened: 2026-08-19

## What this phase delivers, and why the scope needed a decision first

Section 25 scopes 4.4 in two negative sentences and nothing else: "Export utility scoped to the existing Hetzner graph, a batch job, not a live adapter", and the PRD's "scoped to the existing Hetzner graph, not a full graph export". Section 6 declines to restate the design. So what gets exported, how the subset is chosen, and what invokes it were all open at phase open.

Product-owner decision, 2026-08-19: a query-scoped subgraph export. The utility takes a seed set of CURIEs, walks a bounded number of hops over Layer 1, and writes BioLink-compliant `nodes.tsv` plus `edges.tsv` plus a manifest. It is not a snapshot dump of the whole graph, which the architecture brainstorming sizes at roughly 144 GB and describes as already produced upstream by the System 1 and System 2 merge pipeline.

Two alternatives were considered and not chosen: serving the upstream full snapshot as a hosted download (little code here, and the hosting is infrastructure this repository does not own), and deferring 4.4 in favor of 4.6 or 4.7.

### The rule conflict this phase has to resolve before it writes code

`CLAUDE.md`'s file-protection rule says: "Don't add System 1/2 ETL code (bulk parsers, KGX exporters, AGE loaders) -- this repo is System 3 only." Build phase 4.4 asks for a KGX exporter. The two cannot both stand as written.

The distinction that resolves it, and which the rule's current text does not draw: System 1 and System 2 write KGX *into* the graph from source NCBI data, which is ETL and stays out of this repository. Build phase 4.4 reads a scoped subgraph *out* of the already-built graph as one of the six delivery surfaces the locked PRD requires. The rule is amended to state that distinction rather than crossed silently. T-4.4-06 owns the amendment, and it lands before any export code, not after.

## Blocked at open: the Layer 1 transport

`python3 tracker/preflight.py` on 2026-08-19 returned `product-model ok`, `harness-model ok`, `graph skipped` (unset in the process environment). Re-probed with the real values loaded from `.env`: `graph down, TCP 15432: Connection refused`. That port is the SSH local forward `ssh -N -L 15432:127.0.0.1:5432 root@46.225.128.133` recorded in `tracker/phase_2.1.md`, and nothing has opened it in this session. Port 22 on the host answers, so the forward is openable from here with product-owner approval.

Every ticket below except T-4.4-06 reads Layer 1. None of them may be dispatched while the probe reads `down`, per `docs/build/Build_workflow_cadence.md` stage 4.

## Tickets

### T-4.4-01: Premise gate for the KGX export

Status: in-review
Refine: refined
Branch: phase/4.4-kgx-export
Depends on: T-4.4-06
Spec: Technical_specification.md Section 25 (4.4), `docs/build/Build_workflow_cadence.md` stage 5

This phase's deliverable is not model-generated, so the gate does not carry stage 5's no-mocking-the-model requirement. It carries every other property, because the failure this phase can actually ship is a file that is well-formed and wrong: correct TSV, correct column headers, and a subgraph that is not the one the seed names.

Acceptance criteria:
- [ ] The gate runs against the live graph, not a fixture, and skips rather than passes when the transport is unreachable
- [ ] Ground truth is read from the live graph and pinned in the test file, so "correct" is checkable rather than plausible
- [ ] The gate asserts on the content of the export, that the seed CURIE's real Layer 1 neighbours appear as rows with their real categories and predicates, not that a file exists or that a row count is greater than zero
- [ ] The gate exercises a seed whose neighbourhood exceeds the export's node cap, and asserts the manifest discloses the truncation
- [ ] The gate exercises a seed CURIE that resolves to no vertex, and asserts an empty export with an explicit manifest reason rather than a crash or a silent zero-row file
- [ ] The gate states, in its own file, which shapes of export it exercises and which it deliberately omits
- [x] The gate has been SEEN FAILING before any other ticket in this phase opens

Evidence:
- `tests/system_03_search_agent/export/test_kgx_export_premise.py`, six cases
- Seen failing: `venv/bin/python -m pytest tests/system_03_search_agent/export/ -q` returns `6 failed in 0.15s`, every one on `ModuleNotFoundError: No module named 'system_03_search_agent.export'`. It FAILED rather than SKIPPED, which is the load-bearing part: the tunnel was open and `_graph_is_reachable()` returned True, so the live guard was exercised and the failures are real
- Ground truth read live 2026-08-19 over the tunnel: TP53 (`NCBIGene:7157`) carries exactly 12 `gene_associated_with_condition` edges to Disease vertices, pinned as `TP53_DISEASE_CURIES`, returned in 2.3 seconds
- Traversal cost measured while pinning that ground truth, and it shaped the design: an unscoped `MATCH (g:Gene {id})-[r]->(n) LIMIT 10` off BRCA1 takes 23.2 seconds and the reverse direction exceeds a 25 second budget, while the same hop scoped to one edge label returns in 2.3 seconds. The exporter traverses per edge label for this reason, not for tidiness
- Coverage stated in the gate's own module docstring. It omits multi-hop traversal, the other thirteen edge labels, non-Gene seeds, and concurrent exports

History:
- 2026-08-19 lead: created, scoped at phase open
- 2026-08-19 lead: claimed
- 2026-08-19 lead: in-review, gate written and seen failing 6 of 6 against a reachable graph. Unblocks T-4.4-02 through T-4.4-05

### T-4.4-02: Bounded subgraph traversal over Layer 1

Status: todo
Refine: refined
Branch: phase/4.4-kgx-export
Depends on: T-4.4-01
Spec: Technical_specification.md Section 6.1, `.claude/rules/tool-call-budgets.md`, `.claude/rules/production-standards.md`
Files: `src/system_03_search_agent/export/__init__.py`, `src/system_03_search_agent/export/traversal.py`

Acceptance criteria:
- [ ] The traversal reads Layer 1 through the existing `graph_connection.execute_cypher` read-only path, and adds no second connection factory and no second credential
- [ ] Every value reaching the Cypher payload is bound through the existing PREPARE and EXECUTE mechanism. No f-string and no `.format()` appears in any query text
- [ ] Every relationship pattern in a generated query carries an explicit edge label from `graph_schema_constants.EDGE_LABELS`
- [ ] A traversal that would exceed its node cap, edge cap, or hop limit stops at the cap and reports which cap it hit, rather than returning a truncated result that looks complete
- [ ] Each individual graph call returns or errors within the 30 second `cypher_query` budget, and a traversal that exhausts its wall-clock budget returns the partial subgraph with the exhaustion recorded, never a hang
- [ ] A seed CURIE that matches no vertex returns an empty subgraph with a reason, not an exception
- [ ] No variable-length relationship pattern is ever emitted, per the F-2.1-C15 bound already enforced in `validate_cypher`

Evidence:
- (filled at close)

History:
- 2026-08-19 lead: created, scoped at phase open

### T-4.4-03: KGX serialization

Status: todo
Refine: refined
Branch: phase/4.4-kgx-export
Depends on: T-4.4-02
Spec: `requirements/PRD.md` "Delivery formats", the column contract in `reference/agentic-search-data-engineering/system-01-data-pipelines/shared/kgx_exporter.py`
Files: `src/system_03_search_agent/export/kgx.py`

Acceptance criteria:
- [ ] `nodes.tsv` carries `id`, `category`, `name`, `source`, `source_url` as its first five columns, in that order, before any additional column
- [ ] `edges.tsv` carries `subject`, `predicate`, `object`, `source`, `source_url`, `knowledge_level`, `agent_type` as its first seven columns, in that order
- [ ] Additional columns follow the required ones sorted alphabetically, and a row missing a column is written as an empty field rather than a shifted row
- [ ] A list-valued or tuple-valued property is pipe-joined, matching the upstream reader that consumes these files
- [ ] Every `source_url` written is produced by the existing `cypher_provenance` host-pinned builders, and a row whose URL cannot be built is written with an empty `source_url` and counted in the manifest rather than given a guessed URL
- [ ] A property value containing a tab, a newline, or a quote round-trips through a standard TSV reader without shifting or splitting a row
- [ ] Files are written UTF-8 with a header row, and an export of zero rows still writes both files with their headers

Evidence:
- (filled at close)

History:
- 2026-08-19 lead: created, scoped at phase open

### T-4.4-04: Manifest, truncation disclosure, and the Layer 1 limitation

Status: todo
Refine: refined
Branch: phase/4.4-kgx-export
Depends on: T-4.4-03
Spec: `docs/architecture/System_3_architecture_brainstorming.md` (the stated Layer 1 limitation), `.claude/rules/production-standards.md`
Files: `src/system_03_search_agent/export/manifest.py`

The disclosure criteria are not decoration. Silent truncation is a defect class this project has now filed four times (F-3.3-A-12, F-4.0-A-12, F-3.5-10, F-2.2-06), and the product owner's standing rule from 2026-08-15 is that if the system drops or shortens anything, it discloses that it did.

Acceptance criteria:
- [ ] Every export writes a `manifest.json` alongside the two TSV files
- [ ] The manifest records the seed CURIEs, the hop limit, every cap value, the node and edge counts written, the graph snapshot version, and the export timestamp
- [ ] An export that hit any cap records which cap, at what value, and that the subgraph is therefore incomplete. An export that hit none records that explicitly rather than by omission
- [ ] The manifest states that the export covers Layer 1 only, and that Layer 2 and Layer 3 data are fetched live at query time and are not present
- [ ] The count of rows written with an empty `source_url` appears in the manifest
- [ ] The same limitation and truncation statements appear on the command's own output, not only inside the manifest file

Evidence:
- (filled at close)

History:
- 2026-08-19 lead: created, scoped at phase open

### T-4.4-05: The batch entry point

Status: todo
Refine: refined
Branch: phase/4.4-kgx-export
Depends on: T-4.4-04
Spec: Technical_specification.md Section 25 (4.4, "a batch job, not a live adapter")
Files: `src/system_03_search_agent/export/cli.py`, `pyproject.toml`

It gets its own console script rather than a subcommand of `s3`. Build phase 4.2 scoped the CLI as a thin HTTP client over the REST surface and explicitly not a second path to data, and a direct-graph batch job inside it would be exactly that second path.

Acceptance criteria:
- [ ] The export is invoked by its own console script and by `python -m`, and neither invocation routes through the REST API or the agent loop
- [ ] The command accepts one or more seed CURIEs, a hop limit, an output directory, and cap overrides, and rejects an unparseable CURIE with an actionable message naming the expected shape
- [ ] The command exits non-zero when the graph is unreachable, with a message naming the transport rather than a stack trace
- [ ] The command writes no file outside the output directory it was given
- [ ] No credential value appears in the command's output or in any log line it emits, on either the success or the failure path

Evidence:
- (filled at close)

History:
- 2026-08-19 lead: created, scoped at phase open

### T-4.4-06: Amend the file-protection rule

Status: in-review
Refine: refined
Branch: phase/4.4-kgx-export
Depends on: nothing
Spec: `CLAUDE.md` file-protection rule, `.claude/rules/file-protection.md`
Files: `.claude/rules/file-protection.md`, `DECISIONS.md`

This is the only ticket in the phase that does not read Layer 1, so it is the only one runnable while the transport is down. It lands before any export code.

Acceptance criteria:
- [ ] The rule distinguishes writing KGX into the graph, which stays out of this repository, from reading a scoped subgraph out of it as a delivery surface, which build phase 4.4 owns
- [ ] The rule still forbids bulk source-data parsers and AGE loaders in this repository, in the same words as before
- [ ] `DECISIONS.md` carries a dated row recording the 4.4 scope decision, the two alternatives rejected, and the reason
- [x] The change ships as its own commit on the phase branch, since it touches `.claude/`

Evidence:
- `ade54c9` on `phase/4.4-kgx-export`, touching `.claude/rules/file-protection.md` and `DECISIONS.md` only
- `.claude/rules/file-protection.md`: the third bullet now reads "bulk source-data parsers, AGE loaders, or anything that writes KGX into the graph", and a new section states the direction-of-data-flow line
- `DECISIONS.md`: the 2026-08-19 row records the scope decision, the three rejected alternatives, and why the rule had to be amended rather than crossed
- `python3 tracker/check_doc_drift.py --check`: 10 facts computed, 0 stale, 0 structural
- `python3 tracker/render_board.py --check`: ok, 34 phases, flags 77

History:
- 2026-08-19 lead: created, scoped at phase open
- 2026-08-19 lead: claimed, the one ticket in this phase that does not read Layer 1
- 2026-08-19 lead: in-review, rule amended and decision logged in `ade54c9`. Awaiting the judge round, which runs with the rest of the phase

## Findings

None yet.

## History

- 2026-08-19 lead: phase opened. Dependencies verified: Section 25 gives 4.4 no in-repo dependency. Preflight run, graph transport down, recorded above. Scope decided by the product owner, six tickets created, refinement moved from `tech_refine` to `refined`.
