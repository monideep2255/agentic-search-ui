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

## Fix round

Base: 490a62be34685ebb26ebb7d61217f7b9de19da4c. One round, against `judge_tag.md` and `adversary_tag.md` (both committed with this fix). Every mutation below was applied by a script that restored the file afterwards and printed `restored True`.

In the reader's words: a reopened answer now shows the same trust words and the same risk tag as the live answer for the same run, and where the saved row cannot show that a grounding check ran, it says "Not verified · no grounding check was recorded" rather than a tick.

| Finding | What changed | Test that pins it | Mutation, result |
|---|---|---|---|
| A-71T-10 | The saved screen's no-trust-line fallback comes from `savedTrustFallback` in `frontend/src/lib/riskTag.ts`: "Grounded · every claim cited" with a tick only for an `answer` outcome with a stored tier; anything else shows "Not verified · no grounding check was recorded" in the risk colour. Never a tick beside a raw outcome word. The words are exported constants beside `riskTagLabel`. | `SavedAnswerScreen.test.tsx` (capped flag, flag and ask with a tier, answer with a tier, no tier); `riskTag.parity.test.tsx` (capped run, live against saved) | fallback returns the old tick plus outcome word: `Tests  20 failed \| 29 passed (49)`. Any tiered outcome gets the tick: `Tests  2 failed \| 47 passed (49)` |
| A-71T-01, A-71T-07, J-71T-01 | `worst_risk_tier_from` reduces exactly as `useRunView.ts` does: every trust_signal takes part, the empty tier included, an unrecognised tier outranks the known ones, the first wins ties. An empty worst tier is stored as `""`, so the saved screen shows no tag and still knows a check ran. | Shared fixture `frontend/e2e/fixtures/card71_risk_tier_parity.json` (13 cases). `test_capture_stores_the_tier_the_live_reduction_picks` (Python) and `riskTag.parity.test.tsx` (live `useRunView` against `SavedAnswerScreen`, with and without a trust line) | restore the empty-tier filter: `3 failed, 33 passed` |
| A-71T-09, J-71T-02, J-71T-03 | `useRunView.ts` builds both risk-tag spans with `riskTagLabel`; its two copies of the words and the low/unknown exclusion are gone. Only those lines and one import changed in that file. The live branch with no trust line now reads "High-risk claim", not "high risk claim". | `riskTag.parity.test.tsx`, "a high tier reads High-risk claim on both trust-line branches" | restore `${tier} risk claim` in the live pill branch: `Tests  3 failed \| 46 passed (49)` |
| A-71T-03, A-71T-11, J-71T-04, J-71T-07 | The CHECK is gone from the migration and from the ORM. The bound is `MAX_RISK_TIER_CHARS = 16` in `feedback/contracts.py`; capture stores None for a worst tier that is not a string of at most 16 characters, so the row is kept. 0011 is now a catalog-only nullable ADD COLUMN. | `test_an_over_long_tier_saves_the_answer_with_a_null_tier` (17 characters: answer saved, tier None), `test_the_interaction_row_refuses_a_tier_over_the_bound`, the wire bound in `test_the_response_model_bounds_every_field`, no CHECK in the migration and ORM tests | drop the length check: `1 failed, 35 passed` (ValidationError). InteractionRow `max_length=17`: `1 failed, 35 passed`. Wire `max_length=1000`: `1 failed, 18 passed`. CHECK put back in the migration: `3 failed, 4 passed` |
| A-71T-05, J-71T-10 | The migration's rollback plan names the order: run `alembic downgrade 0010_interactions_saved_answer` from this build's code, then redeploy the previous build at once. It also says that between the two steps this build breaks reopening and saving. The expand-contract paragraph is corrected. One paragraph added under "Rolling back" in `docs/build/Release_flow.md`. | `test_the_rollback_plan_names_the_order_downgrade_first_then_the_previous_build` | step 1 reworded to the old "`downgrade()` drops the column": `1 failed, 6 passed` |
| J-71T-05 | New arm: upgrade over three rows saved at 0010 (all NULL after), then a downgrade over rows that hold a tier (all four rows kept). | `test_the_migration_keeps_every_row_of_a_populated_table_both_ways` | `server_default="low"` on the column: `3 failed, 4 passed` |
| J-71T-06 | The forget test seeds `risk_tier="high"` and asserts it reads NULL after forgetting, while the other account keeps its tier. | `test_forgetting_clears_one_accounts_answers_and_nobody_elses` | remove `risk_tier=None,` from forget: `1 failed, 11 passed` |
| J-71T-08 | The tag test checks colour and weight. | `SavedAnswerScreen.test.tsx`, the High-risk claim and other-tier tests | tag `fontWeight: 700, color: inkMuted`: `Tests  4 failed \| 45 passed (49)` |
| J-71T-09 | moderate, critical and an unknown tier ("severe") are each covered on the saved screen, and `""` joins the no-tag cases. | `SavedAnswerScreen.test.tsx`, "shows the live words for a stored %s tier" | non-high tiers return null: `Tests  3 failed \| 46 passed (49)` |

### Left open

- A-71T-08: grounding is not stored. Showing "Not fully grounded" on a reopened answer needs a second column, which is a migration the owner has not approved. Until then, an `answer` outcome with a stored tier and no trust line shows the grounded words, and a reopened answer with a trust line cannot show "Not fully grounded".
- A-71T-02: a trust_signal after `done` is stored, but the live screen never showed it. No emitter does this today.
- A-71T-12: wrapping at phone width on the saved trust line. Not rendered this round.
- J-71T-11: the MCP saved-answer output carries no risk tier. This is outside the fence and needs its own card.
- Known edge, not a finding: a run with a trust line but no trust_signal reads "Not verified" live and shows its trust line reopened. A trust line needs grounded claims, and grounded claims emit trust signals, so the parity test leaves out that pairing.
- The live "Not verified" and "Grounded" words still sit as literals in `useRunView.ts`, because the fence allowed only the risk-tag lines there. `riskTag.parity.test.tsx` binds them to the shared constants: a drift on either side turns it red. Moving those lines onto the constants is a one-line follow-up once tonight's other branches merge.

### Runs

All runs used a throwaway localhost database, `card71fix_scratch`, migrated to head and dropped afterwards.

- `test_capture_saved_answer.py`: `36 passed`
- `test_history_saved_answer.py`: `12 passed`
- `test_saved_answer_endpoint.py`: `19 passed, 2 warnings`
- `test_migration_0011.py`: `7 passed`
- `tests/system_03_search_agent/feedback`: `237 passed, 2 warnings`
- Migration tests 0010, 0011 and the chain: `26 passed`
- `riskTag.parity.test.tsx`: `Tests  28 passed (28)`
- `SavedAnswerScreen.test.tsx`: `Tests  21 passed (21)`
- Related vitest files (useRunView hooks, answerBold, set9, card102, card22, App.savedAnswer, api.fetchHistoryAnswer): `Tests  123 passed (123)`
- `ruff check .`: `All checks passed!`. isort `--check-only` on the changed Python files: exit 0. `npx tsc --noEmit -p .`: exit 0.
