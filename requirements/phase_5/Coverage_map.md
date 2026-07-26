# Phase 5 coverage map

This document is the gate list a builder works against during Phase 6. It converts three locked specifications, requirements/Technical_specification.md, requirements/PRD.md, and requirements/Evaluation_playbook.md, into one checkable table of enforceable obligations, each one tied to the rule or skill that owns it.

It was produced by ten parallel agents. Seven of them extracted enforceable obligations from the three locked specifications: five agents covered the Technical specification in slices (sections 1 to 5, section 6 tool specifications, sections 7 to 12, sections 13 to 20, and sections 21 to 25), one covered the PRD, and one covered the Evaluation playbook. Each extracted obligation was mapped to a candidate owner, the rule or skill responsible for enforcing it, or NONE where no owner existed yet at extraction time.

How to use this document: work Phase 6 against the per-slice tables below. Before shipping a feature a table covers, confirm the obligation's candidate owner is wired up, as a rule, a skill, or code, and enforced. The "Obligations with no owner" section lists every row that had no owner at extraction time, grouped by where Phase 5 routed it. The "Cross-tool contract" section lists the ten obligations every one of the seven tools must satisfy, drawn from the tool-specification slice.

Date: 2026-07-26.

## Table of contents

- [Summary of totals](#summary-of-totals)
- [Slice 1: Technical specification, sections 1 to 5](#slice-1-technical-specification-sections-1-to-5)
- [Slice 2: Technical specification, section 6 (tool specifications)](#slice-2-technical-specification-section-6-tool-specifications)
- [Slice 3: Technical specification, sections 7 to 12](#slice-3-technical-specification-sections-7-to-12)
- [Slice 4: Technical specification, sections 13 to 20](#slice-4-technical-specification-sections-13-to-20)
- [Slice 5: Technical specification, sections 21 to 25](#slice-5-technical-specification-sections-21-to-25)
- [Slice 6: PRD](#slice-6-prd)
- [Slice 7: Evaluation playbook](#slice-7-evaluation-playbook)
- [Obligations with no owner](#obligations-with-no-owner)
- [Cross-tool contract](#cross-tool-contract)

## Summary of totals

Counted directly from the seven source tables: every row with an ID (D1-01 through D7-32) counts as one obligation. A row counts as "had an owner" when its candidate-owner column names any rule or skill, including a tentative one marked with a question mark. A row counts as "unowned" only when its candidate-owner column is the literal value NONE.

| Source | Obligations | Had an owner | Unowned |
|---|---|---|---|
| Technical specification (slices 1 to 5) | 226 | 191 | 35 |
| PRD | 45 | 37 | 8 |
| Evaluation playbook | 32 | 18 | 14 |
| Total | 303 | 246 | 57 |

## Slice 1: Technical specification, sections 1 to 5

Source: phase5_demand_01_sections_1-5.md, extracted from requirements/Technical_specification.md sections 1 to 5 (lines 39 to 711). 40 rows.

| # | Section | Obligation (one imperative line) | Type | Candidate owner | Spec line |
|---|---|---|---|---|---|
| D1-01 | 1.2 | Guardrail must validate input, reject prompt injection, off-topic, and medical-advice requests, and check rate and cost pre-caps before any model call runs. | security | ai-security-standards | 117 |
| D1-02 | 1.2 | Plan step must never write Cypher; cypher_query generates and validates Cypher internally. | correctness | production-standards | 119 |
| D1-03 | 1.2 | Write step must synthesize the cited research brief from structured findings only, with the harness binding and verifying every citation marker. | correctness | production-standards | 121 |
| D1-04 | 1.4 | The surface must never see a raw tool payload, a raw LLM completion, or raw chain-of-thought; it only consumes the typed event stream. | security | production-standards | 179 |
| D1-05 | 1.5 | A rejected query must never proceed past Guardrail; rejection stops the loop at a guard event. | security | ai-security-standards | 186 |
| D1-06 | 1.5 | Raw Cypher must never cross from Think or Plan to Act. | security | production-standards | 187 |
| D1-07 | 1.5 | A raw API payload, raw abstract, or raw record body must never cross unmediated from Act to Write. | security | production-standards | 188 |
| D1-08 | 1.5 | An unbound citation marker must never cross from Write to Core output; the harness strips any marker it cannot verify. | correctness | production-standards | 189 |
| D1-09 | 1.5 | Raw chain-of-thought must never cross from Core to Surface; reasoning is always a curated narrative. | security | ai-security-standards | 190 |
| D1-10 | 1.5 | No direct LLM or tool call may bypass the harness's cost-accounting path. | cost | system-design-patterns | 191 |
| D1-11 | 2.1 | Query.text, session_id, trace_id, and user_id must be schema-validated with max_length caps (2000, 64, 64, 64) at the FastAPI boundary. | security | production-standards | 236 |
| D1-12 | 2.1 | run() must never return a bare string or raw model completion; every output unit is a typed Event. | correctness | production-standards | 227 |
| D1-13 | 2.2 | Every event envelope must include type, version, trace_id, seq, ts, and payload. | correctness | production-standards | 257 |
| D1-14 | 2.3 | Every event string field must carry maxLength and every array maxItems, and tool fields must be enums pinned to the seven registered tools. | security | production-standards | 371 |
| D1-15 | 2.4 | A token referencing an unbound or unverifiable citation marker must have that marker stripped before the token event is emitted. | correctness | production-standards | 378 |
| D1-16 | 2.4 | Citation id matching must be exact-string, never fuzzy. | correctness | production-standards | 379 |
| D1-17 | 2.5 | think and plan events must carry only a curated narrative field, never a raw token-level reasoning trace. | security | ai-security-standards | 383 |
| D1-18 | 2.6 | Within v1, contract changes must be additive only; a breaking change requires a v2 contract. | process | NONE | 393 |
| D1-19 | 2.6 | A tool-registry change (add or remove a tool) must be coordinated with a contract-version bump, never silent. | process | NONE | 395 |
| D1-20 | 2.7 | The cost event must be filtered from every end-user surface and shown only to operator callers; done's cost fields must be suppressed for non-operator callers. | security | ai-security-standards | 409 |
| D1-21 | 3.4 | The coordinator-worker reader must be scoped to Read plus the one API that produced the payload, never Write, never call another tool. | security | production-standards | 473 |
| D1-22 | 3.4 | Synth tier must never receive a raw record; it receives only the reader's structured findings or pass-through structured fields. | security | production-standards | 474 |
| D1-23 | 3.5 | A tool or model-call failure must never silently default; every failure is classified transient, recoverable, or unexpected before any retry, and every retry is logged. | correctness | production-standards | 540 |
| D1-24 | 3.5 | When a failure recurs, the harness must be iterated first and the model swap tried second. | process | NONE | 540 |
| D1-25 | 3.6 | Model tier selection must be scored deterministically for correctness against the Phase 6 model-bench before being locked; taste-weighted scoring is reserved for Write-step tone only. | test | eval-harness | 544 |
| D1-26 | 3.3 | resolve_model() must never hardcode a model id; model identity is resolved only from env-configured tier values. | process | NONE | 461 |
| D1-27 | 4.2 | The tool list must never change mid-session, the model per tier must never switch mid-query, and no timestamp, request id, or volatile token may sit in the stable prompt-cache prefix. | performance | NONE | 587 |
| D1-28 | 4.2 | Tool schemas in the prompt-cache prefix must be sorted alphabetically and fixed in code, never re-ordered at runtime. | performance | NONE | 576 |
| D1-29 | 4.3 | A cache miss combined with an API failure must never serve a stale entry as fresh and must never silently substitute a default; it must propagate a recoverable error event. | correctness | production-standards | 613 |
| D1-30 | 5.1 | The graph database port must never open to the internet in either transport phase; only 443 is internet-facing. | security | ai-security-standards | 645 |
| D1-31 | 5.1 | The Cypher validator must reject any generated query containing a write keyword (CREATE, MERGE, DELETE, SET, REMOVE) before execution. | security | production-standards | 647 |
| D1-32 | 5.1 | The database role (kg_reader) must carry no write grants. | security | ai-security-standards | 648 |
| D1-33 | 5.1 | The v1 HTTPS query service must accept only MATCH/RETURN-shaped bodies and refuse anything else. | security | production-standards | 648 |
| D1-34 | 5.1 | Cypher generation inside cypher_query must follow a fixed order: Plan hands structured intent, then the tool's plan-tier call generates Cypher against a sliced schema, then a validator checks the Cypher before execution. | correctness | production-standards | 650 |
| D1-35 | 5.2 | Tool code must parse each Layer 2 or Layer 3 response against its own output JSONSchema and extract only schema-declared fields; nothing outside the schema may survive the call. | security | production-standards | 666 |
| D1-36 | 5.2 | The model must never see a raw Layer 2 or Layer 3 response body. | security | production-standards | 667 |
| D1-37 | 5.2 | Every Layer 2/3 tool output string field must carry maxLength, every array maxItems, and every source_url a host-pinned regex. | security | production-standards | 669 |
| D1-38 | 5.2 | Each Layer 2/3 tool must declare its allowed host or hosts, its own per-call timeout, and its own rate-limit pool up front. | security | ai-security-standards | 671 |
| D1-39 | 5.2 | Independent tool calls must run in parallel via asyncio.gather whenever the Plan step's call list contains two or more independent calls. | performance | parallel-first | 665 |
| D1-40 | 5.3 | No tool call may span two layers; each tool is scoped to exactly one layer. | correctness | system-design-patterns | 673 |

## Slice 2: Technical specification, section 6 (tool specifications)

Source: phase5_demand_02_section_6_tools.md, extracted from requirements/Technical_specification.md section 6 (lines 712 to 1467). 43 rows.

| # | Section | Obligation (one imperative line) | Type | Candidate owner | Spec line |
|---|---|---|---|---|---|
| D2-01 | all 7 | Every tool schema must enforce maxLength on every string, maxItems on every array, a host-pinned source_url regex, and no additionalProperties | security | production-standards | 714 |
| D2-02 | all 7 | Every tool must act as a read-plus-one-source reader that calls only its own source, never another tool, never a write path | security | system-design-patterns | 714 |
| D2-03 | all 7 | Every source_url pattern must use the strict host-pinned regex from Section 9.3, never the looser any-subdomain form | security | production-standards | 716 |
| D2-04 | all 7 | A citation must always resolve to the human-facing record page, never the eutils or api fetch host the tool actually called | security | production-standards | 716 |
| D2-05 | all 7 | Untrusted free text fields returned by any Layer 2 or 3 source must never be treated as an instruction, only as data for an isolated reader pass before Synth | security | ai-security-standards | 1178 |
| D2-06 | all 7 | A zero-result response must map to status empty, not error, and act as the cite-or-refuse trigger for that layer | correctness | production-standards | 798 |
| D2-07 | all 7 | Every tool must enforce its own specified per-call timeout | performance | system-design-patterns? | 1451 |
| D2-08 | all 7 | Every tool call is subject to the shared per-user and per-query cost budget in Section 21 | cost | system-design-patterns | 986 |
| D2-09 | all 7 | A tool must never inline a full large result set into agent context, it must truncate and report the total available count | performance | system-design-patterns | 800 |
| D2-10 | all 7 | Any API key must be passed via environment variable only, never hardcoded or logged | security | ai-security-standards | 986 |
| D2-11 | 6.1 | The main agent must never generate or see raw Cypher, only cypher_query's internal pipeline may generate it | security | ai-security-standards | 722 |
| D2-12 | 6.1 | Generated Cypher must be validated before execution, with exactly one retry feeding the validator error back, then return status error on a second failure | process | production-standards | 799 |
| D2-13 | 6.1 | Every Cypher query must use an explicit edge label, never an untyped relationship pattern | correctness | NONE | 794 |
| D2-14 | 6.1 | The cypher_executed field is an audit trail only and must never be rendered raw to the end user | security | ai-security-standards | 788 |
| D2-15 | 6.1 | The tool must auto-inject row_limit, default 100 hard max 500, when LIMIT is missing, and set truncated plus total_available when true rows exceed what is returned | performance | system-design-patterns | 800 |
| D2-16 | 6.1 | cypher_query must enforce a 30 second per-call timeout | performance | NONE | 803 |
| D2-17 | 6.2 | field_tags must be validated against the EInfo field list for db before use, never built from free text | security | production-standards | 829 |
| D2-18 | 6.2 | The link action must always specify an explicit target db, never rely on the ELink default | correctness | NONE | 858 |
| D2-19 | 6.2 | coordinate_overlap must apply the exact overlap predicate in tool code, never trust the raw ESearch coordinate range | correctness | production-standards | 966 |
| D2-20 | 6.2 | The tool must inspect the response body, not HTTP status, to decide cite-or-refuse for every E-utilities action, while Datasets and PubChem branch on HTTP status directly | correctness | production-standards | 982 |
| D2-21 | 6.2 | The XML parser used for retmode xml must disable external entities | security | production-standards | 982 |
| D2-22 | 6.2 | ncbi_efetch must enforce a 15 second per-call timeout with one backoff retry on transient failure | performance | NONE | 984 |
| D2-23 | 6.2 | The tool must respect E-utilities rate limits of 3 requests per second unauthenticated and 10 per second with an API key | cost | system-design-patterns? | 986 |
| D2-24 | 6.2 | Pathogen Detection and ClinicalTrials.gov must never be folded into ncbi_efetch as extra actions, each gets its own named tool | process | NONE | 988 |
| D2-25 | 6.3 | The tool must read frequency data only from the global_mafs array, the flat global_maf scalar is verified null and must never be read | correctness | NONE | 1072 |
| D2-26 | 6.3 | The defensive handling for non-200 or malformed Variation Services responses must be live-verified before Phase 6 ships the tool | test | dev-standards? | 1074 |
| D2-27 | 6.3 | Variation Services normalization and the dbSNP ESummary clinical fetch must run sequentially, never in parallel, within one tool invocation | correctness | NONE | 1076 |
| D2-28 | 6.3 | ncbi_dbsnp must enforce a 15 second per-call timeout and budget up to 30 seconds worst case for one invocation | performance | NONE | 1076 |
| D2-29 | 6.3 | The tool must respect the Variation Services rate limit of roughly 1 request per second, a separate pool from E-utilities | cost | NONE | 1078 |
| D2-30 | 6.4 | Entity lookup with zero matches must map to status empty, a biocjson 400 response must map to status error using the detail string as the message | correctness | production-standards | 1176 |
| D2-31 | 6.4 | name, description, and every annotation field are untrusted free text and must get an isolated reader pass before the Synth model sees them | security | ai-security-standards | 1178 |
| D2-32 | 6.4 | pubtator_annotate must enforce a 15 second per-call timeout | performance | NONE | 1180 |
| D2-33 | 6.4 | The PubTator3 relations endpoint must not ship until its path and fields are live-verified | process | NONE | 1174 |
| D2-34 | 6.5 | The litvar_id must be URL-encoded by the tool before the call, with @ encoded as %40 and # encoded as %23 | security | production-standards | 1205 |
| D2-35 | 6.5 | pmids must be capped at maxItems 50 with total_pmids carrying the true count, the tool must always truncate and always report the total | performance | system-design-patterns | 1255 |
| D2-36 | 6.5 | litvar2_lookup must enforce a 15 second per-call timeout | performance | NONE | 1257 |
| D2-37 | 6.6 | The tool must resolve and pin only to the latest COMPLETE snapshot with Metadata, Clusters, and AMR directories all present, never a mid-build snapshot | correctness | NONE | 1348 |
| D2-38 | 6.6 | The tool must never stream or load a full TSV into agent context, it must index and read only the matched rows and report total_available when truncated | performance | system-design-patterns | 1360 |
| D2-39 | 6.6 | pathogen_detection must enforce a per-call timeout of 60 seconds or more | performance | NONE | 1358 |
| D2-40 | 6.6 | A biosample_acc or pds_cluster not found in the pinned snapshot must map to status empty, an unreachable or incomplete snapshot must map to status error naming the taxon and snapshot version | correctness | production-standards | 1354 |
| D2-41 | 6.7 | brief_title, eligibility_summary, and every free-text module field are untrusted content and must get the isolated reader pass before Synth sees them | security | ai-security-standards | 1433 |
| D2-42 | 6.7 | A query with no matches must return status empty as the Layer 3 cite-or-refuse trigger | correctness | production-standards | 1431 |
| D2-43 | 6.7 | clinicaltrials_search must enforce a 15 second per-call timeout with a provisional throttle of about 5 requests per second | performance | NONE | 1435 |

## Slice 3: Technical specification, sections 7 to 12

Source: phase5_demand_03_sections_7-12.md, extracted from requirements/Technical_specification.md sections 7 to 12 (lines 1468 to 2142). 50 rows.

| # | Section | Obligation (one imperative line) | Type | Candidate owner | Spec line |
|---|---|---|---|---|---|
| D3-01 | 7.1 | State the live Layer 2 or Layer 3 value, never the graph value, as current whenever both were fetched for the same answer | correctness | NONE | 1478 |
| D3-02 | 7.2 | Run the shared-field comparison in Write step code, on schema-extracted fields, never as a model judgment or a free-text diff | correctness | production-standards? | 1486 |
| D3-03 | 7.1/7.2 | Never silently drop one side or silently pick one value on a detected cross-layer disagreement; cite both and route the claim to the trust signal's flag outcome | correctness | production-standards | 1480 |
| D3-04 | 7.3 | Give every coordinate or sequence answer an explicit assembly field, never left implicit, and refuse to state the claim if assembly resolves to null | correctness | production-standards | 1535 |
| D3-05 | 7.4 | Auto-cross-verify a volatile Layer 1 field against a live Layer 2 call before citing it as current once its graph snapshot exceeds the 30-day (volatile class) or 90-day (stable class) staleness threshold | correctness | NONE | 1547 |
| D3-06 | 8.1 | Give Synth only a code-built, structured findings list, never a raw retrieved document | security | production-standards | 1561 |
| D3-07 | 8.1 | Validate every finding passed to Synth against the required schema (ref_index, citation_id, layer, tool, field, field_value, source_url) | test | production-standards | 1577 |
| D3-08 | 8.1 | Bind one citation marker to exactly one finding; a claim drawing on two findings carries two markers, never one marker covering both | correctness | production-standards | 1583 |
| D3-09 | 8.1 | Strip any factual-sounding clause that has no adjacent citation marker as untraceable | correctness | production-standards | 1584 |
| D3-10 | 8.2 | Ground every claim by exact-or-substring match after normalization only, never a fuzzy or model-judged score, regardless of risk tier | correctness | production-standards | 1590 |
| D3-11 | 8.2 | Drop any clause whose marker does not resolve to a ref_index in the findings list, accept a claim as grounded only via the normalize-then-match rule with no embedding similarity or LLM-judged closeness, and retain the stripped-claim count for the eval harness and audit trail without ever surfacing it as a citation | correctness | production-standards | 1595 |
| D3-12 | 8.2 | Discard the partial narrative and return the refuse path when grounding strips the query's core ask entirely, rather than ship a thin or misleading answer | correctness | production-standards | 1600 |
| D3-13 | 8.2 | Run the grounding check before the trust-signal step on every answer, with no risk-tier exemption | process | production-standards | 1609 |
| D3-14 | 8.3.1 | Compute risk tier per claim, never per query | correctness | production-standards | 1617 |
| D3-15 | 8.3.2 | Run triangulation only for high-risk claims, comparing categorical bucketed values across independent-origin sources, never free-text similarity | correctness | production-standards | 1630 |
| D3-16 | 8.3.2 | Count two findings as independent only when they come from different origin databases; two fetches of the same origin database never count as two independent sources | correctness | production-standards | 1632 |
| D3-17 | 8.3.3 | Apply the fixed risk-tier/grounded/triangulation decision table deterministically to yield exactly one of answer, flag, ask, or refuse | correctness | production-standards | 1652 |
| D3-18 | 8.3.3 | Refuse any ungrounded claim regardless of its risk tier | correctness | production-standards | 1656 |
| D3-19 | 8.3.4 | Attach each grounded claim's own trust_signal to its citation via the shared citation_id, never embedded on the citation object itself | correctness | production-standards | 1665 |
| D3-20 | 8.3.4 | Compute the answer-level trust_signal as the most restrictive outcome among the answer's claims (refuse outranks ask, ask outranks flag, flag outranks answer) | correctness | production-standards | 1667 |
| D3-21 | 8.4 | Emit an NCBI cross-database fallback link on every refuse outcome, fully percent-encoded, validated against the host-pinned regex before it is ever attached to an event | security | production-examples | 1677 |
| D3-22 | 8.4 | Close the response on a refuse outcome with no further citation or token events, and mark the done event status refused, never error | process | production-standards | 1690 |
| D3-23 | 9.1 | Emit the same provenance schema on every citation across all four surfaces (UI, REST/SSE, MCP, export) | correctness | system-design-patterns | 1696 |
| D3-24 | 9.1 | Never make trust_signal a field on the citation payload; keep it a separate event joined by citation_id | correctness | system-design-patterns? | 1725 |
| D3-25 | 9.2 | Populate evidence_kind and assertion_confidence only from the fixed per-tool default table or lexicon in code, never as a per-call model judgment | correctness | production-standards | 1740 |
| D3-26 | 9.2 | Render a null population_ancestry_context as "not specified" in the UI, never inferred or guessed | correctness | production-standards | 1760 |
| D3-27 | 9.2 | Treat license: unspecified as a build-blocking gap for any tool that reaches it; must not ship in v1 without a confirmed per-source mapping | process | production-standards | 1770 |
| D3-28 | 9.3 | Validate every source_url against its layer's host-pinned allowlist regex before it is attached to a citation event, and reject the citation on failure | security | production-standards | 1774 |
| D3-29 | 9.3 | Never let a fetch-only host (eutils.ncbi.nlm.nih.gov, api.ncbi.nlm.nih.gov) appear as a source_url value | security | production-standards | 1793 |
| D3-30 | 9.4 | Renumber display_index sequentially only after the grounding pass strips hallucinated markers, and keep citation_id as the stable, never-changing binding key | correctness | production-standards | 1801 |
| D3-31 | 10.1 | Route every query through the ordered six-step guardrail pipeline before it can reach Think, Plan, or Act | security | ai-security-standards | 1829 |
| D3-32 | 10.1 | Emit a guard event with outcome and reason, and stop the loop, for any query that fails a pipeline step | security | ai-security-standards | 1838 |
| D3-33 | 10.2 | Reject immediately at zero model cost on a confident non-LLM pre-filter match (off-topic, medical-advice pattern, or injection marker) | security | ai-security-standards | 1844 |
| D3-34 | 10.3 | Type- and length-bound every chat request with a Pydantic model at the FastAPI boundary; never let a raw dict or untyped payload reach Guardrail code | security | production-standards | 1852 |
| D3-35 | 10.4 | Schema-validate the Guard-tier model's structured injection-classification output before it is accepted or rejected | security | production-standards | 1868 |
| D3-36 | 10.5 | Reject outright any query requesting a write, mutation, or deletion against the graph, including hypothetical or indirect phrasing | security | ai-security-standards | 1879 |
| D3-37 | 10.5 | Enforce read-only access at three independent points (guardrail rejection, Cypher validator, kg_reader connection role with no write grant), with no single layer carrying the whole guarantee | security | ai-security-standards | 1884 |
| D3-38 | 10.6 | Enforce the per-user daily (100 queries), system-wide daily ($10), per-query ($0.10), and per-step timeout caps at their specified gate points, and never show the end user a dollar figure on a cap rejection | cost | system-design-patterns | 1896 |
| D3-39 | 11.1 | Schema-validate every Layer 2 and Layer 3 tool result (maxLength on strings, maxItems on arrays) before it reaches any prompt | security | ai-security-standards | 1915 |
| D3-40 | 11.1/11.2 | Restrict the isolated reader to no tool-calling ability beyond its own scoped re-verification call, no write access to graph/database/filesystem, and no ability to invoke another tool or sub-agent | security | system-design-patterns | 1916 |
| D3-41 | 11.1 | Never format retrieved content into a system or developer-role message; it enters a model call only as user-role or tool-role data | security | ai-security-standards | 1919 |
| D3-42 | 11.3 | Never send account PII (email, name) to an external LLM prompt | security | ai-security-standards | 1940 |
| D3-43 | 11.4 | Keep every credential in an environment variable or secrets manager only, never in code, prompts, logs, or generated docs; log only the key's name on failure, never its value | security | ai-security-standards | 1946 |
| D3-44 | 11.5 | Log every Layer 2 and Layer 3 access with tool, endpoint, params, finding count, credential/role identifier, admitting guardrail step, cost, trace_id, and timestamp, without ever inlining the full response payload | security | ai-security-standards | 1962 |
| D3-45 | 12.1 | Never let the React UI retrieve data, ground a claim, or compute a trust signal itself | security | system-design-patterns | 1976 |
| D3-46 | 12.2 | Never register a client-side listener for a cost event, and never let the server write one onto a non-operator connection | cost | system-design-patterns | 2068 |
| D3-47 | 12.4 | Never render a citation chip from data the frontend has not received as a verified citation event | correctness | production-standards | 2078 |
| D3-48 | 12.4 | Validate a citation's source_url client-side against the allowed host set before navigation, as a second check behind the server's host-pinned regex | security | production-examples | 2080 |
| D3-49 | 12.6 | Never render a dollar amount, token count, or cost figure in GuardrailBanner or CapMessage copy | cost | system-design-patterns | 2105 |
| D3-50 | 12.8 | Never show a raw, token-level chain-of-thought trace in ReasoningExpander | security | production-standards | 2115 |

## Slice 4: Technical specification, sections 13 to 20

Source: phase5_demand_04_sections_13-20.md, extracted from requirements/Technical_specification.md sections 13 to 20 (lines 2143 to 2871). 48 rows.

| # | Section | Obligation (one imperative line) | Type | Candidate owner | Spec line |
|---|---|---|---|---|---|
| D4-01 | 13.1 | Every request body to the REST plus SSE API must be validated with a Pydantic model at the FastAPI boundary. | security | production-standards | 2162 |
| D4-02 | 13.1 | GET /v1/query/{run_id}/events must require the same authenticated identity that owns run_id, else return 403. | security | production-standards | 2167 |
| D4-03 | 13.1 | POST /v1/query/{run_id}/stop must be idempotent: a finished or already-stopped run returns 200, never an error. | correctness | production-standards | 2168 |
| D4-04 | 13.1 | The cost event must never be written to the SSE response when operator_mode is false. | security | system-design-patterns | 2183 |
| D4-05 | 13.1 | operator_mode must be derived server-side from the authenticated identity's role, never taken from a client-supplied field. | security | ai-security-standards | 2189 |
| D4-06 | 13.2 | No MCP tool may expose a raw Cypher passthrough or a raw NCBI API passthrough; only ask_biomedical_question is exposed. | security | system-design-patterns | 2231 |
| D4-07 | 13.2 | Each MCP client must authenticate with its own scoped API key, never the web UI's session credential. | security | ai-security-standards | 2231 |
| D4-08 | 13.3 | A non-operator CLI credential passing --operator must have the flag silently ignored server-side. | security | ai-security-standards | 2243 |
| D4-09 | 13.3 | On Ctrl-C the CLI must send a stop request for the run before the process exits. | correctness | system-design-patterns | 2255 |
| D4-10 | 14.1 | Two users asking an identical question with no session history must receive an identical set of grounded claims, regardless of personalization. | correctness | production-standards | 2283 |
| D4-11 | 14.3 | SessionMemorySummary fields must enforce hard caps (per-field maxLength and maxItems, token_budget 1500) enforced at injection, never treated as a soft target. | security | production-standards | 2323 |
| D4-12 | 14.3 | resolved_entities must never be dropped for budget reasons alone; eviction beyond the 50-item cap must be FIFO. | correctness | production-standards | 2327 |
| D4-13 | 14.4 | SessionMemorySummary must never be injected into the Act step; tool calls must always execute against fresh retrieval, never memory. | correctness | production-standards | 2333 |
| D4-14 | 14.4 | A compressed_finding must never be asserted in Write as a citable source; Plan must schedule re-verification before it can support an answer. | correctness | production-standards | 2333 |
| D4-15 | 14.4 | The session-memory token cap must be enforced server-side with the actual tokenizer before injection, never a client-supplied or assumed character count. | security | production-standards | 2335 |
| D4-16 | 14.5 | audience_depth must never change which tool results are retrieved, the cite-or-refuse gate, or the trust-signal rule. | correctness | production-standards | 2347 |
| D4-17 | 15 | The user-data database connection must never reach the graph box, and the graph box must never see a user's email, query text, or feedback. | security | ai-security-standards | 2363 |
| D4-18 | 15 | The kg_reader role must be read-only, enforced at the connection level and double-checked by the Cypher validator. | security | ai-security-standards | 2367 |
| D4-19 | 15 | The access token must be a short-lived (15 minute) JWT carrying only user_id, never PII beyond the user id. | security | ai-security-standards | 2386 |
| D4-20 | 15 | The refresh token must be stored only as its SHA-256 hash and rotated on every use. | security | ai-security-standards? | 2387 |
| D4-21 | 15 | Passwords must be hashed with argon2id, never a reversible encoding, and never logged. | security | ai-security-standards | 2388 |
| D4-22 | 15 | users.profile must hold presentation-layer preferences only, never grounding-relevant state. | correctness | production-standards | 2405 |
| D4-23 | 15 | Only reviewed_by and review_decision, both human-set fields, may move a cq_candidates row to promoted. | process | ai-security-standards | 2534 |
| D4-24 | 15 | The user-data schema must never share a connection pool, credential, or schema namespace with the AGE graph. | security | ai-security-standards | 2553 |
| D4-25 | 16 | Every completed query must write exactly one interactions row regardless of outcome. | correctness | production-standards | 2582 |
| D4-26 | 16 | The interactions insert must use ON CONFLICT (trace_id) DO NOTHING so a retried background task never double-writes a row. | correctness | production-standards | 2586 |
| D4-27 | 16 | A capture failure must be retried once, then dropped with a warning; it must never be surfaced to the user or block the response. | process | production-standards | 2587 |
| D4-28 | 16 | A cluster must clear the frequency threshold (3 occurrences in 30 days) and both moat gates before becoming a new candidate. | process | goal-contracts? | 2608 |
| D4-29 | 16 | The LLM-judge must never be the final say; only a human-set column (review_decision, reviewed_by) may promote a candidate. | process | ai-security-standards | 2625 |
| D4-30 | 16 | No column in interactions or cq_candidates may ever hold an API key, token, or credential. | security | production-standards | 2640 |
| D4-31 | 17 | The few-shot pool must load once at process start from a versioned file, never as a live database read on every request. | performance | NONE | 2650 |
| D4-32 | 17 | Think must resolve a recognizable exact identifier as ground truth before any fuzzy matching runs. | correctness | NONE | 2719 |
| D4-33 | 18 | The Guard tier and the deterministic harness layers (trust-signal rule, cost caps, cite-or-refuse) must stay fixed across every A/B arm, never a target of experimentation. | correctness | production-standards | 2743 |
| D4-34 | 18 | A new A/B experiment must start at a low variant share and only ramp after a human reviews the early comparison. | process | ai-security-standards | 2770 |
| D4-35 | 18 | An A/B conclusion must be gated by a minimum sample size: 30 golden-dataset replays or 100 live interactions per arm. | test | eval-harness | 2782 |
| D4-36 | 18 | If any arm's hard-fail rate drops below the pass^k = 100 percent target, that arm must auto-pause and traffic must route back to control. | correctness | production-standards | 2786 |
| D4-37 | 18 | Every experiment arm must obey the same per-query, per-user-daily, and system-daily cost caps; no arm gets extra budget headroom. | cost | system-design-patterns | 2787 |
| D4-38 | 18 | Starting, ramping, or ending an A/B experiment must be a human action. | process | ai-security-standards | 2788 |
| D4-39 | 19.1 | The harness must enforce four hard caps: per-query $0.10, per-user daily 100 queries, system-wide daily $10, and per-step timeouts of 5s, 10s, 30s, and 2 minutes. | cost | system-design-patterns | 2802 |
| D4-40 | 19.1 | Changing a cost cap value requires explicit approval, never a silent config edit. | process | system-design-patterns | 2809 |
| D4-41 | 19.2 | A cap check must run before a model call fires, refusing to dispatch a call that would certainly exceed the per-query cap. | cost | system-design-patterns | 2818 |
| D4-42 | 19.2 | A retried model call must be metered as a new billable event and checked against the remaining per-query budget before it fires. | cost | production-standards | 2819 |
| D4-43 | 19.4-19.5 | No dollar figure may ever reach an end-user-facing surface; every end-user adapter must filter the cost event out, leaving only the operator dashboard subscribed. | security | system-design-patterns | 2829 |
| D4-44 | 20.1 | User-account PII must never leave the auth service boundary and must never be attached to a LangSmith trace. | security | ai-security-standards | 2851 |
| D4-45 | 20.2 | PostHog must receive behavioral aggregates only, never raw query text or citation content. | security | ai-security-standards | 2857 |
| D4-46 | 20.3 | Every tool-call audit log line must record trace_id, tool name, endpoint, redacted params with no API keys, returned record ids, status, latency, and timestamp. | security | ai-security-standards | 2862 |
| D4-47 | 20.3 | The tool-call audit log must be append-only, never mutated after write, with one writer per process. | correctness | NONE | 2863 |
| D4-48 | 20.1 | trace_id must be minted at the Guardrail step and thread through every event, LiteLLM call, and tool call as the single join key. | process | NONE | 2849 |

## Slice 5: Technical specification, sections 21 to 25

Source: phase5_demand_05_sections_21-25.md, extracted from requirements/Technical_specification.md sections 21 to 25 (lines 2872 to 3319). 45 rows.

| # | Section | Obligation (one imperative line) | Type | Candidate owner | Spec line |
|---|---|---|---|---|---|
| D5-01 | 21.1 | NCBI API key must live in an env var only, never appear in code or logs | security | ai-security-standards | 2878 |
| D5-02 | 21.1 | Confirm which E-utilities rate-limit figure (3/10 vs 100 requests/second) is authoritative before locking throttle constants into code for the Phase 6 build | process | NONE | 2885 |
| D5-03 | 21.1 | Apply a provisional throttle of about 5 requests/second to the Datasets API v2 and each of the four enrichment APIs until a published rate limit is confirmed | correctness | NONE | 2887 |
| D5-04 | 21.3 | The Act step must hard-stop at 20 Layer 2 and Layer 3 tool calls per query regardless of what Plan estimated, and route to Write with whatever tool_results already exist | cost | system-design-patterns? | 2898 |
| D5-05 | 21.4 | Cap each API family's wait queue depth at roughly 15 to 30 calls and tie a queued call's wait ceiling to the query's remaining latency budget; a call that would exceed either must fail fast with an actionable rate_limited error | performance | NONE | 2906-2907 |
| D5-06 | 21.4 | On fail-fast, return a rate_limited error carrying a retry_after estimate and the saturated family name; Act may retry once with backoff if budget allows, otherwise mark the result unavailable | correctness | production-standards | 2909 |
| D5-07 | 22.1 | On zero-hit retrieval, refuse and stop; never answer from model priors | correctness | production-standards | 2923 |
| D5-08 | 22.1 | On a partial-layer failure, synthesize from whatever layers responded and explain the gap; never fail the whole query over one tool's error | correctness | production-standards | 2929 |
| D5-09 | 22.1 | On suspect Layer 1 data, fall back to Layer 2 as the authoritative source and correct the answer; surface the correction to the user only if it also leaves the answer incomplete | correctness | NONE | 2935 |
| D5-10 | 22.1 | On an ambiguous entity resolution, ask one targeted clarifying question before issuing any tool call; never guess | correctness | production-standards? | 2941 |
| D5-11 | 22.1 | Validate every E-utilities field tag against the EInfo field list before issuing a search, so a malformed tag never reaches the live API | correctness | production-standards | 2959 |
| D5-12 | 22.1 | Section 23's test coverage must include a rejected malformed-field-tag fixture | test | production-standards | 2960 |
| D5-13 | 22.2 | A non-fatal error must never sever the SSE connection or instruct a surface to discard already-rendered tokens or citations; every surface renders errors additively | correctness | system-design-patterns | 2964-2965 |
| D5-14 | 22.3 | The interactions-table capture write must use a natural-key upsert on trace_id so a retried write never double-logs the same query | correctness | production-standards | 2971 |
| D5-15 | 22.3 | Every error event must carry an actionable message naming the failed layer or tool, the error class, and a retry_after estimate where known; a bare "Error 500" must never ship | correctness | production-standards | 2972 |
| D5-16 | 22.3 | Enforce maxLength caps on every error-event field (scope 16, source 64, error_class 16, message 256) | security | production-standards | 2979-2983 |
| D5-17 | 23 | Guardrail unit tests (Pydantic validation, injection rejection, forbidden query types, rate and cost pre-checks) are merge-blocking | test | verify | 2999 |
| D5-18 | 23 | Tool logic unit tests (Cypher generation and validation, response parsing per tool, schema slicing) are merge-blocking | test | verify | 3000 |
| D5-19 | 23 | Layer 1 cypher_query integration tests against the real AGE graph are merge-blocking as a network-gated job | test | verify? | 3001 |
| D5-20 | 23 | Layer 2 and Layer 3 integration tests against live NCBI and enrichment endpoints are merge-blocking as a network-gated job | test | verify? | 3002 |
| D5-21 | 23 | Write-step grounding tests (cite-or-refuse, zero-retrieval refusal) are merge-blocking and required | test | production-standards | 3003 |
| D5-22 | 23 | FastAPI endpoint tests covering valid, invalid, and null input are merge-blocking | test | production-standards | 3004 |
| D5-23 | 23 | React UI component tests (render, interaction, WCAG 2.1 AA) are merge-blocking on UI-touching changes | test | production-standards | 3005 |
| D5-24 | 23 | Retry-safety idempotency tests are merge-blocking on any tool that writes or mutates state | test | production-standards | 3006 |
| D5-25 | 23 | The agent-answer-quality eval harness runs as a milestone gate before any answer-generation feature ships and again before every release, never on every PR | test | eval-harness | 3007 |
| D5-26 | 23 | Any unit test that builds a query string must assert the parameterized placeholder form; never an f-string or .format() on the query text itself | security | production-standards | 3015 |
| D5-27 | 23 | No graph integration test may issue write Cypher (CREATE, MERGE, DELETE); at least one test must confirm a write attempt is rejected at the kg_reader role level | test | production-standards | 3026 |
| D5-28 | 23 | Live Layer 2 and Layer 3 integration tests must run at a pace respecting each API's verified rate limit so the integration job never trips a rate limit itself | performance | NONE | 3031 |
| D5-29 | 23 | The dbVar two-step tool needs its own integration test asserting the placement post-filter removes cross-assembly false positives | test | NONE | 3033 |
| D5-30 | 23 | test_cite_or_refuse_compliance and test_zero_retrieval_refusal are merge-blocking on every PR that touches the Write step, a tool's output schema, or the provenance model | test | production-standards | 3048 |
| D5-31 | 23 | test_cite_or_refuse_compliance must use exact or substring match after normalization, never a fuzzy similarity threshold | correctness | production-standards | 3050 |
| D5-32 | 23 | The two required-path tests must never be deleted, narrowed, or weakened to make a change land faster | process | goal-contracts | 3052 |
| D5-33 | 23 | Domain sign-off for the clinical and human-variation golden fixtures needs a named owner before build phase 5.1 ships the 50-query golden dataset | process | NONE | 3044 |
| D5-34 | 24 | Never place a secret's value in logs or exception strings for any env var listed in this section; log the variable name only | security | ai-security-standards | 3120 |
| D5-35 | 24 | Python must compile and import cleanly, imports must pass isort --check, and code must pass ruff check, all merge-blocking ahead of the test suites | test | verify | 3130-3132 |
| D5-36 | 24 | pip-audit must show no Critical or High CVE before merge | security | supply-chain-security | 3135 |
| D5-37 | 24 | npm audit --audit-level=high must pass before merge | security | supply-chain-security | 3136 |
| D5-38 | 24 | Phase branches must never auto-deploy; only a merge to main triggers Railway's automatic build and deploy | process | git-workflow | 3141 |
| D5-39 | 24 | The security-scan milestone runs only as release-workflow Step 3 and a pull-request-template checkbox before a release or PR, never as an automated CI block | process | release-workflow | 3143 |
| D5-40 | 24 | The read-only HTTPS graph query service must accept only an already-validated, already-parameterized Cypher payload, never free-form Cypher text over the wire | security | production-standards | 3150 |
| D5-41 | 24 | The HTTPS graph query service must re-run the forbidden-keyword and edge-label checks server-side as defense in depth | security | production-standards | 3151 |
| D5-42 | 24 | The HTTPS graph query service must authenticate the HTTPS hop with a bearer token or API key (GRAPH_QUERY_TOKEN); an IP allowlist alone is not sufficient | security | ai-security-standards | 3153 |
| D5-43 | 24 | The HTTPS graph query service must enforce a hard row limit, a per-call timeout matching the tool's own budget, and a rate limit per caller | performance | NONE | 3154 |
| D5-44 | 24 | The HTTPS graph query service's database port must never open to the internet; TLS terminates via an automatic-HTTPS reverse proxy in front of it | security | production-standards | 3155 |
| D5-45 | 24 | The HTTPS graph query service must log every call, what was queried, when, and the caller, for the audit trail | security | ai-security-standards | 3156 |

### Per-phase build shape

Judged from the Technical specification's Section 25 build order table (lines 3178 to 3203) and dependency graph (lines 3221 to 3293).

| Build phase | Branch | Delivers (short) | Runnable artifact? | Independent build tasks (1 or 2+) | Overlapping files across tasks? |
|---|---|---|---|---|---|
| 1.0 | phase/1.0-fastapi-skeleton | FastAPI skeleton, health endpoint, typed run() contract stub, Pydantic boundary validation | Yes | 1 | No |
| 1.1 | phase/1.1-auth-service | Minimal v1 auth, Postgres user-data schema (interactions, cq_candidates, users) | Yes | 2+ | No (auth code vs schema) |
| 1.2 | phase/1.2-react-shell-sse | React shell, SSE consumption, empty chat endpoint wired end to end, stop button | Yes | 2+ | Yes (shared frontend tree) |
| 2.0 | phase/2.0-langgraph-agent-loop | LangGraph graph with stub Guardrail/Think/Plan/Act/Write nodes, three-tier harness wired, coordinator-worker scaffold, cost caps enforced | Yes (stub level) | 2+ | Yes (shared graph module) |
| 2.1 | phase/2.1-cypher-tool | cypher_query over Layer 1 prototype transport, schema slicing, validate-then-execute pipeline, edge-label enforcement | Yes | 2+ | Yes (shared tool module) |
| 2.2 | phase/2.2-write-step-grounding | Deterministic cite-or-refuse, provenance type for Layer 1, first trust signal, two required tests | Yes | 2+ | No (write-step code vs test code) |
| 3.0 | phase/3.0-guardrail-node | Full guardrail: Pydantic validation, injection rejection, forbidden query types, rate/cost pre-checks | Yes | 2+ | Yes (shared guardrail module) |
| 3.1 | phase/3.1-ncbi-efetch | ncbi_efetch: E-utilities (PubMed, ClinVar, OMIM) plus Datasets API v2 (Gene, Genome, Orthologs, Taxonomy) | Yes | 2+ | Yes (shared tool module) |
| 3.2 | phase/3.2-ncbi-dbsnp | ncbi_dbsnp over Variation Services, plus Q1 dbVar two-step sub-tool | Yes | 2+ | No (separate tool files) |
| 3.3 | phase/3.3-enrichment-tools | pubtator_annotate and litvar2_lookup, untrusted-source-reader tier separation | Yes | 2+ | No (separate tool files) |
| 3.5 | phase/3.5-pathogen-clinicaltrials-tools | pathogen_detection and clinicaltrials_search, own timeout/snapshot/cache semantics | Yes | 2+ | No (separate tool files) |
| 3.4 | phase/3.4-citation-trust-full | Provenance extended to Layer 2/3, two-tier risk gate, freshness and conflict resolution | Yes | 2+ | Yes (shared provenance/citation module) |
| 4.0 | phase/4.0-rest-sse-hardening | REST plus SSE adapter finalized as public API surface | Yes | 1 | No |
| 4.1 | phase/4.1-mcp-server | Outbound-only MCP server wrapping existing tool functions | Yes | 1 | No |
| 4.2 | phase/4.2-cli-adapter | Thin CLI client over REST API | Yes | 1 | No |
| 4.3 | phase/4.3-graphql-api | GraphQL surface via Strawberry, sharing auth and tools with REST | Yes | 1 | No |
| 4.4 | phase/4.4-kgx-export | Export utility scoped to the existing Hetzner graph, a batch job | Yes | 1 | No |
| 4.5 | phase/4.5-personalization-memory | Bounded session memory, audience-level depth control, stable named persona | Yes | 2+ | Yes (shared personalization/agent-state module) |
| 4.6 | phase/4.6-feedback-capture | Real interaction capture into interactions table, manual review ritual, hand-promotion to few-shot examples | Yes | 2+ | No (capture code vs review process) |
| 4.7 | phase/4.7-cq-routing | Few-shot routing seeded with the seven must-pass CQs, query-shape routing | Yes | 2+ | Yes (shared routing/plan module) |
| 5.0 | phase/5.0-observability | LangSmith tracing, PostHog analytics, tool-call audit log | Yes | 2+ | No (separate integration modules) |
| 5.1 | phase/5.1-golden-dataset-eval | 50-query golden dataset, eval-harness grading against LangSmith traces, cost tracking dashboard | Yes | 2+ | No (dataset file, eval code, dashboard separate) |
| 6.0 | phase/6.0-rate-limit-concurrency | Per-layer throttling, concurrency queue strategy, 20-call-per-query budget | Yes | 2+ | Yes (shared rate-limiter/harness module) |
| 6.1 | phase/6.1-hardening-release | Full dev-standards six-lens pass, CI/CD gates finalized, security-scan milestone, accessibility pass | Yes | 2+ | No (spans CI config, frontend a11y, security process) |
| 7.0 | phase/7.0-model-bench | Benchmark candidate models per tier against golden dataset, pick tier winners | Yes | 2+ | No (separate benchmark run per tier) |
| 7.1 | phase/7.1-ab-mechanism | Online A/B randomized-routing mechanism across orchestrator-plus-planner combinations | Yes | 1 | No |

### Still-open flags

From the Technical specification's Section 25 "Flags carried into this build order" table (lines 3297 to 3304), items marked still open:

- Domain sign-off for the golden fixtures: the playbook flags this as a real gap on clinical and human-variation questions, tagged a Phase 4 process item. Still open, needs a named owner before build phase 5.1 ships the 50-query golden dataset. This is the same gap as D5-33 above.
- Stale pull request template: .github/pull_request_template.md still lists BioLink and KGX validation gates from the System 1 and System 2 template repo. Still open, out of this build order's scope, belongs to Phase 5 Step 5.3 (root document updates).

## Slice 6: PRD

Source: phase5_demand_06_prd.md, extracted from requirements/PRD.md. 45 rows.

| # | PRD section | Obligation (one imperative line) | Type | Candidate owner | PRD line |
|---|---|---|---|---|---|
| D6-01 | Success metrics | G3 answers must be scored on the 8-point rubric with cite-or-refuse enforced before shipping | test | eval-harness | 75 |
| D6-02 | Success metrics | Every answer must pass cite-or-refuse (claim tied to a resolvable source, or an honest refusal) to count toward the trust metric | security | production-standards | 81 |
| D6-03 | Success metrics | The offline competency-question gate must run before any answer-generation feature ships | test | eval-harness | 83 |
| D6-04 | Users and personas | The system must never render a verdict for clinicians and genetic counselors, only assemble cited evidence | security | ai-security-standards | 99 |
| D6-05 | Competency questions | Ship an answer-generation feature only when all seven v1 must-pass competency questions meet their playbook targets | test | eval-harness | 119 |
| D6-06 | Competency questions | If the Phase 4 coordinate-range check fails, Q1 must move to the fast-follow set and the v1 must-pass set becomes six | scope | eval-harness? | 121 |
| D6-07 | Core user flows | The Guardrail step must reject prompt injection, block off-topic and medical-advice requests, and check rate and cost caps, with a cheap non-LLM pre-filter running before any model call | security | ai-security-standards | 135 |
| D6-08 | Core user flows | The Think step must ask one targeted clarifying question on ambiguity before querying, never guess | correctness | NONE | 136 |
| D6-09 | Core user flows | The agent must never write Cypher directly; only the cypher_query tool generates and validates Cypher internally | security | production-standards | 137 |
| D6-10 | Core user flows | The Act step must execute independent tool calls in parallel | performance | parallel-first? | 138 |
| D6-11 | Core user flows | The Write step must map each narrative marker to a verified source and strip any marker it cannot verify | security | production-standards | 139 |
| D6-12 | UI experience | Time-to-first-token must be under one second | performance | system-design-patterns | 149 |
| D6-13 | UI experience | Streaming must use typed SSE events (status, tool_result, token, citation, done) | correctness | system-design-patterns | 149 |
| D6-14 | UI experience | A stop button must be available throughout the loop so the user can abort a query at any point | correctness | system-design-patterns | 150 |
| D6-15 | UI experience | A citation the harness cannot verify must never appear as a chip | security | production-standards | 152 |
| D6-16 | Cost-control UX | Per-query cap ($0.10 starter value): on exceed, the loop must stop and show a partial cited result plus a budget note | cost | system-design-patterns | 162 |
| D6-17 | Cost-control UX | Per-user daily cap (100 queries/day starter value): once reached, new queries must be declined for the day with a clear message and a reset time | cost | system-design-patterns | 163 |
| D6-18 | Cost-control UX | System-wide daily cap ($10/day starter value): once reached, the system must pause accepting new queries and say so | cost | system-design-patterns | 164 |
| D6-19 | Cost-control UX | Per-step timeouts must inherit the latency budgets; on timeout the system must synthesize from partial results and explain what timed out | performance | system-design-patterns | 165 |
| D6-20 | Cost-control UX | Changing a cap value requires explicit user approval | process | system-design-patterns | 167 |
| D6-21 | Edge cases | Empty retrieval must return an explicit "I could not find information on this" refusal and stop, never answer from priors; this refusal path must be tested | test | production-standards | 173 |
| D6-22 | Edge cases | Partial-layer failure must synthesize from whatever responded and explain the gap; graceful degradation is mandatory | correctness | NONE | 174 |
| D6-23 | Edge cases | Suspect Layer 1 data must be corrected by falling back to the authoritative Layer 2 | correctness | system-design-patterns? | 175 |
| D6-24 | Edge cases | Guardrail rejection must be refused and, where sensible, redirected to what the system can do | security | ai-security-standards | 177 |
| D6-25 | Edge cases | Large tool result sets must be compressed before re-injection into agent context; a large result must never flood context or induce hallucination | performance | system-design-patterns | 179 |
| D6-26 | Edge cases | A citation that cannot be verified must be stripped before the user sees it; a claim that loses its citation must never ship as an uncited sentence | security | production-standards | 180 |
| D6-27 | Guardrails | The system must never give personal medical advice, diagnosis, treatment, a pathogenicity classification, or a variant prioritization | security | ai-security-standards | 186 |
| D6-28 | Guardrails | Every claim must tie to a specific retrieved source, or the system must refuse and stop | security | production-standards | 187 |
| D6-29 | Guardrails | Layer 1 access must be read-only, enforced twice independently (Cypher validator and database-client layer); no prompt may induce a write | security | ai-security-standards | 188 |
| D6-30 | Guardrails | Off-topic and non-biomedical queries must be refused and redirected by a pre-LLM guardrail before any model call | security | ai-security-standards | 189 |
| D6-31 | Guardrails | Prompt injection must be rejected at the Guardrail step; the natural-language-to-Cypher separation must prevent injected text from becoming a query | security | ai-security-standards | 190 |
| D6-32 | Guardrails | Higher-stakes answers must additionally pass a citation-substantiation check and a cross-source triangulation gate | security | production-standards | 191 |
| D6-33 | Security requirements | v1 must ship read-only enforcement, provenance integrity, cost caps and timeouts, and prompt-injection defense | security | ai-security-standards | 197 |
| D6-34 | Security requirements | All retrieved content must be treated as untrusted data for the Write step to cite, never as an instruction to act on | security | ai-security-standards | 198 |
| D6-35 | Security requirements | Secrets must live only in environment variables or a secrets manager, never in code, prompts, logs, or generated docs | security | ai-security-standards | 199 |
| D6-36 | Security requirements | No user PII may be sent to the LLM; the system must contain no PHI | security | ai-security-standards | 200 |
| D6-37 | Security requirements | Every tool and agent must follow least privilege, with schema-validated tool input and output at each hop of the loop | security | ai-security-standards | 201 |
| D6-38 | Security requirements | Every Layer 2 and Layer 3 access must be logged with its authorization | security | NONE | 202 |
| D6-39 | Accessibility and compliance | v1 must meet reasonable-effort accessibility (semantic HTML, keyboard navigation); no formal audit is required yet | correctness | production-standards? | 208 |
| D6-40 | Delivery formats | KGX export must be scoped to the existing Hetzner graph, not a full graph export | scope | file-protection? | 218 |
| D6-41 | Out of scope | No compute tools in v1: no BLAST, no sequence-similarity search, no VCF ingestion | scope | NONE | 225 |
| D6-42 | Out of scope | External non-NCBI knowledge-graph federation is out of scope for v1 | scope | NONE | 227 |
| D6-43 | Out of scope | Model distillation (fine-tuning a smaller student model) is out of scope for v1 | scope | NONE | 228 |
| D6-44 | Out of scope | The automated mining half of the online feedback loop is out of scope for v1; v1 ships capture plus manual review plus hand-promotion only | scope | NONE | 230 |
| D6-45 | Out of scope | Sub-query decomposition for deep research is out of scope until the failure rate on that query class exceeds 20 percent | scope | NONE | 232 |

### Out of scope for v1

- Compute tools: no BLAST, no sequence-similarity search, no VCF ingestion. The three execution-heavy questions (Q2, Q7, Q9) are the fast-follow set.
- Segmental-duplication overlap for Q1: deferred to the fast-follow with a UCSC source.
- External non-NCBI knowledge-graph federation: v1 federation is exactly the three data layers.
- Model distillation (fine-tuning a smaller student model): a v2 optimization, deferred until query logs stabilize.
- Fusion and ensemble model panels: a v2 triggered-escalation lever.
- The automated mining half of the online feedback loop: v1 ships capture plus manual review plus hand-promotion.
- Full Section 508 and WCAG audit, and enterprise security (IAM, session expiry, access review): the production track.
- Sub-query decomposition for deep research: the planned upgrade, triggered by a failure rate above 20 percent on that query class.

## Slice 7: Evaluation playbook

Source: phase5_demand_07_playbook.md, extracted from requirements/Evaluation_playbook.md (306 lines) and, for the coverage check sub-section, from .claude/skills/eval-harness/SKILL.md (195 lines). 32 rows in the obligations table.

| # | Playbook section | Obligation (one imperative line) | Type | Candidate owner | Line |
|---|---|---|---|---|---|
| D7-01 | What this is and why | Never render a clinical verdict (classification, prioritization, diagnosis, treatment); assemble and cite evidence only, human decides. | correctness | NONE | 39 |
| D7-02 | The moat test | Disqualify a candidate question outright if its answer cannot be cited to a source record (provenance gate). | correctness | production-standards | 49 |
| D7-03 | The moat test | Require the answer to be reproducible and verifiable given the data state at query time (determinism gate). | correctness | eval-harness? | 50 |
| D7-04 | The moat test | Run the candidate question against a panel of the strongest general tools and pass it only if none produces a correct, verifiably cited answer. | process | NONE | 54 |
| D7-05 | The moat test | Rank the moat test above persona coverage and usage frequency when selecting and tiering competency questions. | process | NONE | 43 |
| D7-06 | The moat test | Never let persona coverage or usage frequency override a weak moat score; use them only as intra-band tiebreakers. | process | NONE | 78 |
| D7-07 | The competency-question set | Cap the v1 must-pass moat set at seven questions. | scope | NONE | 100 |
| D7-08 | The competency-question set | If the Step 4.0 interval-overlap check fails, drop Q1 to fast-follow and reduce the cap to six. | process | NONE | 114 |
| D7-09 | The competency-question set | Run no compute tools in v1 (no BLAST, no sequence similarity, no VCF ingestion). | scope | NONE | 127 |
| D7-10 | The competency-question set | Re-score the expansion pool against the moat bar only at growth time, routing each question to Tier 1, Tier 2 should-pass, or handled-outside-eval-set by outcome. | process | NONE | 135 |
| D7-11 | The coverage metric | Never treat the coverage metric as a shipping gate; use it only as a diagnostic. | process | NONE | 142 |
| D7-12 | The coverage metric | Compute coverage against a fixed denominator: 10 concept labels and 14 edge predicates. | metric | NONE | 146 |
| D7-13 | The coverage metric | Report concept coverage and predicate coverage as two separate ratios, not a blended score. | metric | NONE | 148 |
| D7-14 | The offline evaluation gate | Run the offline gate, graded with the eval-harness skill, before any answer-generation feature ships. | process | eval-harness | 163 |
| D7-15 | The offline evaluation gate | Require a rubric score of at least 13 of 16 to pass a run. | metric | eval-harness | 180 |
| D7-16 | The offline evaluation gate | Fail the gate on any single hard-fail, regardless of total rubric score. | correctness | production-standards | 184 |
| D7-17 | The offline evaluation gate | Hard-fail a run when provenance scores 0 (a claim with no source). | correctness | production-standards | 186 |
| D7-18 | The offline evaluation gate | Hard-fail a run when safety-and-limits scores 0 on a clinical or pathogenicity question (a rendered verdict). | correctness | production-standards? | 187 |
| D7-19 | The offline evaluation gate | Hard-fail a run that is missing assembly or version context on a coordinate or sequence question. | correctness | production-standards? | 188 |
| D7-20 | The offline evaluation gate | Score zero retrieval plus a correct refusal string as pass, never as fail. | correctness | eval-harness | 190 |
| D7-21 | The offline evaluation gate | Grade every run into exactly one outcome: pass (>=13/16, no hard-fail), fail (hard-fail or <13), or abstain (refusal string returned). | metric | eval-harness | 196 |
| D7-22 | The offline evaluation gate | Hold hard-fails at pass^k = 100 percent on every run for a must-pass moat question. | metric | eval-harness | 201 |
| D7-23 | The offline evaluation gate | Meet pass@3 as the quality floor and pass^3 at least 90 percent as the reliability target for a must-pass moat question. | metric | eval-harness | 202 |
| D7-24 | The offline evaluation gate | Run the eval against pinned fixtures, with a freshness-window allowance for live-API questions. | test | eval-harness? | 208 |
| D7-25 | The offline evaluation gate | Measure every acceptance-criteria table against the fixed golden/moat query set. | scope | eval-harness | 209 |
| D7-26 | The offline evaluation gate | Keep ACMG classification out of scope; evidence assembly only. | scope | NONE | 213 |
| D7-27 | The offline evaluation gate | Keep live BLAST and SRA sequence search out of scope for v1 (fast-follow with fixtures). | scope | NONE | 214 |
| D7-28 | The offline evaluation gate | Keep dbGaP controlled-access flows out of scope for Tier 1; the seven are public-data only. | scope | NONE | 215 |
| D7-29 | The online feedback loop | Require a human to approve every candidate question before it is promoted (human gate on routing changes). | process | ai-security-standards? | 244 |
| D7-30 | The online feedback loop | Require promotion to be both human-approved and provenance-gated. | process | ai-security-standards? | 246 |
| D7-31 | The online feedback loop | Never store secrets in the loop's captured interaction data. | process | ai-security-standards | 269 |
| D7-32 | The online feedback loop | Grade offline eval runs in order: code graders first, then the LLM-judge, then a human only on flagged edge cases. | process | eval-harness | 275 |

Row count confirmed against the source file's own tally: 32 rows total, 14 marked NONE (D7-01, D7-04, D7-05, D7-06, D7-07, D7-08, D7-09, D7-10, D7-11, D7-12, D7-13, D7-26, D7-27, D7-28).

### The must-pass set

The v1 must-pass moat set is capped at seven questions (playbook line 100). Question text quoted from the "Question (short)" column of the table at playbook lines 102 to 110. Q1 is conditional: if the Step 4.0 interval-overlap check fails, it drops to fast-follow and the cap becomes six (line 114).

- Q1: CNV region to cited ACMG-relevant evidence (dbVar, ClinVar, genes, OMIM, Variation Viewer). Assembles evidence, no classification. Wedge type: gene-variant-literature. Personas: 3, 8, 10.
- Q3: BRCA1 to Gene, PubMed, ClinVar, GTR, MedGen in one answer. Wedge type: gene-variant-literature. Personas: 1, 3, 8, 10, 11.
- Q4: Disease phrase to routed cross-database queries (MedGen, ClinVar, GTR, PubMed, ClinicalTrials, Gene). Wedge type: gene-variant-literature. Personas: 1, 3, 8, 10.
- Q5: Salmonella isolate to SNP cluster, AMR genes, BioSample, neighbors within 5 SNPs. Wedge type: pathogen-sequence-outbreak. Personas: 6, 4, 10.
- Q6: Natural-language SRA metadata search with match rationale. Wedge type: pathogen-sequence-outbreak. Personas: 6, 2, 11.
- Q8: PMID to linked SRA, BioProject, GEO, assembly, PubChem, marking direct, inferred, or absent. Wedge type: paper-data-tool. Personas: 1, 4, 10, 11.
- Q10: BioProject to BioSamples, SRA runs, assembly bundle with retrieval path. Wedge type: paper-data-tool. Personas: 4, 6, 10, 11.

### Eval-harness coverage check

Source: .claude/skills/eval-harness/SKILL.md, read in full (195 lines) and checked against every playbook demand.

| Playbook demand | Does eval-harness/SKILL.md cover it? | Evidence (quote with line number, or "absent") |
|---|---|---|
| pass@k and pass^k metric definitions | Yes | Line 31: "At least 1 of k generated samples passes all tests." Line 41: "All k samples must pass. Higher bar for critical paths." |
| pass/fail/abstain outcome model, abstain scored by whether a correct source existed | Yes | Lines 60-63: "pass: the agent answered correctly, tied to a real retrieved source... fail, wrong answer: the agent answered from priors or fabricated a citation... abstain: the agent returned 'I could not find information on this' and stopped." Lines 65-67 give the exact scoring rule for when abstain counts as pass versus fail. |
| The 8-point rubric (intent understanding through output usability) and the 13-of-16 pass threshold | No | Absent. The skill has no rubric criteria list and no "13" or "16" threshold anywhere in the file. |
| Hard-fail conditions (provenance = 0, safety-and-limits = 0 on a clinical question, missing assembly or version context) that fail a run regardless of score | No | Absent as a named "hard-fail" concept. Partial adjacency only: line 130 has "Cite-or-refuse compliance" and line 133 "Provenance completeness" as citation-synthesizer criteria, but neither is framed as an automatic fail-regardless-of-score, and there is no criterion for a clinical-verdict fail or a missing-assembly/version fail. |
| The coverage metric (concept coverage and predicate coverage ratios against the graph schema) | No | Absent. No mention of "coverage," "concept," or "predicate" anywhere in the file. |
| The moat test (empirical general-tool-panel test for no-general-tool-equivalent scoring) | No | Absent. No mention of "moat," "general tool," or a comparison panel anywhere in the file. |
| The v1 must-pass set of seven named competency questions (Q1, Q3, Q4, Q5, Q6, Q8, Q10) | No | Absent. The skill references only the generic "Phase 4 golden dataset of 50 queries" (line 183), never the seven-question moat set or its identifiers. |
| Golden dataset of 50 queries as the fixed query set every acceptance-criteria table measures against | Yes | Line 183: "The golden dataset of 50 queries is the fixed query set every acceptance-criteria table above measures against." |
| Model-selection method (model-bench offline leaderboard, A/B testing online) | No | Absent. No mention of "model-bench," "leaderboard," or "A/B" anywhere in the file. |
| The online feedback loop (capture, mine and cluster, review, trigger, promote stages) | No | Absent. None of these five stage names appear in the file. |
| Human gate required before promoting a new competency question or routing change | No | Absent. The file has no promotion workflow and no human-approval-gate language for routing changes. |
| Data storage split (Postgres system-of-record, LangSmith raw traces, PostHog behavioral analytics) | No | Absent as a storage-split concept. Only a narrow, tangential mention of LangSmith exists at line 186: "LangSmith tracing gives the raw hop-by-hop data... that the graders above consume," with no mention of Postgres or PostHog anywhere in the file. |
| Determinism via pinned fixtures with a freshness-window allowance for live-API questions | No | Absent. No mention of "pinned," "fixture," or "freshness" anywhere in the file. |
| Offline eval grading order: code graders first, then the LLM-judge, then a human only on flagged edge cases | Yes | Line 172: "Run each sample through graders, code first, then model, then human." |
| Cite-or-refuse and citation coverage as pass/fail acceptance criteria measured before any answer-generation feature ships | Yes | Line 24: "Before shipping any answer-generation feature: verify cite-or-refuse and citation-coverage targets are met." Line 184: "Cite-or-refuse and citation coverage are pass/fail acceptance criteria, measured with pass@k against that fixed query set, before any answer-generation feature ships. This is not optional polish, it is the gate." |
| Never store secrets captured by the online loop | No | Absent. The file has no secrets-handling language at all; cost tracking is mentioned (line 185) but not secrets or privacy. |
| Assemble-evidence-not-verdict boundary (never render a clinical verdict) | No | Absent. No mention of "clinical," "verdict," "diagnosis," or "classification" anywhere in the file. |

## Obligations with no owner

Every row across all seven slices whose candidate owner is the literal value NONE, 57 rows total, grouped by the theme Phase 5 routed it to. Where a row plausibly fit two themes, it appears under the one best match only.

### Per-call timeouts, rate limits, and queue depth

Now owned by .claude/rules/tool-call-budgets.md. 13 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D2-16 | Technical specification 6.1 | cypher_query must enforce a 30 second per-call timeout | 803 |
| D2-22 | Technical specification 6.2 | ncbi_efetch must enforce a 15 second per-call timeout with one backoff retry on transient failure | 984 |
| D2-28 | Technical specification 6.3 | ncbi_dbsnp must enforce a 15 second per-call timeout and budget up to 30 seconds worst case for one invocation | 1076 |
| D2-29 | Technical specification 6.3 | The tool must respect the Variation Services rate limit of roughly 1 request per second, a separate pool from E-utilities | 1078 |
| D2-32 | Technical specification 6.4 | pubtator_annotate must enforce a 15 second per-call timeout | 1180 |
| D2-36 | Technical specification 6.5 | litvar2_lookup must enforce a 15 second per-call timeout | 1257 |
| D2-39 | Technical specification 6.6 | pathogen_detection must enforce a per-call timeout of 60 seconds or more | 1358 |
| D2-43 | Technical specification 6.7 | clinicaltrials_search must enforce a 15 second per-call timeout with a provisional throttle of about 5 requests per second | 1435 |
| D5-02 | Technical specification 21.1 | Confirm which E-utilities rate-limit figure (3/10 vs 100 requests/second) is authoritative before locking throttle constants into code for the Phase 6 build | 2885 |
| D5-03 | Technical specification 21.1 | Apply a provisional throttle of about 5 requests/second to the Datasets API v2 and each of the four enrichment APIs until a published rate limit is confirmed | 2887 |
| D5-05 | Technical specification 21.4 | Cap each API family's wait queue depth at roughly 15 to 30 calls and tie a queued call's wait ceiling to the query's remaining latency budget; a call that would exceed either must fail fast with an actionable rate_limited error | 2906-2907 |
| D5-28 | Technical specification 23 | Live Layer 2 and Layer 3 integration tests must run at a pace respecting each API's verified rate limit so the integration job never trips a rate limit itself | 3031 |
| D5-43 | Technical specification 24 | The HTTPS graph query service must enforce a hard row limit, a per-call timeout matching the tool's own budget, and a rate limit per caller | 3154 |

### Prompt-cache discipline

Now owned by .claude/rules/prompt-cache-discipline.md. 2 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D1-27 | Technical specification 4.2 | The tool list must never change mid-session, the model per tier must never switch mid-query, and no timestamp, request id, or volatile token may sit in the stable prompt-cache prefix. | 587 |
| D1-28 | Technical specification 4.2 | Tool schemas in the prompt-cache prefix must be sorted alphabetically and fixed in code, never re-ordered at runtime. | 576 |

### v1 scope boundary

Now owned by .claude/rules/v1-scope-boundary.md. 11 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D6-41 | PRD, out of scope | No compute tools in v1: no BLAST, no sequence-similarity search, no VCF ingestion | 225 |
| D6-42 | PRD, out of scope | External non-NCBI knowledge-graph federation is out of scope for v1 | 227 |
| D6-43 | PRD, out of scope | Model distillation (fine-tuning a smaller student model) is out of scope for v1 | 228 |
| D6-44 | PRD, out of scope | The automated mining half of the online feedback loop is out of scope for v1; v1 ships capture plus manual review plus hand-promotion only | 230 |
| D6-45 | PRD, out of scope | Sub-query decomposition for deep research is out of scope until the failure rate on that query class exceeds 20 percent | 232 |
| D7-07 | Evaluation playbook, competency-question set | Cap the v1 must-pass moat set at seven questions. | 100 |
| D7-08 | Evaluation playbook, competency-question set | If the Step 4.0 interval-overlap check fails, drop Q1 to fast-follow and reduce the cap to six. | 114 |
| D7-09 | Evaluation playbook, competency-question set | Run no compute tools in v1 (no BLAST, no sequence similarity, no VCF ingestion). | 127 |
| D7-26 | Evaluation playbook, offline evaluation gate | Keep ACMG classification out of scope; evidence assembly only. | 213 |
| D7-27 | Evaluation playbook, offline evaluation gate | Keep live BLAST and SRA sequence search out of scope for v1 (fast-follow with fixtures). | 214 |
| D7-28 | Evaluation playbook, offline evaluation gate | Keep dbGaP controlled-access flows out of scope for Tier 1; the seven are public-data only. | 215 |

### Cross-layer authority, freshness, observability, and degradation

Now folded into .claude/rules/production-standards.md. 7 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D3-01 | Technical specification 7.1 | State the live Layer 2 or Layer 3 value, never the graph value, as current whenever both were fetched for the same answer | 1478 |
| D3-05 | Technical specification 7.4 | Auto-cross-verify a volatile Layer 1 field against a live Layer 2 call before citing it as current once its graph snapshot exceeds the 30-day (volatile class) or 90-day (stable class) staleness threshold | 1547 |
| D4-47 | Technical specification 20.3 | The tool-call audit log must be append-only, never mutated after write, with one writer per process. | 2863 |
| D4-48 | Technical specification 20.1 | trace_id must be minted at the Guardrail step and thread through every event, LiteLLM call, and tool call as the single join key. | 2849 |
| D5-09 | Technical specification 22.1 | On suspect Layer 1 data, fall back to Layer 2 as the authoritative source and correct the answer; surface the correction to the user only if it also leaves the answer incomplete | 2935 |
| D6-22 | PRD, edge cases | Partial-layer failure must synthesize from whatever responded and explain the gap; graceful degradation is mandatory | 174 |
| D6-38 | PRD, security requirements | Every Layer 2 and Layer 3 access must be logged with its authorization | 202 |

### Contract and harness discipline

Now folded into .claude/rules/system-design-patterns.md. 9 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D1-18 | Technical specification 2.6 | Within v1, contract changes must be additive only; a breaking change requires a v2 contract. | 393 |
| D1-19 | Technical specification 2.6 | A tool-registry change (add or remove a tool) must be coordinated with a contract-version bump, never silent. | 395 |
| D1-24 | Technical specification 3.5 | When a failure recurs, the harness must be iterated first and the model swap tried second. | 540 |
| D1-26 | Technical specification 3.3 | resolve_model() must never hardcode a model id; model identity is resolved only from env-configured tier values. | 461 |
| D2-24 | Technical specification 6.2 | Pathogen Detection and ClinicalTrials.gov must never be folded into ncbi_efetch as extra actions, each gets its own named tool | 988 |
| D4-31 | Technical specification 17 | The few-shot pool must load once at process start from a versioned file, never as a live database read on every request. | 2650 |
| D4-32 | Technical specification 17 | Think must resolve a recognizable exact identifier as ground truth before any fuzzy matching runs. | 2719 |
| D6-08 | PRD, core user flows | The Think step must ask one targeted clarifying question on ambiguity before querying, never guess | 136 |
| D7-01 | Evaluation playbook, what this is and why | Never render a clinical verdict (classification, prioritization, diagnosis, treatment); assemble and cite evidence only, human decides. | 39 |

### Per-tool API mechanics

Now documented in docs/Tool_implementation_mechanics.md. 5 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D2-13 | Technical specification 6.1 | Every Cypher query must use an explicit edge label, never an untyped relationship pattern | 794 |
| D2-18 | Technical specification 6.2 | The link action must always specify an explicit target db, never rely on the ELink default | 858 |
| D2-25 | Technical specification 6.3 | The tool must read frequency data only from the global_mafs array, the flat global_maf scalar is verified null and must never be read | 1072 |
| D2-27 | Technical specification 6.3 | Variation Services normalization and the dbSNP ESummary clinical fetch must run sequentially, never in parallel, within one tool invocation | 1076 |
| D2-37 | Technical specification 6.6 | The tool must resolve and pin only to the latest COMPLETE snapshot with Metadata, Clusters, and AMR directories all present, never a mid-build snapshot | 1348 |

### Still open, needing a human decision or Phase 6 action

10 rows.

| ID | Source | Obligation | Line |
|---|---|---|---|
| D2-33 | Technical specification 6.4 | The PubTator3 relations endpoint must not ship until its path and fields are live-verified | 1174 |
| D5-29 | Technical specification 23 | The dbVar two-step tool needs its own integration test asserting the placement post-filter removes cross-assembly false positives | 3033 |
| D5-33 | Technical specification 23 | Domain sign-off for the clinical and human-variation golden fixtures needs a named owner before build phase 5.1 ships the 50-query golden dataset | 3044 |
| D7-04 | Evaluation playbook, the moat test | Run the candidate question against a panel of the strongest general tools and pass it only if none produces a correct, verifiably cited answer. | 54 |
| D7-05 | Evaluation playbook, the moat test | Rank the moat test above persona coverage and usage frequency when selecting and tiering competency questions. | 43 |
| D7-06 | Evaluation playbook, the moat test | Never let persona coverage or usage frequency override a weak moat score; use them only as intra-band tiebreakers. | 78 |
| D7-10 | Evaluation playbook, competency-question set | Re-score the expansion pool against the moat bar only at growth time, routing each question to Tier 1, Tier 2 should-pass, or handled-outside-eval-set by outcome. | 135 |
| D7-11 | Evaluation playbook, the coverage metric | Never treat the coverage metric as a shipping gate; use it only as a diagnostic. | 142 |
| D7-12 | Evaluation playbook, the coverage metric | Compute coverage against a fixed denominator: 10 concept labels and 14 edge predicates. | 146 |
| D7-13 | Evaluation playbook, the coverage metric | Report concept coverage and predicate coverage as two separate ratios, not a blended score. | 148 |

## Cross-tool contract

Reproduced verbatim from phase5_demand_02_section_6_tools.md. Every one of the seven tools (cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search) must satisfy all ten.

- Every tool schema must enforce maxLength on every string, maxItems on every array, a host-pinned source_url regex, and no additionalProperties (line 714).
- Every tool must act as a read-plus-one-source reader that calls only its own source, never another tool, never a write path (line 714).
- Every source_url pattern must use the strict host-pinned regex from Section 9.3, never the looser any-subdomain form (line 716).
- A citation must always resolve to the human-facing record page, never the eutils or api fetch host the tool actually called (line 716).
- Untrusted free text fields returned by any Layer 2 or 3 source must never be treated as an instruction, only as data for an isolated reader pass before Synth (line 1178).
- A zero-result response must map to status empty, not error, and act as the cite-or-refuse trigger for that layer (line 798).
- Every tool must enforce its own specified per-call timeout (line 1451).
- Every tool call is subject to the shared per-user and per-query cost budget in Section 21 (line 986).
- A tool must never inline a full large result set into agent context, it must truncate and report the total available count (line 800).
- Any API key must be passed via environment variable only, never hardcoded or logged (line 986).
