---
description: "File protection: no deletion without asking, no unnecessary file creation, no System 1/2 code"
scope: portable
alwaysApply: true
---

## File protection

- Don't delete files or folders without explicitly informing the user first.
- Don't create new files unnecessarily. Prefer editing existing files.
- Don't add System 1/2 ETL code (bulk source-data parsers, AGE loaders, or anything that writes KGX into the graph). This repository is System 3 only.
- Don't modify files in `reference/`. That symlink is read-only reference material.

Reading a scoped subgraph out of the graph for a user to download is a delivery surface (build phase 4.4, read-only credential) and is allowed. Writing into the graph is not. The history of that line: `.claude/rules-reference/file-protection.md`.

The test: does this code write into the graph or read out of it? Writing in is System 1 and 2. Reading out is a delivery surface.
