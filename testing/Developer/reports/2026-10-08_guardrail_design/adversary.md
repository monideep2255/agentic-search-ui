# Guardrail card 84 and 72: adversary round 1

Base: 55fdb1e3ca7b64690df6a407c5777d510d643b5f (fix/card84-72-guardrail tip), run in a separate local checkout. Findings are appended as found; none are fixed, triaged or closed here.

## Findings

### A-GR-01: The web app's "try again in about N seconds" words can never show, because the guardrail always sends a wait of 0

- Severity: major
- What: step 1 of the design promises "For a rate limit that named a wait: Try asking again in about 20 seconds". `useRunView.ts` builds those words from `retry_after_s`, but every guardrail error the backend emits carries `retry_after_s: 0`: `_step_error_kwargs` in `core/graph.py` (line 884) hard-codes it, and the unusable-verdict payload (line 2094) does too. The branch is dead code end to end; only the frontend unit test, which feeds a hand-made payload, ever reaches it.
- Reproduction: a guard error whose cause is a 429 with `Retry-After: 20` and 12 s left:
  `_classifier_retry_wait_s(e, 12.0)` -> `None` (the search ends at once), then `_step_error_kwargs("guardrail", e)` -> `{'fatal': True, 'scope': 'step', 'source': 'guardrail', 'error_class': 'transient', 'message': ..., 'retry_after_s': 0}`. The web app therefore renders "... not with your question. Try asking again." with no wait.
- What a person sees: a provider that just said "come back in 20 seconds" ends their search, and they are told to try again now; asking at once meets the same rate limit. The design's stated words for this case never appear. The test file `useRunView.retryAfter.test.ts` claims F-84-A01, A02, A09 and F-72-V05 closed on input production never sends.
- NOT FIXED
### A-GR-02: The wait words round 121 seconds up to 3 minutes and read a day as "about 1440 minutes"

- Severity: minor (reachable only if A-GR-01 is fixed, or by a non-guardrail path that later sends a wait with source "guardrail")
- What: `guardrailFailure` in `useRunView.ts` uses `Math.ceil(seconds / 60)` past 120 s, with no hours and no upper bound. F-84-A02 ("about 86400 seconds") is reworded, not fixed.
- Reproduction: the same function body evaluated in node: `121 -> about 3 minutes`, `150 -> about 3 minutes`, `86400 -> about 1440 minutes`, `31536000 -> about 525600 minutes`, `1000000000000 -> about 16666666667 minutes`. The contract field is `retry_after_s: int = Field(..., ge=0)` with no maximum.
- What a person sees: a 2 minute wait told as 3 minutes; a day-long wait as a four-digit minute count.
- NOT FIXED
### A-GR-03: A Jev reply stating a vanishingly small cost is charged that, so the "never $0" floor is bypassed by 1e-300

- Severity: minor (unsure whether the owner's "never $0" means a minimum or only a stand-in for $0)
- What: `jev_charge_usd` charges any stated cost above 0.0 as stated. A reply stating `1e-300` or `5e-324` is usable and charged that figure, which no cap can see, exactly the F-72-J02 blindness the floor was built to end. Only an exact 0 (or -0.0) is raised to the floor.
- Reproduction: `call_jev` with `_post` returning a 200 whose `usage.cost` is the given value (script in my scratchpad, real `jev_client`):
  `cost 0 -> USABLE cost_usd=0.0001`, `cost -0.0 -> USABLE cost_usd=0.0001`, `cost 1e-300 -> USABLE cost_usd=1e-300`, `cost 5e-324 -> USABLE cost_usd=5e-324`.
- What a person sees: nothing directly. A drift or units slip in the undocumented endpoint (it once reported 12.5 for $0.0000125, per the module) toward tiny figures makes every Jev call free to the per-query, per-user and $25 daily caps.
- NOT FIXED
### A-GR-04: Step 3c does not close F-84-J07: a key-shaped provider name is still logged whole

- Severity: minor (the design and the docstring claim F-84-J07 fixed; it is not)
- What: F-84-J07 was "the log line wrote up to 64 characters of whatever the upstream host put in its name field, a key-shaped string included". `provider_of` now keeps `[A-Za-z0-9. -]`, which is every character of a router key. Only control characters and punctuation are dropped.
- Reproduction: `provider_of(SimpleNamespace(provider=K))`, where K is the router's usual key prefix followed by "0123456789abcdef" three times (57 characters, built from pieces because this project's secret-scan hook rejects the literal), returns K unchanged, so the WARNING line carries `provider=` plus the whole key-shaped string.
- What a person sees: nothing. The deployment's log, read by the step 2 ranking script, still records any key-shaped text the upstream field carries; the design's "fixes F-84-J07 on develop" is untrue.
- NOT FIXED

### A-GR-05: The provider filter mangles names instead of rejecting them, so step 2's host ranking can be fed wrong or merged hosts

- Severity: minor
- What: `provider_of` deletes disallowed characters and logs what is left, rather than refusing a name that needed deleting. Different names collapse together and lookalikes become plausible other names; a forged "next line" survives as words on the same line.
- Reproduction (real `call_log.provider_of`):
  `'Fireworks\nWARNING forged line trace=abc ok' -> 'FireworksWARNING forged line traceabc ok'`; `'\x1b[31mRed\x1b[0m' -> '31mRed0m'`; `'Тogether'` (Cyrillic T) `-> 'ogether'`; fullwidth `'ＤｅｅｐＩｎｆｒａ' -> None` (logged as "unknown"); `'deepinfra/fp8' -> 'deepinfrafp8'`; `'Google AI Studio (Vertex)' -> 'Google AI Studio Vertex'`; `'  -- ..  ' -> '-- ..'`. A 10,000 character name took 72 microseconds and was capped at 64.
- Why it matters: the design picks attempt 1 and attempt 2's hosts "from a week of the #159 log lines". A mangled or merged name puts a slow host's calls under another host's name, or under "unknown", and the ranking sends attempt 2 to the wrong place. Spaces are kept, so a provider field can still append words such as `DeepInfra outcome ok` after `provider=` on the line.
- NOT FIXED
### A-GR-06: On a busy server, every hung Jev call now lasts about 5 to 7 seconds instead of 3, and past the "never more than budget plus 2 s" promise

- Severity: major (unsure how often the server is this busy; the design states step 3 costs no seconds)
- What: `wait_counting_free_time` does not count any look that came back more than 0.05 s late. A loop that is merely busy, not frozen (other questions' synchronous work in short chunks), makes almost every look late, so almost nothing is counted and the wait runs to the real-time cap. The cap itself is overshot, so the docstring's "never more than `budget_s` plus `JEV_STALL_ALLOWANCE_S` of real time" is false. This bound now sits under every Jev call: the injection pick, every `decide()` point (guardrail relevancy, Think and Plan decisions) and the sentence check's calls through `_send`.
- Reproduction: virtual clock, a coroutine that blocks the loop for `chunk` seconds then yields, forever; a Jev call that never answers, bound 3.0 s. Real-time length of the wait, new versus develop's `asyncio.wait_for(…, 3.0)`:
  `0.03s chunks: 3.69s vs 3.15s`; `0.06s chunks: 5.22s vs 3.30s`; `0.1s chunks: 5.40s vs 3.50s`; `0.15s chunks: 5.85s vs 3.75s`; `0.3s chunks: 6.30s vs 4.50s`; `0.6s chunks: 7.20s vs 6.00s`. (Probe: `test_hog` in my temporary probe file.)
- What a person sees: when the service is busy and Jev stalls, an off-topic refusal that waits on Jev's relevancy pick, and every Jev-decided point in Think and Plan, each takes about 2 s longer than on develop. Several such points in one question push it toward the 20 s answer rule, in the conditions where time is shortest.
- NOT FIXED
### A-GR-07: Past the stall allowance, a Jev reply that already arrived is thrown away, and the topic check then admits after 15 s; the design names this residual as a refusal

- Severity: minor (unsure: on the virtual clock develop reads these replies, but that may be the stub's timer order; on real sockets develop's 3 s clock probably loses them too)
- What: `wait_counting_free_time` checks its real-time cap before the reply that landed during the pause has been read, so after a pause of about 4.9 s or more both of Jev's guardrail calls raise `TimeoutError` with their answers in hand. The docstring says "A reply that has arrived always wins over the clock"; after a long pause it does not. The design's named residual says such a pause "still ends Jev's clock and refuses"; with the classifier admitting and the guard fallback slow, it admits instead, through the topic check's fail-open rule.
- Reproduction (my probe on the sweep's `run_case`, question "Tell me about the tree of life."): classifier admits at 0.3 s; Jev injection "injection" and Jev relevancy "off_topic", each answering at 0.2 s; a 5 s blocking pause as the injection request is sent; the guard fallback pick hangs. Develop (yardstick): `off_topic` at 5.00 s. New: `ok` (admitted) at 15.00 s. Band: with injection at 0.12 s and relevancy on topic, pauses of 3.0 to 4.85 s give develop `ok`, new `injection` (new is safer); from 4.9 s both give `ok`.
- What a person sees: after a long server freeze, a question both Jev checks rejected runs, after a 15 s wait.
- NOT FIXED
### A-GR-08: Every pause still costs Jev up to 0.1 s of its clock, so a Jev pick in the last tenth of its bound is still refused after a pause

- Severity: minor (Jev measured 0.12 to 0.37 s, so a reply near 3 s is rare; the design's promise is stated without this limit)
- What: a look that comes back late is counted as `ask_s + _STALL_SLACK_S`, 0.05 + 0.05 s, not as the 0.05 s asked. Each pause therefore spends up to 0.1 s of Jev's counted 3 s, and N pauses spend up to N x 0.05 s more than the time actually free. FA03's promise, "an on-topic question Jev admits is no longer refused because the server paused", holds only for picks more than about 0.1 s inside the bound.
- Reproduction (probe `test_slack`, classifier says off topic at 0.3 s, Jev relevancy on topic at the given time, pause as Jev's request is sent, guard fallback off topic):
  `Jev on_topic at 2.9s, pause 0.0s: develop ok | new ok`; `Jev on_topic at 2.9s, pause 0.2s: develop off_topic 3.30s | new off_topic 3.10s`; `Jev on_topic at 2.95s, pause 0.06s: develop off_topic 3.30s | new off_topic 3.00s`. At 2.85 s the pause no longer refuses (`new ok`).
- What a person sees: rarely, an on-topic question refused as off topic after a brief server pause, the FA03 shape at its edge.
- NOT FIXED
### A-GR-09: A backward step of the clock is subtracted from Jev's counted time, so the wait grows by the size of the step

- Severity: unsure (Python's `time.monotonic` is documented never to go backwards, so this needs a broken clock or a test double; filed because the brief asked)
- What: `counted += min(now - last, ask_s + _STALL_SLACK_S)` has no floor at 0, and the real-time cap is measured from the same clock, so a backward step both un-counts time and widens the cap.
- Reproduction (probe `test_backwards`, a hung Jev call under a 3.0 s bound, `jev_client.time.monotonic` stepping back once on its fifth reading): `jumps -0.5s once: ends after 3.50s`; `jumps -5.0s once: ends after 8.00s`; `jumps -100.0s once: ends after 103.00s` of loop time.
- What a person sees: only with a misbehaving clock: a guardrail or Think decision waiting on Jev for as long as the clock stepped back, until the step's own 15 s budget (which reads the same clock) is also stretched.
- NOT FIXED
### A-GR-10: A question the guard model's provider refuses on content now reads "not with your question. Try asking again"

- Severity: major (step 1's own change; wrong words on a refusal path)
- What: step 1 shows the guardrail words for every fatal error whose `source` is "guardrail", whatever its `error_class`. A provider content-policy refusal (`litellm.ContentPolicyViolationError`) or any 400 (`BadRequestError`) on the guard call is classed "recoverable", ends the guardrail at once with no second attempt, and is caused by the question's text. Develop told the person "Try asking again, or rephrase the question", which was right for this case; the branch tells them the problem was ours and to ask the same thing again, which fails the same way every time.
- Reproduction (probe `test_policy_words`, the real `guardrail_node` on the sweep's `run_case`, "Which diseases are associated with BRCA1?", the guard call raising each error):
  `policy -> {'fatal': True, 'scope': 'step', 'source': 'guardrail', 'error_class': 'recoverable', ...} requests {'classify': 1}`;
  `badreq -> {... 'source': 'guardrail', 'error_class': 'recoverable', ...} requests {'classify': 1}`;
  `refused` (401) `-> {... 'source': 'guardrail', 'error_class': 'unexpected', ...}`.
  `useRunView.ts` then renders, for all three: "We could not finish checking your question, so nothing was searched. This was a problem on our side, not with your question. Try asking again."
- What a person sees: a question the provider would not process is blamed on us, and they are told to repeat it unchanged; repeating it fails identically. With a 401 (our key revoked) every question fails, and "Try asking again" will never work. The design's words were written for two cases only (double timeout, two unreadable replies); the code applies them to every guardrail failure.
- NOT FIXED
### A-GR-11: INSIDE THIS PHASE'S FIX (step 3b): after a 3 to 4.5 s server pause, a question the guard model called off topic and Jev called injection is admitted; develop's real code refuses it

- Severity: major (needs a pause past the 2 s allowance, which the design names as a residual that "refuses"; here it admits, against develop, real code on both sides)
- What: one pause hits both of Jev's guardrail calls. Step 3b's free-time clock now reads Jev's relevancy "on_topic" (a fast reply) after the pause, which sets the guard model's off-topic verdict aside (R-03). Jev's injection call, a little slower, runs into the same clock's real-time cap (3 s + 2 s) and is thrown away, so the refusal it carried never happens. On develop both replies were lost to `asyncio.wait_for`, the guard's off-topic verdict stood, and the question was refused. The admitting signal survives the pause and the refusing signal does not.
- Reproduction: not the sweep's yardstick but develop's REAL code, `git archive origin/develop src` into my scratchpad, run through the same `run_case` (port=False) with the same probe, checked to import the exported tree (`has wait_counting_free_time: False`). Question "Tell me about the tree of life."; classifier replies off topic at 0.3 s; Jev relevancy "on_topic" at 0.2 s; Jev injection "injection" at 2.0 s; a 3.0 s blocking pause as Jev's relevancy request is sent; guard fallback pick off topic at 0.3 s.
  develop: `off_topic 3.300`; branch: `ok 5.000` (admitted).
  Smallest Jev injection latency that admits, per pause: `{3.0: 2.0, 3.5: 1.5, 4.0: 1.0, 4.5: 0.6}` seconds. Cases where develop refuses (off_topic) and the branch admits, out of 144 per pause: 9 at 3.0 s, 12 at 3.5 s, 15 at 4.0 s, 18 at 4.5 s. No such case at 2.2 s or 2.5 s, and none in my 18,000-case grid with pauses of 2 s or less.
- What a person sees: after a few seconds' server freeze, a question both checks rejected (one as off topic, one as an injection) is searched and answered. The sweep cannot see this: its relevancy grid pauses only 0, 0.6 and 1.0 s, and only as the relevancy request is sent.
- NOT FIXED
### A-GR-12: The sweep, the design's gate, never pauses near or past 2 s, never pauses during the injection call, and accepts "later by the pause" as holding

- Severity: major (a gate that could not have caught A-GR-11)
- What: `_relevancy_grid` in `test_guard_request_dominance.py` uses pauses `(0.0, 0.6, 1.0)` only, staged only as the relevancy request is sent; Jev's injection latency is fixed at 0.12 s; the classifier sweep with Jev on never pauses. So the 2 s allowance's edge, the residual past it, and a pause landing during the injection call or as a reply arrives are untested. The paused cases also pass when the branch answers later than develop by up to the pause, so a refusal or admission up to 2 s slower counts as held, against the design's "no seconds" for step 3.
- Reproduction: my own grid on the same `run_case`, 18,000 cases, pauses `0, 0.3, 0.6, 0.76, 1.0, 1.5, 1.9, 2.0, 2.2, 3.0` at five points (relevancy send, reply, mid-wait; injection send, reply), branch against develop's real exported code: with pauses of 2 s or less, `1925` cases the same verdict but later on the branch (largest: `ok 3.30s -> ok 5.22s`, classifier admits, Jev injection "not_injection" at 0.12 s, Jev relevancy hangs, a 2.0 s pause as the injection reply arrives), `174` off-topic refusals turned into injection refusals, `947` sooner. With pauses over 2 s, the admissions of A-GR-11 appear; the sweep's grid contains none of these shapes.
- What a person sees: nothing directly; the gate's green does not cover the timing the step changed.
- NOT FIXED
### A-GR-06 addendum: the same busy loop, measured on the whole guardrail node against develop's real code

- Reproduction (probe `test_hog_node`, run on the branch and on `git archive origin/develop src`, "Tell me about the tree of life.", a coroutine blocking the loop in chunks from the first Jev request on):
  - 0.06 s chunks, classifier off topic, Jev relevancy hangs, guard pick off topic: develop `off_topic at 3.90s`, branch `off_topic at 5.40s`.
  - 0.06 s chunks, classifier admits, Jev relevancy hangs, guard pick on topic: develop `ok at 4.32s`, branch `ok at 6.12s`.
  - 0.15 s chunks, the same two: develop `4.05s` and `5.70s`, branch `6.30s` and `7.65s`.
  - Faster on the branch when Jev answers or fails outright (http 500: develop `1.38s`, branch `0.54s` at 0.06 s chunks), as the design intends.
- NOT FIXED
### A-GR-13: The debugging guide and the module docstring still promise a 3-second total Jev timeout that "a caller may shorten but never lengthen"

- Severity: minor (documentation now false; misleads whoever debugs a slow Jev call)
- What: since step 3b, `_send` waits up to `timeout_s` of free time and up to `timeout_s + JEV_STALL_ALLOWANCE_S` (5 s) of real time, more under a busy loop (A-GR-06: 5.22 to 7.20 s measured). The rewritten `jev_client` row of `docs/build/Debugging_guide.md` still says "a 3-second total timeout a caller may shorten but never lengthen"; `jev_client.py` line 98 ("A 3-second TOTAL timeout on the whole call") and line 715 ("may shorten the 3-second total bound, never") say the same.
- Reproduction: `git diff origin/develop...HEAD -- docs/build/Debugging_guide.md` shows the row rewritten in this phase with that phrase kept; `test_hog` above shows a 3.0 s bound ending at 5.22 s with 0.06 s chunks.
- What a person sees: nothing; an engineer reading the guide during an incident would rule out Jev for a 5 s stall.
- NOT FIXED
### A-GR-14: A NaN timeout handed to `call_jev_batch` now waits forever, where develop gave up at once

- Severity: unsure (no current caller can pass NaN: the sentence check passes `min(JEV_TOTAL_TIMEOUT_S, budget_s)`, which returns 3.0 for a NaN budget; filed as a latent hang)
- What: `call_jev_batch` bounds with `min(timeout_s, _TIMEOUT_S)`, which returns NaN for a NaN `timeout_s` (argument order). `wait_counting_free_time` then never ends, since every comparison with NaN is false: `left_s <= _NONE_LEFT_S` and `real_left_s <= _NONE_LEFT_S` are never true, and `min(_LOOK_S, nan, nan)` is 0.05. Infinity behaves the same. Develop's `asyncio.wait_for(…, timeout=nan)` timed out immediately.
- Reproduction (real asyncio, a call that never answers, guarded by an outer 2 s `wait_for`): `budget nan: still waiting after 2.0s (outer guard fired)`; `budget inf: still waiting after 2.0s (outer guard fired)`; `wait_for(nan) timed out after 0.00s`; `min(float('nan'), 3.0)` -> `nan`.
- What a person sees: today nothing. If a future caller derives the timeout from arithmetic that can produce NaN, a sentence check on a hung Jev holds the answer until the step's outer budget, not 3 s.
- NOT FIXED

## Verdict

FAIL against "nothing develop answers is lost, no question admitted that develop refuses", on A-GR-11, which sits inside this phase's own step 3b change and so meets the review loop's stop condition. A-GR-10 is also inside this phase's step 1 change.

Verified by my own probes:

| Claim | How | Result |
|---|---|---|
| The classifier path is identical to develop | 25,765 cases (the sweep's 5,153 providers x 5 Jev injection behaviours: not_injection, injection fast, injection 2.9 s, http 500, hang), branch against develop's REAL exported `src` | 25,765 of 25,765 identical in verdict, time and requests |
| No admission or refusal swap with pauses of 2 s or less | 18,000 cases, 10 pause lengths at 5 points, branch against develop's real code | none, apart from off topic turning into an injection refusal (174) |
| Pauses past 2 s | the same grid and a 2,592-case grid | admissions develop refuses (A-GR-11) |
| Never past the 15 s budget | every case above | none past 15 s |
| Charges | 31 reply shapes through the real `call_jev` | floor, ceiling and error rules hold except A-GR-03 |
| The tests are not vacuous | 7 mutations, each restored | each caught by at least one test |

Read only, not probed: the frontend copy beyond evaluating its wait function in node (A-GR-02); `call_jev_batch`'s charge paths, which share the rule I probed through `call_jev`; the CLI and MCP renderers.
