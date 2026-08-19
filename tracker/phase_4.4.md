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

Status: in-progress
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

Status: in-progress
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

Status: in-progress
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

Status: in-review
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
- [x] No credential value appears in the command's output or in any log line it emits, on either the success or the failure path

Evidence, re-run by the lead rather than quoted from the builder:
- `src/system_03_search_agent/export/cli.py`, `tests/system_03_search_agent/export/test_kgx_cli.py`, and one line added to `pyproject.toml` registering `s3-kgx-export`
- `venv/bin/python -m pytest tests/system_03_search_agent/export/test_kgx_cli.py -q`: `26 passed in 0.15s`
- `venv/bin/ruff check src/system_03_search_agent/export/cli.py`: `All checks passed!`
- `git diff pyproject.toml`: one added line, nothing else
- `git diff --stat` on the premise gate: empty, the gate was not modified
- Credential criterion spot-checked at source rather than accepted on report: `test_kgx_cli.py:440` builds a fake failure carrying `postgresql://kg_reader:hunter2@127.0.0.1:15432/ncbi_kg` and asserts the password reaches neither stdout nor stderr
- Caps are passed through only when the flag is given, so `export_subgraph`'s own defaults win rather than being duplicated in a second place. That is the right call and it is now a coupling the judge should confirm holds once T-4.4-02 lands

History:
- 2026-08-19 lead: created, scoped at phase open
- 2026-08-19 builder-export-cli: claimed
- 2026-08-19 builder-export-cli: in-review, all five criteria reported holding, one with the caveat filed as F-4.4-01
- 2026-08-19 lead: verify commands re-run independently, all green. Not closed here: the judge closes, never the builder and never the dispatcher

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

Round 1, the adversary pass, filed 12: one critical, four reachable majors, seven minors. Full detail per finding is in `tracker/phase_4.4_adversary_report.md`. No finding carried a `Regression of:` line, so the phase did not stop mid-round. The blocking five are F-4.4-50 through F-4.4-54. The critical is restated here in full because it is the phase's central result and because it indicts this phase's own premise gate.

### F-4.4-50: The default invocation exports the wrong subgraph and the manifest certifies coverage that never happened

Status: confirmed
Raised by: adversary
Confirmed by: lead, independently reproduced
Severity: critical
Round: 1
Reachable: yes, it IS the default path. `s3-kgx-export NCBIGene:7157 --output-dir DIR` with no `--edge-label` flag reaches it
Ticket: T-4.4-02, with a second half in T-4.4-04
Location: `src/system_03_search_agent/export/traversal.py:522-534`, `src/system_03_search_agent/export/manifest.py:138-158`

What happened: with no explicit edge-label list, the traversal walks `EDGE_LABELS` in order and spends the entire shared node budget on the second label, `mentioned_in`, which is the highest-cardinality edge in the graph. It never reaches `gene_associated_with_condition`, which sits thirteenth. There is no fairness or round-robin across labels, so a single high-cardinality label starves every other one.

Reproduced independently by the lead against the live graph, seed `NCBIGene:7157`, `hops=1`, no `edge_labels` argument:

- 500 nodes, 499 edges
- every edge `biolink:mentioned_in`, every node an Article but the seed
- 0 of the 12 TP53 disease neighbours this phase pinned as its own ground truth

The second half is the disclosure. `manifest.json` lists all fourteen edge labels under `edge_labels`, a key whose own docstring defines it as the labels actually traversed. Exactly one was. So the export is not merely incomplete, it ships a manifest asserting coverage it does not have, which is worse than silence.

Why the premise gate did not catch it, which is the part worth keeping: five of the gate's six cases pass an explicit single-label list, and the sixth is a cap case that asserts only on truncation. The default invocation, the one every real user hits first, is exercised by no case at all. The gate's own coverage statement names "every edge label but `gene_associated_with_condition`" as a deliberate omission, and the critical lives exactly there. Stating a blind spot made this arguable in one reading; it did not make it safe. The gate is the lead's artifact, so this is a defect in the lead's work as much as the builder's.

History:
- 2026-08-19 adversary: filed, reproduced live
- 2026-08-19 lead: confirmed, reproduced independently with the numbers above. Blocks the merge

### Lead rulings on two disputed findings, 2026-08-19

The round 2 fix agent disputed two findings rather than complying with them, and flagged both for the lead instead of deciding unilaterally. That is the behaviour this harness wants: the round that finally closed build phase 4.3 also correctly disputed a finding. Both disputes are UPHELD.

F-4.4-10, the hop limit, upheld on placement. The judge asked for the hop limit to be reported; the fix agent reports it as its own explicit manifest field (`hop_limit_reached` plus `unexpanded_frontier_nodes`) rather than as a `truncation` entry, and it is right. A one-hop export normally ends with a non-empty frontier, so folding the hop limit into `truncation` would set `truncated: true` on almost every ordinary export and cost the flag its meaning. `truncated` means the export is smaller than what the caller asked for. The hop limit is part of what the caller asked for, not a shortfall against it. The criterion is satisfied: the limit is reported, and reported more usefully than the finding proposed.

F-4.4-11, the snapshot-version fallback, upheld. The fix agent disclosed the provenance with `graph_snapshot_version_source` rather than changing the hardcoded fallback value. Changing the value here alone would have made this module disagree with `cypher_query`, which reads the same variable with the same fallback, and a silent divergence between two modules reporting the same fact is worse than a documented fallback. Correct call.

### F-4.4-12: The CLI's error classification rests on a convention, not a declaration

Status: filed
Raised by: lead, while verifying the round 2 CLI fix
Severity: minor
Round: 2
Reachable: no, latent. Verified today: `graph_connection` raises no `ValueError` at all, so no credential-bearing message can reach the verbatim-printed branch, and the only `json.loads` in the package sits in a separate try block that routes a `JSONDecodeError` to the runtime path rather than the usage path
Ticket: T-4.4-05
Location: `src/system_03_search_agent/export/cli.py:312`

What happened: the round 2 fix classifies an input problem as "the exception was a `ValueError`". That is a better rule than the one it replaced, which classified by where the exception was caught, and it does generalize to validators added later. It is still a proxy rather than a declaration: it holds only while every `ValueError` reachable from this call path really is a caller-input problem. The property was verified true today rather than assumed, which is why this is latent and not a defect.

The trigger that would make it real: any module in the export path raising `ValueError` for a reason that is not bad caller input, for example a parse failure over graph data. Then a data failure would print verbatim and exit with the usage code. The durable form is an explicit exception type owned by this package, for example `ExportInputError`, so the classification is declared by the raiser rather than inferred by the catcher.

History:
- 2026-08-19 lead: filed after verifying the fix. Not a blocker under the merge bar; tracked with a named trigger

### F-4.4-01: The console-script criterion cannot be verified end to end, because nothing is installed

Status: filed
Raised by: builder-export-cli, confirmed reproducible by the lead
Severity: minor
Round: 0 (build, not review)
Ticket: T-4.4-05

What happened: T-4.4-05 requires the export to be invocable by its own console script. The entry point is registered in `pyproject.toml`, but neither `venv/bin/s3-kgx-export` nor `venv/bin/s3` exists, so no console script in this environment resolves from `$PATH`. Both invocations are verified only with `PYTHONPATH=src` set, which is what pytest's own `pythonpath` config supplies.

This is pre-existing and not caused by this phase: the same is already true of the `s3` command build phase 4.2 shipped, and the root cause is the already-tracked open item "Fix `pip install .`, fails outright on a `package-dir` mapping error", owned by build phase 6.1. Recorded here rather than fixed, because fixing packaging inside a build phase that does not own it is scope creep, and because a criterion that is only structurally satisfied should be visible rather than quietly ticked.

History:
- 2026-08-19 builder-export-cli: flagged in its report as out of its file scope
- 2026-08-19 lead: reproduced, `ls venv/bin/s3 venv/bin/s3-kgx-export` finds neither. Linked to the existing build phase 6.1 packaging item

## History

- 2026-08-19 lead: two builders dispatched in parallel on disjoint file scopes, Sonnet tier. One holds T-4.4-02, T-4.4-03 and T-4.4-04 serially, since traversal, serialization and manifest are one coupled build and parallel agents inside coupled code is the documented failure of build phase 4.2's rounds 1 to 4. The second holds T-4.4-05 alone, writing `export/cli.py` and the `pyproject.toml` entry against the signature the premise gate fixes, with `export_subgraph` monkeypatched so it needs neither the graph nor the other builder's modules. Both were told the premise gate file is read-only.
- 2026-08-19 lead: tunnel confirmed open, all three transports green on `python3 tracker/preflight.py`.
- 2026-08-19 lead: phase opened. Dependencies verified: Section 25 gives 4.4 no in-repo dependency. Preflight run, graph transport down, recorded above. Scope decided by the product owner, six tickets created, refinement moved from `tech_refine` to `refined`.
