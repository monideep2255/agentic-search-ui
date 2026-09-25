# Graph data hand over, 2026-09-25

A request from System 3 (this repository) to the data-engineering repository
(`reference/agentic-search-data-engineering`, System 1 and 2). System 3 reads
the graph read-only and never writes into it, per
`.claude/rules/file-protection.md`, so each item below is a request to fix at
the source rather than work this repository can do itself. Card 29,
product-owner decision of 2026-09-25 (`DECISIONS.md`, the row on card 12,
item 11.29, which hands these same gaps to the data repository).

Every item below names the exact measurement, its date and the query or probe
script that produced it, so a reader in the other repository can re-run it.

## Table of contents

- [One: Disease vertices are named after their source vocabulary](#one-disease-vertices-are-named-after-their-source-vocabulary)
- [Two: no Disease vertex has an outgoing has_phenotype edge](#two-no-disease-vertex-has-an-outgoing-has_phenotype-edge)
- [Three: the graph holds no MeSH term names](#three-the-graph-holds-no-mesh-term-names)
- [Four: the Gene vertex carries no facts](#four-the-gene-vertex-carries-no-facts)
- [What we are asking for](#what-we-are-asking-for)

## One: Disease vertices are named after their source vocabulary

What was measured: no `Disease` vertex's `name` property, graph-wide out of
200,845 rows, contains the word "syndrome". Sampled property bags show the
field instead holds the name of the vocabulary the row came from, such as
"MeSH", "MONDO", "MedGen" or "SNOMEDCT_US" rather than the name of the
disease: the eight diseases `FBN1` is associated with are named "GARD",
"MONDO" and "MedGen", and three arbitrary `Disease` vertices are named
"SNOMEDCT_US", "MedGen" and "MeSH".

When: the graph-wide "zero syndrome" measurement was taken on 2026-09-23.
The per-vertex pattern (names reading as a source vocabulary rather than a
disease) was first filed during build phase 2.1, on 2026-07-31, as finding
F-2.1-B07, which gives BRCA1's four diseases as its worked example rather
than a graph-wide count; that finding's status is recorded three different
ways across this repository's own records (closed in one place, in progress
in another, still open in a third), so treat it as background for the
pattern rather than as the source of the graph-wide number below.

By what query: `testing/Developer/reports/2026-09-23_overnight/probe_disease_names.py`,
the probe titled "Do ANY Disease vertices have a name that is not a source
vocabulary", `MATCH (d:Disease) WHERE d.name =~ $pattern RETURN d AS result
LIMIT 10` with `pattern = "(?i).*syndrome.*"`, zero rows returned. The same
file's other probes pulled the full property bags for the FBN1-linked
diseases and for three arbitrary `Disease` vertices, quoted above.

What a person using the product loses: a disease question, such as "what
conditions is BRCA1 associated with?", cannot be answered from the graph's
own disease names, because the graph does not hold disease names for the
diseases sampled. The graph already carries the correct CURIE for each
disease and the edge to the gene that causes it. Only the display name is
wrong for the vertices measured. This is the cheapest fix of the four items
here, because the field already exists and holds the wrong string; it does
not need a new column or a new ETL pass, only the correct value written into
the one that already exists.

## Two: no Disease vertex has an outgoing has_phenotype edge

What was measured: no `Disease` vertex in the graph has an outgoing
`has_phenotype` edge, graph-wide, with no filter applied. Every
`PhenotypicFeature` vertex sampled is an unpopulated stub of the shape
`[stub] HP:0000002`, with its `source` property reading `stub` and an empty
`source_url`.

When: measured live on 2026-09-23, using probes committed at
`testing/Developer/reports/2026-09-23_overnight/probe_disease_names.py` and
`probe_g022.py`. The `has_phenotype` edge label's endpoint pairs are recorded
separately, on 2026-09-14, in
`docs/data-engineering/Knowledge_graph_on_server_reference.md` section E
(edge labels and counts): that row names 6,076,735 `has_phenotype` rows and
gives both endpoint pairs the edge covers, "Disease to PhenotypicFeature, and
SequenceVariant to Disease", with a worked example of the second pair
(HNF1A, 2,075 rows over 1,158 variants and 36 diseases). No source cited here
gives a per-pair breakdown of the 6,076,735 total, so this hand-over does not
state what share of that total runs each way; what the 2026-09-23 probes
establish directly is that the `Disease` to `PhenotypicFeature` pair returns
zero rows when queried from the `Disease` side.

By what query: `MATCH (a)-[:has_phenotype]->(b) RETURN a AS result LIMIT 5`
and the matching query on the `b` side, plus a direct existence check for any
`Disease` vertex with an outgoing `has_phenotype` edge, and a sample of
`PhenotypicFeature` vertices to confirm they are unpopulated stubs, all in
`probe_disease_names.py`.

What a person using the product loses: a question about what a condition
looks like clinically, for example "what phenotypic features are associated
with Marfan syndrome?", could not be answered from this edge on 2026-09-23,
because the code asked the graph a relationship that returns zero rows from
the `Disease` side. As of this hand-over the product answers this class of
question through a different path (MedGen's own clinical-features field,
landed in build phase 8.1, `testing/Developer/reports/2026-09-25_phase_8.1/fix_round.md`),
not through this edge, so the graph still cannot cite its own phenotype data
for a `Disease` vertex even though the product's answer for this specific
example is no longer a refusal.

## Three: the graph holds no MeSH term names

What was measured: every `OntologyClass` vertex is named after its own
identifier rather than its term name, measured graph-wide: zero
`OntologyClass` names anywhere contain a lowercase run of four or more
letters, and zero contain "neoplasm", a common MeSH word. Five arbitrary
`OntologyClass` vertices and the 26 rows golden question G-019 actually
reaches are all named in the shape `[MeSH] D000001` rather than a term name.
A control query in the same probe confirms the graph is not broadly
unpopulated: the same `Article` vertex's `name` property holds its real
title, so this is a per-label mapping defect rather than a general gap.

When: measured graph-wide on 2026-09-23. Restated as an open item during the
phase 8 UI fix loop on 2026-09-24 (`testing/UI_fixes_done.md`).

By what query: `testing/Developer/reports/2026-09-23_overnight/probe_ontology_names.py`,
the probes titled "Does ANY OntologyClass name contain a spelled-out word
(lowercase run of 4+)" (`pattern = ".*[a-z]{4,}.*"`) and "Does ANY
OntologyClass name contain 'neoplasm'" (`pattern = "(?i).*neoplasm.*"`),
both zero rows graph-wide.

What a person using the product loses: any question that would benefit from
a MeSH heading, such as a literature search organized by MeSH term rather
than free text, gets no help from the graph's own vertex names, because the
stored name is the vocabulary's own identifier rather than the term. As with
item one, System 3 can and does answer these questions today from live NCBI
records and the literature; the loss is that the graph cannot contribute its
own citations to that answer.

## Four: the Gene vertex carries no facts

What was measured: the `Gene` vertex carries seven properties and none of
them states anything about the gene itself. Every sentence of content in a
System 3 answer about a gene comes from a live API call made at query time,
not from the graph. In the worst measured cold pass this spends 17 of a
20-call budget, and 2,957 of 4,748 citations in the sampled run came from a
layer that supplies no words of its own.

When: scoped on 2026-09-23.

By what query: this is a structural property of the `Gene` vertex schema
rather than a single Cypher probe; the count and the call-budget figures are
recorded in
`testing/Developer/reports/2026-09-23_overnight/soft_edges_scoping.md`
("count four: where answers actually fail today", the request list at the
end of that document).

What a person using the product loses: depth. A gene question can be
answered, correctly and with citations, but every fact in that answer costs
a live call, and the number of calls available per query is bounded. Adding
real content fields to the `Gene` vertex, such as a summary or a function
description, would let an answer say more without spending more of that
budget, and is the "graph plus values" model the scoping document argues
for over "graph plus vectors".

## What we are asking for

Item one is the cheapest fix and the largest single improvement measured
here: it corrects a value in a field that already exists, no schema or ETL
structural change needed. Items two and three are larger: item two needs
the `has_phenotype` edge either repointed to where the phenotype data
actually lives or populated on the `Disease` to `PhenotypicFeature` pair as
already declared in the schema, and item three needs term names loaded onto
`OntologyClass` vertices. Item four is the largest: it asks whether the
`Gene` vertex should carry real content fields at all, not only identifier
and link scaffolding. All three of items two, three and four are a genuine
question of what System 1 and 2 have the time and capacity to build, not a
correctness bug the way item one is.

System 3 will keep answering these question classes from Layer 2 and Layer 3
in the meantime: it degrades to a live API call rather than returning an
unsupported answer, per this repository's cite-or-refuse rule
(`.claude/rules/production-standards.md`). It will keep being unable to cite
the graph itself for them until this is fixed.
