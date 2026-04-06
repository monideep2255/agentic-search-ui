# What success looks like

What the NCBI agentic search system looks and feels like when it's working. Concrete scenarios, not abstractions.

---

## The researcher's experience

### Scenario 1: clinical geneticist investigating a patient's variant

Today (30-60 minutes):
1. Opens ClinVar, searches for the variant by HGVS notation
2. Finds the ClinVar record, notes the gene and clinical significance
3. Opens a new tab, goes to Gene, searches for the gene
4. Reads the gene summary, checks associated pathways
5. Opens another tab, goes to PubMed, searches gene + disease
6. Scans 50 abstracts to find relevant ones
7. Opens OMIM to check inheritance pattern
8. Opens GTR to see if other labs offer testing
9. Manually writes up a summary connecting all of this

With this system (10 seconds):

```
Query: "What do we know about NM_000277.3:c.1222C>T in PKU?"

Streaming response:
  Searching ClinVar... Found: VCV000000037, pathogenic, reviewed by expert panel
  Searching Gene... Found: PAH (phenylalanine hydroxylase), chromosome 12q23.2
  Searching MedGen... Found: Phenylketonuria (MONDO:0009861)
  Checking PubMed... 847 publications for PAH + PKU, 23 specifically cite this variant
  Checking on-demand APIs...
    LitVar2: 156 publications specifically for rs5030858
    ClinicalTrials.gov: 12 active trials for PKU treatment

Answer:
  NM_000277.3:c.1222C>T (p.Arg408Trp, rs5030858) is a pathogenic variant in
  the PAH gene, classified as pathogenic by expert panel review in ClinVar
  (VCV000000037). This is the most common PKU-causing variant in European
  populations.

  Gene: PAH encodes phenylalanine hydroxylase, which catalyzes the conversion
  of phenylalanine to tyrosine. Loss of function leads to phenylalanine
  accumulation (PKU). [Gene:5053]

  Disease: classic phenylketonuria (MONDO:0009861). Autosomal recessive
  inheritance. [MedGen:C0031485, OMIM:261600]

  Literature: 156 publications cite this specific variant. Key findings:
  - Most common PKU allele in European populations (PMID:1234567)
  - Associated with classic (severe) PKU phenotype (PMID:2345678)
  - Residual enzyme activity <1% in functional studies (PMID:3456789)

  Active trials: 12 trials for PKU, including gene therapy (NCT04480567)
  and enzyme substitution (NCT03752515).

  [View graph: PAH gene -> variant -> PKU disease -> 23 publications -> 12 trials]
```

The graph visualization shows every entity as a clickable node. Click the variant node to open ClinVar. Click a publication to open PubMed. Click a trial to open ClinicalTrials.gov.

---

### Scenario 2: drug researcher exploring a target

```
Query: "What genes are involved in GLP-1 signaling and what variants
        in those genes affect diabetes risk?"

Answer:
  GLP-1 signaling pathway involves 8 key genes. 4 have clinically
  significant variants associated with diabetes:

  | Gene | Variants (pathogenic/likely pathogenic) | Disease association | Publications |
  |------|---------------------------------------|-------------------|-------------|
  | GLP1R | 12 | Type 2 diabetes, obesity | 89 |
  | GCG | 3 | Hyperglycemia | 34 |
  | PCSK1 | 7 | Obesity, impaired proinsulin processing | 56 |
  | TCF7L2 | 23 | Type 2 diabetes (strongest common risk) | 412 |

  [View graph: GLP-1 pathway -> 8 genes -> 45 variants -> 4 diseases -> 591 papers]
```

The graph shows the pathway as a hub, genes as connected nodes, variants branching from each gene, diseases connected to variants, and publications as the outer ring. All clickable.

---

### Scenario 3: the AI agent experience (MCP)

A researcher is talking to Claude about their work. They mention a gene. Claude automatically queries the NCBI MCP server:

```
Researcher: "I'm studying FOXP3 and its role in autoimmune diseases.
             What should I know about the variant landscape?"

Claude's internal process:
  [Calling ncbi_search: "FOXP3 variants associated with autoimmune diseases"]

Claude's response (enriched with NCBI data):
  FOXP3 (NCBIGene:50943) is the master regulator of regulatory T cells.
  ClinVar lists 287 variants, of which 34 are pathogenic/likely pathogenic.
  The most clinically significant are associated with IPEX syndrome
  (immune dysregulation, polyendocrinopathy, enteropathy, X-linked).

  Key variants to know about:
  - c.1150G>A (p.Ala384Thr): pathogenic, 12 clinical submissions
  - c.748delA: pathogenic, frameshift, loss of function
  - c.227delT: pathogenic, most frequently reported in IPEX

  There are currently 3 active clinical trials targeting FOXP3 pathways
  for autoimmune conditions.

  Sources: ClinVar, Gene, MedGen, PubMed (47 papers), ClinicalTrials.gov
```

The researcher never visited NCBI. The agent did it for them. This is the dominant usage pattern within 2-3 years.

---

### Scenario 4: the bioinformatician (CLI)

```bash
$ ncbi-search "pathogenic BRCA1 variants" --format tsv | head -5
variant_id      gene    hgvs_protein    significance    publications    trials
rs80357906      BRCA1   p.Glu1735Ter    Pathogenic      744            3
rs80357713      BRCA1   p.Arg1699Trp    Pathogenic      523            1
rs28897696      BRCA1   p.Arg1443Ter    Pathogenic      312            2
rs80357711      BRCA1   p.Gly1706Glu    Pathogenic      187            0

$ ncbi-search traverse --from gene:672 --rel has_variant \
    --filter significance=pathogenic --format json | \
    jq '.[] | {variant: .hgvs, disease: .associated_diseases[0]}' | head -3
{"variant": "p.Glu1735Ter", "disease": "Hereditary breast and ovarian cancer"}
{"variant": "p.Arg1699Trp", "disease": "Hereditary breast and ovarian cancer"}
{"variant": "p.Arg1443Ter", "disease": "Hereditary breast and ovarian cancer"}

$ ncbi-search batch my_gene_list.txt --output results/
Processing 50 genes... done. Results in results/
  50 gene summaries
  1,247 pathogenic variants
  3,891 supporting publications
```

Pipe-friendly. Scriptable. Every output format works with standard Unix tools.

---

### Scenario 5: the data scientist (KGX export)

```python
import pandas as pd

# Download the gene-disease subgraph
nodes = pd.read_csv("https://ncbi-search.org/api/v1/export/gene-disease/nodes.tsv", sep="\t")
edges = pd.read_csv("https://ncbi-search.org/api/v1/export/gene-disease/edges.tsv", sep="\t")

print(f"Nodes: {len(nodes):,}")   # Nodes: 94,234
print(f"Edges: {len(edges):,}")   # Edges: 847,291

# Load into NetworkX for analysis
import networkx as nx
G = nx.from_pandas_edgelist(edges, source="subject", target="object", edge_attr=True)

# Find the most connected disease
disease_nodes = nodes[nodes["category"] == "biolink:Disease"]
degree = {n: G.degree(n) for n in disease_nodes["id"] if n in G}
top_diseases = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]
```

BioLink-compliant. Importable into Neo4j, NetworkX, RDF stores, or any KGX-compatible tool. Monthly snapshots for reproducibility.

---

## The numbers that define success

### At launch (week 8)

| Metric | Target |
|---|---|
| Databases in graph | 6 (Gene, PubMed, ClinVar, MedGen, Taxonomy, SNP clinical subset) |
| Databases on-demand | 30+ via ELink |
| Graph nodes | 150M+ |
| Graph edges | 500M+ (cross-database relationships) |
| CQ test skeletons passing | 20+ |
| End-to-end query latency | < 10 seconds |
| Access channels | 5 (Web UI, MCP, API, CLI, KGX) |
| Evaluation golden datasets | 20-30 curated QA pairs |
| Answer grounding rate | > 85% (every claim traceable to graph data) |

### At 3 months post-launch

| Metric | Target |
|---|---|
| GitHub stars | 100+ |
| PyPI installs (CLI) | 500+ |
| MCP integrations | Used by at least 2 AI agent platforms |
| Research queries per week | 100+ (from early adopters) |
| Publication | Submitted to Bioinformatics or NAR |
| Additional databases | 2-3 more fully ingested (OMIM, PubChem, Protein) |

### At 1 year

| Metric | Target |
|---|---|
| Dominant usage channel | MCP (agent-to-agent > human queries) |
| Community contributors | 10+ |
| Federated KGs importing this data | 2+ (Monarch, Translator) |
| NCBI adoption | Internal team using it or forked it |
| Paper citations | First citations from researchers who used the tool |

---

## What success feels like

For the researcher: "I asked one question and got an answer that would have taken me an hour to assemble manually. Every fact links back to the source. I trust it because I can verify it."

For the AI agent: "I called one MCP tool and got structured, cited biomedical knowledge. I can give my user a better answer than I could from my training data alone."

For the bioinformatician: "I piped a gene list through the CLI and got a complete variant landscape in 30 seconds. No manual curation needed."

For the data scientist: "I downloaded the KGX export, loaded it into NetworkX, and ran my analysis in 10 lines of Python. BioLink-compliant, reproducible, monthly updates."

For the open source community: "Finally, an open-source agentic search for NCBI. I can contribute a new database pipeline, and it plugs into the existing merge and search architecture."

For your career: "I designed and built a system that connects 39 NCBI databases, serves 5 access channels, and uses 8 AI agents, open sourced it, published a paper, and it costs $300-500 to run. This is the portfolio piece."

---

*Created: April 2, 2026.*
