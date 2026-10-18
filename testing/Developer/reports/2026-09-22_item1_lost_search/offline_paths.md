# Template path per golden question, offline, from the 2026-09-22 consistency run

Computed by `offline_paths.py` with the template chooser as it stands when the
script runs; the last column is what the question's own graph call returned on
develop during the morning run, before any change in this folder.

| id | run | class | entities | anchor | shapes | template now | own call then |
|---|---|---|---|---|---|---|---|
| G-001 | 1 | aggregate |  |  |  | (no entity) | error 0 |
| G-001 | 2 | aggregate |  |  |  | (no entity) | error 0 |
| G-001 | 3 | aggregate |  |  |  | (no entity) | error 0 |
| G-002 | 1 | aggregate | 1 | Gene | diseases, variants, articles | gene_variant_diseases_one | ok 100 |
| G-002 | 2 | exploratory | 1 | Gene | diseases, variants, articles | gene_variant_diseases_one | ok 100 |
| G-002 | 3 | exploratory | 1 | Gene | diseases, variants, articles | gene_variant_diseases_one | ok 100 |
| G-003 | 1 | exploratory | 1 | Disease | genes | disease_genes_one | ok 12 |
| G-003 | 2 | exploratory | 1 | Disease | genes | disease_genes_one | ok 12 |
| G-003 | 3 | exploratory |  |  |  | (no entity) | error 0 |
| G-004 | 1 | multi_hop | 2 | Disease | genes | disease_genes_many | ok 2 |
| G-004 | 2 | multi_hop | 2 | Disease | genes | disease_genes_many | ok 2 |
| G-004 | 3 | multi_hop | 2 | Disease | genes | disease_genes_many | ok 2 |
| G-005 | 1 | aggregate | 3 | Disease | none | None (model path) | empty 0 |
| G-005 | 2 | multi_hop | 3 | Disease | none | None (model path) | empty 0 |
| G-005 | 3 | exploratory |  |  |  | (no entity) |  |
| G-006 | 1 | aggregate | 1 | Article | none | None (model path) | error 0 |
| G-006 | 2 | lookup | 1 | Article | none | article_record_one | ok 1 |
| G-006 | 2_client_asleep | multi_hop | 1 | Article | none | None (model path) |  |
| G-006 | 3 | multi_hop | 1 | Article | none | None (model path) | ok 1 |
| G-007 | 1 | single_hop |  |  |  | (no entity) | error 0 |
| G-007 | 2 | multi_hop |  |  |  | (no entity) | error 0 |
| G-007 | 3 | exploratory |  |  |  | (no entity) | error 0 |
| G-008 | 1 | (guardrail) |  |  |  |  |  |
| G-008 | 2 | (guardrail) |  |  |  |  |  |
| G-008 | 3 | (guardrail) |  |  |  |  |  |
| G-009 | 1 | (guardrail) |  |  |  |  |  |
| G-009 | 2 | (guardrail) |  |  |  |  |  |
| G-009 | 3 | (guardrail) |  |  |  |  |  |
| G-010 | 1 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-010 | 2 | aggregate | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-010 | 3 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-011 | 1 | multi_hop | 10 | mixed | (mixed labels) | gene_diseases_many | error 0 |
| G-011 | 2 | multi_hop | 2 | Gene | diseases | gene_diseases_many | ok 13 |
| G-011 | 3 | multi_hop | 2 | Gene | diseases | gene_diseases_many | ok 13 |
| G-012 | 1 | single_hop | 8 | Disease | none | None (model path) | empty 0 |
| G-012 | 2 | exploratory | 8 | Disease | none | disease_record_many | error 0 |
| G-012 | 3 | lookup | 8 | Disease | none | disease_record_many | ok 8 |
| G-013 | 1 | single_hop | 1 | Gene | diseases | gene_diseases_one | ok 4 |
| G-013 | 2 | single_hop | 1 | Gene | diseases | gene_diseases_one | ok 4 |
| G-013 | 3 | single_hop | 1 | Gene | diseases | gene_diseases_one | ok 4 |
| G-014 | 1 | single_hop |  |  |  | (no entity) |  |
| G-014 | 2 | multi_hop |  |  |  | (no entity) |  |
| G-014 | 3 | single_hop | 8 | Disease | none | None (model path) | empty 0 |
| G-015 | 1 | (guardrail) |  |  |  |  |  |
| G-015 | 2 | (guardrail) |  |  |  |  |  |
| G-015 | 3 | (guardrail) |  |  |  |  |  |
| G-016 | 1 | multi_hop | 1 | Gene | orthologs | gene_orthologs_one | ok 100 |
| G-016 | 2 | single_hop | 1 | Gene | orthologs | gene_orthologs_one | ok 100 |
| G-016 | 3 | single_hop | 1 | Gene | orthologs | gene_orthologs_one | ok 100 |
| G-017 | 1 | exploratory | 1 | Gene | processes | gene_processes_one | empty 0 |
| G-017 | 2 | exploratory | 1 | Gene | processes | gene_processes_one | empty 0 |
| G-017 | 3 | exploratory | 1 | Gene | processes | gene_processes_one | empty 0 |
| G-018 | 1 | single_hop | 1 | Gene | components | gene_components_one | empty 0 |
| G-018 | 2 | single_hop | 1 | Gene | components | gene_components_one | empty 0 |
| G-018 | 3 | single_hop | 1 | Gene | components | gene_components_one | empty 0 |
| G-019 | 1 | lookup | 1 | Article | mesh | article_mesh_one | ok 26 |
| G-019 | 2 | (guardrail) |  |  |  |  |  |
| G-019 | 3 | lookup | 1 | Article | mesh | article_mesh_one | ok 26 |
| G-020 | 1 | lookup | 1 | Gene | taxon | gene_taxon_one | ok 1 |
| G-020 | 2 | single_hop | 1 | Gene | taxon | gene_taxon_one | ok 1 |
| G-020 | 3 | single_hop | 1 | Gene | taxon | gene_taxon_one | ok 1 |
| G-021 | 1 | exploratory | 1 | Gene | articles | gene_articles_one | ok 100 |
| G-021 | 2 | exploratory | 1 | Gene | articles | gene_articles_one | ok 100 |
| G-021 | 3 | exploratory | 1 | Gene | articles | gene_articles_one | ok 100 |
| G-022 | 1 | single_hop | 1 | Disease | phenotypes | disease_phenotypes_one | empty 0 |
| G-022 | 2 | single_hop | 1 | Disease | phenotypes | disease_phenotypes_one | empty 0 |
| G-022 | 3 | exploratory | 1 | Disease | phenotypes | disease_phenotypes_one | empty 0 |
| G-023 | 1 | multi_hop | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-023 | 2 | multi_hop | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-023 | 3 | multi_hop | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-024 | 1 | single_hop | 1 | mixed | (mixed labels) | None (model path) | empty 0 |
| G-024 | 2 | single_hop | 1 | mixed | (mixed labels) | None (model path) | empty 0 |
| G-024 | 3 | single_hop | 1 | mixed | (mixed labels) | None (model path) | empty 0 |
| G-025 | 1 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-025 | 1_client_asleep | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-025 | 2 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-025 | 3 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-026 | 1 | single_hop | 1 | Disease | genes | disease_genes_one | ok 4 |
| G-026 | 2 | single_hop | 1 | Disease | genes | disease_genes_one | ok 4 |
| G-026 | 3 | single_hop | 1 | Disease | genes | disease_genes_one | ok 4 |
| G-027 | 1 | single_hop | 1 | Disease | none | None (model path) | empty 0 |
| G-027 | 2 | lookup | 1 | Disease | none | disease_record_one | ok 1 |
| G-027 | 3 | single_hop | 1 | Disease | none | None (model path) | empty 0 |
| G-028 | 1 | exploratory | 2 | mixed | (mixed labels) | gene_disease_link | empty 0 |
| G-028 | 1_client_asleep | exploratory | 2 | mixed | (mixed labels) | gene_disease_link | empty 0 |
| G-028 | 2 | multi_hop | 2 | mixed | (mixed labels) | gene_disease_link | empty 0 |
| G-028 | 3 | exploratory | 2 | mixed | (mixed labels) | gene_disease_link | empty 0 |
| G-029 | 1 | single_hop | 1 | Disease | genes | disease_genes_one | ok 4 |
| G-029 | 2 | single_hop | 1 | Disease | genes | disease_genes_one | ok 4 |
| G-029 | 3 | single_hop | 1 | Disease | genes | disease_genes_one | ok 4 |
| G-030 | 1 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-030 | 2 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-030 | 3 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-031 | 1 | single_hop | 1 | Gene | activities | gene_activities_one | empty 0 |
| G-031 | 2 | single_hop | 1 | Gene | activities | gene_activities_one | empty 0 |
| G-031 | 3 | lookup | 1 | Gene | activities | gene_activities_one | empty 0 |
| G-032 | 1 | single_hop | 1 | Gene | processes | gene_processes_one | empty 0 |
| G-032 | 2 | single_hop | 1 | Gene | processes | gene_processes_one | empty 0 |
| G-032 | 3 | single_hop | 1 | Gene | processes | gene_processes_one | empty 0 |
| G-033 | 1 | exploratory | 3 | mixed | (mixed labels) | gene_diseases_many | error 0 |
| G-033 | 2 | exploratory | 3 | mixed | (mixed labels) | gene_diseases_many | error 0 |
| G-033 | 3 | exploratory | 3 | mixed | (mixed labels) | gene_diseases_many | error 0 |
| G-034 | 1 | aggregate | 8 | Disease | genes | None (model path) | ok 1 |
| G-034 | 2 | aggregate | 8 | Disease | genes | None (model path) | ok 1 |
| G-034 | 3 | aggregate | 8 | Disease | genes | None (model path) | ok 1 |
| G-035 | 1 | aggregate |  |  |  | (no entity) | error 0 |
| G-035 | 2 | aggregate |  |  |  | (no entity) | error 0 |
| G-035 | 3 | exploratory |  |  |  | (no entity) | error 0 |
| G-036 | 1 | exploratory |  |  |  | (no entity) |  |
| G-036 | 2 | exploratory |  |  |  | (no entity) |  |
| G-036 | 3 | exploratory |  |  |  | (no entity) |  |
| G-037 | 1 | single_hop | 1 | Gene | none | gene_record_one | error 0 |
| G-037 | 2 | multi_hop | 1 | Gene | none | gene_record_one | error 0 |
| G-037 | 3 | exploratory | 9 | mixed | (mixed labels) | gene_record_one | error 0 |
| G-038 | 1 | (guardrail) |  |  |  |  |  |
| G-038 | 2 | (guardrail) |  |  |  |  |  |
| G-038 | 3 | (guardrail) |  |  |  |  |  |
| G-039 | 1 | exploratory | 1 | Gene | none | gene_record_one | error 0 |
| G-039 | 1_client_asleep | exploratory | 1 | Gene | none | gene_record_one |  |
| G-039 | 2 | exploratory | 1 | Gene | none | gene_record_one | error 0 |
| G-039 | 3 | exploratory | 1 | Gene | none | gene_record_one | ok 1 |
| G-040 | 1 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-040 | 2 | multi_hop | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-040 | 3 | exploratory | 1 | Gene | variants | gene_variants_one | ok 100 |
| G-041 | 1 | single_hop |  |  |  | (no entity) |  |
| G-041 | 2 | single_hop |  |  |  | (no entity) |  |
| G-041 | 3 | single_hop |  |  |  | (no entity) |  |
| G-042 | 1 | (guardrail) |  |  |  |  |  |
| G-042 | 2 | (guardrail) |  |  |  |  |  |
| G-042 | 3 | (guardrail) |  |  |  |  |  |
| G-043 | 1 | (guardrail) |  |  |  |  |  |
| G-043 | 2 | (guardrail) |  |  |  |  |  |
| G-043 | 3 | (guardrail) |  |  |  |  |  |
| G-044 | 1 | (guardrail) |  |  |  |  |  |
| G-044 | 2 | (guardrail) |  |  |  |  |  |
| G-044 | 3 | (guardrail) |  |  |  |  |  |
| G-045 | 1 | (guardrail) |  |  |  |  |  |
| G-045 | 2 | (guardrail) |  |  |  |  |  |
| G-045 | 3 | (guardrail) |  |  |  |  |  |
| G-046 | 1 | lookup | 8 | Disease | none | disease_record_many | ok 7 |
| G-046 | 2 | single_hop | 8 | Disease | none | None (model path) | empty 0 |
| G-046 | 3 | single_hop | 8 | Disease | none | None (model path) | empty 0 |
| G-047 | 1 | exploratory | 2 | Disease | none | disease_record_many | ok 100 |
| G-047 | 2 | exploratory | 2 | Disease | none | disease_record_many | empty 0 |
| G-047 | 3 | exploratory | 2 | Disease | none | disease_record_many | ok 100 |
| G-048 | 1 | lookup |  |  |  | (no entity) | error 0 |
| G-048 | 2 | single_hop |  |  |  | (no entity) | error 0 |
| G-048 | 3 | lookup |  |  |  | (no entity) | error 0 |
| G-049 | 1 | (guardrail) |  |  |  |  |  |
| G-049 | 2 | (guardrail) |  |  |  |  |  |
| G-049 | 3 | (guardrail) |  |  |  |  |  |
| G-050 | 1 | single_hop | 1 | Gene | diseases | gene_diseases_one | ok 4 |
| G-050 | 2 | multi_hop | 1 | Gene | diseases | gene_diseases_one | ok 4 |
| G-050 | 3 | multi_hop | 1 | Gene | diseases | gene_diseases_one | ok 4 |

Runs per template path:

- (guardrail refusal): 28
- (no entity): 22
- None (model path): 17
- gene_variants_one: 16
- disease_genes_one: 8
- gene_record_one: 7
- gene_diseases_many: 6
- disease_record_many: 6
- gene_diseases_one: 6
- gene_processes_one: 6
- gene_disease_link: 4
- gene_variant_diseases_one: 3
- disease_genes_many: 3
- gene_orthologs_one: 3
- gene_components_one: 3
- gene_taxon_one: 3
- gene_articles_one: 3
- disease_phenotypes_one: 3
- gene_activities_one: 3
- article_mesh_one: 2
- article_record_one: 1
- disease_record_one: 1
