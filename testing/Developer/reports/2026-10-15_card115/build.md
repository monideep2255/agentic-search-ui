# Card 115 build, 2026-10-15

Base: 7626fe850f10b1fd6da7d7256285f92647e3112a, branch fix/card115-readonly-reply-first.

## Change

- File: `src/system_03_search_agent/core/graph.py`, `_guardrail_after_prefilter` only, 11 lines added.
- On the memory-bound follow-up path card 35 added (topic check running and the allowlist cleared), before the topic check is read, `forbidden.screen` runs. If it refuses as write_seeking, the topic check is cancelled and the read-only refusal returns at once.
- Nothing else moves: the later forbidden screen, every bound and every other verdict are unchanged.

## Test

- `test_a_write_seeking_follow_up_keeps_the_read_only_reply_without_the_topic_check`: 2 write-seeking texts x topic check off_topic or hung after a BRCA1 turn. Expects refuse:write_seeking with the read-only reply, under 1.0 s, and the hung check cancelled.
- Mutation (early return disabled): 4 failed, 125 deselected (off_topic reply instead of the read-only one). Restored: 4 passed.

## Grid (stubs, BRCA1 in memory, classifier ok, 3 write-seeking and 3 ordinary texts)

Jev off or on (not_injection pick) x topic pick off_topic fast, off_topic at 0.3 s, hung, on_topic, no usable pick = 60 cases. Changed 12; the only change is refuse:off_topic to refuse:write_seeking, on the write-seeking texts under an off_topic pick (6 with Jev off, 6 with Jev on). All 30 ordinary-follow-up cases and every hung, on_topic and no_pick case are identical. Timings in the run were noisy from load and are not evidence; the test above checks the wait.

| Topic pick | Text kind | Develop | This branch |
|---|---|---|---|
| off_topic fast or 0.3 s | write-seeking | refuse:off_topic | refuse:write_seeking |
| off_topic fast or 0.3 s | ordinary | refuse:off_topic | refuse:off_topic |
| hung | write-seeking | refuse:write_seeking | refuse:write_seeking |
| hung | ordinary | admit | admit |
| on_topic | write-seeking | refuse:write_seeking | refuse:write_seeking |
| on_topic | ordinary | admit | admit |
| no usable pick | write-seeking | refuse:write_seeking | refuse:write_seeking |
| no usable pick | ordinary | admit | admit |

Same table for Jev off and Jev on.

## Gates

- ruff check: All checks passed.
- isort --check-only (gate paths): exit 0.
- pytest guardrail and core, not integration: 1951 passed, 56 skipped, 1 deselected.
