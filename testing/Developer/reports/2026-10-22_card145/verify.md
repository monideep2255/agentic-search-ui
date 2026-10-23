# Card 145 fresh verification

Verifier for pull request 293, branch `fix/card145-second-reading-before-ask-back` at 1c48885c, after fix round c21ae14e and the schema commit. Read and run only. Findings are appended as they are established.

## Findings

### V-145-01: A-145-03 is still open, and on that model reply the branch is worse than develop
- Severity: major (conditional on the plan model tagging a word of the question as a disease on the second reading; not measured live)
- What: the word-for-word check (`_second_reading_usable`, `core/graph.py` near :6806) passes any span the question contains, so an ordinary word of a dangling first message that MedGen title-matches still binds. Develop asks these questions back on the same first reply.
- Reproduction: the adversary's probe rerun on 1c48885c (`adv/test_adv145.py::test_own_word_binds`, hermetic, MedGen stubbed to the adversary's live results). `Is it dangerous?`, first reply `{"entities": []}`, second tags `dangerous` as disease: `calls= 2`, `clarifying = None`, eight entities `('dangerous', 'MedGen:C0563039')` and on, narrative `stand-in (dangerous: 8 of 13 MedGen records matched by name)`, token `Found 1 gene record for dangerous: ...`, `trust_outcome = ask`. `What variants cause it?` with `variants`: the same shape, `variants: 8 of at least 20 MedGen records matched by name`. On develop the same first reply asks back (`test_a_follow_up_with_nothing_to_point_at_asks_which`).
- Why it matters: the person whose first message is "Is it dangerous?" can get records about "Unsafe storage of dangerous substances" instead of the ask-back, and that subject then goes to session memory (A-145-06's write path is unchanged for a span written in the question). The owner left this open knowingly; it is filed so the "worse than develop" line is explicit.
- Not a regression of the fix round: the binder and the second draw predate c21ae14e; the fix round narrowed it.
- NOT FIXED

- Addendum to V-145-01, live NCBI, read only (about 5 calls): `resolve_disease_mention_to_curies("cause")` returned 8 CURIEs of 20 matched (`MedGen:C0156247` ...), so "What variants cause it?" carries a second own-word span that binds besides `variants`. `resolve_disease_mention_to_curies("it")` returned `([], 0)` and `resolve_symbol_to_curie("IT", taxon="human")` returned `None`, so the pronoun itself, which `_written_in_question("it", "What is it?")` passes (`True`), binds nothing today.

### V-145-02: A second reading that names only an organism is recorded as "resolved" on a run that then asks the person back
- Regression of: A-145-02 (the fix round's decision record, c21ae14e and 1c48885c)
- Severity: minor
- What: `_second_reading_usable` (`core/graph.py` near :6806) accepts a reading with no CURIE when it has an organism span, and the caller then appends `_second_reading_record` (`core/graph.py` near :6826, call site near :4446) unconditionally. On a question whose record type is not SRA or assembly, the organism anchor does not run, nothing resolves, and Think asks the organism wording back. The done event still says the reading resolved the question.
- Reproduction: verifier probe `test_zz_fix.py::test_v_organism_only_record2` (scratch copy of 1c48885c, the card's `think_readings` stubs). Question `Where is Mycobacterium tuberculosis found and how does it spread?`, first reply `{"entities": []}`, second names `Mycobacterium tuberculosis` as organism, `record_type` "none". Output: `calls 2`, `clarifying 'One more detail is needed: which kind of record about Mycobacterium tu...'`, `resolved_entities []`, `trust_outcome refuse`, and `decisions` carries `{'name': 'think.second_reading', 'options': ['resolved', 'asked_back'], 'chosen': 'resolved: Mycobacterium tuberculosis', 'decided_by': 'plan', ...}`.
- Why it matters: the record the owner asked for ("the answer's record says it was used") states "resolved" on a run that resolved nothing and refused, so an operator reading traces is misled on exactly this path; `chosen` is also not one of the record's own `options`. For the person typing the question it is not worse than develop: develop asks "which gene, variant or condition do you mean?", the branch asks which kind of record about the organism they named. No test covers an organism-only second reading on a non-organism record type.
- NOT FIXED

- Addendum to V-145-02: mutation `if not resolution.curies and not reading.organism_spans:` to `if not resolution.curies:` (`core/graph.py:6818`, scratch copy of 1c48885c) leaves `test_clarification.py` at `38 passed in 4.84s`. The organism-only acceptance path is untested in both directions.

### V-145-03: An `s3` command line installed from develop or earlier fails every run whose done event carries the "plan" record, contrary to "old ... clients read as before"
- Regression of: A-145-02 (the record added by the fix round, made valid by the schema commit 1c48885c)
- Severity: major (for command-line users on an older install; the web app does not read `decided_by`)
- What: `DecisionRecord.decided_by` widened from `Literal["jev", "guard"]` to add `"plan"` (`contracts/events.py:121`). A new value in a known field is exactly the case the client's lenient decode says it does not cover (`adapters/cli/client.py:589` to `:592`, "A new enum VALUE in a known field is not covered"). Develop's strict `Event` model rejects the frame, `_decode_ignoring_unknown_fields` returns None because no key was dropped, and `_decode_stream_event` synthesizes a fatal error.
- Reproduction: I dumped the `done` and `think` frames of the recovered croup run from a scratch copy of 1c48885c (`test_zz_fix.py::test_v_dump_done`) and fed them to develop's client code (`git archive origin/develop`, b902d80a):
  - Develop `Event.model_validate_json(done)`: `strict FAIL ... payload does not match the 'done' event schema ... decisions.5.decided_by`; `_decode_ignoring_unknown_fields` -> `None`; `_payload_declares_unknown_type` -> `False`.
  - Develop `CliClient._decode_stream_event(("done", line, "42"), is_trailing=False)` -> `error {'fatal': True, 'scope': 'run', 'source': 'cli_stream_decode', 'error_class': 'transient', 'message': "the server sent a 'done' event that this client could not decode; the run cannot be trusted to have completed as reported." ...} terminal True`.
  - The branch's own client decodes the same frame: `done {... 'trust_outcome': 'answer' ...}`. The `think` frame decodes on both.
- Which questions produce the record: one producer only, `_second_reading_record` at `core/graph.py:4445` (grep for `decided_by="plan"` in `src` finds only `:6846`). It fires whenever `_read_question_again` returns a usable reading, that is a first question with no session memory, a referring word, nothing resolved on the first reading, and a second reading whose subjects are all written in the question. That includes the recovered answers (bronchiolitis, croup) and also the organism-only readings that end asked back (V-145-02), so an older `s3` fails on some ask-back runs too. Measured base rate from the builder's diagnosis: the plan model returned no entity on 3 of 10 readings of the bronchiolitis question; I did not measure how often the trigger fires across real traffic.
- Why it matters: on develop such a question is a clean run (it is asked back); with this branch an older `s3` prints a fatal "could not decode" error and a nonzero exit instead of the answer. The owner's decision text premised the schema change on "old answers and clients read as before"; for clients that premise is false. Saved answers are not re-validated on read (`feedback/history.py` has no `DonePayload` validation), so the "old answers" half holds as far as I read.
- NOT FIXED

### V-145-04: after.md still states the second reading's bound as Think's 45 s budget
- Severity: minor (documentation)
- What: `testing/Developer/reports/2026-10-22_card145/after.md:115`, under "What this does not settle", reads "The second reading is bounded by what is left of Think's own step budget (45 s from Think's start) ... but the bound itself is wider than the 20-second answer rule". The fix round's own table in the same file (`:39`) says min(4 s, what is left of Think's deadline).
- Reproduction: `sed -n 110,120p after.md` in the worktree prints the line above; my probe `test_v_wall_clock_slow_second` (second Think reply sleeping 30 s, real budget) printed `elapsed=4.06s calls=2`, asked back.
- Why it matters: a reader of the evidence file gets two contradictory bounds; the stale one is the defect the fix round closed.
- NOT FIXED

### V-145-05: A second reading cut at 4 s is charged at its pre-flight estimate, about 50 times a completed reading
- Severity: unsure (likely the harness's intended fail-safe for a cancelled call; the new path is that a 4 s cut now happens on ask-back questions)
- What: when `asyncio.wait_for` in `_read_question_again` (`core/graph.py` near :6915) cancels the in-flight plan-tier call, the done event's cost carries a charge far above a completed call's.
- Reproduction: verifier probe `test_zz_fix.py::test_v_cost_on_cancel`, croup question, both replies `{"entities": []}`. Completed second reading: `calls 2 done_total 0.00015999999999999999`. Second reply sleeping 30 s, cut at the real 4 s: `calls 2 done_total 0.00814`. Both end asked back.
- Why it matters: the person's answer, an ask-back, reports a cost about 50 times what the provider was likely billed, and the per-question and daily caps count it. The amount is small against the 25-cent cap. I did not check whether develop's own Think timeout path charges the same way; if it does, this is not new behaviour, only a new place it fires.
- NOT FIXED

## Closed findings, re-derived

Probes ran in scratch copies made with `git archive` of 1c48885c and of origin/develop (b902d80a, the branch's merge base), never in the worktree. The branch copy's `graph.py` and `test_clarification.py` were confirmed byte-identical to the worktree with `diff -q`.

| Finding | Verdict | Evidence, my own probe unless marked read |
|---|---|---|
| J-145-01 | Closed | Second Think reply sleeping 30 s, real budget: `elapsed=4.06s calls=2`, asked back. Second confirmation sleeping 30 s: `elapsed=4.02s`, asked back. Mutation `budget = step_deadline - time.monotonic()` turns `test_a_very_long_think_deadline_still_caps_the_second_reading` red |
| J-145-03 | Closed | Each of the nine trigger conditions (`core/graph.py:4417` to `:4425`) replaced by `True` one at a time: each turns its own `test_trigger_*` red (memory, window, accession, isolate, organism, exact ID, resolved with two tests, rejected symbol, referring word) |
| J-145-04 | Closed | Mutation narrowing `except Exception` at `:6926` to `ZeroDivisionError` turns `test_an_ncbi_error_in_the_second_confirmation_asks_back` red with `RuntimeError: stand-in NCBI failure`; a raising provider on the second call: `calls 2`, asked back, no error event |
| J-145-05 | Closed | Second call raising `RuntimeError`: only INFO lines `second reading's call failed (unexpected, ...)` and `second reading ended early (step_error); asking back`, no "step failed". Mutation `second_reading=False` at `:6903` turns `test_a_failed_second_reading_is_not_logged_as_a_failed_step` red with the `step failed ... step=think` line |
| J-145-06 | Closed | Mutation `step_deadline,` to `time.monotonic() + 3600,` at `:4431` turns `test_the_caller_hands_the_second_reading_think_own_deadline` red |
| A-145-01 | Closed | Adversary probe rerun: all eight `test_dangling_second_reading_invents` cases now `calls= 2`, the `CLARIFICATION_QUESTION`, `entities = []`, `trust_outcome = refuse` (was `answer` with cystic fibrosis or CFTR bound) |
| A-145-02 | Closed, with V-145-02 and V-145-03 | Recovered croup run: `done.decisions` carries `think.second_reading`, `chosen 'resolved: croup'`, `decided_by 'plan'`, and the done payload validates as `DonePayload`. Mutation dropping the append at `:4445` turns `test_a_used_second_reading_is_recorded_in_the_done_decisions` red |
| A-145-04 | Closed | Adversary SRA probe rerun: second reading `SARS` as disease, and `SARS-CoV-2` plus `SARS`, both now asked back with `entities = []` (were three SARS disease records) |
| A-145-05 | Closed | Adversary probe rerun, organism second reading: wording is now `which kind of record about SARS-CoV-2 do you want?` instead of "which gene"; the card's test with Taxonomy stubbed resolves `NCBITaxon:2697049`. My probe with `record_type` sra on Mycobacterium tuberculosis resolved `NCBITaxon:1773` |
| A-145-06 | Closed for invented subjects; open through V-145-01 | Invented spans are now asked back, so the plan event and citations stay empty (card test, and it goes red under the break-it mutation). A span written in the question that binds still reaches the plan event and so memory (read, `core/run.py`) |

## Left open, against develop

| Finding | Worse than develop? | Evidence |
|---|---|---|
| A-145-03 | Yes, conditional on the model tagging an ordinary word as a disease on the second reading | V-145-01 |
| J-145-02 | No | Memory present with no resolved entity, croup question, first reading empty: `calls 1`, asked back, as on develop. The memory condition is now pinned (mutation turns `test_trigger_memory_a_session_with_memory_makes_one_call` red) |
| J-145-07 | Unmeasured, not shown worse | after.md's fix-round runs: 3 of 3 full bronchiolitis runs resolved on the first reading, so the recovered path through Write was never run live (read). Stubbed: the recovered croup run ends `trust_outcome answer` with a citation |
| J-145-08 | No, in the person's terms | A triggered question with two gene-shaped tokens repeats the first reading's lookups on the second: develop `genes [ABCX1, XYZ2]`, `medgen [ABCX1, XYZ2]`; branch each twice. Both live resolvers cache clean answers (`_SYMBOL_CURIE_CACHE`, `_DISEASE_CURIE_CACHE`, read), so repeats are free unless NCBI is failing. Extra calls only matter on a recovered question, which develop asked back |
| J-145-09 | Yes, only through A-145-03 | Invented subjects are blocked (A-145-01 closed); a second draw of an own-word disease tag still binds (V-145-01) |

## Rule 4: the moved `_resolve_reading`

- Same 19 stubbed classifications run through develop's and the branch's full graph (`test_zz_identity.py`: gene, rejected symbol, typed ID, disease with and without a referring word, MODY disease fallback, GCK gene fallback, organism anchor, SRA with no entity, assembly, mouse Tp53, dangling with and without an invented span, rsID accession, own-word disease, bronchiolitis empty, topic, memory, organism with no record type).
- After dropping fields that differ between two develop runs (persona text, citation and marker IDs, which I confirmed by running develop twice: 19 of 19 identical), 17 of 19 were identical in the think, plan, token, tool_start, trust_signal and done payloads and in every NCBI lookup made (symbols with taxa, MedGen mentions, Taxonomy names).
- The two that differ are the two that reach the second reading (`dangling_empty`, `bronch_empty`): identical events, Think calls 1 on develop and 2 on the branch.
- So the first reading is behaviour-identical to develop on every question I tried that never reaches the second reading. No regression found there.

## Break it

- Mutation `return all(_written_in_question(span, query_text) for span in spans)` to `return True` (`core/graph.py:6822`), in the byte-identical scratch copy of 1c48885c, not the worktree: `test_clarification.py` gave `7 failed, 31 passed in 6.28s`. Red: the four `test_a_subject_the_question_never_names_is_asked_back` cases (A-145-01), `test_an_invented_subject_never_reaches_session_memory` (A-145-06), and the two `test_the_sra_question_never_binds_the_disease_cut_from_the_virus_name` cases (A-145-04).
- Mutation ignoring the joiner check in `_written_in_question` (`:6801`, `if True:`): 3 red, the two SRA cases and `test_written_in_question_reads_whole_phrases_only`.
- Restored after every mutation (`restored True`, the copy compared to its saved original). Worktree after all probes: `git diff HEAD | wc -l` printed `0`; `git status --short` shows only `?? frontend/node_modules`. No `git stash` was used.

## Runs

- Gate 2, `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: `Skipped 2 files`, exit 0.
- Gate 3, `venv/bin/ruff check .`: `All checks passed!`, exit 0.
- `tests/system_03_search_agent/core/test_clarification.py`: `38 passed in 4.95s`.
- `tests/system_03_search_agent/contracts`: `221 passed in 0.29s`.
- The 29 test files referencing `_think` or `think_node`: `1000 passed, 84 skipped, 2 warnings in 36.14s`.
- `tests/system_03_search_agent/adapters/cli`: `455 passed in 25.56s`.
- Whole unit suite, `pytest tests`: `8518 passed, 166 skipped, 1 xfailed, 7 warnings in 709.63s`.
- Live NCBI, read only: about 5 calls (`it`, `cause` as diseases; `IT` as a human gene). No live model call.

## Verdict

- HOLD. Not PASS, because two things are worse than develop:
  - V-145-03 (major, Regression of A-145-02, inside the schema commit): an `s3` installed from develop fails with a fatal decode error on every run that records a second reading, where develop gave a clean ask-back. This contradicts the decision's premise that "old ... clients read as before". The builder reported it, and I confirmed it.
  - V-145-01 (major, conditional): A-145-03 stays open. When the second reading tags a word the question contains, it binds that word's MedGen records, where develop asks back. "cause" binds 8 records live, and so do "dangerous" and "variants".
- Minor, inside the fix round's code: V-145-02 (Regression of A-145-02). An organism-only second reading is recorded "resolved" on a run that asks back, and that path is untested. Also minor: V-145-04, a stale bound in after.md. Unsure: V-145-05, a cut reading is charged at its pre-flight estimate.
- Rule 4: V-145-02 and V-145-03 sit inside this phase's fixes, so they fire the stop condition. The first reading's moved code is clean: 17 of 19 stubbed classifications match develop's output exactly, and the other two differ only in Think call count.
- Verified with my own probes: every closed finding in the tables above; the identity comparison; the 4 s wall clock; the cancel path; the decision record and its validation; the old-client decode; memory without entities; the repeated lookups; the cost on a cut reading; every mutation; and the gates and suites.
- Read only, not probed: the session-memory write in `core/run.py` for an own-word binding; resolver caching; saved answers not being re-validated on read; J-145-07, which is after.md's live evidence; and whether the live plan model ever produces the V-145-01 spans.
