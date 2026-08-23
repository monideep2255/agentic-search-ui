# Build phase 4.7 re-verification report, round 2

Branch: `phase/4.7-cq-routing`
Range reviewed: `b3d030e..HEAD` (HEAD = `4a64c12`)
Date: 2026-08-23
Role: re-verifier, read-only on `src/` and `tests/`. Nothing under `src/`, `tests/` or `frontend/` was modified by this round. Every mutation below was applied in-process, by monkeypatching from scripts held outside the repository, never by editing a tracked file.

## Verdict: FAIL

Three MAJOR findings, all reachable, all filed against the phase's own verify surface rather than against its product code.

| ID | Severity | Where | Blocks |
|----|----------|-------|--------|
| F-4.7-R2-01 | MAJOR | `tests/system_03_search_agent/core/test_cq_routing_premise.py:900-914` (P12b) | YES |
| F-4.7-R2-02 | MAJOR | `tests/system_03_search_agent/core/test_cq_routing_premise.py:441` (P1) | YES |
| F-4.7-R2-03 | MAJOR | `tests/system_03_search_agent/core/test_graph.py:2234-2263`, root cause `src/system_03_search_agent/core/graph.py:1082-1091` | YES |
| F-4.7-R2-04 | MAJOR, latent | `src/system_03_search_agent/core/graph.py:2179-2187`, reached via `src/system_03_search_agent/core/run.py:392-407` | NO, see the finding |
| F-4.7-R2-05 to F-4.7-R2-09 | MINOR | listed below | NO |

The good news first, and it is measured rather than assumed: the round 1 CRITICAL is genuinely fixed. P1's four cases all go RED under the exact defect the arm names, where before the fix all four stayed GREEN. `4a64c12`'s central claim holds. What fails this round is different work: one gate arm that cannot fail at all, one gate arm whose assertion is narrower than the property it names, and two live controls whose only tests were deleted during this phase's retirement sweep.

### Rule 4 was considered and NOT triggered

Stated explicitly, because one finding sits close to the line. F-4.7-R2-04 falsifies a claim made in `4a64c12`'s commit message, but the defect it names is in `plan_node`, which `4a64c12` did not touch, and which has behaved this way since build phase 4.5 (verified against `b3d030e:core/graph.py:1958-1973`). A pre-existing defect that a fix declined to fix is not a defect inside the fix. The three blocking findings are all in code written at `2b6f01d` (the original gate) or in the `d9b5235` test-retirement commit, neither of which is a fix for a finding filed in this phase. Verified: `e79741d` touched only P1 and the question constants (`git show e79741d --stat`), and `4a64c12` touched only `core/graph.py` plus tracker files.

---

## Task 1: the mutation sweep, every arm

Method. Offline arms were invoked directly with their real bodies, against the real modules, with one target monkeypatched per mutation. Live arms (`@premise_gate`) were driven through the REAL `core.run.run()` loop end to end, with `litellm.acompletion` replaced by a controllable stand-in that answers Guard, Think and Synth per tier, `resolve_symbol_to_curie` replaced by a fixed map, and both `httpx` transports hard-blocked so a leaked outbound call would raise rather than pass. That exercises `think_node`, `plan_node`, `act_node` and `write_node` for real; only the model's own words are mine. Zero live model calls were spent.

The question asked of every arm is the one round 1's CRITICAL turned on: can the value the assertion reads ever take the value that would make it fail?

| Arm | Property it claims to protect | Mutation applied | Observed |
|-----|-------------------------------|------------------|----------|
| P1, Q4 `GTR` | a database name mentioned in passing is not resolved as an entity of the question | model extracts `GTR` as a gene and the live lookup confirms it | **RED** `Q4 Lynch syndrome: 'GTR' is a database name mentioned in passing, and it was resolved as an entity of the question. This is F-2.0-15 exactly. Resolved: ['GTR']` |
| P1, Q4 `GTR` | the question is not refused with the unresolved-gene refusal | model extracts `GTR`, live lookup returns `None` | **RED** `refused with the unresolved-gene refusal` |
| P1, Q5 `AMR` | as above | same two | **RED**, **RED** (`Resolved: ['AMR']`) |
| P1, Q6 `SRA` | as above | same two | **RED**, **RED** (`Resolved: ['SRA']`) |
| P1, Q10 `SRA` | as above | same two | **RED**, **RED** (`Resolved: ['SRA']`) |
| P1, all four | *the same property, when the model returns a WIDER span* | model extracts `"SRA runs"` / `"SRA metadata"` / `"sra"` as a gene and it resolves | **GREEN, GREEN, GREEN** -> F-4.7-R2-02 |
| P2 | the flagship question's subject resolves to an `NCBIGene:` CURIE from raw text | model extracts nothing | **RED** `the flagship question names BRCA1 explicitly and resolved nothing` |
| P2 | as above | `BRCA1` resolves to `HGNC:1100`, not an `NCBIGene:` CURIE | **RED** `BRCA1 must resolve to an NCBIGene CURIE, got ['HGNC:1100']` |
| P2, line 3 | `query_class` is one of Section 17's five shapes | *unfalsifiable*: `ThinkPayload.query_class` is a validated `Literal` (`contracts/events.py:124-126`) | GREEN under every reachable input. Structural guard only; P2's two real assertions above are sound |
| P3 | a multi-database coordinate question is not classified `lookup` | classifier returns the stub literal `"lookup"` | **RED** `...classified as 'lookup', whose Section 17 budget is 5 seconds and one live API call. This is the stub's value surviving under a new name` |
| P4 | classification is not a constant | classifier returns the constant `"exploratory"` | **RED** `a one-gene graph traversal and a PMID cross-link resolution both classified as 'exploratory'` |
| P4 | as above | constant `"lookup"`; constant `"multi_hop"` | **RED**, **RED** |
| P5 | the exact-ID pre-pass resolves an rsID and a PMID with no model call | pre-pass returns `[]` | **RED** `the pre-pass resolved nothing from a string containing both an rsID and a PMID, so the zero-model-call assertion below would pass vacuously` |
| P5 | as above | rsID rule removed from the pre-pass | **RED** `rsID not resolved, got {'PMID 21376230'}` |
| P5 | the pre-pass is local and deterministic, never async | resolver replaced by an `async def` carrying `is_async=True` | fails, but as `TypeError: 'coroutine' object is not iterable` at the populate-check, not at the `is_async` assertion |
| P5 | as above | `is_async=True` set on the REAL sync resolver | **RED** `the exact-ID pre-pass must be deterministic and local` — the assertion is falsifiable |
| P6 | no CURIE is fabricated for a gene-shaped token NCBI does not know | confirmation removed, CURIE built from the symbol (`NCBIGene:ZZZX9Q`) | **RED** `a CURIE was fabricated for a gene symbol that does not exist: ['NCBIGene:ZZZX9Q']` |
| P6 | every returned value is in `prefix:local_id` form | resolution returns the bare string `"672"` | **RED** `'672' is not in prefix:local_id CURIE form` |
| P6 | *the same property, fabricated to a plausible CURIE* | confirmation removed, `ZZZX9Q` fabricated to `NCBIGene:672` | **GREEN** -> F-4.7-R2-05 |
| P6 | *the arm's own premise* | model extracts NOTHING at all, so nothing is ever attempted | **GREEN** -> F-4.7-R2-05, no populate-check |
| P7 | the retired stopword list is gone with no fallback | `_SYMBOL_CANDIDATE_STOPWORDS` re-attached to `core.graph` | **RED** `'_SYMBOL_CANDIDATE_STOPWORDS' is still present in core.graph` |
| P7 | the retired token pattern is gone | `_GENE_SYMBOL_TOKEN_PATTERN` re-attached | **RED** `'_GENE_SYMBOL_TOKEN_PATTERN' is still present in core.graph` |
| P8 | the pool holds the seven must-pass questions | pool truncated to six | **RED** `expected the seven v1 must-pass moat questions, found 6` |
| P8 | every entry's class is a Section 17 shape | one entry's `query_class` set to `"bogus_shape"` | **RED** `'bogus_shape' is not one of Section 17's five shapes` |
| P8 | every entry has a `query_pattern` | one entry's `query_pattern` emptied | **RED** `an example with no query_pattern` |
| P8 | every entry's route names a tool | one entry's `route.tools` emptied | **RED** `an example whose route names no tool` |
| P9 | the pool file is read at most once per process | loader re-reads the file on every call | **RED** `the pool file was read 7 times across six calls` |
| P9 | *and at least once* (the populate-check) | loader returns `[]` and never touches disk | **RED** `the loader returned an empty pool, so nothing is being counted` |
| P10 | the stable prefix is byte-identical across assemblies | a fresh `request_id=<uuid>` appended to the prefix | **RED** `the stable prefix is not byte-identical across two assemblies` |
| P10 | as above | a `time.time()` timestamp appended to the prefix | **RED**, same message |
| P10 | *and the pool is actually in it* (the populate-check) | pool content stripped out of the assembled prefix | **RED** `the few-shot pool is not in the stable prefix at all, so the byte-equality assertion below would hold trivially` |
| P11 | two concurrent promotions cannot lose an entry or corrupt the file | writer replaced by an unlocked read-modify-write | **RED** 3 of 3 runs: `a concurrent promotion lost an entry: {'pattern 1'}` / `{'pattern 2'}` / `{'pattern 2'}` |
| P11 | as above | writer replaced by an atomic `os.replace` with NO lock (the "atomicity is enough" belief) | **RED** 3 of 3 runs, two as lost entries and one as `FileNotFoundError` |
| P12 | the interactions row's class equals the class the loop routed on | assembler hardcodes `"lookup"` again | **RED** `the interactions row recorded 'lookup' while the loop actually routed on 'multi_hop'` |
| P12 | *a row was produced at all* (the populate-check) | assembler returns `None` | **RED** `the assembler produced no row for a completed run` |
| P12b | "the class selects a real Act budget", and the graph tool's timeout is still a floor under it | `budget_for_step` returns `0.001` for every class | **GREEN** |
| P12b | as above | `budget_for_step` returns `-1.0` | **GREEN** |
| P12b | as above | `CYPHER_QUERY_TIMEOUT_SECONDS` set to `0.0`, destroying the floor | **GREEN** |
| P12b | *the populate-check*, that a real class was produced | *unfalsifiable*: validated `Literal` at two layers | **GREEN** under every reachable input |

Twelve of the thirteen arms are falsifiable and were watched RED under a mutation of the property they name. P12b is not, on any line.

### F-4.7-R2-01, MAJOR: P12b is a vacuous gate arm

`tests/system_03_search_agent/core/test_cq_routing_premise.py:907-914`:

```python
    act_budget = max(
        budget_for_step("act", _class_of(payload)), CYPHER_QUERY_TIMEOUT_SECONDS
    )
    assert act_budget >= CYPHER_QUERY_TIMEOUT_SECONDS, (
        "the graph tool's own 30 second timeout is no longer a floor under "
        ...
```

The arm computes `max(b, C)` itself and then asserts `max(b, C) >= C`. That is a mathematical identity, not a measurement. It holds for every real value of `b`:

```
   budget_for_step -> -1.0          max(b, 90.0) = 90.0      >= 90.0 ? True
   budget_for_step -> 0.0           max(b, 90.0) = 90.0      >= 90.0 ? True
   budget_for_step -> 0.001         max(b, 90.0) = 90.0      >= 90.0 ? True
   budget_for_step -> 5.0           max(b, 90.0) = 90.0      >= 90.0 ? True
   budget_for_step -> 30.0          max(b, 90.0) = 90.0      >= 90.0 ? True
   budget_for_step -> 120.0         max(b, 90.0) = 120.0     >= 90.0 ? True
   budget_for_step -> nan           max(b, 90.0) = nan       >= 90.0 ? False
```

Only `nan` falsifies it, and no code path produces `nan`: `_QUERY_CLASS_BUDGET_S` (`harness/harness.py:350-356`) is five float literals.

The property the arm's docstring names lives at `src/system_03_search_agent/core/graph.py:2514`:

```python
act_timeout_s = max(budget_for_step("act", query_class), CYPHER_QUERY_TIMEOUT_SECONDS)
```

The arm never reads that line, never runs `act_node`, and never inspects the timeout `act_node` actually used. Deleting the `max()` from `graph.py:2514` outright leaves P12b GREEN, which was mutation-confirmed: setting `CYPHER_QUERY_TIMEOUT_SECONDS` to `0.0` and running the arm through the real loop returned GREEN.

The arm's populate-check does not rescue it either. `assert _class_of(payload) in SECTION_17_SHAPES` reads `ThinkPayload.query_class`, which is a `Literal` validated at two independent layers, `_ThinkClassification.query_class` (`core/graph.py:920`) and `ThinkPayload.query_class` (`contracts/events.py:124-126`). Measured:

```
  ThinkPayload REJECTED query_class='bogus_shape' at construction:
    1 validation error for ThinkPayload query_class Input should be 'lookup',
    'single_hop', 'multi_hop', 'aggregate' or 'exploratory'
  => `_class_of(payload) in SECTION_17_SHAPES` can NEVER be False in an emitted think event.
```

So neither of P12b's two assertions can fail. It is inert on every line, it costs a live model call on every gate run, and it is one of the sixteen passes the phase reports as its evidence. This is the third vacuous-arm finding in this phase and the same shape as round 1's CRITICAL: an assertion reading a value whose codomain excludes the failing value.

Owner note, not a directive: an arm that graded this property would have to read what `act_node` actually used, for example by asserting `act_node`'s dispatch timeout for a `lookup`-classified query is at least `CYPHER_QUERY_TIMEOUT_SECONDS` after mutating `_QUERY_CLASS_BUDGET_S["lookup"]` down.

### F-4.7-R2-02, MAJOR: P1 asserts exact list membership where the property is containment

`test_cq_routing_premise.py:441`:

```python
    resolved = _resolved_texts(payload)
    assert passing_mention not in resolved, (
```

`resolved` is a `list[str]`, so `in` is exact element equality, not substring containment. The arm therefore catches the defect only when the model's extracted span is byte-identical to the bare token. Driven through the real loop with the database name genuinely resolved as a gene:

```
[GREEN] P1 Q6, DB name resolved but the extracted span is 'SRA runs'
[GREEN] P1 Q6, DB name resolved but the extracted span is 'SRA metadata'
[RED  ] P1 Q6, DB name resolved but the extracted span is ' SRA'
[GREEN] P1 Q6, DB name resolved but the extracted span is 'sra'
```

In three of those four the database name WAS taken as the subject of the question and the arm reported the control holding. The live gate runs against a real model whose span choice is not pinned by anything, and `"SRA runs"` is at least as natural an extraction from Q6's text (`"Find SRA runs from stool samples..."`) as the bare token is. This is not a hypothetical escape route, it is the likelier one.

This matters more than an ordinary narrowing because P1 is the arm the phase's own tracker calls "the phase's reason to exist", and because the round 1 CRITICAL was closed specifically by making this assertion able to see the surface form. Making it able to see the surface form and then comparing that surface form by exact equality recovers only part of the coverage the fix was supposed to buy.

The same narrowing does not affect P6's `"ZZZX9Q" in curie`, which is a substring test.

### F-4.7-R2-03, MAJOR: two live controls lost their only tests in the retirement sweep

`tests/system_03_search_agent/core/test_graph.py:2234-2263` retires a cluster of tests with a stated reason, which is the right form. The reason is wrong on two of them. It says the retired mechanism's own behaviour included "how the live-lookup budget sliced the candidate list". That slicing is not retired. It moved, verbatim, into the new code:

```python
# src/system_03_search_agent/core/graph.py:1082-1091
    for entity in entities:
        if entity.entity_type != "gene":
            continue
        if entity.text in seen_symbols:      # ADV-FIX2-8's de-duplication
            continue
        seen_symbols.add(entity.text)
        gene_symbols.append(entity.text)

    for symbol in gene_symbols[:_MAX_LIVE_SYMBOL_LOOKUPS]:   # the ceiling, still 3
```

`_MAX_LIVE_SYMBOL_LOOKUPS = 3` is still defined at `graph.py:1376`. `_confirm_extracted_entities`'s own docstring claims the de-duplication discipline is preserved and cites the adversary finding it came from: "de-duplicated before any network call so a repeated mention never consumes more than one of the `_MAX_LIVE_SYMBOL_LOOKUPS` live-lookup slots (the same discipline the retired regex-token guess enforced, ADV-FIX2-8)".

The two tests that graded exactly those two controls were deleted in `d9b5235` and nothing replaced them:

- `test_candidate_filter_caps_live_lookups_at_the_ceiling`
- `test_a_repeated_symbol_does_not_consume_a_second_budget_slot`

```
$ grep -rn "_MAX_LIVE_SYMBOL_LOOKUPS\|_confirm_extracted_entities" tests/
tests/system_03_search_agent/core/test_graph.py:2242:# matched, how the stopword list filtered them, how the live-lookup budget
```

One comment. No test.

Measured rather than argued. Both controls were removed at runtime (`_MAX_LIVE_SYMBOL_LOOKUPS` raised to 10^6 and the `seen_symbols` de-duplication deleted from `_confirm_extracted_entities`) and the full suite was run:

```
*** MUTATION ACTIVE: no live-lookup ceiling, no repeated-symbol dedup ***
6 failed, 3757 passed, 146 skipped, 1 xfailed, 4 warnings in 78.84s
```

Byte-for-byte the unmutated baseline, the same six pre-existing `test_citation_trust_full_premise.py` failures, not one test detects it. A query whose extraction names twenty gene spans, or names the same span twenty times, now fires twenty live NCBI lookups inside one Think step with nothing to stop it. `.claude/rules/tool-call-budgets.md` owns that pacing, and `.claude/rules/goal-contracts.md` is explicit that a check removed so a suite stays green is a failed run. The retirement here was not made to hide a failure, the intent is plainly honest, but the effect is the same: a live control lost its verify surface under a reason that misdescribes it.

The rest of the retirement audit is clean, and is recorded so it is not re-derived:

| Retired test | Mechanism genuinely gone? | Evidence |
|---|---|---|
| `test_guardrail_and_think_call_the_guard_tier_model` | yes, split | replaced by `test_guardrail_alone_calls_the_guard_tier_model` and `test_think_now_calls_the_plan_tier_model` |
| `test_think_event_narrative_documents_itself_as_a_stub` | yes | the stub literal is gone; replaced by `test_think_event_carries_a_real_classification_not_the_retired_stub` |
| `test_candidate_filter_never_calls_resolution_for_stopwords` | yes | `_SYMBOL_CANDIDATE_STOPWORDS` has no definition anywhere (grep, and gate arm P7) |
| `test_corf_family_gene_symbols_are_attempted_despite_lowercase_orf` | yes | `_CORF_GENE_TOKEN_PATTERN` has no definition anywhere |
| `test_corf_and_all_caps_candidates_interleave_in_query_order` | yes | same |
| `test_candidate_filter_does_not_reresolve_a_verbatim_curie_as_a_symbol` | yes, the mechanism moved and IS covered | `resolve_exact_identifiers` claims the span first, `_build_think_messages` names it as already resolved, and `test_resolve_exact_identifiers_does_not_double_claim_an_overlapping_span` grades it |
| `test_candidate_filter_caps_live_lookups_at_the_ceiling` | **NO** | see above |
| `test_a_repeated_symbol_does_not_consume_a_second_budget_slot` | **NO** | see above |
| `test_a_candidate_that_resolves_rescues_a_query_with_another_that_does_not` | not a deletion | re-added in the same file with a new signature |
| all six in `test_plan_memory_binding.py` | not deletions | all six re-added by name; only the `stub_resolver` fixture parameter was dropped |
| `test_14_the_real_gene_is_actually_attempted_among_ordinary_words` | yes | the property was the retired regex's own candidate ORDER; `test_ncbi_efetch_premise.py:801-838` carries a full stated reason and re-points cases 12 and 13 at `resolve_symbol_to_curie` directly |

Total: 16 removed `def test_` lines, 27 added. Six are signature changes, one is a rename, seven are genuinely retired with a correct stated reason, two are the finding above.

---

## Task 2: the eight items round 1 never reached

### 1. Prefix stability, proven not assumed. PASS

Computed by driving `core.run.run()` twice with different queries, different `session_id`s and different `trace_id`s, capturing the leading system message actually handed to `litellm.acompletion` on every call, and hashing it.

```
request 1: 4 calls carried the STABLE PREFIX as message[0]
request 2: 4 calls carried the STABLE PREFIX as message[0]
request 1 distinct prefix sha256: {'34a07a1aab36ecad4491fa2173bc8cb5d14566b3e71d3e4c879e181d9b26603e'}
request 2 distinct prefix sha256: {'34a07a1aab36ecad4491fa2173bc8cb5d14566b3e71d3e4c879e181d9b26603e'}
IDENTICAL ACROSS THE TWO REQUESTS: True

prefix length: 28925 chars
module constant _STABLE_PREFIX sha256: 34a07a1aab36ecad4491fa2173bc8cb5d14566b3e71d3e4c879e181d9b26603e
captured prefix == _STABLE_PREFIX     : True
```

Request 1 was `"Which diseases are associated with BRCA1?"` / `sess-AAAA-1111` / `trace-AAAA-1111`; request 2 was `"What is the RefSeq accession for TP53, and which BioProjects cite it?"` / `sess-BBBB-2222` / `trace-BBBB-2222`. One digest across all eight calls in both requests.

Volatile-token scan over the captured prefix:

```
  session id 1                 present in prefix? False
  trace id 1                   present in prefix? False
  session id 2                 present in prefix? False
  trace id 2                   present in prefix? False
  the request-1 query text     present in prefix? False
  the request-2 query text     present in prefix? False
  owner id                     present in prefix? False
  a unix timestamp             present in prefix? False
  a uuid                       present in prefix? False
  an ISO date                  present in prefix? True   2026-08-08
```

The ISO date is a static graph-snapshot literal inside `_BIOLINK_CONCEPT_SCHEMA`, not a runtime value: if it were runtime the two digests could not match. The few-shot section is sourced from `few_shot_pool.load_pool()`, which is process-cached behind a lock (`orchestrator/few_shot_pool.py:161-166`) and serialized with `sort_keys=True` (`harness/cache.py:534-536`), so its bytes are fixed for the process. `build_stable_prefix` takes no suffix-shaped parameter at all; per-query content rides the user message (`_build_think_messages`, `graph.py:1006-1020`).

### 2. F-4.6-A-08, concurrency, RUN not read. PASS

Two questions, both answered by execution.

Is there exactly one writer implementation? Yes. `grep -rn "few_shot_examples.json\|DEFAULT_POOL_PATH\|append_example\|_write_json_object" src/` returns exactly one write path: `few_shot_pool.append_example` (`orchestrator/few_shot_pool.py:187-275`). `promotion._append_pool_entry` (`feedback/promotion.py:245-265`) is a three-line delegation to it, imported inside the function body to break a circular import. `promotion._write_json_object` survives but its only remaining caller is `_append_golden_entry`, the golden-dataset half, which is out of F-4.6-A-08's scope by that module's own docstring.

Is the write atomic, genuinely serialized, and free of partial reads? Measured with 8 real OS processes (spawn start method, so eight independent interpreters, which is the "two shells" scenario F-4.6-A-08 actually describes and which P11's two threads do not reach), each appending 6 entries, with a ninth process reading the file in a tight loop throughout:

```
--- A: few_shot_pool.append_example directly ---
  writers: 8 OS PROCESSES x 6 appends = 48 expected
  entries actually in the file: 48
  LOST: none   EXTRA: none
  concurrent reader: 120648 reads, 0 JSON PARSE FAILURES, 0 empty reads, max examples seen 48
  RESULT: PASS
  leftover temp files: none;  lock file present: True
--- B: promotion._append_pool_entry (the promotion path) ---
  writers: 8 OS PROCESSES x 6 appends = 48 expected
  entries actually in the file: 48
  LOST: none   EXTRA: none
  concurrent reader: 119251 reads, 0 JSON PARSE FAILURES, 0 empty reads, max examples seen 48
  RESULT: PASS
  leftover temp files: none;  lock file present: True
```

Zero lost entries across 96 concurrent cross-process appends, and 239,899 concurrent reads with not one partial or unparseable observation. No temp file survived either run. The control is real: replacing the writer with an unlocked read-modify-write loses an entry 3 of 3 runs, and replacing it with an atomic-`os.replace`-but-unlocked writer also loses an entry 3 of 3 runs, which is the useful half, since "atomic replace is enough" is the belief that would otherwise look sufficient on a reading.

### 3. v1 scope boundary. PASS

Section 17 puts retrieval or top-k over the pool, and a learned router, outside v1, and the phase's goal contract forbids any deterministic route-lookup layer that dispatches without an LLM call.

- No retrieval, no top-k, no ranking. `_build_few_shot_section` (`harness/cache.py:512-540`) renders the ENTIRE pool, in file order, with no scoring and no selection. `grep -rni "top_k\|topk\|rank\|similar\|embed\|retriev\|nearest\|score"` over `few_shot_pool.py` and `cache.py` returns only three hits, all inside the cite-or-refuse text of `SYSTEM_INSTRUCTIONS`.
- No learned router. Nothing under `core/` or `harness/` imports `few_shot_pool` except `cache.py`, which only concatenates it into a prompt.
- No LLM-free dispatch. `think_node` reaches `_dispatch_tier_call` on every query with no early return before it (`graph.py:1109-1145`); its only exits are the three exception paths. `plan_node` likewise makes its own plan-tier call before selecting anything. The pool never reaches a matcher; it only reaches a model, as a prompt.

### 4. `_STEP_TIER["think"]` moved from `"guard"` to `"plan"`. Correct, and it is NOT the cost change

Correctness: yes. `budget_for_step` uses `_STEP_TIER` only to pick a per-step TIMEOUT (`harness/harness.py:441-447`); it does not select the model. `think_node` passes the tier positionally as the literal `"plan"` (`graph.py:1123`), matching Section 17's "Think still makes this call, via the Plan-tier model, on every query". Leaving the table at `"guard"` would have raced a 15.0 s guard budget against a plan-tier call the same file measures at 15 to 45 s. The change moves Think's timeout from `_TIER_STEP_BUDGET_S["guard"] = 15.0` to `_TIER_STEP_BUDGET_S["plan"] = 45.0`. Correct.

Cost: the `_STEP_TIER` edit itself costs nothing. The spend change comes from `think_node`'s own `"plan"` argument and from the prompt it now sends, both T-4.7-04, and it is real. Before (`b3d030e:core/graph.py:914-936`) Think made a guard-tier call with `_stub_probe_messages` and discarded the response.

```
guard deepseek/deepseek-v4-flash: in $0.140/M  out $0.280/M
plan  moonshotai/kimi-k2.6:       in $0.646/M  out $2.720/M
  input  price ratio plan/guard = 4.61x
  output price ratio plan/guard = 9.71x

_THINK_SYSTEM_INSTRUCTION: 2531 chars, ~633 tokens
old stub probe system:     ~30 chars, ~8 tokens
_STABLE_PREFIX:            28925 chars, ~7231 tokens
TIER MAX TOKENS: {'guard': 128, 'plan': 4000, 'synth': 4000}
```

Per query, Think's own call moves from roughly 7,240 prompt tokens at guard prices with a 128-token completion ceiling, to roughly 7,870 prompt tokens at plan prices with a 4,000-token ceiling. On the input leg that is about $0.0010 to about $0.0051, a 5.0x increase; the output leg's worst case moves from about $0.000036 to about $0.0109, roughly 300x at the ceiling, though a JSON classification will not approach 4,000 tokens in practice. Call COUNT is unchanged: Think made one model call before and makes one now. The dominant mitigation is that about 7,231 of the roughly 7,870 prompt tokens are the stable prefix, which is now proven byte-identical (item 1) and therefore cacheable at the provider. That is a real increase, it is proportionate to Think doing real work for the first time, and nothing in the change is wrong. Filed as a fact for the product owner, not as a defect.

### 5. `core/state.py` changed outside its builder's ticket file scope. Necessary and correct

The diff is one functional line plus one import plus docstring updates:

```python
+from system_03_search_agent.contracts.events import Event, ResolvedEntity
+    resolved_entities: list[ResolvedEntity]
```

Necessary: `think_node` returns `{"resolved_entities": ...}` (`graph.py:1223`) and `plan_node` reads `state.get("resolved_entities", [])` (`graph.py:2116-2118`). Without the declaration the key would be undeclared on the `GraphState` TypedDict and mypy would reject both sites. Correct: `GraphState` is `total=False`, so adding the key changes no existing construction, and every other node is unaffected. The type is right: `ResolvedEntity` is the same class `graph.py` imports as `EventResolvedEntity`. The docstring edits to `query_class` and `unresolved_entity_symbols` are accurate against the code (`unresolved_entity_symbols` is now set by `think_node` at `graph.py:1230`, no longer by `plan_node`). No scope objection.

### 6. Retired tests. FAIL, see F-4.7-R2-03 above

Full table given under F-4.7-R2-03. Two of sixteen removals took a live control's only test with them.

### 7. Schema bounds on untrusted model output. PASS, one latent note

The Think classification and entity-extraction path, `core/graph.py:912-930` and `1023-1057`:

- `_ThinkClassification`: `model_config = ConfigDict(extra="forbid")` (`:918`); `query_class` a five-value `Literal` (`:920`); `narrative: str = Field(..., max_length=500)` (`:921`); `entities: list[...] = Field(default_factory=list, max_length=20)` (`:922`).
- `_ThinkExtractedEntity`: `extra="forbid"` (`:906`); `text: str = Field(..., max_length=200)` (`:908`); `entity_type` a five-value `Literal` (`:909`).
- Enforced BEFORE anything downstream reads it: `_parse_think_classification` runs `model_validate` at `:1055` and `think_node` calls it at `:1146`, before `classification.entities` is first touched at `:1172` and before `classification.query_class` reaches state at `:1214`. A `ValidationError` becomes `ThinkClassificationUnavailableError` and then a `step_error` (`:1147-1163`), never a default.
- Downstream bounds hold too. `_MAX_LIVE_SYMBOL_LOOKUPS = 3` caps live calls (`:1091`), `_TARGET_ENTITIES_MAX_ITEMS = 10` caps the list (`:1210`), `ThinkPayload.resolved_entities` carries `max_length=20` and `ResolvedEntity.text` carries `max_length=200`, exactly matching `_ThinkExtractedEntity.text`'s own cap, so the `4a64c12` fix cannot overflow the event contract by putting a surface form where a CURIE used to go. That match was checked specifically because it is the one way the fix could have broken something.

Latent note, non-blocking: `_parse_think_classification` calls `json.loads` on `response.content` with no explicit character cap of its own. It is bounded in practice by `_TIER_MAX_TOKENS["plan"] = 4000`, which is a provider-side bound rather than a local one. Worth a `maxLength` on the raw text if the tier ceiling ever rises.

### 8. Round 1's own passed items, re-derived rather than inherited

- The classification is real and is not a new constant. `think_node` READS the response: `_parse_think_classification(response.content)` at `:1146`, and `classification.query_class` is what reaches both the payload (`:1214`) and state (`:1222`). Grepping lines 1109 to 1232 for the string `lookup` returns exactly two hits: `budget_for_step("think", "lookup")` at `:1140`, which is Think's own step budget and where `budget_for_step` ignores the query-class argument entirely for any non-`act` step (`harness/harness.py:439-447`), and one word inside a comment. Independently confirmed behaviourally: P4 goes RED on each of three different constants.
- No CURIE can be fabricated. `_confirm_extracted_entities` appends only inside `if curie is not None:` where `curie = await resolve_symbol_to_curie(symbol)` (`graph.py:1092-1099`); an unconfirmed span goes to `unresolved` and contributes nothing. The other producer, `resolve_exact_identifiers` (`graph.py:1416-1445`), builds each CURIE deterministically from a matched span under four fixed patterns. Behaviourally confirmed: fabricating `NCBIGene:ZZZX9Q` turns P6 RED.
- The retired heuristic has no `except` path resurrecting it. `grep -rn "_SYMBOL_CANDIDATE_STOPWORDS\|_GENE_SYMBOL_TOKEN_PATTERN\|_CORF_GENE_TOKEN_PATTERN\|_resolve_query_entities\|_KNOWN_GENE_SYMBOL_CURIES" src/ tests/ frontend/src` returns only comments, docstrings and test-local names; no definition and no call site. `think_node` has exactly three `except` clauses (`QueryCapExceededError`, `HarnessCallError`, `ThinkClassificationUnavailableError`) and all three `return` immediately without resolving anything. P7 is falsifiable and was watched RED on both names.

---

## Task 3: `4a64c12` reviewed hardest

The fix is correct in what it does. It is incomplete in one place, and its commit message states the reason for that incompleteness in terms that are no longer true.

### Is the fix real? Yes, and it is the one thing this round confirms without reservation

Before `4a64c12`, injecting the exact defect P1's docstring names left all four cases GREEN. After it, all four go RED with the arm's own message. That was re-derived independently this round, driven through the real loop rather than reasoned from the diff, and it is in the sweep table above.

### Can a CURIE end up in `text` again? No route found

Three routes were checked.

- The model extracts a CURIE-shaped span. `resolve_exact_identifiers` claims that span first (`graph.py:1428-1429`), `_build_think_messages` then names it in the "Already resolved exactly, do not re-extract" block (`graph.py:1006-1012`), and even if the model extracts it anyway, `resolve_symbol_to_curie` is a gene-symbol lookup that will not confirm a `prefix:local_id` string; and if it somehow did, `seen_curies` (`graph.py:1175`, `:1204`) drops it as a duplicate.
- `resolve_exact_identifiers`'s own entities, the different route the brief asks about. These were never affected: `_add` sets `text=text` from the matched span and `curie` separately (`graph.py:1424-1429`), and for the verbatim-CURIE rule the two are equal because the user really did type a CURIE, which is honest rather than a substitution. They enter `resolved_entities` first, as `list(exact_matches)` (`graph.py:1174`), and seed `seen_curies`. Correct.
- A future lookup-with-fallback. The fix explicitly avoids this by carrying pairs. That reasoning is sound and the code matches it.

### Can `confirmed` and `curies` diverge? No, but `curies` is now dead

`_EntityResolution` has exactly one construction site in `src/` (`graph.py:1101-1105`), and `curies.append(curie)` and `confirmed.append((symbol, curie))` are adjacent lines inside the same `if curie not in seen_curies:` guard (`graph.py:1096-1097`). They cannot diverge.

They cannot diverge because `curies` is no longer read. `grep -rn "\.curies\b" src/` returns one hit and it is a comment (`graph.py:1178`). Measured: forcing `_EntityResolution.curies` to `[]` on every call and running the full suite returns `6 failed, 3757 passed, 146 skipped, 1 xfailed`, the exact unmutated baseline. Filed as F-4.7-R2-06, MINOR: a field maintained alongside the one that replaced it, read by nothing, is the drift surface the fix's own docstring warns about.

### F-4.7-R2-04, MAJOR (latent): the fix's justification for its scope boundary is false, and the defect is live on the path that feeds the model

`4a64c12`'s commit message and the comment it left in place both say:

> The justifying comment for substituting the CURIE lives in `plan_node`, where "the free-text mention is not recoverable" is genuinely true. It was carried into `think_node`, where it is false.

The first half is no longer true, and this phase is what made it untrue. `plan_node` reads Think's pairs at `graph.py:2116-2118`:

```python
    think_resolved_entities: list[EventResolvedEntity] = state.get(
        "resolved_entities", []
    )
```

and then, 70 lines later at `graph.py:2179-2187`, discards the surface forms it is holding:

```python
            # `text` is the CURIE rather than the user's phrase: the free-text
            # mention is not recoverable at this point, and echoing the CURIE
            # is honest where inventing a phrase would not be.
            resolved_entities=[
                EventResolvedEntity(text=curie, curie=curie, confidence=1.0)
                for curie in planned.cypher_input.target_entities[:20]
            ],
```

The mention IS recoverable at that point, in a variable already in scope in that function. This is the exact pattern `.claude/rules/self-eval-loop.md` names: a comment asserting a property sitting above code that does not implement it, and it is the second instance of this same comment being wrong in this phase.

It is reachable, not theoretical. `core/run.py:390-407` builds session memory from the PLAN event, never the think event, and takes `mention` straight from `text`:

```python
        if event.type != "plan":
            continue
        for entity in event.payload.get("resolved_entities") or []:
            ...
                        mention=str(entity.get("text") or curie)[:200],
```

Measured end to end through the real loop:

```
think  resolved_entities = [{'text': 'BRCA1',        'curie': 'NCBIGene:672', 'confidence': 1.0}]
plan   resolved_entities = [{'text': 'NCBIGene:672', 'curie': 'NCBIGene:672', 'confidence': 1.0}]
```

Think now says `BRCA1`. Plan still says `NCBIGene:672`, and Plan is the one memory reads. So `session_memory._render` (`core/session_memory.py:253-256`) emits `resolved NCBIGene:672 to NCBIGene:672 (Unknown)` into the dynamic suffix of every later turn in the session, which is precisely the harm the round 1 CRITICAL described ("every `think` event now tells its consumers the user typed a CURIE"), still live on the one path that feeds it back to a model.

Why this does NOT block on its own, and why it is not a Rule 4 stop: the behaviour is unchanged from build phase 4.5 (`b3d030e:core/graph.py:1958-1973` carries the same code and the same comment), `4a64c12` did not touch `plan_node`, and the memory entry is still factually correct about the CURIE, so it degrades the memory rather than producing a wrong answer. What is new is that the fix declined to close it while asserting a reason that this phase had already falsified. That assertion should be corrected in `tracker/phase_4.7.md` rather than left standing, because a false justification recorded next to a closed CRITICAL is how this repository has previously lost a defect. The fix itself is a two-line change now that the pairs exist.

### The comments introduced by `4a64c12`, checked as claims rather than read as documentation

- "Every downstream consumer of `resolved_entities` reads `.curie`, never `.text`" (round 1's report, line 111, restated as the basis for calling the fix non-breaking). FALSE as written, and I re-derived it rather than inheriting it: `core/run.py:406` reads `.text`. It is true for the THINK event, which is all the fix needed, and the frontend validates `text` (`frontend/src/lib/events.ts:273`) without rendering it. The fix is still non-breaking. The claim as stated is not.
- "Pairs are iterated rather than looked up per CURIE deliberately" (`graph.py:1195-1201`). True and verified: `for symbol, curie in model_resolution.confirmed` at `:1203`, no dict, no `.get`, no fallback.
- "Default-empty so `resolve_exact_identifiers`'s own construction is unchanged" (`graph.py:1753-1755`). True in effect but imprecise: `resolve_exact_identifiers` does not construct an `_EntityResolution` at all, it returns a `list[EventResolvedEntity]`. The default matters for the test-local constructions in `test_plan_memory_binding.py`, not for that function. Cosmetic.

---

## Minor findings, reported with an owner, not blocking

| ID | Severity | Finding | Owner |
|----|----------|---------|-------|
| F-4.7-R2-05 | minor | P6 has no populate-check for its own premise and passes on a plausible fabrication. Mutation-measured: a model that extracts NOTHING leaves P6 GREEN, and fabricating `ZZZX9Q` to the real-looking `NCBIGene:672` also leaves it GREEN, because the assertion tests for the token INSIDE the CURIE. The file's own docstring claims every arm asserts it produced the state it measures; P6 does not. It is falsifiable (two mutations turn it red), so it is not vacuous | phase 4.7 lead |
| F-4.7-R2-06 | minor | `_EntityResolution.curies` is now write-only in production. Full suite green with it forced empty | phase 4.7 lead |
| F-4.7-R2-07 | minor | P12b's docstring (`test_cq_routing_premise.py:889`, `:911`) and `core/graph.py:2505` both say "30 second" for `CYPHER_QUERY_TIMEOUT_SECONDS`, which is `90.0` (`tools/graph_schema_constants.py:170`, deliberately, with its measurements recorded). Three places state a number the constant has not held since build phase 2.1 | phase 4.7 lead |
| F-4.7-R2-08 | minor | The 90.0 s floor at `core/graph.py:2514` MASKS the per-class Act budget for four of five classes: lookup 15, single_hop 20, aggregate 30, multi_hop 30 all resolve to 90.0 after the `max()`, and only exploratory (120) selects anything different. T-4.7-08's "a real class finally selects a real budget" is true at `budget_for_step` and very nearly inert at Act. Worth stating in the phase's own record rather than discovering later | product owner |
| F-4.7-R2-09 | minor | `few_shot_pool.append_example` creates a sibling `few_shot_examples.json.lock` (`orchestrator/few_shot_pool.py:240`). `.gitignore` has no entry for it, so a promotion run inside the repository leaves an untracked file beside a tracked one | phase 4.7 lead |

Not re-filed, per the brief: F-4.7-04 (`test_persona.py`'s measured 1-in-32 flake) did not appear in any of this round's three full-suite runs.

Already known, restated only so it is not read as new: `python tracker/check_doc_drift.py --check` still fails (6 stale facts, tests 3896 vs computed 3910, decisions 380 vs computed 384). T-4.7-10 is still `todo`, so this is unfinished work rather than a defect.

---

## Is the phase's done-when genuinely met?

No, and for the same reason as round 1 rather than a new one: the gap is at the verify surface, not at the tickets.

`tracker/phase_4.7.md` states the verify surface as "this phase's premise gate, run live... every arm carrying a populate-check and every arm mutation-proven".

- "Every arm mutation-proven" is now TRUE as a matter of record, because this report proves them. Twelve of thirteen survived. P12b did not: it cannot fail on either of its two assertions, so one of the sixteen reported live passes still does not mean what it is read to mean. That is the same defect class the phase has now shipped three times.
- "Every arm carrying a populate-check" is still not literally true: P6 has none for its own premise, and P12b's is unfalsifiable.
- The done-when's own first clause, "none is refused because a database name mentioned in passing was misread as a gene symbol", has exactly one grader, P1, and P1 now CAN see the surface form (the round 1 fix worked) but compares it by exact list membership, so the clause is graded only when the real model happens to return the bare token rather than a natural wider span. The clause is partially graded, which is better than round 1's not-graded, and it is not yet fully graded.

The rest of the done-when IS met and is evidenced above: the pool loads once per process from the versioned file, the stable prefix is byte-identical across two real requests by SHA-256 with no volatile token in it, two concurrent promotions cannot corrupt the file and that was proven with eight processes rather than two threads, `interactions.query_class` records the class the loop used and P12 catches a regression of it, and the seven must-pass questions reach Act with a real classification and real resolution.

Separately, F-4.7-R2-03 means the phase's retirement sweep cost the suite two live controls with no replacement, which `.claude/rules/goal-contracts.md` treats as weakening the verify surface regardless of intent.

---

## Working tree

```
$ ruff check src/
All checks passed!

$ python -m pytest tests -q -p no:randomly
6 failed, 3757 passed, 146 skipped, 1 xfailed, 4 warnings in 92.90s

$ python -m pytest tests/system_03_search_agent/core/test_cq_routing_premise.py -q -p no:randomly
6 passed, 10 skipped in 2.37s

$ git status --short
?? tracker/phase_4.7_reverify_report.md
```

CLEAN. The only untracked path is this report, the one file this round was permitted to write.

The suite matches the branch-point baseline: the same six pre-existing `test_citation_trust_full_premise.py` failures, no new failure, no `test_persona.py` flake in three full runs. The offline gate re-runs at `6 passed, 10 skipped in 2.37s`, identical to its state before this round began.

Mid-round, `git status --short` also listed ` M DECISIONS.md`, ` M tracker/phase_4.7.md` and `?? tracker/phase_4.7_adversary_report.md`. Those were another agent's concurrent work, not this round's, and they are no longer in the working tree at the time of writing. This round modified no file under `src/`, `tests/`, `frontend/` or `tracker/` other than writing this report, and applied every mutation by in-process monkeypatching from scripts held outside the repository.
