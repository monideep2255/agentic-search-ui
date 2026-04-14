# Bossman execution plan: System 1 data pipelines

Phase-by-phase implementation plan for the 6 NCBI ETL pipelines. Each phase is one bossman session with integrated skill chain and branch+MR workflow. Use `/bossman-mode --phase N` to execute.

Created: 2026-04-13. Based on System_1_data_engineering_plan.md.

---

## End product

When all 11 phases are complete, this repo produces:

1. 6 ETL pipelines that download NCBI bulk data and output BioLink-compliant KGX files (nodes.tsv + edges.tsv per database)
2. A merged knowledge graph in PostgreSQL + Apache AGE, queryable via openCypher
3. Every node and edge traceable back to its NCBI source record (provenance on 100%)

### Graph scale

| Pipeline | Nodes | Edges | KGX size |
|----------|-------|-------|----------|
| Gene (all organisms) | ~94M | ~134M | ~40-60GB |
| ClinVar | ~4.5M | ~9M | ~3-5GB |
| MedGen | ~233K | ~500K | ~200MB |
| PubMed | ~40M | ~40M+ | ~30-50GB |
| Taxonomy | ~2.9M | ~2.9M | ~1-2GB |
| SNP (full dbSNP) | ~1.2B | ~1.2B+ | ~200-400GB |
| Total | ~1.4B | ~1.5B+ | ~300-500GB |

### What you can query after Phase 4.1

- "Find all pathogenic variants in BRCA1" (Gene -> ClinVar)
- "What diseases are associated with HNF1A?" (Gene -> ClinVar -> MedGen)
- "What publications mention BRCA1 and breast cancer?" (Gene -> PubMed, MeSH filter)
- "What human genes are involved in glucose metabolism?" (Taxonomy + Gene -> GO)
- "What is the European allele frequency of rs328?" (dbSNP population frequencies)
- "What is the mutation spectrum for HNF1A?" (full dbSNP aggregate variant stats)

This is System 1 + System 2. System 3 (search agent, FastAPI, LangGraph, UI) lives in a separate repo and consumes this graph.

---

## Timeline estimate

### What the phases produce (code vs data)

Each bossman phase produces code only: parsers, pipeline orchestrators, shared utilities, and tests. Tests use small inline fixtures, not real NCBI data. No data is downloaded during bossman sessions.

The actual FTP downloads happen when you run the pipelines for the first time (e.g. `gene-etl`, `clinvar-etl`, `medgen-etl`). Running the pipelines is a separate step from building them. The "wall-clock time" table below estimates how long each download and processing run takes.

### Data validation gates (run after each phase group)

After each group of pipeline phases is built and merged, run the pipelines on real data before building the next group. This catches data format surprises early instead of discovering them after all code is written.

| Gate | Run after | Commands | What to verify |
|------|-----------|----------|----------------|
| Gate 1 | Phase 1.5 | `medgen-etl`, `gene-etl --tax-id 9606`, `clinvar-etl` | KGX files exist in `/export/home/chakrabortim2/data/kgx/{gene,clinvar,medgen}/`, row counts are reasonable, no parse errors |
| Gate 2 | Phase 2.2 | `pubmed-etl` (overnight), `taxonomy-etl` | PubMed and Taxonomy KGX files, 5-database merge report looks sane |
| Gate 3 | Phase 3.1 | `snp-etl` (overnight) | dbSNP KGX files, final 6-database merge, check disk usage |
| Gate 4 | Phase 4.1 | Run Cypher test queries | Graph responds correctly to the 3 test queries from the plan |

Gate 1 is the next step. Run the three core triangle pipelines on real data, inspect the KGX output, then proceed to Phase 2.

### Coding time (bossman sessions)

| Phase | Session | What | Status |
|-------|---------|------|--------|
| 1.0 | 1 | Schema + scaffolding | DONE (2026-04-13) |
| 1.1 | 2 | Shared utilities (6 modules) | DONE (2026-04-14) |
| 1.2+1.3+1.4 | 3 | Gene + ClinVar + MedGen ETL (parallel) | DONE (2026-04-14) |
| 1.5 | 4 | Merge + validation | DONE (2026-04-14) |
| Gate 1 | - | Run pipelines on real data | NEXT |
| 2.0 | 5 | PubMed ETL | Pending (after Gate 1) |
| 2.1 | 6 | Taxonomy ETL | Pending |
| 2.2 | 7 | 5-database merge | Pending |
| Gate 2 | - | Run PubMed + Taxonomy on real data | Pending |
| 3.0 | 8 | SNP ETL (1.2B records) | Pending |
| 3.1 | 9 | SNP-ClinVar merge + final merge | Pending |
| Gate 3 | - | Run dbSNP on real data | Pending |
| 4.0 | 10 | PostgreSQL + AGE loader | Pending |
| 4.1 | 11 | Cypher query validation | Pending |
| Gate 4 | - | Run Cypher test queries | Pending |

### Wall-clock time (downloads and processing that can't be compressed)

| Task | Wall-clock | When to run |
|------|-----------|-------------|
| MedGen download (115MB) | 5 min | Gate 1 |
| Gene FTP download (3GB) | 30-60 min | Gate 1 |
| ClinVar download (500MB) | 20-30 min | Gate 1 |
| PubMed baseline download (30GB) | 4-8 hours | Gate 2, start overnight |
| Taxonomy download (500MB) | 10 min | Gate 2 |
| dbSNP full download (100GB) | 8-16 hours | Gate 3, start overnight |
| dbSNP VCF parsing (1.2B records) | 4-12 hours | Gate 3, after download |
| AGE graph loading (1.4B nodes) | 6-24 hours | Gate 4, start overnight |
| Node normalization (6 subgraphs) | 2-4 hours | Gate 3, during merge |

### Realistic calendar

| Week | Phases | Milestone | Status |
|------|--------|-----------|--------|
| Week 1 | 1.0-1.5 + Gate 1 | Core triangle code complete, run on real data | Code DONE (2026-04-14). Gate 1 NEXT. |
| Week 2 | 2.0-2.2 + Gate 2 | Literature + taxonomy added, 5 databases merged | Pending |
| Week 3 | 3.0-3.1 + Gate 3 | Full dbSNP, all 6 databases, 1.4B nodes merged | Pending |
| Week 4 | 4.0-4.1 + Gate 4 | Graph loaded in PostgreSQL + AGE, Cypher queries working | Pending |

Phase 1 code completed in a single session (2026-04-14). Gate 1 (run pipelines on real data) is the next step before building Phase 2.

### Disk budget (434GB available on /export as of 2026-04-14)

| After gate | Cumulative disk usage | Headroom |
|------------|----------------------|----------|
| Gate 1 | ~10-15GB (human-only Gene + ClinVar + MedGen) | ~420GB |
| Gate 2 | ~50-70GB (add PubMed + Taxonomy) | ~365GB |
| Gate 3 | ~300-500GB (add full dbSNP) | Tight: process incrementally |
| Gate 4 | AGE database ~200-300GB (replaces KGX intermediates) | Delete KGX after loading |

Full dbSNP (Phase 3) is the disk constraint. Strategy: load each pipeline into AGE incrementally, delete KGX intermediates after loading.

### Data storage

All data lives on local disk (`/export`), not the NFS home directory (which is only 20GB). Paths are configured in `.env`:

| Path | What lives here | Gitignored |
|------|----------------|------------|
| `/export/home/chakrabortim2/data/ftp_cache/` | Raw FTP downloads (gene_info.gz, ClinVar XML, etc.). Kept for re-runs. | Yes |
| `/export/home/chakrabortim2/data/raw/` | Intermediate parsed data | Yes |
| `/export/home/chakrabortim2/data/kgx/` | KGX output (nodes.tsv + edges.tsv per database). Deleted after AGE load. | Yes |
| PostgreSQL data directory | AGE graph database (final storage) | N/A (system) |

Disk: `/export` is local LVM volume (`/dev/mapper/usrvg1-export`), 4.3TB total, ~434GB free as of 2026-04-14. Enough for Gates 1-2. Gate 3 (full dbSNP) requires incremental processing.

The repo itself contains only code, schema, tests, and docs. No data files are committed to git.

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

| Phase | Branch name | Status |
|-------|------------|--------|
| 1.0 | `phase/1.0-schema-scaffolding` | Merged, deleted |
| 1.1 | `phase/1.1-shared-utilities` | Merged, deleted |
| 1.2+1.3+1.4 | `phase/1.2-1.4-core-triangle-etl` | Merged, deleted (combined) |
| 1.5 | `phase/1.5-merge-validation` | Merged, deleted |

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

The original plan called for three separate branches, but in practice these were combined into a single branch (`phase/1.2-1.4-core-triangle-etl`) since all three pipelines touch different directories with no conflicts. One PR, one merge. Faster to review and ship.

---

## Execution map

```
Session 1: Phase 1.0  schema + project scaffolding        DONE (2026-04-13, merged ad77889)
    |  branch: phase/1.0-schema-scaffolding -> MR -> merge
    v
Session 2: Phase 1.1  shared utilities (6 modules)        DONE (2026-04-14, branch pushed e108a0c)
    |  branch: phase/1.1-shared-utilities -> MR -> merge
    v
Session 3: Phase 1.2 + 1.3 + 1.4  Gene + ClinVar + MedGen ETL              DONE (2026-04-14, combined branch)
    |  branch: phase/1.2-1.4-core-triangle-etl -> MR -> merge
    v
Session 4: Phase 1.5  merge + cross-pipeline validation                    DONE (2026-04-14)
    |  branch: phase/1.5-merge-validation -> MR -> merge
    v
--- GATE 1: run pipelines on real data ---                                 NEXT
    |  medgen-etl (~5 min)
    |  gene-etl --tax-id 9606 (~30-60 min)
    |  clinvar-etl (~20-30 min)
    |  verify KGX output, fix any parse errors before proceeding
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
--- GATE 2: run PubMed + Taxonomy on real data ---
    |  pubmed-etl (4-8 hours, start overnight)
    |  taxonomy-etl (~10 min)
    |  verify 5-database merge report
    v
Session 8: Phase 3.0  SNP ETL pipeline (1.2B records, streaming)
    |  branch: phase/3.0-snp-etl -> MR -> merge
    v
Session 9: Phase 3.1  SNP-ClinVar merge + final 6-database merge
    |  branch: phase/3.1-final-merge -> MR -> merge
    v
--- GATE 3: run dbSNP on real data ---
    |  snp-etl (8-16 hour download + 4-12 hour parse, start overnight)
    |  verify final 6-database merge, check disk usage
    v
Session 10: Phase 4.0  System 2: PostgreSQL + AGE loader
    |  branch: phase/4.0-age-loader -> MR -> merge
    v
Session 11: Phase 4.1  System 2: Cypher query validation
    |  branch: phase/4.1-cypher-validation -> MR -> merge
    v
--- GATE 4: run Cypher test queries ---
    |  verify 3 test queries return correct results
    |  system complete
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

### Phase 1.1: shared utilities (DONE 2026-04-14)

Branch: `phase/1.1-shared-utilities` (merged, deleted)

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

Pass criteria (all passed):
- [x] `pytest tests/shared/` all pass (82 tests across 6 modules)
- [x] All 6 modules importable
- [x] map_node returns dict with id, category, name, source, source_url (all non-empty)
- [x] map_edge returns dict with subject, predicate, object, source, source_url (all non-empty)
- [x] validate_provenance catches missing source_url
- [x] ftp_client skips download on cache hit

### Phase 1.2: Gene ETL pipeline (DONE 2026-04-14)

Branch: `phase/1.2-1.4-core-triangle-etl` (combined branch with 1.3 and 1.4, merged, deleted)

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

Pass criteria (all passed):
- [x] Gene nodes: id (NCBIGene:NNN), category (biolink:Gene), name, source, source_url, xrefs
- [x] Correct GO predicates by aspect (P/F/C)
- [x] Zero dangling edges, zero duplicates within Gene KGX
- [x] 100% provenance coverage
- [x] Pipeline runs with --tax-id 9606 for fast testing
- [x] `pytest tests/gene/` passes (10 tests)

### Phase 1.3: ClinVar ETL pipeline (DONE 2026-04-14)

Branch: `phase/1.2-1.4-core-triangle-etl` (combined branch, merged, deleted)

Skills chain: best-practices -> architecture-patterns -> python-code-standards -> testing-standards -> qa-gate -> ship

FTP source: `ftp.ncbi.nlm.nih.gov/pub/clinvar/`

| File | Size | Produces |
|------|------|----------|
| variant_summary.txt.gz | ~500MB | Variant nodes + is_sequence_variant_of + has_phenotype edges (primary source) |
| var_citations.txt | ~50MB | cited_in edges (Variant -> Article) |

Decision: used variant_summary.txt.gz (tabular) as the primary source instead of ClinVarFullRelease.xml.gz. Simpler, faster, sufficient for all needed fields. XML parser was unnecessary complexity.

Modules created (5):
- `clinvar/download.py`, `clinvar/parse_variant_summary.py`, `clinvar/parse_var_citations.py`
- `clinvar/pipeline.py`, `clinvar/cli.py`

Pass criteria (all passed):
- [x] Variant nodes: id (ClinVar:NNN), category (biolink:SequenceVariant), clinical_significance, review_status
- [x] is_sequence_variant_of edges to NCBIGene: IDs
- [x] has_phenotype edges to MedGen CUI IDs
- [x] Streaming line-by-line parser (memory safe for 500MB)
- [x] 100% provenance
- [x] `pytest tests/clinvar/` passes (16 tests)

### Phase 1.4: MedGen ETL pipeline (DONE 2026-04-14)

Branch: `phase/1.2-1.4-core-triangle-etl` (combined branch, merged, deleted)

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

Pass criteria (all passed):
- [x] Disease nodes: id (MONDO or MedGen CUI), category (biolink:Disease or biolink:PhenotypicFeature)
- [x] MONDO canonical where available, MedGen CUI fallback
- [x] xrefs include OMIM, Orphanet, MeSH, SNOMED, HPO
- [x] subclass_of edges form DAG
- [x] 100% provenance
- [x] `pytest tests/medgen/` passes (18 tests)

Decision: parse_id_mappings returns a cui_to_canonical_id map alongside nodes. pipeline.py rewrites all edge CUI references to canonical IDs (MONDO where promoted), preventing dangling edges within MedGen.

### Phase 1.5: merge + cross-pipeline validation (DONE 2026-04-14)

Branch: `phase/1.5-merge-validation` (merged, deleted)

Skills chain: best-practices -> architecture-patterns -> eval-harness (full validation) -> qa-gate -> ship

Deliverables:
- `system-01-data-pipelines/shared/merger.py`: merge_kgx (concat, dedup, stub injection, validate)
- `system-01-data-pipelines/shared/merge_report.py`: statistics by category/predicate
- `mappings/gene_hgnc.sssom.tsv`, `mappings/clinvar_mondo.sssom.tsv`, `mappings/gene_go.sssom.tsv`
- `tests/integration/test_merge.py`, `tests/integration/test_cross_database_traversal.py`

Parallel builders: 2 (merger+report, SSSOM files)

Pass criteria (all passed):
- [x] Zero dangling edges in merged output (stubs injected for cross-pipeline refs)
- [x] Zero duplicate node IDs
- [x] Gene IDs from ClinVar edges exist in merged nodes (or stubbed)
- [x] MedGen CUIs from ClinVar edges exist (or stubbed)
- [x] Expected counts to be verified at Gate 1 with real data
- [x] 100% provenance
- [x] Merge report generated
- [x] `pytest tests/integration/` passes (14 tests)

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
  conftest.py                          shared fixtures (4 fixtures)
  test_schema.py                       schema validation (5 tests)
  shared/
    conftest.py                        sys.path setup for shared imports
    test_config.py                     config loading (8 tests)
    test_ftp_client.py                 mocked FTP, cache-hit (8 tests)
    test_entrez_client.py              mocked Entrez, retry/backoff (14 tests)
    test_biolink_mapper.py             node/edge mapping, provenance (22 tests)
    test_kgx_exporter.py              TSV output, column order (10 tests)
    test_validator.py                  dangling edges, duplicates (20 tests)
  gene/
    test_gene_pipeline.py              all parsers + end-to-end (10 tests)
  clinvar/
    test_clinvar_pipeline.py           variant_summary, citations, end-to-end (16 tests)
  medgen/
    test_medgen_pipeline.py            id_mappings, names, mgrel, end-to-end (18 tests)
  integration/
    conftest.py                        sys.path setup
    test_merge.py                      merge dedup, stubs, validation (9 tests)
    test_cross_database_traversal.py   Gene -> ClinVar -> MedGen triangle (5 tests)
```

All tests use inline fixtures (no separate fixture files). Total: 146 tests, all passing.

### Testing rules

- Tests do not hit the network unless marked `@pytest.mark.integration`
- One assertion per test concept
- Fixtures for shared setup, never copy-paste
- For new code: there must be a test next to it
- Coverage target: 70%+ on shared utilities, parsers, and mappers

---

## Key decisions

1. Parsers are separate files per FTP source, not monoliths. Enables parallel builders.
2. Cross-database edges dangle within single-pipeline KGX. Merge phase injects stubs to resolve them.
3. ClinVar uses variant_summary.txt.gz (tabular, streaming line-by-line), not XML. Simpler and sufficient.
4. MONDO is canonical disease ID, MedGen CUI fallback. CUI-to-canonical-id rewriting in MedGen pipeline.
5. No Entrez API in Phase 1. All data from FTP bulk files.
6. Combined branch for parallel phases (1.2+1.3+1.4) when they touch different directories.
7. Skill chain is fixed: best-practices -> architecture-patterns -> [dev with standards] -> qa-gate -> release-workflow -> ship.
8. Sub-agents (not agent teams) used for parallel builders. Simpler, sufficient for the task.
9. Testing integrated at every phase via testing-standards + qa-gate + eval-harness.
10. 146 tests across Phase 1 (5 schema + 82 shared + 10 gene + 16 clinvar + 18 medgen + 14 integration + 1 conftest).
11. Data validation gates between phase groups. Run pipelines on real data before building next group.
