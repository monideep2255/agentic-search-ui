---
description: "File protection: no deletion without asking, no unnecessary file creation, no System 3 code"
scope: portable
alwaysApply: true
depends_on: []
depended_by:
  - CLAUDE.md
  - .claude/README.md
---

## File protection

- **Don't delete files or folders without explicitly informing the user first.**
- Don't create new files unnecessarily -- prefer editing existing files.
- Don't add System 3 code (FastAPI, LangGraph, UI, MCP servers) -- this repo is System 1 + System 2 only.
