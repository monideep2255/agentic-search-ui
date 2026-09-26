# Builder F2, build phase 8.6 fix round: one judge per reworded sentence, and four smaller repairs

Fix builder F2, the one fix-and-verify round after the judge and the adversary (`tracker/phase_8.6.md`, "Lead triage after round 2"). Branch `fix/8.6-f2`, based on `0a9a4ba`. Each finding below was written the moment it was established.

## Table of contents

- [What a person using the product notices](#what-a-person-using-the-product-notices)
- [Commits](#commits)
- [Fix 1: the reworded-sentence check](#fix-1-the-reworded-sentence-check)
- [Live before and after on the adversary's A09 set](#live-before-and-after-on-the-adversarys-a09-set)
- [Fix 2: the rule's bounded exception](#fix-2-the-rules-bounded-exception)
- [Fix 3: the reasoning retry](#fix-3-the-reasoning-retry)
- [Fix 4: what a Jev reply costs](#fix-4-what-a-jev-reply-costs)
- [Fix 5: stale words](#fix-5-stale-words)
- [Fix 6: drift](#fix-6-drift)
- [Tests and gates](#tests-and-gates)
- [Left open for the lead](#left-open-for-the-lead)

## What a person using the product notices

- A reworded sentence is shown as checked only when Jev is more sure it adds nothing than that it adds something. A coin toss withholds it, and the reader gets the code-built line in its place.
- When Jev fails, no weaker second judge waves a reworded sentence through. The answer keeps only what code alone can verify.
- A question whose provider error merely mentions reasoning is no longer sent a second time with reasoning left to the provider's default, which measured 20 to 45 seconds on the writing tier.
- Nothing else is visible. Fixes 4 to 6 are cost accounting and documentation.

## Commits

| Commit | Subject | Findings |
| --- | --- | --- |
| `e40849e` | fix(write): approve a reworded sentence only when Jev's own odds back it | A01, J14, A09, A16 |
| `5fabfa7` | docs(rules): name the sentence check's judge and its fail-closed list as they now are | J14 |
| `a4ae762` | fix(harness): retry without the reasoning block only on the provider's own refusal phrase | J05, A02 |
| `494ea63` | fix(harness): charge an unusable Jev reply at its reported cost, never at zero | J10 |
| `add9b9e` | docs: correct the words build phase 8.6 left stale in code and schema pages | J07, J11, J16 |
| `69ddae1` | docs: date the Debugging guide to its latest change | J15 |

## Fix 1: the reworded-sentence check

- F2-01 (the change, `synthesis/sentence_check.py`): with `CLASSIFIER_PROVIDER=jev` a sentence is approved only when Jev picks "no, it says nothing more" AND Jev's own probability for "no" is strictly higher than for "yes" (`_jev_approves`). The details:
  - A pick at exactly even odds approves nothing.
  - So does a pick its own probabilities contradict, or an answer missing either probability.
  - `confidence` is never read, since it is the margin between the options (A16).
  - A failed, late, malformed or cost-capped Jev call approves nothing and asks no other model; `GUARD_FALLBACK_MIN_S` and the fallback are gone.
  - The guard provider's path is develop's, byte for byte.
  - The exact checks in `grounding.exact_synthesis_checks_pass` are untouched and still run first.
- Tests, in `tests/system_03_search_agent/synthesis/test_sentence_check.py`:
  - G6: every Jev failure approves nothing and never asks a guard that would approve everything. Covered failures are a timeout, an HTTP error, a malformed reply, an option outside the set, an unexpected error, an unreadable verdict and a late reply through the real client.
  - G8: the probability rule through the real `call_jev_batch`, with only its HTTP seam stubbed. It includes the adversary's two A01 reply shapes, which approved item 1 before and approve nothing now, and a reply where one sentence at even odds leaves the others approved.
  - Write step: in Jev mode a failed Jev dispatches no guard-tier call, and in guard mode the write step makes develop's one guard call with the whole 12-second budget.
- Mutants, run as pytest plugins from the session scratchpad, not committed:
  - The bare-choice rule turns 8 tests red.
  - Putting the guard fallback back turns 10 tests red.
- F2-02 (established reading the code, outside this fence): two places still say the guard tier is asked when Jev fails. Both are builder F1's files:
  - `core/graph.py`'s `_ground_with_sentence_check` docstring.
  - `docs/architecture/Model_architecture.md`'s sentence-check table row and its Jev section, which also names the 2-second floor.

## Live before and after on the adversary's A09 set

Method:

- The sentences are the adversary's probe G, unchanged: 6 faithful and 22 unfaithful rewordings over two abstracts. The exact checks block 2 of the unfaithful ones, so 20 reach Jev. The brief's "18 faithful" are those 6 over 3 runs.
- Each side made 3 runs through the real `check_reworded_sentences`, with `CLASSIFIER_PROVIDER=jev` and a guard stub that raises if asked. It was never asked.
- Before is a `git archive` of `0a9a4ba`. After is this branch at `e40849e`.
- The probe script and its full output stay in the session scratchpad.

| Code | Run | Faithful approved | Unfaithful approved |
| --- | --- | --- | --- |
| Before, `0a9a4ba` | 1 | 3/6 | 0/20 |
| Before, `0a9a4ba` | 2 | 5/6 | 0/20 |
| Before, `0a9a4ba` | 3 | 4/6 | 0/20 |
| Before, total | 3 runs | 12/18 | 0/60 |
| After, fix branch | 1 | 3/6 | 0/20 |
| After, fix branch | 2 | 4/6 | 0/20 |
| After, fix branch | 3 | 5/6 | 0/20 |
| After, total | 3 runs | 12/18 | 0/60 |

Spend: $0.00104 before and $0.00104 after, $0.00208 in all, against the brief's $0.10.

- F2-03 (live): Jev reports its probabilities rounded to two decimals, while `confidence` keeps a finer margin. Three of the 36 faithful answers read came back at p(no) 0.5 and p(yes) 0.5:
  - Before, run 1: "Taking these drugs for a long time is linked to broken bones and kidney disease", picked "yes", confidence 0.0.
  - After, run 1: "These drugs were not linked to bowel cancer", picked "no", confidence 0.01.
  - After, run 2: "Nearly three quarters of BRCA1 carriers develop breast cancer by age 80", picked "no", confidence 0.01.
- On the after side's own replies the bare-choice rule would have approved 14 faithful sentences (4, 5 and 5); the new rule approved 12 (3, 4 and 5). The two withheld are the "no" picks above: "exactly even" in the reply covers margins under half a point.
- On this set the rule prevented no wrong approval, since Jev picked "no" for no unfaithful sentence in any of the 6 runs. Its cost here was a correct plain-language sentence replaced by the code-built line, 2 times in 18 faithful chances. Its guard is against the A01 shape, a "no" at even odds, which occurred twice in these 6 runs.
- Whether to ask more than "strictly more likely than not" stays the product owner's call; this rule sets no number of its own.

## Fix 2: the rule's bounded exception

- `.claude/rules/production-standards.md`, the one bounded exception bullet only, one line. The permission check allowed the edit.
- It now names the judge: Jev with `CLASSIFIER_PROVIDER=jev`, citing DECISIONS.md 2026-09-25, and the guard tier with the guard provider, never both for one answer.
- Its fail-closed list now reads: an unreadable reply, a failed or late call, the cost cap or too little budget accepts nothing. With Jev, only a "no" with a strictly higher probability is accepted, and a Jev failure gets no guard-tier second chance.
- The scope, the three exact checks, the 0-of-53 measurement and the sign-off sentence are unchanged. The word diff removes only "a guard-tier" (now "one"); everything else is added.
- `check_style.py`: 2 hard findings, identical on the base copy. They are `wall-comma-chain` at line 13 and `toc-missing`, both outside the bullet this fence allows, so this edit adds none.
- F2-04 (merge note): the other builder's "Grade this with the `eval-harness` skill" bullet is the very next line, so git will likely report the two edits as a conflict on merge. Keep both lines.

## Fix 3: the reasoning retry

- `harness/harness.py`: `_refuses_reasoning_block` now matches the whole phrase "reasoning is mandatory for this endpoint and cannot be disabled", lower-cased with runs of whitespace collapsed. It never matches a `ContextWindowExceededError` or a `ContentPolicyViolationError`, which litellm makes subclasses of `BadRequestError` and whose text can echo the person's words.
- These are not retried now:
  - A context-window 400 naming reasoning.
  - A content-policy 400 echoing "explain the reasoning behind BRCA1 testing".
  - A content-policy 400 echoing the refusal phrase itself.
  - A context-window 400 carrying the phrase.
  - A plain 400 echoing "a clinical reasoning question".
- The live text, an upper-case copy and a copy wrapped over two lines are still retried once without the block.
- Mutant: the old word match turns all 5 not-retried cases red.

## Fix 4: what a Jev reply costs

- `harness/jev_client.py`: `JevCallError` carries `billed_cost_usd`, the cost a reply that came back unusable reports. Unusable means malformed, an option outside the set, or a cost above `MAX_JEV_COST_USD`. `decide()` and the sentence check charge it before the error goes on. The reply is still not used, and the cost cap applies to the rest of the question: a $0.02 reply against a $0.015 cap now stops the guard fallback before it is sent.
- Decided from the user's chair, where the brief was silent: only a real amount is charged, meaning finite and zero or more. A figure that is not one charges nothing and logs a warning, so the zero is never silent. The reasons:
  - Infinity stopped every later model call in the question and blanked its cost (F-8.2-J15).
  - NaN would switch the per-query cap off, since `check_per_query_cap` refuses only when `projected > cap`, which is never true with NaN.
  - A negative charge would give money back to the caps.
- Tests cover `call_jev` and `call_jev_batch` (the billed figure for each shape), `decide()` and the sentence check through the real client, and the cap arm.
- Mutants:
  - Dropping the charge turns 13 tests red.
  - Charging any figure turns 11 red.

## Fix 5: stale words

- Golden-run scripts (J07): `run_consistency.py` and `summarize.py` now say the first word is the first text a person sees, an answer, a refusal or a question asked back alike. Only a guardrail refusal, a cap decline, an error or a timeout leaves it empty. The summary's row label, which `golden_client_dry_run.py` reads, is unchanged.
- `Harness.last_call_elapsed_s` and `CostPayload.call_elapsed_s` (J11): the value is the latest completed call on the tier, so Plan answering from a template repeats Think's plan-tier time.
- `DecisionRecord` and `DonePayload.decisions` (J16): the loop attaches the records, Jev decides alone with the guard tier only on its failure, and `agreed` stays empty on every live record.
- `harness/task_tiers.py` (J16):
  - The sentence check is a "classifier" row.
  - `guardrail.injection` and `think.asks_features` are added.
  - `plan.resource` is marked as not yet asked by any step.
  - The docstrings no longer say the guard runs beside Jev or that the seam is unwired.
- `visualizations/Schema_visualization.md`: the `cost` row lists `call_elapsed_s`, and the `done` row and diagram list `decisions`.
- F2-05: `think.query_class` is left out of the task-tier table because the triage has F1 revert T-8.6-05. If that revert does not land, the table needs the row.
- F2-06 (outside this fence): `core/graph.py`'s "classifier seam, wired" comment still says the guard tier decides every question beside Jev and is recorded, stale since T-8.6-01.

## Fix 6: drift

- `docs/build/Debugging_guide.md` now reads "Last updated: 2026-09-26", and the drift check no longer reports it.
- Three structural findings remain, all outside this fence:
  - `testing/Developer/reports/2026-09-26_slowdown/findings.md` and `testing/Developer/reports/2026-09-26_writer_bench_2/results.md`, each with a `##` section missing from its table of contents.
  - `tracker/phase_8.6.md`, whose table of contents lacks "Lead triage after round 2".
- The stale counts were ignored, as briefed.

## Tests and gates

Pasted from each command's output at `69ddae1`:

- Named suites (`harness`, `synthesis`, `contracts`, `test_debugging_guide_coverage.py`): `1088 passed, 10 skipped, 1 xfailed in 35.28s`. The baseline at `0a9a4ba` was `1048 passed, 10 skipped, 1 xfailed in 49.81s`.
- Full unit suite, as CI's gate04 runs it: `5720 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 334.69s (0:05:34)`, exit 0.
- `golden_client_dry_run.py`, offline, over the two edited golden-run scripts: `dry run: every check passed`, including the summary's new wording ("Time to the first word, on the client's clock from submitting the question to the first text a person sees arriving, answer, refusal or question alike: 0.4 / 0.4 / 0.4, over 1 of 2 runs.").
- `ruff check .`: `All checks passed!`
- `isort --check-only src tests`: `Skipped 2 files`, exit 0.
- `check_style.py`:
  - `docs/build/Debugging_guide.md`: `ok: 0 hard | 0 advisory`.
  - `visualizations/Schema_visualization.md`: `ok: 0 hard | 0 advisory`.
  - `.claude/rules/production-standards.md`: `2 hard | 0 advisory`, both pre-existing (Fix 2).
  - This report: `ok: 0 hard | 2 advisory`. The two advisories are "Jev" capitalized in a heading, a proper name, and a suggested diagram this fix list does not need.
- `tracker/check_doc_drift.py --check`: `error: 6 facts computed (4 skipped) | 3 stale | 3 structural`, none of them in this fence (Fix 6).

## Left open for the lead

- A03 and J08: the triage gives builder F2 a budget-aware guard fallback in `decide()`, but the brief's six fixes do not include it, so it was not done. It needs the calling step's remaining budget, which only `core/graph.py`, F1's file, can pass.
- Stale text in F1's files (F2-02, F2-06): `_ground_with_sentence_check`'s docstring, the "classifier seam, wired" comment and `docs/architecture/Model_architecture.md`'s sentence-check text.
- F2-04: the rule's two adjacent bullets will meet at merge.
- F2-05: the task-tier table assumes F1's revert of T-8.6-05.
- F2-03, for the product owner: on this set, 2 of 18 faithful chances were withheld at a reported 0.5 to 0.5.
