"""Observability for System 3, tech spec Section 20.

Three complementary records, each owning one job, so no single outage or
retention gap in one blinds the whole picture:

- `tracing`: LangSmith per-run traces (Section 20.1). Full-fidelity replay,
  joined to everything else on `trace_id`, and the input a build phase 5.1
  eval grader re-scores offline without re-executing the run.
- `analytics`: PostHog behavioral analytics (Section 20.2). Product usage
  AGGREGATES ONLY: event names and counts. Never raw query text, never
  citation content, never account PII.
- `audit`: the append-only tool-call audit log (Section 20.3). One durable
  JSONL line per Layer 1, Layer 2 and Layer 3 access with its
  authorization, deliberately separate from LangSmith so it survives a
  LangSmith outage or a free-tier retention limit.

`config` is the single resolver for every environment value the three read.
It exists so that three separate modules cannot each invent their own
answer to "is this turned on", which is exactly how one of them ends up
enabled when the operator believes everything is off.

Depends on:
    - Nothing inside this package. `config` is a leaf, and the other three
      modules depend on it rather than on each other.

Reads:
    - Environment: LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_ENDPOINT,
      LANGCHAIN_TRACING_V2 (and the LANGCHAIN_-namespaced spellings langsmith
      itself honours), POSTHOG_API_KEY, POSTHOG_HOST, TOOL_AUDIT_LOG_PATH,
      TOOL_AUDIT_LOG_ENABLED.

Writes:
    - The audit sink named by `audit_log_path()`, default
      `logs/tool_audit.jsonl`, append-only, never mutated after write.
"""
