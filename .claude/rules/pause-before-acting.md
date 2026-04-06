---
scope: portable
depends_on:
  - .claude/rules/
depended_by:
  - CLAUDE.md
  - .claude/README.md
---

## Pause before acting

Before executing any task, take a beat:

1. **Check rules** - does any rule in `.claude/rules/` apply to this file type, task, or context?
2. **Check clarification** - do I need to ask something before I can do this correctly?
3. **Execute** - only after 1 and 2 are clear.

Do not jump straight to reading files or calling tools. The system has rules for a reason - they only work if checked before acting.
