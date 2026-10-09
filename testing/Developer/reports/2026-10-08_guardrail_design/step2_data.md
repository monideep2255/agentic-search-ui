# Step 2 data: host order and slow-call clustering

Written 2026-10-08 by a diagnosis worker. Read-only: no code changed, no model call made, no Railway state changed.

## Table of contents

- [In one minute](#in-one-minute)
- [1. Does the router honour a host order per request](#1-does-the-router-honour-a-host-order-per-request)
- [2. What the develop log shows](#2-what-the-develop-log-shows)
- [3. What the data does not cover](#3-what-the-data-does-not-cover)

## In one minute

- Router honours a per-request host order: yes, per OpenRouter's documented `provider` request field (`order`, `allow_fallbacks`, `only`, `ignore`, `sort`). Working argument path: `extra_body={"provider": {"order": ["<Host>"], "allow_fallbacks": true}}` added to the `request` dict that `call_tier` passes to `litellm.acompletion` (`src/system_03_search_agent/harness/harness.py:635` builds it, `:654` sends it). Checked offline with the installed LiteLLM 1.93.0: the `provider` object lands as a top-level key of the request body. Not checked against the live router (no credit spent).
- The reply names the serving host: yes, in a top-level `provider` field. Our code already reads it (`harness/call_log.py` `provider_of`, used at `harness.py:732`). OpenRouter's routing page does not document this response field; the develop log proves it is present.
- Slow calls cluster on one host: cannot be told. All 5 timeouts name no host, and no completed call went over 10 s.
- Recommendation: not enough data to pick hosts. Missing: the host of a timed-out call, and a longer window with a real slow spell (develop's log kept only 3.5 days and 197 guard lines).
- What the data does say: all 5 timeouts (2.6% of 189 first attempts) recovered on attempt 2, on a different host each time (1.4 to 3.9 s). That supports the idea of steering attempt 2, but does not show a single bad host.

Ranked hosts (guard call, `ok` replies only; small samples):

| Rank by median | Host | Calls | Median s | p95 s | Max s | Note |
|---|---|---|---|---|---|---|
| 1 | Relace | 23 | 0.65 | 1.66 | 5.15 | 1 unusable reply |
| 2 | Alibaba | 6 | 1.17 | 1.36 | 1.36 | n too small |
| 3 | Baidu | 3 | 1.22 | 3.48 | 3.48 | n too small |
| 4 | Parasail | 7 | 1.48 | 2.21 | 2.21 | n small |
| 5 | Novita | 6 | 1.50 | 1.85 | 1.85 | n small |
| 6 | GMICloud | 14 | 1.59 | 2.62 | 2.62 | |
| 7 | StreamLake | 64 | 2.00 | 6.74 | 8.68 | most traffic |
| 8 | DigitalOcean | 18 | 2.14 | 9.43 | 9.43 | slowest p95 of the larger hosts |

If the lead must choose now, provisional only: attempt 1 Relace, attempt 2 GMICloud (largest fast host after Relace). Relace has 1 unusable reply in 23, and AtlasCloud had 3 unusable replies in 8 (avoid it for attempt 2). Treat this as a guess until a slow spell is in the log.

## 1. Does the router honour a host order per request

OpenRouter's provider routing page (https://openrouter.ai/docs/features/provider-routing), read 2026-10-08:

| Field | Meaning |
|---|---|
| `order` | Providers to try in sequence, e.g. `"order": ["anthropic", "openai"]` |
| `allow_fallbacks` | Default true. False restricts routing to the named providers only |
| `only` | Whitelist of providers |
| `ignore` | Blacklist of providers, merged with account-wide ignores |
| `sort` | `"price"`, `"throughput"` or `"latency"`, instead of load balancing |

Our code, how the guard call is built:

| Where | What |
|---|---|
| `harness/harness.py:570` | `call_tier(tier, messages, *, cache_prefix, max_tokens)`: no argument for a host today |
| `harness/harness.py:635-645` | `request` dict: `model` (`openrouter/<id>`), `messages`, `reasoning`, `max_tokens`. No `extra_body`, no `provider` |
| `harness/harness.py:654` | `litellm.acompletion(**request)`. The same dict is resent unchanged on a transient retry and on the reasoning resend, so a host order added to `request` rides every resend |
| `harness/harness.py:732` | `provider=provider_of(response)` fills `LLMResponse.provider` |
| `harness/call_log.py` | `provider_of` reads the reply's top-level `provider` string; `log_model_call` writes the line |

Argument path that works: LiteLLM accepts `extra_body` for OpenRouter and merges it into the request body (`litellm/main.py` around line 3230, `litellm/llms/openrouter/chat/transformation.py` lines 158-160). Offline test with installed LiteLLM 1.93.0 (`get_optional_params` then `OpenrouterConfig.transform_request`, no network): input `extra_body={"provider": {"order": ["Relace"], "allow_fallbacks": True}}` produced a body with a top-level `provider` key holding that object. So the build is a new optional `provider_order` argument on `call_tier` that sets `request["extra_body"] = {"provider": {...}}`.

One design note from the data: with `allow_fallbacks: false` and a single host in `order`, the host of attempt 1 is known to us even when the call times out, which closes the "timed-out call names no host" gap. With `allow_fallbacks: true` it does not.

## 2. What the develop log shows

Source: Railway project `system3-search-agent-develop`, service `search-agent-api`, environment `develop`, deploy log, filter `"model call point=" "kind=guard"`, read-only `get-logs`. Line format (`call_log.py`): `model call point=<point> trace=<id> kind=<guard|jev> elapsed_ms=<n> outcome=<ok|timeout|rate_limited|error|unusable_reply> attempt=<n> provider=<name|unknown>`.

Window actually returned: 2026-10-05 18:01 UTC to 2026-10-08 06:56 UTC. Target was 7 days; Railway kept only the deployments since #159 reached develop, and the earlier ones are gone. The query returned 197 lines against a cap of 500, so it is the complete retained set.

| Item | Value |
|---|---|
| Guard lines | 197 (attempt 1: 189, attempt 2: 8) |
| Per day (UTC) | 2026-10-05: 92, 10-06: 18, 10-07: 13, 10-08: 74 |
| Decision point | all `guardrail.classify` |
| Outcomes | ok 188, timeout 5, unusable_reply 4, rate_limited 0, error 0 |
| Guard model id | not in the log line. Code default is `deepseek/deepseek-v4-flash` (`harness/tiers.py:54`, overridable by the `GUARD_MODEL` variable, which I did not read) |

Guard calls by host (median and p95 over `ok` replies; max over all calls of that host):

| Host | Calls | ok | Median s | p95 s | Max s | Over 10 s | Not ok |
|---|---|---|---|---|---|---|---|
| StreamLake | 64 | 64 | 2.00 | 6.74 | 8.68 | 0 | 0 |
| Relace | 23 | 22 | 0.65 | 1.66 | 5.15 | 0 | 1 |
| DigitalOcean | 18 | 18 | 2.14 | 9.43 | 9.43 | 0 | 0 |
| OpenInference | 16 | 16 | 2.76 | 6.61 | 6.61 | 0 | 0 |
| GMICloud | 14 | 14 | 1.59 | 2.62 | 2.62 | 0 | 0 |
| Venice | 10 | 10 | 1.98 | 8.08 | 8.08 | 0 | 0 |
| AtlasCloud | 8 | 5 | 1.56 | 2.36 | 2.75 | 0 | 3 |
| Parasail | 7 | 7 | 1.48 | 2.21 | 2.21 | 0 | 0 |
| Alibaba | 6 | 6 | 1.17 | 1.36 | 1.36 | 0 | 0 |
| Novita | 6 | 6 | 1.50 | 1.85 | 1.85 | 0 | 0 |
| DeepInfra | 6 | 6 | 1.56 | 3.94 | 3.94 | 0 | 0 |
| SiliconFlow | 5 | 5 | 2.86 | 3.10 | 3.10 | 0 | 0 |
| Baidu | 3 | 3 | 1.22 | 3.48 | 3.48 | 0 | 0 |
| Azure | 2 | 2 | 1.89 | 2.47 | 2.47 | 0 | 0 |
| Wafer | 2 | 2 | 1.43 | 1.67 | 1.67 | 0 | 0 |
| Mancer | 2 | 2 | 1.44 | 1.44 | 1.44 | 0 | 0 |
| unknown (cut off) | 5 | 0 | n/a | n/a | 10.00 | 0 | 5 |

Over-10 s counts are 0 because the first attempt is cut at 10 s; the 5 cut-offs read 9.99 to 10.00 s and are the "slow" calls.

The 5 timeouts, with what attempt 2 did:

| Day (UTC) | Attempt 1 | Attempt 2 host | Attempt 2 s |
|---|---|---|---|
| 10-05 | timeout, host unknown | StreamLake | 1.6 |
| 10-05 | timeout, host unknown | Novita | 1.8 |
| 10-05 | timeout, host unknown | DigitalOcean | 3.9 |
| 10-05 | timeout, host unknown | GMICloud | 1.4 |
| 10-08 | timeout, host unknown | DigitalOcean | 1.5 |

The 4 unusable replies (cut-off or unreadable): AtlasCloud 3 of 8 calls, Relace 1 of 23. Of the four, 3 were followed by an ok attempt 2 on another host and 1 had no attempt 2 line.

Slow but finished (8 s or more): DigitalOcean 9.43 s, Venice 8.08 s, StreamLake 8.68 s. These hosts all have slow tails, but each is one call.

Jev (from the newest 500 lines of an unfiltered pull, 2026-10-06 to 10-08): 397 calls, all ok, median 0.22 s, max 1.59 s, provider always `unknown` (Jev's reply carries no host). So Jev is not a host-routing question.

## 3. What the data does not cover

- Seven days: only about 3.5 days are retained, and only 31 guard lines on 10-06 and 10-07 combined. The 2026-09-29 slow spell the design cites (11 of 150 over 10 s) is before #159 and is not in the log.
- Clustering: a cut-off call names no host, so the data cannot show whether the 5 stalls were one host. Attempt 2 landing on a different host each time is weak evidence that stalls are per host, since attempt 2 would also be different by chance.
- Host ranking: most hosts have under 10 calls, so p95 is the maximum for them. Only StreamLake, Relace, DigitalOcean, OpenInference and GMICloud have 14 or more.
- Router behaviour live: the order field was tested offline only. Whether a named host is always available for the guard model, and whether `allow_fallbacks: false` fails fast when it is down, is unmeasured.
- The model id in force on the deployment, price per host, and whether hosts differ in answer quality (AtlasCloud's unusable replies hint they may).
- Time of day: calls come from a few test sessions, not real user traffic.
- Next data to gather: keep the log for a week through a busy period, or run a small batch with `order` set to one named host per call and `allow_fallbacks: false`, so a stall names its host. That batch spends model credit and was out of scope here.
