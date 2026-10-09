# Fresh verifier report, guardrail cards 84 and 72

Checkout at origin/fix/card84-72-guardrail, HEAD 6f666269 (confirmed with git rev-parse). Base on develop c916cfa3. Results are appended as they are established.

## Results

### V-GR-01: A-GR-11's admission survives on the follow-up path; a question both judges refused is admitted after a 4 to 4.8 s pause, develop refuses it

- Regression of: A-GR-11 (the fix in 10da5cf0 is incomplete; its commit title "A server pause never admits a question both judges refused" is false)
- Severity: critical (an admission develop refuses, of a question Jev called an injection and the guard model called off topic)
- What: the A-GR-11 rule (`jev_injection_unknown`, core/graph.py lines 2140 to 2225) is applied only in the R-03 branch, where Jev's on-topic pick sets the guard model's off-topic verdict aside. The memory-bound follow-up branch (graph.py, `_is_memory_bound_follow_up`, the first `if` under `if not classifier_verdict.admitted`) also sets the guard model's off-topic verdict aside, and then admits on Jev's relevancy pick reading on topic (graph.py, `relevancy == "off_topic"` / `relevancy is None and classifier_off_topic_set_aside`). It never reads `jev_injection_unknown`. So one pause still keeps Jev's fast on-topic pick on the free-time clock and loses Jev's slower injection pick to the real-time cap, and the question is admitted.
- Reproduction: my probe (the sweep's own stubs and virtual clock, `guardrail_node` run on this branch's src and on an export of develop's real src at c916cfa3), question "Tell me more about it in the tree of life." (no allowlist word, a referring word), session memory holding one resolved entity (BRCA1, NCBIGene:672), Jev provider on. Guard classifier: off topic at 0.3 s. Jev injection: "injection". Jev relevancy: "on_topic" at 0.2 s. Guard fallback pick: off topic at 0.3 s. One pause as Jev's relevancy request is sent. Pasted:
  - Jev injection at 2.0 s, pause 4.0 s: develop off_topic 4.30s, branch ok at 5.00s
  - Jev injection at 0.6 s, pause 4.5 s: develop off_topic 4.80s, branch ok at 5.00s
  - Jev injection at 2.0 s, pause 4.5 s: develop off_topic 4.80s, branch ok at 5.00s
  - Jev injection at 0.6 s, pause 4.8 s: develop off_topic 5.10s, branch ok at 5.00s
  - Jev injection at 2.0 s, pause 4.8 s: develop off_topic 5.10s, branch ok at 5.00s
  - The same case with no pause: develop injection 2.00s, branch injection at 2.00s (both refuse).
  - The same shape on a first question (no memory), pause 4.5 s: branch off_topic at 5.00s, so only the follow-up path leaks.
- Why the gate misses it: `run_case` builds `RequestContext(surface="rest_sse")` with no session memory, so no sweep case can reach the follow-up branch.
- What a person sees: after a 4 to 5 s server freeze, a follow-up turn the guard model refused as off topic and Jev refused as an injection is searched and answered. Develop refuses it.
- NOT FIXED

### V-GR-02: the yardstick still equals develop's real code after the fix round (pause grid)

- Result: verified, my probe. The pause grid (16,800 cases) run three ways on the virtual clock: develop's real src (export of c916cfa3), this branch's yardstick (`port=True`) and this branch's real node. Pasted: "develop real vs yardstick (port): identical (verdict, time, requests, peak): 16800 of 16800". So the sweep's "develop" column is develop.
- Develop real vs branch over the same grid: "identical 11517 of 16800"; "verdict transitions A->B: {('off_topic', 'ok'): 230, ('ok', 'off_topic'): 282, ('ok', 'injection'): 306, ('off_topic', 'injection'): 272, ('injection', 'off_topic'): 1}"; "same verdict later in B: 2861 max 2.0"; "B past 15 s: 0"; "B two of one kind in flight: 0".
- Of the 230 new admissions, 228 are FA03 (develop admits the same case with no pause) and 2 are the kept cases below (develop refuses with and without the pause).

### V-GR-03: the two kept cases, reproduced; my call

- Reproduction (develop real against the branch, my dump of the pause grid, each also run with no pause):
  - "classifier admit@0.3, Jev injection injection@2, Jev relevancy on_topic@0.2, a 4.5s pause at relevancy_send, guard pick off_topic@0.3 | develop off_topic 4.8 {'classify': 1, 'pick': 1} | develop calm injection | branch ok 5.0 {'classify': 1, 'pick': 0} | branch calm injection"
  - "classifier admit@0.3, Jev injection injection@2, Jev relevancy on_topic@0.2, a 4.5s pause at classify_send, guard pick off_topic@0.3 | develop off_topic 4.8 {'classify': 1, 'pick': 1} | develop calm injection | branch ok 5.5 {'classify': 1, 'pick': 0} | branch calm injection"
- Should it be admitted: no, not by develop's own calm policy. In both cases Jev's injection pick is "injection"; with no pause both develop and the branch refuse it as injection. build.md's description ("the guard model's own verdict admitted, Jev's own pick said on topic") leaves out that Jev's injection judge flags this question. The sweep's predicate `_guard_admitted_and_develop_lost_jevs_pick` does not look at Jev's injection pick at all, so it would also accept any future admission of this shape.
- Is develop's refusal real protection: no, a timing accident. Develop refuses only because its clock also lost Jev's on-topic pick and the guard fallback pick, asked only then, said off topic. The same case with the fallback saying on topic is admitted by develop ("guard pick on_topic@0.3 | develop ok 4.8 | branch ok 5.0"), and with the fallback hanging develop admits at 15.0 s. Across the pause grid develop itself admits 420 cases whose no-pause verdict is an injection refusal (Jev's injection pick lost to the pause on develop's real-time clock).
- Does it weaken a stated design promise: not literally. The guard classifier's own verdict admitted (rule 1 holds), and on the branch's path no refusal arrives to be removed (rule 3 holds). It is the same exposure develop already carries in 420 cases. It does contradict the fix round's own A-GR-11 reasoning ("nobody knows whether Jev would have refused"), which the branch applies only where Jev's on-topic pick sets a refusal aside, not where it replaces the guard fallback.
- My call: acceptable in kind on its own, not by itself a reason to stop. It is not the reason for my verdict; V-GR-01 is.

### V-GR-04: the A-GR-11 rule refuses as off topic questions develop admits with and without the pause, after a 2.5 to 5.5 s pause

- Regression of: A-GR-11 (introduced by the rule added in 10da5cf0)
- Severity: major (an on-topic question, by Jev's own topic pick and by develop's policy with no pause, refused as off topic; needs a pause past the 2 s allowance)
- What: when the guard model says off topic and Jev's injection pick ends on its real-time cap after a pause, the branch now refuses (`jev_injection_unknown`, graph.py line 2149 and the early return in the R-03 branch). This includes an injection pick that would never have refused: a Jev injection call that hangs (Jev takes its whole bound, which develop and the branch with no pause both read as "no pick", the classifier's verdict standing), an HTTP 500, and a "not_injection" reply still in flight when the pause ends. Develop admits all of these on Jev's on-topic pick (R-03).
- Reproduction: my own grid (30,744 first-question cases: classifier admit or off topic or injection at 0.3 s and admit at 6 s; Jev injection not_injection, injection at 0.12, 1, 2 and 2.9 s, an HTTP 500, a hang; Jev relevancy on topic at 0.2, 2 and 2.9 s, off topic at 0.2 and 2.5 s, a hang; guard pick on topic, off topic, hang; one pause of 0.5 to 5.5 s at six points), develop's real src against the branch, each also run on develop with no pause. Pasted: "develop admits (paused and calm), branch refuses: 273 Counter({'off_topic': 273})"; "by Jev injection pick: {'not_injection@0.12': 9, 'http_500@0.1': 9, 'hang@0': 255}"; "by pause: {'5.5': 54, '2.5': 39, '3': 36, '3.5': 36, '4': 36, '4.5': 36, '4.8': 36}". Example: "classifier off-topic@0.3, Jev injection not_injection@0.12, Jev relevancy on_topic@0.2, a 5.5s pause at injection_send, guard pick on_topic@0.3 | develop ok 5.5 | branch off_topic 5.5".
- Attribution, by breaking it: with line 2149 changed to `jev_injection_unknown = False` (restored after), all 273 are admitted again ("of those the A-GR-11 rule off admits: 273"), and the A-GR-11 test goes red ("FAILED ...test_a_pause_never_admits_a_question_both_judges_refused[4.5-0.6]", "1 failed, 3 passed").
- Why the gate hides it: `_paused_case` files any refusal past the allowance as `_PAST_REFUSED` ("the named residual") without asking whether develop admitted the case. The design's named residual is a refusal develop also gives; these develop does not give.
- What a person sees: after a few seconds' server freeze, a question Jev judged on topic and develop answers is turned away as off topic.
- NOT FIXED

### V-GR-05: the kept admission class is not 2 cases; the sweep's cap of 2 is a property of its grid

- Severity: minor (my call on the class itself is in V-GR-03)
- What: on my wider grid the kept shape (guard admitted, Jev on topic read, Jev injection pick "injection" lost to the pause, develop refusing only through its guard fallback) gives 26 first-question admissions develop refuses with and without the pause, not 2: "branch admits, develop refuses with AND without the pause: 26", "13 ('classifier admit@0.3', 'Jev injection injection', 'develop off_topic', 'develop calm injection')", "13 ('classifier admit@6', ...)". Examples: "classifier admit@0.3, Jev injection injection@2, Jev relevancy on_topic@0.2, a 3.5s pause at relevancy_send, guard pick off_topic@0.3 | develop off_topic 3.8 | branch ok 5.0"; "... injection@1, ..., a 4.8s pause ... | develop off_topic 5.1 | branch ok 5.0". The `<= 2` assertion in `test_a_pause_around_or_past_the_allowance_admits_nothing_develop_refuses` bounds the grid, not the behaviour.
- NOT FIXED

### V-GR-06: no case past 15 s and never two requests of one kind in flight (classifier and guard pick)

- Verified, my probes: pause grid "B past 15 s: 0", "B two of one kind in flight: 0"; my first-question grid "branch past 15 s: 0 | two in flight: 0"; my follow-up grid the same. Jev requests in flight are not counted by the stubs (J-GR-07, still open); not verified for Jev.

### V-GR-07: J-GR-08's lateness bound holds on my grids; no-pause cases are never later

- Verified, my probes, every case of my two 30,744-case grids (first question and follow-up), develop real against the branch: "no-pause verdict diffs: 4 {('off_topic', 'injection')} | no-pause later: 0 | paused later than min(pause+look, 2s): 0", the same line for both grids. The 4 no-pause differences are the counted `_INJECTION_SOONER` class (a refusal either way, never later).

### V-GR-08: on a merely busy server, with no long pause, a question develop admits is refused as off topic

- Regression of: A-GR-11 (the A-GR-11 rule in 10da5cf0 combined with the busy-loop path of the same commit, which raises `PausedTimeoutError` whenever looks come back late)
- Severity: major (same class as V-GR-04, but reachable without any single pause past the allowance: the server only has to be busy while one Jev injection call hangs)
- What: on a loop busy in short chunks, `wait_counting_free_time` counts almost nothing (each look returns more than 0.05 s late) and ends on its real-time cap, raising `PausedTimeoutError`. A Jev injection call that hangs therefore reads as "unknown" (`_JEV_INJECTION_CUT_BY_PAUSE`), and the A-GR-11 rule then keeps the guard model's off-topic refusal that Jev's own on-topic pick sets aside on develop.
- Reproduction: my probe, the real node on the virtual clock with a coroutine blocking the loop in fixed chunks for the whole run, develop's real src against the branch. Classifier off topic at 0.3 s, Jev injection hangs, Jev relevancy on topic at 0.2 s, guard pick off topic:
  - 0.03 s chunks: develop "ok 3.33s", branch "off_topic 5.13s"
  - 0.06 s chunks: develop "ok 3.66s", branch "off_topic 5.22s"
  - 0.15 s chunks: develop "ok 4.35s", branch "off_topic 5.85s"
- What a person sees: when the service is busy and Jev's injection check stalls, an on-topic question develop answers is refused as off topic, and about 1.5 to 1.8 s later than develop's answer.
- NOT FIXED

### V-GR-09: A-GR-06 is bounded, not closed; on a busy server a Jev wait still ends about 1.5 to 2 s after develop's, and 1 s chunks overshoot to 7 s

- Severity: minor (unsure how busy production gets)
- Reproduction: `wait_counting_free_time` on a hung call, bound 3.0 s, virtual clock, loop busy in chunks: "0.03s: 4.98s", "0.06s: 4.92s", "0.1s: 4.90s", "0.15s: 5.10s", "0.3s: 4.80s", "0.6s: 4.20s", "1.0s: 7.00s" (each "PausedTimeoutError"). The adversary measured develop's `wait_for(3.0)` at 3.15 to 6.00 s for the same chunks. On the node: classifier admit, Jev relevancy hangs, guard pick on topic: develop "ok 3.87s" / branch "ok 5.67s" at 0.03 s chunks; develop "ok 4.44s" / branch "ok 6.00s" at 0.06 s; develop "ok 5.85s" / branch "ok 7.35s" at 0.15 s.
- The bound the fix round states, "ends by the cap, give or take one turn of a busy loop", holds for chunks up to 0.6 s; at 1.0 s chunks the wait ends 2 s past the 5 s cap, so the pinned test (chunks 0.03 to 0.6 s) does not cover the whole claim.
- NOT FIXED

### V-GR-10: fixed by my own probes: J-GR-01, J-GR-02, J-GR-03, A-GR-07, A-GR-09, A-GR-14 (the wait itself)

- J-GR-01 / A-GR-08: "pause 0.2 then reply at 2.95: ('reply', 3.15)"; "pause 1.9 then reply at 2.99: ('reply', 4.89)"; with no pause a reply at 3.05 s still times out ("TimeoutError", 3.00 s). Fixed.
- J-GR-02: "pause 4.7s at send, reply 0.2s later: ('reply', 4.90)"; "pause 4.9s ...: ('PausedTimeoutError', 5.00)"; "pause 6.0s: ('PausedTimeoutError', 6.0)". The code does what the corrected comment says.
- A-GR-07, on `wait_counting_free_time`: a reply ready at 0.2 s then a 3, 5 or 10 s pause is read ("('reply', 3.2)", "('reply', 5.2)", "('reply', 10.2)"). On the node, the adversary's shape (classifier admits, Jev injection and Jev off topic at 0.2 s, a 5 s pause as the injection request is sent, guard pick hangs): develop "off_topic 5.00s", branch "off_topic 5.00s" (first build: ok at 15 s). Also at 4.9, 6 and 8 s pauses, both off topic. Fixed.
- J-GR-03 / A-GR-14: on a real loop, budgets nan, inf, 0.0, -1.0, True, 1e-09 each "TimeoutError after 0.00s real". A frozen `time.monotonic`: "PausedTimeoutError after 2.86s real" (ends on the look limit). Fixed.
- A-GR-09: a clock stepping back 0.5, 5 or 100 s once: "TimeoutError after 0.35s real" each. Fixed.

### V-GR-11: every usable Jev reply is now charged $0.0001 instead of the $0.00002 it states, outside the owner's rule

- Regression of: J-GR-04 (1ce2c8d4)
- Severity: minor in money, but it is a charge outside the owner's rule, which the brief names as worse than develop
- What: the owner's rule of 2026-09-29 (DECISIONS.md, the row "A Jev reply that reached the provider is charged the cost it states when that is above $0 and at most `MAX_JEV_COST_USD`, otherwise a floor near Jev's real price, about $0.0001, never $0") charges a stated $0.00002 as $0.00002. The fix round's `jev_charge_usd` (`if stated_usd is None or not stated_usd >= JEV_FLOOR_COST_USD: return JEV_FLOOR_COST_USD`) raises every stated cost under $0.0001 to $0.0001. Jev's real price is under the floor, so every usable Jev reply is charged about five times what it states. The judge's J-GR-04 asked for a floor "below some plausible minimum (for example a tenth of Jev's measured $0.0000148)" if the owner wanted one; the fix chose a floor above Jev's real price, without an owner decision I could find in DECISIONS.md. build.md's own earlier deviation note ("a stated cost below the floor but above $0 ... is charged as stated, per the owner's words") is now contradicted by the code.
- Reproduction: my probe, the real `call_jev` with `_post` replaced, on develop's src and the branch's: "develop stated 2e-05: usable charged 2e-05" / "branch stated 2e-05: usable charged 0.0001"; "develop stated 1.48e-05: usable charged 1.48e-05" / "branch stated 1.48e-05: usable charged 0.0001". The rest of the rule holds on the branch: "stated 0: 0.0001", "stated None: malformed_reply charged 0.0001", "stated 0.05: malformed_reply charged 0.01", "HTTP 500: http_error charged 0.0001", "not JSON 200: malformed_reply charged 0.0001", "stated 1e-300: usable charged 0.0001" (A-GR-03 closed).
- What a person sees: nothing directly; each question's counted Jev spend rises about fivefold (build.md: "under a tenth of a cent" a question), so the per-query, per-user and daily caps are reached sooner than the real spend warrants. The design's step 3a stated cost was "at most $0.0001 per Jev reply that states $0 or is unreadable", not per every reply.
- NOT FIXED

### V-GR-12: A-GR-14 fixed

- My probe, a hung `_post` under an outer 4 s guard: "branch A-GR-14 call_jev_batch timeout_s=nan: JevCallError timeout after 0.00s real" (develop's src: "TimeoutError after 4.00s real", the outer guard firing); inf: "JevCallError timeout after 3.00s real" on both.

### V-GR-13: A-GR-10 fixed; no non-guardrail failure reads the guardrail words

- Backend, my probe on the real node, develop's src then the branch's (source, class, wait): two timeouts "guardrail, transient, 0" on both; two unreadable replies develop "recoverable", branch "transient" (the one intended change); a 401 "unexpected" on both; a content-policy refusal and a 400 "recoverable" on both; a 429 with no wait, a 429 naming 13 s and a 503 "transient" on both, with identical times and request counts.
- Web app: `useRunView.ts` line 1275 shows the guardrail words only for source "guardrail" and class "transient". Changing it back to `!== "cancelled"` (restored after): "Tests  3 failed | 8 passed (11)", the content-policy, 400 and 401 arms. The backend class for two unreadable replies set back to "recoverable" (restored after): "FAILED ...test_each_kind_of_guardrail_failure_carries_its_own_category[two unreadable replies]", "1 failed, 4 passed".
- Every source "guardrail" step error is built in `_guardrail_after_prefilter` from the guard call (graph.py lines 1982, 2026, 2038, 2110); the daily caps carry their own `cost_control` sources and a crash carries "core.run.run". So only a guardrail failure can read the words. A rate limit at the guard call reads them too (class "transient", disclosed by the builder).
- Left as the builder disclosed: A-GR-01 and J-GR-05, every guardrail error still sends `retry_after_s: 0` (probe above: "429 wait 13 -> ... 'retry_after_s': 0"), so the "about N seconds" words never show.

### V-GR-14: the named suites, run one at a time on 6f666269

- `tests/system_03_search_agent/guardrail`: "378 passed in 94.41s (0:01:34)".
- `tests/system_03_search_agent/harness`: "507 passed in 24.61s".
- `synthesis/test_sentence_check.py`: "99 passed in 4.22s"; `synthesis/test_sentence_pair_check.py`: "47 passed in 3.17s".
- `frontend/src/hooks/useRunView*.test.ts(x)`, seven files one at a time: 6, 4, 3, 8, 11 (`retryAfter`), 5 and 7 tests, all passed.
- These are the author's tests; my verdict rests on the probes above, not on these.

### V-GR-15: the four sweeps, run by me, and one break of the code

- `pytest -s ... test_guard_request_dominance.py -k reports_its_counts` on 6f666269, pasted:
  - "classifier, guard sweep: 10306 cases, develop answered 5940, held 5940, problems 0"
  - "classifier, jev sweep: 10306 cases, develop answered 5940, held 5940, problems 0"
  - "relevancy sweep: 1296 cases, develop answered 1080, held 928, problems 0" (classes: injection sooner 2; Jev's own pick now read 100; later by no more than the pause and one look 50; FA03 48)
  - "pause sweep: 16800 cases, develop answered 16650, held 12628, problems 0" (classes: past the allowance, admitted as develop admits it 86; "refused where the same case with no pause is not (the named residual): 258"; the kept admission 2; refused either way under the other category 2; Jev's own pick now read 829; later 2845; FA03 228)
  - "1 passed, 13 deselected in 45.76s". These match build.md's figures.
- Break: Jev's on-topic pick allowed to set aside the classifier's injection verdict (graph.py, the R-03 condition `classifier_verdict.category == "off_topic"` changed to `in ("off_topic", "injection")`; restored after, `git status` clean). Result: "FAILED ...test_the_relevancy_wait_loses_nothing_develop_answers_and_answers_nothing_later", "FAILED ...test_a_pause_around_or_past_the_allowance_admits_nothing_develop_refuses", "2 failed, 5 passed, 7 deselected", with lines such as "classifier injection@0.3, Jev injection not_injection@0.12, Jev relevancy on_topic@0.2, a 0s pause at relevancy_send, guard pick on_topic@0.3: admitted although a judge said injection". The sweep catches Jev removing a refusal on the first-question path.
- Break 2, from V-GR-04: the A-GR-11 rule switched off: "FAILED ...test_a_pause_never_admits_a_question_both_judges_refused[4.5-0.6]", "1 failed, 3 passed".
- What the sweep cannot see (my findings above): a follow-up turn (V-GR-01, no session memory in any case), a refusal of what develop admits past the allowance (V-GR-04, filed as "the named residual"), a busy server (V-GR-08), and Jev requests in flight (J-GR-07).

### V-GR-16: the classifier path equals develop's real code; two pauses add nothing new

- Classifier grid (5,153 providers, budgets 15 and 12 s) under four Jev modes (guard provider; Jev "not_injection" at 0.12 s; Jev "injection" at 2.9 s; Jev hangs), "BRCA1" question, develop's real src against the branch: "41224 cases; identical (verdict, time, requests, peak, error class): 39836"; every difference is "('recoverable', 'transient'): 1388", the intended A-GR-10 class change for two unreadable replies, same verdict, time and requests.
- Two pauses in one case (6,912 cases, first question and follow-up, pauses of 1.5 and 3 s at two different points), develop real against the branch: "branch past 15 s: 0 | two in flight: 0"; "branch admits, develop refuses paused and calm: 0"; "develop admits paused and calm, branch refuses: 117" (the V-GR-04 class again).

## Fix round findings, one by one

| Finding | Fixed? | Evidence |
|---|---|---|
| A-GR-11 | Partly. First question: yes (my probe: branch "injection" or "off_topic" where the first build admitted; rule off turns the test red). Follow-up turn: no | V-GR-01; regressions V-GR-04, V-GR-08 inside the same fix |
| A-GR-12 | Partly. The pause grid exists and catches the first-question shape | No follow-up turns, and `_PAST_REFUSED` hides refusals develop does not give (V-GR-01, V-GR-04); the cap of 2 is a grid fact (V-GR-05) |
| A-GR-10 | Yes | V-GR-13, backend and web app, each broken and restored |
| A-GR-06 | Bounded, not closed | V-GR-09: about 5 s against develop's 3.2 to 4.5 s on a busy server; 7 s at 1 s chunks |
| A-GR-07 | Yes | V-GR-10 |
| A-GR-09, A-GR-14 | Yes | V-GR-10, V-GR-12 |
| J-GR-01 / A-GR-08 | Yes | V-GR-10 |
| J-GR-02 | Yes, the stated rule now matches the code | V-GR-10 |
| J-GR-03 | Yes | V-GR-10 |
| J-GR-04 / A-GR-03 | 1e-300 now charged the floor, but every real Jev reply is now overcharged, outside the owner's rule | V-GR-11 (Regression of: J-GR-04) |
| J-GR-08 | Yes, the bound holds on my grids | V-GR-07 |

## Verdict

Verified by my own probes: every row of the table above; the yardstick equal to develop's real code (16,800 of 16,800 pause cases, 41,224 classifier cases bar the intended class change); the four sweeps' counts; the sweep failing when Jev sets aside an injection verdict and when the A-GR-11 rule is off; no case past 15 s and never two classifier or guard-pick requests in flight across about 95,000 cases; the web app's words by mutation; the charge rule through the real `call_jev`.

Only read, not probed: Jev requests in flight (the stubs do not count them, J-GR-07); the MCP, CLI and GraphQL renderers of the new "transient" class; the cancelled-but-not-awaited Jev task on a timeout (`_retrieve_quietly`) for leaked connections; the debugging guide text.

The two kept cases: develop's refusal is a timing accident and the class is develop's own exposure (develop admits 420 such cases), so on their own I would not stop for them; but they are 26 cases on a wider grid, not 2, and in each Jev's injection judge flags the question.

DO NOT MERGE: worse than develop. V-GR-01 admits a follow-up turn that the guard model refused as off topic and Jev refused as an injection, where develop refuses it (Regression of: A-GR-11). V-GR-04 and V-GR-08 refuse as off topic questions develop admits with and without the pause, after a pause past 2 s or on a busy server (Regression of: A-GR-11). V-GR-11 charges every Jev reply outside the owner's rule (Regression of: J-GR-04). All three sit inside this phase's fix round, which fires the review loop's stop condition: escalate to the product owner, not another round.
