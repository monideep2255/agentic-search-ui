SET search_path = ag_catalog, "$user", public;
LOAD 'age';
SET enable_seqscan = off;
SET max_parallel_workers_per_gather = 0;
SET work_mem = '32MB';
\echo === A: gene record ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'}) RETURN g $$) AS (result agtype) LIMIT 100;
\echo === B: orthologous_to hop ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:orthologous_to]->(o:Gene) RETURN o $$) AS (result agtype) LIMIT 100;
\echo === C: mentioned_in hop (Gene to Article) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:mentioned_in]->(a:Article) RETURN a $$) AS (result agtype) LIMIT 100;
\echo === D: gene_associated_with_condition hop ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:gene_associated_with_condition]->(d:Disease) RETURN d $$) AS (result agtype) LIMIT 100;
SET search_path = ag_catalog, "$user", public;
LOAD 'age';
SET enable_seqscan = off;
SET max_parallel_workers_per_gather = 0;
SET work_mem = '32MB';
\echo === D2: gene_associated_with_condition WITH ORDER BY (the template shape) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:gene_associated_with_condition]->(d:Disease) RETURN d ORDER BY d.id $$) AS (result agtype) LIMIT 100;
\echo === B2: orthologous_to WITH ORDER BY ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:orthologous_to]->(o:Gene) RETURN o ORDER BY o.id $$) AS (result agtype) LIMIT 100;
\echo === E: participates_in, no ORDER BY ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:participates_in]->(p:BiologicalProcess) RETURN p $$) AS (result agtype) LIMIT 100;
\echo === E2: participates_in WITH ORDER BY (the shipped GO template) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:participates_in]->(p:BiologicalProcess) RETURN p ORDER BY p.id $$) AS (result agtype) LIMIT 100;
SET search_path = ag_catalog, "$user", public;
LOAD 'age';
SET enable_seqscan = off;
SET max_parallel_workers_per_gather = 0;
SET work_mem = '32MB';
\echo === F: two hop gene -> article -> mesh ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:mentioned_in]->(a:Article)-[:has_mesh_annotation]->(m:OntologyClass) RETURN m $$) AS (result agtype) LIMIT 100;
\echo === G: label-less relationship ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[]->(n) RETURN n $$) AS (result agtype) LIMIT 100;
\echo === H: collect over articles ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:mentioned_in]->(a:Article) RETURN g, collect(a) $$) AS (result agtype) LIMIT 100;
SET search_path = ag_catalog, "$user", public;
LOAD 'age';
SET enable_seqscan = off;
SET max_parallel_workers_per_gather = 0;
SET work_mem = '32MB';
\echo ================ enable_memoize = off ================
SET enable_memoize = off;
\echo === F (two hop) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:mentioned_in]->(a:Article)-[:has_mesh_annotation]->(m:OntologyClass) RETURN m $$) AS (result agtype) LIMIT 100;
\echo === B (orthologs) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:orthologous_to]->(o:Gene) RETURN o $$) AS (result agtype) LIMIT 100;
\echo ================ memoize on, join_collapse_limit = 1 ================
SET enable_memoize = on;
SET join_collapse_limit = 1;
SET from_collapse_limit = 1;
\echo === F (two hop) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:mentioned_in]->(a:Article)-[:has_mesh_annotation]->(m:OntologyClass) RETURN m $$) AS (result agtype) LIMIT 100;
\echo === B (orthologs) ===
EXPLAIN SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene {id: 'NCBIGene:672'})-[:orthologous_to]->(o:Gene) RETURN o $$) AS (result agtype) LIMIT 100;
