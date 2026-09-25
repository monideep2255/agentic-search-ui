# Builder A report, phase 8.1

## Follow-up tickets (second dispatch)

Merged `phase/8.1-good-questions-answer` into this worktree (fast-forward,
`eb943c3..5aa0c3e`, brings builder B's grounding fix, builder C's MedGen
parser, `tracker/phase_8.1.md`, and builder_B.md/builder_C.md). No files
outside my fence touched.

## T-8.1-06b: a phenotype question names phenotypes

Read `tracker/phase_8.1.md` (F-8.1-04) and `testing/Developer/reports/
2026-09-25_phase_8.1/builder_C.md` in full. Builder C's parser
(`tools/ncbi_eutils_actions.py`, commit `888016d`) always sets
`record.fields["clinical_features"]` on a `db="medgen"` record: a bounded
list of `{"name": ..., "hpo_id": ...}` items, `[]` when MedGen has none.
Confirmed by builder C live: 30 features for Marfan syndrome (the cap).

Cause confirmed by reading `core/graph.py`: `_BREADTH_FIELDS_BY_PURPOSE
["medgen_summary"]` (was `("title", "definition", "semantictype")`) is
the allowlist `_ncbi_efetch_output_to_structured_fields` filters every
medgen row's `fields` through; `clinical_features` was absent, so it was
dropped at that filter, before any row, finding or citation existed.
Builder C independently confirmed this live (a real run that answered
with no phenotype ever cited).

Fix, `core/graph.py` only:
1. Added `"clinical_features"` to the `medgen_summary` allowlist tuple.
2. New `_medgen_clinical_features_text(features)`: turns the list into a
   single citable string, `"Name (HP:xxxx), Name2 (HP:yyyy), ..."`, the
   same discipline `_sra_run_accessions` already applies to SRA's `runs`
   field, because `synthesis/grounding.ground_claim` matches a clause
   against source TEXT by containment and can never quote a Python list.
   Reads defensively (`isinstance` at every level, skips a malformed item,
   never raises): this is parsed content one hop from a live NCBI
   response, still untrusted.
3. When the list is empty, missing, or entirely malformed, returns the
   fixed sentence `_MEDGEN_NO_CLINICAL_FEATURES_TEXT` ("MedGen lists no
   clinical features for this condition") instead of an empty string or a
   dropped key. This is code composing a verifiable fact from a value
   already fetched (the record's own empty list), never a hardcoded
   decision about what to search or classify: the row it rides on keeps
   its own `source_url`, so the sentence is cited to that MedGen record
   like any other fact.
4. Wired both into the same `if purpose == _MEDGEN_SUMMARY_PURPOSE:`
   block that already unwraps `definition`/`semantictype`, ahead of the
   row cap and sort, matching where `_sra_run_accessions` runs for its
   own purpose.

Unit tests added, `tests/system_03_search_agent/core/test_disease_breadth.py`
(the file that already owns every other MedGen-shape test in this repo):
`test_clinical_features_reach_the_row_as_a_quotable_string` (the populated
case, red against the pre-fix allowlist by construction: the old filter
drops the key entirely, so the assertion would `KeyError`, not fail),
`test_no_clinical_features_states_the_honest_sentence_not_a_drop` (the
empty case, and that the row's own `source_url` is unchanged), and
`test_medgen_clinical_features_text_direct_unit_cases` (the helper in
isolation: empty list, `None`, a non-list, an all-malformed list, one
real item, and a mixed usable/malformed list). Full
`tests/system_03_search_agent/core` suite: 1096 passed, 56 skipped, no
regressions (up from 1093 before this ticket's 3 new tests plus builder
B's and C's own additions already in the merge).

ROUND 2, found from a live run: the round-1 fix (allowlist alone) reached
the tool's structured output but changed nothing a reader saw. Live proof
of that: a researcher-depth run after the allowlist fix still answered
with zero phenotypes named, only the record's title and a code-built
listing. Root cause: `render_finding_body`/`_pick_representative_field`
show exactly ONE field per finding, and `title` always wins over
`clinical_features` on the same row (documented insertion-order
preference). Fixed by adding `_medgen_clinical_feature_rows`, mirroring
`_pubmed_abstract_rows`'s own ADDITIONAL-row pattern: one extra row per
admitted MedGen title row, carrying `clinical_features` as its own,
unshared field, wired into the same post-cap block
`_PUBMED_ABSTRACTS_PURPOSE` already uses. Confirmed via an offline call to
`_ncbi_efetch_output_to_structured_fields` (no live cost): 2 rows now
exist for one MedGen record, the second carrying only `clinical_features`.
Unit tests updated to match (2 rows, not 1) plus the direct-helper cases;
full core suite 1096 passed, 56 skipped, no regressions.

BLOCKED-STOP, ROUND 3, found from two more live runs (researcher and
plain_language) after round 2 landed: the clinical_features finding now
DOES reach the model's own prompt (confirmed via an offline reconstruction
of `run_grounding_pass` against the exact live finding shapes, no live
cost: `_ncbi_efetch_output_to_structured_fields`, `build_synth_findings`
and `render_findings_block` all correctly place and pass it through). Two
independent things outside `core/graph.py` still stop it reaching the
reader:

1. The model itself did not choose to write about it in either live run
   (2 of 2). Both times it grounded a different, real, correctly-cited
   fact instead (the disease's genetic cause or inheritance pattern from a
   PubMed abstract). This is a genuine model choice on a real available
   fact, not a bug: nothing forces the writing model to prefer one true,
   available finding over another. `SYNTH_SYSTEM_INSTRUCTION`, the prompt
   that could ask the model to prioritize a phenotype question's answer,
   lives in `synthesis/findings.py`, not `core/graph.py`.
2. When the model's own prose does not ground the fact, the code-built
   fallback and tail should still show it. Traced with two offline
   reconstructions of the exact live finding set (`build_structured_
   fallback_narrative`, no live cost): `one_finding_per_record`
   (`synthesis/findings.py`, fix-plan item 12.7 round 2) deliberately
   collapses every finding sharing one `source_url` down to ONE, by field
   name, specifically to stop duplicate-title spam for one paper (a real,
   deliberate, documented product decision, not a bug). MedGen's title row
   and the new clinical_features row share the SAME `source_url` (one
   MedGen record), so this collapse picks the title, by the same
   insertion-order-like tie-break as `_pick_representative_field`, and the
   phenotype fact is dropped from the code-built listing every time,
   deterministically, regardless of the model.

Both mechanisms live in `synthesis/findings.py`, which is not in my fence
and is not owned by anyone this phase (`tracker/phase_8.1.md` assigns
builder B only `synthesis/grounding.py` and `synthesis/trust.py`). Per the
phase's own goal contract ("a ticket whose fix needs a file outside its
builder's fence... stops, writes its finding here, and the builder moves
to its next ticket") and the ticket's identical language, I am stopping
here rather than guessing at a fix in a file I do not own.

STATUS: T-8.1-06b PARTIALLY MEETS ACCEPTANCE. What is fixed and verified:
the field is parsed, capped, stringified, honestly discloses an empty
list, and genuinely reaches the writing model's own prompt as its own
citable fact, on every question that resolves a MedGen concept, at both
depths, no regression. What is NOT met: the two live runs so far (1
researcher, 1 plain_language, after the round-2 fix) did not name five
phenotypic features in the answer text, because of the two outside-fence
mechanisms above. RECOMMENDATION for whoever owns `synthesis/findings.py`
next: either widen `one_finding_per_record`'s tie-break to prefer
`clinical_features` over `title` when both exist for one record (a
narrow, low-risk change: a disease's clinical features are strictly more
informative than its bare title in a fallback listing, for ANY disease
question, not just a phenotype-shaped one), or add an explicit instruction
in `SYNTH_SYSTEM_INSTRUCTION` for phenotype-shaped questions.

Live-run budget spent on this ticket: 7 of the 12 available for both
follow-up tickets (5 real runs via `builder_a_live_run.py`, 2 more via a
throwaway diagnostic script with the same mechanics; the two offline
reconstructions used no live call at all). 5 remain for T-8.1-05b.

## T-8.1-05b: the trust line stays the same when the evidence is the same

Read `tracker/phase_8.1.md` (F-8.1-01) and `builder_B.md` in full. Builder
B's diagnosis: `_apply_conflict_flags_to_claim_trusts` only ever
downgrades a `ClaimTrust` already present in `claim_trusts`, the GROUNDED
subset, so an identical question's genuine conflict floors `trust_outcome`
at `flag` on one run and not another, purely because the model chose to
write about both conflicting values one run and not the other. The lead's
decision (option 2): compute the downstream floors over `synth_findings`,
the full retrieval, never over `grounding.claims`.

Fix, `core/graph.py` only, `synthesis/trust.py` untouched (per the
ticket's own constraint): added `_full_retrieval_conflict_exists(synth_findings)`,
which reuses `_layer1_layer2_field_pairs`, `_paired_field_values_agree`
and `detect_conflict`, the SAME rule the per-claim check already uses,
over the full `synth_findings` list rather than the grounded citations.
`SynthFinding` already carries `citation_id` and `source_url`, the only
two attributes `_layer1_layer2_field_pairs` reads off each item, so
`synth_findings` is passed there directly, no synthetic citations needed.
Wired as an ADDITIVE check right after the existing per-claim floor: when
it finds a conflict, `trust_outcome` is floored to `flag` via the same
`aggregate` most-restrictive-wins call every other floor in `write_node`
already uses. The existing per-claim check is untouched (a specific
claim's own `ClaimTrust.outcome` is still rightly a function of what it
cites); this is a second, answer-level check answering a different
question. Neither `ClaimTrust` nor `synthesis/trust.py`'s own tier
meanings change: only whether the answer-level aggregate SEES a conflict
that exists in the evidence, regardless of what the model wrote.

Did not touch `_unaddressed_target_entities` (the OTHER completeness
floor the ticket's title gestures at, "the completeness and cap floors"):
its entire purpose (per its own docstring, F-3.4-A-01) is checking what
the ANSWER addressed, not what was retrieved, so pointing it at
`synth_findings` instead of `citations` would make it never fire,
changing what it means rather than fixing an inconsistency. Builder B's
own diagnosis names only the conflict-flag mechanism as the concrete,
reproduced cause; I fixed that one precisely rather than reinterpreting a
second mechanism into scope on my own guess.

Unit tests added, `tests/system_03_search_agent/core/test_graph.py`:
`_full_retrieval_conflict_exists` in isolation (a genuine conflict, no
conflict, only one layer present), and
`test_same_evidence_gives_the_same_trust_outcome_regardless_of_what_was_grounded`,
the acceptance criterion stated exactly: the SAME `synth_findings` (one
Layer 1 value, one disagreeing Layer 2 value), run through two different
grounded-claim subsets (both conflicting claims grounded, versus only
one), both now give `trust_outcome == "flag"`. Before this fix the second
subset would give `"answer"`, the literal variance builder B measured
live. Full `tests/system_03_search_agent/core` + `harness` suite: 1308
passed, 56 skipped, no regressions.

Live-run proof: 3 local live runs of builder B's own repro question,
"What diseases are caused by variants in the HNF1A gene?", researcher
depth (the same question T-8.1-03 also investigated, for its 127-second
outlier, an unrelated defect):
- Run 1: `trust_outcome: "ask"`, 62 citations, cost $0.0180.
- Run 2: `trust_outcome: "ask"`, 62 citations, cost $0.0184.
- Run 3: `trust_outcome: "ask"`, 62 citations, cost $0.0179.

RESULT: T-8.1-05b MEETS ACCEPTANCE. All 3 runs gave the identical
`trust_outcome` ("ask", from the truncation/completeness notes, not from
a conflict on this particular live evidence, which happened to carry
none this session); the unit test is what proves the FIX specifically,
since a live conflict is not guaranteed to exist in the graph on any
given day (the same reasoning builder B's own report gives for testing
the mechanism offline). Live-run budget used: 3 of the 5 remaining (10 of
12 total across both follow-up tickets).

## Answering the coordinator's question: what does "58 sources, cap 30" mean

T-8.1-02's report said the BRCA1 papers live run "cites 58 sources each"
against a cap of 30. Exact meaning, by code line (`core/graph.py`):

- The 30 is `_MAX_FINDINGS_FOR_MODEL_PROMPT` (line ~6395): the hard
  ceiling on how many findings reach the WRITING MODEL's own prompt in
  one Synth call (`prompt_findings = synth_findings[:_MAX_FINDINGS_FOR_MODEL_PROMPT]`,
  line ~9855). At most 30 findings are ever things the model could choose
  to write a grounded sentence about.
- The 58 is the TOTAL CITATION COUNT the answer emits, which is NOT
  bounded by 30 at all. It is bounded by `_MAX_FINDINGS_FOR_DISPLAY`
  (aliased to `_PLAN_TOOL_CALL_ROW_LIMIT`, 100), the ceiling on how many
  already-fetched, CODE-BUILT rows may reach the citation list, the
  disclosure table and the findings tail (comment above
  `_MAX_FINDINGS_FOR_DISPLAY`, line ~6386). Every citation beyond the
  model's own 30-finding prompt slice comes from the CODE-BUILT tail
  (`unreported_findings`/the Researcher listing, both described in
  T-8.1-06b's finding above), which lists every PREPARED finding the
  model did not mention, up to the 100-row display cap, not the 30-row
  prompt cap. This is deliberate, documented behaviour from the
  2026-09-20 prompt/display split (the comment at `_MAX_FINDINGS_FOR_DISPLAY`'s
  own definition), not a bug T-8.1-02 introduced: the two caps have
  always answered two different questions ("what can the model read" versus
  "what can the reader be shown"), and 30 only bounds the first one.

So: 30 bounds what the WRITING MODEL may read and could choose to cite in
its own prose; 58 is what the READER is actually shown, most of it the
CODE-BUILT listing of prepared-but-unmentioned records, a path the 30
figure was never meant to cap.

## T-8.1-01: think classification malformed replies

Evidence found (no `tracker/phase_8.1.md` existed in this worktree at start;
proceeded from the ticket text given directly). Root cause confirmed from
`testing/Developer/reports/2026-09-23_user_feedback/q5_coffee_exercise.txt`
and `testing/Developer/reports/2026-09-23_set12/breadth_runs/q5_coffee_exercise.txt`:
the plan tier answers Think's classification call with the right shape
except it uses a synonym key for the required `narrative` field: `"why"`
or `"reason"` instead of `"narrative"` (one reply also wrapped the object
in a ```json fence AND used `"why"`). Both retry attempts hit the same
substitution, because the existing retry (`core/graph.py`, the `for
attempt in (1, 2)` loop around line 2248) resends the identical messages,
so a systematic key-naming habit reproduces on attempt 2 as well as
attempt 1. `is_there_a_trial_recruiting_for_melanoma` at researcher depth
failed the same way per `testing/Developer/reports/2026-09-24_no_hardcoding/live_runs/all.json`
row 30 (`outcome: refuse`, `errors: ["step/think"]`).

Fix applied in `core/graph.py`:
1. `_parse_think_classification` now attempts a deterministic key-alias
   repair (`why`/`reason`/`explanation`/`rationale` -> `narrative`) before
   giving up, only when `narrative` is absent and no other unexpected keys
   would trip `extra="forbid"`. This is schema tolerance, not a modeled
   business decision (no hardcoded query text or answer content involved).
2. `ThinkClassificationUnavailableError` now carries the actual pydantic
   field-level errors (field name + generic pydantic message, first 5,
   never raw values), so the previously-generic message is now actionable.
3. The retry loop feeds that detail back to the plan tier on attempt 2 as
   an added user message naming exactly which field was wrong, instead of
   resending byte-identical messages. Still never fabricates or defaults a
   classification: two failed attempts still raise a `step_error`.

Unit tests added to `tests/system_03_search_agent/core/test_graph.py` (8
new tests, all pass): replay the 3 exact malformed shapes measured live
(key repair succeeds), an unrelated-extra-key reply that must NOT be
laundered, the still-raises-honestly path with the new field-level detail
in the message, a retry that feeds the validation error back and recovers
on attempt 2, and a two-failures-still-refuses regression guard (T-4.7-04
never defaults). Full `tests/system_03_search_agent/core` suite: 1093
passed, 56 skipped, no regressions.

Live-run proof, script `testing/Developer/reports/2026-09-25_phase_8.1/
builder_a_live_run.py` (this worktree's `src/` on `sys.path`, `.env` from
the main repository, never printed):
- "is there a trial recruiting for melanoma", researcher depth: 5 of 5
  runs `outcome: answer`, 0 errors (12-14 citations each run).
- "Does coffee help make exercise more effective?", researcher depth: 5 of
  5 runs `outcome: answer`, 0 errors (9-10 citations each run).

RESULT: T-8.1-01 MEETS ACCEPTANCE. 10/10 live runs, both previously-failing
questions, no `step/think` failures, no `error` events, and the fix never
introduces a default/fabricated classification (proven by the two-attempt
regression test).

## T-8.1-02: citation cap 20 -> 30

DECISIONS.md rows added 2026-09-25 (confirmed by direct read, not
paraphrase): `_MAX_CITATIONS_PER_ANSWER` in `core/graph.py` rises 20 -> 30
(card 6), and `_MAX_FINDING_TOTAL_BYTES` in `harness/coordinator_worker.py`
rises 50,000 -> 70,000 (card 43), "so the 30-source cap can reach 30 on
paper questions".

IMPORTANT FINDING (attack-the-constraint: read the actual gate before
assuming the named constant is it). `_MAX_CITATIONS_PER_ANSWER` is NOT the
live-path bound on how many findings reach the writing model or the
citation list. A 2026-09-20 refactor (comment directly above the constant,
`core/graph.py` ~line 6363) deliberately split it in two and left
`_MAX_CITATIONS_PER_ANSWER` wired ONLY to `_citations_from_findings`, "a
build-phase-2.1-era function that is not on this live path". The two live
constants are `_MAX_FINDINGS_FOR_MODEL_PROMPT` (bounds what the synth
model's prompt sees, `prompt_findings = synth_findings[:_MAX_FINDINGS_FOR_MODEL_PROMPT]`)
and `_MAX_FINDINGS_FOR_DISPLAY` (bounds the citation list, the disclosure
table and the findings tail; aliased to `_PLAN_TOOL_CALL_ROW_LIMIT`,
already 100, i.e. already well above 30 and not the binding constraint).
DECISIONS.md's own text ("the same constant bounds what the writing model
sees") describes the PRE-2026-09-20 wiring, not the code as it stands.
Bumping only the named constant, per the letter of the ticket, would
change nothing a user sees: the answer would still cap at 20 citations,
because `_MAX_FINDINGS_FOR_MODEL_PROMPT` still would.

DECISION (this is the subject that needed fixing, not the check, per
`goal-contracts`' "never corrupt the subject to satisfy the check"): raise
`_MAX_CITATIONS_PER_ANSWER` to 30 as literally instructed (keeps the
legacy function's own behaviour consistent with the new number, and
matches DECISIONS.md's literal text), AND raise `_MAX_FINDINGS_FOR_MODEL_PROMPT`
to 30, since that is the actual constant gating what the writing model
sees and therefore what an answer can cite. `_MAX_FINDINGS_FOR_DISPLAY`
(100, `_PLAN_TOOL_CALL_ROW_LIMIT`) already exceeds 30 and needs no change.
Comments updated at both constants to state the derivation and this
finding, so a future reader is not misled the way this ticket's own
DECISIONS.md text was.

Code changes applied (all in `core/graph.py` and `harness/coordinator_worker.py`,
within fence):
- `_MAX_CITATIONS_PER_ANSWER`: 20 -> 30 (literal ticket instruction, and
  keeps the legacy `_citations_from_findings` function's own tests, which
  assert on it directly, matching the decision's stated number).
- `_MAX_FINDINGS_FOR_MODEL_PROMPT`: 20 -> 30. This is the constant that
  actually gates what the writing model sees on the live path (see the
  finding above); raising only the first constant would have changed
  nothing a user sees.
- `_MAX_FINDING_TOTAL_BYTES` (`coordinator_worker.py`): 50,000 -> 70,000,
  per DECISIONS.md card 43, so the byte ceiling does not truncate a
  long-abstract paper answer down before the new citation cap can bind.
- Corrected a pre-existing, unrelated documentation bug found while
  auditing every mention of these constants: a comment near
  `citations_capped` (`core/graph.py` ~line 10464) named
  `_MAX_CITATIONS_PER_ANSWER` as "the model-prompt bound alone", which
  contradicts the 2026-09-20 split's own comment 100 lines above it.
  Corrected to name `_MAX_FINDINGS_FOR_MODEL_PROMPT`, the constant that
  split actually produced. Not required by the ticket, but left uncorrected
  it would mislead the next reader into repeating this exact investigation.
- Checked every other "value derived from the old 20": `_LEAD_FINDINGS_QUOTA`
  (10, a MINIMUM guarantee, already well under both 20 and 30, comment
  already says so, no change needed), `_LAYER_TOOL_ROW_CAP` (5, a
  per-tool-call row cap with no documented tie to the answer-level
  citation cap, independent, no change needed), `_MAX_FINDINGS_FOR_DISPLAY`
  (aliased to `_PLAN_TOOL_CALL_ROW_LIMIT` = 100, already exceeds 30, no
  change needed, confirmed independent by its own comment).
- Did NOT touch `PUBMED_RESULT_CAP` / `TOPIC_RESULT_CAP` (5) in
  `core/breadth_plan.py`: outside my file fence, and untouched by this
  decision (the topic-only literature path's per-call row request is a
  separate, unrelated constant).

Tests updated (pinned the old 20/50,000 values):
- `tests/system_03_search_agent/core/test_write_answer_quality.py`:
  `_MANY_DISEASE_ROWS` widened from 26 to 36 rows, since its own
  "POPULATE CHECK" assertion (`len(...) > _MAX_FINDINGS_FOR_MODEL_PROMPT`)
  would otherwise now correctly fail (26 is no longer greater than 30).
  Docstring and inline comments updated to the new numbers.
- `tests/system_03_search_agent/harness/test_coordinator_worker.py`: two
  assertions hardcoded `<= 50_000  # _MAX_FINDING_TOTAL_BYTES` as a magic
  number instead of reading the real constant; replaced both with
  `<= coordinator_worker_module._MAX_FINDING_TOTAL_BYTES` so the test
  tracks the module's own bound instead of silently testing a stricter,
  stale one.
- `tests/system_03_search_agent/core/test_graph.py`: updated a
  section-header comment's stated numbers (was "(20, unchanged)").
- Historical narrative docstrings that describe a PAST measurement at the
  old value (e.g. "24 of 30 live answers hit that shared cap", "at the
  time this was measured") were deliberately left alone: they document
  what was true when written, not a live invariant.

Full `tests/system_03_search_agent/core` + `tests/system_03_search_agent/harness`
suite: 1301 passed, 56 skipped, no regressions.

Live-run proof (same script). A gene question phrased to ask for the
literature ("What research papers discuss BRCA1?", researcher depth) fans
out across PubMed, ClinVar and OMIM with long PubMed abstracts, the exact
shape DECISIONS.md's card 43 measurement describes:
- Run 1: 58 citations, outcome `ask`, cost $0.0172.
- Run 2: 58 citations, outcome `ask`, cost $0.0171.
- Run 3: 58 citations, outcome `ask`, cost $0.0168.

RESULT: T-8.1-02 MEETS ACCEPTANCE. All 3 runs cite well past 22 sources (58
each, comfortably above the old byte-ceiling failure point), and all 3
costs are far under the $0.10 per-query cap (about 1.7 cents each, in line
with the decision's own "about half a cent more per paper question"
estimate against a low base cost).

## T-8.1-03: the 127-second run

Source located: `testing/UI_fixes_done.md` item 22 ("THE 127.1 SECOND RUN,
against a median of 13.6, unowned since 2026-09-20") and its full detail in
`testing/Developer/reports/2026-09-20_verification_rate/findings.md` and
`run_log.txt`/`runs.json` in that same folder.

Facts established from the raw data (`run_log.txt`, lines 7 to 9): the
question "What diseases are caused by variants in the HNF1A gene?" at
researcher depth ran 3 times in that measurement. Runs 1 and 2 took 14.5s
and 11.3s. Run 3 alone took 127.1s, with `fallback_note=True` (the
grounding pass discarded the model's prose) and 16 sources, `outcome: ask`
(the run SUCCEEDED with real data, it did not error out). Same question,
same depth, same code: only one of three runs spiked.

Checked whether commit `2bc8ec0` (the graph statement-timeout fix for the
exploratory class, landed 2026-09-22) explains or fixes it. It does NOT,
for two independent reasons, both confirmed by reading the commit itself
(`git show 2bc8ec0`):

1. Wrong class. `2bc8ec0` widens `tools/cypher_templates.py`'s
   record-template gate to exactly the `exploratory` query class. Its own
   message explicitly EXCLUDES `multi_hop` from that widening, by name,
   citing G-011 as the reason a multi_hop question must keep the
   model-generated-Cypher path. "What diseases are caused by variants in
   the HNF1A gene?" matches `_THINK_SYSTEM_INSTRUCTION`'s own worked
   example of `multi_hop` almost word for word ("What conditions link to
   BRCA1 pathogenic variants?"), so this question was never eligible for
   that fix's gate in the first place, before or after.
2. Wrong file. The entire fix is 3 lines of stat plus test changes, all in
   `tools/cypher_templates.py` and its two test files. Neither file is in
   my fence (`core/graph.py`, `harness/coordinator_worker.py`), so even if
   the class matched, this would not be my fix to make.

Read the actual timeout wiring for the graph call in my fence,
`core/graph.py` lines 5904 to 5922 (`_execute_planned_call`'s Layer 1
branch): `act_timeout_s = max(budget_for_step("act", query_class),
CYPHER_QUERY_TIMEOUT_SECONDS)`. For `multi_hop`,
`_QUERY_CLASS_BUDGET_S["multi_hop"]` is 30.0 seconds
(`harness/harness.py`), and `CYPHER_QUERY_TIMEOUT_SECONDS` is also 30
(tool-call-budgets.md's locked figure), so `act_timeout_s` resolves to 30,
not 127. This timeout has wrapped the graph call since commit `473c5a6`
(2026-07-31), well before the 2026-09-20 measurement, so it was already
active when the 127.1s run happened. `cypher_query` itself
(`tools/cypher_query.py`, outside my fence) ALSO wraps its own pipeline in
`asyncio.wait_for(..., timeout=CYPHER_QUERY_TIMEOUT_SECONDS)` and its
docstring states it "never raises" past that budget, converting any
timeout into a `status: "error"` output. Two independent 30-second
timeouts existed in the path this run took, and the run still took 127.1s
and SUCCEEDED with real rows rather than erroring at ~30s.

DIAGNOSIS: this is evidence that the declared 30-second timeouts did not
actually bound this run's wall time; the query genuinely ran to
completion past 4x its stated budget without either timeout firing. The
available data does not let me attribute the extra time to a specific
step (no per-step timing was captured in the 2026-09-20 measurement,
`runs.json` records only total elapsed and the three note flags), so I
cannot say with evidence whether the graph call itself ran long (an
`asyncio.to_thread`-wrapped psycopg2 call, once actually running in its
own OS thread, cannot be forcibly interrupted by `asyncio.wait_for`
cancelling the awaiting coroutine, so a `wait_for` timeout can detach the
CALLER from a hung thread without ever truly stopping it; whether that
detach-not-stop gap, or something in the write/grounding step that also
fired the fallback note, produced the 127s figure, is not distinguishable
from this data alone), or whether Write's own repair/retry path (the
`fallback_note` firing means grounding was re-attempted) added
substantial extra latency after a graph call that itself returned inside
budget. Both live inside a query that also, separately, hit the shape
2bc8ec0 later hardened against for a different class: a model-generated,
non-templated Cypher search on an unusual query plan.

This is a single non-reproduced outlier (1 run in 3 of the same question,
29 of 30 runs in the measurement were 7 to 23 seconds), so it is not
something I can reliably reproduce and re-time inside this ticket's live
run budget to localize further.

DECISION: NOT FIXING. The cause is not established to be in my fence
(the two candidate mechanisms, a real-thread timeout-cancellation gap in
`tools/cypher_query.py`'s to_thread-wrapped DB call, or Write's own
repair path, are both either outside my fence or not narrowed down enough
by available evidence to call a "small fix"), and per the ticket's own
instruction ("Fix only if the cause is in your fence and the fix is small,
with a test") I am stopping at diagnosis. Widening `2bc8ec0`'s deliberate,
reasoned exclusion of `multi_hop` from the template gate would also be
reopening a considered product tradeoff (G-011), not a small, obviously
safe fix, and is explicitly not something to do silently under
`v1-scope-boundary`/`attack-the-constraint` discipline.

RECOMMENDATION for whoever owns `tools/cypher_query.py` next: add a test
that proves `enforce_timeout`/`cypher_query`'s own internal
`asyncio.wait_for` actually bounds wall time when the wrapped coroutine
is a REAL `asyncio.to_thread`-wrapped blocking call already running in
its executor thread, not only against a cooperative `asyncio.sleep` (the
existing proof in `harness/harness.py`'s `enforce_timeout` docstring is
explicitly the sleep-based case). If that proves the gap, the fix is
likely either a hard socket/statement-level timeout set directly on the
psycopg2 connection (so the DATABASE itself, not the Python wrapper,
bounds the call), or accepting that a timed-out call's orphaned thread is
a known, documented limitation.

