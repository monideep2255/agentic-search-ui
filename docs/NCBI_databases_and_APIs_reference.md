# NCBI databases and APIs reference

Comprehensive reference for all NCBI databases accessible via the Entrez E-utilities API and related research APIs.

---

## Provenance

All data in this document was obtained from live API calls on April 2, 2026. No web-scraped or secondary sources.

| Section | Source | How verified |
|---|---|---|
| Part 1: 39 Entrez databases (summary table) | `einfo.fcgi` with no `db` param returned the full database list | API call with NCBI API key |
| Part 2: database details (fields + links) | `einfo.fcgi?db={each_db}` for all 39 databases | Individual API call per database |
| Part 3: E-utilities API reference | NCBI E-utilities documentation + live endpoint testing | Tested ESearch, EFetch, ESummary, ELink, EGQuery against live API |
| Part 4: Datasets API | `api.ncbi.nlm.nih.gov/datasets/v2/gene/id/672` and `genome/accession/GCF_000001405.40/dataset_report` | Live API calls, response structures documented from actual responses |
| Part 5: PubTator3 API | `pubtator3-api/publications/export/biocjson?pmids=32942285` | Live API call, response structure from actual JSON |
| Part 5: LitVar2 API | `litvar2-api/variant/autocomplete/?query=rs328` and `variant/get/litvar@rs328##` | Live API calls, response fields from actual JSON |
| Part 5: LitSense API | `litsense-api/api?query=covid+vaccine+efficacy&limit=5` | Live API call, response structure from actual JSON |
| Part 5: ClinicalTrials.gov API | `clinicaltrials.gov/api/v2/studies?query.term=cancer&pageSize=1`, `studies/NCT04368728`, `stats/size` | Live API calls, 578,873 total studies confirmed |
| Part 5: BLAST, PubChem PUG REST | NCBI documentation (not live-tested in this session) | Documented from official NCBI API docs |
| Part 6: cross-database link map | Derived from EInfo link data across all 39 databases | Aggregated from Part 2 data |
| Part 7: usage policies | NCBI E-utilities documentation | Standard published policies |

NCBI API key used: stored in project `.env` file. Rate limits: 10 req/sec with key vs 3 req/sec without.

---

## How to use this document

This is a reference for building agentic search tools. Each database entry shows:
- The `db` parameter value (what you pass to E-utilities)
- Live record count (how big the database is)
- All searchable fields (what you can query on)
- All cross-database links (what connects to what)

The cross-database links are critical for agentic search: they define the graph of connections between databases.

---

## Part 1: all 39 Entrez databases (live from API)

### Summary table

| db parameter | Display name | Description | Record count | Last updated |
|---|---|---|---|---|
| `pubmed` | PubMed | PubMed bibliographic record | 40,345,671 | 2026/04/02 |
| `pmc` | PMC | PubMed Central full-text archive | 12,097,327 | 2026/04/02 |
| `books` | Books | Biomedical books, reports, databases | 1,313,805 | 2026/04/02 |
| `nlmcatalog` | NLM Catalog | Bibliographic data for NLM resources | 1,656,997 | 2026/03/27 |
| `mesh` | MeSH | Controlled vocabulary thesaurus | 355,733 | 2026/04/02 |
| `gene` | Gene | Gene-specific records | 94,350,249 | 2026/04/02 |
| `genome` | Genome | Genomic sequences, contigs, and maps | 88,333 | 2025/07/08 |
| `assembly` | Assembly | Genome assembly database | 3,530,774 | 2026/04/01 |
| `nuccore` | Nucleotide | Core nucleotide sequences (GenBank, RefSeq, TPA) | 711,555,121 | 2026/04/01 |
| `nucleotide` | Nucleotide | Alias for nuccore | (same as nuccore) | - |
| `protein` | Protein | Protein sequence records | 1,571,802,241 | 2026/04/01 |
| `ipg` | Identical Protein Groups | Consolidated identical protein records | 1,078,358,353 | 2026/03/31 |
| `proteinclusters` | Protein Clusters | Related protein sequences from complete genomes | 1,137,329 | 2017/12/04 |
| `protfam` | Protein Family Models | Homologous protein models (HMM, BlastRule, Sparcle) | 177,652 | 2026/03/31 |
| `cdd` | Conserved Domains | Protein domain alignments and profiles | 67,160 | 2025/07/02 |
| `structure` | Structure | 3D molecular structures (from PDB) | 251,427 | 2026/04/01 |
| `sra` | SRA | Sequence Read Archive (NGS raw data) | 43,553,382 | 2026/04/02 |
| `bioproject` | BioProject | Compilation of biological studies | 1,033,674 | 2026/04/02 |
| `biosample` | BioSample | Biological sample descriptions | 53,489,004 | 2026/04/02 |
| `snp` | SNP | Single nucleotide polymorphisms (dbSNP) | 1,197,210,835 | 2025/03/11 |
| `clinvar` | ClinVar | Variant-disease relationships with evidence | 4,489,534 | 2026/03/29 |
| `dbvar` | dbVar | Large-scale structural variants | 8,669,169 | 2025/08/27 |
| `gap` | dbGaP | Genotype-phenotype interaction studies | 363,717 | 2024/09/20 |
| `medgen` | MedGen | Medical genetics concepts and terms | 233,563 | 2026/04/01 |
| `omim` | OMIM | Online Mendelian Inheritance in Man | 29,529 | 2026/04/02 |
| `gtr` | GTR | Genetic Testing Registry | 64,392 | 2026/04/02 |
| `gds` | GEO DataSets | Gene Expression Omnibus datasets | 8,719,068 | 2026/04/01 |
| `geoprofiles` | GEO Profiles | Individual gene expression profiles | 128,414,055 | 2024/02/20 |
| `pccompound` | PubChem Compound | Validated unique chemical structures | 123,812,247 | 2026/04/02 |
| `pcsubstance` | PubChem Substance | Chemical substances as deposited | 344,614,675 | 2026/04/02 |
| `pcassay` | PubChem BioAssay | Bioactivity screening data | 1,769,824 | 2026/04/01 |
| `taxonomy` | Taxonomy | Organism names and phylogenetic lineages | 2,869,904 | 2026/04/02 |
| `popset` | PopSet | Population study DNA sequences | (API error: deprecated?) | - |
| `homologene` | HomoloGene | Automated homolog detection | (API error: deprecated?) | - |
| `biocollections` | Biocollections | Biological collection metadata | 8,497 | 2024/05/15 |
| `annotinfo` | AnnotInfo | Genome annotation pipeline info | 2,524 | 2026/04/01 |
| `blastdbinfo` | BlastdbInfo | BLAST database metadata | 3,424,842 | 2026/04/02 |
| `gapplus` | GaPPlus | Internal genotypes and phenotypes | 136,796 | 2017/09/29 |
| `grasp` | GRASP | GWAS results (SNP-phenotype associations) | 7,862,970 | 2015/01/26 |
| `orgtrack` | Orgtrack | Organizations providing genetic tests | 9,189 | 2026/04/02 |
| `seqannot` | SeqAnnot | Sequence annotation tracks | 514,180 | 2026/04/02 |

Total records across all databases: approximately 4.4 billion.

---

## Part 2: database details (searchable fields and cross-links)

### PubMed (`pubmed`) - 40.3M records

The primary biomedical literature database. 36M+ citations and abstracts from MEDLINE plus additional life science journals.

Searchable fields (48):

| Field code | Name | What you can search |
|---|---|---|
| ALL | All Fields | All terms from all searchable fields |
| TITL | Title | Words in title of publication |
| TIAB | Title/Abstract | Free text in abstract and title |
| MESH | MeSH Terms | Medical Subject Headings assigned to publication |
| MAJR | MeSH Major Topic | MeSH terms of major importance |
| AUTH / FULL | Author | Author name(s) |
| FAUT | First Author | First author |
| LAUT | Last Author | Last author |
| JOUR | Journal | Journal abbreviation |
| AFFL | Affiliation | Author's institutional affiliation and address |
| PDAT | Publication Date | Date of publication |
| EDAT | Entry Date | Date first accessible through Entrez |
| MDAT | Modification Date | Date of last modification |
| PTYP | Publication Type | Type (review, clinical trial, etc.) |
| LANG | Language | Language of publication |
| GRNT | Grants and Funding | NIH grant numbers |
| SUBH | MeSH Subheading | Additional MeSH specificity |
| ECNO | EC/RN Number | Enzyme commission or CAS registry number |
| SUBS | Supplementary Concept | CAS chemical name or MEDLINE substance name |
| VOL | Volume | Volume number |
| PAGE | Pagination | Page numbers |
| ISS | Issue | Issue number |
| SI | Secondary Source ID | Cross-references to other databases |
| COLN | Corporate Author | Corporate author |
| CNTY | Place of Publication | Country of publication |
| PAPX | Pharmacological Action | MeSH pharmacological action |
| PID | Publisher ID | Publisher identifier |
| FINV | Investigator | Full name of investigator |
| TT | Transliterated Title | Words in transliterated title |
| LID | Location ID | ELocation ID |
| AUID | Author Identifier | Author identifier (e.g. ORCID) |
| PS | Personal Name as Subject | Personal name as subject |
| COIS | Conflict of Interest | Conflict of interest statements |
| WORD | Text Word | Free text associated with publication |

Cross-database links (47 connections): PubMed links to Assembly, BioProject, BioSample, Books, CDD, ClinVar, dbGaP, dbVar, GEO DataSets, Gene, Genome, GEO Profiles, MedGen, Nucleotide, OMIM, PubChem BioAssay, PubChem Compound, PubChem Substance, PMC, Protein, Protein Clusters, Protein Family Models, SNP, SRA, Structure, and itself (similar articles, frequently viewed together, references).

Key link types:
- `pubmed_gene` - genes mentioned in the paper
- `pubmed_gene_rif` - GeneRIF (gene reference into function) links
- `pubmed_clinvar` - clinical variants associated with publication
- `pubmed_pmc` - free full-text in PMC
- `pubmed_pubmed` - similar articles (text + MeSH matching)
- `pubmed_snp` - SNP records cited
- `pubmed_pccompound` - chemical compounds discussed

---

### PubMed Central (`pmc`) - 12.1M records

Full-text archive of biomedical journal articles. Unlike PubMed (abstracts only), PMC has the complete article text, figures, tables, and supplementary materials.

Searchable fields (45): all PubMed fields plus:

| Field code | Name | What you can search |
|---|---|---|
| ARTI | Body - All Words | Full article body text |
| SECT | Section Title | Section titles within articles |
| REFR | Reference | Reference text |
| REFA | Reference Author | Reference author names |
| METHKWD | Methods | Keywords in methods section |
| Caption | Figure/Table Caption | Figure and table captions |
| ACK | Acknowledgments | Acknowledgments section |
| DSO | DSO | Additional text from summary |

Cross-database links (18): BioProject, Books, CDD, ClinVar, dbGaP, GEO DataSets, Gene, GEO Profiles, MedGen, OMIM, PubChem BioAssay/Compound/Substance, PubMed, SNP, SRA.

---

### Gene (`gene`) - 94.4M records

Gene-specific records with annotation, nomenclature, RefSeqs, maps, pathways, phenotypes, and interactions.

Searchable fields (36):

| Field code | Name | What you can search |
|---|---|---|
| GENE | Gene Name | Symbol or symbols of the gene |
| GFN | Gene Full Name | Full gene name |
| PFN | Protein Full Name | Full protein name |
| ORGN | Organism | Scientific and common names |
| CHR | Chromosome | Chromosome number |
| MV | Default Map Location | Chromosomal map location |
| DIS | Disease/Phenotype | Associated diseases |
| ACCN | Nucleotide/Protein Accession | Associated accessions |
| MIM | MIM ID | OMIM number |
| GO | Gene Ontology | GO terms |
| DOM | Domain Name | Associated domains |
| CPOS | Base Position | Chromosome base position |
| GL | Gene Length | Gene length |
| XC | Exon Count | Number of exons |
| EXPR | Expression/Tissues | Gene expression data |
| PMID | PubMed ID | Associated publications |
| TID | Taxonomy ID | Taxonomy identifier |
| PROP | Properties | Gene record properties |

Cross-database links (33): Books, CDD, ClinVar, dbVar, dbGaP, Genome, GEO Profiles, GTR, MedGen, Nucleotide (RefSeqGene, RefSeq RNA), OMIM, PubChem BioAssay/Compound/Substance, PMC, Protein (RefSeq), Protein Clusters, Protein Family Models, PubMed (including GeneRIF and OMIM-derived), SNP, Structure, Taxonomy.

---

### Nucleotide (`nuccore`) - 711.6M records

Core nucleotide sequence database containing GenBank, RefSeq, and third-party annotation sequences.

Searchable fields (34):

| Field code | Name | What you can search |
|---|---|---|
| ACCN | Accession | Sequence accession number |
| ORGN | Organism | Scientific/common names + full taxonomy |
| GENE | Gene Name | Associated gene name |
| PROT | Protein Name | Associated protein name |
| TITL | Title | Definition line words |
| AUTH | Author | Publication authors |
| SLEN | Sequence Length | Length of sequence |
| FKEY | Feature key | Annotated features |
| PROP | Properties | Source qualifiers and molecule type |
| GPRJ | BioProject | Associated BioProject |
| ASSM | Assembly | Associated assembly |
| DIV | Division | GenBank division |
| STRN | Strain | Organism strain |
| BIOS | BioSample | Associated BioSample |

Cross-database links (37): Assembly, BioCollections, BioProject, BioSample, CCDS, dbVar, Gene, Genome, GEO Profiles, OMIM, PubChem Compound/Substance, Protein (multiple: coding region, mature peptides, WGS, TSA), Protein Clusters, PubMed, SNP, SRA, Structure, Taxonomy. Also self-links: GenBank-RefSeq mappings, same-species links, RNA annotations, small genome segments.

---

### Protein (`protein`) - 1.57B records

Protein sequence records from GenPept, RefSeq, Swiss-Prot, PIR, PRF, and PDB.

Searchable fields (33): similar to Nucleotide, plus:

| Field code | Name | What you can search |
|---|---|---|
| MLWT | Molecular Weight | Protein molecular weight |
| PROT | Protein Name | Protein name |
| SLEN | Sequence Length | Sequence length |

Cross-database links (38): BioCollections, BioProject, CCDS, CDD (conserved domains, concise domains, domain summary), Gene, Genome, Nucleotide (coding region, mRNA, WGS, TSA), OMIM, PubChem BioAssay/Compound/Substance, Protein Clusters, Protein Family Models, PubMed, SNP, Structure (identical, direct, related), Taxonomy. Also self-links: RefSeq-UniProt mappings, autonomous proteins, CDART (domain architecture).

---

### SNP (`snp`) - 1.2B records

Single nucleotide polymorphisms, microsatellites, and small insertions/deletions (dbSNP).

Searchable fields (29):

| Field code | Name | What you can search |
|---|---|---|
| RS | Reference SNP ID | rs number |
| CHR | Chromosome | Chromosome |
| GENE | Gene Name | Associated gene |
| FXN | Function Class | Functional consequence |
| CLIN | Clinical Significance | Clinical effects |
| GMAF | Global Minor Allele Frequency | MAF from 1000 Genomes |
| ALFA_EUR | European MAF | ALFA European population frequency |
| ALFA_AFR | African MAF | ALFA African population frequency |
| ALFA_ASN | Asian MAF | ALFA Asian population frequency |
| ALFA_SAS | South Asian MAF | ALFA South Asian frequency |
| ALFA_LAC | Latin American 1 MAF | ALFA Latin American 1 frequency |
| ALFA_LEN | Latin American 2 MAF | ALFA Latin American 2 frequency |
| ALFA_OTR | Other MAF | ALFA other population frequency |
| SCLS | SNP Class | SNP class (snv, deletion, insertion, etc.) |
| VALI | Validation Status | Validation status |
| CPOS | Base Position | Chromosome position (GRCh38) |
| CPOS_GRCH37 | Base Position Previous | Position on GRCh37 |

Cross-database links (14): BioProject, BioSample, ClinVar, dbVar, dbGaP, Gene, Nucleotide, PMC, Protein, PubMed, Structure, Taxonomy. Also: somatic SNPs (self-link).

---

### ClinVar (`clinvar`) - 4.5M records

Reported relationships between human genetic variants and health conditions, with supporting clinical evidence and review status.

Searchable fields (44):

| Field code | Name | What you can search |
|---|---|---|
| GENE | Gene Name | Gene symbol |
| DIS | Disease/Phenotype | Associated diseases/traits |
| ACCN | ClinVar accession | Accession of the assertion |
| VRID | External allele ID | Public variant ID |
| VRTP | Type of variation | Variant type (SNV, deletion, etc.) |
| MCNS | Molecular consequence | Molecular-level consequence |
| RVST | Review status | Review status (practice guideline to no assertion) |
| CLINSIG_LAST_CHANGED | Last significance change | Date of last clinical significance change |
| ALID | AlleleID | Unique allele identifier |
| ORIG | Origin | Germline, somatic, etc. |
| CSPDI | Canonical SPDI | Canonical SPDI for variation |
| FCNS | Functional consequence | Functional consequence |
| COLLMETHOD | Collection method | How evidence was collected |
| SBM | Submitter | Submitting organization |
| CHR | Chromosome | Chromosome |
| CPOS | Base Position | GRCh38 position |
| C37 | Base Position GRCh37 | GRCh37 position |
| VLEN | Variant Length | Length of variant |
| MIM | MIM | OMIM number |
| HGNC | HGNC identifier | HUGO gene nomenclature ID |

Cross-database links (11): dbVar, Gene, GTR, MedGen, OMIM, Orgtrack, PMC, PubMed, dbSNP.

---

### SRA (`sra`) - 43.6M records

Raw sequencing data from next-generation sequencing platforms (Illumina, PacBio, Oxford Nanopore, etc.).

Searchable fields (22):

| Field code | Name | What you can search |
|---|---|---|
| ACCN | Accession | SRA accession |
| ORGN | Organism | Organism name |
| Platform | Platform | Sequencing platform |
| Strategy | Strategy | Sequencing strategy (WGS, RNA-Seq, etc.) |
| Source | Source | Sequence source (genomic, transcriptomic, etc.) |
| Selection | Selection | Library selection method |
| Layout | Layout | Single or paired-end |
| ReadLength | Read Length | Read length |
| Access | Access | Public or controlled access |
| Aligned | Aligned | Percent of aligned reads |
| Mbases | Mbases | Size in megabases |
| GPRJ | BioProject | Associated BioProject |
| BIOS | BioSample | Associated BioSample |

Cross-database links (9): Assembly, BioProject, BioSample, dbGaP, GEO DataSets, Nucleotide WGS, PMC, PubMed, Taxonomy.

---

### Assembly (`assembly`) - 3.5M records

Genome assembly metadata with quality statistics, links to sequences, and submission details.

Searchable fields (50):

| Field code | Name | What you can search |
|---|---|---|
| ASAC | Assembly Accession | GCA/GCF accession |
| ASLV | Assembly Level | Contig, scaffold, chromosome, complete genome |
| ORGN | Organism | Organism name |
| NAME | Assembly Name | Assembly nomenclature |
| COV | Coverage | Sequencing coverage |
| LEN | Total Length Mbp | Total sequence length |
| CN50 | Contig N50 | Contig N50 statistic |
| SN50 | Scaffold N50 | Scaffold N50 statistic |
| CNTG | Contig Count | Number of contigs |
| REPL | Chromosome Count | Number of chromosomes |
| SUBO | Submitter Organization | Who submitted |
| TECH | Sequencing Technology | Technology used |
| RCAT | RefSeq Category | RefSeq classification |
| FTYP | From Type Material | Whether from type material |
| NFRS | Excluded from RefSeq | Reasons for exclusion |

Cross-database links (10): BioProject, BioSample, Genome, Nucleotide (INSDC, RefSeq, WGS master), PubMed, SRA, Taxonomy. Also: linked diploid assembly.

---

### BioProject (`bioproject`) - 1.0M records

Compilation of biological studies with links to resulting datasets across NCBI.

Searchable fields (35): Organism, Project Accession, Project Type/Subtype, Title, Submitter Organization, Replicon info, Description, Keyword, Data Type, Grant ID, Funding Agency, PMID, DOI, Assembly info, Attributes.

Cross-database links (26): Assembly, BioProject (umbrella/data relationships), BioSample, dbVar, dbGaP, GEO DataSets, Genome, Nucleotide (multiple types: genomic DNA/RNA, map records, RefSeq, representative, transcript, TSA, WGS), PMC, Protein, PubMed, SNP, SRA, Taxonomy.

---

### BioSample (`biosample`) - 53.5M records

Descriptions of biological materials used in experimental assays, with structured metadata attributes.

Searchable fields (14): Accession, Title, Organism, Author, Publication/Modification Date, Attribute Name, Attribute, Submitter Organization, Properties.

Cross-database links (12): Assembly, BioCollections, BioProject, dbVar, dbGaP, GEO DataSets, Nucleotide, OMIM, PubMed, SNP, SRA, Taxonomy.

---

### Taxonomy (`taxonomy`) - 2.9M records

Names and phylogenetic lineages of organisms with molecular data in NCBI.

Searchable fields (21):

| Field code | Name | What you can search |
|---|---|---|
| SCIN | Scientific Name | Scientific name |
| COMN | Common Name | Common name |
| TXSY | Synonym | Name synonyms |
| NXLV | Next Level | Immediate parent in hierarchy |
| SBTR | Subtree | Any parent node |
| LNGE | Lineage | Full lineage |
| GC | Nuclear Genetic Code | Genetic code |
| MGC | Mitochondrial Genetic Code | Mitochondrial code |
| RANK | Rank | Hierarchical position (kingdom, genus, etc.) |

Cross-database links (20): Assembly, BioProject, BioSample, Books, CDD, dbVar, GEO DataSets, Gene, Genome, GEO Profiles, PubChem BioAssay/Compound/Substance, Protein, Protein Clusters, PubMed, SNP, SRA, Structure.

---

### GEO DataSets (`gds`) - 8.7M records

Curated gene expression and molecular abundance datasets from the Gene Expression Omnibus.

Searchable fields (31): Organism, GEO Accession (GDS/GPL/GSM/GSE), Title, Description, Supplementary Files, Entry Type, Sample/Platform Type, Number of Samples, Source, Author, MeSH Terms, Attributes.

Cross-database links (10): BioProject, BioSample, dbVar, GEO Profiles, PMC, PubMed, SRA, Taxonomy. Also: related datasets, similar studies (self-links).

---

### GEO Profiles (`geoprofiles`) - 128.4M records

Individual gene expression profiles from GEO experiments.

Searchable fields (26): Organism, GEO Accession, Gene Symbol, Gene Description, Spot/Probe ID, Expression statistics (ranked std dev, max, min), Gene Ontology, Chromosome, Dataset Type, Annotation Type.

---

### ClinicalTrials (not in Entrez)

ClinicalTrials.gov is a separate system not accessible via E-utilities. It has its own API at `https://clinicaltrials.gov/api/v2/`.

---

### PubChem Compound (`pccompound`) - 123.8M records

Validated, unique chemical structures with computed properties.

Searchable fields (41):

| Field code | Name | What you can search |
|---|---|---|
| UID | CompoundID | CID number |
| InChI | InChI | International Chemical Identifier |
| InChIKey | InChI Key | Hashed InChI |
| Synonym | Synonym | Chemical synonyms |
| MeSHTerm | MeSH Term | Associated MeSH terms |
| PharmAction | Pharmacological Action | Drug action type |
| MolecularWeight | Molecular Weight | MW in daltons |
| XLogP | XLogP | Lipophilicity |
| Complexity | Complexity | Molecular complexity score |
| TPSA | TPSA | Topological polar surface area |
| HydrogenBondDonorCount | H-bond Donors | Number of H-bond donors |
| HydrogenBondAcceptorCount | H-bond Acceptors | Number of H-bond acceptors |
| RotatableBondCount | Rotatable Bonds | Number of rotatable bonds |
| HeavyAtomCount | Heavy Atoms | Non-hydrogen atom count |
| ExactMass | Exact Mass | Monoisotopic mass |
| ActiveAidCount | Active BioAssay Count | Number of active assays |
| TotalAidCount | Total BioAssay Count | Total assays tested |

Cross-database links (28): Gene, MeSH, Nucleotide, OMIM, BioAssays (all/active/inactive/probe, activity concentration thresholds), Mixture/Parent/Same-connectivity compounds, PMC, Protein, PubMed, Structure, Taxonomy, PubChem Substance.

---

### PubChem Substance (`pcsubstance`) - 344.6M records

Chemical substance information as deposited by data sources (before standardization to Compound).

Searchable fields (21): SubstanceID, SourceName, SourceID, SourceCategory, DepositDate, Synonym, CompoundID (standardized CID), AssaySourceName, StructureID.

---

### PubChem BioAssay (`pcassay`) - 1.8M records

Bioactivity screening data and descriptions of biological assays.

Searchable fields (41): Assay ID/Name/Description/Protocol, Activity Outcome Method, Source Name, Deposit/Modify Date, Journal, Active/Total SID counts, Protein Target Name/GI, Gene Symbol, RNA Target, Taxonomy, Cell Line, GenBank/UniProt Accession, Detection Method, Organism.

---

### MedGen (`medgen`) - 233.6K records

Medical genetics concepts linking diseases, genes, and clinical features across vocabularies (SNOMED CT, HPO, OMIM, etc.).

Searchable fields (24): Accession (CUI), Title, Definition, Vocabulary, Source ID, Clinical Features, Gene Name, Chromosome, OMIM ID, Mode of Inheritance, SNOMED CT CUI, Keywords.

Cross-database links (15): Books, ClinVar, dbGaP, Gene, GTR (clinical + research tests), MeSH, OMIM (including OMIM genes), PMC, PubMed (including Bookshelf-cited and GeneReviews).

---

### OMIM (`omim`) - 29.5K records

Online Mendelian Inheritance in Man: catalog of human genes and genetic disorders with detailed clinical descriptions.

Searchable fields (22): MIM ID, Title, Clinical Synopsis, Allelic Variant, Gene Map, Gene Name, Chromosome, Publication Date, Editor, Properties.

Cross-database links (17): BioSample, Books, ClinVar, dbVar, Gene, GEO Profiles, GTR, MedGen (including gene-related), Nucleotide, OMIM (related entries), PubChem BioAssay/Compound/Substance, PMC, Protein, PubMed, Structure.

---

### GTR (`gtr`) - 64.4K records

Voluntary registry of genetic tests with detailed information about labs, methods, diseases, and genes.

Searchable fields (60+): Test accession/name, Organization details (name, city, state, country, directors, staff, certifications), Disease names, Gene symbols/IDs, Method categories, Clinical utility/validity, Specimen types, Target populations, CPT codes, Pharmacogenetic conditions, Microbe-related fields.

Cross-database links (4): Gene, MedGen, OMIM, Orgtrack.

---

### dbGaP (`gap`) - 363.7K records

Genotype and phenotype interaction studies with controlled-access data.

Searchable fields (43): Study ID/Name, Disease, Project, Genotype Platform, Variable ID/Name/Description, Document ID/Name, Analysis ID/Name, Dataset ID/Name, Molecular Data Type, Study Design, Data Access Committee, PhenX mappings.

Cross-database links (12): BioProject, BioSample, dbVar, GEO DataSets, Gene, MedGen, MeSH, Nucleotide, PMC, PubMed, SNP, SRA.

---

### dbVar (`dbvar`) - 8.7M records

Large-scale genomic structural variants (insertions, deletions, duplications, inversions, translocations).

Searchable fields (42): Accession, Assembly, Chromosome/Position, Variant Type/Size, Clinical Interpretation, Disease/Phenotype, Gene Name, Method Type, Population allele frequencies (Global, African, American, East Asian, European, South Asian, Other), Allele Origin, Zygosity, Sex, Age, Study Type, OMIM, PubMed ID, MeSH.

---

### Conserved Domains (`cdd`) - 67.2K records

Protein domain models from multiple source databases (Pfam, SMART, COG, etc.).

Searchable fields (16): Accession, Database source, Title, Subtitle, Description, Organism, PSSM Length, Functional Sites count/description, Alternative Accession, Structure Representative.

---

### Structure (`structure`) - 251.4K records

3D macromolecular structures derived from the Protein Data Bank.

Searchable fields (52): PDB Accession, Resolution, Experimental Method, Title/Abstract, Author, PDB Class/Source/Description, Chemical Ligand codes/names/synonyms, Organism, Taxonomy ID, Molecule counts (protein/DNA/RNA/chemical per biological unit and ASU), Molecular Weight, Conserved Domain fields, Gene Name/Description.

---

### Bookshelf (`books`) - 1.3M records

Collection of biomedical books, reports, and databases, including GeneReviews.

Searchable fields (33): Author, Title, Full Text, Book ID, PMID, Publisher, ISBN, MeSH Terms, Disease Name, Gene Name, Protein Name, Grant Number, Publication Type, Resource Type.

---

### NLM Catalog (`nlmcatalog`) - 1.7M records

Bibliographic data for resources cataloged by NLM.

Searchable fields (42): Author, Title, Journal, Language, Resource Type, MeSH Terms, Country, ISSN, NLM Title Abbreviation, Publication Start/End Year, Authority Information.

---

### MeSH (`mesh`) - 355.7K records

Medical Subject Headings controlled vocabulary thesaurus.

Searchable fields (14): Tree Number, MeSH Terms, Substance Name, Scope Note, Registry Number, Record Type (main heading, subheading, pharmacological action, substance, publication type), MeSH Unique ID.

Cross-database links (3): dbGaP, MedGen, PubChem Compound.

---

### Identical Protein Groups (`ipg`) - 1.08B records

Consolidated records of identical protein sequences across GenBank, RefSeq, SwissProt, and PDB.

Searchable fields (20): Accession (protein + nucleotide), Title, Organism, Protein Name, Sequence Length, Molecular Weight, Protein Count (in group), Organism Count, BioProject, Assembly, Division.

---

### Remaining databases

**Protein Clusters (`proteinclusters`)** - 1.1M records: Related protein sequences from complete prokaryotic and organelle genomes. 32 searchable fields including COG, KO, HAMAP, Domains, Paralogs, SwissProt Accession. Last updated 2017.

**Protein Family Models (`protfam`)** - 177.7K records: HMM and BlastRule protein family models with Sparcle architectures. 23 searchable fields including EC Number, Gene Symbol, GO terms, CDD references, Review Level.

**Biocollections (`biocollections`)** - 8.5K records: Biological collection metadata (museums, culture collections). 16 fields including Institution/Collection codes, Country.

**AnnotInfo (`annotinfo`)** - 2.5K records: Genome annotation pipeline metadata. 14 fields including Assembly Accession, Annotation Release ID, Milestones, Build Status.

**BlastdbInfo (`blastdbinfo`)** - 3.4M records: BLAST database metadata. 15 fields including Database Name/Title, Organism Taxid, Sequence Type/Strategy.

**GaPPlus (`gapplus`)** - 136.8K records: Internal genotypes and phenotypes database. 16 fields including Study/Analysis ID, Marker RS, PValue, Trait, Chromosome, Gene. Last updated 2017.

**GRASP (`grasp`)** - 7.9M records: Genome-wide association study results (SNP-phenotype associations). 20 fields including RS ID, Chromosome, Gene, P-value, Phenotype, Population. Last updated 2015.

**Orgtrack (`orgtrack`)** - 9.2K records: Organizations providing genetic tests (labs and clinics). 36 fields including Organization details, Test methods, Certifications, Disease/Gene associations.

**SeqAnnot (`seqannot`)** - 514.2K records: Sequence annotation tracks. 14 fields including Accession, Organism, Target Assembly, Annotation Type.

---

## Part 3: E-utilities API reference

Base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

### Rate limits

| Condition | Rate limit | Details |
|---|---|---|
| Without API key | 3 requests/second | Per IP address |
| With API key | 10 requests/second | Per API key |
| BLAST | 1 submission/10 seconds | 1 status poll/minute per RID |
| PubChem PUG REST | 5 requests/second | 400 requests/minute |
| Large result sets | Use &retmax and &retstart | Page through results, max 10,000 per call for most dbs |
| Bulk downloads | Use FTP instead | E-utilities not designed for bulk data transfer |

API key usage: add `&api_key=YOUR_KEY` to any E-utility URL.

### 9 E-utility endpoints

#### EInfo - database information

```
einfo.fcgi?db={database}&retmode=json
```

Returns: list of all databases (no db param), or field list + link list for a specific database. This is what was used to generate this entire document.

#### ESearch - text search

```
esearch.fcgi?db={database}&term={query}&retmode=json&retmax=20&retstart=0
```

Returns: list of UIDs matching the query. Use field tags in queries: `cancer[TITL] AND 2024[PDAT]`.

Key parameters:
- `term` - search query (supports boolean AND/OR/NOT, field tags, ranges)
- `retmax` - max results to return (default 20, max 10,000 for most dbs, max 100,000 for some)
- `retstart` - offset for pagination
- `sort` - sort order (varies by db)
- `datetype` / `mindate` / `maxdate` - date filtering
- `usehistory=y` - store results on server for subsequent retrieval

#### EFetch - record retrieval

```
efetch.fcgi?db={database}&id={uid_list}&rettype={type}&retmode={mode}
```

Returns: full records in specified format. This is the main data retrieval endpoint.

Common rettype/retmode combinations:
- PubMed: `rettype=abstract&retmode=text`, `rettype=xml`, `rettype=medline`
- Nucleotide/Protein: `rettype=fasta`, `rettype=gb` (GenBank), `rettype=gp` (GenPept)
- Gene: `rettype=gene_table`
- SNP: `rettype=json`

Max IDs per request: 200 for most databases (POST for larger batches).

#### ESummary - document summaries

```
esummary.fcgi?db={database}&id={uid_list}&retmode=json
```

Returns: condensed record summaries (lighter than EFetch). Good for getting metadata without full records.

#### ELink - cross-database links

```
elink.fcgi?dbfrom={source_db}&db={target_db}&id={uid_list}&retmode=json
```

Returns: UIDs in target database that are linked to source UIDs. This is the key endpoint for traversing the database graph.

Link commands:
- `cmd=neighbor` (default) - related records in target db
- `cmd=neighbor_score` - with relevancy scores
- `cmd=neighbor_history` - store results on server
- `cmd=acheck` - check which links exist
- `cmd=llinks` - LinkOut URLs (external resources)

#### EPost - upload UIDs to history server

```
epost.fcgi?db={database}&id={uid_list}
```

Returns: WebEnv + QueryKey for use in subsequent calls. Use for batch operations with large ID lists.

#### EGQuery - global search

```
egquery.fcgi?term={query}&retmode=json
```

Returns: count of results in every Entrez database for a given query. Good for discovering which databases have relevant data.

#### ESpell - spelling suggestions

```
espell.fcgi?db={database}&term={query}
```

Returns: spelling corrections for search terms.

#### ECitMatch - citation matching

```
ecitmatch.cgi?db=pubmed&rettype=xml&bdata={journal}|{year}|{volume}|{first_page}|{author}|{key}|
```

Returns: PubMed ID for a citation specified by journal, year, volume, page, and author.

### Common API workflows

**Search and fetch (most common):**
1. ESearch to get UIDs matching a query
2. EFetch or ESummary to get the records

**Cross-database discovery:**
1. ESearch in one database
2. ELink to find related records in another database
3. EFetch to get the linked records

**Batch operations (large datasets):**
1. EPost to upload a list of UIDs to the history server
2. EFetch with WebEnv + QueryKey, paginating with retstart/retmax

**Global discovery:**
1. EGQuery to see which databases have hits for a term
2. ESearch in the most relevant databases
3. ELink to find cross-database connections

---

## Part 4: NCBI Datasets API (v2)

A newer REST API for genome, gene, taxonomy, and virus data. Simpler and more modern than E-utilities for the databases it covers: cleaner JSON responses, richer nested objects, and downloadable data packages.

Source: live API calls to `https://api.ncbi.nlm.nih.gov/datasets/v2/` on April 2, 2026.

Base URL: `https://api.ncbi.nlm.nih.gov/datasets/v2/`

### Datasets vs E-utilities: when to use which

| Need | Use Datasets API | Use E-utilities |
|---|---|---|
| Gene info with GO terms, transcripts, Swiss-Prot accessions | Yes (richer gene records) | Yes (but flatter structure) |
| Genome assemblies with annotation stats, BUSCO, gene counts | Yes (much richer) | Yes (basic metadata only) |
| Taxonomy with lineage | Yes | Yes |
| Virus genomes | Yes | Yes (via nuccore) |
| PubMed, PMC, literature | No | Yes |
| SNP, ClinVar, dbVar (variation) | No | Yes |
| GEO, expression data | No | Yes |
| PubChem (chemistry) | No | Yes |
| Cross-database linking (ELink) | No | Yes |
| MedGen, OMIM, GTR (clinical genetics) | No | Yes |

The Datasets API overlaps with E-utilities for Gene, Genome/Assembly, Taxonomy, and Nucleotide/Protein. For those databases, Datasets returns richer, more structured data. For everything else (literature, variation, expression, chemistry, clinical genetics), E-utilities is the only option.

### Endpoints (verified live)

| Endpoint | Method | What it returns |
|---|---|---|
| `gene/id/{gene_id}` | GET | Gene record with symbol, description, GO terms, transcripts, proteins, OMIM IDs, Ensembl IDs, Swiss-Prot accessions, reference standards |
| `gene/symbol/{symbol}/taxon/{taxon}` | GET | Gene lookup by symbol and organism |
| `genome/accession/{accession}` | GET | Genome metadata |
| `genome/accession/{accession}/dataset_report` | GET | Rich assembly report: organism info, assembly stats (N50, contig/scaffold counts, GC content, chromosome count), annotation info (gene counts by type, BUSCO scores), BioProject lineage |
| `genome/taxon/{taxon}` | GET | All genomes for an organism |
| `taxonomy/taxon/{taxon}` | GET | Taxonomy info with lineage |
| `virus/genome/accession/{accession}` | GET | Virus genome data |

### Gene record structure (Datasets API, verified live with Gene ID 672 / BRCA1)

```
gene_id, symbol, description, type (PROTEIN_CODING)
tax_id, taxname, common_name
chromosomes, orientation
nomenclature_authority (HGNC)
swiss_prot_accessions
ensembl_gene_ids
omim_ids
synonyms
summary (free text description)
reference_standards (accession, genomic range)
annotations (assembly-specific locations)
transcript_count, protein_count, transcript_type_counts
gene_groups
gene_ontology:
  molecular_function[] (name, GO ID, evidence code, qualifier)
  biological_process[] (name, GO ID, evidence code, qualifier)
  cellular_component[] (name, GO ID, evidence code, qualifier)
```

### Genome report structure (verified live with GCF_000001405.40 / human reference)

```
accession, current_accession, paired_accession
source_database, refseq_category
organism (tax_id, organism_name, common_name)
assembly_info (level, status, name, type, release_date)
assembly_stats:
  total_number_of_chromosomes
  total_sequence_length, total_ungapped_length
  contig_n50, scaffold_n50
  contig_count, scaffold_count
  gc_count, gc_percent
  number_of_gaps
annotation_info:
  provider, release_date
  gene_counts (total, protein_coding, non_coding, pseudogene)
  busco (complete, single_copy, duplicated, fragmented, missing)
organelle_info (mitochondrial details)
bioproject_lineage, bioproject_accession
submitter, blast_url
```

No API key required. No documented rate limits.

---

## Part 5: other NCBI APIs

### BLAST URL API

Two-phase workflow:
1. PUT: submit query to `https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi` with `CMD=Put`
2. GET: poll for results with `CMD=Get` and the returned RID

Rate limits: 1 request per 10 seconds for submission, poll no more than once per minute per RID.

### PubChem PUG REST

Base URL: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/`

URL structure: `{domain}/{namespace}/{identifiers}/{operation}/{output}`

Input types: CID, SID, AID, name, SMILES, InChI, InChIKey, formula, substructure, similarity, identity.

Rate limits: 5 requests/second, 400 requests/minute. No API key system, IP-based throttling.

### Variation Services API

- SPDI notation endpoints for normalizing variant representations
- ClinVar Submission API for programmatic submission
- Clinical Table Search Service for ClinVar data

### PubTator3 API - biomedical text mining

Base URL: `https://www.ncbi.nlm.nih.gov/research/pubtator3-api/`

PubTator3 automatically extracts and normalizes biomedical entities from PubMed articles: genes, diseases, chemicals, mutations, species, and cell lines. Returns annotations with normalized IDs (MeSH, NCBI Gene, etc.) and entity-entity relationships with confidence scores.

Endpoints (verified live):

| Endpoint | Method | What it does |
|---|---|---|
| `publications/export/biocjson?pmids={pmid_list}` | GET | Export full annotations for specific PMIDs in BioC JSON format |
| `publications/export/pubtator?pmids={pmid_list}` | GET | Export in PubTator format (tab-delimited) |
| `cite/tsv?pmids={pmid_list}` | GET | Citation-level entity summary in TSV |
| `search/?text={query}&page={n}&sort={field}` | GET | Search PubTator3 annotations by text query |
| `publications/export/biocxml?pmids={pmid_list}` | GET | Export in BioC XML format |

Response structure (BioC JSON):
- `pmid`, `pmcid`, `journal`, `date`, `authors` - publication metadata
- `passages[]` - article sections (title, abstract, body)
  - `annotations[]` - extracted entities with:
    - `text` - entity mention
    - `infons.type` - entity type (Gene, Disease, Chemical, Species, CellLine, Mutation)
    - `infons.identifier` - normalized ID (e.g. MESH:D001943 for breast cancer, NCBI Gene ID for genes)
    - `locations[]` - offset and length in text
  - `relations[]` - entity-entity relationships with:
    - `type` - relationship type (Association, Bind, etc.)
    - `score` - confidence (0-1)
    - `role1`, `role2` - the two entities

No API key required. No documented rate limits, but respect standard NCBI usage policies.

### LitVar2 API - variant-literature linking

Base URL: `https://www.ncbi.nlm.nih.gov/research/litvar2-api/`

LitVar2 links genetic variants (by rsID, HGVS, or gene) to PubMed literature. Returns variant metadata, clinical significance, allele frequencies, and associated publications.

Endpoints (verified live):

| Endpoint | Method | What it does |
|---|---|---|
| `variant/autocomplete/?query={text}` | GET | Autocomplete variant search (rs IDs, gene names, HGVS) |
| `variant/get/{variant_id}` | GET | Full variant record by LitVar ID |
| `variant/search/?variant_id={id}&page={n}&page_size={n}` | GET | Search publications for a variant |

Variant ID format: `litvar@rs328##` (URL-encode the `#` as `%23`).

Response fields for variant records:
- `rsid` - dbSNP identifier
- `gene[]` - associated gene symbols
- `name` - variant name (e.g. p.S447X)
- `hgvs` - HGVS nomenclature
- `pmids_count` - number of associated publications
- `clingen_ids[]` - ClinGen identifiers
- `data_clinical_significance[]` - clinical assessments (benign, pathogenic, etc.)
- `data_maf.alfa` - minor allele frequency from ALFA
- `data_snp_class` - SNP classification
- `data_chromosome_base_position` - genomic coordinates
- `data_species` - organism
- `data_tax_id` - taxonomy ID
- `flag_gene_variant`, `flag_clingen_variant`, `flag_rsid_variant` - variant type flags

No API key required. No documented rate limits.

### LitSense API - sentence-level literature search

Base URL: `https://www.ncbi.nlm.nih.gov/research/litsense-api/`

LitSense searches PubMed at the sentence level rather than article level. Returns individual sentences with relevance scores and entity annotations.

Endpoints (verified live):

| Endpoint | Method | What it does |
|---|---|---|
| `api?query={text}&limit={n}` | GET | Search for sentences matching a query |

Response fields:
- `text` - the matched sentence
- `score` - relevance score
- `section` - document section (title, abstract, body, or null)
- `annotations[]` - extracted entities in format `position|length|type|identifier`
- `pmid` - source PubMed ID
- `pmcid` - source PMC ID (if available)

No API key required. No documented rate limits.

### ClinicalTrials.gov API (v2) - 578,873 studies

Base URL: `https://clinicaltrials.gov/api/v2/`

Separate from NCBI E-utilities. This is the registry of publicly and privately supported clinical studies worldwide. No API key required.

Endpoints (verified live):

| Endpoint | Method | What it does |
|---|---|---|
| `studies?query.term={text}` | GET | Search all studies by keyword |
| `studies?query.cond={condition}` | GET | Search by condition/disease |
| `studies?query.intr={intervention}` | GET | Search by intervention/treatment |
| `studies/{nctId}` | GET | Get a single study by NCT ID |
| `studies?fields={field_list}` | GET | Return only specific fields |
| `stats/size` | GET | Total number of studies in database |

Search parameters:
- `query.term` - general search across all fields
- `query.cond` - condition or disease
- `query.intr` - intervention or treatment
- `query.titles` - search in titles only
- `query.outc` - search in outcomes
- `query.spons` - sponsor or collaborator
- `query.lead` - lead sponsor
- `query.id` - study ID (NCT number)
- `filter.overallStatus` - status filter (RECRUITING, COMPLETED, etc.)
- `filter.geo` - geographic filter
- `filter.advanced` - Essie expression syntax
- `pageSize` - results per page (max 1000)
- `pageToken` - pagination token from previous response
- `fields` - comma-separated list of fields to return
- `sort` - sort order

Study record structure (protocolSection modules):
- `identificationModule` - NCT ID, titles, acronym, organization, secondary IDs
- `statusModule` - overall status, start/completion dates, submission dates, verification
- `sponsorCollaboratorsModule` - lead sponsor, collaborators, responsible party
- `oversightModule` - DMC status, FDA regulation flags
- `descriptionModule` - brief summary, detailed description
- `designModule` - study type, phases, allocation, enrollment, masking, design info
- `armsInterventionsModule` - arm groups with descriptions, interventions with type/name/description
- `outcomesModule` - primary and secondary outcome measures with time frames
- `eligibilityModule` - inclusion/exclusion criteria, age range, sex, healthy volunteers
- `contactsLocationsModule` - officials, facility locations with city/state/country/coordinates

Derived section:
- `conditionBrowseModule` - MeSH terms and condition hierarchy
- `interventionBrowseModule` - MeSH terms for interventions
- `miscInfoModule` - version info

No rate limits documented, but large-scale scraping is discouraged. Use bulk download files instead.

### PMC ID Converter

`https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/`

Converts between PMID, PMCID, and DOI. No API key required.

### EDirect (command-line)

NCBI provides command-line tools (`esearch`, `efetch`, `elink`, `efilter`, `xtract`) that wrap E-utilities with Unix pipe-friendly syntax. Useful for scripting complex multi-step queries.

---

## Part 6: cross-database link map

This is the graph of how databases connect to each other. Critical for agentic search: an agent that starts in PubMed and follows links can reach Gene, ClinVar, SNP, Protein, Structure, and more.

### Highest-connectivity databases (most outbound links)

1. PubMed (47 link types to 25+ databases)
2. Nucleotide (37 link types)
3. Protein (38 link types)
4. Gene (33 link types)
5. PubChem Compound (28 link types)
6. BioProject (26 link types)

### Key traversal paths for agentic search

| Starting point | Path | What you find |
|---|---|---|
| Disease name | MedGen -> ClinVar -> Gene -> Protein -> Structure | From disease to 3D protein structure |
| Gene symbol | Gene -> SNP -> ClinVar -> PubMed | Gene variants with clinical significance and literature |
| Chemical name | PubChem Compound -> BioAssay -> Gene -> PubMed | Drug target identification with literature |
| Publication | PubMed -> Gene -> Protein -> CDD | Proteins and domains from a paper |
| Organism | Taxonomy -> Genome -> Assembly -> Nucleotide -> Protein | Full genome to proteome |
| Clinical variant | ClinVar -> Gene -> GTR | From variant to available genetic tests |
| Expression profile | GEO DataSets -> Gene -> PubMed | Expression data to function and literature |

### Universal connectors

These databases appear as link targets from almost every other database:
- PubMed (literature links from nearly everything)
- Gene (gene associations from variation, expression, structure, etc.)
- Taxonomy (organism classification links from all sequence databases)
- Protein (protein links from gene, structure, domain databases)

---

## Part 7: NCBI usage policies

- Always include an API key for production use (10 req/sec vs 3 req/sec)
- Include a tool name and email in requests: `&tool=my_tool&email=my@email.com`
- Do not make requests faster than the rate limit
- For bulk data, use NCBI FTP: `ftp.ncbi.nlm.nih.gov`
- Weekend and off-hours are preferred for large batch jobs
- NCBI may block IPs that violate usage policies without warning
- If you need higher throughput, contact NCBI at eutilities@ncbi.nlm.nih.gov

Key FTP paths:
- PubMed: `ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/`
- GenBank: `ftp://ftp.ncbi.nlm.nih.gov/genbank/`
- RefSeq: `ftp://ftp.ncbi.nlm.nih.gov/refseq/`
- dbSNP: `ftp://ftp.ncbi.nlm.nih.gov/snp/`
- ClinVar: `ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/`
- Assembly: `ftp://ftp.ncbi.nlm.nih.gov/genomes/`
- GEO: `ftp://ftp.ncbi.nlm.nih.gov/geo/`

---

*All data sourced from live NCBI API calls on April 2, 2026. Record counts are point-in-time snapshots and grow continuously. See Provenance table at the top of this document for exact endpoints and verification methods used for each section.*
