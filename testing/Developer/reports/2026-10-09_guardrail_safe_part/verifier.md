# Guardrail safe part (cards 84 and 72): fresh verifier

Branch fix/card84-72-guardrail-safe-part at 6f21e0fc, compared with develop b01dee92. Fresh context, read only, no live model calls. Findings are appended as they are established.

## Findings

### V-GRS-01: The grid test is honest: its record is develop's, the approved class change is the only difference, and verdict changes turn it red
- Severity: none (verified claim)
- What: `develop_decision_grid.json` equals develop's own verdicts, and `_APPROVED_CLASS_CHANGES` moves exactly the 192 two-unreadable-reply cases from "recoverable" to "transient" and nothing else.
- Reproduction: branch, `test_decision_grid_matches_develop.py`: "1 passed". The branch's test and JSON copied into an export of b01dee92: "192 of 768 verdicts differ from develop's, the approved class change applied: allowlisted | two unreadable replies | HTTP 429 ...: expected transient, now recoverable", 1 failed. Same export with the map's key renamed so no change applies: "1 passed in 2.97s". Mutations on the branch, each restored by `git checkout`: the class at graph.py 2144 to "unexpected": "192 of 768 verdicts differ", 1 failed; the relevancy refusal at 2314 inverted: "216 of 768", 1 failed; the injection choice at 2177 inverted: "52 of 768", 1 failed. `_expected_now` also asserts develop's record equals the "was" side for every case it rewrites, so the map cannot hide a recorded admit.
- Words only: the class feeds the web app's words, the MCP and CLI disclosure sentences (two unreadable replies now read "temporary error ... Retrying may succeed" and "Run 's3 ask' again" instead of "could not complete as requested"), and `useAgentRun`'s internal "run failed (transient)". The CLI's exit code is nonzero either way because the error is fatal; `retry_after_s` stays 0; nothing in `src/` or `frontend/src/` admits, retries or stores differently on "transient" for a guardrail step error (grep of every `error_class` reader).
- NOT FIXED (nothing to fix)

### V-GRS-02: My own grid, 27,240 cases including follow-up turns, gives develop's verdict in every case but the approved class change
- Severity: none (verified claim)
- What: no admit or refuse verdict differs between b01dee92 and 6f21e0fc. The only difference is the 5,448 two-unreadable-reply cases, "recoverable" on develop and "transient" here, each still a fatal guardrail step error.
- Reproduction: my own script (scratch, outside the checkout) drives the real `guardrail_node` on an export of each tree, stubbing only `litellm.acompletion` and `jev_client._post`. Axes: six questions (the tree-of-life one, an allowlisted one, a forbidden one, and three follow-up turns with BRCA1 in session memory: "And what about it in children?", "is it good pizza?", "Tell me a joke"); five guard outcomes (admit, off topic, injection, two unreadable replies, one unreadable then admit); 34 Jev replies per decision (stated 0.00002, 0, -0.0, 5e-324, 0.01, 0.0100001, 0.05, 12.5, 1e400, Infinity, NaN, -0.001, "0.00002", "abc", true, null, missing, a 401-digit and a 5001-digit integer, the other option, an option outside the set at $0 and at 0.00002, null probabilities, HTTP 500, 429, 402, 401, 404, 302, not JSON, empty, a JSON list, a body nested 100,000 deep, a read timeout, a connection error); both fallback picks. Relevancy was asked on both trees for the same four questions. Result: "verdict diffs 5448 of 27240", every one `{"step_error": ["guardrail", "recoverable"]} -> {"step_error": ["guardrail", "transient"]}`; "diffs outside two unreadable replies: 0". Develop's mix: off topic 8280, injection 6780, admitted 6660, step error 5448, write-seeking 72. No case raised on either tree.
- Limit: run at a $1.00 per-query cap. The cap sweep is V-GRS-05.
- NOT FIXED (nothing to fix)

### V-GRS-03: Every Jev charge follows the owner's rule as written, at every boundary, single and batch calls alike
- Severity: none (verified claim)
- What: the real `call_jev` and `call_jev_batch`, `_post` stubbed, charge the stated cost when it is finite, above $0 and at most $0.01, and $0.0001 otherwise; a timeout or a connection error is charged $0, since no reply came.
- Reproduction: my own probe (scratch), 142 cases: 30 stated costs (0, 1e-12, 5e-324, 0.00002, 0.0001, 0.00999999, exactly 0.01, the next float above 0.01, 0.0100000001, 0.05, 12.5, 1e308, 1e400, plus and minus Infinity, NaN, -0.001, -0.0, "0.005", "0.05", "1e309", "abc", true, false, null, missing, a 401-digit and a 5001-digit integer, a list, an object) times a usable choice and an option outside the set times single and batch; HTTP 500, 429, 402, 401 and 302; not JSON, empty, a list body, a body nested 100,000 deep; read timeout; connect error. Each was compared with the rule coded independently in the probe. Branch: "DIFFERS from rule: 0". Develop, same probe: "DIFFERS from rule: 110" (ceiling 0.01 above the cap and for unreadable amounts, $0 for a stated $0, -0.0 and false, $0 for error statuses, "ESCAPED RecursionError" for the deep body).
- Caps get these amounts: the three charge sites (`core/graph.py` `_jev_injection_pick`, `harness/decide.py` `_run_jev_pick`, `synthesis/sentence_check.py` `_ask_jev`) pass `result.cost_usd` or `exc.billed_cost_usd` to `Harness.track_cost`, unchanged. In my 27,240-case grid, every `track_cost` amount equals the client's charge (for example "HTTP500 dev [2e-05] br [2e-05, 0.0001]", "injection@0.05 dev [2e-05, 0.01] br [2e-05, 0.0001]", "injection@0.01 both [2e-05, 0.01]"). The most a question's guardrail is charged above develop: $0.0002. The sentence check's reservation, calls times $0.01, still covers the most any one reply is charged.
- As the rule allows: a stated 5e-324 is charged 5e-324, the same as develop (J-GRS-05, A-GRS-04, left by the lead).
- NOT FIXED (nothing to fix)

### V-GRS-04: Per-case words, probed: no failure a question can cause reads "the problem was ours"
- Severity: none (verified claim)
- What: I drove the real `guardrail_node` on both trees with the guard model's two attempts stubbed (litellm exceptions raised, or a prose reply), Jev answering normally, and read the step error's class; the words follow from `useRunView.ts`'s mapping (develop: `FATAL_COPY` by class; branch: source "guardrail" and class "transient" read the plain words, every other class keeps `FATAL_COPY`). "In a moment" is develop's transient line, "rephrase" its recoverable and unexpected line, "ours" the step 1 words.
- Reproduction (class, develop then branch; words, develop then branch):

| Guard attempts | Class | Words |
|---|---|---|
| timeout, timeout | transient, transient | in a moment, ours |
| timeout, unreadable | recoverable, transient | rephrase, ours |
| unreadable, timeout | transient, transient | in a moment, ours |
| 429, 429 | transient, transient | in a moment, ours |
| 500, 500 / 503, 503 / connection, connection | transient, transient | in a moment, ours |
| unreadable, unreadable | recoverable, transient | rephrase, ours |
| unreadable, 429 | transient, transient | in a moment, ours |
| unreadable, content policy / unreadable, 400 | recoverable, recoverable | rephrase, rephrase |
| content policy / 400 | recoverable, recoverable | rephrase, rephrase |
| timeout, content policy / timeout, 400 | recoverable, recoverable | rephrase, rephrase |
| 401, or unreadable then 401 | unexpected, unexpected | rephrase, rephrase |

- Every case a question can cause, a content-policy refusal or a 400, alone or after an unreadable reply or a timeout, keeps "rephrase" on the branch. `retry_after_s` was 0 in every case on both trees, so "in about N seconds" never shows yet (known, A-GR-01).
- NOT FIXED (nothing to fix)

### V-GRS-05: The log keeps reply text and key-shaped strings out, and the model call line is bounded
- Severity: none (verified claim)
- What: in my 27,240-case grid, no log record at any level, on either tree, held Jev's off-set choice (written to echo a person's health detail), an HTTP error body or a key-shaped string placed in that body. The branch's new Jev warnings name a fixed category, a length and an amount only. Every `log_model_call` caller passes `provider_of(response)`, and `provider_of` turned a router key, a bearer header, a JWT, a URL with a secret query value, a forged line break, an escape sequence, a 65-character and a 500-character name, and a 20-character hex-and-digit run into None ("unknown"). With 5,000-character values in every text field the line is 335 characters on the branch; develop wrote 20,136.
- Reproduction: grid markers, branch and develop alike: MARKCHOICE 0, MARKBODY 0, key prefix 0. Sample branch lines: "Jev's reply for decision 'guardrail.injection' could not be used: option_outside_set, reply length 276 bytes; it is charged $0.000020"; "Jev returned HTTP 500 for decision 'guardrail.injection', reply length 96 bytes; it is charged $0.000100". Develop for the same off-set reply logged no Jev line at all. Every `except JevCallError` handler (graph.py 1726, decide.py 316 and 379, sentence_check.py 681 and 799) logs `exc.reason` only.
- Limit: a key handed straight to `log_model_call(provider=...)`, bypassing `provider_of`, still prints its first 64 characters. No caller does that today (grep of every call site).
- NOT FIXED (nothing to fix)

### V-GRS-06: Multi-word provider names now log as "unknown", losing which host served a call for the line's own purpose
- Severity: minor
- What: `provider_of` drops any value with a space. Develop kept them.
- Reproduction: `provider_of(SimpleNamespace(provider=v))`. Develop: "Google AI Studio", "Google Vertex", "Amazon Bedrock", "Nebius AI Studio", "Atlas Cloud" and "Moonshot AI" are returned as given. Branch: None for all six, so the line says provider=unknown. One-word names ("Together", "DeepInfra", "Groq", "Inference.net", "Z.AI") are kept on both.
- Why it matters: nothing for a person; no answer, word or charge changes. For the operator, the line exists to rank upstream hosts for step 2 of the guardrail design (call_log.py's own docstring). Calls served by Google's two hosts, Amazon or Nebius all collapse into "unknown", together with calls that named no provider, so a week of lines cannot rank those hosts or tell them apart from a missing field. How much this matters depends on which hosts the guard model is routed to; I could not find the production guard model in the repository. Allowing single spaces between words, as the build report suggests, would keep them without letting a key through, since the credential checks run on each run between separators. Should be fixed before step 2 reads the lines; not a merge blocker.
- NOT FIXED

### V-GRS-07: A guard reply's first characters still reach the log when it is unreadable (pre-existing, same on develop)
- Severity: unsure (not introduced here)
- What: `core/graph.py` logs "guard classification unusable (attempt 1 of 2, trace ...): the guard tier did not return valid JSON; reply length 30, starts 'MARKREPLY I will look this up.'". The guard model's free text can echo the question, the concern A-GRS-05 raised for Jev's text.
- Reproduction: guard stub returning prose twice, both trees, WARNING level, the same line word for word.
- Why it matters: not worse than develop, outside this change's files' changed lines. Filed so the "no reply text reaches the log" claim is read as covering Jev's replies and the model call line only.
- NOT FIXED

### V-GRS-08: The fix agent's caveat: a question that makes the guard model reply in prose twice now reads "not with your question"
- Severity: minor (unsure whether it is a defect; not worse than develop for a person, in my judgement)
- What: two unreadable guard replies now read "We could not finish checking your question, so nothing was searched. This was a problem on our side, not with your question. Try asking again." If the question itself causes the prose replies, that sentence is false, and asking again fails the same way.
- Reproduction: guard stub returning prose twice: develop class "recoverable", words "Try asking again, or rephrase the question."; branch class "transient", the plain words (V-GRS-04 table). I did not find a real question that does this; the repository's own record (graph.py `_is_memory_bound_follow_up`) traces the prose replies of 2026-09-13 to a memory block in the guard prompt, since removed, and the three of 2026-09-29 to cut-off replies.
- Weighing it from the person's chair: nothing is admitted on either tree, so safety is unchanged. For the common cause, a cut-off reply, develop's "rephrase" was wrong and the new words are right. For a question written to break the guard, the person gains nothing from either message. The one person worse off is someone whose ordinary question happens to push the guard model into prose: told it was not their question, they may retry the same words twice before rephrasing, which develop would have prompted. That person is rare on the evidence above, and loses a retry, not an answer. Not worse than develop on balance; worth a test query if a real question of this kind is ever seen.
- NOT FIXED

### V-GRS-09: Inside this phase's own change: the charge comment at `_jev_injection_pick` now states the opposite of the code
- Severity: minor (a comment, no behaviour; it sits in lines this phase wrote at 3261eb47 and the fix round made wrong)
- What: `core/graph.py` line 1731, written by this phase, says a reply is charged "the ceiling when it states more"; since 6f21e0fc `jev_charge_usd` charges the floor above the ceiling. The build report lists it as left open because the round touched nothing else in graph.py.
- Reproduction: `grep -n "ceiling when it states more" src/system_03_search_agent/core/graph.py` gives line 1731; my charge probe gives "single choice=a stated=0.05 -> malformed_reply charged 0.0001".
- Why it matters: the next person changing the guardrail's charges reads a rule the code no longer follows, the same paraphrase drift DECISIONS.md's row of 2026-10-09 names as the reason for applying the rule as written. A one-line fix. Also left: `_log_step_failed("guardrail", "recoverable", ...)` logs "recoverable" for a step error the wire now calls "transient", so an operator matching log lines to screens sees two classes.
- NOT FIXED

### V-GRS-10: Under a per-query cap of about one to two cents, verdicts differ from develop in both directions; at $0.10 and $0.25 none do
- Severity: minor (unreachable at develop's $0.25 cap; widens A-GRS-02, which named one direction only)
- What: with the cap between about $0.0105 and $0.02, develop's $0.01 ceiling charge for an unreadable Jev reply trips the cap and skips the guard fallback; the branch's $0.0001 floor does not, so the fallback decides. On the branch, a tight cap gives exactly the verdict both trees give at a normal cap.
- Reproduction: my reduced grid (4,920 cases per cap, same axes as V-GRS-02 with 12 injection and 10 relevancy replies), both trees. Caps $0.0105, $0.013 and $0.02: 660 differences outside the approved class change each: 464 develop admitted, branch refuses as off topic; 116 develop refused as off topic, branch admits (follow-ups "And what about it in children?" and "is it good pizza?" with the fallback saying on topic, for example "fu-pizza | offtopic | HTTP500 | notjson | on_topic"); 64 injection to off topic; 16 off topic to injection. All 660 branch verdicts equal develop's at a $1 cap ("branch equals develop at $1: 660"). Caps $0.1 and $0.25: 0 differences. Caps $0.0003 to $0.004: every case stops at the cap on both trees.
- Why it matters: a deployment with a cap near a cent would see a few verdicts move toward what the guardrail gives at a normal cap, including some admits. Develop runs at $0.25, so no person sees it today.
- NOT FIXED

### V-GRS-11: Two harness tests failed once under heavy machine load, then passed
- Severity: unsure (not in this change's files)
- What: `tests/system_03_search_agent/harness` gave "2 failed, 560 passed in 63.55s" while eight of my grid runs were loading the machine, `test_opus_writer.py::test_the_old_writer_is_never_priced_below_the_static_estimate` among them. Alone it passed, and the whole directory unloaded gave "562 passed in 27.29s". `test_opus_writer.py` and `harness.py` are not in the diff from b01dee92.
- Why it matters: a load-sensitive test can fail CI by chance; it says nothing against this branch.
- NOT FIXED

## Test runs

| Run | Result |
|---|---|
| `test_decision_grid_matches_develop.py`, branch | "1 passed" |
| The same test and JSON on an export of b01dee92 | "192 of 768 verdicts differ", only the approved class change; "1 passed" with the change switched off |
| `tests/system_03_search_agent/guardrail` | "353 passed in 70.79s" |
| `tests/system_03_search_agent/harness` | "562 passed in 27.29s" (see V-GRS-11 for one loaded run) |
| `synthesis/test_sentence_check.py` and `test_sentence_pair_check.py` | "146 passed in 3.20s" |
| `npx vitest run src/hooks/useRunView.retryAfter.test.ts` | "Tests  11 passed (11)"; with the class check widened to every class but "cancelled", "3 failed"; with the guardrail source check removed, "1 failed"; both restored |
| `npx tsc --noEmit -p .` | exit 0 |
| `ruff check` (no path) | "All checks passed!", exit 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |

## Verdict

PASS against the overnight merge bar: nothing is worse than develop for a person, and the fix round's claims hold.

Verified with my own probes:
- Admit and refuse verdicts equal develop's: 27,240 cases at a $1 cap across guard outcomes, 34 Jev replies per decision and three follow-up turns, plus cap sweeps from $0.0003 to $0.25 (V-GRS-02, V-GRS-10). The only difference at develop's own $0.25 cap is the approved class change.
- The grid test's record is develop's, `_APPROVED_CLASS_CHANGES` changes only the 192 two-unreadable-reply cases, and three verdict mutations turn it red (V-GRS-01).
- The class change changes words only, on the web, MCP and CLI surfaces (V-GRS-01, read of every `error_class` reader).
- Per-case words for 17 guard failure sequences on both trees; no failure a question can cause reads "ours" (V-GRS-04).
- Every Jev charge follows the owner's rule as written, single and batch, 142 cases, and the caps receive those amounts (V-GRS-03).
- No Jev reply text or key-shaped string reaches the log; the line is bounded at 335 characters for 5,000-character inputs (V-GRS-05); multi-word providers now log as "unknown" (V-GRS-06).
- The web test bites under two mutations of the mapping.

Read, not probed:
- The web app's words themselves: I mirrored `useRunView.ts`'s mapping in my probe and ran its test, but did not render a screen.
- That no real question makes the guard model reply in prose (V-GRS-08); I relied on the repository's record.
- Which hosts the production guard model is routed to (V-GRS-06).
- A real timeout and the pause path: my timeouts were raised at once; the change touches no wait.

Inside this phase's own fix: V-GRS-09, a comment this phase wrote that the fix round made wrong. Minor, no behaviour.

MERGE. No finding blocks. V-GRS-06 (multi-word provider names log as "unknown") and V-GRS-09 (the stale charge comment) are worth one small follow-up before step 2 reads the log lines.
