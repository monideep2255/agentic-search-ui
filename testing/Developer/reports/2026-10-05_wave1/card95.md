# Card 95: raw citation markers in the lead line

## The defect

- A lead line citing more than 20 records showed markers 21 and up as raw bracketed text.
- Cause: a token event carries at most 20 `marker_ids` (`TokenPayload`, and the `[:20]` in `marker_ids()` in `core/graph.py`). The lead sentence from `answer_summary_sentence` wrote one `[N]` per counted record, so any marker past 20 had no chip to replace it.

## The change

- `src/system_03_search_agent/synthesis/answer_layout.py`: new `MAX_SUMMARY_MARKERS = 20`. The lead line writes at most that many markers, less the markers of linked diseases it names. The count in the sentence still states every record. The records past the cap stay listed and cited in the record tables below.
- No frontend change. The saved-answer screen renders the same token stream, so it gets the same fix.

## Tests

- `test_the_lead_sentence_never_writes_more_markers_than_a_token_can_carry`, both depths, 35 findings. Failed on the old `answer_layout.py` (35 markers), passes now.

## Gates

- Gate 2 (import order) and gate 3 (ruff, whole repository): green.
- Gate 4: 6530 passed, 6 failed. All six fail with `psycopg2.OperationalError`, connection refused to a local PostgreSQL on port 5432 (`test_no_cost_channel` x3, `test_think_retry` x3). That is the shell lacking a database, outside this change; the lead should confirm they pass in CI.

## Not covered

- No live run of query 27. Frontend not touched, so its tests were not run.
- The lead line now cites only the first 20 records by number; the rest are cited in the tables.
