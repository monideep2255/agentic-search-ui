# Card 145 judge round

Judge, one round, on branch fix/card145-second-reading-before-ask-back (commit 4f128c66) in the card145 worktree. Read and run only.

## Findings

### J-145-01: The second reading may run up to Think's 45 s budget, so a question asked back today can now take 25 s or more
- Severity: major
- What: `_read_question_again` bounds itself by `step_deadline` (`core/graph.py:6724`, `asyncio.wait_for(_read(), timeout=remaining)` at `:6738`). That deadline is `time.monotonic() + budget_for_step("think")` (`core/graph.py:1430`, set in `think_node` at `:4176`). Think's budget is the plan tier's, `"plan": 45.0` (`harness/harness.py:529`). Nothing bounds the second reading to the owner's 20 s rule. Inside `_read`, `_run_think_classification` makes up to two calls, each with `budget_s=budget_for_step("think", "lookup")` = 45 s (`core/graph.py:4075`), so `remaining` is the only bound.
- Reproduction: judge probe (scratchpad `probes/test_j145_probe.py::test_probe_slow_second_reading_wall_clock`, reusing `test_clarification.py`'s autouse stubs). The first Think reply is `{"entities": []}` at once; the second sleeps 25 s, then names croup. Output: `PROBE slow: calls=2 elapsed=25.8s clarifying=None entities=['MedGen:C0010380']`. Before the change this question asked back in under 1 s on the same stubs.
- Why it matters: this is the failure card 56 slice 1 was closed for, "fired on ordinary questions, one taking 46 s" (DECISIONS.md 2026-10-17). The trigger is narrower here, so ordinary questions do not pay. But on the ask-back path the person can now wait up to about 45 s minus the first reading, plus the guardrail, against "every answer within 20 s". The builder states this in after.md ("the bound itself is wider than the 20-second answer rule"). The live sample showed a 7.9 s Think. That is one tail sample, not a bound. No test pins a bound.
- NOT FIXED

### J-145-02: The memory condition is untested, and it makes the trigger narrower than the set of CLARIFICATION_QUESTION ask-backs
- Severity: minor (unsure whether the narrowing is intended)
- What: the trigger needs `_session_memory(state) is None` (`core/graph.py:4572`). The ask-back itself reads only `_antecedent_curie(_memory_curies(state))` (`core/graph.py:6677`). So a session whose memory exists but holds no resolved entity still gets `CLARIFICATION_QUESTION` from one reading. `remember_turn_for_caller` writes memory when a turn has findings but no entities (`core/session_memory.py:996`, `if not resolved and not findings: return None`), so a topic or literature answer followed by a referring question is such a session.
- Reproduction, narrowing: probe `test_probe_memory_without_entities`, memory `SessionMemorySummary(resolved_entities=[])`, the croup question, first reading empty, second would resolve. Output: `PROBE memory-empty: calls=1 asked_back=True`.
- Reproduction, break it: I replaced `_session_memory(state) is None` at `:4572` with `True` and ran `test_clarification.py`. Output: `14 passed in 6.78s`. No test went red. `test_a_remembered_subject_makes_exactly_one_think_call` uses a BRCA1 memory, and `_needs_clarification` already returns False for that memory, so that test cannot see this condition. I restored the file; `git diff HEAD | wc -l` printed `0`.
- Why it matters: the owner said "a first question", so the narrowing may be correct. But the code comment says the trigger is "the exact set of conditions under which the ask-back below fires" (`:4563`), and it is not. The brief's mutation, drop the memory condition, survives the whole suite.
- NOT FIXED

### J-145-03: Seven of the trigger's nine conditions can each be removed with the card's own tests green; four with the whole Think suite green
- Severity: major (test gap on the acceptance clause "no question that answers today pays for it")
- What: the trigger is correct as built. Every shape I probed made one Think call. But only `_needs_clarification` (`core/graph.py:4581`) and `accession_plan is None` (`:4574`) are pinned by any test, and both only by older tests outside this card that count model calls. Nothing pins `not exact_matches` (`:4577`), `not model_resolution.unresolved_symbols` (`:4580`), `not organism_spans` (`:4576`), `window is None` (`:4573`) or `isolate_question is None` (`:4575`). Each one is load-bearing.
- Reproduction, branch as built, judge probe `test_probe_calls_for_answering_shapes`:
  - exact ID: `What is NCBIGene:672 and why is it studied?` gave `calls=1 ... entities=['NCBIGene:672']`.
  - rejected symbol: `What does BRCA9 do and why is it studied?` gave `calls=1`.
  - organism: `Which genome assemblies of Mycobacterium tuberculosis exist and where is it found?` gave `calls=1 clarifying='One more detail is needed: which kind of record about Mycoba'`.
- Reproduction, each condition replaced by `and True`, one at a time:
  - `not exact_matches`: the exact-ID question gave `calls=2`.
  - `not model_resolution.unresolved_symbols`: the BRCA9 question gave `calls=2`.
  - `not organism_spans`: the organism question gave `calls=2`.
  - `test_clarification.py` printed `14 passed` under every one of the eight mutations, `_needs_clarification` included.
  - The 27 Think-related test files printed `976 passed, 84 skipped` under the `organism_spans`, `exact_matches`, `unresolved_symbols`, `window` and `isolate_question` mutations.
  - The `_needs_clarification` mutation gave `8 failed, 968 passed` (test_graph, test_think_retry call counts). The `accession_plan` mutation gave `1 failed` (`test_card30_two_late_decisions_share_one_grace`).
  - I restored the file after each; `git diff HEAD | wc -l` printed `0`.
- Why it matters: a later edit to this condition can make exact-ID, rejected-symbol, organism, window or isolate questions pay a second plan-tier call and up to its 45 s (J-145-01) with nothing going red. That is card 56 slice 1's failure again. The card's one "answers today" test (`test_a_question_that_resolves_makes_exactly_one_think_call`) covers only a gene that resolves, which `not model_resolution.confirmed` alone already guards.
- NOT FIXED

- Count correction to J-145-03, same round: the trigger has ten conditions, from `:4572` to `:4581`. Removed one at a time, all ten leave `test_clarification.py` green: the memory one (J-145-02), the eight above, and `not model_resolution.confirmed` (`14 passed in 4.11s`). Only removing `curies` and `confirmed` together turns the card's tests red: `2 failed, 12 passed` (`test_a_question_that_resolves_makes_exactly_one_think_call`, `test_a_plain_english_subject_that_resolves_first_time_makes_one_call`). Restored, `git diff HEAD | wc -l` printed `0`.

### J-145-04: Fail-closed holds for model-call errors but not for an error in the second confirmation, which turns an ask-back into a failed query
- Severity: minor
- What: the docstring promises "a cost-cap hit or step error on the second call ... fails closed" (`core/graph.py:6713` to `6715`). For the model call it holds. `_run_think_classification` turns `QueryCapExceededError` and `HarnessCallError` into dicts (`:4087` to `:4090`), and `_read` maps a dict to None (`:6728`). But `_confirm_extracted_entities` (`:6730`) is outside any handler, and only `TimeoutError` is caught (`:6739`).
- Reproduction, judge probes on the croup question, first reading empty:
  - Second model call raising ValueError, RuntimeError or KeyError: each gave `calls=2 asked_back=True error=None types=['guard', 'cost', 'think', 'cost', 'plan', 'token', 'trust_signal', 'done']`, so fail-closed holds there.
  - `_confirm_extracted_entities` raising RuntimeError on its second call only: `PROBE confirm-raise: run RAISED RuntimeError`. The question that asks back today ended with an exception instead.
- Why it matters: the resolvers it calls are documented "never raises" (`resolve_disease_mention_to_curies` catches `Exception`, `:3391` and `:3408`), so the exposure is narrow. The same raise on the first reading already fails the run. Still, the docstring states a guarantee the code gives only for the model half, and this path is new.
- NOT FIXED

### J-145-05: A second reading that fails its schema twice logs "step failed ... step=think" on a run that goes on and asks back
- Severity: minor
- What: on a double schema failure `_run_think_classification` calls `_log_step_failed("think", "recoverable", parse_error)` (`core/graph.py:4143`). On `HarnessCallError`, `_step_error_kwargs` calls it too (`:959`). Both were written for paths that end the run. On the second reading the run continues to the ask-back, but the log line says Think failed.
- Reproduction: read only. The probe above (second call raising) reached `_step_error_kwargs` and returned a normal ask-back with `error=None`, so the warning was logged for a step that did not fail. I did not capture the log line itself.
- Why it matters: an operator who counts "step failed step=think" lines to judge Think's health gets false failures on ask-back runs. Cosmetic for the person typing the question.
- NOT FIXED

- Evidence added to J-145-05, same round. Probe `test_probe_step_failed_log`: the first reply was `{"entities": []}`, then two unparseable replies. Output: `calls=3 asked_back=True error=None lines=['step failed trace_id=none step=think error_class=recoverable cause_class=ThinkClassificationUnavailableError']`. The run asked back normally and still logged that Think failed.

### J-145-06: Nothing tests that the caller hands Think's own deadline to the second reading; an hour-long deadline passes the suite
- Severity: minor
- What: `test_the_second_reading_fails_closed_past_think_budget` calls `_read_question_again` directly with a deadline it builds itself, and `_run_think_classification` mocked out. The argument at the call site, `step_deadline` at `core/graph.py:4584`, is not covered.
- Reproduction: I replaced `step_deadline` at `:4584` with `time.monotonic() + 3600` and ran `test_clarification.py`. Output: `14 passed in 3.64s`. I restored the file; `git diff HEAD | wc -l` printed `0`.
- Why it matters: the card's only timing promise, "it can never stretch Think past its budget", rests on one argument that no test pins. With J-145-01 open, that budget is already 45 s.
- NOT FIXED

### J-145-07: The recovered path, where the second reading resolves and the question is then searched and answered, was never run end to end live
- Severity: minor (evidence gap, not a code defect)
- What: after.md's full runs (`testing/Developer/reports/2026-10-22_card145/after.md`, "Full runs of the bronchiolitis question") have no run in which the second reading fired and resolved. Run 4 fired and found nothing; the other four never fired. The one recovery, batch b run 7, was Think alone (`think_probe.py`), which stops before Plan, Act and Write.
- Reproduction: after.md table rows 1 to 5: "Second reading" reads `no`, `no`, `no`, `yes, found nothing`, `no`. The summary row reads "recovered 1", and the "Think alone" table puts that one in batch b, run 7.
- Why it matters: what the person sees after a recovered reading, a cited answer about the condition within 20 s, is shown only by stubbed unit tests (`test_an_unread_first_question_is_read_again_and_answered` checks Think's payload and that the token is not the ask-back). The timing to done on that path, the second confirmation's share of the Layer 2 call ceiling (J-145-08) and the trust outcome are all unmeasured.
- NOT FIXED

### J-145-08: The second confirmation's NCBI calls are charged to the question's 20-call Layer 2 ceiling, which Act then needs
- Severity: unsure
- What: `_confirm_extracted_entities` reaches NCBI through the transport. The transport charges every attempt, retries included, with `call_budget.charge_one_call` (`tools/ncbi_transport.py:1605`). That is the per-question ceiling Act needs for its own calls. On the trigger path the first reading may already have spent up to 6 MedGen calls: up to 3 unconfirmed disease spans (`_MAX_LIVE_DISEASE_LOOKUPS = 3`, `core/graph.py:3257`) and the disease fallback's up to 3 candidates, each an ESearch plus an ESummary. The second reading can then spend gene lookups (3 symbols, two legs, one retry each), up to 6 MedGen calls, and the gene-as-disease retry.
- Reproduction: read only. I did not build a probe that counts the call budget on this path. The comment at `core/graph.py:4384` to `4393` records the same ceiling refusing a window question's records "and the answer carried no citations".
- Why it matters: when a recovered question spends its ceiling in Think, Act's own calls can be refused and the answer comes back with fewer or no citations. For the bronchiolitis case it is probably 2 calls, cached after the first success, so the risk is likely small. Filed because it is unmeasured (see J-145-07).
- NOT FIXED

### J-145-09: Two readings double the chance that a genuinely dangling first message binds a subject it never named
- Severity: unsure
- What: for "What variants cause it?" with no memory, the right answer is the ask-back (`test_a_follow_up_with_nothing_to_point_at_asks_which`). Each reading samples the plan-tier model with no temperature set (diagnosis.md, "The Think call sends no `temperature`"). Any span the model invents and MedGen or Gene confirms now has two chances to bind instead of one. Examples: "variants" tagged disease, matched by `variants[title]`. Both readings use the same confirmation, so this is the same bound as the first reading, applied twice.
- Reproduction: not reproduced, since live model calls were out of scope. `test_the_dangling_first_message_is_still_asked_back_after_two_readings` uses the file's stub, which never names a span, so it cannot show this.
- Why it matters: "a confident wrong record is worse than a missing one". The owner's decision accepts a second reading. Whether it doubles a wrong-binding rate on dangling questions has not been measured. A small live sample of "What variants cause it?" would settle it.
- NOT FIXED

## Checks that passed, with evidence

- Trigger as built is inside the set of CLARIFICATION_QUESTION ask-backs. By reading `core/graph.py:4571` to `4581` against `:4676` to `:4710`: with every condition true, `resolved_entities` is empty, `has_accession_subject` is False, and no organism, window, isolate or accession override applies. So the question is asked back today. Plan returns early on `clarification_needed` (`:6970`). Probes on the branch as built: exact ID `calls=1`, rejected symbol `calls=1`, organism `calls=1`; the card's test with a resolving BRCA1 question also makes 1 call.
- Replacement is consistent. After `:4592` the turn reads `classification` only for `query_class` (`:4662`) and `narrative` (`:4711`), and reads `model_resolution` for everything else. Both come from the second reading. `exact_matches` is empty by the trigger. The organism-records and fallback blocks all run before the trigger, and their outputs are empty there. The second resolution goes through the same `_confirm_extracted_entities` against NCBI (`:6730`) and is taken only when it has CURIEs (`:6731`).
- Cost: the second call is charged and pre-flighted. Probe `test_probe_spend`: `one_read_resolves: think_calls=1 total_usd=0.000160`, `two_reads_resolves: think_calls=2 total_usd=0.000180`. Probe `test_probe_real_cap`, where the real pre-flight raises `QueryCapExceededError` on the second Think call only: `preflights=2 model_calls=1 asked_back=True`, with no error event.
- Stop: `asyncio.CancelledError` is not caught (`:6739` catches `TimeoutError` only), so a Stop still cancels. The venv is `3.11.6`, `asyncio.TimeoutError is TimeoutError` is `True`, and `requires-python = ">=3.11"`.
- Break it, from the brief: making `_read_question_again` return None turned 5 card tests red, the plain-English gap test included (`test_an_unread_first_question_is_read_again_and_answered`). Dropping the memory condition stayed green (J-145-02).
- Runs:
  - `test_clarification.py`: `14 passed in 3.05s`.
  - The 27 test files that reference `_think` or `think_node`: `976 passed, 84 skipped, 2 warnings in 44.78s`.
  - `ruff check` on `core/graph.py`, `test_clarification.py` and the report folder: `All checks passed!`. `ruff format --check` flags `graph.py`, but the diff shows lines outside this change (`:1653`, `:1746`, `:1996`); CI runs no `ruff format`.
  - The tree was restored after every mutation: `git status --short` shows only `?? frontend/node_modules`.
- Privacy: no local path, address or key in the committed report artifacts (grep for the home folder path, the owner's name, `@gmail`, `sk-` returned nothing).

## Verdict

- Overall: FAIL against the brief's checklist, while the owner's acceptance sentence is met as built.
- Met: a first question about to be asked back is read again. It is asked back only if the second reading also resolves nothing. The shapes I probed that answer today make one Think call.
- Failed: the timing check. The second reading can push an ask-back question to 25.8 s in my probe, and up to about 45 s by arithmetic, against "every answer within 20 s" (J-145-01). This is the shape card 56 slice 1 was closed for.
- Failed: the tests check. Every trigger condition can be removed one at a time with the card's tests green (J-145-02, J-145-03). So "no question that answers today pays for it" is true today but no test protects it.
- Verified with my own probes: slow second reading wall clock; memory without entities; each answering shape's call count, as built and mutated; exceptions on the second call and in the second confirmation; the step-failed log line; spend; the real cap pre-flight; all mutations.
- Read only, not probed: the Layer 2 call-ceiling exposure (J-145-08), wrong-binding exposure on dangling questions (J-145-09), the end-to-end recovered path (J-145-07, from after.md).
- Not a fix-round regression: these findings sit in card 145's first build commit `4f128c66`, not inside a fix made during a review round.
