## System design patterns

Mental models for designing pipelines, loaders, schemas, agents, and skills in this repo. Adapted from personal-os-work for the ETL + KG context.

### 1. Three-state permissions (allow / deny / ask)

When writing a rule, agent, or skill, bucket actions explicitly:

- Allow: agent does this freely (read files, run validators, query the graph read-only)
- Deny: agent never does this (delete cached FTP downloads, drop tables, push secrets, modify files in `reference/`)
- Ask: agent pauses and confirms first (creating new data-pipelines modules, modifying DECISIONS.md, schema changes, anything that touches `data/` or `knowledge-graph/schema/`)

Don't write rules that are ambiguous about which state an action falls into.

### 2. Idempotent over destructive

Pipeline steps should be safe to re-run. If a step needs to clean up, it should snapshot first or write to a temp location and atomic-rename. Never `rm -rf` cache or output without an explicit user instruction.

### 3. Specialize by tool access, not just prompt

The strongest constraint is removing the ability, not asking the agent not to use it. When designing a new agent, ask: should this agent be able to edit files? If not, restrict its tools list. Don't just say "don't edit" in the prompt.

For this repo specifically: the docs-sync agent should not have access to `data-pipelines/` or `knowledge-graph/`. Read-only graph query agents (when they exist) should not have `Edit` or `Bash`.

### 4. Output truncation for large results

When a tool output exceeds a useful size (NCBI bulk listings, AGE query results over 1000 rows, ClinVar parses), write to disk and return a pointer (file path + line count + first N lines). Prevents silent truncation where the LLM hallucinates the rest.

For pipelines this means: write KGX TSVs to `data/kgx/<database>/`, log the row counts, and return the path. Never inline a 100k-row result in a tool response.

### 5. Provenance is a first-class type

Treat `source`, `source_url`, and evidence fields as required parameters in every node/edge constructor function. If a function can produce a node without provenance, the function signature is wrong. This is the architectural enforcement of the trust moat principle.

### 6. Validation at boundaries, trust internally

Validate at the system edges: NCBI API responses, FTP file contents, user-provided config, KGX file load. Inside the codebase, trust your own functions — don't re-validate every record at every layer. Boundary validation + good types is enough.
