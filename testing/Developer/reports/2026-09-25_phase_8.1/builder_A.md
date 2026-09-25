# Builder A report, phase 8.1

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

