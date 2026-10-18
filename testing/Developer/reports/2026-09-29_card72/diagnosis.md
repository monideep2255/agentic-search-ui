# Card 72 diagnosis: the guardrail's model call times out twice

The symptom, in the user's words: about 3 searches in 100 end with "A step in this query hit a temporary error. Retrying the query may succeed." because the guardrail's model call did not answer in time, twice. This report finds the cause and lists the fixes. It changes no code. Written 2026-09-29 from the repository at develop `beaccf36`, the golden runs under `testing/Developer/reports/`, and develop's API log on Railway (read only). Paths are relative to `<repo-root>`.

## Table of contents

- [Summary](#summary)
- [1. Which model answers the guard classification call](#1-which-model-answers-the-guard-classification-call)
- [2. The guardrail's budget and how it is split](#2-the-guardrails-budget-and-how-it-is-split)
- [3. How often attempt 1 and both attempts time out](#3-how-often-attempt-1-and-both-attempts-time-out)
- [4. How long a successful guard call takes](#4-how-long-a-successful-guard-call-takes)
- [5. The cause, and what was ruled out](#5-the-cause-and-what-was-ruled-out)
- [6. Fix options and the recommendation](#6-fix-options-and-the-recommendation)
- [Method and limits](#method-and-limits)

## Summary

- Cause: the upstream that OpenRouter picks for `deepseek/deepseek-v4-flash` sometimes answers the guard classification slowly, in bursts. During a burst about 1 call in 13 takes more than 10 seconds. Our process was healthy all the while: Jev, called in parallel by the same guardrail through the same OpenRouter account, answered in 124 to 368 ms in every one of those slow runs.
- Why a slow call becomes a failed search: the guardrail gives the first attempt 10 of its 15 seconds and cancels it. The second attempt then has only 5 seconds, and in a burst that is sometimes not enough.
- Measured on 2026-09-29 (card 63's golden run, 150 searches):
  - 11 first attempts timed out (7.3%).
  - 4 of those also timed out on the second attempt (2.7%), which is the "about 3 in 100".
  - The other 7 second attempts answered in 0.6 to 3.0 seconds.
- Not a code change: nothing on the guard path changed between the clean runs of 2026-09-26 (0 timeouts in 300 searches) and 2026-09-29.
- Recommended fix: a hedged second request. If the first request has not answered by about 4 seconds, send a second one without cancelling the first, and use whichever valid reply arrives first, all inside the same 15 seconds.

## 1. Which model answers the guard classification call

The guard classification call and Jev's injection pick are two separate calls, running at the same time.

The guard classification call:

- It is made in `_guardrail_after_prefilter`, `src/system_03_search_agent/core/graph.py:1886` to `1901`, through `_dispatch_tier_call(harness, trace_id, "guard", "guardrail", ...)`.
- That goes to `Harness.call_tier("guard", ...)`, `src/system_03_search_agent/harness/harness.py:564`. It is a chat-completions call to `openrouter/<model_id>` through LiteLLM (`harness.py:627` to `639`), with `reasoning: {"effort": "none"}` (`harness.py:322`) and `max_tokens` 128 (`harness.py:373`).
- The model id comes from `GUARD_MODEL`, and when that is unset, from `_DEFAULT_MODELS["guard"] = "deepseek/deepseek-v4-flash"` (`src/system_03_search_agent/harness/tiers.py:53` to `54`).
- `docs/architecture/Model_architecture.md:50` and `:54` record that develop's guard tier is `deepseek/deepseek-v4-flash`, read from Railway on 2026-09-25. I did not re-read develop's variables, because listing them would print secrets. The deploy history since then shows only code deploys (reason "deploy", one per merge), which is consistent with no model change, though an edited variable does not always show there.
- The request carries no OpenRouter provider preference: no `provider`, `order` or `allow_fallbacks` field in `call_tier`'s request. So OpenRouter chooses the upstream host for each call.

Jev's injection pick:

- With `CLASSIFIER_PROVIDER=jev` on develop, `guardrail_node` starts `_jev_injection_pick` as its own task (`graph.py:1775` to `1778`). It runs beside the guard call, never in place of it.
- Jev is `typesafe/jev-1.13` on OpenRouter's `/api/alpha/decisions` endpoint (`tiers.py:72`, `harness/jev_client.py`), a different endpoint and model.
- When the guard call fails there is no verdict, and the guardrail fails closed, whatever Jev said (`graph.py:1949` to `1970`). This is deliberate: Jev can add an injection refusal but never remove one (`Model_architecture.md:64`, `:158`).

A third call runs only when a question does not clear the biomedical word list: the `guardrail.relevancy` decision, Jev first with the guard tier as fallback (`graph.py:1760` to `1766`). It is not what timed out: the log line names the classifier call, and all 7 timed-out runs that finished had skipped the relevancy decision (the 4 failures left no `done` event to say).

## 2. The guardrail's budget and how it is split

- Total: 15.0 seconds. `budget_for_step("guardrail", ...)` maps the step to the guard tier (`harness.py:436` to `441`), and `_TIER_STEP_BUDGET_S["guard"] = 15.0` (`harness.py:473` to `477`). The clock starts when `guardrail_node` begins (`_step_deadline`, `graph.py:1248` to `1258`, called at `graph.py:1706`), so the daily-cap database checks are counted in it too.
- Attempt 1: `_CLASSIFIER_FIRST_ATTEMPT_SHARE = 2 / 3` of what is left (`graph.py:1433`, applied at `graph.py:1888` to `1890`). With about 15 seconds left, that is about 10.0 seconds.
- Attempt 2: whatever is left, about 5.0 seconds. After a timeout the wait before it is 0.0 seconds: `_classifier_retry_wait_s` returns 0.0 for any `harness.enforce_timeout` source (`graph.py:1541` to `1542`). The log confirms it: "asking once more within the guardrail's budget after 0.0s".
- Each attempt's `enforce_timeout` wraps the whole `call_tier`, including `call_tier`'s own single transient retry (`graph.py:1856` to `1860`). A request that simply hangs gets no inner retry: it runs the attempt's budget out.
- `.claude/rules/tool-call-budgets.md` does not name the guardrail's budget.

That explains the 15.4 seconds in every failed run: about 10 seconds for attempt 1, about 5 for attempt 2, then the step error. The four failures on 2026-09-29 took 15.4, 15.4, 15.6 and 15.4 seconds (`runs.jsonl`, `seconds`).

## 3. How often attempt 1 and both attempts time out

### Where the counts come from

- The log line "guard classification call failed (attempt 1 of 2, ..., harness.enforce_timeout:guardrail, transient)" exists only since the re-land, R-01, merged as #116 (`c0bf50bd`) at 20:34 UTC on 2026-09-26. Before that the guardrail made a single attempt with the full 15 seconds, so a timeout left no line of its own. For those days the golden runs' failures are counted instead.
- Develop's API log goes back to 2026-09-25 05:39 UTC. Searches are counted as `POST /v1/query ... 202 Accepted` lines.
- The filter "guard classification" over the whole retained log (from 2026-09-20 on) returns 15 lines: 11 timeouts and 3 unusable replies on 2026-09-29, and 1 unusable reply on 2026-09-27.

### Per day

| Day (UTC) | Searches in the log | Attempt 1 timed out | Both attempts timed out | Unusable reply at attempt 1 | Code on the guard path |
|---|---|---|---|---|---|
| 2026-09-25 (from 05:39) | 313 | no log line yet | 1 of 150 in the 8.2 golden run (G-046, 15.4 s), 0 of 150 in 8.1 | not logged | single attempt, 15 s |
| 2026-09-26, before 20:34 | about 157 | no log line yet | 1 of 150 in the 8.6 golden run (G-005, 15.5 s) | not logged | single attempt, 15 s |
| 2026-09-26, from 20:34 | about 324 | 0 | 0 (re-land and follow-up golden runs, 300 searches) | 0 | two attempts, 10 s and 5 s |
| 2026-09-27 | 55 | 0 | 0 | 1 (a full 289-character reply that failed the schema) | the same |
| 2026-09-28 | 0 | 0 | 0 | 0 | the same |
| 2026-09-29 | 154 (150 of them the card 63 golden run) | 11 (7.1% of searches; 7.3% of the golden run) | 4 (2.6%; 2.7% of the golden run) | 3 (cut-off replies of 2, 9 and 60 characters) | the same |

### The 11 timeouts of 2026-09-29, matched to golden runs by trace id

| Trace (first 8) | Golden run | Outcome | Guardrail step took |
|---|---|---|---|
| b1fa5677 | G-006 run 1 | refused, no evidence | 10.62 s, recovered |
| 42c1c07e | G-027 run 1 | error | 15.4 s, both timed out |
| 8f10e06d | G-041 run 2 | error | 15.4 s, both timed out |
| de631602 | G-007 run 3 | answered | 10.88 s, recovered |
| 551dfd5e | G-016 run 3 | error | 15.6 s, both timed out |
| b938038d | G-024 run 3 | error | 15.4 s, both timed out |
| fe43703f | G-031 run 3 | answered | 11.56 s, recovered |
| b655a90f | G-033 run 3 | answered | 11.33 s, recovered |
| 6345a2b1 | G-030 run 3 | answered | 11.87 s, recovered |
| 09abda3a | G-032 run 3 | answered | 10.95 s, recovered |
| 7cffb3f2 | G-050 run 3 | answered | 12.99 s, recovered |

A sample line, quoted in part: `2026-09-29T16:10:29Z WARNI [system_03_search_agent.core.graph] guard classification call failed (attempt 1 of 2, trace 42c1c07e-..., harness.enforce_timeout:guardrail, transient); asking once more within the guardrail's budget after 0.0s`.

### Did it start or worsen on a date?

It worsened on 2026-09-29 and clustered in time:

- 8 of the 11 timeouts came in pass 3, between 16:22 and 16:31 UTC.
- The same window produced the three cut-off replies, a failure mode not seen on any other day.

It is not new, though. Slow bursts show on other days too:

- In the 8.6 golden run (2026-09-26 17:02), 34 of 149 guardrail steps took more than 4 seconds, against 8 and 4 in the two runs that evening. It ended one search under the old single 15-second attempt.
- On 2026-09-25, the 8.2 golden run lost one search the same way.

What was deployed or changed:

- The golden run tested `bae5d1bd`. Between the clean follow-up run (`15aae082`) and `bae5d1bd`, the only changes under `src/system_03_search_agent/guardrail/` and `src/system_03_search_agent/harness/` are comment wording ("repo" to "repository"), in `git diff 15aae082 bae5d1bd`.
- The `core/graph.py` changes in that range are card 63's, in the Act step (tool failure kinds), and card 58's cost accounting in `core/run.py`. Neither touches the guardrail.
- No `DECISIONS.md` row since 2026-09-25 changes the guard model, its provider or the guardrail's budget. The rows that touch models change the writer tier (2026-09-27, Opus 5.5, pending its bench) and the Jev seam (2026-09-25). The row for 2026-09-26 sets the product target that every answer arrives within 20 seconds (card 50).

## 4. How long a successful guard call takes

The latency is not logged per call (`LLMResponse.elapsed_s` goes to the operator-only `cost` event, which the golden runs do not record). I measured the guardrail step from each run's own server events instead: the `guard` event's time minus the run's start, where the start is the `done` event's time minus its `elapsed_ms`.

In the question-only runs, the step is the slower of the guard call and Jev's pick, and Jev's pick took a median of 136 to 161 ms, so the step time is effectively the guard call's time. The 8.1 and 8.2 runs are left out: their `elapsed_ms` gives negative values under this method.

| Golden run | Runs measured | Median | 90th percentile | 95th percentile | Worst | Over 4 s | Over 10 s |
|---|---|---|---|---|---|---|---|
| 8.6, 2026-09-26 17:02 | 149 | 1.53 s | 6.25 s | 7.66 s | 12.07 s | 34 | 1 |
| 8.6 re-land, 2026-09-26 20:38 | 150 | 1.41 s | 2.93 s | 4.56 s | 9.02 s | 8 | 0 |
| 8.6 follow-up, 2026-09-26 23:48 | 150 | 1.37 s | 2.85 s | 3.27 s | 8.23 s | 4 | 0 |
| card 63, 2026-09-29 16:07 | 145, plus 4 failures | 1.55 s | 6.16 s | 10.62 s | 12.99 s, or over 15 s for the 4 failures | 23 | 8, plus 4 failures |

Against the budget:

- The median, about 1.5 seconds, did not move. What moved is the tail.
- On a normal evening the worst call, 8 to 9 seconds, still fits the first attempt's 10 seconds.
- On 2026-09-29 the 95th percentile alone exceeded 10 seconds.
- When the first attempt was cut off, the second attempt usually answered fast. The 7 recoveries finished 0.6 to 3.0 seconds after the 10-second cut (10.62 to 12.99 s in total), which is inside normal latency.

## 5. The cause, and what was ruled out

The cause: the guard model's upstream on OpenRouter, reached for `deepseek/deepseek-v4-flash` with no provider pinned, has bursts of slow replies. In a burst a request can take more than 10 seconds while the next request answers in 1 to 3. The two-attempt split then turns part of those bursts into failed searches: the first attempt is cut at 10 seconds, and the second sometimes needs more than the 5 seconds left.

Candidate by candidate:

- The provider being slow: the cause.
  - Jev, called through the same OpenRouter account in the same guardrail at the same moment, answered in 124 to 368 ms in all 19 runs of 2026-09-29 whose guard step took more than 5 seconds.
  - In the same window the same model returned three replies cut off at 2, 9 and 60 characters, far short of the 128-token ceiling. That is a sign of a misbehaving upstream, not of our code. One possible reading is an upstream that ignores `effort: none` and spends the ceiling on reasoning. It is unconfirmed, because the upstream's name is not logged.
- Contention inside our process (a blocked event loop, or another question's work starving the call): ruled out.
  - A blocked loop would have delayed Jev's reply as much as the guard's, and it did not (above).
  - The golden runs always use two workers, the same on the clean evening of 2026-09-26 as on 2026-09-29.
  - Card 63's NCBI transport change uses `asyncio.sleep` and `httpx.AsyncClient` (`tools/ncbi_transport.py:1170`, `:1382`, `:1485`), so it cannot block the loop.
- A rate limit: ruled out.
  - Every failure's source is `harness.enforce_timeout:guardrail`, a hang. A 429 would surface from `harness.call_tier` and would take the `Retry-After` branch, which logs "rate-limited" (`graph.py:1912` to `1919`, the line at `1914`). No such line exists.
  - The golden run's `rate_limit_signals` total is 0.
- The budget being too small for a normal call: ruled out as the cause.
  - On a normal evening 0 of 300 first attempts passed 10 seconds, and the worst call took 9.02 seconds.
  - Raising the total would only buy time for abnormal calls, and it pushes against the 20-second answer target.
- The first-attempt share leaving the second attempt too little: a contributing factor, not the cause.
  - In a burst the 5-second second attempt rescued 7 of 11.
  - The design note at `graph.py:1414` to `1432` predicted 0.29% failures on the assumption that the two attempts' times are independent. They are not: 4 of 11 second attempts in one burst also took more than 5 seconds.
  - The split is also why a slow first request that might have answered at 11 or 12 seconds is thrown away, not waited for.
- A code or configuration change: ruled out. The guard path's code is unchanged since the clean runs (section 3), and no decision row changes the guard model or budget.

## 6. Fix options and the recommendation

None of these is implemented. Per the 2026-09-26 decision rows (F-8.6-FA03, R-10), the named guardrail flags land before anything else touches the guardrail, so whichever option is chosen follows R-10 or folds into it.

| Option | What the person typing a question notices | What it costs |
|---|---|---|
| A. Hedged request: if the guard call has not answered by about 4 s, send a second identical request without cancelling the first; the first usable reply wins; both stay inside the same 15 s | In a slow burst the search gets past the guardrail in about 4 to 7 s instead of 10 to 15 s, and far fewer searches end in the temporary-error message. On a normal day nothing changes | A second guard call on about 3 to 5% of questions on a normal evening, 15% in a burst like 2026-09-29. At the guard model's price, about 0.14 and 0.28 US dollars per million tokens, that is a fraction of a cent per hedged question. No new model, and no longer worst case. It is guardrail code under Review_rounds, with a golden run |
| B. Change the split: for example, 5 s for the first attempt and 10 s for the second | Slightly fewer failures in a burst, but more searches pay a retry | A retry on about 5% of normal questions (the over-5 s count was 4 to 7 of 150). It still cancels a first request that might have answered at 6 to 10 s, and it is strictly weaker than A |
| C. Raise the guardrail budget, for example to 20 s | Failures drop, but in a burst the person stares at a spinner for up to 20 s before anything happens, and the whole answer blows past the 20-second target (card 50) | No extra spend. The latency budget belongs to the product owner (`harness.py:473` to `477`), and this treats the symptom |
| D. Pin or steer the upstream: set OpenRouter provider preferences for the guard call, a known-fast host with fallbacks allowed, and log which upstream served each call | If the slow host is the cause, bursts stop reaching the person at all | Needs a measurement first, since the upstream's name is not logged today. The pinned host's price may differ. A provider change on a model call is the product owner's decision |
| E. Switch the guard tier to a different model | Depends on the model: possibly faster everywhere | A new classifier to re-measure against the injection payloads (F-4.7-A-01), a new price, and a bench. The largest change for a tail problem |
| F. Let Jev's "not injection" admit a question when the guard call fails twice | No temporary error at the guardrail | Rejected: it lets Jev remove a refusal, which the 2026-09-25 and 2026-09-26 decisions forbid, because Jev admitted forged chat transcripts that the classifier refused. It would trade safety for speed |

Recommendation: A, with D's logging alongside.

- From the user's chair, a search that answers is the goal. In a burst the hedge gets it past the guardrail in seconds rather than failing it at 15.
- The evidence says a fresh request usually answers fast: 7 of 11 second attempts took 0.6 to 3.0 seconds.
- A hedge also stops throwing away a slow first request that might still answer, and it keeps the 15-second ceiling and the 20-second target.
- Add a log of each guard call's elapsed time and the upstream OpenRouter reports, so the next burst can be tied to a host and D can be decided on data. Adding this log needs no decision from the product owner, because it changes no behaviour.

How to prove it: a golden run with 0 guardrail errors, plus a count of the "attempt 1 of 2" log lines against searches.

## Method and limits

- Golden data: `testing/Developer/reports/2026-09-2[5-9]_*golden/runs.jsonl` and each run's `raw/*.json` events. The guardrail's step time is derived from server timestamps, so it includes the daily-cap database checks. For the 12 of 145 runs that also asked the relevancy decision, it includes that decision too; the medians with and without them agree to 0.02 s.
- Logs: Railway `get-logs` on develop's API service, read only. The per-day search counts come from `POST /v1/query` lines. For 2026-09-26 the split before and after 20:34 is by hour, so it is approximate. Nothing was redeployed, restarted or set.
- Not verified: the live value of develop's `GUARD_MODEL`, which was not read, to avoid printing secrets; and which OpenRouter upstream served any call, which is not logged.
- The one error on 2026-09-29 that did not come from the guardrail, G-026 (`core.run.run`, 4.2 s), belongs to card 73, not this card.
