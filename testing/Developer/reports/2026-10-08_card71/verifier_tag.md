# Card 71 high-risk tag: fresh verifier report

Base: origin/fix/card71-high-risk-tag at 522676511b25d28351f2cb79a91ae8155d40dfe6 (52267651), checked out detached in the card71-adv worktree. Diff against origin/develop: 3 commits, 24 files.

## Findings and results (written as established)

### Test runs (one file at a time, throwaway localhost database ver71_scratch migrated to head)

- data/test_migration_0011.py: `7 passed in 1.19s` (no skips)
- feedback/test_capture_saved_answer.py: `36 passed in 0.21s`
- feedback/test_history_saved_answer.py: `12 passed in 0.58s`
- feedback/test_outage_note_dated.py: `48 passed, 2 warnings in 4.10s`
- adapters/web_sse/test_saved_answer_endpoint.py: `19 passed, 2 warnings in 4.73s`
- tests/system_03_search_agent/feedback: `237 passed, 2 warnings in 18.82s` (no skips with -rs)
- data/test_migration.py: `11 passed in 2.99s`; data/test_migration_0010.py: `8 passed in 1.37s`

- vitest, one file at a time: riskTag.parity.test.tsx `Tests  28 passed (28)`; SavedAnswerScreen.test.tsx `Tests  21 passed (21)`; api.fetchHistoryAnswer.test.ts `Tests  10 passed (10)`; live-view files answerBold 5, set9AnswerStructure 8, useRunView.clarification 6, clarificationOptions 4, handoff 3, refusal 8, sourceName 5, writeState 7, all passed.
- `npx tsc --noEmit -p .` in frontend: exit 0.
- e2e specs (read, not run): the only live-tag assertions are `toContainText("High-risk claim")` (bold-and-stagger.spec.ts:192, summary branch, unchanged) and `toContainText(/high/i)` (trust-surface.spec.ts:235), which matches both the old and new wording. No e2e asserts the old lowercase "high risk claim".

## 1. Fix-round findings, re-derived

Mutation method: a scratchpad script applies one exact string replacement (refuses unless it matches exactly once), runs the named tests, then `git checkout -- <file>`; each run printed `restored: 0 changed lines in diff stat`.

### A-71T-10 (capped run reopened with a tick and "flag"): fixed

- Code: frontend/src/lib/riskTag.ts `savedTrustFallback`, used at SavedAnswerScreen.tsx (the `fallback` const and the trust-line Box).
- M1, fallback returns `{ kind: "good", label: outcome }` (develop's look): parity 2 failed, screen 5 failed, e.g. `expected '✓flag' to be 'Not verified · no grounding check was…'`.
- M2, any outcome with a tier gets the tick: `Tests  2 failed | 47 passed (49)`.
- M3, an "answer" row with no tier gets the tick (an old row looking grounded): `Tests  3 failed | 46 passed (49)`.
- M4, "Not verified" loses the risk colour: `2 failed | 47 passed`, `toHaveStyle()`.
- M5, the tick shown for the risk kind: `6 failed`.
- My own reading of reachability: a saved row has trust_line NULL only when done.trust_line was None, which `answer_trust_line` returns for refuse or no grounded claims; graph.py emits claim and answer trust_signals only `if claim_trusts`, so such a row normally has no trust_signal, and live showed "Not verified · no grounding check was recorded" (useRunView.ts:891-895). The new saved words now match live there; develop showed "✓answer" or "✓flag". Capture began storing trust_line in the same commit as answer_markdown (1fd16e29, `git log -S`), so no pre-0011 saved row lost a trust line it had live.

### Own end-to-end parity probe (capture, real writer, real database, real read, wire model, real live hook, real saved screen)

- Python probe (scratchpad, outside the checkout): 870 runs, every trust_signal tier sequence of length 0 to 2 over `low, moderate, high, critical, unknown, "", severe, High`, with all grounded or the first ungrounded, outcome answer, flag or ask, with and without a done.trust_line. Each run went through `assemble_interaction`, `write_interaction` into ver71_scratch, `get_saved_answer`, and `SavedAnswerResponse`. Output: `cases 870 db-roundtrip mismatches 0 empty-tier stored 156`.
- A throwaway vitest file (moved out afterwards) fed each run's events to the real `useRunView` and the wire record to the real `SavedAnswerScreen`. Output: `cases=870 tagMismatch=0 savedMoreConfident=291 firstSpanMismatch(no trust line)=288`.
- The tag, the ticket's subject, matched live in all 870 runs, empty tier, unrecognised tiers, "High" and ties included.
- The 291 "more confident" and 288 first-span mismatches are all in combinations the backend does not produce, by my reading of graph.py and synthesis/trust.py: (a) an ungrounded signal beside a trust line (live adds "Not fully grounded", saved omits it: A-71T-08, identical on develop, which also showed only the trust line); (b) trust signals with no trust line, which needs claim_trusts non-empty and grounding.claims empty, but `claim_trusts = trust_for_claims(grounding.claims, ...)` (graph.py:13561) and `answer_trust_line` returns None only for refuse or `not claims` (trust.py:692); (c) an "answer" outcome with an ungrounded claim, but an ungrounded claim's outcome comes from `DECISION_TABLE[(tier, False, None)]` (trust.py:446) and `aggregate` takes the most restrictive, and `trust_for_claims` builds every surviving claim with `grounded=True` (trust.py:525).

- Backend invariant confirmed by read: trust.py:409 `("low", False, None): "refuse"` and :411 `("high", False, None): "refuse"`. The probe test file was moved out of the checkout; `git status --short` showed only `?? frontend/node_modules`.

### A-71T-01, A-71T-07, J-71T-01 (empty tier): fixed

- Code: capture.py `worst_risk_tier_from` (no filter, unrecognised outranks known, first wins ties, None over 16 characters).
- M6, restore the empty-tier filter: `FAILED ...[high,]` and `...[,high]`, `assert 'high' == ''`.
- M7, ties go to the last (`>=`): `1 failed, 35 passed`, `assert 'brand-new' == 'severe'`.
- M8, unrecognised ranks below known: 4 failures, e.g. `assert 'high' == 'unknown'`.
- M9, last tier instead of worst: 4 failures, e.g. `assert 'low' == 'high'`.
- M10, the LIVE side filters the empty tier (useRunView.ts `risk_tier || "low"`): parity `Tests  4 failed | 24 passed (28)`. The shared fixture binds both sides.
- End to end (probe above): `["high", ""]` stores `""`, reads back `""` on the wire, saved shows no tag, live shows no tag.

### A-71T-09, J-71T-02, J-71T-03 (two copies of the words, lowercase pill): fixed

- useRunView.ts now calls `riskTagLabel` in both branches (diff: two blocks and one import, nothing else in that file).
- M11, the live pill branch back to `${tier} risk claim`: parity `Tests  3 failed | 46 passed (49)`.
- M12, riskTagLabel's words change: `4 failed | 45 passed (49)`.
- M15, riskTagLabel stops excluding "unknown": screen `1 failed | 48 passed (49)`.
- M16, the live "Grounded · every claim cited" literal drifts: parity `13 failed`. M17, the live "Not verified · no grounding check was recorded" literal drifts: parity `2 failed`. The build note's claim that the parity test binds the live literals to the shared constants holds.

### J-71T-08 (tag look untested): fixed

- M14, tag `fontWeight: 700, color: designTokens.inkMuted`: `Tests  4 failed | 45 passed (49)`, `toHaveStyle()`.

### J-71T-09 (moderate, critical, unknown tier untested): fixed

- M13, non-high tiers return null: `3 failed | 46 passed (49)`, `Unable to find ... saved-answer-trust-risk`.

### A-71T-03, A-71T-11, J-71T-04, J-71T-07 (over-long tier loses the row; validated CHECK under lock; bounds untested): fixed

- M18, drop capture's length check: `1 failed, 35 passed`, `ValidationError: 1 validation error for InteractionRow` at capture.py:518.
- M19, off by one (`>=`): `1 failed`, `assert None == ('c' * 16)`.
- M20, InteractionRow `max_length=17`: `1 failed`, `DID NOT RAISE ValidationError`.
- M21, wire `max_length=1000`: `1 failed, 18 passed`, `assert 1000 == 16`.
- M22, CHECK put back in 0011: 2 failed, including `CheckViolation ... ck_interactions_risk_tier_length`.
- M23, the ORM declares a CheckConstraint: `1 failed, 6 passed`.
- Offline SQL and lock behaviour: see section 3.

## 3. Deploy safety (own probe, throwaway localhost database ver71_mig, develop's tree exported with `git archive origin/develop`)

- Develop's tree `alembic upgrade head` stopped at `0010_interactions_saved_answer`. Develop's capture and writer wrote 3 saved answers, plus 200 bulk rows by SQL: `203|3` (rows, saved answers). `relfilenode` 1739679.
- Offline SQL of 0010 to 0011, complete: `BEGIN; ALTER TABLE interactions ADD COLUMN risk_tier TEXT; UPDATE alembic_version ...; COMMIT;`. No CHECK, no default, no backfill.
- This branch's `alembic upgrade head` over the populated table: `0011_interactions_risk_tier`, `203|3|0` (rows, answers, non-null tiers), `relfilenode` still 1739679 (no table rewrite), column `risk_tier|text|YES|` (no default), 0 risk constraints.
- Old code against the new schema (the deploy window, while the previous container still serves): develop's code wrote `oldafter` rows and read them and `old-0` back, unchanged.
- New code against the new schema: `new-0 (... 'high')`, `new-1 (... 'low')`, `new-2 (..., None, None)`; old rows read `None` (no tag).
- Wrong rollback order (previous build first, at 0011): `FAILED: Can't locate revision identified by '0011_interactions_risk_tier'`. The documented order avoids it.
- Documented step 1, this branch's `alembic downgrade 0010_interactions_saved_answer`: `0010_interactions_saved_answer`, `209|9`, column gone (0). Every row kept.
- The window between steps, as documented: this branch's reads raise `ProgrammingError (psycopg2.errors.UndefinedColumn) column interactions.risk_tier does not exist`, and 3 of 3 writes logged "dropping the row". The docstring and Release_flow.md now say exactly this and say to keep the window short.
- Documented step 2, develop's start command `alembic upgrade head` at 0010: no-op, then develop reads `new-0`, `old-0`, `oldafter-2` and writes `afterrb`: `212|12`.
- Re-upgrade with this branch: `212|12|0`.
- railway.json `startCommand` is `alembic upgrade head && ... uvicorn ...`, so a normal deploy never runs new code on the old schema.
- Lock: ADD COLUMN of a nullable column with no default takes ACCESS EXCLUSIVE only for the catalog change; no `lock_timeout` is set, so it can queue behind a long reader. Same as develop's 0010 pattern; not worse.
- Result: deploy safe; the downgrade keeps every row; the documented rollback order is correct by probe.

### A-71T-05, J-71T-10 (rollback plan wrong): fixed

- Docstring "Rollback plan, in this order" and docs/build/Release_flow.md line 89 match my probe above. Test `test_the_rollback_plan_names_the_order_downgrade_first_then_the_previous_build` pins the order (the build note's mutation: `1 failed, 6 passed`; my own mutation M24 below).

- M24, a first step "0. First redeploy the previous build." inserted before the downgrade: `1 failed, 6 passed` (test_migration_0011.py:203). Fixed.
- F-V71T-01 (minor, test weakness, not a product defect): the rollback-order test matches the literal lowercase phrase "redeploy the previous build" by position. The same reordering written "0. Redeploy the previous build." (capital R) passed, `7 passed in 2.23s`, because `plan.index` then finds the later lowercase phrase in step 2. Release_flow.md's paragraph has no test: replacing its first sentence passed, `7 passed in 0.75s`. Neither changes what ships tonight; the text itself is correct by my probe.

### J-71T-05 (no populated-table migration test): fixed

- M25, `server_default="low"`: 3 failed, including `assert ['low', 'low', 'low'] == [None, None, None]`.
- M26, the downgrade deletes rows holding a tier: `1 failed, 6 passed`.
- M27, the upgrade deletes old rows: `1 failed, 6 passed`.

### J-71T-06 (forget leaves the tier): fixed

- M28, `risk_tier=None,` removed from `forget_saved_answers_for_account`: `1 failed, 11 passed`, `assert 'high' is None`.

### Other controls, all red under mutation

- M29, writer writes None: `2 failed, 10 passed`.
- M30, endpoint `saved.risk_tier or "high"`: `1 failed, 18 passed`, `assert 'high' is None`.
- M31, api.ts defaults an absent tier to "high": `1 failed | 9 passed (10)`.

## 2. Worse than develop?

### Live answer screen: only the intended wording change

- Probe: the same 870 runs fed to the real `useRunView`, once with this branch's file and once with `git show origin/develop:frontend/src/hooks/useRunView.ts` swapped in (restored with `git checkout`), trust spans compared line by line. Output: `differing lines: 36`, all of one kind: `risk:high risk claim  ==>  risk:High-risk claim` (18 beside "Grounded · every claim cited", 18 beside "Not fully grounded"). No other live span changed in any run, including the summary branch.
- Those 36 runs are the no-trust-line pill branch, which by my reading of graph.py:13561 and trust.py:692 today's backend does not reach (trust signals imply grounded claims imply a trust line). Where reached, the new words match the summary branch's. Not worse.

### Reopening an answer saved before the migration

- Probe rows written by develop's code at 0010, read by this branch after 0011: `old-0 ('answer', 'Based on 2 sources cited, not yet confirmed', None)`, `old-2 ('answer', None, None)`. The wire carries `risk_tier: null`; the screen shows no tag (screen tests plus M31 and M30 above).
- One visible change on old rows: a row with no trust line read "✓answer" (or "✓flag", "✓ask") on develop and now reads "Not verified · no grounding check was recorded" in the risk colour. For the runs the backend saves with no trust line (no grounded claims, or the cost-cap partial result), the live answer showed exactly that sentence (useRunView.ts:891-895, parity test arm "a capped run"). The reopened answer now matches live and is never more confident. Not worse; it closes A-71T-10.

### Saving answers

- New code writes and reads at 0011 (`new-0 ... 'high'`); old code keeps writing during the deploy window (`oldafter` rows). The 870-run probe wrote every row with 0 losses (`db-roundtrip mismatches 0`).

### Account forget

- `forget_saved_answers_for_account` now also clears `risk_tier`; M28 shows the test pins it. The function has no caller today (its own docstring), same as develop.

### Saved-answer endpoint

- Wire shape gains one optional field `risk_tier` (max 16). Endpoint test: the whole wire shape set now includes it; old rows answer null (M30 red). An older frontend ignores the extra field; the new frontend maps an absent field to null (api.ts:643, M31 red).

### Migration up and down on a populated table

- See section 3: every row kept both ways, no rewrite, no constraint.

## 4. Items left open, each against develop

- Every `done` emission in core/graph.py, by line: 2296, 2336, 12741, 12783, 12842, 13122 are `trust_outcome="refuse"` (never saved); 14037 carries `trust_line=answer_trust_line(...)`; 14079 (`_partial_result_for_cap`) is `"flag"` with no trust line and emits only a token and done, no trust_signal. core/run.py's fallback done is `"refuse"` (lines 184, 412). So a saved row with trust signals always has a trust line on today's backend.
- A-71T-08 (ungrounded live, reopened drops "Not fully grounded"): with a trust line, develop's saved screen showed the trust line alone; this branch shows the trust line plus the live tag. Probe line: `LIVE[!Not fully grounded | Based on 2 sources cited, not yet confirmed || tag=High-risk claim] SAVED[Based on 2 sources cited, not yet confirmed || tag=High-risk claim]`. The reopened answer gains a warning it lacked on develop and loses nothing. Reachability is further limited: a saved outcome (answer, flag, ask) needs every claim grounded, since an ungrounded claim's outcome is refuse (trust.py:409, 411) and `trust_for_claims` builds surviving claims with `grounded=True` (trust.py:525). No worse than develop.
- A-71T-02 (trust_signal after done): no emitter orders one after done (every emitter above emits signals before done). Develop stored no tier at all, so develop's reopened answer never showed a tag; the branch could only differ in a case no code produces. No worse than develop.
- A-71T-12 (wrapping at phone width): read only, not rendered by me. The saved line is a block Box with inline spans; on develop the same Box held only the trust line and no tag, so the only new wrapping is of the new tag. A break inside "High-risk claim" can show "High-" at a line end. Cosmetic; develop showed no tag at all, which the ticket counts as worse. No worse than develop. Could not verify by rendering.
- J-71T-11 (MCP saved answer carries no tier): read src/system_03_search_agent/adapters/mcp/server.py; the diff does not touch it (`git diff --stat` lists no mcp file). Identical to develop.

## Further findings

### F-V71T-02: the saved fallback can state "Grounded · every claim cited" for a row whose live answer said "Not fully grounded"
- Severity: unsure (not reachable on today's backend, by my reading)
- Inside fix commit 52267651 (A-71T-10's `savedTrustFallback`). Not a regression of a person-visible state: in the same hypothetical, develop showed "✓answer".
- What: `savedTrustFallback("answer", tier)` returns the tick and "Grounded · every claim cited" for any stored tier. The row does not store grounding (A-71T-08), so an answer-outcome run with no trust line and an ungrounded trust signal would reopen as fully grounded. The function's comment rests on "An answer outcome is reached only when every claim was grounded", a backend invariant no test in this change binds.
- Reproduction: 870-run probe, class `{"outcome":"answer","line":false}` with an ungrounded first signal: `LIVE[!Not fully grounded || tag=null] SAVED[✓Grounded · every claim cited || tag=null]` (28 runs, plus the tagged variants). Reachability: the backend saves no such run (section 4: every saved done with trust signals carries a trust line; trust.py:409, 411 map ungrounded to refuse).
- Why it matters: only if a future backend path emits an answer with signals and no trust line; then the reopened answer would read more confident than live, the exact thing the ticket forbids. Recorded so the invariant is visible; not a merge blocker.
- NOT FIXED

### F-V71T-01: see section 1 (rollback-order test matches a lowercase phrase by position; Release_flow.md paragraph untested). Minor, test-only.

## Gates

- `ruff check .` from the checkout root: `All checks passed!`
- gate02's exact command `isort --check-only src tests services tracker alembic .claude .github`: exit 0 (`Skipped 2 files`). Note: isort on app.py alone by path reports unsorted, and so does develop's app.py, so that is a path-resolution artefact, not this change.
- PR #212, head 522676511b25d28351f2cb79a91ae8155d40dfe6, `gh pr checks`: Accessibility (10) pass, Frontend gates (7, 8) pass, Integration suite (5) pass, Python gates (1, 2, 3, 4, 6, 9) pass.

## Verified by my own probes versus read only

- Probed: every fix-round finding by mutation (M1 to M31, each red, each restored); tag parity end to end over 870 runs through the real database (0 tag mismatches); develop's live hook against this branch's over the same 870 runs (only the 36 intended "High-risk claim" wording changes); migration up over 203 populated rows, no rewrite, old code on the new schema, the downgrade keeping every row, the documented rollback order, and the wrong order failing.
- Read only: that the backend never saves a run with trust signals and no trust line (graph.py done emitters, trust.py), which is what keeps F-V71T-02 and the A-71T-08 no-trust-line case unreachable; phone-width wrapping (A-71T-12, not rendered); the MCP output (J-71T-11, untouched by the diff); the Railway start command and service rollback behaviour.

Cleanup: throwaway databases ver71_scratch and ver71_mig dropped (`0` remaining); probe files kept in the session scratchpad; checkout at 522676511b25d28351f2cb79a91ae8155d40dfe6 with `git status --short` showing only `?? frontend/node_modules`.

## Verdict

MERGE (nothing worse than develop). Every fix-round finding confirmed fixed by a mutation that turned a test red. No regression of a fixed finding found. F-V71T-02 sits inside fix commit 52267651 but is unreachable on today's backend and is no worse than develop's "✓answer" in the same hypothetical; F-V71T-01 is test-only.
