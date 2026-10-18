# Card 72 and R-10: adversary round

Branch `fix/card72-r10-guardrail`, reviewed 2026-09-29. Stubs and fake clocks only. Findings are appended as they are established. Judge's F-72-J01 to J11 are not refiled.

## Findings

### F-72-A01: the web app never shows the new "try again in about N seconds" words; a rate-limited person is still told "Try asking again in a moment"
- Severity: major (a flag marked closed, FA02, whose user-visible promise does not reach the main surface)
- Where: backend `src/system_03_search_agent/core/graph.py:1597-1621` (`_rate_limited_step_error`) and `:865-876` (the two new messages); web app `frontend/src/hooks/useRunView.ts:1195-1204` (`FATAL_COPY`, keyed on `error_class` only) and `frontend/src/hooks/useAgentRun.ts:376` (`setError(\`run failed (${error_class})\`)`). No frontend file reads `retry_after_s` for a run (only `FeedbackSurface.tsx:228`, a different API).
- What: the builder's first "What a person notices" line and flag FA02 say the person "is told to try again in about the number of seconds the provider named". The backend does write those words, but the web app deliberately never renders `payload.message` (F-4.8-A-15, F-4.9-A-01) and maps every `transient` fatal error to one fixed sentence that says the opposite: try again in a moment.
- Reproduction, run, not read: `adv72/p1_rl_event.py` drives the real `guardrail_node` with every guard request a `litellm.RateLimitError` (Retry-After 20, then none), and builds the error event through the real `ErrorPayload`. Its exact payloads were then fed to the real `useRunView` hook with vitest (`adv72/fe/src/adv72_rl.test.tsx`, a scratch copy of this branch's `frontend/src`, node_modules linked from the main checkout):
  ```
  Retry-After 20: requests=1 after 0.05s
  BACKEND message: "The service that checks each question is busy right now. Try the query again in about 20 seconds, not straight away." retry_after_s: 20
  WEB UI failure : "This run could not be completed. Try asking again in a moment."
  BACKEND message: "The service that checks each question is busy right now. Wait a little before trying the query again." retry_after_s: 0
  WEB UI failure : "This run could not be completed. Try asking again in a moment."
  ```
- What a person would notice: in a rate-limit spell, the web app still says "Try asking again in a moment". They retry at once, meet the same limit, and each retry sends the rate-limited provider one or two more requests. The new words reach only a surface that prints `message` (REST, CLI, MCP, if they do). No test covers the message on any surface a person uses. The fix is a frontend branch on the guardrail's rate-limit shape, or a new closed field, which is outside this change's fence. Either way FA02 should not read "closed" until the web app changes.
- NOT FIXED

### F-72-A02: in a slow spell, a question the allowlist misses still waits the full 15 s, because the relevancy decision's guard request gets no hedge
- Severity: minor (no search is lost and nothing regresses against develop, but the change's headline "about 4 to 7 seconds instead of 15" is false for this class of question)
- Where: `src/system_03_search_agent/core/graph.py:2394-2396` (`_await_within_step(relevancy_task, step_deadline, ...)` waits to the step's end) with `src/system_03_search_agent/harness/decide.py:249-251` (`_run_guard_pick`: one `call_tier` request with a 15 s budget, no hedge). Reached whenever `prefilter.clears_biomedical_allowlist` is false and the relevancy pick comes from the guard model: with the guard provider always, with Jev whenever Jev fails.
- Reproduction (`adv72/p2_slow_spell.py`, real `guardrail_node`, real `decide()`, stubbed `litellm.acompletion`): a slow spell where the first classifier request and every other guard-model request hang, and a fresh classifier request (the hedge) answers admit 0.6 s after it is sent. Question "Why do naked mole rats live so long?" (misses the allowlist):
  ```
  jev, Jev healthy                         passed after 4.61s   requests [0.0, 4.0] ['classifier', 'classifier']
  jev, Jev relevancy fails (HTTP 500)      passed after 15.00s  requests [0.0, 0.05, 4.0] ['classifier', 'other', 'classifier']
  jev, Jev relevancy slow (Jev timeout)    passed after 15.00s  requests [0.0, 3.0, 4.0] ['classifier', 'other', 'classifier']
  guard provider (default)                 passed after 15.00s  requests [0.0, 0.0, 4.0] ['other', 'classifier', 'classifier']; decisions []
  ```
  The classifier's hedge admits at 4.6 s every time. The person still waits until 15.00 s for a relevancy decision that is then thrown away and read as "no pick", which fails open.
- What a person would notice: a question phrased without a biomedical keyword waits 15 seconds in exactly the slow spell card 72 is for, whenever Jev also fails or the guard provider is set. The builder's report does not name this class. Either the same hedge is needed on the relevancy guard request, or the claim should say "questions the allowlist admits".
- NOT FIXED

### F-72-A03: a drift in Jev's reply shape now costs each question about 500 times more than on develop, which can pause every person at develop's $25 system cap
- Severity: minor, unsure (the builder named the per-query side of this trade-off; the system-wide consequence and the size of the change against develop are not in the report)
- Where: `src/system_03_search_agent/harness/jev_client.py:239-270` (`_unusable_reply`, always `MAX_JEV_COST_USD`), reached from the parse arms at `:469-477` and the out-of-set arm at `:479-485`; charged at `core/graph.py:1936-1937` and `harness/decide.py:303-304`.
- Reproduction (`adv72/p3_jev_drift.py`, real `guardrail_node`, Jev on, Jev's `_post` returning a 200 that states a normal $0.00002 cost but is otherwise unusable; the same script run against this branch and against the main checkout on develop `d23674f4`):
  ```
  branch   probabilities null       passed=True guardrail cost $0.02004  (injection and relevancy: 'malformed_reply')
  branch   option outside the set   passed=True guardrail cost $0.02004  ('invalid_option' x2)
  develop  probabilities null       passed=True guardrail cost $0.00004  ('unexpected_error' x2)
  develop  option outside the set   passed=True guardrail cost $0.00008  ('invalid_option' x2)
  ```
  The question is answered the same way either way; only the charge moves.
- Why it matters: the loop asks Jev at seven points per question (`guardrail.relevancy`, `guardrail.injection`, `think.ask_back`, `think.recent_years`, `think.asks_features`, `plan.literature`, and the sentence check). Jev's endpoint is an undocumented alpha whose shape was pinned by hand, so a drift can hit every reply at once. Each question would then carry about $0.07 of charges no provider billed at that size, where develop charged about $0.0001. HANDOFF.md puts develop's `SYSTEM_DAILY_CAP_USD` at 25. At roughly $0.07 of drift charges plus the real model cost, the system cap stops every person's questions for the rest of the day after a few hundred questions, or after about five golden runs. Per question, $0.07 of the $0.10 cap leaves a synth pre-flight (estimate $0.025) and a repair call little room (`CC.check_per_query_cap`: plan and synth still allowed at $0.07 spent, by probe). This is the mirror of F-72-J02, and whether one cent is the right fixed charge is the owner's call. The point for the owner is that a Jev outage now spends the system's daily money, where before it spent almost none.
- NOT FIXED

### F-72-A04: a slow spell lasting 4 to 10 seconds now loses the search, where develop answered it at 10.6 s, because both requests are sent inside the spell
- Severity: major, INSIDE THIS CHANGE'S OWN FIX (card 72 option A, the hedge). Unsure only on how often live slow spells take this shape.
- Where: `src/system_03_search_agent/core/graph.py:1460` (`_CLASSIFIER_HEDGE_AFTER_S = 4.0`) with `:1467` (`_CLASSIFIER_MAX_REQUESTS = 2`) and `:1726-1759`: the only other request goes out at 4 s, and nothing is sent after it.
- What: the hedge assumes a slow request is slow on its own, so a fresh request sent 4 s later will probably land somewhere healthy. When the slowness is correlated in time, meaning the upstream host is stalled for a stretch and every request sent in that stretch hangs, the 4 s hedge lands inside the same stall. With the cap at two, no request is left for after it. Develop's R-01 split sent its second request at 10 s, after a stall shorter than 10 s had ended.
- Reproduction (`adv72/p4_burst.py`, real `guardrail_node`, stubbed `litellm.acompletion`: every request SENT during the first N seconds hangs, and every request sent later answers admit in 0.6 s; the same script against this branch and against develop `d23674f4` in the main checkout):
  ```
  branch   stall of  3.0s: passed=True after 4.60s, requests sent at [0.0, 4.0]
  branch   stall of  5.0s: step_error='A step in this query hit a temporary error. R' after 15.00s, requests sent at [0.0, 4.0]
  branch   stall of  8.0s: step_error='A step in this query hit a temporary error. R' after 15.00s, requests sent at [0.0, 4.0]
  branch   stall of 11.0s: step_error=... after 15.00s, requests sent at [0.0, 4.0]
  develop  stall of  3.0s: passed=True after 10.60s, requests sent at [0.0, 10.0]
  develop  stall of  5.0s: passed=True after 10.60s, requests sent at [0.0, 10.0]
  develop  stall of  8.0s: passed=True after 10.60s, requests sent at [0.0, 10.0]
  develop  stall of 11.0s: step_error=... after 15.00s, requests sent at [0.0, 10.0]
  ```
- Evidence the live shape may be time-correlated, read and not proven: in card 63's golden run (`testing/Developer/reports/2026-09-29_card63_golden/runs.jsonl`), the guardrail failures came from two workers 41 s apart (G-027 by worker A at 16:12:06, G-026 by worker B at 16:12:47), then three more within six minutes. That is what one stalled host looks like, not independent per-request luck. The builder's diagnosis (a fresh request "usually answered in 0.6 to 3.0 s") measured requests sent after the stall, which is the case the hedge wins either way.
- What a person would notice: in a stall of 4 to 10 seconds, the search that develop answered after about 11 seconds now fails at 15 with "A step in this query hit a temporary error". No test covers a time-correlated stall; every hedge test has request 2 answer quickly. The trade is real in both directions: short stalls get faster, 4 to 10 s stalls get lost. That trade is the owner's to make on data, which needs the per-request log line this change adds, joined by send time.
- NOT FIXED

### F-72-A05: the hedge goes out even with a fraction of a second left, and is charged a full cancelled call it could never have earned
- Severity: minor (inside this change's fix; rare, and only money and provider load, not an answer)
- Where: `src/system_03_search_agent/core/graph.py:1729-1731` (`hedge_due = ... and hedge_at < step_deadline`). The retry path keeps `_CLASSIFIER_MIN_SECOND_ATTEMPT_S` (3 s) for its second request (`:1585`). The hedge has no such floor.
- Reproduction (`adv72/p7_late_hedge.py`, real `_classify_within_budget`, every request hangs, called with 4.3 s and 4.9 s of the guardrail's budget left, as happens when the node's synchronous daily-cap checks run long before it):
  ```
  guard classification request 2 of 2 (trace t-f2db98): cut at the guardrail's budget after 0.30s
  budget left 4.3s: requests sent at [0.0, 4.0], cancelled [1, 2], charged $0.000512
  budget left 4.9s: requests sent at [0.0, 4.0], cancelled [1, 2], charged $0.000512
  ```
  The 0.3 s hedge is charged the same cancelled-call ceiling as a full request ($0.000256 at the probe's prices), and it adds one request to a provider that is already slow.
- What a person would notice: nothing on the answer. The operator sees a second request the design could not have used, and the question pays for it. Applying the same 3 s floor to the hedge would stop it.
- NOT FIXED

