# NCBI KG prototype: SME feedback (March 2026)

Feedback from two NCBI subject matter experts testing the KG prototype interface. This feedback defines the types of questions the system must handle and the quality bar for answers.

---

## Feedback 1: ClinVar SME (senior)

Date: March 9, 2026

### Issue 1: out-of-scope queries should say so

"If we ask something that is out of scope, it should tell us that, rather than just say 0 results."

Implication: the agent needs a scope-awareness layer. When the graph doesn't contain relevant data, the response should explain what's missing and why, not return an empty result.

### Issue 2: sample query "which genes are located in the mitochondria?"

- Result list truncated at 200. Asking for the full list returned 0 results.
- Ambiguity not handled: does the query mean genes literally on mitochondrial DNA, or genes encoding mitochondrial proteins? The results didn't distinguish these, and the answer was wrong for both interpretations.

Implication: the agent must detect ambiguous queries and either ask for clarification or answer both interpretations explicitly.

### Issue 3: "What diseases are caused by variants in the HNF1A gene?"

- Text answer was acceptable.
- Table showed 13 variants with no explanation of why these 13. ClinVar has 200+ pathogenic/likely pathogenic variants in HNF1A.
- Not clear whether the 13 were random, most-submitted, most-frequent, or most-cited.

Implication: when showing a subset, the agent must state the selection criteria ("showing top 13 by submission count out of 247 pathogenic variants") and offer access to the full list.

### Issue 4: "What genes are associated with MODY?"

- Returned 6 genes (correct but incomplete).
- OMIM phenotypic series lists 14 genes.
- MedGen has the phenotypic series and individual MODY subtypes connected.

Implication: the system must traverse MedGen phenotypic series and OMIM, not just direct gene-disease edges in ClinVar. Incomplete answers from a single source erode trust.

### Issue 5: "Which genes have the most disease-causing variants?"

- Top results (DMD, TSC2, PKD1) were correct globally but not scoped to glucose metabolism.
- The prototype searched all of ClinVar rather than the domain-relevant subset.

Implication: the agent must understand domain context. If the system is scoped to glucose metabolism, queries should respect that scope unless the user explicitly asks for global results.

### Issue 6: "which genes are involved in glucose metabolism?"

- Returned 0 results.
- This is a core use case for the prototype.

Implication: Gene Ontology terms (e.g., "glucose metabolic process") should be used to build gene lists. The SME suggested using Gene database with GO term filtering: taxonomy ID 9606 + GO terms containing "glucose metabolic."

### Issue 7: "Which genes have both deletions and single nucleotide variants?"

- Found 4 genes (DOK7, IDUA, SURF1, MMACHC), none glucose metabolism related.
- HNF1A definitely has both deletions and SNVs but wasn't returned.

Implication: variant type filtering is broken or incomplete. The graph must have variant type annotations (from Sequence Ontology) to support this query pattern.

### Issue 8: "Describe the spectrum of mutations for HNF1A variants that cause MODY"

- Answer was very general with only 5 variants listed.
- Expected: specific summary statistics ("50% are SNVs, 20% are deletions, 10% are insertions. Missense variants are most common. Pathogenic variants cluster in exons 1-4.")

Implication: the agent needs to compute aggregate statistics over the graph, not just list individual records. This requires a different retrieval pattern: aggregate Cypher queries that count and group, not just MATCH and RETURN.

---

## Feedback 2: ClinVar team member

Date: March 2026

### Queries that returned zero results (should have returned results)

All of these are standard, biologically relevant queries:

| Query | Expected behavior |
|---|---|
| What are pathways involved in glucose metabolism? | Return GO biological process terms and associated genes |
| What are pathways associated with SLC2A2? | Return GO terms and pathway annotations for this gene |
| What are the most common genes involved in familial diabetes? | Return gene-disease associations from ClinVar + MedGen |
| What are insulin-related pathways? | Return GO terms containing "insulin" |
| What proteins are involved in beta-thalassemia? | Return HBB and related proteins from Gene + ClinVar |
| What pathways does the TP53 gene participate in? | Return GO biological process annotations for TP53 |
| What are the genes associated with Marfan syndrome? | Return FBN1 and others from ClinVar + OMIM |
| What diseases are caused by variants in the OPTN gene? | Return disease associations from ClinVar |
| What are the genes involved in kidney cancer? | Return gene-disease associations |
| What are pathways involved in autosomal recessive nonsyndromic hearing loss? | Return pathway annotations for associated genes |
| What genes are associated with familial hypercholesterolemia? | Return LDLR, PCSK9, APOB from ClinVar |
| What pathways are involved with hypercholesterolemia? | Return lipid metabolism GO terms |
| What are pathways involved in familial breast cancer? | Return DNA repair and tumor suppressor pathways |

### Queries with incomplete or incorrect results

"Show me examples of BRCA1 pathogenic variants?"
- Returned only 9 pathogenic SNVs. Seems very limited. Did not specify variant type but only got SNVs.

"What disease is caused by variants in MYO6?"
- Correctly identified autosomal dominant and recessive hearing loss. But also returned 10 specific variants that were not requested.

"What are genes associated with glaucoma?"
- Found only 5 genes (likely truncated). Included GALM (associated with galactosemia), which is incorrect, likely a hallucination.

"What is FBN1?" (and similar gene symbol queries)
- Responses were very brief and lacked detail.

---

## Summary: what the system must handle

### Query patterns that must work

| Pattern | Example | What it requires in the graph |
|---|---|---|
| Gene-to-disease | "What diseases are caused by variants in HNF1A?" | Gene -> Variant -> Disease edges (ClinVar) |
| Disease-to-gene | "What genes are associated with MODY?" | Disease -> Gene edges (ClinVar + MedGen + OMIM phenotypic series) |
| Gene-to-pathway | "What pathways does TP53 participate in?" | Gene -> GO biological process edges (gene2go) |
| Pathway-to-gene | "What genes are involved in glucose metabolism?" | GO term -> Gene edges (gene2go with GO term filtering) |
| Variant spectrum | "Describe the mutation spectrum for HNF1A" | Aggregate queries over variant types (Sequence Ontology) |
| Variant filtering | "Which genes have both deletions and SNVs?" | Variant type annotations on variant nodes |
| Cross-database | "Trace from variant to gene to pathway to disease" | Multi-hop traversal across ClinVar, Gene, GO, MedGen |
| Scope awareness | "Which genes have the most disease-causing variants?" | Respect domain scope or state that results are global |
| Out-of-scope | Any query outside the graph's coverage | Explain what's missing, don't return empty results |
| Ambiguous queries | "Genes in the mitochondria" | Detect ambiguity, answer both interpretations or ask for clarification |
| Aggregate statistics | "What percentage of variants are missense?" | Cypher COUNT/GROUP BY queries, not just individual records |
| Subset explanation | Any truncated result list | State selection criteria and offer full list |

### Quality bar (from SME expectations)

- Complete, not partial: if OMIM lists 14 MODY genes, return 14, not 6
- Specific, not generic: variant spectrum answers should include percentages and distributions
- Transparent about limitations: say "showing 13 of 247" not just show 13
- Domain-aware: respect the scope of the system or be explicit when going global
- No hallucinations: GALM is not a glaucoma gene. Every returned entity must be grounded in graph data.

---

*Reformatted: April 2, 2026. Original feedback from March 2026 SME testing sessions.*
