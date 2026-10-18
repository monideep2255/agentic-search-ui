# Card 72 / R-10 judge round, 2026-09-29

Branch `fix/card72-r10-guardrail`, commits 29b53b0c..9e08d1d0 over origin/develop. One round. Probes are stubs and fake clocks only; no live model calls, no deployed app.

## Findings

### F-72-J01: an injection verdict already in hand is discarded when both hedged replies land in the same loop pass
- Severity: blocking (inside this change's own fix, card 72 option A; unsure only on how often production hits it)
- Where: `src/system_03_search_agent/core/graph.py:1760` (`for task in sorted(done, key=... number)`) with `:1817` (`return classification, verdict` on the first usable reply) and the `finally` at `:1853` that logs every unread request as `stopped_because`.
- What: when `asyncio.wait` returns both requests in `done`, the loop walks them by request NUMBER, not by arrival, and returns on the first usable one. Request 2's verdict, already parsed-able and already paid for, is never read. If request 1 says admit and request 2 says injection, the question is admitted. Arrival order does not matter: request 2 can finish first. The log then says request 2 was "cancelled, the other request answered first", which is false.
- Reproduction (stubbed `litellm.acompletion`, real `guardrail_node`, Jev off, scratch `judge72/p1b_node.py`): request 1 answers ADMIT at 4.5 s one tick AFTER request 2, request 2 (the hedge) answers `is_injection: true` first. Output:
  ```
  LOG guard classification request 1 of 2 (trace t-feef4ed5): answered after 4.50s, upstream not named
  LOG guard classification request 2 of 2 (trace t-feef4ed5): cancelled, the other request answered first after 0.50s, upstream not named
  sent 2 guard events [{'passed': True, 'category': 'ok', 'reason': None}] step_error None cost 3.9999999999999996e-05
  ```
  Direct `_classify_within_budget` probe (`p1_same_tick.py`), both replies released together: `('A', 'I') ... is_injection= False`; `('I', 'A') ... is_injection= True`. The outcome is set by request numbering alone.
- Why it can happen live: both replies in one `done` set needs them to complete before the waiting coroutine resumes, which is exactly what an event-loop stall produces (the stall FA03 is about): both sockets are readable when the loop wakes. Before the hedge there was only one verdict, so this state did not exist.
- What a person would notice: nothing, which is the problem. A question the guard model called injection is answered, and the operator log says the injecting reply was cancelled. Fix shape (not mine to make): when `done` holds more than one usable reply, refuse if any of them says injection or off topic, or at least read all of them before returning; and log an unread finished request as "answered, not read".
- NOT FIXED

### F-72-J02: R-10 line 3 as written is not met: a USABLE Jev reply stating $0 is still charged $0
- Severity: should-fix (an acceptance line not met in its own words; the builder named the reading, so this is a decision to put to the owner, not a hidden gap)
- Where: `src/system_03_search_agent/harness/jev_client.py:184` (`cost_usd: ... Field(ge=0.0, le=MAX_JEV_COST_USD)`, so 0 is accepted as usable), charged as stated at `core/graph.py:1943` (`harness.track_cost(trace_id, "guard", result.cost_usd)`) and in `decide._run_jev_pick`.
- What: the ledger line reads "Every Jev reply that reached the provider is charged between one cent and `MAX_JEV_COST_USD`, for every body shape." Only UNUSABLE replies now get one cent. A usable 200 reply that states `usage.cost: 0` (or 1e-12) reaches the provider and is charged that, so the per-query cap sees nothing for it. This is the same shape as FJ02 (a reply stating $0 charged $0), moved from the unusable arm to the usable arm.
- Reproduction (`judge72/p3_jev_cost.py`, `jev_client._post` stubbed with a well-formed 200 body, real `Harness`):
  ```
  injection pick, stated cost 0 -> JevResult not_injection charged 0.0
  injection pick, stated cost 1e-12 -> JevResult not_injection charged 1e-12
  decide relevancy stated 0 -> jev on_topic charged 0.0
  ```
- Why it matters: `system-design-patterns` pattern 4 and `production-standards` say a cost cap that guesses must guess toward stopping. The undocumented alpha endpoint has already sent one unit slip (12.5 for $0.0000125, F-8.6-V01); a slip toward zero is invisible to every cap. A person notices nothing; the cap simply under-counts. The builder's cost argument (5 to 7 cents a question if every usable reply were charged a cent) is real, so a floor of the smallest plausible price, not a full cent, is one middle reading. Owner's call.
- NOT FIXED

### F-72-J03: FA03 is marked closed but still reproduces: a 0.6 s stall one step later turns Jev's admission into an off-topic refusal
- Severity: should-fix (the flag's own severity; the builder's table says "closed", and R-10 line 1's "so a stalled server never turns a Jev admission into a refusal" is false)
- Where: `src/system_03_search_agent/harness/decide.py:101` (`_JEV_WAIT_S = JEV_TOTAL_TIMEOUT_S + 0.5`) and `:349-353` (`asyncio.wait_for(_run_jev_pick(...), timeout=_JEV_WAIT_S)`), whose timeout then sets `jev_failed` at `:492-493`, which `core/graph.py:1984-1998` acts on.
- What: the outer net is armed when `_jev_attempt` starts; Jev's own 3 s bound is armed later, inside `call_jev` (`jev_client.py:378`). Any event-loop stall that lands between the two (in `_run_jev_pick`'s cap check, or simply the scheduling gap before that task first runs, which is where another question's synchronous daily-cap SQL would land) spends the outer net's 0.5 s margin. Jev then answers inside its own bound, the outer net has already fired "timeout", `decide()` correctly raises the new signal, and the guardrail correctly acts on it: the question is refused. The signal is honest; the clock behind it is still the clock FA03 named, 0.5 s tighter than R-06's.
- Reproduction (`judge72/p4_fa03.py`: real `guardrail_node`, real `decide()`, Jev mode, classifier says off topic, Jev's injection pick "not_injection", Jev's relevancy `_post` answers on_topic 2.9 s after its request; a blocking stall placed once, either where the builder's test puts it or in `_run_jev_pick`'s cap check):
  ```
  stall 1.0s at resolve_jev_model (the builder's spot): guard={'passed': True, ...} after 3.91s records=[..., ('guardrail.relevancy', 'jev', 'on_topic', None)]
  stall 0.8s at inside Jev's wait, before its request: guard={'passed': False, 'category': 'off_topic', ...} after 3.50s records=[..., ('guardrail.relevancy', 'guard', 'off_topic', 'timeout')]
  stall 0.6s at inside Jev's wait, before its request: guard={'passed': False, 'category': 'off_topic', ...} after 3.50s
  stall 0.4s at inside Jev's wait, before its request: guard={'passed': True, ...} after 3.31s
  ```
- The test that claims it (`tests/system_03_search_agent/guardrail/test_followup_guardrail.py:912`, `test_with_jev_a_stalled_loop_never_turns_jevs_admission_into_a_refusal`) stalls inside `resolve_jev_model`, the one place BEFORE the outer net is armed, so it passes; move the stall one call later and the same scenario refuses. The builder's "Not closed" section names the `_JEV_WAIT_S` edge, but the flag table and line 1's status both say closed.
- What a person would notice: under load (a stall of about half a second), "Tell me about the tree of life"-type questions Jev judges on topic are turned away as off topic, the FA03 symptom, at a lower stall threshold than FA03 measured (0.76 s).
- NOT FIXED

### F-72-J04: the rate-limit message can say "try again in about 1 seconds, not straight away"
- Severity: note (copy; the number is honest, the words are not)
- Where: `src/system_03_search_agent/core/graph.py` `_rate_limited_step_error` (`seconds = min(..., max(1, math.ceil(left_s)))`) with `_GUARDRAIL_RATE_LIMITED_WAIT_MESSAGE` ("Try the query again in about {seconds} seconds, not straight away.").
- What: whenever the provider's stated wait has already run out by the time the question ends (it fit, was waited, and the second request then failed; or the header was a past date or negative), the floor of 1 produces "about 1 seconds, not straight away": a plural on one, and a contradiction, since one second IS straight away for a person.
- Reproduction (`judge72/p5_rl.py`): request 1 is a 429 with `Retry-After: 2`, which fits and is honoured; request 2 hangs to the budget. After 15.00 s the person gets `'message': '... Try the query again in about 1 seconds, not straight away.', 'retry_after_s': 1`. Same words for `Retry-After: -5` and for a past HTTP date. Two requests only in every arm (limit held).
- What a person would notice: after a 15-second wait, an instruction that reads as broken. Using the no-number message when the wait left is under a few seconds would read right.
- NOT FIXED

### F-72-J05: R-10 line 4 holds for the classifier call only: a rate-limited guard model still gets 4 requests for a question the allowlist misses
- Severity: should-fix (the acceptance line is per QUESTION; the builder named the gap and marked FJ04 "closed, classifier call")
- Where: `src/system_03_search_agent/harness/decide.py:250` (`harness.call_tier("guard", messages)`, default `retry=True`) in `_run_guard_pick`, started beside the classifier by `core/graph.py:2126-2131` whenever `prefilter.clears_biomedical_allowlist` is false.
- Reproduction (`judge72/p6_rl_count.py`, default provider, every guard-model request a 429 with no Retry-After, real `guardrail_node`):
  ```
  'Which diseases are associated with BRCA1?' guard-model requests: 2 peak in flight 1 ...
  'Tell me about the tree of life.' guard-model requests: 4 peak in flight 2 ...
  ```
  The second request of the relevancy pick goes out at once, with no backoff and ignoring any Retry-After (it is `call_tier`'s immediate transient retry).
- Why it matters: the ledger's line is "A rate-limited guard model is sent at most two requests per question." That is true only when the allowlist admits. Any question phrased without a biomedical keyword doubles the load on a provider that is already refusing, which is FJ04's original complaint. The person sees the same "busy" message either way.
- NOT FIXED

### F-72-J06: no test pins "an unusable fast reply does not beat a usable slow one" once both requests are in flight
- Severity: should-fix (the code is right today; the control is unguarded, and it is the one that keeps a slow-spell search alive)
- Where: `src/system_03_search_agent/core/graph.py`, the unusable-reply arm of `_classify_within_budget` (`_log_guard_request(request, trace_id, "answered, unusable", upstream)` then `continue`, about `:1813`).
- Code is correct, by probe (`judge72/p8_unusable.py`, unmodified worktree): the hedge answers garbage at 4.5 s while request 1 answers admit at 8.0 s, `-> verdict is_injection=False at 8.00s sent 2`; and the mirror (request 1 garbage at 4.5 s after the hedge went out, hedge admits at 8.0 s), same result.
- Break-it: scratch edit adding `if len(requests) >= 2: break` after that log line, so an unusable reply ends the question while the other request is still running. Both guardrail test files: `112 passed in 99.45s`. No test went red. Restored, `git diff --quiet` clean.
- Why it matters: this is precisely the slow-spell case card 72 exists for. A later refactor that ends the loop on an unusable reply would turn "admitted at 8 s" back into "could not complete" at 4.5 s, and CI would stay green.
- NOT FIXED

### F-72-J07: the Jev signal's live path, raised WHILE the guardrail is already waiting, is untested
- Severity: should-fix (code right today, control unguarded; this is R-10 line 1's own mechanism)
- Where: `src/system_03_search_agent/core/graph.py:1985` (`said_so = asyncio.ensure_future(jev_failed.wait())`) in `_await_jev_own_pick`.
- What: every guardrail arm that exercises the signal uses the `_relevancy` stub (`test_followup_guardrail.py:793`), which sets `jev_failed` at the START of the decision, before the guardrail reaches its wait. `_await_jev_own_pick` then sees `jev_failed.is_set()` in its pre-check at `:1984` and never waits. In production the order is the reverse: the classifier answers off topic in about 1.5 s and Jev fails at its 3 s bound, so the event is raised mid-wait.
- Break-it: scratch edit making the wait ignore the event (`said_so = asyncio.ensure_future(asyncio.sleep(3600))`). Whole `tests/system_03_search_agent/guardrail/` directory: all green. Restored, `git diff --quiet` clean.
- Probe that does discriminate (`judge72/p9_midwait.py`, Jev mode, classifier off topic at 0.05 s, a `decide` stub that raises `jev_failed` 2.0 s in and returns the guard fallback 5.0 s later): unmodified code `refusal [...'off_topic'...] after 2.00s`; with the mutation `after 7.00s`. That 5-second difference is RJ03 coming back, and CI would not see it.
- What a person would notice if it regressed: an off-topic refusal that takes as long as the slowest guard fallback, up to the 15 s budget, instead of arriving when Jev fails.
- NOT FIXED

### F-72-J08: `retry=False` also removes the reasoning-refusal fallback, so a guard model that cannot turn reasoning off fails every question at the front door
- Severity: should-fix (latent: today's guard model accepts the block; the builder named it; recorded because the failure is total and silent in its words)
- Where: `src/system_03_search_agent/harness/harness.py:677-678` (`transient_retry_left = retry`, `reasoning_fallback_left = retry`), used by the classifier via `core/graph.py` `_send()` (`retry=False`).
- What: the reasoning fallback is not a second request for the same answer; it is the only way a reasoning-mandatory model can be called at all. The classifier now never takes it, and `_classify_within_budget` treats the 400 as non-transient and stops after one request. Every other caller of the same model still self-heals.
- Reproduction (`judge72/p12_reasoning.py`, guard model stub that answers 400 "Reasoning is mandatory for this endpoint and cannot be disabled." whenever the `reasoning` field is present):
  ```
  classifier with a reasoning-mandatory guard model -> {'step_error': {... 'error_class': 'recoverable', 'message': 'A step in this query could not complete as requested.', ...}} sent 1 in 0.05s
  call_tier default retry -> answered sent 2
  ```
- Why it matters: `GUARD_MODEL` is an environment variable. Setting it to such a model would turn every search into "could not complete as requested" in 50 ms, while Think, Plan and Write on the same model work, which points a debugger away from the cause. Keeping the reasoning fallback under `retry=False` (it is not a duplicate request, and it still keeps the classifier at two requests if counted) would close it. `test_retry_false_sends_exactly_one_request[a reasoning refusal]` pins the current behaviour as intended.
- NOT FIXED

### F-72-J09: an unusable Jev reply can carry a question past its per-query cap, because the pre-flight check prices Jev at the guard estimate and the charge is now always the one-cent ceiling
- Severity: note (pre-existing for a not-JSON body since R-07; R-10 makes it the rule for every unusable shape; bounded to about one cent per concurrent Jev call)
- Where: `src/system_03_search_agent/harness/decide.py:285` and `synthesis/sentence_check.py:359` (`check_per_query_cap(..., "guard")` before each Jev call) against `harness/jev_client.py` `_unusable_reply` (`billed_cost_usd=MAX_JEV_COST_USD`).
- Reproduction (`judge72/p13_cap.py`, `PER_QUERY_COST_CAP_USD=0.10`, running cost preset to $0.0965, guard pre-flight estimate printed as 0.003, Jev `_post` returning a garbage 200):
  ```
  before 0.0965, Jev unusable -> malformed_reply after 0.1065 cap 0.10
  two concurrent from 0.0965 -> 0.1165
  ```
- Why it matters: `production-standards` and pattern 4 treat the per-query cap as a hard ceiling. The overshoot is small (up to 1.65 cents on a 10-cent cap in the probe, from two Jev decisions the guardrail really does start together), and later calls are then refused, so it cannot run away. A Jev-specific pre-flight estimate of `MAX_JEV_COST_USD` would make the check match the charge. Recorded for the owner, not blocking.
- NOT FIXED

### F-72-J10: the hedge picks the FASTER of two classifier samples, so any link between reply length and verdict now leans the front door one way
- Severity: note, unsure (not demonstrable with stubs; recorded so the golden run is read with it in mind)
- Where: `src/system_03_search_agent/core/graph.py` `_classify_within_budget`, "whichever usable reply comes first decides".
- What: before card 72 each question got one classifier sample. On the 3 to 5 in 100 questions where the first request passes 4 s, it now gets the earlier of two. If an injection or off-topic verdict tends to come with a longer `reason` (more output tokens, a slower reply), the faster sample is more often the admission. Nothing in the change or its tests measures this; the builder's diagnosis measures latency, not verdict by latency.
- What would settle it: the per-request log line this change adds, joined to the verdict, over one golden run: are the requests that won a hedge race admitted at the same rate as single-request questions.
- NOT FIXED

### F-72-J11: `synthesis/sentence_check.py` still says an unusable Jev reply is "charged its reported cost"
- Severity: note (builder named it as outside the fence)
- Where: `src/system_03_search_agent/synthesis/sentence_check.py:352-353` (docstring) and `:369-370` (comment "its reported cost is charged"). Probe `judge72/p11_batch.py` shows the site now charges the ceiling: `sentence check usage null -> 'JevCallError' charged 0.01`. The words describe the pre-R-10 rule; the next reader of the third charge site is told the wrong amount.
- NOT FIXED

## What I verified with my own probes, and what I only read

All probe scripts are under the session scratchpad, `judge72/`. Every model and Jev reply is a stub; no live call, no deployed app. The worktree was restored after each scratch edit (`git diff --quiet` printed clean each time) and `git status --short` shows only this report.

Verified by probe, holding:
- Two requests at most, in flight and in total, for the classifier call, no path past the 15 s budget (scaled to 1.5 s), and never an admission without an admit reply: `p2_sweep.py`, every ordered pair of 33 request behaviours (admit, injection, unusable, connection error, 429 with and without Retry-After, 429 with a wait that does not fit, auth error, hang, at 4 delays), 1089 combinations: `combos 1089 problems 0`. The sweep is not vacuous: allowing a third request makes it report `combos 289 problems 90` (`p2_meta.py`).
- Charging in that same sweep: every request that answered is charged its token cost, every request cancelled is charged the guard tier's cancelled-call ceiling, errors nothing, exactly, in all 1089 combinations.
- An unusable fast reply never beats a usable slow one, either order (`p8_unusable.py`), but see F-72-J06 for the missing test.
- Node level, Jev on: two hung, unusable-then-hung, or rate-limited classifier requests give a step error even when Jev says on topic and not injection; a classifier injection verdict is kept whichever request carried it (`p14_node_jev.py`).
- The Jev signal: raised mid-wait, the refusal returns at 2.00 s instead of 7.00 s (`p9_midwait.py`); see F-72-J07 for the missing test and F-72-J03 for the clock that still decides.
- Every unusable Jev body shape I tried (usage null, answers a list, choice a dict, cost a boolean, top-level string, top-level null) is charged $0.01 at `_jev_injection_pick` and `decide` (`p10_sites.py`), and at the sentence check (`p11_batch.py`).
- The new per-request log line carries no key and no question text, strips a newline and control characters from the upstream host, and cuts it to 64 characters (`p7_logs.py`: `KEY in log: False`; the new lines printed in full above). The question marker did appear in the log, but only in the PRE-EXISTING "guard classification unusable ... starts %r" line, which echoes the model's reply (moved, not added, by this change).
- Retry-After: read from either request; a past date, a negative value and "nan" all handled without a third request (`p5_rl.py`).
- `ruff check .` all passed; `isort --check-only` exit 0; `tests/system_03_search_agent/harness` plus `test_sentence_check.py` 508 passed; both guardrail follow-up files 112 passed on the unmodified branch.

Break-it, my own scratch edits (all restored):
- Hedge never sent (4.0 to 16.0 s): 11 red. Loser never cancelled: 4 red. Hedge allowed while two are in flight: 15 red. `decide()` raising the signal after a Jev pick: 1 red. Upstream host not sanitised: 3 red. Reasoning fallback kept under `retry=False`: 1 red.
- An unusable reply ends the question while the other request runs: 0 red (F-72-J06). The wait ignores a signal raised mid-wait: 0 red across the whole guardrail directory (F-72-J07).

Only read, not independently probed:
- The full unit suite result (6599 passed) is the builder's; I ran the touched directories only.
- The Retry-After header locations inside real litellm exceptions (I used litellm's own `RateLimitError(headers=...)`, one of the three locations).
- The builder's latency figures from the diagnosis (11 of 150, 4 of 150, the 1.5 s median).

Line correction to F-72-J09: the Jev cap check in `decide.py` is at `:286`, not `:285`.

## Verdict: FIX FIRST

- F-72-J01 is blocking and sits INSIDE this change's own fix (card 72 option A, the hedge): a guard-model injection verdict that has already come back is discarded in favour of the other request's admission when both land in one loop pass, and the log calls the discarded reply cancelled. By the review loop's stop condition this escalates to the product owner rather than going into another round on its own.
- F-72-J03: FA03 is marked closed but reproduces at a 0.6 s stall one step later than the builder's test places it; line 1's "never" is not met.
- F-72-J02 and F-72-J05: R-10 lines 3 and 4 are met only under the builder's narrower readings (usable replies may be charged $0; the two-request limit covers the classifier call, not the question). Both named by the builder, both need the owner's reading.
- F-72-J06, J07, J08 should be fixed with the round; J04, J09, J10, J11 are notes.
