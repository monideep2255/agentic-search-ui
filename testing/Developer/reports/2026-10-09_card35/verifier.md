# Card 35 verifier report, 2026-10-09

Fresh-context verifier after the fix round, branch fix/card35-offtopic-followup at 40b454eb against develop b01dee92. No live model calls. Findings are appended as established.

## Findings

### V-35-01: Offline grid, guard provider: every changed verdict is admit to refuse:off_topic on an allowlisted memory-bound follow-up whose topic check said off topic inside the bound
- Severity: unsure (intended by design; recorded as evidence, not a defect)
- What: the verifier's own grid ran the real `guardrail_node` from develop (b01dee92, exported with `git archive` to a temp folder outside the checkout) and from 40b454eb, stubbed only at `litellm.acompletion` (guard classifier), `graph.decide` (topic check) and `graph.call_jev`, sockets disabled. 21 texts in five groups (13 on-topic follow-ups with a referring word, 4 other on-topic, 5 off-topic follow-ups with a biomedical word, 3 other off-topic, 3 injections carrying a referring word and a biomedical word) by memory BRCA1 or none, by 6 guard outcomes (ok, off_topic, injection, junk, error, hang), by 9 topic outcomes (Jev on, Jev off, guard-fallback on, guard-fallback off, no usable pick, seam raises, hang, off topic after 2.0 s, off topic after 0.3 s). Guardrail budget patched to 4 s for speed.
- Reproduction: 3024 cases per tree, 114 changed, all `admit -> refuse:off_topic`, all memory=True and allowlist=True, topic outcome only jev_off, g_off or fast_off (0.3 s). 0 cases moved from refuse or step error to admit. No change under nopick, raise, hang or slow_off (2.0 s, past the bound): those keep develop's admit. 72 of the 114 are on-topic follow-ups refused only because the stubbed topic check wrongly said off topic (the live rate of that is the judge's 0 of 48, not re-measured here, no live calls).
- Caveat on method: a first run with 1500 cases in flight at once showed load-induced timing noise (allowlist misses differing between trees, where the code is identical); the run reported here uses 150 at a time and is clean.
- NOT FIXED
### V-35-02: Timing, sequential at the real 15 s budget: a hung topic check adds at most 1.5 s from its start, and the cancelled task leaves nothing running
- Severity: unsure (evidence that the fix-round claim holds on the main path)
- What: sequential probe, real `budget_for_step`, one question at a time, text "Which variants of it are pathogenic?" with BRCA1 in memory, topic check stubbed to sleep 600 s, guard classifier replying ok after a set delay.
- Reproduction (develop / 40b454eb, guardrail seconds, guard provider; the Jev provider gave the same to 0.02 s):
  - classifier 0.0 s: 0.00 / 1.50; 0.5 s: 0.51 / 1.50; 1.0 s: 1.00 / 1.50; 2.0 s: 2.00 / 2.01; 3.0 s: 3.01 / 3.00. Verdict admit on both.
  - classifier off_topic at 0.2 s (set aside by the referring word), topic hangs: 0.21 / 1.50, admit on both.
  - topic answers on_topic in 0.3 s: classifier 0.0 s, 0.01 / 0.30; classifier 2.0 s, 2.00 / 2.01. So "no added wait" holds only while the classifier is the slower call; the added wait is the topic check's own time minus the classifier's, never more than 1.5 s.
  - inside and outside the bound, "Which cell phone is it best to buy this year?", classifier 0.2 s: topic off_topic at 1.4 s refuses at 1.40 s; topic off_topic at 1.6 s is cancelled at 1.50 s and admitted (develop's verdict, develop 0.20 s).
  - every hung run: topic check started 1, cancelled 1 (CancelledError reached the stub), still running after the node returned 0, other asyncio tasks left 0.
  - other paths keep the step deadline: allowlist miss "What is the capital of France?", topic hangs, 15.00 s develop / 15.01 s branch; topic answering at 5 s, 5.01 / 5.01.
- NOT FIXED
### V-35-03: With Jev on, a follow-up Jev calls injection waits up to 3.75 s for a hung topic check before being refused; develop refuses it at once
- Severity: minor (same verdict, refusal only; inside the card's code: the fix round's new ternary in `_guardrail_after_prefilter` puts `certain_refusal` ahead of `follow_up_only`, so this sub-path keeps Jev's own window, 3.75 s, instead of the 1.5 s bound)
- What: CLASSIFIER_PROVIDER=jev, allowlisted memory-bound follow-up, guard classifier ok, Jev's injection pick "injection", topic check hung. The branch waits until `_jev_own_pick_deadline` (started + 3.75 s); develop asked no topic check and refused immediately.
- Reproduction: sequential probe, real budget. "Which variants of it are pathogenic?": develop refuse:injection 0.21 s, 40b454eb refuse:injection 3.78 s. "Which cell phone is it best to buy this year?": 0.21 s versus 3.77 s. Topic check started 1, cancelled 1, nothing left running.
- Why it matters: the brief's check 2 ("a follow-up on this path waits at most about 1.5 s more than develop") does not hold on this sub-path: 3.57 s more. The person is refused either way, and the total stays far inside 20 s; it needs Jev on (develop deployment), a Jev injection pick on a follow-up, and a slow or failing topic check at the same time. The judge recorded the same 3.75 s cap at cd0e65a8 (J-35-03); the fix round did not bring this sub-path under the new bound. Using `min(follow_up_deadline, _jev_own_pick_deadline(...))` when both apply would, on reading, close it; not tested.
- NOT FIXED
### V-35-04: The bound's test goes red when the bound is removed from the wait; a first mutation showed one assertion is a constant check
- Severity: minor (test quality, for the record)
- What: two mutations of `core/graph.py`, each restored with `git checkout`.
- Reproduction:
  - Mutation B, behavioural: the `else follow_up_deadline if follow_up_only` arm deleted from the wait, so the follow-up waits to the step deadline. `-k "hung_follow_up_topic_check or inside_the_bound"`: 2 failed, 1 passed, failing at `assert elapsed < bound + 1.0` with "assert 15.007548374996986 < (1.5 + 1.0)". Restored.
  - Mutation A: `_FOLLOW_UP_TOPIC_CHECK_BOUND_S` set to 1000.0. Also 2 failed, but the first assertion to trip is `assert bound <= 1.5`, a check of the constant's value rather than of the wait. Restored.
- Why it matters: the behavioural proof (mutation B) is real, so check 3 holds. Not caught by either fix-round test: the bound counted from the read rather than from the topic check's start (both are the same when the stub classifier replies instantly), and V-35-03's Jev-injection sub-path, which no test covers.
- NOT FIXED
### V-35-05: Query 111 is typeable and its off-topic texts reach the card's path; two of its three controls do not exercise the changed path
- Severity: minor (test-document coverage)
- What: query 111 sits in section 6 of `testing/Test_queries_and_workflows.md`, numbered once, with a row in the "card 35" table pointing at it. Its texts are plain sentences a person can type after query 1.
- Reproduction: `prefilter.clears_biomedical_allowlist` on 40b454eb: "Which cell phone is it best to buy this year?" True, "Is it effective to invest in bitcoin right now?" True (both allowlisted and memory-bound, so the new topic check decides them); controls "what about its symptoms" True (the changed path), "and what about it in children?" False and "tell me more about it" False (allowlist misses, topic-checked on develop already, so unchanged by the card). `prefilter.screen` is None for all five.
- Why it matters: only one control proves an on-topic follow-up on the new path stays answered. A second allowlisted control, for example "Which variants of it are pathogenic?", would make the owner's check cover the risk the judge named in J-35-01. The entry's "waits for the slower of the two, not both" is true while the topic check is healthy; V-35-02 shows up to 1.5 s more when it hangs, and V-35-03 up to 3.75 s on a refusal with Jev on. Not visible to the owner as written.
- NOT FIXED
### V-35-06: Offline grid, Jev provider: no admission develop refused, no injection admitted; category and timing changes only on the allowlisted memory-bound path
- Severity: unsure (evidence; the category change is the judge's J-35-02, still present)
- What: the V-35-01 grid with CLASSIFIER_PROVIDER=jev and a fifth axis, Jev's injection pick (injection, not_injection, hang, error, malformed), budget patched to 6 s, 300 cases in flight at once.
- Reproduction: 15120 cases per tree, 627 changed, all memory=True and allowlist=True; 0 changes elsewhere. Transitions: admit to refuse:off_topic 494, refuse:injection to refuse:off_topic 133. Develop refuse:injection to branch admit: 0. Any change to admit: 0. On-topic follow-ups newly refused: 312, every one under a stubbed off_topic topic pick (jev_off 96, g_off 96, fast_off 96, slow_off 24). The 24 slow_off rows (a pick at 2.0 s, past the 1.5 s bound) are refused because the node was already waiting longer for something else, Jev's own injection pick hanging or Jev's injection window (V-35-03), and the pick arrived during that wait: no extra wait, but the 1.5 s bound is not the only thing deciding whether a late off-topic pick counts. Largest added waits: 3.61 to 3.71 s, all Jev pick injection with the topic check hung (V-35-03).
- NOT FIXED
### V-35-07: The 1.5 s bound was calibrated on Jev's topic latency; with the code-default guard provider the topic check takes about as long as the bound
- Severity: unsure (no regression against develop; a possible loss of the card's catch where the guard tier decides)
- What: `_FOLLOW_UP_TOPIC_CHECK_BOUND_S` cites Jev's 0.3 s median and 0.77 s maximum. With CLASSIFIER_PROVIDER unset, the code default and per `docs/architecture/Model_architecture.md` what production runs, `decide()` asks the guard tier, which the adversary measured at 1.42 to 1.79 s for this decision and 0.26 to 5.54 s over 60 calls. A topic pick that lands after 1.5 s from its start is dropped when the guard classifier has already replied.
- Reproduction: read, plus V-35-02's offline pair: classifier 0.2 s, topic off_topic at 1.4 s refused; at 1.6 s admitted. No live latency measured here (no live calls).
- Why it matters: on the guard provider the off-topic follow-up the card targets is refused only when the topic call beats 1.5 s or the classifier is slower than the topic call; otherwise it is admitted as on develop. Never worse than develop, but the judge's 88% catch was measured with Jev and may not carry to production.
- NOT FIXED

## Checks run by the verifier

| Check | Result |
|---|---|
| `tests/system_03_search_agent/guardrail` | 411 passed |
| The card's grid and refusal tests, `-k "no_on_topic_follow_up_develop_admits or off_topic_follow_up_with_a_biomedical_word or first_question_the_allowlist_admits"` | 61 passed |
| `test_guardrail_node_integration.py`, the file the fix agent ran | 124 passed |
| `ruff check` (no path) | All checks passed, exit 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | "Skipped 2 files", exit 0 |
| Mutations | V-35-04, both restored with `git checkout`; `git status --short` shows only `frontend/node_modules` and this report |

## Verdict

HOLD, on V-35-03.

- Check 1, offline grid on both trees: holds, verified with my own probes (V-35-01, V-35-06). Every changed verdict moves toward refusal; nothing develop refused is admitted; no injection is admitted; an on-topic follow-up is newly refused only when the topic check itself says off topic. Under ok, no pick, seam error, junk, hang and timeout it keeps develop's verdict.
- Check 2, timing: holds on the main path (V-35-02: hung check adds at most 1.5 s from its start, the cancelled task leaves nothing running, other paths keep the step deadline). It does not hold on one sub-path (V-35-03): with Jev on, a follow-up Jev calls injection waits up to 3.75 s, 3.57 s more than develop, for the same refusal. This sits inside the fix round's own new ternary, which orders `certain_refusal` ahead of `follow_up_only`; the judge recorded the 3.75 s cap at cd0e65a8 and the fix round left it. Per the review loop's stop condition this goes to the product owner. On reading, taking the earlier of the two deadlines would close it.
- Check 3: holds, mutation B goes red at 15.0 s and is restored (V-35-04).
- Check 4: holds, run by me.
- Check 5: query 111 can be typed and its off-topic texts reach the new path; only one of three controls exercises it (V-35-05). Read and probed with the allowlist function, not typed into the running product.
- Only read, not probed: the live topic-pick accuracy and latency (no live calls; the judge's and adversary's numbers stand), V-35-07, and the build report's cost estimate.
