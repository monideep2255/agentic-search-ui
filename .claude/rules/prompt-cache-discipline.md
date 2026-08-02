## Prompt-cache discipline

The three-tier harness (Guard, Plan, Synth) makes many model calls per query, and provider-side prompt caching is how the per-query cost cap in `system-design-patterns.md` pattern 4 stays affordable. A provider caches on an exact prefix match: system instructions, then tool schemas, then the static graph and BioLink schema, in that order. Rewrite a single byte anywhere in that prefix and the cache misses, so the whole prompt re-bills at the uncached rate. Nothing errors. The bill just climbs. This rule exists so that fact is known before the harness code is written, not discovered later in a cost dashboard.

`requirements/Technical_specification.md` Section 4 is the source of truth for this project's caching design, the prefix structure, the Redis response cache, the TTL buckets, and the cache-efficiency metrics. This rule states the discipline that design depends on; it does not restate Section 4 in full.

### The stable prefix

Per Section 4.2, the main agent's Think, Plan, and Write calls share one stable prefix, assembled in this fixed order:

- System instructions and behavioral directives, static across every query.
- Tool schemas for the seven registered tools, sorted alphabetically and fixed in code.
- The static graph and BioLink schema at the concept level (the 11 vertex labels and 14 edge predicates), not the per-query slice. The eleventh vertex label is `NamedThing`, the dangling-endpoint stub the five-database merge produces. It is a real label the live graph contains and a generator must be able to name, so it belongs in the stable prefix along with the other 10 (finding F-2.1-01, `tracker/phase_2.1.md`; recorded 2026-07-29 in `DECISIONS.md`). The locked technical specification still says "10 concept labels" and is not edited until the Step 6.2 reconciliation; do not revert this figure to 10 to match it.

Everything else, the current query, resolved entities, the session-memory tail, and the structured plan, belongs in the dynamic suffix, never the prefix.

### The three obligations

Obligation 1: the tool list, the model per tier, and every volatile token stay out of the stable prefix.

- The tool list never changes mid-session. Adding or removing a tool is a contract-version event, coordinated across a session boundary, never a live edit during a running session.
- The model per tier never switches mid-query. A tier's model is resolved once at query start and held for the query's duration.
- No timestamp, request id, session id, or other volatile token is placed in the stable prefix. Volatile values live only in the dynamic suffix.

Obligation 2: tool schemas are sorted alphabetically and fixed in code.

- The seven tool schemas (`clinicaltrials_search`, `cypher_query`, `litvar2_lookup`, `ncbi_dbsnp`, `ncbi_efetch`, `pathogen_detection`, `pubtator_annotate`) are sorted by tool name, deterministically, in code.
- Never re-order the tool array at runtime for any reason, including a heuristic like "put the most relevant tool first." A reorder changes the prefix bytes even when the tools themselves are unchanged, and reads to the provider as a cache miss exactly like a schema edit would.

Obligation 3: the few-shot pool loads once at process start from a versioned file.

- The v1 few-shot pool (the seven or eight must-pass moat questions, seeded from the evaluation playbook) lives as a versioned file in the repo, loaded once into memory at process start.
- Never read the pool from a live database on every request. The pool sits inside the stable prefix precisely because it does not change within a session, and a per-request database read defeats that: a changing prefix source, even one that happens to return the same content, is a liveness risk the caching design does not tolerate.
- A promoted competency question is appended to the pool file at the weekly review cadence and takes effect on the next deploy, never a live hot reload mid-session.

### Where new context belongs

Retrieved passages, resolved entities, session-memory tail content, and the structured plan go in the dynamic suffix, the latest turn after the stable prefix, never spliced into the system block or the tool-schema block. Only the tail after the cache breakpoint is uncached anyway, so new content placed there costs nothing extra in cache terms and leaves the prefix untouched.

### The Redis response cache is a separate layer

Section 4.1 names two distinct caches. This rule governs the prompt cache above. The Redis response cache (Section 4.3) caches Layer 2 and Layer 3 API responses before they reach the network, keyed by `l{layer}:{tool}:{endpoint}:{normalized_params_hash}:{schema_version}`. That key is computed over the normalized, final request parameters, not the raw pre-normalization input, the same principle as caching over the bytes actually used rather than what arrived. Do not confuse the two caches when reasoning about a cache-related bug: a stale API response is a Redis TTL or `schema_version` problem, a cost spike from a cache-miss-heavy session is a prompt-prefix problem.

### How to verify

A change that claims to preserve the stable prefix is proven with a byte-equality assertion (SHA-256 over the assembled prefix), computed across two requests whose dynamic suffix differs but whose stable prefix should not, not merely that the existing test suite still passes. A change that silently reorders a schema key or drops an unmodeled field passes an ordinary test suite and fails this one. Pair this check with the prompt cache hit rate metric in Section 4.4: a hand-verified prefix that still shows a dropping cache hit rate in practice means something outside the checked path is still touching the prefix.

### Three-state permissions

Allow:
- Append the current query, resolved entities, session-memory tail, and structured plan to the dynamic suffix on every request, without asking.
- Track prompt cache hit rate and Redis hit rate as first-class per-query and per-day metrics, without asking.
- Refactor the prefix-assembly code in `harness/cache.py` freely as long as the byte-equality assertion still passes.

Ask:
- Before adding any new layer in front of a model call, a request normalizer, a provenance tagger, a compressor, or a caching proxy, that could rewrite, reorder, or re-serialize the stable prefix, even when the change looks lossless.
- Before changing the tool-schema sort order or the prefix assembly order defined in `harness/cache.py`.
- Before promoting a few-shot example outside the weekly review cadence, or before switching the few-shot pool from inject-everything to retrieval-based top-k selection, since that changes what enters the stable prefix per query.

Deny:
- Never mutate the system instructions, tool schemas, or the static graph and BioLink schema between requests within a session.
- Never reorder the tool schema array or change tool list membership mid-session.
- Never switch the model assigned to a tier mid-query.
- Never place a timestamp, request id, session id, or other volatile token in the stable prefix.
- Never load the few-shot pool via a live per-request database read; it loads once at process start from the versioned file, full stop.

The test: does this change leave the stable prefix, system instructions, tool schemas, and the static graph schema, byte-identical between requests within a session, place all new content only in the dynamic suffix, and keep the tool list, the per-tier model, and the few-shot pool fixed for the duration of that session?
