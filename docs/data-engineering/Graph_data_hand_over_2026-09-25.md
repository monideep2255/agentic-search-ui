# Graph data hand over, 2026-09-25

A request from System 3 (this repository) to the data-engineering repository
(`reference/agentic-search-data-engineering`, System 1 and 2). System 3 reads
the graph read-only and never writes into it, per
`.claude/rules/file-protection.md`, so each item below is a request to fix at
the source rather than work this repository can do itself. Card 29,
product-owner decision of 2026-09-25 (`DECISIONS.md`, the row on card 12,
item 11.29, which hands these same gaps to the data repository).

## Table of contents

- [One: Disease vertices are named after their source vocabulary](#one-disease-vertices-are-named-after-their-source-vocabulary)
- [Two: no Disease vertex has an outgoing has_phenotype edge](#two-no-disease-vertex-has-an-outgoing-has_phenotype-edge)
- [Three: the graph holds no MeSH term names](#three-the-graph-holds-no-mesh-term-names)
- [What we are asking for](#what-we-are-asking-for)

## One: Disease vertices are named after their source vocabulary

What was measured: every `Disease` vertex's `name` property holds the name of
the vocabulary it came from, such as "MeSH", "MONDO", "MedGen" or
"SNOMEDCT_US", rather than the name of the disease. A graph-wide census found
zero vertices, out of 200,845 `Disease` rows, containing the word "syndrome".

When: censused on 2026-07-31, during build phase 2.1.

By what query: a graph-wide scan of every `Disease` vertex's `name` property,
counting vocabulary-artifact strings against the full 200,845-row population.
Filed as finding F-2.1-B07 in `tracker/phase_2.1.md`.

What a person using the product loses: a disease question, such as "what
conditions is BRCA1 associated with?", cannot be answered from the graph's own
disease names, because the graph does not hold disease names. The graph
already carries the correct CURIE for each disease and the edge to the gene
that causes it. Only the display name is wrong. This is the cheapest fix of
the three, because the field already exists and holds the wrong string; it
does not need a new column or a new ETL pass, only the correct value written
into the one that already exists.

## Two: no Disease vertex has an outgoing has_phenotype edge

What was measured: no `Disease` vertex in the graph has an outgoing
`has_phenotype` edge, graph-wide, with no filter applied. All 6,076,735
`has_phenotype` edges run from `SequenceVariant` to `Disease` instead. Every
`PhenotypicFeature` vertex sampled is an unpopulated stub of the shape
`[stub] HP:0000002`, with its `source` property reading `stub` and an empty
`source_url`.

When: measured live on 2026-09-23, using probes committed at
`testing/Developer/reports/2026-09-23_overnight/probe_disease_names.py` and
`probe_g022.py`. The underlying `has_phenotype` endpoint count (6,076,735 rows,
all `SequenceVariant` to `Disease`) was recorded earlier, on 2026-09-14, in
`docs/data-engineering/Knowledge_graph_on_server_reference.md` section D.

By what query: `MATCH (a)-[:has_phenotype]->(b) RETURN a AS result LIMIT 5`
and the matching query on the `b` side, plus a direct existence check for any
`Disease` vertex with an outgoing `has_phenotype` edge, and a sample of
`PhenotypicFeature` vertices to confirm they are unpopulated stubs.

What a person using the product loses: a question about what a condition
looks like clinically, for example "what phenotypic features are associated
with Marfan syndrome?", gets the answer "I could not find evidence" on every
attempt, because the code asks the graph a relationship it declared but never
populated. That refusal reads as "nothing is known about what this condition
looks like", when phenotype data for the condition exists in MedGen. This is
the worst of the three from the person's chair: it is a confident false
statement about the world, not a missing feature. The product's Disease to
PhenotypicFeature template was removed on 2026-09-23 rather than left dead
(recorded in `testing/UI_fixes_done.md`), so today the product falls back to
live sources for this class of question instead of returning the false
refusal; that fallback still cannot cite the graph's own phenotype data,
because the graph does not have any to cite.

## Three: the graph holds no MeSH term names

What was measured: the graph holds no disease names and no MeSH term names.
Every `Disease` vertex is named after its source vocabulary (see item one
above) and every `OntologyClass` vertex after its own identifier rather than
its term name, measured graph-wide.

When: known since build phase 2.1 as finding F-2.1-B07, and restated as an
open item during the phase 8 UI fix loop on 2026-09-24
(`testing/UI_fixes_done.md`).

By what query: the same graph-wide vocabulary-artifact census described in
item one, extended to the `OntologyClass` label.

What a person using the product loses: any question that would benefit from a
MeSH heading, such as a literature search organized by MeSH term rather than
free text, gets no help from the graph's own vertex names, because the stored
name is the vocabulary's own identifier rather than the term. As with item
one, System 3 can and does answer these questions today from live NCBI
records and the literature; the loss is that the graph cannot contribute its
own citations to that answer.

## What we are asking for

Item one is the cheapest fix and the largest single improvement: it corrects
a value in a field that already exists, no schema or ETL structural change
needed. Items two and three are larger: item two needs the `has_phenotype`
edge either repointed to where the data actually lives or populated on the
`Disease` to `PhenotypicFeature` pair as originally declared, and item three
needs term names loaded onto `OntologyClass` vertices. Both are a genuine
question of whether the graph should carry disease and phenotype content, not
only vocabulary and identifier scaffolding, which is an architectural choice
for System 1 and 2 to make with the time and capacity they have. System 3
will keep answering these question classes from Layer 2 and Layer 3 in the
meantime, since the citation rule in `CLAUDE.md` means an answer is never
withheld while the graph gap stands, but it will keep being unable to cite the
graph itself for them until this is fixed.
