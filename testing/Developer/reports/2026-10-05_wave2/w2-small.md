# w2-small: cards 96, 97, 98

Three commits on `fix/cards96-97-98-small-fixes`.

| Card | Change in plain words | Test, red on old code |
|------|------------------------|------------------------|
| 96 | The graph connection now opens with `client_encoding="UTF8"`, so a Latin-1 default no longer turns "Torré" into "TorrÃ©" | `test_default_connection_reads_text_as_utf8` |
| 97 | The answer listing shows one row per record: two claims about the same record (title and symbol) no longer make two identical rows, in the table and in the plain list | `test_one_record_cited_by_two_claims_is_one_row` (red output showed the two identical OMIM rows) |
| 98 | `parse_classification(None)` raises the same `ClassificationUnavailableError` as a malformed reply, so the existing retry and "try again" path handles it | `test_a_reply_with_no_content_is_an_unusable_reply_not_a_crash` |

Red proof: the three source changes were reverted with `git apply -R` (no stash), the three tests failed, then the changes were restored.

Gates: gate 2 green, gate 3 green. Gate 4: 6531 passed, 6 failed. All 6 failures are "connection refused" to a local Postgres on port 5432 (no database in this shell), unrelated to these changes.

Not covered:
- Card 96: the evidence file named in the brief was not in the repository; the raw run JSON in `testing/Developer/reports/2026-10-05_cards91_93/raw/q24_r1.json` shows the garbled text arriving from the graph query. No repository code decodes bytes as Latin-1, and the HTTP path decodes JSON as UTF-8, so the only place a client encoding is chosen is the psycopg2 connection. The fix is the single place the repository controls; the test checks the connect argument, not a live read. If the stored graph text is itself garbled, this will not fix it (that is System 1 data). Needs a live check of the Muir-Torré record (note the service on the VPS also uses this factory, so it needs the deploy).
- Card 97: the cause is inferred from the run output (two sentences citing one citation id); the live record path was not run.
- Card 98: no change to timeouts, retries or fail-open/closed rules.
