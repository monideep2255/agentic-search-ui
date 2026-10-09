# Adversary round, card 71 high-risk tag

Base: 490a62be34685ebb26ebb7d61217f7b9de19da4c (fix/card71-high-risk-tag). Reviewer: adversary, one round, 2026-10-08.

## Findings

### A-71T-01: an empty-string tier hides the tag live but the reopened answer shows "High-risk claim"
- Severity: minor (the contract allows the value; no emitter of "" found today)
- What: `worst_risk_tier_from` drops a `risk_tier` of "" before reducing (`if isinstance(tier, str) and tier`). The live reduce in `useRunView.ts` does not drop it: `RISK_ORDER.indexOf("")` is -1, so "" ranks above every known tier, wins the reduce, and is then falsy, so the live line shows no risk tag at all. `TrustSignalPayload.risk_tier` is `str` with `max_length=16` and no `min_length`, so `Event(type="trust_signal", payload={"risk_tier": "", ...})` validates (probed: constructs fine).
- Reproduction: scratch probe calling `assemble_interaction` with a user owner, one token, trust_signal tiers `["high", ""]` then `done(answer)`. Output: `'high,empty' capture='high' live_worst=''` and `'empty,high' capture='high' live_worst=''`. Saved screen: `riskTagLabel("high")` is "High-risk claim". Live: `payload.risk_tier` is "" so the risk-tag branch is skipped.
- What a person sees: the live answer shows no risk tag; the same answer reopened from history shows a red "High-risk claim". The ticket's parity promise fails in the direction of a tag the person never saw. (The live behaviour is arguably the defect, but the ticket is parity.)
- NOT FIXED

### A-71T-02: a trust_signal after `done` is stored but was never shown live
- Severity: unsure (no emitter found that orders a trust_signal after done; the fallback `done` in `core/run.py` is appended only when no done exists)
- What: the live client stops reading the stream at the first `done` (`useAgentRun.ts`: `if (agentEvent.type === "done") { await reader.cancel(); return; }`). Capture reduces over every trust_signal in the run's event list regardless of position, so a tier that arrives after `done` reaches the saved row but never the live screen.
- Reproduction: probe events `[token, trust_signal(low), done(answer), trust_signal(high)]`. Output: `after-done: capture= 'high' live (stops at done)= 'low'`.
- What a person sees: no tag live, "High-risk claim" on the reopened answer.
- NOT FIXED

### A-71T-03: a tier over 16 characters makes `assemble_interaction` raise, losing the whole row, not just the tier
- Severity: unsure (unreachable through a validated `Event`, which refuses a 17-character tier at construction; reachable only through `Event.model_construct` or a payload dict mutated after construction)
- What: `InteractionRow.risk_tier` has `max_length=16` and `worst_risk_tier_from` passes the raw string through. A 17-character tier raises `ValidationError` inside `assemble_interaction`, before `write_interaction` and therefore before the writer's `_minimal_interaction_values` fallback that exists so a bad payload degrades a row's content and never its existence (F-4.6-A-01). The run is then not saved and not counted against the daily cap. The migration docstring argues the length bound exists so a new tier never loses a saved answer; at the model layer the same bound does exactly that.
- Reproduction: probe with `Event.model_construct(type="trust_signal", payload={"risk_tier": "b"*17, ...})` then `assemble_interaction(user query, [token, that, done(answer)])`. Output: `17-char assemble raised: ValidationError 1 validation error for InteractionRow`. A validated `Event` with the same payload: `17-char Event raised: ValidationError`.
- What a person sees: if reached, their past search is missing from history entirely, not merely missing a tag.
- NOT FIXED

### A-71T-04: new code against the pre-0011 schema loses every row, including the cap-counting minimal row, and breaks reopening every older answer; the migration docstring says it fails "only in capture's best-effort write"
- Severity: minor (Railway's `startCommand` runs `alembic upgrade head &&` before uvicorn, so production should not reach this order; the docstring's claim is false and any environment that starts the app without that command reaches it)
- What: `_minimal_interaction_values` now names `risk_tier`, so the last-resort insert that exists to keep a row (and the daily cap count, F-4.6-A-01) also fails on `UndefinedColumn`. `get_saved_answer` selects `Interaction.risk_tier`, so every reopen raises, for old rows too.
- Reproduction: throwaway database `adv71_scratch` on localhost, `alembic upgrade head` from `origin/develop`'s tree (stops at 0010), a user row inserted, then:
  - develop's code writes `trace-old`: `stored rows: [('trace-old', 'What is BRCA1?', True, [])]`
  - this branch's code writes `trace-newpre`: `interaction write failed ... (ProgrammingError) even with the payload columns dropped; dropping the row rather than failing the query`, `stored rows: []`
  - this branch's `get_saved_answer(owner, "trace-old")`: `get_saved_answer raised: ProgrammingError (psycopg2.errors.UndefinedColumn) column interactions.risk_tier does not exist`
- What a person sees: in that window, a signed-in person's new searches never appear in history and are not counted against the daily limit, and opening any earlier answer from history fails (the endpoint does not catch this, so a server error rather than the 404 "ask it again").
- NOT FIXED

### A-71T-05: rolling the deploy back to the previous build does not start, because the previous build's start command cannot find revision 0011
- Severity: major (the migration's own "Rollback plan" names only `downgrade()`; the obvious rollback, redeploying the previous build in Railway, crash-loops)
- What: `railway.json`'s `startCommand` is `alembic upgrade head && ... uvicorn ...`. Once 0011 has run, the database's `alembic_version` is `0011_interactions_risk_tier`. The previous build's `alembic/versions` has no such file, so its `alembic upgrade head` exits non-zero and `&&` never starts uvicorn. The restart policy retries three times, then the service is down. The general shape is not new to this card (any migration has it), but this card adds a migration and its rollback plan does not state that `alembic downgrade 0010_interactions_saved_answer` must run, with this branch's code, BEFORE the old build is redeployed.
- Reproduction: throwaway database `adv71_scratch`, upgraded to head with this branch's tree. Then from `origin/develop`'s exported tree: `alembic upgrade head` printed `FAILED: Can't locate revision identified by '0011_interactions_risk_tier'`, `alembic exit=255`.
- What a person sees: if the release misbehaves and someone presses "redeploy previous", the site stays down instead of returning to yesterday's version.
- NOT FIXED

### A-71T-06 (confirmation, not a defect): old row reads null, old code after the migration still writes, owner scoping holds
- Severity: none, recorded so the claims below are marked as probed
- Reproduction, same throwaway database: develop's code wrote `trace-old` under 0010; after this branch's `alembic upgrade head`, `get_saved_answer(owner, "trace-old")` gave `('trace-old', None, 'Based on 1 source, not yet confirmed')`; this branch wrote `trace-new` and read `('trace-new', 'high', ...)`; develop's code writing `trace-old2` after 0011 stored the row; a second account reading either trace got `None` (`other owner sees: None`).
- NOT FIXED (nothing to fix)

### A-71T-07: confirmed with the real live code, an empty tier beside "high": live shows no tag, the reopened answer shows "High-risk claim" (A-71T-01 reproduced end to end)
- Severity: minor (same reachability caveat as A-71T-01)
- Reproduction: a throwaway vitest probe feeding the same events to the real `useRunView` and rendering the real `SavedAnswerScreen` with the tier capture stored (`high`, from the Python probe). Events: token, trust_signal(high), trust_signal(""), done(trust_line "Based on 1 source, not yet confirmed"). Output:
  `LIVE : plain:Based on 1 source, not yet confirmed`
  `SAVED: Based on 1 source, not yet confirmed·High-risk claim`
- What a person sees: a red "High-risk claim" on the reopened answer that the live answer never showed.
- NOT FIXED

### A-71T-08: an ungrounded answer shows "Not fully grounded" live but the reopened answer drops it and keeps only the high-risk tag
- Severity: major if reachable (an answer, flag or ask outcome whose trust_signals carry `grounded: false`); unsure on reachability. Not introduced by this card, but sits in the trust-line block this card rewrote, and is the same "live showed a risk span, reopened shows none" shape the ticket is about
- What: the live line pushes `risk:Not fully grounded` whenever any trust_signal is ungrounded. Nothing stores grounding, and the saved screen has no branch for it.
- Reproduction (same vitest probe): events token, trust_signal(high, grounded false), done(trust_line). Output:
  `LIVE : risk:Not fully grounded | plain:Based on 1 source, not yet confirmed | risk:High-risk claim`
  `SAVED: Based on 1 source, not yet confirmed·High-risk claim`
  And with no trust_line and a low ungrounded signal: `LIVE : risk:Not fully grounded` versus `SAVED: ✓answer`.
- What a person sees: the reopened answer reads more confident than the one they were shown; in the second case a green tick replaces a red "Not fully grounded".
- NOT FIXED

### A-71T-09: with no trust_line, the live tag reads "high risk claim" but the reopened one reads "High-risk claim", beside "✓answer" instead of "Grounded · every claim cited"
- Severity: minor (reached only by an answered run whose `done` carries no trust_line but which emitted trust_signals; `answer_trust_line` returns None when there are no grounding claims, which normally also means no trust_signals)
- What: the live pill path (`useRunView.ts` line 967) labels any non-low tier `${tier} risk claim`; only the trust-line path special-cases "High-risk claim". `riskTagLabel` always special-cases it. The saved fallback prints the raw stored outcome word after a tick.
- Reproduction (vitest probe): events token, trust_signal(high), done(no trust_line). Output:
  `LIVE : good:Grounded · every claim cited | risk:high risk claim`
  `SAVED: ✓answer·High-risk claim`
- What a person sees: different words on the reopened answer, and the internal word "answer" after a tick.
- NOT FIXED

### A-71T-10: a run stopped by the per-question cost limit is saved, shows a red "Not verified" live, and reopens with a green tick and the word "flag"
- Severity: major (reachable on today's backend; NOT introduced by this card, the same output is on develop's `SavedAnswerScreen`, but the card rewrote exactly this branch of the trust line and kept it)
- What: `_partial_result_for_cap` (`core/graph.py`) emits the cap note as a token and `done(trust_outcome="flag")` with no trust_line and no trust_signal. "flag" is in `_SAVEABLE_OUTCOMES`, so capture stores the answer. Live: no trust_signal plus landed gives `risk:Not verified · no grounding check was recorded`. Saved: trust_line null, so the fallback renders a green tick and the raw outcome word.
- Reproduction: Python probe, `assemble_interaction` on `[token(PER_QUERY_CAP_PARTIAL_RESULT_NOTE), done(flag)]` for a user: `answer_markdown stored: True trust_signal: flag trust_line: None risk_tier: None`. Vitest probe with the same events and the stored values:
  `LIVE : risk:Not verified · no grounding check was recorded`
  `SAVED: ✓flag`
- What a person sees: a partial answer they were warned about live reopens from history looking verified.
- NOT FIXED

### A-71T-11: the CHECK constraint is added validated, so the migration scans the whole `interactions` table under an ACCESS EXCLUSIVE lock while the previous build is still serving
- Severity: minor (size of the production table unknown to me; read, not timed)
- What: `op.create_check_constraint(...)` in `0011_interactions_risk_tier.py` issues a plain `ALTER TABLE interactions ADD CONSTRAINT ... CHECK (...)`, not `NOT VALID` followed by `VALIDATE CONSTRAINT`. PostgreSQL validates every existing row while holding ACCESS EXCLUSIVE, in the same transaction as the ADD COLUMN, and there is no `lock_timeout`. Railway runs this in the new container's start command while the old container still serves, so every capture write and every history read queues behind it, and if any old-build transaction holds a lock on `interactions` the ALTER itself queues and blocks everything behind it.
- Reproduction: read of `upgrade()`; no `postgresql_not_valid=True`, no `SET lock_timeout`. Not timed against a production-sized table.
- What a person sees: during the deploy, searches and history opens stall for as long as the scan or the lock wait takes; with no lock timeout that is unbounded.
- NOT FIXED

### A-71T-12: on a narrow screen the saved tag can break inside "High-risk" or leave the middle dot alone at a line end; the live line keeps each span whole
- Severity: unsure (read, not rendered at phone width)
- What: the live trust line is a flex row with `flexWrap: "wrap"` and one flex item per span, so "High-risk claim" wraps as a unit. The saved line is a block `Box` with inline text spans, so normal text wrapping applies: a break may fall after "High-" (a hyphen is a break opportunity) or between the aria-hidden "·" and the tag. The saved line also has no `aria-label="Trust signals"` and no info button, which the live one has.
- Reproduction: read of `SavedAnswerScreen.tsx` lines 321 to 367 against `AnswerScreen.tsx` lines 2191 to 2240. Not rendered in a browser this round.
- What a person sees: at phone width the reopened tag may read "High-" on one line and "risk claim" on the next, unlike the live answer.
- NOT FIXED

## Verdict

FAIL against the ticket's parity promise, narrowly. On the normal path the reopened answer shows the tag the live answer showed, and an old row shows none. Two findings are major, A-71T-05 (rolling back to the previous build) and A-71T-10 (a capped answer reopens with a green tick, which was already on develop). A-71T-08 is major only if it can happen. None of the findings sits inside a fix made during this phase. A-71T-08 and A-71T-10 sit in the trust-line block this card rewrote, but the behaviour was already on develop.

Probed myself:
- The capture reduction against the real `useRunView`, through a vitest probe (A-71T-01, 07, 08, 09, 10).
- The 17-character case (A-71T-03).
- Deploy order and rollback on a localhost throwaway database (A-71T-04, 05).
- Old row null after upgrade, owner scoping, account forget clearing the tier, and the database refusing 17 characters (A-71T-06, plus a forget probe: `forgot 3`, every `risk_tier` None, `17 refused: IntegrityError`).

Read only:
- The lock behaviour (A-71T-11).
- Phone-width wrapping (A-71T-12).
- Reachability of an empty tier and of a trust_signal after done.

Probe files were kept outside the checkout or moved out of it afterwards. The throwaway database was dropped. `git status --short` shows only `frontend/node_modules`.
