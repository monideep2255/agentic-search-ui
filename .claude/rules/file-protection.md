---
description: "File protection: no deletion without asking, no unnecessary file creation, no System 1/2 code"
scope: portable
alwaysApply: true
---

## File protection

- Don't delete files or folders without explicitly informing the user first.
- Don't create new files unnecessarily -- prefer editing existing files.
- Don't add System 1/2 ETL code (bulk parsers, KGX exporters, AGE loaders) -- this repo is System 3 only.
- Don't modify files in `reference/` -- that symlink is read-only reference material.
