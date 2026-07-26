# NCBI and enrichment API capability sheet

Phase 4, Step 4.0 deliverable. The verified current-state capability surface of every Layer 2 (NCBI) and Layer 3 (enrichment) API the System 3 tools reach. The Step 4.1 tool specifications are written against this sheet.

Verified live 2026-07-25 against the production endpoints. Scope: the databases and APIs the five roadmap tools touch (cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup), documented at their general capability surface, with the moat-seven competency questions as verification anchors, not as the scope ceiling. Layer 1 (the knowledge graph) is covered by the data-engineering server reference and re-verified live in Phase 6 (see the Layer 1 note).

## Table of contents

- [Feasibility flags resolved](#feasibility-flags-resolved-the-step-40-constraint)
- [How this was verified](#how-this-was-verified)
- [Layer 1: the knowledge graph (cross-reference)](#layer-1-the-knowledge-graph-cross-reference)
- [Layer 2: E-utilities core, PubMed, Gene](#layer-2-e-utilities-core-pubmed-gene)
- [Layer 2: variant and coordinate layer](#layer-2-variant-and-coordinate-layer-dbsnp-variation-services-clinvar-dbvar-omim-medgen-gtr)
- [Layer 2: sequence-data and cross-database traversal](#layer-2-sequence-data-and-cross-database-traversal-elink-sra-bioproject-biosample-assembly-geo-pathogen-detection)
- [Layer 2: NCBI Datasets API v2 and PubChem PUG REST](#layer-2-ncbi-datasets-api-v2-and-pubchem-pug-rest)
- [Layer 3: enrichment APIs](#layer-3-enrichment-apis-pubtator3-litvar2-litsense-clinicaltrialsgov-v2)
- [Tool-layer design implications](#tool-layer-design-implications-from-the-reference-mining)
- [Moat-seven competency question to API anchor map](#moat-seven-competency-question-to-api-anchor-map)
- [Open items and drift flags](#open-items-and-drift-flags)

## Feasibility flags resolved (the Step 4.0 constraint)

The three Phase 2 feasibility flags are the reason Step 4.0 verifies live. All three resolve, and the moat-seven all hold: the cap stays seven, no demotions.

| Flag | Question | Verdict | Consequence for the build |
|------|----------|---------|---------------------------|
| Q1 | dbVar interval-overlap for large SVs | Resolved, conditional | ESearch coordinate-range is a coarse multi-valued prefilter, not true interval overlap. Cross-placement false positives are proven (point insertions matched a 2.5Mb span query because a GRCh37-scaffold start paired with a GRCh38 end). True overlap is reachable via ESearch prefilter plus a placement-level post-filter in tool code. Q1 stays tier-1, cap stays seven, the two-step filter is a documented ncbi_efetch requirement. |
| Q5 | Pathogen Detection access | Resolved, feasible | No clean public JSON API (the isolates browser path serves HTML). The FTP results tree (versioned PDG snapshots) gives isolate to SNP cluster to AMR to BioSample to SNP-distance neighbors. Bulk-file access with snapshot pinning. Q5 holds. |
| Q6 | SRA metadata field availability | Resolved, feasible | Two-tier: 22 ESearch-indexed fields for filtering, plus rich EFetch sample attributes (serovar, isolation_source, geo_loc_name, collection_date) for the match rationale. Attribute tag names vary by submitter, so the tool must normalize them. Q6 holds. |

## How this was verified

- Live probes against production endpoints on 2026-07-25: eutils.ncbi.nlm.nih.gov, api.ncbi.nlm.nih.gov (Datasets and Variation Services), ftp.ncbi.nlm.nih.gov (Pathogen Detection), pubchem.ncbi.nlm.nih.gov, the research enrichment APIs, and clinicaltrials.gov. Every non-trivial claim in the sections below is backed by a live call made this session.
- Constraint-focused depth (2026-07-25 scope decision): the three feasibility flags plus the exact endpoints and fields the five tools use were verified live; the 2026-04-20 reference re-verification is trusted for stable behavior.
- Cross-checked against a four-agent mining of the Agentic-Search reference repository for design intent, prior-art tool decomposition, caching, and security (folded into the tool-layer implications section).

## Layer 1: the knowledge graph (cross-reference)

Layer 1 is the AGE graph on the Hetzner box, read-only via psycopg2, SSH-only and firewalled, so it is not reachable from the planning sandbox. Its schema (10 concept labels, which is the 11 vertex labels in the server doc minus the NamedThing merger stub, and 14 edge predicates), indexes, connection prelude, and the canonical smoke-test suite are documented and gate-verified (2026-04-22) in docs/data-engineering/Knowledge_graph_on_server_reference.md. Per the 2026-07-25 scope decision, the cypher_query section of the tech spec is written against that doc, and Layer 1 is re-verified live in Phase 6 when the tool connects over the real DSN. This sheet covers Layers 2 and 3.

## Layer 2: E-utilities core, PubMed, Gene

Verified live 2026-07-25 against https://eutils.ncbi.nlm.nih.gov/entrez/eutils/. Every claim below is backed by a live call made this session.

### E-utilities mechanics

Base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`. Nine endpoints: EInfo (db metadata and field lists), ESearch (text query to UID list), EFetch (UID to full record), ESummary (UID to document summary), ELink (cross-database links), EPost (upload UIDs to the history server), EGQuery (global count across all dbs), ESpell (spelling suggestions), ECitMatch (citation string to PMID).

Standard workflows:

- Search then fetch: ESearch returns a UID list, EFetch or ESummary retrieves records for those UIDs.
- Search then link: ESearch returns UIDs in db A, ELink maps them to related UIDs in db B.
- Large result sets: ESearch with `usehistory=y` returns `WebEnv` + `query_key` instead of inlining thousands of UIDs; EFetch or ESummary then pages over the history set with `retstart`/`retmax`. This is the mechanism the tools use to avoid inlining large ID lists into agent context (system-design-patterns rule 7, output truncation).

Rate limits: 3 requests/second without an API key, 10 requests/second with a key passed as `&api_key=`. The key belongs in an env var, never in code or logs (production-standards secrets gate). All tool calls must serialize or throttle to stay under the shared cap across concurrent users (rate-limiting-and-concurrency section of the tech spec).

### Error and empty behavior (verified, load-bearing for cite-or-refuse)

The single most important finding for tool and guardrail design: HTTP status is not a reliable success signal. E-utilities returns HTTP 200 for empty results AND for several error classes. The tool must inspect the response body.

| Condition | HTTP | Body signal (verified) |
|-----------|------|------------------------|
| Zero hits | 200 | `esearchresult.count = "0"`, `idlist = []`, `warninglist.outputmessages = ["No items found."]`, unmatched phrases in `errorlist.phrasesnotfound` |
| EFetch on a nonexistent id | 200 | empty record set, e.g. `<PubmedArticleSet></PubmedArticleSet>` (no error node) |
| Invalid db name | 200 | `esearchresult.ERROR = "Invalid db name specified: <db>"` |
| Unknown field tag, e.g. `cancer[badfield]` | 200 | no error; silently falls back to a broad search (returned 5,666,701 hits), `errorlist.fieldsnotfound = []` |

Tool-design consequences:
- The cite-or-refuse path keys on `count = 0` (a clean, structured empty), not on HTTP status. Zero hits is the tested refusal trigger.
- The ncbi_efetch tool must treat an empty record set as no-data, not success-with-content.
- The tool must parse for `ERROR` in the JSON body and surface it as an actionable error to the agent loop (production-standards retry-safety: errors say what to do next).
- The silent unknown-field-tag fallback is a correctness trap: a malformed field tag returns plausible but wrong results with no error. The query builder must validate field tags against the EInfo field list before issuing a search, never construct a tag from free text.

### PubMed (db=pubmed, 40.3M records)

ESummary (retmode=json) returns full citation metadata, verified field set: `uid`, `authors` (array with name and authtype), `source` (journal abbrev), `fulljournalname`, `pubdate`, `epubdate`, `volume`, `issue`, `pages`, `elocationid` (carries the DOI, e.g. `doi: 10.32604/or.2026.078924`), `articleids` (all external ids including doi, pmc), `issn`/`essn`, `lastauthor`, `sortfirstauthor`, `pubtype`, `history`, `references`, `pmcrefcount`, `nlmuniqueid`.

EFetch retrieves the abstract and MeSH terms: `rettype=abstract&retmode=text` for plain text, `retmode=xml` for the structured PubmedArticle (AbstractText, MeshHeadingList, AuthorList, GrantList). The XML parser must disable external entities (`resolve_entities=False`, production-standards).

CitationAdapter: PubMed satisfies it fully. `source_url` per record is `https://pubmed.ncbi.nlm.nih.gov/<pmid>/`, host-pinned to `pubmed.ncbi.nlm.nih.gov`.

Anchors Q3 (BRCA1 literature) and Q4 (disease phrase to PubMed).

### Gene (db=gene, 95.0M records)

ESummary (json) verified fields for BRCA1 (uid 672): `name` (symbol), `description`, `nomenclaturesymbol`, `nomenclaturename`, `otheraliases`, `otherdesignations`, `chromosome`, `maplocation`, `genomicinfo` (array with chrloc, chrstart, chrstop, exoncount: the current-assembly coordinates), `mim` (OMIM number for the gene->OMIM bridge), `organism` (with taxid), `summary`, `geneweight`.

Cross-links via ELink (dbfrom=gene): verified linknames include `gene_pubmed` (7219 links for 672), `gene_pubmed_rif` (Gene References into Function), `gene_pubmed_citedinomim`. The clinvar, snp, protein, nuccore, and omim link targets are reached the same way (full linkname enumeration is in the sequence-data traversal section). ELink structure: `linksets[0].linksetdbs[]`, each with `linkname` and a `links[]` UID array.

Gene is the flagship traversal hub for Q3 (BRCA1 to Gene, PubMed, ClinVar, GTR, MedGen). `source_url`: `https://www.ncbi.nlm.nih.gov/gene/672`.

### Taxonomy and MeSH (connectors)

Taxonomy (db=taxonomy, 2.9M records): organism-name normalization and taxid resolution, used to constrain organism-scoped searches (for example pinning `Salmonella enterica` to taxid 28901 for SRA and Pathogen Detection queries). ESummary returns scientific name, rank, lineage, division.

MeSH (db=mesh, 355.7K records): the controlled-vocabulary layer behind PubMed subject search. Used to expand a disease phrase into MeSH terms for precise PubMed routing (Q4). ESummary returns the MeSH heading, tree numbers, scope note, and unique id.

## Layer 2: variant and coordinate layer (dbSNP, Variation Services, ClinVar, dbVar, OMIM, MedGen, GTR)

Verified live 2026-07-25. This cluster feeds the ncbi_dbsnp tool and the coordinate-overlap path of the ncbi_efetch tool.

### dbSNP (db=snp) via E-utilities

ESummary (json) for rs334 (uid 334) verified fields: `snp_id`, `acc`, `allele`, `allele_origin`, `chr`, `chrpos` (e.g. `11:5227002`), `chrpos_prev_assm` (prior assembly position), `spdi` (comma-joined SPDI list, e.g. `NC_000011.10:5227001:T:A,...:T:C,...:T:G`), `clinical_significance` (comma-joined, e.g. `pathogenic,protective,likely-benign`), `fxn_class` (e.g. `missense_variant,coding_sequence_variant`), `genes` (array of `{name, gene_id}`, e.g. `HBB`/3043), `global_mafs` (population MAF array), `snp_class`, `validated`, `tax_id`, `createdate`/`updatedate`.

Note: the flat `global_maf` scalar is null; frequencies live in the `global_mafs` array. The tool must read the array, not the scalar.

`source_url`: `https://www.ncbi.nlm.nih.gov/snp/rs334`.

### NCBI Variation Services (base https://api.ncbi.nlm.nih.gov/variation/v0)

This is a separate host from eutils, with its own rate budget (historically ~1 req/second, treat as low). No API key is required (all calls below returned HTTP 200 with no key). It is the precise variant-normalization path for the ncbi_dbsnp tool. Verified endpoints (all HTTP 200):

| Endpoint | Returns |
|----------|---------|
| `refsnp/{rsid}` (e.g. refsnp/334) | full RefSNP record: `refsnp_id`, `primary_snapshot_data`, `mane_select_ids`, `citations`, `dbsnp1_merges`, `present_obs_movements`, `create_date`, `last_update_date` |
| `spdi/{spdi}/canonical_representative` | canonical SPDI: `{seq_id, position, deleted_sequence, inserted_sequence}` |
| `spdi/{spdi}/all_equivalent_contextual` | all equivalent contextual alleles for the SPDI |
| `hgvs/{hgvs}/contextuals` | SPDI contextual alleles for an HGVS expression (encode `>` as `%3E`) |

Use it to normalize a user-supplied HGVS or coordinate to a canonical SPDI and rsid before graph or Layer 2 lookup, so entity normalization scores 2 on the eval rubric.

### ClinVar (db=clinvar) coordinate path (cleaner than dbVar)

Coordinate ESearch verified clean and single-assembly. `17[CHR] AND 43044295:43125483[C37]` translated to `CHRPOS37` range and returned 99 variants. Fields: `CHR`, `CPOS` (GRCh38, tag CHRPOS), `C37` (GRCh37, tag CHRPOS37), `VLEN` (variant length). Because `C37` and `CPOS` are assembly-specific position tags, pinning the query to one of them gives clean single-assembly coordinates. This does not have dbVar's cross-placement false-positive problem for point and short variants; for larger ClinVar CNVs, apply the same placement-level post-filter using `VLEN`.

ESummary schema (verified current, drifted to the ACMG-aligned shape): `accession` (VCV...), `title` (HGVS c. and p.), `germline_classification` (object: `description` e.g. "Pathogenic", `review_status`, `last_evaluated`, `trait_set` with `trait_xrefs` to MedGen, MeSH, MONDO, Orphanet), `oncogenicity_classification`, `clinical_impact_classification`, `molecular_consequence_list`, `protein_change`, `genes`, `variation_set` (with `canonical_spdi`, `cdna_change`, `variant_type`, `variation_loc`), `supporting_submissions`.

Drift flag: the summary now uses `germline_classification` rather than a flat `clinical_significance` scalar. Any tool or fixture written against the old field name must update. The `trait_set.trait_xrefs` is the ClinVar to disease-concept bridge (MedGen CUI, MONDO, Orphanet), which routes Q4.

`source_url`: `https://www.ncbi.nlm.nih.gov/clinvar/variation/<VariationID>/`.

Anchors Q1 (ClinVar coordinate evidence, GRCh37 explicit so no liftover), Q3, Q4.

### dbVar (db=dbvar): coordinate overlap requires a two-step design (verified)

Fields (EInfo, verified): `CH` (Chr), `BASE` (ChrPos, start of placement), `CHR_END` (ChrEnd, end of placement), `VT` (Variant Type), `VLEN` (Variant Size), `CLIN` (Clinical Interpretation), `PATHO_RNG` (Pathogenic Overlap Range, precomputed reciprocal overlap with a pathogenic variant), plus per-population allele frequencies (AFR, AMR, EAS, EUR, SAS, OTH, FREQ), `OMIM` (MIM), `PUBMED_ID`, `GENE_NAME`, `ASSM`.

Verified finding (the Q1 resolution): ESearch coordinate-range on dbVar is NOT true interval overlap by itself. `ChrPos` and `ChrEnd` are multi-valued per record (across GRCh37, GRCh38, and remapped placements), and Entrez matches the two range constraints independently, so `BASE <= We AND CHR_END >= Ws` over-returns false positives.

Evidence (chr1 GRCh38, window 1,000,000 to 1,100,000):
- Naive start-in-window (`1000000:1100000[BASE]`): 1,892 records.
- Two-field "overlap" (`1:1100000[BASE] AND 1000000:250000000[CHR_END]`): 26,696 records.
- Three sampled "spanning" hits (start < 500k AND end > 2M) were all point insertions with a 0bp GRCh38 span (nsv7894147 at 248,800,147; nsv7892017 at 125,151,644; nsv7882294 at 248,775,703). Each matched only because a GRCh37 unplaced-scaffold start (e.g. 44,815) paired with a GRCh38 end. The `GRCh38[ASSM]` filter selects records that have a GRCh38 placement, but does not pin the coordinate pair to that placement.

Required tool design for true overlap:
1. ESearch coordinate range as a coarse candidate prefilter (pinned to the assembly via `ASSM` to reduce noise).
2. ESummary each candidate, read `dbvarplacementlist` (each entry: `chr`, `chr_start`, `chr_end`, `assembly`), select the target-assembly placement.
3. Apply the exact predicate in tool code: `placement.chr_start <= We AND placement.chr_end >= Ws`.

Consequence for the moat set: Q1 stays tier-1 (overlap is reachable), the cap stays seven, and the two-step filter is a documented requirement of the ncbi_efetch coordinate-overlap path. Do not rely on raw ESearch range semantics for any coordinate-overlap query.

`source_url`: `https://www.ncbi.nlm.nih.gov/dbvar/variants/<nsv>/`.

### OMIM, MedGen, GTR

OMIM (db=omim): ESummary is thin (`oid` = MIM number, `title`, `alttitles`, `locus`, `uid`). Enough for the gene to MIM disorder citation bridge (Gene ESummary carries `mim`, and dbVar/ClinVar carry OMIM xrefs). Full OMIM narrative content needs the separate api.omim.org (key-gated); for System 3 the Entrez MIM number plus title suffices for a cited link. `source_url`: `https://www.omim.org/entry/<mim>`. Anchors Q1, Q3.

MedGen (db=medgen): the disease-concept hub. ESummary fields: `conceptid` (the UMLS CUI, e.g. `C1332443`), `title`, `definition`, `semantictype`, `conceptmeta`, `modificationdate`. The CUI is the normalization key that ClinVar `trait_xrefs` point to, so MedGen anchors disease-phrase routing. Anchors Q4 (disease phrase to MedGen), Q3. `source_url`: `https://www.ncbi.nlm.nih.gov/medgen/<uid>`.

GTR (db=gtr): registered genetic tests. Rich ESummary: `accession`, `testname`, `genelist`, `conditionlist`, `method`, `analyticalvalidity`, `clinicalvalidity`, `clinicalutility`, `offerer` (the lab), `offererlocation`, `orderurl`, `certifications`, `specimens`, `testtargetlist`, `testpurpose`. Anchors Q3 (GTR tests for BRCA1), Q4 (tests for a disease). `source_url`: `https://www.ncbi.nlm.nih.gov/gtr/tests/<id>/`.

## Layer 2: sequence-data and cross-database traversal (ELink, SRA, BioProject, BioSample, Assembly, GEO, Pathogen Detection)

Verified live 2026-07-25. This cluster feeds the ncbi_efetch tool's traversal path and the pathogen tool.

### ELink cross-database traversal (anchors Q8, Q10)

Structure (json): `linksets[0].linksetdbs[]`, each entry has `dbto`, `linkname`, and a `links[]` UID array. The `linkname` encodes the link semantics and is how the tool distinguishes direct from inferred:

- Direct curated links: named `<dbfrom>_<dbto>`, for example `gds_pubmed` (a GEO DataSet to its publication), `bioproject_sra`, `bioproject_biosample`. Verified: BioProject uid 1498027 returned `bioproject_sra` = 12 links and `bioproject_biosample` = 12 links.
- Computed or inferred neighbors: named with a doubled db and a qualifier, for example `pubmed_pubmed_citedin`, `pubmed_pubmed_alsoviewed`, `pubmed_pubmed_refs`, `pubmed_pubmed_reviews`. These are algorithmic neighbors, not asserted data links.

Verified finding (load-bearing for Q8): direct PubMed to data links are sparse. Three major genomics papers (1000 Genomes 2015, PMID 26432245; 1000 Genomes pilot 2010, PMID 20981092) returned only `pubmed_pubmed*` computed neighbors, no `pubmed_sra`, `pubmed_gds`, `pubmed_nuccore`, or `pubmed_assembly`. Consequence: the Q8 answer must treat "absent" as the common case (the eval rubric already allows this), and the reliable signal is the reverse direction (data record to PubMed, for example `gds_pubmed`) or parsing the PMC full-text data-availability section. Do not assume a PMID carries forward data links.

Tool-design rule: pass an explicit `db=<dbto>` to ELink to force and isolate a single target link set. Without it, the default neighbor response can be dominated by computed `pubmed_pubmed*` links and hide or omit the data links you want.

### SRA (db=sra, 43.6M records) (anchors Q6)

Two-tier metadata (verified):
- ESearch-indexed structured fields (22, for filtering): `ORGN`, `PLAT` (Platform), `STRA` (Strategy), `SRC` (Source), `SEL` (Selection), `LAY` (Layout), `ACS` (Access, public or controlled), `GPRJ` (BioProject), `BSPL` (BioSample), `MBS` (Mbases), `RLEN`, `ALN`, `ACCN`, `TITL`, `WORD`.
- Rich sample attributes (not indexed as structured fields, retrieved via EFetch db=sra full XML, SAMPLE_ATTRIBUTE TAG/VALUE pairs): verified tags on live Salmonella records include `serovar`, `strain`, `isolation source`, `collection date`, `geographic location (country and/or sea)`, `geographic location (region and locality)`, `collected by`, plus ENA-brokered records add `INSDC center name`, `ENA-FIRST-PUBLIC`, `ENA-STATUS`.

Verified heterogeneity caveat: attribute tag names vary by submitter and broker (for example `collection_date` versus `collection date`, and ENA-brokered records use ENA-specific tags). A tool matching on sample attributes must normalize tag names, not assume a fixed key set. This is a concrete tool-design requirement for Q6's natural-language metadata match.

Match rationale for Q6: search maps the natural-language query to indexed fields where possible (organism, platform, strategy) plus free-text `ALL`/`WORD` for the rest, then EFetch supplies the exact attribute values that matched, which is the citable rationale. The BigQuery `nih-sra-datastore` public dataset holds normalized attributes and is an out-of-Entrez option for structured attribute search (mentioned, not verified here).

`source_url`: `https://www.ncbi.nlm.nih.gov/sra/<accession>`.

### BioProject, BioSample, Assembly, GEO

All four are Entrez databases reached through E-utilities, so they inherit the E-utilities mechanics documented in the E-utilities section: the 3 and 10 per second rate limits, the history server for large sets, and the error and empty behavior (HTTP 200 with count 0 on no hits, HTTP 200 with an ERROR body on a bad db or field). ESearch and ESummary take the same shape as the other Entrez databases; the notes below cover only what is specific to each.

BioProject (db=bioproject, 1.0M records): the umbrella record. Verified traversal to SRA and BioSample via ELink (above). Feeds Q10's bundle root.

BioSample (db=biosample, 53.5M records): the physical-sample record with structured attribute packages (host, isolation source, collection date, geographic location). Links to SRA and, for pathogens, is the join key in the Pathogen Detection metadata (`biosample_acc`).

Assembly (db=assembly, 3.5M records): genome-assembly metadata (accession GCA/GCF, level, coverage, contig N50, submitter). Note: the NCBI Datasets API v2 is the preferred path for assembly reports and data packages (see the Datasets section), Entrez Assembly is the ELink-traversal path.

GEO DataSets (db=gds, 8.7M records): expression and other functional-genomics series. `gds_pubmed` is a reliable curated link to the source publication (verified n=1 for a real series). Feeds Q8 (paper to GEO) via the reverse direction.

### NCBI Pathogen Detection (anchors Q5)

No clean public JSON API: the Isolates Browser path `/pathogens/isolates/api/` returns the Django HTML web app (verified). The verified programmatic path is the FTP results tree.

Base: `https://ftp.ncbi.nlm.nih.gov/pathogen/Results/<Taxon>/` (for example `Salmonella/`), holding versioned PDG snapshots `PDG000000002.NNNN`. Snapshots are incremental: the newest may be mid-build (`.4158` had only `Metadata/`), so pin to the latest complete snapshot (`.4157` had the full set). Verified file map of a complete snapshot:

| Path | Contents | Q5 role |
|------|----------|---------|
| `Metadata/PDG*.metadata.tsv` | per-isolate row: `biosample_acc`, `Run` (SRA), `asm_acc`, `strain`, `serovar`, `geo_loc_name`, `collection_date`, `host`, `isolation_source`, `AMR_genotypes`, `AMR_genotypes_core`, `AST_phenotypes`, `number_amr_genes`, `minsame`, `mindiff`, `target_acc` | isolate to BioSample, SRA, AMR, SNP-distance summary |
| `Clusters/PDG*.reference_target.cluster_list.tsv` | isolate to PDS SNP-cluster membership | which cluster an isolate belongs to |
| `Clusters/PDG*.reference_target.SNP_distances.tsv` | pairwise SNP distances | the neighbors-within-5-SNPs set |
| `Clusters/PDG*.reference_target.all_isolates.tsv` and `new_isolates.tsv` | isolate rosters | cluster context |
| `AMR/PDG*.amr.metadata.tsv` (+ .xml) | AMRFinderPlus gene and phenotype detail | AMR gene names and resistance |
| `SNP_trees/PDS<id>.<ver>.tar.gz` | per-cluster newick tree + SNP matrix, versioned | cluster tree and distances for one PDS |

Verified full Q5 chain: isolate to SNP cluster (cluster_list.tsv), to AMR genes (amr.metadata.tsv or the AMR_genotypes column), to BioSample (biosample_acc), to neighbors within 5 SNPs (SNP_distances.tsv, or minsame/mindiff for a quick summary).

Tool-design caveat (real): this is bulk versioned TSV and tar.gz files, not a light REST call. The tool must pin the current complete PDG snapshot, cache aggressively (the snapshot changes on NCBI's build cadence, not per query), and stream or index the large TSVs rather than loading them whole. This is heavier than an E-utilities call and is the reason Q5 is a flagship differentiator (no general tool assembles this).

`source_url`: `https://www.ncbi.nlm.nih.gov/pathogens/isolates/#/search/<accession>` for the human-facing record, plus the FTP snapshot path for provenance of the assembled evidence.

## Layer 2: NCBI Datasets API v2 and PubChem PUG REST

Verified live 2026-07-25. Distinct Layer 2 surfaces from E-utilities: they return structured JSON reports and use proper HTTP error codes.

### NCBI Datasets API v2

Base: `https://api.ncbi.nlm.nih.gov/datasets/v2/` (verified 200; a `v2alpha` path also responds 200, but use the stable `v2`). No API key required for the report endpoints tested. Returns structured JSON, not Entrez XML.

Gene report (verified BRCA1, gene id 672): `GET /gene/id/{gene_id}` and `GET /gene/symbol/{symbol}/taxon/{taxon}`. Response nests under `.reports[0].gene`. Verified field set: `gene_id`, `symbol`, `description`, `taxname`, `tax_id`, `nomenclature_authority` (for example HGNC), `omim_ids` (the gene to OMIM bridge, structured), `ensembl_gene_ids`, `swiss_prot_accessions`, `chromosomes`, `map_locations`, `gene_ontology` (GO annotations, structured), `gene_groups`, `synonyms`, `alternate_names`, `protein_count`, `transcript_count`, `annotations`, `reference_standards`, `summary`, `type`, `orientation`. This is richer and more structured than the Entrez Gene ESummary, and it carries cross-reference IDs (OMIM, Ensembl, SwissProt, GO) inline, so a single Datasets call replaces several ELink hops for gene cross-refs.

Genome and assembly report (verified GCF_000001405.40): `GET /genome/accession/{accession}/dataset_report`. Response under `.reports[0]`: `accession`, `current_accession`, `paired_accession` (the GCF to GCA pairing), `organism`, `assembly_info` (`assembly_level` for example Chromosome, `assembly_name` for example GRCh38.p14), `assembly_stats`, `annotation_info`, `organelle_info`, `source_database`. This is the preferred path for the Q10 assembly bundle and for any assembly-context or version answer (the eval rubric's freshness-and-versioning criterion).

Error behavior (verified): a bad gene id returns HTTP 400 with `{"error":"Bad Request","code":400,"message":"..."}`. Unlike E-utilities, Datasets uses real HTTP status codes, so the tool can branch on status. This differs from the E-utilities 200-with-body-error pattern, so the ncbi tool layer needs per-API-family error handling.

Datasets versus E-utilities, when to use which:
- Datasets: structured JSON reports (gene, genome, taxonomy), inline cross-reference IDs, data-package downloads, proper HTTP errors. Use for gene and genome record retrieval and for assembly context.
- E-utilities: text search (ESearch), Entrez record retrieval (EFetch), and cross-database link traversal (ELink) across all 39 databases. Use for search, for databases Datasets does not cover, and for ELink traversal.

`source_url`: `https://www.ncbi.nlm.nih.gov/datasets/gene/<gene_id>/` and `https://www.ncbi.nlm.nih.gov/datasets/genome/<accession>/`.

Anchors Q3 (gene record and cross-refs) and Q10 (assembly bundle).

### PubChem PUG REST

Base: `https://pubchem.ncbi.nlm.nih.gov/rest/pug`. No API key. Rate limit is per-host (historically about 5 requests/second and no more than 400 requests/minute); throttle accordingly.

Verified endpoints:
- Properties by CID: `GET /compound/cid/{cid}/property/{prop_list}/JSON`. Verified aspirin (CID 2244): `{CID, MolecularFormula: "C9H8O4", MolecularWeight: "180.16", ConnectivitySMILES, IUPACName: "2-acetyloxybenzoic acid"}`.
- Name to CID: `GET /compound/name/{name}/cids/JSON`. Verified `aspirin` returns `{CID: [2244]}`.
- Output-format suffix pattern: append `/JSON`, `/XML`, `/CSV`, or `/property/...` to shape the response.

Drift flag (verified): the SMILES property key returned is `ConnectivitySMILES`, not the legacy `CanonicalSMILES`, even when `CanonicalSMILES` is requested in the URL. Any tool or fixture written against `CanonicalSMILES` as a response key must update.

Error behavior (verified): a bad CID returns HTTP 400 with `{"Fault": {"Code": "PUGREST.BadRequest", "Message": "Invalid ID, must be positive integer"}}`. Proper HTTP status, structured fault body.

`source_url`: `https://pubchem.ncbi.nlm.nih.gov/compound/<cid>`.

Anchors Q8 (a paper linked to a PubChem compound: resolve the CID, then link to the compound record).

## Layer 3: enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov v2)

Verified live 2026-07-25. These feed the pubtator_annotate and litvar2_lookup tools plus the clinical-trials path.

Security note (applies to all four, per ai-security-standards and production-standards): every field these APIs return is untrusted external content (abstract text, annotation labels, trial descriptions). It is data for the Write step to cite, never an instruction the agent executes. The tool that ingests each of these gets Read plus that one API only, never Write and never the ability to call other tools directly. Every string field carries a `maxLength` and every array a `maxItems` in the tool's output schema, and injected context fragments carry a hard character cap before they reach a model prompt.

### PubTator3 (base https://www.ncbi.nlm.nih.gov/research/pubtator3-api)

No API key. Feeds pubtator_annotate.

Verified endpoints:
- Entity lookup: `GET /entity/autocomplete/?query={text}&limit={n}`. Verified `BRCA1` returns `[{_id: "@GENE_BRCA1", biotype: "gene", db_id: "672", db: "ncbi_gene", name, description}]`. The `_id` is the PubTator entity id and `db_id` bridges to the NCBI database id (for example ncbi_gene 672), so this normalizes a free-text entity to a resolvable id.
- Annotation export: `GET /publications/export/biocjson?pmids={csv}`. Verified: the response nests under a top-level `{"PubTator3": [...]}` key (this is a drift point: parsers that expect a bare BioC document will fail). Annotations live at `.PubTator3[i].passages[].annotations[]`, each with an `infons` object whose verified keys are `type`, `identifier`, `normalized_id`, `normalized`, `valid`, `biotype`, `database`, `accession`, `name`. Read `normalized_id` for the canonical id (it can be null), and check `valid`. Verified entity types across records: Gene, Disease, Chemical, Species, and Variant/Mutation.
- Relations: a relations endpoint exists for entity-pair relations (chemical-disease, gene-disease); use it for relation-level enrichment.

Error and empty behavior (verified): entity autocomplete on a no-match query returns an empty array `[]` with HTTP 200 (the cite-or-refuse empty signal). The biocjson export on a nonexistent PMID returns HTTP 400 with `{"detail": "Could not retrieve publications"}`, so this endpoint uses a real error status, unlike E-utilities.

`source_url`: annotations cite back to the source PMID at `https://pubmed.ncbi.nlm.nih.gov/<pmid>/`.

### LitVar2 (base https://www.ncbi.nlm.nih.gov/research/litvar2-api)

No API key. Feeds litvar2_lookup (variant to literature).

Verified endpoints:
- Variant search: `GET /variant/autocomplete/?query={rsid or hgvs or name}`. Verified `rs334` returns `[{_id: "litvar@rs334##", rsid: "rs334", gene: ["HBB"], name: "c.20A>T", hgvs: "c.20A>T", pmids_count: 589, flag_rsid_variant: true, data_clinical_significance: ["protective", "pathogenic", ...]}]`. The litvar id format is `litvar@rs334##`.
- Publications for a variant: `GET /variant/get/{litvar_id}/publications`. The id must be URL-encoded (`@` as `%40`, `#` as `%23`), for example `.../variant/get/litvar%40rs334%23%23/publications`. Verified: returns `{"pmids": [33593344, 35964929, ...]}` (589 PMIDs for rs334).

Use LitVar2 to attach the literature evidence set to a variant that dbSNP or ClinVar surfaced, with `pmids_count` as a quick evidence-weight signal.

Error and empty behavior (verified): variant autocomplete on a no-match query returns an empty array `[]` with HTTP 200 (the cite-or-refuse empty signal).

`source_url`: `https://www.ncbi.nlm.nih.gov/research/litvar2/#!?query=<litvar_id>`, plus each cited PMID.

### LitSense (base https://www.ncbi.nlm.nih.gov/research/litsense-api)

No API key, no documented rate limit. Sentence-level literature search (finer grain than article-level PubMed).

Verified endpoint: `GET /api/?query={text}&limit={n}`. The trailing slash before the query string is required, without it the server responds HTTP 301 (my first probes used `api/search/` and got HTTP 404, so the exact path is `api/` directly). Verified response: an array of `{text (the matched sentence), score (relevance), section (title, abstract, body, or null), pmid, pmcid, annotations[] (entities as position|length|type|identifier)}`. Verified example matched a BRCA1-breast-cancer sentence with score 1.0.

Use LitSense when the answer needs a specific supporting sentence rather than a whole article, which sharpens the citation. No moat-seven CQ currently requires it, so it is a supporting tool, not a v1 must-build.

`source_url`: the cited `pmid`/`pmcid`.

### ClinicalTrials.gov API v2 (base https://clinicaltrials.gov/api/v2)

No API key. Feeds the disease-to-trials path (anchors Q4).

Verified endpoint: `GET /studies?query.cond={condition}&pageSize={n}&countTotal=true`. Verified `query.cond=cystic fibrosis` returns `{studies: [...], totalCount: 1763, nextPageToken}`. Query params: `query.cond` (condition), `query.term` (free text), `query.intr` (intervention), `filter.overallStatus` (for example RECRUITING), `pageSize`, `pageToken`, and `fields` to project.

Response: each study has a `protocolSection` with verified modules `identificationModule` (nctId, briefTitle, officialTitle), `statusModule` (overallStatus, dates), `conditionsModule`, `armsInterventionsModule`, `eligibilityModule` (criteria, sex, ages), `descriptionModule`, `designModule`, `outcomesModule`, `sponsorCollaboratorsModule`, `contactsLocationsModule`, `oversightModule`. Paging via `nextPageToken`.

Error and empty behavior: a query with no matches returns `studies: []` with `totalCount: 0` (structured empty, the cite-or-refuse trigger).

`source_url`: `https://clinicaltrials.gov/study/<nctId>`.

## Tool-layer design implications (from the reference mining)

Four agents mined the Agentic-Search reference repository for design intent behind the Layer 2/3 tool layer. The load-bearing implications for the Step 4.1 tool specs:

- The API-caller pattern (prior art): a non-LLM code tool executes the planner's call list (ELink, EFetch, Datasets, PubTator3, LitVar2, LitSense, ClinicalTrials) in parallel with the graph query, manages rate limits and caching, and never lets the LLM see raw Layer 2/3 payloads for factual claims. The model sees only structured fields the tool extracted. This is the concrete instance of specialize-by-tool-access (system-design-patterns rule 8) and the untrusted-source reader gate.
- Error handling branches by API family (verified live): E-utilities returns HTTP 200 for both empty results and errors, with the error in the body (esearchresult.ERROR), and it silently falls back to a broad search on an unknown field tag. Datasets, PubChem, and ClinicalTrials.gov use proper HTTP status codes (400 with a structured fault body). The tool layer must inspect the E-utilities body but can branch on HTTP status for the JSON APIs.
- Rate limits and caching: E-utilities is 3 requests/second without a key and 10/second with a free key (key in an env var only, never in code or logs). Variation Services is about 1/second. PubChem is about 5/second. PubTator3, LitVar2, LitSense, and ClinicalTrials.gov need no key. Reference-proposed cache TTLs: gene data 1 week, variant data 1 week, publication data 1 day. The reference Layer 2 budget is at most about 20 API calls per user query, response-cached (Redis), at 200 to 500ms per call.
- Untrusted-source tier separation: the reference names a reader, orchestrator, analyzer, writer split as the cheapest prompt-injection defense for retrieval-heavy pipelines. Enforce the schema rules from production-standards on every tool output: maxLength on every string, maxItems on every array, and a host-pinned URL regex for source_url, for example `^https://([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/` (and the clinicaltrials.gov and equivalent hosts for Layer 3).
- Fail loud, retry-safe: Layer 2/3 wrappers must never silently default on timeout or serve a stale cache as fresh, because a silent default teaches the agent a false model of API reliability. Use a transient, recoverable, unexpected error taxonomy with backoff for the transient class, and keep tool calls idempotent so the Act step can retry (production-standards retry-safety gate).
- Per-call timeouts: observed interactive latencies are 1 to 2 seconds (EInfo 1.7s, ESummary and ESearch similar). Recommended per-call timeouts for Step 4.1: 15 seconds with backoff for the interactive HTTPS APIs (E-utilities, Datasets, Variation Services, PubChem, and the enrichment APIs), and a longer budget (60 seconds or more) for the Pathogen Detection FTP bulk files, which transfer large TSVs. The reference PoC used a 30-second cap on the graph Cypher query, which is the value to carry into the cypher_query tool. These pair with the per-query cost cap and the per-step timeout in the harness (system-design-patterns rule 4).
- Truncate before context: apply just-in-time retrieval, observation masking, and subagent summarization to shape large NCBI and enrichment payloads before they enter the model context, and truncate large result sets to the first N with a total count (system-design-patterns rule 7). This directly mitigates the hallucination risk from inlining large Cypher or API result sets.
- Prompt-cache discipline: freeze and deterministically sort the tool list, because a tool-schema mutation, reorder, or timestamp injection mid-session busts the KV cache and forces a full recompute.
- The per-competency-question I/O spec: reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/02_Tier1_eval_spec.md holds, for each Tier-1 competency question, its required and optional databases plus the required IDs and fields the answer must return. Use it as the per-tool input/output contract when writing the tool specs in Step 4.1.

## Moat-seven competency question to API anchor map

Each moat question maps to the APIs and tools that answer it. This is the coverage the tool specs must deliver.

| CQ | Wedge | APIs it exercises | Primary tools |
|----|-------|-------------------|---------------|
| Q1 | CNV region to cited evidence | dbVar (two-step coordinate overlap), ClinVar (C37 coordinate path), Gene (overlapping genes), OMIM (gene to MIM), Variation Viewer citation link (human-facing web UI at ncbi.nlm.nih.gov/variation/view, a source_url target, not an API) | ncbi_efetch |
| Q3 | BRCA1 cross-database hub | Gene and Datasets v2 (gene report and cross-refs), PubMed, ClinVar, GTR, MedGen | cypher_query (graph traversal), ncbi_efetch |
| Q4 | disease phrase routed | MedGen (concept hub), ClinVar, GTR, PubMed, ClinicalTrials.gov, Gene | ncbi_efetch, ClinicalTrials path |
| Q5 | Salmonella isolate to outbreak context | Pathogen Detection FTP (cluster_list, SNP_distances, AMR), BioSample, SRA | pathogen tool (FTP) |
| Q6 | natural-language SRA metadata | SRA (ESearch indexed fields plus EFetch sample attributes) | ncbi_efetch |
| Q8 | PMID to linked data | ELink (direct, inferred, absent), SRA, BioProject, GEO, Assembly, PubChem | ncbi_efetch (elink path) |
| Q10 | BioProject to data bundle | BioProject to BioSample to SRA (ELink), Assembly (Datasets v2) | ncbi_efetch, Datasets |

Cross-cutting output requirements for every tool (from the reference mining and the citations-non-negotiable rule): provenance and source_url on every returned record, an explicit not-found signal rather than silence, assembly and version context on any coordinate or sequence answer, and deterministic IDs and a clear schema for the AI and MCP consumer persona.

## Open items and drift flags

Drift found live versus the 2026-04-20 reference doc:

- ClinVar ESummary now returns `germline_classification` (an object with description, review_status, last_evaluated, trait_set xrefs), not a flat `clinical_significance` scalar; the field count grew from 44 to 47.
- PubChem PUG REST returns the SMILES property key as `ConnectivitySMILES`, not the legacy `CanonicalSMILES`.
- PubTator3 biocjson nests under a top-level `{"PubTator3": [...]}` key, and its annotation `infons` carry `normalized_id` (canonical, can be null) plus `valid` and `biotype`.
- EGQuery 301-redirects to an unresolvable internal host: fall back to parallel `esearch.fcgi?rettype=count` per database for global counts.
- LitSense is at `research/litsense-api/api/?query=`, and the trailing slash before the query string is required (otherwise HTTP 301; a `/search/` path returns 404).

Open items carried to Step 4.1 and beyond:

- The reference-copy NCBI doc (Data/reference, dated April 2) is stale; docs/NCBI_databases_and_APIs_reference.md (April 20) is authoritative.
- No numeric NCBI rate-limit figures exist in the proposal subtree; use the verified 3 and 10 per second for E-utilities and about 1/second for Variation Services.
- OMIM full narrative content needs api.omim.org (key-gated); Entrez supplies the MIM number and title only, which is enough for a cited link.
- The UCSC segmental-duplication source for the Q1 seg-dup fast-follow still needs a design (deferred, not v1).
- Scope reconciliation note: an older innovation proposal excluded SRA, dbGaP, and PubChem from the alpha. The locked PRD and the evaluation playbook (the moat-seven) are authoritative and include SRA (Q5, Q6) and PubChem (Q8). Flag if the older proposal scope resurfaces.

Last updated: 2026-07-25. Verification method: live production-endpoint probes plus a four-agent reference-repository mining. This sheet feeds Step 4.1 (the tech-spec outline and the per-tool specifications).
