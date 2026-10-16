# Judge review: guardrail safe part (cards 84 and 72)

Branch fix/card84-72-guardrail-safe-part at 664e0e5b, base develop b01dee92. Fresh-context judge, 2026-10-09.

## Findings

### J-GRS-01: Check 1 verified: the guard admits and refuses exactly what develop does, on the builder's grid and on a wider grid of my own

- Severity: none (verified claim)
- What: the recorded `develop_decision_grid.json` is develop's real behaviour, not a copy that drifted. I exported develop's tree at b01dee92 (`git archive`) into a scratch folder, dropped the branch's grid test and JSON into it, and ran it there: "1 passed in 5.05s" (the import resolved to the export's `jev_client.py`, which has no `JEV_FLOOR_COST_USD`). So the JSON equals develop's code at b01dee92.
- My own grid, live on both trees, no frozen file: 5,920 cases, the builder's question, classifier and fallback axes with my own Jev reply axis (stated cost 2e-5, 1e-300, 5e-324, exactly 0.01, 0.0100000001, NaN, -0.001, -0.0, "0.00002" as a string, "abc", true, a 401-digit integer, 1e400, null, missing, -Infinity, `usage: null`, a JSON list body, an empty 200, HTTP 401 and 402, for both injection picks and both relevancy picks). Result: "differ 0 of 5920". Verdict mix on develop: off topic 1887, injection 1648, step error 1480, admitted 868, read-only 37. Repeated with the per-query cap at $0.0005, $0.005 and $0.00003: "differ 0 of 5920" each.
- Mutations, each restored with `git checkout` (`git status` clean after): graph.py line 2306 `relevancy == "off_topic"` to `"on_topic"`: "216 of 768 verdicts differ from develop's", 1 failed. graph.py line 2169 `jev.choice == "injection"` to `"not_injection"`: "52 of 768 verdicts differ", 1 failed. The test bites.
- Limits, read not probed: the grid has no follow-up turn with session memory, no timeout and no pause. That is acceptable because the branch's source diff touches only charge amounts, comments, and the log line, never a wait or a branch of the verdict logic (I read the whole `src/` diff). The JSON is a snapshot of b01dee92: once develop's guardrail changes legitimately, this test goes red and must be re-recorded, so it is a pin, not a live comparison.
- NOT FIXED (nothing to fix)

### J-GRS-02: Step 3a boundaries, the real `call_jev` and `call_jev_batch` on develop's tree and the branch's

- Severity: none for the rows that match the rule; the deviations are filed as J-GRS-03 to J-GRS-06
- Reproduction: my probe (scratch, not committed) replaces `jev_client._post` and calls the real `call_jev` on an export of b01dee92 and of 664e0e5b. Pasted, "develop -> branch":
  - stated 0: "usable charged 0.0" -> "usable charged 0.0001"; -0.0: "-0.0" -> "0.0001"
  - 5e-324: "usable charged 5e-324" both; 1e-300: "1e-300" both; 2e-5: "2e-05" both; "0.00002" as a string: "2e-05" both
  - exactly MAX 0.01: "usable charged 0.01" both
  - 0.0100000001, 0.05, 12.5, int 1, a 401-digit integer: "malformed_reply charged 0.01" both
  - Infinity, -Infinity, 1e400, NaN, -0.001, missing, null, "abc", "Infinity", true: develop "charged 0.01", branch "charged 0.0001"
  - an option outside the set at stated 0: develop "invalid_option charged 0.0", branch "0.0001"; at 2e-5: "2e-05" both
  - not JSON, empty body, a JSON list: develop 0.01, branch 0.0001; a body nested 100,000 deep: develop "ESCAPED RecursionError" (uncharged), branch "malformed_reply charged 0.0001"
  - HTTP 500, 429, 402, 401, 404, 302: develop "http_error charged 0.0", branch "http_error charged 0.0001"
  - transport failure: "http_error charged 0.0" both (no reply came, nothing charged)
  - `call_jev_batch`, the sentence check's path: the same pattern ("0 usable 0.0 -> 0.0001", "0.05 malformed 0.01 both", "Infinity/NaN/-1/missing/"x" 0.01 -> 0.0001", "HTTP 500 0.0 -> 0.0001").
- What matches the owner's row of 2026-09-29: above $0 and at most MAX is charged as stated (including 2e-5, so V-GR-11 is not present here); $0, missing and unreadable amounts are charged the floor, never $0; an error status is charged the floor. Never $0 for a reply that came back, except the J-GRS-05 case.
- Compared with develop, no reply is charged more except a stated $0 (0 -> 0.0001) and an error status (0 -> 0.0001), both by the owner's rule.
- NOT FIXED (verified claim)

### J-GRS-03: A reply stating more than MAX_JEV_COST_USD is charged the $0.01 ceiling; the owner's row, read literally, says the floor

- Severity: unsure (over-charge relative to the literal rule; same as develop; follows the design's step 3a)
- What: the DECISIONS.md row of 2026-09-29 reads "charged the cost it states when that is above $0 and at most `MAX_JEV_COST_USD`, otherwise a floor near Jev's real price, about $0.0001". A stated cost above MAX falls under "otherwise". The branch charges it $0.01, 100 times the floor. The design's step 3a chose this on purpose ("A stated cost above $0.01 is charged the $0.01 ceiling, not the floor (fixes F-84-A06)"), and develop charges the same $0.01. The approval row of 2026-10-09 says "exactly by the owner's rule of 2026-09-29 (step 3a ...)", which names both texts, and they disagree here.
- Reproduction: "0.0100000001 | malformed_reply charged 0.01", "0.05 | malformed_reply charged 0.01", "12.5 | malformed_reply charged 0.01", "int 1 | malformed_reply charged 0.01" on the branch (J-GRS-02 probe). `jev_charge_usd`: `if stated_usd > MAX_JEV_COST_USD: return MAX_JEV_COST_USD`.
- Why it matters: per such reply the caps count $0.0099 more than the literal rule. A units slip in Jev's endpoint (the 12.5 incident of F-8.6-V01) would charge a cent per call, as develop does today. It is the owner's words against the design's; the owner should say which reading stands. Not worse than develop.
- NOT FIXED

### J-GRS-04: Charge is not monotone in the stated cost past the largest float: 0.05 is charged $0.01, 1e400 and Infinity $0.0001

- Severity: minor
- What: a JSON number above about 1.8e308 (for example `1e400`) parses as Infinity and is charged the floor, while 0.05 and a 401-digit integer literal are charged the ceiling. The design cites F-84-A06 ("the more a reply says it cost, the more is counted") as the reason above-MAX gets the ceiling; Infinity and 1e400 break that same principle. build.md records that the lead read Infinity as unreadable on 2026-10-09, so this is a disclosed reading, but `1e400` written as a plain number is not named anywhere.
- Reproduction: branch "1e400 | malformed_reply charged 0.0001", "Infinity | malformed_reply charged 0.0001", "0.05 | malformed_reply charged 0.01", "401-digit int | malformed_reply charged 0.01".
- Why it matters: little in money (a reply is unusable either way, and the floor is the owner's own figure for unreadable). Filed so the owner sees the two readings disagree with each other.
- NOT FIXED

### J-GRS-05: A usable reply stating a vanishingly small positive cost (1e-300, 5e-324) is charged that, so the caps see about $0; A-GR-03 is open again

- Severity: minor (unsure whether it is a defect: the literal rule allows it, and the owner approved leaving out the fix round's floor change)
- What: `jev_charge_usd` charges any stated cost above $0 as stated. 5e-324 is above $0, so a reply that reached the provider is counted as effectively nothing, which the rule's "never $0" was written to prevent. The parked fix round closed this (V-GR-11's probe: "stated 1e-300: usable charged 0.0001") but did so by overcharging every real reply. The approval row excludes that change, so this is the expected consequence, not a builder slip.
- Reproduction: branch "5e-324 | usable charged 5e-324", "1e-300 | usable charged 1e-300". Develop the same.
- Why it matters: only reachable if Jev states a nonsense tiny cost; then the per-query, per-user and daily caps are blind to those calls, as on develop. A narrow fix (a floor only below, say, a tenth of Jev's measured $0.0000148) was suggested in J-GR-04 and was not taken. Owner's call.
- NOT FIXED

### J-GRS-06: An HTTP 401, 404 or 302 from Jev is charged the $0.0001 floor, though such a reply is not one the provider billed

- Severity: unsure
- What: every non-200 status is charged the floor (`_send`), not only the 500, 429 and 402 the design names. A 401 means our key was refused and a 404 or 302 that the endpoint moved; neither is a call a model provider billed. With a revoked key, every question carries the floor charge for every Jev call (about three per question) for nothing.
- Reproduction: branch "HTTP 401 | http_error charged 0.0001", "HTTP 404 | http_error charged 0.0001", "HTTP 302 | http_error charged 0.0001"; develop "charged 0.0" for each.
- Why it matters: small in money (about $0.0003 a question), but it is a charge outside the design's named statuses. The owner's row says "a Jev reply that reached the provider", which a 401 arguably did not.
- NOT FIXED

### J-GRS-07: Step 1 verified: only a guardrail failure classed "transient" reads the new words, and every such failure is one where nothing was searched and the question was not at fault

- Severity: none (verified claim, part read and part probed)
- What I read: the graph's entry point is `guardrail` (`set_entry_point("guardrail")`, graph.py line 15104) and no task started inside `guardrail_node` searches anything, so no run with a guardrail step error has searched. The only builder of a source "guardrail" error is `_guardrail_after_prefilter` (graph.py, `_step_error_kwargs("guardrail", ...)` and the literal at line 2135). Class "transient" comes from `harness._TRANSIENT_EXCEPTIONS` (rate limit, connection error, timeout, 503, 500, 502) or the budget-spent arm, all provider or our side. A content-policy refusal, a 400, a context-window error and an unprocessable entity are "recoverable" and keep "Try asking again, or rephrase the question"; a 401 is "unexpected" and keeps develop's line.
- What I probed: `npx vitest run src/hooks/useRunView.retryAfter.test.ts`: "Tests  11 passed (11)"; `npx tsc --noEmit -p .`: exit 0. Mutation 1, the class test widened to `!== "cancelled"` (A-GR-10's bug): "4 failed", the content-policy, 400, two unreadable replies and 401 cases. Mutation 2, the source test removed: "Tests  1 failed | 10 passed (11)", the other-step case. Both restored with `git checkout`.
- No case found where something was searched, or the question was at fault, and the person is told "nothing was searched, the problem was ours".
- NOT FIXED (verified claim)

### J-GRS-08: Two unreadable guard replies still read "Try asking again, or rephrase the question", because the approved A-GR-10 fix was taken only in part

- Severity: minor (same words as develop, so not worse; but short of what was approved)
- What: the approval row of 2026-10-09 reads "step 1 with its A-GR-10 fix". That fix, 3592e856, has two halves: the web app's class test, taken, and a one-line class change in `core/graph.py` `_guardrail_after_prefilter` sending two unreadable guard replies as "transient", left out as outside the builder's file fence. The design's step 1 names exactly two cases its words are for, "both the double timeout and two unreadable replies". So one of the two cases does not get them.
- What a person sees: when the guard model answers twice with something unreadable, nothing was searched and the fault was ours, yet the screen reads develop's "This run could not be completed. Try asking again, or rephrase the question." They may rewrite a perfectly good question. Asking again unchanged would very likely work.
- Reproduction: graph.py at 664e0e5b, the `if classifier_verdict is None:` block, `"error_class": "recoverable"`; the decision grid's own verdicts for every "two unreadable replies" case: `{"step_error": ["guardrail", "recoverable"]}` (1480 of my 5,920 cases); the web test "two unreadable replies, sent as 'recoverable' today, read develop's words" pins develop's text.
- Why it matters: build.md discloses it. It is not a regression, but the card's step 1 is half done for the reader, and the lead should decide whether the fence or the approval governs.
- NOT FIXED

### J-GRS-09: Step 3c verified for control characters, line breaks, escape sequences and log-field injection; the line stays at WARNING

- Severity: none (verified claim)
- Reproduction: my probe calls the real `provider_of` on both trees, develop -> branch: "Groq\nERROR fake line" -> "GroqERROR fake line"; "\x1b[31mRed\x1b[0m" -> "31mRed0m"; "x outcome=ok trace=t-evil" -> "x outcomeok tracet-evil" (no "=" so no forged field); a Cyrillic look-alike with U+202E and U+200B -> "Grq"; "%s%s%n" -> "ssn"; tab, CR and NUL dropped; "/:?#" -> None; 200 letters capped at 64; a non-string -> None. The emitted line on the branch: "model call point=p trace=t kind=guard elapsed_ms=... outcome=ok attempt=1 provider=GroqINJECTED" (develop: "provider=Groq\nINJECTED", a forged second line). `log_model_call` still calls `logger.warning(`; the docstring change only renames the condition for lowering it.
- NOT FIXED (verified claim)

### J-GRS-10: A key-shaped string or the text of a URL path in the router's provider field still reaches the log line

- Severity: minor (the brief's check 4 fails as worded; disclosed by the builder; not worse than develop; the source is the router's reply, not user input)
- What: the kept character set (ASCII letters, digits, dots, hyphens, spaces) is every character a router key uses, and a URL loses only its punctuation. So a key-shaped value is logged as is, truncated at 64 characters, and a URL's path, query and fragment survive run together.
- Reproduction (branch, real `provider_of`; the key is a fake assembled at run time, shown here as placeholders): "<router-key prefix><64 hex characters>" -> "<router-key prefix><first 55 hex characters>", unchanged but cut at 64; "Bearer <same fake key>" -> "Bearer <router-key prefix><first 48 hex characters>"; "https://api.example.com/v1/keys?q=abc#frag" -> "httpsapi.example.comv1keysqabcfrag".
- Why it matters: if the router ever echoed a credential or a signed URL in `provider`, it would land in the deployment log at WARNING on every call. Unlikely, but the brief asked that no secret, key or URL path can reach the line, and that is not true. A shape check (reject a value with a known key prefix, or a run of 16 or more letters and digits, or anything longer than a host name) would close it. build.md's "Left open" names it as out of this part's scope.
- NOT FIXED

### J-GRS-11: An error-status reply is charged the floor with no warning, though the module docstring and the debugging guide say a warning names every charge that is not the stated cost

- Severity: minor (observability and doc accuracy; no person sees it)
- What: `jev_client.py`'s docstring says "It writes one warning whenever a reply is not charged the cost it states, naming the amount", and the debugging guide's `jev_client` row says "a warning names it whenever it is not the stated cost". `_send` raises the floor-charged `JevCallError` for a non-200 status without logging. The guide's row also names only "500, 429, 402", while every non-200 status is charged (J-GRS-06).
- Reproduction: my probe, branch, the real `call_jev` with a capturing handler on `jev_client.logger`: "500 charged 0.0001 | warnings: ''"; for comparison "200 charged 0.0001 | warnings: \"Jev's reply for decision 'q' could not be used: it could not be read as JSON (JSONDecodeError); it is charged $0.000100\"".
- Why it matters: someone reading the log to reconcile counted Jev spend against the stated costs finds error-status charges with no line naming them. The exception message does carry "it is charged $0.000100", so callers that log it see it.
- NOT FIXED

### J-GRS-12: Test query 109's "Why it matters" credits the change with the case it leaves alone

- Severity: minor (document accuracy)
- What: `testing/Test_queries_and_workflows.md`, query 109, says "before this, a person whose question was fine was told to rephrase it". The failure this query covers, the double timeout, was "transient" on develop and read "This run could not be completed. Try asking again in a moment." (develop's `FATAL_COPY.transient`, read at b01dee92), never "rephrase". The case that told a fine question to rephrase, two unreadable replies, still does (J-GRS-08), as the same query's own "What you should see" says.
- Reproduction: `git show b01dee92:frontend/src/hooks/useRunView.ts`, `FATAL_COPY`: transient "Try asking again in a moment."; query 109's last bullet.
- Why it matters: the owner testing query 109 is told the change fixed something it did not.
- NOT FIXED

### J-GRS-13: None of the findings that parked the earlier attempt is present

- Severity: none (verified claim)
- What: V-GR-01, V-GR-04, V-GR-05, V-GR-08 and V-GR-09 all sit in step 3b, the server-pause wait. `grep` for `wait_counting_free_time`, `PausedTimeoutError`, `JEV_STALL_ALLOWANCE_S`, `jev_failed`, `_await_jev_own_pick` and `jev_injection_unknown` across `src` and `tests`: 0 lines. The `core/graph.py` diff is comment lines only (every added or removed line is a comment). V-GR-11, the fix round's floor raising $0.00002 to $0.0001: not present, "2e-5 | usable charged 2e-05" on the branch (J-GRS-02).
- NOT FIXED (verified claim)

### Runs, for the record

- Tests for the changed files: grid test, `test_call_log.py`, `test_decide.py`, `test_jev_client.py`, `test_jev_cost_bounds.py`, `test_jev_followup_costs.py`, `synthesis/test_sentence_check.py`: "338 passed in 32.89s". `tests/system_03_search_agent/guardrail` and `tests/system_03_search_agent/harness` together: "861 passed in 81.21s".
- `npx vitest run src/hooks/useRunView.retryAfter.test.ts`: "Tests  11 passed (11)". `npx tsc --noEmit -p .`: exit 0.
- `ruff check` (no path): "All checks passed!". `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0 ("Skipped 2 files").
- These are the author's tests; my verdict rests on the probes in J-GRS-01, 02, 07, 09 and 13.

## Verdict

MERGE.

Verified by my own probes: the guard's verdicts equal develop's real code (the recorded JSON rerun on an export of b01dee92, and my own 5,920-case grid live on both trees at four cap settings, 0 differences); the grid test goes red on two guard mutations (216 and 52 differences); the charge at every boundary through the real `call_jev` and `call_jev_batch` on both trees; the web words by two mutations; `provider_of` on hostile inputs on both trees and the line's WARNING level; the absence of step 3b and of V-GR-11.

Only read, not probed: that no source "guardrail" transient error can follow a search (from the graph's wiring and the one builder of such errors); the classes `harness._classify_exception` gives each provider error; the non-web surfaces (they are unchanged).

Nothing here is worse than develop for a person. Open items: J-GRS-03 (above the ceiling charged $0.01, the owner's row read literally says the floor; same as develop) and J-GRS-05 (a near-zero stated cost charged as stated) are the owner's to settle; J-GRS-08 (two unreadable replies keep "rephrase", the approved A-GR-10 backend half left out) is the lead's scope call; J-GRS-10 (key-shaped text still reaches the log) fails check 4 as worded but is not worse than develop; J-GRS-11 and J-GRS-12 are small doc corrections, J-GRS-12 worth fixing before the owner runs query 109. No finding sits inside a fix made during this phase.
