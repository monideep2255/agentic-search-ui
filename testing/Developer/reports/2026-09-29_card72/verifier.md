# Card 72 and R-10: fresh verifier report

Fresh verifier, 2026-09-29. Branch `fix/card72-r10-guardrail`, stubs and fake clocks only. Verdicts are appended the moment each is established.

## Verdicts on judge and adversary findings

- F-72-J01: FIXED, with a bound (see F-72-V01). Own probe `ver72/p1_order.py`, real `guardrail_node` on the virtual clock, every ordered pair of {admit, injection, off topic, unusable} for request 1 and the hedge (sent at 10.0 s), 7 timing modes, 112 cases: every case where both replies end in the same pass, or one to three passes apart, refuses when either reply refuses (e.g. `A I same -> injection`, `I A r1hops3 -> injection`, `O A same -> off_topic`). The only 4 admissions with a refusal among the two replies are the ones where the admission arrived 1 ms earlier and the refusal was still in flight (`A I r2+1ms -> ok, cancelled [2]`), which is J10's first-reply-decides residual, as fix.md names it.

## New findings

### F-72-V01: "a refusal in hand always wins, whatever order or tick" holds only while the refusal's task finishes within four event-loop passes of the admission's
- Severity: minor, unsure (how many passes a real litellm and httpx reply takes between its bytes arriving and `call_tier` returning was not measured; stubs only)
- What: `ask_guard_model` reads every request whose task is DONE when it wakes, then cancels the rest. A refusal reply that reached the process at the same instant as the admission, but whose task needs five or more further loop passes to return (response parsing, logging callbacks, the harness's own awaits), is cancelled and the admission decides. The committed test `test_two_replies_in_hand_the_refusal_wins` covers the same tick and one tick apart only.
- Reproduction: `ver72/p1b_hops.py`, real `guardrail_node`, virtual clock. Both stubbed replies arrive at 11.000 s, and the injection one then awaits `asyncio.sleep(0)` k times. Output: `r1=A r2=I ... takes 4 extra loop passes -> injection, cancelled []` and `... takes 5 extra loop passes -> ok, cancelled [2]`. Mirror: `r1=I r2=A ... 5 -> injection`, `... 6 -> ok, cancelled [1]`.
- Why it matters: this is the J01 shape (both replies land during one stall) with a small, realistic skew between the two call chains. The person asking notices nothing, and a question one classifier sample called injection is answered. Likely rare, because both chains run the same code. Recorded so the claim's words match its reach. A fix would give any request still running a few passes, or a few milliseconds, once the first usable reply is read.
- NOT FIXED

## Verdicts, continued

- F-72-J02: FIXED to the owner's decision of 2026-09-29. Judge's `p3_jev_cost.py` re-run on HEAD: `injection pick, stated cost 0 -> ... charged 0.0001`, `stated cost 0.01 -> charged 0.01`, `decide relevancy stated 0 -> jev on_topic charged 0.0001`. A stated `1e-12` is still charged `1e-12`, which is what the decision's words ("above $0") allow. For replies with a status other than 200, see F-72-V03.
- F-72-A03: FIXED. Adversary's `p3_jev_drift.py` re-run on HEAD: `probabilities null ... guardrail cost $0.00024`, `option outside the set ... $0.00024`, down from $0.02004 on the pre-fix branch. That is the $0.0001 floor twice plus two guard requests, against $0.00004 to $0.00008 on develop. Judge's `p10_sites.py`: every unusable shape is charged `0.0001` at both the injection pick and `decide`, and `p11_batch.py` gives the same `0.0001` at the sentence check.
- F-72-J09: FIXED for one Jev call at a time at `decide` and at the injection pick. Judge's `p13_cap.py`: `before 0.0965, Jev unusable -> cost_cap after 0.0965`. OPEN AS NAMED at the sentence check, and correctly described: own probe `ver72/p3_cap.py` gives `sentence check from 0.0965, usable batch stating $0.009 -> final $0.105500 (cap 0.10)`. The most it can pass the cap by is $0.007, as fix.md says. NOT covered: two Jev calls whose pre-flights both run before either is charged (F-72-V02).
- F-72-J11: FIXED. `sentence_check._ask_jev`'s docstring and comment now describe the floor, read at `synthesis/sentence_check.py` lines 350 to 357 and 372 to 374.

### F-72-V02: two Jev calls pre-flighted together can still take a question past its per-query cap
- Severity: minor (theoretical at today's prices, because the guardrail and Think run early when a question's cost is low; the named test claims more than this)
- What: `check_jev_per_query_cap` compares the running cost plus one `MAX_JEV_COST_USD` with the cap. The guardrail starts its Jev injection pick and its Jev relevancy decision at the same moment, and Think starts several decisions together. Every pre-flight passes before any of those calls is charged, so N concurrent calls can add up to N times $0.01 on top of a running cost that left room for only one. fix.md says "no Jev charge takes the question past its cap", and a test is named `test_no_jev_charge_takes_a_question_past_its_cap`.
- Reproduction: `ver72/p3_cap.py`, real `guardrail_node`, Jev on, cap $0.10, the question "Tell me about the tree of life." (the allowlist misses it, so both Jev calls run), and both Jev replies usable and stating $0.009. Output: `running cost 0.085 ... -> final $0.103020 (cap $0.10) OVER CAP` and `running cost 0.089 ... -> final $0.107020 (cap $0.10) OVER CAP`. At 0.080 the final is $0.098020, under the cap.
- Why it matters: the cap is meant to be a hard ceiling (production-standards, pattern 4). The overshoot is bounded at about one cent per concurrent Jev call, and nobody using the product notices. It matters only because a claim of "never" is on record.
- NOT FIXED

### F-72-V03: a Jev reply with a status other than 200 reached the provider and is charged $0
- Severity: unsure (turns on how the owner's decision reads; fix.md names only the timeout as a $0 case)
- What: `jev_client._send` raises `JevCallError(reason="http_error")` with `billed_cost_usd=0.0` for any status other than 200, and every charge site then charges nothing. The owner's decision says that a Jev reply that reached the provider is charged the stated cost or the floor, "never $0". A 500, a 429 or a 402 is a reply from the provider. `JevCallError`'s docstring states this exclusion. fix.md's "Open, and why" names only "A Jev call that times out is still charged $0", and the newest debugging-guide line (75d4f60b) says "a reply that reached the provider is never charged $0".
- Reproduction: `ver72/p4_non200.py`, with `jev_client._post` stubbed to return each status. Output: `Jev HTTP 500: ('http_error', 0.0, 'http_error', 0.0)`, `Jev HTTP 429: (... 0.0 ...)`, `Jev HTTP 402: (... 0.0 ...)`, against `Jev HTTP 200: ('malformed_reply', 0.0001, 'malformed_reply', 0.0001)`, at both `_jev_injection_pick` and `decide`'s `_jev_attempt`.
- Why it matters: probably nothing is billed for an error status. But the decision's words and the documentation say "never $0" and the code says otherwise, so the owner should either confirm the reading or have the floor applied. A person sees nothing.
- NOT FIXED

### F-72-V04: the newest debugging-guide line (75d4f60b) says an unusable Jev reply is charged its stated cost, but the code charges the floor
- Severity: minor (documentation inside this phase's last commit)
- What: `docs/build/Debugging_guide.md` line 328 says that an unusable reply "carries a charge ... the cost the reply states when it is above $0 and at most `MAX_JEV_COST_USD`, otherwise the floor". `jev_client._unusable_reply` always sets `billed_cost_usd=JEV_FLOOR_COST_USD`, and its own docstring says "never the reported figure". Only a USABLE reply is charged its stated cost. The same line's "never charged $0" is contradicted by F-72-V03.
- Reproduction: the adversary's `p3_jev_drift.py` on HEAD. A reply stating $0.00002 with `probabilities: null` is charged $0.0001, since the guardrail cost is $0.00024 = 2 x 0.0001 + 2 x 0.00002 of guard requests. Judge's `p10_sites.py`: every unusable shape is charged `0.0001`.
- Why it matters: this is the file a debugger opens when a question's cost looks wrong, and it gives the wrong rule for the one case R-10 changed.
- NOT FIXED
- F-72-J03: FIXED, up to the named 2-second stall allowance. Note first that the judge's `p4_fa03.py` is vacuous on HEAD: its stall hooks `check_per_query_cap` when called from `_run_jev_pick`, which now calls it through `check_jev_per_query_cap`, so the 0.8, 0.6 and 0.4 s arms never stall (`after 3.01s / 2.90s / 2.91s`, the bare Jev time). Own probe `ver72/p5_stall.py`: real `guardrail_node`, real `decide()`, real `jev_client` with `_post` stubbed to answer on_topic 2.9 s after its request, the classifier saying off topic, and one blocking stall in each of five places (`resolve_jev_model`, `check_jev_per_query_cap`, `_post` before its request, `_post` after the reply arrived, and a 2.0 s reply). Stalls of 0.6, 1.0 and 1.9 s at every place: `passed=True ok ... ('guardrail.relevancy', 'jev', 'on_topic', None)`. A 2.4 s stall before the request: `passed=False off_topic after 5.00s`, which is `JEV_STALL_ALLOWANCE_S` doing what fix.md says it does. The same 2.4 s after the reply arrived: admitted, because a reply in hand wins.
- F-72-J04: FIXED as named. Own probe `ver72/p6_rlmsg.py` on `_rate_limited_step_error`: a wait of 1 gives `about 1 second, not straight away.`; `inf` and `nan` give `Wait a little before trying the query again.` with `0` and no exception; 20 gives `about 20 seconds`. Residual, as a note: a stated wait that has already run out (2 s read 5 s ago, or a stated 0) still gives "about 1 second, not straight away", the contradiction the judge's second sentence named. The web app never shows this text (next line).
- F-72-A01: FIXED for a stated wait; the no-wait case still reads as before (F-72-V05). Own vitest probe on a scratch copy of this branch's `frontend/src` (`ver72/fe/src/ver72_wait.test.tsx`), using the real `useRunView`: `N=1 -> "...Try asking again in about 1 second."`, `N=2 -> "...about 2 seconds."`, `N=20 -> "...about 20 seconds."`, `N=0.2 -> "...about 1 second."`, and `N=0`, `N missing`, `N null` and `N=-3` all give `"...Try asking again in a moment."`. No event-contract change: `contracts/events.py` and `frontend/src/lib/events.ts` are not in `git diff origin/develop...HEAD`, and `retry_after_s` stays `int, ge=0`. The only backend producer of a non-zero `retry_after_s` on a run event is `_rate_limited_step_error` (grep of `src/`), so no other error's words change today.
- Frontend exit run, in the worktree with `frontend/node_modules` linked to the main checkout's for the run only and unlinked after (`ls: node_modules: No such file or directory` before and after): `npx vitest run src/hooks/useRunView.retryAfter.test.ts src/hooks/useRunView` gave `Test Files  7 passed (7)` and `Tests  37 passed (37)`.

### F-72-V05: the web app's wait wording keeps "in a moment" for a rate limit that named no wait, and reads a raw count of seconds for a long one
- Severity: minor (wording; A01's second reproduction line still reproduces)
- What: the adversary's A01 reproduction had two lines: `retry_after_s: 20` and `retry_after_s: 0`. The fix changes only the first. A guardrail rate limit whose provider named no wait (backend message "Wait a little before trying the query again.") still reads in the web app as "Try asking again in a moment.", the words A01 said send the person straight back into the limit. The committed test pins that as intended ("keeps the class's own words when no wait was named"). Also, a long stated wait reads as a raw count: `N=86400 -> "...about 86400 seconds."` (the backend caps at 86,400; a Retry-After of 3600 would read "about 3600 seconds"). And the branch ignores `error_class`, so a `cancelled` error carrying a wait would read "could not be completed ... about 20 seconds". No producer sends that today.
- Reproduction: `ver72/fe/src/ver72_wait.test.tsx`, real `useRunView`: `N=0 -> "This run could not be completed. Try asking again in a moment."`, `N=86400 -> "This run could not be completed. Try asking again in about 86400 seconds."`, `N=20 cancelled -> "This run could not be completed. Try asking again in about 20 seconds."`.
- Why it matters: for a rate-limited question with no stated wait, the person still sees "in a moment" and retries at once. Unsure whether the owner wants a distinct "wait a little" line there. Minutes or hours would read better than thousands of seconds.
- NOT FIXED
- F-72-A02: FIXED. Own probe `ver72/p9_burst.py`, real `guardrail_node` on the virtual clock, run on branch code and on develop's code (the main checkout's `src`, `d23674f4`): every guard request sent inside an N-second spell hangs, and later ones answer in 0.6 s. "Why do naked mole rats live so long?" (the allowlist misses it), with the guard provider and with Jev failing on HTTP 500. Branch: spells of 3, 5, 8 and 9.9 s give `passed after 10.60s sends [('cls', 0.0), ('pick', 0.0), ('cls', 10.0), ('pick', 10.0)]`. Develop: `passed after 15.00s`. An 11 s spell is a step error on both.
- F-72-J05: FIXED per guard call. OPEN AS NAMED per question, and correctly described. Own probe `ver72/p7_storm.py`, every guard request a 429, both providers. A question the allowlist admits: classifier sends `[0.0, 2.15]`, pick none, peak 1. "Tell me about the tree of life.": classifier `[0.0, 2.15]` and pick `[0.0, 2.15]`, 4 requests in all, peak 2. With `Retry-After: 3` both second requests go at 3.05, and with `Retry-After: 30` there is one request each and the question ends at 0.05 s with "about 30 seconds". Never more than 2 per guard call, and every second request goes after the backoff or the stated wait, as fix.md says.
- F-72-A05: FIXED. Own probe `ver72/p11_latehedge.py`, with the daily-cap check stalled so 4.3, 4.9 or 5.9 s are left. Branch, hanging replies: `sends [10.7] cancelled [1] cost 0.000256`, one request. Develop: `sends [10.7, 13.567] ... cost 0.000512`. No case in that probe that develop answers is lost (a 5.5 s reply with 5.9 s left: branch `passed`, develop `STEP_ERROR`).
- F-72-A04: FIXED for hang spells, the adversary's shape. `ver72/p9_burst.py` spells of 3, 5, 8 and 9.9 s: branch and develop both `passed after 10.60s` with 2 requests, and 11 s is lost by both. The fix agent's sweep claim ("every one develop answered") holds on its own grid but not in general. Own sweep `ver72/p10_sweep.py` runs develop's REAL code (not the test file's port) against the branch on 508 cases in six families the committed sweep lacks: a recovering provider, a degrading provider, per-request latencies, 500, 502 and `litellm.Timeout` spells, unusable-then-slow, and held-then-503. Develop answered 342 and the branch 362, never more than 2 requests and never past 15 s. The branch loses 4, all "held-then-503", where requests sent before S hang until S and then fail (`held-then-503 S=11 L=0.6: develop 11.60 s 3 req | branch 11.00 s 2 req`). That is the named "fail, fail, then answer" shape. A focused grid of 503 spells whose errors take 1.5 to 4 s (`ver72/p10b_sweep.py`, 144 cases) loses 35 that develop answered (develop 95, branch 60), e.g. `E=9.0 err_after=3.0 L=0.6 develop 11.60 4 | branch 11.00 2`. That is OPEN AS NAMED ("errors that take 2 to 4 s to arrive"), but it reaches spells of 9 and 11 s and errors of 2.5 and 3.5 s, not only the examples fix.md lists, and on this grid it is 24% of cases, not fix.md's 16 of 108. The same sweep found the branch answering LATER than develop in 46 cases (F-72-V06).

### F-72-V06: INSIDE THIS PHASE'S FIX (c263c159): one failed guard request that took a second or more to fail now makes the person wait 4 to 5 seconds longer than on develop
- Severity: major (a speed regression against develop on the front door, which the owner's no-degradation rule covers; unsure only on how often a guard request fails slowly rather than at once)
- What: `harness/decide.py` `second_request_at` sends the second request, after a transient error, "when develop's policy would have sent its LAST request" (`_develop_last_send`). That is the time of develop's fourth request, but develop's SECOND request went out the moment the first failed (`call_tier`'s immediate resend). For an isolated failure, the provider is healthy again straight away, and develop answered from that immediate resend while the branch waits several seconds first. The design keeps the ANSWER (dominance) but not the SPEED. fix.md's "What a person notices" and its known-limit list do not state it. `test_when_the_second_request_goes` pins it ("an error after 1 s: the same" -> 5.0).
- Reproduction: `ver72/p10_sweep.py`, real `guardrail_node`, virtual clock, the question "Which diseases are associated with BRCA1?", only the FIRST request failing (spell E=1.0, so only the request sent at 0 s fails), branch code against develop's real code (`d23674f4`):
  ```
  500 spell E=1.0 err_after=1.0 L=0.6 | develop answered=1 at 1.60s, 2 requests
  500 spell E=1.0 err_after=1.0 L=0.6 | branch answered=1 at 5.60s, 2 requests
  500 spell E=1.0 err_after=5.0 L=0.6 | develop answered=1 at 5.60s, 2 requests
  500 spell E=1.0 err_after=5.0 L=0.6 | branch answered=1 at 10.60s, 2 requests
  held-then-503 S=4 L=0.6: develop 4.60 s | branch 9.60 s
  ```
  The same holds for 502 and `litellm.Timeout`: 46 cases slower by up to 5.0 s, 28 of them by 2 s or more.
- Why it matters: a gateway error or upstream timeout that arrives after a few seconds is an ordinary provider failure, and it is one request, not a spell. On develop the person got an answer about 0.6 s after the error. On this branch they wait until about 5 s, or until the 10 s hedge point, for the same answer. The trade (outlasting an error spell against answering an isolated error at once) belongs to the owner, and it is not on record.
- NOT FIXED

### F-72-V07: INSIDE THIS PHASE'S FIX (c263c159): at every decision point, one failed guard request now delays the decision by 2.1 to 5 s, more than fix.md's "about 2 s later", and Think waits for it
- Severity: minor (named by fix.md, but understated; speed only, and only when a guard request fails)
- What: `_run_guard_pick` now goes through `ask_guard_model`, so every `decide()` guard pick (Think's `think.recent_years` and `think.ask_back`, `plan.literature`, and the guardrail's relevancy, with the guard provider at its default or after Jev fails) sends its second request at `second_request_at`, not at once. fix.md says "after an error send their second about 2 s later rather than at once". Measured, the delay grows with how long the error took to arrive: 2.1 s for a fast error, and 3.0, 4.0 and 5.0 s for errors after 0.5, 1 and 3 s. Think awaits `think.recent_years` before it goes on (`core/graph.py` about line 3814), so the person waits for that delay. A decision read late by a later step has only `_LATE_DECISION_GRACE_S` (1.0 s) of grace, so a later finish is more often read as no decision.
- Reproduction: `ver72/p13_decide_err.py`, a real `decide()` with the guard provider on the virtual clock, where request 1 gets a 503 after e seconds and request 2 answers. Branch against develop's real code:
  ```
  503 after 0.05s, reply 0.6s: branch done at 2.75s sends [0.0, 2.15] | develop done at 0.65s sends [0.0, 0.05]
  503 after 0.5s,  reply 0.6s: branch done at 4.10s sends [0.0, 3.5]  | develop done at 1.10s sends [0.0, 0.5]
  503 after 1.0s,  reply 0.6s: branch done at 5.60s sends [0.0, 5.0]  | develop done at 1.60s sends [0.0, 1.0]
  503 after 3.0s,  reply 0.6s: branch done at 8.60s sends [0.0, 8.0]  | develop done at 3.60s sends [0.0, 3.0]
  ```
- Why it matters: after a single failed request, Think's own decisions now hold the person up to 5 s longer than develop, on the same provider behaviour. The guardrail's classifier already had R-05's backoff on develop; the other decision points did not. It is the same trade as F-72-V06, spread across the loop.
- NOT FIXED

## Verdicts, continued (2)

- F-72-J08: FIXED. Judge's `p12_reasoning.py` re-run on HEAD: `classifier with a reasoning-mandatory guard model -> (... is_injection=False ...), GuardVerdict(admitted=True ...)) sent 2 in 0.10s`, where the pre-fix branch gave a step error after 1 request in 0.05 s. The resend is one extra provider request inside the same guard request, which fix.md names.
- F-72-J07: behaviour holds. Judge's `p9_midwait.py` on HEAD: `refusal [... 'off_topic' ...] after 2.00s`, the moment Jev's failure is signalled, not 7.00 s. Whether the new test catches a regression is in the break-it line below.
- F-72-J06: behaviour holds. Own probe `ver72/p12_j06.py`, with both requests in flight after the 10 s hedge: `hedge unusable 10.5, first admits 12: ok at 12.00s`, `first unusable 10.5, hedge admits 12: ok at 12.00s`, `first unusable 10.5, hedge INJECTION 12: injection at 12.00s`, `hedge unusable 10.5, first INJECTION 14.9: injection at 14.90s`. The judge's `p8_unusable.py` no longer reaches the both-in-flight state on HEAD (its hedge case gives `sent 1`, because it was written for the 4 s hedge), so it cannot confirm this.
- F-72-J10: OPEN AS NAMED. `ver72/p1_order.py`: when both replies are in hand, the stricter decides; when the admission comes back first (1 ms earlier), it decides and the other request is cancelled (`A I r2+1ms -> ok, cancelled [2]`). That is fix.md's stated residual. F-72-V01 bounds "in hand".
- Log privacy of the new per-request line, re-checked with the judge's `p7_logs.py` on HEAD: `KEY in log: False`. The upstream host has its newline and NUL stripped and is cut to 64 characters (`upstream evilFAKE LINExxxx...`). The question marker appears only in the pre-existing "unusable ... starts" line, which echoes the model's reply.

### F-72-V08: INSIDE THIS PHASE'S FIX (c263c159): the relevancy pick's new hedge admits an off-topic question that develop refused
- Severity: major (hunt item 1: an admission of a question a classifier refused on develop; the harm is an off-topic question searched and answered, not an injection)
- What: the guardrail's relevancy decision (`guardrail.relevancy`, asked whenever the biomedical allowlist misses, with the guard provider or after Jev fails) now goes through `ask_guard_model` (F-72-A02, J05). On develop its one guard request ran to the guardrail's budget and was never cut, so a slow "off_topic" reply at 10.6 to 15 s refused the question. On the branch a hedge goes out at 10 s. The FIRST usable reply decides, and the slow first request, still in flight, is cancelled. When the hedge says "on_topic" before the first request's "off_topic" arrives, the question is admitted. The stricter-reply rule (J01) cannot help, because the refusal is not in hand yet. This is not the classifier's own hedge, where develop also cut request 1 at 10 s and the outcome matches develop.
- Reproduction: `ver72/p15_pick_race.py`, real `guardrail_node` on the virtual clock, "Why do naked mole rats live so long?", the classifier admitting at 0.5 s, the relevancy pick's first request saying `off_topic` at T, any later pick request saying `on_topic` in 0.6 s. Branch against develop's real code (`d23674f4`):
  ```
  branch  jev=False ... off_topic at 12.0s ...: guard=ok at 10.60s sends [('cls', 0.0), ('pick', 0.0), ('pick', 10.0)] cancelled [2]
  develop jev=False ... off_topic at 12.0s ...: guard=off_topic at 12.00s sends [('cls', 0.0), ('pick', 0.0)] cancelled []
  branch  jev=True  ... off_topic at 14.0s ...: guard=ok at 10.60s ... cancelled [2]
  develop jev=True  ... off_topic at 14.0s ...: guard=off_topic at 14.00s
  ```
  At T = 10.5 s both refuse, because the first reply beats the hedge.
- Why it matters: in a slow spell, a question the guard model judges off topic, the pizza kind, is answered on the branch and refused on develop. The fix's promise "no question the classifier would refuse is ever admitted" does not hold on this new path. Fix shapes the owner could pick: for a refusal-only decision, do not let an admission from the hedge decide while the first request is still running (wait for both, to the deadline); or keep the relevancy pick on develop's unhedged path.
- NOT FIXED
- Break-it, my own mutations on a scratch copy of HEAD (`git archive HEAD` into `ver72/copy`, never the worktree; runner `ver72/mutate.py`, which restores each file after its run; the last copy file checked byte-identical to HEAD with `cmp`). Suite: the guardrail directory, `test_harness`, `test_decide`, `test_jev_client`, `test_jev_cost_bounds`, `test_jev_followup_costs` and `test_sentence_check`. Baseline `733 passed`.
  - J06, an unusable reply cancels the other request: `2 failed`.
  - J07, the wait ignores Jev's failure signal: `1 failed`.
  - J08, `retry=False` drops the reasoning fallback: `3 failed`.
  - J01a, the first usable reply read decides instead of the strictest: `2 failed`.
  - J01, only one ended request read per pass AND the leftover-read block removed (the pre-fix shape): `2 failed` (`test_two_replies_in_hand_the_refusal_wins[... same tick]` and `[the judge's probe ...]`). Either half alone stays green (`733 passed`), because each covers for the other, and the leftover-read block is unreachable while every ended request is read first.
  - Off topic ranked below an admission: `1 failed`, the rank unit test only. The same holds for the relevancy pick's rank inverted: no behavioural test covers either, only `test_the_stricter_reply_ranks_are_the_refusals_first`.
  - Hedge share 1/3: `14 failed`. Second request at once after any error: `11 failed`. `JEV_FLOOR_COST_USD = 0`: `26 failed`.

## Exit run

- Touched guardrail, harness and Jev tests, in the worktree (`-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`): `test_followup_guardrail.py`, `test_guard_request_dominance.py`, `test_reland_guardrail.py`, `test_decide.py`, `test_harness.py`, `test_jev_client.py`, `test_jev_cost_bounds.py`, `test_jev_followup_costs.py` and `test_sentence_check.py` gave `478 passed in 31.92s`.
- Frontend: `Test Files  7 passed (7)`, `Tests  37 passed (37)` (above). `frontend/node_modules` was linked for the run only and unlinked after.
- `git status --short` afterwards shows only this report: `?? testing/Developer/reports/2026-09-29_card72/verifier.md`.

## Verdict: DO NOT MERGE

The blocking item is F-72-V08. It sits INSIDE THIS PHASE'S FIX (c263c159, the A02 and J05 fix that sent the relevancy pick through the hedged path), so by the review loop's stop condition it goes to the product owner, not into another round on its own. In a slow spell, the relevancy decision's hedge admits a question that the guard model's own reply called off topic and develop refused. That breaks the change's headline promise, "no question the classifier would refuse is ever admitted", on a path this round created. F-72-V06 also sits inside the same fix: after one guard request fails slowly, the person waits 4 to 5 s longer than on develop. The owner should rule on it with V08, since both are the price of copying develop's timing into a two-request policy.

Every J and A finding is FIXED or OPEN AS NAMED; none is NOT FIXED. Partial or residual: J04 ("about 1 second, not straight away" for a wait that has run out), A01 (the no-wait case still reads "in a moment", F-72-V05), J09 (V02, concurrent pre-flights), and A04 (the named 2 to 4 s error-spell limit is wider than fix.md's examples). New findings: V01 minor and unsure, V02 minor, V03 unsure, V04 minor, V05 minor, V06 major (inside the fix), V07 minor (inside the fix), V08 major (inside the fix, blocking).

What I verified with my own probes (stubs and the virtual clock, or real time for stalls; no live model, no deployed app):
- J01's stricter-reply rule over 112 orderings.
- The loop-pass bound (V01).
- Jev charges at every site, including non-200 statuses (V03).
- The per-query cap, single and concurrent (V02), and the sentence check (J09 open).
- Stalls at five places in Jev's wait (J03).
- The rate-limit message edge values (J04).
- The web app's wording for 12 values of N (A01, V05), and no event-contract change.
- Storm request counts (J05).
- Slow-spell and late-hedge behaviour against develop's REAL code (A02, A04, A05).
- An own dominance sweep of 508 plus 144 cases against develop's real code, which found V06.
- `decide()` timing after one failed request (V07).
- The relevancy-pick race against develop (V08).
- Unusable against usable replies with both in flight (J06).
- The reasoning fallback (J08) and the mid-wait signal (J07).
- Log privacy.
- 12 break-it mutations on a scratch copy.

What I only read, not probed:
- The fix agent's full-suite, ruff, isort and build gates.
- The committed sweep's own grid numbers (429 and 453 of 752), which I did not recount; I ran the sweep file green and my own sweep instead.
- How many event-loop passes a real litellm and httpx reply takes (V01's realism).
- Whether a non-200 Jev status is billed by the provider (V03).
- The latency data in the diagnosis.
