# Build phase 4.5 judge report: personalization and session memory

Round: judge (stage 8), run 2026-08-20, AFTER the merge of PR #52
Diff under review: merge base `bddd970` to merge commit `1f70fc3`, eleven commits
Reviewer: independent judge, fresh context, no part in writing the phase

## What this report is

Stage 8 never ran for build phase 4.5. The code merged with no judge round and no adversary round, and every fix and every test on the branch was written by the same agent that wrote the code. This is that missing check, run after the fact.

Because the phase is already merged, this is not a merge gate. It is a defect ledger, and its one decision is whether a fix branch is required before build phase 4.6 opens. The verdict is at the bottom. It is: yes, and two of the findings are criticals on the live answer path.

Method note, stated so a reader can weigh the evidence rather than take it on trust. No live model call and no live graph query was made; nothing here cost money. Five findings were confirmed by EXECUTING the shipped code offline and their probes are quoted inline: F-4.5-J-01, F-4.5-J-02, F-4.5-J-03, F-4.5-J-19, F-4.5-J-20, plus the skip-count in F-4.5-J-07 and the no-over-budget-block check in T-4.5-03. The rest are established by reading the source and by grep over call sites, which is stated in each finding. F-4.5-J-18 is explicitly UNMEASURED and says so.

## Table of contents

- [What this report is](#what-this-report-is)
- [Per-ticket grades](#per-ticket-grades)
- [Premise gate vacuity audit](#premise-gate-vacuity-audit)
- [Tracker claims checked against the code](#tracker-claims-checked-against-the-code)
- [Prompt-cache stable prefix](#prompt-cache-stable-prefix)
- [Retry safety and cost on the second Synth call](#retry-safety-and-cost-on-the-second-synth-call)
- [Findings ledger](#findings-ledger)
- [Verdict](#verdict)

## Per-ticket grades

Graded against each ticket's OWN stated acceptance criteria in `tracker/phase_4.5.md`. A criterion that could not be verified from code actually read is UNVERIFIED, never PASS.

### T-4.5-01: Premise gate

| Criterion | Verdict | Evidence |
|---|---|---|
| Gate calls the real model, no mocked tier | PASS | `test_personalization_premise.py:481-497` `_run_once` drives `core.run.run` end to end; the skip predicate at :353 requires a real key |
| Firewall arm: identical claim set, prose differs | PARTIAL | :637 P2 asserts the pinned-disease set against live ground truth (strong). The prose half was split out to P2b at :802 and is xfailed, so the "both halves asserted" criterion is not met as written |
| Default-path arm FIRST, no explicit value | FAIL | :595 P1 passes `audience_depth=default_query.audience_depth` explicitly to `build_synth_messages`, and its live half calls `_ask(...)` whose own default at :488 passes `audience_depth="researcher"` into `Query`. `build_synth_messages`'s own default parameter is exercised by nothing. Worse, P1's "carries no session memory" premise is unenforced: see F-4.5-J-11 |
| Memory arm asserts the CURIE reached | PASS | :857 P4 asserts `BRCA1 in answer.plan_narrative` with a negative control at :896 |
| Anti-citation arm constructed so it CAN fail | FAIL | :909 P5 is unfalsifiable. See F-4.5-J-05 |
| Contradiction arm | FAIL | :953 P6 is unfalsifiable by the same mechanism. See F-4.5-J-05 |
| Cap arm against the tokenizer's own count | PARTIAL | :1061 P8 does catch a deleted cap, but its tokenizer half is vacuous. See F-4.5-J-06 |
| Prefix arm byte-identical across depth AND session memory | FAIL | :1028 P7 varies depth only. No test anywhere varies session memory. See F-4.5-J-08 |
| Every arm MUTATION-PROVEN | FAIL | P10 (:1158) cannot go red under any mutation; P5, P6 and P13 likewise. Only F-4.5-02's mutation is recorded as actually applied |
| Coverage statement in the module docstring | PASS | :29-121, and it is unusually honest, naming P2b as the weakest arm |
| Seen failing before T-4.5-02 opened | PASS | Recorded at `tracker/phase_4.5.md:71`, 12 failed 2 passed, with per-failure causes |

### T-4.5-02: The SessionMemorySummary contract

| Criterion | Verdict | Evidence |
|---|---|---|
| Three models with Section 14.3's field names, types, caps | PASS | `contracts/query.py:45-160`, all three present with the declared caps |
| `Query.session_memory` typed, placeholder and validator removed in the same change | PASS | `contracts/query.py:194`; the `SESSION_MEMORY_MAX_SERIALIZED_LENGTH` constant and `_bound_session_memory_size` are both gone in the same diff |
| Tests for valid, invalid, null on each model | FAIL | `tests/.../contracts/test_query.py` (33 passed in 0.04s, run by this judge) has no test that constructs `ResolvedEntity` or `CompressedFinding` directly to assert rejection of a missing required field or an over-length string. All coverage is indirect, through `SessionMemorySummary`'s list-level tests |
| `max_length` on every string, cap on every list | **FAIL** | `contracts/query.py:81-84`: `CompressedFinding.citation_ids` caps the list at 5 and does NOT cap the item strings. F-4.5-J-19. The per-item `open_threads` validator at :151-160 shows the author knew a list cap is not a string cap, and the same treatment was not given to `citation_ids` |
| The four adapters accept and reject the same inputs as before | UNVERIFIED | The adapter tests were changed in this same diff, so "same as before" is not established by them. No before/after comparison exists |

### T-4.5-03: build_session_context and the hard token cap

| Criterion | Verdict | Evidence |
|---|---|---|
| Cap counted with the receiving tier's real tokenizer | PASS in code, UNGUARDED | `session_memory.py:72-97` calls `litellm.token_counter`. No test can tell it from a character count: F-4.5-J-06 |
| Enforced before injection, cannot return an over-budget block | PASS | `session_memory.py:193-231`. Verified by probe: a summary whose single finding cannot fit any budget returns `""`, length 0, rather than an over-budget block |
| Over-budget on entry is compacted, not truncated mid-entry | PARTIAL | `compact` at :130 operates on whole entries and `_render`'s `entity_limit` cuts at entry boundaries at :104-113. But the findings merge at :176-180 ends `f"{oldest}; {second}"[:280]`, a raw character slice that can cut the second claim mid-word with no disclosure, unlike the entity path which discloses via `_OMITTED_TEMPLATE` |
| Tests pin the boundary: at budget, one token over, far over | FAIL | Only "far over" exists (P8 at :1061, 50 entities plus 10 threads). No at-budget case, no one-token-over case, and no `tests/.../core/test_session_memory.py` exists at all |

### T-4.5-04: Append and compaction

| Criterion | Verdict | Evidence |
|---|---|---|
| Compaction order exactly Section 14.3's | PASS | `session_memory.py:167-189`: threads loop first, then the findings merge loop |
| `resolved_entities` never dropped for budget, FIFO past 50 | PASS | `session_memory.py:150-152`, and the render-time cut at :104 is disclosed by `_OMITTED_TEMPLATE` rather than silent |
| Append idempotent or repeat-safe | **FAIL once compaction has merged** | `merge_turn` at :427-476 dedups findings by `(trace_id, claim_summary)`, and `compact` at :176-188 rewrites `claim_summary` when it merges. Replaying the same turn then re-adds the originals and the content duplicates in place, growing on every replay. Reproduced by this judge. F-4.5-J-20 |
| A test that catches the WRONG compaction order | PASS, with a wrong justification | P9 at :1096 does go red under a reversed order, via its `len(compacted.open_threads) < len(threads)` assertion. Its docstring's stated reason ("any other order also fits") is false: merging findings alone can never fit budget 400 against ten 180-char threads. The arm is sound, the comment explaining why is not |

### T-4.5-05: Storage and ownership binding

| Criterion | Verdict | Evidence |
|---|---|---|
| Alembic revision adds the column, rollback verified | PARTIAL | `alembic/versions/0007_session_memory.py:47-54`, `sessions.memory` JSONB nullable, downgrade drops it, and it matches `data/models.py:165`. `tracker/BOARD.md:67` records one manual up-and-down run. But no column-level test exists, breaking this repository's own established pattern for column-only migrations (`test_auth_sessions_has_the_absolute_expiry_column`, `test_guest_sessions_has_the_attempt_counter_column`), which exist precisely because the table-level `ALL_TABLES` check cannot see a column. F-4.5-J-21 |
| A session with non-null `user_id` readable only by that user | PASS | `session_memory.py:420` |
| A guest session's memory never served to a caller that cannot present the identity that created it | **FAIL, CRITICAL** | `session_memory.py:420` compares `None != None`. Proven by probe: an unrelated anonymous caller reads another guest's memory. F-4.5-J-02 |
| Refusal tested on every surface accepting a caller-supplied `session_id` | FAIL | P11 at :1188 exercises `load_for_caller` directly with an injected store. Zero surface-level tests: `grep -rn "SessionOwnershipError" tests/` returns nothing outside that one arm |
| The error says what to do next | PASS | `session_memory.py:376-381`, asserted at :1224 |
| F-4.1-A-15 marked closed on BOARD.md with this ticket as evidence | PASS | `tracker/BOARD.md:67` |

### T-4.5-06: Inject memory into Think and Plan, and nowhere else

| Criterion | Verdict | Evidence |
|---|---|---|
| Block appends to the dynamic suffix, never the system block | PASS | `core/graph.py:921` and :1764 both append to the user content; the system content is a constant |
| `prefix_sha256` byte-identical across two requests differing only in session memory | FAIL | No such assertion exists anywhere. F-4.5-J-08 |
| Never injected into Act | PASS in code, UNGUARDED | Two call sites only, both verified by grep. The arm that claims to guard it cannot. F-4.5-J-04 |
| Never injected into Write as a citable source | PASS in code, UNGUARDED | Same. F-4.5-J-05 |
| A relevant `compressed_finding` re-verified by a scheduled Act step or a cached `tool_result` | FAIL | Not built. `compressed_findings` are rendered into the Think and Plan text at `session_memory.py:118` and nothing ever schedules a re-verification. The contract type carries `trace_id` for this purpose and no code reads it |
| Memory sourced from where entities are actually resolved | PASS | `contracts/events.py:144-158` adds `PlanPayload.resolved_entities`; `core/run.py:_remember_turn` reads it |
| (not a stated criterion, but the mechanism this ticket owns) | **CRITICAL DEFECT** | `core/graph.py:1726-1730` lets memory defeat the unresolved-entity refusal. F-4.5-J-01 |

### T-4.5-07: Thread audience_depth into Write

| Criterion | Verdict | Evidence |
|---|---|---|
| `build_synth_messages` renders the directive into the USER message | PASS | `synthesis/findings.py`, the `f"{directive}\n\n"` prefix on `user_content` |
| `SYNTH_SYSTEM_INSTRUCTION` unmodified by depth, byte-equality proved across all three depths | PASS | P7 at :1028 hashes the system block across all three depths |
| Depth never changes retrieval, cite-or-refuse, or trust calculation | PARTIAL | Retrieval and cite-or-refuse are untouched. The trust calculation IS now changed on the answer path, though not by depth: the completeness repair floors `trust_outcome` at `ask` at `core/graph.py:4403-4407`. See F-4.5-J-18 |
| `clinical_brief` still obeys the forbidden-output boundary | PASS | P3 at :835, and it is honestly labelled a regression guard on the guardrail's own control |
| Default remains `researcher` on every surface | PASS | `contracts/query.py`, `web_sse/app.py:263`, `mcp/server.py:717`, `graphql/schema.py:291`, CLI `--depth` |

### T-4.5-08: Depth persistence

| Criterion | Verdict | Evidence |
|---|---|---|
| Depth defaults to the user's last-used value, stored on the user row | FAIL at the server | `write_audience_depth` is called on the query path (`web_sse/app.py:955-961`), but `read_audience_depth` is called only from `GET /auth/me` (`auth/router.py:623`). `post_v1_query` never reads it; `CreateRunRequest.audience_depth` defaults to the hardcoded literal `"researcher"` at `app.py:263`. The round trip works only because one client re-echoes it. A CLI, GraphQL, MCP or bare API caller that omits the field gets `researcher` regardless of what the account stored |
| Before auth, it defaults per session | FAIL | Not implemented. No per-session depth store exists; `alembic 0007` adds only `sessions.memory`, and `SessionMemorySummary` has no depth field |
| Always overridable per query | PASS | Every surface accepts it explicitly |

### T-4.5-09: The curated persona list and the draw

| Criterion | Verdict | Evidence |
|---|---|---|
| Versioned file, roughly 30 deceased names, contribution recorded | PASS | `data/personas_v1.json`, 32 entries, each with a `died` year |
| Loaded once at process start | PASS | `core/persona.py:72`, `@lru_cache(maxsize=1)` |
| Storage, draw and consumers sized for 100 | FAIL | The draw is `int.from_bytes(sha256(identity)[:8]) % len(personas)` at `core/persona.py:146`. Extending the file changes the modulus, which reassigns a different persona to essentially every existing identity. Sized for 100 in the file, not in the mechanism |
| `users` gains a persona column via an alembic revision with verified rollback | **FAIL** | No such column and no such revision. `grep -rn "persona" alembic/` returns zero matches; `data/models.py` has no persona field |
| Drawn once at first login and STORED, never reassigned | **FAIL** | Nothing is stored. It is recomputed per request, and F-4.5-J-10 shows it is not stable across a list extension |
| A test asserts deceased-only against the file | PARTIAL | P12 at :1284 asserts a `died` field is present and truthy. It cannot verify the person is actually dead, which the arm's own docstring concedes |

### T-4.5-10: Wire the persona to all four surfaces

| Criterion | Verdict | Evidence |
|---|---|---|
| `_STUB_PERSONA_NAME` removed from web_sse | PASS | Removed in the diff; only a historical comment remains |
| `_PERSONA_NAME` removed from graphql/fold.py, one source | PASS | Both surfaces import `core.persona` |
| CLI status line carries the persona, closing F-4.2-03 | PASS | `adapters/cli/render.py:508` and :564-566; `adapters/cli/main.py:839,875` |
| Frontend chip renders `persona_name` from the response, `PLACEHOLDER_PERSONAS` removed | PASS | No match for `PLACEHOLDER_PERSONAS` or a live `drawPersona` anywhere in `frontend/src` |
| Stub cleared from `frontend/src/stubs/registry.ts` | PASS | 16 lines removed in the diff |
| Name reaches the caller once, never repeated on every streamed event | PASS in code, WEAKLY GUARDED | `web_sse/app.py:1020-1030` returns it on the response body. P13's assertion is made against `run()`'s events, a layer that never carried it. F-4.5-J-17. Separately, `GET /v1/persona` disagrees with `POST /v1/query` for a signed-in user: F-4.5-J-12 |

### T-4.5-11: The AudienceDepthToggle component

| Criterion | Verdict | Evidence |
|---|---|---|
| Three-way control mirroring `Query.audience_depth`, defaulting to researcher | PASS by a pre-existing component | No `AudienceDepthToggle` exists. `frontend/src/components/controls/DepthControl.tsx` is the control, and `frontend/src/phase48Premise.test.tsx:782` records that it already existed before this phase |
| Disabled once a run has started and is mid-stream | UNVERIFIED | Not established by anything read |
| Change applies to the NEXT query, not the running one | UNVERIFIED | Not established by anything read |
| WCAG 2.1 AA checked in both themes | UNVERIFIED | No accessibility check for this control was found. A claim is not a check |
| Built against the design-system component card | UNVERIFIED | The component predates this phase |

The honest summary of this ticket: it was closed by work that had already shipped in build phase 4.8. What this phase actually added was the `/auth/me` seeding at `frontend/src/App.tsx:241-245`.

### T-4.5-12: Resolve the canned follow-up pronoun

| Criterion | Verdict | Evidence |
|---|---|---|
| The follow-up resolves against session memory | PASS | `core/graph.py:1726-1728`, and P4b at :985 exercises it end to end with nothing handed in |
| A follow-up with no memory degrades to a clarifying question, not a confident answer about the wrong entity | **FAIL** | The inverse case is worse and is live: with memory available and a NAMED entity that does not resolve, the system answers confidently about the wrong entity. F-4.5-J-01 |
| F-4.8-A-22 marked closed on BOARD.md | PASS | `tracker/BOARD.md:67`, recorded as "mechanism CLOSED" |

## Premise gate vacuity audit

The question asked of every arm: if the control this arm names were deleted from the real source, would this single arm go red?

| Arm | Control it names | Deleting that control turns it red? | Verdict |
|---|---|---|---|
| P1 (:595) | Depth routing into the Synth user message | Yes for the directive half. But the arm's second premise, "carries no session memory", is not enforced at all | PARTIALLY VACUOUS, F-4.5-J-11 |
| P2 (:637) | Depth never changes the fact set; an omission must be disclosed and floored | Yes. Pinned to live ground truth, so all three depths agreeing on a wrong answer still fails. The strongest arm in the file | SOUND |
| P2b (:802) | Depth is not inert | Yes in principle, but it is a directional length test an inert control satisfies by coin flip, and it is xfailed at a measured 1.13 against a 1.4 threshold | WEAK, honestly labelled |
| P3 (:835) | The guardrail's forbidden-output boundary | Yes, but the control is the guardrail's and predates this phase | SOUND as a regression guard, not evidence of this phase |
| P4 (:857) | Memory-to-Plan reference resolution | Yes. The negative control at :896 is what makes it falsifiable, and it is correctly constructed | SOUND |
| P4b (:985) | That anything ever WRITES memory | Yes. The only arm that obtains memory the way production does | SOUND, and the most valuable arm added |
| P5 (:909) | "Memory never becomes a citation" | **No.** There is no code path from memory to a citation to delete, and even injecting memory into Synth would not turn it red, because the grounding pass strips any claim with no matching finding | **VACUOUS**, F-4.5-J-05 |
| P6 (:953) | "Retrieval beats memory on a contradiction" | **No.** Same mechanism. `"999"` cannot reach the narrative because ungrounded sentences are stripped before emission | **VACUOUS**, F-4.5-J-05 |
| P7 (:1028) | Depth routed to the suffix, not the system block | Yes: moving the directive into the system block makes the three digests differ. But it covers only half its stated criterion, since it never varies session memory | SOUND but INCOMPLETE, F-4.5-J-08 |
| P8 (:1061) | The hard cap, and the real tokenizer | Cap half: yes. **Tokenizer half: no.** The assertion calls the same `count_tokens_for_tier` the implementation calls, so replacing `litellm.token_counter` with `len(text)//4` leaves it green | **HALF VACUOUS**, F-4.5-J-06 |
| P9 (:1096) | Compaction order | Yes, via the threads assertion. Its docstring's justification is wrong but the arm works | SOUND |
| P10 (:1158) | "Memory never reaches Act" | **No.** `injected_steps` has exactly one definition and ZERO production call sites; `core/graph.py:1665` says so in a comment. Adding `_memory_suffix(state, "act")` to `act_node` leaves this arm green | **FULLY VACUOUS**, F-4.5-J-04 |
| P11 (:1188) | The ownership decision | Yes for account-vs-account. Its five cases are arranged around the one hole they do not cover, guest-vs-guest | SOUND BUT HOLED, F-4.5-J-02 |
| P12 (:1284) | A persona entry with no recorded death year | Yes for a missing field. Cannot verify actual death | WEAK, honestly labelled |
| P13 (:1309) | "Delivered once, never on a streamed event" | **No.** It asserts absence on `run()`'s events, a layer that never carried the persona. The adapter is where the name is added and where a repeat would occur, and the arm never touches it | **VACUOUS**, F-4.5-J-17 |

Count: 3 fully vacuous arms (P5, P6, P10), 1 half vacuous (P8), 1 partially vacuous (P1), 1 incomplete against its own criterion (P7). Two of the three fully vacuous arms are the ones covering Section 14.1's firewall on the memory side, which is the property the gate's own docstring calls "the CENTRAL premise here".

Both shapes named in the brief are present. The "arm supplies the thing under test" shape survived F-4.5-09's fix: P4b was added and it is genuinely good, but P5, P6, P8, P9, P10 all still construct their own input, and for P5 and P6 that is precisely why they cannot fail. The "explicit value so the default path is exercised by nothing" shape is present in P1, whose live half passes `audience_depth="researcher"` through `_ask`'s own default at :488.

One further gate-integrity issue, separate from vacuity. Run by this judge with no tunnel and no key:

```console
$ venv/bin/python -m pytest tests/system_03_search_agent/core/test_personalization_premise.py -q
2 passed, 14 skipped in 0.03s
```

P7, P8, P9, P10 and P12 need neither a graph nor a model. They are pure-function tests, and they run in 0.03 seconds. All five are marked `@premise_gate` and therefore skip on any machine without a live tunnel and a live key. P11's own docstring argues the exact opposite position for itself, "A skipped security check is worse than a fast one", and that reasoning was not extended to the five arms it applies to equally. Combined with the absence of any `tests/.../core/test_session_memory.py`, the practical always-on coverage of this phase's 500-line memory module is one ownership arm. F-4.5-J-07.

## Tracker claims checked against the code

`tracker/phase_4.5.md` is a claim, not evidence. Six claims were checked directly.

| Claim | Where | Holds? |
|---|---|---|
| "thirteen premise arms plus one retry-safety test" | :70 | NO. Fifteen test functions plus the retry-safety test. Minor, but the tracker's own count of its verify surface is wrong |
| "Every arm has been MUTATION-PROVEN... seen going red" | :65 | NO. Only F-4.5-02's mutation is recorded as applied, and it was free because the control was already absent. P5, P6, P10 and P13 cannot be seen going red because no mutation exists that turns them red |
| "The repair is kept only when it is a STRICT improvement. A regeneration that recovered the missing rows but dropped others... is discarded" | :382 | NO. The guard at `core/graph.py:4338` compares COUNTS, not sets. F-4.5-J-13 |
| "It sits inside the same try block as the first call so a cap hit... takes the identical, already-tested path" | `core/graph.py:4279-4282` | NO. The repair is outside that try/except and carries its own. F-4.5-J-14 |
| "A question that names its own gene is never overridden by an older one from memory" | `core/graph.py:1719-1721` | NO, when the named gene fails to resolve. F-4.5-J-01 |
| "keyed exactly as `POST /v1/query` keys it, so the name shown on the landing screen is the one the first answer will carry" | `web_sse/app.py`, the `GET /v1/persona` comment | NO for any signed-in user. F-4.5-J-12 |

Five of six load-bearing comments assert a property the code does not have. This is the `self-eval-loop` "review a fix harder than new code" pattern, and specifically its second practice: a confident comment is exactly where the next reader stops checking.

The tracker is honest in one important respect and it deserves saying: F-4.5-09 is a genuinely excellent self-finding, written up without softening, and P4b is the right fix for it.

## Prompt-cache stable prefix

The obligation holds in code and is only half asserted.

- Depth: correct. `synthesis/findings.py` puts the directive on `user_content`; the system message is `SYNTH_SYSTEM_INSTRUCTION` unchanged. P7 at :1028 proves it by SHA-256 across all three depths, and the arm is non-vacuous: putting the directive in the system block makes the digest set size 3 and turns it red.
- Session memory: correct in code. `core/graph.py:921` and :1764 both append `_memory_suffix(...)` to the user content, and the system content at both sites is a module constant.
- The assertion for the memory half does not exist. `grep -rn "prefix_sha256" tests/` returns exactly one hit in this gate, P7, which varies depth only. T-4.5-01's criterion says "differ in depth and in session memory"; T-4.5-06's says "byte-identical across two requests differing only in session memory, asserted directly". Neither is met. F-4.5-J-08.

## Retry safety and cost on the second Synth call

Checked against the three questions in the brief. This part of the repair is, on the whole, correctly built.

- Does it respect the per-query cost cap? YES. `_dispatch_tier_call` at `core/graph.py:591-613` runs `cost_control.check_per_query_cap` as a pre-flight before every dispatch, and the repair goes through it like every other call. A query already at its cap cannot spend the repair call.
- Does a repair failure leave the answer in a defined state? YES. `core/graph.py:4321-4326` catches both `QueryCapExceededError` and `HarnessCallError`, sets `repaired_text = None`, keeps the original grounded answer, and leaves `omitted_findings` unchanged so the disclosure at :4403 still fires and the outcome is still floored. This is the right shape.
- Can it fire more than once? NO. One `if omitted_findings:` block, no loop, no recursion.

Two problems remain in the same code:

- The repair block's own comment claims it sits inside the first call's try block and takes "the identical, already-tested path". It does not, and the paths differ materially: a cap hit on the FIRST call returns `_partial_result_for_cap`, while a cap hit on the REPAIR is swallowed and the query completes normally, reporting a `total_cost_usd` that has passed the cap with no cap signal to the caller. The swallow is defensible; the comment describing it is wrong. F-4.5-J-14.
- The whole mechanism has no deterministic test. `grep -rn "unreported_findings\|build_completeness_directive\|incomplete_answer_note" tests/` returns exactly one hit, a fingerprint string constant at :192. A second Synth call on the answer path, a discard rule, and a `trust_outcome` floor all shipped with zero unit tests. F-4.5-J-09.

## Findings ledger

### F-4.5-J-01: session memory defeats the unresolved-entity refusal, and the system answers about the wrong gene

Severity: **CRITICAL**, in the product
File: `src/system_03_search_agent/core/graph.py:1726-1730`

```python
target_curies = resolution.curies
if not target_curies and memory_curies:
    target_curies = list(memory_curies)
elif not resolution.curies and resolution.unresolved_symbols:
    return _UnresolvedEntityRefusal(attempted_symbols=resolution.unresolved_symbols)
```

The `elif` is the defect. When this turn resolved nothing, has a gene-shaped token a live lookup confirmed does not exist, AND memory holds any CURIE, the first branch wins and the refusal never runs.

What breaks: T-3.1-13 / F-2.1-B10's deterministic refusal is a safety control. It exists precisely so the loop refuses BEFORE dispatching a query when a named entity was tried and NCBI does not know it. Memory now silently defeats it, and the query is dispatched against a DIFFERENT entity than the one the user named.

Triggering sequence, exact:
1. Turn 1, any session: "Which diseases are associated with BRCA1?" Memory records `NCBIGene:672`.
2. Turn 2, same session: "Which diseases are associated with BRCA9?" (`BRCA9` is gene-symbol-shaped and does not resolve.)

Confirmed by executing the shipped function with `_resolve_query_entities` stubbed to the resolution it actually returns for an unknown symbol:

```text
WITH memory    -> _PlannedToolCall  target_entities=['NCBIGene:672']
WITHOUT memory -> _UnresolvedEntityRefusal  attempted_symbols=['BRCA9']
```

Identical question, identical code, and the only difference is whether the session remembers anything. The answer that comes back is grounded, correctly cited, and about a gene the user did not ask about. That is the confident wrong answer this product exists to avoid, and the citations make it more convincing rather than less.

Why it is real rather than theoretical: mistyped and obsolete gene symbols are the single most common thing a user gets wrong in this domain, the refusal was built specifically for them, and the trigger is a follow-up question in an ordinary session. The code comment three lines above states the opposite property as if it held: "A question that names its own gene is never overridden by an older one from memory, which would be memory silently answering a different question than the one asked." That is exactly what happens, whenever the named gene fails to resolve.

No gate arm covers it. P4 (:857) tests a pronoun with no competing symbol; nothing tests a NAMED-but-unresolvable symbol with memory present.

### F-4.5-J-02: any guest can read and overwrite any other guest's session memory

Severity: **CRITICAL**, in the product
Files: `src/system_03_search_agent/core/session_memory.py:420` and `:496`; `src/system_03_search_agent/adapters/web_sse/app.py:966`

The ownership check is `if (owner_id or None) != (user_id or None): raise`. Every anonymous caller has `user_id = None`, and every guest-owned session row has `owner_id = None`, so `None != None` is False and the check passes.

Confirmed by executing `load_for_caller` against a store returning an anonymous-owned session:

```text
anon caller reading another anon session -> LEAKED: NCBIGene:672
WROTE to guest-1 as None
```

The write path leaks the same way, so this is not only disclosure. An attacker can `save_for_caller` into another guest's session and plant a CURIE, and the victim's next turn with an unresolvable reference will bind to it through F-4.5-J-01's path. Read plus write plus F-4.5-J-01 compose into steering another user's answer.

Reachable on the live surface. `web_sse/app.py:966` builds `Query(user_id=caller.user_id, ...)`, and for a guest `caller.user_id` is None; only `caller.owner_id` carries the `guest:<uuid>` identity that build phase 4.10 already mints. The distinguishing identity exists and is not used.

Exploitability is not gated on guessing a UUID. `adapters/cli/main.py:836` reads `args.session_id or uuid.uuid4().hex`, so `--session-id` is a documented user-supplied flag; the MCP surface accepts any string up to 64 characters; and low-entropy ids are exactly what programmatic and scripted callers produce. Two unauthenticated callers who both use `--session-id shared`, or `default`, or `test`, share one conversation's memory. The gate's own arms use the literal `"premise-gate-4-5"`.

T-4.5-05's third criterion states the requirement in words this fails against directly: "A guest session's memory is never served to a caller that cannot present the identity that created it."

P11 (:1188) has five cases and covers account-vs-account, anon-store-vs-auth-caller, auth-store-vs-anon-caller, and unknown-session. The one case it does not construct is `_Store(None)` with `user_id=None`, which is the hole.

### F-4.5-J-03: eleven remembered entities crash the query

Severity: MAJOR, in the product
Files: `src/system_03_search_agent/core/graph.py:1727`; `src/system_03_search_agent/tools/cypher_schemas.py:66-69`

`_memory_curies` returns up to `MAX_RESOLVED_ENTITIES = 50` CURIEs. Line 1727 assigns the whole list to `target_curies` with no cap. `CypherQueryInput.target_entities` carries `max_length=10`.

Confirmed by probe: 10 accepted, 11 and 50 both `ValidationError`, and calling the shipped `_select_planned_tool_call` with eleven memory CURIEs and a pronoun question raises rather than returning.

`_select_planned_tool_call` is called at `core/graph.py:1772`, OUTSIDE `plan_node`'s try/except, which catches only `QueryCapExceededError` and `HarnessCallError`. The `ValidationError` propagates out of `ainvoke` into `run()`'s last-resort catch and the caller receives the synthetic pair: `"This query failed unexpectedly before it could complete."` with zero real events and `trust_outcome="refuse"`.

Triggering sequence: any session that accumulates eleven distinct resolved CURIEs (eleven substantive turns, or fewer turns naming multiple genes each), then any turn that resolves nothing on its own. That last turn is exactly the canned follow-up chip T-4.5-12 exists to serve. Long sessions are the ones memory is FOR, so the feature fails hardest in the case it was built for, and it fails as a mystery: the crash message names nothing.

There is a second, milder defect in the same line. Even under 10, the pronoun binds to EVERY entity the session ever resolved, not the most recent one. "What variants cause it?" after discussing BRCA1 and TP53 queries both. A pronoun has one antecedent.

### F-4.5-J-04: P10 cannot detect memory reaching Act, which is the only thing it exists to detect

Severity: MAJOR, in the gate
Files: `tests/.../test_personalization_premise.py:1158-1183`; `src/system_03_search_agent/core/session_memory.py:232-245`; `src/system_03_search_agent/core/graph.py:1665`

P10 asserts `set(injected_steps(memory)) == {"think", "plan"}`. `injected_steps` returns the module constant `_INJECTED_STEPS` and discards its argument (`del summary`).

`grep -rn "injected_steps" src/ tests/` returns: the definition, the `__all__` entry, two comments, and the test. ZERO production call sites. `core/graph.py:1665` states it outright: "`injected_steps` is not consulted here to decide WHETHER to inject; the two call sites are Think and Plan by construction."

So the mutation that matters, adding `query.text + _memory_suffix(state, "act")` inside `act_node`, leaves P10 green. The arm asserts a constant equals itself. T-4.5-06's "Never injected into Act" criterion is unguarded, and the gate's coverage note lists "Memory never reaching Act (P10)" as exercised.

This is not theoretical: build phase 4.7 is scheduled to move entity resolution from Plan to Think, which means someone will edit these injection sites, and the arm meant to catch a third site appearing will not fire.

### F-4.5-J-05: P5 and P6, the two arms covering the memory-side firewall, cannot fail

Severity: MAJOR, in the gate
Files: `tests/.../test_personalization_premise.py:909-951` and `:953-983`

P5 asserts a fabricated memory claim ("BRCA1 is associated with Wilson disease") never appears in `claim_text` on a citation. P6 asserts a fabricated count ("999") never appears in the narrative.

Neither can go red under any mutation, for two independent reasons stacked:

1. There is no code path from `SessionMemorySummary` to `write_node`. `_memory_suffix` has exactly two call sites (`core/graph.py:921`, `:1764`), both before Act. There is no control to delete.
2. Even the strongest mutation, splicing the memory block into `build_synth_messages`, would not turn either arm red. Citations are built from `grounding.claims`, which are produced by `run_grounding_pass` over `synth_findings`. A claim with no matching finding is stripped before it can become a citation or reach the narrative. This phase's own F-4.5-06 breach 1 measured that exact behavior: forbidding identifiers made every claim fail the substring match and the answer was stripped to a refusal.

So both arms are protected by build phase 2.2's grounding pass, not by anything build phase 4.5 built, and their verdicts carry no information about this phase. The gate docstring's claim for P5, "Constructed so it CAN fail, meaning memory really does hold a claim the current turn's findings do not support", is half right: the memory does hold such a claim, and the arm still cannot fail.

What an arm here would need to do to be worth its runtime: assert on the NARRATIVE as well as citations (P5 checks only `claim_text`), and be constructed against a mutation that is actually available, for example asserting that `build_synth_messages` receives no argument derived from `RequestContext.session_memory`.

### F-4.5-J-06: P8 cannot tell the real tokenizer from a character count

Severity: MAJOR, in the gate
Files: `tests/.../test_personalization_premise.py:1086-1092`; `src/system_03_search_agent/core/session_memory.py:72-97`

P8 does:

```python
block = build_session_context(oversized, tier="plan")
actual = count_tokens_for_tier(block, tier="plan")
assert actual <= oversized.token_budget
```

The assertion calls the same function the implementation calls. Replace the `litellm.token_counter` body of `count_tokens_for_tier` with `len(text) // 4` and both sides move together: the implementation compacts until the character estimate fits, the assertion measures with the same estimate, and the arm stays green.

That is the exact control named first in T-4.5-03's criteria ("Cap counted with the receiving tier's real tokenizer, never a character count, never a client-supplied number") and named in P8's own docstring ("server-side, real tokenizer, never a character count"). The cap half of P8 is sound; the tokenizer half asserts nothing.

Why it matters concretely: `count_tokens_for_tier`'s fallback at :90-97 already returns a character estimate whenever `litellm` cannot map the tier's model to a tokenizer. A tier configuration change that makes that fallback the normal path would silently move the whole system onto character counting, and nothing would report it. The estimate deliberately over-counts, so the cap fails safe, but the criterion asserts the tokenizer is real and no test can confirm it.

### F-4.5-J-07: five arms that need no live resources skip in ordinary CI, and there is no unit test file for the memory module

Severity: MAJOR, in the gate
Files: `tests/.../test_personalization_premise.py:353` (`premise_gate` marker), applied at :1028, :1061, :1096, :1158, :1284

Run by this judge with no tunnel and no key:

```text
2 passed, 14 skipped in 0.03s
```

The two that run are P11 and the retry-predicate test. P7 (prompt-cache SHA-256), P8 (token cap), P9 (compaction order), P10 (injected steps) and P12 (persona list) are pure functions over in-memory data. They complete in hundredths of a second and touch neither the graph nor a model, and all five are gated behind the live-environment skip.

`ls tests/system_03_search_agent/core/` confirms there is no `test_session_memory.py`. So `core/session_memory.py`, 500 lines covering the token cap, the compaction order, `merge_turn`'s idempotence, the uuid5 row mapping and the ownership check, has exactly one test that runs without a live environment.

P11's own docstring makes the argument that should have been applied to all five: "A skipped security check is worse than a fast one." The reasoning generalizes to every arm that needs no live resource, and was applied to one.

Practical consequence: a regression in the compaction order, the token cap, or the prompt-cache prefix ships green on any developer machine and in any CI run without a tunnel.

### F-4.5-J-08: the session-memory half of the prompt-cache assertion does not exist

Severity: MAJOR, in the gate
File: `tests/.../test_personalization_premise.py:1028-1057`

`grep -rn "prefix_sha256" tests/` returns one hit in this gate (P7) plus pre-existing harness tests. P7 varies `audience_depth` across three values and hashes the system block. Nothing anywhere varies `session_memory` and hashes anything.

Two criteria require it explicitly:
- T-4.5-01: "`prefix_sha256` of the assembled stable prefix is byte-identical across two requests that differ in depth and in session memory."
- T-4.5-06: "`prefix_sha256` of the stable prefix is byte-identical across two requests differing only in session memory, asserted directly."

The property does hold today: `core/graph.py:921` and `:1764` both append the block to user content, and both system blocks are constants. The point of `prompt-cache-discipline` is that this failure is silent, so "correct today, unasserted" is precisely the state it forbids. The rule's own words: nothing errors when it breaks, the bill just climbs.

The Think and Plan prompts are also where the injection sites will be edited by build phase 4.7, which makes the missing assertion latent-but-scheduled rather than hypothetical.

### F-4.5-J-09: the completeness repair has no deterministic test

Severity: MAJOR, in the product's verify surface
Files: `src/system_03_search_agent/synthesis/findings.py` (`unreported_findings`, `build_completeness_directive`); `src/system_03_search_agent/core/graph.py:4291-4348`, `:4403-4407`, `_build_incomplete_answer_note`

`grep -rn "unreported_findings\|build_completeness_directive\|incomplete_answer_note" tests/` returns exactly one hit: a fingerprint string constant at :192, used inside P2's conditional disclosure branch.

Untested, all of it: the omission computation, the discard rule at :4338, the repair-failure path at :4321, the `trust_outcome` floor at :4405, and the note's own text and singular/plural handling. The only coverage is P2, which exercises the disclosure branch only when a live model happens to omit a finding on that particular question, and P2 skips without a live environment.

This is the most safety-critical new code in the phase. It fires a second Synth call, it can replace the answer the user sees, and it changes the trust outcome. All three are deterministic, pure-function decisions that could be unit-tested in milliseconds with hand-built `SynthFinding` lists and a stubbed dispatch, and none are.

The specific defect this absence already hides is F-4.5-J-13: a test named "the repair is discarded when it drops a previously reported finding" would have failed on the day it was written.

### F-4.5-J-10: the persona is never stored, and extending the list reassigns every user

Severity: MAJOR, in the product
File: `src/system_03_search_agent/core/persona.py:124-147`

The draw is `int.from_bytes(sha256(identity).digest()[:8], "big") % len(personas)`. Nothing is written anywhere. `grep -rn "persona" alembic/` returns zero matches and `data/models.py` has no persona column.

T-4.5-09 states two criteria this fails:
- "`users` gains a persona column via an alembic revision with a verified rollback." No column, no revision.
- "Drawn once at first login and stored. Never reassigned for the life of the account." Recomputed every request from a modulus over the list length.

The failure is not academic, because the phase's own product decision guarantees the trigger. `tracker/phase_4.5.md:22` records: "the drawing mechanism, the storage column and all four surfaces sized for 100, so a later extension is a data change rather than a code change." Extending `personas_v1.json` from 32 entries toward 100 changes `len(personas)`, which changes `hash % N` for essentially every existing identity. Every registered user wakes up bound to a different scientist. The exact scenario the "sized for 100" decision was made to make safe is the one that breaks it, and no test would catch it: P12 checks the file's contents, not the stability of the mapping across a size change.

### F-4.5-J-11: P1's "carries no session memory" premise is unenforced and self-contaminating

Severity: MAJOR, in the gate
Files: `tests/.../test_personalization_premise.py:488` and `:499` (`_ask`'s defaults), :595 (P1)

`_run_once` and `_ask` both default `session_id="premise-gate-4-5"`, a fixed literal shared by P1, P2 (three runs), P2b (two runs), P3 and P13, all with `user_id=None`.

`run()` calls `_load_session_memory` at `core/run.py`, which loads STORED memory whenever the caller supplied none, and `_remember_turn` writes memory after every run. So from the second execution of this gate onward, P1's live half runs with whatever the previous execution persisted to that session row. Its docstring's premise, "A caller that names no depth and carries no memory is the first turn of every session on every surface", is not what the arm actually exercises.

Three consequences, in order of seriousness:
1. The arm designated "THE DEFAULT PATH, FIRST" is not the default path. This is the shape the file's own coverage note swears off, quoting build phase 4.4.
2. The gate is order- and history-dependent. Results are not reproducible across executions, which makes any future "it passed yesterday" claim unsound.
3. It composes with F-4.5-J-03. The shared session accumulates CURIEs across executions, and if it ever reaches eleven distinct ones, arms on that session start crashing with "This query failed unexpectedly" for a reason that has nothing to do with what they test.

The fix shape is the one P4b already uses at :986: a per-run unique session id.

### F-4.5-J-12: a signed-in user's landing chip names a different scientist than their answers

Severity: MINOR, in the product
File: `src/system_03_search_agent/adapters/web_sse/app.py`, the `get_v1_persona` handler

`GET /v1/persona` calls `persona_for_session(session_id=session_id, user_id=None)` with `user_id` hardcoded to None. `POST /v1/query` calls `persona_for_session(session_id=request.session_id, user_id=caller.user_id)`.

Since the draw is a hash of the identity, an authenticated user gets one name from the endpoint and a different one on every answer.

Reproduction: sign in, load the landing screen (chip shows scientist X), ask one question (response `persona_name` is scientist Y).

The endpoint's own comment asserts the opposite: "The answer is a pure function of the identity, keyed exactly as `POST /v1/query` keys it, so the name shown on the landing screen is the one the first answer will carry." It is keyed on the session only. The comment also correctly identifies why this matters, having rejected a client-side draw on the grounds that "the browser cannot know which scientist an ACCOUNT is bound to, so it would show one name and every other surface would show a different one for the same user." The endpoint reintroduces the defect it was written to avoid, one layer down.

### F-4.5-J-13: the "strict improvement" guard compares counts, not sets, and can drop a finding the first answer reported

Severity: MINOR, in the product
File: `src/system_03_search_agent/core/graph.py:4338-4340`

```python
if repaired_grounding.claims and len(still_omitted) < len(omitted_findings):
```

The comment two lines above claims: "A regeneration that reported the missing rows but dropped others, or that grounded nothing at all, is not an improvement, and accepting it because it is newer would trade a known-incomplete answer for an unknown one."

The code does not implement that. It implements "fewer omissions than before", which is not a superset test.

Concrete sequence, five findings A through E:
- First answer reports A and B. `omitted_findings = {C, D, E}`, count 3.
- Repair reports B, C, D, E. `still_omitted = {A}`, count 1. 1 < 3, so the repair is KEPT.
- Finding A, which the user would have seen in the first answer, is gone from the shipped one.

Bounded rather than critical, because the disclosure at :4403 fires and names the residual scale, and the outcome is floored at `ask`, so the loss is not silent. But the guarantee the comment states is not the guarantee the code provides, and a reader relying on the comment would not check. F-4.5-J-09 is why: a unit test asserting the superset property is what would have caught this on day one.

### F-4.5-J-14: the repair block's comment describes a try/except structure the code does not have

Severity: MINOR, in the product
File: `src/system_03_search_agent/core/graph.py:4279-4282`

The comment states the repair "sits inside the same try block as the first call so a cap hit or a harness failure during the repair takes the identical, already-tested path as the original, rather than introducing a second error contract to keep in sync."

The repair is outside that try. The first call's `except cost_control.QueryCapExceededError` returns `_partial_result_for_cap(...)`. The repair's own `except` at :4321 swallows and continues. Those are different paths with different observable behavior: a cap hit on the first call produces a partial-result response, while a cap hit on the repair produces a complete-looking response whose reported `total_cost_usd` has crossed the per-query cap with no cap signal anywhere in the event stream.

The chosen behavior is defensible and its inner comment explains it correctly. The outer comment is stale and it is exactly the shape `self-eval-loop` warns about: a confident comment asserting a structural property, sitting where the next reader stops checking.

### F-4.5-J-15: T-4.5-08's per-session default is not implemented and the server-side default ignores the stored preference

Severity: MINOR, in the product
Files: `src/system_03_search_agent/adapters/web_sse/app.py:263`, `:955-961`; `src/system_03_search_agent/auth/router.py:623`

`write_audience_depth` is on the query path. `read_audience_depth` is called only from `GET /auth/me`. `CreateRunRequest.audience_depth` defaults to the hardcoded literal `"researcher"`.

So "depth defaults to the user's last-used value" is true only for a client that first calls `/auth/me` and then re-echoes the value on every query, which the web UI does at `frontend/src/App.tsx:241-245` and `:424`. A CLI, GraphQL, MCP or bare REST caller that omits the field gets `researcher` regardless of the account's stored preference. The preference is written by every surface and honored by one.

"Before auth, it defaults per session" is not implemented at all: there is no per-session depth store anywhere. Alembic 0007 adds only `sessions.memory`, and `SessionMemorySummary` has no depth field by design.

### F-4.5-J-16: save_for_caller re-checks ownership between two awaits

Severity: LATENT
File: `src/system_03_search_agent/core/session_memory.py:492-500`

`save_for_caller` awaits `store.get`, evaluates the ownership comparison, then awaits `store.put`. Two concurrent turns of the same session, or a session whose owner changes between the two awaits, can have the check pass and the write land against a different owner.

Correct today: nothing in v1 reassigns a session's `user_id`, and the gate's coverage note at :113-117 explicitly declares concurrency out of scope and assigns it to build phase 6.0. Named here because build phase 4.6's history migration is described in `load_for_caller`'s own docstring as the step that moves a guest session to an account, and that is precisely an owner change between two awaits.

### F-4.5-J-17: P13 asserts persona absence on a layer that never carried the persona

Severity: MINOR, in the gate
File: `tests/.../test_personalization_premise.py:1309-1333`

P13's second half collects `[e for e in answer.events if "persona_name" in (e.payload or {})]` from `_ask`, which drives `core.run.run`. The persona is added by the adapter at `web_sse/app.py:1020-1030`, on the response body, downstream of `run()`. No event produced by `run()` has ever carried `persona_name` and none could.

The mutation that matters, making the SSE surface attach `persona_name` to every streamed event, leaves P13 green because `_ask` never touches the adapter.

Its first half is also weak: `first == second` for two calls to a pure hash function is trivially true and cannot distinguish "drawn once and stored" (the criterion) from "recomputed every call" (what shipped, per F-4.5-J-10).

### F-4.5-J-18: the completeness repair fires on the general answer path, not only on brief answers, with no measurement of how often

Severity: MAJOR, unmeasured
File: `src/system_03_search_agent/core/graph.py:4291-4296`, `:4403-4407`

The gate is `if tool_outcome != "no_tool" and synth_findings:` followed by `if omitted_findings:`. It is not conditioned on `audience_depth`, and `omitted_findings` is every finding handed to Synth whose citation id did not survive grounding.

`build_synth_findings` is called with `max_findings=_MAX_CITATIONS_PER_ANSWER`, which is 20 (`core/graph.py:4222-4224`, `:2257`). So any query whose retrieval produces more citable rows than the answer weaves into prose, which is the normal case for anything broader than the four-disease BRCA1 question, now:

1. Fires a second full Synth call, roughly doubling the most expensive tier's cost for that query.
2. Floors `trust_outcome` at `ask` when the repair does not recover everything.
3. Appends "Note: this answer reports N of the M findings retrieved for it..." to the answer.

Concrete scenario: a TP53 disease question retrieves twelve disease rows plus the gene record. If the answer's prose grounds six of them, six are "omitted", the repair fires, and unless the regeneration reports all thirteen the user gets `ask` plus a disclosure note on a perfectly good answer.

This is filed as major and unmeasured rather than as a defect with a fixed verdict, because it may be exactly what the product owner's Option A decision intended, and settling it needs live measurement this judge deliberately did not run. What is a defect regardless is that the phase shipped a change to the cost profile and the trust semantics of the general answer path with no measurement of its firing rate, no unit test (F-4.5-J-09), and no ticket criterion describing it. T-4.5-07's own criterion says depth "never changes the trust-signal calculation"; the mechanism introduced to serve that ticket changes the answer-level trust outcome for every depth.

### F-4.5-J-19: `CompressedFinding.citation_ids` items are unbounded strings

Severity: MINOR, in the contract
File: `src/system_03_search_agent/contracts/query.py:81-84`

```python
citation_ids: list[str] = Field(
    default_factory=list, max_length=MAX_CITATION_IDS_PER_FINDING
)
```

`max_length` on a `list[str]` bounds the number of items, not the length of each. Confirmed by execution: `CompressedFinding(claim_summary='x', trace_id='t', citation_ids=['A'*1000000])` validates, and the accepted item length is 1,000,000.

T-4.5-02's criterion is "Every string field carries `max_length` and every list carries a length cap, per the multi-agent pipeline gate". This string field carries none, so a `SessionMemorySummary` has no upper bound on serialized size at all: 20 findings times 5 unbounded items. The retired placeholder bound `SESSION_MEMORY_MAX_SERIALIZED_LENGTH = 5000` did bound it, so this is a bound that was removed and not fully replaced.

Scoped honestly: the live blast radius is small today. `_render` at `session_memory.py:104-125` renders `claim_summary` only and never `citation_ids`, so an oversized value cannot reach a model prompt on the current path, and every adapter constructs `RequestContext` with `session_memory=None` (`web_sse/app.py:969`, `mcp/server.py:757`, `graphql/schema.py:311`), so no external caller supplies one. The reachable cost is a JSONB row of arbitrary size on the `sessions` table. Filed as minor for that reason and not lower, because the criterion is explicit and the author demonstrably knew the distinction: `open_threads` gets a per-item validator at :151-160 for exactly this reason, and `citation_ids` did not get the same treatment.

### F-4.5-J-20: merge_turn stops being idempotent the moment compaction merges a finding

Severity: MAJOR, in the product
Files: `src/system_03_search_agent/core/session_memory.py:427-476` (`merge_turn`), `:176-188` (the merge step in `compact`)

`merge_turn` dedups findings on `(trace_id, claim_summary)`. `compact` merges the two oldest findings into a new entry whose `claim_summary` is `f"{oldest}; {second}"`. That new summary is not either original, so the dedup key no longer matches, and replaying the same turn re-appends both originals.

Reproduced by this judge, three identical calls to `merge_turn` with the same turn under a budget that forces the merge:

```text
turn 1 : ['alpha claim text; beta claim text']
replay1: ['alpha claim text; beta claim text; alpha claim text; beta claim text']
replay2: ['alpha claim text; beta claim text; alpha claim text; beta claim text; alpha claim text; beta claim text']
idempotent? False
```

The content duplicates in place and grows on every replay until the `[:280]` slice at :179 silently cuts it, at which point the stored memory is a truncated repetition of itself.

Two things this fails against directly:

- T-4.5-04's criterion: "Append is idempotent or repeat-safe per the retry-safety gate, since the Act step retries and a turn can be replayed."
- The function's own docstring at :434-441: "an entity is keyed by its CURIE and a finding by its `trace_id` plus summary, so folding the same turn twice produces the same summary as folding it once." That holds only until the first compaction, and compaction is not an edge case, it is the mechanism the whole module exists for.

On live reachability, stated rather than assumed because it changes the severity: `_remember_turn` runs once per `run()` and keys findings on `query.trace_id`, and `trace_id` is a server-minted uuid4 per run (`web_sse/app.py:961`), so this judge could NOT establish a path today that replays a turn under a stable `trace_id`. It is filed as major rather than critical for that reason. It is filed as major rather than latent because the invariant is broken now, the docstring asserts it holds, and build phase 4.6 is the named next change: interaction capture writes against the same session row and is the obvious source of a replayed fold. A test asserting `merge_turn(merge_turn(x)) == merge_turn(x)` under a forced-merge budget takes three lines and does not exist.

### F-4.5-J-21: migration 0007 has no column-level test, against this repository's own established pattern

Severity: MINOR, in the verify surface
Files: `alembic/versions/0007_session_memory.py`; `tests/system_03_search_agent/data/test_migration.py`

The migration itself is correct: `sessions.memory`, JSONB, nullable, no server default, a plain `drop_column` downgrade, and it matches `data/models.py:165`. `tracker/BOARD.md:67` records one manual up-and-down run against the live database.

What is missing is the test. `test_migration.py` carries `test_auth_sessions_has_the_absolute_expiry_column` and `test_guest_sessions_has_the_attempt_counter_column`, both of which exist because the module's table-level `ALL_TABLES` check is structurally blind to a column-only migration. Revision 0007 is a column-only migration and got no equivalent. The generic full-chain downgrade test exercises `downgrade()` incidentally, which proves it does not error, not that the column was added and removed as declared.

So the rollback is verified by one person once, on one machine, and not by anything that will run again. T-4.5-05's criterion says "with a rollback verified per the migration gate", and the gate's own established shape for this class of change was not followed.

### F-4.5-J-22: compact makes its drop decisions against the wrong tokenizer for Think

Severity: LATENT
Files: `src/system_03_search_agent/core/session_memory.py:148` (`tier: Tier = "plan"`), `:193` (`build_session_context(..., tier)`), `src/system_03_search_agent/core/graph.py:921`

`compact` hardcodes `tier = "plan"` for every `fits()` decision. `build_session_context` takes the caller's tier and re-measures against it. The Think call site passes `tier="guard"` (`core/graph.py:921`); the Plan call site passes `"plan"` (`:1764`).

The hard cap is still safe, because the final check at `session_memory.py:214` and the entity-shrink fallback at :220-223 both use the caller's real tier. Verified by probe: no path returns an over-budget block.

What is wrong is that for the Think step the compaction DECISIONS, which threads to drop and which findings to merge, are computed against the plan tier's tokenizer rather than the guard tier's. If the two tiers resolve to models with materially different tokenizers, the specified drop order under-shrinks or over-shrinks for Think, pushing work onto the entity-shrinking fallback that Section 14.3's order was written to avoid. Correct today because the two tiers' tokenizers are close enough that no probe distinguishes them; fragile under a guard-tier model swap, which `system-design-patterns` pattern 11 treats as a one-table edit.

## Verdict

**A fix branch is REQUIRED before build phase 4.6 opens.**

Two of the findings are criticals on the live answer path, and both are of the exact class this repository's own standards call worse than a crash.

- F-4.5-J-01 makes the product give a confident, fully cited answer about a gene the user did not ask about, by defeating a refusal control built in build phase 3.1 for exactly that input. One line at `core/graph.py:1726-1730`.
- F-4.5-J-02 hands one anonymous user another anonymous user's conversation, and lets them overwrite it. It is the finding F-4.1-A-15 was boarded for, closed on the board, and still open in the code for the guest half. The identity needed to fix it (`caller.owner_id`) already exists and is not used.

Build phase 4.6 must not open on top of these two specifically, because it inherits both. Its interaction capture writes `interactions.session_id` through the same `session_row_key` mapping and against the same ownership model, so shipping 4.6 on the current model widens a live authorization gap from memory to captured interactions. And its history migration is the operation F-4.5-J-16 names as the one that turns a latent race into a real one.

Counts by severity: **2 critical, 11 major, 7 minor, 2 latent** (22 findings, F-4.5-J-01 through F-4.5-J-22).

The three worst:

1. F-4.5-J-01, critical: with any session memory present, a question naming an unresolvable gene skips the refusal and is answered, grounded and cited, about a different gene entirely.
2. F-4.5-J-02, critical: `(owner_id or None) != (user_id or None)` is False for every guest pair, so any anonymous caller who names another guest's session id reads and can overwrite their memory; proven by executing the shipped function.
3. F-4.5-J-04 with F-4.5-J-05, major: the three gate arms covering "memory never reaches Act", "memory never becomes a citation" and "retrieval beats memory" cannot go red under any mutation, so Section 14.1's firewall on the memory side is entirely unguarded despite being the property the gate's own docstring calls its central premise.

What this phase got right, said plainly because a ledger of defects is not a verdict on the work. P2 pinned to live graph ground truth is the strongest arm this repository has written. P4b is the correct, honest fix for the phase's own worst finding, and F-4.5-09 was found by asking a question no test asked, which is the hardest way to find anything. The depth-directive history recorded at `synthesis/findings.py` (four versions, one cause: each tried to buy a property with an instruction about form) is genuinely transferable and worth promoting into `LEARNINGS.md`. The cost-cap pre-flight on the second Synth call is correctly placed. And the phase self-reported that stages 8 and 9 did not run, which is why this report exists at all.

The pattern across the ledger is narrower than the count suggests, and it is one pattern: this phase's controls are mostly correct in the code and mostly unguarded by the gate. Five of six load-bearing comments assert a property the code does not have, three arms cannot fail, five pure arms skip in ordinary CI, and the 500-line memory module has no unit test file. The standing repository bias held exactly as briefed: F-4.5-J-01, F-4.5-J-02 and F-4.5-J-03 all live in `6576b73` and `1543c46`, the two newest feature commits, and F-4.5-J-01 is inside the reference-resolution code written to close F-4.8-A-22 while F-4.5-J-02 is inside the ownership check written to close F-4.1-A-15. Both criticals are in code written to repair an earlier finding.
