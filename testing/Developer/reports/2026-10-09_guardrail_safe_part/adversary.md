# Adversary review: guardrail safe part (cards 84 and 72)

Fresh-context adversary, 2026-10-09. Checkout detached at 664e0e5b, base develop b01dee92.

## Findings

### A-GRS-01: provider_of still passes a router key, a bearer token, a JWT and a query string's secret value into the log line
- Severity: minor (the build report names the key case as left open; filed so it is tracked, not as a surprise)
- What: `_NOT_IN_A_HOST_NAME` keeps letters, digits, dots, hyphens and spaces, which is every character of a router key, a bearer header, a JWT and most secret values. Slashes, `?`, `&` and `=` are dropped, so a URL with a query string collapses into one run of letters that still carries the secret value. The 64-character cap keeps 55 of a 64-hex-digit router key's secret digits.
- Reproduction: `provider_of(SimpleNamespace(provider=v))` on this branch, every value built at run time (described here, not pasted, so the secret scanners stay quiet):
  - the router's key prefix plus 64 hex digits gives back the prefix and the first 55 hex digits, intact
  - the word Bearer, a space and a key-shaped string give the same string back, unchanged
  - a URL with a path and a query string whose parameter value is SECRET123 gives `httpsapi.example.comv1chat...SECRET123...`, the value intact
  - a three-part JWT (base64url header, payload and signature joined by dots) gives itself back, unchanged
  - `Together` plus a line break plus `2026-10-09 WARNING model call point=fake outcome=ok` gives `Together2026-10-09 WARNING model call pointfake outcomeok`: the break and `=` are gone, the spoofed words stay on the line
- What a person sees: nothing in the app. The operator's deployment log can hold a credential if the router ever echoes one in its `provider` field. Step 3c's goal, "keeps only what a host name needs", is met for control characters and line breaks only; a host name never needs 55 hex digits in a row.
- NOT FIXED

### A-GRS-02: Near the per-query cap the branch refuses as off topic questions develop admits; the decision grid cannot see it
- Severity: minor (unreachable at the $0.10 starter cap, since the guardrail is the first step of a question and spends about $0.02 at most; filed because the build report states the guardrail "admits and refuses exactly what develop does" without that condition)
- What: the grid test pins `PER_QUERY_COST_CAP_USD` at 1.0, so no charge difference can ever reach a cap check. Develop charges a Jev relevancy reply with no readable cost the $0.01 ceiling; the branch charges the $0.0001 floor. With the cap between about $0.0105 and $0.012, develop's ceiling charge trips the cap before the guard fallback, `_run_guard_pick` returns None and the relevancy decision fails open (admit). On the branch the fallback runs and its off_topic pick refuses.
- Reproduction: my own probe (a scratch pytest file driving the real `guardrail_node` with only `litellm.acompletion` and `jev_client._post` stubbed, the grid test's own stubs reused), run once on this branch and once with develop's five source files from b01dee92 checked out in place, then restored. Question "Tell me about the tree of life.", guard classifier admit, Jev injection not_injection at $0.00002, Jev relevancy reply with `usage.cost` of `null`, `"abc"`, `true`, `-0.001`, `NaN`, `1e309`, a list or a nested object, guard fallback off_topic. At caps 0.0105, 0.0107, 0.011, 0.0112, 0.0115 and 0.012: develop `{'category': 'ok', 'passed': True}`, branch `{'category': 'off_topic', 'passed': False}`. 120 of 4498 cases differ across 13 caps; every difference is in this direction; none is the branch admitting what develop refuses. At caps from 0.0004 to 0.0012 and at 0.0205 and 0.021, and at 1.0 on 346 extended cases, 0 differ.
- What a person sees: only with a per-query cap configured near a cent: an off-topic question develop let through is now refused as off topic. That is arguably the better answer, but it is a verdict change the build report says does not exist, and the grid would not have caught a change in the other direction either.
- NOT FIXED

### A-GRS-03: A reply stating far more than a cent is charged the $0.0001 floor when the figure is written as 1e309, as a string, or as an integer over 4300 digits
- Severity: minor
- What: step 3a's rule says "A stated cost above $0.01 is charged the $0.01 ceiling, not the floor (fixes F-84-A06)". `_stated_cost_usd` reads a JSON number `1e309` as infinity and returns None, so it is charged the floor. A string `"1e309"` likewise. A bare integer of 400 digits is charged the ceiling, but one of 5000 digits makes `response.json()` raise (Python's integer digit limit) and the whole body is charged the floor. So whether "more than any call costs" is counted as $0.01 or $0.0001 depends on how the provider spells the number. F-84-A06, "the more a reply said it cost, the less was counted", survives for these spellings.
- Reproduction: my probe above, Jev injection reply `{"usage":{"cost":<X>,...}}` with the guard admitting an allowlisted question. Charged to the query, branch: `1e309` 0.0001; `"1e309"` 0.0001; `1` followed by 5000 zeros 0.0001; `1` followed by 400 zeros 0.01; `0.0100001` 0.01; `"0.02"` 0.01. Develop charged 0.01 for the first three.
- What a person sees: nothing directly. The caps see a hundredth of what such a reply claims. The design's own reading may be that 1e309 is "infinity, unreadable"; I am filing it because the wire text is a finite, standard JSON number above $0.01, which the rule says is the ceiling. Unsure whether the owner would read it as unreadable.
- NOT FIXED

### A-GRS-04: A reply stating a vanishing cost, 5e-324, is used and charged 5e-324, which every cap reads as $0
- Severity: unsure
- What: `jev_charge_usd` charges any stated cost above $0 as stated, by design (V-GR-11, the build report's deviation from `1ce2c8d4`). A stated `5e-324` (or `1e-300`) passes `> 0.0`, so the call is charged a figure that adds nothing measurable to the running total. The owner's words are "never $0"; this is not $0 in the float, but it is $0 to every cap and every cost line.
- Reproduction: my probe, Jev injection reply `{"usage":{"cost":5e-324,...}}`, choice injection, guard admitting an allowlisted question. Branch: verdict `{'category': 'injection', 'passed': False}` (the reply is used), query total 2e-05 minus the guard's 2e-05 equals -3.4e-21, i.e. nothing added. The same as a timeout.
- What a person sees: nothing. A provider that drifts to tiny or denormal figures makes every Jev call free to the caps, the failure the floor was built to close (F-72-J02). Filed as unsure because it follows the rule's letter, "above $0"; whether a floor applies to absurdly small figures is the owner's reading.
- NOT FIXED

### A-GRS-05: New in this phase's fix: an off-set Jev choice, free model text over the person's question, is now written to the deployment log
- Severity: minor (privacy of the person's words in the log; inside step 3a's own change, so it fires the stop condition for a fix-inside-the-fix)
- What: `_unusable_reply` (new in 3261eb47) writes a WARNING line for every unusable reply whose detail, for an option outside the set, is `it chose {parsed.choice!r}`, up to 200 characters of Jev's own output. Jev's state for `guardrail.injection` and `guardrail.relevancy` is the person's question, and for the sentence check it is the answer's sentences, so a reply that echoes the question puts the person's own words in the log. Develop raised the same text inside `JevCallError` but never logged it; its callers log only `exc.reason`. The project's own rule in `core/graph.py` (`_log_step_failed`) is "Never `str(exc)`: a provider error can carry the person's own text", and `call_log.py` says its line "never sees the question".
- Reproduction: `call_jev(question_key "guardrail.injection", state = the question)` with `_post` stubbed to a 200 whose `answers["guardrail.injection"].choice` is the question text, "I am Jane Example, my BRCA1 carrier status is positive", cost 0.00002. Branch log: `WARNING system_03_search_agent.harness.jev_client Jev's reply for decision 'guardrail.injection' could not be used: it chose 'I am Jane Example, my BRCA1 carrier status is positive', which is not one of the offered options ['injection', 'not_injection']; it is charged $0.000020`. Develop's `jev_client.py` from b01dee92, same stub: no log line at all, only `reason invalid_option` returned. The batch path (`call_jev_batch`, the sentence check) logs `it chose {answer.choice!r} for question ...` the same way.
- What a person sees: nothing on screen. Their question, or a health detail in it, can sit in the operator's log, which develop did not do. `repr` escapes line breaks, so the line cannot be forged; the content is the problem.
- NOT FIXED

### A-GRS-06: Two of step 3a's charge changes have no test that bites: a batch reply with an option outside the set, and a body nested too deep
- Severity: minor (behaviour on the branch is right today; nothing stops it regressing)
- What: I mutated `jev_client.py` nine ways and ran `test_jev_client.py`, `test_jev_cost_bounds.py`, `test_jev_followup_costs.py`, `test_decide.py` and `synthesis/test_sentence_check.py` (306 tests). Seven mutations were caught. Two survived with "306 passed":
  - M4: `call_jev_batch`'s invalid-option arm charged `parsed.cost_usd` (develop's rule) instead of `charged_usd`. A batch reply stating $0 with an option outside the set is then charged $0, the F-72-J02 hole, in the sentence check. The only batch invalid-option test states a sensible cost, where both rules agree.
  - M5: `_json_payload` catching `ValueError` only (develop's arm) instead of `Exception`. A body nested 100000 deep raises `RecursionError`, escapes `call_jev` uncharged and reaches `_jev_injection_pick`'s `unexpected_error` arm. The docstring cites F-8.6-FA01 for exactly this; no test in these five files feeds a deep body.
- Reproduction: mutations applied by line in my checkout, run, then `git checkout` of the file after each. M4: "306 passed in 19.43s". M5: "306 passed in 20.05s". For contrast, M1 (batch usable reply at $0 charged $0) "2 failed", M3 (single-call invalid option charged as stated) "1 failed", M6 (stated $0 charged $0) "9 failed". The branch's own behaviour, probed directly: batch invalid option at $0 gives `('invalid_option', 0.0001)`; deep nest gives `('malformed_reply', 0.0001)`.
- What a person sees: nothing today. A later edit can undo either charge and stay green.
- NOT FIXED

### A-GRS-07: A reply stating a cost as an integer of 309 or more digits writes a 320-character dollar figure into the log line and the error message
- Severity: minor
- What: `_stated_cost_usd` turns a positive integer too large for a float into `sys.float_info.max`, and the above-the-ceiling detail formats it with `:.6f`, so the warning reads "it reported a cost of $179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000". Every other log line in this area caps untrusted figures (`repr(raw)[:40]` on develop, `_PROVIDER_MAX_CHARS` in `call_log.py`).
- Reproduction: Jev injection reply with `usage.cost` a `1` followed by 400 zeros, from my grid probe; charged 0.01 as designed; the message carries the 309-digit figure.
- What a person sees: nothing. One very long line per such reply in the operator's log, and a stated figure that is not what the reply said (the reply said 1e400; the log says 1.8e308).
- NOT FIXED

### A-GRS-08: Step 1 delivers only half of what was approved: two unreadable guard replies still tell the person to rephrase, and test query 109 says that was fixed
- Severity: major against step 1's contract (disclosed in the build report's deviations, so not hidden; filed because the shipped words and the test query disagree with what the person will see)
- What: the design's step 1, as approved, reads "the web app shows its own fixed words for any failure whose source is the guardrail, both the double timeout and two unreadable replies", and its problem statement names the second case as the one where "Rephrasing cannot help, because nothing was wrong with the question" (cards 91 and 94). The branch changes only `source === "guardrail" && error_class === "transient"`. Two unreadable replies arrive from `core/graph.py` as `recoverable` (graph.py line 2134 on this branch, unchanged), so they still read develop's "This run could not be completed. Try asking again, or rephrase the question." The only case whose words change is the double timeout, which on develop already did not say rephrase; it said "Try asking again in a moment".
- Reproduction: `git show b01dee92:frontend/src/hooks/useRunView.ts` has `transient: "This run could not be completed. Try asking again in a moment."`, so before this change the double timeout never said "rephrase". On the branch, `graph.py` `_guardrail_after_prefilter` still returns `{"source": "guardrail", "error_class": "recoverable", ...}` when the classifier's two replies are unusable; my extended grid probe shows that verdict, `{"step_error": ["guardrail", "recoverable"]}`, for all 52 two-unreadable-reply cases, branch and develop alike; and `useRunView.ts` maps `recoverable` to `FATAL_COPY.recoverable`, the rephrase line. Test query 109, "Why it matters", says: "before this, a person whose question was fine was told to rephrase it ... Saying the problem was ours, and that asking again is the fix, tells them what to do next." The person in that case is still told to rephrase.
- What a person sees: when the guard model sends back two cut-off replies (3 seen on 2026-09-29), the screen still says to rephrase a question that was fine. The owner reading query 109 would believe that was fixed.
- NOT FIXED

Correction to A-GRS-08: the two-unreadable-replies step error sits at `core/graph.py` lines 2130 to 2140 on this branch (the `"source": "guardrail"` key is line 2135), not line 2134.

## Verdict

FAIL.

- No admission or refusal differs from develop at any realistic cap: 0 of 346 extended cases at a $1.00 cap, and none where the branch admits what develop refuses at any of 13 tight caps (A-GRS-02 is the only difference, refusals near a one-cent cap). Step 3b is absent from the diff.
- FAIL rests on A-GRS-08 (step 1 as approved names two unreadable replies, which still read "rephrase", and query 109 says otherwise) and A-GRS-05, a new log line inside step 3a's own change that writes Jev's free text, which can echo the person's question, to the deployment log. A-GRS-05 is a defect inside this phase's fix and should fire the stop condition.

Verified with my own probes:
- Verdict parity, branch against develop's five source files from b01dee92 checked out in place and restored: a 346-case extended grid (crafted costs as strings, booleans, null, NaN, negative, -0, 1e309, 400 and 5000 digit integers, nested objects, lists, a denormal, missing or null usage; HTTP 400, 401, 402, 403, 404, 429, 502, 503; Jev timeout and connect error; empty, non-JSON, top-level list and deeply nested bodies), and a 4498-case cap sweep.
- That the frozen `develop_decision_grid.json` is develop's: the grid test passes with develop's sources in place ("1 passed in 3.56s").
- The charge for every crafted reply, branch and develop (A-GRS-03, A-GRS-04).
- `provider_of` on key, bearer, JWT, URL and line-break inputs (A-GRS-01).
- Nine mutations of `jev_client.py` against the five charge test files (A-GRS-06).
- The log line for an echoed choice, branch and develop (A-GRS-05), and the 522-character line for a huge stated cost (A-GRS-07).
- `useRunView.retryAfter.test.ts` runs green ("11 passed"); `test_call_log.py` and the grid test run green ("32 passed").

Only read, not probed:
- The web app mapping (`source === "guardrail" && error_class === "transient"`) and that only the guardrail node emits `source: "guardrail"`; I did not render the screen or mutate the TypeScript.
- Which provider errors litellm classes as transient against recoverable (`harness.py` `_TRANSIENT_EXCEPTIONS`), so whether a "transient" guardrail failure can ever be caused by the person's input.
- Follow-up turns: the charge change cannot reach them except through the cap, which A-GRS-02 covers; I did not drive a session.
