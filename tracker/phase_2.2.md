# Phase 2.2: deterministic cite-or-refuse and the first trust signal

Build phase 2.2 delivers the Write step's deterministic half: the Section 8.1 findings list Synth is given, the Section 8.2 grounding pass that decides what survives, the Section 8.3 trust signal, the Section 8.4 refuse path, Layer 1 provenance on every citation, and the two required tests from Section 23.

Depends on: build phase 2.1 (done, merged as PR #15)
Branch: `phase/2.2-write-step-grounding`
Spec: `requirements/Technical_specification.md` Sections 8, 9, 23
Reference: `LEARNINGS.md`'s build phase 2.1 retrospective, `docs/build/Build_workflow_cadence.md` stage 5

## Phase premise (the done-when)

A real question reaches the live graph, comes back as rows, and leaves as prose a reader can trust: every factual clause carries a marker, every marker resolves to a finding that actually supports it, every citation is a claim that was checked rather than a row that was fetched, and a question the graph cannot answer refuses with somewhere to go instead of a fabricated answer.

The verify surface is `tests/system_03_search_agent/core/test_write_grounding_premise.py`, not a suite total. Build phase 2.1's whole retrospective is that a green suite proved nothing about whether the answer was right.

## Phase open status: IN PROGRESS

Opened 2026-08-03.

Stage 5, the blocking premise gate, is satisfied: the gate was written before any Write-step code and run against the unmodified 2.1 Write step, where it failed 7 of 10. Evidence recorded under "Premise gate" below.

## What was already true when this phase opened

Verified at phase open rather than assumed:

- The event contract already types `trust_signal` and the full `CitationPayload`, including Section 9.2's four added fields. Neither had ever been emitted: `grep` found zero `TrustSignalPayload` constructions in `src/`.
- `write_node` made a synth-tier model call with a bare user question as its only message and discarded the response entirely. No narrative reached any surface.
- `trust_outcome` was derived from whether any fetched row carried a `source_url`, not from whether anything was grounded.
- Build phase 2.1's premise gate is 8 of 9, not the 9 of 9 recorded in `requirements/phase_6/Continuation_prompt.md`. See F-2.2-01.

## Premise gate

File: `tests/system_03_search_agent/core/test_write_grounding_premise.py`

Written first and watched failing, per the blocking cadence stage. Ten questions, real model, real graph, assertions on the meaning of the answer text.

Result against the unmodified 2.1 Write step, 2026-08-03: 7 failed, 2 passed, 1 skipped. The two that passed did so vacuously on an empty narrative, which is itself recorded as a gate weakness below rather than counted as coverage.

Coverage is stated in the file's own module docstring, per `.claude/rules/goal-contracts.md` and the F-2.1-A5-03 lesson: answer shape (set, scalar, string property), hop depth (0, 1, 2), anchor type (Gene and Disease), the refuse path, the grounding pass itself, the trust signal, and synthesis-layer injection. Deliberately omitted, each with a reason: Layer 2 and Layer 3 findings, triangulation's concordant and discordant branches, `assertion_confidence` values `hedged` and `contested`, multi-tool answers, and cost or latency.

Known gate weakness, stated rather than hidden: `test_every_factual_clause_in_the_answer_carries_a_marker` passes vacuously when the narrative is empty, since an empty string contains no unmarked clause. It is sound only in combination with `test_a_disease_answer_states_the_diseases_in_prose`, which requires a non-empty narrative. Neither test is safe to read alone.

## Ticket map

| Ticket | Slice | Files |
|--------|-------|-------|
| T-2.2-01 | Section 8.1, the findings list and the Synth prompt | `synthesis/findings.py` |
| T-2.2-02 | Section 8.2, the grounding pass | `synthesis/grounding.py` |
| T-2.2-03 | Section 8.3, the trust signal | `synthesis/trust.py` |
| T-2.2-04 | Section 8.4, the refuse path | `synthesis/refuse.py` |
| T-2.2-05 | Contract additions, additive within v1 | `contracts/events.py` |
| T-2.2-06 | Integration: the Write step rewired | `core/graph.py` |
| T-2.2-07 | The two required tests from Section 23 | `tests/system_03_search_agent/synthesis/test_required_paths.py` |
| T-2.2-08 | The premise gate | `tests/system_03_search_agent/core/test_write_grounding_premise.py` |

## Tickets

### T-2.2-01: the Section 8.1 findings list and the Synth prompt

Status: in review
Files: `src/system_03_search_agent/synthesis/findings.py`

Acceptance criteria:
- [x] `SynthFinding` carries Section 8.1's seven fields, with `as_schema_dict` returning exactly those seven
- [x] The findings list is code-built from `Finding.structured_fields`, never model-built
- [x] Only `structured_pass_through` findings with `status == "ok"` contribute
- [x] A row with no resolvable `source_url` is skipped, never cited without one
- [x] Duplicate facts collapse on `(source_url, field, field_value)`
- [x] The list is capped, and the caller can tell a capped list from a complete one
- [x] The Synth system instruction is fixed text with no interpolation, so it stays inside the stable prompt prefix
- [x] The question is delimited and labelled as data

Evidence:
- `SynthFinding`: `findings.py:82-120`. `build_synth_findings`: `findings.py:157-230`
- Dedup on `(source_url, field, field_value)`: `findings.py:196-200`. Before it, the flagship disease question produced two findings per disease, one for the artifact `name` and one for a derived field whose value was the CURIE the row already carried
- Cap wired to the citation cap, not the module default: `core/graph.py`, `max_findings=_MAX_CITATIONS_PER_ANSWER`
- `SYNTH_SYSTEM_INSTRUCTION` is a module-level constant with no f-string: `findings.py`

History:
- 2026-08-03 lead: implemented. Set in-review, not done: the lead built this and does not close its own tickets.

---

### T-2.2-02: the Section 8.2 grounding pass

Status: in review
Files: `src/system_03_search_agent/synthesis/grounding.py`

Acceptance criteria:
- [x] All seven Section 8.2 steps implemented in order
- [x] Matching is exact-or-substring after normalization, with no similarity score anywhere in the module
- [x] A hallucinated marker drops its clause
- [x] An unmarked factual clause is stripped; framing language survives
- [x] Whole-answer refuse when stripping removes the core ask
- [x] Markers renumbered 1..M with no gaps, `citation_id` untouched
- [x] `stripped_count` retained for the audit trail

Evidence:
- `ground_claim` matches the spec's own code block, plus the empty-value guard: `grounding.py`
- 20 tests in `tests/system_03_search_agent/synthesis/test_required_paths.py`, all passing

History:
- 2026-08-03 lead: implemented. Three defects found by its own tests and by the premise gate during the phase, all fixed: trailing punctuation counted as an unmarked claim; the F-2.2-02 number check stripping question-supplied identifiers; leading clause glue reaching `claim_text`. Set in-review.

---

### T-2.2-03: the Section 8.3 trust signal

Status: in review
Files: `src/system_03_search_agent/synthesis/trust.py`

Acceptance criteria:
- [x] Risk tier computed per claim, not per query, defaulting to `low`
- [x] Triangulation compares categorical values across independent-ORIGIN sources, never layers
- [x] The Section 8.3.3 decision table transcribed as data, checkable line by line against the spec
- [x] Answer-level aggregation takes the most restrictive outcome
- [x] An empty outcome list aggregates to `refuse`, never `answer`
- [x] `triangulated` is a tri-state: None means not evaluated, which is not False

Evidence:
- `DECISION_TABLE` is a dict literal with one entry per Section 8.3.3 row: `trust.py`
- `_origin_of` derives origin from the CURIE prefix, so a Layer 1 snapshot and a Layer 2 live fetch of the same database will not count as two independent sources when build phase 3.4 arrives

History:
- 2026-08-03 lead: implemented. Set in-review.

---

### T-2.2-04: the Section 8.4 refuse path

Status: in review
Files: `src/system_03_search_agent/synthesis/refuse.py`

Acceptance criteria:
- [x] Five construction steps, with `safe=""` full percent-encoding
- [x] The host pin validates the CONSTRUCTED url, not the input
- [x] A refusal always carries the fallback link
- [x] `query_term` prefers the resolved entity string over the raw query text (Section 8.4 step 2)

Evidence:
- `build_fallback_link` raises `FallbackLinkError` rather than returning a link off NCBI: `refuse.py`
- Tested including the tampered-base case: `test_the_fallback_link_is_host_pinned_on_the_constructed_url`
- The resolved-entity preference closes a reflection gap the premise gate found: an injected instruction was being percent-encoded into a user-visible link. See F-2.2-03.

History:
- 2026-08-03 lead: implemented. Set in-review.

---

### T-2.2-05: contract additions

Status: in review
Files: `src/system_03_search_agent/contracts/events.py`

Additive within v1 per Section 2.6, which permits a new optional field and forbids removing one or changing a field's meaning. Four optional fields on `TrustSignalPayload`, each defaulting to None, so every payload built before this phase validates unchanged:

- `citation_id`: the Section 9.1 join key binding a trust signal to its citation
- `scope`: `claim` or `answer`, so a surface can tell a per-chip verdict from the Section 8.3.4 banner
- `message` and `fallback_link`: Section 8.4's refuse payload, whose spec example shows exactly these keys. `fallback_link` carries the same host pin as every `source_url`

History:
- 2026-08-03 lead: implemented. Set in-review.

---

### T-2.2-06: the Write step rewired

Status: in review
Files: `src/system_03_search_agent/core/graph.py`

Acceptance criteria:
- [x] Synth is called with the Section 8.1 findings prompt, and its response is used rather than discarded
- [x] The narrative is emitted as `token` events, one per sentence, with `marker_ids` carrying `citation_id` values
- [x] A citation exists only where a claim survived grounding
- [x] `trust_signal` events are emitted per claim and once for the answer
- [x] `trust_outcome` comes from the Section 8.3 decision table
- [x] The citation cap from build phase 2.1 is not weakened
- [x] The truncation note follows the narrative rather than preceding it, and fires for `flag` and `ask` as well as `answer`

Evidence:
- Full Python suite: 988 passed, 0 failed
- `ruff check src/`: clean. `ruff check tests/`: the same 2 pre-existing errors build phase 2.1 already recorded, verified unchanged against a stashed baseline
- Live e2e suite against the real graph: 22 passed

History:
- 2026-08-03 lead: implemented. Set in-review.

---

### T-2.2-07: the two required tests from Section 23

Status: in review
Files: `tests/system_03_search_agent/synthesis/test_required_paths.py`

20 tests, no model call and no network. `test_cite_or_refuse_compliance` and `test_zero_retrieval_refusal` are implemented as the two test classes Section 23 names.

History:
- 2026-08-03 lead: implemented, 20 passing. Set in-review.

---

### T-2.2-08: the premise gate

Status: done
Files: `tests/system_03_search_agent/core/test_write_grounding_premise.py`

Done rather than in-review because its acceptance criterion is that it FAILED before the code existed, which is recorded above with its result, and that is not a judgment the judge needs to re-derive.

---

## Findings

### F-2.2-01: build phase 2.1's premise gate is 8 of 9, and a syntax flake is why

Severity: medium
Status: open
Raised by: lead, 2026-08-03, at phase open

`requirements/phase_6/Continuation_prompt.md` and `CLAUDE.md` both record the 2.1 premise gate at 9 of 9. Measured at 2.2's phase open: 7 passed, 1 xpassed, 1 failed.

The failure is `test_all_four_of_the_genes_diseases_survive_to_the_answer`, and it is nondeterministic. Generation intermittently emits Cypher with no parentheses around node patterns:

```
MATCH g:Gene {id: $e_NCBIGene_672}-[:gene_associated_with_condition]->d:Disease
```

The graph rejects it as a SyntaxError, and nothing retries. Re-running the same test three times passed three times, which is what makes this a flake rather than a regression.

Two things follow, and the second is the real one:

- The documented 9 of 9 is a single observation, not a stable rate. Roughly 1 run in 10 fails.
- `cypher_query` has no retry on a generated-Cypher SyntaxError. A valid question fails outright some fraction of the time for a reason the user cannot act on. The validate-then-execute pipeline has a repair retry for validator rejections; a server-side SyntaxError on an accepted query does not reach it.

Not fixed in this phase: it is a generation-side defect and 2.2's deliverable is the Write step. The premise gate re-runs once on this specific error string so it reports on synthesis rather than on generation luck, which is a workaround in the gate, not a fix.

### F-2.2-02: the Section 8.2 substring rule accepts invented text riding along

Severity: high
Status: mitigated, needs spec reconciliation
Raised by: lead, 2026-08-03, from a required-path test

Section 8.2 step 5 accepts a claim when "one is a substring of the other". The `field_value in claim_text` direction has a hole. Given a finding whose value is `15310`:

```
BRCA1 has 15310 variants and 400 orthologs [1]
```

grounds cleanly. The ortholog count is invented, carries a real marker, cites a resolving URL, and ships. This is build phase 2.1's failure shape (a fluent, fully cited answer to a different question) relocated from retrieval into synthesis, and the spec's rule as written cannot see it.

Mitigated by `numbers_are_supported` in `grounding.py`: every standalone number in a claim must appear in the cited value or in the user's own question. It targets numbers because a number is the highest-risk invented content in a biomedical answer and is unverifiable by eye. It only ever rejects claims Section 8.2 would accept, so it cannot weaken the gate.

Not closed: this is a tightening of a locked specification. It needs a Step 6.2 reconciliation decision on whether the spec text changes to match, and an adversary should attack the non-numeric version of the same hole (invented entity names riding along with a matched identifier), which is NOT covered.

The lead raised this and must not also close it.

### F-2.2-03: refusals reflected the raw question, injected text included

Severity: low
Status: fixed, needs verification
Raised by: the premise gate, 2026-08-03

Section 8.4 step 2 allows `query_term` to be either the raw query text or the resolved entity string. The first implementation used the raw text, so a refusal to an injection-carrying question produced a user-visible link containing `...causes%20Marfan%20syndrome...`.

Nothing is executed and nothing is asserted, so this is not the injection defect itself. It is attacker-supplied text reflected into a rendered link, which is worth not having.

Fixed by preferring the resolved entity string, which Section 8.4 step 2 already permits and which is the better search term regardless. Falls back to the raw text only when nothing resolved.

Found by the premise gate rather than by a reviewer, which is the gate working as intended.

### F-2.2-04: the findings block did not express the answer, and the model correctly refused

Severity: high
Status: fixed, needs verification
Raised by: lead, 2026-08-03, by printing the model's actual input

The first version of `render_findings_block` rendered `field` and `field_value` only. For the system's flagship question that produced:

```
[1] curie: MedGen:C0346153
[2] curie: MedGen:C2676676
[3] curie: MedGen:C3280442
[4] curie: MedGen:C4554406
```

A real model, handed that and asked "which diseases are associated with NCBIGene:672?", replied `I could not find information on this.` and was right to. Four opaque identifiers under a field named `curie` do not say they are diseases. The correct answer was not expressible from what the model was given, so seven premise-gate questions failed and every one of them pointed at synthesis.

This is build phase 2.1's root cause repeating one layer up: a composition defect between a correct retrieval step and a correct generation step, with the assembly between them handing over less than the answer needs. It was found in one probe by printing the exact prompt, which is what `.claude/rules/attack-the-constraint.md` says to do first and what 2.1 took five rounds to do.

Fixed by rendering the record type and identifier alongside the value, so the block reads `[1] Disease record MedGen:C0346153`.

Worth noting for the judge: no test in the 988-test suite could see this. Every one of them mocks the model, and a mocked model returns whatever the test author already decided was correct.

## Decisions taken in this phase

Logged to `DECISIONS.md`. Recorded here with the reasoning that belongs to the phase:

- A corrupted row is cited on its CURIE, not on the vocabulary artifact. This REVERSES a build phase 2.1 decision and needs product-owner confirmation. See the note below.
- The findings cap is set to the citation cap, since findings bound citations by construction.
- `numbers_are_supported` tightens Section 8.2. See F-2.2-02.
- The refuse path uses the resolved entity string. See F-2.2-03.

### The one reversal, confirmed by the product owner 2026-08-03

Status: CONFIRMED. The product owner delegated the call to the lead's recommendation on 2026-08-03 and the 2.2 behavior stands. The judge pass was asked to assess it independently anyway, since a decision the lead recommended and the lead implemented has had no adversarial look at it, and the specific thing to check is whether the hedge and the payload marker actually survive to the wire. If they do not, the argument below does not hold and this reopens.

Build phase 2.1 decided that a row whose `name` is a vocabulary artifact (`name="MeSH"` on a `Disease`, a documented MedGen ETL defect) should be cited on the artifact with `assertion_confidence` downgraded to `hedged`, on the principle that the corrupted value is shown rather than hidden.

Build phase 2.2 cites the row's CURIE instead. Three reasons:

- "MeSH" is not the disease's name, so showing it as the claim shows a false statement with a caveat attached. The CURIE is true and resolves to a real record.
- Handing Synth `field_value="MeSH"` gives it two options, both bad: write something false, or write the CURIE and have the grounding pass strip it as unsupported.
- Under a grounding pass, the 2.1 behavior is unreachable anyway: a claim citing "MeSH" would have to SAY "MeSH" to survive.

Nothing is hidden. The `hedged` downgrade is unchanged, the artifact is still reported verbatim on the finding payload via `vocabulary_artifact_fields`, and both are asserted by tests.

This resolves the "vocabulary-artifact rule would be strictly better as a name frequency table" item from the continuation prompt, differently than that note guessed: the frequency table was an idea for detecting the artifact better, and the actual defect was what the code did after detecting it.

## Open items inherited by this phase, and their status

From `requirements/phase_6/Continuation_prompt.md`:

| Item | Status |
|------|--------|
| F-2.1-C07, fourth status value for "matched plenty, cited none" | Addressed. `_UNGROUNDED_SYNTHESIS_REFUSAL_MESSAGE` distinguishes a refusal caused by ungroundable synthesis from one caused by uncitable rows, with a different `scope` and `source`. Implemented as a distinct message rather than a new enum value, since the two causes differ in what an operator should do, not in the tool's own status |
| F-2.1-A5-02, consumer half | Addressed. `vocabulary_artifact_fields` now has a real consumer: it drives the CURIE fallback in `build_synth_findings` |
| Vocabulary-artifact rule | Addressed. See the reversal note above |
| Premise-gate coverage statement | Done. Stated in the gate's own module docstring |
| F-06, 2 of 6 model calls bypass the stable prefix | NOT addressed yet |
| F-2.1-C15, generation half | NOT addressed |
| F-2.1-A5-05, `mentioned_in` latency | NOT addressed |
| Fresh judge and adversary pass over the 2.1 surface | NOT started |

## Verification status

| Gate | Result |
|------|--------|
| Full Python suite | 988 passed, 0 failed |
| Required paths, Section 23 | 20 passed |
| Live graph e2e | 22 passed |
| `ruff check src/` | clean |
| `ruff check tests/` | 2 pre-existing errors, unchanged from baseline |
| Premise gate, before the code | 7 failed, 2 passed, 1 skipped |
| Premise gate, after the code | NOT YET RUN to completion |
| Judge pass | NOT RUN |
| Adversary pass | NOT RUN |
| `eval-harness` | NOT RUN. Required before shipping any answer-generation feature |
| Frontend suite | NOT RUN |

This phase is NOT ready to close. The premise gate is the phase premise and has not yet been re-run to completion after the fixes.
