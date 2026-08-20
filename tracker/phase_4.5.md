# Build phase 4.5: personalization and session memory

Branch: `phase/4.5-personalization-memory`
Spec: `requirements/Technical_specification.md` Section 14 (all of it), Section 12.7, Section 13.1, Section 13.3, Section 25 (row 4.5)
Depends on: 1.2 (PR #12) and 2.2 (PR #18), both verified merged at phase open
Opened: 2026-08-20

## What this phase delivers

Three things, per Section 25: bounded in-conversation session memory, audience-level depth control, and the stable named scientist persona. It never touches grounding.

## What was actually undecided at open, and what was not

This phase carried `product_refine` on `tracker/BOARD.md` with the product owner as owner, and the continuation prompt named three things to settle before any ticket existed. Two of the three were already settled in the locked specification, and reading it first is why this phase opened with one question instead of three.

- The memory bound: SPECIFIED. Section 14.3 gives `token_budget = 1500` as a hard cap, `maxItems` of 50 resolved entities, 20 compressed findings and 10 open threads, and a named compaction order. Section 14.4 pins the injection point and requires the cap be counted server-side with the receiving tier's real tokenizer. Nothing here needed a product decision.
- The depth levels: SPECIFIED. Section 14.5 gives `clinical_brief`, `researcher` (the default) and `deep_technical`, user-set, overridable per query, defaulting to the user's last-used value once auth is live. `Query.audience_depth` already rides the contract on all four callable surfaces. Nothing here needed a product decision either.
- The persona: GENUINELY OPEN, and the only one. Section 14.2 draws from a "curated top-100 biomedical-scientist list (curation is a Phase 6 build task, already logged)". `DECISIONS.md` logged that on 2026-07-21. The list was never produced.

Settled with the product owner on 2026-08-20, both logged in `DECISIONS.md`:

- The list ships as roughly 30 curated names in a versioned data file, with the drawing mechanism, the storage column and all four surfaces sized for 100, so a later extension is a data change rather than a code change.
- The list contains deceased scientists only. A living scientist's name rendered above a generated biomedical answer reads as an endorsement that person never gave.

## What the code actually looks like at open, measured rather than assumed

Four facts found by reading the source before decomposing. Each one moves a ticket.

- `audience_depth` is CARRIED AND DROPPED. It is on `contracts/query.py:40` and on all four adapters, and nothing in `core/` or `harness/` reads it. This is wiring, not new plumbing.
- `session_memory` is a typed hole. `contracts/query.py:84` types it `Any | None` behind a serialized-length placeholder bound, with a comment naming this phase as the one that lands the real type.
- `think_node` IS STILL A STUB. It emits `resolved_entities=[]` and a fixed `query_class="lookup"`. The real entity resolution in the shipped system happens in `plan_node` (`resolve_symbol_to_curie`, `unresolved_entity_symbols`). So the source that populates `SessionMemorySummary.resolved_entities` is Plan, not Think, and a ticket written against Section 14.3's wording alone would have wired memory to a node that resolves nothing.
- The persona is stubbed in THREE places that must agree: `_STUB_PERSONA_NAME = "Assistant"` at `adapters/web_sse/app.py:263`, `_PERSONA_NAME = "Assistant"` restated at `adapters/graphql/fold.py:174`, and a 10-name `PLACEHOLDER_PERSONAS` at `frontend/src/components/shell/PersonaChip.tsx:28` that the frontend draws from locally instead of reading the response.

## The trap this phase can most easily ship

`build_synth_messages` (`synthesis/findings.py:555`) returns a system message holding `SYNTH_SYSTEM_INSTRUCTION` and a user message holding everything per-query. The system message is the prompt-cache stable prefix. Putting the depth directive there is the obvious, natural place to put it, and it would break the stable prefix on every query whose depth differs from the last, silently re-billing every Synth call at the uncached rate with nothing erroring. `.claude/rules/prompt-cache-discipline.md` requires the proof be a SHA-256 byte-equality assertion across two requests whose suffix differs, not a passing suite. The same trap applies to the session-memory block at Think and Plan.

## Blocked at open: the Layer 1 transport

`python3 tracker/preflight.py` at phase open returned `product-model ok`, `harness-model ok`, `graph skipped (GRAPH_PG_HOST is unset)`. Nothing in this phase's own code touches Layer 1, so building is not blocked. The premise gate's multi-turn cases run the real agent loop, which does reach the graph, so the graph must be re-probed and reachable before those cases are trusted. A `skipped` transport is not a passing one.

## Tickets

### T-4.5-01: Premise gate for personalization and memory

Status: in-review
Refine: refined
Branch: phase/4.5-personalization-memory
Depends on: nothing
Spec: Section 14.1, 14.3, 14.4, 14.5; `docs/build/Build_workflow_cadence.md` stage 5

This phase's deliverable IS model-generated: the depth control changes what the Synth tier writes. So the gate carries stage 5's no-mocking-the-model requirement in full. The failure this phase can actually ship is an answer that is fluent, correctly cited, and personalized in a way that moved a claim, which is precisely what Section 14.1's firewall exists to forbid and precisely what a shape assertion cannot see.

The gate's central premise is the FIREWALL, not the feature. The same question asked at all three depths must produce the identical set of grounded claims while the prose visibly differs. An assertion that "depth changed the text" is decoration: it passes on a system that also changed the facts.

Acceptance criteria:
- [ ] The gate calls the real model. No mocked tier, on any case that asserts about generated text
- [ ] Firewall arm: one question run at `clinical_brief`, `researcher` and `deep_technical` yields the identical set of citation ids and the identical grounded-claim set, while the answer text differs between at least two of the three. Both halves asserted, since either alone passes on a broken system
- [ ] Default-path arm FIRST: a request that names no depth and carries no session memory is exercised before any arm that passes an explicit value. Build phase 4.4 shipped a critical because five of six gate cases passed an explicit list and the default path was tested by nothing
- [ ] Memory arm: a two-turn session where turn 2 carries an unresolvable pronoun resolves against turn 1's entity, and the resolution is asserted by the CURIE reached, not by the answer being non-empty
- [ ] Anti-citation arm: a `compressed_finding` present only in memory, whose claim is NOT re-grounded by this turn's retrieval, must not appear as a citation in the answer. This arm must be constructed so it CAN fail, meaning memory must actually hold a claim the current turn's findings do not support
- [ ] Contradiction arm: where session memory disagrees with this turn's fresh retrieval, the answer follows retrieval. Memory shapes orchestration, never grounding
- [ ] Cap arm: a summary built past `token_budget` is compacted before injection, asserted against the tokenizer's own count for the receiving tier, not a character count and not a trusted client value
- [ ] Prefix arm: `prefix_sha256` of the assembled stable prefix is byte-identical across two requests that differ in depth and in session memory. This arm names the specific control, so deleting the depth-into-suffix routing turns it red
- [ ] Every arm has been MUTATION-PROVEN: the control it names is deleted from the real source, the single arm is run, and it is seen going red. Build phase 4.3 found five vacuous arms whose mutations had been named in comments and never applied
- [ ] The gate states, in its own module docstring, which shapes it exercises and which it omits
- [ ] The gate has been SEEN FAILING before T-4.5-02 opens

Evidence:
- `tests/system_03_search_agent/core/test_personalization_premise.py`, thirteen premise arms plus one retry-safety test
- SEEN FAILING: `venv/bin/python -m pytest tests/system_03_search_agent/core/test_personalization_premise.py -q` returns `12 failed, 2 passed in 74.29s`. It FAILED rather than SKIPPED, which is the load-bearing part: the tunnel was open, `OPENROUTER_API_KEY` was set, `_graph_is_reachable()` returned True, so the live guard was exercised and the failures are real
- Every failure verified to be for the RIGHT reason: `ModuleNotFoundError` on `core.session_memory` and `core.persona`, `ImportError` on `ResolvedEntity` and `CompressedFinding`, `TypeError: build_synth_messages() got an unexpected keyword argument 'audience_depth'`, and P2 on its own depth fingerprint. No arm failed on a fixture or an environment problem
- The two passes are accounted for rather than counted: P3 is a regression guard whose control is the guardrail's, which already exists, and the retry-safety test needs neither graph nor model by design. Neither is evidence that any phase 4.5 control exists
- CHECKED, NOT ASSUMED: the first full run answered "I could not identify that gene" for BRCA1 at all three depths, which reads as a shipped regression in the flagship query. `test_write_grounding_premise.py` was then run and returned `11 passed, 1 xfailed in 249.25s` against that same gene, so it was a live Layer 2 resolution flake, not a regression. Filed as F-4.5-03 and fixed in this gate rather than left as a note
- MUTATION PROOF, taken while it was free: P2's control is already absent on this system, so the mutation needed no edit. Its first version passed under that mutation, was rewritten to assert a directional depth fingerprint, and now fails with `deep_technical surfaced no raw identifier`. Filed as F-4.5-02

History:
- 2026-08-20 lead: created, scoped at phase open
- 2026-08-20 lead: gate written and seen failing 12 of 14 against a reachable graph and a live model key. Two of its own arms were found defective before any product code was written, F-4.5-02 (vacuous firewall half) and F-4.5-03 (no environmental retry, no pacing), both fixed in the gate. Unblocks T-4.5-02 onward

### T-4.5-02: The SessionMemorySummary contract

Status: in-review
Refine: refined
Depends on: T-4.5-01
Spec: Section 14.3, Section 2.1

Replace `contracts/query.py`'s `session_memory: Any | None` placeholder with the three real models exactly as Section 14.3 declares them: `ResolvedEntity`, `CompressedFinding`, `SessionMemorySummary`, with every `max_length` and `maxItems` the spec states. Remove the serialized-length placeholder bound and its validator once the real per-field caps land, since carrying both leaves two disagreeing bounds on one field.

Acceptance criteria:
- [ ] All three models present with Section 14.3's exact field names, types and caps
- [ ] `Query.session_memory` typed `SessionMemorySummary | None`, placeholder bound and its validator removed in the same change
- [ ] Tests for valid, invalid and null input on each model, per `production-standards`
- [ ] Every string field carries `max_length` and every list carries a length cap, per the multi-agent pipeline gate
- [ ] The four adapters still accept and reject the same inputs they did before, verified rather than assumed

### T-4.5-03: build_session_context and the hard token cap

Status: in-review
Refine: refined
Depends on: T-4.5-02
Spec: Section 14.4

The server-side builder that formats a `SessionMemorySummary` into the compact block Section 14.4 shows, counting tokens against `token_budget` with the actual tokenizer for the tier receiving the prompt.

Acceptance criteria:
- [ ] Cap counted with the receiving tier's real tokenizer, never a character count, never a client-supplied number
- [ ] The cap is enforced before injection, not after, and the function cannot return a block over budget
- [ ] A summary that is already over budget on entry is compacted, not truncated mid-entry into a corrupt block
- [ ] Tests pin the boundary: at budget, one token over, and far over

### T-4.5-04: Append and compaction

Status: in-review
Refine: refined
Depends on: T-4.5-02
Spec: Section 14.3

The append step that runs after each turn's Write, and the compaction pass that runs when the serialized summary exceeds budget.

Acceptance criteria:
- [ ] Compaction order is exactly Section 14.3's: drop oldest `open_threads` first, then merge oldest `compressed_findings` into a shorter combined entry
- [ ] `resolved_entities` are never dropped for budget reasons; they are capped at 50 with FIFO eviction beyond
- [ ] Append is idempotent or repeat-safe per the retry-safety gate, since the Act step retries and a turn can be replayed
- [ ] A test constructs a summary where dropping in the wrong order still fits the budget, so an implementation that compacts in the wrong order is caught rather than passing by luck

### T-4.5-05: Session memory storage and ownership binding

Status: in-review
Refine: refined
Depends on: T-4.5-02
Spec: Section 15; closes F-4.1-A-15

Store the summary on the existing `sessions` table as a JSONB column with an alembic revision, rather than in process, so it survives a restart and more than one worker. The `sessions` row already carries `user_id`, which is what makes the ownership check possible at all.

This ticket closes F-4.1-A-15, boarded at build phase 4.1 and explicitly deferred to whichever of 4.5 or 4.6 first wires a `Query.session_id` consumer. This phase is that consumer. Today the MCP surface passes a caller-supplied `session_id` into `Query` with a length check and no ownership check; the moment memory is readable by session id, that becomes a live authorization gap on every surface, not just MCP.

Acceptance criteria:
- [ ] Alembic revision adds the column, with a rollback verified per the migration gate
- [ ] A session row with a non-null `user_id` is readable only by that user. A caller naming another account's session id gets a refusal, not that account's memory
- [ ] A guest session's memory is never served to a caller that cannot present the identity that created it
- [ ] The refusal is tested on every surface that accepts a caller-supplied `session_id`, which is at least web SSE, MCP and the CLI, not only on MCP where the finding was filed
- [ ] The error says what to do next, not just that it failed, per the retry-safety gate
- [ ] F-4.1-A-15 marked closed on `tracker/BOARD.md` with this ticket as evidence

### T-4.5-06: Inject memory into Think and Plan, and nowhere else

Status: in-review
Refine: refined
Depends on: T-4.5-03, T-4.5-05
Spec: Section 14.1, 14.4

Acceptance criteria:
- [ ] The block appends to the live tail of the Think and Plan prompts, in the DYNAMIC SUFFIX, never in the system block
- [ ] `prefix_sha256` of the stable prefix is byte-identical across two requests differing only in session memory, asserted directly
- [ ] Never injected into Act. Tool calls execute against fresh retrieval
- [ ] Never injected into Write as a citable source
- [ ] A `compressed_finding` relevant to the current answer is re-verified by a scheduled Act step or a reuse of the original `trace_id`'s cached `tool_result`, never asserted straight from the summary text
- [ ] Memory is sourced from where entities are actually resolved. `plan_node` resolves symbols today and `think_node` is still a stub emitting an empty list, so wiring against Think's payload alone ships a permanently empty memory

### T-4.5-07: Thread audience_depth into the Write step

Status: in-review
Refine: refined
Depends on: T-4.5-01
Spec: Section 14.5

Acceptance criteria:
- [ ] `build_synth_messages` takes the depth and renders its directive into the USER message
- [ ] `SYNTH_SYSTEM_INSTRUCTION` is not modified by depth, and a byte-equality assertion proves it across all three depths
- [ ] Depth changes vocabulary, mechanistic detail and background only. It never changes which tool results are retrieved, never changes the cite-or-refuse gate, never changes the trust-signal calculation
- [ ] `clinical_brief` still obeys the forbidden-output boundary. It never unlocks a diagnosis or a classification
- [ ] The default remains `researcher` when the caller names nothing, on every surface

### T-4.5-08: Depth persistence

Status: todo
Refine: refined
Depends on: T-4.5-07
Spec: Section 14.5

Acceptance criteria:
- [ ] Once auth is live, depth defaults to the user's last-used value, stored on the user row
- [ ] Before auth, it defaults per session
- [ ] Always overridable per query, including by a programmatic caller with no stored preference, which is the MCP case Section 13.2 names

### T-4.5-09: The curated persona list and the draw

Status: in-review
Refine: refined
Depends on: nothing
Spec: Section 14.2; `DECISIONS.md` 2026-08-20, both rows

Acceptance criteria:
- [ ] A versioned data file holding roughly 30 curated names, every one a DECEASED scientist, each with the contribution it was selected for recorded alongside it
- [ ] The file carries its own version, and the loader reads it once at process start from the versioned file, never per request, per `prompt-cache-discipline`
- [ ] Storage, draw and every consumer are sized for 100, so extending the file is a data change with no code change
- [ ] `users` gains a persona column via an alembic revision with a verified rollback
- [ ] Drawn once at first login and stored. Never reassigned for the life of the account
- [ ] An anonymous session draws one and holds it for that session only, redrawn on the next anonymous session
- [ ] A test asserts the deceased-only property against the file itself, so a later extension that adds a living scientist is caught by the gate rather than by a reader

### T-4.5-10: Wire the persona to all four surfaces

Status: in-review
Refine: refined
Depends on: T-4.5-09
Spec: Section 12.7, Section 13.1, Section 13.3; closes F-4.2-03

Acceptance criteria:
- [ ] `_STUB_PERSONA_NAME` removed from `adapters/web_sse/app.py`, replaced by the real resolution
- [ ] `_PERSONA_NAME` removed from `adapters/graphql/fold.py`. The two surfaces resolve from one source rather than restating a literal
- [ ] The CLI status line carries the persona prefix Section 13.3 asks for, closing F-4.2-03. `adapters/cli/render.py:540` currently omits it rather than fabricating one, which was correct and is now fixable
- [ ] The frontend chip renders `persona_name` from the `POST /v1/query` response instead of calling `drawPersona` locally. `PLACEHOLDER_PERSONAS` is removed, not left beside the real path
- [ ] The stub is cleared from `frontend/src/stubs/registry.ts`
- [ ] The name reaches the caller once, on the response body, never repeated on every streamed event

### T-4.5-11: The AudienceDepthToggle component

Status: todo
Refine: refined
Depends on: T-4.5-07
Spec: Section 12 component inventory, Section 12.7

Acceptance criteria:
- [ ] Three-way control mirroring `Query.audience_depth` exactly, defaulting to `researcher`
- [ ] Disabled once a run has started and is mid-stream. The depth a run was dispatched with is locked for that run
- [ ] Changing it sets the value sent on the NEXT `POST /v1/query`, not the running one
- [ ] WCAG 2.1 AA, checked in both light and dark theme, per the accessibility bar every UI change carries
- [ ] Built against the design-system component card, never against the prototype, per `docs/build/design/Design_to_build_workflow.md`

### T-4.5-12: Resolve the canned follow-up pronoun

Status: in-review
Refine: refined
Depends on: T-4.5-06
Spec: closes F-4.8-A-22

A canned follow-up chip sends an unresolvable pronoun ("What variants cause it?") to the backend as a standalone query with no prior context. Boarded at build phase 4.8 against this phase as the only one that can resolve it, since this phase owns session memory.

Acceptance criteria:
- [ ] The follow-up resolves against session memory rather than being sent as a standalone query
- [ ] A follow-up sent with no memory available degrades to a clarifying question, not a confident answer about the wrong entity
- [ ] F-4.8-A-22 marked closed on `tracker/BOARD.md`

## Findings

### F-4.5-01: preflight reports the graph unverifiable in the normal case, and still exits READY

Severity: major, harness rather than product
Round: 0 (found at phase open, by the lead, running the tool the cadence mandates)
Status: open

`tracker/preflight.py:132` reads `GRAPH_PG_HOST` from `os.environ` only. It never loads `.env`. This repository keeps the graph host and port in `.env`, so on a normal developer shell the variable is unset in the environment and preflight returns `skipped: GRAPH_PG_HOST is unset, so there is no tunnel to probe`.

Reproduced at phase open, 2026-08-20, in this order:

- `python3 tracker/preflight.py` returned `graph skipped (GRAPH_PG_HOST is unset)`.
- `grep "^GRAPH_PG_HOST" .env` returned `GRAPH_PG_HOST=127.0.0.1`, and `GRAPH_PG_PORT=15432`. The variable was not unset, it was unread.
- The tunnel was opened and `nc -z 127.0.0.1 15432` succeeded.
- `python3 tracker/preflight.py --transport graph` returned the identical `skipped` line against a graph that was, at that moment, reachable.

Why it matters rather than being a cosmetic message. Preflight was added on 2026-08-18 specifically so a phase does not dispatch expensive agents into a dead transport, and the tool's own output says "a skipped transport is not a passing one". But the process exits 0 and prints `READY`, so the one transport it cannot actually verify is also the one it waves through. A phase that needs the graph gets a green light and a benign-looking word for "I did not check".

This is a repeat of a defect this repository already fixed once. Every premise gate calls `_load_env_explicitly()` before reading these variables, and the comment at `tests/system_03_search_agent/core/test_write_grounding_premise.py:205` cites finding F-2.1-04 as the reason. Preflight was written later and did not inherit it.

Fix: load `.env` before probing, the same way the gates do, and treat a host that resolves but does not answer as `down` rather than `skipped`.


## History

- 2026-08-20 lead: phase opened. Dependencies 1.2 (PR #12) and 2.2 (PR #18) verified merged in `git log`, not taken from the table. Preflight run: product-model ok, harness-model ok, graph skipped. Branch cut from `develop` at `bddd970`
- 2026-08-20 product owner: settled the persona list scope (roughly 30, sized for 100) and its selection basis (deceased only). Both logged in `DECISIONS.md`. The other two questions the handoff raised were already answered in the locked specification and did not need deciding
- 2026-08-20 lead: decomposed into twelve tickets after reading the source rather than the spec alone, which moved three of them: `audience_depth` is wiring rather than new plumbing, memory must source from `plan_node` because `think_node` is still a stub emitting an empty entity list, and the persona is stubbed in three places that must be collapsed to one

### F-4.5-02: the firewall arm's second half was vacuous, and the mutation was free

Severity: critical, in the gate rather than the product
Round: 0 (found by the lead, by running the gate rather than by reading it)
Status: open, fix in flight

`test_p2_the_claim_set_is_identical_across_depths_and_the_prose_is_not` asserted its second half as `len({narrative per depth}) > 1`, meaning "the three depths did not all produce byte-identical prose".

That assertion is satisfied by ordinary model sampling nondeterminism. `audience_depth` is inert on this system today, carried on the contract and dropped before Synth, so the three runs differ from each other for the same reason any two runs of one prompt differ. The arm passes with the control it names entirely absent.

Measured, not reasoned:

- Full-file run: P2 FAILED, all three depths byte-identical, because all three happened to hit the same live gene-resolution flake and returned the identical canned refusal.
- P2 re-run alone minutes later: PASSED, on the identical inert code.

So the arm's verdict flipped without a line of production code changing, and the passing verdict was the wrong one. This is build phase 4.3's finding repeated in a new place: an arm that asserts "something differed" on a surface with many independent reasons to differ proves nothing about WHICH control did the differing.

It is also the exact failure `.claude/rules/goal-contracts.md` names as reward-hacking-adjacent, arrived at honestly: the gate was written to catch a firewall breach and its second half instead measured the weather.

The fix is a depth-specific FINGERPRINT rather than inequality. Section 14.5 says `deep_technical` surfaces raw identifiers and full coordinate detail while `clinical_brief` is concise and evidence-first, so the arm now asserts that `deep_technical` carries at least one raw CURIE and `clinical_brief` carries none, which an inert control cannot satisfy in either direction rather than satisfying it half the time by coin flip.

The transferable form, and the reason this is filed rather than quietly patched: WHEN AN ARM'S CONTROL IS ALREADY ABSENT, THE MUTATION PROOF IS FREE. Run it then, before writing the code. Every arm in this gate whose control does not yet exist is in that state exactly once, and this phase spent that opportunity on one arm and found it rotten.

### F-4.5-03: the gate has no environmental retry and no pacing between live runs

Severity: major, in the gate rather than the product
Round: 0
Status: open, fix in flight

The full-file run returned "I could not identify that gene. NCBI has no record matching the name in your question" for BRCA1, at all three depths. BRCA1 is the canonical pinned gene, and build phase 2.2's gate asserts real ground truth against it.

Checked rather than assumed: `test_write_grounding_premise.py` was run immediately afterward and returned 11 passed, 1 xfailed in 249 seconds. BRCA1 resolves. The refusal was a live gene-resolution flake, not a product regression, and the difference between the two gates is that 2.2's carries `_is_environmental_failure` plus a single re-run and this one carries neither.

Two gaps, both this gate's:

- No environmental retry. A flake in Layer 2 resolution reports here as a personalization defect, which is the wrong step entirely and would send a reviewer looking in the wrong file.
- No pacing. P2 fires three full loops back to back with no delay, and each resolves a gene symbol against live E-utilities, whose unauthenticated pool is 3 requests per second. `.claude/rules/tool-call-budgets.md` names this directly: an integration suite that fires faster than the limit it tests against is a self-inflicted failure, and it can trip a shared bucket that then fails an unrelated run.

### F-4.5-04: the firewall arm compared prose, not grounding

Severity: major, in the gate rather than the product
Round: 0
Status: closed by the lead, same session

P2's invariant was a set of `(source_id, claim_text)` pairs. `claim_text` is the sentence fragment a citation supports, and depth is SUPPOSED to change sentences, so the arm reported a breach while the feature was working correctly: `deep_technical` grounded the same sources in two extra sentences and the pair-set diff called it a firewall violation.

It conflated presentation with grounding, which is the precise distinction Section 14.1 draws and the one this whole phase is about. Corrected to assert the ANSWER SET pinned against ground truth read from the live graph, which is stronger where it matters, since all three depths agreeing on a wrong answer still fails it.

### F-4.5-05: the gate ran against a blocked network and blamed personalization

Severity: critical, in the gate rather than the product
Round: 0
Status: closed by the lead, same session

`tests/conftest.py` installs a session-scoped autouse fixture that blocks every real outbound HTTP call unless `RUN_PREMISE_GATE=1` is set. It was added at build phase 3.1 after a judge proved the unit suite was silently burning E-utilities quota on every run.

This gate did not set it. The consequence was not a skip and not an obvious error. Live gene-symbol resolution returned nothing, the loop refused with "I could not identify that gene", and a file about personalization reported that refusal as a personalization defect.

How it was found, because the method is the point. The failure looked exactly like an intermittent live flake and was treated as one at first. What broke the tie was measuring instead of theorising:

- 3 of 3 identical failures under pytest, so not a flake.
- The same question run outside pytest succeeded 2 of 2, with 5 citations.
- `resolve_symbol_to_curie` called directly succeeded 5 of 5.
- `_extract_target_entities` returned the correct CURIE for all four phrasings.
- A direct HTTPS probe of E-utilities returned gene 672 in 164ms, so NCBI was neither down nor throttling.

Every component worked; only the composition failed. That is the signature of an environment difference rather than a defect, and it pointed straight at conftest.

Build phase 2.2's gate never hit this because its questions name CURIEs directly and resolve no symbol, so it reaches the graph over psycopg2 and opens no outbound HTTP at all. This gate asks with bare symbols, which is what a real user types.

Fixed: the skip predicate now requires `RUN_PREMISE_GATE=1` and says so in the skip reason.

### F-4.5-06: audience depth breached the grounding firewall, twice, in two different costumes

Severity: CRITICAL, in the product
Round: 0 (found by the premise gate on the first real implementation, before any review round)
Status: partially fixed, ONE HALF OPEN AND NEEDS A PRODUCT DECISION

This is what the gate was built for, and it caught the lead's own code.

Breach 1, fixed. The first `clinical_brief` directive ended "do not print CURIEs, accession numbers, or coordinates in the prose; the citations carry them". Build phase 2.2's grounding pass accepts a claim only when it substring-matches the finding it cites, and a Layer 1 finding's value IS the identifier. So forbidding identifiers made every claim fail the match, the answer was stripped, and the run REFUSED with "I could not find grounded evidence for this", while `researcher` cited all four pinned diseases from the identical findings. A depth control had turned into a retrieval control.

The transferable form: a presentation instruction that constrains WHICH TOKENS may appear is not presentation at all when a downstream gate matches on those tokens. It is grounding wearing a style hat.

Breach 2, OPEN. With that clause removed and replaced by "be brief, keep background to a minimum", the depth stopped refusing and started ANSWERING INCOMPLETELY: three of the four pinned diseases, fully cited, confidently worded, with nothing in the output announcing the loss. Strengthening the directive to "report every finding you were given, without exception. Say less about each finding; never report fewer findings" did NOT fix it. Measured again after that change: still 3 of 4, missing `MedGen:C0346153`.

Breach 2 is worse than breach 1 even though it looks milder. A refusal is visibly a non-answer. A brief that silently drops one of four disease associations is a confident wrong answer, which is the single failure mode this product exists to avoid, and the clinician who selected "brief" is exactly the reader least able to notice.

Why this is not just a prompt to keep tuning: two successive strengthenings of the instruction did not hold, which is evidence that completeness under a brevity instruction is not reliably promptable. Per `attack-the-constraint`, the constraint is not the wording.

THE PRODUCT DECISION, for the product owner, since it is a real trade-off rather than a bug with one right answer:

- Option A, completeness is structural. After synthesis, check by code that every finding handed to Synth is represented in the answer, and if any is missing either regenerate or append the omitted ones. `clinical_brief` then guarantees the same fact set as every other depth. Costs some of the brevity the depth exists to provide.
- Option B, brevity may summarize, and must DISCLOSE. `clinical_brief` may report a subset, and the answer must then say so explicitly, the same discipline build phase 2.2 already applies to a truncated result set. Keeps the depth genuinely brief, and makes the omission visible rather than silent.
- Option C, drop `clinical_brief` from v1. Ship `researcher` and `deep_technical` only, on the grounds that a clinical audience is the one for whom a silent omission is least acceptable.

The lead recommends Option A, on the grounds that this repository's own standard is that a confident wrong answer is worse than no answer, and a per-depth completeness guarantee is the only one of the three that keeps the eval harness's stateless pass a trustworthy proxy for live behavior. It is not taken unilaterally because it trades away part of what the depth was for, which is a product call.

### F-4.5-06 update, 2026-08-20: the repair is built, and it lands short of the guarantee

Product owner chose Option A, completeness is structural, on 2026-08-20.

What was built, in `synthesis/findings.py` and `core/graph.py`:

- `unreported_findings` compares the findings handed to Synth against the citation ids that survived the grounding pass. It is the finding-level sibling of F-3.4-A-01's entity-level check, one level down: that one catches an answer covering only some of the entities the QUESTION named, this one catches an answer reporting only some of the findings RETRIEVAL produced.
- On an omission, ONE bounded regeneration runs, carrying a directive that names the missing rows explicitly rather than repeating a general "report everything", since the general form is precisely what had already failed twice.
- The repair is kept only when it is a STRICT improvement. A regeneration that recovered the missing rows but dropped others, or that grounded nothing, is discarded in favour of the original, because trading a known-incomplete answer for an unknown one is not a repair.
- If omissions survive the regeneration, `trust_outcome` floors at `ask` through the same `aggregate` most-restrictive-wins rule the entity check and the conflict check already use, and `_build_incomplete_answer_note` names what is missing. Never silent.

The directive itself took three more attempts, and the pattern across all of them is the finding worth keeping:

- Version 1 forbade identifiers. Every claim failed the grounding pass's substring match, so the depth REFUSED.
- Version 2 said "keep background to a minimum". The depth reported three of four findings.
- Version 3 said "state the identifiers and values exactly as they appear" and "say less about each finding". The model complied literally, emitted a bare identifier list with no sentence answering the question, the core-ask requirement rejected it, and the depth refused with an EMPTY narrative.
- Version 4, current, constrains register and length and NOTHING about form.

One cause under three symptoms: each version tried to buy a property (verifiability, completeness, groundedness) with an instruction about FORM. The grounding pass already owns verifiability and the repair now owns completeness, structurally. A depth directive that also tries to own them fights two mechanisms that are better at it.

CURRENT MEASURED STATE, stated plainly rather than rounded up:

- P1 (default path) PASSES.
- P3 (forbidden-output boundary at clinical_brief) PASSES.
- P2 (the firewall) STILL FAILS. `clinical_brief` reports three of the four pinned diseases. The regeneration fired and did not recover the fourth.
- The disclosure fires correctly. The shipped answer now reads "Note: this answer does not report every retrieved finding. Missing: curie=MedGen:C0346153. The full set is in the citations."

So the SILENT wrong answer is fixed and the guarantee is not yet met. The system is honest about the gap; it does not yet close it.

THE REMAINING CHOICE, for the product owner, because Option A named two mechanisms and only one is built:

- A1, deterministic append. Construct the missing findings' sentences by code from the findings themselves, grounded by construction, and append them with their markers. This GUARANTEES the fact set at every depth, which is what Option A asked for. It is the more invasive change: it writes prose by code into the one path where prose has so far only ever come from the model, and it interacts with Section 9.4's marker renumbering, so it wants independent review more than anything else in this phase.
- A2, accept regenerate-then-disclose as shipped. Completeness is attempted, and any residue is named in the answer with the outcome floored at `ask`. Cheaper, already built and measured, and strictly better than what the phase started with, but it is Option A in spirit and Option B in guarantee.

The lead did not choose between these unilaterally because A1 was authorized in principle by the Option A decision while its actual cost, generating answer prose in code, was not visible at the time that decision was made.

### F-4.5-07: the depth fingerprint is not reliably measurable on this question

Severity: minor, in the gate rather than the product
Round: 0
Status: open, xfailed non-strictly so it reports XPASS the day it holds

P2b asserts that `deep_technical` is materially longer than `clinical_brief`, at a ratio of 1.4. Measured on the BRCA1 disease question: 1.13, from 161 characters against 182.

The cause is the data, not the directive. That answer is built from five short Layer 1 rows, and `deep_technical`'s brief is to add raw identifiers, assembly context and coordinate detail "that the findings actually contain". These findings contain almost nothing more than the identifiers already required at every depth for grounding, so there is very little for the deeper register to add. The two answers came out nearly identical in length while still differing in register: `deep_technical` wrote "BRCA1 (gene symbol: BRCA1 [1])" where `clinical_brief` wrote "BRCA1 [1]".

Three options were considered and the reasoning is recorded because the tempting one is wrong:

- Lower the threshold to the observed 1.13. REJECTED. That is tuning the check until it passes, which `.claude/rules/goal-contracts.md` names as a failed run rather than a completed one. The threshold would then encode the measurement instead of the requirement.
- Delete the arm. REJECTED. It is the only depth-differentiation signal in the file, and deleting a check because it currently fails is the same reward hack wearing a different hat.
- Keep it running and xfail non-strictly, with the reason stated in the marker. CHOSEN, following the precedent build phase 2.2 set for F-2.2-06's truncation-scale half. It reports XPASS the day a richer finding set or a stronger directive makes the split real, so the gap is visible in every run rather than silently accepted.

Two ways to close it properly, neither done here:

- Ask the fingerprint question against a finding set with room to differentiate. TP53 carries twelve disease associations against BRCA1's four, so a brief and a deep write-up of it have far more to diverge over. This is the better fix and costs two more live runs per gate execution.
- Accept that on sparse Layer 1 findings the depths legitimately converge, and assert the register difference rather than the length difference. That needs a register fingerprint that does not collide with grounding, which is exactly what F-4.5-06 established is hard: the obvious one, identifier presence, is unavailable because grounding requires identifiers at every depth.

The honest summary for a reviewer: this gate currently proves that depth does not BREAK anything. It does not prove that depth DOES anything. Those are different claims and only the first is gated.
