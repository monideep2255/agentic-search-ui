# NCBI repos deep dive

What we learned from analyzing 13 repositories in the NCBI GitHub org (out of ~200 total), and how each finding maps to a concrete decision, code artifact, or learning for System 3.

## Table of contents

- [How to read this doc](#how-to-read-this-doc)
- [Code you can reuse directly](#code-you-can-reuse-directly)
- [Architecture decisions this informs](#architecture-decisions-this-informs)
- [Tech stack choices confirmed or changed](#tech-stack-choices-confirmed-or-changed)
- [Patterns to adopt from NCBI's own tools](#patterns-to-adopt-from-ncbis-own-tools)
- [What NOT to build (use hosted services instead)](#what-not-to-build-use-hosted-services-instead)
- [Future capabilities to revisit after Phase 4](#future-capabilities-to-revisit-after-phase-4)
- [Repo-by-repo reference card](#repo-by-repo-reference-card)
- [Repos we filtered out](#repos-we-filtered-out)

---

## How to read this doc

This is not a survey of interesting repos. It is a decision-support document organized by the question "what do I do with this?" Each section maps findings to a specific action: code to copy, an architecture call to make, a tool to avoid building, or a pattern to adopt.

When you are implementing a specific tool (e.g., `ncbi_dbsnp`), jump to the repo reference card for that tool's upstream repo. When you are making an architecture decision (e.g., how to handle entity resolution), read the relevant section for the trade-offs we uncovered.

---

## Code you can reuse directly

### dbSNP Variation Services wrapper (`navs.py`)

Source: [ncbi/dbsnp](https://github.com/ncbi/dbsnp) (143 stars)

The `lib/python/navs.py` file is a ready-made Python wrapper around the NCBI Variation Services API (`https://api.ncbi.nlm.nih.gov/variation/v0/`). It auto-detects input type (rsID, SPDI, HGVS, VCF) and returns structured data.

What to copy into our `ncbi_dbsnp` tool:
- The `Variation` class that accepts any variant format and normalizes it
- The conversion methods: `asSpdiList()`, `asHgvsList()`, `asVcfList()`, `asRsidList()`
- The attribute extractor in `rsatt.py` for pulling frequencies by study (gnomAD, TopMed, ExAC)

What to add on top:
- Provenance fields (`source`, `source_id`, `source_url`, `layer`) per our citation requirements
- Rate limiting (1 rps for Variation Services, 10 rps for E-utilities with API key)
- Error handling and retry logic (the original wrapper has none)
- Clinical significance extraction from the allele annotations JSON

Rate limits:
- Variation Services API: 1 request/second (IP-based, no auth needed)
- E-utilities: 3 rps default, 10 rps with API key (free from NCBI account settings)

### NCBI Datasets API endpoints for gene/genome lookups

Source: [ncbi/datasets](https://github.com/ncbi/datasets) (530 stars)

107+ REST endpoints at `https://api.ncbi.nlm.nih.gov/datasets/v2`. No official Python SDK exists, but the API is clean REST with OpenAPI spec available (`datasets.openapi.yaml`).

Endpoints most relevant to our tools:
- Gene lookup: `GET /gene/id/{gene_ids}/dataset_report`
- Gene by symbol: `GET /gene/symbol/{symbols}/taxon/{taxon}/`
- Orthologs: `GET /gene/id/{gene_id}/orthologs`
- Taxonomy: `GET /taxonomy/taxon/{taxons}`

Output formats via Accept header: `application/json`, `application/x-ndjson`, `text/tab-separated-values`, `application/zip`

Auth: HTTP header `api-key: YOUR_KEY` or query param `?api_key=YOUR_KEY`. Free tier, no credit card. 10 rps with key.

---

## Architecture decisions this informs

### Decision 1: two-API strategy for Layer 2

NCBI Datasets and E-utilities cover complementary domains. Neither covers everything.

| Data need | Use Datasets API | Use E-utilities |
|-----------|-----------------|-----------------|
| Gene records | Yes (primary) | Fallback |
| Genome metadata | Yes | No |
| Orthologs | Yes (native endpoint) | No (manual via elink) |
| Taxonomy | Yes | No |
| ClinVar variants | No (not in Datasets) | Yes (primary) |
| dbSNP variants | No (not in Datasets) | Yes + Variation Services API |
| PubMed literature | No (not in Datasets) | Yes (primary) |
| OMIM disease records | No (not in Datasets) | Yes (primary) |

Implication: our Layer 2 tool implementations need to know which API to call for each data type. This is not a "pick one" decision. Both APIs are needed.

### Decision 2: PubTator REST API for entity resolution (not local models)

Three NCBI repos offer entity resolution capabilities: AIONER (NER), GNorm2 (gene normalization), tmVar3 (variant normalization). All three are heavy:
- AIONER: TensorFlow, 500MB models, 50-350ms
- GNorm2: 60GB JVM heap, Java + Python hybrid
- tmVar3: 5GB JVM, pure Java, CRF++ dependency

PubTator3's REST API wraps all three behind a single cloud endpoint. It accepts raw text and returns normalized entities with database IDs (Gene IDs, MeSH IDs, rsIDs).

Trade-off: network latency (~100-500ms per request) vs. local infrastructure burden (60GB+ memory, Java + Python + TensorFlow).

Recommendation: use PubTator REST API for entity resolution in the Think step. If latency becomes a bottleneck, revisit AIONER as a lightweight local NER option (it's the smallest of the three at 500MB).

### Decision 3: ClinVar has three classification systems now

As of May 2024, ClinVar serves three distinct classification types:

1. Germline (traditional): Pathogenic, Likely pathogenic, Uncertain significance, Likely benign, Benign
2. Somatic clinical impact (new): Tier I (strong), Tier II (potential), Tier III (unknown), Tier IV (benign)
3. Oncogenicity (new): Oncogenic, Likely oncogenic, Uncertain, Likely benign, Benign

Our agent's responses must surface which classification system applies to each variant. A variant can have all three classifications simultaneously. The 4-star review status (practice guideline > expert panel > criteria provided > no assertion criteria) indicates consensus level and should feed into our citation confidence scoring.

---

## Tech stack choices confirmed or changed

### Confirmed: E-utilities for ClinVar queries

ClinVar access works through E-utilities with `db=clinvar` using VCV (Variation-Centric View) format. The repo confirms no alternative API exists. FTP is available for bulk downloads but not suitable for real-time agent queries.

Query pattern: `esearch` to find VCV IDs, then `efetch` with `rettype=vcv` for full XML records. Parse for: VCV accession, gene(s), condition(s), classification(s), review status, citations (PMIDs), submitters.

### Confirmed: separate tools per data layer

GeneGPT's architecture validates our "one tool, one layer" design. GeneGPT uses esearch -> efetch chains for each database independently. It does not mix database queries in a single tool call. Our adapter pattern (QueryAdapter, FacetAdapter, CitationAdapter, etc.) is the right abstraction.

### New: Variation Services API alongside E-utilities for dbSNP

The dbsnp repo reveals a second API beyond E-utilities: the Variation Services API at `api.ncbi.nlm.nih.gov/variation/v0/`. This is more modern (proper REST, JSON responses) but has a tighter rate limit (1 rps vs 10 rps). Use Variation Services for individual variant lookups (rsID -> full record) and E-utilities for batch searches (gene name -> all pathogenic variants).

---

## Patterns to adopt from NCBI's own tools

### Pattern 1: demonstrations over documentation (from GeneGPT)

GeneGPT's key finding: showing the LLM concrete API call examples with real results produced better tool use than providing API documentation. Their in-context learning approach used 4 worked examples covering single-hop lookups, entity linking, multi-entity queries, and sequence alignment.

How to apply: our agent's system prompt should include worked examples of each tool call with real input/output pairs, not just tool schemas. When we add a new tool, write 2-3 demonstration examples as part of the tool definition.

### Pattern 2: conservative multiplicative fusion for citations (from BmCS)

The biomedical-citation-selector uses multiplicative probability fusion: `final_score = voting_ensemble_prob x cnn_prob`. This creates a "both models must agree" effect that prevents weak evidence from inflating citation confidence.

How to apply: our citation confidence scoring should multiply independent signals rather than averaging them. For example: `citation_confidence = graph_provenance_score x api_freshness_score x source_authority_score`. A citation must score well on ALL dimensions to surface as high confidence.

### Pattern 3: BIO tagging with entity type markers (from AIONER and BioREx)

Both AIONER and BioREx use special tokens to mark entity boundaries and types in text: `@GeneOrGeneProductSrc$ IL-6 @/GeneOrGeneProductSrc$`. This pattern lets transformers attend to entity structure explicitly.

How to apply: if we build any local NER/RE models in the future, adopt this entity marker convention. It is compatible with PubTator's output format, so results from PubTator API can be reformatted into this pattern.

### Pattern 4: iterative context building with execution trace (from GeneGPT)

GeneGPT appends each API call and its result to the prompt context: `q_prompt += f'{text}->[{call}]\n'`. This maintains a full execution trace that the LLM can reference when deciding the next action.

How to apply: our LangGraph agent state should include the full tool call history (tool name, parameters, truncated result) so the synthesis step can reference what was queried and what was found. This also enables debugging: the trace shows exactly which API calls led to the final answer.

What to avoid from GeneGPT's approach:
- Do not append raw API responses (they used full JSON, causing context bloat). Summarize to key fields.
- Do not truncate from the start of context (they pruned oldest examples first, losing the demonstrations). Preserve system prompt and demonstrations, truncate oldest intermediate results.
- Do not use regex URL extraction. Use structured tool calling.

---

## What NOT to build (use hosted services instead)

| Capability | Repo that offers it | Why not build locally | What to use instead |
|-----------|--------------------|-----------------------|-------------------|
| Gene normalization | GNorm2 | 60GB JVM heap, Java + Python hybrid, 30-60s startup | PubTator REST API |
| Variant normalization | tmVar3 | 5GB JVM, pure Java, CRF++ dependency, no Python API | PubTator REST API |
| Full NER + normalization + RE pipeline | AIONER + GNorm2 + tmVar3 + BioREx | 4 separate tools, mixed languages, 65GB+ memory | PubTator3 REST API (wraps all four) |
| PubMed article embeddings | MedCPT | 37 chunks x 1GB = 37GB storage for pre-computed embeddings | Not needed until Phase 4+ |

The PubTator3 REST API endpoint: `https://www.ncbi.nlm.nih.gov/research/pubtator3-api/`
- Accepts raw text via POST
- Returns JSON with entities (normalized to database IDs) and relations
- Covers all 6 entity types (gene, disease, variant, chemical, species, cell line)
- Free, no auth required

---

## Future capabilities to revisit after Phase 4

These repos offer capabilities that are not needed for the initial build but become relevant once the core agent loop is working and we are optimizing retrieval quality.

### MedCPT for semantic search over PubMed

Source: [ncbi/MedCPT](https://github.com/ncbi/MedCPT) (257 stars)

What it is: a bi-encoder (query encoder + article encoder) plus a cross-encoder re-ranker, trained on 255 million real PubMed search log pairs. 110M parameters (PubMedBERT base). Pre-computed embeddings for 31M PubMed articles available on NCBI FTP.

Why wait: our Layer 3 enrichment does not yet include PubMed semantic search. When it does, MedCPT provides:
- Query encoding in <100ms on GPU
- Pre-computed article embeddings (download, no need to encode 31M articles)
- FAISS-compatible vectors for sub-millisecond retrieval
- Cross-encoder re-ranking for precision on top-k results

Models on HuggingFace: `ncbi/MedCPT-Query-Encoder`, `ncbi/MedCPT-Article-Encoder`, `ncbi/MedCPT-Cross-Encoder`

### BioConceptVec for query expansion

Source: [ncbi/BioConceptVec](https://github.com/ncbi/BioConceptVec) (43 stars)

What it is: 400K+ biomedical concept embeddings (100D) covering genes (98% of human genes), diseases, chemicals, mutations, cell lines. Four algorithms available (CBOW, Skip-gram, GloVe, fastText).

Why wait: our LLM already handles semantic understanding of biomedical queries. But if recall is a bottleneck (user asks about a gene synonym the graph does not index), concept vectors could expand the query with related terms. Lightweight: 800MB JSON or 2.4GB binary per algorithm.

### BioREx for knowledge graph edge validation

Source: [ncbi/BioREx](https://github.com/ncbi/BioREx) (44 stars)

What it is: the relation extraction engine behind PubTator3. 41 relation types (INHIBITOR, BIND, Positive_Correlation, mechanism, etc.) across gene-disease, drug-gene, protein-protein pairs. BioLinkBERT-based, ~50-200ms per entity pair on GPU.

Why wait: our knowledge graph already has 693M edges with typed relationships. BioREx becomes useful when we want to validate graph edges against recent literature ("is this gene-disease association still supported by new publications?") or discover edges the graph does not yet contain.

Note: BioREx relation types do NOT map directly to BioLink model predicates. A custom mapping layer would be needed (e.g., BioREx "INHIBITOR" -> BioLink `biolink:decreases_activity_of`).

---

## Repo-by-repo reference card

Quick-lookup table for when you are implementing a specific tool and need to check the upstream repo.

### GeneGPT (424 stars)

- Repo: [ncbi/GeneGPT](https://github.com/ncbi/GeneGPT)
- What: LLM + NCBI API agent. Iterative prompt-context loop with regex URL extraction.
- Language: Python. Dependencies: openai, pandas.
- Key files: `main_turbo.py` (agent loop), `evaluate.py` (task eval), `data/geneturing.json` (400 QA pairs)
- Accuracy: 0.83 average on GeneTuring benchmark (vs 0.12 for ChatGPT alone)
- Lesson: demonstrations > documentation. Concrete API call examples with real results outperform API docs in prompts.
- Limitation: no error handling, no provenance tracking, regex-based tool calling, 10-call hard limit, context truncation from start (loses demonstrations)
- Use for: reference architecture. Do not copy code directly.

### NCBI Datasets (530 stars)

- Repo: [ncbi/datasets](https://github.com/ncbi/datasets)
- What: modern REST API for genes, genomes, orthologs, taxonomy. 107+ endpoints.
- Language: Jupyter Notebook (tutorials), OpenAPI spec (YAML)
- Key files: `datasets.openapi.yaml` (full API spec), `training/NCBI_Datasets_Orthologs.ipynb` (worked examples)
- Coverage: Gene, Genome, Virus, Taxonomy, Organelle, BioSample, Protein. Does NOT cover ClinVar, dbSNP, OMIM, PubMed.
- Rate limit: 5 rps default, 10 rps with API key
- Use for: Layer 2 gene/genome/ortholog lookups. Complement with E-utilities for variants and literature.

### dbSNP (143 stars)

- Repo: [ncbi/dbsnp](https://github.com/ncbi/dbsnp)
- What: schemas, tutorials, Python wrappers for dbSNP data access
- Language: Python, Jupyter Notebook, C++, Perl
- Key files: `lib/python/navs.py` (Variation Services wrapper), `lib/python/rsatt.py` (attribute extraction), `tutorials/rsjson_demo.py` (JSON parsing)
- APIs: Variation Services (`api.ncbi.nlm.nih.gov/variation/v0/`, 1 rps) and E-utilities (`db=snp`, 10 rps with key)
- Input types: rsID, SPDI, HGVS, VCF (auto-detected)
- Output fields: genomic position, alleles, clinical significance, frequencies (gnomAD, TopMed, ExAC), gene annotations, transcript/protein changes, citations
- Use for: direct code reuse in `ncbi_dbsnp` tool

### ClinVar (83 stars)

- Repo: [ncbi/clinvar](https://github.com/ncbi/clinvar)
- What: schemas, sample data, API documentation, prototypes for new classification types
- Language: HTML, JSON schemas
- Three classification systems: germline (Pathogenic/Benign/VUS), somatic clinical impact (Tiers I-IV, new May 2024), oncogenicity (Oncogenic/Benign, new May 2024)
- Review status: 4-star system (practice guideline > expert panel > criteria provided > no assertion criteria)
- Cross-references: Gene, dbSNP, MedGen (primary condition identifier), OMIM, HP, MONDO
- Access: E-utilities with `db=clinvar`, VCV format recommended. FTP for bulk downloads.
- Use for: understanding ClinVar data model when building ClinVar query tools

### MedCPT (257 stars)

- Repo: [ncbi/MedCPT](https://github.com/ncbi/MedCPT)
- What: contrastive pre-trained transformer for zero-shot biomedical retrieval
- Language: Python (PyTorch, Transformers)
- Architecture: bi-encoder (110M params each for query and article) + cross-encoder re-ranker (110M params)
- Training: 255M real PubMed search log query-article pairs
- Pre-computed: embeddings for 31M PubMed articles on NCBI FTP (37 chunks, ~1GB each)
- Latency: query encoding ~50-100ms (GPU), FAISS retrieval <1ms for 30M docs, re-ranking ~5-10ms for 100 docs
- HuggingFace: `ncbi/MedCPT-Query-Encoder`, `ncbi/MedCPT-Article-Encoder`, `ncbi/MedCPT-Cross-Encoder`
- Use for: Phase 4+ semantic search over PubMed

### AIONER (65 stars)

- Repo: [ncbi/AIONER](https://github.com/ncbi/AIONER)
- What: all-in-one biomedical NER. 6 entity types: gene, disease, variant, chemical, species, cell line.
- Language: Python (TensorFlow 2.x, Transformers)
- Models: Bioformer-softmax (faster) or PubMedBERT-CRF (more accurate). ~500MB total.
- Latency: 50-350ms per document (GPU), 200-570ms (CPU)
- Limitation: recognition only, no normalization to database IDs. Must chain with PubTator API for ID resolution.
- HuggingFace: `lingbionlp/AIONER-0415`
- Use for: if PubTator API latency is too high, AIONER is the lightweight local alternative for entity recognition only

### BioREx (44 stars)

- Repo: [ncbi/BioREx](https://github.com/ncbi/BioREx)
- What: biomedical relation extraction (the RE engine behind PubTator3)
- Language: Python (TensorFlow 2.x, Transformers)
- Relations: 41 types across gene-disease, drug-gene, chemical-disease, protein-protein pairs
- Model: BioLinkBERT-base (preferred) or PubMedBERT-base. ~110M params.
- Latency: ~50-200ms per entity pair (GPU)
- Limitation: does not use BioLink predicates natively (custom mapping needed). Sentence-level only.
- Trained on: BioRED, CDR, DDI, AIMED, DrugProt, PharmGKB, DisGeNET (11 datasets)
- Use for: Phase 4+ KG edge validation against literature

### GNorm2 (29 stars)

- Repo: [ncbi/GNorm2](https://github.com/ncbi/GNorm2)
- What: gene name recognition and normalization to NCBI Gene IDs
- Language: Python (NER/species assignment) + Java (normalization scoring)
- Architecture: 3-stage pipeline: species recognition -> gene NER (Bioformer/PubMedBERT) -> scoring-based normalization
- Requirement: 60GB JVM heap for normalization stage
- Handles ambiguity: abbreviation resolution (Ab3P), multi-species disambiguation, synonym/variant matching
- Use for: do NOT run locally. Use PubTator REST API instead.

### tmVar3 (23 stars)

- Repo: [ncbi/tmVar3](https://github.com/ncbi/tmVar3)
- What: variant mention recognition and normalization
- Language: Pure Java (9K LOC)
- Formats: DNA-level (HGVS c.), protein-level (p.M1V), rsIDs, indels, CNVs
- Database: SQLite `rs2gene.db` maps rs IDs to Gene IDs
- Requirement: 5GB JVM, CRF++ binary
- Use for: do NOT run locally. Use PubTator REST API instead.

### Biomedical citation selector (13 stars)

- Repo: [ncbi/biomedical-citation-selector](https://github.com/ncbi/biomedical-citation-selector)
- What: production ML system for MEDLINE citation classification. Processes 50K citations/day.
- Language: Python (scikit-learn, TensorFlow/Keras)
- Architecture: dual ensemble (4 classical ML learners via TF-IDF + CNN with word embeddings). Multiplicative fusion.
- Performance: 83% recall, 92% precision
- Key files: `BmCS/BmCS.py` (pipeline), `BmCS/model_utils.py` (fusion logic), `BmCS/bmcs_cnn_model.py` (CNN)
- Use for: pattern reference for citation confidence scoring. The multiplicative fusion concept is directly transferable.

### BioConceptVec (43 stars)

- Repo: [ncbi/BioConceptVec](https://github.com/ncbi/BioConceptVec)
- What: 400K+ biomedical concept embeddings trained on full PubMed corpus
- Dimensions: 100D vectors. Four algorithms: CBOW, Skip-gram, GloVe, fastText.
- Coverage: genes (98% of human genes), diseases, chemicals, mutations, cell lines
- Size: 800MB (JSON) or 2.4GB (binary) per algorithm
- Loading: `gensim.models.KeyedVectors.load_word2vec_format(path, binary=True)`
- Use for: Phase 4+ query expansion if recall is a bottleneck

### bert_gt (31 stars)

- Repo: [ncbi/bert_gt](https://github.com/ncbi/bert_gt)
- What: BERT + Graph Transformer for cross-sentence n-ary relation extraction
- Language: Python (TensorFlow 2.x)
- Innovation: neighbor-attention mechanism reduces noise in long sequences
- Performance: +5.44% accuracy over prior SOTA on n-ary relations
- Use for: reference only. BioREx covers our RE needs with simpler architecture.

---

## Repos we filtered out

The remaining ~187 repos in the NCBI org fall into categories irrelevant to System 3:

- Sequence analysis: sra-tools (1331 stars), SKESA, ngs, ngs-tools, BLAST tools, magicblast. We query structured data, not raw sequences.
- Genome annotation: pgap (376 stars), egapx (190 stars), amr (362 stars), stxtyper. Upstream pipeline tools, not search.
- Structural biology: icn3d (173 stars), SSDraw. 3D protein viewers, not our domain.
- Workflows: CWL pipelines, Docker configs. Infrastructure, not data access.
- Niche research: protein folding, tumor dynamics, population genetics, SELEX analysis.
- Legacy/deprecated: sratoolkit, various internal tools.
- Microbiology-specific: fcs (contamination screening), SRPRISM, ITSx.
- Infrastructure: gprobe, consul-announcer, finagle, logging tools.

---

Last updated: 2026-05-05
