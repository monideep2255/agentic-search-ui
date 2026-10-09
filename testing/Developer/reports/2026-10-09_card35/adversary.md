# Card 35 adversary report

Fresh-context adversary, checkout detached at cd0e65a8 (fix/card35-offtopic-followup), base develop b01dee92. Credits before: left 31.6258.

## Findings

### A-35-01: a slow topic decision now holds an on-topic follow-up for up to the guardrail's whole 15 s budget

- Severity: minor (failure path only; unsure whether the owner's 20 s rule makes it major)
- What: an allowlist-admitted, memory-bound follow-up now waits for the `guardrail.relevancy` decision even when the guard classifier has already admitted it. When that decision is slow or hangs, the wait is bounded only by the step deadline (`_await_within_step(..., step_deadline)` at the read after line 2294), and the question is then admitted anyway (no usable pick fails open). On develop the same follow-up asked no decision and passed the guardrail at once.
- Reproduction: offline probe, guard classifier faked to admit instantly, `graph.decide` replaced by a coroutine that sleeps N s then returns on_topic, memory holding BRCA1 with open thread "Which diseases are associated with BRCA1?", text "What variants cause it?".
  - Fix (cd0e65a8): delay 0 s, elapsed 0.00 s; delay 5 s, elapsed 5.00 s; delay 30 s, elapsed 15.00 s, log "decision guardrail.relevancy still running when its step's budget ran out", passed=True.
  - Develop (b01dee92 graph.py, same probe): elapsed 0.00 s at every delay, passed=True.
- What a person sees: a follow-up such as "What variants cause it?" that used to start answering at once sits on the first step for up to 15 seconds whenever the topic model call stalls, and is then answered exactly as before. The wait buys nothing on that path, since the outcome is the fail-open admit. With Think, Plan, Act and Write still to run, the 20 s answer target is lost on that run. The build report's "the person waits for the slower of the two" holds only when the decision is healthy.
- NOT FIXED
### A-35-02: an off-topic follow-up carrying the card's own word "study" was admitted in one live run of three

- Severity: major (unsure: model variance, not a code defect; filed because the word is the one the owner named)
- What: the fix hands the follow-up to the live `guardrail.relevancy` decision, and that decision does not reliably call an off-topic follow-up containing "study" off topic. When it picks on_topic, the guard classifier's off-topic verdict is set aside by the referring word and the question is admitted, the card's original symptom.
- Reproduction: live, guard tier (`GUARD_MODEL` from .env, `CLASSIFIER_PROVIDER` unset), `_decide_point(harness, trace, _RELEVANCY, _relevancy_state(text, state))` with memory holding BRCA1 and open thread "Which diseases are associated with BRCA1?". Text "Is there a study showing which football team it is best to bet on?" (allowlist hit, memory-bound). Three runs: off_topic, on_topic, off_topic. Offline, an on_topic pick with the guard classifier saying off_topic gives ADMIT on the fix (grid probe, jev off and on).
- What a person sees: after a BRCA1 answer, asking which football team to bet on returns, one time in three, a full paid search grounded on BRCA1 instead of the "Outside biomedical research" refusal. The build report's live check (five or more runs per follow-up) was not run; the offline tests mock the decision to say off_topic, so they cannot show this.
- NOT FIXED

### A-35-03: a creative-writing follow-up naming the gene is admitted every time

- Severity: unsure (it may be acceptable that a request naming BRCA1 is treated as on topic)
- What: "Write me a love poem for my girlfriend and mention it, BRCA1" is an allowlist hit and memory-bound; the live relevancy decision picked on_topic in three of three runs, so it is admitted whatever the guard classifier says.
- Reproduction: same live harness as A-35-02. Picks: on_topic, on_topic, on_topic. Latencies 1.63 s, 1.79 s, 1.42 s.
- What a person sees: a poem request after a BRCA1 answer runs a full paid search and returns BRCA1 evidence rather than the refusal that says what to type next. Same outcome as develop, so not a regression, but the card's goal ("checked for topic like any other question") does not cover it in practice.
- NOT FIXED

### A-35-04: a general programming follow-up mentioning gene tables is admitted two runs in three

- Severity: unsure (bioinformatics programming is arguably on topic)
- What: "Which python library is best for it, pandas or polars, for gene tables?" got live picks on_topic, on_topic, off_topic. The criteria name "general programming" as off topic; the decision is not stable on it.
- Reproduction: same live harness as A-35-02. Picks: on_topic, on_topic, off_topic.
- What a person sees: the same follow-up is refused once and answered with a BRCA1-grounded search twice; the person cannot predict which.
- NOT FIXED

### Live controls (not findings)

- On-topic allowlist-hit follow-ups after BRCA1, three runs each, all on_topic (27 of 27): "show me the trials for it", "Is this gene linked to cancer?", "Explain that in plain language for a patient", "does it cause cancer in dogs?", "wat diseeses is it linkd to? cancer?", "Which drugs target it?", "What about its role in the cell cycle?", "How do those variants change the protein?", "can men get it too? breast cancer".
- After an ask-back (previous question "BRCA1"): "What about its role in breast cancer?" and "Which drugs target it?" on_topic 6 of 6; "Which cell phone is it best to buy this year?" off_topic 3 of 3.
- Off topic, refused 3 of 3 each: the cell phone question, "Is it a good time to buy shares in a gene therapy company?", the long follow-up burying a Paris itinerary, the two-biomedical-word nurse phone question, the Tesla commute question.
- Relevancy decision latency over 60 live calls: 0.26 s to 5.54 s; outliers 5.54 s and 4.91 s. The person now waits for the slower of this and the guard classifier on every memory-bound allowlist-hit follow-up; the guard classifier's own latency was not measured here (decide calls only), so the added wait on the healthy path is unmeasured.
### A-35-05: terse on-topic follow-ups with no referring word are refused as off topic in up to two runs of three (pre-existing, not a card 35 regression)

- Severity: minor (pre-existing on develop; the card's change does not touch this path, the grid probe shows identical verdicts on b01dee92 and cd0e65a8)
- What: a follow-up with no word from `_REFERRING_WORDS` and no allowlist hit is judged by `guardrail.relevancy` on its bare text, because `_relevancy_state` adds the previous question only for a memory-bound follow-up. The live decision then calls short continuations off topic, and its off_topic refuses.
- Reproduction: live, same harness as A-35-02, memory holding BRCA1, open thread "Which diseases are associated with BRCA1?". State sent is the bare text. Picks over three runs:
  - "and in mice?": on, on, on
  - "why?": off, on, off
  - "more": off, off, on
  - "¿y en ratones?": off, on, on
  - "what about kids": off, on, on
  Latency 0.69 s to 7.55 s.
- What a person sees: after a BRCA1 answer, typing "why?" or "more" is refused with "Outside biomedical research" most of the time, and "¿y en ratones?" or "what about kids" about one time in three. The card's fix narrows the off-topic leak but leaves this other side of the same rule, the referring-word list, deciding what the topic judge sees.
- NOT FIXED
## Verdict

PASS, with A-35-01 and A-35-02 for the owner's attention.

Verified with my own probes:

- Offline grid, 1920 cases (16 follow-ups, 3 memory states, 5 guard classifier outcomes including injection, junk twice and a hard error, 4 decision outcomes including no usable pick and a raising seam, Jev off and on), run on cd0e65a8 and on develop's graph.py: the only verdict changes are a real off_topic pick newly refusing an allowlist-hit memory-bound follow-up (48 cases). No failure of ours (no pick, seam down, junk reply) refuses an on-topic follow-up, and no injection is admitted.
- The grid is not vacuous: removing the card's `_guardrail_after_prefilter` clause makes it report 48 no-pick and seam-down refusals develop does not make.
- Slow decision: A-35-01, up to 15 s added on the fix, 0 s on develop.
- Live, 75 guard-tier decision calls: on-topic allowlist-hit follow-ups 27 of 27 on_topic; after an ask-back 6 of 6; off-topic follow-ups mostly off_topic, with the leaks in A-35-02 to A-35-04.
- `tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py`: 121 passed (the author's tests, run only as a sanity check).

Only read, not probed: Plain language mode (the guardrail never reads `audience_depth`, so it cannot change this path); a follow-up after a refusal (a refused question is not stored in memory, so it behaves as after the last answered question); the guard classifier's own live latency and verdicts (decide calls only, per the brief).

A-35-01 sits inside this card's own new condition in `guardrail_node`.

Credits: left 31.6258 before, 31.6122 after (shared key; other sessions may have spent part of the 0.0136).
