# Judge report, card 71 last part (stored High-risk claim tag)

Base: 490a62be34685ebb26ebb7d61217f7b9de19da4c on fix/card71-high-risk-tag, two commits over origin/develop (66123ba5, 490a62be).

## Findings

### J-71T-01: an empty-string tier makes the saved tag differ from the live one

- Severity: minor
- Evidence: `TrustSignalPayload.risk_tier` is `str = Field(..., max_length=16)` with no `min_length` (src/system_03_search_agent/contracts/events.py:499), so `""` validates. Live (frontend/src/hooks/useRunView.ts:902-909) ranks `""` as unknown (index -1, MAX_SAFE_INTEGER), so it wins the reduce and the falsy tier shows no tag. Capture drops it instead (src/system_03_search_agent/feedback/capture.py:265-270, `if isinstance(tier, str) and tier`). My probe ran capture's `worst_risk_tier_from` on 584 sequences of 1 to 3 trust_signal events over `low, moderate, high, critical, unknown, High, severe, ""`, and compared the stored tier with live's reduce, copied verbatim. Pasted output: `cases=584 storedTierDiffersFromLiveWorst=122 labelMismatch(summary branch)=96`, for example `{"seq":["high",""],"live":null,"saved":"High-risk claim","stored":"high"}`. With `""` removed: `cases=399 storedTierDiffersFromLiveWorst=0 labelMismatch(summary branch)=0`. No producer in src emits `""` today (graph.py emits `low`, `high`, `unknown`), so the user cannot hit this now. It shows that capture is not the same reduction, as its docstring claims.
- Smallest fix: drop the `and tier` filter so `""` ranks like live and wins. Or add `min_length=1` to the event field.

### J-71T-02: for a run with no trust line, the saved tag's words differ from the live tag's words

- Severity: minor
- Evidence: live has two label forms. With a `done.trust_line` it shows `"High-risk claim"` (useRunView.ts:943). Without one it shows `` `${payload.risk_tier} risk claim` ``, which reads "high risk claim" (useRunView.ts:967). `riskTagLabel` always returns "High-risk claim" for `high` (frontend/src/lib/riskTag.ts:12). Same probe, non-trust_line branch: `labelMismatch(no-trust_line branch)=25` of 399 non-empty sequences, every one a sequence whose worst tier is `high`. The saved row stores `answer_trust_line = done_payload.trust_line`, which is None when `answer_trust_line` returns None (synthesis/trust.py, `if trust_outcome == "refuse" or not claims: return None`). An answered run with no parsed claims therefore showed "high risk claim" live and "High-risk claim" reopened. The builder disclosed this in build_tag.md, but it is still a word difference against the ticket's "the same tag".
- Smallest fix: make riskTagLabel's output depend on whether the row has a `trust_line`, to match the live branch. Or fix the live non-summary branch's casing in a follow-up so both read "High-risk claim".

### J-71T-03: the label strings live in three places with no test that binds them

- Severity: minor
- Evidence: the label is built in frontend/src/lib/riskTag.ts:11-12, frontend/src/hooks/useRunView.ts:940-944 and useRunView.ts:966-967. Each holds its own `"low"`/`"unknown"` exclusion and its own wording. No test renders the live view and the saved view from the same tier and compares the text: `grep -rn "riskTagLabel" frontend/src` finds only riskTag.ts and SavedAnswerScreen.tsx. If someone edits the live wording, the saved screen drifts silently. J-71T-02 shows the two copies already disagree in one branch.
- Smallest fix: have useRunView import `riskTagLabel`, in a follow-up because the file was out of fence. Or add one vitest that feeds the same tier to the live hook and to SavedAnswerScreen and asserts equal tag text for low, moderate, high, critical, unknown and an unrecognised tier.

### Migration probe (passed, no finding)

My own script ran against a throwaway database on localhost (`judge71_scratch_<uuid>`), created and dropped by the script. It did: upgrade to 0010, insert 500 old-shape rows, upgrade to head, set risk_tier='high' on 10 rows, downgrade to 0010, then upgrade again. Pasted output:

```
heads: ['0011_interactions_risk_tier']
after upgrade rows: (500, 0, 500)
constraint def: ('CHECK (((risk_tier IS NULL) OR (char_length(risk_tier) <= 16)))', True)
after downgrade: risk_tier present: False rows: 500
constraint left: 0
re-upgrade rows: (500, 0)
dropped: judge71_scratch_810f7b6232e7445ba89adec983adb5cc 0
```

The chain has a single head, and the downgrade drops the constraint before the column. The constraint cannot fail on existing rows, because every existing row is NULL after ADD COLUMN. Offline SQL (`alembic upgrade 0010...:0011... --sql`): `ALTER TABLE interactions ADD COLUMN risk_tier TEXT;` then `ALTER TABLE interactions ADD CONSTRAINT ck_interactions_risk_tier_length CHECK (...)`, both in one transaction.

### J-71T-04: the CHECK is added validated, a full table scan under an exclusive lock, with no lock timeout

- Severity: minor
- Evidence: from the offline SQL above, both ALTERs run in one transaction, so the ACCESS EXCLUSIVE lock from ADD COLUMN is held while ADD CONSTRAINT scans every row to validate (`convalidated = True` in the probe). `grep -n "lock_timeout\|statement_timeout" alembic/env.py` returns nothing. On develop's table this is likely milliseconds, and 0010 used the same pattern (alembic/versions/0010_interactions_saved_answer.py:142-152). But a long-running reader on `interactions` would queue every later query behind this ALTER with no upper bound.
- Smallest fix: `op.create_check_constraint(..., postgresql_not_valid=True)`. The constraint still applies to new writes and needs no scan, since every existing row is NULL. Optionally add `SET lock_timeout` in the migration.

### J-71T-05: no migration test runs the upgrade over a populated table

- Severity: minor
- Evidence: in tests/system_03_search_agent/data/test_migration_0011.py, `migrated_head` upgrades to head and then runs `TRUNCATE interactions CASCADE`. Every arm inserts rows only AFTER the column exists. No arm upgrades from 0010 with rows present, and no arm downgrades with a non-NULL risk_tier present. The brief's requirement, safe on a populated table, holds by my probe above, not by any test in the change.
- Smallest fix: one arm that downgrades to 0010, inserts a row, upgrades to 0011, and asserts the row survives with NULL risk_tier. Then it sets one tier and downgrades.

### Mutations so far (each restored, `git diff --stat HEAD` empty after each)

| Control | Mutation | Result |
|---|---|---|
| capture stores the tier | capture.py `risk_tier = worst_risk_tier_from(events)` to `None` | red, `1 failed, 19 passed` |
| writer writes it | writer.py `"risk_tier": row.risk_tier` to `None` | red, `FAILED test_history_saved_answer.py::test_the_stored_risk_tier_is_returned_and_an_old_row_reads_none` |
| worst, not last | capture.py `return worst` to `return tiers[-1]` | red, `1 failed, 19 passed` |
| unknown outranks known | capture.py `else len(_RISK_ORDER)` to `else -1` | red, `1 failed, 19 passed` |
| history returns it | history.py `risk_tier=row.risk_tier` to `None` | red, `1 failed, 11 passed` |
| endpoint returns it | app.py `risk_tier=saved.risk_tier` to `None` | red, `1 failed, 18 passed` |
| endpoint does not invent one | app.py to `saved.risk_tier or 'high'` | red, `1 failed, 18 passed` |
| forget clears it | history.py removed `risk_tier=None,` from `forget_saved_answers_for_account` | GREEN, `221 passed` (J-71T-06) |

### J-71T-06: forgetting an account's saved answers can leave the tier behind and no test notices

- Severity: minor
- Evidence: I deleted `risk_tier=None,` from the `.values(...)` in `forget_saved_answers_for_account` (src/system_03_search_agent/feedback/history.py:469-473). Then `pytest tests/system_03_search_agent/feedback` gave `221 passed`. The forget tests (test_history_saved_answer.py:360-398) assert only on `_stored_answer` and `get_saved_answer`, never on `risk_tier`. The function is called by nothing today (its own docstring, history.py:434), so no user is affected now. But the account-delete path it exists for would keep a per-answer field the owner's 2026-09-22 decision says goes with the account.
- Smallest fix: in the forget test, store a row with `risk_tier="high"` and assert the column reads NULL after `forget_saved_answers_for_account`.

### Length bound mutations

| Hop | Mutation | Result |
|---|---|---|
| migration constant | `MAX_RISK_TIER_CHARS = 16` to `17` | red, `2 failed, 3 passed` |
| migration SQL | the CHECK made `<= 100`, with the constant left at 16 | red, `1 failed, 4 passed` |
| ORM CheckConstraint | models.py `char_length(risk_tier) <= 16` to `<= 17` | GREEN, `226 passed` (migration test plus feedback) |
| InteractionRow | contracts.py `max_length=16` to `17` | GREEN, `221 passed` (feedback) |
| wire model | app.py `SavedAnswerResponse.risk_tier max_length=16` to `1000` | GREEN, `19 passed` (endpoint test) |

### J-71T-07: three of the four length bounds can be loosened with every test green

- Severity: minor
- Evidence: see the table above. The ORM's CheckConstraint (src/system_03_search_agent/data/models.py:295-298), `InteractionRow.risk_tier` (feedback/contracts.py:254) and `SavedAnswerResponse.risk_tier` (adapters/web_sse/app.py:905) each passed after the mutation. `test_the_orm_declares_the_column_the_migration_adds` checks only nullable and type (test_migration_0011.py, last test). The upstream event bound (`TrustSignalPayload.risk_tier max_length=16`) and the database CHECK still hold, so no over-long value reaches a user today. The ORM copy can drift from the migration unseen, and so can the two Pydantic copies.
- Smallest fix: one parametrized unit test that a 17-character tier is refused by `InteractionRow` and by `SavedAnswerResponse`. In the ORM test, assert that `ck_interactions_risk_tier_length` is in `Interaction.__table__.constraints` with `<= 16` in its text.

### Frontend mutations (each restored, `git diff --stat HEAD` empty after each)

| Control | Mutation | Result |
|---|---|---|
| null shows nothing | riskTag.ts `if (!tier \|\| ...` to `if (tier === "low" ...` | red, `2 failed \| 11 passed (13)` |
| absent tier reads null | api.ts default `: null` to `: "high"` | red, `1 failed \| 9 passed (10)` |
| tier carried through | api.ts `risk_tier: null` always | red, `1 failed \| 9 passed (10)` |
| screen shows the tag | SavedAnswerScreen.tsx `{riskLabel ? (` to `{false ? (` | red, `1 failed \| 12 passed (13)` |
| the look | SavedAnswerScreen.tsx tag `fontWeight: 400, color: designTokens.risk` to `fontWeight: 700, color: designTokens.inkMuted` | GREEN, `13 passed (13)` (J-71T-08) |
| other known tiers | riskTag.ts non-high tiers return `null` | GREEN, `13 passed (13)` (J-71T-09) |

### J-71T-08: the test titled "in the risk colour" does not check the colour or the weight

- Severity: minor
- Evidence: in frontend/src/components/screens/SavedAnswerScreen.test.tsx, the test "shows the High-risk claim tag for a high tier, in the risk colour, beside the trust line" asserts text and containment only. I changed the span to `fontWeight: 700, color: designTokens.inkMuted` and the file passed, `Tests  13 passed (13)`. The tag's look is the one thing that makes it stand out on the live answer (AnswerScreen.tsx:2218-2226: "a high-risk span keeps the risk colour, which is what makes it stand out"). A grey, bold tag on the reopened answer would ship green. By reading, the code today uses the same token and weight as live (SavedAnswerScreen.tsx:360 against AnswerScreen.tsx:2221-2226).
- Smallest fix: assert `toHaveStyle({ color: designTokens.risk, fontWeight: 400 })` on the tag, as other screen tests in this repository do for tone, or drop "in the risk colour" from the title.

### J-71T-09: no test covers moderate, critical or an unrecognised tier on the saved screen

- Severity: minor
- Evidence: I made `riskTagLabel` return `null` for every tier except `high` and SavedAnswerScreen.test.tsx passed, `13 passed (13)`. There is no riskTag test file (`ls frontend/src/lib/riskTag*` shows only riskTag.ts). The live code ranks and labels `moderate` and `critical`, and labels any unrecognised tier as `<tier> risk claim` (useRunView.ts:902, 943). The ticket's "same tag" covers these. My probe (J-71T-01) shows today's code produces identical labels for them in the summary branch, so behaviour is correct now. Only the test is missing.
- Smallest fix: extend the screen test's `it.each` with `["critical", "critical risk claim"]`, `["moderate", "moderate risk claim"]` and `["severe", "severe risk claim"]`.

### Security and standards (read and probed, no finding)

- SQL: the diff adds no raw SQL. `git diff origin/develop...HEAD -- src | grep "^+.*text(\|^+.*execute"` returns nothing. The writes go through SQLAlchemy `insert(...).values(...)` (writer.py:339, 392) and the reads through `select(...)` (history.py:400-406), all bound parameters.
- Validation at each hop: event `max_length=16` (contracts/events.py:499), `InteractionRow` `max_length=16` (feedback/contracts.py:254), DB CHECK `<= 16` (enforced, red under mutation), wire `SavedAnswerResponse` `max_length=16` (app.py:905), frontend `typeof body.risk_tier === "string" ? ... : null` (api.ts:643). The bounds untested at three hops are J-71T-07.
- Rendering: the tier reaches the DOM only as a React text child (`{riskLabel}`, SavedAnswerScreen.tsx:362). Neither SavedAnswerScreen.tsx nor riskTag.ts uses `dangerouslySetInnerHTML` (the one grep hit is a comment at SavedAnswerScreen.tsx:40).

### J-71T-10: the migration's rollback plan and expand-contract note are wrong about new code on the old schema

- Severity: major
- Evidence: alembic/versions/0011_interactions_risk_tier.py's docstring makes two claims. Rollback plan: "`downgrade()` drops the constraint and then the column ... a reopened answer then shows no tag, which is exactly what it does today". Expand-contract: "new application code against the old schema fails only in capture's best-effort write". Both are false. `get_saved_answer` selects `Interaction.risk_tier` (feedback/history.py:403). My probe migrated a throwaway localhost database to 0010 and called the new `get_saved_answer`. Pasted: `get_saved_answer on 0010 schema raised: ProgrammingError (psycopg2.errors.UndefinedColumn) column interactions.risk_tier does not exist`. The endpoint catches only `ValueError` (adapters/web_sse/app.py, `get_v1_history_answer`, `except ValueError:`), so this becomes a server error. An operator who follows the written rollback plan, downgrading the database while this code stays deployed, breaks the opening of every saved answer, not only the tag. Normal deploys are safe, because railway.json runs `alembic upgrade head && ... uvicorn`, so new code never starts on the old schema. The defect is the written plan, which the owner's approval of this migration relied on.
- Smallest fix: rewrite both paragraphs to say that the code must be rolled back before `downgrade()`, because reading a saved answer selects the column and fails without it. Alternatively, make the read tolerate a missing column. The docstring edit is the smaller fix.

### J-71T-11: a saved answer reopened over MCP still carries no risk tier

- Severity: minor (unsure whether it is in scope; the ticket names the screen)
- Evidence: the MCP saved-answer output model in src/system_03_search_agent/adapters/mcp/server.py ends at `trust_line: str | None = Field(default=None, max_length=200)` and has no `risk_tier` (`extra="forbid"`). The live MCP answer carries `risk_tier` (server.py:980-988). So an assistant client that reopens a saved answer through MCP loses the high-risk signal the live answer carried, while the web now keeps it. The same `get_saved_answer` already returns `risk_tier`, so the data is there.
- Smallest fix: add `risk_tier: str | None = Field(default=None, max_length=16)` to the MCP saved-answer output and pass `saved.risk_tier` through. If parity is out of scope for card 71, record that as a follow-up card.

## Test runs (one file at a time, against a throwaway localhost database `judge71_tests` migrated to head, dropped afterwards)

- test_migration_0011.py: `5 passed in 1.05s`
- feedback/test_capture_saved_answer.py: `20 passed in 0.18s`
- feedback/test_history_saved_answer.py: `12 passed in 0.41s`
- feedback/test_outage_note_dated.py: `48 passed, 2 warnings in 3.69s`
- adapters/web_sse/test_saved_answer_endpoint.py: `19 passed, 2 warnings in 3.29s`
- tests/system_03_search_agent/feedback: `221 passed, 2 warnings in 11.06s`
- SavedAnswerScreen.test.tsx: `Tests  13 passed (13)`
- api.fetchHistoryAnswer.test.ts: `Tests  10 passed (10)`

After every mutation, `git diff --stat HEAD` printed empty. At the end, `git status --short` shows only untracked files (frontend/node_modules, adversary_tag.md, judge_tag.md) at HEAD 490a62be.

## Verified by my own probes versus read only

- Probed: stored tier against live worst tier over 584 event sequences (J-71T-01, J-71T-02). The migration on a populated table, downgrade and re-upgrade (passed). New code on the 0010 schema (J-71T-10). Every control mutation in the tables above.
- Read only: the visual equivalence of the saved span and the live span (same token `designTokens.risk`, weight 400, middle dot; the saved line is block, the live line is flex with gap 0.75, the saved dot has mx 0.75). Railway's start order. That no producer emits an empty tier.

## Verdict

FIX FIRST: J-71T-10 (the rollback plan in the migration is wrong; a docstring fix). Everything else is minor and can follow: J-71T-01 to J-71T-09 and J-71T-11. The core behaviour verified correct by probe: same tier as live for every non-empty tier sequence, null rows tagless, the bound enforced in the database, and the migration safe on populated rows.
