# E. coli metadata AMR-genotype scan probe

Probed on 2026-09-22. Live measurement against the real NCBI Pathogen Detection FTP snapshot tree (`ftp.ncbi.nlm.nih.gov/pathogen/Results/`), using `pathogen_ftp_transport.resolve_complete_snapshot` and `stream_filtered_tsv_rows` exactly as the shipped tool calls them. Purpose: decide whether a bounded scan of a taxon's Metadata TSV can find isolates carrying a given AMR genotype (ESBL genes as the test case) inside a 120 second budget, for a planned third mode of `pathogen_detection.py`.

## A. Snapshot resolution: taxon folder and snapshot id

```
Root listing GET: https://ftp.ncbi.nlm.nih.gov/pathogen/Results/
Root listing elapsed: 1.377s
All taxon folders (107):
  Acinetobacter
  Aeromonas
  Aeromonas_salmonicida
  Aeromonas_sobria
  Aeromonas_veronii
  Bacillus_cereus_group
  Bacillus_inaquosorum
  BioProject_Hierarchy
  Burkholderia_cepacia_complex
  Burkholderia_mallei
  Campylobacter
  Candidozyma_auris
  Citrobacter_freundii
  Citrobacter_portucalensis
  Clostridioides_difficile
  Clostridium_botulinum
  Clostridium_perfringens
  Corynebacterium_striatum
  Cronobacter
  Edwardsiella_ictaluri
  Edwardsiella_piscicida
  Edwardsiella_tarda
  Elizabethkingia
  Enterobacter_asburiae
  Enterobacter_bugandensis
  Enterobacter_cancerogenus
  Enterobacter_chengduensis
  Enterobacter_chuandaensis
  Enterobacter_cloacae
  Enterobacter_hormaechei
  Enterobacter_intestinihominis
  Enterobacter_kobei
  Enterobacter_ludwigii
  Enterobacter_mori
  Enterobacter_oligotrophicus
  Enterobacter_quasiroggenkampii
  Enterobacter_roggenkampii
  Enterobacter_sichuanensis
  Enterobacter_soli
  Enterococcus_faecalis
  Enterococcus_faecium
  Enterococcus_hirae
  Escherichia_coli_Shigella
  Flavobacterium_psychrophilum
  Haemophilus_influenzae
  Klebsiella
  Klebsiella_oxytoca
  Kluyvera_intermedia
  Kosakonia_oryzendophytica
  Kosakonia_oryziphila
  Legionella_anisa
  Legionella_bozemanae
  Legionella_cherrii
  Legionella_feeleii
  Legionella_pneumophila
  Listeria
  Listeria_innocua
  Mannheimia_haemolytica
  Morganella
  Mycobacterium_tuberculosis
  Neisseria_bacilliformis
  Neisseria_cinerea
  Neisseria_elongata
  Neisseria_flava
  Neisseria_gonorrhoeae
  Neisseria_lactamica
  Neisseria_meningitidis
  Neisseria_oralis
  Neisseria_perflava
  Neisseria_polysaccharea
  Neisseria_subflava
  Neisseria_weaveri
  Pasteurella_multocida
  Photobacterium_damselae
  Phytobacter_massiliensis
  Pluralibacter_gergoviae
  Providencia
  Pseudomonas_aeruginosa
  Pseudomonas_putida
  Salmonella
  Serratia
  Shewanella_algae
  Staphylococcus_aureus
  Staphylococcus_pseudintermedius
  Stenotrophomonas_maltophilia
  Streptococcus_agalactiae
  Streptococcus_equi
  Streptococcus_iniae
  Streptococcus_mutans
  Streptococcus_pneumoniae
  Streptococcus_pyogenes
  Streptococcus_suis
  Treponema_pallidum
  Vibrio_alginolyticus
  Vibrio_antiquarius
  Vibrio_cholerae
  Vibrio_diabolicus
  Vibrio_fluvialis
  Vibrio_harveyi
  Vibrio_metoecus
  Vibrio_metschnikovii
  Vibrio_mimicus
  Vibrio_owensii
  Vibrio_parahaemolyticus
  Vibrio_vulnificus
  Yersinia_enterocolitica
  Yersinia_ruckeri

E. coli / Shigella candidate folders: ['Escherichia_coli_Shigella', 'Yersinia_enterocolitica']

Chosen taxon folder: Escherichia_coli_Shigella
resolve_complete_snapshot('Escherichia_coli_Shigella') -> PDG000000004.6314
resolve_complete_snapshot elapsed: 0.590s
```

Taxon folder is 'Escherichia_coli_Shigella'; resolved complete snapshot is 'PDG000000004.6314'. Resolution (root listing + snapshot walk) took 1.97s total, well inside a 120s budget.

## B. Metadata TSV: URL, size, header row

```
Metadata TSV URL: https://ftp.ncbi.nlm.nih.gov/pathogen/Results/Escherichia_coli_Shigella/PDG000000004.6314/Metadata/PDG000000004.6314.metadata.tsv
HEAD status: 200
HEAD elapsed: 0.040s
Content-Length (bytes): 546535269
Content-Length (MB): 521.22
Header row (67 columns), verbatim:
  [0] #label
  [1] FDA_lab_id
  [2] HHS_region
  [3] IFSAC_category
  [4] LibraryLayout
  [5] PFGE_PrimaryEnzyme_pattern
  [6] PFGE_SecondaryEnzyme_pattern
  [7] Platform
  [8] Run
  [9] asm_acc
  [10] asm_level
  [11] asm_stats_contig_n50
  [12] asm_stats_length_bp
  [13] asm_stats_n_contig
  [14] assembly_method
  [15] attribute_package
  [16] bioproject_acc
  [17] bioproject_center
  [18] biosample_acc
  [19] isolate_identifiers
  [20] collected_by
  [21] collection_date
  [22] epi_type
  [23] fullasm_id
  [24] geo_loc_name
  [25] host
  [26] host_disease
  [27] isolation_source
  [28] lat_lon
  [29] ontological_term
  [30] outbreak
  [31] sample_name
  [32] scientific_name
  [33] serovar
  [34] source_type
  [35] species_taxid
  [36] sra_center
  [37] sra_release_date
  [38] strain
  [39] sequenced_by
  [40] project_name
  [41] food_origin
  [42] target_acc
  [43] target_creation_date
  [44] taxid
  [45] wgs_acc_prefix
  [46] wgs_master_acc
  [47] minsame
  [48] mindiff
  [49] computed_types
  [50] number_drugs_resistant
  [51] number_drugs_intermediate
  [52] number_drugs_susceptible
  [53] number_drugs_tested
  [54] number_amr_genes
  [55] number_core_amr_genes
  [56] AST_phenotypes
  [57] AMR_genotypes
  [58] AMR_genotypes_core
  [59] number_stress_genes
  [60] stress_genotypes
  [61] number_virulence_genes
  [62] virulence_genotypes
  [63] amrfinder_version
  [64] refgene_db_version
  [65] amrfinder_analysis_type
  [66] amrfinder_applied

AMR genotype column(s) present: ['AMR_genotypes']
AST phenotype column(s) present: ['AST_phenotypes']
All AMR/AST/genotype/phenotype-related columns found: ['wgs_master_acc', 'number_amr_genes', 'number_core_amr_genes', 'AST_phenotypes', 'AMR_genotypes', 'AMR_genotypes_core', 'stress_genotypes', 'virulence_genotypes', 'amrfinder_version', 'amrfinder_analysis_type', 'amrfinder_applied']
```

Metadata TSV is 521.2 MB. AMR genotype column is 'AMR_genotypes'. No separate 'core' AMR genotype column or AST phenotype column beyond what is listed above.

## C. AMR genotype row format, first 200 rows

```
Rows read: 200
AMR genotype column index: 57
Elapsed: 0.196s

First 5 non-empty 'AMR_genotypes' values, verbatim:
  1. "acrF,blaEC,mdtM"
  2. "aadA1,acrF,blaEC,mdtM,sul1,tet(A)"
  3. "acrF,blaEC,mdtM"
  4. "acrF,blaEC,mdtM"
  5. "acrF,aph(3'')-Ib,aph(6)-Id,blaEC,mdtM,sul2,tet(A)"
```

Out of the first 200 rows, 5 example(s) of non-empty 'AMR_genotypes' values were captured above; see their separator and gene spelling for the third mode's parsing design. The value is a double-quoted, comma-joined list, matching `_parse_pathogen_list_field`'s documented shape exactly. None of these 5 examples carry a `=COMPLETE`/`=PARTIAL` or similar suffix on a gene name; every gene token shown here is bare (`acrF`, `blaEC`, `mdtM`, `aadA1`, `sul1`, `tet(A)`, `aph(3'')-Ib`, `aph(6)-Id`, `sul2`), so the existing parser needs no change for this decoration on this snapshot, though this was only checked against these 5 examples, not the full 279100-row ESBL match set from section D (which only recorded the matched gene-prefix label, not the full field value).

## D. Scan for ESBL genes, 120s deadline

```
Deadline budget: 120s
Elapsed: 17.651s
Rows scanned: 584433
Matching rows: 279100
Truncated by deadline: False

First 10 matches:
  1. biosample_acc=SAMN02442782 strain=AZ-TG59959 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  2. biosample_acc=SAMN02442784 strain=AZ-TG59983 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  3. biosample_acc=SAMN02442787 strain=AZ-TG60279 geo_loc_name=USA:AZ collection_date=2013-03-19 matched_genes=['blaTEM-']
  4. biosample_acc=SAMN02442772 strain=AZ-TG56155 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
  5. biosample_acc=SAMN02442778 strain=AZ-TG59911 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  6. biosample_acc=SAMN02442781 strain=AZ-TG59947 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  7. biosample_acc=SAMN02442786 strain=AZ-TG60007 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  8. biosample_acc=SAMN02442791 strain=AZ-TG60327 geo_loc_name=USA:AZ collection_date=2013-03-19 matched_genes=['blaTEM-']
  9. biosample_acc=SAMN02442767 strain=AZ-TG56075 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
  10. biosample_acc=SAMN02442768 strain=AZ-TG56091 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
```

At a 120s budget: 584433 rows scanned, 279100 ESBL matches found, reached end of file before the deadline. `stream_filtered_tsv_rows` accepts `max_matches`, which stops the scan once N rows matching an EXACT key_values membership test have been collected. It has no substring/contains matcher, so it cannot be reused as-is for a 'contains any of these gene prefixes' filter; a third mode would need its own row-filter callable (or an extended transport function taking a predicate) that still stops after N matches the way max_matches does today.

## D. Scan for ESBL genes, 60s deadline

```
Deadline budget: 60s
Elapsed: 20.259s
Rows scanned: 584433
Matching rows: 279100
Truncated by deadline: False

First 10 matches:
  1. biosample_acc=SAMN02442782 strain=AZ-TG59959 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  2. biosample_acc=SAMN02442784 strain=AZ-TG59983 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  3. biosample_acc=SAMN02442787 strain=AZ-TG60279 geo_loc_name=USA:AZ collection_date=2013-03-19 matched_genes=['blaTEM-']
  4. biosample_acc=SAMN02442772 strain=AZ-TG56155 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
  5. biosample_acc=SAMN02442778 strain=AZ-TG59911 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  6. biosample_acc=SAMN02442781 strain=AZ-TG59947 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  7. biosample_acc=SAMN02442786 strain=AZ-TG60007 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  8. biosample_acc=SAMN02442791 strain=AZ-TG60327 geo_loc_name=USA:AZ collection_date=2013-03-19 matched_genes=['blaTEM-']
  9. biosample_acc=SAMN02442767 strain=AZ-TG56075 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
  10. biosample_acc=SAMN02442768 strain=AZ-TG56091 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
```

At a 60s budget: 584433 rows scanned, 279100 ESBL matches found, reached end of file before the deadline. `stream_filtered_tsv_rows` accepts `max_matches`, which stops the scan once N rows matching an EXACT key_values membership test have been collected. It has no substring/contains matcher, so it cannot be reused as-is for a 'contains any of these gene prefixes' filter; a third mode would need its own row-filter callable (or an extended transport function taking a predicate) that still stops after N matches the way max_matches does today.

## D. Scan for ESBL genes, 30s deadline

```
Deadline budget: 30s
Elapsed: 26.474s
Rows scanned: 584433
Matching rows: 279100
Truncated by deadline: False

First 10 matches:
  1. biosample_acc=SAMN02442782 strain=AZ-TG59959 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  2. biosample_acc=SAMN02442784 strain=AZ-TG59983 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  3. biosample_acc=SAMN02442787 strain=AZ-TG60279 geo_loc_name=USA:AZ collection_date=2013-03-19 matched_genes=['blaTEM-']
  4. biosample_acc=SAMN02442772 strain=AZ-TG56155 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
  5. biosample_acc=SAMN02442778 strain=AZ-TG59911 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  6. biosample_acc=SAMN02442781 strain=AZ-TG59947 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  7. biosample_acc=SAMN02442786 strain=AZ-TG60007 geo_loc_name=USA:AZ collection_date=2013-03-05 matched_genes=['blaTEM-']
  8. biosample_acc=SAMN02442791 strain=AZ-TG60327 geo_loc_name=USA:AZ collection_date=2013-03-19 matched_genes=['blaTEM-']
  9. biosample_acc=SAMN02442767 strain=AZ-TG56075 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
  10. biosample_acc=SAMN02442768 strain=AZ-TG56091 geo_loc_name=USA:AZ collection_date=2013-02-13 matched_genes=['blaTEM-']
```

At a 30s budget: 584433 rows scanned, 279100 ESBL matches found, reached end of file before the deadline. `stream_filtered_tsv_rows` accepts `max_matches`, which stops the scan once N rows matching an EXACT key_values membership test have been collected. It has no substring/contains matcher, so it cannot be reused as-is for a 'contains any of these gene prefixes' filter; a third mode would need its own row-filter callable (or an extended transport function taking a predicate) that still stops after N matches the way max_matches does today.

## E. Time to 1st, 10th, 20th match

```
Time to 1st match: 0.131s
Time to 10th match: 0.131s
Time to 20th match: 0.131s
Total matches found within 120s: 279100
```

These times are from the 120s run above. If the 20th match arrives within a few seconds, a stop-after-N-matches design gives a fast, useful response even though a full scan of the file takes far longer.

## F. Total row count

```
Total data rows in the Metadata TSV: 584433 (full file scanned within the 120s budget).
```

The 120s scan reached end of file, so this is an exact count, not an estimate.

## Design note: the prefix filter over-matches true ESBL

279100 of 584433 rows (47.8%) matched the `blaCTX-M`/`blaSHV-`/`blaTEM-`/`blaOXA-` prefix filter, and every one of the first 10 matches carries only `blaTEM-`. `blaTEM-1` (the most common E. coli TEM allele) is a plain broad-spectrum beta-lactamase, not an ESBL: only specific TEM alleles (for example TEM-3, TEM-10, TEM-26) confer the extended-spectrum phenotype. A prefix match on `blaTEM-` alone therefore returns mostly non-ESBL isolates alongside genuine ones. This does not change any number measured above (the scan and its speed are real), but it means the third mode's gene list needs to be exact allele numbers for TEM and SHV, not bare prefixes; `blaCTX-M` and most `blaOXA-` extended-spectrum variants are safer as prefixes since ESBL activity is closer to family-wide for those two.
