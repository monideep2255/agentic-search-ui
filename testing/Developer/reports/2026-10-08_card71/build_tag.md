# Card 71 build: the high-risk tag on a reopened answer

Base: c916cfa30f59802dfd85c81ef7ba39bdcfc2b263 (origin/develop).

## Findings and deviations

- The live tag is built from the WORST risk tier over every `trust_signal` event (claim and answer scope), not only the answer-level one. Capture stores that same reduction (`worst_risk_tier_from`), so the saved tag matches the live one. An unrecognised tier outranks all known ones, as live.
- `feedback/writer.py` names every `interactions` column explicitly (two places), so it had to gain `risk_tier`. It is outside the stated fence; the change is two lines. Without it the column would never be written.
- `adapters/web_sse/app.py` holds `SavedAnswerResponse` (the history answer wire model), and `feedback/contracts.py` holds `InteractionRow`; both gained one optional field. Also outside the named fence, required by the ticket.
- The CHECK on the column is a 16-character length bound, not a list of tiers: the wire field is a bare string and a list would make the database refuse a saved answer when a new tier name appears (capture is best-effort, so the answer would be lost silently).
- A local PostgreSQL is running and the shared development database is at revision 0010. Tests that write `interactions` rows would fail there until it is migrated, so they were run against a throwaway database migrated to head. The shared database was not touched.
- The tag's words live in the new `frontend/src/lib/riskTag.ts` (`riskTagLabel`), used by the saved screen. `useRunView.ts` was off limits, so it still holds its own copy of the same label strings. The live tag span sits inside `AnswerBody`, too large to reuse; the saved screen renders a span with the same colour token, weight 400 and middle dot separator inside its existing trust line.
- The live non-summary branch labels a high tier "high risk claim" (lowercase); the saved screen always uses "High-risk claim", the summary branch's wording.
- `test_outage_note_dated.py` builds a fake row with `SimpleNamespace`; it needed `risk_tier=None` because `get_saved_answer` now selects the column.

## Learnings

- Commits were held by the `mod-public-repo-guard` hook ("the guard failed while checking this call") on every `git commit` attempt, while `git add` and `git status` passed. Not bypassed. The work is staged, uncommitted.
- The Bash hook blocks `rm`, so restore-after-mutation used `cp` from scratchpad backups.

## Test evidence

- Mutations that turn tests red: history returns None instead of the column (1 failed), capture stores None (1 failed), capture ranks the lowest tier as worst (2 failed), riskTagLabel changes the words (1 failed), the screen hard-codes "high" (4 failed).
