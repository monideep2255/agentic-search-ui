/**
 * Every figure, database name, host and budget the Architecture page states,
 * and the four lines the About page's "Where the data comes from" strip
 * states, in ONE module.
 *
 * WHY A MODULE RATHER THAN TWO COPIES. Both pages quote the same snapshot.
 * Writing `115,406,761` twice is one typo away from two pages disagreeing
 * about the size of the graph, and a reader has no way to tell which one is
 * wrong. The cheapest fix is for there to be only one of it.
 *
 * WHY IT IS NOT IN EITHER SCREEN FILE. `ArchitectureScreen.tsx` already
 * imports `Page`, `JourneyStop`, `StopText` and `StopLabel` from
 * `InfoScreens.tsx`, which is where the About page lives. Putting the shared
 * data in either of those two would make the pair import each other. A third
 * module that neither imports back cannot form that cycle.
 *
 * EVERY VALUE BELOW WAS READ OUT OF A DOCUMENT OR A CONSTANT IN CODE, and
 * each carries the file it came from. Nothing here is recalled.
 */

/**
 * The date the loaded snapshot finished, as a person reads it.
 *
 * Source: `reference/agentic-search-data-engineering/CLAUDE.md`, Current
 * focus, "V1 COMPLETE (2026-04-22) ... loaded 2026-04-22".
 */
export const SNAPSHOT_DATE = "22 April 2026";

/**
 * The snapshot's headline figures, written in full rather than rounded. A
 * rounded count cannot be checked against the source table; an exact one can.
 *
 * Source: `reference/agentic-search-data-engineering/docs/
 * Knowledge_graph_on_server_reference.md` Section A, "It contains
 * 115,406,761 nodes and 693,295,991 edges across 11 vertex labels and 14 edge
 * labels", and the same repository's `CLAUDE.md`.
 */
export const NODE_COUNT = "115,406,761";
export const EDGE_COUNT = "693,295,991";
export const VERTEX_LABEL_COUNT = "11";
export const EDGE_LABEL_COUNT = "14";

export const SNAPSHOT_FIGURES: { value: string; label: string }[] = [
  { value: NODE_COUNT, label: "nodes" },
  { value: EDGE_COUNT, label: "edges" },
  { value: VERTEX_LABEL_COUNT, label: "vertex labels" },
  { value: EDGE_LABEL_COUNT, label: "edge labels" },
];

/**
 * The five NCBI databases the graph is built from, with the graph label each
 * becomes, the number of nodes it contributes, and a sample identifier.
 *
 * Source: `Knowledge_graph_on_server_reference.md` Section D, "Vertex labels
 * and counts", and Section F for the sample CURIEs. These are the LOADED
 * counts, which is why Disease reads 200,845 rather than MedGen's roughly
 * 233K source concepts: one table, stating what is in the graph, rather than
 * source-record counts mixed with graph counts.
 */
export const SOURCE_DATABASES: {
  source: string;
  label: string;
  nodes: string;
  curie: string;
}[] = [
  { source: "NCBI Gene", label: "Gene", nodes: "67,536,325", curie: "NCBIGene:672" },
  { source: "PubMed", label: "Article", nodes: "40,387,670", curie: "PMID:1088347" },
  { source: "ClinVar", label: "SequenceVariant", nodes: "4,467,468", curie: "ClinVar:17660" },
  { source: "NCBI Taxonomy", label: "OrganismTaxon", nodes: "2,736,611", curie: "NCBITaxon:9606" },
  { source: "MedGen", label: "Disease", nodes: "200,845", curie: "MedGen:C0031485" },
];

/**
 * The same five databases as one readable sentence fragment, for the About
 * page's strip, derived rather than retyped so the two lists cannot diverge.
 *
 * The short names are the ones a reader recognises: the graph reference calls
 * the sources "Gene, ClinVar, MedGen, PubMed, and Taxonomy" (Section A), so
 * the "NCBI " qualifier that `SOURCE_DATABASES` carries for precision is
 * dropped here for the running sentence.
 */
export const SOURCE_DATABASE_NAMES: string[] = SOURCE_DATABASES.map((db) =>
  db.source.replace(/^NCBI /, ""),
);

/**
 * The five steps every one of those pipelines runs, in order.
 *
 * Source: `reference/agentic-search-data-engineering/CLAUDE.md`, "Pipeline
 * pattern (every ETL follows this)": Download, Parse, Map, Validate, Export.
 */
export const PIPELINE_STEPS = [
  "Download",
  "Parse",
  "Map to BioLink",
  "Validate",
  "Export KGX",
] as const;

/**
 * The three layers the search agent reads, each with the tools that reach it.
 * `calls` names the host or service, `budget` the per-call limit the code
 * enforces.
 *
 * Sources: `visualizations/Architecture_diagram.md`'s tool table for the
 * layer split and the budgets, each of which is a constant in code
 * (`CYPHER_QUERY_TIMEOUT_SECONDS = 90.0` and `MAX_ROW_LIMIT = 500` in
 * `tools/graph_schema_constants.py`, `DEFAULT_TIMEOUT_S = 15.0` in
 * `tools/ncbi_transport.py`, `_TOTAL_BUDGET_S = 120.0` in
 * `tools/pathogen_detection.py`). The hosts come from the tool modules
 * themselves: `_EUTILS_BASE` in `tools/ncbi_eutils_actions.py`,
 * `_DATASETS_BASE` in `tools/ncbi_datasets_actions.py`, `_VARIATION_BASE` in
 * `tools/ncbi_dbsnp.py`, and the PubTator3, LitVar2 and ClinicalTrials.gov
 * constants in their own modules.
 *
 * ONE DIVERGENCE IS DELIBERATE. The About page's walk lists
 * `pathogen_detection` under layer 3. This list puts it under layer 2,
 * following `Architecture_diagram.md`, which classifies it there "because it
 * is an NCBI-native bulk source, not one of the four enrichment APIs" and is
 * this repository's source of truth for the tool-to-layer mapping. About's
 * own list is left as it stands, since that page was out of scope to
 * restructure; the disagreement is stated rather than papered over.
 */
export const LAYERS: {
  n: 1 | 2 | 3;
  name: string;
  summary: string;
  tools: { name: string; calls: string; budget: string }[];
}[] = [
  {
    n: 1,
    name: "Knowledge graph",
    summary:
      "The snapshot above, read over an authenticated HTTPS query service on a read-only credential. Broad and fast, and as current as the snapshot date.",
    tools: [
      {
        name: "cypher_query",
        calls: "the ncbi_kg graph, PostgreSQL with Apache AGE",
        budget: "90 seconds, at most 500 rows",
      },
    ],
  },
  {
    n: 2,
    name: "Live NCBI APIs",
    summary:
      "Called at the moment you ask, so the answer carries today's record rather than the snapshot's. Narrower than the graph, and always current.",
    tools: [
      {
        name: "ncbi_efetch",
        calls: "E-utilities ESearch, ESummary, EFetch and ELink, plus NCBI Datasets v2",
        budget: "15 seconds, one retry",
      },
      {
        name: "ncbi_dbsnp",
        calls: "NCBI Variation Services, then the dbSNP record",
        budget: "15 seconds per call, two calls in sequence",
      },
      {
        name: "pathogen_detection",
        calls: "the NCBI Pathogen Detection bulk snapshot over FTP",
        budget: "120 seconds",
      },
    ],
  },
  {
    n: 3,
    name: "Enrichment",
    summary:
      "Literature and trial evidence, layered on a fact the first two layers already established. Called when the question asks for it, never by default.",
    tools: [
      { name: "pubtator_annotate", calls: "PubTator3", budget: "15 seconds" },
      { name: "litvar2_lookup", calls: "LitVar2", budget: "15 seconds" },
      { name: "clinicaltrials_search", calls: "ClinicalTrials.gov API v2", budget: "15 seconds" },
    ],
  },
];

/**
 * The one Cypher query the Architecture page shows, so "what a query looks
 * like" is something a reader can see rather than a sentence they take on
 * trust.
 *
 * It is the shape Section H of `Knowledge_graph_on_server_reference.md` calls
 * rule 1 and rule 2: name the node by its CURIE, and always name the edge
 * label. `gene_associated_with_condition` and its direction come from
 * `docs/visualizations/Schema_visualization.md` section 3.
 */
export const EXAMPLE_CYPHER =
  "MATCH (g:Gene {id: 'NCBIGene:672'})-[:gene_associated_with_condition]->(d:Disease)\nRETURN d.id, d.name";
