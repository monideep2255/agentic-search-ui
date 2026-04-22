-- Gate 3 Cypher test suite for ncbi_kg AGE graph.
-- Run on VPS: sudo -u postgres psql -d ncbi_kg -f gate3_queries.sql
-- Every session needs the AGE prelude below.

LOAD 'age';
SET search_path = ag_catalog, "$user", public;
\timing on

\echo '=== Q1: BRCA1 gene to variants (typed edge, GIN on Gene) ==='
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene {id: 'NCBIGene:672'})-[r:is_sequence_variant_of]-(v:SequenceVariant)
    RETURN g.name, v.id LIMIT 10
$$) as (gene agtype, variant_id agtype);

\echo '=== Q2: Phenylketonuria (MedGen CURIE) to associated gene (directed: Gene -> Disease) ==='
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease {id: 'MedGen:C0031485'})
    RETURN d.id, d.name, g.id, g.name LIMIT 10
$$) as (did agtype, dname agtype, gid agtype, gname agtype);

\echo '=== Q3: Genes participating in glucose metabolism (regex on BioProcess name) ==='
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene)-[:participates_in]->(p:BiologicalProcess)
    WHERE p.name =~ '(?i).*glucose metabol.*'
    RETURN g.name, p.name LIMIT 10
$$) as (gene agtype, process agtype);

\echo '=== Q4: TP53 mentioned in articles (directed: Gene -> Article) ==='
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene {id: 'NCBIGene:7157'})-[:mentioned_in]->(a:Article)
    RETURN g.name, a.id LIMIT 10
$$) as (gene agtype, article agtype);

\echo '=== Q5: Human taxon -> genes located in humans (directed: Gene -> Taxon) ==='
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene)-[:in_taxon]->(t:OrganismTaxon {id: 'NCBITaxon:9606'})
    RETURN t.id, g.id, g.name LIMIT 10
$$) as (tid agtype, gid agtype, gname agtype);

\echo '=== Q6: Node count per vertex label (sanity) ==='
SELECT label, count(*)
FROM (
    SELECT 'Gene' as label, id FROM ncbi_kg."Gene"
    UNION ALL SELECT 'SequenceVariant', id FROM ncbi_kg."SequenceVariant"
    UNION ALL SELECT 'Article', id FROM ncbi_kg."Article"
    UNION ALL SELECT 'Disease', id FROM ncbi_kg."Disease"
    UNION ALL SELECT 'OrganismTaxon', id FROM ncbi_kg."OrganismTaxon"
    UNION ALL SELECT 'BiologicalProcess', id FROM ncbi_kg."BiologicalProcess"
    UNION ALL SELECT 'PhenotypicFeature', id FROM ncbi_kg."PhenotypicFeature"
    UNION ALL SELECT 'MolecularActivity', id FROM ncbi_kg."MolecularActivity"
    UNION ALL SELECT 'CellularComponent', id FROM ncbi_kg."CellularComponent"
    UNION ALL SELECT 'OntologyClass', id FROM ncbi_kg."OntologyClass"
    UNION ALL SELECT 'NamedThing', id FROM ncbi_kg."NamedThing"
) x GROUP BY label ORDER BY count DESC;

\echo '=== Q7: Edge count per edge label (sanity) ==='
SELECT relname AS edge_label, n_live_tup AS rows
FROM pg_stat_user_tables
WHERE schemaname = 'ncbi_kg' AND relname NOT IN (
    'Gene','SequenceVariant','Article','Disease','OrganismTaxon',
    'BiologicalProcess','PhenotypicFeature','MolecularActivity',
    'CellularComponent','OntologyClass','NamedThing',
    '_ag_label_vertex','_ag_label_edge'
)
ORDER BY n_live_tup DESC;
