---
paths: ["src/system_03_search_agent/**/*.py", "services/**/*.py", ".claude/agents/**/*", ".claude/skills/*/SKILL.md", ".claude/rules/**/*", ".claude/hooks/**/*"]
---
## System design patterns

Eleven mental models for the search agent, API routes, UI components, tool integrations, and this harness's own rules, agents and skills. Read the full text before designing any of them: `.claude/rules-reference/system-design-patterns.md`.

1. Three-state permissions (allow, deny, ask)
2. Agent loop as the core abstraction
3. Three-layer data access
4. Cost control is safety-critical
5. Provenance is a first-class type
6. Streaming by default
7. Output truncation for large results
8. Specialize by tool access, not just prompt
9. The description is a routing contract, not a summary
10. Contract versioning discipline
11. The harness owns model identity
