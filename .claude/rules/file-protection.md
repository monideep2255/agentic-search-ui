---
description: "File protection: no deletion without asking, no unnecessary file creation, documentation repo only"
scope: portable
alwaysApply: true
depends_on: []
depended_by:
  - CLAUDE.md
  - .claude/README.md
---

## File protection

- **Don't delete files or folders without explicitly informing the user first.**
- Don't create new files unnecessarily -- prefer editing existing documentation.
- Don't add build/test commands -- this is a documentation repo, not a software project.
