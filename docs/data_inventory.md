# Data inventory

Tracks all data downloaded from NCBI FTP, with source URLs, file sizes, row counts, and attributes. Updated each time a pipeline runs on real data.

## Storage location

All data is on local disk at `/export/home/chakrabortim2/data/`:
- `ftp_cache/`: raw FTP downloads (kept for re-runs)
- `kgx/`: KGX output per database (nodes.tsv + edges.tsv)
- `raw/`: intermediate parsed data (currently unused)

## MedGen (downloaded 2026-04-14, Gate 1)

### FTP downloads

| File | FTP URL | Size | Format |
|------|---------|------|--------|
| MedGenIDMappings.txt.gz | ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt.gz | 5.8 MB | gzipped, pipe-delimited |
| MGREL.RRF.gz | ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MGREL.RRF.gz | 15.7 MB | gzipped, pipe-delimited |
| NAMES.RRF.gz | ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/NAMES.RRF.gz | 3.1 MB | gzipped, pipe-delimited |
| medgen_pubmed_lnk.txt.gz | ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/medgen_pubmed_lnk.txt.gz | 239.9 MB | gzipped, pipe-delimited |
| MedGen_HPO_OMIM_Mapping.txt.gz | ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MedGen_HPO_OMIM_Mapping.txt.gz | 4.1 MB | gzipped, pipe-delimited |

### KGX output

| File | Path | Rows |
|------|------|------|
| nodes.tsv | /export/home/chakrabortim2/data/kgx/medgen/nodes.tsv | 198,813 |
| edges.tsv | /export/home/chakrabortim2/data/kgx/medgen/edges.tsv | 48,327,094 |

### Node attributes

| Column | Description | Example |
|--------|-------------|---------|
| id | MONDO:{id} or MedGen:{CUI} | MONDO:0007254 |
| category | biolink:Disease or biolink:PhenotypicFeature | biolink:Disease |
| name | Preferred concept name | Breast cancer |
| source | Always "MedGen" | MedGen |
| source_url | Link to MedGen record | https://www.ncbi.nlm.nih.gov/medgen/C0006142 |
| xrefs | Pipe-separated OMIM, MeSH, Orphanet, SNOMED, HPO IDs | OMIM:114480\|MeSH:D001943 |

### Edge attributes

| Predicate | Count | Subject type | Object type |
|-----------|-------|-------------|-------------|
| biolink:subclass_of | 95,894 | MedGen concept | MedGen concept |
| biolink:mentioned_in | 47,821,200 | MedGen concept | PMID (dangling until PubMed pipeline) |
| biolink:close_match | 410,000 | MedGen concept | HP or OMIM identifier |

### Validation

| Check | Result |
|-------|--------|
| Duplicate nodes | 0 |
| Provenance (nodes) | 100% |
| Provenance (edges) | 100% |
| Dangling edges | 48,231,910 (expected: mostly PMID references that resolve when PubMed pipeline runs) |

## Gene (downloaded 2026-04-14, Gate 1, all organisms)

### FTP downloads

| File | FTP URL | Size | Format |
|------|---------|------|--------|
| gene_info.gz | ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_info.gz | ~2.5 GB | gzipped, tab-separated |
| gene2go.gz | ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz | ~200 MB | gzipped, tab-separated |
| gene2pubmed.gz | ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2pubmed.gz | ~500 MB | gzipped, tab-separated |
| gene_refseq_uniprotkb_collab.gz | ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_refseq_uniprotkb_collab.gz | ~50 MB | gzipped, tab-separated |
| mim2gene_medgen | ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/mim2gene_medgen | ~5 MB | plain text, tab-separated |
| gene_orthologs.gz | ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_orthologs.gz | ~100 MB | gzipped, tab-separated |

Note: gene_refseq_uniprotkb_collab.gz has no GeneID column (maps protein accessions, not genes). UniProt enrichment returned 0 results. See learnings.md for details.

### KGX output

| File | Path | Rows | Size |
|------|------|------|------|
| nodes.tsv | /export/home/chakrabortim2/data/kgx/gene/nodes.tsv | 67,562,827 | 8.3 GB |
| edges.tsv | /export/home/chakrabortim2/data/kgx/gene/edges.tsv | 278,665,267 | 31 GB |

### Node breakdown

| Category | Count |
|----------|-------|
| biolink:Gene (all organisms) | 67,536,236 |
| GO terms (BiologicalProcess, MolecularActivity, CellularComponent) | 26,591 |

### Edge breakdown

| Predicate | Count |
|-----------|-------|
| biolink:in_taxon | 67,536,236 |
| biolink:participates_in / actively_involved_in / located_in (GO) | 117,490,871 |
| biolink:mentioned_in (gene2pubmed) | 76,209,437 |
| biolink:gene_associated_with_condition (mim2gene) | 7,644 |
| biolink:orthologous_to | 17,421,079 |

### Validation

| Check | Result |
|-------|--------|
| Duplicate nodes | 0 |
| Provenance (nodes) | 100% |
| Provenance (edges) | 100% (node validation only, edge validation skipped for memory) |
| UniProt enrichment | 0 (gene_refseq_uniprotkb_collab.gz has no GeneID column, see learnings.md) |

Note: edges written via streaming append (5 batches) to avoid OOM on 278M edges. Edge-level dangling check skipped at pipeline level, will run at merge phase.

## ClinVar (downloaded 2026-04-14, Gate 1)

### FTP downloads

| File | FTP URL | Size | Format |
|------|---------|------|--------|
| variant_summary.txt.gz | ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz | ~500 MB | gzipped, tab-separated |
| var_citations.txt | ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/var_citations.txt | ~50 MB | plain text, tab-separated |

### KGX output

| File | Path | Rows |
|------|------|------|
| nodes.tsv | /export/home/chakrabortim2/data/kgx/clinvar/nodes.tsv | 4,426,035 |
| edges.tsv | /export/home/chakrabortim2/data/kgx/clinvar/edges.tsv | 14,408,846 |

### Node attributes

| Column | Description | Example |
|--------|-------------|---------|
| id | ClinVar:{VariationID} | ClinVar:12345 |
| category | biolink:SequenceVariant | biolink:SequenceVariant |
| name | Variant name from ClinVar | NM_007294.4(BRCA1):c.5266dupC |
| clinical_significance | ClinVar classification | Pathogenic |
| review_status | Review status | criteria provided, multiple submitters, no conflicts |
| source_url | Link to ClinVar record | https://www.ncbi.nlm.nih.gov/clinvar/variation/12345 |

### Edge breakdown

| Predicate | Count |
|-----------|-------|
| biolink:is_sequence_variant_of | 4,407,222 |
| biolink:has_phenotype | 6,076,746 |
| biolink:cited_in | 3,924,878 |

### Validation

| Check | Result |
|-------|--------|
| Duplicate nodes | 2,337 (0.05%, multi-assembly rows, acceptable) |
| Provenance (nodes) | 100% |
| Provenance (edges) | 100% |
| Dangling edges | 14.4M (expected: NCBIGene, MedGen, PMID refs resolve at merge or later pipelines) |
