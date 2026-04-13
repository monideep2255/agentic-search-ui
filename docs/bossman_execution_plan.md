# Bossman execution plan: System 1 data pipelines

Phase-by-phase implementation plan for the 6 NCBI ETL pipelines. Each phase is one bossman session with integrated skill chain and branch+MR workflow. Use `/bossman-mode --phase N` to execute.

Created: 2026-04-13. Based on System_1_data_engineering_plan.md.

---

## Skill chain (every phase follows this)

Each bossman phase integrates multiple skills in a fixed order. This is not optional.

```
PHASE START
  |
  +-- best-practices         session checklist (venv, postgres, CLAUDE.md, git status)
  +-- architecture-patterns   read before designing new modules
  +-- git branch              create phase/N.M-description from main
  |
DEVELOPMENT (bossman autonomous execution)
  |
  +-- python-code-standards   inline during code writing (type hints, docstrings, logging)
  +-- testing-standards       write tests alongside code (fixtures, no network, one assert per concept)
  +-- documentation-standards sentence case, no bold, no em dashes
  +-- decision-logging        log choices to DECISIONS.md as they happen
  +-- parallel-first          check independence, dispatch parallel builders
  +-- boil-the-lake           complete 100%, no shortcuts
  +-- attack-the-constraint   focus on what actually blocks progress
  |
PHASE END
  |
  +-- qa-gate                 6-phase quality gate (mandatory, no skips)
  |   +-- Phase 1: pytest -q
  |   +-- Phase 2: python-code-standards + testing-standards
  |   +-- Phase 3: eval-harness (BioLink, KGX, dangling edges, provenance)
  |   +-- Phase 4: schema + dependency-tracking
  |   +-- Phase 5: documentation-standards + docs-sync agent
  |   +-- Phase 6: verdict checklist
  |
  +-- release-workflow        chains qa-gate then ship
  +-- ship                    docs-sync agent -> commit -> push branch -> create MR
  |
MR REVIEW
  |
  +-- user reviews and approves MR
  +-- merge into main
  +-- delete phase branch
  +-- proceed to next phase
```

### Skills by role

| When | Skills active | Rules active | Agents |
|------|--------------|-------------|--------|
| Phase start | best-practices, architecture-patterns | file-protection, dependency-tracking | none |
| Development | python-code-standards, testing-standards, documentation-standards | parallel-first, boil-the-lake, attack-the-constraint, writing-style, decision-logging | bossman team (builders, judge, test writer) |
| Phase end | qa-gate (chains eval-harness), release-workflow, ship | git-workflow, file-protection | docs-sync, git-sync |
| Review | objective-review (optional, if user asks) | none | none |

### Skills suspended during bossman execution

| Skill | Why suspended |
|-------|--------------|
| socratic-questioning | Scope is defined. No Socratic questioning mid-build. |
| first-principles | Used during planning, not execution. |
| pause-before-acting | Plan is agreed. No need to pause and re-check. |
| preserve-your-thinking | Decisions were made during planning. Execute. |
| clarify-before-drafting | Scope is defined. |

---

## Branch + MR workflow

### Branch naming

`phase/N.M-short-description` where N.M matches the phase number.

| Phase | Branch name |
|-------|------------|
| 1.0 | `phase/1.0-schema-scaffolding` |
| 1.1 | `phase/1.1-shared-utilities` |
| 1.2 | `phase/1.2-gene-etl` |
| 1.3 | `phase/1.3-clinvar-etl` |
| 1.4 | `phase/1.4-medgen-etl` |
| 1.5 | `phase/1.5-merge-validation` |

### Per-phase git flow

```
1. git checkout main && git pull origin main
2. git checkout -b phase/N.M-description
3. [bossman builds, commits within branch]
4. qa-gate passes
5. git push -u origin phase/N.M-description
6. gh pr create (using .github/pull_request_template.md)
7. user reviews MR
8. merge into main, delete branch
9. start next phase from updated main
```

### Parallel phases (1.2 + 1.3 + 1.4)

When three pipelines run in parallel, each gets its own branch:
- `phase/1.2-gene-etl`
- `phase/1.3-clinvar-etl`
- `phase/1.4-medgen-etl`

Each branch is created from main (after Phase 1.1 merges). Each gets its own MR. Merge order does not matter since they touch different directories. Phase 1.5 starts after all three are merged.

---

## Execution map

```
Session 1: Phase 1.0  schema + project scaffolding        DONE (2026-04-13, merged ad77889)
    |  branch: phase/1.0-schema-scaffolding -> MR -> merge
    v
Session 2: Phase 1.1  shared utilities (6 modules)        NEXT
    |  branch: phase/1.1-shared-utilities -> MR -> merge
    v
Session 3: Phase 1.2 + 1.3 + 1.4  Gene + ClinVar + MedGen ETL (PARALLEL)
    |  three branches, three MRs, all merge into main
    v
Session 4: Phase 1.5  merge + cross-pipeline validation
    |  branch: phase/1.5-merge-validation -> MR -> merge
    v
Session 5: Phase 2.0  PubMed ETL pipeline
    |  branch: phase/2.0-pubmed-etl -> MR -> merge
    v
Session 6: Phase 2.1  Taxonomy ETL pipeline
    |  branch: phase/2.1-taxonomy-etl -> MR -> merge
    v
Session 7: Phase 2.2  PubMed + Taxonomy merge into existing graph
    |  branch: phase/2.2-literature-taxonomy-merge -> MR -> merge
    v
Session 8: Phase 3.0  SNP ETL pipeline (1.2B records, streaming)
    |  branch: phase/3.0-snp-etl -> MR -> merge
    v
Session 9: Phase 3.1  SNP-ClinVar merge + final 6-database merge
    |  branch: phase/3.1-final-merge -> MR -> merge
    v
Session 10: Phase 4.0  System 2: PostgreSQL + AGE loader
    |  branch: phase/4.0-age-loader -> MR -> merge
    v
Session 11: Phase 4.1  System 2: Cypher query validation
       branch: phase/4.1-cypher-validation -> MR -> merge
```

---

## Phase 1: core triangle (Gene + ClinVar + MedGen)

### Phase 1.0: schema + project scaffolding (DONE 2026-04-13)

Branch: `phase/1.0-schema-scaffolding` (merged, deleted)

Deliverables (all complete):
- `schema/biolink_ncbi.yaml`: LinkML schema with 10 node types, 14 predicates, provenance fields required
- `pyproject.toml`: project metadata, pytest config, Click entry points, package-dir mapping
- `tests/conftest.py`: 4 shared fixtures (sample_node_dict, sample_edge_dict, tmp_output_dir, schema_path)
- `tests/test_schema.py`: 5 tests validating schema structure

Pass criteria (all passed):
- [x] `linkml validate schema/biolink_ncbi.yaml` exits 0
- [x] All 10 node categories present
- [x] 14 predicates present (2 more than plan minimum: orthologous_to, cited_in)
- [x] Every node class requires: id, category, name, source, source_url
- [x] `pytest tests/test_schema.py` passes (5/5)

Decisions made:
- 14 predicates instead of 12: added orthologous_to and cited_in (needed by Gene and ClinVar pipelines)
- package-dir mapping in pyproject.toml: preserves hyphenated directory names while enabling Python imports

### Phase 1.1: shared utilities

Branch: `phase/1.1-shared-utilities`

Skills chain:
- best-practices (session checklist)
- architecture-patterns (idempotent steps, provenance as required param)
- python-code-standards (all 6 modules)
- testing-standards (6 test modules, mocked network)
- qa-gate (6 phases)
- ship (push branch, create MR)

Deliverables (all in `system-01-data-pipelines/shared/`):

| Module | Purpose | Reference pattern |
|--------|---------|-------------------|
| `config.py` | @dataclass PipelineConfig, loads .env, __post_init__ creates dirs | `reference/.../config.py:11-101` |
| `ftp_client.py` | download_ftp_file with cache-hit check, idempotent | `reference/.../utils.py:91-104` |
| `entrez_client.py` | configure_entrez, esearch with retry/backoff, esummary_batch | `reference/.../utils.py:35-86` |
| `biolink_mapper.py` | map_node(), map_edge(), category/predicate registries | New, enforces provenance |
| `kgx_exporter.py` | export_kgx writes nodes.tsv + edges.tsv | `reference/.../export.py` |
| `validator.py` | validate_no_dangling, validate_no_duplicates, validate_provenance | `reference/.../utils.py:109-138` |

Parallel builders: 3 (config+ftp, entrez+mapper, exporter+validator)

Pass criteria:
- [ ] `pytest tests/shared/` all pass (6 test modules)
- [ ] All 6 modules importable
- [ ] map_node returns dict with id, category, name, source, source_url (all non-empty)
- [ ] map_edge returns dict with subject, predicate, object, source, source_url (all non-empty)
- [ ] validate_provenance catches missing source_url
- [ ] ftp_client skips download on cache hit

### Phase 1.2: Gene ETL pipeline

Branch: `phase/1.2-gene-etl`

Skills chain: best-practices -> architecture-patterns -> python-code-standards -> testing-standards -> qa-gate -> ship

FTP source: `ftp.ncbi.nlm.nih.gov/gene/DATA/`

| File | Size | Produces |
|------|------|----------|
| gene_info.gz | ~2GB | Gene nodes + in_taxon edges + xrefs (HGNC, OMIM, Ensembl) |
| gene2go.gz | ~200MB | participates_in / actively_involved_in / located_in edges |
| gene2pubmed.gz | ~500MB | mentioned_in edges (Gene -> Article) |
| gene_refseq_uniprotkb_collab.gz | ~50MB | UniProt xrefs on Gene nodes |
| mim2gene_medgen | ~5MB | gene_associated_with_condition edges |
| gene_orthologs.gz | ~100MB | orthologous_to edges |

Modules to create (9):
- `gene/download.py`, `gene/parse_gene_info.py`, `gene/parse_gene2go.py`
- `gene/parse_gene2pubmed.py`, `gene/parse_mim2gene.py`, `gene/parse_refseq_uniprot.py`
- `gene/parse_orthologs.py`, `gene/pipeline.py`, `gene/cli.py`

Parallel builders: 3

Pass criteria:
- [ ] Gene nodes: id (NCBIGene:NNN), category (biolink:Gene), name, source, source_url, xrefs
- [ ] Correct GO predicates by aspect (P/F/C)
- [ ] Zero dangling edges, zero duplicates within Gene KGX
- [ ] 100% provenance coverage
- [ ] Pipeline runs with --tax-id 9606 for fast testing
- [ ] `pytest tests/gene/` passes

### Phase 1.3: ClinVar ETL pipeline

Branch: `phase/1.3-clinvar-etl`

Skills chain: best-practices -> architecture-patterns -> python-code-standards -> testing-standards -> qa-gate -> ship

FTP source: `ftp.ncbi.nlm.nih.gov/pub/clinvar/`

| File | Size | Produces |
|------|------|----------|
| ClinVarFullRelease.xml.gz | ~2GB | Variant nodes + is_sequence_variant_of + has_phenotype edges |
| variant_summary.txt.gz | ~500MB | Cross-validation source (tabular) |
| var_citations.txt | ~50MB | cited_in edges (Variant -> Article) |

Modules to create (6):
- `clinvar/download.py`, `clinvar/parse_xml.py` (streaming lxml.etree.iterparse)
- `clinvar/parse_variant_summary.py`, `clinvar/parse_var_citations.py`
- `clinvar/pipeline.py`, `clinvar/cli.py`

Parallel builders: 2

Pass criteria:
- [ ] Variant nodes: id (ClinVar:VCVNNN), category (biolink:SequenceVariant), clinical_significance, review_status
- [ ] is_sequence_variant_of edges to NCBIGene: IDs
- [ ] has_phenotype edges to MedGen CUI IDs
- [ ] Streaming parser, not DOM load (memory safe for 2GB)
- [ ] 100% provenance
- [ ] `pytest tests/clinvar/` passes

### Phase 1.4: MedGen ETL pipeline

Branch: `phase/1.4-medgen-etl`

Skills chain: best-practices -> architecture-patterns -> python-code-standards -> testing-standards -> qa-gate -> ship

FTP source: `ftp.ncbi.nlm.nih.gov/pub/medgen/`

| File | Size | Produces |
|------|------|----------|
| MedGenIDMappings.txt | ~50MB | Disease node xrefs (MONDO, OMIM, Orphanet, MeSH, SNOMED, HPO) |
| MGREL | ~20MB | subclass_of edges (disease hierarchy) |
| Names.RRF | ~30MB | Disease node names + synonyms |
| medgen_pubmed_lnk.txt | ~10MB | mentioned_in edges |
| MedGen_HPO_OMIM_Mapping.txt | ~5MB | Additional HPO/OMIM xrefs |

Modules to create (8):
- `medgen/download.py`, `medgen/parse_id_mappings.py`, `medgen/parse_names.py`
- `medgen/parse_mgrel.py`, `medgen/parse_pubmed_links.py`, `medgen/parse_hpo_omim.py`
- `medgen/pipeline.py`, `medgen/cli.py`

Parallel builders: 2

Pass criteria:
- [ ] Disease nodes: id (MONDO or MedGen CUI), category (biolink:Disease or biolink:PhenotypicFeature)
- [ ] MONDO canonical where available, MedGen CUI fallback
- [ ] xrefs include OMIM, Orphanet, MeSH, SNOMED, HPO
- [ ] subclass_of edges form DAG
- [ ] 100% provenance
- [ ] `pytest tests/medgen/` passes

### Phase 1.5: merge + cross-pipeline validation

Branch: `phase/1.5-merge-validation`

Skills chain: best-practices -> architecture-patterns -> eval-harness (full validation) -> qa-gate -> ship

Deliverables:
- `system-01-data-pipelines/shared/merger.py`: merge_kgx (concat, dedup, stub injection, validate)
- `system-01-data-pipelines/shared/merge_report.py`: statistics by category/predicate
- `mappings/gene_hgnc.sssom.tsv`, `mappings/clinvar_mondo.sssom.tsv`, `mappings/gene_go.sssom.tsv`
- `tests/integration/test_merge.py`, `tests/integration/test_cross_database_traversal.py`

Parallel builders: 2 (merger+report, SSSOM files)

Pass criteria:
- [ ] Zero dangling edges in merged output
- [ ] Zero duplicate node IDs
- [ ] Gene IDs from ClinVar edges exist in merged nodes
- [ ] MedGen CUIs from ClinVar edges exist (or stubbed)
- [ ] Expected counts: ~62K Gene (human), ~4.5M ClinVar, ~233K MedGen
- [ ] 100% provenance
- [ ] Merge report generated
- [ ] `pytest tests/integration/` passes

---

## Phase 2: literature + taxonomy (future sessions)

### Phase 2.0: PubMed ETL

Branch: `phase/2.0-pubmed-etl`
FTP: `ftp.ncbi.nlm.nih.gov/pubmed/baseline/` (~30GB compressed, 40M articles)
Nodes: biolink:Article with MeSH edges (has_mesh_annotation)
Linked to Gene via gene2pubmed (already downloaded in Phase 1.2)
Wall-clock: 4-8 hour download, run overnight

### Phase 2.1: Taxonomy ETL

Branch: `phase/2.1-taxonomy-etl`
FTP: `ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz` (~500MB)
Nodes: biolink:OrganismTaxon with subclass_of edges (full lineage tree, 2.9M organisms)

### Phase 2.2: 5-database merge

Branch: `phase/2.2-literature-taxonomy-merge`
Merge PubMed + Taxonomy into existing Phase 1 graph. Validate gene2pubmed edges resolve. Validate in_taxon edges resolve.

---

## Phase 3: variant depth (future sessions)

### Phase 3.0: SNP ETL (full dbSNP)

Branch: `phase/3.0-snp-etl`
FTP: `ftp.ncbi.nlm.nih.gov/snp/` (~100GB compressed, 1.2B records)
Per-chromosome VCF parsing, parallelized. Streaming into KGX or direct AGE load.
Wall-clock: 8-16 hour download + 4-12 hour parse

### Phase 3.1: SNP-ClinVar merge + final merge

Branch: `phase/3.1-final-merge`
Merge variants via rs ID. Combined ClinVar + dbSNP properties on matched variants.
All 6 databases in one graph.

---

## Phase 4: System 2 knowledge graph (future sessions)

### Phase 4.0: PostgreSQL + AGE loader

Branch: `phase/4.0-age-loader`
KGX TSV to AGE graph. Schema creation, node/edge loading, index creation.

### Phase 4.1: Cypher query validation

Branch: `phase/4.1-cypher-validation`
Run the 3 test queries from the plan against the loaded graph:
- Gene to variant traversal (BRCA1)
- Disease to gene traversal (phenylketonuria -> PAH)
- Gene to biological process (glucose metabolism genes)

---

## Reference files

| File | Read when |
|------|-----------|
| `docs/System_1_data_engineering_plan.md` | Before any pipeline work |
| `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/utils.py` | Building shared utilities |
| `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/config.py` | Building config |
| `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/assembly.py` | Building merger |
| `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/export.py` | Building KGX exporter |

## Skills reference

| Skill | When used | How |
|-------|-----------|-----|
| `best-practices` | Every phase start | Session checklist, scope discipline |
| `architecture-patterns` | Before designing modules | ETL patterns, provenance, idempotency |
| `python-code-standards` | During development + qa-gate Phase 2 | Type hints, docstrings, logging, error handling |
| `testing-standards` | During development + qa-gate Phase 2 | Fixtures, mocking, coverage targets |
| `documentation-standards` | During development + qa-gate Phase 5 | Sentence case, no bold, no em dashes |
| `eval-harness` | qa-gate Phase 3 | BioLink validation, dangling edges, provenance |
| `qa-gate` | Every phase end | 6-phase mandatory gate |
| `release-workflow` | Every phase end | Chains qa-gate then ship |
| `ship` | Final step | docs-sync, commit, push branch, create MR |
| `decision-logging` | Continuous during dev | Log choices to DECISIONS.md |
| `bossman-mode` | Wraps entire execution | Autonomous mode, suspended clarification |
| `objective-review` | Optional, user-requested | Critical feedback on deliverables |

---

## Agent teams (experimental)

Bossman mode uses Claude Code agent teams, not just sub-agents. Agent teams run as independent Claude Code instances with shared task lists and direct teammate communication.

Enabled via `.claude/settings.json`:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Display: tmux split panes (tmux is installed at `/usr/bin/tmux`). Each teammate gets its own pane.

### Team composition per phase

| Role | Count | Responsibility | Display |
|------|-------|---------------|---------|
| Lead (orchestrator) | 1 | Decomposes phase, spawns teammates, tracks progress | Main pane |
| Researcher | 1-N | FTP inventory, reference pattern lookup, API docs | tmux pane |
| Builder | 2-3 | Write code independently, one task per builder | tmux pane each |
| Judge | 1 | Reviews all builder output: functional, quality, plan adherence | tmux pane |
| Test writer | 1 | Unit tests, integration tests, fixture files | tmux pane |

### Sub-agents vs agent teams

| Aspect | Sub-agents (Agent tool) | Agent teams |
|--------|------------------------|-------------|
| Communication | Report back to main only | Teammates message each other |
| Coordination | Main agent manages all | Shared task list, self-coordination |
| Context | Fresh per dispatch | Full independent context window |
| Best for | Quick focused tasks | Complex parallel builds |
| Display | Inline results | tmux split panes |

Use agent teams for Phase 1.2+1.3+1.4 (three parallel ETL pipelines). Use sub-agents for simpler phases (1.0, 1.5).

---

## Testing strategy

Testing is integrated at every phase, not an afterthought.

### Per-phase testing

| When | What | Skill |
|------|------|-------|
| During development | Write tests alongside code, one test file per module | testing-standards |
| qa-gate Phase 1 | `pytest -q` all tests pass | qa-gate |
| qa-gate Phase 2 | Test quality: fixtures, no network, one assert per concept | testing-standards |
| qa-gate Phase 3 | BioLink validation, dangling edges = 0, provenance = 100% | eval-harness |
| Phase 1.5 | Integration tests: cross-pipeline traversal, merge correctness | custom |

### Test file structure

```
tests/
  conftest.py                          shared fixtures
  test_schema.py                       schema validation
  shared/
    test_config.py                     config loading
    test_ftp_client.py                 mocked FTP, cache-hit
    test_entrez_client.py              mocked Entrez, retry/backoff
    test_biolink_mapper.py             node/edge mapping, provenance
    test_kgx_exporter.py              TSV output, column order
    test_validator.py                  dangling edges, duplicates
  gene/
    test_parse_gene_info.py            small fixture (10 rows)
    test_parse_gene2go.py              GO aspect mapping
    test_gene_pipeline.py              end-to-end with mocked downloads
  clinvar/
    test_parse_xml.py                  small fixture XML (5 VCV records)
    test_parse_variant_summary.py      tabular parsing
    test_clinvar_pipeline.py           end-to-end
  medgen/
    test_parse_id_mappings.py          MONDO resolution
    test_parse_mgrel.py                hierarchy DAG check
    test_medgen_pipeline.py            end-to-end
  integration/
    test_merge.py                      3-way merge correctness
    test_cross_database_traversal.py   Gene -> ClinVar -> MedGen path
  fixtures/
    gene_info_10rows.tsv               small fixtures for fast tests
    clinvar_5records.xml
    medgen_mappings_sample.txt
```

### Testing rules

- Tests do not hit the network unless marked `@pytest.mark.integration`
- One assertion per test concept
- Fixtures for shared setup, never copy-paste
- For new code: there must be a test next to it
- Coverage target: 70%+ on shared utilities, parsers, and mappers

---

## Key decisions

1. Parsers are separate files per FTP source, not monoliths. Enables parallel builders.
2. Cross-database edges dangle within single-pipeline KGX. Merge phase enforces zero dangling.
3. ClinVar uses streaming XML (iterparse), not DOM. Memory safe for 2GB.
4. MONDO is canonical disease ID, MedGen CUI fallback.
5. No Entrez API in Phase 1. All data from FTP bulk files.
6. Branch-per-phase with MR review before merging to main.
7. Skill chain is fixed: best-practices -> architecture-patterns -> [dev with standards] -> qa-gate -> release-workflow -> ship.
8. Agent teams (experimental) for parallel phase execution, tmux split panes for visibility.
9. Testing integrated at every phase via testing-standards + qa-gate + eval-harness.
10. 56 total files across Phase 1 (37 code + 19 test).
