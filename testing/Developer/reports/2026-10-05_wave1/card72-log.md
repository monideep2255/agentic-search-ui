# Card 72, logging half: one log line per classifier-model call

## Table of contents

- [The change](#the-change)
- [Tests](#tests)
- [Gates](#gates)
- [Not covered](#not-covered)

## The change

When a search ends with "This run could not be completed" because the guard model did not answer, the deployment log now says how long each call took and how it ended. Nothing else changed: no timeout, retry, verdict or fail-open or closed rule.

- New `harness/call_log.py`: `log_model_call` writes one WARNING line, `model call point=... trace=... kind=... elapsed_ms=... outcome=... attempt=... provider=...`. It never raises.
- Outcomes: ok, timeout, rate_limited, error, unusable_reply.
- Guardrail classifier call (`core/graph.py`): one line per attempt, point `guardrail.classify`, attempt 1 or 2.
- Guard-tier call inside `decide()` (`harness/decide.py`): one line per call, point is the decision point.
- Jev decision call in `decide()` and Jev's `guardrail.injection` call: one line each, kind `jev`.
- Provider: `LLMResponse` gains `provider` (default None), read from the router's reply when it carries a plain string. Failed and timed-out calls have no reply, so they read "unknown".
- The line carries no question text, prompt, reply text, token count or cost.

## Tests

`tests/system_03_search_agent/harness/test_call_log.py`, 19 tests: fields on success, timeout, error, rate limit and unusable reply, for the guardrail node and for `decide()` in guard and Jev mode (Jev timeout, http error, malformed reply, invalid option), a two-attempt guardrail run, a provider-less reply, a logging fault that never reaches the caller, and a test that a question marker, a reply marker and the words token, cost, prompt and content never appear in any line.

Red on old code: with the `src` changes removed, 17 of the 19 fail (the two that pass test `provider_of` and the logging fault guard, which live in the new module only).

## Gates

- Gate 2 (import order): green.
- Gate 3 (ruff, whole repository): green after one fix (use `contextlib.suppress`).
- Gate 4 (unit suite): 6819 passed, 2 failed. Both failures were the debugging guide coverage arms asking for a row and a manifest entry for the new file. Fixed (row in `docs/build/Debugging_guide.md`, manifest regenerated); the two arms and the new tests were re-run green. The full suite was not re-run after that fix.

## Not covered

- Whether a live router's reply carries a `provider` field on the object litellm returns. Stubs only; the first deployed log line shows it. If it reads "unknown" on every line, the field needs reading from litellm's hidden params instead.
- The line is logged at WARNING, deliberately: the service sets no root log level, so INFO is dropped before it reaches the deployment log. Lower it to INFO after the guardrail decision. It adds about three lines per search.
- `think` and other plan-tier calls are not logged; the card asked for the guard tier and Jev.
