## System design patterns

Mental models for designing the search agent, API routes, UI components, and tool integrations in this repo.

### 1. Three-state permissions (allow / deny / ask)

When writing a rule, agent, or skill, bucket actions explicitly:

- Allow: agent does this freely (read files, run tests, query the graph read-only, start dev server)
- Deny: agent never does this (write to the knowledge graph, delete user data, expose API keys, push to main directly)
- Ask: agent pauses and confirms first (changing agent prompts, modifying cost control thresholds, adding new dependencies, changing auth config)

Don't write rules that are ambiguous about which state an action falls into.

### 2. Agent loop as the core abstraction

The search agent follows a 5-step loop: Guardrail -> Think -> Plan -> Act -> Write. Each step has one job. Design decisions should maintain this separation:

- Guardrail changes affect what reaches downstream steps. Test edge cases.
- Tool additions go in Act. Tools are typed JSON schemas with explicit error handling.
- Synthesis logic lives in Write. It consumes tool results, not raw data.
- The orchestrator routes between tiers (Guard/Plan/Synth). Model choice is a harness decision, not an agent decision.

### 3. Three-layer data access

System 3 queries data across three layers. Each has different latency, cost, and freshness characteristics:

- Layer 1 (graph): Cypher queries against the AGE graph on Hetzner. Sub-second for most queries. Data is a periodic snapshot.
- Layer 2 (on-demand API): Live NCBI E-utilities calls. 100-500ms. Always current.
- Layer 3 (enrichment): PubTator3, LitVar2, ClinicalTrials.gov. 200-800ms. Always current.

Design tool calls to specify which layer they hit. Cache Layer 2/3 responses (24h TTL for stable fields). Never mix layers in a single tool - one tool, one layer.

### 4. Cost control is safety-critical

LLM cost can spike unpredictably. The harness enforces hard caps:

- Per-query cap: kill the agent loop if total cost exceeds threshold
- Per-user daily cap: reject new queries after daily quota
- System-wide daily cap: pause accepting new queries
- Per-step timeout: abort stuck model calls

These are not optional. Every new feature must respect existing caps. Changes to cap values require explicit user approval.

### 5. Provenance is a first-class type

Every citation includes `source`, `source_id`, `source_url`, and `layer`. Functions that produce citations must take provenance as a required parameter. If you can produce a citation without provenance, the function signature is wrong.

### 6. Streaming by default

All user-facing responses stream via SSE. Design for:

- Time-to-first-token under 1 second
- Graceful handling of mid-stream errors (show partial result + error, don't blank the screen)
- Stop button that cleanly aborts the agent loop
- Citation chips emitted inline as the model references sources

### 7. Output truncation for large results

When a tool returns more data than useful for synthesis (e.g., 500+ Cypher rows, large API responses), truncate to the first N relevant results and include a count of total available. Never inline large result sets into the agent's context - it causes hallucination of the remaining data.
