# Review: after-plan thoughts

Post-plan review notes from Monideep. Items routed to appropriate docs where actionable.

1. Monideep task: do a data mapping, setting up rules by self and map it to what the pipeline code did, before loading into KG
2. Visualizations, schema of the architecture must be present
3. Documentation of the end to end process must be present -> technical walk through similar to done for ncbi-kg, also simplify for both technical and non-technical audience, use @writing rules
4. UI and everything must have BioLink validation (KGX tests for BioLink conformity and that it will work for NCATS: https://github.com/biolink/kgx/blob/master/docs/kgx_biolink_validation.md)
   - Run `kgx validate` on every KGX output after each gate
   - Checks: categories and predicates exist in official BioLink model, ID prefixes are registered, required KGX columns present, edge subjects/objects reference valid node IDs
   - Install: `pip install kgx`, then `kgx validate -i tsv data/kgx/<database>/nodes.tsv data/kgx/<database>/edges.tsv`
5. Double check that all data, meaning all, is downloaded
6. EMPTY SPACE BEFORE DBSNP? (resolved: dbSNP deferred from V1, served by System 3 API)
7. Want 1 week: build V1 of all the 3 systems. User research is critical (step 1 validation). Then try looking for ways to optimize ETL pipelines (NCBI experts) + optimize search experience (what questions) + seed golden datasets. Feedback loop development.
8. Architecture diagram must include (1) the code logic and why (2) overall high level schema (3) System 2 schema (4) rules (5) step by step process of cleaning (ETL) (6) how the ontology mapping was done
9. Make sure plan, decisions, learnings and any other relevant docs are always updated!
10. Post Gate 3 cost optimization: delete KGX files from both Hetzner and laptop after graph is validated, downgrade Hetzner from CPX42 (320GB, ~$34/month) to CPX32 (240GB, ~$24-26/month). KGX files are derived output, regeneratable by re-running pipelines. Only the AGE database needs to persist.

## Where each item landed

| Item | Routed to | Status |
| ---- | --------- | ------ |
| 1. Data mapping | bossman_execution_plan.md Phase 4 pre-load validation | added |
| 2. Visualizations | Mermaid diagrams added to all 12 docs | done |
| 3. End-to-end documentation | Extensive docs already exist across docs/ | done |
| 4. BioLink validation | bossman_execution_plan.md gate criteria + learnings.md | already covered |
| 5. Verify all data | bossman_execution_plan.md Phase 4 pre-load validation | added |
| 6. dbSNP space | Resolved: deferred from V1 | done |
| 7. V1 timeline + feedback loop | bossman_execution_plan.md post-V1 section | added |
| 8. Architecture diagrams | System_1_data_engineering_plan.md diagram checklist | added |
| 9. Keep docs updated | Enforced by docs-sync agent + /ship workflow | done |
| 10. Cost optimization | bossman_execution_plan.md post-Gate 3 steps | added |
