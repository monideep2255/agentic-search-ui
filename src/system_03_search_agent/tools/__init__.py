"""The tool layer: one data source adapter per tool (Technical_specification.md Section 6).

Each tool is a Read-plus-one-source untrusted-source reader in the sense of
`.claude/rules/system-design-patterns.md` pattern 8: it can call its own
source and nothing else, never another tool, never a write path.

Build phase 2.1 lands the first of the seven, `cypher_query` (Section 6.1),
the only path to Layer 1.

Depends on:
    - system_03_search_agent.harness.harness (plan-tier call for Cypher generation)
    - system_03_search_agent.contracts.events (ToolCall, ToolName, Layer)

Reads:
    - Environment: GRAPH_PG_HOST, GRAPH_PG_PORT, GRAPH_PG_USER,
      GRAPH_PG_PASSWORD, GRAPH_PG_DBNAME (read-only Layer 1 access)

Writes:
    - Nothing. Layer 1 access is read-only by credential, not only by
      convention: the `kg_reader` role carries default_transaction_read_only.
"""
