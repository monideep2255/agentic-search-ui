---
description: "File protection: no deletion without asking, no unnecessary file creation, no System 1/2 code"
scope: portable
alwaysApply: true
---

## File protection

- Don't delete files or folders without explicitly informing the user first.
- Don't create new files unnecessarily -- prefer editing existing files.
- Don't add System 1/2 ETL code (bulk source-data parsers, AGE loaders, or anything that writes KGX into the graph) -- this repo is System 3 only.
- Don't modify files in `reference/` -- that symlink is read-only reference material.

### Reading KGX out of the graph is not writing KGX into it

The bullet above used to read "bulk parsers, KGX exporters, AGE loaders", which forbade the deliverable of build phase 4.4, a build phase the locked technical specification's Section 25 requires and the locked PRD names as one of six v1 delivery surfaces. Amended 2026-08-19 with product-owner approval, because the rule and the spec could not both stand as written and the distinction is worth stating rather than crossing silently.

The line, stated by direction of data flow:

- Into the graph: parsing NCBI source data, mapping it to BioLink, writing KGX files that get loaded into AGE. That is Systems 1 and 2, it stays in the data-engineering repository, and this rule still forbids it here in the same words as before.
- Out of the graph: reading a scoped subgraph from the already-built graph and serializing it for a user to download. That is a delivery surface, it reads through the existing read-only Layer 1 credential, and build phase 4.4 owns it.

Two things that do not change. A read-out path never acquires write credentials to the graph, since Layer 1 access is read-only at the connection level. And a full-graph snapshot dump is still not this repository's job: the System 1 and System 2 merge pipeline already produces one, and build phase 4.4 is scoped to a seed-and-hops subgraph, not a whole-graph export.

The test: does this code write into the graph or read out of it? Writing in is System 1 and 2. Reading out is a delivery surface.
