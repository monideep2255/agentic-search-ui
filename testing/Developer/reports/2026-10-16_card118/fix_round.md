# Fix round, card 118 (PR #253)

Owner's rule: clear server errors (502, 503) retry quietly as today; only a truly unknown outcome asks the person to run s3 login once.

| Finding | Result | Test (fails before, passes after) |
|---|---|---|
| A-118-01, J-118-02 | FIXED. A 2xx other than 200 retries quietly only with an empty or non-JSON body; a JSON body keeps the token counted as sent and asks for s3 login. | `test_a_2xx_with_a_json_body_after_a_saved_renewal_asks_for_s3_login` (201, 202, 206, 299; 4 failed before). `test_a_2xx_other_than_200_retries_quietly` now runs 201, 202, 204 with an empty body and with an HTML body (still passes: V-75B-01 holds). |
| A-118-02 | FIXED. Quiet class is 3xx to 5xx except 401 and 504; 600 and above asks for s3 login again. | `test_a_status_of_600_or_more_asks_for_s3_login` (600, 650, 999; 3 failed before). |
| J-118-03 | FIXED. The 504 reply code is asserted as -32001. | In `test_a_504_on_renewal_asks_for_s3_login_once`. It passed before, since the code was already right; it now fails if the code changes. |
| J-118-01, A-118-04 | FIXED. A latched bridge that cannot read the sign-in file because another s3 command holds it says to wait for that command to finish and try again, in the reply and the log; the reply keeps s3 login only for someone who has not run it yet. No path. | `test_a_lock_timeout_on_a_latched_bridge_is_named_in_the_log` (failed before). |
| A-118-03 | FIXED. The 504 log line is "... returned 504, so the outcome is unknown. In a terminal, run: s3 login. ..." | In `test_a_504_says_the_outcome_is_unknown_not_expired` (failed before). |

Not touched: J-118-04 (pre-existing, unlatched lock timeout).

Scenario probe (card 75 `probe.py`, base and EXTRA rows, VERBOSE) on this branch against develop 467d1081: only the intended rows differ.

- The 504 rows: new reply and log wording, code unchanged.
- XH (204 empty): quiet retry, then OK.
- R5 (re-login with the default port): resumes.
- XI (202 with a JSON body): now identical to develop (asks for s3 login), by design.
