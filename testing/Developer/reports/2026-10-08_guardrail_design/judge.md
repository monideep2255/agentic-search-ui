# Judge report, guardrail cards 84 and 72, round 1

Base: 55fdb1e3ca7b64690df6a407c5777d510d643b5f (branch fix/card84-72-guardrail, five commits over origin/develop).

## Findings

## Evidence log, written as each check was run

### E1: the suites the brief names, run one at a time on 55fdb1e3

- `pytest tests/system_03_search_agent/guardrail`: "367 passed in 78.06s".
- `pytest tests/system_03_search_agent/harness`: "472 passed in 24.58s".
- `pytest tests/system_03_search_agent/synthesis/test_sentence_check.py`: "99 passed in 3.85s"; `test_sentence_pair_check.py`: "47 passed in 3.90s".
- `npx vitest run src/hooks/useRunView.retryAfter.test.ts`: "Tests  9 passed (9)".

Green suites are the author's evidence, not mine; the probes below are mine.

### E2: 3d, is the sweep's copy of develop really develop?

Probe: `git archive origin/develop src` exported to a scratch folder, and the branch's own `run_case` and grids driven three ways by a scratch script: develop's real `src` with `port=False`, the branch's yardstick copies (`port=True`), and the branch's new code. Result, pasted:

- "develop real vs branch yardstick copy: identical 21908 of 21908 {'cls-guard': 10306, 'cls-jev': 10306, 'rel': 1296} diffs by grid {}"
- "develop real vs branch new: identical 21556 of 21908 ... diffs by grid {'rel': 352}"

So the copy is develop case for case (verdict, elapsed time, requests by kind), and the classifier path is unchanged in all 20,612 classifier cases. The check against develop's real code is not a standing test; it is the builder's one-off, now repeated here. Only the yardstick copies run in CI.

### E3: the relevancy grid against develop's real code, transitions

"Counter({('off_topic', 'ok'): 48, ('off_topic', 'injection'): 26, ('ok', 'off_topic'): 16, ('injection', 'off_topic'): 12})"; "any later (answered): 64 max delta 0.9000000000000004". These match the builder's counts.

### E4: the 16 cases develop admitted and the branch refuses off topic

All 16 have the same shape: the classifier admits (at 0.3 s or 6 s), Jev's injection pick is "not_injection" or an HTTP 500, Jev's relevancy pick is "off_topic" arriving 2.5 s after it is sent, the server pauses 0.6 s or 1.0 s as that request goes out, and the guard fallback pick is "on_topic" at 0.3 s or hangs. Cases rel-37, 38, 46, 47, 181, 182, 190, 191, 901, 902, 910, 911, 1045, 1046, 1054, 1055.

- Why develop admitted: 2.5 s plus the pause passes Jev's 3.0 s real-time bound, so Jev's own off-topic pick is thrown away and the guard fallback decides: "on_topic" admits at 3.3 s or 6.0 s, and a hanging fallback fails open and admits at 15.0 s. That is a timing accident: with no pause, develop itself refuses each of these as off topic on Jev's pick.
- The branch: Jev's own pick is read (free time 2.5 s), refused off topic at 3.1 s to 6.0 s, the same verdict the case gets with no pause, and never sends the guard fallback pick ("pick: 0").
- Is the refusal right: the grid is model-verdict combinations on a stub question, not real questions, so "genuinely off topic" cannot be checked from it. What can be checked is that the branch makes the same call Jev makes with no pause, which is develop's own policy in Jev mode. No on-topic question is refused here that develop would not refuse with no pause. Not blocking.

### J-GR-01: a pause still turns Jev's late on-topic pick into an off-topic refusal

- Severity: minor (an incomplete fix of 3b, not a regression: develop refuses every one of these cases too).
- What: `wait_counting_free_time` counts each look that a stall interrupts as `ask_s + _STALL_SLACK_S`, up to 0.1 s, though no free time passed (`harness/jev_client.py`, `counted += min(now - last, ask_s + _STALL_SLACK_S)`). A Jev reply in the last 0.1 s of its 3.0 s bound is therefore lost to any pause, however short, and the classifier's off-topic refusal stands. The design's promise for 3b is "an on-topic question Jev admits is no longer refused because the server paused".
- Evidence: scratch probe on the branch's own `run_case` (classifier off-topic at 0.3 s, Jev relevancy "on_topic", pause as Jev's request is sent, guard pick on_topic):
  - "Jev on_topic after 2.89s, pause 0.3s -> ok at 3.19s"
  - "Jev on_topic after 2.91s, pause 0.0s -> ok at 2.91s"
  - "Jev on_topic after 2.91s, pause 0.3s -> off_topic at 3.20s"
  - "Jev on_topic after 2.9s, pause 1.9s -> off_topic at 4.80s" (a pause under the 2 s allowance)
  - Develop on the same probe: "Jev on_topic after 2.75s, pause 0.3s -> off_topic at 3.30s", so the branch is strictly better.
- Why the author's tests miss it: the relevancy grid uses Jev times of 0.2 s and 2.5 s only, and the six stall arms in `test_followup_guardrail.py` place the stall where it is not charged against a 2.9 s reply.
- Smallest fix: count an interrupted look as the time asked only when the clock moved by less than the look plus slack, otherwise count nothing (or the measured free part); or state the 0.1 s residual in the design and the docstring. Jev's measured latency is under 0.4 s, so the person rarely meets it.

### J-GR-02: "a pause over 2 s ends Jev's clock" is not what the code does

- Severity: minor (a wrong stated rule; the behaviour errs toward reading Jev's own pick, which can only add a refusal or set aside an off-topic verdict the guard model already judged).
- What: the allowance caps total real time at the bound plus 2 s, not the pause at 2 s. A 4.7 s pause with a fast Jev reply is not counted at all, and Jev's pick is used. The design ("up to 2 s of pause", "a pause over 2 s still ends Jev's clock and refuses"), `JEV_STALL_ALLOWANCE_S`'s comment and build.md's residual all say otherwise; the residual test passes only because its Jev reply comes at 2.9 s, so 2.5 + 2.9 passes 5.0.
- Evidence: "Jev on_topic after 0.2s, pause 4.7s -> ok at 4.90s"; "Jev on_topic after 0.2s, pause 4.9s -> off_topic at 5.00s"; "Jev on_topic after 2.5s, pause 2.1s -> ok at 4.60s".
- Smallest fix: reword the constant's comment, the residual test's docstring and build.md to "Jev's clock ends at its bound plus 2 s of real time, whatever the pause", or cap the uncounted pause itself at 2 s if the design's wording is the intent. The owner should know which rule shipped.

### J-GR-03: wait_counting_free_time never ends on a clock that does not move, or on a NaN or infinite budget

- Severity: minor (no production caller reaches it today: the callers pass the constants 3.0 and 3.5, and in production `time.monotonic` is the loop's own clock and always moves; but the brief's check "cannot hang on a clock that does not move" fails as written).
- What: both exits of the loop are computed from the module's `time.monotonic`. If that clock stands still while the loop runs, `counted` and `real_left_s` never change and the loop looks every 50 ms for ever. A NaN budget makes both comparisons false for ever; an infinite one never runs out. `_NONE_LEFT_S` fixes only the case where the virtual loop does not advance for a tiny wait.
- Evidence: scratch probe calling the branch's `wait_counting_free_time` on a hanging awaitable under an outer 8 s `asyncio.wait_for`:
  - "real clock, budget 0.3 TimeoutError after 0.30s real"
  - "frozen clock, budget 0.3 (outer guard 8s) TimeoutError after 8.00s real" (the outer guard fired, not the function)
  - "backwards clock, budget 0.3 (outer guard 8s) TimeoutError after 8.00s real"
  - "budget nan TimeoutError after 8.00s real"; "budget inf (outer guard 8s) TimeoutError after 8.00s real"
  - "real clock, budget 0.5, 3s blocking pause TimeoutError after 3.01s real" (a pause longer than the allowance does end it, at once).
- Smallest fix: also bound the number of looks (budget plus allowance over `_LOOK_S`, plus a margin), or read `asyncio.get_running_loop().time()` for the real-time cap, and reject a budget that is not finite and positive at entry.

### E5: 3a charges, probed through the branch's real `call_jev` with `_post` replaced

Every case of the owner's rule holds. Pasted lines (name, outcome, charge):

- "usable, cost 0.00002  usable  charged 2e-05"; "usable, cost 0  usable  charged 0.0001"; "usable, cost missing  malformed_reply charged 0.0001"
- "usable, cost 0.01 exactly  usable  charged 0.01"; "usable, cost 0.05  malformed_reply charged 0.01"; "usable, cost 0.010001  malformed_reply charged 0.01"
- "usable, cost Infinity literal  malformed_reply charged 0.01"; "usable, cost 1e400 literal ... charged 0.01"; "usable, cost 10**400 int ... charged 0.01"; "usable, cost 'Infinity' string ... charged 0.01"
- "usable, cost NaN literal ... charged 0.0001"; "usable, cost -1 ... charged 0.0001"; "usable, cost -10**400 int ... charged 0.0001"; "usable, cost 'abc' ... charged 0.0001"; "cost True ... charged 0.0001"; "[] list" and "{} dict" 0.0001
- An unusable reply stating a sensible cost: "bad option, cost 0.00002  invalid_option  charged 2e-05"; "probabilities null, cost 0.003  malformed_reply charged 0.003" (FJ01 no longer escapes)
- "not JSON 200 ... 0.0001"; "deep nesting 200 ... 0.0001"; "HTTP 402 / 429 / 500 / 404 / 301  http_error  charged 0.0001"; "HTTP 500 stating cost 0.005  http_error charged 0.0001"
- "timeout (hang)  timeout  charged 0.0"; "transport failure  http_error  charged 0.0"
- "non-httpx exception in _post  ESCAPED RuntimeError: boom", uncharged; nothing came back, and develop behaves the same, so not filed.

The three charge sites (`core/graph.py:1664` and `:1674`, `harness/decide.py:332` and `:338`, `synthesis/sentence_check.py:689` and `:691`) each charge `exc.billed_cost_usd` or `result.cost_usd` as fixed in `jev_client`, so they cannot charge different amounts for one reply. The cap checks before a Jev call (`graph.py:1639`, `decide._run_jev_pick`, the sentence check's card 99 reservation) are unchanged in the diff apart from comments.

### J-GR-04: a stated cost a hair above $0 is charged as stated, so the "never $0" promise is only literal

- Severity: minor, unsure (it follows the owner's words, "above $0", exactly; filed so the owner sees the consequence).
- What: `jev_charge_usd` charges any stated figure above 0 as stated. A Jev reply stating `1e-300` is charged `1e-300`, which every cap sees as nothing, the same blindness F-72-J02 fixed for a stated $0. A units slip that shrinks the figure (the endpoint once misreported by a factor, F-8.6-V01) would leave every Jev call invisible to the caps again.
- Evidence: "usable, cost 1e-300  usable  charged 1e-300"; "bad option, cost 1e-300  invalid_option  charged 1e-300".
- Smallest fix, if the owner wants it: charge the floor for a stated figure below some plausible minimum (for example a tenth of Jev's measured $0.0000148), or leave it and record that the floor covers $0 and no amount only, as build.md already says.

### E6: mutations of the branch's own code, run in a scratch copy (`git archive HEAD`), each restored

Each mutation was a source edit, not a monkeypatch, run against the sweep and the named files:

- A hedge at the guard classifier's call site (a second request after 4 s, first reply wins, written into `core/graph.py` as a wrapper around `_dispatch_tier_call`): "FAILED ...test_the_classifier_matches_develop_case_for_case_with_the_guard_provider", "FAILED ...with_jev_on", "FAILED ...test_the_relevancy_wait_loses_nothing...". The sweep catches a re-introduced hedge.
- Jev's "not_injection" removing the classifier's injection refusal (`if not classifier_verdict.admitted and not (classifier_verdict.category == "injection" and injection_task is not None and not jev_says_injection):`): "FAILED ...with_jev_on", "FAILED ...test_the_relevancy_wait_loses_nothing...". The sweep catches Jev removing a refusal. (The author's own "catches Jev removing a refusal" test mutates the classifier's parse, not Jev; this probe is the real shape.)
- `decide()` never setting `jev_failed` after Jev fails: "FAILED ...test_decide_says_jev_failed_before_it_asks_the_guard_tier", "FAILED ...test_the_relevancy_wait_loses_nothing...".
- `wait_counting_free_time` counting real time (`counted += now - last`): four stall arms of `test_followup_guardrail.py` and the relevancy sweep fail.
- The topic check failing closed (`if relevancy is None:`): "FAILED ...test_the_relevancy_wait_loses_nothing...".
- The 15 s budget: `harness/harness.py` and `budget_for_step` are untouched (`git diff --stat` over `harness.py`, `cost_control.py` and `guardrail/` is empty). The sweep replaces `_step_deadline` with its own budget, so it would not see a change to the 15 s; `test_harness.py:530` and `:547` pin it instead.

### E7: 3c, `provider_of` over every Unicode code point

Each of the 1,114,112 code points was put between "a" and "b" and passed through the branch's `provider_of`: "outputs with a disallowed char: 0 []"; "categories of characters kept: {'Zs': 1, 'Pd': 1, 'Po': 1, 'Nd': 10, 'Lu': 26, 'Ll': 26}", that is the space, the hyphen, the dot, ASCII digits and ASCII letters only. "'Together\r\nINFO fake' -> 'TogetherINFO fake'"; "'x outcome=ok' -> 'x outcomeok'" (no forged key=value); "'‮evil' -> 'evil'"; a full-width letter is dropped. An allowlist of 65 characters strips every other category by construction. Passes.

### J-GR-05: the rate-limit wait words never reach a person

- Severity: minor (disclosed by the builder as a deviation; filed so the owner decides it, since the design promised it).
- What: design step 1 says a rate limit that named a wait reads "Try asking again in about 20 seconds", on the premise that the web app "already receives `source` and `retry_after_s` on every error". The backend sends `retry_after_s: 0` on every guardrail error (`core/graph.py` `_step_error_kwargs`, `"retry_after_s": 0`, and the unusable-verdict dict at `graph.py:2091`), so `guardrailFailure` always takes the plain branch. A person whose guard call was refused with a stated 13 s `Retry-After` reads "Try asking again." and can retry straight into the limit. The seconds and minutes branches are reachable only from the test.
- Evidence: the frontend mutations below show the branches are tested, but nothing in `src/` ever sets a non-zero `retry_after_s` for source "guardrail" (`grep -n '"source":\|source=' core/graph.py`: line 881 `"source": step` with `"retry_after_s": 0`, line 2091 the same).
- Smallest fix: either carry the stated wait into `_step_error_kwargs` for a rate-limited guard call (a backend change step 4 may forbid) or strike the "about 20 seconds" promise from the design so nobody believes it is live. The owner's call.

### E8: step 1, mutations of the web app copy, run in a scratch copy with the test file

- Every failure reading the guardrail words (source check removed): "Tests  1 failed | 8 passed (9)".
- The backend's own `message` rendered for a guardrail failure: "Tests  7 failed | 2 passed (9)".
- Seconds up to 20 minutes instead of 2: "Tests  1 failed | 8 passed (9)".
- A cancelled run reading the guardrail words: "Tests  1 failed | 8 passed (9)".
- A passed wait told to wait a second: "Tests  4 failed | 5 passed (9)".
- Daily cap declines carry sources `cost_control.check_user_daily_query_cap` and `cost_control.check_system_daily_cost_cap` (`graph.py:1829` to `1833`), not "guardrail", so they keep their own words. Only guardrail-sourced failures change. Passes.

### J-GR-06: the free-time clock also lengthens the sentence check's Jev calls, outside the guardrail

- Severity: minor (only under a server pause, at most 2 s; but it is inside this phase's own fix and outside its stated fence).
- What: `wait_counting_free_time` sits in the shared `_send`, so every Jev call, `call_jev_batch` from the sentence check included, now runs up to its bound plus 2 s of wall clock under a pause. The sentence check is given `min(budget_s - 1.0, _SENTENCE_CHECK_MAX_BUDGET_S)` by `core/graph.py` near line 9788 and has no outer real-time wait, so a pause can carry the Write step past its budget by up to a second. The debugging guide's row still says "a 3-second total timeout a caller may shorten but never lengthen", and design 3b's "Cost: nothing in seconds" names only the guardrail.
- Evidence: scratch probe, `call_jev_batch(..., timeout_s=1.0)` with `_post` blocking the loop 1.5 s then awaiting 0.4 s: branch "timeout_s=1.0: malformed_reply after 1.90s real" (my stub's reply shape was rejected, the point is the 1.90 s); develop "timeout_s=1.0: timeout after 1.51s real".
- Smallest fix: let `_send` take the allowance as a parameter, 0 for `call_jev_batch` (the sentence check), or wrap the sentence check in a real-time `asyncio.wait_for` of its budget; and update the debugging guide row.

### J-GR-07: the sweep does not count Jev requests in flight, so two Jev requests of one kind pass it

- Severity: minor (no such hedge exists on the branch; this is a hole in the gate the design names as step 2's gate).
- What: `_GuardStub` counts classifier and guard-pick requests and their peak in flight; `_jev_post` counts nothing. The rule "never two requests of one kind in flight" is therefore not checked for Jev's relevancy or injection requests. With a pause in the grid, a doubled Jev request is caught only by accident, because the stub stalls the server once per relevancy request, so two requests stall it twice and the timing check fires.
- Evidence: a source mutation in a scratch copy, `decide()` sending two `_jev_attempt` calls at once and taking the first: the full relevancy sweep fails only on the paused cases ("Jev relevancy hang@0 after a 0.6s pause, ...: develop 3.30s, new 4.40s, more than the 0.6s pause later"), and over the 432 no-pause cases: "mutated (two Jev requests in flight) -> no-pause relevancy cases 432 problems 0"; "unmutated -> no-pause relevancy cases 432 problems 0".
- Smallest fix: count Jev requests by question key in `_jev_post`, with an active counter and a peak, and add them to `_Run.peak` so `_check_new` checks them like the other kinds.

### J-GR-08: after a pause a verdict can come up to 2 s later than develop, not 0.9 s

- Severity: minor (the builder's own deviation, under-stated; the bound "never more than the pause" holds).
- What: build.md and the brief describe the lateness as "by 0.15 to 0.9 s, never more than the pause itself". That range is the grid's (pauses of 0.6 s and 1.0 s only). The real bound is the smaller of the pause and `JEV_STALL_ALLOWANCE_S`, 2 s. For a person: after a server pause of a second and a half or more, a question whose Jev call fails can wait up to 2 s longer for its answer than on develop.
- Evidence: scratch probe, develop's real code against the branch, same case (classifier admits at 0.3 s, guard pick on_topic at 0.3 s):
  - "DEVELOP: classifier admit, Jev hang@0.0, pause 1.5: ok at 3.30s   BRANCH: ... ok at 4.70s" (1.4 s later)
  - "DEVELOP: classifier admit, Jev hang@0.0, pause 3.0: ok at 3.30s   BRANCH: ... ok at 5.30s" (2.0 s later)
  - "DEVELOP: classifier off-topic, Jev hang@0.0, pause 3.0: off_topic at 3.30s   BRANCH: ... off_topic at 5.00s" (1.7 s later)
  - "pause 6.0": both at 6.30 s or 6.00 s, so past the allowance the lateness goes away.
- Smallest fix: state the bound as "up to the length of the pause, at most 2 s" in build.md and in the sweep's docstring, and add a 1.5 s and a 3 s pause to the relevancy grid so the gate covers it. The owner accepted the deviation on the 0.9 s figure; the 2 s figure is what ships.

### E9: the rules, scanned over every new result of the relevancy grid

From the branch's 1,296 relevancy results: "admitted with classifier hang: 0 | admitted though a judge said injection: 0 | off-topic set aside without Jev on_topic: 0 | past 15 s: 0"; "admitted total in relevancy grid: 240". `ruff check` over the repository: "All checks passed!"; `isort --check-only src tests`: no errors. The diff carries no local path, no address and no em dash in the added report text.

## Verdict

MERGE. No blocking or major finding. Eight minor findings, J-GR-01 to J-GR-08, none of which admits a question develop refuses, refuses an on-topic question develop admits with no pause, or breaks a rule every step keeps.

Note for the stop condition: every finding sits inside this phase's own new code. J-GR-01, 02, 03, 06 and 08 are in step 3b's free-time clock (`wait_counting_free_time`), J-GR-04 in step 3a's charge rule, J-GR-05 in step 1, and J-GR-07 in step 3d's sweep. This is round 1, so there is no earlier fix round for them to sit in.

The builder's two deviations, judged:

- Up to 0.9 s later after a pause: accepted in kind, but the true bound is 2 s, not 0.9 s (J-GR-08). The owner should accept the 2 s figure.
- The 16 cases develop admitted under a pause: each is a timing accident on develop (Jev's own off-topic pick thrown away by a real-time clock, then the guard fallback or the fail-open admitted), and each now matches the verdict the same case gets with no pause (E4). Accepted.
- Plumbing in `guardrail_node`, `_relevancy_decision` and `_decide_point`: the smallest change that carries the event, with no other behaviour change; the classifier path is identical to develop in all 20,612 classifier cases (E2). Accepted.

What I verified with my own probes: the yardstick equals develop's real code case for case (E2); the 16 cases and all verdict transitions (E3, E4); every 3a charge case through the real `call_jev` (E5); the sweep catching a source-level hedge, Jev removing a refusal, a missing signal, a real-time clock and a fail-closed topic check (E6); `provider_of` over every code point (E7); step 1's words under five mutations (E8); the rule scan (E9); and J-GR-01, 02, 03, 06, 07 and 08 by direct reproduction.

What I only read: that the 15 s budget is unchanged (no diff in `harness.py` or `budget_for_step`, and the sweep cannot see it); that the cap checks before a Jev call are unchanged (comment-only diffs); that the three charge sites charge identical amounts (each charges the figure `jev_client` fixed; I probed `jev_client`, not each site); and the debugging guide row.
