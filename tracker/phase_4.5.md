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

Status: in-review
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

Status: in-review
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

### F-4.5-08: the incomplete-answer note misdirected the reader and broke citation coverage

Severity: major, in the product, found by the offline eval gate
Round: 0
Status: closed by the lead, same session

The note this phase added to disclose an unreported finding carried two defects, and neither was visible by reading it. Both surfaced only when `tests/system_03_search_agent/eval/test_write_step_eval_gate.py` ran.

- IT MADE A FALSE CLAIM. The note ended "The full set is in the citations." That is not true. A finding the answer never reported produced no grounded claim, and citations are built from grounded claims, so the omitted rows are missing from the citations exactly as they are missing from the prose. The note pointed the reader at a place the data is not, which is worse than saying nothing: a wrong pointer closes the question, while silence at least leaves it open.
- IT BROKE THE COVERAGE GATE. `_citation_coverage` treats any non-framing sentence without a marker as an uncited factual claim. The note was three sentences and only the first began "Note:", so the two continuations scored as uncited claims and pulled coverage below 1.0.

Fixed as one sentence stating the SCALE rather than naming each omitted value. That is the discipline `_build_truncated_answer_note` already follows, and here it is also forced rather than chosen: a Layer 1 field value such as `NM_007294.4(BRCA1):c.190T>G` is full of periods, and the coverage grader splits sentences on periods, so inlining values fragments the note into uncited pieces no matter how it is worded.

The general form worth carrying: a disclosure is ANSWER TEXT, and every rule that governs answer text governs it too. It can be uncited, it can be wrong, and it can fail the same gates a claim fails. Writing one is not a safe act just because its purpose is honesty.

### F-4.5-09: session memory was never written, and eight gate arms could not see it

Severity: CRITICAL, in the product
Round: 0 (found by the lead, at the end of the phase, by asking what actually populates memory)
Status: closed, with a new gate arm that would have caught it

The phase built the read side of session memory completely: the contract, the token cap, compaction, the injection point, reference resolution against it, and the ownership check. Every one of those worked. Nothing ever WROTE a summary, so on the real path memory was permanently empty and the entire feature was inert.

Eight premise-gate arms passed throughout, because every one of them constructs a `SessionMemorySummary` in the test and hands it in on `RequestContext`. They test that memory is READ and INJECTED correctly, and they are structurally blind to whether anything ever produces one.

This is build phase 4.4's lesson arriving in a new costume, and the lead wrote the coverage note quoting that lesson while committing the same error. There, five of six cases passed an explicit edge-label list and the default path was tested by nothing. Here, every memory case passed an explicit summary and the path a real caller takes was tested by nothing. THE INJECTED FIXTURE IS THE EXPLICIT LIST.

Found by asking a question no test asked: what populates this? Not by a failing test, not by review, and not by the gate.

Four defects were behind it, and each one alone would have kept memory inert. That is worth recording, because each was invisible to the tests that existed and each was found only by running the end-to-end arm and reading what actually came back:

- NO WRITE PATH AT ALL. `merge_turn` and `save_for_caller` did not exist. Added, with idempotent folding by natural key, since the Act step retries and a blind append would grow the list on every replay.
- NO READ-BACK PATH. `load_for_caller` existed and nothing called it on the way in. The graph reads `RequestContext.session_memory`, which only a CALLER ever set, so a summary could have been written every turn and never read. Write-without-read and read-without-write are the same bug from two sides, and both look correct in isolation.
- THE ROW KEY WAS WRONG. `Query.session_id` is a free-form string of up to 64 characters and the surfaces genuinely differ: the web UI sends `crypto.randomUUID()`, the CLI sends bare 32-character hex, MCP accepts anything. `sessions.id` is a UUID column, and the first store silently DROPPED every session whose id did not parse as a UUID. Memory would have worked in a browser and been inert for the CLI and most MCP callers. Fixed with a documented uuid5 mapping, which build phase 4.6 must use for `interactions.session_id` or the two will disagree about which row a conversation is.
- THE ENTITIES WERE READ FROM A FIELD THAT DOES NOT EXIST ON THE WIRE. `_remember_turn` reached into `tool_calls[].target_entities`, and `ToolCall` carries tool, call_id and layer only. It found nothing, every turn, silently. Fixed by publishing the resolved CURIEs on `PlanPayload.resolved_entities`, an additive field, so memory reads a typed value instead of parsing a narrative sentence for a CURIE-shaped substring.

Two further defects surfaced while fixing those, both from the same end-to-end arm:

- The event contract's `ResolvedEntity` is `{text, curie, confidence}` and the memory contract's is `{mention, curie, entity_type}`. Constructing one with the other's fields crashed `plan_node`, and `run()`'s last-resort catch turned the crash into a generic "failed unexpectedly" with an empty narrative. The catch is correct and it also means a contract mismatch presents as a mystery rather than a traceback.
- An ownership refusal on the READ path escaped `run()` as an unhandled exception, breaking its documented never-raises contract and failing 27 existing tests. Read and write need different answers: a read from another caller's session degrades to a stateless turn, since it discloses nothing and the caller loses nothing they were entitled to, while a write still refuses because it would overwrite their conversation.

The new arm, P4b, hands in NOTHING: two real turns through one session, where turn 2's pronoun can only bind if turn 1 was actually persisted. It was seen failing against each of the four defects above in turn, which is the only reason it can be trusted now.

The transferable rule, stated plainly because this phase paid for it twice: WHEN A TEST SUPPLIES THE THING UNDER TEST, IT CANNOT TELL YOU THE THING EXISTS. At least one arm must obtain that thing the way production obtains it.

## The independent review this phase merged without, run afterwards

Build phase 4.5 merged as PR #52 having run stages 1 to 7 and 10. Stages 8 and 9, the judge round and the adversary round, did not run, and every fix and every test on the branch was written by the same agent that wrote the code. That is the one split `.claude/rules/self-eval-loop.md` says must never collapse. Both rounds were run on 2026-08-20 against the merged code, before build phase 4.6 opened.

Reports, one per round:

- `tracker/phase_4.5_judge_report.md`: 22 findings, F-4.5-J-01 through F-4.5-J-22. 2 critical, 11 major, 7 minor, 2 latent.
- `tracker/phase_4.5_adversary_report.md`: 26 findings, F-4.5-A-01 through F-4.5-A-26. 3 critical, 9 major, 11 minor, 3 latent. 19 confirmed by executing code, 7 reasoned from reading.

Roughly 35 unique findings after overlap. Both reviewers ran with separate briefs and separate contexts, and they converged independently on the same three worst defects, which is the strongest verification signal available short of a live exploit.

### What the two rounds agreed on, stated first because agreement is the signal

- Memory defeats the unresolved-entity refusal (F-4.5-J-01, F-4.5-A-01, critical, both confirmed by execution). A question naming a gene that does not resolve is answered about a remembered gene instead, grounded, cited, and shipped as `trust_outcome: "answer"` with no disclosure. The comment three lines above asserts the opposite property.
- Every guest is the same principal (F-4.5-J-02, F-4.5-A-02, critical, both confirmed by execution). `(owner_id or None) != (user_id or None)` is False for every guest pair, so any anonymous caller reads and overwrites any other guest's memory. The distinguishing identity already exists: `caller.owner_id` carries `guest:<uuid>` and is passed to `create_run` on the next line. It is simply not the field the check reads.
- Eleven remembered CURIEs crash the query (F-4.5-J-03 major, F-4.5-A-03 critical, both confirmed). `_memory_curies` returns up to 50, `target_entities` caps at 10, and the memory path does not slice where the resolver path does. Permanent for the session, because memory only grows, and it fails hardest in long sessions, which are what memory is for.

The severity disagreement on the third is recorded rather than reconciled away: the judge called it major, the adversary critical. Treated as critical here, because the failure is permanent for the affected session and presents as an opaque crash naming nothing.

### The pattern both rounds named independently

The phase's controls are mostly correct in the code and mostly unguarded by the gate. Three arms are fully vacuous, one half, one partial. Five arms that need no live resources sit behind `@premise_gate` and skip in ordinary CI, measured at `2 passed, 14 skipped in 0.03s`, so most of this gate does not run unless someone runs it deliberately. The 500-line memory module has no unit test file. The completeness repair, which fires a second Synth call on the most safety-critical path in the product and floors `trust_outcome`, has no deterministic test. Five of six load-bearing code comments assert a property the code does not have.

Both criticals live in the two newest feature commits, `6576b73` and `1543c46`, and both sit inside code written to repair an earlier finding: F-4.5-J-01 inside the reference resolution closing F-4.8-A-22, F-4.5-J-02 inside the ownership check closing F-4.1-A-15. The standing bias this repository measured across build phases 2.1, 4.2 and 4.3, that every review round finds its worst defect inside the previous round's fix, held here without a single exception.

### F-4.5-09 recurred four times in one phase

The phase's own signature defect is that a test which supplies the thing under test cannot tell you the thing exists. It was filed once, quoted in this file while being committed a second time, and the two rounds found two further instances that had gone unfiled:

- F-4.5-A-09: both injection sites discard the model's response. `think_node` is the build-phase-2.0 stub and `plan_node` selects its tool deterministically straight afterwards, so the whole rendered-memory apparatus, `_render`, `compact`, `build_session_context`, the token cap and the compaction order, produces a block appended to two prompts, billed at two tiers at 59 tokenizer calls and 50ms twice per query, and read by nothing that changes an answer. The only live effect memory has today is `_memory_curies` feeding `target_entities`, which needs none of it.
- F-4.5-A-10: `open_threads` has no writer anywhere in `src/`. Section 14.3's first compaction rule, drop the oldest open threads first, can never fire on real data, so real compaction always begins by merging findings, which the section itself names as the more expensive loss. Premise arm P9 proves the order holds only because it constructs ten threads by hand and passes them in.

### Disposition

Settled with the product owner on 2026-08-20: fix the criticals and the reachable majors before build phase 4.6 opens, track the minors and the latent findings. That is the merge bar build phase 4.3 converged under and the standard every phase since has been held to.

Fix work runs on `fix/4.5-review-followups`, cut from `develop` at `45c2636`. Findings are grouped by file with one agent per group working serially, per `docs/build/Build_workflow_cadence.md`: parallel fix agents in one file are individually correct and structurally blind to the sibling editing the same function, which is how build phase 4.2 reached six rounds.

### F-4.5-01, closed

`tracker/preflight.py` now loads `.env` before probing, so the graph transport is actually verified rather than reported `skipped` against an open tunnel while the run prints READY and exits 0. This was F-2.1-04 in a second place: every premise gate already loads `.env` explicitly and cites that finding, and preflight was written later and did not inherit it. `setdefault`, so an exported variable still beats the file.

Proven both directions rather than asserted:

- `python3 tracker/preflight.py --transport graph` returned `skipped` before and returns `ok  TCP 15432 open in 2ms` after, against the same open tunnel.
- `GRAPH_PG_PORT=1 python3 tracker/preflight.py --transport graph` returns `down  ConnectionRefusedError` and exits 1, which proves both that the exported value beat `.env`'s 15432 and that a configured but dead graph now fails the run.
- A full run reports `ok` for all three transports, the first preflight run in this repository to actually verify the graph.

Commit `d79122a`. One stale reference remains, at `tests/system_03_search_agent/core/test_personalization_premise.py:292`, which says preflight is the one tool that does not load `.env`. It is left for the agent that owns that file rather than edited under a concurrent reviewer.

## WITHDRAWN: the "regression" was my own instrument, and how it was wrong is the lesson

Status: WITHDRAWN on 2026-08-21 by the lead who filed it, after measuring the mechanism instead of reading it. There is no regression, and no product-owner decision is needed. The original text is kept below rather than removed, because the way it was wrong is worth more than the finding ever was.

WHAT IS ACTUALLY TRUE. The completeness repair runs, with 29 to 43 seconds of its 45-second budget still available, and finishes in 2 to 8.5 seconds. Budget starvation was never possible. Measured by instrumenting every Synth dispatch, every grounding pass and every `unreported_findings` call in a single probe:

```text
synth_call  budget 45.0  took 3.9   the first answer
grounding   claims 0                it grounded nothing
unreported  omitted 1               so the repair is triggered
synth_call  budget 41.1  took 8.5   THE REPAIR, running, 41s available
grounding   claims 0                the repair also grounded nothing
                                    and no second unreported_findings call
```

WHY IT LOOKED LIKE A REGRESSION. The instrument counted calls to `unreported_findings` and read two calls as "the repair completed". The shipped code computed `still_omitted` unconditionally after any regeneration. The strict-superset fix for F-4.5-J-13 short-circuits that call when the regeneration grounded nothing. So the two commits differ in how many times one function is CALLED, not in what the product DOES, and the instrument reported that structural difference as a behavioural one.

THE LESSON, which is this repository's own rule turned back on the person applying it. `attack-the-constraint` says that when a generated output looks wrong, print what the component actually received before debugging the component. The same discipline applies one level up: when a MEASUREMENT looks wrong, verify the instrument before believing the number. Two narrower probes disagreed on an identical tree, and `git log` showed no code in the Write path had changed between them. That was the moment to suspect the instrument, and it was not taken. It was taken only after a third probe recorded the whole block at once.

Compounding it: the original diagnosis named budget starvation and called it "confirmed by reading, not inferred from the numbers". Reading the source confirmed that a subtraction EXISTS. It did not confirm the subtraction ever binds, and it never binds. A mechanism read out of source is a hypothesis, not a confirmation, and calling it confirmed is how a wrong cause acquires false authority.

WHAT THE MEASUREMENT DID ESTABLISH, and this part stands:

- F-4.5-J-18 and F-4.5-A-05 are CONFIRMED on the substance. The repair fires often: 7 of 12 runs in the first sample, 2 of 4 in the second. It is a structural event rather than a rare one, exactly as both rounds argued.
- Their ARITHMETIC was wrong. Both derived that rate from "two to five sentences cannot ground twenty findings". Only 0 or 1 findings reach synthesis, never more, at both commits. A correct conclusion drawn from a false premise is not evidence for the premise.
- The repair is cheap where it was feared expensive: 2 to 8.5 seconds inside one declared 45-second step budget.
- The real quality problem sits upstream of all of it. One finding reaches synthesis, and the first answer grounds nothing against it in roughly half of runs, which is what produces a refusal. That belongs to the eval harness at build phase 5.1, and it is present at both commits.

The superseded original text follows, unedited.

Status (superseded, and wrong): open, needs a product-owner decision. Nothing is merged; `develop` is untouched and this lives on `fix/4.5-review-followups`.

F-4.5-A-04a said the completeness repair took a SECOND full Write-step budget, so the step could run to twice its declared timeout. That is a real contract breach under `.claude/rules/tool-call-budgets.md` and it was fixed by sharing one deadline: `repair_budget_s = write_budget_s - elapsed`, with the repair skipped below a floor.

The fix is worse than the defect, and the only reason that is known is that the product owner asked for the firing rate to be MEASURED rather than reasoned about.

Twelve live runs, four questions across all three depths, run identically against `45c2636` (pre-fix) and against the fix branch:

| Measure | Baseline 45c2636 | After the fix |
|---------|------------------|---------------|
| Repair attempted, an omission existed | 7 of 12 | 7 of 12 |
| Second Synth call produced usable text | 7 of 7 | 1 of 7 |
| Terminal outcome `answer` | 6 | 5 |
| Terminal outcome `refuse` | 4 | 6 |

The mechanism is confirmed by reading, not inferred from the numbers: the first Synth call consumes most of the Write budget, so the subtraction leaves the repair below its floor or too short to finish. The repair is the mechanism that rescues an answer which grounded nothing against its findings, so starving it converts answers into refusals.

Both options are real and neither is obviously right, which is why this is not being decided by the lead:

- Revert to a second full budget. Restores the measured-good behaviour and reopens F-4.5-A-04a, so the Write step can again take twice its declared timeout. It also requires changing a mutation-proven test that currently pins the shared deadline, and `.claude/rules/goal-contracts.md` forbids weakening a check to make something pass, so that edit needs to be a deliberate, recorded decision rather than a tidy-up.
- Declare the real budget. Make the Write step's declared timeout account for a possible repair, so one deadline covers both calls honestly and the contract stops lying. This is the better shape and it changes a locked per-step budget, which `tool-call-budgets` explicitly puts in the ask-first column.

What this episode is worth beyond the fix, and the reason it is written here rather than in a commit message. Both review rounds derived the repair's firing rate arithmetically from the shipped prompt: rule 7 asks for two to five sentences while up to 20 findings are handed in, so the repair must fire nearly always. The measurement found the number of findings reaching synthesis is 0 or 1, NEVER more, across all twelve runs at both commits. The premise both rounds reasoned from does not describe this system. That is `attack-the-constraint`'s own rule arriving from the other direction: the constraint was upstream of the thing two careful reviewers were reasoning about, and reading the input would have found it before either ledger was written.

Second, smaller result from the same runs, not filed as a finding because it predates this branch: the flagship query shape refuses often at BOTH commits, 4 of 12 before and 6 of 12 after, because only one finding reaches synthesis and the first answer frequently grounds nothing against it. That is a product-quality question for build phase 5.1's eval harness, not a defect this branch introduced.

Method note, stated so the numbers can be attacked: the instrument counts grounding passes, so "repair attempted but the regeneration returned nothing" and "repair never attempted" look identical in the raw log. They are separated by the recorded omission count, which is why the table above reports attempts and completions as two different rows. n is 12 per commit against a sampling model, so the 7-of-7 versus 1-of-7 split is the load-bearing figure and the single-run outcomes are not.
