# Build phase 4.6 judge report

Round: judge, round 1
Date: 2026-08-21
Branch: `phase/4.6-feedback-capture`, working tree at `b5b1907` plus 33 uncommitted paths (`git status --porcelain | wc -l` = 33). `git diff b5b1907...HEAD --stat` is EMPTY because nothing is committed yet; every diff below is against the working tree.
Author: judge agent, read-only. No source file, no test, and no `tracker/phase_4.6.md` was modified. No `git commit`, `git add`, `git stash` or `git checkout` was run. Every mutation was applied by copy-mutate-run-restore and the restore was verified.

## Verdict

FAIL against the merge bar.

Three findings block: two REACHABLE MAJORs proven with a running reproduction and a running test, and one reachable major that is a disclosed design limit the product owner may accept.

| ID | Severity | Reachable in the shipped product | Blocks |
|----|----------|----------------------------------|--------|
| J-01 | major | YES, reproduced end to end | BLOCKS |
| J-02 | major | YES, two arms of a merged blocking gate are red on this branch | BLOCKS |
| J-03 | major | No (verify-surface hole) | tracked |
| J-04 | major | No (gate is vacuous by construction) | tracked |
| J-05 | major | No (gate arm's named control is false) | tracked |
| J-06 | major | YES, 300-second window | BLOCKS, or product-owner acceptance converts to tracked |
| J-07 | major | No (untested branch) | tracked |
| J-08 to J-14 | minor | mixed | tracked |

The worst finding is J-01: a guest who signs up and then rates the answer they just received is told "you do not own this run" with HTTP 403, and their rating is silently discarded. It is reproduced below with production code only.

## What was measured, with the commands

| Check | Command | Result |
|-------|---------|--------|
| Premise gate, live | `RUN_PREMISE_GATE=1 pytest tests/system_03_search_agent/core/test_feedback_capture_premise.py -v` | `17 passed, 3 skipped, 2 warnings in 12.62s` |
| Full Python suite | `pytest tests/ -p no:randomly -q --tb=no -rf` | `8 failed, 3551 passed, 130 skipped, 1 xfailed in 196.63s` |
| Frontend unit | `npx vitest run` | `Test Files 16 passed (16) / Tests 209 passed (209)` |
| Playwright, feedback | `npx playwright test e2e/feedback-submission.spec.ts` | `3 passed (13.8s)` |
| Ruff, every touched file | `ruff check <17 paths>` | `All checks passed!` |
| Doc drift | `python tracker/check_doc_drift.py --check` | `error: 10 facts computed | 14 stale | 0 structural` |
| New tests in this phase | `pytest <5 new files> --collect-only` | `107 tests collected` |
| Mutations executed | see the mutation table | 36 valid mutations run; 30 red, 6 green |

### The stated baseline is wrong

The brief states the branch baseline is `6 failed, 3552 passed, 130 skipped, 1 xfailed`. The measured baseline on this branch is `8 failed, 3551 passed, 130 skipped, 1 xfailed`. The two extra failures are:

```
FAILED tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py::TestTrustSignalHelpers::test_the_two_phase_4_10_citation_fields_are_really_on_the_wire
FAILED tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py::TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field
```

Both are caused by this branch. That is finding J-02.

## Grade 1: the premise

The question the brief asks is not "did each ticket produce a file" but: does a real query, on every surface and at every trust outcome, cause exactly one correctly-attributed `interactions` row?

For the OFFLINE half, yes, and it is genuinely proven rather than asserted. P1 asks an ordinary question as a guest with nothing handed in and reads a row back out of the database (`test_feedback_capture_premise.py:387-425`), and removing the epilogue dispatch turns it red (mutation M1). P2 does the same across all five `RequestContext.surface` values and all five go red when capture is made conditional (M10). P2b covers the Guardrail refusal, the outcome with nothing to assemble from, and goes red when the assembler drops a citation-less run (M2). The four dispatch sites in `core/run.py` all exist and all four are individually mutation-proven: `run()` normal (`run.py:412`, M1), `run()` crash (`run.py:394`, M14), `run_streaming()` crash (`run.py:484`, M15), `run_streaming()` normal (`run.py:493`, M16). Attribution is real: P3 and M3b show that collapsing `session_row_key` back onto the bare `session_id` merges two guests, and M20 shows that dropping `owner_id` from the insert reds six writer tests.

For the LIVE half, NO, and this is the largest single gap in the phase.

The three live arms (P1b, P9, P12) SKIPPED even with `RUN_PREMISE_GATE=1`, because the Layer 1 graph tunnel is down:

```
graph reachable: False   model configured: True   network permitted: True
GRAPH_PG_HOST= 127.0.0.1 PORT= 15432
$ python tracker/preflight.py
  product-model  ok       openrouter.ai HTTP 200 in 204ms
  harness-model  ok       api.anthropic.com HTTP 404 in 132ms
  graph          down     TCP 15432: ConnectionRefusedError: [Errno 61] Connection refused
```

I attempted to open the SSH forward and was denied by the permission layer, and per `.claude/rules/sandbox-diagnosis.md` an SSH (Layer-4) failure is not something `/sandbox` can fix and not grounds to disable the sandbox. So P1b, P9 and P12 are unverified, which under the brief's own rule ("I could not verify X is a FAIL for X") is a FAIL for the live half of the premise. What that specifically leaves unproven:

- P9: that all eight Decision G fields carry a value on a run that actually traversed the graph. Four of them (`citations`, `normalized_entities`, `route`, `coverage_tags`) are empty by construction against the offline stub, so no offline arm covers them.
- P12: that `coverage_tags` names the predicate actually traversed. This is the arm F-4.6-04 was filed against, and the phase board records "P12 NOT RUN and explicitly not claimed to pass". It is still not run.

Note also that the gate exits 0 in this state: `17 passed, 3 skipped` with `exit code 0`. LEARNINGS.md's own 2026-08-19 entry says "a `skipped` premise gate is never a passing one". Nothing in this gate enforces that, so a reviewer who runs it with the tunnel down sees a clean pass.

## Grade 2: mutation-testing every gate arm

36 valid mutations were run. Two further mutations were discarded as invalid setups and are recorded rather than dropped: M3 renamed `session_row_key` (an ImportError proves nothing), and M5 appended a second `model_config` that the class's existing one overrode. The count below is what I actually ran, not what I intended.

### Premise gate arms

| Mutation | Arm and its named control | Result |
|----------|---------------------------|--------|
| M1 | P1: delete `run.py:412` epilogue dispatch | RED |
| M2 | P2b: assembler returns None when a run has no citations | RED (P1 stayed green, so the arm discriminates) |
| M3b | P3: `session_memory.py:503` drops `owner_id` from the uuid5 key | RED |
| M4 | P4: remove `writer.py:186` `on_conflict_do_nothing(index_elements=["trace_id"])` | **GREEN** (J-05) |
| M5b | P5: `app.py:273` `extra="forbid"` to `extra="ignore"` | RED |
| M6 | P5b: move the conflict key from `trace_id` to `session_id` | RED |
| M7 | P6: remove the try/except in `run.py:_capture_interaction` | RED |
| M8 | P7: writer records `user_id=None` | RED |
| M9 | P8: `_caller_owns_row` returns True | RED |
| M10 | P2 x5: capture made conditional on query text | RED, all 5 params |
| M11 | P10: leak `OPENROUTER_API_KEY` into the `route` column | RED |
| M12 | P11: `rubric_outcome_for` always returns `"pass"` | RED |
| M13 | coverage-statement arm: delete the entire coverage docstring | **GREEN** (J-04) |
| P1b, P9, P12 | not mutated | NOT RUN, graph down |

### Other new suites

| Mutation | Target | Result |
|----------|--------|--------|
| M14 | `run()` crash-path dispatch removed | RED (`test_run_captures_on_the_crash_fallback_path`) |
| M15 | `run_streaming()` crash-path dispatch removed | RED |
| M16 | `run_streaming()` normal-path dispatch removed | RED |
| M17 | re-add the reverted `trace_id` mint in `run()` | RED (`test_run_does_not_overwrite_the_trace_id_it_was_given`) |
| M18 | `_caller_owns_row` returns True | RED, 3 arms (matches the F-4.6-01 claim exactly) |
| M19 | `_caller_owns_row` treats NULL as owned | RED, 1 arm |
| M20 | writer stops persisting `owner_id` | RED, 6 arms |
| M25 | `_caller_owns_row` returns False | RED, 5 arms (matches the F-4.6-01 claim exactly) |
| M21b | revert F-4.6-04: `graph.py` stops threading `row_types` | **GREEN** (J-03) |
| M22 | `coverage.py` emits no predicate tags | RED, 2 arms |
| M23 | `coverage.py` emits a predicate tag for any value | RED, 1 arm |
| M24 | remove `node_or_edge_type` from `CitationPayload` | turns the 2 failing MCP arms GREEN (causation proof for J-02) |
| EP1 | endpoint answers the not-yet-captured race with a silent 204 | RED |
| EP2 | endpoint answers an ownership refusal with a silent 204 | **GREEN** (J-07) |
| EP3 | endpoint drops `_get_owned_run` | RED, 2 arms |
| RV3 | `find_weekly_candidates` SQL selects every row | **GREEN** (J-07) |
| RV4 | review window widened by 10 years | RED |
| RV5 | the `_is_flagged` Python re-assertion deleted | **GREEN** (J-07) |
| RV2 | `reviewed_by` human-terminal gate removed | RED |
| PR1 | promotion no longer requires `review_decision == 'approve'` | RED |
| CP1 | assembler hardcodes `owner_id` | RED, 5 arms |
| FE1 | `App.tsx` stops passing `runId` (the F-4.6-08 defect) | **GREEN in vitest** (J-13), RED in Playwright |
| FE2 | `AnswerScreen` stops rendering `FeedbackSurface` | RED, 8 arms |

Six mutations stayed green. Every one is a finding below.

### Claims in the Findings table that I re-ran

The brief asked me to verify rather than trust. Four claims were re-run and all four hold exactly as written:

- F-4.6-01: "forcing the check to `True` turned the two stranger arms and the NULL arm red, forcing it to `False` turned both owner arms red." M18 gives exactly 3 red (`test_a_different_registered_account_is_refused_and_writes_nothing`, `test_a_different_guest_is_refused_and_writes_nothing`, `test_a_row_with_no_owner_id_refuses_even_the_true_caller`). M25 gives 5 red including both owner arms. Confirmed.
- F-4.6-06: "flipping `extra='forbid'` to `extra='ignore'` turns P5 red" (M5b, confirmed) and "moving the writer's conflict key off `trace_id` turns P5b red" (M6, confirmed).
- F-4.6-08: "dropping the two props timed out the send path." Confirmed against real Playwright: with `runId={null}`, `feedback-submission.spec.ts:143 a rating actually reaches the backend and the panel confirms it` FAILS and the other two pass.
- F-4.6-04: "four mutations run and confirmed red." The two I could reconstruct (M22, M23) are red. The threading itself is not covered by any of them, which is J-03.

## Grade 3: the gate itself

### P5 and P5b, the rewritten arms, graded hard

Both are sound and I would keep them. P5's structural claim is correct and stronger than the behavioural one it replaced: `CreateRunRequest` at `app.py:272-273` sets `extra="forbid"` and declares no `trace_id`, and I confirmed by reading that `adapters/mcp/server.py:769` sets `trace_id=run_id` from its own mint and `adapters/graphql/schema.py` never reads a caller value, so the property really is closed at the contract rather than at runtime. P5b's docstring is the best-written arm in the file, because it records what the mutation ACTUALLY did (a `ProgrammingError` and a silent drop of both rows) rather than what was predicted, and my M6 reproduces exactly that. The regression guard at `test_run_capture.py:163` is real: re-adding a mint inside `run()` turns it red (M17). The revert is clean: `grep -n "uuid" src/system_03_search_agent/core/run.py` shows no mint, and all four capture dispatch sites survive and are individually mutation-proven.

### The harder question: is any OTHER arm testing a path no caller can take, or claiming a control it does not have?

Yes, three, and one of them is the same shape as F-4.6-06.

The worst is `test_the_gate_states_its_own_coverage` (`test_feedback_capture_premise.py:975-997`). It reads its own source and asserts two literal headings are present. Both literals appear in the assertion expressions themselves, so they are always in the file being read. I deleted the ENTIRE 5762-character coverage statement from the module docstring and the arm still passed:

```
deleted 5762 chars of coverage statement
heading still anywhere in file: True
NOT-exercised heading still anywhere in file: True
1 passed in 0.77s
```

The arm's own docstring says "A docstring can be deleted in a refactor without anything noticing, so this arm notices." It demonstrably does not notice. This is a self-satisfying assertion that can never go red, in the arm whose whole purpose is enforcing the `goal-contracts` coverage requirement that F-4.6-06 was filed under. That is J-04.

Second is P4 (`test_feedback_capture_premise.py:545-590`). Its docstring names the ON CONFLICT clause as its control and states "Replace it with a plain insert and this arm goes red, either on the count or on the integrity error." It does not. I removed the clause and re-ran with logging on:

```
mutation applied; on_conflict present now: False
tests/.../test_p4_capturing_the_same_run_twice_leaves_one_row PASSED [100%]
1 passed in 22.06s
```

The reason is structural and worth stating: `write_interaction` (`writer.py:205-224`) catches every exception and drops the row, so the duplicate insert raises an `IntegrityError` that is swallowed, the count stays at 1, and the arm cannot distinguish "idempotent by design" from "duplicate write silently dropped". P5b's own docstring already names this hazard ("a malformed write is invisible from the outside") without noticing that it disarms P4. That is J-05.

Third is the assertion-versus-reality gap on P2's coverage claim. The gate's coverage statement says GraphQL, CLI and MCP are "asserted to inherit capture through `run()` by P2's parametrisation over `RequestContext.surface` only". That is honestly stated and I have no complaint about it. But the arm's own docstring goes further: "A capture call added to one adapter rather than to `run()` passes P1 and fails four of these five." That specific claim is not testable by any mutation I could construct, because all five params call the same `_run_default` helper; my M10 reds all five together, not four of five. The claim is decorative rather than false. Recorded, not filed.

## Grade 4: the four still-open findings

### F-4.6-03, durable cross-reload history, scope conflict, product owner

I AGREE with the disposition and it does NOT block. Section 25 is locked and authoritative on what a phase delivers, and it names three deliverables with history not among them. The two `frontend/src/stubs/registry.ts` notes were written by phases 4.8 and 4.10 and are build artifacts, not the spec. I verified the lead followed Section 25 and built no history surface. One thing to add for the product owner: the "history" stub entry is STILL in `registry.ts` naming 4.6 as its owner, so whichever way this is settled, that line needs to change or it will point at a closed phase.

### F-4.6-07, Section 20.1 versus Section 13.1 on where `trace_id` is minted, product owner

I AGREE with the disposition and it does NOT block this phase. I verified both halves independently. Section 13.1's shipped behaviour holds: `app.py:1016-1036` mints one uuid4 and uses it as both `run_id` and `Query.trace_id`. Section 20.1's wording is genuinely contradictory and cannot be satisfied without splitting that pair. Following 13.1, the more specific and already-shipped section, is the right call. Two things the reconciliation owner should have: the conflict is now ALSO live in the harness (`harness/harness.py:477` still says "minted at the Guardrail step") and in a comment this phase newly added (J-09), so the count of places that will mislead the next reader went up rather than down.

### F-4.6-09, `citation_flags` carries a display index in a field named `citation_id`

I AGREE it is a minor and it does NOT block. I verified the technical account is exactly right: `FeedbackSurface.tsx:158` does `citation_flags: flaggedSources.map((n) => ({ citation_id: String(n), ... }))`, and `AnswerScreen.tsx:52-61`'s `Source` interface has no `citation_id` field at all, so the real value genuinely does not reach this component. One correction to the finding's stated purpose. It says it was "filed so the ritual's first real reviewer is not the person who discovers it". That purpose is not met: `docs/build/Feedback_review_ritual.md` is what the reviewer reads and `grep -n "citation_id\|display index\|F-4.6-09\|index"` on it returns nothing. A single line in the runbook closes the gap the finding was filed to close. That is J-12.

### F-4.6-10, a migration destroys baseline re-measurement

I AGREE with the analysis and it does NOT block, and I did not repeat the mistake: I measured the branch baseline only, on the branch, and never checked out an old commit against the shared database. But the finding's stated branch figure is wrong. It records "branch 6 failed / 3552 passed / 0 errors". The measured figure is 8 failed / 3551 passed. The two-failure difference is J-02, a real regression this phase caused, and it was inside the number the finding was using to argue that the OTHER number was the artifact. The lesson the finding draws is right; the instrument it trusted on the branch side had its own error in it.

## Grade 5: scope

CLEAN. Nothing built stage 2, a small version of it, or a helper for it.

```
$ grep -rniE "cluster|kmeans|embedding|cosine|tfidf|silhouette|dbscan|blast|vcf|sequence.similarity|mine_" \
    src/system_03_search_agent/feedback/ src/system_03_search_agent/orchestrator/
```
returns four hits, all of them prose disclaiming the boundary (`review.py:37` "nothing here builds a clustering", `review.py:112` a docstring word, `review.py:295` a quote from stage 4, `contracts.py:58` an unrelated sentence). No BLAST, no sequence similarity, no VCF.

Two things I checked specifically because they LOOK like stage 2:

- `review.normalize_query_text` (`review.py:82-91`) is whitespace collapse plus lowercase, with no stemming, no synonym folding and no entity resolution. Grouping is exact string equality on that. That is stage 3 step 1's "grouped by normalized query text", not clustering.
- `find_similar_existing_candidates` (`review.py:173-190`) uses `pg_trgm` similarity. Section 16 stage 4 names `pg_trgm` similarity on `representative_query` explicitly as one of the two acceptable v1 novelty checks, and the function returns candidates for the reviewer rather than deciding. In scope.

The human-terminal gate is structural, not conventional, as T-4.6-10 required: `review.py:301-309` makes `reviewed_by` and `review_decision` required and validated, and `promotion.py:287` refuses any candidate whose `review_decision` is not `approve`. Both are mutation-proven red (RV2, PR1).

## Findings

### J-01. MAJOR, REACHABLE, BLOCKS. A guest who signs up is 403'd on their own answer and their rating is discarded

`src/system_03_search_agent/feedback/writer.py:245`, `src/system_03_search_agent/core/run_registry.py:833-835`, `src/system_03_search_agent/auth/router.py:487-491`, `src/system_03_search_agent/adapters/web_sse/app.py:1512-1516`

The feedback endpoint runs TWO ownership checks against TWO different records of who owns a run, and the guest-to-account migration updates only one of them.

- `app.py:1476` calls `_get_owned_run(run_id, caller)`, which compares `RunEntry.owner_id` (`app.py:1156` to `run_registry.py:resolve_owned_run`).
- `app.py:1478` then calls `record_feedback`, which reaches `_caller_owns_row` at `writer.py:245` and compares `interactions.owner_id`, the column alembic 0008 added this phase.

`auth/router.py:487-491` migrates a guest at signup by calling `default_registry.reassign_owner(...)`, and `run_registry.py:833-835` shows that call mutates exactly two things:

```python
if entry.owner_id == old_owner_id:
    entry.owner_id = new_owner_id
    entry.user_id = new_user_id
```

Nothing rewrites `interactions.owner_id`. The two records now disagree, the first check passes and the second refuses.

Reproduced with production code only, no mocks and no test helpers (`_migrate_guest_session`'s own `reassign_owner` call, the real `write_interaction`, the real `record_feedback`, the real `RunRegistry`), against a scratch database at `alembic head`:

```
1. captured interactions row: owner_id=guest:c03b7602-3659-4fd2-b13d-36cdaa12caf1
2. registry RunEntry.owner_id=guest:c03b7602-3659-4fd2-b13d-36cdaa12caf1
3. signup -> reassign_owner reassigned 1 run(s); RunEntry.owner_id is now user:525e72b6-0e05-4cf0-b8e4-dc8fdf90b20e
4. _get_owned_run PASSES: the registry agrees the run is theirs
5. record_feedback RAISED FeedbackOwnershipError -> HTTP 403 "you do not own this run"  <-- DEFECT
6. stored user_feedback=None (their rating was discarded); row owner_id still 'guest:c03b7602-3659-4fd2-b13d-36cdaa12caf1'
```

Why it is reachable and not theoretical. Build phase 4.10 shipped the anonymous run path specifically so someone can use the product before creating an account, and signing up after seeing a good answer is the conversion path that path exists to create. The frontend supports it directly: `App.tsx:637` passes the CURRENT `authToken`, so after signup the panel posts with the new account token against the same `runId`. And the user sees `app.py:1516`'s detail string, "you do not own this run", about the answer they are looking at.

This is named by the phase's own board. T-4.6-06's acceptance criteria include "F-4.10-A-14 closed: after a guest-to-account migration the run's own `Query.user_id` is rewritten alongside `RunEntry.user_id`, so a migrated run's row is attributed rather than orphaned." No code on this branch does that; `run_registry.py` and `auth/router.py` are not in the diff at all. The criterion is unmet and the new column turned "orphaned" into "actively refused".

Owner: the fix belongs beside `reassign_owner`, not inside the endpoint. Note that a fallback that treats a guest-owned row as claimable by any account would reintroduce F-4.5-A-02, so the fix must match on the specific migrated guest identity, exactly as `reassign_owner` already does.

### J-02. MAJOR, REACHABLE, BLOCKS. Widening `CitationPayload` broke build phase 4.1's blocking MCP premise gate, and bypassed a documented approval control

`src/system_03_search_agent/contracts/events.py:229-263`, `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py:856` and `:1285` and `:1562`

F-4.6-04's fix added `node_or_edge_type` to `CitationPayload`. `AskBiomedicalQuestionOutput` (`adapters/mcp/server.py:260-286`) embeds `list[CitationPayload]` directly, so the new field is now on the real MCP wire response. `_ALLOWED_RESPONSE_KEYS` was not updated, and two arms of the phase 4.1 premise gate are red:

```
E   AssertionError: every CitationPayload field must be on the allowlist, since Section 13.2's
E   CitationV1 IS CitationPayload; a field on the model and off the allowlist fails the gate at
E   runtime instead of here, which is a worse place to find out
E   Extra items in the left set: 'node_or_edge_type'
tests/system_03_search_agent/adapters/mcp/test_phase_4_1_premise.py:1285
```

The second failure is worse than the first, because it is not a model-introspection check: `test_an_operator_allowlisted_caller_still_gets_no_cost_field` makes a REAL MCP client call and asserts over the response tree it actually produced. It fails at `:1562` with the same extra key, so the field is confirmed present on live MCP output, not merely on the model.

Causation is proven, not inferred:

```
$ git show b5b1907:src/.../contracts/events.py | grep -c node_or_edge_type   -> 0
$ grep -c node_or_edge_type src/.../contracts/events.py                     -> 2
$ git diff --stat tests/system_03_search_agent/adapters/mcp/                -> (empty)
[M24 remove node_or_edge_type field] rc=0 :: 2 passed, 2 warnings in 3.36s
```

Removing only the new field turns both arms green. This branch is the sole cause.

The control that was bypassed is explicit and was followed twice before. `test_phase_4_1_premise.py:856-900` records that `_ALLOWED_RESPONSE_KEYS` is "a deliberate manual control", that build phase 4.10's `display_index`/`entity_name` pair and build phase 4.5's `persona_name` were each "Added by the LEAD, not by the builder that widened `CitationPayload`", each "with the product owner's explicit approval", and that the agent making the source change "stopped here and escalated rather than edit it, which is the control working". Build phase 4.6 did neither: it did not update the allowlist and it did not escalate. F-4.6-04's fix note claims a careful additive change and even records that the agent grepped `harness/cache.py` to prove the prompt-cache prefix was untouched, but it never checked the one surface allowlist that both prior identical changes had to pass.

The field's CONTENT is benign (a graph label, no user data, no cost data), so this is not a disclosure. What blocks is that a merged phase's blocking gate is red on this branch and the documented approval step for widening a locked wire contract did not happen.

Owner: lead, plus a product-owner decision on the allowlist entry, following the three-test template the two prior entries already establish at `test_phase_4_1_premise.py:860-880`.

### J-03. MAJOR, not reachable as a product defect, TRACKED. The F-4.6-04 fix has no verification anywhere

`src/system_03_search_agent/core/graph.py:4636-4638`, `tests/system_03_search_agent/feedback/test_coverage.py`

Reverting the entire fix leaves the offline suite byte-identical:

```
[M21b revert F-4.6-04 (targeted)] rc=0 :: 423 passed, 3 skipped, 2 warnings in 38.68s
=== UNMUTATED CONTROL on the same selection ===
                                     423 passed, 3 skipped, 2 warnings in 36.42s
```

With `row_types` no longer threaded, every citation's `node_or_edge_type` is `None`, so `coverage.py:133`'s membership check never fires and NO real run can ever produce a `predicate:` tag. Nothing notices. Combined with P12 being unrunnable, the `predicate:<edge_type>` half of `coverage_tags` (T-4.6-05's first acceptance criterion, and the whole content of F-4.6-04's fix) has zero verification, offline or live.

`test_coverage.py`'s ten arms are real and two of them go red on a genuine mutation (M22, M23), but every one of them hands `node_or_edge_type` in on a constructed citation dict. That is precisely the shape the gate's own docstring warns about at `test_feedback_capture_premise.py:17-20`: "an arm that constructs a row payload, hands it to the writer, and reads it back proves the writer works and says nothing at all about whether a query ever calls it." Here it proves the derivation works and says nothing about whether any citation ever carries the field.

I confirmed no other test covers the seam: `grep -rn "node_or_edge_type" tests/ | grep -v test_coverage.py` returns only `tools/test_cypher_*.py` (the tool-level row field, a different layer) and `core/test_graph.py`'s `_node_or_edge_type_by_citation_id` unit tests (the producer, which was already there). Nothing asserts `CitationPayload.node_or_edge_type` is populated by `write_node`.

Not blocking, because I cannot show a product defect: the shipped code looks correct on reading and the key spaces line up. But this is the one place where a real defect could be sitting right now with nothing able to see it, and it is exactly what P12 exists for. Recommend an offline arm that drives `_citations_from_grounded_claims` with a `row_types` dict built by `_node_or_edge_type_by_citation_id` from the same findings, so the two key spaces are asserted to agree without needing the graph.

### J-04. MAJOR (gate), not reachable in the product, TRACKED. `test_the_gate_states_its_own_coverage` can never fail

`tests/system_03_search_agent/core/test_feedback_capture_premise.py:975-997`

Evidence and mechanism are in Grade 3 above. The arm greps its own source for two literals that appear in its own assertion expressions, so both are always present. Deleting the whole coverage statement leaves it green. Fix is one line: compare against the module docstring (`__doc__`) rather than the file source, which excludes the assertion text.

This is the second arm in this file, after F-4.6-06's P5, written by the lead and claiming a property it does not have. F-4.6-06's own reason line says "the lead wrote this arm, found it, and fixed it, so all three roles are the same party and the judge round is the only real check." That observation was correct and applied to more than one arm.

### J-05. MAJOR (gate), not reachable in the product, TRACKED. P4's named control is false

`tests/system_03_search_agent/core/test_feedback_capture_premise.py:545-590`, masked by `src/system_03_search_agent/feedback/writer.py:205-224`

Evidence in Grade 3 above. The shipped `ON CONFLICT (trace_id) DO NOTHING` at `writer.py:186` IS present and IS correct, which is why this is not a product defect. What is wrong is that P4 cannot tell if it ever goes away, because the writer's best-effort catch converts a duplicate-insert `IntegrityError` into a silently dropped row and the count P4 asserts on stays at 1 either way. Any future change that removes the clause passes this gate.

Fix that keeps the property: assert directly against `_write_interaction_row`, which `writer.py:137-151`'s own docstring says was "Kept separate from `write_interaction` ... so a test can exercise the ON CONFLICT clauses directly, with a real `IntegrityError` propagating on a mutation, instead of that mutation being masked by the outer best-effort catch." The seam the fix needs already exists and P4 does not use it. `test_writer.py:343`'s `test_a_second_insert_under_the_same_trace_id_changes_nothing` is the arm that should carry this; it was not in the set M4 reds either.

### J-06. MAJOR, REACHABLE, BLOCKS (or product-owner acceptance). Feedback is impossible on any answer older than 300 seconds

`src/system_03_search_agent/adapters/web_sse/app.py:1476`, `src/system_03_search_agent/core/run_registry.py:183` and `:1077`

`post_v1_query_feedback` resolves the run through `_get_owned_run`, which reads the in-process `default_registry`. `run_registry.py:183` sets `DEFAULT_RETENTION_SECONDS = 300.0` and `run_registry.py:1077` constructs `default_registry = RunRegistry()` with that default, and `_evict_expired` (`:681-693`) drops every run finished for longer than that. After five minutes a rating on your own answer returns 404 "no such run", even though `capture_run` wrote a durable `interactions` row for it and `record_feedback` would have accepted the write.

The code discloses this honestly at `app.py:1458-1470` as a "KNOWN GAP, not routed around" with a declared blocked-stop, and I credit that. Two reasons I am still filing it rather than accepting the disclosure:

- It was never filed on the board. `tracker/phase_4.6.md`'s Findings table has ten rows and none of them is this. A limitation that bounds the phase's own deliverable and is known to the builder belongs in the ledger where the product owner reads it, not only in a source comment.
- It starves one of the three inputs the phase's other half depends on. `find_weekly_candidates` (`review.py:141-145`) filters on `user_feedback->>'rating' = 'down'` as one of its three conditions. A considered thumbs-down on a long answer is exactly the feedback that takes more than five minutes to form, and it is the class this window makes unreachable.

There is a second, sharper form of the same coupling worth naming for whoever fixes it: the registry is per-process, so the moment this is deployed behind more than one uvicorn worker, a feedback POST that lands on a different worker than the one that ran the query gets a 404 regardless of elapsed time. Build phase 4.12 is the Railway deployment, which makes this due before then rather than after.

This is the one blocker of the three most likely to be resolved by a product-owner acceptance rather than code. I am marking it BLOCKS because it is reachable and it is not on the board; a recorded acceptance converts it to tracked.

### J-07. MAJOR, not reachable as a product defect, TRACKED. Three controls with no test behind them

Three separate mutations left their suites fully green:

- `EP2`: turning `app.py:1512`'s `FeedbackOwnershipError` handler into a silent 204 leaves `test_feedback_endpoint.py` at `11 passed`. The row-level 403 branch has no arm at all. This is not academic: J-01 is precisely that branch firing in production, and this is why nothing caught it.
- `RV3`: widening `find_weekly_candidates`'s SQL `or_(...)` so it selects every row leaves `test_review.py` at `10 passed`. T-4.6-10's first acceptance criterion, "exactly per stage 3 step 1", is untested. Only the time window is (`RV4` reds `test_find_weekly_candidates_excludes_rows_outside_the_window`).
- `RV5`: deleting the `_is_flagged(row)` re-assertion at `review.py:148` leaves `test_review.py` at `10 passed`. `review.py:95-101`'s docstring says the double-check exists so the SQL and the Python "can never silently drift apart"; nothing asserts they agree, so the guard cannot detect the drift it was written for.

Not blocking: in all three the shipped code is correct today. Filed because the first one is the direct cause of a blocker.

### J-08. MINOR. The dead `feedback` prop was not removed, contradicting F-4.6-08's own fix note

`frontend/src/components/screens/AnswerScreen.tsx:91`

F-4.6-08's fix note states "The dead prop and its import are removed." The import was removed from `App.tsx:82`. The PROP was not:

```
$ grep -n "feedback" frontend/src/components/screens/AnswerScreen.tsx
34:import { FeedbackSurface } from "../feedback/FeedbackSurface";
91:  feedback?: React.ReactNode;
```

`feedback?: React.ReactNode` is still declared, is no longer destructured in the signature (`:220-224`), and is never rendered. `grep -n "feedback\|Feedback" frontend/src/App.tsx` shows no caller passes it. Its justification comment at `:82-88` says it is "Kept in the prop type, rather than removed, only so `App.tsx`'s existing call site ... keeps type-checking until that ticket updates it" — and that ticket has now updated it, so the stated reason has expired.

This is the exact silent-discard trap that WAS F-4.6-08: a declared prop that type-checks and is thrown away on arrival. Leaving it means the next caller who passes `feedback={<X/>}` reproduces the critical with a green type-check.

### J-09. MINOR. A new comment claims the `trace_id` mint that F-4.6-06 deliberately reverted

`src/system_03_search_agent/feedback/contracts.py:64`

```python
# Identity. `trace_id` is server-minted at the Guardrail step (T-4.6-02)
```

This was added by this phase and is false: the mint was reverted and `test_run_capture.py:163` now turns red if anyone re-adds it. This is the `F-2.1-J5-01` liability shape the repository's own `self-eval-loop` rule names, a confident comment asserting a property the code deliberately does not have, and it points the next reader straight back at the change F-4.6-06 exists to prevent.

### J-10. MINOR. `capture_run`'s docstring says "Never raises" and has no try/except

`src/system_03_search_agent/feedback/__init__.py:60-70`

The docstring says "Never raises. A capture failure is logged and dropped." The body has no exception handling; `assemble_interaction` can raise `CallerIdentityRequired` (via `session_row_key`) or a Pydantic `ValidationError`. No product impact today: `run.py:_capture_interaction` catches and logs, and I verified every surface sets `owner_id` (`app.py:1027`, `app.py:1036`, `app.py:1479`, `mcp/server.py:772`, `graphql/schema.py:259`), so the raise is unreachable. But `run.py:180-186`'s own comment already says it "catches anyway rather than trusting that promise", which means the promise is known to be untrustworthy and is still written as a contract.

### J-11. MINOR. The phase's own goal-contract verify item fails

`python tracker/check_doc_drift.py --check` returns `error: 10 facts computed | 14 stale | 0 structural`. The goal contract at `tracker/phase_4.6.md:19` names this command as part of the verify surface. Normally cleared at `/phase-checkpoint`; noted so it is not skipped. Real new counts: 3690 Python tests, 209 frontend tests, 29 Playwright declarations, 360 DECISIONS.md rows, 105 LEARNINGS.md entries.

### J-12. MINOR. F-4.6-09's caveat is not where the reviewer will see it

`docs/build/Feedback_review_ritual.md`. Detail in Grade 4 above. One line in the runbook closes it.

### J-13. MINOR (observation). The regression guard for this phase's own critical is Playwright-only, and there is no CI

`FE1` shows that setting `App.tsx:637` back to `runId={null}` leaves the frontend unit suite at `209 passed`. The only guard is `frontend/e2e/feedback-submission.spec.ts:143`, which does go red (verified). `ls .github/workflows/` returns nothing, so Playwright is manual-run only and the tracked frontend count (209) does not include it. `AnswerScreen.feedback.test.tsx:54` tests `AnswerScreen` with `runId` passed IN; the `App` to `AnswerScreen` seam that WAS the critical has no unit coverage. Recommend one shallow `App` render asserting `runId` reaches `FeedbackSurface`.

### J-14. MINOR (observation). Capture does blocking synchronous database IO on the event loop

`src/system_03_search_agent/feedback/writer.py:152` inside `async def write_interaction`, reached from `run.py:412`. `session_scope` (`data/session.py:45`) is a synchronous generator over a synchronous SQLAlchemy `Session`. Awaiting it from the epilogue blocks the whole event loop, so a slow write delays every other concurrent request on that worker, not only its own. Section 16 stage 1 specifies "a FastAPI background task dispatched after the `done` event is sent", which this is not.

Not filed against this phase: `_remember_turn` (`run.py:267`) established exactly this pattern at build phase 4.5 and it is merged. 4.6 doubles the per-run blocking database work rather than introducing it. Worth an owner before build phase 4.12's deployment.

## Per-ticket status

| Ticket | Status | Evidence |
|--------|--------|----------|
| T-4.6-01 premise gate | PASS with two vacuous arms and three unrun | `17 passed, 3 skipped`. 13 arms mutation-proven red. J-04 (coverage arm vacuous), J-05 (P4's control false), P1b/P9/P12 not run |
| T-4.6-02 server-minted `trace_id` | SUPERSEDED, correctly | Mint reverted per F-4.6-06; property closed structurally by P5 (M5b red) and guarded by `test_run_capture.py:163` (M17 red). Stale comment left behind: J-09 |
| T-4.6-03 capture assembler | PASS offline, UNVERIFIED live | `test_capture.py` 19 arms, CP1 reds 5. All eight Decision G fields present at `capture.py:247-273`. P9, the live completeness arm, did not run |
| T-4.6-04 deterministic `rubric_outcome` | PASS | `rubric.py:52-55`; P11 red on M12; `rubric_score=None` at `capture.py:265` with the reason in code |
| T-4.6-05 `coverage_tags` | FAIL on its own first criterion | `concept:` derivation is real and tested. `predicate:` derivation has no verification at all (J-03) and P12 did not run |
| T-4.6-06 interactions writer | FAIL | ON CONFLICT present and correct; ownership check correct and well mutation-proven (M18, M19, M20, M25). But the F-4.10-A-14 criterion is unimplemented and now produces J-01 |
| T-4.6-07 epilogue dispatch | PASS | All four dispatch sites present and individually red under M1, M14, M15, M16. P6 proves it never fails a query (M7 red) |
| T-4.6-08 feedback endpoint | PARTIAL | Body validation, 409 race and registry ownership are real (EP1, EP3 red). The 403 branch is untested (J-07) and the durable-lookup gap is J-06 |
| T-4.6-09 frontend surface | PASS | Playwright `3 passed`, 10 axe checks; stub registry entry removed; `phase48Premise.test.tsx` updated. FE2 reds 8 arms. Caveats J-08, J-13 |
| T-4.6-10 weekly review ritual | PARTIAL | Real script with a real CLI; human-terminal gate structural and red under RV2. Its primary filter is untested (J-07: RV3, RV5) |
| T-4.6-11 few-shot promotion | PASS | Both destination files created with scope notes; Section 17 shapes; idempotent; the verbatim-copy privacy gate is real (`promotion.py:295`) and PR1 reds the approve gate |
| T-4.6-12 runbook | PASS | `docs/build/Feedback_review_ritual.md` exists and is indexed at `CLAUDE.md:60` and `AGENTS.md:60`. Missing the J-12 caveat |

## What I could not verify, and why

Each of these is a FAIL for the thing named, not a pass.

1. P1b, P9 and P12, the three live premise-gate arms. The Layer 1 graph tunnel is down (`preflight.py`: `graph down TCP 15432: ConnectionRefusedError`) and my attempt to open the SSH forward was denied by the permission layer. Per `.claude/rules/sandbox-diagnosis.md` this is a Layer-4 failure that `/sandbox` cannot address. Consequence: the live half of the phase premise, all four live-only Decision G fields, and the entire `predicate:` coverage-tag path are unverified.
2. The MCP, GraphQL and CLI adapters' own transports. The gate's coverage statement already declares this omission and I did not close it; P2 parametrises `RequestContext.surface` in-process only. I did verify by reading that all three set `Query.owner_id` and route through `run()`.
3. Concurrency. Two runs finishing on one session at the same instant. The gate declares this omission and I did not test it. J-05 makes it worse than declared: the ON CONFLICT clause is the design answer, and the arm meant to protect it cannot see it disappear.
4. The eight-failure baseline's SIX pre-existing failures in `test_citation_trust_full_premise.py`. I took the brief's word that they predate the branch and did not re-measure at the branch point, per F-4.6-10's warning about the shared database. I independently confirmed the OTHER two are caused by this branch (M24).

## Mutation harness note

All mutations were applied to the working tree by literal string replacement with an assertion that the pattern occurred exactly once, and restored by file copy. Restoration was verified after each destructive check (for example, after the P4 probe: `RESTORED` then `grep -c 'on_conflict_do_nothing(index_elements=\["trace_id"\])'` returned `1`; after the coverage-statement probe, `wc -l` returned `997`). The working tree is byte-identical to how I found it.
