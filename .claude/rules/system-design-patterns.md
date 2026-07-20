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

### 8. Specialize by tool access, not just prompt

The strongest constraint on an agent is removing the ability, not asking it not to use one. A prompt instruction is a request the model can misread, drift from, or get talked out of by a crafted input. A missing tool is not available to call at all, regardless of what the prompt says or what a retrieved document tries to induce.

When designing an agent, restrict its tools list first, then write the prompt for what remains:

- The repo's read-only reviewer agents (`objective-review`, `first-principles`, `socratic`) get Read, Grep, and Glob only, never Write. They cannot modify a file even if a prompt injection in a reviewed document tried to talk them into it.
- Untrusted-source readers, any tool that ingests a Layer 3 enrichment fetch, a scraped abstract, or an NCBI record body, get Read access and the relevant API tool only, never Write and never the ability to call other tools directly (see the multi-agent pipeline gate in `production-standards`).
- Layer 1 graph access is read-only by design at the connection level, not only by instruction. The credential itself cannot write, so no prompt, injected or otherwise, can talk the agent into a graph mutation.

If an agent should never do X, the first question is whether X can be removed from its tool list, not whether the prompt says not to do X.

### 9. The description is a routing contract, not a summary

A skill or agent description is the only thing the router sees before deciding whether to load it. The body, the step list, the examples, is invisible at routing time. A description that summarizes the body instead of specifying when to trigger produces a router that either never loads the right component or loads the wrong one.

Write a description with three parts: what the component does, when to use it (literal trigger phrases the user might actually type), and a differentiator versus related components that could otherwise match.

- `eval-harness`'s description names the pass@k and pass^k metrics it owns and explicitly distinguishes itself from `dev-standards`: this is the evaluation and metrics skill, answering whether a component's output is correct and honest, not whether the code is safe to ship. Without that differentiator, a query like "is this ready" could route to either skill.
- `bossman-mode`'s description states literal trigger phrases ("bossman mode", "let's execute", "go build this") and an explicit negative trigger ("DO NOT TRIGGER during architecture/planning discussions"). The negative trigger does as much work as the positive ones: it stops the skill from loading during a planning conversation that merely mentions execution.

Never write a description as a table of contents for the body. If the description says what the skill covers instead of when to load it, the router runs on a degraded signal. It never sees the body it would need to make the same judgment call.
