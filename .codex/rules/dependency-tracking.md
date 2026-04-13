## Dependency tracking

Every component file in `.codex/` (skill, agent, rule, hook) and every Python module under `system-01-data-pipelines/` and `system-02-knowledge-graph/` should make its dependencies explicit. This prevents silent breakage when files move or get deleted.

### For .codex/ components

Components with YAML frontmatter (skills, agents, rules) declare:

```yaml
---
name: my-skill
description: ...
---
```

What counts:

- `depends_on`: other skills/agents/rules this component reads or invokes, config files it consumes
- `depended_by`: index files (AGENTS.md, README.md) that list it, other components that reference it

### For Python modules

Use module docstrings to list cross-module dependencies that aren't obvious from imports:

```python
"""ClinVar variant parser.

Depends on:
    - data_pipelines.shared.utils.download_file
    - data_pipelines.shared.biolink.validate_node
    - knowledge_graph.schema.constants (BIOLINK_PREDICATES)

Reads:
    - data/ftp_cache/variant_summary.txt.gz

Writes:
    - data/kgx/clinvar/nodes.tsv
    - data/kgx/clinvar/edges.tsv
"""
```

### When to update

- Creating a new component: add both fields from the start
- Modifying a component: check if dependencies changed
- When a NEW file starts referencing an existing component, update the existing component's `depended_by`
- When deleting a component, grep for its name first and update everywhere that listed it

### Keep it honest

- Only direct dependencies (1 hop), not transitive
- Use relative paths from repo root
- Update when you notice drift, don't let it go stale
- This rule is enforced by convention, not by tooling. If you skip it, future-you will have to grep through 50 files to figure out what broke
