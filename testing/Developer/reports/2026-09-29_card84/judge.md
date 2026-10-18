# Card 84 judge round, 2026-09-29

Judge, one round, of branch `fix/card84-r10-sound-parts` at b5a37cdd against `origin/develop`. Evidence only; closes nothing. Findings are appended as they are established.

## Findings

### Verified by my own probe: the sweep's develop yardstick is develop's real code

- Method: `git archive origin/develop src` (5c1f3ad5; no `src/` change since the branch point d9e05c4e) into the judge's scratch folder; my own runner (`judge84/record.py`) ran develop's REAL `guardrail_node` and REAL `_run_guard_pick` over the builder's own grid (`_classifier_grid()` at budgets 15 s and 12 s, `_pick_grid()`), then the builder's port and the branch's real code over the same grid, in separate processes, recording verdict, elapsed, request count, peak in flight, every send time and every outcome kind.
- Develop real vs the port: 10,306 of 10,306 and 280 of 280 identical in verdict, time, request count and send times ("differ 0").
- Develop real vs the branch, my own classification: classifier held 4,872 (same verdict, time, requests and send times, every case develop answered with no 429 met), rate-limited lost 630, later 210, same 216, different verdict 12; pick held 132, rate-limited lost 6, later 6, same 6. Zero cases with two requests in flight. Matches builder.md's "The sweep, rerun" exactly.
- Also counted, not in builder.md: 84 classifier cases and 2 pick cases where develop reached NO verdict and the branch does (all rate-limited): 28 admitted, 28 injection, 28 off topic. None is a refusal turned into an admission of the same reply.
- Both sweeps vary verdicts as well as timings: admit, injection, off topic (classifier) and on_topic, off_topic (pick) at 0.3, 6 and 12 s, plus time-switched providers.

### F-84-J01: with a guard model that cannot turn reasoning off, a non-rate-limit failure is answered later than develop and costs one more request
- Severity: major, unsure (it breaks the owner's "request for request and moment for moment" rule exactly, but only for a guard model that refuses `reasoning: {"effort": "none"}`, the case F-72-J08's fallback exists for; I did not establish whether develop's configured guard model is one)
- Where: `src/system_03_search_agent/harness/decide.py:318-322` and `:371-373` (each request is a fresh `call_tier(retry=False)`), `src/system_03_search_agent/harness/harness.py:684-686` and `:719-730` (the reasoning fallback is per `call_tier` call, "never remembered"). On develop the fallback and the transient resend share ONE `call_tier`, so the resend already goes without the block; on the branch the resend is a new `call_tier`, which sends the block again, is refused again, and only then asks.
- Reproduction: `judge84/reasoning_probe.py`, the real `guardrail_node` on the virtual clock, a stub that answers any request carrying `reasoning` with litellm `BadRequestError("Reasoning is mandatory for this endpoint and cannot be disabled")` after 0.05 s, and otherwise the listed sequence. Develop is `git archive origin/develop src`.
  - "503 then ok": develop `('ok', 0.4, ['refuse@0.00', '503@0.05', 'ok@0.10'])`; branch `('ok', 0.45, ['refuse@0.00', '503@0.05', 'refuse@0.10', 'ok@0.15'])`.
  - "503,503,ok": develop `('ok', 2.5, [... 5 requests])`; branch `('ok', 2.55, [... 6 requests])`.
  - "429,429,ok": develop admits at 2.5 s; branch ends at 0.2 s with the rate-limit message after FOUR HTTP requests to the rate-limiting provider (`refuse, 429, refuse, 429`), two of them the refused block.
- Why it matters: every non-rate-limit failure on such a model reaches its verdict one refusal round trip later than develop, and the builder's sweep cannot see it because its stub ignores the `reasoning` field (`test_guard_request_dominance.py` `_Stub.__call__`). With a slow refusal and a slow answer near the 15 s budget this can turn into a lost question. A person using such a guard model waits longer for every screening that met an error.
- NOT FIXED

### F-84-J02: a second 429 that names no wait tells the person to try again straight away, from the first 429's stale wait
- Severity: minor
- Where: `src/system_03_search_agent/harness/decide.py:498` keeps `stated_until` from an earlier request when a later 429 names no wait, `:574` turns the passed wait into `rate_limit_wait_s` 0.0, and `src/system_03_search_agent/core/graph.py:1479-1480` then picks `_GUARDRAIL_RATE_LIMITED_WAIT_PASSED_MESSAGE` ("was busy a moment ago. Try the query again.").
- Reproduction: `judge84/rl_probe.py`, the real `guardrail_node` on the virtual clock, the builder's own `_Stub`. Provider: request 1 a 429 with `Retry-After: 5`, request 2 a 429 with no `Retry-After`. Output: `(None, 5.1, [0.0, 5.05], 'The service that checks each question was busy a moment ago. Try the query again.', 0)`. The provider rate-limited the question 0.05 s before this message, and named no wait.
- Why it matters: builder.md line 5 and F-72-V05 say a rate limit that names no wait reads "Wait a little before trying the query again", never "try again now". Here the person is told the service "was busy a moment ago" while it is still refusing, so an immediate retry is likely to be rate-limited again. The web app shows the same `retry_after_s: 0` as a plain transient line. Only the combination "wait stated, waited out, then a bare 429" reaches it.
- NOT FIXED

### F-84-J03: a guard call rate-limited on its third or fourth request has sent three or four requests, so "at most two" holds only as "none after the second"
- Severity: unsure (a reading of the owner's words, not a malfunction; no two-request policy can know in advance that request 3 will meet a 429 without breaking the "develop's retries exactly" rule)
- Where: `src/system_03_search_agent/harness/decide.py:509` stops only requests AFTER a 429; the sweep's own check (`test_guard_request_dominance.py`, `_sweep`, `new.requests > max(GUARD_RATE_LIMITED_MAX_REQUESTS, first_429)`) accepts any count up to the request that met the first 429.
- Reproduction: `judge84/rl_probe.py`, provider 503, 503, 503, then 429 with `Retry-After: 5`: `(None, 2.2, [0.0, 0.05, 2.1, 2.15], '... Try the query again in about 5 seconds, not straight away.', 5)`, four requests in a call that ended rate-limited.
- Why it matters: the owner's rule reads "a rate-limited guard call gets at most two requests". builder.md's "Acceptance line 1, corrected" states the implemented rule precisely ("no further request goes unless it is the second in all"), but `GuardCall`'s docstring and the debugging guide should not be read as a hard two-request ceiling for every call that met a 429. The lead may want the owner to confirm this reading.
- NOT FIXED

### F-84-J04: an unusable Jev reply that states a sensible cost is charged the floor, not the cost it states, against the owner's words
- Severity: minor
- Where: `src/system_03_search_agent/harness/jev_client.py` `_unusable_reply` (`billed_cost_usd=JEV_FLOOR_COST_USD` for every unusable 200 reply, whatever it states) versus `jev_charge_usd`, which is applied only to a USABLE reply.
- Reproduction: `judge84/cost_probe.py`, the real `decide()` with `CLASSIFIER_PROVIDER=jev`, `jev_client._post` stubbed, the guard pick stubbed to None, cost charged by the real `Harness`:
  - `usable, states 0.00002 -> ('jev', None, 2e-05)`
  - `invalid option, states 0.00002 -> ('guard', 'no_usable_pick:invalid_option', 0.0001)`
- Why it matters: `DECISIONS.md` 2026-09-29 (the owner's row) reads "A Jev reply that reached the provider is charged the cost it states when that is above $0 and at most `MAX_JEV_COST_USD`, otherwise a floor ... about $0.0001". It does not distinguish usable from unusable replies. The branch charges an unusable reply five times what it states. The money is tiny ($0.00008 per such reply) and errs toward stopping, so nobody using the product notices; it is filed because the brief's cost line is the owner's rule verbatim and the code implements a stricter one (`test_jev_followup_costs.py`'s module docstring states the stricter rule as if it were the decision). The lead or owner should confirm which is meant.
- NOT FIXED

### F-84-J05: the Jev pre-flight now holds the full $0.01 ceiling for a call that costs about $0.00002, so from about $0.09 of a $0.10 question every Jev decision goes to the dearer guard tier and the sentence check approves nothing
- Severity: minor, unsure of reach (I did not measure how many questions reach $0.09)
- Where: `src/system_03_search_agent/harness/decide.py` `check_jev_per_query_cap` (`if current + reserved + MAX_JEV_COST_USD > cap`), used by `jev_charge_reserved` at all three Jev sites. Develop checked the guard tier's $0.003 estimate only.
- Reproduction: `judge84/cost_probe.py`, cap $0.10, a question already at $0.0905, Jev stubbed to answer usably: `('guard', 'no_usable_pick:cost_cap', 0.0)`, so the decision went to the guard tier, whose own pre-flight ($0.0905 + $0.003) lets it run. At $0.0895 Jev runs: `('jev', None, 0.01)`. On develop, Jev ran at both starting costs.
- Why it matters: it is the price of the owner's "no charge takes a question past its cap", which the branch does meet for Jev-against-Jev (see the verified section). But near the cap it swaps a $0.00002 Jev call for a guard call costing tens of times more, and in the Write step's sentence check a capped Jev call approves no reworded sentence, so an answer near its cap can lose sentences develop kept. Nobody at $0.09 was asked about it; builder.md does not name this trade.
- NOT FIXED

### F-84-J06: a Jev charge can still take a question past its per-query cap when a guard-tier call is charged while the Jev call is in flight
- Severity: minor (named by the builder in "Not closed"; not a regression, develop has no reservation at all; unsure how often a guard or plan call overlaps a Jev call near the cap in the real loop)
- Where: `src/system_03_search_agent/harness/decide.py:529` (`ask_guard_model`'s `cost_control.check_per_query_cap(harness, trace_id, "guard")`) and `cost_control.check_per_query_cap` do not count `_JEV_RESERVED`; only Jev's own pre-flight (`decide.py:677`) does.
- Reproduction: `judge84/cap_probe.py`, cap $0.10, a real `Harness` at $0.089. Started together: the real `decide()` in Jev mode (Jev stubbed to answer usably after 0.2 s, stating $0.01) and the real `ask_guard_model` (litellm stubbed to a reply costing $0.005). Output: `guard answered True jev jev final cost 0.104 cap 0.10`.
- Why it matters: the owner's line is "no charge takes a question past its cap". The Jev pre-flight saw $0.099 and let the call through; the guard call's pre-flight saw $0.092 and let it through; the Jev charge then landed at $0.104. The overrun is bounded by one guard or plan call's cost and needs Jev to state near its $0.01 ceiling (its real price is about $0.00002), so a person would almost never notice; it is filed because the cost line in the brief is absolute.
- NOT FIXED

### Verified by my own probe: the guard-call log line carries no key, token, question or prompt of ours
- `judge84/log_probe.py`, the real `guardrail_node`, a question carrying a marker word, provider errors whose own text carries the question and a fake key-shaped token: the one "guard call" line reads `guard call guard classification (trace t-...): rate limited after 0.10s in all, 2 requests; request 1: failed, transient (ServiceUnavailableError) after 0.05s; request 2: rate limited after 0.05s`. Token in logs: False; question in logs: False. The provider's error text never reaches the line (`_failure_words` names the class only).

### F-84-J07: the guard-call log line writes up to 64 characters of the provider's own `provider` field verbatim, so whatever text the upstream puts there reaches the log
- Severity: unsure (low: our key and the question never go there; only the upstream's own reply field does)
- Where: `src/system_03_search_agent/harness/harness.py` `_upstream_provider` and `src/system_03_search_agent/harness/decide.py` `_clean_upstream`: printable characters kept, cut to 64, no allow-list of host-name characters.
- Reproduction: `judge84/log_probe2.py`, the same probe with a reply whose `provider` is `"Deep\nInfra\x1b[31m " + <fake key-shaped token> + " " + "x"*100`. The log line ends `upstream DeepInfra[31m sk-or-v1-<fake> xxxxxxxxxxxxxxxx` (token redacted here by me): the newline and the escape byte are dropped, the rest, key-shaped token included, is written.
- Why it matters: the brief's secrets line says the new log lines carry no key or token. Ours never do; but this field is untrusted external text (ai-security-standards: retrieved content is data), and a host name needs only letters, digits, dots, hyphens and spaces. An allow-list would make the line provably clean whatever the upstream sends. Nobody using the product sees it; an operator reading logs could.
- NOT FIXED

## Stopped

The lead stopped this round on 2026-09-29, unfinished, when the product owner chose to stop card 84 after the adversary round (`DECISIONS.md`). Findings above were written before the stop; no verdict was reached.
