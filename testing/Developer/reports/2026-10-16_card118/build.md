# Card 118 build report

Files: `src/system_03_search_agent/adapters/cli/mcp_bridge.py`, `tests/system_03_search_agent/adapters/cli/test_mcp_bridge.py`.

| Finding | Fix | New test | Mutation (red, then restored) |
|---|---|---|---|
| V-75B-01 | Any status except 200, 401, 504 retries quietly, 2xx included | `test_a_2xx_other_than_200_retries_quietly` (201, 202, 204) | old `300 <= status < 600`: 3 failed |
| V-75B-02 | 504 gets its own log line and reply: outcome unknown, server may have renewed, `s3 login` | `test_a_504_says_the_outcome_is_unknown_not_expired` | branch disabled: 1 failed |
| V-75B-03 | Default port (443 for https, 80 for http) dropped before comparing; other ports still differ | `test_a_default_port_is_the_same_server`, `test_only_a_default_port_is_dropped_from_an_address` | strip disabled: 2 failed |
| V-75B-04 | Lock timeout on a latched bridge logs one line, no path; reply unchanged | `test_a_lock_timeout_on_a_latched_bridge_is_named_in_the_log` | clause disabled: 1 failed |

- V-75B-05 and V-75B-06 left as they are (on develop before card 75, or unsure).
- Bridge test file: 122 passed, all earlier tests unchanged.
- Gates: ruff check clean, isort clean, `pytest tests/system_03_search_agent/adapters -m "not integration" -q`: 939 passed.
