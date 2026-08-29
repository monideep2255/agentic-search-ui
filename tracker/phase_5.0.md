# Build phase 5.0: observability

Branch: `phase/5.0-observability`
Depends on: 2.0, merged. Section 25 names 2.0 as the only dependency.
Opened: 2026-08-29
Status: OPEN, PAUSED 2026-08-29 at the product owner's request, mid-phase, BLOCKED ON ONE DECISION.
Resume by reading the "Where this stops, and what the next session does first" section below. Do not re-plan the phase; six of seven tickets are built, verified and committed.

Section 25 contains this phase as written, so unlike build phases 4.8 and 4.10 through 4.16 this is not an inserted exception. It delivers tech spec Section 20 in full: LangSmith per-run tracing (20.1), PostHog behavioral analytics (20.2), and the append-only tool-call audit log (20.3).

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [Everything measured before any change was made](#everything-measured-before-any-change-was-made)
- [The three findings that changed the design](#the-three-findings-that-changed-the-design)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [Findings](#findings)
- [History](#history)

## What this phase is for

Nothing in this system can currently be asked what it did. A query runs, emits events to whoever was listening, writes one `interactions` row, and leaves no durable per-step record. When build phase 4.12 put the product in front of a person and `GCK` resolved locally but was refused on the deployed API, the traceback could not be read at all, and that open item is still recorded in the continuation prompt as an unproven hypothesis rather than a finding. It is unproven because there was nothing to read.

Three separate records, each with one job, so no single outage blinds the whole picture:

- LangSmith holds the full-fidelity replay a build phase 5.1 eval grader re-scores offline without re-executing the run.
- PostHog holds aggregate product usage, and nothing else, ever.
- The audit log holds one durable append-only line per Layer 2 and Layer 3 access with its authorization, which is a PRD requirement (Step 1.12 decision) that must survive a LangSmith outage or a free-tier retention limit.

## Everything measured before any change was made

Measured on `phase/5.0-observability` at its branch point on 2026-08-29, following build phases 4.14 and 4.15's practice. This table is the input to the design rather than a summary of it, and three of its rows changed what the tickets say.

| What | Measured value |
|------|----------------|
| Suite at the branch point | `4158 passed, 170 skipped, 1 xfailed, 0 failed` out of 4329 collected, in 133s |
| Doc drift at the branch point | `10 facts computed, 0 stale, 0 structural` |
| Transports at phase open | all three green: `product-model`, `harness-model`, `graph` (HTTPS query service) |
| `LANGSMITH_API_KEY` | ABSENT. Empty in `.env` and `env.example`, and absent from the shell environment. No credential exists anywhere |
| `POSTHOG_API_KEY` | SET, a real 47-character `phc_`-prefixed project key, in the SHELL ENVIRONMENT rather than in `.env`. A first pass that grepped only `.env` reported this empty and was wrong |
| PostHog capture, probed live with a DELIBERATELY INVALID key | `https://us.posthog.com/i/v0/e` and `https://us.i.posthog.com/i/v0/e` BOTH returned `200 {"status":"Ok"}` |
| `LANGCHAIN_TRACING_V2` | SET to `true` in `.env`, and in `env.example:107` |
| `LANGSMITH_PROJECT` | SET to `agentic-search-ui` |
| Installed langsmith | `0.10.10`, a declared direct dependency at `requirements.txt:11`, absent from `pyproject.toml` |
| Installed langgraph / langchain-core | `1.2.9` / `1.5.1` |
| `posthog` the package | installed NOWHERE: absent from `pyproject.toml`, `requirements.txt` and `frontend/package.json` |
| Existing PostHog integration code | ZERO lines. The env var names are reserved in Section 24 and nothing reads them |
| Existing audit log | ZERO lines. No `logs/` directory, no file logging, no settings module anywhere in the repository |
| `logs/` in `.gitignore` | ABSENT. Writing Section 20.3's `logs/tool_audit.jsonl` today would commit it |
| Tools with a production call site | TWO of seven: `cypher_query` and `ncbi_efetch` |
| Call sites that bypass `act_node` | FIVE, listed below |
| Per-tool latency | tracked NOWHERE. The only latency in the codebase is whole-query `elapsed_ms` in `core/run.py` |
| Numeric HTTP status in a tool output | DISCARDED. Classified to `ok|empty|error` inside the action modules before the tool returns |

## The three findings that changed the design

### One: hooking `act_node` is the enumeration fix, and it misses five sites on day one

The obvious implementation of an audit log is a hook in `act_node`, where `tool_start` and `tool_result` already fire. It is wrong, and it is wrong in the exact shape `.claude/rules/bossman-mode.md` Rule 2 forbids: a defense that lists instances rather than naming the class.

Five production call sites reach a data layer without passing through `act_node`:

| Site | What runs | What it bypasses |
|---|---|---|
| `core/graph.py:2038` | `ncbi_efetch`, `action=dataset_report` | `act_node` entirely. Inside `_resolve_symbol_to_curie_uncached`, called from `think_node` |
| `core/graph.py:2098` | `ncbi_efetch`, `action=search`, db=gene | same |
| `core/graph.py:2139` | `ncbi_efetch`, `action=summary`, db=gene | same |
| `export/traversal.py:558` | `graph_connection.execute_cypher` directly | `act_node` AND the `cypher_query` tool wrapper. KGX export's seed lookup |
| `export/traversal.py:801` | same | same. KGX export's hop traversal, the bulk of `s3-kgx-export`'s graph reads |

An `act_node` hook would log zero lines for all five while passing every acceptance criterion written against it, which is build phase 4.4's stated-blind-spot failure and build phase 4.6's manufactured-requirement failure arriving together.

The category fix is to hook the transport, not the caller. Verified directly rather than assumed: every Layer 2 and Layer 3 tool module imports `tools/ncbi_transport.py`, so there are exactly three chokepoints below every one of the seven tools and below all five bypasses.

| Chokepoint | Covers |
|---|---|
| `tools/ncbi_transport.py`, `execute_get` (line 1134) | every Layer 2 and Layer 3 HTTPS call, from all seven tools and from the three `think_node` bypasses |
| `tools/graph_connection.py`, `execute_cypher` (line 420) | every Layer 1 read, from `cypher_query` and from both KGX export bypasses |
| `tools/pathogen_ftp_transport.py` | the Pathogen Detection bulk FTP path, which is not an HTTPS call and would be missed by the other two |

### Two: the transport is the only place Section 20.3's required fields actually exist

This is the argument that makes the chokepoint design correct rather than merely convenient, and it was found by asking what each field costs at each site rather than by preference.

Section 20.3 requires HTTP status and latency in milliseconds on every line. At `act_node`, neither is reachable. The numeric `response.status_code` is real, but it lives inside `ncbi_eutils_actions.py`, `ncbi_datasets_actions.py`, `ncbi_pubchem_actions.py` and `ncbi_coordinate_overlap.py`, where it is classified into a three-value `status: ok|empty|error` plus a capped message, and the number is discarded before the tool returns. Latency is computed nowhere per call. Threading both up through the action modules to satisfy an `act_node` hook would be a wide change to four modules and seven tool outputs, in service of a hook that still misses five call sites.

At the transport, both are free. `execute_get` holds the `httpx.Response` and can bracket its own await.

`trace_id` is the exact inverse: a local at `act_node`, absent at the transport, where `execute_get(url, params, ...)` has no run scope. A `contextvars.ContextVar` set once per run carries it down without changing seven tool signatures, and it covers the five bypass sites for free. Where no run is in scope, as in `s3-kgx-export`, the field records null against a source marker rather than a fabricated id, which is the honest reading and is asserted by an arm.

### Three: tracing is already switched on, and only a hardcoded override is holding it back

`LANGCHAIN_TRACING_V2=true` is set in `.env` and in `env.example:107`. Verified against the installed langsmith 0.10.10 source rather than its documentation: `utils.py:121-139` resolves tracing through `get_env_var("TRACING_V2")` across both the `LANGSMITH_` and `LANGCHAIN_` namespaces, so that spelling is honoured. The only thing suppressing tracing today is `tracing_context(enabled=False)`, hardcoded at `core/run.py:478-480` around the `ainvoke` call and at `core/run.py:615-618` around the whole `astream` loop.

So the naive reading of this phase's title, delete the override, is a live PII breach the moment a key is present. LangGraph's tracing integration captures node inputs and outputs automatically through LangChain's callback system, independent of anything in this repository, and the object it captures is `GraphState`, which carries `Query.owner_id` (`contracts/query.py:216`) and `Query.user_id` (`contracts/query.py:199`) plus `RequestContext.session_memory`. Section 20.1's PII rule is explicit that user-account PII never leaves the auth service boundary and is never attached to a trace.

Redaction is therefore part of the deliverable, not a follow-up. The mechanism was probed live rather than read from documentation: `langsmith.Client` accepts `hide_inputs`, `hide_outputs`, `hide_metadata` and `anonymizer`, each taking a bool or a `Callable[[dict], dict]`.

Both call sites change together. `core/run.py:548-549` and `:570` state that `run_streaming()`, not `run()`, is the entry point a real SSE surface uses and the one real users reach, so wiring only `run()` would leave production traffic untraced while looking done.

## Where this stops, and what the next session does first

PAUSED 2026-08-29 by the product owner, ahead of a session limit. The branch is `phase/5.0-observability`, the working tree is CLEAN and 11 commits are pushed. Nothing is held in a running agent's context.

THE ONE THING BLOCKING THIS PHASE IS A DECISION, NOT WORK: F-5.0-13, escalated under Rule 4 because half of it sits inside this phase's own F-5.0-08 fix. The product owner had not answered when the session paused, so nothing about it has been touched. Read its Findings row, then take one of:

- Option A, the lead's recommendation: fix both halves category-first. Redact the `error` field the way `params` already is, and make the value scanner find a credential ANYWHERE in a string rather than only when the whole string is a URL. One fix agent, then one re-verify round by a FRESH agent, never by whoever wrote the fix.
- Option B: redact `error` only, and carry the embedded-URL gap as latent with a named owner.
- Option C: revert the F-5.0-08 fix and re-decompose the redaction model. Heaviest, and only if value-scanning strings is judged the wrong model.

WHAT IS DONE, all committed and independently verified by the lead rather than accepted on a builder's report:

| Ticket | State |
|---|---|
| T-5.0-01 config resolver | done, 18 arms, 4 mutations proven red |
| T-5.0-02 audit log | done, F-5.0-08 fixed and re-verified on the real path with a positive control |
| T-5.0-03 tracing | done, F-5.0-03 and F-5.0-09 fixed, PII proven absent by reading data back OUT of LangSmith |
| T-5.0-04 analytics | done, built and wired, sends NOTHING pending F-5.0-12 |
| T-5.0-05 wiring | done, both `run.py` sites, three transport chokepoints, live-verified |
| T-5.0-06 gitignore and env | done, `.env` and `env.example` synced at 40 keys each |
| T-5.0-07 premise gate and mutation harness | done, 9 arms and 6 mutation cases, both real bypass callers driven |

Measured at the pause: `4259 passed, 171 skipped, 1 xfailed, 0 failed`; `ruff check` clean over the WHOLE repository, no path argument; observability directory `101 passed, 1 skipped`.

WHAT REMAINS AFTER THE DECISION, in order: the fix and a fresh-agent re-verify, then the judge round, then the adversary round (its target here is the PII boundary and the no-credential path, not cite-or-refuse, since this phase generates no answers), then the stage-10 gates, then `/phase-checkpoint` and `/ship`.

TWO THINGS THE NEXT SESSION MUST NOT REDISCOVER:

- Doc drift is KNOWN and deliberately deferred: `CLAUDE.md`, `AGENTS.md` and this phase's continuation prompt still cite 4329 Python tests against a computed 4416 at the time it was checked, and the figure moved again after the gate landed. It is `/phase-checkpoint`'s job at phase close, not a defect.
- `eval-harness` does NOT apply to this phase. Nothing here touches answer generation, grounding or citations.

## Goal contract

Written before the first change, per `.claude/rules/goal-contracts.md`.

Done when:

- Every Layer 1, Layer 2 and Layer 3 access from any of the three chokepoints writes exactly one append-only JSONL line carrying every Section 20.3 field, including the five call sites that bypass `act_node`.
- Enabling tracing attaches `trace_id` as the join key and provably transmits no `owner_id`, `user_id` or session-memory content.
- A PostHog event is emitted for each product signal this repository can honestly produce today, carrying event name, count-shaped properties and no raw query text or citation content.
- With no credential configured, tracing and analytics are OFF and make provably zero outbound calls, asserted by an arm that fails if a call is attempted.
- The audit log is gitignored.

Verify surface, immutable for the run:

- A premise gate whose arms are each proven red by a mutation, added in the same edit as the arm per build phase 4.15's rule.
- One arm per bypass call site, asserting a line is written. The gate must be able to distinguish a written line from nothing having happened (the populate-check, build phase 4.11).
- A no-credential arm that asserts zero outbound calls, not merely that no exception was raised.
- A PII arm that inspects the actual assembled trace payload for `owner_id` and `user_id`, not a proxy for it.
- The full Python suite against the re-measured `4158 passed, 0 failed` baseline.
- `ruff check` over the WHOLE repository with no path argument, per build phase 4.15's CI finding.
- `python tracker/check_doc_drift.py --check` at 0 stale, 0 structural.

Constraints:

- No new Python dependency. PostHog ships as an httpx POST against a documented wire contract, since `httpx` is already a dependency and `.claude/rules/supply-chain-security.md` requires a review before any new package.
- Every outbound call carries a declared timeout, per `.claude/rules/tool-call-budgets.md`.
- Observability is best-effort and never blocks or fails a user's query, following `feedback/writer.py`'s existing discipline.
- No secret in any log line, trace, event or audit record.
- Locked documents are not edited. Where Section 20.1 and Section 13.1 contradict each other on who mints `trace_id`, the shipped code wins and the contradiction is recorded, per LEARNINGS.md's build phase 4.6 entry.

Blocked-stop:

- The two halves are NOT symmetric, corrected after a first measurement that grepped only `.env` and got PostHog wrong. A real PostHog project key IS present in the shell environment, so the analytics half can reach the live service. No `LANGSMITH_API_KEY` exists anywhere, so the tracing half cannot be verified live at all, by anyone, until the product owner provisions one.
- Reaching the live PostHog service is NOT the same as verifying it, per F-5.0-05: capture returns an identical 200 for an invented key, so a live call confirms only reachability. Ingestion cannot be confirmed with a project key at all, since reading events back needs a separate personal API key that nobody has asked for. Every substantive arm therefore runs against a local stub, and the live call is recorded as reachability and labelled as such.

## Tickets

Dispatch shape, per `.claude/rules/plan-then-fan-out.md` and bossman-mode Rule 1. `core/run.py` is a shared seam for tracing, analytics and the contextvar set, so it is NOT split across builders. Wave 1 builds pure modules with no call-site wiring, in parallel on disjoint files. Wave 2 is a single serial builder holding every integration point at once.

| Ticket | Wave | Deliverable | Files it may touch | Status |
|---|---|---|---|---|
| T-5.0-01 | 0, lead | `observability/config.py` and `__init__.py`: one resolver for every `LANGSMITH_*` and `POSTHOG_*` value and the audit path. No key means off, everywhere, by construction | `src/system_03_search_agent/observability/config.py`, `__init__.py` | todo |
| T-5.0-02 | 1 | `observability/audit.py`: the append-only JSONL writer, the `trace_id` contextvar, the params redactor, one writer per process, never mutating a written line | `src/system_03_search_agent/observability/audit.py` | todo |
| T-5.0-03 | 1 | `observability/tracing.py`: the configured tracing context and the `RunnableConfig` builder, with a redaction client that strips `owner_id`, `user_id` and session memory | `src/system_03_search_agent/observability/tracing.py` | todo |
| T-5.0-04 | 1 | `observability/analytics.py`: the PostHog client over httpx with a declared timeout, and the aggregate-only event catalogue | `src/system_03_search_agent/observability/analytics.py` | todo |
| T-5.0-05 | 2, serial | Every integration point, held by ONE builder: both `core/run.py` tracing sites, the contextvar set, the analytics epilogue, the three transport hooks, the feedback endpoint event | `core/run.py`, `tools/ncbi_transport.py`, `tools/graph_connection.py`, `tools/pathogen_ftp_transport.py`, `adapters/web_sse/app.py` | done |
| T-5.0-06 | 3 | `.gitignore` the audit log, update `env.example`, and document the three records | `.gitignore`, `env.example`, `docs/build/` | todo |
| T-5.0-07 | 3 | The premise gate and its mutation harness, one mutation case added in the same edit as each arm | `tests/system_03_search_agent/observability/` | todo |

## Coverage: what this phase does not cover

Stated here rather than discovered later, per `.claude/rules/goal-contracts.md`'s rule that a verify surface must state its own coverage. Build phase 4.4's premise gate passed 6 of 6 while the default path it never exercised returned a wrong answer, and its coverage statement had named that omission from day one.

- NOTHING IS VERIFIED AGAINST LIVE LANGSMITH. No `LANGSMITH_API_KEY` exists anywhere, so every tracing arm proves the wiring against a local stub or an injected fake. A green gate there means the payload this system WOULD send is correct, and says nothing about whether LangSmith accepts it.
- POSTHOG IS REACHABLE BUT STILL NOT VERIFIABLE, which is a sharper statement than it sounds and is the reason F-5.0-05 exists. A real project key is present, so a live call can be made, and it will return `200 {"status":"Ok"}`. So will a call carrying a key that was invented on the spot, measured. Capture is fire-and-forget by design and reports success for anything shape-valid, and reading an event back to confirm ingestion needs a personal API key that is a different credential nobody has. So the live call proves REACHABILITY and nothing downstream of it, and no arm in this phase may claim otherwise.
- FIVE OF THE SEVEN TOOLS HAVE NO PRODUCTION CALL SITE. `ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `pathogen_detection` and `clinicaltrials_search` are reachable only from their own tests, because `plan_node`'s planned-call union has just two members. The transport hook covers them by construction, and that coverage is exercised by test-driven calls rather than by production traffic. An audit log with zero lines for five tools is a fact about `plan_node`, not about this hook.
- THE FTP CHOKEPOINT IS THE LEAST EXERCISED. `pathogen_detection` has no production caller, so its transport hook is proven only by direct test invocation.
- THREE OF SECTION 20.2'S SIX NAMED EVENTS CANNOT BE PRODUCED HONESTLY TODAY. Saved-query creation has a model at `data/models.py:311` and zero endpoint across all eight routes in `app.py`. The follow-up funnel has its join keys (`session_id`, and `askSeq` client-side) and no funnel logic anywhere. Session length is derivable retrospectively from `interactions.created_at` grouped by `session_id`, and no live session-start or session-end event exists. These three are recorded as not built rather than emitted as approximations.
- NUMERIC HTTP STATUS IS CAPTURED AT THE TRANSPORT ONLY. A tool output still carries the classified three-value status, unchanged by this phase. The audit line and the tool output therefore describe the same call at different resolutions, deliberately.
- THE ADVERSARY'S USUAL TARGET IS ABSENT. This phase generates no answers, so cite-or-refuse is untouched and `eval-harness` does not apply. The adversary's target here is the PII boundary and the no-credential path.

### Coverage for T-5.0-05's wiring tests (test_wiring.py), run 2026-08-29

`tests/system_03_search_agent/observability/test_wiring.py` proves the SEAM T-5.0-05 built, not the four modules it wires (each already has its own test file and its own coverage statement above). Stated separately, per the same rule, because this file's gap is a different shape from theirs.

- THE BYPASS ARMS DO NOT INVOKE THE REAL BYPASS CALLERS. `TestBypassArms` calls `graph_connection.execute_cypher` and `ncbi_transport.execute_get` directly, with the same call shape `export/traversal.py:558`/`:801` and `core/graph.py`'s `_resolve_symbol_to_curie_uncached` use, but does not stand up either module's own dependency graph. This is sufficient to prove the chokepoint design's central claim (the same function is reached regardless of caller, because there is only one function to reach), since both real callers import and call the identical `execute_cypher`/`execute_get` names this file calls directly. It does NOT prove those two real callers still pass the correct arguments into that shared call today; `export/test_kgx_traversal.py` and `core/test_graph.py` own that, and neither of those files was touched by this ticket, so neither was re-verified against the now-audited transport as part of this change.
- MUTATION-PROVEN FOR THE TWO PRIMARY CHOKEPOINTS ONLY. Every arm depending on `ncbi_transport.execute_get` or `graph_connection.execute_cypher` was hand-mutated (the `record_tool_call(...)` call site replaced with a no-op) and confirmed to turn red, then the source file was restored and confirmed byte-identical by `diff`. The `TestNoLangsmithKeyMeansZeroTraceThroughRun` arm's populate-check (the `config.tracing_enabled` call-counting spy) was mutation-proven the same way, against `core/run.py`'s own `traced_graph_run` call site, and incidentally reproduced this repository's original F-5.0-03 shape live: with the wrap removed, LangGraph's ambient LangSmith tracer attempted a genuine outbound HTTPS call, caught by `tests/conftest.py`'s hermetic-suite guard rather than by this file's own assertion. `TestPathogenChokepoint` and `TestCredentialNeverLeaksThroughTheTransport` were NOT separately hand-mutated; they share the identical file-existence populate-check shape as the two proven classes, and are recorded as unproven-by-mutation rather than assumed equivalent.
- `AnalyticsEvent.QUERY_COMPLETED`'s wiring in `core/run.py`'s epilogue has NO dedicated arm in this file. It is exercised incidentally by `TestNoLangsmithKeyMeansZeroTraceThroughRun`'s full `run()` invocation (with `audit_enabled()` forced off so no audit file is written) but that arm asserts nothing about the analytics call itself; `POSTHOG_API_KEY` is not set in that fixture stack either, so `capture_event` is a no-op the whole way through and no assertion would have caught a broken property mapping. `AnalyticsEvent.FEEDBACK_SUBMITTED`'s wiring is covered by `tests/system_03_search_agent/adapters/web_sse/test_feedback_endpoint.py`, not by this file.
- THE PATHOGEN CHOKEPOINT REMAINS THE LEAST EXERCISED, unchanged from the phase-level coverage statement above: `_get_directory_listing`'s own audit hook has no test in this file at all, only `stream_filtered_tsv_rows`'s does.

### Mutation evidence for T-5.0-01, run 2026-08-29

Four mutations, each restoring `config.py` byte-identical afterwards and confirmed by `diff`. Recorded here so T-5.0-07 inherits a proven starting set rather than re-deriving one, per build phase 4.15's rule that the mutation case is added in the same edit as the arm.

| Mutation applied to `config.py` | Suite result |
|---|---|
| `tracing_enabled()` returns `tracing_flag_set()` alone, dropping the key requirement. This IS the naive implementation of this phase | 1 failed, 17 passed |
| `_first_set` returns a present-but-empty value instead of treating it as absent | 4 failed, 14 passed |
| `_is_truthy` accepts `1`, `yes` and `on`, diverging from the installed langsmith's narrow rule | 3 failed, 15 passed |
| `audit_enabled()` returns False for any value of the env var | 1 failed, 17 passed |

Unmutated: `18 passed in 0.02s`.

### F-5.0-08 reproduction, run 2026-08-29

Constructed rather than reasoned, per this repository's standard that a claimed defect needs an input that makes the assertion fail. The stand-in credential is generated with `uuid.uuid4().hex` at runtime rather than typed, since a secret-shaped literal in a command is blocked by `.claude/hooks/scan-secrets.sh`. That hook fired correctly twice while this finding was being recorded, which is worth noting as the security layer working rather than as friction.

| Input shape | Result |
|---|---|
| The credential as a dict value under a key literally named for it | redacted. The key-name rule works as designed |
| The identical credential as an E-utilities query parameter inside a URL, held under a key named `endpoint` | LEAKED verbatim |

The two differ only in where the same secret sits, which is the whole finding. `_append_api_key` puts it in the query string, so the second shape is the one the transport actually produces and the first is the one the redactor was written against.

### Live end-to-end verification, run 2026-08-29

The product owner provisioned both credentials mid-phase, which turned the tracing half from "provable against a stub" into "seen working". Everything below is measured against the real services rather than a fake, and the PostHog half is deliberately absent for the reason F-5.0-12 gives.

What one live query produced, `trace_id` `live-verify-8ae70ae8`:

| Audit line | Layer | Endpoint | HTTP |
|---|---|---|---|
| `ncbi_transport:datasets` | 2 | `api.ncbi.nlm.nih.gov/datasets/v2/gene/symbol/BRCA1/taxon/human` | 200 |
| `cypher_query` | 1 | `ncbi_kg` | none, this path carries no HTTP status |
| `ncbi_transport:datasets` | 2 | `api.ncbi.nlm.nih.gov/datasets/v2/gene/id/672` | 200 |

THE FIRST ROW IS THE PHASE'S CENTRAL CLAIM PROVING ITSELF ON REAL TRAFFIC, not in a test. `gene/symbol/BRCA1/taxon/human` is `think_node`'s symbol resolution (`core/graph.py:2038`), one of the five call sites that never reach `act_node`. An `act_node` hook would have written nothing for it while passing every criterion written against it. All three lines carry one `trace_id`, and both layers appear.

F-5.0-08 on the real path, with a positive control, which is the half that makes it evidence rather than decoration:

| Check | Result |
|---|---|
| The credential really was in the request URL (`_append_api_key` applied) | true, asserted before the negative check |
| Credential present in the audit log | false |
| Any `api_key` fragment in the audit log | false |

F-5.0-03 read back OUT of LangSmith, on a second query carrying generated identity values, `trace_id` `pii-check-b958f3ec`, 9 spans and 190,335 characters of stored payload:

| Field | Leaked to LangSmith |
|---|---|
| `owner_id` | NO |
| `user_id` | NO |
| `session_id` | NO |

with `trace_id` present as the join key, the question text present (Section 20.1 permits it), and 30 `[redacted]` markers in the stored payload. The marker count is the populate-check: it distinguishes "redaction fired" from "those fields were never in the payload to begin with", which is the difference between an arm and a decoration.

### Coverage for T-5.0-07's premise gate and mutation harness, run 2026-08-29

Two new files, `tests/system_03_search_agent/observability/test_observability_premise.py`
and `tests/system_03_search_agent/observability/test_observability_mutation.py`. Full
coverage statements live in each file's own module docstring, per
`.claude/rules/goal-contracts.md`'s rule that a verify surface must state its
own coverage; summarized here rather than restated in full.

The premise gate closes `test_wiring.py`'s own stated central gap: its
bypass arms call `graph_connection.execute_cypher` and `ncbi_transport.
execute_get` directly, proving the chokepoint is reached by a call SHAPED
like the two real bypass callers, not that the real callers themselves
still reach it. `TestRealBypassCallersAreAudited` calls `core.graph.
_resolve_symbol_to_curie_uncached("BRCA1", "human")` and `export.
traversal.traverse_subgraph(["MONDO:0007254"], hops=0, ...)` directly,
unmodified, faking only the one genuine external boundary each has. The
symbol-resolution arm reproduces this phase's own live evidence verbatim:
`api.ncbi.nlm.nih.gov/datasets/v2/gene/symbol/BRCA1/taxon/human` as the
recorded endpoint, the same line a real production run wrote first.

Six further arms: zero outbound tracing attempts with no `LANGSMITH_API_KEY`
(against a call-counting spy, with a populate-check proving `tracing_
enabled()` was genuinely consulted); every Section 20.3 field present,
checked against the spec's OWN text (both governing bullets, since
`authorization` is named in the first bullet and not the second's
enumerated list) rather than against the code's own docstring; an NCBI API
key confirmed present in the outbound request (positive control) and
confirmed absent from the audit line, with `authorization` recording
`"ncbi_api_key"` by identifier; `trace_id` present in scope and null out of
scope; and append-only, proven as byte-identical first-line bytes after a
second real call. One live, opt-in arm reads `Client.info` (read-only)
against the real LangSmith service, gated behind `RUN_PREMISE_GATE=1` AND a
real `LANGSMITH_API_KEY`; it ran and passed during this work. No arm
anywhere in either file reaches PostHog, gated or not: F-5.0-12 stands, and
the provisioned key is the wrong credential for that job.

Stated gaps: the KGX bypass arm proves the audit hook fires from the real
caller, not that `MONDO:0007254` resolves (the fake connection returns no
rows for any candidate label, so it never does); `export/test_kgx_
traversal.py` owns seed-resolution correctness. `ncbi_dbsnp`, `pubtator_
annotate`, `litvar2_lookup`, `pathogen_detection` and `clinicaltrials_
search` still have no production caller for a "real bypass caller" arm to
drive, unchanged from the phase-level coverage statement above.

The mutation harness covers six mutations, monkeypatch-based rather than
file-text-edit-based (the file's own docstring states why: `audit.py`
imports `audit_enabled`/`audit_log_path` by name from `config.py`, so
reloading `config.py` alone would not propagate, and reloading `audit.py`
too would reset its module-level lock for the whole session). Each of the
six runs its target arm unmutated first (must be green, the control half
`test_release_environments_mutation.py` calls not optional) and mutated
second (must be red), then asserts the mutated attribute is restored to
the exact original object by identity. Two of the six close gaps
`test_wiring.py`'s own coverage statement named as unproven-by-mutation
(`TestCredentialNeverLeaksThroughTheTransport`, via `ncbi_transport.
_endpoint_for_audit`) without editing that file; a third proves the F-5.0-07
hermetic-guard regression without ever writing to `tests/conftest.py`,
by mutating `requests.adapters.HTTPAdapter.send` one layer below the
session-scoped fixture instead. Verified stable across three consecutive
random-ordered runs of the observability directory (`101 passed, 1
skipped` each time) and once under `-p no:randomly`, so no state leak
between the mutation harness and the rest of the suite in this directory.
No completeness claim is made beyond the six named mutations, per build
phase 4.15's rule that the fix for a false completeness claim is deletion,
not a better sentence.

## Findings

Filed the moment they are established, per `.claude/rules/self-eval-loop.md`'s write-first rule and PR #70.

| ID | Severity | Summary | Raised by | State | Reason |
|---|---|---|---|---|---|
| F-5.0-01 | major | `logs/` is absent from `.gitignore`, so Section 20.3's `logs/tool_audit.jsonl` would be committed to git, carrying tool params and returned record ids into the repository's history | lead, at phase open | FIXED | `logs/` added at `.gitignore:112`. Proven rather than asserted: `git check-ignore -v` reports the rule that matches, `git status` does not see the file, and a `git add -A` dry run stages nothing from it. Closed by T-5.0-06 |
| F-5.0-02 | major | An `act_node` audit hook, the obvious implementation, structurally misses five production call sites: three `ncbi_efetch` calls in `think_node` and two `execute_cypher` calls in KGX export | lead, from research | open | Design changed to the three transport chokepoints before any builder was dispatched. Owned by T-5.0-02 and T-5.0-05 |
| F-5.0-03 | critical | Removing the hardcoded `tracing_context(enabled=False)` without adding redaction would transmit `Query.owner_id`, `Query.user_id` and `RequestContext.session_memory` to LangSmith, because `LANGCHAIN_TRACING_V2=true` is already set and LangGraph traces `GraphState` automatically | lead, from research | open | Not yet reachable: no `LANGSMITH_API_KEY` exists, so nothing is transmitted today. It becomes reachable the moment a key is provisioned, which makes it a blocker on this phase rather than on a later one. Owned by T-5.0-03 |
| F-5.0-05 | major | A 200 `{"status":"Ok"}` from PostHog's capture endpoint proves NOTHING. Measured directly: an invented key, `phc_thisisnotarealkey_probe_only`, returns byte-identical success to what a real key returns, on both hosts | lead, probed live at phase open | open | Shapes the gate rather than the code. Any arm asserting "PostHog accepted the event" is vacuous by construction and would pass against a garbage key, a garbage project and a garbage event name. Owned by T-5.0-07 |
| F-5.0-06 | minor | `POSTHOG_HOST` is `https://us.posthog.com` in `.env` and `env.example:109`, while PostHog documents `https://us.i.posthog.com` as the ingest host. Probed: both accept `/i/v0/e`, so this is a divergence from the documented endpoint rather than a break | lead, probed live at phase open | FIXED in the documented surfaces | `env.example` and `config.posthog_host()`'s default now carry the `.i.` ingest host, with the EU host named alongside it. The live `.env` on this machine is NOT edited, since it is an untracked secrets file the product owner owns. Closed by T-5.0-06 |
| F-5.0-09 | major | The tracing redactor's structural default-deny FAILS OPEN. `tracing.py:146` recognizes a Query-shaped dict with `key_set.issubset(_QUERY_FIELDS)`, so a payload carrying ONE key the model does not declare is not recognized, the safe-field allowlist never applies, and the whole structural rule disengages. Measured: with the exact model shape `session_id` is `[redacted]`; add one unrelated key and `session_id` ships in cleartext alongside the unexpected field | lead, verifying the T-5.0-03 builder's own stated property | fixed | Fixed by an independent fix agent per the maker-cannot-check rule (not T-5.0-03's own author). `_allowlist_for` now recognizes through `_looks_like_model`, which fires on EITHER a pure subset (unchanged, handles a minimal partial view) OR two or more of a model's declared field names co-occurring in the dict regardless of what else it carries, so an extra undeclared key no longer disengages recognition, it is instead itself default-denied once recognition fires. HALF THE BUILDER'S ORIGINAL CLAIM STAYS TRUE: a field added to the model is still caught by default, since `_QUERY_FIELDS` still reads `model_fields` at import. A residual gap is named in `_looks_like_model`'s own docstring rather than hidden: a dict carrying exactly ONE model field plus only undeclared keys defeats co-occurrence, which matters only for `Query.session_id`, the one SAFE-allowlist-excluded field with no category coverage; closed by adding `sessionid` to `_PII_KEY_CATEGORIES` as a second, independent layer, the same defense-in-depth shape F-5.0-08's fix used. Four new tests added to `tests/system_03_search_agent/observability/test_tracing.py` (14 total, up from 10): the exact Query-plus-extra-key and RequestContext-plus-extra-key reproductions, a generalized "every non-safe Query field is denied" test walking the live `model_fields`, and an over-recognition guard asserting a tool-result-shaped dict (rows, citations) is left untouched. Mutation-proven: reverting `_looks_like_model` to the bare `issubset` test turned exactly the two new extra-key arms red (`billing_address` and `unexpected_field_not_on_request_context` surviving unredacted), the other 12 tests stayed green, and the file was restored byte-identical afterward (`diff` clean). `pytest` `14 passed`, `ruff check` clean on both files |
| F-5.0-10 | major | `.env` on this machine was missing `ANON_DAILY_RUN_CAP`, which `cost_control` reads through `_read_int_env`, a function that RAISES when the value is unset. The guest-allowance path therefore failed with `RuntimeError: ANON_DAILY_RUN_CAP is not set` rather than degrading. Ten keys in total were present in `env.example` and absent from `.env`, and one, `BUILD_OPENROUTER_API_KEY`, was present in `.env` and undocumented in `env.example` | lead, while syncing the two files at the product owner's request | FIXED | The same class build phase 4.14 found from the other side, when CI proved about thirty environment values the suite needs that a clean machine lacks: `env.example` is only a provisioning contract if something actually compares the two. Fixed by bringing both to an identical 40-key set, verified by diffing the key names in both directions. Values deliberately DIFFER where the machine differs: `RUN_MIGRATIONS_ON_STARTUP` is `false` locally against the example's documented `true`, since it gates `alembic upgrade head` in `railway.json` and a local process should not silently migrate a developer's database |
| F-5.0-11 | minor | `test_tiers.py`'s pattern-11 scan (`_MODEL_ID_SHAPE`, `^[\\w.-]+/[\\w.-]+$`) flags any string constant shaped `a/b`, which every POSIX path and every IANA media type matches. This phase's `logs/tool_audit.jsonl` default became its THIRD false positive: build phase 2.2 hit it once (LEARNINGS.md, 2026-08-03) and F-4.2-09 hit it again for media types, which is when `_EXEMPT_MEDIA_TYPE_LITERALS` was added | lead, from a full-suite run after wave 1 | open | NOT fixed by weakening the guard, and NOT fixed by a third exemption, which would be the enumerated defense Rule 2 rejects with an obvious fourth case coming. The subject was made unambiguous instead, per `goal-contracts.md`'s third case: build the path from segments, change neither definition, and `audit_log_path()` returns a byte-identical value. Recorded because the guard's mechanism will keep producing these and the decision about its breadth belongs to whoever owns pattern 11, not to a phase that happened to trip it. A likely precision fix, offered rather than applied: ignore any candidate whose right-hand segment carries a file extension, or match against a known provider-name set |
| F-5.0-12 | major | The provisioned `POSTHOG_API_KEY` is a PERSONAL API key (`phx_` prefix, 52 chars), not a project token. PostHog's own documentation is explicit that a `phx_` key "should NOT be public as it enables reading and writing potentially private data" and grants "the same access as if you were logged into your PostHog instance", while capture wants the `phc_` project token, which is designed to be public and carries no access to private data. A third type, `phs_`, exists for server-to-server use | lead, on inspecting the newly provisioned credential | open, NEEDS THE PRODUCT OWNER | Two separate problems. WRONG KEY FOR THE JOB: `/i/v0/e` authenticates on the project token in the request body, so a personal key is not what that endpoint is built to take. LEAST PRIVILEGE, which is the one that matters: `ai-security-standards.md` forbids wiring a new integration to a full-access credential when a scoped one will do, and this is an account-wide read-write credential being handed to a fire-and-forget analytics writer that only ever needs to append events. NO EVENT HAS BEEN SENT WITH IT and none will be until the product owner replaces it: the earlier key in the shell environment was correctly `phc_`, so the right credential exists and this looks like the wrong one being copied |
| F-5.0-13 | major, RULE 4 | TWO gaps that compose into a credential path onto the append-only audit sink. ONE: `record_tool_call` writes `"error": error` RAW. `params` goes through `redact_params` plus `_bounded`; the error string goes through nothing. TWO, AND THIS SITS INSIDE THE F-5.0-08 FIX: the value-level scanner only redacts a string that IS a URL or DSN, not one that CONTAINS one. Measured, same generated credential in both shapes: as a bare value it is redacted, embedded in `connection failed: postgresql://kg_reader:...@host/db` or `HTTP 500 calling https://...api_key=... after 3 retries` it LEAKS. An exception message is precisely where a URL appears inside prose | lead, reviewing the T-5.0-05 wiring diff | open, ESCALATED | `execute_cypher`'s new audit wrapper catches bare `Exception` and passes `str(exc)` into the sink. Today's psycopg2 path happens to be clean, because `_classify_connect_error` redacts the password when it BUILDS the GraphError, but that is a PROVENANCE argument, not a value check: it holds only while every upstream exception is pre-redacted, and `except Exception` is bounded by nothing. Build phase 4.3 shipped that exact shape as a critical TWICE, three rounds apart, and the durable lesson recorded there was check the value, not where it came from. RULE 4 APPLIES to gap two, which is why this is escalated rather than fixed inline: a finding located inside an earlier fix from the same phase stops the round, because it is the signal that the approach may be wrong rather than incomplete |
| F-5.0-08 | critical | The audit log can write the NCBI API key in cleartext into an append-only file. `ncbi_transport._append_api_key` (line 1105) appends the credential to the QUERY STRING, so the `url` at the transport chokepoint carries the secret. Section 20.3 requires the audit line to record "endpoint or database called", and `redact_params` matches on KEY NAME, so a field named `endpoint` or `url` holding that URL is not redacted by anything | lead, reviewing the T-5.0-02 module against the transport it will hook | fixed | `redact_params` in `src/system_03_search_agent/observability/audit.py` now applies a second, independent rule after the key-name rule: any string value that survives (its key was innocuous) is itself scanned via `_redact_value_string`, which blanks a URL query parameter whose NAME is secret-ish and a connection-string password in a URL's userinfo segment, reusing `_SECRET_KEY_MARKERS` so the two rules cannot drift apart. Host, path and non-secret query parameters are preserved so the line stays diagnostically useful; a URL carrying no secret passes through byte-identical. Note this is only the redactor half: T-5.0-05 still owns wiring `record_tool_call` into the transport and should prefer `_host_of`-style endpoint recording over the raw URL where possible, per this finding's original note, with the redactor as defense in depth rather than the only control. Five new tests added to `tests/system_03_search_agent/observability/test_audit.py` (22 total, up from 17), each proven killable by mutation: removing the value-scanning branch turned 4 of 5 new arms red, and a complementary over-redaction mutation turned the fifth (no-secret-passthrough) red, confirming every new arm can fail. `ruff check` clean, file restored byte-identical after both mutations |
| F-5.0-07 | major | The suite's hermetic guard cannot see LangSmith. `tests/conftest.py` blocks real outbound calls by patching `httpx.AsyncHTTPTransport.handle_async_request` and `httpx.HTTPTransport.handle_request`, deliberately at the socket-I/O layer so in-process ASGI clients are unaffected. The installed langsmith 0.10.10 drives its HTTP through `requests` (38 references in `client.py`) rather than httpx, so nothing in the guard covers it | lead, while reading conftest before writing config tests | FIXED | Masked today only because tracing is hardcoded off and no key exists, which is exactly the pair this phase removes. Owned by T-5.0-07, which extends the guard to the `requests` layer. Recorded with its mechanism because a FIRST reading of the same file got it wrong in the safe direction, believing the guard was patched at `ncbi_transport.execute_get` and therefore narrower than it is. CLOSED 2026-08-29, and it stopped being hypothetical the same day: the product owner provisioned a real `LANGSMITH_API_KEY`, which flipped `tracing_enabled()` to True, so a plain `pytest` run would have shipped real traces of test data to a real LangSmith project. `tests/conftest.py` now also patches `requests.adapters.HTTPAdapter.send`, at the same socket-I/O layer and for the same reason the two httpx blockers sit where they do. Four permanent arms in `test_hermetic_guard.py`, including an over-blocking arm proving an in-process ASGI client still works. Mutation: removing the patch turns exactly the two `requests` arms red and leaves the other two green |
| F-5.0-04 | minor | Section 20.1 says the Guardrail step mints `trace_id`; the shipped code mints it in three adapters (`web_sse/app.py:1299`, `graphql/schema.py:291`, `mcp/server.py:765`) and Section 13.1 agrees with the code | lead, from research | open | A re-confirmation of the build phase 4.6 finding, not a new defect. Recorded so this phase does not re-manufacture the requirement that phase already reverted. No code change |

## History

- 2026-08-29: phase opened on `phase/5.0-observability`. Baseline re-measured at the branch point rather than carried forward, per build phase 4.4: `4158 passed, 170 skipped, 1 xfailed, 0 failed`, drift 0 stale 0 structural, all three transports green.
- 2026-08-29: three researchers dispatched in parallel (audit call sites, LangSmith API surface, PostHog wire contract). All three reported. F-5.0-01 through F-5.0-04 filed from their output before any builder was dispatched.
- 2026-08-29: design settled on three transport chokepoints rather than an `act_node` hook, on two independent grounds: coverage (five bypass sites) and field availability (HTTP status and latency exist only at the transport).
- 2026-08-29: fix agent (independent of T-5.0-02's author, per the maker-cannot-check rule) closed F-5.0-08. Added value-level redaction to `redact_params` in `audit.py` and five mutation-proven tests to `test_audit.py`. Suite `22 passed`, `ruff check` clean on both files. State moved to fixed.
- 2026-08-29: fix agent (independent of T-5.0-03's author, per the maker-cannot-check rule) closed F-5.0-09. Replaced the bare `issubset` recognition test in `tracing.py`'s `_allowlist_for` with `_looks_like_model` (pure subset OR two-or-more-field co-occurrence), so an extra undeclared key is default-denied instead of disabling recognition, and added a `sessionid` category entry as a named second layer for the one residual gap the new rule's own docstring documents. Four mutation-proven tests added to `test_tracing.py` (14 total, up from 10). Suite `14 passed`, `ruff check` clean on both files, mutation reverting the rule to `issubset` turned exactly the two new extra-key arms red, file restored byte-identical. State moved to fixed.
- 2026-08-29: F-5.0-01 and F-5.0-06 closed by T-5.0-06. `env.example` gained the audit sink's two variables and, more usefully, a written explanation of why a blank `LANGSMITH_API_KEY` is what keeps tracing off while the flag beside it reads `true`, so the next reader does not repeat this phase's critical finding by deleting what looks like a contradiction.
- 2026-08-29: `.env` and `env.example` brought key-for-key into sync at the product owner's request, 40 keys each, verified by a two-way diff of key names. F-5.0-10 filed and fixed. `.env` re-confirmed gitignored at `.gitignore:19`, never tracked and absent from git history.
- 2026-08-29: the product owner provisioned both credentials. That closed F-5.0-07 by making it urgent rather than latent, and opened F-5.0-12: the PostHog credential is a personal API key rather than a project token, so nothing will be sent to PostHog until it is replaced.
- 2026-08-29: F-5.0-13 filed and the phase ESCALATED under Rule 4. The second half of it sits inside the F-5.0-08 fix, which is the stop condition, so it is handed to the product owner with options rather than patched in place by the lead.
- 2026-08-29: PAUSED by the product owner ahead of a session limit, with F-5.0-13 open and awaiting a decision. Tree clean, branch pushed, six of seven tickets complete.
