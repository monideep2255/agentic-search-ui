# Build phase 4.7 judge report, round 1

Branch: `phase/4.7-cq-routing`
Range reviewed: `b3d030e..HEAD` (HEAD = `e79741d`)
Date: 2026-08-23
Role: judge, read-only. Nothing in `src/`, `tests/` or `tracker/phase_4.7.md` was modified by this round.

## Verdict: FAIL

**RULE 4 STOP.** This round was halted before completion. A defect was found INSIDE `e79741d`, the commit written earlier in this phase to fix this phase's own finding F-4.7-01. Per the standing rule, the round does not continue and the finding is not batched with others: a finding inside a fix means the fix approach is wrong rather than incomplete.

The blocking finding is F-4.7-J1-01 below, labelled `Regression of: F-4.7-01`.

Round 1 of the two-round budget is therefore CONSUMED without a full sweep. Sections 2 through 10 of the judge brief (schema validation at every hop beyond what is noted, the retired-heuristic sweep, the prompt-cache byte-equality proof, the F-4.6-A-08 writer audit, the v1 scope check, the `_STEP_TIER` cost question, the `state.py` scope question, and the retired-test audit) were NOT completed. What was measured before the stop is recorded under "State at the stop" so the next round does not re-measure it.

---

## The blocking finding

| ID | Severity | file:line | Blocks |
|----|----------|-----------|--------|
| F-4.7-J1-01 | CRITICAL | `tests/system_03_search_agent/core/test_cq_routing_premise.py:440` and `:374`; root cause `src/system_03_search_agent/core/graph.py:1173` | YES |

**Regression of: F-4.7-01.**

### What is wrong

Premise gate arm P1, `test_p1_a_database_name_in_passing_is_not_the_subject`, is the arm this phase's own tracker calls "the phase's reason to exist" and runs first for that reason. Its load-bearing assertion still CANNOT FAIL after `e79741d`, for all FOUR parametrized cases, including the Q10 case that `e79741d`'s commit message declares was "sound".

The arm's assertion is:

```python
resolved = _resolved_texts(payload)
assert passing_mention not in resolved, (
    f"{label}: `{passing_mention}` is a database name mentioned in "
    ...
```
(`test_cq_routing_premise.py:440`)

and `_resolved_texts` reads the `text` field of each resolved entity:

```python
def _resolved_texts(payload: dict[str, Any]) -> list[str]:
    return [entity["text"] for entity in _resolved(payload)]
```
(`test_cq_routing_premise.py:374-375`)

But `think_node` never puts a surface form in `text` for a model-extracted entity. It overwrites it with the CURIE:

```python
resolved_entities.append(EventResolvedEntity(text=curie, curie=curie, confidence=1.0))
```
(`src/system_03_search_agent/core/graph.py:1173`)

The only other producer of entries in that list is `resolve_exact_identifiers`, at `graph.py:1387`, whose `text` is a match of `_CURIE_IN_TEXT_PATTERN` (contains a `:`), `_RSID_PATTERN` (`rs\d+`), `_BARE_PMID_PATTERN` (`PMID` + digits) or `_ACCESSION_PATTERN` (`N[MCP]_\d+`). None of those four patterns can ever produce the strings `GTR`, `AMR` or `SRA`.

So `_resolved_texts()` structurally yields only CURIEs and exact-identifier literals. The bare token `GTR`/`AMR`/`SRA` cannot appear in it under ANY behaviour of the model, the confirmation call, or the loop. The assertion is unfalsifiable.

### Why this is a regression of F-4.7-01, not a new sibling

`e79741d` closed F-4.7-01 with two claims, both in its commit message and both restated in `tracker/phase_4.7.md:105`:

> "Closed two ways: the strings now name the database... AND the arm carries a populate-check asserting the token is present in the question before asserting it is not resolved. The second half is the durable fix, because it makes the defect mechanical rather than a matter of someone noticing."

Both halves are falsified as a closure of the defect:

- The populate-check added at `test_cq_routing_premise.py:415-421` proves only that the token is present in the QUESTION. It does not prove the token is present in the CODOMAIN of the value the assertion reads. The arm still cannot distinguish "the control held" from "the control could not be violated", which is the exact definition this phase's own docstring gives for a non-arm at `test_cq_routing_premise.py:52-54`.
- "Makes the defect mechanical rather than a matter of someone noticing" is the specific claim that fails. The defect survived the mechanism.

This is the same shape as build phase 4.11's arm that was "vacuous twice, in two different ways, while quoting the lesson against vacuous arms in its own docstring", which `test_cq_routing_premise.py:44-47` quotes. It has now happened a third time, in the file that quotes it.

### Evidence, mutation-executed

Two independent executions, both offline, both against the shipped code.

Mutation 1, at the assertion layer. Construct the `think` payload `think_node` emits in exactly the case P1's docstring names ("a `think_node` that refuses nothing but still resolves `SRA` as a gene has not fixed anything", `test_cq_routing_premise.py:409-411`), then run P1's populate-check and its real assertion against it using the gate file's own helpers:

```
Q4 Lynch syndrome        token=GTR  resolved_texts=['NCBIGene:6301'] -> P1 assertion PASSES=True
Q5 Salmonella isolate    token=AMR  resolved_texts=['NCBIGene:6301'] -> P1 assertion PASSES=True
Q6 SRA metadata          token=SRA  resolved_texts=['NCBIGene:6301'] -> P1 assertion PASSES=True
Q10 BioProject bundle    token=SRA  resolved_texts=['NCBIGene:6301'] -> P1 assertion PASSES=True
```

All four cases GREEN on the injected defect, populate-check satisfied in all four.

Mutation 2, driven through the REAL `think_node` code path rather than a hand-built payload. `_dispatch_tier_call` stubbed to return a classification extracting `{"text": "SRA", "entity_type": "gene"}`, and `resolve_symbol_to_curie` stubbed to confirm it. The `think` event actually emitted by `think_node` was then read with the gate's own `_resolved_texts`:

```
emitted resolved_entities: [{'text': 'NCBIGene:6301', 'curie': 'NCBIGene:6301', 'confidence': 1.0}]
P1 sees resolved_texts = ['NCBIGene:6301']
P1 assertion `'SRA' not in resolved_texts` -> True (True == arm stays GREEN on the mutation)
```

The arm stays green while `SRA` is being carried as a resolved entity of the question. That is precisely the state F-2.0-15 describes and precisely what P1 exists to catch.

### What this costs the phase's evidence

`e79741d`'s commit message reports `16 passed in 298.11s` for the live gate. Four of those sixteen passes are P1 cases whose primary assertion cannot fail. The live green does not establish what the phase claims it establishes.

Note also that P1 was never watched failing. `tracker/phase_4.7.md:76-88` records the gate-first red run as arms P2 and P3 only, `2 failed, 14 deselected in 63.56s`. The four arms that carry the phase's stated reason to exist have no recorded red.

The arm is not 100% inert: its second assertion, `"could not identify that gene" not in answer.lower()` at `test_cq_routing_premise.py:447`, is falsifiable and does provide coverage. But the arm's own docstring states that assertion alone is insufficient, which is why the token assertion was written. The insufficient half is the only half that works.

### Root cause, and why the fix is cheap

`think_node` has the surface form in hand and discards it. `_ThinkExtractedEntity.text` (`graph.py:906`) carries the exact span the model named, and `_confirm_extracted_entities` (`graph.py:1053-1094`) even keeps it in `gene_symbols`, but `_EntityResolution` returns only `curies` and the surface form is dropped before `graph.py:1173` runs.

The comment justifying the CURIE-for-text substitution lives at `graph.py:2118-2120`, in `plan_node`, and its stated reason is "the free-text mention is not recoverable at this point". That reason is true in `plan_node` and FALSE in `think_node`. The justification was carried across a boundary where it stops holding.

Every downstream consumer of `resolved_entities` reads `.curie`, never `.text`. Verified by grep across `src/`: `graph.py:1168`, `graph.py:1802`, `graph.py:2063` and `core/run.py:393` are the consumers, and none reads `text`. So preserving the surface form in `text` for model-extracted entities is a non-breaking change.

That is a suggestion, not a directive: this round is a stop, and the fix approach is the product owner's and the lead's call, not the judge's. What the judge asserts is only that P1 as written cannot grade what it claims to grade.

---

## State at the stop

Recorded so round 2 does not re-measure it. These are measurements, not a verdict on the checks they belong to.

### Full Python suite

```
$ source venv/bin/activate && python -m pytest tests -q -p no:randomly 2>&1 | tail -12
=========================== short test summary info ============================
FAILED tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py::test_a_genuine_cross_layer_conflict_is_detected_and_flagged
FAILED tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py::test_a_stale_volatile_field_auto_cross_verifies_against_live_layer_2
FAILED tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py::test_ncbi_efetch_citation_defaults_to_primary_assertion
FAILED tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py::test_ncbi_dbsnp_citation_carries_full_provenance
FAILED tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py::test_pubtator_and_litvar2_citations_default_to_literature_mention
FAILED tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py::test_clinicaltrials_search_citation_defaults_to_external_annotation
6 failed, 3757 passed, 146 skipped, 1 xfailed, 4 warnings in 83.74s (0:01:23)
```

Against the stated branch-point baseline of `6 failed, 3752 passed, 137 skipped, 1 xfailed`: the same six pre-existing failures, all in `test_citation_trust_full_premise.py`, no new failure. `test_persona.py` did not flake in this run (F-4.7-04, not re-filed).

### ruff

```
$ ruff check src/
All checks passed!
```

### Doc drift

```
$ python tracker/check_doc_drift.py --check
AGENTS.md:16: says 3896 python tests (computed: 3910)
CLAUDE.md:16: says 3896 python tests (computed: 3910)
requirements/Plan.md:20: says 380 decisions.md rows (computed: 383)
requirements/phase_6/Continuation_prompt.md:101: says 3896 python tests (computed: 3910)
requirements/phase_6/Continuation_prompt.md:116: says 380 decisions.md rows (computed: 383)
requirements/phase_6/Continuation_prompt.md:447: says 3896 python tests (computed: 3910)
error: 10 facts computed | 6 stale | 0 structural
```

FAILS. T-4.7-10's acceptance criterion is that this command passes. T-4.7-10 is still `todo` in `tracker/phase_4.7.md:64`, so this is unfinished work rather than a defect, and it is recorded here only so it is not rediscovered.

### Working tree

```
$ git status --short
[no output]
```

Clean. No mutation was applied to any tracked file: both mutations above were executed by monkeypatching in a scratch script outside the repository, never by editing `src/` or `tests/`.

### Checks that were completed before the stop and did not fail

Stated with evidence, since a check without evidence is a fail:

- Brief item 1, the classification is real, PASSES. `think_node` reads the response: `_parse_think_classification(response.content)` at `graph.py:1146`, and `classification.query_class` is what reaches state at `graph.py:1177` and `:1186`. A value outside Section 17's five shapes is rejected, not coerced: `_ThinkClassification.query_class` is `Literal["lookup", "single_hop", "multi_hop", "aggregate", "exploratory"]` at `graph.py:920`, `model_config = ConfigDict(extra="forbid")` at `:918`, and a `ValidationError` becomes `ThinkClassificationUnavailableError` at `graph.py:1044-1046`, which `think_node` turns into a `step_error` at `graph.py:1147-1163` rather than a default. The literal `"lookup"` appears in `think_node` only at `graph.py:1140`, as the argument to `budget_for_step("think", "lookup")`, which is Think's own step budget and not the emitted class.
- Brief item 4, the retired heuristic is gone, PASSES. `grep -rn "_SYMBOL_CANDIDATE_STOPWORDS\|_GENE_SYMBOL_TOKEN_PATTERN\|_CORF_GENE_TOKEN_PATTERN\|_resolve_query_entities" src tests frontend` returns only comment and docstring references (`graph.py:333`, `:341`, `:398`, `:1299`, `:1300`, `:1693`) and test comments; no definition and no call site survives. No `except` clause reconstructs a token guess: the only `except` paths in `think_node` are `QueryCapExceededError` (`graph.py:1142`), `HarnessCallError` (`:1144`) and `ThinkClassificationUnavailableError` (`:1147`), and all three return without resolving anything.
- Brief item 2, partial. `_ThinkClassification` carries `extra="forbid"` and `max_length=20` on the `entities` array (`graph.py:922`), and `_ThinkExtractedEntity.text` carries `max_length=200` (`graph.py:906`), both applied before any field is read, at `graph.py:1146`. This satisfies the multi-agent schema gate for the Think hop specifically. The wider "every hop" sweep was not completed.
- Brief item 3, no fabricated CURIEs, PASSES ON THE CODE PATH. `_confirm_extracted_entities` (`graph.py:1053-1094`) contributes a CURIE only from `await resolve_symbol_to_curie(symbol)` returning non-`None`; an unconfirmed span goes to `unresolved` and never becomes an entity. Traced through the call, not from the docstring. Note that P6, the arm that is supposed to grade this, was NOT mutation-tested before the stop.

### Checks NOT performed

Explicitly listed rather than left implied, because an unperformed check is not a pass:

- Mutation testing of every gate arm. Only P1 was mutation-tested. P2 through P12 were NOT. The mutation-results table this report was to carry cannot be produced from round 1.
- Brief item 5, the SHA-256 stable-prefix byte-equality proof against a real pair of requests. `build_stable_prefix` reads as prefix-clean (`harness/cache.py:539-587`, no timestamp, trace id or session id parameter, few-shot pool sourced from the process-cached `few_shot_pool.load_pool()`), but no execution evidence was gathered.
- Brief item 6, the F-4.6-A-08 writer audit. `few_shot_pool.append_example` (`orchestrator/few_shot_pool.py:187-275`) reads as a single `fcntl.flock` + `os.replace` writer with `promotion._append_pool_entry` delegating to it, but the concurrency claim was NOT executed and the two-writer question was NOT settled.
- Brief item 7, the v1 scope boundary check against Section 17's two excluded upgrades and the deterministic-route-lookup prohibition.
- Brief item 8, the `_STEP_TIER["think"]` correctness and per-query cost question.
- Brief item 9, the `core/state.py` out-of-scope-file question.
- Brief item 10, the retired-test audit over `git diff b3d030e..HEAD -- tests/`.
- The live premise gate was NOT re-run. `e79741d`'s reported `16 passed in 298.11s` is taken as reported, and F-4.7-J1-01 establishes that four of those sixteen passes do not mean what they are being read to mean.

---

## Is the phase's done-when met, as opposed to each ticket being done?

No, and the gap is at the verify surface rather than at the tickets.

`tracker/phase_4.7.md:24-25` states the done-when and, in the same contract, states its verify surface: "this phase's premise gate, run live... every arm carrying a populate-check and every arm mutation-proven".

Two clauses of that verify surface are not satisfied:

- "Every arm mutation-proven" is not true. There is no record in `tracker/phase_4.7.md` of a mutation and an observed red for any arm, and the one arm this round mutation-tested survived its mutation green.
- "Every arm carrying a populate-check" is satisfied in letter and defeated in substance for P1. The populate-check is present and passes; the arm is still unable to fail.

The done-when's own first clause is "none is refused because a database name mentioned in passing was misread as a gene symbol". That clause has exactly one grader in the phase, P1, and P1 cannot grade the half of it that names the token. The tickets may each be individually complete; the outcome the tickets exist to produce is not evidenced.

This is the phase's own trap list turned back on it. `tracker/phase_4.7.md:48` names "A GATE ARM THAT CANNOT FAIL" as trap three and cites build phase 4.11's three vacuous arms. The trap was named, the countermeasure was designed, the countermeasure was applied, and the arm is still vacuous by a route the countermeasure does not cover. `.claude/rules/goal-contracts.md` is unambiguous on the consequence: a run whose verify surface cannot detect the failure it exists to detect is a failed run, not a completed one.

---

## Recommended disposition

Round 1 is consumed. One round remains in the budget. Per Rule 4 this is an escalation to the product owner, not a lead decision:

1. F-4.7-J1-01 is fixed, and the fix is proven by mutation with the mutation and the observed RED recorded in `tracker/phase_4.7.md`, not asserted.
2. Every remaining arm, P2 through P12, is mutation-tested before the next judge round opens, so round 2 is not spent rediscovering vacuity one arm at a time.
3. Round 2 then runs the eight brief items this round did not reach.

Reopening F-4.7-01 rather than filing F-4.7-J1-01 as a fresh finding is also defensible and is the product owner's call. This report files it as a new id with an explicit `Regression of:` label so both the original finding and the failure of its closure stay visible.
